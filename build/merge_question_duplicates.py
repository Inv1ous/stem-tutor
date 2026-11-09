"""Merge exact-duplicate question images into one canonical asset with declared aliases.

plan is read-only against the vault. apply and rollback reuse the journalled, lock-protected
machinery of consolidate_question_media: copies verified before the catalog switch, old paths
stay declared aliases, the canonical asset keeps its id and digest, surplus bytes are preserved
under Archive, and the journal restores the exact prior catalog.

Groups come from find_question_duplicates.py (same sha256). A group is skipped when it is
cross-course, holds a validator-pinned image, or holds an image referenced by learner
events/answers/grades. Run with --help.
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import re
import sys
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'build'))
sys.path.insert(0, str(ROOT / 'src'))
import consolidate_question_media as journalled
import organize_question_library as organize
import question_media_names as names
from tutorlib.asset_library import (AssetLibrary, asset_path_key, catalog_writer_lock,
                                    validate_catalog, _directory, _read_at, _atomic_at)

TOOL = 'merge_question_duplicates'
WORK = ROOT.parent / 'Work' / 'Preparation' / 'question-library-organize'
DEFAULT_GROUPS = WORK / 'duplicates.json'
DEFAULT_PLAN = WORK / 'merge-plan.json'
IMAGE_TOKEN = re.compile(r'[A-Za-z0-9_][A-Za-z0-9._/-]*\.(?:png|jpg|jpeg|svg|webp)\b')
ASSET_TOKEN = re.compile(r'asset:[A-Za-z0-9._:/-]+')


def sha(data: bytes) -> str:
    return journalled._sha(data)


def is_pinned(record: dict) -> bool:
    return record.get('kind') == 'Questions/Media' and bool(organize.PINNED.fullmatch(PurePosixPath(record['path']).name))


def learner_references(vault: Path) -> set[str]:
    """Every image path or asset id the learner vault cites outside Library (events, answers, grades, packs)."""
    root = Path(vault) / '.tutor'
    found = set()
    if not root.is_dir():
        return found
    for path in sorted(root.rglob('*')):
        if path.suffix not in ('.json', '.jsonl') or not path.is_file():
            continue
        try:
            text = path.read_text('utf-8', 'replace')
        except OSError:
            continue
        for token in IMAGE_TOKEN.findall(text):
            try:
                found.add(asset_path_key(token))
            except ValueError:
                continue
        found.update(ASSET_TOKEN.findall(text))
    return found


def rank(copy: dict, record: dict) -> tuple:
    """Course Questions/Media before SourcePractice, canonical name before legacy, then shortest path, lowest id."""
    path = copy['path']
    name = PurePosixPath(path).name
    parts = names.canonical_parts(name)
    named = bool(parts and parts['sha12'] == record['sha256'][:12])
    foldered = bool(named and PurePosixPath(path).parent.name == names.FOLDER[parts['role']])
    return (0 if '/Questions/Media/' in path else 1, 0 if foldered else 1 if named else 2, len(path), copy['id'])


def find_groups(vault: Path) -> list[dict]:
    """Exact-duplicate groups (same sha256) from the catalog, as find_question_duplicates.py reports them."""
    import find_question_duplicates as finder
    return finder.exact_groups(finder.candidate_images(AssetLibrary(vault).records()))


def build_plan(vault: Path, groups: list, *, records: dict | None = None, library: AssetLibrary | None = None) -> dict:
    vault = Path(os.path.abspath(vault))
    library = library or AssetLibrary(vault)
    records = records if records is not None else library.records()
    occupied = {}
    for identifier, record in records.items():
        for ref in [record['path'], *record.get('aliases', [])]:
            occupied.setdefault(asset_path_key(ref), identifier)
    cited = learner_references(vault)
    merges, moves, skipped, errors = [], [], [], []
    for group in groups:
        copies = [c for c in group['copies'] if c['id'] in records]
        if len(copies) < 2:
            skipped.append({'sha256': group['sha256'], 'kind': group['kind'], 'count': group['count'],
                            'reason': 'fewer than two catalogued copies', 'paths': [c['path'] for c in group['copies']]})
            continue
        if group['kind'] == 'cross-course':
            skipped.append({'sha256': group['sha256'], 'kind': group['kind'], 'count': group['count'],
                            'reason': 'cross-course group', 'paths': [c['path'] for c in copies]})
            continue
        pinned = [c['path'] for c in copies if is_pinned(records[c['id']])]
        if pinned:
            skipped.append({'sha256': group['sha256'], 'kind': group['kind'], 'count': group['count'],
                            'reason': 'validator-pinned image', 'paths': pinned})
            continue
        referenced = [c['path'] for c in copies
                      if asset_path_key(c['path']) in cited or 'asset:' + c['id'] in cited]
        if referenced:
            skipped.append({'sha256': group['sha256'], 'kind': group['kind'], 'count': group['count'],
                            'reason': 'learner event/answer/grade reference', 'paths': referenced})
            continue
        canonical = min(copies, key=lambda c: rank(c, records[c['id']]))
        surplus = [c for c in copies if c['id'] != canonical['id']]
        surplus_ids = {c['id'] for c in surplus}
        clash = []
        for copy in surplus:
            for ref in [copy['path'], *records[copy['id']].get('aliases', [])]:
                owner = occupied.get(asset_path_key(ref))
                if owner not in (None, canonical['id']) and owner not in surplus_ids:
                    clash.append(ref)
        if clash:
            skipped.append({'sha256': group['sha256'], 'kind': group['kind'], 'count': group['count'],
                            'reason': 'alias already owned by another asset: ' + clash[0],
                            'paths': [c['path'] for c in copies]})
            continue
        merges.append({'canonical': canonical['id'], 'path': canonical['path'], 'sha256': group['sha256'],
                       'kind': group['kind'], 'aliases': [c['id'] for c in surplus]})
        for copy in surplus:
            moves.append({'id': copy['id'], 'from': copy['path'], 'sha256': group['sha256'],
                          'into': canonical['id']})
    raw = journalled._read(vault, 'Library/catalog.json')
    return {'format_version': 1, 'tool': TOOL, 'vault': str(vault), 'catalog_sha256': sha(raw),
            'merges': merges, 'moves': moves, 'skipped': skipped, 'errors': errors}


def scan_tokens(library: AssetLibrary, records: dict) -> dict[str, str | None]:
    """Every image reference written in a Library JSON file, mapped to the asset it names today."""
    refs = {}
    for identifier, record in records.items():
        for ref in [record['path'], *record.get('aliases', [])]:
            refs[asset_path_key(ref)] = identifier
    tokens = {}
    for identifier, record in sorted(records.items()):
        path = record['path']
        if not path.endswith('.json') or path.endswith('.png.json') or not path.startswith('Library/'):
            continue
        try:
            text = library.read('asset:' + identifier).decode('utf-8', 'replace')
        except (OSError, ValueError):
            continue
        for token in set(organize.TOKEN.findall(text)):
            if token.startswith('asset:'):
                tokens[token] = token[6:] if token[6:] in records else None
            else:
                try:
                    tokens[token] = refs.get(asset_path_key(token))
                except ValueError:
                    tokens[token] = None
    return tokens


def simulate(vault: Path, plan: dict, tokens: dict[str, str | None], records: dict) -> dict:
    """Apply the merges to an in-memory catalog and prove every reference still names identical bytes."""
    catalog = json.loads(journalled._read(vault, 'Library/catalog.json'))
    for move in plan['moves']:
        surplus = catalog['assets'].pop(move['id'], None)
        if surplus is None:
            continue
        canonical = catalog['assets'][move['into']]
        for ref in [surplus['path'], *surplus.get('aliases', [])]:
            canonical['aliases'] = list(dict.fromkeys([*canonical.get('aliases', []), ref]))
    validate_catalog(catalog)
    after = {}
    for identifier, record in catalog['assets'].items():
        after['asset:' + identifier] = identifier
        for ref in [record['path'], *record.get('aliases', [])]:
            after[asset_path_key(ref)] = identifier
    broken = []
    for token, identifier in tokens.items():
        if identifier is None:
            continue
        key = token if token.startswith('asset:') else asset_path_key(token)
        target = after.get(key)
        if target is None or catalog['assets'][target]['sha256'] != records[identifier]['sha256']:
            broken.append(token)
    retired = 0
    for move in plan['moves']:
        if after.get(asset_path_key(move['from'])) != move['into']:
            broken.append(move['from'])
        if 'asset:' + move['id'] in tokens:  # a retired id must not be cited anywhere
            broken.append('asset:' + move['id'])
        retired += 1
    return {'tokens_checked': len(tokens), 'retired_ids': retired, 'broken': broken[:50],
            'broken_count': len(broken)}


def verify_files(vault: Path, plan: dict, records: dict) -> list[str]:
    """Every canonical copy must still read back at its planned digest."""
    problems = []
    for merge in plan['merges']:
        try:
            data = journalled._read(vault, merge['path'])
        except (OSError, ValueError) as exc:
            problems.append(f"{merge['canonical']}: {exc}")
            continue
        if sha(data) != merge['sha256']:
            problems.append(f"{merge['canonical']}: digest mismatch at {merge['path']}")
    return problems


def summarize(plan: dict, vault: Path) -> dict:
    sizes = collections.Counter()
    saved = 0
    for move in plan['moves']:
        try:
            saved += (Path(vault) / move['from']).stat().st_size
        except OSError:
            pass
    for skip in plan['skipped']:
        sizes[skip['reason'].split(':')[0]] += 1
    kinds = collections.Counter(m['kind'] for m in plan['merges'])
    return {'groups_merged': len(plan['merges']), 'copies_aliased': len(plan['moves']),
            'bytes_saved': saved, 'merged_by_kind': dict(kinds),
            'groups_skipped': len(plan['skipped']), 'skipped_by_reason': dict(sizes),
            'errors': len(plan['errors'])}


def _cleanup(vault: Path, moves: list[dict]) -> None:
    directories = set()
    for move in moves:
        old = vault / move['from']
        if old.exists() or old.is_symlink():
            if sha(journalled._read(vault, move['from'])) != move['sha256']:
                raise ValueError('surplus media changed during cleanup')
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


def apply(plan: dict, journal: Path) -> dict:
    if plan.get('errors'):
        raise ValueError('merge plan contains errors')
    if plan.get('reference_check', {}).get('broken_count', 1) != 0:
        raise ValueError('plan was not reference-verified')
    vault, journal = Path(plan['vault']), Path(os.path.abspath(journal))
    if journal.is_relative_to(vault):
        raise ValueError('merge journal and originals must be outside the learner vault')
    with catalog_writer_lock(vault) as directory:
        raw = _read_at(directory, 'catalog.json')
        saved = json.loads(journal.read_text()) if journal.exists() else None
        if saved:
            if saved.get('vault') != str(vault) or saved.get('format_version') != 1:
                raise ValueError('journal belongs to another merge')
            if saved['status'] == 'complete':
                if sha(raw) != saved['catalog_after_sha256']:
                    raise ValueError('catalog changed after completed merge')
                for move in saved['moves']:
                    if sha(journalled._read(saved['originals'], move['id'])) != move['sha256']:
                        raise ValueError('archived duplicate digest mismatch')
                return {'status': 'complete', 'merged': len(saved['merges']), 'aliased': len(saved['moves']),
                        'journal': str(journal)}
            if saved['status'] == 'committed' or (saved['status'] == 'switching'
                                                  and sha(raw) == saved['catalog_after_sha256']):
                if sha(raw) != saved['catalog_after_sha256']:
                    raise ValueError('catalog changed before cleanup')
                _cleanup(vault, saved['moves'])
                saved['status'] = 'complete'; journalled._json(journal, saved)
                return {'status': 'complete', 'merged': len(saved['merges']), 'aliased': len(saved['moves']),
                        'journal': str(journal)}
            if saved['moves'] != plan['moves'] or saved['merges'] != plan['merges']:
                raise ValueError('journal does not match requested merge plan')
        if sha(raw) != plan['catalog_sha256']:
            raise ValueError('catalog changed since merge plan')
        catalog = json.loads(raw)
        archive = journal.parent / journal.stem / 'originals'
        for move in plan['moves']:
            entry = catalog['assets'].get(move['id'])
            if entry is None or entry['path'] != move['from'] or entry['sha256'] != move['sha256']:
                raise ValueError('duplicate identity changed since plan')
            if sha(journalled._read(vault, move['from'])) != move['sha256']:
                raise ValueError('duplicate digest changed since plan')
        for merge in plan['merges']:
            entry = catalog['assets'].get(merge['canonical'])
            if entry is None or entry['path'] != merge['path'] or entry['sha256'] != merge['sha256']:
                raise ValueError('canonical identity changed since plan')
        if saved is None:
            saved = {'format_version': 1, 'tool': TOOL, 'vault': str(vault), 'status': 'prepared',
                     'catalog_before': raw.decode(), 'merges': plan['merges'], 'moves': plan['moves'],
                     'originals': str(archive)}
            journalled._json(journal, saved)
        for move in plan['moves']:
            data = journalled._read(vault, move['from'])
            journalled._put(archive, move['id'], data)
            if sha(journalled._read(archive, move['id'])) != move['sha256']:
                raise ValueError('archived duplicate digest mismatch')
        for move in plan['moves']:
            surplus = catalog['assets'].pop(move['id'])
            canonical = catalog['assets'][move['into']]
            for ref in [surplus['path'], *surplus.get('aliases', [])]:
                canonical['aliases'] = list(dict.fromkeys([*canonical.get('aliases', []), ref]))
        validate_catalog(catalog)
        updated = (json.dumps(catalog, ensure_ascii=False, indent=2) + '\n').encode()
        saved['catalog_after_sha256'] = sha(updated)
        saved['status'] = 'switching'; journalled._json(journal, saved)
        _atomic_at(directory, 'catalog.json', updated, replace=True)
        saved['status'] = 'committed'; journalled._json(journal, saved)
        _cleanup(vault, plan['moves'])
        saved['status'] = 'complete'; journalled._json(journal, saved)
    return {'status': 'complete', 'merged': len(plan['merges']), 'aliased': len(plan['moves']),
            'journal': str(journal)}


def rollback(journal: Path) -> dict:
    journal = Path(journal)
    saved = json.loads(journal.read_text())
    vault, archive = Path(saved['vault']), Path(saved['originals'])
    with catalog_writer_lock(vault) as directory:
        raw = _read_at(directory, 'catalog.json')
        before_hash = sha(saved['catalog_before'].encode())
        resuming = saved['status'] in ('rolling_back', 'rolled_back')
        allowed = {saved.get('catalog_after_sha256'), before_hash} if resuming else {saved.get('catalog_after_sha256')}
        if sha(raw) not in allowed:
            raise ValueError('catalog changed; automatic rollback would discard other work')
        saved['status'] = 'rolling_back'; journalled._json(journal, saved)
        for move in saved['moves']:
            data = journalled._read(archive, move['id'])
            if sha(data) != move['sha256']:
                raise ValueError('archived duplicate digest mismatch')
            journalled._put(vault, move['from'], data)
        _atomic_at(directory, 'catalog.json', saved['catalog_before'].encode(), replace=True)
        saved['status'] = 'rolled_back'; journalled._json(journal, saved)
    return {'status': 'rolled_back', 'restored': len(saved['moves'])}


def cmd_plan(args):
    groups = json.loads(args.groups.read_text())['exact']
    plan = build_plan(args.vault, groups)
    library = AssetLibrary(args.vault)
    records = library.records()
    plan['reference_check'] = simulate(Path(plan['vault']), plan, scan_tokens(library, records), records)
    plan['file_check'] = verify_files(Path(plan['vault']), plan, records)
    journalled._json(args.out, plan)
    print(json.dumps(summarize(plan, plan['vault']) | {'reference_check': plan['reference_check']['broken_count'],
                                                      'file_check': len(plan['file_check']),
                                                      'out': str(args.out)}, indent=1))


def cmd_apply(args):
    if not args.yes:
        raise SystemExit('apply changes the vault catalog: pass --yes after reading the plan and verifying a backup')
    plan = json.loads(args.plan.read_text())
    if plan.get('tool') != TOOL:
        raise SystemExit('not a merge_question_duplicates plan')
    print(json.dumps(apply(plan, args.journal)))
    return 0


def cmd_rollback(args):
    print(json.dumps(rollback(args.journal)))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('plan')
    p.add_argument('--vault', type=Path, default=ROOT.parent / 'STEM Tutor')
    p.add_argument('--groups', type=Path, default=DEFAULT_GROUPS)
    p.add_argument('--out', type=Path, default=DEFAULT_PLAN)
    p.set_defaults(func=cmd_plan)
    p = sub.add_parser('apply')
    p.add_argument('--plan', type=Path, required=True)
    p.add_argument('--journal', type=Path, required=True)
    p.add_argument('--yes', action='store_true')
    p.set_defaults(func=cmd_apply)
    p = sub.add_parser('rollback')
    p.add_argument('--journal', type=Path, required=True)
    p.set_defaults(func=cmd_rollback)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == '__main__':
    raise SystemExit(main())
