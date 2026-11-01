"""Diagnostic evidence must come from distinct canonical questions."""
import copy
import json
import random
from datetime import datetime

import pytest

from fixtures import make_vault
from tutorlib import session, store, topicals

NOW = datetime.fromisoformat('2026-09-29T17:00:00+08:00')
KC = '9702-2.1.1'


def _tutor(root):
    return session.Tutor(store.Vault(root), rng=random.Random(0), now=lambda: NOW)


def _pool(tmp_path, independent_part=False):
    root = make_vault(tmp_path)
    item = {'id': '9702-2.1-i50', 'kcs': [KC], 'kind': 'mcq', 'difficulty': 3, 'marks': 1,
            'source': {'type': 'past', 'qid': '9702_s23_12_q1'}, 'stem': 'Which quantity is a vector?',
            'options': {'A': 'distance', 'B': 'displacement'}, 'answer': 'B'}
    alias = copy.deepcopy(item)
    alias.update(id='9702-2.1-i51', kcs=[KC, '9702-2.1.4'], difficulty=5)
    if independent_part:
        alias['source']['part'] = 'b'
    other = copy.deepcopy(item)
    other.update(id='9702-2.1-i52', difficulty=4, stem='What is the average velocity after one complete lap?',
                 options={'A': 'zero', 'B': 'distance divided by time'}, answer='A')
    other['source']['qid'] = '9702_s23_12_q2'
    path = root / '.tutor/packs/v1/specs/9702/packs/9702-2.1.json'
    pack = json.loads(path.read_text())
    pack['items'] = [item, alias, other]
    path.write_text(json.dumps(pack))
    return root, path


@pytest.mark.parametrize('restart', [False, True])
def test_diagnosis_avoids_a_consumed_source_alias_in_another_kc_context(tmp_path, restart):
    root, path = _pool(tmp_path)
    source_before = path.read_bytes()
    t = _tutor(root)
    t.start('diagnose', 40, [KC])
    first = t.next()['items'][0]
    first_record = copy.deepcopy(t.session['presented'][str(first['n'])])
    assert first_record['item'] == '9702-2.1-i50'
    assert t.answer(f"{first['n']}B4")['results'][0]['correct']
    event_files = {p.name: p.read_bytes() for p in (root / '.tutor/events').glob('*.jsonl')}
    if restart:
        t = _tutor(root)
    second = t.next()['items'][0]
    second_record = t.session['presented'][str(second['n'])]

    assert topicals.identity(second_record['inst']) != topicals.identity(first_record['inst'])
    assert second_record['item'] == '9702-2.1-i52'
    assert not t.answer(f"{second['n']}B4")['results'][0]['correct']
    t.next()  # finish the bracket once the distinct pool is exhausted
    diagnosis = [e for e in t.vault.events() if e['type'] == 'diagnosis'][-1]
    assert diagnosis['results'][KC]['asked'] == [[3, True], [4, False]]
    assert diagnosis['results'][KC]['level'] == 'partial' and KC in t.state['gaps']
    assert path.read_bytes() == source_before
    assert all((root / '.tutor/events' / name).read_bytes().startswith(data) for name, data in event_files.items())


def test_independently_assessed_source_parts_remain_eligible(tmp_path):
    root, _ = _pool(tmp_path, independent_part=True)
    t = _tutor(root)
    t.start('diagnose', 40, [KC])
    first = t.next()['items'][0]
    first_record = copy.deepcopy(t.session['presented'][str(first['n'])])
    t.answer(f"{first['n']}B4")
    second = t.next()['items'][0]
    second_record = t.session['presented'][str(second['n'])]
    assert second_record['item'] == '9702-2.1-i51'
    assert topicals.identity(second_record['inst']) != topicals.identity(first_record['inst'])


def test_recalled_alias_cannot_make_the_diagnostic_result_secure(tmp_path):
    root, _ = _pool(tmp_path)
    t = _tutor(root)
    t.start('diagnose', 40, [KC])
    for _ in range(4):
        activity = t.next()
        diagnosis = [e for e in t.vault.events() if e['type'] == 'diagnosis']
        if diagnosis:
            break
        assert activity['block'] == 'bracket'
        # The learner knows the repeated vector question but misses the independent lap question.
        t.answer(', '.join(f"{q['n']}B4" for q in activity['items']))
    assert diagnosis
    result = diagnosis[-1]['results'][KC]
    assert result['asked'] == [[3, True], [4, False]]
    assert result['level'] == 'partial' and KC in t.state['gaps']
