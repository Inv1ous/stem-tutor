"""Colour-coded transcript cards (Rich renderables)."""
from __future__ import annotations

import re

from rich.console import Group
from rich.markdown import Markdown
from rich.markup import escape
from rich.panel import Panel
from rich.text import Text

from tutorlib.views import feedback_card

from .look import C
from .texmath import linearize, to_terminal

CONF = {1: "Guess", 2: "Unsure", 3: "Fairly sure", 4: "Certain"}


def md(text: str) -> Markdown:
    """A single line break stays a break (a table typed as lines is not one run-on line), except mid-sentence."""
    return Markdown(re.sub(r"(?<=\S)\n(?=[^\n])(?!(?<=[a-z,]\n)[a-z])", "  \n", to_terminal(text or "")),
                    hyperlinks=False)


def literal(text: str) -> str:
    """Typed text shown as typed inside Markdown: 3*x**2 + x_1 keeps its stars and underscores."""
    return re.sub(r"([\\`*_$])", r"\\\1", to_terminal(text))


def framed(body, colour: str, title: str, **kw) -> Panel:
    """A transcript card. Classic draws the whole frame in the card's colour; Night and Day draw a quiet frame and
    give the title the card's colour."""
    if C["frame"]:
        return Panel(body, title=Text.from_markup(title, style=colour), border_style=C["frame"], padding=(0, 1), **kw)
    return Panel(body, title=title, border_style=colour, padding=(0, 1), **kw)


def _carries(panel, role: str, title: str, body: str):
    """The card keeps its words (role, title, Markdown) so the screen can put the same card on Now and in the log."""
    panel.card = (role, title, body)
    return panel


def card(kind: str, title: str, body: str = "", subtitle: str | None = None) -> Panel:
    if subtitle and C["frame"]:  # Rich draws a plain subtitle in the frame's quiet grey: too faint to read
        subtitle = Text(subtitle, style=C["dim"])
    return _carries(framed(md(body) if body else Group(), C[kind], f"[b]{escape(to_terminal(title))}[/b]",
                           title_align="left", subtitle=subtitle, subtitle_align="right"), kind, title, body)


def question(view: dict) -> Panel:
    n, kind = view["n"], view.get("kind", "")
    marks = view.get("marks", 1)
    tags = [kind.upper(), f"{marks} mark{'s' if marks != 1 else ''}"]
    if view.get("unassisted"):
        tags.append("no hints")
    parts = [md(view.get("stem", ""))]
    if (bad := view.get("garbled")) and view.get("image"):  # some text did not copy from the paper; the picture is whole
        from tutorlib.views import unreadable
        parts = [md(unreadable(view.get("stem", "")))] if bad.get("stem") else parts
        parts.append(Text("◆ Part of this question did not copy from the paper" + (" (□)" if bad.get("stem") else "")
                          + ": the picture in Now is exact (press o).", style=C["hint"]))
    if view.get("options") and kind != "mcq":  # MCQ options are listed in the answer panel below
        parts.append(Text("\n".join(f"  {k}  {to_terminal(v)}" for k, v in view["options"].items()), style=C["text"]))
    if view.get("image") and not view.get("garbled"):
        parts.append(Text("◆ This question has a figure: see Now in Obsidian (press o).", style=C["hint"]))
    if view.get("source"):
        parts.append(Text(linearize(view["source"]), style=C["dim"]))
    return framed(Group(*parts), C["question"], f"[b]Q{n}[/b] · {escape(' · '.join(tags))}", title_align="left")


def feedback(fb: dict, your: str) -> Panel:
    role, title, body = feedback_card(fb, your, esc=literal)  # the wording Now and the lesson log use too
    return framed(md(body), C[role], f"[b]{escape(title)}[/b]", title_align="left")


def you(text: str, title: str = "You") -> Panel:
    return _carries(framed(Text(linearize(text)), C["you"], f"[b]{title}[/b]", title_align="right"), "you", title, text)


def ai(text: str, title: str = "Tutor (AI)") -> Panel:
    return _carries(framed(md(text or "…"), C["ai"], f"[b]{title}[/b]", title_align="left"), "ai", title, text)


class Live:
    """A streaming AI reply's card, redrawn at most every `every` seconds. Each redraw parses the whole reply again
    (Markdown and maths), so redrawing on every chunk made a long reply cost seconds of CPU (Q-004); the caller draws
    the finished reply in full once it ends."""

    def __init__(self, widget, every: float = 0.15):
        self.widget, self.every, self.at = widget, every, 0.0

    def update(self, text: str) -> bool:
        import time
        if time.monotonic() - self.at < self.every:
            return False
        self.widget.update(ai(text))
        self.at = time.monotonic()
        return True


class Line(Text):
    """A quiet line between cards (Text itself cannot carry its words)."""


def note(text: str, kind: str = "dim") -> Text:
    return _carries(Line(linearize(text), style=C[kind]), "note", "", text)
