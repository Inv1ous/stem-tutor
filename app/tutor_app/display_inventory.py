"""Resource-bound question inventory for presentation, never eligibility or marking.

A learner-state change does not change the kinds published for a skill. Reuse
that display inventory until its resource signatures change. Actual question
selection keeps its independent source authentication in the engine.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Mapping


@dataclass(frozen=True)
class QuestionInventory:
    kinds: Mapping[str, frozenset[str]]
    topical_chapters: frozenset[str]
    resource_key: tuple
    source_courses: frozenset[str] = frozenset()  # courses with source-verified practice (no mastery credit)

    def __post_init__(self):
        object.__setattr__(self, 'kinds', MappingProxyType(
            {kc: frozenset(kinds) for kc, kinds in self.kinds.items()}))
        object.__setattr__(self, 'topical_chapters', frozenset(self.topical_chapters))
        object.__setattr__(self, 'resource_key', tuple(self.resource_key))
        object.__setattr__(self, 'source_courses', frozenset(self.source_courses))


def _signature(path: Path) -> tuple:
    """Observe pointer/catalog identity, including a changed symlink or target."""
    def values(info):
        return (info.st_dev, info.st_ino, info.st_mode, info.st_size,
                info.st_mtime_ns, info.st_ctime_ns)
    try:
        link = path.lstat()
    except OSError as exc:
        return ('unavailable', type(exc).__name__, exc.errno)
    try:
        target = values(path.stat())
    except OSError as exc:
        target = ('unavailable', type(exc).__name__, exc.errno)
    return values(link), target


def resource_key(app) -> tuple:
    """Cheap invalidation hint; these metadata checks do not authenticate assets."""
    root = Path(app.vault).absolute()
    return (id(app.tutor.packs), str(root),
            _signature(root / '.tutor/packs/CURRENT'),
            _signature(root / '.tutor/topicals/CURRENT'),
            _signature(root / 'Library/catalog.json'))


def peek_inventory(app) -> QuestionInventory | None:
    """The cached summary when it is still current, else None: never loads, so it is safe on the UI thread."""
    cached = getattr(app, '_question_display_inventory', None)
    if (isinstance(cached, QuestionInventory) and getattr(app, '_question_inventory_packs', None) is app.tutor.packs
            and cached.resource_key == resource_key(app)):
        return cached
    return None


def _source_courses(app) -> frozenset[str]:
    """Course names the sealed source-practice release covers; none when there is no release."""
    try:
        from tutorlib.source_practice import Collection
        return frozenset(Collection(app.vault).courses())
    except Exception:  # noqa: BLE001 - an absent or damaged release only means "no source-verified questions"
        return frozenset()


def _clear_cache(app) -> None:
    app._question_display_inventory = None
    app._question_inventory_packs = None


def get_inventory(app, *, force: bool = False) -> QuestionInventory:
    """Load a sealed display summary once per resource version.

    Only kind names and chapter identifiers leave the fresh bank request. No
    question content, answer, source image, or eligibility result is cached.
    A resource change during the load discards the summary instead of mixing
    versions; the next call retries independently.
    """
    packs = app.tutor.packs
    before = resource_key(app)
    cached = getattr(app, '_question_display_inventory', None)
    if (not force and isinstance(cached, QuestionInventory)
            and getattr(app, '_question_inventory_packs', None) is packs
            and cached.resource_key == before):
        return cached
    _clear_cache(app)
    kinds = {}
    try:
        with packs.topicals.request():
            for kc in tuple(packs.kcs):
                kinds[kc] = frozenset(row['kind'] for row in packs.items_for(kc)
                                      if isinstance(row.get('kind'), str))
            chapters = frozenset(packs.topical_chapters())
            current = packs.topicals.request_current()
        after = resource_key(app)
        if not current or after != before:
            return QuestionInventory({}, frozenset(), after)
    except (OSError, ValueError, KeyError, TypeError):
        return QuestionInventory({}, frozenset(), resource_key(app))
    result = QuestionInventory(kinds, chapters, before, _source_courses(app))
    app._question_display_inventory = result
    # Retain object identity too, so a later Packs instance cannot accidentally
    # reuse a collected object's numeric id and inherit its display summary.
    app._question_inventory_packs = packs
    return result
