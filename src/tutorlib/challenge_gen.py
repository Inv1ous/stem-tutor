"""Challenge mode, the AI half: write hard calculation questions, then check each one before it is shown.

Each question passes three gates, one AI call each (about 3 calls a question when all goes well):
  generate  the chosen model writes the question, its key and a worked solution, from the allowed syllabus only
  solve     a blind solve (stem and options only) by the other model family, the only independent one: it must
            reach the key. A failed call is asked once more and is never counted as a miss
  audit     a fresh examiner call (the generator's model, no memory of writing it) maps every idea the solution uses
            to an allowed syllabus point, rates the difficulty without being told the level asked for, and flags
            ambiguity, a second correct option, missing data or a unit error
  recheck   only when the solve missed a question asked for and rated at level 8 or more: a second, careful blind
            solve by the same independent model must reach the key (the audit, shown the key, would only anchor on it)
A rejected question is written again with the reason (3 tries), then once a level easier, else the slot is skipped.
Costs are capped: MAX_CALLS_PER_QUESTION per slot, one retry after a failed call in a slot, and a set stops after
MAX_FAILS_IN_ROW failed calls in a row.
`to_item` makes the result grade-ready: the same item shape as a pack item, so grade.grade_item marks it.
No AI is called here directly: `ask(prompt, schema, model, timeout)` is injected and returns a dict, or None when the
call failed or timed out, or raises Refused when the model declined (the app raises it when Claude's message says its
safeguards flagged the request). A declined call is not a failed attempt: it is handed to the other model once, and a
question whose writing or audit both models decline is skipped. The independent solve is never handed to the
writer's own model: if the other model declines it, the question is written again. Each question records the model
that wrote it (`model`), the gates it passed (`checks`: "solve", "audit", "recheck"), its rating (`rated`) and the
level asked (`requested`).
"""
from __future__ import annotations

import asyncio
import math
import random
import re
import time

from . import grade, units
from .challenge import LEVELS

GEN_SYSTEM = """You write and check exam-style A-Level calculation questions (CAIE 9701 Chemistry, CAIE 9702 Physics, \
Edexcel IAL Mathematics) for a strong 17-year-old who wants hard problems for fun. British English. Be exact: work \
every number out carefully before you commit to it. Reply only with the JSON asked for."""

# what each level means, in features a writer can build in and an examiner can check; the names are challenge.LEVELS'
MINUTES = {6: 6, 7: 8, 8: 12, 9: 20, 10: 30}  # least time a strong student should need, from level 6 up
LEVEL_GUIDE = {
    1: "one step, one idea, data given directly",
    2: "two steps from one idea: the standard textbook calculation",
    3: "two or three steps; may need a unit conversion or a rearrangement first",
    4: "three or four steps joining two ideas: a typical full-mark exam part",
    5: "four or five steps combining two or three ideas, with one easy trap (a unit, a component, a sign): the hard "
       "end of a normal paper",
    6: "at least two independent stages feeding a final one; three syllabus ideas; the method is not signposted and "
       "an intermediate quantity the question never names must be found",
    7: "three stages; three or four ideas, one from an earlier chapter; an unfamiliar framing or a hidden constraint "
       "the student must notice (something stops, a limit is reached, a condition fixes an unknown); algebra best "
       "done symbolically before substituting",
    8: "three or four stages; four ideas from at least two chapters; a non-obvious setup is required (choosing the "
       "system or the conserved quantity, a limiting case, working backwards from a condition); an unknown must be "
       "eliminated or cancels symbolically; no step handed to the student",
    9: "olympiad-lite: four or more linked stages, an unusual insight in at least one, and a condition to be found "
       "(a maximum, a minimum, a threshold) or unknowns eliminated between simultaneous equations",
    10: "a long multi-stage problem far beyond any A-level paper: several insights, an optimisation or a "
        "self-consistent condition, heavy symbolic work; yet every step uses only the listed syllabus ideas, with no "
        "calculus or university methods unless the list contains them",
}
MAX_CALLS_PER_QUESTION = 12  # every AI call one slot may make, retries and fallbacks included (3 when all goes well)
MAX_FAILS_IN_ROW = 3  # failed or timed-out calls in a row (declines aside) that stop a whole set: the AI is not answering
# seconds per call, by level tier (1-5, 6-7, 8-10): writing a level-10 question can keep Opus busy for 14 minutes
TIMEOUTS = {"generate": {"sonnet": (300, 420, 600), "opus": (420, 600, 900)},
            "check": {"sonnet": (240, 420, 600), "opus": (240, 420, 600)}}
_SCOPE_CHARS = 9000  # past this the earlier chapters are listed by title only


