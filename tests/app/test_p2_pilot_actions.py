"""The P2 Proof pilot through the real lesson screen: the AI is offered the visual tools, asks for actions, and the program
draws them in the Terminal log and in Obsidian (Now / lesson log). The model here is a fake that replies with actions."""
from library_assets import read_json as library_json
import asyncio
import hashlib
import io
import json
from pathlib import Path

import pytest
from test_tui import app_for
from textual.widgets import Static
from tutor_app import learn_reply
from tutor_app.ai import Result
from tutor_app.screens import SessionScreen
from tutorlib.asset_library import write_asset

ROOT = Path(__file__).resolve().parents[2]
CARD = library_json('build/work/teach/P2-1.json')["P2-1.1"]
KC, SUB = "9702-2.1.1", "9702-2.1"  # the test vault's physics idea stands in for the P2 chapter; the card is P2's own
NOTES_PATH = 'Library/Courses/9702/Diagrams/p2-1-notes-techniques-map.png'
GENERATED = 'Library/Courses/9702/Diagrams'


def install_test_figure(vault):
    """Register a synthetic figure and provenance in this test's isolated Library."""
    from PIL import Image
    image = io.BytesIO()
    Image.new('RGB', (3, 2), 'blue').save(image, format='PNG')
    data = image.getvalue()
    metadata = {'subtopic': SUB, 'sha256': hashlib.sha256(data).hexdigest(), 'pdf': 'YMA01 c1.1.pdf',
                'page': 2, 'caption': 'Proof techniques map', 'why': 'Compare techniques'}
    sidecar = write_asset(vault, 'Library/Courses/9702/Sources/Provenance/map.png.json', json.dumps(metadata).encode())
    write_asset(vault, NOTES_PATH, data, metadata={'provenance': {'sidecars': [sidecar]}})
    for kind in ('qp', 'ms'):
        filename = f'9702_s23_{kind}_22.pdf'
        write_asset(vault, f'Library/Courses/9702/Sources/Papers/{filename}', b'%PDF-1.4 synthetic fixture',
                    aliases=[f'Papers/9702/{filename}'])


def _log_text(screen) -> str:
    """What the terminal log shows, as plain text (a card is a Rich panel)."""
    from rich.console import Console
    console = Console(width=100, record=True, file=open("/dev/null", "w"))
    for w in screen.query("#log .entry"):
        if isinstance(w, Static):
            console.print(w.content)
    return console.export_text()


@pytest.mark.parametrize("size", [(120, 40), (80, 24)])
def test_the_ai_uses_a_notes_figure_a_generated_figure_and_a_form_check(tmp_path, monkeypatch, size):
    app, vault = app_for(tmp_path, monkeypatch)
    install_test_figure(vault)
    monkeypatch.setattr(learn_reply, "published_related_cards", lambda tutor, kc: {kc: CARD})
    prompts, asked = [], []

    async def fake_model(prompt, schema=None, **kw):
        prompts.append(prompt)
        return {"actions": [
            {"action": "explain", "section": "plain_words"},
            {"action": "diagram", "source": "notes", "figure": "p2-1-notes-techniques-map"},
            {"action": "diagram", "source": "generated", "type": "case_split", "why": "n is even or odd",
             "params": {"start": "n is an integer", "cases": ["n even", "n odd"], "end": "n² + n is even"}},
            {"action": "check", "form": 0}]}, Result()

    async def go():
        async with app.run_test(size=size) as pilot:
            monkeypatch.setattr(app, "ai_available", lambda mode: True)
            monkeypatch.setattr(app.ai, "one_shot", fake_model)
            app.push_screen(SessionScreen({"mode": "test", "minutes": 10, "focus": [SUB]}))
            await pilot.pause()
            scr, t = app.screen, app.tutor
            t.session["presented"], t.session["queue"] = {}, {}
            scr.kc = KC
            await scr.learn_request("I do not see where to start a proof").wait()
            await pilot.pause()
            # offered: the visual tools, the real notes figure and the card's forms, without any answer
            assert "generated" in prompts[0] and "p2-1-notes-techniques-map" in prompts[0] and "case_split" in prompts[0]
            assert CARD["forms"][0]["answer"] not in prompts[0]
            # Obsidian: explanation, the sourced figure with its PDF and page, the generated figure
            # (Now then moves on to the check, which stands alone by design; the lesson log keeps the whole exchange)
            log = (vault / t.session["log"]).read_text()
            assert CARD["plain_words"].strip()[:60] in log
            assert f"![[{NOTES_PATH}]]" in log and "YMA01 c1.1.pdf, p.2" in log
            assert f"![[{GENERATED}/case_split-" in log
            svg = next((vault / GENERATED).glob("case_split-*.svg"))
            assert "n is an integer" in svg.read_text()
            # Terminal: the same cards as text, with the figures' descriptions
            shown = _log_text(scr)
            assert "Figure from your notes" in shown and "Proof techniques map" in shown
            # the check became the question on screen, unassisted, with its answer kept out of Obsidian
            assert scr.view["stem"] == CARD["forms"][0]["check"]
            assert CARD["forms"][0]["answer"] not in (vault / "Now.md").read_text()
            assert t.ai_help(given=False).get("refused")
            await app.ai.close()
    asyncio.run(go())


