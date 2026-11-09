"""Exact IAL identities and original-source pins; recognition grants no approval."""
from __future__ import annotations

import copy
import hashlib
import math

from .ial_p1_identity import p1_identity, p1_namespace, p1_pilot, p1_question, validate_p1_sources

_P2_Q1 = 'P2_pearson-edexcel-ial_WMA12_2019-06_01_q1'
_P2_QUESTION = {
    'course': 'P2', 'board': 'Pearson Edexcel', 'unit': 'WMA12',
    'session': '2019-06', 'component': '01', 'question': 1, 'part': '',
    'assessed_parts': ['a(i)', 'a(ii)', 'b'],
    'part_suffixes': {'a(i)': 'a-i', 'a(ii)': 'a-ii', 'b': 'b'},
    'qp': {'asset_id': 'asset:legacy-f10afe0b25e647fb783a2dee',
           'path': 'Library/Courses/P2/Sources/PastPapers/ial/WMA12/WMA12_2019_Jun_qp.pdf',
           'sha256': '4c4e7702880bf159c01532e67e4990a3f3d36f6c11c52a2d5ff464f53e220d77', 'pages': 11,
           'initial_pages': [1, 2], 'initial_selector': '1-2',
           'required_region_pages': [2], 'allowed_region_pages': [2]},
    'ms': {'asset_id': 'asset:legacy-4da88baf2635cd6489af022d',
           'path': 'Library/Courses/P2/Sources/PastPapers/ial/WMA12/WMA12_2019_Jun_ms.pdf',
           'sha256': '95685db810234d0e8505fdafefa2b6624deb4b51a96ccf00d61fbc25bf89f0a1', 'pages': 26,
           'initial_pages': [1, 2, 3, 4, 5, 6, 7], 'initial_selector': '1-7',
           'required_region_pages': [7], 'allowed_region_pages': [1, 2, 3, 4, 5, 6, 7]},
}


def ial_question(qid: object) -> dict | None:
    """Return independent exact whole-question metadata, separate from assessment."""
    if isinstance(qid, str) and qid == _P2_Q1:
        return copy.deepcopy(_P2_QUESTION)
    return p1_question(qid)


def ial_assessed(qid: object, part: object) -> dict | None:
    """Authenticate exact printed labels without case or punctuation aliases."""
    if isinstance(qid, str) and qid == _P2_Q1:
        if not isinstance(part, str) or part not in _P2_QUESTION['assessed_parts']:
            return None
        question = copy.deepcopy(_P2_QUESTION)
        question['part'] = part
        return question
    return p1_pilot(qid, part)


def ial_identity(qid: object, part: object) -> str | None:
    if isinstance(qid, str) and qid == _P2_Q1:
        return qid + ':' + part if ial_assessed(qid, part) is not None else None
    return p1_identity(qid, part)


def ial_namespace(qid: object) -> bool:
    """Reserve resemblance against CAIE fallback; this grants no recognition."""
    return p1_namespace(qid) or isinstance(qid, str) and qid.lower().startswith('p2_')


def validate_ial_sources(qid, part, course, question_regions, scheme_regions, library) -> None:
    """Validate exact source roles, nested-record pages, catalog metadata and bytes."""
    if not isinstance(qid, str) or qid != _P2_Q1:
        return validate_p1_sources(qid, part, course, question_regions, scheme_regions, library)
    pilot = ial_assessed(qid, part)
    if pilot is None or course != 'P2':
        raise ValueError('unsupported P2 official identity or course')
    try:
        for role, regions in (('qp', question_regions), ('ms', scheme_regions)):
            pin = pilot[role]
            if not isinstance(regions, list) or not regions:
                raise ValueError('P2 source regions must be nonempty ordered lists')
            last = 0
            for region in regions:
                if (not isinstance(region, dict) or region.get('source_id') != pin['asset_id']
                        or region.get('source_sha256') != pin['sha256']):
                    raise ValueError('P2 source role or digest mismatch')
                page, box = region.get('page'), region.get('box')
                if type(page) is not int or not last <= page <= pin['pages'] or page < 1:
                    raise ValueError('invalid or unordered P2 source page')
                last = page
                if (not isinstance(box, list) or len(box) != 4
                        or any(type(v) not in (int, float) or not math.isfinite(v) for v in box)
                        or not (0 <= box[0] < box[2] <= 1 and 0 <= box[1] < box[3] <= 1)):
                    raise ValueError('invalid normalized P2 source box')
            pages = {region['page'] for region in regions}
            if not set(pin['required_region_pages']) <= pages or not pages <= set(pin['allowed_region_pages']):
                raise ValueError('P2 question-specific source pages changed')
            record = library.record(pin['asset_id'])
            if (record.get('path') != pin['path'] or record.get('sha256') != pin['sha256']
                    or record.get('course') != 'P2' or record.get('kind') != 'Sources/PastPapers'):
                raise ValueError('P2 source catalog binding mismatch')
            if hashlib.sha256(library.read(pin['asset_id'])).hexdigest() != pin['sha256']:
                raise ValueError('P2 original source bytes changed')
    except OSError as exc:
        raise ValueError(f'P2 source unavailable: {exc}') from None
