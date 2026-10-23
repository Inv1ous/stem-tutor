"""Shortcuts & Elegant Methods: learn a shortcut (a card at a time, then practice), and its own recall queue.

All the learner's state is the course's own (tutorlib.shortcuts: settings, events and cards under .tutor/shortcuts/):
the syllabus model, sessions and reviews are never touched."""
from __future__ import annotations

import random
import re
from datetime import datetime, timezone

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Input, OptionList, SelectionList, Static
from textual.widgets.option_list import Option
from textual.widgets.selection_list import Selection

from tutorlib import shortcuts as sc
from tutorlib.grade import ParseError, parse_quantity
from tutorlib.units import parse_unit, unit_factor, unit_readings

from .look import C
from .panels import TickList
from .screens import READ_KEY, AskScreen, ConfirmScreen, PickerScreen, ReadAloud
from .texmath import to_terminal

NO_CONTENT = ("No shortcuts have been published to your tutor folder yet. Ask Claude Code to run build/publish.py "
              "(after build/shortcuts.py parse), then come back.")
RATE_LABELS = [("1", "1  Again: I did not get it"), ("2", "2  Hard: I got it with effort"),
               ("3", "3  Good: I understand it"), ("4", "4  Easy: I could use it straight away")]
PER_DAY = [0, 1, 2, 3, 5, 8, 10, 15, 20, 30, 50]
HINTS = 3


# ============================ small helpers ============================
def txt(v) -> str:
    """Text from a lesson field of any type, with the maths turned into terminal characters."""
    return to_terminal(v if isinstance(v, str) else "" if v is None else str(v)).strip()


def items(v) -> list[str]:
    return [t for t in (txt(x) for x in v) if t] if isinstance(v, (list, tuple)) else ([txt(v)] if txt(v) else [])


def number(s, expected_unit: str = "") -> float | None:
    # Read the whole value: a fraction is not just its numerator.
    try:
        value, unit, _ = parse_quantity(str(s))
    except ParseError:
        return None
    if not unit:
        return value
    factors = unit_readings(unit, expected_unit, allow_comments=False)[0] if expected_unit else []
    return value * factors[0] if factors else None


def numeric_ok(given: str, answer, stem: str = "") -> bool:
    """Right when the strings match, or the numbers are within 1% of each other."""
    if str(given).strip().lower() == str(answer).strip().lower():
        return True
    # Read units from the request, not data such as "Evaluate tan 225, with the angle in degrees".
    request = " ".join(sentence for sentence in re.split(r"(?<=[.?!])\s+", txt(stem)) if re.search(
        r"\b(?:find|calculate|determine|give|state|express|estimate|what|write|convert|how far|how much|how fast)\b",
        sentence, re.I))
    expected_unit = ""
    for match in re.finditer(r"\bin\s+([^.,;?]+?)(?=\s+(?:to|as|measured|using|between)\b|[.,;?]|$)", request):
        candidate = match[1].strip()
        # Degrees and Celsius are recognised units, but are not part of SI unit algebra.
        if unit_factor(candidate, "°") is None and unit_factor(candidate, "°C") is None:
            try:
                parse_unit(candidate)
            except (ValueError, ArithmeticError):
                continue
        expected_unit = candidate
    a, b = number(given, expected_unit), number(txt(answer), expected_unit)
    if a is None or b is None:
        return False
    return abs(a - b) <= 0.01 * abs(b) if b else abs(a) < 1e-9


def utc(iso) -> datetime | None:
    try:
        d = datetime.fromisoformat(iso)
    except (TypeError, ValueError):
        return None
    return d.replace(tzinfo=timezone.utc) if d.tzinfo is None else d.astimezone(timezone.utc)


def when_text(due: datetime | None, tz) -> str:
    if due is None:
        return "not scheduled yet"
    now = datetime.now(timezone.utc)
    if due <= now:
        return "now"
    days = (due.astimezone(tz).date() - now.astimezone(tz).date()).days
    clock = f"{due.astimezone(tz):%H:%M}"
    if days <= 0:
        return f"today at {clock}"
    return f"tomorrow at {clock}" if days == 1 else f"in {days} days ({due.astimezone(tz):%a %-d %b})"


def next_due(course: sc.Course) -> datetime | None:
    ids = {e["id"] for e in (course.entries() if course.cfg["recall_scope"] == "learned" else course.pool())}
    dues = [d for i, c in course.state()["cards"].items() if i in ids and (d := utc(c.get("due")))]
    return min(dues) if dues else None


