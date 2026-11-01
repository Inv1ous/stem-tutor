"""Ask-mode references use published facts without crossing practice-answer boundaries."""
import json
import re
from types import SimpleNamespace

import pytest

from tutor_app import prompts
from tutorlib.packs import Packs
from tutorlib.store import Vault


def point(kc, title, statement, glossary, guidance=None):
    row = {"id": kc, "subtopic": kc.rsplit(".", 1)[0], "title": title, "statement": statement,
           "glossary": glossary, "level": "AS", "type": "conceptual", "prereqs": []}
    if guidance:
        row["guidance"] = guidance
    return row


@pytest.fixture
def tutor(tmp_path):
    graphs = {
        "9701": ("chem", [
            point("9701-3.4.1", "Covalent bonding", "A covalent bond is the electrostatic attraction between two nuclei and a shared pair of electrons.", ["covalent bond", "shared pair"]),
            point("9701-3.2.1", "Ionic bonding", "An ionic bond is electrostatic attraction between oppositely charged ions.", ["ionic bond", "oppositely charged ions"]),
            point("9701-3.3.1", "Metallic bonding", "Metallic bonding is attraction between positive ions and delocalised electrons.", ["metallic bonding", "delocalised electrons"]),
            point("9701-5.1.1", "Bond energy", "Bond energy concerns gaseous covalent bonds.", ["bond energy"]),
            point("9701-13.1.1", "Organic formulae", "Use molecular and structural formulae for organic compounds.", ["organic formulae"]),
        ]),
        "9702": ("phys", [
            point("9702-6.1.1", "Energy", "Energy is conserved.", ["energy"]),
            point("9702-9.1.1", "Bond energy", "A toy physics reference used to detect subject ambiguity.", ["bond energy"]),
            point("9702-2.1.1", "Velocity", "Velocity is rate of change of displacement.", ["velocity"]),
            point("9702-4.1.1", "Momentum", "Momentum is the product of mass and velocity.", ["momentum"]),
            point("9702-7.1.1", "Pressure", "Pressure is force per unit area.", ["pressure"]),
        ]),
        "P1": ("math", [point("P1-1.1", "Laws of indices", "Use laws of indices with rational exponents.", ["laws of indices", "fractional indices"], r"$a^m a^n = a^{m+n}$ for $a > 0$.")]),
        "M1": ("math", [point("M1-1.1", "Particle models", "A particle has negligible size.", ["particle model"])]),
    }
    root = tmp_path / "vault"
    published = root / ".tutor/packs/v17"
    published.mkdir(parents=True)
    (published.parent / "CURRENT").write_text("v17")
    (published / "manifest.json").write_text(json.dumps({"version": "v17", "specs": list(graphs)}))
    for spec, (subject, rows) in graphs.items():
        base = published / "specs" / spec
        (base / "packs").mkdir(parents=True)
        subtopics = [{"id": row["subtopic"], "title": row["title"], "topic": spec} for row in rows]
        graph = {"spec": spec, "subject": subject, "version": "2025-2027", "topics": [], "subtopics": subtopics, "kcs": rows}
        (base / "graph.json").write_text(json.dumps(graph))
        for row in rows:
            kc = row["id"]
            pack = {"spec": spec, "subtopic": row["subtopic"], "outline": "OUTLINE_SECRET",
                    "flashcards": [{"id": "fc1", "kc": kc, "front": f"Define {row['title']}.", "back": "PUBLIC_FLASHCARD " + row["statement"]},
                                  {"id": "fc2", "kc": "unrelated", "front": row["title"], "back": "UNRELATED_FLASHCARD_SECRET"}],
                    "misconceptions": [{"id": "mis1", "kc": kc, "statement": row["title"] + " is always weak.", "refutation": "PUBLIC_REFUTATION " + row["statement"]}],
                    "items": [{"kcs": [kc], "answer": "ITEM_ANSWER_SECRET", "solution": "ITEM_SOLUTION_SECRET", "explanation": "ITEM_EXPLANATION_SECRET"}],
                    "worked": [{"kc": kc, "steps": [{"do": "WORKED_STEP_SECRET"}]}],
                    "ai_cards": {kc: {"establish": "AI_CARD_SECRET"}}}
            (base / "packs" / f"{row['subtopic']}.json").write_text(json.dumps(pack))
    vault = Vault(root)
    return SimpleNamespace(packs=Packs(vault), vault=vault, session={"mode": "long", "subtopic": "9702-2.1", "recent": []})


def packet(tutor, question, kc=None):
    result = prompts.ask(tutor, question, kc)
    before_request = result.removesuffix(f"\n\nSTUDENT ASKS: {question}")
    return before_request.removeprefix(prompts.context(tutor, kc)).strip()


