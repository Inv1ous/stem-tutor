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
_ARG = r"(\{(?:[^{}]|\{[^{}]*\})*\}|\\?\w)"  # a {group} or one character
_BRACES = {"p": "()", "b": "()", "": "()", "v": "||", "V": "‖‖", "B": "\ue000\ue001", "cases": "\ue000\ue001"}


def _chem(body: str) -> str:
    """\\ce{...} (mhchem): element counts as subscripts, charges as superscripts, arrows."""
    body = body.replace("<=>", "⇌").replace("->", "→").replace("<-", "←")
    body = re.sub(r"\^\{?([0-9]*[+-])\}?", lambda m: m.group(1).translate(_SUP), body)
    body = re.sub(r"(?<=[A-Za-z)\]])(\d+)", lambda m: m.group(1).translate(_SUB), body)
    return body


def _math(expr: str) -> str:
    e = expr
    e = re.sub(r"\\ce\s*\{((?:[^{}]|\{[^{}]*\})*)\}", lambda m: _chem(m.group(1)), e)
    e = re.sub(r"(?:\{\}|(?<![\w})\]|'\\]))\^(\{[^{}]*\}|\w)(?:\s*_(\{[^{}]*\}|\w))?",  # nuclides: ¹⁴₆C, mass over number
               lambda m: "{}^{" + m.group(1).strip("{}") + "}" + ("{}_{" + m.group(2).strip("{}") + "}" if m.group(2) else ""), e)
    e = re.sub(r"\\(int|oint|sum|prod)\s*(?:_" + _ARG + r"\s*\^" + _ARG + r"|\^" + _ARG + r"\s*_" + _ARG + ")",  # ∫₀¹
               lambda m: rf"\{m.group(1)}{{}}_{m.group(2) or m.group(5)}{{}}^{m.group(3) or m.group(4)}", e)
    e = re.sub(r"\\binom\s*\{([^{}]*)\}\s*\{([^{}]*)\}", r"C(\1,\2)", e)
    e = re.sub(r"\\SI\s*\{([^{}]*)\}\s*\{((?:[^{}]|\{[^{}]*\})*)\}", lambda m: m.group(1) + r"\,\text{" + m.group(2) + "}", e)
    e = re.sub(r"\\(?:si|num)\s*\{((?:[^{}]|\{[^{}]*\})*)\}", r"\\text{\1}", e)
    e = re.sub(r"\\(mathrm|text|mathbf|mathit|mathsf)\s+([A-Za-z0-9])", r"\\\1{\2}", e)  # \mathrm K is \mathrm{K}
    for _ in range(3):  # keep text as a group, spaces kept: \times\text{IQR} is × IQR, not a command \timesIQR
        e = re.sub(_TEXT_CMDS + r"(\s*[\^_])?", lambda m: ("{}" + m.group(1).replace(" ", r"\,") + m.group(2) if m.group(2)
                                                          else "{" + m.group(1).replace(" ", r"\,") + "}"), e)  # Cu²⁺
    e = re.sub(r"\\begin\{([pbvVB]?matrix|cases)\}(.*?)\\end\{\1\}",  # (3; -4), |a b; c d|, {1, x>0; 0, x≤0}
               lambda m: _BRACES[m.group(1).replace("matrix", "")][0] + r";\,".join(
                   (r",\," if m.group(1) == "cases" else r"\,").join(c.strip() for c in r.split("&"))
                   for r in m.group(2).split("\\\\")) + _BRACES[m.group(1).replace("matrix", "")][1], e, flags=re.S)
    e = re.sub(r"\\(le|ge|ne)(?![A-Za-z])", r"\\\1q", e).replace(r"\ldots", r"\dots")  # names flatlatex lacks
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
            return _unmark(re.sub(r"(?<=\w)\[(\w+)\]", r"_\1", _CONV.convert(e)))  # subscripts without a glyph: v_y
        except Exception:
            pass
    return _unmark(re.sub(r"\\([A-Za-z]+)", r"\1", e).replace("{", "").replace("}", ""))


def _unmark(text: str) -> str:
    return text.replace("\ue000", "{").replace("\ue001", "}")  # literal braces kept out of LaTeX grouping


def to_terminal(text: str) -> str:
    """Convert every $...$ / $$...$$ / \\(...\\) / \\[...\\] span, and plain units such as m s^-2 elsewhere."""
    if not text:
        return ""
    text = re.sub(r"\$\$(.+?)\$\$|(?<!\\)\\\[(.+?)\\\]|(?<!\\)\\\((.+?)\\\)",
                  lambda m: _math(next(g for g in m.groups() if g is not None).strip()), text, flags=re.S)
    text = re.sub(r"(?<!\\)\$(?!\s)((?:\\\$|[^$])+?)(?<![\s\\])\$(\d?)",  # prices are not maths: '$5 and $6', '$5-$6'
                  lambda m: m.group(0) if m.group(2) and not re.search(r"[\\^_{=]", m.group(1))
                  else _math(m.group(1)) + m.group(2), text, flags=re.S)
    return pretty_units(text)


def pretty_units(text: str) -> str:
    """'m s^-2' → 'm s⁻²' for answers written in plain unit notation."""
    return re.sub(r"\^(?:\{(-?\d+)\}|(-?\d+)(?!\d|\.\d))", lambda m: (m.group(1) or m.group(2)).translate(_SUP),
                  text or "")  # m^{1/2} or m^2.5 stay as typed rather than half-converted
