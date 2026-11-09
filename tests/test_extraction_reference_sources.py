"""Explicit auxiliary references append before native repair, without evidence transfer."""
import json
from pathlib import Path

import pytest
from library_assets import write_asset
from test_extraction import make_pdf
from test_extraction_evidence_sources import prepared as focused_job, selection


def prepared(tmp_path, monkeypatch):
    ex, vault, refs = focused_job(tmp_path, monkeypatch)
    ex.evidence_sources('job', selection(refs), 'Native original QP/MS')
    auxiliary = write_asset(vault, 'Library/Courses/9702/Sources/Library/later-reference.pdf',
                            make_pdf(tmp_path / 'reference.pdf', ['Later edition cover', 'Constants', 'Atomic table']).read_bytes())
    return ex, vault, refs, auxiliary


def test_reference_append_preserves_exact_inputs_and_requires_real_repair_review(tmp_path, monkeypatch):
    ex, vault, _, ref = prepared(tmp_path, monkeypatch)
    before = ex.load('job'); old = ex.candidate_path(before); raw = old.read_bytes()
    media = (old.parent / 'compiled.png').read_bytes()
    state_path = ex.job_dir('job') / 'state.json'; state_raw = state_path.read_bytes()
    library_raw = {str(p): p.read_bytes() for p in (vault / 'Library').rglob('*') if p.is_file()}
    state = ex.reference_sources('job', [ref + '=1-3'], 'Later edition constants/table only', 'Explicit auxiliary evidence')
    assert state['sources'][:-1] == before['sources']
    auxiliary = state['sources'][-1]
    assert auxiliary['id'] == ref and auxiliary['selected_page_numbers'] == [1, 2, 3]
    assert auxiliary['evidence_role'] == 'auxiliary_reference'
    assert auxiliary['reference_purpose'] == 'Later edition constants/table only'
    for key in ('candidate', 'candidate_sha256', 'jobs', 'stage', 'selected_item_scope', 'required_source_occurrences',
                'focus_graph_sha256', 'source_rebase_history', 'reliability_failures', 'history'):
        assert state[key] == before[key]
    assert old.read_bytes() == raw and (old.parent / 'compiled.png').read_bytes() == media
    history = state['reference_source_history'][0]
    assert Path(history['state_snapshot']).read_bytes() == state_raw
    assert Path(history['candidate_snapshot']).read_bytes() == raw
    assert ex.digest(history['state_snapshot']) == history['state_snapshot_sha256']
    assert ex.digest(history['candidate_snapshot']) == history['candidate_sha256']
    for role in ('extract', 'review'):
        contract = json.loads(ex._prompt(state, role).split('JOB CONTRACT:\n')[1])
        assert contract['sources'][-1] == auxiliary
    assert ex.check('job')['stage'] == 'pending'
    with pytest.raises(ValueError):
        ex.register('job')
    with pytest.raises(ValueError):
        ex.publish('job', tmp_path / 'never-published')
    assert library_raw == {str(p): p.read_bytes() for p in (vault / 'Library').rglob('*') if p.is_file()}


@pytest.mark.parametrize('fault', ['extract-attempt', 'review-attempt', 'running', 'reviewed', 'registered',
                                  'published', 'guard-extract', 'guard-review', 'candidate', 'base-source',
                                  'base-snapshot', 'scope', 'graph', 'repeat', 'same-id', 'wrong-course', 'pagecap'])
