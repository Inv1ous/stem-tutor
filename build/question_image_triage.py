"""Find question images that are not questions (page headers, footers, page numbers, blank strips, answer lines only),
without reading them one by one.

  scan      programmatic and free: measure every MCQ/Long question image, flag the suspicious ones (small, blank, a single
            line of text), and group near-identical ones, so one verdict covers the whole group
  review    one cheap vision-model call per GROUP (RouteLLM, a low-tier model), results remembered in the verdict file
            so nothing is ever reviewed twice; each verdict is printed as it arrives
  apply     flag every image of a "junk" group in the Library catalog (`junk: true`). The files and their hashes stay, so
            history and references remain valid; the tutor never shows a flagged image. --undo flips the flags back.

    .venv/bin/python build/question_image_triage.py scan [--vault V]
    .venv/bin/python build/question_image_triage.py review [--model claude-haiku-5-5] [--limit N]
    .venv/bin/python build/question_image_triage.py apply [--undo]

Keys (the answer cells) are never judged: a one-line "8 | D" is a legitimate key. Extraction calls `check_new` on each
crop it stores, so a known-junk look is flagged at once and a new suspicious one is queued for the next review.
"""
from __future__ import annotations

import argparse
import base64
import collections
import hashlib
import io
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path, PurePosixPath

import numpy as np
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
WORK = ROOT.parent / 'Work' / 'Preparation' / 'question-library-organize'
DEFAULT_VAULT = Path(os.environ.get('STEM_TUTOR_VAULT') or ROOT.parent / 'STEM Tutor')
VERDICTS = WORK / 'image-triage.json'
FOLDERS = ('/MCQ/', '/Long/')
MIN_HEIGHT = 150          # a question with its options is taller than this; headers and footers are not
MIN_WIDTH = 200
BLANK_INK = 0.0004        # share of dark pixels below which an image is empty
SIMILAR = 8               # bits (of 128) two group signatures may differ by
KEY_URL = Path.home() / '.config/routellm/key'
BASE = os.environ.get('ABACUS_ROUTELLM_BASE_URL', 'https://routellm.abacus.ai/v1')

PROMPT = ('This image was cropped from an exam paper and filed as a QUESTION. Is it part of a question a student must '
          'read to answer (question text, a diagram, a table, answer options, a mark-scheme point), or page furniture '
          'with nothing to answer (a running header or footer, a page number, a chapter title, a blank area, only '
          'ruled answer lines, a cover page)? Reply with JSON only: {"verdict": "keep" | "junk", "why": "<8 words>"}. '
          'When unsure, say keep.')


# ---------------------------------------------------------------- measurement (no model)
def features(data: bytes) -> dict:
    """Size, ink and a 128-bit look-alike signature of one image."""
    with Image.open(io.BytesIO(data)) as image:
        grey = image.convert('L')
    arr = np.asarray(grey)
    dark = arr < 160
    rows = dark.any(axis=1)
    bands, in_band = 0, False
    for row in rows:                       # separate lines of ink
        if row and not in_band:
            bands += 1
        in_band = bool(row)
    small = np.asarray(grey.filter(ImageFilter.GaussianBlur(1.5)).resize((32, 4), Image.Resampling.BILINEAR), dtype=float)
    bits = (small < small.mean()).flatten()
    signature = ''.join('1' if b else '0' for b in bits)
    return {'width': int(arr.shape[1]), 'height': int(arr.shape[0]), 'ink': round(float(dark.mean()), 5),
            'bands': bands, 'signature': hex(int(signature, 2))[2:].zfill(32)}


def suspicious(f: dict) -> str | None:
    """Why an image looks like page furniture, or None. Deliberately generous: the group review decides."""
    if f['ink'] < BLANK_INK:
        return 'blank'
    if f['height'] < MIN_HEIGHT:
        return 'short'
    if f['width'] < MIN_WIDTH:
        return 'narrow'
    if f['bands'] <= 1 and f['height'] < 260:
        return 'single line'
    return None


def distance(a: str, b: str) -> int:
    return bin(int(a, 16) ^ int(b, 16)).count('1')


def groups_of(rows: list[dict]) -> list[list[dict]]:
    """Near-identical suspects together (same look, same size class): one verdict for each group."""
    groups: list[list[dict]] = []
    for row in sorted(rows, key=lambda r: (r['height'], r['path'])):
        for group in groups:
            lead = group[0]
            if abs(lead['height'] - row['height']) <= 12 and distance(lead['signature'], row['signature']) <= SIMILAR:
                group.append(row)
                break
        else:
            groups.append([row])
    return groups


