"""The refine system on a scratch copy of the build tree, with fake workers: no AI is started and the learner's real
usage, foundry board and vault are never touched."""
import copy
import importlib
import json
import os
import sys
import time
from pathlib import Path

import pytest

from fixtures import GRAPH

REPO = Path(__file__).resolve().parents[1]
SUB = "9702-2.1"
CARD = {"motivate": "Why this.", "establish": "The idea.", "connect": "Builds on that.", "note": "- one\n- two",
        "self_explain": "Say it in your own words."}
NOTE = ("# 2.1 Equations of motion\n\nDisplacement is a vector and distance is a scalar. For uniform "
        "acceleration use the suvat equations such as $v = u + at$.\n")


@pytest.fixture
def rf(tmp_path, monkeypatch):
    sys.path.insert(0, str(REPO / "tests"))
    from test_validate import good_pack
    pack = good_pack()
    pack["teach"] = {f"{SUB}.1": dict(CARD), f"{SUB}.4": dict(CARD)}
    for d in ("build/out/packs/9702", "build/out/specs/9702", "build/work/bundles"):
        (tmp_path / d).mkdir(parents=True)
    (tmp_path / "build/work/bundles" / f"{SUB}.md").write_text("# Bundle\n")
    (tmp_path / f"build/out/packs/9702/{SUB}.json").write_text(json.dumps(pack))
    (tmp_path / "build/out/specs/9702/graph.json").write_text(json.dumps(GRAPH))
    note = tmp_path / "build/out/notes" / pack["note"]
    note.parent.mkdir(parents=True)
    note.write_text(NOTE)
    monkeypatch.setenv("FOUNDRY_ROOT", str(tmp_path))
    monkeypatch.setenv("FOUNDRY_NOTIFY", "0")
    monkeypatch.setenv("FOUNDRY_PUBLISH", "0")
    monkeypatch.setenv("FOUNDRY_COMMIT", "0")
    fake = str(REPO / "tests/fake_worker.py")
    monkeypatch.setenv("FOUNDRY_CODEX", fake)
    monkeypatch.setenv("FOUNDRY_CLAUDE", fake)
    now = time.time()
    (tmp_path / "usage-now.json").write_text(json.dumps({
        "claude": {"seven_day": {"used": 50, "resets": now + 4 * 86400}},
        "codex": {"five_hour": {"used": 10, "resets": now + 3 * 3600}, "seven_day": {"used": 50, "resets": now + 4 * 86400}}}))
    monkeypatch.setenv("FOUNDRY_USAGE_FILE", str(tmp_path / "usage-now.json"))
    for name in ("FAKE_FAIL", "FAKE_COPY", "FAKE_REPORT", "FAKE_ARGV", "FAKE_UTILIZATION", "FAKE_REJECT"):
        monkeypatch.delenv(name, raising=False)
    sys.path.insert(0, str(REPO / "foundry"))
    sys.path.insert(0, str(REPO / "refine"))
    import foundry
    importlib.reload(foundry)
    import refine
    return importlib.reload(refine)


def finished(rf, name, tries=150):
    for _ in range(tries):
        job = rf.load(SUB)["jobs"].get(name, {})
        if job.get("finished"):
            return job
        time.sleep(0.1)
    raise AssertionError(f"{name} was never collected: {rf.load(SUB)['jobs']}")


def new_question(n=1, answer="C"):
    return {"id": f"{SUB}-r{n:02d}", "kcs": [f"{SUB}.1"], "kind": "mcq", "difficulty": 3, "command_word": "State",
            "source": {"type": "generated"}, "stem": f"Which quantity is a vector? ({n})",
            "options": {"A": "speed", "B": "distance", "C": "velocity", "D": "time"}, "answer": answer,
            "distractors": {"A": "m1"}, "marks": 1, "explanation": "Velocity has direction.", "hints": ["h1", "h2", "h3"]}


