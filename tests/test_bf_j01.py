from __future__ import annotations

import json
from pathlib import Path

import pytest

from tutorlib import grade


def _published_item(spec: str, chapter: str, ident: str) -> dict:
    path = Path(__file__).resolve().parents[1] / "build/out/packs" / spec / f"{chapter}.json"
    return next(item for item in json.loads(path.read_text())["items"] if item["id"] == ident)


@pytest.mark.parametrize("spec,chapter,ident,typed", [
    ("S1", "S1-6", "S1-6-r02", "49.8694%"),
    ("9701", "9701-2.1", "9701-2.1-r01", "20.3%"),
])
def test_a_percentage_in_the_given_data_does_not_make_the_answer_a_percentage(spec, chapter, ident, typed):
    """B-042 (bug watch): supporting percentages do not supply the answer's unit."""
    item = _published_item(spec, chapter, ident)
    result = grade.grade_item(item, {"kind": "value", "value": typed})
    assert not result["correct"] and result["score"] == 0
    assert grade.value_problem(item, typed) == "unit"
    assert grade.grade_item(item, {"kind": "value", "value": typed[:-1]})["score"] == 1.0


@pytest.mark.parametrize("stem", [
    "Find c using the standard Normal percentage point.",
    "Calculate the relative atomic mass using the percentage abundances.",
    "A sample contains 25% of isotope A. Find its relative atomic mass.",
    "The abundance is given as a percentage. Calculate the relative atomic mass.",
    "The abundances in percent are 25 and 75. Find the relative atomic mass.",
    "The yield is 25% by mass. Calculate the mass of the product.",
])
def test_asking_for_a_value_using_percentages_does_not_allow_a_percent_sign(stem):
    """B-042 (bug watch): the requested quantity, not a later mention, sets the unit."""
    item = {"kind": "numeric", "stem": stem, "answer": {"value": 25, "unit": ""}}
    assert grade.value_problem(item, "25%") == "unit"
    assert grade.grade_item(item, {"kind": "value", "value": "25%"})["score"] == 0


@pytest.mark.parametrize("stem", [
    "Calculate the percentage of the mass in the nucleus.",
    "Find the percentage of its volume above the surface.",
    "What percentage of the sample remains?",
    "Calculate the yield. Give your answer as a percentage.",
    "Express the result in percent.",
    "Calculate the % yield of the reaction.",
    "What % of the sample remains?",
    "Determine the % by mass of carbon in the compound.",
    "Find the composition. Give your answer as a %.",
])
def test_an_answer_requested_as_a_percentage_still_accepts_the_percent_sign(stem):
    """B-042 (bug watch): genuine percentage answers keep their optional sign."""
    item = {"kind": "numeric", "stem": stem, "answer": {"value": 25, "unit": ""}}
    for typed in ("25", "25%"):
        assert grade.value_problem(item, typed) is None
        assert grade.grade_item(item, {"kind": "value", "value": typed})["score"] == 1.0


@pytest.mark.parametrize("typed", ["3/2", "3.00/2.00", "(3/2)"])
def test_a_fraction_does_not_satisfy_an_explicit_significant_figure_requirement(typed):
    """B-057 (bug watch): the aluminium mole ratio must be expressed to three figures."""
    item = _published_item("9701", "9701-2.4", "9701-2.4-r02")
    result = grade.grade_item(item, {"kind": "value", "value": typed})
    assert result["correct"] and result["score"] == 0.5 and result["error"] == "NOTATION"
    assert grade.grade_item(item, {"kind": "value", "value": "1.5"})["score"] == 0.5
    assert grade.grade_item(item, {"kind": "value", "value": "1.50"})["score"] == 1.0


@pytest.mark.parametrize("stem,answer", [
    ("Find the ratio to 3 significant figures.", {"sf_ok": [2, 3]}),
    ("Find the ratio.", {"sf": 3}),
])
def test_a_fraction_respects_figures_fixed_by_the_question_or_answer_key(stem, answer):
    """B-057 (bug watch): both existing ways of fixing precision also apply to fractions."""
    item = {"kind": "numeric", "stem": stem, "answer": {"value": 1.5, "unit": "", **answer}}
    result = grade.grade_item(item, {"kind": "value", "value": "3/2"})
    assert result["correct"] and result["score"] == 0.5 and result["error"] == "NOTATION"


@pytest.mark.parametrize("answer", [{}, {"exact": True}, {"sf_ok": [2, 3]}])
def test_an_exact_fraction_still_gets_full_credit_when_figures_are_not_fixed(answer):
    """B-057 (bug watch): an exact ratio need not be padded with decimal zeros."""
    item = {"kind": "numeric", "stem": "Find the ratio.",
            "answer": {"value": 1.5, "unit": "", **answer}}
    assert grade.grade_item(item, {"kind": "value", "value": "3/2"})["score"] == 1.0
