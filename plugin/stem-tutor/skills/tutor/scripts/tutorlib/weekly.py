"""Weekly bookkeeping (no AI): refresh Today.md and Profile.md, start/finish personal experiments,
export new Anki cards when a week has passed, and sync the Almanac planner when it has left an export."""
from __future__ import annotations

from datetime import datetime

from . import anki, experiments, report

EXPERIMENT_QUEUE = [
    {"arms": ["worked_faded", "problem_first"], "eligible": {"types": ["conceptual", "procedural"], "theta_min": 0.3}},
    {"arms": ["pretest_explain", "worked_faded"], "eligible": {"types": ["conceptual"]}},
]


def start_experiments(t) -> list[str]:
    started = []
    for subject in ("chem", "phys", "math"):
        if experiments.active(t.state, subject):
            continue
        done = [n for n, e in t.state["experiments"].items() if e["subject"] == subject]
        introduced = [k for k, s in t.state["kcs"].items() if s["n"] and k in t.packs.kcs
                      and t.packs.kc(k)["subject"] == subject]
        if len(done) < len(EXPERIMENT_QUEUE) and len(introduced) >= 5:
            name = f"{subject}-{len(done) + 1}"
            t.log({"type": "exp_start", "exp": name, "subject": subject, "target_pairs": 12,
                   **EXPERIMENT_QUEUE[len(done)]})
            started.append(name)
    for name, exp in t.state["experiments"].items():
        r = experiments.analyze(exp)
        if exp["status"] == "running" and r["decision"] not in ("pending",):
            t.log({"type": "exp_end", "exp": name, "result": r})
    return started


def run(t, minutes: int = 50) -> dict:
    res = {"today": report.today_note(t, minutes), "profile": report.profile_note(t),
           "experiments_started": start_experiments(t)}
    last = t.state.get("anki_last")
    if last is None or (t.now() - datetime.fromisoformat(last)).days >= 6:
        res["anki"] = anki.export(t)
    root = t.vault.root
    if (root / "Almanac").exists() and any((root / "Almanac").glob("almanac-progress-*.json")):
        res["almanac"] = report.almanac_sync(t)
    return res
