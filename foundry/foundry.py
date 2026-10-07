#!/usr/bin/env python3
"""The content foundry: build syllabus chapters (content packs) with a team of cheap workers and one manager.

The manager reads only this board and small packets, and decides disputes. Every other role is a headless worker
launched here, on the learner's Claude allowance (`claude -p`) or their Codex allowance (`codex exec`): the router
(router.py) sends each job to the allowance with more left, so both run out together, and starts each role on the
cheapest model that has proved enough for it. Every hand-off goes through deterministic gates (validator, note lint,
blind compare), so nobody has to read a whole pack to know whether it is right.

  foundry.py add <subtopic>...            register chapters (bundle them, hold them back from publishing)
  foundry.py board                        one line per chapter
  foundry.py next                         what to do now, per chapter (the manager's to-do list)
  foundry.py step [subtopics…]            do all of that which needs no judgement: launch, compare, sign
  foundry.py usage                        what is left of the Claude and Codex allowances; where the next job goes
  foundry.py reading claude five_hour <percent> [reset time]   pass on a figure Claude does not report to the foundry
  foundry.py run <role> <subtopic> [--on claude|codex]   launch one headless worker (drafter, fixer, tiebreak,
                                          solver, checker, adjudicator); `codex <role> <subtopic>` forces Codex
  foundry.py dispatch <subtopic>          launch the solvers (one per shard) and the checker the chapter needs now
  foundry.py queue <role> <subtopics…>    launch that role for each chapter as slots free up (run it detached)
  foundry.py wait [seconds]               return when no worker is running (default: up to 9 minutes)
  foundry.py coverage [--queue N|--json]  the whole syllabus against what is built; holes; what to build next
  foundry.py escalate <subtopic>          launch the adjudicator on the chapter's open items
  foundry.py install-skill                install /foundry (the manager loop on Sonnet, medium effort)
  foundry.py prompt <role> <subtopic> [--shard k]   a worker's prompt, to run by hand
  foundry.py strip <subtopic> [--changed] write the blind questions file, split into solver shards (no answers in it)
  foundry.py compare <subtopic>           score solver answers against the keys; tiebreak answers settle disputes
  foundry.py packet <subtopic>            the manager's adjudication packet: open disputes and findings only
  foundry.py resolve <subtopic> <ref> keep|fix [instruction]
  foundry.py gates <subtopic>             validator + note lint (also run automatically after every worker)
  foundry.py sign <subtopic>              everything green: release the chapter for publishing
  foundry.py status <subtopic>            the chapter's full state as JSON
  foundry.py watch [seconds]              live view of every worker and both allowances, redrawn every few seconds

Stages: draft → solve → (tiebreak) → check → (adjudicate → fix → recheck) → sign → ready.
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
CLAUDE = os.environ.get("FOUNDRY_CLAUDE") or shutil.which("claude") or "claude"
USAGE = ROOT / "foundry/usage.json"  # the router's notes: readings of both allowances, tier floors (not in git)

sys.path.insert(0, str(REPO / "build"))
sys.path.insert(0, str(REPO / "plugin/stem-tutor/skills/tutor/scripts"))
sys.path.insert(0, str(HERE))
import router  # noqa: E402
from router import NAMES  # noqa: E402

# every role is a headless worker; which allowance and which model does it is the router's choice (config.json)
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


@contextmanager
def notes():
    """Read-modify-write the router's notes under their own lock: workers on both allowances finish at once."""
    USAGE.parent.mkdir(parents=True, exist_ok=True)
    with open(USAGE.with_suffix(".lock"), "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            data = json.loads(USAGE.read_text())
        except (OSError, ValueError):
            data = {}
        try:
            yield data
        finally:  # a Wait raised inside still keeps the readings taken before it
            tmp = USAGE.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1))
            tmp.replace(USAGE)


def load(sub: str) -> dict:
    return json.loads((STATE / f"{sub}.json").read_text())


def chapters() -> list[dict]:
    return [json.loads(p.read_text()) for p in sorted(STATE.glob("*.json"))] if STATE.exists() else []


def move(st: dict, stage: str, note: str = "") -> None:
    st["history"].append({"t": now(), "from": st["stage"], "to": stage, "note": note})
    st["stage"] = stage


def hold(sub: str, reason: str | None) -> None:
    """Hold a chapter back from publishing, or release it, under a lock: several workers finish at once."""
    STATE.mkdir(parents=True, exist_ok=True)
    HOLD.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE / ".hold.lock", "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        held = json.loads(HOLD.read_text()) if HOLD.exists() else {}
        if reason is None:
            held.pop(sub, None)
        else:
            held[sub] = reason
        tmp = HOLD.with_suffix(".tmp")
        tmp.write_text(json.dumps(dict(sorted(held.items())), ensure_ascii=False, indent=1))
        tmp.replace(HOLD)


