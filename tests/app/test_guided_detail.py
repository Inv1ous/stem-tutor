from library_assets import read_json as library_json
import asyncio
import pytest
from textual.widgets import Button
from test_tui import app_for
from tutor_app.screens import SessionScreen


def test_expanded_detail_appears_only_after_request_and_is_logged(tmp_path, monkeypatch):
    app, vault = app_for(tmp_path, monkeypatch)
    async def run():
        async with app.run_test(size=(120, 40)) as pilot:
            app.push_screen(SessionScreen({"mode": "test", "minutes": 10, "focus": ["9702-2.1"]}))
            await pilot.pause()
            screen = app.screen
            app.tutor.session["presented"] = {}
            app.tutor.session["queue"] = {}
            act = {"activity": "explain", "title": "In plain words", "text": "SHORT VERSION",
                   "detail": "EXPANDED DETAIL", "kc": "9702-2.1.1", "part": "plain_words"}
            monkeypatch.setattr(app.tutor, "next", lambda: act)
            screen.advance()
            await pilot.pause()
            assert len(screen.query("#detail")) == 1
            assert "EXPANDED DETAIL" not in (vault / "Now.md").read_text()
            screen.query_one("#detail", Button).press()
            await pilot.pause()
            assert "EXPANDED DETAIL" in (vault / "Now.md").read_text()
            assert app.tutor.session is not None
            await app.ai.close()
    asyncio.run(run())


def test_expanded_detail_does_not_reveal_a_skipped_answer(tmp_path, monkeypatch):
    app, vault = app_for(tmp_path, monkeypatch)
    async def run():
        async with app.run_test(size=(120, 40)) as pilot:
            app.push_screen(SessionScreen({"mode": "test", "minutes": 10, "focus": ["9702-2.1"]}))
            await pilot.pause()
            screen = app.screen
            app.tutor.session['presented'] = {}
            app.tutor.session['queue'] = {}
            app.tutor.session['skipped_answer_guards'] = {'item': {'key': '14', 'kind': 'numeric'}}
            act = {"activity": "explain", "title": "Idea", "text": "SHORT",
                   "detail": "The answer is 14.", "kc": "9702-2.1.1", "part": "plain_words"}
            monkeypatch.setattr(app.tutor, 'next', lambda: act)
            screen.advance()
            await pilot.pause()
            screen.query_one('#detail', Button).press()
            await pilot.pause()
            assert 'The answer is 14.' not in (vault / 'Now.md').read_text()
            await app.ai.close()
    asyncio.run(run())


def test_expanded_detail_is_not_revealed_with_an_open_question(tmp_path, monkeypatch):
    app, vault = app_for(tmp_path, monkeypatch)
    async def run():
        async with app.run_test(size=(120, 40)) as pilot:
            app.push_screen(SessionScreen({"mode": "test", "minutes": 10, "focus": ["9702-2.1"]}))
            await pilot.pause()
            screen = app.screen
            act = {"activity": "explain", "title": "In plain words", "text": "SHORT VERSION",
                   "detail": "SECRET DETAIL", "kc": "9702-2.1.1", "part": "plain_words"}
            monkeypatch.setattr(app.tutor, "next", lambda: act)
            screen.advance()
            await pilot.pause()
            screen.query_one("#detail", Button).press()
            await pilot.pause()
            assert "SECRET DETAIL" not in (vault / "Now.md").read_text()
            await app.ai.close()
    asyncio.run(run())


