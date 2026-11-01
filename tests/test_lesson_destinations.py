"""Immutable lesson destinations must not block durable learner work."""
import json
import os
import random

import pytest

from fixtures import make_vault
from test_session import T0
from tutorlib import asset_library, session, store, views


RESOURCE = "Library/Courses/9702/Notes/archived-lesson.md"


def registered_vault(tmp_path):
    root = make_vault(tmp_path).resolve()
    (root / ".tutor/packs/v1/papers.json").write_text('{"papers": []}')
    for file in (root / ".tutor/packs/v1").rglob("*.json"):
        relative = file.relative_to(root / ".tutor/packs/v1").as_posix()
        asset_library.write_asset(root, "Library/Releases/v1/" + relative, file.read_bytes(),
                                  aliases=[file.relative_to(root).as_posix()])
    return root


def files(folder):
    return {p.relative_to(folder).as_posix(): p.read_bytes() for p in folder.rglob("*") if p.is_file()}


@pytest.mark.parametrize("method", ["add", "recover_answer"])
@pytest.mark.parametrize("adapter", ["regular", "symlink"])
def test_registered_valid_lesson_alias_refuses_every_update(tmp_path, method, adapter):
    log = views.LessonLog.create(tmp_path, "Lesson - Example", T0)
    path = tmp_path / log.rel
    original = path.read_bytes()
    asset_library.write_asset(tmp_path, RESOURCE, original, aliases=[log.rel])
    if adapter == "symlink":
        path.unlink()
        path.symlink_to(tmp_path / RESOURCE)
    before = files(tmp_path / "Library")
    with pytest.raises(PermissionError, match="[Rr]ead.only"):
        if method == "add":
            log.add("Learner continuation")
        else:
            log.recover_answer({"n": 1, "correct": True, "partial": False, "answer": "B"}, "B")
    assert files(tmp_path / "Library") == before
    assert path.read_bytes() == original
    assert path.is_symlink() == (adapter == "symlink")


@pytest.mark.parametrize("catalog", ["valid", "missing", "damaged"])
def test_new_session_refuses_library_directory_adapter_before_any_state_or_event(tmp_path, catalog):
    root = registered_vault(tmp_path)
    tutor = session.Tutor(store.Vault(root), now=lambda: T0)
    shelf = root / "Library/Courses/9702/Notes"
    shelf.mkdir(parents=True)
    (root / "Lessons").symlink_to(shelf, target_is_directory=True)
    if catalog == "missing":
        (root / "Library/catalog.json").unlink()
    elif catalog == "damaged":
        (root / "Library/catalog.json").write_text('{"invalid": true}')
    before = files(root)

    result = tutor.start("test", focus=["9702-2.1"])

    assert result.get("error") and result.get("ok") is False
    assert tutor.session is None
    assert files(root) == before


@pytest.mark.parametrize("adapter", ["regular", "symlink"])
@pytest.mark.parametrize("interrupted", [False, True])
def test_resumed_immutable_log_keeps_question_draft_answer_recovery_and_end(tmp_path, monkeypatch,
                                                                        adapter, interrupted):
    root = registered_vault(tmp_path)
    tutor = session.Tutor(store.Vault(root), rng=random.Random(0), now=lambda: T0)
    tutor.start("test", focus=["9702-2.1"])
    first = tutor.next()["items"][0]
    rel = tutor.session["log"]
    path = root / rel
    original = path.read_bytes()
    asset_library.write_asset(root, RESOURCE, original, aliases=[rel])
    if adapter == "symlink":
        path.unlink()
        path.symlink_to(root / RESOURCE)
    p = tutor.session["presented"][str(first["n"])]
    p["saved_work"] = "My unfinished learner draft"
    tutor._save()
    pending = json.loads(json.dumps(tutor.session["presented"]))
    prefix = files(root / ".tutor/events")
    library = files(root / "Library")
    tutor = session.Tutor(store.Vault(root), now=lambda: T0)
    assert tutor.session["presented"] == pending
    assert tutor.session["log"] == rel
    tutor.next()  # the public resume route can append question/step cards
    if interrupted:
        save = tutor._save

        def fail_after_answer():
            if any(e["type"] == "answer" for e in tutor.vault.events()):
                raise OSError("interrupted after durable answer")
            return save()

        monkeypatch.setattr(tutor, "_save", fail_after_answer)
        with pytest.raises(OSError, match="interrupted after durable answer"):
            tutor.answer(f"{first['n']}?")
        tutor = session.Tutor(store.Vault(root), now=lambda: T0)
    else:
        assert tutor.answer(f"{first['n']}?")["results"]
    assert len([e for e in tutor.vault.events() if e["type"] == "answer"]) == 1
    assert tutor.session["log"] == rel
    assert tutor.state == tutor._fold()
    result = tutor.end()
    assert result["answered"] == 1 and "Lesson transcript" in result["view_errors"]
    assert "read-only" in result["view_errors"]["Lesson transcript"].lower()
    assert tutor.session is None
    assert files(root / "Library") == library
    assert path.read_bytes() == original
    assert path.is_symlink() == (adapter == "symlink")
    assert all((root / ".tutor/events" / name).read_bytes().startswith(data) for name, data in prefix.items())
    closed = files(root / ".tutor/events")
    restarted = session.Tutor(store.Vault(root), now=lambda: T0)
    assert restarted.session is None and restarted.state == restarted._fold()
    assert files(root / ".tutor/events") == closed


