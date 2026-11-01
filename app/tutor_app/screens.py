"""Main study screens and shared screen helpers; dialogs are re-exported for compatibility."""
from __future__ import annotations

import asyncio
import copy
import hashlib
from tutorlib.card_diagrams import diagram_descriptions
import json
import re
import textwrap
import time
from datetime import date, datetime, timedelta
from time import monotonic

from rich.text import Text
from rich.spinner import Spinner
from rich.segment import Segment
from rich.style import Style
from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen, Screen
from textual.strip import Strip
from textual.widgets import Button, Collapsible, Footer, Input, Markdown, OptionList, Select, SelectionList, Static, Switch
from textual.widgets.option_list import Option
from textual.widgets.selection_list import Selection

from tutorlib import almanac, clock, insights, lesson, model, policy, report, teach_actions as ta, views
from tutorlib.lesson import GOALS

from . import ai as ai_mod
from . import cards, codex_models, config, learn_reply, learn_write, local_models, look, mac, presets, prompts, tts
from . import __version__
from .dialogs import AskScreen, ConfirmScreen, SummaryScreen
from .look import C
from .panels import (ChoicePanel, ChoosePanel, Composer, Confidence, ContinuePanel, LessonPanel, LongPanel, Panel,
                     ReflectPanel, TextPanel, TickList, TickPanel, ValuePanel, WorkedPanel)
from .texmath import to_terminal
from .output_format import normalise_visual, terminal_visual


def bar(done: int, total: int, width: int = 12) -> str:
    fill = round(width * done / max(1, total))
    return "█" * fill + "░" * (width - fill)


def leave_asking_first(screen: Screen, boxes: str, typed: str = "answer", unsaved: bool = False) -> None:
    """Back to the previous screen, but not over something typed without asking: it would be lost."""
    if not unsaved and not any(w.text.strip() for w in screen.query(boxes)):
        screen.app.pop_screen()
        return

    def decided(choice: str | None) -> None:
        if choice == "leave" and screen.is_current:
            screen.app.pop_screen()
    screen.app.push_screen(ConfirmScreen(f"Leave? Your typed {typed} will be lost.",
                                         [("leave", "Leave"), ("stay", "Keep writing")]), decided)


def open_report_note(screen: Screen, note: str) -> None:
    """Refresh an explicitly requested report before showing it in Obsidian."""
    try:
        {"Profile": report.profile_note, "Mistakes": report.mistakes_note}[note](screen.app.tutor)
    except OSError as exc:
        screen.app.notify(f"{note} could not be updated: {exc}", severity="warning", timeout=8)
        return
    mac.open_in_obsidian(screen.app.vault, note, background=False)


def spoken_feedback(fb: dict, your: str = "", explanation: str | None = None) -> list[str]:
    """A marked answer as it is read aloud, in parts: the verdict and the answer, then why (maths is turned into
    words later). The question's own explanation is a part by itself, so its pre-generated audio is found."""
    if fb.get('attempt_saved'):
        return ['Your attempt is saved for marking after the other protected questions.']
    if fb.get('feedback_withheld'):
        return ['Feedback is saved until the skipped question has been attempted.']
    if fb.get("answer_withheld"):
        return ["Skipped. The answer is withheld."]
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


def image_for_local(tutor, model: str) -> dict:
    """Only local structured marking accepts the focused question's diagram."""
    return {"image": prompts.focus_image(tutor)} if local_models.is_local(model) else {}


class LocalActivity:
    """Honest, terminal-only activity for a local request; Claude keeps its existing display."""
    PHASES = {"preparing": "Preparing local model…", "loading": "Loading local model…",
              "queued": "Waiting for another local request…",
              "waiting": "Waiting for local model…", "thinking": "Thinking…", "generating": "Generating reply…",
              "reading_image": "Reading question image…", "searching": "Searching the web…",
              "done": "Finishing reply…", "error": "Local request stopped."}

    def __init__(self, screen: Screen, model: str | None, widget: Static | None = None, task: str = ""):
        self.screen, self.model, self.widget, self.task = screen, model, widget, task
        self.auxiliary = None  # answer-only hides the transcript; status still sits above the answer panel
        self.local, self.owns_widget = local_models.is_local(model), widget is None
        self.started, self.at, self.text, self.timer = time.monotonic(), 0.0, "", None
        self.live = cards.Live(widget) if widget is not None else None
        self.spinner = Spinner("dots", style=C["ai"])

    def __enter__(self):
        if not self.local:
            return self
        logs = self.screen.query("#log")
        hidden_log = bool(logs and not logs.first().display)
        if self.widget is None:
            self.widget = Static(classes="entry local-progress")
            if hidden_log:
                self.screen.mount(self.widget, before=self.screen.query_one("#panel"))
            elif logs:
                logs.first().mount(self.widget)
                logs.first().scroll_end(animate=False)
            elif (profile := self.screen.query("#insights")):
                profile.first().parent.mount(self.widget, before=profile.first())
                self.screen.call_after_refresh(self.widget.scroll_visible, animate=False)
            else:
                self.widget = None
                return self
        elif hidden_log:
            self.auxiliary = Static(classes="local-progress")
            self.screen.mount(self.auxiliary, before=self.screen.query_one("#panel"))
        self.widget.add_class("local-progress")
        self._draw(initial=True)
        self.timer = self.screen.set_interval(0.2, self._draw)
        return self

    def status(self, initial: bool = False) -> str:
        state = {} if initial else getattr(self.screen.app.ai, "progress_for", lambda model: {})(self.model)
        if state.get("started", self.started) < self.started:
            state = {}  # an earlier preload or reply must not supply this request's status
        phase = "preparing" if initial else state.get("phase", "waiting")
        text = f"{self.PHASES.get(phase, self.PHASES['waiting'])} · {int(time.monotonic() - self.started)}s elapsed"
        if state.get("tokens", 0) > 0:
            text += f" · {state['tokens']} tokens"
        return f"{self.task} · {text}" if self.task else text

    def _draw(self, initial: bool = False) -> None:
        if self.widget is None:
            return
        self.at = time.monotonic()
        status = self.status(initial)
        if self.text and self.auxiliary is None:
            self.widget.update(cards.ai(self.text, subtitle=status, partial=True))
        else:
            self.spinner.update(text=Text(status, style=C["muted"]))
            target = self.auxiliary if self.auxiliary is not None else self.widget
            target.update(cards.framed(self.spinner, C["ai"],
                                       local_models.LOCAL_MODELS[self.model], title_align="left"))
            if self.text:
                self.widget.update(cards.ai(self.text, partial=True))  # hidden in answer-only view

    def update(self, text: str) -> bool:
        if not self.local:
            return self.live.update(text)
        self.text = text
        if time.monotonic() - self.at < 0.15:
            return False
        self._draw()
        return True

    def __exit__(self, kind, error, traceback) -> None:
        if self.timer is not None:
            self.timer.stop()
        if self.widget is None:
            return
        if not self.local:
            if kind is not None and issubclass(kind, asyncio.CancelledError):
                # Keep only text already displayed; a buffered answer may still be protected.
                shown = getattr(self.widget.content, "card", None)
                partial = shown[2] if shown and shown[0] == "ai" and shown[2] != "…" else ""
                message = "The reply was cancelled before it finished."
                self.widget.update(cards.card("hint", "AI reply stopped",
                                              f"{partial}\n\n{message}" if partial else message, ai_output=True))
            return
        self.widget.remove_class("local-progress")
        if self.auxiliary is not None:
            self.auxiliary.remove()
        if self.owns_widget:
            self.widget.remove()
        elif kind is not None and issubclass(kind, asyncio.CancelledError):
            self.widget.update(cards.card("hint", "Local AI stopped", "The local request was cancelled."))


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
        if sp is None or self.app.screen is not self:
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
        self.app.stop_local_preload(self)

    def on_unmount(self) -> None:
        self.hush()
        self.app.stop_local_preload(self)


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
        self.call_after_refresh(self._scroll_cue)

    def _scroll_cue(self) -> None:
        """When the side box holds more than fits (Your topics, the chapters), say on its frame how to reach it (Q-008)."""
        try:
            box = self.query_one("#stats", VerticalScroll)
            box.border_subtitle = "Tab · PgDn for your topics" if box.max_scroll_y > 0 else ""
        except Exception:  # noqa: BLE001 - a courtesy, as above
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

    def _write_home(self) -> bool:
        app = self.app
        try:
            views.write_home(app.vault, app.tutor.packs, app.tutor.state, app.tutor.now(), views.recent_lessons(app.vault))
        except views.ReadOnlyViewDestination as exc:
            app.tutor.view_warnings.setdefault("Home.md", exc)
            return False
        app.tutor.view_warnings.pop("Home.md", None)
        return True

    def on_mount(self) -> None:
        app = self.app
        self._fit()
        self._read_almanac()
        views.organise_lessons(app.vault)  # lesson logs from before the day folders: moved into them, once
        self._write_home()
        report.today_note(app.tutor, app.settings.minutes)  # Today.md: this week's plan and what's due
        if (week := self._week_in_review()):
            app.notify(f"Your week in review is ready: {week} in Obsidian.", timeout=10)
        self.refresh_home()

        def resources_changed() -> None:
            if self.is_current and self.app.settings.usage_display in ("ram", "both"):
                self._draw_stats()
        self.set_interval(2, resources_changed)

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
        due_count = len(due) + len(policy.review_terms(t.state, t.packs, now))
        self.query_one("#banner", Static).update(look.banner())  # in the colours of the look just chosen
        menu = self.query_one("#menu", OptionList)
        items = []
        try:
            has_retained_drafts = bool(t.retained_drafts())
        except (OSError, ValueError):
            has_retained_drafts = False
            app.notify('Saved draft history could not be read; its file was not changed.', severity='warning', timeout=8)
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
                  ("review", f"↻  Review what's due ({due_count})"),
                  ("weak", f"✚  Fix my weak spots ({len(insights.weak_spots(t))})"),
                  ("test", "◎  Test prep: check and fix a chapter"),
                  ("long", "✎  Long questions (typed or iPad)"),
                  *([("topical", "▤  Topical past papers")] if t.packs.topical_chapters() else []),
                  ("blurt", "»  Blurt: write everything you remember"),
                  ("challenge", "⚑  Challenge: hard calculation questions"),
                  *shortcut_lines,
                  ("chat", "✦  Ask the tutor anything"),
                  ("insights", "◉  What the tutor knows about you"),
                  *([('saved-attempts', '▤  Saved attempts and drafts')] if t.postponed_judgments() or has_retained_drafts else []),
                  ("progress", "▤  My progress"),
                  ("obsidian", "▣  Open my notes in Obsidian"),
                  ("settings", "≡  Settings"), ("help", "?  How it works"), ("quit", "×  Quit")]
        self._menu_items = items
        self._fill_menu()
        menu.focus()
        self.query_one("#stats-text", Static).update(self.stats_text(now, due))
        self.call_after_refresh(self._scroll_cue)
        self.call_after_refresh(self._draw_stats)  # again once the box has its width: the titles wrap to it
        glance = Text(f"✶ {self.streak(now)}-day streak · ↻ {due_count} due · ◔ {clock.fmt(studied)} today", style=C["soft"])
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
        due_count = len(due) + len(policy.review_terms(t.state, t.packs, now))
        out.append(f"✶ {self.streak(now)}-day streak   ↻ {due_count} due\n", style=C["soft"])
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
        width = self.query_one("#stats-text", Static).size.width or 46

        def wrapped(text: str, room: int) -> list[str]:
            return [line.plain for line in Text(text).wrap(app.console, max(1, room))] or [""]

        for group in views.subtopic_groups(t.packs):
            ideas = [k for k, v in t.packs.kcs.items() if t.packs.subtopics.get(v["subtopic"], {}).get("topic") in
                     {c["id"] for c in group["chapters"]}]
            sure = sum(views.kc_status(t.state, k) == "secure" for k in ideas)
            out.append(f"\n{group['name']}", style=f"bold {C['banner']}")
            out.append(f"  {sure}/{len(ideas)} ideas secure\n", style=C["muted"])
            for chapter in group["chapters"]:
                kcs = [k for k, v in t.packs.kcs.items() if v["subtopic"] in chapter["subs"]]
                done = sum(views.kc_status(t.state, k) == "secure" for k in kcs)
                count = f"{done}/{len(kcs)}"
                if Text(f"▸ {chapter['name']}  {count}").cell_len <= width:
                    out.append(f"▸ {chapter['name']}", style=f"bold {C['plan']}")
                    out.append(f"  {count}\n", style=C["muted"])
                else:
                    for i, line in enumerate(wrapped(chapter["name"], width - 2)):
                        out.append(f"{'▸ ' if i == 0 else '  '}{line}\n", style=f"bold {C['plan']}")
                    out.append(f"  {count}\n", style=C["muted"])
                for sub in chapter["subs"]:
                    kcs = [k for k, v in t.packs.kcs.items() if v["subtopic"] == sub]
                    sec = sum(views.kc_status(t.state, k) == "secure" for k in kcs)
                    started = any(views.kc_status(t.state, k) != "new" for k in kcs)
                    colour = C["ok"] if sec == len(kcs) else C["soft"] if started else C["dim"]
                    count = f"{sec}/{len(kcs)}"
                    lead = Text(f"  {sub:<9} " + " " * 6 + f" {count:<6}").cell_len
                    compact = width - lead < 12
                    if compact:
                        out.append(f"  {sub}", style=C["text"])
                        out.append(f"  {count}\n", style=C["muted"])
                        out.append("  ")
                        lead = 2 + 6 + 1  # indent, bar, space before the title
                    else:
                        out.append(f"  {sub:<9} ", style=C["text"])
                    out.append(bar(sec, len(kcs), 6), style=colour)
                    out.append(" " if compact else f" {count:<6}", style=C["muted"])
                    lines = wrapped(t.packs.subtopics[sub]["title"], width - lead)
                    out.append(lines[0] + "\n", style=C["muted"])
                    for more in lines[1:]:
                        out.append(" " * lead + more + "\n", style=C["muted"])
        a = app.ai
        state = ("on" if a.available else {"login": "sign-in needed", "limit": "paused (limit)",
                                           "off": "not installed"}.get(a.status, a.status)) if app.settings.ai else "off"
        left = app.usage_status()
        out.append(f"\nAI tutor: {state} · {a.today()['replies']} replies today{' · ' + left if left else ''}\n",
                   style=C["ai"])
        out.append(f"\nSTEM Tutor v{__version__}", style=C["dim"])
        return out

    @on(OptionList.OptionSelected, "#menu")
    def pick(self, event: OptionList.OptionSelected) -> None:
        key = event.option.id
        app = self.app
        s = app.tutor.session
        if key in ("today", "learn", "review", "weak", "test", "long", "blurt") and s:  # even before an answer (B-104)
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
            if not model.due_kcs(app.tutor.state, app.tutor.now()) and not policy.review_terms(
                    app.tutor.state, app.tutor.packs, app.tutor.now()):
                app.notify("Nothing is due right now: your memory is on schedule. Try a lesson or a blurt instead.",
                           timeout=6)
                return
            app.push_screen(SessionScreen({"mode": "review", "focus": None, "minutes": app.settings.minutes}))
        elif key == "test":
            app.push_screen(PickerScreen("test"), lambda r: r and app.push_screen(
                SessionScreen({"mode": "test", "focus": r, "minutes": app.settings.minutes})))
        elif key == "topical":
            app.push_screen(PickerScreen("topical"), lambda r: r and app.push_screen(
                SessionScreen({"mode": "topical", "focus": r, "minutes": app.settings.minutes})))
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
        elif key == 'saved-attempts':
            if prompts.skipped_guards(app.tutor) or any((app.tutor.session or {}).get(k) for k in ('presented', 'queue')):
                app.notify('Finish or retry protected questions before viewing saved attempts.', severity='warning', timeout=6)
                return
            app.push_screen(SavedAttemptsScreen())
        elif key == "obsidian":
            if self._write_home():
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


