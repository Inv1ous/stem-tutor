"""Bounded whole-total witnesses from immutable Library originals."""
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
from tutorlib.prepared_evidence import _whole_total

sys.path.insert(0, str(Path(__file__).parents[1] / 'extraction'))
CASES = {
    'bracket': ('asset:asset-188c5884602560d3bb345fde',
                'asset:asset-02e6878b363bb062d8932285', 4, (5, 6), (12,), '[6 marks]', 6),
    'later-part': ('asset:asset-21e7d3db2d89e5f129a140f0',
                   'asset:asset-27430605964c81a79e5b7eb7', 8, (13, 14), (12, 13, 14), 'Total 12', 12),
}


def module():
    return importlib.import_module('prepared_scope')


def region(role, page):
    return {'role': role, 'page': page, 'box': [0, 0, 1, 1]}


@pytest.fixture
def originals(tmp_path):
    vault = tmp_path / 'vault'
    vault.mkdir()
    for asset in sorted({a for case in CASES.values() for a in case[:2]}):
        copy_to_vault(canonical_path(asset), vault)
        catalog_path = vault / 'Library/catalog.json'
        catalog = json.loads(catalog_path.read_text())
        key = next(k for k, v in catalog['assets'].items() if v['path'] == canonical_path(asset))
        catalog['assets'][asset[6:]] = catalog['assets'].pop(key)
        catalog_path.write_text(json.dumps(catalog))
    copy_to_vault('Library/Shared/Sources/Specifications/ial-maths-spec.pdf', vault)
    return AssetLibrary(vault)


def request_for(lib, case):
    qp, ms, number, qp_pages, ms_pages, _, _ = CASES[case]
    public = [region('qp', p) for p in qp_pages]
    private = [region('ms', p) for p in ms_pages]
    sources = {}
    for role, asset in [('qp', qp), ('ms', ms)]:
        with pymupdf.open(stream=lib.read(asset), filetype='pdf') as doc:
            sources[role] = {'asset_id': asset, 'sha256': lib.record(asset)['sha256'],
                             'inspection_pages': list(range(1, len(doc) + 1))}
    return {'course': 'FP1', 'sources': sources, 'questions': [{
        'number': number, 'assessment_mode': 'whole_official_rubric_v1',
        'question_regions': public, 'scheme_regions': private,
        'parts': [{'part': '', 'label': '', 'question_media_regions': public,
                   'scheme_media_regions': private}]}]}


@pytest.mark.parametrize('case', CASES)
def test_actual_whole_total_retains_exact_literal_and_all_assessed_parts(originals, case):
    m = module()
    request = request_for(originals, case)
    q = request['questions'][0]
    source = request['sources']['ms']
    with pymupdf.open(stream=originals.read(source['asset_id']), filetype='pdf') as doc:
        layout = m._source_layout(doc, 'ms')
        total = m._located_whole_total(q, {'ms': layout}, {}, 'ms')
        assert (total['label'], total['value'], total['region']['page']) == (*CASES[case][-2:], 12)
        assert m._region_text(doc, [total['region']]) == total['label']
        assert _whole_total(total['label'], 'ms', q['number']) == total['value']
        text = m._region_text(doc, q['scheme_regions'])
        assert all(label in text for label in (('4.(a)', '(b)', '(c)', 'Alternative')
                                               if case == 'bracket' else ('8(i)', '(ii)', 'Notes')))


def table(*, total='[6 marks]', notes=None):
    """Disposable assessed rows; these synthetic inputs never enter Library."""
    doc = pymupdf.open()
    page = doc.new_page()
    for x, y, text in [(45, 45, 'Question'), (45, 60, 'Number'),
                        (200, 45, 'Scheme'), (500, 45, 'Marks')]:
        page.insert_text((x, y), text, fontsize=11)
    for y, label, marks in [(100, '1(a)', 2), (250, '(b)', 4)]:
        page.insert_text((50, y), label, fontsize=11)
        page.insert_text((200, y), 'Assessed working', fontsize=11)
        page.insert_text((500, y + 10), 'M1', fontsize=11)
        page.insert_text((550, y + 50), f'({marks})', fontsize=11)
    page.insert_text((500, 400), total, fontsize=11)
    if notes is not None:
        page.insert_text((50, notes), 'Notes', fontsize=11)
    return doc


def located(doc):
    m = module()
    return m._located_whole_total({'number': 1, 'scheme_regions': [region('ms', 1)]},
                                  {'ms': m._source_layout(doc, 'ms')}, {}, 'ms')


@pytest.mark.parametrize('total,notes', [('[6 marks]', None), ('Total 6', 200)])
def test_new_literals_need_complete_assessed_rows_even_after_intervening_notes(total, notes):
    with table(total=total, notes=notes) as doc:
        assert located(doc)['label'] == total


