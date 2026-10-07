"""`tutor look`: set up the tutor's macOS Terminal window for the Night and Day looks, once. `tutor look --undo` goes back.

In order: back up Terminal's settings (nothing changes if that fails), install the bundled JuliaMono font, add the
"STEM Tutor Night" and "STEM Tutor Day" profiles (only if missing; the learner's own profiles are never touched),
check, switch the look to Night, and print a specimen to judge the result by eye."""
from __future__ import annotations

import hashlib
import os
import plistlib
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from . import config, look, mac, termprofile
from .texmath import to_terminal

IS_MAC = sys.platform == "darwin"
FONT_DIR = Path.home() / "Library" / "Fonts"
BUNDLED = Path(__file__).parent / "fonts"
FONTS = ("JuliaMono-Regular.ttf", "JuliaMono-Bold.ttf", "JuliaMono-RegularItalic.ttf")
EXISTS = 'on run argv\ntell application "Terminal" to return exists settings set (item 1 of argv)\nend run'
MATHS = (r"$s = ut + \frac{1}{2}at^2$   $\sqrt{b^2-4ac}$   $\Delta H^\ominus = -286\,\text{kJ mol}^{-1}$",
         r"$\ce{Cu^2+ + 2e- -> Cu}$   $\ce{N2 + 3H2 <=> 2NH3}$   $\mathbf{F} = m\mathbf{a}$   $\vec{v}$  $\hat{x}$  $\bar{x}$",
         r"$\int_0^1 x^2\,dx$   $\sum_{i=1}^{n} x_i$   $\frac{dy}{dx} = 3x^2 - 2$   $\theta \le 30^\circ$   $\lambda$ $\mu$ $\pi$")
UI_GLYPHS = "▸ ★ ◆ ↻ ✚ ◎ ✎ » ✦ ◉ ▤ ▣ ≡ × ✶ ⧗ ▦ △ ◷ ✓ ✗ ● ○ ◔ ◑ ⏎ ↑ ↓ … · –"


def _run(args: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, timeout=30, **kw)


def terminal_prefs(target: Path) -> dict | None:
    """Export Terminal's settings to `target` and read them back; None if that did not work."""
    try:
        done = _run(["defaults", "export", "com.apple.Terminal", str(target)])
        if done.returncode != 0:
            return {} if "does not exist" in (done.stderr or "") else None  # never set up: nothing to lose
        return plistlib.loads(target.read_bytes())
    except (OSError, subprocess.SubprocessError, plistlib.InvalidFileException, ValueError):
        return None


def profile_exists(name: str) -> bool:
    try:
        return _run(["osascript", "-", name], input=EXISTS).stdout.strip() == "true"
    except (OSError, subprocess.SubprocessError):
        return False


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _matches(saved: dict, wanted: dict) -> bool:
    """Whether a profile Terminal has is the one `tutor look` would add (font, size and colours)."""
    try:
        return all(termprofile.decoded(saved[k]) == termprofile.decoded(wanted[k]) for k in
                   ("Font", "BackgroundColor", "TextColor"))
    except (KeyError, TypeError, ValueError, plistlib.InvalidFileException):
        return False


def install(vault: Path, device: bool = False, out=print) -> int:
    if not IS_MAC:
        out("tutor look sets up macOS Terminal: run it on the Mac.")
        return 1
    backups = vault / ".tutor" / "backups"
    backups.mkdir(parents=True, exist_ok=True)
    backup = backups / f"terminal-{datetime.now():%Y%m%d-%H%M%S}.plist"
    prefs = terminal_prefs(backup)
    if prefs is None:
        out("Could not back up your Terminal settings, so nothing was changed. Try again with Terminal open.")
        return 1
    out(f"✓ Backed up your Terminal settings: {backup}")

    FONT_DIR.mkdir(parents=True, exist_ok=True)
    for name in FONTS:
        target = FONT_DIR / name
        if not target.exists():
            shutil.copy2(BUNDLED / name, target)
            out(f"✓ Installed the font {name}")
        elif _sha(target) != _sha(BUNDLED / name):
            out(f"· Kept your own {name} (a different version). If symbols look wrong, delete it from "
                f"{FONT_DIR} and run  tutor look  again.")

    profiles = prefs.get("Window Settings") or {}
    study = profiles.get("Study") or {}
    try:
        size = termprofile.decoded(study["Font"])[1]
    except (KeyError, TypeError, ValueError, IndexError, plistlib.InvalidFileException):
        size = termprofile.SIZE
    folder = vault / ".tutor" / "look"
    folder.mkdir(parents=True, exist_ok=True)
    problems = []
    for theme in ("night", "day"):
        name = look.TERMINAL_PROFILES[theme]
        wanted = termprofile.profile(name, look.PALETTES[theme], termprofile.ANSI[theme], size, study, device)
        if name in profiles:
            if _matches(profiles[name], wanted):
                out(f"✓ Terminal profile {name}: already set up")
            else:
                problems.append(f"Terminal already has a profile called {name} that is different. Delete it in "
                                f"Terminal › Settings › Profiles (select it, click −), then run  tutor look  again.")
            continue
        file = folder / f"{name}.terminal"
        file.write_bytes(termprofile.dumps(wanted))
        _run(["open", str(file)])  # Terminal adds the profile (and opens a window in it: close that one)
        for _ in range(20):
            if profile_exists(name):
                out(f"✓ Added the Terminal profile {name} (JuliaMono {size:g} pt). Close the extra window it opened.")
                break
            time.sleep(0.5)
        else:
            problems.append(f"Terminal did not add {name}. Double-click {file} in Finder to add it by hand.")

    after = terminal_prefs(backups / "after-tutor-look.plist")
    if after is not None:
        names = after.get("Window Settings") or {}
        for key in ("Default Window Settings", "Startup Window Settings"):
            if after.get(key) != prefs.get(key):
                problems.append(f"Terminal's {key.lower()} changed (expected not): set it back in Terminal › Settings "
                                f"› Profiles › Default, or restore the backup (tutor look --undo explains how).")
        if study and names.get("Study") != study:
            problems.append("Your Study profile looks changed (expected not); tutor look --undo explains how to "
                            "restore the backup.")
        twins = sorted(n for n in names if n.startswith("STEM Tutor ") and n not in look.TERMINAL_PROFILES.values())
        if twins:
            problems.append(f"Terminal now has extra copies ({', '.join(twins)}): delete them in Terminal › Settings "
                            f"› Profiles.")
    for p in problems:
        out(f"✗ {p}")
    if any(not profile_exists(look.TERMINAL_PROFILES[t]) for t in ("night", "day")):
        out("\nThe look stays Classic until both profiles are there.")
        return 1
    settings = config.Settings.load(vault)
    settings.theme = "night"
    settings.save(vault)
    mac.switch_terminal_profile(mac.terminal_tty(), look.TERMINAL_PROFILES["night"])
    out("✓ The tutor now uses the Night look (change it any time: Settings, F2).\n")
    out(specimen())
    return 1 if problems else 0


