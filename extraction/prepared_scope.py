"""Offline preparation of small source-bound Pearson IAL assessment groups.

The package is a reproducible proposal, never a teaching/review approval. Verify
by recomputing the descriptor, seed and every rendered byte from Library.
"""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import re
import stat

from tutorlib.prepared_evidence import (
    PROFILE, COURSE_UNITS, SPEC_PATH, SPEC_SHA256, canonical_bytes, canonical_qid,
    digest, part_suffix, reject_reserved, sha, source_identity, validate_region, validate_descriptor,
    required_asset_pages, WHOLE_ASSESSMENT, validate_whole_row,
)


class PendingEvidence(ValueError):
    """A source landmark cannot be established by this conservative profile."""


def _physical(path: Path, *, exists=True) -> Path:
    if '..' in Path(path).parts:
        raise ValueError('unsafe_physical_path: parent traversal not permitted')
    path = Path(os.path.abspath(path))
    for parent in [*reversed(path.parents), path]:
        if parent.is_symlink():
            raise ValueError('unsafe_physical_path: symlink/alias not permitted')
        if parent.exists() and parent.name in ('Library', 'Archive', '.tutor'):
            raise ValueError('unsafe_physical_path: protected resource output/input')
    if exists and not path.exists():
        raise ValueError('missing package/request path')
    return path


def _read_json(path: Path):
    if not path.is_file() or path.is_symlink():
        raise ValueError('unsafe or missing package JSON')
    try:
        def unique(pairs):
            result={}
            for key,value in pairs:
                if key in result: raise ValueError('competing JSON field: '+key)
                result[key]=value
            return result
        return json.loads(path.read_bytes(), object_pairs_hook=unique,
                          parse_constant=lambda value: (_ for _ in ()).throw(ValueError('region_box: nonfinite JSON')))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError('invalid package JSON') from exc


def _cover(doc, exam, role):
    text = ' '.join(doc[0].get_text().split())
    identity = re.search(r'Pearson\s+Edexcel\s+International\s+Advanced\s+(?:Level|Subsidiary\s*/\s*Advanced\s+Level)', text, re.I)
    if role == 'ms' and not identity:
        # Actual modern WFM/WME schemes use these issuer spellings too. The
        # native unit, component, role and session checks below remain required;
        # source_identity separately rejects legacy numbered GCE originals.
        identity = re.search(r'Pearson\s+Edexcel\s+(?:International\s+A\s+Level|IAL|International\s+GCE)\b', text, re.I)
    if not identity:
        raise PendingEvidence('pending_cover_identity: decisive native Pearson IAL cover unavailable')
    codes = set(re.findall(r'\b(?:WMA\d{2}|WFM\d{2}|WME\d{2}|WST\d{2}|WDM\d{2})\b', text))
    if codes != {exam['unit']}:
        raise ValueError('competing_cover_marker: source unit differs or ambiguous')
    unit = re.escape(exam['unit'])
    code_component = re.search(unit + r'\s*/\s*01\b', text)
    if role == 'qp':
        if re.search('Mark Scheme', text, re.I) or not re.search(r'Paper\s+reference', text, re.I) or not code_component:
            raise ValueError('source_role: QP paper reference/role not established')
    elif not re.search(r'Mark\s+Scheme', text, re.I) or not (code_component or re.search(r'Paper\s+01\b', text)):
        raise ValueError('source_role: MS heading/component not established')
    components = set(re.findall(unit + r'\s*/\s*(\d{2})\b', text)) | set(re.findall(r'Paper\s+(\d{2})\b', text))
    if components != {'01'}:
        raise ValueError('source_component: competing component')
    year, month = exam['session'].split('-')
    months={name:f'{i:02d}' for i,name in enumerate(('January','February','March','April','May','June','July','August','September','October','November','December'),1)}
    months['Summer']='06'
    sessions = {(y, months[m]) for m,y in re.findall(r'\b('+'|'.join(months)+r')\s+(20\d{2})\b', text)}
    # Pearson defines the IAL May-June (Summer) series:
    # https://qualifications.pearson.com/en/qualifications/edexcel-international-advanced-levels.html
    # The registered provisional Summer 2023 timetable also lists WFM01 in May.
    # A scheme must independently name June/Summer; October is never equivalent.
    if role == 'qp' and month == '06' and sessions == {(year, '05')}:
        sessions = {(year, '06')}
    if sessions != {(year, month)}:
        raise PendingEvidence('pending_cover_session: date/session requires demonstrated equivalence')
    return {'page': 1, 'text_sha256': sha(text.encode()), 'text': text,
            'unit': exam['unit'], 'component': '01', 'session': exam['session'], 'role': role}


def _paired_covers(qp_doc, ms_doc, qp_exam, ms_exam, *, ms_pages=None):
    """Authenticate native covers, with one bounded undated-QP publisher proof.

    ``ms_pages`` optionally restricts the usable log-witness pages. Callers that
    omit it must include the returned ms_log page in their inspection inventory.
    The requested session is a joint series identity, never a printed QP date.
    """
    if qp_exam != ms_exam:
        raise ValueError('source_pair: edition/session/component mismatch')
    ms_cover = _cover(ms_doc, ms_exam, 'ms')
    try:
        return {'qp': _cover(qp_doc, qp_exam, 'qp'), 'ms': ms_cover}
    except PendingEvidence as exc:
        # _cover has already established issuer, native unit, role and component
        # before this single missing/conflicting-session failure can be raised.
        if not str(exc).startswith('pending_cover_session:'):
            raise
    import unicodedata
    raw_text = qp_doc[0].get_text()
    text = ' '.join(raw_text.split())
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    date_lines = []
    for index, line in enumerate(lines):
        # Actual native QPs print these revision codes directly after the paper
        # ID and Pearson copyright. Exempt that exact ASCII production form,
        # never a short/space-separated date or an incidental chain elsewhere.
        if (index >= 2 and re.fullmatch(r'(?:[A-Z]:(?:1/){2,}|(?:1/){3,}1?)', line)
                and re.fullmatch(r'P\d{5}A', lines[index-2])
                and re.fullmatch(r'©\s*20\d{2}\s+Pearson\s+Education\s+Ltd\.?', lines[index-1])):
            continue
        date_lines.append(line)
    date_text = unicodedata.normalize('NFKC', ' '.join(date_lines))
    date_text = ''.join('-' if unicodedata.category(char) == 'Pd' or char == '−'
                        else '/' if char in '⁄∕' else char for char in date_text)
    # Match full/abbreviated months even next to a year ("Sept2020"). Lowercase
    # "may" in calculator instructions is a verb; numeric/standalone May is not.
    months = r'Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?|Summer|Winter|Spring|Autumn'
    printed_date = (re.search(r'(?<![a-z])(?:' + months + r')(?![a-z])', date_text, re.I)
                    or re.search(r'(?<![a-z])(?:May|MAY)(?![a-z])', date_text)
                    or re.search(r'\bmay\s*(?:20\d{2}|\d{1,2}\b)|\b\d{1,2}\s*may\b', date_text, re.I)
                    or re.search(r'^\s*may\s*$', raw_text, re.I | re.M))
    for candidate in re.finditer(r'(?<!\w)\d{1,4}(?:\s*[/.-]\s*\d{1,4})+(?!\w)', date_text):
        # The actual M1 cover states a physical scalar with explicit SI units.
        # A standalone "9.8" stays ambiguous, as does any additional date.
        if (candidate[0] == '9.8' and re.search(r'\bg\s*=\s*$', date_text[:candidate.start()])
                and re.match(r'\s*m\s+s\s*-\s*2\b', date_text[candidate.end():])):
            continue
        printed_date = True
        break
    if printed_date:
        raise PendingEvidence('pending_cover_session: printed_date prevents undated pair fallback')
    paper_tokens = re.findall(r'\bP\d+A\d*\b', text)
    ids = {token[:7] for token in paper_tokens if re.fullmatch(r'P\d{5}A(?:\d{4})?', token)}
    if len(ids) != 1 or any(not re.fullmatch(r'P\d{5}A(?:\d{4})?', token) for token in paper_tokens):
        raise PendingEvidence('pending_qp_paper_id: one unique native QP paper ID required')
    paper_id = next(iter(ids))
    label = r'Question\s+Paper\s+Log\s+Number'
    number = 1
    log_text = ms_cover['text']
    if not re.search(label, log_text, re.I):
        number = 2
        if len(ms_doc) < 2 or ms_pages is not None and 2 not in ms_pages:
            raise PendingEvidence('pending_pair_log: explicit publisher log witness unavailable')
        log_text = ' '.join(ms_doc[1].get_text().split())
    fields = list(re.finditer(r'(' + label + r')\s*[:#]?\s*(P\d{5}A)\b', log_text, re.I))
    if (len(fields) != 1 or len(re.findall(label, log_text, re.I)) != 1
            or fields[0][2] != paper_id
            or set(re.findall(r'\bP\d+A\d*\b', log_text)) != {paper_id}):
        raise PendingEvidence('pending_pair_log: exact unique Question Paper Log Number required')
    publication_code = None
    if number == 2:
        # This is publisher frontmatter immediately following the authenticated
        # cover, not an arbitrary answer/note page containing a matching number.
        year, month = ms_exam['session'].split('-')
        codes = re.findall(r'Publications?\s+Code\s+(\S+)', log_text, re.I)
        prefix = ms_exam['unit'] + '_01_'
        expected = {prefix + year[2:] + month + '_MS', prefix + 'MS_' + year[2:] + month}
        series_months={name.lower():f'{i:02d}' for i,name in enumerate(
            ('January','February','March','April','May','June','July','August',
             'September','October','November','December'),1)}
        series_months['summer']='06'
        seasons={(y,series_months[season.lower()]) for season,y in re.findall(
            r'\b('+'|'.join(series_months)+r')\s+(20\d{2})\b',log_text,re.I)}
        units=set(re.findall(r'W(?:MA|FM|ME|ST|DM)\d{2}',log_text))
        if (not re.search(r'Edexcel\s+and\s+BTEC\s+Qualifications', log_text, re.I)
                or not re.search(r'copyright\s+©\s*Pearson\s+Education\s+Ltd\.?\s+' + year + r'\b', log_text, re.I)
                or len(codes) != 1 or codes[0] not in expected
                or seasons != {(year, month)} or units != {ms_exam['unit']}):
            raise PendingEvidence('pending_pair_frontmatter: publisher/series/component evidence unavailable')
        publication_code = codes[0]
    qp_cover = {'page': 1, 'text_sha256': sha(text.encode()), 'text': text,
                'unit': qp_exam['unit'], 'component': '01', 'session': qp_exam['session'], 'role': 'qp'}
    field = fields[0]
    qp_cover['joint_series_evidence'] = {
        'kind': 'publisher_question_paper_log', 'qp_date_status': 'no_printed_date',
        'question_paper_log_number': paper_id, 'session': ms_exam['session'],
        'qp': {'role': 'qp', 'page': 1, 'text_sha256': qp_cover['text_sha256'], 'paper_id': paper_id},
        'ms_cover': {'role': 'ms', 'page': 1, 'text_sha256': ms_cover['text_sha256']},
        'ms_log': {'role': 'ms', 'page': number, 'text_sha256': sha(log_text.encode()),
                   'text': log_text, 'label': field[1], 'literal': field[0],
                   'publication_code': publication_code}}
    return {'qp': qp_cover, 'ms': ms_cover}