def test_work_directory_adapter_remains_mutable_for_transcript_and_recovery(tmp_path):
    root = tmp_path / "Vault"
    root.mkdir()
    work = tmp_path / "Work/Lessons"
    work.mkdir(parents=True)
    (root / "Lessons").symlink_to(work, target_is_directory=True)
    log = views.LessonLog.create(root, "Lesson - Example", T0)
    log.add("Learner continuation")
    fb = {"n": 1, "correct": True, "partial": False, "answer": "B"}
    log.recover_answer(fb, "B")
    before = (root / log.rel).read_bytes()
    log.recover_answer(fb, "B")
    assert (root / log.rel).resolve().is_relative_to(work)
    assert b"Learner continuation" in before
    assert (root / log.rel).read_bytes() == before


@pytest.mark.parametrize("owner", ["vault_archive", "workspace_archive", "events"])
def test_new_log_never_writes_redirected_preservation_directories(tmp_path, owner):
    root = tmp_path / "Vault"
    root.mkdir()
    shelf = {"vault_archive": root / "Archive", "workspace_archive": tmp_path / "Archive",
             "events": root / ".tutor/events"}[owner]
    shelf.mkdir(parents=True)
    original = shelf / "original.md"
    original.write_bytes(b"Original preserved bytes\r\n")
    (root / "Lessons").symlink_to(shelf, target_is_directory=True)
    before = files(shelf)
    with pytest.raises(PermissionError, match="[Rr]ead.only"):
        views.LessonLog.create(root, "Lesson - Example", T0)
    assert files(shelf) == before


def test_read_only_new_destination_does_not_end_or_change_existing_session(tmp_path):
    root = registered_vault(tmp_path)
    tutor = session.Tutor(store.Vault(root), now=lambda: T0)
    tutor.start("test", focus=["9702-2.1"])
    first = tutor.next()["items"][0]
    tutor.answer(f"{first['n']}?")
    work = tmp_path / "Working lessons"
    (root / "Lessons").rename(work)
    (root / "Lessons").symlink_to(root / "Library", target_is_directory=True)
    before = files(root)
    original = json.loads(json.dumps(tutor.session))

    result = tutor.start("test", focus=["9702-2.1"], replace=True)

    assert result.get("error") and result.get("ok") is False
    assert json.loads(json.dumps(tutor.session)) == original
    assert files(root) == before
    assert not any(e["type"] == "session_end" for e in tutor.vault.events())


def test_public_session_keeps_valid_work_directory_adapter(tmp_path):
    root = registered_vault(tmp_path)
    work = tmp_path / "Work/Lessons"
    work.mkdir(parents=True)
    (root / "Lessons").symlink_to(work, target_is_directory=True)
    tutor = session.Tutor(store.Vault(root), now=lambda: T0)
    assert tutor.start("test", focus=["9702-2.1"]).get("session")
    first = tutor.next()["items"][0]
    tutor.answer(f"{first['n']}?")
    path = root / tutor.session["log"]
    assert path.resolve().is_relative_to(work)
    assert f"Q{first['n']}" in path.read_text()
    assert "view_errors" not in tutor.end()