def filters_text(cfg: dict) -> str:
    def lst(v, empty="all"):
        return ", ".join(v) if v else empty
    rating = f"{cfg['min_score']} to {cfg['max_score']}" if cfg["min_score"] != cfg["max_score"] else str(cfg["min_score"])
    return (f"Rating {rating} out of 10 · subjects: {lst(cfg['specs'])} · level: {lst(cfg['levels'], 'AS and A')} · "
            f"sections: {lst(cfg['sections'])} · source: {lst(cfg['origins'])} · order: {cfg['order']} · "
            f"new a day: {cfg['new_per_day']} · full lessons only: {'yes' if cfg['lessons_only'] else 'no'}")


def sections_of(entry: dict) -> list[tuple[str, Text]]:
    """The reveal cards of one entry, in order. An entry with no written lesson shows its own note as the idea."""
    les = entry.get("lesson")
    if not isinstance(les, dict):
        return [("The idea", Text(txt(entry.get("body")) or "(no note)"))]
    out: list[tuple[str, Text]] = []

    def add(head, body):
        if body:
            out.append((head, body if isinstance(body, Text) else Text(body)))
    add("The pain", txt(les.get("hook")))
    add("When to use it", txt(les.get("when")))
    add("The idea", txt(les.get("idea")) or txt(entry.get("body")))
    add("Why it works", txt(les.get("why")))
    steps = items(les.get("steps"))
    add("Steps", "\n".join(f"{n}. {s}" for n, s in enumerate(steps, 1)))
    w = les.get("worked")
    if isinstance(w, dict) and any(txt(w.get(k)) for k in ("question", "long", "short", "saving")):
        t = Text()
        for key, label in (("question", "Question"), ("long", "The long way"), ("short", "The shortcut"),
                           ("saving", "What it saves")):
            if txt(w.get(key)):
                t.append(label + ": ", style="bold")
                t.append(txt(w.get(key)) + "\n")
        t.rstrip()
        add("Worked example", t)
    add("Watch out", "\n".join("• " + p for p in items(les.get("pitfalls"))))
    add("Check", txt(les.get("check")))
    return out


def practice_of(entry: dict) -> list[dict]:
    les = entry.get("lesson")
    raw = les.get("practice") if isinstance(les, dict) else None
    return [p for p in raw if isinstance(p, dict) and p.get("stem") and p.get("answer") not in (None, "")] \
        if isinstance(raw, list) else []


# ============================ widgets ============================
class Actions(OptionList):
    """A short list of choices. Digits pick a rating; with `letters`, A to D pick an option."""
    BINDINGS = [Binding(str(i), f"digit({i})", show=False) for i in range(1, 5)]

    def __init__(self, choices: list[tuple[str, str]], digits: bool = False, letters: bool = False,
                 current: int = 0) -> None:
        super().__init__(*[Option(label, id=cid) for cid, label in choices], classes="sc-actions")
        self.digits, self.letters, self.start = digits, letters, current

    def on_mount(self) -> None:
        self.highlighted = self.start

    def action_digit(self, n: int) -> None:
        if self.digits:
            self.screen.act(str(n))

    def on_key(self, event) -> None:
        if self.letters and event.character and event.character.upper() in {o.id for o in self.options}:
            event.stop()
            self.screen.act(event.character.upper())


class SettingsList(OptionList):
    """The settings, one a row with its value: ⏎ changes one."""


class TickScreen(PickerScreen):
    """Tick any of a list (subjects)."""

    def __init__(self, title: str, rows: list[tuple[str, str]], chosen: list[str]) -> None:
        super().__init__("shortcuts")
        self.title, self.rows, self.chosen = title, rows, chosen

    def compose(self) -> ComposeResult:
        with Vertical(id="picker"):
            yield Static(f"{self.title}: space ticks, then ctrl+s or Done. None ticked means all. Esc cancels.",
                         classes="hint")
            yield TickList(*[Selection(label, value, value in self.chosen) for value, label in self.rows], id="subs")
            yield Button("Done", id="done", variant="primary")

    @on(Button.Pressed, "#done")
    def action_go(self) -> None:
        self.dismiss(list(self.query_one("#subs", SelectionList).selected))


