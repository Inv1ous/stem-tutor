"""Plan one naming convention for every question image, without guessing.

Name: <course>_<series><yy>_<paper>_q<NN>[<part>]_<role>_<sha12>.<ext>
  role mcq|long|key|ref|ctx, sha12 = first 12 hex of the file's sha256.

A question is identified from its own metadata only, strongest evidence first: the
sidecar record (official_qid/kind/part), bank/pack/topical item ids, an already
canonical name, catalog provenance, then file-name tokens (s17_11_q12, w25, ms).
An image whose question id cannot be derived keeps its name and is listed under
``unnamed`` with the reason; nothing is invented.

Multi-page questions (one question, one role, 2+ images of different content) are
reported as one group and each page gets ``_p01``, ``_p02`` before the role/sha12
tail. Single-image questions never get a page suffix; identical-content duplicates
are listed on the group instead of being numbered as pages.

Sub-command ``plan`` (the default) is read-only against the vault and writes the
JSON plan to ``--report``. There is no apply: the Library move stays with the
journalled ``organize_question_library.py apply --plan``.
"""
from __future__ import annotations

import argparse
import collections
import json
import re
import sys
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'build'))
sys.path.insert(0, str(ROOT / 'src'))
import consolidate_question_media as journalled
import organize_question_library as organizer
from question_media_names import (FOLDER, KEY_WORDS, canonical_name, classify, filename_role, parse_qid)
from tutorlib.asset_library import AssetLibrary, asset_path_key

TOOL = 'normalize_question_names'
DEFAULT_VAULT = ROOT.parent / 'STEM Tutor'
WORK = ROOT.parent / 'Work' / 'Preparation' / 'question-naming'
PAGE = '_p{:02d}'
TAIL = re.compile(r'_(?P<role>mcq|long|key|ref|ctx)_(?P<sha12>[0-9a-f]{12})(?P<ext>\.[a-z0-9.]+)$')


def question_images(decisions: dict) -> dict:
    """Course question images only: Library/Courses/<course>/Questions/Media/**."""
    return {identifier: entry for identifier, entry in decisions.items()
            if entry['scope'] == 'course' and entry['area'] == 'Media'}


def split_name(name: str) -> tuple:
    """(stem, role, sha12, ext) of a canonical name, or (name, None, None, '') when it is not one."""
    match = TAIL.search(name)
    if match is None:
        return name, None, None, ''
    return name[:match.start()], match.group('role'), match.group('sha12'), match.group('ext')


def with_page(name: str, number: int) -> str:
    """Insert the page suffix before the role/sha12 tail; a non-canonical name is left alone."""
    stem, role, _, _ = split_name(name)
    return f'{stem}{PAGE.format(number)}_{role}{name[len(stem) + len(role) + 1:]}' if role else name


def sidecar_ids(records: dict, by_path: dict, record: dict) -> list:
    """Sidecar records declared by provenance, plus the conventional <name>.png.json."""
    provenance = record.get('provenance') if isinstance(record.get('provenance'), dict) else {}
    references = [*provenance.get('sidecars', []), record['path'] + '.json']
    found = []
    for reference in references:
        identifier = by_path.get(reference) or (reference[6:] if reference.startswith('asset:') else None)
        if identifier in records and identifier not in found:
            found.append(identifier)
    return found


def metadata_qid(library: AssetLibrary, records: dict, by_path: dict, record: dict) -> tuple:
    """Question id declared by the image's own sidecar or catalog provenance, if any."""
    provenance = record.get('provenance') if isinstance(record.get('provenance'), dict) else {}
    declared = provenance.get('official_qid') or provenance.get('qid')
    if isinstance(declared, str) and declared:
        return declared, str(provenance.get('part') or '')
    for identifier in sidecar_ids(records, by_path, record):
        try:
            data = json.loads(library.read('asset:' + identifier))
        except (ValueError, OSError):
            continue
        if not isinstance(data, dict):
            continue
        inner = data.get('record') if isinstance(data.get('record'), dict) else {}
        for source in (data, inner):
            qid = source.get('official_qid') or source.get('qid') or source.get('question_id')
            if isinstance(qid, str) and qid:
                return qid, str(source.get('part') or '')
    return None, ''


def rescue_metadata(library: AssetLibrary, records: dict, by_path: dict,
                    images: dict, named: dict, unnamed: list) -> list:
    """Name an unnamed image only when its own sidecar or catalog metadata states the question id."""
    remaining = []
    for row in unnamed:
        entry = images[row['id']]
        qid, part = metadata_qid(library, records, by_path, records[row['id']])
        parsed = parse_qid(qid)
        if entry['problem'] or entry['role'] is None or parsed is None or parsed['course'] != entry['course']:
            remaining.append(row)
            continue
        entry['qid'], entry['qid_state'] = qid, 'single'
        entry['name'] = canonical_name(entry['course'], entry['role'], entry['sha256'], qid=qid,
                                       part=part or parsed['part'], ext=PurePosixPath(entry['path']).suffix)
        entry['fallback'] = False
        named[row['id']] = entry
    return remaining


