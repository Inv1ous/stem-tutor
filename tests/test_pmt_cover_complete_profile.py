"""Complete v2 native source proof, using digest-checked Library fixtures."""
import importlib
import importlib.util
import hashlib
import json
from pathlib import Path
import sys

import pymupdf
import pytest
from library_assets import canonical_path, copy_to_vault, read_bytes

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'extraction'))
SURDS = 'asset:asset-1987d297a29c4c35a1eb55e1'
INEQUALITIES = 'asset:asset-33eaeba3d5e3aea227ec991b'
SLOPE = 'asset:asset-75f11891f644730dd4fb4b8f'
DIRECT_IMPACT = 'asset:asset-0ca41c32586f12e4786d8fe0'


@pytest.fixture(autouse=True)
def no_live_guards(tmp_path, monkeypatch):
    import source_practice
    monkeypatch.setattr(source_practice, 'WORKERS', tmp_path / 'no-workers')


def profile():
    assert importlib.util.find_spec('pmt_cover_complete_profile') is not None, 'complete v2 PMT adapter missing'
    return importlib.import_module('pmt_cover_complete_profile')


def analyse(reference=INEQUALITIES, course='P1', raw=None):
    return profile().analyse(read_bytes(reference) if raw is None else raw, course, reference,
                             source_path=canonical_path(reference))


def test_real_inequalities_has_complete_geometry_and_only_native_q10_semantic_hold():
    bundle = analyse()
    assert bundle['profile'] == 'pmt-native-cover-complete-set1-v2'
    assert len(bundle['questions']) == 11
    assert [q['label'] for q in bundle['questions'] if q.get('hold_reasons')] == ['10']
    held = bundle['questions'][9]
    assert held['marks'] is None
    assert held['printed_total_witness'] == '(Total 7 marks)'
    assert held['scheme_total_witness'] == '[8]'
    assert held['mark_scheme_regions'] and held['regions']
    assert bundle['pages'][0]['role'] == 'public_frontmatter'
    for q in bundle['questions']:
        assert q['context_regions'] == [{'source_id': INEQUALITIES,
            'source_sha256': bundle['source']['sha256'], 'page': 1, 'box': [0, 0, 1, 1]}]
        assert q['official_qid'] is None
    for page in bundle['pages']:
        assert page['intervals'][0]['box'][1] == 0 and page['intervals'][-1]['box'][3] == 1
        assert all(a['box'][3] == b['box'][1] for a, b in zip(page['intervals'], page['intervals'][1:]))


def test_actual_v1_semantic_failure_is_isolated_after_complete_geometry():
    bundle = analyse(SLOPE, 'M1')
    assert len(bundle['questions']) > 1
    assert any(q.get('hold_reasons') for q in bundle['questions'])
    assert any(not q.get('hold_reasons') for q in bundle['questions'])
    assert all(q['regions'] and q['mark_scheme_regions'] for q in bundle['questions'])


def test_actual_surds_placeholder_cover_count_uses_independent_full_sequences():
    bundle = analyse(SURDS)
    assert len(bundle['questions']) == 24
    assert bundle['cover_count'] == {'declared_count': None, 'literal': 'There are xx questions in this test.', 'derived_count': 24}
    assert not any(q.get('hold_reasons') for q in bundle['questions'])
    assert all(q['printed_total_geometry'] for q in bundle['questions'])


def derivative(reference, page_number, target=None, replacement=None, point=None, paint=False):
    with pymupdf.open(stream=read_bytes(reference), filetype='pdf') as doc:
        page = doc[page_number-1]
        if target:
            boxes = page.search_for(target)
            assert boxes
            for box in boxes: page.add_redact_annot(box, fill=(1, 1, 1))
            page.apply_redactions()
            point = point or (boxes[0].x0, boxes[0].y1-3)
        if replacement: page.insert_text(point, replacement, fontsize=10)
        if paint: page.draw_rect(pymupdf.Rect(100, 12, 140, 20), fill=(0, 0, 0))
        return doc.tobytes()


