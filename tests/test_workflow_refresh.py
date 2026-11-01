"""Workflow refresh regressions; all files and workers are disposable."""
import copy
import json
import time
from pathlib import Path

import pytest

from test_refine import rf, SUB, NOTE
from test_foundry import fdy


def test_course_budget_persists_across_chapters_and_restarts(tmp_path):
    from tutor_workers import lifecycle
    assert lifecycle.course_remaining(tmp_path, '9709-1.1', 7200, at=100) == 7200
    assert lifecycle.course_remaining(tmp_path, '9709-2.1', 7200, at=110) == 7190
    assert lifecycle.course_remaining(tmp_path, '9709-9.1', 7200, at=7301) == 0
    assert lifecycle.course_remaining(tmp_path, '9702-2.1', 7200, at=9000) is None


def test_reserve_requires_known_weekly_usage_and_stops_before_75_percent(fdy):
    cfg = fdy.config()
    cfg["weekly_launch_cap"] = 70
    import router
    for windows in (None, {'five_hour': {'used': 1}}, {'seven_day': {'used': 74, 'resets': time.time() + 9000}}):
        score, why = router.score('claude', windows, cfg, [], own=3)
        assert score is None and why


def test_new_scope_is_persisted_and_running_legacy_pass_is_unchanged(rf):
    rf.cmd_add([SUB])
    assert rf.load(SUB)['scope'] == 'lessons'
    with rf.chapter(SUB) as st:
        st.pop('scope')
    rf.cmd_add([SUB, '--scope', 'full'])
    assert 'scope' not in rf.load(SUB)


def test_lessons_scope_protects_note_bytes_items_but_allows_guided_fields(rf):
    rf.cmd_add([SUB])
    before = rf.snapshot(SUB)
    candidate = copy.deepcopy(before['pack'])
    candidate['guided_forms'] = [{'id': 'test-form'}]
    assert rf.scope_problems('lessons', before, candidate, NOTE) == []
    candidate['items'][0]['explanation'] = 'changed'
    assert any('items' in p for p in rf.scope_problems('lessons', before, candidate, NOTE))
    assert any('note' in p for p in rf.scope_problems('lessons', before, before['pack'], NOTE + '\n'))


def test_library_file_adapter_gets_fresh_candidate_and_baseline_survives(rf, tmp_path):
    adapter = rf.pack_path(SUB)
    data = adapter.read_bytes()
    resource = tmp_path / 'STEM Tutor/Library/Courses/9702/pack.json'
    resource.parent.mkdir(parents=True)
    from tutorlib.asset_library import write_asset
    write_asset(tmp_path / "STEM Tutor", resource.relative_to(tmp_path / "STEM Tutor").as_posix(), data)
    adapter.unlink()
    adapter.symlink_to(resource)
    rf.cmd_add([SUB])
    candidate = rf.pack_path(SUB)
    assert candidate != adapter and not candidate.is_symlink()
    assert 'Preparation' in str(candidate)
    candidate.write_text('{}')
    assert resource.read_bytes() == data
    assert rf.snapshot(SUB)['pack'] == json.loads(data)


def test_queue_uses_teaching_preparation_not_audio_age(rf):
    rf.cmd_add([SUB])
    queue = rf.preparation_queue()
    assert queue[0]['sub'] == SUB
    assert queue[0]['prepared_at'] is None
    assert queue[0]['age'] == 'unknown'
    assert 'speech' not in queue[0]


def test_deadline_blocks_signing_instead_of_marking_pending_ready(fdy, tmp_path):
    sub = '9709-1.1'
    from tutor_workers import lifecycle
    lifecycle.course_remaining(fdy.STATE, sub, 7200, at=1)
    with pytest.raises(SystemExit, match='deadline'):
        fdy.cmd_sign(sub)


def test_timeout_supervisor_terminates_worker(tmp_path):
    import sys
    from tutor_workers.timeout import run
    path = tmp_path / 'should-not-exist'
    assert run(0.02, [sys.executable, '-c', f'import time; time.sleep(1); open({str(path)!r}, "w").write("late")']) == 124
    assert not path.exists()


