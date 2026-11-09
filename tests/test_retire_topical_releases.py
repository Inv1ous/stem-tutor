"""Retiring superseded topical releases that cite a leak: plan guards, archive move, record-wise rollback."""
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'build'))
import prune_question_leaks as prune
import retire_topical_releases as retire
from tutorlib.asset_library import AssetLibrary, write_asset

LEAK = 'Library/Courses/9702/Questions/Media/Long/9702_x_q1_p01_long_aaaaaaaaaaaa.png'
QUESTION = 'Library/Courses/9702/Questions/Media/Long/9702_x_q1_p02_long_bbbbbbbbbbbb.png'
OLD = 'Library/Shared/Topicals/Releases/vold/'
NEW = 'Library/Shared/Topicals/Releases/vnew/'


@pytest.fixture
def vault(tmp_path):
    vault = tmp_path / 'STEM Tutor'
    vault.mkdir()
    leak = write_asset(vault, LEAK, b'leak-bytes', metadata={'course': '9702', 'kind': 'Questions/Media'})
    write_asset(vault, QUESTION, b'question-bytes', metadata={'course': '9702', 'kind': 'Questions/Media'})
    write_asset(vault, OLD + 'bank.json', json.dumps({'items': [{'id': 'q', 'images': [QUESTION, LEAK]}]}).encode())
    write_asset(vault, OLD + 'report.json', b'{"preparation": {}}')
    write_asset(vault, NEW + 'bank.json', json.dumps({'items': [{'id': 'q', 'images': [QUESTION]}]}).encode())
    (vault / '.tutor/topicals').mkdir(parents=True)
    (vault / '.tutor/topicals/CURRENT').write_text('vnew\n')
    return vault, leak[6:]


def test_retire_makes_leak_unreferenced_and_rollback_restores(vault, tmp_path):
    vault, leak = vault
    plan = retire.build_plan(vault, [leak])
    assert plan['errors'] == [] and plan['units'] == [OLD.rstrip('/')]
    assert {e['path'] for e in plan['retire']} == {OLD + 'bank.json', OLD + 'report.json'}
    assert plan['reference_check']['broken_count'] == 0
    before = (vault / 'Library/catalog.json').read_bytes()
    archive, journal = tmp_path / 'Archive/retired', tmp_path / 'work/journal.json'
    result = retire.apply(plan, journal, archive, tmp_path / 'work/catalog.before.json')
    assert result['status'] == 'complete' and result['retired'] == 2
    assert not (vault / OLD).exists() and (archive / OLD / 'bank.json').is_file()
    library = AssetLibrary(vault)
    assert not prune.citations(library, library.records()).get(leak)
    assert retire.apply(plan, journal, archive, tmp_path / 'work/catalog.before.json')['status'] == 'complete'
    assert retire.rollback(journal)['restored'] == 2
    assert (vault / OLD / 'bank.json').is_file() and not (archive / OLD / 'bank.json').exists()
    assert json.loads((vault / 'Library/catalog.json').read_bytes()) == json.loads(before)


def test_plan_refuses_current_release_and_learner_citations(vault, tmp_path):
    vault, leak = vault
    (vault / '.tutor/topicals/CURRENT').write_text('vold\n')
    assert any('CURRENT' in e for e in retire.build_plan(vault, [leak])['errors'])
    (vault / '.tutor/topicals/CURRENT').write_text('vnew\n')
    (vault / '.tutor/events.jsonl').write_text(json.dumps({'release': 'vold'}) + '\n')
    assert any('learner' in e for e in retire.build_plan(vault, [leak])['errors'])
    plan = retire.build_plan(vault, [leak])
    with pytest.raises(ValueError, match='clean'):
        retire.apply(plan, tmp_path / 'j.json', tmp_path / 'a', tmp_path / 'b.json')
