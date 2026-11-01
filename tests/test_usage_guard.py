"""Invalid allowance readings never authorize paid work; all boards are disposable."""
import json
import os
import time
from types import SimpleNamespace

import pytest

from test_foundry import fdy
from test_refine import rf, SUB


INVALID = [None, False, True, 'unknown', 'NaN', 'Infinity', '-Infinity', -1, 101]


def provider_reading(router, source, value, tmp_path):
    reset = int(time.time() + 86400)
    if source == 'codex':
        return router.codex_windows({'rateLimits': {'secondary': {
            'windowDurationMins': 10080, 'usedPercent': value, 'resetsAt': reset}}})
    if source in ('cache', 'cache-new'):
        limit = {'percent': value, 'kind': 'weekly_all', 'is_active': True,
                 'resets_at': '2099-01-01T00:00:00Z'}
        utilization = {'limits': [limit]} if source == 'cache' else {
            'seven_day': {'utilization': value, 'resets_at': limit['resets_at']}}
        cache = tmp_path / 'claude-cache.json'
        cache.write_text(json.dumps({'cachedUsageUtilization': {
            'utilization': utilization, 'fetchedAtMs': 1000}}))
        return router.claude_cache(cache)[0]
    return router.claude_events(json.dumps({'type': 'rate_limit_event', 'rate_limit_info': {
        'unifiedWindows': {'seven_day': {'utilization': value, 'resetsAt': reset}}}}))['windows']


@pytest.mark.parametrize('fixture_name', ['fdy', 'rf'])
@pytest.mark.parametrize('provider', ['codex', 'claude'])
@pytest.mark.parametrize('used', INVALID)
def test_invalid_usage_blocks_direct_launch(fixture_name, provider, used, request, monkeypatch):
    board = request.getfixturevalue(fixture_name)
    board.cmd_add([SUB])
    path = os.environ['FOUNDRY_USAGE_FILE']
    with open(path, 'w') as stream:
        json.dump({provider: {'seven_day': {'used': used, 'resets': time.time() + 86400}}}, stream)
    monkeypatch.setattr(board.subprocess, 'Popen', lambda *a, **k: pytest.fail('invalid usage authorized a worker'))
    with pytest.raises(SystemExit, match='usage.*(unknown|invalid)'):
        board.cmd_run('checker', SUB, on=provider)
    assert not board.load(SUB)['jobs']


@pytest.mark.parametrize('source,provider', [('codex', 'codex'), ('cache', 'claude'),
                                             ('cache-new', 'claude'), ('events', 'claude')])
@pytest.mark.parametrize('value', [False, True, 'NaN', -1, 101])
def test_provider_reading_cannot_turn_invalid_percentage_into_launch(fdy, source, provider, value, tmp_path, monkeypatch):
    fdy.cmd_add([SUB])
    windows = provider_reading(fdy.router, source, value, tmp_path)
    with open(os.environ['FOUNDRY_USAGE_FILE'], 'w') as stream:
        json.dump({provider: windows}, stream)
    monkeypatch.setattr(fdy.subprocess, 'Popen', lambda *a, **k: pytest.fail('invalid provider reading authorized a worker'))
    with pytest.raises(SystemExit, match='usage.*(unknown|invalid)'):
        fdy.cmd_run('checker', SUB, on=provider)
    assert not fdy.load(SUB)['jobs']


@pytest.mark.parametrize('fixture_name', ['fdy', 'rf'])
@pytest.mark.parametrize('provider', ['codex', 'claude'])
@pytest.mark.parametrize('used', [0, 69])
def test_valid_usage_launches_with_reserve_and_weekly_cap(fixture_name, provider, used, request, monkeypatch):
    board = request.getfixturevalue(fixture_name)
    board.cmd_add([SUB])
    original_config = board.config
    def guarded_config():
        cfg = original_config()
        cfg['weekly_launch_cap'] = 70
        cfg['reserve'][provider] = 25
        return cfg
    monkeypatch.setattr(board, 'config', guarded_config)
    with open(os.environ['FOUNDRY_USAGE_FILE'], 'w') as stream:
        json.dump({provider: {'seven_day': {'used': used, 'resets': time.time() + 86400}}}, stream)
    monkeypatch.setattr(board.subprocess, 'Popen', lambda *a, **k: SimpleNamespace(pid=99999999))
    board.cmd_run('checker', SUB, on=provider)
    assert board.load(SUB)['jobs']['checker']['provider'] == provider


@pytest.mark.parametrize('source', ['codex', 'cache', 'cache-new', 'events'])
def test_provider_reading_preserves_exact_zero(fdy, source, tmp_path):
    windows = provider_reading(fdy.router, source, 0, tmp_path)
    assert windows['seven_day']['used'] == 0
    assert windows['seven_day']['resets']


