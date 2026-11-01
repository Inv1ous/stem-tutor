"""Current-content assertions must read CURRENT rather than historical aliases."""
import json

import pytest

import library_assets
from tutorlib.asset_library import write_asset


def register_release(vault, version, item_id, *, manifest_version=None, packs=1):
    prefix = f'Library/Releases/{version}/'
    manifest = {'version': manifest_version or version, 'specs': ['9701'], 'packs': packs}
    write_asset(vault, prefix + 'manifest.json', json.dumps(manifest).encode())
    write_asset(vault, prefix + 'specs/9701/packs/9701-9.1.json', json.dumps({
        'spec': '9701', 'subtopic': '9701-9.1', 'items': [{'id': item_id}],
    }).encode())


@pytest.fixture
def vault(tmp_path, monkeypatch):
    root = tmp_path / 'vault'
    root.mkdir()
    pointer = root / '.tutor/packs/CURRENT'
    pointer.parent.mkdir(parents=True)
    pointer.write_text('v1')
    register_release(root, 'v1', 'selected')
    register_release(root, 'v2', 'unpublished')
    monkeypatch.setattr(library_assets, 'REAL_VAULT', root)
    return root


def test_current_selected_release_beats_newer_registered_resource_without_writes(vault):
    before = {p.relative_to(vault): p.read_bytes() for p in vault.rglob('*') if p.is_file()}
    assert library_assets.current_release_packs()[0]['items'] == [{'id': 'selected'}]
    after = {p.relative_to(vault): p.read_bytes() for p in vault.rglob('*') if p.is_file()}
    assert before == after


def test_next_call_observes_new_pointer_and_fresh_catalog(vault):
    assert library_assets.current_release_packs()[0]['items'] == [{'id': 'selected'}]
    register_release(vault, 'v3', 'newly-selected')
    (vault / '.tutor/packs/CURRENT').write_text('v3')
    assert library_assets.current_release_packs()[0]['items'] == [{'id': 'newly-selected'}]


@pytest.mark.parametrize('pointer', ['../v2', 'v0', 'v1/specs', 'invalid'])
def test_malformed_current_pointer_fails_closed(vault, pointer):
    (vault / '.tutor/packs/CURRENT').write_text(pointer)
    with pytest.raises(ValueError, match='CURRENT'):
        library_assets.current_release_packs()


@pytest.mark.parametrize('relative', ['manifest.json', 'specs/9701/packs/9701-9.1.json'])
def test_current_registered_resource_digest_mismatch_fails_closed(vault, relative):
    path = vault / 'Library/Releases/v1' / relative
    path.write_bytes(path.read_bytes() + b' ')
    with pytest.raises(ValueError, match='digest mismatch'):
        library_assets.current_release_packs()


@pytest.mark.parametrize('manifest_version,packs', [('v2', 1), ('v1', 2)])
def test_current_manifest_must_match_selected_version_and_pack_count(vault, monkeypatch, manifest_version, packs):
    # A new disposable fixture begins with this malformed registered manifest.
    other = vault.parent / 'malformed-vault'
    other.mkdir()
    pointer = other / '.tutor/packs/CURRENT'
    pointer.parent.mkdir(parents=True)
    pointer.write_text('v1')
    register_release(other, 'v1', 'bad-manifest', manifest_version=manifest_version, packs=packs)
    monkeypatch.setattr(library_assets, 'REAL_VAULT', other)
    with pytest.raises(ValueError, match='manifest'):
        library_assets.current_release_packs()
