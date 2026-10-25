"""Slow local requests show honest activity without putting status text into learner notes."""
import asyncio
import os
from io import StringIO
from pathlib import Path

import pytest
from rich.console import Console

from test_tui import app_for
from tutor_app import ai, local_models
from tutor_app.screens import ChatScreen, InsightsScreen, SessionScreen


MODELS = ("ollama:qwen3.5:9b", "ollama:gemma4:26b-a4b-it-qat", "ollama:qwen3.8:27b")


@pytest.fixture(autouse=True)
def local_without_runtime(monkeypatch):
    from tutor_app.local_ai import LocalAI

    async def warm(self, model, timeout=120):
        return ai.Result()
    monkeypatch.setattr(LocalAI, "warm", warm)
    monkeypatch.setattr(local_models, "available_models", lambda: MODELS)


def words(screen):
    console = Console(width=80, record=True, file=StringIO())
    for entry in screen.query(".entry, .local-progress"):
        if entry.display:
            console.print(entry.content)
    return console.export_text()


def snapshot(app, name):
    if folder := os.environ.get("LOCAL_PROGRESS_SHOTS"):
        Path(folder).mkdir(parents=True, exist_ok=True)
        app.save_screenshot(path=folder, filename=name + ".svg")


@pytest.mark.parametrize("model", MODELS)
def test_local_chat_shows_preparing_thinking_then_visible_answer_without_mirroring_progress(tmp_path, monkeypatch, model):
    app, vault = app_for(tmp_path, monkeypatch)
    app.settings.ai_ask_model = model

    async def go():
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            app.push_screen(ChatScreen())
            await pilot.pause()
            state, token, finish = {"phase": "preparing"}, asyncio.Event(), asyncio.Event()
            monkeypatch.setattr(app.ai, "progress_for", lambda selected: state, raising=False)

            async def slow(prompt, **kwargs):
                await token.wait()
                yield "A force changes motion."
                await finish.wait()
                app.ai.last = ai.Result(text="A force changes motion.")
            monkeypatch.setattr(app.ai, "stream", slow)
            worker = app.screen.reply("Explain a force")
            await pilot.pause(0.05)
            snapshot(app, model.replace(":", "-") + "-preparing")
            assert "Preparing local model" in words(app.screen)
            state["phase"] = "thinking"
            await pilot.pause(0.25)
            snapshot(app, model.replace(":", "-") + "-thinking")
            assert "Thinking" in words(app.screen) and "elapsed" in words(app.screen)
            assert "Thinking" not in (vault / "Now.md").read_text()
            state["phase"] = "generating"
            token.set()
            await pilot.pause(0.25)
            snapshot(app, model.replace(":", "-") + "-generating")
            assert "A force changes motion." in words(app.screen)
            assert "Generating" in words(app.screen)
            finish.set()
            await worker.wait()
            await pilot.pause()
            assert "Generating" not in words(app.screen)
            assert "A force changes motion." in (vault / "Now.md").read_text()
            assert "local model" not in (vault / "Now.md").read_text()
            await app.ai.close()
    asyncio.run(go())


def test_cancelled_local_stream_stops_pending_activity(tmp_path, monkeypatch):
    app, _ = app_for(tmp_path, monkeypatch)
    app.settings.ai_ask_model = MODELS[0]

    async def go():
        async with app.run_test() as pilot:
            await pilot.pause()
            app.push_screen(ChatScreen())
            await pilot.pause()

            async def slow(prompt, **kwargs):
                await asyncio.Event().wait()
                yield "unreachable"
            monkeypatch.setattr(app.ai, "stream", slow)
            worker = app.screen.reply("Explain a force")
            await pilot.pause()
            assert "Preparing local model" in words(app.screen)
            worker.cancel()
            await pilot.pause(0.3)
            assert "Preparing local model" not in words(app.screen)
            assert "cancelled" in words(app.screen).lower()
            await app.ai.close()
    asyncio.run(go())


def test_local_session_help_stays_active_while_answer_guard_holds_streamed_text(tmp_path, monkeypatch):
    app, vault = app_for(tmp_path, monkeypatch)
    app.settings.ai_ask_model = MODELS[1]

    async def go():
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = SessionScreen({"mode": "test", "focus": ["9702-2.1"], "minutes": 40})
            app.push_screen(screen)
            await pilot.pause()
            finish = asyncio.Event()
            state = {"phase": "generating"}
            monkeypatch.setattr(app.ai, "progress_for", lambda selected: state, raising=False)

            async def slow(prompt, **kwargs):
                yield "A private partial reply."
                await finish.wait()
                app.ai.last = ai.Result(text="A useful explanation.")
            monkeypatch.setattr(app.ai, "stream", slow)
            worker = screen._stream("Explain", False)
            await pilot.pause(0.25)
            assert "Generating" in words(screen)
            assert "private partial" not in words(screen)
            assert "Preparing local model" not in (vault / "Now.md").read_text()
            finish.set()
            await worker.wait()
            await pilot.pause()
            assert "Generating" not in words(screen)
            await app.ai.close()
    asyncio.run(go())


def test_local_profile_json_has_visible_transient_progress(tmp_path, monkeypatch):
    app, vault = app_for(tmp_path, monkeypatch)
    app.settings.ai_explain_model = MODELS[2]

    async def go():
        async with app.run_test() as pilot:
            await pilot.pause()
            app.push_screen(InsightsScreen())
            await pilot.pause()
            finish = asyncio.Event()

            async def slow(prompt, **kwargs):
                await finish.wait()
                return None, ai.Result(ok=False, message="Try later.")
            monkeypatch.setattr(app.ai, "one_shot", slow)
            worker = app.screen._summarise()
            await pilot.pause(0.05)
            assert app.screen.query(".local-progress")
            assert "Preparing local model" in words(app.screen)
            finish.set()
            await worker.wait()
            await pilot.pause()
            assert not app.screen.query(".local-progress")
            assert not (vault / ".tutor" / "profile_ai.json").exists()
            await app.ai.close()
    asyncio.run(go())


