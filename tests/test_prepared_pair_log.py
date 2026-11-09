"""Joint native identity proof; real originals stay in disposable Library copies."""
import copy
import hashlib
import json
from pathlib import Path
import sys

import pymupdf
import pytest
from library_assets import canonical_path, copy_to_vault, read_bytes
from tutorlib.asset_library import AssetLibrary
from tutorlib.prepared_evidence import WHOLE_ASSESSMENT, source_identity

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'extraction'))
import prepared_scope as prepared

SPEC = 'Library/Shared/Sources/Specifications/ial-maths-spec.pdf'
REAL = {
    'FP1': ('legacy-a54a0eb442875751c3a8818b', 'legacy-c40da01063e22fd1d4d50237', 'P66060A'),
    'M1': ('legacy-2dc7143e4ba4bf7a9924c086', 'legacy-dba46400fb415f862b50bf90', 'P65266A'),
}
EXAM = {'unit': 'WFM01', 'component': '01', 'session': '2021-06'}
QP = 'Pearson Edexcel International Advanced Level\nPaper reference WFM01/01\n*P66060A0132*\nP66060A\nCandidates may use a calculator.'
MS = 'Pearson Edexcel International Advanced Level\nMark Scheme (Results)\nSummer 2021\nWFM01/01'
FRONT = ('Edexcel and BTEC Qualifications\nPearson: helping people progress, everywhere\n'
         'Summer 2021\nQuestion Paper Log Number P66060A\n'
         'Publications Code WFM01_01_2106_MS\n'
         'All the material in this publication is copyright\n© Pearson Education Ltd 2021')


def document(*texts, unicode_font=False):
    doc = pymupdf.open()
    for text in texts:
        page = doc.new_page()
        fontname = 'helv'
        if unicode_font:
            if '\uff0f' in text:
                fontname = 'china-s'  # Built-in CJK font retains the fullwidth solidus.
            else:
                fontname = 'date-test'
                page.insert_font(fontname=fontname, fontbuffer=read_bytes('Library/Shared/Fonts/JuliaMono-Regular.ttf'))
        assert page.insert_textbox(pymupdf.Rect(30, 30, 560, 800), text, fontsize=11, fontname=fontname) > 0
    return doc


def pair(qp=QP, ms=MS, front=FRONT, *, exam=None, ms_exam=None, ms_pages=None):
    with document(qp) as q, document(ms, front) as m:
        return prepared._paired_covers(q, m, exam or EXAM, ms_exam or exam or EXAM, ms_pages=ms_pages)


def real_pair(tmp_path, course):
    vault = tmp_path / 'vault'; vault.mkdir()
    paths = {role: copy_to_vault(canonical_path('asset:' + ref), vault)
             for role, ref in zip(('qp', 'ms'), REAL[course][:2])}
    copy_to_vault(SPEC, vault)
    lib = AssetLibrary(vault)
    refs = {role: path.relative_to(vault).as_posix() for role, path in paths.items()}
    ids = {role: 'asset:' + next(key for key, record in lib.records().items() if record['path'] == ref)
           for role, ref in refs.items()}
    exams = {role: source_identity(ref, role, course) for role, ref in refs.items()}
    return lib, paths, ids, exams


@pytest.mark.parametrize('course', ['FP1', 'M1'])
def test_real_undated_pair_requires_exact_publisher_log_and_records_actual_pages(tmp_path, course):
    lib, paths, _, exams = real_pair(tmp_path, course)
    with pymupdf.open(paths['qp']) as qp, pymupdf.open(paths['ms']) as ms:
        with pytest.raises(prepared.PendingEvidence, match='pending_cover_session'):
            prepared._cover(qp, exams['qp'], 'qp')
        result = prepared._paired_covers(qp, ms, exams['qp'], exams['ms'])
        witness = result['qp']['joint_series_evidence']
        assert witness['question_paper_log_number'] == REAL[course][2]
        assert witness['qp_date_status'] == 'no_printed_date'
        assert witness['qp']['role'] == 'qp' and witness['qp']['page'] == 1
        assert witness['ms_cover']['role'] == 'ms' and witness['ms_cover']['page'] == 1
        assert witness['ms_log']['role'] == 'ms' and witness['ms_log']['page'] == 2
        for key, doc in [('qp', qp), ('ms_cover', ms), ('ms_log', ms)]:
            text = ' '.join(doc[witness[key]['page'] - 1].get_text().split())
            assert witness[key]['text_sha256'] == hashlib.sha256(text.encode()).hexdigest()
        assert result['ms'] == prepared._cover(ms, exams['ms'], 'ms')
        assert 'date' not in result['qp']


