from pathlib import Path

import pytest
from build.teach_cards import check_card
from test_guided_teach_cards import _foundry, base_card


def card():
    return {**base_card(), 'plain_words': 'Idea',
            'terms': [{'term': 'Proof', 'meaning': 'Argument', 'notation': 'none', 'spoken': 'proof', 'source': 'spec'}],
            'forms': [{'name': 'Direct', 'wordings': ['Prove'], 'example': 'Example', 'check': 'Check', 'answer': 'Answer', 'source': 'spec', 'rubric': [{'point': 'Proof', 'keywords': [['proof']]}]}],
            'misconceptions': [{'id': 'm', 'idea': 'Mistake', 'temptation': 'Reason', 'fix': 'Correction'}],
            'diagrams': [], 'diagram_reason': 'No suitable figure.'}


def gate(inventory, teach):
    pack = {'subtopic': 's', 'guided_forms': inventory, 'teach': teach,
            'misconceptions': [{'id': 'm', 'kc': 's.1'}]}
    return _foundry().guided_problems(pack, {'kcs': [{'id': 's.1', 'subtopic': 's'}]}, '', Path('/tmp'))


@pytest.mark.parametrize('inventory', [{'s.1': []}, {'s.1': ['']}, {'s.1': ['Direct', 'Direct']}, {'s.1': ['Direct', 1]}, {'s.1': ['Direct', 'Missing']}])
def test_invalid_or_uncovered_inventory_is_rejected(inventory):
    assert gate(inventory, {'s.1': card()})


@pytest.mark.parametrize('teach', [[], 'bad', {'s.1': []}])
def test_malformed_teach_is_rejected(teach):
    assert gate({'s.1': ['Direct']}, teach)


def test_duplicate_form_names_and_identical_check_rejected():
    c = card()
    c['forms'].append(dict(c['forms'][0]))
    c['forms'][0]['check'] = c['forms'][0]['example']
    issues = check_card('s.1', c, guided=True)
    assert any('unique' in issue for issue in issues)
    assert any('distinct' in issue for issue in issues)


@pytest.mark.parametrize('discover', [['bad'], {'options': []}, {'options': {'A': 'x', 1: 'y'}}])
def test_malformed_discover_is_rejected(discover):
    assert check_card('s.1', {**base_card(), 'discover': discover}, guided=True)
