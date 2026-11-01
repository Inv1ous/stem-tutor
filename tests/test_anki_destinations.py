"""Personal export packages must not enter immutable/preservation shelves."""
from copy import deepcopy

import pytest

from test_lesson_destinations import files, registered_vault
from test_session import T0
from tutorlib import anki, asset_library, session, store


def ready_tutor(tmp_path):
    root = registered_vault(tmp_path)
    tutor = session.Tutor(store.Vault(root), now=lambda: T0)
    tutor.log({"type": "answer", "item": "introduced", "kcs": ["9702-2.1.1"], "subject": "phys",
               "difficulty": 3, "conf": 3, "hinted": False, "marks": 1,
               "grade": {"correct": True, "score": 1.0, "error": None, "misconception": None}})
    return tutor


@pytest.mark.parametrize("owner", ["library", "library-case", "vault-archive", "workspace-archive", "events"])
def test_public_anki_export_refuses_preservation_directory_before_package_or_event(tmp_path, owner):
    tutor = ready_tutor(tmp_path)
    root = tutor.vault.root
    canonical = root / "Library/Shared/Exports"
    canonical.mkdir(parents=True)
    target = {"library": canonical, "library-case": root / "library/Shared/Exports",
              "vault-archive": root / "Archive/Exports", "workspace-archive": root.parent / "Archive/Exports",
              "events": root / ".tutor/events"}[owner]
    if owner == "library-case" and not target.exists():
        pytest.skip("Physical case-alias control requires case-insensitive filesystem")
    target.mkdir(parents=True, exist_ok=True)
    (root / "Anki").symlink_to(target, target_is_directory=True)
    before, preserved = files(root), files(target)
    state = deepcopy(tutor.state)

    with pytest.raises(PermissionError, match="[Rr]ead.only"):
        anki.export(tutor)

    assert files(root) == before and files(target) == preserved
    assert tutor.state == state


def test_export_does_not_create_a_file_at_an_absent_declared_resource_alias(tmp_path):
    tutor = ready_tutor(tmp_path)
    root = tutor.vault.root
    rel = f"Anki/STEM Tutor {T0:%Y-%m-%d %H%M}.apkg"
    asset_library.write_asset(root, "Library/Shared/Exports/reference.bin", b"Immutable reference", aliases=[rel])
    before = files(root)

    with pytest.raises(PermissionError, match="[Rr]ead.only"):
        anki.export(tutor)

    assert files(root) == before and not (root / rel).exists()


def test_public_anki_export_keeps_work_directory_and_existing_package(tmp_path):
    tutor = ready_tutor(tmp_path)
    root = tutor.vault.root
    work = tmp_path / "Work/Exports"
    work.mkdir(parents=True)
    (root / "Anki").symlink_to(work, target_is_directory=True)
    first = work / f"STEM Tutor {T0:%Y-%m-%d %H%M}.apkg"
    first.write_bytes(b"Previous package kept for import")
    library = files(root / "Library")

    result = anki.export(tutor)

    assert result["cards"] == 1 and (root / result["path"]).resolve().is_relative_to(work)
    assert first.read_bytes() == b"Previous package kept for import"
    assert files(root / "Library") == library
    assert len([e for e in tutor.vault.events() if e["type"] == "anki_export"]) == 1
