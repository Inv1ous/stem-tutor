"""Distinct sampled questions keep their own sweep target across save/restart."""
import copy
import json
import random
from datetime import datetime

import pytest

from fixtures import PACK, make_vault
from tutorlib import session, store
from tutorlib.session import _display_answer

NOW = datetime.fromisoformat('2026-09-29T17:00:00+08:00')
KC, OTHER = '9702-2.1.1', '9702-2.1.4'


def _tutor(root, sequential):
    return session.Tutor(store.Vault(root), rng=random.Random(0), now=lambda: NOW, one_at_a_time=sequential)


def _events(root):
    return {p.name:p.read_bytes() for p in (root / '.tutor/events').glob('*.jsonl')}


def _template_pool(tmp_path):
    root = make_vault(tmp_path)
    path = root / '.tutor/packs/v1/specs/9702/packs/9702-2.1.json'
    pack = json.loads(path.read_text())
    template = copy.deepcopy(PACK['items'][1])
    template['kcs'] = [KC, OTHER]
    pack['items'] = [template]
    path.write_text(json.dumps(pack))
    return root, path


def _exercise_instances(root, path, sequential, restart, wrong_first, focus):
    source = path.read_bytes()
    t = _tutor(root, sequential)
    t.start('test', 40, focus)
    t.next()
    staged = [*t.session['presented'].values(), *t.session.get('queue', {}).values()]
    assert len(staged) == 2 and staged[0]['item'] == staged[1]['item']
    assert staged[0]['inst']['params'] != staged[1]['inst']['params']
    assert [row['inst']['_serving_kc'] for row in staged] == focus
    historical = _events(root)
    expected = {}
    for index, target in enumerate(focus):
        if restart == 'before' and index == 0 or restart == 'between' and index == 1:
            before = _events(root)
            t = _tutor(root, sequential)
            assert _events(root) == before
        question = t.next()['items'][0]
        inst = t.session['presented'][str(question['n'])]['inst']
        assert inst['_serving_kc'] == target
        correct = not (wrong_first and index == 0)
        value = _display_answer(inst) if correct else '0 m'
        confidence = 1 if index == 0 else 4
        feedback = t.answer(f"{question['n']} = {value} ~{confidence}")['results'][0]
        assert feedback['correct'] == correct
        expected[target] = {'ok':correct, 'conf':confidence}
        assert t.session['blocks'][0]['res'] == expected
    assert t.session['answered'] == 2 and not t.session.get('queue')
    t.next()
    if wrong_first:
        repair = [block['kc'] for block in t.session['blocks'] if block['kind'] == 'learn']
        assert repair == [focus[0]]
    answers = [event for event in t.vault.events() if event['type'] == 'answer']
    assert len(answers) == 2 and answers[0]['grade']['correct'] == (not wrong_first)
    assert answers[1]['grade']['correct']
    assert path.read_bytes() == source
    assert all((root / '.tutor/events' / name).read_bytes().startswith(data) for name,data in historical.items())


@pytest.mark.parametrize('sequential', [False, True])
@pytest.mark.parametrize('restart', ['none', 'before', 'between'])
@pytest.mark.parametrize('wrong_first', [False, True])
def test_public_sampled_sweep_answers_keep_separate_targets(tmp_path, sequential, restart, wrong_first):
    root, path = _template_pool(tmp_path)
    _exercise_instances(root, path, sequential, restart, wrong_first, [KC,OTHER])


def test_reversed_focus_uses_the_selected_instance_target(tmp_path):
    root, path = _template_pool(tmp_path)
    _exercise_instances(root, path, True, 'between', True, [OTHER,KC])


@pytest.mark.parametrize('sequential', [False, True])
@pytest.mark.parametrize('legacy_item_map', [False, True])
def test_old_saved_sweep_without_instance_target_keeps_existing_fallbacks(tmp_path, sequential, legacy_item_map):
    root = make_vault(tmp_path)
    path = root / '.tutor/packs/v1/specs/9702/packs/9702-2.1.json'
    pack = json.loads(path.read_text())
    first = copy.deepcopy(PACK['items'][0])
    first.update(kcs=[KC], source={'type':'past','qid':'9702_s23_12_q1'})
    second = copy.deepcopy(first)
    second.update(id='9702-2.1-i51', kcs=[OTHER], source={'type':'past','qid':'9702_s23_12_q2'})
    pack['items'] = [first,second]
    path.write_text(json.dumps(pack))
    t = _tutor(root, sequential)
    t.start('test',20,[KC,OTHER])
    t.next()
    saved_path = t.session_path
    saved = json.loads(saved_path.read_text())
    for bucket in ('presented','queue'):
        for pending in saved.get(bucket,{}).values():
            pending['inst'].pop('_serving_kc',None)
    if not legacy_item_map:
        saved['blocks'][0].pop('asked',None)
    saved_path.write_text(json.dumps(saved))  # disposable input in the supported older saved-session shape
    before = _events(root)
    t = _tutor(root, sequential)
    assert _events(root) == before
    for target in (KC,OTHER):
        question = t.next()['items'][0]
        assert t.answer(f"{question['n']}B4")['results'][0]['correct']
        assert t.session['blocks'][0]['res'][target] == {'ok':True,'conf':4}
    assert set(t.session['blocks'][0]['res']) == {KC,OTHER}
    assert len([event for event in t.vault.events() if event['type'] == 'answer']) == 2
    assert all((root / '.tutor/events' / name).read_bytes().startswith(data) for name,data in before.items())
