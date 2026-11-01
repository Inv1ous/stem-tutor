"""Publish built content into the learner's vault as an immutable Library release.

Course packs live under Library/Releases and CURRENT is flipped last, so a
Cowork session never sees a half-written version. Notes, diagrams, and papers
are registered under Library/Courses or Library/Shared; learner state/events
are not changed by content publication.

  python build/publish.py [--vault PATH]
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import shutil
import stat
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "plugin/stem-tutor/skills/tutor/scripts"))
from tutorlib import store  # noqa: E402
from tutorlib.asset_library import AssetLibrary, asset_path_key, validate_catalog, write_asset  # noqa: E402
from tutorlib.library_refs import ASSET_SUFFIXES  # noqa: E402
BUILD = ROOT / "build/out"
DEFAULT_VAULT = ROOT.parent / "STEM Tutor"  # local vault (moved out of iCloud 2026-09-29)
FOLDERS = ["Subjects", "Assets", "Sessions", "Lessons", "My Notes", "Inbox", "Inbox/Marked", "Anki", "Almanac", "Papers"]

def _course(relative: str) -> str | None:
    m = re.search(r"(?<![A-Za-z0-9])(9701|9702|P1|P2|FP[1-3]|[MSD][1-4])(?![A-Za-z0-9])", relative)
    if m:
        return m.group(1)
    return None


def _asset_target(relative: str, kind: str) -> str:
    course = _course(relative)
    base = f"Library/Courses/{course}" if course else "Library/Shared"
    return f"{base}/{kind}/{relative}"


def _catalog(vault: Path) -> tuple[dict, dict[str, str]]:
    library = vault / "Library"
    if library.is_symlink():
        raise ValueError("Library must not be a symlink")
    path = library / "catalog.json"
    if path.is_symlink():
        raise ValueError("Library catalog must not be a symlink")
    if not path.exists():
        return {"format_version": 1, "assets": {}}, {}
    if not stat.S_ISREG(path.lstat().st_mode):
        raise ValueError("Library catalog must be a regular file")
    catalog = json.loads(path.read_text(encoding="utf-8"))
    validate_catalog(catalog)
    owners = {}
    for ident, entry in catalog["assets"].items():
        for ref in [entry.get("path"), *entry.get("aliases", [])]:
            key = asset_path_key(ref) if ref else None
            if key is not None and key in owners and owners[key] != ident:
                raise ValueError(f"ambiguous Library reference: {ref}")
            if ref:
                owners[key] = ident
    return catalog, owners


def _register_data(vault: Path, owners: dict, data: bytes, target: str, alias: str | list[str],
                   kind: str, rel: str, mapping: dict[str, str], *, metadata: dict | None = None) -> str:
    digest = hashlib.sha256(data).hexdigest()
    dest = vault / target
    parent = dest.parent
    while parent != vault:
        if parent.is_symlink() or (parent.exists() and not parent.is_dir()):
            raise ValueError(f"unsafe Library path component: {parent}")
        parent = parent.parent
    # Canonical paths are immutable. A changed source with the same legacy
    # name receives a content-addressed path; old aliases remain owned.
    if dest.exists() or dest.is_symlink():
        mode = dest.lstat().st_mode
        if not stat.S_ISREG(mode):
            raise ValueError(f"immutable Library target is not a regular file: {target}")
        if hashlib.sha256(dest.read_bytes()).hexdigest() != digest:
            dest = dest.with_name(f"{dest.stem}--{digest[:12]}{dest.suffix}")
            target = dest.relative_to(vault).as_posix()
    # Never retarget an old alias to a new version.
    legacy_aliases = [alias] if isinstance(alias, str) else alias
    aliases = [ref for ref in legacy_aliases if asset_path_key(ref) not in owners]
    record_metadata = metadata if metadata is not None else {"course": _course(rel), "kind": kind}
    write_asset(vault, target, data, aliases=aliases, metadata=record_metadata)
    _, refreshed_owners = _catalog(vault)
    owners.clear(); owners.update(refreshed_owners)
    for ref in legacy_aliases:
        mapping[ref] = target
    mapping[rel] = target
    return target


def _register_file(vault: Path, owners: dict, source: Path, alias: str,
                   kind: str, rel: str, mapping: dict[str, str]) -> str:
    aliases = [alias]
    if kind == "Notes":
        aliases.extend(["Subjects/" + rel, "build/out/notes/" + rel])
    return _register_data(vault, owners, source.read_bytes(), _asset_target(rel, kind),
                          aliases, kind, rel, mapping)


def _rewrite_published(value, mapping: dict[str, str], key: str = ""):
    if isinstance(value, dict):
        return {k: _rewrite_published(v, mapping, k) for k, v in value.items()}
    if isinstance(value, list):
        return [_rewrite_published(v, mapping, key) for v in value]
    if isinstance(value, str):
        base, marker, suffix = value.partition("#")
        canonical = mapping.get(base)
        return canonical + marker + suffix if canonical else value
    return value


def _validate_pack_assets(value, vault: Path, *, location: str = "pack") -> None:
    """Reject pack image/diagram references that do not resolve to verified assets."""
    asset_fields = {"image", "images", "diagram", "diagrams"}
    library = None

    def visit(child, field: str | None = None, path: str = location) -> None:
        nonlocal library
        if isinstance(child, dict):
            for key, item in child.items():
                nested_field = key if key in asset_fields else field if field in {"diagram", "diagrams"} and key == "file" else None
                visit(item, nested_field, f"{path}.{key}")
        elif isinstance(child, list):
            for index, item in enumerate(child):
                visit(item, field, f"{path}[{index}]")
        elif field and isinstance(child, str) and child:
            reference = child.partition("#")[0]
            try:
                if library is None:
                    library = AssetLibrary(vault)
                library.resolve(reference)
            except (OSError, ValueError) as exc:
                raise ValueError(f"unresolved pack asset {child!r} at {path}: {exc}") from exc

    visit(value)


_MD_ASSET = re.compile(r"(?<!\\)(?P<open>!?\[[^\]\n]*\]\()(?P<target><[^>\n]+>|[^)\s]+)"
                       r"(?P<tail>(?:[ \t]+(?:\"[^\"\n]*\"|'[^'\n]*'))?[ \t]*\))")
_MD_CODE_SPAN = re.compile(r"(?<!\\)(?P<ticks>`+).*?(?P=ticks)(?!`)")


def _rewrite_markdown_assets(text: str, mapping: dict[str, str]) -> str:
    def rewrite_segment(segment: str) -> str:
        inline_code = []
        def protect_code(match):
            inline_code.append(match.group(0))
            return f"\x00CODE{len(inline_code)-1}\x00"
        segment = _MD_CODE_SPAN.sub(protect_code, segment)
        def replace(match):
            raw=match.group('target'); wrapped=raw.startswith('<') and raw.endswith('>')
            target=raw[1:-1] if wrapped else raw
            base, marker, suffix = target.partition('#')
            canonical=mapping.get(base)
            if not canonical: return match.group(0)
            rewritten = canonical + marker + suffix
            return match.group('open') + ('<' + rewritten + '>' if wrapped else rewritten) + match.group('tail')
        segment = _MD_ASSET.sub(replace, segment)
        def wiki(match):
            target, rest=match.group(2),match.group(3)
            base, marker, suffix=target.partition('#')
            canonical=mapping.get(base)
            return f"{match.group(1)}[[{canonical+marker+suffix+rest}]]" if canonical else match.group(0)
        segment = re.sub(r"(?<!\\)(!?)\[\[([^\]|#]+)([^\]]*)\]\]",wiki,segment)
        for index, code in enumerate(inline_code):
            segment = segment.replace(f"\x00CODE{index}\x00", code)
        return segment

    # Preserve fenced examples verbatim. CommonMark allows backticks or tildes
    # of any length and an optional info string on the opening fence.
    output, active_fence = [], None
    for line in text.splitlines(keepends=True):
        fence = re.match(r"^[ \t]{0,3}(`{3,}|~{3,})", line)
        if active_fence:
            output.append(line)
            if fence and fence.group(1)[0] == active_fence[0] and len(fence.group(1)) >= len(active_fence):
                active_fence = None
            continue
        if fence:
            active_fence = fence.group(1)
            output.append(line)
        else:
            output.append(rewrite_segment(line))
    return ''.join(output)


def _note_target(relative: str, version: str) -> str:
    """The immutable destination selected before rendering so links can target final files, including cycles."""
    course = _course(relative)
    base = f"Library/Courses/{course}/Notes/Published" if course else "Library/Shared/Notes/Published"
    return f"{base}/{version}/{relative}"


def _verified_source(path: Path) -> Path:
    """Only catalogue-verified immutable files may be read through file adapters."""
    resolved = path.resolve()
    if "Library" in resolved.parts:
        index = resolved.parts.index("Library")
        vault = Path(*resolved.parts[:index])
        return AssetLibrary(vault).resolve(resolved.relative_to(vault).as_posix())
    if path.is_symlink():
        raise ValueError(f"publication file adapter is not a Library resource: {path}")
    return path


def _publish_library(vault: Path, held_notes: set[str], version: str, *, build_root: Path | None = None,
                     note_overlay: dict[str, Path] | None = None,
                     pending_notes: list | None = None) -> tuple[dict[str, str], int]:
    """Copy this build's visible learning files to immutable catalogued Library paths."""
    build = BUILD if build_root is None else Path(build_root)
    catalog, owners = _catalog(vault)
    mapping: dict[str, str] = {}
    # A retired build directory may no longer contain media that a current
    # note still references. Seed the renderer from declared legacy asset
    # aliases so those links resolve to the existing immutable Library file.
    # AssetLibrary verifies the target bytes against the catalogue hash and
    # rejects symlinks before any reference is accepted.
    if catalog["assets"]:
        library = AssetLibrary(vault)
        for entry in catalog["assets"].values():
            canonical = entry["path"]
            media_aliases = [alias for alias in entry.get("aliases", [])
                             if Path(alias).suffix.lower() in ASSET_SUFFIXES
                             or Path(alias).suffix.lower() in {".ttf", ".otf", ".woff", ".woff2", ".eot"}]
            if media_aliases:
                # One verified read per catalogue record, even if it declares
                # several legacy spellings for the same media bytes.
                library.resolve(canonical)
                mapping.update({alias: canonical for alias in media_aliases})
    copied = 0
    roots = [
        (build / "notes", "Notes", {".md"}),
        (build / "Assets", "Diagrams", None),
        (build / "assets", "Diagrams", None),
        (build / "Papers", "PastPapers", None),
    ]
    note_sources: dict[str, Path] = {}
    note_targets: dict[str, str] = {}
    for source_root, kind, extensions in roots:
        if not source_root.exists():
            continue
        if source_root.is_symlink():
            raise ValueError(f"publication source directory is a symlink: {source_root}")
        for source in sorted(source_root.rglob("*")):
            if not source.is_file() or source.name.startswith(".DS_"):
                continue
            rel = source.relative_to(source_root).as_posix()
            verified = _verified_source(source)
            if extensions is not None and source.suffix.lower() not in extensions:
                continue
            if kind == "Notes" and rel in held_notes:
                continue
            actual_kind = kind
            if kind == "Diagrams" and source.suffix.lower() == ".json":
                actual_kind = "Sources/Provenance"
            if kind == "Notes":
                # Choose every destination up front, before rendering any note. A note may point forward or form a cycle;
                # all links must use the final per-release target rather than a raw source record which can be superseded.
                canonical = _note_target(rel, version)
                alias = source_root.name + "/" + rel
                note_sources[rel] = verified
                note_targets[rel] = canonical
                mapping[alias] = canonical
                mapping["Subjects/" + rel] = canonical
                mapping["build/out/notes/" + rel] = canonical
                copied += 1
            else:
                alias = source_root.name + "/" + rel
                canonical = _register_file(vault, owners, verified, alias, actual_kind, rel, mapping)
                if source_root.name == "Assets": mapping["assets/" + rel] = canonical
                copied += 1
    for rel, source in (note_overlay or {}).items():
        if rel in held_notes:
            raise ValueError(f"candidate note is held: {rel}")
        canonical = _note_target(rel, version)
        note_sources[rel] = source
        note_targets[rel] = canonical
        for alias in (rel, "notes/" + rel, "Subjects/" + rel, "build/out/notes/" + rel):
            mapping[alias] = canonical
    # Preserve the existing note-link matcher, then point its resolved names
    # at their Library location. Relative note structure is retained.
    by_stem: dict[str, list[str]] = {}
    for rel, canonical in note_targets.items():
        by_stem.setdefault(Path(rel).stem, []).append(canonical)
    for rel, canonical in note_targets.items():
        source = note_sources[rel]
        note_text = source.read_text(encoding="utf-8")
        note_text = fix_tags(link_notes(note_text, set(by_stem),
                                        {stem: [str(Path(path).parent) for path in paths]
                                         for stem, paths in by_stem.items()},
                                        Path(rel).parent.as_posix()))
        # Rewrite only wikilink destinations for notes, preserving labels.
        def note_link(match):
            target, tail = match.group(1), match.group(2)
            mapped = mapping.get(target)
            if mapped:
                return f"[[{mapped}{tail}]]"
            stem = target.rsplit("/", 1)[-1]
            options = by_stem.get(stem, [])
            if len(options) == 1:
                return f"[[{options[0]}{tail}]]"
            return match.group(0)
        note_text = WIKILINK.sub(note_link, note_text)
        note_text = _rewrite_markdown_assets(note_text, mapping)
        aliases = ["Subjects/" + rel, "build/out/notes/" + rel, f"rendered:{version}:{rel}"]
        data = note_text.encode()
        metadata = {"course": _course(rel), "kind": "Notes/Published"}
        if pending_notes is None:
            canonical = _register_data(vault, owners, data, canonical, aliases,
                                       "Notes/Published", rel, mapping, metadata=metadata)
        else:
            pending_notes.append((canonical, data, aliases, rel, metadata))
        mapping["Subjects/" + rel] = canonical
        mapping["build/out/notes/" + rel] = canonical
        mapping[rel] = canonical
    return mapping, copied


