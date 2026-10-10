"""The content foundry's board, gates, hand-offs and its split of work between the Claude and Codex allowances, on a
scratch copy of the build tree. The workers are fakes: no AI is started and the learner's real usage is never read."""
import importlib
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import pytest

from fixtures import GRAPH

REPO = Path(__file__).resolve().parents[1]
SUB = "9702-2.1"
CARD = {"motivate": "Why this.", "establish": "The idea.", "connect": "Builds on that.", "note": "- one\n- two",
        "self_explain": "Say it in your own words."}


@pytest.fixture
def fdy(tmp_path, monkeypatch):
    sys.path.insert(0, str(REPO / "tests"))
    from test_validate import good_pack
    pack = good_pack()
    pack["teach"] = {f"{SUB}.1": dict(CARD), f"{SUB}.4": dict(CARD)}  # a teaching card for each syllabus outcome
    (tmp_path / "build/out/packs/9702").mkdir(parents=True)
    (tmp_path / "build/out/specs/9702").mkdir(parents=True)
    (tmp_path / "build/work/bundles").mkdir(parents=True)
    (tmp_path / "build/work/bundles" / f"{SUB}.md").write_text("# Bundle\n")
    (tmp_path / f"build/out/packs/9702/{SUB}.json").write_text(json.dumps(pack))
    (tmp_path / "build/out/specs/9702/graph.json").write_text(json.dumps(GRAPH))
    note = tmp_path / "build/out/notes" / pack["note"]
    note.parent.mkdir(parents=True)
    note.write_text("# 2.1 Equations of motion\n\nDisplacement is a vector and distance is a scalar. For uniform "
                    "acceleration use the suvat equations such as $v = u + at$.\n")
    monkeypatch.setenv("FOUNDRY_ROOT", str(tmp_path))
    monkeypatch.setenv("FOUNDRY_NOTIFY", "0")  # no Mac notifications from tests
    monkeypatch.setenv("FOUNDRY_PUBLISH", "0")  # never publish into the real vault from tests
    monkeypatch.setenv("FOUNDRY_COMMIT", "0")
    fake = str(REPO / "tests/fake_worker.py")
    monkeypatch.setenv("FOUNDRY_CODEX", fake)
    monkeypatch.setenv("FOUNDRY_CLAUDE", fake)
    (tmp_path / "usage-now.json").write_text(json.dumps(usage(50, 50)))  # read instead of the real allowances
    monkeypatch.setenv("FOUNDRY_USAGE_FILE", str(tmp_path / "usage-now.json"))
    for name in ("FAKE_FAIL", "FAKE_COPY", "FAKE_REPORT", "FAKE_ARGV", "FAKE_UTILIZATION"):
        monkeypatch.delenv(name, raising=False)
    sys.path.insert(0, str(REPO / "foundry"))
    import foundry
    return importlib.reload(foundry)


def usage(claude_week, codex_week, codex_now=10, claude_days=4.0, codex_days=4.0):
    """Both allowances as the foundry reads them: percent used, and when each window resets."""
    now = time.time()
    return {"claude": {"seven_day": {"used": claude_week, "resets": now + claude_days * 86400}},
            "codex": {"five_hour": {"used": codex_now, "resets": now + 3 * 3600},
                      "seven_day": {"used": codex_week, "resets": now + codex_days * 86400}}}


def finished(fdy, name, tries=150):
    """Wait until a background worker has been collected."""
    for _ in range(tries):
        job = fdy.load(SUB)["jobs"].get(name, {})
        if job.get("finished"):
            return job
        time.sleep(0.1)
    raise AssertionError(f"{name} was never collected: {fdy.load(SUB)['jobs']}")


def keys(fdy):
    import blind
    pack = json.loads(fdy.pack_path(SUB).read_text())
    out = {}
    for iid, inst in blind._instances(pack):
        a = inst["answer"]
        out[iid] = a if isinstance(a, str) else (f"{a['value']:.3g} {a.get('unit', '')}".strip() if "value" in a else a["expr"])
    return out


def test_a_chapter_goes_from_solve_to_ready(fdy, tmp_path):
    fdy.cmd_add([SUB])
    assert fdy.load(SUB)["stage"] == "solve" and SUB in json.loads(fdy.HOLD.read_text())
    assert fdy.cmd_gates(SUB)["ok"]

    fdy.cmd_strip(SUB)
    answers = keys(fdy)
    wrong = next(i for i, a in answers.items() if a in ("A", "B", "C", "D"))
    answers[wrong] = "D" if answers[wrong] != "D" else "C"
    (fdy.BLIND / f"{SUB}.answers.json").write_text(json.dumps(answers))
    fdy.cmd_compare(SUB)
    st = fdy.load(SUB)
    assert st["stage"] == "tiebreak" and [d["id"] for d in st["disputes"] if d["status"] == "open"] == [wrong]

    (fdy.BLIND / f"{SUB}.tiebreak.json").write_text(json.dumps({wrong: keys(fdy)[wrong]}))  # agrees with the key
    fdy.cmd_compare(SUB)
    st = fdy.load(SUB)
    assert st["stage"] == "check" and st["disputes"][0]["status"] == "closed"

    fdy.WORK.mkdir(parents=True, exist_ok=True)
    (fdy.WORK / f"{SUB}.check.json").write_text(json.dumps({"findings": [
        {"where": "note line 3", "rule": "wrong definition", "evidence": "Use $v = u + at$.", "fix": "say when"}]}))
    fdy.cmd_compare(SUB)
    assert fdy.load(SUB)["stage"] == "adjudicate"

    fdy.cmd_resolve(SUB, "note line 3", "fix", "Add: only for constant acceleration.")
    st = fdy.load(SUB)
    assert st["stage"] == "fix" and st["fixes"][0]["status"] == "open"
    assert "only for constant acceleration" in fdy.role_prompt("fixer", SUB)

    out = tmp_path / "fix.out.json"
    out.write_text(json.dumps({"fixed": 1, "not_done": [], "validator_ok": True, "lint_ok": True}))
    fdy.cmd_collect("fixer", SUB, str(out), "0")
    assert fdy.load(SUB)["stage"] == "sign"  # a note fix changes no question: nothing to re-solve

    fdy.cmd_sign(SUB)
    assert fdy.load(SUB)["stage"] == "ready" and SUB not in json.loads(fdy.HOLD.read_text())


def test_a_verdict_other_than_keep_or_fix_is_refused(fdy):
    fdy.cmd_add([SUB])
    with fdy.chapter(SUB) as st:
        st["stage"] = "adjudicate"
        st["findings"].append({"ref": "note line 3", "status": "open"})
    with pytest.raises(SystemExit, match="keep or fix"):
        fdy.cmd_resolve(SUB, "note line 3", "fixed", "say when")  # a typo would have closed it unfixed
    st = fdy.load(SUB)
    assert st["findings"][0]["status"] == "open" and st["stage"] == "adjudicate" and not st["fixes"]


