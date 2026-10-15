#!/usr/bin/env python3
"""The refine system: the content foundry's twin that improves chapters already signed, without remaking them.

Same mechanics as foundry/foundry.py (state files, router, headless workers on the Claude and Codex allowances, blind
solve by the other family, tiebreak, adjudicator, fixer, sign = publish + commit), and most of its helpers are
imported from it. What differs is the use: a scout plans a few additions, a refiner makes them by appending only, and
a `no-loss` gate proves nothing that was there before was removed or changed.

  refine.py add <subtopic…|--all>         put chapters on the refine board (--all: every signed chapter not in the foundry)
  refine.py board                         one line per chapter: stage, gates, passes, last refined
  refine.py next                          what each chapter needs now
  refine.py step [subtopics…]             do everything that needs no judgement: launch, compare, sign
  refine.py wait [seconds]                return when no refine worker is running
  refine.py usage                         both allowances (shared with the foundry)
  refine.py only codex|claude|off         the foundry's switch (one shared setting)
  refine.py run <role> <subtopic> [--on claude|codex]   one headless worker (scout, refiner, solver, checker,
                                          tiebreak, fixer, adjudicator)
  refine.py dispatch <subtopic>           blind solvers for the NEW questions and the checker of the additions
  refine.py queue <role> <subtopics…>     start that role for each chapter as slots free up (run it detached)
  refine.py tts <subtopic…|--all> | status   read-aloud audio (same as foundry tts): local CPU only, no allowance
  refine.py coverage                      which chapters were refined, when, how much; which still lack diagrams
  refine.py packet <subtopic>             open disputes and findings for the manager
  refine.py resolve <subtopic> <ref> keep|fix [instruction]
  refine.py escalate <subtopic>           the adjudicator on the open items
  refine.py gates <subtopic>              foundry gates + no-loss + plan check
  refine.py additions <subtopic>          write and print what this pass has added (what the checker reads)
  refine.py sign <subtopic>               everything green: publish and commit
  refine.py status <subtopic>             the chapter's state as JSON
  refine.py watch [seconds]               live view
  refine.py install-skill                 install /refine (the manager loop on Sonnet, medium effort)
  refine.py collect …                     called by workers when they exit

Stages: plan → refine → solve → (tiebreak) → check → (adjudicate → fix → recheck) → sign → ready.
"""
from __future__ import annotations

import fcntl
import json
import os
import re
import shlex
import subprocess
import sys
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "foundry"))
import foundry as fd  # noqa: E402  (also puts build/, the tutor scripts and the router on the path)
import router  # noqa: E402
from router import NAMES  # noqa: E402

ROOT = fd.ROOT  # the data tree (FOUNDRY_ROOT in tests)
HERE = REPO / "refine"
STATE = ROOT / "refine/state"
LOGS = ROOT / "refine/logs"
WORK = ROOT / "build/work/refine"
BLIND = fd.BLIND
PY = fd.PY
PFX = "refine."  # blind files of a refine pass never clash with the foundry's

STAGE_ROLE = {"plan": "scout", "refine": "refiner", "solve": "solver", "tiebreak": "tiebreak", "check": "checker",
              "adjudicate": "manager", "fix": "fixer", "recheck": "solver", "sign": "manager"}
KINDS = ("diagram", "figure", "questions", "clarification", "feature", "source_gap")
NEW_ID = re.compile(r"-r\d{2,}$")

now, move, pack_path, spec_of = fd.now, fd.move, fd.pack_path, fd.spec_of
_running, _done, _since, _tiebroken, _alive = fd._running, fd._done, fd._since, fd._tiebroken, fd._alive


def config() -> dict:
    return json.loads((HERE / "config.json").read_text())


def plan_path(sub: str) -> Path:
    return WORK / f"{sub}.plan.json"


def snap_path(sub: str) -> Path:
    return WORK / f"{sub}.snapshot.json"


def note_path(pack: dict) -> Path:
    return fd.NOTES / pack.get("note", "")


# ---------------- state ----------------
@contextmanager
def chapter(sub: str):
    STATE.mkdir(parents=True, exist_ok=True)
    path = STATE / f"{sub}.json"
    with open(STATE / ".lock", "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        st = json.loads(path.read_text()) if path.exists() else None
        if st is None:
            raise SystemExit(f"{sub} is not on the refine board: run `refine.py add {sub}` first")
        yield st
        st["updated"] = now()
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(st, ensure_ascii=False, indent=1))
        tmp.replace(path)


def load(sub: str) -> dict:
    return json.loads((STATE / f"{sub}.json").read_text())


def chapters() -> list[dict]:
    return [json.loads(p.read_text()) for p in sorted(STATE.glob("*.json"))] if STATE.exists() else []


def _busy() -> dict[str, list[str]]:
    """Jobs running now on each allowance: the refine system's AND the foundry's, so the two never oversubscribe.
    The foundry's own count already includes refine's (it reads refine/state), so it is used as it is."""
    return fd._busy()


# ---------------- the snapshot and the no-loss gate ----------------
def take_snapshot(sub: str, pass_no: int) -> dict:
    pack = json.loads(pack_path(sub).read_text())
    note = note_path(pack)
    snap = {"pass": pass_no, "taken": now(), "pack": pack,
            "note": note.read_text(encoding="utf-8") if note.is_file() else ""}
    WORK.mkdir(parents=True, exist_ok=True)
    snap_path(sub).write_text(json.dumps(snap, ensure_ascii=False))
    return snap


def snapshot(sub: str) -> dict | None:
    try:
        return json.loads(snap_path(sub).read_text())
    except (OSError, ValueError):
        return None


def ensure_snapshot(st: dict) -> dict:
    """The chapter as it was before this pass's refiner first touched it. Taken once per pass, never retaken on a
    retry: a second refiner attempt is still compared with the original."""
    snap = snapshot(st["sub"])
    if snap is None or snap.get("pass") != st.get("pass", 1):
        snap = take_snapshot(st["sub"], st.get("pass", 1))
    return snap


def _empty(v) -> bool:
    return v is None or v == "" or v == [] or v == {}


def _lines_kept(old: str, new: str) -> str | None:
    """None when every line of `old` is still in `new`, in order (lines may be inserted anywhere); else the first
    line that is gone."""
    it = iter(new.splitlines())
    for line in old.splitlines():
        if not any(line == n for n in it):
            return line
    return None


# fields of an existing item that stay exactly as they were, even when empty (a figure question's `options: null`);
# any other field (explanation, hints, …) must stay as it was where it had a value, and may be filled where it had none
ITEM_FIXED = ("id", "kind", "stem", "options", "answer", "kcs", "source", "template", "image", "tier", "marks",
              "rubric", "scheme", "distractors")
LISTS = {"items": "id", "misconceptions": "id", "worked": "id", "flashcards": "id", "diagrams": "file"}
_GONE = object()


def _entry_problems(where: str, old: dict, new: dict, fixed: tuple = ()) -> list[str]:
    out = []
    for k in dict.fromkeys([*fixed, *old]):
        was, now_ = old.get(k, _GONE), new.get(k, _GONE)
        if k in fixed or (was is not _GONE and not _empty(was)):
            if was != now_:
                out.append(f"{where}: field `{k}` was " + ("removed" if now_ is _GONE else
                                                         "added" if was is _GONE else "changed"))
    return out


