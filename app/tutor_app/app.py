"""STEM Tutor — the terminal app."""
from __future__ import annotations

import contextlib
import random
import threading
import time
from pathlib import Path

from textual import events
from textual.app import App
from textual.binding import Binding

from tutorlib import packs, store
from tutorlib.session import Tutor

from . import config, look, mac, tts
from .ai import Claude

CSS = """
Screen { background: $background; }
#banner { height: 6; content-align: center middle; padding: 1 0 0 0; }
Horizontal#home { height: 1fr; padding: 1 2; }
#menu { width: 52; height: auto; max-height: 100%; border: round $menu-border; padding: 0 1;
  background: $menu-background; }
#menu:focus { background-tint: $menu-tint; }
#stats { width: 1fr; height: auto; max-height: 100%; padding: 0 0 1 2; border: round $stats-border; margin-left: 2;
  scrollbar-size-vertical: 1; scrollbar-gutter: stable; scrollbar-background: $background; }
#stats-text { margin-right: 1; }
#bar { height: auto; max-height: 2; background: $panel; }
#map { height: auto; max-height: 2; }
#log { height: 1fr; padding: 0 0 0 1; scrollbar-size-vertical: 1; scrollbar-gutter: stable;
  scrollbar-background: $background; }
ChatScreen #log, BlurtScreen #log { padding-top: 1; }
.entry { margin: 0 1 1 0; }
#panel { height: auto; max-height: 55%; }
.panel { height: auto; padding: 0 2 1 1; border-top: solid $panel-rule; }
.panel.tall { max-height: 30; }
.panel.short.tight { padding: 0 2 0 1; }
.hint { color: $text-muted; padding: 0 0 0 1; }
.buttons { height: auto; }
.buttons Button { margin: 0 1 0 0; }
Button:focus { background-tint: $button-focus-tint; }
Button.-textual-compact { min-width: 0; }  /* as wide as its label: focused, no unstyled cells either side of it */
Button.-textual-compact:focus { text-style: $button-compact-focus-text-style; }
OptionList { height: auto; max-height: 12; border: none; }
#note { margin-top: 1; min-height: 1; max-height: 5; }
SelectionList { height: auto; max-height: 14; }
#full { padding: 0 0 0 5; }
TextArea { height: 1fr; min-height: 4; max-height: 12; }
Composer { height: auto; min-height: 3; max-height: 10; }
.check { color: $check-color; padding: 0 0 0 1; }
#picker, Vertical#ask, #summary, #help, #settings { width: 90; max-width: 95%; height: auto; max-height: 90%;
  border: round $modal-border; background: $modal-background; padding: 1 2; }
PickerScreen, AskScreen, SummaryScreen, HelpScreen, SettingsScreen, ConfirmScreen { align: center middle; }
#help { padding: 0 2; }
#summary { scrollbar-size-vertical: 1; }
#summary-hint { dock: bottom; }
#help MarkdownH1 { margin: 1 0 0 0; }
MarkdownH1 { content-align-horizontal: $markdown-h1-align; }
#settings .row { height: auto; margin: 0 0 1 0; }
#settings .row > Static { width: 1fr; }
#settings Switch { border: none; padding: 0 1; margin-right: 1; }
#settings Switch:focus { border: none; background: $accent 40%; }
#settings #minutes, #settings #tts_speed, #settings #tts_volume { width: 10; background: $panel; }
#settings #settings-hint { content-align: left middle; height: 100%; padding: 0 0 0 2; }
#settings .row > Button { margin: 0; }
#settings .title { text-style: bold; color: $accent; margin-bottom: 1; }
#settings .ai-row > Select { width: 34; }
#glance { display: none; height: 1; margin-top: 1; padding: 0 4; text-wrap: nowrap; text-overflow: ellipsis; }
#settings #save-row { dock: bottom; }
SettingsScreen.flat #settings Switch { padding: 0; margin-right: 3; background: transparent; }
SettingsScreen.flat #settings Switch > .switch--slider { color: $text-muted; background: $panel; }
SettingsScreen.flat #settings Switch.-on > .switch--slider { color: $success; }
SettingsScreen.flat #settings Switch:focus { background: transparent; }
SettingsScreen.flat #settings Switch:focus > .switch--slider { background: $block-cursor-background; }
SettingsScreen.flat #settings .row:focus-within > Static { color: $accent; }
SettingsScreen.flat #settings #minutes, SettingsScreen.flat #settings #tts_speed, SettingsScreen.flat #settings #tts_volume { background: $panel; }
SettingsScreen.short #settings .row { margin: 0; }
SettingsScreen.short #settings #save { margin-top: 1; }
HomeScreen.narrow #stats { display: none; }
HomeScreen.narrow #glance { display: block; }
HomeScreen.narrow #menu { width: 1fr; }
HomeScreen.short #banner { display: none; }
SessionScreen.answer-only #log, ChallengeScreen.answer-only #log { display: none; }
SessionScreen.answer-only #panel, ChallengeScreen.answer-only #panel { height: 1fr; max-height: 100%; }
#picker #subs { height: auto; max-height: 60vh; }
#picker #find { margin: 0 0 0 0; }
ChallengeScreen.setup #log { display: none; }
ChallengeScreen.setup #panel { height: 1fr; max-height: 100%; }
ShortcutsScreen #panel, ShortcutRecallScreen #panel { height: auto; max-height: 50%; }
.sc-actions { height: auto; max-height: 12; border: none; padding: 0; }
.sc-input { margin: 0 1 0 0; }
ShortcutSettingsScreen #sc-setup { height: 1fr; padding: 0 0 0 1; }
ShortcutSettingsScreen #sc-settings, ShortcutSettingsScreen #sc-settings:focus { border: none; padding: 0; height: auto; }
ShortcutSettingsScreen #sc-detail { padding: 1 1 0 1; }
.panel.setup { height: 1fr; padding: 0 0 0 1; }
#setup { height: 1fr; scrollbar-size-vertical: 1; scrollbar-gutter: stable; scrollbar-background: $background; }
#setup #words { margin: 0 1 0 0; }
#setup #settings, #setup #settings:focus { border: none; padding: 0; height: auto; max-height: 100%; }
#setup #understood, #setup #detail, #setup #preview, #setup-note { padding: 0 1 0 1; }
#setup #detail { margin-bottom: 1; }
"""


