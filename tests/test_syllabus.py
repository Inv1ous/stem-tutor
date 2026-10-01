import sys
from pathlib import Path

from fixtures import GRAPH

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "build"))
import syllabus  # noqa: E402
from test_validate import good_pack  # noqa: E402

NOTE = ("Displacement is a vector and distance is a scalar; velocity is the rate of change of displacement. "
        "For uniform acceleration use the suvat equations, for example $v = u + at$.")
CARD = {"motivate": "Why.", "establish": "The idea.", "connect": "Builds on.", "note": "- a\n- b", "self_explain": "Say it."}
WORDS = {"State", "Calculate", "Deduce"}


def full_pack():
    pack = good_pack()
    pack["teach"] = {"9702-2.1.1": dict(CARD), "9702-2.1.4": dict(CARD)}
    return pack


def rules(problems):
    return sorted((p["rule"], p["where"]) for p in problems)


def test_a_chapter_that_follows_its_syllabus_passes():
    assert syllabus.check(full_pack(), GRAPH, NOTE, WORDS) == []


def test_every_gap_against_the_syllabus_is_named():
    pack = full_pack()
    del pack["teach"]["9702-2.1.4"]  # an outcome with no teaching card
    pack["flashcards"], pack["worked"] = [], []  # "define …" with no definition, "derive …" with no derivation
    assert rules(syllabus.check(pack, GRAPH, "Nothing about this topic.", {"State", "Calculate"})) == [
        ("command-word", "item 9702-2.1-i04"),  # "Deduce" is not a command word of this syllabus
        ("define-not-covered", "9702-2.1.1"), ("derive-not-covered", "9702-2.1.4"), ("no-teach-card", "9702-2.1.4"),
        ("note-misses-outcome", "9702-2.1.1"), ("note-misses-outcome", "9702-2.1.4")]


def test_past_paper_wording_is_not_checked_for_command_words():
    pack = full_pack()
    next(i for i in pack["items"] if i["id"] == "9702-2.1-i03")["command_word"] = "Deduce"  # a past-paper question
    assert [p for p in syllabus.check(pack, GRAPH, NOTE, {"State", "Calculate"}) if p["where"].endswith("i03")] == []


def test_command_words_come_from_the_bundle():
    bundle = "# Bundle\n\n## Command words\n\n- **Calculate**: work out\n- **Show (that)**: give evidence\n\n## Constants\n"
    assert syllabus.command_words(bundle) == {"Calculate", "Show (that)"}
    assert syllabus.command_words("# A bundle with no such section\n") is None


def test_audit_finds_outcomes_that_differ_from_the_syllabus():
    official = {"9702-2.1.1": GRAPH["kcs"][0]["statement"], "9702-2.1.9": "an outcome the graph dropped"}
    assert rules(syllabus.audit(official, GRAPH)) == [("missing-outcome", "9702-2.1.9"), ("not-in-syllabus", "9702-2.1.4")]
    official = {k["id"]: k["statement"] for k in GRAPH["kcs"]}
    assert syllabus.audit(official, GRAPH) == []
    official["9702-2.1.4"] = GRAPH["kcs"][1]["statement"] + (
        " (When performing calculations, candidates' answers should reflect the number of significant figures given or "
        "asked for in the question.)")
    assert rules(syllabus.audit(official, GRAPH)) == [("wording-lost", "9702-2.1.4")]  # a syllabus note was dropped


def test_audit_finds_a_subtopic_listed_twice():
    graph = {**GRAPH, "subtopics": GRAPH["subtopics"] + [{"id": "9702-2.1", "title": "A glossary heading", "topic": "9702-2"}]}
    official = {k["id"]: k["statement"] for k in GRAPH["kcs"]}
    assert rules(syllabus.audit(official, graph)) == [("duplicate-subtopic", "9702-2.1")]


def test_audit_accepts_tidied_wording():
    graph = {"kcs": [{"id": "9702-5.2.4", "statement": r"recall and use $E_K = \frac{1}{2}mv^2$"}]}
    assert syllabus.audit({"9702-5.2.4": "recall and use EK = 2 1 mv2"}, graph) == []  # as the PDF extraction reads it


def test_show_that_counts_as_the_listed_command_word_and_maths_has_no_list():
    pack = full_pack()
    next(i for i in pack["items"] if i["id"] == "9702-2.1-i04")["command_word"] = "Show that"
    assert syllabus.check(pack, GRAPH, NOTE, {"State", "Calculate", "Show (that)"}) == []
    pack["items"][0]["command_word"] = "Find"
    assert syllabus.check(pack, {**GRAPH, "spec": "P1"}, NOTE, {"State"}) == []  # Edexcel defines no command words
