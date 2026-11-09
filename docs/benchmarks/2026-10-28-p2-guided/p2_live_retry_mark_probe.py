import asyncio,json,time
from pathlib import Path
from tutor_app import prompts,ai
from tutor_app.tutor_ai import TutorAI
cards=json.loads(Path('build/work/teach/P2-1.json').read_text())
forms={name:next(f for f in cards[kc]['forms'] if f['name']==name)['retry'] for kc,name in [('P2-1.1','Geometric-series proof by cancellation'),('P2-1.3','Counterexample after widening the domain')]}
cases=[('formula_verify','Geometric-series proof by cancellation','Using the formula, S4=(4⁴−1)/3=85. Every later term is positive, so partial sums strictly increase and no other positive integer term count gives 85.'),('formula_incomplete','Geometric-series proof by cancellation','S4=(4⁴−1)/3=85.'),('equal_positive','Counterexample after widening the domain','Choose x=1 and y=1. Both are positive reals, but x−y=0, which is not positive.'),('outside_domain','Counterexample after widening the domain','Choose x=−1 and y=2. Then x−y=−3, which is negative.')]
async def run():
 client=TutorAI(Path('/tmp'),binary='/bin/false');out=[]
 for name,formname,answer in cases:
  f=forms[formname];points=[r['point'] for r in f['rubric']];started=time.monotonic()
  result,status=await client.one_shot(prompts.judge(f['check'],points,answer),schema=prompts.local_judge_schema(points),model='ollama:qwen3.5:4b',think=False,timeout=90)
  row={'case':name,'answer':answer,'response':result,'ok':status.ok,'elapsed':round(time.monotonic()-started,2),'matches_points':ai.matches_points(result,points)};out.append(row);print(json.dumps(row,ensure_ascii=False),flush=True)
 await client.close();Path('/tmp/p2-retry-mark-probe.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))
asyncio.run(run())