def _source_issues(doc, pages, exam):
    issues=[]
    for number in pages:
        text=' '.join(doc[number-1].get_text().split())
        publications=re.findall(r'Publications?\s+Code\s+([^ ]+)',text,re.I)
        without=text
        for code in publications:
            without=without.replace(code,'')
            units=set(re.findall(r'W(?:MA|FM|ME|ST|DM)\d{2}',code))
            if units and units != {exam['unit']}:
                issues.append({'type':'publication_code_discrepancy','page':number,
                               'label':'Publications Code','value':code,'expected_unit':exam['unit'],
                               'disposition':'independent_review_required'})
        units=set(re.findall(r'\bW(?:MA|FM|ME|ST|DM)\d{2}\b',without))
        if units-{exam['unit']}:
            raise PendingEvidence('pending_competing_source_identity: contradictory unit outside labelled publication code')
        if units or publications or re.search(r'Paper\s+reference|Mark\s+Scheme\s*\(Results\)',without,re.I):
            sessions={(year,{'January':'01','June':'06','Summer':'06','October':'10'}[season])
                      for season,year in re.findall(r'\b(January|June|Summer|October)\s+(20\d{2})\b',without)}
            if any(year+'-'+month!=exam['session'] for year,month in sessions):
                raise PendingEvidence('pending_competing_source_identity: contradictory session in selected source evidence')
    return issues


def _words(page):
    result=[]
    for word in page.get_text('words', sort=True):
        import pymupdf
        box = pymupdf.Rect(word[:4]) * page.rotation_matrix
        result.append({'text': word[4], 'box': [box.x0/page.rect.width, box.y0/page.rect.height,
                                             box.x1/page.rect.width, box.y1/page.rect.height]})
    return result


def _inside(outer, inner):
    return outer[0] <= inner[0] and outer[1] <= inner[1] and outer[2] >= inner[2] and outer[3] >= inner[3]


def _intersects(a,b):
    return max(a[0],b[0])<min(a[2],b[2]) and max(a[1],b[1])<min(a[3],b[3])


def _part_marker(word):
    match=re.fullmatch(r'(?:[1-9]\d?\.?)?\(([a-z])\)',word['text'])
    return match[1] if match and word['box'][0]<.125 else None


def _region_text(doc, regions):
    return ' '.join(w['text'] for r in regions for w in _words(doc[r['page']-1]) if _inside(r['box'],w['box']))


def _bind_regions(proposed, role, sources, *, containers=None):
    if not isinstance(proposed, list) or not proposed:
        raise ValueError('missing ordered source regions')
    result=[]; previous=(0, -1)
    for raw in proposed:
        if not isinstance(raw, dict): raise ValueError('invalid region')
        if set(raw)-{'role','page','box','source_id','source_sha256'}: raise ValueError('unknown region field')
        r=copy.deepcopy(raw)
        r.setdefault('source_id', sources[role]['asset_id'])
        r.setdefault('source_sha256', sources[role]['sha256'])
        validate_region(r,role,sources)
        order=(r['page'],r['box'][1])
        if order < previous: raise ValueError('unordered source regions')
        previous=order
        if containers is not None and not any(c['page']==r['page'] and _inside(c['box'],r['box']) for c in containers):
            raise ValueError('crop_containment: disclosure outside inspection scope')
        result.append(r)
    return result


def _ms_question_column(words):
    """Locate one positively labelled native question-number table column."""
    columns=[]
    for header in words:
        h=header['box']
        if header['text']!='Number' or not .03<h[0]<.3 or h[1]>.2:
            continue
        if not any(w['text']=='Question' and abs(w['box'][0]-h[0])<.015
                   and 0<=h[1]-w['box'][1]<.035 for w in words):continue
        if not all(any(w['text']==label and w['box'][0]>h[2]
                       and abs(w['box'][1]-h[1])<.04 for w in words)
                   for label in ('Scheme','Marks')):continue
        columns.append(h)
    return columns[0] if len(columns)==1 else None


def _source_layout(doc, role):
    """Find printed boundaries in whole original pages, never request strips."""
    pages=[]
    for index,page in enumerate(doc):
        words=_words(page)
        starts=[]
        if role=='qp':
            for word in words:
                match=re.fullmatch(r'([1-9]\d?)\.(?:\([a-z]\))?',word['text'])
                if match and word['box'][0]<.16:
                    starts.append({'number':int(match[1]),'box':word['box']})
        else:
            # The printed Question/Number column identifies standalone whole-Q
            # rows too. Formula values to its right are not question starts.
            headers=[w for w in words if w['text']=='Number' and w['box'][0]<.17]
            candidates=[]
            if headers and any(w['text']=='Question' and w['box'][0]<.17 for w in words) and any(w['text']=='Scheme' for w in words):
                bottom=min(w['box'][3] for w in headers)
                candidates=[w for w in words if w['box'][0]<.125 and w['box'][1]>=bottom-.002
                            and re.fullmatch(r'[1-9]\d?\.?(?:\([a-z]\))?',w['text'])]
            gutter=candidates[0]['box'][0] if candidates else None
            for word in words:
                compact=re.fullmatch(r'([1-9]\d?)\.?\([a-z]\)',word['text'])
                number=re.fullmatch(r'([1-9]\d?)\.?',word['text'])
                aligned=word in candidates and abs(word['box'][0]-gutter)<.006
                followed_by_part=number and word['box'][0]<.125 and any(
                    _part_marker(w) and w['box'][0]>word['box'][0]
                    and abs(w['box'][1]-word['box'][1])<.012 for w in words)
                if word['box'][0]<.125 and (compact or number and (aligned or followed_by_part)):
                    starts.append({'number':int((compact or number)[1]),'box':word['box']})
            if not starts:
                # New geometry variant only: infer the number column from a
                # stacked, top-of-table Question/Number heading. Keep existing
                # accepted layout descriptors byte-for-byte unchanged.
                columns=[]
                for header in words:
                    if header['text']!='Number' or not .03<header['box'][0]<.3 or header['box'][1]>.2:
                        continue
                    h=header['box']
                    if not any(w['text']=='Question' and abs(w['box'][0]-h[0])<.015
                               and 0<=h[1]-w['box'][1]<.035 for w in words):continue
                    if not all(any(w['text']==label and w['box'][0]>h[2]
                                   and abs(w['box'][1]-h[1])<.04 for w in words)
                               for label in ('Scheme','Marks')):continue
                    columns.append(h)
                if len(columns)==1:
                    h=columns[0]
                    notes=[w['box'][1] for w in words if w['text'] in ('Notes','Notes:') and w['box'][0]<.3]
                    for word in words:
                        b=word['box'];match=re.fullmatch(r'([1-9]\d?)\.?(?:\([a-z]\))?',word['text'])
                        if (match and h[0]<=b[0] and b[2]<=h[2]+.006
                                and (b[1]+b[3])/2>h[3]
                                and (not notes or b[1]<min(notes))):
                            starts.append({'number':int(match[1]),'box':b})
            column=_ms_question_column(words)
            if column:
                # Equality/arithmetic printed inside the number gutter is a
                # formula, rather than a standalone question-number row.
                starts=[row for row in starts if not any(
                    w['text'] in ('=','+','−','-','×','÷')
                    and column[0]<=w['box'][0]<=column[2]+.006
                    and abs(w['box'][1]-row['box'][1])<.004 for w in words)]
                # A compact nested part label is still a row of this question.
                # Its complete literal stays in words, alongside every note.
                for word in words:
                    b=word['box']
                    match=re.fullmatch(r'([1-9]\d?)\.?\([a-z]\)\([ivx]+\)',word['text'])
                    if (match and column[0]-.002<=b[0]<=column[2]
                            and (b[1]+b[3])/2>column[3]):
                        starts.append({'number':int(match[1]),'box':b})
                starts.sort(key=lambda row:(row['box'][1],row['box'][0]))
        pages.append({'page':index+1,'words':words,'text':' '.join(w['text'] for w in words),'starts':starts})
    if role=='ms':
        previous=None
        for page in pages:
            column=_ms_question_column(page['words'])
            grouped=[]
            page_numbers={row['number'] for row in page['starts']}
            for row in page['starts']:
                b=row['box']
                authenticated=bool(column and column[0]-.002<=b[0]<=column[2]
                                   and (b[1]+b[3])/2>column[3])
                if not (previous and previous[0]==row['number'] and previous[1] and authenticated
                        and (grouped or len(page_numbers)==1)):
                    grouped.append(row)
                previous=(row['number'],authenticated)
            page['starts']=grouped
    return pages


