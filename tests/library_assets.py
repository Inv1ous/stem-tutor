"""Read real course test inputs from their canonical, digest-checked Library records.

Use ``install_course`` for integration tests: bytes are copied from the actual
Library catalog into the test's disposable vault, including the aliases needed
by that fixture's runtime pack loader. It never writes to the learner vault.
"""
from __future__ import annotations

import json
from pathlib import Path
from pathlib import PurePosixPath
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "plugin/stem-tutor/skills/tutor/scripts"))
from tutorlib.asset_library import AssetLibrary, write_asset  # noqa: E402
from tutorlib.library_refs import ASSET_FIELDS, ASSET_PREFIXES, ASSET_SUFFIXES, PROTECTED_FIELDS  # noqa: E402

REAL_VAULT = Path(__import__("os").environ.get("STEM_TUTOR_TEST_LIBRARY_VAULT", ROOT.parent / "STEM Tutor"))


def _library() -> AssetLibrary:
    """Create a fresh reader so a stale catalog cache cannot hide changed metadata."""
    return AssetLibrary(REAL_VAULT)


def _source_alias(alias: str, library: AssetLibrary | None = None) -> str:
    """Resolve content references whose only catalog record uses a build-root alias."""
    library = _library() if library is None else library
    candidates = [alias]
    if alias.startswith("Assets/"):
        candidates.extend(("build/out/Assets/" + alias.removeprefix("Assets/"),
                           "build/out/assets/" + alias.removeprefix("Assets/")))
    elif alias.startswith("assets/"):
        candidates.extend(("build/out/assets/" + alias.removeprefix("assets/"),
                           "build/out/Assets/" + alias.removeprefix("assets/")))
    elif alias.startswith("build/out/Assets/"):
        candidates.append("build/out/assets/" + alias.removeprefix("build/out/Assets/"))
    elif alias.startswith("build/out/assets/"):
        candidates.append("build/out/Assets/" + alias.removeprefix("build/out/assets/"))
    for candidate in candidates:
        try:
            library.resolve(candidate)
            return candidate
        except ValueError:
            continue
    if alias.startswith("Papers/"):
        name = PurePosixPath(alias).name
        matches = {record["path"] for record in library.records().values()
                   if PurePosixPath(record["path"]).name == name
                   or any(PurePosixPath(ref).name == name for ref in record.get("aliases", []))}
        if len(matches) == 1:
            return next(iter(matches))
        if len(matches) > 1:
            raise ValueError(f"ambiguous canonical paper asset for {alias}: {sorted(matches)}")
    # Preserve the catalog API's useful, explicit unknown-reference error.
    library.resolve(alias)
    raise AssertionError("unreachable")


def read_bytes(alias: str) -> bytes:
    """Read an alias only through the catalog and verify its SHA-256 digest."""
    library = _library()
    return library.read(_source_alias(alias, library=library))


def read_json(alias: str):
    return json.loads(read_bytes(alias))


def current_release_packs() -> list[dict]:
    """Read only the release selected by CURRENT, with one fresh catalog reader."""
    pointer = REAL_VAULT / '.tutor/packs/CURRENT'
    if pointer.is_symlink() or not pointer.is_file():
        raise ValueError('unsafe or missing CURRENT pointer')
    version = pointer.read_text().strip()
    if not re.fullmatch(r'v[1-9][0-9]*', version):
        raise ValueError('invalid CURRENT release version')
    library = _library()
    prefix = f'Library/Releases/{version}/'
    manifest = json.loads(library.read(prefix + 'manifest.json'))
    if (not isinstance(manifest, dict) or manifest.get('version') != version
            or not isinstance(manifest.get('specs'), list)
            or any(not isinstance(spec, str) or not re.fullmatch(r'[A-Za-z0-9]+', spec)
                   for spec in manifest['specs'])
            or type(manifest.get('packs')) is not int or manifest['packs'] < 1):
        raise ValueError('invalid CURRENT release manifest')
    paths = sorted(record['path'] for record in library.records().values()
                   if re.fullmatch(re.escape(prefix) + r'specs/[^/]+/packs/[^/]+\.json', record['path']))
    if (len(paths) != manifest['packs']
            or any(path.removeprefix(prefix).split('/')[1] not in manifest['specs'] for path in paths)):
        raise ValueError('CURRENT release manifest does not match registered packs')
    return [json.loads(library.read(path)) for path in paths]


def read_text(alias: str, encoding: str = "utf-8") -> str:
    return read_bytes(alias).decode(encoding)


