"""Counted topical sets preserve reviewed identity, eligibility and saved attempts."""
from copy import deepcopy
import json
import random

import pytest

from test_topicals import TARGET, OTHER, THIRD, bank_vault, item, publish, tutor_for
from tutorlib import topicals


def mixed_bank(root):
    """Disposable variants of the existing synthetic bank exercise selection, not teaching content."""
    rows = []
    for index, chapter in enumerate((TARGET, OTHER, THIRD)):
        for n in range(4 if chapter == TARGET else 1):
            row = item(id=f'choice-{index}-{n}', kcs=[chapter + '.1'],
                       source={'type': 'past', 'qid': f'9702_s23_22_q{20 + index * 10 + n}'})
            row['topical'].update(requires=[chapter], support={}, chapters=[chapter])
            rows.append(row)
    long = deepcopy(rows[0])
    long.update(id='long-choice', kind='structured', marks=12,
                source={'type': 'past', 'qid': '9702_s23_22_q60'},
                scheme=[{'mark': 'M1', 'point': 'Synthetic method point.'} for _ in range(12)])
    rows.append(long)
    publish(root, rows)
    return rows


def answer_open(tutor, view):
    entry = f"{view['n']} pts=0" if view['kind'] == 'structured' else f"{view['n']}?"
    tutor.answer(entry)


def collect(tutor):
    result = []
    for _ in range(220):
        act = tutor.next()
        if act['activity'] == 'end':
            return result
        assert act['activity'] == 'questions'
        view = act['items'][0]
        pending = tutor.session['presented'][str(view['n'])]
        result.append(deepcopy(pending))
        answer_open(tutor, view)
    raise AssertionError('A counted topical set did not terminate')


@pytest.mark.parametrize('kind,command,stem,want', [
    ('mcq', 'Define', 'Define this.', 'mcq'), ('numeric', None, '', 'calculation'),
    ('expression', None, '', 'calculation'), ('short', 'Define', '', 'definition'),
    ('short', None, 'Define this term.', 'definition'),
    ('short', None, 'What is meant by this term?', 'definition'),
    ('short', 'Explain', 'Explain this result.', 'written'),
    ('short', None, 'Explain why the definition is useful.', 'written'),
    ('structured', 'Calculate', '', 'structured'), ('unrecognised', None, '', None),
])
def test_categories_follow_existing_kind_and_explicit_definition_commands(kind, command, stem, want):
    from tutorlib import topical_selection
    assert topical_selection.category({'kind': kind, 'command_word': command, 'stem': stem}) == want


def test_cross_chapter_count_is_exact_and_structured_marks_do_not_consume_extra_slots(tmp_path):
    root = bank_vault(tmp_path)
    rows = mixed_bank(root)
    tutor = tutor_for(root)
    result = tutor.start('topical', minutes=3, focus=[TARGET, OTHER, THIRD], topical_count=7)
    assert result.get('ok') is not False
    questions = collect(tutor)
    assert len(questions) == len(rows) == 7
    assert len({topicals.identity(q['inst']) for q in questions}) == 7
    assert {q['inst']['kind'] for q in questions} == {'mcq', 'structured'}
    assert {q['serving_chapter'] for q in questions[:3]} == {TARGET, OTHER, THIRD}
    assert not tutor.session.get('kcs_learned')


def test_type_filter_and_shortage_never_borrow_other_types_or_topics(tmp_path):
    root = bank_vault(tmp_path)
    mixed_bank(root)
    tutor = tutor_for(root)
    before = deepcopy(tutor.state)
    inventory = tutor.topical_choices([TARGET], ['structured'])
    assert inventory['available'] == 1 and inventory['counts']['structured'] == 1
    assert tutor.state == before and tutor.session is None
    result = tutor.start('topical', focus=[TARGET], topical_count=20, topical_types=['structured'])
    block = result['blocks'][0]
    assert block['question_count'] == 20 and len(block['question_queue']) == 1
    questions = collect(tutor)
    assert len(questions) == 1 and questions[0]['inst']['kind'] == 'structured'
    assert questions[0]['serving_chapter'] == TARGET


