"""Geometry-backed CAIE topical start markers, with explicit uncertain pages.

This is mechanical preparation only. A printed compilation number is never an
original question identity; only a complete explicit code can establish that.
Coordinates cover the start marker, not a computed complete question region.
"""
from __future__ import annotations

import re

import pymupdf

_EXAMMATE = re.compile(
    r'^\s*(\d+)\s*-\s*\((970[12])/(\d{1,2})_(Summer|Winter|Spring|March|February)_(20\d{2})_Q(\d+)\s*\)', re.I)
_NATIVE = re.compile(r'^\s*(\d+)\.\s*(970[12])_([msw])(\d{2})_qp_(\d{1,2})\b', re.I)
_SLASH = re.compile(r'(970[12])/(\d{1,2})/(M/J|O/N|F/M)/(\d{2})(?:/Q(\d+))?', re.I)
_Q = re.compile(r'\bQ:\s*(\d+)\b', re.I)
_CLASSIFIED = re.compile(r'^Q(\d+)\.$')
_SESSIONS = {'summer': 's', 'winter': 'w', 'spring': 'm', 'march': 'm', 'february': 'm',
             'M/J': 's', 'O/N': 'w', 'F/M': 'm'}


def _lines(page):
    """Keep source geometry; some publishers serialize headers bottom first."""
    lines = []
    for block in page.get_text('dict', flags=pymupdf.TEXTFLAGS_DICT & ~pymupdf.TEXT_PRESERVE_IMAGES)['blocks']:
        for line in block.get('lines', []):
            text = ''.join(span['text'] for span in line['spans']).strip()
            if text:
                lines.append({'text': text, 'bbox': line['bbox'], 'dir': line.get('dir', (1, 0))})
    return sorted(lines, key=lambda line: (line['bbox'][1], line['bbox'][0]))


def _anchor(page, rect, bbox, label, qid, profile):
    return {'page': page, 'top': max(0.0, bbox[1] / rect.height),
            'bottom': min(1.0, bbox[3] / rect.height), 'label': label,
            'official_qid': qid, 'part': '', 'profile': profile,
            'evidence_bbox': list(bbox)}


def _answer_page(page, lines):
    # These are publisher headings, not incidental mentions in question prose.
    if any(re.search(r'\bCH\d+\s*-\s*Answers?\s*-', line['text'], re.I) for line in lines):
        return True
    texts = {line['text'].upper() for line in lines}
    if {'SN', 'PAPER', 'Q. NO.', 'ANSWER'} <= texts:
        return True
    # Exam-mate's answer appendix repeats identical question headers but replaces
    # each image with a single answer letter. Never interpret those as questions.
    if not page.get_images() and any(_EXAMMATE.match(line['text']) for line in lines):
        body = [line['text'] for line in lines
                if 75 < line['bbox'][1] < page.rect.height - 80
                and not _EXAMMATE.match(line['text'])]
        if body and all(re.fullmatch(r'[ABCD]', text) for text in body):
            return True
    # Some classified "question" files are in fact just compact answer tables.
    cells = [line['text'] for line in lines]
    return len(cells) >= 8 and all(re.fullmatch(r'(?:\d+[ABCD]|NIL)', text) for text in cells)


