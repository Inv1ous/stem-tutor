from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

from tutorlib import report


REPO = Path(__file__).resolve().parents[1]


def test_scratch_sessions_leave_the_learners_files_untouched(monkeypatch) -> None:
    """B-062 (bug watch): isolate both Almanac sync and the app's automatic startup imports."""
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

        # Stand in for the learner's folders outside the disposable vault. No live path is used.
        from tutor_app import config
        monkeypatch.syspath_prepend(str(REPO / "tests/app"))
        from test_tui import app_for

        inbox, downloads = root / "learner-inbox", root / "learner-downloads"
        inbox.mkdir()
        downloads.mkdir()
        pdf, export, claude = inbox / "work.pdf", downloads / "almanac-progress-2026-09-29.json", root / "claude.json"
        originals = {pdf: b"handwritten work", export: b'{"done": {"5-phys1": 1}}', claude: b"{}"}
        for path, content in originals.items():
            path.write_bytes(content)
        monkeypatch.setattr(config, "ICLOUD_INBOX", inbox)
        monkeypatch.setattr(config, "DOWNLOADS", downloads)
        monkeypatch.setattr(config, "CLAUDE_STATE", claude)
        monkeypatch.setenv("TERM_PROGRAM", "Apple_Terminal")
        monkeypatch.setenv("STEM_TUTOR_VAULT", str(root / "scratch/mnt/STEM Tutor"))
        # Execute the helper's printed Python setup, just as a scratch pilot does before startup.
        setup = done.stdout.partition("# Python setup before constructing any scratch TutorApp:\n")[2]
        exec(setup, {})
        app, vault = app_for(root / "scratch", monkeypatch)

        async def go() -> None:
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause()
                assert app.screen.__class__.__name__ == "HomeScreen"
        asyncio.run(go())

        assert all(path.is_file() and path.read_bytes() == content for path, content in originals.items()), \
            "Scratch startup moved a learner export out of its source folder"
        assert not (inbox / "Imported").exists()
        assert not (vault / "Inbox/work.pdf").exists()
        assert not (vault / "Almanac" / export.name).exists()
        assert all(path.is_relative_to(root / "scratch")
                   for path in (config.ICLOUD_INBOX, config.DOWNLOADS, config.CLAUDE_STATE))
        assert "TERM_PROGRAM" not in os.environ
