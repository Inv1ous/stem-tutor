"""Conservative cleaner for Edexcel question images (blank answer pages, trailing answer lines).

Originals in ``Library/SourcePractice/Media`` are never touched.  Every image gets a decision:

  keep      unchanged (also every borderline case: when unsure the image is kept)
  crop      trailing ruled answer lines (and the page footer under them) cut away
  collapse  a long ruled answer band between two parts of the question squeezed to a small gap
  remove    the page holds only ruled answer lines ("Question 4 continued") - no question content

``crop``/``collapse`` write a NEW PNG named by its own sha256 under the output directory; the sidecar
``image_cleaning.json`` maps original -> decision, parameters and cleaned file.  An item never loses its
last image: ``resolve`` falls back to the original when every image of an item was removed.

    .venv/bin/python build/clean_question_images.py [--limit N] [--courses P1,P2,...]
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import io
import json
import os
import random
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(Path(__file__).resolve().parent))

WORK = ROOT.parent / 'Work/Preparation/source-migration'
DEFAULT_VAULT = Path(os.environ.get('STEM_TUTOR_VAULT') or ROOT.parent / 'STEM Tutor')
SCHEMA = 1
NON_EDEXCEL = {'9701', '9702'}

PARAMS = {
    'ink': 215,               # gray level below which a pixel is ink (answer lines are ~170, text ~0-120)
    'frame_ink': 205,         # printed page-frame rules are thin mid-grey
    'line_fraction': 0.70,    # a ruled line: this fraction of the content width is ink on a thin row group
    'line_max_thickness': 7,
    'min_trailing_lines': 3,
    'min_collapse_lines': 6,
    'spacing_tolerance': 3,   # px deviation of line spacing within one ruled block
    'band_gap': 14,           # ink rows closer than this belong to one text band
    'min_band_ink': 12,       # fewer ink pixels than this is scanner noise, not content
    'crop_pad': 22,           # blank px kept under the last content band
    'collapse_gap': 28,
    'header_max_height': 70,  # "Question 4 continued" label
    'header_max_width': 0.55,
    'header_zone': 0.12,      # header band must start within the top fraction of the frame
    'min_saving': 0.08,       # do not crop for less than this fraction of the height
    'min_remaining': 0.12,    # never keep less than this fraction (guards over-cropping)
    'min_blank_lines': 6,
}


# ---- exam cover / instruction pages -------------------------------------------------------------------------------
COVER_MARKERS = {
    'candidate_surname': r'candidate\s*s[a-z]{3,6}me\b',          # "Candidate surname" (OCR: "sumame")
    'other_names': r'\bother\s+names\b',
    'centre_number': r'cent[rt]e\s*numbe',
    'candidate_number': r'candidate\s*number',
    'paper_reference': r'paper\s*reference',
    'check_details': r'check\s+the\s+examination\s+details',
    'write_name': r'write\s+your\s+name\s+here',
    'you_must_have': r'you\s+must\s+have\s*:',
    'total_marks_box': r'^total\s+marks\s*$',
    'calculator_notice': r'candidates\s+may\s+use\s+any\s+calculator',
    'fill_boxes': r'fill\s+in\s+the\s+boxes\s+at\s+the\s+top',
    'do_not_open': r'do\s+not\s+open\s+this\s+question\s+paper',
    'instructions_head': r'^instructions\s*$',
    'information_head': r'^information\s*$',
    'advice_head': r'^advice\s*$',
    # topic-booklet title pages (PhysicsAndMathsTutor "Information for Candidates" sheets)
    'info_for_candidates': r'information\s+for\s+c\S*ndidates',
    'advice_to_candidates': r'advice\s+to\s+c\S*ndidates',
    'questions_in_test': r'there\s+are\s+\d+\s+questions?\s+in\s+th',
    'calculators_not_used': r'calculators\s+may\s+not\s+be\s+used',
}
COVER_MIN_MARKERS = 3


def cover_markers(text: str) -> list[str]:
    """Names of the cover-page phrases present in OCR text (pure, case-insensitive, line aware)."""
    lines = [re.sub(r'\s+', ' ', ln).strip().lower() for ln in text.splitlines()]
    flat = ' '.join(lines)
    found = []
    for name, pattern in COVER_MARKERS.items():
        if (any(re.search(pattern, ln) for ln in lines) if pattern.startswith('^') else re.search(pattern, flat)):
            found.append(name)
    return found


def is_cover_text(text: str) -> bool:
    return len(cover_markers(text)) >= COVER_MIN_MARKERS


OCR_BIN = WORK / 'bin/ocr_batch'


def ocr_texts(vault: Path, entries: list[dict], cache_path: Path, binary: Path = OCR_BIN) -> dict[str, str]:
    """Literal on-device OCR text per original sha256, cached on disk (the images are immutable, so the cache is exact).
    Compiles ``build/ocr_batch.swift`` into ``Work`` on first use; returns {} if Apple Vision is unavailable."""
    cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}
    todo = [e for e in entries if e['original_sha256'] not in cache]
    if todo:
        if not binary.exists():
            source = Path(__file__).with_name('ocr_batch.swift')
            binary.parent.mkdir(parents=True, exist_ok=True)
            built = subprocess.run(['swiftc', '-O', str(source), '-o', str(binary)], capture_output=True)
            if built.returncode:
                return {}
        by_path = {str(Path(vault) / e['original']): e['original_sha256'] for e in todo}
        done = subprocess.run([str(binary)], input='\n'.join(by_path).encode(), capture_output=True)
        for line in done.stdout.decode().splitlines():
            row = json.loads(line)
            cache[by_path[row['path']]] = row['text']
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = cache_path.with_suffix('.tmp')
        tmp.write_text(json.dumps(cache, sort_keys=True))
        os.replace(tmp, cache_path)
    return cache


def mark_covers(vault: Path, images: dict, cache_path: Path) -> dict:
    """Turn every non-removed image that OCR shows to be an exam cover/instruction page into a ``remove`` decision."""
    texts = ocr_texts(vault, [e for e in images.values() if e['decision'] != 'remove'], cache_path)
    caught = 0
    for entry in images.values():
        text = texts.get(entry['original_sha256'])
        if entry['decision'] != 'remove' and text is not None and is_cover_text(text):
            entry.update(was=entry['decision'], was_reason=entry['reason'], decision='remove', reason='exam_cover_page',
                         borderline=False, cleaned=None, cover_markers=cover_markers(text))
            entry.pop('pieces', None)
            caught += 1
    return {'ocr_available': bool(texts) or not images, 'caught': caught}


def _groups(mask_rows: np.ndarray, gap: int = 1):
    """Consecutive True runs of a 1-D boolean array as (start, end_exclusive), merging gaps < ``gap``+1."""
    idx = np.flatnonzero(mask_rows)
    if idx.size == 0:
        return []
    out, start, prev = [], idx[0], idx[0]
    for i in idx[1:]:
        if i - prev > gap:
            out.append((int(start), int(prev) + 1))
            start = i
        prev = i
    out.append((int(start), int(prev) + 1))
    return out


def find_frame(gray: np.ndarray, p: dict):
    """Printed answer-page frame -> (x0, x1, y0, y1) just inside the printed rules, or None for bare crops.

    The frame is a thin grey rectangle plus, on answer pages, a vertical rule that closes the writing column
    (the 'DO NOT WRITE IN THIS AREA' margin lies beyond it and is excluded from analysis)."""
    h, w = gray.shape
    if w < 900 or h < 1200:
        return None
    dark = gray < p['frame_ink']
    cols = np.flatnonzero(dark.sum(0) > 0.55 * h)
    rows = np.flatnonzero(dark.sum(1) > 0.55 * w)
    left = cols[cols < w * 0.4]
    right = cols[cols > w * 0.6]
    if not left.size or not right.size:
        return None
    x0, x1 = int(left.max()) + 3, int(right.min()) - 2
    y0 = 0
    top = rows[rows < h * 0.12]
    if top.size:
        y0 = int(top.max()) + 3
    y1 = h
    bottom = rows[rows > h * 0.88]
    if bottom.size:
        y1 = int(bottom.min()) - 2
    if x1 - x0 < 0.5 * w or y1 - y0 < 0.4 * h:
        return None
    return x0, x1, y0, y1


def analyze(gray: np.ndarray, params: dict | None = None) -> dict:
    """Decide what to do with one image.  Pure function of pixels and parameters."""
    p = dict(PARAMS, **(params or {}))
    h, w = gray.shape
    frame = find_frame(gray, p)
    x0, x1, y0, y1 = frame if frame else (int(w * 0.03), int(w * 0.97), 0, h)
    sub = gray[y0:y1, x0:x1]
    ink = sub < p['ink']
    cw = ink.shape[1]
    fraction = ink.sum(1) / max(cw, 1)
    is_line_row = fraction >= p['line_fraction']
    line_groups = [g for g in _groups(is_line_row) if g[1] - g[0] <= p['line_max_thickness']]
    # anything thicker than a ruled line (solid rules, filled blocks) is content, not a line
    line_mask = np.zeros(ink.shape[0], bool)
    for a, b in line_groups:
        line_mask[max(a - 1, 0):b + 1] = True
    text = ink.copy()
    text[line_mask] = False
    text[:, :3] = False
    text[:, -3:] = False
    rows_with_ink = text.sum(1) >= 1
    bands = []
    for a, b in _groups(rows_with_ink, p['band_gap']):
        count = int(text[a:b].sum())
        if count < p['min_band_ink']:
            continue
        cols = np.flatnonzero(text[a:b].any(0))
        bands.append({'y0': a, 'y1': b, 'ink': count, 'x0': int(cols[0]), 'x1': int(cols[-1]) + 1})
    lines = [{'y0': a, 'y1': b, 'c': (a + b) / 2} for a, b in line_groups]
    metrics = {'size': [w, h], 'frame': list(map(int, (x0, x1, y0, y1))) if frame else None, 'lines': len(lines),
               'bands': len(bands), 'ink_density': round(float(ink.mean()), 4)}
    result = {'action': 'keep', 'reason': 'no_answer_lines', 'borderline': False, 'metrics': metrics, 'params': p}
    if len(lines) < 2:
        if not bands and ink.sum() == 0 and frame is None:
            result.update(reason='empty_image', borderline=True)   # entirely white: never silently drop
        return result

    def between(top, bottom):
        return [b for b in bands if b['y0'] < bottom and b['y1'] > top]

    # ruled blocks: consecutive lines with regular spacing and no text between them
    blocks, current = [], [lines[0]]
    for prev, line in zip(lines, lines[1:]):
        gap = line['c'] - prev['c']
        spaced = (len(current) < 2 or abs(gap - (current[-1]['c'] - current[-2]['c'])) <= p['spacing_tolerance'])
        if spaced and not between(prev['y1'], line['y0']) and gap < 90:
            current.append(line)
        else:
            blocks.append(current)
            current = [line]
    blocks.append(current)
    blocks = [b for b in blocks if len(b) >= 2]
    metrics['blocks'] = [len(b) for b in blocks]
    if not blocks:
        result.update(reason='lines_not_regular', borderline=len(lines) >= 4)
        return result
    inner_h = y1 - y0
    first_line = lines[0]['y0']
    ruled_lines = sum(len(b) for b in blocks)

    def header_like(b):
        return (b['y0'] < p['header_zone'] * inner_h + 40 and b['y1'] - b['y0'] <= p['header_max_height']
                and (b['x1'] - b['x0']) <= p['header_max_width'] * cw)

    content = [b for b in bands if not header_like(b)]
    # ---- (i) a page with only ruled answer lines ----
    if not content and ruled_lines >= p['min_blank_lines'] and len(bands) <= 2:
        result.update(action='remove', reason='ruled_answer_page_only')
        return result
    if not content and ruled_lines >= p['min_blank_lines']:
        result.update(reason='blank_page_with_unexpected_bands', borderline=True)
        return result
    if not content:
        result.update(reason='too_few_ruled_lines_to_call_blank', borderline=ruled_lines >= 3)
        return result
    # ---- (ii) trailing answer lines under the last content band ----
    last = max(content, key=lambda b: b['y1'])
    trailing = [ln for ln in lines if ln['y0'] > last['y1']]
    pieces = [(0, h)]
    decision = {}
    if len(trailing) >= p['min_trailing_lines'] and not between(last['y1'] + 1, y1):
        # only the lines+footer follow: footer text under the frame lies outside [y0, y1) and is dropped too
        cut = min(y0 + last['y1'] + p['crop_pad'], h)
        saving = 1 - cut / h
        if saving < p['min_saving']:
            result.update(reason='saving_too_small')
        elif cut / h < p['min_remaining']:
            result.update(reason='would_remove_most_of_image', borderline=True)
        else:
            pieces = [(0, cut)]
            decision = {'action': 'crop', 'reason': 'trailing_answer_lines', 'trailing_lines': len(trailing)}
    elif trailing:
        result.update(reason='few_trailing_lines', borderline=True)
    # ---- (iii) embedded answer block between content bands ----
    end = pieces[-1][1]
    collapsed = []
    ordered = sorted(content, key=lambda b: b['y0'])
    for above, below in zip(ordered, ordered[1:]):
        inside = [ln for ln in lines if ln['y0'] > above['y1'] and ln['y1'] < below['y0']]
        block = [b for b in blocks if any(ln in b for ln in inside)]
        if len(inside) >= p['min_collapse_lines'] and block and len(block[0]) >= p['min_collapse_lines']:
            top = y0 + above['y1'] + p['crop_pad'] // 2
            bottom = y0 + below['y0'] - p['crop_pad'] // 2
            removed = bottom - top - p['collapse_gap']
            if removed > 3 * p['collapse_gap'] and top < end:
                collapsed.append((top, top + p['collapse_gap'], bottom))
    if collapsed:
        # keep [0, top+gap) then continue at `bottom`; the gap is blank because the rows are only answer lines
        pieces, start = [], 0
        for top, keep_to, bottom in collapsed:
            pieces.append((start, keep_to))
            start = bottom
        pieces.append((start, end))
        decision = decision or {'action': 'collapse', 'reason': 'embedded_answer_lines'}
        if decision['action'] == 'crop':
            decision['collapsed_blocks'] = len(collapsed)
        else:
            decision['collapsed_blocks'] = len(collapsed)
    if decision:
        result.update(decision)
        result['pieces'] = [list(map(int, piece)) for piece in pieces]
        result['borderline'] = False
    return result


def apply(image: Image.Image, decision: dict) -> Image.Image:
    pieces = decision['pieces']
    parts = [image.crop((0, a, image.width, b)) for a, b in pieces]
    if len(parts) == 1:
        return parts[0]
    canvas = Image.new(image.mode, (image.width, sum(p.height for p in parts)), 255 if image.mode in 'LA' else (255,) * len(image.getbands()))
    y = 0
    for part in parts:
        canvas.paste(part, (0, y))
        y += part.height
    return canvas


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def png_bytes(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format='PNG', optimize=True)
    return buffer.getvalue()


def clean_one(vault: Path, relative: str, out_dir: Path, params=None, write: bool = True) -> dict:
    data = (Path(vault) / relative).read_bytes()
    image = Image.open(io.BytesIO(data))
    gray = np.array(image.convert('L'))
    decision = analyze(gray, params)
    entry = {'original': relative, 'original_sha256': sha256(data), 'size': [image.width, image.height],
             'decision': decision['action'], 'reason': decision['reason'], 'borderline': decision['borderline'],
             'metrics': decision['metrics'], 'cleaned': None}
    if decision['action'] in ('crop', 'collapse'):
        cleaned = apply(image, decision)
        blob = png_bytes(cleaned)
        name = sha256(blob) + '.png'
        entry['cleaned'] = {'file': name, 'sha256': sha256(blob), 'size': [cleaned.width, cleaned.height]}
        entry['pieces'] = decision['pieces']
        entry['decision_detail'] = {k: v for k, v in decision.items() if k in ('trailing_lines', 'collapsed_blocks')}
        if write:
            out_dir.mkdir(parents=True, exist_ok=True)
            target = out_dir / name
            if not target.exists():
                target.write_bytes(blob)
    return entry


def media_of(items, courses) -> dict[str, list[str]]:
    """Unique question/context image paths -> ids of items that use them."""
    uses: dict[str, list[str]] = {}
    for item in items:
        if item['course'] in courses:
            for key in ('question_media', 'context_media'):
                for ref in item.get(key, []):
                    uses.setdefault(ref, []).append(item['id'])
    return uses


def run(vault: Path, out: Path, *, courses=None, limit=None, release=None, params=None, write=True, ocr=True) -> dict:
    from source_topics import load_release  # shared sealed-release reader
    release, data = load_release(vault, release)
    allowed = set(courses) if courses else {i['course'] for i in data['items']} - NON_EDEXCEL
    uses = media_of(data['items'], allowed)
    paths = sorted(uses)[:limit]
    images = {}
    for ref in paths:
        entry = clean_one(vault, ref, out / 'cleaned', params, write)
        entry['used_by'] = sorted(set(uses[ref]))
        images[ref] = entry
    covers = mark_covers(vault, images, out / 'image_ocr_cache.json') if ocr else {'ocr_available': False, 'caught': 0}
    sidecar = {'schema_version': SCHEMA, 'release': release, 'generator': 'build/clean_question_images.py',
               'params': dict(PARAMS, **(params or {})), 'cleaned_dir': 'cleaned', 'images': images,
               'summary': summarize(images)}
    sidecar['covers'] = covers
    courses_of = {i['id']: i['course'] for i in data['items']}
    sidecar['cover_pages_by_course'] = dict(sorted(collections.Counter(
        courses_of[u] for e in images.values() if e['reason'] == 'exam_cover_page' for u in e['used_by']).items()))
    sidecar['kept_for_item_integrity'] = guard_last_image(data['items'], images, allowed)
    sidecar['items_losing_only_image_to_cover'] = sorted(
        i['id'] for i in data['items'] if i['course'] in allowed and only_cover_images(i, images))
    return sidecar


def _is_cover(images: dict, ref: str) -> bool:
    return images.get(ref, {}).get('reason') == 'exam_cover_page'


def only_cover_images(item: dict, images: dict) -> bool:
    """True when the item has question/context images and every one is a cover page."""
    refs = item.get('question_media', []) + item.get('context_media', [])
    return bool(refs) and all(_is_cover(images, r) for r in refs)


def guard_last_image(items, images, courses) -> list[str]:
    """Items whose every image would be removed keep their originals (an item is never imageless)."""
    saved = []
    for item in items:
        if item['course'] not in courses:
            continue
        refs = item.get('question_media', []) + item.get('context_media', [])
        if refs and all(images.get(r, {}).get('decision') == 'remove' for r in refs) and not any(
                _is_cover(images, r) for r in refs):
            saved.append(item['id'])
    return sorted(saved)


def summarize(images: dict) -> dict:
    out = {'images': len(images)}
    for entry in images.values():
        out[entry['decision']] = out.get(entry['decision'], 0) + 1
        if entry['borderline']:
            out['borderline'] = out.get('borderline', 0) + 1
    return out


def resolve(sidecar: dict, item: dict) -> dict:
    """Cleaned media lists for one item: {'question_media': [...], 'context_media': [...]} with entries
    {'original', 'cleaned' (file name or None), 'decision'}; removed images drop out unless that would empty
    the item's whole question image set."""
    result = {}
    images = sidecar['images']
    # exam cover pages are never question content: dropped even when nothing else is left (the caller holds the item)
    flat = [r for key in ('question_media', 'context_media') for r in item.get(key, []) if not _is_cover(images, r)]
    all_removed = bool(flat) and all(images.get(r, {}).get('decision') == 'remove' for r in flat)
    for key in ('question_media', 'context_media'):
        rows = []
        for ref in item.get(key, []):
            entry = images.get(ref)
            if entry is None:
                rows.append({'original': ref, 'cleaned': None, 'decision': 'keep'})
            elif _is_cover(images, ref):
                continue
            elif entry['decision'] == 'remove' and not all_removed:
                continue
            elif entry['decision'] == 'remove':
                rows.append({'original': ref, 'cleaned': None, 'decision': 'keep_last_image'})
            else:
                rows.append({'original': ref, 'cleaned': (entry['cleaned'] or {}).get('file'), 'decision': entry['decision']})
        result[key] = rows
    result['cover_dropped'] = [r for key in ('question_media', 'context_media') for r in item.get(key, [])
                               if _is_cover(images, r)]
    return result


