"""Answer panels shown at the bottom of the session screen. Each posts `Panel.Done(data)` when finished."""
from __future__ import annotations

import time

from rich.cells import cell_len
from rich.segment import Segment
from textual import events

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.markup import escape
from textual.message import Message
from textual.strip import Strip
from textual.widgets import Button, Input, OptionList, SelectionList, Static, TextArea
from textual.widgets.option_list import Option
from textual.widgets.selection_list import Selection

from .cards import CONF
from .texmath import to_terminal

DONT_KNOW = "?"


class Panel(Vertical):
    """Base: subclasses call self.finish(data)."""

    class Done(Message):
        def __init__(self, data: dict, panel: "Panel") -> None:
            self.data, self.panel = data, panel
            super().__init__()

    def finish(self, data: dict) -> None:
        self.post_message(self.Done(data, self))

    def on_mount(self) -> None:
        focusable = [w for w in self.query("OptionList, SelectionList, Input, TextArea, Button") if w.focusable]
        if focusable:
            focusable[0].focus()


def _hint(text: str) -> Static:
    return Static(text, classes="hint")


class Confidence(OptionList):
    """How sure are you? 1–4. Esc goes back to change your answer."""
    BINDINGS = [Binding(str(i), f"pick({i})", show=False) for i in range(1, 5)] + [Binding("escape", "back", "Change answer")]

    class Back(Message):
        pass

    def action_back(self) -> None:
        self.post_message(self.Back())

    def __init__(self) -> None:
        super().__init__(*[Option(f"{i}  {CONF[i]}", id=str(i)) for i in (1, 2, 3, 4)], id="conf")

    def action_pick(self, i: int) -> None:
        self.highlighted = i - 1
        self.action_select()


class Composer(TextArea):
    """A text box that wraps and grows over several lines. ⏎ sends what is in it; ctrl+j starts a new line."""

    class Submitted(Message):
        def __init__(self, composer: "Composer", value: str) -> None:
            self.composer, self.value = composer, value
            super().__init__()

        @property
        def control(self) -> "Composer":
            return self.composer

    def __init__(self, placeholder: str = "", id: str | None = None, compact: bool = False) -> None:
        super().__init__(soft_wrap=True, tab_behavior="focus", show_line_numbers=False, id=id, compact=compact)
        self.placeholder = placeholder

    def _on_key(self, event: events.Key) -> None:
        if event.key == "enter":
            event.stop()
            event.prevent_default()
            self.post_message(self.Submitted(self, self.text))
        elif event.key in ("ctrl+j", "shift+enter"):
            event.stop()
            event.prevent_default()
            self.insert("\n")


class ChoicePanel(Panel):
    """Multiple choice: ↑↓ + ⏎ (or the letter key), then confidence 1–4. Always offers "I don't know"."""
    BINDINGS = [Binding(k, f"letter('{k.upper()}')", show=False) for k in "abcd"] + \
               [Binding("0", "letter('?')", show=False)]

    def __init__(self, n: int, options: dict | None, confidence: bool = True) -> None:
        super().__init__(classes="panel")
        self.n, self.options, self.ask_conf, self.choice = n, options or {k: "" for k in "ABCD"}, confidence, None

    def compose(self) -> ComposeResult:
        yield _hint(f"Q{self.n}: choose with ↑↓ and ⏎ (or press A–D).  0 = I don't know.  Full question: Now in Obsidian (o).")
        opts = [Option(f"[b]{k}[/b]  {escape(to_terminal(v))}".rstrip(), id=k) for k, v in self.options.items()]
        yield OptionList(*opts, Option("[i]I don't know[/i]", id=DONT_KNOW), id="choices")
        yield Composer(placeholder="✎ optional note (Tab)", id="note", compact=True)  # its ⏎: back to the list

    def action_letter(self, letter: str) -> None:
        if self.choice is None and (letter in self.options or letter == DONT_KNOW):
            self._chosen(letter)

    @on(OptionList.OptionSelected, "#choices")
    def _picked(self, event: OptionList.OptionSelected) -> None:
        self._chosen(event.option.id or DONT_KNOW)

    def _chosen(self, letter: str) -> None:
        self.choice = letter
        if letter == DONT_KNOW or not self.ask_conf:
            self.finish({"entry": f"{self.n}?" if letter == DONT_KNOW else f"{self.n}{letter}",
                         "your": "I don't know" if letter == DONT_KNOW else letter, "note": self._note()})
            return
        for w in (self.query_one("#choices"), self.query_one(".hint"), self.query_one("#note")):
            w.display = False  # the confidence step alone, so a small window has room for all four levels
        self.mount(_hint(f"You chose {letter}. How sure are you? (1–4, Esc to change your answer)"), Confidence())
        self.query_one(Confidence).focus()

    @on(Confidence.Back)
    def _back(self) -> None:
        for w in list(self.query(Confidence)) + [h for h in self.query(".hint") if "How sure" in str(h.render())]:
            w.remove()
        self.choice = None
        self.query_one(".hint").display = self.query_one("#note").display = True
        ol = self.query_one("#choices", OptionList)
        ol.display = True
        ol.focus()

    @on(OptionList.OptionSelected, "#conf")
    def _conf(self, event: OptionList.OptionSelected) -> None:
        c = int(event.option.id or 3)
        self.finish({"entry": f"{self.n}{self.choice}{c}", "your": f"{self.choice} ({CONF[c].lower()})", "note": self._note()})

    @on(Composer.Submitted, "#note")
    def _noted(self) -> None:
        conf = self.query(Confidence)
        (conf.first() if conf else self.query_one("#choices")).focus()

    def _note(self) -> str:
        return " ".join(self.query_one("#note", Composer).text.split())


