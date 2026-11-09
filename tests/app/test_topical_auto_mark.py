"""Topical marking choices are session-local and AI verdicts require owned, complete inputs."""
import asyncio
from copy import deepcopy
import json

import pytest
from textual.widgets import Button, Select
from textual.worker import WorkerCancelled

from test_topical_setup import staged_app
from test_topicals import TARGET
from tutor_app import ai
from tutor_app.panels import TickPanel
from tutor_app.screens import SessionScreen, TopicalSetupScreen
from tutorlib.asset_library import write_asset


def test_topical_marking_choice_is_remembered_for_next_time_and_survives_topic_changes_and_resume(tmp_path, monkeypatch):
    app, vault = staged_app(tmp_path, monkeypatch)
    app.settings.save(vault)

    async def go():
        async with app.run_test(size=(60, 20)) as pilot:
            result = []
            setup = TopicalSetupScreen([TARGET])
            await app.push_screen(setup, result.append)
            await pilot.pause()
            assert setup.query_one('#topical-marking', Select).value == 'manual'
            setup.query_one('#topical-marking', Select).value = 'ai'
            setup.query_one('#topical-topics', Button).press()
            await pilot.pause()
            await pilot.press('escape')
            await pilot.pause()
            assert app.screen is setup and setup.query_one('#topical-marking', Select).value == 'ai'
            setup.query_one('#topical-start', Button).press()
            await pilot.pause()
            assert result[0]['topical_auto_mark'] is True
            app.tutor.start('topical', **result[0])
            assert app.tutor.session['topical_auto_mark'] is True
            from tutorlib.session import Tutor
            from tutorlib.store import Vault
            restored = Tutor(Vault(vault))
            assert restored.session['topical_auto_mark'] is True
            from tutor_app.config import Settings
            assert Settings.load(vault).practice_auto_mark is True          # kept for the next set (the session keeps its own)
            await app.ai.close()
    asyncio.run(go())


@pytest.mark.parametrize('automatic', [False, True])
@pytest.mark.parametrize('verdict', ['full', 'partial', 'zero', 'invalid', 'failure'])
def test_structured_auto_marks_exactly_once_or_preserves_manual_fallback(tmp_path, monkeypatch, automatic, verdict):
    app, _ = staged_app(tmp_path, monkeypatch)
    app.settings.ai_mark_model = 'codex:gpt-6.1-terra'
    app.settings.marking_strictness = 'lenient'
    calls = []
    working = 'My full typed working\nSecond step, with units.'

    async def go():
        async with app.run_test(size=(80, 24)) as pilot:
            app.tutor.start('topical', focus=[TARGET], topical_count=1, topical_types=['structured'],
                            topical_auto_mark=automatic)
            screen = SessionScreen(None)
            await app.push_screen(screen)
            await pilot.pause()
            n = screen.view['n']
            original = deepcopy(app.tutor.session['presented'][str(n)]['inst'])
            monkeypatch.setattr(app, 'ai_available', lambda mode: True)

            async def marker(prompt, **kwargs):
                calls.append((prompt, kwargs))
                if verdict == 'failure':
                    raise RuntimeError('Scripted provider failure')
                met = 12 if verdict == 'full' else 6 if verdict == 'partial' else 0
                points = [{'point': f"{p.get('mark', '')} {p.get('point', '')}", 'met': i < met}
                          for i, p in enumerate(screen.scheme)]
                if verdict == 'invalid':
                    points[0]['point'] = 'Incorrect identity'
                return {'points': points, 'feedback': 'Scripted verdict.'}, ai.Result()

            monkeypatch.setattr(app.ai, 'one_shot', marker)
            screen.long_written({'text': working})
            await app.workers.wait_for_complete()
            await pilot.pause()
            answers = [e for e in app.tutor.vault.events() if e['type'] == 'answer']
            if not automatic or verdict in ('invalid', 'failure'):
                assert not answers and screen.query_one('#panel > *', TickPanel)
                assert len(calls) == (1 if automatic else 0)
                if automatic:
                    assert app.tutor.session['presented'][str(n)]['saved_work'] == working
            else:
                assert len(answers) == len(calls) == 1
                assert answers[0]['grade']['score'] == {'full': 1, 'partial': .5, 'zero': 0}[verdict]
                assert screen.last_fb['your'] == working
                assert not screen.query('#panel > TickPanel')
                assert 'AI MARKING STRICTNESS: Lenient' in calls[0][0] and working in calls[0][0]
                assert calls[0][1]['model'] == 'codex:gpt-6.1-terra'
            if str(n) in app.tutor.session['presented']:
                assert app.tutor.session['presented'][str(n)]['inst'] == original
            assert not app.tutor._marking_tickets
            await app.ai.close()
    asyncio.run(go())


@pytest.mark.parametrize('model,pages,want_calls', [('codex:gpt-6.1-terra', 2, 1),
                                                ('haiku', 1, 0), ('ollama:gemma4:e4b', 2, 0)])