def _glyph_fixed(pack: dict, note: str) -> tuple[dict, str]:
    """The chapter as build/glyphs.py writes it: a repair of unsafe Unicode sub/superscripts (Eₖ → $E_k$) is not a loss,
    so both sides of the comparison are put through the very transformation (idempotent: fixed text stays as it is)."""
    import glyphs
    return glyphs.fix_data(pack)[0], "\n".join(glyphs.fix_text(line) for line in note.split("\n"))


def no_loss(before: dict, pack: dict, note: str) -> list[str]:
    """What the refine pass removed or changed. `before` is the snapshot ({"pack", "note"}). Allowed: new items,
    worked examples, flashcards, misconceptions, diagrams, teach-card fields, note lines; an empty field of an existing
    item filled in (an explanation an extra lacked); a glyph repair (see _glyph_fixed). Everything else that was there
    must still be there, unchanged."""
    old, was_note = _glyph_fixed(before["pack"], before.get("note", ""))
    pack, note = _glyph_fixed(pack, note)
    before, out = {**before, "pack": old, "note": was_note}, []
    for key, val in old.items():
        if key in LISTS or key == "teach":
            continue
        if key == "diagrams_skipped" and pack.get("diagrams"):
            continue  # a diagram now drawn replaces the reason there was none
        if key not in pack:
            out.append(f"pack: `{key}` was removed")
        elif pack[key] != val:
            out.append(f"pack: `{key}` was changed")
    for key, idf in LISTS.items():
        now_by = {e.get(idf): e for e in pack.get(key) or [] if isinstance(e, dict)}
        for e in old.get(key) or []:
            ref = e.get(idf)
            if ref not in now_by:
                out.append(f"{key}: {ref} was removed")
            else:
                out += _entry_problems(f"{key} {ref}", e, now_by[ref], ITEM_FIXED if key == "items" else ())
    teach = pack.get("teach") or {}
    for kc, card in (old.get("teach") or {}).items():
        if kc not in teach:
            out.append(f"teach card {kc} was removed")
            continue
        for f, v in card.items():
            if f not in teach[kc]:
                out.append(f"teach card {kc}: `{f}` was removed")
            elif isinstance(v, str) and isinstance(teach[kc][f], str):
                if (gone := _lines_kept(v, teach[kc][f])) is not None:
                    out.append(f"teach card {kc}: `{f}` lost the line {gone[:80]!r}")
            elif teach[kc][f] != v:
                out.append(f"teach card {kc}: `{f}` was changed")
    if (gone := _lines_kept(before.get("note", ""), note)) is not None:
        out.append(f"note: the line {gone[:80]!r} was removed or changed (the note may only gain lines)")
    return out


def new_items(before: dict, pack: dict) -> list[dict]:
    known = {it.get("id") for it in before["pack"].get("items", [])}
    return [it for it in pack.get("items", []) if it.get("id") not in known]


def plan_problems(sub: str, before: dict, pack: dict, plan: dict | None, note: str = "") -> list[str]:
    """New items are named `<sub>-rNN`; what the plan asked for is there; the caps hold. New figures (PNG crops from the
    library) are counted apart from diagrams: each is a file with a provenance sidecar, embedded in the note."""
    caps, out = config()["caps"], []
    added = new_items(before, pack)
    out += [f"new item {it.get('id')} must be named {sub}-rNN (never reuse or renumber ids)" for it in added
            if not str(it.get("id", "")).startswith(sub + "-r") or not NEW_ID.search(str(it.get("id", "")))]
    old_files = {d.get("file") for d in before["pack"].get("diagrams") or []}
    drawn = [d for d in pack.get("diagrams") or [] if d.get("file") not in old_files]
    if len(added) > caps["questions"]:
        out.append(f"{len(added)} new questions: at most {caps['questions']} in one pass")
    if len(drawn) > caps["diagrams"]:
        out.append(f"{len(drawn)} new diagrams: at most {caps['diagrams']} in one pass")
    out += [f"diagram {d['file']} is requested but not rendered (run build/diagrams.py on the pack)" for d in drawn
            if not (ROOT / "build/out" / d.get("file", "")).is_file()]
    import library
    was = set(library.embeds(before.get("note", "")))
    figs = [e for e in dict.fromkeys(library.embeds(note)) if e not in was]
    if len(figs) > caps.get("figures", 3):
        out.append(f"{len(figs)} new figures: at most {caps.get('figures', 3)} in one pass")
    out += [f"figure {e} is embedded but its file does not exist (make it with build/library.py crop)" for e in figs
            if not (library.assets_dir() / e.removeprefix("Assets/")).is_file()]
    out += [f"figure {e} has no provenance sidecar (make it with build/library.py crop or extract)" for e in figs
            if not library.sidecar_of(e).is_file()]
    if plan:
        want_q = sum(int(i.get("count", 1)) for i in plan.get("improvements", []) if i.get("kind") == "questions")
        want_d = sum(1 for i in plan.get("improvements", []) if i.get("kind") == "diagram")
        if len(added) < want_q:
            out.append(f"the plan asks for {want_q} new questions; {len(added)} were added")
        if len(drawn) < want_d:
            out.append(f"the plan asks for {want_d} new diagrams; {len(drawn)} were added")
        want_f = sum(1 for i in plan.get("improvements", []) if i.get("kind") == "figure")
        if len(figs) < want_f:
            have = set(library.embeds(note))
            loose = [Path(d["file"]).name for d in library.sidecars_for(sub)
                     if f"Assets/{Path(d['file']).parent.name}/{Path(d['file']).name}" not in have]
            out.append(f"the plan asks for {want_f} new figures; {len(figs)} were embedded"
                       + (f" (cropped but not embedded: {', '.join(loose[:4])})" if loose else ""))
    return out


def _inherited(g: dict, sub: str, before: dict, pack: dict, note: Path) -> None:
    """What the chapter already had is not the refiner's to fix: it may only add. A link whose title was reworded, or the
    lack of a diagram, was there before the pass (publishing resolves the first; the plan decides the second), so only
    NEW link problems, a requested diagram that is not embedded, and figure problems count in the figures gate."""
    import content_checks
    import library
    if not note.is_file():
        return
    text = note.read_text(encoding="utf-8")
    graph = json.loads((fd.SPECS / fd.spec_of(sub) / "graph.json").read_text())
    old_links = set(fd.link_problems(before.get("note", "")))
    figs = [x for x in fd.link_problems(text) if x not in old_links] + \
           [x for x in fd.diagram_problems(pack, graph, text) if not x.startswith("no diagram")] + \
           library.figure_problems(text, sub) + content_checks.letter_problems(pack) + content_checks.latex_problems(pack)
    first = [x for x in g.get("first", []) if not x.startswith("figures ")] + [f"figures {x}"[:200] for x in figs[:6]]
    g.update(figures=len(figs), first=first)
    g["ok"] = not (g.get("validator") or g.get("lint") or g.get("syllabus") or g.get("glyphs") or figs)
    if not first:
        g.pop("first", None)


