"""AI presets preview first, apply only to the dialog, then use the normal settings Save."""
import asyncio
import importlib
import json

import pytest
from textual.widgets import Button, Input, Select, Static, Switch

from test_tui import app_for
from tutor_app import config, local_models


def presets_module():
    return importlib.import_module("tutor_app.presets")


@pytest.fixture(autouse=True)
def no_real_local_preloads(monkeypatch):
    from tutor_app.ai import Result
    from tutor_app.local_ai import LocalAI

    async def warm(self, model, timeout=120):
        return Result()
    monkeypatch.setattr(LocalAI, "warm", warm)


def run(app, steps, size=(80, 24)):
    async def go():
        async with app.run_test(size=size) as pilot:
            await pilot.pause()
            await steps(pilot)
            await app.ai.close()
    asyncio.run(go())


def task_choices(screen):
    return {mode: (screen._selected_model(mode), screen.query_one(f"#ai_{mode}_think", Switch).value)
            for mode in ("mark", "explain", "ask")}


async def wait_for(pilot, condition):
    for _ in range(40):
        await pilot.pause(0.1)
        if condition():
            return
    assert condition(), "Settings did not detect the model availability change."


@pytest.mark.parametrize("name,model", [("claude_fast", "haiku"), ("claude_balanced", "sonnet"),
                                       ("chatgpt_fast", "codex:gpt-6-luna"),
                                       ("chatgpt_strong", "codex:gpt-6.1-sol")])
def test_cloud_presets_stay_provider_only_with_thinking_off(name, model):
    preset = presets_module().PRESETS[name]
    assert [preset.ai_for(mode) for mode in ("mark", "explain", "ask")] == [(model, False)] * 3


@pytest.mark.parametrize("name,model,think", [
    ("local_fast", "ollama:gemma4:e4b", False),
    ("local_precise", "ollama:gemma4:26b-tutor-mlx", False),
    ("local_reasoning", "mlx:gpt-oss:20b", "low"),
    ("local_medium", "mlx:gpt-oss:20b", "medium"),
    ("local_deep", "mlx:gpt-oss:20b", "high"),
])
def test_curated_local_presets_keep_strong_marking_and_explicit_tutor_thinking(name, model, think):
    presets = presets_module()
    preset = presets.PRESETS[name]
    assert preset.provider == "local"
    assert preset.ai_for("mark") == ("ollama:gemma4:26b-tutor-mlx", False)
    assert [preset.ai_for(mode) for mode in ("explain", "ask")] == [(model, think)] * 2
    assert not presets.is_available(name, ())
    assert presets.is_available(name, ("ollama:gemma4:26b-tutor-mlx", model))
    if model != "ollama:gemma4:26b-tutor-mlx":
        assert not presets.is_available(name, (model,))


def test_preset_catalogue_has_two_per_cloud_provider_and_five_local_setups():
    presets = presets_module()
    assert len(presets.PRESETS) == 9
    assert [preset.provider for preset in presets.PRESETS.values()].count("claude") == 2
    assert [preset.provider for preset in presets.PRESETS.values()].count("chatgpt") == 2
    assert [preset.provider for preset in presets.PRESETS.values()].count("local") == 5
    for preset in presets.PRESETS.values():
        assert all(model in config.AI_MODELS for model in preset.required_models)
        if preset.provider == "local":
            assert all(local_models.is_local(model) for model in preset.required_models)


