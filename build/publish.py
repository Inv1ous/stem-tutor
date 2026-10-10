"""Publish built content into the learner's vault folder as a new pack version.

Writes .tutor/packs/v<N>/ (graphs, packs, plan, papers, manifest) and flips CURRENT last, so a
Cowork session never sees a half-written version. Notes, SVG diagrams and MCQ figures are copied
into the visible folders (Subjects/, Assets/). Existing learner state and events are never touched.

  python build/publish.py [--vault PATH]
"""
from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "plugin/stem-tutor/skills/tutor/scripts"))
from tutorlib import store  # noqa: E402
BUILD = ROOT / "build/out"
DEFAULT_VAULT = ROOT.parent / "STEM Tutor"  # local vault (moved out of iCloud 2026-09-29)
FOLDERS = ["Subjects", "Assets", "Sessions", "Lessons", "My Notes", "Inbox", "Inbox/Marked", "Anki", "Almanac", "Papers"]


PROFILE = "Study"  # the learner's Terminal profile for the tutor: its title bar shows the name only, its colours match

# Terminal opens a .command file in its default profile. This moves the launcher's own window (found by its tty) to
# the tutor's profile; with no such profile, or in another terminal, nothing happens.
SWITCH_PROFILE = f'''on run argv
    tell application "Terminal"
        if not (exists settings set "{PROFILE}") then return
        repeat with w in windows
            repeat with t in tabs of w
                if tty of t is (item 1 of argv) then set current settings of t to settings set "{PROFILE}"
            end repeat
        end repeat
    end tell
end run'''


def launcher_script(vault: Path | None = None) -> str:
    """The double-click launcher. A vault other than the default is named, or the app would open the default one."""
    other = vault is not None and Path(vault).resolve() != DEFAULT_VAULT.resolve()
    return ("#!/bin/bash\n# Opens the STEM Tutor terminal app in a roomy Terminal window.\n"
            '[ "$TERM_PROGRAM" = "Apple_Terminal" ] && osascript - "$(tty)" >/dev/null 2>&1 <<\'APPLESCRIPT\'\n'
            f"{SWITCH_PROFILE}\nAPPLESCRIPT\n"
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


def publish(vault: Path) -> dict:
    missing = [n for n in ("specs", "plan.json", "notes") if not (BUILD / n).exists()]
    if missing:  # checked before the vault is touched
        raise SystemExit(f"publish: the build has no {', '.join(missing)} in {BUILD}; build it first")
    tutor = vault / ".tutor"
    for f in FOLDERS:
        (vault / f).mkdir(parents=True, exist_ok=True)
    cfg = tutor / "config.json"
    if not cfg.exists():
        cfg.parent.mkdir(parents=True, exist_ok=True)
        cfg.write_text(json.dumps({"tz": "Asia/Hong_Kong", "created": "2026-09-28"}, indent=1))
    packs = tutor / "packs"
    packs.mkdir(parents=True, exist_ok=True)
    versions = sorted(int(p.name[1:]) for p in packs.glob("v*") if p.name[1:].isdigit())
    version = f"v{(versions[-1] + 1) if versions else 1}"
    target = packs / f".{version}.tmp"  # built aside and renamed once whole, so a crash leaves no half version
    shutil.rmtree(target, ignore_errors=True)
    specs = sorted(p.name for p in (BUILD / "specs").iterdir() if (p / "graph.json").exists())
    hold_f = BUILD / "packs" / "HOLD.json"  # subtopics whose review is unfinished stay out of the vault
    hold = json.loads(hold_f.read_text()) if hold_f.exists() else {}
    held_notes = {json.loads(pk.read_text())["note"] for pk in (BUILD / "packs").glob("*/*.json") if pk.stem in hold}
    n_packs = 0
    for spec in specs:
        (target / "specs" / spec / "packs").mkdir(parents=True, exist_ok=True)
        shutil.copy2(BUILD / "specs" / spec / "graph.json", target / "specs" / spec / "graph.json")
        for pk in sorted((BUILD / "packs" / spec).glob("*.json")) if (BUILD / "packs" / spec).exists() else []:
            if pk.stem in hold:
                continue
            shutil.copy2(pk, target / "specs" / spec / "packs" / pk.name)
            n_packs += 1
    shutil.copy2(BUILD / "plan.json", target / "plan.json")
    papers = BUILD / "papers.json"
    store.write_text(target / "papers.json", papers.read_text() if papers.exists() else json.dumps({"papers": []}))
    store.write_text(target / "manifest.json", json.dumps({"version": version, "specs": specs, "packs": n_packs}, indent=1))
    os.replace(target, packs / version)
    names = {f.stem for f in (BUILD / "notes").rglob("*.md") if str(f.relative_to(BUILD / "notes")) not in held_notes} \
        | {f.stem for f in vault.rglob("*.md")}
    where: dict[str, list[str]] = {}
    for f in (BUILD / "notes").rglob("*.md"):
        rel = f.relative_to(BUILD / "notes")
        if str(rel) not in held_notes:
            where.setdefault(f.stem, []).append(rel.parent.as_posix())
    copied = 0
    for src_root, dest in ((BUILD / "notes", vault), (BUILD / "Assets", vault / "Assets"),
                           (BUILD / "assets", vault / "Assets"), (BUILD / "Papers", vault / "Papers")):
        if not src_root.exists():
            continue
        for f in src_root.rglob("*"):
            if f.is_file() and not f.name.startswith(".DS_") \
                    and not (src_root == BUILD / "notes" and str(f.relative_to(src_root)) in held_notes):
                d = dest / f.relative_to(src_root)
                if src_root == BUILD / "notes" and f.suffix == ".md":  # links follow what is published
                    text = fix_tags(link_notes(f.read_text(encoding="utf-8"), names, where,
                                               f.relative_to(src_root).parent.as_posix()))
                    # a note you edited in the vault (newer than the build's) is kept
                    if not d.exists() or (d.stat().st_mtime <= f.stat().st_mtime
                                          and d.read_text(encoding="utf-8") != text):
                        d.parent.mkdir(parents=True, exist_ok=True)
                        d.write_text(text, encoding="utf-8")
                        os.utime(d, (f.stat().st_atime, f.stat().st_mtime))
                        copied += 1
                elif not d.exists() or d.stat().st_mtime < f.stat().st_mtime:
                    d.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(f, d)
                    copied += 1
    engine = tutor / "engine"  # remote Cowork runs the engine inside the connected folder (device_bash)
    new, old = tutor / "engine.new", tutor / "engine.old"  # copied aside and swapped in: never half an engine
    shutil.rmtree(new, ignore_errors=True)
    shutil.rmtree(old, ignore_errors=True)
    shutil.copytree(ROOT / "plugin/stem-tutor/skills/tutor/scripts", new, ignore=shutil.ignore_patterns("__pycache__"))
    if engine.exists():
        os.replace(engine, old)
    os.replace(new, engine)
    shutil.rmtree(old, ignore_errors=True)
    launcher = vault / "Start Tutor.command"  # double-click in Finder to open the terminal app
    store.write_text(launcher, launcher_script(vault))
    launcher.chmod(0o755)
    store.write_text(packs / "CURRENT", version)  # flip last
    prune_versions(packs, version)
    return {"version": version, "specs": len(specs), "packs": n_packs, "held": sorted(hold), "files_copied": copied}



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
    print(json.dumps(publish(vault_from(sys.argv))))