def specimen() -> str:
    """A page to judge by eye in the new window: matching background, colours, borders, every symbol, maths."""
    p = look.PALETTES["night"]

    def paint(hex_colour: str, text: str, ground: bool = False) -> str:
        r, g, b = (int(hex_colour[i:i + 2], 16) for i in (1, 3, 5))
        return f"\x1b[{48 if ground else 38};2;{r};{g};{b}m{text}\x1b[0m"
    roles = "  ".join(paint(p[role], role) for role in ("tutor", "question", "good", "bad", "hint", "ai", "dim"))
    lines = ["How it should look (the tutor draws the same way):", "",
             "1. The band between the bars should be invisible (the window and the app share one background):",
             "   |" + paint(p["background"], " " * 40, ground=True) + "|",
             "   If you can see it, delete the two STEM Tutor profiles and run:  tutor look --device-colours", "",
             "2. Colours:  " + roles, "",
             "3. Borders join and bars are solid:",
             "   ╭──────────╮  ▁▁▁▁▁▁▁▁▁▁  ███████░░░",
             "   │ a card   │  ▔▔▔▔▔▔▔▔▔▔  ▏▎▍▌▋▊▉█",
             "   ╰──────────╯", "",
             "4. Every symbol sits in one cell, between its bars:",
             "   |" + "|".join(UI_GLYPHS.split()) + "|", "",
             "5. Maths:"] + ["   " + to_terminal(m) for m in MATHS] + [
             "", "Start the tutor as usual (double-click Start Tutor). To go back: tutor look --undo"]
    return "\n".join(lines)


def doctor_rows(vault: Path) -> list[tuple[bool | None, str, str]]:
    """(ok, check, what to do) for the look; ok None is advice, not a problem (Classic needs none of it)."""
    if not IS_MAC:
        return []
    theme = config.Settings.load(vault).theme
    needed = theme != "classic"
    rows: list[tuple[bool | None, str, str]] = [
        (None, f"Look: {look.LABELS[theme]}", "" if needed else "Optional: run  tutor look  for the Night and Day looks.")]
    font = (FONT_DIR / FONTS[0]).exists()
    rows.append((True if font else False if needed else None, "Font: JuliaMono " + ("installed" if font else "not installed"),
                 "" if font else "Run  tutor look"))
    try:
        done = _run(["defaults", "export", "com.apple.Terminal", "-"])
        names = set((plistlib.loads(done.stdout.encode()).get("Window Settings") or {}) if done.returncode == 0 else {})
    except (OSError, subprocess.SubprocessError, plistlib.InvalidFileException, ValueError):
        names = set()
    have = all(look.TERMINAL_PROFILES[t] in names for t in ("night", "day"))
    rows.append((True if have else False if needed else None,
                 "Terminal profiles: STEM Tutor Night and Day " + ("ready" if have else "not added"),
                 "" if have else "Run  tutor look"))
    env = os.environ
    if env.get("TERM_PROGRAM") == "Apple_Terminal":
        build = env.get("TERM_PROGRAM_VERSION", "?")
        full = mac.wants_truecolor({**env, "COLORTERM": ""}, "night")
        rows.append((True if full else None, f"Colours: {'24-bit' if full else '256 colours'} (Terminal build {build})",
                     "" if full else "Night and Day show their exact colours from macOS 26 on."))
    return rows


def undo(vault: Path, out=print) -> int:
    settings = config.Settings.load(vault)
    settings.theme = "classic"
    settings.save(vault)
    mac.switch_terminal_profile(mac.terminal_tty(), look.TERMINAL_PROFILES["classic"])
    backups = sorted((vault / ".tutor" / "backups").glob("terminal-*.plist"))
    out("✓ The tutor is back to the Classic look (and this tab to your Study profile).\n")
    out("To remove the rest by hand (nothing else needs it):")
    out("  1. Terminal › Settings › Profiles: select STEM Tutor Night, click −; the same for STEM Tutor Day.")
    out(f"  2. Fonts (optional): in Finder, Go › Go to Folder… {FONT_DIR}, delete the JuliaMono files.")
    if backups:
        out(f"  3. All Terminal settings exactly as before (optional): quit Terminal, open Script Editor, run\n"
            f"       do shell script \"defaults import com.apple.Terminal '{backups[0]}'\"\n"
            f"     then open Terminal again.")
    out("  4. The app as it was before the new look: in the stem-tutor folder,  git checkout v1.6.1")
    return 0
