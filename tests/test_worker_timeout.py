"""Deadline cleanup terminates real synthetic workers, never model providers."""
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

from tutor_workers.timeout import run
from tutor_workers import timeout as worker_timeout


def test_timeout_kills_resistant_child_after_parent_exits(tmp_path):
    pidfile = tmp_path / 'child.pid'
    child = (
        'import os,signal,time; from pathlib import Path; '
        'signal.signal(signal.SIGTERM,signal.SIG_IGN); '
        f'Path({str(pidfile)!r}).write_text(str(os.getpid())); time.sleep(60)'
    )
    parent = (
        'import subprocess,sys,time; '
        f'subprocess.Popen([sys.executable,"-c",{child!r}]); time.sleep(60)'
    )
    child_pid = None
    try:
        assert run(1.0, [sys.executable, '-c', parent]) == 124
        assert pidfile.exists(), 'synthetic child did not start; reproduction is inconclusive'
        child_pid = int(pidfile.read_text())
        deadline = time.monotonic() + 1
        while True:
            status = subprocess.run(
                ['/bin/ps', '-p', str(child_pid), '-o', 'stat='],
                capture_output=True, text=True, check=False,
            ).stdout.strip()
            if not status or status.startswith('Z'):
                break
            assert time.monotonic() < deadline, f'worker child survives timeout: {status}'
            time.sleep(0.01)
    finally:
        if child_pid is None and pidfile.exists():
            child_pid = int(pidfile.read_text())
        if child_pid is not None:
            try:
                os.kill(child_pid, signal.SIGKILL)
            except ProcessLookupError:
                pass


def test_captured_run_preserves_output_exit_and_environment(tmp_path):
    result = worker_timeout.run_captured(
        [sys.executable, '-c',
         'import os,sys; print(os.environ["WORKER_TEST"]); print(os.getcwd(), file=sys.stderr); sys.exit(7)'],
        seconds=5, cwd=tmp_path, env={**os.environ, 'WORKER_TEST': 'exact output'},
    )
    assert result.returncode == 7
    assert result.stdout == 'exact output\n'
    assert result.stderr == str(tmp_path.resolve()) + '\n'


def test_captured_timeout_kills_resistant_child_and_preserves_diagnostics(tmp_path):
    pidfile = tmp_path / 'captured-child.pid'
    child = (
        'import os,signal,time; from pathlib import Path; '
        'signal.signal(signal.SIGTERM,signal.SIG_IGN); '
        f'Path({str(pidfile)!r}).write_text(str(os.getpid())); time.sleep(60)'
    )
    parent = (
        'import subprocess,sys,time; '
        f'subprocess.Popen([sys.executable,"-c",{child!r}]); '
        'print("maker started", flush=True); print("diagnostic", file=sys.stderr, flush=True); time.sleep(60)'
    )
    try:
        import pytest
        with pytest.raises(subprocess.TimeoutExpired) as caught:
            worker_timeout.run_captured([sys.executable, '-c', parent], seconds=1)
        assert caught.value.output == 'maker started\n'
        assert caught.value.stderr == 'diagnostic\n'
        assert pidfile.exists(), 'synthetic child did not start; reproduction is inconclusive'
        status = subprocess.run(['/bin/ps', '-p', pidfile.read_text(), '-o', 'stat='],
                                capture_output=True, text=True).stdout.strip()
        assert not status or status.startswith('Z'), f'child survives captured timeout: {status}'
    finally:
        if pidfile.exists():
            try:
                os.kill(int(pidfile.read_text()), signal.SIGKILL)
            except ProcessLookupError:
                pass
