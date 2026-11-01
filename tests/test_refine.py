"""The refine system on a scratch copy of the build tree, with fake workers: no AI is started and the learner's real
usage, foundry board and vault are never touched."""
from library_assets import read_json as library_json
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
    monkeypatch.setenv("FOUNDRY_PREGEN", "0")  # no audio pre-generation (nor the learner's vault) from tests
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
    mod = importlib.reload(refine)
    real = mod.config

    def neutral() -> dict:  # the learner's own pacing choices (a Codex reserve, a five-hour cap) are not under test
        cfg = real()
        cfg["reserve"]["codex"] = 0
        cfg["window_cap"] = {}
        cfg["weekly_launch_cap"] = 100  # neutral routing fixtures; reserve policy has dedicated regressions
        cfg.pop("focus", None)  # the learner's chapter list is not under test
        for role, ladders in CODEX_LADDERS.items():  # fixed two-family routing, not the shipped Claude-only config
            cfg["ladders"].setdefault(role, {}).update(ladders)
        for role, weight in CODEX_WEIGHTS.items():
            cfg["weights"].setdefault("codex", {})[role] = weight
        cfg["max_parallel"].setdefault("codex", 3)  # the foundry's Codex slots
        return cfg
    mod.config = neutral
    return mod


# Codex routing is tested against these fixed ladders and weights: the shipped refine config is Claude-only, and a
# learner's live config must not decide what these tests cover.
CODEX_LADDERS = {
    "scout": {"codex": [["gpt-6.1-terra", "low"], ["gpt-6.1-terra", "medium"]]},
    "refiner": {"codex": [["gpt-6.1-terra", "medium"], ["gpt-6.1-sol", "medium"]]},
    "solver": {"codex": [["gpt-6.1-terra", "low"], ["gpt-6.1-terra", "medium"]]},
    "checker": {"codex": [["gpt-6.1-terra", "low"], ["gpt-6.1-terra", "medium"]]},
    "tiebreak": {"codex": [["gpt-6.1-terra", "low"], ["gpt-6.1-terra", "medium"]]},
}
CODEX_WEIGHTS = {"scout": 0.6, "refiner": 2.0, "solver": 0.15, "checker": 0.2, "tiebreak": 0.2}


def test_shipped_refine_config_routes_both_families_on_known_tiers():
    """Refine can run on either allowance (the learner chooses with `only`); every role has both ladders, on the
    documented tiers, so a one-family preference never leaves a role with nobody to run it."""
    shipped = json.loads((REPO / "refine" / "config.json").read_text())
    for role, ladders in shipped["ladders"].items():
        assert set(ladders) == {"claude", "codex"}, f"{role}: {sorted(ladders)}"
        for model, effort in ladders["codex"]:
            assert model in {"gpt-6.1-sol", "gpt-6.1-terra", "gpt-6-luna"}, f"{role}: unexpected Codex model {model}"
            assert isinstance(effort, str)
    assert set(shipped["weights"]) == {"claude", "codex"}
    assert set(shipped["reserve"]) == {"claude", "codex"} and set(shipped["max_parallel"]) == {"claude", "codex"}


def test_shipped_refine_config_ladders_are_claude_models():
    shipped = json.loads((REPO / "refine" / "config.json").read_text())
    for role, ladders in shipped["ladders"].items():
        for model, effort in ladders["claude"]:
            assert model in {"claude-haiku-5-5", "sonnet", "opus"}, f"{role}: unexpected Claude model {model}"
            assert isinstance(effort, str)


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
    rf.cmd_add(["--all", "--scope", "full"])
    assert [st["sub"] for st in rf.chapters()] == [SUB] and rf.load(SUB)["stage"] == "plan"
    rf.cmd_add([other, "--scope", "full"])  # named, but the foundry has it
    assert not (rf.STATE / f"{other}.json").exists()


def test_a_second_pass_starts_again_at_plan_and_keeps_the_count(rf):
    rf.cmd_add([SUB, "--scope", "full"])
    with rf.chapter(SUB) as st:
        st.update(stage="ready", refined=1, findings=[{"ref": "x", "status": "closed"}])
    rf.cmd_add([SUB, "--scope", "full"])
    st = rf.load(SUB)
    assert st["stage"] == "plan" and st["pass"] == 2 and st["refined"] == 1 and st["findings"] == []
    rf.cmd_add([SUB, "--scope", "full"])  # already in a pass: left alone
    assert rf.load(SUB)["pass"] == 2


# ---------------- the snapshot and the no-loss gate ----------------
def snap_and_pack(rf):
    rf.cmd_add([SUB, "--scope", "full"])
    before = rf.take_snapshot(SUB, 1)
    return before, copy.deepcopy(before["pack"])


