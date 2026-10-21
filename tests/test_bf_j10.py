from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

from tutorlib import report


REPO = Path(__file__).resolve().parents[1]


def test_scratch_sessions_never_write_to_the_learners_almanac(monkeypatch) -> None:
    """B-062 (bug watch): the sandbox must remove the published plan's live sync destination."""
    with tempfile.TemporaryDirectory(dir="/tmp", prefix="bf-j10-") as directory:
        root = Path(directory)
        (root / "bugwatch").mkdir()
        shutil.copy2(REPO / "bugwatch/sandbox.sh", root / "bugwatch/sandbox.sh")
        (root / ".venv/bin").mkdir(parents=True)
        (root / ".venv/bin/python").symlink_to(sys.executable)
        (root / "plugin").symlink_to(REPO / "plugin", target_is_directory=True)
        planner = root / "A-Levels.html"
        planner.write_text("<html></html>", encoding="utf-8")
        original = {"source": planner.name, "source_path": str(planner), "source_sha256": "abc",
                    "weeks": {"1": [{"title": "Kinematics"}]}}
        (root / "plan.json").write_text(json.dumps(original), encoding="utf-8")
        (root / "build").mkdir()
        # Stand in for publishing; never run the real content pipeline or copy the learner's data.
        (root / "build/publish.py").write_text(
            "import sys, shutil\nfrom pathlib import Path\n"
            "packs = Path(sys.argv[2]) / '.tutor/packs'\n"
            "(packs / 'v7').mkdir(parents=True)\n"
            "(packs / 'CURRENT').write_text('v7\\n')\n"
            "shutil.copy2(Path(__file__).parents[1] / 'plan.json', packs / 'v7/plan.json')\n",
            encoding="utf-8",
        )
        done = subprocess.run(["bash", str(root / "bugwatch/sandbox.sh"), str(root / "scratch")],
                              capture_output=True, text=True, timeout=30)
        assert done.returncode == 0, done.stderr
        plan = json.loads((root / "scratch/mnt/STEM Tutor/.tutor/packs/v7/plan.json").read_text())
        written = []
        monkeypatch.setattr(report, "_write_text", lambda path, text: written.append(path))
        monkeypatch.setattr(report, "almanac_payload", lambda tutor: {})
        report.almanac_push(SimpleNamespace(packs=SimpleNamespace(plan=plan)))
        assert written == [], "A scratch session would overwrite the learner's Almanac sidecar"
        assert plan == {"source": planner.name, "weeks": original["weeks"]}
        assert json.loads((root / "plan.json").read_text()) == original
