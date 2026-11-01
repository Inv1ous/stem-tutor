"""Report summaries describe the same available glossary work as Review."""
import copy
from datetime import datetime

import pytest

from test_profile_term_workload import KC, NOW, prepared
from tutorlib import lesson, report


@pytest.mark.parametrize("count", [1, 2])
def test_public_brief_and_today_name_and_count_actual_available_term_review(tmp_path, count):
    tutor, source, terms = prepared(tmp_path)
    ids = [lesson.term_id(KC, term["term"]) for term in terms[:count]]
    for tid in ids:
        tutor.log({"type": "term_introduced", "term_id": tid, "kc": KC})
    tutor.log({"type": "term_introduced", "term_id": ids[0], "kc": KC})
    for tid, kc in ((lesson.term_id(KC, "Removed"), KC), ("term:orphan", "9702-9.9.9")):
        tutor.log({"type": "term_introduced", "term_id": tid, "kc": kc})
    future = lesson.term_id(KC, terms[count]["term"])
    tutor.log({"type": "term_introduced", "term_id": future, "kc": KC})
    tutor.log({"type": "term_review", "term_id": future, "rating": "good"})
    assert datetime.fromisoformat(tutor.state["terms"][future]["fsrs"]["due"]) > NOW
    state = copy.deepcopy(tutor.state)
    source_bytes = source.read_bytes()
    history = {path: path.read_bytes() for path in (tutor.vault.tutor / "events").glob("*.jsonl")}

    brief = report.brief(tutor)
    path = report.today_note(tutor)
    text = (tutor.vault.root / path).read_text()
    label = f"{count} term{'s' if count != 1 else ''}"

    assert brief["due"] == count
    assert f"glossary review ({label})" in brief["suggest"]
    assert f"- **Glossary review**: {label}" in text
    assert "Term_review" not in text
    assert tutor.state == state and source.read_bytes() == source_bytes
    assert all(path.read_bytes() == data for path, data in history.items())
    blocks = tutor.start("review", 50)["blocks"]
    assert set(next(block["terms"] for block in blocks if block["kind"] == "term_review")) == set(ids)
    stem = tutor.next()["items"][0]["stem"]
    assert any(term["term"] in stem for term in terms[:count])


def test_normal_kc_only_report_plan_keeps_exact_existing_output(tmp_path):
    tutor, _, _ = prepared(tmp_path)
    assert report.brief(tutor)["suggest"] == (
        "50 min: learn 9702-2.1.1 → learn 9702-2.1.4 → exit 9702-2.1.1, 9702-2.1.4")
    text = (tutor.vault.root / report.today_note(tutor)).read_text()
    assert text == (
        "# Today · Tue 29 Sep 2026 · Almanac week 5\n\n"
        "Next sitting: **9702-AS** in 223 days (2027-05-10).\n\n"
        "## Suggested 50-minute session\n\n"
        "- **Learn**: 9702-2.1.1 Distance, displacement, speed, velocity\n"
        "- **Learn**: 9702-2.1.4 suvat\n"
        "- **Exit**: 9702-2.1.1 Distance, displacement, speed, velocity, 9702-2.1.4 suvat\n\n"
        "## This week's Almanac objectives\n\n"
        "- phys · Kinematics (0/2 KCs mastered)\n")
