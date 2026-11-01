"""Stage proposed factual corrections in memory; never modify refine snapshots or files."""
from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import stat
import sys
from pathlib import Path

MAX_SOURCE_BYTES = 128 * 1024 * 1024
STRUCTURED_SELECTORS = (['items', {'id': 'P2-1-i15'}, 'rubric'], ['worked', {'id': 'we2'}, 'faded'],
    # 2026-10-30: P1-1 answer.sf_ok narrowed from [3, 4] to [3] (stems say three significant figures; WMA11 instruction)
    ['items', {'id': 'P1-1-i09'}, 'answer', 'sf_ok'], ['items', {'id': 'P1-1-i10'}, 'answer', 'sf_ok'],
    ['items', {'id': 'P1-1-i25'}, 'answer', 'sf_ok'], ['items', {'id': 'P1-1-i29'}, 'answer', 'sf_ok'],
    ['items', {'id': 'P1-1-i30'}, 'answer', 'sf_ok'], ['items', {'id': 'P1-1-i60'}, 'answer', 'sf_ok'],
    # 2026-10-30: P1-4-i01 stored answer value 4.0 is for a=2, which the template excludes; numeric slot
    # 2026-10-30: P1 rubric keyword groups (review haiku-review-p1-rubric-1); P1-1-r01 is an addition, not here
    ['items', {'id': 'P1-1-i21'}, 'rubric'],
    ['items', {'id': 'P1-1-i36'}, 'rubric'],
    ['items', {'id': 'P1-1-i44'}, 'rubric'],
    ['items', {'id': 'P1-1-i50'}, 'rubric'],
    ['items', {'id': 'P1-1-i67'}, 'rubric'],
    ['items', {'id': 'P1-5-i02'}, 'rubric'],
    ['items', {'id': 'P1-4-i01'}, 'answer', 'value'],
    # 2026-10-30: 9702-6.2-x017 options are figures only; the whole-question image carries them (null options, reviewed)
    ['items', {'id': '9702-6.2-x017'}, 'options'],
    # 2026-10-30: 9702-6.1 misconception m8 refutation (string slot; reviewed; contradicted the unloaded-reference convention)
    ['misconceptions', {'id': 'm8'}, 'refutation'])


def _structured_slot(document, path):
    """Return (holder, key) for an approved structured selector; the id must match exactly one row."""
    rows = document[path[0]]
    matches = [row for row in rows if isinstance(row, dict) and row.get('id') == path[1]['id']]
    if len(matches) != 1:
        raise ValueError('structured correction must match exactly once')
    holder = matches[0]
    for key in path[2:-1]:
        holder = holder[key]
    return holder, path[-1]

