"""A saved session still opens its summary and explains optional note failures."""
import asyncio
from pathlib import Path

import pytest

from test_tui import app_for, shot
from tutor_app.screens import SessionScreen, SummaryScreen
from tutorlib import views


@pytest.mark.parametrize("failed_view", ["notes", "transcript"])
def test_optional_note_failure_warns_without_hiding_the_saved_summary(tmp_path, monkeypatch, failed_view):
    app, _ = app_for(tmp_path, monkeypatch)
    app.settings.ai = False
    notices = []
    notify = app.notify

    def record(message, **kwargs):
        notices.append(message)
        notify(message, **kwargs)

    monkeypatch.setattr(app, "notify", record)

    async def go():
        async with app.run_test(size=(100, 30), notifications=True) as pilot:
            screen = SessionScreen({"mode": "test", "minutes": 40, "focus": ["9702-2.1"]})
            app.push_screen(screen)
            await pilot.pause()
            screen.submit({"entry": f"{screen.view['n']}?", "your": "I don't know"})
            await pilot.pause()
            session_id = app.tutor.session["id"]
            if failed_view == "notes":
                def unavailable(*args, **kwargs):
                    raise OSError("notes file unavailable")
                monkeypatch.setattr(views, "refresh_status", unavailable)
                label, error = "My Notes 9702-2.1", "notes file unavailable"
            else:
                transcript = app.vault / app.tutor.session["log"]
                original_open = open

                def unavailable(file, mode="r", *args, **kwargs):
                    if isinstance(file, (str, Path)) and Path(file) == transcript and mode == "a":
                        raise OSError("lesson summary unavailable")
                    return original_open(file, mode, *args, **kwargs)
                monkeypatch.setattr("builtins.open", unavailable)
                label, error = "Lesson transcript", "lesson summary unavailable"
            screen.finish()
            await pilot.pause()
            await shot(pilot, f"optional-{failed_view}-summary")
            assert isinstance(app.screen, SummaryScreen)
            assert app.screen.summary["session"] == session_id and app.screen.summary["answered"] == 1
            assert app.screen.summary["view_errors"] == {label: error}
            assert any("Session saved" in message and label in message and error in message for message in notices)
            assert app.tutor.session is None
            assert len([event for event in app.tutor.vault.events()
                        if event["type"] == "session_end" and event["session"] == session_id]) == 1
            await pilot.press("escape")
            await pilot.pause()
            assert app.screen.__class__.__name__ == "HomeScreen"
            await app.ai.close()

    asyncio.run(go())
