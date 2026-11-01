"""Read catalogued learning assets from the vault's shared Library.

Catalog version 1 maps stable identifiers to vault-relative ``Library/...``
paths, SHA-256 digests, and optional legacy path aliases. Only catalogued
assets resolve. Call ``read`` when consuming verified bytes; ``resolve``
validates the current file and returns its canonical path for external tools.
Neither method changes the catalog or the learner's files.
"""
from __future__ import annotations

import hashlib
import copy
import json
import os
import re
import stat
import fcntl
import uuid
import threading
import unicodedata
from contextlib import contextmanager
from pathlib import Path, PurePosixPath

_REGISTRATION_LOCK = threading.RLock()


def library_location(path: Path) -> tuple[Path, str] | None:
    """Identify physical Library ownership independently of catalog availability."""
    resolved = path.resolve()
    for index, part in enumerate(resolved.parts):
        if part != 'Library':
            if part.casefold() != 'library':
                continue
            folder = Path(*resolved.parts[:index + 1])
            try:
                if not folder.samefile(folder.with_name('Library')):
                    continue
            except FileNotFoundError:
                continue
        vault = Path(*resolved.parts[:index])
        return vault, Path('Library', *resolved.parts[index + 1:]).as_posix()
    return None


def _relative(value: str, *, library: bool = False) -> str:
    if (not isinstance(value, str) or not value or "\\" in value
            or "\x00" in value or any(part in ("", ".", "..") for part in value.split("/"))
            or PurePosixPath(value).is_absolute()):
        raise ValueError("invalid vault-relative asset path")
    if library and (not value.startswith("Library/") or value == "Library/"):
        raise ValueError("asset path must be inside Library")
    return value


def asset_path_key(relative: str) -> str:
    """Compare vault paths consistently across macOS case and Unicode forms."""
    return unicodedata.normalize('NFC', _relative(relative)).casefold()


def _reference_key(reference: str) -> str:
    return reference if reference.startswith('asset:') else 'path:' + asset_path_key(reference)


def _read_regular(root: Path, relative: str, max_bytes: int | None = None) -> bytes:
    """Open each path component without following symlinks, including Library."""
    descriptors = []
    try:
        directory = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
        descriptors.append(directory)
        parts = relative.split("/")
        for part in parts[:-1]:
            directory = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
            descriptors.append(directory)
        descriptor = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
        descriptors.append(descriptor)
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode):
            raise ValueError("asset must be a regular file")
        if max_bytes is not None and info.st_size > max_bytes:
            raise ValueError('asset exceeds size limit')
        with os.fdopen(os.dup(descriptor), "rb") as source:
            data = source.read() if max_bytes is None else source.read(max_bytes + 1)
        if max_bytes is not None and len(data) > max_bytes:
            raise ValueError('asset exceeds size limit')
        return data
    except OSError as exc:
        raise ValueError(f"asset unavailable or unsafe: {relative}") from exc
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)


def _index(catalog):
    if (not isinstance(catalog, dict) or type(catalog.get("format_version")) is not int
            or catalog["format_version"] != 1 or not isinstance(catalog.get("assets"), dict)):
        raise ValueError("unsupported asset catalog format")
    assets: dict[str, tuple[str, str]] = {}
    by_reference: dict[str, str] = {}
    for identifier, entry in catalog["assets"].items():
        if (not isinstance(identifier, str)
                or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]*", identifier)):
            raise ValueError("invalid asset identifier")
        if not isinstance(entry, dict):
            raise ValueError("invalid asset record")
        path = _relative(entry.get("path"), library=True)
        digest = entry.get("sha256")
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError("invalid asset sha256")
        aliases = entry.get("aliases", [])
        if not isinstance(aliases, list):
            raise ValueError("asset aliases must be a list")
        references = [f"asset:{identifier}", path]
        for alias in aliases:
            if isinstance(alias, str) and alias.startswith('asset:'):
                raise ValueError('asset aliases must be paths, not stable identifiers')
            references.append(_relative(alias))
        assets[identifier] = (path, digest)
        for reference in references:
            key = _reference_key(reference)
            if key in by_reference and by_reference[key] != identifier:
                raise ValueError(f"ambiguous asset reference: {reference}")
            by_reference[key] = identifier
    return assets, by_reference


def validate_catalog(catalog: dict) -> None:
    """Validate catalog format and unambiguous normalized path ownership."""
    _index(catalog)