class BadQuestion(ValueError):
    pass


class Refused(Exception):
    """Raised by `ask` when the model declined the request (its safeguards flagged it). Never reworded and retried
    on the same model: that one call goes to the other model instead."""


_STR = {"type": "string"}
GENERATE_SCHEMA = {
    "type": "object", "required": ["stem", "solution", "concepts"],
    "properties": {
        "working": {"type": "string", "description": "scratch work while designing the question (not shown)"},
        "stem": _STR,
        "correct": {"type": "string", "description": "MCQ only: the correct option's text"},
        "wrong": {"type": "array", "description": "MCQ only: exactly 3 wrong options",
                  "items": {"type": "object", "required": ["text", "mistake"],
                            "properties": {"text": _STR, "mistake": _STR}}},
        "value": {"type": ["number", "null"], "description": "typed only: the exact final value, unrounded"},
        "unit": {"type": "string", "description": "typed only: SI unit as '<sym> <sym>^-n', e.g. 'm s^-2', '' if none"},
        "sf": {"type": ["integer", "null"], "description": "typed only: significant figures the stem asks for"},
        "exact": {"type": "boolean", "description": "typed only: true when the answer is an exact count"},
        "expr": {"type": "string", "description": "only when told an expression answer is allowed"},
        "solution": {"type": "string", "description": "full worked solution, never naming option letters"},
        "concepts": {"type": "array", "items": _STR, "description": "allowed syllabus ids the solution uses"},
    },
}
GENERATE_MCQ_SCHEMA = {**GENERATE_SCHEMA, "required": ["stem", "correct", "wrong", "solution", "concepts"]}
SOLVE_SCHEMA = {
    "type": "object", "required": ["working", "answer"],
    "properties": {"working": _STR, "answer": {"type": "string",
                                               "description": "MCQ: one letter. Typed: the value with its unit"}},
}
AUDIT_SCHEMA = {
    "type": "object", "required": ["working", "solution_correct", "concepts", "out_of_scope", "rated_level", "problems"],
    "properties": {
        "working": {"type": "string", "description": "your own step-by-step check of the solution"},
        "solution_correct": {"type": "boolean"},
        "concepts": {"type": "array", "items": {"type": "object", "required": ["idea", "kc"],
                                                "properties": {"idea": _STR, "kc": _STR}}},
        "out_of_scope": {"type": "array", "items": _STR},
        "rated_level": {"type": "integer", "minimum": 1, "maximum": 10},
        "problems": {"type": "array", "items": _STR},
    },
}


# ---------------- prompts ----------------
def _names() -> list[str]:
    return [lv["name"] for lv in sorted(LEVELS, key=lambda lv: lv["level"])]


def _spec_of(kc: dict) -> str:
    return kc.get("spec") or kc["id"].split("-")[0]


def _maths(spec: str) -> bool:
    return not spec[:1].isdigit()  # CAIE sciences are numbers (9702); Edexcel units are P1, M1, S1…


def _course(scope: list[dict]) -> str:
    # the chosen chapters' course: a P1 prereq of a physics chapter does not make it a maths question
    specs = sorted({_spec_of(k) for k in scope if k.get("chosen")} or {_spec_of(k) for k in scope}) or ["9702"]
    names = {"9702": "CAIE 9702 Physics (g = 9.81 m s^-2, the 9702 data sheet's constants)",
             "9701": "CAIE 9701 Chemistry (the 9701 data booklet's values; Ar to the data booklet)"}
    return "; ".join(names.get(s, f"Edexcel IAL {s} (g = 9.8 m s^-2 in mechanics)") for s in specs)


def _scope_text(scope: list[dict], cfg: dict | None) -> str:
    """The allowed syllabus, one point a line: chosen chapters in full; earlier ones by title when the list is long."""
    full = [f"{k['id']} {k.get('title', '')}: {k.get('statement', '')}" for k in scope]
    if sum(map(len, full)) <= _SCOPE_CHARS or not any(_chosen(k, cfg) for k in scope):
        return "\n".join(full)
    return "\n".join(line if _chosen(k, cfg) else f"{k['id']} {k.get('title', '')}" for k, line in zip(scope, full))


def _chosen(kc: dict, cfg: dict | None) -> bool:
    """One of the chapters the set is on (challenge.allowed_scope marks them), not an earlier one."""
    return bool(kc.get("chosen")) or kc.get("subtopic") in ((cfg or {}).get("topics") or ())


def _scale() -> str:
    return "\n".join(f"  {i} {name}: {LEVEL_GUIDE[i]}" + (f" (at least {MINUTES[i]} minutes)" if i in MINUTES else "")
                     for i, name in enumerate(_names(), 1))


