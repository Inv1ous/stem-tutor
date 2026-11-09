"""Lesson inputs acknowledge processing without altering lesson or learner records."""
import asyncio
import os
from pathlib import Path

import library_assets
import pytest

from test_tui import app_for
from test_lesson_detail_selection import open_detail
from tutor_app import learn_reply, look
from tutor_app.ai import Result
from tutor_app.panels import Composer, ContinuePanel
from textual.widgets import Button
from textual.worker import WorkerCancelled



@pytest.mark.parametrize('model,size', [('codex:gpt-6.1-terra', (80, 24)), ('sonnet', (60, 24)),
                                        ('ollama:gemma4:e4b', (100, 30))])
@pytest.mark.parametrize('answer_only', [False, True])
def test_lesson_request_shows_processing_and_blocks_repeated_input(tmp_path, monkeypatch, model, size, answer_only):
    monkeypatch.setenv("TERM", "xterm-256color")
    monkeypatch.setenv("COLORTERM", "truecolor")
    app, vault = app_for(tmp_path, monkeypatch)
    library_assets.install_course(vault, "9701", "9701-1.4")
    app.settings.ai = False
    app.settings.ai_learn_model = model
    app.settings.theme = ('day' if model == 'sonnet' else 'night' if model.startswith('ollama:') else 'classic')
    look.use(app.settings.theme)
    app.settings.answer_only = answer_only

    async def go():
        ready, release = asyncio.Event(), asyncio.Event()
        calls = []
        async with app.run_test(size=size) as pilot:
            screen = await open_detail(pilot, app)
            monkeypatch.setattr(learn_reply, 'published_related_cards',
                                lambda tutor, kc: {kc: {'plain_words': 'Start from the assumptions.'}})
            monkeypatch.setattr(app, 'ai_available', lambda mode: True)
            async def slow(prompt, **kwargs):
                calls.append(kwargs)
                ready.set()
                await release.wait()
                return {'sections': [f'{screen.kc}|plain_words']}, Result()
            monkeypatch.setattr(app.ai, 'one_shot', slow)
            box = screen.query_one('#learning-question', Composer)
            box.text = 'How should I start?'
            box.focus()
            await pilot.press('enter')
            await asyncio.wait_for(ready.wait(), 3)
            await pilot.pause()
            evidence = Path(os.environ.get('LESSON_FEEDBACK_SHOTS', str(tmp_path)))
            evidence.mkdir(parents=True, exist_ok=True)
            app.save_screenshot(f"{model.replace(':', '-')}-{size[0]}-{'answer-only' if answer_only else 'full'}-pending.svg", path=str(evidence))
            try:
                status = screen.query_one('#lesson-progress')
                assert status.display and status.region.height > 0
                assert all(button.disabled for button in screen.query('#panel Button'))
                box.text = 'Keep this next question as a draft'
                await pilot.press('enter')
                await pilot.pause()
                assert len(calls) == 1 and box.text == 'Keep this next question as a draft'
                assert 'elapsed' not in (vault / 'Now.md').read_text()
                await pilot.resize_terminal(100, 40)
                await pilot.pause()
                box = screen.query_one('#learning-question', Composer)
                assert box.text == 'Keep this next question as a draft'
                assert all(button.disabled for button in screen.query('#panel Button'))
            finally:
                release.set()
                await app.workers.wait_for_complete()
            await pilot.pause()
            assert not screen.query_one('#lesson-progress').display
            assert all(not button.disabled for button in screen.query('#panel Button'))
            assert 'Start from the assumptions.' in (vault / 'Now.md').read_text()
            await app.ai.close()
    asyncio.run(go())