@pytest.mark.parametrize('value', [None, False, 'NaN', -1, 101])
def test_invalid_claude_cache_survives_live_estimation_then_recovers(fdy, value, tmp_path, monkeypatch):
    router = fdy.router
    at = time.time()
    monkeypatch.delenv('FOUNDRY_USAGE_FILE')
    monkeypatch.setenv('FOUNDRY_CLAUDE_STATE', str(tmp_path / 'claude-cache.json'))
    monkeypatch.setattr(router, 'codex_usage', lambda *a: pytest.fail('unexpected usage CLI'))
    monkeypatch.setattr(router, 'claude_probe', lambda *a: pytest.fail('must not spend on a probe'))
    provider_reading(router, 'cache', value, tmp_path)
    cache_path = tmp_path / 'claude-cache.json'
    cached = json.loads(cache_path.read_text())
    cached['cachedUsageUtilization']['fetchedAtMs'] = at * 1000
    cache_path.write_text(json.dumps(cached))
    notes = {'codex': {'at': at, 'windows': {'seven_day': {'used': 10, 'resets': at + 86400}}},
             'claude': {'probed': at, 'windows': {'seven_day': {
                 'used': 20, 'spent': 1, 'at': at - 10, 'resets': 4070908800.0}}}}
    live = router.usage(notes, 'fake-codex', 'fake-claude', now=at)
    assert live['claude']['seven_day']['used'] is None
    assert live['claude']['seven_day']['resets'] == 4070908800.0
    assert router.score('claude', live['claude'], fdy.config(), [], now=at)[0] is None
    cached['cachedUsageUtilization']['utilization']['limits'][0]['percent'] = 0
    cached['cachedUsageUtilization']['fetchedAtMs'] = (at + 1) * 1000
    cache_path.write_text(json.dumps(cached))
    recovered = router.usage(notes, 'fake-codex', 'fake-claude', now=at + 2)
    assert recovered['claude']['seven_day']['used'] == 0
    assert recovered['claude']['seven_day']['resets'] == 4070908800.0
    assert router.score('claude', recovered['claude'], fdy.config(), [], now=at + 2)[0] is not None


@pytest.mark.parametrize('invalid_first', [False, True])
def test_invalid_duplicate_codex_limit_cannot_be_masked_by_valid_limit(fdy, invalid_first):
    readings = [False, 10] if invalid_first else [10, False]
    windows = fdy.router.codex_windows({'rateLimits': {'secondary': {
        'windowDurationMins': 10080, 'usedPercent': readings[0], 'resetsAt': 20000}},
        'rateLimitsByLimitId': {'another': {'secondary': {
            'windowDurationMins': 10080, 'usedPercent': readings[1], 'resetsAt': 20000}}}})
    score, why = fdy.router.score('codex', windows, fdy.config(), [], now=1000)
    assert score is None and 'invalid' in why


@pytest.mark.parametrize('window', ['seven_day', 'five_hour'])
@pytest.mark.parametrize('used', [None, False, float('nan')])
def test_expired_window_does_not_authorize_unknown_usage(fdy, window, used):
    windows = {'seven_day': {'used': 20, 'resets': 20000}, window: {'used': used, 'resets': 1}}
    score, why = fdy.router.score('codex', windows, fdy.config(), [], now=1000)
    assert score is None and 'invalid' in why


@pytest.mark.parametrize('source', ['codex', 'cache', 'cache-new', 'events'])
@pytest.mark.parametrize('percent', [0.5, 69, 100])
def test_provider_reading_preserves_valid_finite_percentages(fdy, source, percent, tmp_path):
    value = percent / 100 if source == 'events' else percent
    assert provider_reading(fdy.router, source, value, tmp_path)['seven_day']['used'] == percent


def test_invalid_reading_is_visible_as_unknown_in_usage_status(fdy):
    with open(os.environ['FOUNDRY_USAGE_FILE'], 'w') as stream:
        json.dump({'codex': {'seven_day': {'used': None, 'resets': 4070908800.0}}}, stream)
    lines = fdy.usage_lines()
    assert any('Codex' in line and 'unknown' in line for line in lines)
    assert any('none can start' in line and 'usage' in line for line in lines)


def test_codex_limit_record_keeps_known_reset_beside_invalid_reading(fdy):
    notes = {}
    fdy.router.record(notes, fdy.config(), 'checker', 'codex', 0, ok=False, limit=True,
                      windows={'seven_day': {'used': None, 'resets': 20000},
                               'five_hour': {'used': 100, 'resets': 3000}}, now=1000)
    assert notes['codex']['closed_until'] == 3000


