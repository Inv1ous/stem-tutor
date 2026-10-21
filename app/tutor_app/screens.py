"""Screens: Home, topic picker, the study session, summary, and small pop-ups (ask, help, settings)."""
from __future__ import annotations

import re
import textwrap
import time
from datetime import date, datetime, timedelta

from rich.text import Text
from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, Footer, Input, Markdown, OptionList, Select, SelectionList, Static, Switch
from textual.widgets.option_list import Option
from textual.widgets.selection_list import Selection

from tutorlib import almanac, clock, insights, model, policy, report, views
from tutorlib.lesson import GOALS

from . import ai as ai_mod
from . import cards, config, look, mac, prompts, tts
from . import __version__
from .look import C
from .panels import (ChoicePanel, ChoosePanel, Composer, ContinuePanel, LongPanel, Panel, ReflectPanel, TextPanel,
                     TickList, TickPanel, ValuePanel, WorkedPanel)
from .texmath import to_terminal


def bar(done: int, total: int, width: int = 12) -> str:
    fill = round(width * done / max(1, total))
    return "█" * fill + "░" * (width - fill)


def leave_asking_first(screen: Screen, boxes: str, typed: str = "answer") -> None:
    """Back to the previous screen, but not over something typed without asking: it would be lost."""
    if not any(w.text.strip() for w in screen.query(boxes)):
        screen.app.pop_screen()
        return

    def decided(choice: str | None) -> None:
        if choice == "leave" and screen.is_current:
            screen.app.pop_screen()
    screen.app.push_screen(ConfirmScreen(f"Leave? Your typed {typed} will be lost.",
                                         [("leave", "Leave"), ("stay", "Keep writing")]), decided)


def spoken_feedback(fb: dict, your: str = "", explanation: str | None = None) -> list[str]:
    """A marked answer as it is read aloud, in parts: the verdict and the answer, then why (maths is turned into
    words later). The question's own explanation is a part by itself, so its pre-generated audio is found."""
    dont_know = your.strip() in ("?", "I don't know")
    verdict = ("Here is the answer." if dont_know else "Correct." if fb.get("correct") else
               "Right value, but a mark was lost." if fb.get("partial") else "Not quite.")
    head = verdict + (f" The answer is {fb['answer']}." if fb.get("answer") not in (None, "") else "")
    parts = [head + (f" {fb['detail']}" if fb.get("detail") else "")]
    parts.append(explanation if explanation is not None else (fb.get("explanation") or ""))
    if (mis := fb.get("misconception")):
        parts += [f"A common trap: {mis.get('statement', '')}.", mis.get("refutation", "")]
    return [p for p in parts if p]


def spoken_too(app) -> dict:
    """one_shot's keyword for an on-the-spot comment: with read aloud on, the same reply carries a spoken version."""
    return {"speech": True} if getattr(getattr(app, "ai", None), "speech", False) else {}


class ReadAloud:
    """ctrl+e reads the thing on screen aloud, and again stops it. With automatic reading on, explanations, feedback
    and AI replies are read as they appear (never a question, never while you type). All a no-op, with a one-line
    hint for ctrl+e, until Kokoro is set up (`tutor tts setup`)."""
    readable = ""  # what ctrl+e reads, as text
    readable_parts: list[str] = []  # the same in its parts, each the exact text the pre-generator spoke

    def readable_now(self, text: str | list[str], auto: bool = False, limit: int | None = None) -> None:
        self.readable_parts = [p for p in ([text] if isinstance(text, str) else text) if p and p.strip()]
        self.readable = "\n\n".join(self.readable_parts)
        sp = getattr(self.app, "speaker", None)
        if sp is None:
            return
        if not auto:
            sp.stop()  # something new is on screen: the old line stops
            return
        s = self.app.settings
        if s.tts_auto and self.readable.strip() and not self.typing() and sp.usable:
            sp.say(self.readable_parts, limit=limit)
        else:
            sp.stop()

    def typing(self) -> bool:
        from textual.widgets import Input, TextArea
        w = self.app.focused
        return isinstance(w, (TextArea, Input)) and bool((w.text if isinstance(w, TextArea) else w.value).strip())

    def can_read(self) -> bool:
        sp = getattr(self.app, "speaker", None)
        return bool(sp and sp.usable)

    def action_read_aloud(self) -> None:
        sp = getattr(self.app, "speaker", None)
        if sp is None:
            return
        if sp.active:
            sp.stop()
            return
        if (why := sp.problem()):
            self.app.notify(why, timeout=6)
        elif not self.readable.strip():
            self.app.notify("Nothing to read aloud here yet.", timeout=4)
        else:
            sp.say(self.readable_parts)

    def hush(self) -> None:
        if (sp := getattr(self.app, "speaker", None)) is not None:
            sp.stop()

    def on_screen_suspend(self) -> None:
        self.hush()

    def on_unmount(self) -> None:
        self.hush()


READ_KEY = Binding("ctrl+e", "read_aloud", "Read", priority=True)


# ============================ Home ============================
MODE_NAMES = {"autopilot": "today's plan", "weak": "weak-spots"}
SUBJECTS = {"math": "Maths", "chem": "Chem", "phys": "Phys", "exam": "Exam"}


