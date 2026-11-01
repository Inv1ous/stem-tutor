"""Bound automatic worker failures without altering content or review gates."""
import hashlib
import json
from pathlib import Path


MAX_FAILURES = 2


def _pass(state):
    return str(state.get('pass', 1))


def launch_problem(state, role, inputs: list[Path], *, baseline: dict | None = None, diagram_catalog=None) -> str | None:
    """Return a reason to pause; inspect inputs and baseline without modifying state."""
    failures = state.get('reliability_failures', {}).get(_pass(state), {}).get(role, [])
    if len(failures) >= MAX_FAILURES:
        return f'{role} paused after {len(failures)} failures in this pass; inspect evidence and clear failures explicitly'
    if baseline is not None:
        try:
            pack = baseline['pack']
            items = pack['items']
            if not isinstance(items, list):
                raise ValueError('baseline items must be a list')
            import content_checks
            debris = content_checks.debris_problems({'items': items})
        except (KeyError, TypeError, ValueError, ImportError) as exc:
            return f'baseline preflight failed: {exc}'
        if debris:
            return 'baseline PDF debris in preserved items requires repair before this pass: ' + '; '.join(debris)
    # Registration is controller-owned; another authoring attempt cannot repair catalog ownership.
    previous = state.get('jobs', {}).get(role, {})
    if diagram_catalog is not None and role in ('drafter', 'refiner', 'fixer') and previous.get('ok') is False:
        try:
            pack = json.loads(Path(inputs[0]).read_text()) if inputs else {}
            if not isinstance(pack, dict):
                raise ValueError('candidate must be an object')
            teaching = pack.get('teach') or {}
            if not isinstance(teaching, dict):
                raise ValueError('candidate teach must be an object')
            references = [request.get('file') if isinstance(request, dict) else None
                          for request in pack.get('diagrams', [])]
            # Match the lesson display gate: card paths are checked even without descriptions.
            # A form diagram can display only when declared in its card's diagrams; the
            # guided-card validator separately rejects undeclared form references.
            for card in teaching.values():
                if isinstance(card, dict) and isinstance(card.get('diagrams'), list):
                    references.extend(path for path in card['diagrams'] if isinstance(path, str))
            for reference in dict.fromkeys(references):
                try:
                    diagram_catalog.resolve(reference)
                except (OSError, ValueError, TypeError, KeyError) as exc:
                    return (f'unregistered or damaged diagram {reference!r}: {exc}; controller must review staged '
                            'asset provenance/hash and register/map it before paid retry; do not grant worker Library access')
        except (OSError, ValueError, TypeError) as exc:
            return f'diagram registration preflight failed: {exc}'
    try:
        fingerprint(state, role, inputs)
    except (OSError, ValueError, UnicodeError) as exc:
        return f'{role} input preflight failed: {exc}'
    return None


def fingerprint(state, role, inputs: list[Path]) -> str:
    """Hash the role, pass and exact inputs; malformed JSON is not launchable."""
    from .candidates import verified_bytes
    digest = hashlib.sha256()
    digest.update(json.dumps([role, _pass(state)], separators=(',', ':')).encode())
    for path in inputs:
        path = Path(path)
        data = verified_bytes(path)
        if path.suffix.lower() == '.json':
            json.loads(data)
        name = str(path).encode()
        digest.update(len(name).to_bytes(8, 'big'))
        digest.update(name)
        digest.update(len(data).to_bytes(8, 'big'))
        digest.update(data)
    return digest.hexdigest()


def record_result(state, name, *, ok: bool, exit_code: int, issues: list[str]) -> None:
    """Record a bounded per-role failure history, including timeouts and invalid output."""
    role = name.split('#', 1)[0]
    current = state.setdefault('reliability_failures', {}).setdefault(_pass(state), {})
    if ok:
        return
    job = state.get('jobs', {}).get(name, {})
    records = current.setdefault(role, [])
    records.append({'exit_code': exit_code, 'issues': list(issues),
                    'failure_input': job.get('failure_input')})
    del records[:-MAX_FAILURES]


def clear_failures(state, reason) -> None:
    """Archive the existing guard state after an explicit operator decision."""
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError('a reason is required to clear failures')
    failures = state.pop('reliability_failures', {})
    state.setdefault('reliability_history', []).append({'reason': reason, 'failures': failures})


def collect_safely(context):
    """Always finalize failed collection, including errors outside content gates."""
    import functools
    from .lifecycle import timestamp
    def decorate(function):
        @functools.wraps(function)
        def wrapped(name, sub, *args, **kwargs):
            try:
                return function(name, sub, *args, **kwargs)
            except Exception as exc:
                message = f'collection {type(exc).__name__}: {exc}'
                with context(sub) as state:
                    job = state.setdefault('jobs', {}).setdefault(name, {})
                    job.update(finished=timestamp(), exit=-1, ok=False, collection_error=message)
                    state['gates'] = {'ok': False, 'collection': 1, 'first': [message]}
                    record_result(state, name, ok=False, exit_code=-1, issues=[message])
                    state.setdefault('history', []).append({'t': timestamp(), 'from': state['stage'],
                                                            'to': state['stage'], 'note': message})
                print(f'{sub}: {message}; candidate preserved')
        return wrapped
    return decorate


def output_problem(path, role):
    """Reject malformed role artifacts before completion can advance the board."""
    try:
        value = json.loads(Path(path).read_text())
        if role == 'checker':
            if not isinstance(value, dict) or not isinstance(value.get('findings'), list) or any(not isinstance(row, dict) for row in value['findings']):
                return 'checker output must contain a findings list of objects'
        elif role in ('solver', 'wsolver', 'wreviewer', 'tiebreak', 'scout'):
            if not isinstance(value, dict):
                return f'{role} output must be an object'
        if role in ('solver', 'wsolver') and any(not isinstance(answer, str) or not answer.strip() for answer in value.values()):
            return 'solver answers must be nonempty strings'
        if role == 'solver':
            path = Path(path)
            questions = path.with_name(path.name.replace('.answers', '.questions', 1))
            if questions == path:
                return 'solver answers need a matching question inventory'
            inventory = json.loads(questions.read_text())
            if (not isinstance(inventory, list) or any(not isinstance(q, dict) or not isinstance(q.get('id'), str) for q in inventory)
                    or set(value) != {q['id'] for q in inventory}):
                return 'solver answers must cover the exact question inventory'
    except (OSError, ValueError, UnicodeError) as exc:
        return f'invalid {role} output: {exc}'
    return None