def generation_prompt(slot: dict, scope: list[dict], cfg: dict, earlier_stems: list[str],
                      retry_reason: str | None = None) -> str:
    level, kind = slot["level"], slot["kind"]
    names = _names()
    by_id = {k["id"]: k for k in scope}
    focus = [f"{i} {by_id[i].get('title', '')}: {by_id[i].get('statement', '')}" for i in slot.get("focus") or []
             if i in by_id]
    expr_ok = kind == "typed" and (cfg or {}).get("maths_forms") and any(_maths(_spec_of(k)) for k in scope)
    if kind == "mcq":
        form = ("Multiple choice: give the correct option's text as `correct` and exactly 3 wrong options as `wrong`, "
                "each built from a realistic mistake (wrong formula, unit or prefix slip, factor of 2, forgot to square, "
                "wrong component, sign error) with the mistake named. All 4 options in the same format and units, all "
                "plausible, all different; exactly one correct. Never write option letters anywhere: refer to options "
                "by their values.")
    else:
        form = ("Typed answer, no options and so no hints: the stem asks for one exact final value. Give `value` "
                "(unrounded), `unit` ('' for a plain number) and `sf`; the stem must end by saying the unit and the "
                "precision, e.g. 'Give your answer in J to 3 significant figures.' Use `exact: true` only for an exact "
                "count.")
        if expr_ok:
            form += " Here an algebraic answer is also allowed: then give `expr` (plain maths, x^2, sin x) and no value."
    lines = [
        f"Write one challenge question [slot {slot['n']}] for {_course(scope)}.",
        f"Difficulty: level {level} of 10, {names[level - 1]}: {LEVEL_GUIDE[level]}"
        + (f"; a strong student needs at least {MINUTES[level]} minutes." if level in MINUTES else "."),
        "",
        "ALLOWED KNOWLEDGE. The question must be solvable using only these syllabus points plus basic arithmetic and "
        "algebra. List in `concepts` the ids the solution uses:",
        _scope_text(scope, cfg),
        *(["", "REQUIRED: the question must be built on these points (earlier ideas from the list above may join "
                "them); list all of them in `concepts`:", *focus] if focus else []),
        "",
        "Rules:",
        "- Calculation only: the student must compute a result. Never ask them to explain, describe, design or plan "
        "an experiment, or recall a definition.",
        "- One well-defined final answer; no ambiguity, no trick wording; all data in the stem, including every "
        "constant the solution uses (e.g. 'Take g = 9.81 m s^-2').",
        "- No figure or graph: describe every arrangement fully in words.",
        "- Use that course's conventions and constants; SI units written like 'm s^-2', 'kJ mol^-1'.",
        "- Choose numbers that give a clean-ish answer, and check the arithmetic twice.",
        "- `solution`: the full worked solution, step by step, ending with the final answer.",
        f"- {form}",
    ]
    if level in MINUTES:
        lines.append(f"- Self-check before answering (in `working`): estimate how many exam marks this is worth and "
                     f"what share of strong A-level students would solve it. If a strong student would finish it in "
                     f"under {MINUTES[level]} minutes it is too easy for level {level}: make it harder. Never split it "
                     f"into guided parts or hint at the method.")
    if earlier_stems:
        lines += ["", "Already in this set; use a different situation and wording:"]
        lines += [f"- {' '.join(s.split())[:200]}" for s in earlier_stems[-10:]]
    if retry_reason:
        lines += ["", f"Your previous attempt was rejected: {retry_reason}. Write a new question that avoids this."]
    return "\n".join(lines)


def _shown(question: dict) -> str:
    it = question["item"]
    lines = [it["stem"]]
    if it["kind"] == "mcq":
        lines += [f"{k}) {v}" for k, v in sorted(it["options"].items())]
    return "\n".join(lines)


def solve_prompt(question: dict, careful: bool = False) -> str:
    """The question as the student sees it, never its key or solution. `careful` asks for the second blind solve of a
    hard question the first solver missed."""
    it = question["item"]
    how = ("Answer with the single letter of the correct option." if it["kind"] == "mcq" else
           "Answer with the final value and its unit as you would type it, e.g. '4.52e-3 mol dm^-3'."
           if it["kind"] == "numeric" else "Answer with the final expression in plain maths, e.g. 3x^2 + 2.")
    care = (" Take your time: it may need an unusual insight. Check your result by a second route before answering."
            if careful else "")
    return f"Solve this question. Work it out fully in `working`, then give `answer`. {how}{care}\n\n{_shown(question)}"