def reference_tokens(records: dict) -> tuple:
    """Every path and alias a record answers to, plus keys that two records both claim.

    A key claimed by more than one record cannot prove anything, so it is reported as
    ambiguous instead of being resolved to whichever record happened to be read last.
    """
    tokens, ambiguous = {}, {}
    for identifier, record in records.items():
        for reference in [record['path'], *record.get('aliases', [])]:
            key = reference if reference.startswith('asset:') else asset_path_key(reference)
            if key in ambiguous:
                ambiguous[key].add(identifier)
            elif key in tokens and tokens[key] != identifier:
                ambiguous[key] = {tokens.pop(key), identifier}
            else:
                tokens[key] = identifier
    return tokens, {key: sorted(ids) for key, ids in ambiguous.items()}


def page_of(library: AssetLibrary, records: dict, by_path: dict, record: dict) -> int | None:
    """Source page of an image, read from its sidecar only (no image decode)."""
    for identifier in sidecar_ids(records, by_path, record):
        try:
            data = json.loads(library.read('asset:' + identifier))
        except (ValueError, OSError):
            continue
        if not isinstance(data, dict):
            continue
        if isinstance(data.get('page'), int):
            return data['page']
        inner = data.get('record') if isinstance(data.get('record'), dict) else {}
        regions = inner.get('regions') or data.get('regions') or []
        pages = [region['page'] for region in regions
                 if isinstance(region, dict) and isinstance(region.get('page'), int)]
        if pages:
            return min(pages)
    return None


def page_groups(library: AssetLibrary, records: dict, decisions: dict) -> list:
    """Number the pages of every multi-image question and return the groups.

    A group is one question (same course, same canonical stem, same role folder) with
    2+ images of different content. Pages are ordered by sidecar page, then by path.
    Identical content is a duplicate, not a page, and is listed on the group.
    """
    by_path = {record['path']: identifier for identifier, record in records.items()}
    buckets = collections.defaultdict(list)
    for identifier, entry in decisions.items():
        stem, role, _, _ = split_name(entry['name'])
        if role is None:
            continue
        buckets[(entry['course'], stem, FOLDER[role])].append(identifier)
    groups = []
    for key, identifiers in sorted(buckets.items()):
        if len({decisions[i]['sha256'] for i in identifiers}) < 2:
            continue
        ordered_ids = sorted(identifiers, key=lambda i: ('--' in PurePosixPath(decisions[i]['path']).name,
                                                         len(decisions[i]['path']), decisions[i]['path']))
        pages, duplicates, seen = [], [], {}
        for identifier in ordered_ids:
            digest = decisions[identifier]['sha256']
            if digest in seen:
                duplicates.append({'id': identifier, 'path': decisions[identifier]['path'],
                                   'same_as': seen[digest]})
                continue
            seen[digest] = decisions[identifier]['path']
            page = page_of(library, records, by_path, records[identifier])
            pages.append((page if page is not None else 10 ** 6, decisions[identifier]['path'], identifier, page))
        pages.sort()
        for number, (_, _, identifier, page) in enumerate(pages, start=1):
            entry = decisions[identifier]
            entry['name'] = with_page(entry['name'], number)
            entry['page'] = number
            entry['page_source'] = 'sidecar' if page is not None else 'path-order'
            entry['group'] = len(groups)
        groups.append({'course': key[0], 'stem': key[1], 'folder': key[2], 'pages': len(pages),
                       'images': [{'id': identifier, 'path': decisions[identifier]['path'],
                                   'page': decisions[identifier]['page'],
                                   'page_source': decisions[identifier]['page_source'],
                                   'name': decisions[identifier]['name']}
                                  for _, _, identifier, _ in pages],
                       'duplicates': duplicates})
    return groups


def unnamed_reason(entry: dict) -> str:
    """Why an image cannot be named: the recorded problem, or the missing question id."""
    if entry['problem']:
        return entry['problem']
    name = PurePosixPath(entry['path']).name.lower()
    if filename_role(name) == 'key' or KEY_WORDS.search(name):
        return 'mark-scheme image without question id'
    return 'no question id'


def role_check(entry: dict) -> bool:
    """True when the name's own role token disagrees with the role it was given."""
    verdict = classify([(0, entry['role'], 'canonical-name')], entry['name'])
    return bool(verdict['conflict'] or verdict['role'] != entry['role'])


