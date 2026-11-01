"""External, disposable public RED controls for approved B248/B250 scope."""
import copy
import json
import random
from datetime import datetime

import pytest

from fixtures import make_vault
from test_historical_tags import history
from test_session import T0
from test_v110 import answer
from tutorlib import model, session, store


KC = "9702-2.1.1"
OCT = "2026-10-01T00:01:00+08:00"
SEP = "2026-09-30T23:59:00+08:00"


def setup(tmp_path, when=OCT, two=False):
    clock = [datetime.fromisoformat(when)]
    tutor = session.Tutor(store.Vault(make_vault(tmp_path)), rng=random.Random(0), now=lambda: clock[0])
    tutor.start("test", focus=["9702-2.1" if two else KC])
    return tutor, clock, tutor.next()["items"]


def wrong(tutor, item):
    return tutor.answer(f"{item['n']}?")["results"][0]["event"]


def event_bytes(tutor):
    return {p: p.read_bytes() for p in (tutor.vault.tutor / "events").glob("*.jsonl")}


def raw_events(tutor):
    return [json.loads(line) for p in tutor.vault._event_files() for line in p.read_bytes().splitlines()]


def check_error(state, code):
    errors = state["traits"]["errors"].get("phys", {})
    assert errors.get(code, 0) == 1
    assert sum(errors.values()) == 1 and all(n >= 0 for n in errors.values())


def check_cache(tutor):
    assert tutor.state == tutor._fold()
    assert tutor.state["last_event"] == tutor.vault.last_event_id() == list(tutor.vault.events())[-1]["id"]
    recorded = event_bytes(tutor)
    restarted = session.Tutor(tutor.vault, now=tutor.now)
    assert restarted.state == tutor.state == restarted._fold()
    assert all(p.read_bytes() == data for p, data in recorded.items())


def test_public_month_rollback_tag_preserves_diagnosis_context_and_cache(tmp_path):
    tutor, clock, items = setup(tmp_path)
    target = wrong(tutor, items[0])
    prefix = event_bytes(tutor)
    clock[0] = datetime.fromisoformat(SEP)

    assert tutor.tag(target, "TIME")["ok"]

    check_error(tutor.state, "TIME")
    check_cache(tutor)
    original = next(e for e in raw_events(tutor) if e["id"] == target)
    assert original["grade"]["error"] == "RECALL"
    derived = next(e for e in tutor.vault.events() if e["id"] == target)
    assert derived["grade"]["error"] == "RECALL"
    tag = next(e for e in raw_events(tutor) if e["type"] == "tag")
    assert type(tag["revision"]) is int and tag["revision"] == 1
    assert tag["answer_context"]["error"] == "RECALL"
    assert all(p.read_bytes().startswith(data) for p, data in prefix.items())


def test_new_tag_revisions_keep_latest_repeated_correction_across_backward_months(tmp_path):
    tutor, clock, items = setup(tmp_path)
    target = wrong(tutor, items[0])
    for when, error in [(SEP, "TIME"), ("2026-08-31T23:59:00+08:00", "SLIP"),
                        ("2026-07-31T23:59:00+08:00", "MISREAD")]:
        clock[0] = datetime.fromisoformat(when)
        assert tutor.tag(target, error)["ok"]
    check_error(tutor.state, "MISREAD")
    check_cache(tutor)
    tags = [e for e in tutor.vault.events() if e["type"] == "tag"]
    assert [e["revision"] for e in tags] == [1, 2, 3]
    assert [e["error"] for e in tags] == ["TIME", "SLIP", "MISREAD"]
    assert [e["answer_context"]["error"] for e in tags] == ["RECALL", "TIME", "SLIP"]


def test_legacy_early_tags_in_one_file_keep_written_order_after_target(tmp_path):
    tutor, clock, items = setup(tmp_path)
    target = wrong(tutor, items[0])
    for when, code in [(SEP, "TIME"), ("2026-09-30T23:58:00+08:00", "SLIP")]:
        tutor.vault.append_event({"type": "tag", "target": target, "error": code}, now=datetime.fromisoformat(when))
    before = event_bytes(tutor)

    tutor.rebuild()

    check_error(tutor.state, "SLIP")
    check_cache(tutor)
    tags = [e for e in tutor.vault.events() if e["type"] == "tag"]
    assert [e["error"] for e in tags] == ["TIME", "SLIP"]
    assert all(p.read_bytes() == data for p, data in before.items())


def test_ambiguous_legacy_multimonth_tags_stay_unbound_then_new_revision_is_explicit(tmp_path):
    tutor, clock, items = setup(tmp_path)
    target = wrong(tutor, items[0])
    for when, code in [(SEP, "TIME"), ("2026-08-31T23:59:00+08:00", "SLIP")]:
        tutor.vault.append_event({"type": "tag", "target": target, "error": code}, now=datetime.fromisoformat(when))
    tutor.rebuild()
    check_error(tutor.state, "RECALL")
    assert all("answer_context" not in e for e in tutor.vault.events() if e["type"] == "tag")
    clock[0] = datetime.fromisoformat("2026-07-31T23:59:00+08:00")

    assert tutor.tag(target, "MISREAD")["ok"]

    check_error(tutor.state, "MISREAD")
    check_cache(tutor)
    tagged = [e for e in raw_events(tutor) if e["type"] == "tag" and e.get("revision") == 1]
    assert len(tagged) == 1 and tagged[0]["answer_context"]["error"] == "RECALL"