# Terminal opens .command files in its default profile. The app applies Study
# to this tab within its cosmetic setup budget, before restoring the saved look.
def launcher_script(vault: Path | None = None) -> str:
    """The double-click launcher. A vault other than the default is named, or the app would open the default one."""
    other = vault is not None and Path(vault).resolve() != DEFAULT_VAULT.resolve()
    return ("#!/bin/bash\n# Opens the STEM Tutor terminal app in a roomy Terminal window.\n"
            "export STEM_TUTOR_STUDY_PROFILE=1\n"
            "printf '\\e[8;46;140t'\n"
            f"exec {shlex.quote(str(ROOT / 'bin' / 'tutor'))}"
            + (f" --vault {shlex.quote(str(Path(vault).resolve()))}" if other else "")
            + "\n")


WIKILINK = re.compile(r"(?<!!)\[\[([^\]|#]+)([^\]]*)\]\]")
CHAPTER = re.compile(r"(\d+(\.\d+)?|§\d+) ")  # a link to a syllabus chapter: "5.2 Hess’s law", "4 Differentiation"


def _plain(name: str) -> str:
    return name.replace("’", "'").replace("‘", "'")


FRONT_TAGS = re.compile(r"^(tags:[ \t]*\[)([^\]\n]*)(\])", re.M)
VAULT_NOTES = {"Home", "Today", "Now", "Profile", "Mistakes", "How It Works"}  # the vault's own pages: always there


