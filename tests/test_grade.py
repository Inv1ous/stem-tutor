import os
import subprocess
import sys

import pytest

from tutorlib import grade


# ---------- compact response syntax ----------
def test_parse_mcq_with_confidence():
    r = grade.parse_responses("1B3, 2d1")
    assert r == [
        {"n": 1, "kind": "choice", "value": "B", "conf": 3},
        {"n": 2, "kind": "choice", "value": "D", "conf": 1},
    ]


def test_parse_numeric_with_unit_and_confidence():
    (r,) = grade.parse_responses("3 = 4.52e-3 mol dm-3 ~2")
    assert r == {"n": 3, "kind": "value", "value": "4.52e-3 mol dm-3", "conf": 2}


def test_parse_dont_know_and_newlines():
    r = grade.parse_responses("4?\n5 = x^2+1")
    assert r[0] == {"n": 4, "kind": "idk", "value": None, "conf": None}
    assert r[1]["value"] == "x^2+1" and r[1]["conf"] is None


def test_parse_self_marked_points():
    (r,) = grade.parse_responses("6 pts=1,3")
    assert r == {"n": 6, "kind": "points", "value": [1, 3], "conf": None}


def test_parse_marks_garbage_as_unreadable():
    assert grade.parse_responses("hello there") == [{"n": None, "kind": "bad", "value": "hello there", "conf": None}]


# ---------- numbers ----------
@pytest.mark.parametrize(
    "text,value",
    [
        ("4.52e-3", 4.52e-3),
        ("4.52 × 10^-3", 4.52e-3),
        ("4.52x10-3", 4.52e-3),
        ("4.52*10^(-3)", 4.52e-3),
        ("4.52 × 10⁻³", 4.52e-3),
        ("-0.050", -0.05),
        ("1/4", 0.25),
    ],
)
def test_parse_number_formats(text, value):
    got, _unit, _sf = grade.parse_quantity(text)
    assert got == pytest.approx(value)


def test_sig_figs_counted_from_text():
    assert grade.parse_quantity("0.050")[2] == 2
    assert grade.parse_quantity("4.52e-3")[2] == 3
    assert grade.parse_quantity("1200")[2] is None  # ambiguous trailing zeros
    assert grade.parse_quantity("1.20 × 10^3")[2] == 3


def test_unit_split_from_number():
    _v, unit, _sf = grade.parse_quantity("9.81 m s-2")
    assert unit == "m s-2"


# ---------- units ----------
@pytest.mark.parametrize(
    "a,b,factor",
    [
        ("m s-1", "m/s", 1.0),
        ("km", "m", 1000.0),
        ("mol dm-3", "mol dm^-3", 1.0),
        ("g", "kg", 1e-3),
        ("kJ mol-1", "J mol-1", 1000.0),
        ("cm3", "dm3", 1e-3),
        ("N m", "J", 1.0),
        ("ms⁻²", "m s-2", 1.0),
        ("minutes", "min", 1.0),
        ("mins", "min", 1.0),
        ("hours", "min", 60.0),
        ("seconds", "min", 1 / 60),
    ],
)
def test_unit_conversion_factor(a, b, factor):
    assert grade.unit_factor(a, b) == pytest.approx(factor)


def test_incompatible_units_return_none():
    assert grade.unit_factor("m", "s") is None


# ---------- grading ----------
MCQ = {"kind": "mcq", "answer": "B", "distractors": {"A": "m1", "C": "m2"}, "marks": 1}
NUM = {
    "kind": "numeric",
    "answer": {"value": 0.0425, "unit": "mol", "sf": 3},
    "distractors": [{"value": 2.49, "misconception": "m1"}],
    "marks": 2,
}


def test_mcq_correct():
    g = grade.grade_item(MCQ, {"kind": "choice", "value": "B", "conf": 4})
    assert g["correct"] and g["score"] == 1.0 and g["error"] is None


def test_mcq_distractor_maps_to_misconception():
    g = grade.grade_item(MCQ, {"kind": "choice", "value": "A", "conf": 4})
    assert not g["correct"] and g["error"] == "CONCEPT" and g["misconception"] == "m1"


def test_idk_is_recall_gap():
    g = grade.grade_item(MCQ, {"kind": "idk", "value": None, "conf": None})
    assert g["score"] == 0 and g["error"] == "RECALL"


def test_numeric_correct_with_unit_conversion():
    g = grade.grade_item(NUM, {"kind": "value", "value": "42.5 mmol", "conf": 3})
    assert g["correct"] and g["score"] == 1.0


def test_numeric_wrong_sig_figs_flags_notation():
    g = grade.grade_item(NUM, {"kind": "value", "value": "0.04250 mol", "conf": 3})
    assert g["correct"] and g["error"] == "NOTATION" and g["score"] == pytest.approx(0.5)


def test_numeric_missing_unit_flags_notation():
    g = grade.grade_item(NUM, {"kind": "value", "value": "0.0425", "conf": 3})
    assert g["correct"] and g["error"] == "NOTATION"


def test_numeric_distractor_value_maps_to_misconception():
    g = grade.grade_item(NUM, {"kind": "value", "value": "2.49 mol", "conf": 4})
    assert not g["correct"] and g["misconception"] == "m1" and g["error"] == "CONCEPT"


