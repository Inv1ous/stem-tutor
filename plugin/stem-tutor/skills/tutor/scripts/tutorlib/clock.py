"""Time spent studying, kept apart from the learning model (it never changes mastery, reviews or the Almanac).

Two clocks for a study session:
- **true time**: the wall clock since the session began. It keeps running while the terminal is closed (a session left
  open overnight shows the night): `session["started"]`.
- **session time**: what was really spent on the screen: counted by the app a second at a time while a study screen is
  open and the learner is there (it stops after a few minutes with no key, and while the terminal is closed).

`<vault>/.tutor/state/time.json` holds the seconds for each day (all study screens together) and for each session. The app
adds seconds with `add()`; they are written every few seconds and at the end (`flush()`).
"""
from __future__ import annotations

import json
from pathlib import Path

KEEP_DAYS, KEEP_SESSIONS = 120, 400


def fmt(seconds: float, clock: bool = False) -> str:
    """"18:42" or "1:05:09" (clock=True), else "18 min" or "1 h 05 min" (under a minute: "0 min")."""
    s = max(0, int(seconds))
    h, rest = divmod(s, 3600)
    m, sec = divmod(rest, 60)
    if clock:
        return f"{h}:{m:02d}:{sec:02d}" if h else f"{m:02d}:{sec:02d}"
    return f"{h} h {m:02d} min" if h else f"{m} min"


class StudyClock:
    def __init__(self, vault) -> None:
        self.path = Path(vault.tutor) / "state" / "time.json"
        self.data = self._read()
        self._dirty = False

    def _read(self) -> dict:
        try:
            data = json.loads(self.path.read_text())
            if isinstance(data, dict):
                return {"days": dict(data.get("days") or {}), "sessions": dict(data.get("sessions") or {}),
                        "day_sessions": dict(data.get("day_sessions") or {})}
        except (OSError, ValueError):
            pass  # no file yet, or a damaged one: counting starts again, nothing else is lost
        return {"days": {}, "sessions": {}, "day_sessions": {}}

    def add(self, day: str, seconds: float, session_id: str | None = None) -> None:
        if seconds <= 0:
            return
        self.data["days"][day] = round(self.data["days"].get(day, 0.0) + seconds, 2)
        if session_id:
            self.data["sessions"][session_id] = round(self.data["sessions"].get(session_id, 0.0) + seconds, 2)
            ids = self.data["day_sessions"].setdefault(day, [])
            if session_id not in ids:
                ids.append(session_id)
        self._dirty = True

    def today(self, day: str) -> float:
        return float(self.data["days"].get(day, 0.0))

    def sessions_on(self, day: str) -> int:
        return len(self.data["day_sessions"].get(day, []))

    def session(self, session_id: str | None) -> float:
        return float(self.data["sessions"].get(session_id or "", 0.0))

    def flush(self) -> None:
        """Write what has been added since. Never raises: a read-only vault loses the count, not the lesson."""
        if not self._dirty:
            return
        days = dict(sorted(self.data["days"].items())[-KEEP_DAYS:])
        sessions = dict(list(self.data["sessions"].items())[-KEEP_SESSIONS:])  # oldest first: dicts keep insertion order
        day_sessions = {d: v for d, v in self.data["day_sessions"].items() if d in days}
        self.data = {"days": days, "sessions": sessions, "day_sessions": day_sessions}
        try:
            from .store import write_text
            write_text(self.path, json.dumps(self.data, indent=1))
            self._dirty = False
        except OSError:
            pass
