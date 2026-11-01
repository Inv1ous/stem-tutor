"""Sending another question gives the interrupted reply an honest terminal status."""
import asyncio

import pytest

from test_bf_j05 import paused_chat
from test_tui import app_for, shot
from tutor_app import ai
from tutor_app.codex_models import CODEX_MODELS


@pytest.mark.parametrize("model", ["haiku", next(iter(CODEX_MODELS))])
@pytest.mark.parametrize("partial", [False, True], ids=["waiting", "streaming"])
@pytest.mark.parametrize("guarded", [False, True], ids=["free-chat", "protected-answer"])
def test_new_chat_question_finishes_the_cancelled_reply_visibly(tmp_path, monkeypatch, model, partial, guarded):
    app, vault = app_for(tmp_path, monkeypatch)
    app.settings.ai = False
    app.settings.ai_ask_model = model
    monkeypatch.setattr(app, "ai_available", lambda mode="ask": True)

    async def go():
        ready, cancelled = asyncio.Event(), asyncio.Event()
        calls = []

        async def stream(prompt, **kwargs):
            calls.append(prompt)
            if len(calls) == 1:
                if partial:
                    yield "I have begun the first explanation."
                ready.set()
                try:
                    await asyncio.Event().wait()
                except asyncio.CancelledError:
                    cancelled.set()
                    raise
            else:
                app.ai.last = ai.Result(text="Here is the second explanation.")
                yield app.ai.last.text

        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            monkeypatch.setattr(app.ai, "stream", stream)
            if guarded:
                await paused_chat(app, pilot, unassisted=False)
            else:
                menu = app.screen.query_one("#menu")
                menu.highlighted = [o.id for o in menu.options].index("chat")
                await pilot.press("enter")
                await pilot.pause()
            screen = app.screen
            await pilot.press(*"First question", "enter")
            await asyncio.wait_for(ready.wait(), timeout=2)
            await pilot.pause()
            interrupted = screen.query(".entry").last()
            await pilot.press(*"Second question", "enter")
            await app.workers.wait_for_complete()
            await pilot.pause()
            await shot(pilot, f"chat-interrupted-{model.replace(':', '-')}-{'partial' if partial else 'waiting'}-{'guarded' if guarded else 'free'}")
            assert cancelled.is_set() and len(calls) == 2
            assert interrupted.content.card[0] == "hint"
            assert "stopped" in interrupted.content.card[1].lower()
            assert "cancelled" in interrupted.content.card[2].lower()
            assert ("I have begun the first explanation." in interrupted.content.card[2]) is (partial and not guarded)
            assert "I have begun the first explanation." not in (vault / "Now.md").read_text()
            assert screen.query(".entry").last().content.card[2] == "Here is the second explanation."
            assert screen.query_one("#text").has_focus and app.screen is screen
            assert all(text in (vault / "Now.md").read_text()
                       for text in ["First question", "Second question", "Here is the second explanation."])
            await app.ai.close()

    asyncio.run(go())
