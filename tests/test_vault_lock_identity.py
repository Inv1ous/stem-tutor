"""Aliases of one physical learner vault must share its writer lock."""
import hashlib
import os
from pathlib import Path
import select
import subprocess
import sys
import tempfile

import pytest

from test_store import make_vault
from tutorlib import store


def child_lock(root):
    code = """
import sys
from pathlib import Path
from tutorlib import store
try:
    with store.Vault(Path(sys.argv[1])).lock(wait_seconds=0):
        print('acquired')
except store.Locked:
    print('blocked')
    sys.exit(23)
"""
    return subprocess.run([sys.executable, "-c", code, str(root)], capture_output=True, text=True,
                          timeout=5, env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")})


@pytest.mark.parametrize("alias_kind", ["case", "symlink"])
@pytest.mark.parametrize("separate_process", [False, True])
def test_physical_vault_aliases_share_lock_and_release_without_writes(tmp_path, alias_kind, separate_process):
    root = make_vault(tmp_path)
    if alias_kind == "case":
        alias = root.with_name(root.name.lower())
        if not alias.exists():
            pytest.skip("this filesystem has no case alias for the same vault")
    else:
        alias = root.with_name("vault-alias")
        alias.symlink_to(root, target_is_directory=True)
    assert alias.samefile(root)
    before = {path: path.read_bytes() for path in root.rglob("*") if path.is_file()}
    with store.Vault(root).lock(wait_seconds=0):
        if separate_process:
            result = child_lock(alias)
            assert (result.returncode, result.stdout) == (23, "blocked\n"), result.stderr
        else:
            with pytest.raises(store.Locked):
                with store.Vault(alias).lock(wait_seconds=0):
                    pass
    result = child_lock(alias)
    assert (result.returncode, result.stdout) == (0, "acquired\n"), result.stderr
    assert {path: path.read_bytes() for path in root.rglob("*") if path.is_file()} == before


def test_distinct_physical_vaults_can_lock_independently(tmp_path):
    first = make_vault(tmp_path, "STEM Tutor")
    second_name = "stem tutor" if not first.with_name("stem tutor").exists() else "Different vault"
    second = make_vault(tmp_path, second_name)
    assert not first.samefile(second)
    with store.Vault(first).lock(wait_seconds=0):
        result = child_lock(second)
        assert (result.returncode, result.stdout) == (0, "acquired\n"), result.stderr


def test_existing_legacy_path_lock_remains_authoritative(tmp_path):
    import fcntl
    root = make_vault(tmp_path)
    key = hashlib.sha1(str(root.resolve()).encode()).hexdigest()[:12]
    path = Path(tempfile.gettempdir()) / f"stem-tutor-{key}.lock"
    fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        result = child_lock(root)
        assert (result.returncode, result.stdout) == (23, "blocked\n"), result.stderr
    finally:
        os.close(fd)
    result = child_lock(root)
    assert (result.returncode, result.stdout) == (0, "acquired\n"), result.stderr


def test_process_death_releases_locks_without_manual_cleanup(tmp_path):
    root = make_vault(tmp_path)
    code = """
import sys,time
from pathlib import Path
from tutorlib import store
with store.Vault(Path(sys.argv[1])).lock(wait_seconds=0):
    print('held', flush=True)
    time.sleep(30)
"""
    process = subprocess.Popen([sys.executable, "-c", code, str(root)], stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True,
                               env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")})
    try:
        assert select.select([process.stdout], [], [], 5)[0], "lock holder did not become ready"
        assert process.stdout.readline() == "held\n"
        with pytest.raises(store.Locked):
            with store.Vault(root).lock(wait_seconds=0):
                pass
    finally:
        process.kill()
        process.communicate(timeout=5)
    with store.Vault(root).lock(wait_seconds=0):
        pass
