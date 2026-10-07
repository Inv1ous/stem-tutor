import json
import random
from datetime import datetime, timedelta

import pytest

from fixtures import make_vault
from tutorlib import report, session, store

T0 = datetime.fromisoformat("2026-09-29T17:00:00+08:00")


@pytest.fixture
def tutor(tmp_path):
    return session.Tutor(store.Vault(make_vault(tmp_path)), rng=random.Random(0), now=lambda: T0)


def _study(tutor, wrong=False):
    tutor.start("autopilot", minutes=50)
    act = tutor.next()
    parts = []
    for q in act["items"]:
        inst = tutor.session["presented"][str(q["n"])]["inst"]
        if q["kind"] == "mcq":
            pick = "A" if wrong and inst["answer"] != "A" else inst["answer"]
            parts.append(f"{q['n']}{pick}4")
        else:
            parts.append(f"{q['n']} = {inst['answer']['value'] * (5 if wrong else 1):.3g} {inst['answer'].get('unit', '')} ~4")
    tutor.answer(", ".join(parts))
    return tutor.end()


def test_brief_is_compact_and_informative(tutor):
    b = report.brief(tutor)
    assert b["week"] == 5
    assert b["next_sitting"]["label"] == "9702-AS" and b["next_sitting"]["days"] > 200
    assert "Kinematics" in " ".join(b["week_objectives"])
    assert len(json.dumps(b)) < 900


def test_session_note_written_with_callouts(tutor):
    summary = _study(tutor)
    path = report.session_note(tutor, summary["session"])
    text = (tutor.vault.root / path).read_text()
    assert path.startswith("Sessions/") and ("> [!success]" in text or "> [!failure]" in text) and "Accuracy" in text


def test_profile_note_contains_traits_and_is_lint_clean(tutor):
    from tutorlib import lint
    _study(tutor, wrong=True)
    path = report.profile_note(tutor)
    text = (tutor.vault.root / path).read_text()
    for heading in ("What the tutor has recorded", "What it has worked out", "What the tutor has adjusted for you",
                    "Exam readiness", "Weak spots", "What it never does", "Mistakes"):
        assert heading in text
    assert lint.lint(text) == []


def test_today_note_lists_plan(tutor):
    path = report.today_note(tutor)
    text = (tutor.vault.root / path).read_text()
    assert "Learn" in text and "9702-2.1.1" in text


def test_brief_caps_missing_pack_list(tutor, monkeypatch):
    from tutorlib import policy
    monkeypatch.setattr(policy, "missing_packs", lambda p, now: [f"X-{i}" for i in range(50)])
    b = report.brief(tutor)
    m = b["unbuilt_subtopics_all_subjects"]
    assert m["count"] == 50 and m["next"] == ["X-0", "X-1", "X-2", "X-3", "X-4"] and "unrelated" in m["say"]


def test_unicode_scripts_become_latex_for_notes():
    assert report.to_note_math("H₂SO₄ and 8 × 10² kg m⁻³") == "H$_{2}$SO$_{4}$ and 8 × 10$^{2}$ kg m$^{-3}$"
    assert report.to_note_math("plain $x^2$ stays") == "plain $x^2$ stays"


def test_session_note_accuracy_counts_lost_marks_as_the_session_does(tutor):  # B-008
    tutor.start("review", minutes=10)
    item = next(i for i in tutor.packs.items_for("9702-2.1.4") if i["kind"] == "numeric")
    n = tutor._present(item, block="practice", phase=None)["n"]
    value = tutor.session["presented"][str(n)]["inst"]["answer"]["value"]
    tutor.answer(f"{n} = {value:.3g} ~4")  # right value, unit left off: the mark is lost
    summary = tutor.end()
    text = (tutor.vault.root / report.session_note(tutor, summary["session"])).read_text()
    assert summary["accuracy"] == 0 and "accuracy: 0.0" in text and "> [!failure]" in text


