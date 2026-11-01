"""Validator-accepted images-only source loses its first-page follow-up attachment."""
import copy
import json
import random
from datetime import datetime

import pytest

from build.publish import _validate_pack_assets
from fixtures import GRAPH, make_vault
from library_assets import copy_to_vault
from test_validate import V, good_pack
from tutor_app import prompts
from tutorlib import session, store

PAGES = ['Library/Courses/9701/Questions/Media/9701_m24_12_q1-423c4ef583aa76cf.png',
         'Library/Courses/9701/Questions/Media/9701-periodic-table-2025-2027-a03a57bd6adb1bdf.png']
KC = '9702-2.1.1'
NOW = datetime.fromisoformat('2026-11-01T21:30:00+08:00')


@pytest.mark.parametrize('restart', [False, True])
def test_public_images_only_source_retains_same_ask_attachment_after_answer(tmp_path, restart):
    root = make_vault(tmp_path)
    for page in PAGES:
        copy_to_vault(page, root)
    pack = good_pack()
    for item in pack['items']:
        if KC in item['kcs']:
            item.pop('image', None)
            item['images'] = list(PAGES)
    assert V.validate(pack, GRAPH) == []
    _validate_pack_assets(pack, root)
    source = root / '.tutor/packs/v1/specs/9702/packs/9702-2.1.json'
    source.write_text(json.dumps(pack))
    (root / '.tutor/packs/v1/papers.json').write_text('{"papers": []}')
    source_before = source.read_bytes()
    tutor = session.Tutor(store.Vault(root), rng=random.Random(0), now=lambda: NOW, one_at_a_time=True)
    tutor.start('test', 20, [KC])
    question = tutor.next()['items'][0]
    pending = tutor.session['presented'][str(question['n'])]
    assert 'image' not in pending['inst'] and pending['inst']['images'] == PAGES
    assert question['image'] == PAGES[0] and question['images'] == PAGES
    first = prompts.focus_image(tutor)
    assert first == root / PAGES[0] and first.read_bytes()
    result = tutor.answer(f"{question['n']}{pending['inst']['answer']}4")['results'][0]
    assert result['correct'] and not tutor.session['presented']
    recent = copy.deepcopy(tutor.session['recent'][-1])
    assert recent['image'] is None and 'images' not in recent
    answer = next(e for e in tutor.vault.events() if e['id'] == result['event'])
    assert 'image' not in answer['question'] and answer['question']['images'] == PAGES
    before_events = {p.name: p.read_bytes() for p in (root / '.tutor/events').glob('*.jsonl')}
    if restart:
        tutor = session.Tutor(store.Vault(root), rng=random.Random(0), now=lambda: NOW, one_at_a_time=True)
    session_before = copy.deepcopy(tutor.session)
    state_before = copy.deepcopy(tutor.state)
    focused = prompts.focus_image(tutor)
    assert source.read_bytes() == source_before
    assert {p.name:p.read_bytes() for p in (root / '.tutor/events').glob('*.jsonl')} == before_events
    assert tutor.session == session_before and tutor.state == state_before
    assert tutor.session['recent'][-1] == recent
    assert focused == first, 'Just-marked Ask lost the supported first-image attachment retained by the exact event'
    assert prompts.focus_page_count(tutor) == 2



@pytest.mark.parametrize('event_id,question', [
    (None, {'images': PAGES}),
    ('unknown', {'images': PAGES}),
    ('focused', None),
    ('focused', 'legacy question text'),
    ('focused', []),
    ('focused', {'images': 'not a page list'}),
    ('focused', {'images': [None, 3], 'image': []}),
])
def test_recent_missing_unknown_or_malformed_event_never_guesses_attachment(event_id, question):
    from types import SimpleNamespace
    recent = {'event': event_id, 'image': None, 'response': "don't know", 'answer': '',
              'explanation': None, 'answer_withheld': True}
    history = [{'id': 'focused', 'question': question},
               {'id': 'newer', 'question': {'image': PAGES[0], 'images': PAGES}}]
    calls = []

    def events():
        calls.append('read')
        return iter(history)
    tutor = SimpleNamespace(session={'recent': [recent]}, vault=SimpleNamespace(events=events))
    before = copy.deepcopy((tutor.session, history))
    focused = prompts.focus(tutor)
    assert not focused.get('image') and not focused.get('images')
    assert focused['response'] == "don't know" and focused['answer'] == ''
    assert focused['explanation'] is None and focused['answer_withheld']
    assert (tutor.session, history) == before
    assert len(calls) <= 1
    if event_id is None:
        assert not calls


@pytest.mark.parametrize('attachment', [{'images': PAGES}, {'image': PAGES[1]},
                                      {'image': PAGES[1], 'images': PAGES}])
def test_recent_exact_event_restores_only_missing_attachment_fields(attachment):
    from types import SimpleNamespace
    recent = {'n': 7, 'event': 'focused', 'image': None, 'response': "don't know", 'answer': '',
              'explanation': None, 'correct': False, 'conf': 1, 'answer_withheld': True}
    history = [{'id': 'focused', 'question': {**attachment, 'stem': 'unrelated replacement',
                'answer': 'SECRET', 'explanation': 'SECRET', 'correct': True}},
               {'id': 'newer', 'question': {'image': 'unrelated.png', 'images': ['unrelated.png']}}]
    tutor = SimpleNamespace(session={'recent': [recent]}, vault=SimpleNamespace(events=lambda: iter(history)))
    before = copy.deepcopy((tutor.session, history))
    focused = prompts.focus(tutor)
    assert focused == {**recent, **attachment, 'open': False}
    assert (tutor.session, history) == before
    if 'images' in focused:
        focused['images'].append('caller-edit.png')
        assert history[0]['question']['images'] == PAGES


@pytest.mark.parametrize('recent', [
    {'image': PAGES[1], 'images': PAGES},
    {'images': PAGES},
    {'image': PAGES[0]},
])
def test_existing_recent_attachment_precedence_skips_history(recent):
    from types import SimpleNamespace

    def forbidden():
        raise AssertionError('Existing attachments must not trigger historical inference')
    tutor = SimpleNamespace(session={'recent': [recent]}, vault=SimpleNamespace(events=forbidden))
    assert prompts.focus(tutor) == {**recent, 'open': False}


def test_highest_open_focus_still_precedes_recent_recovery():
    from types import SimpleNamespace

    def forbidden():
        raise AssertionError('An open question must not trigger recent attachment lookup')
    newest = {'stem': 'current question', 'images': [PAGES[1]]}
    tutor = SimpleNamespace(session={'presented': {'2': {'inst': {'image': PAGES[0]}}, '9': {'inst': newest}},
                                    'recent': [{'event': 'older', 'image': None}]},
                            vault=SimpleNamespace(events=forbidden))
    focused = prompts.focus(tutor)
    assert focused['n'] == 9 and focused['open'] and focused['images'] == [PAGES[1]]
