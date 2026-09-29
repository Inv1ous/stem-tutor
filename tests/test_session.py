import random
from datetime import datetime, timedelta

import pytest

from fixtures import make_vault
from tutorlib import experiments, policy, session, store

T0 = datetime.fromisoformat("2026-09-29T17:00:00+08:00")  # Almanac week 5


class Clock:
    def __init__(self, t):
        self.t = t

    def __call__(self):
        return self.t


@pytest.fixture
def tutor(tmp_path):
    clock = Clock(T0)
    t = session.Tutor(store.Vault(make_vault(tmp_path)), rng=random.Random(0), now=clock)
    t.clock = clock
    return t


# ---------- policy ----------
def test_current_week_from_plan():
    plan = {"start": "2026-09-01", "week2_monday": "2026-09-07"}
    assert policy.current_week(plan, datetime.fromisoformat("2026-09-03T10:00:00+08:00")) == 1
    assert policy.current_week(plan, T0) == 5


@pytest.mark.parametrize("kc_type,theta,mis,expected", [
    ("procedural", 0.0, [], "worked_faded"),
    ("conceptual", 0.0, [], "pretest_explain"),
    ("factual", 0.0, [], "pretest_explain"),
    ("conceptual", 0.9, [], "problem_first"),
    ("procedural", 0.9, [], "problem_first"),
    ("procedural", 0.9, ["m2"], "refutation"),
])
def test_default_method_policy(kc_type, theta, mis, expected):
    assert policy.default_method({"type": kc_type}, {"theta": theta, "active_misconceptions": mis}) == expected


# ---------- session flow ----------
def test_autopilot_plan_learns_prerequisite_first(tutor):
    plan = tutor.start("autopilot", minutes=50)
    learn = [b for b in plan["blocks"] if b["kind"] == "learn"]
    assert [b["kc"] for b in learn][:2] == ["9702-2.1.1", "9702-2.1.4"]
    assert plan["blocks"][-1]["kind"] == "exit"


def test_pretest_questions_hide_answers(tutor):
    tutor.start("autopilot", minutes=50)
    act = tutor.next()
    assert act["activity"] == "questions" and act["phase"] == "pretest"
    for q in act["items"]:
        assert "answer" not in q and "distractors" not in q and "explanation" not in q
        assert q["n"] >= 1 and q["stem"]


def test_answer_reveals_key_logs_event_and_updates_state(tutor):
    tutor.start("autopilot", minutes=50)
    act = tutor.next()
    q = act["items"][0]
    fb = tutor.answer(f"{q['n']}A4" if q["kind"] == "mcq" else f"{q['n']} = 1 ~2")
    assert fb["results"][0]["n"] == q["n"] and "answer" in fb["results"][0]
    assert any(e["type"] == "answer" for e in tutor.vault.events())
    assert tutor.state["kcs"]["9702-2.1.1"]["n"] == 1


def _answer_all(tutor, act, good=True):
    parts = []
    for q in act["items"]:
        inst = tutor.session["presented"][str(q["n"])]["inst"]
        if q["kind"] == "mcq":
            parts.append(f"{q['n']}{inst['answer'] if good else next(k for k in inst['options'] if k != inst['answer'])}3")
        else:
            v = inst["answer"]["value"] if good else inst["answer"]["value"] * 7.3
            parts.append(f"{q['n']} = {v:.3g} {inst['answer'].get('unit', '')} ~3")
    return tutor.answer(", ".join(parts))


def test_after_pretest_method_is_chosen_and_teaching_follows(tutor):
    tutor.start("autopilot", minutes=50)
    _answer_all(tutor, tutor.next(), good=False)
    act = tutor.next()
    assert act["activity"] == "teach"
    assert act["method"] == "pretest_explain"  # conceptual KC, novice
    assert act["note"].endswith(".md") and "card" in act
    assert any(e["type"] == "method" for e in tutor.vault.events())


def test_pending_items_are_re_served_until_answered(tutor):
    tutor.start("autopilot", minutes=50)
    first = tutor.next()
    again = tutor.next()
    assert again["activity"] == "awaiting" and [q["n"] for q in again["items"]] == [q["n"] for q in first["items"]]