@pytest.mark.parametrize("item_id", ["9702-2.1-p01", "9702-2.1-x001"])
def test_past_paper_mistakes_keep_their_question(tutor, item_id):  # B-037: only ids with -i were looked up
    past = {"id": item_id, "kcs": ["9702-2.1.1"], "kind": "mcq", "difficulty": 2, "marks": 1,
            "stem": "Which quantity is a vector?", "options": {"A": "speed", "B": "mass", "C": "velocity", "D": "time"},
            "answer": "C", "source": {"type": "past", "ref": "CAIE 9702 · Nov 2021 · P12 · Q3"}}
    tutor.packs.pack("9702-2.1")["items"].append(past)
    tutor.start("review", minutes=10)
    n = tutor._present(past, block="practice", phase=None)["n"]
    tutor.answer(f"{n}?")
    summary = tutor.end()
    journal = (tutor.vault.root / report.mistakes_note(tutor)).read_text()
    assert "Question: Which quantity is a vector?" in journal and "Right answer: C: velocity" in journal
    assert "## 9702-2.1 Equations of motion" in journal and "not recorded" not in journal
    assert "Which quantity is a vector?" in (tutor.vault.root / report.session_note(tutor, summary["session"])).read_text()


def test_today_note_counts_almanac_ticks_and_follows_you_ahead(tutor):
    """Asked by the learner: ticked objectives were not counted as done, and only the calendar week was shown."""
    plan = tutor.packs.plan
    plan["weeks"]["5"].append({"id": "5-exam1", "subject": "exam", "title": "D28 review", "kcs": [], "type": "REVIEW"})
    plan["weeks"]["6"] = [{"id": "6-phys1", "subject": "phys", "title": "Dynamics", "kcs": [], "type": "NEW"}]
    folder = tutor.vault.root / "Almanac"
    folder.mkdir()
    export = folder / "almanac-progress-2026-09-29.json"
    export.write_text(json.dumps({"done": {"5-phys1": 1}}))
    text = (tutor.vault.root / report.today_note(tutor)).read_text()
    assert "This week's Almanac objectives" in text and "Kinematics (0/2 KCs mastered) ✅ ticked in your Almanac" in text
    assert "Check what you ticked" in text and "**Learn**" not in text  # a ticked objective is checked, not taught
    export.write_text(json.dumps({"done": {"5-phys1": 1, "5-exam1": 1}}))  # the whole week ticked: you are ahead
    text = (tutor.vault.root / report.today_note(tutor)).read_text()
    assert "Almanac week 6" in text and "ahead" in text and "Dynamics" in text
    assert "Kinematics" not in text.split("## ")[-1]  # week 5's objectives are no longer the ones listed


def test_a_tick_the_tutor_put_in_the_almanac_is_not_read_back_as_the_learners(tutor):
    folder = tutor.vault.root / "Almanac"
    folder.mkdir()
    (folder / "almanac-progress-2026-09-29.json").write_text(
        json.dumps({"done": {"5-phys1": 1}, "tutor": {"stamp": "s", "done": {"5-phys1": 1}}}))
    assert tutor.ticks() == frozenset()  # no longer earned here: the tutor's own tick does not hold it up
    text = (tutor.vault.root / report.today_note(tutor)).read_text()
    assert "ticked in your Almanac" not in text and "**Learn**" in text


def test_the_almanac_file_holds_everything_the_tutor_knows(tutor, tmp_path):
    """Asked by the learner: fill in the whole Almanac for me (ticks, colours, the wall, mistakes, the week's
    retrospective, the paper stage) and keep it up to date as I study."""
    planner = tmp_path / "A-Levels.html"
    planner.write_text("<html></html>")
    tutor.packs.plan["source_path"] = str(planner)
    first = report.almanac_payload(tutor)
    assert first["rag"] == {"phys-2": "r"} and first["done"] == {} and first["wall"] == {} and first["retro"] == {}
    _study(tutor, wrong=True)
    assert report.almanac_push(tutor) == str(tmp_path / "A-Levels.tutor.js")
    text = (tmp_path / "A-Levels.tutor.js").read_text()
    assert text.startswith("window.TUTOR_SYNC = ") and text.rstrip().endswith(";")
    data = json.loads(text[len("window.TUTOR_SYNC = "):].rstrip().rstrip(";"))
    assert data["wall"] == {"2026-09-29": 1} and data["stage"] == 0
    assert set(data["err"]) <= {"Algebra slip", "Misread the question", "Wrong method", "Ran out of time",
                                "Could not recall", "Careless arithmetic"}  # the Almanac's own six families
    assert "answers" in data["retro"]["5"]["broke"] and data["retro"]["5"]["fix"]  # Almanac week 5
    assert data["stamp"] == report.almanac_payload(tutor)["stamp"] != first["stamp"]  # same facts, same stamp


def test_nothing_is_written_when_the_planner_is_not_on_this_machine(tutor):
    assert report.almanac_push(tutor) is None


