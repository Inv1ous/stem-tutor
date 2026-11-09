"""`bin/extract leaks`: plan by default, counts per class, AI review file, deletion only with --apply."""
import json
from pathlib import Path

import pytest
from test_extraction import extraction
from test_prune_question_leaks import MCQ, blank, needs_ocr, source, vault, G_STRIP  # noqa: F401
import library_assets


def cli(ex, capsys, *argv):
    assert ex.main(list(argv)) == 0
    return json.loads(capsys.readouterr().out)


def test_job_plan_counts_and_review_file(tmp_path, monkeypatch, capsys):
    ex = extraction()
    monkeypatch.setenv('STEM_EXTRACT_ROOT', str(tmp_path / 'Work'))
    cand = tmp_path / 'cand'
    cand.mkdir()
    (cand / 'tiny.png').write_bytes(blank(40, 12))
    (cand / 'q.png').write_bytes(library_assets.read_bytes(MCQ))
    (cand / 'candidate.json').write_text(json.dumps({'questions': [{'id': 'a', 'media': ['tiny.png', 'q.png']}]}))
    job = ex.job_dir('leakjob')
    job.mkdir(parents=True)
    (job / 'state.json').write_text(json.dumps({'candidate': str(cand / 'candidate.json'), 'course': '9701'}))
    result = cli(ex, capsys, 'leaks', 'leakjob')
    assert result['counts']['review'] >= 1 and sum(result['counts'].values()) == 2
    review = json.loads((job / 'ai-review.json').read_text())
    assert review['items'][0]['id'] == 'tiny.png' and review['items'][0]['class'] == 'SMALL_REVIEW'
    assert (cand / 'tiny.png').exists()
    assert ex.main(['leaks', 'leakjob', '--apply']) == 1  # job candidates are never pruned here


def test_vault_plan_does_not_delete_until_apply(vault, tmp_path, capsys):
    ex = extraction()
    out = tmp_path / 'out'
    before = sorted(p.relative_to(vault).as_posix() for p in vault.rglob('*') if p.is_file())
    result = cli(ex, capsys, 'leaks', '--vault', str(vault), '--out', str(out))
    assert set(result['counts']) == {'delete', 'review', 'keep'} and not result['applied']
    assert json.loads((out / 'ai-review.json').read_text())['format_version'] == 1
    assert before == sorted(p.relative_to(vault).as_posix() for p in vault.rglob('*') if p.is_file())
    if gate_ready():
        applied = cli(ex, capsys, 'leaks', '--vault', str(vault), '--out', str(out), '--apply')
        assert applied['applied'] and (out / 'prune-journal.json').exists()


def gate_ready():
    import question_leak_gate
    return question_leak_gate._binary() is not None
