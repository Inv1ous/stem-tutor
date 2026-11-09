"""Workflow refresh regressions; all writes target synthetic disposable vaults."""
import copy
import hashlib
import json
import random

import pytest

from fixtures import make_vault
from tutorlib import packs, session, store, teach_actions as ta, topicals
from tutorlib.asset_library import write_asset

SUB, KC = '9702-2.1', '9702-2.1.1'


def make_tutor(tmp_path, kind='mcq', media=None):
    tutor = session.Tutor(store.Vault(make_vault(tmp_path)))
    tutor.start(mode='test', minutes=10, focus=[SUB])
    item = copy.deepcopy(tutor.packs.pack(SUB)['items'][0])
    item['kind'] = kind
    if media:
        item.update(media)
    node = {'inst': item, 'item': item['id'], 'kcs': [KC], 'unassisted': True,
            'serving_chapter': SUB, 'hinted': False, 'hint_level': 0}
    tutor.session['presented'] = {'1': node}
    return tutor, node


@pytest.mark.parametrize('kind', ['mcq', 'numeric', 'expression', 'short', 'structured'])
@pytest.mark.parametrize('media', [None, {'image': 'protected.png'}, {'images': ['a.jpg', 'b.svg']}])
def test_graph_solvability_is_metadata_only_for_every_kind_and_media(tmp_path, kind, media):
    tutor, node = make_tutor(tmp_path, kind, media)
    before = copy.deepcopy(node)
    result = tutor.check_solvable(1)
    assert result['status'] == 'solvable'
    assert result['basis'] == 'course_graph'
    assert 'course graph' in result['message'].lower()
    assert node == before and '1' in tutor.session['presented']
    assert 'topical' not in node['inst']
    assert not tutor.state.get('topical_exclusions')
    assert not node['hinted']


def test_graph_missing_prerequisites_remain_open_without_reviewed_exclusion(tmp_path):
    tutor, node = make_tutor(tmp_path)
    tutor.packs.kcs[KC]['prereqs'] = ['9702-3.1.1']
    tutor.packs.kcs['9702-3.1.1'] = {'id': '9702-3.1.1', 'subtopic': '9702-3.1', 'spec': '9702', 'prereqs': ['9702-4.1.1']}
    tutor.packs.kcs['9702-4.1.1'] = {'id': '9702-4.1.1', 'subtopic': '9702-4.1', 'spec': '9702', 'prereqs': []}
    for sub in ['9702-3.1', '9702-4.1']:
        tutor.packs.subtopics[sub] = {'id': sub, 'spec': '9702'}
    result = tutor.check_solvable(1)
    assert result['status'] == 'unavailable'
    assert result['topics'] == ['3.1', '4.1']
    assert '1' in tutor.session['presented'] and not tutor.state.get('topical_exclusions')
    assert 'remains open' in result['message']


@pytest.mark.parametrize('corruption', ['unknown', 'malformed', 'cycle', 'foreign', 'unknown_assessed', 'topical'])
def test_incomplete_or_conflicting_graph_is_unverified(tmp_path, corruption):
    tutor, node = make_tutor(tmp_path)
    if corruption == 'unknown':
        tutor.packs.kcs[KC]['prereqs'] = ['missing']
    elif corruption == 'malformed':
        tutor.packs.kcs[KC]['prereqs'] = 'not a list'
    elif corruption == 'cycle':
        tutor.packs.kcs[KC]['prereqs'] = [KC]
    elif corruption == 'foreign':
        tutor.packs.kcs[KC]['spec'] = '9701'
    elif corruption == 'unknown_assessed':
        node['inst']['kcs'] = ['missing']
    else:
        node['inst']['topical'] = {'reviewed': False}
    result = tutor.check_solvable(1)
    expected = 'topic_pending' if corruption == 'unknown_assessed' else 'unverified'  # untagged: AI names the topics
    assert result['status'] == expected and '1' in tutor.session['presented']


def set_items(root, items):
    path = root / '.tutor/packs/v1/specs/9702/packs/9702-2.1.json'
    content = json.loads(path.read_text())
    content['items'] = items
    path.write_text(json.dumps(content))


def past_item(identifier):
    return {'id': identifier, 'kind': 'mcq', 'kcs': [KC], 'marks': 1, 'difficulty': 3,
            'source': {'type': 'past', 'qid': '9702_w20_13_q34'}, 'stem': 'Which quantity is a vector?',
            'options': {'A': 'distance', 'B': 'displacement'}, 'answer': 'B'}


