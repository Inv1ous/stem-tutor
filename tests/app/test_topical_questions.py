"""Eligibility is discoverable in the existing question controls, including no-hints checks."""
import asyncio
from io import StringIO
from rich.console import Console

from textual.widgets import Button

from test_tui import app_for
from tutor_app.screens import SessionScreen


def test_metadata_action_is_visible_and_works_during_no_hints(tmp_path, monkeypatch):
    app, root = app_for(tmp_path, monkeypatch)

    async def go():
        async with app.run_test(size=(100, 35)) as pilot:
            await pilot.pause()
            scr = SessionScreen({'mode': 'test', 'minutes': 20, 'focus': ['9702-2.1']})
            app.push_screen(scr)
            await pilot.pause()
            assert scr.view['unassisted']
            button = scr.query_one('#check-solvable', Button)
            assert button.display and 'Can I solve this?' in str(button.label)
            t = app.tutor
            p = t.session['presented'][str(scr.view['n'])]
            p['inst']['topical'] = {'reviewed': True, 'requires': ['9702-2.1'], 'support': {},
                                    'chapters': ['9702-2.1'], 'revision': '2025-2027'}
            await pilot.press('ctrl+y')
            await pilot.pause()
            await app.workers.wait_for_complete()  # the check runs in a worker
            await pilot.pause()
            assert not p['hinted'] and t.session['answered'] == 0
            assert 'Can I solve this?' in (root / 'Now.md').read_text()
            assert not any(e['type'] == 'answer' for e in t.vault.events())
            await app.ai.close()
    asyncio.run(go())


def test_ctrl_y_on_faded_retry_stays_answer_free(tmp_path, monkeypatch):
    from tutorlib import faded

    app, root = app_for(tmp_path, monkeypatch)

    async def go():
        async with app.run_test(size=(100, 35)) as pilot:
            await pilot.pause()
            scr = SessionScreen({'mode': 'test', 'minutes': 20, 'focus': ['9702-2.1']})
            app.push_screen(scr)
            await pilot.pause()
            t = app.tutor
            t.start('learn', focus=['9702-2.1.1'])
            item = {'id': 'ui-faded-guard', 'kind': 'short', 'problem': 'Explain the result.',
                    'review_answer': 'SECRET SOLUTION',
                    'rubric': [{'point': 'SECRET POINT', 'keywords': [['reason']]}]}
            view = t._present(faded.question_item(item, '9702-2.1.1'), block='learn', phase='faded')
            t.answer(f"{view['n']}?")
            retry = t.retry_skipped()['items'][0]
            scr.act = {'activity': 'questions', 'items': [retry]}
            scr.ask_question(retry)
            await pilot.pause()
            answered_before = t.session['answered']
            events_before = len(list(t.vault.events()))

            await pilot.press('ctrl+y')
            await pilot.pause()
            await app.workers.wait_for_complete()  # the check runs in a worker
            await pilot.pause()

            assert 'Can I solve this?' in (root / 'Now.md').read_text()
            assert 'SECRET' not in (root / 'Now.md').read_text()
            assert t.session['answered'] == answered_before
            assert str(retry['n']) in t.session['presented']
            assert len(list(t.vault.events())) == events_before
            await app.ai.close()
    asyncio.run(go())


def test_ctrl_y_after_advancing_does_not_check_previous_question(tmp_path, monkeypatch):
    app, root = app_for(tmp_path, monkeypatch)

    async def go():
        async with app.run_test(size=(100, 35)) as pilot:
            await pilot.pause()
            scr = SessionScreen({'mode': 'test', 'minutes': 20, 'focus': ['9702-2.1']})
            app.push_screen(scr)
            await pilot.pause()
            t = app.tutor
            previous = scr.view['n']
            old = t.session['presented'][str(previous)]
            old['inst']['topical'] = {'reviewed': True, 'requires': ['9702-3.1'], 'support': {},
                                      'chapters': ['9702-2.1'], 'revision': '2025-2027'}
            t.answer(f"{previous}A3")
            scr.advance()
            await pilot.pause()
            assert str(previous) not in t.session['presented']
            current = scr.view['n']
            assert current != previous

            checked = []
            real_check = t.check_solvable
            def capture_check(n):
                checked.append(n)
                return real_check(n)
            monkeypatch.setattr(t, 'check_solvable', capture_check)
            await pilot.press('ctrl+y')
            await pilot.pause()
            await app.workers.wait_for_complete()  # the check runs in a worker
            await pilot.pause()

            now = (root / 'Now.md').read_text()
            assert checked == [current]
            assert 'Can I solve this?' in now
            assert 'This question is no longer open.' not in now
            assert t.session['answered'] == 1
            assert not any('SECRET' in line for line in now.splitlines())
            await app.ai.close()
    asyncio.run(go())


