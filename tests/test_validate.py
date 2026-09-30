import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "build"))
import validate_pack as V  # noqa: E402
from fixtures import GRAPH, PACK  # noqa: E402


def good_pack():
    p = copy.deepcopy(PACK)
    # top up to the retrieval minimum: templates count 3, fixed items 1
    for kc in ("9702-2.1.1", "9702-2.1.4"):
        for i in range(6):
            p["items"].append({"id": f"9702-2.1-x{kc[-1]}{i}", "kcs": [kc], "kind": "mcq", "difficulty": 2,
                               "command_word": "State", "source": {"type": "generated"}, "stem": f"Pick B ({kc} {i}).",
                               "options": {"A": "a", "B": "b", "C": "c", "D": "d"}, "answer": "B",
                               "distractors": {"A": "m1"}, "marks": 1, "explanation": "B.",
                               "hints": ["h1", "h2", "h3"]})
    for it in p["items"]:
        it.setdefault("hints", ["h1", "h2", "h3"])
        it.setdefault("explanation", "because")
    return p


def errs(pack, **kw):
    return [e["rule"] for e in V.validate(pack, GRAPH, **kw)]


def test_good_pack_passes():
    assert errs(good_pack()) == []


def test_unknown_kc_rejected():
    p = good_pack()
    p["items"][0]["kcs"] = ["9702-9.9.9"]
    assert "unknown-kc" in errs(p)


def test_duplicate_item_id_rejected():
    p = good_pack()
    p["items"][1]["id"] = p["items"][0]["id"]
    assert "duplicate-id" in errs(p)


def test_mcq_answer_must_be_an_option_and_not_a_distractor():
    p = good_pack()
    p["items"][0]["answer"] = "E"
    assert "mcq-answer" in errs(p)
    p = good_pack()
    p["items"][0]["distractors"] = {"B": "m1"}
    assert "mcq-distractor" in errs(p)


def test_unknown_misconception_rejected():
    p = good_pack()
    p["items"][0]["distractors"] = {"A": "m99"}
    assert "unknown-misconception" in errs(p)


def test_template_answer_equal_to_distractor_rejected():
    p = good_pack()
    t = next(i for i in p["items"] if i.get("template"))
    t["template"]["distractors"] = [{"expr": "0.5*9.81*t**2", "misconception": "m2"}]
    assert "distractor-equals-answer" in errs(p)


def test_wrong_constant_for_spec_rejected():
    p = good_pack()
    t = next(i for i in p["items"] if i.get("template"))
    t["template"]["answer"] = "0.5*9.8*t**2"
    assert "constant" in errs(p)


def test_numeric_needs_parsable_unit_and_sig_figs():
    p = good_pack()
    fixed = next(i for i in p["items"] if i["id"] == "9702-2.1-i03")
    fixed["answer"]["unit"] = "furlongs"
    assert "unit" in errs(p)


def test_retrieval_minimum_per_kc():
    p = copy.deepcopy(PACK)
    for it in p["items"]:
        it["hints"], it["explanation"] = ["a", "b", "c"], "x"
    assert "too-few-items" in errs(p)


def test_generated_items_need_three_hints():
    p = good_pack()
    p["items"][0]["hints"] = ["only one"]
    assert "hints" in errs(p)


def test_markdown_fields_are_linted():
    p = good_pack()
    p["outline"] = "Uniform acceleration \\(v=u+at\\)"
    assert "lint" in errs(p)


def test_expression_answer_must_parse():
    p = good_pack()
    p["items"].append({"id": "9702-2.1-e1", "kcs": ["9702-2.1.4"], "kind": "expression", "difficulty": 3,
                       "command_word": "Find", "source": {"type": "generated"}, "stem": "Differentiate.",
                       "answer": {"expr": "2*x*("}, "marks": 2, "explanation": "x", "hints": ["a", "b", "c"]})
    assert "expression" in errs(p)


def test_structured_scheme_required():
    p = good_pack()
    s = next(i for i in p["items"] if i["kind"] == "structured")
    s["scheme"] = []
    assert "scheme" in errs(p)


def test_worked_step_check_verified():
    p = good_pack()
    p["worked"][0]["steps"][2]["check"]["answer"]["unit"] = "zz"
    assert "unit" in errs(p)


def test_hint_that_states_the_mcq_answer_is_flagged():
    p = good_pack()
    it = p["items"][0]  # answer B: "displacement"
    it["hints"] = ["Think about direction.", "Vectors have magnitude and direction.", "So the answer is displacement."]
    assert "hint-leak" in errs(p)


def test_hint_that_states_the_numeric_answer_is_flagged():
    p = good_pack()
    fixed = next(i for i in p["items"] if i["id"] == "9702-2.1-i03")  # 4.0 m s-2
    fixed["hints"] = ["Use v^2 = u^2 + 2as.", "Rearrange for a.", "You should get a deceleration of 4.0 m s^-2."]
    fixed["explanation"] = "x"
    assert "hint-leak" in errs(p)


def test_hints_that_share_words_with_every_option_are_fine():
    p = good_pack()
    p["items"][0]["hints"] = ["distance or displacement?", "which one has direction?", "speed and time have no direction"]
    assert "hint-leak" not in errs(p)


def test_the_same_question_twice_is_rejected():
    p = good_pack()
    twin = copy.deepcopy(next(i for i in p["items"] if i["kind"] == "mcq" and "template" not in i))
    twin["id"], twin["source"] = "9702-2.1-x99", {"type": "past", "ref": "CAIE 9702 · Nov 2025 · P13 · Q1"}
    p["items"].append(twin)
    assert "duplicate-question" in errs(p)
