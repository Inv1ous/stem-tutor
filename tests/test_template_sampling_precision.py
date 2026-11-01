"""Stepped scientific-scale parameters keep their declared decimal resolution."""
import copy
import random

import pytest

from fixtures import GRAPH, PACK
from test_template_sampling import _item
from tutorlib import packs
from validate_pack import validate


@pytest.mark.parametrize("spec,expected", [
    ({"min": 1e-12, "max": 7e-12, "step": 3e-12}, {1e-12, 4e-12, 7e-12}),
    ({"min": -7e-12, "max": -1e-12, "step": 3e-12}, {-7e-12, -4e-12, -1e-12}),
    ({"min": 1.25e-12, "max": 7.25e-12, "step": 3e-12}, {1.25e-12, 4.25e-12, 7.25e-12}),
    ({"min": 1e-12, "max": 9e-12, "step": 3e-12}, {1e-12, 4e-12, 7e-12}),
    ({"min": -9e-12, "max": -1e-12, "step": 3e-12}, {-9e-12, -6e-12, -3e-12}),
    ({"min": -1.25e-12, "max": -1.25e-12, "step": 3e-12}, {-1.25e-12}),
    ({"min": 0, "max": 6e-12, "step": 3e-12}, {0, 3e-12, 6e-12}),
    ({"min": 1e-24, "max": 7e-24, "step": 3e-24}, {1e-24, 4e-24, 7e-24}),
])
def test_public_scientific_grid_keeps_representable_values_and_inclusive_bounds(spec, expected):
    item = _item(spec)
    pack = copy.deepcopy(PACK)
    pack["items"] = [item]
    assert not validate(pack, GRAPH, min_variants=0)
    original = copy.deepcopy(item)
    observed = set()
    for seed in range(20):
        inst = packs.instantiate(item, random.Random(seed))
        value = inst["params"]["x"]
        observed.add(value)
        assert spec["min"] <= value <= spec["max"]
        assert inst["answer"]["value"] == value
        assert "[[" not in inst["stem"] and "[[" not in inst["explanation"]
    assert observed == expected
    assert item == original
