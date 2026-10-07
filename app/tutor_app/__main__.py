"""`tutor` — start the app.  `tutor doctor` — check everything is set up."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import config, mac


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="tutor", description="STEM Tutor: study in the terminal, notes in Obsidian.")
    ap.add_argument("command", nargs="?", choices=["doctor"], help="doctor = check the setup")
    ap.add_argument("--vault", type=Path, help="tutor folder (default: ~~ AI Workflow/STEM Tutor)")
    args = ap.parse_args(argv)
    vault = args.vault or config.vault_path()
    if args.command == "doctor":
        rows = mac.doctor(vault)
        for ok, check, fix in rows:
            print(f"{'✓' if ok else '✗'} {check}" + (f"\n   → {fix}" if fix else ""))
        print("\nAll good. Start with: tutor" if all(ok for ok, _, _ in rows) else
              "\nFix the ✗ items above: the tutor can't start without its folder." if not rows[0][0] else
              "\nFix the ✗ items above (the tutor still runs without AI).")
        return 0
    from .app import TutorApp
    app = TutorApp(vault)
    print(f"\x1b]0;{app.TITLE}\x07", end="", flush=True)  # name the terminal window: a terminal shows what it is told
    try:
        app.run()
    finally:
        print("\x1b]0;\x07", end="", flush=True)  # hand the title back
    return 0


if __name__ == "__main__":
    sys.exit(main())
