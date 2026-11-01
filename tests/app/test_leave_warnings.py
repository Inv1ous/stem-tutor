"""Leaving before a submitted structured answer is marked must be an explicit choice."""
import asyncio

from test_tui import app_for
from tutor_app.panels import TickPanel
from tutor_app.screens import SessionScreen


def test_leaving_self_mark_panel_warns_that_mark_choices_will_be_lost(tmp_path, monkeypatch):
    app, _ = app_for(tmp_path, monkeypatch)

    async def run():
        async with app.run_test(size=(80, 24)) as pilot:
            screen = SessionScreen(None)
            await app.push_screen(screen)
            await pilot.pause()
            screen.panel(TickPanel("Review marks", [("M1 method", "1", True)], [("mine", "Submit")]))
            await pilot.pause()
            screen.action_leave()
            await pilot.pause()
            assert app.screen is not screen
            question = app.screen.question
            assert "mark choices" in question.lower()
            await pilot.press("escape")
            await pilot.pause()
            assert app.screen is screen
            assert screen.query_one("#ticks").selected == ["1"]
            await app.ai.close()

    asyncio.run(run())
