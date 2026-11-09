"""Native MCQ Q/MS crops stay independently reviewed while only Q/reference is public."""
import copy
import json

import pytest
from PIL import Image
from library_assets import write_asset
from test_extraction import make_pdf


def prepared(tmp_path, monkeypatch, *, with_reference=False):
    import test_extraction_next_question as fixture
    monkeypatch.setattr(fixture, 'publish_current', lambda *a, **kw: None)
    ex, vault, _, _, _, _ = fixture.prepared(tmp_path, monkeypatch)
    if with_reference:
        ref = write_asset(vault, 'Library/Courses/9702/Sources/Library/reference.pdf',
                          make_pdf(tmp_path / 'reference.pdf', ['Reference constants']).read_bytes())
        ex.reference_sources('multi', [ref + '=1'], 'Distinct auxiliary constants only', 'Before first native maker')
    state = ex.load('multi'); path = ex.candidate_path(state); data = json.loads(path.read_text()); q = data['questions'][0]
    qp, ms = state['sources'][:2]
    region = lambda source, page: {'source_id': source['id'], 'source_sha256': source['sha256'], 'page': page, 'box': [0, 0, 1, 1]}
    q.update(kind='mcq', complete=True, uncertainty=[], answer='A', stem='Which quantity is a vector?',
        options={'A': 'displacement', 'B': 'distance', 'C': 'speed', 'D': 'time'},
        regions=[region(qp, 1)], mark_scheme_regions=[region(ms, 2)])
    q.pop('scheme')
    q['media_regions'] = {'question.png': copy.deepcopy(q['regions'][0]), 'scheme.png': copy.deepcopy(q['mark_scheme_regions'][0])}
    if with_reference:
        Image.new('RGB', (20, 20), 'green').save(path.parent / 'reference.png')
        q.update(reference_regions=[region(state['sources'][-1], 1)], reference_media=['reference.png'])
    data['source_coverage'] = [{'source_id': s['id'], 'source_sha256': s['sha256'],
        'inspected_pages': s['selected_page_numbers'], 'no_relevant_content': False, 'reason': ''} for s in state['sources']]
    def save(inspected=None):
        path.write_text(json.dumps(data))
        review = ex.job_dir('multi') / 'review.json'
        review.write_text(json.dumps({'candidate_sha256': ex.digest(path), 'verdict': 'pass', 'findings': [],
            'inspected_images': [ex.digest(path.parent / name) for name in (q['media'] + q.get('reference_media', []) if inspected is None else inspected)]}))
        with ex.state_lock('multi') as current:
            current['jobs']['extract'].update(exit=0, finished='disposable native MCQ repair', output_sha256=ex.digest(path))
            current['jobs']['review'].update(exit=0, finished='disposable independent review', output_sha256=ex.digest(review))
    save()
    return ex, vault, path, q, save


@pytest.mark.parametrize('with_reference', [False, True])
def test_native_mcq_private_key_is_registered_but_excluded_from_published_public_view(tmp_path, monkeypatch, with_reference):
    from tutorlib import packs, session, store, views
    ex, vault, path, q, _ = prepared(tmp_path, monkeypatch, with_reference=with_reference)
    raw = path.read_bytes(); state = ex.register('multi')
    mapping = next(iter(state['registered_records'].values()))
    assert set(mapping) == set(q['media'] + q.get('reference_media', []))
    from tutorlib.asset_library import AssetLibrary
    catalog = AssetLibrary(vault)
    assert catalog.read(mapping['scheme.png']) == (path.parent / 'scheme.png').read_bytes()
    sidecar = json.loads(catalog.read(catalog.record(mapping['scheme.png'])['provenance']['sidecars'][0]))
    assert sidecar['regions'] == [q['media_regions']['scheme.png']]
    assert sidecar['pdf'] == q['mark_scheme_regions'][0]['source_id']
    assert ex.digest(path.parent / 'scheme.png') in sidecar['review']['inspected_images']
    batch = tmp_path / 'batch'; ex.prepare_publication('multi', batch)
    item = json.loads((batch / 'bank.json').read_text())['items'][0]
    public = [mapping[name] for name in q['question_media'] + q.get('reference_media', [])]
    assert item['images'] == public
    assert mapping['scheme.png'] not in item['images']
    ex.publish('multi', batch)
    runtime = packs.Packs(store.Vault(vault)); assert not runtime.topical_errors
    tutor = session.Tutor(store.Vault(vault))
    assert 'error' not in tutor.start('topical', focus=['9702-2.1'], topical_count=1, topical_types=['mcq'])
    view = tutor.next()['items'][0]
    assert view['images'] == public and 'answer' not in view
    assert mapping['scheme.png'] not in json.dumps(view)
    assert mapping['scheme.png'] not in views.question_block(view, vault_root=vault)
    assert path.read_bytes() == raw


