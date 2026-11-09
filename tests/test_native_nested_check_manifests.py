"""Worker-only manifests use authenticated originals copied into disposable vaults."""
import copy
import hashlib
import importlib
import json
from pathlib import Path
import sys

import pymupdf
import pytest
from library_assets import canonical_path, copy_to_vault
from tutorlib.asset_library import AssetLibrary

ROOT = Path(__file__).resolve().parents[2]
WORKER = ROOT / 'Work/Workers/extraction/overnight-20261105-10pct'
sys.path[:0] = [str(WORKER), str(ROOT / 'stem-tutor/extraction')]
import prepared_scope
import native_part_manifest
import lightweight_verification as check

# Actual whole-question boundaries, independently printed QP/MS totals.
SOURCES = {
    'nested': ('S2', 6, 'asset:legacy-21ec9972897bf8bf1ded353d', range(18, 22),
               'asset:legacy-6ebd40e121b2ba7666c543ae', [11]),
    'reverse': ('FP1', 1, 'asset:legacy-a54a0eb442875751c3a8818b', range(2, 6),
                'asset:legacy-c40da01063e22fd1d4d50237', [9]),
    'shared': ('P1', 5, 'asset:legacy-5433803d0abf868d346949c8', [10, 11],
               'asset:legacy-49fc389000ec4447e3b10835', [14, 15]),
    'flat': ('FP2', 1, 'asset:legacy-4feb8fa28182b7b84ff8646f', range(2, 6),
             'asset:legacy-05de55f2ac913134fcfd7f52', [7]),
    'whole': ('FP3', 1, 'asset:legacy-60b9712260c8c2fdffecd495', [2, 3],
              'asset:legacy-6f838e266dd038af0e3a7c16', [7]),
}


def source_question(tmp_path, name):
    course, number, qp, pages, ms, ms_pages = SOURCES[name]
    vault = tmp_path / name
    vault.mkdir()
    for asset in (qp, ms):
        copy_to_vault(canonical_path(asset), vault)
    lib = AssetLibrary(vault)
    qp, ms = canonical_path(qp), canonical_path(ms)
    docs = {role: pymupdf.open(stream=lib.read(asset), filetype='pdf') for role, asset in [('qp', qp), ('ms', ms)]}
    q = {'number': number}
    for role, field, asset, selected in [('qp', 'question_regions', qp, pages), ('ms', 'scheme_regions', ms, ms_pages)]:
        q[field] = [{'role': role, 'source_id': asset, 'source_sha256': lib.record(asset)['sha256'],
                     'page': p, 'box': [0, 0, 1, 1]} for p in selected]
    layouts = {role: [{'words': prepared_scope._words(p)} for p in doc] for role, doc in docs.items()}
    q['whole_assessment'] = prepared_scope._whole_assessment(q, layouts, {})
    # The legacy MS tokenizer is incomplete for compound labels; v1 uses its
    # flat witness for old supported flat cases only.
    q['witness'] = {role + '_parts': sorted({prepared_scope._part_marker(w)
        for r in q['question_regions' if role == 'qp' else 'scheme_regions']
        for w in layouts[role][r['page'] - 1]['words'] if prepared_scope._part_marker(w)}) for role in docs}
    if name == 'flat': q['witness']['ms_parts'] = ['a', 'b', 'c']
    return q, docs, lib, course


def test_real_nested_leaf_maxima_ignore_incomplete_ms_tokenizer(tmp_path):
    q, docs, _, _ = source_question(tmp_path, 'nested')
    manifest = native_part_manifest.derive(q, docs['qp'], prepared_scope._words)
    assert manifest['status'] == 'source_manifest'
    assert manifest['parts'] == [{'id': 'a', 'marks': 2}, {'id': 'b(i)', 'marks': 4},
                                 {'id': 'b(ii)', 'marks': 2}, {'id': 'c', 'marks': 2}, {'id': 'd', 'marks': 2}]
    assert sum(p['marks'] for p in manifest['parts']) == q['whole_assessment']['max_marks']
    for proof in manifest['evidence']['parts']:
        for region in (proof['part']['region'], proof['maximum']['region']):
            assert region['source_sha256'] == q['question_regions'][0]['source_sha256']
            assert region['page'] in range(18, 22) and len(region['box']) == 4


