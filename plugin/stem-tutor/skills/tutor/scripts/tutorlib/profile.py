"""What the tutor has learned about you, computed from your answers (no AI). Used by Profile.md and the app.

Every figure compares what happened with what the model expected, so a hard topic doesn't look like a bad day.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from . import experiments, model

CONF_NAMES = {"1": "Guess", "2": "Unsure", "3": "Fairly sure", "4": "Certain"}
MIN = 12  # answers needed before a pattern is reported


def _residual(n: int, correct: int, expected: float) -> float:
    return (correct - expected) / n if n else 0.0


def summary(state: dict, packs, now: datetime) -> dict:
    t = state["traits"]
    out: dict = {}

    # confidence: how often you're right at each confidence level
    cal = model.calibration(state)
    by = t["calibration"].get("by_conf", {})
    out["calibration"] = {
        "n": cal["n"], "bias": cal.get("bias"), "brier": cal.get("brier"), "high_conf_errors": cal.get("high_conf_errors", 0),
        "levels": [{"level": CONF_NAMES[c], "said": model.CONF_P[int(c)], "n": n, "right": k / n}
                   for c, (n, k) in sorted(by.items()) if n],
    }

    # time of day: accuracy above/below what was expected for those questions
    blocks = [{"block": b, "n": v[0], "residual": _residual(v[0], v[1], v[2])} for b, v in t.get("hours", {}).items()]
    ranked = sorted([b for b in blocks if b["n"] >= MIN], key=lambda b: -b["residual"])
    out["time_of_day"] = {"blocks": sorted(blocks, key=lambda b: ["morning", "afternoon", "evening", "late night"]
                                           .index(b["block"])),
                          "best": ranked[0]["block"] if len(ranked) >= 2 and ranked[0]["residual"] - ranked[-1]["residual"] >= 0.1
                          else None}

    # stamina: accuracy vs expectation by position in the session
    fat = []
    for b, v in sorted(t["fatigue"].items(), key=lambda x: int(x[0])):
        n, c = v[0], v[1]
        e = v[2] if len(v) > 2 else n * 0.5
        fat.append({"items": f"{int(b) * 5 + 1}–{int(b) * 5 + 5}", "n": n, "residual": _residual(n, c, e)})
    out["stamina"] = {"buckets": fat, "break_after": model.knobs(state)["max_items_before_break"]}

    # mistakes by kind
    errs: dict[str, int] = {}
    for per in t["errors"].values():
        for code, n in per.items():
            errs[code] = errs.get(code, 0) + n
    out["errors"] = dict(sorted(((k, v) for k, v in errs.items() if v > 0), key=lambda x: -x[1]))

    # forgetting: recall on spaced reviews vs the model's forecast
    out["forgetting"] = {s: {"n": n, "expected": pred / n, "actual": act / n}
                         for s, (n, pred, act) in t["retention"].items() if n}

    # pace
    out["pace"] = {s: sec / marks / 60 for s, (sec, marks) in t["time"].items() if marks}

    # habits: study days in the last 4 weeks, current streak
    days = sorted({date.fromisoformat(d) for d in state.get("study_days", [])})
    today = now.date()
    streak, d = 0, today if today in days else today - timedelta(days=1)
    dayset = set(days)
    while d in dayset:
        streak, d = streak + 1, d - timedelta(days=1)
    out["habits"] = {"streak": streak, "last_28": sum(1 for x in days if (today - x).days < 28),
                     "hints_rate": t["hints"]["hinted"] / t["hints"]["n"] if t["hints"]["n"] else 0.0}

    # workload: reviews falling due each of the next 7 days
    load = [0] * 7
    for k in state["kcs"].values():
        if k.get("fsrs"):
            due = datetime.fromisoformat(k["fsrs"]["due"]).astimezone(now.tzinfo).date()
            i = max(0, (due - today).days)
            if i < 7:
                load[i] += 1
    out["workload"] = load

    # mastery per spec
    spec: dict[str, dict] = {}
    for kc, k in state["kcs"].items():
        if k["n"] and kc in packs.kcs:
            s = spec.setdefault(packs.kc(kc)["spec"], {"started": 0, "secure": 0})
            s["started"] += 1
            s["secure"] += model.is_mastered(k)
    out["mastery"] = spec

    # which teaching methods have worked (experiments + what happened after lessons)
    out["experiments"] = [{"name": name, "subject": exp["subject"], **experiments.analyze(exp)}
                          for name, exp in state["experiments"].items()]
    out["knobs"] = model.knobs(state)
    return out


def advice(p: dict) -> list[str]:
    """Plain-English takeaways, only when the evidence is there."""
    tips = []
    cal = p["calibration"]
    if cal["n"] >= 30 and cal["bias"] is not None:
        if cal["bias"] > 0.1:
            tips.append("You tend to be **overconfident**: when you feel sure, double-check units, signs and the "
                        "question wording before answering.")
        elif cal["bias"] < -0.1:
            tips.append("You tend to be **underconfident**: you know more than you think. Trust answers you can justify.")
    if p["time_of_day"]["best"]:
        tips.append(f"You do best in the **{p['time_of_day']['best']}** compared with what's expected for the "
                    "questions you get. Put new topics there when you can.")
    if p["stamina"]["break_after"]:
        tips.append(f"Your accuracy dips after about **{p['stamina']['break_after']} questions**: the tutor suggests a "
                    "short break there.")
    errs = p["errors"]
    total = sum(errs.values())
    if total >= 8:
        top = next(iter(errs))
        tips.append({"SLIP": "Most lost marks are **careless slips**: use the checking routine before each answer.",
                     "MISREAD": "Many lost marks come from **misreading**: underline what is given and what is asked.",
                     "RECALL": "Many misses are **not remembering**: keep up the reviews, they target exactly this.",
                     "CONCEPT": "Many misses are **misconceptions**: the 'Watch out' boxes in My Notes list yours.",
                     "PROCEDURE": "Many misses are **method errors**: redo the worked examples and predict each step.",
                     "NOTATION": "Marks are lost on **units and significant figures**: make them a habit.",
                     }.get(top, f"Your most common mistake type is **{top.lower()}**."))
    if p["habits"]["hints_rate"] >= 0.4:
        tips.append("You use hints a lot: have a real go first; struggling a little is what makes it stick.")
    return tips
