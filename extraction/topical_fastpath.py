#!/usr/bin/env python3
"""Prepare topical question images with page accounting and explicit exceptions.

No provider, manager job, Library registration, publication or learner writes.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import re
import sys
import time

import pymupdf
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent / 'src')]
from tutorlib.asset_library import AssetLibrary
from fastpath import _png, sha
from topical_ial import find_anchors as sme_anchors
from topical_caie import find_anchors as caie_anchors
from topical_pmt import find_anchors as pmt_anchors, registered_course as pmt_course

COURSES = {'9701', '9702', 'P1', 'P2', 'P3', 'P4', 'FP1', 'FP2', 'FP3', 'M1', 'D1', 'S1', 'S2', 'S3'}
STOPS = {'cover', 'front_matter', 'answer', 'answer_section', 'lesson_notes',
         'missing_text', 'unsupported', 'unanchored', 'blank'}
PRIVATE = {'answer', 'answer_section'}


def analyse_source(raw: bytes, course: str, source_id: str, *, exclusions=(), source_path=None, ocr_cache=None) -> dict:
    digest = sha(raw)
    with pymupdf.open(stream=raw, filetype='pdf') as doc:
        rules = [r for r in exclusions if r['source_id'] == source_id]
        if any(r['source_sha256'] != digest for r in rules):
            raise ValueError('exclusion source digest mismatch; review rule before applying')
        base = {'schema_version': 1, 'kind': 'topical_preparation', 'course': course,
                'source': {'id': source_id, 'sha256': digest, 'pages': len(doc)},
                'teaching_approved': False, 'questions': [], 'pages': [], 'review_pages': [],
                'private_pages': [], 'issues': [], 'profile': 'unsupported'}
        if rules:
            return {**base, 'status': 'excluded', 'exclusion': rules,
                    'pages': [{'page': n, 'status': 'excluded'} for n in range(1, len(doc) + 1)]}
        # Opaque raster answers can carry the same Qn/header geometry as questions.
        # Registered source role must precede visual-layout routing.
        role_path = str(source_path or source_id).replace('\\', '/').lower()
        if re.search(r'(?:^|/)[^/]*\banswers?\b[^/]*(?:/|$)|mark[ _-]*schemes?|(?:_ms|\.ms|\bms)\.pdf$', role_path):
            return {**base, 'status': 'private_answers_only', 'profile': 'registered_answer_source',
                    'pages': [{'page': n, 'status': 'private_answers'} for n in range(1, len(doc) + 1)],
                    'private_pages': [{'page': n, 'region': {'source_id': source_id, 'source_sha256': digest,
                                       'page': n, 'box': [0, 0, 1, 1]}} for n in range(1, len(doc) + 1)]}
        is_pmt = pmt_course(source_path) is not None
        detected = (pmt_anchors(doc, course, source_path) if is_pmt else
                    sme_anchors(doc, course) if course in COURSES else
                    {'anchors': [], 'issues': ['unsupported_course']})
        if (not is_pmt and not detected.get('anchors') and 'declared_question_count' not in detected
                and course in ('9701', '9702') and not detected.get('page_roles')):
            detected = caie_anchors(doc, course)
        if not is_pmt and not detected.get('anchors') and ocr_cache is not None:
            from topical_ocr import find_anchors_from_cache
            cached = find_anchors_from_cache(raw, source_id, Path(ocr_cache))
            if cached.get('anchors') and cached.get('source_course') == course and course in COURSES:
                detected = cached
            elif cached.get('anchors'):
                detected['issues'] = list(detected.get('issues', [])) + [{'reason': 'ocr_source_course_conflict',
                    'source_course': cached.get('source_course'), 'requested_course': course}]
            else:
                detected['issues'] = list(detected.get('issues', [])) + list(cached.get('issues', []))
        base['profile'] = detected.get('profile', 'unsupported')
        base['detector'] = detected
        base['issues'] = list(detected.get('issues', []))
        by_page = defaultdict(list)
        for anchor in detected.get('anchors', []):
            if anchor.get('candidate_unit') == 'page_fragment':
                continue
            if (type(anchor.get('page')) is not int or not 1 <= anchor['page'] <= len(doc)
                    or not 0 <= anchor['top'] < anchor['bottom'] <= 1):
                raise ValueError('invalid topical anchor geometry')
            by_page[anchor['page']].append(anchor)
        active = None
        for n in range(1, len(doc) + 1):
            role = detected.get('page_roles', {}).get(str(n), 'unanchored')
            if (role in {'question', 'question_content', 'continuation', 'content'}
                    and n not in detected.get('validated_ocr_pages', []) and not doc[n - 1].get_text().strip()):
                role = 'missing_text'
            anchors = sorted(by_page[n], key=lambda a: a['top'])
            page = {'page': n, 'profile_role': role, 'question_starts': len(anchors)}
            def region(lo=0, hi=1):
                return {'source_id': source_id, 'source_sha256': digest, 'page': n,
                        'box': [0, round(lo, 8), 1, round(hi, 8)]}
            if role in STOPS:
                active = None
                page['status'] = 'private_answers' if role in PRIVATE else role
                if role in PRIVATE:
                    base['private_pages'].append({'page': n, 'region': region()})
                elif role not in {'cover', 'front_matter', 'blank', 'lesson_notes'}:
                    base['review_pages'].append({'page': n, 'reason': role, 'region': region()})
                base['pages'].append(page)
                continue
            if not anchors:
                if active is not None and role in {'question', 'question_content', 'continuation', 'content'}:
                    active['regions'].append(region())
                    page['status'] = 'continuation'
                else:
                    page['status'] = 'unsegmented'
                    base['review_pages'].append({'page': n, 'reason': 'no_verified_question_boundary', 'region': region()})
                    active = None
                base['pages'].append(page)
                continue
            prefix_end = max(0, anchors[0]['top'] - .004)
            prefix = region(0, prefix_end) if prefix_end > 0 else None
            context = []
            if prefix:
                if active is not None:
                    active['regions'].append(prefix)
                else:
                    context = [prefix]
            for index, anchor in enumerate(anchors):
                lo = max(0, anchor['top'] - .004)
                hi = max(lo, anchors[index + 1]['top'] - .004) if index + 1 < len(anchors) else 1
                if hi <= lo:
                    raise ValueError('overlapping topical question anchors')
                location = json.dumps({'source_sha256': digest, 'page': n, 'top': anchor['top'],
                                       'section': anchor.get('section'), 'compilation_page': anchor.get('compilation_page')}, sort_keys=True)
                if anchor.get('candidate_unit') == 'review_fragment':
                    base['review_pages'].append({'page': n, 'reason': 'raster_question_fragment',
                                                 'region': region(0 if index == 0 and context else lo, hi)})
                    active = None
                    continue
                official = anchor.get('official_qid')
                kind = anchor.get('question_type') or ('mcq' if official and re.search(r'_1\d_q', official) else 'unknown')
                active = {'id': 'occurrence-' + sha(location.encode())[:24], 'official_qid': official,
                          'part': anchor.get('part', ''), 'label': anchor['label'],
                          'section': anchor.get('section'), 'kind': kind,
                          'regions': [region(lo, hi)], 'context_regions': context if index == 0 else [],
                          'answer': None, 'answer_status': 'missing', 'explanation_policy': 'on_demand',
                          'review_reasons': ['independent_source_visual_review', 'answer_or_rubric_required',
                                             'syllabus_mapping_required'], 'teaching_approved': False}
                base['questions'].append(active)
            page['status'] = ('mixed_review_regions' if any(
                a.get('candidate_unit') == 'review_fragment' for a in anchors) else 'question_regions')
            base['pages'].append(page)
        qualified = detected.get('segmentation_status') == 'qualified'
        # CAIE marker profiles do not establish complete ordered-question coverage.
        # They remain provisional unless their detector explicitly qualifies it.
        base['status'] = ('segmented_unreviewed' if base['questions'] and qualified and not base['review_pages']
                          else 'needs_review' if base['questions'] else 'unsegmented')
        base['segmented_question_occurrences'] = len(base['questions'])
        base['missing_answer_occurrences'] = len(base['questions'])
        base['declared_question_count'] = detected.get('declared_question_count')
        return base


def prepare(vault: Path, source_id: str, course: str, output: Path, *, dpi=120, exclusions=(), ocr_cache=None) -> dict:
    if type(dpi) is not int or not 72 <= dpi <= 200:
        raise ValueError('dpi must be an integer from 72 to 200')
    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError(f'output exists: {output}')
    protected = [Path(vault).resolve(), (HERE.parents[1] / 'STEM Tutor').resolve()]
    if any(output == p or p in output.parents for p in protected):
        raise ValueError('output must be outside source and production learner vaults')
    start = time.perf_counter()
    library = AssetLibrary(Path(vault))
    raw = library.read(source_id)
    record = library.record(source_id)
    declared_course = record.get('course')
    if declared_course is None:
        match = re.search(r'(?:^|/)Courses/([^/]+)/', record['path'])
        declared_course = match[1] if match else None
    if declared_course is not None and str(declared_course) != course:
        raise ValueError('requested course conflicts with registered source course')
    if not source_id.startswith('asset:'):
        source_id = next('asset:' + key for key, item in library.records().items() if item['path'] == record['path'])
    bundle = analyse_source(raw, course, source_id, exclusions=exclusions,
                            source_path=record['path'], ocr_cache=ocr_cache)
    requests = {}
    def add(regions, visibility):
        names = []
        for region in regions:
            key = json.dumps(region, sort_keys=True, separators=(',', ':'))
            name = visibility + '/' + sha(key.encode())[:24] + '.png'
            requests[name] = {'region': region, 'visibility': visibility}
            names.append(name)
        return names
    for q in bundle['questions']:
        q['question_media'] = add(q['regions'], 'questions')
        q['context_media'] = add(q['context_regions'], 'context')
    for item in bundle['review_pages']:
        item['media'] = add([item['region']], 'review')
    for item in bundle['private_pages']:
        item['media'] = add([item['region']], 'private')
    output.mkdir(parents=True, exist_ok=False)
    groups = defaultdict(list)
    for name, item in requests.items():
        groups[item['region']['page']].append((name, item))
    media = {}
    # One full page resident at a time, including large compilation PDFs.
    with pymupdf.open(stream=raw, filetype='pdf') as doc:
        for n, group in sorted(groups.items()):
            pix = doc[n - 1].get_pixmap(dpi=dpi, alpha=False)
            image = Image.frombytes('RGB', [pix.width, pix.height], pix.samples)
            for name, item in group:
                data = _png(image, item['region']['box'])
                path = output / name
                path.parent.mkdir(exist_ok=True)
                path.write_bytes(data)
                media[name] = {**item, 'sha256': sha(data), 'bytes': len(data)}
            image.close()
    bundle['media'] = media
    bundle['metrics'] = {'elapsed_seconds': time.perf_counter() - start, 'dpi': dpi,
                         'page_renders': len(groups), 'model_calls': 0}
    data = json.dumps(bundle, indent=2, ensure_ascii=False).encode() + b'\n'
    (output / 'bundle.json').write_bytes(data)
    (output / 'COMPLETE').write_text(sha(data) + '\n')
    return bundle


def verify_bundle(output: Path) -> dict:
    output = Path(output)
    try:
        raw = (output / 'bundle.json').read_bytes()
        expected = (output / 'COMPLETE').read_text().strip()
    except OSError as exc:
        raise ValueError('incomplete topical preparation') from exc
    if sha(raw) != expected:
        raise ValueError('manifest digest mismatch')
    bundle = json.loads(raw)
    if bundle.get('kind') != 'topical_preparation' or bundle.get('schema_version') != 1 or bundle.get('teaching_approved') is not False:
        raise ValueError('invalid topical preparation schema')
    refs = set()
    covered = defaultdict(list)
    def bind(regions, names, visibility):
        if len(regions) != len(names):
            raise ValueError('incomplete coverage media binding')
        for region, name in zip(regions, names):
            item = bundle['media'].get(name)
            if not item or item.get('region') != region or item.get('visibility') != visibility:
                raise ValueError('invalid coverage media binding')
            if (region.get('source_id') != bundle['source']['id']
                    or region.get('source_sha256') != bundle['source']['sha256']):
                raise ValueError('invalid coverage source binding')
            box = region.get('box')
            if (not isinstance(box, list) or len(box) != 4 or box[0] != 0 or box[2] != 1
                    or not 0 <= box[1] < box[3] <= 1):
                raise ValueError('invalid coverage geometry')
            covered[region['page']].append((box[1], box[3], visibility))
    for q in bundle['questions']:
        if not q['question_media']:
            raise ValueError('missing question media')
        refs.update(q['question_media'] + q['context_media'])
        bind(q['regions'], q['question_media'], 'questions')
        bind(q['context_regions'], q['context_media'], 'context')
    for field, visibility in [('review_pages', 'review'), ('private_pages', 'private')]:
        for item in bundle[field]:
            refs.update(item['media'])
            bind([item['region']], item['media'], visibility)
    if refs != set(bundle['media']):
        raise ValueError('incomplete media references')
    for name, item in bundle['media'].items():
        if not re.fullmatch(r'(questions|context|private|review)/[a-f0-9]{24}\.png', name):
            raise ValueError('unsafe media path')
        path = output / name
        if path.is_symlink() or path.parent.is_symlink():
            raise ValueError('symlink media path')
        if not path.is_file() or sha(path.read_bytes()) != item['sha256']:
            raise ValueError('media digest mismatch')
        with Image.open(path) as image:
            image.verify()
        with Image.open(path) as image:
            image.load()
    count = bundle['source']['pages']
    if [p['page'] for p in bundle['pages']] != list(range(1, count + 1)):
        raise ValueError('incomplete page coverage ledger')
    detector_starts = defaultdict(list)
    for anchor in bundle.get('detector', {}).get('anchors', []):
        if anchor.get('candidate_unit') != 'page_fragment':
            detector_starts[anchor['page']].append(anchor)
    expected_review = defaultdict(list)
    for n, starts in detector_starts.items():
        starts.sort(key=lambda anchor: anchor['top'])
        for index, anchor in enumerate(starts):
            if anchor.get('candidate_unit') != 'review_fragment':
                continue
            # Match analyse_source's crop convention. A first fragment may
            # additionally retain the page prefix, but its full core interval
            # must remain in review even if materialized bindings are moved.
            lo = max(0, anchor['top'] - .004)
            hi = max(lo, starts[index + 1]['top'] - .004) if index + 1 < len(starts) else 1
            expected_review[n].append((round(lo, 8), round(hi, 8)))
    for page in bundle['pages']:
        status, n = page['status'], page['page']
        for fragment_lo, fragment_hi in expected_review[n]:
            if status != 'mixed_review_regions':
                raise ValueError('detector review fragment has invalid page role')
            end = fragment_lo
            for lo, hi, visibility in sorted(covered[n]):
                if visibility != 'review' or hi <= end:
                    continue
                if lo > end + 1e-7:
                    break
                end = max(end, hi)
            if end < fragment_hi - 1e-7:
                raise ValueError('detector review fragment missing review coverage')
        if status in {'cover', 'front_matter', 'blank', 'lesson_notes', 'excluded'}:
            continue
        required = ({'private'} if status == 'private_answers' else
                    {'questions', 'context'} if status in {'question_regions', 'continuation'} else
                    {'questions', 'context', 'review'} if status == 'mixed_review_regions' else {'review'})
        if status == 'mixed_review_regions':
            public = [(lo, hi) for lo, hi, visibility in covered[n]
                      if visibility in {'questions', 'context'}]
            review = [(lo, hi) for lo, hi, visibility in covered[n] if visibility == 'review']
            if any(min(public_hi, review_hi) > max(public_lo, review_lo) + 1e-7
                   for public_lo, public_hi in public for review_lo, review_hi in review):
                raise ValueError('public and review regions overlap')
        end = 0
        for lo, hi, visibility in sorted(covered[n]):
            if visibility not in required or lo > end + 1e-7:
                raise ValueError('page coverage has a gap or visibility conflict')
            end = max(end, hi)
        if end < 1 - 1e-7:
            raise ValueError('page coverage missing preserved content')
    return {'status': bundle['status'], 'questions': len(bundle['questions']),
            'review_pages': len(bundle['review_pages']), 'private_pages': len(bundle['private_pages']),
            'pages_accounted': count, 'media': len(refs), 'manifest_sha256': sha(raw)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    build = sub.add_parser('prepare')
    build.add_argument('--vault', type=Path, required=True)
    build.add_argument('--source', required=True)
    build.add_argument('--course', required=True)
    build.add_argument('--output', type=Path, required=True)
    build.add_argument('--dpi', type=int, default=120)
    build.add_argument('--exclusions', type=Path)
    build.add_argument('--ocr-cache', type=Path, help='optional existing source-bound OCR cache; never generates OCR')
    check = sub.add_parser('verify')
    check.add_argument('output', type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == 'verify':
            result = verify_bundle(args.output)
        else:
            exclusions = json.loads(args.exclusions.read_text()) if args.exclusions else []
            bundle = prepare(args.vault, args.source, args.course, args.output, dpi=args.dpi,
                             exclusions=exclusions, ocr_cache=args.ocr_cache)
            result = {**verify_bundle(args.output), 'output': str(args.output.resolve()), 'metrics': bundle['metrics']}
        print(json.dumps(result, indent=2))
        return 0
    except (OSError, ValueError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
