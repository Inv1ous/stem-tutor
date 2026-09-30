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
