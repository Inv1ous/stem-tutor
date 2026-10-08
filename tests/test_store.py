import json
from datetime import datetime

import pytest

from tutorlib import store


def make_vault(tmp_path, name="STEM Tutor"):
    root = tmp_path / "mnt" / name
    (root / ".tutor").mkdir(parents=True)
    (root / ".tutor" / "config.json").write_text(json.dumps({"tz": "Asia/Hong_Kong"}))
    return root


def test_find_vault_in_mount_glob(tmp_path):
    root = make_vault(tmp_path)
    assert store.find_vault([str(tmp_path / "mnt" / "*")]) == root


def test_find_vault_prefers_env_override(tmp_path, monkeypatch):
    root = make_vault(tmp_path, "Elsewhere")
    monkeypatch.setenv("STEM_TUTOR_VAULT", str(root))
    assert store.find_vault([]) == root


def test_find_vault_none_raises(tmp_path):
    with pytest.raises(store.VaultNotFound):
        store.find_vault([str(tmp_path / "nothing" / "*")])


def test_atomic_json_roundtrip(tmp_path):
    p = tmp_path / "a" / "b.json"
    store.write_json(p, {"x": 1})
    assert store.read_json(p) == {"x": 1}
    assert not list(p.parent.glob("*.tmp"))


def test_read_json_default_when_missing(tmp_path):
    assert store.read_json(tmp_path / "missing.json", {"d": 0}) == {"d": 0}


def test_events_append_to_monthly_file_and_read_back(tmp_path):
    v = store.Vault(make_vault(tmp_path))
    v.append_event({"type": "t1"}, now=datetime.fromisoformat("2026-09-30T23:30:00+08:00"))
    v.append_event({"type": "t2"}, now=datetime.fromisoformat("2026-10-01T08:00:00+08:00"))
    files = sorted(p.name for p in (v.tutor / "events").iterdir())
    assert files == ["2026-09.jsonl", "2026-10.jsonl"]
    types = [e["type"] for e in v.events()]
    assert types == ["t1", "t2"]
    assert all("ts" in e and "id" in e for e in v.events())


def test_now_uses_configured_timezone(tmp_path):
    v = store.Vault(make_vault(tmp_path))
    assert v.now().utcoffset().total_seconds() == 8 * 3600


@pytest.mark.parametrize("text", ['{"tz": "Asia/Hong', '"Asia/Hong_Kong"', '[1]', '{"tz": "Not/AZone"}', '{"tz": 8}'])
def test_a_torn_or_odd_config_falls_back_to_the_defaults(tmp_path, text):
    root = make_vault(tmp_path)
    (root / ".tutor" / "config.json").write_text(text)
    v = store.Vault(root)
    assert isinstance(v.config, dict) and str(v.tz) == "Asia/Hong_Kong"


def test_lock_is_exclusive(tmp_path):
    v = store.Vault(make_vault(tmp_path))
    with v.lock():
        with pytest.raises(store.Locked):
            with store.Vault(v.root).lock(wait_seconds=0.3):
                pass
    with v.lock():  # released after exit
        pass


def test_lock_leaves_nothing_in_the_folder_and_ignores_old_lock_files(tmp_path):
    v = store.Vault(make_vault(tmp_path))
    (v.tutor / ".lock").write_text("5")  # left behind by the old engine, undeletable in Cowork
    before = sorted(p.name for p in v.tutor.iterdir())
    with v.lock():
        pass
    assert sorted(p.name for p in v.tutor.iterdir()) == before


def test_icloud_placeholders_detected(tmp_path):
    v = store.Vault(make_vault(tmp_path))
    (v.root / "Subjects").mkdir()
    (v.root / "Subjects" / ".note.md.icloud").write_text("")
    assert v.placeholders() == ["Subjects/.note.md.icloud"]


