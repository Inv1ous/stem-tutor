from datetime import datetime, timedelta

import pytest

from tutorlib import model

T0 = datetime.fromisoformat("2026-09-28T17:00:00+08:00")


def ans(kc="K1", score=1.0, correct=True, error=None, mis=None, conf=4, hinted=False,
        ts=T0, difficulty=3, subject="chem", seconds=None, marks=1, credit=(), item="i1", pos=0):
    return {
        "type": "answer", "ts": ts.isoformat(), "item": item, "kcs": [kc], "subject": subject,
        "difficulty": difficulty, "conf": conf, "hinted": hinted, "seconds": seconds, "marks": marks,
        "grade": {"correct": correct, "score": score, "error": error, "misconception": mis},
        "credit": list(credit), "pos": pos,
    }


def fold(events):
    s = model.new_state()
    for e in events:
        model.apply(s, e)
    return s


def test_p_correct_is_half_at_matching_difficulty():
    assert model.p_correct(0.0, 3) == pytest.approx(0.5)
    assert model.p_correct(0.0, 1) > 0.5 > model.p_correct(0.0, 5)


def test_theta_rises_on_success_and_falls_on_failure():
    up = fold([ans(score=1.0)])["kcs"]["K1"]["theta"]
    down = fold([ans(score=0.0, correct=False)])["kcs"]["K1"]["theta"]
    assert up > 0 > down


def test_hinted_success_raises_theta_less_than_unaided():
    plain = fold([ans()])["kcs"]["K1"]["theta"]
    hinted = fold([ans(hinted=True)])["kcs"]["K1"]["theta"]
    assert 0 < hinted < plain


def test_first_unassisted_attempt_creates_fsrs_card_due_in_future():
    k = fold([ans()])["kcs"]["K1"]
    due = datetime.fromisoformat(k["fsrs"]["due"])
    assert due > T0


def test_only_first_attempt_per_day_counts_as_review():
    s = fold([ans(), ans(ts=T0 + timedelta(minutes=5), score=0, correct=False)])
    assert s["kcs"]["K1"]["reviews"] == 1


def test_hinted_correct_attempt_rates_hard_and_does_not_count_towards_secure():
    s = fold([ans(hinted=True)])
    assert s["kcs"]["K1"]["last_rating"] == "hard"
    assert s["kcs"]["K1"]["succ_days"] == []


def test_mastery_needs_theta_and_two_spaced_successes():
    day1 = [ans(ts=T0 + timedelta(minutes=i), item=f"i{i}") for i in range(6)]
    s = fold(day1)
    assert s["kcs"]["K1"]["theta"] >= model.MASTERY_THETA
    assert not model.is_mastered(s["kcs"]["K1"])
    s = fold(day1 + [ans(ts=T0 + timedelta(days=2), item="i9")])
    assert model.is_mastered(s["kcs"]["K1"])


def test_implicit_credit_reviews_prerequisite_listed_in_event():
    s = fold([ans(kc="P", ts=T0 - timedelta(days=10)), ans(kc="K1", credit=["P"])])
    assert s["kcs"]["P"]["reviews"] == 2


def test_misconception_flag_set_then_cleared_after_two_correct():
    s = fold([ans(score=0, correct=False, error="CONCEPT", mis="m1")])
    assert s["kcs"]["K1"]["active_misconceptions"] == ["m1"]
    s = fold([
        ans(score=0, correct=False, error="CONCEPT", mis="m1"),
        ans(ts=T0 + timedelta(minutes=1), item="i2"),
        ans(ts=T0 + timedelta(minutes=2), item="i3"),
    ])
    assert s["kcs"]["K1"]["active_misconceptions"] == []


def test_high_confidence_error_counts_hypercorrection():
    s = fold([ans(score=0, correct=False, conf=4, error="CONCEPT", mis="m1")])
    assert s["traits"]["calibration"]["high_conf_errors"] == 1


def test_calibration_bias_positive_when_overconfident():
    s = fold([ans(score=0, correct=False, conf=4, item=f"i{i}", ts=T0 + timedelta(minutes=i)) for i in range(4)])
    assert model.calibration(s)["bias"] > 0.5


def test_error_codes_counted_per_subject():
    s = fold([ans(score=0, correct=False, error="SLIP")])
    assert s["traits"]["errors"]["chem"]["SLIP"] == 1


def test_tag_event_reclassifies_error():
    e = ans(score=0, correct=False, error=None)
    e["id"] = "ev1"
    s = fold([e, {"type": "tag", "target": "ev1", "error": "SLIP", "ts": T0.isoformat()}])
    assert s["traits"]["errors"]["chem"]["SLIP"] == 1


def test_gap_events():
    s = fold([{"type": "gaps", "add": ["K1", "K2"], "ts": T0.isoformat()},
              {"type": "gaps", "remove": ["K1"], "ts": T0.isoformat()}])
    assert s["gaps"] == ["K2"]


def test_force_due_sets_card_due():
    s = fold([ans(), {"type": "force_due", "kc": "K1", "due": (T0 + timedelta(days=7)).isoformat(), "ts": T0.isoformat()}])
    assert datetime.fromisoformat(s["kcs"]["K1"]["fsrs"]["due"]) == T0 + timedelta(days=7)


def test_due_kcs_sorted_most_overdue_first():
    s = fold([ans(kc="A", ts=T0 - timedelta(days=30)), ans(kc="B", ts=T0 - timedelta(days=60))])
    assert model.due_kcs(s, T0) == ["B", "A"]


def test_retention_knob_raises_target_when_reviews_fail():
    events = []
    for i in range(12):
        kc = f"K{i}"
        events.append(ans(kc=kc, ts=T0 - timedelta(days=40)))
        events.append(ans(kc=kc, ts=T0, score=0, correct=False, item="r"))
    knobs = model.knobs(fold(events))
    assert knobs["desired_retention"]["chem"] > 0.9


def test_rebuild_is_deterministic():
    evs = [ans(), ans(ts=T0 + timedelta(days=3), item="x")]
    assert fold(evs) == fold(evs)
