"""Experiment evidence counts eligible independent fixed questions once."""
import copy
import json
import random
from datetime import datetime, timedelta

import pytest

from fixtures import PACK, make_vault
from test_fixed_batch_uniqueness import KC as SOURCE_KC, OTHER_KC, _setup
from tutorlib import experiments, session, store, topicals

KC = "9702-2.1.4"


@pytest.mark.parametrize("fixed_count", [1, 2])
@pytest.mark.parametrize("sequential", [False, True])
@pytest.mark.parametrize("unavailable", ["structured", "supported", "excluded"])
def test_public_retest_counts_only_eligible_fixed_questions_once(tmp_path, fixed_count, sequential, unavailable):
    root = make_vault(tmp_path)
    source = root / ".tutor/packs/v1/specs/9702/packs/9702-2.1.json"
    pack = json.loads(source.read_text())
    fixed = []
    for index in range(fixed_count):
        item = copy.deepcopy(PACK["items"][0])
        item.update(id=f"retest-{index}", kcs=[KC], source={"type": "past", "qid": f"9702_s23_12_q{index + 1}"})
        fixed.append(item)
    extra = copy.deepcopy(PACK["items"][4])
    if unavailable != "structured":
        extra = copy.deepcopy(fixed[0])
        extra.update(id="unavailable-question", source={"type": "past", "qid": "9702_s23_12_q99"})
    if unavailable == "supported":
        graph_path = source.parents[1] / "graph.json"
        graph = json.loads(graph_path.read_text())
        graph["subtopics"].append({"id": "9702-2.2", "title": "Other chapter", "topic": "9702-2"})
        graph_path.write_text(json.dumps(graph))
        extra["topical"] = {"reviewed": True, "chapters": ["9702-2.1"],
                            "requires": ["9702-2.1", "9702-2.2"], "revision": graph["version"],
                            "support": {"9702-2.2": "A prerequisite fact provided during assisted practice."}}
    pack["items"] = [*fixed, extra]
    source.write_text(json.dumps(pack))
    original_source = source.read_bytes()
    clock = [datetime.fromisoformat("2026-09-20T17:00:00+08:00")]
    tutor = session.Tutor(store.Vault(root), rng=random.Random(0), now=lambda: clock[0], one_at_a_time=sequential)
    tutor.log({"type": "exp_start", "exp": "E1", "subject": "phys",
               "arms": ["worked_faded", "problem_first"], "eligible": {}})
    tutor.log({"type": "exp_assign", "exp": "E1", "kc": KC, "arm": "worked_faded", "pair": 0})
    if unavailable == "excluded":
        tutor.log({"type": "topical_exclude", "identity": topicals.identity(extra), "chapter": "9702-2.1",
                   "missing": [], "reason": "Learner excluded this source"})
    clock[0] += timedelta(days=8)
    assert tutor.start("review", 20, [KC])["blocks"][0]["kind"] == "retest"
    activity = tutor.next()
    prefix = {path: path.read_bytes() for path in (root / ".tutor/events").glob("*.jsonl")}
    tutor = session.Tutor(store.Vault(root), rng=random.Random(0), now=lambda: clock[0], one_at_a_time=sequential)
    assert all(path.read_bytes() == data for path, data in prefix.items())
    activity = tutor.next()
    for _ in range(4):
        assert activity.get("items") and all(p["block"] == "retest" for p in tutor.session["presented"].values())
        tutor.answer(", ".join(f"{question['n']}B4" for question in activity["items"]))
        if any(event["type"] == "exp_score" for event in tutor.vault.events()):
            break
        activity = tutor.next()
    answers = [event for event in tutor.vault.events() if event["type"] == "answer"]
    identities = [topicals.identity(next(item for item in fixed if item["id"] == event["item"]))
                  for event in answers]
    assert len(answers) == fixed_count
    assert len(identities) == len(set(identities))
    assert tutor.state["experiments"]["E1"]["pairs"][0]["scores"] == {KC: 1.0}
    assert experiments.retests_due(tutor.state, clock[0]) == []
    assert source.read_bytes() == original_source
    assert all(path.read_bytes().startswith(data) for path, data in prefix.items())
    before = copy.deepcopy(tutor.state)
    tutor = session.Tutor(store.Vault(root), now=lambda: clock[0])
    assert tutor.state == before
    tutor.rebuild()
    assert tutor.state == before


