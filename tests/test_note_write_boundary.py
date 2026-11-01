"""Personal-note authoring must stay inside its learner vault and outside Library."""
import copy
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from fixtures import GRAPH, PACK, make_vault
from test_v110 import T0
from tutorlib import model, packs, store, views
from tutorlib.asset_library import write_asset

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "build"))
import validate_pack  # noqa: E402


def loaded(tmp_path, note=PACK["note"]):
    root = make_vault(tmp_path)
    source = root / ".tutor/packs/v1/specs/9702/packs/9702-2.1.json"
    pack = json.loads(source.read_text())
    pack["note"] = note
    source.write_text(json.dumps(pack))
    return root, packs.Packs(store.Vault(root)), model.new_state(), source


@pytest.mark.parametrize("reference", ["Subjects/../../outside-note.md", "Subjects/../Library/reference.md"])
def test_unsafe_reference_never_updates_a_file_outside_personal_notes(tmp_path, reference):
    root, content, state, source = loaded(tmp_path, reference)
    unsafe = (root / ("My Notes/" + reference.split("/", 1)[1])).resolve()
    if unsafe.is_relative_to(root / "Library"):
        write_asset(root, unsafe.relative_to(root).as_posix(), b"Original protected text.\n")
    else:
        unsafe.parent.mkdir(parents=True, exist_ok=True)
        unsafe.write_text("Original protected text.\n")
    original = unsafe.read_bytes()
    original_source = source.read_bytes()

    relative = views.notes_update(root, content, state, "9702-2.1")

    assert unsafe.read_bytes() == original
    assert (root / relative).resolve().is_relative_to((root / "My Notes").resolve())
    assert ".." not in Path(relative).parts
    assert source.read_bytes() == original_source