def test_the_gates_say_what_the_note_linter_found(fdy):
    note = fdy.NOTES / json.loads(fdy.pack_path(SUB).read_text())["note"]
    note.write_text(note.read_text() + "\nBroken maths: $\\frac{1}{2$.\n")
    g = fdy.gates(SUB)
    assert g["lint"] and any("unbalanced { } in math" in line for line in g["first"])


def test_a_chapter_waiting_for_its_checker_cannot_be_signed(fdy):
    fdy.cmd_add([SUB])
    with fdy.chapter(SUB) as st:
        st["stage"] = "check"  # the blind solve agreed; the checker has not reported yet
    with pytest.raises(SystemExit, match="not ready"):
        fdy.cmd_sign(SUB)
    assert fdy.load(SUB)["stage"] == "check"
    with fdy.chapter(SUB) as st:
        st["checked"] = True  # the checker found nothing
    fdy.cmd_sign(SUB)
    assert fdy.load(SUB)["stage"] == "ready"


def test_an_unfinished_solve_is_sent_back(fdy):
    fdy.cmd_add([SUB])
    fdy.cmd_strip(SUB)
    answers = keys(fdy)
    answers.pop(next(iter(answers)))
    (fdy.BLIND / f"{SUB}.answers.json").write_text(json.dumps(answers))
    with pytest.raises(SystemExit, match="unanswered"):
        fdy.cmd_compare(SUB)
    assert fdy.load(SUB)["stage"] == "solve"


def test_sign_refuses_open_work_and_red_gates(fdy):
    fdy.cmd_add([SUB])
    with pytest.raises(SystemExit, match="not ready"):
        fdy.cmd_sign(SUB)  # still at solve
    pack = json.loads(fdy.pack_path(SUB).read_text())
    pack["items"][0]["answer"] = "Z"
    fdy.pack_path(SUB).write_text(json.dumps(pack))
    assert not fdy.gates(SUB)["ok"]


def test_solver_prompt_is_short_and_never_includes_keys(fdy):
    fdy.cmd_add([SUB])
    prompt = fdy.role_prompt("solver", SUB)
    assert "foundry/roles/solver.md" in prompt and len(prompt) < 600
    assert all(k not in prompt for k in ('"answer"', "distractors", "packs/", "bundles/"))
    assert f"build/work/blind/{SUB}.questions.json" in prompt and f"build/work/blind/{SUB}.answers.json" in prompt
    assert "packs/" in fdy.role_prompt("drafter", SUB)  # only the blind roles are kept away from the keys


def test_a_big_chapter_is_split_across_parallel_solvers(fdy):
    fdy.cmd_add([SUB])
    shards = fdy.cmd_strip(SUB, size=5)
    assert len(shards) >= 3
    answers = keys(fdy)
    for k in shards:  # each Haiku solver answers only its own shard
        part = json.loads((fdy.BLIND / f"{SUB}.questions.part{k}.json").read_text())
        assert f"questions.part{k}.json" in fdy.role_prompt("solver", SUB, k)
        if k != shards[-1]:
            (fdy.BLIND / f"{SUB}.answers.part{k}.json").write_text(json.dumps({q["id"]: answers[q["id"]] for q in part}))
    with pytest.raises(SystemExit, match="unanswered"):
        fdy.cmd_compare(SUB)  # the last solver hasn't finished
    part = json.loads((fdy.BLIND / f"{SUB}.questions.part{shards[-1]}.json").read_text())
    (fdy.BLIND / f"{SUB}.answers.part{shards[-1]}.json").write_text(json.dumps({q["id"]: answers[q["id"]] for q in part}))
    fdy.cmd_compare(SUB)
    assert fdy.load(SUB)["stage"] == "check"
    fdy.cmd_strip(SUB, size=1000)  # re-stripping clears old shards, so they can't be merged by mistake
    assert not list(fdy.BLIND.glob(f"{SUB}.*part*.json"))


def test_a_codex_job_run_by_hand_is_not_duplicated_and_reports_back(fdy):
    fdy.cmd_add([SUB])
    with fdy.chapter(SUB) as st:
        st["stage"] = "fix"
        st["fixes"] = [{"ref": "note", "instruction": "x", "status": "open"}]
    fdy.cmd_prompt("fixer", SUB)  # printed for pasting into the Codex app
    assert fdy._running(fdy.load(SUB)) == ["fixer"]
    with pytest.raises(SystemExit, match="already working"):
        fdy.cmd_run("fixer", SUB)
    fdy.cmd_collect("fixer", SUB, "-", "0")
    st = fdy.load(SUB)
    assert fdy._running(st) == [] and st["stage"] == "sign"


def test_watch_shows_a_codex_worker_and_what_it_is_doing(fdy, tmp_path):
    import os
    fdy.cmd_add([SUB])
    log = tmp_path / "foundry/logs/x.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text("exec .venv/bin/python build/validate_pack.py build/out/packs/9702/9702-2.1.json\n")
    with fdy.chapter(SUB) as st:
        st["jobs"]["drafter"] = {"pid": os.getpid(), "model": "gpt-6-sol/medium", "started": fdy.now(),
                                 "log": "foundry/logs/x.log"}
    text = fdy.watch_text()
    assert "Codex drafter (gpt-6-sol/medium) 0m: exec .venv/bin/python build/validate_pack.py" in text


def test_signing_publishes_and_commits_the_chapter_at_once(fdy, monkeypatch):
    calls = []
    monkeypatch.setenv("FOUNDRY_PUBLISH", "1")
    monkeypatch.setenv("FOUNDRY_COMMIT", "1")
    monkeypatch.delenv("STEM_TUTOR_VAULT", raising=False)
    monkeypatch.setattr(fdy.subprocess, "run", lambda args, **k: calls.append(args) or
                        type("R", (), {"returncode": 0, "stdout": '{"version": "v2"}', "stderr": ""})())
    fdy.cmd_add([SUB])
    with fdy.chapter(SUB) as st:
        st["stage"] = "sign"
    fdy.cmd_sign(SUB)
    publish = [c for c in calls if any(str(x).endswith("build/publish.py") for x in c)]
    commit = [c for c in calls if "commit" in c]
    assert publish and commit
    assert any(str(x).endswith(f"{SUB}.json") for x in commit[0]) and "--" in commit[0]  # only this chapter's files
    assert "--vault" not in publish[0]


def test_signing_publishes_into_the_vault_the_app_uses(fdy, monkeypatch, tmp_path):
    calls = []
    monkeypatch.setenv("FOUNDRY_PUBLISH", "1")
    monkeypatch.setenv("STEM_TUTOR_VAULT", str(tmp_path / "vault"))
    monkeypatch.setattr(fdy.subprocess, "run", lambda args, **k: calls.append(args) or
                        type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})())
    fdy.release(SUB)
    publish = [c for c in calls if any(str(x).endswith("build/publish.py") for x in c)]
    assert publish[0][-2:] == ["--vault", str(tmp_path / "vault")]


