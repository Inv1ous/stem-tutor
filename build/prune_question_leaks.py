"""Prune non-question pages that leaked into course question media (data sheets, periodic tables, constants strips).

plan is read-only against the vault: it classifies every in-scope question image with
question_leak_gate (size/ink first, on-device OCR second, sideways OCR for rotated pages,
near-duplicate hashes of confirmed leaks third) and checks every reference to it:

  LEAK_UNREFERENCED  confident leak, cited by no pack/bank/topical/release/attestation/learner file,
                     not validator-pinned: deleted by apply.
  LEAK_REFERENCED    confident leak that a question item still cites. Library items are immutable and
                     no sanctioned media-removal mechanism exists, so it is kept and listed for review.
  SMALL_REVIEW       excessively small, near-blank, mark-scheme media the gate flagged, or unchecked:
                     kept and listed for an AI check.

Outputs: the plan, the AI review file (Work/Preparation/question-leaks/ai-review.json) and the leak
signature file the extraction gate reads to reject near-duplicates of confirmed leaks.

apply is journalled and lock-protected like merge_question_duplicates: catalog digest bound to the
plan, the full catalog backed up first (Work/Preparation/question-library-organize/catalog.before-prune.json),
records removed in one atomic catalog switch, bytes unlinked only after digest checks. The journal
keeps a manifest (id, path, sha256, size, reason) - not the bytes. rollback restores the catalog
from the backup; deleted bytes cannot be restored (hash manifest only). Run with --help.
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import sys
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'build'))
sys.path.insert(0, str(ROOT / 'src'))
import consolidate_question_media as journalled
import merge_question_duplicates as merge
import organize_question_library as organize
import question_leak_gate as gate
from tutorlib.asset_library import (AssetLibrary, asset_path_key, catalog_writer_lock,
                                    validate_catalog, _directory, _read_at, _atomic_at)

TOOL = 'prune_question_leaks'
WORK = ROOT.parent / 'Work' / 'Preparation' / 'question-leaks'
DEFAULT_PLAN = WORK / 'plan.json'
DEFAULT_REVIEW = WORK / 'ai-review.json'
DEFAULT_BACKUP = organize.WORK / 'catalog.before-prune.json'
OCR_CACHE = 'ocr-cache.json'
COURSES = ('9701', '9702', 'P1', 'P2')
CLASSES = ('LEAK_UNREFERENCED', 'LEAK_REFERENCED', 'SMALL_REVIEW', 'KEEP')


def sha(data: bytes) -> str:
    return journalled._sha(data)


def citations(library: AssetLibrary, records: dict) -> dict[str, set[str]]:
    """asset id -> Library JSON files (packs, banks, topicals, releases, attestations) that cite it.

    Provenance sidecars (*.png.json) describe their own image and do not count as a use.
    """
    refs = {}
    for identifier, record in records.items():
        for ref in [record['path'], *record.get('aliases', [])]:
            refs[asset_path_key(ref)] = identifier
    cited = collections.defaultdict(set)
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
                target = token[6:] if token[6:] in records else None
            else:
                try:
                    target = refs.get(asset_path_key(token))
                except ValueError:
                    target = None
            if target:
                cited[target].add(path)
    return cited


def scope_images(records: dict, courses) -> list[tuple[str, dict, str]]:
    found = []
    for identifier, record in sorted(records.items()):
        place = organize.locate(record['path'])
        if place and place[0] == 'course' and place[1] in courses and organize.is_image(record['path']):
            found.append((identifier, record, place[1]))
    return found


def is_key(path: str) -> bool:
    name = PurePosixPath(path).name
    return PurePosixPath(path).parent.name == 'Keys' or '_key_' in name or '-key-' in name


def ocr_texts(vault: Path, images, cache_path: Path | None, enabled=True) -> dict[str, str]:
    """OCR text per absolute path, cached by sha256 (Library bytes are immutable)."""
    cache = {}
    if cache_path and cache_path.is_file():
        try:
            cache = json.loads(cache_path.read_text())
        except ValueError:
            cache = {}
    if enabled:
        todo = {str((vault / r['path']).resolve()): r['sha256'] for _, r, _ in images if r['sha256'] not in cache}
        if todo:
            for path, text in gate.ocr(list(todo)).items():
                cache[todo[path]] = text
            if cache_path:
                journalled._json(cache_path, cache)
    return {str((vault / r['path']).resolve()): cache[r['sha256']] for _, r, _ in images if r['sha256'] in cache}


def item_context(library: AssetLibrary, files, record: dict, identifier: str, parsed: dict, limit=3) -> list[dict]:
    """Which items in the citing files hold the image (item id, qid, file)."""
    needles = {record['path'], *record.get('aliases', []), 'asset:' + identifier}
    out = []
    for path in sorted(files)[:limit]:
        if path not in parsed:
            try:
                parsed[path] = json.loads(library.read(path))
            except (OSError, ValueError):
                parsed[path] = None
        data = parsed[path]
        items = data.get('items') if isinstance(data, dict) else None
        for item in items if isinstance(items, list) else [data]:
            if not isinstance(item, dict):
                continue
            text = json.dumps(item, ensure_ascii=False)
            if any(needle in text for needle in needles):
                source = item.get('source') if isinstance(item.get('source'), dict) else {}
                out.append({'file': path, 'item': item.get('id'), 'qid': item.get('official_qid') or source.get('qid')})
                break
    return out


def sidecar_identity(library: AssetLibrary, record: dict) -> dict:
    provenance = record.get('provenance') if isinstance(record.get('provenance'), dict) else {}
    for reference in provenance.get('sidecars', []):
        try:
            data = json.loads(library.read(reference))
        except (OSError, ValueError):
            continue
        inner = data.get('record') if isinstance(data, dict) and isinstance(data.get('record'), dict) else {}
        return {'record_id': inner.get('id'), 'qid': inner.get('official_qid'), 'part': inner.get('part'),
                'extraction_job': data.get('extraction_job') if isinstance(data, dict) else None}
    return {}


def build_plan(vault: Path, *, courses=COURSES, ocr=True, cache_path: Path | None = None) -> dict:
    vault = Path(os.path.abspath(vault))
    library = AssetLibrary(vault)
    records = library.records()
    images = scope_images(records, courses)
    cited = citations(library, records)
    learner = merge.learner_references(vault)
    attested = organize.attestation_pins(library, records)
    texts = ocr_texts(vault, images, cache_path, ocr)
    paths = {identifier: str((vault / record['path']).resolve()) for identifier, record, _ in images}
    verdicts = gate.classify_many(list(paths.values()), texts=texts if ocr else {p: None for p in paths.values()},
                                  signatures=[])
    # Near-duplicates of confirmed leaks (another paper's copy of the same data page) inherit the verdict.
    confirmed = [{'dhash': v['dhash'], 'aspect': v['aspect'], 'sha256': records[i]['sha256'], 'reason': v['reason']}
                 for i, v in ((i, verdicts[paths[i]]) for i in paths) if v['action'] == 'delete' and 'dhash' in v
                 and not is_key(records[i]['path'])]
    entries, parsed = [], {}
    for identifier, record, course in images:
        verdict = dict(verdicts[paths[identifier]])
        if verdict['action'] == 'keep' and 'dhash' in verdict:
            match = gate.signature_match(verdict, [c for c in confirmed if c['sha256'] != record['sha256']])
            if match:
                verdict.update(action='delete', reason=f"near-duplicate of confirmed leak {match['sha256'][:12]}")
        keys = {asset_path_key(ref) for ref in [record['path'], *record.get('aliases', [])]}
        holds = []
        if cited.get(identifier):
            holds.append(f'cited by {len(cited[identifier])} Library file(s)')
        if keys & learner or 'asset:' + identifier in learner:
            holds.append('learner event/answer/grade reference')
        if keys & set(attested):
            holds.append('prepared attestation pin')
        if merge.is_pinned(record):
            holds.append('validator-pinned name')
        action = verdict['action']
        if action == 'delete' and is_key(record['path']):
            klass, why = 'SMALL_REVIEW', 'mark-scheme image the gate read as reference matter: never auto-deleted'
        elif action == 'delete':
            klass, why = ('LEAK_REFERENCED' if holds else 'LEAK_UNREFERENCED'), verdict['reason']
        elif action == 'review':
            klass, why = 'SMALL_REVIEW', verdict['reason']
        else:
            klass, why = 'KEEP', verdict['reason']
        entry = {'id': identifier, 'path': record['path'], 'sha256': record['sha256'], 'course': course,
                 'class': klass, 'reason': why, 'holds': holds,
                 'size': (vault / record['path']).stat().st_size if (vault / record['path']).is_file() else None,
                 **{k: verdict.get(k) for k in ('width', 'height', 'ink', 'dhash', 'aspect')}}
        if klass in ('LEAK_REFERENCED', 'SMALL_REVIEW'):
            entry['cited_by'] = sorted(cited.get(identifier, ()))[:5]
            entry['cited_count'] = len(cited.get(identifier, ()))
            entry['items'] = item_context(library, cited.get(identifier, ()), record, identifier, parsed)
            entry['source_record'] = sidecar_identity(library, record)
            entry['ocr_excerpt'] = (texts.get(paths[identifier]) or '')[:240]
        entries.append(entry)
    deletes = [{k: e[k] for k in ('id', 'path', 'sha256', 'size', 'reason', 'course')}
               for e in entries if e['class'] == 'LEAK_UNREFERENCED']
    raw = journalled._read(vault, 'Library/catalog.json')
    return {'format_version': 1, 'tool': TOOL, 'gate_version': gate.VERSION, 'vault': str(vault),
            'courses': list(courses), 'ocr': bool(ocr), 'catalog_sha256': sha(raw), 'deletes': deletes,
            'entries': [e for e in entries if e['class'] != 'KEEP'],
            'kept': sum(e['class'] == 'KEEP' for e in entries), 'errors': []}


def simulate(vault: Path, plan: dict) -> dict:
    """Drop the planned records from an in-memory catalog and prove every Library reference still resolves."""
    library = AssetLibrary(vault)
    records = library.records()
    tokens = merge.scan_tokens(library, records)
    catalog = json.loads(journalled._read(vault, 'Library/catalog.json'))
    gone = {d['id'] for d in plan['deletes']}
    for identifier in gone:
        catalog['assets'].pop(identifier, None)
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
    return {'tokens_checked': len(tokens), 'removed_ids': len(gone), 'broken': broken[:50], 'broken_count': len(broken)}


def summarize(plan: dict) -> dict:
    table = collections.defaultdict(collections.Counter)
    for entry in plan['entries']:
        table[entry['course']][entry['class']] += 1
    return {'by_course': {k: dict(v) for k, v in sorted(table.items())},
            'by_class': dict(collections.Counter(e['class'] for e in plan['entries'])),
            'kept': plan['kept'], 'deletes': len(plan['deletes']),
            'bytes_to_free': sum(d['size'] or 0 for d in plan['deletes'])}


def review_file(plan: dict) -> dict:
    rows = [e for e in plan['entries'] if e['class'] in ('LEAK_REFERENCED', 'SMALL_REVIEW')]
    return {'format_version': 1, 'tool': TOOL, 'catalog_sha256': plan['catalog_sha256'],
            'instructions': ('AI check: LEAK_REFERENCED images are data-sheet/periodic-table/constants pages a question '
                             'item still cites; Library items are immutable, so removal needs a new reviewed revision '
                             '(e.g. a new topical release without the image). SMALL_REVIEW images are tiny, near-blank '
                             'or unchecked: confirm each is real question/answer content or mark it for removal.'),
            'counts': dict(collections.Counter(r['class'] for r in rows)),
            'items': [{k: r.get(k) for k in ('class', 'course', 'id', 'path', 'sha256', 'width', 'height', 'reason',
                                             'holds', 'cited_count', 'cited_by', 'items', 'source_record', 'ocr_excerpt')}
                      for r in rows]}


def signatures(plan: dict) -> dict:
    return {'format_version': 1, 'tool': TOOL, 'gate_version': gate.VERSION,
            'signatures': [{k: e[k] for k in ('dhash', 'aspect', 'sha256', 'reason', 'width', 'height')}
                           for e in plan['entries'] if e['class'].startswith('LEAK_') and e.get('dhash')]}


def _unlink(vault: Path, deletes: list[dict]) -> int:
    freed = 0
    for entry in deletes:
        path = vault / entry['path']
        if not (path.exists() or path.is_symlink()):
            continue
        if sha(journalled._read(vault, entry['path'])) != entry['sha256']:
            raise ValueError(f"leak bytes changed before delete: {entry['path']}")
        size = path.stat().st_size
        with _directory(vault, list(Path(entry['path']).parts[:-1])) as directory:
            os.unlink(path.name, dir_fd=directory)
        freed += size
    return freed  # Folders are left in place; nothing else is removed to empty them.


def _backup(raw: bytes, backup: Path) -> Path:
    backup = Path(backup)
    if backup.exists() and sha(backup.read_bytes()) != sha(raw):
        backup = backup.with_name(f'{backup.stem}-{sha(raw)[:12]}{backup.suffix}')
    if not backup.exists():
        backup.parent.mkdir(parents=True, exist_ok=True)
        temp = backup.with_name(backup.name + '.tmp')
        temp.write_bytes(raw)
        os.replace(temp, backup)
    if sha(backup.read_bytes()) != sha(raw):
        raise ValueError('catalog backup digest mismatch')
    return backup


def apply(plan: dict, journal: Path, *, backup: Path = DEFAULT_BACKUP) -> dict:
    if plan.get('tool') != TOOL or plan.get('errors'):
        raise ValueError('not a clean prune_question_leaks plan')
    if plan.get('reference_check', {}).get('broken_count', 1) != 0:
        raise ValueError('plan was not reference-verified')
    vault, journal = Path(plan['vault']), Path(os.path.abspath(journal))
    if journal.is_relative_to(vault) or Path(os.path.abspath(backup)).is_relative_to(vault):
        raise ValueError('prune journal and catalog backup must be outside the learner vault')
    with catalog_writer_lock(vault) as directory:
        raw = _read_at(directory, 'catalog.json')
        saved = json.loads(journal.read_text()) if journal.exists() else None
        if saved:
            if saved.get('vault') != str(vault) or saved.get('tool') != TOOL:
                raise ValueError('journal belongs to another operation')
            if saved['deletes'] != plan['deletes']:
                raise ValueError('journal does not match requested prune plan')
            if saved['status'] == 'complete':
                if sha(raw) != saved['catalog_after_sha256']:
                    raise ValueError('catalog changed after completed prune')
                return {'status': 'complete', 'deleted': len(saved['deletes']), 'journal': str(journal)}
            if saved['status'] == 'committed' or (saved['status'] == 'switching'
                                                  and sha(raw) == saved['catalog_after_sha256']):
                saved['bytes_freed'] = saved.get('bytes_freed', 0) + _unlink(vault, saved['deletes'])
                saved['status'] = 'complete'; journalled._json(journal, saved)
                return {'status': 'complete', 'deleted': len(saved['deletes']), 'bytes_freed': saved['bytes_freed'],
                        'journal': str(journal)}
        if sha(raw) != plan['catalog_sha256']:
            raise ValueError('catalog changed since prune plan')
        catalog = json.loads(raw)
        cited = merge.learner_references(vault)
        for entry in plan['deletes']:
            record = catalog['assets'].get(entry['id'])
            if record is None or record['path'] != entry['path'] or record['sha256'] != entry['sha256']:
                raise ValueError(f"leak identity changed since plan: {entry['id']}")
            if sha(journalled._read(vault, entry['path'])) != entry['sha256']:
                raise ValueError(f"leak digest changed since plan: {entry['path']}")
            keys = {asset_path_key(ref) for ref in [record['path'], *record.get('aliases', [])]}
            if keys & cited or 'asset:' + entry['id'] in cited:
                raise ValueError(f"learner reference appeared since plan: {entry['path']}")
        copy = _backup(raw, backup)
        manifest = [{**entry, 'aliases': catalog['assets'][entry['id']].get('aliases', []),
                     'record': {k: v for k, v in catalog['assets'][entry['id']].items() if k != 'aliases'}}
                    for entry in plan['deletes']]
        saved = {'format_version': 1, 'tool': TOOL, 'vault': str(vault), 'status': 'prepared',
                 'catalog_before_sha256': sha(raw), 'catalog_backup': str(copy), 'deletes': plan['deletes'],
                 'manifest': manifest, 'bytes_restorable': False,
                 'note': 'Deleted bytes are not kept; rollback restores catalog records only (hash manifest above).'}
        journalled._json(journal, saved)
        for entry in plan['deletes']:
            catalog['assets'].pop(entry['id'])
        validate_catalog(catalog)
        updated = (json.dumps(catalog, ensure_ascii=False, indent=2) + '\n').encode() if plan['deletes'] else raw
        saved['catalog_after_sha256'] = sha(updated)
        saved['status'] = 'switching'; journalled._json(journal, saved)
        if plan['deletes']:
            _atomic_at(directory, 'catalog.json', updated, replace=True)
        saved['status'] = 'committed'; journalled._json(journal, saved)
        saved['bytes_freed'] = _unlink(vault, plan['deletes'])
        saved['status'] = 'complete'; journalled._json(journal, saved)
    return {'status': 'complete', 'deleted': len(plan['deletes']), 'bytes_freed': saved['bytes_freed'],
            'journal': str(journal), 'catalog_backup': str(copy)}


def rollback(journal: Path) -> dict:
    """Restore the pre-prune catalog from the verified backup. Deleted bytes cannot come back."""
    journal = Path(journal)
    saved = json.loads(journal.read_text())
    if saved.get('tool') != TOOL:
        raise ValueError('not a prune_question_leaks journal')
    vault = Path(saved['vault'])
    before = Path(saved['catalog_backup']).read_bytes()
    if sha(before) != saved['catalog_before_sha256']:
        raise ValueError('catalog backup digest mismatch')
    with catalog_writer_lock(vault) as directory:
        raw = _read_at(directory, 'catalog.json')
        allowed = {saved.get('catalog_after_sha256'), saved['catalog_before_sha256']}
        if sha(raw) not in allowed:
            raise ValueError('catalog changed; automatic rollback would discard other work')
        saved['status'] = 'rolling_back'; journalled._json(journal, saved)
        _atomic_at(directory, 'catalog.json', before, replace=True)
        missing = [d['path'] for d in saved['deletes'] if not (vault / d['path']).is_file()]
        saved['status'] = 'rolled_back'; saved['bytes_missing_after_rollback'] = missing
        journalled._json(journal, saved)
    return {'status': 'rolled_back', 'records_restored': len(saved['deletes']), 'bytes_missing': len(missing),
            'note': 'catalog restored; deleted bytes are not recoverable from this journal (sha256 manifest only)'}


def cmd_plan(args):
    plan = build_plan(args.vault, courses=tuple(args.courses.split(',')), ocr=not args.no_ocr,
                      cache_path=args.out.parent / OCR_CACHE)
    plan['reference_check'] = simulate(Path(plan['vault']), plan)
    journalled._json(args.out, plan)
    journalled._json(args.review, review_file(plan))
    journalled._json(args.signatures, signatures(plan))
    print(json.dumps(summarize(plan) | {'reference_check': plan['reference_check']['broken_count'],
                                       'out': str(args.out), 'review': str(args.review)}, indent=1))


def cmd_apply(args):
    if not args.yes:
        raise SystemExit('apply changes the vault catalog and deletes bytes: pass --yes after reading the plan')
    print(json.dumps(apply(json.loads(args.plan.read_text()), args.journal, backup=args.backup)))


def cmd_rollback(args):
    print(json.dumps(rollback(args.journal)))


def cmd_gate(args):
    return gate.main([*map(str, args.images), *(['--json'] if args.json else [])])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('plan', help='read-only classification; writes plan, AI review file and leak signatures')
    p.add_argument('--vault', type=Path, default=ROOT.parent / 'STEM Tutor')
    p.add_argument('--courses', default=','.join(COURSES))
    p.add_argument('--out', type=Path, default=DEFAULT_PLAN)
    p.add_argument('--review', type=Path, default=DEFAULT_REVIEW)
    p.add_argument('--signatures', type=Path, default=gate.SIGNATURES)
    p.add_argument('--no-ocr', action='store_true', help='size/ink/hash signals only')
    p.set_defaults(func=cmd_plan)
    p = sub.add_parser('apply')
    p.add_argument('--plan', type=Path, required=True)
    p.add_argument('--journal', type=Path, required=True)
    p.add_argument('--backup', type=Path, default=DEFAULT_BACKUP)
    p.add_argument('--yes', action='store_true')
    p.set_defaults(func=cmd_apply)
    p = sub.add_parser('rollback')
    p.add_argument('--journal', type=Path, required=True)
    p.set_defaults(func=cmd_rollback)
    p = sub.add_parser('gate', help='extraction-time verdict for image files (same as question_leak_gate.py)')
    p.add_argument('images', nargs='+', type=Path)
    p.add_argument('--json', action='store_true')
    p.set_defaults(func=cmd_gate)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == '__main__':
    raise SystemExit(main())
