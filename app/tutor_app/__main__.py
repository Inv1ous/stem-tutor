"""`tutor` — start the app.  `tutor doctor` — check everything is set up.  `tutor look` — set up the Terminal window."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from . import config, look, mac


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="tutor", description="STEM Tutor: study in the terminal, notes in Obsidian.")
    ap.add_argument("command", nargs="?", choices=["doctor", "look"],
                    help="doctor = check the setup; look = set up macOS Terminal for the Night and Day looks (once)")
    ap.add_argument("--undo", action="store_true", help="with look: back to the Classic look, and how to undo the rest")
    ap.add_argument("--device-colours", action="store_true",
                    help="with look: write the profiles' colours as plain numbers (if the window's edge shows)")
    ap.add_argument("--vault", type=Path, help="tutor folder (default: ~~ AI Workflow/STEM Tutor)")
    args = ap.parse_args(argv)
    vault = args.vault or config.vault_path()
    if args.command == "doctor":
        rows = mac.doctor(vault)
        for ok, check, fix in rows:
            print(f"{'·' if ok is None else '✓' if ok else '✗'} {check}" + (f"\n   → {fix}" if fix else ""))
        print("\nAll good. Start with: tutor" if all(ok is not False for ok, _, _ in rows) else
              "\nFix the ✗ items above: the tutor can't start without its folder." if not rows[0][0] else
              "\nFix the ✗ items above (the tutor still runs meanwhile).")
        return 0
    if args.command == "look":
        from . import setup_look
        return setup_look.undo(vault) if args.undo else setup_look.install(vault, device=args.device_colours)
    if mac.wants_truecolor(os.environ, config.Settings.load(vault).theme):
        os.environ["COLORTERM"] = "truecolor"  # before the app reads it
    from .app import TutorApp
    app = TutorApp(vault)
    app.tty = mac.terminal_tty()
    if app.settings.theme != "classic":  # Classic leaves the tab as the launcher set it, as it always did
        profile = look.TERMINAL_PROFILES[app.settings.theme]
        app.profile_missing = mac.switch_terminal_profile(app.tty, profile) == "missing"
    print(f"\x1b]0;{app.TITLE}\x07", end="", flush=True)  # name the terminal window: a terminal shows what it is told
    try:
        app.run()
    finally:
        print("\x1b]0;\x07", end="", flush=True)  # hand the title back
    return 0


if __name__ == "__main__":
    sys.exit(main())
