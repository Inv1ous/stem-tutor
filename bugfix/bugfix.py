#!/usr/bin/env python3
"""The bug-fix system: Codex workers fix the bug watch's findings; a manager (Claude Opus, in /bugfix) only decides.

Same mechanics as the foundry and refine (state file, headless workers on the learner's Codex allowance, a worker's
shell runs `collect` when it ends), applied to bugwatch/codex/BUGS.md. A job is one to three related findings. Its
fixer works in a git worktree of its own; `collect` commits what it changed (a Codex sandbox cannot write .git),
refuses edits to files no fixer may touch, and runs the test suites. A reviewer on a stronger tier then reads the diff
against bugfix/DESIGN.md. Red tests or a rejected review send the job back to its fixer, one tier higher. A job that
passes waits for the manager, who accepts it (merged into the main checkout, verdicts written to FIXES.md) or sends it
back with one line of instruction.

  bugfix.py triage                       open findings, one line each, with the suggested group and tiers
  bugfix.py plan --suggested             make jobs of every open finding not in one, as triage suggests
  bugfix.py plan B-042,B-057 [--model M/E] [--review M/E] [--note TEXT]   one job, the manager's choice
  bugfix.py set J03 [--model M/E] [--review M/E] [--note TEXT]            change a job that is not running
  bugfix.py step                         launch what can start (fixers, reviewers), then the board
  bugfix.py wait [seconds]               return when a worker finishes (or after `seconds`, default 540)
  bugfix.py board                        one line per job
  bugfix.py packet J03                   what the manager needs to decide: verdicts, diff size, tests, review
  bugfix.py diff J03 [path]              the job's diff (for a closer look)
  bugfix.py accept J03                   merge it, write its verdicts to FIXES.md, remove its worktree
  bugfix.py reject J03 TEXT [--model M/E] [--restart]   back to its fixer with TEXT (--restart: a fresh worktree)
  bugfix.py drop J03                     give the job up; its findings go back to the open pool
  bugfix.py close B-123 REJECTED|DEFERRED|DUPLICATE TEXT   a verdict without a job
  bugfix.py release [--sign]             a scribe writes the release notes; --sign: checks, publish, commit, tag
  bugfix.py usage                        the Codex allowance
  bugfix.py watch [seconds]              live board
  bugfix.py install-skill                install /bugfix (the manager loop, on Opus)
  bugfix.py collect JOB ROLE OUT EXIT    called by a worker's shell when it ends

Stages: queued → fixing → gating → review → reviewing → ready → merged   (fix = back to the fixer; stuck = the manager
decides; dropped). Tiers are written model/effort, e.g. gpt-6-astra/high.
"""
from __future__ import annotations

import fcntl
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
TARGET = Path(os.environ.get("BUGFIX_REPO") or REPO)  # the git checkout the fixes land in (a scratch repo in tests)
STATE_DIR = Path(os.environ.get("BUGFIX_STATE") or HERE / "state")
LOGS = STATE_DIR.parent / "logs" if os.environ.get("BUGFIX_STATE") else HERE / "logs"
WT = Path(os.environ.get("BUGFIX_WORKTREES") or TARGET / ".bugfix-wt")
BUGS, FIXES = TARGET / "bugwatch/codex/BUGS.md", TARGET / "bugwatch/FIXES.md"
PY = str(REPO / ".venv/bin/python")
CODEX = os.environ.get("BUGFIX_CODEX") or os.environ.get("FOUNDRY_CODEX") or shutil.which("codex") or \
    "/Applications/ChatGPT.app/Contents/Resources/codex-cli/bin/codex"
CLAUDE = os.environ.get("BUGFIX_CLAUDE") or os.environ.get("FOUNDRY_CLAUDE") or shutil.which("claude") or "claude"
# Claude workers: lean (none of the learner's plugins, skills, hooks or servers), as in the foundry
LEAN = ["--output-format", "stream-json", "--verbose", "--safe-mode", "--disable-slash-commands", "--strict-mcp-config",
        "--setting-sources", "", "--no-session-persistence"]
READ_BASH = ["Bash(git diff *)", "Bash(git log *)", "Bash(git show *)", "Bash(git status *)", "Bash(ls *)"]

HEAD = re.compile(r"^### (B-\d+) · (P[0-3]) · ([^·]+?) · (.+)$")
VERDICT = re.compile(r"^- \d\d:\d\d (B-\d+) (CONFIRMED|FIXED|REJECTED|DUPLICATE|DEFERRED|NEEDS-INFO)\b")
DONE = {"FIXED", "VERIFIED", "REJECTED", "DUPLICATE", "DEFERRED"}  # the board's REOPENED is open
LIVE = ("fixing", "gating", "reviewing", "scribing")
# what a fixer may never change: the release notes and versions (the scribe's), the bug watch's own logs, the test set-up
FORBIDDEN = ("CHANGELOG.md", "STATUS.md", "README.md", "plugin/stem-tutor/.claude-plugin/plugin.json",
             "app/tutor_app/__init__.py", "build/out/notes/How It Works.md", "bugwatch/codex/", "bugwatch/FIXES.md",
             "bugwatch/README.md", "bugwatch/bugs.py", "bugwatch/post.py", "tests/conftest.py", "tests/app/conftest.py",
             ".codex/", "bugfix/", "refine/state/", "foundry/state/", ".gitignore")
ALLOWED = ("app/", "plugin/", "build/", "foundry/", "refine/", "tests/", "bin/", "bugwatch/sandbox.sh", "bugwatch/check.sh",
           "docs/", "eval/")
RELEASE_FILES = ("CHANGELOG.md", "STATUS.md", "README.md", "plugin/stem-tutor/.claude-plugin/plugin.json",
                 "app/tutor_app/__init__.py", "build/out/notes/How It Works.md")
