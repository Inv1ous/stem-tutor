"""Bounded durable-proof handoff; this module never dispatches workers or signs.

The caller must freeze the actual candidate pack, note, graph and resolved figure
files before independent dispatch, then supply a freshly resolved item inventory
at import. This is a preservation primitive, not identity authentication.
"""
from __future__ import annotations

import copy
import fcntl
import hashlib
import json
import os
from pathlib import Path
import uuid
from contextlib import contextmanager

from .candidates import library_backed


def _hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def freeze_source(paths: list[Path], items: list[dict]) -> dict:
    """Bind exact source bytes and resolved visible-content/image inventory."""
    return {'version': 1, 'files': {str(p.resolve()): _hash(p.read_bytes()) for p in paths},
            'inventory_sha256': _hash(json.dumps(items, sort_keys=True, ensure_ascii=False).encode())}


@contextmanager
def _directory(path):
    # Use directory descriptors for every mutation; reject symlink components.
    path = path.absolute()
    if '..' in path.parts or library_backed(path):
        raise ValueError('invalid evidence directory')
    fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in path.parts[1:]:
            try:
                os.mkdir(part, dir_fd=fd)
            except FileExistsError:
                pass
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        yield fd
    finally:
        os.close(fd)


def _read_at(directory, name):
    try:
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=directory)
    except FileNotFoundError:
        return None
    with os.fdopen(fd, 'rb') as stream:
        return stream.read()


def _write_at(directory, name, payload):
    fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=directory)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(payload)


def import_proof(*, binding: dict, source_paths: list[Path], items: list[dict], records: dict,
                 source_root: Path, source_work: Path, source_blind: Path,
                 target: Path, expected_target: bytes | None, root: Path, work: Path, blind: Path) -> dict:
    """Copy verified proof immutably and merge only against exact prior bytes.

    A failure can leave an unreferenced immutable archive, never an accepted
    partial merge. No workflow state, existing proof or candidate is rewritten.
    """
    import written_review
    if not isinstance(records, dict) or set(records) != {item['id'] for item in items}:
        raise ValueError('proof records must exactly match requested inventory')
    if binding != freeze_source(source_paths, items):
        raise ValueError('source changed since independent review was requested')
    if not target.resolve().is_relative_to(work.resolve()):
        raise ValueError('handoff target is outside worker evidence directory')
    problems = written_review.independent_record_problems(
        items, records, root=source_root, work=source_work, blind=source_blind)
    if problems:
        raise ValueError('; '.join(problems))
    with _directory(target.parent) as parent_fd:
        lock_fd = os.open(target.name + '.lock', os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW,
                          0o600, dir_fd=parent_fd)
        with os.fdopen(lock_fd, 'a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            return _import_locked(binding, source_paths, items, records, source_root, target,
                                  expected_target, root, work, blind, parent_fd)


def _import_locked(binding, source_paths, items, records, source_root, target,
                   expected_target, root, work, blind, parent_fd):
    import written_review
    prior = _read_at(parent_fd, target.name)
    if prior != expected_target:
        raise ValueError('review target changed; explicit merge required')
    merged = json.loads(prior) if prior is not None else {}
    if not isinstance(merged, dict):
        raise ValueError('malformed existing review records')
    # Existing accepted records are preservation boundaries: never replace
    # an incompatible binding implicitly, even with another valid review.
    for ident, record in records.items():
        if ident in merged and merged[ident] != record:
            raise ValueError('conflicting existing review record: ' + ident)
    archive_name = 'handoff-' + uuid.uuid4().hex
    os.mkdir(archive_name, 0o700, dir_fd=parent_fd)
    archive = target.parent / archive_name
    archive_fd = os.open(archive_name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent_fd)
    try:
        return _copy_locked(binding, source_paths, items, records, source_root, target,
                            root, work, blind, parent_fd, archive, archive_fd, merged, prior)
    finally:
        os.close(archive_fd)


def _copy_locked(binding, source_paths, items, records, source_root, target,
                 root, work, blind, parent_fd, archive, archive_fd, merged, prior):
    import written_review
    copied = copy.deepcopy(records)
    destinations = {}
    for record in copied.values():
        for entry in record['evidence']['files'].values():
            reference = entry['path']
            if reference not in destinations:
                original = source_root / reference
                payload = original.read_bytes()
                if _hash(payload) != entry['sha256']:
                    raise ValueError('proof changed during handoff')
                dest = archive / f'{len(destinations)}-{original.name}'
                _write_at(archive_fd, dest.name, payload)
                destinations[reference] = os.path.relpath(dest, root)
            entry['path'] = destinations[reference]
    _write_at(archive_fd, 'source-manifest.json', (json.dumps(binding, indent=1) + '\n').encode())
    merged.update(copied)
    problems = written_review.independent_record_problems(items, merged, root=root, work=work, blind=blind)
    if problems:
        raise ValueError('; '.join(problems))
    if binding != freeze_source(source_paths, items):
        raise ValueError('source changed during proof import')
    if _read_at(parent_fd, target.name) != prior:
        raise ValueError('review target changed during handoff')
    _write_at(archive_fd, 'merged.json', (json.dumps(merged, ensure_ascii=False, indent=1) + '\n').encode())
    os.replace('merged.json', target.name, src_dir_fd=archive_fd, dst_dir_fd=parent_fd)
    return merged
