"""Rapid duplicate numeric-format notices leave the correctable editor visible."""
import asyncio
from copy import deepcopy
import os
from pathlib import Path

import pytest
from textual.document._document import Selection

import library_assets
from test_numeric_refusal_editing import open_numeric
from test_tui import app_for
from tutor_app import screens
from tutor_app.panels import Composer, Confidence, ValuePanel


def setup_app(tmp_path, monkeypatch):
    app, vault = app_for(tmp_path, monkeypatch)
    app.settings.ai = False
    library_assets.install_course(vault, "9702", "9702-2.1")
    notices, notify = [], app.notify

    def observed(message, **kwargs):
        notices.append((str(message), kwargs))
        return notify(message, **kwargs)

    monkeypatch.setattr(app, "notify", observed)
    return app, notices


def format_notices(notices):
    return [(message, kwargs) for message, kwargs in notices if "Edit your value below" in message]


def capture(app, name):
    if directory := os.environ.get("Q041_SHOTS"):
        Path(directory).mkdir(parents=True, exist_ok=True)
        app.save_screenshot(path=directory, filename=name + ".svg")


async def refuse(pilot, box, text="4,5 m s-2"):
    box.text = text
    box.selection = Selection((0, 1), (0, 2))
    await pilot.press("enter")
    await pilot.pause()
    await pilot.press("4")
    await pilot.pause()


@pytest.mark.parametrize("size", [(80, 24), (100, 30)])
def test_same_format_warning_coalesces_and_corrected_answer_marks_once(tmp_path, monkeypatch, size):
    app, notices = setup_app(tmp_path, monkeypatch)

    async def go():
        async with app.run_test(size=size, notifications=True) as pilot:
            await pilot.pause()
            screen = await open_numeric(pilot, app)
            tutor = app.tutor
            panel = screen.query_one(ValuePanel)
            box = panel.query_one("#value", Composer)
            number = str(screen.view["n"])
            state, session = deepcopy(tutor.state), deepcopy(tutor.session)
            events = {path: path.read_bytes() for path in tutor.vault.tutor.glob("events/*.jsonl")}
            before = [event for event in tutor.vault.events() if event["type"] == "answer"]
            for _ in range(3):
                await refuse(pilot, box)
                assert screen.query_one(ValuePanel) is panel and box.has_focus and not box.disabled
                assert box.text == "4,5 m s-2" and box.selection == Selection((0, 1), (0, 2))
                assert not panel.query(Confidence) and tutor.state == state and tutor.session == session
                assert all(path.read_bytes() == data for path, data in events.items())
            capture(app, f"coalesced-{size[0]}")
            assert len(format_notices(notices)) == 1
            assert format_notices(notices)[0][1] == {"severity": "warning", "timeout": 6}
            await pilot.press(".", "enter")
            await pilot.pause()
            await pilot.press("4")
            await pilot.pause()
            answers = [event for event in tutor.vault.events() if event["type"] == "answer"]
            assert number not in tutor.session["presented"]
            assert len(answers) == len(before) + 1 and answers[-1]["grade"]["correct"]
            assert app.ai.session.replies == 0
            capture(app, f"marked-once-{size[0]}")
            await app.ai.close()

    asyncio.run(go())


def test_distinct_errors_and_original_deadline_remain_independent(tmp_path, monkeypatch):
    app, notices = setup_app(tmp_path, monkeypatch)
    clock = [1000.0]
    monkeypatch.setattr(screens, "monotonic", lambda: clock[0], raising=False)

    async def go():
        async with app.run_test(size=(100, 30), notifications=True) as pilot:
            await pilot.pause()
            screen = await open_numeric(pilot, app)
            box = screen.query_one("#value", Composer)
            tutor = app.tutor
            state, session = deepcopy(tutor.state), deepcopy(tutor.session)
            events = list(tutor.vault.events())
            await refuse(pilot, box)
            clock[0] = 1001.0
            await refuse(pilot, box, "4,6 m s-2")
            clock[0] = 1002.0
            await refuse(pilot, box)
            assert len(format_notices(notices)) == 2  # A/B/A retains one notice for each exact message.
            app.notify("A separate note remains visible.", severity="information", timeout=9)
            refusal = "Wait for the saved attempt to finish recovering."
            with monkeypatch.context() as patch:
                patch.setattr(tutor, "answer", lambda *args, **kwargs: {
                    "results": [{"n": screen.view["n"], "error": refusal}]})
                for _ in range(2):
                    await refuse(pilot, box)
            assert sum(message == refusal for message, _ in notices) == 2
            assert sum(message == "A separate note remains visible." for message, _ in notices) == 1
            clock[0] = 1005.9
            await refuse(pilot, box)
            assert len(format_notices(notices)) == 2
            clock[0] = 1006.1
            await refuse(pilot, box)
            assert len(format_notices(notices)) == 3  # Repeats did not extend the first six-second deadline.
            assert box.has_focus and box.text == "4,5 m s-2"
            assert box.selection == Selection((0, 1), (0, 2))
            assert tutor.state == state and tutor.session == session and list(tutor.vault.events()) == events
            assert app.ai.session.replies == 0
            await app.ai.close()

    asyncio.run(go())


def test_new_retry_question_gets_its_own_format_warning(tmp_path, monkeypatch):
    app, notices = setup_app(tmp_path, monkeypatch)
    monkeypatch.setattr(screens, "monotonic", lambda: 1000.0, raising=False)

    async def go():
        async with app.run_test(size=(100, 30), notifications=True) as pilot:
            await pilot.pause()
            screen = await open_numeric(pilot, app)
            number = str(screen.view["n"])
            box = screen.query_one("#value", Composer)
            await refuse(pilot, box)
            assert len(format_notices(notices)) == 1
            box.text = "?"
            await pilot.press("enter")
            await pilot.pause()
            assert number not in app.tutor.session["presented"]
            await pilot.press("ctrl+u")
            await pilot.pause()
            assert screen.view["kind"] == "numeric" and str(screen.view["n"]) != number
            box = screen.query_one("#value", Composer)
            await refuse(pilot, box)
            assert len(format_notices(notices)) == 2
            assert box.has_focus and box.text == "4,5 m s-2" and app.ai.session.replies == 0
            await app.ai.close()

    asyncio.run(go())