def searchable(text: str) -> str:
    """Text as a topic search compares it: lower case, hyphens as spaces, curly apostrophes straight, accents dropped,
    so "Bronsted" finds Brønsted and "Hess's" finds Hess’s (Q-018). Greek letters stay as they are."""
    import unicodedata
    text = text.lower().replace("-", " ").translate(str.maketrans({"’": "'", "‘": "'", "ʼ": "'", "ø": "o", "æ": "ae",
                                                                   "ß": "ss", "–": " ", "—": " "}))
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


class _TopicOptions(OptionList):
    """Topic rows use role colours; the focused row uses the theme's cursor ink."""

    def render_line(self, y: int) -> Strip:
        strip = super().render_line(y)
        line = self.scroll_offset.y + y
        if 0 <= line < len(self._lines):
            index, _ = self._lines[line]
            if index == self.highlighted and not self.options[index].disabled:
                cursor = self.get_visual_style("option-list--option", "option-list--option-highlighted").rich_style
                foreground = Style(color=cursor.color)
                return Strip((Segment(segment.text, (segment.style or Style()) + foreground, segment.control)
                              for segment in strip), strip.cell_length)
        return strip


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

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        if action in ("tick_shown", "untick_all"):
            return self.mode == "test"
        return super().check_action(action, parameters)

    # ---------- data ----------
    def _prepare(self) -> None:
        t = self.app.tutor
        bank_chapters = t.packs.topical_chapters() if self.mode == "topical" else set()
        self.built = [s for s in t.packs.subtopics if (s in bank_chapters if self.mode == "topical" else t.packs.pack(s))]
        if self.mode == "long":
            # A selectable subtopic must have at least one structured question in
            # the KCs the fixed 30-minute session will consider.
            eligible = set()
            for sub in self.built:
                kcs = [k for k, v in t.packs.kcs.items() if v["subtopic"] == sub]
                long_kcs = [k for k in kcs if any(i.get("kind") == "structured" for i in t.packs.items_for(k))]
                if long_kcs[:2]:
                    eligible.add(sub)
            self.built = [s for s in self.built if s in eligible]
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
            self.hay[sub] = searchable(" ".join([sub, t.packs.subtopics[sub]["title"], topic.get("title", ""),
                                                 topic.get("spec", ""), topic.get("level", ""),
                                                 SEARCH_WORDS.get(self.info[sub]["subject"], ""), self.info[sub]["topic"]]))
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
        return all(w in self.hay[sub] for w in searchable(self.needle).split())

    def _crumb(self) -> str:
        names = dict(SUBJECT_FOLDERS)
        parts = [{"lesson": "Learn", "long": "Long questions", "blurt": "Blurt", "test": "Test prep", "topical": "Topical past papers"}.get(self.mode, "Topics")]
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
                       "blurt": "Pick a subtopic to blurt on.",
                       "topical": "Which subtopic do you want to practise with reviewed past papers?"}.get(self.mode, "Which subtopic do you want to study?")
                yield Static(f"{ask} (⏎ to choose or open a folder, Esc to go back)", classes="hint")
            yield Input(placeholder="Search everything: a word, a code (9702-3, P1) …  or just start typing", id="find",
                        compact=True, select_on_focus=False)
            yield Static(id="found", classes="hint")
            yield _TopicOptions(id="subs")
            if self.mode == "test":
                yield Button("Start test prep", id="go", variant="primary")

    def on_mount(self) -> None:
        self.fill()
        if self.mode == "long" and not self.built:
            self.query_one("#found", Static).update("No long questions are available in the published topics yet.")
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
        elif str(first.id).startswith("dir:"):
            self.open(str(first.id))
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
        self._up_folder()

    def _up_folder(self) -> None:
        came = "dir:" + "/".join(self.path)
        self.path = self.path[:-1]
        self.fill(keep=came)

    def action_back(self) -> None:
        if self.needle:  # the first Esc clears the search, then up a folder, then out
            self.query_one("#find", Input).value = ""
            self.query_one("#subs", OptionList).focus()
        elif len(self.path) > self.floor:
            self.query_one("#subs", OptionList).focus()
            self._up_folder()
        else:
            self.dismiss(None)

    def action_search(self) -> None:
        self.query_one("#find", Input).focus()

    def action_jump(self, step: int) -> None:
        """Move to the first subtopic of the next (or previous) topic."""
        box = self.query_one("#subs", OptionList)
        opts = [box.get_option_at_index(i) for i in range(box.option_count)]
        if not self.needle and len(self.path) == 1 and opts:
            box.highlighted = max(0, min(len(opts) - 1, (box.highlighted or 0) + step))
            return
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
                Binding("ctrl+y", "check_solvable", "Can I solve this?", show=False, priority=True),
                Binding("ctrl+r", "explain", "Explain", priority=True),
                Binding("ctrl+u", "retry_skipped", "Retry skipped", show=False, priority=True),
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
        yield Button("Can I solve this? · ctrl+y", id="check-solvable", compact=True)
        yield Container(id="panel")
        yield Footer()

    # ---------- plumbing ----------
    def on_resize(self, event) -> None:
        # Capture before the log is reflowed; a second layout pass can change its height again.
        size = event.size
        if size != getattr(self, "_resize_size", None) and self.query("#log"):
            log = self.query_one("#log", VerticalScroll)
            self._resize_follow_end = log.scroll_y >= log.max_scroll_y
            self._resize_size = size

    def finish_panel_resize(self) -> None:
        if getattr(self, "_resize_follow_end", False) and self.is_mounted:
            self.query_one("#log", VerticalScroll).scroll_end(animate=False, immediate=True)

    @property
    def tutor(self):
        return self.app.tutor

    def say(self, renderable, mirror: str | None = "both") -> Static:
        """Print a card, and put the same card on Now and in the lesson log (Obsidian reads as the terminal does, also
        with answer-only on). `mirror`: "now" when the engine has logged it already, None for the cards the engine
        draws itself (questions, marked answers, lesson steps) or a reply still streaming in."""
        w = Static(renderable, classes="entry")
        log = self.query_one("#log", VerticalScroll)
        log.mount(w)
        log.scroll_end(animate=False)
        if mirror and (c := getattr(renderable, "card", None)):
            role, title, body = c
            self.tutor.show(role, body, title, log=mirror == "both")
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
        if prompts.skipped_guards(self.tutor):
            self.app.notify("Retry the skipped question first (ctrl+u) before showing earlier teaching.", timeout=6)
            return
        for w in self.query("#log > .entry"):
            w.display = True
        self.query_one("#log", VerticalScroll).scroll_end(animate=False)

    def panel(self, widget) -> None:
        box = self.query_one("#panel", Container)
        box.remove_children()
        box.mount(widget)
        self.showing = widget
        self.query_one("#check-solvable", Button).display = (
            str((self.view or {}).get("n")) in (self.tutor.session or {}).get("presented", {}))

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
                "topical": "Reviewed past-paper questions for this chapter. Source figures are in Obsidian; supporting facts count as assistance.",
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
        if (t.session or {}).get('faded_cancel_intent'):
            self.faded_recovery_panel()
        if not self.view or self.view.get("kind") not in ("short", "structured"):
            self.app.prepare_local_ai("mark" if (t.session or {}).get("mode") == "long" else "explain")

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
        mode = {"lesson": "Lesson", "review": "Review", "test": "Test prep", "long": "Long questions", "topical": "Topical past papers"}.get(
            s.get("mode", ""), s.get("mode", "").title())
        replies = f"{a.session.replies} {'reply' if a.session.replies == 1 else 'replies'}"
        resource = self.app.usage_status()
        use = " · ".join(x for x in (replies, resource) if x)
        head, tail = Text(), Text()
        head.append(" STEM Tutor ", style=f"bold {C['badge_fg']} on {C['badge_bg']}")
        head.append(f" {title + ' · ' if title else ''}{mode} ", style="bold")
        tail.append(f" ◷ {clock.fmt(true_s, True)} true ", style=C["plan"])
        tail.append(f" ◔ {clock.fmt(active_s, True)} session ", style=C["plan"])
        tail.append(f" ✓ {s.get('correct', 0)}/{s.get('answered', 0)} ", style=C["good"])
        timing = tail.copy()
        tail.append(f" {ai_state} {use} ", style=C["ai"])
        if head.cell_len + tail.cell_len <= width:
            return head + tail
        if self.app.settings.usage_display in ("ram", "both"):
            # Keep both resource values whole in a narrow window; the title shares their first row.
            head.truncate(max(0, width - Text(resource).cell_len - 1), overflow="ellipsis")
            head.append(f" {resource}", style=C["ai"])
            tail = timing
            tail.append(f" {ai_state} {replies} ", style=C["ai"])
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
        self.query_one("#check-solvable", Button).display = kind in ("questions", "awaiting")
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
            spoken = [act.get("text") or act.get("outline", "")]  # the card's own text alone: its pre-generated audio is found by it
            if kind == "teach" and act.get("misconceptions"):
                spoken += [f"A common trap: {m}." for m in act["misconceptions"]]
            self.say_step(act, subtitle="second look" if act.get("part") == "fix" else None)
            self.readable_now(spoken, auto=True)
            self.explanation_panel(act)
        elif kind == 'saved_judgment_unavailable':
            buttons = ([('restore-saved-judgment', 'Restore question for marking')] if act.get('restore_candidate') else [])
            buttons.append(('postpone-saved-judgment', 'Save attempt for later'))
            buttons.append(('leave', 'Return to menu'))
            self.panel(ContinuePanel(act['error'], buttons=buttons))
        elif kind == "choose":
            self.say(cards.card("plan", act["question"], ""), mirror=None)  # its choices are in the panel below
            self.panel(ChoosePanel("Pick how you want to learn this (↑↓ and ⏎)", act["options"]))
        elif kind == "plan":
            self.say_step(act, subtitle="the concept map is in Obsidian → Now")
            self.prepare_cards(act["default_teach"])  # AI teaching cards (if needed) start while you read the plan
            self.panel(TickPanel("Ticked ideas will be taught (space to change). Then ctrl+s, or ⏎ on Start.",
                                 [(n["title"], n["kc"], n["kc"] in act["default_teach"]) for n in act["nodes"]],
                                 [("start", "Start lesson ⏎")]))
        elif kind in ("worked", "walkthrough"):
            self.say_step(act)  # with the steps already seen before a resume
            self.readable = act.get("problem") or ""
            self.panel(WorkedPanel(len(act["steps"]), start=act.get("revealed", 0) + 1))
        elif kind == "refute":
            m = act["misconceptions"][0]
            m = m if isinstance(m, dict) else {"statement": m}
            self.say_step(act)
            self.readable_now([f"A common trap: {m.get('statement', '')}.", m.get("refutation", ""),
                               m.get("contrast") or ""], auto=True)
            self.panel(ContinuePanel(read=self.can_read()))
        elif kind == "own_words":
            self.fold()
            self.say_step(act)
            self.panel(TextPanel("One or two sentences. Esc to skip.", done_label=None, confirm_skip=True))
        elif kind == "stuck":
            self.say_step(act)
            self.readable_now(act["say"], auto=True)
            buttons = [("continue", "Move on ⏎")] + ([("talk", "Talk it through with the tutor (AI)")]
                                                     if self.ai_ok("ask") else [])
            self.panel(ContinuePanel(buttons=buttons))
        elif kind == "end":
            self.finish()
        else:
            self.say(cards.card("bad", "Unexpected step", str(act)))
            self.panel(ContinuePanel(buttons=[("home", "Back to menu ⏎")]))

    @property
    def visual(self) -> bool:
        """In a lesson, everything is drawn by the one renderer AI text uses (`normalise_visual`, then the Unicode maths
        converter), so a card written in advance and a reply written now look the same. Other modes are unchanged."""
        return (self.tutor.session or {}).get("mode") == "lesson"

    def say_step(self, act: dict, subtitle: str | None = None) -> None:
        """A lesson step's cards, in the words the engine puts on Now and in the log (views.activity_cards)."""
        for i, (role, title, body) in enumerate(views.activity_cards(act)):
            self.say(cards.card(role, title, body, subtitle=subtitle if i == 0 else None,
                                ai_output=self.visual or bool(act.get("ai_source"))), mirror=None)
        self.show_lesson_figure(act)

    def explanation_panel(self, act: dict, *, detail: bool = True) -> None:
        """Prepared explanations and follow-up conversation share the same lesson controls."""
        unguarded = act.get('part') != 'guard_pause' and self.teaching_help_allowed()
        # Retain the existing diagram control while questions are queued. Its
        # handler explains why it cannot show content until the queue is clear.
        diagrams = (lesson.teach_card(self.tutor, self.kc).get('diagrams', [])
                    if self.kc and act.get('part') != 'guard_pause' and not prompts.skipped_guards(self.tutor) else [])
        buttons = [('continue', 'Continue ⏎')]
        if detail and act.get('detail'):
            buttons.append(('detail', 'More detail'))
        if diagrams:
            buttons.append(('diagram', 'Show diagrams'))
        if self.visual and unguarded:
            buttons += [('learn-stuck', "I'm stuck"), ('learn-example', 'Another example'),
                        ('learn', 'Talk to your tutor')]
            old = next(iter(self.query('#learning-question')), None) if not detail else None
            widget = LessonPanel(buttons=buttons, read=self.can_read(), draft=old.text if old else '',
                                 selection=old.selection if old else None)
        else:
            buttons += [('explain', 'Explain differently (ctrl+r)'), ('ask', 'Ask the tutor (ctrl+t)')]
            widget = ContinuePanel(buttons=buttons, read=self.can_read())
        self.panel(widget)

    def teaching_help_allowed(self) -> bool:
        """A shared boundary for inline conversation and images, including persisted retry guards."""
        session = self.tutor.session or {}
        return not (prompts.skipped_guards(self.tutor)
                    or any(session.get(key) for key in ('presented', 'queue', 'faded_cancel_intent')))

    def show_lesson_figure(self, act: dict) -> None:
        """Show only an unguarded activity's explicit, catalogue-verified figure."""
        if not self.visual or not act.get('diagram') or not self.teaching_help_allowed():
            return
        from .lesson_media import figure_preview
        if preview := figure_preview(self.app.vault, act['diagram']):
            self.say(preview, mirror=None).add_class('lesson-figure')

    def ask_question(self, view: dict, say: str | None = None) -> None:
        self.view = view
        if view.get("image") or view.get("kind") in ("short", "structured"):
            self.call_after_refresh(self._prepare_question, view)
        self.fold()
        card = self.say(cards.question(view, ai_output=self.visual), mirror=None)
        self.query_one("#check-solvable", Button).display = True
        if view.get("support"):
            facts = "\n".join(f"{k.split('-', 1)[-1]}: {v}" for k, v in view["support"].items())
            self.say(cards.card("hint", "Supporting facts · assisted attempt", facts), mirror=None)
        if len(view.get("images") or []) > 1:
            self.say(cards.note(f"This question has {len(view['images'])} source pages. Read all pages in Obsidian (ctrl+o).", "dim"), mirror=None)
        if say:  # under the question, where Now and the log have it
            self.say(cards.note(say, "dim"))
        parts = [view.get("speech") or view.get("stem", "")]
        if view.get("kind") == "mcq":  # the choices are part of the question (B-107); never the key
            parts += [f"Option {k}: {v}" for k, v in (view.get("options") or {}).items()]
        self.readable_now(parts)  # ctrl+e reads the question; it is never read by itself
        self.query_one("#log", VerticalScroll).call_after_refresh(self._show_top, card)  # after say's scroll_end
        self.answer_panel(view)

    def _prepare_question(self, view: dict) -> None:
        """Prepare written marking or an image once while the learner reads the current question."""
        key = ((self.tutor.session or {}).get("id"), view.get("n"), view.get("image"))
        if not self.is_current or self.view is not view or key == getattr(self, "_prepared_question", None):
            return
        if view.get("kind") in ("short", "structured"):
            model = self.app.settings.ai_for("mark")[0]
            if local_models.is_local(model) and self.app.ai_available("mark"):
                self._prepared_question = key
                self.app.prepare_local_ai("mark")
                return
        if not view.get("image"):
            return
        for mode in ("mark", "ask"):
            model = self.app.settings.ai_for(mode)[0]
            if (local_models.is_local(model) and not local_models.supports_vision(model)
                    and self.app.ai_available(mode)):
                self._prepared_question = key
                self.app.prepare_local_ai(mode)
                return

    def _show_top(self, card: Static) -> None:
        """Keep the start of the question visible after later notices scroll the log."""
        log = self.query_one("#log", VerticalScroll)
        if card.is_attached:
            log.scroll_to_widget(card, top=True, animate=False, immediate=True)

    def action_scroll_log(self, direction: int) -> None:
        """alt+↑ / alt+↓: the log a page at a time, keeping a line of what was on screen; works while typing."""
        log = self.query_one("#log", VerticalScroll)
        log.scroll_relative(y=direction * max(1, log.scrollable_content_region.height - 1), animate=False)

    def answer_panel(self, view: dict) -> None:
        checking = model.knobs(self.tutor.state)["checking_routine"]
        self.hint_armed = False
        if view["kind"] == "mcq":
            options = view.get("options")
            if (bad := view.get("garbled")) and options:  # a choice that did not copy: read it in the picture (Q-009)
                options = {k: "(in the picture)" if k in bad.get("options", []) else v for k, v in options.items()}
            self.panel(ChoicePanel(view["n"], options))
        elif view["kind"] == "structured":
            pending = (self.tutor.session or {}).get('presented', {}).get(str(view['n']), {})
            self.panel(LongPanel(view["n"], checking=checking, initial=view.get('saved_work', ''),
                                 ungraded=pending.get('ungraded_unavailable') is True))
        else:
            self.panel(ValuePanel(view["n"], view["kind"], checking=checking, initial=view.get('saved_work', '')))

    def respond(self, data: dict) -> None:
        if (self.tutor.session or {}).get("awaiting"):
            self.tutor.respond(data)

    # ---------- panel results ----------
    @on(Panel.Done)
    def panel_done(self, event: Panel.Done) -> None:
        if event.panel is not getattr(self, "showing", None):  # queued on a panel already replaced (key repeat): once only
            return
        data, kind = event.data, self.act.get("activity")
        if data.get('button') == 'faded-recover':
            binding = getattr(self, 'faded_recovery_binding', None)
            intent = (self.tutor.session or {}).get('faded_cancel_intent') or {}
            if not binding or self.tutor.session is not binding[0] or intent.get('operation') != binding[1]:
                self.app.notify('The recovery state changed; reopen the session.', severity='warning')
                return
            result = self.tutor.retry_faded_cancellation()
            if result.get('ok'):
                self.panel(ContinuePanel('Draft saved. The skipped question is still protected.',
                                         buttons=[('retry-skipped', 'Retry skipped question'), ('leave', 'Return to menu')]))
            else:
                self.faded_recovery_panel()
            return
        if data.get('button') in ('faded-submit', 'faded-edit', 'faded-skip'):
            pending = getattr(self, 'pending_faded', None)
            self.pending_faded = None
            if not pending or self.tutor.session is not pending['session']:
                self.app.notify('The question changed; reopen it before continuing.', severity='warning')
                return
            n = pending['n']
            question = (self.tutor.session or {}).get('presented', {}).get(str(n))
            if question is not pending['question']:
                self.app.notify('The question changed; reopen it before continuing.', severity='warning')
                return
            if data['button'] == 'faded-edit':
                self.view = self.tutor._view(n)
                self.answer_panel(self.view)
            elif data['button'] == 'faded-skip':
                self.submit({'entry': f'{n}?', 'your': "I don't know"})
            else:
                result = self.tutor.confirm_faded_attempt(n, pending['working'])
                if not result.get('ok'):
                    self.app.notify(result.get('error', 'Could not confirm this work.'), severity='warning')
                    self.answer_panel(self.tutor._view(n))
                else:
                    self.submit(pending['data'])
            return
        if data.get("button") == "read":
            self.action_read_aloud()
            return
        if data.get("button") == "retry-skipped":
            self.action_retry_skipped()
            return
        if data.get("button") == "suspend-for-retry":
            result = self.tutor.suspend_questions_for_retry()
            if not result.get('ok'):
                self.app.notify(result.get('error', 'Could not set questions aside.'), severity='error')
                return
            self.action_retry_skipped()
            return
        if data.get("button") == "resume-suspended":
            result = self.tutor.resume_suspended_questions()
            if result.get('ok'):
                self.advance()
            else:
                self.app.notify(result.get('error', 'Could not return to saved questions.'), severity='error')
            return
        if data.get('button') == 'skip-protected-retry':
            result = self.tutor.answer(f"{self.view['n']}?")
            if result.get('ok') is False or any(row.get('error') for row in result.get('results', [])):
                self.app.notify('Could not close the retry.', severity='error')
                return
            if (self.tutor.session or {}).get('suspended_for_retry'):
                restored = self.tutor.resume_suspended_questions()
                if not restored.get('ok'):
                    self.app.notify(restored.get('error', 'Could not return to saved questions.'), severity='error')
                    return
            self.advance()
            return
        if data.get('button') == 'restore-saved-judgment':
            candidate = self.act.get('restore_candidate')
            if not candidate:
                return
            def restore(choice):
                if choice == 'restore':
                    result = self.tutor.restore_topical(**candidate)
                    if result.get('ok'):
                        self.advance()
                    else:
                        self.app.notify(result.get('error', 'Could not restore the question.'), severity='error')
            self.app.push_screen(ConfirmScreen(
                f"Restore this question to {candidate['chapter']}? It may appear there again.",
                [('restore', 'Restore and mark'), ('cancel', 'Keep excluded')]), restore)
            return
        if data.get('button') == 'postpone-saved-judgment':
            result = self.tutor.postpone_saved_judgment()
            if result.get('ok'):
                message = ('Attempt saved; its original image needs review before marking.'
                           if result.get('image_review_required') else
                           'Attempt saved; it will return in a later session when eligible.')
                self.app.notify(message, timeout=6)
                self.advance()
            else:
                self.app.notify(result.get('error', 'Could not save the attempt.'), severity='error')
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
        if data.get('learn_question'):
            self.learn_request(data['learn_question'])
        elif data.get('button') in ('learn-stuck', 'learn-example'):
            request = ("I'm stuck on this idea. Can you guide me through it one step at a time?"
                       if data['button'] == 'learn-stuck' else
                       "Can you show me a different worked example for this idea?")
            self.learn_request(request)
        elif "entry" in data:
            self.submit(data)
        elif kind == "choose":
            self.say(cards.you(GOALS.get(data["choice"], data["choice"])), mirror="now")
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
            self.respond({"step": data["step"]})  # the engine logs the step and redraws the example on Now
            self.say(cards.card(*views.activity_cards({**self.act, "revealed": data["step"]})[data["step"]]), mirror=None)
            self.readable_now([f"Step {data['step']}.", st["do"], st.get("why", "")])
            if data["step"] >= len(self.act["steps"]):  # the last step is the answer: wait for the learner, do not move on
                self.panel(ContinuePanel("That was the last step. Read it through, then continue.", read=self.can_read()))
        elif kind in ("worked", "walkthrough") and data.get("done"):
            self.respond({"done": True})
            self.advance()
        elif kind == "own_words":
            if data.get("text"):
                self.say(cards.you(data["text"]), mirror="now")
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
        elif data.get("button") == "detail" and self.act.get("detail"):
            if any((self.tutor.session or {}).get(key) for key in ("presented", "queue")):
                self.app.notify("Finish the pending questions before showing more detail.", timeout=5)
                return
            detail = self.act["detail"]
            if self.learning_answer_is_guarded(detail):
                return
            self.say(cards.card("tutor", "More detail", detail))
            self.readable_now(detail, auto=True)
            self.explanation_panel(self.act, detail=False)
        elif data.get("button") == "diagram" and self.kc:
            if any((self.tutor.session or {}).get(key) for key in ("presented", "queue")):
                self.app.notify("Finish the pending questions before showing diagrams.", timeout=5)
                return
            card = lesson.teach_card(self.tutor, self.kc)
            self.show_lesson_diagrams(card)
        elif data.get("button") == "learn":
            self.action_learn_tutor()
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
            if kind not in ("questions", "awaiting"):
                self.respond({})
            self.advance()
        elif "ticked" in data:  # long answer self-marking
            self.long_marks(data)

    def submit(self, data: dict) -> None:
        t = self.tutor
        view = self.view or {}
        out = t.answer(data["entry"], your={view.get("n"): data.get("your", "")})
        if out.get("ok") is False:
            self.app.notify(out["error"], severity="error")
            return
        if len(out["results"]) > 1:
            self.app.notify("Your answer was read as several parts. Please avoid commas between numbers and try again.",
                            severity="warning", timeout=7)
        r = out["results"][0]
        if r.get('attempt_confirmation_required'):
            n = view['n']
            question = (t.session or {}).get('presented', {}).get(str(n))
            if not question:
                return
            self.pending_faded = {'session': t.session, 'question': question, 'n': n,
                                  'working': question.get('saved_work'), 'data': copy.deepcopy(data)}
            self.panel(ContinuePanel('Submit this as your attempt? Review will show the worked answer.',
                                     buttons=[('faded-edit', 'Keep editing'), ('faded-submit', 'Submit attempt'),
                                              ('faded-skip', 'Skip without seeing the answer')]))
            return
        if r.get('retry_cancelled'):
            self.panel(ContinuePanel('The skipped question remains saved.',
                                     buttons=[('retry-skipped', 'Retry skipped question'), ('leave', 'Return to menu')]))
            return
        if r.get('judgment_postponed'):
            self.panel(ContinuePanel('Your earlier attempt remains saved for marking.',
                                     buttons=[('next', 'Return to saved attempt'), ('leave', 'Return to menu')]))
            return
        if r.get('needs_retry'):
            self.view = t._view(view['n'])
            pending = (t.session or {}).get('presented', {}).get(str(view['n']), {})
            buttons = ([('skip-protected-retry', 'Close retry without marking'), ('leave', 'Return to menu')]
                       if pending.get('block') == 'skipped_retry' else
                       [('suspend-for-retry', 'Set aside and retry'), ('leave', 'Return to menu')])
            self.panel(ContinuePanel(r['error'], buttons=buttons))
            return
        if r.get("error"):
            if (t.session or {}).get('faded_cancel_intent'):
                self.faded_recovery_panel()
                return
            question = (t.session or {}).get('presented', {}).get(str(view.get('n')), {})
            self.view = (t._view(view['n']) or view) if question.get('inst', {}).get('written_faded') else view
            if (question and view.get("kind") == "numeric" and isinstance(self.showing, ValuePanel)
                    and self.showing.query(Confidence)):
                message = r["error"]
                show_notice = True
                if "; resend" in message:
                    message = (message.rsplit("; resend", 1)[0]
                               + ". Edit your value below, then press Enter and choose your confidence.")
                    now = monotonic()
                    notices = {key: deadline for key, deadline in getattr(self, "_numeric_format_notices", {}).items()
                               if deadline > now}
                    key = ((t.session or {}).get("id"), str(view["n"]), message)
                    show_notice = key not in notices
                    if show_notice:
                        notices[key] = now + 6
                    self._numeric_format_notices = notices
                if show_notice:
                    self.app.notify(message, severity="warning", timeout=6)
                self.showing.query_one(Confidence).action_back()
            else:
                self.app.notify(r["error"], severity="warning", timeout=6)
                self.answer_panel(self.view)
            return
        if data.get("note"):  # before the verdict, in Now and the log as well
            self.say(cards.you("✎ " + data["note"], f"Note on Q{view.get('n')}"))
        if r.get("pending_judgement"):
            # Keep the answer protected before the worker starts, and until marking finishes.
            self.pending_short = (view["n"], data, max(1, len(r.get("rubric", []))))
            self.judge_short(view, data, r)
            return
        self.say(cards.feedback(r, data.get("your", ""), ai_output=self.visual))
        self.readable_now(spoken_feedback(r, data.get("your", "")), auto=True)
        self.finish_feedback(r)

    def faded_recovery_panel(self) -> None:
        session = self.tutor.session
        intent = ((session or {}).get('faded_cancel_intent') or {})
        self.faded_recovery_binding = (session, intent.get('operation'))
        message = ('Different saved drafts were found. Both are retained; retry may not resolve this conflict. '
                   'Return to the menu if retry does not work.' if intent.get('conflict_recorded') else
                   'Your draft is saved. Retry saving it before continuing.')
        self.panel(ContinuePanel(message,
                                 buttons=[('faded-recover', 'Retry saving'), ('leave', 'Return to menu')]))

    def finish_feedback(self, r: dict, written: bool = False) -> None:
        self.last_fb = {**r, "written": written}
        self.followups = (["reflect"] if r.get("reflect") else []) + (["break"] if r.get("break_suggested") else [])
        self.next_followup()

    def can_remark(self) -> bool:
        """Whether the answer just marked can go to the AI examiner: one you gave (not "I don't know"), which the
        program marked wrong or docked a mark, and which has not been re-marked."""
        fb = getattr(self, "last_fb", None) or {}
        return bool(not fb.get('feedback_withheld') and not fb.get('attempt_saved') and len((self.view or {}).get("images") or []) <= 1 and self.ai_ok("mark") and fb.get("event") and not fb.get("correct") and not fb.get("remarked") and not fb.get("written")
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
            if ((getattr(self, "last_fb", None) or {}).get("answer_withheld")
                    and not (self.tutor.session or {}).get("queue")):
                buttons = [("retry-skipped", "Try again"), ("next", "Next ⏎")]
            if ((getattr(self, 'last_fb', None) or {}).get('feedback_withheld')
                    or (getattr(self, 'last_fb', None) or {}).get('attempt_saved')):
                buttons = [('retry-skipped', 'Retry skipped question'), ('next', 'Next ⏎')]
            if (getattr(self, "last_fb", None) or {}).get("written"):
                buttons = [("next", "Next ⏎"), ("ask", "Ask the tutor (ctrl+t)")]
            self.panel(ContinuePanel(buttons=buttons, read=self.can_read()))

    # ---------- written answers ----------
    def show_guided_review_answer(self, n: int, data: dict) -> None:
        question = (self.tutor.session or {}).get("presented", {}).get(str(n), {})
        solution = question.get("inst", {}).get("review_answer")
        attempt = data.get("your")
        if ((question.get("phase") in ("form_check", "term_review", "faded") or question.get('inst', {}).get('written_faded'))
                and isinstance(attempt, str) and attempt.strip()
                and isinstance(solution, str) and solution.strip()):
            self.say(cards.you(attempt, f"Your working for Q{n}"))
            self.say(cards.card("tutor", "Example answer", solution))
        if (question.get("phase") == "form_check" and isinstance(attempt, str) and attempt.strip()
                and question.get("inst", {}).get("review_rule") == "consecutive_primes"):
            from .guided_review import consecutive_prime_warning
            if warning := consecutive_prime_warning(attempt):
                self.say(cards.card("hint", "Check the domain", warning))
        if (question.get("phase") == "form_check" and isinstance(attempt, str) and attempt.strip()
                and question.get("inst", {}).get("review_rule") == "geometric_subtraction"):
            from .guided_review import geometric_subtraction_note
            if note := geometric_subtraction_note(attempt):
                self.say(cards.card("hint", "Check the subtraction", note))
        if (question.get('phase') == 'form_check' and isinstance(attempt, str) and attempt.strip()
                and question.get('inst', {}).get('review_rule') == 'positive_pair'):
            from .guided_review import positive_pair_warning
            working = re.sub(r'\s+\((?:guess|unsure|fairly sure|certain)\)$', '', attempt, flags=re.I)
            if warning := positive_pair_warning(working):
                self.say(cards.card('hint', 'Check the domain', warning))

    @work(exclusive=True, group="judge")
    async def judge_short(self, view: dict, data: dict, pending: dict) -> None:
        n = view["n"]
        points = pending.get("rubric", [])
        marking_ticket = self.tutor.begin_marking(n, data.get('your'))
        if self.ai_ok("mark") and len(view.get("images") or []) <= 1:
            try:
                self.panel(ContinuePanel("Checking your wording against the mark points…", buttons=[]))
                model, think = self.app.settings.ai_for("mark")
                schema = prompts.local_judge_schema(points) if local_models.is_local(model) else prompts.JUDGE
                with LocalActivity(self, model, task="Marking answer"):
                    res, _ = await self.app.ai.one_shot(prompts.judge(view.get("stem", ""), points, data.get("your", "")),
                                                        schema=schema, model=model, think=think,
                                                        **spoken_too(self.app), **image_for_local(self.tutor, model))
            except BaseException:
                self.tutor.cancel_marking(marking_ticket)
                raise
            marking_state = self.tutor.marking_status(marking_ticket)
            if marking_state == 'stale':
                return
            if marking_state != 'ok':
                self.pending_short = None
                if marking_state == 'retry_protected':
                    self.submit(data)  # engine keeps the working and offers the protected retry
                else:
                    self.panel(ContinuePanel('Your working is saved. Return to the menu before marking.',
                                             buttons=[('leave', 'Return to menu')]))
                return
            if ai_mod.matches_points(res, points):
                question = (self.tutor.session or {}).get("presented", {}).get(str(n), {})
                if question.get("phase") in ("form_check", "term_review", "faded") or question.get('inst', {}).get('written_faded'):
                    self.show_guided_review_answer(n, data)
                    self.panel(TickPanel("AI suggestions are unverified. Tick earned points after reviewing; alternative methods may earn credit. Alt+↑↓ scrolls; ctrl+s confirms.",
                                         [(f"AI suggests {'met' if res['points'][i]['met'] else 'not met'} · {p}", str(i), False)
                                          for i, p in enumerate(points)],
                                         [("self", "Confirm marks ⏎")]))
                    return
                met = sum(1 for p in res["points"] if p.get("met"))
                score = met / max(1, len(points))
                verdict = (res.get("feedback", "") + "\n\n" + "\n".join(
                    f"- {'✓' if p.get('met') else '✗'} {p.get('point', '')}" for p in res["points"])).strip()
                out = self.tutor.answer(data["entry"], judge={n: score}, your={n: data.get("your", "")},
                                        explanation={n: verdict})  # Now and the log carry the examiner's verdict too
                fb = out["results"][0]
                self.pending_short = None
                self.say(cards.feedback(fb, data.get("your", ""), ai_output=True))
                self.readable_now(spoken_feedback(fb, data.get("your", ""), res.get("speech") or None), auto=True)
                self.finish_feedback(fb, written=True)
                return
        else:
            # No asynchronous judge response is pending; consume the ticket so
            # the tutor does not retain an unused process-local identity token.
            self.tutor.marking_status(marking_ticket)
        self.show_guided_review_answer(n, data)
        self.panel(TickPanel("Mark yourself: tick each point your answer really contains (space), then ctrl+s, or ⏎ on Done.",
                             [(p, str(i), False) for i, p in enumerate(points)], [("self", "Done ⏎")]))

    def long_marks(self, data: dict) -> None:
        if getattr(self, "pending_short", None):
            n, d, total = self.pending_short
            self.pending_short = None
            question = (self.tutor.session or {}).get("presented", {}).get(str(n), {})
            rubric = question.get("inst", {}).get("rubric", [])
            if (question.get("phase") in ("form_check", "faded") or question.get('inst', {}).get('written_faded')) and rubric:
                selected = set(data["ticked"]) & {str(i) for i in range(len(rubric))}
                verdict = "**Reviewed mark points:**\n\n" + "\n".join(
                    f"- {'✓' if str(i) in selected else '✗'} {point['point']}"
                    for i, point in enumerate(rubric))
                out = self.tutor.answer(d["entry"], judge={n: len(selected) / total},
                                        your={n: d.get("your", "")}, explanation={n: verdict})
            else:
                out = self.tutor.answer(d["entry"], judge={n: len(data["ticked"]) / total}, your={n: d.get("your", "")})
            self.say(cards.feedback(out["results"][0], d.get("your", "")))
            self.readable_now(spoken_feedback(out["results"][0], d.get("your", "")), auto=True)
            self.finish_feedback(out["results"][0], written=True)
            return
        n = self.view["n"]
        if data.get("button") == "ai":
            self.ai_check_long(data)
            return
        claimed = f"{len(data['ticked'])} mark point(s) claimed"
        out = self.tutor.answer(f"{n} pts=" + ",".join(data["ticked"]) if data["ticked"] else f"{n} pts=", your={n: claimed})
        fb = out["results"][0]
        self.say(cards.feedback(fb, claimed))
        self.readable_now(spoken_feedback(fb), auto=True)
        self.finish_feedback(fb, written=True)

    def long_written(self, data: dict) -> None:
        text = data.get("text", "")
        self.long_text = text
        pending = (self.tutor.session or {}).get('presented', {}).get(str(self.view['n']), {})
        if pending.get('ungraded_unavailable') is True:
            if data.get('button') == 'cancel-ungraded':
                try:
                    result = self.tutor.cancel_ungraded_structured(self.view['n'], text)
                except (OSError, ValueError) as exc:
                    result = {'ok': False, 'error': str(exc) or 'Could not save draft.'}
                if result.get('ok'):
                    self.panel(ContinuePanel('Draft saved; the skipped question remains protected.',
                                             buttons=[('retry-skipped', 'Retry skipped question'), ('leave', 'Return to menu')]))
                else:
                    self.panel(LongPanel(self.view['n'], initial=text, ungraded=True))
                    self.app.notify(result.get('error', 'Could not save draft.'), severity='error')
                return
            try:
                result = self.tutor.save_ungraded_structured(self.view['n'], text)
            except (OSError, ValueError) as exc:
                result = {'ok': False, 'error': str(exc) or 'Could not save working.'}
            if not result.get('ok'):
                self.panel(LongPanel(self.view['n'], initial=text, ungraded=True))
                self.app.notify(result.get('error', 'Could not save working.'), severity='error')
                return
            self.say(cards.you(text, f"Your working for Q{self.view['n']}"))
            self.say(cards.feedback(result, text))
            self.finish_feedback(result, written=True)
            return
        self.say(cards.you(text, f"Your working for Q{self.view['n']}"))  # kept in the log, even if you leave before marking
        sch = self.tutor.scheme(self.view["n"])
        if sch.get('error'):
            saved = self.tutor.save_structured_draft(self.view['n'], text)
            if not saved.get('ok'):
                self.panel(LongPanel(self.view['n'], initial=text))
                self.app.notify(saved.get('error', 'Could not save working.'), severity='error')
                return
            self.panel(ContinuePanel(sch['error'] + ' Your working is saved in this session without a mark. '
                                     'Set pending questions aside to retry the skipped question.',
                                     buttons=[('suspend-for-retry', 'Set aside and retry'), ('leave', 'Return to menu')]))
            return
        self.scheme = sch.get("scheme", [])
        buttons = [("mine", "Submit my marks ⏎")] + ([("ai", "Ask the AI examiner to check")]
                  if self.ai_ok("mark") and len(self.view.get("images") or []) <= 1 else [])
        self.mark_panel("Tick every mark point your answer earns (space), then ctrl+s. Honest self-marking is great practice.",
                        (), buttons)

    def mark_panel(self, prompt: str, ticked, buttons: list[tuple[str, str]]) -> None:
        self.panel(TickPanel(prompt, [(f"{p.get('mark', '')} {p.get('point', '')}", str(p["i"]), str(p["i"]) in ticked)
                                      for p in self.scheme], buttons))

    @work(exclusive=True, group="judge")
    async def ai_check_long(self, data: dict) -> None:
        if len((self.view or {}).get("images") or []) > 1:
            self.mark_panel("Read all source pages in Obsidian, then submit your own marks.", data.get("ticked", []),
                            [("mine", "Submit my marks ⏎")])
            return
        self.panel(ContinuePanel("The AI examiner is marking your answer…", buttons=[]))
        points = [f"{p.get('mark', '')} {p.get('point', '')}" for p in self.scheme]
        model, think = self.app.settings.ai_for("mark")
        schema = prompts.local_judge_schema(points) if local_models.is_local(model) else prompts.JUDGE
        self.long_mark_pending = True
        try:
            with LocalActivity(self, model, task="Marking answer"):
                res, r = await self.app.ai.one_shot(prompts.judge(self.view.get("stem", ""), points, self.long_text),
                                                    schema=schema, model=model, think=think,
                                                    **spoken_too(self.app), **image_for_local(self.tutor, model))
        finally:
            self.long_mark_pending = False
        if not ai_mod.matches_points(res, points):  # give the tick list back, with your ticks, so you can still mark it yourself
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
        ticked = sorted(met)
        self.mark_panel("Adjust if you disagree, then ctrl+s to submit.", ticked, [("mine", "Submit ⏎")])

    @work(exclusive=True, group="judge")
    async def remark(self) -> None:
        """A second marker for an answer the program marked wrong. It matches units, forms and wording narrowly, and
        an answer key can be wrong; if the AI examiner finds the answer right, it counts as right from then on."""
        fb, view = self.last_fb, self.view or {}
        self.panel(ContinuePanel("The AI examiner is checking the marking…", buttons=[]))
        selected, selected_think = self.app.settings.ai_for("mark")
        model = selected if local_models.is_local(selected) or codex_models.is_codex(selected) else prompts.REMARK_MODEL
        think = (selected_think if local_models.thinking_levels(model) and self.app.settings.ai_mark_effort else
                 local_models.supports_thinking(model)) if local_models.is_local(model) else True
        with LocalActivity(self, model, task="Checking the marking"):
            res, r = await self.app.ai.one_shot(prompts.remark(view, fb), schema=prompts.REMARK, model=model, think=think,
                                                **spoken_too(self.app), **image_for_local(self.tutor, model))
        if res:
            fb["remarked"] = True  # one re-mark an answer; a call that failed can be tried again
            self.readable_now(["Re-marked: correct." if res.get("correct") is True else "Re-marked: the mark stands.",
                               res.get("speech") or res.get("why", "")], auto=True)
        out = self.tutor.regrade(fb["event"], res.get("why", "")) if res and res.get("correct") is True else {}
        if out.get("ok"):
            self.last_fb = {**(out.get("feedback") or {**fb, "correct": True, "partial": False}), "remarked": True}
            self.followups = ["break"] if self.last_fb.get("break_suggested") else []  # nothing was missed
            self.say(cards.card("tutor", "Re-marked: correct ✓",  # the engine logged it in these words
                                f"{res.get('why', '')}\n\nIt now counts as right in your record.", ai_output=True), mirror="now")
        elif res:
            self.say(cards.card("hint", "Re-marked: the mark stands", res.get("why", ""), ai_output=True))
        else:
            self.say(cards.card("hint", "AI check unavailable", r.message or "Try again later."))
        self.update_bar()
        self.next_followup()

    # ---------- AI ----------
    def ai_ok(self, mode: str = "explain") -> bool:
        return self.app.ai_available(mode)

    def stream(self, prompt: str, then_continue: bool = False, mode: str = "ask", web_query: str | None = None) -> None:
        if not self.ai_ok(mode):
            a = self.app.ai
            msg = (a.problem_for(self.app.settings.ai_for(mode)[0]) if self.app.settings.ai
                   else "AI is switched off in Settings.")
            self.say(cards.card("hint", "AI help is off", msg))
            if then_continue:
                self.panel(ContinuePanel(buttons=[("continue", "Continue ⏎")]))
            return
        if (help_ := self.tutor.ai_help(given=False)).get("refused"):  # not allowed while a no-help check is open
            self.say(cards.card("hint", "No help on this one", help_["refused"]))
            if then_continue:
                self.panel(ContinuePanel(buttons=[("continue", "Continue ⏎")]))
            return
        self._stream(prompt, then_continue, mode, web_query)

    @work(exclusive=True, group="ai")
    async def _stream(self, prompt: str, then_continue: bool, mode: str = "ask", web_query: str | None = None) -> None:
        a = self.app.ai
        w = self.say(cards.ai("…"), mirror=None)  # Now and the log get the whole reply once it ends
        buf = ""
        # guard every open question (normally just the one on screen; a session begun in the chat may hold more)
        session, act = self.tutor.session, self.act
        numbers = tuple((session or {}).get("presented", {}))
        log = self.tutor._lesson_log()
        keys = prompts.guard_keys(self.tutor)
        skipped = bool(prompts.skipped_guards(self.tutor))
        model, think = self.app.settings.ai_for(mode)  # chosen in Settings for this kind of help
        with LocalActivity(self, model, w) as live:
            async for chunk in a.stream(prompt, image=prompts.focus_image(self.tutor), model=model, think=think,
                                         **({"web_query": web_query} if local_models.is_local(model) and web_query else {})):
                buf += chunk
                if not keys and not skipped and self.act is act and self.tutor.session is session and live.update(buf):
                    self.query_one("#log", VerticalScroll).scroll_end(animate=False)
        speech = a.last.speech if a.last.ok else ""
        buf = (a.last.text or buf) if a.last.ok else buf  # whole and tidy: a code fence the spoken line opened is gone
        withheld = skipped or any(ai_mod.leaks(buf, *k) or (speech and ai_mod.leaks(speech, *k)) for k in keys)
        if withheld:
            buf = ("I can't give that away while the question is open. Try a hint (h), or answer first and I'll explain."
                   if numbers else "I can't give away the answer to a skipped question before an attempt. Start or resume a lesson and press ctrl+u to retry it.")
            speech = ""
        buf = normalise_visual(buf)
        # A reply to an earlier question stays in its transcript, never on the new question.
        if self.tutor.session is not session or self.act is not act or tuple((self.tutor.session or {}).get("presented", {})) != numbers:
            w.update(cards.ai(buf))
            w.display = False
            if a.last.ok and log:
                title = "Tutor (AI)" + (" · Q" + ", Q".join(numbers) if numbers else " · earlier activity")
                log.tutor(buf, title=title)
            self.update_bar()
            return
        if not a.last.ok:
            w.update(cards.card("hint", "AI paused", a.last.message))
            self.tutor.show("hint", a.last.message, "AI paused")
        elif not buf.strip():
            message = "The AI returned an empty reply. Try asking again."
            w.update(cards.card("hint", "No AI reply", message))
            self.tutor.show("hint", message, "No AI reply")
        else:
            w.update(cards.ai(buf))
            self.readable_now(speech or buf, auto=True, limit=tts.AI_SPEECH_LIMIT)
            if buf and not withheld:
                self.tutor.ai_help()  # help that reached you counts as a hint on every open question
            self.tutor.show("ai", buf, "Tutor (AI)")  # the card as drawn: Now and the log
        self.update_bar()
        if then_continue:
            self.panel(ContinuePanel(buttons=[("continue", "Continue ⏎"), ("ask", "Ask the tutor (ctrl+t)")],
                                     read=self.can_read()))
        # A synchronous stream can finish before this card mounts and acquires its final height.
        w.call_after_refresh(self.query_one("#log", VerticalScroll).scroll_end, animate=False)

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
            model, think = self.app.settings.ai_for("explain")
            if not local_models.is_local(model) and not codex_models.is_codex(model):
                think = False  # Claude cards keep their original fast, non-thinking default.
            with LocalActivity(self, model, task="Writing teaching notes"):
                data, _ = await self.app.ai.one_shot(prompts.teach_card(self.tutor, kc), schema=prompts.CARD,
                                                    model=model, think=think)
            if data and all(data.get(f) for f in ("motivate", "establish", "note")):
                p = self.app.vault / ".tutor" / "cache" / "teach" / f"{kc}.json"
                try:
                    p.parent.mkdir(parents=True, exist_ok=True)
                    p.write_text(json.dumps({**data, "source": "ai"}, ensure_ascii=False, indent=1))
                except OSError:  # a vault that cannot be written: the card is simply not cached
                    pass

    # ---------- key actions ----------
    def show_lesson_diagrams(self, card: dict) -> bool:
        """Use the same terminal description and Obsidian embed as lesson steps."""
        # The text-only guard cannot inspect the content of an SVG.
        if prompts.guard_keys(self.tutor):
            self.say(cards.card("hint", "Diagram", "The diagram is withheld while a skipped answer is protected."))
            return False
        descriptions = diagram_descriptions(card)
        for index, diagram in enumerate(card.get("diagrams") or []):
            description = descriptions[index] if index < len(descriptions) else "Lesson diagram."
            act = {"activity": "explain", "title": "Diagram", "text": description, "diagram": diagram}
            role, title, body = views.activity_cards(act)[0]
            self.say(cards.card(role, title, body), mirror=None)
            self.show_lesson_figure(act)
            obsidian = views.activity_cards(act, obsidian=True)[0]
            self.tutor.show(obsidian[0], obsidian[2], obsidian[1])
        return True

    def action_learn_tutor(self) -> None:
        if any((self.tutor.session or {}).get(key) for key in ("presented", "queue")):
            self.app.notify("Finish the pending questions before talking through the idea.", timeout=5)
            return
        if self.query('#learning-question'):
            self.query_one('#learning-question', Composer).focus()
        else:
            self.app.push_screen(AskScreen(mode="learn"), lambda q: q and self.learn_request(q))

    def remember_card_disclosures(self, session: dict, cards_to_show: list[dict]) -> None:
        """Keep explicitly disclosed items out of later checks, including related cards."""
        disclosed = session.setdefault('disclosed_item_ids', [])
        for card in cards_to_show:
            ids = card.get('disclosed_item_ids') if isinstance(card, dict) else None
            if isinstance(ids, list):
                disclosed.extend(item for item in ids if isinstance(item, str) and item not in disclosed)
        self.tutor._save()

    def remember_learning_exchange(self, session: dict, kc: str, question: str, reply: str) -> None:
        """Keep the same bounded history for all learning-tutor reply paths."""
        entries = session.setdefault("learn_history", {}).setdefault(kc, [])
        entries.append({"question": question[:1000], "reply": reply[:3000]})
        del entries[:-4]
        self.tutor._save()

    def remember_selected_terms(self, sections: list[str], source_cards: dict) -> None:
        for section in sections:
            selected_kc, _, ref = section.partition('|')
            match = re.fullmatch(r'term:(0|[1-9][0-9]*)', ref)
            if match:
                term = source_cards[selected_kc]['terms'][int(match.group(1))]['term']
                tid = lesson.term_id(selected_kc, term)
                if tid not in self.tutor.state.get('terms', {}):
                    self.tutor.log({'type': 'term_introduced', 'term_id': tid, 'kc': selected_kc})

    def learning_answer_is_guarded(self, text: str) -> bool:
        # Literal matching cannot detect paraphrased answers. Until skipped
        # questions can be revisited, fail closed for this hidden prototype.
        if (prompts.skipped_guards(self.tutor)
                or any(ai_mod.leaks(text, *key) for key in prompts.guard_keys(self.tutor))):
            self.say(cards.card("hint", "Learning tutor paused",
                                "I can't give away the answer to a skipped question before an attempt. Press ctrl+u to retry it."))
            return True
        return False

    def start_form_check(self, index: int, question: str, source_cards: dict, kc: str, echo: bool = True) -> bool:
        """Give the learner the short check of one question form, unassisted, through the usual question path."""
        forms = source_cards.get(kc, {}).get('forms') or []
        form = forms[index] if 0 <= index < len(forms) and isinstance(forms[index], dict) else {}
        rubric = form.get('rubric')
        if (not isinstance(form.get('check'), str) or not form['check'].strip()
                or not isinstance(rubric, list) or not rubric):
            self.say(cards.card('hint', 'Learning tutor', 'No check is available for that form.'))
            return False
        if self.learning_answer_is_guarded(''):
            return False
        item = {'id': f'{kc}-form-{index + 1}', 'kcs': [kc], 'kind': 'short', 'difficulty': 3,
                'stem': form['check'], 'rubric': rubric, 'marks': len(rubric),
                'review_answer': form.get('answer', ''), 'form_index': index}
        if form.get('review_rule'):
            item['review_rule'] = form['review_rule']
        activity = self.tutor._questions({'kind': 'guided_request', 'kc': kc}, None, [item],
                                         phase='form_check', unassisted=True)
        if not activity:
            self.say(cards.card('hint', 'Learning tutor', 'This check is unavailable.'))
            return False
        if echo:
            self.say(cards.you(question))
        self.act = activity
        self.ask_question(activity['items'][0], 'Try this form without hints.')
        self.update_bar()
        return True

    def start_topical_question(self, kc: str, question: str, echo: bool = True) -> bool:
        """One eligible bank question on this idea, chosen by the program (never by the AI), asked unassisted."""
        item = self.tutor._pick(kc, 0.6)
        activity = self.tutor._questions({'kind': 'guided_request', 'kc': kc}, None, [item], phase='ai_question',
                                         unassisted=True) if item else None
        if not activity:
            self.say(cards.card('hint', 'Learning tutor', 'There is no eligible past-paper question for this idea yet.'))
            return False
        if echo:
            self.say(cards.you(question))
        self.act = activity
        self.ask_question(activity['items'][0], 'A question on this idea. Try it without hints.')
        self.update_bar()
        return True

    def show_teach_results(self, question: str, results: list[dict], kc: str, source_cards: dict) -> str:
        """Draw what the teaching actions returned, exactly as the lesson draws its own cards. Returns the text shown
        (for the exchange history)."""
        self.say(cards.you(question))
        shown, ui = [], []
        for r in results:
            if r["kind"] == "problem":
                self.say(cards.card("hint", "Learning tutor", r["text"]))
            elif r["kind"] == "card" and r.get("note"):
                if (log := self.tutor._lesson_log()):
                    log.card("you", "Note", r["body"])
                self.say(cards.you(r["body"], "Note saved"), mirror="now")
                shown.append(r["body"])
            elif r["kind"] == "card" and r.get("image"):
                role, title, body = views.activity_cards(ta.as_activity(r))[0]
                self.say(cards.card(role, title, body, ai_output=True), mirror=None)
                self.show_lesson_figure(ta.as_activity(r))
                obsidian = views.activity_cards(ta.as_activity(r), obsidian=True)[0]
                self.tutor.show(obsidian[0], obsidian[2], obsidian[1])
                shown.append(r["body"])
            elif r["kind"] == "card":
                self.say(cards.card(r["role"], r["title"], r["body"], ai_output=True))
                shown.append(r["body"])
            elif r["kind"] == "term":
                tid = lesson.term_id(kc, r["term"])
                if tid not in self.tutor.state.get("terms", {}):
                    self.tutor.log({"type": "term_introduced", "term_id": tid, "kc": kc})
            else:
                ui.append(r)
        text = "\n\n".join(shown)
        if text:
            self.readable_now(text, auto=True, limit=tts.AI_SPEECH_LIMIT)
        for r in ui[:1]:  # a question or hint takes over the screen: only the first
            if r["do"] == "check":
                self.start_form_check(r["form"], question, source_cards, kc, echo=False)
            elif r["do"] == "question":
                self.start_topical_question(kc, question, echo=False)
            elif r["do"] == "hint":
                self.action_hint()
        return text

    @work(exclusive=True, group="ai")
    async def learn_request(self, question: str) -> None:
        """Use prepared teaching and contextual follow-ups without advancing the lesson."""
        session, act, kc = self.tutor.session, self.act, self.kc
        if not session or not kc or session.get("presented") or session.get("queue"):
            self.app.notify("Finish the pending questions before talking through the idea.", timeout=5)
            return
        if self.learning_answer_is_guarded(''):
            return
        detail_request = bool(re.fullmatch(
            r'\s*(?:(?:can|could) you (?:give|show|tell) me (?:some )?(?:more|the) detail|'
            r'(?:show )?(?:me )?(?:more|the) detail|(?:please )?explain more)\s*[?.!]*\s*', question, re.I))
        if not detail_request and session.pop('learn_detail', None):
            self.tutor._save()
        calculation = (learn_reply.checked_arithmetic_request(question)
                       or learn_reply.checked_identity_request(question))
        if calculation is not None:
            if self.learning_answer_is_guarded(calculation):
                return
            self.say(cards.you(question))
            self.say(cards.ai(normalise_visual(calculation)))
            self.remember_learning_exchange(session, kc, question, calculation)
            self.readable_now(calculation, auto=True, limit=tts.AI_SPEECH_LIMIT)
            return
        question_count = session.get("count", 0)
        model_name, think = self.app.settings.ai_for("learn")
        history = session.get("learn_history", {}).get(kc, [])[-4:]
        previous = "\n\nEarlier exchanges on this idea:\n" + "\n".join(
            f"Student: {entry['question']}\nTutor: {entry['reply']}" for entry in history) if history else ""
        source_cards = learn_reply.published_related_cards(self.tutor, kc)
        if not source_cards:
            self.say(cards.card("hint", "Learning tutor paused", "No published teaching card is available for this idea."))
            return
        pending = session.get('learn_detail')
        if detail_request and pending:
            fingerprint = hashlib.sha256(json.dumps(source_cards, sort_keys=True, ensure_ascii=False,
                                                    separators=(',', ':')).encode()).hexdigest()
            if (pending.get('session') != session.get('id') or pending.get('kc') != kc
                    or pending.get('cards') != fingerprint):
                session.pop('learn_detail', None)
                self.tutor._save()
                self.say(cards.card('hint', 'Learning tutor', 'The teaching material changed. Ask your question again.'))
                return
            data = {'sections': pending.get('sections')}
            text, problem = learn_reply.render_related_selection(data, source_cards)
            if problem or self.learning_answer_is_guarded(text):
                if problem:
                    self.say(cards.card('hint', 'Learning tutor', problem))
                return
            self.remember_card_disclosures(session, [source_cards[s.partition('|')[0]] for s in data['sections']])
            self.say(cards.you(question))
            self.say(cards.ai(normalise_visual(text)))
            self.remember_selected_terms(data['sections'], source_cards)
            self.remember_learning_exchange(session, kc, question, text)
            session.pop('learn_detail', None)
            self.tutor._save()
            self.readable_now(text, auto=True, limit=tts.AI_SPEECH_LIMIT)
            return
        if not self.ai_ok("learn"):
            self.app.notify("Learning tutor is unavailable; check Settings.", timeout=5)
            return
        card = source_cards.get(kc, {})
        mis_id = learn_reply.explicit_misconception(question, card)
        subtopic = self.tutor.packs.kcs.get(kc, {}).get("subtopic")
        tracked = self.tutor.packs.misconception(subtopic, mis_id) if subtopic and mis_id else None
        if tracked and tracked.get("kc") == kc:
            entry = next((m for m in card.get("misconceptions", []) if m.get("id") == mis_id), None)
            if entry and all(isinstance(entry.get(key), str) and entry[key] for key in ("idea", "temptation", "fix")):
                self.tutor.log({"type": "misconception_noted", "kc": kc, "misconception": mis_id})
                self.say(cards.you(question))
                text = lesson.misconception_text(entry)
                if self.learning_answer_is_guarded(text):
                    return
                self.remember_card_disclosures(session, [card])
                self.say(cards.card("hint", "Let's revisit this", text))
                self.remember_learning_exchange(session, kc, question, text)
                return
        if re.fullmatch(r"\s*(?:show|list) (?:me )?(?:the )?(?:question )?forms\s*[?.!]*\s*", question, re.I):
            forms = source_cards.get(kc, {}).get("forms") or []
            lines = []
            for number, form in enumerate(forms, 1):
                if isinstance(form, dict) and isinstance(form.get("name"), str):
                    wordings = form.get("wordings") or []
                    wording = "; ".join(w for w in wordings if isinstance(w, str))
                    lines.append(f"- **{form['name']}** (form {number})" + (f": {wording}" if wording else ""))
            self.say(cards.you(question))
            text = ("\n".join(lines) + "\n\nAsk ‘Show example for form 1’ or ‘Try form 1’, using the form number you want."
                    if lines else "No question forms are available for this idea yet.")
            if self.learning_answer_is_guarded(text):
                return
            self.remember_card_disclosures(session, [source_cards.get(kc, {})])
            self.say(cards.card("tutor", "Question forms", text))
            self.remember_learning_exchange(session, kc, question, text)
            return
        form_request = re.fullmatch(r'\s*show (?:me )?(?:the )?example for form ([1-9][0-9]{0,2})\s*[?.!]*\s*',
                                    question, re.I)
        if form_request:
            forms = source_cards.get(kc, {}).get('forms') or []
            index = int(form_request.group(1)) - 1
            form = forms[index] if index < len(forms) and isinstance(forms[index], dict) else {}
            text = form.get('example')
            if not isinstance(text, str) or not text.strip():
                self.say(cards.card('hint', 'Learning tutor', 'No example is available for that form.'))
                return
            if self.learning_answer_is_guarded(text):
                return
            self.remember_card_disclosures(session, [source_cards.get(kc, {})])
            self.say(cards.you(question))
            self.say(cards.card('tutor', form.get('name', 'Worked example'), text))
            card = source_cards.get(kc, {})
            diagram = form.get('diagram')
            diagrams = card.get('diagrams') or []
            if isinstance(diagram, str) and diagram in diagrams:
                position = diagrams.index(diagram)
                descriptions = diagram_descriptions(card)
                description = descriptions[position] if position < len(descriptions) else 'Lesson diagram.'
                self.show_lesson_diagrams({'diagrams': [diagram], 'diagram_descriptions': [description]})
            self.remember_learning_exchange(session, kc, question, text)
            self.readable_now(text, auto=True, limit=tts.AI_SPEECH_LIMIT)
            return
        practice_request = re.fullmatch(r'\s*(?:try|practise|practice) form ([1-9][0-9]{0,2})\s*[?.!]*\s*',
                                        question, re.I)
        if practice_request:
            self.start_form_check(int(practice_request.group(1)) - 1, question, source_cards, kc)
            return
        if re.fullmatch(r"\s*(?:show|display) (?:me )?(?:the )?diagrams?\s*[?.!]*\s*", question, re.I):
            card = source_cards.get(kc, {})
            if card.get("diagrams"):
                self.remember_card_disclosures(session, [card])
                self.say(cards.you(question))
                if not self.show_lesson_diagrams(card):
                    return
                descriptions = diagram_descriptions(card)
                text = "\n".join(x for x in descriptions if isinstance(x, str)) or "Lesson diagrams shown."
                self.remember_learning_exchange(session, kc, question, text)
            else:
                self.say(cards.card("hint", "Diagram", "There is no diagram for this idea yet."))
            return
        invitation = learn_reply.try_first(question, kc, source_cards.get(kc, {}), session, self.tutor.state)
        if invitation:
            if self.learning_answer_is_guarded(invitation):
                return
            self.remember_card_disclosures(session, [source_cards.get(kc, {})])
            self.say(cards.you(question))
            self.say(cards.ai(normalise_visual(invitation)))
            self.remember_learning_exchange(session, kc, question, invitation)
            self.readable_now(invitation, auto=True, limit=tts.AI_SPEECH_LIMIT)
            return
        index = learn_reply.relevant_form_suggestion(question, source_cards.get(kc, {}))
        if index is not None:
            form = source_cards[kc]['forms'][index]
            text = (f"A possibly related form is **{form['name']}** (form {index + 1}). "
                    f"Ask ‘Show example for form {index + 1}’ to see a worked example, "
                    f"or ‘Try form {index + 1}’ to practise it.")
            if self.learning_answer_is_guarded(text):
                return
            self.say(cards.you(question))
            self.say(cards.card('tutor', 'Relevant question form', text))
            self.remember_learning_exchange(session, kc, question, text)
            return
        failure = "The tutor could not respond."
        data = (learn_reply.active_misconception_selection(
                    question, kc, source_cards, self.tutor.state,
                    prerequisites=self.tutor.packs.kcs.get(kc, {}).get('prereqs') or [])
                or learn_reply.exact_term_selection(question, kc, source_cards))
        if data == {'sections': []}:
            self.say(cards.card("hint", "Learning tutor", "No recorded misconception with an available teaching explanation was found for that request."))
            return
        model_selection = data is None
        if data is None:
            context = prompts.learn(self.tutor, kc, question)
            # Keep the idea and learner profile even when the general session context is long.
            recent_questions, _, idea_context = context.partition("\n\nLESSON IDEA:")
            figures = ta.figures_for(self.app.vault, self.tutor.packs.kcs.get(kc, {}).get("subtopic", ""),
                                     kc=kc, card=source_cards.get(kc, {}))
            prompt = (learn_reply.selection_prompt(question, source_cards, idea_context or context, previous,
                                                    recent_questions=recent_questions if idea_context else "")
                      + "\n\n" + ta.catalogue(source_cards.get(kc, {}), figures))
            with LocalActivity(self, model_name, task="Finding teaching material"):
                data, result = await self.app.ai.one_shot(prompt, schema=learn_reply.CARD_SELECTION_SCHEMA,
                                                          model=model_name, think=think,
                                                          system="You are a careful A-level tutor. Follow the requested structured "
                                                                 "response format, teach in British English, and never "
                                                                 "invent mathematical steps or reveal an open answer.",
                                                          **image_for_local(self.tutor, model_name))
            if not result.ok:
                data = None
                failure = result.message or "The tutor could not respond."
        def current_request():
            return (self.is_current and self.tutor.session is session and self.act is act and self.kc == kc
                    and not session.get('presented') and not session.get('queue')
                    and not session.get('faded_cancel_intent')
                    and session.get('count', 0) == question_count)

        if not current_request() or self.learning_answer_is_guarded(''):
            return
        if model_selection and isinstance(data, dict) and "actions" in data:  # the AI asked for teaching actions
            for req in [r for r in data["actions"] if isinstance(r, dict) and r.get("action") == "write"][:1]:
                req["text"], req["checked"], req["unchecked"] = "", [], 0
                with LocalActivity(self, model_name, task="Writing an explanation"):
                    doc, wrote = await self.app.ai.one_shot(
                        learn_write.prompt(question, str(req.get("topic") or question), idea_context or context,
                            learner_context=f"Lesson goal: {lesson.GOALS.get(session.get('goal'), 'Not chosen yet')}\n"
                                            + previous[-3500:]),
                        schema=learn_write.SCHEMA, model=model_name, think=think,
                        system="You are a careful A-level tutor. Follow the requested structured response format and "
                               "teach in British English.", **image_for_local(self.tutor, model_name))
                # A question, retry guard or new activity may have arrived while
                # the writer was running. Never apply a stale reply or figure.
                if not current_request() or self.learning_answer_is_guarded(''):
                    return
                try:
                    if not wrote.ok:
                        raise ValueError(wrote.message or "the AI did not reply")
                    req.update(learn_write.lay_out(doc))
                except ValueError as exc:  # includes DocumentError
                    req["problem"] = f"I could not write that explanation ({exc}), so I am not showing it."
            blocked = ('Finish the pending questions before talking through the idea.'
                       if not current_request() else
                       'A skipped answer is protected; retry it before asking for an explanation.'
                       if prompts.guard_keys(self.tutor) or prompts.skipped_guards(self.tutor) else None)
            if blocked:
                return
            results = ta.run(data["actions"], card=source_cards.get(kc, {}), kc=kc,
                             subtopic=self.tutor.packs.kcs.get(kc, {}).get("subtopic", ""), vault_root=self.app.vault,
                             figures=figures, blocked=blocked)
            if not current_request() or self.learning_answer_is_guarded(
                    '\n'.join(str(result.get('body') or '') for result in results)):
                return
            self.remember_card_disclosures(session, [source_cards.get(kc, {})])
            shown = self.show_teach_results(question, results, kc, source_cards)
            self.remember_learning_exchange(session, kc, question, shown or "(an activity)")
            return
        text, problem = learn_reply.render_related_selection(data, source_cards) if data is not None else ("", failure)
        if problem:
            self.say(cards.card("hint", "Learning tutor paused", problem))
            return
        # Keep whole, validated sections intact; never cut a mathematical explanation mid-step.
        explicit_detail = bool(re.search(r'\b(?:detail|detailed|thorough|in depth)\b', question, re.I))
        continuation = None
        if model_selection and len(data['sections']) > 1 and not explicit_detail:
            sections = data['sections']
            initial = [s for i, s in enumerate(sections) if i == 0 or s.partition('|')[2] == 'plain_words']
            remaining = [s for s in sections if s not in initial]
            data = {'sections': initial}
            text, problem = learn_reply.render_related_selection(data, source_cards)
            if problem:
                return
            if remaining:
                fingerprint = hashlib.sha256(json.dumps(source_cards, sort_keys=True, ensure_ascii=False,
                                                        separators=(',', ':')).encode()).hexdigest()
                continuation = {'session': session.get('id'), 'kc': kc, 'cards': fingerprint, 'sections': remaining}
                text += '\n\nAsk “More detail” to see the rest.'
        if self.learning_answer_is_guarded(text):
            return
        selected_cards = [source_cards[section.partition('|')[0]] for section in data['sections']]
        self.remember_card_disclosures(session, selected_cards)
        self.say(cards.you(question))
        self.say(cards.ai(normalise_visual(text)))
        self.remember_selected_terms(data['sections'], source_cards)
        self.remember_learning_exchange(session, kc, question, text)
        if continuation:
            session['learn_detail'] = continuation
            self.tutor._save()
        self.readable_now(text, auto=True, limit=tts.AI_SPEECH_LIMIT)

    def action_ask(self) -> None:
        if self.query('#learning-question'):
            self.action_learn_tutor()
            return
        def got(q: str | None) -> None:
            if q:
                self.say(cards.you(q))
                self.stream(prompts.ask(self.tutor, q, self.kc), web_query=q)
        notice = ("Ask receives the question text and first image only. Read all pages in Obsidian."
                  if prompts.focus_page_count(self.tutor) > 1 else None)
        self.app.push_screen(AskScreen(notice=notice), got)

    def action_retry_skipped(self) -> None:
        activity = self.tutor.retry_skipped()
        if activity.get("activity") != "questions":
            if ((self.tutor.session or {}).get('suspended_for_retry')
                    and not (self.tutor.session or {}).get('presented')):
                self.panel(ContinuePanel('Your pending questions remain saved in this session.',
                                         buttons=[('retry-skipped', 'Retry skipped question'),
                                                  ('resume-suspended', 'Return to saved questions'),
                                                  ('leave', 'Return to menu')]))
            candidate = activity.get('restore_candidate')
            ungraded = self.tutor.ungraded_retry_candidate()
            def try_ungraded():
                retry = self.tutor.retry_skipped_ungraded(ungraded['guard'])
                if retry.get('activity') == 'questions':
                    self.act = retry
                    self.ask_question(retry['items'][0], 'Your attempt will be saved without marking. Prerequisite support is not shown.')
                    self.update_bar()
                else:
                    self.app.notify(retry.get('error', 'Retry is unavailable.'), timeout=5)
            if candidate:
                def restore(choice):
                    if choice == 'restore':
                        result = self.tutor.restore_topical(**candidate)
                        if result.get('ok'):
                            retry = self.tutor.retry_skipped(**candidate, guard_id=activity.get('restore_guard'))
                            if retry.get('activity') == 'questions':
                                self.act = retry
                                self.ask_question(retry['items'][0], 'Try the skipped question again.')
                                self.update_bar()
                            else:
                                self.app.notify(retry.get('error', 'Retry is unavailable.'), timeout=5)
                        else:
                            self.app.notify(result.get('error', 'Could not restore this question.'), timeout=5)
                    elif choice == 'ungraded' and ungraded:
                        try_ungraded()
                choices = [('restore', 'Restore and retry'), ('cancel', 'Keep excluded')]
                if ungraded:
                    same_question = ungraded['guard'] == activity.get('restore_guard')
                    label = ('Try without marking' if same_question else
                             f"Try {ungraded['item']} without marking")
                    choices.append(('ungraded', label))
                self.app.push_screen(ConfirmScreen(
                    f"Question {candidate['identity']} was excluded from {candidate['chapter']}. Restore it to retry? "
                    "It may appear in that chapter again."
                    + (f" Question: {activity['restore_stem']}" if activity.get('restore_stem') else '')
                    + ((" Trying without marking keeps it excluded." if same_question else
                        f" The ungraded option is for {ungraded['item']}: {ungraded['stem']}")
                       + " Prerequisite support is not shown." if ungraded else ''),
                    choices), restore)
                return
            if ungraded:
                self.app.push_screen(ConfirmScreen(
                    activity.get('error', 'The skipped question is unavailable.') +
                    f" Save an unmarked attempt for {ungraded['item']}: {ungraded['stem']}? "
                    "Exclusions remain in place; prerequisite support is not shown and marking may require later review.",
                    [('cancel', 'Cancel'), ('ungraded', 'Try without marking')]),
                    lambda choice: try_ungraded() if choice == 'ungraded' else None)
                return
            self.app.notify(activity.get("error", "Retry is unavailable."), timeout=5)
            return
        self.act = activity
        self.ask_question(activity["items"][0], "Try the skipped question again.")
        self.update_bar()

    def action_explain(self) -> None:
        if self.query('#learning-question'):
            self.learn_request('Can you explain this idea another way, using what I have said so far?')
            return
        if self.kc:
            self.say(cards.you("Explain this idea again, a different way."))
            self.stream(prompts.explain_again(self.tutor, self.kc), mode="explain")

    @on(Button.Pressed, "#check-solvable")
    def check_solvable_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        self.action_check_solvable()

    def action_check_solvable(self) -> None:
        if not self.view or str(self.view["n"]) not in (self.tutor.session or {}).get("presented", {}):
            return
        result = self.tutor.check_solvable(self.view["n"])
        self.say(cards.card("tutor", "Can I solve this?", result["message"]), mirror=None)
        if result["status"] == "skipped":
            self.advance()

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
            self.say(cards.card("hint", f"Hint {h.get('level', '')} for Q{self.view['n']}", h.get("hint", ""), ai_output=self.visual),
                     mirror=None)  # the engine put it on Now and in the log
            self.readable_now(h.get("hint", ""))  # ctrl+e reads it

    def action_obsidian(self) -> None:
        mac.open_in_obsidian(self.app.vault, "Now", background=False)

    def action_leave(self) -> None:
        pending = bool(getattr(self, "pending_short", None))
        marking = isinstance(getattr(self, "showing", None), TickPanel) or getattr(self, "long_mark_pending", False)
        typed = "answer and mark choices" if pending else "mark choices" if marking else "answer"
        leave_asking_first(self, "#panel TextArea", typed, unsaved=pending or marking)

    def action_esc(self) -> None:
        """Esc means "back" everywhere else; here a panel may use it (change an answer, skip), and leaving is ctrl+b."""
        self.hush()
        if time.monotonic() - getattr(self, "esc_told", -9.0) >= 4:  # said once while it shows, not a stack of them
            self.esc_told = time.monotonic()
            self.app.notify("ctrl+b saves and returns to the menu.", timeout=4)

    def finish(self) -> None:
        summary = self.tutor.end()
        if summary.get('error'):
            self.app.notify(summary['error'], severity='warning', timeout=6)
            return
        if summary.get('home_error'):
            self.app.notify(f"Session saved, but Home could not be updated: {summary['home_error']}",
                            severity='warning', timeout=6)
        if summary.get('view_errors'):
            failed = "; ".join(f"{name}: {error}" for name, error in summary['view_errors'].items())
            self.app.notify(f"Session saved, but some notes could not be updated: {failed}",
                            severity='warning', timeout=10)
        try:
            from tutorlib import weekly
            # Today/Profile notes, experiments, Anki export when due
            summary["week"] = weekly.run(self.tutor, self.app.settings.minutes)
        except Exception as exc:  # bookkeeping must never cost you the session
            summary["week"] = {"error": str(exc)}
        self.app.switch_screen(SummaryScreen(summary))  # closing the summary lands back on the menu


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
        self._chat_ready = False
        self._chat_reset_done = asyncio.Event()
        self.run_worker(self._reset_chat(), group="reset")

    async def _reset_chat(self) -> None:
        try:
            await self.app.ai.reset()  # finish revoking the old conversation before starting a new preload
            self._chat_ready = True
            if self.is_current:
                self.app.prepare_local_ai("ask")
        finally:
            self._chat_reset_done.set()

    def on_screen_resume(self) -> None:
        if (getattr(self, "_chat_ready", False) and self.is_current
                and getattr(self.app, "_preload_owner", None) is not self):
            self.app.prepare_local_ai("ask")  # Settings and other pop-ups suspend this screen's preparation

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
        self.app.tutor.show("you", q, "You")  # each card here goes to Now as drawn
        self.hush()
        self.reply(q)

    @work(exclusive=True)
    async def reply(self, q: str) -> None:
        a = self.app.ai
        t = self.app.tutor
        log = self.query_one("#log", VerticalScroll)
        if not self.app.ai_available("ask"):
            message = a.problem_for(self.app.settings.ai_for("ask")[0]) if self.app.settings.ai else "Switch AI on in Settings."
            log.mount(Static(cards.card("hint", "AI help is off", message), classes="entry"))
            self.app.tutor.show("hint", message, "AI help is off")
            log.scroll_end(animate=False)
            return
        if prompts.skipped_guards(t):
            message = "A skipped question is still protected. Start or resume a lesson and press ctrl+u to retry it."
            log.mount(Static(cards.card("hint", "Tutor paused", message), classes="entry"))
            t.show("hint", message, "Tutor paused")
            log.scroll_end(animate=False)
            return
        if (help_ := t.ai_help(given=False)).get("refused"):
            log.mount(Static(cards.card("hint", "No help on this one", help_["refused"]), classes="entry"))
            t.show("hint", help_["refused"], "No help on this one")
            log.scroll_end(animate=False)
            return
        w = Static(cards.ai("…"), classes="entry")
        log.mount(w)
        buf = ""
        # A paused session keeps its answer guard, including while a reply is streaming.
        keys = prompts.guard_keys(t)
        skipped = bool(prompts.skipped_guards(t))
        model, think = self.app.settings.ai_for("ask")
        image = prompts.focus_image(t)
        with LocalActivity(self, model, w) as live:
            if local_models.is_local(model):
                await self._chat_reset_done.wait()  # cancelling one reply must not cancel the shared reset
                if not self._chat_ready or self not in self.app.screen_stack:
                    raise asyncio.CancelledError
            async for chunk in a.stream(prompts.ask(self.app.tutor, q, None), model=model, think=think,
                                         **({"web_query": q} if local_models.is_local(model) else {}),
                                         **({"image": image} if image is not None else {})):
                buf += chunk
                if not keys and not skipped and live.update(buf):
                    log.scroll_end(animate=False)
        if not a.last.ok:
            w.update(cards.card("hint", "AI paused", a.last.message))
            self.app.tutor.show("hint", a.last.message, "AI paused")
        else:
            buf = a.last.text or buf
            speech = a.last.speech
            withheld = skipped or any(ai_mod.leaks(buf, *k) or (speech and ai_mod.leaks(speech, *k)) for k in keys)
            if withheld:
                buf = ("I can't give that away while the question is open. Answer first and I'll explain."
                       if (t.session or {}).get("presented") else
                       "I can't give away the answer to a skipped question before an attempt. Start or resume a lesson and press ctrl+u to retry it.")
                speech = ""
            buf = normalise_visual(buf)
            if not buf.strip() and not (speech or "").strip():
                message = "The AI returned an empty reply. Try asking again."
                w.update(cards.card("hint", "No AI reply", message))
                t.show("hint", message, "No AI reply")
                log.scroll_end(animate=False)
                return
            w.update(cards.ai(buf))
            if buf and not withheld:
                t.ai_help()
            t.show("ai", buf, "Tutor (AI)")
            self.readable_now(speech or buf, auto=True, limit=tts.AI_SPEECH_LIMIT)
        log.scroll_end(animate=False)


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
        summary = report.load_ai_summary(t)
        # Keep the AI section out of the authored report's common-font converter.
        marker = "STEMTUTORVISUALSUMMARY"
        report_text = report.insights_markdown(t, {**summary, "text": marker} if summary else None)
        while marker in report.insights_markdown(t):
            marker += "X"
            report_text = report.insights_markdown(t, {**summary, "text": marker} if summary else None)
        rendered = self._for_terminal(report_text)
        if summary:
            rendered = rendered.replace(marker, terminal_visual(summary["text"]).replace("\n", "\n> "))
        return (rendered + "\n---\n\n**a** asks the "
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
        if not self.app.ai_available("explain"):
            self.app.notify("The AI tutor is off or unavailable right now (Settings: F2 on the menu).",
                            severity="warning")
            return
        self.app.notify("Asking the AI tutor to explain your profile…", timeout=4)
        self._summarise()

    @work(exclusive=True, group="profile-ai")
    async def _summarise(self) -> None:
        from tutorlib.store import write_json
        t = self.app.tutor
        model, think = self.app.settings.ai_for("explain")
        if not local_models.is_local(model) and not codex_models.is_codex(model):
            think = False
            if not local_models.is_local(self.app.ai.model) and not codex_models.is_codex(self.app.ai.model):
                model = None  # Claude summaries keep their original default model and non-thinking behaviour.
        with LocalActivity(self, model, task="Explaining your profile"):
            data, res = await self.app.ai.one_shot(prompts.profile_summary(report.insights_markdown(t)),
                                                   schema=prompts.PROFILE, model=model, think=think)
        if not (data and data.get("summary")):
            self.app.notify(res.message or "The AI tutor couldn't write a summary just now.", severity="warning")
            return
        try:
            write_json(self.app.vault / ".tutor" / "profile_ai.json", {"text": data["summary"], "at": t.now().isoformat()})
        except OSError as exc:
            self.app.notify(f"The AI summary could not be saved: {exc}", severity="warning", timeout=8)
            return
        try:
            report.profile_note(t)
        except OSError as exc:
            self.app.notify(f"AI summary saved, but Profile could not be updated: {exc}",
                            severity="warning", timeout=8)
        document = self.query_one("#insights", Markdown)
        await document.update(self._text())
        document.goto_anchor("ai-summary")

    def action_open(self, note: str) -> None:
        open_report_note(self, note)

    def action_weekly(self) -> None:
        folder = self.app.vault / "Weekly"
        weeks = sorted(folder.glob("*.md")) if folder.exists() else []
        if not weeks:
            self.app.notify("No week in review yet: the first appears when the tutor opens in a new week.", timeout=6)
            return
        mac.open_in_obsidian(self.app.vault, f"Weekly/{weeks[-1].stem}", background=False)


class SavedAttemptsScreen(Screen):
    """Show the learner's postponed work without displaying marking keys or unpinned images."""
    BINDINGS = [Binding('escape', 'app.pop_screen', 'Back')]

    def compose(self) -> ComposeResult:
        with VerticalScroll():
            yield Static(Text('Saved attempts awaiting review', style='bold'))
            yield Static(Text('Eligible text-only attempts return in a later session. Esc goes back.'))
            for number, item in enumerate(self.app.tutor.postponed_judgments(), 1):
                inst = item.get('inst') or {}
                yield Static(Text(f'\nAttempt {number} · {item.get("serving_chapter") or "Saved topic"}', style='bold'))
                yield Static(Text(to_terminal(str(inst.get('stem') or 'Question text unavailable'))))
                if inst.get('image') or inst.get('images'):
                    yield Static(Text('The original image needs review before this attempt can be marked.'))
                yield Static(Text('Your working:\n' + str(item.get('saved_work') or '')))
            drafts = self.app.tutor.retained_drafts()
            if drafts:
                yield Static(Text('\nEarlier draft copies', style='bold'))
                yield Static(Text('These copies were retained when a saved draft changed.'))
                for number, versions in enumerate(drafts.values(), 1):
                    for version, text in enumerate(versions, 1):
                        yield Static(Text(f'\nDraft {number}.{version}\n{text}'))
        yield Footer()


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
        open_report_note(self, "Profile")


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
                                    "ideas already scheduled for Review that you miss are brought forward; ideas without a "
                                    "review schedule can be worked through in a lesson."), classes="entry")
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
        boxes = self.query("#blurt")
        text = boxes.first(TextArea).text.strip() if boxes else ""
        if not text or getattr(self, "checked", False):  # a second ctrl+s or click while the box is going: once only
            return
        t = self.app.tutor
        res = t.blurt(self.subtopic, text)
        if res.get("error"):
            self.app.notify(res["error"], severity="warning", timeout=6)
            boxes.first(TextArea).focus()
            return
        self.checked = True
        self.query_one("#check", Button).disabled = True
        log = self.query_one("#log", VerticalScroll)
        n, total = len(res["recalled"]), len(res["ideas"])
        for role, title, body in res["cards"]:  # the cards the lesson log and Now have
            log.mount(Static(cards.you(body, title) if role == "you" else cards.card(role, title, body), classes="entry"))
        log.scroll_end(animate=False)
        left_out = [v["title"] for v in res["ideas"].values() if not v["recalled"]]
        self.readable_now(f"You recalled {n} of {total} ideas."
                          + (" You left out: " + "; ".join(left_out) + "." if left_out else ""), auto=True)
        box = self.query_one("#panel", Container)
        box.remove_children()
        box.mount(Static("Esc for the menu. Your blurt and results are saved in Lessons in Obsidian.", classes="hint"))


