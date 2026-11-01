"""Plan and copy known learning resources into the shared learner Library.

Expand-only: originals and learner records remain untouched. Planning includes
source provenance and known generated notes/questions, never arbitrary work JSON.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import uuid
import sys

from plan import UNIT

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from tutorlib.asset_library import AssetLibrary, asset_path_key, catalog_writer_lock, validate_catalog

MEDIA = {'.pdf', '.svg', '.png', '.jpg', '.jpeg', '.webp', '.gif', '.ttf', '.otf', '.woff', '.woff2'}
EXCLUDED_DIRECTORIES = {'.git', '.venv', 'venv', 'node_modules', '__pycache__', '.pytest_cache',
                        '.mypy_cache', '.ruff_cache', '.cache', 'worktrees', '.bugfix-wt'}
MIGRATION_MARKER = ("# Storage migrated\n\nAuthoritative resources now live in `STEM Tutor/Library`, organized by course and resource type. "
                    "Use the Library catalog to resolve historical paths. This directory is a compatibility marker, not an asset store. "
                    "Originals are preserved in the workspace Archive.\n").encode()


def _parts(relative):
    if (not isinstance(relative, str) or not relative or relative.startswith('/')
            or '\\' in relative or '\x00' in relative
            or any(p in ('', '.', '..') for p in relative.split('/'))):
        raise ValueError('unsafe relative path')
    return relative.split('/')


@contextmanager
def _directory(root, parts, create=False):
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
                except FileExistsError:
                    pass
            directory = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
            descriptors.append(directory)
        yield directory
    except OSError as exc:
        raise ValueError('unsafe or unavailable directory') from exc
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)


def _read(root, relative, optional=False):
    parts = _parts(relative)
    with _directory(root, parts[:-1]) as directory:
        try:
            descriptor = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
        except FileNotFoundError:
            if optional:
                return None
            raise ValueError(f'missing file: {relative}') from None
        except OSError as exc:
            raise ValueError(f'unsafe file: {relative}') from exc
        with os.fdopen(descriptor, 'rb') as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                raise ValueError(f'not a regular file: {relative}')
            return stream.read()


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _write(root, relative, data, replace=False):
    """Anchor all parents by descriptor; immutable files never overwrite."""
    parts = _parts(relative)
    with _directory(root, parts[:-1], create=True) as directory:
        temporary = '.migration-' + uuid.uuid4().hex
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644, dir_fd=directory)
        try:
            with os.fdopen(descriptor, 'wb') as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            if replace:
                os.replace(temporary, parts[-1], src_dir_fd=directory, dst_dir_fd=directory)
            else:
                try:
                    os.link(temporary, parts[-1], src_dir_fd=directory, dst_dir_fd=directory, follow_symlinks=False)
                except FileExistsError:
                    if _read(root, relative) != data:
                        raise ValueError(f'destination conflict: {relative}') from None
            os.fsync(directory)
        finally:
            try:
                os.unlink(temporary, dir_fd=directory)
            except FileNotFoundError:
                pass


def atomic_json(path: Path, data: dict) -> None:
    path = Path(os.path.abspath(path))
    path = path.parent.resolve() / path.name
    _write(Path(path.anchor), path.relative_to(path.anchor).as_posix(),
           (json.dumps(data, ensure_ascii=False, indent=2) + '\n').encode(), replace=True)


def _course(relative):
    # Source codes YMA01/XMA01 are not unique course IDs. Folder descriptions
    # identify their units, as shown in the existing SaveMyExams library.
    lowered = relative.lower()
    for label, prefix in [('further-pure', 'FP'), ('pure', 'P'), ('statistics', 'S'),
                          ('mechanics', 'M'), ('decision', 'D')]:
        found = re.search(r'(?<![a-z-])' + label + r'[- ]([1-4])\b', lowered)
        if found:
            return prefix + found[1]
    found = re.search(r'(?<![A-Za-z0-9])(9701|9702|FP[1-3]|[PSMD][1-4])(?![A-Za-z0-9])', relative)
    if found:
        return found[1]
    for official, course in UNIT.items():
        if re.search(r'(?<![A-Za-z0-9])' + official + r'(?!\d)', relative):
            return course
    return None


def _validate_catalog(catalog):
    validate_catalog(catalog)


def _migrated_work_adapter(workspace: Path, source: Path) -> bool:
    """Recognize exact post-migration work links without reading through them.

    Their existing resources are catalogued; future candidates go through the
    publisher. Arbitrary symlink inputs remain invalid migration sources.
    """
    for old, new in (
        ('build/out', 'Work/Candidates'), ('build/work', 'Work/Preparation'),
        ('foundry/state', 'Work/Workers/Foundry/state'),
        ('foundry/logs', 'Work/Workers/Foundry/logs'),
        ('refine/state', 'Work/Workers/Refine/state'),
        ('refine/logs', 'Work/Workers/Refine/logs'),
    ):
        adapter = workspace / 'stem-tutor' / old
        destination = workspace / new
        if not source.is_relative_to(adapter) or not adapter.is_symlink():
            continue
        try:
            if adapter.resolve(strict=True) != destination:
                return False
            with _directory(workspace, _parts(new)):
                return True
        except (OSError, ValueError, RuntimeError):
            return False
    return False


def plan(workspace: Path) -> dict:
    workspace = workspace.resolve(strict=True)
    vault = workspace / 'STEM Tutor'
    repository = workspace / 'stem-tutor'
    sources = [
        (vault / 'Assets', 'Assets', 'media', MEDIA | {'.json'}),
        (vault / 'Papers', 'Papers', 'Sources/PastPapers', None),
        (repository / 'build/out/assets', 'build/out/assets', 'media', MEDIA | {'.json'}),
        (repository / 'build/out/Assets', 'build/out/Assets', 'media', MEDIA | {'.json'}),
        (repository / 'sources/library', 'sources/library', 'Sources/Library', None),
        (repository / 'sources/papers', 'sources/papers', 'Sources/PastPapers', None),
        (repository / 'sources/specs', 'sources/specs', 'Sources/Specifications', None),
        (repository / 'app/tutor_app/fonts', 'app/tutor_app/fonts', 'Fonts', MEDIA),
        (repository / 'build/out/notes', 'build/out/notes', 'Notes', {'.md'}),
        (repository / 'build/out/packs', 'build/out/packs', 'Questions/Packs', {'.json'}),
        (repository / 'build/out/specs', 'build/out/specs', 'Notes/CourseGraph', {'.json'}),
        (repository / 'build/out/topicals', 'build/out/topicals', 'Questions/Topicals', MEDIA | {'.json'}),
        (repository / 'build/out/shortcuts', 'build/out/shortcuts', 'Shortcuts', {'.json', '.md', '.txt'}),
        (repository / 'sources/shortcuts', 'sources/shortcuts', 'Sources/Shortcuts', {'.json', '.md', '.txt'}),
        (vault / '.tutor/shortcuts/course', '.tutor/shortcuts/course', 'Shortcuts', {'.json', '.md', '.txt'}),
        # Discover retained screenshots and test media after primary learning
        # roots, so existing catalog identities and aliases remain unchanged.
        (repository, '', 'ReviewEvidence', MEDIA | {'.json'}),
    ]
    entries, errors, destinations, origins, excluded = {}, [], {}, {}, []
    adapters = set()
    catalog = None
    if (vault / 'Library/catalog.json').exists():
        try:
            catalog = AssetLibrary(vault)
        except (OSError, ValueError) as exc:
            errors.append({'source': str(vault / 'Library/catalog.json'), 'error': str(exc)})
    for source_root, alias_root, kind, extensions in sources:
        if not source_root.exists() and not source_root.is_symlink():
            continue
        if catalog is not None and _migrated_work_adapter(workspace, source_root):
            excluded.append({'source': str(source_root), 'reason': 'migrated_work_directory_adapter'})
            continue
        try:
            with _directory(workspace, _parts(source_root.relative_to(workspace).as_posix())):
                pass
        except ValueError as exc:
            errors.append({'source': str(source_root), 'error': str(exc)})
            continue
        for directory, dirs, filenames in os.walk(source_root, followlinks=False):
            generic = kind == 'ReviewEvidence'
            dirs[:] = [name for name in dirs if name not in EXCLUDED_DIRECTORIES
                       and (generic or not name.startswith('.'))]
            for name in dirs:
                path = Path(directory) / name
                if path.is_symlink():
                    if generic and catalog is not None and _migrated_work_adapter(workspace, path):
                        excluded.append({'source': str(path), 'reason': 'migrated_work_directory_adapter'})
                    elif generic and path.resolve().is_relative_to(repository.resolve()):
                        excluded.append({'source': str(path), 'reason': 'internal directory alias; physical target scanned separately'})
                    else:
                        errors.append({'source': str(path), 'error': 'symlink source directory'})
            dirs[:] = sorted(d for d in dirs if not (Path(directory) / d).is_symlink())
            for filename in sorted(filenames):
                source = Path(directory) / filename
                if filename.startswith('.') or (extensions is not None and source.suffix.lower() not in extensions):
                    continue
                if kind == 'Questions/Packs' and filename == 'HOLD.json':
                    continue
                if kind == 'Questions/Topicals' and filename == 'report.json':
                    continue
                if generic and source.suffix.lower() == '.json' and Path(filename[:-5]).suffix.lower() not in MEDIA:
                    continue  # only provenance sidecars, never arbitrary test/work JSON
                relative = source.relative_to(source_root).as_posix()
                origin = source.relative_to(workspace).as_posix()
                alias = alias_root + '/' + relative if alias_root else relative
                if origin in origins or origin in adapters:
                    continue
                if source.is_symlink():
                    try:
                        if catalog is None:
                            raise ValueError('symlink source has no catalog')
                        record = catalog.record(alias)
                        if alias not in record.get('aliases', []) and alias != record['path']:
                            raise ValueError('symlink alias is not recorded exactly')
                        target = catalog.resolve(alias)  # verify canonical bytes, never the legacy link
                        if source.resolve(strict=True) != target:
                            raise ValueError('symlink target does not match catalog')
                        excluded.append({'source': str(source), 'reason': 'already_library_adapter',
                                         'alias': alias, 'canonical': record['path']})
                        adapters.add(origin)
                    except (OSError, ValueError, RuntimeError) as exc:
                        errors.append({'source': str(source), 'error': str(exc)})
                    continue
                if catalog is not None and filename == 'README.md' and kind.startswith('Sources/'):
                    try:
                        is_marker = _read(workspace, origin) == MIGRATION_MARKER
                    except (OSError, ValueError) as exc:
                        errors.append({'source': str(source), 'error': str(exc)})
                        continue
                    if is_marker:
                        excluded.append({'source': str(source), 'reason': 'retired_storage_marker'})
                        continue
                course = _course(relative)
                target_relative = relative
                section = kind
                if kind == 'Shortcuts':
                    if relative.startswith('lessons/'):
                        section = 'Notes/Shortcuts'
                        target_relative = relative.removeprefix('lessons/')
                    else:
                        section = 'Shortcuts/Entries'
                        course = None
                if generic and (relative.startswith(('docs/', 'bugwatch/', '.superpowers/', 'tests/'))
                                or course is None):
                    course = None
                base = f'Library/Courses/{course}' if course else 'Library/Shared'
                if generic and course:
                    section = 'Questions/Media' if any(part in ('mcq', 'questions', 'topicals')
                                                       for part in source.parts) else 'Diagrams'
                if kind == 'media':
                    section = 'Questions/Media' if relative.startswith(('mcq/', 'topicals/')) else 'Diagrams'
                    if source.suffix == '.json':
                        section = 'Sources/Provenance'
                target = f'{base}/{section}/{target_relative}'
                try:
                    sha = _sha(_read(workspace, origin))
                except (ValueError, OSError) as exc:
                    errors.append({'source': str(source), 'error': str(exc)})
                    continue
                key = 'legacy-' + hashlib.sha256(origin.encode()).hexdigest()[:24]
                folded = asset_path_key(target)
                if folded in destinations:
                    existing = entries[destinations[folded]]
                    if existing['sha256'] != sha:
                        path = Path(target)
                        target = str(path.with_name(path.stem + '--' + sha + path.suffix))
                        folded = asset_path_key(target)
                    if folded in destinations:
                        existing_id = destinations[folded]
                        existing = entries[existing_id]
                        if existing['sha256'] != sha:
                            errors.append({'source': str(source), 'error': 'unresolved destination collision'})
                            continue
                        if alias not in existing['aliases']:
                            existing['aliases'].append(alias)
                        if origin not in existing['origins']:
                            existing['origins'].append(origin)
                        origins[origin] = existing_id
                        continue
                destinations[folded] = key
                entries[key] = {'path': target, 'sha256': sha, 'aliases': [alias],
                                'course': course, 'kind': section, 'origins': [origin]}
                origins[origin] = key
    for entry in entries.values():
        sidecars = [origins[origin + '.json'] for origin in entry['origins'] if origin + '.json' in origins]
        if sidecars:
            entry['provenance'] = {'sidecars': list(dict.fromkeys('asset:' + item for item in sidecars))}
    result = {'format_version': 1, 'workspace': str(workspace), 'assets': entries,
              'errors': errors, 'excluded': excluded}
    try:
        _validate_catalog(result)
        _preflight(result)
    except (ValueError, OSError) as exc:
        errors.append({'source': str(vault / 'Library/catalog.json'), 'error': str(exc)})
    return result


def _existing(workspace):
    path = workspace / 'STEM Tutor/Library'
    if not path.exists() and not path.is_symlink():
        return None
    return _read(workspace, 'STEM Tutor/Library/catalog.json', optional=True)


def _destination(workspace, relative):
    # A missing parent means no target; every existing parent must still be safe.
    parts = _parts('STEM Tutor/' + relative)
    current = workspace
    for part in parts:
        current = current / part
        try:
            info = current.lstat()
        except FileNotFoundError:
            return None
        if stat.S_ISLNK(info.st_mode):
            raise ValueError(f'symlink destination: {relative}')
    return _read(workspace, 'STEM Tutor/' + relative)


def _preflight(migration):
    workspace = Path(migration['workspace'])
    raw = _existing(workspace)
    existing = json.loads(raw) if raw is not None else {'format_version': 1, 'assets': {}}
    _validate_catalog(existing)
    merged = dict(existing['assets'])
    for identifier, entry in migration['assets'].items():
        if identifier in merged and merged[identifier] != entry:
            raise ValueError(f'catalog entry changed: {identifier}')
        for origin in entry.get('origins', []):
            if _sha(_read(workspace, origin)) != entry['sha256']:
                raise ValueError(f'source changed since planning: {origin}')
        if not entry.get('origins'):
            raise ValueError('asset has no source origin')
        target = _destination(workspace, entry['path'])
        if target is not None and _sha(target) != entry['sha256']:
            raise ValueError(f'destination conflict: {entry["path"]}')
        merged[identifier] = entry
    catalog = {**existing, 'assets': merged}
    _validate_catalog(catalog)
    return raw, catalog


def apply(migration: dict) -> dict:
    if migration['errors']:
        raise ValueError('migration has unresolved errors')
    _validate_catalog(migration)
    _preflight(migration)  # Reject invalid input before even creating the writer lock.
    workspace = Path(migration['workspace'])
    with catalog_writer_lock(workspace / 'STEM Tutor', create=True):
        before, catalog = _preflight(migration)
        copied = 0
        for entry in migration['assets'].values():
            data = _read(workspace, entry['origins'][0])
            if _sha(data) != entry['sha256']:
                raise ValueError('source changed since preflight')
            relative = 'STEM Tutor/' + entry['path']
            if _destination(workspace, entry['path']) is None:
                _write(workspace, relative, data)
                copied += 1
        if _existing(workspace) != before:
            raise ValueError('catalog changed since preflight')
        _write(workspace, 'STEM Tutor/Library/catalog.json',
               (json.dumps(catalog, ensure_ascii=False, indent=2) + '\n').encode(), replace=True)
        return {'copied': copied, 'catalog_assets': len(catalog['assets']), 'sources_deleted': 0}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    migration = plan(args.workspace)
    atomic_json(args.report, migration)
    result = apply(migration) if args.apply else {'planned': len(migration['assets']), 'errors': len(migration['errors'])}
    print(json.dumps(result))


if __name__ == '__main__':
    main()