def test_real_reverse_hierarchy_has_no_parent_fake_marks(tmp_path):
    q, docs, _, _ = source_question(tmp_path, 'reverse')
    manifest = native_part_manifest.derive(q, docs['qp'], prepared_scope._words)
    assert manifest.get('parts') == [{'id': 'i(a)', 'marks': 2}, {'id': 'i(b)', 'marks': 4}, {'id': 'ii', 'marks': 4}]


def test_real_shared_child_allocation_preserves_printed_parent_group(tmp_path):
    q, docs, _, _ = source_question(tmp_path, 'shared')
    assert helper().derive_nested(q, docs['qp'], prepared_scope._words)['status'] == 'held'
    manifest = native_part_manifest.derive(q, docs['qp'], prepared_scope._words)
    assert manifest['parts'] == [{'id': 'a', 'marks': 2}, {'id': 'b', 'marks': 2}, {'id': 'c', 'marks': 2}]
    group, = manifest['evidence']['parent_groups']
    assert group['parent']['id'] == 'c'
    assert [child['id'] for child in group['children']] == ['c(i)', 'c(ii)']
    assert all(set(child) == {'id', 'region'} for child in group['children'])
    assert group['maximum']['marks'] == 2


@pytest.mark.parametrize('name', ['flat', 'whole'])
def test_v1_real_source_output_remains_byte_identical(tmp_path, name):
    q, docs, _, _ = source_question(tmp_path, name)
    old = native_part_manifest._derive_v1(q, docs['qp'], prepared_scope._words)
    assert old['status'] == 'source_manifest'
    expected = {'flat': 'e5dca03f7db7d72435010231e7e2ea4c3c70681c178ea6e77c120604cf774f25',
                'whole': '3ac14250ee21beea5f6294df5e8095775b5c2ddd2dd8697250e7b1f062aa0d70'}
    assert hashlib.sha256(json.dumps(old).encode()).hexdigest() == expected[name]
    assert json.dumps(native_part_manifest.derive(q, docs['qp'], prepared_scope._words)) == json.dumps(old)


@pytest.mark.parametrize('fault', ['duplicate', 'gap', 'equation', 'extra_marks', 'wrong_total', 'forged_marker', 'parent_marks'])
def test_nested_ambiguity_and_forgery_fail_closed(tmp_path, fault):
    q, docs, _, _ = source_question(tmp_path, 'nested')
    base_words = prepared_scope._words
    mutated = {p.number: copy.deepcopy(base_words(p)) for p in docs['qp']}
    page = mutated[17]
    markers = q['whole_assessment']['printed_markers']['qp']
    roman = next(w for w in page if w['text'] == '(ii)')
    if fault == 'duplicate': roman['text'] = '(i)'
    elif fault == 'gap': roman['text'] = '(iii)'
    elif fault == 'equation': roman['box'][0] = .4
    elif fault == 'extra_marks': page.append({'text': '(2)', 'box': [.83, .8, .86, .82]})
    elif fault == 'wrong_total': q['whole_assessment']['max_marks'] += 1
    elif fault == 'forged_marker': markers[0]['text'] = '(z)'
    elif fault == 'parent_marks':
        parent = next(w for w in page if w['text'] == '(b)')
        page.append({'text': '(1)', 'box': [.83, parent['box'][1] + .001, .86, parent['box'][3]]})
    if fault != 'forged_marker':
        import re
        q['whole_assessment']['printed_markers']['qp'] = [
            {'text': w['text'], 'region': {**r, 'box': w['box']}}
            for r in q['question_regions'] for w in mutated[r['page'] - 1]
            if w['box'][0] < .25 and re.fullmatch(r'(?:[1-9]\d?\.?)?\((?:[a-z]|[ivx]+)\)', w['text'])]
    assert native_part_manifest.derive(q, docs['qp'], lambda p: mutated[p.number])['status'] == 'held'


