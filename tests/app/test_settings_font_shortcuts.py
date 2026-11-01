"""Global text-size shortcuts and pending Settings edits must keep distinct intent."""
import asyncio
import os
from pathlib import Path

import pytest
from textual.widgets import Button, Input

from test_terminal_font import FakeTab
from test_tui import app_for
from tutor_app import config, look, mac


@pytest.fixture(autouse=True)
def restore_palette():
    yield
    look.use("classic")


def font_app(tmp_path, monkeypatch, theme, start=13):
    app, vault = app_for(tmp_path, monkeypatch)
    tab = FakeTab(13)
    monkeypatch.setattr(mac, "terminal_font_size", tab.font_size)
    app.tty = "/dev/fake-tutor-tab"
    app.settings.theme = theme
    app.settings.font_size = 0 if start == 13 else start
    look.use(theme)
    app.settle_font_size()
    return app, vault, tab


async def replace(pilot, field, text):
    field.focus()
    await pilot.press("home", "shift+end", *text)
    assert field.value == text


async def save(pilot, app):
    app.screen.query_one("#save", Button).focus()
    await pilot.press("enter")
    await pilot.pause()
    await app.workers.wait_for_complete()
    assert type(app.screen).__name__ == "HomeScreen"


def capture(app, name):
    if directory := os.environ.get("B234_SHOTS"):
        Path(directory).mkdir(parents=True, exist_ok=True)
        app.save_screenshot(name + ".svg", path=directory)


@pytest.mark.parametrize("theme", ["classic", "day"])
@pytest.mark.parametrize("key,start,wanted", [("alt+equals_sign", 13, 14), ("alt+minus", 13, 12),
                                              ("alt+0", 16, 13)])
def test_settings_save_keeps_immediate_global_font_choice(tmp_path, monkeypatch, theme, key, start, wanted):
    app, vault, tab = font_app(tmp_path, monkeypatch, theme, start)

    async def go():
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            await pilot.press("f2")
            await pilot.pause()
            screen = app.screen
            field = screen.query_one("#font_size", Input)
            assert field.value == str(start)
            minutes = screen.query_one("#minutes", Input)
            await replace(pilot, minutes, "17")
            selection = minutes.selection
            await pilot.press(key)
            await app.workers.wait_for_complete()
            await pilot.pause()
            assert tab.size == app.text_size() == wanted
            saved_size = 0 if wanted == 13 else wanted
            assert config.Settings.load(vault).font_size == saved_size
            capture(app, f"{theme}-{key.replace('+', '-')}-changed")
            assert field.value == str(wanted)
            assert app.focused is minutes and minutes.selection == selection and minutes.value == "17"
            if key == "alt+equals_sign":
                await pilot.press("alt+equals_sign", "alt+minus")
                await app.workers.wait_for_complete()
                await pilot.pause()
                assert field.value == str(wanted) and tab.size == wanted
            await save(pilot, app)
            capture(app, f"{theme}-{key.replace('+', '-')}-saved")
            assert tab.size == app.text_size() == wanted
            settings = config.Settings.load(vault)
            assert settings.font_size == saved_size and settings.minutes == 17
            await app.ai.close()

    asyncio.run(go())


@pytest.mark.parametrize("theme", ["classic", "day"])
@pytest.mark.parametrize("timing", ["before", "after", "roundtrip-before", "roundtrip-after"])
def test_explicit_pending_font_edit_wins_even_back_at_the_opening_value(tmp_path, monkeypatch, theme, timing):
    app, vault, tab = font_app(tmp_path, monkeypatch, theme)

    async def go():
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            await pilot.press("f2")
            await pilot.pause()
            field = app.screen.query_one("#font_size", Input)

            async def edit():
                await replace(pilot, field, "16")
                if timing.startswith("roundtrip"):
                    await replace(pilot, field, "13")

            if timing.endswith("before"):
                await edit()
            await pilot.press("alt+equals_sign")
            await app.workers.wait_for_complete()
            if timing.endswith("after"):
                await edit()
            expected = 13 if timing.startswith("roundtrip") else 16
            assert field.value == str(expected) and tab.size == 14
            assert config.Settings.load(vault).font_size == 14
            await save(pilot, app)
            assert tab.size == app.text_size() == expected
            assert config.Settings.load(vault).font_size == (0 if expected == 13 else expected)
            await app.ai.close()

    asyncio.run(go())


@pytest.mark.parametrize("theme", ["classic", "day"])
def test_escape_keeps_global_size_but_discards_unsaved_form_edits(tmp_path, monkeypatch, theme):
    app, vault, tab = font_app(tmp_path, monkeypatch, theme)

    async def go():
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            minutes = app.settings.minutes
            await pilot.press("f2")
            await pilot.pause()
            await replace(pilot, app.screen.query_one("#font_size", Input), "16")
            await replace(pilot, app.screen.query_one("#minutes", Input), "17")
            await pilot.press("alt+equals_sign")
            await app.workers.wait_for_complete()
            await pilot.press("escape")
            await pilot.pause()
            assert type(app.screen).__name__ == "HomeScreen" and tab.size == app.text_size() == 14
            settings = config.Settings.load(vault)
            assert settings.font_size == 14 and settings.minutes == minutes
            await pilot.press("f2")
            await pilot.pause()
            assert app.screen.query_one("#font_size", Input).value == "14"
            assert app.screen.query_one("#minutes", Input).value == str(minutes)
            await app.ai.close()

    asyncio.run(go())
