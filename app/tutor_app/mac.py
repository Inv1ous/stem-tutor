"""Mac helpers: Obsidian, the iPad inbox, and the health check (`tutor doctor`)."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote

OBSIDIAN_CONFIG = Path.home() / "Library/Application Support/obsidian/obsidian.json"
INBOX_HELP = ("macOS isn't letting the tutor open your iPad inbox in iCloud Drive. To allow it: System Settings › "
              "Privacy & Security › Files & Folders › Terminal › turn on iCloud Drive (or add Terminal under Full Disk "
              "Access), then restart the tutor. Everything else works meanwhile.")
DOWNLOADS_HELP = ("macOS isn't letting the tutor look in Downloads for your Almanac export, so your ticks aren't "
                  "counted. Either allow it (System Settings › Privacy & Security › Files & Folders › Terminal › "
                  "Downloads Folder) or move the exported file into this vault's Almanac folder yourself.")


SWITCH_PROFILE = """on run argv
    set wanted to item 2 of argv
    tell application "Terminal"
        if not (exists settings set wanted) then return "missing"
        repeat with w in windows
            repeat with t in tabs of w
                if tty of t is (item 1 of argv) then
                    if name of current settings of t is not wanted then set current settings of t to settings set wanted
                    return "ok"
                end if
            end repeat
        end repeat
    end tell
    return "no tab"
end run"""
LOOK_HELP = ("This look's Terminal window isn't set up yet, so its edges keep the old colours. In Terminal run:  "
             "tutor look   (once; it backs up your Terminal settings first). Or choose Classic in Settings (F2).")


def terminal_tty() -> str | None:
    """The macOS Terminal tab this app runs in (/dev/ttys003), or None in any other terminal."""
    if os.environ.get("TERM_PROGRAM") != "Apple_Terminal":
        return None
    for stream in (sys.__stdout__, sys.__stdin__):
        try:
            return os.ttyname(stream.fileno())
        except (OSError, ValueError, AttributeError):
            continue
    return None


def switch_terminal_profile(tty: str | None, name: str) -> str:
    """Show the Terminal tab on `tty` in the profile `name` (only that tab): "ok", "missing" when Terminal has no such
    profile, or "" when it could not be asked (not in Terminal, Apple Events refused, too slow)."""
    if not tty:
        return ""
    try:
        done = subprocess.run(["osascript", "-", tty, name], input=SWITCH_PROFILE, capture_output=True, text=True,
                              timeout=3)
    except (OSError, subprocess.SubprocessError):
        return ""
    return done.stdout.strip()


def wants_truecolor(env, theme: str) -> bool:
    """macOS Terminal has drawn 24-bit colour since macOS 26 (build 470) without saying so, and the app then falls back
    to 256 colours. Night and Day are drawn in their real colours; Classic keeps what it always had."""
    if theme == "classic" or env.get("COLORTERM") or env.get("TERM_PROGRAM") != "Apple_Terminal":
        return False
    build = re.match(r"\d+", env.get("TERM_PROGRAM_VERSION", ""))
    return bool(build) and int(build.group()) >= 470


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
    dest, done = vault / "Inbox", inbox / "Imported"
    dest.mkdir(exist_ok=True)
    files = [f for f in sorted(inbox.iterdir())  # raises if macOS privacy settings block iCloud Drive: the caller warns
             if f.is_file() and f.suffix.lower() in (".pdf", ".png", ".jpg", ".jpeg", ".heic")
             and not f.name.startswith(".")]
    try:
        if files:
            done.mkdir(exist_ok=True)
    except OSError:  # nowhere to put the originals: copying would import them again on every launch
        return []
    for f in files:
        target = _unused(dest, f.name)
        try:
            shutil.copy2(f, target)
        except OSError:  # unreadable (still downloading from iCloud?): leave it for next time
            target.unlink(missing_ok=True)
            continue
        try:
            f.rename(_unused(done, f.name))
        except OSError:  # the original can't be moved aside: drop the copy, or the next launch copies it again
            target.unlink(missing_ok=True)
            continue
        moved.append(target.name)
    return moved


def import_almanac_exports(vault: Path, downloads: Path) -> list[str]:
    """Move the Almanac's progress files (its Export button saves them into Downloads) into the vault's Almanac
    folder, where the tutor reads your ticks. Nothing there is overwritten. Raises OSError when macOS privacy settings
    keep the tutor out of Downloads: the caller says how to allow it."""
    moved = []
    for name in sorted(os.listdir(downloads)) if downloads.is_dir() else []:
        if name.startswith("almanac-progress-") and name.endswith(".json"):
            (vault / "Almanac").mkdir(parents=True, exist_ok=True)
            target = _unused(vault / "Almanac", name)
            shutil.move(str(downloads / name), target)  # keeps the time it was saved: the newest export counts
            moved.append(target.name)
    return moved


def claude_limits(path: Path) -> dict:
    """What Claude Code last noted about the plan's limits (it refreshes the note when one of its sessions starts, so
    it can lag): {"five_hour": {"used": 40.0, "resets": <epoch>}, "seven_day": {…}} for the windows in force."""
    from datetime import datetime
    try:
        limits = json.loads(Path(path).read_text())["cachedUsageUtilization"]["utilization"]["limits"]
        return {{"session": "five_hour", "weekly_all": "seven_day"}.get(x["kind"], x["kind"]):
                {"used": float(x["percent"]), "resets": datetime.fromisoformat(x["resets_at"]).timestamp()}
                for x in limits if x.get("is_active") and x.get("percent") is not None and x.get("resets_at")}
    except (OSError, ValueError, KeyError, TypeError):
        return {}


def inbox_blocked(inbox: Path) -> bool:
    """True when the inbox exists but can't be listed (macOS privacy settings for iCloud Drive)."""
    try:
        if inbox.exists():
            next(inbox.iterdir(), None)
    except OSError:
        return True
    return False


def almanac_changed(plan: dict) -> bool:
    """True when the Almanac file the plan was built from has changed since, so the tutor still follows the old plan."""
    src, digest = plan.get("source_path"), plan.get("source_sha256")
    if not (src and digest):
        return False
    try:
        return hashlib.sha256(Path(src).read_bytes()).hexdigest() != digest
    except OSError:  # moved or unreadable: nothing to compare
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
        from tutorlib import store
        try:
            cur = (tutor_dir / "packs" / "CURRENT").read_text().strip()
        except OSError:
            cur = ""
        try:
            v = store.Vault(vault)
            events, bad = sum(1 for _ in v.events()), getattr(v, "bad_lines", [])
        except (OSError, ValueError):
            events, bad = 0, ["the history could not be read"]
        rows.append((bool(cur), f"Content packs: {cur or 'none published'}; {events} study events recorded",
                     "" if cur else "Run the build's publish step."))
        if bad:
            rows.append((False, f"Study history: {len(bad)} damaged line{'s' if len(bad) != 1 else ''} skipped "
                         f"({', '.join(bad[:3])}{', …' if len(bad) > 3 else ''})",
                         "Cut off mid-save (a crash?); everything else is read. If answers are missing, restore that "
                         "file from a backup."))
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
    from . import setup_look
    return rows + setup_look.doctor_rows(vault)
