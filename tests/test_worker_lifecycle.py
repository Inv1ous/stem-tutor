"""Shared workflow mechanics on isolated artifacts; no AI workers are launched."""
from datetime import datetime
from pathlib import Path
import sys

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'src'))
from tutor_workers import lifecycle
from tutor_workers.locations import WorkerLocations, chapter_pack, spec_of


EARLY = '2026-10-30T09:00:00+08:00'
ENTERED = '2026-10-30T10:00:00+08:00'
LATER = '2026-10-30T11:00:00+08:00'


def state(stage='solve'):
    return {'stage': stage, 'created': EARLY, 'history': [], 'jobs': {}}


def test_locations_keep_data_override_separate_from_executable_checkout(tmp_path):
    repo = tmp_path / 'checkout'
    data = tmp_path / 'scratch-data'
    locations = WorkerLocations.from_environment(repo, {'FOUNDRY_ROOT': str(data)})
    assert locations.repository == repo
    assert locations.data_root == data
    assert locations.python == str(repo / '.venv/bin/python')
    assert locations.state('foundry') == data / 'foundry/state'
    assert locations.state('refine') == data / 'refine/state'
    assert locations.logs('refine') == data / 'refine/logs'
    assert locations.work('refine') == data / 'build/work/refine'
    assert locations.blind == data / 'build/work/blind'
    assert locations.packs == data / 'build/out/packs'
    assert locations.specs == data / 'build/out/specs'
    assert locations.notes == data / 'build/out/notes'
    assert locations.usage == data / 'foundry/usage.json'
    assert not data.exists()


def test_default_locations_preserve_current_paths_and_reject_unknown_workflows(tmp_path):
    locations = WorkerLocations.from_environment(tmp_path, {})
    assert locations.data_root == tmp_path
    assert chapter_pack(locations.packs, '9702-2.1') == tmp_path / 'build/out/packs/9702/9702-2.1.json'
    assert spec_of('P1-2') == 'P1'
    with pytest.raises(ValueError, match='unknown'):
        locations.state('../learner')


def test_stage_reentry_invalidates_older_jobs_but_self_transition_does_not(tmp_path):
    st = state('solve')
    lifecycle.transition(st, 'check', at=EARLY)
    lifecycle.transition(st, 'solve', at=ENTERED)
    lifecycle.transition(st, 'solve', 'extra note', at=LATER)
    assert lifecycle.stage_started(st) == datetime.fromisoformat(ENTERED).timestamp()
    artifact = tmp_path / 'answers.json'
    artifact.write_text('{}')
    st['jobs']['solver'] = {'exit': 0, 'finished': EARLY, 'expects': 'answers.json'}
    assert not lifecycle.job_completed(st, 'solver', tmp_path)
    st['jobs']['solver']['finished'] = ENTERED
    assert lifecycle.job_completed(st, 'solver', tmp_path)
    assert st['history'][-1]['note'] == 'extra note'


def test_job_completion_requires_success_expected_artifact_and_current_stage(tmp_path):
    st = state()
    st['jobs']['solver'] = {'exit': 0, 'finished': LATER, 'expects': 'answers.json'}
    assert not lifecycle.job_completed(st, 'solver', tmp_path)
    (tmp_path / 'answers.json').write_text('{}')
    assert lifecycle.job_completed(st, 'solver', tmp_path)
    st['jobs']['solver']['exit'] = 1
    assert not lifecycle.job_completed(st, 'solver', tmp_path)
    st['jobs']['solver']['exit'] = 0
    st['jobs']['solver'].pop('expects')
    assert not lifecycle.job_completed(st, 'solver', tmp_path)
    assert not lifecycle.job_completed(st, 'missing', tmp_path)


def test_manual_and_live_jobs_block_but_finished_or_dead_workers_do_not():
    st = state()
    st['jobs'] = {'manual': {'manual': True}, 'live': {'pid': 101}, 'dead': {'pid': 102},
                  'finished-zombie': {'pid': 101, 'finished': LATER}, 'unstarted': {}}
    assert lifecycle.running_jobs(st, is_alive=lambda pid: pid == 101) == ['manual', 'live']


def test_tiebreak_requires_success_since_latest_tiebreak_entry():
    st = state('tiebreak')
    lifecycle.transition(st, 'solve', at=EARLY)
    lifecycle.transition(st, 'tiebreak', at=ENTERED)
    st['jobs']['tiebreak'] = {'exit': 0, 'finished': EARLY}
    assert not lifecycle.tiebreak_completed(st)
    st['jobs']['tiebreak']['finished'] = LATER
    assert lifecycle.tiebreak_completed(st)
    st['jobs']['tiebreak']['exit'] = 1
    assert not lifecycle.tiebreak_completed(st)


@pytest.mark.parametrize(('finished', 'expected'), [
    ('2026-10-30T02:01:00+00:00', True),
    ('2026-10-30T11:00:00+09:00', True),
    ('2026-10-30T10:59:00+09:00', False),
])
def test_tiebreak_freshness_compares_instants_across_timezones(finished, expected):
    st = state('solve')
    lifecycle.transition(st, 'tiebreak', at=ENTERED)
    st['jobs']['tiebreak'] = {'exit': 0, 'finished': finished, 'ok': True}
    assert lifecycle.tiebreak_completed(st) is expected


def test_process_liveness_preserves_missing_and_dead_pid_rules(monkeypatch):
    calls = []
    monkeypatch.setattr(lifecycle.os, 'kill', lambda pid, signal: calls.append((pid, signal)))
    assert not lifecycle.process_alive(None)
    assert not lifecycle.process_alive(0)
    assert lifecycle.process_alive(123)
    assert calls == [(123, 0)]
    monkeypatch.setattr(lifecycle.os, 'kill', lambda *args: (_ for _ in ()).throw(ProcessLookupError()))
    assert not lifecycle.process_alive(123)
