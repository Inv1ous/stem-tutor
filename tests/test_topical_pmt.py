"""PMT public preparation boundaries and privacy, using immutable registered sources."""
import importlib.util
from pathlib import Path

import pymupdf
import pytest
from library_assets import read_bytes, canonical_path, copy_to_vault

PATH = Path(__file__).parents[1] / 'extraction/topical_fastpath.py'
spec = importlib.util.spec_from_file_location('pmt_fastpath_tests', PATH)
fp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fp)
S3 = 'asset:asset-2974885b9b9ed953fc2e1d23'
SET1 = 'asset:asset-4b7b93f6b6a352d6e2cabe11'
SET2 = 'asset:asset-cee4971756368bdc66a7251d'
NOTES = 'asset:asset-888697559cd471381f829738'
MS = 'asset:asset-661435df599759219052682e'


def analyse(asset, course):
    return fp.analyse_source(read_bytes(asset), course, asset, source_path=canonical_path(asset))


def test_plain_s3_keeps_two_text_questions_and_explicit_raster_fragment():
    b = analyse(S3, 'S3')
    assert [q['label'] for q in b['questions']] == ['1', '2']
    assert b['review_pages'] and b['review_pages'][0]['region']['box'][1] > .48
    q = b['questions'][1]
    assert .29 < q['regions'][0]['box'][1] < .31
    assert .48 < q['regions'][0]['box'][3] < .50
    assert all(q['official_qid'] is None for q in b['questions'])
    assert b['status'] == 'needs_review' and b['declared_question_count'] is None


def test_set1_footer_is_not_scheme_but_reset_rubric_and_reports_are_private():
    b = analyse(SET1, 'D1')
    assert [q['label'] for q in b['questions']] == ['1', '2', '3', '4', '5', '6']
    assert [p['page'] for p in b['private_pages']] == list(range(4, 10))
    assert all(q['official_qid'] is None for q in b['questions'])
    assert b['status'] == 'needs_review'


def test_set2_preserves_original_starts_and_explicit_continuations_stops_formulae():
    b = analyse(SET2, 'FP2')
    assert [q['label'] for q in b['questions']] == ['7', '3', '1', '1', '2', '6']
    assert [r['page'] for r in b['questions'][0]['regions']][:2] == [2, 3]
    # The next page's header prefix is preserved by the shared region adapter.
    assert b['questions'][0]['regions'][-1]['box'][3] < .08
    assert [r['page'] for r in b['questions'][-1]['regions']] == [8, 9]
    assert not any(r['page'] >= 10 for q in b['questions'] for r in q['regions'])
    assert all(p['status'] == 'lesson_notes' for p in b['pages'][9:])


@pytest.mark.parametrize('asset,course,status', [(NOTES, 'S3', 'lesson_notes'), (MS, 'S3', 'private_answers')])
def test_registered_source_role_precedes_examples_and_raster_anchors(asset, course, status):
    b = analyse(asset, course)
    assert not b['questions']
    assert all(p['status'] == status for p in b['pages'])
    if asset == MS:
        assert b['status'] == 'private_answers_only'


def synthetic(pages, course='P1', path=None):
    with pymupdf.open() as d:
        for rows in pages:
            p = d.new_page(width=596, height=842)
            for x, y, text in rows:
                p.insert_text((x, y), text)
        return fp.analyse_source(d.tobytes(), course, 'synthetic', source_path=path or f'Library/Courses/{course}/Sources/Library/PMT/Edexcel/{course}/Edexcel-Set-1/topic.pdf')


HEADER = (300, 40, 'PhysicsAndMathsTutor.com')
START = (57, 100, '1. Solve this question.')
TOTAL = (300, 250, '(Total 4 marks)')


def test_mixed_question_scheme_page_is_wholly_private_and_stops_continuation():
    b = synthetic([[HEADER, START, (57, 400, '1. Mark Scheme'), (300, 440, 'M1 A1')],
                   [HEADER, (57, 100, 'Question 1 continued')]])
    assert not b['questions']
    assert b['private_pages'][0]['region']['box'] == [0, 0, 1, 1]
    assert any(i.get('reason') == 'mixed_question_answer_page' for i in b['issues'] if isinstance(i, dict))


