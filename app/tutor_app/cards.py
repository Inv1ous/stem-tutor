"""Colour-coded transcript cards (Rich renderables)."""
from __future__ import annotations

import re

from rich.console import Group
from rich.markdown import ListElement, Markdown
from rich.markup import escape
from rich.panel import Panel
from rich.text import Text
from rich.segment import Segment

from tutorlib.views import feedback_card, CONFIDENCE_LABELS

from .look import C
from .texmath import linearize, to_terminal
from .output_format import normalise_visual, terminal_visual

CONF = CONFIDENCE_LABELS


class _SpacedList(ListElement):
    """Rich collapses loose Markdown lists; AI steps keep a visible reading gap."""

    def __rich_console__(self, console, options):
        number = self.list_start or 1
        for index, item in enumerate(self.items):
            if index:
                yield Segment("\n")
            if self.list_type == "bullet_list_open":
                yield from item.render_bullet(console, options)
            else:
                yield from item.render_number(console, options, number + index, number + len(self.items))


class _AIMarkdown(Markdown):
    elements = {**Markdown.elements, "bullet_list_open": _SpacedList, "ordered_list_open": _SpacedList}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for block in self.parsed:
            for token in block.children or ():
                if token.type == "softbreak":
                    token.type = "hardbreak"


def md(text: str, *, ai_output: bool = False, partial: bool = False) -> Markdown:
    """A single line break stays a break (a table typed as lines is not one run-on line), except mid-sentence."""
    if ai_output:
        return _AIMarkdown(terminal_visual(text or "", partial=partial), hyperlinks=False)
    return Markdown(re.sub(r"(?<=\S)\n(?=[^\n])(?!(?<=[a-z,]\n)[a-z])", "  \n", to_terminal(text or "")),
                    hyperlinks=False)


def _narrow_question_tables(text: str, width: int) -> str:
    """Expand Markdown grids into labelled pairs so long numeric cells stay distinct in narrow cards."""
    def cells(row: str) -> list[str] | None:
        # Pipes split cells only outside code spans and when they are not escaped.
        row = row.strip()
        result, current, ticks, escaped = [], [], 0, False
        for char in row:
            if char == "|" and not escaped and ticks == 0:
                result.append("".join(current).strip())
                current = []
            else:
                current.append(char)
            if char == "`" and not escaped:
                ticks = 0 if ticks else 1
            escaped = char == "\\" and not escaped
            if char != "\\":
                escaped = False
        if current:
            result.append("".join(current).strip())
        if row.startswith("|") and result and result[0] == "":
            result.pop(0)
        if row.endswith("|") and result and result[-1] == "":
            result.pop()
        return result if len(result) > 1 else None

    lines = text.splitlines()
    out, i = [], 0
    while i < len(lines):
        if not lines[i].lstrip().startswith("|") or i + 2 >= len(lines):
            out.append(lines[i]); i += 1; continue
        header = cells(lines[i])
        separator = cells(lines[i + 1])
        if not header or not separator or not all(re.fullmatch(r":?-{3,}:?", cell.replace(" ", "")) for cell in separator):
            out.append(lines[i]); i += 1; continue
        rows, end = [], i + 2
        while end < len(lines) and (row := cells(lines[end])) is not None:
            if len(row) != len(header):
                break
            rows.append(row)
            end += 1
        if not rows:
            out.append(lines[i]); i += 1; continue
        block = lines[i:end]
        # Approximate the minimum grid width: cell contents plus padding and borders.
        if sum(max(len(label), *(len(row[col]) for row in rows)) + 2 for col, label in enumerate(header)) + 1 <= width:
            out.extend(block); i = end; continue
        for row in rows:
            out.extend(f"**{label}:** {value}" for label, value in zip(header, row))
        i = end
    return "\n\n".join(out) if out != lines else text


def literal(text: str) -> str:
    """Typed text shown as typed inside Markdown: 3*x**2 + x_1 keeps its stars and underscores."""
    return re.sub(r"([\\`*_$])", r"\\\1", to_terminal(text))


