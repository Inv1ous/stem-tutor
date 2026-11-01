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
    real_write = publish.store.write_text
    def crash(path, text, *a, **k):
        if str(path).endswith("9701-5.1.json"):
            raise OSError("disk full")
        return real_write(path, text, *a, **k)
    monkeypatch.setattr(publish.store, "write_text", crash)
    with pytest.raises(OSError):
        publish.publish(vault)
    assert sorted(p.name for p in packs.glob("v*")) == ["v1", "v2", "v3"]  # compatibility links only
    assert (packs / "CURRENT").read_text() == "v3"
    monkeypatch.setattr(publish.store, "write_text", real_write)
    assert publish.publish(vault)["version"] == "v4"
    assert sorted(p.name for p in packs.iterdir() if p.name != "CURRENT") == ["v1", "v2", "v3", "v4"]
    assert all((packs / v / "manifest.json").exists() for v in ("v1", "v2", "v3", "v4"))


def test_failed_release_copy_does_not_publish_notes_for_the_inactive_version(tmp_path, monkeypatch):
    """B-122: notes visible through Library must match the release selected by CURRENT."""
    import pytest

    build = _build(tmp_path, monkeypatch)
    vault = tmp_path / "vault"
    note = build / "notes/Subjects/9701 Chemistry/5.1 Enthalpy.md"
    assert publish.publish(vault)["version"] == "v1"
    visible = vault / "Library/Courses/9701/Notes/Published/v1/Subjects/9701 Chemistry/5.1 Enthalpy.md"
    assert visible.read_text() == "# Enthalpy\n"

    note.write_text("# New enthalpy lesson\n")
    real_write = publish.store.write_text

    def fail_pack_copy(path, text, *args, **kwargs):
        if str(path).endswith("9701-5.1.json"):
            raise OSError("injected release copy failure")
        return real_write(path, text, *args, **kwargs)

    monkeypatch.setattr(publish.store, "write_text", fail_pack_copy)
    with pytest.raises(OSError, match="injected release copy failure"):
        publish.publish(vault)

    assert (vault / ".tutor/packs/CURRENT").read_text() == "v1"
    assert visible.read_text() == "# Enthalpy\n"
    assert not list((vault / "Library/Courses/9701/Notes/Published/v2").rglob("*.md"))


def test_held_subtopic_note_stays_private_when_pack_json_is_missing(tmp_path, monkeypatch):
    """A stale review hold still protects its note after the pack JSON disappears (B-124)."""
    import json

    build = _build(tmp_path, monkeypatch)
    subtopic = "9701-8.1"
    note_rel = "Subjects/9701 Chemistry/08 Reaction kinetics/8.1 Held.md"
    note = build / "notes" / note_rel
    note.parent.mkdir(parents=True)
    note.write_text("# Still awaiting review\n")
    (build / "packs/HOLD.json").write_text(json.dumps({subtopic: "awaiting review"}))
    # Deliberately do not create packs/9701/9701-8.1.json.

    vault = tmp_path / "vault"
    result = publish.publish(vault)

    assert result["held"] == [subtopic]
    assert not list((vault / "Library/Courses/9701/Notes/Published" / result["version"]).rglob("8.1 Held.md"))
    catalog = json.loads((vault / "Library/catalog.json").read_text())
    assert not any(entry["path"].endswith("8.1 Held.md") for entry in catalog["assets"].values())
    assert (vault / ".tutor/packs/CURRENT").read_text() == result["version"]


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
    import shlex
    import subprocess
    script = publish.launcher_script()
    assert script.startswith("#!/bin/bash\n")
    assert shlex.split(script.rstrip().splitlines()[-1]) == ["exec", str(publish.ROOT / "bin/tutor")]
    assert "export STEM_TUTOR_STUDY_PROFILE=1" in script  # applied by the app within its startup budget
    assert "osascript" not in script  # no unbounded automation before the app can start
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


