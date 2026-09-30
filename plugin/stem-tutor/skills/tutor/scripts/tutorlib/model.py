"""Learner model. State is a pure fold over events, so `rebuild` always reproduces it.

Per knowledge component (KC): Elo ability θ against fixed item difficulty, an FSRS card
(day-level problem scheduling), spaced-success days for mastery, misconception flags.
Global traits: calibration, error mix, hint use, time per mark, fatigue, forgetting vs model.
"""
from __future__ import annotations

import math
import zlib
from datetime import date, datetime, timezone

from . import deps

MASTERY_THETA = 0.8
CONF_P = {1: 0.25, 2: 0.5, 3: 0.75, 4: 0.95}
SUCCESS = 0.75
MODEL_VERSION = "1.1"  # bump when the fold changes; saved states from older versions are rebuilt from events once
SLIP_DAMPING = 0.5  # a likely slip (fast miss on an item you almost always get) moves θ half as much


def p_correct(theta: float, difficulty: int) -> float:
    b = (difficulty - 3) * 0.8
    return 1 / (1 + math.exp(-(theta - b)))


def new_state() -> dict:
    return {
        "kcs": {},
        "traits": {
            "calibration": {"n": 0, "sum_conf": 0.0, "sum_acc": 0.0, "sum_brier": 0.0, "high_conf_errors": 0},
            "errors": {},
            "hints": {"n": 0, "hinted": 0},
            "time": {},
            "fatigue": {},
            "retention": {},
            "sessions": 0,
            "hours": {},
        },
        "study_days": [],
        "anki_last": None,
        "model_version": MODEL_VERSION,
        "gaps": [],
        "items_seen": {},
        "answers": {},
        "experiments": {},
    }


def _new_kc() -> dict:
    return {"theta": 0.0, "n": 0, "succ_days": [], "fsrs": None, "reviews": 0, "last_rating": None,
            "last_review_day": None, "active_misconceptions": [], "mis_counts": {}, "mis_streak": {},
            "errors": {}, "first_seen": None}


def _fsrs():
    deps.ensure("fsrs")
    import fsrs

    return fsrs


_SCHEDULERS: dict[float, object] = {}


def _scheduler(desired_retention: float):
    """One FSRS scheduler per retention target (building one per review was the slowest part of a rebuild)."""
    r = round(desired_retention, 3)
    if r not in _SCHEDULERS:
        fsrs = _fsrs()
        _SCHEDULERS[r] = fsrs.Scheduler(desired_retention=r, learning_steps=(), relearning_steps=(),
                                        enable_fuzzing=False)
    return _SCHEDULERS[r]


def fsrs_rating(success: bool, conf: int | None, prior_success_days: int) -> str:
    """Map an attempt to FSRS's four grades. Wrong or hinted → again; right but guessing/unsure → hard;
    right and certain on an idea already recalled on two earlier days → easy; otherwise good."""
    if not success:
        return "again"
    if conf in (1, 2):
        return "hard"
    if conf == 4 and prior_success_days >= 2:
        return "easy"
    return "good"


def retrievability(k: dict, now: datetime) -> float | None:
    if not k.get("fsrs"):
        return None
    fsrs = _fsrs()
    return float(_scheduler(0.9).get_card_retrievability(fsrs.Card.from_dict(k["fsrs"]), now.astimezone(timezone.utc)))


def _review(state: dict, kc: str, good: bool, when: datetime, subject: str, rating: str | None = None,
            retention: float | None = None) -> None:
    fsrs = _fsrs()
    k = state["kcs"][kc]
    sched = _scheduler(retention or knobs(state)["desired_retention"].get(subject, 0.9))
    utc = when.astimezone(timezone.utc)
    if k["fsrs"]:
        card = fsrs.Card.from_dict(k["fsrs"])
        if card.state == fsrs.State.Review:
            r = state["traits"]["retention"].setdefault(subject, [0, 0.0, 0.0])
            r[0] += 1
            r[1] += sched.get_card_retrievability(card, utc)
            r[2] += 1.0 if good else 0.0
    else:
        card = fsrs.Card(card_id=zlib.crc32(kc.encode()))
    rating = rating or ("good" if good else "again")
    card, _ = sched.review_card(card, getattr(fsrs.Rating, rating.capitalize()), utc)
    k["fsrs"] = card.to_dict()
    k["reviews"] += 1
    k["last_rating"] = rating
    k["last_review_day"] = when.date().isoformat()


