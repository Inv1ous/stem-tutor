"""External judgement must not turn an explicit abstention into successful recall."""
import json
from datetime import timedelta

import pytest

from fixtures import make_vault
from test_session import Clock, T0
from tutorlib import session, store


KC = "9702-2.1.1"


def make_tutor(tmp_path, kind):
    root = make_vault(tmp_path)
    source = root / ".tutor/packs/v1/specs/9702/packs/9702-2.1.json"
    pack = json.loads(source.read_text())
    item = {"id": "judged-abstention", "kind": kind, "kcs": [KC], "difficulty": 3,
            "marks": 1, "stem": "Give the answer."}
    item.update({
        "mcq": {"options": {"A": "wrong", "B": "right"}, "answer": "B"},
        "numeric": {"answer": {"value": 4, "unit": "m"}},
        "expression": {"answer": {"expr": "x"}},
        "short": {"rubric": [{"point": "The required answer", "keywords": [["answer"]]}]},
        "structured": {"scheme": [{"mark": "B1", "point": "The required answer"}]},
    }[kind])
    pack["items"] = [item]
    source.write_text(json.dumps(pack))
    clock = Clock(T0)
    return session.Tutor(store.Vault(root), now=clock), clock, source


@pytest.mark.parametrize("kind, mode", [
    ("mcq", "test"), ("numeric", "test"), ("expression", "test"),
    ("short", "test"), ("structured", "long"), ("mcq", "review"), ("mcq", "lesson"),
])
def test_judged_abstention_retains_recall_gap_in_feedback_history_and_replay(tmp_path, kind, mode):
    tutor, clock, source = make_tutor(tmp_path, kind)
    source_bytes = source.read_bytes()
    if mode == "review":
        tutor.start("test", focus=[KC])
        first = tutor.next()["items"][0]
        tutor.answer(f"{first['n']}B3")
        tutor.end()
        clock.t += timedelta(days=100)
    tutor.start(mode, focus=[KC])
    if mode == "lesson":
        tutor.next()
        tutor.respond({"choice": "gaps"})
    question = tutor.next()["items"][0]
    prior_days = list(tutor.state["kcs"].get(KC, {}).get("succ_days", []))

    result = tutor.answer(f"{question['n']}?", judge={question["n"]: 1})["results"][0]

    assert result["correct"] is False and result["score"] == 0
    assert tutor.session["correct"] == 0
    answer = [e for e in tutor.vault.events() if e["type"] == "answer"][-1]
    assert answer["response"] == "don't know"
    assert answer["grade"]["correct"] is False and answer["grade"]["score"] == 0
    assert answer["grade"]["error"] == "RECALL"
    assert tutor.state["kcs"][KC]["succ_days"] == prior_days
    assert tutor.state["kcs"][KC]["last_rating"] == "again"
    if mode == "lesson":
        assert result["answer_withheld"] and tutor.marking_guards()
    events = {p: p.read_bytes() for p in (tutor.vault.tutor / "events").glob("*.jsonl")}
    restarted = session.Tutor(tutor.vault, now=clock)
    assert restarted.state == tutor.state == restarted._fold()
    assert source.read_bytes() == source_bytes
    assert all(p.read_bytes() == data for p, data in events.items())


def test_manual_judgement_of_an_actual_written_response_still_applies(tmp_path):
    tutor, _, _ = make_tutor(tmp_path, "short")
    tutor.start("test", focus=[KC])
    question = tutor.next()["items"][0]
    result = tutor.answer(f"{question['n']} = My written answer", judge={question["n"]: 0.5})["results"][0]
    assert result["score"] == 0.5
    answer = next(e for e in tutor.vault.events() if e["type"] == "answer")
    assert answer["response"] == "My written answer" and answer["grade"]["score"] == 0.5
