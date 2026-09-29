"""Publish built content into the learner's vault folder as a new pack version.

Writes .tutor/packs/v<N>/ (graphs, packs, plan, papers, manifest) and flips CURRENT last, so a
Cowork session never sees a half-written version. Notes, SVG diagrams and MCQ figures are copied
into the visible folders (Subjects/, Assets/). Existing learner state and events are never touched.

  python build/publish.py [--vault PATH]
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build/out"
DEFAULT_VAULT = Path("/Users/sora/Library/Mobile Documents/iCloud~md~obsidian/Documents/Notes/01 Study/STEM Tutor")
FOLDERS = ["Subjects", "Assets", "Sessions", "Question Sheets", "Inbox", "Inbox/Marked", "Anki", "Almanac", "Papers"]


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
    copied = 0
    for src_root, dest in ((BUILD / "notes", vault), (BUILD / "Assets", vault / "Assets"),
                           (BUILD / "assets", vault / "Assets"), (BUILD / "Papers", vault / "Papers")):
        if not src_root.exists():
            continue
        for f in src_root.rglob("*"):
            if f.is_file() and not (src_root == BUILD / "notes" and str(f.relative_to(src_root)) in held_notes):
                d = dest / f.relative_to(src_root)
                if not d.exists() or d.stat().st_mtime < f.stat().st_mtime:
                    d.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(f, d)
                    copied += 1
    engine = tutor / "engine"  # remote Cowork runs the engine inside the connected folder (device_bash)
    shutil.rmtree(engine, ignore_errors=True)
    shutil.copytree(ROOT / "plugin/stem-tutor/skills/tutor/scripts", engine, ignore=shutil.ignore_patterns("__pycache__"))
    (packs / "CURRENT").write_text(version)  # flip last
    for old in sorted(p for p in packs.glob("v*") if p.name != version)[:-2]:
        shutil.rmtree(old)  # keep the two previous versions for rollback
    return {"version": version, "specs": len(specs), "packs": n_packs, "held": sorted(hold), "files_copied": copied}


if __name__ == "__main__":
    vault = Path(sys.argv[sys.argv.index("--vault") + 1]) if "--vault" in sys.argv else DEFAULT_VAULT
    print(json.dumps(publish(vault)))
