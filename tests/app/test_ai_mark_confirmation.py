"""Optional lesson-review confirmation uses the normal AI marking and save paths."""
import asyncio
import json

import pytest
from textual.widgets import Button, Switch

from test_tui import app_for
from tutor_app.ai import Result
from tutor_app.config import Settings
from tutor_app.panels import TickPanel
from tutor_app.screens import SessionScreen


@pytest.mark.parametrize('saved,want', [({}, True), ({'confirm_ai_marks': False}, False),
                                       ({'confirm_ai_marks': True}, True),
                                       ({'confirm_ai_marks': 'false'}, True)])
def test_confirmation_settings_preserve_old_defaults_and_saved_boolean(tmp_path, saved, want):
    folder = tmp_path / '.tutor'
    folder.mkdir()
    (folder / 'app_settings.json').write_text(json.dumps(saved))
    assert Settings.load(tmp_path).confirm_ai_marks is want


@pytest.mark.parametrize('initial,save', [(True, True), (False, True), (True, False)])
def test_confirmation_switch_saves_or_cancels(tmp_path, monkeypatch, initial, save):
    app, vault = app_for(tmp_path, monkeypatch)
    app.settings.confirm_ai_marks = initial
    app.settings.save(vault)

    async def go():
        async with app.run_test(size=(80, 24)) as pilot:
            app.action_settings()
            await pilot.pause()
            switch = app.screen.query_one('#confirm_ai_marks', Switch)
            assert switch.value is initial
            switch.focus()
            await pilot.press('space')
            assert switch.value is not initial
            if save:
                app.screen.query_one('#save', Button).press()
            else:
                await pilot.press('escape')
            await pilot.pause()
            await app.workers.wait_for_complete()
            expected = not initial if save else initial
            assert app.settings.confirm_ai_marks is expected
            assert Settings.load(vault).confirm_ai_marks is expected
            await app.ai.close()
    asyncio.run(go())


@pytest.mark.parametrize('phase,written_faded', [('form_check', False), ('term_review', False),
                                                ('faded', False), ('practice', True)])
@pytest.mark.parametrize('examiner_state', ['valid', 'invalid', 'unavailable'])
def test_disabled_confirmation_applies_valid_ai_marks_and_keeps_manual_fallback(
        tmp_path, monkeypatch, phase, written_faded, examiner_state):
    app, vault = app_for(tmp_path, monkeypatch)
    app.settings.confirm_ai_marks = False
    app.settings.ai_mark_model = 'codex:gpt-6.1-terra'
    calls = []
    points = ['First reason', 'Second reason']

    async def examiner(*args, **kwargs):
        calls.append(kwargs['model'])
        if examiner_state == 'invalid':
            return {}, Result(ok=False, message='Incomplete reply')
        return {'points': [{'point': p, 'met': i == 0} for i, p in enumerate(points)],
                'feedback': 'One reason earned.'}, Result()

    async def go():
        async with app.run_test(size=(80, 24)) as pilot:
            tutor = app.tutor
            tutor.start('review', minutes=10)
            item = {'id': 'optional-confirmation', 'kcs': ['9702-2.1.1'], 'kind': 'short',
                    'difficulty': 3, 'marks': 2, 'stem': 'Explain two reasons.',
                    'review_answer': 'Example explanation.', 'written_faded': written_faded,
                    'rubric': [{'point': p, 'keywords': [[p]]} for p in points]}
            view = tutor._present(item, block='practice', phase=phase)
            data = {'entry': f"{view['n']} = my reason", 'your': 'my reason'}
            if phase == 'faded' or written_faded:
                assert tutor.answer(data['entry'])['results'][0]['attempt_confirmation_required']
                assert tutor.confirm_faded_attempt(view['n'], data['your'])['ok']
            screen = SessionScreen(None)
            await app.push_screen(screen)
            await pilot.pause()
            monkeypatch.setattr(app, 'ai_available', lambda mode: examiner_state != 'unavailable')
            monkeypatch.setattr(app.ai, 'one_shot', examiner)
            screen.pending_short = (view['n'], data, 2)
            await screen.judge_short(view, data, {'rubric': points}).wait()
            await pilot.pause()
            answers = [e for e in tutor.vault.events() if e['type'] == 'answer']
            if examiner_state == 'valid':
                assert len(answers) == 1
                assert answers[0]['grade']['score'] == 0.5
                assert screen.pending_short is None and screen.last_fb['written']
                assert not screen.query('#panel > TickPanel')
                assert '✓ First reason' in tutor.session['recent'][-1]['explanation']
                assert '✗ Second reason' in tutor.session['recent'][-1]['explanation']
            else:
                assert not answers
                assert screen.query_one('#panel > *', TickPanel)
            assert calls == ([] if examiner_state == 'unavailable' else ['codex:gpt-6.1-terra'])
            assert 'my reason' in (vault / 'Now.md').read_text()
            await app.ai.close()
    asyncio.run(go())
