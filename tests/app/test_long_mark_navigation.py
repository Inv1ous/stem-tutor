"""A pending AI check must keep the self-marking leave warning."""
import asyncio

import pytest

from test_tui import app_for, _open_long_and_submit, shot
from tutor_app import ai
from tutor_app.panels import TickPanel


@pytest.mark.parametrize("key", ["ctrl+b", "ctrl+q"])
@pytest.mark.parametrize("leave", [False, True], ids=["keep-marking", "leave"])
@pytest.mark.parametrize("valid", [False, True], ids=["unavailable", "valid-examiner"])
def test_leaving_during_long_ai_check_keeps_the_mark_choices_warning(tmp_path, monkeypatch, key, leave, valid):
    app, _ = app_for(tmp_path, monkeypatch)
    monkeypatch.setattr(app, "ai_available", lambda mode="explain": True)

    async def go():
        ready, release, cancelled = asyncio.Event(), asyncio.Event(), asyncio.Event()
        calls = []

        async def delayed(*args, **kwargs):
            calls.append(True)
            points = [{"point": f"{p.get('mark', '')} {p.get('point', '')}", "met": False}
                      for p in app.screen.scheme]
            ready.set()
            try:
                await release.wait()
            except asyncio.CancelledError:
                cancelled.set()
                raise
            return ({"points": points}, ai.Result()) if valid else (None, ai.Result(ok=False, message="Try marking yourself."))

        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            await _open_long_and_submit(pilot, app, "My working: v = u + at")
            screen = app.screen
            ticks = screen.query_one(TickPanel).query_one("#ticks")
            ticks.select(ticks.get_option_at_index(0).value)
            selected = list(ticks.selected)
            before_events = list(app.tutor.vault.events())
            monkeypatch.setattr(app.ai, "one_shot", delayed)
            await pilot.click("#ai")
            await ready.wait()
            await pilot.pause()
            suffix = f"{key.replace('+', '-')}-{'leave' if leave else 'stay'}-{'valid' if valid else 'unavailable'}"
            await shot(pilot, f"long-mark-pending-before-leave-{suffix}")
            await pilot.press(key)
            await pilot.pause()
            await shot(pilot, f"long-mark-pending-after-leave-{suffix}")
            try:
                assert app.screen.__class__.__name__ == "ConfirmScreen"
                assert "mark choices" in app.screen.question.lower()
                if leave:
                    await pilot.press("enter")
                    await pilot.pause()
                    assert app.screen.__class__.__name__ == "HomeScreen"
                    await asyncio.wait_for(cancelled.wait(), timeout=2)
                    menu = app.screen.query_one("#menu")
                    menu.reveal("resume")
                    await pilot.press("enter")
                    await pilot.pause()
                    resumed = app.screen
                    assert resumed.__class__.__name__ == "SessionScreen" and resumed is not screen
                    before_now = (app.vault / "Now.md").read_bytes()
                    release.set()
                    await app.workers.wait_for_complete()
                    await pilot.pause()
                    assert not screen.long_mark_pending and app.screen is resumed
                    assert (app.vault / "Now.md").read_bytes() == before_now
                else:
                    if valid:
                        release.set()  # the examiner may finish while the leave choice is still open
                        await app.workers.wait_for_complete()
                        await pilot.pause()
                        assert app.screen.__class__.__name__ == "ConfirmScreen"
                    await pilot.press("escape")
                    await pilot.pause()
                    assert app.screen is screen
                    release.set()
                    await app.workers.wait_for_complete()
                    await pilot.pause()
                    assert screen.query_one(TickPanel).query_one("#ticks").selected == ([] if valid else selected)
                    assert screen.query_one("#ticks").has_focus
                    assert not cancelled.is_set() and not screen.long_mark_pending
                assert calls == [True]
                assert list(app.tutor.vault.events()) == before_events
            finally:
                release.set()
                await app.ai.close()

    asyncio.run(go())
