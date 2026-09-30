#!/bin/bash
# Build a scratch copy of the tutor vault under /tmp so the engine and app can be exercised
# without touching the learner's real vault (../STEM Tutor).
#   bash bugwatch/sandbox.sh [/tmp/some-dir]
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${1:-/tmp/stem-tutor-bugwatch}"
case "$OUT" in
  /tmp/*|/private/tmp/*) ;;
  *) echo "refusing: the sandbox must live under /tmp (got $OUT)" >&2; exit 1 ;;
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
