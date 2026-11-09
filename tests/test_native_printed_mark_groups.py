"""Indivisible printed parents retain every source child and literal maximum."""
import copy
import importlib.util
import json
from pathlib import Path
import sys

import pymupdf
import pytest
from library_assets import canonical_path, copy_to_vault
from tutorlib.asset_library import AssetLibrary
from test_native_nested_check_manifests import source_question, receipt

ROOT = Path(__file__).resolve().parents[2]
WORKER = ROOT / 'Work/Workers/extraction/overnight-20261105-10pct'
sys.path[:0] = [str(WORKER), str(ROOT / 'stem-tutor/extraction')]
import prepared_scope
import native_part_manifest
import native_nested_parts as nested


def groups():
    assert importlib.util.find_spec('native_printed_mark_groups'), 'printed parent proof is missing'
    return __import__('native_printed_mark_groups')


def native_source(tmp_path):
    vault = tmp_path / 'native-vault'; vault.mkdir()
    refs = {'qp': 'asset:asset-5167f429c608e94f09978eff', 'ms': 'asset:asset-d8f77908a39d96bd4a0b45cb'}
    for ref in refs.values(): copy_to_vault(canonical_path(ref), vault)
    library = AssetLibrary(vault)
    docs = {role: pymupdf.open(stream=library.read(ref), filetype='pdf') for role, ref in refs.items()}
    question = {'number': 5, 'official_qid': 'FP3_pearson-edexcel-ial_WFM03_2023-01_01_q5'}
    for role, field, pages in [('qp', 'question_regions', range(12, 16)), ('ms', 'scheme_regions', [14, 15])]:
        question[field] = [{'source_id': refs[role], 'source_sha256': library.record(refs[role])['sha256'],
                            'role': role, 'page': page, 'box': [0, 0, 1, 1]} for page in pages]
    layouts = {role: [{'words': prepared_scope._words(page)} for page in doc] for role, doc in docs.items()}
    question['whole_assessment'] = prepared_scope._whole_assessment(question, layouts, {})
    question['witness'] = {'qp_parts': [], 'ms_parts': ['a']}
    return question, docs, library


def test_real_fp3_source_parent_retains_all_children_without_child_marks(tmp_path):
    question, docs, _ = native_source(tmp_path)
    assert nested.derive_nested(question, docs['qp'], prepared_scope._words)['reason'] == groups().TRIGGER
    manifest = native_part_manifest.derive(question, docs['qp'], prepared_scope._words)
    assert manifest['status'] == 'source_manifest'
    assert manifest['parts'] == [{'id': 'a', 'marks': 2}, {'id': 'b', 'marks': 5}, {'id': 'c', 'marks': 5}]
    evidence = manifest['evidence']
    assert evidence['kind'] == evidence['source_profile'] == groups().KIND
    assert sum(part['marks'] for part in manifest['parts']) == evidence['whole_maximum'] == 12
    group, = evidence['parent_groups']
    assert group['parent']['id'] == 'b'
    assert [child['id'] for child in group['children']] == ['b(i)', 'b(ii)']
    assert all(set(child) == {'id', 'region'} for child in group['children'])
    assert group['maximum']['marks'] == 5 and group['maximum']['label'] == '(5)'
    for child in group['children']:
        assert child['region']['source_sha256'] == question['question_regions'][0]['source_sha256']
    assert 'mastery' not in json.dumps(manifest)


def test_real_pmt_source_parent_reaches_new_fallback(tmp_path, monkeypatch):
    from test_pmt_complete_profile import staged
    import pmt_complete_profile, source_practice, prepared_source_packet
    reference = 'asset:asset-d0f29d9cd25224c431401a46'
    vault = staged(tmp_path, reference)
    for course in ('M1', 'P1', 'P2', 'P3', 'P4'):
        copy_to_vault(f'build/out/specs/{course}/graph.json', vault)
    monkeypatch.setattr(source_practice, 'WORKERS', tmp_path / 'no-workers')
    package = tmp_path / 'Work/Preparation/pmt'
    pmt_complete_profile.prepare(vault, reference, 'M1', package, dpi=72)
    replay = source_practice.verify(vault, package)
    row = next(row for row in replay['items'] if row['id'] == 'occurrence-6f0392eb3268522314297be7')
    manifest, packet = prepared_source_packet.prepared_packet(package, replay, row, AssetLibrary(vault))
    assert manifest['status'] == 'source_manifest'
    assert manifest['parts'] == [{'id': 'a', 'marks': 5}, {'id': 'b', 'marks': 3}, {'id': 'c', 'marks': 3}]
    evidence = manifest['evidence']
    assert evidence['source_profile'] == prepared_source_packet.PMT_PROFILE
    assert evidence['derivation_kind'] == groups().KIND
    assert [c['id'] for c in evidence['parent_groups'][0]['children']] == ['a(i)', 'a(ii)']
    assert packet['required_parts'] == manifest['parts']
    assert packet['binding']['item']['chapter_catalog']['course'] == 'M1'