def test_lesson_scope_detects_subject_note_line_ending_change(rf):
    note = rf.note_path(json.loads(rf.pack_path(SUB).read_text()))
    note.write_bytes(NOTE.replace('\n', '\r\n').encode())
    rf.cmd_add([SUB])
    note.write_bytes(NOTE.encode())
    assert any('bytes' in problem for problem in rf.gates(SUB).get('first', []))


def test_queue_missing_before_ready_and_recorded_age_then_syllabus_order(rf):
    rf.cmd_add([SUB])
    with rf.chapter(SUB) as state:
        state['prepared_at'] = '2020-01-01T00:00:00+00:00'
    row = rf.preparation_queue()[0]
    assert row['prepared_at'] == '2020-01-01T00:00:00+00:00'
    assert not row['guided_prepared']


def test_candidate_copy_rejects_tampered_library_resource(tmp_path):
    from tutor_workers import candidates
    from tutorlib.asset_library import write_asset
    vault = tmp_path / 'vault'
    vault.mkdir()
    relative = 'Library/Courses/9702/pack.json'
    write_asset(vault, relative, b'{"subtopic":"9702-2.1"}')
    source = vault / relative
    source.write_bytes(b'{"tampered":true}')
    with pytest.raises(ValueError, match='hash|digest|SHA'):
        candidates.prepare(tmp_path, 'refine', SUB, source, tmp_path / 'absent-note')


def test_expired_course_queue_does_not_retry_or_sleep(fdy, monkeypatch):
    from tutor_workers import lifecycle
    sub = 'P1-1'
    lifecycle.course_remaining(fdy.STATE, sub, 7200, at=1)
    monkeypatch.setattr(fdy, 'cmd_add', lambda subs: None)
    sleeps = []
    monkeypatch.setattr(fdy.time, 'sleep', lambda wait: sleeps.append(wait))
    fdy.cmd_queue('drafter', [sub], wait=0, tries=2)
    assert sleeps == []


@pytest.mark.parametrize('workflow,provider', [('foundry', 'codex'), ('foundry', 'claude'), ('refine', 'codex'), ('refine', 'claude')])
def test_worker_grants_exact_external_candidate_and_artifact_dirs(workflow, provider, request, tmp_path, monkeypatch):
    from types import SimpleNamespace
    mod = request.getfixturevalue('fdy' if workflow == 'foundry' else 'rf')
    mod.cmd_add([SUB])
    folder = tmp_path.parent / (tmp_path.name + '-external') / 'Work/Preparation/candidate'
    folder.mkdir(parents=True)
    pack = folder / 'pack.json'
    pack.write_bytes(mod.pack_path(SUB).read_bytes())
    note = folder / 'note.md'
    note.write_text(NOTE)
    with mod.chapter(SUB) as state:
        state.update(candidate_pack=str(pack), candidate_note=str(note))
    shells = []
    monkeypatch.setattr(mod.subprocess, 'Popen', lambda args, **kwargs: shells.append(args[-1]) or SimpleNamespace(pid=0))
    mod.cmd_run('checker', SUB, on=provider)
    import shlex
    argv = shlex.split(shells[0].split(' < /dev/null')[0])
    grants = [argv[index+1] for index, arg in enumerate(argv[:-1]) if arg == '--add-dir']
    assert str(folder.resolve()) in grants
    assert str(mod.WORK.resolve()) in grants
    assert str(mod.BLIND.resolve()) in grants
    assert str(mod.STATE.resolve()) in grants
    assert str(mod.LOGS.resolve()) in grants
    assert all('Library' not in Path(path).parts for path in grants)


def test_explicit_new_course_run_archives_deadline_and_resume_keeps_it(tmp_path):
    from tutor_workers import lifecycle
    lifecycle.course_remaining(tmp_path, 'P1-1', 7200, at=1)
    before = json.loads((tmp_path / 'budgets/P1.json').read_text())
    lifecycle.new_course_run(tmp_path, 'P1', 7200, states=[], at=8000)
    assert lifecycle.course_remaining(tmp_path, 'P1-2', 7200, at=8001) == 7199
    assert lifecycle.course_remaining(tmp_path, 'P1-3', 7200, at=8010) == 7190
    assert any(json.loads(path.read_text())['deadline'] == before['deadline'] for path in (tmp_path / 'budgets/history/P1').glob('*.json'))


