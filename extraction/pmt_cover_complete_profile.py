"""Explicit v2 native PMT C1-cover and Internal Review complete-region profile.

This is source proof only. Semantic review and operational admission remain separate.
Unknown ownership, incomplete totals, or nonblank separators refuse the source.
"""
from __future__ import annotations

from collections import defaultdict
import json
from pathlib import Path
import re
import time

import pymupdf
from PIL import Image

from fastpath import _png, sha
from pmt_source_profile import _REGISTERED, _PUBLISHER, _MARK, _REPORT, _TOTAL
from tutorlib.asset_library import AssetLibrary

KIND = 'pmt_cover_complete_preparation'
PROFILE = 'pmt-native-cover-complete-set1-v2'
_REPORT_COMPLETE = re.compile(_REPORT.pattern + r'|\bThis question proved\b|\bmajority attempted\b', re.I)
_PRIVATE_LITERAL = re.compile(r'\b(?:mark\s+schemes?|examiner\s+reports?)\b|\banswers?\s*:', re.I)


def _json(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()


# Frozen v1 physical geometry; identity and item semantics below belong to v2.
from pmt_complete_profile import (_glyphs, _painted_bounds, _bounds,
                                  _authenticate_furniture, _separator)
_GEOMETRY_SHA256 = '3288061579d1d7d9fadcc5f96d9fed5be1a131df4100013ee1d07691e6bdc121'



_C1_TOPICS = {
    'Inequalities': ('Algebra', 'Inequalities'),
    'Quadratics': ('Algebra', 'Quadratics'),
    'Simultaneous Equations': ('Algebra', 'Simultaneous Equations'),
    'Surds and Indices': ('Algebra', 'Surds and Indices'),
    'Coordinate Geometry: Straight Lines': ('Coordinate Geometry', 'Straight Lines'),
    'Differentiation: Stationary points': ('Differentiation', 'Stationary Points'),
    'Differentiation: Tangents and Normals': ('Differentiation', 'Tangents and Normals'),
    'Basic Differentiation': ('Differentiation', 'Basic Differentiation'),
    'Functions: Transformations and Graphs': ('Functions', 'Transformations and Graphs'),
    'Integration: Areas': ('Integration', 'Areas'),
    'Integration: Basic Integration': ('Integration', 'Basic Integration'),
    'Sequences and Series: Arithmetic Series': ('Sequences and series', 'Arithmetic series'),
    'Sequences and Series': ('Sequences and series', 'General'),
}
_COVER_PREFIX = ('1 Paper Reference(s) 6663/01 Edexcel GCE Core Mathematics C1 '
                 'Advanced Subsidiary ')
_COVER_MIDDLE = (' Calculators may NOT be used for these questions. Information for Candidates '
                 'A booklet ‘Mathematical Formulae and Statistical Tables’ might be needed for some questions. '
                 'The marks for the parts of questions are shown in round brackets, e.g. (2). ')
_COVER_SUFFIX = (' Advice to Candidates You must ensure that your answers to parts of questions are clearly labelled. '
                 'You must show sufficient working to make your methods clear. '
                 'Answers without working may not gain full credit. PhysicsAndMathsTutor.com')


def _cover(page, course):
    """Authenticate the observed complete GCE C1 cover, preserving its qualification."""
    text = ' '.join(page.get_text().split())
    lines = {line.strip() for line in page.get_text().splitlines()}
    if (course != 'P1' or not {'6663/01', 'Edexcel GCE', 'Core Mathematics C1',
                              'Advanced Subsidiary'} <= lines or page.rotation
            or page.first_annot is not None or page.get_image_info()):
        raise ValueError('unsupported native legacy C1 cover identity')
    topics = [topic for topic in _C1_TOPICS if text.startswith(_COVER_PREFIX + topic + _COVER_MIDDLE)]
    counts = re.findall(r'There are ([1-9]\d*|xx) questions in this test\.', text)
    if len(counts) != 1:
        raise ValueError('ambiguous native C1 cover count')
    literal = f'There are {counts[0]} questions in this test.'
    if len(topics) != 1 or text != _COVER_PREFIX + topics[0] + _COVER_MIDDLE + literal + _COVER_SUFFIX:
        raise ValueError('unexplained native C1 cover content or qualification')
    drawings = page.get_drawings()
    if topics[0] in {'Inequalities', 'Quadratics'}:
        first, second = 405.35, 526.95
    elif topics[0] == 'Sequences and Series: Arithmetic Series':
        first, second = 445.6, 572.9
    elif topics[0] in {'Coordinate Geometry: Straight Lines', 'Differentiation: Stationary points',
                        'Differentiation: Tangents and Normals', 'Functions: Transformations and Graphs'}:
        first, second = 457.6, 584.9
    else:
        first, second = 411.1, 538.45
    expected = [(61.05, first, 517.45, first), (55.05, second, 511.45, second)]
    if (len(drawings) != 2 or any(kind != 'stroke-path' for kind, _ in page.get_bboxlog() if 'text' not in kind)
            or any(d['type'] != 's' or d['color'] != (0, 0, 0) or d['width'] != .75
                   or d['stroke_opacity'] != 1 or len(d['items']) != 1 or d['items'][0][0] != 'l'
                   or any(abs(x-y) > .002 for x, y in zip(d['rect'], box))
                   for d, box in zip(drawings, expected))):
        raise ValueError('unexplained native C1 cover paint')
    category, topic = _C1_TOPICS[topics[0]]
    heading = f'C1 {category} {"-" if topics[0] == "Integration: Areas" else "–"} {topic}'
    prefix = f'C1 {category}: {topic}'
    return heading, prefix, {'declared_count': None if counts[0] == 'xx' else int(counts[0]),
                              'literal': literal}


def _c1_furniture(page, number, title, prefix):
    """Authenticate every native margin glyph and the positive page role."""
    glyphs = _glyphs(page)
    head = [c for c in glyphs if c['bbox'][3] <= 52]
    foot = [c for c in glyphs if c['bbox'][1] >= 790]
    compact = lambda text: ''.join(text.split())
    actual_head, actual_foot = (''.join(c['c'] for c in chars) for chars in (head, foot))
    head_titles = [title + 'PhysicsAndMathsTutor.com', 'PhysicsAndMathsTutor.com']
    roles = {'questions': ['', prefix + ' – Questions'],
             'mark_scheme': [prefix + ' – Mark Schemes'],
             'examiner_comments': [prefix + ' – Examiner Reports']}
    matches = [role for role, literals in roles.items()
               if any(actual_foot == compact(literal + str(number)) for literal in literals)]
    if (actual_head not in [compact(t) for t in head_titles] or len(matches) != 1
            or (actual_head == compact(head_titles[1]) and actual_foot != compact(prefix + ' – Questions' + str(number)))
            or page.rotation or page.first_annot is not None
            or any(b[1] < max(c['bbox'][3] for c in head) or b[3] > min(c['bbox'][1] for c in foot)
                   for b in _painted_bounds(page))):
        raise ValueError('unexplained native C1 furniture or role')
    return max(c['bbox'][3] for c in head), min(c['bbox'][1] for c in foot), matches[0]


def analyse(raw: bytes, course: str, source_id: str, *, source_path: str) -> dict:
    import pmt_complete_profile as geometry
    if sha(Path(geometry.__file__).read_bytes()) != _GEOMETRY_SHA256:
        raise ValueError('frozen v1 PMT geometry algorithm differs')
    registered = _REGISTERED.fullmatch(source_path)
    if not registered or registered[1] != course or not re.fullmatch(r'asset:[A-Za-z0-9_-]+', source_id):
        raise ValueError('unsupported complete PMT source/course/provenance')
    digest = sha(raw)
    with pymupdf.open(stream=raw, filetype='pdf') as doc:
        if not len(doc): raise ValueError('empty PMT source')
        legacy = 'Edexcel GCE' in doc[0].get_text()
        cover_count = None
        if legacy:
            title, prefix, cover_count = _cover(doc[0], course)
        else:
            title = doc[0].get_text().splitlines()[0].strip()
        printed = course.replace('P', 'C') if course.startswith('P') else course
        if not title.startswith((course + ' ', printed + ' ')):
            raise ValueError('PMT printed course title conflict')
        info, anchors = [], []
        for n, page in enumerate(doc, 1):
            if legacy and n == 1:
                info.append({'top': 0, 'bottom': 1, 'body': [], 'boxes': _bounds(page), 'role': 'public_frontmatter'})
                continue
            text = page.get_text()
            if not _PUBLISHER.search(text):
                raise ValueError('missing native PMT page publisher')
            if not legacy and (page.rotation or 'Edexcel Internal Review' not in text
                    or text.splitlines()[0].strip() != title):
                raise ValueError('unsupported native PMT page provenance')
            words = page.get_text('words', sort=True)
            role = None
            if legacy:
                header_bottom, footer_top, role = _c1_furniture(page, n, title, prefix)
            else:
                title_boxes = page.search_for(title)
                publishers = page.search_for('PhysicsAndMathsTutor.com')
                header = title_boxes + publishers
                footer = page.search_for('Edexcel Internal Review')
                if len(title_boxes) != 1 or len(publishers) != 1 or len(footer) != 1 or footer[0].y0 < .9 * page.rect.height:
                    raise ValueError('ambiguous native PMT furniture')
                _authenticate_furniture(page, title, n, header, footer[0])
                header_bottom, footer_top = max(r.y1 for r in header), footer[0].y0
            boxes = _bounds(page)
            body = [b for b in boxes if b[3] > header_bottom + .01 and b[1] < footer_top - .01]
            if not body or any(b[1] < header_bottom or b[3] > footer_top for b in body):
                raise ValueError('unowned native PMT page content')
            top = _separator(page, boxes, header_bottom, min(b[1] for b in body))
            bottom = _separator(page, boxes, max(b[3] for b in body), footer_top)
            info.append({'boxes': boxes, 'body': body, 'top': top, 'bottom': bottom, 'role': role})
            for word in words:
                match = re.fullmatch(r'([1-9]\d{0,2})\.', word[4])
                if match and .045 < word[0]/page.rect.width < .12 and top < word[1]/page.rect.height < bottom:
                    anchors.append({'number': int(match[1]), 'page': n, 'top': word[1]/page.rect.height,
                                    'bbox': list(word[:4])})
        reset = next((i for i, a in enumerate(anchors) if i and a['number'] == 1), None)
        if reset is None: raise ValueError('missing native PMT marking reset')
        public = anchors[:reset]
        count = len(public)
        expected = list(range(1, count + 1))
        if [a['number'] for a in public] != expected:
            raise ValueError('ambiguous public question sequence')
        if legacy:
            if cover_count['declared_count'] is not None and cover_count['declared_count'] != count:
                raise ValueError('native C1 cover count conflicts with full public inventory')
            cover_count['derived_count'] = count
        # The existing source profile's exact positive bare-label predicate is
        # private-only and aligned to the first authenticated dotted MS label.
        start = anchors[reset]
        bare = []
        for n, page in enumerate(doc, 1):
            if n < start['page']: continue
            words = page.get_text('words', sort=True)
            for word in words:
                if (not re.fullmatch(r'[1-9]\d{0,2}', word[4])
                        or not .045 < word[0]/page.rect.width < .12
                        or not .06 < word[1]/page.rect.height < .9
                        or (n, word[1]) <= (start['page'], start['bbox'][1])
                        or abs(word[0]/page.rect.width - start['bbox'][0]/doc[start['page']-1].rect.width) > .003
                        or not info[n-1]['top'] < word[1]/page.rect.height < info[n-1]['bottom']):
                    continue
                if any(re.fullmatch(r'\([a-z]\)', w[4])
                       and 0 < w[0]-word[2] < page.rect.width*.07
                       and abs(w[1]-word[1]) < 3 for w in words):
                    bare.append({'number': int(word[4]), 'page': n, 'top': word[1]/page.rect.height,
                                 'bbox': list(word[:4])})
        anchors = public + sorted(anchors[reset:] + bare, key=lambda a: (a['page'], a['top']))
        schemes = anchors[reset:reset + count]
        if [a['number'] for a in schemes] != expected:
            raise ValueError('ambiguous native PMT scheme sequence')
        tail = anchors[reset + count:]
        if tail:
            if ([a['number'] for a in tail] != expected
                    or not (legacy and info[tail[0]['page']-1]['role'] == 'examiner_comments')
                    and not _REPORT_COMPLETE.search('\n'.join(doc[n].get_text() for n in range(tail[0]['page']-1, len(doc))))):
                raise ValueError('ambiguous native PMT examiner commentary boundary')
        if tail and any(not (legacy and info[n]['role'] == 'examiner_comments') and not _REPORT_COMPLETE.search(doc[n].get_text())
                        and not re.search(r'No Report available', doc[n].get_text(), re.I)
                        for n in range(tail[0]['page']-1, len(doc))):
            raise ValueError('unclassified private commentary tail')
        # A body reset must be positively understood, never silently discarded.
        starts = public + schemes + tail[:1]
        previous = None
        separators = []
        for anchor in starts:
            n = anchor['page']; page = doc[n-1]; data = info[n-1]
            # The connected vertical object component containing the label
            # includes tall formula glyphs above the label's own top. Earlier
            # content on a new physical page can belong to the previous block.
            low, high = anchor['bbox'][1], anchor['bbox'][3]
            while True:
                connected = [b for b in data['body'] if b[1] <= high and b[3] >= low]
                lo2, hi2 = min(b[1] for b in connected), max(b[3] for b in connected)
                if (lo2, hi2) == (low, high): break
                low, high = lo2, hi2
            prior = [b[3] for b in data['body'] if b[3] < low]
            if previous and previous['page'] == n and (not prior or low <= previous['bbox'][3]):
                raise ValueError('content crosses numbered block ownership')
            cut = _separator(page, data['boxes'], max(prior), low) if prior else data['top']
            anchor['cut'] = cut
            anchor['component_top'] = low
            separators.append({'page': n, 'cut': cut, 'next_number': anchor['number']})
            previous = anchor

        # A printed public total closes its content. Blankness alone cannot
        # assign later disconnected working to that public question. Require
        # every subsequent component to begin with the next authenticated block;
        # ambiguous post-total content holds rather than moving a public cut.
        for index, anchor in enumerate(public):
            following = public[index+1] if index+1 < count else schemes[0]
            witnesses = []
            for n in range(anchor['page'], following['page']+1):
                page = doc[n-1]
                for literal in dict.fromkeys(m[0] for m in _TOTAL.finditer(page.get_text())):
                    for box in page.search_for(literal):
                        if ((n, box.y0) >= (anchor['page'], anchor['bbox'][1])
                                and (n, box.y1) < (following['page'], following['bbox'][1])):
                            witnesses.append({'page': n, 'bbox_pt': list(box), 'literal': literal})
            if len(witnesses) != 1:
                raise ValueError('ambiguous public total ownership witness')
            witness = witnesses[0]
            for n in range(witness['page'], following['page']+1):
                low = witness['bbox_pt'][3] if n == witness['page'] else info[n-1]['top']*doc[n-1].rect.height
                high = following['component_top'] if n == following['page'] else info[n-1]['bottom']*doc[n-1].rect.height
                extra = [b for b in info[n-1]['body'] if b[1] < high and b[3] > low]
                if legacy:
                    # These original underscore rules remain owned by the
                    # public block; they are never used to infer its boundary.
                    rules = [tuple(c['bbox']) for c in _glyphs(doc[n-1]) if c['c'] == '_']
                    extra = [b for b in extra if b not in rules]
                if high < low or extra:
                    raise ValueError('ambiguous post-total public/private component ownership')
            anchor['total_witness'] = witness

        def region(n, lo, hi):
            return {'source_id': source_id, 'source_sha256': digest, 'page': n,
                    'box': [0, lo, 1, hi]}

        def regions(first, end):
            result = []
            for n in range(first['page'], end['page'] + 1):
                lo = first['cut'] if n == first['page'] else info[n-1]['top']
                hi = end['cut'] if n == end['page'] else info[n-1]['bottom']
                if hi > lo: result.append(region(n, lo, hi))
            return result

        def text_for(rows):
            return '\n'.join(doc[r['page']-1].get_text(clip=pymupdf.Rect(
                0, r['box'][1]*doc[r['page']-1].rect.height,
                doc[r['page']-1].rect.width, r['box'][3]*doc[r['page']-1].rect.height)) for r in rows)

        end = tail[0] if tail else {'page': len(doc), 'cut': info[-1]['bottom']}
        questions = []
        for index, anchor in enumerate(public):
            qr = regions(anchor, public[index+1] if index+1 < count else schemes[0])
            sr = regions(schemes[index], schemes[index+1] if index+1 < count else end)
            qt, st = text_for(qr), text_for(sr)
            totals = _TOTAL.findall(qt)
            bracket = re.findall(r'\[(\d+)\]', st)
            scheme_witnesses = []
            if bracket:
                literal = '[' + bracket[-1] + ']'
                for r in sr:
                    page = doc[r['page']-1]
                    for box in page.search_for(literal):
                        if box.y0 >= r['box'][1]*page.rect.height and box.y1 <= r['box'][3]*page.rect.height:
                            scheme_witnesses.append({'page': r['page'], 'bbox_pt': list(box), 'literal': literal})
            reasons = []
            if len(totals) != 1 or int(totals[0]) <= 0:
                reasons.append('ambiguous_printed_question_total')
            if not bracket or not scheme_witnesses or (len(totals) == 1 and int(bracket[-1]) != int(totals[0])):
                reasons.append('ambiguous_printed_total_or_scheme_termination')
            if not _MARK.search(st): reasons.append('missing_official_scoring_codes')
            if _MARK.search(qt) or _REPORT_COMPLETE.search(qt) or _PRIVATE_LITERAL.search(qt):
                reasons.append('public_private_content_evidence')
            if _REPORT_COMPLETE.search(st) or re.search(r'\bExaminer\s+Reports?\b', st, re.I):
                reasons.append('private_commentary_in_scheme')
            location = json.dumps({'source_sha256': digest, 'page': anchor['page'], 'top': anchor['top'],
                                   'section': 'Questions', 'compilation_page': None}, sort_keys=True)
            questions.append({'id': 'occurrence-' + sha(location.encode())[:24], 'official_qid': None,
                              'part': '', 'label': str(anchor['number']), 'section': 'Questions',
                              'kind': 'structured', 'regions': qr, 'context_regions': [region(1, 0, 1)] if legacy else [],
                              'mark_scheme_regions': sr, 'question_text': qt, 'scheme_text': st,
                              'marks': None if reasons else int(totals[0]), 'printed_total_witness': _TOTAL.search(qt)[0],
                              'scheme_total_witness': '[' + bracket[-1] + ']' if bracket else None,
                              'scheme_total_geometry': scheme_witnesses[-1] if scheme_witnesses else None,
                              'hold_reasons': reasons,
                              'printed_total_geometry': anchor['total_witness'],
                              'maximum_authority': 'printed_question_total', 'answer': None,
                              'answer_status': 'rubric', 'explanation_policy': 'on_demand',
                              'review_reasons': ['independent_source_visual_review', 'syllabus_mapping_required'],
                              'teaching_approved': False})
        pages, private = [], []
        comments = regions(tail[0], {'page': len(doc), 'cut': info[-1]['bottom']}) if tail else []
        owned = []
        for q in questions:
            owned += [(r, 'questions', q['id']) for r in q['regions']]
            owned += [(r, 'mark_scheme', q['id']) for r in q['mark_scheme_regions']]
        owned += [(r, 'examiner_comments', None) for r in comments]
        for n in range(1, len(doc)+1):
            if legacy and n == 1:
                pages.append({'page': 1, 'role': 'public_frontmatter', 'intervals': [
                    {'box': [0, 0, 1, 1], 'role': 'public_frontmatter'}]})
                continue
            intervals = [{'box': [0, 0, 1, info[n-1]['top']], 'role': 'running_header'}]
            for r, role, owner in sorted((x for x in owned if x[0]['page'] == n), key=lambda x: x[0]['box'][1]):
                if r['box'][1] != intervals[-1]['box'][3]:
                    raise ValueError('missing or overlapping physical content interval')
                intervals.append({'box': r['box'], 'role': role, 'question_id': owner})
                if legacy and role != info[n-1]['role']:
                    raise ValueError('native C1 page role conflicts with physical ownership')
                if role != 'questions': private.append({'page': n, 'role': role, 'region': r})
            if intervals[-1]['box'][3] != info[n-1]['bottom']:
                raise ValueError('unowned PMT content tail')
            intervals.append({'box': [0, info[n-1]['bottom'], 1, 1], 'role': 'running_footer'})
            pages.append({'page': n, 'role': '+'.join(dict.fromkeys(i['role'] for i in intervals[1:-1])),
                          'intervals': intervals})
    return {'schema_version': 1, 'kind': KIND, 'profile': PROFILE, 'course': course, 'title': title,
            'cover_count': cover_count,
            'source_qualification': 'Edexcel GCE 6663/01 Core Mathematics C1 Advanced Subsidiary' if legacy else 'Edexcel Internal Review',
            'source': {'id': source_id, 'sha256': digest, 'pages': len(pages), 'path': source_path},
            'teaching_approved': False, 'questions': questions, 'pages': pages, 'review_pages': [],
            'private_pages': private, 'issues': [], 'separators': separators,
            'status': 'source_verified_unreviewed'}


def prepare(vault: Path, source_id: str, course: str, output: Path, *, dpi=120) -> dict:
    if type(dpi) is not int or not 72 <= dpi <= 200: raise ValueError('invalid preparation dpi')
    output = Path(output).resolve()
    if output.exists(): raise FileExistsError(f'output exists: {output}')
    if not any(p.name == 'Preparation' and p.parent.name == 'Work' for p in output.parents):
        raise ValueError('fresh output must live under Work/Preparation')
    production = Path(__file__).resolve().parents[2] / 'STEM Tutor'
    if any(p == output or p in output.parents for p in [Path(vault).resolve(), production.resolve()]):
        raise ValueError('output must be outside learner vaults')
    library = AssetLibrary(vault)
    raw = library.read(source_id); record = library.record(source_id)
    if record.get('course', course) != course: raise ValueError('registered course conflict')
    bundle = analyse(raw, course, source_id, source_path=record['path'])
    bundle['render_recipe'] = {'dpi': dpi, 'renderer': 'pymupdf-rgb-pillow-normalized-v1'}
    from source_practice import _replay_media
    requests = _replay_media(bundle, False)
    output.mkdir(parents=True, exist_ok=False)
    groups = defaultdict(list)
    for name, value in requests.items(): groups[value['region']['page']].append((name, value))
    media = {}; start = time.perf_counter()
    with pymupdf.open(stream=raw, filetype='pdf') as doc:
        for n, group in sorted(groups.items()):
            pix = doc[n-1].get_pixmap(dpi=dpi, alpha=False)
            image = Image.frombytes('RGB', [pix.width, pix.height], pix.samples)
            for name, value in group:
                png = _png(image, value['region']['box'])
                path = output / name; path.parent.mkdir(exist_ok=True); path.write_bytes(png)
                media[name] = {**value, 'sha256': sha(png), 'bytes': len(png)}
            image.close()
    bundle['media'] = media
    bundle['metrics'] = {'dpi': dpi, 'page_renders': len(groups), 'model_calls': 0,
                         'elapsed_seconds': time.perf_counter()-start}
    encoded = json.dumps(bundle, indent=2, ensure_ascii=False).encode() + b'\n'
    (output / 'bundle.json').write_bytes(encoded)
    (output / 'COMPLETE').write_text(sha(encoded) + '\n')
    return bundle


def verify_bundle(output: Path) -> dict:
    raw = (output / 'bundle.json').read_bytes()
    if sha(raw) != (output / 'COMPLETE').read_text().strip(): raise ValueError('manifest digest mismatch')
    bundle = json.loads(raw)
    if (bundle.get('kind') != KIND or bundle.get('profile') != PROFILE
            or bundle.get('schema_version') != 1 or bundle.get('teaching_approved') is not False):
        raise ValueError('invalid complete PMT preparation')
    dpi = bundle.get('metrics', {}).get('dpi')
    if (type(dpi) is not int or not 72 <= dpi <= 200
            or bundle.get('render_recipe') != {'dpi': dpi, 'renderer': 'pymupdf-rgb-pillow-normalized-v1'}):
        raise ValueError('preparation rendering recipe differs')
    for name, item in bundle['media'].items():
        if not re.fullmatch(r'(questions|context|private|review)/[a-f0-9]{24}\.png', name):
            raise ValueError('unsafe media path')
        path = output / name
        if path.is_symlink() or path.parent.is_symlink() or sha(path.read_bytes()) != item['sha256']:
            raise ValueError('media digest mismatch')
    return bundle
