"""`tutor` — start the app.  `tutor doctor` — check everything is set up.  `tutor look` — set up the Terminal window.
`tutor tts setup|say|voices|doctor` — reading aloud with Kokoro."""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

from . import config, look, mac


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="tutor", description="STEM Tutor: study in the terminal, notes in Obsidian.")
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["tts"]:  # `tutor tts setup | say "…" | voices | doctor`: its own options
        from . import tts
        rest, vault = argv[1:], None
        if "--vault" in rest and rest.index("--vault") + 1 < len(rest):
            i = rest.index("--vault")
            vault, rest = Path(rest[i + 1]), rest[:i] + rest[i + 2:]
        return tts.cli(rest, vault or config.vault_path())
    ap.add_argument("command", nargs="?", choices=["doctor", "look"],
                    help="doctor = check the setup; look = set up macOS Terminal for the Night and Day looks (once); "
                         "tts = reading aloud (tutor tts setup | say | voices | doctor)")
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
        return 1 if any(ok is False for ok, _, _ in rows) else 0
    if args.command == "look":
        from . import setup_look
        return setup_look.undo(vault) if args.undo else setup_look.install(vault, device=args.device_colours)
    if mac.wants_truecolor(os.environ, config.Settings.load(vault).theme):
        os.environ["COLORTERM"] = "truecolor"  # before the app reads it
    from .app import TutorApp
    app = TutorApp(vault)
    app.tty = mac.terminal_tty()
    if app.settings.theme != "classic":  # Classic leaves the tab as the launcher set it, as it always did
        status, app.tty_profile = mac.switch_terminal_profile(app.tty, look.TERMINAL_PROFILES[app.settings.theme])
        app.profile_missing = status == "missing"
        app.profile_denied = status == "denied"
    app.settle_font_size()  # the text size the learner chose last time, which the profile switch just reset
    time.sleep(0.3)  # Terminal lays the window out again for the new size before it can be measured
    cell = app.match_zoom(mac.cell_size(), mac.cell_size)  # a ⌘ zoom last time: matched exactly, in this unzoomed window
    # (and `cell` is kept to see, at the end, whether the text was zoomed with ⌘+ / ⌘− this time)
    print(f"\x1b]0;{app.TITLE}\x07", end="", flush=True)  # name the terminal window: a terminal shows what it is told
    try:
        app.run()
    finally:
        app.note_zoom(cell, mac.cell_size())  # before the tab gets its old profile back, and with it that profile's size
        print("\x1b]0;\x07", end="", flush=True)  # hand the title back
        if app.tty_profile:  # and the tab its own profile, as it was before the tutor
            mac.switch_terminal_profile(app.tty, app.tty_profile)
    return app.return_code or 0


if __name__ == "__main__":
    sys.exit(main())
