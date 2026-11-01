"""A saved Challenge answer/correction must retain its one durable event."""
import json

import pytest

from test_challenge import cs, vault  # noqa: F401 - disposable public fixtures
from tutorlib import challenge as ch


WRONG = {"correct": False, "score": 0.0, "error": "CONCEPT"}


@pytest.mark.parametrize("operation", ["record", "regrade"])
@pytest.mark.parametrize("stage", ["before-append", "after-append", "clear-save"])
def test_challenge_pending_event_recovers_once_without_rewriting_history(vault, cs, monkeypatch, operation, stage):
    if operation == "regrade":
        cs.record(0, "B", WRONG, 12)
    original = {p: p.read_bytes() for p in (vault.tutor / "events").glob("*.jsonl")}
    append, save = vault.append_event, cs._save
    saves = 0

    def interrupted_append(event, **kwargs):
        if stage == "before-append":
            raise OSError("event interrupted")
        result = append(event, **kwargs)
        if stage == "after-append":
            raise OSError("event interrupted")
        return result

    def interrupted_save():
        nonlocal saves
        saves += 1
        if stage == "clear-save" and saves == 2:
            raise OSError("intent cleanup interrupted")
        return save()

    with monkeypatch.context() as patch:
        patch.setattr(vault, "append_event", interrupted_append)
        patch.setattr(cs, "_save", interrupted_save)
        with pytest.raises(OSError, match="interrupted"):
            if operation == "record":
                cs.record(0, "B", WRONG, 12)
            else:
                cs.regrade(0, "Accepted after examiner review")

    restored = ch.ChallengeSet(vault, cs.id)
    assert restored.cursor == 1 and restored.answers[0]["response"] == "B"
    assert restored.answers[0]["seconds"] == 12
    events = list(vault.events())
    if operation == "record":
        assert len(events) == 1 and events[0]["type"] == "challenge"
        assert events[0]["correct"] is False
    else:
        assert [e["type"] for e in events] == ["challenge", "challenge_regrade"]
        assert restored.answers[0]["grade"]["correct"] is True
        assert events[1]["why"] == "Accepted after examiner review"
        assert restored.regrade(0, "Duplicate retry") is False
    assert all(p.read_bytes().startswith(b) for p, b in original.items())
    after = {p: p.read_bytes() for p in (vault.tutor / "events").glob("*.jsonl")}
    ch.ChallengeSet(vault, cs.id)
    assert {p: p.read_bytes() for p in after} == after
    assert "pending_event" not in json.loads(cs.path.read_text())


def test_legacy_challenge_without_intent_is_read_without_inventing_events(vault, cs):
    data = json.loads(cs.path.read_text())
    data["answers"] = [{"index": 0, "response": "B", "grade": WRONG, "seconds": 12, "confidence": None}]
    cs.path.write_text(json.dumps(data))
    before = cs.path.read_bytes()

    restored = ch.ChallengeSet(vault, cs.id)

    assert restored.cursor == 1 and restored.summary()["answered"] == 1
    assert cs.path.read_bytes() == before and list(vault.events()) == []


@pytest.mark.parametrize("operation", ["record", "regrade"])
def test_challenge_initial_save_failure_preserves_live_and_saved_answers(vault, cs, monkeypatch, operation):
    if operation == "regrade":
        cs.record(0, "B", WRONG, 12)
    cs.add_elapsed(0, 5)
    before = cs.path.read_bytes()
    answers = json.loads(json.dumps(cs.answers))
    events = list(vault.events())

    def readonly(*args, **kwargs):
        raise OSError("set is read-only")

    with monkeypatch.context() as patch:
        patch.setattr(ch, "write_json", readonly)
        with pytest.raises(OSError, match="read-only"):
            if operation == "record":
                cs.record(0, "B", WRONG, 12)
            else:
                cs.regrade(0, "Accepted")
    assert cs.answers == answers and cs.elapsed == {0: 5}
    assert cs.path.read_bytes() == before and list(vault.events()) == events


@pytest.mark.parametrize("operation", ["record", "regrade"])
def test_challenge_same_live_retry_finishes_original_event_once(vault, cs, monkeypatch, operation):
    if operation == "regrade":
        cs.record(0, "B", WRONG, 12)

    def interrupted(*args, **kwargs):
        raise OSError("event interrupted")

    def act():
        return cs.record(0, "B", WRONG, 12) if operation == "record" else cs.regrade(0, "Accepted")

    with monkeypatch.context() as patch:
        patch.setattr(vault, "append_event", interrupted)
        with pytest.raises(OSError):
            act()
    act()

    assert [e["type"] for e in vault.events()] == (["challenge"] if operation == "record"
                                                   else ["challenge", "challenge_regrade"])
    assert cs.answers[0]["seconds"] == 12
    assert "pending_event" not in json.loads(cs.path.read_text())


def test_challenge_conflicting_saved_intent_is_preserved_without_event_inference(vault, cs, monkeypatch):
    def interrupted(*args, **kwargs):
        raise OSError("event interrupted")

    with monkeypatch.context() as patch:
        patch.setattr(vault, "append_event", interrupted)
        with pytest.raises(OSError):
            cs.record(0, "B", WRONG, 12)
    data = json.loads(cs.path.read_text())
    data["answers"][0]["grade"]["correct"] = True
    cs.path.write_text(json.dumps(data))
    before = cs.path.read_bytes()

    with pytest.raises(ValueError, match="Mismatched"):
        ch.ChallengeSet(vault, cs.id)

    assert cs.path.read_bytes() == before and list(vault.events()) == []
