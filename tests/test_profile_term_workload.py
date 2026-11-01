"""Profile forecasts the independent term work that Review can actually offer."""
import copy
import json
from datetime import datetime, timedelta, timezone

from fixtures import make_vault
from tutorlib import lesson, model, profile, session, store

KC = "9702-2.1.1"
NOW = datetime.fromisoformat("2026-09-29T17:00:00+08:00")


def prepared(tmp_path):
    root = make_vault(tmp_path)
    source = root / ".tutor/packs/v1/specs/9702/packs/9702-2.1.json"
    pack = json.loads(source.read_text())
    terms = [{"term": name, "meaning": f"The meaning of {name}"}
             for name in ("Velocity", "Distance", "Speed", "Vector", "Acceleration", "Displacement")]
    pack["teach"] = {KC: {"terms": terms}}
    source.write_text(json.dumps(pack))
    tutor = session.Tutor(store.Vault(root), now=lambda: NOW)
    return tutor, source, terms


def test_public_profile_includes_due_published_terms_without_changing_history(tmp_path):
    tutor, source, terms = prepared(tmp_path)
    tid = lesson.term_id(KC, terms[0]["term"])
    tutor.log({"type": "term_introduced", "term_id": tid, "kc": KC})
    original_source = source.read_bytes()
    before = copy.deepcopy(tutor.state)
    history = {path: path.read_bytes() for path in (tutor.vault.tutor / "events").glob("*.jsonl")}

    assert profile.summary(tutor.state, tutor.packs, NOW)["workload"] == [1, 0, 0, 0, 0, 0, 0]

    assert tutor.state == before
    assert source.read_bytes() == original_source
    assert all(path.read_bytes() == data for path, data in history.items())
    restarted = session.Tutor(store.Vault(tutor.vault.root), now=lambda: NOW)
    assert profile.summary(restarted.state, restarted.packs, NOW)["workload"][0] == 1
    restarted.rebuild()
    assert profile.summary(restarted.state, restarted.packs, NOW)["workload"][0] == 1
    assert restarted.start("review", 10)["blocks"][0] == {"kind": "term_review", "terms": [tid]}
    assert terms[0]["term"] in restarted.next()["items"][0]["stem"]


def test_term_forecast_uses_local_calendar_days_and_keeps_independent_kc_work(tmp_path):
    tutor, _, terms = prepared(tmp_path)
    midnight = NOW.replace(hour=0, minute=0, second=0, microsecond=0)
    dues = [NOW - timedelta(days=2), NOW + timedelta(hours=1), midnight + timedelta(days=1),
            midnight + timedelta(days=6, hours=23, minutes=59), midnight + timedelta(days=7),
            NOW + timedelta(days=30)]
    for term, due in zip(terms, dues):
        tid = lesson.term_id(KC, term["term"])
        tutor.log({"type": "term_introduced", "term_id": tid, "kc": KC})
        tutor.state["terms"][tid]["fsrs"]["due"] = due.astimezone(timezone.utc).isoformat()
    tutor.state["kcs"][KC] = model._new_kc()
    tutor.state["kcs"][KC]["fsrs"] = copy.deepcopy(tutor.state["terms"][lesson.term_id(KC, terms[0]["term"])]["fsrs"])
    tutor.state["kcs"][KC]["fsrs"]["due"] = (midnight + timedelta(days=1)).isoformat()
    before = copy.deepcopy(tutor.state)

    assert profile.summary(tutor.state, tutor.packs, NOW)["workload"] == [2, 2, 0, 0, 0, 0, 1]

    assert tutor.state == before


def test_removed_and_orphaned_terms_stay_historical_without_inflating_available_work(tmp_path):
    tutor, _, terms = prepared(tmp_path)
    current = lesson.term_id(KC, terms[0]["term"])
    removed = lesson.term_id(KC, "No longer taught")
    orphaned = lesson.term_id("9702-9.9.9", "Unknown idea")
    for tid, kc in ((current, KC), (removed, KC), (orphaned, "9702-9.9.9")):
        tutor.log({"type": "term_introduced", "term_id": tid, "kc": kc})
    tutor.log({"type": "term_introduced", "term_id": current, "kc": KC})
    before = copy.deepcopy(tutor.state)

    assert profile.summary(tutor.state, tutor.packs, NOW)["workload"] == [1, 0, 0, 0, 0, 0, 0]

    assert tutor.state == before
    assert set(tutor.state["terms"]) == {current, removed, orphaned}
