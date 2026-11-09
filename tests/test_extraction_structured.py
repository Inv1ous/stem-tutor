"""Structured imports retain their reviewed rubric and hide official answer media."""
import copy
import json

import pytest

from fixtures import make_vault
from test_extraction import complete_coverage, extraction, reviewed_diagram


def structured_case(tmp_path, monkeypatch):
    from PIL import Image

    ex = extraction()
    path = reviewed_diagram(ex, tmp_path, monkeypatch)
    diagram = json.loads(path.read_text())['diagrams'][0]
    vault = make_vault(tmp_path)
    # Runtime and extraction validate against the same disposable graph.
    monkeypatch.setenv('STEM_TUTOR_VAULT', str(vault))
    monkeypatch.setenv('STEM_LIBRARY_SPECS', str(vault / '.tutor/packs/v1/specs'))
    (vault / '.tutor/packs/v1/papers.json').write_text('{"papers": []}')
    Image.new('RGB', (200, 150), 'blue').save(path.parent / 'official-ms.png')
    q = {**diagram, 'id': 'written-part-a', 'official_qid': '9702_s24_22_q1', 'part': 'a',
         'kind': 'structured', 'prerequisites': [], 'answer': 'A vector includes direction.',
         'stem': 'State what distinguishes a vector from a scalar. Answer part (a) only.',
         'marks': 1, 'scheme': [{'mark': 'B1', 'point': 'A vector includes direction.'}],
         'syllabus': ['9702-2.1'], 'kcs': ['9702-2.1.1'],
         'mark_scheme_regions': [{**diagram['regions'][0], 'box': [0, .5, 1, 1]}],
         'media': ['circuit.png', 'official-ms.png'],
         'question_media': ['circuit.png'], 'mark_scheme_media': ['official-ms.png']}
    with ex.state_lock('diagram') as state:
        state['scope'] = 'questions'

    def save(question=q):
        path.write_text(json.dumps({'questions': [question], 'diagrams': [],
                                   'source_coverage': complete_coverage(ex.load('diagram'))}))
        (ex.job_dir('diagram') / 'review.json').write_text(json.dumps({
            'candidate_sha256': ex.digest(path), 'verdict': 'pass', 'findings': [],
            'inspected_images': [ex.digest(path.parent / name) for name in q['media']]}))

    save()
    return ex, path, q, vault, save


def batch_for(ex, q, tmp_path):
    state = ex.register('diagram')
    context = ex.hashlib.sha256(json.dumps(q, sort_keys=True).encode()).hexdigest()[:12]
    registered = state['registered_records'][context]
    item = {key: copy.deepcopy(q[key]) for key in ('id', 'kind', 'stem', 'answer', 'marks', 'scheme', 'kcs')}
    item.update(source={'type': 'past', 'qid': q['official_qid'], 'part': q['part'],
                        'extraction_regions': q['regions'], 'mark_scheme_regions': q['mark_scheme_regions'],
                        'extraction_prerequisites': q['prerequisites']},
                images=[registered[name] for name in q['question_media']],
                topical={'reviewed': True, 'revision': '2025-2027', 'requires': q['syllabus'],
                         'chapters': q['syllabus'], 'support': {}})
    batch = tmp_path / 'batch'
    batch.mkdir()
    bank = {'format_version': 1, 'syllabus_versions': {'9702': '2025-2027'}, 'items': [item]}
    (batch / 'bank.json').write_text(json.dumps(bank))
    (batch / 'report.json').write_text('{"preparation":{"expected_current":null}}')
    return batch, bank, registered


