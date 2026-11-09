"""Explicit missing historical MS staging never certifies current scheme evidence."""
import copy
import json
import os
from pathlib import Path

import pytest
from PIL import Image
from library_assets import write_asset
from test_extraction import make_pdf
from test_extraction_source_selection import prepared as source_job


def prepared(tmp_path, monkeypatch, *, fault=None):
    ex, vault, _, _, ref = source_job(tmp_path, monkeypatch)
    graph = tmp_path / 'specs/9702/graph.json'; graph.parent.mkdir(parents=True)
    graph.write_text(json.dumps({'subtopics': [{'id': '9702-1.1'}], 'kcs': [
        {'id': '9702-1.1.1', 'subtopic': '9702-1.1'}]}))
    monkeypatch.setenv('STEM_LIBRARY_SPECS', str(graph.parent.parent))
    ex.create('missing-ms', '9702', provider='codex', scope='questions', sources=[ref])
    ex.inventory('missing-ms'); state = ex.plan('missing-ms'); source = state['sources'][0]
    path = ex.candidate_path(state); path.parent.mkdir(parents=True)
    Image.new('RGB', (20, 20), 'red').save(path.parent / 'question.png')
    region = {'source_id': ref, 'source_sha256': source['sha256'], 'page': 1, 'box': [0, 0, 1, 1]}
    records = [{'id': 'q5-' + part, 'official_qid': '9702_s25_22_q5', 'part': part,
        'kind': 'structured', 'complete': False, 'uncertainty': ['Official scheme unavailable in original selected pages'],
        'answer': None, 'regions': [copy.deepcopy(region)], 'mark_scheme_regions': [],
        'media': ['question.png'], 'syllabus': ['9702-1.1'], 'kcs': ['9702-1.1.1'], 'prerequisites': []}
        for part in ('a', 'b.i', 'b.ii', 'b.iii')]
    if fault == 'none':
        records[0]['mark_scheme_regions'] = None
    elif fault == 'missing-key':
        records[0].pop('mark_scheme_regions')
    elif fault == 'bad-hash':
        records[0]['mark_scheme_regions'] = [{**region, 'source_sha256': '0' * 64}]
    elif fault == 'bad-page':
        records[0]['mark_scheme_regions'] = [{**region, 'page': 2}]
    elif fault == 'bad-question-region':
        records[0]['regions'] = []
    data = {'questions': records, 'diagrams': [], 'source_coverage': [{
        'source_id': ref, 'source_sha256': source['sha256'], 'inspected_pages': [1], 'no_relevant_content': False, 'reason': ''}]}
    path.write_text(json.dumps(data))
    with ex.state_lock('missing-ms') as current:
        current['jobs']['extract'].update(exit=0, finished='saved maker', output_sha256=ex.digest(path))
        current['reliability_failures'] = {'1': {'extract': [{'issues': ['old whole-range gate failure']}]}}
    refs = []
    for name, pages in [('native-qp', ['Cover', 'Question 5']), ('native-ms', ['Cover', 'Official scheme 5'])]:
        refs.append(write_asset(vault, f'Library/Courses/9702/Sources/Library/{name}.pdf',
                                make_pdf(tmp_path / (name + '.pdf'), pages).read_bytes()))
    return ex, vault, path, data, refs


def test_missing_scheme_opt_in_stages_native_repair_and_preserves_historical_absence(tmp_path, monkeypatch):
    ex, _, original, data, refs = prepared(tmp_path, monkeypatch)
    original_bytes = original.read_bytes(); old_state = (ex.job_dir('missing-ms') / 'state.json').read_bytes()
    with pytest.raises(ValueError, match='mark_scheme_regions'):
        ex.focus('missing-ms', '9702_s25_22_q5', 'Default remains strict')
    state = ex.focus('missing-ms', '9702_s25_22_q5', 'Acquire missing official MS', stage_missing_scheme=True)
    assert original.read_bytes() == original_bytes
    assert Path(state['focus_history'][0]['state_snapshot']).read_bytes() == old_state
    scope = state['selected_item_scope']
    assert scope['missing_historical_mark_scheme_record_ids'] == ['q5-a', 'q5-b.i', 'q5-b.ii', 'q5-b.iii']
    focused = json.loads(ex.candidate_path(state).read_text())
    assert focused['questions'] == data['questions']
    assert ex._regions(focused['questions'][0], {s['id']: s for s in state['sources']}, 'mark_scheme_regions')
    state = ex.evidence_sources('missing-ms', [refs[0] + '=1-2', refs[1] + '=1-2'], 'Exact native official sources')
    candidate = json.loads(ex.candidate_path(state).read_text())
    for old, row in zip(data['questions'], candidate['questions']):
        assert row['mark_scheme_regions'] == [] and row['complete'] is False and row['answer'] is None
        assert row['uncertainty'] == old['uncertainty']
        assert row['source_occurrences'][-1]['mark_scheme_regions'] == []
        assert row['source_occurrences'][-1]['regions'] == old['regions']
    # Historical page inspection is retained, never transferred to the new native PDFs.
    assert candidate['source_coverage'] == data['source_coverage']
    checked = ex.check('missing-ms')
    assert checked['stage'] == 'pending' and any('mark_scheme_regions must contain' in p for p in checked['problems'])
    assert len(checked['reliability_failures']['1']['extract']) == 1
    with pytest.raises(ValueError, match='review|validation'):
        ex.register('missing-ms')
    with pytest.raises(ValueError, match='review|registration'):
        ex.publish('missing-ms', tmp_path / 'no-batch')
    assert original.read_bytes() == original_bytes