def gates(sub: str) -> dict:
    """The foundry's gates (validator, note lint, syllabus, figures: links + diagrams), then no-loss and the plan."""
    g = fd.gates(sub)  # includes the glyphs gate
    before = snapshot(sub)
    if before is None or not pack_path(sub).exists():
        return {**g, "no_loss": 0, "planned": 0}
    pack = json.loads(pack_path(sub).read_text())
    note = note_path(pack)
    _inherited(g, sub, before, pack, note)
    lost = no_loss(before, pack, note.read_text(encoding="utf-8") if note.is_file() else "")
    try:
        plan = json.loads(plan_path(sub).read_text())
    except (OSError, ValueError):
        plan = None
    planned = plan_problems(sub, before, pack, plan, note.read_text(encoding="utf-8") if note.is_file() else "")
    g.update(no_loss=len(lost), planned=len(planned), ok=g["ok"] and not lost and not planned)
    if lost or planned:
        g["first"] = [f"no-loss {x}"[:200] for x in lost[:10]] + [f"plan {x}"[:200] for x in planned[:6]] + \
                     g.get("first", [])
    return g


def additions(sub: str) -> dict:
    """What this pass added, for the checker, the manager and the board."""
    before, pack = snapshot(sub), json.loads(pack_path(sub).read_text())
    if before is None:
        return {"items": [], "diagrams": [], "note_lines": [], "teach": {}, "other": {}}
    note = note_path(pack)
    text = note.read_text(encoding="utf-8") if note.is_file() else ""
    old_lines = before.get("note", "").splitlines()
    added_lines, i = [], 0
    for line in text.splitlines():  # the lines that are not the original ones, in order
        if i < len(old_lines) and line == old_lines[i]:
            i += 1
        else:
            added_lines.append(line)
    old = before["pack"]
    files = {d.get("file") for d in old.get("diagrams") or []}
    teach = {}
    for kc, card in (pack.get("teach") or {}).items():
        was = (old.get("teach") or {}).get(kc, {})
        grown = {f: v for f, v in card.items() if f != "source" and v != was.get(f)}
        if grown:
            teach[kc] = grown
    other = {}
    for key, idf in LISTS.items():
        if key in ("items", "diagrams"):
            continue
        ids = {e.get(idf) for e in old.get(key) or []}
        other[key] = [e for e in pack.get(key) or [] if e.get(idf) not in ids]
    return {"items": new_items(before, pack), "diagrams": [d for d in pack.get("diagrams") or [] if d.get("file") not in files],
            "note_lines": [l for l in added_lines if l.strip()], "teach": teach, "other": {k: v for k, v in other.items() if v}}


def counts(a: dict) -> dict:
    return {"questions": len(a["items"]), "diagrams": len(a["diagrams"]), "note_lines": len(a["note_lines"]),
            "cards": len(a["teach"]), "other": sum(len(v) for v in a["other"].values())}


def write_additions(sub: str) -> Path:
    a = additions(sub)
    WORK.mkdir(parents=True, exist_ok=True)
    out = WORK / f"{sub}.additions.md"
    parts = [f"# What refine pass added to {sub}", "", f"Counts: {json.dumps(counts(a))}", ""]
    if a["note_lines"]:
        parts += ["## New lesson-note lines", "", *a["note_lines"], ""]
    if a["items"]:
        parts += ["## New questions", "", "```json", json.dumps(a["items"], ensure_ascii=False, indent=1), "```", ""]
    if a["teach"]:
        parts += ["## Teaching-card additions", "", "```json", json.dumps(a["teach"], ensure_ascii=False, indent=1), "```", ""]
    if a["diagrams"] or a["other"]:
        parts += ["## Other additions", "", "```json", json.dumps({"diagrams": a["diagrams"], **a["other"]},
                                                                  ensure_ascii=False, indent=1), "```", ""]
    out.write_text("\n".join(parts), encoding="utf-8")
    return out


# ---------------- the plan ----------------
def trim_plan(plan: dict) -> tuple[dict, list[str]]:
    """Keep the plan's improvements within the caps, in the scout's order of priority. Returns what was dropped."""
    caps = config()["caps"]
    kept, dropped, n = [], [], {"diagram": 0, "figure": 0, "questions": 0, "additions": 0}
    for imp in plan.get("improvements") or []:
        kind = imp.get("kind")
        sited = (imp.get("pdf") and imp.get("page") and isinstance(imp.get("box"), list)) if kind == "figure" else imp.get("where")
        if kind not in KINDS or not sited:
            dropped.append(f"not an improvement: {json.dumps(imp)[:80]}")
            continue
        if kind == "diagram":
            ok = n["diagram"] < caps["diagrams"]
            n["diagram"] += ok
        elif kind == "figure":
            ok = n["figure"] < caps.get("figures", 3)
            n["figure"] += ok
        elif kind == "questions":
            c = max(1, int(imp.get("count", 1)))
            room = caps["questions"] - n["questions"]
            ok = room > 0
            if ok:
                imp = {**imp, "count": min(c, room)}
                n["questions"] += imp["count"]
        else:
            ok = n["additions"] < caps["additions"]
            n["additions"] += ok
        (kept.append(imp) if ok else dropped.append(f"over the cap: {kind} {imp.get('where') or imp.get('pdf')}"))
    return {**plan, "improvements": kept}, dropped


# ---------------- commands ----------------
def signed_chapters() -> list[str]:
    """Chapters built, published (not held) and not anywhere in the foundry's pipeline."""
    held = json.loads(fd.HOLD.read_text()) if fd.HOLD.exists() else {}
    out = []
    for p in sorted(fd.PACKS.glob("*/*.json")):
        sub = p.stem
        if sub in held or not sub[:1].isalnum():
            continue
        f = fd.STATE / f"{sub}.json"
        if f.exists() and json.loads(f.read_text()).get("stage") != "ready":
            continue
        out.append(sub)
    return sorted(out, key=fd._natural)


def in_foundry(sub: str) -> str | None:
    """Why the foundry owns this chapter now, or None."""
    held = json.loads(fd.HOLD.read_text()) if fd.HOLD.exists() else {}
    f = fd.STATE / f"{sub}.json"
    if f.exists() and (stage := json.loads(f.read_text()).get("stage")) != "ready":
        return f"in the foundry at {stage}"
    if sub in held:
        return f"held: {held[sub]}"
    return None


def cmd_add(subs: list[str]) -> None:
    if subs == ["--all"] or "--all" in subs:
        subs = signed_chapters()
    for sub in subs:
        if not pack_path(sub).exists():
            print(f"{sub}: no pack; build it in the foundry first")
            continue
        if why := in_foundry(sub):
            print(f"{sub}: skipped ({why})")
            continue
        path = STATE / f"{sub}.json"
        if path.exists():
            st = load(sub)
            if st["stage"] != "ready":
                print(f"{sub}: already being refined ({st['stage']})")
                continue
            with chapter(sub) as st:  # a new pass on a chapter refined before
                st["pass"] = st.get("pass", 1) + 1
                for k in ("disputes", "findings", "fixes"):
                    st[k] = []
                st.update(jobs={}, gates=None, checked=False, maker=None, plan=None, same_family=False)
                move(st, "plan", f"pass {st['pass']}")
            print(f"{sub}: pass {load(sub)['pass']} added at plan")
        else:
            STATE.mkdir(parents=True, exist_ok=True)
            st = {"sub": sub, "stage": "plan", "pass": 1, "refined": 0, "created": now(), "updated": now(),
                  "history": [], "gates": None, "disputes": [], "findings": [], "fixes": [], "jobs": {}}
            path.write_text(json.dumps(st, indent=1))
            print(f"{sub}: added at plan")
        if not (ROOT / "build/work/bundles" / f"{sub}.md").exists() and (REPO / "build/bundle.py").exists():
            subprocess.run([PY, str(REPO / "build/bundle.py"), sub], cwd=ROOT, capture_output=True)


