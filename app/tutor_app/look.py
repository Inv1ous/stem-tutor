"""How the tutor looks: three themes (Night, Day, Classic), each a palette of roles, and the Terminal profile it uses.

Every colour on screen comes from a role here, so a theme changes in one place, and Classic keeps exactly the
colours the app had before themes existed (Catppuccin Mocha plus its own yellow)."""
from __future__ import annotations

import dataclasses

from . import mac
from .config import THEMES

THEME = {name: f"tutor-{name}" for name in THEMES}  # the Textual theme each one registers as
TERMINAL_PROFILES = {"night": "STEM Tutor Night", "day": "STEM Tutor Day", "classic": "Study"}
LABELS = {"night": "Night", "day": "Day (light)", "classic": "Classic (as before)"}

PALETTES = {
    "classic": {
        "background": "#181825", "surface": "#313244", "panel": "#45475a", "border": "#585b70", "frame": None,
        "text": "#cdd6f4", "muted": "#9399b2", "dim": "#6c7086", "soft": "#f9e2af", "ok": "#a6e3a1",
        "tutor": "#89b4fa", "question": "#cba6f7", "you": "#9399b2", "good": "#a6e3a1", "bad": "#f38ba8",
        "hint": "#f9e2af", "ai": "#f5c2e7", "plan": "#94e2d5", "banner": "#ffd500", "badge_fg": "#1e1e2e",
        "badge_bg": "#ffd500",
    },
    "night": {  # one blue accent; green and red only for right and wrong; quiet grey frames
        "background": "#16181c", "surface": "#1c1f24", "panel": "#23262c", "border": "#3b4048", "frame": "#3b4048",
        "text": "#e4e6ea", "muted": "#a6abb4", "dim": "#7b818b", "soft": "#a6abb4", "ok": "#73a7f5",
        "tutor": "#73a7f5", "question": "#bd8ff2", "you": "#a6abb4", "good": "#7cc48a", "bad": "#ef8088",
        "hint": "#e6bd6c", "ai": "#e99acb", "plan": "#73a7f5", "banner": "#73a7f5", "badge_fg": "#16181c",
        "badge_bg": "#73a7f5", "cursor": "#283447", "selection": "#2c3a50",
    },
    "day": {  # warm paper, the same roles in darker inks
        "background": "#f8f5ee", "surface": "#f0ece3", "panel": "#e7e2d7", "border": "#c9c2b4", "frame": "#c9c2b4",
        "text": "#1d2025", "muted": "#4a4f58", "dim": "#6d727b", "soft": "#4a4f58", "ok": "#1f5bb5",
        "tutor": "#1f5bb5", "question": "#6f2fb0", "you": "#4a4f58", "good": "#23703a", "bad": "#b2242f",
        "hint": "#875600", "ai": "#9e2f6d", "plan": "#1f5bb5", "banner": "#1f5bb5", "badge_fg": "#ffffff",
        "badge_bg": "#1f5bb5", "cursor": "#dbe4f2", "selection": "#c9d6ea",
    },
}

C: dict = dict(PALETTES["classic"])  # the live palette: one dict, updated in place, so every importer sees a change

# CSS variables of our own (app.py); a theme sets them, these are only the fallback for the first parse
CSS_DEFAULTS = {"menu-border": "#585b70", "stats-border": "#585b70", "panel-rule": "#585b70", "modal-border": "#585b70",
                "menu-background": "#313244", "menu-tint": "#cdd6f4 5%"}

BANNER = r"""  ___ _____ ___ __  __   _____      _
 / __|_   _| __|  \/  | |_   _|  _| |_ ___ _ _
 \__ \ | | | _|| |\/| |   | || || |  _/ _ \ '_|
 |___/ |_| |___|_|  |_|   |_| \_,_|\__\___/_|"""


def textual_themes() -> list:
    from textual.theme import BUILTIN_THEMES, Theme  # here, so `tutor doctor` runs even when textual is missing
    base = BUILTIN_THEMES["catppuccin-mocha"]
    made = base.to_color_system().generate()
    classic = dataclasses.replace(base, name=THEME["classic"], variables={
        **base.variables, "menu-border": made["accent"], "stats-border": made["primary-darken-2"],
        "panel-rule": made["accent"], "modal-border": made["accent"], "menu-background": made["surface"],
        "menu-tint": f"{made['foreground']} 5%"})  # what OptionList draws by default
    themes = [classic]
    for name in ("night", "day"):
        p = PALETTES[name]
        themes.append(Theme(
            name=THEME[name], primary=p["tutor"], secondary=p["muted"], accent=p["tutor"], warning=p["hint"],
            error=p["bad"], success=p["tutor"], foreground=p["text"], background=p["background"],
            surface=p["surface"], panel=p["panel"], dark=name == "night",
            variables={
                "menu-border": p["border"], "stats-border": p["border"], "panel-rule": p["border"],
                "modal-border": p["border"], "border": p["tutor"], "border-blurred": p["border"],
                "menu-background": p["background"], "menu-tint": f"{p['text']} 0%",  # flat, like the box beside it
                "text-muted": p["muted"], "text-disabled": p["dim"],
                "block-cursor-background": p["cursor"], "block-cursor-foreground": p["text"],
                "block-cursor-text-style": "bold", "block-cursor-blurred-background": p["panel"],
                "block-cursor-blurred-foreground": p["text"], "block-cursor-blurred-text-style": "none",
                "block-hover-background": p["panel"],
                "footer-background": p["panel"], "footer-key-foreground": p["tutor"],
                "footer-description-foreground": p["muted"],
                "input-cursor-background": p["tutor"], "input-cursor-foreground": p["background"],
                "input-selection-background": p["selection"], "screen-selection-background": p["selection"],
                "button-color-foreground": p["badge_fg"],
                "scrollbar": p["border"], "scrollbar-hover": p["muted"], "scrollbar-active": p["tutor"],
                "scrollbar-background": p["background"], "scrollbar-background-hover": p["background"],
                "scrollbar-background-active": p["background"], "scrollbar-corner-color": p["background"],
                "link-color": p["tutor"], "markdown-h1-color": p["tutor"], "markdown-h1-background": p["background"],
                "markdown-h2-color": p["text"], "markdown-h3-color": p["text"],
            }))
    return themes


def use(name: str) -> None:
    """Make `name` the live palette (cards and screens read `C` when they draw)."""
    C.clear()
    C.update(PALETTES[name if name in PALETTES else "classic"])


def apply(app, name: str) -> None:
    """Switch the running app to another look, and its macOS Terminal tab to the look's profile (in the background)."""
    use(name)
    app.theme = THEME[name]
    if app.tty:
        def switch() -> None:
            status, was = mac.switch_terminal_profile(app.tty, TERMINAL_PROFILES[name])
            if status == "ok" and app.tty_profile is None:
                app.tty_profile = was
            if status == "missing" and name != "classic":
                app.call_from_thread(app.notify, mac.LOOK_HELP, timeout=15)
        app.run_worker(switch, thread=True, group="terminal-profile", exclusive=True)


def banner() -> str:
    return f"[b {C['banner']}]{BANNER}[/]"