def test_reviewed_structured_part_reaches_runtime_without_official_answer_image(tmp_path, monkeypatch):
    from tutorlib import packs, session, store

    ex, path, q, vault, _ = structured_case(tmp_path, monkeypatch)
    before = path.read_bytes()
    checked = ex.check('diagram')
    assert checked['stage'] == 'reviewed', checked['problems']
    batch, _, registered = batch_for(ex, q, tmp_path)
    result = ex.publish('diagram', batch)
    published = json.loads((vault / result['release'] / 'bank.json').read_text())['items'][0]
    assert published['scheme'] == [{'mark': 'B1', 'point': 'A vector includes direction.'}]
    assert published['images'] == [registered['circuit.png']]
    assert registered['official-ms.png'] not in published['images']
    assert path.read_bytes() == before
    runtime = packs.Packs(store.Vault(vault))
    assert not runtime.topical_errors
    assert any(row['id'] == 'written-part-a' for row in runtime.items_for('9702-2.1.1'))
    tutor = session.Tutor(store.Vault(vault))
    started = tutor.start('topical', focus=['9702-2.1'], topical_count=1,
                          topical_types=['structured'])
    assert 'error' not in started, started
    view = tutor.next()['items'][0]
    assert view['kind'] == 'structured'
    assert 'scheme' not in view and 'answer' not in view
    assert registered['official-ms.png'] not in json.dumps(view)


@pytest.mark.parametrize('change', [
    {'scheme': []}, {'scheme': [{'point': ''}]}, {'scheme': [{'point': 'x', 'check': {'kind': 'unknown'}}]},
    {'marks': 2}, {'marks': True}, {'stem': ''}, {'answer': None},
    {'question_media': []}, {'question_media': ['official-ms.png']},
    {'mark_scheme_media': []}, {'official_qid': 'P1_s24_22_q1'},
])
def test_incomplete_structured_rubric_identity_or_media_roles_remain_pending(tmp_path, monkeypatch, change):
    ex, _, q, _, save = structured_case(tmp_path, monkeypatch)
    save({**q, **change})
    assert ex.check('diagram')['stage'] == 'pending'


def test_new_structured_extraction_requires_explicit_marks(tmp_path, monkeypatch):
    ex, _, q, _, save = structured_case(tmp_path, monkeypatch)
    del q['marks']
    save()
    assert ex.check('diagram')['stage'] == 'pending'


@pytest.mark.parametrize('change', [
    {'kind': 'mcq'}, {'stem': 'An unreviewed question.'}, {'marks': 2},
    {'scheme': [{'mark': 'B1', 'point': 'Unreviewed answer.'}]},
])
def test_publication_cannot_change_reviewed_structured_content(tmp_path, monkeypatch, change):
    ex, _, q, vault, _ = structured_case(tmp_path, monkeypatch)
    batch, bank, _ = batch_for(ex, q, tmp_path)
    bank['items'][0].update(change)
    (batch / 'bank.json').write_text(json.dumps(bank))
    with pytest.raises(ValueError, match='reviewed'):
        ex.publish('diagram', batch)
    assert not (vault / '.tutor/topicals/CURRENT').exists()


@pytest.mark.parametrize('change', [
    {'requires': ['9702-2.1'], 'support': {}},
    {'requires': ['9702-2.1', '9702-2.2'],
     'support': {'9702-2.2': 'Unreviewed answer-bearing fact'}},
])
def test_publication_cannot_bypass_reviewed_prerequisites_or_add_unreviewed_support(tmp_path, monkeypatch, change):
    ex, _, q, vault, save = structured_case(tmp_path, monkeypatch)
    graph_path = vault / '.tutor/packs/v1/specs/9702/graph.json'
    graph = json.loads(graph_path.read_text())
    graph['subtopics'].append({'id': '9702-2.2', 'title': 'Prerequisite', 'topic': '9702-2'})
    graph_path.write_text(json.dumps(graph))
    q['prerequisites'] = ['9702-2.2']
    save()
    batch, bank, _ = batch_for(ex, q, tmp_path)
    bank['items'][0]['topical'].update(change)
    (batch / 'bank.json').write_text(json.dumps(bank))
    with pytest.raises(ValueError, match='reviewed.*prerequisite|support'):
        ex.publish('diagram', batch)
    assert not (vault / '.tutor/topicals/CURRENT').exists()