def test_numeric_power_of_ten_error_is_notation():
    g = grade.grade_item(NUM, {"kind": "value", "value": "4.25 mol", "conf": 2})
    assert not g["correct"] and g["error"] == "NOTATION"


def test_numeric_sign_error_is_slip_candidate():
    g = grade.grade_item(NUM, {"kind": "value", "value": "-0.0425 mol", "conf": 2})
    assert not g["correct"] and g["error"] == "SLIP"


def test_numeric_unclassified_wrong():
    g = grade.grade_item(NUM, {"kind": "value", "value": "0.9 mol", "conf": 2})
    assert not g["correct"] and g["error"] is None and g["needs_judgement"]


def test_expression_equivalence():
    item = {"kind": "expression", "answer": {"expr": "2*x*exp(x**2)"}, "marks": 2}
    ok = grade.grade_item(item, {"kind": "value", "value": "2x e^(x^2)", "conf": 3})
    bad = grade.grade_item(item, {"kind": "value", "value": "e^(x^2)", "conf": 3})
    assert ok["correct"] and not bad["correct"]


def test_rubric_keyword_precheck_partial():
    item = {
        "kind": "short",
        "marks": 2,
        "rubric": [
            {"point": "electrons delocalised", "keywords": [["electron"], ["delocalised", "delocalized", "sea"]]},
            {"point": "attraction to positive ions", "keywords": [["attract"], ["positive ion", "cation"]]},
        ],
    }
    g = grade.grade_item(item, {"kind": "value", "value": "a sea of electrons", "conf": 3})
    assert g["score"] == pytest.approx(0.5)
    assert g["needs_judgement"] and g["unmatched"] == ["attraction to positive ions"]


def test_self_marked_points_score():
    item = {"kind": "structured", "marks": 4, "scheme": [{"mark": "M1"}, {"mark": "A1"}, {"mark": "M1"}, {"mark": "A1"}]}
    g = grade.grade_item(item, {"kind": "points", "value": [1, 2, 3], "conf": None})
    assert g["score"] == pytest.approx(0.75) and g["self_marked"]


@pytest.mark.parametrize("text,value", [("(−1)", -1.0), ("( -1 )", -1.0), ("−1", -1.0), ("= -1", -1.0), ("[2.5] m", 2.5)])
def test_quantity_tolerates_brackets_equals_and_unicode_minus(text, value):
    assert grade.parse_quantity(text)[0] == pytest.approx(value)


def test_unreadable_entry_is_reported_not_raised():
    rs = grade.parse_responses("1B3, 2 # what, 3?")
    assert [r["kind"] for r in rs] == ["choice", "bad", "idk"] and rs[1]["n"] == 2


def test_entries_split_on_question_numbers_but_not_thousands():
    rs = grade.parse_responses("1 = (−1) ~3, 2 $x, 3 = 1,000 m ~2\n")
    assert [(r["n"], r["kind"]) for r in rs] == [(1, "value"), (2, "bad"), (3, "value")]
    assert rs[0]["conf"] == 3 and rs[2]["value"] == "1,000 m"


# ---------- expression input is data, never code (B-005) ----------
def test_expression_input_cannot_run_code(tmp_path):
    item = {"kind": "expression", "answer": {"expr": "x"}, "marks": 1}
    proof = tmp_path / "proof.txt"
    for payload in (f"open({str(proof)!r}, 'w').write('X')",
                    f"__import__('pathlib').Path({str(proof)!r}).touch()",
                    "x.__class__", "(lambda: x)()", "[x][0]", "x if 1 else 2"):
        g = grade.grade_item(item, {"kind": "value", "value": payload, "conf": 3})
        assert not g["correct"] and g["needs_judgement"], payload
    assert not proof.exists()


def test_expression_power_tower_is_refused_not_computed():
    code = ("import sys; from tutorlib import grade; "
            "g = grade.grade_item({'kind': 'expression', 'answer': {'expr': 'x'}}, "
            "{'kind': 'value', 'value': sys.argv[1]}); print(g['correct'], g['needs_judgement'])")
    env = {**os.environ, "PYTHONPATH": os.pathsep.join(sys.path), "PYTHONDONTWRITEBYTECODE": "1"}
    for tower in ("9^9^9^9", "((10^1000)^1000)^1000", "2^(10^6)"):
        out = subprocess.run([sys.executable, "-c", code, tower], capture_output=True, text=True, timeout=20, env=env)
        assert out.stdout.split() == ["False", "True"], (tower, out.stderr[-300:])


@pytest.mark.parametrize("given,expected", [
    ("u^2 + 2 a s", "u**2 + 2*a*s"),
    ("sin(x)^2 + cos(x)^2", "1"),
    ("ln(e^x)", "x"),
    ("0.5 m v^2", "m*v**2/2"),
    ("pi r^2", "pi*r**2"),
    ("sqrt(2 g h)", "(2*g*h)**0.5"),
    ("abs(-x) + 10^3", "abs(x) + 1000"),
    ("ln(x^2)", "2*ln(x)"),
    ("sqrt(x) sqrt(y)", "sqrt(x*y)"),
    ("(x^2 - 1)/(x - 1)", "x + 1"),
    ("ln(8)", "3*ln(2)"),
    ("sqrt(8)", "2*sqrt(2)"),
    ("e^(e^x)", "exp(exp(x))"),
    ("log(x, 10)", "log(x)/log(10)"),
])
def test_expression_equivalent_forms_still_match(given, expected):
    item = {"kind": "expression", "answer": {"expr": expected}, "marks": 1}
    assert grade.grade_item(item, {"kind": "value", "value": given, "conf": 3})["correct"]


