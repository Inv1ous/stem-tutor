import random
from datetime import datetime, timedelta

import pytest

from fixtures import make_vault
from tutorlib import experiments, grade, policy, session, store

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
        elif act["activity"] in ("teach", "worked", "walkthrough", "refute"):
            tutor.respond({"done": True})  # as the app does on Continue / after the last step
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


def test_now_note_mirrors_open_items_with_images_then_feedback(tutor):
    tutor.start("autopilot", minutes=50)
    item = dict(tutor.packs.items_for("9702-2.1.1")[0], image="Assets/mcq/x.png", id="img1")
    tutor._questions({"kind": "practice"}, 0, [item])
    now = (tutor.vault.root / "Now.md").read_text()
    assert "![[Assets/mcq/x.png]]" in now and "Which quantity is a vector?" in now
    n = max(int(k) for k in tutor.session["presented"])
    inst = tutor.session["presented"][str(n)]["inst"]
    tutor.answer(f"{n}{inst['answer']}3")
    now = (tutor.vault.root / "Now.md").read_text()
    assert f"Q{n} — correct" in now


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


# ---------- lesson mode (probe → plan → teach, notes grow) ----------
def _drive_lesson(tutor, first_wrong=True, own_words="Displacement has a direction; distance does not."):
    seen, wrong_left = [], {"9702-2.1.1": first_wrong, "9702-2.1.4": first_wrong}
    for _ in range(80):
        act = tutor.next()
        kind = act["activity"]
        seen.append((kind, act.get("phase") or act.get("part") or act.get("purpose")))
        if kind == "end":
            break
        if kind == "choose":
            tutor.respond({"choice": "gaps"})
        elif kind == "plan":
            tutor.respond({"teach": act["default_teach"]})
        elif kind == "own_words":
            tutor.respond({"text": own_words})
        elif kind == "worked":
            for i in range(1, len(act["steps"]) + 1):
                tutor.respond({"step": i})
            tutor.respond({"done": True})
        elif kind in ("explain", "refute", "stuck"):
            tutor.respond({})
        elif kind in ("questions", "awaiting"):
            kc = tutor.session["presented"][str(act["items"][0]["n"])]["kcs"][0]
            bad = act.get("phase") == "sweep" or (act.get("phase") == "check" and wrong_left.get(kc))
            if bad:
                wrong_left[kc] = False
            _answer_all(tutor, act, good=not bad)
    return seen


def test_lesson_runs_goal_probe_plan_then_each_idea(tutor):
    plan = tutor.start("lesson", minutes=40, focus=["9702-2.1"])
    assert [b["kind"] for b in plan["blocks"]] == ["goal", "sweep", "plan"]
    seen = _drive_lesson(tutor)
    kinds = [k for k, _ in seen]
    assert kinds[0] == "choose" and "plan" in kinds and kinds[-1] == "end"
    assert ("explain", "motivate") in seen and ("explain", "establish") in seen and ("questions", "check") in seen
    assert kinds.index("plan") < kinds.index("explain")
    assert any(e["type"] == "node_done" and e["kc"] == "9702-2.1.1" for e in tutor.vault.events())


def test_lesson_grows_my_notes_with_own_words_and_mistakes(tutor):
    tutor.start("lesson", minutes=40, focus=["9702-2.1"])
    _drive_lesson(tutor)
    notes = next((tutor.vault.root / "My Notes").rglob("*.md")).read_text()
    assert "```mermaid" in notes and "Distance, displacement, speed, velocity" in notes
    assert "In your words" in notes and "Displacement has a direction" in notes
    assert "Watch out (your mistakes)" in notes
    assert notes.index("stem-tutor:node 9702-2.1.1") < notes.index("stem-tutor:node 9702-2.1.4")


def test_lesson_log_never_shows_a_key_before_the_answer(tutor):
    tutor.start("lesson", minutes=40, focus=["9702-2.1"])
    _drive_lesson(tutor)
    log = next((tutor.vault.root / "Lessons").glob("*.md")).read_text()
    blocks = log.split("\n\n")
    questions = [b for b in blocks if b.startswith("> [!question] Q")]
    assert questions and not any("Correct answer" in b for b in questions)
    first_q = log.index("> [!question] Q1 ·")
    assert log.index("Q1 — ") > first_q  # the answer callout comes after the question