def test_the_launcher_runs_the_tutor_from_a_folder_with_shell_characters(tmp_path, monkeypatch):
    import os
    import subprocess
    root = tmp_path / 'it\'s "my" $HOME `x`'
    (root / "bin").mkdir(parents=True)
    (root / "bin/tutor").write_text('#!/bin/bash\necho "ran $0 $*"\n')
    (root / "bin/tutor").chmod(0o755)
    monkeypatch.setattr(publish, "ROOT", root)
    path = tmp_path / "Start Tutor.command"
    path.write_text(publish.launcher_script(tmp_path / "vault"))
    env = {k: v for k, v in os.environ.items() if k != "TERM_PROGRAM"}
    r = subprocess.run(["bash", str(path)], capture_output=True, text=True, env=env)
    assert r.returncode == 0 and f"ran {root}/bin/tutor --vault {(tmp_path / 'vault').resolve()}" in r.stdout


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
    publish.publish(vault)
    first = list((vault / "Library/Courses/9701/Notes").rglob("5.1 Enthalpy.md"))[0]
    assert "5.2 Hess's law" in first.read_text()
    original_first_bytes = first.read_bytes()
    (note.parent / "5.2 Hess’s law.md").write_text("# Hess\n")
    publish.publish(vault)
    releases = list((vault / "Library/Courses/9701/Notes").rglob("5.1 Enthalpy*.md"))
    assert any("[[" in p.read_text() for p in releases)
    publish.publish(vault)
    assert first.read_bytes() == original_first_bytes


def test_published_note_chain_and_cycle_use_final_versioned_targets(tmp_path, monkeypatch):
    import json
    from tutorlib.asset_library import AssetLibrary
    build = tmp_path / "out"
    notes = build / "notes/Subjects/P2 Pure Mathematics 2/01 Proof"
    notes.mkdir(parents=True)
    (notes / "A.md").write_text("See [[B]].\n")
    (notes / "B.md").write_text("![[Assets/P2/figure.svg]]\nSee [[A]].\n")
    (build / "Assets/P2").mkdir(parents=True)
    (build / "Assets/P2/figure.svg").write_text("<svg>diagram</svg>")
    (build / "specs/P2").mkdir(parents=True)
    (build / "specs/P2/graph.json").write_text("{}")
    (build / "packs").mkdir()
    (build / "plan.json").write_text(json.dumps({}))
    monkeypatch.setattr(publish, "BUILD", build)
    monkeypatch.setattr(publish, "ROOT", tmp_path)
    (tmp_path / "plugin/stem-tutor/skills/tutor/scripts").mkdir(parents=True)
    vault = tmp_path / "vault"

    publish.publish(vault)
    library = AssetLibrary(vault)
    a = library.resolve("build/out/notes/Subjects/P2 Pure Mathematics 2/01 Proof/A.md")
    b = library.resolve("build/out/notes/Subjects/P2 Pure Mathematics 2/01 Proof/B.md")
    figure = library.resolve("Assets/P2/figure.svg")
    a_text, b_text = a.read_text(), b.read_text()
    assert f"[[{b.relative_to(vault).as_posix()}]]" in a_text
    assert f"[[{a.relative_to(vault).as_posix()}]]" in b_text
    assert f"![[{figure.relative_to(vault).as_posix()}]]" in b_text
    assert "]](Assets/" not in b_text


