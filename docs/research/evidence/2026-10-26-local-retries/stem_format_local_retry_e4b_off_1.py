"""Retained post-hardening local trials. Serial inference; frozen prompts unchanged."""
import asyncio
import hashlib
import json
import time
from contextlib import aclosing
from dataclasses import asdict
from pathlib import Path

from tutor_app import ai, chat_output
from tutor_app.tutor_ai import TutorAI

ROOT = Path('/Users/sora/Miscellaneous/02 Education/~~ AI Workflow/stem-tutor')
SOURCE = Path('/tmp/stem-format-current/candidate-local-matrix-1.json')
DEST = Path('/tmp/stem-format-current/candidate-local-retry-e4b-off-1.json')
if DEST.exists():
    raise SystemExit('Refusing to overwrite retained retry evidence')
frozen = json.loads(SOURCE.read_text())
rows, releases, bad = [], [], []
code_hashes = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
               for p in (ROOT / 'app/tutor_app').glob('*.py')}
metadata = {'source': str(SOURCE), 'source_sha256': hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
            'system': ai.SYSTEM, 'code_sha256_start': code_hashes,
            'scope': 'Frozen E4B Thinking Off bonding/topic_change/literal_code following retained Thinking On coverage failures.',
            'limitations': 'Serial retained trials; transport validity is separate from factual coverage. No claim that planning estimates guarantee native memory safety.'}

def save():
    DEST.write_text(json.dumps({**metadata, 'rows': rows, 'releases': releases}, ensure_ascii=False, indent=2))

original_render = chat_output._render

def checked_render(kind, text, step):
    try:
        return original_render(kind, text, step)
    except chat_output.DocumentError as exc:
        bad.append({'kind': kind, 'text': text, 'error': str(exc)})
        raise
chat_output._render = checked_render
original_token = chat_output.DocumentDecoder._token

def checked_token(self, token, value, emitted):
    try:
        return original_token(self, token, value, emitted)
    except chat_output.DocumentError as exc:
        bad.append({'stage': 'decoded_token', 'block': dict(self._block),
                    'token': token, 'state': self._state, 'error': str(exc)})
        raise
chat_output.DocumentDecoder._token = checked_token


def frozen_case(model, case):
    return next(row for row in frozen['rows'] if row['model'] == model and row['case'] == case)


async def trial(client, model, think, case, *, condition='warm', repetition=1):
    source = frozen_case(model, case)
    prompt, speech = source['prompt'], source.get('speech', case == 'speech')
    await client.reset(warm=False)
    client.speech = speech
    seeded = 0
    if case == 'long_context':
        wire = json.dumps({'blocks': [{'kind': 'paragraph', 'text': 'Earlier organic revision. Alkanes are saturated hydrocarbons.'}]})
        history = []
        for i in range(8):
            history.extend([{'role': 'user', 'content': ('Earlier organic study context ' + str(i) + '. ') * 120},
                            {'role': 'assistant', 'content': wire}])
        client.local._history[(model, client.local._effort(model, think), speech)] = history
        seeded = len(history)
    parts, requests, first = [], [], None
    local = client.local
    original_events = local._events
    async def recorded_events(payload, timeout, path='/api/chat'):
        record = {'path': path, 'payload': json.loads(json.dumps(payload)), 'event_done': False}
        requests.append(record)
        async with aclosing(original_events(payload, timeout, path)) as events:
            async for event in events:
                visible = (event.get('message') or {}).get('content')
                if visible:
                    record.setdefault('visible_json_chunks', []).append(visible)
                if event.get('done'):
                    record['event_done'] = True
                    record['done_reason'] = event.get('done_reason')
                yield event
        record['owned_server_pid'] = local._owned.pid if local._owned is not None else None
        process = getattr(local._mlx, '_process', None)
        record['owned_mlx_worker_pid'] = process.pid if process is not None else None
    local._events = recorded_events
    start, bad_start = time.monotonic(), len(bad)
    print(json.dumps({'phase': 'start', 'model': model, 'case': case, 'condition': condition, 'repetition': repetition}), flush=True)
    try:
        async def consume():
            nonlocal first
            async for part in client.stream(prompt, model=model, think=think):
                if first is None:
                    first = time.monotonic() - start
                parts.append(part)
        await asyncio.wait_for(consume(), 310)
        result = asdict(client.last)
    except Exception as exc:
        result = {'ok': False, 'message': type(exc).__name__ + ': ' + str(exc), 'text': ''.join(parts)}
    finally:
        local._events = original_events
    row = {'model': model, 'think': think, 'case': case, 'condition': condition, 'repetition': repetition,
           'speech': speech, 'prompt': prompt, 'prompt_sha256': hashlib.sha256(prompt.encode()).hexdigest(),
           'result': result, 'seconds': time.monotonic() - start, 'first_seconds': first,
           'stream_equals_final': ''.join(parts) == result.get('text'), 'bad_blocks': bad[bad_start:],
           'seeded_history_messages': seeded, 'requests': requests}
    if case == 'literal_code':
        row['exact_literal_line_present'] = 'record = {"reply": "x_1^2", "cost": "$5", "rate": "50%"}' in result.get('text', '')
    if case == 'long_context':
        generated = [r['payload'] for r in requests if r['payload'].get('messages')]
        row['actual_generation_message_counts'] = [len(p['messages']) for p in generated]
        row['current_prompt_preserved'] = all(p['messages'][-1]['content'] == prompt for p in generated)
        row['generation_content_bytes'] = [sum(len(m.get('content', '').encode()) for m in p['messages']) for p in generated]
    history = local._history.get((model, local._effort(model, think), speech), [])
    row['validated_assistant_wire'] = history[-1]['content'] if history and result.get('ok') else None
    rows.append(row)
    save()
    print(json.dumps({'phase': 'result', 'model': model, 'case': case, 'condition': condition,
                      'repetition': repetition, 'ok': result.get('ok'), 'seconds': round(row['seconds'], 2),
                      'message': result.get('message'), 'message_counts': row.get('actual_generation_message_counts'),
                      'literal_exact': row.get('exact_literal_line_present')}), flush=True)


async def release(client, model):
    record = {'model': model}
    local = client._local
    if local is not None and model.startswith('ollama:'):
        try:
            request = {'model': model.removeprefix('ollama:'), 'messages': [], 'stream': False, 'keep_alive': 0}
            async with aclosing(local._http_events(request, 30, start_service=False)) as events:
                async for event in events:
                    record['unload_done'] = event.get('done')
                    record['unload_reason'] = event.get('done_reason')
        except Exception as exc:
            record['unload_error'] = type(exc).__name__ + ': ' + str(exc)
    await client.close()
    record['closed'] = True
    releases.append(record)
    save()
    print(json.dumps({'phase': 'released', **record}), flush=True)


async def main():
    save()
    groups = [
        ('ollama:gemma4:e4b', False, ['bonding', 'topic_change', 'literal_code']),
    ]
    for model, think, cases in groups:
        client = TutorAI(ROOT, model=model)
        client.local_web = False
        try:
            for index, case in enumerate(cases):
                await trial(client, model, think, case, condition='cold' if index == 0 else 'warm')
        finally:
            await release(client, model)
    metadata['code_sha256_end'] = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                                   for p in (ROOT / 'app/tutor_app').glob('*.py')}
    save()

asyncio.run(main())
