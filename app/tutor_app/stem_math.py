"""Faithful, semantic Unicode mathematics for AI output in JuliaMono."""
from __future__ import annotations

import functools
import re

from . import texmath

_COMMAND = re.compile(r"\\(?:[A-Za-z]+|[^A-Za-z])")
_ALPHABETS = {"mathit": "it", "mathbf": "bf", "boldsymbol": "bf", "bm": "bf", "mathbb": "bb",
              "mathcal": "cal", "mathfrak": "frak", "mathtt": "mono", **{n: n for n in ("it", "bf", "bb", "cal", "frak", "mono")}}
_UPRIGHT = {"mathrm", "text", "textrm", "mathsf", "operatorname", "textbf", "textit", "mbox",
            "ce", "pu", "si", "unit", "num", "begin", "end"}
_BIG = {"int": "∫", "oint": "∮", "iint": "∬", "iiint": "∭", "sum": "∑", "prod": "∏"}
_ENVIRONMENTS = {"matrix", "pmatrix", "bmatrix", "Bmatrix", "vmatrix", "Vmatrix", "cases"}
_ALIGNED = {"aligned", "aligned*", "align", "align*", "gathered", "split"}
_FUNCTIONS = set(texmath._FUNCS.split("|"))
_UPRIGHT_SYMBOLS = {"π", "Δ", "∇", "∂"}
_DIFFERENTIAL = re.compile(r"d(?:\s*[A-Za-z]|\\[A-Za-z]+)(?=\s|\\[,;!]|$|[+),=<>≤≥≠≈≃≅≡∝∼]"
                           r"|\\(?:leq?|geq?|neq?|approx|equiv|sim|propto)(?![A-Za-z]))")
_COMPLEX = chr(0xE0FF)  # a saved compound base must retain its grouping through flatlatex
_PREPROCESSED = _UPRIGHT | set(_ALPHABETS) | set(_BIG) | {
    "SI", "qty", "abs", "norm", "dv", "pdv", "binom", "dfrac", "tfrac", "degree", "ominus", "to",
    "left", "right", "le", "ge", "ne", "ldots", "therefore", "because", "limits", "nolimits",
    "displaystyle", "textstyle", "scriptstyle", "scriptscriptstyle", "boxed", "textcolor",
    "textsuperscript", "textsubscript", "lvert", "rvert", "lVert", "rVert", "vert", "Vert",
    "big", "Big", "bigg", "Bigg", "bigl", "bigr", "Bigl", "Bigr", "biggl", "biggr", "Biggl", "Biggr",
    "quad", "qquad", *_FUNCTIONS,
}


if texmath.flatlatex is not None:
    _ITALIC = texmath._data.it
    _PLAIN_ITALIC = {v: k for k, v in _ITALIC.items()}
    _SUB = {body: ch for ch, (kind, body) in texmath.SCRIPT_GLYPHS.items() if kind == "sub"}
    _SUB.update(texmath._data.subscript)
    _SUP = texmath._data.superscript

    def _script(body: str, mapping: dict[str, str]) -> str | None:
        plain = "".join(_PLAIN_ITALIC.get(ch, ch) for ch in body).replace("−", "-")
        if plain and all(ch in mapping for ch in plain):
            return "".join(mapping[ch] for ch in plain)
        return None

    class _AIConverter(texmath._Converter):
        """Keep the established fractions/accents, extending only JuliaMono scripts."""

        def _converter__latexfun_comb(self, comb, inputs):
            expr = inputs[0]
            plain = "".join(_PLAIN_ITALIC.get(ch, ch) for ch in expr)
            if comb[0] == "\u0302" and re.fullmatch(r"[A-Z]{3}", plain):
                return "∠" + expr
            if comb[0] in "\u20d7\u20d6" and not texmath._simple(expr) and not re.fullmatch(r"[A-Z]{2,}", plain):
                return (texmath._VEC_R if comb[0] == "\u20d7" else texmath._VEC_L) + "(" + expr + ")"
            return super()._converter__latexfun_comb(comb, inputs)

        def _converter__exponent(self, a, b):
            glyphs = _script(b, _SUP)
            base = a if texmath._simple(a) else f"({a})"
            if glyphs is not None:
                return base + glyphs
            if b.strip() in ("*", "∗"):
                return base + "∗"
            return f"({a}) to the power ({texmath._tidy(b)})"

        def _converter__indexed(self, a, b):
            if b.startswith(texmath._FNSUB):
                return a + "[" + texmath._tidy(b.removeprefix(texmath._FNSUB)) + "]"
            b = b.removeprefix(texmath._FNSUB)
            glyphs = _script(b, _SUB)
            base = a if texmath._simple(a) else f"({a})"
            return base + (glyphs if glyphs is not None else texmath._SUB_L + f"[index: {texmath._tidy(b)}]" + texmath._SUB_R)

    _CONVERTER = _AIConverter()
    _CONVERTER._converter__cmds[r"\bot"] = texmath._funtypes.latexfun(lambda _: "⊥", 0)
else:  # pragma: no cover - the existing optional-dependency fallback remains available to authored text
    _CONVERTER = None
    _ITALIC = {}


