"""Native effort remains explicit without changing saved cloud switches."""
import asyncio
import json

import pytest
from textual.widgets import Button, Select, Static, Switch

from test_tui import app_for
from tutor_app import config, local_models, presets


GPT = "mlx:gpt-oss:20b"
GEMMA = "ollama:gemma4:26b-tutor-mlx"
QWEN = "ollama:qwen3.8:27b"


@pytest.mark.parametrize("model,value,want", [
    (GPT, False, "low"), (GPT, True, "high"), (GPT, "medium", "medium"),
    ("ollama:gpt-oss:20b", "medium", "medium"),
    (QWEN, False, False), (QWEN, True, "xhigh"), (QWEN, "off", False),
    (QWEN, "low", "low"), (QWEN, "medium", "medium"), (QWEN, "xhigh", "xhigh"),
    (GEMMA, False, False), (GEMMA, True, True),
])
def test_native_reasoning_values_and_history_identity(model, value, want):
    assert local_models.thinking_value(model, value) == want
    assert local_models.thinking_key(model, value) == want


@pytest.mark.parametrize("model,value", [(GPT, "off"), (GPT, "xhigh"), (QWEN, "high"),
                                        (GEMMA, "medium"), ("ollama:lfm2.5:8b", "low"),
                                        ("ollama:phi4-mini:3.8b", "low")])
def test_unsupported_named_strength_is_rejected(model, value):
    with pytest.raises(ValueError):
        local_models.thinking_value(model, value)


def test_legacy_and_explicit_settings_roundtrip_without_touching_cloud(tmp_path):
    folder = tmp_path / ".tutor"
    folder.mkdir()
    (folder / "app_settings.json").write_text(json.dumps({
        "ai_mark_model": GPT, "ai_mark_think": False,
        "ai_explain_model": QWEN, "ai_explain_think": True, "ai_explain_effort": "medium",
        "ai_ask_model": "codex:gpt-6.1-sol", "ai_ask_think": False, "ai_ask_effort": "high",
    }))
    settings = config.Settings.load(tmp_path)
    assert settings.ai_for("mark") == (GPT, False)
    assert settings.ai_mark_effort == ""
    assert settings.ai_for("explain") == (QWEN, "medium")
    assert settings.ai_for("ask") == ("codex:gpt-6.1-sol", False)
    settings.save(tmp_path)
    saved = config.Settings.load(tmp_path)
    assert saved.ai_for("mark") == (GPT, False)
    assert saved.ai_for("explain") == (QWEN, "medium")
    assert saved.ai_for("ask") == ("codex:gpt-6.1-sol", False)


def test_invalid_saved_strength_falls_back_to_legacy_boolean(tmp_path):
    folder = tmp_path / ".tutor"
    folder.mkdir()
    (folder / "app_settings.json").write_text(json.dumps({
        "ai_ask_model": QWEN, "ai_ask_think": True, "ai_ask_effort": "high",
    }))
    assert config.Settings.load(tmp_path).ai_for("ask") == (QWEN, True)


def test_preset_matching_understands_legacy_local_aliases_without_cloud_coercion():
    choices = {"mark": (GEMMA, False), "explain": (GPT, False), "ask": (GPT, "low")}
    assert presets.matching(choices) == "local_reasoning"
    choices["ask"] = (GPT, "medium")
    assert presets.matching(choices) == "custom"
    assert presets.matching({mode: ("haiku", "low") for mode in config.AI_MODES}) == "custom"


@pytest.fixture
def isolated_models(monkeypatch):
    from tutor_app.ai import Result
    from tutor_app.local_ai import LocalAI

    async def warm(self, model, timeout=120):
        return Result()
    monkeypatch.setattr(LocalAI, "warm", warm)
    monkeypatch.setattr(local_models, "available_models", lambda: tuple(local_models.LOCAL_MODELS))


@pytest.mark.parametrize("size", [(60, 24), (80, 24), (100, 24)])
def test_effort_only_keyboard_edit_is_custom_and_save_preserves_cloud_switch(
        tmp_path, monkeypatch, isolated_models, size):
    app, vault = app_for(tmp_path, monkeypatch)
    app.settings.ai_ask_model = GPT
    app.settings.ai_mark_model, app.settings.ai_mark_think = "sonnet", True

    async def go():
        async with app.run_test(size=size) as pilot:
            await pilot.pause()
            app.action_settings()
            await pilot.pause()
            screen = app.screen
            strength = screen.query_one("#ai_ask_effort", Select)
            assert strength.display and strength.value == "low"
            assert not screen.query_one("#ai_ask_think", Switch).display
            assert not screen.query_one("#ai_mark_effort", Select).display
            assert screen.query_one("#ai_mark_think", Switch).display
            assert strength.region.width <= 12
            assert strength.parent.content_region.contains_region(strength.region)
            model = screen.query_one("#ai_ask_model", Select)
            assert model.parent.content_region.contains_region(model.region)
            label = screen.query_one("#ai_ask_label", Static)
            assert label.region.width >= 9
            assert label.region.right < model.region.x
            strength.focus()
            await pilot.press("enter", "down", "enter")
            await pilot.pause()
            assert strength.value == "medium"
            assert screen.query_one("#ai_preset", Select).value == "custom"
            assert screen._task_choices()["ask"] == (GPT, "medium")
            screen.query_one("#save", Button).press()
            await pilot.pause()
            saved = config.Settings.load(vault)
            assert saved.ai_for("ask") == (GPT, "medium")
            assert saved.ai_for("mark") == ("sonnet", True)
            assert saved.ai_ask_think is False
            await app.ai.close()
    asyncio.run(go())


