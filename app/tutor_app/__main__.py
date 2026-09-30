"""`tutor` — start the app.  `tutor doctor` — check everything is set up."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import config, mac


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="tutor", description="STEM Tutor: study in the terminal, notes in Obsidian.")
    ap.add_argument("command", nargs="?", choices=["doctor"], help="doctor = check the setup")
    ap.add_argument("--vault", type=Path, help="tutor folder (default: AI Workflow/STEM Tutor)")
    args = ap.parse_args(argv)
    vault = args.vault or config.vault_path()
    if args.command == "doctor":
        ok_all = True
        for ok, check, fix in mac.doctor(vault):
            ok_all &= ok
            print(f"{'✅' if ok else '❌'} {check}" + (f"\n   → {fix}" if fix else ""))
        print("\nAll good. Start with: tutor" if ok_all else "\nFix the ❌ items above (the tutor still runs without AI).")
        return 0
    from .app import TutorApp
    app = TutorApp(vault)
    app.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
