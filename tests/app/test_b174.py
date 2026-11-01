"""Submitted typed answers leave room for the confidence step after resizing."""
import html
import re

import pytest

from test_qol import run
from test_tui import app_for
from tutor_app.panels import Composer, Confidence, Settling, TickPanel, ValuePanel
from tutor_app.screens import SessionScreen

LONG_ANSWER = ("Displacement is the vector change in position from the initial point to the final point. "
               "It has a magnitude and a direction unlike distance which is the total path length.\n" * 4)[:500]


def _rendered_text(app):
    return html.unescape("".join(re.findall(r">([^<>]*)</text>", app.export_screenshot()))).replace("\xa0", " ")


@pytest.mark.parametrize("kind,raw", [("short", LONG_ANSWER), ("short", "Change in position with direction."),
                                     ("numeric", "19.6 m s-1")], ids=["long-short", "normal-short", "numeric"])
def test_typed_confidence_survives_resize_and_escape_without_losing_answer(tmp_path, monkeypatch, kind, raw):
    app, _ = app_for(tmp_path, monkeypatch)
    app.settings.ai = False
    # Make the held-Enter guard deterministic throughout the test. Number keys still deliberately choose.
    monkeypatch.setattr(Settling, "SETTLE", 100)

    async def steps(pilot):
        item = {"id": "9702-2.1-i50", "kind": kind, "kcs": ["9702-2.1.1"], "difficulty": 2,
                "marks": 1, "stem": "Define displacement." if kind == "short" else "Calculate the velocity.",
                "rubric": [{"point": "Change in position with direction.", "keywords": [["position", "direction"]]}],
                "answer": {"value": 19.6, "unit": "m s-1", "sf_ok": [3, 3]}}
        app.tutor.packs.pack("9702-2.1")["items"][:] = [item]
        screen = SessionScreen({"mode": "test", "minutes": 10, "focus": ["9702-2.1.1"]})
        app.push_screen(screen)
        await pilot.pause()
        panel = screen.query_one(ValuePanel)
        composer = panel.query_one("#value", Composer)
        composer.load_text(raw)
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        conf = panel.query_one(Confidence)
        assert conf.has_focus
        assert panel.value == " ".join(raw.split())
        assert not [e for e in app.tutor.vault.events() if e["type"] == "answer"]

        await pilot.resize_terminal(80, 24)
        await pilot.pause()
        assert conf.region.height == 4 and conf.region.bottom <= screen.query_one("Footer").region.y
        visible = _rendered_text(app)
        for text in ("How sure are you?", "Guess", "Unsure", "Fairly sure", "Certain"):
            assert text in visible
        assert conf.has_focus
        await pilot.press("enter")  # a repeat must not submit the selected default confidence
        await pilot.pause()
        assert not [e for e in app.tutor.vault.events() if e["type"] == "answer"]

        await pilot.press("escape")
        await pilot.pause()
        assert not panel.query(Confidence)
        assert composer.text == raw and composer.display and not composer.disabled and composer.has_focus
        assert composer.region.height > 0 and composer.region.bottom <= screen.query_one("Footer").region.y
        assert panel.query_one(".hint").display
        assert not [e for e in app.tutor.vault.events() if e["type"] == "answer"]

        await pilot.press("enter")
        await pilot.pause()
        assert panel.query_one(Confidence).has_focus
        await pilot.press("4")
        await pilot.pause()
        await app.workers.wait_for_complete()
        await pilot.pause()
        if screen.query(TickPanel):
            await pilot.click("#self")
            await pilot.pause()
        answers = [e for e in app.tutor.vault.events() if e["type"] == "answer"]
        assert len(answers) == 1
        assert answers[0]["response"] == " ".join(raw.split()) and answers[0]["conf"] == 4

    run(app, (140, 46), steps)