def fix_tags(text: str) -> str:
    """Obsidian rejects a tag made only of digits: `tags: [stem-tutor/lesson, 9701]` becomes `…, cie-9701]`."""
    def tag(m: re.Match) -> str:
        items = [t.strip() for t in m.group(2).split(",") if t.strip()]
        return m.group(1) + ", ".join(f"cie-{t}" if t.strip("'\"").isdigit() else t for t in items) + m.group(3)
    head, sep, rest = text.partition("\n---\n") if text.startswith("---\n") else ("", "", text)
    return FRONT_TAGS.sub(tag, head) + sep + rest if sep else text


_STOP = {"the", "and", "for", "with", "from", "that", "this", "its", "their", "into", "using"}
_UNIT = r"(?:FP\d|P\d|M\d|S\d|D\d)"
_CHAPTER = re.compile(rf"^(?:({_UNIT})\s+)?(\d+(?:\.\d+)?)\s+(.+)$")
_UNIT_ONLY = re.compile(rf"^({_UNIT})\s+(.+)$")


def _words(title: str) -> set[str]:
    """The meaningful words of a chapter title, singular: "Formulae" and "formula" meet."""
    out = set()
    for w in re.findall(r"[^\W\d_]+", title.lower()):
        w = w[:-1] if w.endswith("s") and len(w) > 3 else w
        if len(w) > 2 and w not in _STOP:
            out.add(w[:5] if len(w) > 6 else w)
    return out