LINKED = (".venv", "build/out/assets", "sources/papers", "sources/specs")  # untracked data a worktree needs (all ignored)
ENGINE_TESTS = ["-m", "pytest", "tests", "-q", "-rf", "--tb=line", "-p", "no:cacheprovider", "--ignore=tests/app",
                "--deselect", "tests/test_speech.py", "--ignore=tests/test_tts.py"]
APP_TESTS = ["-m", "pytest", "tests/app", "-q", "-rf", "--tb=line", "-p", "no:cacheprovider"]


def config() -> dict:
    cfg = json.loads((HERE / "config.json").read_text())
    cfg["provider"] = os.environ.get("BUGFIX_PROVIDER") or cfg.get("provider", "codex")  # tests pin it: never a real worker
    return cfg


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def git(*args: str, cwd: Path | None = None, check: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(cwd or TARGET), *args], capture_output=True, text=True, check=check)


# ---------------- state ----------------
@contextmanager
def state():
    """The one state file, locked while it is read and written (workers' collects run at the same time)."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    path, lock = STATE_DIR / "jobs.json", STATE_DIR / ".lock"
    with open(lock, "w") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        st = json.loads(path.read_text()) if path.exists() else {"jobs": {}, "released": []}
        yield st
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(st, indent=1, ensure_ascii=False))
        os.replace(tmp, path)


def peek() -> dict:
    with state() as st:
        return json.loads(json.dumps(st))


def history(job: dict, note: str) -> None:
    job.setdefault("history", []).append({"t": now(), "stage": job["stage"], "note": note})


# ---------------- findings ----------------
def statuses() -> dict[str, str]:
    """Each finding's status exactly as the bug watch's own board has it (bugwatch/bugs.py): Claude's verdicts in
    FIXES.md and Codex's VERIFIED / REOPEN in BUGS.md, taken in time order. Reading the two files one after the other
    instead put an old REOPEN after the fix that answered it, so findings fixed and verified long ago (B-001, B-012,
    B-014) came back as open and were sent to fixers again."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("bugwatch_board", REPO / "bugwatch/bugs.py")
    board = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(board)
    board.BUGS, board.FIXES = BUGS, FIXES
    found, events, _, _ = board.load()
    return {b: board.status_of(b, events) for b in found}


def findings() -> dict[str, dict]:
    """Every finding: id, priority, area, title, its block, the REPLY lines that correct or extend it, its status."""
    out: dict[str, dict] = {}
    cur, fenced = None, False
    for line in BUGS.read_text(encoding="utf-8").splitlines() if BUGS.exists() else []:
        if line.strip().startswith("```"):
            fenced, cur = not fenced, None
            continue
        if fenced:
            continue
        if m := HEAD.match(line):
            cur = out[m[1]] = {"id": m[1], "pri": m[2], "area": m[3].strip(), "title": m[4].strip(), "block": [line],
                               "replies": []}
        elif re.match(r"- \d\d:\d\d ", line):
            cur = None
            if (m := re.match(r"- \d\d:\d\d REPLY (B-\d+)\b", line)) and m[1] in out:
                out[m[1]]["replies"].append(line)
        elif line.startswith("#"):
            cur = None
        elif cur is not None:
            cur["block"].append(line)
    seen = statuses()
    for b in out.values():
        b["block"] = "\n".join(b["block"]).strip()
        b["status"] = seen.get(b["id"], "OPEN")
    return out


def group_key(b: dict) -> str:
    """Findings in the same file go in the same job (or never run side by side): the file the finding names."""
    area = b["area"].lower()
    if area.endswith(".json") or "build/out/packs" in area:
        return "pack content"
    if "how it works" in area:
        return "guide"
    return Path(area.split()[0]).name if area.split() else area


def suggest(b: dict) -> tuple[str, str]:
    """The fixer's and the reviewer's tiers for a finding, from config.json's table (the manager may change them)."""
    table, area = config()["suggest"], b["area"].lower()
    ui = "[visual]" in b["title"] or any(k in area for k in ("screens", "panels", "cards", "app.py", "_screen"))
    key = b["pri"] if b["pri"] in ("P0", "P1") else ("ui" if ui else b["pri"])
    return table[key]["fix"], table[key]["review"]


def open_findings() -> list[dict]:
    taken = {x for j in peek()["jobs"].values() if j["stage"] not in ("dropped",) for x in j["bugs"]}
    return [b for b in findings().values() if b["status"] not in DONE and b["id"] not in taken]


# ---------------- planning ----------------
def cmd_triage() -> None:
    rows = sorted(open_findings(), key=lambda b: (b["pri"], group_key(b), b["id"]))
    for b in rows:
        fix, review = suggest(b)
        print(f"{b['id']} {b['pri']} {group_key(b)[:16]:<16} {fix:<18} {b['title'][:64]}")
    print(f"{len(rows)} open; `plan --suggested` groups them by file, up to {config()['group_size']} a job")


def new_job(st: dict, bugs: list[str], model: str, review: str, note: str = "") -> str:
    n = 1 + max((int(k[1:]) for k in st["jobs"]), default=0)
    jid = f"J{n:02d}"
    every = findings()
    pri = min(every[b]["pri"] for b in bugs)
    st["jobs"][jid] = {"id": jid, "bugs": bugs, "pri": pri, "files": sorted({group_key(every[b]) for b in bugs}),
                       "model": model, "review": review, "note": note, "stage": "queued", "round": 0, "feedback": [],
                       "created": now()}
    history(st["jobs"][jid], "planned")
    return jid