def test_signing_commits_a_chapter_whose_figures_git_ignores(fdy, monkeypatch):
    monkeypatch.setenv("FOUNDRY_COMMIT", "1")
    root = fdy.ROOT

    def git(*args):
        return fdy.subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=True).stdout

    git("init", "-q")
    git("config", "user.email", "test@example.com")
    git("config", "user.name", "Test")
    (root / ".gitignore").write_text("build/out/Assets/\n")  # figures are not kept in git
    git("add", ".gitignore")
    git("commit", "-q", "-m", "base")
    fdy.cmd_add([SUB])
    figure = root / "build/out/Assets" / SUB.split("-")[0] / f"{SUB}-figure.svg"
    figure.parent.mkdir(parents=True, exist_ok=True)
    figure.write_text("<svg/>")
    with fdy.chapter(SUB) as st:
        st["stage"] = "sign"
    fdy.cmd_sign(SUB)
    assert f"content({SUB})" in git("log", "--format=%s") and not git("ls-files", "build/out/Assets")


def bank(root, questions):
    work = root / "build/work/mcq"
    work.mkdir(parents=True, exist_ok=True)
    (work / "9702.tagged.json").write_text(json.dumps(questions))
    return work


def past(n, **over):
    return {"id": f"9702_s23_1{n}_q5", "ref": f"CAIE 9702 · Jun 2023 · P1{n} · Q5", "kcs": [f"{SUB}.1"],
            "stem": f"Past question {n}?", "options": {"A": "a", "B": "b", "C": "c", "D": "d"}, "answer": "A", **over}


def extras(path):
    return {i["source"]["qid"]: i for i in json.loads(path.read_text())["items"] if i.get("tier") == "extra"}


def test_extras_keep_their_ids_and_corrections_when_the_pack_is_rebuilt(fdy, tmp_path):
    sys.path.insert(0, str(REPO / "build"))
    import add_past
    work = bank(tmp_path, [past(1), past(2)])
    (work / "overrides.json").write_text(json.dumps({"9702_s23_12_q5": {"explanation": "Why A.", "answer": "B"}}))
    path = fdy.pack_path(SUB)
    plain = path.read_text()
    assert add_past.add(path, work=work) == 2
    first = extras(path)
    assert first["9702_s23_12_q5"]["explanation"] == "Why A." and first["9702_s23_12_q5"]["answer"] == "B"
    ids = {q: i["id"] for q, i in first.items()}
    bank(tmp_path, [past(0), past(1), past(2)])  # a new question lands first in the bank
    path.write_text(plain)  # the generator re-ran: the extras are gone from the pack
    add_past.add(path, keep_ids=ids, work=work)
    again = {q: i["id"] for q, i in extras(path).items()}
    assert {q: again[q] for q in ids} == ids and again["9702_s23_10_q5"] not in ids.values()


def test_extras_come_back_after_a_fixer_reruns_the_generator(fdy, tmp_path):
    bank(tmp_path, [past(1), past(2)])
    fdy.cmd_add([SUB])
    fdy.cmd_collect("drafter", SUB, "-")  # as after drafting: the extras are appended and remembered
    path = fdy.pack_path(SUB)
    before = [i["id"] for i in json.loads(path.read_text())["items"]]
    assert len(extras(path)) == 2
    pack = json.loads(path.read_text())
    pack["items"] = [i for i in pack["items"] if i.get("tier") != "extra"]
    path.write_text(json.dumps(pack))  # a fixer edited the generator and re-ran it
    with fdy.chapter(SUB) as st:
        st["stage"], st["fixes"] = "fix", []
    fdy.cmd_collect("fixer", SUB, "-")
    assert [i["id"] for i in json.loads(path.read_text())["items"]] == before and fdy.load(SUB)["stage"] == "sign"


def test_next_says_compare_once_the_tiebreak_has_finished(fdy):
    fdy.cmd_add([SUB])
    with fdy.chapter(SUB) as st:
        fdy.move(st, "tiebreak", "1 disputed")
    assert "run tiebreak" in fdy.action(fdy.load(SUB))
    fdy.cmd_prompt("tiebreak", SUB)  # taken by hand: now running
    assert fdy.action(fdy.load(SUB)).startswith("wait")
    fdy.cmd_collect("tiebreak", SUB, "-")
    assert fdy.action(fdy.load(SUB)) == f"foundry.py compare {SUB}"  # not "launch the tiebreak" again


def test_queue_waits_for_a_free_slot_and_skips_a_chapter_that_cannot_start(fdy, monkeypatch):
    calls, full = [], [True, True]

    def run(role, sub):
        calls.append(sub)
        if sub == "bad":
            raise SystemExit("bad: a drafter is already working on this chapter")
        if full:
            full.pop()
            raise fdy.router.Wait("no allowance can take a drafter now: 3 workers already running on each")

    monkeypatch.setattr(fdy, "cmd_run", run)
    monkeypatch.setattr(fdy, "cmd_add", lambda subs, stage="draft": None)
    fdy.cmd_queue("drafter", [SUB, "bad", "next"], wait=0)
    assert calls == [SUB, SUB, SUB, "bad", "next"]  # two full houses, then started; the bad one is skipped, not retried


def test_a_finished_job_does_not_count_as_running_even_if_its_process_lingers(fdy):
    import os
    fdy.cmd_add([SUB])
    with fdy.chapter(SUB) as st:  # a finished worker not yet reaped by its parent (the queue) still answers kill(pid, 0)
        st["jobs"]["drafter"] = {"pid": os.getpid(), "started": fdy.now(), "finished": fdy.now(), "exit": 0}
    assert fdy._running(fdy.load(SUB)) == []


def test_the_syllabus_gate_blocks_a_chapter_with_an_outcome_untaught(fdy):
    fdy.cmd_add([SUB])
    assert fdy.cmd_gates(SUB)["ok"]
    pack = json.loads(fdy.pack_path(SUB).read_text())
    del pack["teach"][f"{SUB}.4"]
    fdy.pack_path(SUB).write_text(json.dumps(pack))
    g = fdy.cmd_gates(SUB)
    assert not g["ok"] and g["syllabus"] == 1 and any("no-teach-card" in x for x in g["first"])
    with fdy.chapter(SUB) as st:
        st["stage"] = "sign"
    with pytest.raises(SystemExit):
        fdy.cmd_sign(SUB)
    assert not fdy.load(SUB)["gates"]["ok"]  # the refusal is recorded, so the drafter is told what to add
    assert "no-teach-card" in fdy.role_prompt("drafter", SUB)


