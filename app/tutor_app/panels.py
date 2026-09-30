"""Answer panels shown at the bottom of the session screen. Each posts `Panel.Done(data)` when finished."""
from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.message import Message
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
    BINDINGS = [Binding(str(i), f"pick({i})", show=False) for i in range(1, 5)]

    def __init__(self) -> None:
        super().__init__(*[Option(f"{i}  {CONF[i]}", id=str(i)) for i in (1, 2, 3, 4)], id="conf")

    def action_pick(self, i: int) -> None:
        self.highlighted = i - 1
        self.action_select()


class ChoicePanel(Panel):
    """Multiple choice: ↑↓ + ⏎ (or the letter key), then confidence 1–4. Always offers "I don't know"."""
    BINDINGS = [Binding(k, f"letter('{k.upper()}')", show=False) for k in "abcd"] + \
               [Binding("0", "letter('?')", show=False)]

    def __init__(self, n: int, options: dict | None, confidence: bool = True) -> None:
        super().__init__(classes="panel")
        self.n, self.options, self.ask_conf, self.choice = n, options or {k: "" for k in "ABCD"}, confidence, None

    def compose(self) -> ComposeResult:
        yield _hint(f"Q{self.n}: choose with ↑↓ and ⏎ (or press A–D).  0 = I don't know.  Full question: Now in Obsidian (o).")
        opts = [Option(f"[b]{k}[/b]  {to_terminal(v)}".rstrip(), id=k) for k, v in self.options.items()]
        yield OptionList(*opts, Option("[i]I don't know[/i]", id=DONT_KNOW), id="choices")
        yield Input(placeholder="✎ optional note: why you chose it (Tab to reach, then ⏎ on the list)", id="note",
                    compact=True)

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
        self.query_one("#choices").display = False
        self.mount(_hint(f"You chose {letter}. How sure are you? (1–4)"), Confidence())
        self.query_one(Confidence).focus()

    @on(OptionList.OptionSelected, "#conf")
    def _conf(self, event: OptionList.OptionSelected) -> None:
        c = int(event.option.id or 3)
        self.finish({"entry": f"{self.n}{self.choice}{c}", "your": f"{self.choice} ({CONF[c].lower()})", "note": self._note()})

    def _note(self) -> str:
        return self.query_one("#note", Input).value.strip()


class ValuePanel(Panel):
    """Typed answer (number with unit, expression, or short words), then confidence."""

    def __init__(self, n: int, kind: str, confidence: bool = True) -> None:
        super().__init__(classes="panel")
        self.n, self.kind, self.ask_conf, self.value = n, kind, confidence, ""

    def compose(self) -> ComposeResult:
        tip = {"numeric": "value and unit, e.g. 19.6 m s-1 or 4.5e-3 mol dm-3",
               "expression": "an expression, e.g. 3*x**2 - 2*x", "short": "your answer in words"}.get(self.kind, "answer")
        yield _hint(f"Q{self.n}: type {tip}, then ⏎.  Type ? if you don't know.")
        yield Input(placeholder=tip, id="value")

    @on(Input.Submitted, "#value")
    def _typed(self, event: Input.Submitted) -> None:
        v = event.value.strip()
        if not v:
            return
        if v in ("?", "idk", "dunno"):
            self.finish({"entry": f"{self.n}?", "your": "I don't know"})
            return
        self.value = v
        if not self.ask_conf:
            self.finish({"entry": f"{self.n} = {v}", "your": v})
            return
        event.input.disabled = True
        self.mount(_hint("How sure are you? (1–4)"), Confidence())
        self.query_one(Confidence).focus()

    @on(OptionList.OptionSelected, "#conf")
    def _conf(self, event: OptionList.OptionSelected) -> None:
        c = int(event.option.id or 3)
        self.finish({"entry": f"{self.n} = {self.value} ~{c}", "your": f"{self.value} ({CONF[c].lower()})"})


class LongPanel(Panel):
    """A long / structured answer typed in full. ctrl+s submits."""
    BINDINGS = [Binding("ctrl+s", "submit", "Submit answer")]

    def __init__(self, n: int) -> None:
        super().__init__(classes="panel tall")
        self.n = n

    def compose(self) -> ComposeResult:
        yield _hint(f"Q{self.n}: write your full working and answer (units!), then ctrl+s. "
                    "Working on paper or the iPad instead? Type 'done on paper', ctrl+s, and self-mark from the scheme.")
        yield TextArea(id="long", soft_wrap=True, tab_behavior="indent")
        yield Button("Submit (ctrl+s)", id="submit", variant="primary")

    def action_submit(self) -> None:
        text = self.query_one("#long", TextArea).text.strip()
        if text:
            self.finish({"text": text})

    @on(Button.Pressed, "#submit")
    def _pressed(self) -> None:
        self.action_submit()


