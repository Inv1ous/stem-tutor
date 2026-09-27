import random

import pytest

from tutorlib import experiments, model


def start(state, **kw):
    e = {"type": "exp_start", "exp": "E1", "subject": "chem", "arms": ["worked_faded", "problem_first"],
         "eligible": {"types": ["conceptual"], "theta_min": 0.5}, "target_pairs": 4, "ts": "2026-10-01T10:00:00+08:00"}
    e.update(kw)
    return model.apply(state, e)


def test_t_cdf_matches_known_values():
    assert experiments.t_cdf(0.0, 5) == pytest.approx(0.5)
    assert experiments.t_cdf(2.015, 5) == pytest.approx(0.95, abs=1e-3)
    assert experiments.t_cdf(-1.833, 9) == pytest.approx(0.05, abs=1e-3)


def test_assign_alternates_within_pair():
    s = start(model.new_state())
    rng = random.Random(1)
    a1 = experiments.assign(s, "E1", "K1", rng)
    model.apply(s, {"type": "exp_assign", "exp": "E1", "kc": "K1", **a1, "ts": "x"})
    a2 = experiments.assign(s, "E1", "K2", rng)
    assert a2["pair"] == a1["pair"] and a2["arm"] != a1["arm"]
    model.apply(s, {"type": "exp_assign", "exp": "E1", "kc": "K2", **a2, "ts": "x"})
    a3 = experiments.assign(s, "E1", "K3", rng)
    assert a3["pair"] == a1["pair"] + 1


def test_eligibility_checks_type_and_theta():
    s = start(model.new_state())
    exp = s["experiments"]["E1"]
    assert experiments.eligible(exp, {"type": "conceptual", "subject": "chem"}, {"theta": 0.6})
    assert not experiments.eligible(exp, {"type": "procedural", "subject": "chem"}, {"theta": 0.6})
    assert not experiments.eligible(exp, {"type": "conceptual", "subject": "chem"}, {"theta": 0.1})
    assert not experiments.eligible(exp, {"type": "conceptual", "subject": "phys"}, {"theta": 0.9})


def _run(scores):
    s = start(model.new_state())
    for i, (sa, sb) in enumerate(scores):
        for kc, arm, sc in ((f"A{i}", "worked_faded", sa), (f"B{i}", "problem_first", sb)):
            model.apply(s, {"type": "exp_assign", "exp": "E1", "kc": kc, "arm": arm, "pair": i, "ts": "x"})
            model.apply(s, {"type": "exp_score", "exp": "E1", "kc": kc, "score": sc, "ts": "x"})
    return experiments.analyze(s["experiments"]["E1"])


def test_analysis_adopts_clearly_better_arm():
    r = _run([(1.0, 0.67), (1.0, 0.67), (0.67, 0.33), (1.0, 0.67)])
    assert r["complete_pairs"] == 4 and r["decision"] == "worked_faded"
    assert r["p_first_better"] > 0.9


def test_analysis_no_difference_when_mixed():
    r = _run([(1.0, 0.67), (0.67, 1.0), (1.0, 1.0), (0.33, 0.67)])
    assert r["decision"] == "no_difference"


def test_analysis_pending_before_target():
    r = _run([(1.0, 0.33)])
    assert r["decision"] == "pending"


def test_retests_due_lists_unscored_kcs_after_seven_days():
    s = start(model.new_state())
    model.apply(s, {"type": "exp_assign", "exp": "E1", "kc": "K1", "arm": "worked_faded", "pair": 0,
                    "ts": "2026-10-01T10:00:00+08:00"})
    from datetime import datetime
    assert experiments.retests_due(s, datetime.fromisoformat("2026-10-05T10:00:00+08:00")) == []
    assert experiments.retests_due(s, datetime.fromisoformat("2026-10-08T10:00:00+08:00")) == [("E1", "K1")]
