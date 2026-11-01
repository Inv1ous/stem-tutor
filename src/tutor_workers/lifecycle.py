"""Stage history, job freshness, and worker liveness shared by both boards."""
from __future__ import annotations

from datetime import datetime
import os
import uuid
from pathlib import Path
from typing import Callable


def timestamp() -> str:
    return datetime.now().astimezone().isoformat(timespec='seconds')


def transition(state: dict, stage: str, note: str = '', *, at: str | None = None) -> None:
    state['history'].append({'t': timestamp() if at is None else at,
                             'from': state['stage'], 'to': stage, 'note': note})
    state['stage'] = stage


def process_alive(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def running_jobs(state: dict, *, is_alive: Callable[[int | None], bool] | None = None) -> list[str]:
    """Finished jobs never run; unfinished manual jobs remain active without a PID."""
    is_alive = process_alive if is_alive is None else is_alive
    return [name for name, job in state['jobs'].items()
            if not job.get('finished') and (is_alive(job.get('pid')) or job.get('manual'))]


def stage_started(state: dict) -> float:
    """Latest entry into the current stage, ignoring notes that stay in that stage."""
    entered = next((step['t'] for step in reversed(state['history'])
                    if step['to'] == state['stage'] != step['from']), state['created'])
    return datetime.fromisoformat(entered).timestamp()


def job_completed(state: dict, name: str, data_root: Path) -> bool:
    """Require successful exit, an expected artifact, and completion in this stage."""
    job = state['jobs'].get(name, {})
    return bool(job.get('finished') and job.get('exit') == 0 and job.get('ok') is not False and job.get('expects')
                and (data_root / job['expects']).exists()
                and datetime.fromisoformat(job['finished']).timestamp() >= stage_started(state) - 1)


def tiebreak_completed(state: dict) -> bool:
    """Require a successful validated tiebreak from the latest review round."""
    job = state['jobs'].get('tiebreak', {})
    entered = next((step['t'] for step in reversed(state['history']) if step['to'] == 'tiebreak'), state['created'])
    return bool(job.get('finished') and job.get('exit') == 0 and job.get('ok') is not False
                and datetime.fromisoformat(job['finished']).timestamp() >= datetime.fromisoformat(entered).timestamp())


class DeadlineReached(SystemExit):
    """A course run is finished; unlike a usage wait it must not be retried."""


def course_remaining(state_dir: Path, sub: str, limit: float, *, at: float | None = None,
                     start: bool = True) -> float | None:
    """Persistent wall-clock course deadline, shared by all chapters and restarts.

    Budget files deliberately live outside the chapter glob. Inspection/signing
    never starts a budget; the first actual worker launch does.
    """
    import fcntl
    import json
    import time
    course = sub.split('-', 1)[0]
    if course in ('9701', '9702'):
        return None
    at = time.time() if at is None else at
    folder = state_dir / 'budgets'
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f'{course}.json'
    with open(folder / '.lock', 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if path.exists():
            budget = json.loads(path.read_text())
        elif start:
            budget = {'course': course, 'run_id': uuid.uuid4().hex, 'started': at, 'deadline': at + limit, 'limit_seconds': limit}
            tmp = path.with_suffix('.tmp')
            tmp.write_text(json.dumps(budget, indent=1))
            tmp.replace(path)
        else:
            return limit
    return max(0.0, budget['deadline'] - at)


def content_fingerprint(pack_file: Path, note_file: Path) -> str:
    import hashlib
    digest = hashlib.sha256(pack_file.read_bytes())
    digest.update(b'\0')
    digest.update(note_file.read_bytes() if note_file.is_file() else b'')
    return digest.hexdigest()


def serialized_launch(directory):
    """Serialize budget rotation against worker/manual launch registration."""
    import functools
    def decorate(function):
        @functools.wraps(function)
        def locked(*args, **kwargs):
            import fcntl
            folder = Path(directory(*args, **kwargs))
            folder.mkdir(parents=True, exist_ok=True)
            with open(folder / '.run.lock', 'a') as lock:
                fcntl.flock(lock, fcntl.LOCK_EX)
                return function(*args, **kwargs)
        return locked
    return decorate


@serialized_launch(lambda state_dir, *args, **kwargs: state_dir)
def new_course_run(state_dir: Path, course: str, limit: float, *, states: list[dict] | Callable[[], list[dict]],
                   at: float | None = None) -> dict:
    """Explicitly renew a course run; resume/add never resets the deadline."""
    import fcntl
    import json
    import time
    import uuid
    course = course.split('-', 1)[0]
    if not course or not course.isalnum():
        raise ValueError('course must be an alphanumeric course ID')
    states = states() if callable(states) else states
    for state in states:
        if state.get('sub', '').split('-', 1)[0] != course:
            continue
        if running_jobs(state):
            raise SystemExit(f'{course}: running workers prevent a new course run')
    at = time.time() if at is None else at
    folder = state_dir / 'budgets'
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f'{course}.json'
    with open(folder / '.lock', 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        ident = uuid.uuid4().hex
        if path.exists():
            history = folder / 'history' / course
            history.mkdir(parents=True, exist_ok=True)
            (history / f'{ident}.json').write_bytes(path.read_bytes())
        budget = {'course': course, 'run_id': ident, 'started': at,
                  'deadline': at + limit, 'limit_seconds': limit,
                  'exempt': course in ('9701', '9702')}
        tmp = path.with_suffix('.tmp')
        tmp.write_text(json.dumps(budget, indent=1))
        tmp.replace(path)
    return budget
