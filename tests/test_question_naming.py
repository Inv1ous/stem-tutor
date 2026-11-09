"""Question naming plans run against a disposable vault and never touch the learner Library."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "build"))
sys.path.insert(0, str(ROOT / "src"))

import normalize_question_names as naming  # noqa: E402
from tutorlib.asset_library import write_asset  # noqa: E402

MEDIA = "Library/Courses/9701/Questions/Media"
BANK = "Library/Courses/9701/Questions/SourceVerified/bank-9701-m17.json"


def sha12(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:12]


def add_image(vault: Path, name: str, data: bytes, *, page: int | None = None,
              aliases: tuple = ()) -> str:
    """Register one question image and, when asked, a sidecar carrying its source page."""
    relative = f"{MEDIA}/{name}"
    write_asset(vault, relative, data, aliases=aliases,
                metadata={"kind": "Questions/Media", "course": "9701"})
    if page is not None:
        write_asset(vault, relative + ".json", json.dumps({"page": page}).encode(),
                    metadata={"kind": "Questions/Media", "course": "9701"})
    return relative


def add_bank(vault: Path, items: list) -> None:
    write_asset(vault, BANK, json.dumps({"items": items}).encode(),
                metadata={"kind": "source_verified_questions", "course": "9701"})


@pytest.fixture
def vault(tmp_path):
    root = tmp_path / "STEM Tutor"
    (root / "Library").mkdir(parents=True)
    (root / "Library/catalog.json").write_text(json.dumps({"format_version": 1, "assets": {}}))
    return root


def test_legacy_name_becomes_canonical(vault):
    data = b"legacy-mcq"
    legacy = add_image(vault, "9701_m17_12_q1-0123456789abcdef.png", data)
    add_bank(vault, [{"kind": "mcq", "official_qid": "9701_m17_12_q1", "question_media": [legacy]}])
    before = (vault / "Library/catalog.json").read_bytes()

    plan = naming.build_report(vault)

    target = f"{MEDIA}/MCQ/9701_m17_12_q01_mcq_{sha12(data)}.png"
    assert [move["to"] for move in plan["moves"] if not move["to"].endswith(".json")] == [target]
    assert plan["multi_page_groups"] == [] and plan["unnamed"] == []
    assert plan["errors"] == [] and plan["reference_check"]["broken_count"] == 0
    assert (vault / "Library/catalog.json").read_bytes() == before


def test_multi_page_question_gets_ordered_page_suffixes(vault):
    first, second = b"page-one", b"page-two"
    one = add_image(vault, "9701_s18_21_q03-page1.png", first, page=1)
    two = add_image(vault, "9701_s18_21_q03-page2.png", second, page=2)
    add_bank(vault, [{"kind": "structured", "official_qid": "9701_s18_21_q03", "question_media": [one, two]}])

    plan = naming.build_report(vault)

    assert len(plan["multi_page_groups"]) == 1
    group = plan["multi_page_groups"][0]
    assert group["pages"] == 2
    assert [image["name"] for image in group["images"]] == [
        f"9701_s18_21_q03_p01_long_{sha12(first)}.png",
        f"9701_s18_21_q03_p02_long_{sha12(second)}.png"]
    assert {move["to"] for move in plan["moves"] if not move["to"].endswith(".json")} == {
        f"{MEDIA}/Long/9701_s18_21_q03_p01_long_{sha12(first)}.png",
        f"{MEDIA}/Long/9701_s18_21_q03_p02_long_{sha12(second)}.png"}


def test_unidentifiable_image_stays_unnamed(vault):
    add_image(vault, "loose-diagram.png", b"no-metadata")

    plan = naming.build_report(vault)

    assert plan["moves"] == []
    assert [row["path"] for row in plan["unnamed"]] == [f"{MEDIA}/loose-diagram.png"]
    assert plan["unnamed"][0]["reason"] == "no classification evidence"
    assert plan["summary"]["totals"]["unnamed"] == 1


def test_alias_only_reference_is_not_broken(vault):
    data = b"alias-only"
    alias = f"{MEDIA}/topicals/9701-periodic-table-0123456789ab.png"
    add_image(vault, "9701_m17_12_q1-0123456789abcdef.png", data, aliases=(alias,))
    add_bank(vault, [{"kind": "mcq", "official_qid": "9701_m17_12_q1", "question_media": [alias]}])

    plan = naming.build_report(vault)

    assert plan["reference_check"]["broken_count"] == 0
    assert plan["reference_check"]["broken"] == []
    assert plan["reference_check"]["ambiguous_count"] == 0
    assert plan["reference_check"]["tokens_checked"] >= 2


def test_colliding_alias_is_ambiguous_not_broken():
    records = {"a": {"path": "Library/x.png", "aliases": ["Library/old.png"]},
               "b": {"path": "Library/old.png", "aliases": []}}

    tokens, ambiguous = naming.reference_tokens(records)

    assert ambiguous == {"library/old.png": ["a", "b"]}
    assert "library/old.png" not in tokens
    assert tokens == {"library/x.png": "a"}


def test_sidecar_qid_names_image_without_filename_qid(vault):
    data = b"sidecar-qid"
    relative = add_image(vault, f"MCQ/9701_nosrc_mcq_{sha12(data)}.png", data)
    write_asset(vault, relative + ".json", json.dumps({"official_qid": "9701_s18_21_q03"}).encode(),
                metadata={"kind": "Questions/Media", "course": "9701"})

    plan = naming.build_report(vault)

    assert plan["unnamed"] == []
    assert [move["to"] for move in plan["moves"] if not move["to"].endswith(".json")] == [
        f"{MEDIA}/MCQ/9701_s18_21_q03_mcq_{sha12(data)}.png"]


def test_image_without_qid_metadata_stays_unnamed(vault):
    data = b"periodic-table"
    add_image(vault, f"MCQ/9701_nosrc_mcq_{sha12(data)}.png", data)

    plan = naming.build_report(vault)

    assert plan["moves"] == []
    assert [row["reason"] for row in plan["unnamed"]] == ["no question id"]
    assert plan["unnamed"][0]["qid_state"] == "none"


def test_per_course_table_counts_groups_not_images(vault):
    first, second = b"page-one", b"page-two"
    one = add_image(vault, "9701_s18_21_q03-page1.png", first, page=1)
    two = add_image(vault, "9701_s18_21_q03-page2.png", second, page=2)
    add_bank(vault, [{"kind": "structured", "official_qid": "9701_s18_21_q03", "question_media": [one, two]}])

    plan = naming.build_report(vault)

    assert plan["per_course"]["9701"] == {"named": 2, "unnamed": 0, "multi_page_groups": 1,
                                          "multi_page_images": 2, "duplicate_groups": 0}
    assert plan["summary"]["per_course"] == plan["per_course"]
