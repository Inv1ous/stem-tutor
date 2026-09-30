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
    with pytest.raises(SystemExit, match="Codex role"):
        fdy.cmd_prompt("drafter", SUB)


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
