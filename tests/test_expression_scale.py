"""Expression equivalence must retain its meaning when all terms are scaled."""
import json
from datetime import datetime

import pytest

from fixtures import make_vault
from tutorlib import grade, session, store


@pytest.mark.parametrize("given, expected", [
    ("0", "0.000000000001*x"),
    ("0.000000000002*x", "0.000000000001*x"),
    ("0.000000000001*(x+1)", "0.000000000001*x"),
    ("0", "0.000000000001"),
    ("0.000000000001", "0"),
])
def test_small_expression_errors_do_not_earn_full_credit(given, expected):
    result = grade.grade_item({"kind": "expression", "answer": {"expr": expected}},
                              {"kind": "value", "value": given})
    assert result["correct"] is False
    assert result["score"] == 0
    assert result["needs_judgement"] is True


@pytest.mark.parametrize("scale", ["1", "0.000000000001"])
@pytest.mark.parametrize("given, expected", [
    ("x+x", "2*x"),
    ("sin(x)^2+cos(x)^2", "1"),
    ("sin(x)^2+cos(x)^2-1", "0"),
    ("(x+1)^2-x^2-2*x-1", "0"),
])
def test_correct_identities_and_cancellation_survive_rescaling(scale, given, expected):
    result = grade.grade_item({"kind": "expression", "answer": {"expr": f"{scale}*({expected})"}},
                              {"kind": "value", "value": f"{scale}*({given})"})
    assert result["correct"] is True
    assert result["score"] == 1


@pytest.mark.parametrize("residual", ["1", "x", "100"])
def test_large_cancellation_cannot_hide_a_nonzero_residual(residual):
    given = f"1000000000000*(sin(x)^2+cos(x)^2-1)+{residual}"
    result = grade.grade_item({"kind": "expression", "answer": {"expr": "0"}},
                              {"kind": "value", "value": given})
    assert result["correct"] is False
    assert result["score"] == 0


@pytest.mark.parametrize("scale", ["1", "0.000000000001"])
@pytest.mark.parametrize("expression", [
    "(sin(x)^2+cos(x)^2-1)^2",
    "(sin(x)^2+cos(x)^2-1)^3",
    "abs(sin(x)^2+cos(x)^2-1)",
    "sin(sin(x)^2+cos(x)^2-1)",
])
def test_nonlinear_cancellation_keeps_its_existing_roundoff_room(scale, expression):
    result = grade.grade_item({"kind": "expression", "answer": {"expr": "0"}},
                              {"kind": "value", "value": f"{scale}*({expression})"})
    assert result["correct"] is True
    assert result["score"] == 1


@pytest.mark.parametrize("typed, correct", [("0", False), ("0.000000000001*(x+x)/2", True)])
def test_small_expression_public_answer_and_replay_keep_the_same_verdict(tmp_path, typed, correct):
    root = make_vault(tmp_path)
    source = root / ".tutor/packs/v1/specs/9702/packs/9702-2.1.json"
    pack = json.loads(source.read_text())
    pack["items"] = [{"id": "small-expression", "kind": "expression", "kcs": ["9702-2.1.1"],
                      "marks": 1, "difficulty": 3, "stem": "Express one trillionth of x.",
                      "answer": {"expr": "0.000000000001*x"}}]
    source.write_text(json.dumps(pack))
    original_source = source.read_bytes()
    now = lambda: datetime.fromisoformat("2026-09-29T17:00:00+08:00")
    tutor = session.Tutor(store.Vault(root), now=now)
    tutor.start("test", focus=["9702-2.1.1"])
    question = tutor.next()["items"][0]

    feedback = tutor.answer(f"{question['n']} = {typed} ~3")["results"][0]

    assert feedback["correct"] is correct
    assert feedback["score"] == (1 if correct else 0)
    answer = next(e for e in tutor.vault.events() if e.get("type") == "answer")
    assert answer["response"] == typed
    assert answer["grade"]["correct"] is correct
    events = {p: p.read_bytes() for p in (root / ".tutor/events").glob("*.jsonl")}
    restarted = session.Tutor(store.Vault(root), now=now)
    assert restarted.state == tutor.state == restarted._fold()
    assert bool(restarted.state["kcs"]["9702-2.1.1"]["succ_days"]) is correct
    assert source.read_bytes() == original_source
    assert all(p.read_bytes() == data for p, data in events.items())
