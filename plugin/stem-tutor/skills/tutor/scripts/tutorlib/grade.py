"""Parse learner responses and grade them deterministically.

Compact response syntax (one entry per comma or line):
  1B3            item 1, option B, confidence 3 (1 guess .. 4 certain)
  3 = 4.52e-3 mol dm-3 ~2   value answer with optional unit and confidence
  4?             don't know
  6 pts=1,3      self-marked: scheme points 1 and 3 awarded
"""
from __future__ import annotations

import keyword
import math
import random
import re

from .units import SUPERSCRIPT, unit_factor

ERROR_CODES = ("RECALL", "MISREAD", "CONCEPT", "PROCEDURE", "STRATEGY", "SLIP", "NOTATION", "TIME")


class ParseError(ValueError):
    pass


_ENTRY_START = re.compile(r"^\s*\d+\s*(pts\s*=|[=:]|\?|[A-Da-d](?![A-Za-z]))")
_IDK = re.compile(r"^(\d+)\s*\?$")
_POINTS = re.compile(r"^(\d+)\s*pts\s*=\s*([\d,\s]*)$")
_CHOICE = re.compile(r"^(\d+)\s*([A-Da-d])\s*([1-4])?$")
_VALUE = re.compile(r"^(\d+)\s*[=:]\s*(.+?)\s*(?:~\s*([1-4]))?$")


def parse_responses(text: str) -> list[dict]:
    entries: list[str] = []
    for chunk in re.split(r"[,\n]", text):
        if not chunk.strip():
            continue
        # a 1-2 digit number opens a new entry; a 3-digit group is a thousands separator ("1,000 m")
        in_points = entries and _POINTS.match(entries[-1]) and re.fullmatch(r"\s*\d+\s*", chunk)
        if not in_points and (_ENTRY_START.match(chunk) or re.match(r"^\s*[1-9]\d?(?![\d.])", chunk) or not entries):
            entries.append(chunk.strip())
        else:
            entries[-1] += "," + chunk.strip()
    out = []
    for e in entries:
        r = _parse_one(e)
        if r is None and "," in e:  # a bad entry swallowed by the one before it
            head, tail = e.split(",", 1)
            if (rh := _parse_one(head.strip())) is not None:
                out.append(rh)
                e = tail.strip()
                r = _parse_one(e)
        if r is None:
            m = re.match(r"\s*(\d+)", e)
            r = {"n": int(m[1]) if m else None, "kind": "bad", "value": e, "conf": None}
        out.append(r)
    return out


def _parse_one(e: str) -> dict | None:
    if m := _IDK.match(e):
        return {"n": int(m[1]), "kind": "idk", "value": None, "conf": None}
    if m := _POINTS.match(e):
        return {"n": int(m[1]), "kind": "points", "value": [int(p) for p in re.findall(r"\d+", m[2])], "conf": None}
    if m := _CHOICE.match(e):
        return {"n": int(m[1]), "kind": "choice", "value": m[2].upper(), "conf": int(m[3]) if m[3] else None}
    if m := _VALUE.match(e):
        return {"n": int(m[1]), "kind": "value", "value": m[2].strip(), "conf": int(m[3]) if m[3] else None}
    return None


# ---------------- numbers ----------------
_NUM = re.compile(
    r"^\s*(?P<mant>[+-]?(?:\d+(?:\.\d*)?|\.\d+))"
    r"(?:\s*/\s*(?P<den>\d+(?:\.\d*)?))?"
    r"(?:\s*[eE]\s*(?P<e1>[+-]?\d+)"
    r"|\s*(?:[x×*·]|\\times)\s*10\s*\^?\s*\{?\(?\s*(?P<e2>[+-]?\d+)\s*\)?\}?)?"
    r"\s*(?P<unit>.*)$"
)


def _sig_figs(mant: str) -> int | None:
    digits = mant.lstrip("+-")
    if "." in digits:
        return len(digits.replace(".", "").lstrip("0")) or 1
    stripped = digits.lstrip("0")
    if stripped.endswith("0"):
        return None
    return len(stripped) or 1


