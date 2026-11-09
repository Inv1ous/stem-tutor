"""Topical short answers distinguish self marking from trusted automatic verdicts."""
import asyncio

import pytest

from test_topical_setup import staged_app
from test_topicals import TARGET, item, publish
from tutor_app.ai import Result
from tutor_app.panels import TickPanel
from tutor_app.screens import SessionScreen
from tutorlib.session import Tutor
from tutorlib.store import Vault


@pytest.mark.parametrize('automatic,verdict', [
    (False, 'valid'), (True, 'valid'), (True, 'invalid'),
    (True, 'failed_result'), (True, 'exception'),
])
def test_topical_short_only_successful_exact_points_grade_once(
        tmp_path, monkeypatch, automatic, verdict):
    app, root = staged_app(tmp_path, monkeypatch)
    app.settings.ai_mark_model = 'codex:gpt-6.1-terra'
    points = ['First synthetic reason.', 'Second synthetic reason.']
    source = item(id='short-auto-route', kind='short', marks=2,
                  stem='Explain two reasons.',
                  rubric=[{'point': p, 'keywords': [['synthetic']]} for p in points])
    source.pop('options')
    source.pop('answer')
    source['topical'].update(requires=[TARGET], support={})
    publish(root, [source], version='short-auto')
    calls = []
    working = 'My original explanation in full.'

    async def marker(prompt, **kwargs):
        calls.append((prompt, kwargs))
        if verdict == 'exception':
            raise RuntimeError('Scripted provider failure')
        rows = [{'point': p, 'met': i == 0} for i, p in enumerate(points)]
        if verdict == 'invalid':
            rows[0]['point'] = 'Wrong point identity'
        return {'points': rows, 'feedback': 'Scripted verdict.'}, Result(
            ok=verdict != 'failed_result', message='Scripted provider failure')

    async def go():
        async with app.run_test(size=(80, 24)) as pilot:
            app.tutor.start('topical', focus=[TARGET], topical_count=1,
                            topical_types=['written'], topical_auto_mark=automatic)
            screen = SessionScreen(None)
            await app.push_screen(screen)
            await pilot.pause()
            assert screen.view['kind'] == 'short'
            n = screen.view['n']
            monkeypatch.setattr(app, 'ai_available', lambda mode: True)
            monkeypatch.setattr(app.ai, 'one_shot', marker)
            screen.submit({'entry': f'{n} = {working}', 'your': working})
            await app.workers.wait_for_complete()
            await pilot.pause()
            answers = [e for e in app.tutor.vault.events() if e['type'] == 'answer']
            assert len(calls) == int(automatic)
            if automatic and verdict == 'valid':
                assert len(answers) == 1 and answers[0]['grade']['score'] == .5
                assert screen.pending_short is None
                assert not screen.query('#panel > TickPanel')
                assert screen.last_fb['your'] == working
                assert working in calls[0][0]
                assert calls[0][1]['model'] == 'codex:gpt-6.1-terra'
            else:
                assert not answers
                assert screen.query_one('#panel > *', TickPanel)
                assert screen.pending_short[1]['your'] == working
                assert app.tutor.session['presented'][str(n)]['saved_work'] == working
                restored = Tutor(Vault(root))
                assert restored.session['presented'][str(n)]['saved_work'] == working
            assert not app.tutor._marking_tickets
            await app.ai.close()
    asyncio.run(go())