# ---------------- gates (deterministic, no tokens) ----------------
def syllabus_gaps(sub: str, pack: dict, graph: dict, note: str) -> list[dict]:
    """Where the chapter departs from its syllabus: an outcome not taught, not covered or not asked as worded."""
    import syllabus
    bundle = ROOT / "build/work/bundles" / f"{sub}.md"
    words = syllabus.command_words(bundle.read_text(encoding="utf-8")) if bundle.is_file() else None
    return syllabus.check(pack, graph, note, words)


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
    text = note.read_text(encoding="utf-8") if note.is_file() else ""
    findings = lint.lint(text) if note.is_file() else [{"rule": "note", "detail": "missing"}]
    gaps = syllabus_gaps(sub, pack, graph, text)
    out = {"ok": not problems and not findings and not gaps, "validator": len(problems), "lint": len(findings),
           "syllabus": len(gaps), "items": len(pack.get("items", [])),
           "extra": sum(it.get("tier") == "extra" for it in pack.get("items", []))}
    if problems or findings or gaps:  # enough for a worker to act on, capped so the board stays small
        out["first"] = [f"{e['rule']} {e['where']} {e.get('detail', '')}"[:160] for e in problems[:8]] + \
                       [f"lint {x.get('rule')} line {x.get('line')}: {x.get('detail', '')}"[:160] for x in findings[:4]] + \
                       [f"syllabus {e['rule']} {e['where']} {e['detail']}"[:160] for e in gaps[:8]]
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


def extra_ids(sub: str) -> dict:
    """qid → id of the chapter's past-paper extras (the bank questions add_past appends after drafting)."""
    try:
        items = json.loads(pack_path(sub).read_text()).get("items", [])
    except (OSError, ValueError):
        return {}
    return {(i.get("source") or {}).get("qid"): i["id"] for i in items if i.get("tier") == "extra"}


def restore_extras(sub: str, known: dict) -> dict:
    """Re-append the past-paper extras with the ids they had: a worker that re-runs the generator rewrites the pack
    without them. Returns the ids to remember."""
    if not pack_path(sub).exists():
        return known
    sys.path.insert(0, str(REPO / "build"))
    import add_past
    add_past.add(pack_path(sub), keep_ids=known, work=ROOT / "build/work/mcq")
    return {**known, **extra_ids(sub)}


def merge_teach(sub: str) -> None:
    """Put the chapter's teaching cards (build/work/teach/<sub>.json) into its pack: a re-run generator writes the
    pack without them. Only well-formed cards for this chapter's outcomes go in; the syllabus gate reports the rest."""
    cards, p = ROOT / "build/work/teach" / f"{sub}.json", pack_path(sub)
    if not (cards.is_file() and p.exists()):
        return
    import teach_cards
    pack = json.loads(p.read_text())
    graph = json.loads((SPECS / spec_of(sub) / "graph.json").read_text())
    kcs = {k["id"] for k in graph["kcs"] if k["subtopic"] == sub}
    pack["teach"] = {kc: {**card, "source": "pack"} for kc, card in json.loads(cards.read_text()).items()
                     if kc in kcs and not teach_cards.check_card(kc, card)}
    p.write_text(json.dumps(pack, ensure_ascii=False, indent=1))


def _natural(sub: str) -> list:
    return [int(x) if x.isdigit() else x for x in re.split(r"(\d+)", sub)]


def coverage() -> dict:
    """The whole syllabus against what is built. Per spec: outcomes in signed chapters, in progress and not started.
    `holes`: signed chapters that do not pass the syllabus gate. `next`: chapters still to build, in Almanac order,
    those the learner has ticked off in the Almanac last (they are ahead: what is in front of them comes first)."""
    import syllabus
    from tutorlib import almanac, policy
    held = json.loads(HOLD.read_text()) if HOLD.exists() else {}
    plan_file = ROOT / "build/out/plan.json"
    plan = json.loads(plan_file.read_text()) if plan_file.exists() else {}
    graphs = [json.loads(p.read_text()) for p in sorted(SPECS.glob("*/graph.json"))]
    sub_of = {k["id"]: k["subtopic"] for g in graphs for k in g["kcs"]}
    week: dict[str, int] = {}
    for w, objectives in plan.get("weeks", {}).items():
        for o in objectives:
            for kc in o.get("kcs", []) if o.get("type", "NEW") == "NEW" else []:
                if kc in sub_of:
                    week[sub_of[kc]] = min(week.get(sub_of[kc], 999), int(w))
    vault = Path(os.environ.get("STEM_TUTOR_VAULT") or ROOT.parent / "STEM Tutor")
    ticked = set(policy.claimed(plan, almanac.ticks(vault)))

    def ticked_off(sub: str) -> bool:
        kcs = [k for k, s in sub_of.items() if s == sub]
        return bool(kcs) and all(k in ticked for k in kcs)

    def status(sub: str) -> str:
        if (STATE / f"{sub}.json").exists():
            return "ready" if load(sub)["stage"] == "ready" else "in_progress"
        return "not_started" if not pack_path(sub).exists() else "in_progress" if sub in held else "ready"

    out: dict = {"specs": {}, "holes": {}, "next": [], "audit": {}}
    for g in graphs:
        tally = {"outcomes": len(g["kcs"]), "ready": 0, "in_progress": 0, "not_started": 0,
                 "chapters": {"ready": 0, "in_progress": 0, "not_started": 0}}
        for sub in dict.fromkeys(s["id"] for s in g["subtopics"]):
            state = status(sub)
            tally[state] += sum(1 for k in g["kcs"] if k["subtopic"] == sub)
            tally["chapters"][state] += 1
            if state == "not_started":
                out["next"].append(sub)
            elif state == "ready":
                pack = json.loads(pack_path(sub).read_text())
                note = NOTES / pack.get("note", "")
                rules = [e["rule"] for e in syllabus_gaps(sub, pack, g, note.read_text(encoding="utf-8")
                                                          if note.is_file() else "")]
                if rules:
                    out["holes"][sub] = {r: rules.count(r) for r in sorted(set(rules))}
        out["specs"][g["spec"]] = tally
        if (REPO / "build/raw").exists() and ROOT == REPO:  # the syllabus documents as extracted, outcome by outcome
            official = syllabus.official(g["spec"])
            problems = syllabus.audit(official, g) if official else [{"rule": "not-extracted", "where": g["spec"]}]
            out["audit"][g["spec"]] = [f"{e['rule']} {e['where']}" for e in problems]
    out["next"].sort(key=lambda sub: (ticked_off(sub), week.get(sub, 999), _natural(sub)))
    out["ticked_off"] = sum(map(ticked_off, out["next"]))
    return out


