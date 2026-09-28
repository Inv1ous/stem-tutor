import random

import pytest

from fixtures import make_vault
from tutorlib import model, packs, store


@pytest.fixture
def P(tmp_path):
    return packs.Packs(store.Vault(make_vault(tmp_path)))


def test_kc_meta_includes_subject_and_prereqs(P):
    k = P.kc("9702-2.1.4")
    assert k["subject"] == "phys" and k["prereqs"] == ["9702-2.1.1"] and k["spec"] == "9702"


def test_items_for_kc(P):
    ids = [i["id"] for i in P.items_for("9702-2.1.1")]
    assert ids == ["9702-2.1-i01", "9702-2.1-i04"]


def test_misconception_lookup(P):
    assert P.misconception("9702-2.1", "m1")["statement"].startswith("Distance")


def test_instantiate_template_computes_answer_and_distractors(P):
    item = next(i for i in P.items_for("9702-2.1.4") if i["id"] == "9702-2.1-i02")
    inst = packs.instantiate(item, random.Random(3))
    t = inst["params"]["t"]
    assert t in (1.0, 1.5, 2.0, 2.5, 3.0)
    assert inst["answer"]["value"] == pytest.approx(0.5 * 9.81 * t * t)
    assert inst["distractors"][0]["value"] == pytest.approx(9.81 * t)
    assert f"{t:.1f} s" in inst["stem"] and "[[" not in inst["stem"]


def test_instantiate_shuffles_mcq_and_remaps_answer(P):
    item = P.items_for("9702-2.1.1")[0]
    seen = set()
    for seed in range(20):
        inst = packs.instantiate(item, random.Random(seed))
        assert inst["options"][inst["answer"]] == "displacement"
        mis_letter = next(k for k, v in inst["distractors"].items() if v == "m1")
        assert inst["options"][mis_letter] == "distance"
        seen.add(inst["answer"])
    assert len(seen) > 1


def test_past_paper_items_never_shuffled(P):
    item = dict(P.items_for("9702-2.1.1")[1], source={"type": "past", "ref": "x"}, shuffle=True)
    assert packs.instantiate(item, random.Random(0))["answer"] == "B"


def test_select_prefers_difficulty_near_target(P):
    state = model.new_state()
    easy = P.select_item("9702-2.1.1", state, target_p=0.8, rng=random.Random(0))
    hard = P.select_item("9702-2.1.1", state, target_p=0.3, rng=random.Random(0))
    assert easy["difficulty"] < hard["difficulty"]


def test_select_avoids_recently_seen_fixed_items(P):
    state = model.new_state()
    state["items_seen"]["9702-2.1-i01"] = "2026-09-28T10:00:00+08:00"
    from datetime import datetime
    now = datetime.fromisoformat("2026-09-29T10:00:00+08:00")
    item = P.select_item("9702-2.1.1", state, target_p=0.8, rng=random.Random(0), now=now)
    assert item["id"] == "9702-2.1-i04"


def test_worked_example_and_note(P):
    assert P.worked_for("9702-2.1.4")[0]["id"] == "we1"
    assert P.pack_for_kc("9702-2.1.4")["note"].endswith("Equations of motion.md")


def test_plan_week_objectives(P):
    assert P.plan["weeks"]["5"][0]["kcs"] == ["9702-2.1.1", "9702-2.1.4"]


def test_template_evaluator_rejects_non_arithmetic():
    with pytest.raises(ValueError):
        packs._eval("__import__('os').system('true')", {})
    with pytest.raises(ValueError):
        packs._eval("t.__class__", {"t": 1.0})
    assert packs._eval("sqrt(2*g*h) > 1 and h < 5", {"g": 9.81, "h": 2.0}) == 1.0


def test_extra_tier_items_only_used_after_explained_ones(P):
    extra = dict(P.items_for("9702-2.1.1")[0], id="9702-2.1-x99", tier="extra", explanation=None, difficulty=2)
    P.pack("9702-2.1")["items"].append(extra)
    state = model.new_state()
    first = P.select_item("9702-2.1.1", state, target_p=0.8, rng=random.Random(0))
    assert first["id"] != "9702-2.1-x99"
    only_extra = P.select_item("9702-2.1.1", state, target_p=0.8, rng=random.Random(0),
                               exclude={"9702-2.1-i01", "9702-2.1-i04"})
    assert only_extra["id"] == "9702-2.1-x99"