class HomeScreen(Screen):
    BINDINGS = [Binding("question_mark", "app.help", "Help"), Binding("f2", "app.settings", "Settings"),
                Binding("q", "app.quit", "Quit")]

    def compose(self) -> ComposeResult:
        yield Static(look.banner(), id="banner")
        yield Static(id="glance")  # the side box in one line, for a window too narrow to show it
        with Horizontal(id="home"):
            yield OptionList(id="menu")
            with VerticalScroll(id="stats"):  # more chapters than fit in the window: the box scrolls
                yield Static(id="stats-text")
        yield Footer()

    def on_resize(self) -> None:
        self._fit()
        self.call_after_refresh(self._fill_menu)  # the menu's width is known once the new layout is done
        self.call_after_refresh(self._draw_stats)  # and so is the side box's: its titles wrap to it

    def _draw_stats(self) -> None:
        try:
            now = self.app.tutor.now()
            self.query_one("#stats-text", Static).update(self.stats_text(now, model.due_kcs(self.app.tutor.state, now)))
        except Exception:  # noqa: BLE001 - the side box is a courtesy; a redraw never breaks the screen
            pass

    def _fill_menu(self) -> None:
        """Put the menu lines in, each wrapped to the menu's width with the words under the words, not under the icon."""
        items = getattr(self, "_menu_items", None)
        if not items:
            return
        # a short window has no room for the time line: the one-line summary and the side box say it there
        items = [i for i in items if i[0] != "time" or self.app.size.height >= 32]
        menu = self.query_one("#menu", OptionList)
        width = max(24, menu.size.width - 6) if menu.size.width else 46  # border, padding and the option's own gutter
        was = menu.get_option_at_index(menu.highlighted).id if menu.highlighted is not None else None
        menu.clear_options()
        for key, label in items:
            menu.add_option(Option(textwrap.fill(label, width, subsequent_indent="   ", break_long_words=False,
                                                 break_on_hyphens=False), id=key, disabled=key == "time"))  # a line to read
        ids = [key for key, _ in items]
        first = next((i for i, (key, _) in enumerate(items) if key != "time"), 0)
        menu.highlighted = ids.index(was) if was in ids else first  # back where you were, not at the top

    def _fit(self) -> None:
        """A narrow window drops the side box and gives the menu the width; a short one drops the banner."""
        w, h = self.app.size
        self.set_class(w < 84, "narrow")
        self.set_class(h < 30, "short")

    def on_screen_resume(self) -> None:
        self._fit()
        if self._read_almanac():  # exported while the tutor was open: the plan in Obsidian follows
            report.today_note(self.app.tutor, self.app.settings.minutes)
        self.refresh_home()

    def _read_almanac(self) -> list[str]:
        """Progress files the Almanac's Export button left in Downloads go into the vault, where ticks are read."""
        app = self.app
        try:
            moved = mac.import_almanac_exports(app.vault, config.DOWNLOADS)
        except OSError:
            if not getattr(app, "downloads_blocked", False):  # said once, not at every return to the menu
                app.downloads_blocked = True
                app.notify(mac.DOWNLOADS_HELP, severity="warning", timeout=15)
            return []
        if moved:
            app.tutor.read_almanac()  # the exam dates entered there, too
            app.notify("Read your ticks from the Almanac export in Downloads.", timeout=6)
        return moved

    def on_mount(self) -> None:
        app = self.app
        self._fit()
        self._read_almanac()
        views.organise_lessons(app.vault)  # lesson logs from before the day folders: moved into them, once
        views.write_home(app.vault, app.tutor.packs, app.tutor.state, app.tutor.now(), views.recent_lessons(app.vault))
        report.today_note(app.tutor, app.settings.minutes)  # Today.md: this week's plan and what's due
        if (week := self._week_in_review()):
            app.notify(f"Your week in review is ready: {week} in Obsidian.", timeout=10)
        self.refresh_home()

    def _week_in_review(self) -> str | None:
        """Last week's report, written once: the first time the app opens in a week that follows a week of study."""
        t = self.app.tutor
        today = t.now().date()
        monday = today - timedelta(days=today.weekday() + 7)
        year, week, _ = monday.isocalendar()
        studied = any(e["type"] == "answer" and monday <= date.fromisoformat(e["ts"][:10]) < monday + timedelta(days=7)
                      for e in t.vault.events())
        if not studied or (self.app.vault / "Weekly" / f"{year}-W{week:02d}.md").exists():
            return None
        return report.week_note(t, monday)

    def refresh_home(self) -> None:
        app = self.app
        t = app.tutor
        if (arrived := t.refresh_content()):  # chapters published while the app was open, e.g. by the foundry
            app.notify("New chapters ready: " + ", ".join(arrived), timeout=10)
        try:
            report.almanac_push(t)  # the Almanac page picks it up: ticks, colours, the wall, the retrospective
        except OSError:
            pass  # the planner's folder can't be written: the tutor itself is unaffected
        now = t.now()
        due = model.due_kcs(t.state, now)
        self.query_one("#banner", Static).update(look.banner())  # in the colours of the look just chosen
        menu = self.query_one("#menu", OptionList)
        items = []
        if t.session:
            s = t.session
            items.append(("resume", f"▸  Resume your {MODE_NAMES.get(s['mode'], s['mode'])} session "
                                    f"({s.get('answered', 0)} answered)"))
        week = policy.focus_week(t.packs.plan, t.state, t.ticks(), now) if t.packs.plan.get("weeks") else 0
        shortcut_lines = self._shortcut_lines()
        studied = t.study_clock.today(now.date().isoformat())
        sessions_today = t.study_clock.sessions_on(now.date().isoformat())
        items.insert(0, ("time", f"◔  Studied today: {clock.fmt(studied)}"
                                 + (f" · {sessions_today} session{'s' if sessions_today != 1 else ''}" if sessions_today else "")))
        items += [("today", f"★  Today's plan{f' (Almanac week {week})' if week else ''}"),
                  ("learn", "◆  Learn a topic (lesson)"),
                  ("review", f"↻  Review what's due ({len(due)})"),
                  ("weak", f"✚  Fix my weak spots ({len(insights.weak_spots(t))})"),
                  ("test", "◎  Test prep: check and fix a chapter"),
                  ("long", "✎  Long questions (typed or iPad)"),
                  ("blurt", "»  Blurt: write everything you remember"),
                  ("challenge", "⚑  Challenge: hard calculation questions"),
                  *shortcut_lines,
                  ("chat", "✦  Ask the tutor anything"),
                  ("insights", "◉  What the tutor knows about you"),
                  ("progress", "▤  My progress"),
                  ("obsidian", "▣  Open my notes in Obsidian"),
                  ("settings", "≡  Settings"), ("help", "?  How it works"), ("quit", "×  Quit")]
        self._menu_items = items
        self._fill_menu()
        menu.focus()
        self.query_one("#stats-text", Static).update(self.stats_text(now, due))
        self.call_after_refresh(self._draw_stats)  # again once the box has its width: the titles wrap to it
        glance = Text(f"✶ {self.streak(now)}-day streak · ↻ {len(due)} due · ◔ {clock.fmt(studied)} today", style=C["soft"])
        if (exam := self.next_exam(now)):
            glance.append(f" · ⧗ {exam}", style=C["plan"])
        self.query_one("#glance", Static).update(glance)

    def _shortcut_lines(self) -> list[tuple[str, str]]:
        """The two Shortcuts & Elegant Methods lines, with counts once the course has been published to the vault."""
        learn, recall = "↯  Shortcuts and elegant methods", "↯  Shortcut recall"
        try:
            vault = self.app.tutor.vault
            if (vault.tutor / "shortcuts" / "course").exists():
                from tutorlib import shortcuts
                course = shortcuts.Course(vault)
                learn += f" ({len(course.next_lessons())} new)"
                recall += f" ({len(course.due())} due)"
        except Exception:  # noqa: BLE001 - a damaged course file never keeps the menu from showing
            pass
        return [("shortcuts", learn), ("shortcut_recall", recall)]

    def streak(self, now: datetime) -> int:
        days = {date.fromisoformat(d) for d in self.app.tutor.state.get("study_days", [])}
        d = now.date() if now.date() in days else now.date() - timedelta(days=1)
        streak = 0
        while d in days:
            streak, d = streak + 1, d - timedelta(days=1)
        return streak

    def next_exam(self, now: datetime) -> str:
        sittings = sorted((date.fromisoformat(v), k) for k, v in (self.app.tutor.packs.plan.get("sittings") or {}).items()
                          if date.fromisoformat(v) >= now.date())
        return f"{sittings[0][1]}: {(sittings[0][0] - now.date()).days} days" if sittings else ""

    def stats_text(self, now: datetime, due: list) -> Text:
        app = self.app
        t = app.tutor
        out = Text()
        out.append(f"{now:%A %d %B}\n", style=f"bold {C['banner']}")
        out.append(f"✶ {self.streak(now)}-day streak   ↻ {len(due)} due\n", style=C["soft"])
        out.append(f"◔ Studied today: {clock.fmt(t.study_clock.today(now.date().isoformat()))}\n\n", style=C["soft"])
        if (exam := self.next_exam(now)):
            out.append(f"⧗ {exam}\n\n", style=C["plan"])
        ticked = t.ticks()
        week = policy.current_week(t.packs.plan, now)
        focus = policy.focus_week(t.packs.plan, t.state, ticked, now)  # past the calendar once this week is done
        objectives = (t.packs.plan.get("weeks") or {}).get(str(focus), [])
        if objectives:
            done = [policy.is_done(o, t.state, ticked) for o in objectives]
            out.append(f"▦ Almanac week {focus}" + (f" · {sum(done)} of {len(done)} done" if any(done) else "") + "\n",
                       style=f"bold {C['plan']}")
            if focus > week:
                out.append(f"You're ahead: the calendar is on week {week}.\n", style=C["ok"])
            for o, finished in list(zip(objectives, done))[:6]:
                kcs = o.get("kcs", [])
                ready = sum(1 for k in kcs if k in t.packs.kcs and t.packs.items_for(k))
                title = o["title"] if o.get("type", "NEW") == "NEW" else f"{o.get('verb', '')} {o['title']}".strip()
                title = title[:36] + ("…" if len(title) > 36 else "")
                out.append(f"{'✓' if finished else ' '} {SUBJECTS.get(o['subject'], o['subject']):<6}{title}",
                           style=C["dim"] if finished else C["text"])
                if kcs and not finished:
                    status = "ready" if ready == len(kcs) else f"{ready}/{len(kcs)} ready" if ready else "not built yet"
                    out.append(" " + status, style=C["ok"] if ready == len(kcs) else C["dim"])
                out.append("\n")
            export = almanac.latest_export(app.vault)
            out.append((f"Ticks read from your export of {datetime.fromtimestamp(export.stat().st_mtime):%-d %b %H:%M}."
                        if export else "To count your ticks: press Export in your Almanac.") + "\n\n", style=C["dim"])
        if mac.almanac_changed(t.packs.plan):
            out.append("△ Your Almanac has changed since the tutor read it: ask Claude Code to refresh the plan.\n\n",
                       style=C["hint"])
        out.append("Your topics\n", style="bold")
        # grouped: a heading for each subject (with its total) and chapter, subtopics under it in order; a title that does
        # not fit goes on to the next line, under itself, instead of being cut off
        width = max(36, self.query_one("#stats-text", Static).size.width or 46)
        lead = 2 + 9 + 1 + 6 + 7  # indent, id, space, bar, " 12/12 "
        for group in views.subtopic_groups(t.packs):
            ideas = [k for k, v in t.packs.kcs.items() if t.packs.subtopics.get(v["subtopic"], {}).get("topic") in
                     {c["id"] for c in group["chapters"]}]
            sure = sum(views.kc_status(t.state, k) == "secure" for k in ideas)
            out.append(f"\n{group['name']}", style=f"bold {C['banner']}")
            out.append(f"  {sure}/{len(ideas)} ideas secure\n", style=C["muted"])
            for chapter in group["chapters"]:
                kcs = [k for k, v in t.packs.kcs.items() if v["subtopic"] in chapter["subs"]]
                done = sum(views.kc_status(t.state, k) == "secure" for k in kcs)
                for i, line in enumerate(textwrap.wrap(chapter["name"], max(14, width - 9), break_long_words=True) or [""]):
                    out.append(f"{'▸ ' if i == 0 else '  '}{line}", style=f"bold {C['plan']}")
                    out.append(f"  {done}/{len(kcs)}\n" if i == 0 and len(chapter["name"]) <= width - 9 else "\n",
                               style=C["muted"])
                for sub in chapter["subs"]:
                    kcs = [k for k, v in t.packs.kcs.items() if v["subtopic"] == sub]
                    sec = sum(views.kc_status(t.state, k) == "secure" for k in kcs)
                    started = any(views.kc_status(t.state, k) != "new" for k in kcs)
                    colour = C["ok"] if sec == len(kcs) else C["soft"] if started else C["dim"]
                    lines = textwrap.wrap(t.packs.subtopics[sub]["title"], max(12, width - lead), break_long_words=True) or [""]
                    out.append(f"  {sub:<9} ", style=C["text"])
                    out.append(bar(sec, len(kcs), 6), style=colour)
                    out.append(f" {f'{sec}/{len(kcs)}':<6}", style=C["muted"])
                    out.append(lines[0] + "\n", style=C["muted"])
                    for more in lines[1:]:
                        out.append(" " * lead + more + "\n", style=C["muted"])
        a = app.ai
        state = ("on" if a.available else {"login": "sign-in needed", "limit": "paused (limit)",
                                           "off": "not installed"}.get(a.status, a.status)) if app.settings.ai else "off"
        left = a.limits_text(app.claude_note())
        out.append(f"\nAI tutor: {state} · {a.today()['replies']} replies today{' · ' + left if left else ''}\n",
                   style=C["ai"])
        out.append(f"\nSTEM Tutor v{__version__}", style=C["dim"])
        return out

    @on(OptionList.OptionSelected, "#menu")
    def pick(self, event: OptionList.OptionSelected) -> None:
        key = event.option.id
        app = self.app
        s = app.tutor.session
        if key in ("today", "learn", "review", "weak", "test", "long", "blurt") and s and s.get("answered"):
            def decided(choice: str | None) -> None:
                if choice == "resume":
                    app.push_screen(SessionScreen(None))
                elif choice == "new":
                    app.tutor.end(abandoned=True)
                    self.refresh_home()
                    self._start(key)
            name = MODE_NAMES.get(s["mode"], s["mode"])
            app.push_screen(ConfirmScreen(f"You have an unfinished {name} session ({s['answered']} answered).",
                                          [("resume", "Resume it"), ("new", "Abandon it and start this"),
                                           ("cancel", "Cancel")]), decided)
            return
        self._start(key)

    def _start(self, key: str) -> None:
        app = self.app
        if key == "resume":
            app.push_screen(SessionScreen(None))
        elif key == "today":  # the engine's autopilot: what's due first, then the Almanac's topics in week order
            if not policy.plan_session(app.tutor.state, app.tutor.packs, app.tutor.now(), app.settings.minutes,
                                       ticked=app.tutor.ticks()):
                app.notify("Nothing to plan right now: no reviews are due and every Almanac topic with questions so "
                           "far is done. The next topics aren't built yet; try a blurt or long questions.", timeout=8)
                return
            app.push_screen(SessionScreen({"mode": "autopilot", "focus": None, "minutes": app.settings.minutes}))
        elif key == "weak":
            weak = insights.weak_spots(app.tutor)
            if not weak:
                app.notify("No weak spots right now: no active misconceptions, gaps, or ideas you keep getting wrong.",
                           timeout=6)
                return
            app.push_screen(SessionScreen({"mode": "weak", "focus": [w["kc"] for w in weak],
                                           "minutes": app.settings.minutes}))
        elif key == "insights":
            app.push_screen(InsightsScreen())
        elif key == "learn":
            app.push_screen(PickerScreen("lesson"), lambda r: r and app.push_screen(
                SessionScreen({"mode": "lesson", "focus": r, "minutes": app.settings.minutes})))
        elif key == "review":
            if not model.due_kcs(app.tutor.state, app.tutor.now()):
                app.notify("Nothing is due right now: your memory is on schedule. Try a lesson or a blurt instead.",
                           timeout=6)
                return
            app.push_screen(SessionScreen({"mode": "review", "focus": None, "minutes": app.settings.minutes}))
        elif key == "test":
            app.push_screen(PickerScreen("test"), lambda r: r and app.push_screen(
                SessionScreen({"mode": "test", "focus": r, "minutes": app.settings.minutes})))
        elif key == "long":
            app.push_screen(PickerScreen("long"), lambda r: r and app.push_screen(
                SessionScreen({"mode": "long", "focus": r, "minutes": 30})))
        elif key == "blurt":
            app.push_screen(PickerScreen("blurt"), lambda r: r and app.push_screen(BlurtScreen(r[0])))
        elif key == "challenge":
            from .challenge_screen import ChallengeScreen
            app.push_screen(ChallengeScreen())
        elif key == "shortcuts":
            from .shortcuts_screen import ShortcutsScreen
            app.push_screen(ShortcutsScreen())
        elif key == "shortcut_recall":
            from .shortcuts_screen import ShortcutRecallScreen
            app.push_screen(ShortcutRecallScreen())
        elif key == "chat":
            app.push_screen(ChatScreen())
        elif key == "progress":
            app.push_screen(ProgressScreen())
        elif key == "obsidian":
            views.write_home(app.vault, app.tutor.packs, app.tutor.state, app.tutor.now(), views.recent_lessons(app.vault))
            mac.open_in_obsidian(app.vault, "Home", background=False)
        elif key == "settings":
            app.action_settings()
        elif key == "help":
            app.action_help()
        elif key == "quit":
            app.exit()


# ============================ Topic picker ============================
def _natural(text: str) -> list:
    """Sort key that puts 9701-1.2 before 9701-1.10."""
    return [int(x) if x.isdigit() else x for x in re.split(r"(\d+)", text)]


SEARCH_WORDS = {"chem": "chemistry chem", "phys": "physics phys", "math": "maths math mathematics"}
SUBJECT_FOLDERS = (("chem", "Chemistry 9701"), ("phys", "Physics 9702"), ("math", "Maths"))


