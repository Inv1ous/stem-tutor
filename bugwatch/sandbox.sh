#!/bin/bash
# Build a scratch copy of the tutor vault under /tmp so the engine and app can be exercised
# without touching the learner's real vault (../STEM Tutor).
#   bash bugwatch/sandbox.sh [/tmp/some-dir]
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${1:-/tmp/stem-tutor-bugwatch}"
# it is deleted below: judge the real path (no .., no symlinked parent), and only a folder inside /tmp, never /tmp
NAME="$(basename "$OUT")"
PARENT="$(cd "$(dirname "$OUT")" 2>/dev/null && pwd -P)"
case "$NAME" in .|..|"") PARENT="" ;; esac
case "$PARENT/$NAME" in
  /tmp/?*|/private/tmp/?*) OUT="$PARENT/$NAME" ;;
  *) echo "refusing: the sandbox must be a folder inside /tmp (got $OUT)" >&2; exit 1 ;;
esac
rm -rf "$OUT" && mkdir -p "$OUT/mnt/STEM Tutor" || exit 1
PYTHONDONTWRITEBYTECODE=1 "$ROOT/.venv/bin/python" "$ROOT/bugwatch/sandbox.py" \
  --source "${STEM_TUTOR_BUGWATCH_SOURCE:-$ROOT/../STEM Tutor}" --target "$OUT/mnt/STEM Tutor" || exit 1
cat <<EOF
Scratch vault ready: $OUT/mnt/STEM Tutor   (safe to change or delete; rerun this script for a fresh one)
Published content and required Library assets are copied with verified hashes.
The engine's temporary-vault guard prevents writes beside the real Almanac.

R="$ROOT"
export PYTHONDONTWRITEBYTECODE=1
export STEM_TUTOR_VAULT="$OUT/mnt/STEM Tutor"
export PYTHONPATH="\$R/app:\$R/src:\$R/plugin/stem-tutor/skills/tutor/scripts"
unset TERM_PROGRAM

# engine CLI:  "\$R/.venv/bin/python" "\$R/plugin/stem-tutor/skills/tutor/scripts/tutor.py" doctor
# in Python:   from tutorlib import store, session; t = session.Tutor(store.Vault(store.find_vault()))
# App startup imports files from iCloud and Downloads. Shell exports alone do not isolate those paths.
# External pytest probes can opt into the existing machine-isolation fixtures:
# bash "\$R/bugwatch/check.sh" -p bugwatch.probe_isolation /tmp/test_probe.py -q
# Fixtures apply at test setup, not module import: keep app construction and file actions inside tests.
# Plain scripts still need the explicit setup below; check.sh defaults and in-repo fixtures are unchanged.
# Python setup before constructing any scratch TutorApp:
import os
from pathlib import Path
from tutor_app import config

os.environ.pop("TERM_PROGRAM", None)
scratch = Path(os.environ["STEM_TUTOR_VAULT"]).parents[1]
config.ICLOUD_INBOX = scratch / "ipad-inbox"
config.DOWNLOADS = scratch / "downloads"
config.CLAUDE_STATE = scratch / "claude.json"

# Then follow tests/app/test_tui.py: use tests/app/fake_claude.py and open_obsidian=False.
EOF