def refine_additively(rf, questions=1, line="> [!tip] Velocity is speed in a stated direction."):
    """What a good refiner does: append a question and a note line; touch nothing else."""
    p = rf.pack_path(SUB)
    pack = json.loads(p.read_text())
    pack["items"] += [new_question(n) for n in range(1, questions + 1)]
    p.write_text(json.dumps(pack))
    note = rf.note_path(pack)
    note.write_text(note.read_text() + "\n" + line + "\n")


def write_plan(rf, improvements):
    rf.WORK.mkdir(parents=True, exist_ok=True)
    rf.plan_path(SUB).write_text(json.dumps({"summary": "test", "improvements": improvements}))


PLAN = [{"kind": "questions", "where": f"{SUB}.1", "why": "only recall items", "count": 1},
        {"kind": "clarification", "where": "note Key ideas", "why": "vector vs scalar"}]


# ---------------- adding chapters ----------------
def test_add_takes_signed_chapters_and_skips_the_foundrys(rf, tmp_path):
    other = "9702-2.2"
    pack = json.loads(rf.pack_path(SUB).read_text())
    (tmp_path / f"build/out/packs/9702/{other}.json").write_text(json.dumps({**pack, "subtopic": other}))
    (tmp_path / "build/out/packs/9702/9702-3.1.json").write_text(json.dumps({**pack, "subtopic": "9702-3.1"}))
    fstate = tmp_path / "foundry/state"
    fstate.mkdir(parents=True)
    (fstate / f"{other}.json").write_text(json.dumps({"sub": other, "stage": "fix", "jobs": {}, "history": []}))
    rf.fd.HOLD.write_text(json.dumps({"9702-3.1": "in the foundry: not signed off yet"}))
    assert rf.signed_chapters() == [SUB]
    rf.cmd_add(["--all"])
    assert [st["sub"] for st in rf.chapters()] == [SUB] and rf.load(SUB)["stage"] == "plan"
    rf.cmd_add([other])  # named, but the foundry has it
    assert not (rf.STATE / f"{other}.json").exists()


def test_a_second_pass_starts_again_at_plan_and_keeps_the_count(rf):
    rf.cmd_add([SUB])
    with rf.chapter(SUB) as st:
        st.update(stage="ready", refined=1, findings=[{"ref": "x", "status": "closed"}])
    rf.cmd_add([SUB])
    st = rf.load(SUB)
    assert st["stage"] == "plan" and st["pass"] == 2 and st["refined"] == 1 and st["findings"] == []
    rf.cmd_add([SUB])  # already in a pass: left alone
    assert rf.load(SUB)["pass"] == 2


# ---------------- the snapshot and the no-loss gate ----------------
def snap_and_pack(rf):
    rf.cmd_add([SUB])
    before = rf.take_snapshot(SUB, 1)
    return before, copy.deepcopy(before["pack"])


def test_additions_pass_the_no_loss_gate(rf):
    before, pack = snap_and_pack(rf)
    pack["items"].append(new_question())
    pack["flashcards"] = (pack.get("flashcards") or []) + [{"id": "fc9", "kc": f"{SUB}.1", "front": "f", "back": "b"}]
    pack["teach"][f"{SUB}.1"]["note"] += "\n- three"  # a card gains a line
    pack["teach"][f"{SUB}.1"]["discover"] = {"stem": "s", "options": {}, "answer": "A", "explanation": "e"}
    extra = next(i for i in pack["items"] if i["id"].endswith("x10"))
    before["pack"]["items"][[i["id"] for i in pack["items"]].index(extra["id"])]["explanation"] = ""
    extra["explanation"] = "Now explained."  # an empty field filled in
    note = NOTE.replace("\n\nDisplacement", "\n\n> [!tip] New.\n\nDisplacement") + "\n## Self-test\n- Q?\n"
    assert rf.no_loss(before, pack, note) == []


