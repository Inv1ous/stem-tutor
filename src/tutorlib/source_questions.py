"""Read-only access to tagged source-verified questions (no UI, no learner state).

Two sources, same shape:

* a registered Library resource produced by ``build/migrate_source_questions.py --apply``
  (``Library/Courses/<course>/Questions/SourceVerified/bank-<sha12>.json``), found through the asset catalog;
* an in-memory/Work document from the same builder (``SourceQuestions.from_document``) for use before apply.

Every item keeps ``source_verified=True``, ``mastery_certified=False``, ``teaching_approved=False``.  Items whose
syllabus mapping is below the confidence bar are ``held``: ``items()`` omits them unless asked.
"""
from __future__ import annotations

import copy
import json
from functools import lru_cache
from pathlib import Path

from .asset_library import AssetLibrary

KIND = 'source_verified_questions'


class SourceQuestions:
    def __init__(self, documents: dict[str, dict]):
        """``documents``: course -> bank document (see migrate_source_questions.build_document)."""
        self._docs = {}
        self._by_id = {}
        for course, doc in documents.items():
            if doc.get('kind') != KIND or doc.get('course') != course:
                raise ValueError('not a source-verified question bank for ' + course)
            for item in doc['items']:
                if (item.get('mastery_certified') is not False or item.get('teaching_approved') is not False
                        or item.get('source_verified') is not True):
                    raise ValueError('source question flags must stay unverified for mastery/teaching')
                if item['id'] in self._by_id:
                    raise ValueError('duplicate source question id ' + item['id'])
                self._by_id[item['id']] = item
            self._docs[course] = doc

    # -- construction -----------------------------------------------------
    @classmethod
    def from_document(cls, *documents: dict) -> 'SourceQuestions':
        return cls({d['course']: d for d in documents})

    @classmethod
    def load(cls, vault: Path, courses=None, *, library: AssetLibrary | None = None) -> 'SourceQuestions':
        """Newest registered bank per course (catalog metadata ``kind``/``course``/``built_at``)."""
        library = library or AssetLibrary(Path(vault))
        newest: dict[str, tuple[str, str]] = {}
        for identifier, record in library.records().items():
            if record.get('kind') != KIND:
                continue
            course = record.get('course')
            if courses is not None and course not in courses:
                continue
            key = (record.get('built_at', ''), record['path'])
            if course not in newest or key > newest[course][0:2]:
                newest[course] = (*key, 'asset:' + identifier)
        return cls({course: json.loads(library.read(ref)) for course, (_, _, ref) in newest.items()})

    # -- queries ----------------------------------------------------------
    def courses(self) -> list[str]:
        return sorted(self._docs)

    def provenance(self, course: str) -> dict:
        return copy.deepcopy(self._docs[course]['provenance'])

    def items(self, course: str, *, include_held: bool = False, kc: str | None = None, subtopic: str | None = None) -> list[dict]:
        rows = []
        for item in self._docs.get(course, {}).get('items', []):
            if item['held'] and not include_held:
                continue
            if kc is not None and kc not in item['kcs']:
                continue
            if subtopic is not None and subtopic not in item['tag']['subtopics']:
                continue
            rows.append(copy.deepcopy(item))
        return rows

    def raw_items(self, course: str):
        """Non-held items of one course WITHOUT copying; callers must not mutate them."""
        return (i for i in self._docs.get(course, {}).get('items', []) if not i['held'])

    def item(self, qid: str) -> dict:
        return copy.deepcopy(self._by_id[qid])

    def required_kcs(self, qid: str) -> list[str]:
        """Union of KCs the whole question needs (empty when held)."""
        return list(self._by_id[qid]['kcs'])

    def part_kcs(self, qid: str) -> dict[str, list[str]]:
        """{part label: KCs}.  Parts whose own text could not be tagged map to [] (never guessed);
        single-part questions return {} and are covered by ``required_kcs``."""
        return {p['label']: list(p['kcs']) for p in self._by_id[qid]['parts']}

    def held(self, course: str) -> list[dict]:
        return [{'id': i['id'], 'reason': i['held_reason']} for i in self._docs.get(course, {}).get('items', []) if i['held']]

    def kc_coverage(self, course: str) -> dict[str, int]:
        counts: dict[str, int] = {}
        for item in self._docs.get(course, {}).get('items', []):
            if not item['held']:
                for kc in item['kcs']:
                    counts[kc] = counts.get(kc, 0) + 1
        return dict(sorted(counts.items()))


# -- serving ----------------------------------------------------------------
def servable(item: dict) -> bool:
    """Only tagged, answerable items are ever served: held/unmapped items, an MCQ without a literal key and a
    structured item without a printed total stay out."""
    if item.get('held') or not item.get('kcs') or item.get('source_verified') is not True:
        return False
    if item.get('kind') == 'mcq':
        return item.get('answer') in ('A', 'B', 'C', 'D')
    return item.get('kind') == 'structured' and type(item.get('marks')) is int and item['marks'] > 0