def question_images(vault: Path):
    from tutorlib.asset_library import AssetLibrary
    library = AssetLibrary(vault)
    for identifier, record in sorted(library.records().items()):
        path = record['path']
        if (path.lower().endswith('.png') and '/Questions/Media/' in path and any(f in path for f in FOLDERS)
                and not record.get('junk')):
            yield identifier, record


# ---------------------------------------------------------------- verdict memory
def load_verdicts() -> dict:
    try:
        return json.loads(VERDICTS.read_text())
    except (OSError, ValueError):
        return {'format_version': 1, 'groups': {}}


def save_verdicts(data: dict) -> None:
    WORK.mkdir(parents=True, exist_ok=True)
    tmp = VERDICTS.with_suffix('.tmp')
    tmp.write_text(json.dumps(data, indent=1, ensure_ascii=False))
    tmp.replace(VERDICTS)


def remembered(verdicts: dict, f: dict) -> dict | None:
    """A verdict already given to a group this image looks like."""
    for entry in verdicts['groups'].values():
        if (abs(entry['height'] - f['height']) <= 12 and distance(entry['signature'], f['signature']) <= SIMILAR
                and entry.get('verdict') in ('keep', 'junk')):
            return entry
    return None


def scan(vault: Path) -> dict:
    from tutorlib.asset_library import AssetLibrary
    library = AssetLibrary(vault)
    verdicts, rows, total = load_verdicts(), [], 0
    for identifier, record in question_images(vault):
        total += 1
        f = features(library.read('asset:' + identifier))
        why = suspicious(f)
        if why:
            rows.append({'id': identifier, 'path': record['path'], 'sha256': record['sha256'], 'why': why, **f})
    result = {'vault': str(vault), 'scanned': total, 'suspects': len(rows), 'groups': {}}
    for group in groups_of(rows):
        lead = group[0]
        key = hashlib.sha256((lead['signature'] + str(lead['height'])).encode()).hexdigest()[:12]
        known = remembered(verdicts, lead)
        result['groups'][key] = {'signature': lead['signature'], 'height': lead['height'], 'width': lead['width'],
                                 'sample': lead['path'], 'members': [{'id': r['id'], 'path': r['path']} for r in group],
                                 'why': sorted({r['why'] for r in group}),
                                 'verdict': known['verdict'] if known else None, 'why_text': known.get('why') if known else None}
    WORK.mkdir(parents=True, exist_ok=True)
    (WORK / 'image-triage-scan.json').write_text(json.dumps(result, indent=1))
    return result


# ---------------------------------------------------------------- review (one call per group)
def api_key() -> str:
    key = os.environ.get('ABACUS_ROUTELLM_API_KEY', '').strip()
    if not key and KEY_URL.exists():
        key = KEY_URL.read_text().splitlines()[0].strip()
    if not key:
        sys.exit('no RouteLLM key: set ABACUS_ROUTELLM_API_KEY or put it in ~/.config/routellm/key')
    return key


