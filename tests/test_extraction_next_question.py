"""Published question scopes advance without replacing guards, resources or history."""
import copy
import importlib.util
import json
import os
from pathlib import Path

import pytest
from PIL import Image

from fixtures import make_vault
from library_assets import write_asset
from test_extraction import make_pdf
from test_extraction_ocr import prepared as ocr_prepared, sha, write_json


def prepared(tmp_path, monkeypatch, *, publish_first=True, missing_second_scheme=False, reference_before_first=False):
    ex, _, old_source, folder = ocr_prepared(tmp_path, monkeypatch)
    vault = make_vault(tmp_path)
    (vault / '.tutor/packs/v1/papers.json').write_text('{"papers": []}')
    monkeypatch.delenv('STEM_LIBRARY_ROOT')
    monkeypatch.setenv('STEM_TUTOR_VAULT', str(vault))
    monkeypatch.setenv('STEM_LIBRARY_CACHE', str(tmp_path / 'Work/cache'))
    monkeypatch.setenv('STEM_LIBRARY_SPECS', str(vault / '.tutor/packs/v1/specs'))
    ref = write_asset(vault, 'Library/Courses/9702/Sources/Library/compiled.pdf', Path(old_source['path']).read_bytes())
    manifest = json.loads((folder / 'manifest.json').read_text())
    manifest['source_id'] = ref
    for page in range(1, 4):
        path = folder / f'p{page:04d}.json'
        payload = json.loads(path.read_text()); payload['source_id'] = ref
        write_json(path, payload)
        manifest['pages'][str(page)]['sha256'] = sha(path)
    write_json(folder / 'manifest.json', manifest)
    ex.create('multi', '9702', provider='codex', scope='questions', sources=[ref])
    ex.inventory('multi'); ex.enable_ocr('multi', ref)
    state = ex.plan('multi'); source = state['sources'][0]
    path = ex.candidate_path(state); path.parent.mkdir(parents=True)
    for title, color in [('question', 'red'), ('scheme', 'blue')]:
        Image.new('RGB', (20, 20), color).save(path.parent / (title + '.png'))
    def region(page):
        return {'source_id': ref, 'source_sha256': source['sha256'], 'page': page, 'box': [0, 0, 1, 1]}
    records = [{'id': f'q{number}-a', 'official_qid': f'9702_s23_22_q{number}', 'part': 'a',
                'kind': 'structured', 'complete': False, 'uncertainty': ['Original OCR requires source comparison'],
                'regions': [region(number)], 'mark_scheme_regions': [region(3)],
                'media': ['question.png', 'scheme.png'], 'question_media': ['question.png'], 'mark_scheme_media': ['scheme.png'],
                'stem': 'State a property of a vector.', 'answer': 'A vector has direction.',
                'marks': 1, 'scheme': [{'mark': 'B1', 'point': 'A vector has direction.'}],
                'syllabus': ['9702-2.1'], 'kcs': ['9702-2.1.1'], 'prerequisites': []}
               for number in (1, 2)]
    if missing_second_scheme:
        records[1]['mark_scheme_regions'] = []
    path.write_text(json.dumps({'questions': records, 'diagrams': [], 'source_coverage': [{
        'source_id': ref, 'source_sha256': source['sha256'], 'inspected_pages': [1, 2, 3], 'no_relevant_content': False, 'reason': ''}]}))
    with ex.state_lock('multi') as current:
        current['jobs']['extract'].update(exit=0, finished='saved', output_sha256=ex.digest(path))
        current['reliability_failures'] = {'1': {'extract': [{'issues': ['old failure']}]}}
    original = path
    native = []
    for title, text in [('qp', ['Native Q1', 'Native Q2']), ('ms', ['Principles', 'Official Q1 scheme', 'Official Q2 scheme'])]:
        native.append(write_asset(vault, f'Library/Courses/9702/Sources/Library/{title}.pdf',
                                  make_pdf(tmp_path / (title + '.pdf'), text).read_bytes()))
    ex.focus('multi', '9702_s23_22_q1', 'first whole question')
    ex.evidence_sources('multi', [native[0] + '=1', native[1] + '=1-2'], 'Native originals')
    if reference_before_first:
        ref = write_asset(vault, 'Library/Courses/9702/Sources/Library/auxiliary.pdf',
                          make_pdf(tmp_path / 'auxiliary.pdf', ['Later edition constants']).read_bytes())
        ex.reference_sources('multi', [ref + '=1'], 'Distinct later-edition reference only', 'Before first repair')
    publish_current(ex, tmp_path, 1, publish=publish_first)
    ex.configure('multi', 'Retain current settings', codex_stop_remaining=40, codex_role_overrides={
        'extract': {'model': 'gpt-6.1-sol', 'effort': 'medium'}, 'review': {'model': 'gpt-6.1-sol', 'effort': 'high'}})
    with ex.state_lock('multi') as current:
        current['pass'] = 1
        current['reliability_failures']['0'] = {'extract': [{'issues': ['prior pass']}, {'issues': ['prior pass second']}]}
        current['reliability_failures']['1']['review'] = [{'issues': ['current review history'] }]
        current['reliability_history'] = [{'reason': 'historical operator decision', 'failures': {'old': 'preserved'}}]
    events = vault / '.tutor/events/preserved.jsonl'; events.parent.mkdir(parents=True)
    events.write_bytes(b'{"historical":"learner event bytes"}\n')
    return ex, vault, original, records, native, folder