class TutorApp(App):
    TITLE = "STEM Tutor"
    CSS = CSS
    ENABLE_COMMAND_PALETTE = False
    BINDINGS = [Binding("ctrl+c", "smart_quit", "Quit", show=False),
                Binding("ctrl+q", "smart_quit", "Quit", show=False, priority=True),
                Binding("ctrl+k", "answer_only", "Answer only", show=False, priority=True),
                Binding("f3", "answer_only", "Answer only", show=False)]

    def __init__(self, vault: Path | None = None, claude_binary: str | None = None, open_obsidian: bool | None = None,
                 seed: int | None = None):
        super().__init__()
        self.vault = Path(vault or config.vault_path())
        self.settings = config.Settings.load(self.vault)
        for theme in look.textual_themes():
            self.register_theme(theme)
        look.use(self.settings.theme)
        if open_obsidian is not None:
            self.settings.open_obsidian = open_obsidian
        self.claude_binary = claude_binary
        self.seed = seed
        self.tty: str | None = None  # the macOS Terminal tab, whose profile follows the look
        self.tty_profile: str | None = None  # the tab's profile before the tutor changed it: put back on exit
        self.font_base: int | None = None  # the tab's text size as its profile has it: the learner's own is measured from it
        self.font_lock = threading.Lock()  # a profile switch and a look at the size must not interleave (see settle_font_size)
        self.profile_missing = False
        self.profile_denied = False  # macOS refused the tutor control of Terminal: said once, then left alone
        self._locks = contextlib.ExitStack()
        self.speaker = tts.Speaker(self.vault, lambda: self.settings, notify=self._notify_from_thread)

    def settle_font_size(self) -> None:
        """Put the text size the learner chose back on the Terminal tab. A tab's profile brings its own size every time the
        tutor switches to it (at the start, and when the look changes), so a ⌘+ or ⌘− is lost; the size is kept in the
        settings (`remember_font_size`) and set again here, after the switch. `font_base` is the profile's size."""
        with self.font_lock:
            self.font_base = mac.terminal_font_size(self.tty)
            if self.font_base and (want := self.settings.font_size) and want != self.font_base:
                mac.terminal_font_size(self.tty, want)

    def remember_font_size(self) -> None:
        """Keep the tab's text size in the settings when it is not the profile's (and forget it when it is: ⌘0)."""
        with self.font_lock:
            size = mac.terminal_font_size(self.tty) if self.tty and self.font_base else None
            if not size:
                return
            keep = 0 if size == self.font_base else size
            if keep != self.settings.font_size:
                self.settings.font_size = keep
                try:
                    self.settings.save(self.vault)
                except OSError:
                    pass

    def _remember_font_tick(self) -> None:
        if self.tty and self.font_base:
            self.run_worker(self.remember_font_size, thread=True, group="terminal-font", exclusive=True)

    def _notify_from_thread(self, message: str) -> None:
        """A one-line note from the reading-aloud thread (or from this one)."""
        try:
            self.call_from_thread(self.notify, message, timeout=6)
        except RuntimeError:  # already on the app's own thread, or the app has stopped
            try:
                self.notify(message, timeout=6)
            except Exception:  # noqa: BLE001 - a note is never worth a crash
                pass

    def get_theme_variable_defaults(self) -> dict[str, str]:
        return look.CSS_DEFAULTS

    def on_mount(self) -> None:
        self.theme = look.THEME[self.settings.theme]
        if not (self.vault / ".tutor" / "config.json").exists():
            self.exit(message=f"No tutor folder at {self.vault}. Run: tutor doctor")
            return
        v = store.Vault(self.vault)
        try:
            self._locks.enter_context(v.lock(wait_seconds=1))
        except store.Locked:
            self.exit(message="Another STEM Tutor window is already open. Use that one (or close it first).")
            return
        try:
            self.tutor = Tutor(v, rng=random.Random(self.seed) if self.seed is not None else None, one_at_a_time=True)
        except packs.DamagedContent as e:
            self.exit(return_code=1, message=str(e))
            return
        for sub in self.tutor.packs.subtopics:  # read every chapter now: a damaged one is left out, and said once
            self.tutor.packs.pack(sub)
        for path in self.tutor.packs.damaged:
            self.notify(f"The content file {path} is damaged, so that chapter is left out: {packs.REINSTALL}.",
                        severity="warning", timeout=15)
        self.ai = Claude(self.vault, model=self.settings.model, binary=self.claude_binary,
                         usage_file=self.vault / ".tutor" / "ai_usage.json", speech=self.speech_wanted())
        self.ai.model, self.ai.think = self.settings.ai_for("ask")  # the conversation started ahead is the one asked most
        def warm() -> None:  # load the maths library in the background so the first algebra answer isn't slow
            try:
                from tutorlib import deps
                deps.ensure("sympy")
                import sympy  # noqa: F401
            except Exception:
                pass
        threading.Thread(target=warm, daemon=True).start()
        try:
            imported = mac.import_ipad_inbox(self.vault, config.ICLOUD_INBOX)
        except OSError:  # macOS privacy settings can block iCloud Drive: start anyway and say how to allow it
            imported = []
            self.notify(mac.INBOX_HELP, severity="warning", timeout=15)
        if imported:
            self.notify(f"Imported from your iPad inbox: {', '.join(imported)}")
        from .screens import HomeScreen
        self.push_screen(HomeScreen())
        self._tick_at, self._last_input = time.monotonic(), time.monotonic()
        self.set_interval(1, self._study_tick)  # session time: see tutorlib/clock.py
        self.set_interval(15, self._remember_font_tick)  # a closed window cannot be asked at the end: keep the size meanwhile
        if self.profile_missing:
            self.notify(mac.LOOK_HELP, timeout=15)
        if self.profile_denied:
            self.notify(mac.AUTOMATION_HELP, timeout=15)
        if self.size.width < 90 or self.size.height < 28:
            self.notify("Tip: make this window bigger (or full-screen) for the best view.", timeout=8)

    def on_resize(self) -> None:
        """Terminal keeps what was drawn beyond a narrowed window's new right edge and shows it in the strip beside its
        own scrollbar: old borders, pieces of scrollbar, letters. The app can only draw inside the window, so it
        clears the display (in the screen's colour, so nothing flashes) and draws everything again."""
        if self._driver is not None:
            r, g, b = self.screen.styles.background.rgb
            self._driver.write(f"\x1b[48;2;{r};{g};{b}m\x1b[2J\x1b[0m")
            self.screen.refresh()

    def claude_note(self) -> dict:
        """What Claude Code last noted about the plan's limits, read again at most every half minute."""
        import time
        at, note = getattr(self, "_claude_note", (0.0, {}))
        if not at or time.monotonic() - at > 30:
            note = mac.claude_limits(config.CLAUDE_STATE)
            self._claude_note = (time.monotonic(), note)
        return note

    def action_smart_quit(self) -> None:
        """ctrl+q / ctrl+c: on the menu it quits; anywhere else it saves and goes back a screen, asking first if
        something typed would be lost."""
        from textual.screen import ModalScreen
        from .screens import HomeScreen
        scr = self.screen
        if isinstance(scr, HomeScreen) or len(self.screen_stack) <= 2:
            self.exit()
        elif hasattr(scr, "action_leave"):
            scr.action_leave()
        elif isinstance(scr, ModalScreen):
            scr.dismiss(None)
        else:
            self.pop_screen()

    def speech_wanted(self) -> bool:
        """Ask the AI for a spoken version of its replies only when it can be read aloud (no cost otherwise)."""
        return bool(self.settings.tts_enabled and tts.available(self.vault))

    IDLE_LIMIT = 180  # seconds without a key or the mouse after which a study screen stops counting as time studied
    FLUSH_EVERY = 10  # seconds between writes of the study clock

    async def on_event(self, event) -> None:
        if isinstance(event, (events.Key, events.MouseDown, events.MouseScrollDown, events.MouseScrollUp)):
            self._last_input = time.monotonic()
        await super().on_event(event)

    def studying(self) -> bool:
        """A study screen is open (the lesson, challenge, blurt, chat, shortcuts), perhaps with a pop-up over it."""
        from textual.screen import ModalScreen
        stack = list(self.screen_stack)
        while stack and isinstance(stack[-1], ModalScreen) and not getattr(stack[-1], "studies", False):
            stack.pop()  # a pop-up over a study screen (ask the tutor, a hint) is still studying
        return bool(stack) and bool(getattr(stack[-1], "studies", False))

    def _study_tick(self, now: float | None = None) -> None:
        """Every second: while a study screen is open and the learner is there, add the time to today's total and to the
        session's. The terminal being closed counts nothing; neither does a stretch with no key (see IDLE_LIMIT) or a
        computer asleep (a gap of more than two seconds between ticks is not counted)."""
        now = time.monotonic() if now is None else now
        gap, self._tick_at = now - self._tick_at, now
        tutor = getattr(self, "tutor", None)
        if tutor is None or not (0 < gap <= 2.5) or now - self._last_input > self.IDLE_LIMIT or not self.studying():
            return
        clock = tutor.study_clock
        clock.add(tutor.now().date().isoformat(), gap, (tutor.session or {}).get("id") if self.session_counts() else None)
        self._since_flush = getattr(self, "_since_flush", 0.0) + gap
        if self._since_flush >= self.FLUSH_EVERY:
            self._since_flush = 0.0
            clock.flush()

    def session_counts(self) -> bool:
        """Only the lesson screen's time goes to the open session; the other study screens count for the day alone."""
        return getattr(self.screen, "study_session", False) or any(getattr(x, "study_session", False) for x in self.screen_stack)

    async def on_unmount(self) -> None:
        if hasattr(self, "tutor"):
            self.tutor.study_clock.flush()
        self.speaker.close()
        if hasattr(self, "ai"):
            await self.ai.close()
        self._locks.close()

    def apply_answer_only(self, screen=None) -> None:
        """Show only the answer box (the question is read in Obsidian, beside this window) or the whole screen again."""
        for each in [screen] if screen else self.screen_stack:  # a pop-up over a session leaves the session's view alone
            each.set_class(self.settings.answer_only, "answer-only")

    def action_answer_only(self) -> None:
        self.settings.answer_only = not self.settings.answer_only
        try:
            self.settings.save(self.vault)
        except OSError:
            pass  # the view still changes; it is just not remembered
        self.apply_answer_only()
        on = self.settings.answer_only
        here = any(x.__class__.__name__ in ("SessionScreen", "ChallengeScreen") for x in self.screen_stack)
        self.notify(("Answer-only view on: ctrl+k brings the question back." if on else "Question shown again.")
                    + ("" if here else " It applies in sessions and challenges."), timeout=4)

    def action_help(self) -> None:
        from .screens import HelpScreen
        self.push_screen(HelpScreen())

    def action_settings(self) -> None:
        from .screens import SettingsScreen
        self.push_screen(SettingsScreen())