def ask_model(model: str, image_bytes: bytes) -> dict:
    body = {'model': model, 'max_tokens': 400, 'temperature': 0,
            'messages': [{'role': 'user', 'content': [
                {'type': 'text', 'text': PROMPT},
                {'type': 'image_url', 'image_url': {'url': 'data:image/png;base64,' + base64.b64encode(image_bytes).decode()}}]}]}
    request = urllib.request.Request(BASE + '/chat/completions', data=json.dumps(body).encode(), method='POST',
                                     headers={'Authorization': f'Bearer {api_key()}', 'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            text = json.loads(response.read())['choices'][0]['message']['content']
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f'HTTP {exc.code}: {exc.read().decode()[:200]}') from None
    match = re.search(r'\{.*\}', text, re.S)
    reply = json.loads(match.group(0)) if match else {}
    if reply.get('verdict') not in ('keep', 'junk'):
        raise RuntimeError(f'unusable reply: {text[:120]!r}')
    return {'verdict': reply['verdict'], 'why': str(reply.get('why', ''))[:80]}


def review(vault: Path, model: str, limit: int | None) -> dict:
    from tutorlib.asset_library import AssetLibrary
    library = AssetLibrary(vault)
    result = json.loads((WORK / 'image-triage-scan.json').read_text()) if (WORK / 'image-triage-scan.json').exists() else scan(vault)
    verdicts = load_verdicts()
    todo = [(k, g) for k, g in result['groups'].items() if g['verdict'] is None]
    todo.sort(key=lambda kv: -len(kv[1]['members']))        # the biggest groups settle the most images first
    print(f"{result['suspects']} suspect images in {len(result['groups'])} groups; "
          f"{len(todo)} groups still need a verdict ({sum(len(g['members']) for _, g in todo)} images). Model: {model}", flush=True)
    asked = junk = 0
    for n, (key, group) in enumerate(todo[:limit], 1):
        sample = group['members'][0]['id']
        try:
            reply = ask_model(model, library.read('asset:' + sample))
        except (RuntimeError, urllib.error.URLError, OSError, ValueError) as exc:
            print(f"  [{n}/{len(todo)}] {key}: {exc}", flush=True)
            continue
        asked += 1
        junk += reply['verdict'] == 'junk'
        verdicts['groups'][key] = {'signature': group['signature'], 'height': group['height'], **reply,
                                   'model': model, 'at': time.strftime('%Y-%m-%d %H:%M'), 'sample': group['sample'],
                                   'members': len(group['members'])}
        save_verdicts(verdicts)
        group['verdict'], group['why_text'] = reply['verdict'], reply['why']
        print(f"  [{n}/{len(todo)}] {reply['verdict'].upper():5} x{len(group['members']):<4} {group['width']}x{group['height']}"
              f"  {PurePosixPath(group['sample']).name}  — {reply['why']}", flush=True)
    (WORK / 'image-triage-scan.json').write_text(json.dumps(result, indent=1))
    print(f'reviewed {asked} groups with {asked} model calls ({junk} junk). Next: apply', flush=True)
    return result


# ---------------------------------------------------------------- apply / undo
def apply(vault: Path, undo: bool) -> dict:
    from tutorlib.asset_library import catalog_writer_lock, _read_at, _atomic_at, validate_catalog
    result = json.loads((WORK / 'image-triage-scan.json').read_text())
    verdicts = load_verdicts()
    junk_ids = {m['id'] for g in result['groups'].values() for m in g['members']
                if (g['verdict'] or (verdicts['groups'].get(next((k for k, v in verdicts['groups'].items()
                                                                  if v['signature'] == g['signature']), ''), {})).get('verdict')) == 'junk'}
    with catalog_writer_lock(vault) as directory:
        raw = _read_at(directory, 'catalog.json') or b'{"assets": {}}'
        catalog = json.loads(raw)
        changed = 0
        for identifier in junk_ids:
            entry = catalog['assets'].get(identifier)
            if entry is None:
                continue
            if undo and entry.pop('junk', None):
                changed += 1
            elif not undo and not entry.get('junk'):
                entry['junk'] = True
                changed += 1
        validate_catalog(catalog)
        if changed:
            (WORK / 'image-triage-catalog-before.json').write_bytes(raw)    # exact copy for a manual rollback
            _atomic_at(directory, 'catalog.json', (json.dumps(catalog, ensure_ascii=False, indent=2) + '\n').encode(), replace=True)
    return {'junk_images': len(junk_ids), 'changed': changed, 'undo': undo}


# ---------------------------------------------------------------- for the extraction workflow
def check_new(data: bytes) -> str | None:
    """Called for each crop an extraction is about to store: "junk" when it looks like a group already judged junk,
    "suspect" when it looks like page furniture nobody has judged yet (queued for the next `review`), else None."""
    f = features(data)
    why = suspicious(f)
    if not why:
        return None
    known = remembered(load_verdicts(), f)
    return known['verdict'] if known and known['verdict'] == 'junk' else ('suspect' if not known else None)


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ('scan', 'review', 'apply'):
        p = sub.add_parser(name)
        p.add_argument('--vault', type=Path, default=DEFAULT_VAULT)
        if name == 'review':
            p.add_argument('--model', default='claude-haiku-5-5')
            p.add_argument('--limit', type=int)
        if name == 'apply':
            p.add_argument('--undo', action='store_true')
    args = parser.parse_args(argv)
    vault = args.vault.resolve()
    if args.command == 'scan':
        r = scan(vault)
        sizes = collections.Counter(bool(g['verdict']) for g in r['groups'].values())
        print(json.dumps({'scanned': r['scanned'], 'suspects': r['suspects'], 'groups': len(r['groups']),
                          'already_judged_groups': sizes[True], 'to_review_groups': sizes[False]}))
    elif args.command == 'review':
        review(vault, args.model, args.limit)
    else:
        print(json.dumps(apply(vault, args.undo)))


if __name__ == '__main__':
    main()