CHECKING = "Before ⏎: units? significant figures? sign? did you answer exactly what was asked?"


class ValuePanel(Panel):
    """Typed answer (number with unit, expression, or short words), then confidence."""

    def __init__(self, n: int, kind: str, confidence: bool = True, checking: bool = False) -> None:
        super().__init__(classes="panel")
        self.n, self.kind, self.ask_conf, self.value, self.checking = n, kind, confidence, "", checking

    def compose(self) -> ComposeResult:
        tip = {"numeric": "value and unit, e.g. 19.6 m s-1 or 4.5e-3 mol dm-3",
               "expression": "an expression, e.g. 3*x**2 - 2*x", "short": "your answer in words"}.get(self.kind, "answer")
        yield _hint(f"Q{self.n}: type {tip}, then ⏎.  Type ? if you don't know.")
        if self.checking:
            yield Static("✓ " + CHECKING, classes="check")
        yield Composer(placeholder=tip, id="value")

    @on(Composer.Submitted, "#value")
    def _typed(self, event: "Composer.Submitted") -> None:
        v = " ".join(event.value.split())  # typed over several lines, it is still one answer
        if not v:
            return
        if v in ("?", "idk", "dunno"):
            self.finish({"entry": f"{self.n}?", "your": "I don't know"})
            return
        if self.kind in ("short", "expression"):
            v = v.replace(",", ";")  # a comma followed by a number would be read as a new answer
        self.value = v
        if not self.ask_conf:
            self.finish({"entry": f"{self.n} = {v}", "your": v})
            return
        event.composer.disabled = True
        self.mount(_hint("How sure are you? (1–4, Esc to edit your answer)"), Confidence())
        self.query_one(Confidence).focus()

    @on(Confidence.Back)
    def _back(self) -> None:
        for w in list(self.query(Confidence)) + [h for h in self.query(".hint") if "How sure" in str(h.render())]:
            w.remove()
        box = self.query_one("#value", Composer)
        box.disabled = False
        box.focus()

    @on(OptionList.OptionSelected, "#conf")
    def _conf(self, event: OptionList.OptionSelected) -> None:
        c = int(event.option.id or 3)
        self.finish({"entry": f"{self.n} = {self.value} ~{c}", "your": f"{self.value} ({CONF[c].lower()})"})


class LongPanel(Panel):
    """A long / structured answer typed in full. ctrl+s submits."""
    BINDINGS = [Binding("ctrl+s", "submit", "Submit answer")]

    def __init__(self, n: int, checking: bool = False) -> None:
        super().__init__(classes="panel tall")
        self.n, self.checking = n, checking

    def compose(self) -> ComposeResult:
        yield _hint(f"Q{self.n}: write your full working and answer (units!), then ctrl+s. "
                    "Working on paper or the iPad instead? Type 'done on paper', ctrl+s, and self-mark from the scheme.")
        if self.checking:
            yield Static("✓ " + CHECKING, classes="check")
        yield TextArea(id="long", soft_wrap=True, tab_behavior="indent")
        yield Button("Submit (ctrl+s)", id="submit", variant="primary")

    def action_submit(self) -> None:
        text = self.query_one("#long", TextArea).text.strip()
        if text:
            self.finish({"text": text})

    @on(Button.Pressed, "#submit")
    def _pressed(self) -> None:
        self.action_submit()


