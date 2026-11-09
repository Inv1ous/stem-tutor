"""Prepared-family worker packets replay registered sources in disposable vaults."""
import copy
from dataclasses import asdict
import hashlib
import importlib
import importlib.util
import json
from pathlib import Path
import sys

import pytest
from library_assets import canonical_path, copy_to_vault
from tutorlib.asset_library import AssetLibrary

ROOT = Path(__file__).resolve().parents[2]
WORKER = ROOT / 'Work/Workers/extraction/overnight-20261105-10pct'
sys.path[:0] = [str(WORKER), str(ROOT / 'stem-tutor/extraction')]
import lightweight_verification as check
import source_practice
from test_native_nested_check_manifests import source_question, receipt
from test_pmt_complete_profile import staged


def helper():
    assert importlib.util.find_spec('prepared_source_packet'), 'prepared source worker helper is missing'
    return importlib.import_module('prepared_source_packet')


@pytest.fixture(autouse=True)
def offline(tmp_path, monkeypatch):
    monkeypatch.setattr(source_practice, 'WORKERS', tmp_path / 'no-workers')


def pmt_package(tmp_path, course='P4', reference='asset:asset-548a7193599a829723e46a06'):
    import pmt_complete_profile
    vault = staged(tmp_path, reference)
    for c in ('P1', 'P2', 'P3', 'P4', 'S1', 'S2', 'M1'):
        copy_to_vault(f'build/out/specs/{c}/graph.json', vault)
    package = tmp_path / 'Work/Preparation/pmt'
    pmt_complete_profile.prepare(vault, reference, course, package, dpi=72)
    replay = source_practice.verify(vault, package)
    return vault, package, replay


@pytest.mark.parametrize('name', ['flat', 'whole', 'nested'])
def test_native_manifest_packet_and_request_wire_are_identical(tmp_path, name):
    import native_part_manifest, native_nested_parts
    q, docs, lib, course = source_question(tmp_path, name)
    for c in ('P1', 'P2', 'P3', 'P4', 'S1', 'S2'):
        copy_to_vault(f'build/out/specs/{c}/graph.json', lib.root)
    lib = AssetLibrary(lib.root)
    q['official_qid'] = f'{course}-q{q["number"]}'
    row = {'id': q['official_qid'], 'kind': 'written', 'marks': q['whole_assessment']['max_marks'],
           'label': str(q['number']), 'source_verified': True,
           'question_media': [f'q{i}' for i in range(len(q['question_regions']))],
           'mark_scheme_media': [f'ms{i}' for i in range(len(q['scheme_regions']))],
           'regions': q['question_regions'], 'mark_scheme_regions': q['scheme_regions']}
    package = tmp_path / 'native'; package.mkdir()
    (package / 'descriptor.json').write_text(json.dumps({'course': course, 'sources': {'qp': {'asset_id': q['question_regions'][0]['source_id']}}, 'questions': [q]}))
    old_manifest = native_part_manifest.derive(q, docs['qp'], __import__('prepared_scope')._words)
    old_packet = native_nested_parts.bound_packet(row, old_manifest, lib, course)
    manifest, packet = helper().prepared_packet(package, {'items': [row]}, row, lib)
    assert json.dumps(manifest) == json.dumps(old_manifest)
    assert json.dumps(packet) == json.dumps(old_packet)
    assert json.dumps(native_nested_parts.plan_request(packet, [])) == json.dumps(native_nested_parts.plan_request(old_packet, []))


def test_pmt_actual_leaf_parts_and_truthful_total_proof(tmp_path):
    vault, package, replay = pmt_package(tmp_path)
    row = replay['items'][1]
    before = {p.relative_to(package): p.read_bytes() for p in package.rglob('*') if p.is_file()}
    manifest, packet = helper().prepared_packet(package, replay, row, AssetLibrary(vault))
    assert manifest['status'] == 'source_manifest'
    assert manifest['parts'] == [{'id': 'a', 'marks': 4}, {'id': 'b', 'marks': 7}]
    evidence = manifest['evidence']
    assert evidence['source_profile'] == 'pmt-native-complete-set1-v1'
    assert evidence['algorithm_input_kind'] == 'transparent_pmt_geometry_adapter'
    assert evidence['totals']['qp']['literal'] == '(Total 11 marks)'
    assert evidence['totals']['ms']['literal'] == '[11]'
    for proof in evidence['totals'].values():
        assert proof['value'] == 11 and proof['region']['source_sha256'] == row['regions'][0]['source_sha256']
    assert packet['binding']['allowed_chapter_ids']
    assert packet['binding']['item']['chapter_catalog']['course'] == 'P4'
    assert packet['binding']['item']['required_parts_evidence'] == evidence
    assert {p.relative_to(package): p.read_bytes() for p in package.rglob('*') if p.is_file()} == before