@pytest.mark.parametrize('fault', [
    'unit', 'course', 'cover_count', 'placeholder', 'cover_watermark', 'body_watermark',
    'cover_private', 'cover_paint', 'header', 'footer', 'missing_ms', 'duplicate_ms',
    'coefficient', 'role_conflict', 'unknown_tail', 'crossing_formula',
])
def test_identity_furniture_sequence_and_physical_ambiguity_hold_whole_source(fault):
    if fault == 'course':
        with pytest.raises(ValueError): analyse(course='P2')
        return
    changes = {
        'unit': (1, '6663/01', '6664/01', None),
        'cover_count': (1, 'There are 11 questions in this test.', 'There are 12 questions in this test.', None),
        'placeholder': (1, 'There are 11 questions in this test.', 'There are unknown questions in this test.', None),
        'cover_watermark': (1, 'PhysicsAndMathsTutor.com', None, None),
        'body_watermark': (9, 'PhysicsAndMathsTutor.com', None, None),
        'cover_private': (1, None, 'M1 A1 Answer: x=2', (100, 720)),
        'header': (2, None, 'UNOWNED PREMISE', (100, 25)),
        'footer': (2, None, 'UNOWNED PREMISE', (100, 835)),
        'missing_ms': (6, '1.', None, None),
        'duplicate_ms': (8, None, '1.', (56.7, 700)),
        'coefficient': (6, '1.', '1', None),
        'role_conflict': (7, 'Mark Schemes', 'Questions', None),
        'unknown_tail': (18, 'Examiner Reports', 'Unknown Material', None),
    }
    if fault == 'cover_paint': raw = derivative(INEQUALITIES, 1, paint=True)
    elif fault == 'crossing_formula':
        with pymupdf.open(stream=read_bytes(INEQUALITIES), filetype='pdf') as doc:
            doc[6].draw_line((280, 40), (280, 100), width=2)
            raw = doc.tobytes()
    else:
        page, target, replacement, point = changes[fault]
        raw = derivative(INEQUALITIES, page, target, replacement, point)
    with pytest.raises(ValueError): analyse(raw=raw)


@pytest.mark.parametrize('fault', ['total_mismatch', 'public_ms', 'public_answer', 'scheme_commentary'])
def test_one_owned_semantic_error_holds_only_its_question(fault):
    if fault == 'total_mismatch': raw = derivative(INEQUALITIES, 6, '[6]', '[9]')
    elif fault == 'public_ms': raw = derivative(INEQUALITIES, 2, replacement='M1 A1', point=(300, 110))
    elif fault == 'public_answer': raw = derivative(INEQUALITIES, 2, replacement='Answer: x=2', point=(300, 110))
    else: raw = derivative(INEQUALITIES, 6, replacement='Most candidates found this difficult.', point=(100, 730))
    bundle = analyse(raw=raw)
    assert [q['label'] for q in bundle['questions'] if q.get('hold_reasons')] == ['1', '10']
    assert bundle['questions'][0]['marks'] is None
    assert bundle['questions'][1]['marks'] == 10


@pytest.mark.parametrize('reference', [SURDS, INEQUALITIES])
def test_occurrence_ids_match_original_topical_source_recipe(reference):
    import topical_fastpath
    raw = read_bytes(reference)
    original = topical_fastpath.analyse_source(raw, 'P1', reference, source_path=canonical_path(reference))
    bundle = analyse(reference)
    assert [q['id'] for q in bundle['questions']] == [q['id'] for q in original['questions']]
    assert all(q['scheme_total_geometry'] for q in bundle['questions'])


def test_old_v1_rejection_and_profile_identity_remain_exact():
    import pmt_complete_profile
    assert pmt_complete_profile.PROFILE == 'pmt-native-complete-set1-v1'
    for reference, course in [(INEQUALITIES, 'P1'), (SLOPE, 'M1')]:
        with pytest.raises(ValueError):
            pmt_complete_profile.analyse(read_bytes(reference), course, reference,
                                         source_path=canonical_path(reference))


def test_existing_mixed_page_and_formula_geometry_matches_frozen_v1():
    import pmt_complete_profile
    reference = 'asset:asset-548a7193599a829723e46a06'
    raw = read_bytes(reference)
    old = pmt_complete_profile.analyse(raw, 'P4', reference, source_path=canonical_path(reference))
    new = analyse(reference, 'P4')
    assert new['pages'] == old['pages']
    assert new['private_pages'] == old['private_pages']
    for before, after in zip(old['questions'], new['questions']):
        assert all(after[k] == v for k, v in before.items())
    assert any({'questions', 'mark_scheme'} <= {i['role'] for i in page['intervals']} for page in new['pages'])


