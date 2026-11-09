"""Focused revisions preserve maker work and account only selected question pages."""
import json
from pathlib import Path

import pytest
from PIL import Image
from test_extraction import extraction, make_pdf


def prepared(tmp_path, monkeypatch):
    ex = extraction()
    monkeypatch.setenv('STEM_EXTRACT_ROOT', str(tmp_path / 'Work'))
    monkeypatch.setenv('STEM_LIBRARY_ROOT', str(tmp_path / 'sources'))
    make_pdf(tmp_path / 'sources/book.pdf', ['question', 'other', 'question end', 'scheme'])
    specs = tmp_path / 'specs/9702'
    specs.mkdir(parents=True)
    (specs / 'graph.json').write_text(json.dumps({'subtopics': [], 'kcs': []}))
    monkeypatch.setenv('STEM_LIBRARY_SPECS', str(specs.parent))
    ex.create('parent', '9702', provider='codex', scope='questions')
    ex.inventory('parent')
    state = ex.plan('parent')
    path = ex.candidate_path(state)
    path.parent.mkdir(parents=True)
    Image.new('RGB', (10, 10), 'red').save(path.parent / 'figure.png')
    source = state['sources'][0]
    def region(page):
        return {'source_id': source['id'], 'source_sha256': source['sha256'], 'page': page, 'box': [0, 0, 1, 1]}
    records = [{'id': f'q1-{part}', 'official_qid': '9702_w25_22_q1', 'part': part,
                'complete': False, 'uncertainty': ['source comparison required'],
                'regions': [region(1), region(3)], 'mark_scheme_regions': [region(4)],
                'media': ['figure.png'], 'syllabus': ['9702-1.1'], 'kcs': ['9702-1.1.1']}
               for part in ('a', 'b')]
    other = {**records[0], 'id': 'other', 'official_qid': '9702_w25_22_q2'}
    data = {'questions': records + [other], 'diagrams': [], 'source_coverage': [
        {'source_id': source['id'], 'source_sha256': source['sha256'], 'inspected_pages': [1, 2, 3, 4],
         'no_relevant_content': False, 'reason': ''}]}
    path.write_text(json.dumps(data))
    with ex.state_lock('parent') as current:
        current['jobs']['extract'].update(exit=0, finished='saved', output_sha256=ex.digest(path))
        current['reliability_failures'] = {'1': {'extract': [{'issues': ['old gate failure']}]}}
    return ex, path, data


def test_focus_reuses_all_parts_and_media_preserving_original_state_and_guard(tmp_path, monkeypatch):
    ex, original, data = prepared(tmp_path, monkeypatch)
    state_path = ex.job_dir('parent') / 'state.json'
    old_state, old_bytes = state_path.read_bytes(), original.read_bytes()
    state = ex.focus('parent', '9702_w25_22_q1', 'Bounded whole-question pilot')
    revised = ex.candidate_path(state)
    selected = json.loads(revised.read_text())
    assert revised != original and original.read_bytes() == old_bytes
    assert selected['questions'] == data['questions'][:2]
    assert (revised.parent / 'figure.png').read_bytes() == (original.parent / 'figure.png').read_bytes()
    assert state['sources'][0]['selected_page_numbers'] == [1, 3, 4]
    assert state['reliability_failures'] == {'1': {'extract': [{'issues': ['old gate failure']}]}}
    assert Path(state['focus_history'][0]['state_snapshot']).read_bytes() == old_state
    assert state['focus_history'][0]['sources'][0]['selected_pages'] == [1, 4]
    assert state['jobs']['extract']['reused_candidate_sha256'] == ex.digest(original)
    assert state['jobs']['review'] == {'provider': 'codex'}
    assert ex._coverage(state, selected) == []
    contract = json.loads(ex._prompt(state, 'review').split('JOB CONTRACT:\n')[1])
    assert contract['sources'][0]['selected_page_numbers'] == [1, 3, 4]
    assert 'selected_page_range' not in contract['sources'][0]
    assert contract['selected_item_scope']['official_qid'] == '9702_w25_22_q1'
    with pytest.raises(ValueError, match='already focused'):
        ex.focus('parent', '9702_w25_22_q1', 'again')