def helper(): return importlib.import_module('native_nested_parts')


@pytest.mark.parametrize('status,error,count', [('checked', None, 1), ('hold', None, 3), ('held_provider_infrastructure', 'timeout', 1), ('launching', None, 0)])
def test_changed_packet_never_resets_canonical_question_history(tmp_path, status, error, count):
    dest = tmp_path / 'old'; dest.mkdir()
    state = {'qid': 'canonical-q1', 'packet_digest': 'old', 'status': status,
             'attempts': [{'envelope': {'error': error}} for _ in range(count)]}
    (dest / 'state.json').write_text(json.dumps(state))
    assert helper().history_holds(tmp_path, 'canonical-q1', 'new')


def test_same_packet_unknown_usage_preserves_retry_history(tmp_path):
    dest = tmp_path / 'same'; dest.mkdir()
    state = {'qid': 'canonical-q1', 'packet_digest': 'same', 'status': 'checkpointed_usage_floor_or_unknown',
             'attempts': [{'envelope': {'error': None}}]}
    path = dest / 'state.json'; path.write_text(json.dumps(state)); before = path.read_bytes()
    assert helper().history_holds(tmp_path, 'canonical-q1', 'same') == []
    assert path.read_bytes() == before


def test_quota_unknown_retries_only_free_observation_once():
    seen = []
    def probe():
        seen.append(True)
        return None if len(seen) == 1 else {'seven_day': {'used': 20}}
    assert helper().observe_usage(probe) == ({'seven_day': {'used': 20}}, 80)
    assert len(seen) == 2
    seen.clear()
    assert helper().observe_usage(lambda: seen.append(True)) == (None, None)
    assert len(seen) == 2


def test_fallback_graph_binding_contains_registered_literal_titles_and_prompt(tmp_path):
    q, docs, lib, course = source_question(tmp_path, 'nested')
    copy_to_vault('build/out/specs/S2/graph.json', lib.root)
    # Real registered prerequisite graphs, if the S2 graph declares cross-course KCs.
    for c in ('P1', 'P2', 'P3', 'P4', 'S1'):
        copy_to_vault(f'build/out/specs/{c}/graph.json', lib.root)
    lib = AssetLibrary(lib.root)
    manifest = native_part_manifest.derive(q, docs['qp'], prepared_scope._words)
    row = {'id': 'S2-q6', 'kind': 'written', 'marks': 12, 'source_verified': True,
           'regions': q['question_regions'], 'question_media': [str(i) for i in range(4)],
           'mark_scheme_regions': q['scheme_regions'], 'mark_scheme_media': ['ms'], 'label': '6'}
    packet = helper().bound_packet(row, manifest, lib, course)
    catalog = packet['binding']['item']['chapter_catalog']
    assert packet['binding']['allowed_chapter_ids']
    for graph in catalog['graphs']:
        assert hashlib.sha256(lib.read(graph['source_id'])).hexdigest() == graph['source_sha256']
        native = json.loads(lib.read(graph['source_id']))
        for chapter in graph['chapters']:
            assert any(c['id'] == chapter['id'] and c['title'] == chapter['title'] for c in native['subtopics'])
    request = helper().plan_request(packet, [])
    assert catalog['graphs'][0]['chapters'][0]['title'] in request['prompt']
    assert 'independent' in request['prompt'] and 'unreviewed' in request['prompt']
    old_manifest = {'parts': [{'id': 'whole', 'marks': 12}], 'evidence': {'kind': 'unpartitioned_whole_question'}}
    old = {**row, 'required_parts': old_manifest['parts'], 'required_parts_evidence': old_manifest['evidence']}
    assert helper().bound_packet(row, old_manifest, lib, course) == check.build_packet(old)