@pytest.mark.parametrize("sequential", [False, True])
def test_template_only_retest_keeps_three_independently_sampled_attempts(tmp_path, sequential):
    root = make_vault(tmp_path)
    source = root / ".tutor/packs/v1/specs/9702/packs/9702-2.1.json"
    pack = json.loads(source.read_text())
    pack["items"] = [copy.deepcopy(PACK["items"][1])]
    source.write_text(json.dumps(pack))
    original = source.read_bytes()
    clock = [datetime.fromisoformat("2026-09-20T17:00:00+08:00")]
    tutor = session.Tutor(store.Vault(root), rng=random.Random(0), now=lambda: clock[0], one_at_a_time=sequential)
    tutor.log({"type": "exp_start", "exp": "E1", "subject": "phys",
               "arms": ["worked_faded", "problem_first"], "eligible": {}})
    tutor.log({"type": "exp_assign", "exp": "E1", "kc": KC, "arm": "worked_faded", "pair": 0})
    clock[0] += timedelta(days=8)
    tutor.start("review", 20, [KC])
    for _ in range(3):
        activity = tutor.next()
        assert activity.get("items")
        assert all(p["inst"].get("params") for p in tutor.session["presented"].values())
        tutor.answer(", ".join(f"{question['n']}?" for question in activity["items"]))
        if tutor.state["experiments"]["E1"]["pairs"][0]["scores"]:
            break
    assert len([event for event in tutor.vault.events() if event["type"] == "answer"]) == 3
    assert len([event for event in tutor.vault.events() if event["type"] == "exp_score"]) == 1
    assert tutor.state["experiments"]["E1"]["pairs"][0]["scores"] == {KC: 0.0}
    assert source.read_bytes() == original


@pytest.mark.parametrize("sequential", [False, True])
@pytest.mark.parametrize("distinct_parts", [False, True])
def test_retest_target_counts_canonical_sources_across_preserved_kc_contexts(tmp_path, sequential, distinct_parts):
    tutor, clock, source = _setup(tmp_path, aliases=True, sequential=sequential)
    content = json.loads(source.read_text())
    content["items"][1]["kcs"] = [SOURCE_KC, OTHER_KC]
    if distinct_parts:
        for row, part in zip(content["items"], ("a", "b")):
            row["source"]["part"] = part
    source.write_text(json.dumps(content))
    before = source.read_bytes()
    tutor.log({"type": "exp_start", "exp": "E1", "subject": "phys",
               "arms": ["worked_faded", "problem_first"], "eligible": {}})
    tutor.log({"type": "exp_assign", "exp": "E1", "kc": SOURCE_KC, "arm": "worked_faded", "pair": 0})
    clock[0] += timedelta(days=8)
    tutor.start("review", 20, [SOURCE_KC])
    tutor.next()
    tutor = session.Tutor(store.Vault(tutor.vault.root), now=lambda: clock[0], one_at_a_time=sequential)
    for _ in range(3):
        activity = tutor.next()
        assert activity.get("items")
        tutor.answer(", ".join(f"{question['n']}?" for question in activity["items"]))
        if tutor.state["experiments"]["E1"]["pairs"][0]["scores"]:
            break
    answers = [event for event in tutor.vault.events() if event["type"] == "answer"]
    assert len(answers) == (2 if distinct_parts else 1)
    assert tutor.state["experiments"]["E1"]["pairs"][0]["scores"] == {SOURCE_KC: 0.0}
    assert source.read_bytes() == before
    assert len(tutor.packs.items_for(SOURCE_KC)) == 2  # retain both assessed teaching contexts