def test_focus_coverage_rejects_missing_parts_and_unrelated_page_credit(tmp_path, monkeypatch):
    ex, _, _ = prepared(tmp_path, monkeypatch)
    state = ex.focus('parent', '9702_w25_22_q1', 'pilot')
    data = json.loads(ex.candidate_path(state).read_text())
    data['questions'].pop()
    assert any('whole selected question' in error for error in ex._coverage(state, data))
    data = json.loads(ex.candidate_path(state).read_text())
    data['source_coverage'][0]['inspected_pages'] = [1, 2, 3, 4]
    assert any('every selected page' in error for error in ex._coverage(state, data))
    source = state['sources'][0]
    assert any('outside' in error for error in ex._regions({'regions': [
        {'source_id': source['id'], 'source_sha256': source['sha256'], 'page': 2, 'box': [0, 0, 1, 1]}]}, {source['id']: source}))


def test_focus_retains_two_failure_hold_and_frozen_graph(tmp_path, monkeypatch):
    ex, _, _ = prepared(tmp_path, monkeypatch)
    with ex.state_lock('parent') as current:
        current['reliability_failures']['1']['extract'].append({'issues': ['second failure']})
    state = ex.focus('parent', '9702_w25_22_q1', 'pilot')
    with pytest.raises(ValueError, match='paused after 2 failures'):
        ex.run('parent', weekly_remaining=90, retry='extract')
    graph = tmp_path / 'specs/9702/graph.json'
    graph.write_text('{}')
    with pytest.raises(ValueError, match='course graph changed'):
        ex.check('parent')


@pytest.mark.parametrize('fault', ['missing-question', 'wrong-hash', 'uninspected', 'reviewed'])
def test_focus_rejects_unsafe_derivations_without_changing_candidate(tmp_path, monkeypatch, fault):
    ex, original, data = prepared(tmp_path, monkeypatch)
    qid = '9702_w25_22_q1'
    if fault == 'missing-question':
        qid = '9702_w25_22_q99'
    elif fault == 'wrong-hash':
        data['questions'][0]['regions'][0]['source_sha256'] = '0' * 64
        original.write_text(json.dumps(data))
    elif fault == 'uninspected':
        data['source_coverage'][0]['inspected_pages'].remove(3)
        original.write_text(json.dumps(data))
    else:
        with ex.state_lock('parent') as current:
            current['stage'] = 'reviewed'
    before = original.read_bytes()
    with pytest.raises(ValueError):
        ex.focus('parent', qid, 'pilot')
    assert original.read_bytes() == before


def test_focus_launch_counts_only_explicit_pages_and_never_reextracts_by_default(tmp_path, monkeypatch):
    ex, _, _ = prepared(tmp_path, monkeypatch)
    ex.focus('parent', '9702_w25_22_q1', 'pilot')
    import capabilities
    monkeypatch.setattr(capabilities, 'preflight', lambda: None)
    with ex.state_lock('parent') as current:
        # An older adapter's bounding range must not expand an explicit item selection.
        current['sources'][0]['selected_pages'] = [1, 1000]
    with pytest.raises(ValueError, match='weekly remaining'):
        ex.run('parent', retry='extract')
    # Default resume reaches the reviewer gate and does not author again.
    with pytest.raises(ValueError, match='candidate validation failed before review'):
        ex.run('parent')


def test_focus_requires_saved_candidate_hash_and_relative_media(tmp_path, monkeypatch):
    ex, original, data = prepared(tmp_path, monkeypatch)
    original.write_text(json.dumps({**data, 'extra': 'edited since maker finished'}))
    with pytest.raises(ValueError, match='exact saved'):
        ex.focus('parent', '9702_w25_22_q1', 'pilot')
    for row in data['questions']:
        row['media'] = [str(original.parent / 'figure.png')]
    original.write_text(json.dumps(data))
    with ex.state_lock('parent') as current:
        current['jobs']['extract']['output_sha256'] = ex.digest(original)
    with pytest.raises(ValueError, match='relative media'):
        ex.focus('parent', '9702_w25_22_q1', 'pilot')


def test_focus_repair_cannot_silently_change_assessed_part_identity(tmp_path, monkeypatch):
    ex, _, _ = prepared(tmp_path, monkeypatch)
    state = ex.focus('parent', '9702_w25_22_q1', 'pilot')
    data = json.loads(ex.candidate_path(state).read_text())
    data['questions'][0]['part'] = ''
    assert any('whole selected question' in error for error in ex._coverage(state, data))
