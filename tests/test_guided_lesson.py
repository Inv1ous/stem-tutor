"""Guided cards reuse the lesson activity stream."""
from types import SimpleNamespace
import pytest

from tutorlib.lesson import LessonMixin
from library_assets import read_json


class StubLesson(LessonMixin):
    def __init__(self):
        self.session = {}
        self.packs = SimpleNamespace(kcs={"P2-1.1": {"title": "Proof"}})

    def _await(self, activity):
        return activity

    def log(self, event):
        pass


def test_guided_discover_keeps_original_but_serves_distinct_probe():
    tutor = StubLesson()
    captured = []
    tutor._questions = lambda block, idx, items, phase=None: captured.extend(items) or {'activity': 'questions'}
    old = {'stem': 'Old probe', 'options': {'A': 'old'}, 'answer': 'A'}
    new = {'stem': 'Distinct probe', 'options': {'A': 'new'}, 'answer': 'A'}
    card = {'source': 'pack', 'discover': old, 'guided_discover': new}
    tutor._step_node({'kc': 'P2-1.1', 'card': card, 'i': 0, 'phases': ['discover']}, 0)
    assert captured[0]['stem'] == 'Distinct probe'
    assert captured[0]['id'] != 'P2-1.1-discover'
    assert card['discover'] == old


def test_guided_lesson_presents_terms_before_plain_words_without_revealing_checks():
    tutor = StubLesson()
    card = {"source": "pack", "terms": [{"term": "Integer", "meaning": "whole number", "notation": "ℤ", "spoken": "integers"}],
            "plain_words": "A proof justifies a claim.", "forms": [{"answer": "secret solution"}]}
    block = {"kc": "P2-1.1", "card": card, "i": 0, "phases": ["terms", "plain_words"]}
    terms = tutor._step_node(block, 0)
    plain = tutor._step_node(block, 0)
    assert terms["title"] == "Helpful terms"
    assert all(word in terms["text"] for word in ("Integer", "whole number", "ℤ", "integers"))
    assert plain["text"] == "A proof justifies a claim."
    assert "secret solution" not in str((terms, plain))


def test_form_example_is_followed_by_a_separate_question_with_a_rubric():
    tutor = StubLesson()
    captured = []
    def questions(block, idx, items, phase=None, unassisted=False):
        captured.extend(items)
        return {"activity": "questions", "items": [{"stem": items[0]["stem"]}]}
    tutor._questions = questions
    form = {"name": "Counterexample", "wordings": ["Disprove"], "example": "Example proof.",
            "check": "Try a new claim.", "answer": "One valid counterexample.",
            "rubric": [{"point": "Give an allowed counterexample.", "keywords": [["example"]]}]}
    block = {"kind": "node", "kc": "P2-1.1", "card": {"source": "pack", "forms": [form]},
             "i": 0, "phases": ["form_example:0", "form_check:0"]}
    example = tutor._step_node(block, 0)
    check = tutor._step_node(block, 0)
    assert "Example proof." in example["text"]
    assert check["items"][0]["stem"] == "Try a new claim."
    assert "counterexample." not in str(check)
    assert captured[0]["rubric"] == form["rubric"]


def test_diagram_has_terminal_description_and_obsidian_embed():
    from tutorlib import views
    tutor = StubLesson()
    card = {"source": "pack", "diagrams": ["Assets/P2/cases.svg"],
            "diagram_descriptions": ["Every integer is either even or odd."]}
    block = {"kc": "P2-1.1", "card": card, "i": 0, "phases": ["diagram:0"]}
    activity = tutor._step_node(block, 0)
    terminal = views.activity_cards(activity)
    obsidian = views.activity_cards(activity, obsidian=True)
    assert "Every integer is either even or odd" in str(terminal)
    assert "![[" not in str(terminal)
    assert "![[Assets/P2/cases.svg]]" in str(obsidian)


def test_presented_terms_are_registered_with_stable_ids():
    tutor = StubLesson()
    events = []
    tutor.log = events.append
    term = {"term": "Integer", "meaning": "whole number", "notation": "ℤ", "spoken": "integers"}
    card = {"source": "pack", "terms": [term]}
    block = {"kc": "P2-1.1", "card": card, "i": 0, "phases": ["terms"]}
    tutor._step_node(block, 0)
    assert len(events) == 1 and events[0]["type"] == "term_introduced"
    assert events[0]["kc"] == "P2-1.1"
    assert events[0]["term_id"].startswith("term:")