def test_goal_scratch_skips_the_probe_and_teaches_everything(tutor):
    tutor.start("lesson", minutes=40, focus=["9702-2.1"])
    tutor.next()
    tutor.respond({"choice": "scratch"})
    act = tutor.next()
    assert act["activity"] == "plan" and act["default_teach"] == ["9702-2.1.1", "9702-2.1.4"]


def test_image_only_mcq_feedback_shows_the_letter(tutor):
    tutor.start("review", minutes=10)
    item = {"id": "img", "kcs": ["9702-2.1.1"], "kind": "mcq", "stem": "See figure.", "options": None, "answer": "C",
            "image": "Assets/mcq/x.png", "difficulty": 3, "marks": 1, "tier": "extra"}
    n = tutor._present(item, block="practice", phase=None)["n"]
    fb = tutor.answer(f"{n}C3")
    assert fb["results"][0]["correct"] and fb["results"][0]["answer"] == "C"


def test_short_answer_with_every_keyword_still_waits_for_judgement(tutor):  # B-024
    item = {"id": "s2", "kcs": ["9702-2.1.1"], "kind": "short", "difficulty": 3, "marks": 2, "stem": "Define displacement.",
            "rubric": [{"point": "distance", "keywords": [["distance"]]}, {"point": "direction", "keywords": [["direction"]]}]}
    tutor.start("review", minutes=10)
    n = tutor._present(item, block="practice", phase=None)["n"]
    r = tutor.answer(f"{n} = distance without a direction")["results"][0]
    assert r["pending_judgement"] and r["matched_score"] == 1.0 and str(n) in tutor.session["presented"]


@pytest.mark.parametrize("one_at_a_time", [False, True])
def test_retest_score_goes_to_the_idea_retested_even_on_a_multi_idea_item(tutor, one_at_a_time):  # B-027
    tutor.one_at_a_time = one_at_a_time
    for it in tutor.packs.items_for("9702-2.1.4"):  # every item for it now lists another idea first
        it["kcs"] = ["9702-2.1.1", "9702-2.1.4"]
    tutor.start("autopilot", minutes=50)
    tutor.end()
    tutor.log({"type": "exp_start", "exp": "E1", "subject": "phys", "arms": ["worked_faded", "problem_first"],
               "eligible": {"types": ["procedural"]}, "target_pairs": 4})
    tutor.log({"type": "exp_assign", "exp": "E1", "kc": "9702-2.1.4", "arm": "worked_faded", "pair": 0})
    tutor.clock.t = T0 + timedelta(days=8)
    assert tutor.start("autopilot", minutes=50)["blocks"][0]["kind"] == "retest"
    for _ in range(4):
        act = tutor.next()
        if act.get("block") != "retest":
            break
        _answer_all(tutor, act, good=True)
    scores = [e for e in tutor.vault.events() if e["type"] == "exp_score"]
    assert [s["kc"] for s in scores] == ["9702-2.1.4"]
    assert experiments.retests_due(tutor.state, tutor.clock.t) == []


def test_expression_answers_unicode_right_and_unreadable_stays_open(tutor):  # B-034
    item = {"id": "e1", "kcs": ["9702-2.1.4"], "kind": "expression", "difficulty": 3, "marks": 1,
            "stem": "Write v^2 in terms of u, a and s.", "answer": {"expr": "u**2 + 2*a*s"}}
    tutor.start("review", minutes=10)
    n = tutor._present(item, block="practice", phase=None)["n"]
    r = tutor.answer(f"{n} = u² + 2as @@ ~3")["results"][0]
    assert "could not read" in r["error"] and str(n) in tutor.session["presented"]
    r = tutor.answer(f"{n} = u² + 2as ~3")["results"][0]
    assert r["correct"] and str(n) not in tutor.session["presented"]


def test_ai_help_counts_as_a_hint_and_is_refused_on_no_help_checks(tutor):  # B-033
    tutor.start("review", minutes=10)
    items = [i for i in tutor.packs.items_for("9702-2.1.1") if i["kind"] == "mcq"]
    n = tutor._present(items[0], block="practice", phase=None)["n"]
    assert tutor.ai_help()["ok"] and tutor.session["presented"][str(n)]["hinted"]
    m = tutor._present(items[1], block="exit", phase=None, unassisted=True)["n"]
    assert "refused" in tutor.ai_help() and not tutor.session["presented"][str(m)]["hinted"]


