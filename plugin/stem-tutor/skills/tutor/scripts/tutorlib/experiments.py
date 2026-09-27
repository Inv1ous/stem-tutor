"""Personal n-of-1 experiments: which of two evidence-based methods works better for this learner.

Design: comparable KCs are paired; within a pair the two methods are randomised; each KC gets a
fixed unassisted 3-item retest 7 days after teaching. Paired differences are analysed with a
flat-prior t posterior. A method is adopted only if P(better) >= 0.9 and the gain >= 10 points.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta

RETEST_DAYS = 7
MIN_GAIN = 0.10
MIN_PROB = 0.9


# ---------- Student t CDF via regularized incomplete beta ----------
def _betacf(a: float, b: float, x: float) -> float:
    tiny, qab, qap, qam = 1e-300, a + b, a + 1, a - 1
    c, d = 1.0, 1 - qab * x / qap
    d = 1 / (d if abs(d) > tiny else tiny)
    h = d
    for m in range(1, 300):
        m2 = 2 * m
        for aa in (m * (b - m) * x / ((qam + m2) * (a + m2)), -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))):
            d = 1 + aa * d
            d = 1 / (d if abs(d) > tiny else tiny)
            c = 1 + aa / c
            c = c if abs(c) > tiny else tiny
            h *= d * c
        if abs(d * c - 1) < 1e-12:
            break
    return h


def _betainc(a: float, b: float, x: float) -> float:
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    lbeta = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log(1 - x)
    if x < (a + 1) / (a + b + 2):
        return math.exp(lbeta) * _betacf(a, b, x) / a
    return 1 - math.exp(lbeta) * _betacf(b, a, 1 - x) / b


def t_cdf(t: float, df: int) -> float:
    tail = 0.5 * _betainc(df / 2, 0.5, df / (df + t * t))
    return 1 - tail if t > 0 else tail


# ---------- state folding (called from model.apply) ----------
def apply(state: dict, e: dict) -> None:
    exps = state["experiments"]
    if e["type"] == "exp_start":
        exps[e["exp"]] = {"subject": e["subject"], "arms": e["arms"], "eligible": e["eligible"],
                          "target_pairs": e.get("target_pairs", 14), "pairs": [], "status": "running",
                          "started": e["ts"], "result": None}
        return
    exp = exps.get(e["exp"])
    if not exp:
        return
    if e["type"] == "exp_assign":
        while len(exp["pairs"]) <= e["pair"]:
            exp["pairs"].append({"arms": {}, "scores": {}, "taught": {}})
        pair = exp["pairs"][e["pair"]]
        pair["arms"][e["kc"]] = e["arm"]
        pair["taught"][e["kc"]] = e["ts"]
    elif e["type"] == "exp_score":
        for pair in exp["pairs"]:
            if e["kc"] in pair["arms"]:
                pair["scores"][e["kc"]] = e["score"]
    elif e["type"] == "exp_end":
        exp["status"] = "done"
        exp["result"] = e.get("result")


# ---------- queries ----------
def active(state: dict, subject: str) -> tuple[str, dict] | None:
    for name, exp in state["experiments"].items():
        if exp["status"] == "running" and exp["subject"] == subject:
            return name, exp
    return None


def eligible(exp: dict, kc_meta: dict, kc_state: dict) -> bool:
    rule = exp["eligible"]
    return (kc_meta.get("subject") == exp["subject"]
            and kc_meta.get("type") in rule.get("types", [kc_meta.get("type")])
            and kc_state.get("theta", 0.0) >= rule.get("theta_min", -99))


def assign(state: dict, exp_name: str, kc: str, rng) -> dict:
    exp = state["experiments"][exp_name]
    for i, pair in enumerate(exp["pairs"]):
        if len(pair["arms"]) == 1:
            used = next(iter(pair["arms"].values()))
            return {"arm": next(a for a in exp["arms"] if a != used), "pair": i}
    return {"arm": rng.choice(exp["arms"]), "pair": len(exp["pairs"])}


def retests_due(state: dict, now: datetime) -> list[tuple[str, str]]:
    out = []
    for name, exp in state["experiments"].items():
        for pair in exp["pairs"]:
            for kc, ts in pair["taught"].items():
                if kc not in pair["scores"] and datetime.fromisoformat(ts) + timedelta(days=RETEST_DAYS) <= now:
                    out.append((name, kc))
    return out


def analyze(exp: dict) -> dict:
    first, second = exp["arms"]
    diffs = []
    for pair in exp["pairs"]:
        by_arm = {arm: pair["scores"].get(kc) for kc, arm in pair["arms"].items()}
        if by_arm.get(first) is not None and by_arm.get(second) is not None:
            diffs.append(by_arm[first] - by_arm[second])
    n = len(diffs)
    out = {"complete_pairs": n, "target_pairs": exp["target_pairs"], "arms": exp["arms"],
           "mean_diff": None, "p_first_better": None, "decision": "pending"}
    if n < 2:
        return out
    mean = sum(diffs) / n
    sd = math.sqrt(sum((d - mean) ** 2 for d in diffs) / (n - 1))
    if sd == 0:
        p = 1.0 if mean > 0 else 0.0 if mean < 0 else 0.5
    else:
        p = t_cdf(mean / (sd / math.sqrt(n)), n - 1)
    out.update(mean_diff=round(mean, 3), p_first_better=round(p, 3))
    if n >= exp["target_pairs"]:
        if p >= MIN_PROB and mean >= MIN_GAIN:
            out["decision"] = first
        elif 1 - p >= MIN_PROB and -mean >= MIN_GAIN:
            out["decision"] = second
        else:
            out["decision"] = "no_difference"
    return out