_POWER = re.compile(r"(?<=\d)[⁻⁺]?[⁰¹²³⁴⁵⁶⁷⁸⁹]+")
_POWER_OF_TEN = re.compile(r"^([+-]?)10\s*\^\s*[({]?\s*([+-]?\d+)\s*[)}]?")


def plain_powers(text: str) -> str:
    """Superscripts as plain text. A power written on a number keeps a caret (10³ → 10^3, never 103); the powers
    in a unit become bare digits (m s⁻² → m s-2)."""
    return _POWER.sub(lambda m: "^" + m[0].translate(SUPERSCRIPT), text).translate(SUPERSCRIPT)


def parse_quantity(text: str) -> tuple[float, str, int | None]:
    return _parse(text)[:3]


def _parse(text: str) -> tuple[float, str, int | None, int | None]:
    """(value, unit, s.f. or None when trailing zeros make it ambiguous, digits written or None for a fraction)"""
    t = plain_powers(text).replace("−", "-").replace("–", "-").strip().lstrip("=").strip()
    t = re.sub(r"^[(\[]\s*([^)\]]*?)\s*[)\]]", r"\1", t)  # "(-1)", "[2.5] m"
    t = re.sub(r"(?<=\d),(?=\d{3}\b)", "", t)
    t = _POWER_OF_TEN.sub(r"\g<1>1e\2", t)  # a bare power of ten is a number (10^3, 10⁻³); any other power is not
    m = _NUM.match(t)
    if not m:
        raise ParseError(f"no number in {text!r}")
    try:
        value = float(m["mant"])
        sf = _sig_figs(m["mant"])
        if m["den"]:
            value /= float(m["den"])
            sf = None
        exp = m["e1"] or m["e2"]
        if exp:
            value *= 10 ** int(exp)
    except (ArithmeticError, ValueError):
        raise ParseError(f"cannot use the number in {text!r}") from None
    if not math.isfinite(value):
        raise ParseError(f"number out of range in {text!r}")
    unit = m["unit"].strip()
    if unit and not (unit[0].isalpha() or unit[0] in "%°/"):  # "500 + 1", "2^10", "5 000": not one number
        raise ParseError(f"more than a number in {text!r}")
    digits = None if m["den"] else len(m["mant"].lstrip("+-").replace(".", "").lstrip("0")) or 1
    return value, unit, sf, digits


def _unit_on_plain_number(item: dict, unit: str) -> bool:
    """A unit typed on an answer that is a plain number; "%" is fine only where the question asks for a percentage."""
    return bool(unit) and not (unit == "%" and re.search(r"percent|%", item.get("stem") or "", re.I))


def value_problem(item: dict, text: str) -> str | None:
    """Why a typed value can't be marked for this numeric item ("unreadable" or "unit"), else None."""
    try:
        unit = _parse(text)[1]
    except ParseError:
        return "unreadable"
    return "unit" if not item["answer"].get("unit") and _unit_on_plain_number(item, unit) else None


# ---------------- grading ----------------
def _result(correct, score, error=None, misconception=None, needs_judgement=False, **extra):
    return {"correct": correct, "score": round(score, 3), "error": error,
            "misconception": misconception, "needs_judgement": needs_judgement, **extra}


def _close(a: float, b: float, tol_rel: float) -> bool:
    return abs(a - b) <= max(tol_rel * abs(b), 1e-12)


def _rounded_to(value: float, target: float, digits: int) -> bool:
    """`value` is `target` rounded to `digits` significant figures (a half may go either way)."""
    if not digits or not target:
        return False
    unit = 10 ** (math.floor(math.log10(abs(target))) - digits + 1)  # one in the last figure kept
    return abs(value - target) <= 0.5 * unit * (1 + 1e-9) and abs(value / unit - round(value / unit)) < 1e-6


def rounding_of(value: float, target: float, sf: int | None, digits: int | None, allowed) -> bool:
    """`value`, as typed, is `target` correctly rounded: at the digits written, or for a whole number ending in
    zeros (2400) at any of them, since such a number does not show its figures. One figure counts only where the
    question accepts one."""
    written = range(1, (digits or 0) + 1) if sf is None else [digits]
    return any(_rounded_to(value, target, d) for d in written if d and (d >= 2 or d in (allowed or ())))


