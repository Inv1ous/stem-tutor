"""v1.1.0: richer memory ratings, exam-aware retention, slip damping, new traits, profile summary."""
from datetime import datetime, timedelta

import random

import pytest

from fixtures import make_vault
from tutorlib import model, profile, session, store

T0 = datetime.fromisoformat("2026-09-29T17:00:00+08:00")


@pytest.fixture
def tutor(tmp_path):
    return session.Tutor(store.Vault(make_vault(tmp_path)), rng=random.Random(0), now=lambda: T0)


def answer(kc="9702-2.1.1", correct=True, conf=3, ts=T0, **extra):
    return {"type": "answer", "ts": ts.isoformat(), "kcs": [kc], "subject": "phys", "difficulty": 3,
            "conf": conf, "hinted": False, "item": f"i{ts.timestamp()}", "marks": 1, "seconds": 30, "pos": 0,
            "grade": {"correct": correct, "score": 1.0 if correct else 0.0, "error": None, "misconception": None},
            **extra}


def due_after(events):
    s = model.new_state()
    for e in events:
        model.apply(s, e)
    return datetime.fromisoformat(s["kcs"]["9702-2.1.1"]["fsrs"]["due"])


def test_rating_map():
    assert model.fsrs_rating(False, 4, 5) == "again"
    assert model.fsrs_rating(True, 1, 0) == "hard" and model.fsrs_rating(True, 2, 3) == "hard"
    assert model.fsrs_rating(True, 3, 0) == "good" and model.fsrs_rating(True, None, 0) == "good"
    assert model.fsrs_rating(True, 4, 1) == "good" and model.fsrs_rating(True, 4, 2) == "easy"


def test_unsure_success_comes_back_sooner_than_sure_success():
    base = [answer(ts=T0), answer(ts=T0 + timedelta(days=3))]
    unsure = base + [answer(ts=T0 + timedelta(days=10), conf=2)]
    sure = base + [answer(ts=T0 + timedelta(days=10), conf=3)]
    certain = base + [answer(ts=T0 + timedelta(days=10), conf=4)]
    assert due_after(unsure) < due_after(sure) < due_after(certain)


def test_higher_retention_target_schedules_sooner():
    lo = [answer(ts=T0), answer(ts=T0 + timedelta(days=3), retention=0.9)]
    hi = [answer(ts=T0), answer(ts=T0 + timedelta(days=3), retention=0.95)]
    assert due_after(hi) < due_after(lo)


def test_likely_slip_moves_ability_less():
    s1, s2 = model.new_state(), model.new_state()
    model.apply(s1, answer(correct=False))
    model.apply(s2, answer(correct=False, slip_likely=True))
    assert s2["kcs"]["9702-2.1.1"]["theta"] > s1["kcs"]["9702-2.1.1"]["theta"]


def test_new_traits_and_study_days():
    s = model.new_state()
    model.apply(s, answer(conf=4, correct=False))
    model.apply(s, answer(conf=4, ts=T0 + timedelta(minutes=1)))
    model.apply(s, {"type": "session_end", "ts": T0.isoformat(), "answered": 2})
    model.apply(s, {"type": "anki_export", "ts": T0.isoformat(), "cards": ["a"]})
    assert s["traits"]["calibration"]["by_conf"]["4"] == [2, 1]
    assert s["traits"]["hours"]["evening"][0] == 2
    assert s["study_days"] == ["2026-09-29"] and s["anki_last"] == T0.isoformat()
    assert len(s["traits"]["fatigue"]["0"]) == 3


def test_profile_summary_and_advice(tutor):
    for i in range(40):
        model.apply(tutor.state, answer(conf=4, correct=i % 3 == 0, ts=T0 + timedelta(minutes=i)))
    p = profile.summary(tutor.state, tutor.packs, T0)
    assert p["calibration"]["bias"] > 0.1 and p["calibration"]["levels"][0]["level"] == "Certain"
    assert any("overconfident" in tip for tip in profile.advice(p))
    assert len(p["workload"]) == 7


# ---------------- session behaviour ----------------
from datetime import date  # noqa: E402

from tutorlib import policy  # noqa: E402


class Clock:
    def __init__(self, t):
        self.t = t

    def __call__(self):
        return self.t