def cmd_coverage(args: list[str]) -> None:
    c = coverage()
    if "--json" in args:
        print(json.dumps(c, ensure_ascii=False, indent=1))
        return
    print(f"{'SYLLABUS':<9} {'OUTCOMES':>8} {'SIGNED':>7} {'IN PROGRESS':>12} {'NOT STARTED':>12}   CHAPTERS SIGNED")
    for spec, t in c["specs"].items():
        ch = t["chapters"]
        print(f"{spec:<9} {t['outcomes']:>8} {t['ready']:>7} {t['in_progress']:>12} {t['not_started']:>12}   "
              f"{ch['ready']}/{sum(ch.values())}")
    total = {k: sum(t[k] for t in c["specs"].values()) for k in ("outcomes", "ready", "in_progress", "not_started")}
    print(f"{'ALL':<9} {total['outcomes']:>8} {total['ready']:>7} {total['in_progress']:>12} {total['not_started']:>12}")
    if c["holes"]:
        print("\nSigned chapters that do not pass the syllabus gate (reopen them to fix):")
        for sub, rules in c["holes"].items():
            print(f"  {sub}: " + ", ".join(f"{r} ×{n}" for r, n in rules.items()))
    reviewed = config().get("audit_reviewed", [])  # wording differences already read and found to be tidying only
    flagged = {spec: [p for p in probs if p.split()[-1] not in reviewed] for spec, probs in c["audit"].items()}
    flagged = {spec: probs for spec, probs in flagged.items() if probs}
    if c["audit"]:
        print(f"\nAgainst the syllabus documents: {sum(t['outcomes'] for t in c['specs'].values())} outcomes in the "
              "graphs" + ("; to check: " + "; ".join(p for probs in flagged.values() for p in probs)
                          if flagged else ", every one present with its wording kept"))
    n = int(args[args.index("--queue") + 1]) if "--queue" in args else 0
    print(f"\nStill to build: {len(c['next'])} chapters. Next in Almanac order"
          + (f" ({c['ticked_off']} you ticked off in the Almanac come last)" if c["ticked_off"] else "")
          + f": {' '.join(c['next'][:max(n, 12)])}")
    if n:
        cmd_queue("drafter", c["next"][:n])


def cmd_escalate(sub: str) -> None:
    """Launch the adjudicator on this chapter's open items: it reads the packet and records each decision itself."""
    cmd_run("adjudicator", sub)


def cmd_install_skill() -> None:
    """Install /foundry for every Claude Code session on this Mac: the manager loop on Sonnet at medium effort."""
    dest = Path.home() / ".claude/skills/foundry/SKILL.md"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text((HERE / "skill/SKILL.md").read_text().replace("{REPO}", str(REPO)))
    print(f"installed {dest}")


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
              "disputes": [], "findings": [], "fixes": [], "jobs": {}, "extra_ids": extra_ids(sub)}
        path.write_text(json.dumps(st, indent=1))
        if not (ROOT / "build/work/bundles" / f"{sub}.md").exists() and (REPO / "build/bundle.py").exists():
            subprocess.run([PY, str(REPO / "build/bundle.py"), sub], cwd=ROOT, capture_output=True)
        if sub not in (json.loads(HOLD.read_text()) if HOLD.exists() else {}):  # keep an existing reason
            hold(sub, "in the foundry: not signed off yet")
        print(f"{sub}: added at {start}")


def _running(st: dict) -> list[str]:
    """Jobs working on this chapter now: headless workers still alive, or a job you run by hand not yet reported."""
    return [r for r, j in st["jobs"].items()  # a finished worker can linger as a zombie until its parent reaps it
            if not j.get("finished") and (_alive(j.get("pid")) or j.get("manual"))]


def _busy() -> dict[str, list[str]]:
    """The jobs running now on each allowance, across every chapter."""
    out: dict[str, list[str]] = {}
    for st in chapters():
        for name in _running(st):
            out.setdefault(st["jobs"][name].get("provider", "codex"), []).append(name)
    return out