class TextAsk(AskScreen):
    def __init__(self, question: str, value: str) -> None:
        super().__init__()
        self.question, self.value = question, value

    def compose(self) -> ComposeResult:
        with Vertical(id="ask"):
            yield Static(self.question + " ⏎ sets it (empty clears it), Esc cancels.", classes="hint")
            yield Input(self.value, id="text")

    def on_mount(self, event) -> None:
        event.prevent_default()  # not AskScreen's: it has no words box
        self.query_one("#text", Input).focus()

    @on(Input.Submitted, "#text")
    def typed(self, event: Input.Submitted) -> None:
        self.dismiss(event.value)


class Pick(ConfirmScreen):
    """One choice from a list, the current one highlighted."""

    def __init__(self, question: str, choices: list[tuple[str, str]], current: str) -> None:
        super().__init__(question, choices)
        self.current = current

    def on_mount(self) -> None:
        ids = [cid for cid, _ in self.choices]
        self.query_one("#confirm", OptionList).highlighted = ids.index(self.current) if self.current in ids else 0


# ============================ the course's settings ============================
class ShortcutSettingsScreen(Screen):
    """The filters of the course, shared by learning and recall. Each change is saved at once."""
    BINDINGS = [Binding("escape", "close", "Back"), Binding("ctrl+b", "close", "Back", priority=True)]

    def __init__(self, course: sc.Course) -> None:
        super().__init__()
        self.course = course

    def action_close(self) -> None:
        self.dismiss(None)

    def compose(self) -> ComposeResult:
        yield Static(Text(" Shortcuts: settings ", style=f"bold {C['badge_fg']} on {C['badge_bg']}"), id="bar")
        with VerticalScroll(id="sc-setup"):
            yield Static("↑↓ and ⏎ change a setting; each is saved at once and shared with shortcut recall. Esc: back.",
                         classes="hint")
            yield SettingsList(id="sc-settings")
            yield Static(id="sc-detail")
        yield Footer()

    def on_mount(self) -> None:
        self.refresh_rows()
        self.query_one("#sc-settings", SettingsList).focus()

    @property
    def cfg(self) -> dict:
        return self.course.cfg

    def rows(self) -> list[tuple[str, str]]:
        c = self.cfg

        def lst(v, empty):
            return ", ".join(v) if v else empty
        return [("min_score", f"Lowest rating    {c['min_score']}/10"), ("max_score", f"Highest rating   {c['max_score']}/10"),
                ("specs", f"Subjects        {lst(c['specs'], 'all')}"),
                ("levels", f"Level           {lst(c['levels'], 'AS and A')}"),
                ("sections", f"Sections        {lst(c['sections'], 'all')}"),
                ("origins", f"Source          {lst(c['origins'], 'all')}"),
                ("order", f"Order           {'best rating first' if c['order'] == 'score' else 'by section'}"),
                ("new_per_day", f"New a day       {c['new_per_day']}"),
                ("lessons_only", f"Full lessons only  {'yes' if c['lessons_only'] else 'no'}"),
                ("recall_scope", f"Recall covers   {'what you have learned' if c['recall_scope'] == 'learned' else 'everything learned, even filtered out'}")]

    def refresh_rows(self) -> None:
        lst = self.query_one("#sc-settings", SettingsList)
        keep = lst.highlighted
        lst.clear_options()
        lst.add_options([Option(Text(label), id=key) for key, label in self.rows()])
        lst.highlighted = keep if keep is not None else 0
        c = self.course
        pool, sel = len(c.pool()), len(c.entries())
        self.query_one("#sc-detail", Static).update(Text(
            (f"{sel} of {pool} shortcut{'s' if pool != 1 else ''} match{'es' if sel == 1 else ''}." if pool else NO_CONTENT)
            + (" Nothing matches: widen the filters." if pool and not sel else ""), style=C["muted"]))

    def change(self, **values) -> None:
        cfg = {**self.cfg, **values}
        if "min_score" in values and cfg["min_score"] > cfg["max_score"]:
            cfg["max_score"] = cfg["min_score"]
        if "max_score" in values and cfg["max_score"] < cfg["min_score"]:
            cfg["min_score"] = cfg["max_score"]
        self.course.cfg = sc.save_config(self.course.vault, cfg)
        self.refresh_rows()

    @on(OptionList.OptionSelected, "#sc-settings")
    def edit(self, event: OptionList.OptionSelected) -> None:
        key, c, push = event.option.id, self.cfg, self.app.push_screen
        if key in ("min_score", "max_score"):
            push(Pick("Lowest rating to include" if key == "min_score" else "Highest rating to include",
                      [(str(i), f"{i}/10") for i in range(11)], str(c[key])), lambda r: r and self.change(**{key: int(r)}))
        elif key == "specs":
            specs = sorted({e["spec"] for e in self.course.pool() if e["spec"]} | set(c["specs"]))
            if specs:
                push(TickScreen("Subjects", [(s, s) for s in specs], c["specs"]),
                     lambda r: r is not None and self.change(specs=r))
            else:
                self.app.notify(NO_CONTENT, timeout=8)
        elif key == "levels":
            now = "both" if not c["levels"] else c["levels"][0] if len(c["levels"]) == 1 else "both"
            push(Pick("Which level?", [("both", "Both AS and A Level"), ("AS", "AS Level only"), ("A", "A Level only")], now),
                 lambda r: r and self.change(levels=[] if r == "both" else [r]))
        elif key == "sections":
            push(TextAsk("Part of a section name, e.g. kinematics. Separate several with commas.", ", ".join(c["sections"])),
                 lambda r: r is not None and self.change(sections=[p.strip() for p in r.split(",") if p.strip()]))
        elif key == "origins":
            now = c["origins"][0] if len(c["origins"]) == 1 else "all"
            push(Pick("Where the shortcuts come from", [("all", "All of them"), ("base", "The hand-made set"),
                                                        ("research", "The researched extras")], now),
                 lambda r: r and self.change(origins=[] if r == "all" else [r]))
        elif key == "order":
            push(Pick("Order", [("score", "Best rating first"), ("section", "By section, in syllabus order")], c["order"]),
                 lambda r: r and self.change(order=r))
        elif key == "new_per_day":
            push(Pick("How many new shortcuts a day?", [(str(n), str(n)) for n in PER_DAY], str(c["new_per_day"])),
                 lambda r: r and self.change(new_per_day=int(r)))
        elif key == "lessons_only":
            self.change(lessons_only=not c["lessons_only"])
        elif key == "recall_scope":
            push(Pick("What does shortcut recall cover?",
                      [("learned", "What you have learned and the filters still allow"),
                       ("all", "Everything you have learned, even if the filters now leave it out")], c["recall_scope"]),
                 lambda r: r and self.change(recall_scope=r))


