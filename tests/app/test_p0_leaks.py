"""Bug-watch P0 findings on the AI tutor's answer-leak guard (the answer is never given before the learner tries)."""
import random

import pytest

from library_assets import read_json
from tutor_app.ai import leaks
from tutorlib import packs, session

def published(spec, chapter, item_id, seed=0):
    item = next(i for i in read_json(f"build/out/packs/{spec}/{chapter}.json")["items"]
                if i["id"] == item_id)
    return packs.instantiate(item, random.Random(seed))


@pytest.mark.parametrize("reply,leak", [("The y-intercept is 1.", True), ("so the intercept is just 1", True),
                                        ("Substitute x = 0 first.", False), ("Try 1 more step.", False)])
def test_a_short_correct_option_given_as_the_answer_is_held_back(reply, leak):
    """B-072: options of six characters or fewer were never checked."""
    key = session._display_answer(published("P2", "P2-5", "P2-5-i01"))
    assert leaks(reply, key, "mcq") is leak


@pytest.mark.parametrize("reply,key", [
    ("6", "B: 6"),
    ("**6**", "B: 6"),
    ("$6$", "B: 6"),
    ("`6`", "B: 6"),
    ("6.", "B: 6"),
    ("**6**.", "B: 6"),
    ("$6$.", "B: 6"),
    ("NO₂", "D: NO₂"),
    ("6 N", "A: 6 N"),
    ("b", "B: displacement"),
    ("(b)", "B: displacement"),
])
def test_a_bare_short_correct_option_is_held_back(reply, key):
    assert leaks(reply, key, "mcq")


@pytest.mark.parametrize("reply,key", [
    ("Try 6 more steps", "B: 6"),
    ("Use 6 N in the calculation", "A: 6 N"),
    ("-6", "B: 6"),
    ("6", "B: 6!"),
])
def test_short_options_are_not_leaked_by_mentions_or_sign_changes(reply, key):
    assert not leaks(reply, key, "mcq")


@pytest.mark.parametrize("reply,leak", [("The answer is b.", True), ("option b is correct", True), ("b is correct", True),
                                        ("It is a vector.", False)])
def test_a_lowercase_option_letter_is_still_the_option(reply, leak):
    assert leaks(reply, "B: displacement", "mcq") is leak


def test_a_short_answer_given_word_for_word_is_held_back():
    model = "Wave motion is propagation of a disturbance through a medium or space, transferring energy."
    assert leaks(f"Here it is: {model}", model, "short") and not leaks("Think about energy.", model, "short")


@pytest.mark.parametrize("reply,key", [("energy", "energy"), ("**energy**", "energy")])
def test_an_exact_short_answer_is_held_back(reply, key):
    assert leaks(reply, key, "short")


def test_a_short_answer_mentioned_in_context_is_not_held_back():
    assert not leaks("Think about energy.", "energy", "short")


@pytest.mark.parametrize("reply,key", [("π", "π"), ("x", "x"), ("$x$", "x"),
                                        ("x²", "x**2"), ("1 - x", "1-x"),
                                        ("1−x", "1-x"), ("1–x", "1-x")])
def test_an_exact_expression_answer_is_held_back(reply, key):
    assert leaks(reply, key, "expression")


@pytest.mark.parametrize("reply,key,kind", [
    ("NO_2", "C: NO₂", "mcq"),
    (r"$\mathrm{NO_2}$", "C: NO₂", "mcq"),
    (r"$\mathrm{NO_2}$", "NO₂", "short"),
    (r"\pi", "π", "expression"),
    (r"\theta", "θ", "expression"),
    (r"\frac{1}{2}", "1/2", "expression"),
    (r"$\frac{1}{2}$", "1/2", "expression"),
])
def test_equivalent_whole_answer_presentation_is_held_back(reply, key, kind):
    assert leaks(reply, key, kind)


@pytest.mark.parametrize("reply,key", [("Let x vary.", "x"), ("Use π in the formula.", "π"),
                                        ("x2", "x²"), ("-x", "x"), ("X", "x"),
                                        ("x!", "x"), ("6", "6!"),
                                        ("2/4", "1/2"),
                                        (r"$a/bc$", r"$a/(bc)$"),
                                        (r"$(a+b)/c$", r"$a+b/c$")])
def test_an_expression_mentioned_in_context_is_not_held_back(reply, key):
    assert not leaks(reply, key, "expression")


@pytest.mark.parametrize("reply,key,kind", [
    ("Use NO_2 in the equation.", "C: NO₂", "mcq"),
    (r"Try \frac{1}{2} next.", "1/2", "expression"),
    ("$\\frac{1}{3}$", "1/2", "expression"),
    ("$\\frac{1}{2}", "1/2", "expression"),
])
def test_rendered_answer_comparison_keeps_context_and_malformed_or_different_answers(reply, key, kind):
    assert not leaks(reply, key, kind)


def test_the_answer_in_another_unit_is_held_back():
    """B-074: 0.4 kN for a 400 N key passed the guard, though the marking gives it full marks."""
    item = published("9702", "9702-5.1", "9702-5.1-r05")
    key, v = session._display_answer(item), item["answer"]["value"]
    assert leaks(f"The force is {v / 1000:g} kN.", key, "numeric", item["answer"])
    assert leaks(f"{v / 1000:g} kN of resistance", key, "numeric", item["answer"])
    assert not leaks("Use P = Fv with the 2.0 kW power.", key, "numeric", item["answer"])


def test_a_numbered_hint_step_is_not_mistaken_for_the_numeric_answer():
    answer = {"value": 1, "exact": True}
    assert not leaks("Step 1: draw a free-body diagram.", "1", "numeric", answer)
    assert leaks("Step 1: the result is 1.", "1", "numeric", answer)
    assert leaks("1", "1", "numeric", answer)