# ---------- numeric precision rules (B-002, B-004) ----------
def _num(value, text, **answer):
    item = {"kind": "numeric", "answer": {"value": value, "unit": answer.pop("unit", ""), **answer}}
    return grade.grade_item(item, {"kind": "value", "value": text, "conf": 3})


@pytest.mark.parametrize("value,text,ok", [
    (117, "118", False), (117, "117", True), (117, "117.0", True), (500, "501", False), (500, "499.9", False),
    (0.1 * 3, "0.3", True), (3, "3.01", False),
])
def test_exact_answers_allow_no_error(value, text, ok):
    assert _num(value, text, exact=True)["correct"] is ok


@pytest.mark.parametrize("text,sf_ok,score", [
    ("16 N", [2, 3], 1.0),      # B-004: correct to 2 s.f., which is allowed
    ("16.5 N", [2, 3], 1.0),
    ("17 N", [2, 3], 0),        # wrongly rounded
    ("16 N", [3, 4], 0.5),      # right value, too few s.f.
    ("2e1 N", [2, 3], 0),       # 1 s.f. is not allowed, so no rounding leeway
    ("2e1 N", [1, 2], 1.0),
    ("0.016 kN", [2, 3], 1.0),
])
def test_value_rounded_to_its_own_sig_figs_is_right(text, sf_ok, score):
    g = _num(16.46207763315433, text, unit="N", sf_ok=sf_ok)
    assert g["score"] == score and g["correct"] is (score > 0)


def test_rounded_distractor_still_names_the_misconception():
    item = {"kind": "numeric", "answer": {"value": 16.46, "unit": "N", "sf_ok": [2, 3]},
            "distractors": [{"value": 1.049, "misconception": "m1"}]}
    g = grade.grade_item(item, {"kind": "value", "value": "1.0 N", "conf": 3})
    assert g["misconception"] == "m1"


@pytest.mark.parametrize("value,text", [(10.392304845413266, "10 N"), (20.38735983690112, "20 N"), (19.78477, "20 N")])
def test_trailing_zero_answer_rounded_correctly_is_right(value, text):  # published 9702-1.4-i03, 9702-2.1-i28/i38
    assert _num(value, text, unit="N", sf_ok=[2, 3])["score"] == 1.0


def test_trailing_zero_is_read_strictly_for_rounding():
    assert not _num(16.46, "20 N", unit="N", sf_ok=[2, 3])["correct"]


@pytest.mark.parametrize("value,text,ok", [
    (9.6013, "10", False), (96, "1.0e2", False),  # coarser than 2 s.f. once the power of ten changes
    (9.96, "10", True), (1050, "1.1e3", True),    # 2 s.f. rounding, halves rounded up
])
def test_rounding_is_judged_at_the_answers_magnitude(value, text, ok):
    assert _num(value, text, sf_ok=[2, 3])["correct"] is ok


# ---------- units after a slash (B-022) ----------
@pytest.mark.parametrize("given,expected,factor", [
    ("kg/ms2", "Pa", 1.0), ("kg/ms2", "N", None), ("J/molK", "J mol^-1 K^-1", 1.0), ("J/molK", "J mol K^-1", None),
    ("N/m2", "Pa", 1.0), ("kg/m3", "g cm-3", 1e-3), ("ms-2", "m s^-2", 1.0), ("kg m/s2", "N", 1.0),
])
def test_joined_units_after_a_slash_are_all_below_the_line(given, expected, factor):
    got = grade.unit_factor(given, expected)
    assert got == (pytest.approx(factor) if factor else None)


def test_compact_denominator_unit_is_not_a_force():
    g = grade.grade_item({"kind": "numeric", "answer": {"value": 1, "unit": "N"}}, {"kind": "value", "value": "1 kg/ms2"})
    assert not g["correct"]


@pytest.mark.parametrize("text", ["1 km9999", "1e300 km99", "1 km-9999", "1e-300 mm99"])
def test_extreme_unit_exponent_is_a_wrong_unit_not_a_crash(text):  # B-003
    g = grade.grade_item({"kind": "numeric", "answer": {"value": 9.81, "unit": "m"}}, {"kind": "value", "value": text})
    assert not g["correct"] and g["score"] == 0


def test_value_overflowing_on_unit_conversion_is_not_a_crash():  # B-003
    g = grade.grade_item({"kind": "numeric", "answer": {"value": 9.81, "unit": "pm"}}, {"kind": "value", "value": "1e305 Gm"})
    assert not g["correct"] and g["score"] == 0


# ---------- plain-number answers (B-001) ----------
@pytest.mark.parametrize("text", ["500 + 1", "500+1", "2^10", "5 000", "500 - 1", "117 * 1", "9.81 (m s-2)"])
def test_arithmetic_after_the_number_is_unreadable(text):
    with pytest.raises(grade.ParseError):
        grade.parse_quantity(text)


