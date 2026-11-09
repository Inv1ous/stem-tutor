"""Native original MCQs reuse the worker's existing blind, source-bound route."""
import copy
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import shutil
import sys

import pytest
from library_assets import copy_to_vault
from tutorlib.asset_library import AssetLibrary

ROOT = Path(__file__).resolve().parents[2]
WORKER = ROOT / 'Work/Workers/extraction/overnight-20261105-10pct'
sys.path[:0] = [str(WORKER), str(ROOT / 'stem-tutor/extraction')]
import fastpath
import lightweight_verification as check
import native_nested_parts as nested
import prepared_source_packet as helper
import source_practice


@pytest.fixture(scope='module')
def original_package(tmp_path_factory):
    root = tmp_path_factory.mktemp('native-mcq-original')
    vault = root / 'vault'
    vault.mkdir()
    refs = {}
    for role in ('qp', 'ms'):
        reference = f'Library/Courses/9702/Sources/PastPapers/9702/2019/s/9702_s19_{role}_11.pdf'
        copy_to_vault(reference, vault)
        refs[role] = next(key for key, record in AssetLibrary(vault).records().items()
                          if record['path'] == reference)
    package = root / 'preparation'
    fastpath.prepare(vault, 'asset:' + refs['qp'], 'asset:' + refs['ms'], package, dpi=72)
    return vault, package


@pytest.fixture
def native_mcq(tmp_path, monkeypatch, original_package):
    vault, original = original_package
    package = tmp_path / 'preparation'
    shutil.copytree(original, package)
    monkeypatch.setattr(source_practice, 'WORKERS', tmp_path / 'no-workers')
    calls = []
    def original_verify(vault, output):
        calls.append((vault, output))
        return source_practice.verify(vault, output)
    replay = helper.verify_prepared(vault, package, original_verify)
    assert calls == [(vault, package)]
    return vault, package, replay


def reseal(package, mutate):
    bundle = json.loads((package / 'bundle.json').read_bytes())
    mutate(bundle)
    raw = json.dumps(bundle).encode()
    (package / 'bundle.json').write_bytes(raw)
    (package / 'COMPLETE').write_text(hashlib.sha256(raw).hexdigest())


def receipt(packet, *, outcome='solved', answer=None):
    return {'packet_digest': packet['digest'], 'item_id': packet['item_id'], 'kind': 'mcq',
            'outcome': outcome, 'context_complete': True, 'question_number': '1',
            'scheme_question_number': None, 'parts': [], 'proposals': [],
            'answer': answer or packet['binding']['item']['answer'],
            'reasons': ['Independent blind calculation from the complete original question.']}


def test_actual_source_verified_native_mcq_routes_to_exact_blind_packet(native_mcq):
    vault, package, replay = native_mcq
    row = replay['items'][0]
    before = copy.deepcopy(row)
    manifest, packet = helper.prepared_packet(package, replay, row, AssetLibrary(vault))
    assert manifest['status'] == 'source_manifest' and manifest['parts'] == []
    assert manifest['evidence'] == {
        'kind': 'prepared_native_mcq_v1', 'source_profile': fastpath.PROFILE,
        'preparation_sha256': replay['preparation_sha256'], 'sources': replay['sources']}
    assert packet == check.build_packet(row) and row == before
    assert replay['key_extractors'] == ['pymupdf_spatial', 'pypdf_serialized']
    request = nested.plan_request(packet, [])
    assert request['images'] == row['context_media'] + row['question_media']
    assert set(request['images']).isdisjoint(row['mark_scheme_media'])
    public = json.loads(request['prompt'].split('\n')[-1])
    assert set(public) == {'id', 'label', 'marks', 'question_text', 'required_parts', 'allowed_chapter_ids'}
    assert not any(key in request['prompt'] for key in ('mark_scheme_regions', 'mark_scheme_media', 'source_profile', 'key_extractors'))
    attempt = check.record_attempt(packet, receipt(packet), model=request['model'], effort=request['effort'])
    assert check.evaluate_receipt(packet, attempt)['status'] == 'checked'