@pytest.mark.parametrize('fault', ['missing_child', 'duplicate_child', 'gap_child', 'shifted_parent',
    'clipped_marker', 'partial_group', 'stray_numeric', 'false_equation_tag',
    'out_of_order', 'source', 'whole_max_conflict', 'forged_witness', 'parent_marks',
    'zero_numeric', 'numeric_label', 'incomplete_label'])
def test_shared_parent_ambiguities_stay_held(tmp_path, fault):
    question, docs, _ = native_source(tmp_path)
    mutated = {page.number: copy.deepcopy(prepared_scope._words(page)) for page in docs['qp']}
    page = mutated[11]
    parent = next(word for word in page if word['text'] == '(b)')
    first = next(word for word in page if word['text'] == '(i)')
    second = next(word for word in page if word['text'] == '(ii)')
    if fault == 'zero_numeric': page.append({'text': '(0)', 'box': [.83, .8, .86, .82]})
    elif fault == 'numeric_label': page.append({'text': '(1)', 'box': [.13, .8, .15, .82]})
    elif fault == 'incomplete_label': second['text'] = '(ii'
    elif fault == 'missing_child': page.remove(second)
    elif fault == 'duplicate_child': second['text'] = '(i)'
    elif fault == 'gap_child': second['text'] = '(iii)'
    elif fault == 'shifted_parent': parent['box'][0] = .03
    elif fault == 'clipped_marker':
        question['question_regions'][0]['box'][3] = second['box'][1] + .001
    elif fault == 'partial_group':
        # Three children, allocation after i and after iii: never guess an ii+iii sub-group.
        third = copy.deepcopy(second); third['text'] = '(iii)'; third['box'] = [second['box'][0], .35, second['box'][2], .37]
        at = page.index(second); page.insert(at + 1, third)
        page.append({'text': '(1)', 'box': [.83, .29, .86, .30]})
    elif fault == 'stray_numeric': page.append({'text': '(2)', 'box': [.83, .8, .86, .82]})
    elif fault == 'false_equation_tag':
        mark = next(word for word in page if word['text'] == '(5)')
        page.append({'text': 'equation', 'box': [.4, mark['box'][1], .6, mark['box'][3]]})
    elif fault == 'out_of_order':
        first['box'][1], second['box'][1] = second['box'][1], first['box'][1]
    elif fault == 'source': question['question_regions'][0]['source_sha256'] = '0' * 64
    elif fault == 'whole_max_conflict': question['whole_assessment']['totals']['ms']['value'] = 11
    elif fault == 'forged_witness': question['whole_assessment']['printed_markers']['qp'][0]['text'] = '(z)'
    elif fault == 'parent_marks': page.append({'text': '(1)', 'box': [.83, .264, .86, .267]})
    if fault not in ('missing_child', 'clipped_marker', 'source', 'forged_witness', 'incomplete_label'):
        question['whole_assessment']['printed_markers']['qp'] = [
            {'text': word['text'], 'region': {**region, 'box': word['box']}}
            for region in question['question_regions'] for word in mutated[region['page'] - 1]
            if word['box'][0] < .25 and nested.LABEL.fullmatch(word['text'])]
    assert native_part_manifest.derive(question, docs['qp'], lambda page: mutated[page.number])['status'] == 'held'


@pytest.mark.parametrize('name', ['flat', 'whole', 'nested', 'reverse'])
def test_accepted_old_manifest_and_packet_fingerprints_stay_exact(tmp_path, name):
    question, docs, library, course = source_question(tmp_path, name)
    for spec in ('FP1', 'FP2', 'FP3', 'S2', 'S1', 'P1', 'P2', 'P3', 'P4'):
        copy_to_vault(f'build/out/specs/{spec}/graph.json', library.root)
    library = AssetLibrary(library.root)
    original = native_part_manifest._derive_v1(question, docs['qp'], prepared_scope._words)
    if original['status'] != 'source_manifest':
        original = nested.derive_nested(question, docs['qp'], prepared_scope._words)
    current = native_part_manifest.derive(question, docs['qp'], prepared_scope._words)
    assert json.dumps(current) == json.dumps(original)
    row = {'id': f'{course}-q{question["number"]}', 'kind': 'written', 'source_verified': True,
           'marks': question['whole_assessment']['max_marks'], 'label': str(question['number']),
           'regions': question['question_regions'], 'mark_scheme_regions': question['scheme_regions'],
           'question_media': ['qp'], 'mark_scheme_media': ['ms']}
    assert json.dumps(nested.bound_packet(row, current, library, course)) == json.dumps(nested.bound_packet(row, original, library, course))


