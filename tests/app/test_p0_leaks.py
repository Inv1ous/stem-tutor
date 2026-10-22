"""Bug-watch P0 findings on the AI tutor's answer-leak guard (the answer is never given before the learner tries)."""
import json
import random
from pathlib import Path

import pytest

from tutor_app.ai import leaks
from tutorlib import packs, session

REPO = Path(__file__).resolve().parents[2]


def published(spec, chapter, item_id, seed=0):
    item = next(i for i in json.loads((REPO / f"build/out/packs/{spec}/{chapter}.json").read_text())["items"]
                if i["id"] == item_id)
    return packs.instantiate(item, random.Random(seed))


@pytest.mark.parametrize("reply,leak", [("The y-intercept is 1.", True), ("so the intercept is just 1", True),
                                        ("Substitute x = 0 first.", False), ("Try 1 more step.", False)])
def test_a_short_correct_option_given_as_the_answer_is_held_back(reply, leak):
    """B-072: options of six characters or fewer were never checked."""
    key = session._display_answer(published("P2", "P2-5", "P2-5-i01"))
    assert leaks(reply, key, "mcq") is leak


@pytest.mark.parametrize("reply,leak", [("The answer is b.", True), ("option b is correct", True), ("b is correct", True),
                                        ("It is a vector.", False)])
def test_a_lowercase_option_letter_is_still_the_option(reply, leak):
    assert leaks(reply, "B: displacement", "mcq") is leak


def test_a_short_answer_given_word_for_word_is_held_back():
    model = "Wave motion is propagation of a disturbance through a medium or space, transferring energy."
    assert leaks(f"Here it is: {model}", model, "short") and not leaks("Think about energy.", model, "short")


def test_the_answer_in_another_unit_is_held_back():
    """B-074: 0.4 kN for a 400 N key passed the guard, though the marking gives it full marks."""
    item = published("9702", "9702-5.1", "9702-5.1-r05")
    key, v = session._display_answer(item), item["answer"]["value"]
    assert leaks(f"The force is {v / 1000:g} kN.", key, "numeric", item["answer"])
    assert leaks(f"{v / 1000:g} kN of resistance", key, "numeric", item["answer"])
    assert not leaks("Use P = Fv with the 2.0 kW power.", key, "numeric", item["answer"])
