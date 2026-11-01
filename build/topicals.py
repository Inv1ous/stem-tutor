"""Import verified local topical questions and publish an independent bank atomically.

Question content stays outside Git. Only reviewed mappings with an official key enter the bank.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
import library as source_library  # noqa: E402 - sibling build tool, same source configuration
from tutorlib.asset_library import AssetLibrary, write_asset  # noqa: E402
from tutorlib.saved_figures import require_runtime_library  # noqa: E402

# Explicit compatibility override for isolated source fixtures. Normal operation
# discovers the actual course Sources shelves through build.library.
LIBRARY = None
ALLOWED = ('Chemistry 9701 AS Topicals', 'Physics 9702 AS Topicals')
EXAMMATE = re.compile(r'(970[12])/(\d{2})_(Summer|Winter|Spring)_(\d{4})_Q(\d+)')
PAPA = re.compile(r'(970[12])_([msw]\d{2})_qp_(\d{2})\s+Q:\s*(\d+)')
KEY = re.compile(r'(970[12])_([msw]\d{2})_qp_(\d{2})\s+(\d{1,2})\s+([ABCD])\b')
_UNSET = object()


def references(text: str) -> list[str]:
    result = []
    for m in EXAMMATE.finditer(text):
        code, variant, season, year, number = m.groups()
        series = {'Summer': 's', 'Winter': 'w', 'Spring': 'm'}[season] + year[2:]
        result.append(f'{code}_{series}_{variant}_q{int(number)}')
    for m in PAPA.finditer(text):
        code, series, variant, number = m.groups()
        result.append(f'{code}_{series}_{variant}_q{int(number)}')
    return list(dict.fromkeys(result))


def table_keys(text: str) -> dict[str, str]:
    result = {}
    for code, series, variant, number, answer in KEY.findall(text):
        qid = f'{code}_{series}_{variant}_q{int(number)}'
        if qid in result and result[qid] != answer:
            raise ValueError(f'official key conflict: {qid}')
        result[qid] = answer
    return result


def question_regions(anchors: list[tuple], index: int, heights: list[float]) -> list[tuple]:
    page, y, _ = anchors[index]
    next_page, next_y, _ = anchors[index + 1] if index + 1 < len(anchors) else (page, heights[page] - 26, '')
    result = []
    for n in range(page, next_page + 1):
        top = y if n == page else 50
        bottom = next_y - 4 if n == next_page else heights[n] - 30
        if bottom > top + 8:
            result.append((n, top, bottom))
    return result


def source_options(options) -> dict[str, str]:
    """A source image owns any option the PDF could not transcribe completely."""
    if (isinstance(options, dict) and set(options) == set('ABCD')
            and all(isinstance(value, str) and value.strip() for value in options.values())):
        return options
    return {letter: '(in the source picture)' for letter in 'ABCD'}


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))


def _asset_relative(name: str) -> Path:
    path = Path(name)
    if (path.is_absolute() or '..' in path.parts or len(path.parts) < 6
            or path.parts[:2] != ('Library', 'Courses') or path.parts[3:5] != ('Questions', 'Media')):
        raise ValueError(f'unsafe topical asset: {name}')
    return path


def _activate_current(base: Path, version: str, expected: str | None) -> None:
    """Serialize the final compare-and-swap so a concurrent bank is never lost."""
    import fcntl
    base.mkdir(parents=True, exist_ok=True)
    current = base / 'CURRENT'
    with (base / '.publish.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        actual = current.read_text().strip() if current.exists() else None
        if actual != expected:
            raise ValueError('topical bank changed during preparation; rebuild against the current bank')
        temporary = base / ('.CURRENT.' + version)
        try:
            temporary.write_text(version + '\n', encoding='utf-8')
            os.replace(temporary, current)
        finally:
            temporary.unlink(missing_ok=True)


def publish(batch: Path, vault: Path, *, expected_current=_UNSET,
            allow_unbound_legacy: bool = False) -> dict:
    """Validate, store an immutable Library release, then switch the state pointer."""
    scripts = ROOT / 'src'
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    from tutorlib.packs import Packs
    from tutorlib.store import Vault
    from tutorlib.topicals import _runtime_items, validate_bank
    batch, vault = Path(batch).resolve(), Path(vault).resolve()
    pointer = vault / '.tutor/topicals/CURRENT'
    previous = pointer.read_text().strip() if pointer.exists() else None
    report_path = batch / 'report.json'
    report = _read(report_path) if report_path.exists() else {}
    if expected_current is _UNSET:
        preparation = report.get('preparation') if isinstance(report, dict) else None
        if isinstance(preparation, dict) and 'expected_current' in preparation:
            expected_current = preparation['expected_current']
        elif isinstance(report, dict) and 'previous_version' in report:
            expected_current = report['previous_version']
        elif allow_unbound_legacy:
            expected_current = previous
        else:
            raise ValueError('batch has no preparation CURRENT binding; pass the explicit legacy override to publish it')
    if previous != expected_current:
        raise ValueError('topical bank changed during preparation; rebuild against the current bank')
    data = _read(batch / 'bank.json')
    if (not isinstance(data, dict) or data.get('format_version') != 1
            or not isinstance(data.get('items'), list) or any(not isinstance(item, dict) for item in data['items'])):
        raise ValueError('invalid topical bank or item structure')
    import content_checks
    damaged = [(item.get('id'), content_checks.debris_problems(item))
               for item in data.get('items', []) if isinstance(item, dict)]
    damaged = [(ident, issues) for ident, issues in damaged if issues]
    if damaged:
        raise ValueError(f'damaged source text requires independent repair: {damaged[:3]}')
    data['items'] = _runtime_items(data['items'], vault)
    try:
        packs = Packs(Vault(vault))
    except (OSError, ValueError, KeyError) as exc:
        raise ValueError(f'publish requires an existing valid tutor vault: {exc}') from exc
    validate_bank(data, packs=packs, asset_root=vault)
    if data.get('format_version') != 1 or not isinstance(data.get('items'), list):
        raise ValueError('invalid topical bank')
    assets = {}
    catalog = AssetLibrary(vault)
    for item in data['items']:
        names = list(dict.fromkeys([item.get('image')] + list(item.get('images') or [])))
        for name in filter(None, names):
            rel = _asset_relative(name)
            # Extraction has already registered immutable Library media. A bank
            # publication changes metadata and its pointer, never copies media.
            assets[rel] = catalog.resolve(name)
    base = vault / '.tutor/topicals'
    if not base.resolve().is_relative_to(vault):
        raise ValueError('unsafe topical destination')
    version = 'v' + uuid.uuid4().hex
    release = f'Library/Shared/Topicals/Releases/{version}'
    require_runtime_library(vault)
    # The bank and optional report are immutable Library resources. CURRENT is
    # state and switches only after every release resource is durable/catalogued.
    write_asset(vault, release + '/bank.json', json.dumps(data, ensure_ascii=False, indent=1).encode('utf-8'),
                metadata={'kind': 'Topicals/Releases', 'version': version})
    if report_path.exists():
        write_asset(vault, release + '/report.json', report_path.read_bytes(),
                    metadata={'kind': 'Topicals/Releases', 'version': version})
    _activate_current(base, version, previous)
    return {'version': version, 'items': len(data['items']), 'assets': len(assets), 'release': release}


def _collections() -> list[Path]:
    roots = [Path(LIBRARY)] if LIBRARY is not None else list(source_library.roots('library').values())
    return [root / name for root in roots for name in ALLOWED if (root / name).is_dir()]


def _source(path: Path) -> tuple[str, bytes]:
    path = Path(os.path.abspath(path))
    if not any(path.is_relative_to(Path(os.path.abspath(folder))) for folder in _collections()):
        raise ValueError(f'outside permitted collections: {path}')
    if LIBRARY is not None:
        root = Path(os.path.abspath(LIBRARY))
        relative = path.relative_to(root)
        if any((root / Path(*relative.parts[:index])).is_symlink() for index in range(1, len(relative.parts) + 1)):
            raise ValueError('unsafe source symlink')
        return relative.as_posix(), path.read_bytes()
    vault = source_library.learner_vault().resolve()
    relative = path.relative_to(vault).as_posix()
    return relative, AssetLibrary(vault).read(relative)


def _source_path(reference: str) -> Path:
    if LIBRARY is not None:
        return Path(LIBRARY) / reference
    return AssetLibrary(source_library.learner_vault()).resolve(reference)


def _collection(name: str) -> Path:
    choices = [path for path in _collections() if path.name == name]
    if len(choices) != 1:
        raise ValueError(f'expected one source collection for {name}; found {len(choices)}')
    return choices[0]


def default_output() -> Path:
    return ROOT.parent / 'Work/Topicals' / ('batch-' + uuid.uuid4().hex)


def store_question_media(vault: Path, code: str, qid: str, data: bytes) -> str:
    if (not re.fullmatch(r'[A-Za-z0-9]+', code) or not re.fullmatch(r'[A-Za-z0-9_-]+', qid)
            or not qid.startswith(code + '_')):
        raise ValueError('invalid course or question identifier')
    digest = hashlib.sha256(data).hexdigest()[:16]
    relative = f'Library/Courses/{code}/Questions/Media/{qid}-{digest}.png'
    require_runtime_library(vault)
    write_asset(vault, relative, data, metadata={'course': code, 'kind': 'Questions/Media'})
    return relative


def source_index(paths: list[Path]) -> tuple[dict, dict]:
    """Reference bounds from question headers only; answer appendices never enter the index."""
    import pymupdf
    pymupdf.TOOLS.mupdf_display_errors(False)
    pymupdf.TOOLS.mupdf_display_warnings(False)
    index, files = {}, {}
    for path in paths:
        rel, data = _source(path)
        doc = pymupdf.open(stream=data, filetype='pdf')
        files[rel] = {'sha256': hashlib.sha256(data).hexdigest(), 'pages': len(doc),
                      'rotation_review_pages': [n + 1 for n, page in enumerate(doc) if page.rotation]}
        anchors = []
        for n, page in enumerate(doc):
            if page.rotation:
                continue  # Pixel/OCR coordinates need a separate physical orientation and boundary review.
            for block in page.get_text('blocks'):
                refs = references(block[4])
                if len(refs) == 1:
                    anchors.append((n, max(0, block[1] - 3), refs[0]))
        anchors.sort(key=lambda a: (a[0], a[1]))
        for i, (page, y, qid) in enumerate(anchors):
            next_anchor = anchors[i + 1] if i + 1 < len(anchors) else None
            end = next_anchor[1] - 4 if next_anchor and next_anchor[0] == page else doc[page].rect.height - 42
            # MCQ extraction is deliberately single-page. In these sources each question is a separate image.
            images = [im for im in doc[page].get_image_info()
                      if im['bbox'][1] >= y and im['bbox'][1] < end and im['bbox'][3] <= end + 5]
            if qid.split('_')[2].startswith('1') and images and end > y + 35:
                index.setdefault(qid, []).append({'file': rel, 'page': page + 1,
                    'box': [20, y, doc[page].rect.width - 20, end], 'images': len(images)})
        doc.close()
    return index, files


def build_matched(output: Path | None = None) -> dict:
    """First conservative batch: exact reviewed KC mappings, source crops and independent official keys."""
    import pymupdf
    prepared_pointer = source_library.learner_vault() / '.tutor/topicals/CURRENT'
    expected_current = prepared_pointer.read_text().strip() if prepared_pointer.exists() else None
    output = Path(output) if output is not None else default_output()
    if output.exists():
        raise ValueError('output already exists; use a fresh batch directory')
    chemistry = _collection(ALLOWED[0]) / '9701 Examinent Paper 1 2017-2024 TA.pdf'
    physics = _collection(ALLOWED[1]) / '(2015 till 2020) PapaCambridge/P1'
    question_paths = [chemistry] + sorted(physics.glob('*.pdf'))
    keys_paths = [chemistry, physics / 'Answers/Physics 9702 Paper 1 - Answers (All Topics).pdf']
    official = {}
    for path in keys_paths:
        _, source_bytes = _source(path)
        with pymupdf.open(stream=source_bytes, filetype='pdf') as doc:
            for qid, answer in table_keys('\n'.join(page.get_text(sort=True) for page in doc)).items():
                if qid in official and official[qid] != answer:
                    raise ValueError(f'official key conflict: {qid}')
                official[qid] = answer
    index, files = source_index(question_paths)
    output.mkdir(parents=True)
    items, pending, counts = [], [], {}
    docs = {}
    try:
        for code in ('9701', '9702'):
            graph = _read(ROOT / f'build/out/specs/{code}/graph.json')
            valid = {k['id']: k for k in graph['kcs'] if k.get('level') == 'AS'}
            published = {p.stem for p in (ROOT / 'build/out/packs' / code).glob('*.json')}
            bank = _read(ROOT / f'build/work/mcq/{code}.tagged.json')
            stats = counts[code] = {'source_mcq_references': sum(q.startswith(code) for q in index),
                                   'ready': 0, 'pending': 0}
            for entry in bank:
                qid = entry['id']
                if qid not in index:
                    continue
                kcs = entry.get('kcs') or []
                reason = ('missing official key' if qid not in official else
                          'official key differs from existing bank' if official[qid] != entry.get('answer') else
                          'off syllabus or invalid mapping' if entry.get('off_syllabus') or not kcs or any(k not in valid for k in kcs) else
                          'chapter not yet published' if any(valid[k]['subtopic'] not in published for k in kcs) else '')
                if reason:
                    pending.append({'qid': qid, 'reason': reason}); stats['pending'] += 1
                    continue
                source = index[qid][0]
                if source['file'] not in docs:
                    _, source_bytes = _source(_source_path(source['file']))
                    docs[source['file']] = pymupdf.open(stream=source_bytes, filetype='pdf')
                doc = docs[source['file']]
                page = doc[source['page'] - 1]
                pix = page.get_pixmap(clip=pymupdf.Rect(source['box']), dpi=130, colorspace=pymupdf.csGRAY)
                image = store_question_media(source_library.learner_vault(), code, qid, pix.tobytes('png'))
                requires = list(dict.fromkeys(valid[k]['subtopic'] for k in kcs))
                items.append({'id': 'topical-' + qid, 'kind': 'mcq', 'kcs': kcs, 'difficulty': 3,
                    'command_word': None, 'source': {'type': 'past', 'ref': entry['ref'], 'qid': qid,
                        'library': source, 'sha256': files[source['file']]['sha256'],
                        'verification': 'existing reviewed KC mapping and independent topical answer table'},
                    'stem': entry['stem'], 'options': source_options(entry.get('options')),
                    'answer': official[qid], 'marks': 1, 'image': image, 'tier': 'extra',
                    'explanation': entry.get('er'),
                    'topical': {'reviewed': True, 'requires': requires, 'support': {},
                                'chapters': requires, 'revision': '2025-2027', 'review_batch': '2026-10-27-exact-match-v1'}})
                stats['ready'] += 1
    finally:
        for doc in docs.values(): doc.close()
    data = {'format_version': 1, 'syllabus_versions': {'9701': '2025-2027', '9702': '2025-2027'}, 'items': items}
    report = {'method': 'Exact pre-existing reviewed KC mappings, source-image crops and separately parsed official keys; published chapters only.',
              'preparation': {'expected_current': expected_current},
              'counts': counts, 'pending': pending, 'sources': files, 'indexed_unique_mcqs': len(index),
              'warning': 'Does not enumerate scan-only books or claim all-source coverage.'}
    (output / 'bank.json').write_text(json.dumps(data, ensure_ascii=False, indent=1))
    (output / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=1))
    return {**{k: v for k, v in report.items() if k not in ('pending', 'sources')}, 'output': str(output)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest='command', required=True)
    build = subs.add_parser('build-matched'); build.add_argument('--output', type=Path)
    pub = subs.add_parser('publish'); pub.add_argument('batch', type=Path); pub.add_argument('--vault', type=Path, required=True)
    pub.add_argument('--allow-unbound-legacy-batch', action='store_true',
                     help='allow a pre-binding batch by binding it to CURRENT at publish start')
    args = parser.parse_args()
    result = (build_matched(args.output) if args.command == 'build-matched' else
              publish(args.batch, args.vault, allow_unbound_legacy=args.allow_unbound_legacy_batch))
    print(json.dumps(result, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
