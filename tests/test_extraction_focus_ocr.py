"""Focused working pages do not narrow the immutable frozen OCR reader inputs."""
import copy
import json
from pathlib import Path

import pytest

from library_assets import write_asset
from test_extraction import make_pdf
from test_extraction_ocr import prepared as ocr_prepared, sha, write_json


def prepared(tmp_path, monkeypatch):
    ex, _, old_source, folder = ocr_prepared(tmp_path, monkeypatch)
    vault = tmp_path / 'vault'
    vault.mkdir()
    monkeypatch.delenv('STEM_LIBRARY_ROOT')
    monkeypatch.setenv('STEM_TUTOR_VAULT', str(vault))
    monkeypatch.setenv('STEM_LIBRARY_CACHE', str(tmp_path / 'Work/cache'))
    ref = write_asset(vault, 'Library/Courses/9702/Sources/Library/scan.pdf',
                      Path(old_source['path']).read_bytes())
    # Reuse the existing disposable OCR fixture with canonical source identity.
    manifest = json.loads((folder / 'manifest.json').read_text())
    manifest['source_id'] = ref
    for page in range(1, 4):
        path = folder / f'p{page:04d}.json'
        payload = json.loads(path.read_text())
        payload['source_id'] = ref
        write_json(path, payload)
        manifest['pages'][str(page)]['sha256'] = sha(path)
    write_json(folder / 'manifest.json', manifest)
    ex.create('focused-scan', '9702', provider='codex', scope='questions', sources=[ref], pages='2-3')
    ex.inventory('focused-scan')
    ex.enable_ocr('focused-scan', ref)
    state = ex.plan('focused-scan')
    source = state['sources'][0]
    path = ex.candidate_path(state)
    path.parent.mkdir(parents=True)
    (path.parent / 'page3.png').write_bytes((folder / 'p0003.png').read_bytes())
    region = {'source_id': ref, 'source_sha256': source['sha256'], 'page': 3, 'box': [0, 0, 1, 1]}
    path.write_text(json.dumps({'questions': [{
        'id': 'part-a', 'official_qid': '9702_s23_22_q8', 'part': 'a',
        'kind': 'structured', 'complete': False, 'uncertainty': ['OCR unreviewed'],
        'regions': [region], 'mark_scheme_regions': [copy.deepcopy(region)],
        'media': ['page3.png']}], 'diagrams': [], 'source_coverage': [{
            'source_id': ref, 'source_sha256': source['sha256'], 'inspected_pages': [2, 3],
            'no_relevant_content': False, 'reason': ''}]}))
    with ex.state_lock('focused-scan') as current:
        current['jobs']['extract'].update(exit=0, finished='saved', output_sha256=ex.digest(path))
        current['reliability_failures'] = {'1': {'extract': [{'issues': ['saved gate failure']}]}}
    specs = tmp_path / 'specs/9702'
    specs.mkdir(parents=True)
    (specs / 'graph.json').write_text('{"subtopics": [], "kcs": []}')
    monkeypatch.setenv('STEM_LIBRARY_SPECS', str(specs.parent))
    before = ex.load('focused-scan')
    ex.focus('focused-scan', '9702_s23_22_q8', 'focused OCR source repair')
    native = write_asset(vault, 'Library/Courses/9702/Sources/Library/native.pdf',
                         make_pdf(tmp_path / 'native.pdf', ['Original native question and scheme']).read_bytes())
    return ex, before, folder, native


def test_focused_ocr_rebase_verifies_original_frozen_reader_scope(tmp_path, monkeypatch):
    ex, before, _, native = prepared(tmp_path, monkeypatch)
    focused = ex.load('focused-scan')
    assert focused['sources'][0]['selected_page_numbers'] == [3]
    assert 'selected_pages' not in focused['sources'][0]
    assert set(focused['sources'][0]['ocr']['pages']) == {'2', '3'}
    old_candidate = ex.candidate_path(focused)
    old_bytes = old_candidate.read_bytes()
    state = ex.evidence_sources('focused-scan', [native + '=1'], 'Native originals located')
    history = state['source_rebase_history'][0]
    assert history['sources'] == focused['sources']
    assert history['sources'][0]['ocr'] == before['sources'][0]['ocr']
    assert history['sources'][0]['status'] == 'pending_ocr'
    assert old_candidate.read_bytes() == old_bytes
    assert state['reliability_failures'] == before['reliability_failures']
    assert state['sources'][0]['id'] == native