def test_reference_append_refuses_unsafe_inputs_atomically(tmp_path, monkeypatch, fault):
    ex, vault, refs, ref = prepared(tmp_path, monkeypatch)
    choices = [ref + '=1-3']
    with ex.state_lock('job') as state:
        if fault.endswith('-attempt'):
            state['jobs'][fault.split('-')[0]]['started'] = 'attempted'
        elif fault == 'running':
            import os
            state['jobs']['extract'].update(pid=os.getpid())
        elif fault in ('reviewed', 'registered', 'published'):
            state['stage'] = fault
        elif fault.startswith('guard-'):
            state['reliability_failures']['1'][fault.split('-')[1]] = [{'issues': ['first']}, {'issues': ['second']}]
        elif fault == 'base-source':
            state['sources'][0]['selected_page_numbers'] = [1]
        elif fault == 'base-snapshot':
            Path(state['source_rebase_history'][0]['state_snapshot']).write_text('{}')
        elif fault == 'scope':
            state['selected_item_scope']['official_qid'] = '9702_s23_22_q9'
        elif fault == 'graph':
            state['focus_graph_sha256'] = '0' * 64
        elif fault == 'candidate':
            ex.candidate_path(state).write_text('{}')
    if fault == 'repeat':
        ex.reference_sources('job', choices, 'Reference only', 'Append once')
    elif fault == 'same-id':
        choices = [refs[1] + '=1']
    elif fault == 'wrong-course':
        wrong = write_asset(vault, 'Library/Courses/9701/Sources/Library/wrong.pdf',
                            make_pdf(tmp_path / 'wrong.pdf', ['Wrong course']).read_bytes())
        choices = [wrong + '=1']
    elif fault == 'pagecap':
        large = write_asset(vault, 'Library/Courses/9702/Sources/Library/large.pdf',
                            make_pdf(tmp_path / 'large.pdf', ['Reference'] * 95).read_bytes())
        choices = [large + '=1-95']  # six existing selected pages, combined101
    state_path = ex.job_dir('job') / 'state.json'; before = state_path.read_bytes()
    with pytest.raises((ValueError, ex.library.Fail)):
        ex.reference_sources('job', choices, 'Reference only', 'Explicit auxiliary evidence')
    assert state_path.read_bytes() == before


@pytest.mark.parametrize('fault', ['snapshot', 'snapshot-hash', 'candidate-snapshot', 'media-snapshot', 'source', 'scope', 'graph', 'history'])
def test_reference_binding_tamper_blocks_free_checks(tmp_path, monkeypatch, fault):
    ex, _, _, ref = prepared(tmp_path, monkeypatch)
    ex.reference_sources('job', [ref + '=1-3'], 'Reference only', 'Explicit auxiliary evidence')
    with ex.state_lock('job') as state:
        entry = state['reference_source_history'][0]
        if fault == 'snapshot':
            Path(entry['state_snapshot']).write_text('{}')
        elif fault == 'snapshot-hash':
            entry['state_snapshot_sha256'] = '0' * 64
        elif fault == 'candidate-snapshot':
            Path(entry['candidate_snapshot']).write_text('{}')
        elif fault == 'media-snapshot':
            Path(entry['media']['compiled.png']['path']).write_bytes(b'changed')
        elif fault == 'source':
            state['sources'][-1]['selected_page_numbers'] = [1]
        elif fault == 'scope':
            state['selected_item_scope']['official_qid'] = '9702_s23_22_q9'
        elif fault == 'graph':
            state['focus_graph_sha256'] = '0' * 64
        else:
            entry['purpose'] = 'Edited purpose'
            entry['added_sources'][0]['reference_purpose'] = 'Edited purpose'
            state['sources'][-1]['reference_purpose'] = 'Edited purpose'
    with pytest.raises(ValueError):
        ex.check('job')


def test_actual_repair_and_fresh_blind_review_can_bind_auxiliary_reference(tmp_path, monkeypatch):
    ex, _, _, ref = prepared(tmp_path, monkeypatch)
    state = ex.reference_sources('job', [ref + '=1-3'], 'Later edition constants/table only', 'Explicit auxiliary evidence')
    path = ex.candidate_path(state); data = json.loads(path.read_text()); qp, ms, auxiliary = state['sources']
    def region(source, page):
        return {'source_id': source['id'], 'source_sha256': source['sha256'], 'page': page, 'box': [0, 0, 1, 1]}
    for row in data['questions']:
        row.update(complete=True, uncertainty=[], regions=[region(qp, 2), region(auxiliary, 2)],
                   mark_scheme_regions=[region(ms, 4)])
        from test_extraction_evidence_sources import native_mcq_partition
        native_mcq_partition(path, row)
    data['source_coverage'] = [{'source_id': s['id'], 'source_sha256': s['sha256'],
        'inspected_pages': s['selected_page_numbers'], 'no_relevant_content': False, 'reason': ''} for s in state['sources']]
    path.write_text(json.dumps(data))
    with ex.state_lock('job') as current:
        current['jobs']['extract'].update(exit=0, finished='disposable native repair', output_sha256=ex.digest(path))
        current['jobs']['review'].update(exit=0, finished='disposable fresh blind review')
    review = {'candidate_sha256': ex.digest(path), 'verdict': 'pass', 'findings': [],
              'inspected_images': [ex.digest(path.parent / name) for name in ('compiled.png', 'native-key.png')]}
    (ex.job_dir('job') / 'review.json').write_text(json.dumps(review))
    assert ex.check('job')['stage'] == 'reviewed'