@pytest.mark.parametrize('state', [
    {'sub': 'P1-1', 'stage': 'ready', 'jobs': {'checker': {'manual': True}}},
])
def test_new_course_run_refuses_active_work(tmp_path, state):
    from tutor_workers import lifecycle
    with pytest.raises(SystemExit, match='pending|running'):
        lifecycle.new_course_run(tmp_path, 'P1', 7200, states=[state])


def test_preparation_readiness_requires_all_kcs_inventory_and_guided_checks(rf):
    rf.cmd_add([SUB])
    pack = json.loads(rf.pack_path(SUB).read_text())
    card = copy.deepcopy(pack['teach'][f'{SUB}.1'])
    card.update(plain_words='Explain the idea.', terms=[{'term': 'speed'}], forms=[{'name': 'form'}])
    pack['teach'] = {f'{SUB}.1': card}
    rf.pack_path(SUB).write_text(json.dumps(pack))
    row = rf.preparation_queue()[0]
    assert not row['guided_prepared']
    assert any('inventory' in reason for reason in row['missing_reasons'])
    assert any(f'{SUB}.4' in reason for reason in row['missing_reasons'])
    assert any('rubric' in reason for reason in row['missing_reasons'])


def test_explicit_new_run_renews_expired_pending_work_without_changing_chapters(tmp_path):
    from tutor_workers import lifecycle
    lifecycle.course_remaining(tmp_path, 'P1-1', 7200, at=1)
    state = {'sub': 'P1-1', 'stage': 'refine', 'jobs': {}, 'history': [{'note': 'unfinished'}]}
    before = copy.deepcopy(state)
    lifecycle.new_course_run(tmp_path, 'P1', 7200, states=[state], at=8000)
    assert lifecycle.course_remaining(tmp_path, 'P1-1', 7200, at=8010) == 7190
    assert state == before


def test_preparation_queue_keeps_missing_graph_as_unprepared(rf):
    rf.cmd_add([SUB])
    (rf.SPECS / '9702/graph.json').unlink()
    row = rf.preparation_queue()[0]
    assert not row['guided_prepared']
    assert 'expected syllabus KCs unavailable' in row['missing_reasons']


def test_new_foundry_job_requires_guided_preparation_before_signing(fdy):
    fdy.cmd_add([SUB])
    with fdy.chapter(SUB) as state:
        state['stage'] = 'sign'
    with pytest.raises(SystemExit, match='not ready'):
        fdy.cmd_sign(SUB)
    assert fdy.load(SUB)['teaching_contract'] == 'guided-v1'
    assert fdy.load(SUB)['gates']['guided'] > 0
    assert fdy.load(SUB)['stage'] == 'sign'


def test_new_complete_guided_foundry_job_requires_written_proof_before_signing(fdy):
    fdy.cmd_add([SUB])
    assert fdy.load(SUB)['teaching_contract'] == 'guided-v1'
    pack = json.loads(fdy.pack_path(SUB).read_text())
    inventory = {}
    for kc, card in pack['teach'].items():
        misconception = next(entry for entry in pack['misconceptions'] if entry['kc'] == kc)
        card.update(plain_words='A plain explanation.',
                    terms=[{'term': 'term', 'meaning': 'meaning', 'notation': 'none', 'spoken': 'term', 'source': 'synthetic fixture'}],
                    forms=[{'name': 'Fixture form', 'wordings': ['Calculate'], 'example': 'Worked example',
                            'check': 'Separate check', 'answer': 'Answer', 'source': 'synthetic fixture',
                            'rubric': [{'point': 'Correct reasoning', 'keywords': [['reasoning']]}]}],
                    misconceptions=[{'id': misconception['id'], 'idea': 'Incorrect idea', 'temptation': 'Why tempting', 'fix': 'Correction'}],
                    diagrams=[], diagram_reason='Synthetic fixture needs no diagram.')
        inventory[kc] = ['Fixture form']
    pack['guided_forms'] = inventory
    fdy.pack_path(SUB).write_text(json.dumps(pack))
    with fdy.chapter(SUB) as state:
        state['stage'] = 'sign'
    gates = fdy.gates(SUB)
    assert all(gates[key] == 0 for key in ('validator', 'lint', 'syllabus', 'figures', 'glyphs'))
    assert gates['guided'] == 1
    assert any('written checks need review records' in issue for issue in gates['first'])
    with pytest.raises(SystemExit, match='not ready'):
        fdy.cmd_sign(SUB)
    assert fdy.load(SUB)['stage'] == 'sign'
    assert fdy.load(SUB)['teaching_contract'] == 'guided-v1'


