"""The bug-fix system (bugfix/bugfix.py): findings become jobs, a Codex fixer works in its own worktree, the system
commits and gates its work, a reviewer reads it, the manager accepts it into the main checkout. Codex is faked."""
import importlib
import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
BUGS = """# BUGS — written by Codex only

```
### B-014 · P1 · session.py · the format example in the header is not a finding
```

### B-001 · P0 · calc.py · add() adds one too many
- **Found:** 10:00 · **Method:** ran · **Confidence:** high
- **Where:** `calc.py` · `add`
- **Repro:** add(1, 2)
- **Expected:** 3
- **Actual:** 4
- **Impact:** wrong marks
- 10:05 REPLY B-001 · negatives too: add(-1, -1) gives -1
- 10:06 SWEEP · calc · done

### B-002 · P2 · screens.py · [visual] a label wraps at 80x24
- **Found:** 10:10 · **Method:** read · **Confidence:** low
- **Where:** screens.py
- **Repro:** x
- **Expected:** x
- **Actual:** x
- **Impact:** x

### B-003 · P3 · calc.py · fixed long ago
- **Found:** 09:00
"""

FAKE = r'''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
a = sys.argv[1:]
wt, out, schema, prompt = Path(a[a.index("-C") + 1]), a[a.index("-o") + 1], a[a.index("--output-schema") + 1], a[-1]
role = Path(schema).stem
if role == "fixer":
    verdicts = []
    if "B-001" in prompt:
        (wt / "calc.py").write_text("def add(a, b):\n    return a + b\n")
        (wt / "tests").mkdir(exist_ok=True)
        (wt / "tests" / "test_bf_j01.py").write_text("def test_add():\n    assert True\n")
        (wt / "probe.txt").write_text("scratch left behind")
        verdicts.append({"id": "B-001", "verdict": "FIXED", "cause": "an extra + 1 in add", "fix": "removed it",
                         "reason": "", "test": "tests/test_bf_j01.py::test_add"})
        if os.environ.get("FAKE_FORBIDDEN"):
            (wt / "CHANGELOG.md").write_text("not yours")
    if "B-002" in prompt:
        verdicts.append({"id": "B-002", "verdict": "REJECTED", "cause": "", "fix": "",
                         "reason": "the label fits at 80x24 (checked)", "test": ""})
    report = {"verdicts": verdicts, "decisions": ["kept the wording"], "notes": ""}
else:
    report = {"approve": os.environ.get("FAKE_REVIEW", "yes") == "yes", "summary": "fine", "per_bug": [],
              "findings": [] if os.environ.get("FAKE_REVIEW", "yes") == "yes" else
              [{"severity": "major", "file": "calc.py", "problem": "weak test", "fix": "assert add(1, 2) == 3"}]}
Path(out).write_text(json.dumps(report))
'''


def git(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, check=True).stdout


