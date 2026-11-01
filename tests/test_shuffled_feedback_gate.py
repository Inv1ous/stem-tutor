"""Generated MCQ feedback cannot retain its authored option letter after shuffle."""
import copy

import pytest

from build import content_checks
from library_assets import read_json


@pytest.mark.parametrize('field', ['explanation', 'hints'])
@pytest.mark.parametrize('phrase', [
    'The tempting alternative in B is wrong: it increases steadily.',
    'The option in A is wrong: it increases steadily.',
    'The choice in C is wrong: it increases steadily.',
])
def test_shuffled_feedback_gate_rejects_explicit_alternative_in_letter(field, phrase):
    item = {'id': 'probe', 'kind': 'mcq', 'shuffle': True, 'source': {'type': 'generated'},
            field: [phrase] if field == 'hints' else phrase}
    problems = content_checks.letter_problems({'items': [item]})
    assert len(problems) == 1 and 'probe' in problems[0]


@pytest.mark.parametrize('text', [
    'The expression in B is wrong because its sign is reversed.',
    'The force at B is wrong because the arrow points downwards.',
    'The current in B is wrong because the wire is disconnected.',
    'The alternative in $B$ is wrong because the algebraic sign changed.',
    'Ball A falls freely while ball B moves horizontally.',
    'The force at A has no moment about A.',
    'Compare the coefficients of $A$ and $B$.',
    'The C–Br bond breaks heterolytically.',
])
def test_feedback_gate_preserves_diagram_algebra_and_chemical_labels(text):
    assert not content_checks.letter_problems({'items': [{
        'id': 'probe', 'kind': 'mcq', 'shuffle': True, 'source': {'type': 'generated'},
        'explanation': text,
    }]})


@pytest.mark.parametrize('source,shuffle', [('past', True), ('generated', False)])
def test_unshuffled_feedback_keeps_the_existing_letter_contract(source, shuffle):
    item = {'id': 'probe', 'kind': 'mcq', 'shuffle': shuffle, 'source': {'type': source},
            'explanation': 'The tempting alternative in B is wrong: it increases steadily.'}
    assert not content_checks.letter_problems({'items': [item]})


def test_real_immutable_v273_feedback_references_are_rejected():
    pack = read_json('Library/Releases/v273/specs/9701/packs/9701-9.1.json')
    problems = content_checks.letter_problems(pack)
    assert len(problems) == 7
    assert {problem.split()[0] for problem in problems} == {
        '9701-9.1-i01', '9701-9.1-i02', '9701-9.1-i03', '9701-9.1-i04',
        '9701-9.1-i05', '9701-9.1-i06', '9701-9.1-i07',
    }
    corrected = copy.deepcopy(pack)
    for item in corrected['items']:
        if item['id'] in {problem.split()[0] for problem in problems}:
            item['explanation'] = item['explanation'].replace('alternative in B is wrong:', 'alternative is wrong:')
    assert not content_checks.letter_problems(corrected)
