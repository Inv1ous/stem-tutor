#!/usr/bin/env python3
"""The content foundry: build syllabus chapters (content packs) with a team of cheap workers and one manager.

Opus is the manager: it reads only this board and small packets, and decides disputes. Codex workers (launched
here, headless, on the ChatGPT plan) draft and fix; Claude Haiku subagents (launched by the manager) blind-solve and
check. Every hand-off goes through deterministic gates (validator, note lint, blind compare), so nobody has to read
a whole pack to know whether it is right.

  foundry.py add <subtopic>...            register chapters (bundle them, hold them back from publishing)
  foundry.py board                        one line per chapter
  foundry.py next                         what to do now, per chapter (the manager's to-do list)
  foundry.py codex <role> <subtopic>      launch a headless Codex worker (drafter, tiebreak, fixer)
  foundry.py dispatch <subtopic>          every Haiku prompt the chapter needs now (solver shards + checker, in parallel)
  foundry.py prompt <role> <subtopic> [--shard k]   one Haiku prompt (solver, checker)
  foundry.py strip <subtopic> [--changed] write the blind questions file, split into solver shards (no answers in it)
  foundry.py compare <subtopic>           score solver answers against the keys; tiebreak answers settle disputes
  foundry.py packet <subtopic>            the manager's adjudication packet: open disputes and findings only
  foundry.py resolve <subtopic> <ref> keep|fix [instruction]
  foundry.py gates <subtopic>             validator + note lint (also run automatically after every worker)
  foundry.py sign <subtopic>              everything green: release the chapter for publishing
  foundry.py status <subtopic>            the chapter's full state as JSON
  foundry.py watch [seconds]              live view of every worker (Codex and Haiku), redrawn every few seconds

Stages: draft → solve → (tiebreak) → check → (adjudicate → fix → recheck) → sign → ready.
"""
from __future__ import annotations

import fcntl
import json
import os
import shlex
import shutil
import subprocess
import sys
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ROOT = Path(os.environ.get("FOUNDRY_ROOT", REPO))  # the data tree (tests point this at a scratch copy)
HERE = REPO / "foundry"
STATE = ROOT / "foundry/state"
LOGS = ROOT / "foundry/logs"
PACKS, SPECS, NOTES = ROOT / "build/out/packs", ROOT / "build/out/specs", ROOT / "build/out/notes"
BLIND, WORK = ROOT / "build/work/blind", ROOT / "build/work/foundry"
HOLD = PACKS / "HOLD.json"
PY = str(REPO / ".venv/bin/python")
CODEX = os.environ.get("FOUNDRY_CODEX") or shutil.which("codex") or \
    "/Applications/ChatGPT.app/Contents/Resources/codex-cli/bin/codex"

sys.path.insert(0, str(REPO / "build"))
sys.path.insert(0, str(REPO / "plugin/stem-tutor/skills/tutor/scripts"))

# who does what; tiers map to Codex models in foundry/config.json
ROLES = {"drafter": "codex", "fixer": "codex", "tiebreak": "codex", "solver": "haiku", "checker": "haiku"}
STAGE_ROLE = {"draft": "drafter", "solve": "solver", "tiebreak": "tiebreak", "check": "checker",
              "adjudicate": "manager", "fix": "fixer", "recheck": "solver", "sign": "manager"}


def config() -> dict:
    return json.loads((HERE / "config.json").read_text())


def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def spec_of(sub: str) -> str:
    return sub.split("-", 1)[0]


def pack_path(sub: str) -> Path:
    return PACKS / spec_of(sub) / f"{sub}.json"


# ---------------- state ----------------
@contextmanager
def chapter(sub: str):
    """Read-modify-write one chapter's state under a lock: several workers finish at once."""
    STATE.mkdir(parents=True, exist_ok=True)
    path = STATE / f"{sub}.json"
    with open(STATE / ".lock", "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        st = json.loads(path.read_text()) if path.exists() else None
        if st is None:
            raise SystemExit(f"{sub} is not a foundry chapter: run `foundry.py add {sub}` first")
        yield st
        st["updated"] = now()
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(st, ensure_ascii=False, indent=1))
        tmp.replace(path)


def load(sub: str) -> dict:
    return json.loads((STATE / f"{sub}.json").read_text())


