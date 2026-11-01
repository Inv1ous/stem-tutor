"""A diagnostic source is consumed once across the complete KC bracket."""
import copy
import json

import pytest

from test_diagnostic_identity import KC, _pool, _tutor
from tutorlib import topicals

OTHER_KC = '9702-2.1.4'


def _events(root):
    return {p.name: p.read_bytes() for p in (root / '.tutor/events').glob('*.jsonl')}


def _staged(t):
    return [*t.session['presented'].values(), *t.session.get('queue', {}).values()]


@pytest.mark.parametrize('sequential', [False, True])
@pytest.mark.parametrize('restart', [False, True])
def test_multikc_bracket_does_not_repeat_sources_within_or_after_a_batch(tmp_path, sequential, restart):
    root, path = _pool(tmp_path)
    source = path.read_bytes()
    t = _tutor(root)
    t.one_at_a_time = sequential
    t.start('diagnose', 40, [KC, OTHER_KC])
    seen = set()
    for _ in range(5):
        activity = t.next()
        diagnosis = [e for e in t.vault.events() if e['type'] == 'diagnosis']
        if diagnosis:
            break
        staged = _staged(t)
        identities = [topicals.identity(p['inst']) or p['item'] for p in staged]
        assert len(identities) == len(set(identities)), identities
        for question in activity['items']:
            record = t.session['presented'][str(question['n'])]
            identity = topicals.identity(record['inst']) or record['item']
            assert identity not in seen
            seen.add(identity)
            t.answer(f"{question['n']}B4")
        before = _events(root)
        if restart:
            t = _tutor(root)
            t.one_at_a_time = sequential
            assert _events(root) == before
    assert diagnosis
    assert diagnosis[-1]['results'][KC]['asked'] == [[3, True], [4, False]]
    assert diagnosis[-1]['results'][OTHER_KC]['asked'] == []
    assert diagnosis[-1]['results'][OTHER_KC]['level'] == 'gap'  # no distinct evidence cannot certify this KC
    assert path.read_bytes() == source


@pytest.mark.parametrize('answer,correct', [('B4', True), ('?', False)])
def test_exact_shared_record_keeps_the_first_target_and_pool_terminates(tmp_path, answer, correct):
    root, path = _pool(tmp_path)
    data = json.loads(path.read_text())
    record = copy.deepcopy(data['items'][0])
    record.update(kcs=[KC, OTHER_KC], difficulty=5)
    data['items'] = [record]
    path.write_text(json.dumps(data))
    source = path.read_bytes()
    t = _tutor(root)
    t.start('diagnose', 40, [KC, OTHER_KC])
    activity = t.next()
    assert len(activity['items']) == 1 and not t.session.get('queue')
    assert t.session['blocks'][0]['asked_for'] == {record['id']: KC}
    number = activity['items'][0]['n']
    t.answer(f'{number}{answer}')
    assert t.session['blocks'][0]['st'][KC]['asked'] == [[5, correct]]
    assert t.session['blocks'][0]['st'][OTHER_KC]['asked'] == []
    before = _events(root)
    t = _tutor(root)
    assert _events(root) == before
    t.next()
    result = [e for e in t.vault.events() if e['type'] == 'diagnosis'][-1]['results']
    assert result[KC]['asked'] == [[5, correct]]
    assert result[OTHER_KC]['asked'] == [] and result[OTHER_KC]['level'] == 'gap'
    assert len([e for e in t.vault.events() if e['type'] == 'answer']) == 1
    assert path.read_bytes() == source
    assert all((root / '.tutor/events' / name).read_bytes().startswith(data) for name, data in before.items())


def test_distinct_queued_question_keeps_its_target_and_values_after_restart(tmp_path):
    root, path = _pool(tmp_path)
    data = json.loads(path.read_text())
    data['items'][2]['kcs'] = [OTHER_KC]
    path.write_text(json.dumps(data))
    t = _tutor(root)
    t.one_at_a_time = True
    t.start('diagnose', 40, [KC, OTHER_KC])
    first = t.next()['items'][0]
    waiting, = t.session['queue'].values()
    assert waiting['item'] == '9702-2.1-i52'
    pending = json.loads(json.dumps(waiting))
    t.answer(f"{first['n']}B4")
    before = _events(root)
    t = _tutor(root)
    t.one_at_a_time = True
    assert _events(root) == before
    second = t.next()['items'][0]
    opened = t.session['presented'][str(second['n'])]
    assert opened['inst'] == pending['inst']
    assert t.next()['items'] == [second]
    t.answer(f"{second['n']}A4")
    bracket = t.session['blocks'][0]
    assert bracket['st'][KC]['asked'] == [[3, True]]
    assert bracket['st'][OTHER_KC]['asked'] == [[4, True]]
    assert not t.session.get('queue') and t.session['answered'] == 2
    t.next()
    assert len([e for e in t.vault.events() if e['type'] == 'diagnosis']) == 1


def test_independent_source_parts_can_be_staged_for_separate_kcs(tmp_path):
    root, _ = _pool(tmp_path, independent_part=True)
    t = _tutor(root)
    t.start('diagnose', 40, [KC, OTHER_KC])
    activity = t.next()
    assert len(activity['items']) == 2
    assert {topicals.identity(p['inst']) for p in _staged(t)} == {'9702_s23_12_q1', '9702_s23_12_q1:b'}
    t.answer(', '.join(f"{q['n']}B4" for q in activity['items']))
    bracket = t.session['blocks'][0]
    assert bracket['st'][KC]['asked'] == [[3, True]]
    assert bracket['st'][OTHER_KC]['asked'] == [[5, True]]
