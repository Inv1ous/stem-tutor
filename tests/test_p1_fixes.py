"""The last P1 findings of the bug watch, fixed by hand: read-aloud (B-112, B-113, B-116, B-128) and content
(B-090, B-129)."""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

from tutorlib import packs
from tutorlib.speech import for_tts

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "build"))
import content_checks  # noqa: E402


def test_subtraction_is_read_as_minus():
    """B-112: `131 - 53 = 78` was read "one hundred and thirty one fifty three equals seventy eight"."""
    assert "thirty one minus fifty three equals" in for_tts("131 - 53 = 78")


def test_a_typed_reaction_arrow_is_read_as_gives():
    """B-113: `->` was read "is greater than"."""
    said = for_tts("2CO + 2NO -> 2CO2 + N2")
    assert "gives" in said and "greater" not in said


def test_the_letter_a_is_said_as_a_letter_not_as_the_article():
    """B-116: "option A" and "point A" were said like the word "a"."""
    assert for_tts("Option A") == "Option ay."
    assert "ay" not in for_tts("A charge moves.")


def test_a_frequency_table_is_read_not_skipped():
    """B-128: read aloud dropped the table a statistics question needs."""
    said = for_tts("The table shows the data.\n\n| Score | 1 | 2 |\n|---|---|---|\n| Frequency | 8 | 12 |\n\nFind the median.")
    assert "Frequency" in said and "twelve" in said


def test_no_two_flashcards_of_a_pack_share_an_id():
    """B-090: the cell and resistor cards of 9702-10.1 were both `fc1`, so Anki saw one note with two faces."""
    bad = []
    for f in sorted((ROOT / "build/out/packs").glob("*/*.json")):
        pack = json.loads(f.read_text())
        if isinstance(pack, dict) and (found := content_checks.id_problems(pack)):
            bad.append((f.stem, found))
    assert not bad, bad
    assert content_checks.id_problems({"flashcards": [{"id": "fc1"}, {"id": "fc1"}]})


def test_a_shuffled_couple_question_explains_itself_whatever_the_letters():
    """B-129: the explanation named options A and B, which the shuffle re-letters."""
    pack = json.loads((ROOT / "build/out/packs/9702/9702-4.1.json").read_text())
    item = next(i for i in pack["items"] if i["id"] == "9702-4.1-i12")
    assert not content_checks.letter_refs(item["explanation"])
    shown = packs.instantiate(item, random.Random(0))
    assert "parallel forces on different lines" in shown["options"][shown["answer"]]
    assert content_checks.letter_refs("Only A has zero resultant force; B acts along one line.")