def test_guided_probe_preserves_the_original_discover_question(rf):
    before, pack = snap_and_pack(rf)
    kc = f'{SUB}.1'
    old = {'stem': 'Original', 'options': {'A': 'one'}, 'answer': 'A', 'explanation': 'Reason'}
    before['pack']['teach'][kc]['discover'] = copy.deepcopy(old)
    pack['teach'][kc]['discover'] = copy.deepcopy(old)
    pack['teach'][kc]['guided_discover'] = {'stem': 'Separate', 'options': {'A': 'two'}, 'answer': 'A'}
    assert rf.no_loss(before, pack, NOTE) == []
    pack['teach'][kc]['discover']['stem'] = 'Changed'
    assert any('discover' in issue for issue in rf.no_loss(before, pack, NOTE))


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
    rf.cmd_add([SUB, "--scope", "full"])
    first = rf.ensure_snapshot(rf.load(SUB))
    refine_additively(rf)
    assert rf.ensure_snapshot(rf.load(SUB))["taken"] == first["taken"]  # a retry compares with the original
    assert len(rf.snapshot(SUB)["pack"]["items"]) == len(first["pack"]["items"])
    with rf.chapter(SUB) as st:
        st["pass"] = 2
    assert len(rf.ensure_snapshot(rf.load(SUB))["pack"]["items"]) == len(first["pack"]["items"]) + 1


def test_gates_send_a_lossy_refine_back_with_the_list(rf):
    rf.cmd_add([SUB, "--scope", "full"])
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
    rf.cmd_add([SUB, "--scope", "full"])
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
    rf.cmd_add([SUB, "--scope", "full"])
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
    rf.cmd_add([SUB, "--scope", "full"])
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
    rf.cmd_add([SUB, "--scope", "full"])
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


def test_failed_publish_does_not_mark_refine_pass_ready(rf, monkeypatch):
    from types import SimpleNamespace
    rf.cmd_add([SUB, "--scope", "full"])
    rf.take_snapshot(SUB, 1)
    with rf.chapter(SUB) as st:
        rf.move(st, 'sign', 'ready for test')
    monkeypatch.setattr(rf.fd, 'settle_glyphs', lambda *args, **kwargs: ({'ok': True}, None))
    monkeypatch.setenv('FOUNDRY_PUBLISH', '1')
    calls = []
    def failed_publish(args, **kwargs):
        calls.append(args)
        return SimpleNamespace(returncode=1, stdout='', stderr='injected publisher failure')
    monkeypatch.setattr(rf.subprocess, 'run', failed_publish)
    base = rf.config
    monkeypatch.setattr(rf, 'config', lambda: {**base(), 'publish_on_sign': True})  # the shipped default is off
    with pytest.raises(RuntimeError, match='PUBLISH FAILED'):
        rf.cmd_sign(SUB)
    st = rf.load(SUB)
    assert st['stage'] == 'sign' and not st.get('refined')
    assert len(calls) == 1 and calls[0][1].endswith('build/publish.py')


def test_a_plan_with_nothing_worth_adding_goes_straight_to_ready(rf, tmp_path, monkeypatch):
    rf.cmd_add([SUB, "--scope", "full"])
    plan = tmp_path / "plan.json"
    plan.write_text(json.dumps({"summary": "already complete", "improvements": []}))
    monkeypatch.setenv("FAKE_COPY", str(plan))
    rf.cmd_run("scout", SUB)
    finished(rf, "scout")
    st = rf.load(SUB)
    assert st["stage"] == "ready" and "nothing worth adding" in st["history"][-1]["note"] and st.get("refined", 0) == 0


def test_an_unreadable_plan_is_a_failed_scout(rf, tmp_path, monkeypatch):
    rf.cmd_add([SUB, "--scope", "full"])
    bad = tmp_path / "bad.json"
    bad.write_text("not json")
    monkeypatch.setenv("FAKE_COPY", str(bad))
    rf.cmd_run("scout", SUB, on="codex")
    job = finished(rf, "scout")
    assert not job["ok"] and rf.load(SUB)["stage"] == "plan"
    assert rf.action(rf.load(SUB)) == f"refine.py run scout {SUB}"