# Exact item selectors approved for source-verified PDF transcription faults (2026-10-29), one item each:
# 9701-2.3-x010 (word spaces), 9701-3.6-p08 (degree sign), 9701-4.1-x018 (multiplication sign),
# 9701-3.5-x011 (stem and four option rows rewritten to the source question, answer key D unchanged).
APPROVED_ITEM_SELECTORS = (
    ['items', {'id': '9701-2.3-x010'}, 'stem'],
    ['items', {'id': '9701-3.6-p08'}, 'stem'],
    ['items', {'id': '9701-4.1-x018'}, 'stem'],
    ['items', {'id': '9701-3.5-x011'}, 'stem'],
    ['items', {'id': '9701-3.5-x011'}, 'options', 'A'],
    ['items', {'id': '9701-3.5-x011'}, 'options', 'B'],
    ['items', {'id': '9701-3.5-x011'}, 'options', 'C'],
    ['items', {'id': '9701-3.5-x011'}, 'options', 'D'],
    ['items', {'id': '9701-3.4-i19'}, 'stem'],
    # 2026-10-29: source-verified transcription faults in 9701-8.1 (x003 stem, x006 stem) and 9701-7.1 (x040 stem, x050 options)
    ['items', {'id': '9701-8.1-x003'}, 'stem'],
    ['items', {'id': '9701-8.1-x006'}, 'stem'],
    ['items', {'id': '9701-7.1-x040'}, 'stem'],
    ['items', {'id': '9701-7.1-x050'}, 'options', 'A'],
    ['items', {'id': '9701-7.1-x050'}, 'options', 'B'],
    ['items', {'id': '9701-7.1-x050'}, 'options', 'C'],
    ['items', {'id': '9701-7.1-x050'}, 'options', 'D'],
    ['items', {'id': '9701-8.1-x003'}, 'options', 'A'],
    ['items', {'id': '9701-8.1-x003'}, 'options', 'B'],
    ['items', {'id': '9701-8.1-x003'}, 'options', 'C'],
    ['items', {'id': '9701-8.1-x003'}, 'options', 'D'],
    # 2026-10-29: source-verified PDF copy faults in 9702-3.3 stems (degree signs and multiplication signs)
    ['items', {'id': '9702-3.3-p09'}, 'stem'],
    ['items', {'id': '9702-3.3-x009'}, 'stem'],
    ['items', {'id': '9702-3.3-x014'}, 'stem'],
    ['items', {'id': '9702-3.3-x025'}, 'stem'],
    # 2026-10-30: source-verified option restorations in 9702-5.2 (p06 Q17 2023 w13; x025 Q19 2025 s11)
    ['items', {'id': '9702-5.2-p06'}, 'options', 'A'],
    ['items', {'id': '9702-5.2-p06'}, 'options', 'B'],
    ['items', {'id': '9702-5.2-p06'}, 'options', 'C'],
    ['items', {'id': '9702-5.2-p06'}, 'options', 'D'],
    ['items', {'id': '9702-5.2-x025'}, 'options', 'A'],
    ['items', {'id': '9702-5.2-x025'}, 'options', 'B'],
    ['items', {'id': '9702-5.2-x025'}, 'options', 'C'],
    ['items', {'id': '9702-5.2-x025'}, 'options', 'D'],
    # 2026-10-30: earlier fraction-glyph fixes in 9702-5.2 that had no reviewed binding (no-loss flagged them)
    ['items', {'id': '9702-5.2-p02'}, 'options', 'A'],
    ['items', {'id': '9702-5.2-x001'}, 'stem'],
    # 2026-10-30: source-verified text restoration in 9702-7.1 x017 (s20 paper 13 Q22; new intensity I/4, amplitude options)
    ['items', {'id': '9702-7.1-x017'}, 'stem'],
    ['items', {'id': '9702-7.1-x017'}, 'options', 'B'],
    ['items', {'id': '9702-7.1-x017'}, 'options', 'C'],
    ['items', {'id': '9702-7.1-x017'}, 'options', 'D'],
    # 2026-10-30: source-verified option restorations in 9702-6.1 x035 (s25 paper 11 Q23; E = 4kL/(pi d^2))
    ['items', {'id': '9702-6.1-x035'}, 'options', 'A'],
    ['items', {'id': '9702-6.1-x035'}, 'options', 'B'],
    ['items', {'id': '9702-6.1-x035'}, 'options', 'C'],
    ['items', {'id': '9702-6.1-x035'}, 'options', 'D'],
    # 2026-10-30: earlier unreviewed fraction-notation changes in 9702-6.1 x010 (s21 paper 13 Q20), now reviewed
    ['items', {'id': '9702-6.1-x010'}, 'stem'],
    ['items', {'id': '9702-6.1-x010'}, 'options', 'A'],
    ['items', {'id': '9702-6.1-x010'}, 'options', 'B'],
    ['items', {'id': '9702-6.1-x010'}, 'options', 'C'],
    ['items', {'id': '9702-6.1-x010'}, 'options', 'D'],
    # 2026-10-30: source-verified PDF symbol faults in 9702-4.1 (degree signs, theta subscripts, one-half fraction options)
    ['items', {'id': '9702-4.1-p01'}, 'stem'],
    ['items', {'id': '9702-4.1-p09'}, 'stem'],
    ['items', {'id': '9702-4.1-x007'}, 'stem'],
    ['items', {'id': '9702-4.1-x021'}, 'stem'],
    ['items', {'id': '9702-4.1-x023'}, 'stem'],
    ['items', {'id': '9702-4.1-p08'}, 'options', 'B'],
    ['items', {'id': '9702-4.1-x011'}, 'options', 'A'],
    ['items', {'id': '9702-4.1-x001'}, 'options', 'A'],
    ['items', {'id': '9702-4.1-x005'}, 'options', 'A'],
    ['items', {'id': '9702-4.1-x005'}, 'options', 'B'],
    ['items', {'id': '9702-4.1-x005'}, 'options', 'C'],
    ['items', {'id': '9702-4.1-x005'}, 'options', 'D'],
    ['items', {'id': '9702-4.1-x014'}, 'options', 'A'],
    ['items', {'id': '9702-4.1-x014'}, 'options', 'B'],
    ['items', {'id': '9702-4.1-x021'}, 'options', 'A'],
    ['items', {'id': '9702-4.1-x021'}, 'options', 'C'],
    # 2026-10-30: source-verified printed angle symbols in 9702-4.2 stems
    ['items', {'id': '9702-4.2-p01'}, 'stem'],
    ['items', {'id': '9702-4.2-p02'}, 'stem'],
    ['items', {'id': '9702-4.2-p03'}, 'stem'],
    ['items', {'id': '9702-4.2-p04'}, 'stem'],
    ['items', {'id': '9702-4.2-p05'}, 'stem'],
    ['items', {'id': '9702-4.2-p08'}, 'stem'],
    ['items', {'id': '9702-4.2-p09'}, 'stem'],
    ['items', {'id': '9702-4.2-x016'}, 'stem'],
    ['items', {'id': '9702-4.2-x030'}, 'stem'],
    ['items', {'id': '9702-4.2-x034'}, 'stem'],
    ['items', {'id': '9702-4.2-x036'}, 'stem'],
    ['items', {'id': '9702-4.2-x037'}, 'stem'],
    ['items', {'id': '9702-4.2-x040'}, 'stem'],
    ['items', {'id': '9702-4.2-x042'}, 'stem'],
    ['items', {'id': '9702-4.2-x043'}, 'stem'],
    # 2026-10-30: source-verified printed options in 9702-5.1 (x016, x043, x054, x059)
    ['items', {'id': '9702-5.1-x016'}, 'options', 'A'],
    ['items', {'id': '9702-5.1-x016'}, 'options', 'B'],
    ['items', {'id': '9702-5.1-x016'}, 'options', 'C'],
    ['items', {'id': '9702-5.1-x016'}, 'options', 'D'],
    ['items', {'id': '9702-5.1-x054'}, 'options', 'A'],
    ['items', {'id': '9702-5.1-x054'}, 'options', 'B'],
    ['items', {'id': '9702-5.1-x054'}, 'options', 'C'],
    ['items', {'id': '9702-5.1-x054'}, 'options', 'D'],
    ['items', {'id': '9702-5.1-x043'}, 'options', 'A'],
    ['items', {'id': '9702-5.1-x043'}, 'options', 'B'],
    ['items', {'id': '9702-5.1-x043'}, 'options', 'C'],
    ['items', {'id': '9702-5.1-x043'}, 'options', 'D'],
    ['items', {'id': '9702-5.1-x059'}, 'options', 'A'],
    ['items', {'id': '9702-5.1-x059'}, 'options', 'B'],
    ['items', {'id': '9702-5.1-x059'}, 'options', 'C'],
    ['items', {'id': '9702-5.1-x059'}, 'options', 'D'],
    ['items', {'id': '9702-4.1-i12'}, 'explanation'],  # 2026-10-30: explanation names options by content, not by letter
    # 2026-10-30: source-verified option fraction glyphs in 9702-6.2 p09 (s23 paper 13 Q19 prints one-half fractions A, B)
    ['items', {'id': '9702-6.2-p09'}, 'options', 'A'],
    ['items', {'id': '9702-6.2-p09'}, 'options', 'B'],
    # 2026-10-30: reviewed defects in 9702-4.3 (review haiku-review-9702-4.3-defects-1)
    ['items', {'id': '9702-4.3-x026'}, 'stem'],
    ['items', {'id': '9702-4.3-x044'}, 'stem'],
    ['items', {'id': '9702-4.3-x022'}, 'options', 'A'],
    # 2026-10-30: reviewed defects in 9702-6.2 options (x001, x016, x032 B)
    ['items', {'id': '9702-6.2-x001'}, 'options', 'A'],
    ['items', {'id': '9702-6.2-x001'}, 'options', 'B'],
    ['items', {'id': '9702-6.2-x001'}, 'options', 'C'],
    ['items', {'id': '9702-6.2-x001'}, 'options', 'D'],
    ['items', {'id': '9702-6.2-x016'}, 'options', 'B'],
    ['items', {'id': '9702-6.2-x016'}, 'options', 'C'],
    ['items', {'id': '9702-6.2-x016'}, 'options', 'D'],
    ['items', {'id': '9702-6.2-x032'}, 'options', 'B'],
    # 2026-10-30: reviewed open text defects (haiku-review-open-text-1)
    ['items', {'id': '9702-1.2-x026'}, 'options', 'A'],
    ['items', {'id': '9702-1.2-x026'}, 'options', 'B'],
    ['items', {'id': '9702-2.1-x061'}, 'stem'],
    ['items', {'id': '9702-2.1-x050'}, 'stem'],
    ['items', {'id': '9702-3.1-x046'}, 'options', 'B'],
    ['items', {'id': '9702-3.1-x046'}, 'options', 'C'],
    ['items', {'id': '9702-3.1-x046'}, 'options', 'D'],
    ['items', {'id': '9702-6.2-x017'}, 'stem'],  # 2026-10-30: printed sentences only (haiku-review-stems-b-1)
    ['items', {'id': '9702-3.2-x013'}, 'stem'],
    # 2026-10-30: reviewed triage restores in 9702-4.3 (haiku-review-9702-4.3-restore-1)
    ['items', {'id': '9702-4.3-x013'}, 'options', 'A'],
    ['items', {'id': '9702-4.3-x013'}, 'options', 'B'],
    ['items', {'id': '9702-4.3-x013'}, 'options', 'C'],
    ['items', {'id': '9702-4.3-x013'}, 'options', 'D'],
    ['items', {'id': '9702-4.3-x035'}, 'stem'],
    ['items', {'id': '9702-4.3-x045'}, 'stem'],
    ['items', {'id': '9702-4.3-x045'}, 'options', 'A'],
    ['items', {'id': '9702-4.3-x045'}, 'options', 'B'],
    ['items', {'id': '9702-4.3-x045'}, 'options', 'C'],
    ['items', {'id': '9702-3.3-x007'}, 'stem'],  # 2026-10-30: reviewed missing space v2 in (haiku-review-b-1)
    # 2026-10-30: reviewed option defects in 9702-8.4 and 9702-7.2 (haiku-review-8.4-7.2-options-1)
    ['items', {'id': '9702-8.4-x026'}, 'options', 'C'],
    ['items', {'id': '9702-8.4-x026'}, 'options', 'D'],
    ['items', {'id': '9702-8.4-x021'}, 'options', 'D'],
    ['items', {'id': '9702-7.2-x006'}, 'options', 'A'],
    ['items', {'id': '9702-7.2-x006'}, 'options', 'B'],
    ['items', {'id': '9702-7.2-x006'}, 'options', 'C'],
    ['items', {'id': '9702-7.2-x006'}, 'options', 'D'],
    # 2026-10-30: reviewed defects in 9702-7.2 and 9702-7.5 (review haiku-review-9702-7.2-7.5-defects-1)
    ['items', {'id': '9702-7.2-x006'}, 'stem'],
    ['items', {'id': '9702-7.2-x016'}, 'options', 'C'],
    ['items', {'id': '9702-7.2-x016'}, 'options', 'D'],
    ['items', {'id': '9702-7.5-p03'}, 'stem'],
    ['items', {'id': '9702-7.5-p04'}, 'stem'],
    ['items', {'id': '9702-7.5-p05'}, 'stem'],
    ['items', {'id': '9702-7.5-p06'}, 'stem'],
    ['items', {'id': '9702-7.5-p06'}, 'explanation'],
    ['items', {'id': '9702-7.5-x005'}, 'stem'],
    # 2026-10-30: reviewed control-character defects in 9702-8.1 and 9702-8.4 (review haiku-review-9702-8.1-8.4-defects-1)
    ['items', {'id': '9702-8.1-x035'}, 'options', 'A'],
    ['items', {'id': '9702-8.1-x035'}, 'options', 'B'],
    ['items', {'id': '9702-8.1-x035'}, 'options', 'C'],
    ['items', {'id': '9702-8.1-x035'}, 'options', 'D'],
    ['items', {'id': '9702-8.4-p03'}, 'stem'],
    ['items', {'id': '9702-8.4-p04'}, 'stem'],
    ['items', {'id': '9702-8.4-p07'}, 'stem'],
    ['items', {'id': '9702-8.4-p12'}, 'stem'],
    ['items', {'id': '9702-8.4-x021'}, 'stem'],
    ['items', {'id': '9702-8.4-x022'}, 'stem'],
    ['items', {'id': '9702-8.4-x024'}, 'stem'],
    ['items', {'id': '9702-8.4-x026'}, 'stem'],
)