def test_flat_shared_marks_without_explicit_parent_stay_held(tmp_path):
    question, docs, _ = native_source(tmp_path)
    mutated = {page.number: copy.deepcopy(prepared_scope._words(page)) for page in docs['qp']}
    labels = iter('abcde')
    for region in question['question_regions']:
        for word in mutated[region['page'] - 1]:
            if word['box'][0] < .25 and nested.LABEL.fullmatch(word['text']):
                word['text'] = '(' + next(labels) + ')'; word['box'][0] = .13; word['box'][2] = .15
    question['whole_assessment']['printed_markers']['qp'] = [
        {'text': word['text'], 'region': {**region, 'box': word['box']}}
        for region in question['question_regions'] for word in mutated[region['page'] - 1]
        if word['box'][0] < .25 and nested.LABEL.fullmatch(word['text'])]
    assert native_part_manifest.derive(question, docs['qp'], lambda page: mutated[page.number])['status'] == 'held'


def group_packet(tmp_path):
    question, docs, library = native_source(tmp_path)
    for course in ('FP3', 'FP2', 'FP1', 'P1', 'P2', 'P3', 'P4'):
        copy_to_vault(f'build/out/specs/{course}/graph.json', library.root)
    library = AssetLibrary(library.root)
    row = {'id': question['official_qid'], 'course': 'FP3', 'kind': 'written', 'marks': 12,
           'source_verified': True, 'mastery_certified': False, 'kcs': [], 'label': '5',
           'regions': question['question_regions'], 'mark_scheme_regions': question['scheme_regions'],
           'question_media': ['q1', 'q2', 'q3', 'q4'], 'mark_scheme_media': ['ms1', 'ms2'],
           'private_guidance_regions': [{**question['scheme_regions'][0], 'page': page} for page in range(3, 7)],
           'private_guidance_media': ['guidance']}
    manifest = native_part_manifest.derive(question, docs['qp'], prepared_scope._words)
    packet = groups().bound_packet(row, manifest, library, 'FP3')
    package = tmp_path / 'native-package'; package.mkdir()
    (package / 'descriptor.json').write_text(json.dumps({'course': 'FP3',
        'sources': {'qp': {'asset_id': question['question_regions'][0]['source_id']}}, 'questions': [question]}))
    pixels = {reference: b'authenticated disposable source pixels ' + reference.encode()
              for reference in row['question_media'] + row['mark_scheme_media'] + row['private_guidance_media']}
    for reference, data in pixels.items(): (package / reference).write_bytes(data)
    return row, manifest, packet, library, package, pixels


def test_native_group_packet_binds_all_images_private_rubric_and_registered_chapters(tmp_path):
    import prepared_source_packet
    row, expected, expected_packet, library, package, _pixels = group_packet(tmp_path)
    manifest, packet = prepared_source_packet.prepared_packet(package, {'items': [row]}, row, library)
    assert manifest == expected and packet == expected_packet
    bound = packet['binding']['item']
    assert bound['regions'] == row['regions']
    assert bound['mark_scheme_regions'] == row['mark_scheme_regions']
    assert bound['private_guidance_regions'] == row['private_guidance_regions']
    assert packet['required_parts'] == [{'id': 'a', 'marks': 2}, {'id': 'b', 'marks': 5}, {'id': 'c', 'marks': 5}]
    assert packet['binding']['allowed_chapter_ids']
    assert bound['mastery_certified'] is False and bound['kcs'] == []
    request = nested.plan_request(packet, [])
    assert 'unreviewed' in request['prompt'] and 'never certify mastery' in request['prompt']


