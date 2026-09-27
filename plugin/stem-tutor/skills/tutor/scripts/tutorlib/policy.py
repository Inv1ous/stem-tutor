"""Deterministic teaching policy: which method, which KCs, in what order.

Default method table encodes the evidence (expertise reversal, refutation for misconceptions,
pretesting for novices on conceptual material). Personal experiments override it per KC.
"""
from __future__ import annotations

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
    return default_method(meta, ks, fresh), None


# ---------------- session planning ----------------
def _introduced(state: dict, kc: str) -> bool:
    return state["kcs"].get(kc, {}).get("n", 0) > 0


def new_kcs(state: dict, packs, now: datetime, limit: int) -> list[str]:
    week = current_week(packs.plan, now)
    weeks = sorted(int(w) for w in packs.plan.get("weeks", {}))
    ordered: list[str] = []
    for w in [w for w in weeks if w <= week] + [w for w in weeks if w == week + 1]:
        for obj in packs.plan["weeks"][str(w)]:
            ordered.extend(obj.get("kcs", []))
    out: list[str] = []

    def add(kc: str, depth: int = 0):
        if kc in out or kc not in packs.kcs or _introduced(state, kc) or depth > 6:
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


def plan_session(state: dict, packs, now: datetime, minutes: int, mode: str = "autopilot",
                 focus: list[str] | None = None) -> list[dict]:
    blocks: list[dict] = []
    used = 0
    retests = experiments.retests_due(state, now)
    if retests and mode in ("autopilot", "review"):
        blocks.append({"kind": "retest", "kcs": [kc for _, kc in retests], "exp": {kc: e for e, kc in retests}})
        used += 4 * len(retests)
    retest_kcs = {kc for _, kc in retests}
    if mode in ("autopilot", "review"):
        due = [k for k in model.due_kcs(state, now) if k not in retest_kcs and packs.items_for(k)]
        cap = max(1, int(0.35 * minutes / 2)) if mode == "autopilot" else max(1, int(0.7 * minutes / 2))
        if due:
            blocks.append({"kind": "review", "kcs": due[:cap]})
            used += 2 * len(due[:cap])
    learn: list[str] = []
    if mode == "learn" and focus:
        learn = [k for k in focus if k in packs.kcs]
    elif mode in ("autopilot", "repair"):
        remaining = max(0, minutes - used)
        n = max(1 if remaining >= 20 else 0, int(0.75 * remaining / 18))
        learn = [k for k in state["gaps"] if k in packs.kcs][:n]
        if mode == "autopilot":
            learn += new_kcs(state, packs, now, n - len(learn))
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
