"""Native evidence revisions preserve compiled occurrences and fail closed until repaired."""
import copy
import json
import os
from pathlib import Path

import pytest
from PIL import Image
from library_assets import write_asset
from test_extraction import extraction, make_pdf


def prepared(tmp_path, monkeypatch):
    ex = extraction()
    vault = tmp_path / 'vault'
    vault.mkdir()
    monkeypatch.delenv('STEM_LIBRARY_ROOT', raising=False)
    monkeypatch.setenv('STEM_TUTOR_VAULT', str(vault))
    monkeypatch.setenv('STEM_EXTRACT_ROOT', str(tmp_path / 'Work'))
    monkeypatch.setenv('STEM_LIBRARY_CACHE', str(tmp_path / 'Work/cache'))
    specs = tmp_path / 'specs/9702'
    specs.mkdir(parents=True)
    (specs / 'graph.json').write_text(json.dumps({'subtopics': [{'id': '9702-1.1'}], 'kcs': [
        {'id': '9702-1.1.1', 'subtopic': '9702-1.1'}]}))
    monkeypatch.setenv('STEM_LIBRARY_SPECS', str(specs.parent))
    refs = []
    for title, pages in [('compiled', ['Question and reproduced key']),
                         ('qp', ['Cover', 'Question', 'Continuation']),
                         ('ms', ['Cover', 'General principles', 'Other', 'Official scheme'])]:
        pdf = make_pdf(tmp_path / f'{title}.pdf', pages)
        refs.append(write_asset(vault, f'Library/Courses/9702/Sources/Library/{title}.pdf', pdf.read_bytes()))
    ex.create('job', '9702', provider='codex', scope='questions', sources=refs[:1])
    ex.inventory('job')
    state = ex.plan('job')
    source = state['sources'][0]
    region = {'source_id': source['id'], 'source_sha256': source['sha256'], 'page': 1, 'box': [0, 0, 1, 1]}
    path = ex.candidate_path(state)
    path.parent.mkdir(parents=True)
    Image.new('RGB', (10, 10), 'red').save(path.parent / 'compiled.png')
    questions = [{'id': f'part-{part}', 'official_qid': '9702_s23_22_q8', 'part': part,
                  'kind': 'mcq', 'complete': False, 'uncertainty': ['compiled OCR unreviewed'],
                  'regions': [region], 'mark_scheme_regions': [copy.deepcopy(region)],
                  'syllabus': ['9702-1.1'], 'kcs': ['9702-1.1.1'], 'prerequisites': [],
                  'answer': 'A', 'media': ['compiled.png']} for part in ('a', 'b')]
    questions[0]['source_occurrences'] = [{'note': 'pre-existing provenance must remain exact'}]
    data = {'questions': questions, 'diagrams': [], 'source_coverage': [
        {'source_id': source['id'], 'source_sha256': source['sha256'], 'inspected_pages': [1],
         'no_relevant_content': False, 'reason': ''}]}
    path.write_text(json.dumps(data))
    with ex.state_lock('job') as current:
        current['sources'][0]['status'] = 'pending_ocr'
        current['jobs']['extract'].update(exit=0, finished='saved', output_sha256=ex.digest(path))
        current['reliability_failures'] = {'1': {'extract': [{'issues': ['saved old failure']}]}}
    ex.focus('job', '9702_s23_22_q8', 'bounded pilot')
    return ex, vault, refs


def selection(refs):
    return [refs[1] + '=1-3', refs[2] + '=1-2,4']


