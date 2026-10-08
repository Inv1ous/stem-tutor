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


# ---------- "mm" is a millimetre, never m·m ----------
@pytest.mark.parametrize("given,expected,factor", [
    ("mm", "m^2", None), ("mm", "m2", None), ("ss", "s^2", None), ("mm", "m", 1e-3), ("mm2", "m^2", 1e-6),
    ("m2", "m^2", 1.0), ("m m", "m^2", 1.0), ("ms-1", "m s^-1", 1.0), ("ms-2", "m s^-2", 1.0), ("ms", "s", 1e-3),
    ("kg/ms2", "Pa", 1.0), ("Nm", "J", 1.0), ("kgm2", "kg m^2", 1.0), ("mmol", "mol", 1e-3), ("mms-1", "m s^-1", 1e-3),
])
def test_a_run_of_one_symbol_twice_is_not_a_square(given, expected, factor):
    got = units.unit_factor(given, expected)
    assert got == (pytest.approx(factor) if factor else None)


def test_millimetres_for_an_area_are_a_wrong_unit():
    area = {"kind": "numeric", "stem": "", "answer": {"value": 3.0, "unit": "m^2", "sf_ok": [2, 3]}}
    g = grade.grade_item(area, {"kind": "value", "value": "3.0 mm"})
    assert not g["correct"] and g["score"] == 0 and g["error"] == "NOTATION"
    for typed in ("3.0 m2", "3.0 m^2", "3.0 m²", "3000000 mm2", "3.0e4 cm2"):
        assert grade.grade_item(area, {"kind": "value", "value": typed})["score"] == 1.0, typed
    length = {"kind": "numeric", "stem": "", "answer": {"value": 3.0, "unit": "m", "sf_ok": [2, 3]}}
    assert grade.grade_item(length, {"kind": "value", "value": "3000 mm"})["score"] == 1.0
    assert not grade.grade_item(length, {"kind": "value", "value": "3.0 mm"})["correct"]


# ---------- characters that look like the right one ----------
@pytest.mark.parametrize("value,unit,text", [
    (47.0, "Ω", "47 Ω"), (47.0, "Ω", "0.047 kΩ"), (47.0, "ohm", "47 Ω"), (6.0, "N m", "6.0 N⋅m"),
    (6.0, "N m", "6.0 N·m"), (30.0, "°", "30º"), (30.0, "°", "30˚"), (25.0, "°C", "25 ºC"),
    (25.0, "°C", "25 ˚C"), (25.0, "°C", "25 ℃"), (-3.2, "", "‒3.2"), (-3.2, "", "﹣3.2"),
    (-3.2, "", "－3.2"), (-3.2, "", "‐3.2"), (-3.2, "", "‑3.2"), (-3.2, "", "−3.2"), (-3.2, "", "–3.2"),
    (-3.2, "", "− 3.2"), (-3.2, "", "- 3.2"), (3.2, "", "+ 3.2"), (1.5e-3, "", "1.5 × 10‒³"),
    (9.81, "m s^-2", "9.81 m s⁻²"), (9.81, "m s^-2", "9.81 m s－2"), (2.0, "μm", "2 µm"),
    (2.0, "µm", "2 μm"), (300.0, "K", "300 K"), (32.0, "", "３２"), (5.0, "kg", "5 kg"),
    (1.5e-3, "", "1.5×10⁻³"), (1000.0, "J", "10³ J"), (5.0, "m^2", "5 m²"),
])
def test_lookalike_characters_read_as_the_character_they_look_like(value, unit, text):
    assert _num(value, text, unit, sf_ok=[1, 2, 3])["score"] == 1.0, text


@pytest.mark.parametrize("text", ["5²", "2³ m", "100³ J", "1.5² m", "- - 3", "−− 3", "-- 3"])
def test_lookalikes_do_not_make_unreadable_text_readable(text):
    with pytest.raises(grade.ParseError):
        grade.parse_quantity(text)


@pytest.mark.parametrize("value,unit,text", [(47.0, "Ω", "47 kΩ"), (-3.2, "", "‒3.3"), (30.0, "°", "30º C"),
                                             (3.2, "", "‒3.2"), (6.0, "N m", "6.0 N⋅s")])
def test_lookalike_characters_do_not_make_a_wrong_answer_right(value, unit, text):
    assert not _num(value, text, unit, sf_ok=[1, 2, 3])["correct"], text


def test_lookalike_units_convert():
    assert units.unit_factor("kΩ", "Ω") == pytest.approx(1000.0)
    assert units.unit_factor("N⋅m", "J") == pytest.approx(1.0)
    assert units.unit_factor("µm", "m") == pytest.approx(1e-6)
    assert units.unit_readings("Ω", "Ω") == ([1.0], False)


