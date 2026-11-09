"""Opt-in official unallocated rubrics never pretend to be mark points."""
import copy
import math

import pytest

from tutorlib import grade, topicals


def whole(maximum=2, media=None):
    return {'kind': 'structured', 'marks': maximum, 'answer': 'Official answer',
            'scheme': [{'point': 'Use the official unallocated rubric.',
                        'whole_rubric': {'version': 1, 'max_marks': maximum, 'media': media or []}}]}


@pytest.mark.parametrize('maximum', [1, 2, 3])
def test_whole_manual_award(maximum):
    helper = getattr(grade, 'grade_human_whole', None)
    assert callable(helper), 'missing explicit human whole-rubric scoring'
    for earned in range(maximum + 1):
        result = helper(whole(maximum), earned)
        assert result['score'] == round(earned / maximum, 3)
        assert result['correct'] is (earned == maximum)
        assert result['self_marked'] is True
        assert result['needs_judgement'] is False


@pytest.mark.parametrize('award', [True, False, '1', 1.0, math.nan, math.inf, None, [], -1, 3])
def test_whole_invalid_award(award):
    helper = getattr(grade, 'grade_human_whole', None)
    assert callable(helper), 'missing strict whole-rubric scorer'
    with pytest.raises(ValueError):
        helper(whole(), award)


@pytest.mark.parametrize('mutate', [
    lambda i: i['scheme'][0].update(whole_rubric=None),
    lambda i: i['scheme'][0].update(whole_rubric={}),
    lambda i: i['scheme'][0]['whole_rubric'].update(version=True),
    lambda i: i['scheme'][0]['whole_rubric'].update(version=2),
    lambda i: i['scheme'][0]['whole_rubric'].update(max_marks=1),
    lambda i: i['scheme'][0].update(point=' '),
    lambda i: i['scheme'].append({'point': 'invented'}),
    lambda i: i['scheme'][0].update(mark='B2'),
    lambda i: i['scheme'][0].update(check={}),
    lambda i: i['scheme'][0]['whole_rubric'].update(extra=1),
    lambda i: i['scheme'][0]['whole_rubric'].update(media=['a', 'a']),
    lambda i: i['scheme'][0]['whole_rubric'].update(media='a'),
    lambda i: i.pop('marks'),
    lambda i: i.update(kind='short'),
])
def test_whole_rubric_invalid_discriminator_never_falls_back(mutate):
    item = whole(); mutate(item)
    with pytest.raises(ValueError):
        topicals.validate_structured_scheme(item)


def test_whole_grade_item_declines_pts_value_and_unknown_metadata():
    for response in ({'kind': 'points', 'value': [1]}, {'kind': 'value', 'value': '2'},
                     {'kind': 'human', 'value': 2, 'earned_marks': 2}):
        result = grade.grade_item(whole(), response)
        assert result['score'] == 0 and result['needs_judgement']
    assert grade.grade_item(whole(), {'kind': 'idk', 'value': None})['score'] == 0


def test_flat_legacy_validation_and_pts_are_identical():
    single = {'kind': 'structured', 'scheme': [{'point': 'legacy'}]}
    topicals.validate_structured_scheme(single)
    assert grade.grade_item(single, {'kind': 'points', 'value': [1]})['score'] == 1
    legacy = {'kind': 'structured', 'marks': 4, 'scheme': [{'point': 'x'} for _ in range(4)]}
    assert grade.grade_item(legacy, {'kind': 'points', 'value': [1, 2]})['score'] == .5