def _covers_page(regions, page):
    boxes=[r['box'] for r in regions if r['page']==page]
    edges=sorted({0,1}|{x for box in boxes for x in (box[0],box[2])})
    for left,right in zip(edges,edges[1:]):
        intervals=sorted((b[1],b[3]) for b in boxes if b[0]<=left and b[2]>=right)
        end=0
        for low,high in intervals:
            if low>end: return False
            end=max(end,high)
        if end<1: return False
    return True


def _whole_question_scope(q, layouts, sources):
    n=q['number']
    qp=layouts['qp']; ms=layouts['ms']
    starts=[p for p in qp if any(s['number']==n for s in p['starts'])]
    if len(starts)!=1:
        raise PendingEvidence('pending_question_start: unique original question start unavailable')
    first=starts[0]['page']
    last=None
    for page in qp[first-1:]:
        if page['starts'] and (page['page']!=first or len(page['starts'])!=1):
            raise PendingEvidence('pending_whole_question_boundary: shared-page or competing question start')
        if page['page']!=first and not re.search(rf'Question\s+{n}\s+continued\b',page['text'],re.I):
            raise PendingEvidence('pending_question_continuation: original continuation not established')
        totals=list(re.finditer(r'\(Total\s+(?:for\s+Question\s+(\d+)\s+is\s+)?(\d+)\s+marks\)',page['text'],re.I))
        if totals:
            if len(totals)!=1 or totals[0][1] is not None and int(totals[0][1])!=n:
                raise PendingEvidence('pending_question_terminator: competing original total')
            last=page['page']
            break
    if last is None:
        raise PendingEvidence('pending_question_terminator: original whole-question end unavailable')
    scheme_starts=[(p,s) for p in ms for s in p['starts'] if s['number']==n]
    if len(scheme_starts)!=1:
        raise PendingEvidence('pending_scheme_row: unique original scheme question row unavailable')
    scheme_first=scheme_starts[0][0]['page']
    if len(ms[scheme_first-1]['starts'])!=1:
        raise PendingEvidence('pending_whole_question_boundary: shared-page scheme rows require separate proof')
    next_page=next((p for p in ms[scheme_first:] if p['starts']),None)
    scheme_last=next_page['page']-1 if next_page else len(ms)
    result={}
    for role,pages in [('qp',range(first,last+1)),('ms',range(scheme_first,scheme_last+1))]:
        proposed=q['question_regions' if role=='qp' else 'scheme_regions']
        if set(r['page'] for r in proposed)!=set(pages) or any(not _covers_page(proposed,p) for p in pages):
            raise PendingEvidence('pending_whole_question_scope: inspection must preserve the complete original block, including its terminator/notes')
        result[role]=[{'role':role,'source_id':sources[role]['asset_id'],'source_sha256':sources[role]['sha256'],
                       'page':p,'box':[0,0,1,1]} for p in pages]
    result['scheme_rows']=[{'number':n,'page':scheme_first}]
    result['scheme_boundary']={'kind':'next_question','page':next_page['page'],
                               'numbers':[s['number'] for s in next_page['starts']]} if next_page else {'kind':'document_end','page':len(ms)}
    return result


def _question_witness(q, docs, sources, scope):
    n=q['number']; regions=scope['qp']; ms=scope['ms']
    pages=list(dict.fromkeys(r['page'] for r in regions))
    if pages != list(range(pages[0],pages[-1]+1)):
        raise PendingEvidence('pending_question_continuation: noncontiguous inspection')
    texts=[_region_text(docs['qp'],[r for r in regions if r['page']==p]) for p in pages]
    starts=[]
    for r in regions:
        for w in _words(docs['qp'][r['page']-1]):
            match=re.fullmatch(r'([1-9]\d?)\.(?:\([a-z]\))?',w['text'])
            if _inside(r['box'],w['box']) and w['box'][0] < .16 and match:
                starts.append((r['page'],int(match[1])))
    if starts != [(pages[0],n)]:
        raise PendingEvidence('pending_question_start: missing or competing printed question landmark')
    total=re.search(rf'\(Total\s+(?:for\s+Question\s+{n}\s+is\s+)?(\d+)\s+marks\)',texts[-1],re.I)
    if not total:
        raise PendingEvidence('pending_question_terminator: complete scope not established')
    for text in texts[1:]:
        if not re.search(rf'Question\s+{n}\s+continued\b',text,re.I):
            raise PendingEvidence('pending_question_continuation: missing continuation landmark')
    scheme_text=_region_text(docs['ms'],ms)
    whole=[p['part'] for p in q['parts']]==['']
    explicit=q.get('assessment_mode')==WHOLE_ASSESSMENT
    scheme_starts=scope['scheme_rows']
    if scheme_starts != [{'number':n,'page':ms[0]['page']}]:
        raise PendingEvidence('pending_scheme_row: question row/notes unavailable')
    qp_parts=[]; ms_parts=[]
    for role, rs, dest in [('qp',regions,qp_parts),('ms',ms,ms_parts)]:
        for r in rs:
            for w in _words(docs[role][r['page']-1]):
                label=_part_marker(w)
                if _inside(r['box'],w['box']) and label:
                    if label not in dest: dest.append(label)
    parts=[p['part'] for p in q['parts']]
    if not explicit and not (whole and not qp_parts and not ms_parts) and (parts != qp_parts or parts != ms_parts):
        raise PendingEvidence('pending_part_inventory: declared parts do not match original QP/MS inventory')
    qp_total=total[1]
    if not re.search(rf'\bTotal\s+{qp_total}\b|\({qp_total}\s+marks\)',scheme_text):
        # New bare labels need the same located source proof as the whole
        # assessment. Never manufacture parentheses around an incidental phrase.
        located=_located_whole_total(q, {'ms':_source_layout(docs['ms'],'ms')}, sources, 'ms')
        if located['value']!=int(qp_total):
            raise PendingEvidence('pending_scheme_total: original question/scheme totals do not agree')
    for p in q['parts']:
        if whole:
            if p['question_media_regions']!=regions or p['scheme_media_regions']!=q.get('private_guidance_regions',[])+ms:
                raise PendingEvidence('pending_whole_assessment_scope: whole disclosure must preserve its complete inspected scope')
            continue
        for role,field,minimum in [('qp','question_media_regions',1),('ms','scheme_media_regions',2)]:
            count=sum(1 for r in p[field] for w in _words(docs[role][r['page']-1])
                      if _inside(r['box'],w['box']) and _part_marker(w)==p['part'])
            if count < minimum:
                raise PendingEvidence('pending_part_crop_witness: public task or private table/notes landmark missing')
        # A label-free crop must not pick up another public assessed paragraph.
        # Printed mark allocations close the paragraph, leaving intervening
        # shared narrative available as context (semantic applicability is review).
        for r in regions:
            words=_words(docs['qp'][r['page']-1])
            primary=[w for w in words if _inside(r['box'],w['box']) and _part_marker(w)]
            for index,marker in enumerate(primary):
                if _part_marker(marker)==p['part']: continue
                stop=primary[index+1]['box'][1] if index+1<len(primary) else 1
                allocations=[w for w in words if w['box'][0]>.75 and marker['box'][1]<w['box'][1]<stop and re.fullmatch(r'\([1-9]\d?\)',w['text'])]
                if not allocations:
                    raise PendingEvidence('pending_part_boundary: printed mark allocation unavailable')
                band=[0,marker['box'][1],1,max(w['box'][3] for w in allocations)]
                if any(c['page']==r['page'] and _intersects(c['box'],band) for c in p['question_media_regions']):
                    raise ValueError('sibling_disclosure: public crop overlaps another assessed paragraph')
    return {'start': {'page':pages[0], 'number':n}, 'continuations':pages[1:],
            'terminator':{'page':pages[-1], 'number':n,'label':total[0]}, 'qp_parts':qp_parts, 'ms_parts':ms_parts,
            'scheme_rows':scheme_starts,'scheme_text_sha256':sha(scheme_text.encode()),
            'whole_question_regions':{'qp':regions,'ms':ms},'scheme_boundary':scope['scheme_boundary']}