@pytest.mark.parametrize('total', ['[6 marks]', 'Total 6'])
@pytest.mark.parametrize('remaining', ['assessed-row', 'mark-only', 'allocation-only', 'unsupported-mark'])
def test_post_total_notes_cannot_hide_remaining_assessment(total, remaining):
    with table(total=total) as doc:
        page = doc[0]
        page.insert_text((50, 430), 'Notes', fontsize=11)
        if remaining == 'assessed-row':
            # Exact independently reviewed counterexample: the final Notes
            # cutoff formerly hid this complete, positively scored part.
            page.insert_text((50, 470), '(c)', fontsize=11)
            page.insert_text((200, 470), 'Additional assessed working', fontsize=11)
        if remaining in ('assessed-row', 'mark-only', 'unsupported-mark'):
            page.insert_text((500, 480), 'A1ft' if remaining == 'unsupported-mark' else 'M1', fontsize=11)
        if remaining in ('assessed-row', 'allocation-only'):
            page.insert_text((550, 520), '(1)', fontsize=11)
        with pytest.raises(ValueError, match='unique independent ms'):
            located(doc)


@pytest.mark.parametrize('total', ['[6 marks]', 'Total 6'])
def test_post_total_notes_preserve_harmless_part_and_scoring_references(total):
    with table(total=total) as doc:
        page = doc[0]
        page.insert_text((50, 430), 'Notes', fontsize=11)
        page.insert_text((50, 470), '(c)', fontsize=11)
        page.insert_text((200, 470), 'Refer to M1 in (b), example (1)', fontsize=11)
        assert located(doc)['label'] == total


@pytest.mark.parametrize('total', ['[6 marks]', 'Total 6'])
@pytest.mark.parametrize('fault', ['notes-total', 'fake-part-reference', 'missing-allocation',
    'part-bracket', 'conflict', 'wrong-column', 'inline-prose', 'unknown-part',
    'skipped-part', 'alternative', 'unknown-mark', 'missing-header', 'not-final',
    'wrong-question', 'wrong-sum', 'notes-code-reference', 'missing-scoring', 'scheme-scoring',
    'pre-row-code'])
def test_new_whole_total_counterexamples_remain_held(fault, total):
    with table(total=total) as doc:
        page = doc[0]
        def erase(x0, y0, x1, y1):
            page.add_redact_annot(pymupdf.Rect(x0, y0, x1, y1))
            page.apply_redactions()
        if fault == 'notes-total':
            page.insert_text((50, 350), 'Notes', fontsize=11)
        elif fault in ('fake-part-reference', 'notes-code-reference'):
            page.insert_text((50, 330), 'Notes', fontsize=11)
            page.insert_text((50, 350), '(c)', fontsize=11)
            page.insert_text((200, 350), 'Refer to earlier assessed part', fontsize=11)
            if fault == 'notes-code-reference':
                page.insert_text((500, 360), 'M1', fontsize=11)
        elif fault == 'missing-allocation':
            erase(545, 285, 580, 305)
        elif fault == 'part-bracket':
            erase(495, 385, 590, 405)
            page.insert_text((500, 180), '[2 marks]', fontsize=11)
        elif fault == 'conflict':
            page.insert_text((500, 430), '[7 marks]', fontsize=11)
        elif fault == 'wrong-column':
            erase(495, 385, 590, 405)
            page.insert_text((300, 400), '[6 marks]', fontsize=11)
        elif fault == 'inline-prose':
            page.insert_text((470, 400), 'award', fontsize=11)
        elif fault in ('unknown-part', 'skipped-part'):
            erase(45, 235, 85, 255)
            page.insert_text((50, 250), '(foo)' if fault == 'unknown-part' else '(c)', fontsize=11)
        elif fault == 'alternative':
            page.insert_text((200, 200), 'OR:', fontsize=11)
        elif fault == 'unknown-mark':
            page.insert_text((500, 280), 'A1ft', fontsize=11)
        elif fault == 'missing-header':
            erase(40, 30, 100, 65)
        elif fault == 'not-final':
            page.insert_text((500, 430), 'A1', fontsize=11)
        elif fault == 'wrong-question':
            erase(45, 85, 85, 105)
            page.insert_text((50, 100), '2(a)', fontsize=11)
        elif fault == 'wrong-sum':
            erase(545, 285, 580, 305)
            page.insert_text((550, 300), '(3)', fontsize=11)
        elif fault in ('missing-scoring', 'scheme-scoring'):
            erase(495, 95, 530, 115)
            if fault == 'scheme-scoring':
                page.insert_text((350, 110), 'M1', fontsize=11)
        elif fault == 'pre-row-code':
            page.insert_text((500, 85), 'M1', fontsize=11)
        with pytest.raises(ValueError, match='unique independent ms'):
            located(doc)


