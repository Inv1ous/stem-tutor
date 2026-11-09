import asyncio, json, time
from pathlib import Path
from tutor_app import prompts, ai
from tutor_app.tutor_ai import TutorAI
form=json.loads(Path('build/work/guided/P2-1-quadratic-gradient-form.json').read_text())
points=[r['point'] for r in form['rubric']]
cases={'square':'3x² − 6x + 4 = 3(x − 1)² + 1 > 0 for every real x. The derivative never vanishes, so there are no turning points.', 'discriminant':'The derivative quadratic has discriminant 36 − 48 = −12 < 0, so it has no real roots. The derivative never vanishes; hence there are no turning points.', 'monotonic':'y = (x − 1)³ + x + 1, which is strictly increasing on the real line as both terms are strictly increasing. Thus it has no turning points.', 'incorrect':'The derivative is a quadratic and has no turning points because its discriminant is 12.'}
async def run():
 client=TutorAI(Path('/tmp'),binary='/bin/false')
 out={}
 for name,answer in cases.items():
  start=time.monotonic(); result,status=await client.one_shot(prompts.judge(form['check'],points,answer),schema=prompts.local_judge_schema(points),model='ollama:qwen3.5:4b',think=False,timeout=90)
  out[name]={'answer':answer,'response':result,'ok':status.ok,'message':status.message,'elapsed':round(time.monotonic()-start,2),'matches_points':ai.matches_points(result,points)}
  print(name,json.dumps(out[name],ensure_ascii=False),flush=True)
 await client.close()
 Path('/tmp/p2-mark-probe.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))
asyncio.run(run())