def test_published_note_uses_catalogued_diagram_alias_when_build_media_is_retired(tmp_path, monkeypatch):
    from tutorlib.asset_library import AssetLibrary, write_asset

    build = tmp_path / "out"
    notes = build / "notes/Subjects/P1 Pure Mathematics/01 Algebra"
    notes.mkdir(parents=True)
    (notes / "A.md").write_text("See [[B]].\n")
    (notes / "B.md").write_text(
        "![[Assets/P1/diagram.svg#main|diagram]]\n"
        "![[build/out/assets/P1/diagram.svg]]\n"
        "[Paper](Papers/P1/source.pdf) and [source](sources/library/P1/source.pdf)\n"
    )
    # There is deliberately no build/out/Assets tree: the retired build asset
    # is available only through the immutable Library catalogue alias.
    monkeypatch.setattr(publish, "BUILD", build)
    vault = tmp_path / "vault"
    vault.mkdir()
    media = b"<svg id='main'></svg>"
    write_asset(vault, "Library/Courses/P1/Diagrams/diagram.svg", media,
                aliases=["Assets/P1/diagram.svg", "build/out/assets/P1/diagram.svg"],
                metadata={"course": "P1", "kind": "Diagrams"})
    paper = b"%PDF-1.4\nsource fixture\n"
    write_asset(vault, "Library/Courses/P1/PastPapers/P1/source.pdf", paper,
                aliases=["Papers/P1/source.pdf", "sources/library/P1/source.pdf"],
                metadata={"course": "P1", "kind": "PastPapers"})

    mapping, copied = publish._publish_library(vault, set(), "v7")
    library = AssetLibrary(vault)
    a = library.resolve("build/out/notes/Subjects/P1 Pure Mathematics/01 Algebra/A.md")
    b = library.resolve("build/out/notes/Subjects/P1 Pure Mathematics/01 Algebra/B.md")
    diagram = library.resolve("Assets/P1/diagram.svg")
    canonical_paper = library.resolve("Papers/P1/source.pdf")

    assert copied == 2
    assert f"[[{b.relative_to(vault).as_posix()}]]" in a.read_text()
    assert f"![[{diagram.relative_to(vault).as_posix()}#main|diagram]]" in b.read_text()
    assert f"![[{diagram.relative_to(vault).as_posix()}]]" in b.read_text()
    assert f"[Paper]({canonical_paper.relative_to(vault).as_posix()})" in b.read_text()
    assert f"[source]({canonical_paper.relative_to(vault).as_posix()})" in b.read_text()
    assert diagram.read_bytes() == media
    assert canonical_paper.read_bytes() == paper
    assert mapping["Assets/P1/diagram.svg"] == diagram.relative_to(vault).as_posix()


def test_publish_resolves_vault_alias_before_library_writes(tmp_path, monkeypatch):
    from tutorlib.asset_library import AssetLibrary
    _build(tmp_path, monkeypatch)
    actual = tmp_path / "vault-real"
    alias = tmp_path / "vault-alias"
    alias.symlink_to(actual, target_is_directory=True)
    publish.publish(alias)
    assert AssetLibrary(actual).records()


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
    assert list((vault / "Library").rglob("x.svg"))
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


def test_a_tag_of_only_digits_is_made_valid_for_obsidian():
    from publish import fix_tags
    assert fix_tags('---\ntags: [stem-tutor/lesson, 9701]\nspec: "9701"\n---\n# T\n#1 is body\n') == \
        '---\ntags: [stem-tutor/lesson, cie-9701]\nspec: "9701"\n---\n# T\n#1 is body\n'
    assert fix_tags("---\ntags: [stem-tutor/lesson, P2]\n---\nx") == "---\ntags: [stem-tutor/lesson, P2]\n---\nx"
    assert fix_tags("no front matter 9701") == "no front matter 9701"
    assert fix_tags("---\ntags: [stem-tutor/lesson, cie-9701]\n---\nx") == "---\ntags: [stem-tutor/lesson, cie-9701]\n---\nx"


def test_a_link_to_a_note_that_does_not_exist_is_plain_text_but_the_vaults_own_pages_stay_links():
    from publish import link_notes
    names = {"4 Differentiation", "5.2 Hess’s law"}
    text = "Builds on [[4 Differentiation]] and [[Tangents and normals]] · [[Optimisation|optimising]] · [[Home]] · [[5.2 Hess's law]]"
    assert link_notes(text, names) == ("Builds on [[4 Differentiation]] and Tangents and normals · optimising · [[Home]] · "
                                       "[[5.2 Hess’s law]]")


