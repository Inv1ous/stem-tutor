"""Practice mode: course/module/chapter scope, topical + source-verified pools; source items count towards mastery."""
import copy
import json

import pytest

from solvability_support import (OTHER, THIRD, TARGET, register_bank, source_item, tutor_for, vault_with_flashcards, NOW)
from test_topicals import item as topical_item, publish
from tutorlib import model, policy

KC_A, KC_B, KC_C = TARGET + '.1', OTHER + '.1', THIRD + '.1'
SCHEME = 'Library/SourcePractice/Media/' + 'c' * 64 + '.png'


def bank(root, *extra):
    items = [source_item('S-mcq', 'mcq', [KC_A], answer='B'),
             source_item('S-struct', 'structured', [KC_A], marks=3, scheme_media=[SCHEME]),
             source_item('S-late', 'mcq', [KC_C], answer='A'),
             source_item('S-held', 'mcq', [KC_A], held=True, answer='A'),
             source_item('S-notag', 'mcq', [], answer='A'),
             source_item('S-nokey', 'mcq', [KC_A], answer=None), *extra]
    register_bank(root, items)


@pytest.fixture
def root(tmp_path):
    r = vault_with_flashcards(tmp_path)
    bank(r)
    return r


def served(t, limit=20):
    out = []
    while len(out) < limit:
        act = t.next()
        if act.get('activity') != 'questions':
            break
        for q in act['items']:
            out.append((q['n'], t.session['presented'][str(q['n'])]['item']))
            t.session['presented'].pop(str(q['n']))
    return out


# ---------- planning ----------
def test_plan_resolves_scope(root):
    t = tutor_for(root)
    plan = lambda **o: policy.plan_session(t.state, t.packs, NOW, 30, 'practice', o.pop('focus', None), practice=o)
    course = plan(course='9702', scope='course')
    assert course[0]['kind'] == 'practice_set' and course[0]['chapters'] == [TARGET, OTHER, THIRD]
    assert plan(course='9702', scope='course', started_only=True) == []         # nothing started yet
    t.log({'type': 'chapter_started', 'chapter': OTHER})
    assert plan(course='9702', scope='course', started_only=True)[0]['chapters'] == [OTHER]
    assert plan(focus=[TARGET, THIRD], scope='chapters')[0]['chapters'] == [TARGET, THIRD]
    assert plan(focus=['9702-2'], scope='module', course='9702')[0]['chapters'] == [TARGET, OTHER, THIRD]
    assert plan(focus=[KC_C], scope='chapters')[0]['chapters'] == [THIRD]
    assert plan(course='9701', scope='course') == []
    assert plan(course='9702', scope='course', sources=['bogus']) == []


def test_start_validates_options(root):
    t = tutor_for(root)
    assert not t.start('practice', course='9702', scope='galaxy')['ok']
    assert not t.start('practice', course='9702', sources=['x'])['ok']
    assert not t.start('practice', course='9702', count=0)['ok']
    assert not t.start('review', course='9702')['ok']
    assert not t.start('practice', course='9702', started_only=True)['ok']       # no started topics: honest error


# ---------- serving ----------
def test_source_only_practice_never_serves_held_untagged_or_keyless(root):
    t = tutor_for(root)
    out = t.start('practice', focus=[TARGET, THIRD], scope='chapters', sources=['source_verified'], count=20)
    assert out['blocks'][0]['available'] == 3
    ids = {i for _, i in served(t)}
    assert ids == {'S-mcq', 'S-struct', 'S-late'}
    assert not ids & {'S-held', 'S-notag', 'S-nokey'}


def test_course_scope_mixes_topical_and_source(root):
    publish(root, [topical_item()])
    t = tutor_for(root)
    t.start('practice', course='9702', scope='course', count=10)
    queue = t.session['blocks'][0]['question_queue']
    assert {e['source'] for e in queue} == {'topical', 'source_verified'}
    assert queue[0]['source'] != queue[1]['source']                              # interleaved
    assert t.session['practice']['course'] == '9702' and t.session['mode'] == 'practice'


def test_started_only_filters_source_pool_by_started_topics(root):
    t = tutor_for(root)
    t.log({'type': 'chapter_started', 'chapter': THIRD})                          # only the LATER chapter is started
    out = t.start('practice', course='9702', scope='course', sources=['source_verified'], started_only=True, count=9)
    assert [e['id'] for e in out['blocks'][0]['question_queue']] == ['S-late']
    assert {i for _, i in served(t)} == {'S-late'}


