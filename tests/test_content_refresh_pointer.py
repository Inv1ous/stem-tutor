"""Transient CURRENT read failures must not disable already loaded content."""
import copy
import json
from pathlib import Path

import pytest

from fixtures import GRAPH, PACK, make_vault
from test_v110 import T0, _publish_new_version
from tutorlib import session, store


@pytest.mark.parametrize("damage", ["missing", "unreadable", "utf8"])
def test_refresh_keeps_loaded_release_then_retries_pointer_read(tmp_path, monkeypatch, damage):
    root = make_vault(tmp_path)
    graph = copy.deepcopy(GRAPH)
    graph["subtopics"].append({"id": "9702-2.2", "title": "Forces", "topic": "9702-2"})
    (root / ".tutor/packs/v1/specs/9702/graph.json").write_text(json.dumps(graph))
    tutor = session.Tutor(store.Vault(root), now=lambda: T0)
    loaded = tutor.packs
    cached = loaded.pack("9702-2.1")
    pointer = loaded.pointer_base / "CURRENT"
    original = pointer.read_bytes()
    real_read = Path.read_text
    blocked = [damage == "unreadable"]

    def read(path, *args, **kwargs):
        if path == pointer and blocked[0]:
            raise OSError("CURRENT is temporarily unavailable")
        return real_read(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", read)
    if damage == "missing":
        pointer.rename(pointer.with_name("CURRENT.saved"))
    elif damage == "utf8":
        pointer.write_bytes(b"\xff")

    assert tutor.refresh_content() == []
    assert tutor.packs is loaded and tutor.packs.pack("9702-2.1") is cached

    blocked[0] = False
    pointer.write_bytes(original)
    _publish_new_version(root, {**copy.deepcopy(PACK), "subtopic": "9702-2.2", "items": [], "worked": []})
    assert tutor.refresh_content() == ["Forces"]
    assert tutor.packs.root.name == "v2"
    assert tutor.state == tutor._fold()


def test_pointer_read_failure_during_new_pack_load_keeps_the_old_release(tmp_path, monkeypatch):
    root = make_vault(tmp_path)
    tutor = session.Tutor(store.Vault(root), now=lambda: T0)
    loaded = tutor.packs
    cached = loaded.pack("9702-2.1")
    _publish_new_version(root)
    pointer = loaded.pointer_base / "CURRENT"
    real_read = Path.read_text
    reads = []

    def read(path, *args, **kwargs):
        if path == pointer:
            reads.append(path)
            if len(reads) == 2:
                raise OSError("CURRENT changed during refresh")
        return real_read(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", read)
    assert tutor.refresh_content() == []
    assert tutor.packs is loaded and loaded.pack("9702-2.1") is cached
    assert tutor.refresh_content() == []  # Same chapters, with a successfully loaded newer release.
    assert tutor.packs.root.name == "v2"
