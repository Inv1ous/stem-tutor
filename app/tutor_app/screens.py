"""Screens: Home, topic picker, the study session, summary, and small pop-ups (ask, help, settings)."""
from __future__ import annotations

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

from tutorlib import almanac, insights, model, policy, report, views
from tutorlib.lesson import GOALS

from . import ai as ai_mod
from . import cards, config, mac, prompts
from . import __version__
from .panels import (ChoicePanel, ChoosePanel, ContinuePanel, LongPanel, Panel, ReflectPanel, TextPanel, TickPanel,
                     ValuePanel, WorkedPanel)

BANNER = r"""[b #ffd500]  ___ _____ ___ __  __   _____      _
 / __|_   _| __|  \/  | |_   _|  _| |_ ___ _ _
 \__ \ | | | _|| |\/| |   | || || |  _/ _ \ '_|
 |___/ |_| |___|_|  |_|   |_| \_,_|\__\___/_|[/]"""


def bar(done: int, total: int, width: int = 12) -> str:
    fill = round(width * done / max(1, total))
    return "█" * fill + "░" * (width - fill)


# ============================ Home ============================
MODE_NAMES = {"autopilot": "today's plan", "weak": "weak-spots"}
SUBJECTS = {"math": "Maths", "chem": "Chem", "phys": "Phys", "exam": "Exam"}