def _key_text(question: dict) -> str:
    it, a = question["item"], question["item"]["answer"]
    if it["kind"] == "mcq":
        return it["options"][a]
    if it["kind"] == "expression":
        return a["expr"]
    shown = f"{a['value']:.{a['sf']}g}" if a.get("sf") else f"{a['value']:.6g}"
    full = f" (unrounded {a['value']:.6g}, kept for marking)" if a.get("sf") and shown != f"{a['value']:.6g}" else ""
    return f"{shown} {a.get('unit', '')}".strip() + full


def audit_prompt(question: dict, scope: list[dict], cfg: dict | None = None) -> str:
    return "\n".join([
        "You are an independent senior examiner checking a challenge question before a student sees it.",
        "", "QUESTION:", _shown(question), "", f"KEY: {_key_text(question)}", "",
        "WORKED SOLUTION:", question["solution"], "",
        "ALLOWED SYLLABUS (with basic arithmetic and algebra):", _scope_text(scope, cfg), "",
        "1. Redo the solution step by step in `working`; `solution_correct` is true only if the key is right.",
        "2. `concepts`: every idea the solution needs, each mapped to an allowed id above, or to 'basic' for plain "
        "arithmetic/algebra. Put any idea that is neither in `out_of_scope` (and map it to its own syllabus id if it "
        "has one).",
        "3. `rated_level`: how hard this is for a strong A-level student, judged by the features it really has "
        "(count the stages and ideas; a long but routine chain is not hard):", _scale(),
        "4. `problems`: only defects that must be fixed before a student sees it: ambiguity, more than one correct "
        "option, no correct option, missing data, unit or arithmetic errors, trick wording, a figure needed, not a "
        "calculation. Not remarks: a standard A-level simplification, unused data or deliberate difficulty is no "
        "problem. Empty if none.",
    ])


# ---------------- normalising the model's question ----------------
_FIGURE = re.compile(r"\b(diagram|figure|graph|fig\.)\b[^.]{0,40}\b(below|above|shown)\b|\bshown (below|above)\b", re.I)
_NOT_CALC = re.compile(r"(?:^|[.?!]\s+)(explain|describe|discuss|design|plan|outline|sketch|draw|suggest)\b", re.I)
_LETTER = re.compile(r"\b(option|choice|answer)\s+(is\s+)?\(?[A-D]\)?(?!\w)|\([A-D]\)\s+(is|would|must)\b|^\s*[A-D]\)",
                     re.M)


def _id(slot: dict, rng: random.Random) -> str:
    return f"ch-{slot['n']}-{rng.getrandbits(24):06x}"


def _concepts(raw: dict, scope: list[dict]) -> list[str]:
    ids = {k["id"] for k in scope}
    got = [c.strip() for c in raw.get("concepts") or [] if isinstance(c, str) and c.strip()]
    got = [c for c in dict.fromkeys(got) if not c.lower().startswith("basic")]
    if not got:
        raise BadQuestion("no syllabus concepts listed")
    if outside := [c for c in got if c not in ids]:
        raise BadQuestion(f"concepts outside the allowed syllabus: {', '.join(outside)}")
    return got


def _quantity(text: str):
    try:
        value, unit, _ = grade.parse_quantity(text)
        return value, unit
    except grade.ParseError:
        return None


