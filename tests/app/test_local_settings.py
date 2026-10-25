"""Local model settings follow SSD availability without restarting the tutor."""
import asyncio
import json
from types import SimpleNamespace

import pytest
from textual.widgets import Button, Input, Select

from test_tui import app_for
from tutor_app import config, local_models, screens
from tutor_app.codex_models import CODEX_MODELS


LOCAL_MODELS = {
    "ollama:qwen3.5:9b": "Qwen 3.5 9B",
    "ollama:gemma4:26b-a4b-it-qat": "Gemma 4 26B",
    "ollama:qwen3.8:27b": "Qwen 3.8 27B",
}


def run(app, steps):
    async def go():
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            await steps(pilot)
            await app.ai.close()
    asyncio.run(go())


async def wait_for(pilot, condition):
    for _ in range(40):
        await pilot.pause(0.1)
        if condition():
            return
    assert condition(), "Settings did not detect the model availability change."


def test_settings_preserve_known_local_models_when_the_ssd_is_disconnected(tmp_path):
    folder = tmp_path / ".tutor"
    folder.mkdir()
    (folder / "app_settings.json").write_text(json.dumps({
        "model": "ollama:qwen3.5:9b", "ai_mark_model": "ollama:gemma4:26b-a4b-it-qat",
        "ai_ask_model": "ollama:qwen3.8:27b", "ai_explain_model": "unknown-local-model",
    }))
    settings = config.Settings.load(tmp_path)
    assert settings.model == "ollama:qwen3.5:9b"
    assert settings.ai_for("mark")[0] == "ollama:gemma4:26b-a4b-it-qat"
    assert settings.ai_for("ask")[0] == "ollama:qwen3.8:27b"
    assert settings.ai_explain_model == ""


@pytest.mark.parametrize("saved,want", [("weekly", "weekly"), ("ram", "ram"), ("both", "both"),
                                        ("unknown", "weekly"), (True, "weekly")])
def test_usage_display_loads_only_supported_choices(tmp_path, saved, want):
    folder = tmp_path / ".tutor"
    folder.mkdir()
    (folder / "app_settings.json").write_text(json.dumps({"usage_display": saved}))
    assert config.Settings.load(tmp_path).usage_display == want


def test_open_settings_detect_ssd_insertion_and_removal_and_preserve_unsaved_cloud_choice(tmp_path, monkeypatch):
    present = []
    monkeypatch.setattr(screens, "local_models", SimpleNamespace(
        LOCAL_MODELS=LOCAL_MODELS, is_local=local_models.is_local, supports_thinking=local_models.supports_thinking, always_thinks=local_models.always_thinks,
        available_models=lambda: tuple(present)), raising=False)
    app, vault = app_for(tmp_path, monkeypatch)

    async def steps(pilot):
        app.action_settings()
        await pilot.pause()
        screen = app.screen
        ask = screen.query_one("#ai_ask_model", Select)
        explain = screen.query_one("#ai_explain_model", Select)
        assert [value for _, value in ask._options if value is not Select.NULL] == ["haiku", "sonnet", "opus", *CODEX_MODELS]
        ask.value = "sonnet"
        present[:] = LOCAL_MODELS
        await wait_for(pilot, lambda: "ollama:qwen3.5:9b" in [value for _, value in ask._options])
        assert [value for _, value in ask._options if value is not Select.NULL] == ["haiku", "sonnet", "opus", *LOCAL_MODELS, *CODEX_MODELS]
        assert ask.value == "sonnet"
        explain.value = "ollama:qwen3.5:9b"
        ask.focus()
        ask.action_show_overlay()
        await pilot.pause(1.15)
        assert ask.expanded and explain.value == "ollama:qwen3.5:9b"
        ask.expanded = False
        present.clear()
        await wait_for(pilot, lambda: "ollama:qwen3.5:9b" not in [value for _, value in explain._options])
        assert [value for _, value in explain._options if value is not Select.NULL] == ["haiku", "sonnet", "opus", *CODEX_MODELS]
        assert explain.value is Select.NULL and ask.value == "sonnet"
        assert "reconnect" in explain.prompt.lower()
        screen.query_one("#usage_display", Select).value = "ram"
        screen.query_one("#save", Button).press()
        await pilot.pause()
        saved = config.Settings.load(vault)
        assert saved.ai_for("ask")[0] == "sonnet" and saved.ai_for("explain")[0] == "ollama:qwen3.5:9b"
        assert saved.usage_display == "ram"
    run(app, steps)