class AssetLibrary:
    """Resolve stable ``asset:<id>``, canonical paths, and declared aliases.

    The catalog is loaded once. Create a new instance after publishing a new
    catalog. Extra metadata is permitted without affecting resolution.
    """

    def __init__(self, vault_root: Path, catalog_path: str = "Library/catalog.json"):
        self.root = Path(vault_root).resolve(strict=True)
        catalog_path = _relative(catalog_path, library=True)
        try:
            catalog = json.loads(_read_regular(self.root, catalog_path))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("invalid asset catalog JSON") from exc
        self._assets, self._references = _index(catalog)
        self._catalog = catalog

    def _entry(self, reference: str) -> tuple[str, str]:
        if not isinstance(reference, str) or _reference_key(reference) not in self._references:
            raise ValueError(f"unknown asset reference: {reference}")
        return self._assets[self._references[_reference_key(reference)]]

    def read(self, reference: str, *, max_bytes: int | None = None) -> bytes:
        """Return bytes only when the catalog's digest matches the file."""
        if max_bytes is not None and (type(max_bytes) is not int or max_bytes < 0):
            raise ValueError('invalid asset byte limit')
        relative, digest = self._entry(reference)
        data = _read_regular(self.root, relative, max_bytes)
        if hashlib.sha256(data).hexdigest() != digest:
            raise ValueError(f"asset digest mismatch: {relative}")
        return data

    def resolve(self, reference: str) -> Path:
        """Validate the current bytes and return the canonical Library path."""
        self.read(reference)
        relative, _ = self._entry(reference)
        return self.root / relative

    def record(self, reference: str) -> dict:
        """Return independent metadata without exposing the loaded catalog to edits."""
        self._entry(reference)
        return copy.deepcopy(self._catalog['assets'][self._references[_reference_key(reference)]])

    def records(self) -> dict[str, dict]:
        """Return independent catalog records for browsing by course or kind."""
        return copy.deepcopy(self._catalog['assets'])


@contextmanager
def _directory(root: Path, parts: list[str], create: bool = False):
    """Keep every parent anchored, rejecting symlinks before reading or writing."""
    descriptors = []
    try:
        root = Path(os.path.abspath(root))
        directory = os.open(root.anchor, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        descriptors.append(directory)
        for part in root.parts[1:]:
            directory = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
            descriptors.append(directory)
        for part in parts:
            if create:
                try:
                    os.mkdir(part, dir_fd=directory)
                    os.fsync(directory)
                except FileExistsError:
                    pass
            directory = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
            descriptors.append(directory)
        yield directory
    except OSError as exc:
        raise ValueError('unsafe or unavailable Library directory') from exc
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)


def _read_at(directory: int, name: str, optional: bool = False) -> bytes | None:
    try:
        descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
    except FileNotFoundError:
        if optional:
            return None
        raise
    with os.fdopen(descriptor, 'rb') as source:
        if not stat.S_ISREG(os.fstat(source.fileno()).st_mode):
            raise ValueError('Library file must be regular')
        return source.read()


def _atomic_at(directory: int, name: str, data: bytes, replace: bool):
    temporary = '.asset-' + uuid.uuid4().hex
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                         0o644, dir_fd=directory)
    try:
        with os.fdopen(descriptor, 'wb') as target:
            target.write(data)
            target.flush()
            os.fsync(target.fileno())
        if replace:
            os.replace(temporary, name, src_dir_fd=directory, dst_dir_fd=directory)
        else:
            try:
                os.link(temporary, name, src_dir_fd=directory, dst_dir_fd=directory, follow_symlinks=False)
            except FileExistsError:
                if _read_at(directory, name) != data:
                    raise ValueError('asset already exists with different content') from None
        os.fsync(directory)
    finally:
        try:
            os.unlink(temporary, dir_fd=directory)
        except FileNotFoundError:
            pass


