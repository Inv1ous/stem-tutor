"""STEM Tutor — the terminal app."""
from __future__ import annotations

import contextlib
import random
from pathlib import Path

from textual.app import App
from textual.binding import Binding

from tutorlib import store
from tutorlib.session import Tutor

from . import config, mac
from .ai import Claude

CSS = """
Screen { background: $background; }
#banner { height: 6; content-align: center middle; padding: 1 0 0 0; }
#home { height: 1fr; padding: 1 2; }
#menu { width: 52; height: auto; max-height: 100%; border: round $accent; padding: 0 1; }
#stats { width: 1fr; height: auto; padding: 1 2; border: round $primary-darken-2; margin-left: 2; }
#bar { height: 1; background: $panel; }
#map { height: auto; max-height: 2; }
#log { height: 1fr; padding: 0 1; scrollbar-size-vertical: 1; }
.entry { margin: 0 0 1 0; }
#panel { height: auto; max-height: 55%; }
.panel { height: auto; padding: 0 1 1 1; border-top: solid $accent; }
.panel.tall { max-height: 30; }
.panel.short { padding: 0 1; }
.hint { color: $text-muted; padding: 0 0 0 1; }
.buttons { height: auto; }
.buttons Button { margin: 0 1 0 0; }
OptionList { height: auto; max-height: 12; border: none; }
#note { margin-top: 1; }
SelectionList { height: auto; max-height: 14; }
TextArea { height: 12; }
#picker, #ask, #summary, #help, #settings { width: 90; max-width: 95%; height: auto; max-height: 90%;
  border: round $accent; background: $surface; padding: 1 2; }
PickerScreen, AskScreen, SummaryScreen, HelpScreen, SettingsScreen { align: center middle; }
#settings .row { height: auto; margin: 0 0 1 0; }
#settings .title { text-style: bold; color: $accent; margin-bottom: 1; }
"""


class TutorApp(App):
    TITLE = "STEM Tutor"
    CSS = CSS
    BINDINGS = [Binding("ctrl+c", "quit", "Quit", show=False)]

    def __init__(self, vault: Path | None = None, claude_binary: str | None = None, open_obsidian: bool | None = None,
                 seed: int | None = None):
        super().__init__()
        self.vault = Path(vault or config.vault_path())
        self.settings = config.Settings.load(self.vault)
        if open_obsidian is not None:
            self.settings.open_obsidian = open_obsidian
        self.claude_binary = claude_binary
        self.seed = seed
        self._locks = contextlib.ExitStack()

    def on_mount(self) -> None:
        self.theme = "catppuccin-mocha"
        if not (self.vault / ".tutor" / "config.json").exists():
            self.exit(message=f"No tutor folder at {self.vault}. Run: tutor doctor")
            return
        v = store.Vault(self.vault)
        try:
            self._locks.enter_context(v.lock(wait_seconds=1))
        except store.Locked:
            self.exit(message="Another STEM Tutor window is already open. Use that one (or close it first).")
            return
        self.tutor = Tutor(v, rng=random.Random(self.seed) if self.seed is not None else None)
        self.ai = Claude(self.vault, model=self.settings.model, binary=self.claude_binary,
                         usage_file=self.vault / ".tutor" / "ai_usage.json", daily_cap=self.settings.daily_cap)
        imported = mac.import_ipad_inbox(self.vault, config.ICLOUD_INBOX)
        if imported:
            self.notify(f"Imported from your iPad inbox: {', '.join(imported)}")
        from .screens import HomeScreen
        self.push_screen(HomeScreen())

    async def on_unmount(self) -> None:
        if hasattr(self, "ai"):
            await self.ai.close()
        self._locks.close()

    def action_help(self) -> None:
        from .screens import HelpScreen
        self.push_screen(HelpScreen())

    def action_settings(self) -> None:
        from .screens import SettingsScreen
        self.push_screen(SettingsScreen())
