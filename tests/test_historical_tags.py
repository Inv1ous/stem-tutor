"""Historical correction bindings survive the bounded recent-answer cache."""
import copy
import json
from datetime import timedelta

import pytest

from fixtures import make_vault
from test_v110 import T0, answer
from tutorlib import model, report, session, store


KC = "9702-2.1.1"
OTHER = "9702-2.1.4"


def history(tmp_path, count=601, *, term=False, first_error="RECALL"):
    vault = store.Vault(make_vault(tmp_path))
    first = None
    for n in range(count):
        event = answer(correct=False, ts=T0 + timedelta(seconds=n), item=f"history-{n}",
                       response="A", key="B", question={"kind": "mcq", "stem": f"Question {n}",
                       "options": {"A": "Wrong", "B": "Right"}})
        event["grade"]["error"] = first_error if n == 0 else "RECALL"
        if n == 0:
            event["kcs"] = [KC, OTHER]
            if term:
                event["term_id"] = "term:historical"
        saved = vault.append_event(event, now=T0 + timedelta(seconds=n))
        first = first or saved
    tutor = session.Tutor(vault, now=lambda: T0 + timedelta(days=1))
    return tutor, first


def event_bytes(tutor):
    return {p: p.read_bytes() for p in (tutor.vault.tutor / "events").glob("*.jsonl")}


def check_counts(tutor, recall, code, amount=1):
    errors = tutor.state["traits"]["errors"]["phys"]
    assert errors.get("RECALL", 0) == recall
    assert errors.get(code, 0) == amount
    assert all(n >= 0 for n in errors.values())


@pytest.mark.parametrize("count", [600, 601])
def test_tag_updates_the_same_answer_before_and_after_cache_pruning(tmp_path, count):
    tutor, first = history(tmp_path, count)
    before = event_bytes(tutor)

    assert tutor.tag(first["id"], "SLIP")["ok"]

    check_counts(tutor, count - 1, "SLIP")
    assert tutor.state["kcs"][KC]["errors"]["SLIP"] == 1
    assert tutor.state["kcs"][OTHER]["errors"]["RECALL"] == 0
    assert tutor.state["kcs"][OTHER]["errors"]["SLIP"] == 1
    assert len(tutor.state["answers"]) <= 600
    raw = [json.loads(line) for p in before for line in p.read_bytes().splitlines()]
    assert raw[-1]["answer_context"] == {"subject": "phys", "kcs": [KC, OTHER], "error": "RECALL"}
    assert all(p.read_bytes().startswith(data) for p, data in before.items())
    payload = report.almanac_payload(tutor)
    assert payload["err"]["Could not recall"] == count - 1
    assert sum(payload["err"].values()) == count
    assert "careless slips" in (tutor.vault.root / report.mistakes_note(tutor)).read_text()
    assert payload["err"]["Careless arithmetic"] == 1
    assert "Careless arithmetic ×1" in payload["retro"]["5"]["broke"]
    recorded = event_bytes(tutor)
    restarted = session.Tutor(tutor.vault, now=tutor.now)
    assert restarted.state == tutor.state == restarted._fold()
    assert all(p.read_bytes() == data for p, data in recorded.items())


def test_legacy_late_tag_refolds_once_and_repeated_old_retags_use_effective_error(tmp_path, monkeypatch):
    tutor, first = history(tmp_path)
    assert first["id"] not in tutor.state["answers"]
    legacy = tutor.vault.append_event({"type": "tag", "target": first["id"], "error": "SLIP"}, now=tutor.now())
    old_state = copy.deepcopy(tutor.state)
    old_state.update(model_version="1.1.9", last_event=legacy["id"])
    store.write_json(tutor.state_path, old_state)
    before = event_bytes(tutor)

    tutor = session.Tutor(tutor.vault, now=tutor.now)

    check_counts(tutor, 600, "SLIP")
    assert all(p.read_bytes() == data for p, data in before.items())
    assert tutor.tag(first["id"], "TIME")["ok"]
    check_counts(tutor, 600, "TIME")
    assert tutor.state["traits"]["errors"]["phys"]["SLIP"] == 0
    assert tutor.tag(first["id"], "TIME")["ok"]
    check_counts(tutor, 600, "TIME")
    assert first["id"] not in tutor.state["answers"] and len(tutor.state["answers"]) <= 600
    raw = [json.loads(line) for p in before for line in p.read_bytes().splitlines()]
    assert raw[-1]["answer_context"]["error"] == "TIME"
    assert tutor.state == tutor._fold()
    assert all(p.read_bytes().startswith(data) for p, data in before.items())
    with monkeypatch.context() as patch:
        patch.setattr(session.Tutor, "_fold", lambda _: pytest.fail("Saved upgraded state must not refold again"))
        assert session.Tutor(tutor.vault, now=tutor.now).state == tutor.state