@pytest.mark.parametrize('finish', ['cancel', 'failure', 'leave'])
def test_processing_releases_controls_after_cancel_failure_or_leave(tmp_path, monkeypatch, finish):
    app, vault = app_for(tmp_path, monkeypatch)
    library_assets.install_course(vault, '9701', '9701-1.4')
    app.settings.ai = False

    async def go():
        ready, release = asyncio.Event(), asyncio.Event()
        async with app.run_test(size=(80, 24)) as pilot:
            screen = await open_detail(pilot, app)
            monkeypatch.setattr(learn_reply, 'published_related_cards',
                                lambda tutor, kc: {kc: {'plain_words': 'A prepared explanation.'}})
            monkeypatch.setattr(app, 'ai_available', lambda mode: True)
            async def slow(*args, **kwargs):
                ready.set()
                await release.wait()
                return None, Result(ok=False, message='Test examiner unavailable')
            monkeypatch.setattr(app.ai, 'one_shot', slow)
            before = list(app.tutor.vault.events())
            worker = screen.learn_request('How should I start?')
            await asyncio.wait_for(ready.wait(), 3)
            await pilot.pause()
            status = screen.query_one('#lesson-progress')
            assert status.display
            if finish == 'cancel':
                worker.cancel()
            elif finish == 'leave':
                await pilot.press('ctrl+b')
            else:
                release.set()
            if finish in ('cancel', 'leave'):
                with pytest.raises(WorkerCancelled):
                    await worker.wait()
            else:
                await worker.wait()
            await pilot.pause()
            assert not status.display
            assert all(not button.disabled for button in screen.query('#panel Button'))
            assert list(app.tutor.vault.events()) == before
            assert not getattr(screen.showing, 'processing', None)
            await app.ai.close()
    asyncio.run(go())


def test_prepared_action_paints_acknowledgement_before_applying_once(tmp_path, monkeypatch):
    from tutor_app.panels import Panel
    app, vault = app_for(tmp_path, monkeypatch)
    library_assets.install_course(vault, '9701', '9701-1.4')
    app.settings.ai = False

    async def go():
        async with app.run_test(size=(80, 24)) as pilot:
            screen = await open_detail(pilot, app)
            panel = screen.showing
            applied = []
            original = screen._apply_panel_done
            def apply(event):
                status = screen.query_one('#lesson-progress')
                assert status.display and status.region.height > 0
                applied.append(event.data)
                original(event)
            monkeypatch.setattr(screen, '_apply_panel_done', apply)
            event = Panel.Done({'button': 'detail'}, panel)
            screen.panel_done(event)
            assert screen.query_one('#lesson-progress').display and not applied
            screen.panel_done(Panel.Done({'button': 'detail'}, panel))
            await pilot.pause()
            assert applied == [{'button': 'detail'}]
            assert not screen.query_one('#lesson-progress').display
            await app.ai.close()
    asyncio.run(go())


def test_lesson_start_paints_preparation_before_starting_engine(tmp_path, monkeypatch):
    from tutor_app.screens import SessionScreen
    app, vault = app_for(tmp_path, monkeypatch)
    library_assets.install_course(vault, '9701', '9701-1.4')
    app.settings.ai = False
    seen = []

    async def go():
        async with app.run_test(size=(80, 24)) as pilot:
            original = app.tutor.start
            def start(*args, **kwargs):
                status = app.screen.query_one('#lesson-progress')
                assert status.display and status.region.height > 0
                seen.append(True)
                return original(*args, **kwargs)
            monkeypatch.setattr(app.tutor, 'start', start)
            screen = SessionScreen({'mode': 'lesson', 'minutes': 10, 'focus': ['9701-1.4']})
            await app.push_screen(screen)
            await pilot.pause()
            assert seen == [True]
            assert not screen.query_one('#lesson-progress').display
            await app.ai.close()
    asyncio.run(go())