# Whole-options restorations: only for items whose stored options are null, and only for ids listed here.
# Each id needs a source-page reading and an independent review before it is bound. Empty means none approved.
APPROVED_WHOLE_OPTIONS = (
    ['items', {'id': '9702-5.2-x021'}, 'options'],
    ['items', {'id': '9702-6.1-x025'}, 'options'],
)


def _json_equal(left, right) -> bool:
    """Compare JSON values without treating booleans, integers and floats as equal."""
    return json.dumps(left, sort_keys=True, ensure_ascii=False, allow_nan=False) == json.dumps(
        right, sort_keys=True, ensure_ascii=False, allow_nan=False)


def _standalone_prose(note: str, addition: str) -> bool:
    """Find a standalone line outside common Markdown and Obsidian hidden blocks.

    This is not a general Markdown renderer or proof of visual placement.
    """
    fence = None
    comment = False
    obsidian_comment = False
    html_block = None
    for line in note.splitlines():
        match = re.match(r'^ {0,3}(`{3,}|~{3,})(.*)$', line)
        if not comment and not obsidian_comment and not html_block and match:
            marker, suffix = match.groups()
            if fence is None:
                fence = (marker[0], len(marker))
            elif marker[0] == fence[0] and len(marker) >= fence[1] and not suffix.strip():
                fence = None
            continue
        if fence:
            continue
        if not comment and not obsidian_comment and not html_block and line.rstrip() in (
                addition, ' ' + addition, '  ' + addition, '   ' + addition):
            return True
        if not comment and not html_block and line.count('%%') % 2:
            obsidian_comment = not obsidian_comment
        if not comment and not obsidian_comment:
            for tag in re.finditer(r'<\s*(/?)\s*(script|style)\b[^>]*>', line, re.I):
                closing, name = tag.group(1), tag.group(2).lower()
                if not closing and html_block is None:
                    html_block = name
                elif closing and html_block == name:
                    html_block = None
        pos = 0
        while pos < len(line):
            marker = '-->' if comment else '<!--'
            found = line.find(marker, pos)
            if found < 0:
                break
            comment = not comment
            pos = found + len(marker)
    return False