@pytest.mark.parametrize("damage,expect", [
    (lambda p, n: (p["items"].pop(0), n)[1], "was removed"),
    (lambda p, n: (p["items"][0].update(answer="A"), n)[1], "`answer` was changed"),
    (lambda p, n: (p["items"][0].update(stem="Reworded."), n)[1], "`stem` was changed"),
    (lambda p, n: (p["items"][0].update(hints=["a", "b", "c"]), n)[1], "`hints` was changed"),
    (lambda p, n: (p["items"][0].update(source={"type": "past"}), n)[1], "`source` was changed"),
    (lambda p, n: (p["items"][0].pop("explanation"), n)[1], "`explanation` was removed"),
    (lambda p, n: (p["items"][0].update(kcs=[f"{SUB}.4"]), n)[1], "`kcs` was changed"),
    (lambda p, n: n.replace("Displacement is a vector", "Displacement is a VECTOR"), "note: the line"),
    (lambda p, n: n.replace("# 2.1 Equations of motion\n", ""), "note: the line"),
    (lambda p, n: (p["teach"].pop(f"{SUB}.4"), n)[1], f"teach card {SUB}.4 was removed"),
    (lambda p, n: (p["teach"][f"{SUB}.1"].pop("connect"), n)[1], "`connect` was removed"),
    (lambda p, n: (p["teach"][f"{SUB}.1"].update(note="- one"), n)[1], "lost the line"),
    (lambda p, n: (p.update(outline="Shorter."), n)[1], "`outline` was changed"),
    (lambda p, n: (p["misconceptions"].pop(), n)[1], "misconceptions: m2 was removed"),
    (lambda p, n: (p["worked"][0].update(problem="Other."), n)[1], "`problem` was changed"),
])
def test_the_no_loss_gate_names_each_kind_of_loss(rf, damage, expect):
    before, pack = snap_and_pack(rf)
    note = damage(pack, NOTE)
    problems = rf.no_loss(before, pack, note)
    assert problems and any(expect in p for p in problems), problems


def test_a_figure_questions_empty_options_must_stay_empty(rf):
    before, pack = snap_and_pack(rf)
    before["pack"]["items"][0]["options"] = None
    pack["items"][0]["options"] = {"A": "1", "B": "2", "C": "3", "D": "4"}  # "filling" a protected field
    assert any("`options` was changed" in p for p in rf.no_loss(before, pack, NOTE))


def test_the_snapshot_is_taken_once_per_pass(rf):
    rf.cmd_add([SUB])
    first = rf.ensure_snapshot(rf.load(SUB))
    refine_additively(rf)
    assert rf.ensure_snapshot(rf.load(SUB))["taken"] == first["taken"]  # a retry compares with the original
    assert len(rf.snapshot(SUB)["pack"]["items"]) == len(first["pack"]["items"])
    with rf.chapter(SUB) as st:
        st["pass"] = 2
    assert len(rf.ensure_snapshot(rf.load(SUB))["pack"]["items"]) == len(first["pack"]["items"]) + 1


def test_gates_send_a_lossy_refine_back_with_the_list(rf):
    rf.cmd_add([SUB])
    write_plan(rf, PLAN)
    rf.take_snapshot(SUB, 1)
    refine_additively(rf)
    assert rf.gates(SUB)["ok"]
    pack = json.loads(rf.pack_path(SUB).read_text())
    pack["items"][0]["answer"] = "A" if pack["items"][0].get("answer") != "A" else "B"
    rf.pack_path(SUB).write_text(json.dumps(pack))
    with rf.chapter(SUB) as st:
        st["stage"] = "refine"
    rf.cmd_collect("refiner", SUB, "-")
    st = rf.load(SUB)
    assert st["stage"] == "refine" and st["gates"]["no_loss"] >= 1
    assert "no-loss" in rf.role_prompt("refiner", SUB) and "put the original back" in rf.role_prompt("refiner", SUB)