def test_note_only_additions_skip_the_solvers_and_only_the_checker_runs(rf, monkeypatch):
    rf.cmd_add([SUB, "--scope", "full"])
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
    rf.cmd_add([SUB, "--scope", "full"])
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
    assert cfg["ladders"]["refiner"]["codex"] == [["gpt-6.1-terra", "medium"], ["gpt-6.1-sol", "medium"]]
    assert cfg["ladders"]["refiner"]["claude"][0] == ["opus", "low"]
    assert set(cfg["ladders"]) == {"scout", "refiner", "solver", "checker", "fixer", "tiebreak", "adjudicator",
                                   "wsolver", "wreviewer"}
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
    codex = rf.worker_command("refiner", "codex", "gpt-6.1-terra", "medium", "p", out)
    assert codex.index("--search") < codex.index("exec")  # a top-level Codex flag
    plain = rf.worker_command("solver", "claude", "haiku", "", "p", out)
    assert "WebSearch" not in " ".join(plain) and "--search" not in rf.worker_command("solver", "codex", "gpt-6.1-terra", "low", "p", out)


def test_a_launched_scout_has_web_search_on_its_command_line(rf, tmp_path, monkeypatch):
    rf.cmd_add([SUB, "--scope", "full"])
    monkeypatch.setenv("FAKE_ARGV", str(tmp_path / "argv.json"))
    rf.cmd_run("scout", SUB, on="claude")
    finished(rf, "scout")
    argv = json.loads((tmp_path / "argv.json").read_text())
    assert argv[argv.index("--model") + 1] == "sonnet" and "WebSearch" in argv[argv.index("--tools") + 1]
    assert "refine/roles/scout.md" in argv[argv.index("-p") + 1]


def test_only_mode_is_the_foundrys_switch_and_marks_own_family_checks(rf, tmp_path, monkeypatch):
    rf.fd.cmd_only(["codex"])
    rf.cmd_add([SUB, "--scope", "full"])
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
    rf.cmd_add([SUB, "--scope", "full"])
    with rf.chapter(SUB) as st:
        st["jobs"]["scout"] = {"pid": os.getpid(), "provider": "claude", "started": rf.now()}
    assert rf._busy() == {"codex": ["drafter"], "claude": ["scout"]}


# ---------------- views ----------------
def test_board_and_coverage_show_when_each_chapter_was_refined(rf, capsys):
    rf.cmd_add([SUB, "--scope", "full"])
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


# ---------------- figures cropped from the learner's PDFs ----------------
def figure_env(rf, tmp_path, monkeypatch):
    """A tiny library PDF and the asset folder inside the scratch tree; returns a function that crops a figure."""
    sys.path.insert(0, str(REPO / "tests"))
    sys.path.insert(0, str(REPO / "build"))
    import library
    import test_library as tl
    monkeypatch.setenv("STEM_LIBRARY_ROOT", str(tmp_path / "sources/library"))
    monkeypatch.setenv("STEM_LIBRARY_ASSETS", str(tmp_path / "build/out/assets"))
    tl.make_figure_pdf(tmp_path / "sources/library/Book.pdf", [{"ops": tl.VECTOR}])

    def crop(name, **kw):
        args = ["crop", "book", "--page", "1", "--box", "0,0.1,1,0.5", "--to", f"9702/{name}", "--caption", "A test",
                "--for", SUB]
        assert library.main(args) == 0
        return f"![[Assets/9702/{name}.png]]\n*Figure: A test (source: Book, p.1)*"
    return crop


def add_to_note(rf, text):
    note = rf.note_path(json.loads(rf.pack_path(SUB).read_text()))
    note.write_text(note.read_text() + "\n" + text + "\n")


def test_figures_are_their_own_kind_with_their_own_cap(rf):
    fig = {"kind": "figure", "pdf": "Book.pdf", "page": 3, "box": [0, 0.1, 1, 0.5], "caption": "c", "kc": f"{SUB}.1", "why": "w"}
    plan = {"improvements": [{"kind": "diagram", "where": str(i), "why": "w"} for i in range(3)]
            + [{**fig, "page": i} for i in range(1, 6)] + [{"kind": "figure", "where": "x", "why": "no pdf or box"}]}
    kept, dropped = rf.trim_plan(plan)
    kinds = [i["kind"] for i in kept["improvements"]]
    assert kinds.count("diagram") == 3 and kinds.count("figure") == 3
    assert len(dropped) == 2 + 1 and any("not an improvement" in d for d in dropped)