def test_a_link_titled_differently_finds_its_chapter_by_number_and_a_shared_word():
    """Asked by the learner: links that point at a file that exists under its real name must open it."""
    from publish import link_notes
    where = {"3.4 Covalent bonding and coordinate (dative covalent) bonding": ["Subjects/9701 Chemistry/03 Chemical bonding"],
             "12.1 Nitrogen and sulfur": ["Subjects/9701 Chemistry/12 Nitrogen and sulfur"],
             "3.4 Gravitational fields": ["Subjects/9702 Physics/03 Gravitation"],
             "3 Kinematics of a particle moving in a straight line": ["Subjects/Maths/M1 Mechanics 1"],
             "3 Kinematics": ["Subjects/Maths/P1 Pure Mathematics 1"],
             "4 Differentiation": ["Subjects/Maths/P1 Pure Mathematics 1", "Subjects/Maths/P2 Pure Mathematics 2"]}
    names = set(where)
    here = "Subjects/9701 Chemistry/13 An introduction"
    out = link_notes("[[3.4 Chemical bonding]] · [[12.1 An introduction to the chemistry of transition elements]] · "
                     "[[3.4 Covalent bonding|bonds]]", names, where, here)
    assert out == ("[[3.4 Covalent bonding and coordinate (dative covalent) bonding|3.4 Chemical bonding]] · "
                   "12.1 An introduction to the chemistry of transition elements · "  # same number, no word in common: not guessed
                   "[[3.4 Covalent bonding and coordinate (dative covalent) bonding|bonds]]")
    # another subject's chapter 3.4 is never taken, and Maths stays inside its unit
    assert link_notes("[[3.4 Chemical bonding]]", names, where, "Subjects/9702 Physics/05 Work").startswith("3.4 Chemical")
    assert link_notes("[[3 Motion in a straight line]]", names, where, "Subjects/Maths/M1 Mechanics 1") == \
        "[[3 Kinematics of a particle moving in a straight line|3 Motion in a straight line]]"
    # a title shared by several units is named by its folder; a unit code in the link picks the unit
    assert link_notes("[[P2 Differentiation]]", names, where, "Subjects/Maths/FP1 Further Pure Mathematics 1") == \
        "P2 Differentiation"  # no number and one shared word: too little to go on
    assert link_notes("[[4 Differentiation]]", names, where, "Subjects/Maths/P1 Pure Mathematics 1") == "[[4 Differentiation]]"


def test_the_shortcuts_course_is_copied_and_learner_state_is_left_alone(tmp_path, monkeypatch):
    import json
    from tutorlib.asset_library import AssetLibrary
    build = _build(tmp_path, monkeypatch)
    (build / "shortcuts/lessons").mkdir(parents=True)
    (build / "shortcuts/9702.json").write_text(json.dumps([{"id": "SEM-9702-a"}]))
    (build / "shortcuts/lessons/9702.json").write_text(json.dumps({"SEM-9702-a": {"id": "SEM-9702-a"}}))
    vault = tmp_path / "vault"
    mine = vault / ".tutor/shortcuts"
    mine.mkdir(parents=True)
    (mine / "events.jsonl").write_text('{"t": "x"}\n')
    (mine / "settings.json").write_text('{"min_score": 3}')
    assert publish.publish(vault)["shortcuts"] == 2
    course = mine / "course"
    assert json.loads((course / "9702.json").read_text())[0]["id"] == "SEM-9702-a"
    assert "SEM-9702-a" in json.loads((course / "lessons/9702.json").read_text())
    library = AssetLibrary(vault)
    entry = library.read("build/out/shortcuts/9702.json")
    lesson = library.read("build/out/shortcuts/lessons/9702.json")
    assert b"SEM-9702-a" in entry and b"SEM-9702-a" in lesson
    assert library.resolve("build/out/shortcuts/9702.json").is_relative_to(vault / "Library")
    assert (mine / "COURSE_CURRENT").read_text() == "v1"
    manifest = json.loads(library.read("Library/Shared/Shortcuts/Releases/v1/manifest.json"))
    assert manifest["entries"] == ["Library/Shared/Shortcuts/Releases/v1/Entries/9702.json"]
    assert manifest["lessons"] == ["Library/Courses/9702/Notes/Shortcuts/Published/v1/9702.json"]
    assert (mine / "events.jsonl").read_text() == '{"t": "x"}\n'
    assert (mine / "settings.json").read_text() == '{"min_score": 3}'
    assert sorted(p.name for p in mine.iterdir()) == ["COURSE_CURRENT", "course", "events.jsonl", "settings.json"]


