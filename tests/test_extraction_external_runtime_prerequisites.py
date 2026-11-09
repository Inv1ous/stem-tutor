"""Declared external KC prerequisites retain graph authority and revision bindings."""
import copy
import json

import pytest
from library_assets import copy_to_vault, write_asset
from test_extraction_structured import structured_case


def prepared(tmp_path, monkeypatch):
    ex, path, q, vault, save = structured_case(tmp_path, monkeypatch)
    target = copy_to_vault('build/out/specs/P1/graph.json', vault)
    adapter = vault / '.tutor/packs/v1/specs/P1/graph.json'; adapter.parent.mkdir(parents=True)
    adapter.symlink_to(target)
    manifest = vault / '.tutor/packs/v1/manifest.json'; data = json.loads(manifest.read_text())
    data['specs'].append('P1'); manifest.write_text(json.dumps(data))
    graph = vault / '.tutor/packs/v1/specs/9702/graph.json'; data = json.loads(graph.read_text())
    data['kcs'][0]['prereqs'] = ['P1-1.5']; graph.write_text(json.dumps(data))
    q['prerequisites'] = ['P1-1.5']; save()
    return ex, path, q, vault, save, target


def test_registered_external_KC_maps_to_version_bound_subtopic_through_publication_and_eligibility(tmp_path, monkeypatch):
    from tutorlib import packs, store, topicals
    ex, path, q, vault, _, _ = prepared(tmp_path, monkeypatch)
    raw = path.read_bytes(); ex.register('diagram')
    batch = tmp_path / 'external-batch'; ex.prepare_publication('diagram', batch)
    bank = json.loads((batch / 'bank.json').read_text()); item = bank['items'][0]
    assert item['topical']['requires'] == ['9702-2.1', 'P1-1']
    assert item['topical']['prerequisite_versions'] == {'P1': '2018 Issue 3'}
    assert bank['syllabus_versions']['P1'] == '2018 Issue 3'
    assert item['source']['extraction_prerequisites'] == ['P1-1.5']
    ex.publish('diagram', batch)
    runtime = packs.Packs(store.Vault(vault)); assert not runtime.topical_errors
    published = runtime.topicals.items[0]
    missing = topicals.eligibility(published, '9702-2.1', {}, runtime, unassisted=True)
    assert missing['status'] == 'unavailable' and missing['missing'] == ['P1-1']
    ready = topicals.eligibility(published, '9702-2.1', {'started_chapters': ['P1-1']}, runtime, unassisted=True)
    assert ready['status'] == 'solvable'
    assert path.read_bytes() == raw


@pytest.mark.parametrize('fault', ['undeclared', 'unknown', 'missing-target', 'tampered-target', 'runtime-unavailable', 'authority-runtime-disagreement'])
def test_external_mapping_rejects_missing_unknown_or_tampered_graph_authority(tmp_path, monkeypatch, fault):
    ex, path, q, vault, save, target = prepared(tmp_path, monkeypatch)
    if fault == 'undeclared':
        graph = vault / '.tutor/packs/v1/specs/9702/graph.json'; data = json.loads(graph.read_text())
        data['kcs'][0]['prereqs'] = []; graph.write_text(json.dumps(data))
    elif fault == 'unknown':
        q['prerequisites'] = ['P1-999.1']
        graph = vault / '.tutor/packs/v1/specs/9702/graph.json'; data = json.loads(graph.read_text())
        data['kcs'][0]['prereqs'] = ['P1-999.1']; graph.write_text(json.dumps(data)); save()
    elif fault == 'missing-target': (vault / '.tutor/packs/v1/specs/P1/graph.json').unlink()
    elif fault == 'tampered-target': target.write_bytes(target.read_bytes() + b' ')
    elif fault == 'authority-runtime-disagreement':
        authority = tmp_path / 'authority'; (authority / '9702').mkdir(parents=True); (authority / 'P1').mkdir()
        (authority / '9702/graph.json').write_bytes((vault / '.tutor/packs/v1/specs/9702/graph.json').read_bytes())
        altered = json.loads(target.read_bytes())
        next(row for row in altered['kcs'] if row['id'] == 'P1-1.5')['subtopic'] = 'P1-2'
        ref = write_asset(vault, 'Library/Courses/P1/Specifications/altered-graph.json', json.dumps(altered).encode())
        from tutorlib.asset_library import AssetLibrary
        (authority / 'P1/graph.json').symlink_to(AssetLibrary(vault).resolve(ref))
        monkeypatch.setenv('STEM_LIBRARY_SPECS', str(authority))
    else:
        # Runtime manifest omits the otherwise registered external graph.
        manifest = vault / '.tutor/packs/v1/manifest.json'; data = json.loads(manifest.read_text())
        data['specs'].remove('P1'); manifest.write_text(json.dumps(data))
    before = path.read_bytes()
    with pytest.raises(ValueError):
        ex.register('diagram')
        ex.prepare_publication('diagram', tmp_path / 'rejected')
    assert path.read_bytes() == before and not (tmp_path / 'rejected').exists()