@pytest.fixture
def bf(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    (repo / "bugwatch/codex").mkdir(parents=True)
    (repo / "bugwatch/codex/BUGS.md").write_text(BUGS)
    (repo / "bugwatch/FIXES.md").write_text("# FIXES\n\n- 11:00 B-003 FIXED · done long ago\n")
    (repo / "calc.py").write_text("def add(a, b):\n    return a + b + 1\n")
    git(tmp_path, "init", "-q", "-b", "main", str(repo))
    git(repo, "add", "-A")
    git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "start")
    fake = tmp_path / "codex"
    fake.write_text(FAKE)  # not the venv's python in the shebang: its path has spaces
    fake.chmod(0o755)
    for k, v in {"BUGFIX_REPO": repo, "BUGFIX_STATE": tmp_path / "state", "BUGFIX_WORKTREES": tmp_path / "wt",
                 "BUGFIX_CODEX": fake, "BUGFIX_TEST_CMD": "true", "BUGFIX_NOTIFY": "0", "BUGFIX_PUBLISH": "0",
                 "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}.items():
        monkeypatch.setenv(k, str(v))
    monkeypatch.syspath_prepend(str(REPO / "bugfix"))
    import bugfix
    return importlib.reload(bugfix), repo


def settle(bf, seconds=60):
    end = time.time() + seconds
    while time.time() < end and any(j["stage"] in bf.LIVE for j in bf.peek()["jobs"].values()):
        time.sleep(0.3)
    return {j["id"]: j for j in bf.peek()["jobs"].values()}


def test_findings_are_read_with_their_replies_and_statuses(bf):
    bf, repo = bf
    every = bf.findings()
    assert set(every) == {"B-001", "B-002", "B-003"}  # the example in the header's code block is not a finding
    assert every["B-001"]["replies"] == ["- 10:05 REPLY B-001 · negatives too: add(-1, -1) gives -1"]
    assert "SWEEP" not in every["B-001"]["block"] and "**Impact:** wrong marks" in every["B-001"]["block"]
    assert every["B-003"]["status"] == "FIXED" and [b["id"] for b in bf.open_findings()] == ["B-001", "B-002"]
    assert bf.suggest(every["B-001"]) == ("gpt-6-astra/high", "gpt-6-astra/xhigh")
    assert bf.suggest(every["B-002"])[0] == "gpt-6-astra/medium"  # a screen: the UI tier, not the P2 one
    assert bf.group_key(every["B-001"]) == "calc.py"
    assert bf.climb("gpt-6-sol/high") == "gpt-6-astra/medium" and bf.climb("gpt-6-astra/xhigh") == "gpt-6-astra/xhigh"


def test_a_job_goes_from_finding_to_merged_fix_with_its_verdicts_in_fixes(bf):
    bf, repo = bf
    bf.cmd_plan(["--suggested"])
    jobs = bf.peek()["jobs"]
    assert [j["bugs"] for j in jobs.values()] == [["B-001"], ["B-002"]]
    bf.cmd_step()
    jobs = settle(bf)
    assert jobs["J01"]["stage"] == "review", jobs["J01"]["history"]
    wt = Path(jobs["J01"]["worktree"])
    assert not (wt / "probe.txt").exists()  # scratch outside the code folders is not committed, and is removed
    assert "add(a, b):\n    return a + b\n" in git(wt, "show", "HEAD:calc.py")
    assert jobs["J02"]["stage"] == "review"  # a REJECTED with no change still goes to a reviewer
    bf.cmd_step()
    jobs = settle(bf)
    assert jobs["J01"]["stage"] == jobs["J02"]["stage"] == "ready"
    bf.cmd_accept("J01")
    assert (repo / "calc.py").read_text() == "def add(a, b):\n    return a + b\n"
    fixes = (repo / "bugwatch/FIXES.md").read_text()
    assert "B-001 FIXED · an extra + 1 in add → removed it" in fixes and "test tests/test_bf_j01.py::test_add" in fixes
    assert not wt.exists() and bf.peek()["jobs"]["J01"]["stage"] == "merged"
    bf.cmd_accept("J02")
    assert "B-002 REJECTED · the label fits at 80x24 (checked)" in (repo / "bugwatch/FIXES.md").read_text()
    assert bf.open_findings() == [] and git(repo, "status", "--porcelain") == ""


def test_a_fixer_that_touches_a_file_it_may_not_is_sent_back_one_tier_up(bf, monkeypatch):
    bf, repo = bf
    monkeypatch.setenv("FAKE_FORBIDDEN", "1")
    bf.cmd_plan(["B-001", "--model", "gpt-6-sol/high"])
    bf.cmd_step()
    job = settle(bf)["J01"]
    assert job["stage"] == "fix" and job["gates"]["forbidden"] == ["CHANGELOG.md"]
    assert job["model"] == "gpt-6-astra/medium" and "CHANGELOG.md" in job["feedback"][-1]["text"]
    assert "CHANGELOG.md" not in git(Path(job["worktree"]), "show", "--name-only", "HEAD")


def test_a_review_that_asks_for_changes_sends_the_job_back_with_its_findings(bf, monkeypatch):
    bf, repo = bf
    monkeypatch.setenv("FAKE_REVIEW", "no")
    bf.cmd_plan(["B-001"])
    bf.cmd_step()
    settle(bf)
    bf.cmd_step()
    job = settle(bf)["J01"]
    assert job["stage"] == "fix" and "weak test" in job["feedback"][-1]["text"]
    assert "weak test" in bf.role_prompt(job, "fixer")  # the next round is told what to address


def test_the_manager_can_send_a_job_back_and_close_a_finding_without_a_job(bf):
    bf, repo = bf
    bf.cmd_plan(["B-001"])
    bf.cmd_reject("J01", ["use", "integer", "maths", "--model", "gpt-6-astra/high"])
    job = bf.peek()["jobs"]["J01"]
    assert job["stage"] == "fix" and job["model"] == "gpt-6-astra/high"
    assert job["feedback"][-1] == {"from": "manager", "text": "use integer maths"}
    bf.cmd_close("B-002", "DEFERRED", "needs the new layout first")
    assert "B-002 DEFERRED · needs the new layout first" in (repo / "bugwatch/FIXES.md").read_text()
    assert [b["id"] for b in bf.open_findings()] == []  # B-001 is in a job, B-002 is closed