def to_item(raw: dict, slot: dict, scope: list[dict], rng: random.Random | None = None, cfg: dict | None = None) -> dict:
    """The model's JSON as a question {n, level, kind, item, solution, concepts}, its item grade-ready; else
    BadQuestion(reason)."""
    rng = rng or random.Random()
    if not isinstance(raw, dict):
        raise BadQuestion("no question returned")
    stem = str(raw.get("stem") or "").strip()
    if len(stem) < 40:
        raise BadQuestion("stem too short")
    if _FIGURE.search(stem):
        raise BadQuestion("needs a figure")
    if _NOT_CALC.search(stem):
        raise BadQuestion("not a calculation")
    solution = str(raw.get("solution") or "").strip()
    if not solution:
        raise BadQuestion("worked solution missing")
    if _LETTER.search(solution):
        raise BadQuestion("the solution names option letters")
    concepts = _concepts(raw, scope)
    if missing := [f for f in slot.get("focus") or [] if f not in concepts]:
        raise BadQuestion(f"does not use the required focus: {', '.join(missing)}")
    kcs = sorted(concepts, key=lambda c: not next((_chosen(k, cfg) for k in scope if k["id"] == c), False))
    item = {"id": _id(slot, rng), "kind": "", "kcs": kcs, "stem": stem}
    if slot["kind"] == "mcq":
        correct = " ".join(str(raw.get("correct") or "").split())
        if not correct:
            raise BadQuestion("correct option missing")
        wrong = [" ".join(str(w.get("text") if isinstance(w, dict) else w or "").split()) for w in raw.get("wrong") or []]
        if len(wrong) != 3 or not all(wrong):
            raise BadQuestion("needs exactly 3 wrong options")
        options = [correct, *wrong]
        if len({o.casefold() for o in options}) < 4:
            raise BadQuestion("options are not distinct")
        if (key := _quantity(correct)) is not None:
            others = [_quantity(w) for w in wrong]
            if any(o is None or o[1] != key[1] for o in others):
                raise BadQuestion("options not in the same format")
            if any(math.isclose(o[0], key[0], rel_tol=0.02) for o in others):
                raise BadQuestion("options are not distinct: a wrong value equals the key")
        rng.shuffle(options)
        item.update(kind="mcq", options=dict(zip("ABCD", options)), answer="ABCD"[options.index(correct)])
    else:
        spec_maths = any(_maths(_spec_of(k)) for k in scope if k["id"] in concepts)
        if raw.get("value") is None and raw.get("expr") and (cfg or {}).get("maths_forms") and spec_maths:
            try:
                grade._sympy()[1](raw["expr"])
            except Exception:  # noqa: BLE001 - any parse failure means an unusable key
                raise BadQuestion("expression does not parse") from None
            item.update(kind="expression", answer={"expr": str(raw["expr"]).strip()})
        else:
            value, unit, sf, exact = raw.get("value"), str(raw.get("unit") or "").strip(), raw.get("sf"), \
                bool(raw.get("exact"))
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise BadQuestion("typed answer needs a finite numeric value")
            if unit:
                try:
                    units.parse_unit(unit)
                except (ValueError, ArithmeticError):
                    raise BadQuestion(f"unit {unit!r} does not parse") from None
            answer = {"value": float(value), **({"unit": unit} if unit else {})}
            if exact:
                answer["exact"] = True
            elif isinstance(sf, int) and not isinstance(sf, bool) and 1 <= sf <= 6:
                answer["sf"] = sf
                if not grade._STATES_FIGURES.search(stem):
                    item["stem"] = f"{stem} Give your answer{f' in {unit}' if unit else ''} to {sf} significant figures."
            else:
                raise BadQuestion(f"s.f. {sf!r} is not 1 to 6")
            item.update(kind="numeric", answer=answer)
    item["explanation"] = solution
    item = {k: item[k] for k in ("id", "kind", "kcs", "stem", "options", "answer", "explanation") if k in item}
    return {"n": slot["n"], "level": slot["level"], "kind": slot["kind"], "item": item, "solution": solution,
            "concepts": concepts, "focus": list(slot.get("focus") or [])}


# ---------------- gates ----------------
def agrees(question: dict, solved: dict | None) -> bool:
    """The blind solve reaches the key, as the real marking would judge it (value right; units converted; within the
    marking tolerance). A missing unit or the wrong number of figures still agrees: the value is what is checked."""
    it = question["item"]
    said = str((solved or {}).get("answer") or "").strip()
    if not said:
        return False
    if it["kind"] == "mcq":
        letter = re.sub(r"[^A-Za-z]", "", said)
        letter = letter.upper() if len(letter) == 1 else (m[1] if (m := re.search(r"\b([A-D])\b", said)) else "")
        return letter == it["answer"]
    return bool(grade.grade_item(it, {"kind": "value", "value": said, "conf": None})["correct"])


def _audit_failure(audit: dict, question: dict, scope_ids: set[str]) -> str | None:
    if not isinstance(audit, dict):
        return "the audit failed"
    if audit.get("problems"):
        return "the examiner found problems: " + "; ".join(map(str, audit["problems"]))[:300]
    if not audit.get("solution_correct"):
        return "the examiner found the worked solution or key wrong"
    outside = [str(c) for c in audit.get("out_of_scope") or []]
    outside += [str(c.get("kc")) for c in audit.get("concepts") or [] if isinstance(c, dict)
                and str(c.get("kc")) not in scope_ids and not str(c.get("kc")).lower().startswith("basic")]
    if outside:
        return "uses ideas outside the allowed syllabus: " + ", ".join(dict.fromkeys(outside))
    if not isinstance(audit.get("rated_level"), int):
        return "the audit gave no difficulty"
    return None


def _level_gap(rated: int, level: int) -> str | None:
    """Why the rated difficulty is outside the band for the level asked: at 7 and above no more than one level easier
    (the top levels ran low), below that two either way."""
    if rated < level - (1 if level >= 7 else 2):
        return f"too easy (rated level {rated}, wanted {level}): make it substantially harder"
    if rated > level + 2:
        return f"too hard (rated level {rated}, wanted {level}): make it easier"
    return None


