"""Job settings can resume budget stops without erasing stage or guard evidence."""
import json
import os
from types import SimpleNamespace

import pytest

from test_extraction_budget import planned
from test_extraction import complete_coverage


def test_existing_budget_stop_can_change_phase_without_erasing_evidence(tmp_path, monkeypatch):
    ex = planned(tmp_path, monkeypatch, 20)
    with ex.state_lock('budget') as state:
        state['jobs']['extract'].update(exit=0, finished='saved', command=['saved-maker'])
        state['reliability_failures'] = {'1': {'review': [{'issues': ['old failure']}]}}
        state['reliability_history'] = [{'reason': 'earlier operator decision'}]
    before = ex.load('budget')
    for stop in (1, 40):
        assert ex.main(['configure', 'budget', '--codex-stop-remaining', str(stop),
                        '--reason', 'Explicit two-phase budget authorization']) == 0
        after = ex.load('budget')
        for key in ('jobs', 'sources', 'stage', 'reliability_failures', 'reliability_history'):
            assert after[key] == before[key]
        assert after['history'][:len(before['history'])] == before['history']
        assert after['codex_stop_remaining'] == stop
        assert after['configuration_history'][-1]['reason'] == 'Explicit two-phase budget authorization'


def test_budget_configuration_does_not_release_failure_guard(tmp_path, monkeypatch):
    ex = planned(tmp_path, monkeypatch, 20)
    with ex.state_lock('budget') as state:
        state['reliability_failures'] = {'1': {'extract': [{'issues': ['failed']}] * 2}}
    assert ex.main(['configure', 'budget', '--codex-stop-remaining', '1',
                    '--reason', 'Budget only']) == 0
    with pytest.raises(ValueError, match='paused after 2 failures'):
        ex.run('budget', weekly_remaining=10)


def test_budget_only_stop_resumes_missing_review_without_reextracting(tmp_path, monkeypatch):
    ex = planned(tmp_path, monkeypatch, 20)
    with ex.state_lock('budget') as state:
        state['jobs']['extract'].update(exit=0, finished='saved', command=['saved-maker'])
        candidate = ex.candidate_path(state)
        candidate.parent.mkdir(parents=True)
        coverage = complete_coverage(state)
        coverage[0].update(no_relevant_content=True, reason='Synthetic source contains no questions or diagrams')
        candidate.write_text(json.dumps({'questions': [], 'diagrams': [], 'source_coverage': coverage}))
    before = ex.load('budget')
    candidate_bytes = candidate.read_bytes()
    with pytest.raises(ValueError, match='weekly'):
        ex.run('budget', weekly_remaining=10)
    assert ex.load('budget') == before
    assert ex.main(['configure', 'budget', '--reason', 'Authorized pre-reset boundary',
                    '--codex-stop-remaining', '1', '--codex-review-model', 'gpt-6.1-sol',
                    '--codex-review-effort', 'high']) == 0
    monkeypatch.setattr(ex.subprocess, 'Popen', lambda *a, **k: SimpleNamespace(pid=99999999))
    state = ex.run('budget', weekly_remaining=10)
    assert state['stage'] == 'reviewing'
    assert state['jobs']['extract'] == before['jobs']['extract']
    assert state['jobs']['review']['weekly_remaining'] == 10
    assert candidate.read_bytes() == candidate_bytes


def test_job_local_role_models_override_legacy_fallback_without_rewriting_attempts(tmp_path, monkeypatch):
    ex = planned(tmp_path, monkeypatch, 20)
    monkeypatch.setenv('STEM_EXTRACT_CODEX', '/disposable/fake-codex')
    with ex.state_lock('budget') as state:
        state.update(codex_model='old-model', codex_effort='low')
        state['jobs']['extract'].update(exit=0, finished='saved', command=['saved-maker'])
    before = ex.load('budget')
    assert ex.main(['configure', 'budget', '--reason', 'Authorized extraction/review tiers',
                    '--codex-extract-model', 'gpt-6.1-sol', '--codex-extract-effort', 'medium',
                    '--codex-review-model', 'gpt-6.1-sol', '--codex-review-effort', 'high']) == 0
    after = ex.load('budget')
    assert after['jobs'] == before['jobs']
    assert after['codex_model'] == 'old-model' and after['codex_effort'] == 'low'
    for role, effort in [('extract', 'medium'), ('review', 'high')]:
        command = ex.worker_command(after, role)
        assert command[command.index('-m') + 1] == 'gpt-6.1-sol'
        assert f'model_reasoning_effort="{effort}"' in command
    legacy = ex.worker_command(before, 'review')
    assert legacy[legacy.index('-m') + 1] == 'old-model'
    assert 'model_reasoning_effort="low"' in legacy


@pytest.mark.parametrize('options', [
    ['--codex-stop-remaining', '0'], ['--codex-stop-remaining', 'nan'],
    ['--codex-extract-model', ' '], [],
])
def test_invalid_configuration_preserves_state_bytes(tmp_path, monkeypatch, options):
    ex = planned(tmp_path, monkeypatch, 20)
    path = ex.job_dir('budget') / 'state.json'
    before = path.read_bytes()
    assert ex.main(['configure', 'budget', '--reason', 'Authorized', *options]) == 1
    assert path.read_bytes() == before


def test_configuration_refuses_running_worker_and_missing_reason(tmp_path, monkeypatch):
    ex = planned(tmp_path, monkeypatch, 20)
    with ex.state_lock('budget') as state:
        state['jobs']['extract']['pid'] = os.getpid()
    path = ex.job_dir('budget') / 'state.json'
    before = path.read_bytes()
    assert ex.main(['configure', 'budget', '--reason', 'Boundary change',
                    '--codex-stop-remaining', '1']) == 1
    assert path.read_bytes() == before
    with ex.state_lock('budget') as state:
        state['jobs']['extract']['finished'] = 'saved'
    before = path.read_bytes()
    assert ex.main(['configure', 'budget', '--reason', ' ', '--codex-stop-remaining', '1']) == 1
    assert path.read_bytes() == before