def test_revision_uses_max_valid_bound_value_not_clock_or_unbound_metadata(tmp_path):
    tutor, clock, items = setup(tmp_path)
    target = wrong(tutor, items[0])
    tutor.vault.append_event({"type": "tag", "target": target, "error": "TIME", "revision": 7},
                             now=datetime.fromisoformat("2026-11-01T00:00:00+08:00"))
    tutor.vault.append_event({"type": "tag", "target": target, "error": "SLIP", "revision": 3},
                             now=datetime.fromisoformat(SEP))
    tutor.vault.append_event({"type": "tag", "target": "missing", "error": "TIME", "revision": 100,
                              "answer_context": {"subject": "phys", "kcs": [KC], "error": "RECALL"}},
                             now=datetime.fromisoformat(SEP))
    tutor.rebuild()
    clock[0] = datetime.fromisoformat("2026-08-31T23:59:00+08:00")

    result = tutor.tag(target, "MISREAD")

    tagged = next(e for e in raw_events(tutor) if e["id"] == result["event"])
    assert tagged["revision"] == 8 and tagged["answer_context"]["error"] == "TIME"
    check_error(tutor.state, "MISREAD")
    check_cache(tutor)


def test_rolled_back_tag_on_pruned_target_keeps_bounded_cache_and_replays(tmp_path):
    tutor, target = history(tmp_path, count=601)
    assert target["id"] not in tutor.state["answers"]
    tutor._now = lambda: datetime.fromisoformat("2026-08-31T23:59:00+08:00")
    assert tutor.tag(target["id"], "SLIP")["ok"]
    assert tutor.state["traits"]["errors"]["phys"]["SLIP"] == 1
    assert tutor.state["traits"]["errors"]["phys"]["RECALL"] == 600
    assert len(tutor.state["answers"]) <= 600
    check_cache(tutor)


def test_regrade_still_suppresses_rolled_back_classifications_without_raw_repair(tmp_path):
    tutor, clock, items = setup(tmp_path)
    target = wrong(tutor, items[0])
    clock[0] = datetime.fromisoformat(SEP)
    tutor.tag(target, "TIME")
    before = event_bytes(tutor)
    assert tutor.regrade(target, "Explicit accepted correction")["ok"]
    assert not [e for e in tutor.vault.events() if e["type"] == "tag"]
    assert all(p.read_bytes().startswith(data) for p, data in before.items())
    assert next(e for e in raw_events(tutor) if e["id"] == target)["grade"]["error"] == "RECALL"
    check_cache(tutor)


def test_bad_old_cache_refolds_once_then_uses_consistent_derived_last_id(tmp_path, monkeypatch):
    tutor, clock, items = setup(tmp_path)
    target = wrong(tutor, items[0])
    clock[0] = datetime.fromisoformat(SEP)
    tutor.tag(target, "TIME")
    old = copy.deepcopy(tutor.state)
    old.update(model_version="1.1.10", last_event=target)
    old["traits"]["errors"]["phys"] = {"RECALL": 1}
    old["kcs"][KC]["errors"] = {"RECALL": 1}
    old["answers"][target]["error"] = "RECALL"
    store.write_json(tutor.state_path, old)
    tutor = session.Tutor(tutor.vault, now=lambda: clock[0])
    check_error(tutor.state, "TIME")
    check_cache(tutor)
    with monkeypatch.context() as patch:
        patch.setattr(session.Tutor, "_fold", lambda _: pytest.fail("Upgraded cache must not refold twice"))
        assert session.Tutor(tutor.vault, now=lambda: clock[0]).state == tutor.state


def test_completed_session_after_month_rollback_preserves_days_and_closes_once(tmp_path):
    tutor, clock, items = setup(tmp_path)
    wrong(tutor, items[0])
    prefix = event_bytes(tutor)
    clock[0] = datetime.fromisoformat(SEP)

    summary = tutor.end()

    assert summary["answered"] == 1
    assert tutor.state["study_days"] == ["2026-09-30", "2026-10-01"]
    assert tutor.state["session_days"] == {}
    check_cache(tutor)
    assert all(p.read_bytes().startswith(data) for p, data in prefix.items())
    assert all("_answer_days" not in e for e in raw_events(tutor))


def test_answer_before_its_known_start_keeps_bound_day_when_session_ends(tmp_path):
    tutor, clock, items = setup(tmp_path)
    clock[0] = datetime.fromisoformat(SEP)
    wrong(tutor, items[0])
    clock[0] = datetime.fromisoformat("2026-10-02T12:00:00+08:00")
    tutor.end()
    assert tutor.state["study_days"] == ["2026-09-30", "2026-10-02"]
    assert tutor.state["session_days"] == {}
    check_cache(tutor)


