#!/usr/bin/env python3
"""CPU preparation/check by default; native runtime requires explicit ROOT_GO.

Never logs hidden reasoning or token IDs. No generated code is executed. Product
sources are read/imported only; alias registration exists only inside this process.
"""
from __future__ import annotations
import argparse
import asyncio
from contextlib import aclosing, contextmanager
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import time

REPO = Path('/Users/sora/Miscellaneous/02 Education/~~ AI Workflow/stem-tutor')
SSD = Path('/Volumes/External SSD TB4/LocalAI')
ROOT = SSD / 'stem-tutor-training/native-probe-v1'
SOURCE = SSD / 'stem-tutor-training/format-challenge-v1'
ALIAS = 'ollama:stem-tutor-qwen35:pilot'
NAME = ALIAS.removeprefix('ollama:')
MODEL_MANIFEST = SSD / 'manifests-v2/ollama.com/library/stem-tutor-qwen35/pilot'
ORGANIC = 'What are the formulaes we need to know for 9701 organic chemistry'
COUNTERS = ('total_duration', 'load_duration', 'prompt_eval_duration', 'eval_duration',
            'prompt_eval_count', 'prompt_eval_cached_count', 'eval_count')
DEPENDENCIES = ['ai', 'chat_output', 'local_models', 'presets', 'local_ai', 'tutor_ai',
                'prompts', 'local_chat', 'local_reply', 'local_context', 'local_reuse',
                'local_ocr', 'local_vision', 'output_fields', 'output_format',
                'stem_training', 'stem_training_eval']