class PickerScreen(ModalScreen):
    """Choose a subtopic (or, for a test, several), as folders: Chemistry, Physics, Maths, each holding a folder per chapter
    (Maths: per module) with the subtopics inside. ⏎ opens a folder, Esc or ← goes up. Typing searches everything at once; Esc clears the search first.
    In a test, space on a folder ticks everything in it, ctrl+a everything shown, ctrl+d clears."""
    BINDINGS = [Binding("escape", "back", "Back"), Binding("ctrl+s", "go", show=False),
                Binding("slash", "search", show=False), Binding("right_square_bracket", "jump(1)", show=False),
                Binding("left_square_bracket", "jump(-1)", show=False), Binding("left", "up", show=False),
                Binding("backspace", "up", show=False), Binding("ctrl+a", "tick_shown", show=False, priority=True),
                Binding("ctrl+d", "untick_all", show=False, priority=True), Binding("space", "tick", show=False)]

    def __init__(self, mode: str) -> None:
        super().__init__()
        self.mode = mode
        self.ticked: set[str] = set()
        self.needle = ""
        self.path: list[str] = []
        self.floor = 0  # folders opened for you when there was only one: Esc does not go back into them

    # ---------- data ----------
    def _prepare(self) -> None:
        t = self.app.tutor
        self.built = [s for s in t.packs.subtopics if t.packs.pack(s)]
        self.info: dict[str, dict] = {}
        for sub in self.built:
            kcs = [k for k, v in t.packs.kcs.items() if v["subtopic"] == sub]
            topic = t.packs.subtopics[sub].get("topic", "")
            self.info[sub] = {"sec": sum(views.kc_status(t.state, k) == "secure" for k in kcs), "n": len(kcs),
                              "topic": topic, "subject": t.packs.topics.get(topic, {}).get("subject", "math")}
        order = {tid: i for i, tid in enumerate(t.packs.topics)}
        self.groups: dict[str, list[str]] = {}
        for sub in sorted(self.built, key=lambda x: (order.get(self.info[x]["topic"], 99), _natural(x))):
            self.groups.setdefault(self.info[sub]["topic"], []).append(sub)
        self.hay = {}
        for sub in self.built:
            topic = t.packs.topics.get(self.info[sub]["topic"], {})
            self.hay[sub] = " ".join([sub, t.packs.subtopics[sub]["title"], topic.get("title", ""), topic.get("spec", ""),
                                      topic.get("level", ""), SEARCH_WORDS.get(self.info[sub]["subject"], ""),
                                      self.info[sub]["topic"]]).lower().replace("-", " ")
        self.path = []
        while len(kids := self._folders(self.path)) == 1:  # one folder only: open it, nothing to choose
            self.path.append(kids[0][0])
        self.floor = len(self.path)

    def _under(self, path: list[str]) -> list[str]:
        """Every subtopic inside a folder, in order."""
        subs = [s for subs in self.groups.values() for s in subs]
        if not path:
            return subs
        subs = [s for s in subs if self.info[s]["subject"] == path[0]]
        return [s for s in subs if self.info[s]["topic"] == path[1]] if len(path) > 1 else subs

    def _folders(self, path: list[str]) -> list[tuple[str, str]]:
        """The folders in a folder: (key, name). Subjects at the top, each subject's chapters under it (Chemistry and
        Physics topics, Maths modules), subtopics inside those: nothing deeper."""
        if not path:
            return [(k, name) for k, name in SUBJECT_FOLDERS if self._under([k])]
        if len(path) == 1:
            return [(tid, self._chapter_name(tid)) for tid in self.groups if self.info[self.groups[tid][0]]["subject"] == path[0]]
        return []

    def _chapter_name(self, tid: str) -> str:
        topic = self.app.tutor.packs.topics.get(tid, {})
        if topic.get("subject") in ("chem", "phys"):
            return self._topic_label(tid)
        return f"{tid}  {topic.get('title', '')}".strip()

    def _topic_label(self, tid: str) -> str:
        topic = self.app.tutor.packs.topics.get(tid, {})
        if topic.get("subject") in ("chem", "phys"):
            return f"{tid.split('-')[-1]}. {topic.get('title', tid)}" + (f" ({topic['level']})" if topic.get("level") else "")
        return f"Maths · {tid} {topic.get('title', '')}".strip()

    def _mark(self, subs: list[str]) -> Text:
        if self.mode != "test":
            return Text()
        n = sum(s in self.ticked for s in subs)
        return Text("[x] " if subs and n == len(subs) else "[-] " if n else "[ ] ",
                    style=C["ok"] if n else C["dim"])

    def _row(self, sub: str) -> Text:
        i, t = self.info[sub], self.app.tutor
        line = self._mark([sub])
        done = i["n"] and i["sec"] == i["n"]
        line.append(f"{sub:<9} ", style=C["text"])
        line.append(bar(i["sec"], i["n"], 8), style=C["ok"] if done else C["soft"] if i["sec"] else C["dim"])
        line.append(f" {i['sec']}/{i['n']}  ", style=C["muted"])
        line.append(t.packs.subtopics[sub]["title"], style=C["dim"] if done else C["text"])
        return line

    def _folder_row(self, path: list[str], name: str, width: int = 34) -> Text:
        subs = self._under(path)
        name = name if len(name) <= width else name[:max(1, width - 1)] + "…"
        sec, n = sum(self.info[s]["sec"] for s in subs), sum(self.info[s]["n"] for s in subs)
        line = self._mark(subs)
        line.append("▸ ", style=C["plan"])
        line.append(f"{name:<{width}} ", style=f"bold {C['text']}")  # a space before the bar, even for the longest
        line.append(bar(sec, n, 8), style=C["ok"] if n and sec == n else C["soft"] if sec else C["dim"])
        line.append(f" {sec}/{n} ideas · {len(subs)} subtopic{'s' if len(subs) != 1 else ''}", style=C["muted"])
        return line

    def _matches(self, sub: str) -> bool:
        words = self.needle.lower().replace("-", " ").split()
        return all(w in self.hay[sub] for w in words)

    def _crumb(self) -> str:
        names = dict(SUBJECT_FOLDERS)
        parts = [{"lesson": "Learn", "long": "Long questions", "blurt": "Blurt", "test": "Test prep"}.get(self.mode, "Topics")]
        if self.path:
            parts.append(names.get(self.path[0], self.path[0]))
            parts += [self._chapter_name(tid) for tid in self.path[1:]]
        return " › ".join(parts)

    # ---------- screen ----------
    def compose(self) -> ComposeResult:
        self._prepare()
        with Vertical(id="picker"):
            if self.mode == "test":
                yield Static("Tick the subtopics the test covers: space to tick (on a folder: all in it), ctrl+a ticks all "
                             "shown, Tab to Start (or ctrl+s), Esc to go back.", classes="hint")
            else:
                ask = {"lesson": "Which subtopic do you want to learn?",
                       "long": "Which subtopic do you want to practise with long questions?",
                       "blurt": "Pick a subtopic to blurt on."}.get(self.mode, "Which subtopic do you want to study?")
                yield Static(f"{ask} (⏎ to choose or open a folder, Esc to go back)", classes="hint")
            yield Input(placeholder="Search everything: a word, a code (9702-3, P1) …  or just start typing", id="find",
                        compact=True, select_on_focus=False)
            yield Static(id="found", classes="hint")
            yield OptionList(id="subs")
            if self.mode == "test":
                yield Button("Start test prep", id="go", variant="primary")

    def on_mount(self) -> None:
        self.fill()
        self.query_one("#subs", OptionList).focus()
        self.call_after_refresh(self._fit)

    def on_resize(self) -> None:
        self.call_after_refresh(self._fit)

    def _fit(self) -> None:
        """The list takes what the window leaves after the hints, the search box and (a test) the Start button, so the
        button is never pushed off the bottom of a short window; a new width draws the folder rows again to fit it."""
        try:
            width = self.query_one("#subs", OptionList).size.width
            if width != getattr(self, "_drawn_at", width):
                self._drawn_at = width
                self.fill()
            self._drawn_at = width
            fixed = sum(w.outer_size.height for w in self.query("#picker > .hint, #picker > Input, #picker > Button"))
            self.query_one("#subs", OptionList).styles.max_height = max(4, int(self.app.size.height * 0.9) - 4 - fixed)
        except Exception:  # noqa: BLE001 - a layout hiccup never keeps the picker from opening
            pass

    def fill(self, keep: str | None = None) -> None:
        """Put the rows in: what matches the search (grouped by topic), or the folder you are in."""
        box = self.query_one("#subs", OptionList)
        was = keep or (box.get_option_at_index(box.highlighted).id if box.highlighted is not None else None)
        box.clear_options()
        rows: list[Option] = []
        shown = 0
        if self.needle:
            for tid, subs in self.groups.items():
                hits = [s for s in subs if self._matches(s)]
                if hits:
                    subject = dict(SUBJECT_FOLDERS).get(self.info[hits[0]]["subject"], "")
                    head = (f"{subject} · " if self.info[hits[0]]["subject"] != "math" else "") + self._topic_label(tid)
                    rows.append(Option(Text(head, style=f"bold {C['plan']}"), id=f"h:{tid}", disabled=True))
                    rows += [Option(self._row(s), id=s) for s in hits]
                    shown += len(hits)
            if not shown:
                rows = [Option(Text(f"Nothing matches “{self.needle}”. Esc clears the search.", style=C["dim"]), id="none",
                               disabled=True)]
        elif folders := self._folders(self.path):
            # one name column for the whole list, as wide as the longest name the window allows, so the bars line up
            # the row's other parts: tick box, ▸, a space, the 8-cell bar and "999/999 ideas · 99 subtopics"
            room = max(14, (box.size.width or 80) - (4 if self.mode == "test" else 0) - 2 - 2 - 1 - 8 - 28)
            width = min(max(len(name) for _, name in folders), room)
            rows = [Option(self._folder_row(self.path + [key], name, width), id="dir:" + "/".join(self.path + [key]))
                    for key, name in folders]
            shown = len(self._under(self.path))
        else:
            rows = [Option(self._row(sub), id=sub) for sub in self._under(self.path)]
            shown = len(rows)
        box.add_options(rows)
        ids = [o.id for o in rows]
        pick = was if was in ids else next((o.id for o in rows if not o.disabled), None)
        box.highlighted = ids.index(pick) if pick in ids else None
        where = f"{len(self.built)} subtopics · {shown} match" if self.needle else self._crumb()
        ticks = f" · {len(self.ticked)} ticked" if self.mode == "test" else ""
        keys = " · type to search · ⏎ open · Esc up" if not self.needle and not self.path else ""
        self.query_one("#found", Static).update(
            (f"Search: {shown} of {len(self.built)} subtopics" if self.needle else where) + ticks + keys)

    @on(Input.Changed, "#find")
    def typed(self, event: Input.Changed) -> None:
        self.needle = event.value.strip()
        self.fill()

    @on(Input.Submitted, "#find")
    def entered(self) -> None:
        """Enter in the search box: take the first match (a test: tick it and go to the list)."""
        box = self.query_one("#subs", OptionList)
        first = next((o for o in (box.get_option_at_index(i) for i in range(box.option_count)) if not o.disabled), None)
        if first is None:
            return
        if self.mode == "test":
            self.toggle(first.id)
            box.focus()
        else:
            self.dismiss([first.id])

    def on_key(self, event) -> None:
        """Typing in the list starts a search: no need to click the box first."""
        if (isinstance(self.focused, OptionList) and event.character and event.character.isprintable()
                and event.character not in " /[]"):
            box = self.query_one("#find", Input)
            box.focus()
            box.value += event.character
            box.cursor_position = len(box.value)
            event.stop()
        elif isinstance(self.focused, Input) and event.key == "down":
            self.query_one("#subs", OptionList).focus()
            event.stop()

    def _ids_of(self, option_id: str) -> list[str]:
        """The subtopics an option stands for: itself, or everything inside a folder."""
        return self._under(option_id[4:].split("/")) if option_id.startswith("dir:") else [option_id]

    def toggle(self, option_id: str) -> None:
        subs = self._ids_of(option_id)
        if all(s in self.ticked for s in subs):
            self.ticked -= set(subs)
        else:
            self.ticked |= set(subs)
        self.fill(keep=option_id)

    def open(self, option_id: str) -> None:
        self.path = option_id[4:].split("/")
        self.fill()

    @on(OptionList.OptionSelected, "#subs")
    def chose(self, event: OptionList.OptionSelected) -> None:
        oid = str(event.option.id)
        if oid.startswith("dir:"):
            self.open(oid)
        elif self.mode == "test":
            self.toggle(oid)
        else:
            self.dismiss([oid])

    # ---------- actions ----------
    def action_up(self) -> None:
        """Up one folder (not into the one that was opened for you, and not while typing a search)."""
        if isinstance(self.focused, Input) or self.needle or len(self.path) <= self.floor:
            return
        came = "dir:" + "/".join(self.path)
        self.path = self.path[:-1]
        self.fill(keep=came)

    def action_back(self) -> None:
        if self.needle:  # the first Esc clears the search, then up a folder, then out
            self.query_one("#find", Input).value = ""
            self.query_one("#subs", OptionList).focus()
        elif len(self.path) > self.floor:
            self.action_up()
        else:
            self.dismiss(None)

    def action_search(self) -> None:
        self.query_one("#find", Input).focus()

    def action_jump(self, step: int) -> None:
        """Move to the first subtopic of the next (or previous) topic."""
        box = self.query_one("#subs", OptionList)
        opts = [box.get_option_at_index(i) for i in range(box.option_count)]
        heads = [i for i, o in enumerate(opts) if str(o.id).startswith("h:")]
        here = box.highlighted or 0
        target = next((h for h in heads if h > here), None) if step > 0 else next((h for h in reversed(heads) if h < here - 1), None)
        if target is not None and target + 1 < len(opts):
            box.highlighted = target + 1
        elif step < 0 and heads:
            box.highlighted = heads[0] + 1

    def action_tick(self) -> None:
        if self.mode != "test" or not isinstance(self.focused, OptionList):
            return
        box = self.query_one("#subs", OptionList)
        if box.highlighted is not None and not box.get_option_at_index(box.highlighted).disabled:
            self.toggle(str(box.get_option_at_index(box.highlighted).id))

    def action_tick_shown(self) -> None:
        if self.mode == "test":
            self.ticked |= {s for s in (self.built if self.needle else self._under(self.path)) if not self.needle or self._matches(s)}
            self.fill()

    def action_untick_all(self) -> None:
        if self.mode == "test":
            self.ticked.clear()
            self.fill()

    @on(Button.Pressed, "#go")
    def action_go(self) -> None:
        if self.mode != "test":
            return
        if self.ticked:
            self.dismiss(sorted(self.ticked, key=_natural))
        else:
            self.app.notify("Tick at least one subtopic (space), then Start.", timeout=5)


