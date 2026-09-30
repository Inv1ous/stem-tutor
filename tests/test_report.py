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
    for heading in ("How sure vs how right", "Mistakes by kind", "Teaching experiments", "What the tutor has adjusted",
                    "When you learn best", "Stamina in a session"):
        assert heading in text
    assert lint.lint(text) == []


def test_today_note_lists_plan(tutor):
    path = report.today_note(tutor)
    text = (tutor.vault.root / path).read_text()
    assert "Learn" in text and "9702-2.1.1" in text


def test_almanac_sync_merges_into_latest_export(tutor):
    folder = tutor.vault.root / "Almanac"
    folder.mkdir()
    (folder / "almanac-progress-2026-09-28.json").write_text(json.dumps(
        {"done": {"1-math1": 1}, "err": {"Could not recall": 2}, "wall": {"2026-09-20": 1}, "rag": {"phys-1": "g"}}))
    _study(tutor, wrong=True)
    r = report.almanac_sync(tutor)
    out = json.loads((tutor.vault.root / r["path"]).read_text())
    assert out["done"] == {"1-math1": 1}
    assert out["wall"]["2026-09-29"] == 1 and out["wall"]["2026-09-20"] == 1
    assert sum(out["err"].values()) >= 2
    again = report.almanac_sync(tutor)  # no double counting
    out2 = json.loads((tutor.vault.root / again["path"]).read_text())
    assert out2["err"] == out["err"]


def test_almanac_sync_writes_best_recent_paper_scores(tutor):
    tutor.paper_score("9702_s23_qp_22", "1a=1/2, 1b=2/3")
    tutor.paper_score("9702_s23_qp_22", "1a=2/2, 1b=3/3")
    out = json.loads((tutor.vault.root / report.almanac_sync(tutor)["path"]).read_text())
    assert out["scores"]["phys-P2"] == 60  # full-paper equivalent: 100% of 60 marks


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
