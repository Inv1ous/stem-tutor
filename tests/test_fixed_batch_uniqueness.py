"""Normal fixed-question batches must not count a staged source twice."""
import copy
import json
import random
from datetime import datetime, timedelta

import pytest

from fixtures import PACK, make_vault
from tutorlib import session, store, topicals

KC, OTHER_KC = '9702-2.1.1', '9702-2.1.4'


def _setup(tmp_path, aliases=False, sequential=False):
    root = make_vault(tmp_path)
    path = root / '.tutor/packs/v1/specs/9702/packs/9702-2.1.json'
    pack = json.loads(path.read_text())
    item = copy.deepcopy(pack['items'][0])
    item.update(kcs=[KC, OTHER_KC], source={'type': 'past', 'qid': '9702_s23_12_q1'})
    pack['items'] = [item]
    if aliases:
        item['kcs'] = [KC]
        alias = copy.deepcopy(item)
        alias.update(id='9702-2.1-i51', kcs=[OTHER_KC])
        pack['items'].append(alias)
    path.write_text(json.dumps(pack))
    clock = [datetime.fromisoformat('2026-09-29T17:00:00+08:00')]
    tutor = session.Tutor(store.Vault(root), rng=random.Random(0), now=lambda: clock[0], one_at_a_time=sequential)
    return tutor, clock, path


def _answer_current_batch(tutor, activity):
    while True:
        tutor.answer(', '.join(f"{q['n']}B4" for q in activity['items']))
        if not tutor.session.get('queue'):
            return
        activity = tutor.next()


@pytest.mark.parametrize('mode', ['test', 'review', 'practice', 'exit'])
@pytest.mark.parametrize('aliases', [False, True])
@pytest.mark.parametrize('sequential', [False, True])
@pytest.mark.parametrize('restart', [False, True])
def test_public_normal_fixed_batch_records_one_exposure_per_canonical_source(tmp_path, mode, aliases, sequential, restart):
    tutor, clock, path = _setup(tmp_path, aliases, sequential)
    source = path.read_bytes()
    if mode != 'test':
        tutor.log({'type': 'answer', 'item': 'earlier-learning', 'kcs': [KC, OTHER_KC], 'subject': 'phys',
                   'difficulty': 3, 'conf': 3, 'hinted': False, 'marks': 1,
                   'grade': {'correct': True, 'score': 1.0, 'error': None, 'misconception': None}})
        if mode == 'review':
            clock[0] += timedelta(days=30)
    tutor.start('test' if mode == 'test' else 'review', 20, [KC, OTHER_KC])
    activity = tutor.next()
    if mode == 'exit':
        assert activity['block'] == 'practice'
        _answer_current_batch(tutor, activity)
        activity = tutor.next()
    assert activity['block'] == {'test': 'sweep'}.get(mode, mode)
    staged = [*tutor.session['presented'].values(), *tutor.session.get('queue', {}).values()]
    identities = [topicals.identity(p['inst']) or p['item'] for p in staged]
    if mode == 'test':
        assert tutor.session['blocks'][0]['asked'] == {staged[0]['item']: KC}
    historical = {p: p.read_bytes() for p in (tutor.vault.tutor / 'events').glob('*.jsonl')}
    if restart:
        saved = json.loads(json.dumps({p['item']: p['inst'] for p in staged}))  # saved metadata tuples become JSON lists
        tutor = session.Tutor(store.Vault(tutor.vault.root), rng=random.Random(0), now=lambda: clock[0],
                              one_at_a_time=sequential)
        reopened = [*tutor.session['presented'].values(), *tutor.session.get('queue', {}).values()]
        assert {p['item']: p['inst'] for p in reopened} == saved
        assert all(p.read_bytes() == content for p, content in historical.items())
        activity = tutor.next()
    before = [e for e in tutor.vault.events() if e['type'] == 'answer']
    _answer_current_batch(tutor, activity)
    after = [e for e in tutor.vault.events() if e['type'] == 'answer']

    assert len(after) - len(before) == 1, identities
    assert len(identities) == len(set(identities))
    assert path.read_bytes() == source
    assert all(p.read_bytes().startswith(content) for p, content in historical.items())


@pytest.mark.parametrize('sequential', [False, True])
def test_distinct_fallback_question_keeps_both_sweep_targets(tmp_path, sequential):
    tutor, _, path = _setup(tmp_path, sequential=sequential)
    pack = json.loads(path.read_text())
    other = copy.deepcopy(pack['items'][0])
    other.update(id='9702-2.1-i51', kcs=[OTHER_KC], difficulty=5,
                 stem='Which quantity includes direction in its definition?',
                 source={'type': 'past', 'qid': '9702_s23_12_q2'})
    pack['items'].append(other)
    path.write_text(json.dumps(pack))
    tutor.start('test', 20, [KC, OTHER_KC])
    activity = tutor.next()
    staged = [*tutor.session['presented'].values(), *tutor.session.get('queue', {}).values()]
    assert [p['item'] for p in staged] == ['9702-2.1-i01', '9702-2.1-i51']
    assert tutor.session['blocks'][0]['asked'] == {'9702-2.1-i01': KC, '9702-2.1-i51': OTHER_KC}
    _answer_current_batch(tutor, activity)
    assert set(tutor.session['blocks'][0]['res']) == {KC, OTHER_KC}
    assert tutor.session['answered'] == 2


def test_independently_assessed_source_parts_remain_eligible_in_one_batch(tmp_path):
    tutor, _, path = _setup(tmp_path, aliases=True)
    pack = json.loads(path.read_text())
    for row, part in zip(pack['items'], ['a', 'b']):
        row['source']['part'] = part
    path.write_text(json.dumps(pack))
    tutor.start('test', 20, [KC, OTHER_KC])
    activity = tutor.next()
    assert len(activity['items']) == 2
    assert {topicals.identity(p['inst']) for p in tutor.session['presented'].values()} == {
        '9702_s23_12_q1:a', '9702_s23_12_q1:b'}


def test_independently_sampled_template_variants_remain_eligible_in_one_batch(tmp_path):
    tutor, _, path = _setup(tmp_path)
    pack = json.loads(path.read_text())
    template = copy.deepcopy(PACK['items'][1])
    template['kcs'] = [KC, OTHER_KC]
    pack['items'] = [template]
    path.write_text(json.dumps(pack))
    tutor.start('test', 20, [KC, OTHER_KC])
    activity = tutor.next()
    assert len(activity['items']) == 2
    instances = [p['inst'] for p in tutor.session['presented'].values()]
    assert instances[0]['params'] != instances[1]['params']
    assert all(inst['id'] == template['id'] for inst in instances)
