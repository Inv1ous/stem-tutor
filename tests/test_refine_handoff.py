"""Handoff regressions use isolated Work paths and synthetic Library adapters."""
import json
from pathlib import Path
import os
import time
from types import SimpleNamespace

from test_refine import rf, SUB  # noqa: F401


def test_existing_pack_candidate_still_gets_a_fresh_teach_copy(rf, tmp_path, monkeypatch):
    from tutor_workers import candidates
    rf.cmd_add([SUB])
    pack = json.loads(rf.pack_path(SUB).read_text())
    pack_copy = tmp_path / 'candidate-pack.json'
    pack_copy.write_text(json.dumps(pack))
    with rf.chapter(SUB) as st:
        st['candidate_pack'] = str(pack_copy)
        st.pop('candidate_teach', None)
    source = tmp_path / 'vault/Library/Courses/9702/teach.json'
    source.parent.mkdir(parents=True)
    source.write_text('{"obsolete": {"note": "an old draft"}}')
    draft = rf.ROOT / 'build/work/teach' / f'{SUB}.json'
    draft.parent.mkdir(parents=True, exist_ok=True)
    draft.symlink_to(source)
    monkeypatch.setattr(candidates, 'verified', lambda p: p.resolve())
    rf.ensure_candidate(SUB)
    st = rf.load(SUB)
    assert Path(st['candidate_pack']) == pack_copy
    editable = Path(st['candidate_teach'])
    assert 'Library' not in editable.parts
    assert json.loads(editable.read_text()) == pack['teach']
    assert source.read_text() == '{"obsolete": {"note": "an old draft"}}'


def test_absent_shared_draft_is_seeded_from_current_pack(rf):
    rf.cmd_add([SUB])
    rf.ensure_candidate(SUB)
    st = rf.load(SUB)
    assert json.loads(Path(st['candidate_teach']).read_text()) == json.loads(rf.pack_path(SUB).read_text())['teach']


def test_archiving_an_older_proposal_never_replaces_previous_evidence(rf):
    rf.cmd_add([SUB])
    proposal = rf.corrections_file(SUB)
    proposal.parent.mkdir(parents=True, exist_ok=True)
    old_time = time.time() - 86400
    for text in ('first source-bound proposal', 'second source-bound proposal'):
        proposal.write_text(text)
        os.utime(proposal, (old_time, old_time))
        assert rf.archive_stale_corrections(SUB)
    kept = list(proposal.parent.glob(f'{SUB}.corrections.before-pass*.json'))
    assert {p.read_text() for p in kept} == {'first source-bound proposal', 'second source-bound proposal'}


def test_signing_with_pending_written_checks_returns_to_independent_review(rf, monkeypatch):
    from test_refine import _written_pack
    rf.cmd_add([SUB])
    _written_pack(rf)
    with rf.chapter(SUB) as st:
        rf.move(st, 'sign')
    assert rf.todo(rf.load(SUB)) == ('dispatch',)
    launched = []
    monkeypatch.setattr(rf, 'cmd_run', lambda role, sub, **kwargs: launched.append(role))
    rf.cmd_dispatch(SUB)
    assert rf.load(SUB)['stage'] == 'recheck'
    assert 'wsolver' in launched


def test_a_worker_can_collect_before_popen_returns_without_losing_its_evidence(rf, monkeypatch):
    from test_refine_written_pipeline import start
    _, _, ident = start(rf)

    def immediate_process(*args, env, **kwargs):
        job = rf.load(SUB)['jobs']['wsolver']
        Path(env['FOUNDRY_EXPECTS']).write_text(json.dumps({ident: 'A complete blind solution.'}))
        out = rf.ROOT / job['out']
        out.write_text('{"done": true}')
        rf.cmd_collect('wsolver', SUB, str(out))
        return SimpleNamespace(pid=99999999)

    monkeypatch.setattr(rf.subprocess, 'Popen', immediate_process)
    rf.cmd_run('wsolver', SUB, on='codex')
    st = rf.load(SUB)
    assert st['jobs']['wsolver']['finished']
    assert st['jobs']['wsolver']['ok'] is True
    assert rf._done(st, 'wsolver')
