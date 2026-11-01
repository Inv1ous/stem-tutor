"""Repair walkthroughs keep an authored problem and its worked steps together."""
import copy
import json
import random
from datetime import datetime

import pytest

from fixtures import make_vault
from tutorlib import session, store, views

NOW = datetime.fromisoformat('2026-09-29T17:00:00+08:00')
KC = '9702-2.1.4'


def _tutor(root):
    return session.Tutor(store.Vault(root), rng=random.Random(0), now=lambda: NOW)


def _event_bytes(root):
    return {p.name:p.read_bytes() for p in (root / '.tutor/events').glob('*.jsonl')}


@pytest.mark.parametrize('kind', ['numeric', 'expression'])
@pytest.mark.parametrize('step_count', [1, 3])
def test_wrong_faded_repair_reuses_the_complete_original_example_and_saved_context(tmp_path, kind, step_count):
    root = make_vault(tmp_path)
    path = root / '.tutor/packs/v1/specs/9702/packs/9702-2.1.json'
    pack = json.loads(path.read_text())
    worked_record = pack['worked'][0]
    if step_count == 1:
        worked_record['steps'] = [worked_record['steps'][-1]]
    if kind == 'expression':
        worked_record['faded'].update(problem='Rearrange v = u + at to make t the subject.',
                                       answer={'expr':'(v-u)/a'})
    path.write_text(json.dumps(pack))
    source = path.read_bytes()
    t = _tutor(root)
    t.start('learn', 40, [KC])
    pretest = t.next()
    assert pretest['phase'] == 'pretest'
    t.answer(', '.join(f"{q['n']}?" for q in pretest['items']))
    teach = t.next()
    assert teach['activity'] == 'teach' and teach['method'] == 'worked_faded'
    t.respond({'done':True})
    worked = copy.deepcopy(t.next())
    assert worked['activity'] == 'worked'
    for index in range(1, len(worked['steps']) + 1):
        t.respond({'step':index})
    t.respond({'done':True})
    faded = t.next()
    question = faded['items'][0]
    assert faded['phase'] == 'faded' and question['kind'] == kind
    assert question['stem'] != worked['problem']
    response = '1 m' if kind == 'numeric' else '1'
    feedback = t.answer(f"{question['n']} = {response} ~4")['results'][0]
    assert not feedback['correct']
    before = _event_bytes(root)
    grade_before = next(e['grade'] for e in t.vault.events() if e.get('id') == feedback['event'])

    repair = t.next()

    assert repair['activity'] == 'walkthrough'
    assert repair['steps'] == worked['steps'] and repair['problem'] == worked['problem']
    assert views.activity_cards(repair)[0][2] == worked['problem']
    assert _event_bytes(root) == before
    t.respond({'step':1})
    restored = _tutor(root)
    resumed = restored.next()
    assert resumed['problem'] == worked['problem'] and resumed['steps'] == worked['steps']
    assert resumed['revealed'] == 1
    assert _event_bytes(root) == before
    for index in range(2, len(worked['steps']) + 1):
        restored.respond({'step':index})
    restored.respond({'done':True})
    assert restored.next()['activity'] != 'walkthrough'
    event = next(e for e in restored.vault.events() if e.get('id') == feedback['event'])
    assert event['grade'] == grade_before and event['response'] == response
    assert event['question']['stem'] == worked_record['faded']['problem']
    assert event['item'] == worked_record['faded']['id']
    assert path.read_bytes() == source
    assert all((root / '.tutor/events' / name).read_bytes().startswith(data) for name,data in before.items())