def test_gates_want_the_planned_figure_as_an_embedded_file_with_its_source(rf, tmp_path, monkeypatch):
    crop = figure_env(rf, tmp_path, monkeypatch)
    rf.cmd_add([SUB, "--scope", "full"])
    write_plan(rf, [{"kind": "figure", "pdf": "Book.pdf", "page": 1, "box": [0, 0.1, 1, 0.5], "caption": "A test", "why": "w"}])
    rf.take_snapshot(SUB, 1)
    refine_additively(rf)
    assert any("plan asks for 1 new figures; 0 were embedded" in x for x in rf.gates(SUB)["first"])
    lines = crop("fig-a")
    assert any("cropped but not embedded: fig-a.png" in x for x in rf.gates(SUB)["first"])
    add_to_note(rf, lines)
    g = rf.gates(SUB)
    assert g["ok"], g.get("first")
    add_to_note(rf, "![[Assets/9702/fig-a.png]]")  # the same figure twice is still one new figure, but needs its caption
    assert any("source caption" in x for x in rf.gates(SUB)["first"])


def test_gates_refuse_a_figure_without_file_sidecar_or_caption_and_more_than_three(rf, tmp_path, monkeypatch):
    crop = figure_env(rf, tmp_path, monkeypatch)
    rf.cmd_add([SUB, "--scope", "full"])
    rf.take_snapshot(SUB, 1)
    add_to_note(rf, "![[Assets/9702/ghost.png]]")
    first = " | ".join(rf.gates(SUB)["first"])
    assert "ghost.png is embedded but its file does not exist" in first and "ghost.png has no provenance sidecar" in first
    add_to_note(rf, "\n".join(crop(f"fig-{c}") for c in "abcd"))
    first = " | ".join(rf.gates(SUB)["first"])
    assert "5 new figures: at most 3" in first
    add_to_note(rf, "![[Assets/9702/fig-e.png]]")
    note = rf.note_path(json.loads(rf.pack_path(SUB).read_text()))
    text = note.read_text().replace("*Figure: A test (source: Book, p.1)*", "")  # captions gone: the foundry gate says so
    note.write_text(text)
    assert "source caption" in " | ".join(rf.gates(SUB)["first"])


def test_a_figure_never_replaces_the_diagram_it_sits_beside(rf, tmp_path, monkeypatch):
    crop = figure_env(rf, tmp_path, monkeypatch)
    rf.cmd_add([SUB, "--scope", "full"])
    rf.take_snapshot(SUB, 1)
    pack = json.loads(rf.pack_path(SUB).read_text())
    note = rf.note_path(pack)
    note.write_text(note.read_text().replace("Displacement", "Displacement and the diagram", 1))  # an edited line
    add_to_note(rf, crop("fig-a"))
    assert any(x.startswith("no-loss") for x in rf.gates(SUB)["first"])


# ---------------- sub/superscript glyphs ----------------
def old_chapter_with_glyphs(rf):
    """A chapter signed before the glyph gate: Eₖ in an item's explanation and vᵢₙᵢₜᵢₐₗ in the note."""
    pack = json.loads(rf.pack_path(SUB).read_text())
    pack["items"][0]["explanation"] = "The energy Eₖ rises."
    rf.pack_path(SUB).write_text(json.dumps(pack))
    rf.note_path(pack).write_text(NOTE + "The speed vᵢₙᵢₜᵢₐₗ is given.\n")


def test_no_loss_tolerates_exactly_the_glyph_repair(rf):
    old_chapter_with_glyphs(rf)
    rf.cmd_add([SUB, "--scope", "full"])
    before = rf.take_snapshot(SUB, 1)
    pack = copy.deepcopy(before["pack"])
    pack["items"][0]["explanation"] = "The energy $E_k$ rises."  # what glyphs.fix_text does to it
    note = (NOTE + "The speed vᵢₙᵢₜᵢₐₗ is given.\n").replace("vᵢₙᵢₜᵢₐₗ", "$v_{initial}$")
    assert rf.no_loss(before, pack, note) == []
    assert rf.no_loss(before, before["pack"], before["note"]) == []  # left as it was is not a loss either
    pack["items"][0]["explanation"] = "The energy rises."  # any other change is still caught
    assert any("`explanation` was changed" in p for p in rf.no_loss(before, pack, note))
    assert any("note: the line" in p for p in rf.no_loss(before, copy.deepcopy(before["pack"]), "something else\n"))


def test_a_refine_that_leaves_glyphs_is_repaired_without_a_retry(rf):
    old_chapter_with_glyphs(rf)
    rf.cmd_add([SUB, "--scope", "full"])
    write_plan(rf, PLAN)
    rf.take_snapshot(SUB, 1)
    refine_additively(rf)
    assert rf.fd.gates(SUB)["glyphs"] == 2
    with rf.chapter(SUB) as st:
        st["stage"] = "refine"
    rf.cmd_collect("refiner", SUB, "-")
    st = rf.load(SUB)
    assert st["stage"] == "solve" and st["gates"]["ok"] and st["gates"]["glyphs"] == 0 and st["gates"]["no_loss"] == 0
    assert any(h["note"] == "glyphs auto-fixed: 2 strings" for h in st["history"])
    assert "$E_k$" in rf.pack_path(SUB).read_text()


