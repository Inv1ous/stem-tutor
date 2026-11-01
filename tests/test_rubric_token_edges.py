"""Rubric keyword matching at token edges (2026-10-30): a keyword does not count inside a longer number, word or unit.

Negation, sign meaning and semantics are NOT handled here; the cases that show that are marked as unchanged, not solved.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "plugin/stem-tutor/skills/tutor/scripts"))
from tutorlib.grade import _contains_keyword, _grade_rubric  # noqa: E402


def _score(keywords, answer):
    """keywords: one group (a list of alternatives), or a list of groups for a point with several groups."""
    groups = keywords if keywords and isinstance(keywords[0], list) else [keywords]
    item = {"rubric": [{"point": "p", "keywords": groups}]}
    return _grade_rubric(item, {"kind": "text", "value": answer})["score"]


# --- numbers: a keyword is not matched inside a longer number ---------------------------------------------------------

@pytest.mark.parametrize("keyword, answer", [
    ("4.3", "the reading is 4.3 mm"),            # correct: the value stands alone
    ("4.3", "the reading is 4.3."),              # correct: sentence full stop after the value
    ("4.3", "4.3 mm"),                           # correct: value at the very start
    ("0.5", "a = 0.5 and b = 0.5"),              # correct: repeated value
    ("8.3", "the percentage is 8.3%"),            # correct: followed by a percent sign
    ("m^-1", "units are m^-1"),                  # correct: caret keyword at the end
])
def test_standalone_number_matches(keyword, answer):
    assert _contains_keyword(keyword, answer.lower())


@pytest.mark.parametrize("keyword, answer", [
    ("4.3", "14.3 mm"),                          # wrong: digit before
    ("4.3", "4.35 mm"),                          # wrong: digit after
    ("4.3", "24.3 mm"),                          # wrong: digit before
    ("8.3", "F gives 18.3%"),                    # wrong: digit before (the exact trap from review)
    ("0.5", "10.5 N"),                           # wrong: digit before
    ("5 n at 53", "15 n at 53 degrees"),         # wrong: digit before the value (review trap)
    ("10^30", "10^300"),                         # wrong: exponent continues
    ("m^-1", "m^-10"),                           # wrong: exponent continues
    ("2", "2.8"),                                # wrong: decimal continues into a digit
    ("1", "0.1"),                                # wrong: preceded by a decimal point and a digit
])
def test_number_inside_a_longer_number_does_not_match(keyword, answer):
    assert not _contains_keyword(keyword, answer.lower())


# --- words and units: a keyword is not matched inside a longer word or unit ------------------------------------------

@pytest.mark.parametrize("keyword, answer", [
    ("sum", "the sum of the moments"),           # correct
    ("electron", "a sea of electrons"),          # correct: plural inflection of a word keyword
    ("attract", "they attracted each other"),    # correct: inflection
    ("m/s", "the speed is 5 m/s"),               # correct: unit at the end of a clause
    ("kg", "mass in kg."),                       # correct
])
def test_word_or_unit_matches_standalone(keyword, answer):
    assert _contains_keyword(keyword, answer.lower())


@pytest.mark.parametrize("keyword, answer", [
    ("sum", "we assume the forces balance"),     # wrong: inside 'assume'
    ("m/s", "the flow is 5 km/s"),               # wrong: 'm/s' inside 'km/s'
    ("kg", "the skg unit"),                      # wrong: inside a longer token
    ("5 m", "15 m/s"),                           # wrong: digit before (review trap)
    ("5 m", "5 mm"),                             # wrong: letter after
])
def test_word_or_unit_inside_a_longer_token_does_not_match(keyword, answer):
    assert not _contains_keyword(keyword, answer.lower())


# --- whole-point scoring keeps the old behaviour for correct answers ------------------------------------------------

def test_point_with_two_groups_still_needs_every_group():
    assert _score([["cancel", "zero"], ["resultant"]], "the forces cancel, so the resultant is zero") == 1.0
    assert _score([["cancel", "zero"], ["resultant"]], "the forces cancel") == 0.0


def test_leading_space_keyword_still_matches_an_answer_that_opens_with_it():
    assert _score([" 750 mm"], "750 mm is the same length as 0.75 m") == 1.0


def test_keyword_with_symbol_edges_keeps_old_behaviour():
    assert _score(["= 0.5"], "so p = 0.5") == 1.0
    assert _score(["(x-3)"], "(x-3)(x+2) = 0") == 1.0


# --- unchanged, not solved: negation and sign are still substring-only ----------------------------------------------

def test_negation_is_still_not_detected_by_the_matcher():
    # documents the limit: a negated sentence that contains the keyword still matches (the judge decides)
    assert _score(["cancel"], "the forces do not cancel") == 1.0


def test_sign_is_still_not_detected_by_the_matcher():
    assert _score(["0.5"], "p = -0.5") == 1.0


def test_word_stems_still_match_inflected_forms():
    # a word keyword written as a stem keeps matching longer forms ("sin" in "sine", "cos" in "cosine")
    assert _contains_keyword("sin", " tangent is sine divided by cosine")
    assert _contains_keyword("cos", " tangent is sine divided by cosine")


def test_trailing_zero_decimal_keeps_the_same_value():
    assert _contains_keyword("86", " m_r=86.0")
    assert _contains_keyword("-3003", " =-3003.0 kj mol")
    assert not _contains_keyword("86", " m_r=86.5")


def test_decimal_keyword_matches_a_trailing_zero_form():
    assert _contains_keyword("1.5", " g = 1.50 n")
    assert not _contains_keyword("1.5", " g = 1.505 n")
    assert not _contains_keyword("9.8", " g = 9.81 m/s^2")
    assert _contains_keyword("9.8", " g = 9.80 m/s^2")


# --- rubric level: a trapped answer scores 0 for the point (not only at keyword level) --------------------------------

@pytest.mark.parametrize("keyword, answer", [
    ("4.3", "the reading is 14.3 mm"),
    ("8.3", "F gives 18.3%"),
    ("sum", "we assume the forces balance"),
    ("m/s", "the flow is 5 km/s"),
    ("5 m", "15 m/s"),
    ("10^30", "10^300"),
])
def test_trapped_answer_scores_zero_for_the_point(keyword, answer):
    assert _score([keyword], answer) == 0.0


def test_standalone_answer_scores_one_for_the_point():
    assert _score(["4.3"], "the reading is 4.3 mm") == 1.0


# --- the eight measured losses (2026-10-30): five spurious old credits, one formula fix, two intended blocks -----------

@pytest.mark.parametrize("keyword, answer", [
    ("pi", "keeping the included left endpoint"),     # spurious: 'pi' inside 'keeping'
    ("oh", "the alcohol group"),                      # spurious: 'oh' inside 'alcohol'
    ("ea", "the area under the curve"),               # spurious: 'ea' inside 'area'
    ("ea", "heating alters the rate"),                # spurious: 'ea' inside 'heating'
])
def test_old_substring_credit_inside_another_word_is_not_given(keyword, answer):
    assert not _contains_keyword(keyword, answer.lower())


def test_formula_keyword_still_matches_before_a_hydrate_dot():
    # a keyword with letters is a formula or a word, so a dot and digits after it are hydrate notation, not a decimal
    assert _contains_keyword("MgSO4", " $\\ce{mgso4.7h2o}$")


def test_pure_number_is_still_not_matched_inside_a_decimal():
    # intended: '5' is not the value 5.3, and '109' is not the value 109.5 (the trade-off is stated, not hidden)
    assert not _contains_keyword("5", " about 5.3, below 7")
    assert not _contains_keyword("109", " about 109.5 degrees")
