"""The content foundry's board, gates and hand-offs, on a scratch copy of the build tree with a fake Codex."""
import importlib
import json
import sys
import time
from pathlib import Path

import pytest

from fixtures import GRAPH

REPO = Path(__file__).resolve().parents[1]
SUB = "9702-2.1"


@pytest.fixture
def fdy(tmp_path, monkeypatch):
    sys.path.insert(0, str(REPO / "tests"))
    from test_validate import good_pack
    pack = good_pack()
    (tmp_path / "build/out/packs/9702").mkdir(parents=True)
    (tmp_path / "build/out/specs/9702").mkdir(parents=True)
    (tmp_path / "build/work/bundles").mkdir(parents=True)
    (tmp_path / "build/work/bundles" / f"{SUB}.md").write_text("# Bundle\n")
    (tmp_path / f"build/out/packs/9702/{SUB}.json").write_text(json.dumps(pack))
    (tmp_path / "build/out/specs/9702/graph.json").write_text(json.dumps(GRAPH))
    note = tmp_path / "build/out/notes" / pack["note"]
    note.parent.mkdir(parents=True)
    note.write_text("# 2.1 Equations of motion\n\nUse $v = u + at$.\n")
    monkeypatch.setenv("FOUNDRY_ROOT", str(tmp_path))
    monkeypatch.setenv("FOUNDRY_NOTIFY", "0")  # no Mac notifications from tests
    monkeypatch.setenv("FOUNDRY_PUBLISH", "0")  # never publish into the real vault from tests
    monkeypatch.setenv("FOUNDRY_COMMIT", "0")
    sys.path.insert(0, str(REPO / "foundry"))
    import foundry
    return importlib.reload(foundry)


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


def test_codex_worker_runs_in_the_background_and_is_collected(fdy, tmp_path, monkeypatch):
    fake = tmp_path / "fake_codex.py"
    fake.write_text("#!/usr/bin/env python3\nimport json, sys\na = sys.argv\n"
                    "open(a[a.index('-o') + 1], 'w').write(json.dumps({'pack_path': 'p', 'note_path': 'n', 'items': 1,"
                    " 'templates': 0, 'worked': 0, 'validator_ok': True, 'lint_ok': True, 'concerns': []}))\n")
    fake.chmod(0o755)
    monkeypatch.setattr(fdy, "CODEX", str(fake))
    monkeypatch.setenv("FOUNDRY_CODEX", str(fake))
    fdy.cmd_add([SUB], stage="draft")
    fdy.pack_path(SUB).rename(tmp_path / "held.json")  # a new chapter: no pack yet
    with fdy.chapter(SUB) as st:
        st["stage"] = "draft"
    (tmp_path / "held.json").rename(fdy.pack_path(SUB))  # the "drafter" leaves a valid pack behind
    fdy.cmd_codex("drafter", SUB)
    for _ in range(100):
        if fdy.load(SUB)["stage"] != "draft":
            break
        time.sleep(0.1)
    st = fdy.load(SUB)
    assert st["stage"] == "solve" and st["jobs"]["drafter"]["exit"] == 0 and st["gates"]["ok"]
    cmd = fdy.config()["tiers"][fdy.config()["roles"]["drafter"]][0]
    assert st["jobs"]["drafter"]["model"].startswith(cmd)


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


def test_the_checker_runs_alongside_the_solvers(fdy, capsys):
    fdy.cmd_add([SUB])
    capsys.readouterr()
    fdy.cmd_dispatch(SUB)
    jobs = json.loads(capsys.readouterr().out.split("\n", 1)[1])  # after the strip line
    assert {j["role"] for j in jobs} == {"solver", "checker"}
    fdy.WORK.mkdir(parents=True, exist_ok=True)
    (fdy.WORK / f"{SUB}.check.json").write_text(json.dumps({"findings": []}))  # the checker finishes first
    fdy.cmd_compare(SUB)
    st = fdy.load(SUB)
    assert st["stage"] == "solve" and st["checked"]
    (fdy.BLIND / f"{SUB}.answers.json").write_text(json.dumps(keys(fdy)))
    fdy.cmd_compare(SUB)
    assert fdy.load(SUB)["stage"] == "sign"  # no disputes, no findings: straight to sign-off


def test_a_codex_job_run_by_hand_is_not_duplicated_and_reports_back(fdy):
    fdy.cmd_add([SUB])
    with fdy.chapter(SUB) as st:
        st["stage"] = "fix"
        st["fixes"] = [{"ref": "note", "instruction": "x", "status": "open"}]
    fdy.cmd_prompt("fixer", SUB)  # printed for pasting into the Codex app
    assert fdy._running(fdy.load(SUB)) == ["fixer"]
    with pytest.raises(SystemExit, match="already working"):
        fdy.cmd_codex("fixer", SUB)
    fdy.cmd_collect("fixer", SUB, "-", "0")
    st = fdy.load(SUB)
    assert fdy._running(st) == [] and st["stage"] == "sign"


def test_dispatched_haiku_jobs_show_as_working_until_their_file_is_written(fdy, capsys):
    fdy.cmd_add([SUB])
    with fdy.chapter(SUB) as st:
        st["checked"] = True  # only the solver this time
    fdy.cmd_dispatch(SUB)
    st = fdy.load(SUB)
    assert fdy._haiku(st) == (["solver"], []) and "Haiku solver working (0/1 done)" in fdy.action(st)
    assert "Haiku solver …" in fdy.watch_text()
    (fdy.BLIND / f"{SUB}.answers.json").write_text(json.dumps(keys(fdy)))
    assert fdy._haiku(fdy.load(SUB)) == ([], ["solver"])
    fdy.cmd_compare(SUB)
    assert fdy._haiku(fdy.load(SUB)) == ([], [])  # closed once compared


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


def test_a_haiku_worker_that_never_reports_is_flagged_as_stalled(fdy):
    fdy.cmd_add([SUB])
    fdy.cmd_dispatch(SUB)
    with fdy.chapter(SUB) as st:  # dispatched an hour ago; the Claude session ran out before the agents wrote anything
        for j in st["jobs"].values():
            j["started"] = "2020-01-01T00:00:00+08:00"
    st = fdy.load(SUB)
    assert fdy._stalled(st) and "re-dispatch" in fdy.action(st) and "stalled" in fdy.watch_text()


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