def test_coverage_names_chapters_whose_stored_content_still_wobbles(rf, capsys):
    assert rf.coverage()["glyphs"] == []
    old_chapter_with_glyphs(rf)
    assert rf.coverage()["glyphs"] == [SUB]
    rf.cmd_coverage([])
    assert "wobble in the terminal (1): " + SUB in capsys.readouterr().out


def test_a_running_refine_job_is_counted_once_not_twice(rf):
    """The foundry's count includes refine's jobs; refine adding its own on top halved the slots it could use."""
    rf.cmd_add([SUB, "--scope", "full"])
    with rf.chapter(SUB) as st:
        st["jobs"]["scout"] = {"provider": "codex", "pid": os.getpid(), "started": rf.now()}
    assert rf._busy().get("codex", []).count("scout") == 1


def test_a_pass_whose_gates_stay_red_pauses_and_preserves_its_additions(rf, monkeypatch):
    """Found on the first real run: a refiner that could not get past a gate was retried 130-216 times on the allowance."""
    rf.cmd_add([SUB, "--scope", "full"])
    pack_before = rf.pack_path(SUB).read_text()
    with rf.chapter(SUB) as st:
        rf.take_snapshot(SUB, 1)
        rf.move(st, "refine", "test")
        for _ in range(rf.MAX_UNCLEAN):
            st["history"].append({"t": rf.now(), "from": "refine", "to": "refine",
                                  "note": "refiner finished but gates are not clean: ['syllabus command-word Estimate']"})
    pack = json.loads(pack_before)
    pack["items"][0]["stem"] += " (an addition that cannot pass)"
    rf.pack_path(SUB).write_text(json.dumps(pack))  # the refiner's uncommitted change
    monkeypatch.setattr(rf.subprocess, "run", lambda *a, **k: type("R", (), {"returncode": 1})())  # tmp root: no git
    assert rf.unclean_streak(rf.load(SUB)) == rf.MAX_UNCLEAN
    rf.cmd_step([SUB])
    st = rf.load(SUB)
    assert st["stage"] == "refine" and not st.get('abandoned')
    assert "an addition that cannot pass" in rf.pack_path(SUB).read_text()
    assert SUB not in rf.coverage()["given_up"]
    two = {**st, "history": st["history"][:-1] + [{"note": "refiner finished but gates are not clean"}, {"note": "refined"}]}
    assert rf.unclean_streak(two) == 0  # the streak is consecutive failures only


def test_a_scout_that_never_used_the_library_or_the_web_is_not_accepted_and_is_retried(rf, tmp_path, monkeypatch):
    """The fake worker's log shows no library or web use: with the check on, its plan is not accepted."""
    import evidence
    monkeypatch.delenv("FOUNDRY_EVIDENCE", raising=False)
    monkeypatch.setattr(evidence, "library_hits", lambda sub: 5)
    rf.cmd_add([SUB, "--scope", "full"])
    plan = tmp_path / "plan.json"
    plan.write_text(json.dumps({"summary": "already complete", "improvements": []}))
    monkeypatch.setenv("FAKE_COPY", str(plan))
    rf.cmd_run("scout", SUB)
    job = finished(rf, "scout")
    st = rf.load(SUB)
    assert not job["ok"] and st["stage"] == "plan"  # not accepted: it never opened the library
    note = st["history"][-1]["note"]
    assert "gates are not clean" in note and "sources" in note and rf.unclean_streak(st) == 1
    assert rf.action(st) == f"refine.py run scout {SUB}"  # tried again, one tier up


def test_guided_errors_remain_blocking_after_inherited_gate_filter(rf):
    rf.cmd_add([SUB, "--scope", "full"])
    rf.take_snapshot(SUB, 1)
    path = rf.pack_path(SUB)
    pack = json.loads(path.read_text())
    pack["guided_forms"] = {}
    path.write_text(json.dumps(pack))
    result = rf.gates(SUB)
    assert result["guided"] > 0
    assert not result["ok"]
    assert any(message.startswith("guided ") for message in result["first"])


def test_unmerged_guided_draft_blocks_refine_gates(rf):
    rf.cmd_add([SUB, "--scope", "full"])
    rf.take_snapshot(SUB, 1)
    path = rf.teach_path(SUB)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({f'{SUB}.1': {**CARD, 'plain_words': 'A draft'}}))
    result = rf.gates(SUB)
    assert not result['ok'] and result['guided'] > 0
    assert any('guided ' in finding for finding in result['first'])