def _read_source(root: Path, relative: str) -> bytes:
    """Read a bounded regular file beneath root without following path symlinks."""
    path = Path(relative)
    if path.is_absolute() or not path.parts or any(part in ('..', '.') for part in path.parts):
        raise ValueError('source is outside project root')
    repository = Path(__file__).resolve().parents[1]
    vault = Path(os.environ.get('STEM_TUTOR_VAULT') or repository.parent / 'STEM Tutor')
    if root.resolve() == repository or (vault / 'Library/catalog.json').exists() or relative.startswith('Library/'):
        sys.path.insert(0, str(repository / 'src'))
        from tutorlib.asset_library import AssetLibrary
        return AssetLibrary(vault).read(relative, max_bytes=MAX_SOURCE_BYTES)
    descriptors = []
    try:
        parent = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
        descriptors.append(parent)
        for part in path.parts[:-1]:
            parent = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
            descriptors.append(parent)
        fd = os.open(path.parts[-1], os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW, dir_fd=parent)
        descriptors.append(fd)
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            raise ValueError('source must be a regular file')
        if info.st_size > MAX_SOURCE_BYTES:
            raise ValueError('source exceeds size limit')
        with os.fdopen(os.dup(fd), 'rb') as stream:
            data = stream.read(MAX_SOURCE_BYTES + 1)
        if len(data) > MAX_SOURCE_BYTES:
            raise ValueError('source exceeds size limit')
        return data
    finally:
        for fd in reversed(descriptors):
            os.close(fd)


