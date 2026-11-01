"""Entered paper dates must reach the scheduling/readiness consumers."""
import json
from datetime import date, datetime
from types import SimpleNamespace

import pytest

from fixtures import make_vault
from tutorlib import insights, policy, session, store


@pytest.fixture
def tutor(tmp_path):
    root = make_vault(tmp_path)
    version = root / ".tutor/packs/v1"
    graph_path = version / "specs/9702/graph.json"
    graph = json.loads(graph_path.read_text())
    graph["kcs"][1]["level"] = "A2"
    graph_path.write_text(json.dumps(graph))
    plan_path = version / "plan.json"
    plan = json.loads(plan_path.read_text())
    plan["papers"] = [
        {"code": "9701/22", "short": "Chem P2", "sitting": "AS · Jun 2027", "date": None},
        {"code": "9702/12", "short": "Phys P1", "sitting": "AS · Jun 2027", "date": None},
        {"code": "9702/22", "short": "Phys P2", "sitting": "AS · Jun 2027", "date": None},
        {"code": "9702/42", "short": "Phys P4", "sitting": "A2 · Jun 2028", "date": None},
        {"code": "9702/52", "short": "Phys P5", "sitting": "A2 · Jun 2028", "date": None},
        {"code": "WMA11/01", "short": "P1", "sitting": "F5 · Jun 2027", "date": "2027-05-06"},
    ]
    plan["sittings"] = {"P1 (WMA11)": "2027-05-06"}
    plan_path.write_text(json.dumps(plan))
    return session.Tutor(store.Vault(root), now=lambda: datetime.fromisoformat("2027-05-01T17:00:00+08:00"))


def exported(tutor, dates):
    folder = tutor.vault.root / "Almanac"
    folder.mkdir(exist_ok=True)
    (folder / "almanac-progress-test.json").write_text(json.dumps({"dates": dates}))
    tutor.read_almanac()


def test_exported_caie_dates_follow_course_level_and_earliest_relevant_paper(tutor):
    exported(tutor, {"0": "2027-05-03", "1": "2027-06-15", "2": "2027-05-31",
                     "3": "2028-06-16", "4": "2028-06-01"})
    assert policy.exam_date(tutor.packs, "9702-2.1.1") == date(2027, 5, 31)
    assert policy.exam_date(tutor.packs, "9702-2.1.4") == date(2028, 6, 1)
    assert policy.target_retention(tutor.state, tutor.packs, "9702-2.1.1", tutor.now()) == 0.93
    readiness = {row["date"]: row for row in insights.readiness(tutor)}
    assert set(readiness) == {"2027-05-31", "2028-06-01"}
    assert all(row["estimated"] is False for row in readiness.values())
    assert readiness["2027-05-31"]["exam"] == "Phys P2 (9702)"
    assert readiness["2028-06-01"]["exam"] == "Phys P5 (9702)"


def test_other_level_dates_do_not_replace_an_undated_caie_estimate(tutor):
    exported(tutor, {"0": "2027-05-03", "3": "2028-06-16"})
    assert policy.exam_date(tutor.packs, "9702-2.1.1") == policy.AS_2027
    assert policy.exam_date(tutor.packs, "9702-2.1.4") == date(2028, 6, 16)
    exported(tutor, {})
    assert policy.exam_date(tutor.packs, "9702-2.1.1") == policy.AS_2027
    assert policy.exam_date(tutor.packs, "9702-2.1.4") == policy.A2_2028
    assert all(row["estimated"] for row in insights.readiness(tutor))


@pytest.mark.parametrize("spec, level, expected", [
    ("9701", "AS", date(2027, 5, 3)),
    ("9701", "A2", policy.A2_2028),
    ("9702", "AS", date(2027, 6, 15)),
    ("9702", "A2", date(2028, 6, 16)),
    ("P1", "AS", date(2027, 5, 6)),
])
def test_date_selection_is_course_and_level_scoped_without_changing_maths(tutor, spec, level, expected):
    exported(tutor, {"0": "2027-05-03", "1": "2027-06-15", "3": "2028-06-16"})
    packs = SimpleNamespace(plan=tutor.packs.plan, kc=lambda _: {"spec": spec, "level": level})
    assert policy.exam_date(packs, "idea") == expected


@pytest.mark.parametrize("level, index, expected", [
    ("AS", 1, date(2027, 6, 15)), ("A2", 3, date(2028, 6, 16)),
])
def test_legacy_component_metadata_retains_the_caie_level(tutor, level, index, expected):
    exported(tutor, {str(index): expected.isoformat()})
    for paper in tutor.packs.plan["papers"]:
        paper.pop("sitting", None)
    packs = SimpleNamespace(plan=tutor.packs.plan, kc=lambda _: {"spec": "9702", "level": level})
    assert policy.exam_date(packs, "idea") == expected


def test_unknown_declared_stage_does_not_guess_an_exam_date(tutor):
    exported(tutor, {"1": "2027-06-15"})
    tutor.packs.plan["papers"][1]["sitting"] = "Unverified"
    assert policy.exam_date(tutor.packs, "9702-2.1.1") == policy.AS_2027


def test_readiness_stays_on_the_next_paper_between_science_components(tutor):
    exported(tutor, {"1": "2027-05-31", "2": "2027-06-15"})
    tutor._now = lambda: datetime.fromisoformat("2027-06-01T17:00:00+08:00")
    rows = insights.readiness(tutor)
    assert any(row["date"] == "2027-06-15" and row["exam"] == "Phys P2 (9702)" for row in rows)
    tutor._now = lambda: datetime.fromisoformat("2027-06-16T17:00:00+08:00")
    assert not any(row["date"].startswith("2027-") for row in insights.readiness(tutor))


def test_an_unverified_stage_at_the_estimate_date_stays_labelled_estimated(tutor):
    exported(tutor, {"1": policy.AS_2027.isoformat()})
    tutor.packs.plan["papers"][1]["sitting"] = "Unverified"
    row = next(row for row in insights.readiness(tutor) if row["date"] == policy.AS_2027.isoformat())
    assert row["estimated"] is True


def test_retention_and_review_priority_use_the_upcoming_component(tutor):
    exported(tutor, {"0": "2027-06-15", "1": "2027-05-31", "2": "2027-07-31"})
    tutor._now = lambda: datetime.fromisoformat("2027-06-01T17:00:00+08:00")
    assert policy.target_retention(tutor.state, tutor.packs, "9702-2.1.1", tutor.now()) == 0.91
    metadata = {
        "physics": {"spec": "9702", "level": "AS", "subtopic": "9702-2.1"},
        "chemistry": {"spec": "9701", "level": "AS", "subtopic": "9701-2.1"},
    }
    packs = SimpleNamespace(plan=tutor.packs.plan, kcs=metadata, kc=metadata.__getitem__)
    assert policy.review_order(tutor.state, packs, tutor.now(), ["physics", "chemistry"]) == ["chemistry", "physics"]
