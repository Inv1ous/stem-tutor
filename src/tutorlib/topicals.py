"""Reviewed, local source questions and deterministic prerequisite policy.

The bank is independent of published teaching packs. A damaged bank supplies no
items; legacy teaching content remains usable. Open attempts hold their own copy.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import re
import threading
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path

from .library_refs import LibraryRefs
from .asset_library import AssetLibrary, verification_scope
from .prepared_evidence import (bank_identity, pearson_namespace, validate_prepared_group,
                                authenticate_prepared_item)
from .ial_identity import ial_identity, ial_namespace, ial_assessed, ial_question, validate_ial_sources

_QID = re.compile(r'(970[12])_([msw]\d{2})_(?:qp_)?(\d{2})_q(\d+)(.*)', re.I)
_REF = re.compile(r'(970[12]).*?(Mar|Feb|Jun|May|Oct|Nov)\w*\s+(20\d{2}).*?P(\d{2}).*?Q(\d+)(.*)', re.I)


def official_course(source: dict) -> str | None:
    """Read source ownership without authenticating content or review."""
    qid = source.get('qid')
    if ial_assessed(qid, source.get('part')) is None and bank_identity(source) is not None:
        return bank_identity(source)[0]
    if pearson_namespace(qid):
        assessed = ial_assessed(qid, source.get('part'))
        return assessed['course'] if assessed else None
    match = _QID.fullmatch(str(qid).lower())
    return match[1] if match else None


def identity(item: dict) -> str | None:
    """Canonical paper question plus independently assessed part (if present)."""
    source = item.get('source') or {}
    if pearson_namespace(source.get('qid')):
        old = ial_identity(source.get('qid'), source.get('part'))
        projected = bank_identity(source)
        return old or (projected[1] if projected else None)
    match = _QID.fullmatch(str(source.get('qid', '')).lower())
    if match:
        code, series, paper, number, suffix = match.groups()
    else:
        match = _REF.search(str(source.get('ref', '')))
        if not match:
            return None
        code, month, year, paper, number, suffix = match.groups()
        series = {'mar': 'm', 'feb': 'm', 'jun': 's', 'may': 's', 'oct': 'w', 'nov': 'w'}[month.lower()] + year[-2:]
    part = re.sub(r'[^a-z0-9]', '', str(source.get('part') or suffix).lower())
    return f'{code}_{series.lower()}_{paper}_q{int(number)}' + (f':{part}' if part else '')


def started_chapters(state: dict, packs) -> set[str]:
    """Actual chapter starts and conservative legacy answer evidence only."""
    result = set(state.get('started_chapters', []))
    result.update(state.get('completed_chapters', []))
    result.update(packs.kcs[k]['subtopic'] for k, v in state.get('kcs', {}).items()
                  if v.get('n', 0) > 0 and k in packs.kcs)
    return result


def _external_requirement_versions(item: dict, packs) -> dict:
    """External requirements need an assessed-KC declaration and exact version pins."""
    meta = item['topical']
    assessed = [packs.kcs[value] for value in item['kcs']]
    specs = {node['spec'] for node in assessed}
    if len(specs) != 1:
        raise ValueError('assessed KC course mismatch')
    spec = next(iter(specs))
    if any(packs.subtopics[value]['spec'] != spec for value in meta['chapters']):
        raise ValueError('serving chapters must remain in the assessed course')
    declarations = {value for node in assessed for value in node.get('prereqs', []) if isinstance(value, str)}
    expected = {}
    for chapter in meta['requires']:
        target = packs.subtopics[chapter]['spec']
        if target == spec:
            continue
        authorized = False
        for dependency in declarations:
            if dependency.split('-', 1)[0] != target:
                continue
            node = packs.kcs.get(dependency)
            if ((node and node.get('spec') == target and node.get('subtopic') == chapter)
                    or dependency == chapter and dependency in packs.subtopics):
                authorized = True
                break
        version = packs.syllabus_versions.get(target)
        if not authorized or not isinstance(version, str) or not version:
            raise ValueError('external requirement lacks an available declared target')
        expected[target] = version
    if meta.get('prerequisite_versions', {}) != expected:
        raise ValueError('external prerequisite version binding mismatch')
    return expected


def eligibility(item: dict, chapter: str | None, state: dict, packs, unassisted: bool = False) -> dict:
    """Private policy output; the public check exposes only topic numbers."""
    meta = item.get('topical')
    if not isinstance(meta, dict) or meta.get('reviewed') is not True:
        return {'status': 'unverified', 'missing': [], 'requires': [], 'support': {}}
    required = meta.get('requires')
    chapters = meta.get('chapters')
    if (not isinstance(required, list) or not required or not all(isinstance(k, str) and k in packs.subtopics for k in required)
            or not isinstance(chapters, list) or not chapters
            or not all(isinstance(k, str) and k in packs.subtopics for k in chapters)
            or chapter not in chapters):
        return {'status': 'unverified', 'missing': [], 'requires': [], 'support': {}}
    try:
        _external_requirement_versions(item, packs)
        if meta.get('revision') != packs.syllabus_versions.get(packs.subtopics[chapters[0]]['spec']):
            raise ValueError('assessed course revision mismatch')
    except (KeyError, ValueError, TypeError, AttributeError):
        return {'status': 'unverified', 'missing': [], 'requires': [], 'support': {}}
    missing = sorted(set(required) - started_chapters(state, packs) - {chapter})
    facts = meta.get('support') or {}
    if not isinstance(facts, dict):
        return {'status': 'unverified', 'missing': [], 'requires': [], 'support': {}}
    support = {k: facts[k] for k in missing if k != chapter and isinstance(facts.get(k), str) and facts[k].strip()}
    status = 'solvable' if not missing else ('supported' if not unassisted and len(support) == len(missing) else 'unavailable')
    return {'status': status, 'requires': sorted(set(required)), 'missing': missing,
            'support': support if status == 'supported' else {}}


def graph_eligibility(item: dict, chapter: str | None, state: dict, packs) -> dict:
    """Conservative graph assessment, distinct from reviewed question metadata.

    A graph can establish recorded prerequisites, not the completeness of a
    question's source mapping. Incomplete, cyclic or cross-course data fails
    closed. This read-only action never supplies support facts or an answer.
    """
    unknown = {'status': 'unverified', 'requires': [], 'missing': [], 'support': {}, 'basis': 'course_graph'}
    assessed = item.get('kcs')
    course = packs.subtopics.get(chapter, {}).get('spec') if isinstance(chapter, str) else None
    if ('topical' in item or item.get('kind') not in {'mcq', 'numeric', 'expression', 'short', 'structured'}
            or not course or not packs.syllabus_versions.get(course)
            or not isinstance(assessed, list) or not assessed
            or any(not isinstance(k, str) for k in assessed)):
        return unknown
    visited, active, required = set(), set(), set()

    def visit(key):
        if key in active:
            raise ValueError('cyclic graph')
        if key in visited:
            return
        node = packs.kcs.get(key)
        if not isinstance(node, dict):
            raise ValueError('unknown KC')
        sub = node.get('subtopic')
        prereqs = node.get('prereqs')
        if (node.get('spec') != course or packs.subtopics.get(sub, {}).get('spec') != course
                or not isinstance(prereqs, list) or any(not isinstance(k, str) for k in prereqs)):
            raise ValueError('incomplete or conflicting graph')
        active.add(key)
        required.add(sub)
        for prerequisite in prereqs:
            visit(prerequisite)
        active.remove(key)
        visited.add(key)

    try:
        for key in assessed:
            visit(key)
    except (ValueError, TypeError, RecursionError):
        return unknown
    missing = sorted(required - started_chapters(state, packs) - {chapter})
    return {'status': 'unavailable' if missing else 'solvable', 'requires': sorted(required),
            'missing': missing, 'support': {}, 'basis': 'course_graph'}


def _runtime_items(items: list[dict], root: Path) -> list[dict]:
    """Adapt old library-relative provenance through declared catalog aliases.

    source.library.file and source.mark_scheme.file have this historical format.
    Image paths and other asset fields retain the strict resolver. Verify each distinct source
    document once for this bank load, rather than hashing a shared PDF per item.
    """
    refs = LibraryRefs(root)

    def resolve_source(value: str) -> str:
        # Explicit provenance files require exact verification, even when a
        # spaced path would be preserved as prose by the general resolver.
        if refs.library is None:
            return value
        return refs.library.resolve(value).relative_to(refs.root).as_posix()

    sources = {}
    result = []
    for original in items:
        copied = copy.deepcopy(original)
        source = copied.get('source')
        documents = {key: source.pop(key) for key in ('library', 'mark_scheme') if key in source} if isinstance(source, dict) else {}
        mapped = refs.content(copied)
        for name, provenance in documents.items():
            if isinstance(provenance, dict) and isinstance(provenance.get('file'), str):
                reference = provenance['file']
                if reference not in sources:
                    try:
                        sources[reference] = resolve_source(reference)
                    except ValueError as exc:
                        path = Path(reference)
                        safe_bare = (reference and not path.is_absolute() and '\\' not in reference
                                     and not any(part in ('', '.', '..') for part in reference.split('/'))
                                     and path.parts[0] not in {'Assets', 'Library', 'sources', 'Sources', 'Papers'})
                        if not str(exc).startswith('unknown asset reference:') or not safe_bare:
                            raise
                        # This is a catalog alias lookup, never a filesystem search.
                        sources[reference] = resolve_source('sources/library/' + reference)
                provenance['file'] = sources[reference]
            mapped['source'][name] = provenance
        result.append(mapped)
    return result


class Bank:
    def __init__(self, vault_root: Path, packs):
        self.root = vault_root
        self.base = vault_root / '.tutor/topicals'
        self.packs = packs
        self.pointer = None
        self.items: list[dict] = []
        self.errors: list[str] = []
        self._request = ContextVar('topical_bank_request', default=None)
        self._lock = threading.RLock()
        self._loaded: dict | None = None

    @contextmanager
    def request(self):
        """One fresh authentication for a synchronous selector and its nested lookups."""
        if self._request.get() is not None:
            yield False
            return
        token = self._request.set({'initialized': False, 'last': None, 'changed': False})
        try:
            self.refresh()
            yield True
        finally:
            self._request.reset(token)

    def _request_seen(self, version):
        request = self._request.get()
        if request is None:
            return False
        if not request['initialized']:
            request.update(initialized=True, initial=version, last=version)
            return False
        request['changed'] |= version != request['initial']
        cached = version == request['last']
        request['last'] = version
        return cached

    def request_current(self):
        self.refresh()  # cheap pointer check inside the scope; new versions are authenticated.
        return not self._request.get()['changed']

    def refresh(self) -> None:
        try:
            version = (self.base / 'CURRENT').read_text().strip()
        except FileNotFoundError:
            self._request_seen(('missing',))
            self.items, self.errors, self.pointer = [], [], None
            return
        except (OSError, UnicodeError) as exc:
            self._request_seen(('error', type(exc).__name__, str(exc)))
            self.items, self.errors = [], [f'Topical bank unavailable: {exc}']
            self.pointer = None
            return
        if self._request_seen(('version', version)):
            return
        with self._lock:
            if version == self.pointer:
                prepared = [i for i, row in enumerate(self.items) if 'prepared_admission' in row.get('source', {})]
                if not prepared or self._reauthenticate_prepared(version, prepared):
                    return
            self._load(version)

    def _load(self, version: str) -> None:
        """Read, validate and adapt the whole release. The result replaces the old one in one step, so a reader on
        another thread never sees a half-built bank."""
        items: list[dict] = []
        errors: list[str] = []
        pointer = version
        loaded = None
        try:
            with verification_scope():
                if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', version) or version in ('.', '..'):
                    raise ValueError('invalid CURRENT pointer')
                canonical = f'Library/Shared/Topicals/Releases/{version}/bank.json'
                target = self.root / canonical
                if target.exists() or target.is_symlink():
                    raw = AssetLibrary(self.root).read(canonical)
                else:
                    raw = None
                    bank = json.loads((self.base / version / 'bank.json').read_text())
                if raw is not None:
                    bank = json.loads(raw)
                validate_bank(bank, self.packs, self.root)
                items = _runtime_items(bank['items'], self.root)
                if raw is not None:
                    loaded = {'version': version, 'raw': raw, 'canonical': canonical,
                              'header': {k: v for k, v in bank.items() if k != 'items'},
                              'rows': bank['items']}
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
            pointer = None  # only a fully verified load may cache a release
            items = []
            errors = [f'Topical bank unavailable: {exc}']
            loaded = None
        self._loaded = loaded
        self.pointer, self.items, self.errors = pointer, items, errors

    def _reauthenticate_prepared(self, version: str, prepared: list[int]) -> bool:
        """A release with prepared-admission questions is authenticated again at every request. Only those questions
        carry that proof; the rest of the (unchanged) bank was verified when it loaded. Re-read the release file
        through the catalog: if its bytes are still the ones loaded, authenticate just the prepared rows. Anything
        else (new bytes, a changed layout, a failed check) takes the full reload, which reports it as before.
        True when the request is settled here."""
        loaded = self._loaded
        if (not loaded or loaded['version'] != version or len(loaded['rows']) != len(self.items)
                or any('prepared_admission' not in (loaded['rows'][i].get('source') or {}) for i in prepared)):
            return False
        try:
            raw = AssetLibrary(self.root).read(loaded['canonical'])
        except (OSError, ValueError):
            return False
        if raw != loaded['raw']:
            return False
        subset = {**loaded['header'], 'items': copy.deepcopy([loaded['rows'][i] for i in prepared])}
        try:
            with verification_scope():
                validate_bank(subset, self.packs, self.root)
                fresh = _runtime_items(subset['items'], self.root)
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
            self._loaded = None
            self.pointer, self.items, self.errors = None, [], [f'Topical bank unavailable: {exc}']
            return True
        items = list(self.items)
        for index, row in zip(prepared, fresh):
            items[index] = row
        self.errors = []
        self.items = items
        return True

    def _validate(self, item: dict, revisions: dict, *, prepared_verified=False) -> None:
        if not isinstance(item, dict) or not isinstance(item.get('id'), str) or not item['id'] or not identity(item):
            raise ValueError('missing item identity')
        if not item.get('source', {}).get('qid') or item['source'].get('type') != 'past':
            raise ValueError('missing canonical source')
        meta = item.get('topical')
        if not isinstance(meta, dict) or meta.get('reviewed') is not True:
            raise ValueError('unreviewed prerequisites')
        for name in ('requires', 'chapters'):
            keys = meta.get(name)
            if not isinstance(keys, list) or not keys or not all(isinstance(k, str) and k in self.packs.subtopics for k in keys):
                raise ValueError(f'invalid {name}')
        kcs = item.get('kcs')
        if (not isinstance(kcs, list) or not kcs
                or any(not isinstance(k, str) or k not in self.packs.kcs for k in kcs)):
            raise ValueError('invalid assessed KCs')
        if len(kcs) != len(set(kcs)):
            raise ValueError('duplicate assessed KC')
        spec = self.packs.kcs[kcs[0]]['spec']
        if (official_course(item['source']) != spec
                or any(self.packs.kcs[k]['spec'] != spec for k in kcs)):
            raise ValueError('item source or assessed KC course mismatch')
        if 'prepared_admission' in item['source']:
            if not prepared_verified:
                authenticate_prepared_item(item, AssetLibrary(self.root), self.packs)
            if (item.get('kind') != 'structured'
                    or any(self.packs.kcs[k].get('subtopic') not in meta['chapters'] for k in kcs)):
                raise ValueError('invalid prepared assessed KC parent')
        elif spec in ('P1', 'P2'):
            if (item.get('kind') != 'structured'
                    or any(self.packs.kcs[k].get('level') != spec
                           or self.packs.kcs[k].get('subtopic') not in meta['chapters'] for k in kcs)):
                raise ValueError(f'invalid {spec} assessed KC level or parent')
            source = item['source']
            validate_ial_sources(source.get('qid'), source.get('part'), spec,
                                source.get('extraction_regions'), source.get('mark_scheme_regions'),
                                AssetLibrary(self.root))
        elif any(self.packs.kcs[k].get('level') != 'AS' for k in kcs):
            raise ValueError('invalid AS assessed KCs')
        if (meta.get('revision') != revisions.get(spec) or any(self.packs.subtopics[k]['spec'] != spec
                for k in meta['chapters'])):
            raise ValueError('item revision or subject mismatch')
        external_versions = _external_requirement_versions(item, self.packs)
        if any(revisions.get(course) != version for course, version in external_versions.items()):
            raise ValueError('external prerequisite bank revision binding mismatch')
        support = meta.get('support')
        if not isinstance(support, dict) or any(k not in meta['requires'] or not isinstance(v, str) or not v.strip() for k, v in support.items()):
            raise ValueError('invalid reviewed support')
        if type(item.get('difficulty', 3)) is not int or not 1 <= item.get('difficulty', 3) <= 5:
            raise ValueError('difficulty must be an integer from 1 to 5')
        if type(item.get('marks', 1)) is not int or item.get('marks', 1) <= 0:
            raise ValueError('marks must be a positive integer')
        if not isinstance(item.get('stem'), str) or not item['stem'].strip():
            raise ValueError('missing stem')
        if item.get('kind') == 'mcq':
            options = item.get('options')
            if not isinstance(options, dict) or item.get('answer') not in ('A', 'B', 'C', 'D'):
                raise ValueError('unverified MCQ key')
            if options and (set(options) != set('ABCD') or any(not isinstance(v, str) or not v.strip() for v in options.values())):
                raise ValueError('invalid MCQ options')
        elif item.get('kind') == 'structured':
            validate_structured_scheme(item)
        else:
            _validate_answer(item)
        images = item.get('images', [])
        if not isinstance(images, list) or any(not isinstance(p, str) for p in images):
            raise ValueError('invalid image list')
        if item.get('image'):
            images = [item['image'], *images]
        if item.get('kind') == 'mcq' and not item.get('options') and not images:
            raise ValueError('missing question options')
        for rel in images:
            path = Path(rel)
            refs = LibraryRefs(self.root)
            if refs.library is not None:
                canonical = refs.reference(rel)
                if not canonical.startswith(f'Library/Courses/{spec}/Questions/Media/'):
                    raise ValueError('unsafe topical source image outside course question media')
                continue
            if (not rel.startswith('Assets/topicals/') or path.is_absolute() or '..' in path.parts
                    or not (self.root / path).is_file() or not (self.root / path).resolve().is_relative_to(self.root.resolve())
                    or any((self.root / Path(*path.parts[:index])).is_symlink() for index in range(1, len(path.parts) + 1))):
                raise ValueError('missing or unsafe source image')
        if whole_rubric(item) is not None and not (prepared_verified and 'prepared_admission' in item['source']):
            whole_rubric_media(item, self.root)

    def overlay(self, originals: list[dict]) -> list[dict]:
        self.refresh()
        indexed = {identity(i): i for i in self.items}
        result, seen = [], set()
        for original in originals:
            key = identity(original)
            imported = indexed.get(key) if key else None
            if imported:
                seen.add(key)
                merged = copy.deepcopy(original)
                merged['topical'] = copy.deepcopy(imported['topical'])
                # Keep assessed KCs, keys, content and IDs of the original attempt.
                merged['_canonical_identity'] = key
                result.append(merged)
            else:
                result.append(original)
        original_ids = {i['id'] for i in originals}
        for imported in self.items:
            key = identity(imported)
            if key not in seen and imported['id'] not in original_ids:
                result.append(imported)
                seen.add(key)
        return result


def validate_bank(bank: dict, packs, asset_root: Path) -> None:
    """Validate a complete candidate before publishing; never reads or changes CURRENT."""
    if not isinstance(bank, dict) or bank.get('format_version') != 1:
        raise ValueError('unsupported bank format')
    revisions = bank.get('syllabus_versions')
    if not isinstance(revisions, dict) or not revisions or any(
            packs.syllabus_versions.get(k) != v for k, v in revisions.items()):
        raise ValueError('syllabus revision mismatch')
    items = bank.get('items')
    if not isinstance(items, list):
        raise ValueError('items must be a list')
    try:
        if any(isinstance(i, dict) and isinstance(i.get('source'), dict) and 'prepared_admission' in i['source'] for i in items):
            validate_prepared_group(items, AssetLibrary(Path(asset_root)), packs)
    except (KeyError, TypeError, AttributeError) as exc:
        raise ValueError(f'invalid prepared group schema: {exc}') from None
    checker = Bank(Path(asset_root), packs)
    identities, ids = set(), set()
    for item in items:
        try:
            checker._validate(item, revisions, prepared_verified=True)
        except (KeyError, TypeError, AttributeError) as exc:
            raise ValueError(f'invalid item schema: {exc}') from None
        key = identity(item)
        if key in identities or item['id'] in ids:
            raise ValueError('duplicate canonical question or item ID')
        identities.add(key)
        ids.add(item['id'])
    try:
        _validate_p2_question_media_scope(items, Path(asset_root))
    except (KeyError, TypeError, AttributeError) as exc:
        raise ValueError(f'invalid P2 media scope schema: {exc}') from None


def _reviewed_sidecars(library, reference: str, record: dict, course: str) -> list:
    """The reviewed provenance sidecars bound to this image as `reference` names it.

    A catalog move keeps the reviewed name as an alias, and a duplicate merge folds several reviewed
    copies into one asset that keeps only the survivor's sidecar; each folded name still has its own
    reviewed sidecar at `<name>.json`. The callers re-check that sidecar against these bytes and the
    question, so following the alias never widens what is accepted.
    """
    sidecars = record.get('provenance', {}).get('sidecars', [])
    if reference != record['path']:
        try:
            own = library.record(reference + '.json')
        except ValueError:
            own = None
        if own and own.get('kind') == 'Sources/Provenance' and own.get('course') == course:
            return [reference + '.json']
    return sidecars


def _validate_p2_question_media_scope(items: list[dict], root: Path) -> None:
    """Bind the complete exact P2 group to immutable roles before disclosure."""
    p2_items = [item for item in items if item['source'].get('qid') == 'P2_pearson-edexcel-ial_WMA12_2019-06_01_q1']
    if not p2_items:
        return
    library = AssetLibrary(root)
    private_paths, private_hashes, public = set(), set(), []
    groups = {}

    def provenance(reference):
        record = library.record(reference)
        sidecars = _reviewed_sidecars(library, reference, record, 'P2')
        if (reference not in (record['path'], *record.get('aliases', [])) or record.get('course') != 'P2'
                or record.get('kind') != 'Questions/Media' or len(sidecars) != 1):
            raise ValueError('P2 media requires immutable reviewed provenance')
        content = library.read(reference)
        value = json.loads(library.read(sidecars[0]))
        digest = hashlib.sha256(content).hexdigest()
        if value.get('sha256') != digest or value.get('course') != 'P2':
            raise ValueError('P2 media provenance digest or course mismatch')
        return value, digest

    def registered_path(name, context, digest):
        path = Path(name)
        stem = re.sub(r'[^A-Za-z0-9_-]', '-', path.stem)[:70]
        return f'Library/Courses/P2/Questions/Media/{stem}-{context}-{digest[:16]}{path.suffix.lower()}'

    for item in p2_items:
        source = item['source']
        names = list(item.get('images', [])) + ([item['image']] if item.get('image') else [])
        if not names:
            raise ValueError('P2 question requires reviewed public media provenance')
        original_record, original_review, group = None, None, None
        for reference in names:
            value, digest = provenance(reference)
            original, review = value.get('record', {}), value.get('review', {})
            context = hashlib.sha256(json.dumps(original, sort_keys=True).encode()).hexdigest()[:12]
            question = ial_question(source['qid'])
            if (original.get('official_qid') != source['qid'] or original.get('part') != source['part']
                    or original.get('id') != 'native-' + source['qid'] + '-' + question['part_suffixes'][source['part']]
                    or item['id'] != 'extracted-' + source['qid'] + '-' + context
                    or original.get('regions') != source.get('extraction_regions')
                    or original.get('mark_scheme_regions') != source.get('mark_scheme_regions')
                    or review.get('verdict') != 'pass' or review.get('findings') != []
                    or not re.fullmatch(r'[0-9a-f]{64}', str(review.get('candidate_sha256', '')))
                    or digest not in review.get('inspected_images', [])
                    or value.get('extraction_job') != source.get('extraction_job')
                    or review.get('candidate_sha256') != source.get('candidate_sha256')):
                raise ValueError('P2 public media differs from reviewed record or source binding')
            public_names = original.get('question_media', []) + original.get('reference_media', [])
            if reference not in {registered_path(name, context, digest) for name in public_names}:
                raise ValueError('P2 public media is not a reviewed public question/reference image')
            private = value.get('private_media')
            if (not isinstance(private, dict) or not isinstance(original.get('mark_scheme_media'), list)
                    or set(private) != set(original['mark_scheme_media'])):
                raise ValueError('P2 private media inventory differs from reviewed record')
            if original_record is not None and (original != original_record or review != original_review):
                raise ValueError('P2 public images mix reviewed records')
            original_record, original_review = original, review
            group = (source['qid'], value['extraction_job'], json.dumps(review, sort_keys=True))
            for local_name, private_reference in private.items():
                private_value, private_digest = provenance(private_reference)
                if (private_reference != registered_path(local_name, context, private_digest)
                        or private_value.get('record') != original or private_value.get('review') != review
                        or private_value.get('extraction_job') != value['extraction_job']
                        or private_digest not in review.get('inspected_images', [])):
                    raise ValueError('P2 private media differs from reviewed record or source binding')
                private_paths.add(private_reference)
                private_hashes.add(private_digest)
            public.append((reference, digest))
        parts = groups.setdefault(group, set())
        if source['part'] in parts:
            raise ValueError('duplicate P2 reviewed scope part')
        parts.add(source['part'])
    for (qid, _, _), parts in groups.items():
        if parts != set(ial_question(qid)['assessed_parts']):
            raise ValueError('P2 bank requires a complete immutable reviewed three-part scope')
    if any(reference in private_paths or digest in private_hashes for reference, digest in public):
        raise ValueError('P2 question scope public media contains private mark-scheme imagery')


def whole_rubric(item: dict) -> dict | None:
    """Recognize the reserved discriminator; malformed payloads never fall back."""
    scheme = item.get('scheme')
    if not isinstance(scheme, list) or not any(isinstance(p, dict) and 'whole_rubric' in p for p in scheme):
        return None
    if (item.get('kind') != 'structured' or type(item.get('marks')) is not int or item['marks'] <= 0
            or len(scheme) != 1 or not isinstance(scheme[0], dict)
            or set(scheme[0]) != {'point', 'whole_rubric'}
            or not isinstance(scheme[0]['point'], str) or not scheme[0]['point'].strip()):
        raise ValueError('invalid whole-rubric marking scheme')
    entry = scheme[0]
    payload = entry['whole_rubric']
    if (not isinstance(payload, dict) or set(payload) != {'version', 'max_marks', 'media'}
            or type(payload['version']) is not int or payload['version'] != 1
            or type(payload['max_marks']) is not int or payload['max_marks'] != item['marks']
            or not isinstance(payload['media'], list) or len(payload['media']) > 32
            or any(not isinstance(m, str) or not m.strip() for m in payload['media'])
            or len(set(payload['media'])) != len(payload['media'])):
        raise ValueError('invalid or unsupported whole-rubric payload')
    return entry


def whole_rubric_media(item: dict, root: Path) -> list[dict]:
    """Verify exact private immutable rasters and reviewed source provenance afresh."""
    import hashlib
    entry = whole_rubric(item)
    if entry is None:
        raise ValueError('not a whole-rubric item')
    names = entry['whole_rubric']['media']
    source = item.get('source') or {}
    if item.get('source_verified') is True and source.get('type') == 'source_verified':
        # registered, digest-checked Library resources of a migrated source-verified bank (read raises on any mismatch)
        library = AssetLibrary(root)
        return [{'reference': name, 'sha256': hashlib.sha256(library.read(name)).hexdigest()} for name in names]
    if 'prepared_admission' in source:
        library = AssetLibrary(root)
        runtime_keys = {'_serving_chapter', '_serving_kc', '_selection_kinds'}
        authenticate_prepared_item({k: v for k, v in item.items() if k not in runtime_keys}, library)
        return [{'reference': name, 'sha256': hashlib.sha256(library.read(name)).hexdigest()} for name in names]
    if not names and not pearson_namespace(source.get('qid')):
        return []
    library = AssetLibrary(root)
    course = official_course(source)
    if course is None:
        raise ValueError('whole-rubric media needs an official source identity')
    if course in ('P1', 'P2'):
        validate_ial_sources(source.get('qid'), source.get('part'), course,
                            source.get('extraction_regions'), source.get('mark_scheme_regions'), library)
    if not names:
        return []
    public = [*item.get('images', []), *([item['image']] if item.get('image') else [])]
    public_hashes = {hashlib.sha256(library.read(ref)).hexdigest() for ref in public}
    result = []
    for reference in names:
        record = library.record(reference)
        path = record['path']
        if ((reference != path and reference not in record.get('aliases', []))
                or not path.startswith(f'Library/Courses/{course}/Questions/Media/')
                or record.get('course') != course or record.get('kind') != 'Questions/Media'):
            raise ValueError('whole-rubric media requires an immutable course question resource')
        data = library.read(reference)
        digest = hashlib.sha256(data).hexdigest()
        if reference in public or digest in public_hashes:
            raise ValueError('private whole-rubric media overlaps public images')
        sidecars = _reviewed_sidecars(library, reference, record, course)
        if len(sidecars) != 1:
            raise ValueError('whole-rubric media lacks reviewed provenance')
        provenance = json.loads(library.read(sidecars[0]))
        original = provenance.get('record', {})
        reviewed = whole_rubric(original)
        review = provenance.get('review', {})
        if (reviewed is None or provenance.get('course') != course or provenance.get('sha256') != digest
                or review.get('verdict') != 'pass' or digest not in review.get('inspected_images', [])
                or original.get('official_qid') != source.get('qid') or original.get('part') != source.get('part')
                or original.get('regions') != source.get('extraction_regions')
                or original.get('mark_scheme_regions') != source.get('mark_scheme_regions')
                or provenance.get('regions') != original.get('mark_scheme_regions')
                or reviewed['point'] != entry['point']
                or reviewed['whole_rubric']['max_marks'] != entry['whole_rubric']['max_marks']
                or len(reviewed['whole_rubric']['media']) != len(names)):
            raise ValueError('whole-rubric media differs from reviewed source or rubric')
        context = hashlib.sha256(json.dumps(original, sort_keys=True).encode()).hexdigest()[:12]
        original_name = reviewed['whole_rubric']['media'][len(result)]
        namepart = re.sub(r'[^A-Za-z0-9_-]', '-', Path(original_name).stem)[:70]
        expected = f'Library/Courses/{course}/Questions/Media/{namepart}-{context}-{digest[:16]}{Path(original_name).suffix.lower()}'
        # The pin binds the reviewed bytes to this asset; a catalog move keeps the reviewed
        # name as a declared alias, so the alias proves the same binding at a new path.
        if (original_name not in original.get('mark_scheme_media', [])
                or (path != expected and expected not in record.get('aliases', []))):
            raise ValueError('whole-rubric media order or private purpose differs from review')
        result.append({'reference': reference, 'sha256': digest})
    return result


def validate_structured_scheme(item: dict) -> None:
    """The extraction and runtime boundaries share one supported rubric shape."""
    if whole_rubric(item) is not None:
        return
    scheme = item.get('scheme')
    marks = item.get('marks', 1)
    if (type(marks) is not int or marks <= 0
            or not isinstance(scheme, list) or not scheme or len(scheme) != marks
            or any(not isinstance(p, dict) or not isinstance(p.get('point'), str) or not p['point'].strip()
                   or 'mark' in p and (not isinstance(p['mark'], str) or not p['mark'].strip()) for p in scheme)):
        raise ValueError('invalid marking points or total marks')
    for point in scheme:
        if point.get('check'):
            _validate_answer(point['check'])


def _validate_answer(item: dict) -> None:
    kind, answer = item.get('kind'), item.get('answer')
    if kind == 'numeric':
        if (not isinstance(answer, dict) or type(answer.get('value')) not in (int, float)
                or not math.isfinite(answer['value']) or not isinstance(answer.get('unit', ''), str)):
            raise ValueError('invalid numeric answer')
        if 'sf_ok' in answer and (not isinstance(answer['sf_ok'], list) or not answer['sf_ok']
                or any(type(n) is not int or not 1 <= n <= 15 for n in answer['sf_ok'])):
            raise ValueError('invalid accepted significant figures')
        if 'sf' in answer and (type(answer['sf']) is not int or not 1 <= answer['sf'] <= 15):
            raise ValueError('invalid significant figures')
        if 'tol_rel' in answer and (type(answer['tol_rel']) not in (int, float)
                or not math.isfinite(answer['tol_rel']) or answer['tol_rel'] < 0):
            raise ValueError('invalid numeric tolerance')
        if 'exact' in answer and type(answer['exact']) is not bool:
            raise ValueError('exact must be a boolean')
    elif kind == 'expression':
        if not isinstance(answer, dict) or not isinstance(answer.get('expr'), str) or not answer['expr'].strip():
            raise ValueError('invalid expression answer')
    elif kind == 'short':
        rubric = item.get('rubric')
        if not isinstance(rubric, list) or not rubric:
            raise ValueError('missing short-answer rubric')
        for point in rubric:
            groups = point.get('keywords') if isinstance(point, dict) else None
            if (not isinstance(point, dict) or not isinstance(point.get('point'), str) or not point['point'].strip()
                    or not isinstance(groups, list) or not groups
                    or any(not isinstance(g, list) or not g or any(not isinstance(k, str) or not k.strip() for k in g) for g in groups)):
                raise ValueError('invalid rubric keyword groups')
    else:
        raise ValueError('unverified answer kind')
