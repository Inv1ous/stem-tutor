"""A display correction may publish only a reviewed diff of the active release."""
import hashlib
import json

import pytest

from library_assets import read_bytes
from tutorlib.asset_library import AssetLibrary, write_asset


def fixture(tmp_path):
    vault = tmp_path / 'vault'
    vault.mkdir()
    pointer = vault / '.tutor/packs/CURRENT'
    pointer.parent.mkdir(parents=True)
    pointer.write_text('v1')
    pack_path = 'specs/P2/packs/P2-4.json'
    pack = read_bytes('build/out/packs/P2/P2-4.json')
    for path, data in {
        pack_path: pack,
        'specs/P2/graph.json': read_bytes('build/out/specs/P2/graph.json'),
        'manifest.json': json.dumps({'version': 'v1', 'specs': ['P2'], 'packs': 1}).encode(),
        'plan.json': b'{}', 'papers.json': b'{"papers": []}',
    }.items():
        write_asset(vault, 'Library/Releases/v1/' + path, data)
    event = vault / '.tutor/events.jsonl'
    event.write_bytes(b'{"historical":true}\n')
    proposal = {'format_version': 1, 'author': 'repair-author', 'version': 'v1', 'repairs': [{
        'path': pack_path, 'before_sha256': hashlib.sha256(pack).hexdigest(),
        'changes': [{'selector': ['items', 0, 'stem'],
                     'old': 'Find the 3th term of $u_n=2n^2-3n+1$.',
                     'new': 'Find the 3rd term of $u_n=2n^2-3n+1$.',
                     'reason': 'B-054: correct the ordinal suffix; mathematics is unchanged.'}],
    }]}
    return vault, proposal


def review(proposal):
    from build.release_repair import proposal_digest
    return {'reviewer': 'independent-reviewer', 'accepted': True,
            'proposal_sha256': proposal_digest(proposal)}


def test_repair_clones_active_bytes_and_preserves_history(tmp_path):
    from build.release_repair import repair_release
    vault, proposal = fixture(tmp_path)
    before = AssetLibrary(vault).records()
    result = repair_release(vault, proposal, review(proposal))
    assert result['version'] == 'v2'
    assert (vault / '.tutor/packs/CURRENT').read_text() == 'v2'
    adapter = vault / '.tutor/packs/v2'
    assert adapter.is_symlink()
    assert adapter.resolve() == vault / 'Library/Releases/v2'
    library = AssetLibrary(vault)
    assert all(library.records()[key] == entry for key, entry in before.items())
    for name in ['plan.json', 'papers.json', 'specs/P2/graph.json']:
        assert library.read('Library/Releases/v2/' + name) == library.read('Library/Releases/v1/' + name)
    original = json.loads(library.read('Library/Releases/v1/specs/P2/packs/P2-4.json'))
    repaired = json.loads(library.read('Library/Releases/v2/specs/P2/packs/P2-4.json'))
    original['items'][0]['stem'] = proposal['repairs'][0]['changes'][0]['new']
    assert repaired == original
    assert (vault / '.tutor/events.jsonl').read_bytes() == b'{"historical":true}\n'
    assert library.record('Library/Releases/v2/specs/P2/packs/P2-4.json')['repair_review']


@pytest.mark.parametrize('fault', ['stale-review', 'self-review', 'wrong-before', 'old-mismatch',
                                   'answer-edit', 'duplicate', 'new-fault', 'active-changed',
                                   'unregistered', 'symlink'])
def test_rejected_repair_never_changes_current(tmp_path, fault):
    from build.release_repair import repair_release
    vault, proposal = fixture(tmp_path)
    change = proposal['repairs'][0]['changes'][0]
    if fault == 'wrong-before': proposal['repairs'][0]['before_sha256'] = '0' * 64
    if fault == 'old-mismatch': change['old'] = 'different source'
    if fault == 'answer-edit': change['selector'] = ['items', 0, 'answer', 'value']
    if fault == 'duplicate': proposal['repairs'][0]['changes'].append(dict(change))
    if fault == 'new-fault': change['new'] = 'Broken \x01 formula'
    evidence = review(proposal)
    if fault == 'stale-review': change['new'] += ' unreviewed'
    if fault == 'self-review': evidence['reviewer'] = proposal['author']
    pointer = vault / '.tutor/packs/CURRENT'
    if fault == 'active-changed': pointer.write_text('v9')
    if fault == 'unregistered': (vault / 'Library/Releases/v1/extra.json').write_text('{}')
    if fault == 'symlink': (vault / 'Library/Releases/v1/link.json').symlink_to('plan.json')
    expected = pointer.read_bytes()
    with pytest.raises(ValueError):
        repair_release(vault, proposal, evidence)
    assert pointer.read_bytes() == expected
    assert not (vault / 'Library/Releases/v2').exists()