def test_pmt_unpartitioned_source_has_whole_only_without_labels(tmp_path):
    vault, package, replay = pmt_package(tmp_path)
    manifest, _ = helper().prepared_packet(package, replay, replay['items'][0], AssetLibrary(vault))
    assert manifest['parts'] == [{'id': 'whole', 'marks': 7}]


@pytest.mark.parametrize('fault', ['shared', 'sum', 'ambiguous_gutter'])
def test_pmt_source_ambiguity_stays_held(tmp_path, monkeypatch, fault):
    import prepared_scope
    vault, package, replay = pmt_package(tmp_path)
    row = replay['items'][1]
    original = prepared_scope._words
    def words(page):
        values = copy.deepcopy(original(page))
        if page.number == 0:
            if fault == 'shared': values = [w for w in values if w['text'] != '(4)']
            elif fault == 'sum': next(w for w in values if w['text'] == '(4)')['text'] = '(3)'
            else:
                next(w for w in values if w['text'] == '(a)')['text'] = '(a'
        return values
    monkeypatch.setattr(prepared_scope, '_words', words)
    manifest, packet = helper().prepared_packet(package, replay, row, AssetLibrary(vault))
    assert manifest['status'] == 'held' and packet is None


def test_new_packet_digest_binds_source_proof_and_registered_graph(tmp_path):
    import native_nested_parts
    vault, package, replay = pmt_package(tmp_path)
    row = replay['items'][1]; lib = AssetLibrary(vault)
    manifest, packet = helper().prepared_packet(package, replay, row, lib)
    altered = copy.deepcopy(row); altered['printed_total_geometry']['bbox_pt'][0] += 1
    replay2 = {**replay, 'items': [altered]}
    assert helper().prepared_packet(package, replay2, altered, lib)[1]['digest'] != packet['digest']
    original = native_nested_parts.chapter_catalog
    def catalog(library, course):
        result = original(library, course); result['graphs'][0]['chapters'][0]['title'] += ' revised'; return result
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(native_nested_parts, 'chapter_catalog', catalog)
    try: assert helper().prepared_packet(package, replay, row, lib)[1]['digest'] != packet['digest']
    finally: monkeypatch.undo()


def test_unsupported_profile_cannot_fall_back_to_native(tmp_path):
    package = tmp_path / 'unknown'; package.mkdir()
    (package / 'bundle.json').write_text(json.dumps({'kind': 'pmt_complete_preparation', 'profile': 'other'}))
    with pytest.raises(ValueError, match='unsupported'):
        helper().prepared_packet(package, {'items': []}, {}, None)


def caie_package(tmp_path):
    import caie_written_profile
    from test_caie_written_profile import ref
    vault = tmp_path / 'vault'; vault.mkdir()
    for role in ('qp', 'ms'): copy_to_vault(ref('9702', role), vault)
    for course in ('9702', 'P1', 'P2', 'P3', 'P4'): copy_to_vault(f'build/out/specs/{course}/graph.json', vault)
    package = tmp_path / 'caie'
    caie_written_profile.prepare(vault, ref('9702', 'qp'), ref('9702', 'ms'), package, dpi=24)
    replay = helper().verify_prepared(vault, package, lambda *_: pytest.fail('CAIE bypassed its own verifier'))
    return vault, package, replay


def test_caie_fresh_source_parts_and_current_guards(tmp_path, monkeypatch):
    monkeypatch.setattr(source_practice, '_guard_holds', lambda: {'9702_s24_22_q2': ['current-guard']})
    vault, package, replay = caie_package(tmp_path)
    assert any(h['id'] == '9702_s24_22_q2' and 'current-guard' in h['reasons'] for h in replay['held'])
    row = next(r for r in replay['items'] if r['number'] == 1)
    manifest, packet = helper().prepared_packet(package, replay, row, AssetLibrary(vault))
    assert manifest['parts'] == [{'id': p['part'], 'marks': p['marks']} for p in row['required_parts']]
    assert manifest['evidence']['source_profile'] == 'caie-original-written-v1'
    assert manifest['evidence']['parts'] == row['required_parts']
    assert packet['binding']['item']['chapter_catalog']['course'] == '9702'