def _distractor(entry) -> tuple[str | None, str]:
    if isinstance(entry, dict):
        return entry.get("misconception"), entry.get("error", "CONCEPT")
    return entry, "CONCEPT"


def _grade_mcq(item, resp):
    if resp["kind"] != "choice":
        return _result(False, 0, needs_judgement=True)
    if resp["value"] == item["answer"]:
        return _result(True, 1.0)
    mis, err = _distractor((item.get("distractors") or {}).get(resp["value"]))
    if mis:
        return _result(False, 0, err, mis)
    return _result(False, 0, needs_judgement=True)


def _grade_numeric(item, resp):
    ans = item["answer"]
    try:
        value, unit, sf, digits = _parse(str(resp["value"]))
    except ParseError:
        return _result(False, 0, needs_judgement=True)
    tol = 1e-9 if ans.get("exact") else ans.get("tol_rel", 0.01)  # exact: counts, conversions; 1e-9 absorbs float noise
    want_unit = ans.get("unit") or ""
    if not want_unit and _unit_on_plain_number(item, unit):  # a plain number: "500 kg" is not 500
        return _result(False, 0, needs_judgement=True, detail="expected a plain number")
    notation = None
    if want_unit:
        if not unit:
            notation = "missing unit"
        else:
            f = unit_factor(unit, want_unit)
            if f is None:
                return _result(False, 0, "NOTATION", detail="wrong unit")
            value *= f
            if not math.isfinite(value):
                return _result(False, 0, needs_judgement=True, detail="number out of range")
    target = ans["value"]
    allowed = ans.get("sf_ok") or ([ans["sf"]] if ans.get("sf") else None)
    # a value correctly rounded at the learner's own precision counts as right; the s.f. rule below then sets the mark
    rounds = not ans.get("exact")
    if _close(value, target, tol) or (rounds and rounding_of(value, target, sf, digits, allowed)):
        if allowed and sf is not None and sf not in allowed:
            notation = notation or f"{sf} s.f. (want {'/'.join(map(str, allowed))})"
        if notation:
            return _result(True, 0.5, "NOTATION", detail=notation)
        return _result(True, 1.0)
    for d in item.get("distractors") or []:
        if _close(value, d["value"], tol) or (rounds and rounding_of(value, d["value"], sf, digits, allowed)):
            return _result(False, 0, d.get("error", "CONCEPT"), d.get("misconception"))
    if value and target:
        k = math.log10(abs(value)) - math.log10(abs(target))  # not log(value / target): 1e308 / 7.5e-7 overflows
        if abs(k - round(k)) < 0.01 and round(k) != 0 and value * target > 0:
            return _result(False, 0, "NOTATION", detail=f"power of ten off by {round(k)}")
        if _close(-value, target, tol):
            return _result(False, 0, "SLIP", detail="sign")
    return _result(False, 0, needs_judgement=True)


# parse_expr runs eval(), so learner text is limited to plain maths before it gets there: these characters only,
# a dot only inside a number, and names that resolve to nothing but the functions below (anything else is a symbol)
_EXPR_TEXT = re.compile(r"[0-9A-Za-z\s+\-*/^().,]{1,200}")
_EXPR_FUNCS = ("sin", "cos", "tan", "sec", "csc", "cot", "asin", "acos", "atan", "sinh", "cosh", "tanh",
               "exp", "log", "sqrt")
_BUILDERS = re.compile(r"(?<![A-Za-z])(Symbol|Function|Number|Integer|Float|Rational|Add|Mul|Pow)(?![A-Za-z])")
_MAX_POWER = 1_000  # nested exponents multiply; A-level needs far less, and sympy grinds on huge powers


_UNICODE_MATHS = str.maketrans({
    "×": "*", "·": "*", "⋅": "*", "÷": "/", "−": "-", "–": "-", "π": " pi ", "√": " sqrt ", "½": "(1/2)",
    "α": " alpha ", "β": " beta ", "γ": " gamma ", "δ": " delta ", "Δ": " Delta ", "ε": " epsilon ", "θ": " theta ",
    "λ": " lamda ", "μ": " mu ", "µ": " mu ", "ν": " nu ", "ρ": " rho ", "σ": " sigma ", "τ": " tau ", "φ": " phi ",
    "ω": " omega ", "Ω": " Omega "})


