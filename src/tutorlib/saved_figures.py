"""Content-addressed snapshots for saved question figures.

Renderable snapshots are vault assets and may participate in vault sync or export.
This helper does not change question presentation or retry policy on its own.
"""
from __future__ import annotations

import hashlib
import io
import copy
import os
import re
import stat
from contextlib import contextmanager
from pathlib import Path

from .asset_library import AssetLibrary, write_asset

MAX_FIGURE_BYTES = 20 * 1024 * 1024
MAX_TOTAL_FIGURE_BYTES = 40 * 1024 * 1024
SNAPSHOT_DIRECTORY = 'Library/Shared/Snapshots'
ORIGINAL_DIRECTORY = 'Library/Shared/OriginalFigures'


def require_runtime_library(root: Path) -> None:
    """Do not create a partial catalog beside an unmigrated legacy asset tree."""
    root = Path(root)
    catalog = root / 'Library/catalog.json'
    if catalog.exists() or catalog.is_symlink():
        AssetLibrary(root)  # reject unsafe or invalid catalogs before producing bytes
        return
    legacy = root / 'Assets'
    if legacy.is_symlink() or (legacy.exists() and (not legacy.is_dir() or any(legacy.iterdir()))):
        raise ValueError('Learning library migration is required before creating new assets. Run the workspace library migration first.')


def _source_bytes(root: Path, source: str) -> bytes:
    """Read bounded bytes, resolving catalogued aliases without legacy fallback."""
    root = Path(root)
    catalog = root / 'Library/catalog.json'
    digest = None
    if catalog.exists() or catalog.is_symlink():
        record = AssetLibrary(root).record(source)
        source, digest = record['path'], record['sha256']
    with _parent(root, source) as (parent, name):
        data = _bytes(parent, name)
    if digest is not None and hashlib.sha256(data).hexdigest() != digest:
        raise ValueError('figure digest mismatch')
    return data


def _store_renderable(root: Path, data: bytes) -> dict:
    require_runtime_library(root)
    digest = hashlib.sha256(data).hexdigest()
    relative = f'{SNAPSHOT_DIRECTORY}/{digest}.png'
    write_asset(root, relative, data, metadata={'kind': 'Snapshots'})
    return {'path': relative, 'sha256': digest}


@contextmanager
def _parent(root: Path, relative: str, create: bool = False):
    path = Path(relative)
    if path.is_absolute() or not path.parts or '..' in path.parts:
        raise ValueError('invalid figure path')
    descriptors = []
    try:
        parent = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
        descriptors.append(parent)
        for part in path.parts[:-1]:
            if create:
                try:
                    os.mkdir(part, mode=0o700, dir_fd=parent)
                    os.fsync(parent)
                except FileExistsError:
                    pass
            parent = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
            descriptors.append(parent)
        yield parent, path.parts[-1]
    finally:
        for fd in reversed(descriptors):
            os.close(fd)


def _bytes(parent: int, name: str) -> bytes:
    fd = os.open(name, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW, dir_fd=parent)
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode):
            raise ValueError('figure must be a regular file')
        data = stream.read(MAX_FIGURE_BYTES + 1)
        after = os.fstat(stream.fileno())
        fields = ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns')
        if any(getattr(before, key) != getattr(after, key) for key in fields):
            raise ValueError('figure changed while reading')
    if len(data) > MAX_FIGURE_BYTES:
        raise ValueError('figure too large')
    return data


def capture(root: Path, source: str) -> dict:
    root = Path(root)
    data = _source_bytes(root, source)
    require_runtime_library(root)
    digest = hashlib.sha256(data).hexdigest()
    relative = f'{ORIGINAL_DIRECTORY}/{digest}.bin'
    write_asset(root, relative, data, metadata={'kind': 'OriginalFigures'})
    return {'path': relative, 'sha256': digest}


def _validated_png(root: Path, source: str) -> bytes:
    try:
        from PIL import Image
    except ImportError as exc:
        raise ValueError('PNG validation is unavailable') from exc
    try:
        data = _source_bytes(root, source)
        with Image.open(io.BytesIO(data)) as image:
            if (image.format != 'PNG' or image.width * image.height > 40_000_000
                    or getattr(image, 'n_frames', 1) != 1):
                raise ValueError('unsupported figure format or size')
            image.load()
    except (OSError, Image.DecompressionBombError) as exc:
        raise ValueError('invalid or unsupported PNG figure') from exc
    return data