def receipt(packet):
    return {'packet_digest': packet['digest'], 'item_id': packet['item_id'], 'kind': packet['kind'],
            'outcome': 'solved', 'answer': None, 'context_complete': True,
            'question_number': str(packet['binding']['item']['label']), 'scheme_question_number': str(packet['binding']['item']['label']), 'reasons': ['Actual source association checked'],
            'parts': [{'id': p['id'], 'question_marks': p['marks'], 'scheme_marks': p['marks'],
                       'question_present': True, 'scheme_present': True, 'values_match': True, 'units_match': True}
                      for p in packet['required_parts']],
            'proposals': [{'part_id': p['id'], 'chapter_ids': [], 'prerequisite_ids': [], 'status': 'unreviewed',
                           'disposition': 'unresolved', 'reason': 'No supported mapping from this source'}
                          for p in packet['required_parts']]}


@pytest.mark.parametrize('tamper', [False, True, 'wire', 'derived', 'derived_v1'])
def test_publisher_reconstructs_graph_bound_packet_and_reuses_saved_runner_receipt(tmp_path, monkeypatch, tamper):
    from dataclasses import asdict
    import publish_native
    q, docs, lib, course = source_question(tmp_path, 'flat' if tamper == 'derived_v1' else 'nested')
    for c in ('S2', 'S1', 'P1', 'P2', 'P3', 'P4'):
        copy_to_vault(f'build/out/specs/{c}/graph.json', lib.root)
    lib = AssetLibrary(lib.root)
    q['official_qid'] = f'{course}-q{q["number"]}'
    row = {'id': q['official_qid'], 'kind': 'written', 'marks': q['whole_assessment']['max_marks'], 'source_verified': True,
           'mastery_certified': False, 'kcs': [], 'held_reasons': [],
           'regions': q['question_regions'], 'question_media': ['q1', 'q2', 'q3', 'q4'],
           'mark_scheme_regions': q['scheme_regions'], 'mark_scheme_media': ['ms'], 'label': str(q['number'])}
    if tamper in ('derived', 'derived_v1'):
        row['context_media'] = ['derived/qp-cover.png']
        row['context_regions'] = [{**q['question_regions'][0], 'page': 1}]
    manifest = native_part_manifest.derive(q, docs['qp'], prepared_scope._words)
    packet = helper().bound_packet(row, manifest, lib, course)
    attempt = check.record_attempt(packet, receipt(packet), model='gpt-6-luna', effort='low')
    assert check.evaluate_receipt(packet, attempt)['status'] == 'checked'
    state_root = tmp_path / 'worker'; state_dir = state_root / 'semantic-checks' / packet['digest']; state_dir.mkdir(parents=True)
    state = {'qid': row['id'], 'packet_digest': packet['digest'], 'status': 'checked',
             'attempts': [{'envelope': asdict(attempt)}]}
    state_path = state_dir / 'state.json'; state_path.write_text(json.dumps(state)); saved = state_path.read_bytes()
    package = tmp_path / 'package'; package.mkdir()
    for reference in ['q1', 'q2', 'q3', 'q4', 'ms']:
        (package / reference).write_bytes(b'authenticated disposable pixels')
    pixels = {ref: b'authenticated disposable pixels' for ref in ['q1', 'q2', 'q3', 'q4', 'ms']}
    if tamper in ('derived', 'derived_v1'):
        pixels['derived/qp-cover.png'] = docs['qp'][0].get_pixmap(dpi=72, alpha=False).tobytes('png')
    monkeypatch.setattr(helper(), 'MEDIA_CACHE_ROOT', tmp_path / 'Candidates')
    request = helper().plan_request(packet, [])
    wire = helper().request_provenance(request, [helper().resolve_replay_image(package, ref, {'_pixels': pixels}) for ref in request['images']])
    if tamper == 'wire': wire['prompt'] = 'forged prompt'
    state['attempts'][0]['request_provenance'] = wire
    state_path.write_text(json.dumps(state)); saved = state_path.read_bytes()
    (package / 'descriptor.json').write_text(json.dumps({'course': course,
        'sources': {'qp': {'asset_id': q['question_regions'][0]['source_id']}}, 'questions': [q]}))
    if tamper is True:
        q['whole_assessment']['printed_markers']['qp'][0]['text'] = '(z)'
        (package / 'descriptor.json').write_text(json.dumps({'course': course,
            'sources': {'qp': {'asset_id': q['question_regions'][0]['source_id']}}, 'questions': [q]}))
    monkeypatch.setattr(publish_native, 'R', state_root)
    monkeypatch.setattr(publish_native, 'original_verify', lambda vault, output: {'items': [row], 'held': [{'id': 'quarantined'}],
        '_pixels': pixels})
    result = publish_native.approved(lib.root, package)
    held = tamper is True or tamper == 'wire'
    assert result['items'] == ([] if held else [row])
    assert result['held'] == [{'id': 'quarantined'}]
    if not held:
        assert result['semantic_verification'][0]['request_provenance'] == [wire]
        assert result['semantic_verification'][0]['packet_digest'] == packet['digest']
        assert result['semantic_verification'][0]['verdict']['mapping_status'] == 'unresolved'
    assert state_path.read_bytes() == saved