def test_full_session_reaches_exit_and_end(tutor):
    tutor.start("autopilot", minutes=50)
    seen = []
    for _ in range(40):
        act = tutor.next()
        seen.append((act["activity"], act.get("block")))
        if act["activity"] == "end":
            break
        if act["activity"] in ("questions", "awaiting"):
            _answer_all(tutor, act, good=True)
    assert seen[-1][0] == "end"
    assert ("questions", "exit") in seen
    summary = tutor.end()
    assert summary["answered"] > 0
    assert tutor.session is None
    assert any(e["type"] == "session_end" for e in tutor.vault.events())


def test_hint_marks_item_hinted_and_is_refused_in_exit(tutor):
    tutor.start("autopilot", minutes=50)
    act = tutor.next()
    n = act["items"][0]["n"]
    h = tutor.hint(n)
    assert h["level"] == 1 and h["hint"]
    assert tutor.session["presented"][str(n)]["hinted"] is True
    tutor.session["presented"][str(n)]["unassisted"] = True
    assert "refused" in tutor.hint(n)


def test_review_block_when_kc_due(tutor):
    tutor.start("autopilot", minutes=50)
    _answer_all(tutor, tutor.next(), good=True)
    tutor.end()
    tutor.clock.t = T0 + timedelta(days=30)
    plan = tutor.start("autopilot", minutes=50)
    assert plan["blocks"][0]["kind"] == "review" and "9702-2.1.1" in plan["blocks"][0]["kcs"]


def test_short_answer_needing_judgement_stays_pending_until_judged(tutor):
    item = {"id": "s1", "kcs": ["9702-2.1.1"], "kind": "short", "difficulty": 3, "marks": 2, "stem": "Define displacement.",
            "rubric": [{"point": "distance", "keywords": [["distance"]]}, {"point": "direction", "keywords": [["direction"]]}]}
    tutor.start("review", minutes=10)
    n = tutor._present(item, block="practice", phase=None)["n"]
    fb = tutor.answer(f"{n} = the distance moved")
    assert fb["results"][0]["pending_judgement"]
    assert str(n) in tutor.session["presented"]
    fb = tutor.answer(f"{n} = the distance moved", judge={n: 0.5})
    assert fb["results"][0]["score"] == 0.5 and str(n) not in tutor.session["presented"]


def test_experiment_retest_scores_after_three_items(tutor):
    tutor.start("autopilot", minutes=50)
    tutor.end()
    tutor.log({"type": "exp_start", "exp": "E1", "subject": "phys", "arms": ["worked_faded", "problem_first"],
               "eligible": {"types": ["conceptual"]}, "target_pairs": 4})
    tutor.log({"type": "exp_assign", "exp": "E1", "kc": "9702-2.1.1", "arm": "worked_faded", "pair": 0})
    tutor.clock.t = T0 + timedelta(days=8)
    plan = tutor.start("autopilot", minutes=50)
    assert plan["blocks"][0]["kind"] == "retest"
    for _ in range(3):
        act = tutor.next()
        assert act["block"] == "retest" and all(q["unassisted"] for q in act["items"])
        _answer_all(tutor, act, good=True)
        if any(e["type"] == "exp_score" for e in tutor.vault.events()):
            break
    scores = [e for e in tutor.vault.events() if e["type"] == "exp_score"]
    assert scores and scores[0]["kc"] == "9702-2.1.1" and scores[0]["score"] == 1.0
    assert experiments.retests_due(tutor.state, tutor.clock.t) == []


def test_state_survives_rebuild(tutor):
    tutor.start("autopilot", minutes=50)
    _answer_all(tutor, tutor.next(), good=True)
    before = tutor.state["kcs"]
    tutor.rebuild()
    assert tutor.state["kcs"] == before


def test_mismatched_response_kind_is_rejected_and_kept_open(tutor):
    tutor.start("autopilot", minutes=50)
    act = tutor.next()
    mcq = next(q for q in act["items"] if q["kind"] == "mcq")
    fb = tutor.answer(f"{mcq['n']} = 19.6 m ~3")
    assert "expects" in fb["results"][0]["error"]
    assert str(mcq["n"]) in tutor.session["presented"]
    assert not any(e["type"] == "answer" for e in tutor.vault.events())


