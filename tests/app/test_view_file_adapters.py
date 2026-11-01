"""Read-only Home/Now references keep their bytes while the public tutor works."""
import asyncio
import json
import os
from pathlib import Path

import pytest

import library_assets
from test_tui import app_for
from tutor_app import ai, mac
from tutorlib.asset_library import AssetLibrary, write_asset
from tutorlib.store import read_json


ORIGINAL = b"# Registered reusable reference\r\nImmutable resource and file-adapter bytes.\r\n"


def capture(app, name):
    if directory := os.environ.get("B247_SHOTS"):
        Path(directory).mkdir(parents=True, exist_ok=True)
        app.save_screenshot(name + ".svg", path=directory)


async def choose(pilot, app, key):
    menu = app.screen.query_one("#menu")
    menu.highlighted = [option.id for option in menu.options].index(key)
    await pilot.press("enter")
    await pilot.pause()


@pytest.mark.parametrize("note", ["Home.md", "Now.md"])
def test_registered_view_adapter_warns_once_without_stopping_public_navigation(tmp_path, monkeypatch, note):
    app, vault = app_for(tmp_path, monkeypatch)
    app.settings.ai = False
    library_assets.install_course(vault, "9702", "9702-2.1")
    resource = "Library/Courses/9702/Notes/registered-" + note
    write_asset(vault, resource, ORIGINAL, aliases=[note])
    (vault / note).write_bytes(ORIGINAL)
    notices, opened = [], []
    notify = app.notify

    def warned(message, **kwargs):
        notices.append(str(message))
        notify(message, **kwargs)

    monkeypatch.setattr(app, "notify", warned)
    monkeypatch.setattr(mac, "open_in_obsidian", lambda *args, **kwargs: opened.append(args))

    async def go():
        async with app.run_test(size=(80, 24), notifications=True) as pilot:
            await pilot.pause()
            if note == "Home.md":
                await choose(pilot, app, "obsidian")
                assert not opened and type(app.screen).__name__ == "HomeScreen"
                await choose(pilot, app, "progress")
                await pilot.press("escape")
            else:
                async def stream(*args, **kwargs):
                    app.ai.last = ai.Result(text="The explanation remains available in this chat.")
                    yield app.ai.last.text

                monkeypatch.setattr(app.ai, "stream", stream)
                monkeypatch.setattr(app, "ai_available", lambda mode="ask": True)
                await choose(pilot, app, "chat")
                await pilot.press(*"Explain this step", "enter")
                await app.workers.wait_for_complete()
                await pilot.pause()
                assert app.screen.query(".entry").last().content.card[2].startswith("The explanation remains")
                assert app.screen.query_one("#text").has_focus
            await pilot.pause(1.1)  # the existing periodic UI tick delivers optional-view warnings
            assert len([message for message in notices if message.startswith(note + " is read-only")]) == 1
            capture(app, note[:-3] + "-protected")
            warning = app.tutor.view_warnings[note]
            if note == "Now.md":
                await pilot.press(*"Another question", "enter")
                await app.workers.wait_for_complete()
            else:
                await choose(pilot, app, "obsidian")
            await pilot.pause(1.1)
            assert app.tutor.view_warnings[note] is warning
            assert len([message for message in notices if message.startswith(note + " is read-only")]) == 1
            assert (vault / note).read_bytes() == ORIGINAL and (vault / resource).read_bytes() == ORIGINAL
            assert AssetLibrary(vault).read(note) == ORIGINAL and app.is_running
            if note == "Now.md":
                await pilot.press("escape")
                await pilot.pause()
            assert type(app.screen).__name__ == "HomeScreen"
            if note == "Now.md":
                monkeypatch.setattr(app, "ai_available", lambda mode="ask": False)
                await choose(pilot, app, "learn")
                await pilot.press("enter")
                await pilot.pause()
                await pilot.press("enter")  # Learn from scratch: the plan is saved despite the read-only mirror.
                await pilot.pause()
                assert type(app.screen).__name__ == "SessionScreen" and app.screen.act["activity"] == "plan"
                assert read_json(app.tutor.session_path) == json.loads(json.dumps(app.tutor.session))
                assert "Now" in app.tutor.session["view_errors"]
                assert (vault / note).read_bytes() == ORIGINAL
                capture(app, "Now-protected-session-saved")
            await app.ai.close()

    asyncio.run(go())


def test_now_warning_can_recur_after_actual_mirror_recovery_between_ticks(tmp_path, monkeypatch):
    app, vault = app_for(tmp_path, monkeypatch)
    app.settings.ai = False
    library_assets.install_course(vault, "9702", "9702-2.1")
    resource = "Library/Courses/9702/Notes/referenced-note.md"
    write_asset(vault, resource, ORIGINAL)
    path = vault / "Now.md"
    path.symlink_to(vault / resource)
    notices = []
    monkeypatch.setattr(app, "notify", lambda message, **kwargs: notices.append(str(message)))

    async def go():
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            await choose(pilot, app, "chat")
            await pilot.pause(1.1)
            first = app.tutor.view_warnings["Now.md"]
            assert len([message for message in notices if message.startswith("Now.md is read-only")]) == 1
            # Removing an undeclared disposable file adapter restores the ordinary mutable mirror.
            path.unlink()
            app.tutor.clear_chat()
            assert "Now.md" not in app.tutor.view_warnings and path.is_file() and not path.is_symlink()
            path.unlink()
            path.symlink_to(vault / resource)
            app.tutor.clear_chat()
            assert app.tutor.view_warnings["Now.md"] is not first
            await pilot.pause(1.1)
            assert len([message for message in notices if message.startswith("Now.md is read-only")]) == 2
            assert path.is_symlink() and (vault / resource).read_bytes() == ORIGINAL
            await app.ai.close()

    asyncio.run(go())
