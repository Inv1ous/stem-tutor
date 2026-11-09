"""Retire superseded topical releases that still cite confirmed question leaks, preserving them in Archive.

A topical release (Library/Shared/Topicals/Releases/<version>/) and the legacy topical bank
(Library/Shared/Questions/Topicals/<batch>/bank.json) are immutable Library resources. After a
leak-free release is CURRENT (leak_free_topical_release.py), the older ones are the only Library
files keeping the leak images referenced. Retiring moves their bytes, unchanged, to an Archive
folder outside the vault and removes their catalog records, so the leaks become unreferenced and
prune_question_leaks.py can delete them.

plan      read-only. Lists every Library JSON file citing a given leak id; refuses unless each is a
          non-CURRENT topical release or a legacy topical bank, no learner file (.tutor) names it,
          and the catalog minus those records still resolves every Library reference.
apply     journalled and lock-protected: catalog digest bound to the plan, catalog backed up, records
          removed in one atomic catalog switch, then each file renamed into the archive (digest
          checked on both sides). Re-running a partial apply resumes it.
rollback  moves every archived file back and re-inserts its exact catalog record. Works on top of
          later catalog changes (record-wise, not a whole-catalog restore); refused for any record id
          that has been reused since.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'build'))
sys.path.insert(0, str(ROOT / 'src'))
import consolidate_question_media as journalled  # noqa: E402
import merge_question_duplicates as merge  # noqa: E402
import prune_question_leaks as prune  # noqa: E402
from tutorlib.asset_library import (AssetLibrary, asset_path_key, catalog_writer_lock,  # noqa: E402
                                    validate_catalog, _read_at, _atomic_at)

TOOL = 'retire_topical_releases'
RELEASES = 'Library/Shared/Topicals/Releases/'
LEGACY = 'Library/Shared/Questions/Topicals/'
WORK = prune.WORK


def sha(data: bytes) -> str:
    return journalled._sha(data)


def _unit(path: str) -> str | None:
    """The retirement unit (folder) a citing file belongs to, or None when it may not be retired."""
    parts = PurePosixPath(path).parts
    if path.startswith(RELEASES) and len(parts) == 6:
        return '/'.join(parts[:5])
    if path.startswith(LEGACY) and len(parts) == 6 and parts[-1] == 'bank.json':
        return '/'.join(parts[:5])
    return None


def build_plan(vault: Path, leaks: list[str]) -> dict:
    vault = Path(os.path.abspath(vault))
    library = AssetLibrary(vault)
    records = library.records()
    unknown = [leak for leak in leaks if leak not in records]
    cited = prune.citations(library, records)
    current = (vault / '.tutor/topicals/CURRENT').read_text().strip()
    errors, units = [], set()
    for leak in leaks:
        for path in sorted(cited.get(leak, ())):
            unit = _unit(path)
            if unit is None:
                errors.append(f'{leak} cited by a file that is not a retirable topical bank: {path}')
            elif unit == RELEASES + current:
                errors.append(f'{leak} still cited by the CURRENT release {current}')
            else:
                units.add(unit)
    learner_text = []
    tutor = vault / '.tutor'
    for path in sorted(tutor.rglob('*')) if tutor.is_dir() else []:
        if path.is_file() and path.suffix in ('.json', '.jsonl'):
            try:
                learner_text.append(path.read_text('utf-8', 'replace'))
            except OSError:
                continue
    learner = '\n'.join(learner_text)
    retire = []
    for identifier, record in sorted(records.items(), key=lambda kv: kv[1]['path']):
        unit = next((u for u in units if record['path'].startswith(u + '/')), None)
        if unit is None:
            continue
        name = PurePosixPath(unit).name
        if record['path'] in learner or f'"{name}"' in learner or f'Releases/{name}/' in learner:
            errors.append(f'learner file names {record["path"]}')
        retire.append({'id': identifier, 'path': record['path'], 'sha256': record['sha256'], 'unit': unit,
                       'size': (vault / record['path']).stat().st_size})
    raw = journalled._read(vault, 'Library/catalog.json')
    plan = {'format_version': 1, 'tool': TOOL, 'vault': str(vault), 'current': current,
            'catalog_sha256': sha(raw), 'leaks': sorted(leaks), 'units': sorted(units), 'retire': retire,
            'errors': errors + [f'unknown leak id {u}' for u in unknown]}
    plan['reference_check'] = simulate(vault, plan)
    return plan


def simulate(vault: Path, plan: dict) -> dict:
    """Drop the retired records in memory and prove every remaining Library reference still resolves."""
    library = AssetLibrary(vault)
    records = library.records()
    gone = {entry['id'] for entry in plan['retire']}
    keys, refs = {}, {}
    for identifier, record in records.items():
        for ref in [record['path'], *record.get('aliases', [])]:
            refs[asset_path_key(ref)] = identifier
            if identifier not in gone:
                keys[asset_path_key(ref)] = identifier
    # Tokens inside the retired files leave with them; every other Library JSON must still resolve.
    broken, checked = [], 0
    for identifier, record in sorted(records.items()):
        path = record['path']
        if (identifier in gone or not path.endswith('.json') or path.endswith('.png.json')
                or not path.startswith('Library/')):
            continue
        try:
            text = library.read('asset:' + identifier).decode('utf-8', 'replace')
        except (OSError, ValueError):
            continue
        for token in set(prune.organize.TOKEN.findall(text)):
            checked += 1
            if token.startswith('asset:'):
                if token[6:] in gone:
                    broken.append(token)
                continue
            try:
                key = asset_path_key(token)
            except ValueError:
                continue
            if key in refs and key not in keys:
                broken.append(token)
    return {'tokens_checked': checked, 'retired_ids': len(gone),
            'broken': broken[:50], 'broken_count': len(broken)}


def _move(source: Path, target: Path, digest: str) -> None:
    if target.exists():
        if sha(target.read_bytes()) != digest:
            raise ValueError(f'archive already holds different bytes: {target}')
        if source.exists():
            if sha(source.read_bytes()) != digest:
                raise ValueError(f'bytes changed: {source}')
            source.unlink()
        return
    if sha(source.read_bytes()) != digest:
        raise ValueError(f'bytes changed: {source}')
    target.parent.mkdir(parents=True, exist_ok=True)
    os.rename(source, target)
    if sha(target.read_bytes()) != digest:
        raise ValueError(f'archived bytes differ: {target}')


def _prune_empty(vault: Path, units) -> None:
    for unit in units:
        folder = vault / unit
        try:
            for leftover in folder.iterdir():
                if leftover.name == '.DS_Store':
                    leftover.unlink()
            folder.rmdir()
        except OSError:
            pass  # Anything else left in the folder stays.


def apply(plan: dict, journal: Path, archive: Path, backup: Path) -> dict:
    if plan.get('tool') != TOOL or plan.get('errors') or plan['reference_check']['broken_count']:
        raise ValueError('not a clean, reference-verified retire plan')
    vault, journal, archive = Path(plan['vault']), Path(os.path.abspath(journal)), Path(os.path.abspath(archive))
    if any(Path(os.path.abspath(p)).is_relative_to(vault) for p in (journal, archive, backup)):
        raise ValueError('journal, archive and backup must be outside the learner vault')
    with catalog_writer_lock(vault) as directory:
        raw = _read_at(directory, 'catalog.json')
        saved = json.loads(journal.read_text()) if journal.exists() else None
        if saved and saved['retire'] != plan['retire']:
            raise ValueError('journal does not match requested retire plan')
        if not saved:
            if sha(raw) != plan['catalog_sha256']:
                raise ValueError('catalog changed since retire plan')
            if (vault / '.tutor/topicals/CURRENT').read_text().strip() != plan['current']:
                raise ValueError('CURRENT topical release changed since plan')
            catalog = json.loads(raw)
            for entry in plan['retire']:
                record = catalog['assets'].get(entry['id'])
                if record is None or record['path'] != entry['path'] or record['sha256'] != entry['sha256']:
                    raise ValueError(f'record changed since plan: {entry["id"]}')
            copy = prune._backup(raw, backup)
            saved = {'format_version': 1, 'tool': TOOL, 'vault': str(vault), 'archive': str(archive),
                     'status': 'prepared', 'catalog_before_sha256': sha(raw), 'catalog_backup': str(copy),
                     'current': plan['current'], 'units': plan['units'], 'retire': plan['retire'],
                     'records': {e['id']: catalog['assets'][e['id']] for e in plan['retire']}}
            journalled._json(journal, saved)
            for entry in plan['retire']:
                catalog['assets'].pop(entry['id'])
            validate_catalog(catalog)
            updated = (json.dumps(catalog, ensure_ascii=False, indent=2) + '\n').encode()
            saved['catalog_after_sha256'] = sha(updated)
            saved['status'] = 'switching'; journalled._json(journal, saved)
            _atomic_at(directory, 'catalog.json', updated, replace=True)
            saved['status'] = 'committed'; journalled._json(journal, saved)
        elif saved['status'] == 'complete':
            return {'status': 'complete', 'retired': len(saved['retire']), 'journal': str(journal)}
        elif saved['status'] in ('prepared', 'switching') and sha(raw) != saved.get('catalog_after_sha256'):
            raise ValueError('interrupted before the catalog switch: rerun plan')
        moved = 0
        for entry in saved['retire']:
            _move(vault / entry['path'], archive / entry['path'], entry['sha256'])
            moved += entry['size']
        _prune_empty(vault, saved['units'])
        saved['bytes_archived'] = moved
        saved['status'] = 'complete'; journalled._json(journal, saved)
    return {'status': 'complete', 'retired': len(saved['retire']), 'units': len(saved['units']),
            'bytes_archived': moved, 'journal': str(journal), 'archive': str(archive)}


def rollback(journal: Path) -> dict:
    journal = Path(journal)
    saved = json.loads(journal.read_text())
    if saved.get('tool') != TOOL:
        raise ValueError('not a retire_topical_releases journal')
    vault, archive = Path(saved['vault']), Path(saved['archive'])
    with catalog_writer_lock(vault) as directory:
        catalog = json.loads(_read_at(directory, 'catalog.json'))
        for entry in saved['retire']:
            present = catalog['assets'].get(entry['id'])
            if present is not None and present != saved['records'][entry['id']]:
                raise ValueError(f'record id reused since retirement: {entry["id"]}')
        saved['status'] = 'rolling_back'; journalled._json(journal, saved)
        for entry in saved['retire']:
            _move(archive / entry['path'], vault / entry['path'], entry['sha256'])
            catalog['assets'][entry['id']] = saved['records'][entry['id']]
        validate_catalog(catalog)
        _atomic_at(directory, 'catalog.json', (json.dumps(catalog, ensure_ascii=False, indent=2) + '\n').encode(),
                   replace=True)
        saved['status'] = 'rolled_back'; journalled._json(journal, saved)
    return {'status': 'rolled_back', 'restored': len(saved['retire'])}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('plan')
    p.add_argument('--vault', type=Path, default=ROOT.parent / 'STEM Tutor')
    p.add_argument('--leaks', help='comma-separated asset ids (default: LEAK_REFERENCED rows of the AI review)')
    p.add_argument('--review', type=Path, default=WORK / 'ai-review.json')
    p.add_argument('--out', type=Path, default=WORK / 'retire-plan.json')
    p = sub.add_parser('apply')
    p.add_argument('--plan', type=Path, required=True)
    p.add_argument('--journal', type=Path, required=True)
    p.add_argument('--archive', type=Path, required=True)
    p.add_argument('--backup', type=Path, default=WORK / 'catalog.before-retire.json')
    p.add_argument('--yes', action='store_true')
    p = sub.add_parser('rollback')
    p.add_argument('--journal', type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == 'plan':
        leaks = args.leaks.split(',') if args.leaks else [r['id'] for r in json.loads(args.review.read_text())['items']
                                                          if r['class'] == 'LEAK_REFERENCED']
        plan = build_plan(args.vault, leaks)
        journalled._json(args.out, plan)
        print(json.dumps({'units': len(plan['units']), 'files': len(plan['retire']), 'errors': plan['errors'][:10],
                          'reference_check': plan['reference_check']['broken_count'], 'out': str(args.out)}, indent=1))
    elif args.command == 'apply':
        if not args.yes:
            raise SystemExit('apply moves Library releases to the archive: pass --yes after reading the plan')
        print(json.dumps(apply(json.loads(args.plan.read_text()), args.journal, args.archive, args.backup)))
    else:
        print(json.dumps(rollback(args.journal)))


if __name__ == '__main__':
    raise SystemExit(main())