def _wrong(tutor, view):
    inst = tutor.session["presented"][str(view["n"])]["inst"]
    if view["kind"] == "mcq":
        return f"{view['n']}{next(k for k in inst['options'] if k != inst['answer'])}3"
    return f"{view['n']} = {inst['answer']['value'] * 7.3:.3g} {inst['answer'].get('unit', '')} ~3"


def test_exam_date_and_retention_rise_near_the_exam(tutor):
    kc = "9702-2.1.1"
    assert policy.exam_date(tutor.packs, kc) == policy.AS_2027
    far = policy.target_retention(tutor.state, tutor.packs, kc, datetime(2025, 1, 1, tzinfo=T0.tzinfo))
    near = policy.target_retention(tutor.state, tutor.packs, kc, datetime(2027, 5, 5, tzinfo=T0.tzinfo))
    assert far < 0.9 < near <= 0.97


def test_review_puts_most_forgotten_first(tutor):
    s = tutor.state
    for kc, ts in (("9702-2.1.1", T0 - timedelta(days=60)), ("9702-2.1.4", T0 - timedelta(days=2))):
        model.apply(s, answer(kc=kc, ts=ts))
    assert policy.review_order(s, tutor.packs, T0, ["9702-2.1.4", "9702-2.1.1"])[0] == "9702-2.1.1"


def test_missed_review_idea_comes_back_later_in_the_session(tutor):
    for kc in ("9702-2.1.1", "9702-2.1.4"):
        model.apply(tutor.state, answer(kc=kc, ts=T0 - timedelta(days=40)))
    tutor.start("review", minutes=20)
    act = tutor.next()
    first = act["items"][0]
    kc = tutor.session["presented"][str(first["n"])]["kcs"][0]
    fb = tutor.answer(_wrong(tutor, first))
    assert fb["results"][0].get("relearn")
    block = tutor.session["blocks"][0]
    assert block["kcs"].count(kc) == 2


def test_wrong_answer_asks_for_reflection_and_tag_updates_the_profile(tutor):
    tutor.start("review", minutes=10)
    item = next(i for i in tutor.packs.items_for("9702-2.1.4") if i["kind"] == "numeric")
    n = tutor._present(item, block="practice", phase=None)["n"]
    fb = tutor.answer(_wrong(tutor, {"n": n, "kind": "numeric"}))["results"][0]
    assert fb.get("reflect") is True
    tutor.tag(fb["event"], "misread")
    assert tutor.state["traits"]["errors"]["phys"].get("MISREAD") == 1


def test_break_is_suggested_once_when_accuracy_drops(tutor):
    tutor.start("review", minutes=30)
    item = next(i for i in tutor.packs.items_for("9702-2.1.1") if i["kind"] == "mcq")
    offered = 0
    for _ in range(14):
        n = tutor._present(item, block="practice", phase=None)["n"]
        fb = tutor.answer(_wrong(tutor, {"n": n, "kind": "mcq"}))["results"][0]
        offered += bool(fb.get("break_suggested"))
    assert offered == 1


def test_likely_slip_is_flagged_on_a_fast_miss_of_an_easy_item(tutor):
    kc = "9702-2.1.1"
    tutor.state["kcs"].setdefault(kc, model._new_kc())["theta"] = 3.0
    tutor.state["traits"]["time"]["phys"] = [600.0, 10]  # 60 s per mark usually
    clock = Clock(T0)
    tutor._now = clock
    tutor.start("review", minutes=10)
    item = next(i for i in tutor.packs.items_for(kc) if i["kind"] == "mcq")
    n = tutor._present(item, block="practice", phase=None)["n"]
    inst = tutor.session["presented"][str(n)]["inst"]
    mapped = set((inst.get("distractors") or {}).keys()) if isinstance(inst.get("distractors"), dict) else set()
    wrong = next((k for k in inst["options"] if k != inst["answer"] and k not in mapped), None)
    if wrong is None:
        pytest.skip("every wrong option in the fixture maps to a misconception")
    clock.t = T0 + timedelta(seconds=5)
    fb = tutor.answer(f"{n}{wrong}3")["results"][0]
    ev = [e for e in tutor.vault.events() if e["type"] == "answer"][-1]
    assert ev.get("slip_likely") is True and "retention" in ev


