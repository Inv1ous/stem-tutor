"""The look: Night, Day and Classic themes, one palette each, Classic exactly the app as it was before themes."""
import asyncio
import json

import pytest
from textual.theme import BUILTIN_THEMES

from test_tui import app_for
from tutor_app import cards, config, look


@pytest.fixture
def palette():
    yield look.use
    look.use("classic")  # the live palette is shared: leave it as every other test expects


def _luminance(hex_colour: str) -> float:
    def channel(c: float) -> float:
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (channel(int(hex_colour[i:i + 2], 16) / 255) for i in (1, 3, 5))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: str, b: str) -> float:
    hi, lo = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def test_classic_keeps_every_colour_the_app_had():
    assert look.PALETTES["classic"] | {} == {
        "background": "#181825", "surface": "#313244", "panel": "#45475a", "border": "#585b70", "frame": None,
        "text": "#cdd6f4", "muted": "#9399b2", "dim": "#6c7086", "soft": "#f9e2af", "ok": "#a6e3a1",
        "tutor": "#89b4fa", "question": "#cba6f7", "you": "#9399b2", "good": "#a6e3a1", "bad": "#f38ba8",
        "hint": "#f9e2af", "ai": "#f5c2e7", "plan": "#94e2d5", "banner": "#ffd500", "badge_fg": "#1e1e2e",
        "badge_bg": "#ffd500"}
    classic = next(t for t in look.textual_themes() if t.name == "tutor-classic")
    made = BUILTIN_THEMES["catppuccin-mocha"].to_color_system().generate()
    assert classic.to_color_system().generate() == made  # the same theme underneath
    assert classic.variables["menu-border"] == made["accent"] == classic.variables["panel-rule"]
    assert classic.variables["modal-border"] == made["accent"]
    assert classic.variables["stats-border"] == made["primary-darken-2"]


@pytest.mark.parametrize("name", ["night", "day"])
def test_night_and_day_are_easy_to_read(name):
    p = look.PALETTES[name]
    bg = p["background"]
    assert contrast(p["text"], bg) >= 7 and contrast(p["muted"], bg) >= 7
    for role in ("tutor", "question", "good", "bad", "hint", "ai", "plan", "ok", "banner"):
        assert contrast(p[role], bg) >= 4.5, role
    assert contrast(p["dim"], bg) >= 3  # only for what is finished or not started
    assert contrast(p["badge_fg"], p["badge_bg"]) >= 4.5
    for under in ("surface", "panel", "cursor", "selection"):
        assert contrast(p["text"], p[under]) >= 7, under
    assert 1.3 <= contrast(p["frame"], bg) <= 2.2  # a frame you see but don't read


def test_the_theme_setting_is_one_of_the_three_or_classic(tmp_path):
    vault = tmp_path / "v"
    (vault / ".tutor").mkdir(parents=True)
    f = vault / ".tutor" / "app_settings.json"
    for stored, loaded in (("night", "night"), ("day", "day"), ("neon", "classic"), (3, "classic"), (None, "classic")):
        f.write_text(json.dumps({} if stored is None else {"theme": stored}))
        assert config.Settings.load(vault).theme == loaded


def test_classic_cards_are_framed_in_their_colour_and_night_cards_in_grey(palette):
    palette("classic")
    c = cards.card("tutor", "Title", "body")
    assert c.border_style == "#89b4fa"
    palette("night")
    c = cards.card("tutor", "Title", "body")
    assert c.border_style == look.PALETTES["night"]["frame"] and c.title.style == look.PALETTES["night"]["tutor"]
    assert cards.feedback({"n": 1, "correct": True, "answer": "1"}, "1").title.style == look.PALETTES["night"]["good"]


@pytest.mark.parametrize("name", ["night", "day", "classic"])
def test_the_app_starts_in_the_chosen_theme(tmp_path, monkeypatch, name):
    app, v = app_for(tmp_path, monkeypatch)
    app.settings.theme = name
    look.use(name)

    async def go():
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            assert app.theme == f"tutor-{name}"
            assert app.screen.styles.background.hex.lower() == look.PALETTES[name]["background"]
            assert str(app.screen.query_one("#banner").render()).strip().startswith("___")
            await app.ai.close()
    try:
        asyncio.run(go())
    finally:
        look.use("classic")