def test_guided_diagram_can_be_reopened_without_leaking_an_open_answer(tmp_path, monkeypatch):
    from tutorlib import lesson
    app, vault = app_for(tmp_path, monkeypatch)
    async def run():
        async with app.run_test(size=(120, 40)) as pilot:
            app.push_screen(SessionScreen({"mode": "test", "minutes": 10, "focus": ["9702-2.1"]}))
            await pilot.pause()
            screen = app.screen
            app.tutor.session["presented"] = {}
            app.tutor.session["queue"] = {}
            card = {"diagrams": ["Assets/P2/proof.svg"], "diagram_descriptions": ["Assumptions lead to a conclusion."]}
            monkeypatch.setattr(lesson, "teach_card", lambda tutor, kc: card)
            act = {"activity": "explain", "title": "In plain words", "text": "SHORT", "kc": "9702-2.1.1"}
            monkeypatch.setattr(app.tutor, "next", lambda: act)
            screen.advance()
            await pilot.pause()
            screen.query_one("#diagram", Button).press()
            await pilot.pause()
            assert "![[Assets/P2/proof.svg]]" in (vault / "Now.md").read_text()
            app.tutor.session["presented"] = {"99": {}}
            before = (vault / "Now.md").read_text()
            screen.query_one("#diagram", Button).press()
            await pilot.pause()
            assert (vault / "Now.md").read_text() == before
            await app.ai.close()
    asyncio.run(run())


@pytest.mark.parametrize("read_aloud", [False, True])
def test_guided_controls_fit_small_terminal(tmp_path, monkeypatch, read_aloud):
    from textual.containers import VerticalScroll
    from tutorlib import lesson
    app, _ = app_for(tmp_path, monkeypatch)
    async def run():
        async with app.run_test(size=(60, 24)) as pilot:
            app.push_screen(SessionScreen({"mode": "test", "minutes": 10, "focus": ["9702-2.1"]}))
            await pilot.pause()
            screen = app.screen
            app.tutor.session["presented"] = {}
            app.tutor.session["queue"] = {}
            monkeypatch.setattr(screen, "can_read", lambda: read_aloud)
            monkeypatch.setattr(lesson, "teach_card", lambda tutor, kc: {"diagrams": ["Assets/P2/proof.svg"]})
            monkeypatch.setattr(app.tutor, "next", lambda: {"activity": "explain", "title": "Idea",
                "text": "Short explanation", "detail": "More detail", "kc": "9702-2.1.1"})
            screen.advance()
            await pilot.pause()
            assert screen.query_one("#log", VerticalScroll).region.height >= 5
            for button in screen.query("#panel Button"):
                assert button.region.bottom <= app.size.height
                assert button.region.right <= app.size.width
            assert screen.query_one("#diagram", Button).region.height > 0
            await app.ai.close()
    asyncio.run(run())


def test_p2_calculus_check_terminal_render_is_readable():
    import json
    from pathlib import Path
    from tutor_app.texmath import to_terminal
    root = Path(__file__).resolve().parents[2]
    cards = library_json('build/work/teach/P2-1.json')
    form = next(f for f in cards['P2-1.1']['forms'] if f['name'] == 'Prove a stationary point is a maximum')
    rendered = to_terminal(form['check'])
    assert 'g′′(x) = −2x − 2' in rendered
    assert '$' not in rendered and r'\prime' not in rendered


def test_all_p2_form_examples_and_checks_render_without_raw_tex():
    import json
    from pathlib import Path
    from tutor_app.texmath import to_terminal
    root = Path(__file__).resolve().parents[2]
    cards = library_json('build/work/teach/P2-1.json')
    for card in cards.values():
        for form in card['forms']:
            for label, content in [('example', form['example']), ('check', form['check']),
                                   ('retry', form['retry']['check'])]:
                rendered = to_terminal(content)
                assert '$' not in rendered and '\\' not in rendered, (form['name'], label, rendered)