# ---------- a label in any alphabet ----------
@pytest.mark.parametrize("value,unit,text", [
    (-57.0, "kJ mol^-1", "ΔH = −57 kJ mol^-1"), (-57.0, "kJ mol^-1", "ΔH=-57 kJ mol-1"), (-57.0, "kJ", "ΔH=-57 kJ"),
    (30.0, "°", "θ = 30°"), (30.0, "°", "θ=30°"), (2.0, "", "λ = 2"), (-57.0, "kJ mol^-1", "ΔH_r = -57 kJ/mol"),
    (24.0, "", "x = 24"), (3.0, "m s^-1", "v = 3.0 m s^-1"),
])
def test_a_greek_label_is_read_past(value, unit, text):
    assert _num(value, text, unit, sf_ok=[2, 3])["score"] == 1.0
    assert grade.value_problem({"kind": "numeric", "answer": {"value": value, "unit": unit}}, text) is None


@pytest.mark.parametrize("value,unit,text,correct", [
    (-57.0, "kJ mol^-1", "ΔH = 57 kJ mol^-1", False), (-57.0, "kJ mol^-1", "ΔH = -57 kJ", False),
    (30.0, "°", "θ = 60°", False)])
def test_a_greek_label_does_not_make_a_wrong_answer_right(value, unit, text, correct):
    assert _num(value, text, unit, sf_ok=[2, 3])["correct"] is correct


@pytest.mark.parametrize("text", ["ΔH = ", "ΔH = θ = 30", "Δ = = 5", "5 = 5", "x = y = 24"])
def test_a_label_without_a_single_value_is_still_unreadable(text):
    with pytest.raises(grade.ParseError):
        grade.parse_quantity(text)


# ---------- a function name run into its argument ----------
def _expr(expected, given):
    return grade.grade_item({"kind": "expression", "answer": {"expr": expected}, "marks": 1},
                            {"kind": "value", "value": given, "conf": 3})["correct"]


@pytest.mark.parametrize("given,expected", [
    ("sin2x", "sin(2*x)"), ("cos3x", "cos(3*x)"), ("ln2x", "log(2*x)"), ("2sinxcosx", "sin(2*x)"),
    ("2sinxcosx", "2*sin(x)*cos(x)"), ("3cos2x", "3*cos(2*x)"), ("tan2theta", "tan(2*theta)"), ("exp2x", "exp(2*x)"),
    ("sqrt2x", "sqrt(2*x)"), ("sin2xcos3x", "sin(2*x)*cos(3*x)"), ("2x sin3x", "2*x*sin(3*x)"), ("sin30", "sin(30)"),
    ("cosxsinx", "sin(2*x)/2"), ("sin2x + cos2x", "sin(2*x) + cos(2*x)"), ("ln3", "log(3)"),
])
def test_a_function_run_into_a_number_is_the_function_of_it(given, expected):
    assert grade.expression_readable(given) and _expr(expected, given), given


@pytest.mark.parametrize("given,expected", [
    ("sin2x", "2*sin(x)"), ("sin2x", "sin(x)^2"), ("cos2x", "2*cos(x)"), ("ln2x", "2*log(x)"), ("2sinxcosx", "sin(x)^2"),
    ("sin3x", "sin(2*x)"), ("x2", "2*x"), ("R2", "2*R1"),
])
def test_a_function_run_into_a_number_is_not_another_answer(given, expected):
    assert not _expr(expected, given), given


@pytest.mark.parametrize("given,expected", [
    ("sinx", "sin(x)"), ("lnx", "log(x)"), ("2cosx", "2*cos(x)"), ("tantheta", "tan(theta)"), ("sinh x", "sinh(x)"),
    ("sinx^2", "sin(x^2)"), ("m1v1", "m1*v1"), ("mv0", "m*v0"), ("1e3 x + 2.5e2 y", "1000*x + 250*y"),
    ("x2sinx", "x2*sin(x)"), ("sin^2x", "sin(x)^2"), ("cost", "cos(t)"), ("sinhx", "sinh(x)"),
])
def test_run_in_function_readings_that_already_worked_still_do(given, expected):
    assert _expr(expected, given), given