def test_actual_wire_provenance_retains_prompt_schema_and_image_bytes(tmp_path):
    request = {'prompt': 'actual literal prompt', 'schema': {'type': 'object'}, 'images': ['public/a.png']}
    path = tmp_path / 'pixels'; path.write_bytes(b'authenticated-pixels')
    value = helper().request_provenance(request, [path])
    assert value['prompt'] == request['prompt'] and value['schema'] == request['schema']
    assert value['prompt_sha256'] == hashlib.sha256(request['prompt'].encode()).hexdigest()
    assert value['images'] == [{'reference': 'public/a.png', 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}]


@pytest.mark.parametrize('mode', ['changed', 'error', 'unknown', 'checked'])
def test_runner_never_launches_on_prior_binding_error_unknown_quota_or_checked(tmp_path, monkeypatch, mode):
    import asyncio
    from dataclasses import asdict
    import check_current
    q, docs, lib, _ = source_question(tmp_path, 'nested')
    manifest = native_part_manifest.derive(q, docs['qp'], prepared_scope._words)
    row = {'id': 'S2-q6', 'kind': 'written', 'marks': 12, 'source_verified': True,
           'regions': q['question_regions'], 'question_media': ['q1', 'q2', 'q3', 'q4'],
           'mark_scheme_regions': q['scheme_regions'], 'mark_scheme_media': ['ms'], 'label': '6',
           'required_parts': manifest['parts'], 'required_parts_evidence': manifest['evidence']}
    packet = check.build_packet(row)
    content = receipt(packet)
    if mode != 'checked': content['outcome'] = 'uncertain'
    attempt = check.record_attempt(packet, content, model='gpt-6-luna', effort='low', error='timeout' if mode == 'error' else None)
    state_root = tmp_path / 'worker'; directory = state_root / 'semantic-checks' / packet['digest']; directory.mkdir(parents=True)
    state = {'qid': row['id'], 'packet_digest': packet['digest'], 'status': 'checked' if mode == 'checked' else 'checkpointed_usage_floor_or_unknown',
             'attempts': [{'envelope': asdict(attempt)}]}
    state_path = directory / 'state.json'; state_path.write_text(json.dumps(state)); saved = state_path.read_bytes()
    (state_root / 'run.json').write_text(json.dumps({'stop_floor': 10}))
    observations = []
    class OfflineClient:
        def __init__(self, **kwargs): pass
        async def one_shot(self, *args, **kwargs): pytest.fail('unexpected paid launch')
        async def close(self): pass
    class OfflineCollection:
        release = 'disposable'
        _items = {row['id']: {**row, **({'new_binding': True} if mode == 'changed' else {})}}
        def __init__(self, root): pass
    monkeypatch.setattr(check_current, 'R', state_root)
    monkeypatch.setattr(check_current, 'Collection', OfflineCollection)
    monkeypatch.setattr(check_current, 'CodexAI', OfflineClient)
    monkeypatch.setattr(check_current, 'codex_usage', lambda binary: observations.append(True))
    asyncio.run(check_current.main(row['id']))
    assert len(observations) == (2 if mode == 'unknown' else 0)
    after = json.loads(state_path.read_bytes())
    assert after['attempts'] == state['attempts']
    if mode in ('checked', 'changed'): assert state_path.read_bytes() == saved
    if mode == 'error': assert after['status'] == 'held_provider_infrastructure'
    assert len(list((state_root / 'semantic-checks').iterdir())) == 1


