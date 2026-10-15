#!/usr/bin/env python3
"""Write the lessons of the Shortcuts course with Codex, in batches, best-ranked entries first.

  shortcuts_gen.py run [--spec S] [--min-score N] [--batch 8] [--max-batches K] [--model gpt-6-sol] [--effort low]
                       [--stop-codex-week 70] [--web] [--dry-run]
  shortcuts_gen.py status [--spec S]        per spec: entries and lessons, by score band
  shortcuts_gen.py verify [--spec S] --sample N   solve a sample of practice items blind with Claude haiku; a lesson whose
                                            stored answer disagrees gets "unverified": true (never deleted)

Entries come from build/out/shortcuts/<spec>.json (`build/shortcuts.py parse`); lessons go to
build/out/shortcuts/lessons/<spec>.json as {entry id: lesson}, merged atomically so nothing already there is lost. A batch
that fails the checks is retried once, for the entries that failed, one effort level higher. The run stops before a batch when
the Codex week is used up to --stop-codex-week percent.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import random
import re
import shutil
import subprocess
import sys
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ROOT = Path(os.environ.get("FOUNDRY_ROOT", REPO))  # the data tree (tests point this at a scratch copy)
HERE = REPO / "foundry"
OUT = ROOT / "build/out/shortcuts"
LESSONS = OUT / "lessons"
LOGS = ROOT / "foundry/logs"
CODEX = os.environ.get("FOUNDRY_CODEX") or shutil.which("codex") or \
    "/Applications/ChatGPT.app/Contents/Resources/codex-cli/bin/codex"
CLAUDE = os.environ.get("FOUNDRY_CLAUDE") or shutil.which("claude") or "claude"
EFFORTS = ("low", "medium", "high")
TIMEOUT = 1800
BANDS = ((10, "10"), (9, "9"), (8, "8"), (0, "<=7"))

sys.path.insert(0, str(REPO / "build"))
sys.path.insert(0, str(REPO / "plugin/stem-tutor/skills/tutor/scripts"))
sys.path.insert(0, str(HERE))
import content_checks  # noqa: E402
import router  # noqa: E402
import shortcuts  # noqa: E402  (build/shortcuts.py: the entry parser and select)
from tutorlib.speech import speech_gaps  # noqa: E402

TEXT = ("hook", "when", "idea", "why", "check")
WORKED = ("question", "long", "short", "saving")
ITEM_TEXT = ("stem", "answer", "explanation", "shortcut_use")


# ---------------- files ----------------
def entries_of(spec: str) -> list[dict]:
    path = OUT / f"{spec}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return shortcuts.load(spec, sources=ROOT / "sources/shortcuts")


def specs_of(only: str | None = None) -> list[str]:
    if only:
        return [only]
    found = {p.stem for p in OUT.glob("*.json")} if OUT.is_dir() else set()
    return sorted(found or {e["spec"] for e in shortcuts.load(sources=ROOT / "sources/shortcuts")})


def lessons_of(spec: str) -> dict:
    try:
        return json.loads((LESSONS / f"{spec}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


@contextmanager
def locked(spec: str):
    LESSONS.mkdir(parents=True, exist_ok=True)
    with open(LESSONS / f".{spec}.lock", "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield


def save_lessons(spec: str, change) -> dict:
    """Apply `change(lessons)` to the spec's file while holding its lock, and write the result in one atomic rename."""
    with locked(spec):
        data = lessons_of(spec)
        change(data)
        path = LESSONS / f"{spec}.json"
        tmp = path.with_suffix(f".{os.getpid()}.tmp")
        tmp.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        os.replace(tmp, path)
    return data


def merge(spec: str, new: dict) -> None:
    save_lessons(spec, lambda data: data.update(new))


# ---------------- checks ----------------
def _strings(x):
    if isinstance(x, str):
        yield x
    elif isinstance(x, dict):
        for v in x.values():
            yield from _strings(v)
    elif isinstance(x, list):
        for v in x:
            yield from _strings(v)