def test_medium_preset_previews_then_applies_and_saves_explicit_task_strengths(tmp_path, monkeypatch):
    monkeypatch.setattr(local_models, "available_models", lambda: tuple(local_models.LOCAL_MODELS))
    app, vault = app_for(tmp_path, monkeypatch)

    async def steps(pilot):
        app.action_settings()
        await pilot.pause()
        screen = app.screen
        selected = screen.query_one("#ai_preset", Select)
        assert "local_medium" in [value for _, value in selected._options]
        selected.value = "local_medium"
        await pilot.pause()
        preview = str(screen.query_one("#preset-preview", Static).content)
        assert "Gemma 4 26B (local MLX)" in preview and "GPT-OSS 20B (local MLX; text only)" in preview
        assert "Explaining: GPT-OSS 20B (local MLX; text only) · medium reasoning" in preview
        assert "Ask the tutor: GPT-OSS 20B (local MLX; text only) · medium reasoning" in preview
        assert app.settings.ai_for("ask") == ("haiku", False)
        assert screen.query_one("#ai_ask_model", Select).value == "haiku"
        screen.query_one("#apply-preset", Button).press()
        await pilot.pause()
        assert screen.query_one("#ai_mark_model", Select).value == "ollama:gemma4:26b-tutor-mlx"
        assert screen.query_one("#ai_mark_think", Switch).value is False
        for mode in ("explain", "ask"):
            assert screen.query_one(f"#ai_{mode}_model", Select).value == "mlx:gpt-oss:20b"
            assert screen.query_one(f"#ai_{mode}_effort", Select).value == "medium"
        assert selected.value == "local_medium"
        assert app.settings.ai_for("ask") == ("haiku", False)
        screen.query_one("#save", Button).press()
        await pilot.pause()
        saved = config.Settings.load(vault)
        choices = {mode: saved.ai_for(mode) for mode in config.AI_MODES}
        assert choices == {"mark": ("ollama:gemma4:26b-tutor-mlx", False),
                           "explain": ("mlx:gpt-oss:20b", "medium"), "ask": ("mlx:gpt-oss:20b", "medium")}
        assert presets_module().matching(choices) == "local_medium"
    run(app, steps)


def test_preview_then_apply_changes_only_task_rows_until_save(tmp_path, monkeypatch):
    app, vault = app_for(tmp_path, monkeypatch)
    app.settings.minutes, app.settings.usage_display, app.settings.local_web = 55, "ram", False

    async def steps(pilot):
        app.action_settings()
        await pilot.pause()
        screen = app.screen
        screen.query_one("#ai_preset", Select).value = "claude_balanced"
        await pilot.pause()
        preview = str(screen.query_one("#preset-preview", Static).content)
        assert "Sonnet" in preview and "Marking" in preview and "Explaining" in preview and "Ask" in preview
        assert task_choices(screen) == {mode: ("haiku", False) for mode in ("mark", "explain", "ask")}
        screen.query_one("#apply-preset", Button).press()
        await pilot.pause()
        assert task_choices(screen) == {mode: ("sonnet", False) for mode in ("mark", "explain", "ask")}
        assert app.settings.ai_for("ask") == ("haiku", False)
        assert not (vault / ".tutor" / "app_settings.json").exists()
        screen.query_one("#save", Button).press()
        await pilot.pause()
        saved = config.Settings.load(vault)
        assert all(saved.ai_for(mode) == ("sonnet", False) for mode in ("mark", "explain", "ask"))
        assert saved.minutes == 55 and saved.usage_display == "ram" and saved.local_web is False
        data = json.loads((vault / ".tutor" / "app_settings.json").read_text())
        assert "ai_preset" not in data  # per-task choices remain the single source of truth
    run(app, steps)


def test_cancel_after_apply_keeps_saved_and_live_settings(tmp_path, monkeypatch):
    app, vault = app_for(tmp_path, monkeypatch)

    async def steps(pilot):
        app.action_settings()
        await pilot.pause()
        app.screen.query_one("#ai_preset", Select).value = "chatgpt_strong"
        app.screen.query_one("#apply-preset", Button).press()
        await pilot.pause()
        assert task_choices(app.screen)["ask"] == ("codex:gpt-6.1-sol", False)
        await pilot.press("escape")
        assert app.settings.ai_for("ask") == ("haiku", False)
        assert config.Settings.load(vault).ai_for("ask") == ("haiku", False)
    run(app, steps)


def test_manual_task_change_marks_applied_preset_custom(tmp_path, monkeypatch):
    app, _ = app_for(tmp_path, monkeypatch)

    async def steps(pilot):
        app.action_settings()
        await pilot.pause()
        screen = app.screen
        screen.query_one("#ai_preset", Select).value = "claude_balanced"
        screen.query_one("#apply-preset", Button).press()
        await pilot.pause()
        assert screen.query_one("#ai_preset", Select).value == "claude_balanced"
        screen.query_one("#ai_ask_model", Select).value = "opus"
        screen.query_one("#ai_mark_think", Switch).value = True
        await pilot.pause()
        assert screen.query_one("#ai_preset", Select).value == "custom"
        assert "Custom" in str(screen.query_one("#preset-status", Static).content)
        assert screen.query_one("#apply-preset", Button).disabled
    run(app, steps)


