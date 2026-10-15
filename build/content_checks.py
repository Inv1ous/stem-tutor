"""Content faults the pack validator does not see, found in audits: checked by the foundry and refine gates and by the tests.

- a generated MCQ is re-lettered when shown (packs.instantiate shuffles it), so its explanation and hints must name an
  option by its text, never by its letter;
- characters lost when text was copied from a PDF (the replacement character, a stray diaeresis for Δ): they read
  aloud as "replacement character" and show as boxes;
- text that still shows LaTeX (a backslash) after the terminal renderer has done its work.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

_VERBS = ("is|are|has|have|uses|adds|ignores|puts|holds|pairs|gives|fails|describes|differs|confuses|reverses|omits|"
          "counts|treats|assumes|forgets|mixes|swaps|doubles|halves|misses|shows|states|says|would|could|cannot")
_LETTER = r"(?<![\w'’-])[A-D](?![\w'’-])"
LETTER_REF = re.compile("|".join([
    r"\b[Oo]ptions?\s+\(?[A-D]\b",                                             # option D, options B and C
    rf"\(\s*[A-D](?:\s*(?:,|and|or|&)\s*[A-D])*(?:\s+(?:is|are)\b[^)]*)?\)",  # (B), (C, D), (A, C, D are false)
    rf"{_LETTER}(?:\s*,\s*[A-D])*,?\s+(?:and|or)\s+[A-D](?![\w'’-])",         # B, C and D
    rf"(?:^|[.;:,!?]\s+|\b(?:and|but|while|whereas|so)\s+){_LETTER}\s+(?:{_VERBS})\b",  # ... and D ignores the charge
    rf"\b[Ii]n\s+[A-D](?:\s*,|\s+(?:the|it|this|that)\b)",                    # In A the 3d ...; in C, 4s ...
    r"\b(?:answer|key)\s+(?:is\s+)?\(?[A-D]\b(?![\w'’-])",                    # the answer is B
]))


def letter_refs(text: str | None) -> list[str]:
    plain = re.sub(r"\$[^$]*\$", " ", text or "")  # $A$, $\mathrm{C}$ and the like are maths, not letters
    return [m.group(0) for m in LETTER_REF.finditer(plain)]


def shuffled(item: dict) -> bool:
    return item.get("kind") == "mcq" and bool(item.get("shuffle")) and (item.get("source") or {}).get("type") != "past"


def letter_problems(pack: dict) -> list[str]:
    """Explanations, hints and linked misconceptions of shuffled MCQs that name an option by its letter."""
    out, linked = [], set()
    for it in pack.get("items", []):
        if not shuffled(it):
            continue
        linked |= {v for v in (it.get("distractors") or {}).values() if isinstance(v, str)}
        for field, text in [("explanation", it.get("explanation"))] + [(f"hint {i + 1}", h) for i, h in enumerate(it.get("hints") or [])]:
            if refs := letter_refs(text):
                out.append(f"{it['id']} {field} names an option by its letter ({refs[0]!r}): a shuffled question is re-lettered, "
                           "name the option by what it says")
    for m in pack.get("misconceptions", []):
        if m.get("id") in linked:
            for field in ("statement", "refutation", "contrast"):
                if refs := letter_refs(m.get(field)):
                    out.append(f"misconception {m['id']} {field} names an option by its letter ({refs[0]!r})")
    return out


def _strings(x):
    stack = [x]
    while stack:
        y = stack.pop()
        if isinstance(y, str):
            yield y
        elif isinstance(y, dict):
            stack.extend(y.values())
        elif isinstance(y, list):
            stack.extend(y)


def latex_problems(pack: dict) -> list[str]:
    """Strings with maths that still show a backslash once rendered (an unsupported command): rewrite them."""
    app = str(Path(__file__).resolve().parents[1] / "app")
    if app not in sys.path:
        sys.path.insert(0, app)
    from tutor_app.texmath import to_terminal
    out = []
    for s in _strings(pack):
        if ("$" in s or "\\(" in s) and "\\" in to_terminal(s):
            out.append("maths that shows LaTeX after rendering: " + s[:90].replace("\n", " "))
    return list(dict.fromkeys(out))[:6]


DEBRIS = re.compile("[\ufffd\u00a8\u0080-\u009f\x00-\x08\x0b\x0c\x0e-\x1f]")


def debris_problems(pack: dict) -> list[str]:
    """Strings with a character the PDF copy lost (Δ became ¨, Σ became the replacement character): rewrite with the real
    symbol, as a dollar-maths `$\\Delta H$` or the Unicode letter."""
    out = []
    for s in _strings(pack):
        if m := DEBRIS.search(s):
            out.append(f"lost character {m.group(0)!r} (a PDF copy fault; write the real symbol): " + s[max(0, m.start() - 30):m.end() + 30].replace("\n", " "))
    return list(dict.fromkeys(out))[:6]