def number_of(text: str) -> float | None:
    """The value of a bare numeric answer ('12.5', '$4.2\\times10^{3}$', '-3'); None when it is anything else."""
    t = re.sub(r"[$\s]", "", str(text)).replace(",", "").replace("−", "-").replace("\\times", "×")
    m = re.fullmatch(r"([-+]?\d+(?:\.\d+)?)(?:[×x*]10\^\{?([-+]?\d+)\}?|[eE]([-+]?\d+))?", t)
    if not m:
        return None
    exp = m[2] or m[3]
    return float(m[1]) * (10 ** int(exp) if exp else 1)


def gives_away(hint: str, answer: str) -> bool:
    """Whether the hint holds the answer as a whole token (7 is not in 17, nor in 7.5)."""
    clean = lambda t: re.sub(r"\s+", " ", re.sub(r"[${}]", "", t)).strip().lower()
    want = clean(answer)
    return bool(want) and re.search(r"(?<![\w.])" + re.escape(want) + r"(?![\w]|\.\d)", clean(hint)) is not None


def lesson_problems(lesson: dict) -> list[str]:
    bad: list[str] = []

    def need(cond, why):
        if not cond:
            bad.append(why)

    def text(v, name):
        ok = isinstance(v, str) and v.strip()
        need(ok, f"{name} is empty or not text")
        return ok

    for k in TEXT:
        text(lesson.get(k), k)
    steps, pits = lesson.get("steps"), lesson.get("pitfalls")
    need(isinstance(steps, list) and 2 <= len(steps) <= 5 and all(isinstance(s, str) and s.strip() for s in steps),
         "steps must be 2 to 5 non-empty strings")
    need(isinstance(pits, list) and 1 <= len(pits) <= 3 and all(isinstance(s, str) and s.strip() for s in pits),
         "pitfalls must be 1 to 3 non-empty strings")
    worked = lesson.get("worked")
    need(isinstance(worked, dict) and all(isinstance(worked.get(k), str) and worked[k].strip() for k in WORKED),
         "worked needs question, long, short and saving")
    recall = lesson.get("recall")
    need(isinstance(recall, list) and 2 <= len(recall) <= 3 and all(
        isinstance(r, dict) and all(isinstance(r.get(k), str) and r[k].strip() for k in ("q", "a")) for r in recall),
        "recall must be 2 or 3 cards with q and a")
    practice = lesson.get("practice")
    if not (isinstance(practice, list) and len(practice) == 2):
        bad.append("practice must hold exactly 2 items")
        practice = []
    for i, p in enumerate(practice, 1):
        if not isinstance(p, dict):
            bad.append(f"practice {i} is not an object")
            continue
        for k in ITEM_TEXT:
            text(p.get(k), f"practice {i} {k}")
        kind, ans, hints = p.get("kind"), str(p.get("answer", "")).strip(), p.get("hints")
        need(kind in ("numeric", "mcq", "short"), f"practice {i}: kind must be numeric, mcq or short")
        need(isinstance(hints, list) and len(hints) == 3 and all(isinstance(h, str) and h.strip() for h in hints),
             f"practice {i}: needs exactly 3 hints")
        opts = p.get("options") if isinstance(p.get("options"), dict) else {}
        if kind == "mcq":
            need(all(isinstance(opts.get(c), str) and opts[c].strip() for c in "ABCD"),
                 f"practice {i}: an mcq needs options A to D, none empty")
            need(ans in "ABCD" and len(ans) == 1, f"practice {i}: the mcq answer must be one of A, B, C, D")
            need(len({str(opts.get(c)).strip().lower() for c in "ABCD"}) == 4, f"practice {i}: options must differ")
            for s in [*(hints if isinstance(hints, list) else []), p.get("explanation")]:
                if isinstance(s, str) and content_checks.letter_refs(s):
                    bad.append(f"practice {i}: names an option by its letter: {s[:60]}")
            if ans in opts and isinstance(hints, list):
                for h in hints:
                    if isinstance(h, str) and gives_away(h, str(opts[ans])) and len(str(opts[ans])) > 2:
                        bad.append(f"practice {i}: a hint gives the answer away")
        else:
            if any(str(v).strip() for v in opts.values()):
                bad.append(f"practice {i}: options belong to mcq only")
            if kind == "numeric":
                need(number_of(ans) is not None, f"practice {i}: the numeric answer {ans!r} is not a bare number")
            if isinstance(hints, list):
                for h in hints:
                    if isinstance(h, str) and gives_away(h, ans):
                        bad.append(f"practice {i}: a hint gives the answer away")
    bad += content_checks.debris_problems(lesson)
    bad += content_checks.latex_problems(lesson)
    for s in dict.fromkeys(_strings(lesson)):
        if ("$" in s or "\\" in s) and (gaps := speech_gaps(s)):
            bad.append(f"maths with no spoken form {gaps[:3]}: {s[:60]}")
    return list(dict.fromkeys(bad))


