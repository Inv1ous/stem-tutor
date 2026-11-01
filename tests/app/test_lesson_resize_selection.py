"""Resizing an inline lesson question must retain where its next edit belongs."""
import asyncio
from copy import deepcopy
import os
from pathlib import Path

import pytest
from textual.document._document import Selection
from textual.widgets import Button

import library_assets
from test_tui import app_for
from tutor_app.panels import Composer


DRAFT = 'Why does average velocity depend on Δx?\nDoes “speed” change the answer?'


def capture(app, name):
    if directory := os.environ.get("B237_SHOTS"):
        Path(directory).mkdir(parents=True, exist_ok=True)
        app.save_screenshot(name + ".svg", path=directory)


async def open_inline(pilot, app):
    menu = app.screen.query_one("#menu")
    menu.highlighted = [option.id for option in menu.options].index("learn")
    await pilot.press("enter")
    await pilot.pause()
    await pilot.press("enter")  # The installed topic.
    await pilot.pause()
    await pilot.press("enter")  # Learn it properly from scratch.
    await pilot.pause()
    screen = app.screen
    assert screen.act["activity"] == "plan"
    screen.query_one("#start", Button).focus()
    await pilot.press("enter")
    await pilot.pause()
    await pilot.press("ctrl+t")
    return screen


@pytest.mark.parametrize("case,selection,small", [
    ("range", Selection((0, 9), (0, 25)), (80, 24)),
    ("caret", Selection((0, 9), (0, 9)), (80, 24)),
    ("modal", Selection((0, 25), (0, 9)), (80, 24)),
    ("same-shape", Selection((0, 9), (0, 25)), (110, 40)),
])
def test_lesson_resize_keeps_inline_edit_position_and_focus(tmp_path, monkeypatch, case, selection, small):
    app, vault = app_for(tmp_path, monkeypatch)
    app.settings.ai = False
    library_assets.install_course(vault, "9702", "9702-2.1")

    async def go():
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            calls = []

            async def unexpected(*args, **kwargs):
                calls.append(args)
                raise AssertionError("Editing and resizing must not request a model")

            async def unexpected_stream(*args, **kwargs):
                await unexpected(*args, **kwargs)
                yield ""

            monkeypatch.setattr(app.ai, "one_shot", unexpected)
            monkeypatch.setattr(app.ai, "stream", unexpected_stream)
            screen = await open_inline(pilot, app)
            box = screen.query_one("#learning-question", Composer)
            assert box.has_focus
            box.text = DRAFT
            box.selection = selection
            await pilot.pause()
            tutor = app.tutor
            state, session = deepcopy(tutor.state), deepcopy(tutor.session)
            protected = {path: path.read_bytes() for path in
                         [tutor.session_path, vault / "Now.md", *tutor.vault.tutor.glob("events/*.jsonl")]}
            pack_path = vault / ".tutor/packs/v1/specs/9702/packs/9702-2.1.json"
            source = pack_path.read_bytes()
            original_box = box
            if case == "modal":
                screen.query_one("#learn", Button).focus()
                await pilot.press("question_mark")
                await pilot.pause()
                modal = app.screen
                assert type(modal).__name__ == "HelpScreen"
                modal.query_one("#help").focus()
                modal_focus = app.focused
            capture(app, case + "-before")

            for size in (small, (120, 40)):
                await pilot.resize_terminal(*size)
                await pilot.pause()
                if case == "modal":
                    assert app.screen is modal and app.focused is modal_focus
                else:
                    assert app.screen is screen and screen.query_one("#learning-question", Composer).has_focus
            if case == "modal":
                await pilot.press("escape")
                await pilot.pause()
                assert app.screen is screen and app.focused.id == "learn"
                await pilot.press("ctrl+t")
                await pilot.pause()
            box = screen.query_one("#learning-question", Composer)
            assert (box is original_box) == (case == "same-shape")
            assert box.text == DRAFT and box.has_focus
            capture(app, case + "-after-resize")
            await pilot.press("X")
            await pilot.pause()
            capture(app, case + "-after-edit")
            start, end = sorted((selection.start[1], selection.end[1]))
            assert box.text == DRAFT[:start] + "X" + DRAFT[end:]
            assert tutor.state == state and tutor.session == session and not calls
            assert all(path.read_bytes() == content for path, content in protected.items())
            assert pack_path.read_bytes() == source
            await app.ai.close()

    asyncio.run(go())
