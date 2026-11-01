from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO / 'src'), str(REPO / 'build')]
from tutor_workers import reliability


def test_baseline_debris_blocks_without_mutation(tmp_path):
    state = {'pass': 1}
    p = tmp_path / 'input.json'
    p.write_text('{}')
    baseline = {'pack': {'items': [{'stem': 'lost � character'}]}}
    assert 'PDF' in reliability.launch_problem(state, 'scout', [p], baseline=baseline)
    assert state == {'pass': 1}


def test_failures_cap_even_when_inputs_change_and_reset_is_explicit(tmp_path):
    p = tmp_path / 'input.json'
    p.write_text('{}')
    state = {'pass': 1, 'jobs': {'fixer': {}}}
    for code in (124, 0):
        assert reliability.launch_problem(state, 'fixer', [p]) is None
        reliability.record_result(state, 'fixer', ok=False, exit_code=code, issues=['bad evidence'])
        p.write_text(p.read_text() + ' ')
    assert 'paused' in reliability.launch_problem(state, 'fixer', [p])
    reliability.clear_failures(state, 'reviewed manually')
    assert reliability.launch_problem(state, 'fixer', [p]) is None
    assert state['reliability_history'][-1]['reason'] == 'reviewed manually'


def test_scope_success_and_unreadable_input(tmp_path):
    p = tmp_path / 'missing.json'
    state = {'pass': 1, 'jobs': {}}
    assert reliability.launch_problem(state, 'scout', [p])

    p.write_text('{}')
    reliability.record_result(state, 'scout', ok=False, exit_code=1, issues=[])
    reliability.record_result(state, 'scout', ok=False, exit_code=1, issues=[])
    assert reliability.launch_problem(state, 'scout', [p])
    assert reliability.launch_problem(state, 'fixer', [p]) is None
    state['pass'] = 2
    assert reliability.launch_problem(state, 'scout', [p]) is None
    reliability.record_result(state, 'scout', ok=False, exit_code=1, issues=[])
    reliability.record_result(state, 'scout', ok=True, exit_code=0, issues=[])
    assert len(state['reliability_failures']['2']['scout']) == 1
    reliability.record_result(state, 'scout#1', ok=False, exit_code=1, issues=[])
    assert reliability.launch_problem(state, 'scout', [p])

def test_empty_or_partial_solver_answers_do_not_complete(tmp_path):
    questions = tmp_path / 'sub.questions.json'
    questions.write_text('[{"id":"q1"},{"id":"q2"}]')
    answers = tmp_path / 'sub.answers.json'
    for text in ('{}', '{"q1":"A"}', '{"q1":"A","q2":""}'):
        answers.write_text(text)
        assert reliability.output_problem(answers, 'solver')
    answers.write_text('{"q1":"A","q2":"B"}')
    assert reliability.output_problem(answers, 'solver') is None


def test_unregistered_diagram_blocks_paid_authoring_retry_with_controller_handoff(tmp_path):
    import json
    pack = tmp_path / 'pack.json'
    pack.write_text(json.dumps({'diagrams': [{'file': 'Assets/M1/new.svg'}]}))
    class Catalog:
        def resolve(self, reference):
            raise ValueError('asset not registered')
    for role in ('drafter', 'refiner', 'fixer'):
        state = {'pass': 1, 'jobs': {role: {'ok': False}}}
        why = reliability.launch_problem(state, role, [pack], diagram_catalog=Catalog())
        assert 'controller' in why and 'Assets/M1/new.svg' in why
        assert state == {'pass': 1, 'jobs': {role: {'ok': False}}}


def test_registered_diagram_retry_is_read_only_and_new_authoring_remains_possible(tmp_path):
    import json
    pack = tmp_path / 'pack.json'
    pack.write_text(json.dumps({'diagrams': [{'file': 'Library/Courses/M1/Diagrams/a.svg'}]}))
    seen = []
    class Catalog:
        def resolve(self, reference):
            seen.append(reference)
            return tmp_path / 'registered.svg'
    assert reliability.launch_problem({'jobs': {'fixer': {'ok': False}}}, 'fixer', [pack], diagram_catalog=Catalog()) is None
    assert seen == ['Library/Courses/M1/Diagrams/a.svg']
    assert reliability.launch_problem({'jobs': {}}, 'refiner', [pack], diagram_catalog=Catalog()) is None


def test_card_only_unregistered_diagram_blocks_authoring_retry(tmp_path):
    import json
    pack = tmp_path / 'pack.json'
    reference = 'Assets/M1/lesson-only.svg'
    pack.write_text(json.dumps({'teach': {'KC': {'diagrams': [reference],
                                                'forms': [{'diagram': reference}]}}}))
    class Catalog:
        def resolve(self, path):
            raise ValueError('unregistered')
    why = reliability.launch_problem({'jobs': {'refiner': {'ok': False}}}, 'refiner', [pack], diagram_catalog=Catalog())
    assert reference in why and 'controller' in why


def test_registered_card_and_bound_form_diagrams_are_preserved_and_checked_once(tmp_path):
    import json
    pack = tmp_path / 'pack.json'
    reference = 'Library/Courses/M1/Diagrams/reviewed.svg'
    original = json.dumps({'diagrams': [{'file': reference}],
                           'teach': {'KC': {'diagrams': [reference],
                                            'forms': [{'diagram': reference}]}}})
    pack.write_text(original)
    seen = []
    class Catalog:
        def resolve(self, path):
            seen.append(path)
            return tmp_path / 'asset.svg'
    assert reliability.launch_problem({'jobs': {'fixer': {'ok': False}}}, 'fixer', [pack], diagram_catalog=Catalog()) is None
    assert seen == [reference]
    assert pack.read_text() == original


def test_malformed_candidate_shape_pauses_retry_instead_of_crashing(tmp_path):
    import json
    from copy import deepcopy
    for invalid in ([{'unrelated': True}], {'teach': [{'diagrams': ['Assets/new.svg']}]}, {'teach': 'invalid'}):
        candidate = tmp_path / 'pack.json'
        candidate.write_text(json.dumps(invalid))
        state = {'pass': 1, 'jobs': {'fixer': {'ok': False}}}
        before = deepcopy(state)
        class Catalog:
            def resolve(self, reference):
                raise AssertionError('malformed candidate must be rejected before asset lookup')
        why = reliability.launch_problem(state, 'fixer', [candidate], diagram_catalog=Catalog())
        assert why and 'preflight' in why
        assert state == before