def source_fingerprints(proposal: dict, root: Path) -> list[dict]:
    """Identify referenced PDF bytes and valid page numbers, without judging their relevance."""
    import pymupdf
    sources = proposal.get('evidence') if isinstance(proposal, dict) else None
    if not isinstance(sources, list) or not sources:
        raise ValueError('missing source evidence')
    root = Path(root).resolve()
    result = []
    for source in sources:
        if (not isinstance(source, dict) or not isinstance(source.get('source'), str)
                or not source['source'].strip() or type(source.get('pdf_page')) is not int
                or source['pdf_page'] < 1):
            raise ValueError('invalid source reference')
        try:
            data = _read_source(root, source['source'])
            with pymupdf.open(stream=data, filetype='pdf') as document:
                if document.needs_pass or source['pdf_page'] > document.page_count:
                    raise ValueError('source page is unavailable')
        except (OSError, RuntimeError) as exc:
            raise ValueError('source PDF is unavailable') from exc
        result.append({'source': source['source'], 'pdf_page': source['pdf_page'],
                       'sha256': hashlib.sha256(data).hexdigest()})
    return result


def verify_source_fingerprints(proposal: dict, root: Path, expected: list[dict]) -> list[str]:
    try:
        actual = source_fingerprints(proposal, root)
    except (ValueError, ImportError) as exc:
        return [f'source evidence unavailable: {exc}']
    return [] if actual == expected else ['source evidence changed since review']