@pytest.mark.parametrize('fault', ['profile', 'answer', 'source', 'geometry', 'public_private'])
def test_resealed_raw_claims_cannot_replace_original_verification(native_mcq, fault):
    vault, package, _ = native_mcq
    def mutate(bundle):
        if fault == 'profile': bundle['profile'] = 'forged-native-mcq'
        elif fault == 'answer':
            row = bundle['questions'][0]
            row['answer'] = 'A' if row['answer'] != 'A' else 'B'
        elif fault == 'source': bundle['sources']['ms']['sha256'] = '0' * 64
        elif fault == 'geometry': bundle['questions'][0]['regions'][0]['box'][1] += .02
        else: bundle['questions'][0]['question_media'] = bundle['questions'][0]['mark_scheme_media']
    reseal(package, mutate)
    with pytest.raises(ValueError):
        helper.verify_prepared(vault, package, source_practice.verify)


@pytest.mark.parametrize('fault', ['absent', 'row_unverified', 'replay_unverified', 'kind', 'key_missing', 'key_forged', 'preparation', 'sources'])
def test_mcq_packet_requires_fresh_membership_and_two_real_key_engines(native_mcq, fault):
    vault, package, replay = native_mcq
    replay = copy.deepcopy(replay)
    row = replay['items'][0]
    if fault == 'absent': replay['items'] = []
    elif fault == 'row_unverified': row['source_verified'] = False
    elif fault == 'replay_unverified': replay['source_verified'] = False
    elif fault == 'kind': row['kind'] = 'written'
    elif fault == 'key_missing': replay['key_extractors'] = ['pymupdf_spatial']
    elif fault == 'key_forged': replay['key_extractors'] = ['pymupdf_spatial', 'forged']
    elif fault == 'preparation': replay['preparation_sha256'] = '0' * 64
    else: replay['sources']['ms']['sha256'] = '0' * 64
    with pytest.raises(ValueError):
        helper.prepared_packet(package, replay, row, AssetLibrary(vault))


def test_existing_current_guard_stays_held_and_excluded(native_mcq, monkeypatch):
    vault, package, original = native_mcq
    row = original['items'][0]
    monkeypatch.setattr(source_practice, '_guard_holds', lambda: {row['id']: ['guard2:unchanged']})
    replay = helper.verify_prepared(vault, package, source_practice.verify)
    assert row['id'] not in {r['id'] for r in replay['items']}
    assert {'id': row['id'], 'reasons': ['guard2:unchanged']} in replay['held']
    with pytest.raises(ValueError, match='absent'):
        helper.prepared_packet(package, replay, row, AssetLibrary(vault))
    assert all(h in replay['held'] for h in original['held'])
    assert all(r == next(old for old in original['items'] if old['id'] == r['id']) for r in replay['items'])


def test_real_fresh_multiple_page_review_stays_held_before_packet(native_mcq):
    vault, package, replay = native_mcq
    row = next(r for r in replay['items'] if r['id'] == '9702_s19_11_q3')
    assert 'multiple_pages_require_review' in row['review_reasons']
    before = copy.deepcopy(row)
    manifest, packet = helper.prepared_packet(package, replay, row, AssetLibrary(vault))
    assert manifest['status'] == 'held' and packet is None
    assert manifest['reason'] == 'native_mcq_unresolved_source_review'
    assert manifest['review_reasons'] == row['review_reasons']
    assert row == before
    # The ordinary semantic-review flag remains eligible on the real q1 row.
    eligible = next(r for r in replay['items'] if r['id'] == '9702_s19_11_q1')
    assert eligible['review_reasons'] == ['independent_visual_and_mapping_review_required']
    manifest, packet = helper.prepared_packet(package, replay, eligible, AssetLibrary(vault))
    assert manifest['status'] == 'source_manifest' and packet == check.build_packet(eligible)