def test_native_evidence_revision_preserves_candidate_sources_and_failure_history(tmp_path, monkeypatch):
    ex, _, refs = prepared(tmp_path, monkeypatch)
    before = ex.load('job')
    old = ex.candidate_path(before)
    old_bytes = old.read_bytes()
    old_data = json.loads(old_bytes)
    state_bytes = (ex.job_dir('job') / 'state.json').read_bytes()
    revised = ex.evidence_sources('job', selection(refs), 'Native originals located')
    path = ex.candidate_path(revised)
    data = json.loads(path.read_text())
    assert path != old and old.read_bytes() == old_bytes
    assert Path(revised['source_rebase_history'][0]['state_snapshot']).read_bytes() == state_bytes
    assert revised['source_rebase_history'][0]['sources'] == before['sources']
    assert revised['source_rebase_history'][0]['sources'][0]['status'] == 'pending_ocr'
    assert revised['reliability_failures'] == before['reliability_failures']
    assert revised['selected_item_scope'] == before['selected_item_scope']
    assert revised['focus_graph_sha256'] == before['focus_graph_sha256']
    assert [s['id'] for s in revised['sources']] == refs[1:]
    assert [s['selected_page_numbers'] for s in revised['sources']] == [[1, 2, 3], [1, 2, 4]]
    assert all(s['status'] == 'available' for s in revised['sources'])
    assert data['source_coverage'] == old_data['source_coverage']
    assert (path.parent / 'compiled.png').read_bytes() == (old.parent / 'compiled.png').read_bytes()
    for original, question in zip(old_data['questions'], data['questions']):
        assert {key: question[key] for key in original if key != 'source_occurrences'} == {
            key: value for key, value in original.items() if key != 'source_occurrences'}
        assert question['source_occurrences'] == original.get('source_occurrences', []) + [{
            'candidate_sha256': ex.digest(old), 'regions': original['regions'],
            'mark_scheme_regions': original['mark_scheme_regions']}]
    checked = ex.check('job')
    assert checked['stage'] == 'pending'
    assert any('source identity/hash mismatch' in e for e in checked['problems'])
    assert not any('pending_ocr' in e for e in checked['problems'])
    assert checked['reliability_failures'] == before['reliability_failures']
    assert revised['jobs']['review'] == {'provider': 'codex'}
    with pytest.raises(ValueError, match='already has a native evidence revision'):
        ex.evidence_sources('job', selection(refs), 'repeat')


def test_native_evidence_requires_occurrence_provenance_in_subsequent_output(tmp_path, monkeypatch):
    ex, _, refs = prepared(tmp_path, monkeypatch)
    state = ex.evidence_sources('job', selection(refs), 'Native originals located')
    data = json.loads(ex.candidate_path(state).read_text())
    data['questions'][0]['source_occurrences'].pop()
    assert any('source occurrence provenance' in e for e in ex._coverage(state, data))
    contract = json.loads(ex._prompt(state, 'extract').split('JOB CONTRACT:\n')[1])
    assert contract['required_source_occurrences'] == state['required_source_occurrences']


def native_mcq_partition(path, question):
    """Disposable repair output includes a separately inspected native key crop."""
    question.setdefault('text', 'Synthetic native MCQ fixture sentinel.')
    Image.new('RGB', (10, 10), 'blue').save(path.parent / 'native-key.png')
    question.update(media=['compiled.png', 'native-key.png'], question_media=['compiled.png'],
                    mark_scheme_media=['native-key.png'], media_regions={
                        'compiled.png': question['regions'][0], 'native-key.png': question['mark_scheme_regions'][0]})


def test_repaired_native_evidence_keeps_occurrences_in_registered_sidecars(tmp_path, monkeypatch):
    from tutorlib.asset_library import AssetLibrary
    ex, vault, refs = prepared(tmp_path, monkeypatch)
    state = ex.evidence_sources('job', selection(refs), 'Native originals located')
    path = ex.candidate_path(state)
    data = json.loads(path.read_text())
    qp, ms = state['sources']
    for question in data['questions']:
        question.update(complete=True, uncertainty=[])
        question['regions'] = [{'source_id': qp['id'], 'source_sha256': qp['sha256'], 'page': 2, 'box': [0, 0, 1, 1]}]
        question['mark_scheme_regions'] = [{'source_id': ms['id'], 'source_sha256': ms['sha256'], 'page': 4, 'box': [0, 0, 1, 1]}]
        native_mcq_partition(path, question)
    data['source_coverage'] = [{'source_id': s['id'], 'source_sha256': s['sha256'],
                                'inspected_pages': s['selected_page_numbers'], 'no_relevant_content': False, 'reason': ''}
                               for s in state['sources']]
    path.write_text(json.dumps(data))
    with ex.state_lock('job') as current:
        current['jobs']['extract'].update(exit=0, finished='repair complete', output_sha256=ex.digest(path))
        current['jobs']['review'].update(exit=0, finished='independent review')
    (ex.job_dir('job') / 'review.json').write_text(json.dumps({
        'candidate_sha256': ex.digest(path), 'verdict': 'pass', 'findings': [],
        'inspected_images': [ex.digest(path.parent / name) for name in ('compiled.png', 'native-key.png')]}))
    assert ex.check('job')['stage'] == 'reviewed'
    state = ex.register('job')
    catalog = AssetLibrary(vault)
    sidecars = [catalog.read(catalog.record(ref)['provenance']['sidecars'][0]) for ref in state['registrations']]
    assert len(sidecars) == 4
    expected = {q['id']: q['source_occurrences'] for q in data['questions']}
    assert all(json.loads(raw)['record']['source_occurrences'] == expected[json.loads(raw)['record']['id']] for raw in sidecars)