def _plain_maths(s: str) -> str:
    """Maths as the app displays it, in plain ASCII: u² → u^(2), 2×a → 2*a, 2πr → 2 pi r, √(2gh) → sqrt (2gh)."""
    s = re.sub(r"[⁻⁺]?[⁰¹²³⁴⁵⁶⁷⁸⁹]+", lambda m: "^(" + m[0].translate(SUPERSCRIPT) + ")", s)
    return s.translate(_UNICODE_MATHS)


def expression_readable(text: str) -> bool:
    """Whether an expression answer can be read at all; one that can't is refused and the question stays open."""
    try:
        _sympy()[1](text)
    except Exception:  # noqa: BLE001 - any parse failure means "type it again", never a wrong answer
        return False
    return True


def _names(s: str) -> str:
    """Spell variable names so sympy reads them as the learner meant: a keyword such as the "as" of 2as is letters,
    lambda is the Greek letter, and digits after a letter are a subscript (R1 -> R_1, not R times 1) unless they are
    the exponent of a number like 1e5."""
    def subscript(m):
        if m[1] in "eE" and m.start() and m.string[m.start() - 1] in "0123456789.":
            return m[0]
        return f" {m[1]}_{m[2]} "

    s = re.sub(r"([A-Za-z])(\d+)", subscript, s)
    return re.sub(r"[A-Za-z]+", lambda m: "lamda" if m[0] == "lambda" else " ".join(m[0])
                  if keyword.iskeyword(m[0]) else m[0], s)


def _check_size(sympy, tree) -> None:
    """Refuse work sympy could take minutes over: a power beyond _MAX_POWER, or exponentials stacked three deep."""
    degree: dict = {}
    height: dict = {}
    for node in sympy.postorder_traversal(tree):
        d = max((degree.get(a, 1) for a in node.args), default=1)
        h = max((height.get(a, 0) for a in node.args), default=0)
        if isinstance(node, sympy.Pow) and not node.exp.free_symbols:
            try:
                d = degree.get(node.base, 1) * max(1.0, abs(complex(node.exp.evalf())))
            except (TypeError, ValueError):
                d = math.inf
        elif isinstance(node, sympy.Pow):
            h = max(height.get(node.base, 0), 1 + height.get(node.exp, 0))
        elif isinstance(node, sympy.exp):
            h = 1 + height.get(node.args[0], 0)
        if not d <= _MAX_POWER or h >= 3:
            raise ParseError("too large to check")
        degree[node], height[node] = d, h


def _sympy():
    from . import deps

    deps.ensure("sympy")
    import sympy
    from sympy.parsing.sympy_parser import (convert_xor, implicit_multiplication_application,
                                            parse_expr, standard_transformations)

    tr = standard_transformations + (implicit_multiplication_application, convert_xor)
    names = {n: getattr(sympy, n) for n in ("Symbol", "Function", "Number", "Integer", "Float", "Rational", "Add",
                                            "Mul", "Pow", *_EXPR_FUNCS)}
    names.update(__builtins__={}, abs=sympy.Abs, ln=sympy.log)

    def parse(s: str):
        s = _plain_maths(s.replace("\\", ""))
        if not _EXPR_TEXT.fullmatch(s) or "." in re.sub(r"\d*\.\d+|\d+\.", "", s) or _BUILDERS.search(s):
            raise ParseError(f"not a plain maths expression: {s[:40]!r}")
        s = _names(s)
        for evaluate in (False, True):  # build unevaluated first so a huge power is refused before it is computed
            expr = parse_expr(s, local_dict={"e": sympy.E, "pi": sympy.pi}, global_dict=dict(names),
                              transformations=tr, evaluate=evaluate)
            if not evaluate:
                _check_size(sympy, expr)
        return expr

    return sympy, parse


