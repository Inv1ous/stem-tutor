"""CAIE topical boundaries from registered source bytes, never learner writes."""
import importlib.util
from pathlib import Path

import pymupdf
import pytest

from library_assets import read_bytes

MODULE = Path(__file__).parents[1] / 'extraction/topical_caie.py'
spec = importlib.util.spec_from_file_location('topical_caie', MODULE)
caie = importlib.util.module_from_spec(spec)
if MODULE.exists():
    spec.loader.exec_module(caie)

CHEM = 'asset:legacy-8c7c41f302848c45d5091223'
CHEM_P2 = 'asset:legacy-43053f0e1843745340b7fe99'
EXAMMATE = 'asset:legacy-834adedf9207d55193def412'
EXAMINENT = 'asset:legacy-94c51c9bcbba526ad8f64b38'
PHYSICS = 'asset:legacy-c25fd8121ed9d37c3c71e507'
PHYSICS_P2 = 'asset:legacy-1f0f39db8d26d2da3428f8c9'
CLASSIFIED = 'asset:legacy-8555cf22b06b8854ac2001a3'
LEGACY_MCQ = 'asset:legacy-bcf4e211611cd9eb29315f08'
LEGACY_THEORY = 'asset:legacy-4fec53921eee5cd5e8ed56da'
SCAN = 'asset:legacy-fc98465053396209207e8eff'


def analyse(asset, course, pages):
    assert hasattr(caie, 'find_anchors'), 'CAIE topical detector is missing'
    with pymupdf.open(stream=read_bytes(asset), filetype='pdf') as doc:
        # Inspect real fixture pages; no content is written or re-registered.
        doc.select(pages)
        return caie.find_anchors(doc, course)


def test_exammate_boundaries_use_geometry_not_pdf_text_stream_order():
    result = analyse(CHEM, '9701', [1])
    anchors = result['anchors']
    assert [a['label'] for a in anchors] == ['1', '2', '3', '4']
    assert [a['official_qid'] for a in anchors] == [f'9701_s20_11_q{q}' for q in [4, 8, 9, 11]]
    assert all(a['page'] == 1 and 0 < a['top'] < a['bottom'] < 1 and a['part'] == '' for a in anchors)
    assert anchors[0]['top'] == pytest.approx(63.23 / 841.97, abs=.003)


@pytest.mark.parametrize('asset,course,pages,expected', [
    (PHYSICS, '9702', [1, 5], ['9702_m20_12_q7', '9702_s20_12_q6', '9702_s20_13_q6']),
    (EXAMINENT, '9701', [8], ['9701_s22_13_q17', '9701_w22_12_q3', '9701_s21_13_q3', '9701_m20_12_q1']),
])
def test_papacambridge_codes_and_question_labels_join_on_same_baseline(asset, course, pages, expected):
    assert [a['official_qid'] for a in analyse(asset, course, pages)['anchors']] == expected


def test_written_parts_are_continuations_not_independent_anchors():
    result = analyse(CHEM_P2, '9701', [2, 3])
    assert [a['official_qid'] for a in result['anchors']] == ['9701_s20_22_q1']
    assert result['page_roles']['2'] == 'continuation'
    result = analyse(PHYSICS_P2, '9702', [1, 2, 3])
    assert len(result['anchors']) == 2


@pytest.mark.parametrize('asset,pages', [(CHEM_P2, [782]), (EXAMMATE, [696, 697]), (EXAMINENT, [715])])
def test_answers_with_question_headers_are_hard_stops(asset, pages):
    result = analyse(asset, '9701', pages)
    assert result['anchors'] == []
    assert set(result['page_roles'].values()) == {'answer'}


def test_classified_outer_q_label_preserves_unknown_official_identity():
    result = analyse(CLASSIFIED, '9702', [0, 1, 2, 3])
    assert [a['label'] for a in result['anchors']] == ['1', '2', '3']
    assert all(a['official_qid'] is None for a in result['anchors'])
    assert result['page_roles']['3'] == 'continuation'


def test_legacy_inline_codes_bind_to_outer_question_gutter():
    result = analyse(LEGACY_MCQ, '9702', [2, 3])
    assert [a['label'] for a in result['anchors']] == [str(n) for n in range(1, 9)]
    assert [a['official_qid'] for a in result['anchors'][:3]] == ['9702_s02_1_q1', '9702_s02_1_q2', '9702_s02_1_q3']
    assert result['anchors'][2]['top'] < .77  # header above the trailing inline code


def test_legacy_footer_does_not_fabricate_original_question_number():
    result = analyse(LEGACY_THEORY, '9702', [1, 2, 3])
    assert [a['label'] for a in result['anchors']] == ['2', '3']
    assert all(a['official_qid'] is None for a in result['anchors'])
    assert result['page_roles']['3'] == 'continuation'


def test_scan_requires_ocr_instead_of_silent_zero_questions():
    result = analyse(SCAN, '9701', [1])
    assert result['anchors'] == []
    assert any(i['reason'] == 'missing_text' for i in result['issues'])
    assert any(i['reason'] == 'no_anchors' for i in result['issues'])


def test_wrong_course_header_is_a_conflicting_identity_not_a_join():
    result = analyse(CHEM, '9702', [1])
    assert result['anchors'] == []
    assert any(i['reason'] == 'conflicting_identity' for i in result['issues'])


def test_unreadable_question_code_is_reported_and_never_guessed():
    assert hasattr(caie, 'find_anchors'), 'CAIE topical detector is missing'
    with pymupdf.open(stream=read_bytes(PHYSICS), filetype='pdf') as doc:
        doc.select([1])
        page = doc[0]
        word = next(w for w in page.get_text('words') if w[4] == '7')
        page.add_redact_annot(pymupdf.Rect(word[:4]))
        page.apply_redactions()
        result = caie.find_anchors(doc, '9702')
        assert all(a['official_qid'] is None for a in result['anchors'])
        assert any(i['reason'] == 'missing_question_identity' for i in result['issues'])


def test_missing_header_between_numbered_neighbors_is_reported():
    assert hasattr(caie, 'find_anchors'), 'CAIE topical detector is missing'
    with pymupdf.open(stream=read_bytes(CHEM), filetype='pdf') as doc:
        doc.select([1])
        page = doc[0]
        rect = page.search_for('2 - (9701/11_Summer_2020_Q8)')[0]
        page.add_redact_annot(rect)
        page.apply_redactions()
        result = caie.find_anchors(doc, '9701')
        assert any(i['reason'] == 'missing_question_anchor' for i in result['issues'])