def test_notes_update_refuses_a_parent_symlink_escape(tmp_path):
    root, content, state, _ = loaded(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "learner.md"
    sentinel.write_text("Original external note.\n")
    (root / "My Notes").symlink_to(outside, target_is_directory=True)
    before = {p.relative_to(outside): p.read_bytes() for p in outside.rglob("*") if p.is_file()}

    with pytest.raises(OSError):
        views.notes_update(root, content, state, "9702-2.1")

    assert {p.relative_to(outside): p.read_bytes() for p in outside.rglob("*") if p.is_file()} == before
    assert (root / "My Notes").is_symlink()


@pytest.mark.parametrize("adapter", ["file", "directory"])
def test_note_adapter_cannot_replace_or_update_a_library_resource(tmp_path, adapter):
    root, content, state, _ = loaded(tmp_path)
    canonical = "Library/Courses/9702/Notes/reference.md"
    write_asset(root, canonical, b"# Immutable reference\n")
    resource = root / canonical
    catalog = root / "Library/catalog.json"
    note = root / views.notes_rel(content, "9702-2.1")
    if adapter == "file":
        note.parent.mkdir(parents=True)
        note.symlink_to(resource)
        protected = resource
    else:
        (root / "My Notes").symlink_to(root / "Library", target_is_directory=True)
        protected = root / "Library" / note.relative_to(root / "My Notes")
        write_asset(root, protected.relative_to(root).as_posix(), b"Existing Library-side content.\n")
    before = protected.read_bytes()
    before_catalog = catalog.read_bytes()

    with pytest.raises(OSError):
        views.notes_update(root, content, state, "9702-2.1")
    with pytest.raises(OSError):
        views.refresh_status(root, content, state, "9702-2.1")

    assert protected.read_bytes() == before
    assert catalog.read_bytes() == before_catalog
    assert (note if adapter == "file" else root / "My Notes").is_symlink()


def test_ordinary_note_updates_keep_the_existing_path_and_learner_text(tmp_path):
    root, content, state, source = loaded(tmp_path)
    relative = views.notes_rel(content, "9702-2.1")
    assert relative == PACK["note"].replace("Subjects/", "My Notes/", 1)
    views.notes_update(root, content, state, "9702-2.1")
    note = root / relative
    note.write_text(note.read_text() + "\nMy own paragraph.\n")
    original_source = source.read_bytes()
    before = copy.deepcopy(state)

    assert views.notes_update(root, content, state, "9702-2.1") == relative
    assert views.refresh_status(root, content, state, "9702-2.1") == relative

    assert "My own paragraph." in note.read_text()
    assert state == before and source.read_bytes() == original_source


@pytest.mark.parametrize("reference", ["Subjects/../../outside.md", "/tmp/outside.md", "Subjects\\..\\outside.md"])
def test_pack_validation_rejects_unsafe_note_references(reference):
    pack = copy.deepcopy(PACK)
    pack["note"] = reference
    assert any(error["rule"] == "note" for error in validate_pack.validate(pack, GRAPH, min_variants=0))


@pytest.mark.parametrize("reference", [PACK["note"], "Library/Courses/9702/Notes/reference.md", "asset:reference-note"])
def test_pack_validation_preserves_normal_and_declared_note_reference_shapes(reference):
    pack = copy.deepcopy(PACK)
    pack["note"] = reference
    assert not any(error["rule"] == "note" for error in validate_pack.validate(pack, GRAPH, min_variants=0))


def test_personal_note_parent_cannot_redirect_into_the_event_log(tmp_path):
    root, content, state, _ = loaded(tmp_path, "Subjects/2026-09.jsonl")
    vault = store.Vault(root)
    event = vault.append_event({"type": "note", "text": "Original learner record"}, now=T0)
    path = vault.tutor / "events/2026-09.jsonl"
    before = path.read_bytes()
    (root / "My Notes").symlink_to(vault.tutor / "events", target_is_directory=True)

    with pytest.raises(OSError):
        views.notes_update(root, content, state, "9702-2.1")

    assert path.read_bytes() == before
    assert list(vault.events()) == [event]


@pytest.mark.parametrize("spec, topic", [("..", "Kinematics"), ("9702", "..")])
def test_unsafe_fallback_metadata_cannot_escape_its_note_shelf(tmp_path, spec, topic):
    root = make_vault(tmp_path)
    content = SimpleNamespace(pack=lambda _: {}, kcs={}, topics={"topic": {"title": topic}},
                              subtopics={"sub": {"spec": spec, "topic": "topic", "title": "Lesson"}})
    with pytest.raises(OSError):
        views.notes_update(root, content, model.new_state(), "sub")
    assert not (root / "My Notes").exists()


def test_catalogued_regular_file_adapter_is_read_only(tmp_path):
    root, content, state, _ = loaded(tmp_path)
    relative = views.notes_rel(content, "9702-2.1")
    canonical = "Library/Courses/9702/Notes/published.md"
    write_asset(root, canonical, b"Published immutable note.\n", aliases=[relative])
    adapter = root / relative
    adapter.parent.mkdir(parents=True)
    adapter.write_bytes((root / canonical).read_bytes())
    before = adapter.read_bytes()
    catalog = (root / "Library/catalog.json").read_bytes()

    with pytest.raises(OSError):
        views.notes_update(root, content, state, "9702-2.1")

    assert adapter.read_bytes() == (root / canonical).read_bytes() == before
    assert (root / "Library/catalog.json").read_bytes() == catalog


def test_declared_reference_alias_still_creates_separate_personal_notes(tmp_path):
    root = make_vault(tmp_path)
    (root / ".tutor/packs/v1/papers.json").write_text('{"papers": []}')
    canonical = "Library/Courses/9702/Notes/reference.md"
    write_asset(root, canonical, b"Immutable teaching reference.\n", aliases=[PACK["note"]])
    content = packs.Packs(store.Vault(root))
    assert content.pack("9702-2.1")["note"] == PACK["note"]
    expected = views.notes_rel(content, "9702-2.1")
    catalog = (root / "Library/catalog.json").read_bytes()

    assert views.notes_update(root, content, model.new_state(), "9702-2.1") == expected

    assert (root / expected).is_file()
    assert (root / canonical).read_bytes() == b"Immutable teaching reference.\n"
    assert (root / "Library/catalog.json").read_bytes() == catalog


def test_directory_alias_staying_inside_personal_notes_is_preserved(tmp_path):
    root, content, state, _ = loaded(tmp_path)
    shelf = root / "My Notes"
    shelf.mkdir()
    actual = shelf / "Actual course"
    actual.mkdir()
    (shelf / "9702 Physics").symlink_to(actual, target_is_directory=True)

    relative = views.notes_update(root, content, state, "9702-2.1")

    assert (root / relative).resolve().is_relative_to(actual)
    assert (shelf / "9702 Physics").is_symlink()


def test_internal_directory_alias_preserves_filesystem_case_semantics(tmp_path):
    root, content, state, _ = loaded(tmp_path)
    shelf = root / "My Notes"
    actual = shelf / "Actual course"
    actual.mkdir(parents=True)
    if not (root / "my notes").exists():
        other = root / "my notes/Actual course"
        other.mkdir(parents=True)
        (shelf / "9702 Physics").symlink_to("../my notes/Actual course", target_is_directory=True)
        with pytest.raises(OSError):
            views.notes_update(root, content, state, "9702-2.1")
        assert list(other.iterdir()) == []
        return
    (shelf / "9702 Physics").symlink_to("../my notes/Actual course", target_is_directory=True)

    relative = views.notes_update(root, content, state, "9702-2.1")

    assert (root / relative).exists()
    assert (root / relative).parent.samefile(actual / "02 Kinematics")
    assert (shelf / "9702 Physics").is_symlink()


def test_catalog_lookup_preserves_internal_alias_vault_case_semantics(tmp_path):
    root, content, state, _ = loaded(tmp_path)
    write_asset(root, "Library/Courses/9702/Notes/reference.md", b"Immutable reference.\n")
    catalog = (root / "Library/catalog.json").read_bytes()
    shelf = root / "My Notes"
    actual = shelf / "Actual course"
    actual.mkdir(parents=True)
    differently_spelled_root = root.with_name(root.name.lower())
    if not differently_spelled_root.exists():
        other = differently_spelled_root / "My Notes/Actual course"
        other.mkdir(parents=True)
        (shelf / "9702 Physics").symlink_to(other, target_is_directory=True)
        with pytest.raises(OSError):
            views.notes_update(root, content, state, "9702-2.1")
        assert list(other.iterdir()) == []
    else:
        (shelf / "9702 Physics").symlink_to(differently_spelled_root / "My Notes/Actual course",
                                           target_is_directory=True)
        relative = views.notes_update(root, content, state, "9702-2.1")
        assert (root / relative).parent.samefile(actual / "02 Kinematics")
    assert (root / "Library/catalog.json").read_bytes() == catalog
    assert (shelf / "9702 Physics").is_symlink()
