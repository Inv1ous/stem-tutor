"""A fresh provider closure cannot expire on an already-past sibling reset."""
import json
import os

import pytest

from test_foundry import fdy, SUB
from test_refine import rf
from test_shortcuts_gen import gen


def report(resets=(1, 20000), reverse=False, flag='ordinary'):
    readings = [{'windowDurationMins': 10080, 'usedPercent': used, 'resetsAt': reset}
                for used, reset in zip((100, 10), resets)]
    if reverse:
        readings.reverse()
    data = {'rateLimits': {'secondary': readings[0]},
            'rateLimitsByLimitId': {'other': {'secondary': readings[1]}}}
    if flag == 'ordinary':
        data['ordinaryUsageAllowed'] = False
    elif flag == 'reached':
        data['rateLimits']['rateLimitReachedType'] = 'secondary'
    elif flag == 'spend':
        data['rateLimits']['spendControlReached'] = True
    return data


@pytest.mark.parametrize('fixture_name', ['fdy', 'rf'])
@pytest.mark.parametrize('flag', ['ordinary', 'reached', 'spend'])
@pytest.mark.parametrize('resets', [(1, 20000), (1, 2), (1, None)])
@pytest.mark.parametrize('reverse', [False, True])
def test_explicit_closure_blocks_actual_launch_with_past_sibling(
        fixture_name, flag, resets, reverse, request, monkeypatch):
    board = request.getfixturevalue(fixture_name)
    board.cmd_add([SUB])
    monkeypatch.setattr(board.router.time, 'time', lambda: 1000)
    windows = board.router.codex_windows(report(resets, reverse, flag))
    with open(os.environ['FOUNDRY_USAGE_FILE'], 'w') as stream:
        json.dump({'codex': windows}, stream)
    monkeypatch.setattr(board.subprocess, 'Popen',
                        lambda *a, **k: pytest.fail('explicit provider closure authorized a worker'))
    with pytest.raises(SystemExit, match='allowance is used up'):
        board.cmd_run('checker', SUB, on='codex')
    assert not board.load(SUB)['jobs']


@pytest.mark.parametrize('flag', [None, 'ordinary', 'reached', 'spend'])
def test_closure_uses_future_reset_from_all_independent_periods(fdy, flag):
    data = report(flag=flag)
    data['rateLimitsByLimitId']['third'] = {'secondary': {
        'windowDurationMins': 10080, 'usedPercent': 20, 'resetsAt': 3000}}
    windows = fdy.router.codex_windows(data, now=1000)
    if flag is None:
        assert 'limit' not in windows
        assert fdy.router.score('codex', windows, fdy.config(), [], now=1000)[0] is not None
    else:
        assert windows['limit'] == {'used': 100, 'resets': 3000}
        assert fdy.router.score('codex', windows, fdy.config(), [], now=1000)[0] is None
        # A cached, known reset may reopen; a new false reading is a new closure.
        assert fdy.router.score('codex', windows, fdy.config(), [], now=3001)[0] is not None
        refreshed = fdy.router.codex_windows(data, now=3001)
        assert refreshed['limit']['resets'] == 20000
        assert fdy.router.score('codex', refreshed, fdy.config(), [], now=3001)[0] is None


@pytest.mark.parametrize('resets', [(1, 2), (None, None), (1000, 1)])
def test_closure_without_a_future_reset_requires_a_fresh_reading(fdy, resets, monkeypatch):
    router = fdy.router
    windows = router.codex_windows(report(resets), now=1000)
    assert windows['limit'] == {'used': 100, 'resets': None}
    monkeypatch.delenv('FOUNDRY_USAGE_FILE')
    monkeypatch.setattr(router, 'codex_usage', lambda *a: None)
    monkeypatch.setattr(router, 'claude_cache', lambda *a: ({}, 0))
    monkeypatch.setattr(router, 'claude_probe', lambda *a: pytest.fail('must not probe a paid provider'))
    notes = {'codex': {'windows': windows, 'at': 1000}, 'claude': {'probed': 30000}}
    live = router.usage(notes, 'fake-codex', 'fake-claude', now=2000)
    assert router.score('codex', live['codex'], fdy.config(), [], now=2000)[0] is None
    data = report((1, 2), flag=None)
    data['ordinaryUsageAllowed'] = True
    monkeypatch.setattr(router, 'codex_usage', lambda *a: router.codex_windows(data, now=2001))
    live = router.usage(notes, 'fake-codex', 'fake-claude', now=2001)
    assert 'limit' not in live['codex']
    assert router.score('codex', live['codex'], fdy.config(), [], now=2001)[0] is not None