def test_compute_defers_qp_cover_until_ms_loaded_and_budgets_log_page(tmp_path):
    lib, _, ids, _ = real_pair(tmp_path, 'FP1')
    public = [{'role': 'qp', 'page': p, 'box': [0, 0, 1, 1]} for p in range(2, 6)]
    private = [{'role': 'ms', 'page': 9, 'box': [0, 0, 1, 1]}]
    request = {'course': 'FP1', 'sources': {
        role: {'asset_id': ids[role], 'sha256': lib.record(ids[role])['sha256'], 'inspection_pages': pages}
        for role, pages in [('qp', [1, 2, 3, 4, 5]), ('ms', [1, 9, 10])]}, 'questions': [
            {'number': 1, 'assessment_mode': WHOLE_ASSESSMENT, 'question_regions': public,
             'scheme_regions': private, 'parts': [{'part': '', 'label': '',
                'question_media_regions': public, 'scheme_media_regions': private}]}]}
    path = tmp_path / 'request.json'; path.write_text(json.dumps(request))
    output = tmp_path / 'package'
    descriptor = prepared.prepare_native(path, output, lib, 'a' * 64)
    assert descriptor == prepared.verify_native_package(output, lib, 'a' * 64)
    assert descriptor['sources']['ms']['inspection_pages'] == [1, 2, 9, 10]
    assert [p['page'] for p in descriptor['sources']['ms']['page_geometry']] == [1, 2, 9, 10]
    assert {'asset_id': ids['ms'], 'page': 2} in descriptor['required_asset_pages']
    assert descriptor['questions'][0]['whole_assessment']['max_marks'] == 10
    reversed_request = copy.deepcopy(request)
    reversed_request['sources'] = dict(reversed(list(request['sources'].items())))
    other, _, _ = prepared._compute(reversed_request, lib, 'a' * 64)
    assert other == descriptor


@pytest.mark.parametrize('fault', ['wrong', 'missing', 'generic', 'ambiguous', 'malformed', 'duplicate-conflict'])
def test_explicit_log_field_cannot_be_replaced_by_incidental_or_ambiguous_ids(fault):
    changes = {
        'wrong': FRONT.replace('Number P66060A', 'Number P99999A'),
        'missing': FRONT.replace('Question Paper Log Number P66060A', ''),
        'generic': FRONT.replace('Question Paper Log Number', 'Publication paper code'),
        'ambiguous': FRONT.replace('Number P66060A', 'Number P66060A P99999A'),
        'malformed': FRONT.replace('Number P66060A', 'Number P66060A9999'),
        'duplicate-conflict': FRONT + '\nQuestion Paper Log Number P99999A',
    }
    with pytest.raises(ValueError, match='log'):
        pair(front=changes[fault])


@pytest.mark.parametrize('qp', [QP.replace('P66060A', ''), QP + '\nP99999A', QP + '\n*P99999A0132*'])
def test_qp_needs_unique_native_paper_id(qp):
    with pytest.raises(ValueError, match='paper_id'):
        pair(qp=qp)


@pytest.mark.parametrize('date', ['June 2020', 'October 2021', 'May 2020', '11 May', 'JAN 2021', '2021-06-01', '01/06/2021', '11 may', '01/06'])
def test_any_printed_qp_month_or_date_prevents_missing_date_fallback(date):
    with pytest.raises(ValueError, match='cover_session|printed_date'):
        pair(qp=QP + '\n' + date)


