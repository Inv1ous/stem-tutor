"""Source proofs for native MS row variants; Library originals stay read-only."""
import importlib
import hashlib
import json
from pathlib import Path
import sys

import pymupdf
import pytest
from library_assets import canonical_path, copy_to_vault
from tutorlib.asset_library import AssetLibrary
from tutorlib.prepared_evidence import _whole_total

sys.path.insert(0, str(Path(__file__).parents[1] / 'extraction'))
M1_QP = 'asset:legacy-93ee75a63bbc175a4a777efd'
M1_MS = 'asset:legacy-100b1b43dde608b77e6e486e'
D1_QP = 'asset:legacy-e59b502724cb01349afa90d6'
D1_MS = 'asset:legacy-c500cc217afc7a29056bcc08'
P3_QP = 'asset:legacy-d5926522b9fc9292d6dd53e3'
P3_MS = 'asset:legacy-d2c7dcabe971fd99d5367aab'


def module():
    return importlib.import_module('prepared_scope')


@pytest.fixture
def originals(tmp_path):
    vault = tmp_path / 'vault'
    vault.mkdir()
    for asset in (M1_QP, M1_MS, D1_QP, D1_MS, P3_QP, P3_MS):
        copy_to_vault(canonical_path(asset), vault)
        catalog_path = vault / 'Library/catalog.json'
        catalog = json.loads(catalog_path.read_text())
        key = next(k for k, v in catalog['assets'].items() if v['path'] == canonical_path(asset))
        catalog['assets'][asset[6:]] = catalog['assets'].pop(key)
        catalog_path.write_text(json.dumps(catalog))
    copy_to_vault('Library/Shared/Sources/Specifications/ial-maths-spec.pdf', vault)
    return AssetLibrary(vault)


def open_original(lib, asset):
    return pymupdf.open(stream=lib.read(asset), filetype='pdf')


def region(role, page):
    return {'role': role, 'source_id': 'asset:synthetic-' + role,
            'source_sha256': 'a' * 64, 'page': page, 'box': [0, 0, 1, 1]}


def test_actual_m1_repeated_rows_preserve_complete_words_and_next_question_scope(originals):
    m = module()
    with open_original(originals, M1_QP) as qp, open_original(originals, M1_MS) as ms:
        layouts = {'qp': m._source_layout(qp, 'qp'), 'ms': m._source_layout(ms, 'ms')}
        assert [(p['page'], [s['number'] for s in p['starts']])
                for p in layouts['ms'] if p['starts']] == [
                    (7, [1]), (8, [2]), (9, [3]), (10, [4]), (11, [5]), (12, [6]), (14, [7])]
        assert all(p['words'] == m._words(ms[p['page'] - 1]) for p in layouts['ms'])
        sources = {role: {'asset_id': asset, 'sha256': originals.record(asset)['sha256']}
                   for role, asset in [('qp', M1_QP), ('ms', M1_MS)]}
        q = {'number': 6, 'question_regions': [region('qp', p) for p in range(16, 20)],
             'scheme_regions': [region('ms', 12), region('ms', 13)]}
        scope = m._whole_question_scope(q, layouts, sources)
        assert [r['page'] for r in scope['ms']] == [12, 13]
        assert scope['scheme_boundary'] == {'kind': 'next_question', 'page': 14, 'numbers': [7]}
        assert 'Notes' in m._region_text(ms, scope['ms'])
        # OR-bearing allocation tables remain held without a part-aware branch
        # proof; source words and the complete continuation still survive.
        with pytest.raises(ValueError, match='unique independent ms'):
            m._located_whole_total(q, layouts, sources, 'ms')
        q2 = {'number': 2, 'scheme_regions': [region('ms', 8)]}
        total = m._located_whole_total(q2, layouts, sources, 'ms')
        assert total['label'] == '13' and total['value'] == 13


def table_document(rows, *, header=True, total='10 marks', notes_y=500):
    """Disposable format counterexamples; never reusable teaching material."""
    doc = pymupdf.open()
    page = doc.new_page()
    if header:
        for x, y, text in [(45, 45, 'Question'), (45, 60, 'Number'),
                           (200, 45, 'Scheme'), (500, 45, 'Marks')]:
            page.insert_text((x, y), text, fontsize=11)
    for y, text in rows:
        page.insert_text((50, y), text, fontsize=11)
        page.insert_text((200, y), 'Method M1', fontsize=11)
    if total is not None:
        page.insert_text((500, 400), total, fontsize=11)
    if notes_y is not None:
        page.insert_text((250, notes_y), 'Notes', fontsize=11)
    return doc


