import random
from datetime import datetime

import pytest

from fixtures import make_vault
from tutorlib import diagnose, packs, session, store

T0 = datetime.fromisoformat("2026-09-29T17:00:00+08:00")


@pytest.fixture
def tutor(tmp_path):
    return session.Tutor(store.Vault(make_vault(tmp_path)), rng=random.Random(0), now=lambda: T0)


def test_map_dump_ranks_kcs_by_glossary_hits(tutor):
    text = "The video said velocity is speed with a direction, and displacement is a vector. Then suvat."
    out = diagnose.map_dump(text, tutor.packs)
    assert out["kcs"][0]["kc"] == "9702-2.1.1"
    assert {"velocity", "displacement"} <= set(out["kcs"][0]["hits"])
    assert any(k["kc"] == "9702-2.1.4" for k in out["kcs"])


def test_map_dump_flags_misconception_echo(tutor):
    text = "distance and displacement are basically the same thing"
    out = diagnose.map_dump(text, tutor.packs)
    assert out["misconceptions"][0]["id"] == "m1"


def test_classify_levels():
    assert diagnose.classify([(3, True), (4, True)])["level"] == "secure"
    assert diagnose.classify([(3, True), (4, False)])["level"] == "partial"
    r = diagnose.classify([(3, False), (2, False)], errors=["RECALL"])
    assert r["level"] == "gap" and r["gap_type"] == "no_schema"
    r = diagnose.classify([(3, False), (2, True)], errors=["CONCEPT"], misconceptions=["m1"])
    assert r["gap_type"] == "misconception"
    assert diagnose.classify([(3, False), (2, True)], errors=["SLIP"])["gap_type"] == "slip"


def _answer(tutor, act, good):
    parts = []
    for q in act["items"]:
        inst = tutor.session["presented"][str(q["n"])]["inst"]
        if q["kind"] == "mcq":
            wrong = next(k for k in inst["options"] if k != inst["answer"])
            parts.append(f"{q['n']}{inst['answer'] if good else wrong}3")
        else:
            v = inst["answer"]["value"] * (1 if good else 3.7)
            parts.append(f"{q['n']} = {v:.3g} {inst['answer'].get('unit', '')} ~3")
    tutor.answer(", ".join(parts))


def _run(tutor, good):
    tutor.start("diagnose", minutes=40, focus=["9702-2.1.1", "9702-2.1.4"])
    for _ in range(15):
        act = tutor.next()
        if act["activity"] != "questions" or act["block"] != "bracket":
            return act
        _answer(tutor, act, good)
    raise AssertionError("bracketing never finished")


def test_bracketing_all_correct_finds_no_gaps(tutor):
    _run(tutor, good=True)
    diag = [e for e in tutor.vault.events() if e["type"] == "diagnosis"][-1]
    assert all(r["level"] == "secure" for r in diag["results"].values())
    assert not tutor.state["gaps"]


def test_bracketing_failures_insert_repair_blocks(tutor):
    act = _run(tutor, good=False)
    assert set(tutor.state["gaps"]) == {"9702-2.1.1", "9702-2.1.4"}
    kinds = [b["kind"] for b in tutor.session["blocks"]]
    assert kinds.count("learn") >= 1 and kinds[-1] == "exit"
    assert act["activity"] in ("questions", "teach")


def test_at_most_three_items_per_kc(tutor):
    _run(tutor, good=False)
    per_kc = {}
    for e in tutor.vault.events():
        if e["type"] == "answer" and e["block"] == "bracket":
            per_kc[e["kcs"][0]] = per_kc.get(e["kcs"][0], 0) + 1
    assert per_kc and max(per_kc.values()) <= 3