def test_duplicate_chapter_mapping_gets_one_slot_and_seeded_rounds_are_reproducible(tmp_path):
    root = bank_vault(tmp_path)
    shared = item()
    shared['topical'].update(chapters=[TARGET, OTHER], requires=[TARGET], support={})
    publish(root, [shared])
    tutor = tutor_for(root)
    tutor.log({'type': 'chapter_started', 'chapter': TARGET})
    assert tutor.topical_choices([TARGET, OTHER])['available'] == 1
    tutor.start('topical', focus=[TARGET, OTHER], topical_count=5)
    assert len(collect(tutor)) == 1
    from tutorlib import topical_selection
    pools = {'a': [{'source': {'qid': f'9702_s23_22_q{i}'}} for i in range(1, 8)],
             'b': [{'source': {'qid': '9702_s23_22_q10'}}]}
    before = deepcopy(pools)
    first = topical_selection.sample(pools, 5, random.Random(42))
    assert first == topical_selection.sample(pools, 5, random.Random(42))
    assert first != topical_selection.sample(pools, 5, random.Random(99))
    assert {q['chapter'] for q in first[:2]} == {'a', 'b'} and pools == before


def test_resume_keeps_planned_identity_order_and_revalidates_exclusions(tmp_path):
    root = bank_vault(tmp_path)
    mixed_bank(root)
    tutor = tutor_for(root)
    tutor.start('topical', focus=[TARGET, OTHER, THIRD], topical_count=6, topical_types=['mcq'])
    plan = deepcopy(tutor.session['blocks'][0]['question_queue'])
    first = tutor.next()['items'][0]
    assert topicals.identity(tutor.session['presented'][str(first['n'])]['inst']) == plan[0]['identity']
    answer_open(tutor, first)
    restored = tutor_for(root)
    assert restored.session['blocks'][0]['question_queue'] == plan
    blocked = plan[1]
    restored.log({'type': 'topical_exclude', 'identity': blocked['identity'], 'chapter': blocked['chapter'],
                  'missing': [], 'reason': 'Synthetic scoped exclusion.'})
    rest = collect(restored)
    identities = [topicals.identity(p['inst']) for p in rest]
    assert identities == [p['identity'] for p in plan[2:]]
    assert len(set(identities)) == len(identities)


def test_disclosed_alias_and_missing_prerequisites_remain_excluded(tmp_path):
    root = bank_vault(tmp_path)
    a, b = item(), item(id='blocked-source', source={'type': 'past', 'qid': '9702_s23_22_q90'})
    b['topical'].update(requires=[TARGET, THIRD], support={})
    publish(root, [a, b])
    tutor = tutor_for(root)
    assert tutor.topical_choices([TARGET])['available'] == 1
    tutor.start('topical', focus=[TARGET], topical_count=2)
    tutor.session['disclosed_item_ids'] = ['topical-one']
    assert collect(tutor) == []


@pytest.mark.parametrize('options', [
    {'topical_count': 0}, {'topical_count': -1}, {'topical_count': 201}, {'topical_count': True},
    {'topical_count': 1.5}, {'topical_count': '10'}, {'topical_types': []},
    {'topical_types': ['unknown']}, {'topical_types': 'mcq'}, {'topical_types': [True]},
])
def test_invalid_options_reject_without_replacing_or_writing_session(tmp_path, options):
    root = bank_vault(tmp_path)
    mixed_bank(root)
    tutor = tutor_for(root)
    tutor.start('review')
    before, events = deepcopy(tutor.session), list(tutor.vault.events())
    result = tutor.start('topical', focus=[TARGET], replace=True, **options)
    assert result['ok'] is False
    assert tutor.session == before and list(tutor.vault.events()) == events