def maker_of(st: dict) -> str | None:
    return st.get("maker")


def _questions(st: dict) -> list | None:
    """This round's blind questions (new ids only), or None before they have been written this round."""
    f = BLIND / f"{st['sub']}.{_pfx(st)}questions.json"
    if not f.exists() or f.stat().st_mtime < _since(st) - 1:
        return None
    return json.loads(f.read_text())


def _pfx(st: dict) -> str:
    return PFX + ("recheck." if st["stage"] == "recheck" else "")


def _solver_jobs(st: dict) -> list[str]:
    sub, pfx = st["sub"], _pfx(st)
    if not _questions(st):
        return []
    parts = sorted(int(p.stem.rsplit("part", 1)[1]) for p in BLIND.glob(f"{sub}.{pfx}questions.part*.json"))
    return [f"solver#{k}" for k in parts] or ["solver"]


def _checked(st: dict) -> bool:
    return bool(st.get("checked")) or (WORK / f"{st['sub']}.check.json").exists() and \
        (WORK / f"{st['sub']}.check.json").stat().st_mtime >= _since_pass(st) - 1


def _since_pass(st: dict) -> float:
    """When this pass began: a check file from an earlier pass does not count."""
    t = next((h["t"] for h in reversed(st["history"]) if h["to"] == "plan"), st["created"])
    return datetime.fromisoformat(t).timestamp()


def todo(st: dict) -> tuple[str, ...]:
    running = _running(st)
    if running:
        return ("wait", *running)
    stage = st["stage"]
    if stage in ("solve", "recheck"):
        names, qs = _solver_jobs(st), _questions(st)
        if qs is not None and not qs:  # nothing new to solve this round: only the checker
            return ("compare",) if stage == "recheck" or _checked(st) else ("dispatch",)
        return ("compare",) if names and all(_done(st, n) for n in names) else ("dispatch",)
    if stage == "check":
        return ("compare",) if _checked(st) else ("dispatch",)
    if stage == "tiebreak":
        return ("compare",) if _tiebroken(st) else ("run", "tiebreak")
    return {"plan": ("run", "scout"), "refine": ("run", "refiner"), "fix": ("run", "fixer"), "adjudicate": ("judge",),
            "sign": ("sign",), "ready": ("done",)}.get(stage, ("?",))


def action(st: dict) -> str:
    sub, (verb, *rest) = st["sub"], todo(st)
    return {"wait": f"wait: {', '.join(rest)} running", "run": f"refine.py run {' '.join(rest)} {sub}",
            "dispatch": f"refine.py dispatch {sub}", "compare": f"refine.py compare {sub}",
            "judge": f"manager: refine.py packet {sub}; refine.py resolve {sub} <ref> keep|fix \"…\"",
            "sign": f"manager: refine.py sign {sub}", "done": "done"}.get(verb, "?")


def cmd_next() -> None:
    for st in chapters():
        if st["stage"] != "ready":
            print(f"{st['sub']:<11} {st['stage']:<11} → {action(st)}")


MAX_UNCLEAN = 3  # consecutive attempts that end with the gates still red before a pass is given up


def unclean_streak(st: dict) -> int:
    """How many of the latest history entries, in a row, say a worker finished with the gates not clean."""
    n = 0
    for h in reversed(st["history"]):
        if "gates are not clean" not in h.get("note", ""):
            break
        n += 1
    return n


def give_up(sub: str, why: str) -> None:
    """Drop this pass's additions and mark the chapter ready as it was: a refiner that cannot get past the gates must
    not loop on the learner's allowance. What was committed before this pass stays; what is uncommitted goes (git),
    or, with no git history for the files, the snapshot taken before the pass is put back."""
    st0 = load(sub)
    pack_file = pack_path(sub)
    pack = json.loads(pack_file.read_text())
    note = note_path(pack)
    rel = [str(f.relative_to(fd.ROOT)) for f in (pack_file, note) if f.exists()]
    done = subprocess.run(["git", "checkout", "--", *rel], cwd=fd.ROOT, capture_output=True).returncode == 0
    before = snapshot(sub)
    if not done and before is not None:
        pack_file.write_text(json.dumps(before["pack"], ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        if note.is_file():
            note.write_text(before.get("note", ""), encoding="utf-8")
    with chapter(sub) as st:
        st["abandoned"] = {"at": now(), "pass": st.get("pass", st0.get("pass", 1)), "why": why[:300]}
        st["gates"] = None
        move(st, "ready", f"given up after {MAX_UNCLEAN} attempts left the gates red: {why[:160]}; additions dropped")


def cmd_step(only: list[str] | None = None) -> None:
    for st in chapters():
        sub, (verb, *rest) = st["sub"], todo(st)
        if only and sub not in only:
            continue
        if st["stage"] in ("refine", "fix", "recheck") and not _running(st) and unclean_streak(st) >= MAX_UNCLEAN:
            last = st["history"][-1].get("note", "")
            give_up(sub, last.split("gates are not clean:", 1)[-1].strip())
            print(f"{sub}: given up (gates red {unclean_streak(st)} times in a row); its additions were dropped")
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
                                    f"needs a decision: refine.py packet {sub}"))
        except SystemExit as e:
            print(f"{sub}: {e}")


def _short_date(ts: str | None) -> str:
    return ts[:10] if ts else "-"


def cmd_board() -> None:
    rows = chapters()
    if not rows:
        print("no chapters on the refine board yet: refine.py add <subtopic…|--all>")
        return
    print(f"{'CHAPTER':<11} {'STAGE':<11} {'GATES':<6} {'OPEN':<5} {'PASS':<5} {'REFINED':<8} {'LAST':<11} WHO / RUNNING")
    for st in rows:
        g = st.get("gates") or {}
        gate = "ok" if g.get("ok") else ("-" if not g else f"{g.get('validator', 0)}+{g.get('lint', 0)}+{g.get('no_loss', 0)}")
        open_n = sum(d["status"] == "open" for d in st["disputes"]) + sum(f["status"] == "open" for f in st["findings"])
        running = _running(st)
        print(f"{st['sub']:<11} {st['stage']:<11} {gate:<6} {open_n:<5} {st.get('pass', 1):<5} {st.get('refined', 0):<8} "
              f"{_short_date(st.get('last_refined')):<11} {STAGE_ROLE.get(st['stage'], '')}"
              f"{' · running: ' + ', '.join(running) if running else ''}")