def test_p2_proposed_corrections_remain_visible_to_no_loss_gate(rf):
    from test_p2_guided_pilot import corrected_draft_pack
    before = __import__('test_p2_guided_pilot').original_pack()
    issues = rf.no_loss({'pack': before, 'note': ''}, corrected_draft_pack(), '')
    joined = '\n'.join(issues)
    assert 'outline' in joined
    assert 'we1' in joined
    assert 'P2-1-i11' in joined
    assert 'm2' in joined
    assert 'fc2' in joined


def test_p2_proposed_note_clarification_is_also_visible_to_no_loss_gate(rf):
    before = __import__('test_p2_guided_pilot').original_pack()
    note = __import__('test_p2_guided_pilot').original_note()
    proposals = library_json('build/work/guided/P2-1-corrections.json')['note_corrections']
    for proposal in proposals:
        assert note.count(proposal['old']) == 1
        candidate = note.replace(proposal['old'], proposal['new'])
        assert any('note: the line' in issue for issue in rf.no_loss({'pack': before, 'note': note}, before, candidate))


def test_written_review_gate_rejects_missing_and_stale_evidence(rf):
    from build.written_review import fingerprint, review_items
    pack = {'teach': {'kc': {'forms': [{'name': 'Proof', 'check': 'Prove', 'answer': 'Working',
                                       'rubric': [{'point': 'Reason'}]}]}}}
    rows = review_items(pack['teach'])
    assert rf.written_review_problems('trial', pack)
    solution = 'Independent proof'
    ident = rows[0]['id']
    review = {'fingerprint': fingerprint(rows[0]), 'solution': solution, 'solver': 'solver-agent', 'reviewer': 'reviewer',
              'verdict': 'accepted', 'rationale': 'Valid reasoning',
              'solution_hash': fingerprint({'id': ident, 'stem': solution, 'answer': None, 'rubric': None})}
    path = rf.WORK / 'trial.written-review.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({ident: review}))
    assert any('durable independent worker evidence' in p for p in rf.written_review_problems('trial', pack))
    pack['teach']['kc']['forms'][0]['check'] = 'Changed proof'
    assert rf.written_review_problems('trial', pack)
    assert rf.written_review_problems('legacy', {'teach': {'kc': {'establish': 'Old'}}}) == []


def test_gate_blocks_unreviewed_written_checks_without_snapshot(rf, monkeypatch):
    path = rf.pack_path(SUB)
    pack = json.loads(path.read_text())
    pack['teach'][f'{SUB}.1']['forms'] = [{'name': 'Proof', 'check': 'Prove', 'answer': 'Working',
                                           'rubric': [{'point': 'Reason'}]}]
    path.write_text(json.dumps(pack))
    monkeypatch.setattr(rf.fd, 'gates', lambda sub, **kw: {'ok': True})
    result = rf.gates(SUB)
    assert result['written_review'] > 0
    assert not result['ok']
    deferred = rf.gates(SUB, defer_written=True)  # after a refiner: reviewed next, so counted but not failing
    assert deferred['written_review'] > 0 and deferred['ok']


def _written_pack(rf):
    path = rf.pack_path(SUB)
    pack = json.loads(path.read_text())
    pack['teach'][f'{SUB}.1']['forms'] = [{'name': 'Proof', 'check': 'Show that v = u + at.', 'answer': 'From a = (v-u)/t.',
                                           'rubric': [{'point': 'definition of acceleration'}]}]
    path.write_text(json.dumps(pack))
    return pack