def _argument(text: str, start: int) -> tuple[str, int]:
    """Read one TeX argument; this scanner leaves actual conversion to flatlatex."""
    while start < len(text) and text[start].isspace():
        start += 1
    if start == len(text):
        raise ValueError("missing argument")
    if text[start] == "{":
        depth, end = 1, start + 1
        while end < len(text):
            if text[end] == "\\":
                command = _COMMAND.match(text, end)
                end = command.end()
                continue
            depth += (text[end] == "{") - (text[end] == "}")
            if not depth:
                return text[start + 1:end], end + 1
            end += 1
        raise ValueError("unbalanced group")
    command = _COMMAND.match(text, start)
    if command:
        end = command.end()
        definition = _CONVERTER._converter__cmds.get(command.group())
        for _ in range(definition.nargs if definition else 0):
            _, end = _argument(text, end)
        return text[start:end], end
    if text[start] in "}^_":
        raise ValueError("missing script or argument")
    return text[start], start + 1


def is_known_command(name: str) -> bool:
    """One command inventory for source validation and scoped JSON-escape recovery."""
    return name in _PREPROCESSED or (_CONVERTER is not None and "\\" + name in _CONVERTER._converter__cmds)


def _valid_source(expr: str) -> bool:
    depth = 0
    for token in re.finditer(r"\\(?:[A-Za-z]+|[^A-Za-z])|[{}$]", expr):
        text = token.group()
        if text.startswith("\\"):
            if text[1:].isalpha() and not is_known_command(text[1:]):
                return False
            if not text[1:].isalpha() and text not in {r"\,", r"\;", r"\:", r"\!", r"\%", r"\{", r"\}", r"\\", r"\ "}:
                return False
        elif text == "{":
            depth += 1
        elif text == "}":
            depth -= 1
            if depth < 0:
                return False
        else:
            return False
    paired = 0
    for delimiter in re.finditer(r"\\(left|right)(?![A-Za-z])", expr):
        bracket = re.match(r"\s*(\\[A-Za-z]+|\\[^A-Za-z]|.)", expr[delimiter.end():], re.S)
        if bracket is None or bracket[1] not in {"(", ")", "[", "]", "|", ".", "<", ">", r"\{", r"\}", r"\|",
                                                   r"\langle", r"\rangle", r"\lceil", r"\rceil", r"\lfloor", r"\rfloor",
                                                   r"\lvert", r"\rvert", r"\lVert", r"\rVert", r"\vert", r"\Vert"}:
            return False
        paired += 1 if delimiter[1] == "left" else -1
        if paired < 0:
            return False
    return depth == paired == 0 and not any(0xE000 <= ord(ch) <= 0xF8FF for ch in expr)


def _saved(visual: str, saved: list[str]) -> str:
    token = chr(0xE100 + len(saved))
    saved.append(visual)
    return "{" + ("" if texmath._simple(visual) else _COMPLEX) + token + "}"


def _slash_before(expr: str, index: int) -> bool:
    return re.sub(r"(?:\s|\\[,;:! ])+$", "", expr[:index]).endswith("/")


