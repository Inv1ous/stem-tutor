"""Prepared visual lessons and contextual tutor controls in disposable vaults."""
import asyncio

import pytest
from textual.widgets import Button

from library_assets import install_course
from test_tui import app_for
from tutor_app.screens import SessionScreen
from tutor_app.panels import Composer
from tutor_app.ai import Result
from tutorlib.library_refs import LibraryRefs


@pytest.mark.parametrize('size', [(60, 24), (100, 30)])
def test_prepared_lesson_shows_real_diagram_and_visible_learning_tutor(tmp_path, monkeypatch, size):
    app, vault = app_for(tmp_path, monkeypatch)
    pack = install_course(vault, '9701', '9701-1.4')
    diagram = pack['diagrams'][0]['file']

    async def run():
        async with app.run_test(size=size) as pilot:
            app.push_screen(SessionScreen({'mode': 'lesson', 'minutes': 30, 'focus': ['9701-1.4']}))
            await pilot.pause()
            screen = app.screen
            app.tutor.session.update(presented={}, queue={})
            act = {'activity': 'explain', 'title': 'Read the trend', 'text': 'Compare Mg with Al.',
                   'kc': '9701-1.4.3', 'part': 'plain_words', 'diagram': diagram,
                   'diagram_description': 'The first ionisation energy falls from magnesium to aluminium.'}
            def next_activity():
                result = app.tutor._await(act)
                app.tutor._save()
                return result
            monkeypatch.setattr(app.tutor, 'next', next_activity)
            screen.advance()
            await pilot.pause()
            assert screen.query('.lesson-figure'), 'The actual Library diagram should appear beside the explanation.'
            button = screen.query_one('#learn', Button)
            assert button.region.height > 0 and button.region.bottom <= size[1]
            assert screen.query_one('#learning-question', Composer).region.bottom <= size[1]
            assert screen.query_one('#log').region.height >= 5
            assert LibraryRefs(vault).reference(diagram) in (vault / 'Now.md').read_text()
            button.press()
            await pilot.pause()
            assert app.screen is screen
            assert screen.query_one('#learning-question', Composer).has_focus
            assert app.tutor.session.get('awaiting') is act
            await app.ai.close()
    asyncio.run(run())


def test_inline_tutor_remembers_followups_and_goal_without_advancing(tmp_path, monkeypatch):
    app, vault = app_for(tmp_path, monkeypatch)
    calls = []

    async def answer(prompt, **kwargs):
        calls.append(prompt)
        return {'actions': [{'action': 'explain', 'section': 'establish'}]}, Result()

    async def run():
        async with app.run_test(size=(100, 30)) as pilot:
            app.push_screen(SessionScreen({'mode': 'lesson', 'minutes': 30, 'focus': ['9702-2.1']}))
            await pilot.pause()
            screen, tutor = app.screen, app.tutor
            kc = '9702-2.1.1'
            tutor.packs.pack_for_kc(kc)['teach'] = {kc: {'motivate': 'Why motion matters.',
                'establish': 'Displacement compares the start and finish.', 'note': '- Displacement is a vector.'}}
            tutor.session.update(presented={}, queue={}, goal='scratch')
            act = {'activity': 'explain', 'title': 'Displacement', 'text': 'Compare start and finish.',
                   'detail': 'An expanded explanation.', 'kc': kc, 'part': 'establish'}
            monkeypatch.setattr(tutor, 'next', lambda: tutor._await(act))
            screen.advance()
            await pilot.pause()
            monkeypatch.setattr(app, 'ai_available', lambda mode: True)
            monkeypatch.setattr(app.ai, 'one_shot', answer)
            assert screen.query('#learning-question'), 'Follow-up questions belong beside the current lesson.'
            composer = screen.query_one('#learning-question', Composer)
            composer.focus()
            composer.text = 'I am confused about distance.'
            await pilot.resize_terminal(60, 24)
            await pilot.pause()
            composer = screen.query_one('#learning-question', Composer)
            assert composer.text == 'I am confused about distance.'
            assert composer.has_focus
            screen.query_one('#detail', Button).press()
            await pilot.pause()
            composer = screen.query_one('#learning-question', Composer)
            assert composer.text == 'I am confused about distance.'
            composer.focus()
            await pilot.press('enter')
            await pilot.pause()
            await app.workers.wait_for_complete()
            await screen.learn_request('How does that connect to displacement?').wait()
            assert len(calls) == 2
            assert 'I am confused about distance.' in calls[1]
            assert 'Learn it properly from scratch' in calls[1]
            assert tutor.session['awaiting'] is act
            assert not tutor.session.get('presented')
            assert len(tutor.session['learn_history'][kc]) == 2
            assert screen.query('#learning-question')
            await app.ai.close()
    asyncio.run(run())


def test_skipped_answer_never_gets_an_inline_diagram(tmp_path, monkeypatch):
    app, vault = app_for(tmp_path, monkeypatch)
    pack = install_course(vault, '9701', '9701-1.4')

    async def run():
        async with app.run_test(size=(100, 30)) as pilot:
            app.push_screen(SessionScreen({'mode': 'lesson', 'minutes': 30, 'focus': ['9701-1.4']}))
            await pilot.pause()
            app.tutor.session.update(presented={}, queue={}, skipped_answer_guards={'held': {'key': '14', 'kind': 'numeric'}})
            act = {'activity': 'explain', 'title': 'Protected', 'text': 'Continue after retrying.',
                   'kc': '9701-1.4.3', 'part': 'plain_words', 'diagram': pack['diagrams'][0]['file']}
            monkeypatch.setattr(app.tutor, 'next', lambda: app.tutor._await(act))
            app.screen.advance()
            await pilot.pause()
            assert not app.screen.query('.lesson-figure')
            assert pack['diagrams'][0]['file'] not in (vault / 'Now.md').read_text()
            await app.ai.close()
    asyncio.run(run())