def test_publishing_without_a_shortcuts_build_adds_no_course_folder(tmp_path, monkeypatch):
    _build(tmp_path, monkeypatch)
    vault = tmp_path / "vault"
    assert publish.publish(vault)["shortcuts"] == 0
    assert not (vault / ".tutor/shortcuts").exists()


def test_failed_shortcut_publication_does_not_advance_active_manifest(tmp_path, monkeypatch):
    import json
    import pytest
    from tutorlib import shortcuts
    from tutorlib.store import Vault
    build = _build(tmp_path, monkeypatch)
    (build / "shortcuts/lessons").mkdir(parents=True)
    entry_path = build / "shortcuts/P1.json"
    lesson_path = build / "shortcuts/lessons/P1.json"
    entry_path.write_text(json.dumps([{"id": "SEM-P1-a", "spec": "P1", "score": 9}]))
    lesson_path.write_text(json.dumps({"SEM-P1-a": {"id": "SEM-P1-a", "hook": "old"}}))
    vault = tmp_path / "vault"
    publish.publish(vault)
    pointer = vault / ".tutor/shortcuts/COURSE_CURRENT"
    assert pointer.read_text() == "v1"

    entry_path.write_text(json.dumps([{"id": "SEM-P1-a", "spec": "P1", "score": 10}]))
    lesson_path.write_text(json.dumps({"SEM-P1-a": {"id": "SEM-P1-a", "hook": "new"}}))
    real_write = publish.store.write_text
    def fail_pointer(path, text, *args, **kwargs):
        if Path(path) == pointer:
            raise OSError("pointer replace failed")
        return real_write(path, text, *args, **kwargs)
    monkeypatch.setattr(publish.store, "write_text", fail_pointer)
    with pytest.raises(OSError, match="pointer replace failed"):
        publish.publish(vault)
    assert pointer.read_text() == "v1"
    active = shortcuts.load_entries(Vault(vault))
    assert active[0]["score"] == 9 and active[0]["lesson"]["hook"] == "old"


def test_form_diagram_asset_and_reference_are_published_together(tmp_path, monkeypatch):
    import json
    from pathlib import Path
    from library_assets import read_bytes
    build = _build(tmp_path, monkeypatch)
    asset = build / 'Assets/P2/P2-1-geometry.svg'
    asset.parent.mkdir(parents=True)
    asset.write_bytes(read_bytes('build/out/Assets/P2/P2-1-geometry.svg'))
    pack_path = build / 'packs/9701/9701-5.1.json'
    pack = json.loads(pack_path.read_text())
    pack['teach'] = {'kc': {'diagrams': ['Assets/P2/P2-1-geometry.svg'],
                            'forms': [{'diagram': 'Assets/P2/P2-1-geometry.svg'}]}}
    pack_path.write_text(json.dumps(pack))
    vault = tmp_path / 'vault'
    result = publish.publish(vault)
    installed = json.loads((vault / '.tutor/packs' / result['version'] / 'specs/9701/packs/9701-5.1.json').read_text())
    assert installed['teach']['kc']['forms'][0]['diagram'].startswith('Library/Courses/P2/Diagrams/')
    assert list((vault / 'Library/Courses/P2/Diagrams').rglob('P2-1-geometry.svg'))


def test_publish_rejects_missing_item_image_before_switching_current(tmp_path, monkeypatch):
    import json
    import pytest

    build = _build(tmp_path, monkeypatch)
    vault = tmp_path / 'vault'
    assert publish.publish(vault)['version'] == 'v1'
    pack_path = build / 'packs/9701/9701-5.1.json'
    pack_path.write_text(json.dumps({'items': [{'id': 'q1', 'image': 'Assets/mcq/missing.png'}]}))

    with pytest.raises(ValueError, match='unresolved pack asset.*Assets/mcq/missing.png'):
        publish.publish(vault)

    assert (vault / '.tutor/packs/CURRENT').read_text() == 'v1'