def test_missing_and_unanchored_pages_break_continuation():
    b = synthetic([[HEADER, START, TOTAL], [], [HEADER, (100, 100, 'unrecognized material')],
                   [HEADER, (57, 100, 'Question 1 continued')]])
    assert [r['page'] for r in b['questions'][0]['regions']] == [1]
    assert len(b['review_pages']) == 3


@pytest.mark.parametrize('course', ['P1','P2','P3','P4','FP1','FP2','FP3','M1','D1','S1','S2','S3'])
def test_all_twelve_modules_have_provisional_preparation(course):
    b = synthetic([[HEADER, START, TOTAL]], course=course)
    assert len(b['questions']) == 1
    assert b['status'] == 'needs_review' and b['teaching_approved'] is False


def test_path_alone_does_not_establish_pmt_layout():
    b = synthetic([[(57, 100, '1. Something unrelated')]])
    assert not b['questions']


def test_requested_course_conflict_rejected_in_analysis_and_preparation(tmp_path):
    assert not analyse(S3, 'P1')['questions']
    vault = tmp_path / 'vault'
    vault.mkdir()
    copy_to_vault(canonical_path(S3), vault)
    with pytest.raises(ValueError, match='course'):
        fp.prepare(vault, S3, 'P1', tmp_path / 'bad')


def test_real_s3_bundle_verifies_partial_review_coverage_without_vault_writes(tmp_path):
    vault = tmp_path / 'vault'
    vault.mkdir()
    copy_to_vault(canonical_path(S3), vault)
    before = {p.relative_to(vault): p.read_bytes() for p in vault.rglob('*') if p.is_file()}
    output = tmp_path / 'bundle'
    b = fp.prepare(vault, S3, 'S3', output, dpi=72)
    assert fp.verify_bundle(output)['questions'] == 2
    assert b['metrics']['model_calls'] == 0
    assert before == {p.relative_to(vault): p.read_bytes() for p in vault.rglob('*') if p.is_file()}


def test_reset_inside_page_is_quarantined_even_without_machine_readable_rubric():
    b = synthetic([[HEADER, (57, 100, '3. Solve the last question.'), TOTAL,
                    (57, 400, '1. Answer text without readable marks')]])
    assert not b['questions']
    assert b['private_pages'][0]['region']['box'] == [0, 0, 1, 1]


def test_real_m1_module_header_is_not_a_method_mark():
    b = analyse('asset:asset-0ca41c32586f12e4786d8fe0', 'M1')
    assert b['questions']
    assert b['pages'][0]['status'] == 'question_regions'


def test_space_ms_suffix_companion_is_private_answers_only():
    b = analyse('asset:asset-41cb38c5f5d4b7dee37cdf0d', 'FP1')
    assert b['status'] == 'private_answers_only'
    assert not b['questions']
    assert len(b['private_pages']) == len(b['pages'])


def test_real_p1_formula_booklet_reference_preserves_genuine_question_pages():
    b = analyse('asset:asset-33eaeba3d5e3aea227ec991b', 'P1')
    for n in range(2, 6):
        page = b['pages'][n - 1]
        assert page['status'] != 'lesson_notes'
        assert (any(r['page'] == n for q in b['questions'] for r in q['regions'])
                or any(r['page'] == n for r in b['review_pages']))
    assert b['pages'][5]['status'] == 'private_answers'


def test_pmt_course_rejection_cannot_fall_through_to_caie_identity():
    rows = [[HEADER, (57, 100, '1 - (9701/12_Summer_2020_Q1)'),
             (90, 140, 'Find the correct answer.')]]
    path = 'Library/Courses/P1/Sources/Library/PMT/Edexcel/P1/Edexcel-Set-1/topic.pdf'
    b = synthetic(rows, course='9701', path=path)
    assert not b['questions']
    assert any(i.get('reason') == 'pmt_source_course_or_provenance_conflict'
               for i in b['issues'] if isinstance(i, dict))
    # The identical header remains supported for ordinary CAIE provenance.
    ordinary = synthetic(rows, course='9701', path='Library/Courses/9701/Sources/topic.pdf')
    assert ordinary['questions'][0]['official_qid'] == '9701_s20_12_q1'


