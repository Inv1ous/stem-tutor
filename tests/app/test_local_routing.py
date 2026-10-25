"""Local help keeps working independently of Claude and never leaks metrics into notes."""
import asyncio

import pytest

from test_tui import app_for
from tutor_app import ai


@pytest.fixture(autouse=True)
def no_real_preloads(monkeypatch):
    from tutor_app.local_ai import LocalAI

    async def warm(self, model, timeout=120):
        return ai.Result()
    monkeypatch.setattr(LocalAI, "warm", warm)


def test_local_stream_bypasses_missing_claude_and_keeps_usage_separate(tmp_path, monkeypatch):
    from tutor_app import tutor_ai
    from tutor_app.local_models import LOCAL_MODELS

    model = next(iter(LOCAL_MODELS))
    monkeypatch.setattr(tutor_ai.local_models, "available_models", lambda: (model,))

    async def go():
        client = tutor_ai.TutorAI(tmp_path, binary="/missing/claude", model=model)
        finished = []
        client.on_result = finished.append

        async def stream(prompt, **kwargs):
            assert kwargs["model"] == model
            client.local.last = ai.Result(text="A useful hint.", performance={"output_tokens": 8})
            yield "A useful hint."

        monkeypatch.setattr(client.local, "stream", stream)
        assert client.available
        assert not client.available_for("haiku")
        assert "".join([chunk async for chunk in client.stream("Help")]) == "A useful hint."
        assert client.last.text == "A useful hint."
        assert client.session.replies == 0
        assert len(finished) == 1 and finished[0].performance["output_tokens"] == 8
        await client.close()

    asyncio.run(go())


def test_local_marking_bypasses_claude_limit_and_disconnect_does_not_fallback(tmp_path, monkeypatch):
    from tutor_app import tutor_ai
    from tutor_app.local_models import LOCAL_MODELS

    model = next(iter(LOCAL_MODELS))
    connected = [model]
    monkeypatch.setattr(tutor_ai.local_models, "available_models", lambda: tuple(connected))

    async def go():
        client = tutor_ai.TutorAI(tmp_path, binary="/missing/claude")
        client.status = "limit"

        async def one_shot(prompt, **kwargs):
            assert kwargs["model"] == model
            return {"score": 1}, ai.Result(text='{"score":1}', performance={"output_tokens": 4})

        monkeypatch.setattr(client.local, "one_shot", one_shot)
        data, result = await client.one_shot("Mark", model=model)
        assert data == {"score": 1} and result.ok
        connected.clear()
        data, result = await client.one_shot("Mark", model=model)
        assert data is None and not result.ok and "SSD" in result.message
        assert client.status == "limit"
        await client.close()

    asyncio.run(go())


def test_performance_is_terminal_only_for_one_shot_and_stream(tmp_path, monkeypatch):
    from tutor_app import tutor_ai
    from tutor_app.local_models import LOCAL_MODELS
    from tutor_app.screens import ChatScreen

    model = next(iter(LOCAL_MODELS))
    monkeypatch.setattr(tutor_ai.local_models, "available_models", lambda: (model,))
    app, vault = app_for(tmp_path, monkeypatch)
    app.settings.ai_ask_model = model

    async def go():
        async with app.run_test(size=(100, 35)) as pilot:
            await pilot.pause()
            app.push_screen(ChatScreen())
            await pilot.pause()
            result = ai.Result(text="A force changes motion.", performance={
                "model": model, "total_seconds": 2.0, "first_token_seconds": 0.5,
                "load_seconds": 0.2, "tokens_per_second": 15.0, "output_tokens": 30})

            async def stream(prompt, **kwargs):
                app.ai.local.last = result
                yield result.text

            monkeypatch.setattr(app.ai.local, "stream", stream)
            app.screen.reply("Explain a force")
            await app.workers.wait_for_complete()
            await pilot.pause()
            entries = app.screen.query(".local-performance")
            assert len(entries) == 1
            assert "15.0 tok/s" in str(entries.first().render())
            assert "A force changes motion." in (vault / "Now.md").read_text()
            assert "tok/s" not in (vault / "Now.md").read_text()
            assert "tok/s" not in app.ai.last.text

            async def one_shot(prompt, **kwargs):
                return {"answer": 4}, result

            monkeypatch.setattr(app.ai.local, "one_shot", one_shot)
            data, marked = await app.ai.one_shot("Mark", model=model)
            await pilot.pause()
            assert data == {"answer": 4} and marked.ok
            assert len(app.screen.query(".local-performance")) == 2
            assert "tok/s" not in (vault / "Now.md").read_text()
            await app.ai.close()

    asyncio.run(go())