def test_publish_rejects_missing_diagram_before_switching_current(tmp_path, monkeypatch):
    import json
    import pytest

    build = _build(tmp_path, monkeypatch)
    vault = tmp_path / 'vault'
    assert publish.publish(vault)['version'] == 'v1'
    pack_path = build / 'packs/9701/9701-5.1.json'
    pack_path.write_text(json.dumps({'teach': {'kc': {'diagrams': ['Assets/diagrams/missing.svg']}}}))

    with pytest.raises(ValueError, match='unresolved pack asset.*Assets/diagrams/missing.svg'):
        publish.publish(vault)

    assert (vault / '.tutor/packs/CURRENT').read_text() == 'v1'


def test_publish_rejects_missing_structured_diagram_before_switching_current(tmp_path, monkeypatch):
    import json
    import pytest

    build = _build(tmp_path, monkeypatch)
    vault = tmp_path / 'vault'
    assert publish.publish(vault)['version'] == 'v1'
    pack_path = build / 'packs/9701/9701-5.1.json'
    pack_path.write_text(json.dumps({'diagrams': [{'file': 'Assets/diagrams/missing.svg'}]}))

    with pytest.raises(ValueError, match='unresolved pack asset.*Assets/diagrams/missing.svg'):
        publish.publish(vault)

    assert (vault / '.tutor/packs/CURRENT').read_text() == 'v1'


def test_changed_same_name_asset_keeps_old_release_and_points_new_pack_to_new_content(tmp_path, monkeypatch):
    import hashlib
    import json
    build = _build(tmp_path, monkeypatch)
    asset = build / 'Assets/P2/figure.svg'
    asset.parent.mkdir(parents=True)
    old_bytes = b'<svg>old</svg>'
    asset.write_bytes(old_bytes)
    pack_path = build / 'packs/9701/9701-5.1.json'
    pack = json.loads(pack_path.read_text())
    pack['teach'] = {'kc': {'diagram': 'Assets/P2/figure.svg'}}
    pack_path.write_text(json.dumps(pack))
    vault = tmp_path / 'vault'
    progress = vault / '.tutor/state.json'
    progress.parent.mkdir(parents=True)
    progress.write_text('{"learner":"keep"}')
    held_note_rel = 'Subjects/9701 Chemistry/08 Reaction kinetics/8.1 Held.md'
    held_note = build / 'notes' / held_note_rel
    held_note.parent.mkdir(parents=True)
    held_note.write_text('held draft')
    held_pack = build / 'packs/9701/9701-8.1.json'
    held_pack.write_text(json.dumps({'note': held_note_rel, 'items': []}))
    hold_path = build / 'packs/HOLD.json'
    hold_path.write_text('{"9701-8.1": "awaiting review"}')

    first = publish.publish(vault)['version']
    first_pack_path = vault / '.tutor/packs' / first / 'specs/9701/packs/9701-5.1.json'
    first_pack = json.loads(first_pack_path.read_text())
    assert not (vault / '.tutor/packs' / first / 'specs/9701/packs/9701-8.1.json').exists()
    assert not list((vault / 'Library/Courses/9701/Notes').rglob('8.1 Held.md'))
    old_target = first_pack['teach']['kc']['diagram']
    old_asset = vault / old_target
    assert old_asset.read_bytes() == old_bytes
    old_catalog = json.loads((vault / 'Library/catalog.json').read_text())
    old_owners = [entry for entry in old_catalog['assets'].values() if entry['path'] == old_target]
    assert len(old_owners) == 1 and 'Assets/P2/figure.svg' in old_owners[0]['aliases']

    new_bytes = b'<svg>new</svg>'
    asset.write_bytes(new_bytes)
    source_after_change = asset.read_bytes()
    second = publish.publish(vault)['version']
    second_pack_path = vault / '.tutor/packs' / second / 'specs/9701/packs/9701-5.1.json'
    new_target = json.loads(second_pack_path.read_text())['teach']['kc']['diagram']
    new_asset = vault / new_target

    assert old_asset.read_bytes() == old_bytes
    assert new_asset.read_bytes() == new_bytes
    assert new_target != old_target and '--' in Path(new_target).name
    assert asset.read_bytes() == source_after_change
    assert json.loads(progress.read_text()) == {'learner': 'keep'}
    assert hold_path.read_text() == '{"9701-8.1": "awaiting review"}'
    # The old alias remains bound to the original immutable asset. The new pack
    # uses the direct content-version path instead of stealing that alias.
    final_catalog = json.loads((vault / 'Library/catalog.json').read_text())
    old_entry = next(e for e in final_catalog['assets'].values() if e['path'] == old_target)
    new_entry = next(e for e in final_catalog['assets'].values() if e['path'] == new_target)
    assert 'Assets/P2/figure.svg' in old_entry['aliases']
    assert 'Assets/P2/figure.svg' not in new_entry['aliases']
    assert new_entry['sha256'] == hashlib.sha256(new_bytes).hexdigest()
    assert (vault / 'Library/Releases' / first / 'manifest.json').exists()


