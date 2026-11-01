import asyncio, ast, hashlib, json, tempfile, time
from contextlib import aclosing
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from markdown_it import MarkdownIt
from tutor_app import ai, chat_output, prompts
from tutor_app.tutor_ai import TutorAI

ROOT = Path('/Users/sora/Miscellaneous/02 Education/~~ AI Workflow/stem-tutor')
DEST = Path('/tmp/stem-format-current/candidate-cloud-extended-1.json')
if DEST.exists():
    raise SystemExit('Refusing to overwrite benchmark evidence')
LOCAL = json.loads((ROOT / 'docs/benchmarks/2026-10-26-structured-output/evidence/candidate-local-matrix-1.json').read_text())
frozen = {r['case']: r for r in LOCAL['rows'] if r['model'] == 'ollama:gemma4:e4b'}
CASES = [
    ('physics_calculation', 'CONTEXT\n(none)\n\nSTUDENT ASKS: For CAIE 9702 physics, a car accelerates uniformly from 4.0 m s^-1 to 16.0 m s^-1 in 6.0 s. Calculate the acceleration. Show the formula and substitution, give the result with its SI unit to two significant figures, and include one check.', False),
    *[(case, frozen[case]['prompt'], frozen[case]['speech']) for case in ('literal_code', 'speech', 'open_hint')],
]
SEEDS = [
    ('context_seed_alkanes', 'CONTEXT\n(none)\n\nSTUDENT ASKS: For CAIE 9701 organic chemistry, state the general molecular formula of an acyclic alkane and what n means. Use one short paragraph.'),
    ('context_seed_alcohols', 'STUDENT ASKS: Now state the general molecular formula of a saturated acyclic monohydric alcohol, with n counting all its carbon atoms. Include the relevant structural assumptions in one short paragraph.'),
    ('context_seed_summary', 'STUDENT ASKS: Summarise the organic formulae we have just discussed in one short sentence, without introducing a new topic.'),
]
MARKS = [
    (r['case'], r['stem'], r['points'], r['student_answer'], r['expected'])
    for r in LOCAL['rows'] if r['model'] == 'ollama:gemma4:e4b' and r['case'].startswith('mark_')
]
MARKS.append(('mark_physics_omission', 'State the expression for kinetic energy and explain how it changes when speed doubles at constant mass.',
              ['Kinetic energy equals one half of mass multiplied by speed squared.',
               'At constant mass, doubling speed quadruples kinetic energy.'],
              'Kinetic energy is one half of the mass times the square of the speed.', [True, False]))
EXACT_LINE = 'record = {"reply": "x_1^2", "cost": "$5", "rate": "50%"}'
rows, releases = [], []
metadata = {
    'created_utc': datetime.now(timezone.utc).isoformat(),
    'base_head': 'aa558ff21ca1da5a46487a9ce6d0811c6f059d62',
    'scope': 'Live cloud extension: physics, exact literal source, separate speech, OPEN protection, real prior turns, and grading.',
    'system': ai.SYSTEM,
    'code_sha256_at_start': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT / 'app/tutor_app').glob('*.py')},
    'frozen_source_sha256': hashlib.sha256((ROOT / 'docs/benchmarks/2026-10-26-structured-output/evidence/candidate-local-matrix-1.json').read_bytes()).hexdigest(),
    'host_condition': 'Concurrent exclusive local MLX training session72543 on this Mac. This benchmark uses remote cloud models only; timings do not isolate transport or formatting cost.',
    'limits': 'Single observations per provider/case. No manual retries. Native result.ok is delivery evidence, not scientific correctness.',
    'models': {'sonnet': {'think': False, 'reasoning': 'off'}, 'codex:gpt-6.1-sol': {'think': False, 'reasoning': 'low'}},
    'privacy': 'Synthetic questions only; temporary cwd and usage file; no live learner files, settings, auth, or local runtime touched.',
    'startup_failure': 'First launch failed before any model call: tutorlib absent from task PYTHONPATH. Log retained separately; corrected task-only PYTHONPATH includes plugin scripts.',
}

def save():
    temporary = DEST.with_suffix('.tmp')
    temporary.write_text(json.dumps({**metadata, 'rows': rows, 'releases': releases}, ensure_ascii=False, indent=2))
    temporary.replace(DEST)

def code_checks(text):
    blocks = [t.content for t in MarkdownIt('commonmark').parse(text) if t.type == 'fence']
    exact = [b for b in blocks if EXACT_LINE in b.splitlines()]
    parsed, errors = False, []
    for block in exact:
        try:
            tree = ast.parse(block)
            parsed = any(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) for node in tree.body)
        except SyntaxError as exc:
            errors.append(str(exc))
    return {'requested_line_in_code_block': bool(exact), 'same_block_has_parseable_function': parsed,
            'ast_errors': errors, 'generated_code_executed': False}

