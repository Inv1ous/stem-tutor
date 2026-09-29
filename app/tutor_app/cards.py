"""Colour-coded transcript cards (Rich renderables)."""
from __future__ import annotations

from rich.console import Group
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text

from .texmath import to_terminal

C = {"tutor": "#89b4fa", "question": "#cba6f7", "you": "#9399b2", "good": "#a6e3a1", "bad": "#f38ba8",
     "hint": "#f9e2af", "ai": "#f5c2e7", "accent": "#ffd500", "dim": "#6c7086", "plan": "#94e2d5"}
CONF = {1: "Guess", 2: "Unsure", 3: "Fairly sure", 4: "Certain"}


def md(text: str) -> Markdown:
    return Markdown(to_terminal(text or ""), hyperlinks=False)


def card(kind: str, title: str, body: str = "", subtitle: str | None = None) -> Panel:
    return Panel(md(body) if body else Text(""), title=f"[b]{title}[/b]", title_align="left",
                 subtitle=subtitle, subtitle_align="right", border_style=C[kind], padding=(0, 1))


def question(view: dict) -> Panel:
    n, kind = view["n"], view.get("kind", "")
    marks = view.get("marks", 1)
    tags = [kind.upper(), f"{marks} mark{'s' if marks != 1 else ''}"]
    if view.get("unassisted"):
        tags.append("no hints")
    parts = [md(view.get("stem", ""))]
    if view.get("options") and kind != "mcq":  # MCQ options are listed in the answer panel below
        parts.append(Text("\n".join(f"  {k}  {to_terminal(v)}" for k, v in view["options"].items()), style="#cdd6f4"))
    if view.get("image"):
        parts.append(Text("◆ This question has a figure: see Now in Obsidian (press o).", style=C["hint"]))
    if view.get("source"):
        parts.append(Text(view["source"], style=C["dim"]))
    return Panel(Group(*parts), title=f"[b]Q{n}[/b] · {' · '.join(tags)}", title_align="left",
                 border_style=C["question"], padding=(0, 1))


def feedback(fb: dict, your: str) -> Panel:
    ok = fb.get("correct")
    dont_know = your.strip() in ("?", "I don't know")
    title = "I don't know — here's the answer" if dont_know else ("Correct ✓" if ok else "Not quite ✗")
    style = C["good"] if ok else (C["hint"] if dont_know else C["bad"])
    body = [f"**Your answer:** {your}  ", f"**Answer:** {fb.get('answer', '')}  "]
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
        body += ["", fb.get("examiner") or "Past-paper question: official answer only (press e for an AI explanation)."]
    if fb.get("hypercorrect"):
        body += ["", "⚑ You were confident but wrong: this is the best moment to fix the idea. Ask why (t)."]
    return Panel(md("\n".join(body)), title=f"[b]Q{fb['n']} — {title}[/b]", title_align="left", border_style=style,
                 padding=(0, 1))


def you(text: str) -> Panel:
    return Panel(Text(text), title="[b]You[/b]", title_align="right", border_style=C["you"], padding=(0, 1))


def ai(text: str, title: str = "Tutor (AI)") -> Panel:
    return Panel(md(text or "…"), title=f"[b]{title}[/b]", title_align="left", border_style=C["ai"], padding=(0, 1))


def note(text: str, kind: str = "dim") -> Text:
    return Text(text, style=C[kind])
