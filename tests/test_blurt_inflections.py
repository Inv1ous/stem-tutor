"""Ordinary plural terms must not turn recalled ideas into due missed ideas."""
import copy
from datetime import datetime

import pytest

from fixtures import make_vault
from tutorlib import blurt, model, session, store


@pytest.mark.parametrize("text,context", [
    ("Distance is scalar; displacement has a direction.", None),
    ("Distances are scalar; displacements have directions.", None),
    ("A force acts on a charge.", ["force", "charge"]),
    ("Forces act on charges.", ["force", "charge"]),
    ("Volume has a value.", ["volume", "value"]),
    ("Volumes have values.", ["volume", "value"]),
    ("The angle and pressure are measured.", ["angle", "pressure"]),
    ("Angles and pressures are measured.", ["angle", "pressure"]),
])
def test_public_blurt_recognizes_final_e_plurals_without_changing_marks_or_due(tmp_path, text, context):
    root = make_vault(tmp_path)
    now = lambda: datetime.fromisoformat("2026-10-08T17:00:00+08:00")
    tutor = session.Tutor(store.Vault(root), now=now)
    kc = "9702-2.1.1"
    if context:
        # Additional valid glossary context exists only in this disposable in-memory test pack.
        tutor.packs.kc(kc).update(title=" and ".join(context), glossary=context)
    missed_kc = "9702-2.1.4"
    tutor.log({"type": "answer", "item": "introduced-blurt", "kcs": [kc, missed_kc], "subject": "phys", "difficulty": 3,
               "conf": 3, "hinted": False, "marks": 1,
               "grade": {"correct": True, "score": 1.0, "error": None, "misconception": None}})
    before = copy.deepcopy(tutor.state["kcs"][kc])
    missed_before = copy.deepcopy(tutor.state["kcs"][missed_kc])
    historical = {p: p.read_bytes() for p in (root / ".tutor/events").glob("*.jsonl")}

    result = tutor.blurt("9702-2.1", text)

    assert kc in result["recalled"] and kc not in result["missed"]
    if context:
        assert set(result["ideas"][kc]["hits"]) == set(context)
    assert tutor.state["kcs"][kc] == before
    assert missed_kc in result["missed"]
    assert missed_kc in model.due_kcs(tutor.state, now()) and kc not in model.due_kcs(tutor.state, now())
    assert tutor.state["kcs"][missed_kc]["n"] == missed_before["n"]
    assert text in (root / result["log"]).read_text()
    events = list(tutor.vault.events())
    assert sum(e["type"] == "answer" for e in events) == 1
    assert sum(e["type"] == "blurt" for e in events) == 1
    assert all(p.read_bytes().startswith(content) for p, content in historical.items())
    restored = session.Tutor(store.Vault(root), now=now)
    assert restored.state == tutor.state == restored._fold()


@pytest.mark.parametrize("word,expected", [
    ("branches", "branch"), ("brushes", "brush"), ("classes", "class"),
    ("indexes", "index"), ("buzzes", "buzz"), ("potatoes", "potato"),
    ("gases", "gase"), ("ages", "ages"),  # preserve the existing length guards, not full English lemmatization
])
def test_other_es_suffixes_and_short_word_guard_keep_existing_behavior(word, expected):
    assert blurt._stem(word) == expected


def test_unrelated_terms_still_miss_and_pull_a_scheduled_idea_forward(tmp_path):
    tutor = session.Tutor(store.Vault(make_vault(tmp_path)))
    kc = "9702-2.1.1"
    tutor.log({"type": "answer", "item": "introduced-blurt", "kcs": [kc], "subject": "phys", "difficulty": 3,
               "conf": 3, "hinted": False, "marks": 1,
               "grade": {"correct": True, "score": 1.0, "error": None, "misconception": None}})
    result = tutor.blurt("9702-2.1", "Forces act on charges.")
    assert kc not in result["recalled"] and kc in result["missed"]
    assert kc in model.due_kcs(tutor.state, tutor.now())