def publish_current(ex, tmp_path, number, *, publish=True):
    state = ex.load('multi'); path = ex.candidate_path(state); data = json.loads(path.read_text())
    qp, ms = state['sources'][:2]
    for row in data['questions']:
        row.update(complete=True, uncertainty=[])
        row['regions'] = [{'source_id': qp['id'], 'source_sha256': qp['sha256'], 'page': number, 'box': [0, 0, 1, 1]}]
        row['regions'] += [{'source_id': s['id'], 'source_sha256': s['sha256'], 'page': s['selected_page_numbers'][0],
                            'box': [0, 0, 1, 1]} for s in state['sources'][2:]]
        row['mark_scheme_regions'] = [{'source_id': ms['id'], 'source_sha256': ms['sha256'], 'page': number + 1, 'box': [0, 0, 1, 1]}]
    data['source_coverage'] = [{'source_id': s['id'], 'source_sha256': s['sha256'], 'inspected_pages': s['selected_page_numbers'],
                                'no_relevant_content': False, 'reason': ''} for s in state['sources']]
    path.write_text(json.dumps(data))
    review = ex.job_dir('multi') / 'review.json'
    review.write_text(json.dumps({'candidate_sha256': ex.digest(path), 'verdict': 'pass', 'findings': [],
                                  'inspected_images': [ex.digest(path.parent / name) for name in data['questions'][0]['media']]}))
    with ex.state_lock('multi') as current:
        current['jobs']['extract'].update(exit=0, finished='completed repair', output_sha256=ex.digest(path))
        current['jobs']['review'].update(exit=0, finished='independent review', output_sha256=ex.digest(review))
    ex.register('multi')
    if not publish:
        return
    batch = tmp_path / f'batch-{number}'
    ex.prepare_publication('multi', batch); ex.publish('multi', batch)


def vault_bytes(vault):
    return {str(p.relative_to(vault)): p.read_bytes() for p in vault.rglob('*') if p.is_file()}


def add_other_scope(ex, vault, tmp_path, *, target=False, qid=None):
    import topicals
    _, _, bank = ex._active_topical_bank(vault)
    other = copy.deepcopy(bank['items'][0]); other['id'] = 'other-scope'
    other['source'].update(qid=qid or ('9702_s23_22_q2' if target else '9702_s23_22_q99'), candidate_sha256='a' * 64)
    bank['items'].append(other)
    batch = tmp_path / 'other-batch'; batch.mkdir()
    (batch / 'bank.json').write_text(json.dumps(bank))
    return topicals.publish(batch, vault, expected_current=(vault / '.tutor/topicals/CURRENT').read_text().strip())