def contact_sheet(vault: Path, sidecar: dict, out: Path, *, decision=None, borderline=None, count=12, seed=1,
                  name='contact.png', width=320) -> Path | None:
    """Original (left) next to cleaned (right) for N random matching entries."""
    pool = [e for e in sidecar['images'].values()
            if (decision is None or e['decision'] == decision) and (borderline is None or e['borderline'] == borderline)]
    random.Random(seed).shuffle(pool)
    pool = pool[:count]
    if not pool:
        return None
    cells = []
    for entry in pool:
        original = Image.open(Path(vault) / entry['original']).convert('L')
        cleaned = Image.open(out / 'cleaned' / entry['cleaned']['file']).convert('L') if entry['cleaned'] else None
        scale = width / original.width
        pair = [original.resize((width, max(1, int(original.height * scale))))]
        if cleaned is not None:
            pair.append(cleaned.resize((width, max(1, int(cleaned.height * scale)))))
        cells.append((entry, pair))
    height = max(max(im.height for im in pair) for _, pair in cells)
    cols = 2
    rows = (len(cells) + cols - 1) // cols
    sheet = Image.new('L', (cols * (2 * width + 30), rows * (min(height, 700) + 24)), 255)
    draw = ImageDraw.Draw(sheet)
    for index, (entry, pair) in enumerate(cells):
        cx, cy = (index % cols) * (2 * width + 30), (index // cols) * (min(height, 700) + 24)
        draw.text((cx + 2, cy + 2), f"{entry['decision']}:{entry['reason']} {entry['original'].rsplit('/', 1)[-1][:24]}", fill=0)
        for k, im in enumerate(pair):
            sheet.paste(im.crop((0, 0, width, min(im.height, 700))), (cx + k * (width + 10), cy + 16))
    path = out / 'contact' / name
    path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(path)
    return path


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--vault', type=Path, default=DEFAULT_VAULT)
    ap.add_argument('--out', type=Path, default=WORK)
    ap.add_argument('--courses', help='comma-separated course codes (default: every non-CAIE course)')
    ap.add_argument('--limit', type=int)
    ap.add_argument('--release')
    ap.add_argument('--no-contact', action='store_true')
    ap.add_argument('--no-ocr', action='store_true', help='skip cover-page detection')
    args = ap.parse_args(argv)
    sidecar = run(args.vault, args.out, courses=args.courses.split(',') if args.courses else None,
                  limit=args.limit, release=args.release, ocr=not args.no_ocr)
    (args.out).mkdir(parents=True, exist_ok=True)
    target = args.out / 'image_cleaning.json'
    tmp = target.with_suffix('.tmp')
    tmp.write_text(json.dumps(sidecar, indent=1, sort_keys=True) + '\n')
    os.replace(tmp, target)
    print(json.dumps(sidecar['summary']), 'kept_for_item_integrity', len(sidecar['kept_for_item_integrity']))
    if not args.no_contact:
        for label, kw in (('cropped', dict(decision='crop')), ('collapsed', dict(decision='collapse')),
                          ('removed', dict(decision='remove')), ('borderline', dict(borderline=True))):
            path = contact_sheet(args.vault, sidecar, args.out, name=f'{label}.png', **kw)
            print(label, path)
    print('wrote', target)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
