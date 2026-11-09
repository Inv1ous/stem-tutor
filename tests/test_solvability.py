"""'Can I solve this?': started-topic semantics, adapted prompts, givens, auto-skip, AI topic fallback."""
import json

import pytest

from solvability_support import (OTHER, THIRD, TARGET, register_bank, source_item, tutor_for, vault_with_flashcards)
from tutorlib import prompts, solvability

KC_A, KC_B, KC_C = TARGET + '.1', OTHER + '.1', THIRD + '.1'


@pytest.fixture
def t(tmp_path):
    return tutor_for(vault_with_flashcards(tmp_path))


def start(t, *chapters):
    for c in chapters:
        t.log({'type': 'chapter_started', 'chapter': c})


def test_started_topics_not_numbering_later_known_earlier_unknown(t):
    start(t, THIRD)                                   # 4.1 known, 2.1 and 3.1 never started
    later = solvability.assess(t.state, t.packs, {'kcs': [KC_C]})
    earlier = solvability.assess(t.state, t.packs, {'kcs': [KC_A]})
    assert later['status'] == 'solvable' and later['missing'] == []
    assert earlier['status'] in ('adapted', 'skipped') and earlier['missing_topics'] == [TARGET]


def test_started_set_is_chapters_completed_and_answered_kcs(t):
    t.state['kcs'][KC_B] = {'n': 2}
    t.state['completed_chapters'] = [TARGET]
    assert solvability.assess(t.state, t.packs, {'kcs': [KC_A, KC_B]})['status'] == 'solvable'


def test_adapted_prompt_names_answerable_parts_without_new_questions(t):
    start(t, TARGET)
    item = {'kcs': [KC_A, KC_C], 'answer': {'value': 7.5}, 'parts': [
        {'label': 'a', 'kcs': [KC_A]}, {'label': 'b', 'kcs': [KC_C]}, {'label': 'c', 'kcs': [KC_A]}]}
    out = solvability.assess(t.state, t.packs, item)
    assert out['status'] == 'adapted' and out['given'] == [] and out['skipped'] is False
    assert out['adapted_prompt'].startswith('Answer parts (a) and (c) now; (b) needs')
    assert out['missing_topics'] == [THIRD] and out['missing'] == [t.packs.subtopics[THIRD]['title']]
    assert [p['state'] for p in out['parts']] == ['ok', 'blocked', 'ok']


def test_given_hint_rescues_a_part_and_is_marked_assisted(t):
    start(t, TARGET)
    item = {'kcs': [KC_A, KC_B], 'parts': [{'label': 'a', 'kcs': [KC_A]}, {'label': 'b', 'kcs': [KC_B]}],
            'answer': {'value': 12.5}}
    out = solvability.assess(t.state, t.packs, item)
    assert out['status'] == 'adapted' and out['assisted'] is True
    assert out['given'] and out['given'][0].startswith('Given (') and 'F = ma' in out['given'][0]
    assert 'assisted' in out['adapted_prompt'] and [p['state'] for p in out['parts']] == ['ok', 'given']


def test_given_never_repeats_the_questions_key(t):
    start(t, TARGET)
    item = {'kcs': [KC_B], 'kind': 'expression', 'answer': {'expr': 'F = ma'}}
    out = solvability.assess(t.state, t.packs, item)
    assert out['status'] == 'skipped' and out['given'] == []


def test_unassisted_questions_get_no_givens(t):
    start(t, TARGET)
    out = solvability.assess(t.state, t.packs, {'kcs': [KC_B]}, unassisted=True)
    assert out['status'] == 'skipped'
    assert solvability.assess(t.state, t.packs, {'kcs': [KC_B]})['status'] == 'adapted'


def test_no_answerable_part_and_no_given_is_skipped(t):
    start(t, TARGET)
    out = solvability.assess(t.state, t.packs, {'kcs': [KC_C]})
    assert out['status'] == 'skipped' and out['skipped'] is True and out['adapted_prompt'] is None
    assert 'which you have not started' in out['message']


def test_untagged_item_is_unverified_and_needs_topic(t):
    out = solvability.assess(t.state, t.packs, {'kcs': [], 'stem': 'x'})
    assert out['status'] == 'unverified' and out['needs_topic'] is True
    assert solvability.assess(t.state, t.packs, {'kcs': ['9702-unknown']})['needs_topic'] is True