def cmd_plan(args: list[str]) -> None:
    every = findings()
    if args and args[0] == "--suggested":
        groups: dict[str, list[dict]] = {}
        for b in sorted(open_findings(), key=lambda b: (b["pri"], b["id"])):
            groups.setdefault(group_key(b), []).append(b)
        size = config()["group_size"]
        with state() as st:
            for key, rows in groups.items():
                for i in range(0, len(rows), size):
                    part = rows[i:i + size]
                    fix, review = suggest(min(part, key=lambda b: b["pri"]))
                    print(f"{new_job(st, [b['id'] for b in part], fix, review)} {key}: {' '.join(b['id'] for b in part)} {fix}")
        return
    bugs = [b.strip() for b in args[0].split(",")] if args else []
    if not bugs or any(b not in every for b in bugs):
        raise SystemExit(f"unknown finding in {bugs}")
    fix, review = suggest(min((every[b] for b in bugs), key=lambda b: b["pri"]))
    with state() as st:
        print(new_job(st, bugs, _opt(args, "--model") or fix, _opt(args, "--review") or review, _opt(args, "--note") or ""))


def _opt(args: list[str], name: str) -> str | None:
    return args[args.index(name) + 1] if name in args and args.index(name) + 1 < len(args) else None


def cmd_set(jid: str, args: list[str]) -> None:
    with state() as st:
        job = st["jobs"][jid]
        if job["stage"] in LIVE:
            raise SystemExit(f"{jid} is {job['stage']}: change it when it stops")
        for key, opt in (("model", "--model"), ("review", "--review"), ("note", "--note")):
            if (v := _opt(args, opt)) is not None:
                job[key] = v
        history(job, f"set {' '.join(args)}")


# ---------------- workers ----------------
def worktree(job: dict, fresh: bool = False) -> Path:
    """A git worktree for the job on its own branch, from the main checkout's HEAD, with the untracked data linked in."""
    wt, branch = WT / job["id"], f"bugfix/{job['id']}"
    if fresh and wt.exists():
        git("worktree", "remove", "--force", str(wt))
        git("branch", "-D", branch)
    if not wt.exists():
        WT.mkdir(parents=True, exist_ok=True)
        git("branch", "-D", branch)
        git("worktree", "add", "-b", branch, str(wt), "HEAD", check=True)
        for rel in LINKED:
            src, dst = TARGET / rel, wt / rel
            if src.exists() and not dst.exists():
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.symlink_to(src)
        job["base"] = git("rev-parse", "HEAD").stdout.strip()
    job["worktree"], job["branch"] = str(wt), branch
    return wt


def tier(text: str) -> tuple[str, str]:
    model, _, effort = text.partition("/")
    return model, effort or "medium"


def climb(text: str) -> str:
    """One tier up the ladder (a second try at the same tier rarely does better)."""
    ladder = config()["ladder"]
    return ladder[min(ladder.index(text) + 1, len(ladder) - 1)] if text in ladder else text


def bug_text(bugs: list[str]) -> str:
    every = findings()
    parts = []
    for b in bugs:
        f = every[b]
        parts.append(f["block"] + ("\n" + "\n".join(f["replies"]) if f["replies"] else ""))
    return "\n\n".join(parts)


def salvage_for(bugs: list[str]) -> list[str]:
    """Earlier attempts (stopped before they were checked) that worked on these findings: hints, never to be trusted."""
    out = []
    for p in sorted((HERE / "salvage").glob("*.patch")):
        head = p.read_text(encoding="utf-8").split("\n", 1)[0]
        if any(re.search(rf"\b{b}\b", head) for b in bugs):
            out.append(str(p.relative_to(REPO)))  # relative: the worker starts in its worktree, which has bugfix/
    return out


def role_prompt(job: dict, role: str) -> str:
    rules = (HERE / "roles" / f"{role}.md").read_text(encoding="utf-8")
    parts = [rules, f"\n## Your job: {job['id']} ({', '.join(job['bugs'])})\n", bug_text(job["bugs"])]
    if job.get("note"):
        parts.append(f"\n## The manager's instruction\n{job['note']}")
    if role == "fixer":
        if hints := salvage_for(job["bugs"]):
            parts.append("\n## An earlier attempt (unfinished, unchecked: use only what you have verified)\n"
                         + "\n".join(f"- {h}" for h in hints))
        if job["feedback"]:
            parts.append("\n## What to address in this round (your earlier work is already in this worktree)\n"
                         + "\n".join(f"- [{f['from']}] {f['text']}" for f in job["feedback"][-6:]))
        parts.append(f"\nName your new test file tests/test_bf_{job['id'].lower()}.py (engine) and/or "
                     f"tests/app/test_bf_{job['id'].lower()}.py (app).")
    if role == "reviewer":
        diff = git("diff", f"{job['base']}..HEAD", cwd=Path(job["worktree"])).stdout
        cap = 60000
        parts += ["\n## The fixer's report\n" + json.dumps(job.get("report"), ensure_ascii=False, indent=1),
                  "\n## The tests after the fix\n" + json.dumps(job.get("gates"), ensure_ascii=False),
                  f"\n## The diff ({len(diff)} characters" + (", cut: read the files for the rest" if len(diff) > cap else "")
                  + ")\n```diff\n" + diff[:cap] + "\n```"]
    parts.append("\nThe design rules: bugfix/DESIGN.md (read it before you start). You start in the worktree's root: use "
                 "paths relative to it; if you ever need an absolute path in a shell command, quote all of it (it has spaces).")
    return "\n".join(parts)