class HelpScreen(ModalScreen):
    pauses_study = True
    BINDINGS = [Binding("escape", "dismiss(None)", "Close"), Binding("enter", "dismiss(None)", "Close"),
                Binding("o", "guide", "Open the full guide")]

    def compose(self) -> ComposeResult:
        text = """_↑↓ to scroll · Esc or ⏎ closes_
# Keys
**↑ ↓** move · **⏎** choose / continue · **A–D** pick an option · **0** I don't know · **1–4** confidence
(1 guess, 2 unsure, 3 fairly sure, 4 certain) · **space** tick a box

**⌥+** / **⌥−** text bigger or smaller, **⌥0** normal size: kept for next time (Terminal's own ⌘+ / ⌘− zoom cannot
be read while the tutor runs, so it is only guessed when you quit).

**ctrl+k** (or **F3**) answer-only view: hides the question and shows just the answer box, for a window beside
Obsidian; press it again to bring the question back · **ctrl+t** ask the tutor (AI) · **ctrl+r** explain this idea again, differently (AI) · **ctrl+y** Can I solve this? (prerequisite topic numbers only) · **ctrl+g** hint (not on
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
    pauses_study = True
    BINDINGS = [Binding("escape", "dismiss(None)", "Close")]

    def compose(self) -> ComposeResult:
        s = self.app.settings
        self._answer_only_touched = False
        self._font_size_touched = False
        self._font_size_synced = str(self.app.text_size() or "")
        self._local_models = local_models.available_models()
        self._selected_models = {mode: s.ai_for(mode)[0] for mode in config.AI_MODES}
        self._efforts = {mode: getattr(s, f"ai_{mode}_effort") for mode in config.AI_MODES}
        self._strength_models, self._strength_values = {}, {}
        self._requested_preset = presets.matching({mode: s.ai_for(mode) for mode in config.AI_MODES})
        self._applied_preset = self._requested_preset
        choices = self._model_choices()
        available = {value for _, value in choices}
        with VerticalScroll(id="settings"):  # a short window scrolls to Save instead of cutting it off
            yield Static("Settings (saved in your tutor folder)", classes="title")
            for key, label in (("ai", "AI tutor (asking, explaining, judging written answers)"),
                               ("own_words_feedback", "AI comments on your 'in your own words' answers"),
                               ("open_obsidian", "Show Now in Obsidian when a session starts"),
                               ("answer_only", "Answer-only view: hide the question here, show just the answer box (ctrl+k)")):
                with Horizontal(classes="row"):
                    yield Switch(value=getattr(s, key), id=key)
                    yield Static(label)
            with Horizontal(classes="row ai-row"):
                yield Static("AI preset")
                yield Select(self._preset_choices(), value=self._requested_preset
                             if self._requested_preset in self._available_presets() else Select.NULL,
                             prompt="Choose a preset" if self._requested_preset in self._available_presets()
                             else "Reconnect LocalAI SSD", id="ai_preset", allow_blank=True, compact=True)
                yield Button("Apply", id="apply-preset", compact=True)
            yield Static("", id="preset-status", classes="hint")
            yield Static("", id="preset-preview", classes="hint")
            with Collapsible(title="Model guide", collapsed=True, collapsed_symbol="▸", expanded_symbol="▾",
                             id="model-guide"):
                yield Static("AI for each kind of help: the model, and whether it thinks first. Haiku without thinking "
                             "is fastest and uses least of your limit; Sonnet about 3x, Opus about 5x; thinking first is "
                             "slower and can use several times as much again. Local models appear while your LocalAI SSD "
                             "is connected; they use this Mac's RAM and no Claude allowance. ChatGPT choices use your "
                             "Codex sign-in and ChatGPT limits; think first selects high reasoning, otherwise low. "
                             "GPT-OSS offers Low, Medium and High reasoning; Qwen 27B offers Off, Low, Medium and "
                             "Maximum (xhigh). DeepSeek R1 and Liquid LFM2.5 always think first. "
                             "Local thinking can take much longer before the first answer appears.", classes="hint")
            for mode, label in (("mark", "Marking answers"), ("explain", "Explaining"), ("ask", "Ask the tutor"),
                                ("learn", "Learning tutor")):
                model, think = s.ai_for(mode)
                with Horizontal(classes="row ai-row task-row"):
                    yield Switch(value=getattr(s, f"ai_{mode}_think"), id=f"ai_{mode}_think")
                    yield Select([("Low", "low")], id=f"ai_{mode}_effort", allow_blank=False, compact=True, classes="strength")
                    yield Static(f"{label}: think first", id=f"ai_{mode}_label")
                    yield Select(choices, value=model if model in available else Select.NULL,
                                 prompt="Model: keep saved model" if model in available else "Model: reconnect LocalAI SSD",
                                 id=f"ai_{mode}_model", allow_blank=True, compact=True)
            with Horizontal(classes="row"):
                yield Switch(value=s.local_web, id="local_web")
                yield Static("Local AI: web sources when needed (sends only your question to search)")
            with Horizontal(classes="row ai-row"):
                yield Static("Resource indicator")
                yield Select([("Weekly usage", "weekly"), ("RAM usage", "ram"),
                              ("Weekly usage and RAM", "both")], value=s.usage_display,
                             id="usage_display", allow_blank=False, compact=True)
            with Horizontal(classes="row"):
                yield Select([(f"Look: {look.LABELS[name]}", name) for name in config.THEMES],
                             value=s.theme, id="theme", allow_blank=False, compact=True)
            with Horizontal(classes="row"):
                yield Static("Text size (points; ⌥+ ⌥− ⌥0 anywhere)")
                yield Input(self._font_size_synced, id="font_size", type="integer", compact=True)
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
                yield Static(f"Reading speed ({tts.SPEED_RANGE[0]:g} to {tts.SPEED_RANGE[1]:g})")
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
        for mode in config.AI_MODES:
            self._update_thinking(mode)
        self._task_snapshot = self._task_choices()
        self._update_preset_preview()
        self._update_preset_status()
        self.query_one("#ai", Switch).focus()  # the first setting, not the scrolling box around them
        self.set_interval(1, self._refresh_models)

    def on_descendant_focus(self, event) -> None:
        if getattr(event.widget, "id", None) == "tts_volume":
            self.query_one("#settings", VerticalScroll).scroll_to_widget(
                self.query_one("#tts_volume").parent, top=True, animate=False, immediate=True
            )

    def sync_font_size(self, size: int) -> None:
        fields = self.query("#font_size")
        if not fields or self._font_size_touched:
            return
        field = fields.first(Input)
        if field.value != self._font_size_synced:
            return  # an explicit edit can precede its Changed message
        self._font_size_synced = str(size)
        with field.prevent(Input.Changed):
            field.value = self._font_size_synced

    @on(Input.Changed, "#font_size")
    def font_size_changed(self, event: Input.Changed) -> None:
        if event.value != self._font_size_synced:
            self._font_size_touched = True

    def _model_choices(self) -> list[tuple[str, str]]:
        return (MODEL_CHOICES + [(f"Model: {local_models.LOCAL_MODELS[name]}", name) for name in self._local_models]
                + [(f"Model: {label}", name) for name, label in codex_models.CODEX_MODELS.items()])

    def _selected_model(self, mode: str) -> str:
        selected = self.query_one(f"#ai_{mode}_model", Select).value
        return self._selected_models[mode] if selected is Select.NULL else str(selected)

    def _task_choices(self) -> dict[str, tuple[str, bool | str]]:
        return {mode: (self._selected_model(mode), self._efforts[mode]
                       if local_models.thinking_levels(self._selected_model(mode)) and self._efforts[mode]
                       else self.query_one(f"#ai_{mode}_think", Switch).value)
                for mode in config.AI_MODES}

    def _update_thinking(self, mode: str, chosen: bool = False) -> None:
        model = self._selected_model(mode)
        supported = not local_models.is_local(model) or local_models.supports_thinking(model)
        required = local_models.always_thinks(model)
        thinking = self.query_one(f"#ai_{mode}_think", Switch)
        strength = self.query_one(f"#ai_{mode}_effort", Select)
        levels = local_models.thinking_levels(model)
        thinking.display, strength.display = not levels, bool(levels)
        label = {"mark": "Marking answers", "explain": "Explaining", "ask": "Ask the tutor", "learn": "Learning tutor"}[mode]
        if levels and self.app.size.width < 76:
            label = {"mark": "Marking", "explain": "Explaining", "ask": "Ask tutor", "learn": "Learning"}[mode]
        else:
            label = f"{label}:" if levels else f"{label}: think first"
        self.query_one(f"#ai_{mode}_label", Static).update(label)
        if levels:
            if self._strength_models.get(mode) != model:
                strength.set_options([("Maximum" if level == "xhigh" else level.title(), level) for level in levels])
                self._strength_models[mode] = model
            effort = self._efforts[mode]
            value = local_models.thinking_value(model, effort if effort in levels else thinking.value)
            self._strength_values[mode] = "off" if value is False else value
            strength.value = self._strength_values[mode]
            strength.tooltip = ("Reasoning strength. Maximum uses native xhigh and can take several minutes on this Mac."
                                if model == "ollama:qwen3.8:27b" else "Native reasoning strength: Low, Medium or High.")
        if required:
            thinking.value = True
        elif chosen and not supported:
            thinking.value = False  # opening Settings or saving another field never rewrites an old choice
        thinking.disabled = required or not supported and not thinking.value
        thinking.tooltip = ("This model always thinks before answering." if required else None if supported else
                            "This model has no thinking mode. You can turn off a saved On choice.")

    def _available_presets(self) -> list[str]:
        return ["custom", *presets.available(self._local_models)]

    def _preset_choices(self) -> list[tuple[str, str]]:
        return [("Custom task choices", "custom"),
                *[(presets.PRESETS[name].label, name) for name in presets.available(self._local_models)]]

    def _update_preset_status(self) -> None:
        label = presets.PRESETS[self._applied_preset].label if self._applied_preset in presets.PRESETS else "Custom"
        self.query_one("#preset-status", Static).update(f"Current AI setup: {label}. Save keeps it.")

    def _update_preset_preview(self) -> None:
        preset = presets.PRESETS.get(self._requested_preset)
        enabled = bool(preset and presets.is_available(self._requested_preset, self._local_models))
        self.query_one("#apply-preset", Button).disabled = not enabled
        if preset is None:
            text = "Choose a preset to preview it. Apply changes these AI choices; Save keeps them."
            choices = self._task_choices()
        else:
            text = "Preview only. Apply sets task choices; Save keeps them.\n" + preset.description
            choices = {mode: preset.ai_for(mode) for mode in config.AI_MODES}
            if not enabled:
                text = "Reconnect LocalAI SSD: this preset needs every listed local model. " + text
        for mode, label in (("mark", "Marking"), ("explain", "Explaining"), ("ask", "Ask the tutor"),
                            ("learn", "Learning tutor")):
            model, think = choices[mode]
            thinking = f"thinking {'on' if think else 'off'}"
            if local_models.is_local(model) and not local_models.supports_thinking(model):
                thinking = "thinking unavailable" + (" (saved on)" if think else "")
            elif local_models.thinking_levels(model):
                value = local_models.thinking_value(model, think)
                name = "off" if value is False else "maximum (xhigh)" if value == "xhigh" else value
                thinking = f"{name} reasoning"
            elif codex_models.is_codex(model):
                thinking = f"{'high' if think else 'low'} reasoning"
            text += f"\n{label}: {presets.model_label(model)} · {thinking}"
        preview = self.query_one("#preset-preview", Static)
        preview.update(text)
        preview.display = self._requested_preset != self._applied_preset or bool(preset and not enabled)

    def _refresh_presets(self) -> None:
        selected = self.query_one("#ai_preset", Select)
        available = self._requested_preset in self._available_presets()
        selected.prompt = "Choose a preset" if available else "Reconnect LocalAI SSD"
        selected.set_options(self._preset_choices())
        selected.value = self._requested_preset if available else Select.NULL
        self._update_preset_preview()

    @on(Select.Changed, "#ai_preset")
    def preset_selected(self, event: Select.Changed) -> None:
        if not hasattr(self, "_task_snapshot") or event.value != event.select.value:
            return
        if event.value is not Select.NULL:
            self._requested_preset = str(event.value)
        elif self._requested_preset in self._available_presets():
            self._requested_preset = "custom"
            event.select.value = "custom"
        self._update_preset_preview()

    @on(Switch.Changed, "#answer_only")
    def answer_only_changed(self, event: Switch.Changed) -> None:
        self._answer_only_touched = True

    @on(Select.Changed)
    @on(Switch.Changed)
    def task_choice_changed(self, event) -> None:
        if not hasattr(self, "_task_snapshot") or event.control.id not in {
                f"ai_{mode}_{field}" for mode in config.AI_MODES for field in ("model", "think", "effort")}:
            return
        if isinstance(event, Select.Changed) and event.value != event.select.value:
            return
        if isinstance(event, Select.Changed) and event.control.id.endswith("_model"):
            mode = next(mode for mode in config.AI_MODES if event.control.id == f"ai_{mode}_model")
            chosen = self._selected_model(mode) != self._task_snapshot[mode][0]
            if chosen:
                self._efforts[mode] = ""
            self._update_thinking(mode, chosen=chosen)
        elif isinstance(event, Select.Changed):
            mode = next(mode for mode in config.AI_MODES if event.control.id == f"ai_{mode}_effort")
            if (not local_models.thinking_levels(self._selected_model(mode)) or event.value is Select.NULL
                    or event.value == self._strength_values.get(mode)):
                return
            self._efforts[mode] = self._strength_values[mode] = str(event.value)
        else:
            mode = next(mode for mode in config.AI_MODES if event.control.id == f"ai_{mode}_think")
            self._update_thinking(mode)
        choices = self._task_choices()
        if choices == self._task_snapshot:
            return  # mounting, applying and SSD refreshes also emit selection events
        self._task_snapshot = choices
        self._applied_preset = self._requested_preset = "custom"
        self.query_one("#ai_preset", Select).value = "custom"
        self._update_preset_preview()
        self._update_preset_status()

    @on(Button.Pressed, "#apply-preset")
    def apply_preset(self) -> None:
        self._refresh_models()  # recheck a drive removed immediately before Apply
        if (self._requested_preset not in presets.PRESETS
                or not presets.is_available(self._requested_preset, self._local_models)):
            self._update_preset_preview()
            return
        preset = presets.PRESETS[self._requested_preset]
        for mode in config.AI_MODES:
            model, think = preset.ai_for(mode)
            self._selected_models[mode] = model
            self.query_one(f"#ai_{mode}_model", Select).value = model
            self._efforts[mode] = think if isinstance(think, str) else ""
            if isinstance(think, bool):
                self.query_one(f"#ai_{mode}_think", Switch).value = think
            self._update_thinking(mode, chosen=True)
        self._task_snapshot = self._task_choices()
        self._applied_preset = self._requested_preset
        self._update_preset_status()
        self._update_preset_preview()

    def _refresh_models(self) -> None:
        """A drive can arrive after launch; unchanged options leave the open dropdown and focus alone."""
        available = local_models.available_models()
        if available == self._local_models:
            return
        self._local_models = available
        choices = self._model_choices()
        valid = {value for _, value in choices}
        for mode in config.AI_MODES:
            select = self.query_one(f"#ai_{mode}_model", Select)
            selected = self._selected_model(mode)
            self._selected_models[mode] = selected  # an unavailable choice stays local until explicitly replaced
            select.prompt = "Model: keep saved model" if selected in valid else "Model: reconnect LocalAI SSD"
            select.set_options(choices)
            select.value = selected if selected in valid else Select.NULL
            self._update_thinking(mode)
        self._refresh_presets()

    def on_resize(self) -> None:
        self._fit()
        if hasattr(self, "_task_snapshot"):
            for mode in config.AI_MODES:
                self._update_thinking(mode)

    def _fit(self) -> None:
        """A short window gets tighter rows and a one-line Save, so everything fits and Save is never cut off."""
        short = self.app.size.height < 30
        self.set_class(short, "short")
        self.set_class(self.app.size.width >= 100, "wide")
        self.set_class(self.app.size.width < 76, "narrow")
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
        self._refresh_models()  # reflect a drive removed just before Save, keeping the chosen local model
        s = self.app.settings
        old_speech, old_ai = s.tts_enabled, s.ai
        for key in ("ai", "own_words_feedback", "open_obsidian", "tts_enabled", "tts_auto", "local_web"):
            setattr(s, key, self.query_one(f"#{key}", Switch).value)
        answer_only = self.query_one("#answer_only", Switch).value
        if self._answer_only_touched:
            s.answer_only = answer_only  # an explicit modal edit takes precedence over a global shortcut
        s.tts_voice = str(self.query_one("#tts_voice", Select).value)
        s.usage_display = str(self.query_one("#usage_display", Select).value)
        try:
            s.tts_speed = round(min(tts.SPEED_RANGE[1], max(tts.SPEED_RANGE[0],
                                                           float(self.query_one("#tts_speed", Input).value))), 2)
        except ValueError:  # blank: the speed you had stays
            pass
        if (volume := self._typed_volume()) is not None:
            s.tts_volume = round(volume, 2)  # blank or not a number: the loudness you had stays
        old_model, old_minutes, typed = s.model, s.minutes, self.query_one("#minutes", Input).value.strip()
        for mode in config.AI_MODES:
            setattr(s, f"ai_{mode}_model", self._selected_model(mode))
            setattr(s, f"ai_{mode}_think", self.query_one(f"#ai_{mode}_think", Switch).value)
            setattr(s, f"ai_{mode}_effort", self._efforts[mode])
        s.model = s.ai_explain_model  # the general choice, for what has no row of its own (teaching cards, the profile summary)
        old_theme, s.theme = s.theme, str(self.query_one("#theme", Select).value)
        try:
            s.minutes = min(180, max(5, int(typed)))
        except ValueError:  # blank or not a number: the length you had stays
            self.app.notify(f"Session length kept at {s.minutes} minutes.", timeout=5)
        else:
            if s.minutes != old_minutes:
                self.app.notify(f"Session length set to {s.minutes} minutes"
                                + (" (5 to 180)." if str(s.minutes) != typed else "."), timeout=5)
        s.save(self.app.vault)
        typed_size = self.query_one("#font_size", Input).value.strip()
        if typed_size.isdigit() and self.app.font_base and int(typed_size) != self.app.text_size():
            self.app.set_text_size(int(typed_size))  # applied on the tab and kept at once
        self.app.ai.model, self.app.ai.think = s.ai_for("ask")  # the conversation started ahead is the one asked most
        self.app.ai.local_web = s.local_web
        if not s.ai or not any(local_models.is_local(s.ai_for(mode)[0]) for mode in config.AI_MODES):
            self.app.stop_local_preload()
            self.app.run_worker(self.app.ai.release_local(), group="local-release")
        speech = self.app.speech_wanted()
        if s.tts_enabled and not old_speech and not tts.available(self.app.vault):
            self.app.notify(tts.SETUP_HINT, timeout=8)
        if not s.tts_enabled:
            self.app.speaker.stop()
        if s.ai and not old_ai:
            self.run_worker(self.app.ai.warm(), group="reset")  # switched on: start the conversation ahead now
        if s.model != old_model or speech != self.app.ai.speech:
            self.app.ai.speech = speech  # the spoken version is asked for in the brief: a fresh process takes it
            self.run_worker(self.app.ai.reset(), group="reset")
        if s.theme != old_theme:
            look.apply(self.app, s.theme)  # the menu underneath redraws in it as this closes
        self.app.apply_answer_only()
        self.dismiss(None)
