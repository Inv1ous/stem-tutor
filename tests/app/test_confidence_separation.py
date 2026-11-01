"""Confidence selection stays outside submitted wording and examiner prompts."""
import asyncio
from types import SimpleNamespace

import pytest

from tutor_app import ai, panels, prompts
from tutor_app.screens import SessionScreen
from tutorlib import grade
from test_tui import app_for

ANSWER = 'Held together with van der waals forces between a lattice of molecules.'


@pytest.mark.parametrize('confidence', [1, 2, 3, 4])
@pytest.mark.parametrize('kind', ['choice', 'short', 'expression', 'numeric'])
def test_picker_preserves_answer_and_records_confidence_separately(confidence, kind):
    panel = panels.ChoicePanel(1, {'A':'one'}) if kind == 'choice' else panels.ValuePanel(1, kind)
    raw = 'A' if kind == 'choice' else ANSWER + ' (guess)'
    if kind == 'choice': panel.choice = raw
    else: panel.value = raw
    result = []
    panel.finish = result.append
    if kind == 'choice': panel._note = lambda: ''
    panel._conf(SimpleNamespace(option=SimpleNamespace(id=str(confidence))))
    data = result[0]
    assert data['your'] == raw  # never strip words the learner actually typed
    parsed = grade.parse_responses(data['entry'])[0]
    assert parsed['conf'] == confidence


def test_confidence_is_not_sent_as_answer_text_to_examiner(tmp_path, monkeypatch):
    app, vault = app_for(tmp_path, monkeypatch)
    captured = []
    async def go():
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            t = app.tutor
            t.start('review', minutes=10)
            point = 'A simple molecular lattice held by relatively weak intermolecular forces.'
            item = {'id':'confidence-short','kcs':['9702-2.1.1'],'kind':'short','difficulty':3,'marks':1,
                    'stem':'Describe the structure.', 'rubric':[{'point':point,'keywords':[['molecules']]}]}
            n=t._present(item, block='practice', phase=None)['n']
            async def examiner(prompt, **kwargs):
                captured.append(prompt)
                return {'points':[{'point':point,'met':True,'why':'Molecules and intermolecular forces stated.'}],
                        'feedback':'This earns the mark.'}, ai.Result()
            monkeypatch.setattr(app.ai,'one_shot',examiner)
            await app.push_screen(SessionScreen(None)); await pilot.pause()
            app.screen.query_one('#value', panels.Composer).load_text(ANSWER)
            await pilot.press('enter'); await pilot.pause(); await pilot.press('1')
            await app.workers.wait_for_complete(); await pilot.pause()
            assert len(captured)==1 and f'STUDENT ANSWER: {ANSWER}\n' in captured[0]
            event=[e for e in t.vault.events() if e['type']=='answer'][-1]
            assert event['response']==ANSWER and event['conf']==1
            recent=t.session['recent'][-1]
            assert recent['conf']==1 and recent['response']==ANSWER
            for path in (vault/'Now.md',vault/t.session['log']):
                text=path.read_text()
                assert f'**Your answer:** {ANSWER}' in text
                assert '**Confidence:** Guess (1/4)' in text
                assert ANSWER+' (guess)' not in text
            assert 'Self-rated confidence: Guess (1/4)' in prompts._marked(recent)
            await app.ai.close()
    asyncio.run(go())