def test_count_and_unseen_first(root):
    t = tutor_for(root)
    t.state.setdefault('source_seen', {})['S-mcq'] = '2026-10-01T00:00:00+08:00'
    t.start('practice', focus=[TARGET], scope='chapters', sources=['source_verified'], count=1)
    assert t.session['blocks'][0]['question_queue'][0]['id'] == 'S-struct'


def test_open_practice_serves_topical_that_needs_unstarted_topics(root):
    publish(root, [topical_item(id='needs-3-1', topical={**topical_item()['topical'], 'support': {}})])
    t = tutor_for(root)
    t.log({'type': 'chapter_started', 'chapter': TARGET})
    strict = t.start('practice', focus=[TARGET], scope='chapters', sources=['topical'], count=3, started_only=True)
    assert strict['ok'] is False and 'No eligible' in strict['error']             # needs 3.1, which is not started
    t.start('practice', focus=[TARGET], scope='chapters', sources=['topical'], count=3)
    assert [i for _, i in served(t)] == ['needs-3-1']                              # open practice: Can-I-solve-this decides


# ---------- mastery credit ----------
def snapshot(t):
    return json.dumps({k: t.state[k] for k in ('kcs', 'items_seen', 'traits', 'gaps', 'started_chapters')
                       if k in t.state}, sort_keys=True, default=str)


def test_source_mcq_is_graded_and_counts_towards_mastery(root):
    t = tutor_for(root)
    t.start('practice', focus=[TARGET], scope='chapters', sources=['source_verified'], count=1)
    t.session['blocks'][0]['question_queue'] = [e for e in t.session['blocks'][0]['question_queue'] if e['id'] == 'S-mcq']
    act = t.next()
    n = act['items'][0]['n']
    assert act['items'][0]['images'] and 'answer' not in act['items'][0]
    res = t.answer(f'{n}B3')['results'][0]
    assert res['correct'] is True and res['marks'] == 1
    events = [e for e in t.vault.events() if e.get('item') == 'S-mcq']
    assert [e['type'] for e in events] == ['answer']
    assert events[0]['source_verified'] is True and 'mastery_credit' not in events[0] and events[0]['kcs'] == [KC_A]
    assert any(e['type'] == 'chapter_started' and e['chapter'] == TARGET for e in t.vault.events())
    k = t.state['kcs'][KC_A]
    assert k['n'] == 1 and k['theta'] > 0 and k['fsrs']                         # mastery moved
    assert t.state['items_seen']['S-mcq'] and t.state['source_seen']['S-mcq']
    fresh = tutor_for(root)                                                        # same after a full refold
    assert snapshot(fresh) == snapshot(t) and 'S-mcq' in fresh.state['source_seen']


def test_source_structured_uses_whole_rubric_manual_award_with_credit(root):
    t = tutor_for(root)
    t.start('practice', focus=[TARGET], scope='chapters', sources=['source_verified'], count=2)
    t.session['blocks'][0]['question_queue'] = [e for e in t.session['blocks'][0]['question_queue'] if e['id'] == 'S-struct']
    act = t.next()
    view = act['items'][0]
    assert view['manual_marking'] is True
    n = view['n']
    rub = t.whole_rubric(n, 'My written working for the structured question.')
    assert 'error' not in rub, rub
    assert rub['media'] == [SCHEME] and rub['max_marks'] == 3
    res = t.answer(f'{n} = My written working for the structured question.',
                   manual_awards={n: {'earned_marks': 2, 'ticket': rub['ticket']}})['results'][0]
    assert res.get('event') and res['score'] == pytest.approx(2 / 3, abs=0.01)
    types = [e['type'] for e in t.vault.events() if e.get('item') == 'S-struct']
    assert types == ['answer']
    assert t.state['kcs'][KC_A]['n'] == 1 and 'S-struct' in t.state['source_seen']


def test_older_source_answer_events_still_give_no_mastery_credit():
    state = model.new_state()
    before = copy.deepcopy(state)
    model.apply(state, {'type': 'source_answer', 'item': 'S-old', 'ts': '2026-10-01T00:00:00+08:00', 'kcs': [KC_A],
                        'grade': {'correct': True, 'score': 1.0}, 'mastery_credit': False, 'source_verified': True})
    assert state['source_seen'] == {'S-old': '2026-10-01T00:00:00+08:00'}
    assert state['kcs'] == before['kcs'] and state['items_seen'] == before['items_seen']


def test_old_modes_still_plan_unchanged(root):
    t = tutor_for(root)
    assert t.start('review')['blocks'] is not None
    assert policy.plan_session(t.state, t.packs, NOW, 30, 'topical', [TARGET]) == []
    assert t.start('test', focus=[TARGET], replace=True)['blocks'][0]['kind'] == 'sweep'