# ---------- superscript powers (B-036) ----------
@pytest.mark.parametrize("text,value,unit", [
    ("10³ J", 1000.0, "J"), ("10^3 J", 1000.0, "J"), ("10⁻³ m", 1e-3, "m"), ("-10² N", -100.0, "N"),
    ("10^(-3) m", 1e-3, "m"), ("2.5×10³ m", 2500.0, "m"), ("6.02 × 10²³", 6.02e23, ""),
    ("1.5 × 10⁻³ mol dm⁻³", 1.5e-3, "mol dm-3"), ("3 m s⁻²", 3.0, "m s-2"), ("5 m²", 5.0, "m2")])
def test_a_superscript_power_keeps_its_value(text, value, unit):
    got, got_unit, _ = grade.parse_quantity(text)
    assert got == pytest.approx(value) and got_unit == unit


@pytest.mark.parametrize("text", ["5²", "2³ m", "100³ J", "1.5² m", "10³⁺² J"])
def test_a_power_that_is_not_a_power_of_ten_is_unreadable_not_misread(text):
    with pytest.raises(grade.ParseError):  # the question then stays open; before, 5² was marked as 52
        grade.parse_quantity(text)


def test_a_power_of_ten_answer_is_marked_on_its_value():
    item = {"kind": "numeric", "stem": "A 40 W motor runs for 25 s. Calculate the energy.",
            "answer": {"value": 1000.0, "unit": "J", "sf_ok": [2, 3]}}
    assert grade.parse_quantity("10³ J") == (1000.0, "J", 1)  # read as 1×10³
    assert grade.grade_item(item, {"kind": "value", "value": "10³ J"})["score"] == 1.0  # exactly 1000: no zeros needed
    assert grade.grade_item(item, {"kind": "value", "value": "1.0×10³ J"})["score"] == 1.0
    assert grade.value_problem(item, "5² J") == "unreadable"


@pytest.mark.parametrize("text", ["500 kg", "500 mm", "500 banana"])
def test_unit_on_a_plain_number_answer_earns_no_credit(text):
    g = _num(500, text, exact=True)
    assert not g["correct"] and g["score"] == 0 and g["needs_judgement"]
    assert grade.value_problem({"kind": "numeric", "answer": {"value": 500, "unit": ""}}, text) == "unit"


def test_percent_sign_only_where_the_question_asks_for_a_percentage():  # B-001 reopened
    pct = {"kind": "numeric", "stem": "Calculate the percentage of the mass in the nucleus.",
           "answer": {"value": 99.95, "unit": "", "sf_ok": [3, 4]}}
    mm = {"kind": "numeric", "stem": "Give the length of the wire in millimetres.", "answer": {"value": 500, "unit": ""}}
    assert grade.grade_item(pct, {"kind": "value", "value": "99.95%"})["score"] == 1.0
    assert grade.value_problem(pct, "99.95 %") is None
    assert not grade.grade_item(mm, {"kind": "value", "value": "500%"})["correct"]
    assert grade.value_problem(mm, "500%") == "unit"


@pytest.mark.parametrize("given,expected", [
    ("abs(x)", "x"), ("sqrt(x^2)", "x"), ("abs(-x) + 1000", "x + 1000"), ("abs(x y)", "x*y"), ("x^2/abs(x)", "x"),
])
def test_identities_true_only_for_positive_values_are_rejected(given, expected):  # B-021
    item = {"kind": "expression", "answer": {"expr": expected}, "marks": 1}
    assert not grade.grade_item(item, {"kind": "value", "value": given, "conf": 3})["correct"]


def test_expression_grading_time_is_bounded():  # B-023
    code = ("import sys, time\nfrom tutorlib import grade\n"
            "for s in sys.argv[1:]:\n"
            "    t = time.perf_counter()\n"
            "    g = grade.grade_item({'kind': 'expression', 'answer': {'expr': 'x'}}, {'kind': 'value', 'value': s})\n"
            "    print(repr(s), g['correct'], round(time.perf_counter() - t, 2))\n")
    inputs = ["Pow(2, 1000000000)", "2Pow(2, 10^9)", "Integer(10)^10^9", "(x+1)^10000", "(x+1)^1000 - x^1000",
              "x^x^x^x", "exp(exp(exp(x)))", "e^(e^(e^x))", "x^(x^x)", "sin(10^100 x)", "x^(x^10)"]
    env = {**os.environ, "PYTHONPATH": os.pathsep.join(sys.path), "PYTHONDONTWRITEBYTECODE": "1"}
    out = subprocess.run([sys.executable, "-c", code, *inputs], capture_output=True, text=True, timeout=90, env=env)
    rows = [line.rsplit(" ", 2) for line in out.stdout.splitlines()]
    assert len(rows) == len(inputs), out.stderr[-400:]
    for s, correct, secs in rows:
        assert correct == "False" and float(secs) < 2, (s, secs)


# ---------- variable names: keywords and subscripts ----------
@pytest.mark.parametrize("given,expected", [
    ("u^2 + 2as", "u**2 + 2*a*s"),              # published 9702-2.1-i24: "as" is a Python keyword
    ("v^2 - u^2 = 2as".split(" = ")[1], "2*a*s"),
    ("h c / lambda", "h*c/lambda"),
    ("m1 v1 + m2 v2", "m1*v1 + m2*v2"),
    ("m1v1", "m1*v1"),
    ("mv0", "m*v0"),
    ("1e3 x + 2.5e2 y", "1000*x + 250*y"),       # the e of a number is not a subscript
])
def test_keywords_and_subscripted_names_are_variables(given, expected):
    item = {"kind": "expression", "answer": {"expr": expected}, "marks": 1}
    assert grade.grade_item(item, {"kind": "value", "value": given, "conf": 3})["correct"]