@pytest.mark.parametrize('visibility', ['questions', 'context'])
def test_mixed_page_verifier_rejects_validly_rerendered_public_review_overlap(tmp_path, visibility):
    import json
    from PIL import Image

    vault = tmp_path / 'vault'
    vault.mkdir()
    source = copy_to_vault(canonical_path(S3), vault)
    output = tmp_path / 'bundle'
    fp.prepare(vault, S3, 'S3', output, dpi=72)
    assert fp.verify_bundle(output)['questions'] == 2
    b = json.loads((output / 'bundle.json').read_text())
    q = b['questions'][1] if visibility == 'questions' else b['questions'][0]
    field, media_field = ('regions', 'question_media') if visibility == 'questions' else ('context_regions', 'context_media')
    region = q[field][-1]
    region['box'][3] = 1
    name = q[media_field][-1]
    with pymupdf.open(source) as doc:
        pix = doc[region['page'] - 1].get_pixmap(dpi=72, alpha=False)
        with Image.frombytes('RGB', [pix.width, pix.height], pix.samples) as image:
            data = fp._png(image, region['box'])
    (output / name).write_bytes(data)
    b['media'][name].update(region=region, sha256=fp.sha(data), bytes=len(data))
    raw = json.dumps(b, indent=2).encode() + b'\n'
    (output / 'bundle.json').write_bytes(raw)
    (output / 'COMPLETE').write_text(fp.sha(raw) + '\n')
    with pytest.raises(ValueError, match='overlap|visibility conflict'):
        fp.verify_bundle(output)


def test_mixed_matching_continuation_scheme_is_private_and_reports_ambiguity():
    b = synthetic([[HEADER, START],
                   [HEADER, (57, 100, 'Question 1 continued'), (300, 400, 'M1 A1')]])
    assert [r['page'] for r in b['questions'][0]['regions']] == [1]
    assert b['private_pages'][0]['region']['box'] == [0, 0, 1, 1]
    assert any(i.get('reason') == 'mixed_question_answer_page' and i.get('page') == 2
               for i in b['issues'] if isinstance(i, dict))


@pytest.mark.parametrize('visibility', ['questions', 'context'])
def test_detector_review_fragment_cannot_be_reassigned_to_public_media(tmp_path, visibility):
    import json

    vault = tmp_path / 'vault'
    vault.mkdir()
    copy_to_vault(canonical_path(S3), vault)
    output = tmp_path / 'bundle'
    fp.prepare(vault, S3, 'S3', output, dpi=72)
    assert fp.verify_bundle(output)['questions'] == 2
    b = json.loads((output / 'bundle.json').read_text())
    fragment = b['review_pages'].pop()
    old_name = fragment['media'][0]
    new_name = visibility + '/' + old_name.split('/')[1]
    # Move identical bytes and source region: no gap, overlap or invalid digest
    # can hide whether verification enforces the retained detector's quarantine.
    (output / visibility).mkdir(exist_ok=True)
    data = (output / old_name).read_bytes()
    (output / new_name).write_bytes(data)
    item = b['media'].pop(old_name)
    item['visibility'] = visibility
    b['media'][new_name] = item
    q = b['questions'][1]
    region_field, media_field = (('regions', 'question_media') if visibility == 'questions'
                                 else ('context_regions', 'context_media'))
    q[region_field].append(fragment['region'])
    q[media_field].append(new_name)
    assert item['sha256'] == fp.sha(data)
    assert b['detector']['anchors'][-1]['candidate_unit'] == 'review_fragment'
    raw = json.dumps(b, indent=2).encode() + b'\n'
    (output / 'bundle.json').write_bytes(raw)
    (output / 'COMPLETE').write_text(fp.sha(raw) + '\n')
    with pytest.raises(ValueError, match='detector.*review fragment'):
        fp.verify_bundle(output)
