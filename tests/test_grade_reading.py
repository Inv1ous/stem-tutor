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


# ---------- a bracketed denominator ----------
@pytest.mark.parametrize("given,expected,factor", [
    ("J/(mol K)", "J K^-1 mol^-1", 1.0), ("J/(K mol)", "J K^-1 mol^-1", 1.0), ("kJ/(mol K)", "J K^-1 mol^-1", 1000.0),
    ("J / (mol K)", "J mol^-1 K^-1", 1.0), ("m/(s^2)", "m s^-2", 1.0), ("m/(s s)", "m s^-2", 1.0),
    ("kg/(m s^2)", "Pa", 1.0), ("W/(m^2 K)", "W m^-2 K^-1", 1.0), ("J/(mol K)", "J mol K^-1", None),
    ("J/(kg K)", "J K^-1 mol^-1", None), ("m/(s)", "m s^-1", 1.0), ("g/(cm3)", "g cm^-3", 1.0),
    ("J/(molK)", "J mol^-1 K^-1", 1.0),
])
def test_a_bracketed_denominator_is_all_below_the_line(given, expected, factor):
    got = units.unit_factor(given, expected)
    assert got == (pytest.approx(factor) if factor else None)


@pytest.mark.parametrize("value,unit,text", [(8.31, "J K^-1 mol^-1", "8.31 J/(mol K)"), (8.31, "J K^-1 mol^-1", "8.31 J/(K mol)"),
                                             (9.81, "m s^-2", "9.81 m/(s^2)"), (8.31, "J K^-1 mol^-1", "8.31 J/(mol K) ")])
def test_a_bracketed_denominator_is_marked_right(value, unit, text):
    assert _num(value, text, unit, sf_ok=[3])["score"] == 1.0


@pytest.mark.parametrize("text", ["8.31 J/((mol K))", "8.31 J/(mol K", "8.31 J/(mol/K)", "8.31 J/(mol K^(-1))"])
def test_an_odd_bracketed_unit_is_unreadable_not_wrong(text):
    item = {"kind": "numeric", "stem": "", "answer": {"value": 8.31, "unit": "J K^-1 mol^-1", "sf_ok": [3]}}
    g = grade.grade_item(item, {"kind": "value", "value": text})
    assert not g["correct"] and g["needs_judgement"] and g["error"] is None
    assert grade.value_problem(item, text) == "unreadable"


@pytest.mark.parametrize("text,score", [("8.31 J/(kg K)", 0), ("8.31 J K-1 mol-1", 1.0), ("8.31 J/molK", 1.0),
                                        ("8.31 J/mol/K", 1.0), ("8.31 J/mol K", 1.0), ("8.31 J K-1", 0)])
def test_unbracketed_units_mark_as_before(text, score):
    g = _num(8.31, text, "J K^-1 mol^-1", sf_ok=[3])
    assert g["score"] == score
    if not score:
        assert g["error"] == "NOTATION" and "wrong unit" in g["detail"]