def test_plain_words_keep_long_explanation_hidden_until_requested():
    from tutorlib import views
    tutor = StubLesson()
    card = {"source": "pack", "plain_words": "Short version.", "establish": "Detailed explanation.", "connect": "Connection."}
    block = {"kc": "P2-1.1", "card": card, "i": 0, "phases": ["plain_words"]}
    act = tutor._step_node(block, 0)
    assert act["text"] == "Short version."
    assert "Detailed explanation" not in str(views.activity_cards(act))
    assert "Detailed explanation" in act["detail"]


def test_misconception_explains_temptation_and_fix():
    tutor = StubLesson()
    card = {"source": "pack", "misconceptions": [{"idea": "Examples prove all cases",
            "temptation": "A pattern looks convincing", "fix": "Cover the whole domain"}]}
    block = {"kc": "P2-1.1", "card": card, "i": 0, "phases": ["misconception:0"]}
    act = tutor._step_node(block, 0)
    assert act["title"] == "Common misconception"
    assert all(s in act["text"] for s in ("Examples prove all cases", "A pattern looks convincing", "Cover the whole domain"))


def test_fix_targets_matching_guided_misconception():
    tutor = StubLesson()
    card = {"source": "pack", "establish": "General explanation", "misconceptions": [
        {"id": "m1", "idea": "Wrong idea", "temptation": "Why tempting", "fix": "Specific fix"}]}
    block = {"kc": "P2-1.1", "card": card, "i": 0, "phases": ["fix"],
             "fix_mis": {"id": "m1", "statement": "Wrong idea", "refutation": "Old fix"}}
    act = tutor._step_node(block, 0)
    assert act["activity"] == "explain"
    assert "Specific fix" in act["text"] and "Why tempting" in act["text"]


def test_p2_repeated_pair_misconception_reteaches_its_specific_fix():
    import json
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    card = read_json('build/work/teach/P2-1.json')["P2-1.2"]
    pack = read_json("build/out/packs/P2/P2-1.json")
    misconception = next(m for m in pack["misconceptions"] if m["id"] == "m3")
    tutor = StubLesson()
    tutor.packs.kcs["P2-1.2"] = {"title": "Proof by exhaustion"}
    block = {"kc": "P2-1.2", "card": card, "i": 0, "phases": ["fix"], "fix_mis": misconception}
    act = tutor._step_node(block, 0)
    assert act["activity"] == "explain"
    assert "equal-value pairs" in act["text"] and "Swapping" in act["text"]


def test_form_miss_keeps_reviewed_mark_points_in_lesson_mistakes():
    tutor = StubLesson()
    block = {'kc': 'P2-1.1', 'misses': 0, 'mistakes': [], 'phases': ['check'], 'i': 0}
    feedback = {'phase': 'form_check', 'answer': 'All points',
                'explanation': '✓ Listed the cases\n✗ Proved both cases'}
    tutor._node_check_result(block, {'correct': False}, feedback, 'One case proof')
    assert '✓ Listed the cases' in block['mistakes'][0]
    assert '✗ Proved both cases' in block['mistakes'][0]


def test_form_miss_revisits_matching_example_before_another_check():
    tutor = StubLesson()
    card = {'source': 'pack', 'establish': 'General idea.', 'diagrams': ['Assets/P2/geometry.svg'],
            'diagram_descriptions': ['A labelled geometry figure.'], 'forms': [
        {'name': 'First form', 'example': 'Unrelated example.'},
        {'name': 'Second form', 'example': 'The relevant worked example.', 'diagram': 'Assets/P2/geometry.svg',
         'check': 'SECRET CHECK', 'answer': 'SECRET ANSWER'}]}
    block = {'kc': 'P2-1.1', 'card': card, 'misses': 0, 'mistakes': [], 'phases': [], 'i': 0}
    tutor._node_check_result(block, {'correct': False},
                             {'phase': 'form_check', 'form_index': 1, 'answer': 'answer'}, 'attempt')
    repair = tutor._step_node(block, 0)
    assert repair['part'] == 'fix'
    assert 'The relevant worked example.' in repair['text']
    assert 'Unrelated example.' not in repair['text']
    assert repair['diagram'] == 'Assets/P2/geometry.svg'
    assert repair['diagram_description'] == 'A labelled geometry figure.'
    assert 'SECRET CHECK' not in str(repair) and 'SECRET ANSWER' not in str(repair)