def framed(body, colour: str, title: str, **kw) -> Panel:
    """A transcript card. Classic draws the whole frame in the card's colour; Night and Day draw a quiet frame and
    give the title the card's colour."""
    if C["frame"]:
        return Panel(body, title=Text.from_markup(title, style=colour), border_style=C["frame"], padding=(0, 1), **kw)
    return Panel(body, title=title, border_style=colour, padding=(0, 1), **kw)


def _carries(panel, role: str, title: str, body: str, redraw=None):
    """The card keeps its words (role, title, Markdown) so the screen can put the same card on Now and in the log."""
    panel.card = (role, title, body)
    panel.redraw = redraw
    return panel


def _redraws(panel, redraw):
    """Keep rendering metadata without changing whether a card mirrors into the learner log."""
    panel.redraw = redraw
    return panel


def card(kind: str, title: str, body: str = "", subtitle: str | None = None, *, ai_output: bool = False) -> Panel:
    if subtitle and C["frame"]:  # Rich draws a plain subtitle in the frame's quiet grey: too faint to read
        subtitle = Text(subtitle, style=C["dim"])
    body = normalise_visual(body) if ai_output else body
    return _carries(framed(md(body, ai_output=ai_output) if body else Group(), C[kind], f"[b]{escape(to_terminal(title))}[/b]",
                           title_align="left", subtitle=subtitle, subtitle_align="right"), kind, title, body,
                     lambda: card(kind, title, body, subtitle, ai_output=ai_output))


def question(view: dict, *, ai_output: bool = False) -> Panel:
    n, kind = view["n"], view.get("kind", "")
    marks = view.get("marks", 1)
    tags = [kind.upper(), f"{marks} mark{'s' if marks != 1 else ''}"]
    if view.get("unassisted"):
        tags.append("no hints")
    if view.get("support"):
        tags.append("support below · alt+↓")
    stem = view.get("stem", "")
    # A 12-column grid cannot fit into the transcript card at 80 columns. Pair labels
    # and values vertically; other cards and wider screens retain the original Markdown.
    if len(stem.splitlines()) >= 3 and any(line.lstrip().startswith("|") for line in stem.splitlines()):
        stem = _narrow_question_tables(stem, 68)
    parts = [md(stem, ai_output=ai_output)]
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
    return _redraws(framed(Group(*parts), C["question"], f"[b]Q{n}[/b] · {escape(' · '.join(tags))}", title_align="left"),
                    lambda: question(view, ai_output=ai_output))


def feedback(fb: dict, your: str, *, ai_output: bool = False) -> Panel:
    role, title, body = feedback_card(fb, your, esc=literal)  # the wording Now and the lesson log use too
    return _redraws(framed(md(body, ai_output=ai_output), C[role], f"[b]{escape(title)}[/b]", title_align="left"),
                    lambda: feedback(fb, your, ai_output=ai_output))


def you(text: str, title: str = "You") -> Panel:
    return _carries(framed(Text(linearize(text)), C["you"], f"[b]{title}[/b]", title_align="right"), "you", title, text,
                    lambda: you(text, title))


def ai(text: str, title: str = "Tutor (AI)", subtitle: str | None = None, *, partial: bool = False) -> Panel:
    details = {"subtitle": Text(subtitle, style=C["muted"]), "subtitle_align": "right"} if subtitle else {}
    canonical = normalise_visual(text, partial=partial)
    return _carries(framed(md(canonical or "…", ai_output=True, partial=partial), C["ai"],
                           f"[b]{title}[/b]", title_align="left", **details), "ai", title, canonical,
                    lambda: ai(text, title, subtitle, partial=partial))


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
        self.widget.update(ai(text, partial=True))
        self.at = time.monotonic()
        return True


class Line(Text):
    """A quiet line between cards (Text itself cannot carry its words)."""


def note(text: str, kind: str = "dim") -> Text:
    return _carries(Line(linearize(text), style=C[kind]), "note", "", text, lambda: note(text, kind))


def redraw(renderable):
    """Rebuild a transcript renderable from its words after the live palette changes."""
    factory = getattr(renderable, "redraw", None)
    return factory() if factory else renderable
