import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "build"))
import publish  # noqa: E402


def test_pruning_keeps_the_two_newest_previous_versions_past_v9(tmp_path):  # B-019
    for n in range(1, 13):
        (tmp_path / f"v{n}").mkdir()
        (tmp_path / f"v{n}/manifest.json").write_text("{}")
    publish.prune_versions(tmp_path, "v12")
    assert sorted(p.name for p in tmp_path.iterdir()) == ["v10", "v11", "v12"]


def test_a_version_without_a_manifest_is_no_rollback_version(tmp_path):
    """A version folder left half-written by a crashed publish has no manifest: it is removed, never kept in place of
    a real version."""
    for n in range(1, 6):
        (tmp_path / f"v{n}").mkdir()
        if n != 4:
            (tmp_path / f"v{n}/manifest.json").write_text("{}")
    publish.prune_versions(tmp_path, "v5")
    assert sorted(p.name for p in tmp_path.iterdir()) == ["v2", "v3", "v5"]


def _build(tmp_path, monkeypatch):
    """A small build to publish from, and no engine to copy."""
    import json
    build = tmp_path / "out"
    (build / "notes/Subjects/9701 Chemistry").mkdir(parents=True)
    (build / "notes/Subjects/9701 Chemistry/5.1 Enthalpy.md").write_text("# Enthalpy\n")
    (build / "specs/9701").mkdir(parents=True)
    (build / "specs/9701/graph.json").write_text("{}")
    (build / "packs/9701").mkdir(parents=True)
    (build / "packs/9701/9701-5.1.json").write_text(json.dumps({"note": "x.md"}))
    (build / "plan.json").write_text("{}")
    monkeypatch.setattr(publish, "BUILD", build)
    monkeypatch.setattr(publish, "ROOT", tmp_path)
    (tmp_path / "plugin/stem-tutor/skills/tutor/scripts").mkdir(parents=True)
    return build


def test_a_crashed_publish_leaves_no_version_that_pushes_out_a_real_one(tmp_path, monkeypatch):
    import pytest
    _build(tmp_path, monkeypatch)
    vault = tmp_path / "vault"
    packs = vault / ".tutor/packs"
    for _ in range(3):
        publish.publish(vault)
    real_copy = publish.shutil.copy2

    def crash(src, dst, *a, **k):
        if str(src).endswith("9701-5.1.json"):
            raise OSError("disk full")
        return real_copy(src, dst, *a, **k)
    monkeypatch.setattr(publish.shutil, "copy2", crash)
    with pytest.raises(OSError):
        publish.publish(vault)
    assert sorted(p.name for p in packs.glob("v*")) == ["v1", "v2", "v3"]  # nothing half-written passes for a version
    assert (packs / "CURRENT").read_text() == "v3"
    monkeypatch.setattr(publish.shutil, "copy2", real_copy)
    assert publish.publish(vault)["version"] == "v4"
    assert sorted(p.name for p in packs.iterdir() if p.name != "CURRENT") == ["v2", "v3", "v4"]
    assert all((packs / v / "manifest.json").exists() for v in ("v2", "v3", "v4"))


def test_publishing_from_an_unfinished_build_leaves_the_vault_alone(tmp_path, monkeypatch):
    import pytest
    build = _build(tmp_path, monkeypatch)
    (build / "plan.json").unlink()
    vault = tmp_path / "vault"
    with pytest.raises(SystemExit, match="plan.json"):
        publish.publish(vault)
    assert not vault.exists()


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
    assert publish.launcher_script(publish.DEFAULT_VAULT) == script  # the default vault's launcher names no vault


def test_a_launcher_published_to_another_vault_opens_that_vault(tmp_path):
    import subprocess
    vault = tmp_path / "Other's Tutor"
    script = publish.launcher_script(vault)
    import shlex
    words = shlex.split(script.rstrip().splitlines()[-1])
    assert words[1].endswith("/bin/tutor") and words[2:] == ["--vault", str(vault.resolve())]
    path = tmp_path / "Start Tutor.command"
    path.write_text(script)
    assert subprocess.run(["bash", "-n", str(path)]).returncode == 0


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


def test_links_open_published_notes_whatever_the_apostrophe():
    names = {"5.2 Hess’s law", "3.4 Chemical bonding", "Profile"}
    text = "Builds on [[3.4 Chemical bonding]] · Leads to [[5.2 Hess's law]] · see [[Profile]] ![[Assets/x.svg]]"
    assert publish.link_notes(text, names) == ("Builds on [[3.4 Chemical bonding]] · Leads to [[5.2 Hess’s law]] · "
                                               "see [[Profile]] ![[Assets/x.svg]]")
    # a chapter not published yet is plain text (clicking it would make an empty note); other links are left alone
    assert publish.link_notes("[[6.2 Electrolysis]], [[6.3 Stress|stress]], [[How It Works]]", names) == \
        "6.2 Electrolysis, stress, [[How It Works]]"


