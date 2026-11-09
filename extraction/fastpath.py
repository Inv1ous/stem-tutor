#!/usr/bin/env python3
"""Prepare native Cambridge MCQs from original pixels and official keys.

This is a deterministic preparation adapter, not a review/publication command.
It never launches providers, writes the Library or updates extraction jobs.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import sys
import time

import pymupdf
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from tutorlib.asset_library import AssetLibrary

PROFILE = 'caie-native-paper1-v1'
PAPER = re.compile(r'(970[12])_([msw])(\d{2})_(1[123])\Z')
NATIVE_NAME = re.compile(r'(970[12])_([msw]\d{2})_(qp|ms)_(1[123])\.pdf\Z')

# Whole-PDF authorities from the original native-word and full-page raster survey
# in Work/Workers/extraction/overnight-20261105-10pct/native-mcq-source-variants.
# These are exact physical pages, never text-based reference/blank detection.
_QP_REFERENCE_PAGES = {
    ('9701_m22_12', 'a62038703d3e55f72fb3b0696779d989fe86a9a9c1dc1c465c8a784bc28289e0'): (19, 20),
    ('9701_m23_12', '1256fc131a9859aafff2fadc63137cc8f7695cfde83c8e49619def2d92bf7af6'): (19, 20),
    ('9701_m24_12', 'da43b3dc9bca2b259f2882fc6f06c1254aa47169eb3559bcce339b49ce86c028'): (19, 20),
}
_MS_BLANK_FURNITURE_PAGES = {
    'ef2d87612dcad60dbdfe1e19b785a4db310b3d5a88b4fbee7bca46f58fe5a82e': (4,),
}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _identity(doc, paper: str, role: str) -> None:
    match = PAPER.fullmatch(paper)
    if not match:
        raise ValueError('unsupported paper identity; expected 9701/9702 native Paper 1')
    course, season, year, variant = match.groups()
    month = {'s': r'May\s*/\s*June', 'w': r'October\s*/\s*November', 'm': r'February\s*/\s*March'}[season]
    if role == 'ms' and season == 'm':
        month = r'(?<![\w/])(?:February/)?March'
    text = ' '.join(doc[0].get_text().split())
    def header_matches(value):
        # Keep the optional prefix literal: April / March and NotMarch are invalid.
        date_value = re.sub(r'\s*/\s*', '/', value) if role == 'ms' and season == 'm' else value
        return (re.search(rf'\b{course}\s*/\s*{variant}\b', value)
                and re.search(month + r'\s+20' + year + r'\b', date_value, re.I))
    if (not header_matches(text)
            or not re.search(r'Paper\s+1\s+Multiple\s+Choice', text, re.I)
            or (role == 'ms' and not re.search(r'MARK\s+SCHEME', text, re.I))
            or (role == 'qp' and re.search(r'MARK\s+SCHEME', text, re.I))):
        raise ValueError(f'{role} content identity does not match {paper}')
    # The cover alone cannot authorize keys from a different paper body.
    if role == 'ms':
        for number, page in enumerate(doc, 1):
            text = ' '.join(page.get_text().split())
            if not header_matches(text):
                raise ValueError(f'ms page {number} content identity does not match {paper}')
    else:
        sitting = {'s': 'M/J', 'w': 'O/N', 'm': 'F/M'}[season]
        expected = f'{course}/{variant}/{sitting}/{year}'
        for number, page in enumerate(doc, 1):
            footers = re.findall(r'970[12]/\d{2}/(?:M/J|O/N|F/M)/\d{2}', page.get_text())
            if any(footer != expected for footer in footers):
                raise ValueError(f'qp page {number} content identity does not match {paper}')


def _region(ref, digest, page, box):
    return {'source_id': ref, 'source_sha256': digest, 'page': page,
            'box': [round(v, 8) for v in box]}


def _words(page):
    return [w for w in page.get_text('words', sort=True) if w[4].strip()]


def _anchors(doc):
    """The profiled question-number gutter, excluding centered page numbers."""
    rows = []
    for index, page in enumerate(doc):
        if index == 0:
            continue
        w, h = page.rect.width, page.rect.height
        for word in _words(page):
            if (re.fullmatch(r'[1-9]|[1-3]\d|40', word[4])
                    and .078 * w <= word[0] <= .09 * w
                    and .06 * h <= word[1] < .93 * h):
                rows.append({'number': int(word[4]), 'page': index + 1,
                             'top': word[1] / h, 'bottom': word[3] / h})
    return sorted(rows, key=lambda r: (r['page'], r['top']))


def _key(doc, ref, digest):
    """Use spatial row adjacency, handling single and side-by-side key columns."""
    found, errors, pages = {}, [], []
    for index, page in enumerate(doc):
        words = _words(page)
        count = 0
        for answer in words:
            if answer[4] not in 'ABCD' or len(answer[4]) != 1 or not .07 * page.rect.height < answer[1] < .93 * page.rect.height:
                continue
            candidates = [w for w in words if re.fullmatch(r'[1-9]|[1-3]\d|40', w[4])
                          and abs(w[1] - answer[1]) < 2.5 and 0 < answer[0] - w[2] < 110]
            if not candidates:
                continue
            number = max(candidates, key=lambda w: w[2])
            n = int(number[4])
            box = [max(0, (number[0] - 5) / page.rect.width),
                   max(0, (min(number[1], answer[1]) - 3) / page.rect.height),
                   min(1, (answer[2] + 6) / page.rect.width),
                   min(1, (max(number[3], answer[3]) + 3) / page.rect.height)]
            if n in found:
                errors.append({'reason': 'duplicate_or_conflicting_key', 'question': n, 'page': index + 1})
            else:
                found[n] = {'answer': answer[4], 'region': _region(ref, digest, index + 1, box)}
            count += 1
        status = 'official_key_rows' if count else 'cover' if index == 0 else 'needs_review'
        if status == 'needs_review' and index + 1 in _MS_BLANK_FURNITURE_PAGES.get(digest, ()):
            status = 'blank_furniture'
        pages.append({'page': index + 1, 'status': status, 'rows': count})
    missing = sorted(set(range(1, 41)) - found.keys())
    if missing:
        errors.append({'reason': 'missing_official_keys', 'questions': missing})
    errors.extend({'reason': 'unassigned_ms_page', 'page': p['page']} for p in pages if p['status'] == 'needs_review')
    return found, pages, errors


def analyse_pair(qp: bytes, ms: bytes, paper: str, qp_ref: str, ms_ref: str) -> dict:
    """Return conservative source-bound geometry and an explicit exception ledger."""
    qhash, mhash = sha(qp), sha(ms)
    with pymupdf.open(stream=qp, filetype='pdf') as qdoc, pymupdf.open(stream=ms, filetype='pdf') as mdoc:
        _identity(qdoc, paper, 'qp')
        _identity(mdoc, paper, 'ms')
        anchors = _anchors(qdoc)
        key, ms_pages, exceptions = _key(mdoc, ms_ref, mhash)
        sequence = [a['number'] for a in anchors]
        if sequence != list(range(1, 41)):
            exceptions.append({'reason': 'question_number_sequence', 'observed': sequence,
                               'missing': sorted(set(range(1, 41)) - set(sequence))})
        qp_pages, shared, references = [], [], []
        for index, page in enumerate(qdoc):
            text = page.get_text()
            local = [a for a in anchors if a['page'] == index + 1]
            if re.search(r'The\s+responses\s+A\s+to\s+D', text, re.I) and local:
                top = .06
                end = max(top, local[0]['top'] - .006)
                shared.append(_region(qp_ref, qhash, index + 1, [0, top, 1, end]))
            status = ('cover' if index == 0 else 'questions' if local else
                      'blank_declared' if 'BLANK PAGE' in text else
                      'front_matter' if anchors and index + 1 < anchors[0]['page'] and text.strip() else
                      'needs_review')
            if not text.strip():
                status = 'needs_ocr'
            elif any(rect.get_area() > .35 * page.rect.get_area()
                     for image in page.get_images()
                     for rect in page.get_image_rects(image[0])):
                status = 'image_body_needs_review'
            if status == 'needs_review' and index + 1 in _QP_REFERENCE_PAGES.get((paper, qhash), ()):
                status = 'reference'
                references.append(_region(qp_ref, qhash, index + 1, [0, 0, 1, 1]))
            qp_pages.append({'page': index + 1, 'status': status,
                             'question_starts': [a['number'] for a in local]})
            if status in ('needs_review', 'needs_ocr', 'image_body_needs_review'):
                exceptions.append({'reason': status, 'source': 'qp', 'page': index + 1})
        questions = []
        # An uncertain anchor invalidates the segmentation, not just one answer.
        if sequence == list(range(1, 41)) and not any(e['reason'] in ('duplicate_or_conflicting_key', 'missing_official_keys') for e in exceptions):
            for index, anchor in enumerate(anchors):
                next_anchor = anchors[index + 1] if index + 1 < len(anchors) else None
                end_page = next_anchor['page'] if next_anchor else anchor['page']
                regions = []
                for p in range(anchor['page'], end_page + 1):
                    lo = max(0, anchor['top'] - .006) if p == anchor['page'] else .06
                    hi = next_anchor['top'] - .006 if next_anchor and p == next_anchor['page'] else .94
                    if hi > lo:
                        regions.append(_region(qp_ref, qhash, p, [0, lo, 1, hi]))
                section_contexts = shared if paper.startswith('9701_') and anchor['number'] >= 31 else []
                contexts = references + section_contexts
                reasons = ['independent_visual_and_mapping_review_required']
                if section_contexts:
                    reasons.append('shared_context_requires_review')
                elif paper.startswith('9701_') and anchor['number'] >= 31 and re.search(r'Section\s+B', '\n'.join(p.get_text() for p in qdoc), re.I):
                    reasons.append('missing_shared_context')
                    exceptions.append({'reason': 'missing_shared_context', 'question': anchor['number']})
                if len(regions) > 1:
                    reasons.append('multiple_pages_require_review')
                questions.append({'id': f'{paper}_q{anchor["number"]}',
                    'official_qid': f'{paper}_q{anchor["number"]}', 'part': '', 'kind': 'mcq',
                    'answer': key[anchor['number']]['answer'], 'marks': 1,
                    'regions': regions, 'context_regions': contexts,
                    'mark_scheme_regions': [key[anchor['number']]['region']],
                    'review_reasons': reasons, 'explanation_policy': 'on_demand',
                    'source_text_authority': 'original_pdf_pixels', 'teaching_approved': False})
        return {'schema_version': 1, 'profile': PROFILE, 'paper': paper,
                'status': 'needs_review' if exceptions else 'prepared_unreviewed',
                'teaching_approved': False, 'sources': {
                    'qp': {'reference': qp_ref, 'sha256': qhash, 'pages': len(qdoc)},
                    'ms': {'reference': ms_ref, 'sha256': mhash, 'pages': len(mdoc)}},
                'questions': questions, 'qp_pages': qp_pages, 'ms_pages': ms_pages,
                'exceptions': exceptions,
                'publication_gates': ['independent_source_and_visual_review', 'syllabus_and_kc_mapping',
                                      'exact_review_binding', 'supported_manager_admission', 'learner_routes']}


def _png(page_image, box):
    width, height = page_image.size
    bounds = [round(box[0] * width), round(box[1] * height),
              round(box[2] * width), round(box[3] * height)]
    cropped = page_image.crop(bounds)
    stream = io.BytesIO()
    cropped.save(stream, format='PNG')
    return stream.getvalue()


def render_regions(raw: bytes, regions: list[dict], dpi: int = 144, *, reuse_pages: bool = True) -> tuple[list[bytes], int]:
    """Same renderer in both evaluation arms; bounded, invocation-local page cache."""
    if type(dpi) is not int or not 72 <= dpi <= 240:
        raise ValueError('dpi must be an integer between 72 and 240')
    images, result, renders = {}, [], 0
    with pymupdf.open(stream=raw, filetype='pdf') as doc:
        for region in regions:
            n = region['page']
            box = region['box']
            if (type(n) is not int or not 1 <= n <= len(doc) or len(box) != 4
                    or not all(isinstance(v, (float, int)) and 0 <= v <= 1 for v in box)
                    or not box[0] < box[2] or not box[1] < box[3]):
                raise ValueError('invalid source region')
            if n not in images:
                pix = doc[n - 1].get_pixmap(dpi=dpi, alpha=False)
                images[n] = Image.frombytes('RGB', [pix.width, pix.height], pix.samples)
                renders += 1
            result.append(_png(images[n], box))
            if not reuse_pages:
                images.pop(n)
        for img in images.values():
            img.close()
    return result, renders


def _paper(library, qp_ref, ms_ref):
    qname = Path(library.record(qp_ref)['path']).name
    mname = Path(library.record(ms_ref)['path']).name
    q, m = NATIVE_NAME.fullmatch(qname), NATIVE_NAME.fullmatch(mname)
    if (not q or not m or q.group(3) != 'qp' or m.group(3) != 'ms'
            or (q.group(1), q.group(2), q.group(4)) != (m.group(1), m.group(2), m.group(4))):
        raise ValueError('registered source identity does not match a supported native QP/MS pair')
    return '_'.join([q.group(1), q.group(2), q.group(4)])


def prepare(vault: Path, qp_ref: str, ms_ref: str, output: Path, dpi: int = 144) -> dict:
    """Write one fresh bundle. COMPLETE is written last; no overwrite or publication."""
    start = time.perf_counter()
    output = Path(output)
    if output.exists() or output.is_symlink():
        raise FileExistsError(f'output exists: {output}')
    library = AssetLibrary(Path(vault))
    # Refuse writes into protected source or learner state, including path aliases.
    resolved = output.resolve()
    protected = [Path(vault).resolve(), (Path(__file__).resolve().parents[2] / 'STEM Tutor').resolve()]
    if any(resolved == p or p in resolved.parents for p in protected):
        raise ValueError('output must be outside the source and production learner vaults')
    # Retain the checked destination; directory adapters can change during analysis.
    output = resolved
    paper = _paper(library, qp_ref, ms_ref)
    qp, ms = library.read(qp_ref), library.read(ms_ref)
    bundle = analyse_pair(qp, ms, paper, qp_ref, ms_ref)
    output.mkdir(parents=True, exist_ok=False)
    media, public, private, render_counts = {}, set(), set(), {}
    requests = {'qp': {}, 'ms': {}}
    for row in bundle['questions']:
        for field, role, visible in [('regions', 'qp', True), ('context_regions', 'qp', True),
                                     ('mark_scheme_regions', 'ms', False)]:
            refs = []
            for region in row[field]:
                identity = json.dumps(region, sort_keys=True, separators=(',', ':'))
                name = f'{role}/{sha(identity.encode())[:24]}.png'
                requests[role][name] = region
                (public if visible else private).add(name)
                refs.append(name)
            row[field.removesuffix('_regions') + '_media' if field != 'regions' else 'question_media'] = refs
    for role, raw in [('qp', qp), ('ms', ms)]:
        (output / role).mkdir()
        names = list(requests[role])
        data, count = render_regions(raw, list(requests[role].values()), dpi)
        render_counts[role] = count
        for name, image in zip(names, data):
            path = output / name
            path.write_bytes(image)
            media[name] = {'sha256': sha(image), 'bytes': len(image), 'region': requests[role][name],
                           'visibility': 'public_question' if role == 'qp' else 'private_answer'}
    bundle.update(media=media, public_media=sorted(public), private_media=sorted(private),
                  metrics={'elapsed_seconds': time.perf_counter() - start, 'page_renders': render_counts,
                           'model_calls': 0, 'dpi': dpi, 'renderer': 'PyMuPDF ' + pymupdf.VersionBind})
    manifest = json.dumps(bundle, ensure_ascii=False, indent=2).encode() + b'\n'
    (output / 'bundle.json').write_bytes(manifest)
    (output / 'COMPLETE').write_text(sha(manifest) + '\n')
    return bundle


def verify_bundle(output: Path) -> dict:
    output = Path(output)
    try:
        raw = (output / 'bundle.json').read_bytes()
        expected = (output / 'COMPLETE').read_text().strip()
    except OSError as exc:
        raise ValueError('incomplete preparation bundle') from exc
    if sha(raw) != expected:
        raise ValueError('bundle manifest digest mismatch')
    bundle = json.loads(raw)
    if (bundle.get('schema_version') != 1 or bundle.get('profile') != PROFILE
            or not PAPER.fullmatch(bundle.get('paper', ''))
            or bundle.get('status') not in ('prepared_unreviewed', 'needs_review')
            or bundle.get('teaching_approved') is not False
            or not isinstance(bundle.get('questions'), list) or not isinstance(bundle.get('media'), dict)):
        raise ValueError('invalid preparation bundle schema')
    referenced, public, private = set(), set(), set()
    for row in bundle['questions']:
        for field, visible in [('question_media', True), ('context_media', True), ('mark_scheme_media', False)]:
            if not isinstance(row.get(field), list) or (field != 'context_media' and not row[field]):
                raise ValueError('invalid or missing question media')
            for name in row[field]:
                if not isinstance(name, str):
                    raise ValueError('invalid question media path')
                referenced.add(name)
                (public if visible else private).add(name)
    if (set(bundle['media']) != referenced or public & private
            or set(bundle.get('public_media', [])) != public
            or set(bundle.get('private_media', [])) != private):
        raise ValueError('bundle media references do not match its complete media map')
    for name, item in bundle['media'].items():
        relative = Path(name)
        if not re.fullmatch(r'(qp|ms)/[a-f0-9]{24}\.png', name):
            raise ValueError('unsafe bundle media path')
        target = output / relative
        if any((output / Path(*relative.parts[:n])).is_symlink() for n in range(1, len(relative.parts) + 1)):
            raise ValueError('symlink in bundle media path')
        if target.is_symlink() or not target.is_file() or sha(target.read_bytes()) != item['sha256']:
            raise ValueError(f'media digest mismatch: {name}')
        with Image.open(target) as img:
            img.verify()
        with Image.open(target) as img:
            img.load()
    return {'status': bundle['status'], 'questions': len(bundle['questions']),
            'media': len(bundle['media']), 'exceptions': len(bundle['exceptions']), 'manifest_sha256': sha(raw)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    build = sub.add_parser('prepare', help='create an unpublished source-bound bundle')
    build.add_argument('--vault', type=Path, required=True)
    build.add_argument('--qp', required=True, help='registered asset reference')
    build.add_argument('--ms', required=True, help='registered asset reference')
    build.add_argument('--output', type=Path, required=True)
    build.add_argument('--dpi', type=int, default=144)
    check = sub.add_parser('verify', help='check completed bundle and every image digest')
    check.add_argument('output', type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == 'verify':
            result = verify_bundle(args.output)
        else:
            bundle = prepare(args.vault, args.qp, args.ms, args.output, args.dpi)
            result = {'output': str(args.output.resolve()), 'paper': bundle['paper'],
                      **verify_bundle(args.output), 'metrics': bundle['metrics']}
        print(json.dumps(result, indent=2))
        return 0
    except (OSError, ValueError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