@pytest.mark.parametrize("text,value,conf", [
    ("3 = 1,5 m", "1,5 m", None), ("1=2,3", "2,3", None), ("1 = 3, 4 ~2", "3,4", 2), ("1 = 3,5 kg ~2", "3,5 kg", 2),
    ("3 = 1,25", "1,25", None), ("2 = -0,5 mol", "-0,5 mol", None),
])
def test_a_decimal_comma_keeps_the_question_open(text, value, conf):
    """"3 = 1,5 m" was Q3 = 1 (marked, and wrong, with no chance to resend) and a bad Q5."""
    (r,) = grade.parse_responses(text)
    assert r == {"n": int(text.split("=")[0]), "kind": "value", "value": value, "conf": conf}
    assert grade.value_problem({"kind": "numeric", "answer": {"value": 1.5, "unit": "m"}}, r["value"]) == "unreadable"


@pytest.mark.parametrize("text,want", [
    ("1 = 9.8 m s-2, 2 idk", [(1, "value", "9.8 m s-2"), (2, "bad", "2 idk")]),
    ("1 = 3.0 m3, 2 dk", [(1, "value", "3.0 m3"), (2, "bad", "2 dk")]),
    ("1 = 2.0 mol dm-3, 2 4", [(1, "value", "2.0 mol dm-3"), (2, "bad", "2 4")]),
    ("1 = 9.8 m s-2, 2 3.0 m", [(1, "value", "9.8 m s-2"), (2, "bad", "2 3.0 m")]),
    ("1 = 8.3 J K-1 mol-1, 2 7", [(1, "value", "8.3 J K-1 mol-1"), (2, "bad", "2 7")]),
])
def test_a_value_with_a_unit_ending_in_a_digit_never_swallows_the_next_entry(text, want):
    """Only a bare number continues past a comma ("3 = 1,5 m"): "9.8 m s-2, 2 idk" was one entry, Q1 "9.8 m s-2,2 idk"
    marked a wrong unit, and Q2 gone."""
    got = grade.parse_responses(text)
    assert [(r["n"], r["kind"], r["value"]) for r in got] == want
    item = {"kind": "numeric", "stem": "", "answer": {"value": 9.8, "unit": "m s-2"}}
    if want[0][2] == "9.8 m s-2":
        assert grade.grade_item(item, got[0])["correct"]


@pytest.mark.parametrize("given", ["9.8 m s-2,2 idk", "9.8 m s-2,2 3.0 m", "9.8 m s-2, 4"])
def test_a_unit_with_a_comma_in_it_is_asked_again_not_a_wrong_unit(given):
    g = _num(9.8, given, "m s-2")
    assert not g["correct"] and g["needs_judgement"] and g["error"] is None
    assert grade.value_problem({"kind": "numeric", "answer": {"value": 9.8, "unit": "m s-2"}}, given) == "unreadable"


def test_a_wrong_unit_without_a_comma_is_still_a_wrong_unit():
    g = _num(9.8, "9.8 kg", "m s-2")
    assert not g["correct"] and g["error"] == "NOTATION" and "wrong unit" in g["detail"]


@pytest.mark.parametrize("text,want", [
    ("1 = 3, 4 = 5", [(1, "value", "3"), (4, "value", "5")]),
    ("1 = 2.5, 2 = 3", [(1, "value", "2.5"), (2, "value", "3")]),
    ("1B, 2C, 3?", [(1, "choice", "B"), (2, "choice", "C"), (3, "idk", None)]),
    ("1 = 3 ~2, 4 kg", [(1, "value", "3"), (4, "bad", "4 kg")]),
    ("1 = 5\n2", [(1, "value", "5"), (2, "bad", "2")]),
    ("1 = 12,345,678 J", [(1, "value", "12,345,678 J")]),
    ("1 = 1,000 m ~2, 2B", [(1, "value", "1,000 m"), (2, "choice", "B")]),
    ("6 pts=1,3, 7 = 2", [(6, "points", [1, 3]), (7, "value", "2")]),
    ("1B3, 2 # what, 3?", [(1, "choice", "B"), (2, "bad", "2 # what"), (3, "idk", None)]),
    ("1 = x^2+1, 2?", [(1, "value", "x^2+1"), (2, "idk", None)]),
    ("1 = 5, 2 = 1,5", [(1, "value", "5"), (2, "value", "1,5")]),
])
def test_entries_around_a_comma_split_as_before(text, want):
    assert [(r["n"], r["kind"], r["value"]) for r in grade.parse_responses(text)] == want


@pytest.mark.parametrize("given", ["sin2 x", "ln2 x", "cos2 (x)", "sin2(x)"])
def test_a_function_number_then_a_separate_argument_is_unreadable(given):
    """sin2 x may be sin²x with its superscript lost, or sin(2x): asked again, never marked."""
    assert not grade.expression_readable(given)
    g = grade.grade_item({"kind": "expression", "answer": {"expr": "sin(2*x)"}}, {"kind": "value", "value": given})
    assert not g["correct"] and g["needs_judgement"]