@pytest.mark.parametrize('fault', ['none', 'missing-key', 'bad-hash', 'bad-page', 'bad-question-region'])
def test_missing_scheme_opt_in_never_accepts_malformed_historical_regions(tmp_path, monkeypatch, fault):
    ex, _, original, _, _ = prepared(tmp_path, monkeypatch, fault=fault)
    state_path = ex.job_dir('missing-ms') / 'state.json'; before = state_path.read_bytes(); old_bytes = original.read_bytes()
    with pytest.raises(ValueError):
        ex.focus('missing-ms', '9702_s25_22_q5', 'Missing evidence staging only', stage_missing_scheme=True)
    assert state_path.read_bytes() == before and original.read_bytes() == old_bytes


@pytest.mark.parametrize('fault', ['guard2', 'running', 'reviewed', 'registered'])
def test_missing_scheme_staging_refuses_holds_and_protected_work(tmp_path, monkeypatch, fault):
    ex, _, original, _, _ = prepared(tmp_path, monkeypatch)
    with ex.state_lock('missing-ms') as current:
        if fault == 'guard2':
            current['reliability_failures']['1']['extract'].append({'issues': ['second failure']})
        elif fault == 'running':
            current['jobs']['extract'].update(pid=os.getpid(), finished=None)
        else:
            current['stage'] = fault
    path = ex.job_dir('missing-ms') / 'state.json'; before = path.read_bytes()
    with pytest.raises(ValueError):
        ex.focus('missing-ms', '9702_s25_22_q5', 'Missing evidence staging only', stage_missing_scheme=True)
    assert path.read_bytes() == before


def test_next_question_missing_scheme_opt_in_reuses_original_and_allows_one_native_stage(tmp_path, monkeypatch):
    from test_extraction_next_question import prepared as published_job, vault_bytes
    ex, vault, original, records, native, _ = published_job(tmp_path, monkeypatch, missing_second_scheme=True)
    original_bytes = original.read_bytes(); frozen_vault = vault_bytes(vault); old = ex.load('multi')
    with pytest.raises(ValueError, match='mark_scheme_regions'):
        ex.next_question('multi', '9702_s23_22_q2', 'Default remains strict')
    state = ex.next_question('multi', '9702_s23_22_q2', 'Stage missing MS only', stage_missing_scheme=True)
    assert json.loads(ex.candidate_path(state).read_text())['questions'] == [records[1]]
    assert state['sources'][0]['selected_page_numbers'] == [2]
    assert state['selected_item_scope']['missing_historical_mark_scheme_record_ids'] == ['q2-a']
    assert state['reliability_failures'] == old['reliability_failures']
    state = ex.evidence_sources('multi', [native[0] + '=2', native[1] + '=1,3'], 'Native MS evidence')
    assert json.loads(ex.candidate_path(state).read_text())['questions'][0]['source_occurrences'][-1]['mark_scheme_regions'] == []
    assert original.read_bytes() == original_bytes and vault_bytes(vault) == frozen_vault


@pytest.mark.parametrize('fault', ['wrong-hash', 'foreign-source'])
def test_native_staging_still_rejects_invalid_nonempty_old_scheme_regions(tmp_path, monkeypatch, fault):
    ex, _, _, _, refs = prepared(tmp_path, monkeypatch)
    state = ex.focus('missing-ms', '9702_s25_22_q5', 'Missing evidence staging', stage_missing_scheme=True)
    path = ex.candidate_path(state); data = json.loads(path.read_text()); source = state['sources'][0]
    data['questions'][0]['mark_scheme_regions'] = [{'source_id': source['id'], 'source_sha256': source['sha256'],
                                                  'page': 1, 'box': [0, 0, 1, 1]}]
    if fault == 'wrong-hash':
        data['questions'][0]['mark_scheme_regions'][0]['source_sha256'] = '0' * 64
    else:
        data['questions'][0]['mark_scheme_regions'][0]['source_id'] = 'asset:foreign-source'
    path.write_text(json.dumps(data))
    with ex.state_lock('missing-ms') as current:
        current['candidate_sha256'] = ex.digest(path)
    state_path = ex.job_dir('missing-ms') / 'state.json'; before = state_path.read_bytes()
    with pytest.raises(ValueError, match='source identity/hash mismatch'):
        ex.evidence_sources('missing-ms', [refs[0] + '=1-2', refs[1] + '=1-2'], 'Native evidence')
    assert state_path.read_bytes() == before
