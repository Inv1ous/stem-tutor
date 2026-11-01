"""Optional Profile AI output failures must keep the app usable and existing output intact."""
import asyncio
import json
from copy import deepcopy
from pathlib import Path

import pytest
from textual.containers import VerticalScroll
from textual.widgets import Markdown

from test_tui import app_for, shot
from tutor_app import ai
from tutorlib import report, store


@pytest.mark.parametrize("failure", ["cache", "note", None])
def test_profile_summary_output_errors_are_recoverable_without_regeneration(tmp_path, monkeypatch, failure):
    app, vault = app_for(tmp_path, monkeypatch)
    app.settings.ai = False
    monkeypatch.setattr(app, "ai_available", lambda mode="explain": True)
    previous, latest = "Previously saved advice.", "Keep checking your units."
    cached = vault / ".tutor" / "profile_ai.json"
    notices, calls = [], []
    notify = app.notify

    def record(message, **kwargs):
        notices.append(message)
        notify(message, **kwargs)

    async def summary(*args, **kwargs):
        calls.append(True)
        return {"summary": latest}, ai.Result()

    monkeypatch.setattr(app, "notify", record)

    async def go():
        async with app.run_test(size=(100, 30), notifications=True) as pilot:
            await pilot.pause()
            store.write_json(cached, {"text": previous, "at": app.tutor.now().isoformat()})
            report.profile_note(app.tutor)
            old_cache, old_profile = cached.read_bytes(), (vault / "Profile.md").read_bytes()
            monkeypatch.setattr(app.ai, "one_shot", summary)
            app.screen._start("insights")
            await pilot.pause()
            screen = app.screen
            scroll = screen.query_one(VerticalScroll)
            scroll.scroll_to(y=8, animate=False, immediate=True)
            await pilot.pause()
            before_scroll = scroll.scroll_y
            state = deepcopy(app.tutor.state)
            events = list(app.tutor.vault.events())
            with monkeypatch.context() as patch:
                if failure == "cache":
                    original = store.write_json

                    def unavailable(path, *args, **kwargs):
                        if Path(path) == cached:
                            raise OSError("profile cache unavailable")
                        return original(path, *args, **kwargs)
                    patch.setattr(store, "write_json", unavailable)
                elif failure == "note":
                    def unavailable(*args, **kwargs):
                        raise OSError("profile note unavailable")
                    patch.setattr(report, "profile_note", unavailable)
                await pilot.press("a")
                await app.workers.wait_for_complete()
                await pilot.pause()
                await shot(pilot, f"profile-summary-{failure or 'success'}")
                assert app.is_running and app.screen is screen and len(calls) == 1
                shown = screen.query_one("#insights", Markdown).source
                if failure == "cache":
                    assert cached.read_bytes() == old_cache and (vault / "Profile.md").read_bytes() == old_profile
                    assert scroll.scroll_y == before_scroll
                    assert previous in shown and latest not in shown
                    assert any("could not be saved" in message and "profile cache unavailable" in message for message in notices)
                else:
                    assert json.loads(cached.read_text())["text"] == latest and latest in shown
                    if failure == "note":
                        assert (vault / "Profile.md").read_bytes() == old_profile
                        assert any("summary saved" in message and "Profile" in message and "profile note unavailable" in message
                                   for message in notices)
                    else:
                        assert latest in (vault / "Profile.md").read_text()
                assert app.tutor.state == state and list(app.tutor.vault.events()) == events
            await pilot.press("escape")
            await pilot.pause()
            assert app.screen.__class__.__name__ == "HomeScreen" and app.is_running
            await app.ai.close()

    asyncio.run(go())