def test_paper_results_fill_the_almanacs_mark_bank(tutor):
    tutor.paper_score("9702_s23_qp_22", "1a=2/2, 1b=1/3")
    assert report.almanac_payload(tutor)["scores"] == {"phys-P2": 36}  # 3 of 5, on the bank's 60 marks


def test_right_answers_in_the_notes_are_written_as_maths():
    assert report.note_answer("9.00 m s^-2") == "9.00 m s$^{-2}$"
    assert report.note_answer("7.46e10 Pa") == "7.46 × 10$^{10}$ Pa"
    assert report.note_answer("C: 10.3 N m⁻¹") == "C: 10.3 N m$^{-1}$"
    assert report.note_answer("D: $(1,4)$") == "D: $(1,4)$"  # already maths: left alone


def test_a_clipped_question_says_it_goes_on():
    assert report._clip_math("A trolley moves through a\nfield. Find x.") == "A trolley moves through a…"
    assert report._clip_math("Find $x$.") == "Find $x$."


def test_one_mistake_is_one_mistake(tutor):
    _study(tutor, wrong=True)
    text = (tutor.vault.root / report.mistakes_note(tutor)).read_text()
    n = sum(line.startswith("- **") for line in text.splitlines())
    assert text.splitlines()[3].startswith(f"{n} mistake{'s' if n != 1 else ''} · ")
    assert "^-" not in text  # units are written as maths


def test_profile_counts_read_as_english(tutor):
    _study(tutor, wrong=True)
    text = report.insights_markdown(tutor)
    assert "1 study day " in text and "1 sessions" not in text and "day(s)" not in text
    assert "Current streak: 1 day." in text


def test_far_off_exams_not_started_share_one_line(tutor, monkeypatch):
    from tutorlib import insights
    row = {"date": "2027-05-15", "estimated": False, "ideas": 3, "built": 1, "started": 0, "secure": 0,
           "recall_if_stop": None, "recall_if_keep": None}
    monkeypatch.setattr(insights, "readiness", lambda t: [
        {**row, "exam": "Near", "days": 200}, {**row, "exam": "Far A", "date": "2028-05-15", "days": 590},
        {**row, "exam": "Far B", "date": "2028-05-15", "days": 590},
        {**row, "exam": "Far but begun", "date": "2028-05-15", "days": 590, "started": 2}])
    text = report.insights_markdown(tutor)
    assert "| Near |" in text and "| Far but begun |" in text and "| Far A |" not in text
    assert "Later, not started yet: Far A, Far B (from 2028-05-15)." in text


def test_today_names_a_few_ideas_per_line_and_counts_the_rest(tutor, monkeypatch):
    from tutorlib import policy
    kcs = sorted(tutor.packs.kcs)
    monkeypatch.setattr(report, "TODAY_KCS", len(kcs) - 1)
    monkeypatch.setattr(policy, "plan_session", lambda *a, **k: [{"kind": "review", "kcs": kcs}])
    text = (tutor.vault.root / report.today_note(tutor)).read_text()
    line = next(l for l in text.splitlines() if l.startswith("- **Review**"))
    assert kcs[-1] not in line and line.endswith(f"{tutor.packs.kc(kcs[-2])['title']} +1 more")


def test_a_review_lesson_is_not_titled_review_review(tutor):
    tutor.start("review", minutes=10)
    assert tutor.session["log"].endswith(" Review.md")


def test_an_idea_dropped_from_the_packs_does_not_stop_the_brief(tmp_path):
    clock = {"now": T0}
    t = session.Tutor(store.Vault(make_vault(tmp_path)), rng=random.Random(0), now=lambda: clock["now"])
    t.log({"type": "answer", "session": "s1", "item": "old-i01", "kcs": ["9702-9.9.9"], "subject": "phys",
           "difficulty": 3, "conf": 3, "hinted": False, "seconds": 30, "marks": 1,
           "grade": {"correct": True, "score": 1.0, "error": None, "misconception": None},
           "credit": [], "pos": 0, "block": "review", "phase": None, "response": "B"})
    clock["now"] = T0 + timedelta(days=30)  # due for review, but no longer in any pack (a republish dropped it)
    assert t.packs.items_for("9702-9.9.9") == [] and t.packs.pack_for_kc("9702-9.9.9") is None
    report.brief(t)
    report.today_note(t)
    assert "9702-9.9.9" not in str(t.start("autopilot", minutes=50)["blocks"])
