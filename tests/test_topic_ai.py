"""AI topic identification for untagged questions: images, strict replies, one retry, cache, absent AI."""
import json

import pytest

from solvability_support import TARGET, tutor_for, vault_with_flashcards
from tutorlib.asset_library import write_asset

KC_A = TARGET + '.1'
GOOD = {'kcs': [KC_A], 'confidence': 0.9, 'subtopics': ['Forces'], 'reason': 'Needs Newton second law.'}


class FakeAI:
    def __init__(self, *replies):
        self.replies, self.calls = list(replies), []

    def __call__(self, request):
        self.calls.append(request)
        return self.replies[min(len(self.calls), len(self.replies)) - 1]


@pytest.fixture
def t(tmp_path):
    return tutor_for(vault_with_flashcards(tmp_path))


def untagged(**kw):
    return {'id': 'untagged-1', 'kind': 'mcq', 'kcs': ['9702-unknown'], 'stem': 'A ball falls.', 'marks': 1,
            'difficulty': 3, 'options': {'A': 'a', 'B': 'b', 'C': 'c', 'D': 'd'}, 'answer': 'B', **kw}


def open_question(t, inst, unassisted=False):
    t.start('review')
    n, p = t._number({**inst, 'id': inst.get('id', 'q1')}, 'practice_set', 'practice', unassisted, None, None, TARGET)
    t.session['presented'][n] = p
    return int(n)


def test_untagged_question_is_identified_from_text_and_image(t):
    ref = 'Library/Courses/9702/Questions/Media/untagged.png'
    write_asset(t.vault.root, ref, b'png-bytes')
    t.topic_ai = ai = FakeAI(json.dumps(GOOD))
    out = t.check_solvable(open_question(t, untagged(image=ref, images=[ref])))
    assert out['status'] == 'solvable' and out['basis'] == 'ai_topics'
    req = ai.calls[0]
    assert set(req) >= {'purpose', 'course', 'system', 'schema', 'prompt', 'images'}
    assert req['purpose'] == 'topic_identification' and req['course'] == '9702' and req['cheapest'] is True
    assert req['schema']['required'] == ['kcs', 'confidence', 'subtopics', 'reason']
    assert req['images'] and req['images'][0].startswith('/') and req['images'][0].endswith('untagged.png')
    assert 'A ball falls.' in req['prompt'] and 'attached image' in req['prompt']
    cached = json.loads((t.vault.tutor / 'state' / 'topic-ai.json').read_text())
    assert list(cached.values())[0]['subtopics'] == ['Forces']


def test_invalid_reply_is_retried_once_then_reported(t):
    t.topic_ai = ai = FakeAI('not json', {'kcs': ['9702-1.1.1'], 'confidence': 1})
    out = t.check_solvable(open_question(t, untagged()))
    assert out['status'] == 'unverified' and out['skipped'] is False
    assert len(ai.calls) == 2 and 'rejected' in ai.calls[1]['prompt']
    assert 'could not be identified reliably' in out['message']
    assert str(1) in t.session['presented'] and not t.topical_exclusions()


def test_retry_can_succeed(t):
    t.topic_ai = ai = FakeAI('{"kcs": []}', json.dumps(GOOD))
    out = t.check_solvable(open_question(t, untagged()))
    assert out['status'] == 'solvable' and len(ai.calls) == 2


def test_cache_hit_does_not_call_ai_again(t):
    t.topic_ai = ai = FakeAI(json.dumps(GOOD))
    assert t.check_solvable(open_question(t, untagged()))['status'] == 'solvable'
    assert t.check_solvable(open_question(t, untagged()))['status'] == 'solvable'
    assert len(ai.calls) == 1
    again = tutor_for(t.vault.root)
    again.topic_ai = FakeAI('should not be asked')
    assert again.check_solvable(open_question(again, untagged()))['status'] == 'solvable'
    assert not again.topic_ai.calls


def test_absent_ai_says_so_and_keeps_the_question_open(t):
    out = t.check_solvable(open_question(t, untagged()))
    assert out['status'] == 'topic_pending' and 'AI' in out['message'] and out['skipped'] is False
    assert str(1) in t.session['presented'] and not t.topical_exclusions()


def test_unavailable_ai_is_not_cached(t):
    def boom(request):
        raise RuntimeError('offline')
    t.topic_ai = boom
    assert t.check_solvable(open_question(t, untagged()))['status'] == 'topic_pending'
    t.topic_ai = FakeAI(json.dumps(GOOD))
    assert t.check_solvable(open_question(t, untagged()))['status'] == 'solvable'