def test_unmapped_part_is_not_guessed_blocked(t):
    start(t, TARGET)
    out = solvability.assess(t.state, t.packs, {'kcs': [KC_A, KC_C], 'parts': [
        {'label': 'a', 'kcs': [KC_A]}, {'label': 'b', 'kcs': []}, {'label': 'c', 'kcs': [KC_C]}]})
    assert out['adapted_prompt'].startswith('Answer parts (a) and (b) now')


# ---------- session: the "Can I solve this?" action ----------
def open_question(t, inst, block='practice_set', **kw):
    t.start('review')
    n, p = t._number({**inst, 'id': inst.get('id', 'q1')}, block, 'practice', kw.get('unassisted', False), None, None,
                     kw.get('chapter', TARGET))
    t.session['presented'][n] = p
    return int(n)


def base_inst(**kw):
    return {'id': 'q1', 'kind': 'mcq', 'kcs': [KC_C], 'stem': 'Which?', 'marks': 1, 'difficulty': 3,
            'options': {'A': 'a', 'B': 'b', 'C': 'c', 'D': 'd'}, 'answer': 'B', **kw}


def test_check_solvable_skips_logs_and_preserves_history(t):
    start(t, TARGET)
    n = open_question(t, base_inst(source={'type': 'source_verified', 'ref': 'x'}, source_verified=True))
    out = t.check_solvable(n)
    assert out['status'] == 'skipped' and out['skipped'] is True and out['missing'] and out['topic']
    assert str(n) not in t.session['presented']
    records = t.topical_exclusions()
    assert records and records[0]['identity'] == 'q1' and records[0]['missing'] == [THIRD]
    assert any(e['type'] == 'topical_exclude' for e in t.vault.events())     # history is an event, never deleted
    assert t.restore_topical('q1', TARGET)['ok'] and not t.topical_exclusions()


def test_check_solvable_adapted_marks_attempt_assisted_without_key(t):
    start(t, TARGET)
    n = open_question(t, base_inst(kcs=[KC_B]))
    out = t.check_solvable(n)
    assert out['status'] == 'adapted' and out['given'] and out['n'] == n
    p = t.session['presented'][str(n)]
    assert p['hinted'] is True and p['support_given'] == out['given']
    assert 'answer' not in json.dumps({k: v for k, v in out.items() if k != 'parts'})


def test_lesson_questions_are_never_auto_skipped(t):
    start(t, TARGET)
    n = open_question(t, base_inst(), block='learn')
    out = t.check_solvable(n)
    assert out['status'] == 'unverified' and str(n) in t.session['presented'] and not t.topical_exclusions()


def test_solvable_returns_all_contract_keys(t):
    start(t, TARGET)
    n = open_question(t, base_inst(kcs=[KC_A]))
    out = t.check_solvable(n)
    assert out['status'] == 'solvable'
    for key in ('status', 'message', 'missing', 'given', 'adapted_prompt', 'topic', 'skipped'):
        assert key in out


# ---------- AI topic identification ----------
class FakeAI:
    def __init__(self, reply):
        self.reply, self.calls = reply, []

    def __call__(self, request):
        self.calls.append(request)
        return self.reply


def untagged(**kw):
    return base_inst(kcs=['9702-unknown'], id='untagged-1', **kw)


def test_no_ai_means_topic_pending_and_question_stays_open(t):
    n = open_question(t, untagged())
    out = t.check_solvable(n)
    assert out['status'] == 'topic_pending' and 'AI' in out['message'] and out['skipped'] is False
    assert str(n) in t.session['presented'] and not t.topical_exclusions()