def test_written_checks_are_blind_solved_reviewed_and_bound(rf):
    pack = _written_pack(rf)
    ident = f'{SUB}.1.form.0.check'
    with rf.chapter(SUB) if (rf.STATE / f'{SUB}.json').exists() else _new_state(rf) as st:
        st['stage'] = 'solve'
        st['history'].append({'t': rf.now(), 'from': 'refine', 'to': 'solve', 'note': ''})
    rf.cmd_strip(SUB)
    st = rf.load(SUB)
    asked = json.loads(rf._written_questions(st).read_text())
    assert asked == [{'id': ident, 'stem': 'Show that v = u + at.'}]  # the stem only: no answer, no rubric
    assert rf._written_jobs(st) == ['wsolver']
    rf._written_answers(st).write_text(json.dumps({ident: 'a = (v - u)/t, so v = u + at.'}))
    with rf.chapter(SUB) as st:
        st['jobs']['wsolver'] = {'provider': 'codex', 'model': 'terra', 'finished': rf.now(), 'exit': 0,
                                 'ok': True, 'expects': str(rf._written_answers(st).relative_to(rf.ROOT)),
                                 'written_batch': rf._written_batch(st)['id'],
                                 'written_input_hash': rf._written_hash(rf._written_questions(st))}
        rf._finish_written_job(st, 'wsolver')
    st = rf.load(SUB)
    assert rf._written_jobs(st) == ['wreviewer']
    items = json.loads(rf.write_written_items(SUB).read_text())
    assert items[0]['answer'] and items[0]['solution'].startswith('a = ')
    rf._written_file(SUB, 'decisions').write_text(json.dumps({ident: {'verdict': 'accepted', 'rationale': 'Sound.'}}))
    with rf.chapter(SUB) as st:
        st['jobs']['wreviewer'] = {'provider': 'codex', 'model': 'sol', 'finished': rf.now(), 'exit': 0,
                                   'ok': True, 'expects': str(rf._written_file(SUB, 'decisions').relative_to(rf.ROOT)),
                                   'written_batch': rf._written_batch(st)['id'],
                                   'written_input_hash': rf._written_hash(rf._written_file(SUB, 'items'))}
        rf._finish_written_job(st, 'wreviewer')
    with rf.chapter(SUB) as st:
        note = rf._ingest_written(st, pack)
    assert '1 accepted' in note
    assert rf.written_review_problems(SUB, pack) == []


def test_a_rejected_written_check_cannot_be_kept_without_actual_review(rf):
    pack = _written_pack(rf)
    ident = f'{SUB}.1.form.0.check'
    with _new_state(rf) as st:
        st['stage'] = 'solve'
    rf.cmd_strip(SUB)
    st = rf.load(SUB)
    rf._written_answers(st).write_text(json.dumps({ident: 'v = u + at by definition.'}))
    with rf.chapter(SUB) as st:
        st['jobs']['wsolver'] = {'provider': 'codex', 'model': 'terra', 'finished': rf.now(), 'exit': 0,
            'ok': True, 'expects': str(rf._written_answers(st).relative_to(rf.ROOT)),
            'written_batch': rf._written_batch(st)['id'],
            'written_input_hash': rf._written_hash(rf._written_questions(st))}
        rf._finish_written_job(st, 'wsolver')
    rf.write_written_items(SUB)
    rf._written_file(SUB, 'decisions').write_text(json.dumps({ident: {'verdict': 'rejected', 'rationale': 'Rubric too narrow.',
                                                                   'fix': 'Accept "rate of change of velocity".'}}))
    with rf.chapter(SUB) as st:
        st['jobs']['wreviewer'] = {'provider': 'codex', 'model': 'sol', 'finished': rf.now(), 'exit': 0,
            'ok': True, 'expects': str(rf._written_file(SUB, 'decisions').relative_to(rf.ROOT)),
            'written_batch': rf._written_batch(st)['id'],
            'written_input_hash': rf._written_hash(rf._written_file(SUB, 'items'))}
        rf._finish_written_job(st, 'wreviewer')
    with rf.chapter(SUB) as st:
        rf._ingest_written(st, pack)
        st['stage'] = 'adjudicate'
    st = rf.load(SUB)
    assert [f['ref'] for f in st['findings'] if f['status'] == 'open'] == [ident]
    assert rf.written_review_problems(SUB, pack)
    with pytest.raises(SystemExit, match='independent written review'):
        rf.cmd_resolve(SUB, ident, 'keep', 'The rubric point is required by the question; the solution earns it.')
    assert rf.written_review_problems(SUB, pack)


def test_earlier_pass_correction_proposals_are_kept_aside_not_applied(rf):
    with _new_state(rf):
        pass
    old = rf.corrections_file(SUB)
    old.parent.mkdir(parents=True, exist_ok=True)
    old.write_text('{"changes": []}')
    os.utime(old, (time.time() - 86400, time.time() - 86400))
    moved = rf.archive_stale_corrections(SUB)
    assert len(moved) == 1 and not old.exists()
    assert (old.parent / moved[0]).read_text() == '{"changes": []}'  # preserved, under a dated name
    old.write_text('{"changes": []}')  # written during this pass: stays
    assert rf.archive_stale_corrections(SUB) == [] and old.exists()