def find_note(target: str, here: str, where: dict[str, list[str]]) -> str | None:
    """The published note a link meant, when its title is not the file's: "3.4 Chemical bonding" for
    "3.4 Covalent bonding and coordinate (dative covalent) bonding". Same chapter number in the same subject (the same
    unit for Maths), and a meaningful word in common: a number alone would send "12.1 transition elements" to
    "12.1 Nitrogen and sulfur". Without a number, two shared words. None unless exactly one note fits. Returns the
    note's folder-qualified name when its file name is not unique."""
    m, u = _CHAPTER.match(target), _UNIT_ONLY.match(target)
    code, number, title = (m.group(1), m.group(2), m.group(3)) if m else (u.group(1), None, u.group(2)) if u else (None, None, target)
    want, found = _words(title), []
    here_unit, here_subject = here, "/".join(here.split("/")[:2]) if here.count("/") < 2 or "Maths" not in here else "Subjects/Maths"
    for stem, dirs in where.items():
        cm = _CHAPTER.match(stem)
        if not cm:
            continue
        for d in dirs:
            unit = d.rsplit("/", 1)[-1]
            if code and not unit.startswith(code + " "):
                continue
            if not code and not (d == here_unit or ("Maths" not in d and d.startswith("/".join(here.split("/")[:2])))):
                continue
            shared = len(want & _words(cm.group(3)))
            if (number and cm.group(2) == number and shared >= 1) or (not number and shared >= 2 and shared >= 0.6 * len(want)):
                found.append((stem, d, shared))
    if len({(s, d) for s, d, _ in found}) != 1:
        return None
    stem, d, _ = found[0]
    return stem if len(where[stem]) == 1 else f"{d}/{stem}"