def test_usage_display_combines_weekly_and_cached_ram(tmp_path, monkeypatch):
    app, _ = app_for(tmp_path, monkeypatch)

    async def go():
        async with app.run_test() as pilot:
            await pilot.pause()
            monkeypatch.setattr(app.ai, "limits_text", lambda noted: "week 60% left")
            monkeypatch.setattr(app, "ram_status", lambda: "RAM 12.0/32.0 GiB")
            app.settings.usage_display = "weekly"
            assert app.usage_status() == "week 60% left"
            app.settings.usage_display = "ram"
            assert app.usage_status() == "RAM 12.0/32.0 GiB"
            app.settings.usage_display = "both"
            assert app.usage_status() == "week 60% left · RAM 12.0/32.0 GiB"
            await app.ai.close()

    asyncio.run(go())


def test_explicit_cloud_model_still_works_when_default_local_model_is_unplugged(tmp_path, monkeypatch):
    from pathlib import Path
    from tutor_app import tutor_ai

    monkeypatch.setattr(tutor_ai.local_models, "available_models", lambda: ())

    async def go():
        client = tutor_ai.TutorAI(tmp_path, binary=str(Path(__file__).with_name("fake_claude.py")),
                                  model="ollama:qwen3.5:9b")
        data, result = await client.one_shot("Mark", model="haiku")
        assert result.ok
        await client.close()

    asyncio.run(go())


def test_mode_availability_does_not_depend_on_ask_model(tmp_path, monkeypatch):
    from tutor_app import tutor_ai
    from tutor_app.screens import SessionScreen

    model = "ollama:qwen3.5:9b"
    monkeypatch.setattr(tutor_ai.local_models, "available_models", lambda: (model,))
    app, _ = app_for(tmp_path, monkeypatch)
    app.settings.ai_mark_model = model
    app.settings.ai_explain_model = model

    async def go():
        async with app.run_test() as pilot:
            await pilot.pause()
            app.ai.status = "off"
            app.push_screen(SessionScreen({"mode": "test", "minutes": 40, "focus": ["9702-2.1"]}))
            await pilot.pause()
            assert app.screen.ai_ok("mark")
            assert app.screen.ai_ok("explain")
            assert not app.screen.ai_ok("ask")
            await app.ai.close()

    asyncio.run(go())


def test_closing_routed_stream_closes_local_generator_immediately(tmp_path, monkeypatch):
    from tutor_app import tutor_ai

    model = "ollama:qwen3.5:9b"
    monkeypatch.setattr(tutor_ai.local_models, "available_models", lambda: (model,))

    async def go():
        client = tutor_ai.TutorAI(tmp_path, binary="/missing/claude", model=model)
        closed = []

        async def stream(*args, **kwargs):
            try:
                yield "First chunk"
                yield "Second chunk"
            finally:
                closed.append(True)

        monkeypatch.setattr(client.local, "stream", stream)
        reply = client.stream("Help")
        assert await anext(reply) == "First chunk"
        await reply.aclose()
        assert closed == [True]
        await client.close()

    asyncio.run(go())


def test_performance_without_first_token_timing_does_not_break_reply(tmp_path, monkeypatch):
    app, _ = app_for(tmp_path, monkeypatch)

    async def go():
        async with app.run_test() as pilot:
            await pilot.pause()
            app.show_local_performance(ai.Result(performance={"model": "ollama:qwen3.5:9b",
                                                             "first_token_seconds": None}))
            await pilot.pause()
            await app.ai.close()

    asyncio.run(go())


def test_talk_it_through_uses_ask_model_availability(tmp_path, monkeypatch):
    from tutor_app import tutor_ai
    from tutor_app.panels import ContinuePanel
    from tutor_app.screens import SessionScreen

    model = "ollama:qwen3.5:9b"
    monkeypatch.setattr(tutor_ai.local_models, "available_models", lambda: (model,))
    app, _ = app_for(tmp_path, monkeypatch)
    app.settings.ai_ask_model = model

    async def go():
        async with app.run_test(size=(100, 35)) as pilot:
            await pilot.pause()
            app.push_screen(SessionScreen({"mode": "test", "minutes": 40, "focus": ["9702-2.1"]}))
            await pilot.pause()
            app.ai.status = "off"
            monkeypatch.setattr(app.tutor, "next", lambda: {"activity": "stuck", "say": "Try once more."})
            app.screen.advance()
            await pilot.pause()
            panel = app.screen.query_one("#panel ContinuePanel", ContinuePanel)
            assert "talk" in [button.id for button in panel.query("Button")]
            await app.ai.close()

    asyncio.run(go())


