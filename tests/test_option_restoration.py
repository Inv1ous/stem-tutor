"""Whole-options restorations (2026-10-30): approved ids only, null options only, exactly A to D, fail closed."""
import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "build"))
import correction_review as cr  # noqa: E402

ITEM = "9702-5.2-x021"
OPTS = {"A": "2", "B": "4", "C": "8", "D": "16"}


def _proposal(selector=None, options=None):
    return {"corrections": [],
            "option_restorations": [{"selector": selector or ["items", {"id": ITEM}, "options"],
                                     "options": OPTS if options is None else options,
                                     "reason": "Options missing in pack; restored from printed page."}],
            "evidence": [{"source": "sources/papers/9702/2024/s/9702_s24_qp_12.pdf", "pdf_page": 8}]}


def _pack(options=None):
    return {"items": [{"id": ITEM, "kind": "mcq", "options": options}, {"id": "9702-5.2-x020", "kind": "mcq",
                                                                        "options": {"A": "x"}}]}


def test_approved_null_options_restoration_is_accepted():
    assert cr.validate_manifest(_proposal()) == []


def test_unapproved_item_is_refused():
    issues = cr.validate_manifest(_proposal(["items", {"id": "9702-5.2-x019"}, "options"]))
    assert "unapproved option restoration selector" in issues


def test_options_must_be_exactly_A_to_D():
    assert cr.validate_manifest(_proposal(options={**OPTS, "E": "32"})) != []
    assert cr.validate_manifest(_proposal(options={"A": "2", "B": "4", "C": "8"})) != []
    assert cr.validate_manifest(_proposal(options={"A": "2", "B": "4", "C": "8", "D": " "})) != []


def test_stage_sets_options_only_where_stored_value_is_null():
    pack = _pack(options=None)
    staged, _ = cr.stage_corrections(pack, "", _proposal())
    assert next(i for i in staged["items"] if i["id"] == ITEM)["options"] == OPTS


def test_stage_refuses_to_overwrite_existing_options():
    with pytest.raises(ValueError, match="stored options are null"):
        cr.stage_corrections(_pack(options={"A": "old"}), "", _proposal())


def test_stage_leaves_every_other_item_unchanged():
    pack = _pack(options=None)
    before = copy.deepcopy(pack)
    staged, _ = cr.stage_corrections(pack, "", _proposal())
    other_before = [i for i in before["items"] if i["id"] != ITEM]
    other_after = [i for i in staged["items"] if i["id"] != ITEM]
    assert other_before == other_after
    assert pack == before  # the input pack is not mutated


def test_no_restorations_leaves_pack_unchanged():
    pack = _pack(options=None)
    staged, _ = cr.stage_corrections(pack, "", {"corrections": [], "evidence": [{"source": "x", "pdf_page": 1}]})
    assert staged == pack