def test_event_after_a_torn_line_survives_replay(tmp_path):  # B-012
    v = store.Vault(make_vault(tmp_path))
    (v.tutor / "events").mkdir()
    (v.tutor / "events" / "2026-08.jsonl").write_text('{"type": "answer", "item":')  # crash mid-append
    t = datetime.fromisoformat("2026-08-30T12:00:00+08:00")
    v.append_event({"type": "gaps", "add": ["9702-1.1.1"]}, now=t)
    v.append_event({"type": "gaps", "add": ["9702-1.1.2"]}, now=t)
    assert [e["add"] for e in v.events()] == [["9702-1.1.1"], ["9702-1.1.2"]]
    assert v.bad_lines == ["2026-08.jsonl:1"]


def test_a_torn_multibyte_character_loses_only_its_own_line(tmp_path):  # B-012 reopened
    v = store.Vault(make_vault(tmp_path))
    (v.tutor / "events").mkdir()
    t = datetime.fromisoformat("2026-09-30T12:00:00+08:00")
    v.append_event({"type": "gaps", "add": ["a"]}, now=t)
    with open(v.tutor / "events" / "2026-09.jsonl", "ab") as f:
        f.write(b'{"type": "answer", "response": "' + "μ".encode("utf-8")[:1])  # crash mid-character
    v.append_event({"type": "gaps", "add": ["b"]}, now=t)
    assert [e["add"] for e in v.events()] == [["a"], ["b"]] and v.bad_lines == ["2026-09.jsonl:2"]


def test_unicode_line_separators_inside_an_answer_survive_replay(tmp_path):  # B-030
    v = store.Vault(make_vault(tmp_path))
    ev = v.append_event({"type": "answer", "response": "velocity displacement /time\x85\x0c"},
                        now=datetime.fromisoformat("2026-09-30T12:00:00+08:00"))
    assert list(v.events()) == [ev] and v.bad_lines == []


def test_last_event_id_is_the_newest_readable_event(tmp_path):  # B-038
    v = store.Vault(make_vault(tmp_path))
    assert v.last_event_id() is None
    a = v.append_event({"type": "note"}, now=datetime.fromisoformat("2026-09-30T23:59:00+08:00"))
    b = v.append_event({"type": "note"}, now=datetime.fromisoformat("2026-10-01T00:01:00+08:00"))
    assert a["id"] != b["id"] and v.last_event_id() == b["id"]
    with open(v.tutor / "events" / "2026-10.jsonl", "ab") as f:
        f.write(b'{"id": "torn", "type": "ans')  # a crash mid-append: replay skips this line, so it is not the newest
    assert v.last_event_id() == b["id"]


def test_an_icloud_conflict_copy_does_not_count_events_twice(tmp_path):
    v = store.Vault(make_vault(tmp_path))
    t = datetime.fromisoformat("2026-09-30T12:00:00+08:00")
    a = v.append_event({"type": "answer", "grade": {"score": 1.0}}, now=t)
    b = v.append_event({"type": "answer", "grade": {"score": 0.0}}, now=t)
    folder = v.tutor / "events"
    (folder / "2026-09 2.jsonl").write_bytes((folder / "2026-09.jsonl").read_bytes())  # the same lines, copied
    with open(folder / "2026-09 2.jsonl", "a") as f:
        f.write(json.dumps({"type": "note"}) + "\n" + json.dumps({"type": "note"}) + "\n")  # no id: each one counts
    v.append_event({"type": "regrade", "target": b["id"], "grade": {"score": 1.0}}, now=t)
    got = list(v.events())
    assert [e.get("id") for e in got if e["type"] == "answer"] == [a["id"], b["id"]]
    assert len([e for e in got if e["type"] == "note"]) == 2 and got[1]["regraded"]