def cmd_strip(sub: str, changed: bool = False, size: int | None = None) -> list[int]:
    """The blind questions file for this pass: the NEW questions only (items, faded examples and card checks the
    snapshot did not have), split into shards."""
    import blind

    pack = json.loads(pack_path(sub).read_text())
    before = snapshot(sub)
    old_ids = {i for i, _ in blind._instances(before["pack"])} if before else set()
    questions = [q for q in blind.strip(pack) if q["id"] not in old_ids]
    st = load(sub)
    if changed:  # recheck: only new questions whose content a fix changed
        ids = {f["ref"] for f in st["fixes"]} | {d["id"] for d in st["disputes"] if d.get("resolution", "").startswith("fix")}
        questions = [q for q in questions if q["id"] in ids]
    BLIND.mkdir(parents=True, exist_ok=True)
    pfx = PFX + ("recheck." if changed else "")
    stale = [*BLIND.glob(f"{sub}.{pfx}*.part*.json"), *BLIND.glob(f"{sub}.{pfx}answers*.json")]
    if not changed:  # a new round: the last pass's tiebreak answers are not this one's
        stale.append(BLIND / f"{sub}.{PFX}tiebreak.json")
    for old in stale:
        if old.exists():
            old.unlink()
    out = BLIND / f"{sub}.{pfx}questions.json"
    out.write_text(json.dumps(questions, ensure_ascii=False, indent=1))
    size = size or config().get("solver_shard_size", 20)
    shards = [questions[i:i + size] for i in range(0, len(questions), size)] if len(questions) > size else []
    for k, part in enumerate(shards, 1):
        (BLIND / f"{sub}.{pfx}questions.part{k}.json").write_text(json.dumps(part, ensure_ascii=False, indent=1))
    print(f"{out.relative_to(ROOT)}: {len(questions)} new questions" + (f" in {len(shards)} shards" if shards else ""))
    return list(range(1, len(shards) + 1))


def _ingest_check(st: dict) -> bool:
    f = WORK / f"{st['sub']}.check.json"
    if st.get("checked") or not f.exists() or f.stat().st_mtime < _since_pass(st) - 1:
        return False
    found = json.loads(f.read_text())
    st["findings"] = [{"ref": x.get("where", "?"), "rule": x.get("rule", ""), "evidence": x.get("evidence", ""),
                       "suggested": x.get("fix", ""), "status": "open"} for x in found.get("findings", [])]
    st["checked"] = True
    return True


def _solver_tier(st: dict, good: bool) -> None:
    job = next((j for n, j in st["jobs"].items() if n.startswith("solver") and j.get("provider")), None)
    if job:
        with fd.notes() as n:
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
        asked_qs = _questions(st)
        if st["stage"] in ("solve", "recheck") and (files or asked_qs == []):
            asked = {q["id"] for q in asked_qs or []}
            answers = {}
            for f in files:
                answers.update(fd.read_answers(f))
            answers = {k: v for k, v in answers.items() if k in asked}
            res = blind.compare(pack, answers)
            skipped = [m for m in res["missing"] if m in asked]
            if skipped:
                raise SystemExit(f"{sub}: {len(skipped)} questions unanswered ({', '.join(skipped[:5])}…); "
                                 "re-run the solver for the shard that holds them")
            known = {d["id"]: d for d in st["disputes"]}
            for d in res["disagreements"]:
                prev = known.get(d["id"])
                if prev and prev["status"] != "open" and pfx == PFX:
                    continue
                known[d["id"]] = {"id": d["id"], "key": d.get("key"), "solver": d.get("solver"), "tiebreak": None,
                                  "status": "open"}
            if st["stage"] == "recheck":
                disagree = {d["id"] for d in res["disagreements"]}
                for d in known.values():
                    if d["status"] == "fixed" and d["id"] not in disagree:
                        d["status"] = "closed"
                st["checked"] = True  # a recheck re-solves; the additions were checked before
            st["disputes"] = list(known.values())
            n_open = sum(d["status"] == "open" for d in st["disputes"])
            solved_well = True if (not n_open and asked) else None
            fd._after_solving(st, f"{res['agreed']} of {len(asked)} new questions agreed, {n_open} disputed")
        elif st["stage"] == "tiebreak" and (BLIND / f"{sub}.{PFX}tiebreak.json").exists():
            tb = json.loads((BLIND / f"{sub}.{PFX}tiebreak.json").read_text())
            res = blind.compare(pack, tb)
            wrong = {d["id"] for d in res["disagreements"]}
            slips = 0
            for d in st["disputes"]:
                if d["status"] == "open" and d["id"] in tb:
                    d["tiebreak"] = tb[d["id"]]
                    if d["id"] not in wrong:
                        d["status"], d["resolution"] = "closed", "solver wrong (tiebreak agrees with key)"
                        slips += 1
            solved_well = slips <= max(2, 0.15 * max(1, len(_questions_any(st))))
            n_open = sum(d["status"] == "open" for d in st["disputes"])
            if n_open:
                move(st, "adjudicate" if st.get("checked") else "check", f"tiebreak left {n_open} for the manager")
            else:
                fd._after_solving(st, "tiebreak settled every dispute")
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


def _questions_any(st: dict) -> list:
    f = BLIND / f"{st['sub']}.{PFX}questions.json"
    return json.loads(f.read_text()) if f.exists() else []


def cmd_dispatch(sub: str) -> None:
    st = load(sub)
    wanted: list[tuple[str, int | None]] = []
    if st["stage"] in ("solve", "recheck"):
        if _questions(st) is None:
            cmd_strip(sub, changed=st["stage"] == "recheck")
        wanted += [("solver", int(n.split("#")[1]) if "#" in n else None) for n in _solver_jobs(load(sub))]
    if st["stage"] in ("solve", "check") and not _checked(st):
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
    import blind

    st = load(sub)
    pack = json.loads(pack_path(sub).read_text())
    items = {it["id"]: it for it in pack.get("items", [])}
    stripped = {q["id"]: q for q in blind.strip(pack)}
    out = {"sub": sub, "additions": str((WORK / f"{sub}.additions.md").relative_to(ROOT)), "disputes": [],
           "findings": [f for f in st["findings"] if f["status"] == "open"]}
    for d in st["disputes"]:
        if d["status"] == "open":
            it = items.get(d["id"], {})
            out["disputes"].append({**d, "question": stripped.get(d["id"], {}), "explanation": it.get("explanation"),
                                    "template": it.get("template")})
    print(json.dumps(out, ensure_ascii=False, indent=1))


