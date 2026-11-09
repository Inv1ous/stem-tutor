"""Solvability belongs to the open question, rather than its completed feedback."""
import asyncio
from copy import deepcopy
import os
from pathlib import Path

import pytest
from textual.widgets import Button

import library_assets
from test_tui import app_for, _open_long_and_submit
from tutor_app.panels import Composer, TickPanel


def capture(app, name):
    if directory := os.environ.get("Q038_SHOTS"):
        Path(directory).mkdir(parents=True, exist_ok=True)
        app.save_screenshot(name + ".svg", path=directory)


def protected(tutor):
    return {path: path.read_bytes() for path in
            [tutor.session_path, *tutor.vault.tutor.glob("events/*.jsonl")]}


@pytest.mark.parametrize("size", [(80, 24), (100, 30)])
@pytest.mark.parametrize("answer", ["right", "skip"])
def test_completed_mcq_hides_solvability_and_next_or_retry_restores_it(tmp_path, monkeypatch, size, answer):
    app, vault = app_for(tmp_path, monkeypatch)
    app.settings.ai = False
    library_assets.install_course(vault, "9702", "9702-2.1")

    async def go():
        async with app.run_test(size=size) as pilot:
            await pilot.pause()
            menu = app.screen.query_one("#menu")
            menu.reveal("learn")
            await pilot.press("enter")
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            await pilot.press("down", "enter")  # Find and fill my gaps: a no-help check.
            await pilot.pause()
            screen, tutor = app.screen, app.tutor
            checker = screen.query_one("#check-solvable", Button)
            assert screen.view["kind"] == "mcq" and screen.view["unassisted"] and checker.display
            original = deepcopy(screen.view)
            pending = tutor.session["presented"][str(screen.view["n"])]
            await pilot.press("0" if answer == "skip" else pending["inst"]["answer"].lower())
            if answer == "right":
                await pilot.press("4")
            await pilot.pause()
            assert str(screen.view["n"]) not in tutor.session["presented"]
            before = protected(tutor)
            session = deepcopy(tutor.session)
            now = (vault / "Now.md").read_bytes()
            entries = list(screen.query(".entry"))
            focus = app.focused
            capture(app, f"{answer}-{size[0]}-feedback")
            assert not checker.display
            await pilot.press("ctrl+y")
            await pilot.pause()
            await app.workers.wait_for_complete()  # the check runs in a worker
            await pilot.pause()
            assert list(screen.query(".entry")) == entries and app.focused is focus
            assert screen.view == original and tutor.session == session
            assert (vault / "Now.md").read_bytes() == now
            assert all(path.read_bytes() == data for path, data in before.items())
            if answer == "skip":
                await pilot.press("ctrl+u")
            else:
                screen.query_one("#next", Button).focus()
                await pilot.press("enter")
            await pilot.pause()
            assert str(screen.view["n"]) in tutor.session["presented"] and checker.display
            if answer == "right":
                assert screen.view["kind"] == "numeric"
                composer = screen.query_one("#value", Composer)
                composer.text = "4.5 m s-1"
                composer.move_cursor((0, 3))
                selection = composer.selection
                focus = app.focused
            before = protected(tutor)
            session = deepcopy(tutor.session)
            await pilot.press("ctrl+y")
            await pilot.pause()
            await app.workers.wait_for_complete()  # the check runs in a worker
            await pilot.pause()
            if answer == "right":
                assert app.focused is focus
                assert composer.text == "4.5 m s-1" and composer.selection == selection
            assert {key: value for key, value in tutor.session.items() if key != "thread"} == {
                key: value for key, value in session.items() if key != "thread"}
            assert all(path.read_bytes() == data for path, data in before.items() if path != tutor.session_path)
            assert screen.query(".entry").last().content.card[1] == "Can I solve this?"
            capture(app, f"{answer}-{size[0]}-open-again")
            await app.ai.close()

    asyncio.run(go())


@pytest.mark.parametrize("size", [(80, 24), (100, 30)])
def test_structured_self_mark_keeps_solvability_until_marks_are_submitted(tmp_path, monkeypatch, size):
    app, _ = app_for(tmp_path, monkeypatch)
    app.settings.ai = False

    async def go():
        async with app.run_test(size=size) as pilot:
            await pilot.pause()
            await _open_long_and_submit(pilot, app, "My working: v = u + at")
            screen, tutor = app.screen, app.tutor
            checker = screen.query_one("#check-solvable", Button)
            assert checker.display and str(screen.view["n"]) in tutor.session["presented"]
            ticks = screen.query_one(TickPanel).query_one("#ticks")
            ticks.select(ticks.get_option_at_index(0).value)
            selected = list(ticks.selected)
            before = protected(tutor)
            session = deepcopy(tutor.session)
            await pilot.press("ctrl+y")
            await pilot.pause()
            await app.workers.wait_for_complete()  # the check runs in a worker
            await pilot.pause()
            assert ticks.has_focus and list(ticks.selected) == selected
            assert checker.display
            assert {key: value for key, value in tutor.session.items() if key != "thread"} == {
                key: value for key, value in session.items() if key != "thread"}
            assert all(path.read_bytes() == data for path, data in before.items() if path != tutor.session_path)
            screen.query_one("#mine", Button).focus()
            await pilot.press("enter")
            await pilot.pause()
            capture(app, f"structured-{size[0]}-feedback")
            assert str(screen.view["n"]) not in tutor.session["presented"] and not checker.display
            before, entries, focus = protected(tutor), list(screen.query(".entry")), app.focused
            await pilot.press("ctrl+y")
            await pilot.pause()
            await app.workers.wait_for_complete()  # the check runs in a worker
            await pilot.pause()
            assert list(screen.query(".entry")) == entries and app.focused is focus
            assert all(path.read_bytes() == data for path, data in before.items())
            await app.ai.close()

    asyncio.run(go())
