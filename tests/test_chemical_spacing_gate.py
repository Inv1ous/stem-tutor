"""Reject source-extraction gaps without guessing how to rewrite chemistry."""
import copy
import json
from pathlib import Path

import pytest

from build import content_checks
from test_foundry import fdy
from test_refine import rf


@pytest.mark.parametrize('text', [
    'Cl ₂', 'MgCl ₂(aq)', 'NaCl O₃', 'Cl O⁻', 'ClO₃\n⁻', 'Al ₂O₃',
    'Br ⁻', 'MnO₄\n⁻', 'SO₃\n²⁻', 'NH₄ ⁺', 'Al ³⁺',
])
def test_chemical_formula_gaps_require_source_review(text):
    pack = {'spec': '9701', 'items': [{'id': 'q', 'stem': text}]}
    before = copy.deepcopy(pack)
    assert content_checks.chemical_spacing_problems(pack)
    assert pack == before


@pytest.mark.parametrize('text', [
    'Cl₂ and NaClO₃ and ClO⁻', 'Al₂O₃, SO₃²⁻, MnO₄⁻ and NH₄⁺',
    '$P ₁ + V ₂$', r'\(V ₁ + P ₂\)', 'x₁ ²', '1 ₂ ¹',
    '20 cm³ and 2 mol dm⁻³', 'Compare NaCl and O₂.', 'Question 1\n2\n3',
])
def test_math_units_lists_and_joined_species_are_not_chemical_spacing_faults(text):
    assert not content_checks.chemical_spacing_problems({'spec': '9701', 'items': [{'stem': text}]})


def test_other_courses_keep_their_own_notation():
    assert not content_checks.chemical_spacing_problems({'spec': '9702', 'items': [{'stem': 'V ₁'}]})


@pytest.mark.parametrize('workflow_fixture', ['fdy', 'rf'])
def test_workflow_gate_rejects_split_species(request, workflow_fixture, tmp_path):
    workflow = request.getfixturevalue(workflow_fixture)
    original = json.loads((tmp_path / 'build/out/packs/9702/9702-2.1.json').read_text())
    pack = json.loads(json.dumps(original).replace('9702', '9701'))
    graph = json.loads((tmp_path / 'build/out/specs/9702/graph.json').read_text().replace('9702', '9701'))
    spec = workflow.SPECS / '9701'
    spec.mkdir()
    (spec / 'graph.json').write_text(json.dumps(graph))
    candidate = tmp_path / 'chemistry.json'
    note = tmp_path / 'build/out/notes' / original['note']

    def gate(stem):
        pack['items'][0]['stem'] = stem
        candidate.write_text(json.dumps(pack))
        if workflow_fixture == 'fdy':
            return workflow.gates('9701-2.1', candidate_pack=candidate, candidate_note=note)
        result = {'ok': True, 'first': []}
        workflow._inherited(result, '9701-2.1', {'note': note.read_text()}, pack, note)
        return result

    clean = gate('Chlorine is Cl₂.')
    broken = gate('Chlorine is Cl ₂.')
    assert broken['figures'] == clean['figures'] + 1
    assert any('chemical formula spacing' in finding for finding in broken['first'])