def call_name(schema: dict) -> str:
    """Which gate a schema belongs to: generate, solve or audit."""
    props = schema.get("properties") or {}
    return "audit" if "rated_level" in props else "generate" if "stem" in props else "solve"


class _Stop(Exception):
    """Ends a slot at once: the AI is not answering, the slot's call limit is spent, or the set was cancelled."""


def timeout_for(call: str, model: str, level: int) -> float:
    """Seconds allowed for one call: writing gets more than solving or auditing, and harder levels more than easy."""
    times = TIMEOUTS["generate" if call == "generate" else "check"].get(model, TIMEOUTS["generate"]["sonnet"])
    return times[0 if level <= 5 else 1 if level <= 7 else 2]


def _other(model: str) -> str:
    return "sonnet" if model == "opus" else "opus"


async def _call(ask, prompt: str, schema: dict, model: str, level: int):
    """One call; a failed or timed-out one returns None and is asked again at most once (by _blind, or as the next
    try with a new prompt), then the slot gives up."""
    return await ask(prompt, schema, model, timeout_for(call_name(schema), model, level))


def _declined(slot: dict, call: str, model: str, to: str | None, log: list, fallbacks: list) -> None:
    fallbacks.append({"n": slot["n"], "call": call, "declined": model, "to": to})
    log.append(f"Q{slot['n']} {call}: {model} declined" + (f"; asking {to}" if to else "; no other model may do it"))


async def _either(ask, prompt: str, schema: dict, first: str, slot: dict, log: list, fallbacks: list):
    """(reply, model that answered). A model that declines hands this one call to the other model, once, as its
    error advises; never the same model again. Raises Refused when both decline."""
    for model in (first, _other(first)):
        try:
            return await _call(ask, prompt, schema, model, slot["level"]), model
        except Refused:
            _declined(slot, call_name(schema), model, _other(model) if model == first else None, log, fallbacks)
    raise Refused("declined by both models")


async def _blind(ask, question: dict, model: str, careful: bool = False) -> dict | None:
    """A blind solve (stem and options only) by `model`, the one model independent of the writer. A failed call is
    asked once more; Refused passes up: no other model may stand in."""
    prompt, level = solve_prompt(question, careful), question["level"]
    return await _call(ask, prompt, SOLVE_SCHEMA, model, level) or await _call(ask, prompt, SOLVE_SCHEMA, model, level)


async def _attempt(ask, slot, scope, cfg, earlier_stems, reason, rng, gen, log, fallbacks):
    """One try at a slot: (question or None, outcome or rejection reason, generator model that answered, candidate).
    A candidate passed every gate but the difficulty band. Raises Refused when both models decline to write it or to
    audit it.

    The key is trusted only on a blind solve by the model that did not write it: never on the writer's own model,
    which would agree with itself. A miss is allowed only when both the level asked and the audit's rating are 8 or
    more, and then a second, careful blind solve by that independent model must reach the key."""
    schema = GENERATE_MCQ_SCHEMA if slot["kind"] == "mcq" else GENERATE_SCHEMA  # an MCQ must come with its options
    raw, gen = await _either(ask, generation_prompt(slot, scope, cfg, earlier_stems, reason), schema, gen, slot, log,
                             fallbacks)
    if raw is None:
        return None, "the AI call failed or timed out", gen, None
    try:
        q = to_item(raw, slot, scope, rng, cfg)
    except BadQuestion as e:
        return None, str(e), gen, None
    q["model"], judge = gen, _other(gen)
    try:
        solved = await _blind(ask, q, judge)
    except Refused:
        _declined(slot, "solve", judge, None, log, fallbacks)
        return None, f"no independent check: {judge} declined to solve it", gen, None
    missed = not agrees(q, solved)
    if missed and slot["level"] < 8:
        said = str((solved or {}).get("answer") or "no answer")[:60]
        return None, f"an independent solver's answer ({said}) did not match the key ({_key_text(q)})", gen, None
    audit, _ = await _either(ask, audit_prompt(q, scope, cfg), AUDIT_SCHEMA, gen, slot, log, fallbacks)
    if (why := _audit_failure(audit, q, {k["id"] for k in scope})):
        return None, why + (" (and the solver missed it too)" if missed else ""), gen, None
    q["rated"], checks = audit["rated_level"], ["audit"] if missed else ["solve", "audit"]
    if missed:
        if q["rated"] < 8:
            return None, (f"the independent solver missed the key ({_key_text(q)}) and the question was rated only "
                          f"level {q['rated']}"), gen, None
        try:
            again = await _blind(ask, q, judge, careful=True)
        except Refused:
            _declined(slot, "recheck", judge, None, log, fallbacks)
            return None, f"no independent check: {judge} declined the second blind solve", gen, None
        if not agrees(q, again):
            return None, f"two independent blind solves missed the key ({_key_text(q)})", gen, None
        q["solver_missed"] = True
        checks.append("recheck")
    q["checks"] = checks
    if (gap := _level_gap(q["rated"], slot["level"])):
        return None, gap, gen, q
    return q, f"accepted (rated L{q['rated']}{', first solve missed, second agreed' if missed else ''})", gen, None