def launch(jid: str, role: str) -> None:
    with state() as st:
        job = st["jobs"][jid]
        if role == "fixer":
            wt = worktree(job, fresh=job.pop("restart", False))
            text = job["model"]
        else:
            wt, text = Path(job["worktree"]), job["review"]
        provider = config().get("provider", "codex")
        model, effort = tier(config()["claude_tiers"].get(text, text) if provider == "claude" else text)
        LOGS.mkdir(parents=True, exist_ok=True)
        stem = f"{jid}.{role}.r{job['round']}.{datetime.now():%m%d-%H%M%S}"
        log, out = LOGS / f"{stem}.log", LOGS / f"{stem}.json"
        prompt = role_prompt(job, role)
        schema = HERE / "schemas" / f"{role}.json"
        if provider == "claude":  # its report is in its own output (the log): collect reads it from there
            out = log
            worker = [CLAUDE, "-p", prompt, "--model", model, "--effort", effort, *LEAN,
                      "--tools", "Read,Write,Edit,Bash,Glob,Grep" if role == "fixer" else "Read,Bash,Glob,Grep",
                      "--permission-mode", "acceptEdits" if role == "fixer" else "default",
                      "--allowedTools", *(["Bash(.venv/bin/python *)"] if role == "fixer" else []), *READ_BASH,
                      "--json-schema", schema.read_text()]
        else:
            worker = [CODEX, "exec", "-m", model, "-c", f'model_reasoning_effort="{effort}"', "-c", 'approval_policy="never"',
                      "-s", "workspace-write" if role == "fixer" else "read-only", "-C", str(wt), "--color", "never",
                      "--output-schema", str(schema), "-o", str(out), prompt]
        then = [PY, str(HERE / "bugfix.py"), "collect", jid, role, str(out)]
        shell = (f"{shlex.join(worker)} < /dev/null > {shlex.quote(str(log))} 2>&1; "
                 f"{shlex.join(then)} $? >> {shlex.quote(str(log))} 2>&1")
        proc = subprocess.Popen(["/bin/sh", "-c", shell], cwd=wt, start_new_session=True, stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1",
                                                                "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1"})
        job.update(stage="fixing" if role == "fixer" else "reviewing", pid=proc.pid, log=str(log), started=now(),
                   provider=provider)
        history(job, f"{role} started on {model}/{effort}")
    print(f"{jid}: {role} on {model}/{effort} · log {log.name}")


