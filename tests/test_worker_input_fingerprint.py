"""Worker input admission hashes the same verified bytes that JSON validation reads."""
import copy
import json

import pytest

from test_worker_library_ownership import library_case
from tutor_workers import reliability
from tutorlib.asset_library import AssetLibrary


@pytest.mark.parametrize("fault", ["resource", "missing_catalog", "damaged_catalog"])
def test_public_launch_preflight_refuses_unverified_library_case_alias(tmp_path, fault):
    canonical, alternate = library_case(tmp_path)
    if not alternate.exists():
        alternate.parent.mkdir(parents=True)
        alternate.write_text('{"ordinary_work":true}')
        assert reliability.launch_problem({"jobs": {}}, "drafter", [alternate]) is None
        return
    catalog = canonical.parents[2] / "catalog.json"
    if fault == "resource":
        canonical.write_text('{"tampered":true}')
    elif fault == "missing_catalog":
        catalog.unlink()
    else:
        catalog.write_text('{"invalid":true}')
    state = {"pass": 1, "jobs": {}}
    before = copy.deepcopy(state)
    content = canonical.read_bytes()
    catalog_bytes = catalog.read_bytes() if catalog.exists() else None

    problem = reliability.launch_problem(state, "drafter", [alternate])

    assert problem and "input preflight" in problem
    assert state == before and canonical.read_bytes() == content
    assert (catalog.read_bytes() if catalog.exists() else None) == catalog_bytes


def test_healthy_fingerprint_preserves_logical_paths_raw_bytes_and_json_gate(tmp_path):
    source = tmp_path / "working.json"
    source.write_bytes(b'{"value":1}\r\n')
    alias = tmp_path / "working-alias.json"
    alias.symlink_to(source)
    state = {"pass": 3, "jobs": {}}
    before = copy.deepcopy(state)
    original = source.read_bytes()
    first = reliability.fingerprint(state, "fixer", [source])
    assert reliability.fingerprint(state, "fixer", [source]) == first
    assert reliability.fingerprint(state, "fixer", [alias]) != first
    assert reliability.launch_problem(state, "fixer", [source]) is None
    assert source.read_bytes() == original and state == before
    source.write_text(json.dumps({"value": 1}))
    assert reliability.fingerprint(state, "fixer", [source]) != first
    source.write_text("not JSON")
    assert "input preflight" in reliability.launch_problem(state, "fixer", [source])
    assert state == before


def test_fingerprint_uses_the_verified_snapshot_when_file_changes_after_read(tmp_path, monkeypatch):
    canonical, _ = library_case(tmp_path)
    expected = reliability.fingerprint({"pass": 1}, "drafter", [canonical])
    original_read = AssetLibrary.read

    def mutate_after_read(self, reference, **kwargs):
        payload = original_read(self, reference, **kwargs)
        canonical.write_text('{"changed_after_read":true}')
        return payload

    with monkeypatch.context() as patch:
        patch.setattr(AssetLibrary, "read", mutate_after_read)
        assert reliability.fingerprint({"pass": 1}, "drafter", [canonical]) == expected
    assert reliability.launch_problem({"jobs": {}}, "drafter", [canonical])