@pytest.mark.parametrize("given,expected", [("R2", "2*R1"), ("v1", "v"), ("x1 + x2", "3*x")])
def test_subscripted_names_are_not_numbers(given, expected):
    item = {"kind": "expression", "answer": {"expr": expected}, "marks": 1}
    assert not grade.grade_item(item, {"kind": "value", "value": given, "conf": 3})["correct"]


@pytest.mark.parametrize("given,expected", [("1/(1/a + 1/b)", "a*b/(a + b)"), ("1/(1/R1 + 1/R2)", "R1*R2/(R1 + R2)")])
def test_equivalence_survives_a_sample_on_a_pole(given, expected):  # a = 1, b = -1 is one of the sampled points
    item = {"kind": "expression", "answer": {"expr": expected}, "marks": 1}
    assert grade.grade_item(item, {"kind": "value", "value": given, "conf": 3})["correct"]


def test_keywords_alone_never_mark_a_short_answer_right():  # B-024
    item = {"kind": "short", "marks": 2, "rubric": [
        {"point": "velocity is the rate of change of displacement", "keywords": [["rate of change of displacement"]]},
        {"point": "acceleration is the rate of change of velocity", "keywords": [["rate of change of velocity"]]}]}
    swapped = "Velocity is the rate of change of velocity. Acceleration is the rate of change of displacement."
    g = grade.grade_item(item, {"kind": "value", "value": swapped})
    assert not g["correct"] and g["needs_judgement"] and g["score"] == 1.0  # every phrase is there: only a hint


@pytest.mark.parametrize("text", ["1e308", "-1e308", "1e-308", "5e-324"])
def test_wildly_wrong_finite_values_grade_without_crashing(text):  # B-025
    g = _num(7.5e-7, text, sf_ok=[1, 2, 3])
    assert not g["correct"] and g["score"] == 0


@pytest.mark.parametrize("given,expected", [  # B-034: maths as the app displays it
    ("u² + 2as", "u**2 + 2*a*s"), ("u^2 + 2×a×s", "u**2 + 2*a*s"), ("2πr", "2*pi*r"), ("√(2gh)", "sqrt(2*g*h)"),
    ("x⁻¹", "1/x"), ("½mv²", "m*v**2/2"), ("mω²r", "m*omega**2*r"), ("hc/λ", "h*c/lambda"), ("F·Δt", "F*Delta*t"),
    ("a − b", "a - b"), ("a ÷ b", "a/b"),
])
def test_unicode_maths_is_read_like_ascii(given, expected):
    item = {"kind": "expression", "answer": {"expr": expected}, "marks": 1}
    assert grade.grade_item(item, {"kind": "value", "value": given, "conf": 3})["correct"], given


@pytest.mark.parametrize("given,expected,factor", [
    ("m/s", "ms-1", 1.0), ("m s-1", "ms-1", 1.0), ("°C", "°C", 1.0), ("° C", "°C", 1.0), ("rpm", "rpm", 1.0),
    ("K", "°C", None),  # an offset, not a factor: never silently equal
])
def test_expected_units_read_every_way_and_identical_units_match(given, expected, factor):  # Haiku review
    got = grade.unit_factor(given, expected)
    assert got == (pytest.approx(factor) if factor else None)


# ---------- a unit that is not a unit (B-035) ----------
@pytest.mark.parametrize("given", ["m" * 30, "m" * 200, "m" * 29 + "z", "ms " * 40, "mms mms mms mms mms mms mms mms"])
def test_a_long_run_of_unit_letters_is_refused_without_trying_every_split(given, monkeypatch):
    from tutorlib import units
    calls = []
    symbol = units._symbol
    monkeypatch.setattr(units, "_symbol", lambda sym: calls.append(1) or symbol(sym))
    assert units.unit_factor(given, "m") is None
    assert len(calls) < 20_000  # "m" * 30 took 1.3 million readings and froze the app while it marked


@pytest.mark.parametrize("given,expected,factor", [
    ("kgms-2", "N", 1.0), ("kg m^2 s^-3 A^-1", "V", 1.0), ("J mol-1 K-1", "kg m2 s-2 mol-1 K-1", 1.0),
    ("kJ/molK", "J mol-1 K-1", 1000.0), ("minutes", "s", 60.0), ("mmol dm-3", "mol m-3", 1.0)])
def test_real_units_are_still_read(given, expected, factor):
    from tutorlib import units
    assert units.unit_factor(given, expected) == pytest.approx(factor)


# ---------- "rounded at your own precision" is a rounding, not a window ----------
@pytest.mark.parametrize("typed,true,sf_ok", [
    ("96 N", 100.5, [2, 3]), ("98 N", 102.0, [2, 3]), ("9.8 N", 10.3, [2, 3]), ("0.95 N", 1.0, [2, 3]),
    ("0.5 N", 1.0, [1, 2]), ("8 N", 12.0, [1, 2]), ("5e23 N", 1e24, [1, 2])])
