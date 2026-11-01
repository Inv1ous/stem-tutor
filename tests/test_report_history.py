"""Reports retain the actual question shown, including shuffled choice letters."""
import copy
import random
from datetime import datetime

import pytest

from fixtures import make_vault
from tutorlib import report, session, store

T0 = datetime.fromisoformat("2026-09-29T17:00:00+08:00")


def _answered_question(tmp_path):
    tutor = session.Tutor(store.Vault(make_vault(tmp_path)), rng=random.Random(0), now=lambda: T0)
    pack = tutor.packs.pack("9702-2.1")
    pack["items"][:] = [pack["items"][0]]
    published = copy.deepcopy(pack["items"][0])
    tutor.start("test", minutes=10, focus=["9702-2.1.1"])
    question = tutor.next()["items"][0]
    assert question["options"] != published["options"]  # deterministic actual shuffle
    wrong = next(k for k, v in question["options"].items() if v == "distance")
    tutor.answer(f"{question['n']}{wrong}4")
    summary = tutor.end()
    event = next(e for e in tutor.vault.events() if e["type"] == "answer")
    assert event["question"]["options"] == question["options"]
    return tutor, published, event, summary


def _event_bytes(tutor):
    return {p.name: p.read_bytes() for p in (tutor.vault.tutor / "events").glob("*.jsonl")}


@pytest.mark.parametrize("pack_state", ["unchanged", "revised", "removed"])
def test_mistake_journal_uses_the_presented_question(tmp_path, pack_state):
    tutor, published, event, _ = _answered_question(tmp_path)
    items = tutor.packs.pack("9702-2.1")["items"]
    if pack_state == "revised":
        items[0]["stem"] = "A later revision asks a different question."
        items[0]["options"] = {"A": "new choice", "B": "another choice"}
    elif pack_state == "removed":
        items.clear()
    before = _event_bytes(tutor)

    text = (tutor.vault.root / report.mistakes_note(tutor)).read_text()

    assert f"Question: {published['stem']}" in text
    for letter, value in event["question"]["options"].items():
        assert f"  > **{letter}** {value}" in text
    assert f"You: `{event['response']}` · Right answer: {event['key']}" in text
    assert "later revision" not in text and "new choice" not in text
    assert _event_bytes(tutor) == before


def test_regraded_session_note_keeps_the_recorded_question_when_pack_is_removed(tmp_path):
    tutor, published, event, summary = _answered_question(tmp_path)
    assert tutor.regrade(event["id"], "The answer is accepted on review.")["ok"]
    tutor.packs.pack("9702-2.1")["items"].clear()
    before = _event_bytes(tutor)

    text = (tutor.vault.root / report.session_note(tutor, summary["session"])).read_text()

    assert published["stem"] in text
    assert "accuracy: 1.0" in text and "> [!success]" in text
    assert _event_bytes(tutor) == before