@pytest.mark.parametrize('flags', [
    ['shared_context_requires_review'], ['missing_shared_context'], ['unknown_source_review'],
    ['independent_visual_and_mapping_review_required', 'unknown_source_review'],
    'multiple_pages_require_review', None,
])
def test_unresolved_or_unknown_mcq_review_flags_cannot_gain_a_packet(native_mcq, flags):
    vault, package, replay = native_mcq
    replay = copy.deepcopy(replay)
    row = replay['items'][0]
    row['review_reasons'] = flags
    before = copy.deepcopy(row)
    manifest, packet = helper.prepared_packet(package, replay, row, AssetLibrary(vault))
    assert manifest['status'] == 'held' and packet is None
    assert manifest['review_reasons'] == flags and row == before


def test_publisher_keeps_real_multiple_page_review_before_semantic_history(native_mcq, tmp_path, monkeypatch):
    import publish_native
    vault, package, replay = native_mcq
    flagged = next(r for r in replay['items'] if r['id'] == '9702_s19_11_q3')
    before = copy.deepcopy(flagged)
    package_before = {p.relative_to(package): p.read_bytes() for p in package.rglob('*') if p.is_file()}
    monkeypatch.setattr(publish_native, 'R', tmp_path / 'worker')
    def original_verify(vault, output):
        actual = source_practice.verify(vault, output)
        actual['items'] = [r for r in actual['items'] if r['id'] == flagged['id']]
        return actual
    monkeypatch.setattr(publish_native, 'original_verify', original_verify)
    monkeypatch.setattr(publish_native, 'history_holds', lambda *_: pytest.fail('flagged row reached semantic history'))
    result = publish_native.approved(vault, package)
    assert result['items'] == [] and result['semantic_verification'] == []
    assert result['semantic_pending'] == [{'id': flagged['id'], 'reason': 'native_mcq_unresolved_source_review'}]
    assert result['held'] == replay['held'] and flagged == before
    assert {p.relative_to(package): p.read_bytes() for p in package.rglob('*') if p.is_file()} == package_before


def test_actual_independent_key_disagreement_still_rejects_source(native_mcq, monkeypatch):
    vault, package, _ = native_mcq
    original = source_practice._serialized_key
    def conflicting_key(raw):
        keys = original(raw)
        keys[1] = 'A' if keys[1] != 'A' else 'B'
        return keys
    monkeypatch.setattr(source_practice, '_serialized_key', conflicting_key)
    with pytest.raises(ValueError, match='independent official key disagreement'):
        helper.verify_prepared(vault, package, source_practice.verify)


def test_all_three_solver_attempts_stay_blind_and_wrong_answer_stays_poisoned(native_mcq):
    vault, package, replay = native_mcq
    row = replay['items'][0]
    _, packet = helper.prepared_packet(package, replay, row, AssetLibrary(vault))
    history = []
    for index in range(3):
        request = nested.plan_request(packet, history)
        assert request['images'] == row['context_media'] + row['question_media']
        assert not set(request['images']) & set(row['mark_scheme_media'])
        assert 'private_source' not in request['prompt']
        content = receipt(packet, outcome='uncertain')
        if index == 0: content['answer'] = 'A' if row['answer'] != 'A' else 'B'
        history.append(check.record_attempt(packet, content, model=request['model'], effort=request['effort'], attempt_history=history))
    assert nested.plan_request(packet, history) is None
    assert check.evaluate_receipt(packet, history[-1], history[:-1])['status'] != 'checked'