class HomeScreen(Screen):
    BINDINGS = [Binding("question_mark", "app.help", "Help"), Binding("f2", "app.settings", "Settings"),
                Binding("q", "app.quit", "Quit")]

    def compose(self) -> ComposeResult:
        yield Static(BANNER, id="banner")
        with Horizontal(id="home"):
            yield OptionList(id="menu")
            with VerticalScroll(id="stats"):  # more chapters than fit in the window: the box scrolls
                yield Static(id="stats-text")
        yield Footer()

    def on_screen_resume(self) -> None:
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
        self._read_almanac()
        lessons = app.vault / "Lessons"
        views.write_home(app.vault, app.tutor.packs, app.tutor.state, app.tutor.now(),
                         sorted((str(f.relative_to(app.vault)) for f in lessons.glob("*.md")), reverse=True)
                         if lessons.exists() else [])
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
        menu = self.query_one("#menu", OptionList)
        menu.clear_options()
        items = []
        if t.session:
            s = t.session
            items.append(("resume", f"▶  Resume your {MODE_NAMES.get(s['mode'], s['mode'])} session "
                                    f"({s.get('answered', 0)} answered)"))
        week = policy.focus_week(t.packs.plan, t.state, t.ticks(), now) if t.packs.plan.get("weeks") else 0
        items += [("today", f"★  Today's plan{f' (Almanac week {week})' if week else ''}"),
                  ("learn", "◆  Learn a topic (lesson)"),
                  ("review", f"↻  Review what's due ({len(due)})"),
                  ("weak", f"✚  Fix my weak spots ({len(insights.weak_spots(t))})"),
                  ("test", "◎  Test prep: check a chapter, fix what's weak"),
                  ("long", "✎  Long questions (typed or iPad)"),
                  ("blurt", "»  Blurt: write everything you remember"),
                  ("chat", "✦  Ask the tutor anything"),
                  ("insights", "◉  What the tutor knows about you"),
                  ("progress", "▤  My progress"),
                  ("obsidian", "▣  Open my notes in Obsidian"),
                  ("settings", "≡  Settings"), ("help", "?  How it works"), ("quit", "×  Quit")]
        for key, label in items:
            menu.add_option(Option(label, id=key))
        menu.highlighted = 0
        menu.focus()
        self.query_one("#stats-text", Static).update(self.stats_text(now, due))

    def stats_text(self, now: datetime, due: list) -> Text:
        app = self.app
        t = app.tutor
        out = Text()
        out.append(f"{now:%A %d %B}\n", style="bold #ffd500")
        days = {date.fromisoformat(d) for d in t.state.get("study_days", [])}
        d = now.date() if now.date() in days else now.date() - timedelta(days=1)
        streak = 0
        while d in days:
            streak, d = streak + 1, d - timedelta(days=1)
        out.append(f"🔥 {streak}-day streak   🔁 {len(due)} due\n\n", style="#f9e2af")
        sittings = sorted((date.fromisoformat(v), k) for k, v in (t.packs.plan.get("sittings") or {}).items()
                          if date.fromisoformat(v) >= now.date())
        if sittings:
            out.append(f"⏳ {sittings[0][1]}: {(sittings[0][0] - now.date()).days} days\n\n", style="#94e2d5")
        ticked = t.ticks()
        week = policy.current_week(t.packs.plan, now)
        focus = policy.focus_week(t.packs.plan, t.state, ticked, now)  # past the calendar once this week is done
        objectives = (t.packs.plan.get("weeks") or {}).get(str(focus), [])
        if objectives:
            done = [policy.is_done(o, t.state, ticked) for o in objectives]
            out.append(f"📅 Almanac week {focus}" + (f" · {sum(done)} of {len(done)} done" if any(done) else "") + "\n",
                       style="bold #94e2d5")
            if focus > week:
                out.append(f"You're ahead: the calendar is on week {week}.\n", style="#a6e3a1")
            for o, finished in list(zip(objectives, done))[:6]:
                kcs = o.get("kcs", [])
                ready = sum(1 for k in kcs if k in t.packs.kcs and t.packs.items_for(k))
                title = o["title"] if o.get("type", "NEW") == "NEW" else f"{o.get('verb', '')} {o['title']}".strip()
                title = title[:36] + ("…" if len(title) > 36 else "")
                out.append(f"{'✓' if finished else ' '} {SUBJECTS.get(o['subject'], o['subject']):<6}{title}",
                           style="#6c7086" if finished else "#cdd6f4")
                if kcs and not finished:
                    status = "ready" if ready == len(kcs) else f"{ready}/{len(kcs)} ready" if ready else "not built yet"
                    out.append(" " + status, style="#a6e3a1" if ready == len(kcs) else "#6c7086")
                out.append("\n")
            export = almanac.latest_export(app.vault)
            out.append((f"Ticks read from your export of {datetime.fromtimestamp(export.stat().st_mtime):%-d %b %H:%M}."
                        if export else "To count your ticks: press Export in your Almanac.") + "\n\n", style="#6c7086")
        if mac.almanac_changed(t.packs.plan):
            out.append("⚠ Your Almanac has changed since the tutor read it: ask Claude Code to refresh the plan.\n\n",
                       style="#f9e2af")
        out.append("Your topics\n", style="bold")
        for sub in sorted(s for s in t.packs.subtopics if t.packs.pack(s)):
            kcs = [k for k, v in t.packs.kcs.items() if v["subtopic"] == sub]
            sec = sum(views.kc_status(t.state, k) == "secure" for k in kcs)
            started = any(views.kc_status(t.state, k) != "new" for k in kcs)
            colour = "#a6e3a1" if sec == len(kcs) else "#f9e2af" if started else "#6c7086"
            out.append(f"{sub:<9}", style="#cdd6f4")
            out.append(bar(sec, len(kcs), 10), style=colour)
            out.append(f" {sec}/{len(kcs)} {t.packs.subtopics[sub]['title'][:26]}\n", style="#9399b2")
        a = app.ai
        state = ("on" if a.available else {"login": "sign-in needed", "limit": "paused (limit)",
                                           "off": "not installed"}.get(a.status, a.status)) if app.settings.ai else "off"
        out.append(f"\nAI tutor: {state} · {a.today()['replies']} replies today\n", style="#f5c2e7")
        out.append(f"\nSTEM Tutor v{__version__}", style="#6c7086")
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
        elif key == "chat":
            app.push_screen(ChatScreen())
        elif key == "progress":
            app.push_screen(ProgressScreen())
        elif key == "obsidian":
            views.write_home(app.vault, app.tutor.packs, app.tutor.state, app.tutor.now(),
                             sorted((str(f.relative_to(app.vault)) for f in (app.vault / "Lessons").glob("*.md")),
                                    reverse=True) if (app.vault / "Lessons").exists() else [])
            mac.open_in_obsidian(app.vault, "Home", background=False)
        elif key == "settings":
            app.action_settings()
        elif key == "help":
            app.action_help()
        elif key == "quit":
            app.exit()