def test_terminal_shows_reviewed_support_beside_question(tmp_path, monkeypatch):
    app, root = app_for(tmp_path, monkeypatch)

    async def go():
        async with app.run_test(size=(100, 35)) as pilot:
            await pilot.pause()
            scr = SessionScreen({'mode': 'test', 'minutes': 20, 'focus': ['9702-2.1']})
            app.push_screen(scr)
            await pilot.pause()
            scr.ask_question({**scr.view, 'support': {'9702-3.1': 'A reviewed prerequisite fact.'}})
            await pilot.pause()
            stream = StringIO()
            console = Console(file=stream, width=100)
            for w in scr.query('#log > *'):
                console.print(getattr(w.render(), "_renderable", w.render()))
            assert 'A reviewed prerequisite fact.' in stream.getvalue()
            await app.ai.close()
    asyncio.run(go())


def test_multipage_written_question_offers_self_marking_until_all_pages_can_reach_ai(tmp_path, monkeypatch):
    app, root = app_for(tmp_path, monkeypatch)

    async def go():
        async with app.run_test(size=(100, 35)) as pilot:
            await pilot.pause()
            scr = SessionScreen({'mode': 'test', 'minutes': 20, 'focus': ['9702-2.1']})
            app.push_screen(scr)
            await pilot.pause()
            structured = next(i for i in app.tutor.packs.items_for('9702-2.1.4') if i['kind'] == 'structured')
            scr.view = app.tutor._present(structured, 'long', None)
            scr.view['images'] = ['Assets/topicals/one.png', 'Assets/topicals/two.png']
            monkeypatch.setattr(scr, 'ai_ok', lambda *args: True)
            captured = []
            monkeypatch.setattr(scr, 'mark_panel', lambda prompt, ticks, buttons: captured.extend(buttons))
            scr.long_written({'text': 'My complete working.'})
            assert [key for key, label in captured] == ['mine']
            await app.ai.close()
    asyncio.run(go())


def test_home_topical_picker_includes_unbuilt_bank_chapter_without_enabling_its_lesson(tmp_path, monkeypatch):
    import json
    from test_topicals import OTHER, item, publish
    from tutor_app.screens import PickerScreen, TopicalSetupScreen
    app, root = app_for(tmp_path, monkeypatch)
    graph_path = root / '.tutor/packs/v1/specs/9702/graph.json'
    graph = json.loads(graph_path.read_text())
    graph['subtopics'].append({'id': OTHER, 'title': 'Unbuilt bank chapter', 'topic': '9702-2'})
    graph['kcs'].append({'id': OTHER + '.1', 'subtopic': OTHER, 'title': 'Unbuilt idea',
                         'statement': 'A syllabus statement.', 'level': 'AS', 'type': 'conceptual', 'prereqs': []})
    graph_path.write_text(json.dumps(graph))
    source = item(kcs=[OTHER + '.1'])
    source['topical'].update(requires=[OTHER], support={}, chapters=[OTHER])
    publish(root, [source])

    async def go():
        async with app.run_test(size=(100, 35)) as pilot:
            await pilot.pause()
            home = app.screen
            assert 'practice' in dict(home._menu_items)  # one entry now; the old 'topical' id still works below
            home._start('topical')
            await pilot.pause()
            assert isinstance(app.screen, PickerScreen) and OTHER in app.screen.built
            app.pop_screen()
            app.push_screen(PickerScreen('lesson'))
            await pilot.pause()
            assert OTHER not in app.screen.built
            app.pop_screen()
            home._start('topical')
            await pilot.pause()
            app.screen.dismiss([OTHER])
            await pilot.pause()
            assert isinstance(app.screen, TopicalSetupScreen)
            app.screen.query_one('#topical-start', Button).press()
            await pilot.pause()
            assert isinstance(app.screen, SessionScreen) and app.screen.view['kind'] == 'mcq'
            await app.ai.close()
    asyncio.run(go())