async def make_question(ask, slot: dict, scope: list[dict], cfg: dict, earlier_stems: list[str], log: list[str],
                        cancelled=lambda: False, rng: random.Random | None = None,
                        fallbacks: list | None = None) -> dict | None:
    """A checked question for `slot`, or None after 3 tries and one a level easier. Each try adds a line to `log`;
    each call a model declined adds an entry to `fallbacks`. A slot both models decline is skipped at once; so is one
    whose AI calls fail twice (one retry after a failure), or that would pass MAX_CALLS_PER_QUESTION.
    A try that passed every gate but the difficulty band is kept: when no try lands in the band, the one rated
    closest to the level asked is used, before the easier try if it is no more than 2 levels easier, and one further
    off only when nothing else came through; it then carries the level it really is (`level`, the lower of the level
    asked and its rating), with the level asked in `requested`."""
    rng, fallbacks = rng or random.Random(), [] if fallbacks is None else fallbacks
    tries = [slot] * 3 + ([{**slot, "level": slot["level"] - 1}] if slot["level"] > 1 else [])
    reason, gen, best, state = None, cfg.get("model", "sonnet"), None, {"calls": 0, "fails": 0}

    def off(c):  # more than two levels easier is the last resort; then the nearest
        return c["rated"] < slot["level"] - 2, abs(c["rated"] - slot["level"])

    async def counted(prompt, schema, model, timeout=120):
        if cancelled():
            raise _Stop("cancelled")
        if state["calls"] >= MAX_CALLS_PER_QUESTION:
            raise _Stop("call limit reached")
        state["calls"] += 1
        try:
            reply = await ask(prompt, schema, model, timeout)
        except (asyncio.CancelledError, Refused):
            raise
        except Exception:  # noqa: BLE001 - a failed AI call is a failed call, never a crash
            reply = None
        if reply is None:
            state["fails"] += 1
            if state["fails"] >= 2:
                raise _Stop("AI not responding")
        return reply

    for k, s in enumerate(tries, 1):
        if cancelled() or (s is not slot and best and not off(best)[0]):
            break  # stopped; or a near-enough question beats an easier one
        t0, before = time.monotonic(), state["calls"]
        try:
            q, outcome, gen, cand = await _attempt(counted, s, scope, cfg, list(earlier_stems), reason, rng, gen,
                                                   log, fallbacks)
        except Refused:
            q, outcome, cand = None, "declined by the models", None
        except _Stop as e:
            q, outcome, cand = None, str(e), None
        easier = " (easier)" if s is not slot else ""
        used = state["calls"] - before
        log.append(f"Q{slot['n']} L{s['level']} {slot['kind']} try {k}{easier}: {outcome} "
                   f"[{used} call{'s' * (used != 1)}, {time.monotonic() - t0:.0f}s]")
        if q:
            return {**q, "requested": slot["level"]}
        if cand and (best is None or off(cand) < off(best)):
            best = cand
        if outcome in ("declined by the models", "AI not responding", "call limit reached", "cancelled"):
            break
        reason = outcome
    if best:
        log.append(f"Q{slot['n']} L{slot['level']} {slot['kind']}: kept the closest try (rated L{best['rated']})")
        return {**best, "level": min(slot["level"], best["rated"]), "requested": slot["level"]}
    return None


def _fallback_summary(fallbacks: list[dict]) -> dict:
    """{"count", "declined": {model: calls}, "note"} for the UI, e.g. 'Opus declined 3 questions; Sonnet wrote them
    instead.'"""
    declined: dict[str, int] = {}
    for f in fallbacks:
        declined[f["declined"]] = declined.get(f["declined"], 0) + 1
    notes = []
    for model in sorted(declined):
        mine = [f for f in fallbacks if f["declined"] == model]
        wrote = sum(f["call"] == "generate" and f.get("to") is not None for f in mine)
        checked = sum(f["call"] != "generate" and f.get("to") is not None for f in mine)
        alone = len(mine) - wrote - checked
        if wrote:
            notes.append(f"{model.title()} declined {wrote} question{'s' * (wrote != 1)}; "
                         f"{_other(model).title()} wrote {'them' if wrote != 1 else 'it'} instead.")
        if checked:
            notes.append(f"{model.title()} declined {checked} check{'s' * (checked != 1)}; "
                         f"{_other(model).title()} did {'them' if checked != 1 else 'it'} instead.")
        if alone:
            notes.append(f"{model.title()} declined {alone} check{'s' * (alone != 1)} no other model could do, so "
                         f"{'those questions were' if alone != 1 else 'that question was'} written again.")
    return {"count": len(fallbacks), "declined": declined, "note": " ".join(notes)}


