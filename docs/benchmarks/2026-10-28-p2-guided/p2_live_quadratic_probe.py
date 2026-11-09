import asyncio,json,shutil,tempfile,time
from pathlib import Path
from fixtures import make_vault
from test_tui import FAKE
from test_p2_guided_pilot import corrected_draft_pack
from tutor_app.app import TutorApp
from tutor_app.screens import SessionScreen
ROOT=Path.cwd()
async def run():
 with tempfile.TemporaryDirectory(prefix='p2-live-screen-') as temp:
  vault=make_vault(Path(temp)); base=vault/'.tutor/packs/v1'; manifest=json.loads((base/'manifest.json').read_text()); manifest['specs'].append('P2'); (base/'manifest.json').write_text(json.dumps(manifest))
  dest=base/'specs/P2'; (dest/'packs').mkdir(parents=True); shutil.copy(ROOT/'build/out/specs/P2/graph.json',dest/'graph.json'); (dest/'packs/P2-1.json').write_text(json.dumps(corrected_draft_pack()))
  app=TutorApp(vault,claude_binary=FAKE,open_obsidian=False,seed=1); app.settings.ai_learn_model='ollama:qwen3.5:4b'; app.settings.ai_learn_think=False
  async with app.run_test(size=(100,30)) as pilot:
   app.push_screen(SessionScreen({'mode':'lesson','minutes':40,'focus':['P2-1']})); await pilot.pause(); screen,tutor=app.screen,app.tutor
   for _ in range(30):
    act=screen.act
    if act.get('part')=='plain_words': break
    if act['activity']=='choose': tutor.respond({'choice':'scratch'})
    elif act['activity']=='plan': tutor.respond({'teach':act['default_teach']})
    elif act['activity']=='questions':
     q=act['items'][0]; answer=tutor.session['presented'][str(q['n'])]['inst']['answer']; tutor.answer(f"{q['n']}{answer}3")
    elif act['activity']=='explain': tutor.respond({})
    else: raise AssertionError(act)
    screen.advance(); await pilot.pause()
   assert screen.kc=='P2-1.1' and screen.act.get('part')=='plain_words'
   questions=['How do I prove a cubic curve has no turning points using its quadratic gradient?', 'Show example for form 24']
   for q in questions:
    started=time.monotonic(); await screen.learn_request(q).wait(); await pilot.pause()
    print('QUESTION:',q,'ELAPSED:',round(time.monotonic()-started,2)); print('NOW:',(vault/'Now.md').read_text()[-4500:]); print('DISCLOSED:',tutor.session.get('disclosed_item_ids'))
   await app.ai.close()
asyncio.run(run())