def current_guide_text() -> str:
    """Read the active guide through its registered target, preserving historical aliases."""
    library = _library()
    target = (library.root / 'How It Works.md').resolve(strict=True)
    reference = target.relative_to(library.root).as_posix()
    return library.read(reference).decode('utf-8')


def canonical_path(alias: str) -> str:
    library = _library()
    return library.resolve(_source_alias(alias, library=library)).relative_to(REAL_VAULT.resolve()).as_posix()


def _asset_references(value, key: str = "") -> set[str]:
    if isinstance(value, dict):
        found = set()
        for child_key, child in value.items():
            if child_key not in PROTECTED_FIELDS:
                found.update(_asset_references(child, child_key))
        return found
    if isinstance(value, list):
        found = set()
        for child in value:
            found.update(_asset_references(child, key))
        return found
    if isinstance(value, str) and key in ASSET_FIELDS:
        return {value}
    return set()


def copy_to_vault(alias: str, vault_root: Path) -> Path:
    """Copy one real canonical asset to an isolated test vault without changing its bytes."""
    source = _library()
    actual_alias = _source_alias(alias, library=source)
    data = source.read(actual_alias)
    relative = source.resolve(actual_alias).relative_to(source.root).as_posix()
    record = source.record(actual_alias)
    metadata = {key: value for key, value in record.items() if key not in {"path", "sha256", "aliases"}}
    write_asset(Path(vault_root), relative, data, aliases=[alias], metadata=metadata)
    return Path(vault_root) / relative


def install_course(vault_root: Path, spec: str, subtopic: str, *, version: str = "v1") -> dict:
    """Stage a real graph, pack, and referenced media in a disposable fixture vault."""
    graph_alias = f"build/out/specs/{spec}/graph.json"
    pack_alias = f"build/out/packs/{spec}/{subtopic}.json"
    graph_data = read_bytes(graph_alias)
    pack_data = read_json(pack_alias)

    # Install referenced images into this temp vault's own catalog. The real
    # test pack and its sources remain immutable in the course Library.
    for reference in sorted(_asset_references(pack_data)):
        if (reference.startswith(ASSET_PREFIXES) or Path(reference).suffix.lower() in ASSET_SUFFIXES):
            copy_to_vault(reference, vault_root)

    # Even disposable copies of real learning content belong in Library.
    # Retain the old test setup path only as an adapter for existing pilots.
    base = Path(vault_root) / "Library/Releases" / version
    legacy = Path(vault_root) / ".tutor/packs" / version
    if legacy.is_dir() and not legacy.is_symlink():
        if base.exists():
            raise ValueError("fixture has two competing course release trees")
        base.parent.mkdir(parents=True, exist_ok=True)
        legacy.rename(base)
    else:
        base.mkdir(parents=True, exist_ok=True)
    if not legacy.exists():
        import os
        legacy.parent.mkdir(parents=True, exist_ok=True)
        legacy.symlink_to(os.path.relpath(base, legacy.parent), target_is_directory=True)

    papers_path = base / "papers.json"
    if papers_path.is_file():
        papers = json.loads(papers_path.read_text())
        for paper in papers.get("papers", []):
            for field in ("qp", "ms", "er", "gt", "ci"):
                reference = paper.get(field)
                if isinstance(reference, str):
                    copy_to_vault(reference, vault_root)

    graph_path = base / "specs" / spec / "graph.json"
    pack_path = base / "specs" / spec / "packs" / f"{subtopic}.json"
    graph_path.parent.mkdir(parents=True, exist_ok=True)
    pack_path.parent.mkdir(parents=True, exist_ok=True)
    graph_path.write_bytes(graph_data)
    pack_path.write_bytes(read_bytes(pack_alias))
    manifest_path = base / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {"version": version, "specs": []}
    manifest["version"] = version
    manifest["specs"] = sorted(set(manifest.get("specs", [])) | {spec})
    manifest_path.write_text(json.dumps(manifest))
    return pack_data


def library_directory_for(alias: str) -> Path:
    """Return the canonical parent directory of one catalogued real asset."""
    return _library().resolve(alias).parent


def library_course_diagrams(spec: str) -> Path:
    """Return the canonical catalog root expected by current foundry checks."""
    return REAL_VAULT / "Library"


def aliases_with_prefix(prefix: str) -> list[str]:
    """List catalogued aliases from the actual Library, never glob repo media."""
    found = {alias for record in _library().records().values()
             for alias in record.get("aliases", []) if alias.startswith(prefix)}
    return sorted(found)
