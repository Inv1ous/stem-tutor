import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "build"))
import publish  # noqa: E402


def test_pruning_keeps_the_two_newest_previous_versions_past_v9(tmp_path):  # B-019
    for n in range(1, 13):
        (tmp_path / f"v{n}").mkdir()
    publish.prune_versions(tmp_path, "v12")
    assert sorted(p.name for p in tmp_path.iterdir()) == ["v10", "v11", "v12"]


def test_the_plan_records_which_almanac_it_was_built_from(tmp_path, monkeypatch):
    import hashlib
    import plan
    alm = tmp_path / "A-Levels.html"
    alm.write_text('<script>const OBJ = [[1, "phys", "Learn", "Physical quantities", "9702 §1 · AS", "-", 1, "NEW", '
                   '"A"]]; const PAPERS = []; const PHASES = []; const STAGES = [];</script>', encoding="utf-8")
    monkeypatch.setattr(plan, "ALMANAC", alm)
    p = plan.build()
    assert p["source_path"] == str(alm)
    assert p["source_sha256"] == hashlib.sha256(alm.read_bytes()).hexdigest()
    assert p["weeks"]["1"][0]["kcs"]  # the objective still maps to syllabus ideas


def test_the_launcher_opens_the_tutor_in_the_study_profile(tmp_path):
    """Asked by the learner: the double-click launcher should open in their Terminal profile "Study"."""
    import subprocess
    script = publish.launcher_script()
    assert script.startswith("#!/bin/bash\n") and script.rstrip().endswith('/bin/tutor"')
    assert 'settings set "Study"' in script and '"$(tty)"' in script  # this window only, and only if the profile exists
    assert "Apple_Terminal" in script  # other terminals are asked nothing
    path = tmp_path / "Start Tutor.command"
    path.write_text(script)
    assert subprocess.run(["bash", "-n", str(path)]).returncode == 0  # the shell can read it
