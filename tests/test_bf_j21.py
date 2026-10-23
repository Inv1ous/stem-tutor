from __future__ import annotations

import pytest

from tutorlib import grade


@pytest.mark.parametrize("unit", ["km9999", "mm-9999", "KM9999"])
def test_an_overflowing_unit_after_the_right_unit_is_refused(unit: str) -> None:
    """B-003 (bug watch): an extreme unit suffix must not crash or be discarded as a comment."""
    item = {"kind": "numeric", "answer": {"value": 1.52, "unit": "mm"}}
    text = f"1.52 mm {unit}"
    assert grade.value_problem(item, text) is None
    result = grade.grade_item(item, {"kind": "value", "value": text})
    assert not result["correct"] and result["score"] == 0
    assert result["error"] == "NOTATION"
    assert result["detail"].startswith("wrong unit:")