def test_teaching_cards_are_merged_again_after_a_worker_rewrites_the_pack(fdy, tmp_path):
    fdy.cmd_add([SUB])
    teach = tmp_path / "build/work/teach"
    teach.mkdir(parents=True)
    (teach / f"{SUB}.json").write_text(json.dumps({f"{SUB}.1": CARD, f"{SUB}.4": {**CARD, "note": "not bullets"}}))
    pack = json.loads(fdy.pack_path(SUB).read_text())
    del pack["teach"]  # the generator re-ran: it writes the pack without the cards
    fdy.pack_path(SUB).write_text(json.dumps(pack))
    fdy.cmd_collect("drafter", SUB, "-")
    merged = json.loads(fdy.pack_path(SUB).read_text())["teach"]
    assert list(merged) == [f"{SUB}.1"] and merged[f"{SUB}.1"]["source"] == "pack"  # the malformed card stays out
    assert not fdy.load(SUB)["gates"]["ok"]  # and the gate says an outcome has no card


def test_blind_solvers_also_get_the_teaching_cards_check_questions(fdy):
    import blind
    pack = json.loads(fdy.pack_path(SUB).read_text())
    pack["teach"][f"{SUB}.1"]["discover"] = {"stem": "Which is a vector?", "answer": "B", "explanation": "It has direction.",
                                             "options": {"A": "speed", "B": "velocity", "C": "mass", "D": "time"}}
    q = next(q for q in blind.strip(pack) if q["id"] == f"{SUB}.1.discover")
    assert q["options"]["B"] == "velocity" and "answer" not in q


@pytest.mark.parametrize("said,agrees", [
    ("{k}", True), ("{lk}", True), ("({k})", True), ("The answer is {k}", True), ("Answer: {k}.", True),
    ("{k}) it has direction", True), ("{w}", False), ("The answer is {w}", False), ("({w})", False)])
def test_a_blind_mcq_answer_is_read_by_its_option_letter(fdy, said, agrees):
    """A solver may answer "(B)" or "The answer is B": the option letter counts, not the first character."""
    import blind
    pack = json.loads(fdy.pack_path(SUB).read_text())
    iid, inst = next((i, x) for i, x in blind._instances(pack) if x["kind"] == "mcq")
    key = inst["answer"]
    wrong = next(x for x in "ABCD" if x != key and x != "A")  # not A: "A" also opens "Answer"
    res = blind.compare(pack, {iid: said.format(k=key, lk=key.lower(), w=wrong)})
    assert (iid not in [d["id"] for d in res["disagreements"]]) == agrees


def test_coverage_counts_outcomes_and_says_what_to_build_next(fdy, tmp_path, capsys):
    graph = json.loads((tmp_path / "build/out/specs/9702/graph.json").read_text())
    graph["subtopics"] += [{"id": "9702-3.1", "title": "Momentum", "topic": "9702-2"},
                           {"id": "9702-2.2", "title": "Later", "topic": "9702-2"}]
    graph["kcs"] += [{"id": "9702-3.1.1", "subtopic": "9702-3.1", "title": "Momentum", "statement": "define momentum"},
                     {"id": "9702-2.2.1", "subtopic": "9702-2.2", "title": "Later", "statement": "use it"}]
    (tmp_path / "build/out/specs/9702/graph.json").write_text(json.dumps(graph))
    (tmp_path / "build/out/plan.json").write_text(json.dumps({"weeks": {
        "3": [{"type": "NEW", "kcs": ["9702-3.1.1"]}], "9": [{"type": "NEW", "kcs": ["9702-2.2.1"]}]}}))
    fdy.cmd_add([SUB])
    c = fdy.coverage()
    assert c["specs"]["9702"] == {"outcomes": 4, "ready": 0, "in_progress": 2, "not_started": 2,
                                  "chapters": {"ready": 0, "in_progress": 1, "not_started": 2}}
    assert c["next"] == ["9702-3.1", "9702-2.2"] and c["holes"] == {}  # Almanac week order, not id order
    with fdy.chapter(SUB) as st:
        st["stage"] = "ready"
    pack = json.loads(fdy.pack_path(SUB).read_text())
    del pack["teach"][f"{SUB}.4"]
    fdy.pack_path(SUB).write_text(json.dumps(pack))
    graph["subtopics"].append(dict(graph["subtopics"][0]))  # a subtopic listed twice is counted once
    (tmp_path / "build/out/specs/9702/graph.json").write_text(json.dumps(graph))
    c = fdy.coverage()
    assert c["specs"]["9702"]["ready"] == 2 and c["holes"] == {SUB: {"no-teach-card": 1}}
    assert c["specs"]["9702"]["outcomes"] == 4 and sum(c["specs"]["9702"]["chapters"].values()) == 3
    fdy.cmd_coverage([])
    assert "9702-3.1" in capsys.readouterr().out