@pytest.mark.parametrize('separate_primary', [False, True])
@pytest.mark.parametrize('missing_primary', [False, True])
def test_auto_source_images_are_complete_or_an_explicit_manual_fallback(tmp_path, monkeypatch, model, pages, want_calls, separate_primary, missing_primary):
    app, vault = staged_app(tmp_path, monkeypatch)
    app.settings.ai_mark_model = model
    images = [f'Library/Courses/9702/Questions/Media/auto-{i}.png' for i in range(pages)]
    (vault / '.tutor/packs/v1/papers.json').write_text('{"papers": []}')
    for path in images:
        write_asset(vault, path, b'disposable transport fixture')
    if missing_primary:
        (vault / images[0]).unlink()
        want_calls = 0
    calls = []

    async def go():
        async with app.run_test(size=(80, 24)) as pilot:
            app.tutor.start('topical', focus=[TARGET], topical_count=1, topical_types=['structured'], topical_auto_mark=True)
            screen = SessionScreen(None)
            await app.push_screen(screen)
            await pilot.pause()
            screen.view.update(image=images[0], images=images[1:] if separate_primary else images)
            monkeypatch.setattr(app, 'ai_available', lambda mode: True)

            async def marker(prompt, **kwargs):
                calls.append(kwargs)
                return {'points': [{'point': f"{p.get('mark', '')} {p.get('point', '')}", 'met': True}
                                   for p in screen.scheme], 'feedback': 'All met.'}, ai.Result()

            monkeypatch.setattr(app.ai, 'one_shot', marker)
            screen.long_written({'text': 'Complete typed answer.'})
            await app.workers.wait_for_complete()
            await pilot.pause()
            assert len(calls) == want_calls
            if want_calls:
                assert calls[0]['images'] == [vault / path for path in images]
                assert len([e for e in app.tutor.vault.events() if e['type'] == 'answer']) == 1
            else:
                assert screen.query_one('#panel > *', TickPanel)
                assert not [e for e in app.tutor.vault.events() if e['type'] == 'answer']
            await app.ai.close()
    asyncio.run(go())


@pytest.mark.parametrize('ending', ['cancel', 'stale', 'guards'])
def test_auto_marking_keeps_work_and_rejects_late_or_cancelled_verdicts(tmp_path, monkeypatch, ending):
    app, _ = staged_app(tmp_path, monkeypatch)
    app.settings.ai_mark_model = 'codex:gpt-6.1-terra'

    async def go():
        ready, release = asyncio.Event(), asyncio.Event()
        async with app.run_test(size=(80, 24)) as pilot:
            app.tutor.start('topical', focus=[TARGET], topical_count=1, topical_types=['structured'], topical_auto_mark=True)
            screen = SessionScreen(None)
            await app.push_screen(screen)
            await pilot.pause()
            monkeypatch.setattr(app, 'ai_available', lambda mode: True)
            n = str(screen.view['n'])

            async def marker(prompt, **kwargs):
                ready.set()
                await release.wait()
                return {'points': [{'point': f"{p.get('mark', '')} {p.get('point', '')}", 'met': True}
                                   for p in screen.scheme], 'feedback': 'All met.'}, ai.Result()

            monkeypatch.setattr(app.ai, 'one_shot', marker)
            screen.long_written({'text': 'Preserve this original working.'})
            await asyncio.wait_for(ready.wait(), 2)
            assert app.tutor.session['presented'][n]['saved_work'] == 'Preserve this original working.'
            if ending == 'cancel':
                for worker in list(app.workers):
                    if worker.group == 'judge':
                        worker.cancel()
            elif ending == 'stale':
                app.tutor.session['presented'][n] = deepcopy(app.tutor.session['presented'][n])
            else:
                app.tutor.session['skipped_answer_guards'] = {'changed': {'key': 'protected'}}
            release.set()
            if ending == 'cancel':
                with pytest.raises(WorkerCancelled):
                    await app.workers.wait_for_complete()
            else:
                await app.workers.wait_for_complete()
            assert not [e for e in app.tutor.vault.events() if e['type'] == 'answer']
            assert not app.tutor._marking_tickets
            assert app.tutor.session['presented'][n]['saved_work'] == 'Preserve this original working.'
            await app.ai.close()
    asyncio.run(go())


def test_paper_only_answer_does_not_get_automatically_graded_as_missing_work(tmp_path, monkeypatch):
    app, _ = staged_app(tmp_path, monkeypatch)
    async def go():
        async with app.run_test() as pilot:
            app.tutor.start('topical', focus=[TARGET], topical_count=1, topical_types=['structured'], topical_auto_mark=True)
            screen = SessionScreen(None)
            await app.push_screen(screen)
            await pilot.pause()
            monkeypatch.setattr(app, 'ai_available', lambda mode: True)
            async def forbidden(*args, **kwargs):
                raise AssertionError('Paper work was not supplied to the marker')
            monkeypatch.setattr(app.ai, 'one_shot', forbidden)
            screen.long_written({'text': 'done on paper'})
            await app.workers.wait_for_complete()
            await pilot.pause()
            assert screen.query_one('#panel > *', TickPanel)
            assert not [e for e in app.tutor.vault.events() if e['type'] == 'answer']
            await app.ai.close()
    asyncio.run(go())


@pytest.mark.parametrize('mode,kind,want', [('test', 'mcq', True), ('test', 'structured', False),
                                          ('long', 'structured', True), ('lesson', 'mcq', False),
                                          ('blurt', 'mcq', False)])
def test_bank_only_topic_is_visible_in_supported_question_modes(tmp_path, monkeypatch, mode, kind, want):
    from test_topicals import OTHER, item, publish
    from tutor_app.screens import PickerScreen
    app, root = staged_app(tmp_path, monkeypatch)
    source = item(id='bank-only-route', kcs=[OTHER + '.1'], kind=kind,
                  source={'type': 'past', 'qid': '9702_s23_22_q92'})
    source['topical'].update(chapters=[OTHER], requires=[OTHER], support={})
    if kind == 'structured':
        source['scheme'] = [{'mark': 'B1', 'point': 'Synthetic mark point.'}]
    # Replace the disposable bank, keeping this chapter without a teaching pack.
    publish(root, [source], version='bank-only')
    async def go():
        async with app.run_test() as pilot:
            picker = PickerScreen(mode)
            await app.push_screen(picker)
            await pilot.pause()
            assert (OTHER in picker.built) is want
            await app.ai.close()
    asyncio.run(go())
