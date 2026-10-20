#!/usr/bin/env python3
"""Post one bug-watch entry the moment it is found. Safe with several hunters posting at once: a lock makes the
numbering and the append one step, so no two entries get the same number or interleave.

  python3 bugwatch/post.py bug   < entry.md    "### B-??? · P2 · file · title" + the fields (codex/BUGS.md format)
  python3 bugwatch/post.py qol   < entry.md    "### Q-??? · file · title" + the fields (codex/QOL.md format)
  python3 bugwatch/post.py line  "SWEEP · area · what ran · findings: 2"     a log line; the HH:MM is added
  python3 bugwatch/post.py line  "REPLY B-041 · coordinator reproduced it"

Prints the number it gave (B-041 / Q-007). Nothing is written if the entry is malformed.
"""
from __future__ import annotations

import fcntl
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
BUGS, QOL, LOCK = HERE / "codex" / "BUGS.md", HERE / "codex" / "QOL.md", HERE / "codex" / ".post.lock"
BUG_HEAD = re.compile(r"^### B-(?:\?\?\?|\d+) · (P[0-3]) · ([^·]+?) · (.+)$")
QOL_HEAD = re.compile(r"^### Q-(?:\?\?\?|\d+) · ([^·]+?) · (.+)$")
BUG_FIELDS = ("Found", "Where", "Repro", "Expected", "Actual", "Impact")
QOL_FIELDS = ("Seen", "Friction", "Idea", "Size")
VERBS = ("SWEEP", "REPLY", "VERIFIED", "REOPEN")


def next_id(path: Path, letter: str) -> str:
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    text = re.sub(r"^```.*?^```", "", text, flags=re.M | re.S)  # the format example in the header is not an entry
    nums = [int(n) for n in re.findall(rf"^### {letter}-(\d+) ", text, flags=re.M)]
    return f"{letter}-{max(nums, default=0) + 1:03d}"


def check(entry: str, head: re.Pattern, fields: tuple[str, ...]) -> str | None:
    lines = entry.strip().splitlines()
    if not lines or not head.match(lines[0]):
        return f"first line must look like: {head.pattern}"
    have = set(re.findall(r"\*\*(\w+):\*\*", entry))
    missing = [f for f in fields if f not in have]
    return f"missing fields: {', '.join(missing)}" if missing else None


def append(path: Path, text: str) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(text)
        f.flush()


def main(argv: list[str]) -> int:
    kind = argv[0] if argv else ""
    LOCK.touch(exist_ok=True)
    with LOCK.open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if kind == "line":
            body = " ".join(argv[1:]).strip()
            if not body.startswith(VERBS):
                print(f"a log line starts with one of {VERBS}", file=sys.stderr)
                return 1
            append(BUGS, f"- {time.strftime('%H:%M')} {body}\n")
            print("posted")
            return 0
        if kind not in ("bug", "qol"):
            print(__doc__, file=sys.stderr)
            return 1
        path, letter, head, fields = (BUGS, "B", BUG_HEAD, BUG_FIELDS) if kind == "bug" else (QOL, "Q", QOL_HEAD, QOL_FIELDS)
        entry = sys.stdin.read()
        if problem := check(entry, head, fields):
            print(f"not posted: {problem}", file=sys.stderr)
            return 1
        new = next_id(path, letter)
        first, _, rest = entry.strip().partition("\n")
        first = re.sub(rf"^### {letter}-(?:\?\?\?|\d+)", f"### {new}", first)
        append(path, f"\n{first}\n{rest}\n")
        print(new)
        return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
