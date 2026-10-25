"""Home-menu free chat prepares Ask after reset and restores preparation after Settings."""
import asyncio
from types import SimpleNamespace

import pytest
from textual.widgets import Button, Select

from test_tui import app_for
from tutor_app import local_models
from tutor_app.local_ai import LocalAI
from tutor_app.local_ocr import NativeOCR
from tutor_app.panels import Composer
from tutor_app.screens import ChatScreen


MODELS = ("ollama:qwen3.5:9b", "ollama:gemma4:26b-a4b-it-qat", "ollama:qwen3.8:27b")


@pytest.fixture
def backend(monkeypatch):
    monkeypatch.setattr(local_models, "available_models", lambda: MODELS)
    state = SimpleNamespace(loads=[], prompts=[], cancelled=[], cleanup_started=asyncio.Event(),
                            cleanup_done=asyncio.Event(), release_cleanup=asyncio.Event(), release_load=asyncio.Event())
    async def events(self, payload, timeout, path="/api/chat"):
        if payload["messages"]:
            state.prompts.append(payload)
            yield {"message": {"content": '{"reply":"A force can change motion."}'}, "done": True}
        else:
            state.loads.append((payload["model"], self._generation))
            try:
                await state.release_load.wait()
                yield {"done": True, "done_reason": "load"}
            except asyncio.CancelledError:
                state.cancelled.append(payload["model"])
                raise
    async def stop_ocr(proc):
        state.cleanup_started.set()
        await state.release_cleanup.wait()
        state.cleanup_done.set()
    monkeypatch.setattr(LocalAI, "_events", events)
    monkeypatch.setattr(NativeOCR, "_stop", staticmethod(stop_ocr))
    return state


async def open_chat(pilot, app):
    menu = app.screen.query_one("#menu")
    menu.highlighted = [option.id for option in menu.options].index("chat")
    await pilot.press("enter")
    await pilot.pause()
    assert isinstance(app.screen, ChatScreen)
    return app.screen


def pending_ocr(app):
    app.ai.local  # retain an old local generation that the pending reset must revoke
    app.ai._ocr = NativeOCR()
    app.ai._ocr._procs.add(object())


async def close_ai(app, backend):
    backend.release_cleanup.set()
    backend.release_load.set()
    await app.ai.close()


@pytest.mark.parametrize("model", MODELS)
def test_home_anything_chat_preloads_selected_ask_before_send(tmp_path, monkeypatch, backend, model):
    app, _ = app_for(tmp_path, monkeypatch)
    app.settings.ai_ask_model = model
    async def go():
        async with app.run_test(size=(100, 35)) as pilot:
            await pilot.pause()
            chat = await open_chat(pilot, app)
            assert backend.loads == [(model.removeprefix("ollama:"), app.ai.local._generation)]
            assert app._preload_owner is chat and not backend.prompts
            await pilot.press(*"what is a force")
            assert chat.query_one("#panel Composer", Composer).text == "what is a force"
            app.pop_screen()
            await pilot.pause()
            assert backend.cancelled == [model.removeprefix("ollama:")]
            await close_ai(app, backend)
    asyncio.run(go())


def test_free_chat_reset_finishes_before_preload_starts(tmp_path, monkeypatch, backend):
    app, _ = app_for(tmp_path, monkeypatch)
    app.settings.ai_ask_model = MODELS[0]
    async def go():
        async with app.run_test() as pilot:
            await pilot.pause()
            pending_ocr(app)
            try:
                chat = await open_chat(pilot, app)
                assert backend.cleanup_started.is_set()
                assert backend.loads == [], "A preload started before reset can be invalidated by that reset"
                await pilot.press(*"still typing")
                assert chat.query_one("#panel Composer", Composer).text == "still typing"
                backend.release_cleanup.set()
                await pilot.pause()
                assert backend.cleanup_done.is_set() and len(backend.loads) == 1
                assert backend.loads[0][1] == app.ai.local._generation
                backend.release_load.set()
                await app.workers.wait_for_complete()
                assert app.ai.progress_for(MODELS[0])["phase"] == "done"
                assert not backend.prompts
            finally:
                await close_ai(app, backend)
    asyncio.run(go())


