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
    assert model.fsrs_rating(False, 3, 0, assisted=True) == "hard"
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


def test_unit_on_a_plain_number_question_keeps_it_open(tutor):  # B-001
    tutor.start("review", minutes=10)
    base = next(i for i in tutor.packs.items_for("9702-2.1.4") if i["kind"] == "numeric")
    item = {**{k: v for k, v in base.items() if k != "template"}, "id": "unitless-probe",
            "answer": {"value": 500, "unit": "", "exact": True}}
    n = tutor._present(item, block="practice", phase=None)["n"]
    r = tutor.answer(f"{n} = 500 kg ~3")["results"][0]
    assert "no unit" in r["error"] and str(n) in tutor.session["presented"]
    r = tutor.answer(f"{n} = 500 ~3")["results"][0]
    assert r["correct"]


def test_retaught_idea_keeps_every_paragraph_of_your_words(tutor):  # B-011
    sub = "9702-2.1"
    words = "FIRST PARAGRAPH\n\nSECOND PARAGRAPH\n\n\nTHIRD"
    for own in (words, None, None):  # re-taught twice
        views.notes_update(tutor.vault.root, tutor.packs, tutor.state, sub,
                           node={"kc": "9702-2.1.1", "note": "- n", "own_words": own})
    text = (tutor.vault.root / views.notes_rel(tutor.packs, sub)).read_text()
    assert views.callout("quote", "In your words", words) in text


def test_same_title_lessons_in_one_minute_get_separate_logs(tutor):  # B-010
    t = datetime.fromisoformat("2026-09-30T12:12:01+08:00")
    a = views.LessonLog.create(tutor.vault.root, "Collision probe", t)
    a.you("KEEP FIRST SESSION NOTES")
    b = views.LessonLog.create(tutor.vault.root, "Collision probe", t + timedelta(seconds=58))
    c = views.LessonLog.create(tutor.vault.root, "Collision probe", t + timedelta(seconds=59))
    assert len({a.rel, b.rel, c.rel}) == 3
    assert "KEEP FIRST SESSION NOTES" in (tutor.vault.root / a.rel).read_text()


@pytest.mark.parametrize("hour,block", [(0, "late night"), (2, "late night"), (4, "late night"), (5, "morning"),
                                        (11, "morning"), (12, "afternoon"), (16, "afternoon"), (17, "evening"),
                                        (22, "late night"), (23, "late night")])
def test_time_blocks_cover_the_small_hours(hour, block):  # B-006
    assert model._time_block(T0.replace(hour=hour)) == block


def test_hinted_answers_do_not_clear_a_misconception():  # B-007
    s = model.new_state()
    miss = {"correct": False, "score": 0, "error": "CONCEPT", "misconception": "m"}
    right = {"correct": True, "score": 1.0, "error": None, "misconception": None}
    model.apply(s, answer(grade=miss))
    for i in (1, 2):
        model.apply(s, answer(ts=T0 + timedelta(minutes=i), grade=right, hinted=True))
    assert s["kcs"]["9702-2.1.1"]["active_misconceptions"] == ["m"]
    for i in (3, 4):
        model.apply(s, answer(ts=T0 + timedelta(minutes=i), grade=right))
    assert s["kcs"]["9702-2.1.1"]["active_misconceptions"] == []


def test_lost_mark_answers_count_as_wrong_in_the_profile():  # B-008
    s = model.new_state()
    model.apply(s, answer(conf=4, grade={"correct": True, "score": 0.5, "error": "NOTATION", "misconception": None}))
    t = s["traits"]
    assert t["calibration"]["by_conf"]["4"] == [1, 0] and t["calibration"]["high_conf_errors"] == 1
    assert t["fatigue"]["0"][1] == 0 and t["hours"][model._time_block(T0)][1] == 0


def test_restart_resumes_the_repair_worked_example_where_it_was(tmp_path):  # B-020
    root = make_vault(tmp_path)
    t = session.Tutor(store.Vault(root), rng=random.Random(5), now=lambda: T0)
    t.start("test", focus=["9702-2.1.4"], replace=True)
    for _ in range(4):
        act = t.next()
        if act["activity"] == "questions":
            t.answer(", ".join(f"{q['n']}?" for q in act["items"]))
        elif act["activity"] == "worked":
            break
    assert act["activity"] == "worked"
    assert t.respond({"step": 1})["ok"]

    again = session.Tutor(store.Vault(root), rng=random.Random(5), now=lambda: T0)  # app restarted
    act = again.next()
    assert act["activity"] == "worked" and act["revealed"] == 1
    assert again.respond({"done": True})["ok"]
    assert again.next()["activity"] != "worked"


def test_a_finished_experiment_decides_the_method(tutor):  # B-009
    s, kc = model.new_state(), "9702-2.1.4"  # procedural physics, never taught: default worked_faded
    exp = {"status": "done", "subject": "phys", "arms": ["worked_faded", "problem_first"], "pairs": [],
           "eligible": {"types": ["procedural"]}, "result": {"decision": "problem_first"}}
    s["experiments"]["phys-1"] = exp
    assert policy.choose_method(s, tutor.packs, kc, random.Random(1)) == ("problem_first", None)
    exp["result"] = {"decision": "no_difference"}
    assert policy.choose_method(s, tutor.packs, kc, random.Random(1)) == ("worked_faded", None)
    exp["result"], exp["eligible"] = {"decision": "problem_first"}, {"types": ["conceptual"]}  # not this kind of idea
    assert policy.choose_method(s, tutor.packs, kc, random.Random(1)) == ("worked_faded", None)
    exp["eligible"] = {"types": ["procedural"]}
    s["kcs"][kc] = {**model._new_kc(), "n": 3, "active_misconceptions": ["m2"]}  # a misconception still wins
    assert policy.choose_method(s, tutor.packs, kc, random.Random(1)) == ("refutation", None)


def test_ending_a_session_refreshes_notes_for_every_idea_answered(tutor):  # B-026
    rel = views.notes_update(tutor.vault.root, tutor.packs, tutor.state, "9702-2.1", node={"kc": "9702-2.1.1", "note": "- n"})
    path = tutor.vault.root / rel
    path.write_text(path.read_text().replace("Progress:", "Progress STALE:"))
    tutor.start("autopilot", minutes=50)
    item = next(i for i in tutor.packs.items_for("9702-2.1.1") if i["kind"] == "mcq")
    n = tutor._present(item, block="review", phase=None)["n"]
    tutor.answer(f"{n}{tutor.session['presented'][str(n)]['inst']['answer']}3")
    tutor.end()
    assert "STALE" not in path.read_text()
