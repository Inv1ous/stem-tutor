"""End-to-end proof on a scratch copy of the learner vault, driven through the Textual pilot.

The real vault is only read: ``.tutor`` is copied and ``Library`` is cloned into a disposable
directory, so every event, session and note this flow writes lands in the copy.
"""
from __future__ import annotations

import asyncio
import os
import subprocess
import traceback
from contextlib import asynccontextmanager
from io import StringIO
from pathlib import Path

import pytest
from rich.console import Console

from tutor_app.app import TutorApp
from tutor_app.panels import (ChoicePanel, ChoosePanel, ContinuePanel, ReflectPanel, TextPanel, TickPanel,
                              ValuePanel, WorkedPanel)

ROOT = Path(__file__).resolve().parents[2]
REAL_VAULT = Path(os.environ.get("STEM_TUTOR_TEST_LIBRARY_VAULT", ROOT.parent / "STEM Tutor"))
FAKE = str(Path(__file__).with_name("fake_claude.py"))
TOPIC_LINES = ("Topics this uses:", "Not covered yet:", "Yes.", "Part of it.", "I can't tell.", "still to come")


@pytest.fixture(scope="module")
def scratch_vault(tmp_path_factory):
    """A disposable vault: .tutor copied, Library cloned (copy-on-write), never a symlink into the real one."""
    if not (REAL_VAULT / ".tutor/packs/CURRENT").is_file():
        pytest.skip(f"no learner vault at {REAL_VAULT}")
    dest = tmp_path_factory.mktemp("scratch") / "STEM Tutor"
    dest.mkdir()
    subprocess.run(["rsync", "-a", "--exclude", "Library", f"{REAL_VAULT}/", f"{dest}/"], check=True)
    clone = subprocess.run(["cp", "-cR", str(REAL_VAULT / "Library"), str(dest / "Library")], capture_output=True)
    if clone.returncode:  # not APFS: a plain copy still keeps the real Library untouched
        subprocess.run(["cp", "-R", str(REAL_VAULT / "Library"), str(dest / "Library")], check=True)
    assert not (dest / "Library").is_symlink()
    return dest


def app_for(vault, monkeypatch, seed=1):
    monkeypatch.setenv("STEM_TUTOR_VAULT", str(vault))
    monkeypatch.setenv("FAKE_CLAUDE_MODE", "ok")
    monkeypatch.setenv("STEM_TUTOR_NOW", "2026-09-29T17:00:00+08:00")
    app = TutorApp(vault, claude_binary=FAKE, open_obsidian=False, seed=seed)
    errors = []
    original = app._handle_exception

    def handle(error):
        errors.append("".join(traceback.format_exception(type(error), error, error.__traceback__)))
        original(error)

    app._handle_exception = handle
    app.test_errors = errors
    run_test = app.run_test

    @asynccontextmanager
    async def ready_test(*args, **kwargs):
        async with run_test(*args, **kwargs) as pilot:
            await pilot.pause()
            yield pilot

    app.run_test = ready_test
    return app


async def settle(pilot, app):
    from textual.worker import WorkerCancelled
    await pilot.pause()
    for _ in range(2):  # an exclusive group replaces its worker; wait for the replacement too
        try:
            await app.workers.wait_for_complete()
        except WorkerCancelled:
            await pilot.pause()
    await pilot.pause()


def render_text(renderable, width=200):
    out = StringIO()
    Console(file=out, width=width, force_terminal=False).print(renderable)
    return " ".join(out.getvalue().split())


def log_text(screen):
    return " ".join(render_text(widget.content) for widget in screen.query("#log > .entry"))


async def answer_one(pilot, app, screen):
    for _ in range(60):
        await pilot.pause()
        panel = next(iter(screen.query("#panel > *")), None)
        if panel is None:
            await pilot.pause(0.05)
            continue
        name = type(panel).__name__
        if isinstance(panel, ChoosePanel):
            await pilot.press("down", "enter")
        elif isinstance(panel, ChoicePanel):
            if panel.choice is None:
                await pilot.press("b")
            await pilot.pause()
            await pilot.press("3")
        elif isinstance(panel, ValuePanel):
            await pilot.press(*"42", "enter")
            await pilot.pause()
            if panel.query("#conf"):
                await pilot.press("2")
        elif isinstance(panel, TickPanel):
            panel.query("Button").first().press()
        elif isinstance(panel, ReflectPanel):
            await pilot.press("1")
        elif isinstance(panel, WorkedPanel):
            await pilot.press("enter")
        elif isinstance(panel, TextPanel):
            await pilot.press(*"it has a direction", "enter")
        elif isinstance(panel, ContinuePanel):
            panel.query("Button").first().press()
        await pilot.pause()
        return name
    return "none"


async def to_picker(pilot, app):
    """Home -> Practice picker, ending any session left open by an earlier test."""
    app.screen.activate("practice")
    await settle(pilot, app)
    if app.screen.__class__.__name__ == "ConfirmScreen":
        await pilot.press("down", "enter")
        await settle(pilot, app)
    return app.screen


def test_home_folders_enter_and_escape(monkeypatch, scratch_vault):
    app = app_for(scratch_vault, monkeypatch)

    async def go():
        async with app.run_test(size=(100, 40)) as pilot:
            await settle(pilot, app)
            home = app.screen
            assert home.__class__.__name__ == "HomeScreen"
            menu = home.query_one("#menu")
            ids = lambda: [menu.get_option_at_index(i).id for i in range(menu.option_count)]
            assert [i for i in ids() if i not in ("time", "resume")] == [
                "dir:learn", "dir:questions", "dir:profile", "dir:tools"]
            for folder, first in (("learn", "today"), ("questions", "practice"),
                                  ("profile", "insights"), ("tools", "chat")):
                home.open_folder(folder)
                await pilot.pause()
                assert ids()[:2] == ["back", first], folder
                await pilot.press("escape")
                await pilot.pause()
                assert home.folder is None, folder
            menu.highlighted = ids().index("dir:questions")
            await pilot.press("enter")
            await pilot.pause()
            assert home.folder == "questions"
            await pilot.press("escape")
            await pilot.pause()
            assert home.folder is None
            home.activate("quit")
            await pilot.pause()
        assert app.return_code == 0
        assert app.test_errors == []

    asyncio.run(go())