def _integer_ms_total(words):
    """Prove a final numeric total cell from its own printed MS allocations."""
    if not _ms_question_column(words):return []
    headings=[w for w in words if w['text']=='Marks' and w['box'][0]>.7 and w['box'][1]<.2]
    notes=[w['box'][1] for w in words if w['text'] in ('Notes','Notes:') and w['box'][0]<.7]
    if len(headings)!=1 or not notes:return []
    h=headings[0]['box']; stop=min(notes)
    centre=lambda w:(w['box'][1]+w['box'][3])/2
    table=[w for w in words if centre(w)>h[3] and centre(w)<stop]
    cell_left=h[2]-.02
    candidates=[w for w in table if w['box'][0]>=cell_left and re.fullmatch(r'[1-9]\d*',w['text'])]
    if len(candidates)!=1:return []
    total=candidates[0]; y=centre(total)
    cell_line=[w for w in table if w['box'][0]>=cell_left and abs(centre(w)-y)<.004]
    if cell_line!=[total]:return []
    marks=[w for w in table if w['box'][0]>=h[0]-.05 and w is not total]
    allocations=[w for w in marks if re.fullmatch(r'\([1-9]\d*\)',w['text'])]
    codes=[w for w in marks if re.fullmatch(r'(?:d?M|D?M|A|B)[1-9]\d*',w['text'])]
    # An unsupported scoring annotation cannot disappear from either the sum
    # or the final-cell boundary. Its scoring semantics remain unresolved.
    if any(w not in codes and re.match(r'(?:(?:dep|d)?[MAB]|SC)\d',w['text'],re.I)
           for w in marks):return []
    if any(centre(w)>y+.004 for w in allocations+codes):return []
    if any(w not in codes for w in marks if abs(centre(w)-y)<.004):return []
    if allocations:
        # An OR may repeat the same allocation. Without a part-aware branch
        # proof, adding these cells would double-count an alternative method.
        if any(re.fullmatch(r'OR:?',w['text'],re.I) for w in table):return []
        proved=sum(int(w['text'][1:-1]) for w in allocations)
    else:
        # Some early tables put an alternative for the final part immediately
        # above the total. Only an equal-mark suffix alternative is separable.
        alternatives=[w for w in table if re.fullmatch(r'OR:?',w['text'],re.I) and w['box'][0]<.7]
        base=codes
        if alternatives:
            if len(alternatives)!=1:return []
            alt=alternatives[0]
            base=[w for w in codes if w['box'][3]<alt['box'][1]-.002]
            suffix=[w for w in codes if w not in base]
            parts=[w for w in table if w['box'][0]<.125
                   and re.fullmatch(r'(?:[1-9]\d?\.?)?\((?:[a-z]|[ivx]+)\)',w['text'])]
            before=[w for w in parts if w['box'][3]<alt['box'][1]]
            if (len(before)<2 or any(w['box'][1]>=alt['box'][1] for w in parts)
                    or not suffix):return []
            last=max(before,key=centre)
            last_codes=[w for w in base if centre(w)>=centre(last)-.012]
            score=lambda rows:sum(int(re.search(r'\d+',w['text'])[0]) for w in rows)
            if not last_codes or score(last_codes)!=score(suffix):return []
        if not base:return []
        proved=sum(int(re.search(r'\d+',w['text'])[0]) for w in base)
    return [total] if proved==int(total['text']) else []


def _additional_ms_whole_totals(q, layouts):
    """Locate two literal total forms only after an independent assessed-row proof.

    This is deliberately a same-page table proof. Intervening Notes must be
    followed by another complete assessed row; note references cannot reopen it.
    Printed part allocations establish the maximum, without alternative/code
    arithmetic or relying on the public question's total.
    """
    found=[]; assessed_pages=[]
    centre=lambda w:(w['box'][1]+w['box'][3])/2
    for r in q['scheme_regions']:
        words=[w for w in layouts['ms'][r['page']-1]['words'] if _inside(r['box'],w['box'])]
        column=_ms_question_column(words)
        if not column:
            if any((w['box'][0]>.7 and w['box'][1]>.05 and (
                        re.match(r'(?:(?:dep|d)?[MAB]|SC)\d',w['text'],re.I)
                        or re.fullmatch(r'(?:Total|\(?\[?[1-9]\d*[)\]]?)',w['text'],re.I)))
                   or (w['box'][0]<.17 and re.fullmatch(r'(?:[1-9]\d?\.?)?\([a-zivx]+\)',w['text']))
                   for w in words):assessed_pages.append(r['page'])
            continue
        assessed_pages.append(r['page'])
        headings=[w for w in words if w['text']=='Marks' and w['box'][0]>.7 and w['box'][1]<.2]
        if len(headings)!=1:continue
        h=headings[0]['box']; left=h[0]-.05
        body=[w for w in words if w['box'][1]>max(h[3],column[3])]
        # Retain the full exact native label, including both separately extracted
        # glyph words. A submatch inside a bracketed label is never authority.
        text=' '.join(w['text'] for w in body);offsets=[];cursor=0
        for w in body:
            offsets.append((cursor,cursor+len(w['text']),w));cursor+=len(w['text'])+1
        candidates=[]
        for match in re.finditer(r'\[[1-9]\d*\s+marks\]|\bTotal\s+[1-9]\d*\b',text,re.I):
            tokens=[w for start,end,w in offsets if start<match.end() and end>match.start()]
            if ' '.join(w['text'] for w in tokens)!=match[0] or len(tokens)!=2:continue
            y=centre(tokens[0])
            line=[w for w in body if w['box'][0]>=.7 and abs(centre(w)-y)<.004]
            if (line!=tokens or any(w['box'][0]<left for w in tokens)
                    or abs(tokens[0]['box'][1]-tokens[1]['box'][1])>.004
                    or not h[0]-.02<=tokens[-1]['box'][0]<=h[2]+.02):continue
            candidates.append((match[0],tokens))
        # Even a different/unsupported maximum in the same total column must
        # not disappear when selecting a candidate.
        if len(candidates)!=1:continue
        label,tokens=candidates[0]; top=min(w['box'][1] for w in tokens)
        notes=[w for w in body if w['text'] in ('Notes','Notes:') and w['box'][0]<.7]
        end=min((w['box'][1] for w in notes if w['box'][1]>top),default=1)
        # Notes may contain harmless part/code references. They cannot hide
        # additional Marks-column assessment from the whole maximum's closure.
        remaining=[w for w in body if w['box'][1]>=end and w['box'][0]>=left]
        if any(re.match(r'(?:(?:dep|d)?[MAB]|SC)\d',w['text'],re.I)
               or re.fullmatch(r'(?:Total|\(?\[?[1-9]\d*[)\]]?)',w['text'],re.I)
               for w in remaining):continue
        table=[w for w in body if w['box'][1]<end]
        gutter=[w for w in table if column[0]-.01<=w['box'][0]<=column[2]+.02]
        rows=[];invalid=False
        for w in gutter:
            match=re.fullmatch(r'(?:([1-9]\d?)\.?)?\(([a-z]|[ivx]+)\)',w['text'])
            if not match:
                # Unknown labels/numbered rows are unresolved, even if their
                # marks happen to sum to the printed whole label.
                if '(' in w['text'] or re.fullmatch(r'[1-9]\d*\.?',w['text']):invalid=True
                continue
            rows.append((w,match[1],match[2]))
        rows.sort(key=lambda row:centre(row[0]))
        parts=[row[2] for row in rows]
        roman=['i','ii','iii','iv','v','vi','vii','viii','ix','x']
        if (invalid or not rows or rows[0][1]!=str(q['number'])
                or any(number is not None for _,number,_ in rows[1:])
                or parts!=list('abcdefghijklmnopqrstuvwxyz')[:len(parts)] and parts!=roman[:len(parts)]
                or any(w['box'][3]>=top for w,_,_ in rows)):continue
        marks=[w for w in table if w['box'][0]>=left and w not in tokens]
        allocations=[w for w in marks if re.fullmatch(r'\([1-9]\d*\)',w['text'])]
        codes=[w for w in marks if re.fullmatch(r'(?:(?:M|A|B)[1-9]\d*)+',w['text'])]
        alternatives=[w for w in table if re.fullmatch(r'OR:?',w['text'],re.I)
                      and (w['text'].endswith(':') or not any(
                          v is not w and column[2]+.02<v['box'][0]<left
                          and abs(centre(v)-centre(w))<.004 for v in table))]
        if (len(allocations)!=len(rows) or any(w not in allocations+codes for w in marks)
                or any(centre(w)<rows[0][0]['box'][1] for w in marks)
                or any(w['box'][3]>=top for w in marks)
                or alternatives):continue
        for index,(row,_,_) in enumerate(rows):
            stop=rows[index+1][0]['box'][1] if index+1<len(rows) else top
            owned=[w for w in allocations if row['box'][1]<=centre(w)<stop]
            scoring=[w for w in codes if row['box'][1]<=centre(w)<stop]
            scheme=[w for w in table if column[2]+.02<w['box'][0]<left-.02
                    and row['box'][1]<=centre(w)<stop and w not in notes]
            if (len(owned)!=1 or not scoring or not scheme
                    or any(w['box'][3]>owned[0]['box'][1]+.004 for w in scoring)):
                invalid=True;break
        if invalid or any(not any(row['box'][1]>note['box'][3] for row,_,_ in rows)
                          for note in notes if note['box'][1]<top):continue
        value=int(re.search(r'[1-9]\d*',label)[0])
        if sum(int(w['text'][1:-1]) for w in allocations)!=value:continue
        box=[min(w['box'][0] for w in tokens),min(w['box'][1] for w in tokens),
             max(w['box'][2] for w in tokens),max(w['box'][3] for w in tokens)]
        found.append({'kind':'question_total','value':value,'label':label,'region':{**r,'box':box}})
    # No unsupported continuation table may be omitted from this narrow proof.
    return found if len(assessed_pages)==1 else []


