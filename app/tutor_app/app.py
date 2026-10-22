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
                Binding("f3", "answer_only", "Answer only", show=False),
                # ⌥+ ⌥− ⌥0: Option on its own types ≠ – º, and with "Use Option as Meta" it sends alt+…; both work
                Binding("alt+equals_sign,not_equal_to,alt+plus,plus_minus_sign", "text_size(1)", "Bigger text",
                        show=False, priority=True),
                Binding("alt+minus,en_dash", "text_size(-1)", "Smaller text", show=False, priority=True),
                Binding("alt+0,º", "text_size(0)", "Normal text size", show=False, priority=True)]
    FONT_RANGE = (8, 36)  # points: smaller is unreadable, larger leaves too few lines for a question

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
        self.font_lock = threading.Lock()  # a profile switch and a size change must not interleave (see settle_font_size)
        self.font_changed = False  # the learner set the size with ⌥+ / ⌥− this time (then a ⌘ zoom cannot be measured)
        self.zoom_kept: int | None = None  # the size a ⌘ zoom last time was matched to at this start: said once
        self.profile_missing = False
        self.profile_denied = False  # macOS refused the tutor control of Terminal: said once, then left alone
        self._locks = contextlib.ExitStack()
        self.speaker = tts.Speaker(self.vault, lambda: self.settings, notify=self._notify_from_thread)

    def settle_font_size(self) -> None:
        """Put the text size the learner chose back on the Terminal tab. A tab's profile brings its own size every time the
        tutor switches to it (at the start, and when the look changes); the size is kept in the settings and set again
        here, after the switch. `font_base` is the profile's size."""
        with self.font_lock:
            self.font_base = mac.terminal_font_size(self.tty)
            if self.font_base and (want := self.settings.font_size) and want != self.font_base:
                mac.terminal_font_size(self.tty, want)

    def text_size(self) -> int | None:
        """The text size in points now: the learner's, or the look's own."""
        return self.settings.font_size or self.font_base

    def set_text_size(self, size: int) -> None:
        """Set the Terminal tab's text size and keep it at once (so a window closed with its red button loses nothing)."""
        size = min(self.FONT_RANGE[1], max(self.FONT_RANGE[0], size))
        self.settings.font_size = 0 if size == self.font_base else size
        self.font_changed = True
        try:
            self.settings.save(self.vault)
        except OSError:
            pass  # it still changes; it is just not remembered

        def apply() -> None:
            with self.font_lock:
                mac.terminal_font_size(self.tty, size)
        self.run_worker(apply, thread=True, group="terminal-font", exclusive=True)

    def action_text_size(self, step: int) -> None:
        """⌥+ / ⌥− / ⌥0: the text bigger, smaller, or the look's normal size. Terminal's own ⌘+ and ⌘− zoom cannot be
        read by the tutor while it runs (only measured when it ends: `note_zoom`), so these are the keys it keeps exactly."""
        if not (self.tty and self.font_base):
            self.notify("Text size works in the macOS Terminal window the tutor opens.", timeout=5)
            return
        self.set_text_size(self.font_base if step == 0 else self.text_size() + step)
        size = self.text_size()
        self.notify(f"Text size {size} pt" + (" (normal)" if size == self.font_base else " · ⌥0 for normal"), timeout=3)

    def note_zoom(self, before: tuple[float, float] | None, after: tuple[float, float] | None) -> None:
        """At the end: if the text was zoomed with ⌘+ / ⌘−, keep it. The zoom cannot be read, only seen in the character
        cell (mac.cell_size, measured at the start and now). Character height does not grow evenly with the size (in
        Terminal 12 to 13 pt is twice the step of 13 to 14), so the size is guessed here and the height kept, for the
        next start to match exactly in a window with no zoom (`match_zoom`)."""
        if not (before and after and self.font_base) or self.font_changed or abs(after[1] - before[1]) < 0.3:
            return
        size = min(self.FONT_RANGE[1], max(self.FONT_RANGE[0], round(self.text_size() * after[1] / before[1])))
        self.settings.font_size = 0 if size == self.font_base else size
        self.settings.font_zoom_cell = round(after[1], 3)
        try:
            self.settings.save(self.vault)
        except OSError:
            pass

    def match_zoom(self, cell: tuple[float, float] | None, measure, settle: float = 0.25) -> tuple[float, float] | None:
        """At the start, before the app's screen: last time ended zoomed, so step the size (one point at a time, as ⌘+
        does) until the character height is the one measured then. A window still zoomed with ⌘ shows no size the tutor
        sets: then nothing can be matched, and the height is kept for a later start. Returns the cell as it is now."""
        target = self.settings.font_zoom_cell
        if not (target and cell and self.font_base):
            return cell

        def try_size(size: int) -> tuple[float, float] | None:
            mac.terminal_font_size(self.tty, size)
            time.sleep(settle)
            return measure()
        size = self.text_size()
        probe = size + (1 if size < self.FONT_RANGE[1] else -1)
        seen = try_size(probe)  # does a size set here show at all?
        if not seen or abs(seen[1] - cell[1]) < 0.01:
            mac.terminal_font_size(self.tty, size)  # still zoomed with ⌘ (or not measurable): try again next time
            return cell
        if abs(seen[1] - target) < abs(cell[1] - target):
            size, cell = probe, seen
        else:
            cell = try_size(size) or cell
        for _ in range(8):  # one point at a time towards the height, stopping at the nearest
            if abs(cell[1] - target) < 0.05:
                break
            nxt = min(self.FONT_RANGE[1], max(self.FONT_RANGE[0], size + (1 if cell[1] < target else -1)))
            now = try_size(nxt) if nxt != size else None
            if not now or abs(now[1] - target) >= abs(cell[1] - target):
                mac.terminal_font_size(self.tty, size)  # passed it: the one before was nearer
                break
            size, cell = nxt, now
        self.settings.font_size = 0 if size == self.font_base else size
        self.settings.font_zoom_cell = 0.0
        self.zoom_kept = size
        try:
            self.settings.save(self.vault)
        except OSError:
            pass
        return cell

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
        if self.profile_missing:
            self.notify(mac.LOOK_HELP, timeout=15)
        if self.profile_denied:
            self.notify(mac.AUTOMATION_HELP, timeout=15)
        if self.zoom_kept:  # last time ended zoomed with ⌘+ / ⌘−: say once what was kept
            self.notify(f"Your ⌘+ / ⌘− text size from last time is kept: {self.zoom_kept} pt. ⌥+ and ⌥− change it here "
                        "and keep it at once.", timeout=10)
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