_CTRL = {"\x0c": "\\f", "\t": "\\t", "\x08": "\\b", "\r": "\\r", "\x07": "\\a", "\x0b": "\\v"}


def repair(x):
    """A model that writes `\\frac` in JSON with one backslash gets a form feed + "rac": put the backslash back."""
    if isinstance(x, str):
        for ch, back in _CTRL.items():
            x = x.replace(ch, back)
        return x
    if isinstance(x, dict):
        return {k: repair(v) for k, v in x.items()}
    if isinstance(x, list):
        return [repair(v) for v in x]
    return x


def check_batch(result, ids: list[str]) -> tuple[dict, dict]:
    """(valid lessons by id, problems by id) for a worker's result against the ids it was asked for."""
    ok: dict[str, dict] = {}
    bad: dict[str, list[str]] = {}
    rows = result.get("lessons") if isinstance(result, dict) else None
    if not isinstance(rows, list):
        return {}, {i: ["the result has no lessons list"] for i in ids}
    for row in rows:
        row = repair(row)
        lid = row.get("id") if isinstance(row, dict) else None
        if lid not in ids:
            bad.setdefault(str(lid), []).append("id is not in this batch")
        elif lid in ok or lid in bad:
            bad.setdefault(lid, []).append("written twice")
            ok.pop(lid, None)
        elif problems := lesson_problems(row):
            bad[lid] = problems
        else:
            ok[lid] = row
    for lid in ids:
        if lid not in ok and lid not in bad:
            bad[lid] = ["no lesson written"]
    return ok, {k: v for k, v in bad.items() if k in ids}


# ---------------- the worker ----------------
def prompt_for(entries: list[dict], problems: dict | None = None) -> str:
    lines = [(HERE / "roles/shortcut_writer.md").read_text(encoding="utf-8").rstrip(), "", "## Entries", ""]
    for e in entries:
        lines += [f"### ID: {e['id']}", f"Spec: {e['spec']} | Section: {e['section']}" + (f" | Topic: {e['topic']}" if e.get("topic") else "")
                  + f" | Score: {e['score']}/10", f"Title: {e['title']}", "Body:", e["body"], ""]
    if problems:
        lines += ["## A previous attempt failed these checks; fix them", ""]
        lines += [f"- {k}: " + "; ".join(v[:4]) for k, v in problems.items()]
    lines.append(f"Write exactly {len(entries)} lessons, with these ids: " + ", ".join(e["id"] for e in entries))
    return "\n".join(lines)


def codex_week(binary: str) -> float | None:
    """Percent of the Codex week used; None when it cannot be read. FOUNDRY_USAGE_FILE stands in for the real readings."""
    if os.environ.get("FOUNDRY_USAGE_FILE"):
        try:
            windows = json.loads(Path(os.environ["FOUNDRY_USAGE_FILE"]).read_text()).get("codex")
        except (OSError, ValueError):
            return None
    else:
        windows = router.codex_usage(binary)
    week = (windows or {}).get("seven_day") or {}
    return float(week["used"]) if week.get("used") is not None else None


def worker_cmd(model: str, effort: str, out: Path, prompt: str, web: bool) -> list[str]:
    schema = HERE / "schemas/shortcut_lessons.json"
    return [CODEX, *(["--search"] if web else []), "exec", "-m", model, "-c", f'model_reasoning_effort="{effort}"',
            "-c", 'approval_policy="never"', "-s", "workspace-write", "-C", str(REPO), "--color", "never",
            "--output-schema", str(schema), "-o", str(out), prompt]