def test_nested_part_rows_group_only_with_positive_table_headers():
    m = module()
    for header in (True, False):
        with table_document([(100, '1(a)(i)'), (150, '1(a)(ii)')], header=header) as doc:
            layout = m._source_layout(doc, 'ms')
            assert [s['number'] for s in layout[0]['starts']] == ([1] if header else [])
            assert [w['text'] for w in layout[0]['words'] if w['text'].startswith('1(')] == ['1(a)(i)', '1(a)(ii)']


def test_nonconsecutive_reset_and_different_questions_are_not_collapsed():
    m = module()
    with table_document([(100, '1(a)'), (150, '2(a)'), (200, '1(b)')]) as doc:
        layout = m._source_layout(doc, 'ms')
        assert [s['number'] for s in layout[0]['starts']] == [1, 2, 1]
    with table_document([(100, '1(a)'), (150, '1(b)'), (200, '2(a)')]) as doc:
        layout = m._source_layout(doc, 'ms')
        assert [s['number'] for s in layout[0]['starts']] == [1, 2]
        qp = [{'page': 1, 'starts': [{'number': 1}], 'text': '(Total 10 marks)'}]
        q = {'number': 1, 'question_regions': [region('qp', 1)], 'scheme_regions': [region('ms', 1)]}
        with pytest.raises(ValueError, match='shared-page'):
            m._whole_question_scope(q, {'qp': qp, 'ms': layout}, {})


def test_formula_digits_outside_question_column_do_not_create_boundaries():
    with table_document([(100, '1(a)'), (150, '1(b)')]) as doc:
        doc[0].insert_text((250, 200), '2 = 2', fontsize=11)
        assert [s['number'] for s in module()._source_layout(doc, 'ms')[0]['starts']] == [1]


def test_unlabelled_formula_in_number_column_is_not_a_question_row():
    with table_document([(100, '1(a)'), (150, '1(b)')]) as doc:
        doc[0].insert_text((50, 200), '2 = 2', fontsize=11)
        assert [s['number'] for s in module()._source_layout(doc, 'ms')[0]['starts']] == [1]


def test_consecutive_rows_across_pages_keep_all_notes_but_nonconsecutive_reset_is_held():
    m = module()
    with pymupdf.open() as doc:
        for rows in [[(100, '1(a)')], [(100, '1(b)')], [(100, '2(a)')], [(100, '1(c)')]]:
            with table_document(rows) as page_doc:
                doc.insert_pdf(page_doc)
        layout = m._source_layout(doc, 'ms')
        assert [[s['number'] for s in p['starts']] for p in layout] == [[1], [], [2], [1]]
        assert 'Notes' in layout[1]['text'] and '1(b)' in layout[1]['text']
        qp = [{'page': 1, 'starts': [{'number': 1}], 'text': '(Total 10 marks)'}]
        q = {'number': 1, 'question_regions': [region('qp', 1)], 'scheme_regions': [region('ms', 1), region('ms', 2)]}
        with pytest.raises(ValueError, match='unique original scheme'):
            m._whole_question_scope(q, {'qp': qp, 'ms': layout}, {})


def test_prose_before_bare_total_in_marks_column_is_not_dropped():
    with table_document([(100, '1(a)')]) as doc:
        doc[0].insert_text((425, 400), 'award', fontsize=11)
        layout = {'ms': module()._source_layout(doc, 'ms')}
        with pytest.raises(ValueError, match='unique independent ms'):
            module()._located_whole_total({'number': 1, 'scheme_regions': [region('ms', 1)]}, layout, {}, 'ms')


def test_cross_page_continuation_sharing_next_question_stays_held():
    m = module()
    with pymupdf.open() as doc:
        for rows in [[(100, '1(a)')], [(100, '1(b)'), (200, '2(a)')]]:
            with table_document(rows) as part:
                doc.insert_pdf(part)
        layout = m._source_layout(doc, 'ms')
        qp = [{'page': 1, 'starts': [{'number': 1}], 'text': '(Total 10 marks)'}]
        q = {'number': 1, 'question_regions': [region('qp', 1)], 'scheme_regions': [region('ms', 1)]}
        with pytest.raises(ValueError, match='unique original scheme|shared-page'):
            m._whole_question_scope(q, {'qp': qp, 'ms': layout}, {})