async def chat(client, model, case, prompt, speech=False, reset=True, seed_count=0):
    if reset:
        await client.reset(warm=False)
    client.speech = speech
    started, first, parts = time.monotonic(), None, []
    try:
        async def consume():
            nonlocal first
            async with aclosing(client.stream(prompt, model=model, think=False)) as stream:
                async for part in stream:
                    if first is None:
                        first = time.monotonic() - started
                    parts.append(part)
        await asyncio.wait_for(consume(), 310)
        result = asdict(client.last)
    except Exception as exc:
        result = {'ok': False, 'message': type(exc).__name__ + ': ' + str(exc), 'text': ''.join(parts)}
    row = {'model': model, 'think': False, 'case': case, 'speech': speech, 'prompt': prompt,
           'prompt_sha256': hashlib.sha256(prompt.encode()).hexdigest(), 'schema': chat_output.document_schema(speech),
           'result': result, 'seconds': time.monotonic() - started, 'first_seconds': first,
           'stream_equals_final': ''.join(parts) == result.get('text'), 'prior_live_seed_turns': seed_count,
           'local_client_created': client._local is not None}
    if model.startswith('codex:'):
        row['retained_history_messages_after'] = [len(h) for h in client.codex._history.values()]
    if case == 'literal_code':
        row['literal_checks'] = code_checks(result.get('text', ''))
    rows.append(row); save()
    print(json.dumps({'model': model, 'case': case, 'ok': result.get('ok'), 'seconds': round(row['seconds'], 2), 'message': result.get('message')}), flush=True)
    return result.get('ok')

async def main():
    save()
    for model in metadata['models']:
        with tempfile.TemporaryDirectory(prefix='stem-cloud-extended-') as folder:
            cwd = Path(folder)
            client = TutorAI(cwd, model=model, usage_file=cwd / 'usage.json')
            client.local_web = False
            client.wanted = lambda: False
            host_attempts = []
            original = client._one_shot
            async def observed_one_shot(*args, **kwargs):
                started = time.monotonic()
                data, result = await original(*args, **kwargs)
                host_attempts.append({'data': data, 'result': asdict(result), 'seconds': time.monotonic() - started})
                return data, result
            client._one_shot = observed_one_shot
            try:
                for case, prompt, speech in CASES:
                    await chat(client, model, case, prompt, speech)
                await client.reset(warm=False)
                client.speech = False
                seed_success = []
                for i, (case, prompt) in enumerate(SEEDS):
                    seed_success.append(await chat(client, model, case, prompt, reset=False, seed_count=i))
                await chat(client, model, 'long_context', frozen['long_context']['prompt'], reset=False, seed_count=len(SEEDS))
                rows[-1]['prior_seed_successes'] = seed_success
                save()
                for case, stem, points, answer, expected in MARKS:
                    await client.reset(warm=False)
                    client.speech = False
                    start, before = time.monotonic(), len(host_attempts)
                    prompt = prompts.judge(stem, points, answer)
                    try:
                        data, result = await client.one_shot(prompt, schema=prompts.JUDGE, model=model, think=False, timeout=150)
                        record = asdict(result)
                    except Exception as exc:
                        data, record = None, {'ok': False, 'message': type(exc).__name__ + ': ' + str(exc)}
                    flags = [p.get('met') for p in (data or {}).get('points', [])]
                    copied = [p.get('point') for p in (data or {}).get('points', [])] == points
                    rows.append({'model': model, 'think': False, 'case': case, 'stem': stem, 'points': points,
                                 'student_answer': answer, 'expected': expected, 'prompt': prompt,
                                 'prompt_sha256': hashlib.sha256(prompt.encode()).hexdigest(), 'schema': prompts.JUDGE,
                                 'data': data, 'result': record, 'seconds': time.monotonic() - start,
                                 'decisions_match_expected': flags == expected and copied, 'copied_point_order_exact': copied,
                                 'claude_host_attempts': host_attempts[before:] if model == 'sonnet' else [],
                                 'local_client_created': client._local is not None})
                    save()
                    print(json.dumps({'model': model, 'case': case, 'ok': record.get('ok'), 'seconds': round(rows[-1]['seconds'], 2), 'decisions_match_expected': rows[-1]['decisions_match_expected']}), flush=True)
            finally:
                await client.close()
                releases.append({'model': model, 'closed': True, 'claude_children_remaining': len(client.procs),
                                 'codex_children_remaining': len(client._codex._procs) if client._codex is not None else 0,
                                 'local_client_created': client._local is not None})
                save()
    metadata['completed_utc'] = datetime.now(timezone.utc).isoformat()
    save()

asyncio.run(main())
