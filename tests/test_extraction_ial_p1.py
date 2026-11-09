"""Synthetic P1 schema compatibility through real gates; no native content claim."""
import copy
import json

import pytest
from ial_p1_fixtures import QID, QP, MS, p1_case
from tutorlib import packs, session, store, topicals
from tutorlib.asset_library import AssetLibrary


def prepare(tmp_path, monkeypatch, *, whole=False, prerequisite=False):
    ex, path, q, vault, save = p1_case(tmp_path, monkeypatch, whole=whole)
    if prerequisite:
        q['prerequisites'] = ['P1-2']; save()
    checked = ex.check('diagram')
    assert checked['stage'] == 'reviewed', checked['problems']
    ex.register('diagram')
    batch = tmp_path / 'p1-prepared'
    ex.prepare_publication('diagram', batch)
    return ex, path, q, vault, save, batch


@pytest.mark.parametrize('whole', [False, True])
def test_p1_schema_fixture_round_trip_reuses_exact_reviewed_import_gates(tmp_path, monkeypatch, whole):
    ex, path, q, vault, _, batch = prepare(tmp_path, monkeypatch, whole=whole)
    before = path.read_bytes(); ex.publish('diagram', batch)
    runtime = packs.Packs(store.Vault(vault)); assert not runtime.topical_errors
    item = runtime.topicals.items[0]
    assert topicals.identity(item) == QID
    for key in ('stem', 'answer', 'marks', 'kcs', 'kind'): assert item[key] == q[key]
    assert item['source']['part'] == ''
    assert item['source']['extraction_regions'] == q['regions']
    assert item['source']['mark_scheme_regions'] == q['mark_scheme_regions']
    assert item['source']['extraction_prerequisites'] == q['prerequisites']
    assert path.read_bytes() == before
    if whole:
        media = topicals.whole_rubric_media(item, vault)
        assert media and media[0]['reference'].startswith('Library/Courses/P1/Questions/Media/')
        assert media[0]['reference'] not in item['images']
    else: assert item['scheme'] == q['scheme']


def test_p1_focus_keeps_whole_record_sources_coverage_and_guards(tmp_path, monkeypatch):
    ex, path, q, vault, save = p1_case(tmp_path, monkeypatch)
    q.update(complete=False, uncertainty=['Synthetic review pending'], source_occurrences=[{'id': 'sentinel', 'regions': q['regions']}]); save()
    old = path.read_bytes()
    with ex.state_lock('diagram') as state:
        state['jobs']['extract'].update(exit=0, finished='saved', output_sha256=ex.digest(path))
        state['reliability_failures'] = {'1': {'extract': [{'issues': ['first']}, {'issues': ['second']}]}}
    with pytest.raises(ValueError, match='two-failure'):
        ex.focus('diagram', QID, 'synthetic focus', stage_missing_scheme=True)
    focused = ex.focus('diagram', QID, 'synthetic focus')
    data = json.loads(ex.candidate_path(focused).read_text())
    assert data['questions'] == [q] and path.read_bytes() == old
    assert focused['selected_item_scope']['assessed_parts'] == {q['id']: ''}
    assert len(focused['reliability_failures']['1']['extract']) == 2
    assert ex._coverage(focused, data) == []
    assert all(s['selected_page_numbers'] == [1] for s in focused['sources'])