def test_a_figure_that_cannot_be_drawn_is_said_in_words_and_the_lesson_goes_on(tmp_path, monkeypatch):
    app, vault = app_for(tmp_path, monkeypatch)
    monkeypatch.setattr(learn_reply, "published_related_cards", lambda tutor, kc: {kc: CARD})

    async def fake_model(prompt, schema=None, **kw):
        return {"actions": [{"action": "diagram", "source": "generated", "type": "molecule", "params": {}},
                            {"action": "explain", "section": "plain_words"}]}, Result()

    async def go():
        async with app.run_test(size=(100, 30)) as pilot:
            monkeypatch.setattr(app, "ai_available", lambda mode: True)
            monkeypatch.setattr(app.ai, "one_shot", fake_model)
            app.push_screen(SessionScreen({"mode": "test", "minutes": 10, "focus": [SUB]}))
            await pilot.pause()
            scr, t = app.screen, app.tutor
            t.session["presented"], t.session["queue"] = {}, {}
            scr.kc = KC
            await scr.learn_request("draw it").wait()
            await pilot.pause()
            shown = _log_text(scr)
            assert "not a figure type I can draw" in shown and "explain it in words" in shown
            assert CARD["plain_words"].strip()[:40] in shown  # the rest of the reply still came
            assert not (vault / GENERATED).exists()
            await app.ai.close()
    asyncio.run(go())


def test_now_shows_the_explanation_and_both_figures_when_no_check_follows(tmp_path, monkeypatch):
    app, vault = app_for(tmp_path, monkeypatch)
    install_test_figure(vault)
    monkeypatch.setattr(learn_reply, "published_related_cards", lambda tutor, kc: {kc: CARD})

    async def fake_model(prompt, schema=None, **kw):
        return {"actions": [{"action": "explain", "section": "plain_words"},
                            {"action": "diagram", "source": "notes", "figure": "p2-1-notes-techniques-map"},
                            {"action": "diagram", "source": "generated", "type": "proof_flow",
                             "params": {"steps": ["Assume", "Deduce", "Conclude"]}}]}, Result()

    async def go():
        async with app.run_test(size=(100, 30)) as pilot:
            monkeypatch.setattr(app, "ai_available", lambda mode: True)
            monkeypatch.setattr(app.ai, "one_shot", fake_model)
            app.push_screen(SessionScreen({"mode": "test", "minutes": 10, "focus": [SUB]}))
            await pilot.pause()
            app.tutor.session["presented"], app.tutor.session["queue"] = {}, {}
            app.screen.kc = KC
            await app.screen.learn_request("what is a proof?").wait()
            await pilot.pause()
            now = (vault / "Now.md").read_text()
            assert CARD["plain_words"].strip()[:60] in now
            assert f"![[{NOTES_PATH}]]" in now and f"![[{GENERATED}/proof_flow-" in now
            await app.ai.close()
    asyncio.run(go())