# ============================ Session ============================
class SessionScreen(ReadAloud, Screen):
    studies = True  # its time is counted as time studied (TutorApp._study_tick), and kept for the session
    study_session = True

    # first in the footer: how to get out and how to get help, so a narrow window still shows them
    BINDINGS = [Binding("ctrl+b", "leave", "Menu", priority=True), Binding("question_mark", "app.help", "Help"),
                Binding("ctrl+t", "ask", "Ask", priority=True), Binding("ctrl+g", "hint", "Hint", priority=True),
                Binding("ctrl+r", "explain", "Explain", priority=True),
                Binding("ctrl+o", "obsidian", "Notes", priority=True),
                Binding("ctrl+e", "read_aloud", "Read", show=False, priority=True),  # in Help; keeps 60 columns
                Binding("ctrl+l", "earlier", "Earlier", show=False, priority=True),  # in Help; keeps 60 columns
                Binding("t", "ask", show=False), Binding("e", "explain", show=False), Binding("h", "hint", show=False),
                Binding("o", "obsidian", show=False), Binding("escape", "esc", show=False),
                Binding("alt+up", "scroll_log(-1)", show=False, priority=True),
                Binding("alt+down", "scroll_log(1)", show=False, priority=True)]

    def __init__(self, start: dict | None) -> None:
        super().__init__()
        self.start_args, self.act, self.kc, self.view = start, {}, None, None
        self.started = time.monotonic()
        self.chatting = False

    def compose(self) -> ComposeResult:
        yield Static(id="bar")
        yield Static(id="map")
        yield VerticalScroll(id="log", can_focus=False)  # Tab stays in the answer panel; alt+↑↓ and the wheel scroll it
        yield Container(id="panel")
        yield Footer()

    # ---------- plumbing ----------
    @property
    def tutor(self):
        return self.app.tutor

    def say(self, renderable) -> Static:
        w = Static(renderable, classes="entry")
        log = self.query_one("#log", VerticalScroll)
        log.mount(w)
        log.scroll_end(animate=False)
        return w

    def fold(self) -> None:
        """Put away what has been said so far. A question is answered from memory: the Now page shows it alone, and
        so does this side, or the explanation just given could simply be read off the screen."""
        for w in self.query("#log > .entry"):
            w.display = False

    def action_earlier(self) -> None:
        """Bring back what was put away. Not while there is something to recall."""
        if (self.tutor.session or {}).get("presented") or self.act.get("activity") == "own_words":
            self.app.notify("Answer first: this asks you to recall what came before. It all comes back afterwards "
                            "with ctrl+l.", timeout=6)
            return
        for w in self.query("#log > .entry"):
            w.display = True
        self.query_one("#log", VerticalScroll).scroll_end(animate=False)

    def panel(self, widget) -> None:
        box = self.query_one("#panel", Container)
        box.remove_children()
        box.mount(widget)
        self.showing = widget

    def on_mount(self) -> None:
        t = self.tutor
        if self.start_args:
            res = t.start(self.start_args["mode"], self.start_args.get("minutes", 40), self.start_args.get("focus"),
                          replace=True)
            if res.get("ok") is False:
                self.say(cards.card("bad", "Can't start", f"{res['error']}\n\n{res.get('fix', '')}"))
                self.panel(ContinuePanel(buttons=[("home", "Back to menu ⏎")]))
                return
            mode = self.start_args["mode"]
            self.say(cards.card("tutor", "Let's go", {
                "lesson": "We'll find out what you already know, agree a plan, then build each idea step by step. "
                          "Your notes grow in Obsidian as we go.",
                "review": "Spaced review: the ideas that are due, mixed together. No hints on the first try.",
                "test": "One question on every syllabus point, then we fix only what you miss.",
                "long": "Exam-style long questions: write your answer, then mark it against the scheme."}.get(mode, "")))
        elif t.session:  # resuming: say so, show where things were, keep the real elapsed time
            from datetime import datetime as _dt
            started = _dt.fromisoformat(t.session["started"])
            self.started = time.monotonic() - max(0.0, (t.now() - started).total_seconds())
            self.say(cards.card("tutor", "Welcome back",
                                f"Carrying on your {t.session['mode']} session: {t.session.get('answered', 0)} answered so far."))
        if self.app.settings.open_obsidian:
            mac.open_in_obsidian(self.app.vault, "Now")
        self.app.apply_answer_only(self)
        self.set_interval(1, self.update_bar)
        self.advance()

    def bar_text(self, width: int) -> Text:
        """The top bar: what this session is, then how it is going (time, score, AI use, what is left of the week's
        limit). On one line when it all fits. When it does not, the running figures move whole to a second line; a
        line still too long for the window ends in an ellipsis, so the bar is never more than two lines."""
        t = self.tutor
        s = t.session or {}
        sub = s.get("subtopic")
        title = to_terminal(t.packs.subtopics.get(sub, {}).get("title", "")) if sub else ""
        true_s = time.monotonic() - self.started  # the wall clock since the session began: runs while the terminal is closed
        active_s = t.study_clock.session(s.get("id"))  # what was really spent on this screen
        a = self.app.ai
        ai_state = "AI ●" if (self.app.settings.ai and a.available) else "AI ○"
        mode = {"lesson": "Lesson", "review": "Review", "test": "Test prep", "long": "Long questions"}.get(
            s.get("mode", ""), s.get("mode", "").title())
        use = " · ".join(x for x in (f"{a.session.replies} {'reply' if a.session.replies == 1 else 'replies'}",
                                     a.limits_text(self.app.claude_note())) if x)
        head, tail = Text(), Text()
        head.append(" STEM Tutor ", style=f"bold {C['badge_fg']} on {C['badge_bg']}")
        head.append(f" {title + ' · ' if title else ''}{mode} ", style="bold")
        tail.append(f" ◷ {clock.fmt(true_s, True)} true ", style=C["plan"])
        tail.append(f" ◔ {clock.fmt(active_s, True)} session ", style=C["plan"])
        tail.append(f" ✓ {s.get('correct', 0)}/{s.get('answered', 0)} ", style=C["good"])
        tail.append(f" {ai_state} {use} ", style=C["ai"])
        if head.cell_len + tail.cell_len <= width:
            return head + tail
        for line in (head, tail):
            line.truncate(width, overflow="ellipsis")
        return head + Text("\n") + tail

    def update_bar(self) -> None:
        t = self.tutor
        s = t.session or {}
        self.query_one("#bar", Static).update(self.bar_text(self.size.width or self.app.size.width))
        nodes = [b for b in s.get("blocks", []) if b.get("kind") == "node"]
        if nodes:
            m = Text(" Map: ", style=C["muted"])
            for b in nodes:
                kc = b["kc"]
                glyph, style = ("✓", C["ok"]) if kc in s.get("kcs_learned", []) else \
                    ("▸", f"bold {C['tutor']}") if kc == self.kc else ("○", C["dim"])
                name = to_terminal(t.packs.kcs[kc]["title"])
                m.append(f"{glyph} {name if len(name) <= 24 else name[:23] + '…'}  ", style=style)
            self.query_one("#map", Static).update(m)

    # ---------- the loop ----------
    def advance(self) -> None:
        t = self.tutor
        act = t.next()
        self.act = act
        kind = act["activity"]
        kc = act.get("kc") or (t.session["presented"][str(act["items"][0]["n"])]["kcs"][0]
                               if kind in ("questions", "awaiting") and act.get("items") else self.kc)
        cursor = (t.session or {}).get("cursor")
        if (kind == "explain" and act.get("part") == "motivate") or cursor != getattr(self, "last_cursor", cursor):
            self.run_worker(self.app.ai.reset(), group="reset")  # new idea or block: fresh AI memory, small context
        self.last_cursor = cursor
        self.kc = kc
        self.update_bar()
        self.readable_now("")  # Next: the line being read stops
        if kind in ("questions", "awaiting"):
            self.ask_question(act["items"][0], act.get("say"))
        elif kind in ("explain", "teach"):
            title = act.get("title") or act.get("kc_title", "")
            text = act.get("text") or act.get("outline", "")
            spoken = [text]  # the card's own text alone: its pre-generated audio is found by it
            if kind == "teach" and act.get("misconceptions"):
                text += "\n\n" + "\n".join(f"- Trap: {m}" for m in act["misconceptions"])
                spoken += [f"A common trap: {m}." for m in act["misconceptions"]]
            self.say(cards.card("tutor", title, text, subtitle="second look" if act.get("part") == "fix" else None))
            self.readable_now(spoken, auto=True)
            self.panel(ContinuePanel(read=self.can_read()))
        elif kind == "choose":
            self.say(cards.card("plan", act["question"], ""))
            self.panel(ChoosePanel("Pick how you want to learn this (↑↓ and ⏎)", act["options"]))
        elif kind == "plan":
            lines = [act["approach"], ""] + [f"- {'✓ you know: ' if n['known'] else ''}{n['title']}" for n in act["nodes"]]
            self.say(cards.card("plan", f"Plan: {act['title']}", "\n".join(lines),
                                subtitle="the concept map is in Obsidian → Now"))
            self.prepare_cards(act["default_teach"])  # AI teaching cards (if needed) start while you read the plan
            self.panel(TickPanel("Ticked ideas will be taught (space to change). Then ctrl+s, or ⏎ on Start.",
                                 [(n["title"], n["kc"], n["kc"] in act["default_teach"]) for n in act["nodes"]],
                                 [("start", "Start lesson ⏎")]))
        elif kind in ("worked", "walkthrough"):
            self.say(cards.card("tutor", "Worked example", act.get("problem") or "Walk through it step by step."))
            for i, st in enumerate(act["steps"][:act.get("revealed", 0)], 1):  # steps already seen before a resume
                self.say(cards.card("tutor", f"Step {i}", f"{st['do']}\n\n_{st.get('why', '')}_"))
            self.readable = act.get("problem") or ""
            self.panel(WorkedPanel(len(act["steps"]), start=act.get("revealed", 0) + 1))
        elif kind == "refute":
            m = act["misconceptions"][0]
            m = m if isinstance(m, dict) else {"statement": m}
            self.say(cards.card("hint", f"Trap: {m.get('statement', '')}",
                                f"{m.get('refutation', '')}\n\n{('_Compare:_ ' + m['contrast']) if m.get('contrast') else ''}"))
            self.readable_now([f"A common trap: {m.get('statement', '')}.", m.get("refutation", ""),
                               m.get("contrast") or ""], auto=True)
            self.panel(ContinuePanel(read=self.can_read()))
        elif kind == "own_words":
            self.fold()
            self.say(cards.card("tutor", "In your own words", act["prompt"]))
            self.panel(TextPanel("One or two sentences. Esc to skip.", done_label=None))
        elif kind == "stuck":
            self.say(cards.card("hint", "Not clicked yet", act["say"]))
            self.readable_now(act["say"], auto=True)
            buttons = [("continue", "Move on ⏎")] + ([("talk", "Talk it through with the tutor (AI)")]
                                                     if self.ai_ok() else [])
            self.panel(ContinuePanel(buttons=buttons))
        elif kind == "end":
            self.finish()
        else:
            self.say(cards.card("bad", "Unexpected step", str(act)))
            self.panel(ContinuePanel(buttons=[("home", "Back to menu ⏎")]))

    def ask_question(self, view: dict, say: str | None = None) -> None:
        self.view = view
        self.fold()
        if say:
            self.say(cards.note(say, "dim"))
        card = self.say(cards.question(view))
        self.readable_now(view.get("stem", ""))  # ctrl+e reads the question; it is never read by itself
        self.query_one("#log", VerticalScroll).call_after_refresh(self._show_top, card)  # after say's scroll_end
        self.answer_panel(view)

    def _show_top(self, card: Static) -> None:
        """A question taller than the log opens at its start, not its end (alt+↑ alt+↓ scroll the rest)."""
        log = self.query_one("#log", VerticalScroll)
        if card.is_attached and card.outer_size.height > log.scrollable_content_region.height:
            log.scroll_to_widget(card, top=True, animate=False, immediate=True)

    def action_scroll_log(self, direction: int) -> None:
        """alt+↑ / alt+↓: the log a page at a time, keeping a line of what was on screen; works while typing."""
        log = self.query_one("#log", VerticalScroll)
        log.scroll_relative(y=direction * max(1, log.scrollable_content_region.height - 1), animate=False)

    def answer_panel(self, view: dict) -> None:
        checking = model.knobs(self.tutor.state)["checking_routine"]
        self.hint_armed = False
        if view["kind"] == "mcq":
            self.panel(ChoicePanel(view["n"], view.get("options")))
        elif view["kind"] == "structured":
            self.panel(LongPanel(view["n"], checking=checking))
        else:
            self.panel(ValuePanel(view["n"], view["kind"], checking=checking))

    def respond(self, data: dict) -> None:
        if (self.tutor.session or {}).get("awaiting"):
            self.tutor.respond(data)

    # ---------- panel results ----------
    @on(Panel.Done)
    def panel_done(self, event: Panel.Done) -> None:
        if event.panel is not getattr(self, "showing", None):  # queued on a panel already replaced (key repeat): once only
            return
        data, kind = event.data, self.act.get("activity")
        if data.get("button") == "read":
            self.action_read_aloud()
            return
        if isinstance(event.panel, LongPanel):
            self.long_written(data)
            return
        if isinstance(event.panel, ReflectPanel):
            if data.get("remark"):
                self.followups.insert(0, "reflect")  # asked again if the mark stands
                self.remark()
                return
            if data.get("code") and getattr(self, "last_fb", {}).get("event"):
                self.tutor.tag(self.last_fb["event"], data["code"])
                self.say(cards.note(f"Noted: {ReflectPanel.CODES[data['code']].lower()}.", "dim"))
            self.next_followup()
            return
        if data.get("button") == "breakok":
            self.next_followup()
            return
        if data.get("button") == "leave":
            self.action_leave()
            return
        if data.get("button") == "home":
            self.app.pop_screen()
            return
        if "entry" in data:
            self.submit(data)
        elif kind == "choose":
            self.say(cards.you(GOALS.get(data["choice"], data["choice"])))
            self.respond({"choice": data["choice"]})
            self.advance()
        elif kind == "plan":
            self.respond({"teach": data["ticked"]})
            self.prepare_cards(data["ticked"])
            self.advance()
        elif kind in ("worked", "walkthrough") and "step" in data:
            st = self.act["steps"][data["step"] - 1]
            if data.get("guess"):
                self.say(cards.you(data["guess"]))
            self.say(cards.card("tutor", f"Step {data['step']}", f"{st['do']}\n\n_{st.get('why', '')}_"))
            self.readable_now([f"Step {data['step']}.", st["do"], st.get("why", "")])
            self.respond({"step": data["step"]})
            if data["step"] >= len(self.act["steps"]):  # the last step is the answer: wait for the learner, do not move on
                self.panel(ContinuePanel("That was the last step. Read it through, then continue.", read=self.can_read()))
        elif kind in ("worked", "walkthrough") and data.get("done"):
            self.respond({"done": True})
            self.advance()
        elif kind == "own_words":
            if data.get("text"):
                self.say(cards.you(data["text"]))
                self.tutor.show("you", data["text"], "In your own words")
                self.respond({"text": data["text"]})
                if self.app.settings.own_words_feedback and self.ai_ok():
                    self.panel(ContinuePanel("The tutor is reading your explanation…", buttons=[]))
                    self.stream(prompts.own_words(self.tutor, self.kc, data["text"]), then_continue=True, mode="explain")
                    return
            else:
                self.respond({})
            self.advance()
        elif kind == "stuck" and data.get("button") == "talk":
            self.chatting = True
            blocks = (self.tutor.session or {}).get("blocks", [])
            idx = self.act.get("block_idx")
            mistakes = blocks[idx].get("mistakes", []) if idx is not None and idx < len(blocks) else []
            self.stream(prompts.stuck(self.tutor, self.kc, mistakes))
            self.panel(TextPanel("Reply to the tutor (⏎ to send). Press the button when you're ready to move on.",
                                 done_label="I'm ready to move on"))
        elif self.chatting and data.get("text"):
            self.say(cards.you(data["text"]))
            self.stream(f"{prompts.context(self.tutor, self.kc)}\n\nSTUDENT: {data['text']}")
        elif self.chatting and (data.get("done") or data.get("skip")):
            self.chatting = False
            self.respond({})
            self.advance()
        elif data.get("button") == "explain":
            self.action_explain()
        elif data.get("button") == "ask":
            self.action_ask()
        elif data.get("button") == "why":
            self.stream(prompts.ask(self.tutor, "Explain clearly why the answer to the question just marked is right, "
                                    "and what the common wrong answer gets wrong.", self.kc), mode="explain")
        elif data.get("button") == "remark":
            self.remark()
        elif data.get("button") in ("next", "continue"):
            self.respond({})
            self.advance()
        elif "ticked" in data:  # long answer self-marking
            self.long_marks(data)

    def submit(self, data: dict) -> None:
        t = self.tutor
        view = self.view or {}
        out = t.answer(data["entry"])
        if out.get("ok") is False:
            self.app.notify(out["error"], severity="error")
            return
        if len(out["results"]) > 1:
            self.app.notify("Your answer was read as several parts. Please avoid commas between numbers and try again.",
                            severity="warning", timeout=7)
        r = out["results"][0]
        if r.get("error"):
            self.app.notify(r["error"], severity="warning", timeout=6)
            self.answer_panel(view)
            return
        if r.get("pending_judgement"):
            self.judge_short(view, data, r)
            return
        if data.get("note"):
            self.say(cards.you("✎ " + data["note"]))
            if (log := t._lesson_log()):
                log.you(f"Note on Q{view.get('n')}: {data['note']}")
        self.say(cards.feedback(r, data.get("your", "")))
        self.readable_now(spoken_feedback(r, data.get("your", "")), auto=True)
        self.last_fb = r
        self.followups = (["reflect"] if r.get("reflect") else []) + (["break"] if r.get("break_suggested") else [])
        self.next_followup()

    def can_remark(self) -> bool:
        """Whether the answer just marked can go to the AI examiner: one you gave (not "I don't know"), which the
        program marked wrong or docked a mark, and which has not been re-marked."""
        fb = getattr(self, "last_fb", None) or {}
        return bool(self.ai_ok() and fb.get("event") and not fb.get("correct") and not fb.get("remarked")
                    and fb.get("response") != "don't know"
                    and (self.view or {}).get("kind") in ("mcq", "numeric", "expression", "short"))

    def next_followup(self) -> None:
        """After feedback: why-did-I-miss-it, then a break suggestion if due, then the usual continue buttons."""
        step = self.followups.pop(0) if getattr(self, "followups", None) else None
        if step == "reflect":
            self.panel(ReflectPanel(bool(self.last_fb.get("slip_likely")), remark=self.can_remark()))
        elif step == "break":
            self.say(cards.card("hint", "Time for a short break?",
                                "Your accuracy has dipped below what's normal for you. A 5-minute break (water, stretch, "
                                "no phone) helps you feel fresher. Your place is saved either way."))
            self.panel(ContinuePanel(buttons=[("breakok", "Keep going ⏎"), ("leave", "Save and stop for now")]))
        else:
            buttons = [("next", "Next ⏎")] + ([("why", "Explain this answer (AI)")] if self.ai_ok() else []) + \
                      ([("remark", "Re-mark (AI)")] if self.can_remark() else []) + [("ask", "Ask the tutor (ctrl+t)")]
            self.panel(ContinuePanel(buttons=buttons, read=self.can_read()))

    # ---------- written answers ----------
    @work(exclusive=True, group="judge")
    async def judge_short(self, view: dict, data: dict, pending: dict) -> None:
        n = view["n"]
        points = pending.get("rubric", [])
        if self.ai_ok():
            self.panel(ContinuePanel("Checking your wording against the mark points…", buttons=[]))
            model, think = self.app.settings.ai_for("mark")
            res, _ = await self.app.ai.one_shot(prompts.judge(view.get("stem", ""), points, data.get("your", "")),
                                                schema=prompts.JUDGE, model=model, think=think, **spoken_too(self.app))
            if res and res.get("points"):
                met = sum(1 for p in res["points"] if p.get("met"))
                score = met / max(1, len(points))
                out = self.tutor.answer(data["entry"], judge={n: score})
                fb = out["results"][0]
                fb["explanation"] = (res.get("feedback", "") + "\n\n" + "\n".join(
                    f"- {'✓' if p.get('met') else '✗'} {p.get('point', '')}" for p in res["points"])).strip()
                self.say(cards.feedback(fb, data.get("your", "")))
                self.readable_now(spoken_feedback(fb, data.get("your", ""), res.get("speech") or None), auto=True)
                self.panel(ContinuePanel(buttons=[("next", "Next ⏎"), ("ask", "Ask the tutor (ctrl+t)")],
                                         read=self.can_read()))
                return
        self.pending_short = (n, data, max(1, len(points)))
        self.panel(TickPanel("Mark yourself: tick each point your answer really contains (space), then ctrl+s, or ⏎ on Done.",
                             [(p, str(i), False) for i, p in enumerate(points)], [("self", "Done ⏎")]))

    def long_marks(self, data: dict) -> None:
        if getattr(self, "pending_short", None):
            n, d, total = self.pending_short
            self.pending_short = None
            out = self.tutor.answer(d["entry"], judge={n: len(data["ticked"]) / total})
            self.say(cards.feedback(out["results"][0], d.get("your", "")))
            self.readable_now(spoken_feedback(out["results"][0], d.get("your", "")), auto=True)
            self.panel(ContinuePanel(buttons=[("next", "Next ⏎"), ("ask", "Ask the tutor (ctrl+t)")]))
            return
        n = self.view["n"]
        if data.get("button") == "ai":
            self.ai_check_long(data)
            return
        out = self.tutor.answer(f"{n} pts=" + ",".join(data["ticked"]) if data["ticked"] else f"{n} pts=")
        fb = out["results"][0]
        self.say(cards.feedback(fb, f"{len(data['ticked'])} mark point(s) claimed"))
        self.readable_now(spoken_feedback(fb), auto=True)
        self.panel(ContinuePanel(buttons=[("next", "Next ⏎"), ("ask", "Ask the tutor (ctrl+t)")]))

    def long_written(self, data: dict) -> None:
        text = data.get("text", "")
        self.long_text = text
        self.say(cards.you(text))
        self.tutor.show("you", text, "Your working")
        if (log := self.tutor._lesson_log()):  # the transcript keeps your working, even if you leave before marking
            log.you(f"Working for Q{self.view['n']}:\n\n{text}")
        sch = self.tutor.scheme(self.view["n"])
        self.scheme = sch.get("scheme", [])
        buttons = [("mine", "Submit my marks ⏎")] + ([("ai", "Ask the AI examiner to check")] if self.ai_ok() else [])
        self.mark_panel("Tick every mark point your answer earns (space), then ctrl+s. Honest self-marking is great practice.",
                        (), buttons)

    def mark_panel(self, prompt: str, ticked, buttons: list[tuple[str, str]]) -> None:
        self.panel(TickPanel(prompt, [(f"{p.get('mark', '')} {p.get('point', '')}", str(p["i"]), str(p["i"]) in ticked)
                                      for p in self.scheme], buttons))

    @work(exclusive=True, group="judge")
    async def ai_check_long(self, data: dict) -> None:
        self.panel(ContinuePanel("The AI examiner is marking your answer…", buttons=[]))
        points = [f"{p.get('mark', '')} {p.get('point', '')}" for p in self.scheme]
        model, think = self.app.settings.ai_for("mark")
        res, r = await self.app.ai.one_shot(prompts.judge(self.view.get("stem", ""), points, self.long_text),
                                            schema=prompts.JUDGE, model=model, think=think, **spoken_too(self.app))
        if not res:  # give the tick list back, with your ticks, so you can still mark it yourself
            self.say(cards.card("hint", "AI check unavailable", r.message or "Mark it yourself."))
            self.mark_panel("Tick every mark point your answer earns (space), then ctrl+s to submit.", data["ticked"],
                            [("mine", "Submit my marks ⏎")])
            return
        verdict = "\n".join(f"- {'✓' if p.get('met') else '✗'} {p.get('point', '')}: {p.get('why', '')}"
                            for p in res.get("points", []))
        self.say(cards.ai(f"{res.get('feedback', '')}\n\n{verdict}", "AI examiner"))
        self.readable_now(res.get("speech") or f"{res.get('feedback', '')}\n\n{verdict}", auto=True,
                          limit=tts.AI_SPEECH_LIMIT)
        met = {str(self.scheme[i]["i"]) for i, p in enumerate(res.get("points", [])) if p.get("met") and i < len(self.scheme)}
        ticked = sorted(set(data["ticked"]) | met) if data["ticked"] else sorted(met)
        self.mark_panel("Adjust if you disagree, then ctrl+s to submit.", ticked, [("mine", "Submit ⏎")])

    @work(exclusive=True, group="judge")
    async def remark(self) -> None:
        """A second marker for an answer the program marked wrong. It matches units, forms and wording narrowly, and
        an answer key can be wrong; if the AI examiner finds the answer right, it counts as right from then on."""
        fb, view = self.last_fb, self.view or {}
        self.panel(ContinuePanel("The AI examiner is checking the marking…", buttons=[]))
        res, r = await self.app.ai.one_shot(prompts.remark(view, fb), schema=prompts.REMARK, model=prompts.REMARK_MODEL, think=True,
                                            **spoken_too(self.app))
        if res:
            fb["remarked"] = True  # one re-mark an answer; a call that failed can be tried again
            self.readable_now(["Re-marked: correct." if res.get("correct") is True else "Re-marked: the mark stands.",
                               res.get("speech") or res.get("why", "")], auto=True)
        out = self.tutor.regrade(fb["event"], res.get("why", "")) if res and res.get("correct") is True else {}
        if out.get("ok"):
            self.last_fb = {**(out.get("feedback") or {**fb, "correct": True, "partial": False}), "remarked": True}
            self.followups = ["break"] if self.last_fb.get("break_suggested") else []  # nothing was missed
            self.say(cards.card("tutor", "Re-marked: correct ✓",
                                f"{res.get('why', '')}\n\nIt now counts as right in your record."))
            self.tutor.show("ai", f"{res.get('why', '')}\n\nIt now counts as right in your record.", "Re-marked: correct ✓")
        elif res:
            self.say(cards.card("hint", "Re-marked: the mark stands", res.get("why", "")))
            self.tutor.show("ai", res.get("why", ""), "Re-marked: the mark stands")
            if (log := self.tutor._lesson_log()):
                log.tutor(res.get("why", ""), title=f"Q{fb.get('n')} re-marked: the mark stands")
        else:
            self.say(cards.card("hint", "AI check unavailable", r.message or "Try again later."))
            self.tutor.show("notice", r.message or "Try again later.", "AI check unavailable")
        self.update_bar()
        self.next_followup()

    # ---------- AI ----------
    def ai_ok(self) -> bool:
        return self.app.settings.ai and self.app.ai.available

    def stream(self, prompt: str, then_continue: bool = False, mode: str = "ask") -> None:
        if not self.ai_ok():
            a = self.app.ai
            msg = a.message or ("AI is switched off in Settings." if not self.app.settings.ai else "AI is unavailable.")
            self.say(cards.card("hint", "AI help is off", msg))
            self.tutor.show("notice", msg, "AI help is off")
            if then_continue:
                self.panel(ContinuePanel(buttons=[("continue", "Continue ⏎")]))
            return
        if (help_ := self.tutor.ai_help(given=False)).get("refused"):  # not allowed while a no-help check is open
            self.say(cards.card("hint", "No help on this one", help_["refused"]))
            self.tutor.show("notice", help_["refused"], "No help on this one")
            if then_continue:
                self.panel(ContinuePanel(buttons=[("continue", "Continue ⏎")]))
            return
        self._stream(prompt, then_continue, mode)

    @work(exclusive=True, group="ai")
    async def _stream(self, prompt: str, then_continue: bool, mode: str = "ask") -> None:
        a = self.app.ai
        w = self.say(cards.ai("…"))
        buf = ""
        # guard every open question (normally just the one on screen; a session begun in the chat may hold more)
        keys = [prompts.key_of(self.tutor, int(n)) for n in (self.tutor.session or {}).get("presented", {})]
        model, think = self.app.settings.ai_for(mode)  # chosen in Settings for this kind of help
        async for chunk in a.stream(prompt, image=prompts.focus_image(self.tutor), model=model, think=think):
            buf += chunk
            if not keys:
                w.update(cards.ai(buf))
                self.query_one("#log", VerticalScroll).scroll_end(animate=False)
        speech = a.last.speech if a.last.ok else ""
        buf = (a.last.text or buf) if a.last.ok else buf  # whole and tidy: a code fence the spoken line opened is gone
        withheld = any(ai_mod.leaks(buf, *k) or (speech and ai_mod.leaks(speech, *k)) for k in keys)
        if withheld:
            buf = "I can't give that away while the question is open. Try a hint (h), or answer first and I'll explain."
            speech = ""
        if not a.last.ok:
            w.update(cards.card("hint", "AI paused", a.last.message))
            self.tutor.show("notice", a.last.message, "AI paused")
        else:
            w.update(cards.ai(buf))
            self.readable_now(speech or buf, auto=True, limit=tts.AI_SPEECH_LIMIT)
            if buf and not withheld:
                self.tutor.ai_help()  # help that reached you counts as a hint on every open question
            if (log := self.tutor._lesson_log()):
                log.tutor(buf, title="Tutor (AI)")
            self.tutor.show("notice" if withheld else "ai", buf, "Held back" if withheld else "Tutor (AI)")  # and on Now
        self.update_bar()
        if then_continue:
            self.panel(ContinuePanel(buttons=[("continue", "Continue ⏎"), ("ask", "Ask the tutor (ctrl+t)")],
                                     read=self.can_read()))

    def prepare_cards(self, kcs: list[str]) -> None:
        """Ideas without a pre-built teaching card get one written by AI in the background (once, then cached)."""
        from tutorlib import lesson
        todo = [k for k in kcs if lesson.teach_card(self.tutor, k).get("source") == "offline"]
        if todo and self.ai_ok():
            self._write_cards(todo)

    @work(exclusive=False, group="cards")
    async def _write_cards(self, kcs: list[str]) -> None:
        import json
        for kc in kcs:
            data, _ = await self.app.ai.one_shot(prompts.teach_card(self.tutor, kc), schema=prompts.CARD)
            if data and all(data.get(f) for f in ("motivate", "establish", "note")):
                p = self.app.vault / ".tutor" / "cache" / "teach" / f"{kc}.json"
                try:
                    p.parent.mkdir(parents=True, exist_ok=True)
                    p.write_text(json.dumps({**data, "source": "ai"}, ensure_ascii=False, indent=1))
                except OSError:  # a vault that cannot be written: the card is simply not cached
                    pass

    # ---------- key actions ----------
    def action_ask(self) -> None:
        def got(q: str | None) -> None:
            if q:
                self.say(cards.you(q))
                if (log := self.tutor._lesson_log()):
                    log.you(q)
                self.tutor.show("you", q, "You asked")
                self.stream(prompts.ask(self.tutor, q, self.kc))
        self.app.push_screen(AskScreen(), got)

    def action_explain(self) -> None:
        if self.kc:
            self.tutor.show("you", "Explain this idea again, a different way.", "You asked")
            self.stream(prompts.explain_again(self.tutor, self.kc), mode="explain")

    def action_hint(self) -> None:
        if not self.view:
            return
        if str(self.view["n"]) not in (self.tutor.session or {}).get("presented", {}):  # answered: nothing to hint
            self.app.notify(f"No hint needed: Q{self.view['n']} is already marked.", timeout=4)
            return
        if model.knobs(self.tutor.state)["attempt_before_hint"] and not getattr(self, "hint_armed", False):
            self.hint_armed = True
            self.app.notify("Have a go first: write your first step or your best guess. Press h again for the hint.",
                            timeout=6)
            return
        h = self.tutor.hint(self.view["n"])
        if "refused" in h or h.get("error"):
            self.app.notify(h.get("refused") or h.get("error"), severity="warning")
        else:
            self.say(cards.card("hint", f"Hint {h.get('level', '')}", h.get("hint", "")))
            self.readable_now(h.get("hint", ""))  # ctrl+e reads it

    def action_obsidian(self) -> None:
        mac.open_in_obsidian(self.app.vault, "Now", background=False)

    def action_leave(self) -> None:
        leave_asking_first(self, "#panel TextArea")

    def action_esc(self) -> None:
        """Esc means "back" everywhere else; here a panel may use it (change an answer, skip), and leaving is ctrl+b."""
        self.hush()
        if time.monotonic() - getattr(self, "esc_told", -9.0) >= 4:  # said once while it shows, not a stack of them
            self.esc_told = time.monotonic()
            self.app.notify("ctrl+b saves and returns to the menu.", timeout=4)

    def finish(self) -> None:
        summary = self.tutor.end()
        try:
            from tutorlib import weekly
            # Today/Profile notes, experiments, Anki export when due
            summary["week"] = weekly.run(self.tutor, self.app.settings.minutes)
        except Exception as exc:  # bookkeeping must never cost you the session
            summary["week"] = {"error": str(exc)}
        self.app.switch_screen(SummaryScreen(summary))  # closing the summary lands back on the menu


