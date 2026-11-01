"""Exact source-bound duplicate approvals; never edit question or learner records."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .asset_library import AssetLibrary
from .library_refs import ASSET_FIELDS, PROTECTED_FIELDS


def fingerprint(item: dict, vault_root: Path) -> str:
    """Hash the complete record, using stable IDs in explicit asset fields only.

    This normalizes asset locations only. It does not normalize OCR, answers,
    whitespace, optional fields, protected answers/citations, or prose content.
    """
    library = AssetLibrary(vault_root)
    references = {}
    for identifier, record in library.records().items():
        stable = 'asset:' + identifier
        for reference in [stable, record['path'], *record.get('aliases', [])]:
            references[reference] = stable

    def normalize(value, *, asset_field=False):
        if isinstance(value, dict):
            return {key: child if key in PROTECTED_FIELDS else normalize(child, asset_field=key in ASSET_FIELDS)
                    for key, child in value.items()}
        if isinstance(value, list):
            return [normalize(child, asset_field=asset_field) for child in value]
        if asset_field and isinstance(value, str) and value in references:
            library.read(value)
            return references[value]
        return value

    data = json.dumps(normalize(item), sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()
    return hashlib.sha256(data).hexdigest()


class Reviews:
    """Read immutable, explicitly reviewed pair approvals from the catalog."""

    def __init__(self, vault_root: Path):
        self.root = vault_root
        self.entries = []
        self.errors = []
        if not (vault_root / 'Library/catalog.json').exists():
            return
        library = AssetLibrary(vault_root)
        for identifier, record in library.records().items():
            if record.get('kind') != 'question_duplicate_review':
                continue
            reference = 'asset:' + identifier
            course = record.get('course')
            try:
                if (not isinstance(course, str) or not course
                        or not record['path'].startswith(f'Library/Courses/{course}/Questions/Reviews/')):
                    raise ValueError('review must belong to its course review shelf')
                document = json.loads(library.read(reference, max_bytes=1024 * 1024))
                if (not isinstance(document, dict) or type(document.get('format_version')) is not int
                        or document['format_version'] != 1
                        or not isinstance(document.get('reviews'), list)):
                    raise ValueError('invalid duplicate review document')
                for row in document['reviews']:
                    self._validate(row, course)
                self.entries.extend((reference, record['sha256'], row) for row in document['reviews'])
            except (ValueError, OSError, TypeError) as exc:
                self._error(f'{reference}: {exc}')

    def _error(self, message):
        if message not in self.errors:
            self.errors.append(message)

    @staticmethod
    def _validate(row, course):
        def digest(value):
            return isinstance(value, str) and len(value) == 64 and all(c in '0123456789abcdef' for c in value)

        if (not isinstance(row, dict) or row.get('reviewed') is not True or row.get('verdict') != 'equivalent'
                or not isinstance(row.get('identity'), str) or not row['identity'].startswith(course + '_')
                or not isinstance(row.get('kcs'), list) or not row['kcs']
                or any(not isinstance(k, str) or not k.startswith(course + '-') for k in row['kcs'])
                or len(set(row['kcs'])) != len(row['kcs'])
                or any(not isinstance(row.get(key), str) or not row[key].strip() for key in ('reviewer', 'evidence'))):
            raise ValueError('incomplete reviewed equivalence evidence')
        for key in ('keep', 'drop'):
            binding = row.get(key)
            if (not isinstance(binding, dict) or not isinstance(binding.get('id'), str) or not binding['id']
                    or not digest(binding.get('sha256'))):
                raise ValueError('invalid complete record binding')
        source = row.get('source')
        if (row['keep']['id'] == row['drop']['id'] or not isinstance(source, dict)
                or not isinstance(source.get('asset'), str) or not source['asset'].startswith('asset:')
                or not digest(source.get('sha256'))):
            raise ValueError('invalid source or duplicate pair binding')

    def filter(self, rows: list[dict], identity: str, context: tuple[str, ...]) -> list[dict]:
        matching = [(ref, digest, row) for ref, digest, row in self.entries
                    if row['identity'] == identity and sorted(row['kcs']) == list(context)]
        if not matching:
            return rows
        by_id = {}
        for item in rows:
            by_id.setdefault(item['id'], []).append(item)
        library = AssetLibrary(self.root)
        decisions = set()
        for reference, review_digest, review in matching:
            try:
                # Revalidate review bytes and source bytes at application time.
                if hashlib.sha256(library.read(reference, max_bytes=1024 * 1024)).hexdigest() != review_digest:
                    raise ValueError('stale duplicate review resource')
                keep, drop = review['keep'], review['drop']
                if len(by_id.get(keep['id'], [])) != 1 or len(by_id.get(drop['id'], [])) != 1:
                    raise ValueError('review pair is absent or ambiguous')
                pair = [by_id[keep['id']][0], by_id[drop['id']][0]]
                if any(fingerprint(item, self.root) != binding['sha256'] for item, binding in zip(pair, (keep, drop))):
                    raise ValueError('stale complete record fingerprint')
                source = review['source']
                if hashlib.sha256(library.read(source['asset'])).hexdigest() != source['sha256']:
                    raise ValueError('stale reviewed source digest')
                record = library.record(source['asset'])
                references = {source['asset'], record['path'], *record.get('aliases', [])}
                if not any(ref in references for item in pair
                           for ref in [item.get('image'), *(item.get('images') or [])] if isinstance(ref, str)):
                    raise ValueError('reviewed source is not bound to either record image')
                decisions.add((keep['id'], drop['id']))
            except (ValueError, OSError, TypeError) as exc:
                self._error(f'{reference}: {exc}')
        kept, dropped = {keep for keep, _ in decisions}, {drop for _, drop in decisions}
        if kept & dropped or len(dropped) != len(decisions):
            self._error('conflicting duplicate review decisions')
            return rows
        return [item for item in rows if item['id'] not in dropped]