@pytest.mark.parametrize('fault', ['absent', 'partial', 'empty-private', 'swapped', 'wrong-source', 'wrong-hash',
                                  'wrong-page', 'wrong-box', 'missing-binding', 'extra-binding', 'renamed-key', 'q-order', 'key-order'])
def test_native_mcq_missing_or_mislabeled_media_partition_remains_pending(tmp_path, monkeypatch, fault):
    ex, _, path, q, save = prepared(tmp_path, monkeypatch)
    if fault == 'absent': q.pop('question_media'); q.pop('mark_scheme_media')
    elif fault == 'partial': q.pop('mark_scheme_media')
    elif fault == 'empty-private': q['mark_scheme_media'] = []; q['question_media'] = list(q['media'])
    elif fault == 'swapped': q['question_media'], q['mark_scheme_media'] = q['mark_scheme_media'], q['question_media']
    elif fault == 'wrong-source': q['media_regions']['question.png'] = copy.deepcopy(q['mark_scheme_regions'][0])
    elif fault == 'wrong-hash': q['media_regions']['question.png']['source_sha256'] = '0' * 64
    elif fault == 'wrong-page': q['media_regions']['question.png']['page'] = 2
    elif fault == 'wrong-box': q['media_regions']['question.png']['box'] = [0, 0, 2, 1]
    elif fault == 'missing-binding': q.pop('media_regions')
    elif fault == 'extra-binding': q['media_regions']['unlisted.png'] = copy.deepcopy(q['regions'][0])
    elif fault == 'renamed-key': (path.parent / 'question.png').write_bytes((path.parent / 'scheme.png').read_bytes())
    elif fault == 'key-order':
        Image.new('RGB', (20, 20), 'cyan').save(path.parent / 'key2.png')
        q['media'].append('key2.png'); q['mark_scheme_media'] = ['key2.png', 'scheme.png']
        q['media_regions']['key2.png'] = copy.deepcopy(q['mark_scheme_regions'][0])
    else:
        (path.parent / 'question2.png').write_bytes((path.parent / 'question.png').read_bytes())
        q['media'] = ['question.png', 'question2.png', 'scheme.png']
        q['question_media'] = ['question2.png', 'question.png']
        q['media_regions']['question2.png'] = copy.deepcopy(q['regions'][0])
    save()
    state = ex.check('multi'); assert state['stage'] == 'pending', state['problems']
    with pytest.raises(ValueError): ex.register('multi')


def test_native_mcq_private_key_requires_hash_bound_independent_inspection(tmp_path, monkeypatch):
    ex, _, _, q, save = prepared(tmp_path, monkeypatch)
    save(inspected=q['question_media'])
    assert any('visual inspection' in value for value in ex.check('multi')['problems'])
    with pytest.raises(ValueError): ex.register('multi')


def test_legacy_unfocused_mcq_without_partition_keeps_its_existing_public_media(tmp_path, monkeypatch):
    from test_extraction_structured import structured_case
    ex, _, q, _, save = structured_case(tmp_path, monkeypatch)
    q.update(kind='mcq', answer='A', options={'A': 'vector', 'B': 'scalar', 'C': 'speed', 'D': 'time'}, media=['circuit.png'])
    q.pop('question_media'); q.pop('mark_scheme_media'); save()
    assert ex.check('diagram')['stage'] == 'reviewed'
    ex.register('diagram'); batch = tmp_path / 'legacy'; ex.prepare_publication('diagram', batch)
    assert len(json.loads((batch / 'bank.json').read_text())['items'][0]['images']) == 1