def test_a_write_action_is_written_by_a_second_request_in_the_shared_document_format(tmp_path, monkeypatch):
    """The AI only names the topic; the screen asks for the text as structured blocks, lays them out itself and checks the
    plain algebra, so every model's explanation reaches Terminal and Obsidian in the same form."""
    app, vault = app_for(tmp_path, monkeypatch)
    monkeypatch.setattr(learn_reply, "published_related_cards", lambda tutor, kc: {kc: CARD})
    calls = []

    async def fake_model(prompt, schema=None, **kw):
        calls.append(schema)
        if len(calls) == 1:
            return {"actions": [{"action": "write", "topic": "Three consecutive integers"}]}, Result()
        return {"blocks": [
            {"kind": "paragraph", "text": "Short version: the sum of three consecutive integers is a multiple of 3."},
            {"kind": "step", "text": "Call the integers $n$, $n+1$ and $n+2$."},
            {"kind": "equation", "text": "n+(n+1)+(n+2)=3n+3=3(n+1)"},
            {"kind": "step", "text": "So the sum is 3 times an integer, for every integer $n$."}]}, Result()

    async def go():
        async with app.run_test(size=(100, 30)) as pilot:
            monkeypatch.setattr(app, "ai_available", lambda mode: True)
            monkeypatch.setattr(app.ai, "one_shot", fake_model)
            app.push_screen(SessionScreen({"mode": "test", "minutes": 10, "focus": [SUB]}))
            await pilot.pause()
            app.tutor.session["presented"], app.tutor.session["queue"] = {}, {}
            app.screen.kc = KC
            await app.screen.learn_request("an example with three consecutive integers").wait()
            await pilot.pause()
            assert len(calls) == 2 and "blocks" in calls[1]["properties"]
            now = (vault / "Now.md").read_text()
            assert "Tutor-written: Three consecutive integers" in now
            assert "> 1. Call the integers $n$, $n+1$ and $n+2$." in now  # the program's numbering
            assert "> $$\n> n+(n+1)+(n+2)=3n+3=3(n+1)\n> $$" in now  # and its maths delimiters
            assert "`n+(n+1)+(n+2) = 3n+3`" in now and "Other equations, the wording and the reasoning" in now
            await app.ai.close()
    asyncio.run(go())


@pytest.mark.parametrize('change', ['session', 'activity', 'kc', 'presented', 'queue', 'count', 'guard'])
def test_write_action_rechecks_live_lifecycle_after_second_model_request(tmp_path, monkeypatch, change):
    app, vault = app_for(tmp_path, monkeypatch)
    monkeypatch.setattr(learn_reply, 'published_related_cards', lambda tutor, kc: {kc: CARD})
    calls = []
    original = {}

    async def fake_model(prompt, schema=None, **kw):
        calls.append(schema)
        if len(calls) == 1:
            return {'actions': [{'action': 'write', 'topic': 'Protected example'},
                                {'action': 'diagram', 'source': 'generated', 'type': 'proof_flow',
                                 'params': {'steps': ['Protected diagram']}}]}, Result()
        scr, tutor = app.screen, app.tutor
        if change == 'session':
            tutor.session = dict(tutor.session, id='replacement')
        elif change == 'activity':
            scr.act = dict(scr.act)
        elif change == 'kc':
            scr.kc = SUB + '.4'
        elif change == 'presented':
            tutor.session['presented'] = {'9': {'inst': {'kind': 'short', 'answer': 'SECRET'}, 'unassisted': True}}
        elif change == 'queue':
            tutor.session['queue'] = {'pending': True}
        elif change == 'count':
            tutor.session['count'] = tutor.session.get('count', 0) + 1
        else:
            tutor.session['skipped_answer_guards'] = {'protected': {'kind': 'short', 'key': 'SECRET'}}
        return {'blocks': [{'kind': 'paragraph', 'text': 'SECRET explanation from the delayed writer.'}]}, Result()

    async def go():
        async with app.run_test(size=(100, 30)) as pilot:
            monkeypatch.setattr(app, 'ai_available', lambda mode: True)
            monkeypatch.setattr(app.ai, 'one_shot', fake_model)
            app.push_screen(SessionScreen({'mode': 'test', 'minutes': 10, 'focus': [SUB]}))
            await pilot.pause()
            scr, tutor = app.screen, app.tutor
            tutor.session['presented'], tutor.session['queue'] = {}, {}
            scr.kc = KC
            before = (vault / 'Now.md').read_bytes()
            await scr.learn_request('write an alternative worked example').wait()
            await pilot.pause()
            assert len(calls) == 2
            assert 'SECRET explanation' not in _log_text(scr)
            if change == 'guard':
                assert 'SECRET explanation' not in (vault / 'Now.md').read_text()
                assert "can't give away" in (vault / 'Now.md').read_text()
            else:
                assert (vault / 'Now.md').read_bytes() == before
            assert not (vault / GENERATED).exists()
            assert not tutor.session.get('learn_history')
            await app.ai.close()
    asyncio.run(go())