def alive(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    try:  # a finished child that nobody waited for is a zombie: not alive
        return os.waitpid(pid, os.WNOHANG) == (0, 0)
    except ChildProcessError:
        return True


# ---------------- collect: commit, gates, verdicts ----------------
def changed(wt: Path) -> list[tuple[str, str]]:
    """(status, path) of every change, paths read NUL-separated: the repository's own paths have spaces."""
    rows, out = git("status", "--porcelain", "-z", "--untracked-files=all", cwd=wt).stdout.split("\0"), []
    skip = False
    for r in rows:
        if skip or not r.strip():
            skip = False
            continue
        out.append((r[:2], r[3:]))
        skip = r[0] in "RC"  # a rename names the old path next
    return out


def forbidden(path: str) -> bool:
    return any(path == f or (f.endswith("/") and path.startswith(f)) for f in FORBIDDEN)


def commit(job: dict, report: dict | None) -> tuple[list[str], list[str]]:
    """Commit what the fixer changed. Returns (files committed, forbidden files it touched: put back, not committed).
    Scratch files outside the code folders are removed; links to the untracked data are left alone."""
    wt = Path(job["worktree"])
    bad, keep = [], []
    for code, path in changed(wt):
        if (wt / path).is_symlink():
            continue
        if forbidden(path):
            bad.append(path)
            if code.strip() == "??":
                (wt / path).unlink(missing_ok=True)
            else:
                git("checkout", "HEAD", "--", path, cwd=wt)
        elif code.strip() == "??" and not path.startswith(ALLOWED):
            (wt / path).unlink(missing_ok=True)
        else:
            keep.append(path)
    if keep:
        git("add", "-A", "--", *keep, cwd=wt)
        lines = [f"{v['id']} {v['verdict']}: {v.get('fix') or v.get('reason', '')}"[:200]
                 for v in (report or {}).get("verdicts", [])]
        msg = (f"bugfix {job['id']}: {', '.join(job['bugs'])} (round {job['round']})\n\n" + "\n".join(lines)
               + f"\n\nFixed-by: Codex {job['model']} (bin/bugfix)")
        git("-c", "user.name=bugfix", "-c", "user.email=bugfix@localhost", "commit", "-q", "-m", msg, cwd=wt)
    return keep, bad


def commit_main(message: str, *paths: str) -> None:
    """Commit only these paths in the main checkout (the learner may have other changes staged there)."""
    git("add", "--", *paths)
    git("-c", "user.name=bugfix", "-c", "user.email=bugfix@localhost", "commit", "-q", "-m", message, "--", *paths)


def run_tests(wt: Path, paths: list[str]) -> dict:
    """The engine suite, and the app suite when the app (or the engine it runs on) changed. BUGFIX_TEST_CMD replaces
    both in tests of this file."""
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    import importlib.util  # pytest-xdist spreads the suites over the cores (the app suite: 4m35s to 1m35s, same results)
    fast = ["-n", str(config()["test_workers"])] if importlib.util.find_spec("xdist") and config().get("test_workers") else []
    runs = []
    if os.environ.get("BUGFIX_TEST_CMD"):
        runs.append(("tests", ["/bin/sh", "-c", os.environ["BUGFIX_TEST_CMD"]], 600))
    else:
        runs.append(("engine", [PY, *ENGINE_TESTS, *fast], 900))
        if any(p.startswith(("app/", "tests/app/", "plugin/")) for p in paths):
            runs.append(("app", [PY, *APP_TESTS, *fast], 1800))
    out: dict = {"ok": True}
    for name, cmd, limit in runs:
        try:
            done = subprocess.run(cmd, cwd=wt, capture_output=True, text=True, timeout=limit, env=env)
            text, code = done.stdout + done.stderr, done.returncode
        except subprocess.TimeoutExpired:
            text, code = f"timed out after {limit} s", 1
        summary = next((l for l in reversed(text.splitlines()) if re.search(r"\d+ (passed|failed|error)", l)), text[-200:])
        out[name] = summary.strip("= ").strip()
        failed = [l.split()[1] for l in text.splitlines() if l.startswith("FAILED ") and len(l.split()) > 1]
        if code and failed and len(failed) <= 5 and fast:
            # Several jobs test at once on shared cores; a timing-sensitive test can fail under that load alone. The
            # failed tests run again, one process, nothing else changed: only what fails then is a real failure.
            again = subprocess.run([PY, "-m", "pytest", "-q", "-p", "no:cacheprovider", *failed], cwd=wt,
                                   capture_output=True, text=True, timeout=600, env=env)
            if again.returncode == 0:
                out[name] += f" (flaky under load, passed alone: {', '.join(f.split('::')[-1] for f in failed)})"
                code = 0
        if code:
            out["ok"] = False
            out.setdefault("failures", []).extend([l[:220] for l in text.splitlines() if l.startswith(("FAILED", "ERROR"))][:10])
    return out


def cmd_collect(jid: str, role: str, out_file: str, code: str) -> None:
    if out_file.endswith(".log"):  # a Claude worker: its report and the allowance it was told about are in its output
        sys.path.insert(0, str(REPO / "foundry"))
        import router
        facts = router.claude_log(Path(out_file))
        report = facts["report"] if facts["report"] and "text" not in facts["report"] else None
        note_claude(facts.get("windows") or {})
    else:
        try:
            report = json.loads(Path(out_file).read_text())
        except (OSError, ValueError):
            report = None
    if role == "scribe":
        with state() as st:
            st["release_report"], st["release_stage"] = report, "written" if report else "failed"
        notify("bugfix: release notes written" if report else "bugfix: the scribe failed")
        return
    if role == "fixer":
        with state() as st:  # the worker's shell (job["pid"]) stays alive while the tests run, so a crash here is seen
            job = st["jobs"][jid]
            job["report"], job["stage"] = report, "gating"
            history(job, f"fixer ended (exit {code}); gating")
        gate_and_route(jid, report, int(code))
    else:
        route_review(jid, report, int(code))
    notify(f"bugfix {jid}: {role} finished · {peek()['jobs'][jid]['stage']}")


def busy_model(job: dict) -> bool:
    """The worker never started work: the model was at capacity (OpenAI's side). Not the job's fault: no round lost."""
    try:
        return "at capacity" in Path(job.get("log") or "").read_text(errors="ignore")[-4000:]
    except OSError:
        return False


def gate_and_route(jid: str, report: dict | None, code: int) -> None:
    job = peek()["jobs"][jid]
    if report is None and busy_model(job):
        with state() as st:
            j = st["jobs"][jid]
            j["stage"], j["pid"] = "fix", None
            j["model"] = config().get("at_capacity", {}).get(j["model"], j["model"])  # its stand-in, if one is named
            history(j, f"the model was at capacity: the same round starts again on {j['model']}")
        return
    keep, bad = commit(job, report)
    wt = Path(job["worktree"])
    every = git("diff", "--name-only", f"{job['base']}..HEAD", cwd=wt).stdout.split()
    g = run_tests(wt, every) if every else {"ok": True, "note": "no change"}
    fixed = [v for v in (report or {}).get("verdicts", []) if v.get("verdict") == "FIXED"]
    if bad:
        g["ok"], g["forbidden"] = False, bad
    if fixed and not any(p.startswith("tests/") for p in every):
        g["ok"], g["no_test"] = False, True
    if report is None or code:
        g["ok"], g["worker"] = False, f"the fixer ended without a report (exit {code})"
    g["files"] = every
    with state() as st:
        job = st["jobs"][jid]
        job["gates"] = g
        job["files"] = sorted(set(job["files"]) | set(every))
        if g["ok"]:
            job["stage"] = "review"
            history(job, "tests green")
        else:
            why = ("; ".join(filter(None, [g.get("worker"), f"touched files no fixer may change: {bad}" if bad else "",
                                           "no regression test for a FIXED finding" if g.get("no_test") else "",
                                           "tests red: " + " | ".join(g.get("failures", [])[:4]) if g.get("failures") else ""])))
            back(job, "gates", why)


def back(job: dict, source: str, text: str) -> None:
    """Back to the fixer with what to address, one tier up; after `rounds` tries the manager decides."""
    job["feedback"].append({"from": source, "text": text[:1500]})
    job["round"] += 1
    if job["round"] > config()["rounds"]:
        job["stage"] = "stuck"
        history(job, f"stuck after {job['round']} rounds: {text[:200]}")
    else:
        job["model"] = climb(job["model"])
        job["stage"] = "fix"
        history(job, f"back to the fixer ({source}) on {job['model']}: {text[:200]}")


def route_review(jid: str, report: dict | None, code: int) -> None:
    with state() as st:
        job = st["jobs"][jid]
        job["review_report"] = report
        if not report or code:
            job["stage"] = "review"  # the reviewer failed: run it again
            if busy_model(job):
                job["review"] = config().get("at_capacity", {}).get(job["review"], job["review"])
            job["review_fail"] = job.get("review_fail", 0) + (0 if busy_model(job) else 1)
            if job["review_fail"] >= 2:
                job["stage"] = "stuck"
            history(job, f"reviewer ended without a report (exit {code})")
            return
        serious = [f for f in report.get("findings", []) if f.get("severity") in ("blocker", "major")]
        if report.get("approve") and not serious:
            job["stage"] = "ready"
            history(job, "review approved")
        else:
            back(job, "review", " | ".join(f"{f['severity']} {f['file']}: {f['problem']} → {f['fix']}" for f in serious)
                 or report.get("summary", "not approved"))


# ---------------- the loop ----------------
def used_now() -> float | None:
    """How much of the provider's allowance is used: Codex's week, or the fuller of Claude's two windows (5 hours and
    the week). Read at most every two minutes."""
    provider = config().get("provider", "codex")
    cache = STATE_DIR / "usage.json"
    try:
        c = json.loads(cache.read_text())
        if time.time() - c["at"] < 120 and c.get("provider") == provider:
            return c["used"]
    except (OSError, ValueError, KeyError):
        pass
    if os.environ.get("BUGFIX_CODEX") or os.environ.get("BUGFIX_CLAUDE"):  # tests and fakes: nothing to ask
        return None
    sys.path.insert(0, str(REPO / "foundry"))
    import router
    if provider == "claude":
        import foundry as fd  # the foundry keeps the readings of both allowances (foundry/usage.json)
        with fd.notes() as n:
            w = router.usage(n, fd.CODEX, fd.CLAUDE).get("claude") or {}
        keys = ("five_hour", "seven_day", "limit")
    else:
        w, keys = router.codex_usage(CODEX) or {}, ("seven_day", "limit")
    used = max([w[k]["used"] for k in keys if k in w] or [-1.0])
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps({"at": time.time(), "used": used, "provider": provider, "windows": w}))
    return used if used >= 0 else None


