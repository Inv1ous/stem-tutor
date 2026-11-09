"""How a past-paper question is shown: its pictures, in page order, and one line saying what to do.

A past-paper or source-verified question comes with a scan of the question as printed. The scan is the question: the
text the PDF copied out of it (stems, options, table cells, "(see the picture)") is never shown beside it, and a
structured question that asks for one part says which part ("Do (a)(iii)."), or which parts when several parts of the
same question belong to the topics chosen, or that the whole question is to be done. Pure functions; nothing here reads
learner state.
"""
from __future__ import annotations

import re
from pathlib import Path

# item["source"]["type"] values whose pictures show the whole question as printed
PRINTED = ("past", "source_verified")
_PAGE = re.compile(r"_p(\d{2})_(?:mcq|long|key|ref|ctx)_[0-9a-f]{12}\.")
_PART = re.compile(r"[A-Za-z0-9]+")


def shows_printed_question(inst: dict) -> bool:
    """The item's pictures ARE the question: a source-verified question's crops, or the pages of a printed structured
    question of which one part is asked. Nothing the PDF copied out of them is shown with them. (A past-paper MCQ whose
    picture is only its table or figure keeps its own sentences: see strip_figure_labels.)"""
    source = inst.get("source")
    if not ((inst.get("images") or inst.get("image")) and isinstance(source, dict)):
        return False
    return source.get("type") == "source_verified" or (
        source.get("type") == "past" and inst.get("kind") == "structured" and bool(source.get("part")))


def _label_line(line: str) -> bool:
    """A line copied out of a diagram or table, not a sentence: a word or three, no closing punctuation, no equation."""
    line = line.strip()
    words = [w for w in line.split() if re.search(r"\w", w)]
    return bool(line) and len(line) <= 24 and len(words) <= 3 and not re.search(r"[.?!:;,]$|[→⇌=]", line)


def strip_figure_labels(stem: str) -> str:
    """A past-paper stem without what the PDF copied out of its figure or table (three short label-like lines or more in
    a row: axis names, table cells). The picture shows them as they should be read; nothing replaces them in the text."""
    kept, run = [], []
    for line in (stem or "").split("\n"):
        if _label_line(line):
            run.append(line)
            continue
        kept.extend(run if len(run) < 3 else [])
        run.clear()
        kept.append(line)
    kept.extend(run if len(run) < 3 else [])
    return "\n".join(kept)


def page_order(refs: list[str]) -> list[str]:
    """Pictures in reading order: a multi-page question's pages (_p01_, _p02_ ...) by page, others as given."""
    pages = [_PAGE.search(Path(r).name) for r in refs]
    numbered = [(int(m[1]), r) for m, r in zip(pages, refs) if m]
    if len(refs) < 2 or len(numbered) != len(refs):
        return list(refs)
    return [r for _, r in sorted(numbered, key=lambda row: row[0])]


def part_label(part: str | None) -> str:
    """"a(iii)" -> "(a)(iii)"; "c" -> "(c)"; "" -> "". The label as a learner reads it on the paper."""
    return "".join(f"({token})" for token in _PART.findall(part or ""))


def _join(labels: list[str]) -> str:
    return labels[0] if len(labels) == 1 else ", ".join(labels[:-1]) + " and " + labels[-1]


def instruction(parts: list[str], *, whole: bool = False) -> str:
    """What to do in the printed question. `parts` are the labels asked for (in paper order); `whole` when they are
    every part there is."""
    if whole:
        return "Do the whole question."
    labels = [label for label in dict.fromkeys(part_label(p) for p in parts) if label]
    return f"Do {_join(labels)}." if labels else ""


def part_key(part: str | None) -> tuple:
    """Sort key putting parts in paper order: a, a(i), a(ii), b, b(i) ... (roman numerals by value)."""
    tokens = _PART.findall(part or "")
    return tuple((0, _roman(t)) if _is_roman(t) and i > 0 else (1, t) for i, t in enumerate(tokens))


_ROMAN = {"i": 1, "v": 5, "x": 10}


def _is_roman(token: str) -> bool:
    return bool(token) and set(token.lower()) <= set(_ROMAN)


def _roman(token: str) -> int:
    total, previous = 0, 0
    for char in reversed(token.lower()):
        value = _ROMAN[char]
        total += -value if value < previous else value
        previous = max(previous, value)
    return total