def chapters() -> list[dict]:
    return [json.loads(p.read_text()) for p in sorted(STATE.glob("*.json"))] if STATE.exists() else []


def move(st: dict, stage: str, note: str = "") -> None:
    st["history"].append({"t": now(), "from": st["stage"], "to": stage, "note": note})
    st["stage"] = stage


def hold(sub: str, reason: str | None) -> None:
    held = json.loads(HOLD.read_text()) if HOLD.exists() else {}
    if reason is None:
        held.pop(sub, None)
    else:
        held[sub] = reason
    HOLD.parent.mkdir(parents=True, exist_ok=True)
    HOLD.write_text(json.dumps(dict(sorted(held.items())), ensure_ascii=False, indent=1))


# ---------------- gates (deterministic, no tokens) ----------------
def gates(sub: str) -> dict:
    import validate_pack
    from tutorlib import lint

    p = pack_path(sub)
    if not p.exists():
        return {"ok": False, "pack": "missing"}
    pack = json.loads(p.read_text())
    graph = json.loads((SPECS / spec_of(sub) / "graph.json").read_text())
    problems = validate_pack.validate(pack, graph)
    note = NOTES / pack.get("note", "")
    findings = lint.lint(note.read_text(encoding="utf-8")) if note.is_file() else [{"rule": "note", "detail": "missing"}]
    out = {"ok": not problems and not findings, "validator": len(problems), "lint": len(findings),
           "items": len(pack.get("items", [])), "extra": sum(it.get("tier") == "extra" for it in pack.get("items", []))}
    if problems or findings:  # enough for a fixer to act on, capped so the board stays small
        out["first"] = [f"{e['rule']} {e['where']} {e.get('detail', '')}"[:160] for e in problems[:8]] + \
                       [f"lint {x.get('rule')} line {x.get('line')}: {x.get('detail', '')}"[:160] for x in findings[:4]]
    return out


def out_of_bounds() -> list[str]:
    """Tracked files changed outside what workers may touch (packs, notes, work files, figures)."""
    try:
        res = subprocess.run(["git", "-C", str(ROOT), "status", "--porcelain"], capture_output=True, text=True)
    except OSError:
        return []
    allowed = ("build/out/packs/", "build/out/notes/", "build/work/", "build/out/Assets/", "build/out/assets/",
               "foundry/state/", "foundry/logs/", "bugwatch/")
    paths = [line[3:].strip('"') for line in res.stdout.splitlines() if line.strip()]
    return [p for p in paths if not p.startswith(allowed) and not p.endswith(".DS_Store")]


# ---------------- commands ----------------
def cmd_add(subs: list[str], stage: str = "draft") -> None:
    for sub in subs:
        path = STATE / f"{sub}.json"
        if path.exists():
            print(f"{sub}: already on the board ({load(sub)['stage']})")
            continue
        STATE.mkdir(parents=True, exist_ok=True)
        start = "solve" if pack_path(sub).exists() and stage == "draft" else stage  # an existing pack is re-checked
        st = {"sub": sub, "stage": start, "created": now(), "updated": now(), "history": [], "gates": None,
              "disputes": [], "findings": [], "fixes": [], "jobs": {}}
        path.write_text(json.dumps(st, indent=1))
        if not (ROOT / "build/work/bundles" / f"{sub}.md").exists() and (REPO / "build/bundle.py").exists():
            subprocess.run([PY, str(REPO / "build/bundle.py"), sub], cwd=ROOT, capture_output=True)
        if sub not in (json.loads(HOLD.read_text()) if HOLD.exists() else {}):  # keep an existing reason
            hold(sub, "in the foundry: not signed off yet")
        print(f"{sub}: added at {start}")


def _running(st: dict) -> list[str]:
    """Roles working on this chapter now: headless workers still alive, or a job you run by hand not yet reported."""
    return [r for r, j in st["jobs"].items()
            if _alive(j.get("pid")) or (j.get("manual") and not j.get("finished"))]


