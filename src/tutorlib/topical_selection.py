"""Read-only reviewed-bank filtering and bounded, topic-balanced random sets."""
from __future__ import annotations

import re

from . import topicals

TYPE_CHOICES = (
    ('MCQs', 'mcq'),
    ('Definitions', 'definition'),
    ('Written answers', 'written'),
    ('Calculations / expressions', 'calculation'),
    ('Long / structured (mixed)', 'structured'),
)
TYPES = tuple(value for _, value in TYPE_CHOICES)
COUNT_LIMIT = 200
_DEFINITION = re.compile(r'^\s*(?:define\b|what is meant by\b)', re.I)


def category(item: dict) -> str | None:
    """Use existing kinds and explicit definition commands, never infer image contents."""
    kind = item.get('kind')
    if kind == 'short':
        command = str(item.get('command_word') or '').strip().casefold()
        return 'definition' if command == 'define' or _DEFINITION.match(item.get('stem') or '') else 'written'
    return {'mcq': 'mcq', 'numeric': 'calculation', 'expression': 'calculation',
            'structured': 'structured'}.get(kind)


def validate_types(types: list[str] | None) -> list[str]:
    if types is None:
        return list(TYPES)
    if (not isinstance(types, (list, tuple)) or not types
            or any(not isinstance(value, str) or value not in TYPES for value in types)):
        raise ValueError('Choose at least one recognised question type.')
    return [value for value in TYPES if value in types]


def validate_count(count: int | None) -> None:
    if count is not None and (type(count) is not int or not 1 <= count <= COUNT_LIMIT):
        raise ValueError(f'Choose a whole number of questions from 1 to {COUNT_LIMIT}.')


def pools(packs, state: dict, chapters: list[str], types: list[str] | None = None,
          *, used=(), disclosed=()) -> dict[str, list[dict]]:
    """Eligible serving contexts; a cross-chapter identity may appear in several pools."""
    bank = getattr(packs, 'topicals', None)
    if bank is None:
        return _pools(packs, state, chapters, types, used=used, disclosed=disclosed)
    with bank.request() as outer:
        groups = _pools(packs, state, chapters, types, used=used, disclosed=disclosed)
        return groups if not outer or bank.request_current() else {chapter: [] for chapter in groups}


def _pools(packs, state: dict, chapters: list[str], types: list[str] | None = None,
           *, used=(), disclosed=()) -> dict[str, list[dict]]:
    selected = set(validate_types(types))
    used, disclosed = set(used), set(disclosed)
    excluded = {(row['identity'], row['chapter']) for row in state.get('topical_exclusions', [])}
    groups = {}
    for chapter in dict.fromkeys(chapters):
        unique = {}
        for item in packs.topical_items(chapter):
            key = topicals.identity(item)
            if not key or key in used or (key, chapter) in excluded or category(item) not in selected:
                continue
            if disclosed and packs.aliases_for(item) & disclosed:
                continue
            if topicals.eligibility(item, chapter, state, packs)['status'] not in ('solvable', 'supported'):
                continue
            unique.setdefault(key, item)
        groups[chapter] = list(unique.values())
    return groups


def counts(groups: dict[str, list[dict]]) -> dict[str, int]:
    identities = {value: set() for value in TYPES}
    for rows in groups.values():
        for item in rows:
            if (kind := category(item)) in identities:
                identities[kind].add(topicals.identity(item))
    return {kind: len(keys) for kind, keys in identities.items()}


def sample(groups: dict[str, list[dict]], count: int, rng) -> list[dict]:
    """Shuffle within topics and take topic rounds, using each source identity once."""
    validate_count(count)
    pending = {chapter: list(dict.fromkeys(key for item in rows if (key := topicals.identity(item))))
               for chapter, rows in groups.items() if rows}
    for keys in pending.values():
        rng.shuffle(keys)
    result = []
    while pending and len(result) < count:
        chapters = list(pending)
        rng.shuffle(chapters)
        assigned = {}

        def allocate(chapter, visited):
            # Reassign a flexible topic's question when a later topic has no alternative.
            # Each round matches at most COUNT_LIMIT topics, bounding recursion depth.
            for key in pending[chapter]:
                if key in visited:
                    continue
                visited.add(key)
                previous = assigned.get(key)
                if previous is None or allocate(previous, visited):
                    assigned[key] = chapter
                    return True
            return False

        for chapter in chapters:
            allocate(chapter, set())
            if len(result) + len(assigned) == count:
                break
        if not assigned:
            break
        round_ = [{'identity': key, 'chapter': chapter} for key, chapter in assigned.items()]
        rng.shuffle(round_)
        result.extend(round_)
        pending = {chapter: left for chapter, keys in pending.items()
                   if (left := [key for key in keys if key not in assigned])}
    return result
