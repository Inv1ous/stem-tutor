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
    ("abs(-x) + 10^3", "x + 1000"),
    ("log(x, 10)", "log(x)/log(10)"),
])
def test_expression_equivalent_forms_still_match(given, expected):
    item = {"kind": "expression", "answer": {"expr": expected}, "marks": 1}
    assert grade.grade_item(item, {"kind": "value", "value": given, "conf": 3})["correct"]
