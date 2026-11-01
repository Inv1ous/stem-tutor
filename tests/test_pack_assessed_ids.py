"""Legacy assessed-ID repeats adapt only the runtime copy, never published bytes."""
import copy
import json
from datetime import datetime, timedelta

from fixtures import PACK, make_vault
import library_assets
from tutorlib import packs, session, store

NOW = datetime.fromisoformat("2026-10-27T12:00:00+08:00")
REAL_PACK = "Library/Releases/v274/specs/9702/packs/9702-3.3.json"


def test_runtime_pack_copy_preserves_distinct_id_order_and_other_fields(tmp_path):
    root = make_vault(tmp_path)
    source = root / ".tutor/packs/v1/specs/9702/packs/9702-2.1.json"
    original = json.loads(source.read_text())
    original["items"][0]["kcs"] = ["9702-2.1.4", "9702-2.1.1", "9702-2.1.4", "9702-2.1.1"]
    source.write_text(json.dumps(original))
    before = source.read_bytes()

    loaded = packs.Packs(store.Vault(root)).pack("9702-2.1")

    expected = copy.deepcopy(original)
    expected["items"][0]["kcs"] = ["9702-2.1.4", "9702-2.1.1"]
    assert loaded == expected
    assert source.read_bytes() == before


def test_real_published_repeated_kc_item_records_one_new_attempt_and_replays(tmp_path):
    raw_bytes = library_assets.read_bytes(REAL_PACK)
    real_pack = json.loads(raw_bytes)
    original_item = next(item for item in real_pack["items"] if item["id"] == "9702-3.3-i13")
    assert original_item["kcs"] == ["9702-3.3.2", "9702-3.3.2"]
    root = make_vault(tmp_path)
    base = root / ".tutor/packs/v1/specs/9702"
    (base / "graph.json").write_bytes(library_assets.read_bytes("Library/Releases/v274/specs/9702/graph.json"))
    source = base / "packs/9702-3.3.json"
    source.write_text(json.dumps({**copy.deepcopy(PACK), "subtopic": "9702-3.3", "note": real_pack["note"],
                                 "items": [original_item], "misconceptions": [], "worked": [], "flashcards": []}))
    source_bytes = source.read_bytes()
    vault = store.Vault(root)
    vault.append_event({"type": "note", "text": "Original learner record"}, now=NOW)
    legacy = vault.append_event({"type": "answer", "item": "legacy-duplicate", "kcs": original_item["kcs"],
                                 "subject": "phys", "difficulty": 3, "marks": 1, "hinted": False,
                                 "grade": {"correct": False, "score": 0.0, "error": "RECALL"}},
                                now=NOW - timedelta(days=1))
    prefix = {path: path.read_bytes() for path in vault.tutor.glob("events/*.jsonl")}
    tutor = session.Tutor(vault, now=lambda: NOW)
    prior_count = tutor.state["kcs"]["9702-3.3.2"]["n"]
    assert prior_count == 2  # this compatibility fix does not revise historical answers
    tutor.start("long", 15, focus=["9702-3.3.2"])
    tutor.next()
    tutor = session.Tutor(store.Vault(root), now=lambda: NOW)
    activity = tutor.next()
    tutor.answer(f"{activity['items'][0]['n']} pts=0")

    assert tutor.state["kcs"]["9702-3.3.2"]["n"] - prior_count == 1
    answer, = [event for event in tutor.vault.events() if event.get("item") == original_item["id"]]
    assert answer["kcs"] == ["9702-3.3.2"]
    assert next(event for event in tutor.vault.events() if event["id"] == legacy["id"]) == legacy
    expected_item = {**original_item, "kcs": ["9702-3.3.2"]}
    assert tutor.packs.pack("9702-3.3")["items"][0] == expected_item
    before = copy.deepcopy(tutor.state)
    restarted = session.Tutor(store.Vault(root), now=lambda: NOW)
    restarted.rebuild()
    assert restarted.state == before
    assert source.read_bytes() == source_bytes
    assert all(path.read_bytes().startswith(data) for path, data in prefix.items())
    assert library_assets.read_bytes(REAL_PACK) == raw_bytes
