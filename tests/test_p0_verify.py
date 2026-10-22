"""Verifier's regression tests for bug-watch P0s found incomplete on the second look."""
import json
import random
from pathlib import Path
from types import SimpleNamespace

from tutorlib import report


def test_a_scratch_vault_in_temp_never_writes_beside_the_real_planner(tmp_path, monkeypatch):
    """B-062: sandbox.sh strips the planner path, but any /tmp copy of a vault that still names it wrote there."""
    planner = Path.home() / "Library" / "planner-for-test.html"  # stands for the real one, outside any temp folder
    monkeypatch.setattr(Path, "is_file", lambda self: True if self == planner else Path.exists(self))
    writes = []
    monkeypatch.setattr(report, "_write_text", lambda path, text: writes.append(str(path)))
    monkeypatch.setattr(report, "almanac_payload", lambda t: {})
    scratch = SimpleNamespace(vault=SimpleNamespace(root=tmp_path / "mnt" / "STEM Tutor"),
                              packs=SimpleNamespace(plan={"source_path": str(planner)}))
    assert report.almanac_push(scratch) is None and writes == []
    real = SimpleNamespace(vault=SimpleNamespace(root=Path.home() / "Documents" / "STEM Tutor"),
                           packs=SimpleNamespace(plan={"source_path": str(planner)}))
    assert report.almanac_push(real).endswith(".tutor.js") and len(writes) == 1  # the real vault still syncs
