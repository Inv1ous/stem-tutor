"""A single guide revision can become visible without republishing draft packs."""
import json

import pytest

from tutorlib import asset_library


@pytest.fixture
def notes(tmp_path):
    vault = tmp_path / 'vault'
    vault.mkdir()
    previous = asset_library.write_asset(vault, 'Library/Shared/Notes/original.md', b'Old guide',
                                         aliases=['build/out/notes/How It Works.md'],
                                         metadata={'review': {'binding': 'preserved'}})
    revised = asset_library.write_asset(vault, 'Library/Shared/Notes/revised.md', b'Corrected guide')
    (vault / 'How It Works.md').write_bytes(b'Old guide')
    (vault / '.tutor').mkdir()
    (vault / '.tutor/events.jsonl').write_bytes(b'learner history\n')
    archive = tmp_path / 'Archive' / 'guide'
    return vault, previous, revised, archive


def test_note_activation_preserves_catalog_history_and_original(notes):
    vault, previous, revised, archive = notes
    before = (vault / 'Library/catalog.json').read_bytes()
    asset_library.activate_note_adapter(vault, 'How It Works.md', revised,
                                       previous_reference=previous, archive_root=archive)
    assert (vault / 'How It Works.md').is_symlink()
    assert (vault / 'How It Works.md').read_bytes() == b'Corrected guide'
    assert (archive / 'original.md').read_bytes() == b'Old guide'
    journal = json.loads((archive / 'publication.json').read_text())
    assert journal['previous_reference'] == previous
    assert journal['new_reference'] == revised
    assert journal['adapter'] == 'How It Works.md'
    assert (vault / 'Library/catalog.json').read_bytes() == before
    reader = asset_library.AssetLibrary(vault)
    assert reader.read(previous) == b'Old guide'
    assert reader.read('build/out/notes/How It Works.md') == b'Old guide'
    assert reader.record(previous)['review'] == {'binding': 'preserved'}
    assert (vault / '.tutor/events.jsonl').read_bytes() == b'learner history\n'
    asset_library.activate_note_adapter(vault, 'How It Works.md', revised,
                                       previous_reference=previous, archive_root=archive)
    assert (archive / 'original.md').read_bytes() == b'Old guide'


def test_note_activation_rejects_changed_learner_copy(notes):
    vault, previous, revised, archive = notes
    (vault / 'How It Works.md').write_bytes(b'User edits')
    with pytest.raises(ValueError, match='previous'):
        asset_library.activate_note_adapter(vault, 'How It Works.md', revised,
                                           previous_reference=previous, archive_root=archive)
    assert (vault / 'How It Works.md').read_bytes() == b'User edits'
    assert not archive.exists()


def test_note_activation_verifies_new_registered_bytes(notes):
    vault, previous, revised, archive = notes
    (vault / 'Library/Shared/Notes/revised.md').write_bytes(b'Tampered')
    with pytest.raises(ValueError, match='digest'):
        asset_library.activate_note_adapter(vault, 'How It Works.md', revised,
                                           previous_reference=previous, archive_root=archive)
    assert (vault / 'How It Works.md').read_bytes() == b'Old guide'
    assert not archive.exists()


def test_note_activation_does_not_retarget_an_existing_root_alias(notes):
    vault, previous, revised, archive = notes
    asset_library.register_asset(vault, 'Library/Shared/Notes/original.md', aliases=['How It Works.md'])
    before = (vault / 'Library/catalog.json').read_bytes()
    with pytest.raises(ValueError, match='catalog owner'):
        asset_library.activate_note_adapter(vault, 'How It Works.md', revised,
                                           previous_reference=previous, archive_root=archive)
    assert (vault / 'Library/catalog.json').read_bytes() == before
    assert (vault / 'How It Works.md').read_bytes() == b'Old guide'
    assert not archive.exists()


def test_next_note_revision_replaces_only_the_exact_previous_registered_adapter(notes):
    vault, previous, revised, archive = notes
    asset_library.activate_note_adapter(vault, 'How It Works.md', revised,
                                       previous_reference=previous, archive_root=archive)
    latest = asset_library.write_asset(vault, 'Library/Shared/Notes/latest.md', b'Latest guide')
    next_archive = archive.with_name('next-guide')
    asset_library.activate_note_adapter(vault, 'How It Works.md', latest,
                                       previous_reference=revised, archive_root=next_archive)
    assert (vault / 'How It Works.md').read_bytes() == b'Latest guide'
    assert (next_archive / 'original.md').read_bytes() == b'Corrected guide'
    reader = asset_library.AssetLibrary(vault)
    assert reader.read(previous) == b'Old guide'
    assert reader.read(revised) == b'Corrected guide'


def test_note_activation_rejects_arbitrary_previous_symlinks(notes):
    vault, previous, revised, archive = notes
    (vault / 'unregistered.md').write_bytes(b'Old guide')
    (vault / 'How It Works.md').unlink()
    (vault / 'How It Works.md').symlink_to('unregistered.md')
    with pytest.raises(ValueError):
        asset_library.activate_note_adapter(vault, 'How It Works.md', revised,
                                           previous_reference=previous, archive_root=archive)
    assert (vault / 'How It Works.md').readlink().as_posix() == 'unregistered.md'
    assert not archive.exists()


def test_note_activation_rechecks_current_bytes_after_archiving(notes, monkeypatch):
    vault, previous, revised, archive = notes
    write = asset_library._atomic_at
    def concurrent_edit(directory, name, data, replace):
        write(directory, name, data, replace)
        if name == 'publication.json':
            (vault / 'How It Works.md').write_bytes(b'Concurrent user edits')
    monkeypatch.setattr(asset_library, '_atomic_at', concurrent_edit)
    with pytest.raises(ValueError, match='previous'):
        asset_library.activate_note_adapter(vault, 'How It Works.md', revised,
                                           previous_reference=previous, archive_root=archive)
    assert (vault / 'How It Works.md').read_bytes() == b'Concurrent user edits'
    assert (archive / 'original.md').read_bytes() == b'Old guide'
    assert list(vault.glob('.note-*')) == []


def test_failed_adapter_swap_keeps_old_note_and_rollback_copy(notes, monkeypatch):
    vault, previous, revised, archive = notes
    replace = asset_library.os.replace
    def fail_note_swap(source, destination, *args, **kwargs):
        if destination == 'How It Works.md':
            raise OSError('interrupted adapter swap')
        return replace(source, destination, *args, **kwargs)
    monkeypatch.setattr(asset_library.os, 'replace', fail_note_swap)
    with pytest.raises(ValueError, match='unsafe|unavailable'):
        asset_library.activate_note_adapter(vault, 'How It Works.md', revised,
                                           previous_reference=previous, archive_root=archive)
    assert (vault / 'How It Works.md').read_bytes() == b'Old guide'
    assert (archive / 'original.md').read_bytes() == b'Old guide'
    assert list(vault.glob('.note-*')) == []


@pytest.mark.parametrize('name', ['../outside.md', '.tutor/state.md', 'Library/old.md', 'guide.json'])
def test_note_activation_only_accepts_root_markdown_adapters(notes, name):
    vault, previous, revised, archive = notes
    with pytest.raises(ValueError):
        asset_library.activate_note_adapter(vault, name, revised,
                                           previous_reference=previous, archive_root=archive)
    assert not archive.exists()
