"""Bounded native Edexcel Internal Review Set 1 written-source association.

Public geometry remains the preparation's responsibility. A source whose actual
question inventory exceeds that public preparation is refused, never repaired by
silently discarding the mixed page. Scheme regions retain notes after totals.
"""
from __future__ import annotations

import copy
import hashlib
import re

import pymupdf

_REGISTERED = re.compile(
    r'^Library/Courses/(D1|M1|P[1-4]|S[1-3])/Sources/Library/PMT/Edexcel/'
    r'\1/Edexcel-Set-1/[^/]+\.pdf$')
_PUBLISHER = re.compile(r'Physics\s*And\s*Maths\s*Tutor\.com', re.I)
_MARK = re.compile(r'(?<![A-Za-z])[1-9]?[MAB][0-9](?:ft)?')
_REPORT = re.compile(
    r'\b(?:most|many|some|few|the majority of)\s+candidates\b|'
    r'\bcandidates\s+(?:scored|gained|were|found|had|could|did|used)\b', re.I)
_TOTAL = re.compile(r'\(Total\s+(\d+)\s+marks?\)', re.I)


def compile_written(raw: bytes, fresh: dict, *, source_path: str) -> tuple[str, list, list]:
    """Associate original public questions with complete native private blocks.

    Registered identity and the native numbered sequence jointly select this
    profile. Missing/duplicate anchors hold the file; an absent or disagreeing
    final bracket total holds its item. Printed question totals remain authority.
    """
    registered = _REGISTERED.fullmatch(source_path)
    if not registered or registered[1] != fresh.get('course'):
        raise ValueError('unsupported PMT written source profile')
    digest = hashlib.sha256(raw).hexdigest()
    if fresh['source']['sha256'] != digest:
        raise ValueError('PMT source digest differs')
    source_id = fresh['source']['id']
    with pymupdf.open(stream=raw, filetype='pdf') as doc:
        if len(doc) != fresh['source']['pages']:
            raise ValueError('PMT source page count differs')
        texts = [page.get_text() for page in doc]
        internal_review = bool(texts and any(_PUBLISHER.search(t) for t in texts[:3])
                               and all('Edexcel Internal Review' in t for t in texts))
        # The observed legacy C1 variant uses a native GCE cover and a PMT
        # watermark on every page. It does not establish modern IAL identity.
        cover_lines = {line.strip() for line in texts[0].splitlines()} if texts else set()
        legacy_c1 = (not internal_review and registered[1] == 'P1'
                     and {'6663/01', 'Edexcel GCE', 'Core Mathematics C1',
                          'Advanced Subsidiary'} <= cover_lines
                     and all(_PUBLISHER.search(t) for t in texts))
        if not internal_review and not legacy_c1:
            raise ValueError('unsupported PMT native Internal Review or legacy C1 layout')
        if legacy_c1:
            titles = [line.strip() for line in texts[1].splitlines() if line.strip().startswith('C1 ')]
            if len(titles) != 1:
                raise ValueError('ambiguous PMT legacy C1 printed title')
            title = titles[0]
        else:
            title = texts[0].splitlines()[0].strip()
        printed_course = registered[1].replace('P', 'C') if registered[1].startswith('P') else registered[1]
        if not (title.startswith(registered[1] + ' ') or title.startswith(printed_course + ' ')):
            raise ValueError('PMT printed course title conflict')
        anchors = []
        for n, page in enumerate(doc, 1):
            words = page.get_text('words', sort=True)
            for word in words:
                match = re.fullmatch(r'([1-9]\d{0,2})(\.)?', word[4])
                x, y = word[0] / page.rect.width, word[1] / page.rect.height
                if not (match and .045 < x < .12 and .06 < y < .9):
                    continue
                bare = not match[2]
                # The observed bare label has a part label immediately to its
                # right. Coefficients, numerical answers and mark columns do not.
                if bare and not any(
                        re.fullmatch(r'\([a-z]\)', w[4])
                        and 0 < w[0] - word[2] < page.rect.width * .07
                        and abs(w[1] - word[1]) < 3 for w in words):
                    continue
                anchors.append({'number': int(match[1]), 'page': n, 'top': y, 'x': x, 'bare': bare})
        anchors.sort(key=lambda a: (a['page'], a['top']))
        dotted = [a for a in anchors if not a['bare']]
        reset = next((i for i, a in enumerate(dotted) if i and a['number'] == 1), None)
        if reset is None:
            raise ValueError('missing native PMT marking block reset')
        public, start = dotted[:reset], dotted[reset]
        count = len(public)
        labels = [str(n) for n in range(1, count + 1)]
        if ([str(a['number']) for a in public] != labels
                or [q['label'] for q in fresh['questions']] != labels):
            raise ValueError('incomplete_public_question_inventory')

        def position(a):
            return a['page'], a['top']

        def regions_between(first, end):
            regions = []
            for n in range(first['page'], end['page'] + 1):
                lo = max(.06, first['top'] - .004) if n == first['page'] else .06
                hi = end['top'] - .004 if n == end['page'] else .95
                if n == end['page'] and n != first['page'] and end['top'] < .15:
                    page = doc[n - 1]
                    # A new block near the top leaves only the running header
                    # above it; keep a prefix only when actual content occupies it.
                    bounds = [w[:4] for w in page.get_text('words')]
                    bounds += [i['bbox'] for i in page.get_image_info()]
                    bounds += [tuple(d['rect']) for d in page.get_drawings()]
                    if not any(lo <= b[1] / page.rect.height < hi for b in bounds):
                        continue
                if hi > lo:
                    regions.append({'source_id': source_id, 'source_sha256': digest,
                                    'page': n, 'box': [0, round(lo, 8), 1, round(hi, 8)]})
            return regions

        def text_for(regions):
            parts = []
            for r in regions:
                page = doc[r['page'] - 1]
                x0, y0, x1, y1 = r['box']
                parts.append(page.get_text(clip=pymupdf.Rect(
                    x0 * page.rect.width, y0 * page.rect.height,
                    x1 * page.rect.width, y1 * page.rect.height)))
            return '\n'.join(parts)

        if any(r['page'] <= start['page'] and not (legacy_c1 and r['page'] == 1)
               for r in fresh['review_pages']):
            raise ValueError('incomplete_public_question_inventory: unresolved_public_page')
        before = text_for(regions_between(public[0], start))
        if len(_TOTAL.findall(before)) != count:
            raise ValueError('incomplete_public_question_inventory: printed totals')
        # A public region may not overlap the first private block, even if a
        # preparation has retained the expected number of labels.
        for q in fresh['questions']:
            if not q['regions'] or any(
                    (r['page'], r['box'][3]) > position(start)
                    for r in q['regions'] + q['context_regions']):
                raise ValueError('incomplete_public_question_inventory: private overlap')
        scheme, commentary = [], None
        for anchor in anchors:
            if position(anchor) < position(start):
                continue
            if len(scheme) == count and anchor['number'] == 1:
                if anchor['bare'] or not _REPORT.search(texts[anchor['page'] - 1]):
                    raise ValueError('ambiguous native PMT examiner commentary boundary')
                commentary = anchor
                break
            if (anchor['number'] != len(scheme) + 1
                    or (anchor['bare'] and abs(anchor['x'] - start['x']) > .003)):
                raise ValueError('ambiguous native PMT numbered marking blocks')
            scheme.append(anchor)
        if len(scheme) != count:
            raise ValueError('missing native PMT numbered marking blocks')
        end = commentary if commentary else {'page': len(doc), 'top': .954}
        # No unrecognized question reset may hide in an apparent MS tail.
        pages = [{'page': n, 'role': ('front_matter' if legacy_c1 and n == 1 else
                  'questions' if n < start['page'] else
                  'examiner_comments' if commentary and n >= commentary['page'] else 'mark_scheme')}
                 for n in range(1, len(doc) + 1)]
        items = []
        for index, question in enumerate(fresh['questions']):
            row = copy.deepcopy(question)
            regions = regions_between(scheme[index], scheme[index + 1] if index + 1 < count else end)
            scheme_text = text_for(regions)
            totals = _TOTAL.findall(text_for(row['regions'] + row['context_regions']))
            bracket_totals = re.findall(r'\[(\d+)\]', scheme_text)
            row.update(kind='structured', mark_scheme_regions=regions, scheme_text=scheme_text,
                       maximum_authority='printed_question_total')
            if (len(totals) != 1 or not bracket_totals or not _MARK.search(scheme_text)
                    or int(bracket_totals[-1]) != int(totals[0])):
                row.update(marks=None, hold_reasons=['ambiguous_printed_total_or_scheme_termination'])
            else:
                row['marks'] = int(totals[0])
            items.append(row)
    return title, pages, items