def _located_whole_total(q, layouts, sources, role):
    from tutorlib.prepared_evidence import _whole_total
    regions=q['question_regions' if role=='qp' else 'scheme_regions']
    found=[]
    for r in regions:
        words=layouts[role][r['page']-1]['words']
        if role=='ms':
            for word in _integer_ms_total(words):
                found.append({'kind':'question_total','value':int(word['text']),'label':word['text'],
                              'region':{**r,'box':word['box']}})
        text=' '.join(w['text'] for w in words); offsets=[];cursor=0
        for word in words:
            offsets.append((cursor,cursor+len(word['text']),word));cursor+=len(word['text'])+1
        pattern=(r'\(Total\s+(?:for\s+Question\s+\d+\s+is\s+)?\d+\s+marks\)' if role=='qp'
                 else r'\((?:(?:Total\s+)?for\s+Question\s+\d+\s+is\s+)?\d+\s+marks\)')
        if role=='ms':pattern += r'|\bTotal\s+[1-9]\d*\b|\b[1-9]\d*\s+marks\b'
        for match in re.finditer(pattern,text,re.I):
            tokens=[w for start,end,w in offsets if start<match.end() and end>match.start()]
            box=[min(w['box'][0] for w in tokens),min(w['box'][1] for w in tokens),
                 max(w['box'][2] for w in tokens),max(w['box'][3] for w in tokens)]
            if role=='ms':
                # Question totals carry "marks" in the right-hand total column.
                # Unlabelled (2) allocations and repeated note prose cannot own it.
                notes=[w['box'][1] for w in words if _part_marker(w) and w['box'][0]<.09]
                bare=re.fullmatch(r'[1-9]\d*\s+marks',match[0],re.I)
                if box[0]<.7 or not bare and notes and box[1]>=min(notes):continue
                if bare or re.fullmatch(r'Total\s+[1-9]\d*',match[0],re.I):
                    # Literal totals are a distinct positive table proof: one
                    # line, in the authenticated Marks column, before standalone
                    # Notes prose. Header-side Notes cells are not note sections.
                    headings=[w for w in words if w['text']=='Marks' and w['box'][0]>.7 and w['box'][1]<.2]
                    sections=[w['box'][1] for w in words if w['text'] in ('Notes','Notes:') and w['box'][0]<(.7 if bare else .3)]
                    centre=(tokens[0]['box'][1]+tokens[0]['box'][3])/2
                    left=.7 if bare else box[0]-.002
                    right_line=[w for w in words if w['box'][0]>=left
                                and abs((w['box'][1]+w['box'][3])/2-centre)<.004]
                    if (right_line!=tokens or len(tokens)!=2 or abs(tokens[0]['box'][1]-tokens[1]['box'][1])>.004
                            or len(headings)!=1 or not headings[0]['box'][0]-.02<=tokens[-1]['box'][0]<=headings[0]['box'][2]+.02
                            or box[1]<=headings[0]['box'][3]
                            or sections and box[3]>=min(sections)
                            or bare and (not _ms_question_column(words) or ' '.join(w['text'] for w in tokens)!=match[0])):
                        continue
            value=_whole_total(match[0],role,q['number'])
            found.append({'kind':'question_total','value':value,'label':match[0],
                          'region':{**r,'box':box}})
    if not found and role=='ms':
        found=_additional_ms_whole_totals(q,layouts)
    if not found and role=='ms':
        from native_ms_maximum_witnesses import located_native_ms_maxima
        from native_closed_totals import located_native_closed_totals
        found=located_native_ms_maxima(q,layouts,sources) or located_native_closed_totals(q,layouts,sources)
    if len(found)!=1 or found[0]['value']<=0:
        raise PendingEvidence('pending_whole_question_total: unique independent '+role+' question maximum unavailable')
    return found[0]


def _whole_assessment(q, layouts, sources):
    totals={role:_located_whole_total(q,layouts,sources,role) for role in ('qp','ms')}
    if totals['qp']['value']!=totals['ms']['value']:
        raise PendingEvidence('pending_whole_question_total: independent original QP/MS question maxima differ')
    markers={}
    for role,field in [('qp','question_regions'),('ms','scheme_regions')]:
        markers[role]=[{'text':w['text'],'region':{**r,'box':w['box']}}
                       for r in q[field] for w in layouts[role][r['page']-1]['words']
                       if w['box'][0]<.25 and re.fullmatch(r'(?:[1-9]\d?\.?)?\((?:[a-z]|[ivx]+)\)',w['text'])]
    return {'max_marks':totals['qp']['value'],'totals':totals,'printed_markers':markers}


def _private_guidance(regions, layout, docs):
    """Bind complete introductory sections, including physical continuations."""
    first=min(p['page'] for p in layout if p['starts'])
    heading_pattern=(r'General Marking Guidance|General Instructions for Marking|'
                     r'General Principles for(?: Pure Mathematics)? Marking|Use of a formula|Exact answers')
    sections=[];page_words={};page_furniture={}
    for page in layout[:first-1]:
        words=[w for w in page['words'] if w['text']!='PMT'
               and not (w['text'].isdigit() and (w['box'][1]<.06 or w['box'][1]>.95))]
        page_words[page['page']]=words
        lines=[]
        for word in words:
            if not lines or abs(lines[-1][0]['box'][1]-word['box'][1])>.006:lines.append([])
            lines[-1].append(word)
        for line in lines:
            text=' '.join(w['text'] for w in sorted(line,key=lambda w:w['box'][0]))
            if re.fullmatch(r'PEARSON EDEXCEL IAL MATHEMATICS',text,re.I) and line[0]['box'][1]<.16:
                page_furniture.setdefault(page['page'],set()).update((w['text'],tuple(w['box'])) for w in line)
            if re.fullmatch(heading_pattern,text,re.I):
                box=[min(w['box'][0] for w in line),min(w['box'][1] for w in line),
                     max(w['box'][2] for w in line),max(w['box'][3] for w in line)]
                sections.append({'heading':text,'region':{**regions[0],'page':page['page'],'box':box},'content':[]})
    for page,words in page_words.items():
        for word in words:
            y=word['box'][1]
            # Only positively recognized edition furniture is exempt. Prose
            # above even an early next heading still belongs to the prior rule.
            if (word['text'],tuple(word['box'])) in page_furniture.get(page,set()):continue
            owner=next((s for s in reversed(sections) if (s['region']['page'],s['region']['box'][1])<=(page,y+.003)),None)
            if owner:owner['content'].append((page,word))
        # A figure may have no extractable words. Include all non-text paint
        # bounds (paths, images and shading), conservatively, in section ownership.
        import pymupdf
        physical=docs['ms'][page-1]
        for kind,bounds in physical.get_bboxlog():
            if kind in ('fill-text','stroke-text','ignore-text'):continue
            rect=(pymupdf.Rect(bounds)*physical.rotation_matrix)&physical.rect
            if rect.is_empty:continue
            box=[rect.x0/physical.rect.width,rect.y0/physical.rect.height,
                 rect.x1/physical.rect.width,rect.y1/physical.rect.height]
            owner=next((s for s in reversed(sections) if (s['region']['page'],s['region']['box'][1])<=(page,box[1])),None)
            if owner:owner['content'].append((page,{'box':box,'graphic':True}))
    def covered(page,top,bottom):
        end=top
        for low,high in sorted((r['box'][1],r['box'][3]) for r in regions if r['page']==page):
            if high<=end:continue
            if low>end+1e-9:return False
            end=max(end,high)
        return end>=bottom-1e-9
    selected=[]
    for r in regions:
        if r['page']>=first or r['box'][0]!=0 or r['box'][2]!=1:
            raise PendingEvidence('pending_private_guidance: only complete introductory same-MS sections are allowed')
        words=page_words[r['page']]
        if any(_intersects(r['box'],w['box']) and not _inside(r['box'],w['box']) for w in words):
            raise PendingEvidence('pending_private_guidance: cropped printed word/context')
        touched=[s for s in sections if any(page==r['page'] and _inside(r['box'],word['box']) for page,word in s['content'])]
        if not touched:
            raise PendingEvidence('pending_private_guidance: readable applicable introductory guidance heading required')
        selected.extend(touched)
    for index,s in enumerate(sections):
        if s not in selected:continue
        region=s['region'];following=sections[index+1]['region'] if index+1<len(sections) else None
        last=(following['page'] if following['box'][1]>=.16 or any(page==following['page'] for page,content in s['content'])
              else following['page']-1) if following else first-1
        for page,content in s['content']:
            if content.get('graphic') and not any(r['page']==page and _inside(r['box'],content['box']) for r in regions):
                raise PendingEvidence('pending_private_guidance: complete visible graphic context required')
        for page in range(region['page'],last+1):
            top=region['box'][1] if page==region['page'] else 0
            bottom=following['box'][1] if following and following['page']==page else 1
            if not covered(page,top,bottom):
                raise PendingEvidence('pending_private_guidance: complete heading/definitions/qualifiers/continuation required')
        if not any(_contained_guidance(region,r) for r in regions):
            raise PendingEvidence('pending_private_guidance: section heading omitted')
    witnesses=[]
    for r in regions:
        touched=[s for s in sections if any(page==r['page'] and _inside(r['box'],word['box']) for page,word in s['content'])]
        text=_region_text(docs['ms'],[r])
        witnesses.append({'region':r,'headings':[{'heading':s['heading'],'region':s['region']} for s in touched],
                          'text_sha256':sha(text.encode())})
    row=min(layout[first-1]['starts'],key=lambda row:row['box'][1])
    if row['number']!=1:raise PendingEvidence('pending_private_guidance: first authenticated assessment row must be question 1')
    boundaries=[]
    for index,section in enumerate(sections):
        if section in selected and index+1<len(sections):
            following=sections[index+1]
            boundaries.append({'heading':following['heading'],'region':following['region']})
    return {'first_question_page':first,
            'first_question_row':{'number':1,'region':{**regions[0],'page':first,'box':row['box']}},
            'boundary_headings':boundaries,'regions':witnesses}