# ============================ Topic picker ============================
class PickerScreen(ModalScreen):
    BINDINGS = [Binding("escape", "dismiss(None)", "Back")]

    def __init__(self, mode: str) -> None:
        super().__init__()
        self.mode = mode

    def compose(self) -> ComposeResult:
        t = self.app.tutor
        built = sorted(s for s in t.packs.subtopics if t.packs.pack(s))
        with Vertical(id="picker"):
            if self.mode == "test":
                yield Static("Tick the subtopics the test covers (space), then ⏎ on Start.", classes="hint")
                yield SelectionList[str](*[Selection(self._label(s), s) for s in built], id="subs")
                yield Button("Start test prep", id="go", variant="primary")
            else:
                word = {"lesson": "learn", "long": "practise with long questions",
                        "blurt": "blurt (write everything you remember about)"}.get(self.mode, "study")
                yield Static(f"Which subtopic do you want to {word}? (⏎ to choose, Esc to go back)", classes="hint")
                yield OptionList(*[Option(self._label(s), id=s) for s in built], id="subs")

    def _label(self, sub: str) -> str:
        t = self.app.tutor
        kcs = [k for k, v in t.packs.kcs.items() if v["subtopic"] == sub]
        sec = sum(views.kc_status(t.state, k) == "secure" for k in kcs)
        return f"{sub:<9} {bar(sec, len(kcs), 8)} {t.packs.subtopics[sub]['title']}"

    @on(OptionList.OptionSelected, "#subs")
    def chose(self, event: OptionList.OptionSelected) -> None:
        self.dismiss([event.option.id])

    @on(Button.Pressed, "#go")
    def go(self) -> None:
        chosen = list(self.query_one("#subs", SelectionList).selected)
        if chosen:
            self.dismiss(chosen)
        else:
            self.app.notify("Tick at least one subtopic (space), then Start.", timeout=5)


