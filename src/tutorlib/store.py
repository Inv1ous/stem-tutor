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


class Changed(Exception):
    """A file was saved by someone else (Obsidian, say) after it was read and before this write could land."""


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


_UNCHECKED = object()


def write_text(path: Path, text: str, expect=_UNCHECKED) -> bool:
    """Atomic write (temp file + rename); skips the write when nothing changed.

    `expect`, if given, is the text the caller read before building `text` (`None`: there was no file). If the file
    no longer holds `expect`, someone else saved it in between: nothing is written and `Changed` is raised, so the
    caller can redo its edit on that save instead of overwriting it."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        current = path.read_text(encoding="utf-8") if path.exists() else None
    except (OSError, ValueError):  # unreadable or torn (not valid UTF-8): just replace it
        current = _UNCHECKED
    if expect is _UNCHECKED and current == text:
        return False
    if expect is not _UNCHECKED and current != expect:
        raise Changed(str(path))
    tmp = path.with_name(f".{path.name}.{uuid.uuid4().hex[:8]}.tmp")
    tmp.write_text(text, encoding="utf-8")
    # If replacement is refused, leave the original intact: an in-place write and its restoration can both fail.
    os.replace(tmp, path)
    return True


def edit_text(path: Path, edit, tries: int = 5) -> bool:
    """Change a file somebody else may be saving too, such as a note open in Obsidian. `edit` is given the text as
    it is now (`None`: there is no file) and returns the new text, or `None` to leave the file alone. If the file
    was saved after `edit` read it, `edit` runs again on that save, so what the other writer saved is kept. True
    when the file was written."""
    path = Path(path)
    for _ in range(tries):
        before = path.read_text(encoding="utf-8") if path.exists() else None
        text = edit(before)
        if text is None:
            return False
        try:
            return write_text(path, text, expect=before)
        except Changed:
            continue
    return False  # saved again every time: leave it; the next change to this file starts from it


def _causal_events(found: list[dict], errors, regraded):
    """Release only known tag/end bindings after their prerequisites; raw records stay unchanged."""
    targets = {e.get("target") for e in found if e.get("type") == "tag" and e.get("error") in errors}
    answers = {e.get("id"): i for i, e in enumerate(found) if e.get("type") == "answer"
               and e.get("id") in targets and isinstance(e.get("grade"), dict)
               and (e.get("term_id") or isinstance(e.get("kcs"), list))}
    families, sessions = {}, {}
    for i, event in enumerate(found):
        if (event.get("type") == "tag" and event.get("target") in answers
                and event.get("target") not in regraded and event.get("error") in errors):
            families.setdefault(event["target"], []).append(i)
        if event.get("type") == "session_start" and isinstance(event.get("session"), str) and event["session"]:
            info = sessions.setdefault(event["session"], {"start": i, "last": i, "days": set(), "early": False})
            info["last"] = i
    held, at = set(), {}
    for target, indices in families.items():
        def revision(i):
            value = found[i].get("revision")
            return value if type(value) is int and value > 0 else 0

        early = [i for i in indices if i < answers[target] and not revision(i)]
        # Unrevisioned retags in different early months do not encode their true creation order.
        ambiguous = set(early) if len({str(found[i].get("ts", ""))[:7] for i in early}) > 1 else set()
        ordered = sorted((i for i in indices if i not in ambiguous),
                         key=lambda i: (bool(revision(i)), revision(i) or i, i))
        if ordered:
            position = max(answers[target], *ordered)
            at.setdefault(position, []).extend(found[i] for i in ordered)
            held.update(ordered)
    for i, event in enumerate(found):
        info = sessions.get(event.get("session")) if isinstance(event.get("session"), str) else None
        if event.get("type") == "answer" and info is not None:
            info["last"] = max(info["last"], i)
            info["early"] |= i < info["start"]
            try:
                info["days"].add(datetime.fromisoformat(event["ts"]).date().isoformat())
            except (KeyError, TypeError, ValueError):
                pass  # no invented day for an unreadable answer timestamp
    for i, event in enumerate(found):
        info = sessions.get(event.get("session")) if isinstance(event.get("session"), str) else None
        if event.get("type") == "session_end" and info is not None and (i < info["last"] or info["early"]):
            at.setdefault(max(i, info["last"]), []).append({**event, "_answer_days": sorted(info["days"])})
            held.add(i)
    for i, event in enumerate(found):
        if i not in held:
            if event.get("type") == "session_end" and "_answer_days" in event:
                event = {key: value for key, value in event.items() if key != "_answer_days"}
            yield event
        yield from at.get(i, ())


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

    def conflict_copies(self) -> dict[str, str]:
        """Contents of sync copies: an older event in one can change progress without moving the last event id."""
        return {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in self._event_files()
                if path.name != f"{path.name[:7]}.jsonl"}

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
                if not isinstance(e, dict):
                    bad_lines.append(f"{path.name}:{n}")
                    continue
                if e.get("id") is not None:  # an iCloud conflict copy ("2026-09 2.jsonl") repeats events
                    try:
                        if e["id"] in seen:
                            continue
                        seen.add(e["id"])
                    except TypeError:  # a damaged identifier must not block intact surrounding events
                        bad_lines.append(f"{path.name}:{n}")
                        continue
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
        from .grade import ERROR_CODES
        targets = {e.get("target") for e in found if e.get("type") == "tag" and e.get("error") in ERROR_CODES}
        contexts = {}  # only tagged answer targets, never an unbounded persistent answer cache
        for e in _causal_events(found, ERROR_CODES, remarks):
            if e.get("type") == "answer" and e.get("id") in remarks:
                # a right answer was no slip: drop the flag so it moves θ fully, as if marked right at first
                e = {**{k: v for k, v in e.items() if k != "slip_likely"},
                     "grade": {**e["grade"], **remarks[e["id"]]}, "regraded": True}
            elif e.get("type") == "tag" and e.get("target") in remarks:
                continue  # "why I missed it", said before the re-mark found it was not missed
            if (e.get("type") == "answer" and e.get("id") in targets and isinstance(e.get("grade"), dict)
                    and (e.get("term_id") or isinstance(e.get("kcs"), list))):
                contexts[e["id"]] = {"subject": e.get("subject", "misc"), "error": e["grade"].get("error"),
                                      "kcs": [] if e.get("term_id") else list(e.get("kcs", []))}
            elif e.get("type") == "tag":
                context = contexts.get(e.get("target"))
                if context is not None and e.get("error") in ERROR_CODES:
                    e = {**e, "answer_context": {**context, "kcs": list(context["kcs"])}}
                    context["error"] = e["error"]
                elif "answer_context" in e:
                    e = {k: v for k, v in e.items() if k != "answer_context"}
            yield e

    def last_event_id(self) -> str | None:
        """Id of the final derived event, including bindings released across raw month boundaries."""
        last = None
        for event in self.events():
            last = event.get("id")
        return last

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
        root = self.root.resolve()
        info = root.stat()
        identity = hashlib.sha1(f"{info.st_dev}:{info.st_ino}".encode()).hexdigest()[:12]
        legacy = hashlib.sha1(str(root).encode()).hexdigest()[:12]
        # Filesystem identity unifies case/Unicode aliases without conflating
        # distinct case-sensitive directories. Keep the legacy lock too, so an
        # already-running caller using this spelling still excludes new work.
        names = (f"stem-tutor-vault-{identity}.lock", f"stem-tutor-{legacy}.lock")
        descriptors = []
        try:
            deadline = time.monotonic() + wait_seconds
            for name in names:
                fd = os.open(os.path.join(tempfile.gettempdir(), name), os.O_CREAT | os.O_RDWR, 0o600)
                descriptors.append(fd)
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
            for fd in reversed(descriptors):
                os.close(fd)

    def placeholders(self) -> list[str]:
        """iCloud-evicted files show up as `.name.icloud` stubs."""
        return sorted(
            str(p.relative_to(self.root)) for p in self.root.rglob(".*.icloud")
        )