def test_current_is_compared_again_after_registration(tmp_path, monkeypatch):
    from build import release_repair
    vault, proposal = fixture(tmp_path)
    original = release_repair.write_asset
    def racing_write(*args, **kwargs):
        result = original(*args, **kwargs)
        (vault / '.tutor/packs/CURRENT').write_text('v9')
        return result
    monkeypatch.setattr(release_repair, 'write_asset', racing_write)
    with pytest.raises(ValueError, match='active release changed'):
        release_repair.repair_release(vault, proposal, review(proposal))
    assert (vault / '.tutor/packs/CURRENT').read_text() == 'v9'


def test_registration_failure_leaves_old_release_active(tmp_path, monkeypatch):
    from build import release_repair
    vault, proposal = fixture(tmp_path)
    original = release_repair.write_asset
    calls = []
    def fail_midway(*args, **kwargs):
        calls.append(args[1])
        if len(calls) == 2:
            raise OSError('simulated write failure')
        return original(*args, **kwargs)
    monkeypatch.setattr(release_repair, 'write_asset', fail_midway)
    with pytest.raises(OSError, match='simulated write failure'):
        release_repair.repair_release(vault, proposal, review(proposal))
    assert (vault / '.tutor/packs/CURRENT').read_text() == 'v1'
    assert AssetLibrary(vault).read('Library/Releases/v1/plan.json') == b'{}'


def test_subsequent_repair_preserves_prior_attestation(tmp_path):
    from build.release_repair import repair_release
    vault, proposal = fixture(tmp_path)
    first = repair_release(vault, proposal, review(proposal))
    library = AssetLibrary(vault)
    prior_review = library.read(first['review'])
    proposal['version'] = first['version']
    repair = proposal['repairs'][0]
    repair['before_sha256'] = library.record(f"Library/Releases/{first['version']}/{repair['path']}")['sha256']
    repair['changes'][0].update(old=repair['changes'][0]['new'], new='Find the third term of $u_n=2n^2-3n+1$.')
    second = repair_release(vault, proposal, review(proposal))
    assert second['version'] == 'v3'
    assert AssetLibrary(vault).read(first['review']) == prior_review


def test_changed_source_evidence_rejected_before_publication(tmp_path):
    from build.release_repair import repair_release
    vault, proposal = fixture(tmp_path)
    path = 'Library/Shared/Notes/source.md'
    write_asset(vault, path, b'registered source')
    proposal['repairs'][0]['changes'][0]['evidence'] = {'pdf': path, 'sha256': '0' * 64}
    with pytest.raises(ValueError, match='source evidence'):
        repair_release(vault, proposal, review(proposal))
    assert (vault / '.tutor/packs/CURRENT').read_text() == 'v1'


def test_adapter_failure_leaves_current_intact(tmp_path, monkeypatch):
    from pathlib import Path
    from build.release_repair import repair_release
    vault, proposal = fixture(tmp_path)
    def fail_adapter(*args, **kwargs):
        raise OSError('simulated adapter failure')
    monkeypatch.setattr(Path, 'symlink_to', fail_adapter)
    with pytest.raises(OSError, match='simulated adapter failure'):
        repair_release(vault, proposal, review(proposal))
    assert (vault / '.tutor/packs/CURRENT').read_text() == 'v1'


def test_only_activation_holds_the_learner_lock(tmp_path, monkeypatch):
    from contextlib import contextmanager
    from build import release_repair
    vault, proposal = fixture(tmp_path)
    held = []
    @contextmanager
    def study_lock(self):
        held.append(True)
        try:
            yield
        finally:
            held.pop()
    monkeypatch.setattr(release_repair.Vault, 'lock', study_lock)
    original_write = release_repair.write_asset
    def register_without_blocking_study(*args, **kwargs):
        assert not held, 'immutable validation/registration must not block learner commands'
        return original_write(*args, **kwargs)
    monkeypatch.setattr(release_repair, 'write_asset', register_without_blocking_study)
    original_replace = release_repair.os.replace
    def locked_switch(source, destination, *args, **kwargs):
        if destination == vault / '.tutor/packs/CURRENT':
            assert held, 'activation must serialize with learner commands'
        return original_replace(source, destination, *args, **kwargs)
    monkeypatch.setattr(release_repair.os, 'replace', locked_switch)
    repair_release = release_repair.repair_release(vault, proposal, review(proposal))
    assert repair_release['version'] == 'v2' and not held