def find_anchors(doc, course: str) -> dict:
    """Return whole-question start markers and page-specific review issues.

    Supported profiles are explicit exam-mate headers, PapaCambridge/Examinent
    code headers, classified Qn. labels, and the old compilation's outer gutter.
    An image-only PDF is not OCR'd here. Answer pages are hard segmentation stops.
    """
    if course not in {'9701', '9702'}:
        return {'profile': 'caie_unsupported', 'anchors': [],
                'issues': [{'reason': 'unsupported_course', 'course': course}], 'page_roles': {}}
    anchors, issues, roles, profiles = [], [], {}, set()
    seen_content = False
    for index, page in enumerate(doc):
        number = index + 1
        lines = _lines(page)
        text = '\n'.join(line['text'] for line in lines)
        page_anchors = []
        if _answer_page(page, lines):
            roles[str(number)] = 'answer'
            issues.append({'page': number, 'reason': 'answer_page'})
            continue
        if not re.search(r'[A-Za-z]{2}', text) and not any(_CLASSIFIED.fullmatch(line['text']) for line in lines):
            if seen_content and page.get_images():
                roles[str(number)] = 'continuation'
            else:
                roles[str(number)] = 'missing_text'
                issues.append({'page': number, 'reason': 'missing_text', 'requires_ocr': True})
            continue
        if any(abs(line['dir'][1]) > .03 for line in lines):
            roles[str(number)] = 'unsupported'
            issues.append({'page': number, 'reason': 'slanted_text_layout'})
            continue
        for line in lines:
            match = _EXAMMATE.match(line['text'])
            if match:
                label, actual_course, paper, season, year, question = match.groups()
                profile = 'caie_exammate_header'
                qid = f'{actual_course}_{_SESSIONS[season.lower()]}{year[-2:]}_{paper}_q{int(question)}'
            else:
                match = _NATIVE.match(line['text'])
                if not match:
                    continue
                label, actual_course, season, year, paper = match.groups()
                profile = 'caie_papacambridge_header'
                # MuPDF may separate "Q: 7" from the code into its own line.
                peers = [other['text'] for other in lines
                         if abs(other['bbox'][1] - line['bbox'][1]) < 3
                         and other['bbox'][0] >= line['bbox'][0]]
                questions = {q for peer in peers for q in _Q.findall(peer)}
                qid = f'{actual_course}_{season.lower()}{year}_{paper}_q{int(next(iter(questions)))}' if len(questions) == 1 else None
                if not qid:
                    issues.append({'page': number, 'reason': 'missing_question_identity', 'label': label})
            if actual_course != course:
                issues.append({'page': number, 'reason': 'conflicting_identity', 'label': label, 'printed_course': actual_course})
                continue
            if line['bbox'][0] > page.rect.width * .3:
                issues.append({'page': number, 'reason': 'unsupported_anchor_geometry', 'label': label})
                continue
            page_anchors.append(_anchor(number, page.rect, line['bbox'], label, qid, profile))

        # Explicit Qn. labels in classified image worksheets are compilation IDs.
        if not page_anchors:
            for line in lines:
                match = _CLASSIFIED.fullmatch(line['text'])
                if match and line['bbox'][0] < page.rect.width * .25:
                    page_anchors.append(_anchor(number, page.rect, line['bbox'], match[1], None, 'caie_classified_q_label'))

        # Old 2002-15 compilations put official codes *inside* question prose.
        # Boundaries come from the far-left number gutter, not those code lines.
        slash_lines = [(line, match) for line in lines for match in _SLASH.finditer(line['text'])]
        if not page_anchors and slash_lines:
            if any(match[1] != course for _, match in slash_lines):
                issues.append({'page': number, 'reason': 'conflicting_identity'})
            else:
                gutter = sorted([word for word in page.get_text('words')
                                 if re.fullmatch(r'\d{1,3}', word[4]) and 35 < word[0] < 68
                                 and word[2] < 75 and 58 < word[1] < page.rect.height - 65], key=lambda word: word[1])
                for pos, word in enumerate(gutter):
                    end = gutter[pos + 1][1] if pos + 1 < len(gutter) else page.rect.height - 50
                    codes = {match[0] for line, match in slash_lines
                             if word[1] - 4 <= line['bbox'][1] < end - 2 and match[5]}
                    qid = None
                    if len(codes) == 1:
                        match = _SLASH.fullmatch(next(iter(codes)))
                        qid = f'{match[1]}_{_SESSIONS[match[3].upper()]}{match[4]}_{match[2]}_q{int(match[5])}'
                    elif len(codes) > 1:
                        issues.append({'page': number, 'reason': 'conflicting_identity', 'label': word[4]})
                    page_anchors.append(_anchor(number, page.rect, word[:4], word[4], qid, 'caie_legacy_gutter'))

        page_anchors.sort(key=lambda anchor: anchor['top'])
        for previous, current in zip(page_anchors, page_anchors[1:]):
            before, after = int(previous['label']), int(current['label'])
            if after > before + 1:
                issues.append({'page': number, 'reason': 'missing_question_anchor',
                               'between_labels': [previous['label'], current['label']]})
        # The same label printed twice with different codes is never a safe join.
        by_label = {}
        for anchor in page_anchors:
            by_label.setdefault(anchor['label'], set()).add(anchor['official_qid'])
        bad = {label for label, identities in by_label.items() if len(identities) > 1}
        if bad:
            issues.append({'page': number, 'reason': 'conflicting_identity', 'labels': sorted(bad)})
            page_anchors = [anchor for anchor in page_anchors if anchor['label'] not in bad]
        if page_anchors:
            roles[str(number)] = 'question'
            seen_content = True
            profiles.update(anchor['profile'] for anchor in page_anchors)
            anchors.extend(page_anchors)
        elif re.search(r'\bcontents\b|\bTOPICAL PAST PAPER WORKSHEETS\b|^Introduction\b', text, re.I):
            roles[str(number)] = 'front_matter'
        else:
            # This can include a lost start marker; callers must retain/review
            # unanchored prefixes rather than inferring an invisible question.
            roles[str(number)] = 'continuation' if seen_content else 'unanchored'
            if not seen_content:
                issues.append({'page': number, 'reason': 'unanchored_page'})
    if not anchors:
        issues.append({'reason': 'no_anchors'})
    return {'profile': next(iter(profiles)) if len(profiles) == 1 else 'caie_mixed' if profiles else 'caie_unrecognized',
            'anchors': anchors, 'issues': issues, 'page_roles': roles}