def maker_of(st: dict) -> str | None:
    """The allowance (so the AI family) that drafted this chapter, when that is known."""
    return st.get("maker") or ("codex" if st["jobs"].get("drafter", {}).get("model", "").startswith("gpt") else None)


def _since(st: dict) -> float:
    """When the chapter entered its present stage: a stage entered again needs its jobs done again."""
    t = next((h["t"] for h in reversed(st["history"]) if h["to"] == st["stage"] != h["from"]), st["created"])
    return datetime.fromisoformat(t).timestamp()


def _done(st: dict, name: str) -> bool:
    """This round's job finished cleanly and the file it had to write is there."""
    j = st["jobs"].get(name, {})
    return bool(j.get("finished") and j.get("exit") == 0 and j.get("expects") and (ROOT / j["expects"]).exists()
                and datetime.fromisoformat(j["finished"]).timestamp() >= _since(st) - 1)


def _solver_jobs(st: dict) -> list[str]:
    """The solver jobs this round needs, one per shard of the questions file; none before it has been written."""
    sub, pfx = st["sub"], _pfx(st)
    if not (BLIND / f"{sub}.{pfx}questions.json").exists():
        return []
    parts = sorted(int(p.stem.rsplit("part", 1)[1]) for p in BLIND.glob(f"{sub}.{pfx}questions.part*.json"))
    return [f"solver#{k}" for k in parts] or ["solver"]


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
        running = _running(st)
        print(f"{st['sub']:<11} {st['stage']:<11} {gate:<6} {open_n:<5} "
              f"{STAGE_ROLE.get(st['stage'], '')}{' · running: ' + ', '.join(running) if running else ''}")
    oob = out_of_bounds()
    if oob:
        print(f"\n⚠ files changed outside the foundry's lanes: {', '.join(oob[:6])}")


def _tiebroken(st: dict) -> bool:
    """A tiebreak has finished cleanly since the chapter last entered that stage: its answers wait to be compared."""
    job = st["jobs"].get("tiebreak", {})
    since = next((h["t"] for h in reversed(st["history"]) if h["to"] == "tiebreak"), "")
    return job.get("exit") == 0 and job.get("finished", "") >= since


def todo(st: dict) -> tuple[str, ...]:
    """What the chapter needs now: ("wait", jobs…), ("run", role), ("dispatch",), ("compare",), ("judge",),
    ("sign",) or ("done",)."""
    sub, stage = st["sub"], st["stage"]
    running = _running(st)
    if running:
        return ("wait", *running)
    if stage in ("solve", "recheck"):
        names = _solver_jobs(st)
        return ("compare",) if names and all(_done(st, n) for n in names) else ("dispatch",)
    if stage == "check":
        return ("compare",) if st.get("checked") or (WORK / f"{sub}.check.json").exists() else ("dispatch",)
    if stage == "tiebreak":
        return ("compare",) if _tiebroken(st) else ("run", "tiebreak")
    return {"draft": ("run", "drafter"), "fix": ("run", "fixer"), "adjudicate": ("judge",), "sign": ("sign",),
            "ready": ("done",)}.get(stage, ("?",))


def action(st: dict) -> str:
    sub, (verb, *rest) = st["sub"], todo(st)
    return {"wait": f"wait: {', '.join(rest)} running",
            "run": f"foundry.py run {' '.join(rest)} {sub}",
            "dispatch": f"foundry.py dispatch {sub}",
            "compare": f"foundry.py compare {sub}",
            "judge": f"manager: foundry.py packet {sub}; foundry.py resolve {sub} <ref> keep|fix \"…\"",
            "sign": f"manager: foundry.py sign {sub}",
            "done": "done (publish with build/publish.py)"}.get(verb, "?")


def cmd_next() -> None:
    for st in chapters():
        if st["stage"] != "ready":
            print(f"{st['sub']:<11} {st['stage']:<11} → {action(st)}")


def cmd_step(only: list[str] | None = None) -> None:
    """One pass over every chapter (or only those named) doing whatever needs no judgement: start the workers that can
    run now, compare finished solves, sign what is green. What it leaves is the manager's: decisions, and waiting."""
    for st in chapters():
        sub, (verb, *rest) = st["sub"], todo(st)
        if only and sub not in only:
            continue
        try:
            if verb == "run":
                cmd_run(rest[0], sub)
            elif verb == "dispatch":
                cmd_dispatch(sub)
            elif verb == "compare":
                cmd_compare(sub)
            elif verb == "sign":
                cmd_sign(sub)
            elif verb != "done":
                print(f"{sub}: " + (f"waiting for {', '.join(rest)}" if verb == "wait" else
                                    f"needs a decision: foundry.py packet {sub}"))
        except SystemExit as e:
            print(f"{sub}: {e}")


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


def _solver_tier(st: dict, good: bool) -> None:
    """Tell the router how the blind solve went. Every shard can finish and the solver still be on too weak a tier:
    what counts is how often the tiebreak sides with the key against it."""
    job = next((j for n, j in st["jobs"].items() if n.startswith("solver") and j.get("provider")), None)
    if job:
        with notes() as n:
            router.record(n, config(), "solver", job["provider"], job.get("rung", 0), ok=good)


