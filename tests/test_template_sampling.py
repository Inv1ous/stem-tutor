"""Stepped template parameters stay on their inclusive declared grids."""
import copy
import random
import sys
from pathlib import Path

import pytest

from fixtures import GRAPH, PACK
from tutorlib import packs

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "build"))
from validate_pack import validate


def _item(spec):
    return {"id": "sampling-grid", "kind": "numeric", "kcs": ["9702-2.1.4"], "difficulty": 3, "marks": 1,
            "source": {"type": "generated"}, "stem": "Use the length [[x]] m.", "answer": {"unit": "m", "sf": 3},
            "hints": ["Read the length.", "Use the supplied quantity.", "Check the units."],
            "explanation": "The sampled length is [[x]] m.",
            "template": {"params": {"x": spec}, "answer": "x"}}


def test_nondivisible_step_never_samples_above_declared_maximum():
    item = _item({"min": 1, "max": 9, "step": 3})
    pack = copy.deepcopy(PACK)
    pack["items"] = [item]
    assert not validate(pack, GRAPH, min_variants=0)
    original = copy.deepcopy(item)
    samples = [packs.instantiate(item, random.Random(seed))["params"]["x"] for seed in range(20)]
    assert set(samples) == {1, 4, 7}
    assert all(1 <= value <= 9 for value in samples)
    assert item == original


@pytest.mark.parametrize("spec,expected,next_random", [
    ({"min": 0, "max": 0.3, "step": 0.1}, [0.1, 0.2, 0.2, 0.0, 0.0, 0.2, 0.2, 0.1, 0.1, 0.0], 0.20543327557559332),
    ({"min": -3, "max": 3, "step": 1.5}, [-1.5, 0.0, 0.0, -3.0, -3.0, 3.0, 0.0, 3.0, 0.0, 3.0], 0.18444279707476485),
    ({"min": 1, "max": 8, "step": 3}, [1, 4, 4, 1, 1, 7, 4, 7, 4, 7], 0.18444279707476485),
    ({"min": 1, "max": 1, "step": 3}, [1] * 10, 0.20543327557559332),
])
def test_already_valid_grids_keep_seeded_outputs_and_random_state(spec, expected, next_random):
    rng = random.Random(314159)
    item = _item(spec)
    assert [packs.instantiate(item, rng)["params"]["x"] for _ in range(10)] == expected
    assert rng.random() == next_random


def test_inclusive_decimal_endpoint_remains_reachable():
    item = _item({"min": 0.1, "max": 0.3, "step": 0.1})
    assert {packs.instantiate(item, random.Random(seed))["params"]["x"] for seed in range(20)} == {0.1, 0.2, 0.3}