def cmd_resolve(sub: str, ref: str, verdict: str, instruction: str = "") -> None:
    if verdict not in ("keep", "fix"):
        raise SystemExit(f"{sub}: the verdict is keep or fix, not {verdict!r}")
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
    g, _ = fd.settle_glyphs(sub, gates, chapter)
    with chapter(sub) as st:
        st["gates"] = g
        open_ = [d["id"] for d in st["disputes"] if d["status"] == "open"] + \
                [f["ref"] for f in st["findings"] if f["status"] == "open"] + \
                [f["ref"] for f in st["fixes"] if f["status"] == "open"]
        stage = st["stage"]
        ready = g["ok"] and not open_ and (stage == "sign" or (stage == "check" and bool(st.get("checked"))))
        if ready:
            with fd.notes() as n:
                st["same_family"] = bool(n.get("only")) and n.get("only") == maker_of(st)
            st["last_additions"] = counts(additions(sub))
            st["refined"] = st.get("refined", 0) + 1
            st["last_refined"] = now()
            move(st, "ready", "refined: " + ", ".join(f"{v} {k}" for k, v in st["last_additions"].items() if v)
                 + (" (checked only by its own family)" if st["same_family"] else ""))
    if not ready:
        raise SystemExit(f"{sub}: not ready (stage {stage}, gates {g}, open {open_})")
    release(sub)
    fd.speech_after_sign(sub, state=chapter, logs=LOGS)  # new audio for the additions, in the background


def chapter_paths(sub: str) -> list[str]:
    pack = json.loads(pack_path(sub).read_text())
    found = [pack_path(sub), note_path(pack), STATE / f"{sub}.json", ROOT / "build/work/mcq/overrides.json",
             ROOT / "build/work/teach" / f"{sub}.json", plan_path(sub), WORK / f"{sub}.additions.md"]
    found += list((ROOT / "build/out/Assets").glob(f"*/{sub}-*"))
    return [str(p.relative_to(ROOT)) for p in found if p.is_file()]


def release(sub: str) -> None:
    """Publish into the vault and commit the chapter's files ("refine(<sub>): …"), as the foundry's sign does."""
    cfg = config()
    if cfg.get("publish_on_sign", True) and os.environ.get("FOUNDRY_PUBLISH", "1") == "1":
        vault = os.environ.get("STEM_TUTOR_VAULT")
        r = subprocess.run([PY, str(REPO / "build/publish.py"), *(["--vault", vault] if vault else [])], cwd=REPO,
                           capture_output=True, text=True)
        print(f"{sub}: " + (f"published into the vault {r.stdout.strip()[-120:]}" if r.returncode == 0
                            else f"PUBLISH FAILED, run build/publish.py: {r.stderr.strip()[-300:]}"))
    if cfg.get("commit_on_sign", True) and os.environ.get("FOUNDRY_COMMIT", "1") == "1":
        paths = chapter_paths(sub)
        ignored = subprocess.run(["git", "-C", str(ROOT), "check-ignore", "-z", "--stdin"], input="\0".join(paths),
                                 capture_output=True, text=True).stdout.split("\0")
        paths = [p for p in paths if p not in ignored]
        a = load(sub).get("last_additions", {})
        what = ", ".join(f"{v} {k.replace('_', ' ')}" for k, v in a.items() if v) or "additions"
        subprocess.run(["git", "-C", str(ROOT), "add", "--", *paths], capture_output=True)
        r = subprocess.run(["git", "-C", str(ROOT), "commit", "-q", "-m",
                            f"refine({sub}): {what}\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>",
                            "--", *paths], capture_output=True, text=True)
        print(f"{sub}: " + ("committed" if r.returncode == 0 else f"commit skipped: {(r.stdout + r.stderr).strip()[-160:]}"))
    fd.notify(f"{sub} has been refined: the additions are in your vault")
    print(f"{sub}: ready")


def cmd_status(sub: str) -> None:
    print(json.dumps(load(sub), ensure_ascii=False, indent=1))


# ---------------- workers ----------------
def role_prompt(role: str, sub: str, shard: int | None = None) -> str:
    st = load(sub)
    lines = [f"You are the refine {role} for chapter {sub}. Working directory: {REPO}.",
             f"Read refine/roles/{role}.md and follow it exactly."]
    if role in ("solver", "tiebreak"):  # blind: the questions file only, never a path to the keys
        re_ = _pfx(st) if role == "solver" else PFX
        part = f".part{shard}" if shard else ""
        lines.append(f"Questions: build/work/blind/{sub}.{re_}questions{part}.json. Write your answers to "
                     f"build/work/blind/{sub}.{re_ + 'answers' + part if role == 'solver' else PFX + 'tiebreak'}.json.")
    else:
        pack = json.loads(pack_path(sub).read_text()) if pack_path(sub).exists() else {}
        lines.append(f"Chapter files: pack {pack_path(sub).relative_to(ROOT)}, note build/out/notes/{pack.get('note', '?')}, "
                     f"bundle build/work/bundles/{sub}.md.")
    if role == "scout":
        lines.append(f"Write the plan to {plan_path(sub).relative_to(ROOT)}.")
    if role in ("refiner", "fixer"):
        lines.append(f"Plan: {plan_path(sub).relative_to(ROOT)}. New question ids continue {sub}-r01, {sub}-r02, … "
                     f"after the highest -r id already in the pack.")
    if role == "checker":
        lines.append(f"What was added: {(WORK / f'{sub}.additions.md').relative_to(ROOT)}. Write findings to "
                     f"{(WORK / f'{sub}.check.json').relative_to(ROOT)}.")
    if role == "tiebreak":
        lines.append("Disputed question ids: " + ", ".join(d["id"] for d in st["disputes"] if d["status"] == "open"))
    if role == "fixer":
        lines.append("Fixes to make (from the manager):\n" + "\n".join(
            f"- {f['ref']}: {f['instruction']}" for f in st["fixes"] if f["status"] == "open"))
    if role in ("fixer", "refiner") and st.get("gates") and not st["gates"].get("ok"):
        lines.append("Gate failures to clear (no-loss ones mean: put the original back exactly): "
                     + "; ".join(st["gates"].get("first", [])))
    if role == "adjudicator":
        lines.append(f"Open items: run `.venv/bin/python refine/refine.py packet {sub}`.")
    return "\n".join(lines)


def _expects(st: dict, role: str, shard: int | None) -> str | None:
    sub = st["sub"]
    if role == "solver":
        return f"build/work/blind/{sub}.{_pfx(st)}answers{f'.part{shard}' if shard else ''}.json"
    return {"tiebreak": f"build/work/blind/{sub}.{PFX}tiebreak.json", "checker": f"build/work/refine/{sub}.check.json",
            "scout": f"build/work/refine/{sub}.plan.json"}.get(role)


def worker_command(role: str, provider: str, model: str, effort: str, prompt: str, out: Path) -> list[str]:
    """The headless command line, as the foundry builds it, plus live web search for the roles in `web`."""
    cfg, schema = config(), HERE / "schemas" / f"{role}.json"
    web = role in cfg.get("web", [])
    if provider == "codex":  # `--search` is a top-level Codex flag: it goes before `exec`
        return [fd.CODEX, *(["--search"] if web else []), "exec", "-m", model, "-c", f'model_reasoning_effort="{effort}"',
                "-c", 'approval_policy="never"', "-s", "workspace-write", "-C", str(REPO), "--color", "never",
                *(["--output-schema", str(schema)] if schema.exists() else []), "-o", str(out), prompt]
    tools = "Read,Write,Edit,Bash,Glob,Grep" + (",WebSearch,WebFetch" if web else "")
    return [fd.CLAUDE, "-p", prompt, "--model", model, *(["--effort", effort] if effort else []), *router.LEAN,
            "--tools", tools, "--permission-mode", "acceptEdits",
            "--allowedTools", "Bash(.venv/bin/python *)", *(["WebSearch", "WebFetch"] if web else []),
            *(["--json-schema", schema.read_text()] if schema.exists() else [])]


