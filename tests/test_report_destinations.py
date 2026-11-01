"""Report-owned output admission preserves immutable resources and their adapters."""
from datetime import date
import os

import pytest

from test_lesson_destinations import files, registered_vault
from test_session import T0
from tutorlib import asset_library, report, session, store


def output(tutor, kind):
    return (report.week_note(tutor, date(2026, 10, 5)) if kind == "week"
            else report.question_sheet(tutor))


def new_tutor(tmp_path, kind):
    root = registered_vault(tmp_path)
    tutor = session.Tutor(store.Vault(root), now=lambda: T0)
    if kind == "questions":
        tutor.start("test", focus=["9702-2.1"])
        tutor.next()
    return tutor


@pytest.mark.parametrize("kind", ["week", "questions"])
@pytest.mark.parametrize("adapter", ["directory", "file", "regular"])
def test_public_report_refuses_library_resources_and_declared_adapters(tmp_path, kind, adapter):
    tutor = new_tutor(tmp_path, kind)
    root = tutor.vault.root
    rel = output(tutor, kind)
    path = root / rel
    resource = "Library/Courses/9702/Notes/" + path.name
    original = b"Immutable original teaching reference\r\n"
    asset_library.write_asset(root, resource, original, aliases=[rel])
    if adapter == "directory":
        path.unlink()
        path.parent.rmdir()
        path.parent.symlink_to((root / resource).parent, target_is_directory=True)
    elif adapter == "file":
        path.unlink()
        path.symlink_to(root / resource)
    else:
        path.write_bytes(original)
    before = files(root)

    with pytest.raises(PermissionError, match="[Rr]ead.only"):
        output(tutor, kind)

    assert files(root) == before
    assert path.is_symlink() == (adapter == "file")
    assert asset_library.AssetLibrary(root).read(resource) == original


@pytest.mark.parametrize("kind", ["week", "questions"])
def test_public_report_preserves_work_directory_adapter(tmp_path, kind):
    tutor = new_tutor(tmp_path, kind)
    root = tutor.vault.root
    shelf = "Weekly" if kind == "week" else "Question Sheets"
    work = tmp_path / "Work" / shelf
    work.mkdir(parents=True)
    (root / shelf).symlink_to(work, target_is_directory=True)
    library = files(root / "Library")
    history = files(root / ".tutor")

    rel = output(tutor, kind)

    assert (root / rel).resolve().is_relative_to(work)
    assert (root / rel).read_text().startswith("# ")
    assert files(root / "Library") == library
    assert files(root / ".tutor") == history


@pytest.mark.parametrize("kind", ["week", "questions"])
@pytest.mark.parametrize("catalog", ["valid", "missing", "damaged"])
def test_physical_case_alias_report_destination_refuses_independently_of_catalog(tmp_path, kind, catalog):
    tutor = new_tutor(tmp_path, kind)
    root = tutor.vault.root
    rel = output(tutor, kind)
    path = root / rel
    canonical = root / "Library/Courses/9702/Notes"
    canonical.mkdir(parents=True)
    alternate = root / "library/Courses/9702/Notes"
    same = alternate.exists()
    if not same:
        alternate.mkdir(parents=True)  # a genuinely distinct case-sensitive working directory
    path.unlink()
    path.parent.rmdir()
    path.parent.symlink_to(alternate, target_is_directory=True)
    if catalog == "missing":
        (root / "Library/catalog.json").unlink()
    elif catalog == "damaged":
        (root / "Library/catalog.json").write_text('{"invalid": true}')
    before = files(root)

    if same or catalog != "valid":
        with pytest.raises(PermissionError, match="[Rr]ead.only"):
            output(tutor, kind)
        assert files(root) == before
    else:
        assert not alternate.samefile(canonical)
        assert output(tutor, kind) == rel
        assert (alternate / path.name).is_file()


@pytest.mark.parametrize("kind", ["week", "questions"])
def test_report_preserves_ordinary_write_failure_boundary(tmp_path, kind, monkeypatch):
    tutor = new_tutor(tmp_path, kind)
    before = files(tutor.vault.root)

    def refused(*args, **kwargs):
        raise OSError("ordinary report output unavailable")

    monkeypatch.setattr(store, "write_text", refused)
    with pytest.raises(OSError, match="ordinary report output unavailable"):
        output(tutor, kind)
    assert files(tutor.vault.root) == before


@pytest.mark.parametrize("kind", ["week", "questions"])
@pytest.mark.parametrize("owner", ["vault_archive", "workspace_archive", "events"])
def test_public_report_refuses_known_preservation_directory_redirects(tmp_path, kind, owner):
    tutor = new_tutor(tmp_path, kind)
    root = tutor.vault.root
    shelf = "Weekly" if kind == "week" else "Question Sheets"
    protected = {"vault_archive": root / "Archive", "workspace_archive": root.parent / "Archive",
                 "events": root / ".tutor/events"}[owner]
    protected.mkdir(parents=True, exist_ok=True)
    original = protected / "learner-original.md"
    original.write_bytes(b"Original learner bytes\r\n")
    (root / shelf).symlink_to(protected, target_is_directory=True)
    before = files(root)
    preserved = files(protected)

    with pytest.raises(PermissionError, match="[Rr]ead.only"):
        output(tutor, kind)

    assert files(root) == before
    assert files(protected) == preserved


def test_public_week_report_preserves_undeclared_hardlinked_library_adapter(tmp_path):
    tutor = new_tutor(tmp_path, "week")
    root = tutor.vault.root
    rel = output(tutor, "week")
    path = root / rel
    resource = "Library/Courses/9702/Notes/" + path.name
    asset_library.write_asset(root, resource, b"Immutable original teaching reference\r\n")
    path.unlink()
    os.link(root / resource, path)
    before = files(root)

    with pytest.raises(PermissionError, match="[Rr]ead.only"):
        output(tutor, "week")

    assert files(root) == before
    assert path.samefile(root / resource) and path.stat().st_nlink == 2
