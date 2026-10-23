"""Regression checks for the Almanac's merge of tutor progress."""
from __future__ import annotations

import shutil

import pytest

from test_almanac_link import merged

pytestmark = pytest.mark.skipif(not shutil.which("node"), reason="needs Node to run the page's script")


def test_a_learners_tick_stays_off_after_they_remove_it() -> None:
    """B-044 (bug watch): earning an already ticked objective must not undo a later untick."""
    update = {"stamp": "first", "done": {"5-phys1": 1}}
    state, _ = merged({"done": {"5-phys1": 1}}, update)
    assert state["done"] == {"5-phys1": 1}
    assert state["tutor"]["done"] == {}  # the original tick remains the learner's claim
    del state["done"]["5-phys1"]
    state, _ = merged(state, {**update, "stamp": "later"}, {"stamp": "absent"},
                      {**update, "stamp": "returned"})
    assert state["done"] == {}


@pytest.mark.parametrize("own", [0, 2])
def test_a_corrected_mistake_leaves_only_the_learners_count(own: int) -> None:
    """B-064 (bug watch): an omitted error family removes its previous tutor count."""
    state, _ = merged({"err": {"Wrong method": own, "Units": 4}},
                      {"stamp": "first", "err": {"Wrong method": 1, "Algebra slip": 2}})
    assert state["err"]["Wrong method"] == own + 1
    state, _ = merged(state, {"stamp": "corrected", "err": {"Algebra slip": 2}},
                      {"stamp": "later", "err": {"Algebra slip": 2}})
    assert state["err"]["Wrong method"] == own
    assert state["err"]["Units"] == 4
    assert state["err"]["Algebra slip"] == 2
