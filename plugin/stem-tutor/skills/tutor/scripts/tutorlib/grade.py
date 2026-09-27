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
from fractions import Fraction

from .units import SUPERSCRIPT, unit_factor

ERROR_CODES = ("RECALL", "MISREAD", "CONCEPT", "PROCEDURE", "STRATEGY", "SLIP", "NOTATION", "TIME")


class ParseError(ValueError):
    pass


_ENTRY_START = re.compile(r"^\s*\d+\s*(pts\s*=|=|\?|[A-Da-d](?![A-Za-z]))")
_IDK = re.compile(r"^(\d+)\s*\?$")
_POINTS = re.compile(r"^(\d+)\s*pts\s*=\s*([\d,\s]*)$")
_CHOICE = re.compile(r"^(\d+)\s*([A-Da-d])\s*([1-4])?$")
_VALUE = re.compile(r"^(\d+)\s*=\s*(.+?)\s*(?:~\s*([1-4]))?$")


def parse_responses(text: str) -> list[dict]:
    entries: list[str] = []
    for chunk in re.split(r"[,\n]", text):
        if _ENTRY_START.match(chunk) or not entries:
            entries.append(chunk.strip())
        else:
            entries[-1] += "," + chunk.strip()
    out = []
    for e in entries:
        if m := _IDK.match(e):
            out.append({"n": int(m[1]), "kind": "idk", "value": None, "conf": None})
        elif m := _POINTS.match(e):
            pts = [int(p) for p in re.findall(r"\d+", m[2])]
            out.append({"n": int(m[1]), "kind": "points", "value": pts, "conf": None})
        elif m := _CHOICE.match(e):
            out.append({"n": int(m[1]), "kind": "choice", "value": m[2].upper(), "conf": int(m[3]) if m[3] else None})
        elif m := _VALUE.match(e):
            out.append({"n": int(m[1]), "kind": "value", "value": m[2].strip(), "conf": int(m[3]) if m[3] else None})
        else:
            raise ParseError(f"Cannot read {e!r}. Use e.g. '1B3', '2 = 4.5 m s-1 ~2', '3?', '4 pts=1,2'.")
    return out


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
    t = text.translate(SUPERSCRIPT).replace("−", "-").strip()
    t = re.sub(r"(?<=\d),(?=\d{3}\b)", "", t)
    m = _NUM.match(t)
    if not m:
        raise ParseError(f"no number in {text!r}")
    value = float(m["mant"])
    sf = _sig_figs(m["mant"])
    if m["den"]:
        value /= float(m["den"])
        sf = None
    exp = m["e1"] or m["e2"]
    if exp:
        value *= 10 ** int(exp)
    return value, m["unit"].strip(), sf


# ---------------- grading ----------------
def _result(correct, score, error=None, misconception=None, needs_judgement=False, **extra):
    return {"correct": correct, "score": round(score, 3), "error": error,
            "misconception": misconception, "needs_judgement": needs_judgement, **extra}


def _close(a: float, b: float, tol_rel: float) -> bool:
    return abs(a - b) <= max(tol_rel * abs(b), 1e-12)


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
        value, unit, sf = parse_quantity(str(resp["value"]))
    except ParseError:
        return _result(False, 0, needs_judgement=True)
    tol = ans.get("tol_rel", 0.01)
    want_unit = ans.get("unit") or ""
    notation = None
    if want_unit:
        if not unit:
            notation = "missing unit"
        else:
            f = unit_factor(unit, want_unit)
            if f is None:
                return _result(False, 0, "NOTATION", detail="wrong unit")
            value *= f
    target = ans["value"]
    if _close(value, target, tol):
        allowed = ans.get("sf_ok") or ([ans["sf"]] if ans.get("sf") else None)
        if allowed and sf is not None and sf not in allowed:
            notation = notation or f"{sf} s.f. (want {'/'.join(map(str, allowed))})"
        if notation:
            return _result(True, 0.5, "NOTATION", detail=notation)
        return _result(True, 1.0)
    for d in item.get("distractors") or []:
        if _close(value, d["value"], tol):
            return _result(False, 0, d.get("error", "CONCEPT"), d.get("misconception"))
    if value and target:
        k = math.log10(abs(value / target))
        if abs(k - round(k)) < 0.01 and round(k) != 0 and value * target > 0:
            return _result(False, 0, "NOTATION", detail=f"power of ten off by {round(k)}")
        if _close(-value, target, tol):
            return _result(False, 0, "SLIP", detail="sign")
    return _result(False, 0, needs_judgement=True)


def _sympy():
    from . import deps

    deps.ensure("sympy")
    import sympy
    from sympy.parsing.sympy_parser import (convert_xor, implicit_multiplication_application,
                                            parse_expr, standard_transformations)

    tr = standard_transformations + (implicit_multiplication_application, convert_xor)
    return sympy, lambda s: parse_expr(s.replace("\\", ""), transformations=tr,
                                       local_dict={"e": sympy.E, "pi": sympy.pi})


def expressions_equal(a: str, b: str) -> bool:
    sympy, parse = _sympy()
    ea, eb = parse(a), parse(b)
    diff = sympy.simplify(ea - eb)
    if diff == 0:
        return True
    syms = sorted(diff.free_symbols, key=str)
    rng = random.Random(7)
    for _ in range(6):
        point = {s: Fraction(rng.randint(3, 17), rng.randint(2, 5)) for s in syms}
        try:
            if abs(complex(diff.subs(point).evalf())) > 1e-9:
                return False
        except (TypeError, ValueError):
            return False
    return bool(syms)


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
    total = len(item["scheme"])
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