def cmd_compare(sub: str) -> None:
    import blind

    pack = json.loads(pack_path(sub).read_text())
    solved_well = None
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
            solved_well = True if not n_open else None  # with disputes, the tiebreak says whose slips they were
            _after_solving(st, f"{res['agreed']} agreed, {n_open} disputed")
        elif st["stage"] == "tiebreak" and (BLIND / f"{sub}.tiebreak.json").exists():
            tb = json.loads((BLIND / f"{sub}.tiebreak.json").read_text())
            res = blind.compare(pack, tb)
            wrong = {d["id"] for d in res["disagreements"]}
            slips = 0
            for d in st["disputes"]:
                if d["status"] == "open" and d["id"] in tb:
                    d["tiebreak"] = tb[d["id"]]
                    if d["id"] not in wrong:  # a second, independent solver agrees with the key: the first erred
                        d["status"], d["resolution"] = "closed", "solver wrong (tiebreak agrees with key)"
                        slips += 1
            solved_well = slips <= max(2, 0.15 * len(blind.strip(pack)))  # more than that is not the odd slip
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
        print(f"{sub}: now {st['stage']} ({st['history'][-1]['note']})")
    if solved_well is not None:
        _solver_tier(load(sub), solved_well)


def cmd_dispatch(sub: str) -> None:
    """Launch every blind solver (one per shard) and the checker this chapter needs now, each as its own headless
    worker. A job already running, or done in this round, is left alone, so this can be asked again at any time."""
    st = load(sub)
    wanted: list[tuple[str, int | None]] = []
    if st["stage"] in ("solve", "recheck"):
        questions = BLIND / f"{sub}.{_pfx(st)}questions.json"
        if not questions.exists() or questions.stat().st_mtime < _since(st) - 1:
            cmd_strip(sub, changed=st["stage"] == "recheck")  # once a round: stripping again discards finished shards
        wanted += [("solver", int(n.split("#")[1]) if "#" in n else None) for n in _solver_jobs(st)]
    if st["stage"] in ("solve", "check") and not st.get("checked") and not (WORK / f"{sub}.check.json").exists():
        wanted.append(("checker", None))
    for role, shard in wanted:
        name = role + (f"#{shard}" if shard else "")
        st = load(sub)
        if name not in _running(st) and not _done(st, name):
            try:
                cmd_run(role, sub, shard=shard)
            except router.Wait as e:
                print(f"{sub}: {name} not started yet ({e})")


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
        stage, ready = st["stage"], g["ok"] and not open_ and st["stage"] in ("sign", "check")
        if ready:
            move(st, "ready", "signed off")
    if not ready:  # raised outside the block so the gate results are saved: the drafter's prompt lists the failures
        raise SystemExit(f"{sub}: not ready (stage {stage}, gates {g}, open {open_})")
    hold(sub, None)
    release(sub)


def chapter_paths(sub: str) -> list[str]:
    """Everything that belongs to one chapter, relative to the repo: what a sign-off commits."""
    pack = json.loads(pack_path(sub).read_text())
    found = [pack_path(sub), NOTES / pack.get("note", ""), STATE / f"{sub}.json", HOLD,
             ROOT / "build/work/mcq/overrides.json", ROOT / "build/work/teach" / f"{sub}.json"]
    found += list((ROOT / "build/work/gen").glob(f"{sub}*")) + list((ROOT / "build/out/Assets").glob(f"*/{sub}-*"))
    found += list(BLIND.glob(f"{sub}.*")) + list(WORK.glob(f"{sub}.*"))
    return [str(p.relative_to(ROOT)) for p in found if p.is_file()]


def release(sub: str) -> None:
    """Signed off: publish into the vault now, so the chapter can be studied straight away, and commit it, so the work
    is safe even if the session stops. Each can be switched off in config.json."""
    cfg = config()
    if cfg.get("publish_on_sign", True) and os.environ.get("FOUNDRY_PUBLISH", "1") == "1":
        vault = os.environ.get("STEM_TUTOR_VAULT")  # the vault the app reads
        r = subprocess.run([PY, str(REPO / "build/publish.py"), *(["--vault", vault] if vault else [])], cwd=REPO,
                           capture_output=True, text=True)
        print(f"{sub}: " + (f"published into the vault {r.stdout.strip()[-120:]}" if r.returncode == 0
                            else f"PUBLISH FAILED, run build/publish.py: {r.stderr.strip()[-300:]}"))
    if cfg.get("commit_on_sign", True) and os.environ.get("FOUNDRY_COMMIT", "1") == "1":
        paths = chapter_paths(sub)
        ignored = subprocess.run(["git", "-C", str(ROOT), "check-ignore", "-z", "--stdin"], input="\0".join(paths),
                                 capture_output=True, text=True).stdout.split("\0")
        paths = [p for p in paths if p not in ignored]  # figures are not kept in git: naming one aborts the commit
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
    if role in ("fixer", "drafter") and st.get("gates") and not st["gates"].get("ok"):
        lines.append("Gate failures to clear: " + "; ".join(st["gates"].get("first", [])))
    if role == "adjudicator":
        lines.append(f"Open items: run `.venv/bin/python foundry/foundry.py packet {sub}`.")
    return "\n".join(lines)


