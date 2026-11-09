"""Test-selection shortcuts must not consume ordinary search editing in other pickers."""
import asyncio
from copy import deepcopy

import pytest

from test_tui import app_for, shot


@pytest.mark.parametrize("route", ["learn", "long", "blurt"])
@pytest.mark.parametrize("shortcut", ["ctrl+a", "ctrl+d"])
def test_non_test_picker_search_keeps_native_input_editing(tmp_path, monkeypatch, route, shortcut):
    app, _ = app_for(tmp_path, monkeypatch)
    app.settings.ai = False

    async def go():
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            menu = app.screen.query_one("#menu")
            menu.reveal(route)
            await pilot.press("enter")
            await pilot.pause()
            picker = app.screen
            await pilot.press("slash")
            await pilot.press(*("motion" if shortcut == "ctrl+a" else "mmotion"))
            await pilot.pause()
            box = picker.query_one("#find")
            state, events = deepcopy(app.tutor.state), list(app.tutor.vault.events())
            if shortcut == "ctrl+a":
                await pilot.press("ctrl+a", *"9702 ")  # Input's standard go-to-start binding
                expected = "9702 motion"
            else:
                await pilot.press("home", "ctrl+d")  # delete the duplicate leading letter
                expected = "motion"
            await pilot.pause()
            await shot(pilot, f"picker-edit-{route}-{shortcut.replace('+', '-')}")
            assert box.value == expected and box.has_focus
            assert {option.id for option in picker.query_one("#subs").options if not option.disabled} == {"9702-2.1"}
            assert "Search: 1 of 1 subtopics" in str(picker.query_one("#found").content)
            assert not picker.ticked and app.tutor.session is None
            assert app.tutor.state == state and list(app.tutor.vault.events()) == events
            await pilot.press("down", "enter")
            await pilot.pause()
            assert app.screen.__class__.__name__ == ("BlurtScreen" if route == "blurt" else "SessionScreen")
            if route != "blurt":
                assert app.tutor.session["mode"] == ("lesson" if route == "learn" else "long")
            await app.ai.close()

    asyncio.run(go())


def test_test_picker_keeps_its_documented_tick_shortcuts_while_searching(tmp_path, monkeypatch):
    app, _ = app_for(tmp_path, monkeypatch)
    app.settings.ai = False

    async def go():
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            menu = app.screen.query_one("#menu")
            app.screen.activate("test")  # an old id: no longer in the menu, still starts the picker
            await pilot.pause()
            picker = app.screen
            await pilot.press("slash", *"motion", "ctrl+a")
            await pilot.pause()
            assert picker.ticked == {"9702-2.1"} and picker.query_one("#find").value == "motion"
            await pilot.press("ctrl+d")
            await pilot.pause()
            assert not picker.ticked and picker.query_one("#find").value == "motion"
            assert picker.query_one("#find").has_focus and app.tutor.session is None
            await app.ai.close()

    asyncio.run(go())