@pytest.mark.parametrize('fault', ['sum', 'duplicate', 'public_proof', 'private_proof', 'total_proof'])
def test_caie_worker_rejects_invalid_replayed_part_contract(tmp_path, fault):
    vault, package, replay = caie_package(tmp_path)
    row = copy.deepcopy(next(r for r in replay['items'] if r['number'] == 1))
    if fault == 'sum': row['required_parts'][0]['marks'] += 1
    elif fault == 'duplicate': row['required_parts'][1]['part'] = row['required_parts'][0]['part']
    elif fault == 'public_proof': row['required_parts'][0]['public_mark_witness']['source_sha256'] = '0' * 64
    elif fault == 'private_proof': row['required_parts'][0]['private_mark_witnesses'] = []
    else: row['maximum_authority']['qp']['source_id'] = 'asset:forged'
    manifest, packet = helper().prepared_packet(package, {**replay, 'items': [row]}, row, AssetLibrary(vault))
    assert manifest['status'] == 'held' and packet is None


def test_original_verifier_is_explicit_and_native_result_untouched(tmp_path):
    (tmp_path / 'descriptor.json').write_text('{}')
    expected = {'items': [], 'held': [{'id': 'old'}]}
    assert helper().verify_prepared('vault', tmp_path, lambda vault, output: expected) is expected


@pytest.mark.parametrize('mode', ['pending', 'checked', 'wire', 'changed_history'])
def test_publisher_new_family_preserves_pending_history_and_full_private_wire(tmp_path, monkeypatch, mode):
    import native_nested_parts, publish_native
    vault, package, replay = pmt_package(tmp_path)
    row = replay['items'][1]; replay = {**replay, 'items': [row]}
    manifest, packet = helper().prepared_packet(package, replay, row, AssetLibrary(vault))
    state_root = tmp_path / 'worker'
    monkeypatch.setattr(publish_native, 'R', state_root)
    monkeypatch.setattr(publish_native, 'original_verify', lambda *_: copy.deepcopy(replay))
    monkeypatch.setattr(native_nested_parts, 'MEDIA_CACHE_ROOT', tmp_path / 'Candidates')
    assert set(native_nested_parts.plan_request(packet, [])['images']) >= set(row['question_media'] + row['mark_scheme_media'])
    saved = None
    if mode != 'pending':
        attempt = check.record_attempt(packet, receipt(packet), model='gpt-6-luna', effort='low')
        assert check.evaluate_receipt(packet, attempt)['status'] == 'checked'
        request = native_nested_parts.plan_request(packet, [])
        paths = [native_nested_parts.resolve_replay_image(package, ref, replay) for ref in request['images']]
        wire = native_nested_parts.request_provenance(request, paths)
        if mode == 'wire': wire['images'][-1]['sha256'] = '0' * 64
        digest = 'old' if mode == 'changed_history' else packet['digest']
        directory = state_root / 'semantic-checks' / digest; directory.mkdir(parents=True)
        state = {'qid': row['id'], 'packet_digest': digest, 'status': 'checked',
                 'attempts': [{'envelope': asdict(attempt), 'request_provenance': wire}]}
        path = directory / 'state.json'; path.write_text(json.dumps(state)); saved = path.read_bytes()
    result = publish_native.approved(vault, package)
    assert result['items'] == ([row] if mode == 'checked' else [])
    assert result['held'] == replay['held']
    if mode != 'checked': assert result['semantic_pending']
    if saved is not None: assert path.read_bytes() == saved


