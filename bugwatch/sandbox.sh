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
PYTHONDONTWRITEBYTECODE=1 "$ROOT/.venv/bin/python" "$ROOT/build/publish.py" --vault "$OUT/mnt/STEM Tutor" >/dev/null || exit 1
cat <<EOF
Scratch vault ready: $OUT/mnt/STEM Tutor   (safe to change or delete; rerun this script for a fresh one)

R="$ROOT"
export PYTHONDONTWRITEBYTECODE=1
export STEM_TUTOR_VAULT="$OUT/mnt/STEM Tutor"
export PYTHONPATH="\$R/app:\$R/plugin/stem-tutor/skills/tutor/scripts"

# engine CLI:  "\$R/.venv/bin/python" "\$R/plugin/stem-tutor/skills/tutor/scripts/tutor.py" doctor
# in Python:   from tutorlib import store, session; t = session.Tutor(store.Vault(store.find_vault()))
# the app:     see tests/app/test_tui.py (Textual pilot, fake Claude in tests/app/fake_claude.py)
EOF