def test_next_question_preserves_published_scope_and_current_guards_then_rebases_again(tmp_path, monkeypatch):
    ex, vault, original, records, native, folder = prepared(tmp_path, monkeypatch)
    first = ex.load('multi'); old_candidate = ex.candidate_path(first); old_bytes = old_candidate.read_bytes()
    original_bytes = original.read_bytes(); old_state = (ex.job_dir('multi') / 'state.json').read_bytes()
    old_review = (ex.job_dir('multi') / 'review.json').read_bytes()
    first_items = ex._active_topical_bank(vault)[2]['items']
    add_other_scope(ex, vault, tmp_path)
    frozen_vault = vault_bytes(vault)
    state = ex.next_question('multi', '9702_s23_22_q2', 'Continue completed original maker work')
    assert vault_bytes(vault) == frozen_vault
    assert old_candidate.read_bytes() == old_bytes and original.read_bytes() == original_bytes
    archive = state['completed_scope_history'][0]
    assert json.loads(Path(archive['state_snapshot']).read_bytes()) == json.loads(old_state)
    assert Path(archive['review_snapshot']).read_bytes() == old_review
    assert archive['source_rebase_history'] == first['source_rebase_history']
    assert state['reliability_failures'] == first['reliability_failures']
    assert state['reliability_history'] == first['reliability_history']
    for key in ('pass', 'codex_stop_remaining', 'codex_role_overrides', 'configuration_history'):
        assert state[key] == first[key]
    for key in ('publication', 'registrations', 'registered_records', 'required_source_occurrences', 'source_rebase_history'):
        assert key not in state
    assert state['jobs']['review'] == {'provider': 'codex'}
    assert json.loads(ex.candidate_path(state).read_bytes())['questions'] == [records[1]]
    assert state['sources'][0]['status'] == 'pending_ocr'
    assert state['sources'][0]['selected_page_numbers'] == [2, 3]
    assert len(state['sources'][0]['ocr']['pages']) == 3
    ex._verify_sources(state)
    assert ex._active_topical_bank(vault)[2]['items'][:1] == first_items
    rebased = ex.evidence_sources('multi', [native[0] + '=2', native[1] + '=1,3'], 'Next native evidence')
    assert len(rebased['source_rebase_history']) == 1
    assert len(rebased['completed_scope_history'][0]['source_rebase_history']) == 1
    publish_current(ex, tmp_path, 2)
    assert ex._active_topical_bank(vault)[2]['items'][:1] == first_items
    with pytest.raises(ValueError):
        ex.next_question('multi', '9702_s23_22_q1', 'already processed')


@pytest.mark.parametrize('fault', ['guard-extract', 'guard-review', 'running', 'pending', 'review', 'media',
                                  'original-candidate', 'original-state', 'graph', 'unknown', 'active-target'])
def test_next_question_rejects_unbound_or_unsafe_transition_atomically(tmp_path, monkeypatch, fault):
    ex, vault, original, _, _, _ = prepared(tmp_path, monkeypatch)
    qid = '9702_s23_22_q2'
    with ex.state_lock('multi') as current:
        if fault.startswith('guard-'):
            current['reliability_failures']['1'][fault.split('-')[1]].append({'issues': ['second']})
        elif fault == 'running':
            current['jobs']['extract'].update(pid=os.getpid(), finished=None)
        elif fault == 'pending':
            current['stage'] = 'pending'
    state = ex.load('multi')
    if fault == 'review':
        p = ex.job_dir('multi') / 'review.json'; p.write_bytes(p.read_bytes() + b' ')
    elif fault == 'media':
        p = ex.candidate_path(state).parent / 'question.png'; p.write_bytes(p.read_bytes() + b'changed')
    elif fault == 'original-candidate':
        original.write_bytes(original.read_bytes() + b' ')
    elif fault == 'original-state':
        p = Path(state['focus_history'][0]['state_snapshot']); p.write_bytes(p.read_bytes() + b' ')
    elif fault == 'graph':
        p = vault / '.tutor/packs/v1/specs/9702/graph.json'; p.write_bytes(p.read_bytes() + b' ')
    elif fault == 'unknown':
        qid = '9702_s23_22_q33'
    elif fault == 'active-target':
        add_other_scope(ex, vault, tmp_path, target=True)
    state_path = ex.job_dir('multi') / 'state.json'; before = state_path.read_bytes(); frozen_vault = vault_bytes(vault)
    with pytest.raises((ValueError, ex.library.Fail)):
        ex.next_question('multi', qid, 'Next question')
    assert state_path.read_bytes() == before
    assert vault_bytes(vault) == frozen_vault


def test_next_scope_route_probe_filters_candidate_hash_with_shared_job_name(tmp_path, monkeypatch):
    ex, vault, _, _, _, _ = prepared(tmp_path, monkeypatch)
    add_other_scope(ex, vault, tmp_path)
    script = Path(__file__).resolve().parents[2] / 'Work/Workers/extraction/all-course-20261101/verify_published_routes.py'
    spec = importlib.util.spec_from_file_location('published_route_probe', script)
    probe = importlib.util.module_from_spec(spec); spec.loader.exec_module(probe)
    monkeypatch.setattr(probe, 'WORKSPACE', tmp_path)
    # The harness reads the manager review at WORKSPACE/Work/Workers/extraction.
    evidence = {}
    _, _, items, _ = probe.bound_publication(vault, ex.load('multi'), evidence)
    assert len(items) == 1 and items[0]['source']['candidate_sha256'] == ex.load('multi')['candidate_sha256']


