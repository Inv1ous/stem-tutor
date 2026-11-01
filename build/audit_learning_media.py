"""Read-only check of catalog bytes, CURRENT question media and visible lesson images."""
from __future__ import annotations

import argparse
from collections import Counter
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from tutorlib.asset_library import AssetLibrary
from tutorlib.library_refs import MARKDOWN_TARGET
from tutorlib.packs import Packs
from tutorlib.store import Vault

IMAGES = {'.svg', '.png', '.jpg', '.jpeg', '.webp', '.gif', '.avif'}


def _images(value, field=''):
    if isinstance(value, dict):
        for key, child in value.items():
            yield from _images(child, key)
    elif isinstance(value, list):
        for child in value:
            yield from _images(child, field)
    elif isinstance(value, str):
        if field in {'image', 'images', 'diagram', 'diagrams', 'file'} and (
                value.startswith('asset:') or Path(value).suffix.lower() in IMAGES):
            yield value
        if '![' in value:
            yield from _markdown_images(value)


def _markdown_images(text):
    for match in MARKDOWN_TARGET.finditer(text):
        if match.group('code'):
            continue
        target = match.group('wiki_target') or match.group('link_target')
        target = target.strip('<>').split('|', 1)[0].split('#', 1)[0]
        if '://' not in target and Path(target).suffix.lower() in IMAGES:
            yield target


def audit(vault: Path) -> dict:
    vault = Path(vault).resolve()
    library = AssetLibrary(vault)
    records = library.records()
    errors, media = [], set()
    for identifier, record in records.items():
        try:
            library.read('asset:' + identifier)
        except (OSError, ValueError) as exc:
            errors.append({'scope': 'catalog', 'source': record['path'], 'error': str(exc)})
    packs = Packs(Vault(vault))
    counts = Counter()
    for sub in sorted(packs.published()):
        try:
            pack = packs.pack(sub)
            if pack is None:
                raise ValueError('published pack could not load')
            counts['packs'] += 1; counts['pack_items'] += len(pack.get('items', []))
            references = list(_images(pack))
            counts['pack_image_mentions'] += len(references)
            media.update(references)
        except (OSError, ValueError, TypeError, KeyError) as exc:
            errors.append({'scope': 'pack', 'source': sub, 'error': str(exc)})
    counts['topical_items'] = len(packs.topicals.items)
    errors.extend({'scope': 'topicals', 'error': message} for message in packs.topical_errors)
    for item in packs.topicals.items:
        references = list(_images(item)); counts['topical_image_mentions'] += len(references); media.update(references)
    for reference in sorted(media):
        try:
            library.resolve(reference)
        except (OSError, ValueError) as exc:
            errors.append({'scope': 'runtime_image', 'source': reference, 'error': str(exc)})
    for directory, dirs, files in os.walk(vault, followlinks=False):
        base = Path(directory)
        dirs[:] = [name for name in dirs if not name.startswith('.') and name != 'Library'
                   and not (base / name).is_symlink()]
        for name in files:
            path = base / name
            if path.suffix.lower() != '.md' or path.is_symlink():
                continue
            counts['visible_markdown_files'] += 1
            for reference in _markdown_images(path.read_text(encoding='utf-8')):
                counts['visible_image_mentions'] += 1
                try:
                    library.resolve(reference)
                    if not (vault / reference).is_file():
                        raise ValueError('visible Markdown requires a physical canonical image path')
                except (OSError, ValueError) as exc:
                    errors.append({'scope': 'visible_markdown', 'source': str(path.relative_to(vault)),
                                   'reference': reference, 'error': str(exc)})
    return {'vault': str(vault), 'course_version': packs.root.name, 'topical_version': packs.topicals.pointer,
            'catalog_assets': len(records), 'unique_runtime_images': len(media), **counts, 'errors': errors}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vault', type=Path, default=ROOT.parent / 'STEM Tutor')
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    result = audit(args.vault)
    if args.report:
        args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(result, ensure_ascii=False))
    raise SystemExit(bool(result['errors']))