def test_free_chat_early_send_waits_for_reset_before_model_requests(tmp_path, monkeypatch, backend):
    app, _ = app_for(tmp_path, monkeypatch)
    app.settings.ai_ask_model = MODELS[0]
    backend.release_load.set()
    async def go():
        async with app.run_test() as pilot:
            await pilot.pause()
            pending_ocr(app)
            try:
                await open_chat(pilot, app)
                await pilot.press(*"what is a force", "enter")
                await pilot.pause()
                assert not backend.loads and not backend.prompts, "An early Send must not race the old conversation reset"
                backend.release_cleanup.set()
                await app.workers.wait_for_complete()
                assert len(backend.prompts) == 1 and app.ai.last.ok
                assert "what is a force" in backend.prompts[0]["messages"][-1]["content"]
            finally:
                await close_ai(app, backend)
    asyncio.run(go())


def test_second_send_does_not_cancel_shared_chat_reset(tmp_path, monkeypatch, backend):
    app, _ = app_for(tmp_path, monkeypatch)
    app.settings.ai_ask_model = MODELS[0]
    backend.release_load.set()
    async def go():
        async with app.run_test() as pilot:
            await pilot.pause()
            pending_ocr(app)
            try:
                chat = await open_chat(pilot, app)
                await pilot.press(*"first question", "enter")
                await pilot.pause()
                await pilot.press(*"second question", "enter")
                await pilot.pause()
                assert not backend.prompts and not chat._chat_ready
                backend.release_cleanup.set()
                await app.workers.wait_for_complete()
                assert app.screen is chat and chat._chat_ready
                assert len(backend.prompts) == 1 and app.ai.last.ok
                assert "second question" in backend.prompts[0]["messages"][-1]["content"]
            finally:
                await close_ai(app, backend)
    asyncio.run(go())


@pytest.mark.parametrize("send", [False, True])
def test_leaving_free_chat_during_reset_never_starts_late_preload(tmp_path, monkeypatch, backend, send):
    app, _ = app_for(tmp_path, monkeypatch)
    app.settings.ai_ask_model = MODELS[0]
    async def go():
        async with app.run_test() as pilot:
            await pilot.pause()
            pending_ocr(app)
            try:
                await open_chat(pilot, app)
                if send:
                    await pilot.press(*"what is a force", "enter")
                    await pilot.pause()
                app.pop_screen()
                backend.release_cleanup.set()
                await pilot.pause()
                assert not backend.loads and not backend.prompts
                assert getattr(app, "_preload_owner", None) is None
            finally:
                await close_ai(app, backend)
    asyncio.run(go())


@pytest.mark.parametrize("action", ["cancel", "change_model"])
def test_free_chat_restores_current_ask_preload_after_settings(tmp_path, monkeypatch, backend, action):
    app, _ = app_for(tmp_path, monkeypatch)
    app.settings.ai_ask_model = MODELS[0]
    async def go():
        async with app.run_test() as pilot:
            await pilot.pause()
            chat = await open_chat(pilot, app)
            assert len(backend.loads) == 1
            app.action_settings()
            await pilot.pause()
            assert backend.cancelled == ["qwen3.5:9b"]
            if action == "cancel":
                await pilot.press("escape")
            else:
                app.screen.query_one("#ai_ask_model", Select).value = MODELS[1]
                app.screen.query_one("#save", Button).press()
            await pilot.pause()
            assert app.screen is chat
            selected = MODELS[0] if action == "cancel" else MODELS[1]
            assert [name for name, _ in backend.loads] == ["qwen3.5:9b", selected.removeprefix("ollama:")]
            assert app._preload_owner is chat and not backend.prompts
            await close_ai(app, backend)
    asyncio.run(go())


@pytest.mark.parametrize("model,enabled", [("haiku", True), ("codex:gpt-6-luna", True), (MODELS[0], False)])
def test_cloud_or_disabled_free_chat_never_starts_local_preparation(tmp_path, monkeypatch, backend, model, enabled):
    app, _ = app_for(tmp_path, monkeypatch)
    app.settings.ai_ask_model, app.settings.ai = model, enabled
    async def go():
        async with app.run_test() as pilot:
            await pilot.pause()
            await open_chat(pilot, app)
            app.action_settings()
            await pilot.pause()
            await pilot.press("escape")
            await pilot.pause()
            assert app.ai._local is None and not backend.loads and not backend.prompts
            await close_ai(app, backend)
    asyncio.run(go())
