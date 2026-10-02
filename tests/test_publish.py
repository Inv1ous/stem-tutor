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


def test_each_objective_carries_the_almanacs_own_id(tmp_path, monkeypatch):
    """The Almanac ticks an objective by id: its week, its subject and its place among that week's objectives of the
    subject, counted in the planner's own order. The plan must name objectives the same way or ticks match nothing."""
    import plan
    alm = tmp_path / "A-Levels.html"
    alm.write_text('<script>const OBJ = ['
                   '[1, "phys", "Learn", "Physical quantities", "9702 §1 · AS", "-", 1, "NEW", "A"],'
                   '[1, "exam", "Hold", "Do not start P3 yet", "-", "-", 0, "RULE", "A"],'
                   '[1, "exam", "Sit", "A first paper", "-", "-", 1, "PAPER", "A"],'
                   '[1, "phys", "Learn", "Kinematics", "9702 §2 · AS", "-", 1, "NEW", "A"]'
                   ']; const PAPERS = []; const PHASES = []; const STAGES = [];</script>', encoding="utf-8")
    monkeypatch.setattr(plan, "ALMANAC", alm)
    ids = [o["id"] for o in plan.build()["weeks"]["1"]]
    assert ids == ["1-phys1", "1-exam2", "1-phys2"]  # the dropped P3 hold still counts: the paper is the second


def test_a_tick_covers_the_objectives_own_section_and_nothing_attached_from_elsewhere(tmp_path, monkeypatch):
    """The planner names a few subtopics of a topic and leaves some sections out altogether; the plan attaches every
    remaining idea to the nearest objective. Those from the objective's own section count as ticked with it."""
    import plan
    alm = tmp_path / "A-Levels.html"
    alm.write_text('<script>const OBJ = [[1, "phys", "Learn", "Physical quantities and units — Physical quantities", '
                   '"9702 §1 · AS", "-", 1, "NEW", "A"]]; const PAPERS = []; const PHASES = []; const STAGES = [];'
                   '</script>', encoding="utf-8")
    monkeypatch.setattr(plan, "ALMANAC", alm)
    o = plan.build()["weeks"]["1"][0]
    assert any(k.startswith("9702-1.2.") for k in o["added_by_tutor"])  # the rest of topic 1, which it refers to
    assert not any(k.startswith("9702-1.") for k in o["outside"])
    assert any(k.startswith("9702-2.") for k in o["outside"])  # another topic, parked here for want of an objective
