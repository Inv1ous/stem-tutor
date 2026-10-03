"""Deterministic teaching policy: which method, which KCs, in what order.

Default method table encodes the evidence (expertise reversal, refutation for misconceptions,
pretesting for novices on conceptual material). Personal experiments override it per KC.
"""
from __future__ import annotations

import math
import re
from datetime import date, datetime

from . import experiments, model

METHOD_PHASES = {
    "worked_faded": ["lesson", "worked", "faded", "practice"],
    "pretest_explain": ["lesson", "worked", "practice"],
    "problem_first": ["challenge", "lesson", "worked", "practice"],
    "refutation": ["refute", "probe", "practice"],
}

METHOD_CARDS = {
    "worked_faded": [
        "Teach the core idea from `outline` in at most 120 words, then ask ONE check question and wait.",
        "Worked example: reveal one step per turn (what + why). Before revealing step 2 onward, ask them to say the next step.",
        "Faded problem: they attempt it in full. No hints unless they ask.",
        "If the faded answer is wrong, walk through from their first wrong step; they do each step.",
    ],
    "pretest_explain": [
        "Say which pretest ideas were off (not the answers). Their errors tell you what to target.",
        "Teach the core idea from `outline` in at most 150 words, contrasting it with each listed misconception.",
        "Ask them to explain it back in one sentence. Correct precisely; praise only what is right.",
        "Worked example: narrate why each step, then move to practice.",
    ],
    "problem_first": [
        "The challenge is attempted cold: no hints. Ask for any approach, even partial; that struggle is the point.",
        "Compare their attempt with the canonical method: name what was right in theirs, then the missing idea.",
        "Teach the core idea from `outline` briefly, show the worked example quickly, then practice.",
    ],
    "refutation": [
        "State the misconception neutrally ('a common idea is ...') before anything else.",
        "Explain why it fails (refutation), then give the contrasting case.",
        "Ask them to predict a case where the misconception and the correct idea give different answers.",
        "Then the probe questions: their choices show whether the old idea is gone.",
    ],
}


def current_week(plan: dict, now: datetime) -> int:
    start = date.fromisoformat(plan.get("start", "2026-09-01"))
    mon2 = date.fromisoformat(plan.get("week2_monday", "2026-09-07"))
    today = now.date()
    if today < mon2:
        return 1 if today >= start else 0
    return 2 + (today - mon2).days // 7


# ---------------- ticks in the Almanac ----------------
def is_done(objective: dict, state: dict, ticked: frozenset = frozenset()) -> bool:
    """Ticked in the Almanac, or every idea in it is secure here."""
    kcs = objective.get("kcs", [])
    return objective.get("id") in ticked or (bool(kcs) and all(
        kc in state["kcs"] and model.is_mastered(state["kcs"][kc]) for kc in kcs))


def focus_week(plan: dict, state: dict, ticked: frozenset, now: datetime) -> int:
    """The week to show: the calendar's, or once everything in it is done, the next week with something left."""
    week = current_week(plan, now)
    for w in sorted(int(w) for w in plan.get("weeks", {})):
        if w >= week and not all(is_done(o, state, ticked) for o in plan["weeks"][str(w)]):
            return w
    return week


def claimed(plan: dict, ticked: frozenset) -> list[str]:
    """Ideas of the objectives ticked in the Almanac, in week order: learned elsewhere, so checked here rather than
    taught. A tick covers the syllabus section the objective refers to, not ideas the tutor attached to it from a
    section the planner never scheduled (`outside`)."""
    out: list[str] = []
    for w in sorted(plan.get("weeks", {}), key=int) if ticked else []:
        for o in plan["weeks"][w]:
            if o.get("id") in ticked:
                out += [k for k in o.get("kcs", []) if k not in o.get("outside", []) and k not in out]
    return out


_WEEKS = re.compile(r"\bweeks?\s+(\d+)(?:\s*[-–]\s*(\d+))?", re.I)
_PHASE_GATE = re.compile(r"\bPhase\s+([IVX]+)\s+gate", re.I)
_NEED = re.compile(r"≥\s*(\d+)\s*/\s*(\d+)|≥\s*(\d+)(?:-\d+)?\s*%")


def about(objective: dict, plan: dict) -> list[str]:
    """The ideas an objective is about: its own, or for a review, check or gate that names weeks ("D28 review of week
    1 content", "check of weeks 1-3") or a phase ("Phase I gate"), the ideas first taught in those weeks."""
    own = [k for k in objective.get("kcs", []) if k not in objective.get("outside", [])]
    title, span = objective.get("title", ""), None
    if own:
        return own
    if (m := _WEEKS.search(title)):
        span = (int(m[1]), int(m[2] or m[1]))
    elif (m := _PHASE_GATE.search(title)):
        span = next(((p["from"], p["to"]) for p in plan.get("phases", []) if p.get("n") == m[1].upper()), None)
    out: list[str] = []
    for w in range(span[0], span[1] + 1) if span else []:
        for o in plan.get("weeks", {}).get(str(w), []):
            if o.get("type", "NEW") == "NEW":
                out += [k for k in o.get("kcs", []) if k not in o.get("outside", []) and k not in out]
    return out


