"""Nested structured corrections (2026-10-30): approved answer fields only, exact old value, fail closed."""
import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "build"))
import correction_review as cr  # noqa: E402

SF = ["items", {"id": "P1-1-i09"}, "answer", "sf_ok"]
VALUE = ["items", {"id": "P1-4-i01"}, "answer", "value"]


def _pack(sf_ok=(3, 4), value=4.0):
    return {"items": [{"id": "P1-1-i09", "answer": {"sf_ok": list(sf_ok)}},
                      {"id": "P1-4-i01", "answer": {"value": value}}, {"id": "P1-1-i10", "answer": {"sf_ok": [3]}}]}


def _proposal(path, old, new):
    return {"corrections": [], "structured_corrections": [
        {"selector": path, "old": old, "new": new, "reason": "Test change reviewed in test."}],
        "evidence": [{"source": "sources/papers/ial/WMA11/WMA11_2019_Jan_qp.pdf", "pdf_page": 1}]}


def test_approved_sf_ok_restriction_validates():
    assert cr.validate_manifest(_proposal(SF, [3, 4], [3])) == []


def test_approved_numeric_value_validates():
    assert cr.validate_manifest(_proposal(VALUE, 4.0, 2.0)) == []


def test_unapproved_nested_path_is_refused():
    other = ["items", {"id": "P1-1-i09"}, "answer", "method"]
    assert "unsafe structured correction selector" in cr.validate_manifest(_proposal(other, [3, 4], [3]))


def test_numeric_slot_rejects_bool_and_string():
    assert cr.validate_manifest(_proposal(VALUE, 4.0, True)) != []
    assert cr.validate_manifest(_proposal(VALUE, 4.0, "2")) != []


def test_stage_applies_only_the_approved_slot():
    pack = _pack()
    staged, _ = cr.stage_corrections(pack, "", _proposal(SF, [3, 4], [3]))
    assert staged["items"][0]["answer"]["sf_ok"] == [3]
    assert staged["items"][1] == pack["items"][1]  # P1-4-i01 untouched
    assert staged["items"][2] == pack["items"][2]
    assert pack["items"][0]["answer"]["sf_ok"] == [3, 4]  # input not mutated


def test_stage_refuses_stale_old_value():
    with pytest.raises(ValueError, match="exactly once"):
        cr.stage_corrections(_pack(sf_ok=(3,)), "", _proposal(SF, [3, 4], [3]))


def test_stage_numeric_value_replaces_stored_answer():
    staged, _ = cr.stage_corrections(_pack(), "", _proposal(VALUE, 4.0, 2.0))
    assert staged["items"][1]["answer"]["value"] == 2.0


def test_slot_helper_points_at_the_nested_value_only():
    candidate = copy.deepcopy(_pack())
    holder, key = cr._structured_slot(candidate, SF)
    assert holder is candidate["items"][0]["answer"] and key == "sf_ok"
    holder[key] = [3]
    assert candidate["items"][0]["answer"]["sf_ok"] == [3]
    assert candidate["items"][2]["answer"]["sf_ok"] == [3]  # other items unaffected


def test_slot_helper_refuses_unknown_or_duplicate_ids():
    pack = _pack()
    pack["items"].append({"id": "P1-1-i09", "answer": {"sf_ok": [3]}})
    with pytest.raises(ValueError, match="exactly once"):
        cr._structured_slot(pack, SF)


NULL_OPTIONS = ["items", {"id": "9702-6.2-x017"}, "options"]


def _null_pack():
    return {"items": [{"id": "9702-6.2-x017", "kind": "mcq", "options": {"A": "graph A", "B": "graph B"}},
                      {"id": "9702-6.2-x016", "kind": "mcq", "options": {"A": "keep"}}]}


def _null_proposal(old, new, path=NULL_OPTIONS):
    return {"corrections": [], "structured_corrections": [
        {"selector": path, "old": old, "new": new, "reason": "Figure-only options; whole-question image carries them."}],
        "evidence": [{"source": "sources/papers/9702/2021/w/9702_w21_qp_13.pdf", "pdf_page": 12}]}


def test_approved_null_options_validates():
    assert cr.validate_manifest(_null_proposal({"A": "graph A", "B": "graph B"}, None)) == []


def test_null_options_refused_for_any_other_item():
    other = ["items", {"id": "9702-6.2-x016"}, "options"]
    assert "unsafe structured correction selector" in cr.validate_manifest(
        _null_proposal({"A": "keep"}, None, path=other))


def test_null_options_requires_a_non_empty_dict_old_value():
    assert "incomplete structured correction" in cr.validate_manifest(_null_proposal([], None))
    assert "incomplete structured correction" in cr.validate_manifest(_null_proposal({}, None))
    assert "incomplete structured correction" in cr.validate_manifest(_null_proposal({"A": "x"}, "gone"))


def test_stage_sets_null_options_only_on_the_approved_item():
    pack = _null_pack()
    staged, _ = cr.stage_corrections(pack, "", _null_proposal({"A": "graph A", "B": "graph B"}, None))
    assert staged["items"][0]["options"] is None
    assert staged["items"][1] == pack["items"][1]
    assert pack["items"][0]["options"] == {"A": "graph A", "B": "graph B"}  # input not mutated


def test_stage_refuses_null_when_stored_options_differ():
    with pytest.raises(ValueError, match="exactly once"):
        cr.stage_corrections(_null_pack(), "", _null_proposal({"A": "other"}, None))


M8 = ["misconceptions", {"id": "m8"}, "refutation"]


def _m8_pack(text="Extension is the change from the original or reference length; a taut reference wire helps remove support movement."):
    return {"misconceptions": [{"id": "m8", "refutation": text}, {"id": "m9", "refutation": "other"}]}


def _m8_proposal(old, new, path=M8):
    return {"corrections": [], "structured_corrections": [
        {"selector": path, "old": old, "new": new, "reason": "Align with the unloaded-reference convention in the note and r02."}],
        "evidence": [{"source": "sources/papers/9702/2023/s/9702_s23_qp_12.pdf", "pdf_page": 1}]}


def test_approved_m8_refutation_validates_as_string():
    assert cr.validate_manifest(_m8_proposal("old text", "new text")) == []


def test_only_the_approved_misconception_is_refused():
    other = ["misconceptions", {"id": "m9"}, "refutation"]
    assert "unsafe structured correction selector" in cr.validate_manifest(_m8_proposal("a", "b", path=other))


def test_string_slot_refuses_empty_or_non_string_text():
    assert "incomplete structured correction" in cr.validate_manifest(_m8_proposal("  ", "new"))
    assert "incomplete structured correction" in cr.validate_manifest(_m8_proposal("old", None))
    assert "incomplete structured correction" in cr.validate_manifest(_m8_proposal("old", 5))


def test_stage_replaces_only_m8_and_only_on_exact_old_text():
    old = "Extension is the change from the original or reference length; a taut reference wire helps remove support movement."
    new = "Extension is the change from the original or reference length; an unloaded reference wire beside the test wire helps remove support movement."
    pack = _m8_pack()
    staged, _ = cr.stage_corrections(pack, "", _m8_proposal(old, new))
    assert staged["misconceptions"][0]["refutation"] == new
    assert staged["misconceptions"][1] == pack["misconceptions"][1]
    assert pack["misconceptions"][0]["refutation"] == old  # input not mutated


def test_stage_refuses_when_m8_text_differs():
    with pytest.raises(ValueError, match="exactly once"):
        cr.stage_corrections(_m8_pack(text="something else"), "", _m8_proposal("old text", "new text"))