def test_actual_d1_bare_marks_literal_is_located_before_notes(originals):
    m = module()
    with open_original(originals, D1_MS) as doc:
        layout = m._source_layout(doc, 'ms')
        total = m._located_whole_total({'number': 8, 'scheme_regions': [region('ms', 17), region('ms', 18), region('ms', 19)]},
                                       {'ms': layout}, {}, 'ms')
        assert total['label'] == '10 marks' and total['value'] == 10
        assert total['region']['page'] == 17
        assert _whole_total(total['label'], 'ms', 8) == 10
        text = m._region_text(doc, [total['region']])
        assert text == total['label']
    with open_original(originals, D1_QP) as doc:
        layout = m._source_layout(doc, 'qp')
        assert len([s for p in layout for s in p['starts'] if s['number'] == 8]) == 2
        with pytest.raises(ValueError, match='unique original question start'):
            m._whole_question_scope({'number': 8}, {'qp': layout, 'ms': []}, {})


@pytest.mark.parametrize('total,header,notes_y', [
    ('award 10 marks', True, 500), ('10 marks available', True, 500),
    ('(10)', True, 500), ('[10 marks]', True, 500),
    ('10 marks', False, 500), ('10 marks', True, 350),
])
def test_bare_total_prose_allocations_or_notes_are_held(total, header, notes_y):
    with table_document([(100, '1(a)')], total=total, header=header, notes_y=notes_y) as doc:
        layout = module()._source_layout(doc, 'ms')
        with pytest.raises(ValueError, match='unique independent ms'):
            module()._located_whole_total({'number': 1, 'scheme_regions': [region('ms', 1)]}, {'ms': layout}, {}, 'ms')


def test_competing_bare_maxima_and_independent_qp_disagreement_are_held():
    m = module()
    with table_document([(100, '1(a)')]) as doc:
        doc[0].insert_text((500, 430), '10 marks', fontsize=11)
        layout = {'ms': m._source_layout(doc, 'ms')}
        with pytest.raises(ValueError, match='unique independent ms'):
            m._located_whole_total({'number': 1, 'scheme_regions': [region('ms', 1)]}, layout, {}, 'ms')
    with table_document([(100, '1(a)')]) as ms, pymupdf.open() as qp:
        qp.new_page().insert_text((40, 100), '(Total 9 marks)', fontsize=11)
        layout = {'ms': m._source_layout(ms, 'ms'), 'qp': m._source_layout(qp, 'qp')}
        q = {'number': 1, 'scheme_regions': [region('ms', 1)], 'question_regions': [region('qp', 1)]}
        with pytest.raises(ValueError, match='maxima differ'):
            m._whole_assessment(q, layout, {})


def test_neutral_bare_total_is_ms_only_and_keeps_literal_grammar():
    assert _whole_total('10 marks', 'ms', 1) == 10
    assert _whole_total('10', 'ms', 1) == 10
    for label, role in [('award 10 marks', 'ms'), ('10 marks available', 'ms'), ('10 marks', 'qp'), ('10', 'qp')]:
        with pytest.raises(ValueError):
            _whole_total(label, role, 1)


@pytest.mark.parametrize('fault', [None, 'wrong-sum', 'scheme-column', 'earlier-cell', 'multiple', 'notes', 'prose'])
def test_integer_total_requires_final_unique_marks_cell_and_independent_allocations(fault):
    with table_document([(100, '1(a)')], total=None) as doc:
        doc[0].insert_text((550, 200), '(3)', fontsize=11)
        doc[0].insert_text((550, 300), '(6)' if fault == 'wrong-sum' else '(7)', fontsize=11)
        x = 250 if fault == 'scheme-column' else 550
        y = 250 if fault == 'earlier-cell' else 550 if fault == 'notes' else 400
        doc[0].insert_text((x, y), '10', fontsize=11)
        if fault == 'multiple': doc[0].insert_text((550, 430), '10', fontsize=11)
        if fault == 'prose': doc[0].insert_text((500, y), 'award', fontsize=11)
        layout = {'ms': module()._source_layout(doc, 'ms')}
        q = {'number': 1, 'scheme_regions': [region('ms', 1)]}
        if fault is None:
            total = module()._located_whole_total(q, layout, {}, 'ms')
            assert total['label'] == '10' and total['value'] == 10
        else:
            with pytest.raises(ValueError, match='unique independent ms'):
                module()._located_whole_total(q, layout, {}, 'ms')