def test_empty_matching_pool_cannot_start_and_legacy_budget_is_preserved(tmp_path):
    root = bank_vault(tmp_path)
    mixed_bank(root)
    tutor = tutor_for(root)
    assert tutor.start('topical', focus=[TARGET], topical_count=5, topical_types=['definition'])['ok'] is False
    assert tutor.session is None
    result = tutor.start('topical', focus=[TARGET], minutes=3)
    assert 'question_queue' not in result['blocks'][0]
    assert len(collect(tutor)) == 1


@pytest.mark.parametrize('saved_index', [-1, 0])
def test_archived_saved_attempt_stays_durable_without_becoming_an_unfiltered_extra_question(tmp_path, saved_index):
    root = bank_vault(tmp_path)
    rows = mixed_bank(root)
    tutor = tutor_for(root)
    tutor.start('review')
    _, saved = tutor._number(rows[saved_index], 'deferred_judgment', 'practice')
    saved['saved_work'] = 'Original saved working'
    tutor.session['deferred_judgments'] = [saved]
    assert tutor.postpone_saved_judgment()['ok']
    assert not tutor.end().get('error')
    archived = tutor.postponed_judgments()
    before = list(tutor.vault.events())
    tutor.start('topical', focus=[TARGET], topical_count=2, topical_types=['mcq'])
    questions = collect(tutor)
    assert len(questions) == 2 and all(q['inst']['kind'] == 'mcq' for q in questions)
    assert topicals.identity(rows[saved_index]) not in {topicals.identity(q['inst']) for q in questions}
    assert tutor.postponed_judgments() == archived
    assert list(tutor.vault.events())[:len(before)] == before
    tutor.end()
    tutor.start('review')
    assert tutor.session['deferred_judgments'][0]['saved_work'] == 'Original saved working'


@pytest.mark.parametrize('seed', range(12))
def test_overlapping_identity_does_not_steal_the_only_question_from_a_scarce_topic(seed):
    from tutorlib import topical_selection
    common = {'source': {'qid': '9702_s23_22_q1'}}
    unique = {'source': {'qid': '9702_s23_22_q2'}}
    result = topical_selection.sample({'large': [common, unique], 'scarce': [common]}, 2, random.Random(seed))
    assert {row['chapter'] for row in result} == {'large', 'scarce'}
    assert len({row['identity'] for row in result}) == 2


def test_filter_only_request_reserves_archived_work_and_does_not_restore_other_types(tmp_path):
    root = bank_vault(tmp_path)
    rows = mixed_bank(root)
    tutor = tutor_for(root)
    tutor.start('review')
    _, saved = tutor._number(rows[-1], 'deferred_judgment', 'practice')
    saved['saved_work'] = 'Saved structured attempt'
    tutor.session['deferred_judgments'] = [saved]
    assert tutor.postpone_saved_judgment()['ok']
    assert not tutor.end().get('error')
    archived = tutor.postponed_judgments()
    tutor.start('topical', focus=[TARGET], topical_types=['mcq'])
    questions = collect(tutor)
    assert questions and all(q['inst']['kind'] == 'mcq' for q in questions)
    assert tutor.postponed_judgments() == archived


def test_multi_chapter_inventory_shares_fresh_bank_proof(tmp_path, monkeypatch):
    from contextlib import contextmanager
    from tutorlib import topical_selection
    root = bank_vault(tmp_path)
    mixed_bank(root)
    tutor = tutor_for(root)
    original = tutor.packs.topicals.request
    authentications = []
    @contextmanager
    def tracked():
        with original() as outer:
            if outer:
                authentications.append(True)
            yield outer
    monkeypatch.setattr(tutor.packs.topicals, 'request', tracked)
    groups = topical_selection.pools(tutor.packs, tutor.state, [TARGET, OTHER, THIRD],
                                    disclosed={'unrelated'})
    assert sum(map(len, groups.values())) == 7
    assert authentications == [True]
