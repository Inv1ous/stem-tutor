"""Reviewed corrections in the refine gates: a change to what was there is accepted only when it was proposed, supported by
a cited PDF page and reviewed against this exact candidate. Nothing else that was lost is excused."""
import json
from pathlib import Path

import pytest

from test_refine import NOTE, SUB, REPO, rf  # noqa: F401  (the scratch build tree and its fake workers)
from library_assets import copy_to_vault

PDF = "sources/papers/ial/WMA12/WMA12_2019_Jun_qp.pdf"


def _setup(rf, monkeypatch):
    vault = rf.ROOT / 'STEM Tutor'
    vault.mkdir(exist_ok=True)
    source = copy_to_vault(PDF, vault)
    monkeypatch.setenv('STEM_TUTOR_VAULT', str(vault))
    before = rf.take_snapshot(SUB, 1)
    pack = json.loads(rf.pack_path(SUB).read_text())
    old = pack["outline"]
    new = old.replace("Uniform acceleration", "Constant acceleration")
    assert new != old
    proposal = {"corrections": [{"selector": ["outline"], "old": "Uniform acceleration", "new": "Constant acceleration",
                                 "reason": "the mark scheme says constant"}],
                "evidence": [{"source": source.relative_to(vault).as_posix(), "pdf_page": 1,
                              "question": "1", "finding": "uses the word constant"}]}
    rf.corrections_file(SUB).write_text(json.dumps(proposal))
    pack["outline"] = new
    rf.pack_path(SUB).write_text(json.dumps(pack))
    return before, pack


def _gate_loss(rf):
    g = rf.gates(SUB)
    return g.get("no_loss", 0), g.get("corrected", 0)


def test_a_proposed_change_without_a_review_still_fails(rf, monkeypatch):
    _setup(rf, monkeypatch)
    lost, corrected = _gate_loss(rf)
    assert lost >= 2 and corrected == 0  # the change itself, and the proposal that was never reviewed
    assert "proposed corrections not accepted" in " ".join(rf.gates(SUB)["first"])


def test_a_reviewed_correction_is_accepted_and_counted_and_the_snapshot_is_untouched(rf, monkeypatch):
    before, _ = _setup(rf, monkeypatch)
    rf.bind_correction_review(SUB, "second reader", "matches the source")
    assert _gate_loss(rf) == (0, 1)
    assert rf.snapshot(SUB)["pack"] == before["pack"]  # the original is still what the gate compares with


def test_a_loss_the_proposal_does_not_cover_still_fails_beside_a_reviewed_correction(rf, monkeypatch):
    _, pack = _setup(rf, monkeypatch)
    pack["items"][0]["stem"] = "A different question altogether."
    rf.pack_path(SUB).write_text(json.dumps(pack))
    rf.bind_correction_review(SUB, "second reader", "matches the source")  # reviewed with the extra change present
    lost, corrected = _gate_loss(rf)
    assert lost >= 1 and corrected == 1
    assert "stem" in " ".join(rf.gates(SUB)["first"])


def test_a_review_goes_stale_when_the_candidate_changes_afterwards(rf, monkeypatch):
    _, pack = _setup(rf, monkeypatch)
    rf.bind_correction_review(SUB, "second reader", "matches the source")
    pack["outline"] += " More."
    rf.pack_path(SUB).write_text(json.dumps(pack))
    lost, corrected = _gate_loss(rf)
    assert lost >= 1 and corrected == 0


def test_a_replacement_that_is_not_in_the_candidate_is_not_accepted(rf, monkeypatch):
    before, pack = _setup(rf, monkeypatch)
    pack["outline"] = before["pack"]["outline"]  # the corrected text was never written
    rf.pack_path(SUB).write_text(json.dumps(pack))
    rf.bind_correction_review(SUB, "second reader", "matches the source")
    lost, corrected = _gate_loss(rf)
    assert corrected == 0
