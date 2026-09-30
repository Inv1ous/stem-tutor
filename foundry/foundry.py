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
  foundry.py prompt <role> <subtopic>     the short prompt for a Haiku subagent (solver, checker)
  foundry.py strip <subtopic> [--changed] write the blind questions file for a solver (no answers in it)
  foundry.py compare <subtopic>           score solver answers against the keys; tiebreak answers settle disputes
  foundry.py packet <subtopic>            the manager's adjudication packet: open disputes and findings only
  foundry.py resolve <subtopic> <ref> keep|fix [instruction]
  foundry.py gates <subtopic>             validator + note lint (also run automatically after every worker)
  foundry.py sign <subtopic>              everything green: release the chapter for publishing
  foundry.py status <subtopic>            the chapter's full state as JSON

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
        running = [r for r, j in st["jobs"].items() if _alive(j.get("pid"))]
        print(f"{st['sub']:<11} {st['stage']:<11} {gate:<6} {open_n:<5} "
              f"{STAGE_ROLE.get(st['stage'], '')}{' · running: ' + ', '.join(running) if running else ''}")
    oob = out_of_bounds()
    if oob:
        print(f"\n⚠ files changed outside the foundry's lanes: {', '.join(oob[:6])}")


def action(st: dict) -> str:
    sub, stage = st["sub"], st["stage"]
    running = [r for r, j in st["jobs"].items() if _alive(j.get("pid"))]
    if running:
        return f"wait: {', '.join(running)} running"
    return {
        "draft": f"foundry.py codex drafter {sub}",
        "solve": f"foundry.py strip {sub}; Haiku: foundry.py prompt solver {sub}; then foundry.py compare {sub}",
        "tiebreak": f"foundry.py codex tiebreak {sub}; then foundry.py compare {sub}",
        "check": f"Haiku: foundry.py prompt checker {sub} (it writes the findings file); then foundry.py compare {sub}",
        "adjudicate": f"manager: foundry.py packet {sub}; foundry.py resolve {sub} <ref> keep|fix \"…\"",
        "fix": f"foundry.py codex fixer {sub}",
        "recheck": f"foundry.py strip {sub} --changed; Haiku: foundry.py prompt solver {sub}; foundry.py compare {sub}",
        "sign": f"manager: foundry.py sign {sub}",
        "ready": "done (publish with build/publish.py)",
    }.get(stage, "?")


def cmd_next() -> None:
    for st in chapters():
        if st["stage"] != "ready":
            print(f"{st['sub']:<11} {st['stage']:<11} → {action(st)}")


def cmd_strip(sub: str, changed: bool = False) -> None:
    import blind

    pack = json.loads(pack_path(sub).read_text())
    questions = blind.strip(pack)
    if changed:  # recheck: only questions whose content changed since they were answered
        st = load(sub)
        ids = {f["ref"] for f in st["fixes"]} | {d["id"] for d in st["disputes"] if d.get("resolution") == "fix"}
        questions = [q for q in questions if q["id"] in ids]
    BLIND.mkdir(parents=True, exist_ok=True)
    out = BLIND / f"{sub}.{'recheck.' if changed else ''}questions.json"
    out.write_text(json.dumps(questions, ensure_ascii=False, indent=1))
    print(f"{out.relative_to(ROOT)}: {len(questions)} questions")


def cmd_compare(sub: str) -> None:
    import blind

    pack = json.loads(pack_path(sub).read_text())
    with chapter(sub) as st:
        answers_f = BLIND / f"{sub}.answers.json"
        if st["stage"] in ("solve", "recheck") and answers_f.exists():
            answers = json.loads(answers_f.read_text())
            if st["stage"] == "recheck" and (BLIND / f"{sub}.recheck.answers.json").exists():
                answers.update(json.loads((BLIND / f"{sub}.recheck.answers.json").read_text()))
            res = blind.compare(pack, answers)
            asked = json.loads((BLIND / f"{sub}.{'recheck.' if st['stage'] == 'recheck' else ''}questions.json")
                               .read_text()) if (BLIND / f"{sub}.questions.json").exists() else []
            skipped = [m for m in res["missing"] if m in {q["id"] for q in asked}]
            if skipped:  # an unfinished solve is not evidence: send the solver back
                raise SystemExit(f"{sub}: {len(skipped)} questions unanswered ({', '.join(skipped[:5])}…); re-run the solver")
            known = {d["id"]: d for d in st["disputes"]}
            for d in res["disagreements"]:
                prev = known.get(d["id"])
                if prev and prev["status"] != "open" and st["stage"] != "recheck":
                    continue
                known[d["id"]] = {"id": d["id"], "key": d.get("key"), "solver": d.get("solver"), "tiebreak": None,
                                  "status": "open"}
            if st["stage"] == "recheck":  # a fixed item the fresh solver now agrees with is closed
                disagree = {d["id"] for d in res["disagreements"]}
                for d in known.values():
                    if d["status"] == "fixed" and d["id"] not in disagree:
                        d["status"] = "closed"
            st["disputes"] = list(known.values())
            n_open = sum(d["status"] == "open" for d in st["disputes"])
            move(st, "tiebreak" if n_open else "check", f"{res['agreed']} agreed, {n_open} disputed")
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
            move(st, "check", f"tiebreak closed {len(tb) - n_open}, {n_open} left for the manager")
        elif st["stage"] == "check" and (WORK / f"{sub}.check.json").exists():
            found = json.loads((WORK / f"{sub}.check.json").read_text())
            st["findings"] = [{"ref": f.get("where", "?"), "rule": f.get("rule", ""), "evidence": f.get("evidence", ""),
                               "suggested": f.get("fix", ""), "status": "open"} for f in found.get("findings", [])]
            opened = [d for d in st["disputes"] if d["status"] == "open"] + st["findings"]
            move(st, "adjudicate" if opened else "sign", f"{len(st['findings'])} checker findings")
        else:
            raise SystemExit(f"{sub}: nothing to compare at stage {st['stage']} (is the answers/findings file written?)")
        print(f"{sub}: now {st['stage']} ({st['history'][-1]['note']})")


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
    print(f"{sub}: ready (released from the hold list; publish with build/publish.py)")


