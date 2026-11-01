"""Optional lesson organisation must never edit immutable resources or redirected outputs."""
from datetime import datetime
from pathlib import Path

import pytest

from tutorlib import asset_library, views


OLD = "Lessons/2026-10-04 1539 Lesson - Test.md"
NEW = "Lessons/2026-10-04/1539 Lesson - Test.md"
LINK = b"Original reference [[Lessons/2026-10-04 1539 Lesson - Test|my lesson]].\r\n"
LESSON = b"# Original lesson\r\nLearner working: 12.0 m\r\n"
RESOURCE = "Library/Courses/9702/Notes/reference.md"


def flat(root):
    source = root / OLD
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(LESSON)
    return source


def test_link_repairs_preserve_all_library_archive_and_event_bytes(tmp_path):
    root = tmp_path / "vault"
    source = flat(root)
    asset_library.write_asset(root, RESOURCE, LINK)
    unregistered = root / "Library/unregistered.md"
    unregistered.write_bytes(LINK)
    original = root / "Archive/original.md"
    original.parent.mkdir()
    original.write_bytes(LINK)
    event = root / ".tutor/events/2026-10.jsonl"
    event.parent.mkdir(parents=True)
    event.write_bytes(b'{"type":"note","text":"[[Lessons/2026-10-04 1539 Lesson - Test]]"}\n')
    learner = root / "Notebook.md"
    learner.write_bytes(LINK)
    protected = {path: path.read_bytes() for path in (root / RESOURCE, unregistered, original,
                                                     root / "Library/catalog.json", event)}

    assert views.organise_lessons(root) == [(OLD, NEW)]

    assert not source.exists() and (root / NEW).read_bytes() == LESSON
    assert "[[Lessons/2026-10-04/1539 Lesson - Test|my lesson]]" in learner.read_text()
    assert all(path.read_bytes() == data for path, data in protected.items())
    assert asset_library.AssetLibrary(root).read(RESOURCE) == LINK
    journal, = (root / ".tutor/backups").glob("lessons-moved-*.txt")
    assert f"{OLD} -> {NEW}" in journal.read_text()
    assert (journal.with_suffix("").with_name(journal.stem + "-originals") / "Notebook.md").read_bytes() == LINK
    assert learner.read_bytes().endswith(b"\r\n")
    assert views.organise_lessons(root) == []


@pytest.mark.parametrize("adapter", ["regular", "symlink"])
def test_registered_note_adapters_are_not_replaced_by_link_repair(tmp_path, adapter):
    root = tmp_path / "vault"
    flat(root)
    asset_library.write_asset(root, RESOURCE, LINK, aliases=["Reference.md"])
    note = root / "Reference.md"
    if adapter == "regular":
        note.write_bytes(LINK)
    else:
        note.symlink_to(RESOURCE)
    original_link = note.readlink() if note.is_symlink() else None

    assert views.organise_lessons(root) == [(OLD, NEW)]

    assert note.read_bytes() == LINK and note.is_symlink() == (adapter == "symlink")
    if original_link is not None:
        assert note.readlink() == original_link
    assert asset_library.AssetLibrary(root).read("Reference.md") == LINK


@pytest.mark.parametrize("adapter", ["regular", "symlink"])
def test_registered_flat_lesson_adapters_remain_at_their_declared_path(tmp_path, adapter):
    root = tmp_path / "vault"
    root.mkdir()
    asset_library.write_asset(root, RESOURCE, LESSON, aliases=[OLD])
    source = root / OLD
    source.parent.mkdir()
    if adapter == "regular":
        source.write_bytes(LESSON)
    else:
        source.symlink_to(Path("..") / RESOURCE)

    assert views.organise_lessons(root) == []

    assert source.read_bytes() == LESSON and not (root / NEW).exists()
    assert source.is_symlink() == (adapter == "symlink")
    assert asset_library.AssetLibrary(root).read(OLD) == LESSON


