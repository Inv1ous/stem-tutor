import asyncio, hashlib, json, tempfile, time
from contextlib import aclosing
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from tutor_app import ai, chat_output
from tutor_app.tutor_ai import TutorAI

ROOT = Path('/Users/sora/Miscellaneous/02 Education/~~ AI Workflow/stem-tutor')
DEST = Path('/tmp/stem-format-current/candidate-cloud-large-context-1.json')
if DEST.exists(): raise SystemExit('Refusing to overwrite benchmark evidence')
source = ROOT / 'docs/benchmarks/2026-10-26-structured-output/evidence/candidate-local-matrix-1.json'
frozen = next(r['prompt'] for r in json.loads(source.read_text())['rows'] if r['case'] == 'long_context')
body = '\n'.join(('Earlier organic study context '+str(i)+'. ')*120 for i in range(4))
seed = ('CONTEXT\nSTALE ORGANIC REVISION BACKGROUND, supplied only to establish prior conversation context:\n' + body +
        '\n\nSTUDENT ASKS: This is earlier revision context, not a question. Acknowledge it in one short sentence; do not summarise or answer anything else.')
rows, releases = [], []
metadata = {
 'created_utc': datetime.now(timezone.utc).isoformat(),
 'scope': 'Actual large prior user turn, then unchanged current NaCl assessment evidence; two live calls per provider.',
 'system': ai.SYSTEM,
 'code_sha256_at_start': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'app/tutor_app').glob('*.py')},
 'frozen_source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
 'large_seed_body_utf8_bytes': len(body.encode()), 'large_seed_prompt_utf8_bytes': len(seed.encode()),
 'current_prompt_utf8_bytes': len(frozen.encode()),
 'construction': 'Four complete120-repeat blocks from the original synthetic local-history pattern, about16KB; eight such blocks would be31,680bytes.',
 'host_condition': 'Concurrent exclusive local MLX training72543; remote cloud only; no causal latency comparison.',
 'limits': 'One observation per case. Repetitive synthetic stale context, not a realistic comprehension task or model context-window benchmark. Successful seed required to establish retained prior context.',
 'privacy': 'Synthetic questions and visible replies only; temporary cwd/usage, existing account sign-ins, no settings/auth/local runtime changes.',
}

def save():
 tmp=DEST.with_suffix('.tmp');tmp.write_text(json.dumps({**metadata,'rows':rows,'releases':releases},ensure_ascii=False,indent=2));tmp.replace(DEST)

async def main():
 save()
 for model in ('sonnet','codex:gpt-6.1-sol'):
  with tempfile.TemporaryDirectory(prefix='stem-cloud-large-context-') as folder:
   cwd=Path(folder);c=TutorAI(cwd,model=model,usage_file=cwd/'usage.json');c.local_web=False;c.wanted=lambda:False
   native_metadata=[];native_inputs=[]
   if model.startswith('codex:'):
    original=c.codex._events
    async def observed_events(messages,name,think,system,schema,deadline):
     started=time.monotonic();native_inputs.append({'messages':messages,'wire_utf8_bytes':len(json.dumps({'messages':messages},ensure_ascii=False).encode()),'system_utf8_bytes':len(system.encode()),'model':name,'think':think,'schema':schema})
     async with aclosing(original(messages,name,think,system,schema,deadline)) as events:
      async for event in events:
       item=event.get('item') or {}
       native_metadata.append({'elapsed_seconds':time.monotonic()-started,'type':event.get('type'),
          'item_type':item.get('type') if isinstance(item,dict) else None,
          'phase':item.get('phase') if isinstance(item,dict) else None,
          'status':item.get('status') if isinstance(item,dict) else None})
       yield event
    c.codex._events=observed_events
   seed_ok=False
   try:
    for case,prompt in [('large_context_seed',seed),('current_after_large_context',frozen)]:
     started=time.monotonic();first=None;parts=[];event_start=len(native_metadata);input_start=len(native_inputs)
     try:
      async def consume():
       nonlocal first
       async with aclosing(c.stream(prompt,model=model,think=False)) as stream:
        async for part in stream:
         if first is None:first=time.monotonic()-started
         parts.append(part)
      await asyncio.wait_for(consume(),310);result=asdict(c.last)
     except Exception as exc:result={'ok':False,'message':type(exc).__name__+': '+str(exc),'text':''.join(parts)}
     row={'model':model,'think':False,'case':case,'prompt':prompt,'prompt_sha256':hashlib.sha256(prompt.encode()).hexdigest(),
          'prompt_utf8_bytes':len(prompt.encode()),'result':result,'seconds':time.monotonic()-started,'first_seconds':first,
          'stream_equals_final':''.join(parts)==result.get('text'),'schema':chat_output.document_schema(),
          'large_prior_seed_success':seed_ok if case=='current_after_large_context' else None,
          'native_event_metadata':native_metadata[event_start:],'native_request_inputs':native_inputs[input_start:],
          'local_client_created':c._local is not None}
     if model=='sonnet':row['stdin_message_utf8_bytes']=len((json.dumps({'type':'user','message':{'role':'user','content':prompt}})+'\n').encode())
     else:row['retained_history_messages_after']=[len(h) for h in c.codex._history.values()]
     rows.append(row);save();print(json.dumps({'model':model,'case':case,'ok':result.get('ok'),'seconds':round(row['seconds'],2),'message':result.get('message')}),flush=True)
     if case=='large_context_seed':seed_ok=result.get('ok') is True
   finally:
    await c.close();releases.append({'model':model,'closed':True,'claude_children_remaining':len(c.procs),'codex_children_remaining':len(c._codex._procs) if c._codex else 0,'local_client_created':c._local is not None});save()
 metadata['completed_utc']=datetime.now(timezone.utc).isoformat();save()

asyncio.run(main())
