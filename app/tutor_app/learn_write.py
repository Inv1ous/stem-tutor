"""A tutor-written explanation, in the program's one output format.

The learning AI asks to `write` about something the chapter material does not cover. The program then asks for the text
as the shared structured document (`chat_output`: paragraph / heading / bullet / step / equation blocks) so the layout,
numbering and maths delimiters come from the program, whichever model wrote it, and `normalise_visual` and the usual
card renderer draw it. Equation blocks that are plain algebra or arithmetic are checked with SymPy; one that is false
stops the whole explanation, and anything that cannot be checked is said to be unchecked.
"""
from __future__ import annotations

import json
import re

from .chat_output import DocumentDecoder, DocumentError, document_instructions, document_schema
from .learn_math import check_equality

SCHEMA = document_schema()


def prompt(question: str, topic: str, context: str, *, learner_context: str = '') -> str:
    return ("Write a short explanation or worked example for this A-level learner, in British English, short version "
            "first (a sentence or two), then the working, at most 12 blocks. Teach it from first principles using "
            "only what the learner has already seen, and never reveal the answer to a question they have not "
            "attempted. Write chemical formulas and units with Unicode subscripts and superscripts (CO₂, kJ mol⁻¹) or $\\mathrm{CO_2}$, never $_2$; put each calculation as its own equation block; an equation block holds algebra only, so write lists, tables and number lines as bullets or paragraphs.\n\n" + document_instructions()
            + "\n\nLearner's request: " + question[:1000] + "\nTopic to write about: " + topic[:200]
            + "\n\nLesson context:\n" + context[-3500:]
            + ("\n\nLearner goal and recent conversation:\n" + learner_context[:4000] if learner_context else ''))


def _plain(latex: str) -> str | None:
    """Simple LaTeX as the SymPy checker reads it, or None when it is not plain algebra or arithmetic."""
    e = latex.strip()
    for a, b in ((r"\times", "*"), (r"\cdot", "*"), (r"\left", ""), (r"\right", ""), (r"\,", " "), (r"\;", " "),
                 (r"\!", ""), (r"\ ", " ")):
        e = e.replace(a, b)
    for _ in range(4):  # \frac{a}{b}, innermost first
        e = re.sub(r"\\frac\{([^{}]*)\}\{([^{}]*)\}", r"((\1)/(\2))", e)
    e = re.sub(r"\^\{([^{}]*)\}", r"**(\1)", e)
    e = re.sub(r"\^([A-Za-z0-9])", r"**\1", e)
    e = e.replace("{", "(").replace("}", ")")
    e = re.sub(r"(?<=[\d)])\s*(?=[A-Za-z(])", "*", e)
    e = re.sub(r"(?<=[A-Za-z])\s*(?=\()", "*", e) if re.fullmatch(r"[A-Za-z]\s*\(.*", e) else e
    return None if "\\" in e or re.search(r"[<>≤≥≠]|\bto\b", e) else e


def _defines(name: str, value: str) -> bool:
    """`name` is a single symbol that does not occur in `value`: the line introduces it (S = n + (n+1), n = 2k)."""
    name = name.strip()
    return bool(re.fullmatch(r"[A-Za-z]", name)) and not re.search(rf"(?<![A-Za-z]){name}(?![A-Za-z])", value)


def lay_out(data: object) -> dict:
    """A finished document reply as {"text": canonical Markdown, "checked": [...], "unchecked": n}; DocumentError (or
    ValueError for a false equation) when it is invalid, incomplete or wrong."""
    decoder = DocumentDecoder()
    try:
        decoder.feed(json.dumps(data, ensure_ascii=False))
        text, _ = decoder.finish()
    except (TypeError, ValueError) as exc:
        raise DocumentError(str(exc)) from exc
    checked, unchecked = [], 0
    for block in decoder.document["blocks"]:
        if block["kind"] != "equation":
            continue
        parts = [p for p in re.split(r"(?<![<>!:])=(?!=)", block["text"])]
        if len(parts) < 2:
            continue
        sides = [_plain(p) for p in parts]
        if any(s is None or not s.strip() for s in sides):
            unchecked += 1
            continue
        for left, right, shown in zip(sides, sides[1:], zip(parts, parts[1:])):
            if _defines(left, right) or _defines(right, left):  # "S = n + (n+1)": a name given, not an identity to test
                unchecked += 1
                continue
            verdict = check_equality(left, right)
            if verdict is False:
                raise ValueError(f"the equation {shown[0].strip()} = {shown[1].strip()} is not true")
            if verdict is True:
                checked.append(f"{shown[0].strip()} = {shown[1].strip()}")
            else:
                unchecked += 1
    return {"text": text, "checked": checked, "unchecked": unchecked}
