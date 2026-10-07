"""Validate a content pack against its spec graph before it may be published.

Checks: schema and ids, KC membership, MCQ keys and distractors, template answers recomputed over
several instantiations, distractors distinct from the answer, units parse, per-spec constants,
expressions parse, structured schemes, worked-example checks, Obsidian render lint on every
markdown field, hints/explanations on generated items, and >= 6 retrieval variants per KC
(a parametric template counts as 3).

  python build/validate_pack.py <pack.json> <graph.json>
"""
from __future__ import annotations

import ast
import json
import math
import random
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "plugin/stem-tutor/skills/tutor/scripts"))
from tutorlib import grade, lint, packs, units  # noqa: E402
from add_past import question_key  # noqa: E402  (build/ is on the path when run as a script or from tests)

MIN_VARIANTS = 6
KINDS = {"mcq", "numeric", "expression", "short", "structured"}
# constant families: any literal in a family must be the value this spec uses
G_FAMILY = {9.8, 9.81, 10.0}
SPEC_G = {"9702": 9.81, "M1": 9.8, "M2": 9.8, "M3": 9.8}


def _e(rule, where, detail=""):
    return {"rule": rule, "where": where, "detail": detail}


def _literals(expr: str) -> list[float]:
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError:
        return []
    return [float(n.value) for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, (int, float))]


def _check_constants(expr: str, spec: str, where: str, out: list) -> None:
    want = SPEC_G.get(spec)
    for v in _literals(expr):
        if v in G_FAMILY and v != 10.0 and want is not None and v != want:
            out.append(_e("constant", where, f"g = {v:g} but {spec} uses {want:g}"))


def _check_answer(ans: dict, where: str, out: list, need_value: bool = True) -> None:
    if "expr" in ans:
        try:
            grade._sympy()[1](ans["expr"])
        except Exception as exc:  # noqa: BLE001 - any parse failure is a content error
            out.append(_e("expression", where, str(exc)[:80]))
        return
    if need_value and not isinstance(ans.get("value"), (int, float)):
        out.append(_e("numeric", where, "answer.value missing"))
    if ans.get("unit"):
        try:
            units.parse_unit(ans["unit"])
        except ValueError as exc:
            out.append(_e("unit", where, str(exc)))
    if not (ans.get("sf") or ans.get("sf_ok")) and not ans.get("exact"):
        out.append(_e("numeric", where, "state sf or sf_ok (or exact: true)"))


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]{3,}", text.lower())}


def _hint_leak(it: dict) -> str | None:
    """A hint must never state the answer: the correct option's words, or the numeric answer itself."""
    hints = it.get("hints") or []
    if not hints:
        return None
    if it["kind"] == "mcq" and isinstance(it.get("options"), dict) and it.get("answer") in it["options"]:
        right = _words(it["options"][it["answer"]])
        others = [_words(v) for k, v in it["options"].items() if k != it["answer"]]
        for h in hints:
            hw = _words(h)
            if right and right <= hw and not any(o and o <= hw for o in others):
                return f"hint names the correct option: {h[:60]}"
    if it["kind"] == "numeric" and isinstance((it.get("answer") or {}).get("value"), (int, float)):
        v = float(it["answer"]["value"])
        for h in hints:
            for n in re.findall(r"-?\d+(?:\.\d+)?(?:e-?\d+)?", h):
                if v and abs(float(n) - v) <= 0.005 * abs(v):
                    return f"hint contains the answer {v:g}: {h[:60]}"
    return None


