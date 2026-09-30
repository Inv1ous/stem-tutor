"""Parse learner responses and grade them deterministically.

Compact response syntax (one entry per comma or line):
  1B3            item 1, option B, confidence 3 (1 guess .. 4 certain)
  3 = 4.52e-3 mol dm-3 ~2   value answer with optional unit and confidence
  4?             don't know
  6 pts=1,3      self-marked: scheme points 1 and 3 awarded
"""
from __future__ import annotations

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


def parse_quantity(text: str) -> tuple[float, str, int | None]:
    return _parse(text)[:3]


def _parse(text: str) -> tuple[float, str, int | None, int | None]:
    """(value, unit, s.f. or None when trailing zeros make it ambiguous, digits written or None for a fraction)"""
    t = text.translate(SUPERSCRIPT).replace("−", "-").replace("–", "-").strip().lstrip("=").strip()
    t = re.sub(r"^[(\[]\s*([^)\]]*?)\s*[)\]]", r"\1", t)  # "(-1)", "[2.5] m"
    t = re.sub(r"(?<=\d),(?=\d{3}\b)", "", t)
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


def value_problem(item: dict, text: str) -> str | None:
    """Why a typed value can't be marked for this numeric item ("unreadable" or "unit"), else None."""
    try:
        unit = _parse(text)[1]
    except ParseError:
        return "unreadable"
    return "unit" if not item["answer"].get("unit") and unit not in ("", "%") else None


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
    return abs(value - target) <= 0.5 * 10 ** (math.floor(math.log10(abs(target))) - digits + 1) * (1 + 1e-9)


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
    if not want_unit and unit not in ("", "%"):  # a plain number: "500 kg" is not 500
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
    # a value correctly rounded at the learner's own precision counts as right, reading "20" strictly as 2 s.f.;
    # the s.f. rule below then sets the mark
    n = digits if digits and not ans.get("exact") and (digits >= 2 or digits in (allowed or ())) else 0
    if _close(value, target, tol) or _rounded_to(value, target, n):
        if allowed and sf is not None and sf not in allowed:
            notation = notation or f"{sf} s.f. (want {'/'.join(map(str, allowed))})"
        if notation:
            return _result(True, 0.5, "NOTATION", detail=notation)
        return _result(True, 1.0)
    for d in item.get("distractors") or []:
        if _close(value, d["value"], tol) or _rounded_to(value, d["value"], n):
            return _result(False, 0, d.get("error", "CONCEPT"), d.get("misconception"))
    if value and target:
        k = math.log10(abs(value / target))
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
        s = s.replace("\\", "")
        if not _EXPR_TEXT.fullmatch(s) or "." in re.sub(r"\d*\.\d+|\d+\.", "", s) or _BUILDERS.search(s):
            raise ParseError(f"not a plain maths expression: {s[:40]!r}")
        for evaluate in (False, True):  # build unevaluated first so a huge power is refused before it is computed
            expr = parse_expr(s, local_dict={"e": sympy.E, "pi": sympy.pi}, global_dict=dict(names),
                              transformations=tr, evaluate=evaluate)
            if not evaluate:
                _check_size(sympy, expr)
        return expr

    return sympy, parse


def _real_at(sympy, expr, point) -> float | None:
    """The value at `point`, or None outside the real domain: any function or fractional power inside is not real
    there (sqrt(x)·sqrt(y) at x, y < 0 is real, but only by passing through imaginary numbers)."""
    def real(e):
        try:
            v = complex(e.evalf(subs=point))  # numeric: exact substitution expands 8.5^(8.5^8.5) digit by digit
        except (TypeError, ValueError, ArithmeticError):
            return None
        return v.real if math.isfinite(abs(v)) and abs(v.imag) <= 1e-9 * max(1.0, abs(v.real)) else None

    for sub in sympy.preorder_traversal(expr):
        if (isinstance(sub, sympy.Function) or (sub.is_Pow and not sub.exp.is_integer)) and real(sub) is None:
            return None
    return real(expr)


def expressions_equal(a: str, b: str) -> bool:
    sympy, parse = _sympy()
    ea, eb = parse(a), parse(b)
    if ea - eb == 0:  # same once sympy has put both in canonical order; everything else is checked by value
        return True
    syms = sorted(ea.free_symbols | eb.free_symbols, key=str)
    rng = random.Random(7)
    agreed = 0
    for i in range(12 if syms else 1):
        # all positive, all negative, then alternating signs: abs(x) and x agree only for x > 0. A point outside
        # either side's real domain is skipped, so ln(x^2) = 2 ln(x) still holds on the positive values
        point = {s: (1 if i < 4 else -1 if i < 6 else (-1) ** (i + j))
                 * sympy.Rational(rng.randint(3, 17), rng.randint(2, 5)) for j, s in enumerate(syms)}
        va, vb = _real_at(sympy, ea, point), _real_at(sympy, eb, point)
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
    return _result(score == 1.0, score, needs_judgement=bool(unmatched), unmatched=unmatched)


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
