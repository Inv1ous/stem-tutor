#!/usr/bin/env python3
"""CPU preparation by default. Eight DEV compatibility requests require explicit ROOT_GO."""
from __future__ import annotations
import argparse
import asyncio
from contextlib import aclosing
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parent
SSD = Path('/Volumes/External SSD TB4/LocalAI')
REPO = Path('/Users/sora/Miscellaneous/02 Education/~~ AI Workflow/stem-tutor')
MODEL = SSD / 'models/stem-tutor-qwen35-hybrid-v1'
PYTHON = SSD / 'tutor-runtime/stem-training/.venv/bin/python'
PRIOR = SSD / 'stem-tutor-training/native-development-diagnostic-v1'
DEV = SSD / 'stem-tutor-training/evaluation-development-protocol-v1'
MARK_ID = 'c58ad26c013848559f4ab9cf'
USER = ('STEM Tutor. Reply in document JSON. A constant force of 6.0 N acts along a displacement '
        'of 0.50 m. Calculate the work done and give a separate spoken version of the answer.')
sys.path[:0] = [str(REPO / 'app'), str(REPO / 'plugin/stem-tutor/skills/tutor/scripts')]
spec = importlib.util.spec_from_file_location('native_dev_helpers', ROOT / 'native_probe_helpers.py')
helpers = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helpers)
ALIAS, NAME, COUNTERS = helpers.ALIAS, helpers.NAME, helpers.COUNTERS
sha, dump = helpers.sha, helpers.dump


class Fatal(RuntimeError):
    pass