def test_install_engine_preserves_old_runtime_and_includes_vendored_dependencies(tmp_path, monkeypatch):
    source = tmp_path / 'canonical/plugin/stem-tutor/skills/tutor/scripts'
    (source / 'tutorlib').mkdir(parents=True)
    (source / 'tutor.py').write_text('new runtime')
    (source / 'tutorlib/session.py').write_text('vendored module')
    monkeypatch.setattr(publish, 'ROOT', tmp_path / 'canonical')
    vault = tmp_path / 'vault'
    engine = vault / '.tutor/engine'
    engine.mkdir(parents=True)
    (engine / 'tutor.py').write_text('old runtime')
    archive = tmp_path / 'Archive'

    backup = publish.install_engine(vault, archive)

    assert backup is not None and backup.parent == archive
    assert (backup / 'tutor.py').read_text() == 'old runtime'
    assert (engine / 'tutor.py').read_text() == 'new runtime'
    assert (engine / 'tutorlib/session.py').read_text() == 'vendored module'


def test_failed_engine_swap_restores_previous_runtime(tmp_path, monkeypatch):
    source = tmp_path / 'canonical/plugin/stem-tutor/skills/tutor/scripts'
    source.mkdir(parents=True)
    (source / 'tutor.py').write_text('new runtime')
    monkeypatch.setattr(publish, 'ROOT', tmp_path / 'canonical')
    vault = tmp_path / 'vault'
    engine = vault / '.tutor/engine'
    engine.mkdir(parents=True)
    (engine / 'tutor.py').write_text('old runtime')
    real_replace = publish.os.replace
    count = 0

    def fail_install(src, dst):
        nonlocal count
        count += 1
        if count == 2:
            raise OSError('simulated failed activation')
        return real_replace(src, dst)

    monkeypatch.setattr(publish.os, 'replace', fail_install)
    import pytest
    with pytest.raises(OSError, match='simulated failed activation'):
        publish.install_engine(vault, tmp_path / 'Archive')
    assert (engine / 'tutor.py').read_text() == 'old runtime'
    assert not list((vault / '.tutor').glob('engine.new-*'))


def test_markdown_asset_rewrite_preserves_link_syntax_and_fenced_examples():
    source = ('![diagram](Assets/a.svg) and [source](Assets/b.pdf "source title")\n'
              '[[Assets/c.svg#shape|label]] ![[Assets/d.png]]\n'
              '`![code](Assets/a.svg)` and \\[escaped](Assets/a.svg)\n'
              '```md\n![example](Assets/a.svg)\n```\n')
    mapping = {f'Assets/{name}': f'Library/Courses/P2/Diagrams/{name}'
               for name in ('a.svg', 'b.pdf', 'c.svg', 'd.png')}
    assert publish._rewrite_markdown_assets(source, mapping) == (
        '![diagram](Library/Courses/P2/Diagrams/a.svg) and '
        '[source](Library/Courses/P2/Diagrams/b.pdf "source title")\n'
        '[[Library/Courses/P2/Diagrams/c.svg#shape|label]] '
        '![[Library/Courses/P2/Diagrams/d.png]]\n'
        '`![code](Assets/a.svg)` and \\[escaped](Assets/a.svg)\n'
        '```md\n![example](Assets/a.svg)\n```\n')