def test_gates_check_the_plan_was_carried_out_and_ids_are_new(rf):
    rf.cmd_add([SUB])
    write_plan(rf, [{"kind": "questions", "where": "x", "why": "y", "count": 2},
                    {"kind": "diagram", "where": "note", "why": "a v-t graph"}])
    rf.take_snapshot(SUB, 1)
    refine_additively(rf)
    g = rf.gates(SUB)
    assert not g["ok"] and any("2 new questions; 1 were added" in x for x in g["first"])
    assert any("1 new diagrams; 0 were added" in x for x in g["first"])
    pack = json.loads(rf.pack_path(SUB).read_text())
    pack["items"].append({**new_question(2), "id": f"{SUB}-i99"})
    rf.pack_path(SUB).write_text(json.dumps(pack))
    assert any("must be named" in x for x in rf.gates(SUB)["first"])


def test_the_plan_is_kept_within_the_caps(rf):
    plan = {"improvements": [{"kind": "diagram", "where": str(i), "why": "w"} for i in range(5)]
            + [{"kind": "questions", "where": "a", "why": "w", "count": 6}, {"kind": "questions", "where": "b", "why": "w", "count": 6}]
            + [{"kind": "clarification", "where": str(i), "why": "w"} for i in range(7)] + [{"kind": "rewrite", "where": "x"}]}
    kept, dropped = rf.trim_plan(plan)
    kinds = [i["kind"] for i in kept["improvements"]]
    assert kinds.count("diagram") == 3 and kinds.count("clarification") == 5
    assert sum(i["count"] for i in kept["improvements"] if i["kind"] == "questions") == 8
    assert len(dropped) == 2 + 2 + 1


# ---------------- the blind solve: new questions only ----------------
def test_only_new_questions_are_stripped_for_the_blind_solve(rf):
    rf.cmd_add([SUB])
    rf.take_snapshot(SUB, 1)
    refine_additively(rf, questions=2)
    with rf.chapter(SUB) as st:
        rf.move(st, "solve", "refined")
    rf.cmd_strip(SUB)
    qs = json.loads((rf.BLIND / f"{SUB}.refine.questions.json").read_text())
    assert [q["id"] for q in qs] == [f"{SUB}-r01", f"{SUB}-r02"] and all("answer" not in q for q in qs)
    prompt = rf.role_prompt("solver", SUB)
    assert f"{SUB}.refine.questions.json" in prompt and "packs/" not in prompt and "plan" not in prompt


def test_a_wrong_new_key_is_disputed_and_old_items_are_not_asked(rf):
    rf.cmd_add([SUB])
    rf.take_snapshot(SUB, 1)
    refine_additively(rf, questions=2)
    with rf.chapter(SUB) as st:
        rf.move(st, "solve", "refined")
        st["checked"] = True
    rf.cmd_strip(SUB)
    (rf.BLIND / f"{SUB}.refine.answers.json").write_text(json.dumps({f"{SUB}-r01": "C", f"{SUB}-r02": "B"}))
    rf.cmd_compare(SUB)
    st = rf.load(SUB)
    assert st["stage"] == "tiebreak" and [d["id"] for d in st["disputes"]] == [f"{SUB}-r02"]
    assert f"{SUB}-r02" in rf.role_prompt("tiebreak", SUB) and f"{SUB}.refine.tiebreak.json" in rf.role_prompt("tiebreak", SUB)


