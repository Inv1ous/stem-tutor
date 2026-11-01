"""Prepared More detail retains the unfinished inline question's next edit."""
import asyncio
from copy import deepcopy
import os
from pathlib import Path

import pytest
from textual.document._document import Selection
from textual.widgets import Button

import library_assets
from test_tui import app_for
from tutor_app.panels import ChoicePanel, Composer, ContinuePanel


DRAFT = 'Why does first ionisation energy change across this period?\nHow does ΔE relate to the 1+ ion?'


def capture(app, name):
    if directory := os.environ.get("B241_SHOTS"):
        Path(directory).mkdir(parents=True, exist_ok=True)
        app.save_screenshot(name + ".svg", path=directory)


async def open_detail(pilot, app):
    menu = app.screen.query_one("#menu")
    menu.highlighted = [option.id for option in menu.options].index("learn")
    await pilot.press("enter")
    await pilot.pause()
    await pilot.press("slash", *"9701-1.4", "enter")
    await pilot.pause()
    await pilot.press("enter")  # Learn properly from scratch.
    await pilot.pause()
    screen = app.screen
    assert screen.act["activity"] == "plan"
    screen.query_one("#start", Button).focus()
    await pilot.press("enter")
    await pilot.pause()
    for _ in range(14):
        if screen.query("#detail"):
            return screen
        panel = screen.query_one("#panel > *")
        if isinstance(panel, ChoicePanel):
            pending = app.tutor.session["presented"][str(screen.view["n"])]
            await pilot.press(pending["inst"]["answer"].lower(), "4")
        elif isinstance(panel, ContinuePanel):
            panel.query(Button).first().focus()
            await pilot.press("enter")
        else:
            raise AssertionError((screen.act, type(panel).__name__))
        await pilot.pause()
    raise AssertionError("The prepared lesson did not reach its plain-words detail control")


@pytest.mark.parametrize("case,selection,size", [
    ("range", Selection((0, 9), (0, 32)), (80, 24)),
    ("reverse", Selection((0, 32), (0, 9)), (100, 30)),
    ("caret", Selection((1, 9), (1, 9)), (80, 24)),
    ("empty", Selection((0, 0), (0, 0)), (100, 30)),
])
def test_more_detail_preserves_inline_selection_without_advancing(tmp_path, monkeypatch, case, selection, size):
    app, vault = app_for(tmp_path, monkeypatch)
    app.settings.ai = False
    library_assets.install_course(vault, "9701", "9701-1.4")

    async def go():
        async with app.run_test(size=size) as pilot:
            await pilot.pause()
            calls = []

            async def unexpected(*args, **kwargs):
                calls.append(args)
                raise AssertionError("Prepared detail must not request a model")

            async def unexpected_stream(*args, **kwargs):
                await unexpected(*args, **kwargs)
                yield ""

            monkeypatch.setattr(app.ai, "one_shot", unexpected)
            monkeypatch.setattr(app.ai, "stream", unexpected_stream)
            screen = await open_detail(pilot, app)
            assert screen.act.get("detail")
            await pilot.press("ctrl+t")
            await pilot.pause()
            box = screen.query_one("#learning-question", Composer)
            draft = "" if case == "empty" else DRAFT
            box.text, box.selection = draft, selection
            tutor = app.tutor
            activity, state = screen.act, deepcopy(tutor.state)
            cursor, blocks = tutor.session["cursor"], deepcopy(tutor.session["blocks"])
            events = {path: path.read_bytes() for path in tutor.vault.tutor.glob("events/*.jsonl")}
            pack_path = vault / ".tutor/packs/v1/specs/9701/packs/9701-1.4.json"
            source = pack_path.read_bytes()
            capture(app, case + "-before")
            screen.query_one("#detail", Button).focus()
            await pilot.press("enter")
            await pilot.pause()
            assert app.focused.id == "continue" and not screen.query("#detail")
            assert "More detail" in (vault / "Now.md").read_text()
            assert screen.act is activity and tutor.session["awaiting"] is activity
            assert tutor.session["cursor"] == cursor and tutor.session["blocks"] == blocks
            assert tutor.state == state and not calls
            assert all(path.read_bytes() == data for path, data in events.items())
            assert pack_path.read_bytes() == source
            capture(app, case + "-detail")
            if case == "empty":
                box = screen.query_one("#learning-question", Composer)
                assert box.text == "" and box.selection == selection
                await pilot.press("enter")  # The existing focused Continue route still advances normally.
                await pilot.pause()
                assert screen.act is not activity and not calls
            else:
                await pilot.press("ctrl+t")
                await pilot.pause()
                box = screen.query_one("#learning-question", Composer)
                assert box.text == draft and box.has_focus
                restored = box.selection
                await pilot.press("X")
                await pilot.pause()
                lines = draft.splitlines(keepends=True)
                offsets = sorted(sum(len(line) for line in lines[:row]) + col for row, col in
                                 (selection.start, selection.end))
                assert box.text == draft[:offsets[0]] + "X" + draft[offsets[1]:]
                assert restored == selection
                assert screen.act is activity and tutor.session["awaiting"] is activity and not calls
                if case == "range":
                    current = Selection((1, 0), (1, 3))
                    box.selection = current
                    text = box.text
                    for resized in ((120, 40), size):
                        await pilot.resize_terminal(*resized)
                        await pilot.pause()
                    box = screen.query_one("#learning-question", Composer)
                    assert box.text == text and box.selection == current and box.has_focus
                capture(app, case + "-edited")
            await app.ai.close()

    asyncio.run(go())