def build_report(vault: Path, *, references: bool = True) -> dict:
    """Read-only plan: canonical names, page suffixes, moves, unnamed images."""
    vault = Path(vault).resolve()
    library, records, decisions, unclassified = organizer.decide(vault)
    images = question_images(decisions)
    unnamed = []
    for identifier, entry in sorted(images.items()):
        if entry['problem'] or entry.get('fallback'):
            unnamed.append({'id': identifier, 'path': entry['path'], 'course': entry['course'],
                            'qid_state': entry['qid_state'], 'reason': unnamed_reason(entry)})
    named = {identifier: entry for identifier, entry in images.items()
             if not entry['problem'] and not entry.get('fallback')}
    by_path = {record['path']: identifier for identifier, record in records.items()}
    unnamed = rescue_metadata(library, records, by_path, images, named, unnamed)
    groups = page_groups(library, records, named)
    conflicts = [identifier for identifier, entry in named.items() if role_check(entry)]
    plan = organizer.build_plan(vault, (library, records, named, unclassified), scope='course')
    if references:
        tokens, ambiguous = reference_tokens(records)
        check = organizer.simulate(vault, plan['moves'], tokens)
        check.update({'ambiguous': ambiguous, 'ambiguous_count': len(ambiguous)})
        plan['reference_check'] = check
    plan.update({'tool': TOOL, 'producer': TOOL, 'format_version': 1, 'vault': str(vault),
                 'unnamed': unnamed, 'multi_page_groups': groups,
                 'role_conflicts': [{'id': identifier, 'path': named[identifier]['path'],
                                     'role': named[identifier]['role'], 'name': named[identifier]['name']}
                                    for identifier in conflicts]})
    plan['per_course'] = per_course(images, groups)
    plan['summary'] = summarize(images, named, unnamed, groups, plan, conflicts)
    plan['summary']['per_course'] = plan['per_course']
    return plan


def per_course(images: dict, groups: list) -> dict:
    """One clean row per course: named, unnamed, multi-page groups and images, duplicate groups."""
    table = collections.defaultdict(lambda: {'named': 0, 'unnamed': 0, 'multi_page_groups': 0,
                                             'multi_page_images': 0, 'duplicate_groups': 0})
    for entry in images.values():
        table[entry['course']]['unnamed' if entry['problem'] or entry.get('fallback') else 'named'] += 1
    for group in groups:
        table[group['course']]['multi_page_groups'] += 1
        table[group['course']]['multi_page_images'] += group['pages']
    by_course = collections.defaultdict(collections.Counter)
    for entry in images.values():
        by_course[entry['course']][entry['sha256']] += 1
    for course, counts in by_course.items():
        table[course]['duplicate_groups'] = sum(1 for count in counts.values() if count > 1)
    return {course: dict(row) for course, row in sorted(table.items())}


def summarize(images: dict, named: dict, unnamed: list, groups: list, plan: dict, conflicts: list) -> dict:
    table = collections.defaultdict(collections.Counter)
    for entry in images.values():
        row = table[entry['course']]
        row['images'] += 1
        row['unnamed' if entry['problem'] or entry.get('fallback') else 'named'] += 1
        row['pinned'] += bool(entry['pinned'])
        row['multi-page'] += bool(entry.get('group') is not None)
    for move in plan['moves']:
        detail = plan['details'].get(move['id'])
        if detail:
            table[detail['course']]['moves'] += 1
    return {'courses': {course: dict(row) for course, row in sorted(table.items())},
            'totals': {'images': len(images), 'named': len(named), 'unnamed': len(unnamed),
                       'held_pinned': len(plan['held']), 'moves': len(plan['moves']),
                       'already_canonical': len(named) - len(plan['details']) - len(plan['held']),
                       'multi_page_groups': len(groups),
                       'multi_page_images': sum(group['pages'] for group in groups),
                       'duplicate_pages': sum(len(group['duplicates']) for group in groups),
                       'role_conflicts': len(conflicts), 'errors': len(plan['errors'])},
            'unnamed_reasons': dict(collections.Counter(entry['reason'] for entry in unnamed)),
            'qid_states': dict(collections.Counter(entry['qid_state'] for entry in named.values()))}


def write(path: Path, data: dict) -> None:
    journalled._json(Path(path), data)


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('command', nargs='?', default='plan', choices=('plan',))
    parser.add_argument('--vault', type=Path, default=DEFAULT_VAULT)
    parser.add_argument('--report', type=Path, default=WORK / 'normalize-plan.json')
    parser.add_argument('--skip-references', action='store_true')
    args = parser.parse_args(argv)
    vault = Path(args.vault).resolve()
    report = Path(args.report).resolve()
    if report.is_relative_to(vault):
        raise SystemExit('refusing to write a plan inside the read-only vault')
    plan = build_report(vault, references=not args.skip_references)
    write(report, plan)
    print(json.dumps({'plan': str(report), 'moves': len(plan['moves']), 'held': len(plan['held']),
                      'errors': len(plan['errors']), 'unnamed': len(plan['unnamed']),
                      'reference_check': plan.get('reference_check', {}).get('broken_count'),
                      'summary': plan['summary']['totals']}))


if __name__ == '__main__':
    main()
