"""An ungraded numeric refusal returns to the same correctable editor."""
import asyncio
from copy import deepcopy
import os
from pathlib import Path

import pytest
from textual.document._document import Selection
from textual.widgets import Button

import library_assets
from test_tui import app_for
from tutor_app.panels import Composer, Confidence, ValuePanel


async def open_numeric(pilot, app):
    menu = app.screen.query_one("#menu")
    menu.highlighted = [option.id for option in menu.options].index("learn")
    await pilot.press("enter")
    await pilot.pause()
    await pilot.press("enter")
    await pilot.pause()
    await pilot.press("down", "enter")
    await pilot.pause()
    screen = app.screen
    pending = app.tutor.session["presented"][str(screen.view["n"])]
    await pilot.press(pending["inst"]["answer"].lower(), "4")
    await pilot.pause()
    screen.query_one("#next", Button).focus()
    await pilot.press("enter")
    await pilot.pause()
    assert screen.view["kind"] == "numeric"
    return screen


def capture(app, name):
    if directory := os.environ.get("B251_SHOTS"):
        Path(directory).mkdir(parents=True, exist_ok=True)
        app.save_screenshot(name + ".svg", path=directory)


@pytest.mark.parametrize("case,size,selection", [
    ("range", (80, 24), Selection((0, 1), (0, 2))),
    ("reverse", (100, 30), Selection((0, 2), (0, 1))),
    ("multiline", (80, 24), Selection((0, 1), (0, 2))),
    ("caret", (100, 30), Selection((0, 2), (0, 2))),
    ("valid", (100, 30), Selection((0, 1), (0, 2))),
    ("refusal", (100, 30), Selection((0, 1), (0, 2))),
])
def test_numeric_correction_preserves_editor_and_records_only_the_valid_attempt(
        tmp_path, monkeypatch, case, size, selection):
    app, vault = app_for(tmp_path, monkeypatch)
    app.settings.ai = False
    library_assets.install_course(vault, "9702", "9702-2.1")
    notices = []
    notify = app.notify

    def warned(message, **kwargs):
        notices.append(str(message))
        notify(message, **kwargs)

    monkeypatch.setattr(app, "notify", warned)

    async def go():
        async with app.run_test(size=size, notifications=True) as pilot:
            await pilot.pause()
            screen = await open_numeric(pilot, app)
            tutor = app.tutor
            panel = screen.query_one(ValuePanel)
            box = panel.query_one("#value", Composer)
            number = str(screen.view["n"])
            session, state = deepcopy(tutor.session), deepcopy(tutor.state)
            events = {path: path.read_bytes() for path in tutor.vault.tutor.glob("events/*.jsonl")}
            await pilot.press("enter")  # An empty value remains an unsubmitted editor.
            await pilot.pause()
            assert box.has_focus and not panel.query(Confidence)
            draft = ("4.5 m s-2" if case in ("valid", "refusal") else
                     "4,5\nm s-2" if case == "multiline" else "4,5 m s-2")
            box.text, box.selection = draft, selection
            capture(app, case + "-before")
            await pilot.press("enter")
            await pilot.pause()
            if case == "valid":
                await pilot.press("escape")  # Existing confidence→edit behavior remains unchanged.
            elif case == "refusal":
                refusal = "Wait for the saved attempt to finish recovering."
                with monkeypatch.context() as patch:
                    patch.setattr(tutor, "answer", lambda *args, **kwargs: {
                        "results": [{"n": int(number), "error": refusal}]})
                    await pilot.press("4")
                    await pilot.pause()
            else:
                await pilot.press("4")
            await pilot.pause()
            capture(app, case + "-editable")
            assert screen.query_one(ValuePanel) is panel and panel.query_one("#value", Composer) is box
            assert box.text == draft and box.selection == selection and box.has_focus and not box.disabled
            assert not panel.query(Confidence)
            assert tutor.session == session and tutor.state == state
            assert all(path.read_bytes() == data for path, data in events.items())
            assert app.ai.session.replies == 0
            if case == "refusal":
                assert notices[-1] == refusal
            elif case != "valid":
                assert notices and "<number>" not in notices[-1] and "~<1-4>" not in notices[-1]
                if case == "caret":
                    await pilot.press("backspace")
                await pilot.press(".")
                assert box.text == draft.replace(",", ".")
            await pilot.press("enter")
            await pilot.pause()
            await pilot.press("4")
            await pilot.pause()
            assert number not in tutor.session["presented"]
            answers = [event for event in tutor.vault.events() if event["type"] == "answer"]
            assert len(answers) == 2 and answers[-1]["grade"]["correct"]  # one prior MCQ, one corrected numeric answer
            assert app.ai.session.replies == 0
            capture(app, case + "-marked-once")
            await app.ai.close()

    asyncio.run(go())
