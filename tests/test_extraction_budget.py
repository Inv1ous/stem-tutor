"""Explicit Codex job reserves do not change shared provider defaults."""
from types import SimpleNamespace

import pytest

from test_extraction import ROOT, extraction, make_pdf


def planned(tmp_path, monkeypatch, stop=None):
    ex = extraction()
    monkeypatch.setenv('STEM_EXTRACT_ROOT', str(tmp_path / 'Work'))
    monkeypatch.setenv('STEM_LIBRARY_ROOT', str(tmp_path / 'sources'))
    make_pdf(tmp_path / 'sources/book.pdf', ['Synthetic extraction budget input'])
    ex.create('budget', '9702', provider='codex', codex_stop_remaining=stop)
    ex.inventory('budget')
    ex.plan('budget')
    return ex


@pytest.mark.parametrize('stop,remaining,launches', [
    (None, 25, False), (None, 31, True),
    (20, 20, False), (20, 21, True), (20, 25, True),
    (20, None, False), (20, float('nan'), False), (20, 101, False),
])
def test_job_stop_boundary_requires_real_allowance_without_changing_defaults(tmp_path, monkeypatch, stop, remaining, launches):
    config = (ROOT / 'foundry/config.json').read_bytes()
    ex = planned(tmp_path, monkeypatch, stop)
    calls = []
    def start(*args, **kwargs):
        calls.append(True)
        return SimpleNamespace(pid=99999999)
    monkeypatch.setattr(ex.subprocess, 'Popen', start)
    if launches:
        state = ex.run('budget', weekly_remaining=remaining)
        assert state['jobs']['extract']['weekly_remaining'] == remaining
    else:
        with pytest.raises(ValueError, match='weekly'):
            ex.run('budget', weekly_remaining=remaining)
    assert len(calls) == int(launches)
    assert (ROOT / 'foundry/config.json').read_bytes() == config
    assert ex.load('budget').get('codex_stop_remaining') == stop


@pytest.mark.parametrize('invalid', [True, 19, 100, float('nan'), float('inf'), '20'])
def test_invalid_job_stop_boundary_cannot_be_persisted(tmp_path, monkeypatch, invalid):
    ex = extraction()
    monkeypatch.setenv('STEM_EXTRACT_ROOT', str(tmp_path / 'Work'))
    with pytest.raises(ValueError, match='stop'):
        ex.create('invalid', '9702', provider='codex', codex_stop_remaining=invalid)
    assert not (ex.job_dir('invalid') / 'state.json').exists()


def test_codex_job_override_does_not_change_claude_boundary(tmp_path, monkeypatch):
    ex = planned(tmp_path, monkeypatch, 20)
    with ex.state_lock('budget') as state:
        state['jobs']['extract']['provider'] = 'claude'
    monkeypatch.setattr(ex.subprocess, 'Popen', lambda *a, **k: pytest.fail('Codex reserve authorized Claude work'))
    with pytest.raises(ValueError, match='weekly'):
        ex.run('budget', weekly_remaining=25)


def test_cli_persists_explicit_job_reserve(tmp_path, monkeypatch):
    ex = extraction()
    monkeypatch.setenv('STEM_EXTRACT_ROOT', str(tmp_path / 'Work'))
    assert ex.main(['new', 'cli', '--course', '9702', '--provider', 'codex',
                    '--codex-stop-remaining', '20']) == 0
    assert ex.load('cli')['codex_stop_remaining'] == 20


def test_corrupted_job_boundary_cannot_launch(tmp_path, monkeypatch):
    ex = planned(tmp_path, monkeypatch, 20)
    with ex.state_lock('budget') as state:
        state['codex_stop_remaining'] = 19
    monkeypatch.setattr(ex.subprocess, 'Popen', lambda *a, **k: pytest.fail('Invalid reserve authorized a worker'))
    with pytest.raises(ValueError, match='stop'):
        ex.run('budget', weekly_remaining=90)
