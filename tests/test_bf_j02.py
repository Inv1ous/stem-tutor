from __future__ import annotations

import ast
import json
import random
from datetime import datetime
from pathlib import Path

import pytest

from fixtures import make_vault
from tutorlib import grade, packs, session, store


def _published(spec: str, chapter: str, item_id: str, seed: int = 0) -> dict:
    path = Path(__file__).resolve().parents[1] / "build/out/packs" / spec / f"{chapter}.json"
    item = next(i for i in json.loads(path.read_text())["items"] if i["id"] == item_id)
    return packs.instantiate(item, random.Random(seed))


@pytest.mark.parametrize("text,score", [
    ("v=u^2+2as", 0), ("z=u^2+2as", 0), ("v^3=u^2+2as", 0),
    ("v^2=u^2+2as", 1), ("v²=2as+u²", 1), ("u^2+2as", 1), ("v^2=u^2-2as", 0),
])
def test_the_suvat_derivation_requires_the_requested_subject(text, score):
    """B-059: the correct right side cannot excuse a wrong equation subject."""
    item = _published("9702", "9702-2.1", "9702-2.1-i24")
    result = grade.grade_item(item, {"kind": "value", "value": text})
    assert result["score"] == score
    assert result["correct"] is bool(score)


def test_rebuilding_the_kinematics_pack_keeps_the_suvat_subject():
    """B-059: the pack is generated, so a key fixed only in the JSON comes back on the next rebuild."""
    root = Path(__file__).resolve().parents[1]
    source = ast.parse((root / "build/work/gen/gen_9702_2_1.py").read_text())
    calls = [n for n in ast.walk(source) if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "gen"
             and n.args and getattr(n.args[0], "value", None) == 24]
    assert len(calls) == 1
    answer = ast.literal_eval(next(k.value for k in calls[0].keywords if k.arg == "answer"))

    item = _published("9702", "9702-2.1", "9702-2.1-i24")
    assert answer["expr"] == item["answer"]["expr"]
    item["answer"] = answer
    assert grade.grade_item(item, {"kind": "value", "value": "v=u^2+2as"})["score"] == 0
    assert grade.grade_item(item, {"kind": "value", "value": "v^2=u^2+2as"})["score"] == 1


def test_an_equation_key_can_pass_content_validation(monkeypatch):
    """B-059: preserving the subject in a key must not prevent publishing it."""
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "build"))
    import validate_pack

    errors = []
    validate_pack._check_answer({"expr": "v^2 = u^2 + 2*a*s"}, "suvat", errors)
    assert errors == []
    validate_pack._check_answer({"expr": "v^2 ="}, "suvat", errors)
    assert errors and errors[0]["rule"] == "expression"


@pytest.mark.parametrize("text", ["7x+K", "7x+D", "7x+c", "7x+C"])
def test_another_integration_constant_earns_full_learning_credit(tmp_path, text):
    """B-102: a named arbitrary constant must not create an incorrect answer event."""
    item = _published("P1", "P1-5", "P1-5-i05")
    tutor = session.Tutor(store.Vault(make_vault(tmp_path)), rng=random.Random(0),
                          now=lambda: datetime.fromisoformat("2026-09-29T17:00:00+08:00"))
    tutor.start("autopilot", minutes=50)
    # Use the fixture's KC so the real event fold has its curriculum metadata.
    item["kcs"] = ["9702-2.1.4"]
    block = {"kind": "practice", "kcs": item["kcs"][:], "i": 0}
    tutor.session["blocks"][0] = block
    tutor._questions(block, 0, [item])
    n = next(iter(tutor.session["presented"]))
    result = tutor.answer(f"{n} = {text}")
    feedback = result["results"][0]
    assert feedback["correct"] and feedback["score"] == 1
    assert not feedback["needs_judgement"] and result["remaining"] == 0
    event = next(e for e in tutor.vault.events() if e["type"] == "answer")
    assert event["grade"]["correct"] and event["grade"]["score"] == 1


@pytest.mark.parametrize("text", ["7x", "7x+3", "8x+K", "7x+K*x", "7x+sin(K)"])
def test_a_constant_name_does_not_excuse_an_incomplete_or_wrong_integral(text):
    """B-102: renaming a constant cannot change the required family of answers."""
    item = _published("P1", "P1-5", "P1-5-i05")
    assert grade.grade_item(item, {"kind": "value", "value": text})["score"] == 0


def test_named_physical_quantities_are_not_arbitrary_integration_constants():
    """B-102: capacitance C must not be interchangeable with an unrelated K."""
    item = {"kind": "expression", "stem": "Write the charge in terms of C and V.",
            "answer": {"expr": "C*V"}}
    assert not grade.grade_item(item, {"kind": "value", "value": "K*V"})["correct"]


@pytest.mark.parametrize("spec,chapter,item_id,seed,text", [
    ("9701", "9701-2.1", "9701-2.1-i13", 0, "100.1"),
    ("9702", "9702-10.2", "9702-10.2-i25", 0, "2.571428571 A"),
    ("9702", "9702-5.2", "9702-5.2-i09", 0, "73.575 J"),
    ("9702", "9702-2.1", "9702-2.1-i13", 25, "11.33 m/s"),
])
def test_correct_science_calculations_keep_credit_at_extra_precision(spec, chapter, item_id, seed, text):
    """B-131: extra calculator figures are accepted unless precision is prescribed."""
    result = grade.grade_item(_published(spec, chapter, item_id, seed), {"kind": "value", "value": text})
    assert result["correct"] and result["score"] == 1 and result["error"] is None


@pytest.mark.parametrize("stem,allowed,text,score", [
    ("Calculate the energy.", [2, 3], "73.575", 0.5),
    ("Calculate the energy.", [2, 3], "73.575 m", 0),
    ("Calculate the energy.", [2, 3], "7e1 J", 0),
    ("Calculate the energy to 3 significant figures.", [3], "73.575 J", 0.5),
    ("Read the instrument's energy display.", [3], "73.575 J", 0.5),
])
def test_extra_precision_does_not_remove_units_or_prescribed_precision(stem, allowed, text, score):
    """B-131: units, insufficient precision and measurement exceptions still count."""
    item = {"kind": "numeric", "stem": stem, "kcs": ["9702-5.2.2"],
            "answer": {"value": 73.575, "unit": "J", "sf_ok": allowed}}
    assert grade.grade_item(item, {"kind": "value", "value": text})["score"] == score


def test_extra_figures_must_still_round_to_an_accepted_science_answer():
    """B-131: being within the old 1% tolerance does not make extra figures correct."""
    item = _published("9702", "9702-10.2", "9702-10.2-i25")
    # 18/7 rounds to 2.6 or 2.57; this rounds to 2.5 or 2.55.
    result = grade.grade_item(item, {"kind": "value", "value": "2.5499 A"})
    assert not result["correct"] and result["score"] == 0


def test_find_the_indefinite_integral_accepts_any_constant_letter():
    """B-102: Edexcel's usual wording, "the indefinite integral", names neither "integrate" nor ∫."""
    item = {"id": "x", "kind": "expression", "stem": "Find the indefinite integral of $2x$.", "answer": {"expr": "x**2 + C"},
            "kcs": ["P2-1.1"]}
    assert grade.grade_item(item, {"kind": "value", "value": "x^2 + k"})["score"] == 1
    assert grade.grade_item(item, {"kind": "value", "value": "x^2 + k*x"})["score"] == 0
