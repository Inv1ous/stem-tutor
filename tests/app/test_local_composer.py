"""The session Ask composer owns local preparation until cancel or submission."""
import asyncio
from types import SimpleNamespace

import pytest

from test_tui import app_for, shot
from tutor_app import ai, local_models, look
from tutor_app.local_ai import LocalAI
from tutor_app.panels import Composer
from tutor_app.screens import AskScreen, SessionScreen


MODEL = "ollama:qwen3.5:9b"


@pytest.fixture
def preload(monkeypatch):
    monkeypatch.setattr(local_models, "available_models", lambda: (MODEL,))
    probe = SimpleNamespace(started=asyncio.Event(), release=asyncio.Event(), stopped=asyncio.Event(), models=[])

    async def warm(client, model, timeout=120):
        probe.models.append(model)
        async with client._lock:
            probe.started.set()
            try:
                await probe.release.wait()
                return ai.Result()
            finally:
                probe.stopped.set()

    monkeypatch.setattr(LocalAI, "warm", warm)
    return probe


@pytest.mark.parametrize("size", [(80, 24), (120, 40)])
@pytest.mark.parametrize("theme", ["night", "day", "classic"])
def test_local_ask_prepares_selected_model_while_learner_types(tmp_path, monkeypatch, preload, size, theme):
    app, _ = app_for(tmp_path, monkeypatch)
    app.settings.ai_ask_model = MODEL
    app.settings.theme = theme
    look.use(theme)

    async def go():
        async with app.run_test(size=size) as pilot:
            await pilot.pause()
            parent = SessionScreen({"mode": "test", "minutes": 40, "focus": ["9702-2.1"]})
            app.push_screen(parent)
            await pilot.pause()
            parent.action_ask()
            await pilot.pause()
            assert preload.started.is_set(), "Ask should load the selected local model before Send"
            await pilot.press(*"what is a force")
            composer = app.screen.query_one("#q", Composer)
            assert composer.text == "what is a force" and app.focused is composer
            assert app.screen.query_one("#ask").region.contains_region(composer.region)
            assert app.screen.region.contains_region(app.screen.query_one("#ask").region)
            await shot(pilot, f"local-composer-{theme}-{size[0]}x{size[1]}")
            assert preload.models == [MODEL]
            assert not preload.stopped.is_set()
            assert app.ai.local._history == {}
            await pilot.press("escape")
            await pilot.pause()
            await app.ai.close()

    try:
        asyncio.run(go())
    finally:
        look.use("classic")


@pytest.mark.parametrize("cancel", ["escape", "empty", "pop"])
def test_cancelled_ask_stops_its_unfinished_preparation(tmp_path, monkeypatch, preload, cancel):
    app, _ = app_for(tmp_path, monkeypatch)
    app.settings.ai_ask_model = MODEL

    async def go():
        async with app.run_test() as pilot:
            await pilot.pause()
            result = []
            parent = app.screen
            app.push_screen(AskScreen(), result.append)
            await pilot.pause()
            assert preload.started.is_set(), "The composer must own an active local preload"
            if cancel == "pop":
                app.pop_screen()
            else:
                await pilot.press("escape" if cancel == "escape" else "enter")
            await pilot.pause()
            assert app.screen is parent
            assert preload.stopped.is_set(), "Cancelling Ask must join its speculative preload"
            if cancel != "pop":
                assert result == [None]
            await app.ai.close()

    asyncio.run(go())


def test_submitted_ask_keeps_preparation_for_requested_inference(tmp_path, monkeypatch, preload):
    app, _ = app_for(tmp_path, monkeypatch)
    app.settings.ai_ask_model = MODEL

    async def go():
        waiting, generated = asyncio.Event(), asyncio.Event()
        replies = []

        async def stream(client, prompt, **kwargs):
            assert prompt == "what is a force"
            assert kwargs["model"] == MODEL
            waiting.set()
            async with client._lock:
                generated.set()
                client.last = ai.Result(text="A useful hint.")
                yield client.last.text

        async def request(question):
            replies.append("".join([piece async for piece in app.ai.stream(question, model=MODEL)]))

        monkeypatch.setattr(LocalAI, "stream", stream)
        async with app.run_test() as pilot:
            await pilot.pause()
            app.push_screen(AskScreen(), lambda question: app.run_worker(request(question)))
            await pilot.pause()
            assert preload.started.is_set(), "Ask must start preparing before its request"
            await pilot.press(*"what is a force", "enter")
            await pilot.pause()
            await asyncio.wait_for(waiting.wait(), 1)
            assert not preload.stopped.is_set(), "Send must retain preparation for the requested answer"
            assert not generated.is_set()
            preload.release.set()
            await app.workers.wait_for_complete()
            assert generated.is_set() and replies == ["A useful hint."]
            assert preload.models == [MODEL]
            await app.ai.close()

    asyncio.run(go())


def test_submitted_ask_preparation_stops_when_parent_session_closes(tmp_path, monkeypatch, preload):
    app, _ = app_for(tmp_path, monkeypatch)
    app.settings.ai_ask_model = MODEL

    async def go():
        async with app.run_test(size=(100, 35)) as pilot:
            await pilot.pause()
            parent = SessionScreen({"mode": "test", "minutes": 40, "focus": ["9702-2.1"]})
            app.push_screen(parent)
            await pilot.pause()
            result = []
            app.push_screen(AskScreen(), result.append)
            await pilot.pause()
            assert preload.started.is_set(), "Ask must prepare before the learner submits"
            await pilot.press(*"what is a force", "enter")
            await pilot.pause()
            assert app.screen is parent and result == ["what is a force"]
            assert not preload.stopped.is_set()
            app.pop_screen()
            await pilot.pause()
            assert preload.stopped.is_set(), "The parent must own retained preparation after Send"
            await app.ai.close()

    asyncio.run(go())


@pytest.mark.parametrize("model,enabled", [("haiku", True), ("codex:gpt-6-luna", True), (MODEL, False)])
def test_cloud_or_disabled_ask_never_creates_local_client(tmp_path, monkeypatch, preload, model, enabled):
    app, _ = app_for(tmp_path, monkeypatch)
    app.settings.ai_ask_model, app.settings.ai = model, enabled

    async def go():
        async with app.run_test() as pilot:
            await pilot.pause()
            assert app.ai._local is None
            app.push_screen(AskScreen())
            await pilot.pause()
            await pilot.press(*"what is a force")
            assert app.screen.query_one("#q", Composer).text == "what is a force"
            assert app.ai._local is None
            assert preload.models == []
            await pilot.press("escape")
            await app.ai.close()

    asyncio.run(go())