def earned(plan: dict, state: dict, packs) -> frozenset:
    """Objectives the learner has finished here, by what their answers show; the tutor ticks these in the Almanac.
    Learning an objective counts once each of its ideas has been answered right without help. A review, check or gate
    counts when the ideas it covers are secure (right on two different days): all of them, or in every subject the
    share its "done when" line asks for. What the tutor cannot see into (practicals, paper routines, anything that
    names no ideas) is left to the learner's own tick."""
    out = set()
    for objectives in plan.get("weeks", {}).values():
        for o in objectives:
            kcs = [k for k in about(o, plan) if k in packs.kcs]
            if not o.get("id") or not kcs:
                continue
            if o.get("type", "NEW") == "NEW":
                done = all(state["kcs"].get(k, {}).get("succ_days") for k in kcs)
            else:
                m = _NEED.search(o.get("done", ""))
                need = min(1.0, max(0.5, int(m[1]) / int(m[2]) if m[1] else int(m[3]) / 100)) if m else 1.0
                subjects: dict[str, list[bool]] = {}
                for k in kcs:
                    subjects.setdefault(packs.kc(k)["subject"], []).append(
                        k in state["kcs"] and model.is_mastered(state["kcs"][k]))
                done = all(sum(secure) >= need * len(secure) for secure in subjects.values())
            if done:
                out.add(o["id"])
    return frozenset(out)


def rag(state: dict, packs, claimed_kcs=()) -> dict[str, str]:
    """A colour for every topic in the Almanac's syllabus section (each CAIE topic, each maths unit), from what the
    answers show. Green: at least 80% of the topic's ideas are secure. Red: nothing in it has been shown yet and
    nothing ticked, or most of what was tried is going wrong. Amber: between (under way, or ticked but unchecked)."""
    topics: dict[str, list[str]] = {}
    for kc, meta in packs.kcs.items():
        key = (f"{meta['subject']}-{meta['subtopic'].split('-')[1].split('.')[0]}"
               if meta["subject"] in ("chem", "phys") else f"math-{meta['spec']}")
        topics.setdefault(key, []).append(kc)
    claimed_kcs, out = set(claimed_kcs), {}
    for key, kcs in topics.items():
        tried = [kc for kc in kcs if state["kcs"].get(kc, {}).get("n")]
        secure = sum(model.is_mastered(state["kcs"][kc]) for kc in tried)
        wrong = sum(1 for kc in tried if kc in state["gaps"] or state["kcs"][kc]["active_misconceptions"]
                    or not state["kcs"][kc]["succ_days"])
        if secure >= 0.8 * len(kcs):
            out[key] = "g"
        elif (not tried and not claimed_kcs.intersection(kcs)) or wrong > len(tried) / 2:
            out[key] = "r"
        else:
            out[key] = "a"
    return out


def default_method(kc_meta: dict, kc_state: dict, fresh: bool = False) -> str:
    """`fresh`: KC never taught before this block, so pretest misconceptions are handled inside teaching."""
    if kc_state.get("active_misconceptions") and not fresh:
        return "refutation"
    if kc_state.get("theta", 0.0) >= 0.5:
        return "problem_first"
    return "worked_faded" if kc_meta.get("type") == "procedural" else "pretest_explain"


def choose_method(state: dict, packs, kc: str, rng, fresh: bool = False) -> tuple[str, dict | None]:
    meta, ks = packs.kc(kc), state["kcs"].get(kc, {})
    if fresh or not ks.get("active_misconceptions"):
        act = experiments.active(state, meta["subject"])
        if act:
            name, exp = act
            already = any(kc in p["arms"] for p in exp["pairs"])
            if not already and experiments.eligible(exp, meta, ks):
                a = experiments.assign(state, name, kc, rng)
                return a["arm"], {"exp": name, "kc": kc, **a}
        return experiments.preferred(state, meta, ks, default_method(meta, ks, fresh)), None
    return default_method(meta, ks, fresh), None


# ---------------- session planning ----------------
def _introduced(state: dict, kc: str) -> bool:
    return state["kcs"].get(kc, {}).get("n", 0) > 0


