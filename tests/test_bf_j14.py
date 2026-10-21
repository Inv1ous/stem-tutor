"""Bug-fix J14: partial self-marked answers are not successes, and a session past midnight counts on both days."""
from datetime import datetime, timedelta

from tutorlib import model

T0 = datetime.fromisoformat("2026-10-20T23:50:00+08:00")


def answer(kc="9702-2.1.1", correct=True, score=1.0, conf=3, ts=T0, **extra):
    return {"type": "answer", "ts": ts.isoformat(), "kcs": [kc], "subject": "phys", "difficulty": 3,
            "conf": conf, "hinted": False, "item": f"i{ts.timestamp()}", "marks": 4, "seconds": 120, "pos": 0,
            "grade": {"correct": correct, "score": score, "error": None, "misconception": None},
            **extra}


def test_three_of_four_self_marked_points_never_reach_mastery():
    """B-067 (bug watch): a structured answer the session reports wrong (3 of 4 scheme points) must not add a
    success day, a Good review or mastery."""
    s = model.new_state()
    for i in range(20):
        e = answer(correct=False, score=0.75, ts=T0 + timedelta(days=i))
        e["grade"]["self_marked"] = True
        model.apply(s, e)
    k = s["kcs"]["9702-2.1.1"]
    assert k["succ_days"] == [] and k["last_rating"] == "again"
    assert not model.is_mastered(k)


def test_a_session_that_ends_after_midnight_counts_the_day_you_answered_on():
    """B-091 (bug watch): answering at 23:55 and stopping at 00:05 is studying on both days, as the clock records
    it; an abandoned session still starts no streak."""
    s = model.new_state()
    model.apply(s, {"type": "session_start", "ts": T0.isoformat(), "session": "s1"})
    model.apply(s, answer(ts=T0 + timedelta(minutes=5), session="s1"))
    model.apply(s, {"type": "session_end", "ts": (T0 + timedelta(minutes=15)).isoformat(), "session": "s1",
                    "answered": 1})
    assert s["study_days"] == ["2026-10-20", "2026-10-21"]

    model.apply(s, {"type": "session_start", "ts": "2026-10-23T23:50:00+08:00", "session": "s2"})
    model.apply(s, answer(ts=datetime.fromisoformat("2026-10-23T23:55:00+08:00"), session="s2"))
    model.apply(s, {"type": "session_end", "ts": "2026-10-24T00:05:00+08:00", "session": "s2", "answered": 1,
                    "abandoned": True})
    assert s["study_days"] == ["2026-10-20", "2026-10-21"]
