"""Actual board launch/collection boundaries use synthetic inputs and no AI."""
import json
from types import SimpleNamespace

import pytest

from test_refine import rf, SUB
from test_foundry import fdy
from tutor_workers import reliability


def test_refine_protected_pdf_damage_blocks_direct_launch(rf, monkeypatch):
    rf.cmd_add([SUB])
    pack = json.loads(rf.pack_path(SUB).read_text())
    pack['items'][0]['stem'] = 'A value is 2\x01 10.'
    rf.pack_path(SUB).write_text(json.dumps(pack))
    with rf.chapter(SUB) as st:
        st['scope'] = 'lessons'
    monkeypatch.setattr(rf.subprocess, 'Popen', lambda *a, **k: pytest.fail('must not spend'))
    with pytest.raises(SystemExit, match='baseline PDF debris'):
        rf.cmd_run('scout', SUB)


def test_missing_baseline_blocks_paid_launch_without_recreating_it(rf, monkeypatch):
    rf.cmd_add([SUB])
    rf.snap_path(SUB).unlink()
    monkeypatch.setattr(rf.subprocess, 'Popen', lambda *a, **k: pytest.fail('must not spend'))
    with pytest.raises(SystemExit, match='baseline'):
        rf.cmd_run('scout', SUB)
    assert not rf.snap_path(SUB).exists()


@pytest.mark.parametrize('fixture_name,role', [('rf', 'scout'), ('fdy', 'drafter')])
def test_direct_launch_cannot_bypass_failed_job_cap(request, fixture_name, role, monkeypatch):
    board = request.getfixturevalue(fixture_name)
    board.cmd_add([SUB])
    with board.chapter(SUB) as st:
        for code in (124, 1):
            reliability.record_result(st, role, ok=False, exit_code=code, issues=['bad'])
    monkeypatch.setattr(board.subprocess, 'Popen', lambda *a, **k: pytest.fail('must not spend'))
    with pytest.raises(SystemExit, match='paused'):
        board.cmd_run(role, SUB)


def test_refine_repeated_gates_preserve_candidate(rf, monkeypatch):
    rf.cmd_add([SUB])
    pack = rf.pack_path(SUB)
    original = pack.read_bytes()
    with rf.chapter(SUB) as st:
        rf.move(st, 'refine')
        for _ in range(3):
            st['history'].append({'t': rf.now(), 'from': 'refine', 'to': 'refine',
                                  'note': 'refiner finished but gates are not clean: bad'})
    monkeypatch.setattr(rf, 'give_up', lambda *a: pytest.fail('must preserve work'))
    rf.cmd_step([SUB])
    assert pack.read_bytes() == original
    assert rf.load(SUB)['stage'] == 'refine'


def test_foundry_fast_collect_keeps_finished_job(fdy, monkeypatch):
    fdy.cmd_add([SUB])
    def immediate(*args, **kwargs):
        with fdy.chapter(SUB) as st:
            assert st['jobs']['drafter']['provider']
            st['jobs']['drafter'].update(finished=fdy.now(), exit=0, ok=True)
        return SimpleNamespace(pid=99999999)
    monkeypatch.setattr(fdy.subprocess, 'Popen', immediate)
    fdy.cmd_run('drafter', SUB)
    assert fdy.load(SUB)['jobs']['drafter']['finished']
    assert fdy.load(SUB)['jobs']['drafter']['ok']


def test_collection_gate_exception_finishes_job_and_counts_failure(rf, monkeypatch, tmp_path):
    rf.cmd_add([SUB])
    out = tmp_path / 'report.json'
    out.write_text('{"done": true}')
    with rf.chapter(SUB) as st:
        st['jobs']['refiner'] = {'started': rf.now(), 'provider': 'codex', 'rung': 0}
    monkeypatch.setattr(rf.fd, 'settle_glyphs', lambda *a, **k: (_ for _ in ()).throw(ValueError('invalid card')))
    rf.cmd_collect('refiner', SUB, str(out))
    st = rf.load(SUB)
    assert st['jobs']['refiner']['finished']
    assert st['jobs']['refiner']['ok'] is False
    assert st['reliability_failures']