def test_a_value_in_the_decade_below_is_not_a_rounding_of_the_answer(typed, true, sf_ok):
    """The check allowed half a unit of the answer's own scale either side, so just above a power of ten it took
    values up to 5% (2 figures) or 50% (1 figure) too small as the answer correctly rounded."""
    item = {"kind": "numeric", "answer": {"value": true, "unit": "N", "sf_ok": sf_ok}}
    assert not grade.grade_item(item, {"kind": "value", "value": typed})["correct"]


@pytest.mark.parametrize("typed,true,sf_ok", [
    ("1.3 N", 1.2771, [2, 3]), ("10 N", 9.96, [2, 3]), ("1.0e2 N", 100.5, [2, 3]), ("0.10 N", 0.0996, [2, 3]),
    ("2 N", 2.5, [1, 2]), ("3 N", 2.5, [1, 2]), ("1e24 N", 1.4e24, [1, 2])])
def test_the_answer_rounded_at_your_own_figures_still_counts(typed, true, sf_ok):
    item = {"kind": "numeric", "answer": {"value": true, "unit": "N", "sf_ok": sf_ok}}
    assert grade.grade_item(item, {"kind": "value", "value": typed})["score"] == 1.0


@pytest.mark.parametrize("typed,true,sf_ok", [
    ("2400 N", 2375.0, [2, 3]), ("2380 N", 2375.0, [2, 3]), ("1500 N", 1540.0, [2, 3]), ("-200 N", -198.0, [2, 3]),
    ("13000 N", 13376.0, [2, 3, 4]), ("1200 N", 1250.0, [2, 3]), ("1300 N", 1250.0, [2, 3]), ("2400 mN", 2.375, [2, 3]),
    ("20 N", 24.3, [1, 2])])
def test_a_rounded_whole_number_written_with_zeros_counts(typed, true, sf_ok):
    """2375 to 2 s.f. is written 2400. Read as four figures it was 1% out and marked wrong."""
    item = {"kind": "numeric", "answer": {"value": true, "unit": "N", "sf_ok": sf_ok}}
    assert grade.grade_item(item, {"kind": "value", "value": typed})["score"] == 1.0


@pytest.mark.parametrize("typed,true,sf_ok", [
    ("2000 N", 2375.0, [2, 3]), ("2300 N", 2375.0, [2, 3]), ("20 N", 24.3, [2, 3]), ("1000 N", 1400.0, [2, 3]),
    ("2400.0 N", 2375.0, [2, 3]), ("1.30 N", 1.2771, [2, 3])])
def test_zeros_do_not_make_a_wrong_rounding_right(typed, true, sf_ok):
    item = {"kind": "numeric", "answer": {"value": true, "unit": "N", "sf_ok": sf_ok}}
    assert not grade.grade_item(item, {"kind": "value", "value": typed})["correct"]


# ---------- an exact answer and its figures ----------
BRAKING = "A car travelling at 30 m s$^{-1}$ brakes uniformly and stops in 50 m. Calculate the deceleration."


def _q(value, sf_ok, unit="m s^-2", kc="9702-2.1.7", stem=BRAKING):
    return {"kind": "numeric", "kcs": [kc], "stem": stem, "answer": {"value": value, "unit": unit, "sf_ok": sf_ok}}


def _mark(item, typed):
    g = grade.grade_item(item, {"kind": "value", "value": typed})
    return g["score"], g.get("detail")


@pytest.mark.parametrize("item,typed", [
    (_q(9.0, [2, 3]), "9 m s-2"),  # the learner's own answer, 30² / (2 × 50): marked down for not writing 9.00
    (_q(3.0, [2, 3]), "3 ms^-2"),
    (_q(0.5, [2, 3], unit=""), "0.5"),
    (_q(0.0, [2, 3], unit="m"), "0 m"),
    (_q(500.0, [2, 3], unit="J"), "0.5 kJ"),
    (_q(0.005, [2, 3], unit="m"), "5×10⁻³ m"),
    (_q(1000.0, [2, 3], unit="J"), "10³ J"),
    (_q(26.0, [3, 4], unit="", kc="S1-2.2", stem="Given $\\Sigma y=200$ for $n=25$, find $\\bar x$."), "26"),
])
def test_an_exact_answer_needs_no_zeros_added(item, typed):
    """CAIE credits an answer that equals the mark scheme's once rounded to its figures; Edexcel asks for 3 s.f.
    only of answers that are not exact. Nothing was rounded away, so zeros would add nothing."""
    assert _mark(item, typed) == (1.0, None)


@pytest.mark.parametrize("item,typed,detail", [
    (_q(3.02, [2, 3]), "3 m s-2", "1 s.f. (want 2/3)"),  # within 1%, but a figure was rounded away
    (_q(1.2771349, [2, 3], unit="s"), "1.2771 s", "5 s.f. (want 2/3)"),
    (_q(1.2771349, [3, 4], unit="", kc="S1-2.4", stem="Find the standard deviation."), "1.27713", "6 s.f. (want 3/4)"),
])
def test_a_rounded_answer_is_still_marked_on_its_figures(item, typed, detail):
    assert _mark(item, typed) == (0.5, detail)