def test_actual_m1_q1_integer_maximum_prepare_replay_preserves_alternative_and_notes(originals, tmp_path):
    m = module()
    public = [{'role': 'qp', 'page': p, 'box': [0, 0, 1, 1]} for p in (2, 3)]
    private = [{'role': 'ms', 'page': 7, 'box': [0, 0, 1, 1]}]
    request = {'course': 'M1', 'sources': {
        role: {'asset_id': asset, 'sha256': originals.record(asset)['sha256'], 'inspection_pages': list(range(1, count + 1))}
        for role, asset, count in [('qp', M1_QP, 24), ('ms', M1_MS, 15)]},
        'questions': [{'number': 1, 'assessment_mode': 'whole_official_rubric_v1',
            'question_regions': public, 'scheme_regions': private,
            'parts': [{'part': '', 'label': '', 'question_media_regions': public, 'scheme_media_regions': private}]}]}
    path = tmp_path / 'request.json'
    path.write_text(json.dumps(request))
    out = tmp_path / 'package'
    d = m.prepare_native(path, out, originals, 'a' * 64)
    assert m.verify_native_package(out, originals, 'a' * 64) == d
    q = d['questions'][0]
    assert q['whole_assessment']['totals']['ms']['label'] == '6'
    assert q['whole_assessment']['max_marks'] == 6
    assert q['witness']['scheme_boundary'] == {'kind': 'next_question', 'page': 8, 'numbers': [2]}
    with open_original(originals, M1_MS) as doc:
        assert 'OR:' in m._region_text(doc, q['scheme_regions']) and 'Notes' in m._region_text(doc, q['scheme_regions'])
        media = q['parts'][0]['scheme_media'][0]
        assert (out / media).read_bytes() == doc[6].get_pixmap(dpi=144, alpha=False).tobytes('png')


@pytest.mark.parametrize('fault', [None, 'wrong-alternative', 'new-part-after-or', 'scheme-codes', 'no-notes'])
def test_integer_code_sum_excludes_only_an_equal_mark_final_part_alternative(fault):
    with table_document([(100, '1(i)'), (200, '(ii)')], total=None,
                        notes_y=None if fault == 'no-notes' else 500) as doc:
        x = 250 if fault == 'scheme-codes' else 500
        for y, label in [(100, 'M1 A1'), (150, 'A1'), (200, 'M1 A1'), (250, 'A1'),
                         (300, 'M1 A1'), (350, 'A2' if fault == 'wrong-alternative' else 'A1')]:
            doc[0].insert_text((x, y), label, fontsize=11)
        doc[0].insert_text((250, 300), 'OR:', fontsize=11)
        doc[0].insert_text((550, 400), '6', fontsize=11)
        if fault == 'new-part-after-or': doc[0].insert_text((50, 350), '(iii)', fontsize=11)
        layout = {'ms': module()._source_layout(doc, 'ms')}
        q = {'number': 1, 'scheme_regions': [region('ms', 1)]}
        if fault is None:
            assert module()._located_whole_total(q, layout, {}, 'ms')['label'] == '6'
        else:
            with pytest.raises(ValueError, match='unique independent ms'):
                module()._located_whole_total(q, layout, {}, 'ms')


@pytest.mark.parametrize('alternative', ['OR:', 'or:', 'Or:', 'oR:'])
@pytest.mark.parametrize('total', [6, 9])
def test_integer_code_alternatives_have_case_independent_mark_totals(alternative, total):
    with table_document([(100, '1(i)'), (200, '(ii)')], total=None) as doc:
        for y, label in [(100, 'M1 A1'), (150, 'A1'), (200, 'M1 A1'),
                         (250, 'A1'), (300, 'M1 A1'), (350, 'A1')]:
            doc[0].insert_text((500, y), label, fontsize=11)
        doc[0].insert_text((250, 300), alternative, fontsize=11)
        doc[0].insert_text((550, 400), str(total), fontsize=11)
        layout = {'ms': module()._source_layout(doc, 'ms')}
        q = {'number': 1, 'scheme_regions': [region('ms', 1)]}
        if total == 6:
            assert module()._located_whole_total(q, layout, {}, 'ms')['label'] == '6'
        else:
            with pytest.raises(ValueError, match='unique independent ms'):
                module()._located_whole_total(q, layout, {}, 'ms')


