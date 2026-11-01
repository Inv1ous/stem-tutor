"""Pre-pass baselines: a new pass snapshots before it edits, superseded snapshots are kept, and a baseline rebuilt
from git HEAD only accepts the drafter's additions. Runs in a temporary git repository, never the real one."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "refine"))
import baseline  # noqa: E402

REL = "build/out/packs/9701/9701-9.9.json"
NOTE_REL = "build/out/notes/Subjects/9701/9.9 Test.md"
PACK = {"subtopic": "9701-9.9", "note": "Subjects/9701/9.9 Test.md", "spec": "9701",
        "items": [{"id": "9701-9.9-i01", "stem": "Original question."}],
        "misconceptions": [{"id": "m1", "kc": "9701-9.9.1", "statement": "Original."}],
        "teach": {"9701-9.9.1": {"motivate": "Why.", "establish": "The idea."}}}
NOTE = "# Test\n\nOriginal line.\n\nAnother line.\n"


@pytest.fixture
def repo(tmp_path, monkeypatch):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / REL).parent.mkdir(parents=True)
    (tmp_path / REL).write_text(json.dumps(PACK, indent=1))
    (tmp_path / NOTE_REL).parent.mkdir(parents=True)
    (tmp_path / NOTE_REL).write_text(NOTE)
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "base"], cwd=tmp_path, check=True)
    monkeypatch.setattr(baseline, "ROOT", tmp_path)
    return tmp_path


def _drafted(repo, mutate=None):
    pack = json.loads(PACK and json.dumps(PACK))
    pack["guided_forms"] = {"9701-9.9.1": ["Form A"]}
    pack["misconceptions"].append({"id": "m2", "kc": "9701-9.9.1", "statement": "New idea."})
    pack["teach"]["9701-9.9.1"].update({"plain_words": "Plain.", "terms": [{"term": "t"}],
                                        "misconceptions": [{"id": "m2", "idea": "New idea."}]})
    if mutate:
        mutate(pack)
    (repo / REL).write_text(json.dumps(pack, indent=1))
    (repo / NOTE_REL).write_text(NOTE.replace("Another line.\n", "Another line.\n\n![[Assets/9701/x.png]]\n*Figure: x (source: y, p.1)*\n"))


def test_a_new_pass_snapshots_before_edits_and_keeps_the_superseded_snapshot(repo):
    snap = repo / "build/work/refine/9701-9.9.snapshot.json"
    snap.parent.mkdir(parents=True)
    old = {"pass": 1, "pack": {"stale": True}, "note": ""}
    snap.write_text(json.dumps(old))
    baseline.begin_pass("9701-9.9", snap, 2, REL, repo / REL, repo / NOTE_REL)
    new = json.loads(snap.read_text())
    assert new["pass"] == 2 and new["pack"]["subtopic"] == "9701-9.9"  # the state before this pass's edits
    kept = list((snap.parent / "history" / "9701-9.9").glob("snapshot.*.json"))
    assert len(kept) == 1 and json.loads(kept[0].read_text()) == old  # the old baseline is not lost
    log = (snap.parent / "history" / "9701-9.9" / "log.jsonl").read_text().splitlines()
    assert json.loads(log[-1])["event"] == "snapshot" and json.loads(log[-1])["pack_matches_head"] is True


def test_drafter_additions_are_removed_and_the_pre_draft_state_is_rebuilt_from_head(repo):
    _drafted(repo)
    snap = repo / "build/work/refine/9701-9.9.snapshot.json"
    result = baseline.reconstruct("9701-9.9", REL, set(), repo / REL, repo / NOTE_REL, snap, 3, "test")
    assert result["pack"] == PACK and result["note"] == NOTE  # identical to the committed chapter
    assert result["provenance"]["pack_matches_head"] is True


def test_a_change_made_outside_the_drafting_is_refused(repo):
    _drafted(repo, mutate=lambda p: p["items"][0].update(stem="Edited by hand."))
    with pytest.raises(ValueError, match="differs from git HEAD"):
        baseline.reconstruct("9701-9.9", REL, set(), repo / REL, repo / NOTE_REL,
                             repo / "build/work/refine/9701-9.9.snapshot.json", 3, "test")


def test_an_appended_misconception_no_card_refers_to_is_refused(repo):
    _drafted(repo, mutate=lambda p: p["misconceptions"].append({"id": "m9", "kc": "9701-9.9.1", "statement": "Stray."}))
    with pytest.raises(ValueError, match="not referenced by any drafted card"):
        baseline.reconstruct("9701-9.9", REL, set(), repo / REL, repo / NOTE_REL,
                             repo / "build/work/refine/9701-9.9.snapshot.json", 3, "test")


def test_a_note_line_removed_or_edited_is_refused(repo):
    _drafted(repo)
    (repo / NOTE_REL).write_text(NOTE.replace("Original line.", "Edited line."))
    with pytest.raises(ValueError, match="note has"):
        baseline.reconstruct("9701-9.9", REL, set(), repo / REL, repo / NOTE_REL,
                             repo / "build/work/refine/9701-9.9.snapshot.json", 3, "test")