# ============================ the shared screen frame ============================
class _CourseScreen(ReadAloud, Screen):
    studies = True
    BINDINGS = [Binding("ctrl+b", "leave", "Menu", priority=True), Binding("escape", "back", "Back"),
                Binding("enter", "advance", "Next", show=False), Binding("space", "advance", show=False),
                Binding("left", "back_step", show=False), Binding("s", "settings", "Settings"),
                Binding("question_mark", "app.help", "Help"), READ_KEY]
    TITLE = "Shortcuts"

    def __init__(self) -> None:
        super().__init__()
        self.phase = "start"
        self.course: sc.Course | None = None

    def compose(self) -> ComposeResult:
        yield Static(id="bar")
        with VerticalScroll(id="log", can_focus=False):
            yield Static(id="card")
        yield Container(id="panel")
        yield Footer()

    # ---------- plumbing ----------
    @property
    def vault(self):
        return self.app.tutor.vault

    @property
    def tz(self):
        return self.vault.tz

    def new_course(self) -> sc.Course:
        self.course = sc.Course(self.vault)
        return self.course

    def card(self, text: Text | str) -> None:
        text = Text(text) if isinstance(text, str) else text
        self.query_one("#card", Static).update(text)
        self.query_one("#log", VerticalScroll).scroll_home(animate=False)
        self.readable_now(text.plain)

    def panel(self, widget=None) -> None:
        """Replace what is in the bottom box (nothing, a list or a text box) and put the cursor in it."""
        box = self.query_one("#panel", Container)
        box.remove_children()
        if widget is not None:
            box.mount(widget)
            self.call_after_refresh(widget.focus)
        else:
            self.call_after_refresh(self.set_focus, None)

    def actions(self, choices, **kw) -> None:
        self.panel(Actions(choices, **kw))

    def bar_text(self) -> Text:
        return Text(f" {self.TITLE} ", style=f"bold {C['badge_fg']} on {C['badge_bg']}")

    def update_bar(self, extra: str = "") -> None:
        t = self.bar_text()
        if extra:
            t.append(f" {extra} ", style="bold")
        self.query_one("#bar", Static).update(t)

    def hint(self, text: str) -> Text:
        return Text(text, style=C["muted"])

    # ---------- keys ----------
    def action_leave(self) -> None:
        if not any(w.value.strip() for w in self.query(".sc-input")):
            self.app.pop_screen()
            return

        def decided(choice: str | None) -> None:
            if choice == "leave" and self.is_current:
                self.app.pop_screen()
        self.app.push_screen(ConfirmScreen("Leave? Your typed answer will be lost.",
                                            [("leave", "Leave"), ("stay", "Keep writing")]), decided)

    def action_back(self) -> None:
        self.action_leave()

    def action_back_step(self) -> None:
        pass

    def action_advance(self) -> None:
        pass

    def action_settings(self) -> None:
        if self.course is None:
            self.new_course()
        self.settings_before = self.course.cfg.copy()
        self.app.push_screen(ShortcutSettingsScreen(self.course), self.settings_closed)

    def settings_closed(self, _=None) -> None:
        if self.course.cfg == self.settings_before:
            return
        if self.phase in ("start", "empty"):
            self.restart()
        else:
            # The current queue includes work already done and possibly a typed answer.
            self.app.notify("Settings saved. They apply to your next set of shortcuts.", timeout=6)

    def restart(self) -> None:
        raise NotImplementedError

    def act(self, key: str) -> None:
        raise NotImplementedError

    @on(OptionList.OptionSelected, ".sc-actions")
    def chose(self, event: OptionList.OptionSelected) -> None:
        event.stop()
        self.act(event.option.id)