def test_actual_worker_wire_uses_only_fresh_public_pixels(native_mcq, tmp_path, monkeypatch):
    import asyncio
    from types import SimpleNamespace
    import check_current
    vault, package, replay = native_mcq
    local_vault = tmp_path / 'STEM Tutor'
    shutil.copytree(vault, local_vault)
    row = replay['items'][0]
    _, packet = helper.prepared_packet(package, replay, row, AssetLibrary(local_vault))
    request = nested.plan_request(packet, [])
    calls = []
    class OfflineClient:
        def __init__(self, **kwargs): pass
        async def one_shot(self, prompt, **kwargs):
            assert prompt == request['prompt'] and kwargs['schema'] == request['schema']
            assert kwargs['model'] == 'codex:' + request['model']
            assert kwargs['think'] == request['think']
            assert len(kwargs['images']) == len(request['images'])
            for ref, path in zip(request['images'], kwargs['images']):
                assert ref not in row['mark_scheme_media']
                assert path.read_bytes() == replay['_pixels'][ref]
            calls.append(True)
            return receipt(packet), SimpleNamespace(ok=True, usage={})
        async def close(self): pass
    class OfflineCollection:
        release = 'disposable'
        library = AssetLibrary(local_vault)
        def __init__(self, root): assert root == local_vault
    worker = tmp_path / 'worker'; worker.mkdir()
    (worker / 'run.json').write_text(json.dumps({'stop_floor': 10}))
    monkeypatch.setattr(check_current, 'ROOT', tmp_path)
    monkeypatch.setattr(check_current, 'R', worker)
    monkeypatch.setattr(check_current, 'Collection', OfflineCollection)
    monkeypatch.setattr(check_current, 'CodexAI', OfflineClient)
    monkeypatch.setattr(check_current, 'codex_usage', lambda _: {'seven_day': {'used': 20}})
    asyncio.run(check_current.main(row['id'], package))
    assert calls == [True]
    state = json.loads((worker / 'semantic-checks' / packet['digest'] / 'state.json').read_bytes())
    assert state['status'] == 'checked'
    expected = nested.request_provenance(request, [package / ref for ref in request['images']])
    assert state['attempts'][0]['request_provenance'] == expected


@pytest.mark.parametrize('mode', ['pending', 'checked', 'missing_wire', 'prompt', 'schema', 'image'])
def test_mcq_publisher_requires_actual_full_blind_wire_and_preserves_source_bytes(native_mcq, tmp_path, monkeypatch, mode):
    import publish_native
    vault, package, replay = native_mcq
    row = replay['items'][0]
    before = {p.relative_to(package): p.read_bytes() for p in package.rglob('*') if p.is_file()}
    _, packet = helper.prepared_packet(package, replay, row, AssetLibrary(vault))
    worker = tmp_path / 'worker'
    monkeypatch.setattr(publish_native, 'R', worker)
    # Keep the publisher's verification real; only narrow this test's candidate set.
    def original_verify(vault, output):
        actual = source_practice.verify(vault, output)
        actual['items'] = [r for r in actual['items'] if r['id'] == row['id']]
        return actual
    monkeypatch.setattr(publish_native, 'original_verify', original_verify)
    saved = None
    if mode != 'pending':
        request = nested.plan_request(packet, [])
        paths = [nested.resolve_replay_image(package, ref, replay) for ref in request['images']]
        wire = nested.request_provenance(request, paths)
        assert all(path.read_bytes() == replay['_pixels'][ref] for path, ref in zip(paths, request['images']))
        attempt = check.record_attempt(packet, receipt(packet), model=request['model'], effort=request['effort'])
        entry = {'envelope': asdict(attempt)}
        if mode != 'missing_wire': entry['request_provenance'] = wire
        if mode == 'prompt': wire['prompt'] += 'changed'
        elif mode == 'schema': wire['schema'] = {}
        elif mode == 'image': wire['images'][0]['sha256'] = '0' * 64
        dest = worker / 'semantic-checks' / packet['digest']; dest.mkdir(parents=True)
        state = dest / 'state.json'
        state.write_text(json.dumps({'qid': row['id'], 'packet_digest': packet['digest'], 'status': 'checked', 'attempts': [entry]}))
        saved = state.read_bytes()
    result = publish_native.approved(vault, package)
    assert result['items'] == ([row] if mode == 'checked' else [])
    assert result['held'] == replay['held']
    assert bool(result['semantic_pending']) is (mode != 'checked')
    if mode == 'checked':
        assert result['semantic_verification'][0]['request_provenance'] == [wire]
    if saved is not None: assert state.read_bytes() == saved
    assert {p.relative_to(package): p.read_bytes() for p in package.rglob('*') if p.is_file()} == before
