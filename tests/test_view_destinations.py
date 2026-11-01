"""Home/Now mirrors cannot replace immutable resources or their file adapters."""
import json
import os

import pytest

from fixtures import make_vault
from test_lesson_destinations import files, registered_vault
from test_session import T0
from tutorlib import asset_library, session, store, views


ORIGINAL = b"# Immutable reusable reference\r\nPreserve this exact resource and adapter.\r\n"


def output(root, tutor, name):
    if name == "Home.md":
        return views.write_home(root, tutor.packs, tutor.state, T0)
    return views.write_now(root, "Current lesson", ["Visible learner activity"])


@pytest.mark.parametrize("name", ["Home.md", "Now.md"])
@pytest.mark.parametrize("adapter", ["regular", "symlink", "hardlink"])
def test_static_views_refuse_registered_file_adapters_before_mutation(tmp_path, name, adapter):
    root = registered_vault(tmp_path)
    tutor = session.Tutor(store.Vault(root), now=lambda: T0)
    resource = "Library/Courses/9702/Notes/" + name
    asset_library.write_asset(root, resource, ORIGINAL, aliases=[name])
    path = root / name
    if adapter == "symlink":
        path.symlink_to(root / resource)
    elif adapter == "hardlink":
        os.link(root / resource, path)
    else:
        path.write_bytes(ORIGINAL)
    before = files(root)

    with pytest.raises(PermissionError, match="[Rr]ead.only"):
        output(root, tutor, name)

    assert files(root) == before and path.is_symlink() == (adapter == "symlink")
    assert asset_library.AssetLibrary(root).read(resource) == ORIGINAL


@pytest.mark.parametrize("name,catalog", [
    (name, catalog) for name in ("Home.md", "Now.md") for catalog in ("missing", "damaged", "broken-directory")
    if (name, catalog) != ("Home.md", "broken-directory")])
def test_unknown_library_ownership_refuses_static_mirror_without_writing(tmp_path, name, catalog):
    root = registered_vault(tmp_path)
    tutor = session.Tutor(store.Vault(root), now=lambda: T0)
    (root / name).write_bytes(ORIGINAL)
    if catalog == "missing":
        (root / "Library/catalog.json").unlink()
    elif catalog == "damaged":
        (root / "Library/catalog.json").write_text('{"invalid": true}')
    else:
        (root / "Library").rename(root / "saved-library")
        (root / "Library").symlink_to(root / "absent-library", target_is_directory=True)
    before = files(root)

    with pytest.raises(PermissionError, match="[Rr]ead.only"):
        output(root, tutor, name)

    assert files(root) == before


@pytest.mark.parametrize("catalog", ["valid", "missing", "damaged"])
def test_now_physical_library_case_alias_is_readonly_independent_of_catalog(tmp_path, catalog):
    root = registered_vault(tmp_path)
    canonical = root / "Library/Courses/9702/Notes"
    canonical.mkdir(parents=True)
    alternate = root / "library/Courses/9702/Notes"
    same = alternate.exists()
    if not same:
        alternate.mkdir(parents=True)
    if catalog == "missing":
        (root / "Library/catalog.json").unlink()
    elif catalog == "damaged":
        (root / "Library/catalog.json").write_text('{"invalid": true}')
    before = files(root)

    if same:
        assert alternate.samefile(canonical)
        with pytest.raises(PermissionError, match="[Rr]ead.only"):
            views.write_now(alternate, "Read-only Library", ["Do not create a learner view here"])
        assert files(root) == before
    else:
        assert not alternate.samefile(canonical)
        assert views.write_now(alternate, "Working directory", ["Mutable content"]) == "Now.md"


@pytest.mark.parametrize("name", ["Home.md", "Now.md"])
@pytest.mark.parametrize("location", ["ordinary", "legacy", "work-directory"])
def test_static_views_preserve_normal_unregistered_and_work_output(tmp_path, name, location):
    root = make_vault(tmp_path) if location == "legacy" else registered_vault(tmp_path)
    tutor = session.Tutor(store.Vault(root), now=lambda: T0)
    destination = root
    if location == "work-directory":
        work = tmp_path / "Work" / "Views"
        work.mkdir(parents=True)
        destination = root / "working-views"
        destination.symlink_to(work, target_is_directory=True)
    library = files(root / "Library")
    history = files(root / ".tutor")

    assert output(destination, tutor, name) == name
    assert (destination / name).read_text().startswith("# ")
    assert files(root / "Library") == library and files(root / ".tutor") == history


def test_readonly_now_does_not_interrupt_durable_question_and_session_saves(tmp_path):
    root = registered_vault(tmp_path)
    tutor = session.Tutor(store.Vault(root), now=lambda: T0)
    resource = "Library/Courses/9702/Notes/current-reference.md"
    asset_library.write_asset(root, resource, ORIGINAL, aliases=["Now.md"])
    (root / "Now.md").write_bytes(ORIGINAL)
    library = files(root / "Library")

    tutor.start("test", focus=["9702-2.1"])
    question = tutor.next()["items"][0]
    tutor.answer(f"{question['n']}?")

    assert store.read_json(tutor.session_path) == json.loads(json.dumps(tutor.session))
    assert store.read_json(tutor.state_path) == tutor.state
    assert any(event["type"] == "answer" for event in tutor.vault.events())
    assert "Now" in tutor.session["view_errors"] and "Now.md" in tutor.view_warnings
    assert (root / "Now.md").read_bytes() == ORIGINAL and files(root / "Library") == library


@pytest.mark.parametrize("boundary", ["state", "session", "ordinary-now"])
def test_readonly_now_handling_does_not_swallow_other_save_failures(tmp_path, monkeypatch, boundary):
    root = registered_vault(tmp_path)
    tutor = session.Tutor(store.Vault(root), now=lambda: T0)
    tutor.start("test", focus=["9702-2.1"])
    if boundary != "ordinary-now":
        resource = "Library/Courses/9702/Notes/protected-current.md"
        asset_library.write_asset(root, resource, ORIGINAL, aliases=["Now.md"])
        (root / "Now.md").write_bytes(ORIGINAL)
    before = tutor.session_path.read_bytes()
    real_write = session.write_json
    target = tutor.state_path if boundary == "state" else tutor.session_path

    def refused(path, *args, **kwargs):
        if path == target:
            raise OSError("critical save refused")
        return real_write(path, *args, **kwargs)

    def refused_now(*args, **kwargs):
        raise OSError("ordinary Now write refused")

    if boundary == "ordinary-now":
        monkeypatch.setattr(views, "write_now", refused_now)
    else:
        monkeypatch.setattr(session, "write_json", refused)
    tutor._dirty = True
    with pytest.raises(OSError, match="refused"):
        tutor._save()
    assert tutor.session_path.read_bytes() == before
    if boundary != "ordinary-now":
        assert (root / "Now.md").read_bytes() == ORIGINAL