def direct_prepared(tmp_path, monkeypatch):
    from test_extraction_structured import structured_case
    ex, _, q, vault, _ = structured_case(tmp_path, monkeypatch)
    monkeypatch.delenv('STEM_LIBRARY_ROOT', raising=False)
    refs = []
    for role in ('qp', 'ms'):
        refs.append(write_asset(vault, f'Library/Courses/9702/Sources/PastPapers/9702/2020/s/9702_s20_{role}_12.pdf',
                                make_pdf(tmp_path / (role + '.pdf'), ['Cover', 'Question' if role == 'qp' else 'Official key']).read_bytes()))
    ex.create('direct', '9702', provider='codex', scope='questions', sources=refs); ex.inventory('direct'); state = ex.plan('direct')
    assert not state.get('source_rebase_history') and all(s['kind'] == 'papers:9702' for s in state['sources'])
    path = ex.candidate_path(state); path.parent.mkdir(parents=True)
    Image.new('RGB', (20, 20), 'red').save(path.parent / 'q.png'); Image.new('RGB', (20, 20), 'blue').save(path.parent / 'key.png')
    region = lambda s: {'source_id': s['id'], 'source_sha256': s['sha256'], 'page': 2, 'box': [0, 0, 1, 1]}
    q.update(kind='mcq', official_qid='9702_s20_12_q10', answer='A', options={'A': 'vector', 'B': 'scalar', 'C': 'speed', 'D': 'time'},
             media=['q.png', 'key.png'], question_media=['q.png'], mark_scheme_media=['key.png'],
             regions=[region(state['sources'][0])], mark_scheme_regions=[region(state['sources'][1])])
    q['media_regions'] = {'q.png': q['regions'][0], 'key.png': q['mark_scheme_regions'][0]}
    def save():
        path.write_text(json.dumps({'questions': [q], 'diagrams': [], 'source_coverage': [{'source_id': s['id'],
            'source_sha256': s['sha256'], 'inspected_pages': [1, 2], 'no_relevant_content': False, 'reason': ''} for s in state['sources']]}))
        (ex.job_dir('direct') / 'review.json').write_text(json.dumps({'candidate_sha256': ex.digest(path), 'verdict': 'pass', 'findings': [],
             'inspected_images': [ex.digest(path.parent / name) for name in q['media']]}))
        with ex.state_lock('direct') as current: current['jobs']['review'].update(exit=0)
    save()
    return ex, vault, path, q, save


@pytest.mark.parametrize('missing_partition', [False, True])
def test_direct_authoritative_native_QP_MS_inventory_has_same_mcq_privacy_requirement(tmp_path, monkeypatch, missing_partition):
    ex, _, _, q, save = direct_prepared(tmp_path, monkeypatch)
    if missing_partition: q.pop('question_media'); q.pop('mark_scheme_media'); save()
    if missing_partition:
        assert ex.check('direct')['stage'] == 'pending'
        with pytest.raises(ValueError): ex.register('direct')
    else:
        ex.register('direct'); batch = tmp_path / 'native-direct'; ex.prepare_publication('direct', batch)
        assert len(json.loads((batch / 'bank.json').read_text())['items'][0]['images']) == 1
        ex.publish('direct', batch)


def test_native_mcq_publication_rejects_key_inserted_into_public_images(tmp_path, monkeypatch):
    ex, _, _, _, _ = prepared(tmp_path, monkeypatch)
    state = ex.register('multi'); mapping = next(iter(state['registered_records'].values()))
    batch = tmp_path / 'tampered'; ex.prepare_publication('multi', batch)
    bank = json.loads((batch / 'bank.json').read_text()); bank['items'][0]['images'].append(mapping['scheme.png'])
    (batch / 'bank.json').write_text(json.dumps(bank))
    with pytest.raises(ValueError, match='registered media'): ex.publish('multi', batch)


def test_legacy_explicit_mcq_partition_is_respected_without_native_source_map(tmp_path, monkeypatch):
    from test_extraction_structured import structured_case
    ex, _, q, _, save = structured_case(tmp_path, monkeypatch)
    q.update(kind='mcq', answer='A', options={'A': 'vector', 'B': 'scalar', 'C': 'speed', 'D': 'time'}); save()
    assert ex.check('diagram')['stage'] == 'reviewed'
    ex.register('diagram'); batch = tmp_path / 'legacy-explicit'; ex.prepare_publication('diagram', batch)
    assert len(json.loads((batch / 'bank.json').read_text())['items'][0]['images']) == 1
