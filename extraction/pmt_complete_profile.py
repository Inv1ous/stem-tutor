"""Explicit, immutable native PMT Internal Review Set1 complete-region profile.

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

KIND = 'pmt_complete_preparation'
PROFILE = 'pmt-native-complete-set1-v1'
_REPORT_COMPLETE = re.compile(_REPORT.pattern + r'|\bThis question proved\b|\bmajority attempted\b', re.I)


def _json(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()


def _glyphs(page):
    return [c for block in page.get_text('rawdict')['blocks'] if block['type'] == 0
            for line in block['lines'] for span in line['spans'] for c in span['chars'] if c['c'].strip()]


def _painted_bounds(page):
    boxes = [tuple(info['bbox']) for info in page.get_image_info()]
    # Text is authenticated and measured per glyph, never by coarse text blocks.
    boxes.extend(tuple(box) for kind, box in page.get_bboxlog() if 'text' not in kind)
    for drawing in page.get_drawings():
        rect = drawing['rect']
        pad = (drawing.get('width') or 0) / 2
        boxes.append((rect.x0 - pad, rect.y0 - pad, rect.x1 + pad, rect.y1 + pad))
    return boxes


def _bounds(page):
    """All native glyph, image and painted vector extents, including stroke width."""
    boxes = [tuple(c['bbox']) for c in _glyphs(page)] + _painted_bounds(page)
    return [b for b in boxes if all(abs(x) < 1e6 for x in b)
            and b[2] >= b[0] and b[3] >= b[1]]


def _authenticate_furniture(page, title, number, header, footer):
    """Only the exact native title/publisher/footer/page number may be excluded."""
    header_bottom, footer_top = max(r.y1 for r in header), footer.y0
    glyphs = _glyphs(page)
    head = [c for c in glyphs if c['bbox'][3] <= header_bottom]
    foot = [c for c in glyphs if c['bbox'][1] >= footer_top]
    if (''.join(c['c'] for c in head) != ''.join((title + 'PhysicsAndMathsTutor.com').split())
            or ''.join(c['c'] for c in foot) != 'EdexcelInternalReview' + str(number)
            or any(b[1] < header_bottom or b[3] > footer_top for b in _painted_bounds(page))
            or page.first_annot is not None):
        raise ValueError('unexplained native PMT furniture content')
    page_numbers = [pymupdf.Rect(w[:4]) for w in page.get_text('words')
                    if w[4] == str(number) and w[1] >= footer_top]
    allowed = header + [footer] + page_numbers
    if len(page_numbers) != 1 or any(not any(pymupdf.Rect(c['bbox']) in r for r in allowed) for c in head + foot):
        raise ValueError('ambiguous native PMT furniture glyph ownership')


def _separator(page, boxes, low, high):
    """Prove a full-width positive blank band with native bounds AND source pixels."""
    if high - low < 2 or any(b[1] < high and b[3] > low for b in boxes):
        raise ValueError('no safe complete horizontal whitespace separator')
    pix = page.get_pixmap(dpi=144, colorspace=pymupdf.csGRAY, alpha=False)
    scale = pix.height / page.rect.height
    first, last = int(low * scale) + 2, int(high * scale) - 2
    samples = pix.samples
    rows = []
    for y in range(max(0, first), min(pix.height, last)):
        if min(samples[y * pix.stride:y * pix.stride + pix.width], default=0) == 255:
            rows.append(y)
    # A continuous pixel band (at least one point), never a lone lucky scanline.
    runs = []
    for y in rows:
        if runs and y == runs[-1][-1] + 1: runs[-1].append(y)
        else: runs.append([y])
    run = max(runs, key=len, default=[])
    if len(run) < 2:
        raise ValueError('raster pixels cross whitespace separator')
    cut = round(((run[0] + run[-1] + 1) / 2) / scale / page.rect.height, 8)
    return cut


def analyse(raw: bytes, course: str, source_id: str, *, source_path: str) -> dict:
    registered = _REGISTERED.fullmatch(source_path)
    if not registered or registered[1] != course or not re.fullmatch(r'asset:[A-Za-z0-9_-]+', source_id):
        raise ValueError('unsupported complete PMT source/course/provenance')
    digest = sha(raw)
    with pymupdf.open(stream=raw, filetype='pdf') as doc:
        if not len(doc): raise ValueError('empty PMT source')
        title = doc[0].get_text().splitlines()[0].strip()
        printed = course.replace('P', 'C') if course.startswith('P') else course
        if not title.startswith((course + ' ', printed + ' ')):
            raise ValueError('PMT printed course title conflict')
        info, anchors = [], []
        for n, page in enumerate(doc, 1):
            text = page.get_text()
            if (page.rotation or not _PUBLISHER.search(text) or 'Edexcel Internal Review' not in text
                    or text.splitlines()[0].strip() != title):
                raise ValueError('unsupported native PMT page provenance')
            words = page.get_text('words', sort=True)
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
            info.append({'boxes': boxes, 'body': body, 'top': top, 'bottom': bottom})
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
        schemes = anchors[reset:reset + count]
        if [a['number'] for a in schemes] != expected:
            raise ValueError('ambiguous native PMT scheme sequence')
        tail = anchors[reset + count:]
        if tail:
            if ([a['number'] for a in tail] != expected
                    or not _REPORT_COMPLETE.search('\n'.join(doc[n].get_text() for n in range(tail[0]['page']-1, len(doc))))):
                raise ValueError('ambiguous native PMT examiner commentary boundary')
        if tail and any(not _REPORT_COMPLETE.search(doc[n].get_text())
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
                if high < low or any(b[1] < high and b[3] > low for b in info[n-1]['body']):
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
            if (len(totals) != 1 or int(totals[0]) <= 0 or not bracket
                    or int(bracket[-1]) != int(totals[0]) or not _MARK.search(st)
                    or _MARK.search(qt) or _REPORT_COMPLETE.search(qt) or _REPORT_COMPLETE.search(st)):
                raise ValueError('ambiguous printed total or public/private content evidence')
            location = json.dumps({'source_sha256': digest, 'page': anchor['page'], 'top': anchor['top'],
                                   'section': 'Questions', 'compilation_page': None}, sort_keys=True)
            questions.append({'id': 'occurrence-' + sha(location.encode())[:24], 'official_qid': None,
                              'part': '', 'label': str(anchor['number']), 'section': 'Questions',
                              'kind': 'structured', 'regions': qr, 'context_regions': [],
                              'mark_scheme_regions': sr, 'question_text': qt, 'scheme_text': st,
                              'marks': int(totals[0]), 'printed_total_witness': _TOTAL.search(qt)[0],
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
            intervals = [{'box': [0, 0, 1, info[n-1]['top']], 'role': 'running_header'}]
            for r, role, owner in sorted((x for x in owned if x[0]['page'] == n), key=lambda x: x[0]['box'][1]):
                if r['box'][1] != intervals[-1]['box'][3]:
                    raise ValueError('missing or overlapping physical content interval')
                intervals.append({'box': r['box'], 'role': role, 'question_id': owner})
                if role != 'questions': private.append({'page': n, 'role': role, 'region': r})
            if intervals[-1]['box'][3] != info[n-1]['bottom']:
                raise ValueError('unowned PMT content tail')
            intervals.append({'box': [0, info[n-1]['bottom'], 1, 1], 'role': 'running_footer'})
            pages.append({'page': n, 'role': '+'.join(dict.fromkeys(i['role'] for i in intervals[1:-1])),
                          'intervals': intervals})
    return {'schema_version': 1, 'kind': KIND, 'profile': PROFILE, 'course': course, 'title': title,
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