@pytest.mark.parametrize('fault', ['pending', 'no_attempt', 'unchecked', 'missing_wire', 'prompt', 'schema', 'image', 'model', 'effort', None])
def test_native_group_publisher_requires_actual_bound_wire_and_keeps_source_holds(tmp_path, monkeypatch, fault):
    from dataclasses import asdict
    import lightweight_verification as check
    import publish_native
    row, manifest, packet, library, package, pixels = group_packet(tmp_path)
    worker = tmp_path / 'worker'; worker.mkdir()
    request = nested.plan_request(packet, [])
    provenance = nested.request_provenance(request, [package / reference for reference in request['images']])
    attempt = check.record_attempt(packet, receipt(packet), model=request['model'], effort=request['effort'])
    state = {'qid': row['id'], 'packet_digest': packet['digest'], 'status': 'checked',
             'attempts': [{'envelope': asdict(attempt), 'request_provenance': provenance}]}
    entry = state['attempts'][0]
    if fault == 'no_attempt': state['attempts'] = []
    elif fault == 'unchecked': state['status'] = 'hold'
    elif fault == 'missing_wire': del entry['request_provenance']
    elif fault == 'prompt': entry['request_provenance']['prompt'] += ' forged'
    elif fault == 'schema': entry['request_provenance']['schema'] = {}
    elif fault == 'image': entry['request_provenance']['images'][0]['sha256'] = '0' * 64
    elif fault == 'model': entry['envelope']['model'] = 'gpt-6.1-sol'
    elif fault == 'effort': entry['envelope']['effort'] = 'medium'
    path = worker / 'semantic-checks' / packet['digest'] / 'state.json'
    if fault != 'pending':
        path.parent.mkdir(parents=True); path.write_text(json.dumps(state))
    before = {p.relative_to(worker): p.read_bytes() for p in worker.rglob('*') if p.is_file()}
    monkeypatch.setattr(publish_native, 'R', worker)
    monkeypatch.setattr(publish_native, 'original_verify', lambda *_: {'items': [row], '_pixels': pixels,
        'held': [{'id': 'old147-quarantine', 'reasons': ['unchanged-current-source-hold']}]})
    if fault == 'model':
        with pytest.raises(ValueError, match='invalid attempt history binding or tier'):
            publish_native.approved(library.root, package)
        assert {p.relative_to(worker): p.read_bytes() for p in worker.rglob('*') if p.is_file()} == before
        return
    result = publish_native.approved(library.root, package)
    assert result['items'] == ([row] if fault is None else [])
    assert result['held'] == [{'id': 'old147-quarantine', 'reasons': ['unchanged-current-source-hold']}]
    assert {p.relative_to(worker): p.read_bytes() for p in worker.rglob('*') if p.is_file()} == before
    if fault is None:
        assert result['semantic_verification'][0]['request_provenance'] == [provenance]
        assert result['semantic_verification'][0]['verdict']['mapping_status'] == 'unresolved'


@pytest.mark.parametrize('fault', ['unverified', 'absent', 'maximum', 'regions'])
def test_group_packet_rejects_unqualified_or_different_source_row(tmp_path, fault):
    import prepared_source_packet
    row, _manifest, _packet, library, package, _pixels = group_packet(tmp_path)
    replay = {'items': [copy.deepcopy(row)]}
    if fault == 'unverified': row['source_verified'] = False; replay['items'] = [row]
    elif fault == 'absent': replay['items'] = []
    elif fault == 'maximum': row['marks'] = 13; replay['items'] = [row]
    else: row['regions'] = row['regions'][:-1]; replay['items'] = [row]
    with pytest.raises(ValueError, match='fresh.*source|fresh verified'):
        prepared_source_packet.prepared_packet(package, replay, row, library)


def test_shared_parent_preserves_other_parents_individual_leaf_allocations():
    reference, sha = 'asset:disposable-source', '1' * 64
    region = {'source_id': reference, 'source_sha256': sha, 'role': 'qp', 'page': 1, 'box': [0, 0, 1, 1]}
    values = []
    def label(text, y, child=False):
        values.append({'text': text, 'box': [.16 if child else .12, y, .19 if child else .15, y + .01]})
    def mark(marks, y): values.append({'text': f'({marks})', 'box': [.83, y, .86, y + .01]})
    label('(a)', .1); label('(i)', .15, True); mark(2, .18)
    label('(ii)', .22, True); mark(3, .25)
    label('(b)', .3); label('(i)', .35, True); label('(ii)', .4, True); mark(5, .43)
    label('(c)', .5); mark(3, .55)
    question = {'number': 1, 'question_regions': [region], 'witness': {'qp_parts': [], 'ms_parts': []},
                'whole_assessment': {'max_marks': 13,
                    'totals': {role: {'value': 13, 'region': {**region, 'role': role}} for role in ('qp', 'ms')},
                    'printed_markers': {'qp': [{'text': word['text'], 'region': {**region, 'box': word['box']}}
                                             for word in values if nested.LABEL.fullmatch(word['text'])], 'ms': []}}}
    manifest = native_part_manifest.derive(question, [object()], lambda _: values)
    assert manifest['parts'] == [{'id': 'a(i)', 'marks': 2}, {'id': 'a(ii)', 'marks': 3},
                                 {'id': 'b', 'marks': 5}, {'id': 'c', 'marks': 3}]
    assert [g['parent']['id'] for g in manifest['evidence']['parent_groups']] == ['b']