# ============================ Session ============================
class SessionScreen(Screen):
    BINDINGS = [Binding("ctrl+t", "ask", "Ask tutor", priority=True), Binding("ctrl+g", "hint", "Hint", priority=True),
                Binding("ctrl+r", "explain", "Re-explain", priority=True),
                Binding("ctrl+o", "obsidian", "Obsidian", priority=True),
                Binding("ctrl+b", "leave", "Save & menu", priority=True),
                Binding("t", "ask", show=False), Binding("e", "explain", show=False), Binding("h", "hint", show=False),
                Binding("o", "obsidian", show=False), Binding("question_mark", "app.help", "Help")]

    def __init__(self, start: dict | None) -> None:
        super().__init__()
        self.start_args, self.act, self.kc, self.view = start, {}, None, None
        self.started = time.monotonic()
        self.chatting = False

    def compose(self) -> ComposeResult:
        yield Static(id="bar")
        yield Static(id="map")
        yield VerticalScroll(id="log")
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

    def panel(self, widget) -> None:
        box = self.query_one("#panel", Container)
        box.remove_children()
        box.mount(widget)

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
        self.set_interval(1, self.update_bar)
        self.advance()

    def update_bar(self) -> None:
        t = self.tutor
        s = t.session or {}
        sub = s.get("subtopic")
        title = t.packs.subtopics.get(sub, {}).get("title", "") if sub else ""
        mins, secs = divmod(int(time.monotonic() - self.started), 60)
        a = self.app.ai
        ai_state = "AI ●" if (self.app.settings.ai and a.available) else "AI ○"
        txt = Text()
        txt.append(" STEM Tutor ", style="bold #1e1e2e on #ffd500")
        mode = {"lesson": "Lesson", "review": "Review", "test": "Test prep", "long": "Long questions"}.get(
            s.get("mode", ""), s.get("mode", "").title())
        txt.append(f" {title + ' · ' if title else ''}{mode} ", style="bold")
        txt.append(f" ⏱ {mins:02d}:{secs:02d} ", style="#94e2d5")
        txt.append(f" ✓ {s.get('correct', 0)}/{s.get('answered', 0)} ", style="#a6e3a1")
        txt.append(f" {ai_state} {a.session.replies} replies · {a.session.output_tokens + a.session.input_tokens} tok ",
                   style="#f5c2e7")
        self.query_one("#bar", Static).update(txt)
        nodes = [b for b in s.get("blocks", []) if b.get("kind") == "node"]
        if nodes:
            m = Text(" Map: ", style="#9399b2")
            for b in nodes:
                kc = b["kc"]
                glyph, style = ("✓", "#a6e3a1") if kc in s.get("kcs_learned", []) else \
                    ("▶", "bold #89b4fa") if kc == self.kc else ("○", "#6c7086")
                name = t.packs.kcs[kc]["title"]
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
        if kind in ("questions", "awaiting"):
            self.ask_question(act["items"][0], act.get("say"))
        elif kind in ("explain", "teach"):
            title = act.get("title") or act.get("kc_title", "")
            text = act.get("text") or act.get("outline", "")
            if kind == "teach" and act.get("misconceptions"):
                text += "\n\n" + "\n".join(f"- Trap: {m}" for m in act["misconceptions"])
            self.say(cards.card("tutor", title, text, subtitle="second look" if act.get("part") == "fix" else None))
            self.panel(ContinuePanel())
        elif kind == "choose":
            self.say(cards.card("plan", act["question"], ""))
            self.panel(ChoosePanel("↑↓ and ⏎", act["options"]))
        elif kind == "plan":
            lines = [act["approach"], ""] + [f"- {'✓ you know: ' if n['known'] else ''}{n['title']}" for n in act["nodes"]]
            self.say(cards.card("plan", f"Plan: {act['title']}", "\n".join(lines),
                                subtitle="the concept map is in Obsidian → Now"))
            self.prepare_cards(act["default_teach"])  # AI teaching cards (if needed) start while you read the plan
            self.panel(TickPanel("Ticked ideas will be taught (space to change). Then ⏎ on Start.",
                                 [(n["title"], n["kc"], n["kc"] in act["default_teach"]) for n in act["nodes"]],
                                 [("start", "Start lesson ⏎")]))
        elif kind in ("worked", "walkthrough"):
            self.say(cards.card("tutor", "Worked example", act.get("problem") or "Walk through it step by step."))
            for i, st in enumerate(act["steps"][:act.get("revealed", 0)], 1):  # steps already seen before a resume
                self.say(cards.card("tutor", f"Step {i}", f"{st['do']}\n\n_{st.get('why', '')}_"))
            self.panel(WorkedPanel(len(act["steps"]), start=act.get("revealed", 0) + 1))
        elif kind == "refute":
            m = act["misconceptions"][0]
            m = m if isinstance(m, dict) else {"statement": m}
            self.say(cards.card("hint", f"Trap: {m.get('statement', '')}",
                                f"{m.get('refutation', '')}\n\n{('_Compare:_ ' + m['contrast']) if m.get('contrast') else ''}"))
            self.panel(ContinuePanel())
        elif kind == "own_words":
            self.say(cards.card("tutor", "In your own words", act["prompt"]))
            self.panel(TextPanel("One or two sentences. Esc to skip.", done_label=None))
        elif kind == "stuck":
            self.say(cards.card("hint", "Not clicked yet", act["say"]))
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
        if say:
            self.say(cards.note(say, "dim"))
        self.say(cards.question(view))
        self.answer_panel(view)

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
        data, kind = event.data, self.act.get("activity")
        if isinstance(event.panel, LongPanel):
            self.long_written(data)
            return
        if isinstance(event.panel, ReflectPanel):
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
            self.respond({"step": data["step"]})
        elif kind in ("worked", "walkthrough") and data.get("done"):
            self.respond({"done": True})
            self.advance()
        elif kind == "own_words":
            if data.get("text"):
                self.say(cards.you(data["text"]))
                self.respond({"text": data["text"]})
                if self.app.settings.own_words_feedback and self.ai_ok():
                    self.panel(ContinuePanel("The tutor is reading your explanation…", buttons=[]))
                    self.stream(prompts.own_words(self.tutor, self.kc, data["text"]), then_continue=True)
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
                                    "and what the common wrong answer gets wrong.", self.kc))
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
        self.last_fb = r
        self.followups = (["reflect"] if r.get("reflect") else []) + (["break"] if r.get("break_suggested") else [])
        self.next_followup()

    def next_followup(self) -> None:
        """After feedback: why-did-I-miss-it, then a break suggestion if due, then the usual continue buttons."""
        step = self.followups.pop(0) if getattr(self, "followups", None) else None
        if step == "reflect":
            self.panel(ReflectPanel(bool(self.last_fb.get("slip_likely"))))
        elif step == "break":
            self.say(cards.card("hint", "Time for a short break?",
                                "Your accuracy has dipped below what's normal for you. A 5-minute break (water, stretch, "
                                "no phone) helps you feel fresher. Your place is saved either way."))
            self.panel(ContinuePanel(buttons=[("breakok", "Keep going ⏎"), ("leave", "Save and stop for now")]))
        else:
            buttons = [("next", "Next ⏎")] + ([("why", "Explain this answer (AI)")] if self.ai_ok() else []) + \
                      [("ask", "Ask the tutor (ctrl+t)")]
            self.panel(ContinuePanel(buttons=buttons))

    # ---------- written answers ----------
    @work(exclusive=True, group="judge")
    async def judge_short(self, view: dict, data: dict, pending: dict) -> None:
        n = view["n"]
        points = pending.get("rubric", [])
        if self.ai_ok():
            self.panel(ContinuePanel("Checking your wording against the mark points…", buttons=[]))
            res, _ = await self.app.ai.one_shot(prompts.judge(view.get("stem", ""), points, data.get("your", "")),
                                                schema=prompts.JUDGE)
            if res and res.get("points"):
                met = sum(1 for p in res["points"] if p.get("met"))
                score = met / max(1, len(points))
                out = self.tutor.answer(data["entry"], judge={n: score})
                fb = out["results"][0]
                fb["explanation"] = (res.get("feedback", "") + "\n\n" + "\n".join(
                    f"- {'✓' if p.get('met') else '✗'} {p.get('point', '')}" for p in res["points"])).strip()
                self.say(cards.feedback(fb, data.get("your", "")))
                self.panel(ContinuePanel(buttons=[("next", "Next ⏎"), ("ask", "Ask the tutor (ctrl+t)")]))
                return
        self.pending_short = (n, data, max(1, len(points)))
        self.panel(TickPanel("Mark yourself: tick each point your answer really contains (space), then ⏎ on Done.",
                             [(p, str(i), False) for i, p in enumerate(points)], [("self", "Done ⏎")]))

    def long_marks(self, data: dict) -> None:
        if getattr(self, "pending_short", None):
            n, d, total = self.pending_short
            self.pending_short = None
            out = self.tutor.answer(d["entry"], judge={n: len(data["ticked"]) / total})
            self.say(cards.feedback(out["results"][0], d.get("your", "")))
            self.panel(ContinuePanel(buttons=[("next", "Next ⏎"), ("ask", "Ask the tutor (ctrl+t)")]))
            return
        n = self.view["n"]
        if data.get("button") == "ai":
            self.ai_check_long(data)
            return
        out = self.tutor.answer(f"{n} pts=" + ",".join(data["ticked"]) if data["ticked"] else f"{n} pts=")
        fb = out["results"][0]
        self.say(cards.feedback(fb, f"{len(data['ticked'])} mark point(s) claimed"))
        self.panel(ContinuePanel(buttons=[("next", "Next ⏎"), ("ask", "Ask the tutor (ctrl+t)")]))

    def long_written(self, data: dict) -> None:
        text = data.get("text", "")
        self.long_text = text
        self.say(cards.you(text))
        if (log := self.tutor._lesson_log()):  # the transcript keeps your working, even if you leave before marking
            log.you(f"Working for Q{self.view['n']}:\n\n{text}")
        sch = self.tutor.scheme(self.view["n"])
        self.scheme = sch.get("scheme", [])
        buttons = [("mine", "Submit my marks ⏎")] + ([("ai", "Ask the AI examiner to check")] if self.ai_ok() else [])
        self.mark_panel("Tick every mark point your answer earns (space). Honest self-marking is great practice.",
                        (), buttons)

    def mark_panel(self, prompt: str, ticked, buttons: list[tuple[str, str]]) -> None:
        self.panel(TickPanel(prompt, [(f"{p.get('mark', '')} {p.get('point', '')}", str(p["i"]), str(p["i"]) in ticked)
                                      for p in self.scheme], buttons))

    @work(exclusive=True, group="judge")
    async def ai_check_long(self, data: dict) -> None:
        self.panel(ContinuePanel("The AI examiner is marking your answer…", buttons=[]))
        points = [f"{p.get('mark', '')} {p.get('point', '')}" for p in self.scheme]
        res, r = await self.app.ai.one_shot(prompts.judge(self.view.get("stem", ""), points, self.long_text),
                                            schema=prompts.JUDGE)
        if not res:  # give the tick list back, with your ticks, so you can still mark it yourself
            self.say(cards.card("hint", "AI check unavailable", r.message or "Mark it yourself."))
            self.mark_panel("Tick every mark point your answer earns (space), then submit.", data["ticked"],
                            [("mine", "Submit my marks ⏎")])
            return
        verdict = "\n".join(f"- {'✓' if p.get('met') else '✗'} {p.get('point', '')}: {p.get('why', '')}"
                            for p in res.get("points", []))
        self.say(cards.ai(f"{res.get('feedback', '')}\n\n{verdict}", "AI examiner"))
        met = {str(self.scheme[i]["i"]) for i, p in enumerate(res.get("points", [])) if p.get("met") and i < len(self.scheme)}
        ticked = sorted(set(data["ticked"]) | met) if data["ticked"] else sorted(met)
        self.mark_panel("Adjust if you disagree, then submit.", ticked, [("mine", "Submit ⏎")])

    # ---------- AI ----------
    def ai_ok(self) -> bool:
        return self.app.settings.ai and self.app.ai.available

    def stream(self, prompt: str, then_continue: bool = False) -> None:
        if not self.ai_ok():
            a = self.app.ai
            msg = a.message or ("AI is switched off in Settings." if not self.app.settings.ai else "AI is unavailable.")
            self.say(cards.card("hint", "AI help is off", msg))
            if then_continue:
                self.panel(ContinuePanel(buttons=[("continue", "Continue ⏎")]))
            return
        if (help_ := self.tutor.ai_help(given=False)).get("refused"):  # not allowed while a no-help check is open
            self.say(cards.card("hint", "No help on this one", help_["refused"]))
            if then_continue:
                self.panel(ContinuePanel(buttons=[("continue", "Continue ⏎")]))
            return
        self._stream(prompt, then_continue)

    @work(exclusive=True, group="ai")
    async def _stream(self, prompt: str, then_continue: bool) -> None:
        a = self.app.ai
        w = self.say(cards.ai("…"))
        buf = ""
        # guard every open question (normally just the one on screen; a session begun in the chat may hold more)
        keys = [prompts.key_of(self.tutor, int(n)) for n in (self.tutor.session or {}).get("presented", {})]
        async for chunk in a.stream(prompt):
            buf += chunk
            if not keys:
                w.update(cards.ai(buf))
                self.query_one("#log", VerticalScroll).scroll_end(animate=False)
        withheld = any(ai_mod.leaks(buf, *k) for k in keys)
        if withheld:
            buf = "I can't give that away while the question is open. Try a hint (h), or answer first and I'll explain."
        if not a.last.ok:
            w.update(cards.card("hint", "AI paused", a.last.message))
        else:
            w.update(cards.ai(buf))
            if buf and not withheld:
                self.tutor.ai_help()  # help that reached you counts as a hint on every open question
            if (log := self.tutor._lesson_log()):
                log.tutor(buf, title="Tutor (AI)")
        self.update_bar()
        if then_continue:
            self.panel(ContinuePanel(buttons=[("continue", "Continue ⏎"), ("ask", "Ask the tutor (ctrl+t)")]))

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
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(json.dumps({**data, "source": "ai"}, ensure_ascii=False, indent=1))

    # ---------- key actions ----------
    def action_ask(self) -> None:
        def got(q: str | None) -> None:
            if q:
                self.say(cards.you(q))
                if (log := self.tutor._lesson_log()):
                    log.you(q)
                self.stream(prompts.ask(self.tutor, q, self.kc))
        self.app.push_screen(AskScreen(), got)

    def action_explain(self) -> None:
        if self.kc:
            self.stream(prompts.explain_again(self.tutor, self.kc))

    def action_hint(self) -> None:
        if not self.view:
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

    def action_obsidian(self) -> None:
        mac.open_in_obsidian(self.app.vault, "Now", background=False)

    def action_leave(self) -> None:
        self.app.pop_screen()

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
    BINDINGS = [Binding("enter", "dismiss(None)", "Back to menu"), Binding("escape", "dismiss(None)", "Back")]

    def __init__(self, summary: dict) -> None:
        super().__init__()
        self.summary = summary

    def compose(self) -> ComposeResult:
        s = self.summary
        t = self.app.tutor
        acc = f"{round(100 * s['accuracy'])}%" if s.get("accuracy") is not None else "–"
        learned = "\n".join(f"- ✓ {t.packs.kcs[k]['title']}" for k in s.get("kcs_learned", []) if k in t.packs.kcs)
        due = model.due_kcs(t.state, t.now() + timedelta(days=1))
        a = self.app.ai
        text = (f"# Session done 🎉\n\n**Answered:** {s['answered']}  ·  **Correct:** {s['correct']}  ·  **Accuracy:** {acc}\n\n"
                + (f"## Learned today\n{learned}\n\n" if learned else "")
                + f"**Due for review by tomorrow:** {len(due)} idea(s)\n\n"
                + f"**AI used this session:** {a.session.replies} replies, "
                  f"{a.session.input_tokens + a.session.output_tokens} new tokens ({a.session.cached_tokens} cached)\n\n"
                + (f"**New Anki cards ({(s.get('week') or {})['anki']['cards']}):** double-click "
                   f"`{(s.get('week') or {})['anki']['path']}` in the tutor folder to import them.\n\n"
                   if ((s.get("week") or {}).get("anki") or {}).get("path") else "")
                + "Your notes and the full lesson are in Obsidian (Home → Recent lessons). Press ⏎ for the menu.")
        with Vertical(id="summary"):
            yield Markdown(text)


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
            yield Static("Ask the tutor anything about this topic (⏎ to send, Esc to cancel).", classes="hint")
            yield Input(placeholder="e.g. why is displacement a vector but distance isn't?", id="q")

    def on_mount(self) -> None:
        self.query_one("#q", Input).focus()

    @on(Input.Submitted, "#q")
    def sent(self, event: Input.Submitted) -> None:
        self.dismiss(event.value.strip() or None)