# ---------- one question at a time (the terminal app) ----------
@pytest.fixture
def app_tutor(tmp_path):
    """The engine as the terminal app runs it: a batch of questions comes on screen one at a time."""
    clock = Clock(T0)
    t = session.Tutor(store.Vault(make_vault(tmp_path)), rng=random.Random(0), now=clock, one_at_a_time=True)
    t.clock = clock
    return t


def test_one_at_a_time_a_question_is_open_only_once_it_is_on_screen(app_tutor):
    t = app_tutor
    t.start("test", minutes=40, focus=["9702-2.1"])
    first, = t.next()["items"]  # a no-help check on two ideas: the app shows one question
    (m, waiting), = t.session["queue"].items()
    assert list(t.session["presented"]) == [str(first["n"])] and int(m) == first["n"] + 1
    assert f"Q{m} " not in (t.vault.root / "Now.md").read_text() + (t.vault.root / t.session["log"]).read_text()
    assert "refused" in t.ai_help()  # the no-help check on screen: no AI help until it is answered
    t.clock.t = T0 + timedelta(minutes=5)
    t.answer(f"{first['n']}?")
    assert t.ai_help() == {"ok": True}  # marked: ask anything about it, though the next no-help question waits
    assert not waiting["hinted"] and f"Q{m} " not in (t.vault.root / "Now.md").read_text()
    second, = t.next()["items"]
    assert str(second["n"]) == m and not t.session["queue"] and second["unassisted"]
    assert f"Q{m} " in (t.vault.root / "Now.md").read_text() and f"Q{m} " in (t.vault.root / t.session["log"]).read_text()
    t.clock.t = T0 + timedelta(minutes=6)
    t.answer(f"{m}?")
    assert [e["seconds"] for e in t.vault.events() if e["type"] == "answer"] == [300, 60]  # its clock starts when shown


def test_one_at_a_time_help_on_one_question_does_not_count_against_the_next(app_tutor):
    t = app_tutor
    t.start("autopilot", minutes=50)
    first, = t.next()["items"]  # a pretest: two questions on one idea, hints allowed
    waiting, = t.session["queue"].values()
    assert t.ai_help() == {"ok": True} and t.session["presented"][str(first["n"])]["hinted"]
    _answer_all(t, {"items": [first]})
    _answer_all(t, t.next())
    assert [e["hinted"] for e in t.vault.events() if e["type"] == "answer"] == [True, False] and not waiting["hinted"]


def test_one_at_a_time_takes_over_a_batch_opened_by_the_chat_interface(tutor):
    tutor.start("test", minutes=40, focus=["9702-2.1"])
    both = tutor.next()["items"]
    assert len(both) == 2  # the chat interface (and the app before 1.2.3) opens the whole batch
    t = session.Tutor(tutor.vault, rng=random.Random(0), now=tutor.clock, one_at_a_time=True)
    first, = t.next()["items"]
    assert first["n"] == both[0]["n"] and list(t.session["queue"]) == [str(both[1]["n"])]
    t.answer(f"{first['n']}?")
    assert t.ai_help() == {"ok": True}
    assert t.next()["items"][0]["n"] == both[1]["n"]


def test_one_at_a_time_asks_the_same_questions_in_the_same_order(tmp_path):
    """Showing a batch one question at a time changes when each is seen, never which questions are asked."""
    def run(one_at_a_time):
        clock = Clock(T0)
        t = session.Tutor(store.Vault(make_vault(tmp_path / str(one_at_a_time))), rng=random.Random(3), now=clock,
                          one_at_a_time=one_at_a_time)
        sessions = []
        for day, mode, focus in [(0, "test", ["9702-2.1"]), (1, "diagnose", ["9702-2.1"]), (4, "autopilot", None),
                                 (8, "review", None), (9, "lesson", ["9702-2.1"]), (15, "autopilot", None)]:
            clock.t = T0 + timedelta(days=day)
            t.start(mode, minutes=40, focus=focus)
            for _ in range(120):
                act = t.next()
                if act["activity"] in ("end", "no_session"):
                    break
                if act["activity"] in ("questions", "awaiting"):
                    for q in act["items"]:
                        _answer_all(t, {"items": [q]}, good=q["n"] % 3 != 0)
                else:
                    t.respond({"done": True})
            sessions.append(t.end()["answered"])
        assert t.state == t._fold()
        return sessions, [(e["item"], e["grade"]["score"], e["phase"]) for e in t.vault.events() if e["type"] == "answer"]
    batch, single = run(False), run(True)
    assert single == batch and all(batch[0])  # every session asked something