def test_install_skill_sets_sonnet_at_medium_effort(fdy, tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    fdy.cmd_install_skill()
    text = (tmp_path / "home/.claude/skills/foundry/SKILL.md").read_text()
    assert "model: sonnet" in text and "effort: medium" in text and "foundry/roles/manager.md" in text


def test_wait_returns_when_no_worker_is_running(fdy, capsys):
    import os
    fdy.cmd_add([SUB])
    fdy.cmd_wait(timeout=5, every=0)  # nothing running: straight back
    with fdy.chapter(SUB) as st:
        st["jobs"]["drafter"] = {"pid": os.getpid(), "started": fdy.now()}  # a worker that never finishes
    t0 = time.time()
    fdy.cmd_wait(timeout=0.3, every=0.05)
    assert 0.25 < time.time() - t0 < 3 and "still running" in capsys.readouterr().out


def test_a_refused_sign_records_why_so_the_drafter_is_told(fdy):
    fdy.cmd_add([SUB])
    pack = json.loads(fdy.pack_path(SUB).read_text())
    del pack["teach"][f"{SUB}.4"]
    fdy.pack_path(SUB).write_text(json.dumps(pack))
    with fdy.chapter(SUB) as st:
        st["stage"] = "sign"
    assert fdy.load(SUB)["gates"] is None  # nothing has run the gates yet
    with pytest.raises(SystemExit):
        fdy.cmd_sign(SUB)
    st = fdy.load(SUB)
    assert st["stage"] == "sign" and st["gates"]["syllabus"] == 1 and "no-teach-card" in fdy.role_prompt("drafter", SUB)


def test_coverage_builds_what_the_learner_has_not_ticked_off_first(fdy, tmp_path, monkeypatch):
    """A learner ahead of the Almanac needs the chapters in front of them before the ones already ticked off there."""
    graph = json.loads((tmp_path / "build/out/specs/9702/graph.json").read_text())
    graph["subtopics"] += [{"id": "9702-3.1", "title": "Momentum", "topic": "9702-2"},
                           {"id": "9702-2.2", "title": "Later", "topic": "9702-2"}]
    graph["kcs"] += [{"id": "9702-3.1.1", "subtopic": "9702-3.1", "title": "Momentum", "statement": "define momentum"},
                     {"id": "9702-2.2.1", "subtopic": "9702-2.2", "title": "Later", "statement": "use it"}]
    (tmp_path / "build/out/specs/9702/graph.json").write_text(json.dumps(graph))
    (tmp_path / "build/out/plan.json").write_text(json.dumps({"weeks": {
        "3": [{"id": "3-phys1", "type": "NEW", "kcs": ["9702-3.1.1"]}],
        "9": [{"id": "9-phys1", "type": "NEW", "kcs": ["9702-2.2.1"]}]}}))
    assert fdy.coverage()["next"] == ["9702-3.1", "9702-2.2"]  # nothing ticked: Almanac order
    vault = tmp_path / "vault"
    (vault / "Almanac").mkdir(parents=True)
    (vault / "Almanac/almanac-progress-2026-10-02.json").write_text(json.dumps({"done": {"3-phys1": 1}}))
    monkeypatch.setenv("STEM_TUTOR_VAULT", str(vault))
    assert fdy.coverage()["next"] == ["9702-2.2", "9702-3.1"]


# ---------------- two allowances: who does each job, and on which one ----------------
def test_every_role_can_run_on_either_allowance_cheapest_tier_first(fdy):
    cfg = fdy.config()
    assert set(cfg["ladders"]) == {"drafter", "fixer", "tiebreak", "solver", "checker", "adjudicator"}
    for role, ladders in cfg["ladders"].items():
        assert set(ladders) == {"claude", "codex"}, role
        for provider, rungs in ladders.items():
            assert len(rungs) >= 2 and all(len(r) == 2 for r in rungs), (role, provider)
    assert cfg["ladders"]["drafter"]["claude"][0] == ["opus", "low"]  # asked by the learner: Opus at its lowest effort


def test_work_goes_to_the_allowance_with_more_of_its_week_left(fdy):
    """Asked by the learner: split the work so both limits run out together, whichever starts with less."""
    pick, cfg = fdy.router.pick, fdy.config()
    assert pick("drafter", None, usage(50, 80), cfg, {}) == "claude"
    assert pick("drafter", None, usage(80, 50), cfg, {}) == "codex"
    assert pick("drafter", None, usage(50, 50, codex_days=1), cfg, {}) == "codex"  # the same left, but it resets sooner
    assert pick("drafter", None, usage(50, 20, codex_now=100), cfg, {}) == "claude"  # Codex's five hours are used up
    assert pick("drafter", None, usage(96, 97), cfg, {}) == "codex"  # the last of Claude's week is kept for the tutor
    with pytest.raises(fdy.router.Wait, match="used up"):
        pick("drafter", None, usage(100, 100), cfg, {})


def test_a_different_ai_family_checks_what_the_maker_wrote(fdy):
    pick, cfg = fdy.router.pick, fdy.config()
    left = usage(10, 90)  # Claude has far more left
    assert pick("solver", "claude", left, cfg, {}) == "codex"  # but Claude wrote the chapter
    assert pick("tiebreak", "claude", left, cfg, {}) == "codex"
    assert pick("solver", None, left, cfg, {}) == "claude"  # an old chapter with no known maker: the usual rule
    assert pick("fixer", "claude", left, cfg, {}) == "claude"  # only the blind roles are bound
    with pytest.raises(fdy.router.Wait, match="Codex"):
        pick("solver", "claude", usage(10, 100), cfg, {})  # the chapter waits for Codex rather than check itself


def test_jobs_already_running_count_against_an_allowance(fdy):
    pick, cfg = fdy.router.pick, fdy.config()
    assert pick("drafter", None, usage(46, 52), cfg, {}) == "codex"  # a little more left once the draft is counted
    assert pick("drafter", None, usage(46, 52), cfg, {"codex": ["drafter", "drafter"]}) == "claude"  # two drafts on it
    full = {"codex": ["solver"] * cfg["max_parallel"]["codex"]}
    assert pick("drafter", None, usage(90, 10), cfg, full) == "claude"  # no free slot on Codex
    with pytest.raises(fdy.router.Wait, match="running"):
        pick("drafter", None, usage(50, 50), cfg, {**full, "claude": ["solver"] * cfg["max_parallel"]["claude"]})


def test_each_role_starts_on_its_cheapest_tier_and_climbs_only_when_that_fails(fdy):
    """Asked by the learner: the least model that gives consistent output, for every job."""
    r, cfg, notes = fdy.router, fdy.config(), {}
    assert r.rung(notes, cfg, "drafter", "codex") == 0
    r.record(notes, cfg, "drafter", "codex", 0, ok=False)
    assert r.rung(notes, cfg, "drafter", "codex") == 0  # one failure is not a pattern
    assert r.rung(notes, cfg, "drafter", "codex", retry=0) == 1  # though the same chapter's retry goes one up
    r.record(notes, cfg, "drafter", "codex", 0, ok=False)
    assert r.rung(notes, cfg, "drafter", "codex") == 1  # twice running: this tier is not enough for the role
    assert r.rung(notes, cfg, "drafter", "claude") == 0 and r.rung(notes, cfg, "fixer", "codex") == 0
    r.record(notes, cfg, "drafter", "codex", 1, ok=False, limit=True)
    r.record(notes, cfg, "drafter", "codex", 1, ok=False, limit=True)
    assert r.rung(notes, cfg, "drafter", "codex") == 1  # a usage limit says nothing about the tier
    assert r.rung(notes, cfg, "drafter", "codex", retry=9) == len(cfg["ladders"]["drafter"]["codex"]) - 1


def test_a_codex_worker_runs_in_the_background_and_is_collected(fdy, monkeypatch):
    monkeypatch.setenv("FAKE_REPORT", json.dumps({"pack_path": "p", "note_path": "n", "items": 1, "templates": 0,
                                                  "worked": 0, "validator_ok": True, "lint_ok": True, "concerns": []}))
    fdy.cmd_add([SUB])
    with fdy.chapter(SUB) as st:
        st["stage"] = "draft"  # the "drafter" finds a valid pack already there
    fdy.cmd_run("drafter", SUB, on="codex")
    job = finished(fdy, "drafter")
    st = fdy.load(SUB)
    assert st["stage"] == "solve" and job["exit"] == 0 and st["gates"]["ok"]
    model, effort = fdy.config()["ladders"]["drafter"]["codex"][0]
    assert job["provider"] == "codex" and job["model"] == f"{model}/{effort}" and st["maker"] == "codex"


def test_a_claude_worker_runs_lean_and_reports_what_is_left(fdy, tmp_path, monkeypatch):
    """Opus at its lowest effort drafts in Codex's place: headless, with none of the learner's plugins or skills."""
    monkeypatch.setenv("FAKE_ARGV", str(tmp_path / "argv.json"))
    monkeypatch.setenv("FAKE_UTILIZATION", "0.64")
    monkeypatch.setenv("FAKE_REPORT", json.dumps({"items": 12, "concerns": []}))
    fdy.cmd_add([SUB])
    with fdy.chapter(SUB) as st:
        st["stage"] = "draft"
    fdy.cmd_run("drafter", SUB, on="claude")
    job = finished(fdy, "drafter")
    st = fdy.load(SUB)
    assert st["stage"] == "solve" and st["maker"] == "claude" and job["report"] == {"items": 12, "concerns": []}
    assert job["cost_usd"] == 0.5  # what the job cost is kept with it
    argv = json.loads((tmp_path / "argv.json").read_text())
    assert argv[argv.index("--model") + 1] == "opus" and argv[argv.index("--effort") + 1] == "low"
    assert "--safe-mode" in argv and argv[argv.index("--setting-sources") + 1] == ""
    assert "pack_path" in argv[argv.index("--json-schema") + 1]  # the report format the Codex drafter is held to
    week = json.loads(fdy.USAGE.read_text())["claude"]["windows"]["seven_day"]
    assert week["used"] == 64.0  # what the worker itself reported is now the newest reading


def test_a_chapters_retry_goes_one_tier_up(fdy, monkeypatch):
    fdy.cmd_add([SUB])
    with fdy.chapter(SUB) as st:
        st["stage"] = "draft"
    monkeypatch.setenv("FAKE_FAIL", "the model lost its way")
    fdy.cmd_run("drafter", SUB, on="codex")
    assert finished(fdy, "drafter")["exit"] == 1 and fdy.load(SUB)["stage"] == "draft"
    monkeypatch.delenv("FAKE_FAIL")
    fdy.cmd_run("drafter", SUB, on="codex")
    assert finished(fdy, "drafter")["model"] == "/".join(fdy.config()["ladders"]["drafter"]["codex"][1])


def test_a_usage_limit_closes_the_allowance_and_is_not_held_against_the_tier(fdy, monkeypatch):
    fdy.cmd_add([SUB])
    with fdy.chapter(SUB) as st:
        st["stage"] = "draft"
    monkeypatch.setenv("FAKE_FAIL", "ERROR: You've hit your usage limit. Upgrade to Pro or try again at 8:27 PM.")
    fdy.cmd_run("drafter", SUB, on="codex")
    finished(fdy, "drafter")
    monkeypatch.delenv("FAKE_FAIL")
    fdy.cmd_run("drafter", SUB)  # the router's own choice: level allowances would mean Codex
    job = finished(fdy, "drafter")
    assert job["provider"] == "claude" and job["rung"] == 0
    assert "usage limit" in " ".join(h["note"] for h in fdy.load(SUB)["history"])


def test_dispatch_starts_the_solver_and_the_checker_and_step_finishes_the_chapter(fdy, tmp_path, monkeypatch):
    fdy.cmd_add([SUB])
    right = tmp_path / "right.json"
    right.write_text(json.dumps(keys(fdy)))
    monkeypatch.setenv("FAKE_COPY", str(right))
    fdy.cmd_dispatch(SUB)
    st = fdy.load(SUB)
    assert sorted(st["jobs"]) == ["checker", "solver"] and fdy.action(st).startswith("wait")
    finished(fdy, "solver"), finished(fdy, "checker")
    fdy.cmd_dispatch(SUB)  # asked again: nothing is started twice
    assert fdy._running(fdy.load(SUB)) == []
    fdy.cmd_step(["another-chapter"])  # only the chapters named are touched
    assert fdy.load(SUB)["stage"] == "solve"
    fdy.cmd_step([SUB])  # compares: no disputes and no findings
    assert fdy.load(SUB)["stage"] == "sign"
    fdy.cmd_step()  # signs
    assert fdy.load(SUB)["stage"] == "ready"


def test_the_checker_can_finish_before_the_solvers(fdy):
    fdy.cmd_add([SUB])
    fdy.cmd_strip(SUB)
    fdy.WORK.mkdir(parents=True, exist_ok=True)
    (fdy.WORK / f"{SUB}.check.json").write_text(json.dumps({"findings": []}))
    fdy.cmd_compare(SUB)
    st = fdy.load(SUB)
    assert st["stage"] == "solve" and st["checked"]
    (fdy.BLIND / f"{SUB}.answers.json").write_text(json.dumps(keys(fdy)))
    fdy.cmd_compare(SUB)
    assert fdy.load(SUB)["stage"] == "sign"  # no disputes, no findings: straight to sign-off


def test_a_worker_that_died_without_reporting_is_started_again(fdy):
    fdy.cmd_add([SUB])
    fdy.cmd_strip(SUB)
    with fdy.chapter(SUB) as st:  # its process is gone and nothing was collected (the Mac slept, the job was killed)
        st["jobs"]["solver"] = {"pid": 999999, "provider": "claude", "started": fdy.now(),
                                "expects": f"build/work/blind/{SUB}.answers.json"}
    st = fdy.load(SUB)
    assert fdy._running(st) == [] and fdy.action(st) == f"foundry.py dispatch {SUB}"


def test_escalate_starts_the_adjudicator_on_its_first_tier(fdy):
    fdy.cmd_add([SUB])
    fdy.cmd_escalate(SUB)
    job = finished(fdy, "adjudicator")
    assert job["model"] == "/".join(fdy.config()["ladders"]["adjudicator"][job["provider"]][0])
    assert (REPO / "foundry/roles/adjudicator.md").exists()


def test_usage_shows_both_allowances_and_where_the_next_job_goes(fdy, tmp_path, capsys):
    (tmp_path / "usage-now.json").write_text(json.dumps(usage(70, 84, codex_now=29)))
    fdy.cmd_usage()
    out = capsys.readouterr().out
    assert "Claude" in out and "70%" in out and "Codex" in out and "84%" in out and "29%" in out
    assert "next job: Claude" in out  # more of its week is left, even with some kept back for the tutor


def test_a_stale_claude_reading_is_refreshed_by_asking_claude_itself(fdy, tmp_path, monkeypatch):
    """Claude has no command that reports its limits. Claude Code's own note of them is refreshed only when a session
    starts, so it can be hours behind; every headless run is told the current figure, so a one-word run is the way
    to ask (a fraction of a cent)."""
    fake = str(REPO / "tests/fake_worker.py")
    monkeypatch.delenv("FOUNDRY_USAGE_FILE")
    cache = tmp_path / "claude.json"
    week = {"kind": "weekly_all", "percent": 72, "is_active": True, "resets_at": "2099-01-01T00:00:00+00:00"}
    cache.write_text(json.dumps({"cachedUsageUtilization": {"fetchedAtMs": (time.time() - 1200) * 1000, "utilization": {
        "limits": [{"kind": "session", "percent": 0, "is_active": False, "resets_at": None}, week]}}}))
    monkeypatch.setenv("FOUNDRY_CLAUDE_STATE", str(cache))
    monkeypatch.setenv("FAKE_UTILIZATION", "0.81")
    notes = {}
    now = fdy.router.usage(notes, fake, fake)
    assert now["codex"] is None  # this fake has no app server: nothing is known, which is not the same as nothing left
    assert now["claude"]["seven_day"]["used"] == 81.0 and list(now["claude"]) == ["seven_day"]  # no five-hour cap in force
    asked = notes["claude"]["probed"]
    monkeypatch.setenv("FAKE_UTILIZATION", "0.99")
    assert fdy.router.usage(notes, fake, fake)["claude"]["seven_day"]["used"] == 81.0  # fresh: not asked again
    assert notes["claude"]["probed"] == asked


def test_claudes_cache_is_read_whatever_the_python(fdy, tmp_path, monkeypatch):
    """Claude Code notes reset times ending in Z, which Python before 3.11 cannot read with fromisoformat."""
    class Py310(fdy.router.datetime):
        @classmethod
        def fromisoformat(cls, s):
            if s.endswith("Z"):
                raise ValueError(f"Invalid isoformat string: {s!r}")
            return super().fromisoformat(s)
    monkeypatch.setattr(fdy.router, "datetime", Py310)
    cache = tmp_path / "claude.json"
    cache.write_text(json.dumps({"cachedUsageUtilization": {"fetchedAtMs": 1000, "utilization": {"limits": [
        {"kind": "weekly_all", "percent": 72, "is_active": True, "resets_at": "2099-01-01T00:00:00Z"}]}}}))
    assert fdy.router.claude_cache(cache) == ({"seven_day": {"used": 72.0, "resets": 4070908800.0}}, 1.0)


def test_asking_for_the_rest_of_a_big_chapter_keeps_the_shards_already_solved(fdy, tmp_path, monkeypatch):
    """Seen on the first real run: three of five shards were solved, the other two had no free slot, and asking again
    wrote the questions afresh, which threw the three finished answer files away and solved them a second time."""
    cfg = {**fdy.config(), "solver_shard_size": 5, "max_parallel": {"codex": 1, "claude": 1}}
    monkeypatch.setattr(fdy, "config", lambda: cfg)
    fdy.cmd_add([SUB])
    with fdy.chapter(SUB) as st:
        st["checked"] = True  # the solvers only
    right = tmp_path / "right.json"
    right.write_text(json.dumps(keys(fdy)))
    monkeypatch.setenv("FAKE_COPY", str(right))
    fdy.cmd_dispatch(SUB)  # one slot on each allowance: two shards start, the rest wait
    first = {n: j["started"] for n, j in fdy.load(SUB)["jobs"].items()}
    assert sorted(first) == ["solver#1", "solver#2"]
    finished(fdy, "solver#1"), finished(fdy, "solver#2")
    time.sleep(1.1)  # so that a job started again would show a later time
    fdy.cmd_dispatch(SUB)
    jobs = fdy.load(SUB)["jobs"]
    assert (fdy.BLIND / f"{SUB}.answers.part1.json").exists() and (fdy.BLIND / f"{SUB}.answers.part2.json").exists()
    assert {n: jobs[n]["started"] for n in first} == first and len(jobs) == 4  # two more started, none again


def test_a_solver_the_tiebreak_keeps_overturning_is_on_too_weak_a_tier(fdy):
    """Seen on the first real run: the cheapest Codex solver "succeeded" on every shard and was wrong on 34 of 92
    questions. Finishing is not enough for a blind solver: what counts is how often the tiebreak sides with the key."""
    fdy.cmd_add([SUB])
    fdy.cmd_strip(SUB)
    answers = keys(fdy)
    for qid in list(answers)[:4]:  # four slips
        answers[qid] = {"A": "B", "B": "C", "C": "D", "D": "A"}.get(answers[qid], "999")
    (fdy.BLIND / f"{SUB}.answers.json").write_text(json.dumps(answers))
    with fdy.chapter(SUB) as st:
        st["checked"] = True
        st["jobs"]["solver"] = {"provider": "codex", "rung": 0, "started": fdy.now(), "finished": fdy.now(), "exit": 0}
    fdy.cmd_compare(SUB)
    assert fdy.load(SUB)["stage"] == "tiebreak"
    (fdy.BLIND / f"{SUB}.tiebreak.json").write_text(json.dumps({q: keys(fdy)[q] for q in list(answers)[:4]}))
    fdy.cmd_compare(SUB)  # the tiebreak agrees with the key every time: the solver slipped four times
    notes = json.loads(fdy.USAGE.read_text())
    assert notes["misses"]["solver/codex"] == 1
    fdy.router.record(notes, fdy.config(), "solver", "codex", 0, ok=True, judge=False)  # a shard merely finishing
    assert notes["misses"]["solver/codex"] == 1  # does not clear it


def test_a_job_refused_by_claudes_five_hour_limit_closes_claude_until_that_window_resets(fdy, tmp_path, monkeypatch):
    """Claude tells a headless run about one limit only, the one nearest its end, so its five-hour window is often
    unknown until a job runs into it. The refusal names the window and when it reopens."""
    r, cfg, notes, now = fdy.router, fdy.config(), {}, time.time()
    facts = r.claude_events(json.dumps({"type": "rate_limit_event", "rate_limit_info": {
        "status": "rejected", "rateLimitType": "five_hour", "resetsAt": now + 3600}}))
    assert facts["limit"] and facts["windows"]["five_hour"]["used"] == 100.0
    r.record(notes, cfg, "drafter", "claude", 0, ok=False, limit=True, windows=facts["windows"], now=now)
    monkeypatch.delenv("FOUNDRY_USAGE_FILE")
    monkeypatch.setenv("FOUNDRY_CLAUDE_STATE", str(tmp_path / "none.json"))
    fake = str(REPO / "tests/fake_worker.py")
    seen = r.usage(notes, fake, fake, now=now + 700)["claude"]  # past the ten-minute pause: the window still has not reset
    closed, why = r.score("claude", seen, cfg, [], now=now + 700)
    assert closed is None and "used up until" in why
    assert r.score("claude", seen, cfg, [], now=now + 3700)[0] is not None  # reopened at its reset
    assert notes["misses"].get("drafter/claude", 0) == 0  # and not held against the tier


def test_a_figure_claude_does_not_report_can_be_passed_on(fdy, tmp_path, monkeypatch, capsys):
    """Asked by the learner: why is Claude's own five-hour window not shown? A headless run is not told it. The Claude
    app shows it, so the manager (or the learner) passes it on, and the router then counts it."""
    monkeypatch.delenv("FOUNDRY_USAGE_FILE")
    monkeypatch.setenv("FOUNDRY_CLAUDE_STATE", str(tmp_path / "none.json"))
    fake = str(REPO / "tests/fake_worker.py")
    fdy.cmd_usage()
    assert "5 hours    not reported by Claude" in capsys.readouterr().out
    fdy.cmd_reading("claude", "five_hour", "74", "2099-01-01T00:00:00Z")
    out = capsys.readouterr().out
    assert "5 hours     74% used" in out and "not reported" not in out
    fdy.cmd_reading("claude", "five_hour", "97", "2099-01-01T00:00:00Z")
    with fdy.notes() as n:
        seen = fdy.router.usage(n, fake, fake)["claude"]
    assert fdy.router.score("claude", seen, fdy.config(), [])[0] is None  # the last few percent are kept back


def test_readings_taken_before_a_wait_are_kept(fdy):
    """The router reads both allowances, then may find no allowance can take the job: what it read is still noted."""
    with pytest.raises(fdy.router.Wait):
        with fdy.notes() as n:
            n["claude"] = {"read": 1}
            raise fdy.router.Wait("no allowance can take a drafter now")
    assert json.loads(fdy.USAGE.read_text())["claude"] == {"read": 1}


def test_chapters_held_at_once_are_all_held(fdy):
    """Several workers finish together and each holds or releases its chapter: none may undo another's."""
    import threading
    subs = [f"9702-{n}.1" for n in range(1, 41)]
    threads = [threading.Thread(target=lambda s=s: [fdy.hold(s, "in the foundry") for _ in range(5)]) for s in subs]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(json.loads(fdy.HOLD.read_text())) == sorted(subs)
    assert not list(fdy.HOLD.parent.glob("*.tmp"))


def test_a_refused_claude_worker_is_recorded_as_a_limit_not_a_failure(fdy, monkeypatch):
    fdy.cmd_add([SUB])
    with fdy.chapter(SUB) as st:
        st["stage"] = "draft"
    monkeypatch.setenv("FAKE_REJECT", "five_hour")
    fdy.cmd_run("drafter", SUB, on="claude")
    job = finished(fdy, "drafter")
    notes = json.loads(fdy.USAGE.read_text())
    assert job["limit"] and not job["ok"] and notes["claude"]["windows"]["five_hour"]["used"] == 100.0
    assert notes["misses"].get("drafter/claude", 0) == 0 and fdy.load(SUB)["stage"] == "draft"


def test_a_job_goes_only_where_there_is_room_for_it(fdy):
    """Seen on the learner's own figures: 18% of Claude's five-hour window was left and a draft by Opus takes about
    21% of one, so the draft would have run into the limit part-way through. Small jobs still fit."""
    pick, cfg = fdy.router.pick, fdy.config()
    seen = usage(60, 80)
    seen["claude"]["five_hour"] = {"used": 77, "resets": time.time() + 3 * 3600}
    assert pick("drafter", None, seen, cfg, {}) == "codex"  # by the week alone it would be Claude
    assert pick("solver", None, seen, cfg, {}) == "claude"  # a blind solve is small enough


def test_codex_windows_reads_a_five_hour_window_when_the_plan_has_one(fdy):
    r = fdy.router
    both = {"rateLimits": {"primary": {"usedPercent": 62, "windowDurationMins": 300, "resetsAt": 2_000_000_000},
                           "secondary": {"usedPercent": 39, "windowDurationMins": 10080, "resetsAt": 2_000_100_000}}}
    assert r.codex_windows(both) == {"five_hour": {"used": 62.0, "resets": 2_000_000_000},
                                     "seven_day": {"used": 39.0, "resets": 2_000_100_000}}
    week_only = {"rateLimits": {"primary": {"usedPercent": 39, "windowDurationMins": 10080, "resetsAt": 5}, "secondary": None},
                 "ordinaryUsageAllowed": True}
    assert list(r.codex_windows(week_only)) == ["seven_day"]  # this plan: a week only
    assert r.codex_windows({}) is None and r.codex_windows({"rateLimits": {"primary": None}}) is None


def test_codex_saying_use_is_not_allowed_closes_it_until_the_nearest_reset(fdy):
    r, cfg, now = fdy.router, fdy.config(), time.time()
    blocked = {"ordinaryUsageAllowed": False, "rateLimits": {
        "primary": {"usedPercent": 100, "windowDurationMins": 300, "resetsAt": now + 3000},
        "secondary": {"usedPercent": 40, "windowDurationMins": 10080, "resetsAt": now + 90000}}}
    w = r.codex_windows(blocked)
    assert w["limit"] == {"used": 100.0, "resets": now + 3000}
    closed, why = r.score("codex", w, cfg, [], now=now)
    assert closed is None and "used up" in why
    assert r.score("codex", {"seven_day": {"used": 40.0, "resets": now + 90000}}, cfg, [], now=now)[0] is not None


def test_a_codex_limit_message_says_when_it_reopens(fdy):
    r, now = fdy.router, time.time()
    at = r.reset_from_message("ERROR: You've hit your usage limit. Upgrade to Pro or try again at 8:27 PM.", now)
    assert at and at > now and at - now <= 86400 + 60 and datetime.fromtimestamp(at).strftime("%H:%M") == "20:27"
    assert r.reset_from_message("usage limit reached, try again in 3 hours 20 minutes", now) == now + 3 * 3600 + 20 * 60
    assert r.reset_from_message("try again in 45 minutes", now) == now + 2700
    assert r.reset_from_message("something broke", now) is None


def test_a_codex_five_hour_limit_closes_codex_until_it_reopens_not_for_ten_minutes(fdy):
    r, cfg, now = fdy.router, fdy.config(), time.time()
    notes = {}
    r.record(notes, cfg, "drafter", "codex", 0, ok=False, limit=True, now=now, until=now + 7200)
    assert notes["codex"]["closed_until"] == now + 7200  # the message said two hours
    r.record(notes, cfg, "drafter", "codex", 0, ok=False, limit=True, now=now,
             windows={"five_hour": {"used": 100.0, "resets": now + 9000}, "seven_day": {"used": 40.0, "resets": now + 99999}})
    assert notes["codex"]["closed_until"] == now + 9000  # the window that is full
    r.record(notes, cfg, "drafter", "codex", 0, ok=False, limit=True, now=now)
    assert notes["codex"]["closed_until"] == now + 600  # nothing known: the old ten minutes
    assert notes["misses"].get("drafter/codex", 0) == 0


def test_usage_says_when_codex_reports_no_five_hour_window(fdy, monkeypatch, capsys):
    monkeypatch.delenv("FOUNDRY_USAGE_FILE", raising=False)
    monkeypatch.setattr(fdy.router, "codex_usage", lambda binary, timeout=20: {"seven_day": {"used": 39.0, "resets": time.time() + 9e5}})
    fdy.cmd_usage()
    assert "Codex   5 hours    not reported by Codex for this plan" in capsys.readouterr().out
