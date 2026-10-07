"""bin/tutor: the one-time setup, run against a stand-in python3 in a temp folder (nothing is installed)."""
import os
import shutil
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

FAKE_PYTHON3 = r'''#!/bin/bash
# stands in for the system python3: a version check, and `-m venv DIR` making a venv whose python is FAKE_VENV_PY
if [ "$1" = "-c" ]; then exit "${FAKE_TOO_OLD:-0}"; fi
if [ "$1" = "--version" ]; then echo "Python 3.9.6"; exit 0; fi
if [ "$1" = "-m" ] && [ "$2" = "venv" ]; then
  mkdir -p "$3/bin" && cp "$FAKE_VENV_PY" "$3/bin/python" && chmod +x "$3/bin/python"; exit 0
fi
exit 9
'''

FAKE_VENV_PY = r'''#!/bin/bash
if [ "$1 $2" = "-m pip" ]; then exit "${FAKE_PIP_FAIL:-0}"; fi
if [ "$1 $2" = "-m tutor_app" ]; then shift 2; echo "app ran with [$*]"; exit 0; fi
exit 9
'''


def _setup(tmp_path):
    root = tmp_path / "repo"
    (root / "bin").mkdir(parents=True)
    (root / "app").mkdir()
    (root / "app/requirements.txt").write_text("py-fsrs\n")
    shutil.copy2(REPO / "bin/tutor", root / "bin/tutor")
    fake = tmp_path / "fakebin"
    fake.mkdir()
    (fake / "python3").write_text(FAKE_PYTHON3)
    (fake / "python3").chmod(0o755)
    (tmp_path / "venv-python").write_text(FAKE_VENV_PY)
    env = {**os.environ, "PATH": f"{fake}:{os.environ['PATH']}", "FAKE_VENV_PY": str(tmp_path / "venv-python")}
    return root, env


def _run(root, env, *args, **extra):
    return subprocess.run(["bash", str(root / "bin/tutor"), *args], capture_output=True, text=True,
                          env={**env, **extra}, timeout=30)


def test_a_failed_install_is_set_up_again_next_time(tmp_path):
    root, env = _setup(tmp_path)
    r = _run(root, env, FAKE_PIP_FAIL="1")
    assert r.returncode != 0 and "app ran" not in r.stdout
    assert not (root / ".venv").exists()  # no half-made venv left to pass for a working one
    r = _run(root, env, "doctor")
    assert "Setting up" in r.stdout and "app ran with [doctor]" in r.stdout
    assert (root / ".venv/.ready").exists()
    r = _run(root, env)
    assert "Setting up" not in r.stdout and "app ran with []" in r.stdout


def test_setup_flag_reinstalls_and_is_not_passed_to_the_app(tmp_path):
    root, env = _setup(tmp_path)
    _run(root, env)
    r = _run(root, env, "--setup")
    assert "Setting up" in r.stdout and "app ran with []" in r.stdout


def test_an_old_python_is_named_instead_of_failing_in_pip(tmp_path):
    root, env = _setup(tmp_path)
    r = _run(root, env, FAKE_TOO_OLD="1")
    assert r.returncode != 0 and "3.10" in r.stderr and "app ran" not in r.stdout
    assert not (root / ".venv").exists()