def test_queue_explicit_manifest_and_prefix_preserve_native_reports(tmp_path, monkeypatch):
    import asyncio, semantic_queue
    monkeypatch.setattr(semantic_queue, 'R', tmp_path)
    (tmp_path / 'run.json').write_text(json.dumps({'last_weekly_remaining': 50, 'stop_floor': 10}))
    native = tmp_path / 'semantic-queue-0.json'; native.write_text('native history')
    manifest = tmp_path / 'new.json'; manifest.write_text(json.dumps({'items': [{'qid': 'new-q', 'package': 'fresh', 'manifest': {'status': 'source_manifest'}}]}))
    calls = []
    async def fake(qid, package): calls.append((qid, package))
    monkeypatch.setattr(semantic_queue.check_current, 'main', fake)
    asyncio.run(semantic_queue.main(0, 1, manifest_file=manifest, name_prefix='prepared'))
    assert calls[0][0] == 'new-q' and native.read_text() == 'native history'
    assert (tmp_path / 'prepared-0.json').exists()


@pytest.mark.parametrize('reference,course,count', [
    ('asset:asset-0f507f71116a4a6b0998380f', 'S2', 2),
    ('asset:asset-548a7193599a829723e46a06', 'P4', 3),
    ('asset:asset-46db0dc5b8a905df939a1883', 'M1', 2),
])
def test_actual_pmt_two_three_two_inventory_has_source_parts_or_explicit_hold(tmp_path, reference, course, count):
    vault, package, replay = pmt_package(tmp_path, course, reference)
    assert len(replay['items']) == count
    for row in replay['items']:
        manifest, packet = helper().prepared_packet(package, replay, row, AssetLibrary(vault))
        if manifest['status'] == 'held':
            assert manifest['reason'] and packet is None
        else:
            assert sum(p['marks'] for p in manifest['parts']) == row['marks']
            assert packet['binding']['item']['regions'] == row['regions']
            assert packet['binding']['item']['mark_scheme_regions'] == row['mark_scheme_regions']
            assert packet['binding']['item']['mark_scheme_media'] == row['mark_scheme_media']


@pytest.mark.parametrize('mode', ['checked', 'unknown', 'changed', 'transport', 'exhausted'])
def test_prepared_runner_preserves_actual_attempts_and_provider_gates(tmp_path, monkeypatch, mode):
    import asyncio, check_current, native_nested_parts
    vault, package, replay = pmt_package(tmp_path)
    row = replay['items'][1]
    _, packet = helper().prepared_packet(package, replay, row, AssetLibrary(vault))
    content = receipt(packet)
    if mode != 'checked': content['outcome'] = 'uncertain'
    history = []
    count = 3 if mode == 'exhausted' else 1
    for _ in range(count):
        history.append(check.record_attempt(packet, content, model=['gpt-6-luna', 'gpt-6-sol', 'gpt-6.1-terra'][len(history)],
                                           effort=['low', 'medium', 'high'][len(history)], attempt_history=history,
                                           error='timeout' if mode == 'transport' else None))
    state_root = tmp_path / 'worker'
    digest = 'older-packet' if mode == 'changed' else packet['digest']
    dest = state_root / 'semantic-checks' / digest; dest.mkdir(parents=True)
    state = {'qid': row['id'], 'packet_digest': digest, 'status': 'checked' if mode == 'checked' else 'checkpointed_usage_floor_or_unknown',
             'attempts': [{'envelope': asdict(a)} for a in history]}
    path = dest / 'state.json'; path.write_text(json.dumps(state)); before = path.read_bytes()
    (state_root / 'run.json').write_text(json.dumps({'stop_floor': 10}))
    observations = []
    class OfflineClient:
        def __init__(self, **kwargs): pass
        async def one_shot(self, *args, **kwargs): pytest.fail('unexpected paid provider launch')
        async def close(self): pass
    class OfflineCollection:
        release = 'disposable'
        library = AssetLibrary(vault)
        def __init__(self, root): pass
    monkeypatch.setattr(check_current, 'R', state_root)
    monkeypatch.setattr(check_current, 'Collection', OfflineCollection)
    monkeypatch.setattr(check_current, 'CodexAI', OfflineClient)
    monkeypatch.setattr(source_practice, 'verify', lambda *_: copy.deepcopy(replay))
    monkeypatch.setattr(check_current, 'codex_usage', lambda _: observations.append(True))
    asyncio.run(check_current.main(row['id'], package))
    assert len(observations) == (2 if mode == 'unknown' else 0)
    assert json.loads(path.read_bytes())['attempts'] == state['attempts']
    if mode != 'transport': assert path.read_bytes() == before or mode == 'unknown'
    assert len(list((state_root / 'semantic-checks').glob('*/state.json'))) == 1


