"""Consecutive independent answers are required before retiring a misconception."""
import copy
import json
import random
from datetime import datetime

import pytest

from fixtures import make_vault
from tutorlib import policy, session, store

KC = '9702-2.1.1'
NOW = datetime.fromisoformat('2026-09-29T17:00:00+08:00')


def make_tutor(tmp_path):
    return session.Tutor(store.Vault(make_vault(tmp_path)), rng=random.Random(0), now=lambda: NOW)


def respond(tutor, choice, hinted=False):
    item = next(item for item in tutor.packs.items_for(KC) if item['id'] == '9702-2.1-i01')
    item = {**item, 'shuffle': False}
    question = tutor._present(item, 'practice', None)
    if hinted:
        tutor.hint(question['n'])
    return tutor.answer(f"{question['n']}{choice}")['results'][0]


@pytest.mark.parametrize('interruption', ['C', '?'])
def test_wrong_answer_breaks_misconception_success_streak(tmp_path, interruption):
    tutor = make_tutor(tmp_path)
    tutor.start('review', minutes=10)
    assert respond(tutor, 'A')['correct'] is False  # diagnosed m1
    assert respond(tutor, 'B')['correct'] is True
    assert tutor.state['kcs'][KC]['mis_streak']['m1'] == 1
    assert respond(tutor, interruption)['correct'] is False  # no diagnosed misconception
    assert respond(tutor, 'B')['correct'] is True

    kc = tutor.state['kcs'][KC]
    assert kc['active_misconceptions'] == ['m1']
    assert kc['mis_streak']['m1'] == 1
    assert policy.default_method(tutor.packs.kc(KC), kc) == 'refutation'

    # Replay and JSON cache reload must preserve the same still-active misconception.
    before = copy.deepcopy(tutor.state)
    history = {p: p.read_bytes() for p in tutor.vault._event_files()}
    tutor.rebuild()
    assert tutor.state == before
    restored = session.Tutor(tutor.vault, now=lambda: NOW)
    assert restored.state == before
    assert {p: p.read_bytes() for p in tutor.vault._event_files()} == history

    # A further consecutive independent success does resolve it.
    assert respond(restored, 'B')['correct'] is True
    assert restored.state['kcs'][KC]['active_misconceptions'] == []


def test_another_idea_does_not_break_a_local_misconception_streak(tmp_path):
    tutor = make_tutor(tmp_path)
    tutor.start('review', minutes=10)
    respond(tutor, 'A')
    respond(tutor, 'B')
    other = next(item for item in tutor.packs.items_for('9702-2.1.4')
                 if item['id'] == '9702-2.1-i03')
    question = tutor._present(other, 'practice', None)
    assert tutor.answer(f"{question['n']}?")['results'][0]['correct'] is False
    assert tutor.state['kcs'][KC]['mis_streak']['m1'] == 1
    respond(tutor, 'B')
    assert tutor.state['kcs'][KC]['active_misconceptions'] == []


def test_assisted_answers_cannot_complete_an_independent_success_streak(tmp_path):
    tutor = make_tutor(tmp_path)
    tutor.start('review', minutes=10)
    respond(tutor, 'A')
    respond(tutor, 'B')
    respond(tutor, 'B', hinted=True)
    respond(tutor, 'B', hinted=True)
    assert tutor.state['kcs'][KC]['active_misconceptions'] == ['m1']
    assert tutor.state['kcs'][KC]['mis_streak']['m1'] == 0

def test_old_cache_replays_interrupted_misconception_streak(tmp_path):
    tutor = make_tutor(tmp_path)
    tutor.start('review', minutes=10)
    for choice in ('A', 'B', 'C', 'B'):
        respond(tutor, choice)
    stale = copy.deepcopy(tutor.state)
    stale['model_version'] = '1.1.8'
    stale['kcs'][KC]['active_misconceptions'] = []
    stale['kcs'][KC]['mis_streak']['m1'] = 2
    tutor.state_path.write_text(json.dumps(stale))
    history = {p: p.read_bytes() for p in tutor.vault._event_files()}

    restored = session.Tutor(tutor.vault, now=lambda: NOW)
    assert restored.state['kcs'][KC]['active_misconceptions'] == ['m1']
    assert restored.state['kcs'][KC]['mis_streak']['m1'] == 1
    assert {p: p.read_bytes() for p in tutor.vault._event_files()} == history