def new_kcs(state: dict, packs, limit: int, ticked: frozenset = frozenset()) -> list[str]:
    """Ideas to teach next: the Almanac's NEW objectives in week order, as far ahead of the calendar as the learner
    has got. Ideas of a ticked objective are not taught: they are checked (`to_check`)."""
    known = set(claimed(packs.plan, ticked))
    ordered: list[str] = []
    for w in sorted(packs.plan.get("weeks", {}), key=int):
        for obj in sorted(packs.plan["weeks"][w], key=lambda o: str(o.get("priority", "A"))[:1]):  # A, then B, then C
            if obj.get("type", "NEW") == "NEW":
                ordered.extend(obj.get("kcs", []))
    out: list[str] = []

    def add(kc: str, depth: int = 0):
        if kc in out or kc in known or kc not in packs.kcs or _introduced(state, kc) or depth > 6:
            return
        for p in packs.kc(kc).get("prereqs", []):
            add(p, depth + 1)
        if not packs.items_for(kc):
            return
        out.append(kc)

    for kc in ordered:
        if len(out) >= limit:
            break
        add(kc)
    return out[:limit]


def to_check(state: dict, packs, ticked: frozenset) -> list[str]:
    """Ideas ticked in the Almanac that have never been answered here and have questions."""
    return [kc for kc in claimed(packs.plan, ticked)
            if kc in packs.kcs and not _introduced(state, kc) and packs.items_for(kc)]


def missing_packs(packs, now: datetime) -> list[str]:
    week = current_week(packs.plan, now)
    missing = set()
    for w, objs in packs.plan.get("weeks", {}).items():
        if int(w) <= week + 2:
            for obj in objs:
                for kc in obj.get("kcs", []):
                    if kc in packs.kcs and not packs.items_for(kc):
                        missing.add(packs.kc(kc)["subtopic"])
    return sorted(missing)


# ---------------- exams and review priority ----------------
AS_2027, A2_2028 = date(2027, 5, 15), date(2028, 5, 15)  # estimates when the planner has no paper date


def exam_date(packs, kc: str) -> date:
    """When this idea is next examined: the planner's paper date, else an estimate from the unit/level."""
    k = packs.kc(kc)
    spec, plan = k["spec"], packs.plan or {}
    for label, d in (plan.get("sittings") or {}).items():
        if label.split(" ")[0] == spec and d:
            return date.fromisoformat(d)
    for paper in plan.get("papers") or []:
        if paper.get("short") == spec and paper.get("date"):
            return date.fromisoformat(paper["date"])
    if spec in (plan.get("sitting_2027_units") or []):
        return AS_2027
    if spec.isdigit():  # CAIE: AS ideas are examined in 2027, A2 ideas in 2028
        return AS_2027 if k.get("level", "AS") == "AS" else A2_2028
    return A2_2028


def target_retention(state: dict, packs, kc: str, now: datetime) -> float:
    """Aim higher as the exam gets close (more reviews, better recall on the day), lower when it is far away."""
    base = model.knobs(state)["desired_retention"].get(packs.kc(kc).get("subject"), 0.9)
    days = (exam_date(packs, kc) - now.date()).days
    boost = 0.05 if days <= 14 else 0.03 if days <= 42 else 0.01 if days <= 120 else -0.02 if days > 400 else 0.0
    return round(min(0.97, max(0.85, base + boost)), 3)


def review_order(state: dict, packs, now: datetime, kcs: list[str]) -> list[str]:
    """Most at risk first (lowest recall probability, weighted towards sooner exams), then mixed across subtopics."""
    scored = []
    for kc in kcs:
        r = model.retrievability(state["kcs"][kc], now) if kc in state["kcs"] else None
        days = max(0, (exam_date(packs, kc) - now.date()).days) if kc in packs.kcs else 365
        scored.append(((1 - (r if r is not None else 0.0)) * (1 + 2 * math.exp(-days / 60)), kc))
    groups: dict[str, list[str]] = {}
    for _, kc in sorted(scored, key=lambda x: -x[0]):
        groups.setdefault(packs.kc(kc)["subtopic"] if kc in packs.kcs else kc, []).append(kc)
    cols = list(groups.values())
    return [g[i] for i in range(max(map(len, cols), default=0)) for g in cols if i < len(g)]


def expand_focus(packs, focus: list[str] | None) -> list[str] | None:
    """KC ids pass through; a subtopic or topic prefix ("9702-2.1", "9702-1") expands to its KCs in syllabus order."""
    if not focus:
        return focus
    out: list[str] = []
    for f in focus:
        hits = [f] if f in packs.kcs else [k for k in packs.kcs if k.startswith(f.rstrip(".") + ".")]
        out += [k for k in hits if k not in out]
    return out


