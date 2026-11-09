"""Exact Examinent compilation: literal appendix authority, no solved answers."""
from __future__ import annotations

import copy
import hashlib
import io
import re

import pymupdf
from pypdf import PdfReader

SOURCE = 'asset:legacy-94c51c9bcbba526ad8f64b38'
SHA256 = '90d2c4a2c144714a1369d6775833e429457600f6b74a069c7daf00777159a70f'
_PAPER = re.compile(r'9701_[msw]\d{2}_qp_1[123]')
_ROW = re.compile(r'(?m)^\s*(\d+)\s+(9701_[msw]\d{2}_qp_1[123])\s+(\d+)\s+([ABCD])\s*$')


def _qid(paper, number):
    return paper.replace('_qp_', '_') + '_q' + str(int(number))


def _serialized_rows(raw):
    """Independent PDF engine and line serialization, without spatial grouping."""
    reader = PdfReader(io.BytesIO(raw))
    return [(int(m[1]), _qid(m[2], m[3]), m[4]) for page in reader.pages[699:717]
            for m in _ROW.finditer(page.extract_text())]


def _spatial_rows(doc):
    rows = []
    for n in range(700, 718):
        page = doc[n - 1]; words = page.get_text('words')
        for paper in words:
            if not _PAPER.fullmatch(paper[4]): continue
            column = int(paper[0] >= page.rect.width / 2)
            cells = sorted([w for w in words if abs(w[1] - paper[1]) < 2
                            and int(w[0] >= page.rect.width / 2) == column], key=lambda w: w[0])
            if (len(cells) != 4 or not cells[0][4].isdigit() or cells[1] != paper
                    or not cells[2][4].isdigit() or cells[3][4] not in 'ABCD'):
                raise ValueError('ambiguous compiled spatial key row')
            box = [min(w[0] for w in cells) - .5, min(w[1] for w in cells) - .5,
                   max(w[2] for w in cells) + .5, max(w[3] for w in cells) + .5]
            region = {'source_id': SOURCE, 'source_sha256': SHA256, 'page': n,
                      'box': [round(v / (page.rect.width if i % 2 == 0 else page.rect.height), 8)
                              for i, v in enumerate(box)]}
            rows.append((int(cells[0][4]), _qid(paper[4], cells[2][4]), cells[3][4], region))
    return sorted(rows, key=lambda row: row[0])


def compile_mcq(raw: bytes, fresh: dict) -> dict:
    """Authenticate all rows before selecting ordinary source occurrences."""
    if (fresh.get('course') != '9701' or fresh.get('source') !=
            {'id': SOURCE, 'sha256': SHA256, 'pages': 717}
            or hashlib.sha256(raw).hexdigest() != SHA256):
        raise ValueError('unsupported exact compiled MCQ source')
    with pymupdf.open(stream=raw, filetype='pdf') as doc:
        if len(doc) != 717 or 'Appendix A' not in doc[698].get_text():
            raise ValueError('compiled appendix boundary differs')
        spatial = _spatial_rows(doc)
    serialized = _serialized_rows(raw)
    tuples = [row[:3] for row in spatial]
    if (tuples != serialized or len(tuples) != 1699
            or [r[0] for r in tuples] != list(range(1, 1700))
            or len({r[1] for r in tuples}) != 1699):
        raise ValueError('independent compiled key disagreement or missing row')
    questions = fresh['questions']
    if (len(questions) != 1699 or [(q['label'], q['official_qid']) for q in questions]
            != [(str(sn), qid) for sn, qid, _ in tuples]):
        raise ValueError('compiled question SN/QID differs from native appendix')
    if {r['page'] for r in fresh['review_pages']} != {1, 2, 4}:
        raise ValueError('unassigned compiled public source page')
    owned = {r['page'] for q in questions for r in q['regions'] + q['context_regions']}
    if not set(range(7, 699)) <= owned:
        raise ValueError('incomplete compiled public source inventory')
    items, exclusions = [], []
    for question, (sn, qid, answer, region) in zip(questions, spatial):
        reason = ('public_appendix_contamination' if any(r['page'] >= 699 for r in
                  question['regions'] + question['context_regions']) else
                  'missing_authenticated_shared_response_context' if int(qid.rsplit('_q', 1)[1]) > 30 else None)
        if reason:
            exclusions.append({'occurrence_id': question['id'], 'official_qid': qid,
                               'label': str(sn), 'reason': reason})
            continue
        if not question['regions']:
            raise ValueError('compiled question lacks original public regions')
        row = copy.deepcopy(question)
        row.update(kind='mcq', answer=answer, answer_status='verified_literal_source_key', marks=1,
                   mark_scheme_regions=[region], maximum_authority='literal_source_answer_key',
                   kcs=[], mastery_certified=False)
        items.append(row)
    return {'title': '9701 Examinent Paper 1 2017-2024 TA', 'items': items,
            'occurrence_exclusions': exclusions, 'key_rows': 1699,
            'key_extractors': ['pymupdf_spatial', 'pypdf_serialized'],
            'pages': [{'page': n, 'role': ('front_matter' if n <= 6 else
                       'appendix_heading' if n == 699 else 'private_key' if n >= 700 else 'questions')}
                      for n in range(1, 718)]}


def reuse_verified(items, collection):
    """Preserve the immutable selected canonical resource when its key agrees.

    Occurrence exclusions never enter this canonical quarantine ledger. The root
    must serialize source writers across this selected-release observation.
    """
    new, reused, held = [], [], []
    for row in items:
        qid = row.get('official_qid') or row['id']
        old = collection._items.get(qid) if collection else None
        if old is None:
            new.append(row)
        elif old.get('source_verified') is True and old.get('kind') == 'mcq' and old.get('answer') == row['answer']:
            reused.append({'occurrence_id': row['id'] if row['id'].startswith('occurrence-') else row['source_occurrence_id'],
                           'canonical_id': qid, 'answer': row['answer'], 'existing_release': collection.release})
        else:
            held.append({'id': qid, 'reasons': ['canonical_source_key_conflict']})
    return new, reused, held
