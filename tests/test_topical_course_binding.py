"""Reviewed topical rows cannot award another course's learner progress."""
import copy
import json
import sys
from datetime import datetime
from pathlib import Path

import pytest

from test_topicals import KC, OTHER, TARGET, bank_vault, item
from fixtures import GRAPH, PACK
from tutorlib import asset_library, session, store

NOW = datetime.fromisoformat("2026-10-27T12:00:00+08:00")
CANONICAL = "Library/Shared/Topicals/Releases/course-check/bank.json"


def two_course_vault(tmp_path):
    root = bank_vault(tmp_path)
    base = root / ".tutor/packs/v1"
    manifest = json.loads((base / "manifest.json").read_text())
    manifest["specs"].append("9701")
    (base / "manifest.json").write_text(json.dumps(manifest))
    graph = json.loads((base / "specs/9702/graph.json").read_text().replace("9702", "9701"))
    graph.update(subject="chem", title="Synthetic second-course graph")
    (base / "specs/9701").mkdir()
    (base / "specs/9701/graph.json").write_text(json.dumps(graph))
    (base / "papers.json").write_text('{"papers": []}')
    return root


def row_for(course):
    row = item()
    if course == "9701":
        row = json.loads(json.dumps(row).replace("9702", "9701"))
    row["id"] = course + "-source-question"
    return row


def register(root, rows):
    bank = {"format_version": 1, "syllabus_versions": {"9702": "2025-2027", "9701": "2025-2027"},
            "items": rows}
    asset_library.write_asset(root, CANONICAL, json.dumps(bank).encode())
    pointer = root / ".tutor/topicals/CURRENT"
    pointer.parent.mkdir()
    pointer.write_text("course-check")


@pytest.mark.parametrize("first_course", ["9702", "9701"])
@pytest.mark.parametrize("defect", ["mixed_kcs", "foreign_qid"])
def test_registered_bank_refuses_cross_course_grading_before_start_or_answer(tmp_path, first_course, defect):
    root = two_course_vault(tmp_path)
    foreign = "9701" if first_course == "9702" else "9702"
    row = row_for(first_course)
    if defect == "mixed_kcs":
        row["kcs"].append(KC.replace("9702", foreign))
    else:
        row["source"]["qid"] = row["source"]["qid"].replace(first_course, foreign)
    register(root, [row])
    vault = store.Vault(root)
    vault.append_event({"type": "note", "text": "Original learner record"}, now=NOW)
    protected = [root / CANONICAL, root / "Library/catalog.json", *vault.tutor.glob("events/*.jsonl")]
    before = {path: path.read_bytes() for path in protected}
    tutor = session.Tutor(vault, now=lambda: NOW)
    state = copy.deepcopy(tutor.state)

    assert tutor.packs.topical_errors
    assert tutor.packs.topical_items(TARGET.replace("9702", first_course)) == []
    result = tutor.start("topical", minutes=9, focus=[TARGET.replace("9702", first_course)])
    assert result["ok"] is False
    assert "error" in tutor.answer("1B4")
    assert tutor.session is None and tutor.state == state
    assert not any(event["type"] == "answer" for event in vault.events())
    assert all(path.read_bytes() == data for path, data in before.items())


def test_multicourse_bank_preserves_same_course_multi_kc_chapter_assessments(tmp_path):
    root = two_course_vault(tmp_path)
    rows = [row_for(course) for course in ("9702", "9701")]
    for row in rows:
        course = row["kcs"][0].split("-", 1)[0]
        row["kcs"].append((OTHER + ".1").replace("9702", course))
        row["topical"]["chapters"].append(OTHER.replace("9702", course))
    register(root, rows)
    source = (root / CANONICAL).read_bytes()
    catalog = (root / "Library/catalog.json").read_bytes()
    tutor = session.Tutor(store.Vault(root), now=lambda: NOW)
    assert not tutor.packs.topical_errors
    for row in rows:
        chapter = row["topical"]["chapters"][0]
        assert "error" not in tutor.start("topical", minutes=9, focus=[chapter])
        activity = tutor.next()
        pending = tutor.session["presented"][str(activity["items"][0]["n"])]
        assert pending["kcs"] == row["kcs"]
        result = tutor.answer(f"{activity['items'][0]['n']}B4")
        assert result["results"][0]["correct"]
        tutor.end()
    for row in rows:
        assert all(tutor.state["kcs"][kc]["n"] == 1 for kc in row["kcs"])
    restarted = session.Tutor(store.Vault(root), now=lambda: NOW)
    restarted.rebuild()
    assert restarted.state == tutor.state
    assert (root / CANONICAL).read_bytes() == source
    assert (root / "Library/catalog.json").read_bytes() == catalog


@pytest.mark.parametrize("course", ["9702", "9701"])
def test_repeated_assessed_kc_cannot_be_graded_as_two_attempts(tmp_path, course):
    root = two_course_vault(tmp_path)
    row = row_for(course)
    row["kcs"] *= 2
    register(root, [row])
    vault = store.Vault(root)
    vault.append_event({"type": "note", "text": "Original learner record"}, now=NOW)
    protected = [root / CANONICAL, root / "Library/catalog.json", *vault.tutor.glob("events/*.jsonl")]
    before = {path: path.read_bytes() for path in protected}
    tutor = session.Tutor(vault, now=lambda: NOW)

    assert tutor.packs.topical_errors
    assert tutor.start("topical", minutes=9, focus=row["topical"]["chapters"])["ok"] is False
    assert "error" in tutor.answer("1B4")
    assert not tutor.state["kcs"]
    assert all(path.read_bytes() == data for path, data in before.items())


def test_publisher_refuses_repeated_kc_before_switching_or_registering(tmp_path):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "build"))
    import topicals as publisher
    root = two_course_vault(tmp_path)
    register(root, [row_for("9702")])
    batch = tmp_path / "candidate"
    batch.mkdir()
    data = json.loads((root / CANONICAL).read_text())
    data["items"][0]["kcs"] *= 2
    (batch / "bank.json").write_text(json.dumps(data))
    pointer = root / ".tutor/topicals/CURRENT"
    before = {path: path.read_bytes() for path in (pointer, root / CANONICAL, root / "Library/catalog.json")}

    with pytest.raises(ValueError, match="duplicate assessed KC"):
        publisher.publish(batch, root, expected_current="course-check")

    assert all(path.read_bytes() == data for path, data in before.items())


@pytest.mark.parametrize("repeated", [False, True])
def test_pack_producer_rejects_only_repeated_assessed_ids(repeated):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "build"))
    import validate_pack
    pack = copy.deepcopy(PACK)
    pack["items"][0]["kcs"] = [KC, KC if repeated else "9702-2.1.4"]
    before = copy.deepcopy(pack)

    errors = validate_pack.validate(pack, GRAPH, min_variants=0)

    assert any(error["rule"] == "duplicate-kc" for error in errors) is repeated
    assert pack == before
