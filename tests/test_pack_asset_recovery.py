"""A failed verified asset load is retriable without rebuilding the pack reader."""
import copy
import json
import random

import pytest

from fixtures import make_vault
from test_topicals import KC, OTHER, bank_vault, item, publish
from tutorlib import asset_library, model, packs, store

CHAPTER = "9702-2.1"
CANONICAL = "Library/Courses/9702/Diagrams/recovery.svg"
ALIAS = "Assets/9702/recovery.svg"


@pytest.mark.parametrize("fault", ["unavailable", "hash"])
@pytest.mark.parametrize("entry", ["pack", "items_for"])
def test_registered_pack_asset_can_recover_on_the_same_reader(tmp_path, monkeypatch, fault, entry):
    root = make_vault(tmp_path)
    (root / ".tutor/packs/v1/papers.json").write_text('{"papers": []}')
    asset_library.write_asset(root, CANONICAL, b"<svg>Disposable registered diagram</svg>", aliases=[ALIAS])
    source = root / ".tutor/packs/v1/specs/9702/packs/9702-2.1.json"
    content = json.loads(source.read_text())
    content["items"][0]["images"] = [ALIAS]
    source.write_text(json.dumps(content))
    before = {path: path.read_bytes() for path in (source, root / CANONICAL, root / "Library/catalog.json")}
    reader = packs.Packs(store.Vault(root))
    read = lambda: reader.pack(CHAPTER) if entry == "pack" else reader.items_for("9702-2.1.1")
    attempts = []
    original_open, original_read = asset_library.os.open, asset_library._read_regular

    def unavailable(path, *args, **kwargs):
        if path == "recovery.svg":
            attempts.append(path)
            raise PermissionError("Transient registered diagram read failure")
        return original_open(path, *args, **kwargs)

    def wrong_bytes(vault, relative, *args, **kwargs):
        if relative == CANONICAL:
            attempts.append(relative)
            return b"Transient wrong bytes"
        return original_read(vault, relative, *args, **kwargs)

    with monkeypatch.context() as patch:
        if fault == "unavailable":
            patch.setattr(asset_library.os, "open", unavailable)
        else:
            patch.setattr(asset_library, "_read_regular", wrong_bytes)
        assert not read()
        assert not read()
        assert len(attempts) <= 2  # no retry loop inside one explicit caller request
        assert reader.damaged == [source.relative_to(root).as_posix()]

    restored = read()
    assert restored
    assert len(attempts) == 2
    loaded = reader.pack(CHAPTER)
    assert loaded["items"][0]["images"] == [CANONICAL]
    assert not reader.damaged
    with monkeypatch.context() as patch:
        patch.setattr(asset_library.os, "open", unavailable)
        assert reader.pack(CHAPTER) is loaded  # successful immutable load remains cached
    assert len(attempts) == 2
    assert all(path.read_bytes() == data for path, data in before.items())


@pytest.mark.parametrize("bank_active", [False, True])
def test_recovered_pack_refreshes_derived_cross_chapter_aliases(tmp_path, monkeypatch, bank_active):
    root = bank_vault(tmp_path)
    (root / ".tutor/packs/v1/papers.json").write_text('{"papers": []}')
    asset_library.write_asset(root, CANONICAL, b"<svg>Disposable registered diagram</svg>", aliases=[ALIAS])
    source = root / ".tutor/packs/v1/specs/9702/packs/9702-2.1.json"
    content = json.loads(source.read_text())
    original = content["items"][0]
    original.update(source={"type": "past", "qid": "9702_s23_12_q99"}, images=[ALIAS])
    source.write_text(json.dumps(content))
    alias = copy.deepcopy(original)
    alias.update(id="other-chapter-alias", kcs=[OTHER + ".1"])
    alias.pop("images")
    other = source.with_name(OTHER + ".json")
    other.write_text(json.dumps({**content, "subtopic": OTHER, "items": [alias]}))
    if bank_active:
        publish(root, [item()])
    reader = packs.Packs(store.Vault(root))
    real_read = asset_library._read_regular

    def unavailable(vault, relative, *args, **kwargs):
        if relative == CANONICAL:
            raise ValueError("Registered diagram temporarily unavailable")
        return real_read(vault, relative, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(asset_library, "_read_regular", unavailable)
        assert original["id"] not in reader.aliases_for(alias)
    assert reader.pack(CHAPTER)

    assert {original["id"], alias["id"]} <= reader.aliases_for(alias)
    assert reader.items_for(KC)


def test_active_bank_items_route_recovers_without_an_explicit_pack_load(tmp_path, monkeypatch):
    root = bank_vault(tmp_path)
    (root / ".tutor/packs/v1/papers.json").write_text('{"papers": []}')
    asset_library.write_asset(root, CANONICAL, b"<svg>Disposable registered diagram</svg>", aliases=[ALIAS])
    source = root / ".tutor/packs/v1/specs/9702/packs/9702-2.1.json"
    content = json.loads(source.read_text())
    content["items"][0]["images"] = [ALIAS]
    source.write_text(json.dumps(content))
    publish(root, [item()])
    before = {path: path.read_bytes() for path in (source, root / CANONICAL, root / "Library/catalog.json")}
    reader = packs.Packs(store.Vault(root))
    real_read = asset_library._read_regular
    attempts = []

    def unavailable(vault, relative, *args, **kwargs):
        if relative == CANONICAL:
            attempts.append(relative)
            raise ValueError("Registered diagram temporarily unavailable")
        return real_read(vault, relative, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(asset_library, "_read_regular", unavailable)
        assert content["items"][0]["id"] not in {row["id"] for row in reader.items_for(KC)}
        reader.items_for(KC)
        assert reader.select_item(KC, model.new_state(), .8, random.Random(0))
        assert len(attempts) == 3
        reader.aliases_for(item())  # nested alias lookups must not amplify retries per candidate
        assert len(attempts) == 3
    # The exact same public entry must retry its missing chapter, rather than
    # requiring the caller to know to invalidate a different cache first.
    assert content["items"][0]["id"] in {row["id"] for row in reader.items_for(KC)}
    assert len(attempts) == 3
    assert not reader.damaged
    assert all(path.read_bytes() == data for path, data in before.items())