def test_disconnected_saved_local_model_shows_unavailable_without_changing_settings_on_cancel(tmp_path, monkeypatch):
    monkeypatch.setattr(screens, "local_models", SimpleNamespace(
        LOCAL_MODELS=LOCAL_MODELS, is_local=local_models.is_local, supports_thinking=local_models.supports_thinking, always_thinks=local_models.always_thinks, available_models=lambda: ()), raising=False)
    app, _ = app_for(tmp_path, monkeypatch)

    async def steps(pilot):
        app.settings.ai_ask_model = "ollama:qwen3.8:27b"
        app.action_settings()
        await pilot.pause()
        selected = app.screen.query_one("#ai_ask_model", Select)
        assert selected.value is Select.NULL and "reconnect" in selected.prompt.lower()
        assert not any(value in LOCAL_MODELS for _, value in selected._options)
        assert app.settings.ai_ask_model == "ollama:qwen3.8:27b"
        await pilot.press("escape")
        assert app.settings.ai_ask_model == "ollama:qwen3.8:27b"
    run(app, steps)


def test_unrelated_settings_save_keeps_all_disconnected_local_preferences(tmp_path, monkeypatch):
    monkeypatch.setattr(screens, "local_models", SimpleNamespace(
        LOCAL_MODELS=LOCAL_MODELS, is_local=local_models.is_local, supports_thinking=local_models.supports_thinking, always_thinks=local_models.always_thinks, available_models=lambda: ()), raising=False)
    app, vault = app_for(tmp_path, monkeypatch)

    async def steps(pilot):
        app.settings.model = "ollama:qwen3.5:9b"  # Explaining inherits the general choice.
        app.settings.ai_mark_model = "ollama:gemma4:26b-a4b-it-qat"
        app.settings.ai_ask_model = "ollama:qwen3.8:27b"
        app.action_settings()
        await pilot.pause()
        app.screen.query_one("#usage_display", Select).value = "both"
        app.screen.query_one("#save", Button).press()
        await pilot.pause()
        saved = config.Settings.load(vault)
        assert saved.usage_display == "both"
        assert saved.model == "ollama:qwen3.5:9b"
        assert saved.ai_for("explain")[0] == "ollama:qwen3.5:9b"
        assert saved.ai_for("mark")[0] == "ollama:gemma4:26b-a4b-it-qat"
        assert saved.ai_for("ask")[0] == "ollama:qwen3.8:27b"
    run(app, steps)


def test_reconnect_restores_local_selection_unless_cloud_was_explicitly_selected(tmp_path, monkeypatch):
    present = list(LOCAL_MODELS)
    monkeypatch.setattr(screens, "local_models", SimpleNamespace(
        LOCAL_MODELS=LOCAL_MODELS, is_local=local_models.is_local, supports_thinking=local_models.supports_thinking, always_thinks=local_models.always_thinks,
        available_models=lambda: tuple(present)), raising=False)
    app, vault = app_for(tmp_path, monkeypatch)

    async def steps(pilot):
        app.settings.ai_ask_model = "ollama:qwen3.8:27b"
        app.action_settings()
        await pilot.pause()
        ask = app.screen.query_one("#ai_ask_model", Select)
        present.clear()
        await wait_for(pilot, lambda: ask.value is Select.NULL)
        assert ask.value is Select.NULL
        present[:] = LOCAL_MODELS
        await wait_for(pilot, lambda: ask.value == "ollama:qwen3.8:27b")
        assert ask.value == "ollama:qwen3.8:27b"
        present.clear()
        await wait_for(pilot, lambda: ask.value is Select.NULL)
        ask.value = "opus"  # Explicitly replacing the unavailable local choice must stick.
        present[:] = LOCAL_MODELS
        await wait_for(pilot, lambda: "ollama:qwen3.8:27b" in [value for _, value in ask._options])
        assert ask.value == "opus"
        app.screen.query_one("#save", Button).press()
        await pilot.pause()
        assert config.Settings.load(vault).ai_for("ask")[0] == "opus"
    run(app, steps)


@pytest.mark.parametrize("choice", ["weekly", "ram", "both"])
def test_usage_display_choice_saves_from_settings(tmp_path, monkeypatch, choice):
    app, vault = app_for(tmp_path, monkeypatch)

    async def steps(pilot):
        app.action_settings()
        await pilot.pause()
        app.screen.query_one("#usage_display", Select).value = choice
        app.screen.query_one("#save", Button).press()
        await pilot.pause()
        assert config.Settings.load(vault).usage_display == choice
    run(app, steps)


def test_saving_unchanged_minutes_is_quiet_and_changed_minutes_report_once(tmp_path, monkeypatch):
    app, _ = app_for(tmp_path, monkeypatch)
    said = []

    async def steps(pilot):
        monkeypatch.setattr(app, "notify", lambda message, **kw: said.append(message))
        for typed in ("40", "040", "55", "55"):
            app.action_settings()
            await pilot.pause()
            app.screen.query_one("#minutes", Input).value = typed
            app.screen.query_one("#save", Button).press()
            await pilot.pause()
        updates = [message for message in said if "Session length" in message]
        assert updates == ["Session length set to 55 minutes."]
    run(app, steps)