@pytest.mark.parametrize('kind', ['text', 'vector', 'image'])
def test_disconnected_unknown_content_after_total_cannot_be_owned_as_public(kind):
    with pymupdf.open(stream=read_bytes(INEQUALITIES), filetype='pdf') as doc:
        page = doc[1]
        if kind == 'text': page.insert_text((200, 290), 'x = 123456789', fontsize=10)
        elif kind == 'vector': page.draw_rect(pymupdf.Rect(200, 280, 230, 290), fill=(0, 0, 0))
        else:
            from PIL import Image
            import io
            stream = io.BytesIO(); Image.new('RGB', (5, 5), 'white').save(stream, format='PNG')
            page.insert_image(pymupdf.Rect(200, 280, 230, 290), stream=stream.getvalue())
        raw = doc.tobytes()
    with pytest.raises(ValueError, match='ownership|separator'): analyse(raw=raw)


def test_bounded_native_bare_ms_label_completes_full_original_sequence():
    bundle = analyse(DIRECT_IMPACT, 'M1')
    assert [q['label'] for q in bundle['questions']] == [str(n) for n in range(1, 7)]
    assert not any(q['hold_reasons'] for q in bundle['questions'])
    assert 'Alternative' in bundle['questions'][4]['scheme_text']
    assert 'The two parts of this question may be done in either order.' in bundle['questions'][4]['scheme_text']
    assert [r['page'] for r in bundle['questions'][5]['mark_scheme_regions']] == [5, 6]


@pytest.mark.parametrize('fault', ['no_part', 'off_gutter', 'coefficient'])
def test_bare_coefficients_or_misaligned_labels_cannot_repair_missing_scheme(fault):
    with pymupdf.open(stream=read_bytes(DIRECT_IMPACT), filetype='pdf') as doc:
        page = doc[4]
        label = next(w for w in page.get_text('words') if w[4] == '6' and w[0] < 80 and w[1] > 700)
        if fault == 'no_part':
            part = next(w for w in page.get_text('words') if w[4] == '(a)' and abs(w[1]-label[1]) < 3)
            page.add_redact_annot(pymupdf.Rect(part[:4]), fill=(1, 1, 1))
            page.apply_redactions()
        else:
            page.add_redact_annot(pymupdf.Rect(label[:4]), fill=(1, 1, 1))
            page.apply_redactions()
            page.insert_text((100 if fault == 'off_gutter' else label[0], label[3]-3),
                             '6' if fault == 'off_gutter' else '6x', fontsize=11)
        raw = doc.tobytes()
    with pytest.raises(ValueError): analyse(DIRECT_IMPACT, 'M1', raw)


@pytest.mark.parametrize('fault', ['above_09', 'below_006', 'left_0045', 'right_012'])
def test_bare_ms_absolute_bounds_cannot_move_original_private_ownership(fault):
    import topical_fastpath
    from pmt_source_profile import compile_written
    with pymupdf.open(stream=read_bytes(DIRECT_IMPACT), filetype='pdf') as doc:
        page = doc[4]
        label = next(w for w in page.get_text('words') if w[4] == '6' and w[0] < 80 and w[1] > 700)
        page.add_redact_annot(pymupdf.Rect(label[:4]), fill=(1, 1, 1))
        page.apply_redactions()
        x, baseline = label[0], label[3]-3
        if fault == 'above_09': baseline = page.rect.height * .91 + 10
        elif fault == 'below_006': baseline = page.rect.height * .059 + 10
        else:
            # Keep the relative-gutter condition satisfied while crossing an
            # old absolute x boundary. The first dotted MS anchor remains in
            # its valid old gutter; no public question anchor is moved.
            first = doc[3]
            anchor = next(w for w in first.get_text('words') if w[4] == '1.' and w[0] < 80)
            first.add_redact_annot(pymupdf.Rect(anchor[:4]), fill=(1, 1, 1))
            first.apply_redactions()
            first_x, bare_x = (.046, .044) if fault == 'left_0045' else (.119, .121)
            first.insert_text((first.rect.width * first_x, anchor[3]-3), '1.', fontsize=11)
            x = page.rect.width * bare_x
        page.insert_text((x, baseline), '6   (a)', fontsize=10)
        raw = doc.tobytes()
    original = topical_fastpath.analyse_source(raw, 'M1', DIRECT_IMPACT,
                                               source_path=canonical_path(DIRECT_IMPACT))
    with pytest.raises(ValueError):
        compile_written(raw, original, source_path=canonical_path(DIRECT_IMPACT))
    with pytest.raises(ValueError): analyse(DIRECT_IMPACT, 'M1', raw)