def plan_focus(slots: list[dict], scope: list[dict], cfg: dict | None = None, seed=None) -> dict[int, list[str]]:
    """The required ideas for each slot, {n: [kc ids]}: 1 at levels 1-3, 2 at 4-7, 3 from 8, drawn from the chosen
    chapters in a seeded rotation, so none repeats until all have been used; from level 8 they come from different
    subtopics where the chosen chapters allow."""
    source = [k for k in scope if _chosen(k, cfg)] or list(scope)
    rng, pool, out = random.Random(f"focus-{seed}"), [], {}
    for slot in slots:
        want = min(len(source), 1 if slot["level"] <= 3 else 2 if slot["level"] <= 7 else 3)
        picked: list[dict] = []
        while len(picked) < want:
            fresh = [i for i, k in enumerate(pool) if k not in picked]
            if not fresh:
                pool += rng.sample(source, len(source))
                continue
            seen = {k["subtopic"] for k in picked} if slot["level"] >= 8 else set()
            picked.append(pool.pop(next((i for i in fresh if pool[i]["subtopic"] not in seen), fresh[0])))
        out[slot["n"]] = [k["id"] for k in picked]
    return out


async def generate_set(ask, cfg: dict, scope: list[dict], on_progress=None, cancelled=lambda: False, parallel: int = 3,
                       seed=None) -> dict:
    """Write and check a whole set: {"questions" (in order, numbered 1..k), "skipped", "log", "fallbacks", "calls"
    (AI calls made, declined ones included)}. Never raises on AI failure; a set may come back shorter than asked.
    After MAX_FAILS_IN_ROW failed or timed-out calls in a row the set stops; what is left is skipped as
    'AI not responding'."""
    from . import challenge
    slots = challenge.plan_slots(cfg, seed)
    focus = plan_focus(slots, scope, cfg, seed)
    slots = [{**s, "focus": focus[s["n"]]} for s in slots]
    sem, stems, log, done, fallbacks = asyncio.Semaphore(max(1, parallel)), [], [], [0], []
    got: dict[int, dict] = {}
    skipped: list[dict] = []
    state = {"calls": 0, "fails": 0, "stopped": False}

    async def watched(prompt, schema, model, timeout=120):
        state["calls"] += 1
        try:
            reply = await ask(prompt, schema, model, timeout)
        except (asyncio.CancelledError, Refused):
            raise
        except Exception:  # noqa: BLE001 - counted as a failed call; make_question turns it into None
            reply = None
        state["fails"] = state["fails"] + 1 if reply is None else 0
        state["stopped"] |= state["fails"] >= MAX_FAILS_IN_ROW
        return reply

    def stop():
        return cancelled() or state["stopped"]

    async def one(slot):
        async with sem:
            reason = "cancelled"
            if not stop():
                rng = random.Random(f"{seed}-{slot['n']}") if seed is not None else None
                start = len(log)
                q = await make_question(watched, slot, scope, cfg, stems, log, stop, rng, fallbacks)
                if q:
                    got[slot["n"]] = q
                    stems.append(q["item"]["stem"])
                else:
                    mine = [line for line in log[start:] if line.startswith(f"Q{slot['n']} L")]
                    reason = "cancelled" if cancelled() and not mine else (
                        mine[-1].split(": ", 1)[-1].rsplit(" [", 1)[0] if mine else "no question")
            if slot["n"] not in got and state["stopped"]:
                reason = "AI not responding"
            if slot["n"] not in got:
                skipped.append({"n": slot["n"], "level": slot["level"], "kind": slot["kind"], "reason": reason})
            done[0] += 1
            if on_progress:
                on_progress(done[0], len(slots), f"Q{slot['n']} {'ready' if slot['n'] in got else 'skipped'}")

    await asyncio.gather(*(one(s) for s in slots))
    questions = [{**got[n], "n": i} for i, n in enumerate(sorted(got), 1)]
    return {"questions": questions, "skipped": sorted(skipped, key=lambda s: s["n"]), "log": log,
            "fallbacks": _fallback_summary(fallbacks), "calls": state["calls"]}