class TickList(SelectionList):
    """A SelectionList whose ticked boxes show ✓ and empty ones are blank: Textual draws an X in both, told apart by
    colour alone."""

    def render_line(self, y: int) -> Strip:
        strip = super().render_line(y)
        segments = list(strip)
        try:
            ticked = self.get_option_at_index(self.scroll_offset.y + y).value in self._selected
        except Exception:  # a line below the last option
            return strip
        if len(segments) > 1 and segments[1].text == "X":
            segments[1] = Segment("✓" if ticked else " ", segments[1].style)
        return Strip(segments, strip.cell_length)


class TickPanel(Panel):
    """Tick the points you earned / want (space to tick; ctrl+s, or ⏎ on the button, to confirm)."""
    BINDINGS = [Binding("ctrl+s", "confirm", show=False)]  # ⏎ in the list ticks, so the list needs a key of its own

    def __init__(self, prompt: str, items: list[tuple[str, str, bool]], buttons: list[tuple[str, str]]) -> None:
        super().__init__(classes="panel tall")
        self.prompt, self.items, self.buttons = prompt, items, buttons

    def compose(self) -> ComposeResult:
        yield _hint(self.prompt)
        yield TickList(*[Selection(escape(to_terminal(label)), value, on) for label, value, on in self.items],
                       id="ticks")
        yield Static(id="full")  # the highlighted point in full, when its row cuts it short
        with Horizontal(classes="buttons"):
            for bid, label in self.buttons:
                yield Button(label, id=bid, variant="primary" if bid == self.buttons[0][0] else "default")

    def on_resize(self) -> None:
        self._show_full()

    @on(SelectionList.SelectionHighlighted, "#ticks")
    def _show_full(self) -> None:
        """A row is one line, so a long mark point ends in "…": you would tick what you cannot read."""
        ticks, full = self.query_one("#ticks", SelectionList), self.query_one("#full", Static)
        i = ticks.highlighted
        text = to_terminal(self.items[i][0]) if i is not None and i < len(self.items) else ""
        room = ticks.scrollable_content_region.width - 4  # less the tick box before each point
        full.update(escape(text))
        full.display = bool(text) and room > 0 and cell_len(text) > room

    @on(Button.Pressed)
    def _pressed(self, event: Button.Pressed) -> None:
        self.finish({"button": event.button.id, "ticked": list(self.query_one("#ticks", SelectionList).selected)})

    def on_mount(self) -> None:
        super().on_mount()
        self.shown = time.monotonic()

    def action_confirm(self) -> None:
        if time.monotonic() - self.shown < 0.5:  # a second ctrl+s from submitting a long answer: mark it first
            return
        self.finish({"button": self.buttons[0][0], "ticked": list(self.query_one("#ticks", SelectionList).selected)})


class ChoosePanel(Panel):
    """Pick one of several labelled choices (no right answer), optionally add text."""

    def __init__(self, prompt: str, options: dict[str, str]) -> None:
        super().__init__(classes="panel")
        self.prompt, self.options = prompt, options

    def compose(self) -> ComposeResult:
        yield _hint(self.prompt)
        yield OptionList(*[Option(escape(v), id=k) for k, v in self.options.items()], id="choose")

    @on(OptionList.OptionSelected, "#choose")
    def _picked(self, event: OptionList.OptionSelected) -> None:
        self.finish({"choice": event.option.id})


class ContinuePanel(Panel):
    """After an explanation: continue, explain differently, or ask."""
    BINDINGS = [Binding("enter", "go", "Continue", show=False)]

    def __init__(self, prompt: str = "", buttons: list[tuple[str, str]] | None = None) -> None:
        super().__init__(classes="panel short")
        self.prompt = prompt
        self.buttons = buttons if buttons is not None else [("continue", "Continue ⏎"),
                                                            ("explain", "Explain differently (ctrl+r)"),
                                                            ("ask", "Ask the tutor (ctrl+t)")]

    def rows(self) -> list[list[tuple[str, str]]]:
        """The buttons in as few rows as the window's width allows: a narrow one gets a second row, never a button
        cut off at the edge."""
        rows, used, width = [[]], 0, self.app.size.width - 3  # the panel's own padding
        for button in self.buttons:
            w = max(16, len(button[1]) + 2) + 1  # a button: its label, a space each side (16 at least), 1 between
            if rows[-1] and used + w > width:
                rows.append([])
                used = 0
            rows[-1].append(button)
            used += w
        return rows

    def compose(self) -> ComposeResult:
        if self.prompt:
            yield _hint(self.prompt)
        rows = self.rows()
        self.shape = self._shape(rows)
        for row in rows:
            with Horizontal(classes="buttons"):
                for bid, label in row:
                    yield Button(label, id=bid, variant="primary" if bid == self.buttons[0][0] else "default",
                                 compact=self.shape[1])

    def _shape(self, rows) -> tuple:
        """How many buttons on each row, and whether they are one line high (a short window: the log keeps room)."""
        return [len(r) for r in rows], self.app.size.height < 30

    async def on_resize(self) -> None:
        if self._shape(self.rows()) != getattr(self, "shape", None):  # the window changed: lay the rows out again
            held = self.screen.focused.id if self.screen.focused in self.query(Button) else None
            await self.recompose()
            if held:
                self.query_one(f"#{held}", Button).focus()

    def action_go(self) -> None:
        if self.buttons:  # a waiting message has no buttons: ⏎ does nothing until it's replaced
            self.finish({"button": self.buttons[0][0]})

    @on(Button.Pressed)
    def _pressed(self, event: Button.Pressed) -> None:
        self.finish({"button": event.button.id})