# ---------------- the whole pass with fake workers ----------------
def test_a_pass_goes_plan_refine_solve_sign_ready_with_fake_workers(rf, tmp_path, monkeypatch):
    fstate = tmp_path / "foundry/state"
    fstate.mkdir(parents=True)
    (fstate / f"{SUB}.json").write_text(json.dumps({"sub": SUB, "stage": "ready", "jobs": {}, "history": []}))
    foundry_before = (fstate / f"{SUB}.json").read_text()
    rf.cmd_add([SUB])
    plan = tmp_path / "plan.json"
    plan.write_text(json.dumps({"summary": "one more vector question", "improvements": PLAN}))
    monkeypatch.setenv("FAKE_COPY", str(plan))
    rf.cmd_step()  # launches the scout
    finished(rf, "scout")
    assert rf.load(SUB)["stage"] == "refine" and rf.load(SUB)["plan"]["improvements"] == 2

    monkeypatch.delenv("FAKE_COPY")
    rf.ensure_snapshot(rf.load(SUB))
    refine_additively(rf)  # the fake refiner's work, done before it "runs"
    rf.cmd_run("refiner", SUB, on="claude")
    finished(rf, "refiner")
    st = rf.load(SUB)
    assert st["stage"] == "solve" and st["maker"] == "claude" and st["gates"]["ok"], st["gates"]
    assert (rf.WORK / f"{SUB}.additions.md").exists()

    right = tmp_path / "right.json"
    right.write_text(json.dumps({f"{SUB}-r01": "C"}))
    monkeypatch.setenv("FAKE_COPY", str(right))
    rf.cmd_step()  # solver (the other family) + checker
    st = rf.load(SUB)
    assert sorted(st["jobs"]) == ["checker", "refiner", "scout", "solver"] and st["jobs"]["solver"]["provider"] == "codex"
    finished(rf, "solver"), finished(rf, "checker")
    rf.cmd_step()  # compare: agreed, no findings
    assert rf.load(SUB)["stage"] == "sign"
    rf.cmd_step()  # sign
    st = rf.load(SUB)
    assert st["stage"] == "ready" and st["refined"] == 1 and st["last_refined"]
    assert st["last_additions"]["questions"] == 1 and st["last_additions"]["note_lines"] == 1
    assert (fstate / f"{SUB}.json").read_text() == foundry_before and sorted(p.name for p in fstate.iterdir()) == [f"{SUB}.json"]
    assert not rf.fd.HOLD.exists()  # a refined chapter is never held back from the vault


def test_a_plan_with_nothing_worth_adding_goes_straight_to_ready(rf, tmp_path, monkeypatch):
    rf.cmd_add([SUB])
    plan = tmp_path / "plan.json"
    plan.write_text(json.dumps({"summary": "already complete", "improvements": []}))
    monkeypatch.setenv("FAKE_COPY", str(plan))
    rf.cmd_run("scout", SUB)
    finished(rf, "scout")
    st = rf.load(SUB)
    assert st["stage"] == "ready" and "nothing worth adding" in st["history"][-1]["note"] and st.get("refined", 0) == 0


def test_an_unreadable_plan_is_a_failed_scout(rf, tmp_path, monkeypatch):
    rf.cmd_add([SUB])
    bad = tmp_path / "bad.json"
    bad.write_text("not json")
    monkeypatch.setenv("FAKE_COPY", str(bad))
    rf.cmd_run("scout", SUB, on="codex")
    job = finished(rf, "scout")
    assert not job["ok"] and rf.load(SUB)["stage"] == "plan"
    assert rf.action(rf.load(SUB)) == f"refine.py run scout {SUB}"


def test_note_only_additions_skip_the_solvers_and_only_the_checker_runs(rf, monkeypatch):
    rf.cmd_add([SUB])
    write_plan(rf, PLAN[1:])
    rf.take_snapshot(SUB, 1)
    refine_additively(rf, questions=0)
    with rf.chapter(SUB) as st:
        rf.move(st, "solve", "refined")
    rf.cmd_dispatch(SUB)
    assert sorted(rf.load(SUB)["jobs"]) == ["checker"]
    finished(rf, "checker")
    rf.cmd_step([SUB])
    assert rf.load(SUB)["stage"] == "sign"