def cmd_prompt(role: str, sub: str, shard: int | None = None) -> None:
    if role in ("drafter", "fixer", "tiebreak"):  # to paste into a session you run yourself: marked, so not duplicated
        with chapter(sub) as st:
            st["jobs"][role] = {"manual": True, "started": now()}
            st["extra_ids"] = {**st.get("extra_ids", {}), **extra_ids(sub)}
        print(role_prompt(role, sub) + f"\nWhen you have finished, run: .venv/bin/python foundry/foundry.py collect {role} {sub} -")
        return
    print(role_prompt(role, sub, shard))


def _expects(st: dict, role: str, shard: int | None) -> str | None:
    """The file a blind solver, tiebreak or checker has to write (relative to the data tree); None for other roles."""
    sub = st["sub"]
    if role == "solver":
        return f"build/work/blind/{sub}.{_pfx(st)}answers{f'.part{shard}' if shard else ''}.json"
    return {"tiebreak": f"build/work/blind/{sub}.tiebreak.json", "checker": f"build/work/foundry/{sub}.check.json"}.get(role)


def cmd_run(role: str, sub: str, on: str | None = None, shard: int | None = None) -> None:
    """Start one headless worker on a chapter. The router picks the allowance (unless `on` names it) and the tier."""
    cfg = config()
    if role not in cfg["ladders"]:
        raise SystemExit(f"{role} is not a worker role (roles: {', '.join(cfg['ladders'])})")
    if on and on not in cfg["ladders"][role]:
        raise SystemExit(f"{on} is not an allowance (allowances: {', '.join(cfg['ladders'][role])})")
    name, st = role + (f"#{shard}" if shard else ""), load(sub)
    if name in _running(st):
        raise SystemExit(f"{sub}: a {name} is already working on this chapter")
    last = st["jobs"].get(name, {})
    with notes() as n:
        provider = on or router.pick(role, maker_of(st), router.usage(n, CODEX, CLAUDE), cfg, _busy())
        failed = last.get("provider") == provider and last.get("ok") is False and not last.get("limit")
        rung = router.rung(n, cfg, role, provider, retry=last.get("rung", 0) if failed else None)
    model, effort = cfg["ladders"][role][provider][rung]
    with chapter(sub) as st:  # so collect can put the extras back with the same ids if the worker rewrites the pack
        st["extra_ids"] = {**st.get("extra_ids", {}), **extra_ids(sub)}
    LOGS.mkdir(parents=True, exist_ok=True)
    stem = f"{sub}.{name.replace('#', '-')}.{datetime.now():%m%d-%H%M%S}"
    log, out, expects = LOGS / f"{stem}.log", LOGS / f"{stem}.out.json", _expects(st, role, shard)
    prompt, schema = role_prompt(role, sub, shard), HERE / "schemas" / f"{role}.json"
    if provider == "codex":
        worker = [CODEX, "exec", "-m", model, "-c", f'model_reasoning_effort="{effort}"', "-c", 'approval_policy="never"',
                  "-s", "workspace-write", "-C", str(REPO), "--color", "never",
                  *(["--output-schema", str(schema)] if schema.exists() else []), "-o", str(out), prompt]
    else:  # lean: none of the learner's plugins, skills, hooks or MCP servers, so a job costs only what the job needs
        worker = [CLAUDE, "-p", prompt, "--model", model, *(["--effort", effort] if effort else []), *router.LEAN,
                  "--tools", "Read,Write,Edit,Bash,Glob,Grep", "--permission-mode", "acceptEdits",
                  "--allowedTools", "Bash(.venv/bin/python *)",
                  *(["--json-schema", schema.read_text()] if schema.exists() else [])]
    then = [PY, str(HERE / "foundry.py"), "collect", name, sub, str(out)]
    shell = (f"{shlex.join(worker)} < /dev/null > {shlex.quote(str(log))} 2>&1; "
             f"{shlex.join(then)} $? >> {shlex.quote(str(log))} 2>&1")
    proc = subprocess.Popen(["/bin/sh", "-c", shell], cwd=REPO, start_new_session=True, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            env={**os.environ, "FOUNDRY_ROOT": str(ROOT), "FOUNDRY_EXPECTS": str(ROOT / expects) if expects else "",
                                 "FOUNDRY_NOTIFY": os.environ.get("FOUNDRY_NOTIFY", "1"),
                                 "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1"})
    tier = f"{model}/{effort}" if effort else model
    with chapter(sub) as st:
        if role == "drafter":
            st["maker"] = provider  # the other family blind-solves what this one writes
        st["jobs"][name] = {"pid": proc.pid, "provider": provider, "model": tier, "rung": rung, "started": now(),
                            "log": str(log.relative_to(ROOT)), "out": str(out.relative_to(ROOT)),
                            **({"expects": expects} if expects else {})}
    print(f"{sub}: {name} started on {NAMES[provider]} ({tier}); log {log.relative_to(ROOT)}")


