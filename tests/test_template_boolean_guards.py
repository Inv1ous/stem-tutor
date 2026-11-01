"""Guarded arithmetic constraints evaluate only the necessary operands."""
import copy
import random

import pytest

from tutorlib import packs


@pytest.mark.parametrize('constraint,choices,expected', [
    ('x != 0 and 1 / x > 0', [0, 2], 2),
    ('x == 0 or 1 / x > 0', [0], 0),
])
def test_instantiation_short_circuits_guarded_constraints(constraint, choices, expected):
    item = {'id': 'guarded-template', 'kind': 'numeric', 'stem': 'Add one to [[x]].',
            'answer': {'unit': '', 'sf': 3},
            'template': {'params': {'x': {'choices': choices}},
                         'constraints': [constraint], 'answer': 'x + 1'}}
    original = copy.deepcopy(item)

    result = packs.instantiate(item, random.Random(1))

    assert result['params'] == {'x': expected}
    assert result['answer']['value'] == expected + 1
    assert result['stem'] == f'Add one to {expected}.'
    assert 'template' not in result
    assert item == original


def test_needed_boolean_operands_keep_existing_errors_and_sandbox():
    with pytest.raises(ZeroDivisionError):
        packs._eval('x == 0 and 1 / x > 0', {'x': 0})
    with pytest.raises(ZeroDivisionError):
        packs._eval('x != 0 or 1 / x > 0', {'x': 0})
    with pytest.raises(ValueError, match='disallowed expression'):
        packs._eval('1 and __import__("os")', {})
    assert packs._eval('x > 0 and x < 3', {'x': 2}) == 1.0
    assert packs._eval('x > 0 or x < -3', {'x': -1}) == 0.0
