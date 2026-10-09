"""Challenge: a set of hard calculation questions written by AI in advance, then done one at a time with a check
each. Set up in words or with a list of settings. Answers go to the set's own file (tutorlib.challenge): the
learner's model, sessions and reviews are not touched."""
from __future__ import annotations

import asyncio
import inspect
import random
import time

from rich.console import Group
from rich.markup import escape
from rich.text import Text
from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Input, OptionList, SelectionList, Static
from textual.widgets.option_list import Option
from textual.widgets.selection_list import Selection

from tutorlib import challenge as ch
from tutorlib import challenge_gen, grade, model
from tutorlib.challenge_gen import generate_set
from tutorlib.session import _display_answer

from . import cards, prompts
from .look import C
from .panels import ChoicePanel, Composer, ContinuePanel, Panel, TickList, ValuePanel
from .screens import AskScreen, ConfirmScreen, PickerScreen, bar, leave_asking_first

LEVEL = {lv["level"]: lv for lv in ch.LEVELS}
KIND_TEXT = {"mcq": "multiple choice", "typed": "typed answer"}
KINDS = [("mcq", "Multiple choice only"), ("typed", "Typed answers only (no options, so no hints)"),
         ("mix:0.5", "Mix: about half typed"), ("mix:0.75", "Mix: mostly typed"),
         ("mix:0.25", "Mix: mostly multiple choice")]
MODELS = {"sonnet": "Sonnet: faster, lighter on your limit",
          "opus": "Opus: slower and stronger, uses much more of your limit"}
MINUTES = {"sonnet": 1.5, "opus": 4.0}  # rough minutes to write and check one question; three are made at a time
SUBJECT = {"9701": "Chem", "9702": "Phys"}
WORDS_HINT = "e.g. 12 questions, easy to extreme, fast then slow"  # fits the box at 60 columns


def kinds_text(cfg: dict) -> str:
    if cfg["kinds"] != "mix":
        return dict(KINDS)[cfg["kinds"]]
    return dict(KINDS).get(f"mix:{cfg['typed_share']:g}", f"Mix: {round(100 * cfg['typed_share'])}% typed")


def plan_text(slots: list[dict]) -> str:
    """'Q1 3 · Q2 4 · Q3 6 (M T M)': the level of each question, then its type."""
    levels = " · ".join(f"Q{s['n']} {s['level']}" for s in slots)
    return f"{levels} ({' '.join('T' if s['kind'] == 'typed' else 'M' for s in slots)})"


def wait_text(cfg: dict) -> str:
    n, m = cfg["count"], cfg["model"]
    mins = max(1, round(n * MINUTES[m] / 3))
    return (f"About {4 * n} AI calls (4 a question, more when one is retried); roughly {mins} min with {m.title()}."
            + (" Opus uses much more of your limit." if m == "opus" else ""))


def level_text(q: dict) -> str:
    """'level 9', or 'level 9 (asked for 10)' when the checked question came out easier than asked."""
    asked = q.get("requested")
    return f"level {q['level']}" + (f" (asked for {asked})" if asked and asked != q["level"] else "")


def fallback_text(fb, chosen: str) -> str:
    """One line when the chosen model declined some calls and the other one stepped in."""
    count = fb.get("count", 0) if isinstance(fb, dict) else fb if isinstance(fb, int) else 0
    if not count:
        return ""
    if isinstance(fb, dict) and fb.get("note"):
        return str(fb["note"])
    other = "sonnet" if chosen == "opus" else "opus"
    return (f"{chosen.title()} declined {count} request{'s' if count > 1 else ''}; {other.title()} did "
            f"{'them' if count > 1 else 'it'} instead.")


def cheer(best: int | None) -> str:
    if best is None:
        return "These are meant to be hard. Read the worked solutions, then try a set a level or two lower."
    if best <= 4:
        return "Good going. Next time, push the hardest level up one."
    if best <= 6:
        return "That is the hard end of a real paper: exam-ready thinking."
    if best <= 8:
        return "Harder than most exams ever ask. Impressive."
    return "Olympiad-level problem solving. Outstanding."