class ChatScreen(Screen):
    """Free chat with the tutor from the menu."""
    BINDINGS = [Binding("escape", "app.pop_screen", "Back to menu")]

    def compose(self) -> ComposeResult:
        yield Static(Text(" Ask the tutor ", style="bold #1e1e2e on #f5c2e7"), id="bar")
        yield VerticalScroll(id="log")
        with Container(id="panel"):
            yield TextPanel("Type a question and ⏎. Esc returns to the menu.")
        yield Footer()

    def on_mount(self) -> None:
        self.run_worker(self.app.ai.reset(), group="reset")  # chat never inherits a lesson's context

    @on(Panel.Done)
    def sent(self, event: Panel.Done) -> None:
        if event.data.get("skip"):
            self.app.pop_screen()
            return
        q = event.data.get("text", "")
        log = self.query_one("#log", VerticalScroll)
        log.mount(Static(cards.you(q), classes="entry"))
        self.reply(q)

    @work(exclusive=True)
    async def reply(self, q: str) -> None:
        a = self.app.ai
        log = self.query_one("#log", VerticalScroll)
        if not (self.app.settings.ai and a.available):
            log.mount(Static(cards.card("hint", "AI help is off", a.message or "Switch AI on in Settings."), classes="entry"))
            return
        w = Static(cards.ai("…"), classes="entry")
        log.mount(w)
        buf = ""
        async for chunk in a.stream(f"CONTEXT\n(none: a general question from the menu)\n\nSTUDENT ASKS: {q}"):
            buf += chunk
            w.update(cards.ai(buf))
            log.scroll_end(animate=False)
        if not a.last.ok:
            w.update(cards.card("hint", "AI paused", a.last.message))
        self.query_one(TextPanel).query_one(Input).value = ""


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
        return (report.insights_markdown(t, report.load_ai_summary(t)) + "\n---\n\n**a** asks the AI tutor to explain "
                "this in a few lines (one reply from today's allowance) · **o** opens it in Obsidian · **m** your "
                "mistake journal · **w** your latest week in review · **Esc** back")

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
        rows += ["", "## Topics", "", "| Subtopic | Secure | Learning | Gaps |", "|---|---|---|---|"]
        for sub in sorted(s for s in t.packs.subtopics if t.packs.pack(s)):
            kcs = [k for k, v in t.packs.kcs.items() if v["subtopic"] == sub]
            st = [views.kc_status(t.state, k) for k in kcs]
            rows.append(f"| {sub} {t.packs.subtopics[sub]['title']} | {st.count('secure')}/{len(kcs)} | "
                        f"{st.count('learning')} | {st.count('gap')} |")
        cal = p["calibration"]
        if cal["levels"]:
            rows += ["", "## How sure vs how right", "", "| You said | Answers | Right |", "|---|---|---|"]
            rows += [f"| {lv['level']} | {lv['n']} | {lv['right']:.0%} |" for lv in cal["levels"]]
        h = p["habits"]
        rows += ["", "## Habits", "", f"- Streak: {h['streak']} day(s); studied {h['last_28']} of the last 28 days.",
                 f"- Reviews due in the next 7 days: {' · '.join(str(x) for x in p['workload'])}."]
        rows += ["", "Esc to go back · o opens the full profile (Profile.md) in Obsidian."]
        with VerticalScroll():
            yield Markdown("\n".join(rows))
        yield Footer()

    def action_open(self) -> None:
        from tutorlib import report
        report.profile_note(self.app.tutor)
        mac.open_in_obsidian(self.app.vault, "Profile", background=False)


