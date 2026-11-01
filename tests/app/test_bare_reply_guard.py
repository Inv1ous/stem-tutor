"""Bare answers must be withheld from the display, transcript and speech before an attempt."""
import asyncio
import os

import pytest

from test_tui import app_for
from tutor_app.ai import Result
from tutor_app.screens import SessionScreen


@pytest.mark.parametrize('kind,answer,key', [('mcq','6','6'), ('mcq','NO₂','NO₂'), ('short','energy','energy'),
                                             ('expression','x','x'), ('expression','1−x','1-x'),
                                             ('mcq',r'NO_2','NO₂'), ('mcq',r'$\mathrm{NO_2}$','NO₂'),
                                             ('expression',r'\pi','π'), ('expression',r'\frac{1}{2}','1/2'),
                                             ('numeric','Consider 10^999; the result is 3 m.','3 m')])
@pytest.mark.parametrize('speech_only', [False,True])
def test_bare_correct_answer_is_withheld_in_real_stream(tmp_path,monkeypatch,kind,answer,key,speech_only):
    app,vault=app_for(tmp_path,monkeypatch)
    async def run():
        async with app.run_test(size=(60,24)) as pilot:
            await pilot.pause()
            tutor=app.tutor; tutor.start('review',minutes=10)
            item={'id':'bare-answer-guard','kcs':['9702-2.1.1'],'kind':kind,'difficulty':2,'marks':1,'stem':'Give the requested answer.'}
            if kind=='mcq': item.update(options={'A':'another value','B':key},answer='B')
            elif kind=='short': item['rubric']=[{'point':key,'keywords':[[key]]}]
            elif kind=='numeric': item['answer']={'value':3,'unit':'m','sf':1}
            else: item['answer']={'expr':key,'variables':['x']}
            n=tutor._present(item,block='practice',phase=None)['n']
            screen=SessionScreen(None); await app.push_screen(screen); await pilot.pause()
            async def stream(*args,**kwargs):
                text='Think about the definition.' if speech_only else answer
                app.ai.last=Result(text=text,speech=answer if speech_only else '')
                yield text
            monkeypatch.setattr(app.ai,'stream',stream)
            spoken=[]; monkeypatch.setattr(screen,'readable_now',lambda text,**kwargs: spoken.append(text))
            await screen._stream('Give me a hint.',False).wait(); await pilot.pause()
            for file in (vault/'Now.md',vault/tutor.session['log']):
                assert "I can't give that away while the question is open" in file.read_text()
            assert str(n) in tutor.session['presented']
            assert all(text!=answer for text in spoken)
            assert not tutor.session['presented'][str(n)]['hinted']
            if os.environ.get('BUGPASS_SCREENSHOTS') and kind=='mcq' and answer=='6' and not speech_only:
                app.save_screenshot(path=os.environ['BUGPASS_SCREENSHOTS'],filename='02-answer-protection-60.svg')
            await app.ai.close()
    asyncio.run(run())