def write(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(dump(value) + '\n')
    temporary.replace(path)


def options(deep=False):
    return {**helpers.requested_options('deep' if deep else 'fast'), 'num_predict': 4096 if deep else 512}


def compat_payload(payload, *, document_chat):
    """Diagnostic-only transform; exact custom alias and document generation only."""
    result = copy.deepcopy(payload)
    if (document_chat and payload.get('model') == NAME and payload.get('messages')):
        result.pop('format', None)
    return result


def sanitize(event, tail):
    """V3 probe boundary, factored here so CPU tests exercise public-only recording."""
    if not isinstance(event, dict):
        raise ValueError('Non-object native event')
    message = event.get('message')
    thought = message.pop('thinking', None) if isinstance(message, dict) else None
    observed = bool(thought)
    del thought
    clean = {k: event[k] for k in (*COUNTERS, 'done', 'done_reason', 'error', 'version') if k in event}
    if isinstance(message, dict):
        content = message.get('content', '')
        if not isinstance(content, str):
            raise ValueError('Non-string final content')
        if '<think' in (tail + content).lower() or '</think' in (tail + content).lower():
            content = ''
            clean['error'] = 'Reasoning delimiter in final-content channel; content discarded'
        tail = (tail + content)[-8:]
        clean['message'] = {'role': 'assistant', 'content': content}
        if observed:
            clean['message']['thinking'] = True
    if 'models' in event:
        clean['models'] = [{k: m[k] for k in ('name', 'model', 'size', 'size_vram') if k in m}
                           for m in event['models'] if isinstance(m, dict)]
    return clean, tail


def assert_pair(outgoing, app_payload):
    expected = copy.deepcopy(app_payload)
    expected.pop('format')
    assert outgoing == expected, 'Document compatibility changes more than native format'


def render_evidence(messages, deep):
    # Reuse existing CPU template dependencies; never install or import MLX here.
    if importlib.util.find_spec('jinja2') is None:
        sys.path.append(str(PYTHON.parent.parent / 'lib/python3.13/site-packages'))
    from jinja2 import Environment
    environment = Environment()
    environment.globals['raise_exception'] = lambda message: (_ for _ in ()).throw(ValueError(message))
    jinja = environment.from_string((MODEL / 'chat_template.jinja').read_text()).render(
        messages=messages, tools=None, add_generation_prompt=True, enable_thinking=deep,
        add_vision_id=False)
    # Source-derived first-turn text-only Qwen35Renderer reconstruction. NOT a runtime capture.
    native = ''.join('<|im_start|>' + m['role'] + '\n' + m['content'].strip() + '<|im_end|>\n'
                     for m in messages)
    native += '<|im_start|>assistant\n' + ('<think>\n' if deep else '<think>\n\n</think>\n\n')
    return dict(jinja=jinja, source_derived_native=native, equal=jinja == native,
                actual_native_runtime_capture=False,
                limitation='CPU source reconstruction only; native rendered bytes/token IDs were not captured',
                native_source='675150d6ad2747df1e218ef59de9194bc4a7e538/model/renderers/qwen35.go:187-335')


async def capture_app(prompt, *, deep=False, schema=None, speech=False):
    """Run real TutorAI until the HTTP boundary; substitute no network transport."""
    from tutor_app import local_models
    from tutor_app.ai import SYSTEM
    from tutor_app.local_ai import LocalAI
    from tutor_app.tutor_ai import TutorAI
    captured = []
    class Captured(BaseException):
        pass
    class CaptureLocal(LocalAI):
        async def _http_events(self, payload, timeout, path='/api/chat', **kwargs):
            if payload.get('messages'):
                captured.append(copy.deepcopy(payload))
                raise Captured()
            yield {'done': True, 'done_reason': 'load'}
        def _with_context(self, payload, model):
            return {**super()._with_context(payload, model), 'options': options(deep)}
    with helpers.temporary_catalogue(local_models):
        tutor = TutorAI(cwd=ROOT, model=ALIAS, document=True, usage_file=None)
        tutor.local_web = False
        tutor.speech = speech
        tutor._local = CaptureLocal(SYSTEM, document=True)
        try:
            if schema is None:
                async for _ in tutor.stream(prompt, model=ALIAS, think=deep):
                    pass
            else:
                await tutor.one_shot(prompt, schema=schema, model=ALIAS, timeout=45, think=False)
        except Captured:
            pass
        finally:
            await tutor.close()
    assert len(captured) == 1, 'App must produce exactly one generation payload'
    return captured[0]


def runtime_schema(row):
    """Regenerate production marking order; never render a canonicalized fixture schema."""
    from tutor_app import prompts
    if row['path'] != 'one_shot':
        return copy.deepcopy(row['schema'])
    schema = prompts.local_judge_schema(row['criteria'])
    assert schema == row['schema'], 'Factory schema value drift'
    assert json.dumps(schema,ensure_ascii=False) == row['ordered_schema_json'], 'Factory schema order drift'
    return schema


async def prior_mark_regression():
    """Reproduce v1 failure at a socket-free production payload boundary."""
    row = next(r for r in json.loads((PRIOR/'inputs.json').read_text()) if r['id']=='mark')
    actual = await capture_app(row['prompt'],schema=row['schema'],speech=False)
    frozen = row['payload']
    same = copy.deepcopy(actual); same['messages'][1]['content'] = frozen['messages'][1]['content']
    assert same == frozen and actual != frozen
    return dict(v1_roundtrip_payload_equal=False,changed_fields=['messages[1].content'],
                prompt_lengths=[len(frozen['messages'][1]['content']),len(actual['messages'][1]['content'])],
                actual_native_runtime_capture=False,no_socket_or_model_calls=True,
                cause='Canonical schema key ordering changed the embedded json_instruction prompt')


async def build_fixtures():
    from tutor_app import chat_output, prompts
    source = list(map(json.loads,(DEV/'test.jsonl').read_text().splitlines()))
    docs = [r for r in source if r['task']!='marking']
    assert len(docs)==6 and [r['task'] for r in docs].count('literal_json')==3
    cases, gold = [], {}
    for row in docs:
        prompt = row['messages'][0]['content']
        app_payload = await capture_app(prompt,speech=False)
        outgoing = compat_payload(app_payload,document_chat=True)
        assert_pair(outgoing,app_payload)
        cases.append(dict(id=row['id'],mode='fast',seconds=45,max_tokens=512,path='chat',speech=False,
                          criteria=None,schema=chat_output.document_schema(False),prompt=prompt,
                          task=row['task'],subject=row['subject'],app_payload=app_payload,payload=outgoing))
        gold[row['id']] = {'expected':row['expected'],'checks':row['checks']}
    mark = next(r for r in source if r['id']==MARK_ID)
    supplied = json.loads(mark['messages'][0]['content'].rsplit('\n',1)[-1])
    criteria = supplied['criteria']
    prompt = prompts.judge('State the defining properties of linear momentum.',criteria,supplied['response'])
    schema = prompts.local_judge_schema(criteria)
    payload = await capture_app(prompt,schema=schema,speech=False)
    cases.append(dict(id='mark',mode='fast',seconds=45,max_tokens=512,path='one_shot',speech=False,
                      criteria=criteria,schema=schema,ordered_schema_json=json.dumps(schema,ensure_ascii=False),
                      prompt=prompt,task='marking',subject='phys',app_payload=payload,payload=copy.deepcopy(payload),
                      development_source_id=MARK_ID))
    gold['mark'] = {'expected':mark['expected'],'checks':mark['checks']}
    full = await capture_app(USER,deep=True,speech=True)
    outgoing = compat_payload(full,document_chat=True)
    assert_pair(outgoing,full)
    cases.append(dict(id='Deep',mode='deep',seconds=180,max_tokens=4096,path='chat',speech=True,
                      criteria=None,schema=chat_output.document_schema(True),prompt=USER,task='calculation',
                      subject='phys',app_payload=full,payload=outgoing))
    gold['Deep'] = {'expected':{},'numeric_work_joules':3.0,'required_precision':'3.0 J',
                    'manual_review_required':True,'related_family_not_independent_science':True}
    return dict(conditions=cases,gold=gold,
                renders={r['id']:render_evidence(r['app_payload']['messages'],r['mode']=='deep') for r in cases})


def execution_gate(root_go, output):
    output = Path(output).resolve()
    if root_go != 'ROOT_GO':
        raise ValueError('Explicit ROOT_GO required; preparation does not authorize execution')
    if output.exists() or not output.is_relative_to((SSD / 'stem-tutor-training').resolve()):
        raise ValueError('Output must be a new SSD stem-tutor-training sibling')
    if output.is_relative_to(ROOT):
        raise ValueError('Output cannot be inside frozen inputs')
    return output


def score(row, observation, gold):
    value = helpers.score_case(row,
                               observation.get('public_final', ''), observation.get('finish_reason'),
                               gold[row['id']])
    raw = observation.get('public_final', '')
    value['repeated_substring_heuristic'] = any(raw.count(raw[i:i+16]) >= 8 for i in range(0, max(0, len(raw)-16), 16))
    value['arithmetic_and_spoken_meaning'] = 'manual_review_required' if row['id'] != 'mark' else 'not_applicable'
    value['native_control_valid'] = (observation.get('thinking_observed', False) if row['mode'] == 'deep'
                                     else not observation.get('thinking_observed', False))
    value['application_delivery'] = observation.get('app_ok')
    value['source_fidelity'] = 'manual_review_required' if row['task']=='published_flashcard' else 'not_applicable'
    try:
        actual = helpers.strict_object(raw)
        value['exact_expected_document'] = actual == gold[row['id']]['expected'] if row['path']=='chat' and row['id']!='Deep' else None
    except ValueError:
        value['exact_expected_document'] = False if row['path']=='chat' else None
    value['successful_complete_delivery'] = bool(value['delivered'] and value['raw_schema_valid']
                                                 and (value['decoder_finish'] if row['path'] == 'chat' else
                                                      value['marking_vector_available']) and not observation.get('error')
                                                 and observation.get('app_ok') is True and value['native_control_valid'])
    return value


def prepare():
    if (ROOT / 'manifest.json').exists():
        raise ValueError('Frozen manifest already exists')
    fixture = asyncio.run(build_fixtures())
    write(ROOT / 'inputs.json', fixture['conditions'])
    write(ROOT / 'gold.json', fixture['gold'])
    write(ROOT / 'cpu-render-evidence.json', fixture['renders'])
    write(ROOT / 'prior-v1-mark-regression.json',asyncio.run(prior_mark_regression()))
    assert all(value['equal'] for value in fixture['renders'].values()), 'CPU source-derived render mismatch'
    source_paths = [REPO / 'app/tutor_app' / (name + '.py') for name in helpers.DEPENDENCIES]
    source_paths += [DEV / name for name in ('test.jsonl', 'selection.json', 'manifest.json')]
    source_paths += [helpers.MODEL_MANIFEST, PYTHON, SSD / 'tutor-runtime/stem-training/requirements.lock',
                     SSD / 'stem-tutor-training/native-probe-v1/native_probe_v1.py',
                     SSD / 'stem-tutor-training/native-probe-v1/manifest-v3-recorder-fixed.json',
                     PRIOR/'diagnostic.py',PRIOR/'manifest.json',PRIOR/'inputs.json',Path(sys.executable)]
    source_paths += [SSD/'stem-tutor-training/native-development-diagnostic-results-v1'/name for name in
                     ('receipt.json','scores.json','observations.json','public-events.jsonl','python.json','mark-payload-cpu-diff.json')]
    source_paths += [MODEL / name for name in ('tokenizer.json', 'tokenizer_config.json', 'chat_template.jinja',
                                             'vocab.json', 'fusion_receipt.json', 'config.json')]
    # Weight identities are inherited from the independently verified fusion receipt; no new model loading.
    write(ROOT / 'manifest.json', dict(version=2,state='CPU_FROZEN_HOLD_ROOT_REVIEW',
        evaluation_role='DEVELOPMENT ONLY; six unchanged DEV documents, one VALID marking, one related-family Deep; no promotion',
        order=[r['id'] for r in fixture['conditions']],always_attempt_all_conditions=True,
        exception='Fatal resource/server/wall/source-identity error stops remaining conditions',
        wall_seconds=600,native_version='0.40.11',options_status='requested; effective native fields not echoed',
        compatibility_scope='Exact custom alias generating document chat only; full instructions and strict host decoder retained; marking native format retained',
        resource_policy={'observed_gib': 14, 'swap_growth_mib': 512, 'ssd_free_gib': 20,
                         'os_headroom_gib': 3, 'initial_pressure': 'normal', 'sustained_warning_seconds': 10},
        files={p.name: sha(p) for p in ROOT.iterdir() if p.is_file() and p.name != 'manifest.json'},
        sources={str(p): sha(p) for p in source_paths}, native_helper_revision='v3-recorder-fixed',
        no_hidden_thought_or_token_ids=True, no_generated_code_execution=True))


def check():
    manifest = json.loads((ROOT / 'manifest.json').read_text())
    for name, digest in manifest['files'].items():
        assert sha(ROOT / name) == digest, 'Frozen file drift: ' + name
    for name, digest in manifest['sources'].items():
        assert sha(name) == digest, 'Source drift: ' + name
    rows = json.loads((ROOT / 'inputs.json').read_text())
    assert [r['id'] for r in rows] == manifest['order']
    for row in rows:
        if row['path']=='chat':assert_pair(row['payload'],row['app_payload'])
        else:
            assert row['payload']==row['app_payload'] and 'format' in row['payload']
            runtime_schema(row)
    assert all('expected' not in row and 'gold' not in row for row in rows)
    actual = asyncio.run(build_fixtures())
    assert actual['conditions'] == rows, 'Actual CPU-captured app payload drift'
    assert actual['gold'] == json.loads((ROOT / 'gold.json').read_text())
    for row in rows:
        reconstructed = asyncio.run(capture_app(row['prompt'],deep=row['mode']=='deep',speech=row['speech'],
                                                schema=runtime_schema(row) if row['path']=='one_shot' else None))
        assert reconstructed == row['app_payload'],'Round-trip app payload drift'
    return manifest, rows


async def execute(root_go, output, manifest, rows):
    # All service calls, resource probes and GPU work start only here.
    import fcntl
    import re
    import subprocess
    from tutor_app import local_models
    from tutor_app.ai import SYSTEM
    from tutor_app.local_ai import LocalAI, _LIMIT
    from tutor_app.tutor_ai import TutorAI
    from tutor_app.stem_training import ResourceMonitor
    output = execution_gate(root_go, output)
    lock = (SSD / 'stem-tutor-training/.native-probe-runtime.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    started = time.monotonic()
    try:
        resources = ResourceMonitor()
        output.mkdir()
    except BaseException:
        lock.close()
        raise
    receipt = dict(state='running', input_manifest_sha256=sha(ROOT / 'manifest.json'),
                   requested_order=manifest['order'], options_status=manifest['options_status'],
                   initial_resources=resources.initial, root_go=True, completed_conditions=0)
    write(output / 'receipt.json', receipt)
    events = (output / 'public-events.jsonl').open('x')
    observations, context = [], {'id': 'startup', 'turn': None}
    def record(event):
        events.write(dump(helpers.contextual_event(context, event, time.monotonic()-started)) + '\n')
        events.flush()
    class Probe(LocalAI):
        def __init__(self):
            super().__init__(SYSTEM, document=True)
            self.reset_public()
            self.expected = None
            self.app_expected = None
            self.document_chat = False
            self.deep = False
        def reset_public(self):
            self.tail, self.parts, self.reason, self.counters = '', [], None, {}
            self.thought, self.first_public, self.thinking_first, self.thinking_seconds = False, None, None, 0
            self.captured = []
        async def _connect(self, deadline):
            return await asyncio.wait_for(asyncio.open_connection('127.0.0.1', 11434, limit=_LIMIT),
                                          max(.001, deadline-time.monotonic()))
        def _decode(self, line):
            clean, self.tail = sanitize(json.loads(line), self.tail)
            return LocalAI._decode(dump(clean).encode())
        def _with_context(self, payload, model):
            return {**super()._with_context(payload, model), 'options': options(self.deep)}
        async def _http_events(self, payload, timeout, path='/api/chat', **kwargs):
            generating = path == '/api/chat' and bool(payload.get('messages'))
            if generating:
                assert payload == self.app_expected,'Actual app request differs from frozen full request'
                original = copy.deepcopy(payload)
                payload = compat_payload(payload,document_chat=self.document_chat)
                if self.document_chat:
                    assert_pair(payload,original)
                else:
                    assert payload == original and 'format' in payload,'Marking native format changed'
                assert payload == self.expected, 'Actual native request differs from frozen app/contrast payload'
                self.captured.append(copy.deepcopy(payload))
                record({'type':'request','payload':payload,'app_payload':original,
                        'document_format_omitted':self.document_chat})
            else:
                record({'type': 'control_request', 'path': path})
            async with aclosing(super()._http_events(payload, timeout, path, **kwargs)) as stream:
                async for event in stream:
                    message = event.get('message') or {}
                    now = time.monotonic()
                    if generating:
                        if message.get('thinking'):
                            self.thought = True
                            if self.thinking_first is None:
                                self.thinking_first = now
                        if message.get('content'):
                            if self.first_public is None:
                                self.first_public = now - self.turn_started
                            self.parts.append(message['content'])
                        if (message.get('content') or event.get('done')) and self.thinking_first is not None:
                            self.thinking_seconds += now-self.thinking_first
                            self.thinking_first = None
                        if event.get('done'):
                            self.reason = event.get('done_reason')
                            self.counters = {k: event[k] for k in COUNTERS if k in event}
                    record({'type': 'public_event', 'event': event})
                    yield event
    local = Probe()
    async def control(path, payload=None, seconds=10):
        try:
            async with aclosing(local._http_events(payload or {}, seconds, path, method='GET' if payload is None else 'POST',
                                                   start_service=False)) as stream:
                return [event async for event in stream]
        except Exception as exc:
            raise Fatal('Server control failed: ' + type(exc).__name__ + ': ' + str(exc)) from exc
    async def residency(empty=False):
        result = await control('/api/ps')
        found = next((r['models'] for r in result if 'models' in r), None)
        if found is None:
            raise Fatal('Missing native residency report')
        names = {m.get('name') or m.get('model') for m in found}
        if names - {NAME} or empty and names:
            raise Fatal('Unexpected resident model; root must resolve ownership')
        if any(m.get('size_vram', 0) > 14*1024**3 for m in found):
            raise Fatal('Native reported size_vram exceeds 14 GiB')
        return found
    async def headroom():
        try:
            await asyncio.to_thread(resources.check)
            vm = await asyncio.to_thread(subprocess.check_output, ['vm_stat'], text=True, timeout=3)
            page = int(re.search(r'page size of (\d+) bytes', vm)[1])
            available = sum(map(int, re.findall(r'^Pages (?:free|inactive|speculative):\s+(\d+)\.', vm, re.M))) * page
            if available < 3*1024**3:
                raise Fatal('OS available memory below 3 GiB')
            if time.monotonic()-started >= 600:
                raise Fatal('Ten-minute total wall limit')
        except Fatal:
            raise
        except Exception as exc:
            raise Fatal('Resource guard: ' + str(exc)) from exc
    async def guard():
        while True:
            await headroom()
            await residency()
            await asyncio.sleep(2)
    async def bounded(coro, seconds):
        try:
            await headroom()
        except BaseException:
            coro.close()
            raise
        work, monitor = asyncio.create_task(coro), asyncio.create_task(guard())
        try:
            done, _ = await asyncio.wait({work, monitor}, timeout=min(seconds, max(.001, 600-(time.monotonic()-started))),
                                         return_when=asyncio.FIRST_COMPLETED)
            if monitor in done:
                monitor.result()
            if work not in done:
                await headroom()
                raise TimeoutError('Condition deadline')
            return await work
        finally:
            work.cancel(); monitor.cancel()
            await asyncio.gather(work, monitor, return_exceptions=True)
    owned = False
    try:
        if [e.get('version') for e in await control('/api/version')] != ['0.40.11']:
            raise Fatal('Require native server 0.40.11')
        await residency(empty=True)  # No model may be resident before this run takes ownership.
        for row in rows:
            await headroom()
            context.update(id=row['id'], turn=1)
            begin = time.monotonic()
            observation = dict(id=row['id'], error=None, app_ok=None, public_final='', finish_reason=None)
            try:
                await residency()
                owned = True
                await local.reset()
                local.reset_public();local.expected=row['payload'];local.app_expected=row['app_payload']
                local.deep=row['mode']=='deep';local.document_chat=row['path']=='chat'
                local.turn_started=begin
                first_rendered,rendered,app_result=None,[],None
                async def native_request():
                    nonlocal first_rendered,app_result
                    tutor=TutorAI(cwd=output,model=ALIAS,document=True,usage_file=None)
                    tutor.local_web=False;tutor.speech=row['speech'];tutor._local=local
                    try:
                        if row['path']=='one_shot':
                            _,app_result=await tutor.one_shot(row['prompt'],schema=runtime_schema(row),model=ALIAS,
                                                            timeout=row['seconds'],think=False)
                        else:
                            async with aclosing(tutor.stream(row['prompt'],model=ALIAS,think=local.deep)) as stream:
                                async for block in stream:
                                    if first_rendered is None:first_rendered=time.monotonic()-begin
                                    rendered.append(block)
                            app_result=tutor.last
                    finally:
                        tutor._local=None
                        await tutor.close()
                try:
                    await bounded(native_request(),row['seconds'])
                finally:
                    observation.update(public_final=''.join(local.parts),finish_reason=local.reason,
                        thinking_observed=local.thought,thinking_seconds=local.thinking_seconds,
                        first_public_seconds=local.first_public,first_rendered_seconds=first_rendered,
                        api_counters=local.counters,missing_counters=[k for k in COUNTERS if k not in local.counters],
                        app_ok=app_result.ok if app_result else None,
                        app_error=app_result.message if app_result and not app_result.ok else None,
                        rendered=''.join(rendered),actual_requests=len(local.captured),
                        document_format_omitted=local.document_chat)
            except Fatal:
                raise
            except AssertionError as exc:
                raise Fatal('Frozen payload/factory identity: '+str(exc)) from exc
            except (ConnectionError, OSError) as exc:
                raise Fatal('Server/runtime transport: '+str(exc)) from exc
            except Exception as exc:
                observation['error'] = type(exc).__name__ + ': ' + str(exc)
            finally:
                observation['seconds'] = time.monotonic()-begin
                observations.append(observation)
                record({'type': 'condition_result', **observation})
                write(output/'observations.json', observations)
                receipt['completed_conditions'] = len(observations)
                write(output/'receipt.json', receipt)
        receipt['state'] = 'eight_conditions_attempted'
    except BaseException as exc:
        receipt.update(state='fatal_stopped', error=type(exc).__name__ + ': ' + str(exc))
        raise
    finally:
        try:
            context.update(id='cleanup', turn=None)
            if owned:
                result = await control('/api/chat', {'model': NAME, 'messages': [], 'stream': False, 'keep_alive': 0}, 20)
                if not any(e.get('done') is True and e.get('done_reason') == 'unload' for e in result):
                    raise Fatal('Unload was not acknowledged')
            await residency(empty=True)
            receipt['cleanup'] = 'owned candidate unloaded; native residency verified empty'
        except Exception as exc:
            receipt['cleanup_error'] = type(exc).__name__ + ': ' + str(exc)
        await local.close()
        gold = json.loads((ROOT/'gold.json').read_text())  # Gold becomes readable only after all generation.
        write(output/'scores.json', [{'id': r['id'], 'scores': score(r, item, gold)}
              for r,item in zip(rows, observations)])
        receipt.update(elapsed_seconds=time.monotonic()-started, final_resources=resources.latest)
        write(output/'receipt.json', receipt)
        events.close(); lock.close()


def main():
    if sys.flags.optimize:
        raise RuntimeError('Run without Python optimisation')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare', action='store_true')
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--root-go', choices=['ROOT_GO'])
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.prepare:
        if args.execute:
            raise ValueError('Preparation and execution are separate')
        prepare()
    else:
        manifest, rows = check()
        if args.execute:
            execution_gate(args.root_go, args.output)
            from tutor_app import local_models
            with helpers.temporary_catalogue(local_models):
                asyncio.run(execute(args.root_go, args.output, manifest, rows))
        else:
            print(dump({'state': 'CPU_CHECKED_HOLD_ROOT_REVIEW', 'conditions': len(rows)}))


if __name__ == '__main__':
    main()
