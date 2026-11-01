"""Explicit corrections update current earned marks after restart or later answers."""
import json
import random

import pytest

from fixtures import make_vault
from test_session import T0
from tutorlib import session, store


def tutor_with_answer(tmp_path, score):
    tutor = session.Tutor(store.Vault(make_vault(tmp_path)), rng=random.Random(0), now=lambda: T0)
    tutor.start("test", focus=["9702-2.1"])
    items = tutor.next()["items"]
    first = items[0]
    feedback = tutor.answer(f"{first['n']}A3", judge={first["n"]: score})["results"][0]
    return tutor, feedback["event"], items


@pytest.mark.parametrize("score", [0.0, 0.5, 0.065])
@pytest.mark.parametrize("timing", ["restored", "earlier"])
def test_supported_earlier_or_restored_regrade_updates_marks_once(tmp_path, score, timing):
    tutor, event, items = tutor_with_answer(tmp_path, score)
    if timing == "restored":
        tutor = session.Tutor(tutor.vault, now=lambda: T0)
    else:
        second = items[1]
        assert tutor.answer(f"{second['n']} = 1 ~3", judge={second["n"]: 1.0})["results"]
    total = tutor.session["marks_total"]
    prefix = {p: p.read_bytes() for p in (tutor.vault.tutor / "events").glob("*.jsonl")}

    assert tutor.regrade(event, "Second marker accepted the full answer")["ok"]

    expected = total  # every answered question is now fully correct
    assert tutor.session["marks_earned"] == expected
    assert tutor.session["marks_total"] == total
    after = {p: p.read_bytes() for p in prefix}
    snapshot = json.loads(json.dumps(tutor.session))
    assert tutor.regrade(event, "Repeated correction")["ok"] is False
    assert json.loads(json.dumps(tutor.session)) == snapshot
    assert all(p.read_bytes() == data for p, data in after.items())
    assert all(p.read_bytes().startswith(data) for p, data in prefix.items())
    assert len([e for e in tutor.vault.events() if e["type"] == "regrade"]) == 1
    tutor = session.Tutor(tutor.vault, now=lambda: T0)
    assert tutor.state == tutor._fold()
    assert tutor.end()["marks"] == [expected, total]


@pytest.mark.parametrize("score", [0.0, 0.5])
def test_immediate_correction_keeps_existing_mark_rollback_behavior(tmp_path, score):
    tutor, event, _ = tutor_with_answer(tmp_path, score)
    assert tutor.regrade(event, "Accepted answer")["ok"]
    assert tutor.session["marks_earned"] == tutor.session["marks_total"] == 1
    assert tutor.end()["marks"] == [1, 1]


@pytest.mark.parametrize("score", [0.0, 0.5])
def test_old_ended_session_correction_preserves_other_live_session_marks_and_history(tmp_path, score):
    tutor, event, _ = tutor_with_answer(tmp_path, score)
    tutor.end()
    ended = next(e for e in tutor.vault.events() if e["type"] == "session_end")
    tutor.start("test", focus=["9702-2.1.1"])
    item = tutor.next()["items"][0]
    tutor.answer(f"{item['n']}A3", judge={item["n"]: 0.0})
    before = (tutor.session["marks_earned"], tutor.session["marks_total"], tutor.session["correct"])

    assert tutor.regrade(event, "Correction belongs to the previous session")["ok"]

    assert (tutor.session["marks_earned"], tutor.session["marks_total"], tutor.session["correct"]) == before
    assert next(e for e in tutor.vault.events() if e["id"] == ended["id"]) == ended
    assert tutor.end()["marks"] == list(before[:2])


@pytest.mark.parametrize("boundary", ["save_after_event", "after_log"])
@pytest.mark.parametrize("retry", ["live", "restart", "finish"])
def test_durable_correction_reconciles_summary_after_interruption_without_double_credit(tmp_path, monkeypatch,
                                                                                       boundary, retry):
    tutor, event, _ = tutor_with_answer(tmp_path, 0.5)
    prefix = {p: p.read_bytes() for p in (tutor.vault.tutor / "events").glob("*.jsonl")}
    original_save, original_log = tutor._save, tutor.log

    def fail_save():
        if any(e["type"] == "regrade" for e in tutor.vault.events()):
            raise OSError("critical correction persistence interrupted")
        return original_save()

    def stop_after_log(value):
        result = original_log(value)
        if value["type"] == "regrade":
            raise OSError("critical correction persistence interrupted")
        return result

    with monkeypatch.context() as patch:
        if boundary == "save_after_event":
            patch.setattr(tutor, "_save", fail_save)
        else:
            patch.setattr(tutor, "log", stop_after_log)
        with pytest.raises(OSError, match="critical correction persistence interrupted"):
            tutor.regrade(event, "Second marker accepted answer")
    if retry == "restart":
        tutor = session.Tutor(tutor.vault, now=lambda: T0)
    if retry == "finish":
        result = tutor.end()
        assert result["marks"] == [1, 1] and result["accuracy"] == 1
        assert len([e for e in tutor.vault.events() if e["type"] == "regrade"]) == 1
        assert all(p.read_bytes().startswith(data) for p, data in prefix.items())
        return
    assert tutor.regrade(event, "Retry after interrupted correction")["ok"] is False
    assert tutor.session["correct"] == 1
    assert tutor.session["marks_earned"] == tutor.session["marks_total"] == 1
    assert len([e for e in tutor.vault.events() if e["type"] == "regrade"]) == 1
    assert all(p.read_bytes().startswith(data) for p, data in prefix.items())
    result = tutor.end()
    assert result["marks"] == [1, 1] and result["accuracy"] == 1