def note_claude(windows: dict) -> None:
    """A Claude worker is told exactly how much of both windows is used: keep it for the next reading."""
    if not windows or os.environ.get("BUGFIX_CLAUDE"):
        return
    sys.path.insert(0, str(REPO / "foundry"))
    import foundry as fd
    import router
    with fd.notes() as n:
        k = n.setdefault("claude", {})
        for name, w in windows.items():
            router._reading(k, name, w["used"], w.get("resets"), time.time(), w.get("exact", False))
    (STATE_DIR / "usage.json").unlink(missing_ok=True)


def stop_at() -> float:
    cfg = config()
    return cfg["stop"][cfg.get("provider", "codex")]


def reap(st: dict) -> None:
    """A worker that died without its collect (killed, machine slept): back to where it can start again."""
    for job in st["jobs"].values():
        if job["stage"] in ("fixing", "gating", "reviewing") and not alive(job.get("pid")):
            started = datetime.fromisoformat(job.get("started", now()))
            if (datetime.now() - started).total_seconds() > 30:
                job["stage"] = "review" if job["stage"] == "reviewing" else "fix"
                job["pid"] = None
                history(job, "the worker stopped without reporting: it will start again")


def cmd_step() -> None:
    cfg = config()
    with state() as st:
        reap(st)
    used = used_now()
    if used is not None and used >= stop_at():
        print(f"{cfg.get('provider', 'codex').title()} {used:.0f}% used (stop at {stop_at():.0f}%): no new workers")
        cmd_board()
        return
    jobs = peek()["jobs"]
    running = [j for j in jobs.values() if j["stage"] in LIVE]
    slots = cfg["max_parallel"] - len(running)
    busy = {f for j in running if j["stage"] in ("fixing", "gating") for f in j["files"]}
    order = sorted(jobs.values(), key=lambda j: (j["stage"] != "review", j["pri"], j["id"]))
    for job in order:
        if slots <= 0:
            break
        if job["stage"] == "review":
            launch(job["id"], "reviewer")
            slots -= 1
        elif job["stage"] in ("queued", "fix") and not busy & set(job["files"]):
            launch(job["id"], "fixer")
            busy |= set(job["files"])
            slots -= 1
    cmd_board()


def cmd_wait(timeout: float = 540, every: float = 5) -> None:
    """Return as soon as a running worker finishes (its job changes stage), or after `timeout` seconds."""
    def live() -> set[str]:
        st = peek()
        return {j["id"] for j in st["jobs"].values() if j["stage"] in LIVE} | (
            {"release"} if st.get("release_stage") == "scribing" else set())
    start, watching = time.time(), live()
    while watching and time.time() - start < timeout:
        time.sleep(every)
        if watching - live():  # one of them has finished (gating counts as still working)
            break
    cmd_board()


def _age(ts: str | None) -> str:
    if not ts:
        return ""
    s = (datetime.now() - datetime.fromisoformat(ts)).total_seconds()
    return f"{s / 60:.0f}m" if s < 5400 else f"{s / 3600:.1f}h"


def cmd_board() -> None:
    jobs = peek()["jobs"]
    open_ = len(open_findings())
    for j in sorted(jobs.values(), key=lambda j: (j["stage"] in ("merged", "dropped"), j["pri"], j["id"])):
        if j["stage"] in ("merged", "dropped"):
            continue
        g = j.get("gates") or {}
        tests = "" if not g else ("green" if g.get("ok") else "red")
        print(f"{j['id']} {j['pri']} {j['stage']:<9} r{j['round']} {j['model']:<18} {','.join(j['bugs']):<24} "
              f"{tests:<5} {_age(j.get('started')) if j['stage'] in LIVE else ''}")
    done = sum(1 for j in jobs.values() if j["stage"] == "merged")
    release = peek().get("release_stage")
    print(f"merged {done} · open findings not in a job {open_}" + (f" · release: {release}" if release else ""))


# ---------------- the manager's decisions ----------------
def cmd_packet(jid: str) -> None:
    j = peek()["jobs"][jid]
    print(f"{jid} · {j['stage']} · round {j['round']} · fixer {j['model']} · reviewer {j['review']}")
    every = findings()
    for b in j["bugs"]:
        print(f"  {b} {every[b]['pri']} {every[b]['title'][:90]}")
    for v in (j.get("report") or {}).get("verdicts", []):
        print(f"{v['id']} {v['verdict']} · {v.get('cause', '')[:160]} → {v.get('fix') or v.get('reason', '')}"[:400]
              + (f" · test {v['test']}" if v.get("test") else ""))
    for q in (j.get("report") or {}).get("decisions", []):
        print(f"decided: {q[:300]}")
    if j.get("worktree") and j.get("base"):
        stat = git("diff", "--shortstat", f"{j['base']}..HEAD", cwd=Path(j["worktree"])).stdout.strip()
        print(f"diff: {stat} · {' '.join((j.get('gates') or {}).get('files', [])[:8])}")
    g = j.get("gates") or {}
    if g:
        print("tests: " + " · ".join(f"{k} {g[k]}" for k in ("engine", "app", "tests") if k in g)
              + ("" if g.get("ok") else f" · RED {g.get('failures', [])[:3]}"))
    r = j.get("review_report") or {}
    if r:
        print(f"review: {'APPROVE' if r.get('approve') else 'CHANGES'} · {r.get('summary', '')[:300]}")
        for f in r.get("findings", [])[:5]:
            print(f"  {f['severity']} {f['file']}: {f['problem'][:160]} → {f['fix'][:120]}")
    for f in j["feedback"][-3:]:
        print(f"earlier [{f['from']}]: {f['text'][:200]}")