class TextPanel(Panel):
    """Free text: your own words, a question for the tutor, a chat reply. Esc skips."""
    BINDINGS = [Binding("escape", "skip", "Skip")]

    def __init__(self, prompt: str, placeholder: str = "type here, then ⏎ (ctrl+j starts a new line)",
                 done_label: str | None = None) -> None:
        super().__init__(classes="panel")
        self.prompt, self.placeholder, self.done_label = prompt, placeholder, done_label

    def compose(self) -> ComposeResult:
        yield _hint(self.prompt)
        yield Composer(placeholder=self.placeholder, id="text")
        if self.done_label:
            yield Button(self.done_label, id="done")

    @on(Composer.Submitted, "#text")
    def _typed(self, event: Composer.Submitted) -> None:
        if event.value.strip():
            event.composer.text = ""
            self.finish({"text": event.value.strip()})

    @on(Button.Pressed, "#done")
    def _done(self) -> None:
        self.finish({"done": True})

    def action_skip(self) -> None:
        self.finish({"skip": True})


class WorkedPanel(Panel):
    """Worked example: predict each step (optional), ⏎ reveals it."""

    def __init__(self, total: int, start: int = 1) -> None:
        super().__init__(classes="panel")
        self.total, self.i = total, max(1, start)

    def compose(self) -> ComposeResult:
        yield _hint(self._label())
        yield Composer(placeholder="what would you do next? (optional) — ⏎ to reveal", id="guess")

    def _label(self) -> str:
        return f"Worked example: step {self.i} of {self.total}. Predict it, then ⏎ to reveal."

    @on(Composer.Submitted, "#guess")
    def _reveal(self, event: "Composer.Submitted") -> None:
        self.post_message(self.Done({"step": self.i, "guess": event.value.strip()}, self))
        event.composer.text = ""
        self.i += 1
        if self.i > self.total:
            self.finish({"done": True})
        else:
            self.query_one(".hint", Static).update(self._label())


class ReflectPanel(Panel):
    """One keypress: why did that answer go wrong? (Feeds your mistake profile.)"""
    CODES = {"SLIP": "Careless slip", "MISREAD": "Misread the question", "RECALL": "Didn't know / forgot",
             "PROCEDURE": "Wrong method", "CONCEPT": "Had the wrong idea"}
    REMARK = "REMARK"  # not a reason: "it was right", when the answer can go to the AI examiner
    BINDINGS = [Binding(str(i), f"pick({i})", show=False) for i in range(1, 7)] + [Binding("escape", "skip", "Skip")]

    def __init__(self, slip_likely: bool = False, remark: bool = False) -> None:
        super().__init__(classes="panel")
        self.slip_likely, self.remark = slip_likely, remark

    def compose(self) -> ComposeResult:
        yield _hint(f"Why did you miss it? (1–{6 if self.remark else 5}, or Esc to skip) — this tunes your profile "
                    "and advice."
                    + ("  It was quick on an idea you usually get: a slip?" if self.slip_likely else ""))
        options = [Option(f"{i}  {label}", id=code) for i, (code, label) in enumerate(self.CODES.items(), 1)]
        if self.remark:
            options.append(Option("6  I think my answer was right: ask the AI examiner to re-mark it", id=self.REMARK))
        yield OptionList(*options, id="reflect")

    def on_mount(self) -> None:
        ol = self.query_one("#reflect", OptionList)
        ol.highlighted = 0
        ol.focus()

    def action_pick(self, i: int) -> None:
        if i <= len(self.CODES):
            self.finish({"code": list(self.CODES)[i - 1]})
        elif self.remark:
            self.finish({"code": None, "remark": True})

    def action_skip(self) -> None:
        self.finish({"code": None})

    @on(OptionList.OptionSelected, "#reflect")
    def _picked(self, event: OptionList.OptionSelected) -> None:
        self.finish({"code": None, "remark": True} if event.option.id == self.REMARK else {"code": event.option.id})