def validate_manifest(proposal: dict) -> list[str]:
    """Check a correction proposal's shape; this does not approve its content."""
    if not isinstance(proposal, dict):
        return ['invalid correction proposal']
    corrections = proposal.get('corrections', [])
    structured = proposal.get('structured_corrections', [])
    notes = proposal.get('note_corrections', [])
    restorations = proposal.get('option_restorations', [])
    sources = proposal.get('evidence')
    if (not isinstance(corrections, list) or not isinstance(structured, list) or not isinstance(notes, list)
            or not isinstance(restorations, list)
            or not (corrections or structured or notes or restorations)
            or not isinstance(sources, list) or not sources or any(not isinstance(s, dict)
            or not isinstance(s.get('source'), str) or not s['source'].strip()
            or type(s.get('pdf_page')) is not int or s['pdf_page'] < 1 for s in sources)):
        return ['missing corrections or source evidence']
    issues, seen, old_notes = [], set(), []
    if 'note_addition' in proposal:
        addition = proposal['note_addition']
        if (not isinstance(addition, str) or not addition.strip() or '\n' in addition or '\r' in addition
                or any(token in addition for token in ('![[', '```', '<!--'))):
            issues.append('unsafe note addition')
    for change in corrections:
        if not isinstance(change, dict):
            issues.append('invalid correction'); continue
        path = change.get('selector')
        valid_id = lambda x: isinstance(x, dict) and set(x) == {'id'} and isinstance(x['id'], str) and bool(x['id'])
        safe = (path == ['outline'] or any(path == approved for approved in APPROVED_ITEM_SELECTORS)
                or isinstance(path, list) and (
            len(path) == 3 and valid_id(path[1])
            and (path[0], path[2]) in (('misconceptions', 'refutation'), ('flashcards', 'back')) or
            len(path) == 3 and path[0] == 'teach' and isinstance(path[1], str) and path[2] == 'establish' or
            len(path) == 4 and path[0] == 'items' and valid_id(path[1]) and path[2] == 'hints'
            and type(path[3]) is int and path[3] >= 0 or
            len(path) == 5 and path[0] == 'worked' and valid_id(path[1]) and path[2] == 'steps'
            and type(path[3]) is int and path[3] >= 0 and path[4] == 'why'))
        if not safe:
            issues.append('unsafe correction selector'); continue
        key = json.dumps(path, sort_keys=True)
        if key in seen:
            issues.append('duplicate correction selector')
        seen.add(key)
        if any(not isinstance(change.get(k), str) or not change[k].strip() for k in ('old', 'new', 'reason')):
            issues.append('incomplete correction')
        elif change['old'] == change['new']:
            issues.append('correction has no effect')
    for change in structured:
        if not isinstance(change, dict):
            issues.append('invalid structured correction'); continue
        path = change.get('selector')
        if path not in STRUCTURED_SELECTORS:
            issues.append('unsafe structured correction selector'); continue
        key = json.dumps(path, sort_keys=True)
        if key in seen:
            issues.append('duplicate correction selector')
        seen.add(key)
        if path[-1] == 'refutation':  # a string slot: non-empty old and new text
            shape_ok = (isinstance(change.get('old'), str) and bool(change['old'].strip())
                        and isinstance(change.get('new'), str) and bool(change['new'].strip()))
        elif path[-1] == 'options':  # null options: the old options must be a non-empty dict; new must be null
            shape_ok = isinstance(change.get('old'), dict) and bool(change['old']) and change.get('new') is None
        else:
            expected_type = list if path[0] == 'items' else dict
            if path[-1] == 'value':
                expected_type = (int, float)
            bad_type = [type(change.get(k)) for k in ('old', 'new')]
            shape_ok = not (any(t is bool or not issubclass(t, expected_type) for t in bad_type)
                            or not change['old'] or not change['new'])
        if (not shape_ok or _json_equal(change.get('old'), change.get('new'))
                or not isinstance(change.get('reason'), str) or not change['reason'].strip()):
            issues.append('incomplete structured correction')
    for change in notes:
        if not isinstance(change, dict) or any(not isinstance(change.get(k), str) or not change[k].strip()
                                               for k in ('old', 'new', 'reason')):
            issues.append('incomplete note correction'); continue
        old = change['old']
        if (old == change['new'] or '\n' in old or '\n' in change['new'] or '\r' in old
                or '\r' in change['new'] or any(token in old or token in change['new']
                                                 for token in ('![[', '```', '<!--'))):
            issues.append('unsafe note correction')
        if any(old in prior or prior in old for prior in old_notes):
            issues.append('overlapping note corrections')
        old_notes.append(old)
    seen_restore = set()
    for rest in restorations:
        if not isinstance(rest, dict):
            issues.append('invalid option restoration'); continue
        path = rest.get('selector')
        if path not in [list(p) for p in APPROVED_WHOLE_OPTIONS]:
            issues.append('unapproved option restoration selector'); continue
        key = json.dumps(path, sort_keys=True)
        if key in seen_restore:
            issues.append('duplicate option restoration')
        seen_restore.add(key)
        opts = rest.get('options')
        if (not isinstance(opts, dict) or set(opts) != {'A', 'B', 'C', 'D'}
                or any(not isinstance(v, str) or not v.strip() for v in opts.values())):
            issues.append('option restoration must give exactly A to D with text'); continue
        if not isinstance(rest.get('reason'), str) or not rest['reason'].strip():
            issues.append('option restoration needs a reason')
    return issues