# ============================ setup widgets ============================
class SettingsList(OptionList):
    """The settings, one a row with its value: ⏎ changes one, ← → step it."""
    BINDINGS = [Binding("left", "step(-1)", show=False), Binding("right", "step(1)", show=False)]

    def action_step(self, delta: int) -> None:
        if self.highlighted is not None:
            self.screen.step(self.get_option_at_index(self.highlighted).id, delta)


class SetupPanel(Panel):
    """Words box, settings list, and what the set will be (scrolls in a small window)."""

    def __init__(self, note: str = "") -> None:
        super().__init__(classes="panel setup")
        self.note = note

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="setup"):
            if self.note:
                yield Static(Text(self.note, style=C["hint"]), id="setup-note")
            yield Static("Say what you want and ⏎, or change a setting below: ↑↓ ⏎ (← → step). Esc: menu.",
                         classes="hint")
            yield Composer(placeholder=WORDS_HINT, id="words")
            yield Static(id="understood")
            yield SettingsList(id="settings")
            yield Static(id="detail")
            yield Static(id="preview")

    def on_mount(self, event) -> None:
        event.prevent_default()  # not Panel's: the list has the focus, not the words box above it
        self.screen.refresh_setup()
        self.query_one("#settings", SettingsList).focus()


class TopicScreen(PickerScreen):
    """Tick the chapters; the earlier chapters they build on come in by themselves."""

    def __init__(self, chosen: list[str]) -> None:
        super().__init__("challenge")
        self.chosen = chosen

    def compose(self) -> ComposeResult:
        rows = ch.topic_choices(self.app.tutor.packs)
        with Vertical(id="picker"):
            yield Static("Tick the chapters (space), then ctrl+s or Done. Earlier chapters they build on are "
                         "included by themselves. Esc cancels.", classes="hint")
            yield TickList(*[Selection(escape(f"{SUBJECT.get(r['spec'], 'Maths'):<5} {r['id']}  {r['title']}"
                                              + ("" if r["built"] else "  (no questions built yet)")),
                                       r["id"], r["id"] in self.chosen) for r in rows], id="subs")
            yield Static(id="scope", classes="hint")
            yield Button("Done", id="done", variant="primary")

    def on_mount(self) -> None:
        self.show_scope()

    @on(SelectionList.SelectedChanged, "#subs")
    def show_scope(self) -> None:
        picked = list(self.query_one("#subs", SelectionList).selected)
        self.query_one("#scope", Static).update(ch.scope_summary(self.app.tutor.packs, picked))

    @on(Button.Pressed, "#done")
    def action_go(self) -> None:
        picked = list(self.query_one("#subs", SelectionList).selected)
        if picked:
            self.dismiss(picked)
        else:
            self.app.notify("Tick at least one chapter (space), then Done.", timeout=5)


class CountScreen(AskScreen):
    def __init__(self, count: int) -> None:
        super().__init__()
        self.count = count

    def compose(self) -> ComposeResult:
        with Vertical(id="ask"):
            yield Static(f"How many questions? 1 to {ch.MAX_COUNT}. ⏎ sets it, Esc cancels.", classes="hint")
            yield Input(str(self.count), id="count", type="integer")

    def on_mount(self, event) -> None:
        event.prevent_default()  # not AskScreen's: it has no words box
        self.query_one("#count", Input).focus()

    @on(Input.Submitted, "#count")
    def typed(self, event: Input.Submitted) -> None:
        try:
            self.dismiss(int(event.value))
        except ValueError:
            self.dismiss(None)


class PickScreen(ConfirmScreen):
    """One choice from a list, the current one highlighted."""

    def __init__(self, question: str, choices: list[tuple[str, str]], current: str) -> None:
        super().__init__(question, choices)
        self.current = current

    def on_mount(self) -> None:
        ids = [cid for cid, _ in self.choices]
        self.query_one("#confirm", OptionList).highlighted = ids.index(self.current) if self.current in ids else 0


class ChallengeChoice(ChoicePanel):
    def on_mount(self) -> None:
        self.query_one(".hint", Static).update(f"Q{self.n}: choose with ↑↓ and ⏎ (or press A-D).  0 = I don't know.")