def test_a_published_note_links_once_its_target_is_published(tmp_path, monkeypatch):
    import json
    import os
    build, vault = tmp_path / "out", tmp_path / "vault"
    note = build / "notes/Subjects/9701 Chemistry/5.1 Enthalpy.md"
    note.parent.mkdir(parents=True)
    (build / "specs/9701").mkdir(parents=True)
    (build / "specs/9701/graph.json").write_text("{}")
    (build / "packs").mkdir()
    (build / "plan.json").write_text(json.dumps({}))
    note.write_text("Leads to [[5.2 Hess's law]]\n")
    monkeypatch.setattr(publish, "BUILD", build)
    monkeypatch.setattr(publish, "ROOT", tmp_path)  # no engine to copy
    (tmp_path / "plugin/stem-tutor/skills/tutor/scripts").mkdir(parents=True)
    out = vault / "Subjects/9701 Chemistry/5.1 Enthalpy.md"
    publish.publish(vault)
    assert out.read_text() == "Leads to 5.2 Hess's law\n"
    (note.parent / "5.2 Hess’s law.md").write_text("# Hess\n")
    publish.publish(vault)
    assert out.read_text() == "Leads to [[5.2 Hess’s law]]\n"
    out.write_text("my own notes\n")
    os.utime(out, (note.stat().st_mtime + 60,) * 2)  # edited in the vault after the build: kept
    publish.publish(vault)
    assert out.read_text() == "my own notes\n"


def test_a_publish_that_fails_midway_leaves_the_engine_and_pointers_whole(tmp_path, monkeypatch):
    """The engine is copied aside and swapped in; CURRENT and the launcher are replaced, never written in place."""
    import pathlib
    import pytest
    _build(tmp_path, monkeypatch)
    (tmp_path / "plugin/stem-tutor/skills/tutor/scripts/tutor.py").write_text("v1\n")
    vault = tmp_path / "vault"
    publish.publish(vault)
    engine, launcher, current = vault / ".tutor/engine", vault / "Start Tutor.command", vault / ".tutor/packs/CURRENT"
    before = launcher.read_text()
    (tmp_path / "plugin/stem-tutor/skills/tutor/scripts/tutor.py").write_text("v2\n")

    def no_copy(*a, **k):
        raise OSError("disk full")
    with monkeypatch.context() as m:
        m.setattr(publish.shutil, "copytree", no_copy)
        with pytest.raises(OSError):
            publish.publish(vault)
    assert (engine / "tutor.py").read_text() == "v1\n"  # the old engine still runs
    real_write = pathlib.Path.write_text

    def torn(self, text, *a, **k):
        if self.name in ("CURRENT", "Start Tutor.command"):
            real_write(self, text[:3], *a, **k)
            raise OSError("disk full")
        return real_write(self, text, *a, **k)
    for name in ("CURRENT", "Start Tutor.command"):
        with monkeypatch.context() as m:
            m.setattr(pathlib.Path, "write_text", torn)
            if name == "CURRENT":
                m.setattr(publish, "launcher_script", lambda v: before)
            try:
                publish.publish(vault)
            except OSError:
                pass
    assert launcher.read_text() == before and current.read_text() in ("v1", "v2", "v3", "v4")
    assert (engine / "tutor.py").read_text() == "v2\n" and not (vault / ".tutor/engine.new").exists()


def test_finder_junk_in_the_build_is_not_copied_into_the_vault(tmp_path, monkeypatch):
    build = _build(tmp_path, monkeypatch)
    (build / "notes/Subjects/.DS_Store").write_bytes(b"\0junk")
    (build / "assets").mkdir()
    (build / "assets/.DS_Store").write_bytes(b"\0junk")
    (build / "assets/x.svg").write_text("<svg/>")
    vault = tmp_path / "vault"
    publish.publish(vault)
    assert (vault / "Assets/x.svg").exists()
    assert not list(vault.rglob(".DS_*"))


def test_vault_flag_without_a_path_says_how_to_use_it(tmp_path):
    import os
    import subprocess
    env = {**os.environ, "STEM_TUTOR_VAULT": str(tmp_path / "vault")}
    r = subprocess.run([sys.executable, str(Path(publish.__file__)), "--vault"], capture_output=True, text=True,
                       env=env, cwd=tmp_path)
    assert r.returncode != 0 and "usage" in r.stderr and "Traceback" not in r.stderr
    assert not (tmp_path / "vault").exists()


def test_publishing_without_a_vault_flag_goes_where_the_app_looks(tmp_path, monkeypatch):
    """STEM_TUTOR_VAULT moves the app's vault (config.vault_path); publishing must follow it."""
    monkeypatch.setenv("STEM_TUTOR_VAULT", str(tmp_path / "vault"))
    assert publish.vault_from([]) == tmp_path / "vault"
    assert publish.vault_from(["--vault", str(tmp_path / "other")]) == tmp_path / "other"
    monkeypatch.delenv("STEM_TUTOR_VAULT")
    assert publish.vault_from([]) == publish.DEFAULT_VAULT