# ============================ learn ============================
class ShortcutsScreen(_CourseScreen):
    BINDINGS = [Binding("ctrl+g", "hint", "Hint", priority=True)]
    TITLE = "Shortcuts"

    def __init__(self) -> None:
        super().__init__()
        self.queue: list[dict] = []
        self.qi = 0
        self.learned_now = 0
        self.secs: list[tuple[str, Text]] = []
        self.shown = 0
        self.prac: list[dict] = []
        self.pi = 0
        self.hints_used = 0
        self.checked: dict | None = None

    def on_mount(self) -> None:
        self.new_course()
        self.restart()

    # ---------- start ----------
    def restart(self) -> None:
        c = self.course
        self.phase = "start"
        self.update_bar("Learn")
        pool, sel = len(c.pool()), len(c.entries())
        st = c.stats()
        left = max(0, c.cfg["new_per_day"] - st["new_today"])
        t = Text()
        t.append("Shortcuts and elegant methods\n", style=f"bold {C['tutor']}")
        t.append("A shortcut is taught in small steps, then practised, then it comes back later in shortcut recall. "
                 "This is separate from your syllabus chapters.\n\n", style=C["text"])
        t.append("Now: ", style="bold")
        t.append(filters_text(c.cfg) + "\n\n", style=C["muted"])
        choices: list[tuple[str, str]] = []
        todo = c.next_lessons()
        if not pool:
            t.append(NO_CONTENT + "\n", style=C["hint"])
        elif not sel:
            t.append("Your filters leave nothing. Press s to widen them.\n", style=C["hint"])
        else:
            t.append(f"{sel} shortcut{'s' if sel != 1 else ''} {'match' if sel != 1 else 'matches'} ({st['lessons']} with a full lesson); {st['learned']} learned so far; "
                     f"{st['new_today']} new today of {c.cfg['new_per_day']}.\n", style=C["text"])
            if todo:
                choices.append(("start", f"Learn {len(todo)} new shortcut{'s' if len(todo) != 1 else ''} ⏎"))
            else:
                more = c.next_lessons(max(1, c.cfg["new_per_day"] or 5))
                if more:
                    t.append("You have learned today's quota. Raise 'new a day' in settings, or carry on anyway.\n",
                             style=C["good"])
                    choices.append(("more", f"Learn {len(more)} more anyway"))
                else:
                    t.append("You have learned every shortcut these filters allow. Widen them for more.\n",
                             style=C["good"])
            if st["due"]:
                choices.append(("recall", f"Shortcut recall: {st['due']} due"))
        choices += [("settings", "Change settings (s)"), ("home", "Back to menu")]
        self.card(t)
        self.actions(choices)

    def act(self, key: str) -> None:
        ph = self.phase
        if ph == "start":
            if key in ("start", "more"):
                self.queue = self.course.next_lessons(None if key == "start" else max(1, self.course.cfg["new_per_day"] or 5))
                self.qi, self.learned_now = 0, 0
                self.begin_entry()
            elif key == "settings":
                self.action_settings()
            elif key == "recall":
                self.app.switch_screen(ShortcutRecallScreen())
            else:
                self.app.pop_screen()
        elif ph == "practice":
            self.answer_choice(key)
        elif ph == "self-mark":
            self.mark_short(key == "ok")
        elif ph == "rate":
            self.rate(int(key))
        elif ph == "done":
            if key == "recall":
                self.app.switch_screen(ShortcutRecallScreen())
            elif key == "again":
                self.restart()
            else:
                self.app.pop_screen()

    # ---------- the card sequence ----------
    def header(self) -> Text:
        e = self.queue[self.qi]
        t = Text()
        t.append(txt(e.get("title")) or e["id"], style=f"bold {C['tutor']}")
        t.append(f"  {e['score']}/10 ", style=f"bold {C['badge_fg']} on {C['badge_bg']}")
        t.append(f"\n{txt(e.get('section'))}  ·  shortcut {self.qi + 1} of {len(self.queue)}\n", style=C["dim"])
        return t

    def begin_entry(self) -> None:
        e = self.queue[self.qi]
        self.secs, self.shown = sections_of(e), 1
        self.prac, self.pi = practice_of(e), 0
        self.phase = "reveal"
        self.update_bar(f"Learn {self.qi + 1}/{len(self.queue)}")
        self.panel()
        self.show_reveal()

    def show_reveal(self) -> None:
        e = self.queue[self.qi]
        t = self.header()
        if not isinstance(e.get("lesson"), dict):
            t.append("\nA full lesson is not written for this one yet, so this is the source note itself.\n",
                     style=C["hint"])
        for head, body in self.secs[:self.shown]:
            t.append(f"\n{head}\n", style=f"bold {C['question']}")
            t.append_text(body)
            t.append("\n")
        more = self.shown < len(self.secs)
        t.append("\n" + (f"⏎ or space: next ({self.shown} of {len(self.secs)}) · ← or Esc: back"
                         if more else "⏎ or space: " + ("practise it" if self.prac else "rate it") + " · ← back"),
                 style=C["muted"])
        self.card(t)
        self.query_one("#log", VerticalScroll).scroll_end(animate=False)

    def action_advance(self) -> None:
        if self.phase == "reveal":
            if self.shown < len(self.secs):
                self.shown += 1
                self.show_reveal()
            elif self.prac:
                self.start_practice()
            else:
                self.start_rating()
        elif self.phase == "feedback":
            self.pi += 1
            self.next_practice()

    def action_back_step(self) -> None:
        if self.phase == "reveal" and self.shown > 1:
            self.shown -= 1
            self.show_reveal()

    def action_back(self) -> None:
        if self.phase == "reveal" and self.shown > 1:
            self.action_back_step()
        else:
            self.action_leave()

    # ---------- practice ----------
    def start_practice(self) -> None:
        self.pi = 0
        self.next_practice()

    def next_practice(self) -> None:
        if self.pi >= len(self.prac):
            self.start_rating()
            return
        p = self.prac[self.pi]
        self.hints_used, self.checked = 0, None
        kind = p.get("kind") if p.get("kind") in ("numeric", "mcq", "short") else "short"
        if kind == "mcq" and not isinstance(p.get("options"), dict):
            kind = "short"
        self.kind = kind
        self.phase = "practice"
        self.update_bar(f"Practice {self.pi + 1}/{len(self.prac)}")
        self.show_question()
        if kind == "mcq":
            opts = [(str(k).upper(), Text(f"{str(k).upper()}  {txt(v)}").plain) for k, v in p["options"].items()]
            self.actions(opts, letters=True)
        else:
            self.panel(Input(placeholder="your answer, then ⏎" if kind == "numeric" else
                             "write your answer in a line, then ⏎ to see the answer", classes="sc-input"))

    def show_question(self, extra: Text | None = None) -> None:
        p = self.prac[self.pi]
        t = Text()
        t.append(f"{txt(self.queue[self.qi].get('title'))}: practice {self.pi + 1} of {len(self.prac)}\n\n",
                 style=f"bold {C['tutor']}")
        t.append(txt(p["stem"]) + "\n", style=C["text"])
        hints = items(p.get("hints"))[:HINTS]
        for n, h in enumerate(hints[:self.hints_used], 1):
            t.append(f"\nHint {n}: {h}", style=C["hint"])
        if extra is None:
            more = len(hints) - self.hints_used
            t.append("\n\n" + (f"ctrl+g: hint ({more} left) · " if more > 0 else "") + "Esc: leave",
                     style=C["muted"])
        else:
            t.append("\n").append_text(extra)
        self.card(t)

    def action_hint(self) -> None:
        if self.phase == "practice" and self.hints_used < len(items(self.prac[self.pi].get("hints"))[:HINTS]):
            self.hints_used += 1
            self.show_question()

    @on(Input.Submitted, ".sc-input")
    def typed(self, event: Input.Submitted) -> None:
        event.stop()
        given = event.value.strip()
        if self.phase != "practice" or not given:
            return
        p = self.prac[self.pi]
        if self.kind == "numeric":
            self.finish_practice(numeric_ok(given, p["answer"], p["stem"]), given)
        else:
            self.phase = "self-mark"
            self.show_question(self.answer_text(p, given, None))
            self.actions([("ok", "I had it"), ("miss", "Not quite")])

    def answer_text(self, p: dict, given: str, ok: bool | None) -> Text:
        t = Text()
        if ok is not None:
            t.append(("Correct. " if ok else "Not quite. ") + (f"You wrote {given}.\n" if given else "\n"),
                     style=C["good"] if ok else C["bad"])
        elif given:
            t.append(f"You wrote: {given}\n", style=C["dim"])
        if self.kind == "mcq":
            ans = str(p["answer"]).strip().upper()
            full = txt((p.get("options") or {}).get(ans, (p.get("options") or {}).get(ans.lower())))
            t.append(f"Answer: {ans}" + (f"  {full}" if full else "") + "\n", style="bold")
        else:
            t.append(f"Answer: {txt(p['answer'])}\n", style="bold")
        if txt(p.get("explanation")):
            t.append(txt(p["explanation"]) + "\n")
        if txt(p.get("shortcut_use")):
            t.append("Where the shortcut comes in: ", style="bold")
            t.append(txt(p["shortcut_use"]) + "\n")
        return t

    def answer_choice(self, key: str) -> None:
        p = self.prac[self.pi]
        self.finish_practice(key == str(p["answer"]).strip().upper(), key)

    def mark_short(self, ok: bool) -> None:
        self.record_practice(ok)
        self.pi += 1
        self.next_practice()

    def record_practice(self, ok: bool) -> None:
        rating = 1 if not ok else 2 if self.hints_used else 3
        self.course.record("practice", self.queue[self.qi]["id"], rating)

    def finish_practice(self, ok: bool, given: str) -> None:
        p = self.prac[self.pi]
        self.record_practice(ok)
        self.phase = "feedback"
        t = self.answer_text(p, given, ok)
        t.append("\n⏎ or space: continue", style=C["muted"])
        self.show_question(t)
        self.panel()

    # ---------- rating ----------
    def start_rating(self) -> None:
        self.phase = "rate"
        self.update_bar(f"Learn {self.qi + 1}/{len(self.queue)}")
        t = self.header()
        t.append("\nHow well did you grasp this one? It comes back in shortcut recall sooner if you say 1 or 2.\n",
                 style=C["text"])
        self.card(t)
        self.actions(RATE_LABELS, digits=True, current=2)

    def rate(self, rating: int) -> None:
        e = self.queue[self.qi]
        self.course.record("learn", e["id"], rating, mode="lesson")
        self.learned_now += 1
        self.qi += 1
        if self.qi < len(self.queue):
            self.begin_entry()
        else:
            self.finish()

    def finish(self) -> None:
        self.phase = "done"
        self.update_bar("Done")
        c = self.new_course()
        st = c.stats()
        t = Text()
        t.append("Well done\n", style=f"bold {C['good']}")
        t.append(f"You learned {self.learned_now} shortcut{'s' if self.learned_now != 1 else ''} just now ({st['new_today']} "
                 f"today, {st['learned']} in all).\n", style=C["text"])
        t.append("The first recall of each comes back when it is due: " + when_text(next_due(c), self.tz) + ".\n",
                 style=C["muted"])
        choices = []
        if c.next_lessons():
            choices.append(("again", f"Learn {len(c.next_lessons())} more today"))
        if st["due"]:
            choices.append(("recall", f"Shortcut recall: {st['due']} due now"))
        choices.append(("home", "Back to menu"))
        self.card(t)
        self.actions(choices)