@pytest.mark.parametrize('fault', ['question_prefix', 'wrong_question_prefix', 'repeated_parent'])
def test_nested_question_prefix_and_repeated_parent_heading(tmp_path, fault):
    import re
    q, docs, _, _ = source_question(tmp_path, 'nested')
    mutated = {p.number: copy.deepcopy(prepared_scope._words(p)) for p in docs['qp']}
    if fault == 'repeated_parent':
        next(w for w in mutated[17] if w['text'] == '(d)')['text'] = '(c)'
    else:
        next(w for w in mutated[17] if w['text'] == '(a)')['text'] = '6(a)' if fault == 'question_prefix' else '7(a)'
    q['whole_assessment']['printed_markers']['qp'] = [
        {'text': w['text'], 'region': {**r, 'box': w['box']}}
        for r in q['question_regions'] for w in mutated[r['page'] - 1]
        if w['box'][0] < .25 and re.fullmatch(r'(?:[1-9]\d?\.?)?\((?:[a-z]|[ivx]+)\)', w['text'])]
    manifest = native_part_manifest.derive(q, docs['qp'], lambda p: mutated[p.number])
    assert manifest['status'] == ('source_manifest' if fault == 'question_prefix' else 'held')


def test_replay_derived_context_materializes_exact_bytes_outside_complete_package(tmp_path, monkeypatch):
    package = tmp_path / 'COMPLETE'; package.mkdir()
    (package / 'descriptor.json').write_bytes(b'unchanged complete descriptor')
    before = {p.name: p.read_bytes() for p in package.iterdir()}
    monkeypatch.setattr(helper(), 'MEDIA_CACHE_ROOT', tmp_path / 'Candidates', raising=False)
    ref = 'derived/qp-cover.png'; replay = {'_pixels': {ref: b'fresh authenticated PNG'}}
    path = helper().resolve_replay_image(package, ref, replay)
    assert path.read_bytes() == replay['_pixels'][ref]
    assert path.is_relative_to(tmp_path / 'Candidates')
    assert helper().resolve_replay_image(package, ref, replay) == path
    assert {p.name: p.read_bytes() for p in package.iterdir()} == before
    provenance = helper().request_provenance({'prompt': 'actual', 'schema': {}, 'images': [ref]}, [path])
    assert provenance['images'] == [{'reference': ref, 'sha256': hashlib.sha256(replay['_pixels'][ref]).hexdigest()}]


@pytest.mark.parametrize('fault', ['packaged', 'cached', 'symlink', 'unsafe_ref', 'unreplayed_ref'])
def test_replay_image_resolver_rejects_tampering_and_unsafe_references(tmp_path, monkeypatch, fault):
    package = tmp_path / 'COMPLETE'; package.mkdir()
    monkeypatch.setattr(helper(), 'MEDIA_CACHE_ROOT', tmp_path / 'Candidates', raising=False)
    ref = 'derived/cover.png'; replay = {'_pixels': {ref: b'fresh replay'}}
    if fault == 'packaged':
        (package / 'derived').mkdir(); (package / ref).write_bytes(b'tampered package')
    elif fault in ('cached', 'symlink'):
        path = helper().resolve_replay_image(package, ref, replay)
        path.chmod(0o644)
        if fault == 'cached': path.write_bytes(b'tampered cache')
        else:
            path.unlink(); target = tmp_path / 'other.png'; target.write_bytes(b'fresh replay'); path.symlink_to(target)
    elif fault == 'unsafe_ref':
        ref = '../escape.png'; replay['_pixels'][ref] = b'fresh replay'
    else: ref = 'not-in-fresh-replay.png'
    with pytest.raises(ValueError): helper().resolve_replay_image(package, ref, replay)