def test_preexisting_foundry_state_keeps_legacy_signing_contract(fdy):
    fdy.cmd_add([SUB])
    with fdy.chapter(SUB) as state:
        state.pop('teaching_contract', None)
        state['stage'] = 'sign'
    fdy.cmd_sign(SUB)
    assert fdy.load(SUB)['stage'] == 'ready'


@pytest.fixture
def lesson_visual(rf, tmp_path):
    from tutorlib.asset_library import write_asset
    import os
    vault = Path(os.environ['STEM_TUTOR_VAULT'])
    vault.mkdir(parents=True, exist_ok=True)
    relative = 'Library/Courses/9702/Diagrams/display.svg'
    write_asset(vault, relative, b'<svg xmlns="http://www.w3.org/2000/svg" width="80" height="40" viewBox="0 0 80 40"><path d="M8 32L72 8" stroke="black" stroke-width="2"/></svg>',
                metadata={'kind': 'Diagrams', 'generated': True, 'renderer': 'graph_sketch'})
    rf.cmd_add([SUB])
    pack = json.loads(rf.pack_path(SUB).read_text())
    pack['diagrams'] = [{'file': relative, 'type': 'graph_sketch', 'params': {}}]
    pack['teach'][f'{SUB}.1']['diagrams'] = [relative]
    pack['teach'][f'{SUB}.1']['diagram_descriptions'] = ['A line slopes upwards from the origin.']
    rf.pack_path(SUB).write_text(json.dumps(pack))
    return rf, vault / relative, relative


def test_lessons_visual_can_display_verified_card_diagram_without_note_edit(lesson_visual):
    rf, _, relative = lesson_visual
    note = rf.note_path(json.loads(rf.pack_path(SUB).read_text()))
    before = note.read_bytes()
    result = rf.gates(SUB)
    assert result['ok'], result.get('first')
    assert note.read_bytes() == before
    with rf.chapter(SUB) as state:
        state['scope'] = 'full'
    assert any('not embedded' in reason for reason in rf.gates(SUB).get('first', []))


@pytest.mark.parametrize('damage', ['unused', 'missing', 'hash', 'description', 'provenance'])
def test_lessons_visual_keeps_binding_render_and_integrity_gates(lesson_visual, damage):
    rf, image, relative = lesson_visual
    pack = json.loads(rf.pack_path(SUB).read_text())
    if damage == 'unused':
        pack['teach'][f'{SUB}.1'].pop('diagrams')
    elif damage == 'description':
        pack['teach'][f'{SUB}.1'].pop('diagram_descriptions')
    elif damage == 'provenance':
        catalog_path = next(parent for parent in image.parents if parent.name == 'Library') / 'catalog.json'
        catalog = json.loads(catalog_path.read_text())
        for entry in catalog['assets'].values():
            if entry['path'] == relative:
                entry.pop('generated', None)
                entry.pop('renderer', None)
        catalog_path.write_text(json.dumps(catalog))
    elif damage == 'missing':
        image.unlink()
    else:
        image.write_bytes(b'tampered SVG')
    rf.pack_path(SUB).write_text(json.dumps(pack))
    result = rf.gates(SUB)
    assert not result['ok']
    assert result['figures'] > 0 or result['guided'] > 0


def test_failed_foundry_publication_stays_pending_held_and_silent(fdy, monkeypatch):
    from types import SimpleNamespace
    from test_foundry import add_legacy_state
    add_legacy_state(fdy, [SUB])
    with fdy.chapter(SUB) as state:
        state['stage'] = 'sign'
    monkeypatch.setenv('FOUNDRY_PUBLISH', '1')
    monkeypatch.setenv('FOUNDRY_COMMIT', '1')
    calls, notifications = [], []
    monkeypatch.setattr(fdy, 'notify', notifications.append)
    monkeypatch.setattr(fdy.subprocess, 'run', lambda args, **kwargs: calls.append(args) or
                        SimpleNamespace(returncode=1, stdout='', stderr='injected publish failure'))
    with pytest.raises(RuntimeError, match='PUBLISH FAILED'):
        fdy.cmd_sign(SUB)
    assert fdy.load(SUB)['stage'] == 'sign'
    assert SUB in json.loads(fdy.HOLD.read_text())
    assert not notifications
    assert not any('git' == args[0] for args in calls)