def test_mlx_preset_preview_apply_cancel_and_disconnected_effort_save(tmp_path, monkeypatch, isolated_models):
    present = list(local_models.LOCAL_MODELS)
    monkeypatch.setattr(local_models, "available_models", lambda: tuple(present))
    app, vault = app_for(tmp_path, monkeypatch)

    async def go():
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            app.action_settings()
            await pilot.pause()
            screen = app.screen
            screen.query_one("#ai_preset", Select).value = "local_deep"
            await pilot.pause()
            assert "high reasoning" in str(screen.query_one("#preset-preview", Static).content)
            screen.query_one("#apply-preset", Button).press()
            await pilot.pause()
            assert screen._task_choices()["ask"] == (GPT, "high")
            await pilot.press("escape")
            assert app.settings.ai_for("ask") == ("haiku", False)
            app.settings.ai_ask_model, app.settings.ai_ask_effort = GPT, "medium"
            app.action_settings()
            await pilot.pause()
            screen = app.screen
            present.clear()
            screen._refresh_models()
            await pilot.pause()
            assert screen.query_one("#ai_ask_model", Select).value is Select.NULL
            assert screen.query_one("#ai_ask_effort", Select).value == "medium"
            screen.query_one("#save", Button).press()
            await pilot.pause()
            assert config.Settings.load(vault).ai_for("ask") == (GPT, "medium")
            await app.ai.close()
    asyncio.run(go())


def test_unknown_backend_performance_is_omitted_and_wall_time_stays_visible(tmp_path, monkeypatch):
    from tutor_app.ai import Result
    app, _ = app_for(tmp_path, monkeypatch)
    notices = []
    monkeypatch.setattr(app, "notify", lambda message, **kwargs: notices.append(message))

    async def go():
        async with app.run_test() as pilot:
            await pilot.pause()
            notices.clear()
            app.show_local_performance(Result(performance={
                "model": GPT, "tokens_per_second": None, "load_seconds": None,
                "first_token_seconds": 1.2, "total_seconds": 2.3, "output_tokens": None,
            }))
            assert len(notices) == 1
            assert "first 1.2s" in notices[0] and "total 2.3s" in notices[0]
            assert "0.0 tok/s" not in notices[0] and "None" not in notices[0]
            await app.ai.close()
    asyncio.run(go())


def test_unrelated_cloud_save_keeps_blank_legacy_effort(tmp_path, monkeypatch, isolated_models):
    app, vault = app_for(tmp_path, monkeypatch)

    async def go():
        async with app.run_test() as pilot:
            await pilot.pause()
            app.action_settings()
            await pilot.pause()
            app.screen.query_one("#save", Button).press()
            await pilot.pause()
            saved = config.Settings.load(vault)
            assert [getattr(saved, f"ai_{mode}_effort") for mode in config.AI_MODES] == ["", "", ""]
            await app.ai.close()
    asyncio.run(go())


@pytest.mark.parametrize("model,effort,want", [(GPT, "medium", "medium"), (QWEN, "off", False),
                                             ("haiku", "high", True), ("codex:gpt-6-luna", "low", True),
                                             (GEMMA, "medium", True)])
def test_remarking_honors_only_applicable_local_strength(tmp_path, monkeypatch, isolated_models, model, effort, want):
    from tutor_app.ai import Result
    from tutor_app.screens import SessionScreen
    app, _ = app_for(tmp_path, monkeypatch)
    app.settings.ai_mark_model, app.settings.ai_mark_effort = model, effort
    monkeypatch.setattr(app, "prepare_local_ai", lambda mode: None)

    async def go():
        async with app.run_test() as pilot:
            await pilot.pause()
            app.push_screen(SessionScreen({"mode": "test", "minutes": 40, "focus": ["9702-2.1"]}))
            await pilot.pause()
            screen = app.screen
            screen.last_fb = {"answer": "9 m", "response": "6 m"}
            calls = []

            async def answer(prompt, **kwargs):
                calls.append((kwargs["model"], kwargs["think"]))
                return None, Result(ok=False)
            monkeypatch.setattr(app.ai, "one_shot", answer)
            await screen.remark().wait()
            assert calls == [(model if model != "haiku" else "sonnet", want)]
            await app.ai.close()
    asyncio.run(go())
