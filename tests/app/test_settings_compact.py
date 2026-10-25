"""Settings keeps controls in view and shows model detail only when it is useful."""
import asyncio

import pytest
from rich.cells import cell_len
from textual.widgets import Button, Collapsible, Select, Static, Switch

from test_tui import app_for
from tutor_app import config, local_models, look


@pytest.fixture(autouse=True)
def isolated_models(monkeypatch):
    from tutor_app.ai import Result
    from tutor_app.local_ai import LocalAI

    async def warm(self, model, timeout=120):
        return Result()
    monkeypatch.setattr(LocalAI, "warm", warm)
    monkeypatch.setattr(local_models, "available_models", lambda: tuple(local_models.LOCAL_MODELS))
    yield
    look.use("classic")


def run(app, steps, size=(140, 46)):
    async def go():
        async with app.run_test(size=size) as pilot:
            await pilot.pause()
            app.action_settings()
            await pilot.pause()
            await steps(pilot)
            await app.ai.close()
    asyncio.run(go())


def assert_save_visible(screen):
    save = screen.query_one("#save", Button)
    assert screen.query_one("#settings").region.contains_region(save.region)
    for y in range(save.region.y, save.region.bottom):
        assert screen.get_widget_at(save.region.x + 2, y)[0] is save


@pytest.mark.parametrize("theme", ["night", "day", "classic"])
@pytest.mark.parametrize("size", [(80, 24), (100, 30), (140, 46)])
def test_settings_uses_available_width_without_cutting_off_controls(tmp_path, monkeypatch, theme, size):
    app, _ = app_for(tmp_path, monkeypatch)
    app.settings.theme = theme
    app.settings.ai_mark_model = "ollama:gemma4:26b-a4b-it-qat"
    look.use(theme)

    async def steps(pilot):
        screen = app.screen
        box = screen.query_one("#settings")
        assert box.region.width <= size[0] * 0.95
        if size[0] >= 100:
            assert box.region.width > 90  # ordinary model labels should have room on a wider terminal
        assert_save_visible(screen)
        for mode in config.AI_MODES:
            select = screen.query_one(f"#ai_{mode}_model", Select)
            assert select.parent.content_region.contains_region(select.region)
            label = select.parent.query_one(Static)
            assert label.region.right <= select.region.x  # a wrapped task label cannot run into its model
        mark = screen.query_one("#ai_mark_model", Select)
        assert mark.content_region.width >= cell_len("Model: Gemma 4 26B (local)") + 3
        await pilot.resize_terminal(80, 24)
        await pilot.pause()
        assert_save_visible(screen)
    run(app, steps, size)


@pytest.mark.parametrize("custom", [False, True])
def test_current_setup_has_no_repeated_preview_and_the_guide_starts_closed(tmp_path, monkeypatch, custom):
    app, _ = app_for(tmp_path, monkeypatch)
    if custom:
        app.settings.ai_ask_model = "opus"

    async def steps(pilot):
        screen = app.screen
        assert not screen.query_one("#preset-preview", Static).display
        assert len(screen.query("#model-guide")) == 1
        guide = screen.query_one("#model-guide", Collapsible)
        assert guide.collapsed and guide.region.height == 1
        assert screen.query_one("#preset-status", Static).region.height == 1
        assert_save_visible(screen)
    run(app, steps)


def test_model_guide_expands_and_collapses_by_keyboard_without_changing_choices(tmp_path, monkeypatch):
    app, _ = app_for(tmp_path, monkeypatch)

    async def steps(pilot):
        screen = app.screen
        assert len(screen.query("#model-guide")) == 1
        guide = screen.query_one("#model-guide", Collapsible)
        guide.query_one("CollapsibleTitle").focus()
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        assert not guide.collapsed and guide.region.height > 1
        assert "Haiku" in str(guide.query_one("Contents > Static", Static).content)
        assert_save_visible(screen)
        await pilot.press("enter")
        await pilot.pause()
        assert guide.collapsed and guide.region.height == 1
        assert not screen.query_one("#preset-preview", Static).display
        assert screen.query_one("#ai_ask_model", Select).value == "haiku"
    run(app, steps, (80, 24))


def test_pending_preset_shows_explicit_choices_then_apply_hides_repetition_and_cancel_keeps_settings(
        tmp_path, monkeypatch):
    app, vault = app_for(tmp_path, monkeypatch)

    async def steps(pilot):
        screen = app.screen
        preview = screen.query_one("#preset-preview", Static)
        assert not preview.display
        screen.query_one("#ai_preset", Select).value = "claude_balanced"
        await pilot.pause()
        assert preview.display
        content = str(preview.content)
        assert "Sonnet" in content and "Marking:" in content and "Explaining:" in content and "Ask the tutor:" in content
        assert "thinking off" in content
        assert app.settings.ai_for("ask") == ("haiku", False)
        screen.query_one("#apply-preset", Button).press()
        await pilot.pause()
        assert not preview.display
        assert screen.query_one("#ai_ask_model", Select).value == "sonnet"
        assert app.settings.ai_for("ask") == ("haiku", False)
        assert not (vault / ".tutor/app_settings.json").exists()
        await pilot.press("escape")
        assert app.settings.ai_for("ask") == config.Settings.load(vault).ai_for("ask") == ("haiku", False)
    run(app, steps)


def test_ssd_reconnect_notice_stays_visible_and_pending_preview_survives_hotplug(tmp_path, monkeypatch):
    present = list(local_models.LOCAL_MODELS)
    monkeypatch.setattr(local_models, "available_models", lambda: tuple(present))
    app, _ = app_for(tmp_path, monkeypatch)
    for mode in config.AI_MODES:
        setattr(app.settings, f"ai_{mode}_model", "ollama:gemma4:26b-tutor-mlx")

    async def steps(pilot):
        screen = app.screen
        preview = screen.query_one("#preset-preview", Static)
        assert not preview.display
        present.clear()
        screen._refresh_models()
        await pilot.pause()
        assert preview.display and "Reconnect LocalAI SSD" in str(preview.content)
        assert screen.query_one("#apply-preset", Button).disabled
        present[:] = local_models.LOCAL_MODELS
        screen._refresh_models()
        await pilot.pause()
        assert not preview.display
        screen.query_one("#ai_preset", Select).value = "local_deep"
        await pilot.pause()
        assert preview.display and "high reasoning" in str(preview.content)
        present.clear()
        screen._refresh_models()
        await pilot.pause()
        assert preview.display and "Reconnect LocalAI SSD" in str(preview.content)
        present[:] = local_models.LOCAL_MODELS
        screen._refresh_models()
        await pilot.pause()
        assert preview.display and "Reconnect" not in str(preview.content)
        assert screen.query_one("#ai_preset", Select).value == "local_deep"
        assert screen.query_one("#ai_ask_model", Select).value == "ollama:gemma4:26b-tutor-mlx"
        assert screen.query_one("#ai_ask_think", Switch).value is False
    run(app, steps)