@pytest.mark.parametrize('role,fault', [
    ('qp', 'issuer'), ('qp', 'unit'), ('qp', 'component'), ('qp', 'role'),
    ('ms', 'issuer'), ('ms', 'unit'), ('ms', 'component'), ('ms', 'role'), ('ms', 'season'), ('ms', 'year'),
])
def test_log_match_does_not_replace_independent_source_role_identity_or_session(role, fault):
    text = QP if role == 'qp' else MS
    text = {'issuer': text.replace('Pearson Edexcel', 'Another Board'),
            'unit': text.replace('WFM01', 'WME01'), 'component': text.replace('/01', '/02'),
            'role': text.replace('Paper reference', 'Mark Scheme').replace('Mark Scheme (Results)', 'Paper reference'),
            'season': text.replace('Summer', 'October'), 'year': text.replace('2021', '2020')}[fault]
    with pytest.raises(ValueError):
        pair(**{role: text})


@pytest.mark.parametrize('front', [
    FRONT.replace('Pearson Education Ltd', 'Other Publisher'),
    FRONT.replace('Summer 2021', 'October 2021'),
    FRONT.replace('WFM01_01_2106_MS', 'WME01_01_2106_MS'),
    FRONT.replace('WFM01_01_2106_MS', 'WFM01_02_2106_MS'),
    FRONT.replace('WFM01_01_2106_MS', 'WFM01_01_2110_MS'),
    FRONT.replace('Publications Code WFM01_01_2106_MS', ''),
    FRONT + '\nNovember 2021',
    FRONT + '\nWME01/01',
])
def test_page_two_requires_authenticated_publisher_frontmatter(front):
    with pytest.raises(ValueError, match='frontmatter'):
        pair(front=front)


def test_pair_exams_must_match_even_with_exact_log_id():
    with pytest.raises(ValueError, match='source_pair'):
        pair(ms_exam={**EXAM, 'session': '2021-10'})


def test_cover_log_is_preferred_and_dated_evidence_is_unchanged():
    result = pair(ms=MS + '\nQuestion Paper Log Number P66060A', front='unrelated page')
    assert result['qp']['joint_series_evidence']['ms_log']['page'] == 1
    with document(QP + '\nJune 2021') as qp, document(MS) as ms:
        assert prepared._paired_covers(qp, ms, EXAM, EXAM) == {
            'qp': prepared._cover(qp, EXAM, 'qp'), 'ms': prepared._cover(ms, EXAM, 'ms')}


def test_log_on_unrelated_later_page_cannot_authenticate_an_undated_qp():
    with document(QP) as qp, document(MS, 'Unrelated', FRONT) as ms:
        with pytest.raises(ValueError, match='log'):
            prepared._paired_covers(qp, ms, EXAM, EXAM)


def test_all_native_id_forms_have_the_same_exact_log_identity():
    for qp in [QP.replace('P66060A\nCandidates', 'Candidates'), QP.replace('*P66060A0132*\n', '')]:
        assert pair(qp=qp)['qp']['joint_series_evidence']['question_paper_log_number'] == 'P66060A'


def test_optional_witness_page_restriction_holds_uninspected_frontmatter():
    with pytest.raises(ValueError, match='log'):
        pair(ms_pages=[1])
    assert pair(ms_pages=[1, 2])['qp']['joint_series_evidence']['ms_log']['page'] == 2