@pytest.mark.parametrize('fault', ['unit', 'session', 'component', 'question', 'part', 'course', 'role', 'digest', 'missing-ms', 'bytes', 'metadata'])
def test_p1_import_rejects_source_or_identity_substitution(tmp_path, monkeypatch, fault):
    ex, _, q, vault, save = p1_case(tmp_path, monkeypatch)
    if fault in ('unit', 'session', 'component', 'question'):
        old, new = {'unit': ('WMA11', 'WMA12'), 'session': ('2019-01', '2019-06'), 'component': ('_01_q', '_02_q'), 'question': ('q1', 'q2')}[fault]
        q['official_qid'] = QID.replace(old, new)
    if fault == 'part': q['part'] = 'a'
    if fault == 'course':
        with ex.state_lock('diagram') as s: s['course'] = '9702'
    if fault == 'role': q['regions'], q['mark_scheme_regions'] = q['mark_scheme_regions'], q['regions']
    if fault == 'digest': q['regions'][0]['source_sha256'] = '0' * 64
    if fault == 'missing-ms': q['mark_scheme_regions'] = []
    if fault == 'bytes': (vault / AssetLibrary(vault).record(QP)['path']).write_bytes(b'corrupt')
    if fault == 'metadata':
        p = vault / 'Library/catalog.json'; d = json.loads(p.read_text()); d['assets'][QP[6:]]['course'] = '9702'; p.write_text(json.dumps(d))
    save()
    try: checked = ex.check('diagram')
    except (ValueError, ex.library.Fail): return
    assert checked['stage'] == 'pending', checked
    assert not (vault / '.tutor/topicals/CURRENT').exists()


@pytest.mark.parametrize('fault', ['qid', 'part', 'role', 'digest', 'missing-ms', 'metadata', 'bytes'])
def test_p1_publication_and_runtime_reject_source_substitution(tmp_path, monkeypatch, fault):
    ex, _, _, vault, _, batch = prepare(tmp_path, monkeypatch)
    bank = json.loads((batch / 'bank.json').read_text()); item = bank['items'][0]; src = item['source']
    if fault == 'qid': src['qid'] = QID.replace('q1', 'q2')
    if fault == 'part': src['part'] = 'a'
    if fault == 'role': src['extraction_regions'], src['mark_scheme_regions'] = src['mark_scheme_regions'], src['extraction_regions']
    if fault == 'digest': src['extraction_regions'][0]['source_sha256'] = '0' * 64
    if fault == 'missing-ms': src['mark_scheme_regions'] = []
    if fault == 'metadata':
        p = vault / 'Library/catalog.json'; d = json.loads(p.read_text()); d['assets'][MS[6:]]['kind'] = 'Diagrams'; p.write_text(json.dumps(d))
    if fault == 'bytes': (vault / AssetLibrary(vault).record(MS)['path']).write_bytes(b'corrupt')
    (batch / 'bank.json').write_text(json.dumps(bank))
    with pytest.raises((ValueError, ex.library.Fail)): ex.publish('diagram', batch)
    assert not (vault / '.tutor/topicals/CURRENT').exists()
    with pytest.raises(ValueError): topicals.validate_bank(bank, packs.Packs(store.Vault(vault)), vault)
    assert not list((vault / '.tutor/events').glob('*.jsonl'))


@pytest.mark.parametrize('fault', ['missing', 'foreign', 'duplicate', 'parent', 'revision', 'level'])
def test_p1_real_graph_levels_and_caie_as_policy_are_independent(tmp_path, monkeypatch, fault):
    ex, _, _, vault, _, batch = prepare(tmp_path, monkeypatch)
    runtime = packs.Packs(store.Vault(vault))
    assert runtime.kcs['P1-1.1']['level'] == 'P1'
    bank = json.loads((batch / 'bank.json').read_text()); item = bank['items'][0]
    if fault == 'missing': item['kcs'] = ['P1-missing']
    if fault == 'foreign': item['kcs'].append('9702-2.1.1')
    if fault == 'duplicate': item['kcs'] *= 2
    if fault == 'parent': item['topical']['chapters'] = ['9702-2.1']
    if fault == 'revision': item['topical']['revision'] = 'wrong'
    if fault == 'level': runtime.kcs['P1-1.1']['level'] = 'AS'
    with pytest.raises(ValueError): topicals.validate_bank(bank, runtime, vault)
    # Existing CAIE validation still rejects A2, independent of P1's real level.
    caie = {'id': 'legacy', 'source': {'type': 'past', 'qid': '9702_s24_22_q9'}, 'kind': 'structured',
            'stem': 'Synthetic', 'answer': 'Synthetic', 'marks': 1, 'scheme': [{'point': 'Synthetic'}],
            'kcs': ['9702-2.1.1'], 'topical': {'reviewed': True, 'revision': '2025-2027', 'chapters': ['9702-2.1'], 'requires': ['9702-2.1'], 'support': {}}}
    legacy = {'format_version': 1, 'syllabus_versions': {'9702': '2025-2027'}, 'items': [caie]}
    topicals.validate_bank(legacy, runtime, vault)
    runtime.kcs['9702-2.1.1']['level'] = 'A2'
    with pytest.raises(ValueError, match='AS'): topicals.validate_bank(legacy, runtime, vault)