def test_runner_passes_transient_replay_context_to_fake_client_and_provenance(tmp_path, monkeypatch):
    import asyncio
    from types import SimpleNamespace
    import check_current
    import source_practice
    q, docs, lib, course = source_question(tmp_path, 'nested')
    for c in ('S2', 'S1', 'P1', 'P2', 'P3', 'P4'):
        copy_to_vault(f'build/out/specs/{c}/graph.json', lib.root)
    lib = AssetLibrary(lib.root); q['official_qid'] = 'S2-q6'
    context_ref = 'derived/qp-cover.png'
    context = docs['qp'][0].get_pixmap(dpi=72, alpha=False).tobytes('png')
    row = {'id': q['official_qid'], 'kind': 'written', 'marks': 12, 'source_verified': True, 'label': '6',
           'regions': q['question_regions'], 'question_media': ['q1', 'q2', 'q3', 'q4'],
           'mark_scheme_regions': q['scheme_regions'], 'mark_scheme_media': ['ms'],
           'context_regions': [{**q['question_regions'][0], 'page': 1}], 'context_media': [context_ref]}
    manifest = native_part_manifest.derive(q, docs['qp'], prepared_scope._words)
    packet = helper().bound_packet(row, manifest, lib, course)
    package = tmp_path / 'COMPLETE'; package.mkdir()
    descriptor = {'course': course, 'sources': {'qp': {'asset_id': q['question_regions'][0]['source_id']}}, 'questions': [q]}
    (package / 'descriptor.json').write_text(json.dumps(descriptor))
    pixels = {ref: b'authenticated source pixels' for ref in row['question_media'] + row['mark_scheme_media']}
    for ref, data in pixels.items(): (package / ref).write_bytes(data)
    pixels[context_ref] = context
    before = {p.name: p.read_bytes() for p in package.iterdir()}
    state_root = tmp_path / 'worker'; state_root.mkdir()
    (state_root / 'run.json').write_text(json.dumps({'stop_floor': 10}))
    calls = []
    class OfflineClient:
        def __init__(self, **kwargs): pass
        async def one_shot(self, prompt, **kwargs):
            paths = kwargs['images']; calls.append(paths)
            assert paths[0].read_bytes() == context and paths[0].is_relative_to(tmp_path / 'Candidates')
            return receipt(packet), SimpleNamespace(ok=True, usage={})
        async def close(self): pass
    class OfflineCollection:
        release = 'disposable'
        library = lib
        def __init__(self, root): pass
    monkeypatch.setattr(helper(), 'MEDIA_CACHE_ROOT', tmp_path / 'Candidates', raising=False)
    monkeypatch.setattr(check_current, 'R', state_root)
    monkeypatch.setattr(check_current, 'Collection', OfflineCollection)
    monkeypatch.setattr(check_current, 'CodexAI', OfflineClient)
    monkeypatch.setattr(check_current, 'codex_usage', lambda binary: {'seven_day': {'used': 20}})
    monkeypatch.setattr(source_practice, 'verify', lambda vault, output: {'items': [row], '_pixels': pixels})
    asyncio.run(check_current.main(row['id'], package))
    assert len(calls) == 1
    state = json.loads((state_root / 'semantic-checks' / packet['digest'] / 'state.json').read_bytes())
    assert state['status'] == 'checked'
    assert state['attempts'][0]['request_provenance']['images'][0] == {
        'reference': context_ref, 'sha256': hashlib.sha256(context).hexdigest()}
    assert {p.name: p.read_bytes() for p in package.iterdir()} == before