def run_worker(spec: str, entries: list[dict], model: str, effort: str, web: bool, tag: str,
               problems: dict | None = None) -> tuple[dict, dict, bool, str]:
    """One Codex run on these entries: (valid lessons, problems by id, hit a usage limit, log path)."""
    LOGS.mkdir(parents=True, exist_ok=True)
    stem = f"shortcuts-{spec}-{datetime.now():%m%d-%H%M%S}-{tag}"
    log, out = LOGS / f"{stem}.log", LOGS / f"{stem}.out.json"
    ids = [e["id"] for e in entries]
    prompt = prompt_for(entries, problems)
    cmd = worker_cmd(model, effort, out, prompt, web)
    started = time.time()
    try:
        res = subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True, text=True, cwd=REPO, timeout=TIMEOUT)
        code, said = res.returncode, res.stdout + res.stderr
    except (OSError, subprocess.SubprocessError) as e:
        code, said = -1, f"{type(e).__name__}: {e}"
    limit = code != 0 and any(w in said.lower() for w in router.LIMIT_WORDS)
    try:
        result = json.loads(out.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        result = None
    ok, bad = check_batch(result, ids) if result is not None else ({}, {i: [f"no usable output (exit {code})"] for i in ids})
    with log.open("w", encoding="utf-8") as f:
        f.write(f"spec {spec}  model {model}/{effort}  entries {len(ids)}  exit {code}  {time.time() - started:.0f}s\n")
        f.write(f"valid {len(ok)}  failed {len(bad)}\n")
        for lid, why in bad.items():
            f.write(f"  {lid}: " + " | ".join(why[:5]) + "\n")
        f.write("\n--- worker output ---\n" + said[-6000:] + "\n--- prompt ---\n" + prompt + "\n")
    return ok, bad, limit, str(log)


# ---------------- commands ----------------
def pending(spec: str, min_score: int) -> list[dict]:
    have = lessons_of(spec)
    return [e for e in shortcuts.select(entries_of(spec), {"min_score": min_score, "specs": [spec]}) if e["id"] not in have]


def cmd_run(a) -> int:
    ladder = list(EFFORTS[EFFORTS.index(a.effort):]) if a.effort in EFFORTS else [a.effort]
    done = batches = 0
    for spec in specs_of(a.spec):
        todo = pending(spec, a.min_score)
        print(f"{spec}: {len(todo)} entries without a lesson (score >= {a.min_score})")
        while todo and (a.max_batches is None or batches < a.max_batches):
            batch, todo = todo[:a.batch], todo[a.batch:]
            if a.dry_run:
                print(f"  would run {a.model}/{a.effort} on {len(batch)}: " + ", ".join(e["id"] for e in batch))
                batches += 1
                continue
            used = codex_week(CODEX)
            if used is not None and used >= a.stop_codex_week:
                print(f"stopping: the Codex week is {used:.0f}% used (limit {a.stop_codex_week:g}%)")
                return 0
            ok, bad, limit, log = run_worker(spec, batch, a.model, ladder[0], a.web, f"b{batches + 1}")
            if bad and not limit and len(ladder) > 1:
                again = [e for e in batch if e["id"] in bad]
                ok2, bad, limit, log = run_worker(spec, again, a.model, ladder[1], a.web, f"b{batches + 1}r", bad)
                ok.update(ok2)
            if ok:
                merge(spec, ok)
            batches += 1
            done += len(ok)
            print(f"  batch {batches}: {len(ok)} written, {len(bad)} failed; {Path(log).relative_to(ROOT) if ROOT in Path(log).parents else log}")
            if limit:
                print("stopping: Codex reported a usage limit")
                return 1
    print(f"{done} lessons written in {batches} batches" if not a.dry_run else f"{batches} batches would run")
    return 0


def band_of(score: int) -> str:
    return next(name for low, name in BANDS if score >= low)


def cmd_status(a) -> int:
    for spec in specs_of(a.spec):
        entries, have = entries_of(spec), lessons_of(spec)
        by: dict[str, list[int]] = {name: [0, 0] for _, name in BANDS}
        for e in entries:
            row = by[band_of(e["score"])]
            row[0] += 1
            row[1] += e["id"] in have
        bad = sum(1 for v in have.values() if v.get("unverified"))
        bands = "  ".join(f"{name}: {n[1]}/{n[0]}" for name, n in by.items())
        print(f"{spec:<6} entries {len(entries):>4}  with lesson {sum(n[1] for n in by.values()):>4}  | {bands}"
              + (f"  | unverified {bad}" if bad else ""))
    return 0


def blind_prompt(item: dict) -> str:
    lines = ["Solve this exam question. You may work it out, but end your reply with one last line `ANSWER: <final answer>`."]
    if item["kind"] == "mcq":
        lines.append("It is multiple choice: reply with the single letter A, B, C or D.")
    else:
        lines.append("The last line is `ANSWER: ` and the bare number (no unit, no words; 4.0e-5 style is fine).")
    lines += ["", item["stem"]]
    if item["kind"] == "mcq":
        lines += [f"{c}. {item['options'][c]}" for c in "ABCD"]
    return "\n".join(lines)


def ask_claude(prompt: str, timeout: float = 300) -> str | None:
    cmd = [CLAUDE, "-p", prompt, "--model", "haiku", *router.LEAN, "--tools", ""]
    try:
        res = subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=timeout, cwd=ROOT,
                             env={**os.environ, "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1"})
    except (OSError, subprocess.SubprocessError):
        return None
    report = router.claude_events(res.stdout)["report"]
    return report.get("text") if isinstance(report, dict) else None