def test_a_finding_goes_to_the_manager_and_a_fix_to_a_question_is_resolved_blind(rf):
    rf.cmd_add([SUB])
    write_plan(rf, PLAN)
    rf.take_snapshot(SUB, 1)
    refine_additively(rf)
    rf.WORK.mkdir(parents=True, exist_ok=True)
    with rf.chapter(SUB) as st:
        rf.move(st, "solve", "refined")
    (rf.WORK / f"{SUB}.check.json").write_text(json.dumps({"findings": [
        {"where": f"{SUB}-r01 hint 3", "rule": "hint gives it away", "evidence": "velocity", "fix": "say less"}]}))
    rf.cmd_strip(SUB)
    (rf.BLIND / f"{SUB}.refine.answers.json").write_text(json.dumps({f"{SUB}-r01": "C"}))
    rf.cmd_compare(SUB)
    assert rf.load(SUB)["stage"] == "adjudicate"
    rf.cmd_resolve(SUB, f"{SUB}-r01 hint 3", "fix", "Hint 3: 'Which has a direction?'")
    assert rf.load(SUB)["stage"] == "fix"
    rf.cmd_collect("fixer", SUB, "-")
    assert rf.load(SUB)["stage"] == "sign"  # the ref names a hint, not a question id: nothing to re-solve


# ---------------- routing, web, only-mode ----------------
def test_scout_and_refiner_ladders_climb_like_the_foundrys(rf):
    cfg, r = rf.config(), rf.router
    assert cfg["ladders"]["scout"]["claude"] == [["sonnet", "low"], ["sonnet", "medium"]]
    assert cfg["ladders"]["refiner"]["codex"] == [["gpt-6-sol", "medium"], ["gpt-6-astra", "medium"]]
    assert cfg["ladders"]["refiner"]["claude"][0] == ["opus", "low"]
    assert set(cfg["ladders"]) == {"scout", "refiner", "solver", "checker", "fixer", "tiebreak", "adjudicator"}
    notes = {}
    assert r.rung(notes, cfg, "refiner", "codex") == 0
    r.record(notes, cfg, "refiner", "codex", 0, ok=False)
    r.record(notes, cfg, "refiner", "codex", 0, ok=False)
    assert r.rung(notes, cfg, "refiner", "codex") == 1
    assert r.rung(notes, cfg, "scout", "codex") == 0


def test_the_refiners_family_never_solves_its_own_questions(rf):
    pick, cfg, now = rf.router.pick, rf.config(), time.time()
    left = {"claude": {"seven_day": {"used": 10.0, "resets": now + 9e5}}, "codex": {"seven_day": {"used": 90.0, "resets": now + 9e5}}}
    assert pick("solver", "claude", left, cfg, {}) == "codex"
    assert pick("tiebreak", "claude", left, cfg, {}) == "codex"
    assert pick("solver", "codex", left, cfg, {}, only="codex") == "codex"  # only-mode: there is nobody else
    assert pick("scout", None, left, cfg, {}, only="codex") == "codex"


def test_web_roles_get_web_search_on_both_allowances(rf, tmp_path):
    out = tmp_path / "o.json"
    claude = rf.worker_command("scout", "claude", "sonnet", "low", "p", out)
    assert "WebSearch" in claude[claude.index("--tools") + 1] and "WebFetch" in claude
    codex = rf.worker_command("refiner", "codex", "gpt-6-sol", "medium", "p", out)
    assert codex.index("--search") < codex.index("exec")  # a top-level Codex flag
    plain = rf.worker_command("solver", "claude", "haiku", "", "p", out)
    assert "WebSearch" not in " ".join(plain) and "--search" not in rf.worker_command("solver", "codex", "gpt-6-sol", "low", "p", out)


def test_a_launched_scout_has_web_search_on_its_command_line(rf, tmp_path, monkeypatch):
    rf.cmd_add([SUB])
    monkeypatch.setenv("FAKE_ARGV", str(tmp_path / "argv.json"))
    rf.cmd_run("scout", SUB, on="claude")
    finished(rf, "scout")
    argv = json.loads((tmp_path / "argv.json").read_text())
    assert argv[argv.index("--model") + 1] == "sonnet" and "WebSearch" in argv[argv.index("--tools") + 1]
    assert "refine/roles/scout.md" in argv[argv.index("-p") + 1]


