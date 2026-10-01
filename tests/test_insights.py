import random
from datetime import date, datetime

import pytest

from fixtures import make_vault
from tutorlib import insights, policy, session, store

T0 = datetime.fromisoformat("2026-09-29T17:00:00+08:00")


@pytest.fixture
def tutor(tmp_path):
    clock = {"now": T0}
    t = session.Tutor(store.Vault(make_vault(tmp_path)), rng=random.Random(0), now=lambda: clock["now"])
    t.clock = clock
    return t


def answer(t, kc="9702-2.1.1", right=True, conf=None, error=None, mis=None, item="9702-2.1-i01", response="B",
           seconds=40, marks=1, params=None, score=None):
    return t.log({"type": "answer", "session": "s1", "item": item, "kcs": [kc], "subject": "phys", "difficulty": 3,
                  "conf": conf, "hinted": False, "seconds": seconds, "marks": marks,
                  "grade": {"correct": right, "score": score if score is not None else 1.0 if right else 0.0,
                            "error": error, "misconception": mis},
                  "credit": [], "pos": 0, "block": "review", "phase": None, "params": params, "response": response})


def finding(f, area):
    return next(i for i in f["items"] if i["area"].startswith(area))


def test_certainty_labels():
    assert [insights.certainty(n, 10) for n in (0, 5, 10, 29, 30)] == [
        "not enough data", "early sign", "likely", "likely", "clear"]


def test_a_new_learner_gets_honest_empty_findings(tutor):
    f = insights.findings(tutor)
    assert f["recorded"]["answers"] == 0 and f["never"]
    assert f["items"] and all(i["certainty"] == "not enough data" and not i["action"] for i in f["items"])
    assert f["adjustments"] == []


def test_misconception_finding_quotes_the_pack(tutor):
    answer(tutor, right=False, mis="m1", response="A")
    m = finding(insights.findings(tutor), "Misconceptions")
    assert "Distance and displacement are the same thing" in m["detail"] and m["certainty"] == "likely"
    assert m["action"]


def test_overconfidence_is_found_and_acted_on(tutor):
    for i in range(32):
        answer(tutor, right=i % 4 == 0, conf=4, error=None if i % 4 == 0 else "CONCEPT")
    f = insights.findings(tutor)
    c = finding(f, "Confidence")
    assert c["certainty"] == "likely" and "Certain" in c["detail"] and "confidence" in c["action"]
    assert c["action"] in f["adjustments"]
    assert f["recorded"]["answers"] == 32 and f["recorded"]["confidence_ratings"] == 32


def test_readiness_counts_and_forecasts(tutor):
    answer(tutor, conf=3)
    r = next(r for r in insights.readiness(tutor) if r["exam"].startswith("9702"))
    assert (r["ideas"], r["built"], r["started"], r["estimated"]) == (2, 2, 1, True)
    assert r["days"] > 200 and r["recall_if_stop"] < r["recall_if_keep"]


def test_weak_spots_order_and_reasons(tutor):
    for _ in range(3):
        answer(tutor, kc="9702-2.1.4", right=False, item="9702-2.1-i03", response="2.0")
    answer(tutor, right=False, mis="m1", response="A")
    w = insights.weak_spots(tutor)
    assert [x["kc"] for x in w] == ["9702-2.1.1", "9702-2.1.4"]
    assert "Distance and displacement" in w[0]["reasons"][0] and w[1]["reasons"] == ["right 0 of 3 times"]


def test_weak_mode_plans_learn_then_practice(tutor):
    blocks = policy.plan_session(tutor.state, tutor.packs, T0, 40, mode="weak", focus=["9702-2.1.1", "9702-2.1.4"])
    assert [b["kind"] for b in blocks] == ["learn", "practice", "exit"]
    assert blocks[0]["kc"] == "9702-2.1.1" and blocks[1]["kcs"] == ["9702-2.1.4"]


def test_week_report_counts_a_scripted_week(tutor):
    tutor.clock["now"] = datetime.fromisoformat("2026-09-21T18:00:00+08:00")  # the week before
    answer(tutor)
    tutor.clock["now"] = datetime.fromisoformat("2026-09-29T18:00:00+08:00")
    answer(tutor, right=False, mis="m1", response="A")
    answer(tutor, kc="9702-2.1.4", item="9702-2.1-i03", response="4.0", seconds=90, marks=2)
    tutor.clock["now"] = datetime.fromisoformat("2026-09-30T18:00:00+08:00")
    answer(tutor)
    answer(tutor)  # two right answers in a row clear the misconception
    r = insights.week_report(tutor, date(2026, 9, 28))
    assert r["week"] == "2026-W40" and r["days"] == 2 and r["answers"] == 4 and r["minutes"] == 3.5
    assert r["right"] == 0.75 and r["right_change"] == -0.25
    assert any("Distance and displacement" in x for x in r["fixed"])


def test_answers_log_the_key_as_it_was_shown(tutor):
    tutor.start("autopilot", minutes=50)
    q = tutor.next()["items"][0]
    inst = tutor.session["presented"][str(q["n"])]["inst"]
    tutor.answer(f"{q['n']}A4" if q["kind"] == "mcq" else f"{q['n']} = 1 ~4")
    assert [e for e in tutor.vault.events() if e["type"] == "answer"][-1]["key"] == session._display_answer(inst)


def test_mistake_journal_has_the_right_answer_and_right_since(tutor):
    from tutorlib import lint, report
    answer(tutor, kc="9702-2.1.4", right=False, item="9702-2.1-i02", params={"t": 1.5}, response="14.7",
           error="PROCEDURE", marks=2)
    answer(tutor, right=False, mis="m1", response="A")
    answer(tutor, kc="9702-2.1.1", right=False, item="9702_s23_qp_22:1a", response="1/2", score=0.5)
    answer(tutor, kc="9702-2.1.4", right=False, item="we1f", response="30")  # a check inside a lesson
    tutor.clock["now"] = datetime.fromisoformat("2026-09-30T10:00:00+08:00")
    answer(tutor)  # the vector question, right this time
    text = (tutor.vault.root / report.mistakes_note(tutor)).read_text()
    assert "Right answer: 11.0 m" in text  # 0.5 × 9.81 × 1.5², re-created from the logged template value
    assert "Distance and displacement" in text and "displacement" in text and "✓ right since" in text
    assert "method errors" in text and "9702_s23_qp_22 Q1a" in text and "1/2" in text
    assert "## we1f" not in text and text.count("## 9702-2.1 Equations of motion") == 1
    assert lint.lint(text) == []


def test_week_note_is_written(tutor):
    from tutorlib import lint, report
    answer(tutor, right=False, mis="m1", response="A")
    path = report.week_note(tutor, date(2026, 9, 28))
    text = (tutor.vault.root / path).read_text()
    assert path == "Weekly/2026-W40.md" and "Studied on **1** day" in text and "[[Mistakes]]" in text
    assert lint.lint(text) == []