# ============================ the screen ============================
class ChallengeScreen(Screen):
    BINDINGS = [Binding("ctrl+b", "leave", "Menu", priority=True), Binding("escape", "esc", "Back"),
                Binding("alt+up", "scroll_log(-1)", show=False, priority=True),
                Binding("alt+down", "scroll_log(1)", show=False, priority=True),
                Binding("pageup", "scroll_log(-1)", show=False), Binding("pagedown", "scroll_log(1)", show=False),
                Binding("question_mark", "app.help", "Help")]

    def __init__(self) -> None:
        super().__init__()
        self.phase, self.set, self.fb, self.i = "start", None, None, 0
        self.seed = random.randrange(1 << 30)
        self.clock = time.monotonic()

    def compose(self) -> ComposeResult:
        yield Static(id="bar")
        yield VerticalScroll(id="log", can_focus=False)
        yield Container(id="panel")
        yield Footer()

    # ---------- plumbing ----------
    @property
    def packs(self):
        return self.app.tutor.packs

    @property
    def vault(self):
        return self.app.tutor.vault

    def say(self, renderable) -> Static:
        w = Static(renderable, classes="entry")
        log = self.query_one("#log", VerticalScroll)
        log.mount(w)
        log.scroll_end(animate=False)
        return w

    def fold(self) -> None:
        for w in self.query("#log > .entry"):
            w.remove()

    def panel(self, widget) -> None:
        box = self.query_one("#panel", Container)
        box.remove_children()
        box.mount(widget)
        self.showing = widget

    def ai_ok(self) -> bool:
        return bool(self.app.settings.ai and self.app.ai.available)

    def ai_problem(self) -> str:
        a = self.app.ai
        if not self.app.settings.ai:
            return "AI is switched off, and new questions are written by AI: switch it on in Settings (F2 on the menu)."
        return ("New questions are written by AI, which is unavailable right now. "
                + (a.message or "Check that Claude Code is installed and signed in (claude auth login)."))

    def on_mount(self) -> None:
        self.cfg = ch.load_config(self.vault, self.packs)
        self.set_interval(1, self.update_bar)
        try:
            left = ch.ChallengeSet.open_latest_unfinished(self.vault)
        except Exception:  # noqa: BLE001 - a damaged set file never keeps you out of Challenge
            left = None
        if left is None:
            self.setup()
            return
        self.set = left
        done, n = left.summary()["answered"], len(left.questions)
        self.say(cards.card("plan", "You have an unfinished set",
                            f"{n} questions on {', '.join(left.cfg.get('topics', [])) or 'your topics'}; "
                            f"{done} answered so far."))
        self.panel(ContinuePanel(buttons=[("resume", f"Continue your set ({done} of {n} done) ⏎"),
                                          ("new", "New set"), ("home", "Back to menu")]))
        self.update_bar()

    # ---------- the top bar ----------
    def bar_text(self, width: int) -> Text:
        head, tail = Text(), Text()
        head.append(" Challenge ", style=f"bold {C['badge_fg']} on {C['badge_bg']}")
        if self.phase == "question" and self.set:
            q = self.set.questions[self.i]
            head.append(f" {self.i + 1}/{len(self.set.questions)} · {level_text(q)} · "
                        f"{LEVEL.get(q['level'], {}).get('name', '')} · {KIND_TEXT.get(q['kind'], q['kind'])} ",
                        style="bold")
        else:
            head.append(f" {({'setup': 'Set up', 'generating': 'Writing your set', 'summary': 'Your score'}).get(self.phase, '')} ",
                        style="bold")
        if self.phase in ("question", "generating"):
            mins, secs = divmod(int(time.monotonic() - self.clock), 60)
            tail.append(f" ◷ {mins:02d}:{secs:02d} ", style=C["plan"])
        if self.set and self.phase in ("question", "summary"):
            s = self.set.summary()
            tail.append(f" ✓ {s['correct']}/{s['answered']} ", style=C["good"])
        if head.cell_len + tail.cell_len <= width:
            return head + tail
        for line in (head, tail):
            line.truncate(width, overflow="ellipsis")
        return head + Text("\n") + tail

    def update_bar(self) -> None:
        self.query_one("#bar", Static).update(self.bar_text(self.size.width or self.app.size.width))

    # ---------- setup ----------
    def setup(self, note: str = "") -> None:
        self.phase, self.seed = "setup", random.randrange(1 << 30)
        self.fold()
        self.set_class(True, "setup")
        if not self.ai_ok():
            note = (note + "\n" if note else "") + self.ai_problem()
        self.panel(SetupPanel(note))
        self.update_bar()

    def rows(self) -> list[tuple[str, str]]:
        c = self.cfg
        topics = c["topics"]
        shown = ", ".join(topics[:3]) + (f" +{len(topics) - 3}" if len(topics) > 3 else "") if topics else \
            "none yet: ⏎ to choose"
        return [("topics", f"Topics     {shown}"), ("count", f"How many   {c['count']}"),
                ("kinds", f"Types      {kinds_text(c)}"),
                ("lo", f"Easiest    level {c['lo']} · {LEVEL[c['lo']]['name']}"),
                ("hi", f"Hardest    level {c['hi']} · {LEVEL[c['hi']]['name']}"),
                ("ramp", f"Ramp       {c['ramp']}"), ("model", f"Model      {c['model'].title()}"),
                ("start", "Start ⏎")]

    def detail(self, key: str | None) -> str:
        c = self.cfg
        if key in ("lo", "hi"):
            lv = LEVEL[c[key]]
            return f"Level {lv['level']}, {lv['name']}: {lv['blurb']} In exams: {lv['exam_chance']}."
        return {"topics": "Questions use these chapters and the earlier ones they build on: nothing outside.",
                "count": f"1 to {ch.MAX_COUNT}: ⏎ to type a number, ← → to step.",
                "kinds": "Typed answers have no options to guess from; units and significant figures are marked "
                         "as in an exam.",
                "ramp": ch.RAMPS.get(c["ramp"], ""), "model": MODELS[c["model"]],
                "start": "Writes and checks the whole set first, then shows it one question at a time. "
                         + wait_text(c)}.get(key, "")

    def refresh_setup(self) -> None:
        if not self.query("#settings"):
            return
        lst = self.query_one("#settings", SettingsList)
        keep = lst.highlighted
        lst.clear_options()
        lst.add_options([Option(escape(label), id=key) for key, label in self.rows()])
        lst.highlighted = keep if keep is not None else 0
        self.show_detail()
        preview = Text()
        preview.append("Scope: ", style="bold")
        preview.append(ch.scope_summary(self.packs, self.cfg["topics"]) + "\n", style=C["text"])
        preview.append("Plan: ", style="bold")
        preview.append(plan_text(ch.plan_slots(self.cfg, self.seed)) + "\n", style=C["text"])
        preview.append(wait_text(self.cfg), style=C["dim"])
        self.query_one("#preview", Static).update(preview)

    @on(OptionList.OptionHighlighted, "#settings")
    def show_detail(self) -> None:
        lst = self.query_one("#settings", SettingsList)
        key = lst.get_option_at_index(lst.highlighted).id if lst.highlighted is not None else None
        self.query_one("#detail", Static).update(Text(self.detail(key), style=C["muted"]))

    def change(self, **values) -> list[str]:
        cfg = {**self.cfg, **values}
        if "lo" in values and cfg["lo"] > cfg["hi"]:  # the easiest level raised past the hardest: it comes along
            cfg["hi"] = cfg["lo"]
        if "hi" in values and cfg["hi"] < cfg["lo"]:
            cfg["lo"] = cfg["hi"]
        self.cfg, notes = ch.normalise_config(cfg, self.packs)
        ch.save_config(self.vault, self.cfg)
        self.refresh_setup()
        return notes

    @on(Composer.Submitted, "#words")
    def words(self, event: Composer.Submitted) -> None:
        text = " ".join(event.value.split())
        if not text:
            return
        res = ch.parse_request(text, self.packs)
        notes = self.change(**res["config"])
        event.composer.text = ""
        out = Text()
        if res["understood"]:
            out.append("✓ Understood: " + ", ".join(res["understood"]) + "\n", style=C["good"])
        for line in res["unclear"] + notes:
            out.append(f"? {line}\n", style=C["hint"])
        if not res["understood"] and not res["unclear"]:
            out.append("? Nothing in that changes a setting.\n", style=C["hint"])
        out.rstrip()
        self.query_one("#understood", Static).update(out)

    @on(OptionList.OptionSelected, "#settings")
    def edit(self, event: OptionList.OptionSelected) -> None:
        key, c = event.option.id, self.cfg
        if key == "start":
            self.begin()
        elif key == "topics":
            self.app.push_screen(TopicScreen(c["topics"]), lambda r: r and self.change(topics=r))
        elif key == "count":
            self.app.push_screen(CountScreen(c["count"]), lambda r: r is not None and self.change(count=r))
        elif key == "kinds":
            self.app.push_screen(PickScreen("Question types", KINDS, "mix:" + f"{c['typed_share']:g}"
                                            if c["kinds"] == "mix" else c["kinds"]), self._kinds)
        elif key in ("lo", "hi"):
            self.app.push_screen(PickScreen(
                "Easiest level of the set" if key == "lo" else "Hardest level of the set",
                [(str(lv["level"]), f"{lv['level']:>2} {lv['name']}: {lv['blurb']} In exams: {lv['exam_chance']}.")
                 for lv in ch.LEVELS], str(c[key])), lambda r: r and self.change(**{key: int(r)}))
        elif key == "ramp":
            self.app.push_screen(PickScreen("How the difficulty changes through the set",
                                            [(k, f"{k}: {v}") for k, v in ch.RAMPS.items()], c["ramp"]),
                                 lambda r: r and self.change(ramp=r))
        elif key == "model":
            self.app.push_screen(PickScreen("Which model writes the questions? (A second model checks each one.)",
                                            list(MODELS.items()), c["model"]), lambda r: r and self.change(model=r))

    def _kinds(self, r: str | None) -> None:
        if r:
            kind, _, share = r.partition(":")
            self.change(kinds=kind, **({"typed_share": float(share)} if share else {}))

    def step(self, key: str, delta: int) -> None:
        c = self.cfg
        if key in ("count", "lo", "hi"):
            self.change(**{key: c[key] + delta})
        elif key in ("kinds", "ramp", "model"):
            ids = {"kinds": [k for k, _ in KINDS], "ramp": list(ch.RAMPS), "model": list(MODELS)}[key]
            now = ("mix:" + f"{c['typed_share']:g}" if c["kinds"] == "mix" else c["kinds"]) if key == "kinds" else c[key]
            new = ids[(ids.index(now) + delta) % len(ids)] if now in ids else ids[0]
            if key == "kinds":
                self._kinds(new)
            else:
                self.change(**{key: new})

    # ---------- generating ----------
    def begin(self) -> None:
        if not self.cfg["topics"]:
            self.app.notify("Choose at least one topic first: Topics, then ⏎.", severity="warning", timeout=6)
            if self.query("#settings"):
                self.query_one("#settings", SettingsList).highlighted = 0
            return
        if not self.ai_ok():
            self.app.notify(self.ai_problem(), severity="warning", timeout=10)
            return
        self.phase, self.clock = "generating", time.monotonic()
        self.set_class(False, "setup")
        self.fold()
        self.say(cards.card("plan", "Writing your set",
                            f"{self.cfg['count']} questions, levels {self.cfg['lo']} to {self.cfg['hi']}, "
                            f"{self.cfg['ramp']}, by {self.cfg['model'].title()}. Each one is written, solved "
                            "separately by a second model, then checked against your syllabus, so you only get "
                            f"questions that can be solved. {wait_text(self.cfg)}"))
        self.progress = self.say(self.progress_card(0, self.cfg["count"], ""))
        self.panel(ContinuePanel("Esc cancels: nothing is saved until the whole set is ready. You can leave the "
                                 "app safely at any time.", buttons=[]))
        self.update_bar()
        self.generate()

    def progress_card(self, done: int, total: int, last: str):
        body = Text()
        body.append(bar(done, total, 20), style=C["plan"])
        body.append(f"  {done} of {total} done\n", style=C["text"])
        body.append(f"Writing question {min(done + 1, total)} of {total}… checking it can be solved from your "
                    f"syllabus." if done < total else "Putting the set together…", style=C["muted"])
        if last:
            body.append(f"\nLast: {last}", style=C["dim"])
        return cards.framed(body, C["plan"], "[b]Progress[/b]", title_align="left")

    async def ask(self, prompt: str, schema: dict, model_name: str, timeout: float = 300) -> dict | None:
        """What the generator calls: one memory-less AI reply as a dict, or None (failed, timed out, unreadable).
        A model that declines raises challenge_gen.Refused, and the generator hands that call to the other model."""
        one_shot, system = self.app.ai.one_shot, challenge_gen.GEN_SYSTEM
        if "system" in inspect.signature(one_shot).parameters:
            data, res = await one_shot(prompt, schema=schema, model=model_name, timeout=timeout, system=system)
        else:  # an older Claude wrapper: the instructions go in front of the prompt
            data, res = await one_shot(f"{system}\n\n{prompt}", schema=schema, model=model_name, timeout=timeout)
        if data is None and "safeguards flagged" in (getattr(res, "message", "") or ""):
            raise challenge_gen.Refused(res.message)
        return data

    @work(exclusive=True, group="challenge")
    async def generate(self) -> None:
        cfg = dict(self.cfg)
        total = cfg["count"]

        def progress(done: int, of: int, last: str = "") -> None:
            if self.phase == "generating" and self.progress.is_attached:
                self.progress.update(self.progress_card(done, of or total, last))
        try:
            out = await generate_set(self.ask, cfg, ch.allowed_scope(self.packs, cfg["topics"]), on_progress=progress,
                                     cancelled=lambda: self.phase != "generating", parallel=3, seed=self.seed)
        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa: BLE001 - a broken run must never take the app down
            out = {"questions": [], "skipped": [], "error": f"{type(e).__name__}: {e}"}
        if self.phase != "generating":  # cancelled meanwhile
            return
        questions, skipped = out.get("questions") or [], out.get("skipped") or []
        why = out.get("error") or (skipped[0].get("reason") if skipped else "") or "no reason given"
        if not questions:
            more = "" if self.app.ai.available else f" {self.ai_problem()}"
            self.set_class(True, "setup")
            self.setup(f"No questions came out of that run ({why}). Nothing was saved: try again, perhaps with a "
                       f"lower hardest level.{more}")
            return
        self.set = ch.ChallengeSet.new(self.vault, cfg, questions)
        note = fallback_text(out.get("fallbacks"), cfg["model"])
        if isinstance(out.get("calls"), int):
            note += (" " if note else "") + f"Writing it took {out['calls']} AI calls."
        if skipped:
            note += (" " if note else "") + (f"{len(skipped)} question{'s' if len(skipped) > 1 else ''} could not be made solid enough and "
                    f"{'were' if len(skipped) > 1 else 'was'} left out ({why}): your set has {len(questions)}.")
        self.start_questions(note)

    def cancel(self) -> None:
        self.phase = "setup"  # the generator's `cancelled()` sees it at once
        self.workers.cancel_group(self, "challenge")

    # ---------- questions ----------
    def start_questions(self, note: str = "", keep: bool = True) -> None:
        """`note` (what happened while writing, or a welcome back) heads the first question; a writing note is also
        kept for the summary."""
        self.set_class(False, "setup")
        self.fold()
        self.notes, self.first_note = (note if keep else ""), note
        if note:
            self.app.notify(note, timeout=10)
        self.show_question(self.set.cursor)

    def show_question(self, i: int) -> None:
        if i >= len(self.set.questions):
            self.summary()
            return
        self.phase, self.i, self.fb, self.clock = "question", i, None, time.monotonic()
        q = self.set.questions[i]
        item = q["item"]
        for w in self.query("#log > .entry"):
            w.display = False  # the last feedback goes: the new question stands alone
        title = (f"[b]Q{i + 1}[/b] of {len(self.set.questions)} · {escape(level_text(q))}"  # the rest is in the bar
                 + (f" · by {q['model'].title()}" if q.get("model") and q["model"] != self.set.cfg.get("model") else ""))
        head = [Text(self.first_note + "\n", style=C["dim"])] if getattr(self, "first_note", "") else []
        self.first_note = ""  # on the first question only
        self.say(cards.framed(Group(*head, cards.md(item["stem"])), C["question"], title, title_align="left"))
        self.query_one("#log", VerticalScroll).scroll_home(animate=False)
        self.answer_panel()
        self.update_bar()

    def answer_panel(self) -> None:
        item = self.set.questions[self.i]["item"]
        if item["kind"] == "mcq":
            self.panel(ChallengeChoice(self.i + 1, item.get("options"), confidence=False))
        else:
            self.panel(ValuePanel(self.i + 1, item["kind"], confidence=False))

    def action_scroll_log(self, direction: int) -> None:
        """alt+↑ / alt+↓ (and page up / down): a long question or solution a page at a time, even while typing."""
        log = self.query_one("#log", VerticalScroll)
        log.scroll_relative(y=direction * max(1, log.scrollable_content_region.height - 1), animate=False)

    def mark(self, data: dict) -> None:
        q = self.set.questions[self.i]
        item = q["item"]
        parsed = grade.parse_responses(data["entry"])
        r = parsed[0] if parsed else {"kind": "bad"}
        problem = None
        if r["kind"] == "bad":
            problem = "Could not read that answer: type it again."
        elif item["kind"] == "numeric" and r["kind"] == "value":
            problem = {"unreadable": "Could not read the value: type a number and its unit, e.g. 4.5 m s^-1.",
                       "unit": "This one is a plain number: type it without a unit."}.get(
                grade.value_problem(item, str(r["value"])))
        elif item["kind"] == "expression" and r["kind"] == "value" and not grade.expression_readable(str(r["value"])):
            problem = "Could not read the expression: use letters, numbers, + - * / ^ and brackets."
        if problem:
            self.app.notify(problem, severity="warning", timeout=6)
            self.answer_panel()  # the same question, its clock still running
            return
        g = grade.grade_item(item, r)
        idk = r["kind"] == "idk"
        partial = bool(g["correct"]) and g["score"] < model.SUCCESS  # right value, a mark lost (unit, s.f.)
        correct = bool(g["correct"]) and not partial
        response = "don't know" if idk else str(r["value"])
        self.set.record(self.i, response, {**g, "correct": correct}, int(time.monotonic() - self.clock))
        self.fb = {"n": self.i + 1, "correct": correct, "partial": partial, "response": response,
                   "detail": None if idk else g.get("detail"), "answer": _display_answer(item),
                   "explanation": q.get("solution") or item.get("explanation", "")}
        card = self.say(cards.feedback(self.fb, data.get("your", "")))
        log = self.query_one("#log", VerticalScroll)
        log.call_after_refresh(log.scroll_to_widget, card, top=True, animate=False)  # its verdict first, not its end
        self.after_answer()

    def can_remark(self) -> bool:
        fb = self.fb or {}
        return bool(self.ai_ok() and fb and not fb["correct"] and not fb.get("remarked")
                    and fb["response"] != "don't know"
                    and self.set.questions[self.i]["item"]["kind"] in ("numeric", "expression"))

    def after_answer(self) -> None:
        last = self.i + 1 >= len(self.set.questions)
        buttons = [("finish", "See your score ⏎") if last else ("next", "Next ⏎")]
        buttons += [("why", "Explain this answer (AI)")] if self.ai_ok() else []
        buttons += [("remark", "Re-mark (AI)")] if self.can_remark() else []
        buttons += [] if last else [("stop", "Stop here (see score)")]
        self.panel(ContinuePanel(buttons=buttons))
        self.update_bar()

    @work(exclusive=True, group="ai")
    async def remark(self) -> None:
        """The program marks units and figures narrowly; if the AI examiner finds the answer right, it counts."""
        fb, item = self.fb, self.set.questions[self.i]["item"]
        self.panel(ContinuePanel("The AI examiner is checking the marking…", buttons=[]))
        view = {"kind": item["kind"], "stem": item["stem"], "options": item.get("options")}
        res, r = await self.app.ai.one_shot(prompts.remark(view, fb), schema=prompts.REMARK, model=prompts.REMARK_MODEL)
        if res:
            fb["remarked"] = True  # one re-mark an answer; a call that failed can be tried again
        if res and res.get("correct") is True and self.set.regrade(self.i, res.get("why", "")):
            fb["correct"] = True
            self.say(cards.card("tutor", "Re-marked: correct ✓",
                                f"{res.get('why', '')}\n\nIt now counts as right in this set's score."))
        elif res:
            self.say(cards.card("hint", "Re-marked: the mark stands", res.get("why", "")))
        else:
            self.say(cards.card("hint", "AI check unavailable", r.message or "Try again later."))
        self.after_answer()

    @work(exclusive=True, group="ai")
    async def explain(self) -> None:
        a, q = self.app.ai, self.set.questions[self.i]
        w = self.say(cards.ai("…"))
        buf = ""
        async for chunk in a.stream(prompts.challenge_explain(q["item"], q.get("solution", ""), self.fb["answer"],
                                                              self.fb["response"])):
            buf += chunk
            w.update(cards.ai(buf))
            self.query_one("#log", VerticalScroll).scroll_end(animate=False)
        if not a.last.ok:
            w.update(cards.card("hint", "AI paused", a.last.message))

    # ---------- summary ----------
    def summary(self) -> None:
        self.phase = "summary"
        self.fold()
        s, n = self.set.summary(), len(self.set.questions)
        mins, secs = divmod(s["seconds"], 60)
        best = s["best_level"]
        best_text = f"{best} {LEVEL[best]['name']}" if best else "none yet"
        rows = "  \n".join(f"{lv} {LEVEL.get(lv, {}).get('name', '')}: {right} of {total}"
                           for lv, (right, total) in s["by_level"].items())
        body = (f"**Score:** {s['correct']} right out of {s['answered']}"
                + (f" ({n - s['answered']} not tried)" if s["answered"] < n else "") + "  \n"
                f"**Highest level right:** {best_text}  \n"
                f"**Time:** {mins} min {secs} s\n\n"
                + (f"**By level**  \n{rows}\n\n" if rows else "")
                + cheer(best)
                + (f"\n\n_{getattr(self, 'notes', '')}_" if getattr(self, "notes", "") else ""))
        self.say(cards.card("good" if s["correct"] else "plan", "Your score", body))
        self.panel(ContinuePanel(buttons=[("again", "Another set (same settings) ⏎"), ("change", "Change settings"),
                                          ("home", "Back to menu")]))
        self.update_bar()

    # ---------- panel results and keys ----------
    @on(Panel.Done)
    def done(self, event: Panel.Done) -> None:
        if event.panel is not getattr(self, "showing", None):  # a panel already replaced (key repeat): once only
            return
        data = event.data
        if "entry" in data:
            self.mark(data)
            return
        button = data.get("button")
        if button not in ("why", "remark"):
            self.workers.cancel_group(self, "ai")  # an explanation still arriving stops: the next screen stays put
        if button == "resume":
            self.notes = ""
            self.start_questions(f"Welcome back: question {self.set.cursor + 1} of {len(self.set.questions)}.",
                                 keep=False)
        elif button == "new":
            self.set.close()  # set aside: not offered again
            self.set = None
            self.setup()
        elif button == "change":
            self.setup()
        elif button == "home":
            self.app.pop_screen()
        elif button == "next":
            self.show_question(self.set.cursor)
        elif button in ("finish", "stop"):
            if button == "stop":
                self.set.close()  # its score is shown now, once; the set does not come back
            self.summary()
        elif button == "why":
            self.explain()
        elif button == "remark":
            self.remark()
        elif button == "again":
            self.cfg = ch.normalise_config(self.set.cfg, self.packs)[0]  # the settings of the set just done
            self.seed = random.randrange(1 << 30)
            self.begin()

    def action_esc(self) -> None:
        if self.phase == "generating":
            self.cancel()
            self.setup("Cancelled: nothing was saved.")
        else:
            self.action_leave()

    def action_leave(self) -> None:
        """Back to the menu. A set being written is dropped; answers given so far are saved, and the set resumes."""
        if self.phase == "generating":
            self.cancel()
        if self.phase == "question" and self.fb is None:
            leave_asking_first(self, "#panel Composer")
        else:
            self.app.pop_screen()
