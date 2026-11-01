"""Exact adoption thresholds are independent of the retest score baseline."""
import random
from datetime import datetime

import pytest

from fixtures import make_vault
from tutorlib import experiments, policy, session, store, weekly


@pytest.mark.parametrize("first,second,winner", [
    (0.7, 0.6, "worked_faded"), (0.6, 0.7, "problem_first"),
    (0.8, 0.7, "worked_faded"), (0.7, 0.8, "problem_first"),
    (0.699, 0.6, "no_difference"), (0.6, 0.699, "no_difference"),
])
def test_weekly_finalization_accepts_exact_ten_point_gain_after_restart(tmp_path, first, second, winner):
    root = make_vault(tmp_path)
    now = lambda: datetime.fromisoformat("2026-10-08T17:00:00+08:00")
    tutor = session.Tutor(store.Vault(root), now=now)
    tutor.log({"type": "exp_start", "exp": "threshold", "subject": "phys", "target_pairs": 12,
               "arms": ["worked_faded", "problem_first"], "eligible": {"types": ["procedural"]}})
    for i in range(12):
        for arm, score in (("worked_faded", first), ("problem_first", second)):
            kc = f"synthetic-{i}-{arm}"
            tutor.log({"type": "exp_assign", "exp": "threshold", "kc": kc, "arm": arm, "pair": i})
            tutor.log({"type": "exp_score", "exp": "threshold", "kc": kc, "score": score})
    historical = {p: p.read_bytes() for p in (root / ".tutor/events").glob("*.jsonl")}
    # The normal weekly API decides and logs the completed experiment.
    weekly.start_experiments(tutor)
    result = tutor.state["experiments"]["threshold"]["result"]
    assert result["complete_pairs"] == 12
    assert result["decision"] == winner
    assert all(p.read_bytes().startswith(content) for p, content in historical.items())
    ended = {p: p.read_bytes() for p in historical}
    restored = session.Tutor(store.Vault(root), now=now)
    assert restored.state["experiments"] == tutor.state["experiments"]
    assert restored.state == restored._fold()
    assert {p: p.read_bytes() for p in historical} == ended
    meta = restored.packs.kc("9702-2.1.4")
    losing = "problem_first" if winner == "worked_faded" else "worked_faded"
    assert experiments.preferred(restored.state, meta, {}, losing) == (losing if winner == "no_difference" else winner)
    if winner == "problem_first":
        assert policy.choose_method(restored.state, restored.packs, "9702-2.1.4", random.Random(0)) == (winner, None)
