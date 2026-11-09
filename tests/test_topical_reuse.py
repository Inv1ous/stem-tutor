"""Reviewed bank questions share existing learner routes without admitting pending candidates."""
from copy import deepcopy
import json

import pytest

from test_topicals import KC, TARGET, bank_vault, item, publish, tutor_for
from tutorlib import model, topicals


@pytest.mark.parametrize('mode', ['lesson', 'test', 'learn', 'review', 'autopilot', 'weak', 'diagnose', 'long'])
def test_reviewed_bank_item_reaches_each_relevant_engine_mode_with_source_identity(tmp_path, mode):
    root = bank_vault(tmp_path)
    path = root / f'.tutor/packs/v1/specs/9702/packs/{TARGET}.json'
    pack = json.loads(path.read_text())
    pack['items'] = []  # Retain fixture teaching content, while the bank supplies the assessment.
    path.write_text(json.dumps(pack))
    source = item(source={'type': 'past', 'qid': '9702_s23_22_q99', 'ref': 'CAIE 9702 · Jun 2023 · P22 · Q99'})
    source['topical'].update(requires=[TARGET], support={})
    if mode == 'long':
        source.update(kind='structured', scheme=[{'mark': 'B1', 'point': 'Synthetic mark point.'}])
    publish(root, [source])
    tutor = tutor_for(root)
    card = model._fsrs().Card().to_dict()
    card['due'] = '2026-10-01T00:00:00+00:00'
    tutor.state['kcs'][KC] = {**model._new_kc(), 'n': 1, 'fsrs': card}
    assert tutor.start(mode, focus=[KC]).get('ok') is not False
    activity = tutor.next()
    if mode == 'lesson':
        assert activity['activity'] == 'choose'
        tutor.respond({'choice': 'gaps'})
        activity = tutor.next()
    assert activity['activity'] == 'questions'
    view = activity['items'][0]
    pending = tutor.session['presented'][str(view['n'])]
    assert pending['item'] == source['id']
    assert topicals.identity(pending['inst']) == topicals.identity(source)
    assert view['source'] == source['source']['ref']
    assert pending['inst']['topical']['reviewed'] is True


def test_invalid_topical_marking_options_do_not_replace_current_session(tmp_path):
    root = bank_vault(tmp_path)
    publish(root, [item()])
    tutor = tutor_for(root)
    tutor.start('review')
    original, events = deepcopy(tutor.session), list(tutor.vault.events())
    for mode, value in [('topical', 'true'), ('topical', 1), ('review', True)]:
        assert tutor.start(mode, focus=[TARGET], replace=True, topical_auto_mark=value)['ok'] is False
        assert tutor.session == original and list(tutor.vault.events()) == events