def test_precise_bonding_excerpts_include_provenance_and_only_public_sources(tutor):
    text = packet(tutor, "Define covalent bonding for chemistry 9701.")
    assert "STUDY REFERENCES" in text
    assert "not an official mark scheme" in text
    assert "9701-3.4.1" in text and "v17" in text
    assert "two nuclei and a shared pair of electrons" in text
    assert "PUBLIC_FLASHCARD" in text and "PUBLIC_REFUTATION" in text
    assert "9702-" not in text and "9701-3.2.1" not in text
    for forbidden in ["ITEM_ANSWER_SECRET", "ITEM_SOLUTION_SECRET", "ITEM_EXPLANATION_SECRET", "WORKED_STEP_SECRET", "AI_CARD_SECRET", "UNRELATED_FLASHCARD_SECRET", "OUTLINE_SECRET"]:
        assert forbidden not in text


@pytest.mark.parametrize("question,want,absent", [
    ("9701: define bond energy", "9701-5.1.1", "9702-9.1.1"),
    ("In chemistry define bond energy", "9701-5.1.1", "9702-9.1.1"),
    ("9702: define bond energy", "9702-9.1.1", "9701-5.1.1"),
    ("P1 laws of indices", "P1-1.1", "M1-1.1"),
    ("Maths: fractional indices", "P1-1.1", "9702-"),
])
def test_explicit_current_scope_overrides_stale_session(tutor, question, want, absent):
    text = packet(tutor, question)
    assert want in text and absent not in text


@pytest.mark.parametrize("question", ["Please explain the formula", "What is this?", "Help me study", "Define bond energy"])
def test_weak_or_cross_subject_ambiguous_request_omits_references(tutor, question):
    tutor.session = {"recent": []}
    assert packet(tutor, question) == ""


def test_phrase_normalisation_preserves_maths_and_guidance(tutor):
    text = packet(tutor, "P1: explain LÁWS—OF—INDICES")
    assert "P1-1.1" in text
    assert r"$a^m a^n = a^{m+n}$ for $a > 0$." in text


def test_multi_part_query_covers_each_requested_bonding_concept(tutor):
    text = packet(tutor, "9701: compare covalent, ionic and metallic bonding")
    assert all(kc in text for kc in ["9701-3.4.1", "9701-3.2.1", "9701-3.3.1"])


def test_output_is_stably_ordered_and_bounded_without_slicing_formulae(tutor):
    for index in range(20):
        kc = f"9701-3.4.{index + 10}"
        tutor.packs.kcs[kc] = {**tutor.packs.kcs["9701-3.4.1"], "id": kc,
                                "statement": "covalent bonding " + r"$x^{12345} + y^{67890}$ " * 1000}
    text = packet(tutor, "9701: covalent bonding")
    assert "9701-3.4.1" in text
    assert len(text) <= 6000
    assert len(set(re.findall(r"9701-3\.4\.\d+", text))) <= 6
    assert "$x^{12345}" not in text  # omit an oversized complete field, never cut a formula
    tutor.packs.kcs = dict(reversed(list(tutor.packs.kcs.items())))
    assert packet(tutor, "9701: covalent bonding") == text


def test_open_question_disables_broad_references_and_preserves_existing_context(tutor):
    tutor.session["presented"] = {"1": {"inst": {"stem": "Define covalent bonding.", "kind": "text", "answer": "two nuclei and a shared pair of electrons"}}}
    question = "9701 chemistry: define covalent bonding.\nKeep $a_b^2$, ‘quotes’ and 50% exactly."
    old_context = prompts.context(tutor)
    assert prompts.ask(tutor, question, None) == f"{old_context}\n\nSTUDENT ASKS: {question}"
    assert "two nuclei and a shared pair" not in old_context


def test_references_precede_request_and_leave_context_and_request_exact(tutor):
    question = "9701: covalent bonding\n$C_2H_6$ and literal \\n."
    result = prompts.ask(tutor, question, None)
    assert result.startswith(prompts.context(tutor) + "\n\nSTUDY REFERENCES")
    assert result.endswith("\n\nSTUDENT ASKS: " + question)


@pytest.mark.parametrize("damage", ["missing", "json", "shape"])
def test_unpublished_or_damaged_chapters_keep_graph_without_pack_facts(tutor, damage):
    path = tutor.packs.root / "specs/9701/packs/9701-3.4.json"
    if damage == "missing":
        path.unlink()
    elif damage == "json":
        path.write_text("{cut off")
    else:
        path.write_text(json.dumps({"flashcards": [None, "bad"], "misconceptions": "bad"}))
    text = packet(tutor, "9701: covalent bonding")
    assert "9701-3.4.1" in text and "two nuclei" in text
    assert "PUBLIC_FLASHCARD" not in text and "PUBLIC_REFUTATION" not in text