@pytest.mark.parametrize('content', ['part', 'total', 'combined-code'])
def test_unheaded_assessed_continuation_cannot_be_omitted_from_whole_maximum(content):
    m = module()
    with table() as doc:
        page = doc.new_page()
        if content == 'part':
            page.insert_text((50, 100), '(c)', fontsize=11)
            page.insert_text((500, 120), 'M1', fontsize=11)
            page.insert_text((550, 150), '(1)', fontsize=11)
        else:
            page.insert_text((500, 100), 'Total 7' if content == 'total' else 'M1A1', fontsize=11)
        q = {'number': 1, 'scheme_regions': [region('ms', p) for p in (1, 2)]}
        with pytest.raises(ValueError, match='unique independent ms'):
            m._located_whole_total(q, {'ms': m._source_layout(doc, 'ms')}, {}, 'ms')


@pytest.mark.parametrize('alternative', ['OR:', 'or:', 'Or:', 'oR:', 'OR', 'or', 'Or', 'oR'])
def test_standalone_alternative_heading_does_not_prove_unique_allocations(alternative):
    with table() as doc:
        doc[0].insert_text((200, 200), alternative, fontsize=11)
        with pytest.raises(ValueError, match='unique independent ms'):
            located(doc)


def test_independent_qp_agreement_cannot_override_new_ms_maximum():
    m = module()
    with table() as ms, pymupdf.open() as qp:
        qp.new_page().insert_text((50, 100), '(Total 7 marks)', fontsize=11)
        q = {'number': 1, 'scheme_regions': [region('ms', 1)], 'question_regions': [region('qp', 1)]}
        with pytest.raises(ValueError, match='maxima differ'):
            m._whole_assessment(q, {role: m._source_layout(doc, role)
                                   for role, doc in [('qp', qp), ('ms', ms)]}, {})


def test_neutral_bracket_total_is_exact_and_ms_only():
    assert _whole_total('[6 marks]', 'ms', 4) == 6
    for label, role in [('[6]', 'ms'), ('[6 marks]', 'qp'), ('award [6 marks]', 'ms'),
                        ('[6 marks] available', 'ms'), ('[0 marks]', 'ms')]:
        with pytest.raises(ValueError):
            _whole_total(label, role, 4)


@pytest.mark.parametrize('case', CASES)
def test_actual_prepare_replay_preserves_complete_pixels_and_rejects_resealed_total(originals, tmp_path, case):
    m = module()
    request = request_for(originals, case)
    path = tmp_path / 'request.json'
    path.write_text(json.dumps(request))
    out = tmp_path / 'package'
    descriptor = m.prepare_native(path, out, originals, 'a' * 64)
    assert m.verify_native_package(out, originals, 'a' * 64) == descriptor
    q = descriptor['questions'][0]
    assert q['whole_assessment']['max_marks'] == CASES[case][-1]
    assert [r['page'] for r in q['scheme_regions']] == list(CASES[case][4])
    for name, media in descriptor['media'].items():
        r = media['region']
        asset = request['sources'][r['role']]['asset_id']
        with pymupdf.open(stream=originals.read(asset), filetype='pdf') as doc:
            expected = doc[r['page'] - 1].get_pixmap(dpi=144, alpha=False).tobytes('png')
        assert (out / name).read_bytes() == expected
        assert media['visibility'] == ('public' if r['role'] == 'qp' else 'private')
    changed = copy.deepcopy(descriptor)
    changed['questions'][0]['whole_assessment']['totals']['ms']['region']['box'][0] += .001
    (out / 'descriptor.json').write_bytes(m.canonical_bytes(changed))
    complete = json.loads((out / 'COMPLETE').read_bytes())
    complete['descriptor_sha256'] = hashlib.sha256((out / 'descriptor.json').read_bytes()).hexdigest()
    (out / 'COMPLETE').write_bytes(m.canonical_bytes(complete))
    with pytest.raises(ValueError, match='source_recomputation'):
        m.verify_native_package(out, originals, 'a' * 64)


@pytest.mark.parametrize('case', CASES)
def test_source_drift_is_held_before_total_replay(originals, tmp_path, case):
    m = module()
    request = request_for(originals, case)
    path = tmp_path / 'request.json'
    path.write_text(json.dumps(request))
    out = tmp_path / 'package'
    m.prepare_native(path, out, originals, 'a' * 64)
    record = originals.record(request['sources']['ms']['asset_id'])
    (originals.root / record['path']).write_bytes(b'changed disposable source')
    with pytest.raises(ValueError, match='digest|hash|sha256'):
        m.verify_native_package(out, originals, 'a' * 64)