def cmd_diff(jid: str, path: str | None = None) -> None:
    j = peek()["jobs"][jid]
    print(git("diff", f"{j['base']}..HEAD", *(["--", path] if path else []), cwd=Path(j["worktree"])).stdout)


def fixes_lines(job: dict, sha: str) -> list[str]:
    at = datetime.now().strftime("%H:%M")
    out = []
    for v in (job.get("report") or {}).get("verdicts", []):
        if v["verdict"] == "FIXED":
            out.append(f"- {at} {v['id']} FIXED · {v.get('cause', '')} → {v.get('fix', '')} · {sha[:7]}"
                       + (f" · test {v['test']}" if v.get("test") else "") + f" · bugfix {job['id']} ({job['model']})")
        elif v["verdict"] in ("REJECTED", "DEFERRED", "DUPLICATE"):
            out.append(f"- {at} {v['id']} {v['verdict']} · {v.get('reason', '')} · bugfix {job['id']}")
    return out


def cmd_accept(jid: str) -> None:
    job = peek()["jobs"][jid]
    if job["stage"] != "ready" and "--force" not in sys.argv:
        raise SystemExit(f"{jid} is {job['stage']}, not ready (accept --force to merge anyway)")
    files = set(git("diff", "--name-only", f"{job['base']}..{job['branch']}").stdout.split())
    dirty = {r[3:].strip('"') for r in git("status", "--porcelain").stdout.splitlines()} & files
    if dirty:
        raise SystemExit(f"the main checkout has uncommitted changes in {sorted(dirty)}: commit or put them aside first")
    merged = git("merge", "--no-ff", "--no-edit", "-m", f"bugfix {jid}: {', '.join(job['bugs'])}", job["branch"])
    if merged.returncode:
        git("merge", "--abort")
        rebased = git("rebase", git("rev-parse", "HEAD").stdout.strip(), cwd=Path(job["worktree"]))
        with state() as st:
            j = st["jobs"][jid]
            if rebased.returncode:
                git("rebase", "--abort", cwd=Path(job["worktree"]))
                (LOGS / f"{jid}.before-conflict.patch").write_text(cmd_text_diff(job))
                j["restart"] = True
                back(j, "merge", f"it conflicts with fixes merged since; redo it on the new base. Your previous diff: "
                                 f"{LOGS / f'{jid}.before-conflict.patch'}")
            else:
                j["base"] = git("rev-parse", "HEAD").stdout.strip()
                j["stage"] = "review"
                history(j, "rebased onto the fixes merged since; reviewed again")
        print(f"{jid}: did not merge cleanly; {peek()['jobs'][jid]['stage']}")
        return
    sha = git("rev-parse", "HEAD").stdout.strip()
    check = run_tests(TARGET, [] if os.environ.get("BUGFIX_TEST_CMD") else ["tutorlib"])  # the engine suite on the result
    if not check["ok"]:
        git("revert", "-m", "1", "--no-edit", "HEAD")
        with state() as st:
            back(st["jobs"][jid], "merge", "after merging, tests failed: " + " | ".join(check.get("failures", [])[:4]))
        print(f"{jid}: merged but tests went red, so the merge was reverted; back to the fixer")
        return
    lines = fixes_lines(job, sha)
    with open(FIXES, "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    commit_main(f"bugwatch: verdicts for {', '.join(job['bugs'])} (bugfix {jid})", "bugwatch/FIXES.md")
    git("worktree", "remove", "--force", job["worktree"])
    git("branch", "-D", job["branch"])
    with state() as st:
        st["jobs"][jid].update(stage="merged", merged=sha, worktree=None)
        history(st["jobs"][jid], f"merged {sha[:7]}")
    print(f"{jid}: merged {sha[:7]}; {len(lines)} verdicts in FIXES.md")


def cmd_text_diff(job: dict) -> str:
    return git("diff", f"{job['base']}..HEAD", cwd=Path(job["worktree"])).stdout


def cmd_reject(jid: str, args: list[str]) -> None:
    model = _opt(args, "--model")
    text = " ".join(a for i, a in enumerate(args) if not a.startswith("--") and not (i and args[i - 1] == "--model"))
    with state() as st:
        job = st["jobs"][jid]
        if job["stage"] in LIVE:
            raise SystemExit(f"{jid} is {job['stage']}: wait for it")
        job["feedback"].append({"from": "manager", "text": text})
        job["model"] = model or job["model"]
        job["restart"] = "--restart" in args
        job["stage"] = "fix"
        history(job, f"manager: {text[:200]}")
    print(f"{jid}: back to the fixer")


def cmd_drop(jid: str) -> None:
    with state() as st:
        job = st["jobs"][jid]
        if job["stage"] in LIVE:
            raise SystemExit(f"{jid} is {job['stage']}: wait for it")
        if job.get("worktree"):
            git("worktree", "remove", "--force", job["worktree"])
            git("branch", "-D", job["branch"])
        job.update(stage="dropped", worktree=None)
        history(job, "dropped by the manager")


def cmd_close(bug: str, verdict: str, text: str) -> None:
    if verdict not in ("REJECTED", "DEFERRED", "DUPLICATE"):
        raise SystemExit("close takes REJECTED, DEFERRED or DUPLICATE")
    with open(FIXES, "a", encoding="utf-8") as f:
        f.write(f"- {datetime.now():%H:%M} {bug} {verdict} · {text}\n")
    commit_main(f"bugwatch: {bug} {verdict}", "bugwatch/FIXES.md")
    print(f"{bug}: {verdict}")


# ---------------- release ----------------
def next_version() -> str:
    cur = re.search(r'__version__ = "([\d.]+)"', (TARGET / "app/tutor_app/__init__.py").read_text())[1]
    major, minor, patch = (int(x) for x in cur.split("."))
    return f"{major}.{minor}.{patch + 1}"


def cmd_release(args: list[str]) -> None:
    st = peek()
    merged = [j for j in st["jobs"].values() if j["stage"] == "merged" and j["id"] not in st["released"]]
    if "--sign" in args:
        g = run_tests(TARGET, ["app/"]) if not os.environ.get("BUGFIX_TEST_CMD") else run_tests(TARGET, [])
        notes = subprocess.run([PY, "-m", "pytest", "tests/test_release_notes.py", "-q", "-p", "no:cacheprovider"],
                               cwd=TARGET, capture_output=True, text=True)
        if not g["ok"] or notes.returncode:
            raise SystemExit(f"not signed: {g} {notes.stdout[-300:]}")
        version = re.search(r'__version__ = "([\d.]+)"', (TARGET / "app/tutor_app/__init__.py").read_text())[1]
        if os.environ.get("BUGFIX_PUBLISH", "1") == "1":
            subprocess.run([PY, str(TARGET / "build/publish.py")], cwd=TARGET, check=True)
        commit_main(f"{version}: bug-watch fixes ({len(merged)} jobs)\n\nReleased-by: bin/bugfix", *RELEASE_FILES)
        git("tag", f"v{version}")
        with state() as s:
            s["released"] += [j["id"] for j in merged]
            s["release_stage"] = "signed"
        print(f"v{version} signed. Push: git -C \"{TARGET}\" push origin main --tags")
        return
    if not merged:
        raise SystemExit("nothing merged since the last release")
    every = findings()
    lines = []
    for j in merged:
        for v in (j.get("report") or {}).get("verdicts", []):
            if v["verdict"] == "FIXED":
                lines.append(f"- {v['id']} ({every[v['id']]['pri']}, {every[v['id']]['area']}): {every[v['id']]['title']} · "
                             f"cause: {v.get('cause', '')} · fix: {v.get('fix', '')}")
    model, effort = tier(config()["scribe"])
    LOGS.mkdir(parents=True, exist_ok=True)
    stem = f"release.{datetime.now():%m%d-%H%M%S}"
    log, out = LOGS / f"{stem}.log", LOGS / f"{stem}.json"
    prompt = ((HERE / "roles" / "scribe.md").read_text(encoding="utf-8")
              + f"\n\n## The release\nVersion {next_version()} (from {next_version().rsplit('.', 1)[0]}.x), "
              f"dated {datetime.now():%Y-%m-%d}. Fixed findings:\n" + "\n".join(lines))
    worker = [CODEX, "exec", "-m", model, "-c", f'model_reasoning_effort="{effort}"', "-c", 'approval_policy="never"',
              "-s", "workspace-write", "-C", str(TARGET), "--color", "never",
              "--output-schema", str(HERE / "schemas" / "scribe.json"), "-o", str(out), prompt]
    then = [PY, str(HERE / "bugfix.py"), "collect", "release", "scribe", str(out)]
    shell = f"{shlex.join(worker)} < /dev/null > {shlex.quote(str(log))} 2>&1; {shlex.join(then)} $? >> {shlex.quote(str(log))} 2>&1"
    subprocess.Popen(["/bin/sh", "-c", shell], cwd=TARGET, start_new_session=True, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL)
    with state() as s:
        s["release_stage"] = "scribing"
    print(f"scribe on {model}/{effort} for v{next_version()} · log {log.name}; then: bugfix release --sign")


# ---------------- small things ----------------
def notify(text: str) -> None:
    if os.environ.get("BUGFIX_NOTIFY", "1") == "1" and sys.platform == "darwin":
        subprocess.run(["osascript", "-e", f"display notification {json.dumps(text)} with title \"Bug fixes\""],
                       capture_output=True)


def cmd_usage() -> None:
    provider, used = config().get("provider", "codex"), used_now()
    print(f"{provider.title()} {used:.0f}% used; new workers stop at {stop_at():.0f}%" if used is not None
          else f"{provider.title()} allowance not known")


def cmd_watch(every: float = 10) -> None:
    try:
        while True:
            print("\033[2J\033[H" + time.strftime("bug fixes · %H:%M:%S\n"), flush=True)
            cmd_board()
            time.sleep(every)
    except KeyboardInterrupt:
        pass


def cmd_install_skill() -> None:
    dest = Path.home() / ".claude/skills/bugfix/SKILL.md"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text((HERE / "skill/SKILL.md").read_text().replace("{REPO}", str(REPO)))
    print(f"installed {dest}")


def main(argv: list[str]) -> None:
    cmd, rest = (argv[0], argv[1:]) if argv else ("board", [])
    if cmd == "triage":
        cmd_triage()
    elif cmd == "plan":
        cmd_plan(rest)
    elif cmd == "set":
        cmd_set(rest[0], rest[1:])
    elif cmd == "step":
        cmd_step()
    elif cmd == "wait":
        cmd_wait(float(rest[0]) if rest else 540)
    elif cmd == "board":
        cmd_board()
    elif cmd == "packet":
        cmd_packet(rest[0])
    elif cmd == "diff":
        cmd_diff(rest[0], rest[1] if len(rest) > 1 else None)
    elif cmd == "accept":
        cmd_accept(rest[0])
    elif cmd == "reject":
        cmd_reject(rest[0], rest[1:])
    elif cmd == "drop":
        cmd_drop(rest[0])
    elif cmd == "close":
        cmd_close(rest[0], rest[1], " ".join(rest[2:]))
    elif cmd == "release":
        cmd_release(rest)
    elif cmd == "usage":
        cmd_usage()
    elif cmd == "watch":
        cmd_watch(float(rest[0]) if rest else 10)
    elif cmd == "install-skill":
        cmd_install_skill()
    elif cmd == "collect":
        cmd_collect(*rest[:4])
    else:
        print(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
