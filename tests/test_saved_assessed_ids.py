"""New answers from old saved attempts count each assessed ID once."""
import copy
import json
from datetime import datetime, timedelta

import pytest

from fixtures import make_vault
from tutorlib import session, store

NOW = datetime.fromisoformat("2026-10-27T12:00:00+08:00")
KC, OTHER = "9702-2.1.4", "9702-2.1.1"


@pytest.mark.parametrize("assessed", [[KC, KC], [KC, OTHER, KC, OTHER]])
@pytest.mark.parametrize("append_fails", [False, True])
def test_old_admission_saved_question_emits_unique_new_ids_without_revising_history(
        tmp_path, monkeypatch, assessed, append_fails):
    root = make_vault(tmp_path)
    source = root / ".tutor/packs/v1/specs/9702/packs/9702-2.1.json"
    raw = json.loads(source.read_text())
    raw["items"] = [copy.deepcopy(raw["items"][4])]
    raw["items"][0]["kcs"] = assessed
    source.write_text(json.dumps(raw))
    source_bytes = source.read_bytes()
    vault = store.Vault(root)
    legacy = vault.append_event({"type": "answer", "item": "old-duplicate", "kcs": assessed,
                                 "subject": "phys", "difficulty": 3, "marks": 1, "hinted": False,
                                 "grade": {"correct": False, "score": 0.0, "error": "RECALL"}},
                                now=NOW - timedelta(days=1))
    old = session.Tutor(vault, now=lambda: NOW)
    # Represent the original admission behavior only while creating an actual
    # old-format saved question; current production source is never reverted.
    old.packs.pack = lambda _: copy.deepcopy(raw)
    old.start("long", 15, focus=[KC])
    question, = old.next()["items"]
    old.save_structured_draft(question["n"], "My original working remains saved.")
    saved = json.loads(old.session_path.read_text())["presented"][str(question["n"])]
    history = {path: path.read_bytes() for path in vault.tutor.glob("events/*.jsonl")}
    tutor = session.Tutor(store.Vault(root), now=lambda: NOW)
    pending = tutor.session["presented"][str(question["n"])]
    assert pending == saved
    guard = session._guard_identity(pending)
    unique = list(dict.fromkeys(assessed))
    counts = {kc: tutor.state["kcs"][kc]["n"] for kc in unique}
    assert all(count == 2 for count in counts.values())
    tutor.next()
    if append_fails:
        original_append = tutor.vault.append_event
        def unavailable(event, **kwargs):
            if event["type"] == "answer":
                raise OSError("New answer append failed before durability")
            return original_append(event, **kwargs)
        with monkeypatch.context() as patch:
            patch.setattr(tutor.vault, "append_event", unavailable)
            with pytest.raises(OSError, match="before durability"):
                tutor.answer(f"{question['n']} pts=0")
        assert pending == saved
        assert all(path.read_bytes() == data for path, data in history.items())
    tutor.answer(f"{question['n']} pts=0")

    assert all(tutor.state["kcs"][kc]["n"] - counts[kc] == 1 for kc in unique)
    new, = [event for event in tutor.vault.events() if event.get("item") == raw["items"][0]["id"]]
    assert new["kcs"] == unique
    assert tutor.session["kcs_answered"] == unique
    assert pending["kcs"] == assessed and pending["inst"] == saved["inst"]
    assert pending["saved_work"] == saved["saved_work"]
    assert session._guard_identity(pending) == guard
    assert next(event for event in tutor.vault.events() if event["id"] == legacy["id"]) == legacy
    before = copy.deepcopy(tutor.state)
    restarted = session.Tutor(store.Vault(root), now=lambda: NOW)
    restarted.rebuild()
    assert restarted.state == before
    assert all(path.read_bytes().startswith(data) for path, data in history.items())
    assert source.read_bytes() == source_bytes