def test_local_preset_hotplug_requires_every_model_and_keeps_unsaved_task_choices(tmp_path, monkeypatch):
    presets = presets_module()
    pair = presets.Preset("Local: test pair", "A local pair for this fixture.", "local",
                          ("ollama:qwen3.5:9b", False), ("ollama:gemma4:26b-a4b-it-qat", False),
                          ("ollama:qwen3.5:9b", False))
    monkeypatch.setitem(presets.PRESETS, "test_pair", pair)
    present = ["ollama:qwen3.5:9b"]
    monkeypatch.setattr(local_models, "available_models", lambda: tuple(present))
    app, _ = app_for(tmp_path, monkeypatch)

    async def steps(pilot):
        app.action_settings()
        await pilot.pause()
        screen = app.screen
        preset = screen.query_one("#ai_preset", Select)
        assert "test_pair" not in [value for _, value in preset._options]
        screen.query_one("#ai_ask_model", Select).value = "sonnet"
        screen.query_one("#minutes", Input).value = "73"
        present.append("ollama:gemma4:26b-a4b-it-qat")
        await wait_for(pilot, lambda: "test_pair" in [value for _, value in preset._options])
        assert "test_pair" in [value for _, value in preset._options]
        preset.value = "test_pair"
        await pilot.pause()
        present.clear()
        screen.query_one("#apply-preset", Button).press()  # recheck just before applying, without waiting for polling
        await pilot.pause()
        assert preset.value is Select.NULL
        assert screen.query_one("#apply-preset", Button).disabled
        assert "Reconnect" in str(screen.query_one("#preset-preview", Static).content)
        assert task_choices(screen)["ask"] == ("sonnet", False)
        assert screen.query_one("#minutes", Input).value == "73"
        present[:] = ["ollama:qwen3.5:9b", "ollama:gemma4:26b-a4b-it-qat"]
        await wait_for(pilot, lambda: preset.value == "test_pair")
        assert preset.value == "test_pair" and not screen.query_one("#apply-preset", Button).disabled
        assert task_choices(screen)["ask"] == ("sonnet", False)
        screen.query_one("#apply-preset", Button).press()
        await pilot.pause()
        assert task_choices(screen)["mark"] == ("ollama:qwen3.5:9b", False)
        assert task_choices(screen)["explain"] == ("ollama:gemma4:26b-a4b-it-qat", False)
        assert screen.query_one("#minutes", Input).value == "73"
    run(app, steps)


@pytest.mark.parametrize("model", ["ollama:phi4-mini:3.8b", "ollama:ministral-3:3b"])
def test_explicit_nonthinking_model_choice_turns_thinking_off_without_changing_cloud_controls(
        tmp_path, monkeypatch, model):
    monkeypatch.setattr(local_models, "available_models", lambda: tuple(local_models.LOCAL_MODELS))
    app, _ = app_for(tmp_path, monkeypatch)
    app.settings.ai_mark_think = True

    async def steps(pilot):
        app.action_settings()
        await pilot.pause()
        screen = app.screen
        thinking = screen.query_one("#ai_mark_think", Switch)
        screen.query_one("#ai_mark_model", Select).value = model
        await pilot.pause()
        assert thinking.disabled and thinking.value is False
        screen.query_one("#ai_mark_model", Select).value = "ollama:qwen3.5:4b"
        await pilot.pause()
        assert not thinking.disabled
        thinking.value = True
        screen.query_one("#ai_mark_model", Select).value = "opus"
        await pilot.pause()
        assert not thinking.disabled and thinking.value is True
    run(app, steps)