class TickPanel(Panel):
    """Tick the points you earned / want (space to tick, ⏎ on the button to confirm)."""

    def __init__(self, prompt: str, items: list[tuple[str, str, bool]], buttons: list[tuple[str, str]]) -> None:
        super().__init__(classes="panel tall")
        self.prompt, self.items, self.buttons = prompt, items, buttons

    def compose(self) -> ComposeResult:
        yield _hint(self.prompt)
        yield SelectionList[str](*[Selection(to_terminal(label), value, on) for label, value, on in self.items], id="ticks")
        with Horizontal(classes="buttons"):
            for bid, label in self.buttons:
                yield Button(label, id=bid, variant="primary" if bid == self.buttons[0][0] else "default")

    @on(Button.Pressed)
    def _pressed(self, event: Button.Pressed) -> None:
        self.finish({"button": event.button.id, "ticked": list(self.query_one("#ticks", SelectionList).selected)})


class ChoosePanel(Panel):
    """Pick one of several labelled choices (no right answer), optionally add text."""

    def __init__(self, prompt: str, options: dict[str, str]) -> None:
        super().__init__(classes="panel")
        self.prompt, self.options = prompt, options

    def compose(self) -> ComposeResult:
        yield _hint(self.prompt)
        yield OptionList(*[Option(v, id=k) for k, v in self.options.items()], id="choose")

    @on(OptionList.OptionSelected, "#choose")
    def _picked(self, event: OptionList.OptionSelected) -> None:
        self.finish({"choice": event.option.id})


class ContinuePanel(Panel):
    """After an explanation: continue, explain differently, or ask."""
    BINDINGS = [Binding("enter", "go", "Continue", show=False)]

    def __init__(self, prompt: str = "", buttons: list[tuple[str, str]] | None = None) -> None:
        super().__init__(classes="panel short")
        self.prompt = prompt
        self.buttons = buttons or [("continue", "Continue ⏎"), ("explain", "Explain differently (e)"),
                                   ("ask", "Ask the tutor (t)")]

    def compose(self) -> ComposeResult:
        if self.prompt:
            yield _hint(self.prompt)
        with Horizontal(classes="buttons"):
            for bid, label in self.buttons:
                yield Button(label, id=bid, variant="primary" if bid == self.buttons[0][0] else "default")

    def action_go(self) -> None:
        self.finish({"button": self.buttons[0][0]})

    @on(Button.Pressed)
    def _pressed(self, event: Button.Pressed) -> None:
        self.finish({"button": event.button.id})


class TextPanel(Panel):
    """Free text: your own words, a question for the tutor, a chat reply. Esc skips."""
    BINDINGS = [Binding("escape", "skip", "Skip")]

    def __init__(self, prompt: str, placeholder: str = "type here, then ⏎", done_label: str | None = None) -> None:
        super().__init__(classes="panel")
        self.prompt, self.placeholder, self.done_label = prompt, placeholder, done_label

    def compose(self) -> ComposeResult:
        yield _hint(self.prompt)
        yield Input(placeholder=self.placeholder, id="text")
        if self.done_label:
            yield Button(self.done_label, id="done")

    @on(Input.Submitted, "#text")
    def _typed(self, event: Input.Submitted) -> None:
        if event.value.strip():
            self.finish({"text": event.value.strip()})

    @on(Button.Pressed, "#done")
    def _done(self) -> None:
        self.finish({"done": True})

    def action_skip(self) -> None:
        self.finish({"skip": True})


class WorkedPanel(Panel):
    """Worked example: predict each step (optional), ⏎ reveals it."""

    def __init__(self, total: int) -> None:
        super().__init__(classes="panel")
        self.total, self.i = total, 1

    def compose(self) -> ComposeResult:
        yield _hint(self._label())
        yield Input(placeholder="what would you do next? (optional) — ⏎ to reveal", id="guess")

    def _label(self) -> str:
        return f"Worked example: step {self.i} of {self.total}. Predict it, then ⏎ to reveal."

    @on(Input.Submitted, "#guess")
    def _reveal(self, event: Input.Submitted) -> None:
        self.post_message(self.Done({"step": self.i, "guess": event.value.strip()}, self))
        event.input.value = ""
        self.i += 1
        if self.i > self.total:
            self.finish({"done": True})
        else:
            self.query_one(".hint", Static).update(self._label())
