"""Colour-coded transcript cards (Rich renderables)."""
from __future__ import annotations

import re

from rich.console import Group
from rich.markdown import Markdown
from rich.markup import escape
from rich.panel import Panel
from rich.text import Text

from .look import C
from .texmath import to_terminal

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


def card(kind: str, title: str, body: str = "", subtitle: str | None = None) -> Panel:
    if subtitle and C["frame"]:  # Rich draws a plain subtitle in the frame's quiet grey: too faint to read
        subtitle = Text(subtitle, style=C["dim"])
    return framed(md(body) if body else Group(), C[kind], f"[b]{escape(to_terminal(title))}[/b]", title_align="left",
                  subtitle=subtitle, subtitle_align="right")


def question(view: dict) -> Panel:
    n, kind = view["n"], view.get("kind", "")
    marks = view.get("marks", 1)
    tags = [kind.upper(), f"{marks} mark{'s' if marks != 1 else ''}"]
    if view.get("unassisted"):
        tags.append("no hints")
    parts = [md(view.get("stem", ""))]
    if view.get("options") and kind != "mcq":  # MCQ options are listed in the answer panel below
        parts.append(Text("\n".join(f"  {k}  {to_terminal(v)}" for k, v in view["options"].items()), style=C["text"]))
    if view.get("image"):
        parts.append(Text("◆ This question has a figure: see Now in Obsidian (press o).", style=C["hint"]))
    if view.get("source"):
        parts.append(Text(view["source"], style=C["dim"]))
    return framed(Group(*parts), C["question"], f"[b]Q{n}[/b] · {escape(' · '.join(tags))}", title_align="left")


def feedback(fb: dict, your: str) -> Panel:
    ok = fb.get("correct")
    dont_know = your.strip() in ("?", "I don't know")
    partial = fb.get("partial")
    title = ("I don't know — here's the answer" if dont_know else "Correct ✓" if ok else
             "Right value, but a mark lost ✗" if partial else "Not quite ✗")
    style = C["good"] if ok else (C["hint"] if dont_know or partial else C["bad"])
    body = [f"**Your answer:** {literal(your)}  ", f"**Answer:** {literal(str(fb.get('answer', '')))}  "]
    if fb.get("detail"):
        body.append(f"**Exam point:** {fb['detail']}  ")
    if fb.get("explanation"):
        body += ["", fb["explanation"]]
    mis = fb.get("misconception")
    if mis:
        body += ["", f"**Trap:** {mis.get('statement', '')}", mis.get("refutation", "")]
        if mis.get("contrast"):
            body.append(f"_Compare:_ {mis['contrast']}")
    if fb.get("official_key_only") and not fb.get("explanation"):
        body += ["", fb.get("examiner") or "Past-paper question: official answer only (the 'Explain this answer' "
                                             "button asks the AI tutor why)."]
    if fb.get("hypercorrect"):
        body += ["", "⚑ You were confident but wrong: this is the best moment to fix the idea. Ask why (t)."]
    if fb.get("calibration_note"):
        body += ["", f"◔ {fb['calibration_note']}"]
    if fb.get("relearn"):
        body += ["", "↻ This idea will come back in a few questions, so you can get it right before you finish."]
    return framed(md("\n".join(body)), style, f"[b]Q{fb['n']} — {title}[/b]", title_align="left")


def you(text: str) -> Panel:
    return framed(Text(text), C["you"], "[b]You[/b]", title_align="right")


def ai(text: str, title: str = "Tutor (AI)") -> Panel:
    return framed(md(text or "…"), C["ai"], f"[b]{title}[/b]", title_align="left")


def note(text: str, kind: str = "dim") -> Text:
    return Text(text, style=C[kind])
