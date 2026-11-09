"""Reference images remain separate from QP/MS while reaching reviewed learner views."""
import copy
import json
from pathlib import Path

import pytest
from PIL import Image
from library_assets import write_asset
from test_extraction import make_pdf
from test_extraction_next_question import prepared as scope_job


def prepared(tmp_path, monkeypatch):
    # Intercept the fixture at its real pre-first-native-maker seam.
    import test_extraction_next_question as fixture
    publish = fixture.publish_current
    def stage(ex, task_path, number, **kwargs):
        ref = write_asset(ex.library.learner_vault(), 'Library/Courses/9702/Sources/Library/reference.pdf',
                          make_pdf(tmp_path / 'ref.pdf', ['Later cover', 'Gas constant', 'Atomic table']).read_bytes())
        ex.reference_sources('multi', [ref + '=1-3'], 'Distinct later-edition constants/table only', 'Native reference context')
    monkeypatch.setattr(fixture, 'publish_current', stage)
    ex, vault, _, _, _, _ = scope_job(tmp_path, monkeypatch)
    monkeypatch.setattr(fixture, 'publish_current', publish)
    state = ex.load('multi'); path = ex.candidate_path(state); data = json.loads(path.read_text()); q = data['questions'][0]
    qp, ms, auxiliary = state['sources']
    region = lambda source, page: {'source_id': source['id'], 'source_sha256': source['sha256'], 'page': page, 'box': [0, 0, 1, 1]}
    q.update(complete=True, uncertainty=[], regions=[region(qp, 1)], mark_scheme_regions=[region(ms, 2)],
             reference_regions=[region(auxiliary, 2), region(auxiliary, 3)], reference_media=['constant.png', 'table.png'])
    for name, color in [('constant.png', 'green'), ('table.png', 'yellow')]:
        Image.new('RGB', (20, 20), color).save(path.parent / name)
    q['auxiliary_reference'] = {'source_id': auxiliary['id'], 'source_sha256': auxiliary['sha256'],
        'evidence_role': 'auxiliary_reference', 'reference_purpose': auxiliary['reference_purpose'],
        'regions': copy.deepcopy(q['reference_regions']), 'media': list(q['reference_media']),
        'learner_reference_text': 'Descriptive metadata must not become learner question text.'}
    data['source_coverage'] = [{'source_id': s['id'], 'source_sha256': s['sha256'],
        'inspected_pages': s['selected_page_numbers'], 'no_relevant_content': False, 'reason': ''} for s in state['sources']]
    def save(inspected=None):
        path.write_text(json.dumps(data))
        review = ex.job_dir('multi') / 'review.json'
        review.write_text(json.dumps({'candidate_sha256': ex.digest(path), 'verdict': 'pass', 'findings': [],
            'inspected_images': [ex.digest(path.parent / f) for f in (inspected if inspected is not None else q['media'] + q.get('reference_media', []))]}))
        with ex.state_lock('multi') as current:
            current['jobs']['extract'].update(exit=1, finished='saved output; historical wrapper failed', output_sha256=ex.digest(path))
            current['jobs']['review'].update(exit=0, finished='disposable review', output_sha256=ex.digest(review))
            current['reliability_failures']['1']['extract'] = [{'issues': ['old failure']}, {'issues': ['old reference coverage error']}]
    save()
    return ex, vault, path, data, q, save


def test_flat_reference_attachments_have_valid_coverage_and_reach_reviewed_published_route(tmp_path, monkeypatch):
    from tutorlib import packs, session, store
    ex, vault, path, data, q, save = prepared(tmp_path, monkeypatch)
    raw = path.read_bytes(); state = ex.check('multi')
    assert state['stage'] == 'reviewed', state['problems']
    assert len(state['reliability_failures']['1']['extract']) == 2
    state = ex.register('multi')
    context = ex.hashlib.sha256(json.dumps(q, sort_keys=True).encode()).hexdigest()[:12]
    mapping = state['registered_records'][context]
    assert set(mapping) == set(q['media'] + q['reference_media'])
    from tutorlib.asset_library import AssetLibrary
    catalog = AssetLibrary(vault)
    for name in q['reference_media']:
        assert catalog.read(mapping[name]) == (path.parent / name).read_bytes()
        sidecar = json.loads(catalog.read(catalog.record(mapping[name])['provenance']['sidecars'][0]))
        assert sidecar['record']['reference_regions'] == q['reference_regions']
        region = q['reference_regions'][q['reference_media'].index(name)]
        assert sidecar['pdf'] == region['source_id'] and sidecar['regions'] == [region]
        assert sidecar['source_sha256'] == region['source_sha256']
        assert ex.digest(path.parent / name) in sidecar['review']['inspected_images']
    batch = tmp_path / 'batch'; ex.prepare_publication('multi', batch)
    item = json.loads((batch / 'bank.json').read_text())['items'][0]
    assert item['images'] == [mapping[name] for name in q['question_media'] + q['reference_media']]
    assert mapping['scheme.png'] not in item['images']
    assert item['source']['qid'] == q['official_qid']
    assert 'auxiliary_reference' not in item and 'learner_reference_text' not in json.dumps(item)
    ex.publish('multi', batch)
    runtime = packs.Packs(store.Vault(vault)); assert not runtime.topical_errors
    tutor = session.Tutor(store.Vault(vault))
    assert 'error' not in tutor.start('topical', focus=['9702-2.1'], topical_count=1, topical_types=['structured'])
    view = tutor.next()['items'][0]
    assert all(mapping[name] in json.dumps(view) for name in q['reference_media'])
    assert mapping['scheme.png'] not in json.dumps(view)
    from tutorlib import views
    rendered = views.question_block(view, vault_root=vault)
    assert all(mapping[name] in rendered for name in q['reference_media'])
    assert mapping['scheme.png'] not in rendered
    assert path.read_bytes() == raw
    proof = ex._published_scope_evidence(ex.load('multi'))
    assert all(name in proof['media_sha256'] for name in q['reference_media'])


