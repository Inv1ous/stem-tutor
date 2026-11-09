"""Journalled question-media consolidation with stable catalog IDs and exact rollback.

Planning and auditing are read-only. Apply copies and verifies originals before
switching the catalog under its shared writer lock. Historical JSON is untouched;
old paths remain declared aliases. Run with --help for explicit apply/rollback.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from tutorlib.asset_library import (AssetLibrary, asset_path_key, catalog_writer_lock,
                                    validate_catalog, _directory, _read_at, _atomic_at)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read(root: Path, relative: str) -> bytes:
    parts = Path(relative).parts
    if not parts or Path(relative).is_absolute() or '..' in parts:
        raise ValueError('unsafe media path')
    with _directory(root, list(parts[:-1])) as directory:
        return _read_at(directory, parts[-1])


def _put(root: Path, relative: str, data: bytes) -> None:
    parts = Path(relative).parts
    if not parts or Path(relative).is_absolute() or '..' in parts:
        raise ValueError('unsafe media path')
    root = Path(os.path.abspath(root))
    with _directory(Path(root.anchor), [*root.parts[1:], *parts[:-1]], create=True) as directory:
        _atomic_at(directory, parts[-1], data, replace=False)


def _json(path: Path, data: dict) -> None:
    path = Path(os.path.abspath(path))
    with _directory(Path(path.anchor), list(path.parent.parts[1:]), create=True) as directory:
        _atomic_at(directory, path.name,
                   (json.dumps(data, ensure_ascii=False, indent=1) + '\n').encode(), replace=True)


def plan(vault: Path) -> dict:
    vault = Path(os.path.abspath(vault))
    reader = AssetLibrary(vault)
    records = reader.records()
    occupied = {asset_path_key(ref): identifier for identifier, record in records.items()
                for ref in [record['path'], *record.get('aliases', [])]}
    moves, errors = [], []
    for identifier, entry in sorted(records.items()):
        parts = Path(entry['path']).parts
        if len(parts) <= 6 or parts[:2] != ('Library', 'Courses') or parts[3:5] != ('Questions', 'Media'):
            continue
        destination = Path(*parts[:5]) / parts[-1]
        if asset_path_key(str(destination)) in occupied:
            name = Path(parts[-1])
            destination = destination.with_name(name.stem + '--' + identifier + name.suffix)
        key = asset_path_key(str(destination))
        if key in occupied:
            errors.append(f'conflicting destination: {destination}')
            continue
        occupied[key] = identifier
        try:
            reader.resolve('asset:' + identifier)
        except (OSError, ValueError) as exc:
            errors.append(str(exc))
        moves.append({'id': identifier, 'from': entry['path'], 'to': str(destination), 'sha256': entry['sha256']})
    return {'format_version': 1, 'vault': str(vault),
            'catalog_sha256': _sha(_read(vault, 'Library/catalog.json')), 'moves': moves, 'errors': errors}


def _cleanup(vault: Path, moves: list[dict]) -> None:
    directories = set()
    for move in moves:
        old = vault / move['from']
        if old.exists() or old.is_symlink():
            if _sha(_read(vault, move['from'])) != move['sha256']:
                raise ValueError('old media changed during cleanup')
            with _directory(vault, list(Path(move['from']).parts[:-1])) as directory:
                os.unlink(old.name, dir_fd=directory)
        directory = old.parent
        while directory != vault and directory.name != 'Media':
            directories.add(directory)
            directory = directory.parent
    for directory in sorted(directories, key=lambda p: len(p.parts), reverse=True):
        try:
            directory.rmdir()
        except (FileNotFoundError, OSError):
            pass  # Uncatalogued files are never discarded to make a folder empty.


def apply(report: dict, journal: Path) -> dict:
    if report.get('errors'):
        raise ValueError('media plan contains errors')
    vault, journal = Path(report['vault']), Path(os.path.abspath(journal))
    if journal.is_relative_to(vault):
        raise ValueError('media journal and originals must be outside the learner vault')
    with catalog_writer_lock(vault) as directory:
        raw = _read_at(directory, 'catalog.json')
        saved = json.loads(journal.read_text()) if journal.exists() else None
        if saved:
            if saved.get('vault') != str(vault) or saved.get('format_version') != 1:
                raise ValueError('journal belongs to another media migration')
            if saved['status'] == 'complete':
                if _sha(raw) != saved['catalog_after_sha256']:
                    raise ValueError('catalog changed after completed media migration')
                for move in saved['moves']:
                    if _sha(_read(vault, move['to'])) != move['sha256']:
                        raise ValueError('migrated media digest mismatch')
                return {'status': 'complete', 'moved': len(saved['moves']), 'journal': str(journal)}
            if saved['status'] == 'committed' or (saved['status'] == 'switching'
                    and _sha(raw) == saved['catalog_after_sha256']):
                if _sha(raw) != saved['catalog_after_sha256']:
                    raise ValueError('catalog changed before cleanup')
                _cleanup(vault, saved['moves'])
                saved['status'] = 'complete'; _json(journal, saved)
                return {'status': 'complete', 'moved': len(saved['moves']), 'journal': str(journal)}
            if saved['moves'] != report['moves']:
                raise ValueError('journal does not match requested media plan')
        if _sha(raw) != report['catalog_sha256']:
            raise ValueError('catalog changed since media plan')
        catalog = json.loads(raw)
        archive = journal.parent / journal.stem / 'originals'
        for move in report['moves']:
            entry = catalog['assets'][move['id']]
            if entry['path'] != move['from'] or entry['sha256'] != move['sha256']:
                raise ValueError('media identity changed since plan')
            if _sha(_read(vault, move['from'])) != move['sha256']:
                raise ValueError('media digest changed since plan')
            target = vault / move['to']
            if target.exists() or target.is_symlink():
                if not saved or _sha(_read(vault, move['to'])) != move['sha256']:
                    raise ValueError('media destination exists or is unsafe')
        if saved is None:
            saved = {'format_version': 1, 'vault': str(vault), 'status': 'prepared',
                     'catalog_before': raw.decode(), 'moves': report['moves'], 'originals': str(archive)}
            _json(journal, saved)
        for move in report['moves']:
            data = _read(vault, move['from'])
            _put(archive, move['id'], data)
            _put(vault, move['to'], data)
            if _sha(_read(archive, move['id'])) != move['sha256'] or _sha(_read(vault, move['to'])) != move['sha256']:
                raise ValueError('media copy digest mismatch')
            entry = catalog['assets'][move['id']]
            entry['path'] = move['to']
            entry['aliases'] = list(dict.fromkeys([*entry.get('aliases', []), move['from']]))
            entry.update(move.get('catalog') or {})  # e.g. a source-practice crop now filed under its course
        validate_catalog(catalog)
        updated = (json.dumps(catalog, ensure_ascii=False, indent=2) + '\n').encode()
        saved['catalog_after_sha256'] = _sha(updated)
        # A crash after catalog replacement is recognized from the recorded hash.
        saved['status'] = 'switching'; _json(journal, saved)
        _atomic_at(directory, 'catalog.json', updated, replace=True)
        saved['status'] = 'committed'; _json(journal, saved)
        _cleanup(vault, report['moves'])
        saved['status'] = 'complete'; _json(journal, saved)
    return {'status': 'complete', 'moved': len(report['moves']), 'journal': str(journal)}


def rollback(journal: Path) -> dict:
    journal = Path(journal)
    saved = json.loads(journal.read_text())
    vault, archive = Path(saved['vault']), Path(saved['originals'])
    with catalog_writer_lock(vault) as directory:
        raw = _read_at(directory, 'catalog.json')
        before_hash = _sha(saved['catalog_before'].encode())
        resuming = saved['status'] in ('rolling_back', 'rolled_back')
        allowed = {saved.get('catalog_after_sha256'), before_hash} if resuming else {saved.get('catalog_after_sha256')}
        if _sha(raw) not in allowed:
            raise ValueError('catalog changed; automatic rollback would discard other work')
        for move in saved['moves']:
            target = vault / move['to']
            if resuming and not target.exists() and not target.is_symlink():
                continue
            if _sha(_read(vault, move['to'])) != move['sha256']:
                raise ValueError('new media changed; refusing to remove it')
        saved['status'] = 'rolling_back'; _json(journal, saved)
        for move in saved['moves']:
            data = _read(archive, move['id'])
            if _sha(data) != move['sha256']:
                raise ValueError('archived media digest mismatch')
            _put(vault, move['from'], data)
        _atomic_at(directory, 'catalog.json', saved['catalog_before'].encode(), replace=True)
        for move in saved['moves']:
            target = vault / move['to']
            if not target.exists() and not target.is_symlink():
                continue
            if _sha(_read(vault, move['to'])) != move['sha256']:
                raise ValueError('new media changed; refusing to remove it')
            with _directory(vault, list(Path(move['to']).parts[:-1])) as parent:
                os.unlink(Path(move['to']).name, dir_fd=parent)
        saved['status'] = 'rolled_back'; _json(journal, saved)
    return {'status': 'rolled_back', 'restored': len(saved['moves'])}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vault', type=Path, default=ROOT.parent / 'STEM Tutor')
    parser.add_argument('--report', type=Path)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--journal', type=Path)
    parser.add_argument('--rollback', type=Path)
    args = parser.parse_args()
    if args.rollback:
        print(json.dumps(rollback(args.rollback))); return
    report = plan(args.vault)
    if args.report:
        _json(args.report, report)
    if args.apply:
        if not args.journal:
            parser.error('--apply requires --journal outside the vault')
        print(json.dumps(apply(report, args.journal)))
    else:
        print(json.dumps({'moves': len(report['moves']), 'errors': report['errors']}))


if __name__ == '__main__':
    main()