# ---------- the answer as shown ----------
def _shown(value, **answer):
    return session._display_answer({"kind": "numeric", "answer": {"value": value, **answer}})


@pytest.mark.parametrize("value,answer,shown", [
    (11.03625, {"unit": "m", "sf_ok": [2, 3]}, "11.0 m"),  # 0.5 × 9.81 × 1.5², shown at the most figures allowed
    (2.5, {"sf": 3}, "2.50"),
    (0.03, {"sf": 3}, "0.0300"),
    (-0.5, {"unit": "m s^-2", "sf": 2}, "-0.50 m s^-2"),
])
def test_shown_answer_keeps_its_significant_zeros(value, answer, shown):
    assert _shown(value, **answer) == shown


@pytest.mark.parametrize("value,sf,shown", [
    (120, 3, "120"), (100.0, 3, "100"), (99.96, 3, "100"), (37.0, 2, "37"), (5.0, 1, "5"), (0.0, 3, "0")])
def test_shown_whole_number_has_no_decimal_point(value, sf, shown):
    assert _shown(value, sf=sf) == shown


@pytest.mark.parametrize("value,sf,shown", [
    (120, 2, "1.2e2"),  # plain 120 cannot show that only two figures count
    (4000.0, 2, "4.0e3"), (4000.0, 1, "4e3"), (468750.0, 3, "4.69e5"), (999.6, 3, "1.00e3"),
    (1.2e-3, 3, "1.20e-3"), (2.4e-6, 3, "2.40e-6"),
])
def test_shown_answer_too_big_or_small_for_plain_digits_is_in_standard_form(value, sf, shown):
    assert _shown(value, sf=sf) == shown


@pytest.mark.parametrize("value,shown", [(5.0, "5"), (117, "117"), (0.5, "0.5"), (-3.0, "-3")])
def test_shown_exact_answer_is_not_padded(value, shown):
    assert _shown(value, exact=True) == shown


@pytest.mark.parametrize("value,shown", [
    (12.25, "12.25"), (1200.0, "1200"), (3500, "3500"), (123456.789, "123456.789"),  # not rounded to 3 s.f.
    (0.1 + 0.2, "0.3"), (1.1 * 1.1, "1.21"), (-0.0, "0"),  # no float noise from template arithmetic
    (2.5e-7, "2.5e-7"), (3e15, "3e15"),  # too small or too big for plain digits: standard form, as it is typed
])
def test_shown_exact_answer_is_in_full(value, shown):
    assert _shown(value, exact=True) == shown


@pytest.mark.parametrize("value,answer", [
    (1.5, {"unit": "mm", "sf_ok": [3]}), (7.0, {"unit": "N", "sf_ok": [2, 3]}), (40000.0, {"unit": "J", "sf_ok": [2, 3]}),
    (120, {"sf": 2}), (2.4e-6, {"unit": "m^2", "sf_ok": [1, 2, 3]}), (12.0, {"exact": True}),
    (12.25, {"exact": True}), (1200.0, {"exact": True}), (0.1 + 0.2, {"exact": True}), (2.5e-7, {"unit": "m", "exact": True}),
])
def test_shown_answer_typed_back_earns_full_marks(value, answer):
    item = {"kind": "numeric", "answer": {"value": value, **answer}}
    assert grade.grade_item(item, {"kind": "value", "value": session._display_answer(item)})["score"] == 1.0


def test_answer_shown_after_a_mark_lost_for_sig_figs_has_the_figures_wanted(tutor):
    tutor.start("long", minutes=20, focus=["9702-2.1.4"])
    item = next(i for i in tutor.packs.items_for("9702-2.1.4") if i["id"] == "9702-2.1-i03")  # 4.0 m s-2, 2 or 3 s.f.
    n = tutor._present(item, block="practice", phase=None)["n"]
    r = tutor.answer(f"{n} = 4 m s-2 ~3")["results"][0]
    assert r["partial"] and "1 s.f." in r["detail"] and r["answer"] == "4.00 m s-2"