def test_narrow_session_keeps_full_ram_and_weekly_values(tmp_path, monkeypatch):
    from rich.cells import cell_len
    from tutor_app.screens import SessionScreen

    app, _ = app_for(tmp_path, monkeypatch)
    app.settings.usage_display = "both"
    monkeypatch.setattr(app, "usage_status", lambda: "week ~58% left · RAM 29.2/32.0 GiB")

    async def go():
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            app.push_screen(SessionScreen({"mode": "test", "minutes": 40, "focus": ["9702-2.1"]}))
            await pilot.pause()
            for width in (60, 80):
                text = app.screen.bar_text(width).plain
                assert "week ~58% left" in text and "RAM 29.2/32.0 GiB" in text
                assert "true" in text and "session" in text
                assert len(text.splitlines()) <= 2
                assert all(cell_len(line) <= width for line in text.splitlines())
            await app.ai.close()

    asyncio.run(go())


def test_local_preload_works_without_claude_and_reset_does_not_load_wrong_model(tmp_path, monkeypatch):
    from tutor_app import tutor_ai

    ask, explain = "ollama:qwen3.5:9b", "ollama:gemma4:26b-a4b-it-qat"
    monkeypatch.setattr(tutor_ai.local_models, "available_models", lambda: (ask, explain))

    async def go():
        client = tutor_ai.TutorAI(tmp_path, binary="/missing/claude", model=ask)
        warmed = []

        async def warm(model, timeout=120):
            warmed.append(model)
            return ai.Result()

        monkeypatch.setattr(client.local, "warm", warm)
        await client.warm(model=explain)
        assert warmed == [explain]
        await client.reset()
        await asyncio.sleep(0)
        assert warmed == [explain]
        client.wanted = lambda: False
        await client.warm(model=ask)
        assert warmed == [explain]
        await client.close()

    asyncio.run(go())


def test_leaving_local_session_cancels_its_preload(tmp_path, monkeypatch):
    from tutor_app import tutor_ai
    from tutor_app.screens import SessionScreen

    model = "ollama:qwen3.8:27b"
    monkeypatch.setattr(tutor_ai.local_models, "available_models", lambda: (model,))
    app, _ = app_for(tmp_path, monkeypatch)
    app.settings.ai_explain_model = model

    async def go():
        started, stopped = asyncio.Event(), asyncio.Event()
        async with app.run_test(size=(100, 35)) as pilot:
            await pilot.pause()

            async def warm(model, timeout=120):
                started.set()
                try:
                    await asyncio.Event().wait()
                finally:
                    stopped.set()

            monkeypatch.setattr(app.ai.local, "warm", warm)
            app.push_screen(SessionScreen({"mode": "test", "minutes": 40, "focus": ["9702-2.1"]}))
            await pilot.pause()
            await asyncio.wait_for(started.wait(), 1)
            app.pop_screen()
            await pilot.pause()
            assert stopped.is_set()
            await app.ai.close()

    asyncio.run(go())


def test_real_request_cancels_preload_of_a_different_model(tmp_path, monkeypatch):
    from tutor_app import tutor_ai

    explain, ask = "ollama:qwen3.8:27b", "ollama:qwen3.5:9b"
    monkeypatch.setattr(tutor_ai.local_models, "available_models", lambda: (explain, ask))
    app, _ = app_for(tmp_path, monkeypatch)
    app.settings.ai_explain_model = explain

    async def go():
        started, stopped = asyncio.Event(), asyncio.Event()
        async with app.run_test() as pilot:
            await pilot.pause()

            async def warm(model, timeout=120):
                started.set()
                try:
                    await asyncio.Event().wait()
                finally:
                    stopped.set()

            async def stream(prompt, **kwargs):
                app.ai.local.last = ai.Result(text="A hint")
                yield "A hint"

            monkeypatch.setattr(app.ai.local, "warm", warm)
            monkeypatch.setattr(app.ai.local, "stream", stream)
            app.prepare_local_ai("explain")
            await asyncio.wait_for(started.wait(), 1)
            assert "".join([piece async for piece in app.ai.stream("Help", model=ask)]) == "A hint"
            await pilot.pause()
            assert stopped.is_set()
            await app.ai.close()

    asyncio.run(go())
