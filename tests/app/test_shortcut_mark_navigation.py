"""Unrecorded shortcut self-marks need the same leave choice as typed answers."""
import asyncio
import json
import os
from pathlib import Path

import pytest

import library_assets
from test_shortcuts_screen import events, open_from_menu, syllabus_files
from test_tui import app_for


def install_lesson(vault, item_id):
    entries = library_assets.read_json("Library/Shared/Shortcuts/Entries/9702.json")
    lessons = library_assets.read_json("Library/Courses/9702/Notes/Shortcuts/9702.json")
    entry = next(entry for entry in entries if entry["id"] == item_id)
    course = vault / ".tutor/shortcuts/course"
    (course / "lessons").mkdir(parents=True)
    (course / "9702.json").write_text(json.dumps([entry]))
    (course / "lessons/9702.json").write_text(json.dumps({item_id: lessons[item_id]}))


async def begin_practice(pilot, app):
    screen = await open_from_menu(pilot, app, "shortcuts", "ShortcutsScreen")
    await pilot.press("enter")
    while screen.phase == "reveal":
        await pilot.press("enter")
        await pilot.pause(.01)
    assert screen.phase == "practice"
    return screen


def capture(app, name):
    if directory := os.environ.get("B229_CAPTURE"):
        Path(directory).mkdir(parents=True, exist_ok=True)
        app.save_screenshot(name + ".svg", path=directory)


@pytest.mark.parametrize("size", [(80, 24), (100, 30)])
@pytest.mark.parametrize("key", ["escape", "ctrl+b"])
def test_pending_shortcut_mark_retains_answer_on_stay_and_requires_confirmed_leave(
        tmp_path, monkeypatch, size, key):
    app, vault = app_for(tmp_path, monkeypatch)
    install_lesson(vault, "SEM-9702-explain-mark-patterns")

    async def go():
        async with app.run_test(size=size) as pilot:
            await pilot.pause()
            protected = syllabus_files(vault)
            screen = await begin_practice(pilot, app)
            assert screen.kind == "short"
            draft = "The current decreases because voltage is fixed."
            await pilot.press(*draft, "enter", "down")
            await pilot.pause()
            assert screen.phase == "self-mark" and not events(vault)
            panel = screen.query_one(".sc-actions")
            assert panel.highlighted == 1
            card = screen.query_one("#card").render().plain
            assert draft in card
            prefix = f"{size[0]}-{key}"
            capture(app, prefix + "-pending")

            await pilot.press(key)
            await pilot.pause()
            capture(app, prefix + "-leave")
            assert type(app.screen).__name__ == "ConfirmScreen"
            assert "lost" in app.screen.question.lower()
            assert "mark" in app.screen.question.lower()
            assert not events(vault)
            await pilot.press("escape")
            await pilot.pause()
            assert app.screen is screen and screen.phase == "self-mark"
            assert screen.query_one("#card").render().plain == card
            assert screen.query_one(".sc-actions") is panel
            assert panel.highlighted == 1 and app.focused is panel

            await pilot.press("enter")  # Not quite: record this first answer once.
            await pilot.pause()
            assert screen.phase == "practice" and screen.pi == 1
            assert len(events(vault)) == 1 and events(vault)[0]["rating"] == 1
            await pilot.press(*"I need to link the changed quantity.", "enter")
            await pilot.pause()
            assert screen.phase == "self-mark"
            await pilot.press(key)
            await pilot.pause()
            assert type(app.screen).__name__ == "ConfirmScreen"
            await pilot.press("enter")  # Explicitly leave this still-unrecorded answer.
            await pilot.pause()
            assert type(app.screen).__name__ == "HomeScreen"
            assert len(events(vault)) == 1
            assert syllabus_files(vault) == protected
            await app.ai.close()

    asyncio.run(go())


@pytest.mark.parametrize("phase", ["blank", "typing", "recorded-feedback"])
def test_shortcut_leave_keeps_existing_unsubmitted_and_recorded_behavior(tmp_path, monkeypatch, phase):
    app, vault = app_for(tmp_path, monkeypatch)
    install_lesson(vault, "SEM-9702-ratio-proportionality-method")

    async def go():
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            screen = await begin_practice(pilot, app)
            if phase == "typing":
                await pilot.press("4")
            elif phase == "recorded-feedback":
                await pilot.press("4", "5", "enter")
                await pilot.pause()
                assert screen.phase == "feedback" and len(events(vault)) == 1
            await pilot.press("ctrl+b")
            await pilot.pause()
            if phase == "typing":
                assert type(app.screen).__name__ == "ConfirmScreen"
                await pilot.press("escape")
                await pilot.pause()
                assert app.screen is screen and screen.query_one(".sc-input").value == "4"
                assert not events(vault)
            else:
                assert type(app.screen).__name__ == "HomeScreen"
                assert len(events(vault)) == (1 if phase == "recorded-feedback" else 0)
            await app.ai.close()

    asyncio.run(go())