def cmd_run(role: str, sub: str, on: str | None = None, shard: int | None = None) -> None:
    cfg = config()
    if role not in cfg["ladders"]:
        raise SystemExit(f"{role} is not a refine role (roles: {', '.join(cfg['ladders'])})")
    if on and on not in cfg["ladders"][role]:
        raise SystemExit(f"{on} is not an allowance (allowances: {', '.join(cfg['ladders'][role])})")
    name, st = role + (f"#{shard}" if shard else ""), load(sub)
    if name in _running(st):
        raise SystemExit(f"{sub}: a {name} is already working on this chapter")
    if role == "refiner":
        ensure_snapshot(st)  # before the refiner touches anything
    last = st["jobs"].get(name, {})
    with fd.notes() as n:
        provider = on or router.pick(role, maker_of(st), router.usage(n, fd.CODEX, fd.CLAUDE), cfg, _busy(),
                                     only=n.get("only"))
        failed = last.get("provider") == provider and last.get("ok") is False and not last.get("limit")
        rung = router.rung(n, cfg, role, provider, retry=last.get("rung", 0) if failed else None)
    model, effort = cfg["ladders"][role][provider][rung]
    LOGS.mkdir(parents=True, exist_ok=True)
    stem = f"{sub}.{name.replace('#', '-')}.{datetime.now():%m%d-%H%M%S}"
    log, out, expects = LOGS / f"{stem}.log", LOGS / f"{stem}.out.json", _expects(st, role, shard)
    worker = worker_command(role, provider, model, effort, role_prompt(role, sub, shard), out)
    then = [PY, str(HERE / "refine.py"), "collect", name, sub, str(out)]
    shell = (f"{shlex.join(worker)} < /dev/null > {shlex.quote(str(log))} 2>&1; "
             f"{shlex.join(then)} $? >> {shlex.quote(str(log))} 2>&1")
    proc = subprocess.Popen(["/bin/sh", "-c", shell], cwd=REPO, start_new_session=True, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            env={**os.environ, "FOUNDRY_ROOT": str(ROOT),
                                 "FOUNDRY_EXPECTS": str(ROOT / expects) if expects else "",
                                 "FOUNDRY_NOTIFY": os.environ.get("FOUNDRY_NOTIFY", "1"),
                                 "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1"})
    tier = f"{model}/{effort}" if effort else model
    with chapter(sub) as st:
        if role == "refiner":
            st["maker"] = provider  # the other family blind-solves what this one adds
        st["jobs"][name] = {"pid": proc.pid, "provider": provider, "model": tier, "rung": rung, "started": now(),
                            "log": str(log.relative_to(ROOT)), "out": str(out.relative_to(ROOT)),
                            **({"expects": expects} if expects else {})}
    print(f"{sub}: {name} started on {NAMES[provider]} ({tier}); log {log.relative_to(ROOT)}")


def _accept_plan(st: dict) -> str | None:
    """Read the scout's plan, keep it within the caps; move the chapter on. None when the plan is unreadable."""
    sub = st["sub"]
    try:
        plan = json.loads(plan_path(sub).read_text())
        assert isinstance(plan, dict)
    except (OSError, ValueError, AssertionError):
        return None
    plan, dropped = trim_plan(plan)
    plan_path(sub).write_text(json.dumps(plan, ensure_ascii=False, indent=1))
    st["plan"] = {"improvements": len(plan["improvements"]), "dropped": dropped,
                  "kinds": {k: sum(i["kind"] == k for i in plan["improvements"]) for k in KINDS}}
    if not plan["improvements"]:
        st["last_checked"] = now()
        move(st, "ready", "nothing worth adding: " + str(plan.get("summary", ""))[:120])
    else:
        move(st, "refine", f"plan: {len(plan['improvements'])} improvements" + (f", {len(dropped)} over the caps dropped"
                                                                               if dropped else ""))
    return "ok"


