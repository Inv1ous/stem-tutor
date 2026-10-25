"""Written questions prepare their marking model before submission, with view ownership."""
import asyncio
import time
from io import StringIO

import pytest
from rich.console import Console

from test_tui import app_for
from tutor_app import ai, local_models
from tutor_app.local_ai import LocalAI
from tutor_app.screens import ChatScreen, LocalActivity, SessionScreen


MARK = "ollama:phi4-mini:3.8b"
EXPLAIN = "ollama:qwen3.5:9b"


@pytest.fixture(autouse=True)
def offline_local(monkeypatch):
    monkeypatch.setattr(local_models, "available_models", lambda: (MARK, EXPLAIN))

    async def no_http(*args, **kwargs):
        pytest.fail("Lifecycle tests must never contact the local runtime")
        yield

    async def warm(self, model, timeout=120):
        return ai.Result()

    monkeypatch.setattr(LocalAI, "_events", no_http)
    monkeypatch.setattr(LocalAI, "warm", warm)


@pytest.mark.parametrize("kind", ["short", "structured"])
@pytest.mark.parametrize("model", [MARK, EXPLAIN])
def test_initial_written_question_prepares_mark_without_loading_explain(tmp_path, monkeypatch, kind, model):
    app, _ = app_for(tmp_path, monkeypatch)
    app.settings.ai_mark_model = model
    app.settings.ai_explain_model = EXPLAIN if model == MARK else MARK
    started, stopped, warmed = asyncio.Event(), asyncio.Event(), []

    async def warm(self, model, timeout=120):
        warmed.append(model)
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            stopped.set()

    monkeypatch.setattr(LocalAI, "warm", warm)

    async def go():
        async with app.run_test() as pilot:
            await pilot.pause()
            next_activity = app.tutor.next

            def written_first():
                activity = next_activity()
                return {**activity, "items": [{**activity["items"][0], "kind": kind}]}

            monkeypatch.setattr(app.tutor, "next", written_first)
            screen = SessionScreen({"mode": "test", "minutes": 40, "focus": ["9702-2.1"]})
            app.push_screen(screen)
            await pilot.pause()
            assert started.is_set(), "Mark should prepare while the first written question is being read"
            assert warmed == [model], "Session mount must not replace the marking preload with Explain"
            assert app._preload_owner is screen
            assert app.ai.local._history == {}
            app.pop_screen()
            await pilot.pause()
            assert stopped.is_set(), "Leaving the session must cancel its owned preparation"
            await app.ai.close()

    asyncio.run(go())


def test_written_preparation_ignores_replaced_and_repeated_views(tmp_path, monkeypatch):
    app, _ = app_for(tmp_path, monkeypatch)
    warmed = []

    async def warm(self, model, timeout=120):
        warmed.append(model)
        return ai.Result()

    monkeypatch.setattr(LocalAI, "warm", warm)

    async def go():
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = SessionScreen({"mode": "test", "minutes": 40, "focus": ["9702-2.1"]})
            app.push_screen(screen)
            await pilot.pause()
            app.settings.ai_mark_model = MARK
            view = {**screen.view, "kind": "short", "n": 90, "image": None}
            screen.ask_question(view)
            screen.ask_question({**view, "n": 91})
            await pilot.pause()
            assert warmed == [MARK], "Only the still-visible written question should prepare"
            screen.ask_question(dict(screen.view))
            await pilot.pause()
            assert warmed == [MARK], "Redrawing the same question must retain its preparation"
            screen.ask_question({**view, "n": 92})
            screen.ask_question({**view, "n": 93, "kind": "mcq"})
            await pilot.pause()
            assert warmed == [MARK], "A queued callback for a replaced written question must do nothing"
            await app.ai.close()

    asyncio.run(go())


@pytest.mark.parametrize("model,enabled", [("haiku", True), ("codex:gpt-6-luna", True), (MARK, False)])
def test_cloud_or_disabled_written_marking_never_starts_local_runtime(tmp_path, monkeypatch, model, enabled):
    app, _ = app_for(tmp_path, monkeypatch)
    app.settings.ai_mark_model, app.settings.ai = model, enabled
    app.settings.ai_ask_model = MARK  # a local Ask choice must not change written marking's provider

    async def go():
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = SessionScreen({"mode": "test", "minutes": 40, "focus": ["9702-2.1"]})
            app.push_screen(screen)
            await pilot.pause()
            screen.ask_question({**screen.view, "kind": "short", "n": 90, "image": None})
            await pilot.pause()
            assert app.ai._local is None
            await app.ai.close()

    asyncio.run(go())


def test_loading_status_and_preload_timing_stay_in_terminal(tmp_path, monkeypatch):
    app, vault = app_for(tmp_path, monkeypatch)

    async def go():
        async with app.run_test() as pilot:
            await pilot.pause()
            app.push_screen(ChatScreen())
            await pilot.pause()
            screen = app.screen
            activity = LocalActivity(screen, MARK)
            monkeypatch.setattr(app.ai, "progress_for", lambda model: {"phase": "loading", "started": time.monotonic()})
            assert "Loading local model" in activity.status()
            before = (vault / "Now.md").read_text()
            result = ai.Result(text="A useful answer", speech="A spoken answer", performance={
                "model": MARK, "total_seconds": 2, "first_token_seconds": 1.5, "load_seconds": .1,
                "preload_seconds": 1.25, "output_tokens": 10,
            })
            app.show_local_performance(result)
            await pilot.pause()
            console = Console(width=180, record=True, file=StringIO())
            for entry in screen.query(".local-performance"):
                console.print(entry.content)
            assert "preload 1.2s" in console.export_text()
            assert (vault / "Now.md").read_text() == before
            assert result.text == "A useful answer" and result.speech == "A spoken answer"
            await app.ai.close()

    asyncio.run(go())
