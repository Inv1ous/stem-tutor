"""Copy the current reviewed content and dependency closure into a scratch vault.

Do not republish authoring drafts or alter registered plans. The engine's existing
temporary-vault guard prevents Almanac writes outside /tmp. No hardlinks or
symlinks to the learner Library are created.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from tutorlib.asset_library import AssetLibrary, validate_catalog, _directory, _read_at
from tutorlib.library_refs import ASSET_FIELDS, ASSET_PREFIXES, ASSET_SUFFIXES, MARKDOWN_TARGET, PROTECTED_FIELDS, normalize_asset_reference, is_asset_reference


def _references(value, field='', *, with_source=False):
    if isinstance(value, dict):
        for key, child in value.items():
            if key not in PROTECTED_FIELDS:
                yield from _references(child, key, with_source=with_source)
    elif isinstance(value, list):
        for child in value:
            yield from _references(child, field, with_source=with_source)
    elif isinstance(value, str) and field in ASSET_FIELDS | {'note', 'review', 'proposal', 'image_reference'}:
        if '\n' not in value and (value.startswith(ASSET_PREFIXES)
                                 or Path(value).suffix.lower() in ASSET_SUFFIXES):
            yield (value, field == 'source') if with_source else value


def copy_current(source: Path, target: Path) -> dict:
    source, target = Path(source).resolve(), Path(target).resolve()
    if target == source or target.is_relative_to(source) or source.is_relative_to(target):
        raise ValueError('scratch and learner vaults must be separate')
    if target.exists() and any(target.iterdir()):
        raise ValueError('scratch destination must be empty')
    library = AssetLibrary(source)
    records = library.records()
    by_path = {entry['path']: identifier for identifier, entry in records.items()}
    selected = {}
    legacy_release = {}
    pending = []
    pointers = {}
    for kind, section in (('packs', 'Library/Releases'), ('topicals', 'Library/Shared/Topicals/Releases')):
        pointer = source / '.tutor' / kind / 'CURRENT'
        if not pointer.exists():
            if kind == 'packs':
                raise ValueError('learner vault has no current course release')
            continue
        version = pointer.read_text().strip()
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', version) or version in ('.', '..'):
            raise ValueError('unsafe current release pointer')
        prefix = section + '/' + version + '/'
        identifiers = [identifier for identifier, entry in records.items() if entry['path'].startswith(prefix)]
        if not identifiers and kind == 'packs':
            # Older published releases are immutable Library directories but
            # predate per-file catalog registration. Snapshot their exact bytes
            # into the scratch catalog; never invent an upstream review claim.
            base = source / section / version
            for path in sorted(base.rglob('*')):
                if path.is_symlink():
                    raise ValueError('release snapshot refuses symlinks')
                if not path.is_file():
                    continue
                relative = path.relative_to(source).as_posix()
                with _directory(source, list(Path(relative).parts[:-1])) as directory:
                    data = _read_at(directory, path.name)
                legacy_release[relative] = data
            if not legacy_release:
                raise ValueError('current release is absent from the Library')
            pending.extend((reference, False) for reference in legacy_release)
        elif not identifiers:
            raise ValueError('current release is absent from the Library catalog')
        pending.extend(('asset:' + identifier, False) for identifier in identifiers)
        pointers[kind] = version
    pending.extend(('asset:' + identifier, False) for identifier, entry in records.items()
                   if entry['path'].startswith('Library/Shared/Fonts/')
                   or entry.get('kind') == 'question_duplicate_review'
                   or (entry.get('kind') == 'source_repair'
                       and entry.get('repair_status') != 'superseded'))
    while pending:
        reference, source_text = pending.pop()
        reference = normalize_asset_reference(reference)
        if reference in legacy_release:
            data = legacy_release[reference]
            identifier = 'scratch-release-' + hashlib.sha256(reference.encode()).hexdigest()[:24]
            entry = {'path': reference, 'sha256': hashlib.sha256(data).hexdigest(), 'aliases': [],
                     'provenance': {'snapshot_only': True, 'source_release': pointers['packs']}}
        else:
            try:
                entry = library.record(reference)
            except ValueError as original:
                # Historical topical provenance files are Library-root-relative.
                try:
                    entry = library.record('sources/library/' + reference)
                except ValueError:
                    # Match runtime source/citation handling only after both
                    # declared alias forms were tried. Keep provenance bytes;
                    # actual unknown local asset paths must still fail.
                    if source_text and not is_asset_reference(reference):
                        continue
                    raise original
                reference = 'sources/library/' + reference
            identifier = by_path[entry['path']]
        if identifier in selected:
            continue
        if reference not in legacy_release:
            data = library.read(reference)
        selected[identifier] = entry
        destination = target / entry['path']
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
        if destination.suffix == '.json':
            pending.extend(_references(json.loads(data), with_source=True))
        elif destination.suffix == '.md':
            for match in MARKDOWN_TARGET.finditer(data.decode('utf-8')):
                if match.group('code'):
                    continue
                value = match.group('wiki_target') or match.group('link_target')
                value = value.strip('<>').split('|', 1)[0].split('#', 1)[0]
                if value.startswith(ASSET_PREFIXES) and Path(value).suffix.lower() in ASSET_SUFFIXES:
                    pending.append((value, False))
        provenance = entry.get('provenance')
        if isinstance(provenance, dict):
            pending.extend((reference, False) for reference in provenance.get('sidecars', []))
    for relative, original in legacy_release.items():
        with _directory(source, list(Path(relative).parts[:-1])) as directory:
            if _read_at(directory, Path(relative).name) != original:
                raise ValueError('published release changed during scratch snapshot')
    catalog = {'format_version': 1, 'assets': selected}
    validate_catalog(catalog)
    (target / 'Library/catalog.json').write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + '\n')
    for kind, version in pointers.items():
        pointer = target / '.tutor' / kind / 'CURRENT'
        pointer.parent.mkdir(parents=True, exist_ok=True)
        pointer.write_text(version)
    (target / '.tutor/config.json').write_text('{"tz":"Asia/Hong_Kong","scratch":true}\n')
    for folder in ('Lessons', 'Sessions', 'My Notes', 'Subjects', 'Inbox', 'Almanac', 'Anki'):
        (target / folder).mkdir(exist_ok=True)
    return {'version': pointers['packs'], 'topicals': pointers.get('topicals'), 'assets': len(selected)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=ROOT.parent / 'STEM Tutor')
    parser.add_argument('--target', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(copy_current(args.source, args.target)))