def test_next_question_refuses_changed_published_items_in_newer_active_bank(tmp_path, monkeypatch):
    import topicals
    ex, vault, _, _, _, _ = prepared(tmp_path, monkeypatch)
    version, _, bank = ex._active_topical_bank(vault)
    bank['items'][0]['answer'] = 'Changed after publication.'
    batch = tmp_path / 'changed-active'; batch.mkdir()
    (batch / 'bank.json').write_text(json.dumps(bank))
    topicals.publish(batch, vault, expected_current=version)
    path = ex.job_dir('multi') / 'state.json'; before = path.read_bytes()
    with pytest.raises(ValueError, match='active bank.*preserves'):
        ex.next_question('multi', '9702_s23_22_q2', 'Next question')
    assert path.read_bytes() == before


def test_next_question_still_checks_unselected_original_frozen_ocr_page(tmp_path, monkeypatch):
    ex, _, _, _, _, folder = prepared(tmp_path, monkeypatch)
    p = folder / 'p0001.json'; p.write_bytes(p.read_bytes() + b'changed')
    path = ex.job_dir('multi') / 'state.json'; before = path.read_bytes()
    with pytest.raises(ValueError, match='OCR page 1 sidecar hash changed'):
        ex.next_question('multi', '9702_s23_22_q2', 'Next question')
    assert path.read_bytes() == before


def test_next_question_accepts_exact_published_scope_after_free_check(tmp_path, monkeypatch):
    ex, vault, _, _, _, _ = prepared(tmp_path, monkeypatch)
    published = ex.load('multi')
    checked = ex.check('multi')
    assert checked['stage'] == 'reviewed' and checked['publication'] == published['publication']
    frozen = vault_bytes(vault)
    state = ex.next_question('multi', '9702_s23_22_q2', 'Continue after free verification')
    assert state['selected_item_scope']['official_qid'] == '9702_s23_22_q2'
    assert state['reliability_failures'] == published['reliability_failures']
    assert vault_bytes(vault) == frozen


def test_next_question_rejects_reviewed_scope_without_publication(tmp_path, monkeypatch):
    ex, vault, _, _, _, _ = prepared(tmp_path, monkeypatch, publish_first=False)
    state = ex.check('multi')
    assert state['stage'] == 'reviewed' and not state.get('publication')
    path = ex.job_dir('multi') / 'state.json'; before = path.read_bytes(); frozen = vault_bytes(vault)
    with pytest.raises(ValueError, match='published'):
        ex.next_question('multi', '9702_s23_22_q2', 'Publication is missing')
    assert path.read_bytes() == before and vault_bytes(vault) == frozen


@pytest.mark.parametrize('alias', ['9702_s23_qp_22_q2', '9702_S23_22_Q002', '9702_S23_QP_22_Q0002'])
def test_next_question_rejects_active_canonical_whole_question_aliases(tmp_path, monkeypatch, alias):
    from tutorlib.topicals import identity
    ex, vault, _, _, _, _ = prepared(tmp_path, monkeypatch)
    add_other_scope(ex, vault, tmp_path, qid=alias)
    active = ex._active_topical_bank(vault)[2]['items'][-1]
    assert identity(active) == '9702_s23_22_q2:a'
    path = ex.job_dir('multi') / 'state.json'; before = path.read_bytes(); frozen = vault_bytes(vault)
    with pytest.raises(ValueError, match='already processed or active'):
        ex.next_question('multi', '9702_s23_22_q2', 'Already active through canonical alias')
    assert path.read_bytes() == before and vault_bytes(vault) == frozen


def test_next_question_rejects_processed_canonical_whole_question_alias(tmp_path, monkeypatch):
    ex, vault, _, _, _, _ = prepared(tmp_path, monkeypatch)
    with ex.state_lock('multi') as current:
        historical = copy.deepcopy(current['focus_history'][0])
        historical['selected_item_scope']['official_qid'] = '9702_S23_QP_22_Q0002'
        current['focus_history'].insert(0, historical)
    path = ex.job_dir('multi') / 'state.json'; before = path.read_bytes(); frozen = vault_bytes(vault)
    with pytest.raises(ValueError, match='already processed or active'):
        ex.next_question('multi', '9702_s23_22_q2', 'Already processed through canonical alias')
    assert path.read_bytes() == before and vault_bytes(vault) == frozen
