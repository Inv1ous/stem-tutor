#!/usr/bin/env python3
"""Live board for the bug hunt: every finding in codex/BUGS.md with its latest status from FIXES.md.

  python bugwatch/bugs.py              open findings (not FIXED/VERIFIED/REJECTED/DUPLICATE/DEFERRED)
  python bugwatch/bugs.py --all        everything
  python bugwatch/bugs.py --unseen     findings newer than Claude's last LAST-READ marker
  python bugwatch/bugs.py --check      report entries that don't follow the format
  python bugwatch/bugs.py --watch [s]  redraw every s seconds (default 5)

Times are HH:MM in one day; events are ordered by time, then by position in the file.
"""
from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
BUGS, FIXES = HERE / "codex" / "BUGS.md", HERE / "FIXES.md"
HEAD = re.compile(r"^### (B-\d+) · (P[0-3]) · ([^·]+?) · (.+)$")
LOG = re.compile(r"^- (\d\d:\d\d) (SWEEP|VERIFIED|REOPEN|REPLY)\b ?(B-\d+)?")
FIX = re.compile(r"^- (\d\d:\d\d) (?:(B-\d+) (CONFIRMED|FIXED|REJECTED|DUPLICATE|DEFERRED|NEEDS-INFO)\b|LAST-READ (B-\d+))")
REQUIRED = ("Found", "Where", "Repro", "Expected", "Actual", "Impact")
DONE = {"FIXED", "VERIFIED", "REJECTED", "DUPLICATE", "DEFERRED"}
COLOUR = {"P0": "\033[1;31m", "P1": "\033[33m", "P2": "\033[36m", "P3": "\033[2m"}
STATUS_COLOUR = {"OPEN": "\033[0m", "CONFIRMED": "\033[35m", "NEEDS-INFO": "\033[34m", "REOPENED": "\033[1;31m",
                 "FIXED": "\033[32m", "VERIFIED": "\033[1;32m", "REJECTED": "\033[2m", "DUPLICATE": "\033[2m",
                 "DEFERRED": "\033[2m"}
RESET = "\033[0m"


def lines_outside_fences(path: Path):
    fenced = False
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines() if path.exists() else [], 1):
        if line.strip().startswith("```"):
            fenced = not fenced
            continue
        if not fenced:
            yield n, line


def load() -> tuple[dict, list, list, str | None]:
    bugs: dict[str, dict] = {}
    events: list[tuple[str, int, str, str]] = []  # (time, order, bug id, status)
    problems: list[str] = []
    cur = None
    order = 0
    for n, line in lines_outside_fences(BUGS):
        if m := HEAD.match(line):
            cur = {"id": m[1], "pri": m[2], "area": m[3].strip(), "title": m[4].strip(), "line": n, "fields": set()}
            if m[1] in bugs:
                problems.append(f"BUGS.md:{n} duplicate id {m[1]}")
            bugs[m[1]] = cur
        elif line.startswith("### "):
            problems.append(f"BUGS.md:{n} heading doesn't match '### B-nnn · P0-3 · area · title'")
            cur = None
        elif cur and line.startswith("- ") and re.search(r"\*\*\w+:\*\*", line):
            cur["fields"].update(re.findall(r"\*\*(\w+):\*\*", line))
        elif m := LOG.match(line):
            order += 1
            if m[2] in ("VERIFIED", "REOPEN") and m[3]:
                events.append((m[1], order, m[3], m[2]))
        elif line.startswith("- ") and re.match(r"- \d\d:\d\d ", line):
            problems.append(f"BUGS.md:{n} log line with unknown verb: {line[:60]}")
    last_read = None
    for n, line in lines_outside_fences(FIXES):
        if m := FIX.match(line):
            order += 1
            if m[4]:
                last_read = m[4]
            else:
                events.append((m[1], 100000 + order, m[2], m[3]))
    for b in bugs.values():
        missing = [f for f in REQUIRED if f not in b["fields"]]
        if missing:
            problems.append(f"{b['id']} (BUGS.md:{b['line']}) missing fields: {', '.join(missing)}")
    return bugs, sorted(events), problems, last_read


def status_of(bug_id: str, events: list) -> str:
    status = "OPEN"
    for _, _, bid, ev in events:
        if bid != bug_id:
            continue
        if ev == "REOPEN":
            status = "REOPENED"
        elif ev == "VERIFIED":
            status = "VERIFIED" if status in ("FIXED", "VERIFIED") else status
        else:
            status = ev
    return status


def render(args) -> str:
    bugs, events, problems, last_read = load()
    rows = [(b, status_of(b["id"], events)) for b in bugs.values()]
    if args.check:
        return "\n".join(problems) if problems else "all entries follow the format"
    if args.unseen:
        seen = int(last_read.split("-")[1]) if last_read else 0
        rows = [(b, s) for b, s in rows if int(b["id"].split("-")[1]) > seen]
    elif not args.all:
        rows = [(b, s) for b, s in rows if s not in DONE]
    rows.sort(key=lambda r: (r[0]["pri"], r[0]["id"]))
    out = [f"{'ID':<6} {'PRI':<3} {'STATUS':<10} {'AREA':<16} TITLE"]
    for b, s in rows:
        out.append(f"{b['id']:<6} {COLOUR[b['pri']]}{b['pri']:<3}{RESET} {STATUS_COLOUR.get(s, '')}{s:<10}{RESET} "
                   f"{b['area'][:16]:<16} {b['title'][:80]}")
    counts: dict[str, int] = {}
    for b in bugs.values():
        s = status_of(b["id"], events)
        counts[s] = counts.get(s, 0) + 1
    out.append("")
    out.append(" · ".join(f"{k.lower()} {v}" for k, v in sorted(counts.items())) or "no findings yet")
    if problems:
        out.append(f"{len(problems)} format problem(s): run with --check")
    return "\n".join(out)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--unseen", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--watch", nargs="?", const=5, type=float)
    args = ap.parse_args()
    if not args.watch:
        print(render(args))
        return
    try:
        while True:
            print("\033[2J\033[H", end="")  # clear the screen
            print(time.strftime("bug watch · %H:%M:%S") + "\n")
            print(render(args))
            time.sleep(args.watch)
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()