def plan_session(state: dict, packs, now: datetime, minutes: int, mode: str = "autopilot",
                 focus: list[str] | None = None, ticked: frozenset = frozenset()) -> list[dict]:
    focus = expand_focus(packs, focus)
    if mode == "lesson":
        kcs = [k for k in focus or [] if k in packs.kcs]
        if not kcs:
            return []
        subs = [packs.kc(k)["subtopic"] for k in kcs]
        sub = max(set(subs), key=subs.count)
        kcs = [k for k in kcs if packs.kc(k)["subtopic"] == sub]
        pre = [p for k in kcs for p in packs.kc(k).get("prereqs", [])
               if p not in kcs and p in packs.kcs and packs.kc(p)["spec"] == packs.kc(k)["spec"]]
        probe = [k for k in dict.fromkeys(pre[:3] + kcs) if packs.items_for(k)]
        return [{"kind": "goal", "subtopic": sub}, {"kind": "sweep", "kcs": probe, "lesson_probe": True},
                {"kind": "plan", "kcs": kcs, "subtopic": sub}]
    if mode == "test":
        groups: dict[str, list[str]] = {}
        for k in focus or []:
            if packs.items_for(k):
                groups.setdefault(packs.kc(k)["subtopic"], []).append(k)
        cols = list(groups.values())
        order = [g[i] for i in range(max(map(len, cols), default=0)) for g in cols if i < len(g)]
        return [{"kind": "sweep", "kcs": order}] if order else []
    if mode == "long":
        pool = focus or model.due_kcs(state, now) or [k for k, v in state["kcs"].items() if v["n"] > 0]
        return [{"kind": "long", "kcs": [k for k in pool if k in packs.kcs][: max(1, minutes // 15)]}]
    if mode == "diagnose":
        return [{"kind": "bracket", "kcs": [k for k in (focus or []) if k in packs.kcs][:8]}]
    if mode == "weak":  # focus: weak spots, weakest first (insights.weak_spots); re-teach some, practise the rest
        weak = [k for k in focus or [] if k in packs.kcs and packs.items_for(k)]
        learn = weak[:max(1, int(0.75 * minutes / 18))]
        rest = weak[len(learn):][:max(1, (minutes - 18 * len(learn)) // 3)]
        return ([{"kind": "learn", "kc": k} for k in learn] + ([{"kind": "practice", "kcs": rest}] if rest else [])
                + ([{"kind": "exit", "kcs": learn[:3]}] if learn else []))
    blocks: list[dict] = []
    used = 0
    retests = experiments.retests_due(state, now)
    if retests and mode in ("autopilot", "review"):
        blocks.append({"kind": "retest", "kcs": [kc for _, kc in retests], "exp": {kc: e for e, kc in retests}})
        used += 4 * len(retests)
    retest_kcs = {kc for _, kc in retests}
    if mode in ("autopilot", "review"):
        due = review_order(state, packs, now,
                           [k for k in model.due_kcs(state, now) if k not in retest_kcs and packs.items_for(k)])
        cap = max(1, int(0.35 * minutes / 2)) if mode == "autopilot" else max(1, int(0.7 * minutes / 2))
        if due:
            blocks.append({"kind": "review", "kcs": due[:cap]})
            used += 2 * len(due[:cap])
    learn: list[str] = []
    if mode == "learn" and focus:
        learn = [k for k in focus if k in packs.kcs]
    elif mode in ("autopilot", "repair"):
        remaining = max(0, minutes - used)
        waiting = to_check(state, packs, ticked) if mode == "autopilot" else []
        check = waiting[:max(2, int(0.3 * remaining / 2))]  # ticked in the Almanac: two minutes each, no lesson
        remaining = max(0, remaining - 2 * len(check))
        n = max(1 if remaining >= 20 else 0, int(0.75 * remaining / 18))
        learn = [k for k in state["gaps"] if k in packs.kcs][:n]
        if mode == "autopilot":
            learn += new_kcs(state, packs, n - len(learn), ticked)
        if check and not learn:  # nothing to teach: the lesson time goes to more checks
            check = waiting[:max(len(check), int(0.6 * (minutes - used) / 2))]
        if check:
            blocks.append({"kind": "sweep", "kcs": check, "claimed": True})
            used += 2 * len(check)
    for kc in learn:
        blocks.append({"kind": "learn", "kc": kc})
        used += 18
    if mode in ("autopilot", "review", "repair"):
        chosen = set(learn) | {k for b in blocks for k in b.get("kcs", [])}
        pool = [kc for kc, k in state["kcs"].items()
                if k["n"] > 0 and not model.is_mastered(k) and kc not in chosen and kc in packs.kcs and packs.items_for(kc)]
        pool.sort(key=lambda kc: packs.kc(kc)["subtopic"])
        count = max(0, int(max(0, minutes - used) / 3))
        interleaved = pool[0::2] + pool[1::2]
        if interleaved and count:
            blocks.append({"kind": "practice", "kcs": interleaved[:count]})
    exit_kcs = learn[:3] or [k for b in blocks for k in b.get("kcs", [])][:3]
    if exit_kcs:
        blocks.append({"kind": "exit", "kcs": exit_kcs})
    return blocks