def test_missing_packs_object_is_ordinary_ask_flow(tutor):
    tutor.packs = SimpleNamespace(kcs={}, subtopics={})
    assert packet(tutor, "9701: covalent bonding") == ""


def test_explicit_point_or_chapter_identifier_can_supply_its_public_facts(tutor):
    text = packet(tutor, "Explain 9701-3.4.1")
    assert "9701-3.4.1" in text and "two nuclei" in text
    assert "PUBLIC_FLASHCARD" in text
    assert "9701-3.2.1" not in text
    assert "9701-3.4.1" in packet(tutor, "Explain 9701-3.4")


def test_six_point_cap_applies_when_many_short_references_fit(tutor):
    for index in range(20):
        kc = f"9701-3.4.{index + 10}"
        tutor.packs.kcs[kc] = {**tutor.packs.kcs["9701-3.4.1"], "id": kc,
                                "statement": f"Public covalent bonding fact {index}."}
    text = packet(tutor, "9701: covalent bonding")
    assert len(re.findall(r"\[9701-3\.4\.\d+;", text)) == 6
    assert len(text) <= 6000


def test_explicit_subject_wins_even_over_a_selected_stale_kc(tutor):
    text = packet(tutor, "Chemistry: bond energy", "9702-2.1.1")
    assert "9701-5.1.1" in text and "9702-9.1.1" not in text


def test_unambiguous_new_topic_wins_over_stale_session_without_subject_word(tutor):
    text = packet(tutor, "Define covalent bonding")
    assert "9701-3.4.1" in text and "9702-" not in text


def test_explicit_unavailable_subject_does_not_fall_back_to_stale_physics(tutor):
    tutor.packs.kcs = {kc: row for kc, row in tutor.packs.kcs.items() if row['subject'] == 'phys'}
    assert packet(tutor, "9701: define velocity") == ""


def test_empty_menu_session_still_uses_latest_question(tutor):
    tutor.session = None
    text = packet(tutor, "9701: covalent bonding")
    assert "9701-3.4.1" in text


def test_distinctive_topic_terms_rank_above_repeated_generic_overlap(tutor):
    common = {f"9701-7.1.{i}": {**tutor.packs.kcs["9701-3.4.1"],
               "title": "Alpha beta gamma example", "glossary": [], "statement": "Common public fact."}
              for i in range(20)}
    tutor.packs.kcs = {**common, "9701-8.1.1": {**tutor.packs.kcs["9701-3.4.1"],
                      "title": "Zeta alpha example", "glossary": [], "statement": "Distinctive public fact."}}
    text = packet(tutor, "9701: zeta alpha beta gamma")
    assert re.search(r"\[(9701-[^;]+);", text)[1] == "9701-8.1.1"


@pytest.mark.parametrize("maths_loaded", [True, False])
@pytest.mark.parametrize("question,physics_kc,maths_spec", [
    ("In physics, explain momentum of two masses m1 and m2.", "9702-4.1.1", "M1"),
    ("In physics, explain pressure at p1 and p2.", "9702-7.1.1", "P1"),
    ("In physics, explain pressure at P1 and P2.", "9702-7.1.1", "P1"),
])
def test_physics_variable_names_do_not_select_maths_modules(tutor, maths_loaded, question, physics_kc, maths_spec):
    if maths_loaded:
        tutor.packs.kcs[f"{maths_spec}-1.1"] = {**tutor.packs.kcs[physics_kc],
                                               "id": f"{maths_spec}-1.1", "spec": maths_spec, "subject": "math"}
    else:
        tutor.packs.kcs = {kc: row for kc, row in tutor.packs.kcs.items() if row["subject"] != "math"}
    text = packet(tutor, question)
    assert physics_kc in text
    assert f"[{maths_spec}-" not in text


@pytest.mark.parametrize("question", ["M1: momentum", "m1: momentum", "Module m1: momentum", "M1 momentum",
                                      "In physics, explain M1-1.1", "In physics, use module M1 for momentum"])
def test_explicit_maths_course_or_point_still_selects_module(tutor, question):
    tutor.packs.kcs["M1-1.1"] = {**tutor.packs.kcs["9702-4.1.1"], "id": "M1-1.1", "spec": "M1", "subject": "math"}
    text = packet(tutor, question)
    assert "[M1-1.1;" in text
    assert "9702-4.1.1" not in text


@pytest.mark.parametrize("question", ["M1: momentum", "m1: momentum", "Module m1: momentum", "Explain M1-1.1"])
def test_unavailable_explicit_maths_course_does_not_fall_back_to_physics(tutor, question):
    tutor.packs.kcs = {kc: row for kc, row in tutor.packs.kcs.items() if row["subject"] != "math"}
    assert packet(tutor, question) == ""
