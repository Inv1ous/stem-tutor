import asyncio,hashlib,json,re,tempfile,time
from contextlib import aclosing
from dataclasses import asdict
from datetime import datetime,timezone
from pathlib import Path
from tutor_app.tutor_ai import TutorAI

ROOT=Path('/Users/sora/Miscellaneous/02 Education/~~ AI Workflow/stem-tutor')
DEST=Path('/tmp/stem-format-current/codex-startup-diagnostic-1.json')
if DEST.exists():raise SystemExit('Refusing to overwrite diagnostic evidence')

def redact(value):
 if isinstance(value,dict):
  return {str(k):redact(v) for k,v in value.items() if str(k) in {'code','status','status_code','message','text','error','type'}}
 if isinstance(value,str):
  value=re.sub(r'\bsk-[A-Za-z0-9_-]+','[REDACTED]',value)
  value=re.sub(r'(?i)Bearer\s+[^\s"\']+','Bearer [REDACTED]',value)
  value=re.sub(r'\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+','[REDACTED]',value)
  value=re.sub(r'(?i)((?:access_token|api_key|authorization|[?&]token|[?&]key)\s*[:=]\s*)[^\s,;]+',r'\1[REDACTED]',value)
  return value[:600]
 return value if value is None or type(value) in (int,float,bool) else str(type(value).__name__)

async def main():
 metadata={'created_utc':datetime.now(timezone.utc).isoformat(),'scope':'One fresh minimal public-startup-error diagnosis, not a benchmark retry or a history A/B test.',
  'model':'codex:gpt-6.1-sol','think':False,'reasoning':'low','deadline_seconds':60,
  'prompt':'Reply with one short acknowledgement.',
  'code_sha256_at_start':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'app/tutor_app').glob('*.py')},
  'limits':'Only public item.type=error message/text/error fields captured, redacted and bounded600characters perstring. No reasoning item content, configuration changes or local model work.'}
 events=[]
 with tempfile.TemporaryDirectory(prefix='stem-codex-startup-diagnostic-') as folder:
  cwd=Path(folder);c=TutorAI(cwd,model=metadata['model'],usage_file=cwd/'usage.json');c.local_web=False;c.wanted=lambda:False
  original=c.codex._events
  async def observed(messages,name,think,system,schema,deadline):
   start=time.monotonic()
   async with aclosing(original(messages,name,think,system,schema,deadline)) as stream:
    async for event in stream:
     item=event.get('item') or {};row={'elapsed_seconds':time.monotonic()-start,'type':event.get('type'),'item_type':item.get('type') if isinstance(item,dict) else None,'phase':item.get('phase') if isinstance(item,dict) else None}
     if isinstance(item,dict) and item.get('type')=='error':
      row['public_error_fields']={key:redact(item[key]) for key in ('message','text','error') if key in item}
     events.append(row)
     yield event
  c.codex._events=observed
  started=time.monotonic();parts=[]
  try:
   async def consume():
    async with aclosing(c.stream(metadata['prompt'],model=metadata['model'],think=False)) as reply:
     async for part in reply:parts.append(part)
   try:
    await asyncio.wait_for(consume(),60);result=asdict(c.last)
   except asyncio.TimeoutError:
    result={'ok':False,'status':'error','message':'Diagnostic-only outer60-second deadline reached. The app chat deadline was not changed.','text':''.join(parts)}
   except Exception as exc:result={'ok':False,'status':'error','message':type(exc).__name__+': '+str(exc),'text':''.join(parts)}
  finally:
   await c.close()
  metadata.update(completed_utc=datetime.now(timezone.utc).isoformat(),seconds=time.monotonic()-started,result=result,native_event_metadata=events,
   closed=True,codex_children_remaining=len(c.codex._procs),claude_children_remaining=len(c.procs),local_client_created=c._local is not None)
 with DEST.open('x') as f:json.dump(metadata,f,ensure_ascii=False,indent=2)
 print(json.dumps({'ok':metadata['result'].get('ok'),'seconds':metadata['seconds'],'events':events},ensure_ascii=False),flush=True)

asyncio.run(main())