@pytest.mark.parametrize('fault', ['bytes', 'role', 'missing'])
def test_p1_optional_whole_private_media_uses_p1_course_and_provenance(tmp_path, monkeypatch, fault):
    ex, _, _, vault, _, batch = prepare(tmp_path, monkeypatch, whole=True); ex.publish('diagram', batch)
    item = packs.Packs(store.Vault(vault)).topicals.items[0]
    original = vault / AssetLibrary(vault).record(MS)['path']
    if fault == 'bytes': original.write_bytes(b'corrupt')
    if fault == 'missing': original.unlink()
    if fault == 'role': item['source']['mark_scheme_regions'] = item['source']['extraction_regions']
    with pytest.raises(ValueError): topicals.whole_rubric_media(item, vault)


def test_p1_additive_import_preserves_unknown_generated_history_and_corrections(tmp_path, monkeypatch):
    import topicals as importer
    ex, path, q, vault, save = p1_case(tmp_path, monkeypatch)
    seed = tmp_path / 'seed'; seed.mkdir()
    old = {'id': 'legacy-stable', 'source': {'type': 'past', 'qid': '9702_s24_22_q9'}, 'kind': 'structured',
           'stem': 'Synthetic', 'answer': 'Synthetic', 'marks': 1, 'scheme': [{'point': 'Synthetic'}],
           'kcs': ['9702-2.1.1'], 'topical': {'reviewed': True, 'revision': '2025-2027', 'chapters': ['9702-2.1'], 'requires': ['9702-2.1'], 'support': {}}}
    (seed / 'bank.json').write_text(json.dumps({'format_version': 1, 'syllabus_versions': {'9702': '2025-2027'}, 'items': [old]}))
    (seed / 'report.json').write_text(json.dumps({'preparation': {'expected_current': None}}))
    first = importer.publish(seed, vault); first_ref = first['release'] + '/bank.json'
    unknown = path.parent / 'unknown.json'; unknown.write_text(json.dumps([{'id': 'sme-stable', 'source': {'qid': 'SME_q1'}}, {'id': 'null', 'source': {'qid': None}}]))
    history = vault / '.tutor/events/preserved.jsonl'; history.parent.mkdir(parents=True, exist_ok=True); history.write_bytes(b'{"type":"sentinel-history","correction":"stable"}\n')
    binding = vault / '.tutor/corrections-sentinel.json'; binding.write_bytes(b'{"event":"stable","binding":"unchanged"}\n')
    snapshot = {p: p.read_bytes() for p in [unknown, history, binding, vault / '.tutor/packs/v1/specs/P1/packs/P1-1.json', ex.job_dir('diagram') / 'review.json']}
    original = AssetLibrary(vault).read(first_ref)
    sources = {r: AssetLibrary(vault).record(r) for r in (QP, MS)}
    ex.register('diagram'); batch = tmp_path / 'add'; ex.prepare_publication('diagram', batch)
    b = json.loads((batch / 'bank.json').read_text()); assert b['items'][0] == old and len(b['items']) == 2
    ex.publish('diagram', batch)
    assert all(p.read_bytes() == data for p, data in snapshot.items())
    assert AssetLibrary(vault).read(first_ref) == original
    assert {r: AssetLibrary(vault).record(r) for r in (QP, MS)} == sources
    runtime = packs.Packs(store.Vault(vault)); assert len(runtime.topicals.items) == 2
    unknowns = json.loads(unknown.read_text()); assert all(topicals.identity(i) is None for i in unknowns)
    assert runtime.topicals.overlay(unknowns)[:2] == unknowns