@pytest.mark.parametrize('operation', ['stream', 'judge', 'long', 'remark'])
def test_cloud_lesson_workers_keep_activity_until_result_in_answer_only(tmp_path, monkeypatch, operation):
    app, vault = app_for(tmp_path, monkeypatch)
    library_assets.install_course(vault, '9701', '9701-1.4')
    app.settings.ai = False
    app.settings.answer_only = True
    app.settings.ai_mark_model = app.settings.ai_ask_model = 'codex:gpt-6.1-terra'

    async def go():
        ready, release = asyncio.Event(), asyncio.Event()
        calls = []
        async with app.run_test(size=(80, 24)) as pilot:
            screen = await open_detail(pilot, app)
            monkeypatch.setattr(app, 'ai_available', lambda mode: True)
            async def delayed(*args, **kwargs):
                ready.set()
                await release.wait()
                return None, Result(ok=False, message='Test request stopped')
            async def streamed(*args, **kwargs):
                calls.append(True)
                ready.set()
                await release.wait()
                app.ai.last = Result(ok=False, message='Test request stopped')
                if False:
                    yield ''
            monkeypatch.setattr(app.ai, 'one_shot', delayed)
            monkeypatch.setattr(app.ai, 'stream', streamed)
            if operation == 'stream':
                screen.panel(ContinuePanel('Reading your explanation…', buttons=[]))
                worker = screen._stream('Give feedback on my explanation', False)
            else:
                item = {'id': 'lesson-worker', 'kcs': [screen.kc], 'kind': 'short', 'difficulty': 3,
                        'marks': 1, 'stem': 'Explain.', 'review_answer': 'A reason.',
                        'rubric': [{'point': 'Reason', 'keywords': [['reason']]}]}
                view = app.tutor._present(item, block='practice', phase='form_check')
                screen.view = view
                if operation == 'judge':
                    data = {'entry': f"{view['n']} = My reason", 'your': 'My reason'}
                    screen.pending_short = (view['n'], data, 1)
                    worker = screen.judge_short(view, data, {'rubric': ['Reason']})
                elif operation == 'long':
                    screen.scheme = [{'i': 1, 'mark': 'B1', 'point': 'Reason'}]
                    screen.long_text = 'My reason'
                    worker = screen.ai_check_long({'ticked': []})
                else:
                    screen.last_fb = {'event': 'fixture-event', 'correct': False}
                    screen.followups = []
                    worker = screen.remark()
            await asyncio.wait_for(ready.wait(), 3)
            await pilot.pause()
            try:
                assert not screen.query_one('#log').display
                assert screen.query_one('#lesson-progress').display
                assert screen.query_one('#lesson-progress').region.height > 0
                if operation == 'stream':
                    await pilot.press('ctrl+r')
                    await pilot.pause()
                    assert calls == [True]
                    await pilot.press('ctrl+t')
                    assert app.screen is screen
            finally:
                release.set()
                await worker.wait()
            await pilot.pause()
            assert not screen.query_one('#lesson-progress').display
            await app.ai.close()
    asyncio.run(go())


def test_activity_replacement_keeps_new_owner_and_original_disabled_states(tmp_path, monkeypatch):
    from textual.document._document import Selection
    from tutor_app.screens import LessonActivity
    app, vault = app_for(tmp_path, monkeypatch)
    library_assets.install_course(vault, '9701', '9701-1.4')
    app.settings.ai = False

    async def go():
        async with app.run_test(size=(80, 24)) as pilot:
            screen = await open_detail(pilot, app)
            button = screen.query_one('#continue', Button)
            button.disabled = True
            box = screen.query_one('#learning-question', Composer)
            box.text = 'Keep this draft and selection'
            box.selection = Selection((0, 12), (0, 5))
            selected = box.selection
            old = LessonActivity(screen, 'First request')
            old.__enter__()
            newer = LessonActivity(screen, 'Second request', 'ollama:gemma4:e4b')
            newer.__enter__()
            state = {'phase': 'thinking', 'started': 0}
            monkeypatch.setattr(app.ai, 'progress_for', lambda model: state)
            newer.set_task('Writing an explanation…')
            status = screen.query_one('#lesson-progress')
            assert 'Writing an explanation' in str(status.content.text)
            assert 'Thinking' not in str(status.content.text)
            state['started'] = newer.started
            newer.draw()
            assert 'Thinking' in str(status.content.text)
            old.__exit__(None, None, None)
            assert status.display and screen._lesson_activity is newer
            assert all(b.disabled for b in screen.query('#panel Button'))
            newer.__exit__(None, None, None)
            assert not status.display and button.disabled
            assert all(not b.disabled for b in screen.query('#panel Button') if b is not button)
            assert box.text == 'Keep this draft and selection' and box.selection == selected
            await app.ai.close()
    asyncio.run(go())