def link_notes(text: str, names: set[str], where: dict[str, list[str]] | None = None, here: str = "") -> str:
    """Make a note's [[links]] open what is in the vault: "Hess's law" finds "Hess’s law.md", a title the drafter
    shortened or reworded finds its chapter (`find_note`), and a link to a chapter not published yet is plain text
    until it is (clicking it would make an empty note)."""
    by_plain = {_plain(n): n for n in names}

    def fix(m: re.Match) -> str:
        target, rest = m.group(1).strip(), m.group(2)
        if target in names or "/" in target:
            return m.group(0)
        if _plain(target) in by_plain:
            return f"[[{by_plain[_plain(target)]}{rest}]]"
        if target in VAULT_NOTES or target.startswith("Assets"):
            return m.group(0)
        if where and (real := find_note(target, here, where)):  # the chapter is there under its real name: the words stay
            return f"[[{real}{rest if '|' in rest else '|' + target}]]"
        return rest.split("|", 1)[1] if "|" in rest else target  # nothing there: plain text, not an empty note on click
    return WIKILINK.sub(fix, text)


def publish(vault: Path, *, build_root: Path | None = None,
            candidate: tuple[str, Path, Path] | None = None) -> dict:
    build = BUILD if build_root is None else Path(build_root)
    pack_overlay, note_overlay = {}, {}
    if candidate:
        sub, pack_file, note_file = candidate
        pack_file, note_file = Path(pack_file), Path(note_file)
        data = json.loads(pack_file.read_text())
        if data.get("subtopic") != sub or data.get("spec", sub.split("-", 1)[0]) != sub.split("-", 1)[0]:
            raise ValueError("candidate identity does not match requested chapter")
        relative = data.get("note", "")
        if not relative or Path(relative).is_absolute() or ".." in Path(relative).parts:
            raise ValueError("candidate note path must be a safe relative path")
        if not note_file.is_file() or pack_file.is_symlink() or note_file.is_symlink():
            raise ValueError("candidate files must be regular editable files")
        pack_overlay[sub] = pack_file
        note_overlay[relative] = note_file
    vault = Path(vault).expanduser().resolve()
    missing = [n for n in ("specs", "plan.json", "notes") if not (build / n).exists()]
    if missing:  # checked before the vault is touched
        raise SystemExit(f"publish: the build has no {', '.join(missing)} in {build}; build it first")
    tutor = vault / ".tutor"
    for f in FOLDERS:
        (vault / f).mkdir(parents=True, exist_ok=True)
    cfg = tutor / "config.json"
    if not cfg.exists():
        cfg.parent.mkdir(parents=True, exist_ok=True)
        cfg.write_text(json.dumps({"tz": "Asia/Hong_Kong", "created": "2026-09-28"}, indent=1))
    packs = tutor / "packs"
    packs.mkdir(parents=True, exist_ok=True)
    releases = vault / "Library" / "Releases"
    releases.mkdir(parents=True, exist_ok=True)
    versions = sorted({int(p.name[1:]) for base in (packs, releases)
                       for p in base.glob("v*") if p.name[1:].isdigit()})
    version = f"v{(versions[-1] + 1) if versions else 1}"
    target = releases / f".{version}.tmp"  # built aside and renamed once whole, so a crash leaves no half version
    shutil.rmtree(target, ignore_errors=True)
    specs = sorted(p.name for p in (build / "specs").iterdir() if (p / "graph.json").exists())
    hold_f = build / "packs" / "HOLD.json"  # subtopics whose review is unfinished stay out of the vault
    hold = json.loads(hold_f.read_text()) if hold_f.exists() else {}
    if candidate:
        hold.pop(candidate[0], None)  # explicit reviewed overlay; preserve the on-disk hold until publisher succeeds
    # A hold may remain after its pack JSON is removed (for example while a
    # subtopic is being rebuilt). Protect its conventional note path too, so
    # the draft cannot leak through the general notes publication pass.
    held_notes = {json.loads(pk.read_text())["note"] for pk in (build / "packs").glob("*/*.json") if pk.stem in hold}
    held_note_prefixes = {(sub.split("-", 1)[0], sub.split("-", 1)[-1] + " ") for sub in hold}
    for note in (build / "notes").rglob("*.md"):
        relative = note.relative_to(build / "notes").as_posix()
        section = note.stem.split(" ", 1)[0] + " "
        if (_course(relative), section) in held_note_prefixes:
            held_notes.add(relative)
    pending_notes = []
    asset_mapping, assets_copied = _publish_library(vault, held_notes, version, build_root=build,
                                                      note_overlay=note_overlay, pending_notes=pending_notes)
    n_packs = 0
    for spec in specs:
        (target / "specs" / spec / "packs").mkdir(parents=True, exist_ok=True)
        shutil.copy2(build / "specs" / spec / "graph.json", target / "specs" / spec / "graph.json")
        for pk in sorted((build / "packs" / spec).glob("*.json")) if (build / "packs" / spec).exists() else []:
            if pk.stem in hold:
                continue
            source = _verified_source(pack_overlay.get(pk.stem, pk))
            pack_data = _rewrite_published(json.loads(source.read_text(encoding="utf-8")), asset_mapping)
            _validate_pack_assets(pack_data, vault, location=f"{pk.name}")
            store.write_text(target / "specs" / spec / "packs" / pk.name,
                             json.dumps(pack_data, ensure_ascii=False, indent=1))
            n_packs += 1
    shutil.copy2(build / "plan.json", target / "plan.json")
    papers = build / "papers.json"
    papers_data = json.loads(papers.read_text(encoding="utf-8")) if papers.exists() else {"papers": []}
    store.write_text(target / "papers.json", json.dumps(_rewrite_published(papers_data, asset_mapping), ensure_ascii=False, indent=1))
    store.write_text(target / "manifest.json", json.dumps({"version": version, "specs": specs, "packs": n_packs}, indent=1))
    os.replace(target, releases / version)
    # Notes become learner-visible Library assets only after the complete
    # release has been assembled. A failed pack copy must leave the old notes
    # in view alongside the still-active release.
    _, note_owners = _catalog(vault)
    for canonical, data, aliases, rel, metadata in pending_notes:
        _register_data(vault, note_owners, data, canonical, aliases,
                       "Notes/Published", rel, asset_mapping, metadata=metadata)
    # Register immutable release bytes before making this release active. Old
    # release records, aliases and source-bound review references remain valid.
    from tutorlib.asset_library import register_asset
    for resource in sorted((releases / version).rglob("*")):
        if resource.is_file():
            register_asset(vault, resource.relative_to(vault).as_posix(),
                           metadata={"kind": "Releases", "version": version})
    names = {f.stem for f in (build / "notes").rglob("*.md") if str(f.relative_to(build / "notes")) not in held_notes} \
        | {f.stem for f in vault.rglob("*.md")}
    where: dict[str, list[str]] = {}
    for f in (build / "notes").rglob("*.md"):
        rel = f.relative_to(build / "notes")
        if str(rel) not in held_notes:
            where.setdefault(f.stem, []).append(rel.parent.as_posix())
    copied = assets_copied
    n_shortcuts = publish_shortcuts(vault, version, build_root=build)
    install_engine(vault)
    launcher = vault / "Start Tutor.command"  # double-click in Finder to open the terminal app
    store.write_text(launcher, launcher_script(vault))
    launcher.chmod(0o755)
    # Compatibility adapter for existing readers and external scripts. The
    # release bytes themselves have one canonical location in Library.
    adapter = packs / version
    if not adapter.exists() and not adapter.is_symlink():
        adapter.symlink_to(Path("../../Library/Releases") / version, target_is_directory=True)
    store.write_text(packs / "CURRENT", version)  # flip last
    return {"version": version, "specs": len(specs), "packs": n_packs, "held": sorted(hold), "files_copied": copied,
            "shortcuts": n_shortcuts}


