"""How typed answers are read: standard form, units, lookalike characters, labels, function names, decimal commas.
Each fix comes with tests that the right/wrong decisions around it do not move."""
import pytest

from tutorlib import grade, units


def _num(value, text, unit="", **answer):
    item = {"kind": "numeric", "stem": "", "answer": {"value": value, "unit": unit, **answer}}
    return grade.grade_item(item, {"kind": "value", "value": text, "conf": 3})


# ---------- "× 10" is standard form only with a written power ----------
@pytest.mark.parametrize("text,value", [
    ("1.5 x 10-3", 1.5e-3), ("1.5x10-3", 1.5e-3), ("1.5 x 10 -3", 1.5e-3), ("1.5 x 10+3", 1.5e3),
    ("1.5 × 10^3", 1.5e3), ("1.5×10³", 1.5e3), ("1.5 x 10^{3}", 1.5e3), ("1.5 x 10^{-3}", 1.5e-3),
    ("1.5 x 10^(-3)", 1.5e-3), ("1.5 x 10{-3}", 1.5e-3), ("1.5E3", 1.5e3), ("1.5e-3", 1.5e-3), ("1.5 * 10^3", 1.5e3),
    ("1.5 X 10^3", 1.5e3), ("1.5 \\times 10^{3}", 1.5e3), ("1.5 × 10 ^ 3", 1.5e3), ("1.5·10⁻³", 1.5e-3),
])
def test_standard_form_with_a_written_power_is_read(text, value):
    assert grade.parse_quantity(text)[0] == pytest.approx(value)


@pytest.mark.parametrize("text", ["5 x 1000", "5 x 1000 m", "3 * 100", "0.25 x 100", "3 x 105", "5 × 1000 m",
                                  "1.5 x 103", "2 x 10", "2 x 10 m", "1.5 x 10 3"])
def test_times_a_number_that_is_not_a_written_power_is_unreadable(text):
    """The caret was optional, so "× 1000" read as ×10^0 and "x 105" as ×10^5."""
    with pytest.raises(grade.ParseError):
        grade.parse_quantity(text)


@pytest.mark.parametrize("value,unit,text", [(5000, "m", "5 x 1000 m"), (3, "", "3 * 100"), (0.25, "", "0.25 x 100"),
                                             (3e5, "", "3 x 105"), (5, "", "5 x 1000")])
def test_a_product_is_left_for_judgement_never_marked(value, unit, text):
    g = _num(value, text, unit, sf_ok=[1, 2, 3])
    assert not g["correct"] and g["score"] == 0 and g["needs_judgement"] and g["error"] is None
    assert grade.value_problem({"kind": "numeric", "answer": {"value": value, "unit": unit}}, text) == "unreadable"


@pytest.mark.parametrize("value,unit,text,score", [
    (5000, "m", "5 x 10^3 m", 1.0), (5000, "m", "5 km", 1.0), (5000, "m", "5×10³ m", 1.0), (1.5e-3, "", "1.5 x 10-3", 1.0),
    (1.5e-3, "", "1.5 x 10-4", 0), (5000, "m", "5 x 10^2 m", 0), (1500, "J", "1.5 X 10^3 J", 1.0)])
def test_standard_form_marks_are_unchanged(value, unit, text, score):
    assert _num(value, text, unit, sf_ok=[1, 2, 3])["score"] == score