def test_a_library_backed_teach_draft_gets_an_editable_work_copy(tmp_path, monkeypatch):
    sys.path.insert(0, str(REPO / "src"))
    from tutor_workers import candidates
    monkeypatch.setattr(candidates, "verified", lambda path: path.resolve())  # no catalog in a scratch vault
    library = tmp_path / "vault/Library/Courses/9702/teach"
    library.mkdir(parents=True)
    (library / f"{SUB}.json").write_text('{"kc": {}}')
    work = tmp_path / "data/build/work/teach"
    work.mkdir(parents=True)
    (work / f"{SUB}.json").symlink_to(library / f"{SUB}.json")
    paths = candidates.prepare_teach(tmp_path / "data", "refine", SUB, work / f"{SUB}.json")
    copy_ = Path(paths["candidate_teach"])
    assert "Library" not in copy_.resolve().parts and copy_.read_text() == '{"kc": {}}'
    plain = tmp_path / "plain.json"
    plain.write_text("{}")
    assert candidates.prepare_teach(tmp_path / "data", "refine", SUB, plain) == {}  # Work-owned drafts are edited in place


def _new_state(rf):
    if not (rf.STATE / f'{SUB}.json').exists():
        rf.cmd_add([SUB])
    return rf.chapter(SUB)


def test_written_review_gate_rejects_malformed_teach(rf):
    for bad in ([], '', None):
        assert rf.written_review_problems('trial', {'teach': bad})
    assert not rf.written_review_problems('trial', {})



def test_board_identifies_written_review_failure(rf, capsys):
    rf.cmd_add([SUB, "--scope", "full"])
    with rf.chapter(SUB) as st:
        st['gates'] = {'ok': False, 'validator': 0, 'lint': 0, 'no_loss': 0, 'written_review': 2}
    rf.cmd_board()
    output = capsys.readouterr().out
    assert 'written_review:2' in output
    assert '0+0+0' not in output


def test_written_faded_check_requires_independent_review(rf):
    pack = {'worked': [{'id': 'we2', 'kc': 'K', 'problem': 'Worked problem', 'steps': [],
                        'faded': {'id': 'we2f', 'kind': 'short', 'problem': 'Disprove.',
                                  'review_answer': '111 = 3 × 37',
                                  'rubric': [{'point': 'Factors', 'keywords': [['3'], ['37']]}]}}]}
    assert rf.written_review_problems('missing-faded-review', pack)


def test_board_and_bare_step_stay_on_the_focus_list(rf, capsys, monkeypatch):
    rf.cmd_add([SUB])
    cfg = rf.config()
    monkeypatch.setattr(rf, "config", lambda: {**cfg, "focus": ["somewhere-else"]})
    assert rf.focused(rf.chapters()) == []
    assert [st["sub"] for st in rf.focused(rf.chapters(), show_all=True)] == [SUB]
    rf.cmd_board()
    assert "no chapters on the refine board" in capsys.readouterr().out
    monkeypatch.setattr(rf, "config", lambda: {**cfg, "focus": [SUB]})
    assert [st["sub"] for st in rf.focused(rf.chapters())] == [SUB]

@pytest.mark.parametrize('stale', [False, True])
def test_checker_launch_rebuilds_additions_after_recovery(rf, monkeypatch, stale):
    rf.cmd_add([SUB, '--scope', 'full'])
    rf.take_snapshot(SUB, 1)
    original_pack = json.loads(rf.pack_path(SUB).read_text())
    candidate = rf.WORK / SUB / 'recovered'
    candidate.mkdir(parents=True)
    (candidate / 'pack.json').write_text(json.dumps(original_pack))
    (candidate / 'note.md').write_text(NOTE)
    (candidate / 'teach.json').write_text(json.dumps(original_pack['teach']))
    with rf.chapter(SUB) as st:
        st.update(candidate_pack=str(candidate / 'pack.json'), candidate_note=str(candidate / 'note.md'),
                  candidate_teach=str(candidate / 'teach.json'))
    refine_additively(rf, questions=0, line='Recovered candidate teaching line.')
    with rf.chapter(SUB) as st:
        rf.move(st, 'solve', 'recovered candidate without collect')
    # The output adapter still names the old source: recovery's selected Work
    # candidate is the checker input and must win over that source.
    source = rf.chapter_pack(rf.PACKS, SUB)
    source_pack = json.loads(source.read_text())
    assert 'Recovered candidate teaching line.' not in (rf.NOTES / source_pack['note']).read_text()
    artifact = rf.WORK / f'{SUB}.additions.md'
    if stale:
        artifact.write_text('stale prior-pass additions')
    monkeypatch.setattr(rf.subprocess, 'Popen', lambda *a, **kw: type('Process', (), {'pid': 99999999})())
    rf.cmd_run('checker', SUB, on='codex')
    assert artifact.is_file()
    text = artifact.read_text()
    assert 'Recovered candidate teaching line.' in text
    assert 'stale prior-pass additions' not in text
