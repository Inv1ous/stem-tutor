"""Conservative PMT preparation proposals; never identities or content approval.

Registered path provenance and publisher content must agree. Unknown boundaries
stop continuation; answer evidence quarantines whole pages before any anchors.
"""
from __future__ import annotations

import re

from topical_caie import _lines

COURSES = {'P1', 'P2', 'P3', 'P4', 'FP1', 'FP2', 'FP3', 'M1', 'D1', 'S1', 'S2', 'S3'}
_REGISTERED = re.compile(r'(?:^|/)Library/Courses/([^/]+)/Sources/Library/PMT/Edexcel/([^/]+)/', re.I)
_PUBLISHER = re.compile(r'physics\s*and\s*maths\s*tutor(?:\.com)?', re.I)
_RUBRIC = re.compile(r'\b(?:[MAB][1-9](?:ft)?|cao|awrt|oe|dep\s*M1)\b')
_ANSWER = re.compile(r'^\s*(?:mark\s+schemes?|answers?(?:\s+and\s+solutions)?|solutions?|examiner[’\x27s ]*reports?)\s*$', re.I)
_REPORT = re.compile(r'\b(?:most|many|some|few|the majority of)\s+candidates\b|\bcandidates\s+(?:scored|gained|were|found|had|could|did|used)\b', re.I)
_FORMULA = re.compile(
    r'^(?:Edexcel\b.*?\b)?(?:Formulae? List|Formula(?:e|s)? Sheet|Mathematical Formulae'
    r'(?: and Statistical Tables)?)(?:\s*[:–—-].*)?\s*$', re.I)
_CONTINUED = re.compile(r'\bQuestion\s+([1-9]\d*)\s+continued\b', re.I)


def registered_course(source_path: str | None) -> str | None:
    """Return the module only for the canonical PMT provenance shelf."""
    match = _REGISTERED.search(str(source_path or '').replace('\\', '/'))
    return match[1].upper() if match and match[1].upper() == match[2].upper() else None