def test_ordinary_transcript_creation_io_failure_propagates_without_partial_new_session(tmp_path, monkeypatch):
    root = registered_vault(tmp_path)
    tutor = session.Tutor(store.Vault(root), now=lambda: T0)
    before = files(root)

    def failed_write(*args, **kwargs):
        raise OSError("ordinary transcript write unavailable")

    monkeypatch.setattr(views, "_write", failed_write)
    with pytest.raises(OSError, match="ordinary transcript write unavailable"):
        tutor.start("test", focus=["9702-2.1"])
    assert tutor.session is None
    assert files(root) == before


def test_read_only_transcript_preserves_real_skipped_guard_through_resume_and_end(tmp_path):
    from test_blurt_guards import skipped_tutor

    tutor = skipped_tutor(tmp_path)
    root = tutor.vault.root
    (root / ".tutor/packs/v1/papers.json").write_text('{"papers": []}')
    for file in (root / ".tutor/packs/v1").rglob("*.json"):
        relative = file.relative_to(root / ".tutor/packs/v1").as_posix()
        asset_library.write_asset(root, "Library/Releases/v1/" + relative, file.read_bytes(),
                                  aliases=[file.relative_to(root).as_posix()])
    rel = tutor.session["log"]
    path = root / rel
    asset_library.write_asset(root, RESOURCE, path.read_bytes(), aliases=[rel])
    path.unlink()
    path.symlink_to(root / RESOURCE)
    guards = json.loads(json.dumps(tutor.marking_guards()))
    guard_bytes = (root / ".tutor/state/deferred-notes.json").read_bytes()
    library = files(root / "Library")
    tutor = session.Tutor(store.Vault(root), now=lambda: T0)
    assert tutor.marking_guards() == guards
    tutor.show("notice", "The saved question remains protected.")
    assert tutor.session["log"] == rel
    result = tutor.end(abandoned=True)
    assert "Lesson transcript" in result["view_errors"]
    assert tutor.marking_guards() == guards
    assert (root / ".tutor/state/deferred-notes.json").read_bytes() == guard_bytes
    assert files(root / "Library") == library


def test_public_resumed_undeclared_library_hardlink_is_read_only_but_progress_continues(tmp_path):
    root = registered_vault(tmp_path)
    tutor = session.Tutor(store.Vault(root), now=lambda: T0)
    tutor.start("test", focus=["9702-2.1"])
    first = tutor.next()["items"][0]
    rel = tutor.session["log"]
    path = root / rel
    original = path.read_bytes()
    asset_library.write_asset(root, RESOURCE, original)  # deliberately no logical lesson alias
    path.unlink()
    os.link(root / RESOURCE, path)
    library = files(root / "Library")
    prefix = files(root / ".tutor/events")
    tutor = session.Tutor(store.Vault(root), now=lambda: T0)

    tutor.next()
    tutor.answer(f"{first['n']}?")
    result = tutor.end()

    assert "Lesson transcript" in result["view_errors"]
    assert result["answered"] == 1
    assert path.stat().st_nlink == 2 and path.samefile(root / RESOURCE)
    assert files(root / "Library") == library
    assert asset_library.AssetLibrary(root).read(RESOURCE) == original
    assert all((root / ".tutor/events" / name).read_bytes().startswith(data) for name, data in prefix.items())
    restarted = session.Tutor(store.Vault(root), now=lambda: T0)
    assert restarted.session is None and restarted.state == restarted._fold()
    assert len([e for e in restarted.vault.events() if e["type"] == "answer"]) == 1


def test_first_read_only_warning_survives_durable_end_then_critical_save_failure(tmp_path, monkeypatch):
    root = registered_vault(tmp_path)
    tutor = session.Tutor(store.Vault(root), now=lambda: T0)
    tutor.start("test", focus=["9702-2.1"])
    rel = tutor.session["log"]
    path = root / rel
    asset_library.write_asset(root, RESOURCE, path.read_bytes(), aliases=[rel])
    path.unlink()
    path.symlink_to(root / RESOURCE)
    library = files(root / "Library")
    save = tutor._save

    def fail_after_end():
        if any(e["type"] == "session_end" for e in tutor.vault.events()):
            raise OSError("critical session save failed")
        return save()

    with monkeypatch.context() as patch:
        patch.setattr(tutor, "_save", fail_after_end)
        with pytest.raises(OSError, match="critical session save failed"):
            tutor.end()
    result = tutor.end()
    assert "Lesson transcript" in result["view_errors"]
    assert tutor.session is None
    assert len([e for e in tutor.vault.events() if e["type"] == "session_end"]) == 1
    assert files(root / "Library") == library