def staged(tmp_path, reference):
    vault = tmp_path / 'vault'
    vault.mkdir()
    path = copy_to_vault(canonical_path(reference), vault)
    catalog_path = vault / 'Library/catalog.json'
    catalog = json.loads(catalog_path.read_bytes())
    key = next(k for k, v in catalog['assets'].items() if v['path'] == path.relative_to(vault).as_posix())
    catalog['assets'][reference.removeprefix('asset:')] = catalog['assets'].pop(key)
    catalog_path.write_text(json.dumps(catalog))
    return vault


@pytest.mark.parametrize('reference,count,held', [(SURDS, 24, []), (INEQUALITIES, 10, ['10'])])
def test_disposable_preparation_fresh_source_pixels_and_per_item_holds(tmp_path, reference, count, held):
    import source_practice
    vault = staged(tmp_path, reference)
    output = tmp_path / 'Work/Preparation/cover-v2'
    bundle = profile().prepare(vault, reference, 'P1', output, dpi=72)
    result = source_practice.verify(vault, output)
    assert len(result['items']) == count
    held_ids = {q['id'] for q in bundle['questions'] if q['label'] in held}
    assert {q['id'] for q in result['held']} == held_ids
    assert result['metrics']['page_renders'] == bundle['source']['pages']
    assert all(q['context_media'] and q['mark_scheme_media'] for q in result['items'])
    assert all(result['_pixels'][m] for q in result['items'] for m in q['context_media'] + q['mark_scheme_media'])
    with pytest.raises(FileExistsError): profile().prepare(vault, reference, 'P1', output, dpi=72)


@pytest.mark.parametrize('fault', ['clear_hold', 'cover_clip', 'ledger', 'total_witness', 'pixel', 'kind'])
def test_resealed_v2_cannot_override_source_hold_context_geometry_or_pixels(tmp_path, fault):
    import source_practice
    vault = staged(tmp_path, INEQUALITIES)
    output = tmp_path / 'Work/Preparation/cover-v2'
    bundle = profile().prepare(vault, INEQUALITIES, 'P1', output, dpi=72)
    if fault == 'clear_hold': bundle['questions'][9]['hold_reasons'] = []
    elif fault == 'cover_clip': bundle['questions'][0]['context_regions'][0]['box'][3] = .5
    elif fault == 'ledger': bundle['pages'][0]['intervals'][0]['role'] = 'running_header'
    elif fault == 'total_witness': bundle['questions'][9]['scheme_total_geometry']['literal'] = '[7]'
    elif fault == 'kind': bundle['kind'] = 'pmt_complete_preparation'
    else:
        name = bundle['questions'][0]['context_media'][0]
        (output / name).write_bytes(b'forged cover')
        bundle['media'][name]['sha256'] = hashlib.sha256(b'forged cover').hexdigest()
    raw = json.dumps(bundle).encode()
    (output / 'bundle.json').write_bytes(raw)
    (output / 'COMPLETE').write_text(hashlib.sha256(raw).hexdigest())
    with pytest.raises(ValueError): source_practice.verify(vault, output)


def test_v2_worker_packet_retains_actual_profile_cover_and_whole_source_hold(tmp_path):
    from tutorlib.asset_library import AssetLibrary
    from test_prepared_source_checks import helper
    import source_practice
    vault = staged(tmp_path, INEQUALITIES)
    for course in ('M1', 'P1', 'P2', 'P3', 'P4', 'S1', 'S2'):
        copy_to_vault(f'build/out/specs/{course}/graph.json', vault)
    output = tmp_path / 'Work/Preparation/cover-v2'
    profile().prepare(vault, INEQUALITIES, 'P1', output, dpi=72)
    replay = source_practice.verify(vault, output)
    row = replay['items'][1]
    manifest, packet = helper().prepared_packet(output, replay, row, AssetLibrary(vault))
    assert manifest['status'] == 'source_manifest'
    assert manifest['parts'] == [{'id': 'a', 'marks': 3}, {'id': 'b', 'marks': 4}, {'id': 'c', 'marks': 3}]
    assert manifest['evidence']['source_profile'] == profile().PROFILE
    assert packet['binding']['item']['required_parts_evidence']['source_profile'] == profile().PROFILE
    assert packet['binding']['item']['context_media'] == row['context_media']
    import native_nested_parts
    request = native_nested_parts.plan_request(packet, [])
    assert request['images'][0] == row['context_media'][0]
    held = analyse()['questions'][9]
    with pytest.raises(ValueError, match='absent'):
        helper().prepared_packet(output, replay, held, AssetLibrary(vault))