class BlurtScreen(Screen):
    """Free recall: write everything you remember, then see what you left out."""
    BINDINGS = [Binding("ctrl+s", "submit", "Check my blurt"), Binding("escape", "app.pop_screen", "Back")]

    def __init__(self, subtopic: str) -> None:
        super().__init__()
        self.subtopic = subtopic

    def compose(self) -> ComposeResult:
        t = self.app.tutor
        title = t.packs.subtopics[self.subtopic]["title"]
        yield Static(Text(f" Blurt · {self.subtopic} {title} ", style="bold #1e1e2e on #ffd500"), id="bar")
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

    @on(Button.Pressed, "#check")
    def action_submit(self) -> None:
        from textual.widgets import TextArea
        from tutorlib import lesson
        text = self.query_one("#blurt", TextArea).text.strip()
        if not text:
            return
        t = self.app.tutor
        res = t.blurt(self.subtopic, text)
        log = self.query_one("#log", VerticalScroll)
        n, total = len(res["recalled"]), len(res["ideas"])
        log.mount(Static(cards.card("good" if n == total else "hint", f"You recalled {n} of {total} ideas",
                                    "Ideas you left out are now due for review, so they come up next time."),
                         classes="entry"))
        for kc, v in res["ideas"].items():
            note = "" if v["recalled"] else lesson.teach_card(t, kc).get("note", "")
            log.mount(Static(cards.card("good" if v["recalled"] else "bad",
                                        f"{'✓' if v['recalled'] else '✗'} {v['title']}", note), classes="entry"))
        log.scroll_end(animate=False)
        box = self.query_one("#panel", Container)
        box.remove_children()
        box.mount(Static("Esc for the menu. Your blurt and results are saved in Lessons in Obsidian.", classes="hint"))


