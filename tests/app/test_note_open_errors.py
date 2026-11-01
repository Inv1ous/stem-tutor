"""Explicit report-note actions must not quit the tutor when a note cannot refresh."""
import asyncio
import json
from copy import deepcopy
from pathlib import Path

import pytest

from test_tui import app_for, shot
from tutor_app import ai, mac
from tutorlib import store


@pytest.mark.parametrize("route", ["profile_after_summary", "mistakes", "progress"])
@pytest.mark.parametrize("refused", [False, True])
def test_report_note_shortcuts_preserve_navigation_when_replace_is_refused(tmp_path, monkeypatch, route, refused):
    app, vault = app_for(tmp_path, monkeypatch)
    app.settings.ai = False
    monkeypatch.setattr(app, "ai_available", lambda mode="explain": True)
    name = "Mistakes" if route == "mistakes" else "Profile"
    note = vault / f"{name}.md"
    original_note = b"# Previously saved note\nEarlier contents remain readable.\n"
    opened, notices, calls = [], [], []
    monkeypatch.setattr(mac, "open_in_obsidian", lambda *args, **kwargs: opened.append((args, kwargs)) or True)
    notify = app.notify

    def record(message, **kwargs):
        notices.append(message)
        notify(message, **kwargs)

    async def summary(*args, **kwargs):
        calls.append(True)
        return {"summary": "Keep checking your units."}, ai.Result()

    monkeypatch.setattr(app, "notify", record)

    async def go():
        async with app.run_test(size=(100, 30), notifications=True) as pilot:
            await pilot.pause()
            note.write_bytes(original_note)
            app.screen._start("progress" if route == "progress" else "insights")
            await pilot.pause()
            screen = app.screen
            before_state = deepcopy(app.tutor.state)
            before_events = list(app.tutor.vault.events())
            replace = store.os.replace

            def refuse_note(source, destination):
                if Path(destination) == note:
                    raise OSError("note file unavailable")
                return replace(source, destination)

            if refused:
                monkeypatch.setattr(store.os, "replace", refuse_note)
            if route == "profile_after_summary":
                monkeypatch.setattr(app.ai, "one_shot", summary)
                await pilot.press("a")
                await app.workers.wait_for_complete()
                await pilot.pause()
                assert json.loads((vault / ".tutor/profile_ai.json").read_text())["text"] == "Keep checking your units."
                assert calls == [True]
            notices.clear()
            await pilot.press("m" if route == "mistakes" else "o")
            await pilot.pause()
            await shot(pilot, f"open-{route}-{'refused' if refused else 'success'}")
            assert app.is_running and app.screen is screen
            if refused:
                assert note.read_bytes() == original_note and not opened
                assert any(name in message and "could not be updated" in message and "note file unavailable" in message
                           for message in notices)
            else:
                assert note.read_bytes() != original_note
                assert opened == [((vault, name), {"background": False})]
            assert app.tutor.state == before_state and list(app.tutor.vault.events()) == before_events
            assert calls == ([True] if route == "profile_after_summary" else [])
            await pilot.press("escape")
            await pilot.pause()
            assert app.screen.__class__.__name__ == "HomeScreen" and app.is_running
            await app.ai.close()

    asyncio.run(go())