def test_unrelated_save_does_not_rewrite_saved_unsupported_thinking(tmp_path, monkeypatch):
    monkeypatch.setattr(local_models, "available_models", lambda: tuple(local_models.LOCAL_MODELS))
    app, vault = app_for(tmp_path, monkeypatch)
    app.settings.ai_mark_model, app.settings.ai_mark_think = "ollama:phi4-mini:3.8b", True

    async def steps(pilot):
        app.action_settings()
        await pilot.pause()
        thinking = app.screen.query_one("#ai_mark_think", Switch)
        assert not thinking.disabled and thinking.value is True
        app.screen.query_one("#usage_display", Select).value = "both"
        app.screen.query_one("#save", Button).press()
        await pilot.pause()
        saved = config.Settings.load(vault)
        assert saved.ai_for("mark") == ("ollama:phi4-mini:3.8b", True)
        assert saved.usage_display == "both"
    run(app, steps)


@pytest.mark.parametrize("model", ["ollama:phi4-mini:3.8b", "ollama:ministral-3:3b"])
def test_saved_unsupported_thinking_can_be_turned_off_then_stays_disabled(tmp_path, monkeypatch, model):
    monkeypatch.setattr(local_models, "available_models", lambda: tuple(local_models.LOCAL_MODELS))
    app, vault = app_for(tmp_path, monkeypatch)
    app.settings.ai_mark_model, app.settings.ai_mark_think = model, True

    async def steps(pilot):
        app.action_settings()
        await pilot.pause()
        screen = app.screen
        thinking = screen.query_one("#ai_mark_think", Switch)
        assert not thinking.disabled and thinking.value is True
        thinking.focus()
        thinking.scroll_visible(animate=False)
        await pilot.pause()
        await pilot.press("space")
        await pilot.pause()
        assert thinking.value is False and thinking.disabled
        assert task_choices(screen)["ask"] == ("haiku", False)
        assert task_choices(screen)["explain"] == ("haiku", False)
        screen.query_one("#save", Button).press()
        await pilot.pause()
        assert config.Settings.load(vault).ai_for("mark") == (model, False)
    run(app, steps)


def test_presets_leave_global_vision_helper_unchanged_on_apply_and_save(tmp_path, monkeypatch):
    presets = presets_module()
    preset = presets.Preset("Local: fixture", "Native vision for this fixture.", "local",
                            ("ollama:gemma4:e2b", False), ("ollama:gemma4:e2b", False),
                            ("ollama:gemma4:e2b", False))
    monkeypatch.setitem(presets.PRESETS, "test_vision", preset)
    monkeypatch.setattr(local_models, "available_models", lambda: ("ollama:gemma4:e2b",))
    app, vault = app_for(tmp_path, monkeypatch)
    app.settings.local_vision_model = "ollama:qwen3.5:9b"

    async def steps(pilot):
        app.action_settings()
        await pilot.pause()
        screen = app.screen
        screen.query_one("#ai_preset", Select).value = "test_vision"
        await pilot.pause()
        screen.query_one("#apply-preset", Button).press()
        await pilot.pause()
        assert app.settings.local_vision_model == "ollama:qwen3.5:9b"
        assert task_choices(screen)["ask"] == ("ollama:gemma4:e2b", False)
        screen.query_one("#save", Button).press()
        await pilot.pause()
        saved = config.Settings.load(vault)
        assert saved.local_vision_model == "ollama:qwen3.5:9b"
        assert saved.ai_for("ask") == ("ollama:gemma4:e2b", False)
    run(app, steps)


@pytest.mark.parametrize("model", ["ollama:lfm2.5:8b", "ollama:deepseek-r1:8b", "ollama:deepseek-r1:14b"])
def test_reasoning_model_selection_shows_locked_on_without_locking_other_models(tmp_path, monkeypatch, model):
    monkeypatch.setattr(local_models, "available_models", lambda: tuple(local_models.LOCAL_MODELS))
    app, _ = app_for(tmp_path, monkeypatch)

    async def steps(pilot):
        app.action_settings()
        await pilot.pause()
        screen = app.screen
        thinking = screen.query_one("#ai_ask_think", Switch)
        screen.query_one("#ai_ask_model", Select).value = model
        await pilot.pause()
        assert thinking.value is True and thinking.disabled
        assert "always" in str(thinking.tooltip).lower()
        screen.query_one("#ai_ask_model", Select).value = "haiku"
        await pilot.pause()
        assert not thinking.disabled
        thinking.value = False
        assert task_choices(screen)["ask"] == ("haiku", False)
        assert task_choices(screen)["mark"] == ("haiku", False)
    run(app, steps)
