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
            f'exec "{ROOT / "bin" / "tutor"}"' + (f" --vault {shlex.quote(str(Path(vault).resolve()))}" if other else "")
            + "\n")


WIKILINK = re.compile(r"(?<!!)\[\[([^\]|#]+)([^\]]*)\]\]")
CHAPTER = re.compile(r"(\d+(\.\d+)?|§\d+) ")  # a link to a syllabus chapter: "5.2 Hess’s law", "4 Differentiation"


def _plain(name: str) -> str:
    return name.replace("’", "'").replace("‘", "'")


def link_notes(text: str, names: set[str]) -> str:
    """Make a note's [[links]] open what is in the vault: "Hess's law" finds "Hess’s law.md", and a link to a chapter
    not published yet is plain text until it is (clicking it would make an empty note)."""
    by_plain = {_plain(n): n for n in names}

    def fix(m: re.Match) -> str:
        target, rest = m.group(1).strip(), m.group(2)
        if target in names or "/" in target:
            return m.group(0)
        if _plain(target) in by_plain:
            return f"[[{by_plain[_plain(target)]}{rest}]]"
        if not CHAPTER.match(target):
            return m.group(0)
        return rest.split("|", 1)[1] if "|" in rest else target
    return WIKILINK.sub(fix, text)


def publish(vault: Path) -> dict:
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
    target = packs / version
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
    (target / "papers.json").write_text(papers.read_text() if papers.exists() else json.dumps({"papers": []}))
    (target / "manifest.json").write_text(json.dumps({"version": version, "specs": specs, "packs": n_packs}, indent=1))
    names = {f.stem for f in (BUILD / "notes").rglob("*.md") if str(f.relative_to(BUILD / "notes")) not in held_notes} \
        | {f.stem for f in vault.rglob("*.md")}
    copied = 0
    for src_root, dest in ((BUILD / "notes", vault), (BUILD / "Assets", vault / "Assets"),
                           (BUILD / "assets", vault / "Assets"), (BUILD / "Papers", vault / "Papers")):
        if not src_root.exists():
            continue
        for f in src_root.rglob("*"):
            if f.is_file() and not (src_root == BUILD / "notes" and str(f.relative_to(src_root)) in held_notes):
                d = dest / f.relative_to(src_root)
                if src_root == BUILD / "notes" and f.suffix == ".md":  # links follow what is published
                    text = link_notes(f.read_text(encoding="utf-8"), names)
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
    shutil.rmtree(engine, ignore_errors=True)
    shutil.copytree(ROOT / "plugin/stem-tutor/skills/tutor/scripts", engine, ignore=shutil.ignore_patterns("__pycache__"))
    launcher = vault / "Start Tutor.command"  # double-click in Finder to open the terminal app
    launcher.write_text(launcher_script(vault))
    launcher.chmod(0o755)
    (packs / "CURRENT").write_text(version)  # flip last
    prune_versions(packs, version)
    return {"version": version, "specs": len(specs), "packs": n_packs, "held": sorted(hold), "files_copied": copied}



def prune_versions(packs: Path, current: str) -> None:
    """Keep the two previous versions for rollback, newest by number: v10 is newer than v9."""
    old = sorted((p for p in packs.glob("v*") if p.name != current and p.name[1:].isdigit()), key=lambda p: int(p.name[1:]))
    for p in old[:-2]:
        shutil.rmtree(p)


if __name__ == "__main__":
    vault = Path(sys.argv[sys.argv.index("--vault") + 1]) if "--vault" in sys.argv else DEFAULT_VAULT
    print(json.dumps(publish(vault)))
