"""Real registered IAL topicals; fixture reads never modify the learner vault."""
from pathlib import Path
import sys

import pymupdf
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'extraction'))
from topical_ial import find_anchors
from library_assets import read_bytes

# Frozen all-source-progress.json sources, not native papers.
FIXTURES = [
    ('D1', 'asset:legacy-1de6b7ae2749bc1e77bf0a6a', 17),
    ('FP1', 'asset:legacy-47c5bea21dee5b7e1190a5d3', 12),
    ('FP1', 'asset:legacy-4609f79cfacc6b9bc3f8b2ee', 8),
    ('P1', 'asset:legacy-aa96697614289e49087e09ed', 43),
    ('P1', 'asset:legacy-45e7b5c6eb6a879329e41a7f', 29),
    ('P4', 'asset:legacy-8d5847e9a94495d3ce949b1d', 26),
    ('9701', 'asset:legacy-dcf1399e0786c90d354487bc', 13),
    ('9702', 'asset:legacy-6fe8410f18b2ae829e72651f', 21),
    ('D1', 'asset:legacy-64faffa759d06646615a7a30', 12),
    ('FP1', 'asset:legacy-3a56fa411fed2698062b4639', 12),
    ('M1', 'asset:legacy-aab926d3a5cae5bd5214eeb8', 28),
    ('P1', 'asset:legacy-5bc3d81eac5b76326e9a0048', 33),
    ('P2', 'asset:legacy-ca243f987e626dc702077eb4', 39),
    ('P3', 'asset:legacy-75060c09f483b580621fe388', 36),
    ('P4', 'asset:legacy-9dfdc6fba6802a635458445b', 32),
    ('S1', 'asset:legacy-45185cea2ab26f6af8d87e0c', 31),
    ('S2', 'asset:legacy-727651e9e8b8aeef9e7f3035', 45),
]


@pytest.mark.parametrize('course,source,total', FIXTURES)
def test_registered_question_compilations_segment_whole_questions(course, source, total):
    with pymupdf.open(stream=read_bytes(source), filetype='pdf') as doc:
        result = find_anchors(doc, course)
        assert result['profile'] == 'sme-topical-v1'
        assert len(result['anchors']) == total
        assert result['segmentation_status'] == 'qualified'
        assert all(a['official_qid'] is None and a['part'] == '' for a in result['anchors'])
        assert all(a['label'].isdigit() and a['page'] > 1 and 0 < a['top'] < a['bottom'] < .94
                   for a in result['anchors'])
        # Continuation pages must not become new whole questions.
        assert len({(a['page'], a['top']) for a in result['anchors']}) == total


def test_registered_lesson_notes_are_not_question_compilations():
    with pymupdf.open(stream=read_bytes('asset:legacy-8be8f8c4a08c55e673e514f1'), filetype='pdf') as doc:
        result = find_anchors(doc, 'P1')
        assert result['anchors'] == []
        assert result['segmentation_status'] == 'unsegmented'
        assert 'lesson_notes_not_question_compilation' in result['issues']


def test_unknown_pdf_and_course_are_explicitly_unsegmented():
    with pymupdf.open() as doc:
        doc.new_page().insert_text((70, 70), '1 This is a page fragment')
        result = find_anchors(doc, 'P1')
        assert result['anchors'] == []
        assert result['segmentation_status'] == 'unsegmented'
        assert find_anchors(doc, 'UNKNOWN')['profile'] == 'unsupported-ial'


@pytest.mark.parametrize('heading', ['Mark Scheme', 'Model Answers', 'Answers and Mark Scheme'])
def test_answer_pages_cannot_export_repeated_question_numbers(heading):
    # Synthetic invalid/mixed input exists only in memory.
    with pymupdf.open() as doc:
        doc.new_page(width=596, height=842).insert_text((70, 70), 'Exam Questions\n1 questions\nSave My Exams')
        p = doc.new_page(width=596, height=842)
        p.insert_text((82, 70), '1'); p.insert_text((96, 70), 'Solve this question.')
        p = doc.new_page(width=596, height=842)
        p.insert_text((70, 30), heading)
        p.insert_text((82, 70), '1'); p.insert_text((96, 70), 'Answer: 2')
        result = find_anchors(doc, 'P1')
        assert len(result['anchors']) == 1
        assert result['page_roles']['3'] == 'answer_section'
        assert 'answer_section_excluded' in result['issues']


def test_concatenated_mcq_and_structured_covers_are_separate_boundaries():
    with pymupdf.open(stream=read_bytes('asset:legacy-dcf1399e0786c90d354487bc'), filetype='pdf') as doc:
        result = find_anchors(doc, '9701')
        assert result['page_roles']['6'] == 'cover'
        assert [c['declared_question_count'] for c in result['compilations']] == [9, 4]
        assert {a['question_type'] for a in result['anchors']} == {'mcq', 'structured'}


def test_declared_total_mismatch_cannot_be_qualified():
    with pymupdf.open(stream=read_bytes('asset:legacy-5bc3d81eac5b76326e9a0048'), filetype='pdf') as doc:
        doc.select([0, 1])  # Invalid truncated input, in memory only.
        result = find_anchors(doc, 'P1')
        assert result['anchors']
        assert result['segmentation_status'] == 'requires_review'
        assert 'declared_question_count_mismatch' in result['issues']


def test_model_answer_cover_cannot_authorize_a_question_compilation():
    with pymupdf.open() as doc:
        doc.new_page().insert_text((70, 70), 'Exam Questions\n1 questions\nSave My Exams\nModel Answers')
        p = doc.new_page(width=596, height=842)
        p.insert_text((82, 70), '1'); p.insert_text((96, 70), 'The answer is 2')
        result = find_anchors(doc, 'P1')
        assert result['anchors'] == []
        assert result['segmentation_status'] == 'unsegmented'
        assert 'answer_material_not_questions' in result['issues']


@pytest.mark.parametrize('source,total', [
    ('asset:legacy-dcedf5c810fa0d62400411e4', 26),
    ('asset:legacy-1d76f8ac7abe517452e35b83', 17),
])
def test_chemistry_solution_label_does_not_start_answer_appendix(source, total):
    with pymupdf.open(stream=read_bytes(source), filetype='pdf') as doc:
        result = find_anchors(doc, '9701')
    assert 'answer_section_excluded' not in result['issues']
    assert result['segmentation_status'] == 'qualified'
    assert len(result['anchors']) == result['declared_question_count'] == total


def test_non_sme_contents_answer_link_does_not_prevent_caie_fallback():
    with pymupdf.open(stream=read_bytes('asset:legacy-834adedf9207d55193def412'), filetype='pdf') as doc:
        result = find_anchors(doc, '9701')
    assert not result['page_roles']
    assert 'unsupported_topical_layout' in result['issues']
