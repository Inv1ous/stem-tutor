"""The foundry and refine make sure a worker used what it was given: the library and the web."""
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO / "foundry"), str(REPO / "build")]
import capabilities  # noqa: E402
import evidence  # noqa: E402

CLAUDE_USED = ('{"type":"assistant","message":{"content":[{"type":"tool_use","name":"WebSearch","input":{"query":"x"}},'
               '{"type":"tool_use","name":"Bash","input":{"command":".venv/bin/python build/library.py for 9702-5.1"}}]}}\n')
CLAUDE_SKIPPED = '{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Read","input":{"file_path":"x"}}]}}\n'
CODEX_USED = ("exec\n/bin/zsh -lc '.venv/bin/python build/library.py for 9702-10.3' in /repo\nweb search: beta plus decay\n")
CODEX_SKIPPED = "exec\n/bin/zsh -lc 'cat refine/roles/scout.md' in /repo\nThe prompt mentions build/library.py but nothing ran it.\n"
CFG = {"web": ["drafter", "scout", "refiner"]}


def test_real_tool_use_is_read_from_both_kinds_of_log():
    assert evidence.from_log(CLAUDE_USED) == {"web": 1, "library": 1}
    assert evidence.from_log(CLAUDE_SKIPPED) == {"web": 0, "library": 0}
    assert evidence.from_log(CODEX_USED) == {"web": 1, "library": 1}
    assert evidence.from_log(CODEX_SKIPPED) == {"web": 0, "library": 0}  # a mention in the prompt is not a use


@pytest.fixture
def on(monkeypatch):
    monkeypatch.delenv("FOUNDRY_EVIDENCE", raising=False)
    monkeypatch.setattr(evidence, "library_hits", lambda sub: 7)


def test_a_scout_or_drafter_that_skipped_the_library_or_the_web_has_not_finished(on, tmp_path):
    log = tmp_path / "w.log"
    log.write_text(CLAUDE_SKIPPED)
    gaps = evidence.missing("scout", "9702-5.1", CFG, log)
    assert len(gaps) == 2 and "library has 7 pages" in gaps[0] and "search the web" in gaps[1] or "web" in gaps[1]
    log.write_text(CODEX_USED)
    assert evidence.missing("scout", "9702-5.1", CFG, log) == []
    assert evidence.missing("drafter", "9702-5.1", CFG, tmp_path / "gone.log") == []  # no log: nothing to judge


def test_other_roles_are_not_held_to_it_and_an_empty_library_asks_for_nothing(on, tmp_path, monkeypatch):
    log = tmp_path / "w.log"
    log.write_text(CLAUDE_SKIPPED)
    for role in ("refiner", "fixer", "solver", "checker", "tiebreak", "adjudicator"):
        assert evidence.missing(role, "9702-5.1", CFG, log) == []
    monkeypatch.setattr(evidence, "library_hits", lambda sub: 0)  # the library has nothing for this chapter
    assert evidence.missing("scout", "9702-5.1", {"web": []}, log) == []  # and no web allowed for the role
    monkeypatch.setenv("FOUNDRY_EVIDENCE", "0")
    assert evidence.missing("scout", "9702-5.1", CFG, log) == []


def test_the_prompt_says_what_the_worker_has(monkeypatch):
    monkeypatch.setattr(evidence, "material", lambda: (673, 5))
    lines = evidence.prompt_lines("scout", "9702-5.1", CFG)
    assert "673 PDFs in 5 folders" in lines[0] and "you must" in lines[0] and "web" in lines[1]
    assert "you must" not in evidence.prompt_lines("refiner", "9702-5.1", CFG)[0]  # it may use them, it is not held to it
    assert evidence.prompt_lines("solver", "9702-5.1", CFG) == []  # blind roles are told nothing of sources
    monkeypatch.setattr(evidence, "material", lambda: (0, 0))
    assert evidence.prompt_lines("scout", "9702-5.1", {"web": []}) == []


def test_the_bundle_lists_the_librarys_pages_for_the_chapter(monkeypatch):
    import bundle
    import library
    monkeypatch.setattr(library, "hits_for", lambda sub: [("9702-5.1.1", "Work done", [("a/b.pdf", 3, "work done")]), ("9702-5.1.2", "None", [])])
    text = "\n".join(bundle._library_lines("9702-5.1"))
    assert "Library hits" in text and "a/b.pdf p.3" in text and "9702-5.1.2" not in text
    monkeypatch.setattr(library, "hits_for", lambda sub: [])
    assert bundle._library_lines("9702-5.1") == []  # an empty library leaves the section out


def test_doctor_lists_what_is_there_and_preflight_refuses_only_for_a_hard_gap(monkeypatch):
    rows = capabilities.check()
    assert any("poppler" in r[1] for r in rows) and any("matplotlib" in r[1] for r in rows)
    text, ok = capabilities.report([(True, "a", "", "hard"), (False, "b", "fix b", "soft")])
    assert ok and "no  b   → fix b" in text
    text, ok = capabilities.report([(False, "needed", "install it", "hard")])
    assert not ok and text.startswith("NO  needed")
    monkeypatch.delenv("FOUNDRY_PREFLIGHT", raising=False)
    monkeypatch.setattr(capabilities, "check", lambda *a, **k: [(False, "needed", "install it", "hard")])
    assert "not starting workers" in capabilities.preflight() and "needed" in capabilities.preflight()
    monkeypatch.setenv("FOUNDRY_PREFLIGHT", "0")
    assert capabilities.preflight() is None
