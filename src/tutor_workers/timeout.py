"""Run one worker under a deadline; collect remains outside this process group."""
import os
import signal
import subprocess
import sys


def _stop_group(worker):
    try:
        os.killpg(worker.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        worker.wait(timeout=2)
    except subprocess.TimeoutExpired:
        pass
    # The group can outlive its leader: a child may ignore SIGTERM even
    # when the parent exits immediately. Always finish group cleanup.
    try:
        os.killpg(worker.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    finally:
        worker.wait()


def run(seconds: float, command: list[str]) -> int:
    worker = subprocess.Popen(command, start_new_session=True)
    try:
        return worker.wait(timeout=seconds)
    except subprocess.TimeoutExpired:
        _stop_group(worker)
        return 124


def run_captured(command: list[str], *, seconds: float, cwd=None, env=None):
    """Capture one CLI's text output while bounding its whole process group."""
    worker = subprocess.Popen(command, cwd=cwd, env=env, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, text=True, start_new_session=True)
    try:
        stdout, stderr = worker.communicate(timeout=seconds)
    except subprocess.TimeoutExpired as exc:
        _stop_group(worker)
        stdout, stderr = worker.communicate()
        raise subprocess.TimeoutExpired(command, seconds, output=stdout, stderr=stderr) from exc
    except BaseException:
        _stop_group(worker)
        raise
    return subprocess.CompletedProcess(command, worker.returncode, stdout, stderr)


if __name__ == '__main__':
    sys.exit(run(float(sys.argv[1]), sys.argv[2:]))
