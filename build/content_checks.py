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
          "counts|treats|assumes|forgets|mixes|swaps|doubles|halves|misses|shows|states|says|would|could|cannot|acts")
_LETTER = r"(?<![\w'’-])[A-D](?![\w'’-])"
LETTER_REF = re.compile("|".join([
    r"\b[Oo]ptions?\s+\(?[A-D]\b",                                             # option D, options B and C
    rf"\(\s*[A-D](?:\s*(?:,|and|or|&)\s*[A-D])*(?:\s+(?:is|are)\b[^)]*)?\)",  # (B), (C, D), (A, C, D are false)
    rf"{_LETTER}(?:\s*,\s*[A-D])*,?\s+(?:and|or)\s+[A-D](?![\w'’-])",         # B, C and D
    rf"(?:^|[.;:,!?]\s+|\b(?:and|but|while|whereas|so)\s+){_LETTER}\s+(?:{_VERBS})\b",  # ... and D ignores the charge
    rf"\b[Ii]n\s+[A-D](?:\s*,|\s+(?:the|it|this|that)\b)",                    # In A the 3d ...; in C, 4s ...
    r"\b(?:alternative|option|choice)\s+in\s+[A-D]\s+is\s+wrong\b",          # the tempting alternative in B is wrong
    r"\b(?:answer|key)\s+(?:is\s+)?\(?[A-D]\b(?![\w'’-])",                    # the answer is B
    rf"\b[Oo]nly\s+{_LETTER}",                                               # Only A has zero resultant (B-129)
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


# A sentence pointing the learner at a further picture ("a periodic-table reference is provided in the next image").
_FURTHER_IMAGE = re.compile(r"\b(?:next|second|following|other)\s+(?:source\s+)?(?:image|picture)s?\b", re.I)


def dangling_image_problems(item: dict) -> list[str]:
    """Question text that sends the learner to a further image the item does not carry (2026-11-07: 34 legacy 9701
    MCQs kept "an official periodic-table reference is provided in the next image" after that leaked data-sheet image
    was removed). A reference the learner owns, such as the Data Booklet, is named instead."""
    if not isinstance(item, dict):
        return []
    images = [name for name in dict.fromkeys([item.get('image')] + list(item.get('images') or [])) if name]
    if len(images) >= 2:
        return []
    out = []
    for field in ('stem', 'explanation'):
        text = item.get(field)
        if isinstance(text, str) and (m := _FURTHER_IMAGE.search(text)):
            out.append(f"{item.get('id')}: {field} points at a further image the item does not show ({len(images)} image): "
                       + text[max(0, m.start() - 60):m.end() + 20].replace("\n", " "))
    return out


# ---- stacked fractions and loose spaces that PDF extraction leaves in chemical and physical formulae ----
_SUBS, _SUPS = "₀₁₂₃₄₅₆₇₈₉", "⁰¹²³⁴⁵⁶⁷⁸⁹"
_FRACTION = re.compile(r"(?<![A-Za-z)\]₀-₉⁰¹²³⁴⁵⁶⁷⁸⁹])([₀-₉]+)\s?([⁰¹²³⁴⁵⁶⁷⁸⁹]+)(?![⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻])")
_VULGAR = {(1, 2): "½", (1, 3): "⅓", (2, 3): "⅔", (1, 4): "¼", (3, 4): "¾", (1, 5): "⅕", (1, 6): "⅙", (1, 8): "⅛"}


def _fraction(m: "re.Match[str]") -> str:
    den, num = int(m.group(1).translate(str.maketrans(_SUBS, "0123456789"))), int(m.group(2).translate(str.maketrans(_SUPS, "0123456789")))
    return _VULGAR.get((num, den), f"{num}/{den}")


def tidy_script_text(text: str) -> str:
    """Repair what PDF extraction does to a stacked fraction and to charges: `PbS + 1 ₂ ¹ O₂` (the numerator above the
    denominator, read in the wrong order, no slash) becomes `PbS + 1½O₂`, and `SO₄ ²⁻` loses its stray space."""
    text = text.replace("\x03", " ")  # a past-paper font's space came out as the control character 3 (Q-009)
    text = re.sub(r"(?<=\d) (?=[₀-₉]+\s?[⁰¹²³⁴⁵⁶⁷⁸⁹]+(?![⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻]))", "", text)  # a mixed number: 1 ½
    text = _FRACTION.sub(_fraction, text)
    # the numerator read first, then the denominator, with no superscript: `1 ₂ FL₁`, `– ¹ ₂ gT²` are halves
    text = re.sub(r"(?<![\w.⁰¹²³⁴⁵⁶⁷⁸⁹₀-₉])[1¹] ([₂-₉])(?![₀-₉⁰¹²³⁴⁵⁶⁷⁸⁹])",
                  lambda m: _VULGAR.get((1, int(m.group(1).translate(str.maketrans(_SUBS, "0123456789")))),
                                        m.group(0)), text)
    text = re.sub(r"(?<=[½⅓⅔¼¾⅕⅙⅛]) \. (?=\S)", "", text)  # ½ . λ: the fraction bar's dot -> ½λ
    text = re.sub(r"(?<=[½⅓⅔¼¾⅕⅙⅛]) (?=[A-Z(])", "", text)  # 1½ O₂ -> 1½O₂, as 2O₂ is written
    return re.sub(r"(?<=[₀-₉]) (?=[⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻])", "", text)  # SO₄ ²⁻ -> SO₄²⁻ ; m₁u₁ ² -> m₁u₁²


_FIGURES_ASKED = re.compile(r"(?:correct to|to|answer to|in)\s+(\d|one|two|three|four|five)\s+(?:s\.f\.|sf\b|significant fig)", re.I)
_EXACT_ASKED = re.compile(r"exact|fraction|simplest form|in terms of|surd", re.I)


def precision_problems(pack: dict) -> list[str]:
    """A numeric answer whose settings disagree with what its question asks: "to 3 s.f." with 4 figures also accepted
    (B-099), or an exact-only key on a question that neither asks for an exact form nor refuses the roundings it lists
    (B-141). The grader marks by the settings, so they must say what the question says."""
    out, words = [], {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5}
    for it in pack.get("items", []):
        ans = it.get("answer") if isinstance(it.get("answer"), dict) else None
        if it.get("kind") != "numeric" or not ans:
            continue
        allowed = ans.get("sf_ok") or ([ans["sf"]] if ans.get("sf") else None)
        if (m := _FIGURES_ASKED.search(it.get("stem") or "")) and allowed and allowed != [int(words.get(m[1].lower(), m[1]))]:
            out.append(f"{it.get('id')}: the question asks for {m[1]} s.f. but the answer accepts {allowed}")
        if ans.get("exact") and len(ans.get("sf_ok") or []) > 1 and not _EXACT_ASKED.search(it.get("stem") or ""):
            out.append(f"{it.get('id')}: exact-only, yet it lists roundings {ans['sf_ok']} and the question asks for no exact form")
    return out


def stacked_problems(pack: dict) -> list[str]:
    """Text that still has a stacked fraction or a stray space inside a formula (see `tidy_script_text`): rewrite it."""
    out = []
    for s in _strings(pack):
        if tidy_script_text(s) != s:
            out.append("a fraction or charge the PDF broke: " + s[:80].replace("\n", " "))
    return list(dict.fromkeys(out))[:6]


# These common species endings are unambiguous in copied Chemistry item text.
# This is a rejection gate, deliberately separate from extraction's automatic
# tidy_script_text: an official source must decide the exact replacement.
_CHEM_ELEMENTS = "He|Li|Be|Ne|Na|Mg|Al|Si|Cl|Ar|Ca|Ti|Cr|Mn|Fe|Co|Ni|Cu|Zn|Br|Ag|Sn|Ba|Hg|Pb|H|B|C|N|O|F|P|S|K|V|I"
_CHEM_SPACING = re.compile(
    rf"(?:{_CHEM_ELEMENTS})\s+(?=[₀-₉]|[{_SUPS}]*[⁺⁻])"
    rf"|Cl\s+(?=O[₀-₉⁺⁻])|(?<=[₀-₉)])\s+(?=[{_SUPS}]*[⁺⁻])")
_EXPLICIT_MATH = re.compile(r"\$\$.*?\$\$|\$[^$]*\$|\\\(.*?\\\)|\\\[.*?\\\]", re.S)


def chemical_spacing_problems(pack: dict) -> list[str]:
    """Require source review for detached elemental scripts/charges (B-048).

    Limit the rule to Chemistry display text; explicit maths, units, numeric
    lists and other courses retain their notation. Never repair source bytes.
    """
    if str(pack.get("spec")) != "9701":
        return []
    out = []
    for item in pack.get("items", []):
        display = {key: item.get(key) for key in ("stem", "options", "explanation", "hints", "scheme")}
        for text in _strings(display):
            plain = _EXPLICIT_MATH.sub("", text)
            if match := _CHEM_SPACING.search(plain):
                context = plain[max(0, match.start() - 20):match.end() + 30]
                out.append(f"{item.get('id', '?')}: chemical formula spacing requires source review: {context!r}")
    return list(dict.fromkeys(out))


def id_problems(pack: dict) -> list[str]:
    """Two items or two flashcards with one id: the learner's answers and Anki notes are kept by id, so the second would
    overwrite the first (B-090: two circuit-symbol cards shared `fc1` and one Anki GUID)."""
    out = []
    for field in ("items", "flashcards"):
        seen = set()
        for x in pack.get(field) or []:
            if x.get("id") in seen:
                out.append(f"two {field} share the id {x['id']}: give the newer one an unused id")
            seen.add(x.get("id"))
    return out