def test_ai_identifies_topics_validates_course_and_caches(t, tmp_path):
    start(t, TARGET)
    ai = t.topic_ai = FakeAI(json.dumps({'kcs': [KC_A], 'confidence': 0.9, 'subtopics': ['Forces'],
                                         'reason': 'The question needs Newton\'s second law.'}))
    n = open_question(t, untagged(stem='A ball falls.'))
    first = t.check_solvable(n)
    assert first['status'] == 'solvable' and first['topic'] == [t.packs.kcs[KC_A]['title']]
    assert len(ai.calls) == 1
    req = ai.calls[0]
    assert KC_A in req['prompt'] and 'A ball falls.' in req['prompt'] and req['cheapest'] is True
    assert req['images'] == [] and 'attached image' not in req['prompt']
    n2 = open_question(t, untagged(stem='A ball falls.'))                       # same question again: cache hit
    assert t.check_solvable(n2)['status'] == 'solvable' and len(ai.calls) == 1
    again = tutor_for(t.vault.root)                                              # cache survives a restart
    again.topic_ai = FakeAI('should not be asked')
    start(again, TARGET)
    n3 = open_question(again, untagged(stem='A ball falls.'))
    assert again.check_solvable(n3)['status'] == 'solvable' and not again.topic_ai.calls


def test_ai_unknown_or_foreign_ids_are_rejected_and_not_asked_twice(t):
    t.topic_ai = ai = FakeAI({'kcs': ['9701-1.1.1'], 'confidence': 1, 'subtopics': ['Forces'], 'reason': 'x'})
    n = open_question(t, untagged())
    assert t.check_solvable(n)['status'] == 'unverified'
    n2 = open_question(t, untagged())
    assert t.check_solvable(n2)['status'] == 'unverified' and len(ai.calls) == 2   # one retry, then cached


def test_ai_failure_is_pending_and_not_cached(t):
    def boom(request):
        raise RuntimeError('offline')
    t.topic_ai = boom
    n = open_question(t, untagged())
    assert t.check_solvable(n)['status'] == 'topic_pending'
    t.topic_ai = FakeAI({'kcs': [KC_A], 'confidence': 0.8, 'subtopics': ['Forces'], 'reason': 'x'})
    assert t.check_solvable(open_question(t, untagged()))['status'] in ('solvable', 'adapted', 'skipped')
    assert len(t.topic_ai.calls) == 1


def test_ai_prompt_notes_image_and_attaches_only_registered_files(t):
    root = t.vault.root
    from tutorlib.asset_library import write_asset
    ref = 'Library/Courses/9702/Questions/Media/untagged.png'
    write_asset(root, ref, b'png-bytes')
    t.topic_ai = ai = FakeAI({'kcs': [KC_C], 'confidence': 0.7, 'subtopics': ['Waves'], 'reason': 'x'})
    n = open_question(t, untagged(image=ref, images=[ref]))
    out = t.check_solvable(n)
    assert out['topic'] == [t.packs.kcs[KC_C]['title']]
    assert ai.calls[0]['images'] and ai.calls[0]['images'][0].endswith('untagged.png')
    assert 'attached image' in ai.calls[0]['prompt']


def test_prompt_helpers_are_strict():
    ids = {'a', 'b'}
    good = {'kcs': ['a'], 'confidence': 0.8, 'subtopics': ['Forces'], 'reason': 'Needs the second law.'}
    assert prompts.parse_topic_reply('```json\n' + json.dumps(good) + '\n```', ids)['kcs'] == ['a']
    assert prompts.parse_topic_reply(good, ids)['subtopics'] == ['Forces']
    assert prompts.parse_topic_reply({**good, 'kcs': ['a', 'z']}, ids) is None
    assert prompts.parse_topic_reply({**good, 'confidence': 2}, ids) is None
    assert prompts.parse_topic_reply({k: v for k, v in good.items() if k != 'subtopics'}, ids) is None
    assert prompts.parse_topic_reply({**good, 'subtopics': []}, ids) is None
    assert prompts.parse_topic_reply({k: v for k, v in good.items() if k != 'reason'}, ids) is None
    assert prompts.parse_topic_reply({**good, 'reason': '  '}, ids) is None
    assert prompts.parse_topic_reply('nope', ids) is None


def test_unassisted_untagged_question_is_identified_by_ai(t):
    start(t, TARGET)
    t.topic_ai = ai = FakeAI({'kcs': [KC_A], 'confidence': 0.9, 'subtopics': ['Forces'], 'reason': 'x'})
    n = open_question(t, untagged(stem='A ball falls.'), unassisted=True)
    out = t.check_solvable(n)
    assert out['status'] == 'solvable' and out['basis'] == 'ai_topics' and len(ai.calls) == 1