def test_long_mode_presents_structured_and_scheme_after_attempt(tutor):
    tutor.start("long", minutes=20, focus=["9702-2.1.4"])
    act = tutor.next()
    q = act["items"][0]
    assert q["kind"] == "structured" and q["scheme_points"] == 3 and "scheme" not in q
    sch = tutor.scheme(q["n"])
    assert [p["i"] for p in sch["scheme"]] == [1, 2, 3] and sch["scheme"][0]["mark"] == "M1"
    fb = tutor.answer(f"{q['n']} pts=1,2")
    assert fb["results"][0]["score"] == pytest.approx(2 / 3, abs=0.01)


def test_paper_list_and_score_logs_per_question(tutor):
    papers = tutor.paper_list("9702")
    assert papers[0]["id"] == "9702_s23_qp_22"
    r = tutor.paper_score("9702_s23_qp_22", "1a=2/2, 1b=1/3")
    assert r["score"] == 3 and r["max"] == 5 and r["weakest"][0]["kc"] == "9702-2.1.4"
    evs = [e for e in tutor.vault.events() if e["type"] == "answer" and e["block"] == "paper"]
    assert len(evs) == 2 and evs[1]["grade"]["score"] == pytest.approx(1 / 3, abs=0.01)
    assert any(e["type"] == "paper_result" for e in tutor.vault.events())


def test_only_new_objectives_introduce_topics(tutor):
    tutor.packs.plan["weeks"]["5"][0]["type"] = "REVISE"
    plan = tutor.start("autopilot", minutes=50)
    assert not [b for b in plan["blocks"] if b["kind"] == "learn"]


def test_question_sheet_mirrors_open_items_with_images(tutor):
    tutor.start("autopilot", minutes=50)
    item = dict(tutor.packs.items_for("9702-2.1.1")[0], image="Assets/mcq/x.png", id="img1")
    tutor._questions({"kind": "practice"}, 0, [item])
    sheet = (tutor.vault.root / "Question Sheets" / "Current.md").read_text()
    assert "![[Assets/mcq/x.png]]" in sheet and "Which quantity is a vector?" in sheet
    n = max(int(k) for k in tutor.session["presented"])
    inst = tutor.session["presented"][str(n)]["inst"]
    tutor.answer(f"{n}{inst['answer']}3")
    assert "Which quantity" not in (tutor.vault.root / "Question Sheets" / "Current.md").read_text() or \
        len(tutor.session["presented"]) > 0


def test_audit_log_records_presentations_and_answers_with_turn(tutor, monkeypatch):
    monkeypatch.setenv("STEM_TUTOR_AUDIT", "1")
    monkeypatch.setenv("STEM_TUTOR_TURN", "3")
    tutor.start("autopilot", minutes=50)
    act = tutor.next()
    q = act["items"][0]
    inst = tutor.session["presented"][str(q["n"])]["inst"]
    monkeypatch.setenv("STEM_TUTOR_TURN", "4")
    tutor.answer(f"{q['n']}{inst['answer']}3" if q["kind"] == "mcq" else f"{q['n']} = 1 ~2")
    import json
    rows = [json.loads(l) for l in (tutor.vault.tutor / "audit.jsonl").read_text().splitlines()]
    present = next(r for r in rows if r["event"] == "present" and r["n"] == q["n"])
    answered = next(r for r in rows if r["event"] == "answer" and r["n"] == q["n"])
    assert present["turn"] == 3 and answered["turn"] == 4 and present["key"]


# ---------- test-prep mode ----------
def test_test_mode_expands_subtopic_and_sweeps_each_kc_once(tutor):
    plan = tutor.start("test", minutes=60, focus=["9702-2.1"])
    assert plan["blocks"] == [{"kind": "sweep", "kcs": ["9702-2.1.1", "9702-2.1.4"]}]
    act = tutor.next()
    assert act["block"] == "sweep" and len(act["items"]) == 2 and all(q["unassisted"] for q in act["items"])
    assert sorted(tutor.session["presented"][str(q["n"])]["kcs"][0] for q in act["items"]) == ["9702-2.1.1", "9702-2.1.4"]


