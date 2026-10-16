import asyncio

from test_tui import app_for
from tutor_app.screens import SessionScreen


def test_ctrl_k_hides_the_question_and_keeps_only_the_answer_box(tmp_path, monkeypatch):
    app, v = app_for(tmp_path, monkeypatch)

    async def go():
        async with app.run_test(size=(60, 30)) as pilot:
            await pilot.pause()
            scr = SessionScreen({"mode": "test", "minutes": 40, "focus": ["9702-2.1"]})
            app.push_screen(scr)
            await pilot.pause()
            await pilot.pause()
            log, panel = scr.query_one("#log"), scr.query_one("#panel")
            assert log.display and not scr.has_class("answer-only")
            await pilot.press("ctrl+k")
            await pilot.pause()
            assert scr.has_class("answer-only") and not log.display
            assert panel.region.height > 0 and panel.region.height >= 10  # the answer box takes the room
            assert app.settings.answer_only
            await pilot.press("ctrl+k")  # and back again
            await pilot.pause()
            assert log.display and not scr.has_class("answer-only") and not app.settings.answer_only
            await app.ai.close()
    asyncio.run(go())


def test_the_choice_is_remembered_and_applies_to_the_next_session(tmp_path, monkeypatch):
    app, v = app_for(tmp_path, monkeypatch)

    async def go():
        async with app.run_test(size=(60, 30)) as pilot:
            await pilot.pause()
            await pilot.press("f3")
            await pilot.pause()
            assert app.settings.answer_only
            scr = SessionScreen({"mode": "test", "minutes": 40, "focus": ["9702-2.1"]})
            app.push_screen(scr)
            await pilot.pause()
            await pilot.pause()
            assert scr.has_class("answer-only") and not scr.query_one("#log").display
            await app.ai.close()
    asyncio.run(go())
    from tutor_app.config import Settings
    assert Settings.load(v).answer_only is True
