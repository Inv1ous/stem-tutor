"""Conservative native-only proof of a closed, explicitly labelled MS total.

Called only after the existing locators supply no authority. The caller retains
source-byte/cover checks, complete question scope, QP agreement and all review
and publication gates. No mark allocation is inferred or summed here.
"""
from __future__ import annotations

import copy
import re

from tutorlib.prepared_evidence import validate_region


def located_native_closed_totals(q, layouts, sources):
    """Return one exact Total N witness, or no authority for an ambiguous page.

    This deliberately accepts only one complete native MS page, with ordered
    Question/Number, Scheme, [Notes], Marks headers. Every native word counts:
    no footer cutoff or Notes cutoff can hide a later right-column allocation.
    """
    regions = q.get('scheme_regions', [])
    if len(regions) != 1 or type(q.get('number')) is not int or q['number'] < 1:
        return []
    region = regions[0]
    try:
        validate_region(region, 'ms', sources)
    except (ValueError, KeyError, TypeError):
        return []
    if region['box'] != [0, 0, 1, 1]:
        return []
    pages = layouts.get('ms', [])
    page_number = region['page']
    if not 1 <= page_number <= len(pages):
        return []
    page = pages[page_number - 1]
    if page['page'] != page_number or [s['number'] for s in page['starts']] != [q['number']]:
        return []
    words = page['words']
    if any(re.search(r'\bcontinued\b', w['text'], re.I) for w in words):
        return []
    headers = {}
    for label in ('Question', 'Number', 'Scheme', 'Marks'):
        found = [w for w in words if w['text'] == label and w['box'][1] < .2]
        if len(found) != 1:
            return []
        headers[label] = found[0]['box']
    question, number, scheme, marks = (headers[k] for k in ('Question', 'Number', 'Scheme', 'Marks'))
    if not (.03 < number[0] < .3 and abs(question[0] - number[0]) < .015
            and 0 < number[1] - question[1] < .035
            and max(question[2], number[2]) < scheme[0] < scheme[2] < marks[0]
            and marks[0] > .7
            and abs(scheme[1] - number[1]) < .025
            and abs(marks[1] - scheme[1]) < .012):
        return []
    notes = [w['box'] for w in words if w['text'] in ('Notes', 'Notes:') and w['box'][1] < .2]
    if len(notes) > 1 or notes and not (scheme[2] < notes[0][0] < notes[0][2] < marks[0]
                                       and abs(notes[0][1] - scheme[1]) < .012):
        return []
    # A single literal anywhere on the full page; even another Notes Total
    # (including equal values) prevents this proof from claiming ownership.
    totals = [w for w in words if re.search(r'\btotal\b', w['text'], re.I)]
    if len(totals) != 1 or totals[0]['text'] != 'Total':
        return []
    total = totals[0]
    index = words.index(total)
    if index + 1 == len(words):
        return []
    value = words[index + 1]
    a, b = total['box'], value['box']
    if not (re.fullmatch(r'[1-9]\d*', value['text'])
            and abs(a[1] - b[1]) < .004 and abs(a[3] - b[3]) < .004
            and 0 <= b[0] - a[2] < .025
            and marks[0] - .02 <= b[0] <= marks[2] + .02
            and a[1] > max(question[3], number[3], scheme[3], marks[3])):
        return []
    left = marks[0] - .05
    if a[0] < left:
        return []
    tokens = [total, value]
    centre = (a[1] + a[3]) / 2
    line = [w for w in words if w['box'][2] > left
            and abs((w['box'][1] + w['box'][3]) / 2 - centre) < .004]
    if line != tokens:
        return []
    # Includes overlapping lower glyphs and content at the physical page foot.
    if any(w not in tokens and w['box'][2] > left
           and (w['box'][1] >= min(a[1], b[1]) - .004
                or (w['box'][1] + w['box'][3]) / 2 >= centre - .004)
           for w in words):
        return []
    gutter_left = min(question[0], number[0]) - .01
    gutter_right = max(question[2], number[2]) + .02
    rows = []
    for word in words:
        text, box = word['text'], word['box']
        if not (box[2] >= gutter_left and box[0] <= gutter_right and box[1] > number[3]):
            continue
        if box[0] < gutter_left:
            # A clipped/offset label crossing the gutter is ambiguous even if
            # the old start parser missed its compact nested part spelling.
            if re.match(r'\d|\([A-Za-z]', text):
                return []
            continue
        numbered = re.fullmatch(r'([1-9]\d*)\.?(?:\([a-z]\)(?:\([ivx]+\))?)?', text)
        if numbered:
            if int(numbered[1]) != q['number'] or box[3] >= a[1]:
                return []
            rows.append(word)
        elif re.match(r'\d|\([A-Za-z]', text):
            # Unknown compact parts or formula numbers in the left gutter are
            # ambiguous. Ordinary unnumbered native part labels remain valid.
            if not re.fullmatch(r'\((?:[a-z]|[ivx]+)\)(?:\([ivx]+\))?', text):
                return []
    start = page['starts'][0]
    if not rows or not any(w['box'] == start['box'] for w in rows):
        return []
    box = [a[0], min(a[1], b[1]), b[2], max(a[3], b[3])]
    return [{'kind': 'question_total', 'value': int(value['text']),
             'label': 'Total ' + value['text'], 'region': {**copy.deepcopy(region), 'box': box}}]