def test_skipped_form_does_not_schedule_form_example_as_repair():
    tutor = StubLesson()
    block = {'kc': 'P2-1.1', 'misses': 0, 'mistakes': [], 'phases': [], 'i': 0}
    tutor._node_check_result(block, {'correct': False},
                             {'phase': 'form_check', 'form_index': 1, 'answer': ''}, '?')
    assert 'fix_form' not in block


def test_later_form_miss_gets_its_own_repair_after_an_earlier_miss():
    tutor = StubLesson()
    block = {'kc': 'P2-1.1', 'misses': 1, 'mistakes': [], 'phases': ['done'], 'i': 0,
             'form_repairs': [0]}
    tutor._node_check_result(block, {'correct': False},
                             {'phase': 'form_check', 'form_index': 1, 'answer': 'answer'}, 'attempt')
    assert block['fix_form'] == 1
    assert block['phases'][:2] == ['fix', 'check']
    assert not block.get('stuck')


def test_repeated_miss_on_same_form_still_escalates():
    tutor = StubLesson()
    block = {'kc': 'P2-1.1', 'misses': 1, 'mistakes': [], 'phases': ['done'], 'i': 0,
             'form_repairs': [1]}
    tutor._node_check_result(block, {'correct': False},
                             {'phase': 'form_check', 'form_index': 1, 'answer': 'answer'}, 'attempt')
    assert block['stuck'] and block['phases'][0] == 'stuck'


def test_form_with_distinct_retry_schedules_a_matching_check():
    tutor = StubLesson()
    form = {'name': 'Parity', 'example': 'A worked example.', 'check': 'First claim.', 'answer': 'First answer.',
            'rubric': [{'point': 'Proof', 'keywords': [['proof']]}],
            'retry': {'check': 'A different parity claim.', 'answer': 'Retry answer.',
                      'rubric': [{'point': 'Both cases', 'keywords': [['cases']]}]}}
    block = {'kc': 'P2-1.1', 'card': {'source': 'pack', 'forms': [form]}, 'misses': 0,
             'mistakes': [], 'phases': ['done'], 'i': 0}
    tutor._node_check_result(block, {'correct': False},
                             {'phase': 'form_check', 'form_index': 0, 'answer': 'First answer.'}, 'attempt')
    assert block['phases'][:2] == ['fix', 'form_retry:0']
    repair = tutor._step_node(block, 0)
    assert 'A worked example.' in repair['text'] and 'Retry answer.' not in str(repair)
    captured = []
    tutor._questions = lambda b, i, items, **kw: captured.extend(items) or {'activity': 'questions', 'items': []}
    activity = tutor._step_node(block, 0)
    assert activity['say'] and captured[0]['stem'] == 'A different parity claim.'
    assert captured[0]['review_answer'] == 'Retry answer.'


def test_p2_draft_diagnostics_identify_and_reteach_their_misconceptions():
    import json
    from pathlib import Path
    from tutorlib.grade import grade_item
    root = Path(__file__).resolve().parents[1]
    cards = read_json('build/work/teach/P2-1.json')
    draft = read_json('build/work/guided/P2-1-misconceptions.json')
    for item, misconception in zip(draft["items"], draft["misconceptions"], strict=True):
        assert grade_item(item, {"kind": "choice", "value": "A"})["correct"]
        result = grade_item(item, {"kind": "choice", "value": "B"})
        assert result["misconception"] == misconception["id"]
        kc = item["kcs"][0]
        tutor = StubLesson()
        tutor.packs.kcs[kc] = {"title": "Proof"}
        block = {"kc": kc, "card": cards[kc], "i": 0, "phases": ["fix"], "fix_mis": misconception}
        act = tutor._step_node(block, 0)
        matching = next(m for m in cards[kc]["misconceptions"] if m.get("id") == misconception["id"])
        assert matching["fix"] in act["text"] and matching["temptation"] in act["text"]