def test_publication_rejects_reviewed_mark_scheme_image_in_question_pages(tmp_path, monkeypatch):
    ex, _, q, vault, _ = structured_case(tmp_path, monkeypatch)
    batch, bank, registered = batch_for(ex, q, tmp_path)
    bank['items'][0]['images'].append(registered['official-ms.png'])
    (batch / 'bank.json').write_text(json.dumps(bank))
    with pytest.raises(ValueError, match='media'):
        ex.publish('diagram', batch)
    assert not (vault / '.tutor/topicals/CURRENT').exists()


def test_structured_role_validation_never_hashes_media_outside_candidates(tmp_path, monkeypatch):
    ex, _, q, _, save = structured_case(tmp_path, monkeypatch)
    outside = tmp_path / 'outside.png'
    outside.write_bytes(b'private bytes')
    q['media'][1] = str(outside)
    q['mark_scheme_media'] = [str(outside)]
    save()
    original_digest = ex.digest

    def digest(path):
        assert path != outside, 'unsafe media was read before candidate path validation'
        return original_digest(path)

    monkeypatch.setattr(ex, 'digest', digest)
    checked = ex.check('diagram')
    assert checked['stage'] == 'pending'
    assert 'candidate media unavailable or unsafe' in checked['problems']


def test_prepare_adds_structured_part_without_changing_existing_active_questions(tmp_path, monkeypatch):
    from tutorlib.asset_library import AssetLibrary
    import topicals

    ex, _, q, vault, _ = structured_case(tmp_path, monkeypatch)
    seed, bank, registered = batch_for(ex, q, tmp_path)
    old = {**copy.deepcopy(bank['items'][0]), 'id': 'existing-written',
           'source': {**bank['items'][0]['source'], 'qid': '9702_s23_22_q2'}}
    bank['items'] = [old]
    (seed / 'bank.json').write_text(json.dumps(bank))
    first = topicals.publish(seed, vault)
    old_bytes = AssetLibrary(vault).read(first['release'] + '/bank.json')
    prepared = tmp_path / 'prepared'
    ex.prepare_publication('diagram', prepared)
    candidate = json.loads((prepared / 'bank.json').read_text())
    assert candidate['items'][0] == old and len(candidate['items']) == 2
    assert candidate['items'][1]['images'] == [registered['circuit.png']]
    assert (vault / '.tutor/topicals/CURRENT').read_text().strip() == first['version']
    published = ex.publish('diagram', prepared)
    active = json.loads(AssetLibrary(vault).read(published['release'] + '/bank.json'))
    assert active['items'][0] == old and len(active['items']) == 2
    assert AssetLibrary(vault).read(first['release'] + '/bank.json') == old_bytes


def test_prepare_maps_reviewed_kc_prerequisites_to_runtime_chapters(tmp_path, monkeypatch):
    ex, _, q, _, save = structured_case(tmp_path, monkeypatch)
    q['kcs'] = ['9702-2.1.4']
    q['prerequisites'] = ['9702-2.1.1']
    save()
    ex.register('diagram')
    prepared = tmp_path / 'prepared'
    ex.prepare_publication('diagram', prepared)
    item = json.loads((prepared / 'bank.json').read_text())['items'][0]
    assert item['topical']['requires'] == ['9702-2.1']
    assert item['source']['extraction_prerequisites'] == ['9702-2.1.1']


def test_extraction_publication_cannot_remove_an_existing_active_question(tmp_path, monkeypatch):
    import topicals

    ex, _, q, vault, _ = structured_case(tmp_path, monkeypatch)
    batch, bank, _ = batch_for(ex, q, tmp_path)
    old = {**copy.deepcopy(bank['items'][0]), 'id': 'existing-written',
           'source': {**bank['items'][0]['source'], 'qid': '9702_s23_22_q2'}}
    bank['items'] = [old]
    (batch / 'bank.json').write_text(json.dumps(bank))
    first = topicals.publish(batch, vault)
    bank['items'] = [{**old, 'id': q['id'], 'source': {**old['source'], 'qid': q['official_qid']}}]
    (batch / 'bank.json').write_text(json.dumps(bank))
    with pytest.raises(ValueError, match='existing|preparation'):
        ex.publish('diagram', batch)
    assert (vault / '.tutor/topicals/CURRENT').read_text().strip() == first['version']