def test_extraction_launch_failures_are_persisted_and_bounded(tmp_path, monkeypatch):
    from test_extraction import extraction
    ex = extraction()
    monkeypatch.setenv('STEM_EXTRACT_ROOT', str(tmp_path / 'Work'))
    ex.create('broken', '9701', provider='codex')
    with ex.state_lock('broken') as st:
        st['jobs'] = {'extract': {'provider': 'codex'}, 'review': {'provider': 'codex'}}
        st['sources'] = []
    monkeypatch.setattr(ex, '_verify_sources', lambda st: None)
    monkeypatch.setattr(ex, 'worker_command', lambda *a, **k: ['fake'])
    monkeypatch.setattr(ex, '_prompt', lambda *a: 'test')
    monkeypatch.setattr(ex.subprocess, 'Popen', lambda *a, **k: (_ for _ in ()).throw(OSError('missing binary')))
    for _ in range(2):
        result = ex.run('broken', weekly_remaining=95)
        assert result['jobs']['extract']['exit'] == -1
    with pytest.raises(ValueError, match='paused'):
        ex.run('broken', weekly_remaining=95)
    assert ex.load('broken')['reliability_failures']


def test_failed_validation_never_counts_as_completed_job(tmp_path):
    from tutor_workers import lifecycle
    path = tmp_path / 'answer.json'
    path.write_text('{}')
    st = {'stage': 'solve', 'created': '2026-10-30T00:00:00+00:00', 'history': [],
          'jobs': {'solver': {'finished': '2026-10-31T00:00:00+00:00', 'exit': 0,
                              'ok': False, 'expects': path.name}}}
    assert not lifecycle.job_completed(st, 'solver', tmp_path)


@pytest.mark.parametrize('fixture_name', ['rf', 'fdy'])
def test_failed_tiebreak_validation_does_not_advance_to_compare(request, fixture_name):
    board = request.getfixturevalue(fixture_name)
    board.cmd_add([SUB])
    with board.chapter(SUB) as st:
        board.move(st, 'tiebreak')
        st['jobs']['tiebreak'] = {'exit': 0, 'finished': board.now(), 'ok': False}

    assert board.todo(board.load(SUB)) == ('run', 'tiebreak')


@pytest.mark.parametrize('fixture_name', ['rf', 'fdy'])
def test_compare_refuses_failed_tiebreak_evidence(request, fixture_name):
    board = request.getfixturevalue(fixture_name)
    board.cmd_add([SUB])
    pack = json.loads(board.pack_path(SUB).read_text())
    item = pack['items'][0]
    board.BLIND.mkdir(parents=True, exist_ok=True)
    prefix = board.PFX if fixture_name == 'rf' else ''
    artifact = board.BLIND / f'{SUB}.{prefix}tiebreak.json'
    artifact.write_text(json.dumps({item['id']: str(item['answer'])}))
    with board.chapter(SUB) as st:
        board.move(st, 'tiebreak')
        st['jobs']['tiebreak'] = {'exit': 0, 'finished': board.now(), 'ok': False}
        st['disputes'] = [{'id': item['id'], 'status': 'open', 'key': item['answer'], 'solver': '?'}]

    with pytest.raises(SystemExit, match='tiebreak.*not.*validated'):
        board.cmd_compare(SUB)
    assert board.load(SUB)['stage'] == 'tiebreak'
    assert board.load(SUB)['disputes'][0]['status'] == 'open'


def test_collection_error_outside_gates_is_finalized(rf, monkeypatch, tmp_path):
    import evidence
    rf.cmd_add([SUB])
    out = tmp_path / 'report.json'
    out.write_text('{"done": true}')
    with rf.chapter(SUB) as st:
        st['jobs']['solver'] = {'started': rf.now(), 'provider': 'codex', 'rung': 0}
    monkeypatch.setattr(evidence, 'missing', lambda *a: (_ for _ in ()).throw(ValueError('source unavailable')))
    rf.cmd_collect('solver', SUB, str(out))
    job = rf.load(SUB)['jobs']['solver']
    assert job['finished'] and job['ok'] is False and job['exit'] == -1


def test_malformed_solver_artifact_is_failed_not_completed(rf, tmp_path):
    rf.cmd_add([SUB])
    artifact = rf.ROOT / 'bad.answers.json'
    artifact.write_text('not JSON')
    out = tmp_path / 'report.json'
    out.write_text('{"done": true}')
    with rf.chapter(SUB) as st:
        st['jobs']['solver'] = {'started': rf.now(), 'provider': 'codex', 'rung': 0, 'expects': artifact.name}
    rf.cmd_collect('solver', SUB, str(out))
    assert rf.load(SUB)['jobs']['solver']['ok'] is False