def test_focused_ocr_reads_only_working_pages_after_verifying_all_reader_bytes(tmp_path, monkeypatch):
    ex, _, _, _ = prepared(tmp_path, monkeypatch)
    source = ex.load('focused-scan')['sources'][0]
    result = ex.ocr_text('focused-scan', source['id'])
    assert [row['page'] for row in result['pages']] == [3]
    with pytest.raises(ValueError, match='selected'):
        ex.ocr_text('focused-scan', source['id'], pages='2')


@pytest.mark.parametrize('target', ['p0002.json', 'p0002.png'])
def test_unselected_frozen_ocr_corruption_still_blocks_focused_native_rebase(tmp_path, monkeypatch, target):
    ex, before, folder, native = prepared(tmp_path, monkeypatch)
    path = folder / target
    path.write_bytes(path.read_bytes() + b'changed')
    state_path = ex.job_dir('focused-scan') / 'state.json'
    original_state = state_path.read_bytes()
    with pytest.raises(ValueError, match='OCR page 2 .*hash changed'):
        ex.evidence_sources('focused-scan', [native + '=1'], 'Native originals located')
    assert state_path.read_bytes() == original_state
    assert ex.load('focused-scan')['reliability_failures'] == before['reliability_failures']


@pytest.mark.parametrize('fault', ['snapshot', 'current-binding'])
def test_focused_ocr_cannot_replace_original_reader_provenance(tmp_path, monkeypatch, fault):
    ex, _, _, native = prepared(tmp_path, monkeypatch)
    focused = ex.load('focused-scan')
    if fault == 'snapshot':
        snapshot = Path(focused['focus_history'][0]['state_snapshot'])
        snapshot.write_bytes(snapshot.read_bytes() + b' ')
    else:
        with ex.state_lock('focused-scan') as current:
            current['sources'][0]['ocr']['pages'].pop('2')
    with pytest.raises(ValueError, match='focused OCR'):
        ex.evidence_sources('focused-scan', [native + '=1'], 'Native originals located')


@pytest.mark.parametrize('binding', ['missing', None, {}])
def test_focused_ocr_binding_removal_cannot_bypass_frozen_integrity(tmp_path, monkeypatch, binding):
    ex, before, folder, native = prepared(tmp_path, monkeypatch)
    # Corrupt a frozen page that is outside the focused working scope.
    path = folder / 'p0002.json'
    path.write_bytes(path.read_bytes() + b'changed')
    with ex.state_lock('focused-scan') as current:
        if binding == 'missing':
            current['sources'][0].pop('ocr')
        else:
            current['sources'][0]['ocr'] = binding
    state_path = ex.job_dir('focused-scan') / 'state.json'
    old_state = state_path.read_bytes()
    with pytest.raises(ValueError, match='focused OCR'):
        ex.evidence_sources('focused-scan', [native + '=1'], 'Native originals located')
    assert state_path.read_bytes() == old_state
    assert ex.load('focused-scan')['reliability_failures'] == before['reliability_failures']


def test_supported_native_rebase_passes_frozen_focus_lineage_validation(tmp_path, monkeypatch):
    ex, _, _, native = prepared(tmp_path, monkeypatch)
    state = ex.evidence_sources('focused-scan', [native + '=1'], 'Native originals located')
    assert 'ocr' not in state['sources'][0]
    ex._verify_sources(state)
    assert ex.check('focused-scan')['stage'] == 'pending'
    # Unsupported source inventory edits cannot imitate the supported native revision.
    state['sources'][0]['selected_page_numbers'] = [1, 2]
    with pytest.raises(ValueError, match='focused OCR'):
        ex._verify_sources(state)