def cmd_collect(name: str, sub: str, out: str, code: str = "0") -> None:
    """Runs after a worker exits: record its report, run the gates, note what the job says about its tier and
    allowance, and move the chapter on."""
    role, exit_code = name.split("#")[0], int(code)
    job = load(sub)["jobs"].get(name, {})
    provider = job.get("provider", "codex")
    report, facts, said = {}, {}, ""
    if out == "-":
        report = {"manual": True}
    elif provider == "claude":
        facts = router.claude_log(ROOT / job["log"]) if job.get("log") else {}
        report = facts.get("report") or {}
    else:
        try:
            said = Path(out).read_text().strip()
            report = json.loads(said)
        except OSError:
            pass
        except ValueError:
            report = {"text": said} if said else {}
        report = report if isinstance(report, dict) else {"text": said}
    try:
        said = (ROOT / job["log"]).read_text(errors="ignore").lower() if job.get("log") else ""
    except OSError:
        said = ""
    limit = bool(facts.get("limit")) or (exit_code != 0 and any(w in said for w in router.LIMIT_WORDS))
    g = fd.settle_glyphs(sub, gates, chapter)[0] if role in ("refiner", "fixer") and exit_code == 0 else None
    wrote = True
    if job.get("expects"):
        f = ROOT / job["expects"]
        wrote = f.exists() and f.stat().st_mtime >= datetime.fromisoformat(job["started"]).timestamp() - 1
    if role == "scout" and wrote:  # the plan must be readable too
        try:
            wrote = isinstance(json.loads(plan_path(sub).read_text()), dict)
        except (OSError, ValueError):
            wrote = False
    ok = exit_code == 0 and bool(report) and wrote and (g is None or g["ok"])
    if out != "-":
        with fd.notes() as n:
            codex = provider == "codex" and limit
            router.record(n, config(), role, provider, job.get("rung", 0), ok=ok, limit=limit,
                          cost=facts.get("cost", 0.0), windows=router.codex_usage(fd.CODEX) if codex else facts.get("windows"),
                          judge=not (role == "solver" and ok), until=router.reset_from_message(said) if codex else None)
    if role not in ("solver", "checker"):
        fd.notify(f"{sub}: refine {role} " + ("finished" if exit_code == 0 and report else "failed")
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
        elif role == "scout" and st["stage"] == "plan":
            _accept_plan(st)
        elif role == "refiner" and g["ok"]:
            write_additions(sub)
            move(st, "solve", "refined: " + ", ".join(f"{v} {k}" for k, v in counts(additions(sub)).items() if v))
        elif role == "fixer" and g["ok"]:
            for f in st["fixes"]:
                f["status"] = "done"
            write_additions(sub)
            ids = {it["id"] for it in json.loads(pack_path(sub).read_text()).get("items", [])}
            changed = any(f["ref"] in ids or f["ref"].endswith((".faded", ".discover")) for f in st["fixes"])
            move(st, "recheck" if changed else "sign", f"fixed; {len(st['fixes'])} fixes applied")
        elif g is not None:
            st["history"].append({"t": now(), "from": st["stage"], "to": st["stage"],
                                  "note": f"{role} finished but gates are not clean: {g.get('first', [])[:2]}"})


# ---------------- views ----------------
def coverage() -> dict:
    """Which chapters were refined, when and how much; which built chapters still lack the diagrams the hints suggest."""
    import diagram_hints
    refined = {st["sub"]: {"passes": st.get("refined", 0), "last": st.get("last_refined"), "stage": st["stage"],
                           "added": st.get("last_additions", {})} for st in chapters()}
    bare = []
    for g in sorted(fd.SPECS.glob("*/graph.json")):
        graph = json.loads(g.read_text())
        for s in graph["subtopics"]:
            pk = pack_path(s["id"])
            if pk.exists() and diagram_hints.suggest([k for k in graph["kcs"] if k["subtopic"] == s["id"]]):
                if not json.loads(pk.read_text()).get("diagrams"):
                    bare.append(s["id"])
    signed = signed_chapters()
    import glyphs
    wobbly = []  # chapters whose stored pack or note still has an unsafe Unicode sub/superscript (build/glyphs.py repairs)
    for s in dict.fromkeys(signed + list(refined)):
        pk = pack_path(s)
        if pk.exists():
            pack = json.loads(pk.read_text())
            note = note_path(pack)
            if glyphs.data_problems(pack) or (note.is_file() and glyphs.problems(note.read_text(encoding="utf-8"))):
                wobbly.append(s)
    return {"speech_gaps": fd.pregen.gaps_report(), "refined": refined, "never": [s for s in signed if s not in refined], "no_diagram": sorted(set(bare), key=fd._natural),
            "glyphs": sorted(wobbly, key=fd._natural),
            "given_up": {st["sub"]: st["abandoned"]["why"] for st in chapters() if st.get("abandoned")}}


def cmd_coverage(args: list[str]) -> None:
    c = coverage()
    if "--json" in args:
        print(json.dumps(c, ensure_ascii=False, indent=1))
        return
    print(f"{'CHAPTER':<11} {'STAGE':<11} {'REFINED':<8} {'LAST':<11} ADDED LAST TIME")
    for sub, r in c["refined"].items():
        added = ", ".join(f"{v} {k.replace('_', ' ')}" for k, v in r["added"].items() if v) or "-"
        print(f"{sub:<11} {r['stage']:<11} {r['passes']:<8} {_short_date(r['last']):<11} {added}")
    print(f"\nSigned chapters never refined ({len(c['never'])}): {' '.join(c['never'][:40])}"
          + (" …" if len(c["never"]) > 40 else ""))
    if c["given_up"]:
        print(f"\nPasses given up after {MAX_UNCLEAN} red attempts (their additions were dropped; the chapter is as it was):")
        for sub, why in c["given_up"].items():
            print(f"  {sub}: {why[:150]}")
    if c["glyphs"]:
        print(f"\nChapters with Unicode sub/superscript letters that wobble in the terminal ({len(c['glyphs'])}): "
              f"{' '.join(c['glyphs'])}  (repair: .venv/bin/python build/glyphs.py --write)")
    fd.pregen.print_gaps()
    if c["no_diagram"]:
        print(f"\nBuilt chapters with points a figure shows and no diagram yet ({len(c['no_diagram'])}): "
              f"{' '.join(c['no_diagram'])}")


def watch_text() -> str:
    out = [f"STEM Tutor refine · {datetime.now():%H:%M:%S}", "", *fd.usage_lines(), ""]
    rows = chapters()
    for st in rows:
        if st["stage"] == "ready":
            continue
        workers = []
        for name, j in st["jobs"].items():
            if not j.get("finished") and _alive(j.get("pid")):
                workers.append(f"{NAMES[j.get('provider', 'codex')]} {name} ({j['model']}) {fd._ago(j['started'])}: "
                               f"{fd._last_line(ROOT / j['log'])}")
        out.append(f"{st['sub']:<11} {st['stage']:<11} " + (" · ".join(workers) if workers else "idle"))
    recent = sorted(((h["t"], st["sub"], h["note"]) for st in rows for h in st["history"]), reverse=True)[:5]
    if recent:
        out += ["", "Recent:"] + [f"  {t[11:16]} {sub}: {note}" for t, sub, note in recent]
    return "\n".join(out)


def cmd_watch(every: float = 5) -> None:
    try:
        while True:
            print("\033[2J\033[H" + watch_text(), flush=True)
            time.sleep(every)
    except KeyboardInterrupt:
        pass


def cmd_queue(role: str, subs: list[str], wait: int = 30, tries: int = 480) -> None:
    for sub in subs:
        cmd_add([sub])
        for _ in range(tries):
            try:
                cmd_run(role, sub)
                break
            except router.Wait:
                time.sleep(wait)
            except SystemExit as e:
                print(f"{sub}: skipped ({e})")
                break


def cmd_wait(timeout: float = 540, every: float = 5) -> None:
    end = time.time() + timeout
    while (busy := [f"{st['sub']} {r}" for st in chapters() for r in _running(st)]):
        if time.time() >= end:
            print("still running: " + ", ".join(busy))
            return
        time.sleep(every)
    print("no refine worker is running")


def cmd_install_skill() -> None:
    """Install /refine for every Claude Code session on this Mac (writes ~/.claude/skills/refine/SKILL.md)."""
    dest = Path.home() / ".claude/skills/refine/SKILL.md"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text((HERE / "skill/SKILL.md").read_text().replace("{REPO}", str(REPO)))
    print(f"installed {dest}")


def main(argv: list[str]) -> None:
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return
    cmd, rest = argv[0], argv[1:]
    simple = {"board": cmd_board, "next": cmd_next, "usage": fd.cmd_usage, "install-skill": cmd_install_skill}
    one = {"compare": cmd_compare, "packet": cmd_packet, "gates": cmd_gates, "sign": cmd_sign, "status": cmd_status,
           "dispatch": cmd_dispatch, "escalate": lambda s: cmd_run("adjudicator", s)}
    if cmd in simple:
        simple[cmd]()
    elif cmd in one:
        one[cmd](rest[0])
    elif cmd == "add":
        cmd_add(rest)
    elif cmd == "step":
        cmd_step(rest)
    elif cmd == "only":
        fd.cmd_only(rest)
    elif cmd == "strip":
        cmd_strip(rest[0], "--changed" in rest)
    elif cmd == "resolve":
        cmd_resolve(rest[0], rest[1], rest[2], " ".join(rest[3:]))
    elif cmd == "additions":
        print(write_additions(rest[0]).read_text())
    elif cmd == "run":
        cmd_run(rest[0], rest[1], on=rest[rest.index("--on") + 1] if "--on" in rest else None)
    elif cmd == "queue":
        cmd_queue(rest[0], rest[1:])
    elif cmd == "wait":
        cmd_wait(*(float(x) for x in rest[:1]))
    elif cmd == "coverage":
        cmd_coverage(rest)
    elif cmd == "tts":
        if fd.pregen.cli(rest):
            sys.exit(1)
    elif cmd == "collect":
        cmd_collect(*rest)
    elif cmd == "watch":
        cmd_watch(float(rest[0]) if rest else 5)
    else:
        raise SystemExit(f"unknown command {cmd!r}\n{__doc__}")


if __name__ == "__main__":
    main(sys.argv[1:])
