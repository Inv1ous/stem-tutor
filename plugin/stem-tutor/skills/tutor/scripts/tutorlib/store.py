"""Vault discovery, atomic JSON files, monthly event log, single-writer lock."""
from __future__ import annotations

import glob
import hashlib
import heapq
import json
import os
import tempfile
import time
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

MOUNT_GLOBS = [
    os.path.expanduser("~/mnt/*"),
    "/mnt/*",
    "/sessions/*/mnt/*",
]


DEFAULT_TZ = "Asia/Hong_Kong"
EVENT_FILES ="[0-9][0-9][0-9][0-9]-[0-9][0-9]*.jsonl"  # monthly logs and their conflict copies, nothing else


class VaultNotFound(Exception):
    pass


NOT_FOUND_FIX = ("Run python3 ~/mnt/*/.tutor/engine/tutor.py <command> with device_bash, on the connected folder itself. "
                 "If no STEM Tutor folder is attached to this session, ask the learner to attach Notes/01 Study/STEM Tutor.")


class Locked(Exception):
    pass


def find_vault(globs: list[str] | None = None) -> Path:
    env = os.environ.get("STEM_TUTOR_VAULT")
    if env and (Path(env) / ".tutor" / "config.json").exists():
        return Path(env)
    home = Path(__file__).resolve().parents[2]  # engine published into <vault>/.tutor/engine/
    if home.name == ".tutor" and (home / "config.json").exists():
        root = home.parent
        seen_as = Path(os.path.abspath(__file__)).parents[3]  # the path as invoked, before resolving symlinks
        if any(r.parent.name == "mnt" or os.path.ismount(r) for r in (root, seen_as)):
            return seen_as if seen_as.parent.name == "mnt" else root
        raise VaultNotFound(f"This engine is inside a copy of the STEM Tutor folder ({root}); progress saved "
                            "there never reaches the learner.")
    for pattern in MOUNT_GLOBS if globs is None else globs:
        for hit in sorted(glob.glob(os.path.join(pattern, ".tutor", "config.json"))):
            return Path(hit).parent.parent
    raise VaultNotFound(
        "No STEM Tutor folder found. Connect 'Notes/01 Study/STEM Tutor' to this Cowork session "
        "(desktop app must be open)."
    )


