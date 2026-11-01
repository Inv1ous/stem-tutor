"""Frozen paired STEM evaluation, with separate generation and CPU scoring.

Importing this module uses only the standard library. Generation requires an
explicit command in the isolated SSD MLX environment. Gold is never placed in
generation prompts. Neither hidden thoughts nor generated executable code are
recorded or evaluated as Python.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from contextlib import closing
from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import re
import time


IDENTITY = 'STEM Tutor. Reply in document JSON.'
PROTOCOL_SYSTEM = {
    'training': None,
    'legacy_system': IDENTITY,
    'neutral_system': 'STEM Tutor. Follow the JSON contract requested by the current task.',
}
SUBJECTS = ('chem', 'math', 'phys')
POLICY = 'subject/task round-robin, SHA256(seed:id) order; metadata only; correlated groups reported'


def generation_messages(row, protocol):
    """Match explicit training or diagnostic roles without consulting any gold."""
    if protocol not in PROTOCOL_SYSTEM:
        raise ValueError('Unknown generation protocol')
    messages = row.get('messages')
    if (not isinstance(messages, list) or len(messages) != 2
            or not all(isinstance(message, dict) for message in messages)
            or messages[1].get('role') != 'assistant'):
        raise ValueError('Dataset requires one user followed by one assistant gold message')
    user = messages[0]
    if (set(user) != {'role', 'content'} or user['role'] != 'user'
            or not isinstance(user['content'], str) or not user['content'].strip()):
        raise ValueError('Invalid evaluation user message')
    copied = {'role': 'user', 'content': user['content']}
    system = PROTOCOL_SYSTEM[protocol]
    return [{'role': 'system', 'content': system}, copied] if system else [copied]


def _format_context(protocol):
    if protocol not in PROTOCOL_SYSTEM:
        raise ValueError('Unknown generation protocol')
    return {'protocol': protocol, 'system': PROTOCOL_SYSTEM[protocol],
            'description': ('Dataset user only, matching the training input roles.' if protocol == 'training'
                            else 'Fixed diagnostic system message followed by the unchanged dataset user.'),
            'added_schema_or_examples': False}


def _json(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(',', ':'))


def _hash(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            result.update(chunk)
    return result.hexdigest()


def _write_new(path, value):
    with Path(path).open('x') as handle:
        handle.write(_json(value) + '\n')


def select_rows(rows, per_subject=40, seed=42):
    """Balance subjects and tasks without consulting prompts, answers or checks."""
    if type(per_subject) is not int or not 1 <= per_subject <= 40:
        raise ValueError('per_subject must be 1..40')
    buckets, seen = defaultdict(lambda: defaultdict(list)), set()
    rank = lambda value: hashlib.sha256(f'{seed}:{value}'.encode()).hexdigest()
    for row in rows:
        identifier, subject, task = row.get('id'), row.get('subject'), row.get('task')
        if not isinstance(identifier, str) or not identifier or identifier in seen:
            raise ValueError('Duplicate or invalid held-out id')
        if subject not in SUBJECTS or not isinstance(task, str) or not task:
            raise ValueError('Invalid held-out subject/task')
        if not isinstance(row.get('group'), str) or not row['group']:
            raise ValueError('Invalid held-out group')
        seen.add(identifier)
        buckets[subject][task].append(row)
    selected = []
    for subject in SUBJECTS:
        tasks = buckets[subject]
        for values in tasks.values():
            values.sort(key=lambda row: rank(row['id']))
        ordered = sorted(tasks, key=rank)
        chosen = []
        while len(chosen) < per_subject and any(tasks.values()):
            for task in ordered:
                if tasks[task] and len(chosen) < per_subject:
                    chosen.append(tasks[task].pop(0))
        selected.extend(chosen)
    return selected


def _test_rows(data_dir):
    root = Path(data_dir)
    manifest_path, test_path = root / 'manifest.json', root / 'test.jsonl'
    manifest = json.loads(manifest_path.read_text())
    if manifest.get('files', {}).get('test.jsonl', {}).get('sha256') != _hash(test_path):
        raise ValueError('Evaluation file hash differs from its dataset manifest')
    rows = [json.loads(line) for line in test_path.read_text().splitlines() if line.strip()]
    return rows, _hash(manifest_path), _hash(test_path)


def freeze_selection(data_dir, output, per_subject=40, seed=42):
    rows, manifest_hash, test_hash = _test_rows(data_dir)
    selected = select_rows(rows, per_subject, seed)
    receipt = {'version': 1, 'policy': POLICY, 'seed': seed, 'per_subject': per_subject,
               'evaluation_role': json.loads((Path(data_dir) / 'manifest.json').read_text()).get('evaluation_role', 'sealed_test'),
               'dataset_manifest_sha256': manifest_hash, 'test_sha256': test_hash,
               'ids': [r['id'] for r in selected], 'rows': len(selected),
               'groups': len({r['group'] for r in selected}),
               'by_subject': {s: {'rows': sum(r['subject'] == s for r in selected),
                                  'groups': len({r['group'] for r in selected if r['subject'] == s})}
                              for s in SUBJECTS},
               'tasks': dict(sorted(Counter(r['task'] for r in selected).items())),
               'caution': 'Variants in one group are correlated; row counts are not independent samples.'}
    _write_new(output, receipt)
    return receipt


def load_selection(data_dir, selection_path):
    rows, manifest_hash, test_hash = _test_rows(data_dir)
    receipt = json.loads(Path(selection_path).read_text())
    if receipt.get('dataset_manifest_sha256') != manifest_hash or receipt.get('test_sha256') != test_hash:
        raise ValueError('Selection dataset hash changed')
    role = json.loads((Path(data_dir) / 'manifest.json').read_text()).get('evaluation_role', 'sealed_test')
    if receipt.get('evaluation_role', 'sealed_test') != role:
        raise ValueError('Selection evaluation role changed')
    selected = select_rows(rows, receipt['per_subject'], receipt['seed'])
    if receipt.get('policy') != POLICY or receipt.get('ids') != [r['id'] for r in selected]:
        raise ValueError('Selection policy or ordered ids changed')
    return selected, receipt


def select_protocol_development(rows, seed=42):
    """Keep all twelve VALID marking rows plus six metadata-chosen documents."""
    rows = list(rows)
    select_rows(rows, seed=seed)  # Validate all metadata, including cross-contract duplicate IDs.
    rank = lambda row: hashlib.sha256(('protocol-dev-v1:' + row['id']).encode()).hexdigest()
    selected = sorted([row for row in rows if row['task'] == 'marking'], key=rank)
    if len(selected) != 12:
        raise ValueError('Protocol development v1 requires exactly twelve original marking rows')
    for subject in SUBJECTS:
        for task in ('published_flashcard', 'literal_json'):
            bucket = [row for row in rows if row['subject'] == subject and row['task'] == task]
            if not bucket:
                raise ValueError(f'Protocol development v1 requires {task} for {subject}')
            selected.append(min(bucket, key=rank))
    return selected


def build_protocol_development(data_dir, output, seed=42):
    """Copy a metadata-chosen VALID subset into a clearly labelled diagnostic corpus."""
    source, target = Path(data_dir).resolve(), Path(output).resolve()
    if target.exists():
        raise FileExistsError(target)
    if target.is_relative_to(source) or source.is_relative_to(target):
        raise ValueError('Diagnostic output must be separate from the original dataset')
    source_manifest = source / 'manifest.json'
    manifest = json.loads(source_manifest.read_text())
    valid = source / 'valid.jsonl'
    valid_hash = _hash(valid)
    if manifest.get('files', {}).get('valid.jsonl', {}).get('sha256') != valid_hash:
        raise ValueError('Development file hash differs from the original dataset manifest')
    rows = [json.loads(line) for line in valid.read_text().splitlines() if line.strip()]
    selected = select_protocol_development(rows, seed=seed)
    target.mkdir(parents=True, exist_ok=False)
    with (target / 'test.jsonl').open('x') as handle:
        handle.write(''.join(_json(row) + '\n' for row in selected))
    receipt = {'version': 1, 'evaluation_role': 'development_protocol_diagnostic',
               'source_split': 'valid', 'purpose': 'DEVELOPMENT ONLY; not sealed-test promotion evidence.',
               'source_dataset_manifest_sha256': _hash(source_manifest), 'source_valid_sha256': valid_hash,
               'seed': seed, 'rows': len(selected), 'groups': len({row['group'] for row in selected}),
               'selection_policy': "All twelve VALID marking rows plus one published_flashcard and one literal_json per subject; SHA256('protocol-dev-v1:' + id) within buckets; metadata only.",
               'marking_groups': sorted({row['group'] for row in selected if row['task'] == 'marking'}),
               'files': {'test.jsonl': {'sha256': _hash(target / 'test.jsonl'), 'rows': len(selected)}},
               'ids': [row['id'] for row in selected],
               'by_subject_contract': {subject: {'document': sum(row['subject'] == subject and row['task'] != 'marking' for row in selected),
                                                'marking': sum(row['subject'] == subject and row['task'] == 'marking' for row in selected)}
                                       for subject in SUBJECTS}}
    _write_new(target / 'manifest.json', receipt)
    freeze_selection(target, target / 'selection.json', per_subject=40, seed=seed)
    return receipt


def _strict_object(text):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Duplicate JSON key')
            result[key] = value
        return result
    def invalid_constant(value):
        raise ValueError(f'Invalid JSON constant: {value}')
    value = json.loads(text, object_pairs_hook=pairs, parse_constant=invalid_constant)
    if not isinstance(value, dict):
        raise ValueError('One JSON object is required')
    return value


def _marking(value):
    if set(value) != {'points', 'feedback'} or not isinstance(value['feedback'], str):
        raise ValueError('Invalid marking envelope')
    points = value['points']
    if not isinstance(points, list) or not points:
        raise ValueError('Invalid marking points')
    for point in points:
        if (not isinstance(point, dict) or set(point) != {'point', 'met', 'why'}
                or type(point['met']) is not bool
                or any(not isinstance(point[key], str) for key in ('point', 'why'))):
            raise ValueError('Invalid marking point')


def score_trial(row, trial):
    """Score inspectable evidence; science and OPEN protection require review."""
    checks, expected = row['checks'], row['expected']
    delivered = trial.get('finish_reason') == 'stop' and bool(trial.get('text', '').strip()) and not trial.get('error')
    score = {'delivered': delivered, 'raw_contract_valid': False, 'host_contract_valid': False,
             'repaired': False, 'exact_document_match': False,
             'science_status': 'manual_review_required',
             'evidence_category': ('source_copy' if checks.get('source_fidelity') else
                                   'curated_marking' if checks.get('schema') == 'marking' else
                                   'source_free_recall' if checks.get('source_free') else 'synthetic_or_curated'),
             'open_protection_status': 'manual_review_required' if checks.get('open_answer_protected') else 'not_applicable'}
    if checks.get('schema') == 'marking':
        score.update(marking_labels_equal=False, marking_envelope_valid=False,
                     marking_criteria_equal=None, marking_vector_available=False,
                     marking_decision_vector=None, marking_vector_correct=None)
    if checks.get('source_fidelity'):
        score['source_copy_exact'] = False
    code = [b['text'] for b in expected.get('blocks', []) if b['kind'] == 'code']
    if code:
        score['literal_code_equal'] = False
    if not delivered:
        return score
    try:
        raw = _strict_object(trial['text'])
        if checks.get('schema') == 'marking':
            _marking(raw)
            document = raw
            same_criteria = [p['point'] for p in raw['points']] == [p['point'] for p in expected['points']]
            decisions = [p['met'] for p in raw['points']]
            correct = decisions == [p['met'] for p in expected['points']]
            score.update(marking_envelope_valid=True, marking_criteria_equal=same_criteria,
                         marking_vector_available=True, marking_decision_vector=decisions,
                         marking_vector_correct=correct if same_criteria else None,
                         marking_labels_equal=same_criteria and correct)
        else:
            # Only CPU scoring needs the app's renderer dependencies.
            from .chat_output import DocumentDecoder
            decoder = DocumentDecoder(speech='speech' in expected)
            decoder.feed(trial['text'])
            decoder.finish()
            document = decoder.document
        score.update(host_contract_valid=True, raw_contract_valid=raw == document,
                     repaired=raw != document, exact_document_match=document == expected)
        if checks.get('source_fidelity'):
            score['source_copy_exact'] = document == expected
        if code:
            score['literal_code_equal'] = [b['text'] for b in document.get('blocks', []) if b['kind'] == 'code'] == code
    except (ValueError, KeyError, TypeError) as exc:
        score['format_error'] = str(exc)
    return score


class VisibleTokens:
    """Discard thought tokens immediately; retain only final token ids."""
    def __init__(self, thinking, open_token, close_token, stop_tokens):
        self.hidden = thinking
        self.open_token, self.close_token, self.stop_tokens = open_token, close_token, set(stop_tokens)
        self.reasoning_tokens = 0
        self.tokens = []

    def feed(self, token):
        if token == self.open_token:
            self.hidden = True
        elif token == self.close_token:
            self.hidden = False
        elif token not in self.stop_tokens:
            if self.hidden:
                self.reasoning_tokens += 1
            else:
                self.tokens.append(token)


@dataclass(frozen=True)
class EvaluationConfig:
    seed: int = 42
    max_tokens: int = 4096
    deadline_seconds: int = 180
    memory_limit_gib: int = 14
    identity: str = IDENTITY
    protocol: str = 'training'
    presence_penalty: float = 1.5

    def sampling(self, mode):
        if mode not in {'fast', 'deep'}:
            raise ValueError('Mode must be fast or deep')
        self.validate()
        if mode == 'deep' and self.presence_penalty != 1.5:
            raise ValueError('Alternate presence penalty is a Fast-only development diagnostic')
        return {'temperature': 1.0 if mode == 'deep' else .7,
                'top_p': .95 if mode == 'deep' else .8, 'top_k': 20,
                'presence_penalty': self.presence_penalty, 'presence_context_size': 1024}

    def validate(self):
        if not 1 <= self.max_tokens <= 8192 or not 1 <= self.deadline_seconds <= 300:
            raise ValueError('Evaluation token/time bounds exceeded')
        if not 2 <= self.memory_limit_gib <= 14 or self.identity != IDENTITY:
            raise ValueError('Evaluation memory/identity differs from frozen policy')
        if type(self.presence_penalty) not in (int, float) or self.presence_penalty not in (0.0, 1.5):
            raise ValueError('Presence penalty must be exactly 0.0 or 1.5')
        _format_context(self.protocol)


def _attempt_number(output, identifier):
    prefix = hashlib.sha256(identifier.encode()).hexdigest()[:24]
    numbers = [int(match[1]) for path in Path(output).iterdir()
               if (match := re.fullmatch(re.escape(prefix) + r'\.(\d+)\.(?:json|started)', path.name))]
    return prefix, max(numbers, default=0) + 1


def start_attempt(output, identifier, value):
    prefix, index = _attempt_number(output, identifier)
    path = Path(output) / f'{prefix}.{index:03d}.started'
    _write_new(path, dict(value, id=identifier, attempt=index, state='started'))
    return path


def write_attempt(output, identifier, value, attempt=None):
    """Append an immutable attempt, preserving failed/interrupted predecessors."""
    safe, index = _attempt_number(output, identifier)
    if attempt is not None:
        if type(attempt) is not int or attempt < 1:
            raise ValueError('Invalid stable attempt number')
        index = attempt
    while True:
        path = Path(output) / f'{safe}.{index:03d}.json'
        try:
            _write_new(path, dict(value, id=identifier, attempt=index))
            return path
        except FileExistsError:
            if attempt is not None:
                raise
            index += 1


def read_attempts(output):
    """Reconcile starts with terminal files; unmatched starts are interruptions."""
    records, starts = {}, {}
    for path in sorted(Path(output).iterdir()):
        if not re.fullmatch(r'[a-f0-9]{24}\.\d+\.(?:json|started)', path.name):
            continue
        value = json.loads(path.read_text())
        if not isinstance(value.get('id'), str) or type(value.get('attempt')) is not int:
            raise ValueError('Attempt record is missing its stable identity')
        key = value['id'], value['attempt']
        target = starts if path.suffix == '.started' else records
        target[key] = dict(value, artifact_file=path.name, artifact_sha256=_hash(path))
    for key, start in starts.items():
        if key not in records:
            records[key] = dict(start, state='interrupted', text='', finish_reason=None,
                                error='Interrupted before a terminal result was recorded')
    return sorted(records.values(), key=lambda record: (record['id'], record['attempt']))


def needs_trial(identifier, attempts, retry_failed=False):
    prior = [p for p in attempts if p.get('id') == identifier and p.get('state') != 'started']
    if not prior:
        return True
    latest = max(prior, key=lambda p: p['attempt'])
    if latest.get('state') == 'interrupted':
        return True
    delivered = (latest.get('state') == 'complete' and latest.get('finish_reason') == 'stop'
                 and bool(latest.get('text', '').strip()) and not latest.get('error'))
    return retry_failed and not delivered


def validate_pair(base_dir, candidate_dir):
    base, candidate = [json.loads((Path(path) / 'run.json').read_text()) for path in (base_dir, candidate_dir)]
    if base.get('variant') != 'base' or candidate.get('variant') not in {'adapter', 'fused'}:
        raise ValueError('Paired comparison requires base versus adapter/fused')
    keys = ['mode', 'protocol', 'config', 'sampling', 'selection_sha256', 'harness_sha256']
    if candidate['variant'] == 'adapter':
        keys.append('model_files')
    if any(base.get(key) != candidate.get(key) for key in keys):
        raise ValueError('Paired runs differ in mode, sampling, inputs or evaluation code')
    if _protocol_assets(base.get('model_files', {})) != _protocol_assets(candidate.get('model_files', {})):
        raise ValueError('Paired tokenizer/template/generation assets differ')
    protocols = []
    for path in (base_dir, candidate_dir):
        loads = [json.loads(p.read_text()) for p in sorted(Path(path).glob('load.*.json'))]
        successful = [load['resolved_protocol'] for load in loads if load.get('state') == 'complete']
        if not successful or any(protocol != successful[0] for protocol in successful):
            raise ValueError('Paired run lacks stable successfully loaded token/stop identity')
        protocols.append(successful[0])
    if protocols[0] != protocols[1]:
        raise ValueError('Paired resolved thought/stop token identities differ')
    return base, candidate


def _protocol_assets(files):
    return {name: value for name, value in files.items() if
            name.startswith(('tokenizer', 'vocab', 'merges', 'chat_template', 'sentencepiece', 'spiece'))
            or name in {'special_tokens_map.json', 'added_tokens.json', 'generation_config.json',
                        'processor_config.json', 'preprocessor_config.json', 'tekken.json', 'tiktoken.model'}}


def _model_hashes(path):
    root = Path(path)
    files = sorted(p for p in root.iterdir() if p.is_file())
    if not files or not any(p.suffix == '.safetensors' for p in files):
        raise ValueError('No model/adapter weights found')
    return {p.name: {'size': p.stat().st_size, 'sha256': _hash(p)} for p in files}


def _memory_snapshot(mx):
    return {'active_bytes': mx.get_active_memory(), 'peak_bytes': mx.get_peak_memory()}


def _check_memory(snapshot, config, phase):
    if max(snapshot.values()) > config.memory_limit_gib * 1024**3:
        raise MemoryError(f'Observed MLX allocation exceeded evaluation budget after {phase}')


def _write_load(output, value):
    index = 1
    while True:
        path = Path(output) / f'load.{index:03d}.json'
        try:
            _write_new(path, value)
            return path
        except FileExistsError:
            index += 1


def run_generation(data_dir, selection_path, model_path, adapter_path, output, variant, mode, config, retry_failed=False):
    """Run one variant/mode. Root coordinates GPU ownership before this call."""
    import fcntl
    import gc
    from .stem_training import SSD_ROOT, ResourceMonitor, configure_ssd_caches
    config.validate()
    sampling = config.sampling(mode)
    for path in (data_dir, selection_path, model_path, output, *([adapter_path] if adapter_path else [])):
        if not Path(path).resolve().is_relative_to(SSD_ROOT.resolve()):
            raise ValueError('Generation inputs and outputs must stay on the external SSD')
    if variant not in {'base', 'adapter', 'fused'} or bool(adapter_path) != (variant == 'adapter'):
        raise ValueError('Only adapter variant accepts and requires an adapter path')
    rows, selection = load_selection(data_dir, selection_path)
    root = Path(output)
    root.mkdir(parents=True, exist_ok=True)
    with (root / '.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        receipt = {'version': 2, 'variant': variant, 'mode': mode, 'protocol': config.protocol, 'config': asdict(config),
                   'sampling': sampling, 'selection_sha256': _hash(selection_path),
                   'selection': selection, 'model_path': str(Path(model_path).resolve()),
                   'adapter_path': str(Path(adapter_path).resolve()) if adapter_path else None,
                   'model_files': _model_hashes(model_path),
                   'adapter_files': _model_hashes(adapter_path) if adapter_path else {},
                   'harness_sha256': _hash(__file__),
                   'format_context': _format_context(config.protocol),
                   'source_context': 'Only dataset user message; expected answer excluded from prompt',
                   'runtime': 'MLX-LM Python; native Ollama is a separate compatibility comparison'}
        run_path = root / 'run.json'
        if run_path.exists():
            if json.loads(run_path.read_text()) != receipt:
                raise ValueError('Existing evaluation run identity differs; use a new output directory')
        else:
            _write_new(run_path, receipt)
        configure_ssd_caches()
        resources = ResourceMonitor()
        import mlx.core as mx
        from mlx_lm import load, stream_generate
        from mlx_lm.sample_utils import make_sampler, make_logits_processors
        mx.set_memory_limit(int((config.memory_limit_gib - 1) * 1024**3))
        model = None
        mx.reset_peak_memory()
        load_started = time.monotonic()
        load_result = {'state': 'error', 'memory_limit_semantics':
                       'Allocation guideline plus observed active/peak checks; cannot interrupt an in-flight kernel'}
        try:
            try:
                model, tokenizer = load(str(model_path), adapter_path=str(adapter_path) if adapter_path else None,
                                        tokenizer_config={'trust_remote_code': False, 'local_files_only': True}, lazy=False)
                model.eval()
                mx.eval(model.parameters())
                load_result.update(_memory_snapshot(mx))
                _check_memory(_memory_snapshot(mx), config, 'model/adapter loading')
                resources.check()
                open_token, close_token = [tokenizer.convert_tokens_to_ids(t) for t in ('<think>', '</think>')]
                if open_token == close_token or any(not isinstance(t, int) for t in (open_token, close_token)):
                    raise ValueError('Native thought boundaries are unavailable')
                stop_tokens = set(getattr(tokenizer, 'eos_token_ids', []) or [])
                if isinstance(tokenizer.eos_token_id, int):
                    stop_tokens.add(tokenizer.eos_token_id)
                load_result.update(state='complete', resolved_protocol={
                    'open_think': open_token, 'close_think': close_token, 'stop_tokens': sorted(stop_tokens)})
            except (Exception, KeyboardInterrupt) as exc:
                load_result.update(_memory_snapshot(mx))
                load_result.update(error=type(exc).__name__ + ': ' + str(exc), seconds=time.monotonic() - load_started)
                _write_load(root, load_result)
                raise
            else:
                load_result.update(seconds=time.monotonic() - load_started)
                _write_load(root, load_result)
            for row in rows:
                prior = read_attempts(root)
                if not needs_trial(row['id'], prior, retry_failed):
                    continue
                resources.check()
                _check_memory(_memory_snapshot(mx), config, 'previous request before peak reset')
                gc.collect()
                mx.clear_cache()
                mx.reset_peak_memory()
                mx.random.seed(config.seed)
                messages = generation_messages(row, config.protocol)
                question = messages[-1]
                prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True,
                                                        enable_thinking=mode == 'deep')
                base = {'variant': variant, 'mode': mode, 'protocol': config.protocol, 'group': row['group'], 'subject': row['subject'],
                        'task': row['task'], 'question': question['content'],
                        'messages_sha256': hashlib.sha256(_json(messages).encode()).hexdigest(),
                        'prompt_sha256': hashlib.sha256(prompt.encode()).hexdigest()}
                start = start_attempt(root, row['id'], base)
                attempt = json.loads(start.read_text())['attempt']
                visible = VisibleTokens(mode == 'deep', open_token, close_token, stop_tokens)
                started, first, last_resource_check, response = time.monotonic(), None, 0, None
                result = dict(base, state='error', text='', finish_reason=None)
                try:
                    with closing(stream_generate(model, tokenizer, prompt=prompt, max_tokens=config.max_tokens,
                            sampler=make_sampler(temp=sampling['temperature'], top_p=sampling['top_p'], top_k=sampling['top_k']),
                            logits_processors=make_logits_processors(presence_penalty=sampling['presence_penalty'],
                                                                    presence_context_size=sampling['presence_context_size']))) as stream:
                        for response in stream:
                            elapsed = time.monotonic() - started
                            if elapsed > config.deadline_seconds:
                                raise TimeoutError('Evaluation request deadline reached')
                            _check_memory(_memory_snapshot(mx), config, 'response token')
                            if elapsed - last_resource_check >= 2:
                                resources.check()
                                last_resource_check = elapsed
                            count = len(visible.tokens)
                            visible.feed(int(response.token))
                            if first is None and len(visible.tokens) > count:
                                first = elapsed
                    _check_memory(_memory_snapshot(mx), config, 'request completion')
                    result.update(state='complete', finish_reason=response.finish_reason if response else None)
                except (Exception, KeyboardInterrupt) as exc:
                    result['error'] = type(exc).__name__ + ': ' + str(exc)
                result.update(text=tokenizer.decode(visible.tokens, skip_special_tokens=True),
                              seconds=time.monotonic() - started, first_final_token_seconds=first,
                              reasoning_tokens=visible.reasoning_tokens, final_tokens=len(visible.tokens),
                              peak_bytes=mx.get_peak_memory(), resources=resources.latest)
                path = write_attempt(root, row['id'], result, attempt=attempt)
                print(_json({'id': row['id'], 'state': result['state'], 'seconds': result['seconds'], 'result': str(path)}), flush=True)
                if result.get('error', '').startswith(('MemoryError:', 'TrainingStopped:', 'KeyboardInterrupt:')):
                    break
        finally:
            del model
            gc.collect()
            mx.clear_cache()


def score_run(data_dir, selection_path, output):
    rows, selection = load_selection(data_dir, selection_path)
    root = Path(output)
    receipt = json.loads((root / 'run.json').read_text())
    if receipt['selection_sha256'] != _hash(selection_path):
        raise ValueError('Run selection hash differs')
    by_id = {r['id']: r for r in rows}
    scores = []
    for trial in read_attempts(root):
        if trial.get('id') not in by_id:
            raise ValueError('Trial id not in frozen held-out selection')
        scores.append({'trial_file': trial['artifact_file'], 'id': trial['id'], 'group': trial['group'],
                       'subject': trial['subject'], 'task': trial['task'], 'attempt': trial['attempt'],
                       'trial_sha256': trial['artifact_sha256'], 'state': trial['state'],
                       **{key: trial.get(key) for key in ('seconds', 'first_final_token_seconds',
                           'reasoning_tokens', 'final_tokens', 'finish_reason', 'error', 'prompt_sha256', 'messages_sha256')},
                       **score_trial(by_id[trial['id']], trial)})
    return {'run_sha256': _hash(root / 'run.json'), 'scorer_sha256': _hash(__file__),
            'protocol': receipt.get('protocol', 'legacy_system'),
            'selection': selection, 'scores': scores,
            'caution': 'All attempts retained; do not cherry-pick retries. Format and source fidelity do not establish scientific correctness.'}


def compare_runs(data_dir, selection_path, base_dir, candidate_dir):
    validate_pair(base_dir, candidate_dir)
    reports = [score_run(data_dir, selection_path, path) for path in (base_dir, candidate_dir)]
    latest = []
    for report in reports:
        by_id = {}
        for score in report['scores']:
            if score['id'] not in by_id or score['attempt'] > by_id[score['id']]['attempt']:
                by_id[score['id']] = score
        latest.append(by_id)
    pairs = []
    for identifier in reports[0]['selection']['ids']:
        baseline, candidate = [report.get(identifier) for report in latest]
        if baseline and candidate and baseline['prompt_sha256'] != candidate['prompt_sha256']:
            raise ValueError('Paired visible prompts differ')
        if baseline and candidate and baseline['messages_sha256'] != candidate['messages_sha256']:
            raise ValueError('Paired role/content hashes differ')
        pairs.append({'id': identifier, 'baseline': baseline, 'candidate': candidate})
    return {'baseline': reports[0], 'candidate': reports[1], 'pairs': pairs,
            'policy': 'Latest terminal/interrupted attempt per id; all attempts retained; null means no start or result recorded.',
            'caution': 'Review scientific correctness and OPEN protection independently before model promotion.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for command in ('freeze', 'generate', 'score', 'pair'):
        child = sub.add_parser(command)
        child.add_argument('--data', type=Path, required=True)
        child.add_argument('--selection', type=Path, required=True)
        if command == 'freeze':
            child.add_argument('--per-subject', type=int, default=40)
            child.add_argument('--seed', type=int, default=42)
        elif command != 'pair':
            child.add_argument('--output', type=Path, required=True)
        if command == 'pair':
            child.add_argument('--baseline', type=Path, required=True)
            child.add_argument('--candidate', type=Path, required=True)
        if command == 'generate':
            child.add_argument('--model', type=Path, required=True)
            child.add_argument('--adapter', type=Path)
            child.add_argument('--variant', choices=('base', 'adapter', 'fused'), required=True)
            child.add_argument('--mode', choices=('fast', 'deep'), required=True)
            child.add_argument('--protocol', choices=tuple(PROTOCOL_SYSTEM), default='training')
            child.add_argument('--presence-penalty', type=float, choices=(0.0, 1.5), default=1.5)
            child.add_argument('--max-tokens', type=int, default=4096)
            child.add_argument('--deadline', type=int, default=180)
            child.add_argument('--execute', action='store_true', required=True)
            child.add_argument('--retry-failed', action='store_true')
    args = parser.parse_args()
    if args.command == 'freeze':
        print(_json(freeze_selection(args.data, args.selection, args.per_subject, args.seed)))
    elif args.command == 'generate':
        run_generation(args.data, args.selection, args.model, args.adapter, args.output, args.variant, args.mode,
                       EvaluationConfig(max_tokens=args.max_tokens, deadline_seconds=args.deadline, protocol=args.protocol,
                                        presence_penalty=args.presence_penalty), args.retry_failed)
    elif args.command == 'score':
        print(_json(score_run(args.data, args.selection, args.output)))
    else:
        print(_json(compare_runs(args.data, args.selection, args.baseline, args.candidate)))


if __name__ == '__main__':
    main()
