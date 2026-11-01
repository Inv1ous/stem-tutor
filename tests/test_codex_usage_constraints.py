"""Distinct Codex reset periods remain independent allowance constraints."""
import json
import os

import pytest

from test_foundry import fdy
from test_refine import rf, SUB


def limits(router, first, second, reverse=False, minutes=10080):
    readings = [{'windowDurationMins': minutes, 'usedPercent': used, 'resetsAt': reset}
                for used, reset in (first, second)]
    if reverse:
        readings.reverse()
    return router.codex_windows({'rateLimits': {'secondary': readings[0]},
        'rateLimitsByLimitId': {'other': {'secondary': readings[1]}}})


@pytest.mark.parametrize('fixture_name', ['fdy', 'rf'])
@pytest.mark.parametrize('reverse', [False, True])
@pytest.mark.parametrize('first_reset', [1, 2000])
def test_distinct_periods_block_launch_after_highest_usage_reset(
        fixture_name, reverse, first_reset, request, monkeypatch):
    board = request.getfixturevalue(fixture_name)
    board.cmd_add([SUB])
    windows = limits(board.router, (100, first_reset), (99, 20000), reverse)
    with open(os.environ['FOUNDRY_USAGE_FILE'], 'w') as stream:
        json.dump({'codex': windows}, stream)
    original_config = board.config
    def capped():
        cfg = original_config()
        cfg['weekly_launch_cap'] = 90
        return cfg
    monkeypatch.setattr(board, 'config', capped)
    monkeypatch.setattr(board.router.time, 'time', lambda: 3000)
    monkeypatch.setattr(board.subprocess, 'Popen', lambda *a, **k: pytest.fail('active named limit authorized work'))
    with pytest.raises(SystemExit, match='allowance is used up'):
        board.cmd_run('checker', SUB, on='codex')
    assert not board.load(SUB)['jobs']


@pytest.mark.parametrize('reverse', [False, True])
def test_distinct_periods_survive_usage_cache_and_successive_resets(fdy, reverse, monkeypatch, tmp_path):
    router = fdy.router
    windows = limits(router, (100, 1100), (99, 1200), reverse)
    monkeypatch.delenv('FOUNDRY_USAGE_FILE')
    monkeypatch.setenv('FOUNDRY_CLAUDE_STATE', str(tmp_path / 'missing.json'))
    calls = []
    def reading(*a):
        calls.append(True)
        return windows if len(calls) == 1 else None
    monkeypatch.setattr(router, 'codex_usage', reading)
    monkeypatch.setattr(router, 'claude_probe', lambda *a: pytest.fail('must not spend on a probe'))
    notes = {'claude': {'probed': 2000}}
    cfg = fdy.config()
    cfg['weekly_launch_cap'] = 90
    for at, blocked in [(1000, True), (1110, True), (1210, False)]:
        live = router.usage(notes, 'fake-codex', 'fake-claude', now=at)
        # State persistence must retain each reset, including between launches.
        notes = json.loads(json.dumps(notes))
        assert (router.score('codex', live['codex'], cfg, [], now=at)[0] is None) == blocked


@pytest.mark.parametrize('reverse', [False, True])
@pytest.mark.parametrize('minutes', [300, 10080, 60])
def test_distinct_periods_enforce_short_and_other_named_windows(fdy, reverse, minutes):
    windows = limits(fdy.router, (100, 1), (99, 20000), reverse, minutes)
    windows.setdefault('seven_day', {'used': 20, 'resets': 30000})
    assert fdy.router.score('codex', windows, fdy.config(), [], now=1000)[0] is not None
    # At 100% the remaining active limit blocks independently of any configured cap.
    windows = limits(fdy.router, (100, 1), (100, 20000), reverse, minutes)
    windows.setdefault('seven_day', {'used': 20, 'resets': 30000})
    assert fdy.router.score('codex', windows, fdy.config(), [], now=1000)[0] is None


@pytest.mark.parametrize('reverse', [False, True])
def test_identical_periods_preserve_plain_window_shape_and_highest_usage(fdy, reverse):
    assert limits(fdy.router, (10, 20000), (80, 20000), reverse) == {
        'seven_day': {'used': 80, 'resets': 20000}}
    assert limits(fdy.router, (80, 20000), (80, 20000), reverse) == {
        'seven_day': {'used': 80, 'resets': 20000}}


@pytest.mark.parametrize('reverse', [False, True])
def test_limit_record_retains_latest_independent_full_window(fdy, reverse):
    windows = limits(fdy.router, (100, 1100), (99, 20000), reverse)
    notes = {}
    fdy.router.record(notes, fdy.config(), 'checker', 'codex', 0, ok=False,
                      limit=True, windows=windows, now=1000)
    assert notes['codex']['closed_until'] == 20000


def test_usage_status_displays_each_independent_period(fdy):
    windows = limits(fdy.router, (100, 1), (99, 20000))
    with open(os.environ['FOUNDRY_USAGE_FILE'], 'w') as stream:
        json.dump({'codex': windows}, stream)
    lines = fdy.usage_lines()
    assert any('100% used' in line for line in lines)
    assert any('99% used' in line for line in lines)


@pytest.mark.parametrize('reverse', [False, True])
def test_active_unknown_reset_is_not_discarded_with_expired_full_window(fdy, reverse):
    windows = limits(fdy.router, (100, 1), (99, None), reverse)
    cfg = fdy.config()
    cfg['weekly_launch_cap'] = 90
    assert fdy.router.score('codex', windows, cfg, [], now=30000)[0] is None


@pytest.mark.parametrize('reverse', [False, True])
@pytest.mark.parametrize('policy', ['reserve', 'weekly', 'window', 'pending'])
def test_each_period_uses_original_window_policy(fdy, reverse, policy):
    windows = limits(fdy.router, (100, 1), (80, 20000), reverse)
    cfg = fdy.config()
    running, own = [], 0
    if policy == 'reserve':
        cfg['reserve']['codex'] = 20
    elif policy == 'weekly':
        cfg['weekly_launch_cap'] = 80
    elif policy == 'window':
        cfg['window_cap'] = {'codex': {'seven_day': 80}}
    else:
        cfg['weights']['codex']['checker'] = 10
        running, own = ['checker'], 10
    assert fdy.router.score('codex', windows, cfg, running, now=1000, own=own)[0] is None


@pytest.mark.parametrize('reverse', [False, True])
def test_score_uses_independent_period_with_least_room_per_hour(fdy, reverse):
    windows = limits(fdy.router, (80, 4600), (10, 37000), reverse)
    score = fdy.router.score('codex', windows, fdy.config(), [], now=1000)[0]
    assert score == 9  # 90% room / 10 hours, versus 20% room / one hour


def test_other_window_names_keep_existing_longest_window_routing(fdy):
    windows = {'seven_day': {'used': 10, 'resets': 4600},
               'seven_day_sonnet': {'used': 80, 'resets': 37000}}
    cfg = fdy.config()
    cfg['reserve']['claude'] = 0
    assert fdy.router.score('claude', windows, cfg, [], model='sonnet', now=1000)[0] == 90
    # A model-specific cap that does not apply must still be skipped.
    windows['seven_day_sonnet'] = None
    assert fdy.router.score('claude', windows, cfg, [], model='opus', now=1000)[0] == 90