def cmd_status(sub: str) -> None:
    print(json.dumps(load(sub), ensure_ascii=False, indent=1))


# ---------------- workers ----------------
def role_prompt(role: str, sub: str) -> str:
    """Short on purpose: the worker reads the long instructions itself (its tokens, not the manager's)."""
    st = load(sub)
    lines = [f"You are the foundry {role} for chapter {sub}. Working directory: {REPO}.",
             f"Read foundry/roles/{role}.md and follow it exactly."]
    if role in ("solver", "tiebreak"):  # blind roles get their questions file only, never the paths of the keys
        re_ = "recheck." if role == "solver" and st["stage"] == "recheck" else ""
        lines.append(f"Questions: build/work/blind/{sub}.{re_}questions.json. Write your answers to "
                     f"build/work/blind/{sub}.{re_ + 'answers' if role == 'solver' else 'tiebreak'}.json.")
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


def cmd_prompt(role: str, sub: str) -> None:
    if ROLES.get(role) != "haiku":
        raise SystemExit(f"{role} is a Codex role: use `foundry.py codex {role} {sub}`")
    print(role_prompt(role, sub))


def cmd_codex(role: str, sub: str) -> None:
    if ROLES.get(role) != "codex":
        raise SystemExit(f"{role} is not a Codex role (Codex roles: {[r for r, w in ROLES.items() if w == 'codex']})")
    cfg = config()
    running = sum(_alive(j.get("pid")) for st in chapters() for j in st["jobs"].values())
    if running >= cfg["max_parallel"]:
        raise SystemExit(f"{running} workers already running (max_parallel {cfg['max_parallel']}); try again later")
    model, effort = cfg["tiers"][cfg["roles"][role]]
    LOGS.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%m%d-%H%M%S")
    log, out = LOGS / f"{sub}.{role}.{stamp}.log", LOGS / f"{sub}.{role}.{stamp}.out.json"
    codex = [CODEX, "exec", "-m", model, "-c", f'model_reasoning_effort="{effort}"', "-c", 'approval_policy="never"',
             "-s", "workspace-write", "-C", str(REPO), "--ephemeral", "--color", "never",
             "--output-schema", str(HERE / "schemas" / f"{role}.json"), "-o", str(out), role_prompt(role, sub)]
    then = [PY, str(HERE / "foundry.py"), "collect", role, sub, str(out)]
    shell = f"{shlex.join(codex)} > {shlex.quote(str(log))} 2>&1; {shlex.join(then)} $? >> {shlex.quote(str(log))} 2>&1"
    proc = subprocess.Popen(["/bin/sh", "-c", shell], cwd=REPO, start_new_session=True,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env={**os.environ, "FOUNDRY_ROOT": str(ROOT)})
    with chapter(sub) as st:
        st["jobs"][role] = {"pid": proc.pid, "model": f"{model}/{effort}", "started": now(),
                            "log": str(log.relative_to(ROOT)), "out": str(out.relative_to(ROOT))}
    print(f"{sub}: {role} started on {model} ({effort}); log {log.relative_to(ROOT)}")


def cmd_collect(role: str, sub: str, out: str, code: str = "0") -> None:
    """Runs after a Codex worker exits: record its report, run the gates, move the chapter on."""
    report = {}
    try:
        report = json.loads(Path(out).read_text())
    except (OSError, ValueError):
        pass
    g = gates(sub)
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
        cmd_prompt(rest[0], rest[1])
    elif cmd == "codex":
        cmd_codex(rest[0], rest[1])
    elif cmd == "collect":
        cmd_collect(*rest)
    else:
        raise SystemExit(f"unknown command {cmd!r}\n{__doc__}")


if __name__ == "__main__":
    main(sys.argv[1:])
