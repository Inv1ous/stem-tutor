"""Shortcut log scrolling preserves reveal state, drafts and native list keys."""
import asyncio
from copy import deepcopy
from datetime import timedelta
import os
from pathlib import Path

import pytest
from textual.widgets import Input

import library_assets
from test_session import T0
from test_shortcuts_screen import events, open_from_menu
from test_tui import app_for
from tutorlib import shortcuts as sc


async def open_lesson(pilot, app):
    screen = await open_from_menu(pilot, app, "shortcuts", "ShortcutsScreen")
    await pilot.press("enter")
    await pilot.pause()
    return screen


def install_lesson(vault, item_id):
    """Keep exact real JSON in Library and expose only read-only legacy file adapters."""
    library_assets.install_course(vault, "9702", "9702-2.1")
    entries_path = library_assets.copy_to_vault("Library/Shared/Shortcuts/Entries/9702.json", vault)
    lessons_path = library_assets.copy_to_vault("Library/Courses/9702/Notes/Shortcuts/9702.json", vault)
    course = vault / ".tutor/shortcuts/course"
    (course / "lessons").mkdir(parents=True)
    (course / "9702.json").symlink_to(entries_path)
    (course / "lessons/9702.json").symlink_to(lessons_path)
    entries = library_assets.read_json("Library/Shared/Shortcuts/Entries/9702.json")
    target = next(entry for entry in entries if entry["id"] == item_id)
    sc.save_config(vault, {"sections": [target["section"]], "min_score": target["score"],
                           "max_score": target["score"], "specs": ["9702"], "lessons_only": True})
    learner = sc.Course(vault)
    for entry in learner.entries():
        if entry["id"] != item_id:
            learner.record("learn", entry["id"], 3, now=T0 - timedelta(days=40))
    assert learner.next_lessons()[0]["id"] == item_id
    return {path: path.read_bytes() for path in (entries_path, lessons_path)}


def capture(app, name):
    if directory := os.environ.get("Q040_SHOTS"):
        Path(directory).mkdir(parents=True, exist_ok=True)
        app.save_screenshot(name + ".svg", path=directory)


@pytest.mark.parametrize("size", [(80, 24), (100, 30)])
@pytest.mark.parametrize("up,down", [("pageup", "pagedown"), ("alt+up", "alt+down")])
def test_shortcut_explanation_scroll_preserves_revealed_steps(tmp_path, monkeypatch, size, up, down):
    app, vault = app_for(tmp_path, monkeypatch)
    app.settings.ai = False
    sources = install_lesson(vault, "SEM-9702-kirchhoff")

    async def go():
        async with app.run_test(size=size) as pilot:
            await pilot.pause()
            screen = await open_lesson(pilot, app)
            while screen.phase == "reveal" and screen.shown < len(screen.secs):
                await pilot.press("enter")
                await pilot.pause()
            log = screen.query_one("#log")
            assert screen.phase == "reveal" and log.max_scroll_y > 0 and log.scroll_y == log.max_scroll_y
            shown, queue, before = screen.shown, deepcopy(screen.queue), events(vault)
            capture(app, f"{size[0]}-{up}-before")
            await pilot.press(up)
            await pilot.pause()
            assert log.scroll_y < log.max_scroll_y
            capture(app, f"{size[0]}-{up}-earlier")
            await pilot.press(down)
            await pilot.pause()
            assert log.scroll_y == log.max_scroll_y
            assert screen.phase == "reveal" and screen.shown == shown and screen.queue == queue
            assert events(vault) == before and all(path.read_bytes() == data for path, data in sources.items())
            await pilot.press("left")
            await pilot.pause()
            assert screen.phase == "reveal" and screen.shown == shown - 1
            await pilot.press("enter")
            await pilot.pause()
            assert screen.phase == "reveal" and screen.shown == shown
            await pilot.press("enter")
            await pilot.pause()
            assert screen.phase == "practice" and events(vault) == before
            await app.ai.close()

    asyncio.run(go())


def test_shortcut_scroll_keeps_numeric_draft_and_focus(tmp_path, monkeypatch):
    app, vault = app_for(tmp_path, monkeypatch)
    app.settings.ai = False
    sources = install_lesson(vault, "SEM-9702-ratio-proportionality-method")

    async def go():
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            screen = await open_lesson(pilot, app)
            while screen.phase == "reveal":
                await pilot.press("enter")
                await pilot.pause()
            assert screen.phase == "practice" and screen.kind == "numeric"
            box = screen.query_one(".sc-input", Input)
            await pilot.press("4", "5", "home", "shift+right")
            draft, selection, before = box.value, box.selection, events(vault)
            for key in ("alt+up", "alt+down"):
                await pilot.press(key)
                await pilot.pause()
                assert box.has_focus and box.value == draft and box.selection == selection
            assert screen.phase == "practice" and events(vault) == before
            assert all(path.read_bytes() == data for path, data in sources.items())
            capture(app, "numeric-draft-kept")
            await app.ai.close()

    asyncio.run(go())


def test_shortcut_choices_keep_native_page_keys_and_mark_once(tmp_path, monkeypatch):
    app, vault = app_for(tmp_path, monkeypatch)
    app.settings.ai = False
    sources = install_lesson(vault, "SEM-9702-explain-mark-patterns")

    async def go():
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            screen = await open_lesson(pilot, app)
            while screen.phase == "reveal":
                await pilot.press("enter")
                await pilot.pause()
            await pilot.press(*"My answer links the quantity and its effect.", "enter")
            await pilot.pause()
            assert screen.phase == "self-mark"
            choices = screen.query_one(".sc-actions")
            await pilot.press("down", "pageup")
            await pilot.pause()
            assert choices.highlighted == 0 and choices.has_focus
            before = events(vault)
            for key in ("alt+up", "alt+down"):
                await pilot.press(key)
                await pilot.pause()
                assert choices.highlighted == 0 and choices.has_focus
            await pilot.press("pagedown")
            await pilot.pause()
            assert choices.highlighted == 1 and screen.phase == "self-mark" and events(vault) == before
            await pilot.press("enter")
            await pilot.pause()
            assert len(events(vault)) == len(before) + 1 and events(vault)[-1]["rating"] == 1
            assert all(path.read_bytes() == data for path, data in sources.items())
            capture(app, "list-routing-kept")
            await app.ai.close()

    asyncio.run(go())