def _contained_guidance(inner,outer):
    return inner['page']==outer['page'] and _inside(outer['box'],inner['box'])


def _occurrence(value,library, occurrence_roots=None):
    # An unproven topical relationship stays separate; never mint a native ID
    # from a compiled printed label, a COMPLETE marker, or editable metadata.
    if value is None: return []
    if not isinstance(value,dict) or set(value) != {'bundle','complete_sha256','id'}:
        raise ValueError('occurrence: malformed optional witness')
    if not isinstance(value.get('bundle'),str) or not Path(value['bundle']).is_absolute() or '..' in Path(value['bundle']).parts:
        raise ValueError('occurrence: absolute physical bundle path required')
    root=_physical(Path((occurrence_roots or {}).get(value['bundle'], value['bundle'])))
    if not root.is_absolute() or not digest(value['complete_sha256']):
        raise ValueError('occurrence: invalid bundle pin')
    from topical_fastpath import verify_bundle
    verify_bundle(root)
    bundle=_read_json(root/'bundle.json')
    if sha((root/'COMPLETE').read_bytes()) != value['complete_sha256']:
        raise ValueError('occurrence: stale bundle')
    matches=[q for q in bundle['questions'] if q.get('id')==value['id']]
    if len(matches)!=1: raise ValueError('occurrence: unknown original occurrence ID')
    source=bundle['source']
    identifier=source.get('id')
    if not isinstance(identifier,str) or not identifier.startswith('asset:'):
        raise ValueError('occurrence: compiled original source pin mismatch')
    data=library.read(identifier)
    if sha(data)!=source.get('sha256'): raise ValueError('occurrence: compiled original source pin mismatch')
    import pymupdf
    with pymupdf.open(stream=data,filetype='pdf') as doc:
        if len(doc)!=source.get('pages'): raise ValueError('occurrence: original page count mismatch')
    regions=matches[0]['regions']; context=matches[0]['context_regions']
    return [{'status':'pending_identity_join', 'original_occurrence_id':value['id'],
             'bundle_complete_sha256':value['complete_sha256'], 'source':bundle['source'],
             'regions':regions,'context_regions':context,
             'inspection_pages':sorted({1}|{r['page'] for r in regions+context})}]


