from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from fixtures import make_vault
from tutorlib import report, session, store

NOW = datetime.fromisoformat("2026-10-20T12:00:00+08:00")
KC = "9702-2.1.1"
NOTE = ("# Scratch note\n\n<!-- stem-tutor:status -->\nold status\n<!-- /stem-tutor:status -->\n\n"
        "## My working\nVelocity = displacement / time.\n")


def answer(when: datetime, item: str) -> dict:
    return {"type": "answer", "ts": when.isoformat(), "item": item, "kcs": [KC],
            "subject": "phys", "difficulty": 3, "conf": 3, "marks": 1, "seconds": 30,
            "grade": {"correct": True, "score": 1.0, "error": None, "misconception": None}}


@pytest.mark.parametrize("days_ago", [1, 35])
def test_an_older_synced_answer_reaches_cached_progress(tmp_path, monkeypatch, days_ago):
    """B-070 (bug watch): a conflict copy can add history without changing the last event."""
    monkeypatch.setattr(report, "almanac_push", lambda tutor: None)
    vault = store.Vault(make_vault(tmp_path))
    tutor = session.Tutor(vault, now=lambda: NOW)
    tutor.log(answer(NOW, "here"))
    newest = vault.last_event_id()
    earlier = NOW - timedelta(days=days_ago)
    synced = {"id": "fromphone", **answer(earlier, "there")}
    conflict = vault.tutor / "events" / f"{earlier:%Y-%m} 2.jsonl"
    conflict.write_text(json.dumps(synced) + "\n", encoding="utf-8")
    assert vault.last_event_id() == newest

    again = session.Tutor(vault, now=lambda: NOW)
    assert again.state["kcs"][KC]["n"] == 2
    assert again.state == again._fold()
    again._save()

    # A later sync may replace a copy with the same byte length, rather than append to it.
    synced["item"] = "other"
    conflict.write_text(json.dumps(synced) + "\n", encoding="utf-8")
    again = session.Tutor(vault, now=lambda: NOW)
    assert "other" in again.state["items_seen"] and "there" not in again.state["items_seen"]
    assert again.state == again._fold()
    again.rebuild()
    assert again.state == again._fold()
    again._save()

    def unexpected_fold(self):
        pytest.fail("An unchanged log should reuse its saved progress")

    monkeypatch.setattr(session.Tutor, "_fold", unexpected_fold)
    assert session.Tutor(vault, now=lambda: NOW).state == again.state


def refuse_replace(src: Path, dst: Path) -> None:
    raise OSError("This mount refuses replacing a file")


def test_a_refused_replacement_leaves_the_learners_note_untouched(tmp_path, monkeypatch):
    """B-142 (bug watch): don't risk an interrupted in-place write of My working."""
    note = tmp_path / "scratch.md"
    note.write_text(NOTE, encoding="utf-8")
    real_write = Path.write_text

    def interrupted(path, text, *args, **kwargs):
        if path == note:
            real_write(path, text[:42], *args, **kwargs)
            raise OSError("Interrupted write")
        return real_write(path, text, *args, **kwargs)

    monkeypatch.setattr(store.os, "replace", refuse_replace)
    monkeypatch.setattr(Path, "write_text", interrupted)
    with pytest.raises(OSError, match="refuses replacing"):
        store.write_text(note, NOTE.replace("old status", "new status"))
    assert note.read_text(encoding="utf-8") == NOTE


def test_failed_writes_leave_the_learners_note_readable(tmp_path, monkeypatch):
    """B-142 (bug watch): failed writes and restoration must leave the visible note intact."""
    note = tmp_path / "scratch.md"
    note.write_text(NOTE, encoding="utf-8")
    updated = NOTE.replace("old status", "new status")
    real_write = Path.write_text

    def interrupted(path, text, *args, **kwargs):
        if path == note:
            real_write(path, text[:42], *args, **kwargs)
            raise OSError("Disk full")
        return real_write(path, text, *args, **kwargs)

    def failed_restore(path, data):
        raise OSError("Still full")

    monkeypatch.setattr(store.os, "replace", refuse_replace)
    monkeypatch.setattr(Path, "write_text", interrupted)
    monkeypatch.setattr(Path, "write_bytes", failed_restore)
    with pytest.raises(OSError):
        store.write_text(note, updated)
    assert note.read_text(encoding="utf-8") == NOTE
    assert any(p.read_text(encoding="utf-8") == updated for p in tmp_path.glob(".*.tmp"))


def test_a_refused_replacement_can_be_retried_without_losing_the_learners_note(tmp_path, monkeypatch):
    """B-142 (bug watch): refuse unsafe writes even when in-place writing would work."""
    note = tmp_path / "scratch.md"
    note.write_text(NOTE, encoding="utf-8")
    updated = NOTE.replace("old status", "new status")
    with monkeypatch.context() as patch:
        patch.setattr(store.os, "replace", refuse_replace)
        with pytest.raises(OSError, match="refuses replacing"):
            store.write_text(note, updated)
        assert note.read_text(encoding="utf-8") == NOTE
    assert store.write_text(note, updated)
    assert note.read_text(encoding="utf-8") == updated