def test_regrade_removes_legacy_and_new_late_tags_without_changing_original_events(tmp_path):
    tutor, first = history(tmp_path)
    tutor.vault.append_event({"type": "tag", "target": first["id"], "error": "SLIP"}, now=tutor.now())
    tutor.rebuild()
    assert tutor.tag(first["id"], "TIME")["ok"]
    before = event_bytes(tutor)

    assert tutor.regrade(first["id"], "Accepted on review")["ok"]

    errors = tutor.state["traits"]["errors"]["phys"]
    assert errors.get("RECALL", 0) == 600
    assert not errors.get("SLIP", 0) and not errors.get("TIME", 0)
    assert not tutor.tag(first["id"], "MISREAD")["ok"]
    assert not any(e["type"] == "tag" and e.get("target") == first["id"] for e in tutor.vault.events())
    assert all(p.read_bytes().startswith(data) for p, data in before.items())
    recorded = event_bytes(tutor)
    assert session.Tutor(tutor.vault, now=tutor.now).state == tutor.state == tutor._fold()
    assert all(p.read_bytes() == data for p, data in recorded.items())


def test_historical_term_tag_does_not_change_parent_kc_error_counts(tmp_path):
    tutor, first = history(tmp_path, term=True)
    assert tutor.tag(first["id"], "SLIP")["ok"]
    check_counts(tutor, 600, "SLIP")
    assert tutor.state["kcs"][KC]["errors"] == {"RECALL": 600}
    assert OTHER not in tutor.state["kcs"]
    assert tutor.state == tutor._fold()


def test_derived_tag_context_is_not_mutated_or_added_to_the_persistent_answer_cache(tmp_path):
    tutor, first = history(tmp_path)
    tutor.vault.append_event({"type": "tag", "target": first["id"], "error": "SLIP"}, now=tutor.now())
    tag = next(e for e in tutor.vault.events() if e["type"] == "tag")
    original = copy.deepcopy(tag)
    state = copy.deepcopy(tutor.state)
    cache = copy.deepcopy(state["answers"])

    model.apply(state, tag)

    assert tag == original
    assert state["answers"] == cache and first["id"] not in state["answers"]
    assert state["traits"]["errors"]["phys"]["SLIP"] == 1


def test_unbound_tag_metadata_cannot_invent_an_answer_correction(tmp_path):
    tutor, _ = history(tmp_path)
    forged = tutor.vault.append_event({"type": "tag", "target": "missing-answer", "error": "SLIP",
                                      "answer_context": {"subject": "phys", "kcs": [KC], "error": "RECALL"}},
                                     now=tutor.now())
    before = event_bytes(tutor)

    tutor.rebuild()

    assert tutor.state["traits"]["errors"]["phys"] == {"RECALL": 601}
    loaded = next(e for e in tutor.vault.events() if e.get("id") == forged["id"])
    assert "answer_context" not in loaded
    assert all(p.read_bytes() == data for p, data in before.items())


def test_historical_unclassified_mistake_is_counted_once_after_retagging(tmp_path):
    tutor, first = history(tmp_path, first_error=None)
    assert tutor.tag(first["id"], "SLIP")["ok"]
    check_counts(tutor, 600, "SLIP")
    assert tutor.tag(first["id"], "MISREAD")["ok"]
    check_counts(tutor, 600, "MISREAD")
    assert tutor.state["traits"]["errors"]["phys"]["SLIP"] == 0
    assert sum(tutor.state["traits"]["errors"]["phys"].values()) == 601
    assert tutor.state == tutor._fold()


@pytest.mark.parametrize("fields", [{}, {"grade": None, "kcs": [KC]}, {"grade": {}, "kcs": None}])
def test_reader_preserves_incomplete_records_without_inventing_context(tmp_path, fields):
    vault = store.Vault(make_vault(tmp_path))
    original = vault.append_event({"type": "answer", **fields}, now=T0)
    tagged = vault.append_event({"type": "tag", "target": original["id"], "error": "SLIP"}, now=T0)
    before = {p: p.read_bytes() for p in (vault.tutor / "events").glob("*.jsonl")}
    assert list(vault.events()) == [original, tagged]
    assert all(p.read_bytes() == data for p, data in before.items())