@contextmanager
def catalog_writer_lock(vault_root: Path, *, create: bool = False):
    """Serialize all catalog writers across threads and processes.

    Hold this lock from reading the current catalog through its final atomic
    replacement. The yielded directory descriptor is anchored inside Library.
    """
    with _REGISTRATION_LOCK, _directory(Path(vault_root), ['Library'], create=create) as directory:
        lock = os.open('.catalog.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600, dir_fd=directory)
        try:
            if not stat.S_ISREG(os.fstat(lock).st_mode):
                raise ValueError('catalog lock must be a regular file')
            fcntl.flock(lock, fcntl.LOCK_EX)
            yield directory
        finally:
            os.close(lock)


def register_asset(vault_root: Path, relative: str, *, aliases=(), metadata: dict | None = None) -> str:
    """Register an existing Library file under an exclusive catalog writer lock.

    Same path and digest retain their identifier and merge aliases and new
    metadata fields. Conflicting content, alias owners, or metadata fail without
    replacing the catalog. Unknown catalog fields are preserved.
    """
    relative = _relative(relative, library=True)
    aliases = [_relative(alias) for alias in aliases]
    metadata = {} if metadata is None else metadata
    if not isinstance(metadata, dict) or set(metadata) & {'path', 'sha256', 'aliases'}:
        raise ValueError('invalid asset metadata')
    root = Path(vault_root)
    parts = relative.split('/')
    with _directory(root, parts[:-1]) as directory:
        data = _read_at(directory, parts[-1])
    digest = hashlib.sha256(data).hexdigest()
    with catalog_writer_lock(root) as directory:
        raw = _read_at(directory, 'catalog.json', optional=True)
        catalog = json.loads(raw) if raw is not None else {'format_version': 1, 'assets': {}}
        _, references = _index(catalog)
        identifier = references.get(_reference_key(relative)) or 'asset-' + hashlib.sha256(relative.encode()).hexdigest()[:24]
        entry = catalog['assets'].get(identifier)
        if entry is None:
            entry = {'path': relative, 'sha256': digest, 'aliases': []}
        else:
            entry = dict(entry)
            if asset_path_key(entry['path']) != asset_path_key(relative) or entry['sha256'] != digest:
                raise ValueError('asset mapping conflicts with existing catalog')
        entry['aliases'] = list(dict.fromkeys([*entry.get('aliases', []), *aliases]))
        for key, value in metadata.items():
            if key in entry and entry[key] != value:
                raise ValueError(f'asset metadata conflict: {key}')
            entry[key] = value
        catalog['assets'][identifier] = entry
        _index(catalog)
        encoded = (json.dumps(catalog, ensure_ascii=False, indent=2) + '\n').encode()
        if encoded != raw:
            _atomic_at(directory, 'catalog.json', encoded, replace=True)
        return 'asset:' + identifier


def write_asset(vault_root: Path, relative: str, data: bytes, *, aliases=(), metadata: dict | None = None) -> str:
    """Publish immutable bytes safely, then register their canonical Library path."""
    relative = _relative(relative, library=True)
    if not isinstance(data, bytes):
        raise ValueError('asset content must be bytes')
    parts = relative.split('/')
    with _directory(Path(vault_root), parts[:-1], create=True) as directory:
        _atomic_at(directory, parts[-1], data, replace=False)
    return register_asset(vault_root, relative, aliases=aliases, metadata=metadata)


def activate_note_adapter(vault_root: Path, name: str, new_reference: str, *,
                          previous_reference: str, archive_root: Path) -> dict:
    """Activate one registered root note without publishing any other content.

    Existing catalog aliases are never reassigned. The current note must match
    the verified previous resource exactly; its original bytes and a rollback
    journal are preserved outside the vault before an atomic adapter swap.
    """
    name = _relative(name)
    if '/' in name or name.startswith('.') or Path(name).suffix.lower() != '.md':
        raise ValueError('note adapter must be a root Markdown file')
    root = Path(os.path.abspath(vault_root))
    archive = Path(os.path.abspath(archive_root))
    if archive.is_relative_to(root):
        raise ValueError('note archive must be outside the vault')
    with catalog_writer_lock(root):
        library = AssetLibrary(root)
        previous = library.read(previous_reference)
        previous_target = library.record(previous_reference)['path']
        revised = library.resolve(new_reference)
        if revised.suffix.lower() != '.md':
            raise ValueError('new note resource must be Markdown')
        target = revised.relative_to(root).as_posix()
        owner = library._references.get(_reference_key(name))
        if owner is not None and library._assets[owner][0] != target:
            raise ValueError('note adapter already has a different catalog owner')
        journal = {'adapter': name, 'previous_reference': previous_reference,
                   'new_reference': new_reference, 'target': target, 'previous_target': previous_target,
                   'previous_sha256': hashlib.sha256(previous).hexdigest(),
                   'new_sha256': library.record(new_reference)['sha256']}
        encoded = (json.dumps(journal, ensure_ascii=False, indent=2) + '\n').encode()
        with _directory(root, []) as directory:
            def snapshot():
                info = os.stat(name, dir_fd=directory, follow_symlinks=False)
                link = os.readlink(name, dir_fd=directory) if stat.S_ISLNK(info.st_mode) else None
                if link is not None:
                    matches = link == previous_target
                else:
                    matches = stat.S_ISREG(info.st_mode) and _read_at(directory, name) == previous
                if not matches:
                    raise ValueError('note adapter differs from the previous registered resource')
                return (info.st_dev, info.st_ino, info.st_mode, info.st_mtime_ns, info.st_ctime_ns, link)

            info = os.stat(name, dir_fd=directory, follow_symlinks=False)
            already_active = stat.S_ISLNK(info.st_mode) and os.readlink(name, dir_fd=directory) == target
            expected = None if already_active else snapshot()
            with _directory(Path(archive.anchor), list(archive.parts[1:]), create=True) as backup:
                _atomic_at(backup, 'original.md', previous, replace=False)
                _atomic_at(backup, 'publication.json', encoded, replace=False)
            if already_active:
                return journal
            temporary = '.note-' + uuid.uuid4().hex
            try:
                os.symlink(target, temporary, dir_fd=directory)
                # Recheck after the archival writes: never replace an edited note.
                if snapshot() != expected:
                    raise ValueError('note adapter differs from the previous registered resource')
                os.replace(temporary, name, src_dir_fd=directory, dst_dir_fd=directory)
                os.fsync(directory)
            finally:
                try:
                    os.unlink(temporary, dir_fd=directory)
                except FileNotFoundError:
                    pass
        return journal
