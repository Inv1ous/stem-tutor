"""Canonical question-media names, role classification and same-content guard.

Name: <course>_<series><yy>_<paper-variant>_q<NN>[<part>]_<role>_<sha12>.<ext>
  Cambridge  9701_m17_12_q01_mcq_<sha12>.png
  Edexcel    FP1_jan14_wfm01-01_q04_long_<sha12>.png
  Booklet    P2_c2-algebra-remainder-factor-theorems_q03_long_<sha12>.png   (topic booklet, no exam paper id)
  Fallback   <course>_nosrc_<role>_<sha12>.png   (metadata not derivable)
  Shared     shared_nosrc_<role>_<sha12>.png     (byte-identical crop used by more than one course)
Roles: mcq|long|key|ref|ctx. sha12 is the first 12 hex of the file's sha256, so equal
content always yields an equal name for equal metadata and duplicates collide.
Nothing here writes to a vault except ``register_canonical`` (via the catalog writer).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from tutorlib.asset_library import AssetLibrary, write_asset

ROLES = ('mcq', 'long', 'key', 'ref', 'ctx')
FOLDER = {'mcq': 'MCQ', 'long': 'Long', 'ctx': 'Long', 'key': 'Keys', 'ref': 'Reference'}
COURSES = ('9701', '9702', 'D1', 'FP1', 'FP2', 'FP3', 'M1', 'P1', 'P2', 'P3', 'P4', 'S1', 'S2', 'S3')
IMAGE_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.svg', '.webp')
MONTHS = {'01': 'jan', '02': 'feb', '03': 'mar', '04': 'apr', '05': 'may', '06': 'jun',
          '07': 'jul', '08': 'aug', '09': 'sep', '10': 'oct', '11': 'nov', '12': 'dec'}

_CAMBRIDGE = re.compile(r'(?P<course>\d{4})_(?P<series>[msw])(?P<yy>\d\d)_(?P<paper>\d\d)_q(?P<q>\d+)(?P<part>[a-z]*)')
_EDEXCEL = re.compile(r'(?P<course>[A-Z]+\d)_pearson-edexcel-ial_(?P<code>[A-Z]+\d\d)_(?P<year>\d{4})-(?P<month>\d\d)_'
                      r'(?P<paper>\d\d)_q(?P<q>\d+)(?P<part>[a-z]*)')
_FILENAME_QID = re.compile(r'(?P<course>\d{4})[_-](?P<series>[msw])(?P<yy>\d\d)[_-](?P<paper>\d\d)[_-]q(?P<q>\d+)(?P<part>[a-z]*)(?![0-9])')
_HASH_TAIL = re.compile(r'(?:-[0-9a-f]{12})?-[0-9a-f]{16}(?=\.)')
_SHA = re.compile(r'[0-9a-f]{64}')
_NAME = re.compile(r'(?P<course>[A-Za-z0-9]+)_(?P<stem>.+)_(?P<role>mcq|long|key|ref|ctx)_(?P<sha12>[0-9a-f]{12})(?P<ext>\.[a-z0-9.]+)')

KEY_WORDS = re.compile(r'(?:^|[-_.])(?:key|ms|markscheme|mark-scheme|notes)(?:[-_.0-9]|$)')
REFERENCE_WORDS = re.compile(r'periodic|data-?sheet|formula|formulae|qualitative-analysis|list-of-data|datasheet')
CONTEXT_WORDS = re.compile(r'(?:^|[-_.])(?:context|ctx)(?:[-_.0-9]|$)')


def parse_qid(qid: str | None) -> dict | None:
    """Split an official question id into series/paper/question parts, or None."""
    if not isinstance(qid, str):
        return None
    if m := _CAMBRIDGE.fullmatch(qid):
        return {'course': m['course'], 'series': m['series'] + m['yy'], 'paper': m['paper'],
                'question': int(m['q']), 'part': m['part']}
    if m := _EDEXCEL.fullmatch(qid):
        return {'course': m['course'], 'series': MONTHS[m['month']] + m['year'][2:],
                'paper': m['code'].lower() + '-' + m['paper'], 'question': int(m['q']), 'part': m['part']}
    return None


def qid_from_filename(name: str) -> str | None:
    """Recover a Cambridge qid from a legacy file name such as 9701_m17_12_q1-<hash>.png."""
    m = _FILENAME_QID.search(PurePosixPath(name).name)
    return f"{m['course']}_{m['series']}{m['yy']}_{m['paper']}_q{m['q']}{m['part']}" if m else None


def topic_slug(title: str) -> str:
    """"C2 Algebra: Remainder & Factor Theorems – Questions" -> "c2-algebra-remainder-factor-theorems"."""
    title = re.sub(r'\s*[-–—]\s*(?:questions|mark ?scheme|ms)\s*$', '', str(title or ''), flags=re.IGNORECASE)
    return re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')[:60].strip('-')


def canonical_name(course: str, role: str, sha256: str, *, qid: str | None = None,
                   part: str | None = None, ext: str = 'png', topic: str | None = None,
                   label: str | None = None) -> str:
    """Deterministic canonical file name. Without a parseable qid, a topic booklet's title and question
    label name it; without either the safe fallback is used."""
    if role not in ROLES:
        raise ValueError(f'unknown role: {role}')
    if not isinstance(sha256, str) or not _SHA.fullmatch(sha256):
        raise ValueError('sha256 must be 64 lowercase hex digits')
    ext = ext.lower().lstrip('.')
    if not re.fullmatch(r'[a-z0-9]+(?:\.[a-z0-9]+)?', ext):
        raise ValueError('unsafe extension')
    if not isinstance(course, str) or not re.fullmatch(r'[A-Za-z0-9]+', course):
        raise ValueError('unsafe course')
    parsed = parse_qid(qid)
    if parsed is None or parsed['course'] != course:
        slug, number = topic_slug(topic) if topic else '', str(label or '').strip().lower()
        if slug and re.fullmatch(r'\d{1,3}[a-z]{0,3}', number):
            digits = re.match(r'\d+', number).group()
            return f'{course}_{slug}_q{int(digits):02d}{number[len(digits):]}_{role}_{sha256[:12]}.{ext}'
        return f'{course}_nosrc_{role}_{sha256[:12]}.{ext}'
    suffix = (part if part is not None else parsed['part']).lower()
    if suffix and not re.fullmatch(r'[a-z]{1,3}', suffix):
        suffix = ''
    return (f"{course}_{parsed['series']}_{parsed['paper']}_q{parsed['question']:02d}{suffix}"
            f'_{role}_{sha256[:12]}.{ext}')


def is_fallback(name: str) -> bool:
    return '_nosrc_' in PurePosixPath(name).name


def is_canonical(name: str) -> bool:
    return _NAME.fullmatch(PurePosixPath(name).name) is not None


def canonical_parts(name: str) -> dict | None:
    """Course/role/sha12 of a canonical name (a ``--<asset id>`` duplicate suffix is tolerated)."""
    m = _NAME.fullmatch(re.sub(r'--[A-Za-z0-9._:-]+(?=\.)', '', PurePosixPath(name).name))
    return m.groupdict() if m else None


def legacy_base(name: str) -> str:
    """File name without the trailing content-hash tokens added by older registrations."""
    return _HASH_TAIL.sub('', PurePosixPath(name).name)


def filename_role(name: str) -> str | None:
    """Lowest-trust evidence: role implied by the file name alone."""
    base = legacy_base(name).lower()
    if REFERENCE_WORDS.search(base):
        return 'ref'
    if KEY_WORDS.search(base):
        return 'key'
    if CONTEXT_WORDS.search(base):
        return 'ctx'
    return None


def folder_for(role: str) -> str:
    return FOLDER[role]


def classify(votes, name: str | None = None) -> dict:
    """Pick a role from evidence votes: iterable of (tier, role, source), lower tier = stronger.

    The strongest tier that has any vote decides. Inside that tier the votes must agree
    (long/ctx are compatible and share a folder); disagreement is reported as a conflict
    and no role is chosen. File-name evidence is appended as the weakest tier (9).
    Weaker tiers that disagree with the decision are listed in ``disagree``.
    """
    votes = [(int(t), r, s) for t, r, s in votes if r in ROLES]
    if name:
        role = filename_role(name)
        if role:
            votes.append((9, role, 'filename'))
    if not votes:
        return {'role': None, 'tier': None, 'conflict': False, 'sources': [], 'disagree': []}
    best = min(t for t, _, _ in votes)
    top = [(r, s) for t, r, s in votes if t == best]
    roles = {r for r, _ in top}
    sources = sorted({s for _, s in top})
    if len({FOLDER[r] for r in roles}) > 1:
        return {'role': None, 'tier': best, 'conflict': True, 'sources': sources, 'disagree': sorted(roles)}
    role = 'long' if roles == {'long', 'ctx'} else next(iter(roles))
    if (role in ('long', 'ctx') or (best >= 3 and role != 'key')) and name and filename_role(name) == 'ref':
        return {'role': 'ref', 'tier': best, 'conflict': False, 'sources': sources + ['filename'], 'disagree': []}
    disagree = sorted({r for t, r, _ in votes if t > best and FOLDER[r] != FOLDER[role]})
    return {'role': role, 'tier': best, 'conflict': False, 'sources': sources, 'disagree': disagree}


def _course_of(record: dict) -> str | None:
    if record.get('course'):
        return record['course']
    parts = PurePosixPath(record['path']).parts
    return parts[2] if len(parts) > 3 and parts[:2] == ('Library', 'Courses') else None


def find_duplicate(vault: Path, sha256: str, course: str) -> dict | None:
    """Existing image record with identical content usable for ``course`` (same course or shared).

    Read-only. Returns {'id', 'path', 'course'} for the lowest id (deterministic) or None.
    Sidecar JSON and non-image records never match.
    """
    if not _SHA.fullmatch(sha256 or ''):
        raise ValueError('sha256 must be 64 lowercase hex digits')
    found = []
    for identifier, record in AssetLibrary(vault).records().items():
        if record.get('sha256') != sha256 or not record['path'].lower().endswith(IMAGE_EXTENSIONS):
            continue
        owner = _course_of(record)
        if owner in (course, None):
            found.append((identifier, record['path'], owner))
    if not found:
        return None
    identifier, path, owner = min(found)
    return {'id': 'asset:' + identifier, 'path': path, 'course': owner}


def store_question_media(vault: Path, data: bytes, legacy: str, *, course: str, role: str, qid: str | None = None,
                         topic: str | None = None, label: str | None = None, metadata: dict | None = None) -> str:
    """Publish one extracted crop in its course folder under its canonical name; ``legacy`` (the reference string
    a release or bank records) stays a declared alias, so readers of that string keep working.

    Idempotent: a legacy reference that already resolves to the same bytes is left as it is, and a crop whose
    canonical name is already registered gains the legacy alias instead of a second copy."""
    import hashlib
    from tutorlib.asset_library import register_asset
    digest = hashlib.sha256(data).hexdigest()
    library = AssetLibrary(vault)

    def known(reference):
        try:
            record = library.record(reference)
        except ValueError as exc:
            if 'unknown asset reference' not in str(exc):
                raise
            return False
        if record['sha256'] != digest:
            raise ValueError(f'{reference} is already registered with other content')
        return True

    if known(legacy):
        return legacy
    name = canonical_name(course, role, digest, qid=qid, topic=topic, label=label)
    relative = f'Library/Courses/{course}/Questions/Media/{FOLDER[role]}/{name}'
    junk = _looks_like_junk(data, role)
    if junk:
        metadata = {**(metadata or {}), 'junk': True}  # a header, footer or blank strip seen before: never shown
    if known(relative):
        register_asset(vault, relative, aliases=[legacy])
    else:
        write_asset(vault, relative, data, aliases=[legacy],
                    metadata={**(metadata or {}), 'course': course, 'kind': 'Questions/Media'})
    return legacy


def _looks_like_junk(data: bytes, role: str) -> bool:
    """A crop that looks like page furniture the triage already judged junk (question_image_triage.py). Keys are never
    judged. A new suspicious look is left for the next `question_image_triage.py review`."""
    if role not in ('mcq', 'long', 'ctx'):
        return False
    try:
        import question_image_triage as triage
        return triage.check_new(data) == 'junk'
    except Exception:  # noqa: BLE001 - the check never stops an extraction
        return False


def register_canonical(vault: Path, data: bytes, course: str, role: str, *, qid: str | None = None,
                       part: str | None = None, ext: str = 'png', metadata: dict | None = None,
                       subdir: str = 'Questions/Media') -> dict:
    """Register question media under its canonical name, reusing identical existing content.

    Returns {'id', 'path', 'reused'}. An existing same-content image for the course is
    returned untouched (its id and path are kept) instead of writing a second copy.
    """
    import hashlib
    digest = hashlib.sha256(data).hexdigest()
    existing = find_duplicate(vault, digest, course)
    if existing:
        return {'id': existing['id'], 'path': existing['path'], 'reused': True}
    name = canonical_name(course, role, digest, qid=qid, part=part, ext=ext)
    relative = f'Library/Courses/{course}/{subdir}/{FOLDER[role]}/{name}'
    identifier = write_asset(vault, relative, data, metadata={'course': course, **(metadata or {})})
    return {'id': identifier, 'path': relative, 'reused': False}