def test_merge_refuses_library_output_and_its_file_adapter(tmp_path, monkeypatch):
    import json
    from build import teach_cards
    from test_guided_teach_cards import base_card

    monkeypatch.setattr(teach_cards, 'ROOT', tmp_path)
    graph = tmp_path / 'build/out/specs/P2/graph.json'
    graph.parent.mkdir(parents=True)
    graph.write_text(json.dumps({'kcs': [{'id': 'P2-1.1', 'subtopic': 'P2-1'}]}))
    draft = tmp_path / 'draft.json'
    draft.write_text(json.dumps({'P2-1.1': base_card()}))
    target = tmp_path / 'Library/Courses/P2/pack.json'
    target.parent.mkdir(parents=True)
    original = json.dumps({'spec': 'P2', 'subtopic': 'P2-1', 'teach': {}})
    target.write_text(original)
    adapter = tmp_path / 'pack.json'
    adapter.symlink_to(target)
    for output in (target, adapter):
        assert teach_cards.main('merge', ['P2-1', '--draft', str(draft), '--pack', str(output)]) == 1
        assert target.read_text() == original



def _signed_foundry_candidate(rf, tmp_path):
    from tutor_workers import lifecycle
    pack = json.loads(rf.pack_path(SUB).read_text())
    folder = tmp_path / 'signed-foundry'
    folder.mkdir()
    candidate = folder / 'pack.json'
    pack['teach'][f'{SUB}.1']['note'] = 'A repaired unpublished teaching note.'
    candidate.write_text(json.dumps(pack))
    note = folder / 'note.md'
    note.write_text(rf.note_path(pack).read_text() + '\nUnpublished repair.\n')
    state = {'sub': SUB, 'stage': 'ready', 'candidate_pack': str(candidate), 'candidate_note': str(note),
             'content_sha256': lifecycle.content_fingerprint(candidate, note), 'gates': {'ok': True}}
    rf.FOUNDRY_STATE.mkdir(parents=True, exist_ok=True)
    (rf.FOUNDRY_STATE / f'{SUB}.json').write_text(json.dumps(state))
    return candidate, note, state


def test_add_copies_signed_unpublished_foundry_candidate_before_baseline(rf, tmp_path, monkeypatch):
    candidate, note, _ = _signed_foundry_candidate(rf, tmp_path)
    published = rf.pack_path(SUB).read_bytes()
    monkeypatch.setattr(rf.fd, 'gates', lambda *args, **kwargs: {'ok': True})
    rf.cmd_add([SUB])
    st = rf.load(SUB)
    assert Path(st['candidate_pack']) != candidate
    assert rf.pack_path(SUB).read_bytes() == candidate.read_bytes()
    assert rf.note_path(json.loads(candidate.read_text())).read_bytes() == note.read_bytes()
    assert rf.snapshot(SUB)['pack'] == json.loads(candidate.read_text())
    assert json.loads(Path(st['candidate_teach']).read_text()) == json.loads(candidate.read_text())['teach']
    assert (rf.PACKS / '9702' / f'{SUB}.json').read_bytes() == published


def test_add_rejects_changed_or_unverified_foundry_candidate_without_state(rf, tmp_path, monkeypatch):
    import pytest
    candidate, _, state = _signed_foundry_candidate(rf, tmp_path)
    candidate.write_text(candidate.read_text() + ' ')
    monkeypatch.setattr(rf.fd, 'gates', lambda *args, **kwargs: {'ok': True})
    with pytest.raises(SystemExit, match='signed Foundry candidate'):
        rf.cmd_add([SUB])
    assert not (rf.STATE / f'{SUB}.json').exists()
    state.pop('content_sha256')
    (rf.FOUNDRY_STATE / f'{SUB}.json').write_text(json.dumps(state))
    with pytest.raises(SystemExit, match='signed Foundry candidate'):
        rf.cmd_add([SUB])
    assert not (rf.STATE / f'{SUB}.json').exists()