RATIO = "Calculate the deflection of the ion as a fraction of the proton's. Give your answer to 2 significant figures."
ROOT = "Use the quadratic formula to solve $x^2+8x-9=0$, giving the positive root correct to 3 s.f."
WIRE = "A micrometer reads $-0.04$ mm with its jaws closed and $1.46$ mm on a wire. Calculate the true diameter, in mm."
LIFT = "A 3 kg load is raised vertically by 2.5 m. Calculate its gain in gravitational potential energy."


@pytest.mark.parametrize("item,typed,detail", [
    (_q(0.05, [2, 3], unit="", kc="9701-1.1.4", stem=RATIO), "0.05", "1 s.f. (want 2/3)"),  # the question says how many
    (_q(1.0, [3, 4], unit="", kc="P1-1.6", stem=ROOT), "1", "1 s.f. (want 3/4)"),
    (_q(2.5, [2, 3], unit="cm", stem="Find the length, to 2 d.p."), "2.5 cm", None),  # as asked: 2 s.f. is accepted
    (_q(2.0, [2, 3], unit="cm", stem="Find the length to the nearest 0.1 cm."), "2 cm", "1 s.f. (want 2/3)"),
    (_q(1.5, [3], unit="mm", kc="9702-1.3.2", stem=WIRE), "1.5 mm", "2 s.f. (want 3)"),  # a reading: 1.50 on a micrometer
    (_q(73.575, [2, 3], unit="J", kc="9702-5.2.3", stem=LIFT), "73.575 J", "5 s.f. (want 2/3)"),  # 3 × 9.81 × 2.5, unrounded
    (_q(9.0, [2, 3]), "9.000 m s-2", "4 s.f. (want 2/3)"),  # figures the data cannot support
])
def test_figures_still_count_where_they_carry_meaning(item, typed, detail):
    assert _mark(item, typed) == ((0.5, detail) if detail else (1.0, None))


def test_one_accepted_count_fixes_the_figures_however_it_is_written():
    item = {"kind": "numeric", "kcs": ["9702-1.3.2"], "stem": WIRE, "answer": {"value": 1.5, "unit": "mm", "sf": 3}}
    assert _mark(item, "1.5 mm") == (0.5, "2 s.f. (want 3)") and _mark(item, "1.50 mm") == (1.0, None)


def test_in_maths_an_exact_answer_may_be_given_in_full():
    coded = "A data set is coded using $y=(x-20)/5$. Given $\\mathrm{Var}(Y)=4.50$, find $\\mathrm{Var}(X)$."
    assert _mark(_q(112.5, [2, 3], unit="", kc="S1-2.5", stem=coded), "112.5") == (1.0, None)
    assert _mark(_q(19.375, [3, 4], unit="", kc="S1-2.2", stem="Find $\\bar x$."), "19.375") == (1.0, None)
    assert _mark(_q(112.5, [2, 3], unit="J", stem="Calculate the work done."), "112.5 J") == (0.5, "4 s.f. (want 2/3)")


def test_the_same_quantity_in_a_tidier_unit_is_the_same_answer():
    """Asked by the learner: answers given in a cleaner unit (kW for W) were marked wrong. A prefix always worked.
    Words after the unit ("200 W of input", in the learner's log), a unit typed without its capitals, or one spelled
    out did not."""
    from tutorlib import grade, units
    item = {"id": "x", "kind": "numeric", "kcs": ["9702-5.1.1"], "stem": "Calculate the power output.",
            "answer": {"value": 1500.0, "unit": "W", "sf_ok": [2, 3]}}
    for typed in ("1500 W", "1.5 kW", "1.5 kw", "1.5 KW", "1.5 kilowatts", "1500 watts", "0.0015 MW", "1.5e3 w",
                  "1.5 kW of input", "1500 W in total", "1.5 kw (3 s.f.)", "1500 J per s", "1500 joules per second"):
        g = grade._grade_numeric(item, {"value": typed})
        assert g["correct"] and g["score"] == 1.0, typed
    assert "capitals" in grade._grade_numeric(item, {"value": "1.5 kw"}).get("detail")  # right, and told how to write it
    for typed in ("1.5 kW", "1.5 kW of input"):
        assert not grade._grade_numeric(item, {"value": typed}).get("detail"), typed
    for typed in ("1.5 mw", "1.5 W", "1.5 kJ", "1500 kw", "1500 W s", "1500 W per second", "1.5 kN",
                  "1500 J per second squared"):
        assert not grade._grade_numeric(item, {"value": typed})["correct"], typed
    assert "'kN'" in grade._grade_numeric(item, {"value": "1.5 kN"})["detail"]  # says which unit, and why not
    assert units.unit_readings("kw", "W") == ([1000.0], True) and units.unit_readings("xyz", "W") == ([], False)
    assert units.unit_readings("kW of input", "W") == ([1000.0], False)
    assert sorted(units.unit_readings("mw", "W")[0]) == [0.001, 1e6]  # milli or mega: the answer decides


# ---------- hunter batch after 1.6.0 ----------
@pytest.mark.parametrize("text,value,unit", [("2,880kJ", 2880.0, "kJ"), ("2,880 kJ", 2880.0, "kJ"),
                                             ("1,000m", 1000.0, "m"), ("12,345,678 J", 12345678.0, "J")])