def test_local_marking_json_progress_never_changes_the_submitted_work_or_notes(tmp_path, monkeypatch):
    from test_tui import _open_long_and_submit
    app, vault = app_for(tmp_path, monkeypatch)
    app.settings.ai_mark_model = MODELS[0]

    async def go():
        async with app.run_test(size=(100, 35)) as pilot:
            await pilot.pause()
            await _open_long_and_submit(pilot, app, "v = u + at")
            screen, finish = app.screen, asyncio.Event()
            before = (vault / "Now.md").read_text()

            async def slow(prompt, **kwargs):
                await finish.wait()
                return None, ai.Result(ok=False, message="Try later.")
            monkeypatch.setattr(app.ai, "one_shot", slow)
            worker = screen.ai_check_long({"ticked": []})
            await pilot.pause(0.05)
            assert "Marking answer" in words(screen) and "Preparing local model" in words(screen)
            assert (vault / "Now.md").read_text() == before
            finish.set()
            await worker.wait()
            await pilot.pause()
            assert not screen.query(".local-progress")
            assert "v = u + at" in (vault / "Now.md").read_text()
            await app.ai.close()
    asyncio.run(go())


def test_local_teaching_cards_have_transient_background_activity(tmp_path, monkeypatch):
    app, _ = app_for(tmp_path, monkeypatch)

    async def go():
        async with app.run_test() as pilot:
            await pilot.pause()
            app.settings.ai = False  # Open the lesson without launching its automatic card request.
            screen = SessionScreen({"mode": "lesson", "focus": ["9702-2.1"], "minutes": 40})
            app.push_screen(screen)
            await pilot.pause()
            app.settings.ai, app.settings.ai_explain_model = True, MODELS[1]
            finish = asyncio.Event()

            async def slow(prompt, **kwargs):
                await finish.wait()
                return None, ai.Result(ok=False)
            monkeypatch.setattr(app.ai, "one_shot", slow)
            worker = screen._write_cards(["9702-2.1.1"])
            await pilot.pause(0.05)
            assert "Writing teaching notes" in words(screen)
            finish.set()
            await worker.wait()
            await pilot.pause()
            assert not screen.query(".local-progress")
            await app.ai.close()
    asyncio.run(go())


def test_local_challenge_explanation_shows_activity_before_first_answer_token(tmp_path, monkeypatch):
    from test_challenge_screen import fake_generator, open_challenge, set_up, start
    app, _ = app_for(tmp_path, monkeypatch)
    app.settings.ai_explain_model = MODELS[2]
    fake_generator(monkeypatch)

    async def go():
        async with app.run_test(size=(100, 35)) as pilot:
            await pilot.pause()
            screen = await open_challenge(pilot, app)
            await set_up(pilot, screen)
            await start(pilot, screen)
            screen.fb = {"answer": "9 m", "response": "6 m"}
            finish = asyncio.Event()

            async def slow(prompt, **kwargs):
                await finish.wait()
                app.ai.last = ai.Result(text="Use the displacement equation.")
                yield app.ai.last.text
            monkeypatch.setattr(app.ai, "stream", slow)
            worker = screen.explain()
            await pilot.pause(0.05)
            assert "Preparing local model" in words(screen)
            finish.set()
            await worker.wait()
            await pilot.pause()
            assert not screen.query(".local-progress")
            assert "Use the displacement equation." in words(screen)
            await app.ai.close()
    asyncio.run(go())


def test_claude_pending_reply_keeps_existing_dots_and_no_local_activity(tmp_path, monkeypatch):
    app, _ = app_for(tmp_path, monkeypatch)

    async def go():
        async with app.run_test() as pilot:
            await pilot.pause()
            app.push_screen(ChatScreen())
            await pilot.pause()
            finish = asyncio.Event()

            async def slow(prompt, **kwargs):
                await finish.wait()
                app.ai.last = ai.Result(text="A Claude reply.")
                yield app.ai.last.text
            monkeypatch.setattr(app.ai, "stream", slow)
            worker = app.screen.reply("Explain a force")
            await pilot.pause(0.05)
            assert "…" in words(app.screen)
            assert "Preparing local model" not in words(app.screen)
            assert not app.screen.query(".local-progress")
            finish.set()
            await worker.wait()
            await app.ai.close()
    asyncio.run(go())


def test_answer_only_session_keeps_local_status_visible_without_revealing_streamed_answer(tmp_path, monkeypatch):
    app, _ = app_for(tmp_path, monkeypatch)
    app.settings.ai_ask_model, app.settings.answer_only = MODELS[0], True

    async def go():
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = SessionScreen({"mode": "test", "focus": ["9702-2.1"], "minutes": 40})
            app.push_screen(screen)
            await pilot.pause()
            finish = asyncio.Event()

            async def slow(prompt, **kwargs):
                yield "An answer that belongs in Obsidian."
                await finish.wait()
                app.ai.last = ai.Result(text="A useful explanation.")
            monkeypatch.setattr(app.ai, "stream", slow)
            worker = screen._stream("Explain", False)
            await pilot.pause(0.05)
            visible = [w for w in screen.query(".local-progress") if w.parent is screen and w.region.height]
            assert visible and "Preparing local model" in words(screen)
            assert "An answer that belongs" not in words(screen)
            finish.set()
            await worker.wait()
            await pilot.pause()
            assert not screen.query(".local-progress")
            await app.ai.close()
    asyncio.run(go())