def test_practice_course_flow_solvable_hint_and_quit(monkeypatch, scratch_vault):
    app = app_for(scratch_vault, monkeypatch)

    async def go():
        async with app.run_test(size=(100, 40)) as pilot:
            await settle(pilot, app)
            picker = await to_picker(pilot, app)
            assert picker.__class__.__name__ == "PickerScreen" and picker.mode == "practice"
            subs = picker.query_one("#subs")
            ids = lambda: [subs.get_option_at_index(i).id for i in range(subs.option_count)]
            assert "dir:9702" in ids()
            subs.highlighted = ids().index("dir:9702")
            await pilot.press("enter")
            await pilot.pause()
            assert picker.path == ["9702"]
            assert "all:9702" in ids()
            subs.highlighted = ids().index("all:9702")
            await pilot.press("space")
            await pilot.pause()
            assert picker.ticked and all(picker.info[s]["spec"] == "9702" for s in picker.ticked)
            await pilot.press("ctrl+s")
            await settle(pilot, app)
            setup = app.screen
            assert setup.__class__.__name__ == "PracticeSetupScreen"
            assert (setup.scope, setup.course) == ("course", "9702")
            from textual.widgets import Button, SelectionList
            sources = setup.query_one("#practice-sources", SelectionList)
            assert set(sources.selected) == {"topical", "source_verified"}
            start = setup.query_one("#practice-start", Button)
            assert not start.disabled
            start.press()
            await settle(pilot, app)
            session = app.screen
            assert session.__class__.__name__ == "SessionScreen"
            assert session.start_args["mode"] == "practice" and session.start_args["scope"] == "course"
            await settle(pilot, app)

            untagged = 0
            for _ in range(4):
                view = session.view or {}
                if not view.get("n"):
                    break
                if not session._question_is_open(view, session.showing):
                    await answer_one(pilot, app, session)
                    await settle(pilot, app)
                    continue
                untagged += 0 if view.get("kcs") else 1
                before = len(session.query("#log > .entry"))
                await pilot.press("ctrl+y")
                await settle(pilot, app)
                assert len(session.query("#log > .entry")) > before
                text = log_text(session)
                assert any(line in text for line in TOPIC_LINES), text[-400:]
                await pilot.press("ctrl+g")
                await settle(pilot, app)
                hint = log_text(session)
                assert "Hint" in hint or "Have a go first" in hint or "No hint needed" in hint, hint[-300:]
                assert await answer_one(pilot, app, session) != "none"
                await settle(pilot, app)
            assert untagged, "no untagged question was offered, so the topic check was never exercised"

            await pilot.press("ctrl+b")
            await settle(pilot, app)
            assert app.screen.__class__.__name__ == "HomeScreen"
            app.screen.activate("quit")
            await pilot.pause()
        assert app.return_code == 0
        assert app.test_errors == []

    asyncio.run(go())


def test_adapted_prompt_for_a_partly_answerable_question(monkeypatch, scratch_vault):
    app = app_for(scratch_vault, monkeypatch, seed=2)

    async def go():
        async with app.run_test(size=(100, 40)) as pilot:
            await settle(pilot, app)
            picker = await to_picker(pilot, app)
            subs = picker.query_one("#subs")
            ids = lambda: [subs.get_option_at_index(i).id for i in range(subs.option_count)]
            for step in ("dir:9702", "dir:9702/9702-1"):
                subs.highlighted = ids().index(step)
                await pilot.press("enter")
                await pilot.pause()
            subs.highlighted = ids().index("9702-1.2")
            await pilot.press("space")
            await pilot.pause()
            assert picker.ticked == {"9702-1.2"}
            await pilot.press("ctrl+s")
            await settle(pilot, app)
            setup = app.screen
            from textual.widgets import Button, Input
            setup.query_one("#practice-count", Input).value = "10"
            await settle(pilot, app)
            setup.query_one("#practice-start", Button).press()
            await settle(pilot, app)
            session = app.screen
            assert session.__class__.__name__ == "SessionScreen"
            assert session.start_args["focus"] == ["9702-1.2"]

            prompt = None
            for _ in range(12):
                await settle(pilot, app)
                view = session.view or {}
                if not view.get("n"):
                    break
                if not session._question_is_open(view, session.showing):
                    await answer_one(pilot, app, session)
                    await settle(pilot, app)
                    continue
                await pilot.press("ctrl+y")
                await settle(pilot, app)
                if "Part of it." in log_text(session):
                    prompt = session.adapted.get(str(view["n"]))
                    card = render_text(session._question_card.content)
                    assert prompt and " ".join(prompt.split()) in card, card[-400:]
                    assert "Answer these parts" in card
                    break
                await answer_one(pilot, app, session)
                await settle(pilot, app)
            assert prompt, "no partly answerable question was offered in 9702-1.2"

            await pilot.press("ctrl+b")
            await settle(pilot, app)
            assert app.screen.__class__.__name__ == "HomeScreen"
            app.screen.activate("quit")
            await pilot.pause()
        assert app.return_code == 0
        assert app.test_errors == []

    asyncio.run(go())
