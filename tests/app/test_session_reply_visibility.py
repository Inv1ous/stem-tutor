"""Guarded session replies must become visible once the complete reply is checked."""
import asyncio
import os

import pytest
from textual.containers import VerticalScroll

from test_tui import app_for
from tutor_app import ai, prompts
from tutor_app.panels import Composer
from tutor_app.screens import SessionScreen


@pytest.mark.parametrize("size", [(60, 24), (80, 24), (140, 46)])
@pytest.mark.parametrize("outcome", ["hint", "answer", "failure"])
def test_finished_guarded_reply_is_visible_above_the_answer_panel(tmp_path, monkeypatch, size, outcome):
    app, vault = app_for(tmp_path, monkeypatch)
    app.settings.ai = False  # the request uses the in-process stream below
    monkeypatch.setattr(app, "ai_available", lambda mode="ask": True)

    async def go():
        async with app.run_test(size=size) as pilot:
            screen = SessionScreen({"mode": "autopilot", "minutes": 50})
            app.push_screen(screen)
            await pilot.pause()
            number = screen.view["n"]
            pending = app.tutor.session["presented"][str(number)]
            assert not pending["unassisted"] and prompts.guard_keys(app.tutor)
            reply = (f"The answer is {prompts.key_of(app.tutor, number)[0]}."
                     if outcome == "answer" else "Think about the units.")

            async def stream(prompt, **kwargs):
                app.ai.last = (ai.Result(ok=False, status="login", message="Sign in first.")
                               if outcome == "failure" else ai.Result(text=reply))
                yield reply

            monkeypatch.setattr(app.ai, "stream", stream)
            screen.action_ask()
            await pilot.pause()
            app.screen.query_one("#q", Composer).text = "Please check my steps:\n" + "First I list the units.\n" * 50
            await pilot.press("enter")
            await app.workers.wait_for_complete()
            await pilot.pause()
            log = screen.query_one("#log", VerticalScroll)
            latest = log.query(".entry").last()
            if shots := os.environ.get("BUGWATCH_UI_SHOTS"):
                app.save_screenshot(path=shots, filename=f"session-{outcome}-{size[0]}x{size[1]}.svg")
            assert log.max_scroll_y > 0
            assert log.scrollable_content_region.contains_region(latest.region)
            expected = {"hint": reply, "answer": "I can't give that away", "failure": "Sign in first."}[outcome]
            assert expected in (vault / "Now.md").read_text()
            assert pending["hinted"] == (outcome == "hint")
            await app.ai.close()

    asyncio.run(go())


@pytest.mark.parametrize("body", ["", " \n\t "])
def test_empty_session_reply_preserves_independent_credit_and_finishes_visibly(tmp_path, monkeypatch, body):
    app, vault = app_for(tmp_path, monkeypatch)
    app.settings.ai = False
    monkeypatch.setattr(app, "ai_available", lambda mode="ask": True)

    async def go():
        async with app.run_test(size=(80, 24)) as pilot:
            screen = SessionScreen({"mode": "autopilot", "minutes": 50})
            app.push_screen(screen)
            await pilot.pause()
            pending = app.tutor.session["presented"][str(screen.view["n"])]
            assert not pending["hinted"] and not pending["unassisted"]
            spoken = []
            monkeypatch.setattr(screen, "readable_now", lambda *args, **kwargs: spoken.append(args))

            async def stream(prompt, **kwargs):
                app.ai.last = ai.Result(text=body)
                if body:
                    yield body

            monkeypatch.setattr(app.ai, "stream", stream)
            screen.stream("Give me a hint")
            await app.workers.wait_for_complete()
            await pilot.pause()
            if shots := os.environ.get("BUGWATCH_UI_SHOTS"):
                app.save_screenshot(path=shots, filename=f"session-empty-{'whitespace' if body else 'blank'}.svg")
            assert not pending["hinted"], "A reply with no visible help must preserve independent-answer credit"
            latest = screen.query(".entry").last()
            assert latest.content.card[1] == "No AI reply"
            assert "Try asking again" in (vault / "Now.md").read_text()
            assert not spoken
            await app.ai.close()

    asyncio.run(go())