@pytest.mark.parametrize('fault', ['empty', 'purpose', 'reason', 'damaged'])
def test_reference_append_requires_explicit_verified_selectors_and_purpose(tmp_path, monkeypatch, fault):
    ex, vault, _, ref = prepared(tmp_path, monkeypatch)
    choices, purpose, reason = [ref + '=1-3'], 'Reference only', 'Explicit auxiliary evidence'
    if fault == 'empty': choices = []
    elif fault == 'purpose': purpose = ' '
    elif fault == 'reason': reason = ''
    else: (vault / 'Library/Courses/9702/Sources/Library/later-reference.pdf').write_bytes(b'changed')
    path = ex.job_dir('job') / 'state.json'; before = path.read_bytes()
    with pytest.raises((ValueError, ex.library.Fail)):
        ex.reference_sources('job', choices, purpose, reason)
    assert path.read_bytes() == before


@pytest.mark.parametrize('fault', ['missing-part', 'flags', 'occurrences', 'historical-candidate'])
def test_reference_append_does_not_accept_rewritten_native_staging_inputs(tmp_path, monkeypatch, fault):
    ex, _, _, ref = prepared(tmp_path, monkeypatch)
    with ex.state_lock('job') as state:
        if fault == 'historical-candidate':
            Path(state['source_rebase_history'][0]['candidate']).write_text('{}')
        else:
            path = ex.candidate_path(state); data = json.loads(path.read_text())
            if fault == 'missing-part': data['questions'].pop()
            elif fault == 'flags': data['questions'][0].update(complete=True, uncertainty=[])
            else: data['questions'][0]['source_occurrences'] = []
            path.write_text(json.dumps(data)); state['candidate_sha256'] = ex.digest(path)
    path = ex.job_dir('job') / 'state.json'; before = path.read_bytes()
    with pytest.raises(ValueError):
        ex.reference_sources('job', [ref + '=1-3'], 'Reference only', 'Explicit auxiliary evidence')
    assert path.read_bytes() == before


def test_next_scope_archives_references_and_reuses_original_without_auxiliary_contamination(tmp_path, monkeypatch):
    from test_extraction_next_question import prepared as published_job, vault_bytes
    ex, vault, original, records, native, _ = published_job(tmp_path, monkeypatch, reference_before_first=True)
    prior = ex.load('multi'); frozen_vault = vault_bytes(vault); original_raw = original.read_bytes()
    reference = prior['reference_source_history'][0]; auxiliary_id = reference['added_sources'][0]['id']
    archived_files = {reference[key]: Path(reference[key]).read_bytes()
                      for key in ('state_snapshot', 'candidate_snapshot', 'manifest')}
    for binding in reference['media'].values():
        archived_files[binding['path']] = Path(binding['path']).read_bytes()
    current_candidate = ex.candidate_path(prior); current_raw = current_candidate.read_bytes()
    state = ex.next_question('multi', '9702_s23_22_q2', 'Continue original completed maker artifact')
    assert 'reference_source_history' not in state
    assert auxiliary_id not in [s['id'] for s in state['sources']]
    archive = state['completed_scope_history'][-1]
    assert archive['reference_source_history'] == prior['reference_source_history']
    assert json.loads(Path(archive['state_snapshot']).read_bytes())['reference_source_history'] == prior['reference_source_history']
    assert all(Path(path).read_bytes() == raw for path, raw in archived_files.items())
    assert original.read_bytes() == original_raw and current_candidate.read_bytes() == current_raw
    assert json.loads(ex.candidate_path(state).read_bytes())['questions'] == [records[1]]
    for key in ('reliability_failures', 'reliability_history', 'pass', 'codex_role_overrides', 'codex_stop_remaining'):
        assert state[key] == prior[key]
    assert vault_bytes(vault) == frozen_vault
    state = ex.evidence_sources('multi', [native[0] + '=2', native[1] + '=1,3'], 'New scope exact native evidence')
    assert 'reference_source_history' not in state
    assert [s['id'] for s in state['sources']] == native
    ex._verify_sources(state)
    assert vault_bytes(vault) == frozen_vault
