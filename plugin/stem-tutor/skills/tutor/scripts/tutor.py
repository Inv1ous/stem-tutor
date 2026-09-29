#!/usr/bin/env python3
"""STEM Tutor engine CLI. Every command prints one compact JSON object.

  doctor [--quiet]                 check vault, packs, deps, iCloud placeholders
  hook                             SessionStart: brief if a tutor folder is connected, else silent
  brief [--minutes N]              status + suggested session
  session start [--mode M] [--minutes N] [--kcs A,B]   modes: autopilot review learn diagnose repair long test
  session end                      close session, write session note
  next                             next activity (questions never include answers)
  answer "<entries>" [--judge JSON]  e.g. "1B3, 2 = 4.5 m s-1 ~2, 3?, 4 pts=1,2"
  hint N                           next hint level for open question N
  scheme N                         mark scheme of open structured question N (only after the attempt is uploaded)
  paper list [--code C]            past papers available in the vault
  paper score ID "1a=2/3, 1b=1/2"  log a self-marked past paper per question
  tag EVENT CODE                   reclassify an answer's error (RECALL MISREAD CONCEPT PROCEDURE STRATEGY SLIP NOTATION TIME)
  taught                           KCs the Almanac has covered up to this week, per subject (for baselines)
  find TEXT                        search KCs by title/glossary
  kc ID                            KC details + pack summary
  diagnose map [--title T]         brain dump on stdin -> candidate KCs + echoed misconceptions
  inbox [done FILE]                iPad uploads ready for marking / archive a marked file
  anki                             export new flashcards to Anki/*.apkg
  week                             Today.md, Profile.md, experiments, Anki export, Almanac sync
  rebuild                          recompute state from events
  lint FILE...                     Obsidian render check
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
import time
from datetime import datetime
from pathlib import Path

sys.dont_write_bytecode = True  # no __pycache__ inside the learner's synced folder
sys.path.insert(0, str(Path(__file__).resolve().parent))

from tutorlib import anki, diagnose, experiments, lint, report, store  # noqa: E402
from tutorlib.session import Tutor  # noqa: E402

EXPERIMENT_QUEUE = [
    {"arms": ["worked_faded", "problem_first"], "eligible": {"types": ["conceptual", "procedural"], "theta_min": 0.3}},
    {"arms": ["pretest_explain", "worked_faded"], "eligible": {"types": ["conceptual"]}},
]
UPLOAD = re.compile(r"\.(pdf|png|jpe?g|heic)$", re.I)


def out(obj) -> None:
    print(json.dumps(obj, ensure_ascii=False, separators=(",", ":")))


def vault() -> store.Vault:
    globs = [os.environ["STEM_TUTOR_MOUNTS"]] if os.environ.get("STEM_TUTOR_MOUNTS") else None
    return store.Vault(store.find_vault(globs))


def tutor(v: store.Vault) -> Tutor:
    fixed = os.environ.get("STEM_TUTOR_NOW")
    now = (lambda: datetime.fromisoformat(fixed)) if fixed else None
    return Tutor(v, rng=random.Random(), now=now)


def cmd_doctor(args) -> None:
    try:
        v = vault()
    except store.VaultNotFound as e:
        if not args.quiet:
            out({"ok": False, "error": str(e)})
        return
    t = tutor(v)
    wheels = sorted(p.name.split("-")[0] for p in (Path(__file__).parent / "wheels").glob("*.whl"))
    report_ = {"ok": True, "vault": str(v.root), "packs": (v.tutor / "packs" / "CURRENT").read_text().strip(),
               "kcs": len(t.packs.kcs), "events": sum(1 for _ in v.events()), "open_session": bool(t.session),
               "icloud_placeholders": v.placeholders()[:10], "wheels": wheels,
               "python": sys.version.split()[0]}
    if report_["icloud_placeholders"]:
        report_["fix"] = "Some files are evicted by iCloud: in Finder right-click the STEM Tutor folder → Keep Downloaded."
    if not args.quiet:
        out(report_)


def cmd_hook(args) -> None:
    try:
        v = vault()
    except store.VaultNotFound:
        return
    b = report.brief(tutor(v))
    print("STEM Tutor: " + json.dumps(b, ensure_ascii=False, separators=(",", ":")))


def cmd_brief(args) -> None:
    out(report.brief(tutor(vault()), args.minutes))


def cmd_session(args) -> None:
    v = vault()
    with v.lock():
        t = tutor(v)
        if args.action == "start":
            kcs = [k.strip() for k in (args.kcs or "").split(",") if k.strip()] or None
            out(t.start(args.mode, args.minutes, kcs))
        else:
            sid = (t.session or {}).get("id")
            summary = t.end()
            summary["note"] = report.session_note(t, sid) if sid else None
            out(summary)


def cmd_next(args) -> None:
    v = vault()
    with v.lock():
        out(tutor(v).next())


def cmd_answer(args) -> None:
    v = vault()
    with v.lock():
        judge = json.loads(args.judge) if args.judge else None
        out(tutor(v).answer(args.text, judge))


def cmd_hint(args) -> None:
    v = vault()
    with v.lock():
        out(tutor(v).hint(args.n))


def cmd_scheme(args) -> None:
    v = vault()
    with v.lock():
        out(tutor(v).scheme(args.n))


def cmd_paper(args) -> None:
    v = vault()
    with v.lock():
        t = tutor(v)
        if args.action == "list":
            out({"papers": t.paper_list(args.code)})
        else:
            out(t.paper_score(args.id, args.marks))


def cmd_tag(args) -> None:
    v = vault()
    with v.lock():
        e = tutor(v).log({"type": "tag", "target": args.event, "error": args.code.upper()})
        out({"ok": True, "event": e["id"]})


def cmd_taught(args) -> None:
    from tutorlib import policy
    t = tutor(vault())
    week = policy.current_week(t.packs.plan, t.now())
    res: dict[str, list[str]] = {}
    for w, objs in sorted(t.packs.plan.get("weeks", {}).items(), key=lambda x: int(x[0])):
        if int(w) <= week:
            for o in objs:
                for kc in o.get("kcs", []):
                    if kc in t.packs.kcs and t.packs.items_for(kc) and kc not in res.get(o["subject"], []):
                        res.setdefault(o["subject"], []).append(kc)
    out(res)


def cmd_find(args) -> None:
    t = tutor(vault())
    words = [w.lower() for w in args.text.split()]
    hits = []
    for kid, k in t.packs.kcs.items():
        hay = " ".join([kid, k["title"], k.get("statement", ""), " ".join(k.get("glossary", []))]).lower()
        score = sum(w in hay for w in words)
        if score:
            hits.append((-score, kid, {"kc": kid, "title": k["title"], "spec": k["spec"],
                                       "has_pack": bool(t.packs.items_for(kid))}))
    out({"matches": [h[2] for h in sorted(hits)[:10]]})


def cmd_kc(args) -> None:
    t = tutor(vault())
    k = t.packs.kc(args.id)
    pack = t.packs.pack_for_kc(args.id) or {}
    ks = t.state["kcs"].get(args.id, {})
    out({**{f: k.get(f) for f in ("id", "title", "statement", "type", "prereqs", "spec", "subtopic")},
         "note": pack.get("note"), "outline": pack.get("outline"),
         "misconceptions": [m["statement"] for m in pack.get("misconceptions", []) if m["kc"] == args.id],
         "theta": round(ks.get("theta", 0.0), 2), "attempts": ks.get("n", 0), "items": len(t.packs.items_for(args.id))})


def cmd_diagnose(args) -> None:
    t = tutor(vault())
    text = sys.stdin.read()
    if args.title:
        text = args.title + "\n" + text
    res = diagnose.map_dump(text, t.packs)
    res["next"] = "Confirm the KC list with the learner, then: session start --mode diagnose --kcs " + \
                  ",".join(k["kc"] for k in res["kcs"][:6])
    out(res)


def cmd_inbox(args) -> None:
    v = vault()
    folder = v.root / "Inbox"
    folder.mkdir(exist_ok=True)
    if args.action == "done":
        src = v.root / args.file
        dest = folder / "Marked" / src.name
        dest.parent.mkdir(exist_ok=True)
        src.rename(dest)
        out({"moved": str(dest.relative_to(v.root))})
        return
    settle = float(os.environ.get("STEM_TUTOR_INBOX_SETTLE", "20"))
    ready, syncing = [], []
    for f in sorted(folder.iterdir()):
        if f.name.startswith(".") and f.name.endswith(".icloud"):
            syncing.append({"file": f"Inbox/{f.name[1:-7]}", "why": "still in iCloud: open the folder in Finder"})
            continue
        if not f.is_file() or not UPLOAD.search(f.name):
            continue
        m = re.match(r"(\d+)", f.name)
        entry = {"file": f"Inbox/{f.name}", "n": int(m.group(1)) if m else None, "bytes": f.stat().st_size}
        (syncing if time.time() - f.stat().st_mtime < settle else ready).append(entry)
    out({"ready": ready, "syncing": syncing,
         "say": "Name iPad exports by question number, e.g. '7.pdf'. Marker compares against the scheme."})


def cmd_anki(args) -> None:
    v = vault()
    with v.lock():
        out(anki.export(tutor(v)))


def _maybe_start_experiments(t: Tutor) -> list[str]:
    started = []
    for subject in ("chem", "phys", "math"):
        if experiments.active(t.state, subject):
            continue
        done = [n for n, e in t.state["experiments"].items() if e["subject"] == subject]
        introduced = [k for k, s in t.state["kcs"].items() if s["n"] and k in t.packs.kcs
                      and t.packs.kc(k)["subject"] == subject]
        if len(done) < len(EXPERIMENT_QUEUE) and len(introduced) >= 5:
            name = f"{subject}-{len(done) + 1}"
            t.log({"type": "exp_start", "exp": name, "subject": subject, "target_pairs": 12,
                   **EXPERIMENT_QUEUE[len(done)]})
            started.append(name)
    for name, exp in t.state["experiments"].items():
        r = experiments.analyze(exp)
        if exp["status"] == "running" and r["decision"] not in ("pending",):
            t.log({"type": "exp_end", "exp": name, "result": r})
    return started


def cmd_week(args) -> None:
    v = vault()
    with v.lock():
        t = tutor(v)
        started = _maybe_start_experiments(t)
        res = {"today": report.today_note(t), "profile": report.profile_note(t), "experiments_started": started}
        last = max((e["ts"] for e in v.events() if e["type"] == "anki_export"), default=None)
        if last is None or (t.now() - datetime.fromisoformat(last)).days >= 6:
            res["anki"] = anki.export(t)
        if (v.root / "Almanac").exists() and any((v.root / "Almanac").glob("almanac-progress-*.json")):
            res["almanac"] = report.almanac_sync(t)
        out(res)


def cmd_rebuild(args) -> None:
    v = vault()
    with v.lock():
        out(tutor(v).rebuild())


def cmd_lint(args) -> None:
    root = None
    try:
        root = vault().root
    except store.VaultNotFound:
        pass
    findings = []
    for f in args.files:
        for x in lint.lint(Path(f).read_text(encoding="utf-8"), vault_root=root):
            findings.append({"file": f, **x})
    out({"findings": findings, "ok": not findings})


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(prog="tutor.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("doctor"); p.add_argument("--quiet", action="store_true"); p.set_defaults(fn=cmd_doctor)
    sub.add_parser("hook").set_defaults(fn=cmd_hook)
    p = sub.add_parser("brief"); p.add_argument("--minutes", type=int, default=50); p.set_defaults(fn=cmd_brief)
    p = sub.add_parser("session"); p.add_argument("action", choices=["start", "end"])
    p.add_argument("--mode", default="autopilot", choices=["autopilot", "review", "learn", "diagnose", "repair", "long", "test"])
    p.add_argument("--minutes", type=int, default=50); p.add_argument("--kcs"); p.set_defaults(fn=cmd_session)
    sub.add_parser("next").set_defaults(fn=cmd_next)
    p = sub.add_parser("answer"); p.add_argument("text"); p.add_argument("--judge"); p.set_defaults(fn=cmd_answer)
    p = sub.add_parser("hint"); p.add_argument("n", type=int); p.set_defaults(fn=cmd_hint)
    p = sub.add_parser("scheme"); p.add_argument("n", type=int); p.set_defaults(fn=cmd_scheme)
    p = sub.add_parser("paper"); p.add_argument("action", choices=["list", "score"]); p.add_argument("id", nargs="?")
    p.add_argument("marks", nargs="?"); p.add_argument("--code"); p.set_defaults(fn=cmd_paper)
    p = sub.add_parser("tag"); p.add_argument("event"); p.add_argument("code"); p.set_defaults(fn=cmd_tag)
    sub.add_parser("taught").set_defaults(fn=cmd_taught)
    p = sub.add_parser("find"); p.add_argument("text"); p.set_defaults(fn=cmd_find)
    p = sub.add_parser("kc"); p.add_argument("id"); p.set_defaults(fn=cmd_kc)
    p = sub.add_parser("diagnose"); p.add_argument("action", choices=["map"]); p.add_argument("--title")
    p.set_defaults(fn=cmd_diagnose)
    p = sub.add_parser("inbox"); p.add_argument("action", nargs="?", choices=["done"]); p.add_argument("file", nargs="?")
    p.set_defaults(fn=cmd_inbox)
    sub.add_parser("anki").set_defaults(fn=cmd_anki)
    sub.add_parser("week").set_defaults(fn=cmd_week)
    sub.add_parser("rebuild").set_defaults(fn=cmd_rebuild)
    p = sub.add_parser("lint"); p.add_argument("files", nargs="+"); p.set_defaults(fn=cmd_lint)
    if (argv if argv is not None else sys.argv[1:])[:1] and str((argv or sys.argv[1:])[0]).endswith("tutor.py"):
        out({"ok": False, "error": "The ~/mnt/*/ pattern matched more than one tutor folder.",
             "fix": "Run the engine from the connected STEM Tutor folder's own .tutor/engine/tutor.py path."})
        return
    args = ap.parse_args(argv)
    try:
        args.fn(args)
    except store.VaultNotFound as e:
        out({"ok": False, "error": str(e)})
    except store.Locked as e:
        out({"ok": False, "error": str(e), "fix": "Another tutor command is still running; wait a few seconds and retry."})


if __name__ == "__main__":
    main()