def test_no_bank_dedups_equivalent_context_keeps_alias_history_and_distinct_parts(tmp_path):
    root = make_vault(tmp_path)
    one, two, part = [past_item(i) for i in ('explained', 'extra', 'part')]
    one['explanation'] = 'A vector has direction.'
    two.update(stem='Which quantity\nis a vector?', tier='extra', explanation=None)
    part['source']['part'] = 'a'
    set_items(root, [one, two, part])
    content = packs.Packs(store.Vault(root))
    assert [i['id'] for i in content.items_for(KC)] == ['explained', 'part']
    assert content.aliases_for(one) == {'explained', 'extra'}
    state = {'kcs': {}, 'items_seen': {'extra': '2026-10-30T10:00:00'}}
    assert content.select_item(KC, state, .7, random.Random(0), exclude={'extra', 'part'}) is None
    assert len(content.pack(SUB)['items']) == 3  # selection never rewrites originals


@pytest.mark.parametrize('field,value', [('answer', 'A'), ('marks', 2), ('scheme', [{'point': 'different'}]),
                                        ('image', 'different.svg'), ('unknown_assessment', True),
                                        ('options', {'A': 'changed', 'B': 'displacement'})])
def test_conflicting_same_context_items_are_retained_and_reported(tmp_path, field, value):
    root = make_vault(tmp_path)
    one, two = past_item('one'), past_item('two')
    two[field] = value
    set_items(root, [one, two])
    content = packs.Packs(store.Vault(root))
    assert len(content.items_for(KC)) == 2
    assert content.selection_conflicts and 'one' in str(content.selection_conflicts) and 'two' in str(content.selection_conflicts)


@pytest.mark.parametrize('extension', ['svg', 'png', 'jpg', 'jpeg'])
def test_discover_verified_explicit_chapter_or_kc_diagrams(tmp_path, extension):
    data = b'<svg/>' if extension == 'svg' else b'synthetic figure bytes'
    path = f'Library/Courses/9702/Diagrams/lesson.{extension}'
    write_asset(tmp_path, path, data, metadata={'subtopic': SUB, 'caption': 'A vector',
                                              'description': 'An arrow pointing right.', 'provenance': {'source': 'teacher'}})
    figures = ta.figures_for(tmp_path, SUB, kc=KC)
    assert len(figures) == 1 and figures[0]['file'] == path
    assert figures[0]['description'] == 'An arrow pointing right.' and figures[0]['source']
    assert not ta.figures_for(tmp_path, '9702-3.1', kc='9702-3.1.1')
    (tmp_path / path).write_bytes(b'tampered')
    assert not ta.figures_for(tmp_path, SUB, kc=KC)


def test_kc_binding_and_card_binding_are_explicit_and_assessment_media_is_never_offered(tmp_path):
    data = b'<svg/>'
    a = 'Library/Courses/9702/Diagrams/kc.svg'
    b = 'Library/Courses/9702/Diagrams/card.svg'
    c = 'Library/Courses/9702/Questions/Media/answer.svg'
    for path in (a, b, c):
        write_asset(tmp_path, path, data, metadata={'kcs': [KC], 'description': 'Explicit figure'})
    write_asset(tmp_path, 'Library/Courses/9702/Diagrams/unrelated.svg', data)
    assert {f['file'] for f in ta.figures_for(tmp_path, SUB, kc=KC, card={'diagrams': [b, c]})} == {a, b}
    assert ta.figures_for(tmp_path, SUB, kc='9702-2.1.4') == []


def test_assessment_sidecar_cannot_offer_legacy_question_as_explanation(tmp_path):
    path = tmp_path / 'Assets/topicals/question.png'
    path.parent.mkdir(parents=True)
    data = b'protected question'
    path.write_bytes(data)
    path.with_suffix('.png.json').write_text(json.dumps({'subtopic': SUB, 'sha256': hashlib.sha256(data).hexdigest()}))
    assert ta.figures_for(tmp_path, SUB, kc=KC) == []


def test_declared_course_conflict_is_not_a_teaching_binding(tmp_path):
    write_asset(tmp_path, 'Library/Courses/9702/Diagrams/conflict.svg', b'<svg/>',
                metadata={'course': '9701', 'subtopic': SUB})
    assert ta.figures_for(tmp_path, SUB, kc=KC) == []


@pytest.mark.parametrize('chapters', [None, SUB, {'chapter': SUB}])
def test_malformed_reviewed_requirements_remain_unverified_and_open(tmp_path, chapters):
    tutor, node = make_tutor(tmp_path)
    node['inst']['topical'] = {'reviewed': True, 'requires': [SUB], 'chapters': chapters, 'revision': '2025-2027'}
    result = tutor.check_solvable(1)
    assert result['status'] == 'unverified' and '1' in tutor.session['presented']
