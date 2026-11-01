"""A transient pointer read failure must not poison an already loaded bank."""
import json

import pytest

from test_topicals import KC, TARGET, bank_vault, item, publish
from tutorlib import asset_library, packs, store


def test_same_topical_release_recovers_after_pointer_decode_failure(tmp_path):
    root = bank_vault(tmp_path)
    publish(root, [item()])
    content = packs.Packs(store.Vault(root))
    before = content.topical_items(TARGET)
    assert before and any(row['id'] == 'topical-one' for row in content.items_for(KC))
    pointer = root / '.tutor/topicals/CURRENT'
    original = pointer.read_bytes()
    bank = root / '.tutor/topicals/one/bank.json'
    bank_bytes = bank.read_bytes()

    pointer.write_bytes(b'\xff')
    assert content.topical_items(TARGET) == []
    assert content.topical_errors
    # Sync restores the original pointer; the immutable release is untouched.
    pointer.write_bytes(original)
    assert content.topical_items(TARGET) == before
    assert not content.topical_errors
    assert bank.read_bytes() == bank_bytes


@pytest.mark.parametrize("failure", ["unavailable", "digest_mismatch"])
def test_canonical_bank_load_failure_retries_and_keeps_successful_caching(tmp_path, monkeypatch, failure):
    root = bank_vault(tmp_path)
    (root / ".tutor/packs/v1/papers.json").write_text('{"papers": []}')
    content = packs.Packs(store.Vault(root))
    canonical = "Library/Shared/Topicals/Releases/one/bank.json"
    data = json.dumps({"format_version": 1, "syllabus_versions": {"9702": "2025-2027"},
                       "items": [item()]}).encode()
    asset_library.write_asset(root, canonical, data)
    pointer = root / ".tutor/topicals/CURRENT"
    pointer.parent.mkdir(parents=True)
    pointer.write_text("one")
    catalog = root / "Library/catalog.json"
    before_catalog = catalog.read_bytes()
    real_open = asset_library.os.open
    real_read = asset_library._read_regular

    def unavailable(path, *args, **kwargs):
        if path == "bank.json":
            raise OSError("bank is temporarily unavailable")
        return real_open(path, *args, **kwargs)

    def mismatched(vault, reference, *args, **kwargs):
        return b"unverified bytes" if reference == canonical else real_read(vault, reference, *args, **kwargs)

    with monkeypatch.context() as patch:
        if failure == "unavailable":
            patch.setattr(asset_library.os, "open", unavailable)
        else:
            patch.setattr(asset_library, "_read_regular", mismatched)
        assert content.topical_items(TARGET) == []
        assert content.topical_errors
        if failure == "digest_mismatch":
            assert "digest mismatch" in content.topical_errors[0]

    assert [question["id"] for question in content.topical_items(TARGET)] == ["topical-one"]
    assert not content.topical_errors
    with monkeypatch.context() as patch:
        # A successful immutable release remains cached; an unavailable file is
        # not consulted again until CURRENT selects another release.
        patch.setattr(asset_library.os, "open", unavailable)
        assert [question["id"] for question in content.topical_items(TARGET)] == ["topical-one"]
        assert not content.topical_errors
    assert (root / canonical).read_bytes() == data
    assert catalog.read_bytes() == before_catalog
    assert pointer.read_text() == "one"
