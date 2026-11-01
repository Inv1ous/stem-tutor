"""A requested AI Profile explanation should be visible when it completes."""
import asyncio
import html
import re

import pytest

from test_tui import app_for, shot
from tutor_app import ai
from tutorlib import report


@pytest.mark.parametrize("size", [(60, 24), (100, 30), (140, 46)])
@pytest.mark.parametrize("note_failure", [False, True])
def test_requested_profile_summary_is_brought_into_view(tmp_path, monkeypatch, size, note_failure):
    app, _ = app_for(tmp_path, monkeypatch)
    app.settings.ai = False
    monkeypatch.setattr(app, "ai_available", lambda mode="explain": True)
    reply = "Give your units a final check."
    calls = []

    async def summary(*args, **kwargs):
        calls.append(True)
        return {"summary": reply}, ai.Result()

    async def go():
        async with app.run_test(size=size) as pilot:
            await pilot.pause()
            app.screen._start("insights")
            await pilot.pause()
            monkeypatch.setattr(app.ai, "one_shot", summary)
            if note_failure:
                def unavailable(*args, **kwargs):
                    raise OSError("profile note unavailable")
                monkeypatch.setattr(report, "profile_note", unavailable)
            await pilot.press("a")
            await app.workers.wait_for_complete()
            await pilot.pause(0.5)
            await shot(pilot, f"profile-ready-{'note-error' if note_failure else 'saved'}-{size[0]}x{size[1]}")
            visible = html.unescape("".join(re.findall(r">([^<>]*)</text>", app.export_screenshot()))).replace("\xa0", " ")
            assert reply in visible
            assert calls == [True]
            await pilot.press("escape")
            await pilot.pause()
            assert app.screen.__class__.__name__ == "HomeScreen"
            await app.ai.close()

    asyncio.run(go())


def test_leaving_before_profile_reply_does_not_update_a_stale_screen(tmp_path, monkeypatch):
    app, vault = app_for(tmp_path, monkeypatch)
    app.settings.ai = False
    monkeypatch.setattr(app, "ai_available", lambda mode="explain": True)
    calls = []

    async def go():
        started, release = asyncio.Event(), asyncio.Event()

        async def summary(*args, **kwargs):
            calls.append(True)
            started.set()
            await release.wait()
            return {"summary": "A late profile reply."}, ai.Result()

        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            app.screen._start("insights")
            await pilot.pause()
            monkeypatch.setattr(app.ai, "one_shot", summary)
            await pilot.press("a")
            await asyncio.wait_for(started.wait(), 2)
            await pilot.press("escape")
            await pilot.pause()
            assert app.screen.__class__.__name__ == "HomeScreen"
            release.set()
            await app.workers.wait_for_complete()
            await pilot.pause()
            assert app.is_running and app.screen.__class__.__name__ == "HomeScreen"
            assert calls == [True] and not (vault / ".tutor" / "profile_ai.json").exists()
            app.screen._start("insights")
            await pilot.pause()
            assert app.screen.__class__.__name__ == "InsightsScreen" and calls == [True]
            await app.ai.close()

    asyncio.run(go())
