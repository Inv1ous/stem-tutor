#!/bin/bash
# Run the test suite without leaving anything in the repo (no .pyc files, no pytest cache).
#   bash bugwatch/check.sh                 whole suite
#   bash bugwatch/check.sh tests/app -q    part of it (extra arguments go to pytest)
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONDONTWRITEBYTECODE=1
cd "$ROOT" || exit 1
[ "$#" -eq 0 ] && set -- tests -q
exec "$ROOT/.venv/bin/python" -m pytest -p no:cacheprovider -o faulthandler_timeout=90 "$@"