def test_events_from_a_conflict_copy_are_read_in_time_order(tmp_path):
    v = store.Vault(make_vault(tmp_path))
    a = v.append_event({"type": "note"}, now=datetime.fromisoformat("2026-09-10T12:00:00+08:00"))
    b = v.append_event({"type": "note"}, now=datetime.fromisoformat("2026-09-20T12:00:00+08:00"))
    folder = v.tutor / "events"
    c = {"id": "fromcopy", "ts": "2026-09-15T05:00:00+01:00", "type": "note"}  # the other device, another offset
    (folder / "2026-09 2.jsonl").write_text(json.dumps(a) + "\n" + json.dumps(c) + "\n")
    (folder / "notes.jsonl").write_text(json.dumps({"id": "stray", "ts": "2026-09-30T12:00:00+08:00"}) + "\n")
    assert [e["id"] for e in v.events()] == [a["id"], "fromcopy", b["id"]]  # not a monthly file: not read
    assert v.last_event_id() == b["id"]
    late = {"id": "late", "ts": "2026-09-25T12:00:00+08:00", "type": "note"}
    with open(folder / "2026-09 2.jsonl", "a") as f:
        f.write(json.dumps(late) + "\n")
    assert [e["id"] for e in v.events()][-1] == v.last_event_id() == "late"


@pytest.mark.parametrize("seed", range(20))
def test_a_log_without_conflict_copies_is_read_in_the_order_it_was_written(tmp_path, seed):
    """A device clock that steps back must not reorder one device's own log: the state built as events were written
    is the state rebuilt from the log, and the newest event is the last one written."""
    import random
    rng = random.Random(seed)
    v = store.Vault(make_vault(tmp_path))
    written = []
    for month in rng.sample(["2026-09", "2026-10"], rng.randint(1, 2)):
        for _ in range(rng.randint(1, 12)):
            t = datetime.fromisoformat(f"{month}-{rng.randint(10, 20)}T{rng.randint(0, 23):02d}:00:00+08:00")
            written.append((month, v.append_event({"type": "note"}, now=t)["id"]))
    want = [i for m in sorted({m for m, _ in written}) for mm, i in written if mm == m]  # month files, in order
    assert [e["id"] for e in v.events()] == want
    assert v.last_event_id() == want[-1]


def test_a_clock_stepping_back_keeps_the_written_order_and_the_newest_event(tmp_path):
    v = store.Vault(make_vault(tmp_path))
    a = v.append_event({"type": "note"}, now=datetime.fromisoformat("2026-09-20T12:00:00+08:00"))
    b = v.append_event({"type": "note"}, now=datetime.fromisoformat("2026-09-20T11:00:00+08:00"))  # clock went back
    assert [e["id"] for e in v.events()] == [a["id"], b["id"]] and v.last_event_id() == b["id"]


def test_last_event_id_skips_a_tag_on_a_re_marked_answer(tmp_path):
    v = store.Vault(make_vault(tmp_path))
    t = datetime.fromisoformat("2026-09-30T12:00:00+08:00")
    a = v.append_event({"type": "answer", "grade": {"score": 0.0}}, now=t)
    r = v.append_event({"type": "regrade", "target": a["id"], "grade": {"score": 1.0, "correct": True}}, now=t)
    v.append_event({"type": "tag", "target": a["id"], "error": "SLIP"},
                   now=datetime.fromisoformat("2026-10-01T12:00:00+08:00"))
    assert [e["id"] for e in v.events()][-1] == v.last_event_id() == r["id"]


def test_a_re_marked_answer_is_no_longer_a_likely_slip(tmp_path):
    v = store.Vault(make_vault(tmp_path))
    t = datetime.fromisoformat("2026-09-30T12:00:00+08:00")
    a = v.append_event({"type": "answer", "grade": {"score": 0.0}, "slip_likely": True}, now=t)
    v.append_event({"type": "regrade", "target": a["id"], "grade": {"score": 1.0, "correct": True}}, now=t)
    (ans,) = [e for e in v.events() if e["type"] == "answer"]
    assert ans["regraded"] and "slip_likely" not in ans and ans["grade"]["score"] == 1.0


def test_write_text_replaces_a_file_that_is_not_valid_utf8(tmp_path):
    p = tmp_path / "Now.md"
    p.write_bytes("# Now\n€".encode()[:-1])  # a torn multibyte character
    assert store.write_text(p, "fresh") is True
    assert p.read_text(encoding="utf-8") == "fresh"