@pytest.mark.parametrize('fault', ['guard-extract', 'guard-review', 'running', 'reviewed', 'registered',
                                  'unfocused', 'wrong-course', 'unregistered', 'damaged', 'bad-pages', 'empty'])
def test_native_evidence_rejects_unsafe_revision_without_state_mutation(tmp_path, monkeypatch, fault):
    ex, vault, refs = prepared(tmp_path, monkeypatch)
    choices = selection(refs)
    with ex.state_lock('job') as state:
        if fault.startswith('guard-'):
            state['reliability_failures']['1'][fault.split('-')[1]] = [{'issues': ['first']}, {'issues': ['second']}]
        elif fault == 'running':
            state['jobs']['review'].update(pid=os.getpid(), finished=None)
        elif fault in ('reviewed', 'registered'):
            state['stage'] = fault
        elif fault == 'unfocused':
            state.pop('selected_item_scope')
    if fault == 'wrong-course':
        wrong = write_asset(vault, 'Library/Courses/9701/Sources/Library/wrong.pdf',
                            make_pdf(tmp_path / 'wrong.pdf', ['Chemistry']).read_bytes())
        choices = [wrong + '=1']
    elif fault == 'unregistered':
        choices = ['asset:missing-source=1']
    elif fault == 'damaged':
        (vault / 'Library/Courses/9702/Sources/Library/qp.pdf').write_bytes(b'tampered')
    elif fault == 'bad-pages':
        choices = [refs[1] + '=1-99']
    elif fault == 'empty':
        choices = []
    path = ex.job_dir('job') / 'state.json'
    before = path.read_bytes()
    with pytest.raises((ValueError, ex.library.Fail)):
        ex.evidence_sources('job', choices, 'Native evidence')
    assert path.read_bytes() == before


def test_native_evidence_preserves_old_review_and_rejects_changed_active_source(tmp_path, monkeypatch):
    ex, vault, refs = prepared(tmp_path, monkeypatch)
    review = ex.job_dir('job') / 'review.json'
    review.write_text('{"verdict":"pending","findings":["original review evidence"]}')
    before = review.read_bytes()
    state = ex.evidence_sources('job', selection(refs), 'native evidence')
    history = state['source_rebase_history'][0]
    assert review.read_bytes() == before
    assert Path(history['review_snapshot']).read_bytes() == before
    assert history['review_sha256'] == ex.digest(review)
    (vault / 'Library/Courses/9702/Sources/Library/qp.pdf').write_bytes(b'tampered')
    with pytest.raises((ValueError, ex.library.Fail), match='digest mismatch|source changed'):
        ex.check('job')


def test_native_evidence_rejects_more_than_100_explicit_pages_and_missing_reason(tmp_path, monkeypatch):
    ex, vault, refs = prepared(tmp_path, monkeypatch)
    large = write_asset(vault, 'Library/Courses/9702/Sources/Library/large.pdf',
                        make_pdf(tmp_path / 'large.pdf', ['Question'] * 101).read_bytes())
    with pytest.raises(ValueError, match='100 selected pages'):
        ex.evidence_sources('job', [large + '=1-101'], 'native evidence')
    with pytest.raises(ValueError, match='reason'):
        ex.evidence_sources('job', selection(refs), '')


def test_native_evidence_rejects_scanned_replacement_without_relabelling_it(tmp_path, monkeypatch):
    from pypdf import PdfWriter
    import io
    ex, vault, _ = prepared(tmp_path, monkeypatch)
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    output = io.BytesIO()
    writer.write(output)
    scanned = write_asset(vault, 'Library/Courses/9702/Sources/Library/scanned.pdf', output.getvalue())
    with pytest.raises(ValueError, match='native text layer'):
        ex.evidence_sources('job', [scanned + '=1'], 'native evidence')
    assert ex.load('job')['sources'][0]['status'] == 'pending_ocr'
