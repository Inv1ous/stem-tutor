"""Native PMT written authority from registered, disposable real-source fixtures."""
import hashlib
import json
from pathlib import Path
import sys

import pymupdf
import pytest
from library_assets import canonical_path, copy_to_vault

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'extraction'))
import source_practice as build
import topical_fastpath as topical
from tutorlib.asset_library import AssetLibrary

SORTING = 'asset:asset-acce130254fa1022369632e7'
IMPACT = 'asset:asset-0ca41c32586f12e4786d8fe0'
MODELLING = 'asset:asset-c636826ce6bae364e03564f9'
TRIG = 'asset:asset-5b09d0e0e2f8b1f9e620d007'
MIXED = 'asset:asset-548a7193599a829723e46a06'
SET2 = 'asset:asset-95faae8d29d1745ae87bce06'


def source(tmp_path, reference, course):
    vault = tmp_path / 'vault'
    vault.mkdir(exist_ok=True)
    path = copy_to_vault(canonical_path(reference), vault)
    catalog_path = vault / 'Library/catalog.json'
    catalog = json.loads(catalog_path.read_bytes())
    key = next(k for k, v in catalog['assets'].items() if v['path'] == path.relative_to(vault).as_posix())
    catalog['assets'][reference.removeprefix('asset:')] = catalog['assets'].pop(key)
    catalog_path.write_text(json.dumps(catalog))
    library = AssetLibrary(vault)
    raw = library.read(reference)
    registered = library.record(reference)['path']
    fresh = topical.analyse_source(raw, course, reference, source_path=registered)
    return vault, raw, registered, fresh


def prepared(tmp_path, reference, course):
    vault, raw, registered, fresh = source(tmp_path, reference, course)
    output = tmp_path / 'preparation'
    topical.prepare(vault, reference, course, output, dpi=72)
    return vault, output


@pytest.fixture(autouse=True)
def isolated_workers(tmp_path, monkeypatch):
    monkeypatch.setattr(build, 'WORKERS', tmp_path / 'no-workers')


@pytest.mark.parametrize('reference,course,count,marks,comment_page', [
    (SORTING, 'D1', 10, [11, 11, 9, 4, 5, 11, 8, 9, 9, 9], 17),
    (IMPACT, 'M1', 6, [7, 6, 6, 9, 7, 10], 7),
    (MODELLING, 'S1', 1, [4], 3),
    (TRIG, 'P2', 9, [9, 10, 5, 7, 14, 10, 8, 8, 10], 8),
])
def test_native_family_original_pixels_complete_schemes_and_printed_totals(
        tmp_path, reference, course, count, marks, comment_page):
    vault, output = prepared(tmp_path, reference, course)
    result = build.verify(vault, output)
    assert len(result['items']) == count and result['held'] == []
    assert [q['marks'] for q in result['items']] == marks
    assert all(q['kind'] == 'structured' and q['official_qid'] is None
               and q['canonical_id'].startswith('occurrence-') for q in result['items'])
    assert all(q['maximum_authority'] == 'printed_question_total' for q in result['items'])
    assert all(q['question_media'] and q['mark_scheme_media'] for q in result['items'])
    for q in result['items']:
        assert all(result['media'][m]['region'] == r for m, r in zip(q['question_media'], q['regions']))
        assert all(result['_pixels'][m] for m in q['question_media'] + q['mark_scheme_media'])
        assert all(r['page'] < comment_page for r in q['mark_scheme_regions'])
    if reference == SORTING:
        assert {r['page'] for r in result['items'][1]['mark_scheme_regions']} == {6, 7, 8}
        assert 'Choosing first' in result['items'][1]['scheme_text']
        # Notes following a bracket total still belong to the private rubric.
        assert 12 in {r['page'] for r in result['items'][4]['mark_scheme_regions']}
    if reference == IMPACT:
        assert {r['page'] for r in result['items'][5]['mark_scheme_regions']} == {5, 6}
    with pymupdf.open(stream=AssetLibrary(vault).read(reference), filetype='pdf') as doc:
        assert result['title'] == doc[0].get_text().splitlines()[0].strip()


def test_mixed_question_scheme_page_holds_incomplete_public_inventory(tmp_path):
    vault, output = prepared(tmp_path, MIXED, 'P4')
    with pytest.raises(ValueError, match='incomplete_public_question_inventory'):
        build.verify(vault, output)


def test_set2_question_only_source_is_refused(tmp_path):
    vault, output = prepared(tmp_path, SET2, 'FP2')
    with pytest.raises(ValueError, match='unsupported PMT written source profile'):
        build.verify(vault, output)


@pytest.mark.parametrize('fault', ['label', 'missing', 'private_region'])
def test_resealed_family_public_association_is_rejected(tmp_path, fault):
    vault, output = prepared(tmp_path, MODELLING, 'S1')
    bundle = json.loads((output / 'bundle.json').read_bytes())
    if fault == 'label':
        bundle['questions'][0]['label'] = '2'
    elif fault == 'missing':
        bundle['questions'].clear()
    else:
        bundle['questions'][0]['regions'][0]['page'] = 2
    raw = json.dumps(bundle).encode()
    (output / 'bundle.json').write_bytes(raw)
    (output / 'COMPLETE').write_text(hashlib.sha256(raw).hexdigest())
    with pytest.raises(ValueError):
        build.verify(vault, output)