def agrees(item: dict, reply: str) -> bool:
    if m := re.findall(r"ANSWER:\s*(.+)", reply):
        reply = m[-1]
    if item["kind"] == "mcq":
        m = re.match(r"\W*([A-D])\b", reply.strip())
        return bool(m) and m[1] == str(item["answer"]).strip()
    want = number_of(item["answer"])
    m = re.search(r"[-+−]?\d+(?:\.\d+)?(?:\s*(?:\\times|×)\s*10\^\{?[-+−]?\d+\}?|[eE][-+]?\d+)?", reply.replace(",", ""))
    got = number_of(m[0]) if m else None
    if want is None or got is None:
        return False
    return abs(got - want) <= 0.02 * abs(want) + 1e-12


def cmd_verify(a) -> int:
    pool = [(spec, lid, i, p) for spec in specs_of(a.spec) for lid, les in lessons_of(spec).items()
            for i, p in enumerate(les.get("practice") or []) if p.get("kind") in ("numeric", "mcq")]
    picked = random.sample(pool, min(a.sample, len(pool)))
    wrong: dict[str, set] = {}
    checked = 0
    for spec, lid, i, p in picked:
        reply = ask_claude(blind_prompt(p))
        if reply is None:
            print(f"  {lid} #{i + 1}: no reply, skipped")
            continue
        checked += 1
        if not agrees(p, reply):
            wrong.setdefault(spec, set()).add(lid)
            print(f"  MISMATCH {lid} #{i + 1}: stored {p['answer']!r}, haiku said {reply.strip()[:60]!r}")
    for spec, ids in wrong.items():
        save_lessons(spec, lambda data, ids=ids: [data[k].update(unverified=True) for k in ids if k in data])
    print(f"checked {checked} of {len(pool)} items; {sum(len(v) for v in wrong.values())} lessons marked unverified")
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="shortcuts_gen.py", description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--spec")
    r.add_argument("--min-score", type=int, default=8)
    r.add_argument("--batch", type=int, default=8)
    r.add_argument("--max-batches", type=int)
    r.add_argument("--model", default="gpt-6-sol")
    r.add_argument("--effort", default="low")
    r.add_argument("--stop-codex-week", type=float, default=70)
    r.add_argument("--web", action="store_true")
    r.add_argument("--dry-run", action="store_true")
    s = sub.add_parser("status")
    s.add_argument("--spec")
    v = sub.add_parser("verify")
    v.add_argument("--spec")
    v.add_argument("--sample", type=int, required=True)
    a = ap.parse_args(argv)
    return {"run": cmd_run, "status": cmd_status, "verify": cmd_verify}[a.cmd](a)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
