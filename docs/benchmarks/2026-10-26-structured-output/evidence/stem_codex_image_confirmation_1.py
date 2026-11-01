import asyncio,hashlib,json,re,tempfile,time
from contextlib import aclosing
from dataclasses import asdict
from datetime import datetime,timezone
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
from tutor_app.tutor_ai import TutorAI

ROOT=Path('/Users/sora/Miscellaneous/02 Education/~~ AI Workflow/stem-tutor')
DEST=Path('/tmp/stem-format-current/codex-image-capability-confirmation-1.json')
FIXTURE=Path('/tmp/stem-format-current/codex-image-capability-fixture-1.png')
if DEST.exists() or FIXTURE.exists():raise SystemExit('Refusing to overwrite diagnostic evidence')

def redact(value):
 if isinstance(value,dict):return {str(k):redact(v) for k,v in value.items() if str(k) in {'code','status','status_code','message','text','error','type'}}
 if isinstance(value,str):
  value=re.sub(r'\bsk-[A-Za-z0-9_-]+','[REDACTED]',value)
  value=re.sub(r'(?i)Bearer\s+[^\s"\']+','Bearer [REDACTED]',value)
  value=re.sub(r'\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+','[REDACTED]',value)
  value=re.sub(r'(?i)((?:access_token|api_key|authorization|[?&]token|[?&]key)\s*[:=]\s*)[^\s,;]+',r'\1[REDACTED]',value)
  return value[:600]
 return value if value is None or type(value) in (int,float,bool) else str(type(value).__name__)

async def main():
 metadata={'created_utc':datetime.now(timezone.utc).isoformat(),'scope':'One post-fix explicit-image compatibility confirmation, not a performance benchmark or history A/B.',
  'model':'codex:gpt-6.1-sol','think':False,'reasoning':'low','deadline_seconds':60,
  'prompt':'Read the attached image. Give the equation and its result in one brief answer.',
  'fixture_truth':'2 + 3 = ?','expected_result':5,
  'code_sha256_at_start':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'app/tutor_app').glob('*.py')},
  'limits':'Only public item.type=error message/text/error fields, bounded600characters and redacted; no reasoning content or environment values. Explicit image input is distinct from the optional view_image tool.'}
 events=[];invocations=[]
 with tempfile.TemporaryDirectory(prefix='stem-codex-image-confirmation-') as folder:
  cwd=Path(folder);picture=cwd/'question.png'
  image=Image.new('RGB',(720,240),'white');draw=ImageDraw.Draw(image);font=ImageFont.load_default(size=100)
  draw.text((80,60),'2 + 3 = ?',font=font,fill='black');image.save(picture)
  FIXTURE.write_bytes(picture.read_bytes())
  metadata['fixture']={'filename':'question.png','width':720,'height':240,'sha256':hashlib.sha256(picture.read_bytes()).hexdigest(),'bytes':picture.stat().st_size}
  c=TutorAI(cwd,model=metadata['model'],usage_file=cwd/'usage.json');c.local_web=False;c.wanted=lambda:False
  original_events=c.codex._events;original_launch=asyncio.create_subprocess_exec
  async def observed_launch(*args,**kwargs):
   invocations.append({'argv':list(args),'cwd':str(kwargs.get('cwd'))})
   return await original_launch(*args,**kwargs)
  async def observed_events(messages,name,think,system,schema,deadline):
   start=time.monotonic()
   metadata['native_request']={'messages':messages,'model':name,'think':think,'schema':schema,'system_utf8_bytes':len(system.encode())}
   async with aclosing(original_events(messages,name,think,system,schema,deadline)) as stream:
    async for event in stream:
     item=event.get('item') or {};row={'elapsed_seconds':time.monotonic()-start,'type':event.get('type'),'item_type':item.get('type') if isinstance(item,dict) else None,'phase':item.get('phase') if isinstance(item,dict) else None}
     if isinstance(item,dict) and item.get('type')=='error':row['public_error_fields']={k:redact(item[k]) for k in ('message','text','error') if k in item}
     events.append(row);yield event
  c.codex._events=observed_events;asyncio.create_subprocess_exec=observed_launch
  started=time.monotonic();parts=[]
  try:
   async def consume():
    async with aclosing(c.stream(metadata['prompt'],model=metadata['model'],think=False,image=picture)) as reply:
     async for part in reply:parts.append(part)
   try:
    await asyncio.wait_for(consume(),60);result=asdict(c.last)
   except asyncio.TimeoutError:result={'ok':False,'status':'error','message':'Diagnostic-only outer60-second deadline reached. Normal chat deadline unchanged.','text':''.join(parts)}
   except Exception as exc:result={'ok':False,'status':'error','message':type(exc).__name__+': '+str(exc),'text':''.join(parts)}
  finally:
   await c.close();asyncio.create_subprocess_exec=original_launch
  warnings='\n'.join(str(row.get('public_error_fields',{})) for row in events)
  args=[arg for call in invocations for arg in call['argv']]
  metadata.update(completed_utc=datetime.now(timezone.utc).isoformat(),seconds=time.monotonic()-started,result=result,
   stream_equals_final=''.join(parts)==result.get('text'),native_event_metadata=events,subprocess_invocations=invocations,
   actual_view_image_feature_disabled='features.view_image=false' in args,
   legacy_view_image_setting_present=any('tools.view_image=' in str(arg) for arg in args),
   explicit_image_argument_present='--image' in args,ignored_view_image_warning_present='tools.view_image' in warnings,
   closed=True,codex_children_remaining=len(c.codex._procs),claude_children_remaining=len(c.procs),local_client_created=c._local is not None)
 with DEST.open('x') as f:json.dump(metadata,f,ensure_ascii=False,indent=2)
 print(json.dumps({'ok':metadata['result'].get('ok'),'text':metadata['result'].get('text'),'seconds':metadata['seconds'],
  'feature_disabled':metadata['actual_view_image_feature_disabled'],'explicit_image':metadata['explicit_image_argument_present'],
  'ignored_warning':metadata['ignored_view_image_warning_present'],'public_warnings':[e.get('public_error_fields') for e in events if e.get('public_error_fields')]},ensure_ascii=False),flush=True)

asyncio.run(main())
