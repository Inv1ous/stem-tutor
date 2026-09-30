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
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # keep symlinked mount paths as given

from tutorlib import anki, diagnose, lint, report, store, weekly  # noqa: E402
from tutorlib.session import Tutor  # noqa: E402

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
            out({"ok": False, "error": str(e), "fix": store.NOT_FOUND_FIX})
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
            out(t.start(args.mode, args.minutes, kcs, replace=args.replace))
        else:
            sid = (t.session or {}).get("id")
            summary = t.end()
            summary["note"] = report.session_note(t, sid) if sid else None
            out(summary)


def cmd_next(args) -> None:
    v = vault()
    with v.lock():
        t = tutor(v)
        if ((t.session or {}).get("awaiting") or {}).get("activity") in ("teach", "worked", "walkthrough", "refute"):
            t.respond({"done": True})  # the skill runs `next` once one of these is finished (there is no respond)
        out(t.next())


def cmd_answer(args) -> None:
    v = vault()
    with v.lock():
        judge = json.loads(args.judge) if args.judge else None
        out(tutor(v).answer(sys.stdin.read() if args.text == "-" else args.text, judge))


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


SUBJECT_WORDS = {"physics": "phys", "phys": "phys", "chemistry": "chem", "chem": "chem"}
SPEC_PATTERNS = [(r"\b(?:further\s+pure|fp)\s*(\d)\b", "FP"), (r"\b(?:pure|p)\s*(\d)\b", "P"),
                 (r"\b(?:stat(?:istic)?s?|s)\s*(\d)\b", "S"), (r"\b(?:mech(?:anics)?|m)\s*(\d)\b", "M"),
                 (r"\b(?:decision|d)\s*(\d)\b", "D")]
STOP = {"and", "the", "of", "a", "an", "in", "on", "for", "my", "to", "test", "exam", "topic", "topics", "chapter",
        "chapters", "ch", "unit", "units", "physics", "phys", "chemistry", "chem", "maths", "math", "quiz", "revise"}


def cmd_find(args) -> None:
    """Map the learner's words to topic, subtopic or KC ids ("physics topic 2", "kinematics", "P1 quadratics")."""
    t = tutor(vault())
    text = args.text.lower()
    subjects = {v for w, v in SUBJECT_WORDS.items() if re.search(rf"\b{w}\b", text)}
    specs = {s for s in {k["spec"] for k in t.packs.kcs.values()} if re.search(rf"\b{s.lower()}\b", text)}
    for pat, prefix in SPEC_PATTERNS:
        specs |= {prefix + m for m in re.findall(pat, text)}
    specs &= {k["spec"] for k in t.packs.kcs.values()}
    in_scope = lambda spec, subject: (not specs or spec in specs) and (not subjects or subject in subjects)  # noqa: E731

    def entry(kind: str, id_: str, title: str, spec: str) -> dict:
        kcs = [k for k in t.packs.kcs if k == id_ or k.startswith(id_ + ".")]
        return {kind: id_, "title": title, "spec": spec, "kcs": len(kcs), "has_pack": any(t.packs.items_for(k) for k in kcs)}

    hits: list[tuple[float, str, dict]] = []
    ids = {i.lower(): i for i in [*t.packs.topics, *t.packs.subtopics, *t.packs.kcs]}
    for tok in re.findall(r"[a-z0-9]+-[\d.]*\d", text):
        if (i := ids.get(tok)) is not None:
            if i in t.packs.kcs:
                k = t.packs.kcs[i]
                hits.append((-20.0, i, {"kc": i, "title": k["title"], "spec": k["spec"], "has_pack": bool(t.packs.items_for(i))}))
            else:
                tp = t.packs.topics.get(i) or t.packs.subtopics[i]
                hits.append((-20.0, i, entry("topic" if i in t.packs.topics else "subtopic", i, tp["title"], tp["spec"])))
    for n in re.findall(r"\b(?:topic|chapter|ch\.?|unit)s?\s*(\d+(?:\.\d+)?)", text) + re.findall(r"\band\s+(\d+)\b", text):
        for tid, tp in {**t.packs.topics, **t.packs.subtopics}.items():
            if tid.split("-", 1)[-1] == n and in_scope(tp["spec"], tp.get("subject") or t.packs.kcs.get(
                    next((k for k in t.packs.kcs if k.startswith(tid + ".")), ""), {}).get("subject")):
                kind = "topic" if tid in t.packs.topics else "subtopic"
                hits.append((-10.0, tid, entry(kind, tid, tp["title"], tp["spec"])))
    words = [w for w in re.findall(r"[a-z][a-z'-]+", text) if w not in STOP]
    if words:
        for tid, tp in {**t.packs.topics, **t.packs.subtopics}.items():
            subject = tp.get("subject") or next((k["subject"] for k in t.packs.kcs.values() if k["spec"] == tp["spec"]), None)
            score = sum(w in tp["title"].lower() for w in words)
            if score and in_scope(tp["spec"], subject):
                kind = "topic" if tid in t.packs.topics else "subtopic"
                hits.append((-(score + 0.5), tid, entry(kind, tid, tp["title"], tp["spec"])))
        for kid, k in t.packs.kcs.items():
            hay = " ".join([k["title"], k.get("statement", ""), " ".join(k.get("glossary", []))]).lower()
            score = sum(w in hay for w in words)
            if score and in_scope(k["spec"], k["subject"]):
                hits.append((-score, kid, {"kc": kid, "title": k["title"], "spec": k["spec"],
                                           "has_pack": bool(t.packs.items_for(kid))}))
    seen, ranked = set(), []
    for score, id_, h in sorted(hits, key=lambda x: (x[0], not x[2]["has_pack"], x[1])):
        if id_ not in seen:
            seen.add(id_)
            ranked.append(h)
    out({"matches": ranked[:12], "truncated": len(ranked) > 12,
         "say": "Pass topic or subtopic ids straight to --kcs; they cover all their syllabus points."})


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
    res["next"] = "Confirm the KC list with the learner, then engine command: session start --mode diagnose --kcs " + \
                  ",".join(k["kc"] for k in res["kcs"][:6])
    out(res)


def cmd_inbox(args) -> None:
    v = vault()
    folder = v.root / "Inbox"
    folder.mkdir(exist_ok=True)
    if args.action == "done":
        src = v.root / args.file
        if not src.is_file():
            raise FileNotFoundError(args.file)
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


def cmd_week(args) -> None:
    v = vault()
    with v.lock():
        out(weekly.run(tutor(v)))


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
        f = str(root / f) if root and not Path(f).is_absolute() and not Path(f).exists() else f
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
    p.add_argument("--mode", default="autopilot", choices=["autopilot", "review", "learn", "diagnose", "repair", "long", "test", "lesson"])
    p.add_argument("--minutes", type=int, default=50); p.add_argument("--kcs"); p.add_argument("--replace", action="store_true")
    p.set_defaults(fn=cmd_session)
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
        out({"ok": False, "error": str(e), "fix": store.NOT_FOUND_FIX})
    except (KeyError, FileNotFoundError, ValueError, json.JSONDecodeError) as e:
        out({"ok": False, "error": f"{type(e).__name__}: {e}",
             "fix": "Check the id, file path or arguments (ids from find; paths relative to the STEM Tutor folder)."})
    except store.Locked as e:
        out({"ok": False, "error": str(e), "fix": "Another tutor command is still running; wait a few seconds and retry."})


if __name__ == "__main__":
    main()
