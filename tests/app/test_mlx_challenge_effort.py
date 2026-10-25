"""An explicit local marking strength applies to challenge re-marking too."""
import asyncio

import pytest

from test_challenge_screen import fake_generator, open_challenge, set_up, start
from test_tui import app_for
from tutor_app import local_models
from tutor_app.ai import Result


@pytest.mark.parametrize("model,effort,want", [
    ("mlx:gpt-oss:20b", "medium", "medium"),
    ("ollama:qwen3.8:27b", "off", False),
    ("haiku", "high", True),
    ("codex:gpt-6-luna", "low", True),
    ("ollama:gemma4:e4b", "medium", True),
])
def test_challenge_remark_uses_explicit_applicable_local_effort(tmp_path, monkeypatch, model, effort, want):
    monkeypatch.setattr(local_models, "available_models", lambda: tuple(local_models.LOCAL_MODELS))
    app, _ = app_for(tmp_path, monkeypatch)
    app.settings.ai_mark_model, app.settings.ai_mark_effort = model, effort
    fake_generator(monkeypatch)
    monkeypatch.setattr(app, "prepare_local_ai", lambda mode: None)
    async def go():
        async with app.run_test(size=(100, 35)) as pilot:
            await pilot.pause()
            screen = await open_challenge(pilot, app)
            await set_up(pilot, screen)
            await start(pilot, screen)
            screen.fb = {"answer": "9 m", "response": "6 m", "correct": False}
            calls = []
            async def answer(prompt, **kwargs):
                calls.append((kwargs["model"], kwargs["think"]))
                return None, Result(ok=False)
            monkeypatch.setattr(app.ai, "one_shot", answer)
            await screen.remark().wait()
            assert calls == [(model if model != "haiku" else "sonnet", want)]
            await app.ai.close()
    asyncio.run(go())
