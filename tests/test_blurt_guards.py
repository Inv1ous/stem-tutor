"""Blurt feedback must respect unresolved skipped-question guards."""
import json
import random

import pytest

from fixtures import make_vault
from test_session import T0
from tutorlib import session, store


SECRET_NOTE = "Displacement is the vector quantity."
KC = "9702-2.1.1"
SUBTOPIC = "9702-2.1"


def new_tutor(tmp_path):
    root = make_vault(tmp_path)
    source = root / ".tutor/packs/v1/specs/9702/packs/9702-2.1.json"
    pack = json.loads(source.read_text())
    pack["items"] = [pack["items"][0]]
    pack["items"][0]["shuffle"] = False
    pack["teach"] = {KC: {"motivate": "Compare scalar and vector quantities.",
                           "establish": SECRET_NOTE, "connect": "Use direction to distinguish them.",
                           "note": SECRET_NOTE, "self_explain": "Explain the distinction."}}
    source.write_text(json.dumps(pack))
    return session.Tutor(store.Vault(root), rng=random.Random(0), now=lambda: T0)


def skipped_tutor(tmp_path):
    tutor = new_tutor(tmp_path)
    tutor.start("lesson", focus=[KC])
    assert tutor.next()["activity"] == "choose"
    tutor.respond({"choice": "gaps"})
    question = tutor.next()["items"][0]
    feedback = tutor.answer(f"{question['n']}?")["results"][0]
    assert feedback["answer_withheld"]
    assert tutor.marking_guards()
    return tutor


def vault_bytes(tutor):
    return {p.relative_to(tutor.vault.root): p.read_bytes()
            for p in tutor.vault.root.rglob("*") if p.is_file()}


@pytest.mark.parametrize("stage", ["live", "ended", "restarted"])
def test_blurt_refuses_guarded_feedback_without_writing_any_output(tmp_path, stage):
    tutor = skipped_tutor(tmp_path)
    if stage != "live":
        assert "error" not in tutor.end(abandoned=True)
    if stage == "restarted":
        tutor = session.Tutor(tutor.vault, now=lambda: T0)
    before = vault_bytes(tutor)
    guards = tutor.marking_guards()

    result = tutor.blurt(SUBTOPIC, "I recall nothing yet.")

    assert SECRET_NOTE not in str(result)
    assert result.get("ok") is False
    assert "protected" in result["error"]
    assert "cards" not in result and "log" not in result
    assert tutor.marking_guards() == guards
    assert vault_bytes(tutor) == before


def test_blurt_feedback_remains_available_without_a_guard(tmp_path):
    tutor = new_tutor(tmp_path)
    result = tutor.blurt(SUBTOPIC, "I recall nothing yet.")
    assert SECRET_NOTE in str(result["cards"])
    assert SECRET_NOTE in (tutor.vault.root / result["log"]).read_text()
    assert SECRET_NOTE in (tutor.vault.root / "Now.md").read_text()
    assert not tutor.marking_guards()


def test_attempting_the_skipped_question_releases_blurt_feedback(tmp_path):
    tutor = skipped_tutor(tmp_path)
    tutor.end(abandoned=True)
    tutor = session.Tutor(tutor.vault, now=lambda: T0)
    tutor.start("lesson", focus=[KC])
    retry = tutor.retry_skipped()["items"][0]
    tutor.answer(f"{retry['n']}B3")
    assert not tutor.marking_guards()
    events = {p: p.read_bytes() for p in (tutor.vault.tutor / "events").glob("*.jsonl")}

    result = tutor.blurt(SUBTOPIC, "I recall nothing yet.")

    assert SECRET_NOTE in str(result["cards"])
    assert all(p.read_bytes().startswith(data) for p, data in events.items())
    assert tutor.state == tutor._fold()


@pytest.mark.parametrize("stage", ["live", "restarted"])
def test_blurt_respects_existing_no_help_policy_without_marking_assistance(tmp_path, stage):
    tutor = new_tutor(tmp_path)
    tutor.start("test", focus=[KC])
    question = tutor.next()["items"][0]
    assert question["unassisted"] and not tutor.marking_guards()
    if stage == "restarted":
        tutor = session.Tutor(tutor.vault, now=lambda: T0)
    before = vault_bytes(tutor)
    assert tutor.ai_help(given=False).get("refused")

    result = tutor.blurt(SUBTOPIC, "I recall nothing yet.")

    assert SECRET_NOTE not in str(result)
    assert result.get("ok") is False and "no-help" in result["error"]
    assert tutor.session["presented"][str(question["n"])]["hinted"] is False
    assert vault_bytes(tutor) == before


def test_allowed_active_learning_activity_does_not_block_blurt(tmp_path):
    tutor = new_tutor(tmp_path)
    tutor.start("learn", focus=[KC])
    question = tutor.next()["items"][0]
    assert not question["unassisted"] and tutor.ai_help(given=False) == {"ok": True}
    result = tutor.blurt(SUBTOPIC, "I recall nothing yet.")
    assert SECRET_NOTE in str(result["cards"])