def _semantic(expr: str, saved: list[str], *, upright: bool = False, differential: bool = False) -> str:
    out, i = [], 0
    integral = bool(re.search(r"\\(?:i+nt|oint)(?![A-Za-z])", expr))
    while i < len(expr):
        command = _COMMAND.match(expr, i)
        if command:
            name, end = command.group()[1:], command.end()
            if name == "operatorname" and expr[end:end + 1] == "*":
                end += 1
            if name in _FUNCTIONS or name == "operatorname":
                function_name, function_source = name, command.group()
                if name == "operatorname":
                    body, end = _argument(expr, end)
                    body = _semantic(body, saved, upright=True)
                    function_name = texmath._math(body, converter=_CONVERTER, strict=True)
                    if not function_name:
                        raise ValueError("missing function name")
                    function_source = r"\operatorname{" + body + "}"
                scripts = {}
                while (tail := re.match(r"\s*([_^])", expr[end:])) is not None:
                    body, end = _argument(expr, end + tail.end())
                    if tail[1] in scripts:
                        raise ValueError("duplicate function script")
                    scripts[tail[1]] = _render(body, saved)
                if scripts:
                    visual = function_name
                    if "_" in scripts:
                        sub = _script(scripts["_"], _SUB)
                        visual += sub if sub is not None else f"[{scripts['_']}]" if name == "lim" else f"[index: {scripts['_']}]"
                    if "^" in scripts:
                        sup = _script(scripts["^"], _SUP)
                        visual = visual + sup if sup is not None else f"({visual}) to the power ({scripts['^']})"
                    out.append(texmath._FN_START + _saved(visual, saved) + texmath._FN_END)
                else:
                    out.append(function_source)
            elif name == "sqrt":
                index = re.match(r"\s*\[([^\[\]]*)\]", expr[end:])
                if expr[end:].lstrip().startswith("[") and index is None:
                    raise ValueError("invalid root index")
                body, end = _argument(expr, end + (index.end() if index else 0))
                if not body.strip():
                    raise ValueError("empty radicand")
                rendered_index = _render(index[1], saved) if index else ""
                if index and _script(rendered_index, _SUP) is None:
                    visual = f"root[index: {rendered_index}]({_render(body, saved)})"
                    out.append(_saved(visual, saved))
                else:
                    out.append(r"\sqrt" + ("[" + _semantic(index[1], saved) + "]" if index else "")
                               + "{" + _semantic(body, saved, upright=upright) + "}")
            elif name in _UPRIGHT or name in _ALPHABETS or name in {"SI", "qty", "frac", "dfrac", "tfrac"}:
                body, end = _argument(expr, end)
                if name in {"frac", "dfrac", "tfrac"}:
                    denominator, end = _argument(expr, end)
                    if not body.strip() or not denominator.strip():
                        raise ValueError("empty fraction")
                    derivative = body.lstrip().startswith("d") and denominator.lstrip().startswith("d")
                    args = [_semantic(arg, saved, upright=upright, differential=derivative) for arg in (body, denominator)]
                    fraction = r"\frac{" + args[0] + "}{" + args[1] + "}"
                    out.append("(" + fraction + ")" if _slash_before(expr, i) else fraction)
                elif name in {"SI", "qty"}:
                    units, end = _argument(expr, end)
                    out.append("\\" + name + "{" + body + "}{" + units + "}")
                else:
                    group = "\\" + _ALPHABETS.get(name, name) + "{" + _semantic(body, saved, upright=True) + "}"
                    if name in _UPRIGHT - {"begin", "end"} and re.match(r"\s*[_^]", expr[end:]):
                        visual = texmath._math(group, converter=_CONVERTER, strict=True)
                        if visual is None:
                            raise ValueError("unsupported upright group")
                        out.append(_saved(visual, saved))
                    else:
                        out.append("(" + group + ")" if _slash_before(expr, i) else group)
            elif name in _BIG:
                limits = {}
                while True:
                    rest = re.match(r"\s*(?:\\(?:no)?limits\s*)?([_^])", expr[end:])
                    if not rest:
                        break
                    arg, end = _argument(expr, end + rest.end())
                    if rest[1] in limits:
                        raise ValueError("duplicate limit")
                    limits[rest[1]] = _render(arg, saved)
                bound = ""
                if "_" in limits and "^" in limits:
                    bound = f"[{limits['_']} to {limits['^']}]"
                elif limits:
                    bound = f"[{'over' if '_' in limits else 'to'} {next(iter(limits.values()))}]"
                out.append(_saved(_BIG[name] + bound, saved) + r"\,")
            else:
                symbol = texmath._data.symbols.get(command.group(), "")
                out.append(_ITALIC.get(symbol, symbol) if not upright and symbol in _ITALIC and symbol not in _UPRIGHT_SYMBOLS else command.group())
            i = end
            continue
        ch = expr[i]
        if ch == "{" and _slash_before(expr, i):
            body, i = _argument(expr, i)
            if not body.strip():
                raise ValueError("empty denominator")
            out.append("(" + _semantic(body, saved, upright=upright) + ")")
            continue
        if ch == "d" and (differential and not expr[:i].strip() or integral and _DIFFERENTIAL.match(expr, i)):
            if integral:
                out.append(r"\,")
            out.append("d")
        elif ch in _UPRIGHT_SYMBOLS or ch in "eE" and i and expr[i - 1].isdigit() and re.match(r"[+-]?\d", expr[i + 1:]):
            out.append(ch)
        else:
            out.append(_ITALIC.get(ch, ch) if not upright else ch)
        i += 1
    return "".join(out)


def _render(expr: str, saved: list[str]) -> str:
    converted = texmath._math(_semantic(expr, saved), converter=_CONVERTER, strict=True)
    if converted is None or any(ch in converted for ch in "\\^_"):
        raise ValueError("unsupported conversion")
    return converted


@functools.lru_cache(maxsize=4096)
def render_math(expr: str) -> str | None:
    """Render delimiter-free maths, or request a source-preserving fallback."""
    if _CONVERTER is None or not expr.strip() or not _valid_source(expr):
        return None
    environments = re.findall(r"\\(begin|end)\{([^{}]+)\}", expr)
    if "&" in expr and not environments:
        return None
    stack = []
    for side, name in environments:
        if name not in _ENVIRONMENTS | _ALIGNED:
            return None
        if side == "begin":
            stack.append(name)
        elif not stack or stack.pop() != name:
            return None
    if stack:
        return None
    try:
        saved: list[str] = []
        aligned = re.fullmatch(r"\s*\\begin\{(" + "|".join(re.escape(n) for n in _ALIGNED) + r")\}(.*?)\\end\{\1\}\s*", expr, re.S)
        if aligned:
            if r"\begin" in aligned[2]:
                return None
            result = "\n".join(_render(row.replace("&", r"\,"), saved) for row in aligned[2].split(r"\\") if row.strip())
        else:
            result = _render(expr, saved)
        for index in reversed(range(len(saved))):
            result = result.replace(chr(0xE100 + index), saved[index])
        return result.replace(_COMPLEX, "").replace("*", "∗")
    except (ValueError, IndexError, RecursionError):
        return None