@pytest.mark.parametrize('fault', ['total', 'wrong_total', 'missing_anchor', 'duplicate_anchor'])
def test_missing_ambiguous_or_mismatched_scheme_never_admitted(tmp_path, fault):
    from pmt_source_profile import compile_written
    _, raw, registered, fresh = source(tmp_path, MODELLING, 'S1')
    with pymupdf.open(stream=raw, filetype='pdf') as doc:
        page = doc[1]
        target = '[4]' if fault in {'total', 'wrong_total'} else '1.'
        matches = page.search_for(target)
        assert matches
        if fault == 'duplicate_anchor':
            page.insert_text((56.7, 400), '1.', fontsize=11)
        else:
            for box in matches:
                page.add_redact_annot(box, fill=(1, 1, 1))
            page.apply_redactions()
            if fault == 'wrong_total':
                page.insert_text((matches[0].x0, matches[0].y1), '[5]', fontsize=11)
        altered = doc.tobytes()
    fresh = topical.analyse_source(altered, 'S1', MODELLING, source_path=registered)
    try:
        _, _, items = compile_written(altered, fresh, source_path=registered)
    except ValueError:
        return
    assert items and all(q.get('hold_reasons') for q in items)


def test_family_written_runtime_preserves_private_gate_and_public_media(tmp_path):
    from tutorlib.source_practice import Collection
    vault, output = prepared(tmp_path, MODELLING, 'S1')
    build.publish(vault, [output], expected_current=None)
    collection = Collection(vault)
    q = collection.questions('S1')[0]
    public = collection.question(q['id'])
    assert public['question_media']
    assert not {'scheme_text', 'mark_scheme_media'} & public.keys()
    for ref in public['question_media']:
        assert collection.media_path(q['id'], ref).is_file()
    attempt = collection.submit(q['id'], 'original written work')
    refs = collection.feedback(attempt['attempt_id'])['scheme_media']
    assert refs
    with pytest.raises(ValueError):
        collection.media_path(q['id'], refs[0])
    assert collection.media_path(q['id'], refs[0], attempt_id=attempt['attempt_id']).is_file()


def test_missing_scheme_continuation_total_holds_only_affected_question(tmp_path):
    from pmt_source_profile import compile_written
    _, raw, registered, _ = source(tmp_path, IMPACT, 'M1')
    with pymupdf.open(stream=raw, filetype='pdf') as doc:
        doc.delete_page(5)
        altered = doc.tobytes()
    fresh = topical.analyse_source(altered, 'M1', IMPACT, source_path=registered)
    _, _, items = compile_written(altered, fresh, source_path=registered)
    assert len(items) == 6
    assert all(not q.get('hold_reasons') for q in items[:5])
    assert items[5]['marks'] is None and items[5]['hold_reasons']


def test_private_notes_before_same_page_commentary_anchor_are_retained(tmp_path):
    from pmt_source_profile import compile_written
    _, raw, registered, _ = source(tmp_path, MODELLING, 'S1')
    note = 'SCHEME CONTINUATION NOTE: allow equivalent model.'
    with pymupdf.open(stream=raw, filetype='pdf') as doc:
        doc[2].insert_text((100, 65), note, fontsize=8)
        altered = doc.tobytes()
    fresh = topical.analyse_source(altered, 'S1', MODELLING, source_path=registered)
    _, _, items = compile_written(altered, fresh, source_path=registered)
    assert len(items) == 1 and not items[0].get('hold_reasons')
    assert note in items[0]['scheme_text']
    assert {r['page'] for r in items[0]['mark_scheme_regions']} == {2, 3}
    with pymupdf.open(stream=altered, filetype='pdf') as doc:
        anchor_top = doc[2].search_for('1.')[0].y0 / doc[2].rect.height
    assert items[0]['mark_scheme_regions'][-1]['box'][3] < anchor_top


def test_unassigned_public_continuation_holds_even_when_labels_and_totals_match(tmp_path):
    from pmt_source_profile import compile_written
    _, raw, registered, _ = source(tmp_path, MODELLING, 'S1')
    with pymupdf.open(stream=raw, filetype='pdf') as doc:
        page = doc.new_page(pno=1, width=doc[0].rect.width, height=doc[0].rect.height)
        page.insert_text((90, 120), 'Further instructions for the modelling question: explain your assumptions.', fontsize=10)
        page.insert_text((56, 810), 'Edexcel Internal Review', fontsize=10)
        altered = doc.tobytes()
    fresh = topical.analyse_source(altered, 'S1', MODELLING, source_path=registered)
    assert [q['label'] for q in fresh['questions']] == ['1']
    assert any(r['page'] == 2 for r in fresh['review_pages'])
    assert all(r['page'] != 2 for q in fresh['questions'] for r in q['regions'])
    with pytest.raises(ValueError, match='incomplete_public_question_inventory'):
        compile_written(altered, fresh, source_path=registered)