def test_multiple_known_answer_days_survive_end_before_start_and_answers(tmp_path):
    tutor, clock, items = setup(tmp_path, two=True)
    wrong(tutor, items[0])
    clock[0] = datetime.fromisoformat(SEP)
    wrong(tutor, items[1])
    tutor.end()
    assert tutor.state["study_days"] == ["2026-09-30", "2026-10-01"]
    assert tutor.state["session_days"] == {}
    check_cache(tutor)


def test_recovered_ended_summary_excludes_private_day_binding_and_preserves_raw_summary(tmp_path, monkeypatch):
    tutor, clock, items = setup(tmp_path)
    wrong(tutor, items[0])
    clock[0] = datetime.fromisoformat(SEP)
    real_save = tutor._save

    def interrupted():
        if any(e["type"] == "session_end" for e in tutor.vault.events()):
            raise OSError("critical end persistence interrupted")
        return real_save()

    with monkeypatch.context() as patch:
        patch.setattr(tutor, "_save", interrupted)
        with pytest.raises(OSError, match="critical end persistence interrupted"):
            tutor.end()
    ended = next(e for e in raw_events(tutor) if e["type"] == "session_end")
    recorded = event_bytes(tutor)

    recovered = tutor.end()

    assert recovered == {k: v for k, v in ended.items() if k not in ("id", "ts", "type")}
    assert "_answer_days" not in recovered
    assert tutor.state["study_days"] == ["2026-09-30", "2026-10-01"]
    assert tutor.state["session_days"] == {}
    assert len([e for e in tutor.vault.events() if e["type"] == "session_end"]) == 1
    assert all(p.read_bytes() == data for p, data in recorded.items())
    check_cache(tutor)


def test_normal_midnight_spanning_session_stays_unchanged(tmp_path):
    tutor, clock, items = setup(tmp_path, when=SEP, two=True)
    wrong(tutor, items[0])
    clock[0] = datetime.fromisoformat(OCT)
    wrong(tutor, items[1])
    tutor.end()
    assert tutor.state["study_days"] == ["2026-09-30", "2026-10-01"]
    check_cache(tutor)


@pytest.mark.parametrize("abandoned,answered", [(True, True), (False, False)])
def test_abandoned_or_zero_answer_rolled_back_end_does_not_invent_study_day(tmp_path, abandoned, answered):
    tutor, clock, items = setup(tmp_path)
    if answered:
        wrong(tutor, items[0])
    clock[0] = datetime.fromisoformat(SEP)
    tutor.end(abandoned=abandoned)
    assert tutor.state["study_days"] == [] and tutor.state["session_days"] == {}
    check_cache(tutor)


def test_unknown_session_start_does_not_acquire_guessed_answer_days(tmp_path):
    vault = store.Vault(make_vault(tmp_path))
    event = answer(correct=False, session="unknown-session", ts=datetime.fromisoformat(OCT))
    saved = vault.append_event(event, now=datetime.fromisoformat(OCT))
    ended = vault.append_event({"type": "session_end", "session": "unknown-session", "answered": 1,
                               "abandoned": False}, now=datetime.fromisoformat(SEP))
    before = {p: p.read_bytes() for p in (vault.tutor / "events").glob("*.jsonl")}
    loaded = list(vault.events())
    assert loaded == [ended, saved]
    assert all("_answer_days" not in e for e in loaded)
    assert all(p.read_bytes() == data for p, data in before.items())


@pytest.mark.parametrize("kind", ["ordinary", "deferred", "unknown"])
def test_raw_private_day_context_cannot_forge_or_replace_reader_bound_days(tmp_path, kind):
    vault = store.Vault(make_vault(tmp_path))
    if kind != "unknown":
        vault.append_event({"type": "session_start", "session": "bound", "mode": "test"},
                           now=datetime.fromisoformat(OCT))
    vault.append_event(answer(correct=False, session="bound", ts=datetime.fromisoformat(OCT)),
                       now=datetime.fromisoformat(OCT))
    ended_at = "2026-10-02T12:00:00+08:00" if kind == "ordinary" else SEP
    ended = vault.append_event({"type": "session_end", "session": "bound", "answered": 1,
                               "abandoned": False, "_answer_days": ["2040-01-01"]},
                              now=datetime.fromisoformat(ended_at))
    before = {p: p.read_bytes() for p in (vault.tutor / "events").glob("*.jsonl")}

    tutor = session.Tutor(vault, now=lambda: datetime.fromisoformat(ended_at))

    loaded = next(e for e in vault.events() if e["id"] == ended["id"])
    if kind == "deferred":
        assert loaded["_answer_days"] == ["2026-10-01"]
    else:
        assert "_answer_days" not in loaded
    expected = (["2026-10-01", "2026-10-02"] if kind == "ordinary" else
                ["2026-09-30", "2026-10-01"] if kind == "deferred" else ["2026-09-30"])
    assert tutor.state["study_days"] == expected
    assert ended["_answer_days"] == ["2040-01-01"]
    assert all(p.read_bytes() == data for p, data in before.items())