@pytest.mark.parametrize('button', ['detail', 'diagram'])
def test_guided_expansion_does_not_reveal_pending_queue(tmp_path, monkeypatch, button):
    from tutorlib import lesson
    app, vault = app_for(tmp_path, monkeypatch)
    async def run():
        async with app.run_test(size=(120, 40)) as pilot:
            app.push_screen(SessionScreen({'mode': 'test', 'minutes': 10, 'focus': ['9702-2.1']}))
            await pilot.pause()
            screen = app.screen
            app.tutor.session['presented'] = {}
            app.tutor.session['queue'] = {'99': {'item': 'unattempted'}}
            monkeypatch.setattr(lesson, 'teach_card', lambda tutor, kc: {'diagrams': ['Assets/P2/proof.svg']})
            monkeypatch.setattr(app.tutor, 'next', lambda: {'activity': 'explain', 'title': 'Idea',
                'text': 'SHORT', 'detail': 'SECRET DETAIL', 'kc': '9702-2.1.1'})
            screen.advance()
            await pilot.pause()
            before = (vault / 'Now.md').read_text()
            screen.query_one(f'#{button}', Button).press()
            await pilot.pause()
            assert (vault / 'Now.md').read_text() == before
            await app.ai.close()
    asyncio.run(run())


def test_constrained_triples_example_fits_small_terminal(tmp_path, monkeypatch):
    import json
    from pathlib import Path
    from textual.containers import VerticalScroll
    root = Path(__file__).resolve().parents[2]
    cards = library_json('build/work/teach/P2-1.json')
    form = next(f for f in cards['P2-1.2']['forms'] if f['name'] == 'Exhaustion with two simultaneous constraints')
    app, vault = app_for(tmp_path, monkeypatch)
    async def run():
        async with app.run_test(size=(80, 24)) as pilot:
            app.push_screen(SessionScreen({'mode': 'test', 'minutes': 10, 'focus': ['9702-2.1']}))
            await pilot.pause()
            screen = app.screen
            app.tutor.session['presented'] = {}
            app.tutor.session['queue'] = {}
            act = {'activity': 'explain', 'title': form['name'], 'text': form['example'],
                   'kc': '9702-2.1.1', 'part': 'form_example'}
            monkeypatch.setattr(app.tutor, 'next', lambda: act)
            screen.advance()
            await pilot.pause()
            assert screen.query_one('#log', VerticalScroll).region.height >= 5
            assert all(b.region.bottom <= app.size.height and b.region.right <= app.size.width
                       for b in screen.query('#panel Button'))
            assert form['answer'] not in (vault / 'Now.md').read_text()
            app.save_screenshot(path='/tmp', filename='p2-constrained-80.svg')
            await app.ai.close()
    asyncio.run(run())


def test_radius_line_example_in_terminal_and_obsidian(tmp_path, monkeypatch):
    import json
    from pathlib import Path
    from textual.containers import VerticalScroll
    root = Path(__file__).resolve().parents[2]
    cards = library_json('build/work/teach/P2-1.json')
    form = next(f for f in cards['P2-1.1']['forms'] if f['name'] == 'Show a radius-line equation from a tangent')
    app, vault = app_for(tmp_path, monkeypatch)
    async def run():
        async with app.run_test(size=(80, 24)) as pilot:
            app.push_screen(SessionScreen({'mode': 'test', 'minutes': 10, 'focus': ['9702-2.1']}))
            await pilot.pause()
            screen = app.screen
            app.tutor.session['presented'] = {}
            app.tutor.session['queue'] = {}
            act = {'activity': 'explain', 'title': form['name'], 'text': form['example'],
                   'kc': '9702-2.1.1', 'part': 'form_example'}
            app.tutor._await(act)
            app.tutor._save()
            monkeypatch.setattr(app.tutor, 'next', lambda: act)
            screen.advance()
            await pilot.pause()
            assert screen.query_one('#log', VerticalScroll).region.height >= 5
            assert all(b.region.bottom <= app.size.height and b.region.right <= app.size.width
                       for b in screen.query('#panel Button'))
            now = (vault / 'Now.md').read_text()
            assert all(line in now for line in form['example'].splitlines() if line.strip())
            assert form['answer'] not in now
            app.save_screenshot(path='/tmp', filename='p2-radius-line-80.svg')
            await app.ai.close()
    asyncio.run(run())
