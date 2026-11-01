"""Editable copies of immutable Library file adapters; never retarget an alias."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import shutil


def state_paths(state_dir: Path, sub: str) -> dict:
    import json
    path = state_dir / f'{sub}.json'
    return json.loads(path.read_text()) if path.exists() else {}


def library_backed(path: Path) -> bool:
    return _library_location(path) is not None


def _library_location(path: Path):
    from tutorlib.asset_library import library_location
    return library_location(path)


def _library_reference(path: Path):
    location = _library_location(path)
    if location:
        from tutorlib.asset_library import AssetLibrary
        vault, relative = location
        return AssetLibrary(vault), relative
    return None


def verified(path: Path) -> Path:
    reference = _library_reference(path)
    if reference:
        library, relative = reference
        return library.resolve(relative)
    return path


def verified_bytes(path: Path, *, max_bytes: int | None = None) -> bytes:
    """Return the exact verified snapshot, with an optional bounded local read."""
    if max_bytes is not None and (type(max_bytes) is not int or max_bytes < 0):
        raise ValueError('invalid source size limit')
    reference = _library_reference(path)
    if reference:
        library, relative = reference
        return library.read(relative, max_bytes=max_bytes)
    with path.open('rb') as source:
        data = source.read() if max_bytes is None else source.read(max_bytes + 1)
    if max_bytes is not None and len(data) > max_bytes:
        raise ValueError('source exceeds size limit')
    return data


def prepare(data_root: Path, workflow: str, sub: str, pack: Path, note: Path, *, force=False) -> dict:
    if not (force or library_backed(pack) or library_backed(note)):
        return {}
    pack = verified(pack)
    note = verified(note) if note.is_file() else note
    base = data_root.parent if data_root.name == 'stem-tutor' else data_root
    folder = base / 'Work/Preparation' / workflow / sub / datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    folder.mkdir(parents=True, exist_ok=False)
    destination = folder / 'pack.json'
    if pack.is_file():
        shutil.copyfile(pack, destination)
    note_destination = folder / 'note.md'
    if note.is_file():
        shutil.copyfile(note, note_destination)
    return {'candidate_pack': str(destination), 'candidate_note': str(note_destination),
            'source_pack': str(pack), 'source_note': str(note)}


def prepare_teach(data_root: Path, workflow: str, sub: str, draft: Path, *, cards: dict | None = None) -> dict:
    """Seed a pass from its current pack, retaining any older draft as source evidence."""
    if cards is None and (not draft.is_file() or not library_backed(draft)):
        return {}
    base = data_root.parent if data_root.name == 'stem-tutor' else data_root
    folder = base / 'Work/Preparation' / workflow / sub / ('teach-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
    folder.mkdir(parents=True, exist_ok=False)
    destination = folder / 'teach.json'
    paths = {'candidate_teach': str(destination)}
    if draft.is_file():
        source = verified(draft)
        shutil.copyfile(source, folder / 'source-teach.json' if cards is not None else destination)
        paths['source_teach'] = str(source.resolve())
    if cards is not None:
        import json
        if not isinstance(cards, dict):
            raise ValueError('teaching cards must be an object')
        destination.write_text(json.dumps(cards, ensure_ascii=False, indent=1) + '\n')
    return paths


def writable_flags(directories: list[Path]) -> list[str]:
    """Grant only concrete authoring/output directories, never a Library shelf."""
    flags = []
    for path in dict.fromkeys(Path(path).resolve() for path in directories):
        if library_backed(path):
            raise ValueError(f'worker output directory is immutable: {path}')
        path.mkdir(parents=True, exist_ok=True)
        flags += ['--add-dir', str(path)]
    return flags


def owned_paths(repository: Path, paths) -> list[str]:
    """Checkpoint only regular files physically owned by this checkout."""
    import stat
    root = repository.resolve()
    owned = []
    for value in paths:
        path = Path(value)
        path = path if path.is_absolute() else repository / path
        if path.is_symlink() or not path.is_file():
            continue
        resolved = path.resolve()
        if not resolved.is_relative_to(root) or not stat.S_ISREG(resolved.stat().st_mode):
            continue
        owned.append(resolved.relative_to(root).as_posix())
    return list(dict.fromkeys(owned))


def checkpoint(repository: Path, paths, message: str, *, run) -> str:
    """Never commit an empty pathspec or an index left behind by a failed add."""
    paths = owned_paths(repository, paths)
    if not paths:
        return 'checkpoint retained in external Work; no repository-owned files to commit'
    git = ['git', '-C', str(repository)]
    ignored = run([*git, 'check-ignore', '-z', '--stdin'], input='\0'.join(paths),
                  capture_output=True, text=True)
    if ignored.returncode not in (0, 1):
        return f'checkpoint skipped: {ignored.stderr.strip()[-160:]}'
    paths = [path for path in paths if path not in ignored.stdout.split('\0')]
    if not paths:
        return 'checkpoint retained in Work; all repository files are ignored'
    added = run([*git, 'add', '--', *paths], capture_output=True, text=True)
    if added.returncode:
        return f'checkpoint skipped: git add failed: {added.stderr.strip()[-160:]}'
    committed = run([*git, 'commit', '-q', '-m', message, '--', *paths], capture_output=True, text=True)
    return 'committed' if committed.returncode == 0 else f'commit skipped: {(committed.stdout + committed.stderr).strip()[-160:]}'