# ============================ Summary / pop-ups ============================
class SummaryScreen(ModalScreen):
    BINDINGS = [Binding("enter", "close", "Back to menu"), Binding("escape", "dismiss(None)", "Back")]

    def __init__(self, summary: dict) -> None:
        super().__init__()
        self.summary = summary
        self.opened = time.monotonic()

    def action_close(self) -> None:
        if time.monotonic() - self.opened >= 0.7:  # not the ⏎ still held down from "Next ⏎": read it first
            self.dismiss(None)
        else:  # ignored, but visibly
            self.query_one("#summary-hint", Static).update("Press ⏎ again for the menu · ↑↓ scroll")

    def compose(self) -> ComposeResult:
        s = self.summary
        t = self.app.tutor
        acc = f"{round(100 * s['accuracy'])}%" if s.get("accuracy") is not None else "–"
        learned = "\n".join(f"- ✓ {t.packs.kcs[k]['title']}" for k in s.get("kcs_learned", []) if k in t.packs.kcs)
        due = model.due_kcs(t.state, t.now() + timedelta(days=1))
        a = self.app.ai
        today = t.study_clock.today(t.now().date().isoformat())
        text = (f"# Session done ✓\n\n**Answered:** {s['answered']}  ·  **Correct:** {s['correct']}  ·  **Accuracy:** {acc}\n\n"
                + (f"**Session time:** {clock.fmt(s['active_seconds'], True)} on the screen  ·  **True time:** "
                   f"{clock.fmt(s['true_seconds'], True)} from start to finish  ·  **Studied today:** {clock.fmt(today)}\n\n"
                   if "active_seconds" in s else "")
                + (f"## Learned today\n{learned}\n\n" if learned else "")
                + f"**Due for review by tomorrow:** {len(due)} idea(s)\n\n"
                + f"**AI replies this session:** {a.session.replies}\n\n"
                + (f"**New Anki cards ({(s.get('week') or {})['anki']['cards']}):** double-click "
                   f"`{(s.get('week') or {})['anki']['path']}` in the tutor folder to import them.\n\n"
                   if ((s.get("week") or {}).get("anki") or {}).get("path") else "")
                + "Your notes and the full lesson are in Obsidian (Home → Recent lessons).")
        with VerticalScroll(id="summary"):  # a short window scrolls it; the way out stays in sight
            yield Static("⏎ menu · ↑↓ scroll", id="summary-hint", classes="hint")
            yield Markdown(to_terminal(text))