@pytest.mark.parametrize('fault', ['undeclared', 'wrong-hash', 'bad-page', 'bad-box', 'missing-media',
    'unsafe-media', 'missing-regions', 'mismatch', 'ms-region', 'ms-media', 'renamed-ms', 'purpose', 'metadata', 'lineage'])
def test_invalid_reference_attachments_remain_pending(tmp_path, monkeypatch, fault):
    ex, _, path, data, q, save = prepared(tmp_path, monkeypatch)
    if fault == 'undeclared': q['reference_regions'][0]['source_id'] = 'asset:unknown'
    elif fault == 'wrong-hash': q['reference_regions'][0]['source_sha256'] = '0' * 64
    elif fault == 'bad-page': q['reference_regions'][0]['page'] = 4
    elif fault == 'bad-box': q['reference_regions'][0]['box'] = [0, 0, 2, 1]
    elif fault == 'missing-media': (path.parent / 'constant.png').unlink()
    elif fault == 'unsafe-media': q['reference_media'][0] = '../constant.png'
    elif fault == 'missing-regions': q.pop('reference_regions')
    elif fault == 'mismatch': q['reference_media'].pop()
    elif fault == 'ms-region': q['reference_regions'][0] = copy.deepcopy(q['mark_scheme_regions'][0])
    elif fault == 'ms-media': q['reference_media'][0] = 'scheme.png'
    elif fault == 'renamed-ms': (path.parent / 'constant.png').write_bytes((path.parent / 'scheme.png').read_bytes())
    elif fault == 'purpose': q['auxiliary_reference']['reference_purpose'] = 'Wrong purpose'
    elif fault == 'metadata': q['auxiliary_reference']['regions'] = []
    elif fault == 'lineage':
        with ex.state_lock('multi') as state:
            Path(state['reference_source_history'][0]['manifest']).write_text('{}')
    # Do not fabricate inspection hashes for intentionally missing files.
    save(inspected=[name for name in q['media'] + q.get('reference_media', []) if (path.parent / name).is_file()])
    if fault == 'lineage':
        with pytest.raises(ValueError): ex.check('multi')
    else:
        checked = ex.check('multi')
        assert checked['stage'] == 'pending', checked['problems']
        with pytest.raises(ValueError): ex.register('multi')


def test_uninspected_reference_images_cannot_register(tmp_path, monkeypatch):
    ex, _, _, _, q, save = prepared(tmp_path, monkeypatch)
    save(inspected=q['media'])
    assert any('visual inspection' in error for error in ex.check('multi')['problems'])
    with pytest.raises(ValueError): ex.register('multi')


@pytest.mark.parametrize('fault', ['drop-reference', 'reorder-reference', 'add-ms', 'drop-reference-provenance'])
def test_publication_requires_exact_reviewed_reference_media_and_regions(tmp_path, monkeypatch, fault):
    ex, _, _, _, q, _ = prepared(tmp_path, monkeypatch)
    ex.register('multi'); batch = tmp_path / 'batch'; ex.prepare_publication('multi', batch)
    bank = json.loads((batch / 'bank.json').read_text()); item = bank['items'][0]
    if fault == 'drop-reference': item['images'].pop()
    elif fault == 'reorder-reference': item['images'][-2:] = item['images'][-2:][::-1]
    elif fault == 'drop-reference-provenance': item['source'].pop('reference_regions')
    else:
        state = ex.load('multi'); mapping = next(iter(state['registered_records'].values()))
        item['images'].append(mapping['scheme.png'])
    (batch / 'bank.json').write_text(json.dumps(bank))
    with pytest.raises(ValueError, match='reviewed|regions'):
        ex.publish('multi', batch)


def test_changed_reference_image_invalidates_inspection_without_changing_candidate_bytes(tmp_path, monkeypatch):
    ex, _, path, _, _, _ = prepared(tmp_path, monkeypatch)
    candidate = path.read_bytes()
    Image.new('RGB', (20, 20), 'purple').save(path.parent / 'constant.png')
    state = ex.check('multi')
    assert state['stage'] == 'pending' and any('visual inspection' in value for value in state['problems'])
    assert path.read_bytes() == candidate
    with pytest.raises(ValueError): ex.register('multi')