def _compute(request, library, graph_sha256, occurrence_roots=None):
    import pymupdf
    if not digest(graph_sha256): raise ValueError('invalid graph_sha256')
    if not isinstance(request,dict) or not isinstance(request.get('course'),str) or request['course'] not in COURSE_UNITS:
        raise ValueError('unsupported native course')
    if set(request)-{'course','sources','questions'}: raise ValueError('unknown request field')
    course=request['course']; raw_sources=request.get('sources')
    if not isinstance(raw_sources,dict) or not {'qp','ms'} <= set(raw_sources) or set(raw_sources)-{'qp','ms','reference'}:
        raise ValueError('source_role: QP/MS originals required')
    spec_ids=['asset:'+key for key,value in library.records().items() if value['path']==SPEC_PATH]
    if len(spec_ids)!=1: raise ValueError('specification stable source ID unavailable')
    mapping={'asset_id':spec_ids[0],'path':SPEC_PATH,'sha256':SPEC_SHA256,'page':84}
    spec_bytes=library.read(mapping['asset_id'])
    if sha(spec_bytes) != SPEC_SHA256:
        raise ValueError('specification source drift')
    with pymupdf.open(stream=spec_bytes,filetype='pdf') as spec:
        specification_text=' '.join(spec[83].get_text().split())
        if any(f'Unit {c}: {u}/01' not in specification_text for c,u in COURSE_UNITS.items()):
            raise ValueError('specification unit mapping drift')
    sources={}; docs={}; cache={}; exams={}
    try:
        for role,raw in raw_sources.items():
            if not isinstance(raw,dict) or not isinstance(raw.get('asset_id'),str) or not raw['asset_id'].startswith('asset:'):
                raise ValueError('source_id: stable asset required')
            if set(raw)-({'asset_id','sha256','inspection_pages'} | ({'edition','purpose'} if role=='reference' else set())):
                raise ValueError('unknown source pin field')
            record=library.record(raw['asset_id'])
            if record['sha256'] != raw.get('sha256'): raise ValueError('source_pin: digest mismatch')
            if raw['sha256'] not in cache: cache[raw['sha256']]=library.read(raw['asset_id'])
            doc=pymupdf.open(stream=cache[raw['sha256']],filetype='pdf'); docs[role]=doc
            pages=raw.get('inspection_pages')
            if not isinstance(pages,list) or not pages or any(type(p) is not int or not 1<=p<=len(doc) for p in pages) or pages != sorted(set(pages)) or 1 not in pages:
                raise ValueError('inspection_pages: ordered actual physical pages including cover required')
            source={**copy.deepcopy(raw),'path':record['path'],'pages':len(doc),
                    'page_geometry':[{'page':p,'width':doc[p-1].rect.width,'height':doc[p-1].rect.height,
                                      'rotation':doc[p-1].rotation,'cropbox':list(doc[p-1].cropbox)} for p in pages]}
            if role in ('qp','ms'):
                exams[role]=source_identity(record['path'],role,course)
                if record.get('course')!=course or record.get('kind')!='Sources/PastPapers':
                    raise ValueError('source_course: registered source metadata mismatch')
            else:
                if (not isinstance(raw.get('edition'),str) or not re.fullmatch(r'Issue [1-9]\d*',raw['edition'])
                        or not isinstance(raw.get('purpose'),str) or not raw['purpose'].strip()):
                    raise PendingEvidence('pending_reference_edition: declared edition/purpose required')
                cover=' '.join(doc[0].get_text().split())
                if raw['edition'] not in cover or not re.search(r'Formulae.*Statisti|Statisti.*Formulae',cover,re.I):
                    raise PendingEvidence('pending_reference_edition: original reference identity unavailable')
                source['header_evidence']={'page':1,'text':cover,'text_sha256':sha(cover.encode())}
            sources[role]=source
        if exams['qp'] != exams['ms'] or sources['qp']['asset_id']==sources['ms']['asset_id']:
            raise ValueError('source_pair: edition/session/component mismatch')
        covers=_paired_covers(docs['qp'],docs['ms'],exams['qp'],exams['ms'])
        joint=covers['qp'].get('joint_series_evidence')
        if joint and joint['ms_log']['page'] not in sources['ms']['inspection_pages']:
            source=sources['ms'];doc=docs['ms']
            source['inspection_pages']=sorted(source['inspection_pages']+[joint['ms_log']['page']])
            source['page_geometry']=[{'page':p,'width':doc[p-1].rect.width,'height':doc[p-1].rect.height,
                'rotation':doc[p-1].rotation,'cropbox':list(doc[p-1].cropbox)} for p in source['inspection_pages']]
        for role in ('qp','ms'):
            sources[role]['header_evidence']=covers[role]
            sources[role]['issues']=_source_issues(docs[role],sources[role]['inspection_pages'],exams[role])
        if len(required_asset_pages(sources,mapping,[]))>100:
            raise ValueError('selected_page_limit: at most 100 distinct asset-pages including source identity')
        raw_questions=request.get('questions')
        if not isinstance(raw_questions,list) or not 1<=len(raw_questions)<=8:
            raise ValueError('question_count: 1..8 distinct whole questions required')
        questions=[]; numbers=[]; media={}; files={}; rows=[]; renders={}; displaylists={}
        recipe={'dpi':144,'renderer':'PyMuPDF','version':pymupdf.VersionBind,
                'coordinates':'normalized rotated CropBox','alpha':False,'format':'png'}
        layouts={role:_source_layout(docs[role],role) for role in ('qp','ms')}
        for raw in raw_questions:
            if not isinstance(raw,dict) or set(raw)-{'number','question_regions','scheme_regions','parts','occurrence','assessment_mode','private_guidance_regions'}:
                raise ValueError('invalid question request fields')
            n=raw.get('number'); qid=canonical_qid(exams['qp'],n); reject_reserved(exams['qp'],n)
            if n in numbers or numbers and n<=numbers[-1]: raise ValueError('question ordering/duplicate')
            numbers.append(n)
            q={'number':n,'official_qid':qid,
               'question_regions':_bind_regions(raw.get('question_regions'),'qp',sources),
               'scheme_regions':_bind_regions(raw.get('scheme_regions'),'ms',sources),'parts':[]}
            if 'assessment_mode' in raw:
                if raw['assessment_mode']!=WHOLE_ASSESSMENT:raise ValueError('unknown assessment_mode')
                q['assessment_mode']=WHOLE_ASSESSMENT
            elif 'private_guidance_regions' in raw:
                raise ValueError('private guidance requires explicit whole assessment_mode')
            scope=_whole_question_scope(q,layouts,sources)
            if 'private_guidance_regions' in raw:
                q['private_guidance_regions']=_bind_regions(raw['private_guidance_regions'],'ms',sources)
                q['guidance_witness']=_private_guidance(q['private_guidance_regions'],layouts['ms'],docs)
                gw=q['guidance_witness'];source=sources['ms'];doc=docs['ms']
                extra={gw['first_question_row']['region']['page']}|{h['region']['page'] for h in gw['boundary_headings']}
                source['inspection_pages']=sorted(set(source['inspection_pages'])|extra)
                source['page_geometry']=[{'page':p,'width':doc[p-1].rect.width,'height':doc[p-1].rect.height,
                    'rotation':doc[p-1].rotation,'cropbox':list(doc[p-1].cropbox)} for p in source['inspection_pages']]
                source['issues']=_source_issues(doc,source['inspection_pages'],exams['ms'])
            boundary=scope['scheme_boundary']
            if boundary['kind']=='next_question' and boundary['page'] not in sources['ms']['inspection_pages']:
                sources['ms']['inspection_pages']=sorted(sources['ms']['inspection_pages']+[boundary['page']])
                source=sources['ms']; doc=docs['ms']
                source['page_geometry']=[{'page':p,'width':doc[p-1].rect.width,'height':doc[p-1].rect.height,
                                         'rotation':doc[p-1].rotation,'cropbox':list(doc[p-1].cropbox)} for p in source['inspection_pages']]
                source['issues']=_source_issues(doc,source['inspection_pages'],exams['ms'])
            parts=raw.get('parts')
            if not isinstance(parts,list) or not parts: raise ValueError('missing assessed parts')
            if 'assessment_mode' in q and (len(parts)!=1 or not isinstance(parts[0],dict) or parts[0].get('part')!=''):
                raise ValueError('whole assessment requires one empty-part record')
            seen=set()
            for part in parts:
                if not isinstance(part,dict) or set(part)-{'part','label','question_media_regions','scheme_media_regions','reference_regions','text_hint'}:
                    raise ValueError('invalid assessed part request fields')
                p=part.get('part'); suffix=part_suffix(p)
                if suffix in seen or part.get('label') != (f'({p})' if p else ''):
                    raise ValueError('duplicate or unstable assessed part label')
                seen.add(suffix)
                item={'id':'native-'+qid+('-'+suffix if suffix else ''),'part':p,'label':part['label']}
                for field,role,container in [('question_media_regions','qp','question_regions'),('scheme_media_regions','ms','scheme_regions')]:
                    item[field]=_bind_regions(part.get(field),role,sources,containers=q[container])
                    for r in item[field]:
                        siblings=[_part_marker(w) for w in _words(docs[role][r['page']-1])
                                  if _intersects(r['box'],w['box']) and _part_marker(w) and _part_marker(w)!=p]
                        if siblings and 'assessment_mode' not in q:
                            raise ValueError('sibling_disclosure: crop contains another assessed part landmark')
                if 'assessment_mode' in q:
                    if item['question_media_regions']!=scope['qp'] or item['scheme_media_regions']!=scope['ms']:
                        raise ValueError('whole assessment requires complete ordered source blocks')
                    item['scheme_media_regions']=q.get('private_guidance_regions',[])+item['scheme_media_regions']
                if part.get('reference_regions'):
                    if 'reference' not in sources: raise ValueError('reference source missing')
                    item['reference_regions']=_bind_regions(part['reference_regions'],'reference',sources)
                # Source hints are a literal excerpt only, never required transcription.
                if 'text_hint' in part:
                    hint=part['text_hint']
                    if not isinstance(hint,str) or hint not in _region_text(docs['qp'],item['question_media_regions']):
                        raise ValueError('text_hint: not a sourced literal excerpt')
                    item['text_hint']=hint
                for field,visibility in [('question_media_regions','public'),('scheme_media_regions','private'),('reference_regions','public')]:
                    names=[]
                    for r in item.get(field,[]):
                        key=canonical_bytes(r)
                        if key not in renders:
                            page=docs[r['role']][r['page']-1]
                            rect=pymupdf.Rect(r['box']); rect=pymupdf.Rect(rect.x0*page.rect.width,rect.y0*page.rect.height,rect.x1*page.rect.width,rect.y1*page.rect.height)
                            page_key=(sources[r['role']]['sha256'],r['page'])
                            if page_key not in displaylists: displaylists[page_key]=page.get_displaylist()
                            pix=displaylists[page_key].get_pixmap(matrix=pymupdf.Matrix(2,2),clip=rect,alpha=False)
                            pix.set_dpi(144,144)
                            renders[key]=pix.tobytes('png')
                        name=visibility+'/'+sha(key)[:24]+'.png'; data=renders[key]
                        files[name]=data; media[name]={'region':r,'visibility':visibility,'sha256':sha(data)}; names.append(name)
                    item['reference_media' if field=='reference_regions' else field.replace('_regions','')]=names
                q['parts'].append(item)
            if '' in seen and len(seen)>1: raise ValueError('mixed whole/part assessments')
            q['witness']=_question_witness(q,docs,sources,scope)
            if 'assessment_mode' in q:q['whole_assessment']=_whole_assessment(q,layouts,sources)
            q['pending_occurrences']=_occurrence(raw.get('occurrence'),library,occurrence_roots)
            questions.append(q)
            rows.extend({'id':p['id'],'source':{'profile':PROFILE,'course':course,'official_qid':qid,'part':p['part']},
                         'question_media':p['question_media'],'scheme_media':p['scheme_media'],
                         'reference_media':p.get('reference_media',[]),'text_hint':p.get('text_hint'),
                         'pending_mappings':['knowledge_components','prerequisites','rubric_representation']} for p in q['parts'])
            if 'assessment_mode' in q:
                row=rows[-1]
                row.update(assessment_mode=WHOLE_ASSESSMENT,whole_assessment=q['whole_assessment'],
                    marks=q['whole_assessment']['max_marks'],
                    scheme=[{'point':'Manual official whole-question rubric; inspect every private guidance/core raster.',
                        'whole_rubric':{'version':1,'max_marks':q['whole_assessment']['max_marks'],'media':q['parts'][0]['scheme_media']}}])
                if 'private_guidance_regions' in q:row['private_guidance_regions']=q['private_guidance_regions']
        inventory=required_asset_pages(sources,mapping,questions)
        if len(inventory)>100:
            raise ValueError('selected_page_limit: at most 100 distinct asset-pages including all required witnesses')
        descriptor={'schema_version':1,'profile':PROFILE,'teaching_approved':False,'graph_sha256':graph_sha256,
                    'exam':exams['qp'],'course':course,'sources':sources,'questions':questions,
                    'verified_pairs':[{'qp':sources['qp']['asset_id'],'ms':sources['ms']['asset_id'],'exam':exams['qp']}],
                    'unit_mapping_evidence':mapping,'required_asset_pages':inventory,
                    'selected_asset_pages':len(inventory),'render_recipe':recipe,'media':media}
        seed={'schema_version':1,'profile':PROFILE,'kind':'native_preparation_seed','teaching_approved':False,
              'descriptor_sha256':sha(canonical_bytes(descriptor)),'records':rows}
        validate_descriptor(descriptor,graph_sha256=graph_sha256)
        return descriptor,seed,files
    finally:
        for doc in docs.values(): doc.close()


def prepare_native(request_path: Path, output: Path, library, graph_sha256: str) -> dict:
    request_path=_physical(request_path); output=_physical(output,exists=False)
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*',output.name):
        raise ValueError('unsafe output directory name')
    if output==library.root or library.root in output.parents:
        raise ValueError('unsafe output: preparation must stay outside the learner/source vault')
    if output.exists(): raise ValueError('fresh output directory required')
    if not output.parent.is_dir(): raise ValueError('fresh output parent must exist')
    request=_read_json(request_path)
    descriptor,seed,files=_compute(request,library,graph_sha256)
    output.mkdir()
    for name,data in {'request.json':canonical_bytes(request),'descriptor.json':canonical_bytes(descriptor),
                      'seed.json':canonical_bytes(seed),**files}.items():
        path=output/name; path.parent.mkdir(exist_ok=True); path.write_bytes(data)
    manifest={'schema_version':1,'profile':PROFILE,
              'request_sha256':sha((output/'request.json').read_bytes()),
              'descriptor_sha256':sha((output/'descriptor.json').read_bytes()),'seed_sha256':sha((output/'seed.json').read_bytes()),
              'files':{name:sha(data) for name,data in files.items()}}
    (output/'COMPLETE').write_bytes(canonical_bytes(manifest))
    return descriptor


