"""LaTeX → readable Unicode for the terminal (Obsidian shows the real typeset maths)."""
from __future__ import annotations

import functools
import re
import unicodedata

BOLD = True  # \mathbf{F} as 𝐅 (Unicode maths bold); False shows a plain F

_SUB = str.maketrans("0123456789+-=()", "₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎")
_SUP = str.maketrans("0123456789+-=()n", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ⁿ")
_TEXT_CMDS = (r"\\(?:mathrm|text|textrm|mathit|mathsf|operatorname|textbf|textit|mbox" + ("" if BOLD else "|mathbf")
              + r")\s*\{((?:[^{}]|\{[^{}]*\})*)\}")
_GROUP = r"(?:[^{}]|\{(?:[^{}]|\{[^{}]*\})*\})*"  # the inside of a {group}, up to two levels of braces deep
_ARG = (r"(\{(?:[^{}]|\{[^{}]*\})*\}|\\[dt]?frac\s*(?:\{[^{}]*\}|\w)\s*(?:\{[^{}]*\}|\w)|\\sqrt\s*(?:\{[^{}]*\}|\w)"
        r"|\\[A-Za-z]+|\\?\w)")  # a {group}, \frac{π}{2} or \sqrt{2}, a command (\pi), or one character
_BRACES = {"p": "()", "b": "()", "": "()", "v": "||", "V": "‖‖", "B": "\ue000\ue001", "cases": "\ue000\ue001"}
_FUNCS = "arcsin|arccos|arctan|sinh|cosh|tanh|sin|cos|tan|sec|csc|cot|log|ln|exp|lim|max|min|det|gcd|deg|arg"
# markers that pass through flatlatex untouched: literal braces, a hyphen that is no minus (a word in \text{}, a
# chemical bond), \quad, a double bond, and the two sides of a function name (a space only where one reads)
_LBRACE, _RBRACE, _HYPHEN, _QUAD, _FN_END, _BOND2, _FN_START = (chr(0xE000 + i) for i in range(7))
_FRAC_L, _FRAC_R = "\ue007", "\ue008"  # around a/b: bracketed when a factor follows, (b/2)x not b/2x
_VEC_R, _VEC_L = "\ue009", "\ue00a"  # the arrow of a vector named by two points, →AB: never spaced like a relation
_XL, _XR = "", ""  # around the condition written over a reaction arrow: A —heat→ B
_SUB_L, _SUB_R = "", ""  # around a subscript with no Unicode form (Kc, v_y): a space if a letter follows
_CHARGE_END = r"(?=$|[\s),;]|\((?:aq|g|l|s)\))"  # after a charge: the end, a space, or a state symbol: Na⁺(g)
# leftovers of PDF extraction in a few packs: a maths font's ≤ ≥, and big-bracket pieces that lost their place
_LEFTOVERS = {0xF084: "≤", 0xF085: "≥", 0x00AD: None, **{c: None for c in range(0xF8E5, 0xF8FF)}}
# commands flatlatex lacks (or draws with a glyph that can turn into an emoji: its ↔ is U+2194)
_SYMBOLS = {r"\iff": "⇔", r"\implies": "⇒", r"\impliedby": "⇐", r"\prime": "′", r"\longrightarrow": "→",
            r"\longleftarrow": "←", r"\Longrightarrow": "⇒", r"\Longleftarrow": "⇐", r"\Longleftrightarrow": "⇔",
            r"\leftrightarrow": "⟷", r"\longleftrightarrow": "⟷", r"\langle": "⟨", r"\rangle": "⟩", r"\lceil": "⌈",
            r"\rceil": "⌉", r"\lfloor": "⌊", r"\rfloor": "⌋", r"\triangle": "△", r"\varnothing": "∅",
            r"\leqslant": "≤", r"\geqslant": "≥", r"\land": "∧", r"\lor": "∨", r"\imath": "ı", r"\jmath": "ȷ",
            r"\dagger": "†", r"\ddagger": "‡", r"\top": "⊤", r"\square": "□", r"\Box": "□", r"\checkmark": "✓",
            r"\bmod": " mod ", r"\textmu": "μ", r"\upmu": "μ", r"\micro": "μ", r"\ohm": "Ω", r"\textdegree": "°",
            r"\perthousand": "‰", r"\textperthousand": "‰", r"\AA": "Å", r"\angstrom": "Å", r"\cdotp": "·"}

try:
    import flatlatex
    from flatlatex import data as _data
    from flatlatex import latexfuntypes as _funtypes
except Exception:  # pragma: no cover - fallback when the package is missing
    flatlatex = None


_CE_ARROWS = {"<=>>": "⇌", "<<=>": "⇌", "<=>": "⇌", "<->": "⟷", "->": "→", "<-": "←"}
_X_ARROWS = {"rightarrow": "→", "longrightarrow": "→", "to": "→", "leftarrow": "←", "longleftarrow": "←",
             "rightleftharpoons": "⇌", "Rightarrow": "⇒", "Leftarrow": "⇐", "leftrightarrow": "⟷"}


def _labelled(arrow: str, above: str | None, below: str | None, chem: bool = False) -> str:
    """An arrow with a condition over (and under) it, in one line with the condition inside the arrow: A —heat→ B."""
    label = r",\,".join(x.strip() for x in (above, below) if x and x.strip())
    if not label:
        return arrow
    if chem:  # spaces in mhchem are kept, except inside 150 °C
        label = re.sub(r"\s*\^\s*(?:\{\s*\\circ\s*\}|\\circ(?![A-Za-z]))\s*", r"\\,°", label).replace(" ", r"\,")
    return _XL + "{" + label + "}" + _XR + arrow


def _no_label(expr: str) -> str:
    """The expression without its plain-text subscripts: what decides whether it needs brackets."""
    return re.sub(_SUB_L + ".*?" + _SUB_R, "", expr)


def _chem(body: str) -> str:
    """\\ce{...} (mhchem): element counts as subscripts, charges as superscripts, bonds and arrows."""
    body = re.sub(r"(<=>>|<<=>|<=>|<->|->|<-)\s*\[([^\]]*)\](?:\s*\[([^\]]*)\])?",  # ->[heat], ->[Ni][150 °C]
                  lambda m: _labelled(_CE_ARROWS[m.group(1)], m.group(2), m.group(3), chem=True), body)
    for ascii_arrow, arrow in _CE_ARROWS.items():
        body = body.replace(ascii_arrow, arrow)
    body = re.sub(r"\^\{?([0-9]*[+-])\}?", lambda m: m.group(1).translate(_SUP), body)  # Cu^2+, SO4^{2-}
    body = re.sub(r"(?<![A-Za-z)\]])([A-Z][a-z]?)(\d+)([+-])" + _CHARGE_END,  # Fe3+: a lone element's charge
                  lambda m: m.group(1) + (m.group(2) + m.group(3)).translate(_SUP), body)
    body = re.sub(r"(?<=\])(\d*[+-])" + _CHARGE_END, lambda m: m.group(1).translate(_SUP), body)  # [Fe(CN)6]3-
    body = re.sub(r"(?<=[A-Za-z\d)])([+-])" + _CHARGE_END, lambda m: m.group(1).translate(_SUP), body)  # H+, OH-
    body = re.sub(r"(?<=[\w)\]])-(?=[A-Z(\[])", _HYPHEN, body)  # a bond: CH3-CH3
    body = re.sub(r"(?<=[\w)\]])=(?=[A-Z(\[])", _BOND2, body)  # CH2=CH2
    body = re.sub(r"([A-Za-z)\]]\d*)[.*](?=\d*[A-Z(])", "\\1·", body)  # CuSO4.5H2O
    body = re.sub(r"(?<=[A-Za-z)\]])(\d+)", lambda m: m.group(1).translate(_SUB), body)
    return body


if flatlatex is not None:
    _SUBSCRIPT = {**_data.subscript, "h": "ₕ", "k": "ₖ", "l": "ₗ", "m": "ₘ", "n": "ₙ", "p": "ₚ", "s": "ₛ", "t": "ₜ"}
    _MODS = set(_SUBSCRIPT.values()) | set(_data.superscript.values()) | set("′″⦵")

    def _simple(expr: str) -> bool:
        """One base character with only sub/superscripts or accents after it: x, x₁, F⃗, v_y (no brackets needed)."""
        return sum(1 for ch in _no_label(expr) if not unicodedata.combining(ch) and ch not in _MODS) <= 1

    def _atom(expr: str) -> bool:
        """What can stand below a fraction line without brackets: x, r², 10, 2.5, dx, Δt, √3, R_T."""
        base = _no_label(expr)
        while base and (unicodedata.combining(base[-1]) or base[-1] in _MODS):
            base = base[:-1]
        if len(base) > 1 and base[0] in "dΔδ∂√∛∜":
            base = base[1:]
        return len(base) == 1 or bool(re.fullmatch(r"\d+(?:\.\d+)?", base))

    def _radicand(expr: str) -> str:
        return expr if _simple(expr) or re.fullmatch(r"\d+(?:\.\d+)?", expr) else f"({expr})"  # √3, √32, √(2gh)

    class _Converter(flatlatex.converter):
        """flatlatex with printed-maths habits: x₁² not (x₁)², dy/dx and 1/(2a), more subscript letters, ∛ ⇔ ′."""

        def __init__(self):
            super().__init__()
            cmds = self._converter__cmds
            for name, symbol in {**_SYMBOLS, r"\colon": ": "}.items():
                cmds[name] = _funtypes.latexfun(lambda _, s=symbol: s, 0)
            cmds[r"\cbrt"] = _funtypes.latexfun(lambda x: "∛" + _radicand(x[0]), 1)
            cmds[r"\qdrt"] = _funtypes.latexfun(lambda x: "∜" + _radicand(x[0]), 1)
            cmds[r"\pmod"] = _funtypes.latexfun(lambda x: f" (mod {x[0]})", 1)
            for name, mark in {r"\widehat": "\u0302", r"\widetilde": "\u0303", r"\mathring": "\u030a", r"\breve": "\u0306",
                               r"\cancel": "\u0336", r"\bcancel": "\u0336", r"\xcancel": "\u0336", r"\sout": "\u0336"}.items():
                cmds[name] = _funtypes.latexfun(lambda x, m=mark: self._converter__latexfun_comb((m, ""), x), 1)

        def _converter__is_complex_expr(self, expr):
            return not _simple(expr)

        def _converter__exponent(self, a, b):
            a = a if _simple(a) else f"({a})"  # x₁²
            if all(ch in _data.superscript for ch in b):
                return a + "".join(_data.superscript[ch] for ch in b)
            many = sum(1 for ch in b if not unicodedata.combining(ch)) > 1
            return a + "^" + (f"({b})" if many else b)  # e^(x²), not e^x² which reads as (eˣ)²

        def _converter__indexed(self, a, b):
            a = a if _simple(a) else f"({a})"
            if b == "1/2":
                return a + "½"  # t½
            if b and all(ch in _SUBSCRIPT for ch in b):
                return a + "".join(_SUBSCRIPT[ch] for ch in b)
            if b == "∞" or re.fullmatch(r"\w+", b):  # no Unicode form: a short label on a capital joins (Kc, Ecell,
                # ΔHf, S∞); same-case, capital, coordinate and long subscripts keep the _ (v_y, N_A, F_y, S_products)
                base = next((c for c in reversed(_no_label(a)) if not unicodedata.combining(c) and c not in _MODS), "")
                joined = b == "∞" or (re.fullmatch(r"[a-w]{1,5}", b) and base.isupper()
                                      and "GREEK" not in unicodedata.name(base, ""))
                return a + _SUB_L + ("" if joined else "_") + b + _SUB_R
            return a + f"[{b}]"  # lim[x→0]

        def _converter__latexfun_frac(self, inputs):
            a, b = inputs
            if (a, b) in _data.known_fracts:
                return _data.known_fracts[(a, b)]
            if a.isdigit() and b.isdigit():
                return a.translate(_SUP) + "⁄" + b.translate(_SUB)  # ²⁄₇
            if re.search(r"[\s,/+\-−=<>≤≥≠≈±∓×÷·→" + _FN_START + _FN_END + "]", a):
                a = f"({a})"  # (a+b)/c, but dy/dx and mv²/r
            if not _atom(b):
                b = f"({b})"  # 1/(2a), but x/2, dy/dx and Δs/Δt
            return f"{_FRAC_L}{a}/{b}{_FRAC_R}"

        def _converter__latexfun_comb(self, comb, inputs):
            """An accent: combined with one letter (x̄, a⃗, 𝐧̂, z̄₁); over several, →AB for a vector between two points,
            ∠ABC for an angle, and a line or mark on every character otherwise (A̅B̅ joins into one overline)."""
            mark, expr = comb[0], inputs[0]
            if not expr.strip():
                return ""
            if _simple(expr):
                base = next((i for i, ch in enumerate(expr) if not unicodedata.combining(ch) and ch not in _MODS), 0)
                return expr[:base + 1] + mark + expr[base + 1:]
            if mark in "\u20d7\u20d6":
                return (_VEC_R if mark == "\u20d7" else _VEC_L) + expr
            if mark == "\u0302" and re.fullmatch(r"[A-Z]{3}", expr):
                return "∠" + expr
            mark = "\u0305" if mark == "\u0304" else mark  # a macron per letter would leave gaps
            return "".join(ch + ("" if unicodedata.combining(ch) else mark) for ch in expr)

        def _converter__latexfun_sqrt(self, inputs):
            return "√" + _radicand(inputs[0])

    _CONV = _Converter()
else:  # pragma: no cover
    _CONV = None


@functools.lru_cache(maxsize=4096)
def _math(expr: str) -> str:
    e = expr
    e = re.sub(r"\\ce\s*\{((?:[^{}]|\{[^{}]*\})*)\}", lambda m: _chem(m.group(1)), e)
    e = re.sub(r"\\(?:(?:display|text|script|scriptscript)style|(?:no)?limits|[bB]igg?[lrm]?)(?![A-Za-z])\s*", "",
               e)  # sizes and styles mean nothing in a terminal
    e = re.sub(r"\\[lr]?vert(?![A-Za-z])", "|", e)
    e = re.sub(r"\\[lr]?Vert(?![A-Za-z])", "‖", e)
    e = re.sub(r"(?:\{\}|(?<![\w})\]|'\\]))\^(\{[^{}]*\}|\w)(?:\s*_(\{[^{}]*\}|\w))?",  # nuclides: ¹⁴₆C, mass over number
               lambda m: "{}^{" + m.group(1).strip("{}") + "}" + ("{}_{" + m.group(2).strip("{}") + "}" if m.group(2) else ""), e)
    e = re.sub(r"\\(int|oint|sum|prod)(?![A-Za-z])((?:\s*[_^]\s*" + _ARG + ")*)", _big_operator, e)  # ∫₀¹ x² dx
    e = re.sub(r"\\x(" + "|".join(_X_ARROWS) + r")(?![A-Za-z])\s*(?:\[((?:[^\[\]{}]|\{[^{}]*\})*)\])?\s*\{(" + _GROUP
               + r")\}", lambda m: _labelled(_X_ARROWS[m.group(1)], m.group(3), m.group(2)), e)  # \xrightarrow[b]{a}
    e = re.sub(r"\\(?:overset|stackrel)\s*\{(" + _GROUP + r")\}\s*\{\s*(?:\\(" + "|".join(_X_ARROWS)
               + r")(?![A-Za-z])|->)\s*\}", lambda m: _labelled(_X_ARROWS.get(m.group(2), "→"), m.group(1), None), e)
    e = re.sub(r"\\(over|under)set\s*\{(" + _GROUP + r")\}\s*\{(" + _GROUP + r")\}",  # anything else: bᵃ, maxₓ
               lambda m: (m.group(3).strip() if re.fullmatch(r"\s*\\[A-Za-z]+\s*", m.group(3)) else "{" + m.group(3) + "}")
               + ("^" if m.group(1) == "over" else "_") + "{" + m.group(2) + "}", e)
    e = re.sub(r"\\binom\s*\{([^{}]*)\}\s*\{([^{}]*)\}", r"C(\1,\2)", e)
    e = re.sub(r"\\SI\s*\{([^{}]*)\}\s*\{((?:[^{}]|\{[^{}]*\})*)\}", lambda m: m.group(1) + r"\,\text{" + m.group(2) + "}", e)
    e = re.sub(r"\\(?:si|num)\s*\{((?:[^{}]|\{[^{}]*\})*)\}", r"\\text{\1}", e)
    e = re.sub(r"\\(?:boldsymbol|bm)(?![A-Za-z])", r"\\mathbf", e)
    e = re.sub(r"\\(mathrm|text|mathbf|mathit|mathsf)\s+([A-Za-z0-9])", r"\\\1{\2}", e)  # \mathrm K is \mathrm{K}
    for _ in range(3):  # keep text as a group, spaces kept: \times\text{IQR} is × IQR, not a command \timesIQR
        e = re.sub(_TEXT_CMDS + r"(\s*[\^_])?", lambda m: ("{}" + _words(m.group(1)) + m.group(2) if m.group(2)
                                                          else "{" + _words(m.group(1)) + "}"), e)  # Cu²⁺
    e = re.sub(r"\\begin\{([pbvVB]?matrix|cases)\}(.*?)\\end\{\1\}",  # (3; -4), |a b; c d|, {1, x>0; 0, x≤0}
               lambda m: _BRACES[m.group(1).replace("matrix", "")][0] + r";\,".join(
                   (r",\," if m.group(1) == "cases" else _QUAD).join(c.strip() for c in r.split("&"))
                   for r in m.group(2).split("\\\\")) + _BRACES[m.group(1).replace("matrix", "")][1], e, flags=re.S)
    e = re.sub(r"\\(le|ge|ne)(?![A-Za-z])", r"\\\1q", e).replace(r"\ldots", r"\dots")  # names flatlatex lacks
    e = re.sub(r"\\[dt]frac", r"\\frac", e)
    e = re.sub(r"\\frac\s*(\d)\s*(\d)", r"\\frac{\1}{\2}", e)  # \tfrac12
    e = e.replace(r"\%", "%").replace(r"\;", r"\,").replace(r"\:", r"\,").replace(r"\!", "").replace("~", r"\,")
    e = re.sub(r"\\(?:left|right)(?![A-Za-z])\s*\.?", "", e)  # \left( … \right), not \leftarrow or \rightleftharpoons
    e = re.sub(r"\\(?:\{|lbrace(?![A-Za-z]))", _LBRACE, e)
    e = re.sub(r"\\(?:\}|rbrace(?![A-Za-z]))", _RBRACE, e)
    e = re.sub(r"\\(q?)quad(?![A-Za-z])", lambda m: _QUAD * (2 if m.group(1) else 1), e)
    e = e.replace(r"\degree", "°").replace(r"^\circ", "°").replace(r"^{\circ}", "°")
    e = re.sub(r"\\(?:to|rightarrow)(?![A-Za-z])", "→", e).replace(r"\Rightarrow", "⇒")
    e = re.sub(r"\\leftarrow(?![A-Za-z])", "←", e)
    e = re.sub(r"\^\s*\{?\s*\\ominus\s*\}?\s*(_\s*(?:\{" + _GROUP + r"\}|\w))", r"\1^\\ominus", e)  # E^⊖_{cell}: subscript first
    e = re.sub(r"\^\s*(?:\{\s*\\ominus\s*\}|\\ominus(?![A-Za-z]))", "⦵", e)  # ΔH⦵, the standard-state sign
    e = re.sub(r"\\sqrt\s*\[\s*([34])\s*\]", lambda m: r"\cbrt" if m.group(1) == "3" else r"\qdrt", e)
    e = re.sub(r"\\sqrt\s*\[([^\]]*)\]", r"{}^{\1}\\sqrt", e)  # ⁿ√x
    e = re.sub(r"(?<=[A-Za-z)])''", "″", e)
    e = re.sub(r"(?<=[A-Za-z)])'", "′", e)
    e = re.sub(r"\\(" + _FUNCS + r")(?![A-Za-z])((?:\s*[\^_]\s*(?:\{[^{}]*\}|-?\d+|\w))*)",  # sin²θ, log₁₀, lim[x→0]
               lambda m: _FN_START + m.group(1) + re.sub(r"\s*([\^_])\s*", r"\1", m.group(2)).strip() + _FN_END, e)
    if _CONV is not None:
        try:
            return _tidy(_CONV.convert(e))
        except Exception:
            pass
    return _tidy(re.sub(r"\\([A-Za-z]+)", r"\1", e).replace("{", "").replace("}", ""))


def _big_operator(m: re.Match) -> str:
    """∫ ∑ ∏ with their limits (below first, then above: ∫₀¹), and the small space a printed page leaves after them."""
    found = re.findall(r"([_^])\s*" + _ARG, m.group(2))
    limits = {side: arg if arg.startswith("{") else "{" + arg + "}" for side, arg in found}
    below, above = ("{}_" + limits["_"] if "_" in limits else ""), ("{}^" + limits["^"] if "^" in limits else "")
    return f"\\{m.group(1)}{below}{above}" + r"\,"


def _words(text: str) -> str:
    """A \\text{} group: spaces kept, a hyphen in a word stays a hyphen (but-2-ene, not a minus), an apostrophe stays
    one (Hooke’s, not a prime)."""
    return re.sub(r"(?<=[A-Za-z0-9)])(?<![\d.][eE])-(?=[A-Za-z0-9(])", _HYPHEN,  # 1.6e−19 keeps its minus
                  re.sub(r"(\\[A-Za-z]+) (?=\S)", r"\1{}", text).replace(" ", r"\,")).replace("'", "’")  # \textmu m


_REL = set("=≠≈≃≅≡∝∼<>≤≥≪≫∈∉⊂⊆→←⟷⇌⇒⇐⇔↦")  # spaced at the top level only: lim[x→0], {x, x≥0} stay tight
_BIN = set("+−±∓×÷∧∨")  # spaced at the top level and inside round brackets: √(b² − 4ac)
_OPEN, _CLOSE = "([{⟨⌈⌊" + _LBRACE, ")]}⟩⌉⌋" + _RBRACE


def _operand(ch: str) -> bool:
    return len(ch) == 1 and (ch.isalnum() or ch in ")]}⟩⌉⌋|′″!%°∞…⦵⁺⁻⁼⁾₊₋₌₎" + _RBRACE or bool(unicodedata.combining(ch)))


def _starts_factor(ch: str) -> bool:
    return len(ch) == 1 and (ch.isalnum() or ch in "(⟨⌈⌊√∛∜∫∑∏∮" + _FN_START + _LBRACE + _FRAC_L + _VEC_R + _VEC_L)


def _tidy(text: str) -> str:
    """Printed-maths spacing: s = ut + ½at², y = −3x (a true minus, unary signs tight), 3.0e−8, (2  −1; 3  4) in a matrix.
    Function names get a space only where one reads (v cos θ, sin(x), log₁₀ x); markers become what they stand for."""
    text = text.replace("-", "−")  # hyphens that are words or bonds are still markers here
    out: list[str] = []
    depth: list[str] = []
    fracs: list[int] = []
    sub_after = False

    def operand(k: int) -> bool:  # a bar closes (|x − 1|, |2|x| − 3|) when something stands before it: |−3| opens
        if k >= 0 and out[k] == "|":
            k -= 1
            while k >= 0 and out[k] == " ":
                k -= 1
        return k >= 0 and _operand(out[k])
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == _XL and _XR in text[i:] and text.index(_XR, i) + 1 < len(text):  # A —heat→ B, spaced as a relation
            j = text.index(_XR, i)
            label, arrow = _tidy(text[i + 1:j]), text[j + 1]
            while out and out[-1] == " ":
                out.pop()
            out += [" ", "←" + label + "—" if arrow == "←" else "—" + label + arrow, " "]
            i = j + 2
            while i < len(text) and text[i] == " ":
                i += 1
            continue
        if ch in _OPEN:
            depth.append(ch)
        elif ch in _CLOSE and depth:
            depth.pop()
        if ch == _FRAC_L:
            fracs.append(len(out))
        elif ch == _FRAC_R:
            start = fracs.pop() if fracs else None
            if start is not None and _starts_factor(text[i + 1:i + 2]):
                out.insert(start, "(")
                out.append(")")
        elif ch == _SUB_L:  # k_B T, not k_BT; a nuclide's ˣ_yA stays tight
            sub_after = bool(out) and out[-1].isalnum() and unicodedata.category(out[-1]) != "Lm"
        elif ch == _SUB_R:
            nxt = text[i + 1:i + 2]
            if sub_after and nxt.isalpha() and unicodedata.category(nxt) != "Lm":
                out.append(" ")
        elif ch == _FN_START:
            if operand(len(out) - 1):
                out.append(" ")
        elif ch == _FN_END:
            nxt = text[i + 1:i + 2]
            if nxt and not nxt.isspace() and nxt not in ")]}," + _RBRACE and not (nxt == "(" and out and out[-1].isalpha()):
                out.append(" ")
        elif (ch in _REL or ch in _BIN) and not unicodedata.combining(text[i + 1:i + 2] or "x"):  # 1̅+̅x̅ stays one
            j = i + 1
            while j < len(text) and text[j] == " ":
                j += 1
            k = len(out) - 1
            while k >= 0 and out[k] == " ":
                k -= 1
            prev, nxt = (out[k] if k >= 0 else ""), text[j:j + 1]
            here = not depth if ch in _REL else all(b == "(" for b in depth)
            unary = ch in _BIN and (not operand(k) or (out[-1:] == [" "] and j == i + 1))  # a matrix row: 2 −1
            e_power = ch in "+−" and prev in "eE" and k > 0 and (out[k - 1].isdigit() or out[k - 1] == ".") and nxt.isdigit()
            if here and nxt and nxt not in _CLOSE + ",;" and operand(k) and not unary and not e_power:
                del out[k + 1:]
                out += [" ", ch, " "]
                i = j
                continue
            out.append(ch)
        else:
            out.append(ch)
        i += 1
    s = re.sub(r" {2,}", " ", "".join(out))
    s = re.sub(r"(?<=[(\[{" + _LBRACE + r"]) +| +(?=[)\]}" + _RBRACE + "])", "", s).strip()
    return _unmark(s.replace(_QUAD, "  ").replace(_HYPHEN, "-").replace(_BOND2, "="))


def _unmark(text: str) -> str:
    return (text.replace(_LBRACE, "{").replace(_RBRACE, "}")  # literal braces kept out of LaTeX grouping
            .replace(_VEC_R, "→").replace(_VEC_L, "←").replace(_XL, "").replace(_XR, "").replace(_SUB_L, "").replace(_SUB_R, ""))


def to_terminal(text: str) -> str:
    """Convert every $...$ / $$...$$ / \\(...\\) / \\[...\\] span, and plain units such as m s^-2 elsewhere."""
    if not text:
        return ""
    text = text.translate(_LEFTOVERS)
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
