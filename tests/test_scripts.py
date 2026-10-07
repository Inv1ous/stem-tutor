"""The repo's helper shell scripts, run on copies in a temp folder."""
import os
import shutil
import subprocess
import uuid
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("out", ["/tmp/", "/tmp", "/tmp/.", "/tmp/x/..", "/tmp/../nonexistent-{u}/x", "/home/x"])
def test_the_sandbox_is_never_made_outside_a_folder_under_tmp(tmp_path, out):
    """sandbox.sh deletes its folder before filling it: a path that only looks as if it is under /tmp is refused,
    as is /tmp itself. rm and mkdir are stand-ins that record what they were asked to do."""
    (tmp_path / "repo/bugwatch").mkdir(parents=True)
    shutil.copy2(REPO / "bugwatch/sandbox.sh", tmp_path / "repo/bugwatch/sandbox.sh")
    fake = tmp_path / "fakebin"
    fake.mkdir()
    for name in ("rm", "mkdir"):
        (fake / name).write_text(f'#!/bin/sh\necho "{name} $*" >> "{tmp_path}/calls"\n')
        (fake / name).chmod(0o755)
    env = {**os.environ, "PATH": f"{fake}:{os.environ['PATH']}"}
    r = subprocess.run(["bash", str(tmp_path / "repo/bugwatch/sandbox.sh"), out.format(u=uuid.uuid4().hex)],
                       capture_output=True, text=True, env=env, timeout=30)
    assert r.returncode == 1 and "refusing" in r.stderr
    assert not (tmp_path / "calls").exists()


def test_the_sandbox_is_made_in_a_folder_under_tmp(tmp_path):
    (tmp_path / "repo/bugwatch").mkdir(parents=True)
    shutil.copy2(REPO / "bugwatch/sandbox.sh", tmp_path / "repo/bugwatch/sandbox.sh")
    (tmp_path / "repo/.venv/bin").mkdir(parents=True)
    (tmp_path / "repo/.venv/bin/python").write_text("#!/bin/sh\nexit 0\n")  # stands in for publishing
    (tmp_path / "repo/.venv/bin/python").chmod(0o755)
    out = Path("/tmp") / f"stem-tutor-sandbox-test-{uuid.uuid4().hex}"
    try:
        r = subprocess.run(["bash", str(tmp_path / "repo/bugwatch/sandbox.sh"), str(out)], capture_output=True,
                           text=True, timeout=30)
        assert r.returncode == 0, r.stderr
        assert (out / "mnt/STEM Tutor").is_dir()
    finally:
        shutil.rmtree(out, ignore_errors=True)


def test_packaging_the_plugin_makes_its_dist_folder(tmp_path):
    if not shutil.which("zip"):
        pytest.skip("no zip here")
    (tmp_path / "build").mkdir()
    shutil.copy2(REPO / "build/package.sh", tmp_path / "build/package.sh")
    (tmp_path / "plugin/stem-tutor/.claude-plugin").mkdir(parents=True)
    (tmp_path / "plugin/stem-tutor/.claude-plugin/plugin.json").write_text("{}")
    r = subprocess.run(["sh", str(tmp_path / "build/package.sh")], capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stderr
    assert (tmp_path / "dist/stem-tutor.plugin").is_file()