def _texts(pack: dict):
    yield "outline", pack.get("outline", "")
    for m in pack.get("misconceptions", []):
        for f in ("statement", "refutation", "contrast"):
            yield f"misconception {m.get('id')}.{f}", m.get(f, "")
    for w in pack.get("worked", []):
        yield f"worked {w.get('id')}.problem", w.get("problem", "")
        for i, st in enumerate(w.get("steps", [])):
            yield f"worked {w.get('id')}.step{i + 1}", f"{st.get('do', '')}\n{st.get('why', '')}"
        if w.get("faded"):
            yield f"worked {w.get('id')}.faded", w["faded"].get("problem", "")
    for it in pack.get("items") if isinstance(pack.get("items"), list) else []:
        if not isinstance(it, dict):
            continue
        yield f"item {it.get('id')}.stem", it.get("stem", "")
        for k, v in (it.get("options") if isinstance(it.get("options"), dict) else {}).items():
            yield f"item {it.get('id')}.option{k}", v
        yield f"item {it.get('id')}.explanation", it.get("explanation") or ""
        for h in it.get("hints") or []:
            yield f"item {it.get('id')}.hint", h
        for pt in it.get("scheme") or []:
            yield f"item {it.get('id')}.scheme", pt.get("point", "")
    for c in pack.get("flashcards", []):
        yield f"flashcard {c.get('id')}", f"{c.get('front', '')}\n{c.get('back', '')}"


def validate(pack: dict, graph: dict, min_variants: int = MIN_VARIANTS) -> list[dict]:
    """Every problem found, as {rule, where, detail}. A pack too malformed to check further is reported, not raised."""
    out: list[dict] = []
    try:
        _validate(pack, graph, min_variants, out)
    except Exception as exc:  # noqa: BLE001 - a shape the checks below did not expect is a content error
        out.append(_e("malformed", "pack", f"{type(exc).__name__}: {exc}"[:120]))
    return out


