"""Validation of richer cards without invalidating existing lessons."""
import pytest

from library_assets import read_json as library_json
from build.teach_cards import check_card, is_guided


def _foundry():
    # Load by path: other suites import foundry.py as the top-level "foundry" module.
    import importlib.util
    from pathlib import Path
    path = Path(__file__).resolve().parents[1] / "foundry/foundry.py"
    spec = importlib.util.spec_from_file_location("guided_test_foundry", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def base_card():
    return {"motivate": "Why", "establish": "Idea", "connect": "Connection",
            "note": "- First\n- Second", "self_explain": "Explain"}


def test_legacy_card_remains_valid():
    assert check_card("P2-1.1", base_card()) == []


def test_guided_discover_requires_a_complete_mcq():
    card = {**base_card(), 'guided_discover': {'stem': 'Try', 'options': {'A': 'One'}, 'answer': 'A'}}
    assert is_guided(card)
    assert any('guided_discover needs' in issue for issue in check_card('P2-1.1', card))


def test_guided_discover_rejects_blank_or_non_text_options():
    probe = {'stem': 'Try', 'options': {'A': 'One', 'B': 'Two', 'C': 'Three', 'D': 'Four'},
             'answer': 'A', 'explanation': 'Reason'}
    for bad in ('', 4, None):
        damaged = {**probe, 'options': {**probe['options'], 'B': bad}}
        assert any('guided_discover needs' in issue
                   for issue in check_card('P2-1.1', {**base_card(), 'guided_discover': damaged}))
    damaged = {**probe, 'answer': ['A']}
    assert any('guided_discover needs' in issue
               for issue in check_card('P2-1.1', {**base_card(), 'guided_discover': damaged}))


def test_richer_card_requires_source_backed_forms_and_complete_terms():
    card = {**base_card(), "plain_words": "An idea.", "terms": [{"term": "Proof"}],
            "forms": [{"name": "Proof"}], "misconceptions": [], "diagrams": []}
    errors = check_card("P2-1.1", card, guided=True)
    assert any("terms" in e for e in errors)
    assert any("forms" in e for e in errors)
    assert any("misconceptions" in e for e in errors)
    assert any("diagram" in e for e in errors)


def test_richer_card_accepts_justified_diagram_exception():
    card = {**base_card(), "plain_words": "An idea.",
            "terms": [{"term": "Proof", "meaning": "Logical argument", "notation": "none", "spoken": "proof", "source": "spec"}],
            "forms": [{"name": "Direct", "wordings": ["Prove"], "example": "A worked argument", "check": "Try another", "answer": "A valid argument", "source": "spec", "rubric": [{"point": "Valid argument", "keywords": [["argument"]]}]}],
            "misconceptions": [{"id": "m1", "idea": "Examples prove all cases", "temptation": "They show a pattern", "fix": "Use a general argument"}],
            "diagrams": [], "diagram_reason": "No suitable figure for this abstract idea."}
    assert check_card("P2-1.1", card, guided=True) == []


def test_guided_gate_requires_each_expected_form_and_actual_diagram(tmp_path):
    guided_problems = _foundry().guided_problems
    card = {**base_card(), "plain_words": "An idea.",
            "terms": [{"term": "Proof", "meaning": "Logical argument", "notation": "none", "spoken": "proof", "source": "spec"}],
            "forms": [{"name": "Direct", "wordings": ["Prove"], "example": "A worked argument", "check": "Try another", "answer": "A valid argument", "source": "spec", "rubric": [{"point": "Valid argument", "keywords": [["argument"]]}]}],
            "misconceptions": [{"idea": "Examples prove all cases", "temptation": "They show a pattern", "fix": "Use a general argument"}],
            "diagrams": ["Assets/P2/proof.svg"]}
    pack = {"subtopic": "P2-1", "guided_forms": {"P2-1.1": ["Direct", "Counterexample"]}, "teach": {"P2-1.1": card}}
    graph = {"kcs": [{"id": "P2-1.1", "subtopic": "P2-1"}]}
    issues = guided_problems(pack, graph, "", tmp_path)
    assert any("Counterexample" in e for e in issues)
    assert any("not rendered" in e for e in issues)
    assert any("not embedded" in e for e in issues)
    assert guided_problems({"subtopic": "P2-1"}, graph, "", tmp_path) == []


def test_guided_gate_reports_malformed_data_instead_of_crashing(tmp_path):
    guided_problems, only_glyphs = _foundry().guided_problems, _foundry().only_glyphs
    pack = {"subtopic": "P2-1", "guided_forms": {"P2-1.1": ["Direct"]},
            "teach": {"P2-1.1": {**base_card(), "forms": [{"name": []}], "diagrams": 7}}}
    graph = {"kcs": [{"id": "P2-1.1", "subtopic": "P2-1"}]}
    assert guided_problems(pack, graph, "", tmp_path)
    assert not only_glyphs({"glyphs": 1, "guided": 1, "ok": False})


def test_guided_gate_requires_misconception_to_match_tracker_and_idea(tmp_path):
    guided_problems = _foundry().guided_problems
    card = {**base_card(), "misconceptions": [
        {"idea": "Untracked", "temptation": "Reason", "fix": "Fix"},
        {"id": "m1", "idea": "Wrong idea", "temptation": "Reason", "fix": "Fix"}]}
    pack = {"subtopic": "P2-1", "guided_forms": {"P2-1.1": ["Proof"]},
            "teach": {"P2-1.1": card},
            "misconceptions": [{"id": "m1", "kc": "P2-1.2"}]}
    graph = {"kcs": [{"id": "P2-1.1", "subtopic": "P2-1"}]}
    issues = guided_problems(pack, graph, "", tmp_path)
    assert any("misconception" in e and "tracker" in e for e in issues)
    pack["misconceptions"][0]["kc"] = "P2-1.1"
    card["misconceptions"] = card["misconceptions"][1:]
    assert not any("misconception" in e and "tracker" in e for e in guided_problems(pack, graph, "", tmp_path))


def test_guided_form_without_marking_rubric_is_rejected():
    card = {**base_card(), "plain_words": "Idea",
            "terms": [{"term": "Proof", "meaning": "Argument", "notation": "none", "spoken": "proof", "source": "spec"}],
            "forms": [{"name": "Direct", "wordings": ["Prove"], "example": "Example", "check": "Check", "answer": "Answer", "source": "spec"}],
            "misconceptions": [{"idea": "Mistake", "temptation": "Reason", "fix": "Correction"}],
            "diagrams": [], "diagram_reason": "No figure is relevant."}
    assert any("rubric" in e for e in check_card("kc", card, guided=True))


def test_guided_retry_requires_a_distinct_question_answer_and_rubric():
    card = {**base_card(), 'plain_words': 'Idea',
            'terms': [{'term': 'Proof', 'meaning': 'Argument', 'notation': 'none', 'spoken': 'proof', 'source': 'spec'}],
            'forms': [{'name': 'Direct', 'wordings': ['Prove'], 'example': 'Example', 'check': 'Check',
                       'answer': 'Answer', 'source': 'spec', 'rubric': [{'point': 'Proof', 'keywords': [['proof']]}],
                       'retry': {'check': 'Check', 'answer': 'Another answer', 'rubric': []}}],
            'misconceptions': [{'id': 'm1', 'idea': 'Mistake', 'temptation': 'Reason', 'fix': 'Correction'}],
            'diagrams': [], 'diagram_reason': 'No figure is relevant.'}
    assert any('retry' in e for e in check_card('kc', card, guided=True))
    card['forms'][0]['retry'] = {'check': 'Different check', 'answer': 'Another answer',
                                  'rubric': [{'point': 'Proof', 'keywords': [['proof']]}]}
    assert not check_card('kc', card, guided=True)


def test_guided_diagrams_need_descriptions_for_terminal_accessibility():
    card = {**base_card(), "plain_words": "Idea", "terms": [{"term": "Proof", "meaning": "Argument", "notation": "none", "spoken": "proof", "source": "spec"}],
            "forms": [{"name": "Direct", "wordings": ["Prove"], "example": "Example", "check": "Check", "answer": "Answer", "source": "spec", "rubric": [{"point": "Valid argument", "keywords": [["argument"]]}]}],
            "misconceptions": [{"idea": "Mistake", "temptation": "Reason", "fix": "Correction"}], "diagrams": ["Assets/P2/x.svg"]}
    assert any("diagram_descriptions" in e for e in check_card("kc", card, guided=True))


def test_guided_gate_finds_diagram_renderer_uppercase_assets(tmp_path, monkeypatch):
    guided_problems = _foundry().guided_problems
    from pathlib import Path
    asset = tmp_path / "Assets" / "P2" / "proof.svg"
    asset.parent.mkdir(parents=True)
    asset.write_text("<svg/>")
    card = {**base_card(), "plain_words": "Idea", "terms": [{"term": "Proof", "meaning": "Argument", "notation": "none", "spoken": "proof", "source": "spec"}],
            "forms": [{"name": "Direct", "wordings": ["Prove"], "example": "Example", "check": "Check", "answer": "Answer", "source": "spec", "rubric": [{"point": "Valid argument", "keywords": [["argument"]]}]}],
            "misconceptions": [{"id": "m1", "idea": "Mistake", "temptation": "Reason", "fix": "Correction"}],
            "diagrams": ["Assets/P2/proof.svg"], "diagram_descriptions": ["The proof has three stages."]}
    pack = {"subtopic": "P2-1", "guided_forms": {"kc": ["Direct"]}, "teach": {"kc": card},
            "misconceptions": [{"id": "m1", "kc": "kc"}]}
    graph = {"kcs": [{"id": "kc", "subtopic": "P2-1"}]}
    original = Path.is_file
    monkeypatch.setattr(Path, "is_file", lambda p: False if str(p).startswith(str(tmp_path / "assets") + "/") else original(p))
    assert not guided_problems(pack, graph, "![[Assets/P2/proof.svg]]", tmp_path / "assets")


def test_malformed_exam_language_is_rejected():
    card = {**base_card(), "exam_language": [{"name": "Prove"}]}
    assert any("exam_language" in e for e in check_card("kc", card, guided=True))


def test_guided_fields_receive_math_format_lint():
    card = {**base_card(), "plain_words": "The quantity is $x", "terms": [], "forms": [], "misconceptions": [], "diagrams": [], "diagram_reason": "No useful diagram."}
    errors = check_card("kc", card, guided=True)
    assert any("plain_words" in e and "unbalanced-dollar" in e for e in errors)


def test_merge_rejects_incomplete_guided_card_without_removing_existing_cards(tmp_path, monkeypatch):
    import json
    from build import teach_cards
    root = tmp_path
    for directory in ('build/work/teach', 'build/out/packs/P2', 'build/out/specs/P2'):
        (root / directory).mkdir(parents=True)
    graph = {'kcs': [{'id': 'P2-1.1', 'subtopic': 'P2-1'}, {'id': 'P2-1.2', 'subtopic': 'P2-1'}]}
    (root / 'build/out/specs/P2/graph.json').write_text(json.dumps(graph))
    original = {'spec': 'P2', 'teach': {'P2-1.1': base_card(), 'P2-1.2': base_card()}}
    path = root / 'build/out/packs/P2/P2-1.json'
    path.write_text(json.dumps(original))
    cards = {'P2-1.1': {**base_card(), 'plain_words': 'Incomplete guided draft'}, 'P2-1.2': base_card()}
    (root / 'build/work/teach/P2-1.json').write_text(json.dumps(cards))
    monkeypatch.setattr(teach_cards, 'ROOT', root)
    assert teach_cards.main('merge', ['P2-1']) == 1
    assert json.loads(path.read_text()) == original


def test_foundry_gate_does_not_pass_when_guided_draft_is_not_merged(tmp_path):
    guided_draft_problems = _foundry().guided_draft_problems
    path = tmp_path / 'draft.json'
    import json
    path.write_text(json.dumps({'kc': {**base_card(), 'plain_words': 'Incomplete'}}))
    pack = {'subtopic': 'chapter', 'teach': {'kc': base_card()}}
    graph = {'kcs': [{'id': 'kc', 'subtopic': 'chapter'}]}
    issues = guided_draft_problems(path, pack, graph)
    assert any('terms' in issue for issue in issues)
    assert any('not merged' in issue for issue in issues)


def test_form_diagram_must_reference_a_declared_card_diagram():
    import json
    from pathlib import Path
    card = library_json('build/work/teach/P2-1.json')['P2-1.1']
    form = next(f for f in card['forms'] if f.get('diagram'))
    assert check_card('P2-1.1', card, guided=True) == []
    form['diagram'] = 'Assets/P2/missing.svg'
    assert any('form diagram' in e for e in check_card('P2-1.1', card, guided=True))
    form['diagram'] = ['Assets/P2/missing.svg']
    assert any('form diagram' in e for e in check_card('P2-1.1', card, guided=True))


def test_guided_form_rejects_unknown_review_rule():
    from teach_cards import check_card
    import json
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    cards = library_json('build/work/teach/P2-1.json')
    card = cards['P2-1.3']
    form = next(f for f in card['forms'] if f['name'] == 'Counterexample involving consecutive primes')
    form['review_rule'] = 'unknown-rule'
    assert any('review rule' in error for error in check_card('P2-1.3', card, guided=True))


def test_blind_solver_includes_guided_discovery_without_answer_key():
    from build import blind
    pack = {'teach': {'P2-1.1': {
        'discover': {'stem': 'Old?', 'options': {'A': 'yes', 'B': 'no'}, 'answer': 'A'},
        'guided_discover': {'stem': 'New?', 'options': {'A': 'one', 'B': 'two'}, 'answer': 'B',
                            'explanation': 'Private explanation'}}}}
    questions = blind.strip(pack)
    guided = next(q for q in questions if q['id'] == 'P2-1.1.guided_discover')
    assert guided == {'id': 'P2-1.1.guided_discover', 'kind': 'mcq', 'stem': 'New?',
                      'options': {'A': 'one', 'B': 'two'}}
    assert blind.compare(pack, {'P2-1.1.discover': 'A', 'P2-1.1.guided_discover': 'B'})['agreed'] == 2
    assert blind.compare(pack, {'P2-1.1.discover': 'A', 'P2-1.1.guided_discover': 'A'})['disagreements'][0]['id'] == guided['id']


def test_blind_written_export_omits_examples_answers_and_rubrics():
    from build import blind
    cards = {'P2-1.1': {'forms': [{'name': 'Proof', 'example': 'secret example',
        'check': 'Prove it.', 'answer': 'secret answer', 'rubric': [{'point': 'secret point'}],
        'retry': {'check': 'Prove another.', 'answer': 'secret retry', 'rubric': [{'point': 'secret'}]}}]}}
    assert blind.strip_guided_written(cards) == [
        {'id': 'P2-1.1.form.0.check', 'stem': 'Prove it.'},
        {'id': 'P2-1.1.form.0.retry', 'stem': 'Prove another.'}]


def test_guided_retry_rejects_unknown_review_rule():
    import json
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    cards = library_json('build/work/teach/P2-1.json')
    card = cards['P2-1.3']
    form = next(f for f in card['forms'] if f['name'] == 'Counterexample after widening the domain')
    form['retry']['review_rule'] = 'not-a-rule'
    assert any('retry review rule' in error for error in check_card('P2-1.3', card, guided=True))


@pytest.mark.parametrize("merge_path", ["cli", "foundry"])
def test_merge_paths_preserve_omitted_cards_and_fields_but_apply_explicit_updates(tmp_path, monkeypatch, merge_path):
    """Both entry points retain probes; supplied lists remain explicit replacements."""
    import copy
    import json
    from build import teach_cards
    root = tmp_path
    for directory in ('build/work/teach', 'build/out/packs/P2', 'build/out/specs/P2'):
        (root / directory).mkdir(parents=True)
    graph = {'kcs': [{'id': 'P2-1.1', 'subtopic': 'P2-1'}]}
    (root / 'build/out/specs/P2/graph.json').write_text(json.dumps(graph))
    probe = {'stem': 'Choose', 'options': dict(A='One', B='Two', C='Three', D='Four'),
             'answer': 'A', 'explanation': 'One applies.'}
    original = {'subtopic': 'P2-1', 'spec': 'P2', 'items': [{'id': 'protected'}],
                'teach': {'P2-1.1': {**base_card(), 'guided_discover': probe,
                                    'disclosed_item_ids': ['old']},
                          'existing-kc': base_card()}}
    staged = {'P2-1.1': {**base_card(), 'motivate': 'Updated motivation',
                          'disclosed_item_ids': ['new']}}
    (root / 'build/work/teach/P2-1.json').write_text(json.dumps(staged))
    path = root / 'build/out/packs/P2/P2-1.json'
    monkeypatch.setattr(teach_cards, 'ROOT', root)
    foundry = _foundry()
    monkeypatch.setattr(foundry, 'ROOT', root)
    monkeypatch.setattr(foundry, 'SPECS', root / 'build/out/specs')
    monkeypatch.setattr(foundry, 'pack_path', lambda sub: path)
    monkeypatch.setattr(foundry, 'spec_of', lambda sub: 'P2')
    path.write_text(json.dumps(original))
    if merge_path == 'cli':
        teach_cards.main('merge', ['P2-1'])
    else:
        foundry.merge_teach('P2-1')
    actual = json.loads(path.read_text())
    expected = copy.deepcopy(original)
    expected['teach']['P2-1.1'].update(staged['P2-1.1'], source='pack')
    assert actual == expected


@pytest.mark.parametrize('ident', [None, '', '   ', 7])
def test_guided_misconception_requires_tracker_id_at_card_check(ident):
    misconception = {'idea': 'Mistake', 'temptation': 'Reason', 'fix': 'Correction'}
    if ident is not None:
        misconception['id'] = ident
    card = {**base_card(), 'misconceptions': [misconception]}
    errors = check_card('kc', card, guided=True)
    assert any('misconceptions entry needs id' in error for error in errors)
    assert not check_card('kc', card), 'Legacy cards remain compatible until guided validation is requested.'


def test_guided_misconception_id_check_does_not_invent_or_resolve_bindings():
    card = {**base_card(), 'misconceptions': [{'id': 'm-existing', 'idea': 'Mistake',
                                            'temptation': 'Reason', 'fix': 'Correction'}]}
    assert not any('misconceptions entry needs' in e for e in check_card('kc', card, guided=True))
    assert card['misconceptions'][0]['id'] == 'm-existing'