def dump(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for piece in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(piece)
    return h.hexdigest()


def production():
    sys.path[:0] = [str(REPO / 'app'), str(REPO / 'plugin/stem-tutor/skills/tutor/scripts')]
    from tutor_app import ai, prompts, chat_output
    from tutor_app.local_chat import chat_system
    return ai, prompts, chat_output, chat_system


def write(path, value):
    Path(path).write_text(dump(value) + '\n')


def requested_options(mode):
    return dict(temperature=.7 if mode == 'fast' else 1.0,
                top_p=.8 if mode == 'fast' else .95, top_k=20, min_p=0,
                presence_penalty=1.5, frequency_penalty=0, repeat_penalty=1,
                repeat_last_n=1024, seed=42, num_predict=4096, num_ctx=8192)


def strict_object(text):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('duplicate JSON key')
            result[key] = value
        return result
    def constant(_):
        raise ValueError('non-finite JSON literal')
    result = json.loads(text, object_pairs_hook=pairs, parse_constant=constant)
    if not isinstance(result, dict):
        raise ValueError('top level must be object')
    return result


def schema_errors(value, schema, path='$'):
    """Validate every keyword used by the frozen production schemas recursively."""
    errors = []
    kind = schema.get('type')
    kinds = {'object': dict, 'array': list, 'string': str, 'boolean': bool,
             'integer': int, 'number': (int, float)}
    if kind in kinds and (not isinstance(value, kinds[kind]) or
                          kind in ('integer', 'number') and isinstance(value, bool)):
        return [path + ': wrong type']
    if 'enum' in schema and value not in schema['enum']:
        errors.append(path + ': enum')
    if isinstance(value, dict):
        props = schema.get('properties', {})
        errors += [path + ': missing ' + key for key in schema.get('required', []) if key not in value]
        if schema.get('additionalProperties') is False and set(value) - set(props):
            errors.append(path + ': additional properties')
        for key in value.keys() & props.keys():
            errors += schema_errors(value[key], props[key], path + '.' + key)
    elif isinstance(value, list):
        if len(value) < schema.get('minItems', 0) or len(value) > schema.get('maxItems', float('inf')):
            errors.append(path + ': array length')
        for i, item in enumerate(value):
            errors += schema_errors(item, schema.get('items', {}), f'{path}[{i}]')
    elif isinstance(value, str):
        if len(value) < schema.get('minLength', 0) or len(value) > schema.get('maxLength', float('inf')):
            errors.append(path + ': string length')
    return errors


def prepare():
    """Only CPU imports and immutable fixture creation; never opens a service."""
    if ROOT.exists():
        raise ValueError('Refusing to overwrite frozen native-probe-v1')
    ai, prompts, output, chat_system = production()
    source = [json.loads(line) for line in (SOURCE / 'test.jsonl').read_text().splitlines()]
    assert len(source) == 18
    cases, gold = [], []
    for row in source:
        user = row['messages'][0]
        assert user['role'] == 'user' and len(row['messages']) == 2
        marking = row['checks']['schema'] == 'marking'
        points = None
        if marking:
            # Criteria must come from the actual supplied question, never an unseen gold answer.
            supplied = json.loads(user['content'].split('\n')[-1])
            points = supplied['criteria']
            assert points == [p['point'] for p in row['expected']['points']]
        speech = 'speech' in row['expected']
        cases.append(dict(id=row['id'], group=row['group'], subject=row['subject'], task=row['task'],
                          path='one_shot' if marking else 'chat', turns=[user['content']],
                          speech=speech, criteria=points,
                          schema=prompts.local_judge_schema(points) if marking else output.document_schema(speech),
                          original_mark_prefix_conflict=bool(marking), image=None))
        gold.append(dict(id=row['id'], expected=row['expected'], checks=row['checks'],
                         provenance=row['provenance']))
    traps = [
        ('chem', 'oxidation_omission', 'State two changes during oxidation.',
         ['Oxidation involves net loss of electrons.', 'Oxidation increases oxidation number.'],
         'Oxidation involves loss of electrons.', [True, False],
         'Electron loss is stated. Oxidation-number increase is absent and receives no inferred credit.'),
        ('chem', 'reduction_negation', 'State two changes during reduction.',
         ['Reduction involves net gain of electrons.', 'Reduction decreases oxidation number.'],
         'Reduction does not involve gaining electrons. Its oxidation number decreases.', [False, True],
         'The first claim is explicitly negated; the second is independently correct.'),
        ('phys', 'kinetic_scaling_contradiction', 'State kinetic energy and its change when speed doubles at constant mass.',
         ['Kinetic energy equals one half of mass multiplied by speed squared.',
          'At constant mass, doubling speed quadruples kinetic energy.'],
         'Kinetic energy is one half of mass times speed squared. Doubling speed doubles kinetic energy.',
         [True, False], 'Substitution gives (2v)^2/v^2=4; explicit doubling claim contradicts the second criterion.'),
        ('phys', 'work_error_and_omission', 'State work done by a constant force along a displacement and its SI unit.',
         ['Work done equals force multiplied by displacement along the force.', 'The SI unit of work is the joule.'],
         'Work done is force divided by displacement.', [False, False],
         'Division contradicts W=Fs; the joule is never stated. Both criteria independently fail.'),
        ('math', 'derivative_negation', 'Differentiate y=3x^2+7, showing variable and constant contributions.',
         ['The derivative of 3x^2 is 6x.', 'The derivative of the constant 7 is zero.'],
         'The derivative of 3x^2 is 6x. The derivative of 7 is not zero; it is 7.', [True, False],
         'Power rule gives 6x. The constant derivative is explicitly contradicted.'),
        ('math', 'integral_contradiction', 'Integrate 2x with respect to x and explain the integration constant.',
         ['An antiderivative of 2x is x^2.', 'The constant of integration is arbitrary.'],
         'The integral of 2x is x^3+C. C is an arbitrary constant.', [False, True],
         'Differentiating x^3 gives 3x^2, not 2x. The arbitrary constant is independently correctly described.'),
    ]
    for subject, name, stem, points, answer, labels, reasoning in traps:
        identifier = 'native-mark-' + name
        expected = {'points': [dict(point=p, met=label, why='Curated independent criterion gold.')
                               for p, label in zip(points, labels)], 'feedback': 'Curated mark trap.'}
        cases.append(dict(id=identifier, group=identifier, subject=subject, task='mark_trap',
                          path='one_shot', turns=[prompts.judge(stem, points, answer)], speech=False,
                          criteria=points, schema=prompts.local_judge_schema(points),
                          original_mark_prefix_conflict=False, image=None))
        gold.append(dict(id=identifier, expected=expected, checks={'schema': 'marking', 'labels': labels},
                         provenance={'review': 'CPU hand-verified before native output', 'derivation': reasoning}))
    extras = [
        ('native-organic-formulae', 'chem', 'organic_coverage', [ORGANIC],
         'Manual review: actual CAIE9701 organic formula coverage, equations, conditions, completeness and correctness; no narrow automatic gold.'),
        ('native-real-topic-change', 'mixed', 'real_two_turn_topic_change',
         ['Explain oxidation in terms of electrons and oxidation number.',
          'Now change topic to physics. Define potential difference and calculate it when 24 J transfers 6 C of charge. Cover both parts. Show the calculation as one numbered step.'],
         'First turn: oxidation loses electrons/increases oxidation number. Second: energy transferred per unit charge; V=W/Q=4 V. Review new-topic focus and both parts.'),
        ('native-open-hint', 'math', 'open_hint',
         ['CONTEXT\nOPEN question 1, on screen now (do not reveal its answer): Solve x^2-5x+6=0.\n\nSTUDENT ASKS: Give me one first-step hint only; do not give the factors, roots or complete solution.'],
         'Manual review: one useful first-step nudge; no factor pair, factorised expression, roots, or full solution.'),
    ]
    for identifier, subject, task, turns, review in extras:
        cases.append(dict(id=identifier, group=identifier, subject=subject, task=task, path='chat',
                          turns=turns, speech=False, criteria=None, schema=output.document_schema(False),
                          original_mark_prefix_conflict=False, image=None))
        gold.append(dict(id=identifier, expected={}, checks={'schema': 'document',
                         'open_answer_protected': task == 'open_hint'}, provenance={'review_rubric': review}))
    assert len(cases) == 27 and sum(len(c['turns']) for c in cases) == 28
    ROOT.mkdir()
    for name in ('test.jsonl', 'manifest.json', 'selection.json'):
        shutil.copyfile(SOURCE / name, ROOT / ('original-' + name))
    (ROOT / 'inputs.jsonl').write_text(''.join(dump(case) + '\n' for case in cases))
    (ROOT / 'gold.jsonl').write_text(''.join(dump(row) + '\n' for row in gold))
    write(ROOT / 'systems.json', dict(system=ai.SYSTEM,
          document=chat_system(ai.SYSTEM, document=True, speech=False),
          document_speech=chat_system(ai.SYSTEM, document=True, speech=True)))
    shutil.copyfile(__file__, ROOT / 'native_probe_v1.py')
    files = {p.name: sha(p) for p in ROOT.iterdir() if p.is_file()}
    sources = {str(REPO / 'app/tutor_app' / (name + '.py')):
               sha(REPO / 'app/tutor_app' / (name + '.py')) for name in DEPENDENCIES}
    write(ROOT / 'manifest.json', dict(version=2, probe_revision='v2-preflight-fixed', state='frozen_before_native_output', files=files,
          production_sources=sources, case_ids=[c['id'] for c in cases], jobs_per_mode=27, turns_per_mode=28,
          source_original_sha256=sha(SOURCE / 'test.jsonl'),
          source_files={name: sha(SOURCE / name) for name in ('test.jsonl', 'manifest.json', 'selection.json')},
          alias=ALIAS, image_inputs=0,
          mode_options={mode: requested_options(mode) for mode in ('fast', 'deep')},
          options_status='requested; effective per-field values not echoed by native API and not assumed',
          native_source_commit='675150d6ad2747df1e218ef59de9194bc4a7e538',
          native_source_options='mlxrunner/server.go:140-153; mlxrunner/sample/sample.go; see repo native sampler research',
          max_tokens_per_request=4096, deadline_seconds_per_turn=300,
          memory_policy='normal initial pressure; sustained warning10s/critical stop; swap delta512MiB; SSD20GiB; OS available3GiB; native reported size_vram14GiB',
          limitations=['Format challenge overlaps underlying training facts; not independent unseen science.',
                       'Original 3 marking prompts retain document-prefix versus marking-envelope conflict.',
                       'No image input; macos:vision configured but OCR remains unvalidated.',
                       'Native scalar settings and timing do not establish Python sampling or kernel parity.',
                       'All public outputs, including failures, are retained; no winner claim automatic.']))
    return check()


def check():
    manifest = json.loads((ROOT / 'manifest.json').read_text())
    assert manifest.get('version') == 2 and manifest.get('probe_revision') == 'v2-preflight-fixed', 'old probe manifest'
    for name, digest in manifest['files'].items():
        assert (ROOT / name).resolve().parent == ROOT.resolve() and sha(ROOT / name) == digest, name
    assert sha(__file__) == manifest['files']['native_probe_v1.py'], 'probe source drift'
    for name, digest in manifest['production_sources'].items():
        assert sha(name) == digest, 'production source drift: ' + name
    assert sha(SOURCE / 'test.jsonl') == manifest['source_original_sha256'], 'original corpus changed'
    for name, digest in manifest['source_files'].items():
        assert sha(SOURCE / name) == digest == sha(ROOT / ('original-' + name)), 'original receipt changed'
    assert manifest['mode_options'] == {mode: requested_options(mode) for mode in ('fast', 'deep')}
    cases = [json.loads(line) for line in (ROOT / 'inputs.jsonl').read_text().splitlines()]
    gold = {r['id']: r for r in map(json.loads, (ROOT / 'gold.jsonl').read_text().splitlines())}
    assert len(cases) == 27 and sum(len(c['turns']) for c in cases) == 28
    assert [c['id'] for c in cases] == manifest['case_ids'] and len(gold) == 27
    original = [json.loads(line) for line in (ROOT / 'original-test.jsonl').read_text().splitlines()]
    by_id = {c['id']: c for c in cases}
    assert all(by_id[r['id']]['turns'] == [r['messages'][0]['content']] for r in original)
    assert sum(c['original_mark_prefix_conflict'] for c in cases) == 3
    assert all('expected' not in c and 'messages' not in c and c['image'] is None for c in cases)
    assert by_id['native-organic-formulae']['turns'] == [ORGANIC]
    ai, prompts, output, chat_system = production()
    for case in cases:
        expected_schema = (prompts.local_judge_schema(case['criteria']) if case['path'] == 'one_shot'
                           else output.document_schema(case['speech']))
        assert case['schema'] == expected_schema, 'production schema mismatch'
        expected = gold[case['id']]['expected']
        if expected:
            assert not schema_errors(expected, case['schema']), case['id']
            if case['path'] == 'chat':
                decoder = output.DocumentDecoder(case['speech'])
                decoder.feed(dump(expected)); decoder.finish()
    assert json.loads((ROOT / 'systems.json').read_text()) == dict(system=ai.SYSTEM,
        document=chat_system(ai.SYSTEM, document=True, speech=False),
        document_speech=chat_system(ai.SYSTEM, document=True, speech=True))
    return manifest, cases


def score_case(case, raw, done_reason, gold):
    from tutor_app.chat_output import DocumentDecoder
    result = dict(delivered=done_reason == 'stop' and bool(raw.strip()), raw_schema_valid=False,
                  decoder_finish=None, exact_criteria_order=None, marking_labels_equal=None,
                  marking_envelope_valid=False, marking_vector_available=False,
                  marking_decision_vector=None, marking_vector_correct=None,
                  exact_literal_code=None, speech_separate=None, science='manual_review_required',
                  open_protection='manual_review_required' if 'open' in case['task'] else 'not_applicable')
    try:
        value = strict_object(raw)
        errors = schema_errors(value, case['schema'])
        result.update(raw_schema_valid=not errors, schema_errors=errors)
        if case['path'] == 'one_shot':
            from tutor_app.stem_training_eval import _marking
            rows = value.get('points', [])
            result['exact_criteria_order'] = (isinstance(rows, list)
                and all(isinstance(row, dict) for row in rows)
                and [row.get('point') for row in rows] == case['criteria'])
            try:
                # The requested marking envelope is stricter than the transport schema:
                # exact keys, point/why strings and type(met) is bool are mandatory.
                _marking(value)
            except ValueError as exc:
                result['marking_envelope_error'] = str(exc)
            else:
                result['marking_envelope_valid'] = True
            if not errors and result['marking_envelope_valid'] and result['exact_criteria_order']:
                labels = [row['met'] for row in rows]
                correct = labels == [row['met'] for row in gold['expected']['points']]
                result.update(marking_vector_available=True, marking_decision_vector=labels,
                              marking_vector_correct=correct, marking_labels_equal=correct)
        else:
            decoder = DocumentDecoder(case['speech']); decoder.feed(raw); decoder.finish()
            result['decoder_finish'] = True
            result['speech_separate'] = ('speech' in value) == case['speech']
            result['block_kinds'] = [block['kind'] for block in value['blocks']]
            code = [b['text'] for b in gold['expected'].get('blocks', []) if b['kind'] == 'code']
            if code:
                result['exact_literal_code'] = [b['text'] for b in value['blocks'] if b['kind'] == 'code'] == code
    except (ValueError, TypeError, KeyError, AttributeError) as exc:
        result['validation_error'] = str(exc)
        if case['path'] == 'chat':
            result['decoder_finish'] = False
    return result


@contextmanager
def temporary_catalogue(catalogue):
    """Restore all five alias entries even if the first mutation or setup fails."""
    mappings = (catalogue.LOCAL_MODELS, catalogue.KEEP_ALIVE,
                catalogue.CONTEXT_LENGTH, catalogue.MAX_CONTEXT_LENGTH)
    saved = [(mapping, ALIAS in mapping, mapping.get(ALIAS)) for mapping in mappings]
    text_member = ALIAS in catalogue.TEXT_MODELS
    try:
        catalogue.LOCAL_MODELS[ALIAS] = 'STEM Tutor Qwen3.5 pilot (probe only)'
        catalogue.TEXT_MODELS.add(ALIAS)
        catalogue.KEEP_ALIVE[ALIAS] = '10m'
        catalogue.CONTEXT_LENGTH[ALIAS] = 8192
        catalogue.MAX_CONTEXT_LENGTH[ALIAS] = 8192  # Disable generic generation retries.
        yield
    finally:
        for mapping, present, value in saved:
            if present:
                mapping[ALIAS] = value
            else:
                mapping.pop(ALIAS, None)
        if text_member:
            catalogue.TEXT_MODELS.add(ALIAS)
        else:
            catalogue.TEXT_MODELS.discard(ALIAS)


async def execute(args, manifest, cases):
    # This function is never reached by prepare/check/compile. No MLX Python import.
    import fcntl
    import subprocess
    from tutor_app import local_models
    from tutor_app.ai import SYSTEM
    from tutor_app.local_ai import LocalAI, LocalError, _LIMIT
    from tutor_app.tutor_ai import TutorAI
    from tutor_app.stem_training import ResourceMonitor, TrainingStopped
    output = Path(args.output).resolve()
    if not output.is_relative_to(SSD.resolve()) or output.exists() or output.is_relative_to(ROOT.resolve()):
        raise ValueError('Output must be a new SSD directory outside frozen inputs')
    if not MODEL_MANIFEST.is_file():
        raise ValueError('Native alias is not registered; probe cannot import it')
    native_manifest = json.loads(MODEL_MANIFEST.read_text())
    if native_manifest.get('runner') != 'mlx':
        raise ValueError('Actual alias manifest does not declare runner mlx')
    lock = (SSD / 'stem-tutor-training/.native-probe-runtime.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    # Root owns scheduling; this advisory lock only excludes simultaneous harness runs.
    resources = ResourceMonitor()
    started = time.monotonic()
    output.mkdir()
    receipt = dict(state='started', mode=args.mode, alias=ALIAS, started_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                   input_manifest_sha256=sha(ROOT / 'manifest.json'), native_manifest_sha256=sha(MODEL_MANIFEST),
                   requested_options=requested_options(args.mode), effective_options=None,
                   source_options_status=manifest['options_status'], initial_resources=resources.initial,
                   root_go=True, gpu_ownership='Root scheduling + harness advisory lock; one existing native server',
                   jobs=27, turns=28, max_tokens=4096, per_turn_timeout_seconds=300)
    write(output / 'receipt.json', receipt)
    events_file = (output / 'public-events.jsonl').open('x')
    observations = []
    context = {'id': 'startup', 'turn': None}
    def record(value):
        events_file.write(dump(dict(case_id=context['id'], turn=context['turn'],
                                   elapsed_seconds=time.monotonic() - started, **value)) + '\n')
        events_file.flush()
    class ProbeLocal(LocalAI):
        def __init__(self):
            super().__init__(SYSTEM, document=True)
            self.public_tail = ''
            self.final_content, self.finish_reason = [], None
            self.thinking_observed = False
            self.actual_counters = {}
        async def _connect(self, deadline):
            # Never launch a second server or modify server environment.
            return await asyncio.wait_for(asyncio.open_connection('127.0.0.1', 11434, limit=_LIMIT),
                                          max(.001, deadline - time.monotonic()))
        def _decode(self, line):
            event = json.loads(line)
            if not isinstance(event, dict):
                raise LocalError('Non-object native event')
            message = event.get('message')
            thought = message.pop('thinking', None) if isinstance(message, dict) else None
            observed = bool(thought)
            del thought  # Hidden text is discarded before validation, recording or any yield.
            clean = {k: event[k] for k in (*COUNTERS, 'done', 'done_reason', 'error', 'version') if k in event}
            if isinstance(message, dict):
                content = message.get('content', '')
                if not isinstance(content, str):
                    raise LocalError('Non-string final content')
                if '<think' in (self.public_tail + content).lower() or '</think' in (self.public_tail + content).lower():
                    content = ''
                    clean['error'] = 'Reasoning delimiter in final-content channel; content discarded'
                self.public_tail = (self.public_tail + content)[-8:]
                clean['message'] = {'role': 'assistant', 'content': content}
                if observed:
                    clean['message']['thinking'] = True  # Boolean phase marker only; production timing remains real.
            if 'models' in event:
                clean['models'] = [{k: m[k] for k in ('name', 'model', 'size', 'size_vram') if k in m}
                                   for m in event['models'] if isinstance(m, dict)]
            del event, message
            return LocalAI._decode(dump(clean).encode())
        async def _http_events(self, payload, timeout, path='/api/chat', **kwargs):
            generating = path == '/api/chat' and bool(payload.get('messages'))
            if generating:
                self.public_tail = ''
                self.final_content, self.finish_reason = [], None
                self.thinking_observed = False
                self.actual_counters = {}
                assert payload.get('think') is (args.mode == 'deep')
                assert payload['format'] == context['schema']
                record({'type': 'request', 'path': path, 'payload': payload})
            else:
                record({'type': 'control_request', 'path': path,
                        'purpose': context['id'], 'requested_options': payload.get('options')})
            async with aclosing(super()._http_events(payload, timeout, path, **kwargs)) as stream:
                async for event in stream:
                    msg = event.get('message') or {}
                    self.thinking_observed |= bool(msg.get('thinking')) if generating else False
                    public = {k: event[k] for k in (*COUNTERS, 'done', 'done_reason', 'error', 'version', 'models') if k in event}
                    if msg.get('content'):
                        public['content'] = msg['content']
                        if generating:
                            self.final_content.append(msg['content'])
                    if generating and event.get('done'):
                        self.finish_reason = event.get('done_reason')
                        self.actual_counters = {key: event[key] for key in COUNTERS if key in event}
                    record({'type': 'public_event', 'event': public})
                    yield event
        def _with_context(self, payload, model):
            payload = super()._with_context(payload, model)
            if model == ALIAS:
                payload['options'] = {**payload.get('options', {}), **requested_options(args.mode)}
            return payload
    # The outer finally covers context entry, the first mutation and all setup.
    try:
        with temporary_catalogue(local_models):
            tutor = TutorAI(cwd=output, model=ALIAS, document=True, usage_file=None)
            tutor.local_web = False
            tutor.local_vision_model = 'macos:vision'
            tutor._local = local = ProbeLocal()
            async def residency():
                found = None
                async with aclosing(local._http_events({}, 10, '/api/ps', method='GET', start_service=False)) as stream:
                    async for event in stream:
                        if 'models' in event:
                            found = event['models']
                if found is None:
                    raise LocalError('Native server did not report residency')
                names = {m.get('model') or m.get('name') for m in found}
                if names - {NAME}:
                    raise LocalError('Another native model is loaded; root must resolve GPU ownership')
                if any(m.get('size_vram', 0) > 14 * 1024**3 for m in found):
                    raise LocalError('Native reported size_vram exceeds 14GiB')
                return found
            class ProbeResourceStop(LocalError):
                pass
            async def headroom():
                await asyncio.to_thread(resources.check)
                vm = await asyncio.to_thread(subprocess.check_output, ['vm_stat'], text=True, timeout=3)
                import re
                page = int(re.search(r'page size of (\d+) bytes', vm)[1])
                available = sum(int(v) for v in re.findall(r'^Pages (?:free|inactive|speculative):\s+(\d+)\.', vm, re.M)) * page
                if available < 3 * 1024**3:
                    raise ProbeResourceStop('Available OS memory below 3GiB headroom')
                if time.monotonic() - started > 7200:
                    raise TimeoutError('Native mode wall-time bound 7200s reached')
            async def guard():
                while True:
                    await headroom()
                    await asyncio.sleep(2)
            async def bounded(coro, seconds=300):
                try:
                    # Check OS headroom before even scheduling the GPU-capable operation.
                    await headroom()
                except BaseException:
                    coro.close()
                    raise
                work, monitor = asyncio.create_task(coro), asyncio.create_task(guard())
                try:
                    done, _ = await asyncio.wait({work, monitor}, timeout=seconds, return_when=asyncio.FIRST_COMPLETED)
                    if not done:
                        raise TimeoutError('Native operation exceeded request deadline')
                    if monitor in done:
                        monitor.result()
                    return await work
                finally:
                    work.cancel(); monitor.cancel()
                    await asyncio.gather(work, monitor, return_exceptions=True)
            async def unload():
                async with aclosing(local._http_events({'model': NAME, 'messages': [], 'stream': False, 'keep_alive': 0},
                                                       30, start_service=False)) as stream:
                    confirmed = False
                    async for event in stream:
                        confirmed |= event.get('done') is True and event.get('done_reason') == 'unload'
                if not confirmed:
                    raise LocalError('Native unload was not acknowledged')
            candidate_owned = False
            try:
                # No service version is inferred from a successful generation response.
                async with aclosing(local._http_events({}, 10, '/api/version', method='GET', start_service=False)) as stream:
                    versions = [e.get('version') async for e in stream]
                if versions != ['0.40.11']:
                    raise LocalError('Native server must report version 0.40.11')
                receipt['server_version'] = versions[0]
                loaded = await residency()
                if loaded:
                    await bounded(unload(), 30)
                candidate_owned = True  # The scheduler was verified empty before this run's first load.
                for label in ('cold_preload', 'warm_preload'):
                    context.update(id=label, turn=None)
                    before = time.monotonic()
                    result = await bounded(local.warm(ALIAS, timeout=300))
                    record({'type': 'preload_result', 'ok': result.ok, 'error': result.message,
                            'wall_seconds': time.monotonic() - before})
                    if not result.ok:
                        raise LocalError('Preload failed: ' + result.message)
                    await residency()
                for case in cases:
                    await tutor.reset(warm=False)
                    tutor.speech = case['speech']
                    for turn, prompt in enumerate(case['turns'], 1):
                        context.update(id=case['id'], turn=turn, schema=case['schema'])
                        local.final_content, local.finish_reason, local.actual_counters = [], None, {}
                        local.thinking_observed = False
                        before, first = time.monotonic(), None
                        rendered = []
                        async def request():
                            nonlocal first
                            if case['path'] == 'one_shot':
                                _, result = await tutor.one_shot(prompt, schema=case['schema'], model=ALIAS,
                                                               timeout=300, think=args.mode == 'deep')
                                return result
                            async with aclosing(tutor.stream(prompt, model=ALIAS, think=args.mode == 'deep')) as stream:
                                async for block in stream:
                                    if first is None:
                                        first = time.monotonic() - before
                                    rendered.append(block)
                            return tutor.last
                        fatal = None
                        try:
                            result = await bounded(request())
                            error = result.message if not result.ok else None
                            performance = result.performance
                            ok = result.ok
                        except Exception as exc:
                            error, performance, ok = f'{type(exc).__name__}: {exc}', {}, False
                            if isinstance(exc, (TimeoutError, TrainingStopped, ProbeResourceStop)):
                                fatal = exc
                        observation = dict(id=case['id'], turn=turn, app_ok=ok, error=error,
                            total_wall_seconds=time.monotonic() - before, first_rendered_block_seconds=first,
                            first_rendered_block_status='not_applicable_marking' if case['path'] == 'one_shot' else 'measured',
                            performance=performance, actual_api_counters=local.actual_counters,
                            missing_api_counters=[key for key in COUNTERS if key not in local.actual_counters],
                            finish_reason=local.finish_reason,
                            thinking_observed=local.thinking_observed, public_final=''.join(local.final_content),
                            rendered='\n\n'.join(rendered), requested_options=requested_options(args.mode))
                        observations.append(observation)
                        record({'type': 'turn_result', **observation})
                        if fatal is not None:
                            raise fatal  # Do not start another turn after guard/deadline cancellation.
                        resources.check()
                        await residency()
                        if not ok and case['task'] == 'real_two_turn_topic_change':
                            record({'type': 'continuation_status', 'status': 'next turn retained with actual failed first-turn history'})
                receipt.update(state='completed_requires_manual_review', completed_turns=len(observations),
                               native_kernel_timing_comparison='not direct Python parity',
                               final_resources=resources.latest)
            except BaseException as exc:
                receipt.update(state='failed_or_stopped', error=f'{type(exc).__name__}: {exc}',
                               completed_turns=len(observations), final_resources=resources.latest)
                raise
            finally:
                context.update(id='cleanup', turn=None)
                try:
                    # Only unload the candidate acknowledged by this run; never evict another app's model.
                    loaded = await residency()
                    if loaded and candidate_owned:
                        await unload()
                    receipt['cleanup'] = 'candidate released or no candidate loaded'
                except Exception as exc:
                    receipt['cleanup'] = 'failed: ' + type(exc).__name__ + ': ' + str(exc)
                await tutor.close()
                try:
                    # Gold is read only after generation has finished. It never enters an API payload.
                    gold = {r['id']: r for r in map(json.loads, (ROOT / 'gold.jsonl').read_text().splitlines())}
                    scored = []
                    by_id = {case['id']: case for case in cases}
                    for item in observations:
                        scores = score_case(by_id[item['id']], item['public_final'], item['finish_reason'], gold[item['id']])
                        scores['native_control_valid'] = (not item['thinking_observed'] if args.mode == 'fast'
                                                           else item['thinking_observed'])
                        scores['delivery_gate'] = bool(item['app_ok'] and not item['error'] and scores['delivered'])
                        scored.append(dict(id=item['id'], turn=item['turn'], scores=scores))
                    write(output / 'scores.json', scored)
                except Exception as exc:
                    receipt['scoring_error'] = type(exc).__name__ + ': ' + str(exc)
                receipt['elapsed_seconds'] = time.monotonic() - started
                write(output / 'receipt.json', receipt)
                events_file.close()
                lock.close()
    finally:
        events_file.close()
        lock.close()


def main():
    if sys.flags.optimize:
        raise RuntimeError('Run without Python optimisation so frozen assertions remain active')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare', action='store_true')
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--root-go', choices=['ROOT_GO'])
    parser.add_argument('--mode', choices=['fast', 'deep'])
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.prepare and args.execute:
        parser.error('prepare and execute are separate operations')
    manifest, cases = prepare() if args.prepare else check()
    if args.execute:
        if args.root_go != 'ROOT_GO' or args.mode is None or args.output is None:
            parser.error('execution requires root GO, one mode and new SSD output')
        asyncio.run(execute(args, manifest, cases))
    else:
        print(dump({'state': 'CPU_manifest_checks_passed_HOLD_ROOT_GO', 'jobs_per_mode': len(cases),
                    'turns_per_mode': sum(len(c['turns']) for c in cases),
                    'manifest_sha256': sha(ROOT / 'manifest.json')}))


if __name__ == '__main__':
    main()