def test_test_mode_repairs_missed_kcs_then_exit(tutor):
    tutor.start("test", minutes=60, focus=["9702-2.1"])
    _answer_all(tutor, tutor.next(), good=False)
    act = tutor.next()
    kinds = [b["kind"] for b in tutor.session["blocks"]]
    assert kinds[:3] == ["sweep", "learn", "learn"] and kinds[-1] == "exit"
    assert act["activity"] in ("teach", "refute", "worked")  # sweep served as the pretest
    assert set(tutor.state["gaps"]) == {"9702-2.1.1", "9702-2.1.4"}


def test_test_mode_confident_success_skips_repair_and_stretches(tutor):
    tutor.start("test", minutes=60, focus=["9702-2.1"])
    act = tutor.next()
    parts = []
    for q in act["items"]:
        inst = tutor.session["presented"][str(q["n"])]["inst"]
        parts.append(f"{q['n']}{inst['answer']}4" if q["kind"] == "mcq" else f"{q['n']} = {inst['answer']['value']:.3g} {inst['answer'].get('unit', '')} ~4")
    tutor.answer(", ".join(parts))
    tutor.next()
    blocks = tutor.session["blocks"]
    assert not [b for b in blocks if b["kind"] == "learn"]
    assert blocks[1]["kind"] == "practice" and blocks[1]["target"] < 0.8


def test_unassisted_success_closes_a_gap(tutor):
    tutor.log({"type": "gaps", "add": ["9702-2.1.1"]})
    tutor.start("review", minutes=10)
    item = tutor.packs.items_for("9702-2.1.1")[0]
    n = tutor._present(item, block="exit", phase=None, unassisted=True)["n"]
    inst = tutor.session["presented"][str(n)]["inst"]
    tutor.answer(f"{n}{inst['answer']}3")
    assert "9702-2.1.1" not in tutor.state["gaps"]


def test_unreadable_numeric_answer_stays_open_and_others_are_graded(tutor):
    tutor.start("long", minutes=20, focus=["9702-2.1.4"])
    item = next(i for i in tutor.packs.items_for("9702-2.1.4") if i["kind"] == "numeric")
    n = tutor._present(item, block="practice", phase=None)["n"]
    fb = tutor.answer(f"{n} = about twenty")
    assert "resend" in fb["results"][0]["error"] and str(n) in tutor.session["presented"]
    inst = tutor.session["presented"][str(n)]["inst"]
    fb = tutor.answer(f"{n} = ({inst['answer']['value']:.3g}) {inst['answer'].get('unit', '')} ~3")
    assert fb["results"][0]["correct"] and "error" not in fb["results"][0]


def test_feedback_names_the_error_code_separately_from_request_errors(tutor):
    tutor.start("test", minutes=30, focus=["9702-2.1"])
    act = tutor.next()
    fb = _answer_all(tutor, act, good=False)
    assert all("error" not in r and "error_code" in r for r in fb["results"])
    again = tutor.answer(f"{act['items'][0]['n']}A3")
    assert "already" in again["results"][0]["error"]


def test_start_refuses_topics_without_questions_and_keeps_open_session(tutor):
    tutor.start("test", minutes=30, focus=["9702-2.1"])
    sid = tutor.session["id"]
    out = tutor.start("test", minutes=30, focus=["9702-3"])
    assert out["ok"] is False and "No questions" in out["error"] and tutor.session["id"] == sid


def test_start_does_not_discard_a_session_in_progress_unless_replaced(tutor):
    tutor.start("test", minutes=30, focus=["9702-2.1"])
    _answer_all(tutor, tutor.next(), good=True)
    sid = tutor.session["id"]
    out = tutor.start("review", minutes=30)
    assert out["ok"] is False and out["open_session"]["answered"] == 2 and tutor.session["id"] == sid
    assert tutor.start("review", minutes=30, replace=True)["session"] != sid