def _replacement(value, correction):
    old, new, reason = (correction.get(k) for k in ('old', 'new', 'reason'))
    if (not all(isinstance(v, str) and v.strip() for v in (old, new, reason))
            or not isinstance(value, str) or value.count(old) != 1):
        raise ValueError('correction must match exactly once and include a reason')
    return value.replace(old, new, 1)


def stage_corrections(pack: dict, note: str, proposal: dict) -> tuple[dict, str]:
    """Produce a review candidate only. A successful stage does not approve a correction."""
    result = copy.deepcopy(pack)
    for correction in proposal.get('corrections', []):
        path = correction.get('selector')
        if not isinstance(path, list) or not path:
            raise ValueError('missing selector')
        parent = result
        try:
            for part in path[:-1]:
                if isinstance(part, dict) and isinstance(parent, list) and part:
                    matches = [row for row in parent if isinstance(row, dict)
                               and all(row.get(k) == v for k, v in part.items())]
                    if len(matches) != 1:
                        raise ValueError('selector is ambiguous or missing')
                    parent = matches[0]
                else:
                    parent = parent[part]
            leaf = path[-1]
            parent[leaf] = _replacement(parent[leaf], correction)
        except (KeyError, IndexError, TypeError) as exc:
            raise ValueError('invalid selector') from exc
    for rest in proposal.get('option_restorations', []):
        path = rest.get('selector')
        if path not in [list(p) for p in APPROVED_WHOLE_OPTIONS]:
            raise ValueError('unapproved option restoration selector')
        matches = [row for row in result.get('items', []) if row.get('id') == path[1]['id']]
        if len(matches) != 1:
            raise ValueError('option restoration item is ambiguous or missing')
        if matches[0].get('options') is not None:
            raise ValueError('option restoration only applies where the stored options are null')
        matches[0]['options'] = dict(rest['options'])
    for correction in proposal.get('note_corrections', []):
        note = _replacement(note, correction)
    for change in proposal.get('structured_corrections', []):
        path = change.get('selector')
        if path not in STRUCTURED_SELECTORS:
            raise ValueError('unsafe structured correction selector')
        try:
            holder, key = _structured_slot(result, path)
            if not _json_equal(holder[key], change['old']):
                raise ValueError('structured correction must match exactly once')
            holder[key] = copy.deepcopy(change['new'])
        except (KeyError, TypeError, IndexError) as exc:
            raise ValueError('invalid structured selector') from exc
    return result, note


