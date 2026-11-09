"""Organize question media into Library/Courses/<course>/Questions/Media/{MCQ,Long,Keys,Reference} with canonical names.

Every course's question images end up in that course's own Media folder, including the crops the source-practice
extraction first stored in Library/SourcePractice/Media. A crop that is byte-for-byte the same for more than one
course (an answer-key cell such as "8 | D") goes to Library/Shared/Questions/Media. The plan also lists past-paper
questions stored more than once (duplicate-questions.json).

audit and plan are read-only against the vault. apply and rollback reuse the journalled,
lock-protected machinery of consolidate_question_media (copies verified, old paths stay
declared aliases, stable asset ids unchanged, exact rollback journal). Run with --help.
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
from question_media_names import (COURSES, FOLDER, IMAGE_EXTENSIONS, canonical_name, classify,
                                  parse_qid, qid_from_filename, legacy_base, is_fallback, canonical_parts)
from tutorlib.asset_library import AssetLibrary, asset_path_key, validate_catalog

TOOL = 'organize_question_library'
WORK = ROOT.parent / 'Work' / 'Preparation' / 'question-library-organize'
ARCHIVE = ROOT.parent / 'Archive' / 'question-library-organize'
FOLDERS = ('MCQ', 'Long', 'Keys', 'Reference')
PINNED = re.compile(r'.+-[0-9a-f]{12}-[0-9a-f]{16}\.[a-z]+\Z')
ATTESTATION = '/Sources/Provenance/prepared-v1/'
TOKEN = re.compile(r'"((?:asset:[A-Za-z0-9._:/-]+)|(?:[^"\\\n]+?\.(?:png|jpg|jpeg|svg|webp)))"')


def locate(path: str):
    """Return (scope, course, area) for an in-scope catalog path, else None."""
    parts = PurePosixPath(path).parts
    if parts[:3] == ('Library', 'SourcePractice', 'Media') and len(parts) >= 4:
        return 'sourcepractice', None, 'SourcePractice/Media'
    if parts[:2] == ('Library', 'Courses') and len(parts) > 5 and parts[2] in COURSES and parts[3] == 'Questions':
        rest = parts[4:]
        if rest[0] == 'Media':
            return 'course', parts[2], 'Media'
        if rest[0] == 'Topicals':
            return 'course', parts[2], 'Topicals'
        if rest[:2] == ('SourceVerified', 'Media'):
            return 'course', parts[2], 'SourceVerified/Media'
    return None


def is_image(path: str) -> bool:
    return path.lower().endswith(IMAGE_EXTENSIONS)


def is_sidecar(path: str) -> bool:
    return path.endswith('.png.json') and locate(path) is not None


def attestation_pins(library: AssetLibrary, records: dict) -> dict:
    """Pinned media whose reference string is fixed inside an immutable prepared attestation.

    Those references are compared literally against the reviewed name, so a path move
    cannot be expressed as an alias without rewriting the attestation. They stay put.
    """
    pins = {}
    for identifier, record in records.items():
        path = record['path']
        if ATTESTATION not in path or not path.endswith('.json'):
            continue
        try:
            data = json.loads(library.read('asset:' + identifier))
        except (ValueError, OSError):
            continue
        media = data.get('media') if isinstance(data, dict) else None
        if not isinstance(media, dict):
            continue
        for group in media.values():
            if not isinstance(group, dict):
                continue
            for pin in group.values():
                reference = pin.get('reference') if isinstance(pin, dict) else None
                if isinstance(reference, str):
                    try:
                        pins[asset_path_key(reference)] = path
                    except ValueError:
                        continue
    return pins


class Evidence:
    def __init__(self, records: dict):
        self.records = records
        self.refs = {}
        for identifier, record in records.items():
            for ref in [record['path'], *record.get('aliases', [])]:
                self.refs[asset_path_key(ref)] = identifier
        self.votes = collections.defaultdict(list)
        self.qids = collections.defaultdict(list)
        self.courses = collections.defaultdict(set)
        self.sidecar_qid = {}
        self.topics = collections.defaultdict(set)  # booklet questions without an exam-paper id: (title, label)

    def resolve(self, reference):
        if not isinstance(reference, str) or not reference:
            return None
        if reference.startswith('asset:'):
            return reference[6:] if reference[6:] in self.records else None
        try:
            return self.refs.get(asset_path_key(reference))
        except ValueError:
            return None

    def vote(self, reference, tier, role, source, qid=None, part='', course=None):
        identifier = self.resolve(reference)
        if identifier is None:
            return
        self.votes[identifier].append((tier, role, source))
        if qid:
            self.qids[identifier].append((qid, part or ''))
        if course:
            self.courses[identifier].add(course)


def _media_refs(item):
    media = item.get('media') if isinstance(item.get('media'), dict) else item
    for key in ('question_media', 'context_media', 'mark_scheme_media'):
        for entry in media.get(key) or []:
            if isinstance(entry, dict):
                for field in ('path', 'original'):
                    if entry.get(field):
                        yield key, entry[field]
            elif isinstance(entry, str):
                yield key, entry


def item_votes(evidence: Evidence, item: dict, source: str, course=None):
    kind = item.get('kind')
    if kind not in ('mcq', 'structured'):
        return
    qid = item.get('official_qid')
    if not qid and isinstance(item.get('source'), dict):
        qid = item['source'].get('qid')
    roles = {'question_media': 'mcq' if kind == 'mcq' else 'long',
             'context_media': 'mcq' if kind == 'mcq' else 'ctx', 'mark_scheme_media': 'key'}
    topic = None
    if not qid and isinstance(item.get('source'), str) and item.get('label') is not None:
        topic = (item['source'], str(item['label']))
    for key, reference in _media_refs(item):
        evidence.vote(reference, 1, roles[key], source, qid, item.get('part') or '', item.get('course') or course)
        if topic and (identifier := evidence.resolve(reference)):
            evidence.topics[identifier].add(topic)


def topical_votes(evidence: Evidence, item: dict, source: str):
    kind, qid = item.get('kind'), (item.get('source') or {}).get('qid') if isinstance(item.get('source'), dict) else None
    role = {'mcq': 'mcq', 'structured': 'long'}.get(kind)
    if role is None:
        return
    references = [*(item.get('images') or [])]
    if item.get('image'):
        references.append(item['image'])
    for reference in references:
        evidence.vote(reference, 1, role, source, qid, '', (parse_qid(qid) or {}).get('course'))


MARK_SCHEME_PDF = re.compile(r'(?:^|[_\-/])(?:ms|markscheme|mark_scheme|mark-scheme)(?:[_\-.]\w*)?\.pdf$', re.IGNORECASE)


def sidecar_votes(evidence: Evidence, library: AssetLibrary, image_id: str, path: str, reference: str):
    try:
        data = json.loads(library.read(reference))
    except (ValueError, OSError):
        return
    if not isinstance(data, dict):
        return
    record = data.get('record') if isinstance(data.get('record'), dict) else {}
    kind, qid = record.get('kind'), record.get('official_qid')
    base = 'media/' + legacy_base(PurePosixPath(path).name)
    private = data.get('private_media') if isinstance(data.get('private_media'), dict) else {}
    media_name = data.get('media_name') if isinstance(data.get('media_name'), str) else ''
    role = {'mcq': 'mcq', 'structured': 'long'}.get(kind)
    lists = ('question_media', 'mark_scheme_media', 'context_media')
    vote = None
    if base in (record.get('mark_scheme_media') or []) or path in private.values() or base in private \
            or media_name.startswith('private/'):
        vote = 'key'
    elif role and base in (record.get('question_media') or []):
        vote = role
    elif role and base in (record.get('context_media') or []):
        vote = 'ctx' if role == 'long' else role
    elif role and media_name.startswith('public/'):
        vote = role
    elif role and not any(record.get(key) for key in lists) and base in (record.get('media') or []):
        vote = role
    # A region cut from a mark-scheme PDF is an answer key whatever the sidecar's record says.
    sources = {entry.get('id'): entry for entry in data.get('source_inventory') or [] if isinstance(entry, dict)}
    for region in data.get('regions') or []:
        source = sources.get(region.get('source_id')) if isinstance(region, dict) else None
        if source and MARK_SCHEME_PDF.search(str(source.get('path') or '')):
            vote = 'key'
            break
    if vote:
        evidence.votes[image_id].append((1, vote, 'sidecar'))
    if qid:
        evidence.qids[image_id].append((qid, record.get('part') or ''))
    if data.get('course'):
        evidence.courses[image_id].add(data['course'])


def structured_files(records):
    for identifier, record in sorted(records.items()):
        path = record['path']
        if not path.endswith('.json') or path.endswith('.png.json'):
            continue
        if '/SourceVerified/' in path and PurePosixPath(path).name.startswith('bank'):
            yield 'bank', identifier, path
        elif '/Topicals/' in path:
            yield 'topical', identifier, path
        elif path.startswith('Library/SourcePractice/Releases/'):
            yield 'release', identifier, path


def collect(vault: Path, *, files=None):
    """Gather every classification vote from sidecars, banks, releases and topical files."""
    library = AssetLibrary(vault)
    records = library.records()
    evidence = Evidence(records)
    for identifier, record in sorted(records.items()):
        if locate(record['path']) is None or not is_image(record['path']):
            continue
        provenance = record.get('provenance') if isinstance(record.get('provenance'), dict) else {}
        references = [*provenance.get('sidecars', [])]
        if evidence.resolve(record['path'] + '.json'):
            references.append(record['path'] + '.json')
        for reference in dict.fromkeys(references):
            if evidence.resolve(reference):
                sidecar_votes(evidence, library, identifier, record['path'], reference)
    for kind, identifier, path in structured_files(records):
        course = (locate(path) or (None, None, None))[1] or (PurePosixPath(path).parts[2] if '/Courses/' in path else None)
        try:
            data = json.loads(library.read('asset:' + identifier))
        except (ValueError, OSError):
            continue
        if isinstance(data, dict) and isinstance(data.get('items'), list):
            for item in data['items']:
                if isinstance(item, dict):
                    (topical_votes if kind == 'topical' else item_votes)(evidence, item, kind + ':' + path, *([] if kind == 'topical' else [course]))
        elif kind == 'topical' and isinstance(data, dict) and data.get('image') and data.get('qid'):
            if data.get('answer') in ('A', 'B', 'C', 'D'):
                evidence.vote(data['image'], 2, 'mcq', 'review-candidate:' + path, data['qid'], '',
                              (parse_qid(data['qid']) or {}).get('course'))
    for identifier, record in records.items():
        for ref in [record['path'], *record.get('aliases', []), *record.get('origins', [])]:
            segments = PurePosixPath(ref).parts
            if 'mcq' in segments[:-1] or 'topicals' in segments[:-1]:
                evidence.votes[identifier].append((3, 'mcq', 'path-segment'))
                break
        provenance = record.get('provenance') if isinstance(record.get('provenance'), dict) else {}
        region = provenance.get('region') if isinstance(provenance.get('region'), dict) else {}
        if provenance.get('visibility') == 'private_answer' or region.get('role') == 'ms':
            evidence.votes[identifier].append((2, 'key', 'provenance'))
    return library, records, evidence


def choose_qid(candidates, course):
    parsed = {}
    for qid, part in candidates:
        info = parse_qid(qid)
        if info is None or info['course'] != course:
            continue
        parsed[(qid, part)] = info
    if not parsed:
        return None, '', 'none'
    distinct = {(i['series'], i['paper']) for i in parsed.values()}
    if len(distinct) > 1:
        return None, '', 'ambiguous'
    qid, part = min(parsed, key=lambda k: (parsed[k]['question'], k[1]))
    return qid, part, 'multi' if len({k[0] for k in parsed}) > 1 else 'single'


def decide(vault: Path):
    """Classify every in-scope image; return (records, per-asset decisions, unclassified)."""
    library, records, evidence = collect(vault)
    decisions, unclassified = {}, []
    for identifier, record in sorted(records.items()):
        path = record['path']
        place = locate(path)
        if place is None or not is_image(path):
            continue
        scope, path_course, area = place
        name = PurePosixPath(path).name
        votes = list(evidence.votes.get(identifier, []))
        named = canonical_parts(name)
        if named and PurePosixPath(path).parent.name == FOLDER[named['role']] and named['sha12'] == record['sha256'][:12]:
            votes.append((0, named['role'], 'canonical-name'))
        verdict = classify(votes, name)
        courses = evidence.courses.get(identifier, set()) | ({path_course} if path_course else set())
        course = path_course or (next(iter(courses)) if len(courses) == 1 else None)
        problem = None
        shared = scope == 'sourcepractice' and len(courses) > 1  # one file several courses' items cite
        if verdict['conflict']:
            problem = 'conflicting evidence: ' + ','.join(verdict['disagree'])
        elif verdict['role'] is None:
            problem = 'no classification evidence'
        elif len(courses) > 1 and not shared:
            problem = 'conflicting courses: ' + ','.join(sorted(courses))
        elif course is None and not shared:
            problem = 'course not determinable'
        candidates = list(evidence.qids.get(identifier, []))
        legacy = qid_from_filename(name)
        if legacy:
            candidates.append((legacy, ''))
        qid, part, qid_state = choose_qid(candidates, course) if course else (None, '', 'none')
        topics = evidence.topics.get(identifier, set())
        topic, label = next(iter(topics)) if qid is None and len(topics) == 1 else (None, None)
        entry = {'id': identifier, 'path': path, 'sha256': record['sha256'], 'scope': scope, 'area': area,
                 'course': None if shared else course, 'shared': shared, 'role': verdict['role'], 'tier': verdict['tier'], 'sources': verdict['sources'][:3],
                 'disagree': verdict['disagree'], 'qid': qid, 'qid_state': qid_state, 'problem': problem,
                 'pinned': bool(record.get('kind') == 'Questions/Media' and PINNED.fullmatch(name))}
        if problem is None:
            ext = PurePosixPath(path).suffix
            entry['name'] = canonical_name('shared' if shared else course, verdict['role'], record['sha256'],
                                           qid=qid, part=part, ext=ext, topic=topic, label=label)
            entry['fallback'] = is_fallback(entry['name'])
            entry['folder'] = FOLDER[verdict['role']]
        else:
            unclassified.append({'id': identifier, 'path': path, 'course': course, 'problem': problem})
        decisions[identifier] = entry
    return library, records, decisions, unclassified


def duplicates(records: dict):
    by_hash = collections.defaultdict(list)
    for identifier, record in records.items():
        by_hash[record['sha256']].append(identifier)
    groups = []
    for digest, ids in by_hash.items():
        if len(ids) < 2:
            continue
        rows = [{'id': i, 'path': records[i]['path'], 'course': records[i].get('course'),
                 'kind': records[i].get('kind')} for i in sorted(ids)]
        images = all(is_image(r['path']) for r in rows)
        groups.append({'sha256': digest, 'count': len(ids), 'images': images,
                       'in_scope': any(locate(r['path']) for r in rows), 'records': rows})
    return sorted(groups, key=lambda g: (-g['count'], g['sha256']))


def destination(entry: dict) -> str:
    if entry.get('shared'):
        return f"Library/Shared/Questions/Media/{entry['folder']}/{entry['name']}"
    return f"Library/Courses/{entry['course']}/Questions/Media/{entry['folder']}/{entry['name']}"


QUESTION_KEY = re.compile(r'(?P<question>.+?)(?:_(?P<page>p\d{2}))?_(?P<role>mcq|long|key|ref|ctx)_[0-9a-f]{12}')


def duplicate_questions(decisions: dict) -> list[dict]:
    """Past-paper questions stored more than once, from canonical names: the same question and role with more
    images than its pages explain (a topical-bank crop beside a source-practice crop, or a question cropped
    twice). The pages of one multi-page question (_p01, _p02) are not duplicates of each other."""
    groups = collections.defaultdict(list)
    for entry in decisions.values():
        name = entry.get('name')
        if entry['problem'] or not name or entry.get('fallback') or entry.get('shared') or not entry.get('qid'):
            continue
        if m := QUESTION_KEY.fullmatch(PurePosixPath(name).stem.split('--')[0]):
            groups[(entry['course'], m['question'], m['role'])].append(
                {'id': entry['id'], 'name': name, 'page': m['page'], 'from': entry['path'], 'sha256': entry['sha256']})
    out = []
    for (course, question, role), rows in sorted(groups.items()):
        pages = [r['page'] for r in rows]
        if len({r['sha256'] for r in rows}) > 1 and (len(set(pages)) < len({r['sha256'] for r in rows})
                                                     or (None in pages and len(set(pages)) > 1)):
            out.append({'course': course, 'question': question, 'role': role, 'count': len(rows),
                        'images': sorted(rows, key=lambda r: r['name'])})
    return out


PAGE_SUFFIX = re.compile(r'_p\d{2}(?=_(?:mcq|long|key|ref|ctx)_[0-9a-f]{12}\.)')


def paged_name_of(path: str, target: str) -> bool:
    """True when ``path`` is ``target`` plus the page suffix normalize_question_names gives a multi-page question.

    Pages are numbered across a question's images, which this per-image planner does not see, so a
    canonical name that differs from its target only by ``_pNN`` is already correct and is left alone.
    """
    current, wanted = PurePosixPath(path), PurePosixPath(target)
    if current.parent != wanted.parent or canonical_parts(current.name) is None:
        return False
    unpaged = PAGE_SUFFIX.sub('', current.name, count=1)
    return unpaged != current.name and asset_path_key(str(current.with_name(unpaged))) == asset_path_key(target)


def build_plan(vault: Path, decided, *, scope='course', include_pinned=False):
    vault = Path(vault).resolve()
    library, records, decisions, unclassified = decided
    occupied = {asset_path_key(ref): identifier for identifier, record in records.items()
                for ref in [record['path'], *record.get('aliases', [])]}
    sidecars = {record['path']: identifier for identifier, record in records.items() if is_sidecar(record['path'])}
    attested = attestation_pins(library, records) if include_pinned else {}
    moves, errors, held, suffixed, detail = [], [], [], [], {}
    for identifier, entry in sorted(decisions.items()):
        if entry['problem'] or entry['scope'] != scope:
            continue
        if entry['pinned'] and not include_pinned:
            held.append({'id': identifier, 'path': entry['path'], 'reason': 'validator-pinned legacy name'})
            continue
        if entry['pinned'] and asset_path_key(entry['path']) in attested:
            held.append({'id': identifier, 'path': entry['path'],
                         'reason': 'prepared attestation pin (immutable reference string)'})
            continue
        target = destination(entry)
        if asset_path_key(target) == asset_path_key(entry['path']) or paged_name_of(entry['path'], target):
            continue
        pair = [(identifier, entry['path'], target, entry['sha256'])]
        side = sidecars.get(entry['path'] + '.json')
        if side:
            pair.append((side, entry['path'] + '.json', target + '.json', records[side]['sha256']))
        taken = [(i, f, t, s) for i, f, t, s in pair]
        key = asset_path_key(target)
        if key in occupied and occupied[key] != identifier:
            stem = PurePosixPath(target)
            target = str(stem.with_name(stem.stem + '--' + identifier + stem.suffix))
            if asset_path_key(target) == asset_path_key(entry['path']):
                continue
            suffixed.append({'id': identifier, 'path': entry['path'], 'to': target})
            taken = [(identifier, entry['path'], target, entry['sha256'])]
            if side:
                taken.append((side, entry['path'] + '.json', target + '.json', records[side]['sha256']))
        if any(asset_path_key(t) in occupied and occupied[asset_path_key(t)] != i for i, _, t, _ in taken):
            errors.append(f'conflicting destination: {target}')
            continue
        for i, source, t, digest in taken:
            occupied[asset_path_key(t)] = i
            try:
                library.read('asset:' + i)
            except (OSError, ValueError) as exc:
                errors.append(f'{i}: {exc}')
            move = {'id': i, 'from': source, 'to': t, 'sha256': digest}
            if i == identifier and entry['scope'] == 'sourcepractice':  # now a course (or shared) question image
                move['catalog'] = {'kind': 'Questions/Media', **({'course': entry['course']} if entry['course'] else {})}
            moves.append(move)
        detail[identifier] = {k: entry[k] for k in ('course', 'role', 'folder', 'tier', 'qid', 'qid_state', 'fallback', 'pinned', 'sources')}
    raw = journalled._read(vault, 'Library/catalog.json')
    report = {'format_version': 1, 'tool': TOOL, 'scope': scope, 'include_pinned': include_pinned,
              'vault': str(vault), 'catalog_sha256': journalled._sha(raw), 'moves': moves, 'errors': errors,
              'held': held, 'suffixed_duplicates': suffixed, 'details': detail}
    return report


def simulate(vault: Path, moves: list, tokens: dict) -> dict:
    """Apply a plan to an in-memory catalog copy and prove every known reference still resolves."""
    raw = journalled._read(vault, 'Library/catalog.json')
    catalog = json.loads(raw)
    before = {t: i for t, i in tokens.items()}
    for move in moves:
        entry = catalog['assets'][move['id']]
        entry['path'] = move['to']
        entry['aliases'] = list(dict.fromkeys([*entry.get('aliases', []), move['from']]))
    validate_catalog(catalog)
    refs = {}
    for identifier, record in catalog['assets'].items():
        refs['asset:' + identifier] = identifier
        for ref in [record['path'], *record.get('aliases', [])]:
            refs[asset_path_key(ref)] = identifier
    broken = []
    for token, identifier in before.items():
        key = token if token.startswith('asset:') else asset_path_key(token)
        if refs.get(key) != identifier:
            broken.append(token)
    for move in moves:
        for ref in (move['from'], 'asset:' + move['id']):
            key = ref if ref.startswith('asset:') else asset_path_key(ref)
            if refs.get(key) != move['id']:
                broken.append(ref)
    return {'tokens_checked': len(before), 'broken': broken[:50], 'broken_count': len(broken)}


def scan_references(vault: Path, library: AssetLibrary, records: dict, evidence_refs: dict, moved: set):
    """Find which pack/bank/topical/release files cite moved assets, by id or by path."""
    kinds = collections.Counter()
    files, tokens = [], {}
    for identifier, record in sorted(records.items()):
        path = record['path']
        if not path.endswith('.json') or path.endswith('.png.json') or not path.startswith('Library/'):
            continue
        try:
            text = library.read('asset:' + identifier).decode('utf-8', 'replace')
        except (OSError, ValueError):
            continue
        counts = collections.Counter(TOKEN.findall(text))
        by_id = by_path = 0
        for token, count in counts.items():
            if token.startswith('asset:'):
                target = token[6:] if token[6:] in records else None
            else:
                try:
                    target = evidence_refs.get(asset_path_key(token))
                except ValueError:
                    target = None
            if target is None:
                continue
            tokens[token] = target
            if target in moved:
                if token.startswith('asset:'):
                    by_id += count
                else:
                    by_path += count
        if by_id or by_path:
            category = ('release' if '/SourcePractice/Releases/' in path else 'pack' if '/Packs/' in path
                        else 'topical' if '/Topicals/' in path else 'bank' if '/SourceVerified/' in path
                        else 'preparation' if '/Preparation/' in path else 'other')
            kinds[category] += 1
            files.append({'file': path, 'category': category, 'refs_by_asset_id': by_id, 'refs_by_path': by_path})
    return {'files_by_category': dict(kinds), 'files': files}, tokens


def summarize(decisions: dict, unclassified: list, groups: list) -> dict:
    table = collections.defaultdict(collections.Counter)
    for entry in decisions.values():
        row = table[entry['course'] or '(unknown)' if entry['scope'] == 'course' else 'SourcePractice/Media']
        row['total'] += 1
        row[entry['folder'] if not entry['problem'] else 'UNCLASSIFIED'] += 1
        row['from ' + entry['area']] += 1
        row['fallback-name'] += bool(entry.get('fallback'))
        row['validator-pinned'] += entry['pinned']
        row['already-in-target'] += bool(not entry['problem'] and PurePosixPath(entry['path']).parent.name == entry['folder']
                                         and PurePosixPath(entry['path']).name == entry['name'])
    sizes = [g for g in groups if g['images']]
    return {'counts': {k: dict(v) for k, v in sorted(table.items())},
            'unclassified': len(unclassified),
            'duplicate_groups': {'all': len(groups), 'images': len(sizes), 'in_scope_images': sum(g['in_scope'] for g in sizes),
                                 'largest': [{'count': g['count'], 'sha256': g['sha256'][:12],
                                              'paths': [r['path'] for r in g['records'][:3]]} for g in sizes[:8]]}}


def audit(vault: Path, *, references=True) -> dict:
    vault = Path(vault).resolve()
    decided = decide(vault)
    library, records, decisions, unclassified = decided
    report = build_plan(vault, decided, scope='course')
    source_report = build_plan(vault, decided, scope='sourcepractice')
    groups = duplicates(records)
    moved = {m['id'] for m in report['moves']} | {m['id'] for m in source_report['moves']}
    result = {'tool': TOOL, 'vault': str(vault), 'summary': summarize(decisions, unclassified, groups),
              'plan_sizes': {'course': len(report['moves']), 'sourcepractice': len(source_report['moves']),
                             'held_validator_pinned': len(report['held']), 'suffixed_duplicates': len(report['suffixed_duplicates']),
                             'errors': len(report['errors']) + len(source_report['errors'])},
              'qid_states': dict(collections.Counter(d['qid_state'] for d in decisions.values() if not d['problem'])),
              'path_table': dict(collections.Counter(
                  f"{d['area']} -> {d['folder']}" for d in decisions.values() if not d['problem'])),
              'tiers': dict(collections.Counter(str(d['tier']) for d in decisions.values() if not d['problem'])),
              'weak_disagreements': [{'id': d['id'], 'path': d['path'], 'role': d['role'], 'weaker_evidence': d['disagree']}
                                     for d in decisions.values() if d['disagree']],
              'fallback_names': [{'id': d['id'], 'path': d['path'], 'name': d['name']}
                                 for d in decisions.values() if d.get('fallback') and d['scope'] == 'course'],
              'unclassified': unclassified, 'duplicate_groups': groups,
              'duplicate_questions': duplicate_questions(decisions)}
    if references:
        refs = {asset_path_key(ref): identifier for identifier, record in records.items()
                for ref in [record['path'], *record.get('aliases', [])]}
        scan, tokens = scan_references(vault, library, records, refs, moved)
        result['reference_scan'] = scan
        result['reference_check'] = simulate(vault, report['moves'] + source_report['moves'], tokens)
    return result


def write(path: Path, data) -> None:
    journalled._json(Path(path), data)


def cmd_audit(args):
    result = audit(args.vault, references=not args.skip_references)
    write(args.out / 'audit.json', result)
    print(json.dumps({'summary': result['summary']['duplicate_groups'] | {'unclassified': result['summary']['unclassified']},
                      'plan_sizes': result['plan_sizes'], 'reference_check': result.get('reference_check', {}).get('broken_count'),
                      'out': str(args.out / 'audit.json')}))


def cmd_plan(args):
    outputs, tokens = {}, None
    decided = decide(args.vault)
    library, records = decided[0], decided[1]
    if not args.skip_references:
        refs = {asset_path_key(ref): i for i, r in records.items() for ref in [r['path'], *r.get('aliases', [])]}
        _, tokens = scan_references(Path(args.vault).resolve(), library, records, refs, set())
    for name, scope, pinned in (('plan.json', 'course', False), ('plan-with-pinned.json', 'course', True),
                                ('plan-source-practice.json', 'sourcepractice', False)):
        report = build_plan(args.vault, decided, scope=scope, include_pinned=pinned)
        if tokens is not None:
            report['reference_check'] = simulate(Path(report['vault']), report['moves'], tokens)
        write(args.out / name, report)
        outputs[name] = {'moves': len(report['moves']), 'errors': len(report['errors']), 'held': len(report['held']),
                         'reference_check': report.get('reference_check', {}).get('broken_count')}
    repeated = duplicate_questions(decided[2])
    write(args.out / 'duplicate-questions.json', {'tool': TOOL, 'questions': repeated})
    outputs['duplicate-questions.json'] = {'questions': len(repeated)}
    print(json.dumps(outputs))


def cmd_apply(args):
    if not args.yes:
        raise SystemExit('apply changes the vault catalog: pass --yes after reading the plan and verifying a backup')
    report = json.loads(args.plan.read_text())
    if report.get('tool') not in (TOOL, 'normalize_question_names') or report.get('errors'):
        raise SystemExit('not a clean organize_question_library plan')
    if report.get('reference_check', {}).get('broken_count', 1) != 0:
        raise SystemExit('plan was not reference-verified; rerun plan without --skip-references')
    print(json.dumps(journalled.apply(report, args.journal)))


def cmd_rollback(args):
    print(json.dumps(journalled.rollback(args.journal)))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ('audit', 'plan'):
        p = sub.add_parser(name)
        p.add_argument('--vault', type=Path, default=ROOT.parent / 'STEM Tutor')
        p.add_argument('--out', type=Path, default=WORK)
        p.add_argument('--skip-references', action='store_true')
        p.set_defaults(func=cmd_audit if name == 'audit' else cmd_plan)
    p = sub.add_parser('apply')
    p.add_argument('--plan', type=Path, required=True)
    p.add_argument('--journal', type=Path, required=True)
    p.add_argument('--yes', action='store_true')
    p.set_defaults(func=cmd_apply)
    p = sub.add_parser('rollback')
    p.add_argument('--journal', type=Path, required=True)
    p.set_defaults(func=cmd_rollback)
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == '__main__':
    main()