def test_p2_inequality_form_accepts_alternative_method_as_judgement_hint():
    import json
    from pathlib import Path
    from tutorlib.grade import grade_item
    cards = read_json('build/work/teach/P2-1.json')
    form = next(f for f in cards["P2-1.1"]["forms"] if f["name"] == "Justify division in an inequality proof")
    item = {"kind": "short", "rubric": form["rubric"]}
    correct = grade_item(item, {"kind": "value", "value":
        "c is negative, so multiplying both sides by its reciprocal reverses the inequality: x > y."})
    assert correct["score"] == 1 and correct["needs_judgement"]
    wrong = grade_item(item, {"kind": "value", "value":
        "c is negative; do not reverse when dividing, so x > y."})
    assert wrong["needs_judgement"] and not wrong["correct"]


def test_exam_language_explains_command_words_and_mark_types():
    tutor = StubLesson()
    card = {"source": "pack", "exam_language": [{"name": "Prove", "meaning": "Give a complete logical argument."},
            {"name": "M mark", "meaning": "A mark for a valid method."}]}
    block = {"kc": "P2-1.1", "card": card, "i": 0, "phases": ["exam_language"]}
    act = tutor._step_node(block, 0)
    assert act["title"] == "Exam language"
    assert all(s in act["text"] for s in ("Prove", "logical argument", "M mark", "valid method"))


def test_terminal_diagram_step_says_where_to_find_the_image():
    from tutorlib import views
    act = {"activity": "explain", "title": "Diagram", "text": "Description.", "diagram": "Assets/P2/figure.svg"}
    role, title, body = views.activity_cards(act)[0]
    assert "Obsidian" in body and "ctrl+o" in body
    assert "ctrl+o" not in views.activity_cards(act, obsidian=True)[0][2]


def test_form_example_attaches_its_associated_diagram():
    tutor = StubLesson()
    form = {'name': 'Geometry', 'wordings': ['Prove'], 'example': 'Worked geometry.',
            'diagram': 'Assets/P2/geometry.svg'}
    block = {'kc': 'P2-1.1', 'card': {'source': 'pack', 'forms': [form],
             'diagrams': [form['diagram']], 'diagram_descriptions': ['Circle with three labelled points.']},
             'i': 0, 'phases': ['form_example:0']}
    act = tutor._step_node(block, 0)
    assert act['diagram'] == form['diagram']
    assert 'Worked geometry.' in act['text']
    from tutorlib import views
    assert 'Circle with three labelled points.' in views.activity_cards(act)[0][2]
    assert '![[Assets/P2/geometry.svg]]' in views.activity_cards(act, obsidian=True)[0][2]


def test_retry_uses_its_own_domain_review_rule():
    tutor = StubLesson()
    form = {'name': 'Domain', 'example': 'Example', 'check': 'Initial check', 'answer': 'Answer',
            'review_rule': 'consecutive_primes', 'rubric': [{'point': 'Point', 'keywords': [['point']]}],
            'retry': {'check': 'Positive pairs only', 'answer': 'Retry', 'review_rule': 'positive_pair',
                      'rubric': [{'point': 'Point', 'keywords': [['point']]}]}}
    block = {'kc': 'P2-1.1', 'card': {'source': 'pack', 'forms': [form]}, 'i': 0,
             'phases': ['form_retry:0'], 'misses': 0, 'mistakes': []}
    captured = []
    tutor._questions = lambda b, i, items, **kw: captured.extend(items) or {'activity': 'questions', 'items': []}
    tutor._step_node(block, 0)
    assert captured[0]['review_rule'] == 'positive_pair'


def test_faded_written_check_uses_short_answer_judgment():
    tutor = StubLesson()
    faded = {'id': 'we2f', 'kind': 'short', 'problem': 'Disprove the claim.',
             'review_answer': '111 = 3 × 37',
             'rubric': [{'point': 'Factors', 'keywords': [['3'], ['37']]}]}
    tutor.packs.worked_for = lambda kc: [{'faded': faded}]
    captured = []
    tutor._questions = lambda block, idx, items, phase=None: captured.extend(items) or {'activity': 'questions'}
    block = {'kind': 'node', 'kc': 'P2-1.1', 'card': {'source': 'pack'}, 'i': 0, 'phases': ['faded']}
    assert tutor._step_node(block, 0)['activity'] == 'questions'
    assert captured[0]['kind'] == 'short'
    assert captured[0]['review_answer'] == faded['review_answer']