def notify(text: str) -> None:
    """A macOS notification, only for workers the foundry launched (never from tests or by hand)."""
    if os.environ.get("FOUNDRY_NOTIFY", "1") == "1" and sys.platform == "darwin":
        subprocess.run(["osascript", "-e", f"display notification {json.dumps(text)} with title \"STEM Tutor foundry\""],
                       capture_output=True)


def _last_line(log: Path) -> str:
    """The last thing a worker did: the last line of a Codex transcript, or of a Claude worker's stream of events
    the last thing it said or the tool it last used."""
    try:
        lines = [l.strip() for l in log.read_text(errors="ignore").splitlines()[-40:] if l.strip()]
    except OSError:
        return ""
    for line in reversed(lines):
        if not line.startswith("{"):
            return line[:90]
        try:
            event = json.loads(line)
        except ValueError:
            return line[:90]
        parts = (event.get("message") or {}).get("content") if event.get("type") == "assistant" else None
        for part in reversed(parts or []):
            said = part.get("text") or " ".join(str(v) for v in (part.get("input") or {}).values())
            if said.strip():
                return " ".join(f"{part.get('name', '')} {said}".split())[:90]
    return ""


def _ago(ts: str) -> str:
    mins = int((datetime.now().astimezone() - datetime.fromisoformat(ts)).total_seconds() // 60)
    return f"{mins}m" if mins < 90 else f"{mins // 60}h{mins % 60:02d}"


def usage_lines() -> list[str]:
    """Both allowances in plain words, and where the next job would go."""
    cfg = config()
    with notes() as n:
        u = router.usage(n, CODEX, CLAUDE)
    words = {"five_hour": "5 hours", "seven_day": "week", "limit": "limit hit"}
    out = []
    for p in router.PROVIDERS:
        for name, w in (u.get(p) or {}).items():
            resets = f"resets {datetime.fromtimestamp(w['resets']):%a %H:%M}" if w.get("resets") else "no reset time"
            kept = f" ({cfg['reserve'][p]}% kept back)" if cfg["reserve"].get(p) and name == "seven_day" else ""
            out.append(f"{NAMES[p]:<7} {words.get(name, name):<10} {w['used']:>3.0f}% used  {resets}{kept}")
        if not u.get(p):
            out.append(f"{NAMES[p]:<7} not known yet (it is read from the first worker that runs)")
        elif p == "claude" and "five_hour" not in u[p]:  # a headless run is told only of the limit nearest its end
            out.append(f"{NAMES[p]:<7} {'5 hours':<10} not reported by Claude (pass it on: foundry reading claude "
                       "five_hour <percent> <reset time>)")
    try:
        out.append(f"next job: {NAMES[router.pick('drafter', None, u, cfg, _busy())]} (more of its week left for the "
                   "time until it resets); a chapter's blind solve goes to the one that did not draft it")
    except router.Wait as e:
        out.append(f"next job: none can start ({e})")
    return out


def cmd_usage() -> None:
    print("\n".join(usage_lines()))


def cmd_reading(provider: str, window: str, used: str, resets: str = "") -> None:
    """Tell the foundry a figure it cannot read itself. Claude tells a headless run about one limit only, the one
    nearest its end, so its five-hour window is usually unknown here; the Claude app's usage card shows it:
    `foundry.py reading claude five_hour 74 2026-10-02T17:59:59Z`."""
    if provider != "claude":
        raise SystemExit("only Claude's figures need passing on: Codex is asked directly")
    when = datetime.fromisoformat(resets.replace("Z", "+00:00")).timestamp() if resets else None
    with notes() as n:
        router._reading(n.setdefault("claude", {}), window, float(used), when, time.time())
    cmd_usage()


def watch_text() -> str:
    out = [f"STEM Tutor foundry · {datetime.now():%H:%M:%S}", "", *usage_lines(), ""]
    rows = chapters()
    for st in rows:
        if st["stage"] == "ready":
            continue
        workers = []
        for name, j in st["jobs"].items():
            if j.get("finished"):
                continue
            who = NAMES[j.get("provider", "codex")]
            if _alive(j.get("pid")):
                workers.append(f"{who} {name} ({j['model']}) {_ago(j['started'])}: {_last_line(ROOT / j['log'])}")
            elif j.get("manual"):
                workers.append(f"{who} {name} (by hand) {_ago(j['started'])}")
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


def cmd_queue(role: str, subs: list[str], wait: int = 30, tries: int = 480) -> None:
    """Start a role on each chapter in turn, waiting while no allowance can take it (no free slot, or used up). Run
    it detached and drafting carries on with no manager: `nohup bin/foundry queue drafter <chapters…> >
    foundry/logs/queue.log 2>&1 &`."""
    for sub in subs:
        cmd_add([sub])  # a chapter already on the board is left as it is
        for _ in range(tries):
            try:
                cmd_run(role, sub)
                break
            except router.Wait:
                time.sleep(wait)
            except SystemExit as e:  # anything else: this chapter can't start, move on
                print(f"{sub}: skipped ({e})")
                break


def cmd_wait(timeout: float = 540, every: float = 5) -> None:
    """Return when no worker is running (or after `timeout` seconds): one command instead of polling."""
    end = time.time() + timeout
    while (busy := [f"{st['sub']} {r}" for st in chapters() for r in _running(st)]):
        if time.time() >= end:
            print("still running: " + ", ".join(busy))
            return
        time.sleep(every)
    print("no worker is running")


def cmd_collect(name: str, sub: str, out: str, code: str = "0") -> None:
    """Runs after a worker exits: record its report, run the gates, note what the job says about its tier and its
    allowance, and move the chapter on. `name` is the job: a role, or `solver#2` for a shard."""
    role, exit_code = name.split("#")[0], int(code)
    job = load(sub)["jobs"].get(name, {})
    provider = job.get("provider", "codex")
    report, facts, said = {}, {}, ""
    if out == "-":
        report = {"manual": True}  # a session you ran by hand reports without a file
    elif provider == "claude":  # its output is a stream of events: the report, the cost and the allowance are in it
        facts = router.claude_log(ROOT / job["log"]) if job.get("log") else {}
        report = facts.get("report") or {}
    else:
        try:
            said = Path(out).read_text().strip()
            report = json.loads(said)
        except OSError:
            pass
        except ValueError:  # a role with no report format ends with a sentence
            report = {"text": said} if said else {}
        report = report if isinstance(report, dict) else {"text": said}
    try:
        said = (ROOT / job["log"]).read_text(errors="ignore").lower() if job.get("log") else ""
    except OSError:
        said = ""
    limit = bool(facts.get("limit")) or (exit_code != 0 and any(w in said for w in router.LIMIT_WORDS))
    if role in ("drafter", "fixer") and exit_code == 0:  # what a re-run generator leaves out of the pack
        with chapter(sub) as st:
            st["extra_ids"] = restore_extras(sub, st.get("extra_ids", {}))
        merge_teach(sub)
    g = gates(sub) if role in ("drafter", "fixer") else None  # only these two change the chapter
    wrote = True
    if job.get("expects"):
        f = ROOT / job["expects"]
        wrote = f.exists() and f.stat().st_mtime >= datetime.fromisoformat(job["started"]).timestamp() - 1
    ok = exit_code == 0 and bool(report) and wrote and (g is None or g["ok"])
    if out != "-":
        with notes() as n:
            router.record(n, config(), role, provider, job.get("rung", 0), ok=ok, limit=limit,
                          cost=facts.get("cost", 0.0), windows=facts.get("windows"),
                          judge=not (role == "solver" and ok))  # a solver is judged by its answers, at compare
    if role not in ("solver", "checker"):
        notify(f"{sub}: {role} " + ("finished" if exit_code == 0 and report else "failed")
               + (" · gates ok" if g and g.get("ok") else ""))
    with chapter(sub) as st:
        if g is not None:
            st["gates"] = g
        job = st["jobs"].get(name, {})
        job.update(finished=now(), exit=exit_code, report=report, ok=ok, **({"limit": True} if limit else {}),
                   **({"cost_usd": round(facts["cost"], 3)} if facts.get("cost") else {}))
        if exit_code != 0 or not report or not wrote:
            why = (f"stopped by a usage limit on {NAMES[provider]}" if limit else
                   f"failed (exit {code})" if exit_code or not report else "finished without writing its file")
            st["history"].append({"t": now(), "from": st["stage"], "to": st["stage"],
                                  "note": f"{name} {why}; see {job.get('log')}"})
        elif role == "drafter" and g["ok"]:
            move(st, "solve", f"drafted: {g['items']} items")
        elif role == "fixer" and g["ok"]:
            for f in st["fixes"]:
                f["status"] = "done"
            ids = {it["id"] for it in json.loads(pack_path(sub).read_text()).get("items", [])}
            changed_questions = any(f["ref"] in ids or f["ref"].endswith((".faded", ".discover")) for f in st["fixes"])
            move(st, "recheck" if changed_questions else "sign", f"fixed; {len(st['fixes'])} fixes applied")
        elif g is not None:  # the blind roles and the adjudicator move nothing: compare and resolve do
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
    elif cmd in ("run", "codex"):
        cmd_run(rest[0], rest[1], on="codex" if cmd == "codex" else rest[rest.index("--on") + 1] if "--on" in rest else None)
    elif cmd == "step":
        cmd_step(rest)
    elif cmd == "usage":
        cmd_usage()
    elif cmd == "reading":
        cmd_reading(*rest)
    elif cmd == "queue":
        cmd_queue(rest[0], rest[1:])
    elif cmd == "wait":
        cmd_wait(*(float(x) for x in rest[:1]))
    elif cmd == "coverage":
        cmd_coverage(rest)
    elif cmd == "escalate":
        cmd_escalate(rest[0])
    elif cmd == "install-skill":
        cmd_install_skill()
    elif cmd == "collect":
        cmd_collect(*rest)
    elif cmd == "watch":
        cmd_watch(float(rest[0]) if rest else 5)
    else:
        raise SystemExit(f"unknown command {cmd!r}\n{__doc__}")


if __name__ == "__main__":
    main(sys.argv[1:])