class HelpScreen(ModalScreen):
    BINDINGS = [Binding("escape", "dismiss(None)", "Close"), Binding("enter", "dismiss(None)", "Close"),
                Binding("o", "guide", "Open the full guide")]

    def compose(self) -> ComposeResult:
        text = """# Keys
**↑ ↓** move · **⏎** choose / continue · **A–D** pick an option · **0** I don't know · **1–4** confidence
(1 guess, 2 unsure, 3 fairly sure, 4 certain) · **space** tick a box

**ctrl+t** ask the tutor (AI) · **ctrl+r** explain this idea again, differently (AI) · **ctrl+g** hint (not on
no-hints checks) · **ctrl+o** show the current question or explanation in Obsidian · **ctrl+b** or **ctrl+q** save
and go back to the menu. These work even while you are typing; when you are not typing, **t e h o** do the same.
**?** this help · **F2** settings · **q** quit (from the menu)

# Where to look
Keep **Obsidian** open beside this window on **Now** (the current question in full, with figures) — your
**My Notes** for the topic grow underneath as you learn. Every session is saved in **Lessons**.

The full plain-English guide is **How It Works** in Obsidian (press **o** now).
"""
        with VerticalScroll(id="help"):
            yield Markdown(text)

    def action_guide(self) -> None:
        mac.open_in_obsidian(self.app.vault, "How It Works", background=False)


