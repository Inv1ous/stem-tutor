"""LaTeX → readable Unicode for the terminal (Obsidian shows the real typeset maths)."""
from __future__ import annotations

import re

try:
    import flatlatex
    _CONV = flatlatex.converter()
except Exception:  # pragma: no cover - fallback when the package is missing
    _CONV = None

_SUB = str.maketrans("0123456789+-=()", "₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎")
_SUP = str.maketrans("0123456789+-=()n", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ⁿ")
_TEXT_CMDS = r"\\(?:mathrm|text|textrm|mathit|mathbf|mathsf|operatorname|textbf|textit|mbox)\s*\{((?:[^{}]|\{[^{}]*\})*)\}"


def _chem(body: str) -> str:
    """\\ce{...} (mhchem): element counts as subscripts, charges as superscripts, arrows."""
    body = body.replace("<=>", "⇌").replace("->", "→").replace("<-", "←")
    body = re.sub(r"\^\{?([0-9]*[+-])\}?", lambda m: m.group(1).translate(_SUP), body)
    body = re.sub(r"(?<=[A-Za-z)\]])(\d+)", lambda m: m.group(1).translate(_SUB), body)
    return body


def _math(expr: str) -> str:
    e = expr
    e = re.sub(r"\\ce\s*\{((?:[^{}]|\{[^{}]*\})*)\}", lambda m: _chem(m.group(1)), e)
    for _ in range(3):
        e = re.sub(_TEXT_CMDS, r"\1", e)
    e = re.sub(r"\\[dt]frac", r"\\frac", e)
    e = re.sub(r"\\frac\s*(\d)\s*(\d)", r"\\frac{\1}{\2}", e)  # \tfrac12
    e = e.replace(r"\%", "%").replace(r"\;", r"\,").replace(r"\:", r"\,").replace(r"\!", "").replace("~", r"\,")
    e = e.replace(r"\left", "").replace(r"\right", "").replace(r"\quad", r"\,\,")
    e = e.replace(r"\degree", "°").replace(r"^\circ", "°").replace(r"^{\circ}", "°")
    e = re.sub(r"\\(?:to|rightarrow)(?![A-Za-z])", "→", e).replace(r"\Rightarrow", "⇒").replace(r"\leftarrow", "←")
    e = re.sub(r"\\(arcsin|arccos|arctan|sinh|cosh|tanh|sin|cos|tan|sec|csc|cot|log|ln|exp|lim|max|min)(?![A-Za-z])"
               r"(\^\{?-?\d+\}?)?", r"\\,\1\2\\,", e)  # function names as words, powers attached: sin²θ
    if _CONV is not None:
        try:
            return re.sub(r"(?<=\w)\[(\w+)\]", r"_\1", _CONV.convert(e))  # subscripts without a glyph: v_y
        except Exception:
            pass
    return re.sub(r"\\([A-Za-z]+)", r"\1", e).replace("{", "").replace("}", "")


def to_terminal(text: str) -> str:
    """Convert every $...$ / $$...$$ span; leave the rest of the text alone."""
    if not text:
        return ""
    text = re.sub(r"\$\$(.+?)\$\$", lambda m: _math(m.group(1).strip()), text, flags=re.S)
    return re.sub(r"(?<!\\)\$(.+?)(?<!\\)\$", lambda m: _math(m.group(1)), text, flags=re.S)


def pretty_units(text: str) -> str:
    """'m s^-2' → 'm s⁻²' for answers written in plain unit notation."""
    return re.sub(r"\^\{?(-?\d+)\}?", lambda m: m.group(1).translate(_SUP), text or "")