# ---------------- blurting ----------------
from tutorlib import blurt  # noqa: E402


def test_blurt_scores_ideas_by_their_key_terms(tutor):
    res = blurt.score(tutor.packs, "9702-2.1", "Displacement is a vector, distance is a scalar. Velocity has direction.")
    assert "9702-2.1.1" in res["recalled"] and "9702-2.1.4" in res["missed"]


def test_blurt_pulls_forgotten_ideas_forward_and_keeps_a_record(tutor):
    model.apply(tutor.state, answer(kc="9702-2.1.4", ts=T0 - timedelta(days=1)))
    assert datetime.fromisoformat(tutor.state["kcs"]["9702-2.1.4"]["fsrs"]["due"]) > T0
    res = tutor.blurt("9702-2.1", "displacement and velocity are vectors")
    assert "9702-2.1.4" in res["missed"]
    assert datetime.fromisoformat(tutor.state["kcs"]["9702-2.1.4"]["fsrs"]["due"]) <= T0
    assert (tutor.vault.root / res["log"]).exists() and tutor.state["traits"]["blurts"][0] == 1


# ---------------- audit regressions ----------------
from tutorlib import grade, views  # noqa: E402


def test_points_on_a_numeric_question_is_rejected_not_a_crash(tutor):
    tutor.start("review", minutes=10)
    item = next(i for i in tutor.packs.items_for("9702-2.1.4") if i["kind"] == "numeric")
    n = tutor._present(item, block="practice", phase=None)["n"]
    r = tutor.answer(f"{n} pts=1,2")["results"][0]
    assert "expects" in r["error"] and str(n) in tutor.session["presented"]


def test_bad_numbers_are_unreadable_not_crashes():
    for bad in ("5/0", "1e999", "2 x 10^400 m"):
        try:
            grade.parse_quantity(bad)
        except grade.ParseError:
            continue
        raise AssertionError(bad)


def test_a_corrupt_event_line_is_skipped(tutor):
    folder = tutor.vault.tutor / "events"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "2026-09.jsonl").open("a").write('{"type": "session_start", "ts": "2026-09-29T10:00:00+08:00"}\n{"type": "ans')
    events = list(tutor.vault.events())
    assert events and tutor.vault.bad_lines


def test_genanki_can_be_prepared_twice():
    from tutorlib import deps
    deps.ensure("genanki")
    deps.ensure("genanki")


def test_end_without_a_session_logs_nothing(tutor):
    before = len(list(tutor.vault.events()))
    tutor.end()
    assert len(list(tutor.vault.events())) == before


def test_paper_scores_above_the_marks_are_rejected(tutor):
    r = tutor.paper_score("9702_s23_qp_22", "1a=5/2")
    assert r["ok"] is False


def test_retaught_idea_keeps_your_earlier_words(tutor):
    sub = "9702-2.1"
    views.notes_update(tutor.vault.root, tutor.packs, tutor.state, sub,
                       node={"kc": "9702-2.1.1", "note": "- n", "own_words": "my first words", "mistakes": ["m1"]})
    views.notes_update(tutor.vault.root, tutor.packs, tutor.state, sub,
                       node={"kc": "9702-2.1.1", "note": "- n", "own_words": None, "mistakes": ["m2"]})
    text = (tutor.vault.root / views.notes_rel(tutor.packs, sub)).read_text()
    assert "my first words" in text and "- m1" in text and "- m2" in text


def test_plan_with_nothing_to_teach_gives_a_practice_check(tutor):
    tutor.start("lesson", minutes=30, focus=["9702-2.1"])
    tutor.next()
    tutor.respond({"choice": "gaps"})
    for _ in range(10):
        act = tutor.next()
        if act["activity"] == "plan":
            break
        for q in act["items"]:
            inst = tutor.session["presented"][str(q["n"])]["inst"]
            tutor.answer(f"{q['n']}{inst['answer']}4" if q["kind"] == "mcq"
                         else f"{q['n']} = {inst['answer']['value']:#.3g} {inst['answer'].get('unit', '')} ~4")
    tutor.respond({"teach": []})
    kinds = [b["kind"] for b in tutor.session["blocks"]]
    assert kinds[-1] == "practice" and "exit" not in kinds and "node" not in kinds