def _validate(pack: dict, graph: dict, min_variants: int, out: list[dict]) -> None:
    spec = graph["spec"]
    if pack.get("spec") != spec:
        out.append(_e("spec", pack.get("subtopic", "?"), f"pack is for {pack.get('spec')}, graph for {spec}"))
    if not pack.get("note"):
        out.append(_e("note", pack.get("subtopic", "?"), "the pack names no note"))
    items = pack.get("items")
    if not isinstance(items, list):
        out.append(_e("items", pack.get("subtopic", "?"), "items must be a list"))
        items = []
    all_kcs = {k["id"] for k in graph["kcs"]}
    sub_kcs = [k["id"] for k in graph["kcs"] if k["subtopic"] == pack.get("subtopic")]
    if not sub_kcs:
        out.append(_e("subtopic", pack.get("subtopic", "?"), "not in graph"))
    mis_ids = {m["id"] for m in pack.get("misconceptions", [])}
    for m in pack.get("misconceptions", []):
        if m.get("kc") not in all_kcs:
            out.append(_e("unknown-kc", f"misconception {m.get('id')}", m.get("kc")))
    seen: set[str] = set()
    questions: dict[str, str] = {}
    variants = {k: 0 for k in sub_kcs}
    for n, it in enumerate(items):
        if not isinstance(it, dict):
            out.append(_e("item", f"item #{n + 1}", "not an object"))
            continue
        where = f"item {it.get('id')}"
        if not it.get("id"):
            out.append(_e("id", f"item #{n + 1}", "no id"))
        if it.get("id") in seen:
            out.append(_e("duplicate-id", where))
        seen.add(it.get("id"))
        if it.get("kind") == "mcq" and "template" not in it:  # CAIE reuses questions across paper variants and years
            if (q := question_key(it)) in questions:
                out.append(_e("duplicate-question", where, f"same question as {questions[q]}"))
            questions.setdefault(q, it.get("id"))
        if it.get("kind") not in KINDS:
            out.append(_e("kind", where, str(it.get("kind"))))
            continue
        if not it.get("kcs") or any(k not in all_kcs for k in it["kcs"]):
            out.append(_e("unknown-kc", where, str(it.get("kcs"))))
        try:
            difficulty_ok = 1 <= int(it.get("difficulty", 0)) <= 5
        except (TypeError, ValueError):
            difficulty_ok = False
        if not difficulty_ok:
            out.append(_e("difficulty", where, str(it.get("difficulty"))))
        generated = (it.get("source") or {}).get("type") != "past"
        if generated and it["kind"] != "structured":
            if len(it.get("hints") or []) != 3:
                out.append(_e("hints", where, "generated items need exactly 3 hints"))
            if not it.get("explanation"):
                out.append(_e("explanation", where))
        leak = _hint_leak(it)
        if leak:
            out.append(_e("hint-leak", where, leak))
        if it["kind"] == "mcq":
            opts = it.get("options")
            if opts is None and it.get("image"):
                opts = {k: k for k in "ABCD"}
            if not isinstance(opts, dict) or sorted(opts) != ["A", "B", "C", "D"] or it.get("answer") not in opts:
                out.append(_e("mcq-answer", where, "options A-D and answer among them"))
            # with a figure the options are in the figure: their text may be only its labels, alike
            elif not it.get("image") and len({" ".join(str(v).split()) for v in opts.values()}) < len(opts):
                out.append(_e("mcq-options", where, "two options say the same"))
            for letter, d in (it.get("distractors") or {}).items():
                mid = d.get("misconception") if isinstance(d, dict) else d
                if letter == it.get("answer") or (opts and letter not in opts):
                    out.append(_e("mcq-distractor", where, letter))
                if mid and mid not in mis_ids:
                    out.append(_e("unknown-misconception", where, mid))
        elif it["kind"] == "numeric":
            tpl = it.get("template")
            _check_answer(it.get("answer") or {}, where, out, need_value=not tpl)
            if tpl:
                for expr in [tpl.get("answer", "")] + [d.get("expr", "") for d in tpl.get("distractors", [])] + \
                        list(tpl.get("derived", {}).values()):
                    _check_constants(expr, spec, where, out)
                for d in tpl.get("distractors", []):
                    if d.get("misconception") and d["misconception"] not in mis_ids:
                        out.append(_e("unknown-misconception", where, d["misconception"]))
                try:
                    for seed in range(8):
                        inst = packs.instantiate(it, random.Random(seed))
                        a = inst["answer"]["value"]
                        if not math.isfinite(a):
                            raise ValueError("non-finite answer")
                        for d in inst["distractors"]:
                            if abs(d["value"] - a) <= 0.02 * max(abs(a), 1e-12):
                                out.append(_e("distractor-equals-answer", where, f"seed {seed}"))
                                raise StopIteration
                except StopIteration:
                    pass
                except Exception as exc:  # noqa: BLE001
                    out.append(_e("template", where, str(exc)[:80]))
            else:
                a = (it.get("answer") or {}).get("value")
                for d in it.get("distractors") or []:
                    if d.get("misconception") and d["misconception"] not in mis_ids:
                        out.append(_e("unknown-misconception", where, d["misconception"]))
                    if isinstance(a, (int, float)) and isinstance(d.get("value"), (int, float)) \
                            and abs(d["value"] - a) <= 0.02 * max(abs(a), 1e-12):
                        out.append(_e("distractor-equals-answer", where, f"{d['value']:g}"))
        elif it["kind"] == "expression":
            _check_answer(it.get("answer") or {"expr": ""}, where, out)
        elif it["kind"] == "short":
            if not it.get("rubric") or any(not p.get("keywords") for p in it["rubric"]):
                out.append(_e("rubric", where))
        elif it["kind"] == "structured":
            if not it.get("scheme"):
                out.append(_e("scheme", where, "structured items need mark-scheme points"))
            for pt in it.get("scheme") or []:
                if pt.get("check"):
                    _check_answer(pt["check"].get("answer", {}), where, out)
        for k in it.get("kcs") or []:
            if k in variants:
                variants[k] += 3 if it.get("template") else 1
    for k, n in variants.items():
        if n < min_variants:
            out.append(_e("too-few-items", k, f"{n} < {min_variants}"))
    for w in pack.get("worked", []):
        for i, st in enumerate(w.get("steps", [])):
            if st.get("check"):
                _check_answer(st["check"].get("answer", {}), f"worked {w.get('id')}.step{i + 1}", out)
        if w.get("faded"):
            _check_answer(w["faded"].get("answer", {}), f"worked {w.get('id')}.faded", out)
    for where, text in _texts(pack):
        for f in lint.lint(text or ""):
            out.append(_e("lint", where, f"{f['rule']}: {f['message']}"))


if __name__ == "__main__":
    pack = json.loads(Path(sys.argv[1]).read_text())
    graph = json.loads(Path(sys.argv[2]).read_text())
    problems = validate(pack, graph)
    print(json.dumps({"ok": not problems, "errors": problems[:80], "count": len(problems)}, ensure_ascii=False, indent=1))
    sys.exit(1 if problems else 0)
