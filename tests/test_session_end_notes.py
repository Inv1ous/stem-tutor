"""A failed convenience note refresh must still return the durable session summary."""
import random
from pathlib import Path

import pytest

from fixtures import make_vault
from test_session import T0
from tutorlib import session, store, views


def test_notes_replace_failure_returns_summary_and_keeps_history_closed(tmp_path, monkeypatch):
    tutor = session.Tutor(store.Vault(make_vault(tmp_path)), rng=random.Random(0), now=lambda: T0)
    subtopic = "9702-2.1"
    note = tutor.vault.root / views.notes_update(tutor.vault.root, tutor.packs, tutor.state, subtopic)
    note.write_text(note.read_text() + "\nMy own paragraph stays here.\n")
    original_note = note.read_bytes()
    tutor.start("test", focus=[subtopic])
    sid = tutor.session["id"]
    first = tutor.next()["items"][0]
    tutor.answer(f"{first['n']}?")
    earlier_events = {p: p.read_bytes() for p in (tutor.vault.tutor / "events").glob("*.jsonl")}
    original_replace = store.os.replace

    def refuse_note_replace(source, destination):
        if Path(destination) == note:
            raise OSError("notes file unavailable")
        return original_replace(source, destination)

    monkeypatch.setattr(store.os, "replace", refuse_note_replace)

    summary = tutor.end()

    assert summary["session"] == sid
    assert summary["answered"] == 1 and summary["correct"] == 0
    assert summary["view_errors"] == {f"My Notes {subtopic}": "notes file unavailable"}
    assert "home_error" not in summary
    assert (tutor.vault.root / "Home.md").is_file()
    assert tutor.session is None
    assert note.read_bytes() == original_note
    closed_events = {p: p.read_bytes() for p in earlier_events}
    assert all(closed_events[p].startswith(before) for p, before in earlier_events.items())
    restarted = session.Tutor(tutor.vault, now=lambda: T0)
    assert restarted.session is None and restarted.state == restarted._fold()
    assert restarted.next()["activity"] == "no_session"
    assert restarted.end()["session"] is None
    assert all(p.read_bytes() == data for p, data in closed_events.items())
    ends = [e for e in restarted.vault.events() if e["type"] == "session_end" and e["session"] == sid]
    assert len(ends) == 1


def test_transcript_summary_failure_closes_live_session_without_duplicate_ends(tmp_path, monkeypatch):
    tutor = session.Tutor(store.Vault(make_vault(tmp_path)), rng=random.Random(0), now=lambda: T0)
    tutor.start("test", focus=["9702-2.1"])
    sid = tutor.session["id"]
    first = tutor.next()["items"][0]
    tutor.answer(f"{first['n']}?")
    transcript = tutor.vault.root / tutor.session["log"]
    transcript_bytes = transcript.read_bytes()
    earlier_events = {p: p.read_bytes() for p in (tutor.vault.tutor / "events").glob("*.jsonl")}
    real_open = open

    def refuse_transcript_append(file, mode="r", *args, **kwargs):
        if file == transcript and mode == "a":
            raise OSError("lesson summary unavailable")
        return real_open(file, mode, *args, **kwargs)

    monkeypatch.setattr("builtins.open", refuse_transcript_append)

    summary = tutor.end()

    assert summary["session"] == sid and summary["answered"] == 1
    assert summary["view_errors"] == {"Lesson transcript": "lesson summary unavailable"}
    assert tutor.session is None
    assert tutor.end()["session"] is None
    assert transcript.read_bytes() == transcript_bytes
    closed_events = {p: p.read_bytes() for p in earlier_events}
    assert all(closed_events[p].startswith(before) for p, before in earlier_events.items())
    restarted = session.Tutor(tutor.vault, now=lambda: T0)
    assert restarted.session is None
    assert restarted.state == tutor.state == restarted._fold()
    assert restarted.end()["session"] is None
    assert all(p.read_bytes() == data for p, data in closed_events.items())
    ends = [e for e in restarted.vault.events() if e["type"] == "session_end" and e["session"] == sid]
    assert len(ends) == 1


@pytest.mark.parametrize("boundary", ["event", "closed_session_save"])
def test_durable_end_failures_still_propagate(tmp_path, monkeypatch, boundary):
    tutor = session.Tutor(store.Vault(make_vault(tmp_path)), now=lambda: T0)
    tutor.start("test", focus=["9702-2.1"])
    sid = tutor.session["id"]
    original_append = tutor.vault.append_event
    original_write = session.write_json

    def failed_append(event, **kwargs):
        if event["type"] == "session_end":
            raise OSError("event unavailable")
        return original_append(event, **kwargs)

    def failed_close(path, data, *args, **kwargs):
        if path == tutor.session_path and data is None:
            raise OSError("session cache unavailable")
        return original_write(path, data, *args, **kwargs)

    with monkeypatch.context() as patch:
        if boundary == "event":
            patch.setattr(tutor.vault, "append_event", failed_append)
        else:
            patch.setattr(session, "write_json", failed_close)
        with pytest.raises(OSError, match="unavailable"):
            tutor.end()

    ends = [e for e in tutor.vault.events() if e["type"] == "session_end" and e["session"] == sid]
    assert len(ends) == (0 if boundary == "event" else 1)
    restarted = session.Tutor(tutor.vault, now=lambda: T0)
    assert (restarted.session is not None) is (boundary == "event")
    assert restarted.state == restarted._fold()


@pytest.mark.parametrize("boundary", ["before_append", "after_append"])
def test_live_end_retry_reconciles_durable_status_before_appending(tmp_path, monkeypatch, boundary):
    tutor = session.Tutor(store.Vault(make_vault(tmp_path)), now=lambda: T0)
    tutor.start("test", focus=["9702-2.1"])
    sid = tutor.session["id"]
    first = tutor.next()["items"][0]
    tutor.answer(f"{first['n']}?")
    before = {p: p.read_bytes() for p in (tutor.vault.tutor / "events").glob("*.jsonl")}

    def failed(*args, **kwargs):
        raise OSError("critical end persistence unavailable")

    with monkeypatch.context() as patch:
        if boundary == "before_append":
            patch.setattr(tutor.vault, "append_event", failed)
        else:
            patch.setattr(tutor, "_save", failed)
        with pytest.raises(OSError, match="critical end persistence unavailable"):
            tutor.end()
    after_failure = {p: p.read_bytes() for p in before}
    assert all(after_failure[p].startswith(data) for p, data in before.items())

    summary = tutor.end()

    assert summary["session"] == sid and summary["answered"] == 1
    assert tutor.session is None
    after_retry = {p: p.read_bytes() for p in before}
    if boundary == "after_append":
        assert after_retry == after_failure
    else:
        assert all(after_retry[p].startswith(data) for p, data in after_failure.items())
    restarted = session.Tutor(tutor.vault, now=lambda: T0)
    assert restarted.session is None
    assert restarted.state == tutor.state == restarted._fold()
    assert tutor.end()["session"] is None and restarted.end()["session"] is None
    assert all(p.read_bytes() == data for p, data in after_retry.items())
    ends = [e for e in restarted.vault.events() if e["type"] == "session_end" and e["session"] == sid]
    assert len(ends) == 1
