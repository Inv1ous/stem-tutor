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
    assert "python3 is 3.9: this needs 3.10 or newer" in r.stderr


CLT_SHIM = r'''#!/bin/bash
# /usr/bin/python3 on a Mac without the Command Line Tools: it only offers to install them
echo "xcode-select: note: No developer tools were found, requesting install." >&2
exit 1
'''


def test_a_missing_python_is_named_as_missing_not_as_a_blank_version(tmp_path):
    root, env = _setup(tmp_path)
    tools = tmp_path / "tools"  # what the launcher needs, and no python3 at all
    tools.mkdir()
    for name in ("bash", "dirname", "readlink", "sed", "rm", "touch"):
        (tools / name).symlink_to(shutil.which(name))
    r = _run(root, env, PATH=str(tools))
    assert r.returncode == 1 and "python3 not found: install Python 3.10 or newer" in r.stderr
    assert "brew install python" in r.stderr and "python3 is " not in r.stderr
    (tmp_path / "fakebin/python3").write_text(CLT_SHIM)  # there, but only the Command Line Tools' stand-in
    r = _run(root, env)
    assert r.returncode == 1 and "python3 not found" in r.stderr and "python3 is " not in r.stderr


def test_the_launcher_finds_its_folder_through_links_without_readlink_f(tmp_path):
    """macOS before 12.3 has no `readlink -f`: the folder is found by following the links one at a time."""
    root, env = _setup(tmp_path)
    assert "app ran" in _run(root, env).stdout  # set up once
    (tmp_path / "fakebin/readlink").write_text(
        '#!/bin/bash\nif [ "$1" = "-f" ]; then echo "readlink: illegal option -- f" >&2; exit 1; fi\n'
        f'exec {shutil.which("readlink")} "$@"\n')
    (tmp_path / "fakebin/readlink").chmod(0o755)
    links = tmp_path / "links"
    (links / "deeper").mkdir(parents=True)
    (links / "deeper/tutor").symlink_to("../../repo/bin/tutor")  # relative, as `ln -s` makes them
    (links / "tutor").symlink_to(links / "deeper/tutor")  # a link to a link
    r = subprocess.run(["bash", str(links / "tutor"), "doctor"], capture_output=True, text=True, env=env,
                       cwd=links, timeout=30)
    assert "Setting up" not in r.stdout and "app ran with [doctor]" in r.stdout, r.stderr
    assert not (tmp_path / ".venv").exists()
