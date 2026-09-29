"""Mac helpers: Obsidian, the iPad inbox, and the health check (`tutor doctor`)."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote

OBSIDIAN_CONFIG = Path.home() / "Library/Application Support/obsidian/obsidian.json"


def obsidian_vault_registered(vault: Path) -> bool:
    try:
        data = json.loads(OBSIDIAN_CONFIG.read_text())
    except (OSError, json.JSONDecodeError):
        return False
    target = str(vault.resolve())
    return any(str(Path(v.get("path", "")).resolve()) == target for v in data.get("vaults", {}).values())


def open_in_obsidian(vault: Path, note: str = "Now", background: bool = True) -> bool:
    """Show a note in Obsidian. background=True keeps the terminal focused."""
    if sys.platform != "darwin" or not shutil.which("open"):
        return False
    if obsidian_vault_registered(vault):
        url = f"obsidian://open?vault={quote(vault.name)}&file={quote(note)}"
    else:
        url = f"obsidian://open?path={quote(str(vault / (note + '.md')))}"
    args = ["open"] + (["-g"] if background else []) + [url]
    return subprocess.run(args, capture_output=True).returncode == 0


def import_ipad_inbox(vault: Path, inbox: Path) -> list[str]:
    """Copy new PDFs/images from the iCloud Drive inbox into the vault's Inbox; originals move to 'Imported'."""
    if not inbox.exists():
        return []
    moved = []
    dest = vault / "Inbox"
    dest.mkdir(exist_ok=True)
    for f in sorted(inbox.iterdir()):
        if f.is_file() and f.suffix.lower() in (".pdf", ".png", ".jpg", ".jpeg", ".heic") and not f.name.startswith("."):
            target = dest / f.name
            if target.exists():
                target = dest / f"{f.stem} {len(list(dest.glob(f.stem + '*')))}{f.suffix}"
            shutil.copy2(f, target)
            (inbox / "Imported").mkdir(exist_ok=True)
            f.rename(inbox / "Imported" / f.name)
            moved.append(target.name)
    return moved


def claude_status() -> dict:
    exe = shutil.which("claude")
    if not exe:
        return {"installed": False, "logged_in": False}
    try:
        out = subprocess.run([exe, "auth", "status"], capture_output=True, text=True, timeout=20).stdout
        data = json.loads(out[out.find("{"):]) if "{" in out else {}
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
        data = {}
    return {"installed": True, "logged_in": bool(data.get("loggedIn")), "method": data.get("authMethod")}


def doctor(vault: Path) -> list[tuple[bool, str, str]]:
    """(ok, check, what to do) for everything the app needs."""
    rows = []
    tutor_dir = vault / ".tutor"
    rows.append((tutor_dir.exists(), f"Tutor folder: {vault}",
                 "" if tutor_dir.exists() else "Run the build's publish step, or set STEM_TUTOR_VAULT."))
    if tutor_dir.exists():
        cur = (tutor_dir / "packs" / "CURRENT").read_text().strip() if (tutor_dir / "packs" / "CURRENT").exists() else "?"
        events = sum(1 for f in (tutor_dir / "events").glob("*.jsonl") for _ in open(f)) if (tutor_dir / "events").exists() else 0
        rows.append((cur != "?", f"Content packs: {cur}; {events} study events recorded", ""))
    reg = obsidian_vault_registered(vault)
    rows.append((reg, "Obsidian knows this folder as a vault",
                 "" if reg else "In Obsidian: Open another vault → Open folder as vault → choose the 'STEM Tutor' folder."))
    cs = claude_status()
    rows.append((cs["installed"], "Claude Code is installed (for AI help)", "" if cs["installed"] else
                 "Install Claude Code; the tutor still works without AI."))
    if cs["installed"]:
        rows.append((cs["logged_in"], "Claude Code is signed in", "" if cs["logged_in"] else
                     "In Terminal run:  claude auth login   (your normal Claude account). AI stays off until then."))
    try:
        import textual
        rows.append((True, f"Terminal interface library ready (textual {textual.__version__})", ""))
    except ImportError:
        rows.append((False, "Terminal interface library", "Run the installer again (bin/tutor --setup)."))
    return rows