@pytest.mark.parametrize("where", ["Library", "outside"])
@pytest.mark.parametrize("redirect", ["lessons", "day"])
def test_redirected_lesson_directories_do_not_move_or_write_resources(tmp_path, where, redirect):
    root = tmp_path / "vault"
    root.mkdir()
    destination = (root / "Library/redirected" if where == "Library" else tmp_path / "outside")
    destination.mkdir(parents=True)
    if where == "Library":
        asset_library.write_asset(root, "Library/marker.bin", b"Original catalogued resource")
    if redirect == "lessons":
        (root / "Lessons").symlink_to(destination, target_is_directory=True)
        source = destination / Path(OLD).name
        source.write_bytes(LESSON)
    else:
        source = flat(root)
        (root / "Lessons/2026-10-04").symlink_to(destination, target_is_directory=True)
    marker = destination / "untouched.md"
    marker.write_bytes(LINK)

    assert views.organise_lessons(root) == []

    assert source.read_bytes() == LESSON and marker.read_bytes() == LINK
    assert not (destination / Path(NEW).name).exists()
    assert not (root / ".tutor/backups").exists()


def test_a_broken_destination_adapter_is_not_overwritten(tmp_path):
    root = tmp_path / "vault"
    source = flat(root)
    target = root / NEW
    target.parent.mkdir()
    target.symlink_to("missing.md")

    assert views.organise_lessons(root) == []

    assert source.read_bytes() == LESSON and target.is_symlink() and target.readlink() == Path("missing.md")


def test_a_declared_destination_alias_is_not_created_by_migration(tmp_path):
    root = tmp_path / "vault"
    source = flat(root)
    asset_library.write_asset(root, RESOURCE, LESSON, aliases=[NEW])

    assert views.organise_lessons(root) == []

    assert source.read_bytes() == LESSON and not (root / NEW).exists()
    assert asset_library.AssetLibrary(root).read(NEW) == LESSON


@pytest.mark.parametrize("where", ["Library", "outside"])
def test_migration_without_a_safe_journal_keeps_flat_source(tmp_path, where):
    root = tmp_path / "vault"
    source = flat(root)
    destination = root / "Library/redirected" if where == "Library" else tmp_path / "outside"
    destination.mkdir(parents=True)
    if where == "Library":
        asset_library.write_asset(root, "Library/marker.bin", b"Original catalogued resource")
    (root / ".tutor").mkdir()
    (root / ".tutor/backups").symlink_to(destination, target_is_directory=True)

    assert views.organise_lessons(root) == []

    assert source.read_bytes() == LESSON and not (root / NEW).exists()
    assert list(destination.iterdir()) == []


@pytest.mark.parametrize("blocked", [".tutor", "Lessons/2026-10-04"])
def test_a_file_in_a_required_parent_path_leaves_the_source_in_place(tmp_path, blocked):
    root = tmp_path / "vault"
    source = flat(root)
    parent = root / blocked
    parent.write_bytes(b"Original file that is not a directory.\n")

    assert views.organise_lessons(root) == []

    assert source.read_bytes() == LESSON and parent.read_bytes() == b"Original file that is not a directory.\n"


def test_a_damaged_catalog_skips_optional_migration_without_guessing_alias_ownership(tmp_path):
    root = tmp_path / "vault"
    source = flat(root)
    (root / "Library").mkdir()
    (root / "Library/catalog.json").write_bytes(b"{invalid catalog")
    (root / "Notebook.md").write_bytes(LINK)

    assert views.organise_lessons(root) == []

    assert source.read_bytes() == LESSON and (root / "Notebook.md").read_bytes() == LINK
    assert not (root / ".tutor/backups").exists()