def find_anchors(doc, course: str, source_path: str | None = None) -> dict:
    """Return provisional starts, explicit private stops and raster exceptions.

    No printed compilation number is promoted to official identity. No declared
    count is inferred. Raster regions with a visible start remain review fragments.
    """
    result = {'profile': 'pmt-unrecognized', 'anchors': [], 'page_roles': {},
              'issues': [], 'segmentation_status': 'unsegmented'}
    actual = registered_course(source_path)
    if course not in COURSES or actual != course or not len(doc):
        result['issues'].append({'reason': 'pmt_source_course_or_provenance_conflict',
                                 'source_course': actual, 'requested_course': course})
        return result
    path = str(source_path).replace('\\', '/').lower()
    # Library source roles are authoritative even when the source is raster.
    if re.search(r'/notes/|\bnotes\.pdf$', path):
        result['profile'] = 'pmt-notes-v1'
        result['page_roles'] = {str(n + 1): 'lesson_notes' for n in range(len(doc))}
        result['issues'].append('lesson_notes_not_question_compilation')
        return result
    if re.search(r'/mark[ _-]*schemes?/|\bms\.pdf$|\banswers?\.pdf$', path):
        result['profile'] = 'pmt-answer-v1'
        result['page_roles'] = {str(n + 1): 'answer_section' for n in range(len(doc))}
        return result
    # A canonical path alone cannot establish a question layout.
    if not any(_PUBLISHER.search(doc[n].get_text()) for n in range(min(3, len(doc)))):
        result['issues'].append('pmt_publisher_content_missing')
        return result
    layout = ('set1' if '/edexcel-set-1/' in path else
              'set2' if '/edexcel-set-2/' in path else 'plain')
    result['profile'] = f'pmt-{layout}-v1'
    private = False
    formula = False
    previous = None
    active_label = None
    for index, page in enumerate(doc):
        number = index + 1
        lines = _lines(page)
        text = '\n'.join(line['text'] for line in lines)
        starts = []
        for word in page.get_text('words', sort=True):
            x0, y0, x1, y1, value = word[:5]
            match = re.fullmatch(r'([1-9]\d{0,2})\.', value)
            if (match and .045 < x0 / page.rect.width < .12
                    and .06 < y0 / page.rect.height < .90):
                starts.append({'page': number, 'top': y0 / page.rect.height,
                               'bottom': y1 / page.rect.height, 'label': match[1],
                               'official_qid': None, 'part': '', 'section': 'Questions',
                               'question_type': 'structured'})
        starts.sort(key=lambda a: a['top'])
        # Module M1 in the running header/cover is not a method mark.
        rubric = any(_RUBRIC.search(line['text']) for line in lines
                     if line['bbox'][1] > page.rect.height * .08
                     and not re.search(r'Edexcel|Maths|Mechanics', line['text'], re.I))
        report = bool(_REPORT.search(text))
        heading = any(_ANSWER.fullmatch(line['text']) for line in lines)
        continued = _CONTINUED.search(text)
        continuing_question = bool(continued and active_label == continued[1])
        question_end = bool(re.search(r'\(Total\s+\d+\s+marks?\)', text, re.I))
        reset = bool(layout == 'set1' and starts and (
            (previous is not None and int(starts[0]['label']) <= previous)
            or any(int(b['label']) <= int(a['label']) for a, b in zip(starts, starts[1:]))))
        if rubric or report or heading or reset:
            # At the first private boundary, numbered starts may still be
            # questions even without a printed Total terminator. Do not infer
            # a public cutoff inside that page.
            if (question_end or ((starts or continuing_question) and not private)) and (rubric or report or heading or reset):
                result['issues'].append({'page': number, 'reason': 'mixed_question_answer_page'})
            if reset:
                result['issues'].append({'page': number, 'reason': 'question_number_reset_private_boundary',
                                         'rubric_evidence': rubric, 'report_evidence': report})
            private = True
        if private:
            result['page_roles'][str(number)] = 'answer_section'
            active_label = None
            continue
        # Match a complete formula heading, never a cover/prose reference to
        # a formula booklet. Publisher footer titles also identify appendices.
        if any(_FORMULA.fullmatch(line['text']) for line in lines):
            formula = True
        if formula or re.search(r'\bRevision Notes\b', text, re.I):
            result['page_roles'][str(number)] = 'lesson_notes'
            active_label = None
            continue
        if not text.strip() or not re.search(r'[A-Za-z]{2}', text):
            result['page_roles'][str(number)] = 'missing_text'
            result['issues'].append({'page': number, 'reason': 'missing_text', 'requires_ocr': True})
            active_label = None
            continue
        if 'Topic Questions from Papers' in text:
            result['page_roles'][str(number)] = 'cover'
            active_label = None
            continue
        if continuing_question and not starts:
            result['page_roles'][str(number)] = 'continuation'
            continue
        if starts:
            # Plain S3 pasted scans can have a text label but no text stem. The
            # complete original image stays in review, never a whole question.
            for pos, anchor in enumerate(starts):
                end = starts[pos + 1]['top'] if pos + 1 < len(starts) else 1
                body = [line['text'] for line in lines
                        if anchor['top'] <= line['bbox'][1] / page.rect.height < end
                        and line['bbox'][0] > page.rect.width * .12
                        and not _PUBLISHER.search(line['text'])]
                prose = ' '.join(body)
                images = [info['bbox'] for info in page.get_image_info()
                          if anchor['top'] <= info['bbox'][1] / page.rect.height < end
                          and (info['bbox'][2] - info['bbox'][0]) > page.rect.width * .3]
                if images and len(re.findall(r'[A-Za-z]{3,}', prose)) < 6:
                    anchor['candidate_unit'] = 'review_fragment'
                    result['issues'].append({'page': number, 'label': anchor['label'],
                                             'reason': 'raster_question_fragment', 'requires_ocr': True})
            result['anchors'].extend(starts)
            result['page_roles'][str(number)] = 'question'
            previous = int(starts[-1]['label'])
            active_label = starts[-1]['label'] if 'candidate_unit' not in starts[-1] else None
        else:
            result['page_roles'][str(number)] = 'unanchored'
            result['issues'].append({'page': number, 'reason': 'unanchored_page'})
            active_label = None
    result['issues'].append('official_identity_unavailable')
    if result['anchors']:
        result['segmentation_status'] = 'requires_review'
    return result