def audit_corrections(pack: dict, note: str, proposal: dict, candidate: dict, candidate_note: str, compare) -> dict:
    """Report original violations and separately identify changes outside a proposal.

    This is review evidence only: neither an empty second list nor a successful
    stage approves the proposal or changes the refine gate's original snapshot.
    """
    staged_pack, staged_note = stage_corrections(pack, note, proposal)
    return {
        'against_original': compare({'pack': pack, 'note': note}, candidate, candidate_note),
        'outside_proposal': compare({'pack': staged_pack, 'note': staged_note}, candidate, candidate_note),
    }


def review_fingerprints(pack: dict, note: str, proposal: dict, candidate: dict, candidate_note: str) -> dict:
    """Bind review evidence to exact semantic JSON and note text; do not approve changes."""
    def digest(value):
        raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
        return hashlib.sha256(raw).hexdigest()
    return {'original': digest({'pack': pack, 'note': note}),
            'proposal': digest(proposal),
            'candidate': digest({'pack': candidate, 'note': candidate_note})}


def validate_review_evidence(pack: dict, note: str, proposal: dict, candidate: dict,
                             candidate_note: str, evidence: dict) -> list[str]:
    """Check an attestation matches the precise candidate; never waive the no-loss gate."""
    if not isinstance(evidence, dict):
        return ['missing correction review']
    expected = review_fingerprints(pack, note, proposal, candidate, candidate_note)
    if evidence.get('fingerprints') != expected:
        return ['stale or missing correction fingerprints']
    if (evidence.get('verdict') != 'accepted' or any(not isinstance(evidence.get(k), str)
            or not evidence[k].strip() for k in ('reviewer', 'finding'))):
        return ['incomplete or unaccepted correction review']
    return []


def assess_reviewed_candidate(pack: dict, note: str, proposal: dict, candidate: dict,
                              candidate_note: str, evidence: dict, compare) -> dict:
    """Audit exact reviewed replacements and unrelated changes without changing any snapshot or gate."""
    if problems := validate_manifest(proposal):
        raise ValueError('; '.join(problems))
    if problems := validate_review_evidence(pack, note, proposal, candidate, candidate_note, evidence):
        raise ValueError('; '.join(problems))
    # Establish that each proposed replacement actually exists in the candidate.
    for change in proposal.get('corrections', []):
        value = candidate
        try:
            for part in change['selector']:
                if isinstance(part, dict):
                    matches = [row for row in value if isinstance(row, dict)
                               and all(row.get(k) == v for k, v in part.items())]
                    if len(matches) != 1:
                        raise ValueError('candidate selector is missing or ambiguous')
                    value = matches[0]
                else:
                    value = value[part]
            if not isinstance(value, str) or value.count(change['new']) != 1:
                raise ValueError('reviewed replacement missing or ambiguous in candidate')
            if change['old'] in value.replace(change['new'], '', 1):
                raise ValueError('original text remains outside the reviewed replacement')
        except (KeyError, IndexError, TypeError) as exc:
            raise ValueError('invalid candidate selector') from exc
    for change in proposal.get('note_corrections', []):
        if candidate_note.count(change['new']) != 1:
            raise ValueError('reviewed note replacement missing or ambiguous in candidate')
        if change['old'] in candidate_note.replace(change['new'], '', 1):
            raise ValueError('original note text remains outside the reviewed replacement')
    if 'note_addition' in proposal:
        addition = proposal['note_addition']
        if addition in note or candidate_note.count(addition) != 1 or not _standalone_prose(candidate_note, addition):
            raise ValueError('reviewed note addition must be new and present exactly once')
    for change in proposal.get('structured_corrections', []):
        path = change['selector']
        try:
            holder, key = _structured_slot(candidate, path)
            if not _json_equal(holder[key], change['new']):
                raise ValueError('structured replacement missing or ambiguous in candidate')
        except (KeyError, TypeError, IndexError) as exc:
            raise ValueError('invalid structured candidate selector') from exc
    return audit_corrections(pack, note, proposal, candidate, candidate_note, compare)


def assess_source_bound_candidate(pack: dict, note: str, proposal: dict, candidate: dict,
                                  candidate_note: str, evidence: dict, compare, source_root: Path) -> dict:
    """Assess a candidate against source fingerprints recorded with its review.

    This checks consistency, not the authenticity or independence of the attestation.
    """
    expected = evidence.get('sources') if isinstance(evidence, dict) else None
    if problems := verify_source_fingerprints(proposal, source_root, expected):
        raise ValueError('; '.join(problems))
    return assess_reviewed_candidate(pack, note, proposal, candidate, candidate_note, evidence, compare)
