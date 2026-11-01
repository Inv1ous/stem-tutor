#!/usr/bin/env python3
"""CPU preparation by default. Seven DEV conditions require --execute --root-go ROOT_GO."""
from __future__ import annotations
import argparse
import asyncio
from contextlib import aclosing
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parent
SSD = Path('/Volumes/External SSD TB4/LocalAI')
REPO = Path('/Users/sora/Miscellaneous/02 Education/~~ AI Workflow/stem-tutor')
MODEL = SSD / 'models/stem-tutor-qwen35-hybrid-v1'
PYTHON = SSD / 'tutor-runtime/stem-training/.venv/bin/python'
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
    return {**helpers.requested_options('deep' if deep else 'fast'), 'num_predict': 1024 if deep else 512}


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


def assert_pair(c, d):
    expected = copy.deepcopy(d)
    expected.pop('format')
    assert c == expected, 'C/D differ beyond format'


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


async def capture_app(prompt, *, deep=False, schema=None):
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
        tutor.speech = schema is None
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


async def build_fixtures():
    from tutor_app import chat_output, prompts
    row = next(json.loads(line) for line in (DEV / 'test.jsonl').read_text().splitlines()
               if json.loads(line)['id'] == MARK_ID)
    supplied = json.loads(row['messages'][0]['content'].rsplit('\n', 1)[-1])
    criteria = supplied['criteria']
    mark_prompt = prompts.judge('State the defining properties of linear momentum.', criteria, supplied['response'])
    d = await capture_app(USER)
    c = copy.deepcopy(d); c.pop('format')
    assert_pair(c, d)
    a = copy.deepcopy(c); a['messages'] = [{'role': 'user', 'content': USER}]
    b = copy.deepcopy(a); b['format'] = copy.deepcopy(d['format'])
    deep = await capture_app(USER, deep=True)
    marking_schema = prompts.local_judge_schema(criteria)
    marking = await capture_app(mark_prompt, schema=marking_schema)
    cases = [dict(id='python', mode='fast', seconds=45, max_tokens=512, path='chat', speech=True,
                  criteria=None, schema=chat_output.document_schema(True), messages=a['messages']),
             *[dict(id=label, mode='fast', seconds=45, max_tokens=512, path='chat', speech=True,
                    criteria=None, schema=chat_output.document_schema(True), payload=payload)
               for label, payload in [('A', a), ('B', b), ('C', c), ('D', d)]],
             dict(id='mark', mode='fast', seconds=45, max_tokens=512, path='one_shot', speech=False,
                  criteria=criteria, schema=marking_schema, prompt=mark_prompt, payload=marking,
                  development_source_id=MARK_ID),
             dict(id='Deep', mode='deep', seconds=60, max_tokens=1024, path='chat', speech=True,
                  criteria=None, schema=chat_output.document_schema(True), payload=deep)]
    return dict(conditions=cases, gold={'work': {'expected': {}, 'numeric_work_joules': 3.0,
                                              'required_precision': '3.0 J', 'manual_review_required': True},
                                      'mark': {'expected': row['expected']}},
                renders={r['id']: render_evidence(r.get('payload', r).get('messages'), r['mode'] == 'deep')
                         for r in cases})


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
    value = helpers.score_case({**row, 'task': 'marking' if row['id'] == 'mark' else 'calculation'},
                               observation.get('public_final', ''), observation.get('finish_reason'),
                               gold['mark' if row['id'] == 'mark' else 'work'])
    raw = observation.get('public_final', '')
    value['repeated_substring_heuristic'] = any(raw.count(raw[i:i+16]) >= 8 for i in range(0, max(0, len(raw)-16), 16))
    value['arithmetic_and_spoken_meaning'] = 'manual_review_required' if row['id'] != 'mark' else 'not_applicable'
    value['native_control_valid'] = (observation.get('thinking_observed', False) if row['mode'] == 'deep'
                                     else not observation.get('thinking_observed', False))
    value['application_delivery'] = observation.get('app_ok')
    value['successful_complete_delivery'] = bool(value['delivered'] and value['raw_schema_valid']
                                                 and (value['decoder_finish'] if row['path'] == 'chat' else
                                                      value['marking_vector_available']) and not observation.get('error')
                                                 and observation.get('app_ok') is not False)
    return value