def test_explicit_candidate_overlay_publishes_candidate_without_touching_sources(tmp_path, monkeypatch):
    import json
    build = _build(tmp_path, monkeypatch)
    sub = '9701-5.1'
    pack = build / f'packs/9701/{sub}.json'
    note_rel = 'Subjects/9701 Chemistry/5.1 Enthalpy.md'
    pack.write_text(json.dumps({'subtopic': sub, 'spec': '9701', 'note': note_rel, 'outline': 'old'}))
    other = build / 'packs/9701/9701-5.2.json'
    other.write_text(json.dumps({'subtopic': '9701-5.2', 'note': note_rel, 'outline': 'untouched'}))
    candidate = tmp_path / 'Preparation/pack.json'
    candidate.parent.mkdir()
    candidate.write_text(json.dumps({'subtopic': sub, 'spec': '9701', 'note': note_rel, 'outline': 'prepared'}))
    note = candidate.with_suffix('.md')
    note.write_text('# Improved lesson\n')
    old = pack.read_bytes()
    vault = tmp_path / 'vault'
    (build / 'packs/HOLD.json').write_text(json.dumps({sub: 'pending review'}))
    result = publish.publish(vault, build_root=build, candidate=(sub, candidate, note))
    assert json.loads((build / 'packs/HOLD.json').read_text()) == {sub: 'pending review'}
    release = vault / 'Library/Releases' / result['version']
    prepared = json.loads((release / f'specs/9701/packs/{sub}.json').read_text())
    assert prepared['outline'] == 'prepared'
    assert (vault / prepared['note']).read_text() == '# Improved lesson\n'
    assert json.loads((release / 'specs/9701/packs/9701-5.2.json').read_text())['outline'] == 'untouched'
    assert pack.read_bytes() == old
    from tutorlib.asset_library import AssetLibrary
    assert AssetLibrary(vault).resolve(f'Library/Releases/{result["version"]}/specs/9701/packs/{sub}.json').is_file()


def test_candidate_identity_mismatch_fails_before_vault_is_touched(tmp_path, monkeypatch):
    import json
    import pytest
    build = _build(tmp_path, monkeypatch)
    candidate = tmp_path / 'candidate.json'
    candidate.write_text(json.dumps({'subtopic': '9702-2.1', 'note': '../unsafe.md'}))
    vault = tmp_path / 'never-created'
    with pytest.raises(ValueError, match='identity'):
        publish.publish(vault, build_root=build, candidate=('9701-5.1', candidate, candidate))
    assert not vault.exists()


def test_publisher_reads_verified_library_note_adapter(tmp_path, monkeypatch):
    import json
    from tutorlib.asset_library import write_asset
    build = _build(tmp_path, monkeypatch)
    source_vault = tmp_path / 'source-vault'
    source_vault.mkdir()
    rel = 'Subjects/9701 Chemistry/5.1 Enthalpy.md'
    canonical = 'Library/Courses/9701/Notes/original.md'
    write_asset(source_vault, canonical, b'# Catalogued original\n')
    note = build / 'notes' / rel
    note.unlink()
    note.symlink_to(source_vault / canonical)
    pack = build / 'packs/9701/9701-5.1.json'
    pack.write_text(json.dumps({'note': rel}))
    vault = tmp_path / 'vault'
    result = publish.publish(vault)
    data = json.loads((vault / f'Library/Releases/{result["version"]}/specs/9701/packs/9701-5.1.json').read_text())
    assert (vault / data['note']).is_file()
    assert (vault / data['note']).read_text() == '# Catalogued original\n'