class ConfirmScreen(ModalScreen):
    BINDINGS = [Binding("escape", "dismiss(None)", "Cancel")]

    def __init__(self, question: str, choices: list[tuple[str, str]]) -> None:
        super().__init__()
        self.question, self.choices = question, choices

    def compose(self) -> ComposeResult:
        with Vertical(id="ask"):
            yield Static(self.question, classes="hint")
            yield OptionList(*[Option(label, id=cid) for cid, label in self.choices], id="confirm")

    def on_mount(self) -> None:
        self.query_one("#confirm", OptionList).focus()

    @on(OptionList.OptionSelected, "#confirm")
    def chose(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(event.option.id)


class AskScreen(ModalScreen):
    BINDINGS = [Binding("escape", "dismiss(None)", "Cancel")]

    def compose(self) -> ComposeResult:
        with Vertical(id="ask"):
            yield Static("Ask the tutor anything: it knows what is on screen and the questions just marked. "
                         "⏎ sends, ctrl+j starts a new line, Esc cancels.", classes="hint")
            yield Composer(placeholder="e.g. what would the full answer be here?", id="q")

    def on_mount(self) -> None:
        self.query_one("#q", Composer).focus()

    @on(Composer.Submitted, "#q")
    def sent(self, event: Composer.Submitted) -> None:
        self.dismiss(event.value.strip() or None)


class ChatPanel(TextPanel):
    """The chat's box: Esc there goes back to the menu, and the footer says so."""
    BINDINGS = [Binding("escape", "skip", "Back")]


class ChatScreen(ReadAloud, Screen):
    studies = True

    """Free chat with the tutor from the menu."""
    BINDINGS = [Binding("escape", "leave", "Back to menu"), READ_KEY]

    def compose(self) -> ComposeResult:
        yield Static(Text(" Ask the tutor ", style=f"bold {C['badge_fg']} on {C['ai']}"), id="bar")
        yield VerticalScroll(id="log")
        with Container(id="panel"):
            yield ChatPanel("Type a question and ⏎. Esc returns to the menu.")
        yield Footer()

    def on_mount(self) -> None:
        self.app.tutor.clear_chat()  # a new chat: the Now page starts it afresh
        self.run_worker(self.app.ai.reset(), group="reset")  # chat never inherits a lesson's context

    def action_leave(self) -> None:
        leave_asking_first(self, "#panel Composer", "question")  # Esc and ctrl+q: not over a question half typed

    @on(Panel.Done)
    def sent(self, event: Panel.Done) -> None:
        if event.data.get("skip"):
            self.action_leave()
            return
        q = event.data.get("text", "")
        log = self.query_one("#log", VerticalScroll)
        log.mount(Static(cards.you(q), classes="entry"))
        self.app.tutor.show("you", q, "You asked")
        self.hush()
        self.reply(q)

    @work(exclusive=True)
    async def reply(self, q: str) -> None:
        a = self.app.ai
        log = self.query_one("#log", VerticalScroll)
        if not (self.app.settings.ai and a.available):
            log.mount(Static(cards.card("hint", "AI help is off", a.message or "Switch AI on in Settings."), classes="entry"))
            self.app.tutor.show("notice", a.message or "Switch AI on in Settings.", "AI help is off")
            return
        w = Static(cards.ai("…"), classes="entry")
        log.mount(w)
        buf = ""
        model, think = self.app.settings.ai_for("ask")
        async for chunk in a.stream(prompts.ask(self.app.tutor, q, None), model=model, think=think):  # with the last questions answered
            buf += chunk
            w.update(cards.ai(buf))
            log.scroll_end(animate=False)
        if not a.last.ok:
            w.update(cards.card("hint", "AI paused", a.last.message))
            self.app.tutor.show("notice", a.last.message, "AI paused")
        else:
            buf = a.last.text or buf
            w.update(cards.ai(buf))
            self.app.tutor.show("ai", buf, "Tutor (AI)")
            self.readable_now(a.last.speech or buf, auto=True, limit=tts.AI_SPEECH_LIMIT)


class InsightsScreen(Screen):
    """What the tutor knows about you: each finding with its evidence, how sure it is, and what it changed."""
    BINDINGS = [Binding("escape", "app.pop_screen", "Back"), Binding("a", "ai", "AI summary"),
                Binding("o", "open('Profile')", "Profile"), Binding("m", "open('Mistakes')", "Mistakes"),
                Binding("w", "weekly", "Last week")]

    def compose(self) -> ComposeResult:
        with VerticalScroll():
            yield Markdown(self._text(), id="insights")
        yield Footer()

    def _text(self) -> str:
        t = self.app.tutor
        return (self._for_terminal(report.insights_markdown(t, report.load_ai_summary(t))) + "\n---\n\n**a** asks the "
                "AI tutor to explain this in a few lines (one reply from today's allowance) · **o** opens it in "
                "Obsidian · **m** your mistake journal · **w** your latest week in review · **Esc** back")

    # the Profile note's colour emoji ⚪ 🟡 🟢 ✅ (Obsidian) as shapes: emoji draw two cells wide in a terminal
    PLAIN = str.maketrans({0x26AA: "○", 0x1F7E1: "◔", 0x1F7E2: "◑", 0x2705: "●"})

    READINESS = {"Exam": "Exam", "Date": "Date", "Ideas": "Ideas", "Secure": "Secure",
                 "If you stopped now": "Stop", "If you keep reviewing": "Review"}

    @classmethod
    def _for_terminal(cls, md: str) -> str:
        """The Profile note is written for Obsidian. Here: callout markers become a bold title, and the readiness
        table keeps the columns that fit a terminal, with shorter headings."""
        out, keep = [], None
        for line in md.splitlines():
            line = re.sub(r"^>\s*\[!\w+\][-+]?\s*(.*)$",
                          lambda m: f"> **{m.group(1)}**\n>" if m.group(1) else ">", line)
            if line.startswith("| Exam |"):
                heads = [c.strip() for c in line.strip("|").split("|")]
                keep = [i for i, h in enumerate(heads) if h in cls.READINESS]
                line = "| " + " | ".join(cls.READINESS[heads[i]] for i in keep) + " |"
            elif keep is not None and line.startswith("|"):
                cells = [c.strip() for c in line.strip("|").split("|")]
                line = "| " + " | ".join(cells[i].replace(" (estimated),", " (est.),") for i in keep
                                         if i < len(cells)) + " |"
            else:
                keep = None
            out.append(line)
        return to_terminal("\n".join(out)).translate(cls.PLAIN) + "\n"

    def action_ai(self) -> None:
        if not (self.app.settings.ai and self.app.ai.available):
            self.app.notify("The AI tutor is off or unavailable right now (Settings: F2 on the menu).",
                            severity="warning")
            return
        self.app.notify("Asking the AI tutor to explain your profile…", timeout=4)
        self._summarise()

    @work(exclusive=True, group="profile-ai")
    async def _summarise(self) -> None:
        from tutorlib.store import write_json
        t = self.app.tutor
        data, res = await self.app.ai.one_shot(prompts.profile_summary(report.insights_markdown(t)),
                                               schema=prompts.PROFILE)
        if not (data and data.get("summary")):
            self.app.notify(res.message or "The AI tutor couldn't write a summary just now.", severity="warning")
            return
        write_json(self.app.vault / ".tutor" / "profile_ai.json", {"text": data["summary"], "at": t.now().isoformat()})
        report.profile_note(t)
        self.query_one("#insights", Markdown).update(self._text())

    def action_open(self, note: str) -> None:
        {"Profile": report.profile_note, "Mistakes": report.mistakes_note}[note](self.app.tutor)
        mac.open_in_obsidian(self.app.vault, note, background=False)

    def action_weekly(self) -> None:
        folder = self.app.vault / "Weekly"
        weeks = sorted(folder.glob("*.md")) if folder.exists() else []
        if not weeks:
            self.app.notify("No week in review yet: the first appears when the tutor opens in a new week.", timeout=6)
            return
        mac.open_in_obsidian(self.app.vault, f"Weekly/{weeks[-1].stem}", background=False)


class ProgressScreen(Screen):
    BINDINGS = [Binding("escape", "app.pop_screen", "Back"), Binding("o", "open", "Open Profile in Obsidian")]

    def compose(self) -> ComposeResult:
        from tutorlib import profile
        t = self.app.tutor
        p = profile.summary(t.state, t.packs, t.now())
        rows = ["# My progress", ""]
        tips = profile.advice(p)
        rows += ["## What the tutor has noticed", ""] + ([f"- {x}" for x in tips] or
                                                        ["- Nothing definite yet: patterns show up after a few sessions."])
        rows += ["", "## Topics"]
        for group in views.subtopic_groups(t.packs):  # a table for each subject, a bold row for each chapter
            rows += ["", f"### {group['name']}", "", "| Subtopic | Secure | Learning | Gaps |", "|---|---|---|---|"]
            for chapter in group["chapters"]:
                rows.append(f"| **{chapter['name']}** | | | |")
                for sub in chapter["subs"]:
                    kcs = [k for k, v in t.packs.kcs.items() if v["subtopic"] == sub]
                    st = [views.kc_status(t.state, k) for k in kcs]
                    rows.append(f"| {sub} {t.packs.subtopics[sub]['title']} | {st.count('secure')}/{len(kcs)} | "
                                f"{st.count('learning')} | {st.count('gap')} |")
        cal = p["calibration"]
        if cal["levels"]:
            rows += ["", "## How sure vs how right", "", "| You said | Answers | Right |", "|---|---|---|"]
            rows += [f"| {lv['level']} | {lv['n']} | {lv['right']:.0%} |" for lv in cal["levels"]]
        h = p["habits"]
        rows += ["", "## Habits", "", f"- Streak: {h['streak']} day{'' if h['streak'] == 1 else 's'}; studied {h['last_28']} of the last 28 days.",
                 "- Reviews due in the next 7 days: " + " · ".join(
                     f"{'today' if i == 0 else f'{t.now() + timedelta(days=i):%a}'} {x}"
                     for i, x in enumerate(p["workload"])) + "."]
        with VerticalScroll():
            yield Markdown(to_terminal("\n".join(rows)))
        yield Footer()

    def action_open(self) -> None:
        from tutorlib import report
        report.profile_note(self.app.tutor)
        mac.open_in_obsidian(self.app.vault, "Profile", background=False)


class BlurtScreen(ReadAloud, Screen):
    studies = True

    """Free recall: write everything you remember, then see what you left out."""
    BINDINGS = [Binding("ctrl+s", "submit", "Check my blurt"), Binding("escape", "leave", "Back"), READ_KEY]

    def __init__(self, subtopic: str) -> None:
        super().__init__()
        self.subtopic = subtopic

    def compose(self) -> ComposeResult:
        t = self.app.tutor
        title = to_terminal(t.packs.subtopics[self.subtopic]["title"])
        yield Static(Text(f" Blurt · {self.subtopic} {title} ", style=f"bold {C['badge_fg']} on {C['badge_bg']}"), id="bar")
        with VerticalScroll(id="log"):
            yield Static(cards.card("tutor", "Write everything you remember",
                                    "Definitions, equations, units, examples, traps: anything about this topic. Don't "
                                    "look anything up. About **3 minutes** is plenty. Recalling is what strengthens memory; "
                                    "checking what you missed shows exactly what to review."), classes="entry")
        with Container(id="panel"):
            from textual.widgets import TextArea
            yield TextArea(id="blurt", soft_wrap=True)
            yield Button("Check my blurt (ctrl+s)", id="check", variant="primary")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#blurt").focus()

    def action_leave(self) -> None:
        leave_asking_first(self, "#blurt")  # once checked, the blurt is saved and the box is gone

    @on(Button.Pressed, "#check")
    def action_submit(self) -> None:
        from textual.widgets import TextArea
        from tutorlib import lesson
        boxes = self.query("#blurt")
        text = boxes.first(TextArea).text.strip() if boxes else ""
        if not text or getattr(self, "checked", False):  # a second ctrl+s or click while the box is going: once only
            return
        self.checked = True
        self.query_one("#check", Button).disabled = True
        t = self.app.tutor
        res = t.blurt(self.subtopic, text)
        log = self.query_one("#log", VerticalScroll)
        n, total = len(res["recalled"]), len(res["ideas"])
        log.mount(Static(cards.you(text, "You wrote"), classes="entry"))  # beside what it is checked against
        log.mount(Static(cards.card("good" if n == total else "hint", f"You recalled {n} of {total} ideas",
                                    "Ideas you left out are now due for review, so they come up next time."),
                         classes="entry"))
        for kc, v in res["ideas"].items():
            note = ("You remembered this." if v["recalled"] else  # a line, not an empty box under the title
                    lesson.teach_card(t, kc).get("note", "") or "You left this out.")
            log.mount(Static(cards.card("good" if v["recalled"] else "bad",
                                        f"{'✓' if v['recalled'] else '✗'} {v['title']}", note), classes="entry"))
        log.scroll_end(animate=False)
        left_out = [v["title"] for v in res["ideas"].values() if not v["recalled"]]
        self.readable_now(f"You recalled {n} of {total} ideas."
                          + (" You left out: " + "; ".join(left_out) + "." if left_out else ""), auto=True)
        box = self.query_one("#panel", Container)
        box.remove_children()
        box.mount(Static("Esc for the menu. Your blurt and results are saved in Lessons in Obsidian.", classes="hint"))


class HelpScreen(ModalScreen):
    BINDINGS = [Binding("escape", "dismiss(None)", "Close"), Binding("enter", "dismiss(None)", "Close"),
                Binding("o", "guide", "Open the full guide")]

    def compose(self) -> ComposeResult:
        text = """_↑↓ to scroll · Esc or ⏎ closes_
# Keys
**↑ ↓** move · **⏎** choose / continue · **A–D** pick an option · **0** I don't know · **1–4** confidence
(1 guess, 2 unsure, 3 fairly sure, 4 certain) · **space** tick a box

**ctrl+k** (or **F3**) answer-only view: hides the question and shows just the answer box, for a window beside
Obsidian; press it again to bring the question back · **ctrl+t** ask the tutor (AI) · **ctrl+r** explain this idea again, differently (AI) · **ctrl+g** hint (not on
no-hints checks) · **ctrl+o** show the current question or explanation in Obsidian · **ctrl+l** bring back what
was said earlier (after you answer) · **ctrl+e** read aloud what is on screen, and again stops it (once set up:
`tutor tts setup`) · **ctrl+b** or **ctrl+q** save and go back to the menu. These work even while
you are typing; when you are not typing, **t e h o** do the same. **alt+↑ alt+↓** scroll a long question or
explanation, even while you type.

Choosing a topic: folders for **Chemistry**, **Physics** and **Maths**, each holding a folder per chapter (Maths: per
module) with the subtopics inside. **⏎** opens a folder, **Esc** or **←** goes up. **Just start typing** to search every
folder at once (a word, or a code such as 9702-3 or P1; Esc clears it). In test prep **space** ticks (on a folder: all in it),
**ctrl+a** ticks everything shown, **ctrl+d** clears.

What the terminal shows is on the **Now** page in Obsidian too: your questions to the AI, its replies, hints.

Typing: **⏎** sends a short answer · **ctrl+j** starts a new line · **ctrl+s** submits a long answer or a blurt.

**?** this help · **F2** settings · **q** quit (from the menu)

# Challenge (menu)
Hard calculation questions written by AI for fun: multiple choice, or typed answers with no hints. Set it up in
words in the top box and **⏎**, e.g. _15 questions on 9702-5.1, start easy, jump to hard fast, end extreme, opus_ or
_mostly typed, level 6 to 9, hardest first_, or with the list: **↑↓** and **⏎** to change a setting, **← →** to step
it. The whole set is written and checked first; **Esc** cancels while it is being written, and goes back to the menu
otherwise (your answers are saved, and the set carries on next time). It does not affect your reviews or progress.

# Shortcuts (menu)
**Shortcuts** teaches quicker, more elegant methods one at a time: a card each for the pain, when to use it, the idea,
why it works, steps, a worked example, pitfalls and a check, then practice, then you rate how well you grasped it
(**1** again to **4** easy). **⏎** or **space** shows the next card, **←** or **Esc** goes back, **ctrl+g** gives a
practice hint. **Shortcut recall** asks the ones that are due, on its own schedule. Press **s** on either to choose
the ratings, subjects, level, sections and how many new ones a day. Neither affects your syllabus reviews or progress.

# Where to look
Keep **Obsidian** open beside this window on **Now** (the current question in full, with figures) — your
**My Notes** for the topic grow underneath as you learn. Every session is saved in **Lessons**, a folder for each day.

The full plain-English guide is **How It Works** in Obsidian (press **o** now).
"""
        with VerticalScroll(id="help"):
            yield Markdown(text)

    def action_guide(self) -> None:
        mac.open_in_obsidian(self.app.vault, "How It Works", background=False)


MODEL_CHOICES = [("Model: Haiku (fast, least usage)", "haiku"), ("Model: Sonnet (clearer, ~3x)", "sonnet"),
                 ("Model: Opus (strongest, ~5x)", "opus")]


class SettingsScreen(ModalScreen):
    BINDINGS = [Binding("escape", "dismiss(None)", "Close")]

    def compose(self) -> ComposeResult:
        s = self.app.settings
        with VerticalScroll(id="settings"):  # a short window scrolls to Save instead of cutting it off
            yield Static("Settings (saved in your tutor folder)", classes="title")
            for key, label in (("ai", "AI tutor (asking, explaining, judging written answers)"),
                               ("own_words_feedback", "AI comments on your 'in your own words' answers"),
                               ("open_obsidian", "Show Now in Obsidian when a session starts"),
                               ("answer_only", "Answer-only view: hide the question here, show just the answer box (ctrl+k)")):
                with Horizontal(classes="row"):
                    yield Switch(value=getattr(s, key), id=key)
                    yield Static(label)
            yield Static("AI for each kind of help: the model, and whether it thinks first. Haiku without thinking "
                         "is fastest and uses least of your limit; Sonnet about 3x, Opus about 5x; thinking first is "
                         "slower and can use several times as much again.", classes="hint")
            for mode, label in (("mark", "Marking answers"), ("explain", "Explaining"), ("ask", "Ask the tutor")):
                model, think = s.ai_for(mode)
                with Horizontal(classes="row ai-row"):
                    yield Switch(value=think, id=f"ai_{mode}_think")
                    yield Static(f"{label}: think first")
                    yield Select(MODEL_CHOICES, value=model, id=f"ai_{mode}_model", allow_blank=False, compact=True)
            with Horizontal(classes="row"):
                yield Select([(f"Look: {look.LABELS[name]}", name) for name in config.THEMES],
                             value=s.theme, id="theme", allow_blank=False, compact=True)
            with Horizontal(classes="row"):
                yield Static("Session length (minutes, 5 to 180)")
                yield Input(str(s.minutes), id="minutes", type="integer", compact=True)
            for key, label in (("tts_enabled", "Read aloud with Kokoro: ctrl+e (set up once: tutor tts setup)"),
                               ("tts_auto", "Read explanations, feedback and AI replies by themselves")):
                with Horizontal(classes="row"):
                    yield Switch(value=getattr(s, key), id=key)
                    yield Static(label)
            with Horizontal(classes="row"):
                yield Select([(f"Voice: {label}", name) for name, label in tts.VOICES.items()]
                             + ([] if s.tts_voice in tts.VOICES else [(f"Voice: {s.tts_voice}", s.tts_voice)]),
                             value=s.tts_voice, id="tts_voice", allow_blank=False, compact=True)
            with Horizontal(classes="row"):
                yield Static("Reading speed (0.8 to 1.3)")
                yield Input(f"{s.tts_speed:g}", id="tts_speed", type="number", compact=True)
            with Horizontal(classes="row"):
                yield Static("Voice loudness (10 to 100 %)")
                yield Input(f"{round(s.tts_volume * 100)}", id="tts_volume", type="integer", compact=True)
                yield Button("▸ Hear it", id="tts_test", compact=True)
            with Horizontal(classes="row", id="save-row"):  # docked: Save and its hint stay in view in a short window
                yield Button("Save", id="save", variant="primary")
                yield Static("Save to apply · Esc cancels", id="settings-hint", classes="hint")

    def on_mount(self) -> None:
        self._fit()
        self.query_one("#ai", Switch).focus()  # the first setting, not the scrolling box around them

    def on_resize(self) -> None:
        self._fit()

    def _fit(self) -> None:
        """A short window gets tighter rows and a one-line Save, so everything fits and Save is never cut off."""
        short = self.app.size.height < 30
        self.set_class(short, "short")
        self.set_class(bool(C["frame"]), "flat")  # Night and Day: a quieter switch, the same width when focused
        self.query_one("#save", Button).compact = short

    def _typed_volume(self) -> float | None:
        """The loudness typed in the box, as a fraction (10 to 100 % allowed); None when it is not a number."""
        try:
            percent = int(self.query_one("#tts_volume", Input).value)
        except ValueError:
            return None
        return min(1.0, max(0.1, percent / 100))

    @on(Button.Pressed, "#tts_test")
    def hear_it(self) -> None:
        """Say a short line at the loudness typed, before saving it, so it can be judged by ear."""
        volume = self._typed_volume()
        if volume is None:
            self.app.notify("Type a loudness from 10 to 100 first.", timeout=5)
            return
        if self.app.speaker.sample(volume):
            self.app.notify(f"Playing at {round(volume * 100)} %.", timeout=3)

    @on(Button.Pressed, "#save")
    def save(self) -> None:
        s = self.app.settings
        old_speech = s.tts_enabled
        for key in ("ai", "own_words_feedback", "open_obsidian", "answer_only", "tts_enabled", "tts_auto"):
            setattr(s, key, self.query_one(f"#{key}", Switch).value)
        s.tts_voice = str(self.query_one("#tts_voice", Select).value)
        try:
            s.tts_speed = round(min(tts.SPEED_RANGE[1], max(tts.SPEED_RANGE[0],
                                                           float(self.query_one("#tts_speed", Input).value))), 2)
        except ValueError:  # blank: the speed you had stays
            pass
        if (volume := self._typed_volume()) is not None:
            s.tts_volume = round(volume, 2)  # blank or not a number: the loudness you had stays
        old_model, typed = s.model, self.query_one("#minutes", Input).value.strip()
        for mode in config.AI_MODES:
            setattr(s, f"ai_{mode}_model", str(self.query_one(f"#ai_{mode}_model", Select).value))
            setattr(s, f"ai_{mode}_think", self.query_one(f"#ai_{mode}_think", Switch).value)
        s.model = s.ai_explain_model  # the general choice, for what has no row of its own (teaching cards, the profile summary)
        old_theme, s.theme = s.theme, str(self.query_one("#theme", Select).value)
        try:
            s.minutes = min(180, max(5, int(typed)))
        except ValueError:  # blank or not a number: the length you had stays
            self.app.notify(f"Session length kept at {s.minutes} minutes.", timeout=5)
        else:
            self.app.notify(f"Session length set to {s.minutes} minutes"
                            + (" (5 to 180)." if str(s.minutes) != typed else "."), timeout=5)
        s.save(self.app.vault)
        self.app.ai.model, self.app.ai.think = s.ai_for("ask")  # the conversation started ahead is the one asked most
        speech = self.app.speech_wanted()
        if s.tts_enabled and not old_speech and not tts.available(self.app.vault):
            self.app.notify(tts.SETUP_HINT, timeout=8)
        if not s.tts_enabled:
            self.app.speaker.stop()
        if s.model != old_model or speech != self.app.ai.speech:
            self.app.ai.speech = speech  # the spoken version is asked for in the brief: a fresh process takes it
            self.run_worker(self.app.ai.reset(), group="reset")
        if s.theme != old_theme:
            look.apply(self.app, s.theme)  # the menu underneath redraws in it as this closes
        self.app.apply_answer_only()
        self.dismiss(None)
