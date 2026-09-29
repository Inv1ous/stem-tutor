"""Vault discovery, atomic JSON files, monthly event log, single-writer lock."""
from __future__ import annotations

import glob
import hashlib
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


class VaultNotFound(Exception):
    pass


class Locked(Exception):
    pass


def find_vault(globs: list[str] | None = None) -> Path:
    env = os.environ.get("STEM_TUTOR_VAULT")
    if env and (Path(env) / ".tutor" / "config.json").exists():
        return Path(env)
    home = Path(__file__).resolve().parents[2]  # engine published into <vault>/.tutor/engine/
    if home.name == ".tutor" and (home / "config.json").exists():
        return home.parent
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


def write_json(path: Path, data) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{uuid.uuid4().hex[:8]}.tmp")
    text = json.dumps(data, ensure_ascii=False, indent=1)
    tmp.write_text(text, encoding="utf-8")
    try:
        os.replace(tmp, path)
    except OSError:  # some mounts refuse replacing a file: write in place instead
        path.write_text(text, encoding="utf-8")
        try:
            tmp.unlink()
        except OSError:
            pass


class Vault:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.tutor = self.root / ".tutor"
        self.config = read_json(self.tutor / "config.json") or {}
        self.tz = ZoneInfo(self.config.get("tz", "Asia/Hong_Kong"))

    def now(self) -> datetime:
        return datetime.now(self.tz)

    # --- events: append-only monthly files, the source of truth ---
    def append_event(self, event: dict, now: datetime | None = None) -> dict:
        now = (now or self.now()).astimezone(self.tz)
        event = {"id": uuid.uuid4().hex[:12], "ts": now.isoformat(timespec="seconds"), **event}
        path = self.tutor / "events" / f"{now:%Y-%m}.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
        return event

    def events(self):
        folder = self.tutor / "events"
        if not folder.exists():
            return
        for path in sorted(folder.glob("*.jsonl")):
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    yield json.loads(line)

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
