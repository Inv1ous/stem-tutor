"""Import-safe index keys; recognition grants no dedup or teaching approval."""
import json
import re

from tutorlib.ial_identity import ial_assessed, validate_ial_sources
from tutorlib.prepared_evidence import pearson_namespace, authenticate_prepared_item, bank_identity


def encoded(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'))


def context(course, chapters, kcs, graphs):
    ch, kc = graphs.get(course, (set(), {}))
    if not isinstance(chapters, list) or not chapters or not all(isinstance(x, str) and x in ch for x in chapters):
        return None
    if not isinstance(kcs, list) or not kcs or not all(isinstance(x, str) and x in kc and kc[x] in chapters for x in kcs):
        return None
    return [sorted(set(chapters)), sorted(set(kcs))]


def question_key(course, row, graphs, library=None, *, bank_item=None):
    qid, part = row.get('official_qid'), row.get('part')
    ctx = context(course, row.get('syllabus'), row.get('kcs'), graphs)
    if bank_item is not None and isinstance(bank_item, dict) and isinstance(bank_item.get('source'), dict) and 'prepared_admission' in bank_item['source']:
        if (not isinstance(qid, str) or not isinstance(part, str) or library is None or ctx is None
                or bank_identity(bank_item['source']) != (course, qid + (':' + part if part else ''))):
            return None
        try:
            reviewed = authenticate_prepared_item(bank_item, library)
            if (any(encoded(row.get(k)) != encoded(reviewed[k]) for k in ('official_qid', 'part', 'syllabus', 'kcs'))
                    or any(encoded(value) != encoded(reviewed.get(key)) for key, value in row.items())):
                return None
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            return None
    elif course in ('P1', 'P2') or pearson_namespace(qid):
        assessed = ial_assessed(qid, part)
        if assessed is None or assessed['course'] != course or ctx is None or library is None:
            return None
        question, scheme = row.get('regions'), row.get('mark_scheme_regions')
        if bank_item is not None:
            if not isinstance(bank_item, dict) or not isinstance(bank_item.get('source'), dict):
                return None
            source = bank_item['source']
            if (source.get('qid') != qid or source.get('part') != part
                    or bank_item.get('kcs') != row.get('kcs')):
                return None
            question, scheme = source.get('extraction_regions'), source.get('mark_scheme_regions')
        try:
            validate_ial_sources(qid, part, course, question, scheme, library)
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            return None
    elif (not isinstance(qid, str) or not re.fullmatch(re.escape(course) + r'_[msw]\d{2}_\d{2}_q\d+', qid)
          or not isinstance(part, str) or ctx is None):
        return None
    return encoded([course, qid, part, *ctx])
