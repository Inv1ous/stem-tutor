"""Read-only inventory of a tutor workspace before a storage migration.

Run ``python build/workspace_audit.py --root PATH`` for JSON on stdout. An
explicit ``--report PATH`` writes an atomic report instead. No content is moved,
repaired, or removed. References describe filesystem candidates, not proof that
a lesson, source, or answer is correct.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tempfile
import unicodedata
from urllib.parse import unquote


ASSET_EXTENSIONS = {".svg", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".pdf", ".avif"}
REFERENCE_EXTENSIONS = ASSET_EXTENSIONS | {".md", ".json", ".wav", ".mp3", ".m4a", ".ogg"}
CACHE_NAMES = {".git", ".venv", "venv", "node_modules", "__pycache__", ".cache",
               ".pytest_cache", ".mypy_cache", ".ruff_cache", "caller-cache"}
WIKI_LINK = re.compile(r"!?\[\[([^\]\n]+)\]\]")
MAX_REFERENCE_BYTES = 16 * 1024 * 1024


def _key(path: str) -> str:
    return unicodedata.normalize("NFC", path).casefold()


def _error(errors: list, path: str, operation: str, exc: Exception) -> None:
    errors.append({"path": path, "operation": operation, "error": str(exc)})


def _role(path: str) -> str:
    parts = {p.casefold() for p in Path(path).parts}
    if "library" in parts or "sources" in parts:
        return "source_library" if "sources" in parts or Path(path).suffix.lower() == ".pdf" else "learning_library"
    if "assets" in parts:
        return "learning_assets"
    if ".tutor" in parts:
        return "learner_runtime"
    if any(p in parts for p in {"lessons", "my notes", "sessions", "inbox", "anki", "subjects"}):
        return "learner_content"
    if "archive" in parts or "archives" in parts or any("preserved" in p for p in parts):
        return "archive"
    if {"build", "out"} <= parts:
        return "generated_content"
    if {"build", "work"} <= parts:
        return "preparation_work"
    if Path(path).suffix.lower() in {".py", ".sh", ".js", ".ts", ".toml"} or "tests" in parts:
        return "code"
    return "other"


def _read(path: Path, binary: bool = False):
    """Refuse symlink files, including a link substituted after enumeration."""
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    if path.is_symlink():
        raise OSError("refusing symlink file")
    descriptor = os.open(path, flags)
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise OSError("not a regular file")
        return os.fdopen(descriptor, "rb" if binary else "r", **({} if binary else {"encoding": "utf-8"}))
    except BaseException:
        os.close(descriptor)
        raise


def _hash(path: Path) -> tuple[str, int]:
    with _read(path, binary=True) as stream:
        before = os.fstat(stream.fileno())
        digest = hashlib.sha256()
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
        after = os.fstat(stream.fileno())
    if (before.st_size, before.st_mtime_ns, before.st_ino) != (after.st_size, after.st_mtime_ns, after.st_ino):
        raise OSError("file changed during audit; rerun when writers are idle")
    return digest.hexdigest(), after.st_size


def _worktree_registry(git: Path, relative: str, errors: list) -> list:
    rows = []
    registry = git / "worktrees"
    if git.is_symlink() or registry.is_symlink() or not registry.is_dir():
        return rows
    try:
        for entry in sorted(registry.iterdir()):
            if entry.is_symlink() or not entry.is_dir():
                continue
            row = {"registry": f"{relative}/worktrees/{entry.name}"}
            for name in ("gitdir", "HEAD", "locked", "prunable"):
                source = entry / name
                if source.exists() or source.is_symlink():
                    try:
                        with _read(source) as stream:
                            row[name] = stream.read(4096).strip()
                    except (OSError, UnicodeError) as exc:
                        _error(errors, f"{row['registry']}/{name}", "worktree_metadata", exc)
            rows.append(row)
    except OSError as exc:
        _error(errors, relative, "worktree_registry", exc)
    return rows


def _json_refs(value, pointer=""):
    if isinstance(value, dict):
        for name, child in value.items():
            escaped = str(name).replace("~", "~0").replace("/", "~1")
            yield from _json_refs(child, f"{pointer}/{escaped}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _json_refs(child, f"{pointer}/{index}")
    elif isinstance(value, str) and len(value) <= 2048 and "\n" not in value:
        target = value.strip()
        if "://" not in target and Path(target.split("#", 1)[0]).suffix.lower() in REFERENCE_EXTENSIONS:
            yield pointer or "/", target


def _references(root: Path, files: list, errors: list) -> list:
    rows = []
    for row in files:
        path = row["path"]
        suffix = Path(path).suffix.lower()
        if row.get("sha256") is None or suffix not in {".md", ".json"}:
            continue
        if row["size"] > MAX_REFERENCE_BYTES:
            _error(errors, path, "references", ValueError("reference parsing skipped: file exceeds 16 MiB"))
            continue
        try:
            with _read(root / path, binary=True) as stream:
                raw = stream.read(MAX_REFERENCE_BYTES + 1)
            # A writer may have changed the file since its hash was recorded.
            if hashlib.sha256(raw).hexdigest() != row["sha256"]:
                raise OSError("file changed before reference parsing; rerun when writers are idle")
            content = raw.decode("utf-8-sig")
            if suffix == ".md":
                for match in WIKI_LINK.finditer(content):
                    target = match.group(1).split("|", 1)[0].split("#", 1)[0].strip()
                    if target:
                        rows.append({"source": path, "kind": "wikilink", "line": content.count("\n", 0, match.start()) + 1,
                                     "target": target})
            else:
                for pointer, target in _json_refs(json.loads(content)):
                    rows.append({"source": path, "kind": "json", "pointer": pointer, "target": target})
        except (OSError, UnicodeError, ValueError) as exc:
            _error(errors, path, "references", exc)
    return rows


def _normalise(path: Path, root: Path) -> str | None:
    """Lexical normalisation only: never resolve a reference through symlinks."""
    absolute = Path(os.path.abspath(path))
    try:
        return absolute.relative_to(root).as_posix()
    except ValueError:
        return None


def _resolve(reference: dict, root: Path, index: dict, namespaces: dict, excluded: list,
             basenames: dict) -> None:
    target = unquote(reference["target"].split("#", 1)[0])
    path = Path(target)
    if "://" in target:
        reference["status"] = "external"
        return
    candidates = []
    if path.is_absolute():
        candidates.append(path)
    else:
        candidates.extend([root / Path(reference["source"]).parent / path, root / path])
        if path.parts:
            for parent in namespaces.get(_key(path.parts[0]), []):
                candidates.append(root / parent / Path(*path.parts[1:]))
    normalised = list(dict.fromkeys(p for candidate in candidates if (p := _normalise(candidate, root)) is not None))
    if not normalised:
        reference["status"] = "outside_root"
        return
    matches = set()
    for candidate in normalised:
        for variant in (candidate, candidate + ".md") if not Path(candidate).suffix else (candidate,):
            matches.update(index.get(_key(variant), []))
    # Obsidian also supports basename-only note/asset links.
    if not matches and len(path.parts) == 1:
        for name in {_key(target), _key(target + ".md")}:
            matches.update(basenames.get(name, []))
    reference["candidates"] = sorted(matches)
    if matches:
        reference["status"] = "resolved" if len(matches) == 1 else "ambiguous"
    elif any(any(p == entry["path"] or p.startswith(entry["path"] + "/") for p in normalised) for entry in excluded):
        reference["status"] = "excluded"
    else:
        reference["status"] = "missing"


def audit_workspace(root: Path | str, report_path: Path | str | None = None) -> dict:
    """Hash regular files; list excluded trees, links, collisions, and references."""
    root = Path(os.path.abspath(root))
    if root.is_symlink() or not root.is_dir():
        raise ValueError("root must be a real directory, not a symlink")
    report_path = Path(os.path.abspath(report_path)) if report_path is not None else None
    files, links, excluded, errors, worktrees = [], [], [], [], []
    names = defaultdict(list)
    namespaces = defaultdict(list)

    def walk(directory: Path) -> None:
        try:
            entries = sorted(os.scandir(directory), key=lambda entry: entry.name)
        except OSError as exc:
            _error(errors, directory.relative_to(root).as_posix(), "list_directory", exc)
            return
        for entry in entries:
            path = Path(entry.path)
            relative = path.relative_to(root).as_posix()
            names[_key(relative)].append(relative)
            try:
                if report_path is not None and path.absolute() == report_path:
                    excluded.append({"path": relative, "reason": "audit_report"})
                    continue
                if entry.is_symlink():
                    links.append({"path": relative, "target": os.readlink(path)})
                    continue
                if entry.is_dir(follow_symlinks=False):
                    worktree_tree = path.name == ".bugfix-wt" or (path.name == "worktrees" and path.parent.name == ".claude")
                    if path.name in CACHE_NAMES or worktree_tree or (path.parent.name == ".tutor" and path.name in {"audio", "tts"}):
                        reason = "worktrees" if worktree_tree else "git_metadata" if path.name == ".git" else "cache_or_environment"
                        excluded.append({"path": relative, "reason": reason})
                        if path.name == ".git":
                            worktrees.extend(_worktree_registry(path, relative, errors))
                        if worktree_tree:
                            children = []
                            for child in sorted(path.iterdir()):
                                children.append({"path": child.relative_to(root).as_posix(), "symlink": child.is_symlink()})
                            worktrees.append({"discovered": relative, "entries": children})
                        continue
                    if path.name.casefold() in {"assets", "library"}:
                        namespaces[_key(path.name)].append(relative)
                    walk(path)
                elif entry.is_file(follow_symlinks=False):
                    if path.name == ".DS_Store" or path.suffix == ".pyc":
                        excluded.append({"path": relative, "reason": "cache_or_environment"})
                        continue
                    row = {"path": relative, "role": _role(relative), "extension": path.suffix.lower(),
                           "learning_asset": path.suffix.lower() in ASSET_EXTENSIONS}
                    try:
                        row["sha256"], row["size"] = _hash(path)
                    except OSError as exc:
                        _error(errors, relative, "hash", exc)
                    files.append(row)
                else:
                    _error(errors, relative, "inventory", ValueError("special file skipped"))
            except OSError as exc:
                _error(errors, relative, "inventory", exc)

    walk(root)
    file_index = defaultdict(list)
    basenames = defaultdict(list)
    hashes = defaultdict(list)
    for row in files:
        file_index[_key(row["path"])].append(row["path"])
        basenames[_key(Path(row["path"]).name)].append(row["path"])
        if row.get("sha256"):
            hashes[row["sha256"]].append(row)
    references = _references(root, files, errors)
    for reference in references:
        _resolve(reference, root, file_index, namespaces, excluded, basenames)
    duplicates = [{"sha256": digest, "paths": [row["path"] for row in rows], "size_each": rows[0]["size"],
                   "duplicate_bytes": rows[0]["size"] * (len(rows) - 1)}
                  for digest, rows in sorted(hashes.items()) if len(rows) > 1]
    locations = Counter(str(Path(row["path"]).parent) for row in files if row["learning_asset"])
    return {"report_kind": "workspace-audit", "schema_version": 1, "root": str(root),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "summary": {"files": len(files), "bytes_hashed": sum(row.get("size", 0) for row in files),
                        "learning_assets": sum(row["learning_asset"] for row in files), "symlinks": len(links),
                        "errors": len(errors), "roles": dict(Counter(row["role"] for row in files)),
                        "references": dict(Counter(row["status"] for row in references))},
            "files": files, "asset_locations": dict(sorted(locations.items())), "symlinks": links,
            "excluded": excluded, "worktrees": worktrees,
            "path_collisions": [paths for _, paths in sorted(names.items()) if len(paths) > 1],
            "duplicates": duplicates, "references": references, "errors": errors}


def write_report(report: dict, destination: Path | str) -> None:
    """Atomically write a report; refuse to overwrite unrelated files or links."""
    destination = Path(destination)
    if destination.is_symlink():
        raise ValueError("report destination must not be a symlink")
    if destination.exists():
        with _read(destination) as stream:
            previous = json.load(stream)
        if not isinstance(previous, dict) or previous.get("report_kind") != "workspace-audit":
            raise ValueError("report destination already contains unrelated data")
    descriptor, temporary = tempfile.mkstemp(prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(report, stream, indent=2, ensure_ascii=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--report", type=Path, help="explicit atomic JSON report destination; otherwise stdout")
    args = parser.parse_args(argv)
    try:
        report = audit_workspace(args.root, args.report)
        if args.report:
            write_report(report, args.report)
        else:
            print(json.dumps(report, indent=2, ensure_ascii=False))
        return 1 if report["errors"] else 0
    except (OSError, ValueError) as exc:
        parser.exit(2, f"workspace audit: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