_SAME_INK = 0.005  # share of pixels that may differ (after a blur) for one crop to count as inside another


@lru_cache(maxsize=256)
def _pixels(path: str, stamp: tuple):
    """A crop as blurred greyscale with blank margins trimmed; None when unreadable or blank."""
    import numpy as np
    from PIL import Image, ImageFilter
    with Image.open(path) as image:
        grey = np.asarray(image.convert('L').filter(ImageFilter.GaussianBlur(2)), dtype=np.int16)
    rows = (grey < 230).any(axis=1)
    if not rows.any():
        return None
    top, bottom = int(rows.argmax()), len(rows) - int(rows[::-1].argmax())
    return grey[top:bottom]


def _inside(small, big) -> bool:
    """Whether crop `small` is a strip of crop `big` (same page width, rendered the same)."""
    import numpy as np
    if small is None or big is None or small.shape[1] != big.shape[1] or small.shape[0] > big.shape[0]:
        return False
    height = small.shape[0]
    return any((np.abs(big[y:y + height] - small) > 40).mean() <= _SAME_INK for y in range(big.shape[0] - height + 1))


def display_images(item: dict, root: Path | str | None = None) -> list[str]:
    """The item's images once each, in reading order: shared context (a section's instructions, a shared stem)
    before the question.  Exact repeats are dropped; with the vault ``root``, so is any crop that is only a strip
    of another of the item's crops (the A-D response key cut out again from the section header it sits in).
    An image that cannot be read is always kept."""
    media = item.get('media') or {}
    refs = list(dict.fromkeys(m['path'] for key in ('context_media', 'question_media')
                              for m in media.get(key, []) if m.get('path')))
    return drop_repeated(refs, root)


def without_junk(refs: list[str], root: Path | str) -> list[str]:
    """`refs` less the images the catalog flags as junk (page headers, footers, blank strips: see
    build/question_image_triage.py). A question never loses its last picture: all flagged keeps them all."""
    try:
        library = AssetLibrary(Path(root))
        kept = [ref for ref in refs if not library.record(ref).get('junk')]
    except (OSError, ValueError):
        return refs
    return kept or refs


def drop_repeated(refs: list[str], root: Path | str | None = None) -> list[str]:
    """`refs` once each: exact repeats (and two names for one file) are dropped, and with the vault ``root`` so is any
    crop that is only a strip of another one. An image that cannot be read is always kept."""
    refs = list(dict.fromkeys(refs))
    if root is None:
        return refs
    refs = without_junk(refs, root)
    if len(refs) < 2:
        return refs
    try:
        from .library_refs import LibraryRefs
        library, base = LibraryRefs(root), Path(root)
        paths = {}
        for ref in refs:
            path = base / library.reference(ref)
            paths[ref] = str(path.resolve())
        seen: set[str] = set()  # two names for one file
        refs = [ref for ref in refs if not (paths[ref] in seen or seen.add(paths[ref]))]
        crops = {}
        for ref in refs:
            info = Path(paths[ref]).stat()
            crops[ref] = _pixels(paths[ref], (info.st_size, info.st_mtime_ns))
    except Exception:  # noqa: BLE001 - never hide a figure because a check failed
        return refs
    return [ref for ref in refs if not any(
        other != ref and crops[ref] is not None and crops[other] is not None
        and crops[other].size > crops[ref].size and _inside(crops[ref], crops[other]) for other in refs)]


def to_instance(item: dict, root: Path | str | None = None) -> dict:
    """The normal-question-flow shape of one source-verified item.  It carries ``source_verified`` so the engine
    tags its ``answer`` events and remembers it in ``source_seen``; attempts count towards mastery.
    A question with images is shown by its images alone: the text pulled from the PDF is not used as its stem."""
    media = item.get('media') or {}
    images = display_images(item, root)
    inst = {
        'id': item['id'], 'kcs': list(item['kcs']), 'kind': item['kind'], 'stem': '' if images else item.get('stem', ''),
        'marks': item.get('marks', 1), 'difficulty': 3,
        'source': {'type': 'source_verified', 'ref': 'Source-verified question ' + str(item.get('label', '')),
                   'course': item.get('course'), 'source_id': item.get('source')},
        'source_verified': True, 'mastery_certified': False, 'teaching_approved': False,
        'parts': [{'label': p['label'], 'kcs': list(p['kcs'])} for p in item.get('parts', [])],
    }
    if images:
        inst['images'] = images
        inst['image'] = images[0]
    if item['kind'] == 'mcq':
        inst['answer'] = item['answer']
    else:
        scheme_media = [m['path'] for m in media.get('mark_scheme_media', []) if m.get('path')]
        point = ('Compare your working with the original mark scheme.' if scheme_media
                 else (item.get('scheme_text') or 'Compare your working with the original mark scheme.')[:4000])
        inst['scheme'] = [{'point': point, 'whole_rubric': {'version': 1, 'max_marks': inst['marks'],
                                                             'media': list(dict.fromkeys(scheme_media))}}]
    return inst