def _haiku(st: dict) -> tuple[list[str], list[str]]:
    """Dispatched Haiku jobs: (still working, finished). A job is finished once its output file is written."""
    working, done = [], []
    for name, j in st["jobs"].items():
        if not j.get("haiku") or j.get("closed"):
            continue
        f = ROOT / j["expects"]
        finished = f.exists() and f.stat().st_mtime >= datetime.fromisoformat(j["started"]).timestamp() - 1
        (done if finished else working).append(name)
    return working, done


def _stalled(st: dict) -> list[str]:
    """Haiku jobs still without their output long after dispatch: the agent stopped (e.g. the session ran out)."""
    limit = config().get("haiku_stall_minutes", 40) * 60
    return [n for n in _haiku(st)[0]
            if (datetime.now().astimezone() - datetime.fromisoformat(st["jobs"][n]["started"])).total_seconds() > limit]


def _alive(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def cmd_board() -> None:
    rows = chapters()
    if not rows:
        print("no chapters yet: foundry.py add <subtopic>")
        return
    print(f"{'CHAPTER':<11} {'STAGE':<11} {'GATES':<6} {'OPEN':<5} WHO / RUNNING")
    for st in rows:
        g = st.get("gates") or {}
        gate = "ok" if g.get("ok") else ("-" if not g else f"{g.get('validator', 0)}+{g.get('lint', 0)}")
        open_n = sum(d["status"] == "open" for d in st["disputes"]) + sum(f["status"] == "open" for f in st["findings"])
        running = _running(st) + [f"Haiku {n}" for n in _haiku(st)[0]]
        print(f"{st['sub']:<11} {st['stage']:<11} {gate:<6} {open_n:<5} "
              f"{STAGE_ROLE.get(st['stage'], '')}{' · running: ' + ', '.join(running) if running else ''}")
    oob = out_of_bounds()
    if oob:
        print(f"\n⚠ files changed outside the foundry's lanes: {', '.join(oob[:6])}")


def action(st: dict) -> str:
    sub, stage = st["sub"], st["stage"]
    running = _running(st)
    if running:
        return f"wait: {', '.join(running)} running"
    working, done = _haiku(st)
    if (stalled := _stalled(st)):
        return f"re-dispatch: Haiku {', '.join(stalled)} stopped without writing its file → foundry.py dispatch {sub}"
    if working:
        return f"wait: Haiku {', '.join(working)} working ({len(done)}/{len(working) + len(done)} done)"
    return {
        "draft": f"foundry.py codex drafter {sub}",
        "solve": f"foundry.py dispatch {sub} → launch every prompt as a Haiku agent, together; then foundry.py compare {sub}",
        "tiebreak": f"foundry.py codex tiebreak {sub}; then foundry.py compare {sub}",
        "check": (f"foundry.py compare {sub}" if load(sub).get("checked") else
                  f"foundry.py dispatch {sub} → Haiku checker (if not already running); then foundry.py compare {sub}"),
        "adjudicate": f"manager: foundry.py packet {sub}; foundry.py resolve {sub} <ref> keep|fix \"…\"",
        "fix": f"foundry.py codex fixer {sub}",
        "recheck": f"foundry.py dispatch {sub} → Haiku solvers; then foundry.py compare {sub}",
        "sign": f"manager: foundry.py sign {sub}",
        "ready": "done (publish with build/publish.py)",
    }.get(stage, "?")


def cmd_next() -> None:
    for st in chapters():
        if st["stage"] != "ready":
            print(f"{st['sub']:<11} {st['stage']:<11} → {action(st)}")


def _pfx(st: dict) -> str:
    return "recheck." if st["stage"] == "recheck" else ""


def cmd_strip(sub: str, changed: bool = False, size: int | None = None) -> list[int]:
    """Write the blind questions file, split into shards so several Haiku solvers can work on one chapter at once."""
    import blind

    pack = json.loads(pack_path(sub).read_text())
    questions = blind.strip(pack)
    if changed:  # recheck: only questions whose content changed since they were answered
        st = load(sub)
        ids = {f["ref"] for f in st["fixes"]} | {d["id"] for d in st["disputes"] if d.get("resolution") == "fix"}
        questions = [q for q in questions if q["id"] in ids]
    BLIND.mkdir(parents=True, exist_ok=True)
    pfx = "recheck." if changed else ""
    for old in BLIND.glob(f"{sub}.{pfx}*.part*.json"):  # shards from an earlier strip would be merged by mistake
        old.unlink()
    out = BLIND / f"{sub}.{pfx}questions.json"
    out.write_text(json.dumps(questions, ensure_ascii=False, indent=1))
    size = size or config().get("solver_shard_size", 20)
    shards = [questions[i:i + size] for i in range(0, len(questions), size)] if len(questions) > size else []
    for k, part in enumerate(shards, 1):
        (BLIND / f"{sub}.{pfx}questions.part{k}.json").write_text(json.dumps(part, ensure_ascii=False, indent=1))
    print(f"{out.relative_to(ROOT)}: {len(questions)} questions" + (f" in {len(shards)} shards" if shards else ""))
    return list(range(1, len(shards) + 1))


def _ingest_check(st: dict) -> bool:
    """Take in the checker's findings once, whenever they arrive (the checker runs alongside the solvers)."""
    f = WORK / f"{st['sub']}.check.json"
    if st.get("checked") or not f.exists():
        return False
    found = json.loads(f.read_text())
    st["findings"] = [{"ref": x.get("where", "?"), "rule": x.get("rule", ""), "evidence": x.get("evidence", ""),
                       "suggested": x.get("fix", ""), "status": "open"} for x in found.get("findings", [])]
    st["checked"] = True
    return True


def _after_solving(st: dict, note: str) -> None:
    if any(d["status"] == "open" for d in st["disputes"]):
        move(st, "tiebreak", note)
    elif not st.get("checked"):
        move(st, "check", note + "; waiting for the checker")
    else:
        move(st, "adjudicate" if any(f["status"] == "open" for f in st["findings"]) else "sign",
             note + f"; {len(st['findings'])} checker findings")


def cmd_compare(sub: str) -> None:
    import blind

    pack = json.loads(pack_path(sub).read_text())
    with chapter(sub) as st:
        fresh = _ingest_check(st)
        pfx = _pfx(st)
        files = [BLIND / f"{sub}.{pfx}answers.json"] + sorted(BLIND.glob(f"{sub}.{pfx}answers.part*.json"))
        files = [f for f in files if f.exists()]
        if st["stage"] in ("solve", "recheck") and files:
            answers = json.loads((BLIND / f"{sub}.answers.json").read_text()) if pfx and \
                (BLIND / f"{sub}.answers.json").exists() else {}
            for f in files:  # every solver's shard
                answers.update(json.loads(f.read_text()))
            res = blind.compare(pack, answers)
            qf = BLIND / f"{sub}.{pfx}questions.json"
            asked = {q["id"] for q in json.loads(qf.read_text())} if qf.exists() else set()
            skipped = [m for m in res["missing"] if m in asked]
            if skipped:  # an unfinished solve is not evidence: send the solver back
                raise SystemExit(f"{sub}: {len(skipped)} questions unanswered ({', '.join(skipped[:5])}…); "
                                 "re-run the solver for the shard that holds them")
            known = {d["id"]: d for d in st["disputes"]}
            for d in res["disagreements"]:
                prev = known.get(d["id"])
                if prev and prev["status"] != "open" and not pfx:
                    continue
                known[d["id"]] = {"id": d["id"], "key": d.get("key"), "solver": d.get("solver"), "tiebreak": None,
                                  "status": "open"}
            if pfx:  # a fixed item the fresh solver now agrees with is closed
                disagree = {d["id"] for d in res["disagreements"]}
                for d in known.values():
                    if d["status"] == "fixed" and d["id"] not in disagree:
                        d["status"] = "closed"
            st["disputes"] = list(known.values())
            n_open = sum(d["status"] == "open" for d in st["disputes"])
            _after_solving(st, f"{res['agreed']} agreed, {n_open} disputed")
        elif st["stage"] == "tiebreak" and (BLIND / f"{sub}.tiebreak.json").exists():
            tb = json.loads((BLIND / f"{sub}.tiebreak.json").read_text())
            res = blind.compare(pack, tb)
            wrong = {d["id"] for d in res["disagreements"]}
            for d in st["disputes"]:
                if d["status"] == "open" and d["id"] in tb:
                    d["tiebreak"] = tb[d["id"]]
                    if d["id"] not in wrong:  # a second, independent solver agrees with the key: the first erred
                        d["status"], d["resolution"] = "closed", "solver wrong (tiebreak agrees with key)"
            n_open = sum(d["status"] == "open" for d in st["disputes"])
            if n_open:  # what is still disputed goes to the manager, with the findings
                if not st.get("checked"):
                    move(st, "check", f"tiebreak left {n_open} for the manager; waiting for the checker")
                else:
                    move(st, "adjudicate", f"tiebreak left {n_open} for the manager")
            else:
                _after_solving(st, "tiebreak settled every dispute")
        elif st["stage"] == "check" and st.get("checked"):
            opened = [d for d in st["disputes"] if d["status"] == "open"] + \
                     [f for f in st["findings"] if f["status"] == "open"]
            move(st, "adjudicate" if opened else "sign", f"{len(st['findings'])} checker findings")
        elif fresh:
            print(f"{sub}: checker findings recorded ({len(st['findings'])}); waiting for the solvers")
            return
        else:
            raise SystemExit(f"{sub}: nothing to compare at stage {st['stage']} (are the answers/findings written?)")
        for name in _haiku(st)[1]:
            st["jobs"][name]["closed"] = now()
        print(f"{sub}: now {st['stage']} ({st['history'][-1]['note']})")


def cmd_dispatch(sub: str) -> None:
    """Every Haiku job this chapter needs now, as prompts to launch together (one Agent call each, one message)."""
    st = load(sub)
    jobs = []
    if st["stage"] in ("solve", "recheck"):
        shards = cmd_strip(sub, changed=st["stage"] == "recheck")
        jobs += [{"role": "solver", "shard": k, "prompt": role_prompt("solver", sub, k)} for k in shards or [None]]
    if st["stage"] in ("solve", "check") and not st.get("checked"):
        jobs.append({"role": "checker", "shard": None, "prompt": role_prompt("checker", sub)})
    pfx = "recheck." if st["stage"] == "recheck" else ""
    with chapter(sub) as st:  # so the board and `watch` can show them working
        for j in jobs:
            part = f".part{j['shard']}" if j["shard"] else ""
            expects = (f"build/work/blind/{sub}.{pfx}answers{part}.json" if j["role"] == "solver"
                       else f"build/work/foundry/{sub}.check.json")
            st["jobs"][j["role"] + (f"#{j['shard']}" if j["shard"] else "")] = {"haiku": True, "started": now(),
                                                                                "expects": expects}
    print(json.dumps(jobs, ensure_ascii=False, indent=1))


def cmd_packet(sub: str) -> None:
    """Only what the manager must judge: each open dispute with its question and both answers, then findings."""
    import blind

    st = load(sub)
    pack = json.loads(pack_path(sub).read_text())
    items = {it["id"]: it for it in pack.get("items", [])}
    stripped = {q["id"]: q for q in blind.strip(pack)}
    out = {"sub": sub, "disputes": [], "findings": [f for f in st["findings"] if f["status"] == "open"]}
    for d in st["disputes"]:
        if d["status"] == "open":
            it = items.get(d["id"], {})
            out["disputes"].append({**d, "question": stripped.get(d["id"], {}), "explanation": it.get("explanation"),
                                    "template": it.get("template")})
    print(json.dumps(out, ensure_ascii=False, indent=1))


def cmd_resolve(sub: str, ref: str, verdict: str, instruction: str = "") -> None:
    with chapter(sub) as st:
        hit = [d for d in st["disputes"] if d["id"] == ref and d["status"] == "open"] + \
              [f for f in st["findings"] if f["ref"] == ref and f["status"] == "open"]
        if not hit:
            raise SystemExit(f"{sub}: no open dispute or finding {ref!r}")
        for x in hit:
            x["status"] = "fixed" if verdict == "fix" else "closed"
            x["resolution"] = f"{verdict}: {instruction}".strip(": ")
        if verdict == "fix":
            st["fixes"].append({"ref": ref, "instruction": instruction, "status": "open"})
        still = [d for d in st["disputes"] if d["status"] == "open"] + [f for f in st["findings"] if f["status"] == "open"]
        if not still:
            move(st, "fix" if any(f["status"] == "open" for f in st["fixes"]) else "sign", "manager decided")
        print(f"{sub}: {ref} → {verdict}; stage {st['stage']}")


def cmd_gates(sub: str) -> dict:
    g = gates(sub)
    with chapter(sub) as st:
        st["gates"] = g
    print(json.dumps(g, ensure_ascii=False))
    return g


def cmd_sign(sub: str) -> None:
    g = gates(sub)
    with chapter(sub) as st:
        st["gates"] = g
        open_ = [d["id"] for d in st["disputes"] if d["status"] == "open"] + \
                [f["ref"] for f in st["findings"] if f["status"] == "open"] + \
                [f["ref"] for f in st["fixes"] if f["status"] == "open"]
        if not g["ok"] or open_ or st["stage"] not in ("sign", "check"):
            raise SystemExit(f"{sub}: not ready (stage {st['stage']}, gates {g}, open {open_})")
        move(st, "ready", "signed off")
    hold(sub, None)
    release(sub)


def chapter_paths(sub: str) -> list[str]:
    """Everything that belongs to one chapter, relative to the repo: what a sign-off commits."""
    pack = json.loads(pack_path(sub).read_text())
    found = [pack_path(sub), NOTES / pack.get("note", ""), STATE / f"{sub}.json", HOLD]
    found += list((ROOT / "build/work/gen").glob(f"{sub}*")) + list((ROOT / "build/out/Assets").glob(f"*/{sub}-*"))
    found += list(BLIND.glob(f"{sub}.*")) + list(WORK.glob(f"{sub}.*"))
    return [str(p.relative_to(ROOT)) for p in found if p.is_file()]


def release(sub: str) -> None:
    """Signed off: publish into the vault now, so the chapter can be studied straight away, and commit it, so the work
    is safe even if the session stops. Each can be switched off in config.json."""
    cfg = config()
    if cfg.get("publish_on_sign", True) and os.environ.get("FOUNDRY_PUBLISH", "1") == "1":
        r = subprocess.run([PY, str(REPO / "build/publish.py")], cwd=REPO, capture_output=True, text=True)
        print(f"{sub}: " + (f"published into the vault {r.stdout.strip()[-120:]}" if r.returncode == 0
                            else f"PUBLISH FAILED, run build/publish.py: {r.stderr.strip()[-300:]}"))
    if cfg.get("commit_on_sign", True) and os.environ.get("FOUNDRY_COMMIT", "1") == "1":
        paths = chapter_paths(sub)
        subprocess.run(["git", "-C", str(ROOT), "add", "--", *paths], capture_output=True)
        r = subprocess.run(["git", "-C", str(ROOT), "commit", "-q", "-m",
                            f"content({sub}): signed off in the foundry\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>",
                            "--", *paths], capture_output=True, text=True)
        print(f"{sub}: " + ("committed" if r.returncode == 0 else f"commit skipped: {(r.stdout + r.stderr).strip()[-160:]}"))
    notify(f"{sub} is ready to study in your vault")
    print(f"{sub}: ready")


def cmd_status(sub: str) -> None:
    print(json.dumps(load(sub), ensure_ascii=False, indent=1))


# ---------------- workers ----------------
def role_prompt(role: str, sub: str, shard: int | None = None) -> str:
    """Short on purpose: the worker reads the long instructions itself (its tokens, not the manager's)."""
    st = load(sub)
    lines = [f"You are the foundry {role} for chapter {sub}. Working directory: {REPO}.",
             f"Read foundry/roles/{role}.md and follow it exactly."]
    if role in ("solver", "tiebreak"):  # blind roles get their questions file only, never the paths of the keys
        re_ = "recheck." if role == "solver" and st["stage"] == "recheck" else ""
        part = f".part{shard}" if shard else ""
        lines.append(f"Questions: build/work/blind/{sub}.{re_}questions{part}.json. Write your answers to "
                     f"build/work/blind/{sub}.{re_ + 'answers' + part if role == 'solver' else 'tiebreak'}.json.")
    else:
        lines.append(f"Chapter files: pack {pack_path(sub).relative_to(ROOT)}, bundle build/work/bundles/{sub}.md.")
    if role == "tiebreak":
        lines.append("Disputed question ids: " + ", ".join(d["id"] for d in st["disputes"] if d["status"] == "open"))
    if role == "fixer":
        lines.append("Fixes to make (from the manager):\n" + "\n".join(
            f"- {f['ref']}: {f['instruction']}" for f in st["fixes"] if f["status"] == "open"))
    if role == "fixer" and st.get("gates") and not st["gates"].get("ok"):
        lines.append("Gate failures to clear: " + "; ".join(st["gates"].get("first", [])))
    return "\n".join(lines)


def cmd_prompt(role: str, sub: str, shard: int | None = None) -> None:
    if ROLES.get(role) == "codex":  # to paste into a Codex session you run yourself: mark it so nobody duplicates it
        with chapter(sub) as st:
            st["jobs"][role] = {"manual": True, "started": now()}
        print(role_prompt(role, sub) + f"\nWhen you have finished, run: .venv/bin/python foundry/foundry.py collect {role} {sub} -")
        return
    print(role_prompt(role, sub, shard))


def cmd_codex(role: str, sub: str) -> None:
    if ROLES.get(role) != "codex":
        raise SystemExit(f"{role} is not a Codex role (Codex roles: {[r for r, w in ROLES.items() if w == 'codex']})")
    cfg = config()
    running = sum(len(_running(st)) for st in chapters())
    if role in _running(load(sub)):
        raise SystemExit(f"{sub}: a {role} is already working on this chapter")
    if running >= cfg["max_parallel"]:
        raise SystemExit(f"{running} workers already running (max_parallel {cfg['max_parallel']}); try again later")
    model, effort = cfg["tiers"][cfg["roles"][role]]
    LOGS.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%m%d-%H%M%S")
    log, out = LOGS / f"{sub}.{role}.{stamp}.log", LOGS / f"{sub}.{role}.{stamp}.out.json"
    codex = [CODEX, "exec", "-m", model, "-c", f'model_reasoning_effort="{effort}"', "-c", 'approval_policy="never"',
             "-s", "workspace-write", "-C", str(REPO), "--color", "never",
             "--output-schema", str(HERE / "schemas" / f"{role}.json"), "-o", str(out), role_prompt(role, sub)]
    then = [PY, str(HERE / "foundry.py"), "collect", role, sub, str(out)]
    shell = f"{shlex.join(codex)} > {shlex.quote(str(log))} 2>&1; {shlex.join(then)} $? >> {shlex.quote(str(log))} 2>&1"
    proc = subprocess.Popen(["/bin/sh", "-c", shell], cwd=REPO, start_new_session=True,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env={**os.environ, "FOUNDRY_ROOT": str(ROOT),
                                                                    "FOUNDRY_NOTIFY": os.environ.get("FOUNDRY_NOTIFY", "1")})
    with chapter(sub) as st:
        st["jobs"][role] = {"pid": proc.pid, "model": f"{model}/{effort}", "started": now(),
                            "log": str(log.relative_to(ROOT)), "out": str(out.relative_to(ROOT))}
    print(f"{sub}: {role} started on {model} ({effort}); log {log.relative_to(ROOT)}")


def notify(text: str) -> None:
    """A macOS notification, only for workers the foundry launched (never from tests or by hand)."""
    if os.environ.get("FOUNDRY_NOTIFY", "1") == "1" and sys.platform == "darwin":
        subprocess.run(["osascript", "-e", f"display notification {json.dumps(text)} with title \"STEM Tutor foundry\""],
                       capture_output=True)


def _last_line(log: Path) -> str:
    try:
        lines = [l.strip() for l in log.read_text(errors="ignore").splitlines()[-40:] if l.strip()]
    except OSError:
        return ""
    return lines[-1][:90] if lines else ""


def _ago(ts: str) -> str:
    mins = int((datetime.now().astimezone() - datetime.fromisoformat(ts)).total_seconds() // 60)
    return f"{mins}m" if mins < 90 else f"{mins // 60}h{mins % 60:02d}"


def watch_text() -> str:
    out = [f"STEM Tutor foundry · {datetime.now():%H:%M:%S}", ""]
    rows = chapters()
    for st in rows:
        if st["stage"] == "ready":
            continue
        workers = []
        for name, j in st["jobs"].items():
            if j.get("haiku") and not j.get("closed"):
                working, _ = _haiku({"jobs": {name: j}})
                stalled = working and name in _stalled(st)
                workers.append(f"Haiku {name} " + ("stalled, re-dispatch" if stalled else
                                                   f"… {_ago(j['started'])}" if working else "✓"))
            elif _alive(j.get("pid")):
                workers.append(f"Codex {name} ({j['model']}) {_ago(j['started'])}: {_last_line(ROOT / j['log'])}")
            elif j.get("manual") and not j.get("finished"):
                workers.append(f"Codex {name} (by hand) {_ago(j['started'])}")
        out.append(f"{st['sub']:<11} {st['stage']:<11} " + (" · ".join(workers) if workers else "idle"))
    recent = sorted(((h["t"], st["sub"], h["note"]) for st in rows for h in st["history"]), reverse=True)[:5]
    if recent:
        out += ["", "Recent:"] + [f"  {t[11:16]} {sub}: {note}" for t, sub, note in recent]
    return "\n".join(out)


def cmd_watch(every: float = 5) -> None:
    import time
    try:
        while True:
            print("\033[2J\033[H" + watch_text(), flush=True)
            time.sleep(every)
    except KeyboardInterrupt:
        pass


def cmd_collect(role: str, sub: str, out: str, code: str = "0") -> None:
    """Runs after a Codex worker exits: record its report, run the gates, move the chapter on."""
    report = {"manual": True} if out == "-" else {}  # "-": a session you ran by hand reports without a file
    try:
        report = report or json.loads(Path(out).read_text())
    except (OSError, ValueError):
        pass
    g = gates(sub)
    notify(f"{sub}: {role} " + ("finished" if int(code) == 0 and report else "failed")
           + (" · gates ok" if g.get("ok") else ""))
    with chapter(sub) as st:
        st["gates"] = g
        job = st["jobs"].get(role, {})
        job.update(finished=now(), exit=int(code), report=report)
        if int(code) != 0 or not report:
            st["history"].append({"t": now(), "from": st["stage"], "to": st["stage"],
                                  "note": f"{role} failed (exit {code}); see {job.get('log')}"})
            return
        if role == "drafter" and g["ok"]:
            move(st, "solve", f"drafted: {g['items']} items")
        elif role == "fixer" and g["ok"]:
            for f in st["fixes"]:
                f["status"] = "done"
            ids = {it["id"] for it in json.loads(pack_path(sub).read_text()).get("items", [])}
            changed_questions = any(f["ref"] in ids or f["ref"].endswith(".faded") for f in st["fixes"])
            move(st, "recheck" if changed_questions else "sign", f"fixed; {len(st['fixes'])} fixes applied")
        elif role == "tiebreak":
            pass  # the manager runs compare, which reads the tiebreak answers
        else:
            st["history"].append({"t": now(), "from": st["stage"], "to": st["stage"],
                                  "note": f"{role} finished but gates are not clean: {g.get('first', [])[:2]}"})


def main(argv: list[str]) -> None:
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return
    cmd, rest = argv[0], argv[1:]
    if cmd == "add":
        cmd_add(rest)
    elif cmd == "board":
        cmd_board()
    elif cmd == "next":
        cmd_next()
    elif cmd == "strip":
        cmd_strip(rest[0], "--changed" in rest)
    elif cmd == "compare":
        cmd_compare(rest[0])
    elif cmd == "packet":
        cmd_packet(rest[0])
    elif cmd == "resolve":
        cmd_resolve(rest[0], rest[1], rest[2], " ".join(rest[3:]))
    elif cmd == "gates":
        cmd_gates(rest[0])
    elif cmd == "sign":
        cmd_sign(rest[0])
    elif cmd == "status":
        cmd_status(rest[0])
    elif cmd == "prompt":
        cmd_prompt(rest[0], rest[1], int(rest[rest.index("--shard") + 1]) if "--shard" in rest else None)
    elif cmd == "dispatch":
        cmd_dispatch(rest[0])
    elif cmd == "codex":
        cmd_codex(rest[0], rest[1])
    elif cmd == "collect":
        cmd_collect(*rest)
    elif cmd == "watch":
        cmd_watch(float(rest[0]) if rest else 5)
    else:
        raise SystemExit(f"unknown command {cmd!r}\n{__doc__}")


if __name__ == "__main__":
    main(sys.argv[1:])