def install_engine(vault: Path, backup_root: Path | None = None) -> Path | None:
    """Atomically install code and preserve the previous runtime in Archive.

    This operation is independent of pack publication. It copies the canonical
    tutor scripts (including vendored dependencies), stages them beside the
    installed engine, and moves any old installation to a unique backup path.
    No prior runtime is deleted, even if installation fails.
    """
    vault = Path(vault)
    tutor = vault / ".tutor"
    tutor.mkdir(parents=True, exist_ok=True)
    engine = tutor / "engine"
    staged = tutor / f"engine.new-{uuid.uuid4().hex[:10]}"
    source = ROOT / "plugin/stem-tutor/skills/tutor/scripts"
    if not source.is_dir():
        raise FileNotFoundError(f"canonical tutor runtime is missing: {source}")
    shutil.copytree(source, staged, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    if not engine.exists() and not engine.is_symlink():
        os.replace(staged, engine)
        return None
    archive = Path(backup_root) if backup_root is not None else vault.parent / "Archive"
    try:
        archive.mkdir(parents=True, exist_ok=True)
        backup = archive / f"tutor-engine-{uuid.uuid4().hex[:10]}"
        os.replace(engine, backup)
        os.replace(staged, engine)
    except BaseException:
        if 'backup' in locals() and not engine.exists() and not engine.is_symlink() and backup.exists():
            try:
                os.replace(backup, engine)
            except OSError:
                # Keep the only old runtime copy in Archive if rollback itself
                # is blocked by a filesystem error.
                pass
        shutil.rmtree(staged, ignore_errors=True)
        raise
    return backup



def publish_shortcuts(vault: Path, version: str, *, build_root: Path | None = None) -> int:
    """Publish immutable Shortcuts assets to Library and keep the old runtime files as a compatibility adapter.

    The adapter contains copies of the exact catalogued bytes for older readers; learner settings/events/state are never
    modified. New consumers and tests resolve the Library aliases, not the mutable build tree.
    """
    src, n = (BUILD if build_root is None else Path(build_root)) / "shortcuts", 0
    if not src.is_dir():
        return 0
    _, owners = _catalog(vault)
    mapping: dict[str, str] = {}
    documents: dict[str, list[str]] = {"entries": [], "lessons": []}
    for f in sorted([*src.glob("*.json"), *src.glob("lessons/*.json")]):
        relative = f.relative_to(src).as_posix()
        area = "Lessons" if relative.startswith("lessons/") else "Entries"
        spec = f.stem
        target = (f"Library/Courses/{spec}/Notes/Shortcuts/Published/{version}/{spec}.json" if area == "Lessons"
                  else f"Library/Shared/Shortcuts/Releases/{version}/Entries/{spec}.json")
        alias = f"build/out/shortcuts/{relative}"
        metadata = {"course": spec if area == "Lessons" else None,
                    "kind": "Notes/Shortcuts" if area == "Lessons" else "Shortcuts/Entries"}
        canonical = _register_data(vault, owners, f.read_bytes(), target, [alias], f"Shortcuts/{area}",
                                   f"Shortcuts/{relative}", mapping, metadata=metadata)
        documents["lessons" if area == "Lessons" else "entries"].append(canonical)
        # Preserve the existing reader API, but source the adapter bytes from the catalogued immutable record.
        store.write_text(vault / ".tutor/shortcuts/course" / relative,
                         (vault / canonical).read_text(encoding="utf-8"))
        n += 1
    if not n:
        return 0
    # The manifest and all immutable content are durable before the active pointer moves. Readers only follow this
    # exact manifest; older and candidate records can coexist without becoming active by directory sort order.
    manifest = {"format_version": 1, "version": version,
                "entries": sorted(documents["entries"]), "lessons": sorted(documents["lessons"])}
    manifest_path = f"Library/Shared/Shortcuts/Releases/{version}/manifest.json"
    write_asset(vault, manifest_path, json.dumps(manifest, ensure_ascii=False, sort_keys=True).encode(),
                metadata={"course": None, "kind": "Shortcuts/Manifest"})
    pointer = vault / ".tutor/shortcuts/COURSE_CURRENT"
    if pointer.is_symlink() or (pointer.exists() and not stat.S_ISREG(pointer.lstat().st_mode)):
        raise ValueError("Shortcuts current pointer must be a regular file")
    store.write_text(pointer, version)
    return n


def prune_versions(packs: Path, current: str) -> None:
    """Keep the two previous versions for rollback, newest by number: v10 is newer than v9. A version without a
    manifest was never finished and is removed."""
    old = sorted((p for p in packs.glob("v*") if p.name != current and p.name[1:].isdigit()), key=lambda p: int(p.name[1:]))
    done = [p for p in old if (p / "manifest.json").exists()]
    for p in [p for p in old if p not in done] + done[:-2]:
        shutil.rmtree(p)


def vault_from(argv: list[str]) -> Path:
    """--vault PATH, else STEM_TUTOR_VAULT as the app reads it (config.vault_path), else the default vault."""
    if "--vault" in argv:
        return Path(argv[argv.index("--vault") + 1])
    return Path(os.environ.get("STEM_TUTOR_VAULT") or DEFAULT_VAULT)


if __name__ == "__main__":
    if sys.argv[-1] == "--vault":
        sys.exit("usage: python build/publish.py [--vault PATH]")
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vault", type=Path)
    parser.add_argument("--build-root", type=Path, help="explicit build/out source tree")
    parser.add_argument("--candidate", nargs=3, metavar=("SUB", "PACK", "NOTE"),
                        help="publish this reviewed candidate over its canonical chapter")
    args = parser.parse_args()
    print(json.dumps(publish(args.vault or vault_from(sys.argv), build_root=args.build_root,
                             candidate=tuple(args.candidate) if args.candidate else None)))