@pytest.mark.parametrize('course,unit,season,printed_month', [
    ('FP1', 'WFM01', 'Jun', 'May'), ('M1', 'WME01', 'Jun', 'May'),
    ('S1', 'WST01', 'Jun', 'June'), ('P1', 'WMA11', 'Oct', 'May'),
])
def test_actual_2020_printed_dates_are_not_repaired_by_october_ms(tmp_path, course, unit, season, printed_month):
    vault = tmp_path / 'vault'; vault.mkdir()
    refs = {role: f'Library/Courses/{course}/Sources/PastPapers/ial/{unit}/{unit}_2020_{season}_{role}.pdf'
            for role in ('qp', 'ms')}
    paths = {role: copy_to_vault(ref, vault) for role, ref in refs.items()}
    with pymupdf.open(paths['qp']) as qp, pymupdf.open(paths['ms']) as ms:
        assert printed_month + ' 2020' in ' '.join(qp[0].get_text().split())
        assert 'October 2020' in ' '.join(ms[0].get_text().split())
        with pytest.raises(ValueError, match='cover_session'):
            prepared._paired_covers(qp, ms, source_identity(refs['qp'], 'qp', course),
                                    source_identity(refs['ms'], 'ms', course))


@pytest.mark.parametrize('date', [
    '01 / 10 / 2020', '2020 - 10 - 01', '01 – 10 – 2020', 'Sept 2020',
    '1/10', '1 / 10', '1-10', '1 – 10', '1.10', '1 . 10',
    '2020 / 10 / 1', '1 / 10 / 20', '2020−10−1', '1 — 10 — 2020',
    '1 ‐ 10 ‐ 2020', '1 ‑ 10 ‑ 2020', '1 ‒ 10 ‒ 2020',
    '1 ／ 10 ／ 2020', '1 ⁄ 10 ⁄ 2020', '1 ∕ 10 ∕ 2020',
    '01\n/\n10\n/\n2020', 'Sept. 2020', 'SEPT', 'Sept2020',
    'Jan. 2020', 'JAN2020', 'Oct-20', 'Monday 1 / 10', 'Mon 1 / 10',
    '1/1/1', '1/1/1/', 'J:1/1/', '9.8',
])
def test_missing_date_guard_rejects_whole_spaced_unicode_and_abbreviated_date_class(date):
    # Use a Unicode-capable font and check the actual PDF extraction so a
    # replacement glyph cannot make Unicode date regressions pass vacuously.
    with document(QP + '\n' + date, unicode_font=True) as qp, document(MS, FRONT) as ms:
        native = ' '.join(qp[0].get_text().split())
        assert ' '.join(date.split()) in native
        with pytest.raises(ValueError, match='printed_date'):
            prepared._paired_covers(qp, ms, EXAM, EXAM)


@pytest.mark.parametrize('revision', ['1/1/1/', '1/1/1/1', 'E:1/1/1/', 'J:1/1/'])
def test_known_publisher_printer_revisions_require_exact_native_copyright_context(revision):
    publisher = 'P66060A\n©2021 Pearson Education Ltd.\n'
    result = pair(qp=QP + '\n' + publisher + revision)
    assert result['qp']['joint_series_evidence']['qp_date_status'] == 'no_printed_date'
    for altered in [publisher.replace('Pearson', 'Another'), publisher.replace('P66060A', 'not-a-paper-id')]:
        with pytest.raises(ValueError, match='printed_date'):
            pair(qp=QP + '\n' + altered + revision)


@pytest.mark.parametrize('date', ['1/10', '1 / 1 / 2020', '1/1/1', '1/1/1/2020/', 'J:1/10/', '1/1/1/ October2020'])
def test_copyright_location_does_not_turn_dates_into_printer_revisions(date):
    with pytest.raises(ValueError, match='printed_date'):
        pair(qp=QP + '\nP66060A\n©2021 Pearson Education Ltd.\n' + date)


def test_unambiguous_m1_physical_constant_does_not_hide_a_nearby_date():
    scalar = 'Whenever a numerical value of g is required, take g = 9.8 m s–2'
    with document(QP + '\n' + scalar, unicode_font=True) as qp, document(MS, FRONT) as ms:
        assert prepared._paired_covers(qp, ms, EXAM, EXAM)['qp']['joint_series_evidence']['qp_date_status'] == 'no_printed_date'
    with document(QP + '\n' + scalar + '\n1/10', unicode_font=True) as qp, document(MS, FRONT) as ms:
        with pytest.raises(ValueError, match='printed_date'):
            prepared._paired_covers(qp, ms, EXAM, EXAM)
