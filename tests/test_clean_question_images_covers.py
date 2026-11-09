"""Exam cover / instruction pages are detected from OCR text and never served as question images."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "build"))

import clean_question_images as c  # noqa: E402
import migrate_source_questions as m  # noqa: E402

COVER = """PMT
Please check the examination details below before entering your candidate information
Candidate surname
Other names
Centre Number
Candidate Number
Paper Reference WME01/01
You must have:
Total Marks
Instructions
Information
Advice"""
BOOKLET = """PhysicsAndMathsTutor.com
Edexcel GCE
Calculators may NOT be used for these questions.
Information for C2ndidates
There are 16 questions in this test.
Advice to Candidates"""
QUESTION = "PMT\nQuestion 7 continued\nFind the value of x.\n(Total for Question 7 is 9 marks)\nTurn over"


def test_cover_and_booklet_pages_are_detected_and_question_pages_are_not():
    assert c.is_cover_text(COVER) and c.is_cover_text(BOOKLET)
    assert not c.is_cover_text(QUESTION) and not c.is_cover_text("")
    assert not c.is_cover_text("Instructions\nUse black ink.")  # one phrase is not enough


def _sidecar(*refs):
    return {'images': {r: {'decision': 'remove', 'reason': 'exam_cover_page', 'cleaned': None, 'borderline': False}
                       if r.startswith('cover') else {'decision': 'keep', 'reason': 'x', 'cleaned': None, 'borderline': False}
                       for r in refs}}


def test_cover_is_dropped_but_other_images_stay():
    item = {'question_media': ['cover.png', 'q.png'], 'context_media': []}
    out = c.resolve(_sidecar('cover.png', 'q.png'), item)
    assert [r['original'] for r in out['question_media']] == ['q.png'] and out['cover_dropped'] == ['cover.png']


def test_item_whose_only_image_is_a_cover_is_held_not_imageless():
    item = {'id': 'M1_x', 'course': 'M1', 'question_media': ['cover.png'], 'context_media': [], 'question_text': 'stem'}
    tag = {'status': 'mapped', 'reason': None, 'kcs_required': ['M1-1.1.1'], 'parts': [], 'method': 'm',
           'confidence': 1, 'subtopics': ['M1-1.1']}
    row = m.build_item(item, tag, _sidecar('cover.png'), False)
    assert row['held'] and row['held_reason'] == 'only_image_was_exam_cover_page'
    assert row['media']['question_media'] == [] and row['media']['cover_dropped'] == ['cover.png']