def capture_renderable(root: Path, source: str) -> dict:
    """Capture a decoded, bounded PNG with a renderable extension; not yet used by presentation."""
    return _store_renderable(Path(root), _validated_png(root, source))


def read_renderable(root: Path, snapshot: dict) -> bytes:
    digest = snapshot.get('sha256') if isinstance(snapshot, dict) else None
    if not isinstance(digest, str) or not re.fullmatch(r'[0-9a-f]{64}', digest):
        raise ValueError('invalid figure digest')
    if snapshot.get('path') not in (f'Assets/tutor-snapshots/{digest}.png', f'{SNAPSHOT_DIRECTORY}/{digest}.png'):
        raise ValueError('invalid snapshot path')
    data = _source_bytes(Path(root), snapshot['path'])
    if hashlib.sha256(data).hexdigest() != digest:
        raise ValueError('figure digest mismatch')
    return data


def capture_pages(root: Path, sources: list[str]) -> list[dict]:
    """Capture all pages in display order, or return no page list on failure."""
    if (not isinstance(sources, list) or not 1 <= len(sources) <= 32
            or any(not isinstance(source, str) or not source for source in sources)):
        raise ValueError('invalid figure page list')
    pages = []
    total = 0
    for source in sources:
        data = _validated_png(root, source)
        total += len(data)
        if total > MAX_TOTAL_FIGURE_BYTES:
            raise ValueError('figure pages too large')
        pages.append(data)
    return [_store_renderable(Path(root), data) for data in pages]


def prepare_question(root: Path, question: dict) -> dict:
    """Return a question copy referring to captured pages; does not present or persist it."""
    if not isinstance(question, dict) or '_figure_snapshots' in question:
        raise ValueError('invalid question figure state')
    primary = question.get('image')
    if primary is not None and (not isinstance(primary, str) or not primary):
        raise ValueError('invalid primary figure')
    if 'images' in question and (not isinstance(question['images'], list)
            or any(not isinstance(path, str) or not path for path in question['images'])):
        raise ValueError('invalid figure page list')
    images = question.get('images') or ([primary] if primary else [])
    if not images:
        return copy.deepcopy(question)
    if primary and (not isinstance(images, list) or images[0] != primary):
        raise ValueError('primary figure differs from first page')
    snapshots = capture_pages(root, images)
    prepared = copy.deepcopy(question)
    prepared['images'] = [entry['path'] for entry in snapshots]
    prepared['image'] = prepared['images'][0]
    prepared['_figure_snapshots'] = snapshots
    return prepared


def verify_question(root: Path, question: dict) -> list[bytes]:
    """Read pinned pages in order, refusing missing or mismatched figure metadata."""
    if not isinstance(question, dict):
        raise ValueError('invalid question figure state')
    primary, images, snapshots = question.get('image'), question.get('images'), question.get('_figure_snapshots')
    if primary is None and images in (None, []) and snapshots is None:
        return []
    if (not isinstance(images, list) or not 1 <= len(images) <= 32
            or not isinstance(snapshots, list) or len(snapshots) != len(images)
            or primary != images[0]
            or any(not isinstance(entry, dict) or entry.get('path') != image
                   for entry, image in zip(snapshots, images))):
        raise ValueError('missing or mismatched figure snapshots')
    try:
        pages, total = [], 0
        for entry in snapshots:
            page = read_renderable(root, entry)
            total += len(page)
            if total > MAX_TOTAL_FIGURE_BYTES:
                raise ValueError('figure pages too large')
            pages.append(page)
        return pages
    except OSError as exc:
        raise ValueError('saved figure unavailable') from exc


def read(root: Path, snapshot: dict) -> bytes:
    digest = snapshot.get('sha256') if isinstance(snapshot, dict) else None
    if not isinstance(digest, str) or not re.fullmatch(r'[0-9a-f]{64}', digest):
        raise ValueError('invalid figure digest')
    path = snapshot.get('path')
    if path not in (f'.tutor/state/saved-figures/{digest}', f'{ORIGINAL_DIRECTORY}/{digest}.bin'):
        raise ValueError('invalid snapshot path')
    if path.startswith('Library/'):
        AssetLibrary(root)  # new canonical snapshots require their catalog
        data = _source_bytes(Path(root), path)
    else:
        with _parent(Path(root), path) as (parent, name):
            data = _bytes(parent, name)
    if hashlib.sha256(data).hexdigest() != digest:
        raise ValueError('figure digest mismatch')
    return data
