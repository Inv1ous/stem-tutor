"""Mac helpers: Obsidian, the iPad inbox, and the health check (`tutor doctor`)."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote

OBSIDIAN_CONFIG = Path.home() / "Library/Application Support/obsidian/obsidian.json"
INBOX_HELP = ("macOS isn't letting the tutor open your iPad inbox in iCloud Drive. To allow it: System Settings › "
              "Privacy & Security › Files & Folders › Terminal › turn on iCloud Drive (or add Terminal under Full Disk "
              "Access), then restart the tutor. Everything else works meanwhile.")


def obsidian_vault_registered(vault: Path) -> str | None:
    """"exact" when Obsidian has this folder as a vault, "inside" when it has a folder containing it (notes then open
    by path and links still resolve), else None."""
    try:
        data = json.loads(OBSIDIAN_CONFIG.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    target = vault.resolve()
    paths = [Path(v.get("path", "")).resolve() for v in data.get("vaults", {}).values() if v.get("path")]
    return "exact" if target in paths else "inside" if any(p in target.parents for p in paths) else None


def open_in_obsidian(vault: Path, note: str = "Now", background: bool = True) -> bool:
    """Show a note in Obsidian. background=True keeps the terminal focused."""
    if sys.platform != "darwin" or not shutil.which("open"):
        return False
    if obsidian_vault_registered(vault) == "exact":
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
    for f in sorted(inbox.iterdir()):  # raises if macOS privacy settings block iCloud Drive: the caller warns
        if f.is_file() and f.suffix.lower() in (".pdf", ".png", ".jpg", ".jpeg", ".heic") and not f.name.startswith("."):
            target = _unused(dest, f.name)
            try:
                shutil.copy2(f, target)
            except OSError:  # unreadable (still downloading from iCloud?): leave it for next time
                target.unlink(missing_ok=True)
                continue
            (inbox / "Imported").mkdir(exist_ok=True)
            f.rename(_unused(inbox / "Imported", f.name))
            moved.append(target.name)
    return moved


def inbox_blocked(inbox: Path) -> bool:
    """True when the inbox exists but can't be listed (macOS privacy settings for iCloud Drive)."""
    try:
        if inbox.exists():
            next(inbox.iterdir(), None)
    except OSError:
        return True
    return False


def _unused(folder: Path, name: str) -> Path:
    """`name` in `folder`, or "name 2", "name 3"… when taken: an import never overwrites handwritten work."""
    target, k = folder / name, 1
    while target.exists():
        k += 1
        target = folder / f"{Path(name).stem} {k}{Path(name).suffix}"
    return target


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
        events = sum(1 for f in (tutor_dir / "events").glob("*.jsonl") for _ in open(f, "rb")) if (tutor_dir / "events").exists() else 0
        rows.append((cur != "?", f"Content packs: {cur}; {events} study events recorded", ""))
    reg = obsidian_vault_registered(vault)
    rows.append((bool(reg), "Obsidian can show these notes" + (" (inside a larger vault)" if reg == "inside" else ""),
                 "" if reg else "In Obsidian: Open another vault → Open folder as vault → choose the 'STEM Tutor' folder."))
    from . import config
    blocked = inbox_blocked(config.ICLOUD_INBOX)
    rows.append((not blocked, "iPad inbox in iCloud Drive: " + ("blocked by macOS" if blocked else "ready"
                 if config.ICLOUD_INBOX.exists() else "not set up (optional)"), INBOX_HELP if blocked else ""))
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