_FLOAT_FUNCS = {"sin": math.sin, "cos": math.cos, "tan": math.tan, "sec": lambda v: 1 / math.cos(v),
                "csc": lambda v: 1 / math.sin(v), "cot": lambda v: 1 / math.tan(v), "asin": math.asin,
                "acos": math.acos, "atan": math.atan, "sinh": math.sinh, "cosh": math.cosh, "tanh": math.tanh,
                "exp": math.exp, "log": math.log, "Abs": abs}


def _value(e, point: dict) -> float:
    """`e` at `point` in real floating point. Raises outside the real domain (sqrt or ln of a negative anywhere
    inside), at a pole and on overflow, where exact arithmetic could grind on 8.5^(8.5^10) or evalf report noise."""
    if e.is_Symbol:
        return point[e]
    if e.is_Add:
        return math.fsum(_value(a, point) for a in e.args)
    if e.is_Mul:
        return math.prod(_value(a, point) for a in e.args)
    if e.is_Pow:
        return math.pow(_value(e.base, point), _value(e.exp, point))
    if e.is_Function:
        return _FLOAT_FUNCS[type(e).__name__](*(_value(a, point) for a in e.args))
    return float(e)  # numbers, pi, E; zoo, nan and I raise


def _real_at(expr, point: dict) -> float | None:
    try:
        v = _value(expr, point)
    except (ArithmeticError, ValueError, TypeError, KeyError):
        return None
    return v if math.isfinite(v) else None


def expressions_equal(a: str, b: str) -> bool:
    parse = _sympy()[1]
    ea, eb = parse(a), parse(b)
    if ea - eb == 0:  # same once sympy has put both in canonical order; everything else is checked by value
        return True
    syms = sorted(ea.free_symbols | eb.free_symbols, key=str)
    rng = random.Random(7)
    agreed = 0
    for i in range(12 if syms else 1):
        # all positive, all negative, then alternating signs: abs(x) and x agree only for x > 0. A point outside
        # either side's real domain is skipped, so ln(x^2) = 2 ln(x) still holds on the positive values
        point = {s: (1 if i < 4 else -1 if i < 6 else (-1) ** (i + j)) * rng.randint(3, 17) / rng.randint(2, 5)
                 for j, s in enumerate(syms)}
        va, vb = _real_at(ea, point), _real_at(eb, point)
        if va is None or vb is None:
            continue
        if abs(va - vb) > 1e-9 * max(1.0, abs(va), abs(vb)):
            return False
        agreed += 1
    return agreed >= (3 if syms else 1)


def _grade_expression(item, resp):
    try:
        ok = expressions_equal(str(resp["value"]), item["answer"]["expr"])
    except Exception:
        return _result(False, 0, needs_judgement=True)
    return _result(True, 1.0) if ok else _result(False, 0, needs_judgement=True)


def _grade_rubric(item, resp):
    text = str(resp["value"]).lower()
    matched, unmatched = 0, []
    for point in item["rubric"]:
        if all(any(k.lower() in text for k in group) for group in point["keywords"]):
            matched += 1
        else:
            unmatched.append(point["point"])
    score = matched / len(item["rubric"])
    # only a hint for the judge: swapped or negated statements ("velocity is the rate of change of velocity")
    # contain every keyword, so a short answer is never marked right on keywords alone
    return _result(False, score, needs_judgement=True, unmatched=unmatched)


def _grade_points(item, resp):
    total = len(item.get("scheme") or [])
    if not total:
        return _result(False, 0, needs_judgement=True)
    got = len({p for p in resp["value"] if 1 <= p <= total})
    return _result(got == total, got / total, self_marked=True)


def grade_item(item: dict, resp: dict) -> dict:
    if resp["kind"] == "idk":
        return _result(False, 0, "RECALL", detail="don't know")
    if resp["kind"] == "points":
        return _grade_points(item, resp)
    kind = item["kind"]
    if kind == "mcq":
        return _grade_mcq(item, resp)
    if kind == "numeric":
        return _grade_numeric(item, resp)
    if kind == "expression":
        return _grade_expression(item, resp)
    if kind == "short":
        return _grade_rubric(item, resp)
    return _result(False, 0, needs_judgement=True, detail="needs self-mark (use pts=)")
