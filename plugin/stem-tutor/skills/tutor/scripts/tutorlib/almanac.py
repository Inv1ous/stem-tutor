"""What the tutor takes from the Almanac planner: the learner's own ticks and the exam dates they entered.

The planner keeps its state in the browser. It reaches the tutor in a progress file (the planner's Export button)
kept in the vault's Almanac folder; the newest file counts. What the ticks mean for the plan is in policy.py; what
the tutor gives back to the planner is in report.py (`almanac_push`).
"""
from __future__ import annotations

import re
from pathlib import Path

from .store import read_json


def latest_export(root: Path) -> Path | None:
    """The newest progress file, by when it was saved (two exports on one day differ only by a suffix)."""
    files = list((Path(root) / "Almanac").glob("almanac-progress-*.json"))
    return max(files, key=lambda p: (p.stat().st_mtime, p.name)) if files else None


def _state(root: Path) -> dict:
    """The planner's state as last exported. No file, or a damaged one, gives nothing: the tutor still runs."""
    f = latest_export(root)
    try:
        data = read_json(f) if f else None
    except (OSError, ValueError):
        data = None
    return data if isinstance(data, dict) else {}


def ticks(root: Path) -> frozenset[str]:
    """Ids of the objectives the learner ticked in the Almanac."""
    done = _state(root).get("done")
    return frozenset(k for k, v in done.items() if v) if isinstance(done, dict) else frozenset()


def exam_dates(root: Path) -> dict[int, str]:
    """Exam dates entered in the Almanac's statement of entry, by the paper's place in its list."""
    dates = _state(root).get("dates")
    return {int(k): v for k, v in (dates.items() if isinstance(dates, dict) else [])
            if str(k).isdigit() and isinstance(v, str) and re.fullmatch(r"\d{4}-\d\d-\d\d", v)}


def apply_dates(plan: dict, dates: dict[int, str]) -> None:
    """Put those dates into the plan, so countdowns and exam readiness follow what the learner entered."""
    papers = plan.get("papers") or []
    for i, day in dates.items():
        if i < len(papers):
            papers[i]["date"] = day
    if dates and papers:
        plan["sittings"] = {f"{p['short']} ({p['code'].split('/')[0]})": p["date"] for p in papers if p.get("date")}