def test_add_rejects_signed_candidate_with_current_gate_damage(rf, tmp_path, monkeypatch):
    import pytest
    _signed_foundry_candidate(rf, tmp_path)
    monkeypatch.setattr(rf.fd, 'gates', lambda *args, **kwargs: {'ok': False, 'first': ['damaged source']})
    with pytest.raises(SystemExit, match='signed Foundry candidate'):
        rf.cmd_add([SUB])
    assert not (rf.STATE / f'{SUB}.json').exists()


def test_new_pass_uses_newer_signed_foundry_and_archives_refine_baseline(rf, tmp_path, monkeypatch):
    from tutor_workers import lifecycle
    rf.cmd_add([SUB])
    old = rf.snapshot(SUB)
    with rf.chapter(SUB) as st:
        st.update(stage='ready', prepared_at='2026-10-01T00:00:00+00:00',
                  content_sha256=lifecycle.content_fingerprint(rf.pack_path(SUB), rf.note_path(old['pack'])))
    candidate, _, state = _signed_foundry_candidate(rf, tmp_path)
    state['prepared_at'] = '2026-10-02T00:00:00+00:00'
    (rf.FOUNDRY_STATE / f'{SUB}.json').write_text(json.dumps(state))
    monkeypatch.setattr(rf.fd, 'gates', lambda *a, **kw: {'ok': True})
    rf.cmd_add([SUB])
    assert rf.snapshot(SUB)['pack'] == json.loads(candidate.read_text())
    archived = list((rf.WORK / 'history' / SUB).glob('snapshot.*.json'))
    assert any(json.loads(p.read_text())['pack'] == old['pack'] for p in archived)
    assert rf.load(SUB)['pass'] == 2


def test_new_foundry_source_cannot_overwrite_independent_refine_edits(rf, tmp_path, monkeypatch):
    import pytest
    from tutor_workers import lifecycle
    rf.cmd_add([SUB])
    with rf.chapter(SUB) as st:
        st.update(stage='ready', prepared_at='2026-10-01T00:00:00+00:00',
                  content_sha256=lifecycle.content_fingerprint(rf.pack_path(SUB), rf.note_path(rf.snapshot(SUB)['pack'])))
    rf.pack_path(SUB).write_text(rf.pack_path(SUB).read_text() + ' ')
    before = (rf.STATE / f'{SUB}.json').read_bytes()
    _, _, state = _signed_foundry_candidate(rf, tmp_path)
    state['prepared_at'] = '2026-10-02T00:00:00+00:00'
    (rf.FOUNDRY_STATE / f'{SUB}.json').write_text(json.dumps(state))
    monkeypatch.setattr(rf.fd, 'gates', lambda *a, **kw: {'ok': True})
    with pytest.raises(SystemExit, match='independent|ambiguous'):
        rf.cmd_add([SUB])
    assert (rf.STATE / f'{SUB}.json').read_bytes() == before


def test_all_discovers_signed_foundry_only_candidate(rf, tmp_path, monkeypatch):
    _signed_foundry_candidate(rf, tmp_path)
    rf.pack_path(SUB).unlink()
    monkeypatch.setattr(rf.fd, 'gates', lambda *a, **kw: {'ok': True})
    rf.cmd_add(['--all'])
    assert rf.load(SUB)['candidate_pack']


def test_different_signed_candidates_without_ordering_fail_closed(rf, tmp_path, monkeypatch):
    import pytest
    rf.cmd_add([SUB])
    with rf.chapter(SUB) as st:
        st['stage'] = 'ready'
    _, _, state = _signed_foundry_candidate(rf, tmp_path)
    before = (rf.STATE / f'{SUB}.json').read_bytes()
    monkeypatch.setattr(rf.fd, 'gates', lambda *a, **kw: {'ok': True})
    with pytest.raises(SystemExit, match='ambiguous'):
        rf.cmd_add([SUB])
    assert (rf.STATE / f'{SUB}.json').read_bytes() == before
