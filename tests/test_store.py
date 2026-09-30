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