def prepare():
    if (ROOT / 'manifest.json').exists():
        raise ValueError('Frozen manifest already exists')
    fixture = asyncio.run(build_fixtures())
    write(ROOT / 'inputs.json', fixture['conditions'])
    write(ROOT / 'gold.json', fixture['gold'])
    write(ROOT / 'cpu-render-evidence.json', fixture['renders'])
    assert all(value['equal'] for value in fixture['renders'].values()), 'CPU source-derived render mismatch'
    source_paths = [REPO / 'app/tutor_app' / (name + '.py') for name in helpers.DEPENDENCIES]
    source_paths += [DEV / name for name in ('test.jsonl', 'selection.json', 'manifest.json')]
    source_paths += [helpers.MODEL_MANIFEST, PYTHON, SSD / 'tutor-runtime/stem-training/requirements.lock',
                     SSD / 'stem-tutor-training/native-probe-v1/native_probe_v1.py',
                     SSD / 'stem-tutor-training/native-probe-v1/manifest-v3-recorder-fixed.json']
    source_paths += [MODEL / name for name in ('tokenizer.json', 'tokenizer_config.json', 'chat_template.jinja',
                                             'vocab.json', 'fusion_receipt.json', 'config.json')]
    # Weight identities are inherited from the independently verified fusion receipt; no new model loading.
    write(ROOT / 'manifest.json', dict(version=1, state='CPU_FROZEN_HOLD_ROOT_REVIEW',
        evaluation_role='DEVELOPMENT ONLY; no challenge rows; no sampler selection',
        order=['python', 'A', 'B', 'C', 'D', 'mark', 'Deep'], always_attempt_all_conditions=True,
        exception='Fatal resource/server/wall/source-identity error stops remaining conditions',
        wall_seconds=360, native_version='0.40.11', options_status='requested; effective native fields not echoed',
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
    assert_pair(rows[3]['payload'], rows[4]['payload'])
    assert all('expected' not in row and 'gold' not in row for row in rows)
    actual = asyncio.run(build_fixtures())
    assert actual['conditions'] == rows, 'Actual CPU-captured app payload drift'
    assert actual['gold'] == json.loads((ROOT / 'gold.json').read_text())
    return manifest, rows


async def execute(root_go, output, manifest, rows):
    # All service calls, subprocess generation, resource probes and GPU work start only here.
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
                assert payload == self.expected, 'Actual native request differs from frozen app/contrast payload'
                self.captured.append(copy.deepcopy(payload))
                record({'type': 'request', 'payload': payload})
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
            if time.monotonic()-started >= 360:
                raise Fatal('Six-minute total wall limit')
        except Fatal:
            raise
        except Exception as exc:
            raise Fatal('Resource guard: ' + str(exc)) from exc
    async def guard():
        while True:
            await headroom()
            await residency(empty=context['id'] == 'python')
            await asyncio.sleep(2)
    async def bounded(coro, seconds):
        try:
            await headroom()
        except BaseException:
            coro.close()
            raise
        work, monitor = asyncio.create_task(coro), asyncio.create_task(guard())
        try:
            done, _ = await asyncio.wait({work, monitor}, timeout=min(seconds, max(.001, 360-(time.monotonic()-started))),
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
    async def python_reference():
        env = {**os.environ, 'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1'}
        process = await asyncio.create_subprocess_exec(str(PYTHON), str(ROOT/'python_reference.py'),
            '--execute', '--root-go', root_go, '--output', str(output/'python.json'), env=env,
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
        try:
            await process.wait()
        finally:
            if process.returncode is None:
                process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), 3)
                except asyncio.TimeoutError:
                    process.kill(); await process.wait()
        if not (output/'python.json').exists():
            return dict(id='python', error='Python child exited without a public result', public_final='',
                        finish_reason=None, child_exit=process.returncode)
        result = json.loads((output/'python.json').read_text())
        if result.get('fatal_resource'):
            raise Fatal(result['fatal_resource'])
        return {**result, 'child_exit': process.returncode}
    owned = False
    try:
        if [e.get('version') for e in await control('/api/version')] != ['0.40.11']:
            raise Fatal('Require native server 0.40.11')
        await residency(empty=True)  # No native resident before Python's GPU-capable child starts.
        for row in rows:
            await headroom()
            context.update(id=row['id'], turn=1)
            begin = time.monotonic()
            observation = dict(id=row['id'], error=None, app_ok=None, public_final='', finish_reason=None)
            try:
                if row['id'] == 'python':
                    observation.update(await bounded(python_reference(), row['seconds']))
                    await residency(empty=True)
                else:
                    await residency()
                    owned = True
                    await local.reset()
                    local.reset_public(); local.expected = row['payload']; local.deep = row['mode'] == 'deep'
                    local.turn_started = begin
                    first_rendered, rendered, app_result = None, [], None
                    async def native_request():
                        nonlocal first_rendered, app_result
                        if row['id'] in ('D', 'Deep', 'mark'):
                            tutor = TutorAI(cwd=output, model=ALIAS, document=True, usage_file=None)
                            tutor.local_web = False; tutor.speech = row['speech']; tutor._local = local
                            if row['id'] == 'mark':
                                _, app_result = await tutor.one_shot(row['prompt'], schema=row['schema'], model=ALIAS,
                                                                   timeout=row['seconds'], think=False)
                            else:
                                async with aclosing(tutor.stream(USER, model=ALIAS, think=local.deep)) as stream:
                                    async for block in stream:
                                        if first_rendered is None:
                                            first_rendered = time.monotonic()-begin
                                        rendered.append(block)
                                app_result = tutor.last
                            # No client close here: the run owns the shared native client until final cleanup.
                            tutor._local = None
                            await tutor.close()
                        else:
                            async with aclosing(local._http_events(row['payload'], row['seconds'], start_service=False)) as stream:
                                async for event in stream:
                                    if event.get('error'):
                                        raise RuntimeError(event['error'])
                    try:
                        await bounded(native_request(), row['seconds'])
                    finally:
                        observation.update(public_final=''.join(local.parts), finish_reason=local.reason,
                            thinking_observed=local.thought, thinking_seconds=local.thinking_seconds,
                            first_public_seconds=local.first_public, first_rendered_seconds=first_rendered,
                            api_counters=local.counters, missing_counters=[k for k in COUNTERS if k not in local.counters],
                            app_ok=app_result.ok if app_result else None,
                            app_error=app_result.message if app_result and not app_result.ok else None,
                            rendered=''.join(rendered), actual_requests=len(local.captured))
                        if row['id'] == 'D' and local.captured:
                            assert_pair(next(r for r in rows if r['id']=='C')['payload'], local.captured[0])
                            observation['c_d_identical_except_format'] = True
            except Fatal:
                raise
            except (ConnectionError, OSError) as exc:
                raise Fatal('Server/runtime transport: '+str(exc)) from exc
            except Exception as exc:
                observation['error'] = type(exc).__name__ + ': ' + str(exc)
            finally:
                if row['id'] == 'python' and (output/'python.json').exists():
                    # Keep the last public prefix even when the parent deadline terminates the child.
                    partial = json.loads((output/'python.json').read_text())
                    observation.update({k: v for k, v in partial.items() if k != 'error'})
                    observation['error'] = observation.get('error') or partial.get('error')
                observation['seconds'] = time.monotonic()-begin
                observations.append(observation)
                record({'type': 'condition_result', **observation})
                write(output/'observations.json', observations)
                receipt['completed_conditions'] = len(observations)
                write(output/'receipt.json', receipt)
        receipt['state'] = 'seven_conditions_attempted'
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
            receipt['cleanup'] = 'native residency verified empty; Python child exited'
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