def test_publisher_accepts_explicit_inventory_without_touching_default(tmp_path, monkeypatch):
    import publish_native
    default = tmp_path / 'native-written-preparations.json'; default.write_text('native inventory unchanged')
    inventory = tmp_path / 'prepared.json'; inventory.write_text(json.dumps({'preparations': []}))
    (tmp_path / 'run.json').write_text(json.dumps({'last_weekly_remaining': 50, 'stop_floor': 10}))
    monkeypatch.setattr(publish_native, 'R', tmp_path)
    saved = source_practice.verify
    publish_native.main(inventory=inventory)
    assert source_practice.verify is saved
    assert default.read_text() == 'native inventory unchanged'


def test_caie_selector_replays_and_rejects_resealed_raw_parts(tmp_path):
    vault, package, replay = caie_package(tmp_path)
    import caie_written_profile
    descriptor = json.loads((package / 'caie-descriptor.json').read_bytes())
    descriptor['questions'][0]['required_parts'][0]['marks'] = 99
    (package / 'caie-descriptor.json').write_bytes(caie_written_profile.canonical_bytes(descriptor))
    seal = {p.relative_to(package).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in package.rglob('*') if p.is_file() and p.name != 'COMPLETE'}
    (package / 'COMPLETE').write_bytes(caie_written_profile.canonical_bytes(seal))
    with pytest.raises(ValueError, match='source replay differs'):
        helper().verify_prepared(vault, package, lambda *_: pytest.fail('CAIE used native verifier'))


def test_prepared_runner_binds_actual_fake_client_wire_and_private_replay_bytes(tmp_path, monkeypatch):
    import asyncio, check_current, native_nested_parts
    from types import SimpleNamespace
    vault, package, replay = pmt_package(tmp_path)
    row = replay['items'][1]
    _, packet = helper().prepared_packet(package, replay, row, AssetLibrary(vault))
    state_root = tmp_path / 'worker'; state_root.mkdir()
    (state_root / 'run.json').write_text(json.dumps({'stop_floor': 10}))
    before = {p.relative_to(package): p.read_bytes() for p in package.rglob('*') if p.is_file()}
    calls = []
    class OfflineClient:
        def __init__(self, **kwargs): pass
        async def one_shot(self, prompt, **kwargs):
            request = native_nested_parts.plan_request(packet, [])
            assert prompt == request['prompt']
            assert len(kwargs['images']) == len(request['images'])
            for ref, path in zip(request['images'], kwargs['images']):
                assert path.read_bytes() == replay['_pixels'][ref]
            private = [path for ref, path in zip(request['images'], kwargs['images']) if ref in row['mark_scheme_media']]
            assert private and all(path.is_relative_to(tmp_path / 'Candidates') for path in private)
            calls.append(True)
            return receipt(packet), SimpleNamespace(ok=True, usage={})
        async def close(self): pass
    class OfflineCollection:
        release = 'disposable'
        library = AssetLibrary(vault)
        def __init__(self, root): pass
    monkeypatch.setattr(check_current, 'R', state_root)
    monkeypatch.setattr(check_current, 'Collection', OfflineCollection)
    monkeypatch.setattr(check_current, 'CodexAI', OfflineClient)
    monkeypatch.setattr(source_practice, 'verify', lambda *_: copy.deepcopy(replay))
    monkeypatch.setattr(check_current, 'codex_usage', lambda _: {'seven_day': {'used': 20}})
    monkeypatch.setattr(native_nested_parts, 'MEDIA_CACHE_ROOT', tmp_path / 'Candidates')
    asyncio.run(check_current.main(row['id'], package))
    assert calls == [True]
    state = json.loads((state_root / 'semantic-checks' / packet['digest'] / 'state.json').read_bytes())
    assert state['status'] == 'checked'
    request = native_nested_parts.plan_request(packet, [])
    for entry, ref in zip(state['attempts'][0]['request_provenance']['images'], request['images']):
        assert entry == {'reference': ref, 'sha256': hashlib.sha256(replay['_pixels'][ref]).hexdigest()}
    assert {p.relative_to(package): p.read_bytes() for p in package.rglob('*') if p.is_file()} == before