@pytest.mark.parametrize('fixture_name', ['fdy', 'rf'])
@pytest.mark.parametrize('reset', [False, True, float('nan'), float('inf'), 'yesterday', {}])
def test_invalid_reset_cannot_clear_exhausted_usage_at_launch(fixture_name, reset, request, monkeypatch):
    board = request.getfixturevalue(fixture_name)
    board.cmd_add([SUB])
    with open(os.environ['FOUNDRY_USAGE_FILE'], 'w') as stream:
        json.dump({'codex': {'seven_day': {'used': 99, 'resets': reset}}}, stream)
    monkeypatch.setattr(board.subprocess, 'Popen', lambda *a, **k: pytest.fail('invalid reset authorized a worker'))
    with pytest.raises(SystemExit, match='usage.*invalid'):
        board.cmd_run('checker', SUB, on='codex')
    assert not board.load(SUB)['jobs']


@pytest.mark.parametrize('reset', [None, 1, 1.5])
def test_valid_reset_semantics_are_preserved(fdy, reset):
    cfg = fdy.config()
    cfg['weekly_launch_cap'] = 70
    score, _ = fdy.router.score('codex', {'seven_day': {'used': 99, 'resets': reset}},
                                cfg, [], now=1000)
    assert (score is None) == (reset is None)


@pytest.mark.parametrize('reset', [False, True, float('nan'), float('inf'), 'yesterday', {}])
def test_invalid_reset_status_and_limit_record_preserve_known_reset(fdy, reset):
    windows = {'seven_day': {'used': 99, 'resets': reset},
               'five_hour': {'used': 100, 'resets': 3000}}
    with open(os.environ['FOUNDRY_USAGE_FILE'], 'w') as stream:
        json.dump({'codex': windows}, stream)
    assert any('next job: none' in line for line in fdy.usage_lines())
    notes = {}
    fdy.router.record(notes, fdy.config(), 'checker', 'codex', 0, ok=False, limit=True,
                      windows=windows, now=1000)
    assert notes['codex']['closed_until'] == 3000


@pytest.mark.parametrize('reset', [False, 'yesterday', {}])
def test_invalid_reset_does_not_crash_claude_reading_learning(fdy, reset):
    notes = {'claude': {'windows': {'seven_day': {'used': 10, 'spent': 1, 'resets': 3000}}}}
    fdy.router.record(notes, fdy.config(), 'checker', 'claude', 0, ok=True,
                      windows={'seven_day': {'used': 20, 'resets': reset}}, now=1000)
    windows = notes['claude']['windows']
    score, why = fdy.router.score('claude', windows, fdy.config(), [], now=1000)
    assert score is None and 'invalid' in why


@pytest.mark.parametrize('fixture_name', ['fdy', 'rf'])
@pytest.mark.parametrize('invalid_first', [False, True])
@pytest.mark.parametrize('reset', [False, float('nan')])
@pytest.mark.parametrize('invalid_used', [10, 99])
def test_duplicate_codex_reading_cannot_hide_invalid_reset_at_launch(
        fixture_name, invalid_first, reset, invalid_used, request, monkeypatch):
    board = request.getfixturevalue(fixture_name)
    board.cmd_add([SUB])
    valid = {'windowDurationMins': 10080, 'usedPercent': 99, 'resetsAt': 1}
    invalid = {'windowDurationMins': 10080, 'usedPercent': invalid_used, 'resetsAt': reset}
    first, second = (invalid, valid) if invalid_first else (valid, invalid)
    windows = board.router.codex_windows({'rateLimits': {'secondary': first},
        'rateLimitsByLimitId': {'other': {'secondary': second}}})
    with open(os.environ['FOUNDRY_USAGE_FILE'], 'w') as stream:
        json.dump({'codex': windows}, stream)
    monkeypatch.setattr(board.subprocess, 'Popen', lambda *a, **k: pytest.fail('duplicate hid invalid reset and authorized work'))
    with pytest.raises(SystemExit, match='usage.*invalid'):
        board.cmd_run('checker', SUB, on='codex')
    assert not board.load(SUB)['jobs']


@pytest.mark.parametrize('higher_first', [False, True])
def test_valid_duplicate_codex_readings_keep_highest_usage(fdy, higher_first):
    low = {'windowDurationMins': 10080, 'usedPercent': 10, 'resetsAt': 1}
    high = {'windowDurationMins': 10080, 'usedPercent': 99, 'resetsAt': 20000}
    first, second = (high, low) if higher_first else (low, high)
    windows = fdy.router.codex_windows({'rateLimits': {'secondary': first},
        'rateLimitsByLimitId': {'other': {'secondary': second}}})
    assert windows['seven_day']['used'] == 99
    assert windows['seven_day']['resets'] == 20000
    cfg = fdy.config()
    cfg['weekly_launch_cap'] = 90
    assert fdy.router.score('codex', windows, cfg, [], now=1000)[0] is None