@pytest.mark.parametrize('fault', ['undeclared-requirement', 'cross-course-chapter', 'assessed-external',
    'item-version-missing', 'item-version-stale', 'bank-version-missing', 'bank-version-stale'])
def test_runtime_rejects_arbitrary_cross_course_metadata_and_unbound_versions(tmp_path, monkeypatch, fault):
    from tutorlib import packs, store, topicals
    ex, _, _, vault, _, _ = prepared(tmp_path, monkeypatch)
    ex.register('diagram'); batch = tmp_path / 'batch'; ex.prepare_publication('diagram', batch)
    bank = json.loads((batch / 'bank.json').read_text()); item = bank['items'][0]
    if fault == 'undeclared-requirement': item['topical']['requires'].append('P1-2')
    elif fault == 'cross-course-chapter': item['topical']['chapters'] = ['P1-1']
    elif fault == 'assessed-external': item['kcs'].append('P1-1.5')
    elif fault == 'item-version-missing': item['topical'].pop('prerequisite_versions')
    elif fault == 'item-version-stale': item['topical']['prerequisite_versions']['P1'] = 'stale'
    elif fault == 'bank-version-missing': bank['syllabus_versions'].pop('P1')
    else: bank['syllabus_versions']['P1'] = 'stale'
    runtime = packs.Packs(store.Vault(vault))
    with pytest.raises(ValueError): topicals.validate_bank(bank, runtime, vault)
    (batch / 'bank.json').write_text(json.dumps(bank))
    with pytest.raises(ValueError): ex.publish('diagram', batch)


def test_changed_runtime_external_version_invalidates_eligibility(tmp_path, monkeypatch):
    from tutorlib import packs, store, topicals
    ex, _, _, vault, _, _ = prepared(tmp_path, monkeypatch)
    ex.register('diagram'); batch = tmp_path / 'batch'; ex.prepare_publication('diagram', batch)
    item = json.loads((batch / 'bank.json').read_text())['items'][0]
    runtime = packs.Packs(store.Vault(vault)); runtime.syllabus_versions['P1'] = 'new authoritative version'
    assert topicals.eligibility(item, '9702-2.1', {'started_chapters': ['P1-1']}, runtime, unassisted=True)['status'] == 'unverified'


def test_additive_external_publication_preserves_old_items_and_learner_history(tmp_path, monkeypatch):
    ex, path, q, vault, _, _ = prepared(tmp_path, monkeypatch)
    import topicals as importer
    old = {key: copy.deepcopy(q[key]) for key in ('kind', 'stem', 'answer', 'marks', 'scheme', 'kcs')}
    old.update(id='existing-local-question', source={'type': 'past', 'qid': '9702_s24_22_q99', 'part': 'a'},
               topical={'reviewed': True, 'revision': '2025-2027', 'requires': ['9702-2.1'], 'chapters': ['9702-2.1'], 'support': {}})
    first = tmp_path / 'old-bank'; first.mkdir()
    (first / 'bank.json').write_text(json.dumps({'format_version': 1, 'syllabus_versions': {'9702': '2025-2027'}, 'items': [old]}))
    (first / 'report.json').write_text(json.dumps({'preparation': {'expected_current': None}}))
    importer.publish(first, vault)
    history = vault / '.tutor/events/preserved.jsonl'; history.parent.mkdir(parents=True, exist_ok=True)
    history.write_bytes(b'{"immutable":"prior learner history"}\n'); historical = history.read_bytes(); candidate = path.read_bytes()
    prior = ex._active_topical_bank(vault)[2]['items']
    ex.register('diagram'); batch = tmp_path / 'additive'; ex.prepare_publication('diagram', batch)
    assert json.loads((batch / 'bank.json').read_text())['items'][:1] == prior
    ex.publish('diagram', batch)
    assert ex._active_topical_bank(vault)[2]['items'][:1] == prior
    assert history.read_bytes() == historical and path.read_bytes() == candidate
