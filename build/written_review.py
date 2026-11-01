"""Prototype for binding written-solution reviews to the reviewed question."""
import hashlib
from tutorlib.card_diagrams import diagram_descriptions
import json
import copy


def faded_review_items(worked):
    """Inventory written faded checks with the full worked context bound to review."""
    from tutorlib.faded import question_item
    if not isinstance(worked, list):
        raise ValueError('invalid worked examples')
    result = []
    for example in worked:
        if not isinstance(example, dict):
            raise ValueError('invalid worked example')
        faded = example.get('faded')
        if not faded or 'kind' not in faded:
            continue
        item = question_item(faded, example.get('kc'))
        if not isinstance(example.get('id'), str) or not example['id'].strip():
            raise ValueError('worked example needs an id')
        result.append({'id': example['id'] + '.faded', 'stem': item['stem'],
                       'answer': item['review_answer'], 'rubric': item['rubric'],
                       'context': copy.deepcopy({key: value for key, value in example.items() if key != 'faded'})})
    return result


def blind_written_faded(worked):
    return [{'id': item['id'], 'stem': item['stem']} for item in faded_review_items(worked)]


def _inventory_diagram_resolver(resolve):
    """One verified byte snapshot per reference, discarded after this extraction."""
    from types import SimpleNamespace
    snapshots = {}
    def snapshot(reference):
        if reference not in snapshots:
            try:
                path = resolve(reference)
                snapshots[reference] = SimpleNamespace(review_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
            except (OSError, ValueError, KeyError) as exc:
                snapshots[reference] = exc
        result = snapshots[reference]
        if isinstance(result, Exception):
            raise result
        return result
    return snapshot


def _visible_form_steps(forms, *, card=None, diagram_resolver=None):
    """Full lesson path: rubric-bearing examples then unanswered check stems.

    Retries and feedback depend on learner responses, so are never projected here.
    """
    steps = []
    for index, form in enumerate(forms):
        if not isinstance(form, dict) or not form.get('rubric'):
            continue
        wordings = ", ".join(form.get('wordings', []))
        step = {'phase': f'form_example:{index}', 'title': form.get('name', ''),
                'text': f"**Wording:** {wordings}\n\n{form.get('example', '')}"}
        if form.get('diagram'):
            step['diagram'] = form['diagram']
            step['diagram_context'] = _visible_diagram(form['diagram'], card or {}, diagram_resolver)
        steps.extend([step, {'phase': f'form_check:{index}', 'stem': form.get('check', '')}])
    return steps


def _visible_diagram(reference, card, resolver):
    diagrams = card.get('diagrams') or []
    descriptions = diagram_descriptions(card)
    index = diagrams.index(reference) if reference in diagrams else -1
    result = {'reference': reference,
              'description': descriptions[index] if 0 <= index < len(descriptions) else 'See the diagram in Obsidian.'}
    if resolver is None:
        result['hash_status'] = 'unresolved: review extraction has no asset resolver'
    else:
        try:
            resolved = resolver(reference)
            result['sha256'] = resolved.review_sha256
        except (OSError, ValueError, KeyError) as exc:
            result['hash_status'] = f'unresolved: {type(exc).__name__}'
    return result


def _current_visible_diagrams(card, form, index, resolver):
    """Figures shown before this form check on the full lesson path.

    The first non-form figure accompanies the introduction; remaining non-form
    figures have dedicated phases. Other forms' solution figures are excluded.
    """
    diagrams = card.get('diagrams') or []
    form_figures = {entry.get('diagram') for entry in card.get('forms', [])
                    if isinstance(entry, dict) and isinstance(entry.get('diagram'), str)}
    result = []
    intro = None
    for number, reference in enumerate(diagrams):
        if reference in form_figures:
            continue
        phase = 'introduction' if intro is None else f'diagram:{number}'
        if intro is None:
            intro = reference
        result.append({'phase': phase, **_visible_diagram(reference, card, resolver)})
    if form.get('diagram') in diagrams:
        result.append({'phase': f'form_example:{index}', **_visible_diagram(form['diagram'], card, resolver)})
    return result


def _possible_other_card_context(cards, current, diagram_resolver=None):
    """Safe projections, not an asserted traversal order: graph/session choose KCs."""
    result = []
    for kc, card in cards.items():
        if kc == current or not isinstance(card, dict):
            continue
        content = {'motivate': card.get('motivate', '')}
        if card.get('plain_words'):
            content['primary_explanation'] = {'phase': 'plain_words', 'text': card['plain_words']}
            content['conditional_detail'] = {
                'visibility': 'conditional: learner requests More detail and answer guard allows it',
                'text': card.get('establish', '') + ('\n\n**How it connects:** ' + card['connect'] if card.get('connect') else '')}
        else:
            content['primary_explanation'] = {'phase': 'establish', 'text': card.get('establish', '') + ('\n\n**How it connects:** ' + card['connect'] if card.get('connect') else '')}
        content['terms'] = [{key: copy.deepcopy(term[key]) for key in ('term', 'meaning', 'notation', 'spoken')
                             if key in term} for term in card.get('terms', []) if isinstance(term, dict)]
        content['exam_language'] = [{key: copy.deepcopy(entry[key]) for key in ('name', 'meaning') if key in entry}
                                    for entry in card.get('exam_language', []) if isinstance(entry, dict)]
        content['misconceptions'] = [
            {'text': f"**The idea:** {entry.get('idea', '')}\n\n**Why it is tempting:** {entry.get('temptation', '')}\n\n**The fix:** {entry.get('fix', '')}"}
            for entry in card.get('misconceptions', []) if isinstance(entry, dict)]
        content['diagrams'] = [_visible_diagram(ref, card, diagram_resolver) for ref in card.get('diagrams', [])]
        content['form_steps'] = _visible_form_steps(card.get('forms', []), card=card, diagram_resolver=diagram_resolver)
        result.append({'kc': kc, 'visibility': 'conditional: only if this KC was taught earlier; order requires lesson graph/session',
                       'content': content})
    return result


def review_items(cards, *, diagram_resolver=None):
    """Extract the exact written checks and marking data; malformed forms fail closed."""
    if not isinstance(cards, dict):
        raise ValueError('invalid cards')
    if diagram_resolver is not None:
        diagram_resolver = _inventory_diagram_resolver(diagram_resolver)
    result = []
    for kc, card in cards.items():
        if not isinstance(kc, str) or not isinstance(card, dict):
            raise ValueError('invalid card')
        forms = card.get('forms', [])
        if not isinstance(forms, list):
            raise ValueError('invalid forms')
        for index, form in enumerate(forms):
            if not isinstance(form, dict):
                raise ValueError('invalid form')
            entries = [('check', form)]
            if 'retry' in form:
                entries.append(('retry', form['retry']))
            for kind, entry in entries:
                if (not isinstance(entry, dict) or not isinstance(entry.get('check'), str)
                        or not entry['check'].strip() or not isinstance(entry.get('answer'), str)
                        or not entry['answer'].strip() or not isinstance(entry.get('rubric'), list)
                        or not entry['rubric']):
                    raise ValueError(f'invalid written check: {kc} form {index} {kind}')
                result.append({'id': f'{kc}.form.{index}.{kind}', 'stem': entry['check'],
                               'answer': entry['answer'], 'rubric': entry['rubric'],
                               'context': copy.deepcopy({'form': form.get('name', ''),
                                           'review_rule': entry.get('review_rule', form.get('review_rule')),
                                           'example': form.get('example'), 'wordings': form.get('wordings'),
                                           'form_content': form,
                                           'current_visible_diagrams': _current_visible_diagrams(card, form, index, diagram_resolver),
                                           'learner_visible_prior': _visible_form_steps(forms[:index], card=card, diagram_resolver=diagram_resolver),
                                           'possible_other_kc_context': _possible_other_card_context(cards, kc, diagram_resolver),
                                           'card_context': {key: value for key, value in card.items() if key != 'forms'}})})
    return result


def fingerprint(item):
    payload = item
    raw = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()


def build_records(items, solutions, decisions, *, solver, reviewer):
    """Bind separate solver output and review decisions; identities are attestations, not authentication."""
    if (not isinstance(items, list) or not items or not isinstance(solutions, dict) or not isinstance(decisions, dict)
            or not isinstance(solver, str) or not solver.strip() or not isinstance(reviewer, str)
            or not reviewer.strip() or solver.strip().casefold() == reviewer.strip().casefold()):
        raise ValueError('invalid or non-independent review inputs')
    ids = [item.get('id') for item in items if isinstance(item, dict)]
    if (len(ids) != len(items) or any(not isinstance(i, str) or not i.strip() for i in ids)
            or len(set(ids)) != len(ids) or set(ids) != set(solutions) or set(ids) != set(decisions)):
        raise ValueError('solutions and decisions must cover the exact inventory')
    records = {}
    for item in items:
        ident = item['id']
        solution = solutions[ident]
        decision = decisions[ident]
        if not isinstance(decision, dict):
            raise ValueError('invalid review decision')
        records[ident] = {'fingerprint': fingerprint(item), 'solution': solution, 'solver': solver,
                          'reviewer': reviewer, 'verdict': decision.get('verdict'),
                          'rationale': decision.get('rationale'),
                          'solution_hash': fingerprint({'id': ident, 'stem': solution, 'answer': None, 'rubric': None})}
    if validate_reviews(items, records):
        raise ValueError('incomplete or unaccepted review')
    return records


def validate_reviews(items, reviews):
    if not isinstance(items, list) or not items or not isinstance(reviews, dict):
        return ["invalid or empty review inventory"]
    issues = []
    seen = set()
    for item in items:
        if (not isinstance(item, dict) or not isinstance(item.get('id'), str) or not item['id'].strip()
                or not isinstance(item.get('stem'), str) or not item['stem'].strip()
                or not isinstance(item.get('answer'), str) or not item['answer'].strip()
                or not isinstance(item.get('rubric'), list) or not item['rubric']):
            issues.append('invalid review item')
            continue
        ident = item['id']
        if ident in seen:
            issues.append(f'{ident}: duplicate identity')
            continue
        seen.add(ident)
        review = reviews.get(ident)
        if not isinstance(review, dict) or review.get('fingerprint') != fingerprint(item):
            issues.append(f'{ident}: missing or stale review')
            continue
        solution_hash = fingerprint({'id': ident, 'stem': review.get('solution'), 'answer': None, 'rubric': None})
        if review.get('solution_hash') != solution_hash:
            issues.append(f'{ident}: solution changed after review')
            continue
        if (review.get('verdict') != 'accepted' or any(not isinstance(review.get(k), str) or not review[k].strip()
                for k in ('solution', 'solver', 'reviewer', 'rationale')) or
                (isinstance(review.get('solver'), str) and isinstance(review.get('reviewer'), str)
                 and review['solver'].strip().casefold() == review['reviewer'].strip().casefold())):
            issues.append(f'{ident}: incomplete or unaccepted review')
    return issues


def pack_review_items(pack, *, diagram_resolver=None):
    """One exact inventory for Foundry and Refine: guided checks/retries plus written faded examples."""
    return (review_items(pack.get('teach', {}), diagram_resolver=diagram_resolver)
            + faded_review_items(pack.get('worked', [])))


def file_hash(path):
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def read_json(path):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


def evidence_path(reference, *, root, work, blind):
    from pathlib import Path
    if (not isinstance(reference, str) or not reference or Path(reference).is_absolute()
            or '..' in Path(reference).parts):
        raise ValueError('invalid written evidence path')
    path = root / reference
    if not any(path.resolve().is_relative_to(folder.resolve()) for folder in (work, blind)):
        raise ValueError('written evidence is outside the worker evidence directories')
    return path


def proof_item(ident: str, record: dict, *, root, work, blind) -> dict:
    """Verify durable source artifacts and return the exact independently reviewed item."""
    evidence = record.get('evidence')
    if (not isinstance(evidence, dict) or evidence.get('version') != 1
            or evidence.get('solver') != record.get('solver')
            or evidence.get('reviewer') != record.get('reviewer')
            or not isinstance(evidence.get('files'), dict)
            or set(evidence['files']) != {'batch', 'questions', 'answers', 'items', 'decisions'}):
        raise ValueError('missing durable independent worker evidence')
    data = {}
    for kind, entry in evidence['files'].items():
        if not isinstance(entry, dict) or not isinstance(entry.get('sha256'), str):
            raise ValueError('invalid written evidence reference')
        path = evidence_path(entry.get('path'), root=root, work=work, blind=blind)
        if entry['sha256'] != file_hash(path):
            raise ValueError(f'{kind} written evidence missing or changed')
        data[kind] = read_json(path)
    batch = data['batch']
    if (not isinstance(batch, dict) or not isinstance(batch.get('id'), str) or not batch['id']
            or batch.get('id') != evidence.get('batch_id')
            or not isinstance(batch.get('items'), list)
            or not isinstance(batch.get('solutions'), dict)
            or batch.get('questions_hash') != evidence['files']['questions']['sha256']
            or batch.get('solver_output_hash') != evidence['files']['answers']['sha256']
            or batch.get('review_items_hash') != evidence['files']['items']['sha256']):
        raise ValueError('invalid reviewed written batch')
    inventory = batch['items']
    if (any(not isinstance(it, dict) or not isinstance(it.get('id'), str) or not isinstance(it.get('stem'), str)
            for it in inventory) or len({it['id'] for it in inventory}) != len(inventory)):
        raise ValueError('invalid reviewed inventory')
    item = next((it for it in inventory if it['id'] == ident), None)
    if (item is None or data['questions'] != [{'id': it['id'], 'stem': it['stem']} for it in inventory]
            or data['answers'] != batch['solutions']
            or set(batch['solutions']) != {it['id'] for it in inventory}
            or data['items'] != [{**it, 'solution': batch['solutions'].get(it['id'])} for it in inventory]
            or batch['solutions'].get(ident) != record.get('solution')
            or not isinstance(data['decisions'], dict)):
        raise ValueError('written evidence does not match the reviewed inventory and solution')
    decision = data['decisions'].get(ident)
    if (not isinstance(decision, dict) or decision.get('verdict') != 'accepted'
            or decision.get('rationale') != record.get('rationale')):
        raise ValueError('independent reviewer did not accept this exact solution')
    return item


def independent_record_problems(items: list[dict], records, *, root, work, blind) -> list[str]:
    issues = validate_reviews(items, records)
    if not isinstance(records, dict):
        return issues
    for item in items:
        ident = item.get('id')
        record = records.get(ident)
        if not isinstance(record, dict):
            continue
        try:
            if proof_item(ident, record, root=root, work=work, blind=blind) != item:
                raise ValueError('durable evidence belongs to different written content')
        except (OSError, ValueError, TypeError, KeyError) as exc:
            issues.append(f'{ident}: {exc}')
    return issues