@pytest.mark.parametrize('reset', [None, 20000])
@pytest.mark.parametrize('cap', [70, 101, 1e308])
def test_shortcut_generator_stops_on_active_explicit_closure(gen, tmp_path, monkeypatch, reset, cap):
    (tmp_path / 'usage.json').write_text(json.dumps({'codex': {
        'seven_day': {'used': 10, 'resets': 20000}, 'limit': {'used': 100, 'resets': reset}}}))
    monkeypatch.setattr(gen.time, 'time', lambda: 1000)
    monkeypatch.setattr(gen, 'run_worker', lambda *a, **k: pytest.fail('explicit closure authorized shortcut work'))
    assert gen.main(['run', '--spec', 'P1', '--max-batches', '1', '--stop-codex-week', str(cap)]) == 0
    assert not (gen.LESSONS / 'P1.json').exists()


def test_shortcut_getter_keeps_actual_usage_after_known_closure_reset(gen, tmp_path, monkeypatch):
    (tmp_path / 'usage.json').write_text(json.dumps({'codex': {
        'seven_day': {'used': 10, 'resets': 20000}, 'limit': {'used': 100, 'resets': 1}}}))
    monkeypatch.setattr(gen.time, 'time', lambda: 1000)
    assert gen.codex_week('fake-codex') == 10


@pytest.mark.parametrize('new_state,cap', [('capped', 70), ('unknown', 1e308), ('closed', 1e308)])
def test_shortcut_retry_rechecks_admission_and_preserves_first_success(
        gen, tmp_path, monkeypatch, new_state, cap):
    gen.LESSONS.mkdir(parents=True)
    existing = {'SEM-P1-old': {'keep': 'previously validated'}}
    (gen.LESSONS / 'P1.json').write_text(json.dumps(existing))
    updates = {
        'capped': {'seven_day': {'used': 90}},
        'unknown': None,
        'closed': {'seven_day': {'used': 10}, 'limit': {'used': 100, 'resets': None}},
    }
    calls = []
    first_ok = {'SEM-P1-e1': {'id': 'SEM-P1-e1', 'from': 'first validated result'}}
    def first_worker(*args, **kwargs):
        calls.append(True)
        if len(calls) != 1:
            pytest.fail('retry ignored the new allowance reading')
        (tmp_path / 'usage.json').write_text(json.dumps({'codex': updates[new_state]}))
        return dict(first_ok), {'SEM-P1-e2': ['needs retry']}, False, str(tmp_path / 'first.log')
    monkeypatch.setattr(gen, 'run_worker', first_worker)
    assert gen.main(['run', '--spec', 'P1', '--batch', '2', '--max-batches', '1',
                     '--stop-codex-week', str(cap)]) == 0
    assert len(calls) == 1
    assert json.loads((gen.LESSONS / 'P1.json').read_text()) == {**existing, **first_ok}
    assert [entry['id'] for entry in gen.pending('P1', 8)] == ['SEM-P1-e2', 'SEM-P1-e3', 'SEM-P1-e4']


def test_shortcut_retry_still_runs_after_a_known_closure_expires(gen, tmp_path, monkeypatch):
    monkeypatch.setattr(gen.time, 'time', lambda: 1000)
    calls = []
    def worker(spec, batch, model, effort, *args):
        calls.append(effort)
        if len(calls) == 1:
            (tmp_path / 'usage.json').write_text(json.dumps({'codex': {
                'seven_day': {'used': 10}, 'limit': {'used': 100, 'resets': 1}}}))
            return {'SEM-P1-e1': {'id': 'SEM-P1-e1'}}, {'SEM-P1-e2': ['retry']}, False, str(tmp_path / 'first.log')
        return {'SEM-P1-e2': {'id': 'SEM-P1-e2'}}, {}, False, str(tmp_path / 'retry.log')
    monkeypatch.setattr(gen, 'run_worker', worker)
    assert gen.main(['run', '--spec', 'P1', '--batch', '2', '--max-batches', '1']) == 0
    assert calls == ['low', 'medium']
    assert set(json.loads((gen.LESSONS / 'P1.json').read_text())) == {'SEM-P1-e1', 'SEM-P1-e2'}
