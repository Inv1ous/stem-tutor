"""Reviewed, local source questions and deterministic prerequisite policy.

The bank is independent of published teaching packs. A damaged bank supplies no
items; legacy teaching content remains usable. Open attempts hold their own copy.
"""
from __future__ import annotations

import copy
import json
import math
import re
from pathlib import Path

from .library_refs import LibraryRefs
from .asset_library import AssetLibrary

_QID = re.compile(r'(970[12])_([msw]\d{2})_(?:qp_)?(\d{2})_q(\d+)(.*)', re.I)
_REF = re.compile(r'(970[12]).*?(Mar|Feb|Jun|May|Oct|Nov)\w*\s+(20\d{2}).*?P(\d{2}).*?Q(\d+)(.*)', re.I)


def identity(item: dict) -> str | None:
    """Canonical paper question plus independently assessed part (if present)."""
    source = item.get('source') or {}
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
            or chapter not in chapters
            or any(meta.get('revision') != packs.syllabus_versions.get(packs.subtopics[k]['spec']) for k in required)):
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

    def refresh(self) -> None:
        try:
            version = (self.base / 'CURRENT').read_text().strip()
        except FileNotFoundError:
            self.items, self.errors, self.pointer = [], [], None
            return
        except (OSError, UnicodeError) as exc:
            self.items, self.errors = [], [f'Topical bank unavailable: {exc}']
            self.pointer = None
            return
        if version == self.pointer:
            return
        self.pointer = version
        self.items, self.errors = [], []
        try:
            if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', version) or version in ('.', '..'):
                raise ValueError('invalid CURRENT pointer')
            canonical = f'Library/Shared/Topicals/Releases/{version}/bank.json'
            target = self.root / canonical
            if target.exists() or target.is_symlink():
                bank = json.loads(AssetLibrary(self.root).read(canonical))
            else:
                bank = json.loads((self.base / version / 'bank.json').read_text())
            validate_bank(bank, self.packs, self.root)
            self.items = _runtime_items(bank['items'], self.root)
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
            self.pointer = None  # only a fully verified load may cache a release
            self.errors = [f'Topical bank unavailable: {exc}']

    def _validate(self, item: dict, revisions: dict) -> None:
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
        if not isinstance(kcs, list) or not kcs or any(k not in self.packs.kcs or self.packs.kcs[k].get('level') != 'AS' for k in kcs):
            raise ValueError('invalid AS assessed KCs')
        if len(kcs) != len(set(kcs)):
            raise ValueError('duplicate assessed KC')
        spec = self.packs.kcs[kcs[0]]['spec']
        source_qid = _QID.fullmatch(str(item['source']['qid']).lower())
        if (source_qid is None or source_qid[1] != spec
                or any(self.packs.kcs[k]['spec'] != spec for k in kcs)):
            raise ValueError('item source or assessed KC course mismatch')
        if (meta.get('revision') != revisions.get(spec) or any(self.packs.subtopics[k]['spec'] != spec
                for k in meta['requires'] + meta['chapters'])):
            raise ValueError('item revision or subject mismatch')
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
            scheme = item.get('scheme')
            if (not isinstance(scheme, list) or not scheme or len(scheme) != item.get('marks', 1)
                    or any(not isinstance(p, dict) or not isinstance(p.get('point'), str) or not p['point'].strip()
                           or 'mark' in p and (not isinstance(p['mark'], str) or not p['mark'].strip()) for p in scheme)):
                raise ValueError('invalid marking points or total marks')
            for point in scheme:
                if point.get('check'):
                    _validate_answer(point['check'])
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
    checker = Bank(Path(asset_root), packs)
    identities, ids = set(), set()
    for item in items:
        try:
            checker._validate(item, revisions)
        except (KeyError, TypeError, AttributeError) as exc:
            raise ValueError(f'invalid item schema: {exc}') from None
        key = identity(item)
        if key in identities or item['id'] in ids:
            raise ValueError('duplicate canonical question or item ID')
        identities.add(key)
        ids.add(item['id'])


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