def test_integer_total_does_not_add_or_alternative_allocations():
    with table_document([(100, '1(a)')], total=None) as doc:
        for y in (200, 300): doc[0].insert_text((550, y), '(3)', fontsize=11)
        doc[0].insert_text((250, 250), 'OR:', fontsize=11)
        doc[0].insert_text((550, 400), '6', fontsize=11)
        layout = {'ms': module()._source_layout(doc, 'ms')}
        with pytest.raises(ValueError, match='unique independent ms'):
            module()._located_whole_total({'number': 1, 'scheme_regions': [region('ms', 1)]}, layout, {}, 'ms')


@pytest.mark.parametrize('annotation', ['A1ft', 'A2ft', 'DepM1', 'dM1', 'DM1', 'M1A1', 'SC1'])
@pytest.mark.parametrize('y', [300, 430])
def test_integer_total_cannot_ignore_scoring_variants_before_or_after_total(annotation, y):
    with table_document([(100, '1(a)')], total=None) as doc:
        doc[0].insert_text((500, 200), 'M1 A1', fontsize=11)
        doc[0].insert_text((550, 400), '2', fontsize=11)
        doc[0].insert_text((500, y), annotation, fontsize=11)
        layout = {'ms': module()._source_layout(doc, 'ms')}
        with pytest.raises(ValueError, match='unique independent ms'):
            module()._located_whole_total({'number': 1, 'scheme_regions': [region('ms', 1)]}, layout, {}, 'ms')


def test_actual_p3_bare_total_prepare_replay_and_complete_private_pixels(originals, tmp_path):
    m = module()
    public = [{'role': 'qp', 'page': p, 'box': [0, 0, 1, 1]} for p in (2, 3)]
    private = [{'role': 'ms', 'page': p, 'box': [0, 0, 1, 1]} for p in (4, 5)]
    request = {'course': 'P3', 'sources': {
        role: {'asset_id': asset, 'sha256': originals.record(asset)['sha256'], 'inspection_pages': list(range(1, count + 1))}
        for role, asset, count in [('qp', P3_QP, 32), ('ms', P3_MS, 19)]},
        'questions': [{'number': 1, 'assessment_mode': 'whole_official_rubric_v1',
            'question_regions': public, 'scheme_regions': private,
            'parts': [{'part': '', 'label': '', 'question_media_regions': public, 'scheme_media_regions': private}]}]}
    path = tmp_path / 'request.json'
    path.write_text(json.dumps(request))
    out = tmp_path / 'package'
    descriptor = m.prepare_native(path, out, originals, 'a' * 64)
    assert m.verify_native_package(out, originals, 'a' * 64) == descriptor
    q = descriptor['questions'][0]
    assert q['whole_assessment']['max_marks'] == 6
    assert q['whole_assessment']['totals']['ms']['label'] == '6 marks'
    assert q['witness']['scheme_boundary'] == {'kind': 'next_question', 'page': 6, 'numbers': [2]}
    assert [r['page'] for r in q['scheme_regions']] == [4, 5]
    for name, media in descriptor['media'].items():
        r = media['region']
        with open_original(originals, P3_QP if r['role'] == 'qp' else P3_MS) as doc:
            expected = doc[r['page'] - 1].get_pixmap(dpi=144, alpha=False).tobytes('png')
        assert (out / name).read_bytes() == expected
        assert media['sha256'] == hashlib.sha256(expected).hexdigest()
        assert media['visibility'] == ('public' if r['role'] == 'qp' else 'private')
    # A changed truthful label cannot be sealed without replaying source proof.
    changed = json.loads((out / 'descriptor.json').read_bytes())
    changed['questions'][0]['whole_assessment']['totals']['ms']['label'] = '(6 marks)'
    (out / 'descriptor.json').write_bytes(m.canonical_bytes(changed))
    complete = json.loads((out / 'COMPLETE').read_bytes())
    complete['descriptor_sha256'] = hashlib.sha256((out / 'descriptor.json').read_bytes()).hexdigest()
    (out / 'COMPLETE').write_bytes(m.canonical_bytes(complete))
    with pytest.raises(ValueError, match='source_recomputation'):
        m.verify_native_package(out, originals, 'a' * 64)
