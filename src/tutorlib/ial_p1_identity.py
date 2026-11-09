"""Exact source-pinned Pearson whole scopes and assessed identities; no content or rubric approval."""
from __future__ import annotations

import copy
import hashlib
import math

_QID = 'P1_pearson-edexcel-ial_WMA11_2019-01_01_q1'
_PILOT = {
    'course': 'P1', 'board': 'Pearson Edexcel', 'unit': 'WMA11',
    'session': '2019-01', 'component': '01', 'question': 1, 'part': '',
    'qp': {'asset_id': 'asset:legacy-5433803d0abf868d346949c8',
           'path': 'Library/Courses/P1/Sources/PastPapers/ial/WMA11/WMA11_2019_Jan_qp.pdf',
           'sha256': 'dfdc644b3818d2242980e515b0b408fd959036cb0ccde78d410e392941360968', 'pages': 28},
    'ms': {'asset_id': 'asset:legacy-49fc389000ec4447e3b10835',
           'path': 'Library/Courses/P1/Sources/PastPapers/ial/WMA11/WMA11_2019_Jan_ms.pdf',
           'sha256': '03d6d5ba312b272436e189b45b9e0d5e6540e442b5b140c67ac089ef7d2b5fda', 'pages': 29},
}


# Q1's returned descriptor remains byte-for-byte compatible. Q2 alone needs
# tighter page pins because it shares the same original PDFs with Q1.
_Q2_ID = 'P1_pearson-edexcel-ial_WMA11_2019-01_01_q2'
_Q2_PILOT = copy.deepcopy(_PILOT)
_Q2_PILOT['question'] = 2
_Q2_PILOT['qp'].update(initial_pages=[1, 4, 5], initial_selector='1,4-5',
                       required_region_pages=[4, 5], allowed_region_pages=[4, 5])
_Q2_PILOT['ms'].update(initial_pages=[1, 2, 3, 4, 5, 6, 7, 9, 10], initial_selector='1-7,9-10',
                       required_region_pages=[9, 10], allowed_region_pages=[1, 2, 3, 4, 5, 6, 7, 9, 10])


_Q3_ID = 'P1_pearson-edexcel-ial_WMA11_2019-01_01_q3'
_Q3_QUESTION = copy.deepcopy(_PILOT)
_Q3_QUESTION.update(question=3, assessed_parts=['a', 'b'])
_Q3_QUESTION['qp'].update(initial_pages=[1, 6, 7], initial_selector='1,6-7',
                         required_region_pages=[6, 7], allowed_region_pages=[6, 7])
_Q3_QUESTION['ms'].update(initial_pages=[1, 2, 3, 4, 5, 6, 7, 11, 12], initial_selector='1-7,11-12',
                         required_region_pages=[11, 12], allowed_region_pages=[1, 2, 3, 4, 5, 6, 7, 11, 12])


_Q4_ID = 'P1_pearson-edexcel-ial_WMA11_2019-01_01_q4'
_Q4_QUESTION = copy.deepcopy(_PILOT)
_Q4_QUESTION['question'] = 4
_Q4_QUESTION['qp'].update(initial_pages=[1, 8, 9], initial_selector='1,8-9',
                         required_region_pages=[8, 9], allowed_region_pages=[8, 9])
_Q4_QUESTION['ms'].update(initial_pages=[1, 2, 3, 4, 5, 6, 7, 13], initial_selector='1-7,13',
                         required_region_pages=[13], allowed_region_pages=[1, 2, 3, 4, 5, 6, 7, 13])


def p1_question(qid: object) -> dict | None:
    """Return independent exact whole-scope pins, not an assessed-record identity."""
    if isinstance(qid, str):
        for identity, question in ((_QID, _PILOT), (_Q2_ID, _Q2_PILOT), (_Q3_ID, _Q3_QUESTION), (_Q4_ID, _Q4_QUESTION)):
            if qid == identity:
                return copy.deepcopy(question)
    return None


def p1_pilot(qid: object, part: object) -> dict | None:
    """Authenticate exact assessed labels; Q3 has no empty aggregate record."""
    if not isinstance(part, str):
        return None
    question = p1_question(qid)
    if question is None or part not in question.get('assessed_parts', ['']):
        return None
    question['part'] = part
    return question


def p1_identity(qid: object, part: object) -> str | None:
    """Canonical assessed identity without punctuation or case aliases."""
    if p1_pilot(qid, part) is None:
        return None
    return qid + (':' + part if part else '')


def p1_namespace(qid: object) -> bool:
    """Block fallback for namespace resemblance; this grants no identity."""
    return isinstance(qid, str) and (qid.lower().startswith('p1_') or 'pearson' in qid.lower())


def validate_p1_sources(qid, part, course, question_regions, scheme_regions, library) -> None:
    """Validate role/shape, declared page pins and bytes; never semantic coverage."""
    pilot = p1_pilot(qid, part)
    if pilot is None or course != 'P1':
        raise ValueError('unsupported P1 official identity or course')
    try:
        for role, regions in (('qp', question_regions), ('ms', scheme_regions)):
            pin = pilot[role]
            if not isinstance(regions, list) or not regions:
                raise ValueError('P1 source regions must be nonempty ordered lists')
            last = 0
            for region in regions:
                if (not isinstance(region, dict) or region.get('source_id') != pin['asset_id']
                        or region.get('source_sha256') != pin['sha256']):
                    raise ValueError('P1 source role or digest mismatch')
                page, box = region.get('page'), region.get('box')
                if type(page) is not int or not last <= page <= pin['pages'] or page < 1:
                    raise ValueError('invalid or unordered P1 source page')
                last = page
                if (not isinstance(box, list) or len(box) != 4
                        or any(type(v) not in (int, float) or not math.isfinite(v) for v in box)
                        or not (0 <= box[0] < box[2] <= 1 and 0 <= box[1] < box[3] <= 1)):
                    raise ValueError('invalid normalized P1 source box')
            if 'required_region_pages' in pin:
                pages = {region['page'] for region in regions}
                if (not set(pin['required_region_pages']) <= pages
                        or not pages <= set(pin['allowed_region_pages'])):
                    raise ValueError('P1 question-specific source pages changed')
            record = library.record(pin['asset_id'])
            if (record.get('path') != pin['path'] or record.get('sha256') != pin['sha256']
                    or record.get('course') != 'P1' or record.get('kind') != 'Sources/PastPapers'):
                raise ValueError('P1 source catalog binding mismatch')
            if hashlib.sha256(library.read(pin['asset_id'])).hexdigest() != pin['sha256']:
                raise ValueError('P1 original source bytes changed')
    except OSError as exc:
        raise ValueError(f'P1 source unavailable: {exc}') from None