def test_a_thousands_comma_holds_when_the_unit_touches_the_number(text, value, unit):
    got, got_unit, _ = grade.parse_quantity(text)
    assert got == pytest.approx(value) and got_unit == unit


@pytest.mark.parametrize("text", ["1,5", "2,88", "2,8800"])
def test_a_comma_that_is_not_a_thousands_separator_is_still_unreadable(text):
    with pytest.raises(grade.ParseError):
        grade.parse_quantity(text)


@pytest.mark.parametrize("text,value,unit", [("x = 24", 24.0, ""), ("x=24", 24.0, ""), ("v = 3.0 m s^-1", 3.0, "m s^-1"),
                                             ("v_0 = -2 m", -2.0, "m"), ("E = 2.5×10³ J", 2500.0, "J")])
def test_a_variable_label_before_the_value_is_read_past(text, value, unit):
    got, got_unit, _ = grade.parse_quantity(text)
    assert got == pytest.approx(value) and got_unit == unit


def test_a_labelled_value_is_marked_not_refused():
    item = {"kind": "numeric", "stem": "Find the speed.", "answer": {"value": 3.0, "unit": "m s^-1"}}
    assert grade.value_problem(item, "v = 3.0 m s^-1") is None
    assert grade.grade_item(item, {"kind": "value", "value": "v = 3.0 m s^-1"})["correct"]
    plain = {"kind": "numeric", "stem": "Solve for x.", "answer": {"value": 24.0}}
    assert grade.value_problem(plain, "x = 24") is None and grade.grade_item(plain, {"kind": "value", "value": "x=24"})["correct"]
    for text in ("5 = 5", "x = y = 24", "x = "):
        assert grade.value_problem(plain, text) == "unreadable", text


SUVAT = {"kind": "expression", "answer": {"expr": "u**2 + 2*a*s"}, "marks": 3}  # 9702-2.1-i24: "write v^2 in terms of"


@pytest.mark.parametrize("typed", ["v^2 = u^2+2as", "v² = u² + 2as", "v^2=2as+u^2", "u^2 + 2as"])
def test_an_answer_written_as_an_equation_for_the_subject_is_marked(typed):
    assert grade.expression_readable(typed)
    assert grade.grade_item(SUVAT, {"kind": "value", "value": typed})["correct"]


@pytest.mark.parametrize("typed", ["v^2 = u^2 - 2as", "v^2 = u + 2as", "a = u^2 + 2as", "v^2 + 1 = u^2 + 2as"])
def test_a_wrong_equation_is_still_not_right(typed):
    assert not grade.grade_item(SUVAT, {"kind": "value", "value": typed})["correct"]


def test_an_equation_key_is_compared_side_by_side():
    assert grade.expressions_equal("y = 2x + 1", "y = 1 + 2*x")
    assert grade.expressions_equal("2x + 1", "y = 1 + 2*x")
    assert not grade.expressions_equal("z = 2x + 1", "y = 1 + 2*x")


@pytest.mark.parametrize("given,expected", [("sin^2(x)", "sin(x)^2"), ("sin²x", "sin(x)^2"), ("sin^2 x + cos^2 x", "1"),
                                            ("sinx", "sin(x)"), ("lnx", "log(x)"), ("2cosx", "2*cos(x)"),
                                            ("tantheta", "tan(theta)"), ("sinh x", "sinh(x)")])
def test_function_powers_and_unspaced_arguments_read_as_written(given, expected):
    assert grade.expression_readable(given) and grade.expressions_equal(given, expected)


def test_unit_spellings_of_the_right_unit():
    deg = {"kind": "numeric", "stem": "Find the angle.", "answer": {"value": 30.0, "unit": "°"}}
    for typed in ("30 °", "30°", "30 degrees", "30 deg", "30 degree"):
        assert grade.grade_item(deg, {"kind": "value", "value": typed})["correct"], typed
    for unit in ("mol dm^-3", "mol/dm3", "mol dm-3"):
        conc = {"kind": "numeric", "stem": "Find the concentration.", "answer": {"value": 0.5, "unit": unit}}
        assert grade.grade_item(conc, {"kind": "value", "value": "0.5 M"})["correct"], unit
    mass = {"kind": "numeric", "stem": "Find the mass.", "answer": {"value": 0.5, "unit": "kg"}}
    assert not grade.grade_item(mass, {"kind": "value", "value": "0.5 M"})["correct"]  # M alone is no unit of mass
    gdm = {"kind": "numeric", "stem": "Find the mass concentration.", "answer": {"value": 12.0, "unit": "g dm^-3"}}
    assert grade.grade_item(gdm, {"kind": "value", "value": "12 g dm^{-3}"})["correct"]


def test_a_capital_x_is_a_times_sign_in_standard_form():
    item = {"kind": "numeric", "answer": {"value": 1500, "unit": "J"}, "marks": 1}
    g = grade.grade_item(item, {"kind": "value", "value": "1.5 X 10^3 J", "conf": 3})
    assert g["correct"]


@pytest.mark.parametrize("written", ["25 percent", "25 per cent", "25 %"])
def test_percent_written_out_is_the_percent_unit(written):
    item = {"kind": "numeric", "answer": {"value": 25, "unit": "%"}, "marks": 1}
    g = grade.grade_item(item, {"kind": "value", "value": written, "conf": 3})
    assert g["correct"] and not g.get("error_type")