def test_only_mode_is_the_foundrys_switch_and_marks_own_family_checks(rf, tmp_path, monkeypatch):
    rf.fd.cmd_only(["codex"])
    rf.cmd_add([SUB])
    write_plan(rf, PLAN)
    rf.take_snapshot(SUB, 1)
    refine_additively(rf)
    with rf.chapter(SUB) as st:
        st["maker"] = "codex"
        rf.move(st, "solve", "refined")
    right = tmp_path / "right.json"
    right.write_text(json.dumps({f"{SUB}-r01": "C"}))
    monkeypatch.setenv("FAKE_COPY", str(right))
    rf.cmd_dispatch(SUB)
    finished(rf, "solver"), finished(rf, "checker")
    st = rf.load(SUB)
    assert all(j["provider"] == "codex" for j in st["jobs"].values())
    rf.cmd_step()
    rf.cmd_step()
    st = rf.load(SUB)
    assert st["stage"] == "ready" and st["same_family"] is True
    with rf.fd.notes() as n:
        assert n["only"] == "codex"  # one setting, in the foundry's usage notes


def test_running_foundry_workers_count_against_the_same_slots(rf, tmp_path):
    fstate = tmp_path / "foundry/state"
    fstate.mkdir(parents=True)
    (fstate / "9702-5.1.json").write_text(json.dumps({"sub": "9702-5.1", "stage": "draft", "history": [], "jobs": {
        "drafter": {"pid": os.getpid(), "provider": "codex", "started": "2026-10-14T10:00:00+08:00"}}}))
    rf.cmd_add([SUB])
    with rf.chapter(SUB) as st:
        st["jobs"]["scout"] = {"pid": os.getpid(), "provider": "claude", "started": rf.now()}
    assert rf._busy() == {"codex": ["drafter"], "claude": ["scout"]}


# ---------------- views ----------------
def test_board_and_coverage_show_when_each_chapter_was_refined(rf, capsys):
    rf.cmd_add([SUB])
    with rf.chapter(SUB) as st:
        st.update(stage="ready", refined=2, last_refined="2026-10-14T12:00:00+08:00",
                  last_additions={"questions": 3, "diagrams": 1, "note_lines": 4, "cards": 0, "other": 0})
    rf.cmd_board()
    out = capsys.readouterr().out
    assert SUB in out and "2026-10-14" in out and "REFINED" in out
    rf.cmd_coverage([])
    out = capsys.readouterr().out
    assert "3 questions" in out and "1 diagrams" in out and "2026-10-14" in out
    c = rf.coverage()
    assert c["refined"][SUB]["passes"] == 2 and c["never"] == []


def test_coverage_lists_chapters_whose_hints_want_a_diagram(rf, tmp_path):
    graph = json.loads((tmp_path / "build/out/specs/9702/graph.json").read_text())
    graph["kcs"][0]["statement"] = "sketch displacement–time graphs"
    (tmp_path / "build/out/specs/9702/graph.json").write_text(json.dumps(graph))
    assert rf.coverage()["no_diagram"] == [SUB] and rf.coverage()["never"] == [SUB]


def test_install_skill_sets_sonnet_at_medium_effort(rf, tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    rf.cmd_install_skill()
    text = (tmp_path / "home/.claude/skills/refine/SKILL.md").read_text()
    assert "model: sonnet" in text and "effort: medium" in text and "refine/roles/manager.md" in text and "{REPO}" not in text


def test_every_role_has_its_instructions():
    for role in ("manager", "scout", "refiner", "solver", "checker", "fixer", "tiebreak", "adjudicator"):
        assert (REPO / "refine/roles" / f"{role}.md").is_file(), role
    text = (REPO / "refine/roles/refiner.md").read_text()
    assert "build/library.py" in text and "no-loss" in text
