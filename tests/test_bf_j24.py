from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path

import pytest

from tutorlib import model, policy, report
from test_session import T0, tutor


def test_setup_stays_unfinished_until_the_learner_ticks_it(tutor):
    """B-041 (bug watch): knowing S1 does not prove notebooks and baseline logs exist."""
    published = json.loads((Path(__file__).resolve().parents[1] / 'build/out/plan.json').read_text())
    setup = next(o for o in published['weeks']['1'] if o['id'] == '1-math2')
    kc = setup['kcs'][0]
    tutor.packs.kcs[kc] = {'subject': 'math', 'spec': 'S1', 'subtopic': 'S1-1', 'title': 'Data'}
    tutor.state['kcs'][kc] = {**model._new_kc(), 'theta': 1.0, 'succ_days': ['2026-09-27', '2026-09-28']}
    review = {**setup, 'id': 'review', 'verb': 'Revise', 'title': 'Review S1', 'done': 'all ideas secure'}
    tutor.packs.plan['weeks'] = {'1': [setup, review]}
    assert policy.earned(tutor.packs.plan, tutor.state, tutor.packs) == {'review'}
    assert set(policy.progress(tutor.packs.plan, tutor.state, tutor.packs)) == {'review'}
    assert not policy.is_done(setup, tutor.state)
    assert policy.is_done(setup, tutor.state, frozenset({setup['id']}))
    assert setup['id'] not in report.almanac_payload(tutor)['done']


@pytest.mark.parametrize('mode', ['repair', 'autopilot'])
def test_practice_samples_weak_ideas_across_subtopics(tutor, monkeypatch, mode):
    """B-089 (bug watch): a short practice block must reach beyond the first few chapters."""
    tutor.packs.plan['weeks'] = {}
    for sub in range(10):
        for idea in range(5):
            kc = f'9701-{sub + 1}.1.{idea + 1}'
            tutor.packs.kcs[kc] = {'subject': 'chem', 'spec': '9701', 'subtopic': f'9701-{sub + 1}.1'}
            model.apply(tutor.state, {
                'type': 'answer', 'ts': T0.isoformat(), 'item': kc, 'kcs': [kc], 'subject': 'chem',
                'difficulty': 3, 'conf': 3, 'hinted': False, 'seconds': None, 'marks': 1,
                'grade': {'correct': False, 'score': 0.0, 'error': None, 'misconception': None},
                'credit': [], 'pos': 0,
            })
    monkeypatch.setattr(tutor.packs, 'items_for', lambda kc: [{'id': kc}])
    now = T0 + timedelta(seconds=1)
    assert not model.due_kcs(tutor.state, now)
    blocks = policy.plan_session(tutor.state, tutor.packs, now, 30, mode)
    selected = next(b['kcs'] for b in blocks if b['kind'] == 'practice')
    assert len(selected) == len(set(selected)) == 10
    assert len({tutor.packs.kc(k)['subtopic'] for k in selected}) == 10
