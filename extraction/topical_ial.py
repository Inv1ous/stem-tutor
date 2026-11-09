"""Conservative whole-question starts in registered Save My Exams topicals.

This module proposes preparation boundaries only. Printed topical numbers are not
exam identities, and notes/worked solutions never become public questions here.
"""
from __future__ import annotations

import re

COURSES = {'P1', 'P2', 'P3', 'P4', 'FP1', 'M1', 'D1', 'S1', 'S2', '9701', '9702'}
PROFILE = 'sme-topical-v1'
ANSWER_HEADING = re.compile(r'^(?:mark\s+scheme|(?:model\s+)?answers?(?:\s+and\s+(?:solutions|mark\s+scheme))?|(?:worked\s+)?solutions)\s*$', re.I)
SECTION = re.compile(r'^(Easy|Medium|Hard|Very Hard)\s+Questions$', re.I)


def find_anchors(doc, course: str) -> dict:
    """Return normalized printed starts, or explicit unsegmented disposition.

    Qualification requires the profiled cover, exact declared total and ordered
    numbering within each difficulty section. Unknown official IDs stay None.
    ``page_roles`` uses 1-based string keys; answer sections are hard boundaries.
    """
    result = {'profile': PROFILE if course in COURSES else 'unsupported-ial',
              'anchors': [], 'issues': [], 'segmentation_status': 'unsegmented',
              'page_roles': {}}
    if course not in COURSES or not len(doc):
        result['issues'].append('unsupported_ial_course_or_empty_document')
        return result
    cover = doc[0].get_text()
    if (re.search(r'save\s*my\s*exams|savemyexams', cover, re.I)
            and any(ANSWER_HEADING.fullmatch(line.strip()) for line in cover.splitlines())):
        result['issues'].append('answer_material_not_questions')
        result['page_roles'] = {str(i + 1): 'answer_section' for i in range(len(doc))}
        return result
    if 'Your notes' in cover:
        result['issues'].append('lesson_notes_not_question_compilation')
        result['page_roles'] = {str(i + 1): 'lesson_notes' for i in range(len(doc))}
        return result
    def cover_info(text):
        declared = re.search(r'(?m)^([1-9]\d*)\s+questions?\s*$', text)
        heading = next((heading for heading in ('Exam Questions', 'Multiple Choice Questions',
                                                'Structured Questions') if heading in text), None)
        if any(ANSWER_HEADING.fullmatch(line.strip()) for line in text.splitlines()):
            return None
        if not (declared and heading and re.search(r'save\s*my\s*exams|savemyexams', text, re.I)):
            return None
        return {'declared_question_count': int(declared[1]),
                'question_type': 'mcq' if heading == 'Multiple Choice Questions' else 'structured'}

    if not cover_info(cover):
        result['issues'].append('unsupported_topical_layout')
        return result
    expected = 0
    result['compilations'] = []
    section, previous, answer_section = 'Questions', 0, False
    sequence_errors = []
    compilation = None
    for index in range(len(doc)):
        page = doc[index]
        width, height = page.rect.width, page.rect.height
        info = cover_info(page.get_text())
        if info and not answer_section:
            expected += info['declared_question_count']
            compilation = {**info, 'page': index + 1, 'detected_question_count': 0}
            result['compilations'].append(compilation)
            result['page_roles'][str(index + 1)] = 'cover'
            section, previous = 'Questions', 0
            continue
        # A standalone heading is required: a question mentioning answers is safe.
        lines = []
        for block in page.get_text('dict')['blocks']:
            for line in block.get('lines', []):
                value = ''.join(span['text'] for span in line['spans']).strip()
                lines.append((line['bbox'][1] / height, value))
        if any(y < .22 and ANSWER_HEADING.fullmatch(value) for y, value in lines):
            answer_section = True
        if answer_section:
            result['page_roles'][str(index + 1)] = 'answer_section'
            continue
        result['page_roles'][str(index + 1)] = 'question_content'
        headings = [(y, match[1].title()) for y, value in lines
                    if (match := SECTION.fullmatch(value))]
        words = page.get_text('words', sort=True)
        starts = []
        for word in words:
            x0, y0, x1, y1, label = word[:5]
            # Question numbers end at the two observed gutter edges: .148
            # without a part and .122 before (a). Diagram/table values live right.
            if (not re.fullmatch(r'[1-9]\d{0,2}', label)
                    or not .035 < y0 / height < .93
                    or not (.145 < x1 / width < .151 or .119 < x1 / width < .125)):
                continue
            same_row = [w for w in words if w[0] > x1 + .002 * width
                        and abs(w[1] - y0) < .006 * height and w[0] < .42 * width]
            if x1 / width < .13 and not any(w[4] == '(a)' for w in same_row):
                continue
            starts.append({'page': index + 1, 'top': y0 / height,
                           'bottom': y1 / height, 'label': label,
                           'official_qid': None, 'part': ''})
        for anchor in sorted(starts, key=lambda a: a['top']):
            relevant = [(y, name) for y, name in headings if y < anchor['top']]
            if relevant:
                name = relevant[-1][1]
                if name != section:
                    section, previous = name, 0
            anchor['section'] = section
            anchor['compilation_page'] = compilation['page']
            anchor['question_type'] = compilation['question_type']
            compilation['detected_question_count'] += 1
            if int(anchor['label']) != previous + 1:
                sequence_errors.append({'page': index + 1, 'label': anchor['label'],
                                        'section': section, 'expected': previous + 1})
            previous = int(anchor['label'])
            result['anchors'].append(anchor)
    if answer_section:
        result['issues'].append('answer_section_excluded')
    result['declared_question_count'] = expected
    if any(c['detected_question_count'] != c['declared_question_count']
           for c in result['compilations']):
        result['issues'].append('declared_question_count_mismatch')
    if sequence_errors:
        result['issues'].append('question_number_sequence_mismatch')
        result['sequence_errors'] = sequence_errors
    if (len(result['anchors']) == expected and not sequence_errors
            and 'declared_question_count_mismatch' not in result['issues']):
        result['segmentation_status'] = 'qualified'
    elif result['anchors']:
        result['segmentation_status'] = 'requires_review'
    result['issues'].append('official_identity_unavailable')
    return result