def verify_native_package(root: Path, library, graph_sha256: str, *, occurrence_roots=None) -> dict:
    root=_physical(root)
    manifest=_read_json(root/'COMPLETE')
    request=_read_json(root/'request.json')
    descriptor,seed,files=_compute(request,library,graph_sha256,occurrence_roots)
    expected={'request.json':canonical_bytes(request),'descriptor.json':canonical_bytes(descriptor),
              'seed.json':canonical_bytes(seed),**files}
    actual=set()
    for path in root.rglob('*'):
        if path.is_symlink() or not (path.is_dir() or stat.S_ISREG(path.stat().st_mode)):
            raise ValueError('unsafe package path')
        if path.is_file(): actual.add(path.relative_to(root).as_posix())
    if actual != set(expected)|{'COMPLETE'}: raise ValueError('package file inventory mismatch')
    for name,data in expected.items():
        if (root/name).read_bytes()!=data: raise ValueError('source_recomputation: package bytes differ from originals')
    expected_manifest={'schema_version':1,'profile':PROFILE,'request_sha256':sha(expected['request.json']),
                       'descriptor_sha256':sha(expected['descriptor.json']),'seed_sha256':sha(expected['seed.json']),
                       'files':{name:sha(data) for name,data in files.items()}}
    if manifest != expected_manifest: raise ValueError('package manifest digest mismatch')
    return descriptor


def prepared_material(descriptor, library):
    """Manager inventory uses normalized required evidence, including end witnesses."""
    sources = []
    pins = {pin['asset_id']: (role, pin) for role, pin in descriptor['sources'].items()}
    pages = {}
    for row in descriptor['required_asset_pages']:
        pages.setdefault(row['asset_id'], []).append(row['page'])
    for identifier, selected in sorted(pages.items()):
        record = library.record(identifier)
        role, pin = pins.get(identifier, ('inspection_only', {}))
        if not pin:
            import pymupdf
            with pymupdf.open(stream=library.read(identifier), filetype='pdf') as doc:
                total = len(doc)
        else:
            total = pin['pages']
        sources.append({'id': identifier, 'path': str(library.root / record['path']),
                        'sha256': record['sha256'], 'pages': total,
                        'kind': 'papers:' + descriptor['course'], 'status': 'available',
                        'selected_page_numbers': selected, 'prepared_role': role,
                        **({'evidence_role': 'auxiliary_reference', 'reference_purpose': pin['purpose']}
                           if role == 'reference' else {})})
    items = {}
    for q in descriptor['questions']:
        for part in q['parts']:
            items[part['id']] = {'official_qid': q['official_qid'], 'part': part['part'],
                'regions': q['question_regions'], 'mark_scheme_regions': q['scheme_regions'],
                'question_media': part['question_media'], 'mark_scheme_media': part['scheme_media'],
                'reference_media': part.get('reference_media', []),
                'reference_regions': part.get('reference_regions', []),
                'question_media_regions': part['question_media_regions'],
                'scheme_media_regions': part['scheme_media_regions'],
                'pending_occurrences': q['pending_occurrences']}
            if 'assessment_mode' in q:
                items[part['id']].update(assessment_mode=WHOLE_ASSESSMENT,whole_assessment=q['whole_assessment'],marks=q['whole_assessment']['max_marks'])
                if 'private_guidance_regions' in q:items[part['id']]['private_guidance_regions']=q['private_guidance_regions']
    return {'sources': sources, 'requested_sources': [s['id'] for s in sources], 'requested_pages': None,
            'focus_graph_sha256': descriptor['graph_sha256'],
            'selected_item_scope': {'type': 'prepared_group', 'origin': PROFILE,
                'official_qids': [q['official_qid'] for q in descriptor['questions']],
                'record_ids': list(items), 'records': items}}


def verify_prepared_state(state, library, graph_sha256):
    """Reconstruct frozen native input. This authenticates proposals, never approval."""
    config = state.get('prepared_scope')
    if not isinstance(config, dict) or set(config) != {'profile','package_sha256','descriptor_sha256','seed_sha256','graph_sha256','job_name'}:
        raise ValueError('prepared scope binding is missing or malformed')
    if (config['profile'] != PROFILE or config['job_name'] != state.get('name')
            or config['graph_sha256'] != graph_sha256 or state.get('scope') != 'questions'):
        raise ValueError('prepared job ownership, scope or graph changed')
    root = Path(state['prepared_input'])
    request=_read_json(root/'request.json')
    references={q['occurrence']['bundle']:q['occurrence']['complete_sha256']
                for q in request['questions'] if q.get('occurrence')}
    expected_roots={original:str(root.parent/'prepared-occurrences'/digest) for original,digest in references.items()}
    if state.get('prepared_occurrences',{}) != expected_roots:
        raise ValueError('prepared frozen occurrence provenance changed')
    for tree in [root, *map(Path,expected_roots.values())]:
        _physical(tree)
        for leaf in tree.rglob('*'):
            if leaf.is_symlink() or leaf.is_file() and leaf.stat().st_nlink != 1:
                raise ValueError('prepared input leaf must be private and physical')
    descriptor = verify_native_package(root, library, graph_sha256, occurrence_roots=expected_roots)
    expected = {'profile': PROFILE, 'job_name': state['name'], 'graph_sha256': graph_sha256,
                'package_sha256': sha((root/'COMPLETE').read_bytes()),
                'descriptor_sha256': sha((root/'descriptor.json').read_bytes()),
                'seed_sha256': sha((root/'seed.json').read_bytes())}
    if config != expected or descriptor['course'] != state.get('course'):
        raise ValueError('prepared frozen package/hash/course changed')
    for key, value in prepared_material(descriptor, library).items():
        if canonical_bytes(state.get(key)) != canonical_bytes(value):
            raise ValueError('prepared normalized scope changed: ' + key)
    if any(key in state for key in ('initial_native_question','focus_history','completed_scope_history',
            'source_rebase_history','reference_source_history','required_source_occurrences')):
        raise ValueError('prepared scope cannot inherit or extend legacy provenance')
    return descriptor


def retained_output_hashes(state):
    """Actual completed maker attempts own output bytes even when they failed."""
    scope = state.get('prepared_scope')
    if not isinstance(scope, dict) or scope.get('profile') != PROFILE or scope.get('job_name') != state.get('name'):
        return set()
    return {r['output_sha256'] for r in state.get('prepared_attempt_receipts', [])
            if r.get('role') == 'extract' and r.get('prepared_scope') == scope
            and r.get('attempt_id') and all(r.get(k) for k in ('started', 'worker_started', 'finished'))
            and type(r.get('exit')) is int and digest(r.get('output_sha256'))
            and r.get('candidate_sha256') == r.get('output_sha256')}


def prepared_candidate_problems(state, data, descriptor, output_root):
    """Exact grouped identities and immutable crop roles, including sibling isolation."""
    errors = []
    # Only the current JSON and exact manager-retained candidate JSON are
    # non-media outputs. Every other leaf must be a frozen media name, regardless
    # of suffix/codec (including WebP and images disguised as JSON or payloads).
    previous_hashes = retained_output_hashes(state)
    actual_images = set()
    for path in output_root.rglob('*'):
        if path.is_dir() and not path.is_symlink(): continue
        name = path.relative_to(output_root).as_posix()
        if name == 'candidate.json': continue
        if (path.parent == output_root and re.fullmatch(r'candidate\.json\.[0-9a-f]{32}\.previous', path.name)
                and not path.is_symlink() and path.is_file() and sha(path.read_bytes()) in previous_hashes):
            continue
        actual_images.add(name)
    if actual_images!=set(descriptor['media']):
        errors.append('prepared candidate raster inventory must have a complete frozen public/private partition')
    scope = state['selected_item_scope']; rows = data.get('questions')
    if (data.get('prepared_scope') != state['prepared_scope'] or data.get('selected_item_scope') != scope
            or data.get('diagrams') != [] or not isinstance(rows, list)
            or any(not isinstance(row, dict) for row in rows)
            or sorted(row.get('id','') for row in rows) != sorted(scope['record_ids'])):
        return ['prepared group scope/records/markers changed']
    for row in rows:
        item = scope['records'][row['id']]
        q=next(q for q in descriptor['questions'] if q['official_qid']==item['official_qid'])
        part=next(p for p in q['parts'] if p['id']==row['id'])
        try:validate_whole_row(row,q,part)
        except (ValueError,KeyError,TypeError) as exc:errors.append(str(exc))
        if (row.get('official_qid') != item['official_qid'] or row.get('part') != item['part']
                or row.get('kind') != 'structured'
                or row.get('prepared_scope_sha256') != state['prepared_scope']['package_sha256']):
            errors.append('prepared row identity/part/profile changed')
        for key in ('regions','mark_scheme_regions','question_media','mark_scheme_media'):
            if canonical_bytes(row.get(key)) != canonical_bytes(item[key]): errors.append('prepared immutable seed role changed: '+key)
        if row.get('media') != item['question_media'] + item['mark_scheme_media']:
            errors.append('prepared primary media must retain ordered public/private seed partition')
        for key in ('reference_media','reference_regions'):
            if row.get(key,[]) != item[key]: errors.append('prepared reference binding changed')
        media = item['question_media'] + item['mark_scheme_media'] + item['reference_media']
        expected_bindings = {name: descriptor['media'][name]['region'] for name in media}
        if canonical_bytes(row.get('media_regions')) != canonical_bytes(expected_bindings):
            errors.append('prepared media original region/role binding changed')
        for name in media:
            path = output_root / name
            if (path.is_symlink() or any(parent.is_symlink() for parent in path.parents if parent.is_relative_to(output_root))
                    or not path.is_file() or path.stat().st_nlink != 1
                    or sha(path.read_bytes()) != descriptor['media'][name]['sha256']):
                errors.append('prepared immutable seed media bytes changed: '+name)
    return errors