def read_json(path: Path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


def write_json(path: Path, data, indent: int | None = 1) -> None:
    write_text(path, json.dumps(data, ensure_ascii=False, indent=indent,
                                separators=None if indent else (",", ":")))


def write_text(path: Path, text: str) -> bool:
    """Atomic write (temp file + rename, in-place fallback); skips the write when nothing changed."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        if path.exists() and path.read_text(encoding="utf-8") == text:
            return False
    except (OSError, ValueError):  # unreadable or torn (not valid UTF-8): just replace it
        pass
    tmp = path.with_name(f".{path.name}.{uuid.uuid4().hex[:8]}.tmp")
    tmp.write_text(text, encoding="utf-8")
    try:
        os.replace(tmp, path)
    except OSError:  # some mounts refuse replacing a file: write in place instead
        path.write_text(text, encoding="utf-8")
        try:
            tmp.unlink()
        except OSError:
            pass
    return True


class Vault:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.tutor = self.root / ".tutor"
        try:
            self.config = read_json(self.tutor / "config.json") or {}
        except (ValueError, OSError):  # torn by a crash mid-write: run on the defaults
            self.config = {}
        if not isinstance(self.config, dict):
            self.config = {}
        try:
            self.tz = ZoneInfo(self.config.get("tz", DEFAULT_TZ))
        except (KeyError, ValueError, TypeError):  # not a time zone name (ZoneInfoNotFoundError is a KeyError)
            self.tz = ZoneInfo(DEFAULT_TZ)

    def now(self) -> datetime:
        return datetime.now(self.tz)

    # --- events: append-only monthly files, the source of truth ---
    def append_event(self, event: dict, now: datetime | None = None) -> dict:
        now = (now or self.now()).astimezone(self.tz)
        event = {"id": uuid.uuid4().hex[:12], "ts": now.isoformat(timespec="seconds"), **event}
        path = self.tutor / "events" / f"{now:%Y-%m}.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "ab+") as f:
            torn = f.seek(0, os.SEEK_END) > 0 and f.seek(-1, os.SEEK_END) >= 0 and f.read(1) != b"\n"
            # after a crash mid-append, end the torn line first so this event isn't glued to it and skipped too
            f.write((("\n" if torn else "") + json.dumps(event, ensure_ascii=False) + "\n").encode("utf-8"))
        return event

    def _event_files(self) -> list[Path]:
        """The monthly files ("2026-09.jsonl") and their iCloud conflict copies ("2026-09 2.jsonl"), oldest first."""
        folder = self.tutor / "events"
        return sorted(folder.glob(EVENT_FILES)) if folder.exists() else []

    def _read_events(self, paths: list[Path], bad_lines: list[str]) -> list[dict]:
        """The events in these files, each once: month by month, each file in the order it was written."""
        seen: set = set()
        months: dict[str, list[list[tuple[float, dict]]]] = {}
        for path in paths:
            months.setdefault(path.name[:7], []).append(self._read_file(path, seen, bad_lines))
        found = []
        for month in sorted(months):
            # a conflict copy ("2026-09 2") is read before its original ("2026-09."): merge the month's files in time
            # order. Within one file the written order stands, even where the device clock stepped back, so the state
            # built as events were written is the state rebuilt from the log. Ties go to the file read first.
            found += [e for _, e in heapq.merge(*months[month], key=lambda ke: ke[0])]
        return found

    @staticmethod
    def _read_file(path: Path, seen: set, bad_lines: list[str]) -> list[tuple[float, dict]]:
        """(time, event) for the events in one file not already seen; an event without a readable time takes the time
        of the one before it."""
        out, last = [], float("-inf")
        # split the bytes on "\n" only, then decode each line: a line torn mid-character is lost alone, and a
        # U+2028 inside an answer (valid JSON) is not taken for a line break as str.splitlines() would
        for n, line in enumerate(path.read_bytes().split(b"\n"), 1):
            if line.strip():
                try:
                    e = json.loads(line.decode("utf-8"))
                except ValueError:  # a half-written line (crash mid-save) must not lock you out of your history
                    bad_lines.append(f"{path.name}:{n}")
                    continue
                if e.get("id") is not None:  # an iCloud conflict copy ("2026-09 2.jsonl") repeats events
                    if e["id"] in seen:
                        continue
                    seen.add(e["id"])
                try:
                    last = datetime.fromisoformat(e["ts"]).timestamp()  # offsets may differ: compare instants
                except (KeyError, TypeError, ValueError):
                    pass
                out.append((last, e))
        return out

    def events(self):
        if not (self.tutor / "events").exists():
            return
        self.bad_lines = []
        found = self._read_events(self._event_files(), self.bad_lines)
        remarks = {e["target"]: e["grade"] for e in found if e.get("type") == "regrade"}
        for e in found:  # an answer re-marked later is read with the re-mark: every report then agrees with it
            if e.get("type") == "answer" and e.get("id") in remarks:
                # a right answer was no slip: drop the flag so it moves θ fully, as if marked right at first
                e = {**{k: v for k, v in e.items() if k != "slip_likely"},
                     "grade": {**e["grade"], **remarks[e["id"]]}, "regraded": True}
            elif e.get("type") == "tag" and e.get("target") in remarks:
                continue  # "why I missed it", said before the re-mark found it was not missed
            yield e

    def last_event_id(self) -> str | None:
        """Id of the last event events() yields, read from the newest month's files only (it runs at every start)."""
        months: dict[str, list[Path]] = {}
        for path in self._event_files():
            months.setdefault(path.name[:7], []).append(path)
        for month in sorted(months, reverse=True):
            found = self._read_events(months[month], [])
            if found:
                if found[-1].get("type") == "tag":  # dropped by replay if its answer was re-marked, at any time
                    return next(iter(reversed(list(self.events()))), {}).get("id")
                return found[-1].get("id")
        return None

    # --- single writer ---
    @contextmanager
    def lock(self, wait_seconds: float = 15.0):
        """flock on a file outside the folder: Cowork's device_bash forbids deleting files in connected
        folders, and a flock is released by the kernel even if the process dies, so it can never go stale."""
        try:
            import fcntl
        except ImportError:  # not on POSIX: single user, run unlocked
            yield
            return
        key = hashlib.sha1(str(self.root.resolve()).encode()).hexdigest()[:12]
        fd = os.open(os.path.join(tempfile.gettempdir(), f"stem-tutor-{key}.lock"), os.O_CREAT | os.O_RDWR, 0o600)
        try:
            deadline = time.monotonic() + wait_seconds
            while True:
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if time.monotonic() > deadline:
                        raise Locked("Another tutor command is still running.") from None
                    time.sleep(0.2)
                except OSError:  # filesystem without flock support: run unlocked
                    break
            yield
        finally:
            os.close(fd)

    def placeholders(self) -> list[str]:
        """iCloud-evicted files show up as `.name.icloud` stubs."""
        return sorted(
            str(p.relative_to(self.root)) for p in self.root.rglob(".*.icloud")
        )