def test_library_without_catalog_cannot_establish_mutable_alias_ownership(tmp_path):
    root = tmp_path / "vault"
    source = flat(root)
    resource = root / RESOURCE
    resource.parent.mkdir(parents=True)
    resource.write_bytes(LINK)
    adapter = root / "Reference.md"
    adapter.write_bytes(LINK)

    assert views.organise_lessons(root) == []

    assert source.read_bytes() == LESSON and adapter.read_bytes() == LINK and resource.read_bytes() == LINK
    assert not (root / ".tutor/backups").exists()


def test_a_broken_library_directory_adapter_is_not_a_legacy_no_library_vault(tmp_path):
    root = tmp_path / "vault"
    source = flat(root)
    library = root / "Library"
    destination = tmp_path / "missing-library"
    library.symlink_to(destination, target_is_directory=True)

    assert views.organise_lessons(root) == []

    assert source.read_bytes() == LESSON and not (root / NEW).exists()
    assert library.is_symlink() and library.readlink() == destination and not destination.exists()
    assert not (root / ".tutor/backups").exists()


def test_repeated_migration_keeps_prior_move_journal_and_originals(tmp_path, monkeypatch):
    class Frozen(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 11, 2, 10, 0)

    monkeypatch.setattr(views, "datetime", Frozen)
    root = tmp_path / "vault"
    flat(root)
    learner = root / "Notebook.md"
    learner.write_bytes(LINK)
    assert views.organise_lessons(root) == [(OLD, NEW)]
    backups = root / ".tutor/backups"
    before = {path: path.read_bytes() for path in backups.rglob("*") if path.is_file()}
    other = "Lessons/2026-10-05 1539 Lesson - Other.md"
    (root / other).write_bytes(LESSON)
    prior_note = learner.read_bytes() + b"[[Lessons/2026-10-05 1539 Lesson - Other]]\r\n"
    learner.write_bytes(prior_note)

    assert views.organise_lessons(root) == [(other, "Lessons/2026-10-05/1539 Lesson - Other.md")]

    assert len(list(backups.glob("lessons-moved-*.txt"))) == 2
    assert all(path.read_bytes() == data for path, data in before.items())
    latest = next(path for path in backups.rglob("Notebook.md") if path not in before)
    assert latest.read_bytes() == prior_note


def test_refused_original_backup_leaves_the_live_learner_note_untouched(tmp_path, monkeypatch):
    root = tmp_path / "vault"
    flat(root)
    learner = root / "Notebook.md"
    learner.write_bytes(LINK)
    original_open = Path.open

    def refuse(path, mode="r", *args, **kwargs):
        if mode == "xb":
            raise PermissionError("Original backup refused")
        return original_open(path, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", refuse)

    assert views.organise_lessons(root) == [(OLD, NEW)]

    assert learner.read_bytes() == LINK and (root / NEW).read_bytes() == LESSON


def test_concurrent_learner_edit_is_preserved_after_original_snapshot(tmp_path, monkeypatch):
    root = tmp_path / "vault"
    flat(root)
    learner = root / "Notebook.md"
    learner.write_bytes(LINK)
    write = views.write_text
    concurrent = LINK + b"My newly saved working.\r\n"

    def saved_elsewhere(path, text, **kwargs):
        if path == learner:
            path.write_bytes(concurrent)
        return write(path, text, **kwargs)

    monkeypatch.setattr(views, "write_text", saved_elsewhere)

    assert views.organise_lessons(root) == [(OLD, NEW)]

    assert learner.read_bytes() == concurrent
    backup, = (root / ".tutor/backups").rglob("Notebook.md")
    assert backup.read_bytes() == LINK


def test_refused_move_journal_prevents_the_first_rename(tmp_path, monkeypatch):
    root = tmp_path / "vault"
    source = flat(root)
    write = views.write_text

    def refused(path, text, **kwargs):
        if path.parent.name == "backups":
            raise PermissionError("Move journal refused")
        return write(path, text, **kwargs)

    monkeypatch.setattr(views, "write_text", refused)

    assert views.organise_lessons(root) == []

    assert source.read_bytes() == LESSON and not (root / NEW).exists()
