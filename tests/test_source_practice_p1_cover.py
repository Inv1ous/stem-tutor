"""Positive legacy C1 cover authentication, with original source boundaries."""
import re

import pymupdf
import pytest
from test_source_practice_pmt_family import source
import topical_fastpath as topical
from pmt_source_profile import compile_written

SURDS = 'asset:asset-1987d297a29c4c35a1eb55e1'
INEQUALITIES = 'asset:asset-33eaeba3d5e3aea227ec991b'


@pytest.mark.parametrize('reference,title,count,held', [
    (SURDS, 'C1 Algebra: Surds and Indices – Questions', 24, []),
    (INEQUALITIES, 'C1 Algebra – Inequalities', 11, ['10']),
])
def test_native_c1_cover_title_original_media_and_complete_rubrics(tmp_path, reference, title, count, held):
    _, raw, registered, fresh = source(tmp_path, reference, 'P1')
    observed_title, pages, items = compile_written(raw, fresh, source_path=registered)
    assert observed_title == title
    assert pages[0] == {'page': 1, 'role': 'front_matter'}
    assert len(items) == count
    assert [q['label'] for q in items if q.get('hold_reasons')] == held
    assert all(q['official_qid'] is None and q['id'].startswith('occurrence-') for q in items)
    assert all(q['kind'] == 'structured' and q['maximum_authority'] == 'printed_question_total' for q in items)
    assert all(r['page'] > 1 for q in items for r in q['regions'] + q['mark_scheme_regions'])
    with pymupdf.open(stream=raw, filetype='pdf') as doc:
        cache = {}
        for q in items:
            for region in q['regions'] + q['mark_scheme_regions']:
                page = doc[region['page'] - 1]
                if region['page'] not in cache:
                    cache[region['page']] = page.get_pixmap(dpi=72, alpha=False)
                assert cache[region['page']].samples
            if not q.get('hold_reasons'):
                totals = re.findall(r'\[(\d+)\]', q['scheme_text'])
                assert totals and int(totals[-1]) == q['marks']
    if reference == SURDS:
        assert {r['page'] for r in items[7]['mark_scheme_regions']} >= {16, 17}
    else:
        assert {r['page'] for r in items[1]['mark_scheme_regions']} >= {7, 8}
        assert items[9]['marks'] is None  # Source ends this block with [8], public total is 7.


def derivative(raw, page_number, target, replacement=None):
    with pymupdf.open(stream=raw, filetype='pdf') as doc:
        page = doc[page_number - 1]; boxes = page.search_for(target)
        assert boxes
        for box in boxes:
            page.add_redact_annot(box, fill=(1, 1, 1))
        page.apply_redactions()
        if replacement:
            page.insert_text((boxes[0].x0, boxes[0].y1), replacement, fontsize=11)
        return doc.tobytes()


@pytest.mark.parametrize('fault', ['wrong_code', 'wrong_course', 'wrong_cover_course', 'cover_watermark', 'body_watermark'])
def test_cover_and_every_page_watermark_are_required(tmp_path, fault):
    _, raw, registered, fresh = source(tmp_path, SURDS, 'P1')
    if fault == 'wrong_course':
        fresh['course'] = 'P2'
    else:
        page, target, replacement = {
            'wrong_code': (1, '6663/01', '6664/01'),
            'wrong_cover_course': (1, 'Core Mathematics C1', 'Core Mathematics C2'),
            'cover_watermark': (1, 'PhysicsAndMathsTutor.com', None),
            'body_watermark': (17, 'PhysicsAndMathsTutor.com', None),
        }[fault]
        raw = derivative(raw, page, target, replacement)
        fresh = topical.analyse_source(raw, 'P1', SURDS, source_path=registered)
    with pytest.raises(ValueError):
        compile_written(raw, fresh, source_path=registered)


def test_cover_does_not_authorize_any_other_unresolved_public_page(tmp_path):
    _, raw, registered, fresh = source(tmp_path, SURDS, 'P1')
    fresh['review_pages'].append({'page': 2, 'reason': 'unanchored'})
    with pytest.raises(ValueError, match='incomplete_public_question_inventory'):
        compile_written(raw, fresh, source_path=registered)


@pytest.mark.parametrize('fault', ['missing_anchor', 'duplicate_anchor', 'wrong_total'])
def test_legacy_cover_keeps_scheme_ambiguity_and_total_holds(tmp_path, fault):
    _, raw, registered, _ = source(tmp_path, SURDS, 'P1')
    if fault == 'duplicate_anchor':
        with pymupdf.open(stream=raw, filetype='pdf') as doc:
            doc[8].insert_text((56.7, 400), '1.', fontsize=11)
            raw = doc.tobytes()
    else:
        raw = derivative(raw, 9, '[2]' if fault == 'wrong_total' else '1.', '[3]' if fault == 'wrong_total' else None)
    fresh = topical.analyse_source(raw, 'P1', SURDS, source_path=registered)
    if fault == 'wrong_total':
        _, _, items = compile_written(raw, fresh, source_path=registered)
        assert items[0]['marks'] is None and items[0]['hold_reasons']
    else:
        with pytest.raises(ValueError): compile_written(raw, fresh, source_path=registered)