class SettingsScreen(ModalScreen):
    BINDINGS = [Binding("escape", "dismiss(None)", "Close")]

    def compose(self) -> ComposeResult:
        s = self.app.settings
        with Vertical(id="settings"):
            yield Static("Settings (saved in your tutor folder)", classes="title")
            for key, label in (("ai", "AI tutor (asking, explaining, judging written answers)"),
                               ("own_words_feedback", "AI comments on your 'in your own words' answers"),
                               ("open_obsidian", "Show Now in Obsidian when a session starts")):
                with Horizontal(classes="row"):
                    yield Switch(value=getattr(s, key), id=key)
                    yield Static(label)
            with Horizontal(classes="row"):
                yield Select([("Haiku (cheapest, fast)", "haiku"), ("Sonnet (clearer, ~3x usage)", "sonnet")],
                             value=s.model, id="model", allow_blank=False)
            with Horizontal(classes="row"):
                yield Static("Session length (minutes): ")
                yield Input(str(s.minutes), id="minutes", type="integer")
            yield Button("Save", id="save", variant="primary")

    @on(Button.Pressed, "#save")
    def save(self) -> None:
        s = self.app.settings
        for key in ("ai", "own_words_feedback", "open_obsidian"):
            setattr(s, key, self.query_one(f"#{key}", Switch).value)
        def num(wid: str, default: int, lo: int, hi: int) -> int:
            try:
                return min(hi, max(lo, int(self.query_one(wid, Input).value)))
            except ValueError:
                return default
        old_model = s.model
        s.model = str(self.query_one("#model", Select).value)
        s.minutes = num("#minutes", 40, 5, 180)
        s.save(self.app.vault)
        self.app.ai.model = s.model
        if s.model != old_model:
            self.run_worker(self.app.ai.reset(), group="reset")
        self.dismiss(None)
