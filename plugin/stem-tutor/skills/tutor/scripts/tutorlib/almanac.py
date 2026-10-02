"""The learner's ticks in the Almanac planner.

The planner keeps its ticks in the browser. They reach the tutor in a progress file (the planner's Export button)
kept in the vault's Almanac folder; the newest file counts. What the ticks mean for the plan is in policy.py.
"""
from __future__ import annotations

from pathlib import Path

from .store import read_json


def latest_export(root: Path) -> Path | None:
    """The newest progress file, by when it was saved (two exports on one day differ only by a suffix)."""
    files = list((Path(root) / "Almanac").glob("almanac-progress-*.json"))
    return max(files, key=lambda p: (p.stat().st_mtime, p.name)) if files else None


def ticks(root: Path) -> frozenset[str]:
    """Ids of the objectives ticked in the Almanac. No file, or a damaged one, gives no ticks: the tutor still runs."""
    f = latest_export(root)
    try:
        data = read_json(f) if f else None
    except (OSError, ValueError):
        data = None
    done = data.get("done") if isinstance(data, dict) else None
    return frozenset(k for k, v in done.items() if v) if isinstance(done, dict) else frozenset()
