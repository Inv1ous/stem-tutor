"""Bug-watch P0 findings on marking and on the published packs' marking settings, fixed together."""
import json
import random
import sys
from pathlib import Path

import pytest

from tutorlib import grade, packs

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "build"))
import content_checks  # noqa: E402


def published(spec, chapter, item_id, seed=0):
    item = next(i for i in json.loads((REPO / f"build/out/packs/{spec}/{chapter}.json").read_text())["items"]
                if i["id"] == item_id)
    return packs.instantiate(item, random.Random(seed))


def score(item, typed):
    return grade.grade_item(item, {"kind": "value", "value": typed})["score"]


@pytest.mark.parametrize("spec,chapter,item_id,right,wrong", [
    ("9701", "9701-2.1", "9701-2.1-i12", ["32.0", "32"], ["31.7", "32.3"]),  # Mr(O2) = 2 × 16.0
    ("9701", "9701-2.1", "9701-2.1-i13", ["100.1", "100"], ["101", "99.1"]),  # Mr(CaCO3) = 100.1
    ("9701", "9701-2.4", "9701-2.4-r02", ["1.50"], ["1.51"]),  # asks 3 s.f.
    ("9702", "9702-5.2", "9702-5.2-r01", ["-4.46 J"], ["-4.45 J"]),  # asks 3 s.f.
])
def test_a_wrong_value_within_one_percent_is_wrong(spec, chapter, item_id, right, wrong):
    """B-140: a blanket 1% window gave full marks to wrong arithmetic (32.3 for 2 × 16.0 = 32.0)."""
    item = published(spec, chapter, item_id)
    assert all(score(item, v) == 1.0 for v in right), right
    assert all(score(item, v) == 0 for v in wrong), wrong


def test_too_few_figures_is_still_the_right_value_marked_down_and_drift_is_forgiven():
    item = {"kind": "numeric", "stem": "Calculate the acceleration.", "kcs": ["9702-2.1.1"],
            "answer": {"value": 3.02, "unit": "m s-2", "sf_ok": [2, 3]}}
    assert score(item, "3 m s-2") == 0.5  # one figure: half, as before
    assert score(item, "3.0 m s-2") == 1.0 and score(item, "3.021 m s-2") == 1.0  # 0.03% drift from rounding midway


@pytest.mark.parametrize("typed,right", [("39.8 m", True), ("40 m", True), ("39.8 m of height", True),
                                         ("39.8 m + 4", False), ("39.8 m = 9", False), ("39.8 m - 1", False),
                                         ("39.8 m * 3", False), ("39.8 m / 2", False), ("39.8 m x 2", False), ("39.8 m X 2", False), ("39.8 m x2", False)])  # the letter x too
def test_a_sum_after_the_unit_is_not_a_comment(typed, right):
    """B-100: "39.8 m + 4" was read as 39.8 m with a comment and earned full marks."""
    assert (score(published("9702", "9702-5.1", "9702-5.1-r03"), typed) == 1.0) is right


@pytest.mark.parametrize("item_id,right", [("S1-3-i02", ["0.33", "0.333", "1/3"]), ("S1-3-i21", ["0.29", "0.286", "2/7"]),
                                            ("S1-3-i22", ["0.57", "0.571", "4/7"])])
def test_rounded_probabilities_count_where_the_question_asks_for_no_exact_form(item_id, right):
    """B-141: an exact-only key refused the 2 and 3 s.f. roundings it listed."""
    item = published("S1", "S1-3", item_id)
    assert all(score(item, v) == 1.0 for v in right), [(v, score(item, v)) for v in right]


def test_a_question_asking_for_three_figures_accepts_three_figures_only():
    """B-099: "correct to 3 s.f." also accepted (and showed) 4 figures."""
    item = published("P1", "P1-1", "P1-1-i10")
    from tutorlib.session import _display_answer
    v = item["answer"]["value"]
    assert score(item, f"{v:#.3g}") == 1.0 and score(item, f"{v:#.4g}") == 0.5
    assert _display_answer(item) == f"{v:.3g}"


def test_no_published_question_asks_for_working_its_marking_cannot_see():
    """B-093: a numeric item asked for the extension and its uncertainty in the working, then marked the final value."""
    assert "In your working" not in published("9702", "9702-1.3", "9702-1.3-r01")["stem"]


def test_no_published_pack_has_marking_settings_that_contradict_its_question():
    bad = []
    for f in (REPO / "build/out/packs").glob("*/*.json"):
        pack = json.loads(f.read_text())
        if isinstance(pack, dict):
            bad += content_checks.precision_problems(pack)
    assert not bad, bad[:5]
    assert content_checks.precision_problems({"items": [{"id": "x", "kind": "numeric", "stem": "Give it to 3 s.f.",
                                                         "answer": {"value": 1, "sf_ok": [3, 4]}}]})
