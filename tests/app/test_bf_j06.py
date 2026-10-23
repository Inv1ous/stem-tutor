from __future__ import annotations

import asyncio

import pytest

from test_tui import app_for, _open_long_and_submit
from tutor_app import ai as ai_mod
from tutor_app.panels import ReflectPanel, TickPanel
from tutor_app.screens import SessionScreen


def test_a_late_ai_reply_never_marks_the_next_question_as_hinted(tmp_path, monkeypatch):
    """B-065: delayed help belongs to the original question, including in Now."""
    app, vault = app_for(tmp_path, monkeypatch)

    async def go():
        async with app.run_test() as pilot:
            await pilot.pause()
            app.push_screen(SessionScreen({"mode": "autopilot", "minutes": 50}))
            await pilot.pause()
            scr, t = app.screen, app.tutor
            ready, release = asyncio.Event(), asyncio.Event()

            async def delayed(*args, **kwargs):
                ready.set()
                await release.wait()
                app.ai.last = ai_mod.Result(text="Consider the dimensions carefully.")
                yield app.ai.last.text

            monkeypatch.setattr(app.ai, "stream", delayed)
            worker = scr._stream("Help with this question", False)
            await ready.wait()
            scr.submit({"entry": f"{scr.view['n']}?"})
            await pilot.pause()
            scr.advance()
            await pilot.pause()
            assert t.session["presented"]
            release.set()
            await worker.wait()
            await pilot.pause()
            assert not any(p["hinted"] for p in t.session["presented"].values())
            assert "Consider the dimensions carefully." not in (vault / "Now.md").read_text()
            assert "Consider the dimensions carefully." in (vault / t.session["log"]).read_text()
    asyncio.run(go())


def test_the_examiner_replaces_overgenerous_ticks(tmp_path, monkeypatch):
    """B-078: the checklist defaults agree with the examiner's rejected points."""
    app, _ = app_for(tmp_path, monkeypatch)

    async def examiner(*args, **kwargs):
        return {"points": [{"met": False}, {"met": False}]}, ai_mod.Result()

    async def go():
        async with app.run_test() as pilot:
            await pilot.pause()
            await _open_long_and_submit(pilot, app, "my working")
            scr = app.screen
            monkeypatch.setattr(app.ai, "one_shot", examiner)
            await scr.ai_check_long({"ticked": [str(p["i"]) for p in scr.scheme]}).wait()
            await pilot.pause()
            ticks = scr.query_one(TickPanel).query_one("#ticks")
            assert ticks.selected == []
            # The learner remains free to disagree with the examiner.
            ticks.select(ticks.get_option_at_index(0).value)
            assert len(ticks.selected) == 1
    asyncio.run(go())


@pytest.mark.parametrize("kind,ai", [("short", True), ("short", False), ("structured", False)])
def test_written_mistakes_show_the_reflection_and_save_its_reason(tmp_path, monkeypatch, kind, ai):
    """B-097: short AI/self marks and long self marks must offer their earned reflection."""
    app, _ = app_for(tmp_path, monkeypatch)
    app.settings.ai = ai

    async def examiner(*args, **kwargs):
        return {"points": [{"point": "distance", "met": True}, {"point": "direction", "met": False}]}, ai_mod.Result()

    async def go():
        async with app.run_test() as pilot:
            await pilot.pause()
            t = app.tutor
            t.start("review", minutes=10)
            if kind == "short":
                item = {"id": "s1", "kcs": ["9702-2.1.1"], "kind": "short", "difficulty": 3, "marks": 2,
                        "stem": "Define displacement.", "rubric": [{"point": "distance", "keywords": [["distance"]]},
                                                                    {"point": "direction", "keywords": [["direction"]]}]}
            else:
                item = next(i for i in t.packs.items_for("9702-2.1.4") if i["kind"] == "structured")
            t._present(item, block="practice", phase=None)
            await app.push_screen(SessionScreen(None))
            await pilot.pause()
            scr = app.screen
            monkeypatch.setattr(app.ai, "one_shot", examiner)
            if kind == "short":
                scr.submit({"entry": f"{scr.view['n']} = how far it moved ~3", "your": "how far it moved"})
                await pilot.pause()
                await scr.workers.wait_for_complete()
                if not ai:
                    scr.long_marks({"ticked": ["0"]})
            else:
                scr.long_written({"text": "my working"})
                scr.long_marks({"ticked": [str(scr.scheme[0]["i"])]})
            await pilot.pause()
            assert isinstance(scr.showing, ReflectPanel)
            assert scr.query_one("#reflect").option_count == 5
            await pilot.press("1")
            await pilot.pause()
            assert [e["error"] for e in t.vault.events() if e["type"] == "tag"] == ["SLIP"]
            assert [b.id for b in scr.query("#panel Button")] == ["next", "ask"]
    asyncio.run(go())