def _count(d: dict, key: str, by: int = 1) -> None:
    d[key] = d.get(key, 0) + by


def _apply_answer(state: dict, e: dict) -> None:
    when = datetime.fromisoformat(e["ts"])
    day = when.date().isoformat()
    g = e["grade"]
    score = g["score"] * (0.7 if e.get("hinted") else 1.0)
    success = g["score"] >= SUCCESS and not e.get("hinted")
    subject = e.get("subject", "misc")
    expected = []
    for kc in e["kcs"]:
        k = state["kcs"].setdefault(kc, _new_kc())
        k["first_seen"] = k["first_seen"] or e["ts"]
        p = p_correct(k["theta"], e.get("difficulty", 3))
        expected.append(p)
        step = max(0.15, 0.6 / (1 + 0.1 * k["n"])) * (SLIP_DAMPING if e.get("slip_likely") else 1.0)
        k["theta"] += step * (score - p)
        k["n"] += 1
        prior_days = len([d for d in k["succ_days"] if d != day])
        if success and day not in k["succ_days"]:
            k["succ_days"].append(day)
        mis = g.get("misconception")
        if mis:
            if mis not in k["active_misconceptions"]:
                k["active_misconceptions"].append(mis)
            _count(k["mis_counts"], mis)
            k["mis_streak"][mis] = 0
        elif g["score"] >= SUCCESS:
            for m in list(k["active_misconceptions"]):
                k["mis_streak"][m] = k["mis_streak"].get(m, 0) + 1
                if k["mis_streak"][m] >= 2:
                    k["active_misconceptions"].remove(m)
        if g.get("error"):
            _count(k["errors"], g["error"])
        if k["last_review_day"] != day:
            _review(state, kc, success, when, subject, fsrs_rating(success, e.get("conf"), prior_days),
                     e.get("retention"))
    for kc in e.get("credit", []):
        k = state["kcs"].get(kc)
        if k and k["fsrs"] and k["last_review_day"] != day and success:
            _review(state, kc, True, when, subject)

    t = state["traits"]
    exp_p = sum(expected) / len(expected) if expected else 0.5
    if e.get("conf") is not None:
        c, acc = CONF_P[e["conf"]], 1.0 if g["correct"] else 0.0
        cal = t["calibration"]
        lvl = cal.setdefault("by_conf", {}).setdefault(str(e["conf"]), [0, 0])
        lvl[0] += 1
        lvl[1] += 1 if g["correct"] else 0
        cal["n"] += 1
        cal["sum_conf"] += c
        cal["sum_acc"] += acc
        cal["sum_brier"] += (c - acc) ** 2
        if e["conf"] >= 3 and not g["correct"]:
            cal["high_conf_errors"] += 1
    if g.get("error"):
        _count(t["errors"].setdefault(subject, {}), g["error"])
    t["hints"]["n"] += 1
    t["hints"]["hinted"] += 1 if e.get("hinted") else 0
    if e.get("seconds") and e.get("marks") and e["seconds"] <= 1800 * e["marks"]:  # ignore questions left open for ages
        tm = t["time"].setdefault(subject, [0.0, 0])
        tm[0] += e["seconds"]
        tm[1] += e["marks"]
    bucket = t["fatigue"].setdefault(str(e.get("pos", 0) // 5), [0, 0, 0.0])
    if len(bucket) == 2:
        bucket.append(0.0)
    bucket[0] += 1
    bucket[1] += 1 if g["correct"] else 0
    bucket[2] += exp_p
    hour = t.setdefault("hours", {}).setdefault(_time_block(when), [0, 0, 0.0])
    hour[0] += 1
    hour[1] += 1 if g["correct"] else 0
    hour[2] += exp_p
    state["items_seen"][e["item"]] = e["ts"]
    if e.get("id"):
        state["answers"][e["id"]] = {"subject": subject, "error": g.get("error"), "kcs": e["kcs"]}
        if len(state["answers"]) > 600:  # only recent answers can still be tagged; keep the state file small
            for old in list(state["answers"])[:100]:
                del state["answers"][old]


def _time_block(when: datetime) -> str:
    h = when.hour
    return "morning" if 5 <= h < 12 else "afternoon" if h < 17 else "evening" if h < 22 else "late night"


def _apply_tag(state: dict, e: dict) -> None:
    a = state["answers"].get(e["target"])
    if not a:
        return
    errs = state["traits"]["errors"].setdefault(a["subject"], {})
    if a["error"]:
        _count(errs, a["error"], -1)
        for kc in a["kcs"]:
            _count(state["kcs"][kc]["errors"], a["error"], -1)
    _count(errs, e["error"])
    for kc in a["kcs"]:
        _count(state["kcs"][kc]["errors"], e["error"])
    a["error"] = e["error"]


def apply(state: dict, e: dict) -> dict:
    kind = e["type"]
    if kind == "answer":
        _apply_answer(state, e)
    elif kind == "tag":
        _apply_tag(state, e)
    elif kind == "gaps":
        gaps = set(state["gaps"]) | set(e.get("add", []))
        state["gaps"] = sorted(gaps - set(e.get("remove", [])))
    elif kind == "force_due":
        k = state["kcs"].get(e["kc"])
        if k and k["fsrs"]:
            k["fsrs"]["due"] = datetime.fromisoformat(e["due"]).astimezone(timezone.utc).isoformat()
    elif kind == "session_start":
        state["traits"]["sessions"] += 1
    elif kind == "session_end":
        day = e["ts"][:10]
        days = state.setdefault("study_days", [])
        if e.get("answered") and not e.get("abandoned") and day not in days:
            days.append(day)
    elif kind == "blurt":  # free recall: ideas left out come due now; totals feed the profile
        for kc in e.get("missed", []):
            k = state["kcs"].get(kc)
            if k and k["fsrs"]:
                ts = datetime.fromisoformat(e["ts"]).astimezone(timezone.utc)
                if datetime.fromisoformat(k["fsrs"]["due"]) > ts:
                    k["fsrs"]["due"] = ts.isoformat()
        b = state["traits"].setdefault("blurts", [0, 0, 0])
        b[0] += 1
        b[1] += len(e.get("recalled", []))
        b[2] += len(e.get("recalled", [])) + len(e.get("missed", []))
    elif kind == "anki_export":
        state.setdefault("anki_exported", []).extend(e["cards"])
        state["anki_last"] = e["ts"]
    elif kind.startswith("exp_"):
        from . import experiments

        experiments.apply(state, e)
    return state


# ---------------- queries ----------------
def is_mastered(k: dict) -> bool:
    days = sorted(date.fromisoformat(d) for d in k["succ_days"])
    return k["theta"] >= MASTERY_THETA and len(days) >= 2 and (days[-1] - days[0]).days >= 1


def due_kcs(state: dict, now: datetime) -> list[str]:
    due = []
    for kc, k in state["kcs"].items():
        if k["fsrs"]:
            d = datetime.fromisoformat(k["fsrs"]["due"])
            if d <= now:
                due.append((d, kc))
    return [kc for _, kc in sorted(due)]


def calibration(state: dict) -> dict:
    c = state["traits"]["calibration"]
    if not c["n"]:
        return {"n": 0, "bias": 0.0, "brier": None}
    return {"n": c["n"], "bias": (c["sum_conf"] - c["sum_acc"]) / c["n"], "brier": c["sum_brier"] / c["n"],
            "high_conf_errors": c["high_conf_errors"]}


def knobs(state: dict) -> dict:
    t = state["traits"]
    retention = {}
    for subject, (n, pred, out) in t["retention"].items():
        if n >= 10:
            delta = out / n - pred / n
            retention[subject] = round(min(0.95, max(0.85, 0.9 - 0.5 * delta)), 3)
    errs = {}
    for per in t["errors"].values():
        for code, v in per.items():
            errs[code] = errs.get(code, 0) + v
    total_err = sum(errs.values())
    cal = calibration(state)
    fatigue_items = None
    f = t["fatigue"]

    def resid(v: list) -> float:  # accuracy above/below what the item difficulty predicted
        return (v[1] - (v[2] if len(v) > 2 else 0.5 * v[0])) / v[0]

    if f.get("0", [0])[0] >= 10:
        base = resid(f["0"])
        for b in sorted(f, key=int)[1:]:
            if f[b][0] >= 10 and base - resid(f[b]) >= 0.15:
                fatigue_items = int(b) * 5
                break
    h = t["hints"]
    return {
        "desired_retention": retention,
        "checking_routine": total_err >= 8 and errs.get("SLIP", 0) / total_err >= 0.25,
        "confidence_training": cal["n"] >= 30 and abs(cal["bias"]) > 0.15,
        "attempt_before_hint": h["n"] >= 20 and h["hinted"] / h["n"] >= 0.4,
        "max_items_before_break": fatigue_items,
    }