@pytest.mark.parametrize('workflow', ['foundry', 'refine'])
def test_disabled_publication_does_not_claim_vault_delivery(workflow, request, monkeypatch):
    from test_foundry import add_legacy_state
    mod = request.getfixturevalue('fdy' if workflow == 'foundry' else 'rf')
    if workflow == 'foundry':
        add_legacy_state(mod, [SUB])
    else:
        mod.cmd_add([SUB])
    with mod.chapter(SUB) as state:
        state['stage'] = 'sign'
    notifications = []
    monkeypatch.setattr(mod if workflow == 'foundry' else mod.fd, 'notify', notifications.append)
    mod.cmd_sign(SUB)
    assert notifications and all('vault' not in text for text in notifications)


@pytest.mark.parametrize('workflow', ['foundry', 'refine'])
def test_external_work_checkpoint_never_invokes_git(workflow, request, tmp_path, monkeypatch):
    from types import SimpleNamespace
    mod = request.getfixturevalue('fdy' if workflow == 'foundry' else 'rf')
    mod.cmd_add([SUB])
    external = tmp_path.parent / (tmp_path.name + '-outside.json')
    external.write_text('{}')
    monkeypatch.setattr(mod, 'chapter_paths', lambda sub: [str(external)])
    config = mod.config
    monkeypatch.setattr(mod, 'config', lambda: {**config(), 'commit_on_sign': True})
    monkeypatch.setenv('FOUNDRY_COMMIT', '1')
    calls = []
    monkeypatch.setattr(mod.subprocess, 'run', lambda args, **kwargs: calls.append(args) or
                        SimpleNamespace(returncode=0, stdout='', stderr=''))
    mod.release(SUB)
    assert not calls


@pytest.mark.parametrize('workflow', ['foundry', 'refine'])
def test_failed_git_add_never_commits_existing_index(workflow, request, tmp_path, monkeypatch):
    from types import SimpleNamespace
    mod = request.getfixturevalue('fdy' if workflow == 'foundry' else 'rf')
    mod.cmd_add([SUB])
    (tmp_path / 'owned.json').write_text('{}')
    monkeypatch.setattr(mod, 'chapter_paths', lambda sub: ['owned.json'])
    config = mod.config
    monkeypatch.setattr(mod, 'config', lambda: {**config(), 'commit_on_sign': True})
    monkeypatch.setenv('FOUNDRY_COMMIT', '1')
    calls = []
    def failed_add(args, **kwargs):
        calls.append(args)
        return SimpleNamespace(returncode=1 if 'add' in args else 0, stdout='', stderr='injected add failure')
    monkeypatch.setattr(mod.subprocess, 'run', failed_add)
    mod.release(SUB)
    assert not any('commit' in args for args in calls)


def test_guided_validator_accepts_card_display_only_in_lessons(lesson_visual):
    rf, _, _ = lesson_visual
    pack = json.loads(rf.pack_path(SUB).read_text())
    pack['guided_forms'] = {}
    graph = json.loads((rf.SPECS / '9702/graph.json').read_text())
    common = (pack, graph, NOTE, rf.ROOT / 'build/out/assets')
    assert not any('not embedded' in issue for issue in rf.fd.guided_problems(*common, lesson_display=True))
    assert any('not embedded' in issue for issue in rf.fd.guided_problems(*common))


def test_lesson_plan_can_reuse_card_svg_without_new_pack_request(lesson_visual):
    rf, _, _ = lesson_visual
    pack = json.loads(rf.pack_path(SUB).read_text())
    pack['diagrams'] = []
    rf.pack_path(SUB).write_text(json.dumps(pack))
    rf.plan_path(SUB).write_text(json.dumps({'improvements': [{'kind': 'diagram'}]}))
    result = rf.gates(SUB)
    assert result['ok'], result.get('first')