# ============================ recall ============================
class ShortcutRecallScreen(_CourseScreen):
    TITLE = "Shortcut recall"

    def __init__(self) -> None:
        super().__init__()
        self.queue: list[str] = []
        self.i = 0
        self.counts = {1: 0, 2: 0, 3: 0, 4: 0}
        self.entry: dict | None = None
        self.qa: dict | None = None
        self.rng = random.Random()

    def on_mount(self) -> None:
        self.new_course()
        self.restart()

    def restart(self) -> None:
        c = self.course
        self.queue = c.due()
        self.i = 0
        self.counts = {1: 0, 2: 0, 3: 0, 4: 0}
        self.update_bar("Recall")
        if not self.queue:
            self.nothing_due()
        else:
            self.ask()

    def by_id(self) -> dict[str, dict]:
        return {e["id"]: e for e in self.course.pool()}

    def nothing_due(self) -> None:
        c = self.course
        self.phase = "empty"
        st = c.stats()
        t = Text()
        t.append("Nothing is due\n", style=f"bold {C['good']}")
        if not c.pool():
            t.append(NO_CONTENT + "\n", style=C["hint"])
        elif not st["learned"]:
            t.append("You have not learned any shortcuts yet, so there is nothing to recall. Learn some first.\n",
                     style=C["text"])
        else:
            t.append(f"You have learned {st['learned']} shortcut{'s' if st['learned'] != 1 else ''}. The next one is due "
                     f"{when_text(next_due(c), self.tz)}.\n", style=C["text"])
        t.append("\n" + filters_text(c.cfg) + "\n", style=C["dim"])
        choices = []
        if c.cfg["new_per_day"] > st["new_today"] and c.next_lessons():
            choices.append(("learn", f"Learn more: {len(c.next_lessons())} new for today"))
        choices += [("settings", "Change settings (s)"), ("home", "Back to menu")]
        self.card(t)
        self.actions(choices)

    # ---------- one card ----------
    def ask(self) -> None:
        by = self.by_id()
        while self.i < len(self.queue) and self.queue[self.i] not in by:  # an entry that has since left the course
            self.queue.pop(self.i)
        if self.i >= len(self.queue):
            self.summary()
            return
        self.entry = by[self.queue[self.i]]
        self.qa = self.rng.choice(self.course.recall_cards(self.entry))
        self.phase = "question"
        self.update_bar(f"Recall {self.i + 1}/{len(self.queue)}")
        t = Text()
        t.append(f"{txt(self.entry.get('title'))}  ", style=f"bold {C['tutor']}")
        t.append(f"{txt(self.entry.get('section'))}\n\n", style=C["dim"])
        t.append(txt(self.qa["q"]) + "\n", style=C["text"])
        t.append("\nThink of the answer, then ⏎ or space to see it · Esc: stop", style=C["muted"])
        self.card(t)
        self.panel()

    def action_advance(self) -> None:
        if self.phase != "question":
            return
        self.phase = "answer"
        t = Text()
        t.append(f"{txt(self.entry.get('title'))}\n\n", style=f"bold {C['tutor']}")
        t.append(txt(self.qa["q"]) + "\n\n", style=C["dim"])
        t.append(txt(self.qa["a"]) + "\n", style=C["text"])
        t.append("\nHow well did you remember it?", style=C["muted"])
        self.card(t)
        self.actions(RATE_LABELS, digits=True, current=2)

    def act(self, key: str) -> None:
        if self.phase == "answer":
            rating = int(key)
            self.course.record("recall", self.entry["id"], rating, mode="recall")
            self.counts[rating] += 1
            self.i += 1
            self.ask()
        elif self.phase in ("empty", "summary"):
            if key == "again":
                self.restart()
            elif key == "learn":
                self.app.switch_screen(ShortcutsScreen())
            elif key == "settings":
                self.action_settings()
            else:
                self.app.pop_screen()

    def summary(self) -> None:
        c = self.new_course()
        self.phase = "summary"
        self.update_bar("Done")
        n = sum(self.counts.values())
        t = Text()
        t.append("Recall done\n", style=f"bold {C['good']}")
        t.append(f"You recalled {n} shortcut{'s' if n != 1 else ''}: " + ", ".join(
            f"{self.counts[r]} {sc.RATINGS[r].lower()}" for r in (1, 2, 3, 4)) + ".\n", style=C["text"])
        still = len(c.due())
        t.append((f"{still} more due now.\n" if still else "Nothing else is due. ")
                 + ("" if still else f"The next is due {when_text(next_due(c), self.tz)}.\n"), style=C["muted"])
        choices = []
        if still:
            choices.append(("again", f"Recall the {still} still due"))
        if c.cfg["new_per_day"] > c.stats()["new_today"] and c.next_lessons():
            choices.append(("learn", "Learn more new shortcuts"))
        choices.append(("home", "Back to menu"))
        self.card(t)
        self.actions(choices)
