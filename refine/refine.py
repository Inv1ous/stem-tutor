#!/usr/bin/env python3
"""The refine system: the content foundry's twin that improves chapters already signed, without remaking them.

Same mechanics as foundry/foundry.py (state files, router, headless workers on the Claude and Codex allowances, blind
solve by the other family, tiebreak, adjudicator, fixer, sign = publish + commit), with shared worker lifecycle and
locations owned by tutor_workers. Foundry still supplies its content gates and allowance routing. What differs is
the use: a scout plans a few additions, a refiner makes them by appending only, and
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
  refine.py review-corrections <sub> --reviewer NAME --finding TEXT   bind an independent review of the proposed
                                          corrections (build/work/refine/<sub>.corrections.json) to this candidate
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
import hashlib
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
sys.path.insert(0, str(REPO / "src"))
from tutor_workers import lifecycle, candidates, reliability
from tutor_workers.locations import WorkerLocations, chapter_pack, spec_of

sys.path.insert(0, str(REPO / "foundry"))
import foundry as fd  # noqa: E402  (also puts build/, the tutor scripts and the router on the path)
import router  # noqa: E402
import baseline  # noqa: E402  (pre-pass snapshots and their history)
from router import NAMES  # noqa: E402

LOCATIONS = WorkerLocations.from_environment(REPO)
ROOT = LOCATIONS.data_root
HERE = REPO / "refine"
STATE, LOGS = LOCATIONS.state("refine"), LOCATIONS.logs("refine")
WORK, BLIND = LOCATIONS.work("refine"), LOCATIONS.blind
PACKS, SPECS, NOTES = LOCATIONS.packs, LOCATIONS.specs, LOCATIONS.notes
HOLD, FOUNDRY_STATE = PACKS / "HOLD.json", LOCATIONS.state("foundry")
PY = LOCATIONS.python
PFX = "refine."  # blind files of a refine pass never clash with the foundry's

STAGE_ROLE = {"plan": "scout", "refine": "refiner", "solve": "solver", "tiebreak": "tiebreak", "check": "checker",
              "adjudicate": "manager", "fix": "fixer", "recheck": "solver", "sign": "manager"}
KINDS = ("diagram", "figure", "questions", "clarification", "feature", "source_gap")
NEW_ID = re.compile(r"-r\d{2,}$")

def now() -> str:
    return lifecycle.timestamp()


def move(st: dict, stage: str, note: str = "") -> None:
    lifecycle.transition(st, stage, note, at=now())


def pack_path(sub: str) -> Path:
    return Path(candidates.state_paths(STATE, sub).get("candidate_pack", chapter_pack(PACKS, sub)))


def _running(st: dict) -> list[str]:
    return lifecycle.running_jobs(st, is_alive=_alive)


def _done(st: dict, name: str) -> bool:
    if name in ('wsolver', 'wreviewer'):
        return _written_done(st, name)
    return lifecycle.job_completed(st, name, ROOT)


def _since(st: dict) -> float:
    return lifecycle.stage_started(st)


def _tiebroken(st: dict) -> bool:
    return lifecycle.tiebreak_completed(st)


def _alive(pid: int | None) -> bool:
    return lifecycle.process_alive(pid)


def config() -> dict:
    return json.loads((HERE / "config.json").read_text())


def plan_path(sub: str) -> Path:
    return WORK / f"{sub}.plan.json"


def snap_path(sub: str) -> Path:
    return WORK / f"{sub}.snapshot.json"


def note_path(pack: dict) -> Path:
    st = candidates.state_paths(STATE, pack.get("subtopic", ""))
    return Path(st.get("candidate_note", NOTES / pack.get("note", "")))


def ensure_candidate(sub: str, *, fresh: bool = False) -> None:
    st = load(sub)
    pack_file = pack_path(sub)
    pack = json.loads(pack_file.read_text())
    paths = (candidates.prepare(ROOT, "refine", sub, pack_file, note_path(pack),
                                force=fresh and bool(st.get("candidate_pack")))
             if fresh or not st.get('candidate_pack') else {})
    if fresh or not st.get("candidate_teach") or not Path(st['candidate_teach']).is_file():
        teach = candidates.prepare_teach(ROOT, "refine", sub, ROOT / "build/work/teach" / f"{sub}.json",
                                         cards=pack.get('teach', {}))
        paths = {**(paths or {}), **teach}
    if paths:
        with chapter(sub) as current:
            current.update(paths)


def teach_path(sub: str) -> Path:
    """The teaching-card draft this pass edits: an editable Work copy when the shared draft is a Library adapter."""
    return Path(candidates.state_paths(STATE, sub).get("candidate_teach", ROOT / "build/work/teach" / f"{sub}.json"))


def remaining(sub: str, *, start: bool = False) -> float | None:
    left = lifecycle.course_remaining(STATE, sub, 3600, start=start)
    if left is not None and left <= 0:
        raise lifecycle.DeadlineReached(f"{sub}: course deadline reached; incomplete work remains pending")
    return left


def repair_glyphs(sub: str) -> int:
    import glyphs
    p = pack_path(sub)
    n = glyphs.repair_file(p)
    # Lesson scope promises exact subject-note bytes, even for glyph repairs.
    if load(sub).get("scope", "legacy") != "lessons":
        note = note_path(json.loads(p.read_text()))
        n += glyphs.repair_file(note) if note.is_file() else 0
    return n


def scope_problems(scope: str, before: dict, pack: dict, note: str) -> list[str]:
    if scope != "lessons":
        return []
    problems = []
    if note != before.get("note", ""):
        problems.append("lessons scope: subject note bytes changed")
    if pack.get("items", []) != before["pack"].get("items", []):
        problems.append("lessons scope: unrelated assessment items changed")
    return problems


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


def focused(rows: list[dict], show_all: bool = False) -> list[dict]:
    """The chapters the learner is working on (`focus` in refine/config.json); every chapter when there is no list or
    with --all. Engine state is untouched: this only narrows what `board`, `next` and a bare `step` look at."""
    focus = config().get("focus")
    return rows if show_all or not focus else [st for st in rows if st["sub"] in set(focus)]


def _busy() -> dict[str, list[str]]:
    """Jobs running now on each allowance: the refine system's AND the foundry's, so the two never oversubscribe.
    The foundry's own count already includes refine's (it reads refine/state), so it is used as it is."""
    return fd._busy()


# ---------------- the snapshot and the no-loss gate ----------------
def take_snapshot(sub: str, pass_no: int) -> dict:
    pack = json.loads(pack_path(sub).read_text())
    note = note_path(pack)
    snap = {"pass": pass_no, "taken": now(), "pack": pack,
            "note": note.read_text(encoding="utf-8") if note.is_file() else "",
            "note_bytes_sha256": hashlib.sha256(note.read_bytes() if note.is_file() else b"").hexdigest()}
    WORK.mkdir(parents=True, exist_ok=True)
    snap_path(sub).write_text(json.dumps(snap, ensure_ascii=False))
    return snap


def snapshot(sub: str) -> dict | None:
    try:
        return json.loads(snap_path(sub).read_text())
    except (OSError, ValueError):
        return None


def reviewed_source_baseline(original: dict, current: dict) -> tuple[dict, int]:
    """Apply registered source evidence in memory; never rewrite the snapshot."""
    from tutorlib.asset_library import AssetLibrary
    from tutor_workers.source_repairs import overlay
    explicit = os.environ.get('STEM_TUTOR_VAULT')
    vault = Path(explicit) if explicit else (ROOT.parent / 'STEM Tutor' if ROOT == REPO else ROOT / 'STEM Tutor')
    if not (vault / 'Library/catalog.json').is_file():
        return original, 0
    return overlay(original, current, AssetLibrary(vault))


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
        if key in LISTS or key in ("teach", "guided_forms"):
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
            elif isinstance(v, list) and isinstance(teach[kc][f], list) and teach[kc][f][:len(v)] == v:
                continue  # source-bound existing entries stay exact; appended teaching entries are additions
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
    lesson_display = candidates.state_paths(STATE, sub).get("scope") == "lessons"
    new_card_visuals = (fd._card_display_paths(pack) - fd._card_display_paths(before["pack"])) if lesson_display else set()
    added = new_items(before, pack)
    out += [f"new item {it.get('id')} must be named {sub}-rNN (never reuse or renumber ids)" for it in added
            if not str(it.get("id", "")).startswith(sub + "-r") or not NEW_ID.search(str(it.get("id", "")))]
    old_files = {d.get("file") for d in before["pack"].get("diagrams") or []}
    drawn = [d for d in pack.get("diagrams") or [] if d.get("file") not in old_files]
    requested = {diagram.get("file") for diagram in drawn}
    drawn += [{"file": path} for path in sorted(new_card_visuals) if path.lower().endswith(".svg") and path not in requested]
    if len(added) > caps["questions"]:
        out.append(f"{len(added)} new questions: at most {caps['questions']} in one pass")
    if len(drawn) > caps["diagrams"]:
        out.append(f"{len(drawn)} new diagrams: at most {caps['diagrams']} in one pass")
    for diagram in drawn:
        try:
            catalog = fd._diagram_catalog(ROOT / "build/out/assets")
            rendered = (fd._verified_display_diagram(catalog, diagram.get("file", ""))
                        if lesson_display else
                        fd._catalog_diagram(catalog, diagram.get("file", "")) if catalog is not None else
                        ROOT / "build/out" / diagram.get("file", ""))
            if not rendered.is_file():
                raise ValueError("not rendered")
        except (OSError, ValueError) as exc:
            out.append(f"diagram {diagram.get('file')} is requested but unavailable: {exc}")
    import library
    was = set(library.embeds(before.get("note", "")))
    figs = [e for e in dict.fromkeys(library.embeds(note)) if e not in was]
    figs += [path for path in sorted(new_card_visuals) if Path(path).suffix.lower() in (".png", ".jpg", ".jpeg") and path not in figs]
    if len(figs) > caps.get("figures", 3):
        out.append(f"{len(figs)} new figures: at most {caps.get('figures', 3)} in one pass")
    for figure in figs:
        if lesson_display and figure in new_card_visuals:
            try:
                fd._verified_display_diagram(fd._diagram_catalog(ROOT / "build/out/assets"), figure)
            except (OSError, ValueError) as exc:
                out.append(f"figure {figure} is unavailable for card display: {exc}")
        else:
            if not (library.assets_dir() / figure.removeprefix("Assets/")).is_file():
                out.append(f"figure {figure} is embedded but its file does not exist (make it with build/library.py crop)")
            if not library.sidecar_of(figure).is_file():
                out.append(f"figure {figure} has no provenance sidecar (make it with build/library.py crop or extract)")
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


def _inherited(g: dict, sub: str, before: dict, pack: dict, note: Path, *, lesson_display: bool = False) -> None:
    """What the chapter already had is not the refiner's to fix: it may only add. A link whose title was reworded, or the
    lack of a diagram, was there before the pass (publishing resolves the first; the plan decides the second), so only
    NEW link problems, a requested diagram that is not embedded, and figure problems count in the figures gate."""
    import content_checks
    import library
    if not note.is_file():
        return
    text = note.read_text(encoding="utf-8")
    graph = json.loads((SPECS / spec_of(sub) / "graph.json").read_text())
    old_links = set(fd.link_problems(before.get("note", "")))
    figs = [x for x in fd.link_problems(text) if x not in old_links] + \
           [x for x in fd.diagram_problems(pack, graph, text, lesson_display=lesson_display) if not x.startswith("no diagram")] + \
           library.figure_problems(text, sub) + content_checks.letter_problems(pack) + content_checks.latex_problems(pack) + content_checks.debris_problems(pack) + content_checks.stacked_problems(pack) + content_checks.precision_problems(pack) + content_checks.id_problems(pack) + content_checks.chemical_spacing_problems(pack)
    first = [x for x in g.get("first", []) if not x.startswith("figures ")] + [f"figures {x}"[:200] for x in figs[:6]]
    g.update(figures=len(figs), first=first)
    g["ok"] = not (g.get("validator") or g.get("lint") or g.get("syllabus") or g.get("glyphs") or g.get("guided") or figs)
    if not first:
        g.pop("first", None)


def _written_diagram_resolver():
    """Fresh, lazy catalog for one extraction; no catalog survives the call."""
    assets = ROOT / 'build/out/assets'
    loaded, catalog, failure = False, None, None
    def resolve(reference: str) -> Path:
        nonlocal loaded, catalog, failure
        if not loaded:
            loaded = True
            try:
                catalog = fd._diagram_catalog(assets)
            except (OSError, ValueError, KeyError) as exc:
                failure = exc
        if failure is not None:
            raise failure
        if catalog is not None:
            return fd._catalog_diagram(catalog, reference)
        # Disposable legacy fixtures have an explicit assets root, never a Library alias.
        if (not isinstance(reference, str) or not reference.startswith('Assets/')
                or '..' in Path(reference).parts or '\\' in reference):
            raise ValueError('invalid or unregistered review diagram')
        return assets / reference.removeprefix('Assets/')
    return resolve


def _written_diagram(reference: str) -> Path:
    """Compatibility single resolution; inventories use a fresh shared resolver."""
    return _written_diagram_resolver()(reference)


def written_review_problems(sub: str, pack: dict) -> list[str]:
    """Require current review records for guided written checks; hashes do not establish independence."""
    import written_review
    try:
        items = written_review.pack_review_items(pack, diagram_resolver=_written_diagram_resolver())
    except (ValueError, TypeError) as exc:
        return [f'invalid written review inventory: {exc}']
    if not items:
        return []  # legacy cards contain no written form checks
    try:
        reviews = json.loads((WORK / f'{sub}.written-review.json').read_text())
    except (OSError, ValueError):
        return [f'{len(items)} written checks need review records']
    return _written_record_problems(items, reviews)


def written_items(pack: dict) -> list[dict]:
    import written_review
    return written_review.pack_review_items(pack, diagram_resolver=_written_diagram_resolver())


def _written_file(sub: str, kind: str) -> Path:
    return WORK / f"{sub}.written-{kind}.json"


def _read(path: Path, default):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return default


def pending_written(sub: str, pack: dict) -> list[dict]:
    """Checks without accepted evidence for their exact current content."""
    records = _read(_written_file(sub, "review"), {})
    records = records if isinstance(records, dict) else {}
    return [it for it in written_items(pack)
            if _written_record_problems([it], {it["id"]: records[it["id"]]} if it["id"] in records else {})]


def _written_questions(st: dict) -> Path:
    return BLIND / f"{st['sub']}.{_pfx(st)}written.questions.json"


def _written_answers(st: dict) -> Path:
    return BLIND / f"{st['sub']}.{_pfx(st)}written.answers.json"


def _written_hash(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def _written_evidence_path(reference: str) -> Path:
    if (not isinstance(reference, str) or not reference or Path(reference).is_absolute()
            or '..' in Path(reference).parts):
        raise ValueError('invalid written evidence path')
    path = ROOT / reference
    if not any(path.resolve().is_relative_to(root.resolve()) for root in (WORK, BLIND)):
        raise ValueError('written evidence is outside the worker evidence directories')
    return path


def _written_proof_item(ident: str, record: dict) -> dict:
    import written_review
    return written_review.proof_item(ident, record, root=ROOT, work=WORK, blind=BLIND)


def _written_record_problems(items: list[dict], records) -> list[str]:
    import written_review
    return written_review.independent_record_problems(items, records, root=ROOT, work=WORK, blind=BLIND)


def _archive_written_batch(st: dict) -> Path | None:
    """Preserve every previous evidence artifact before a new strip replaces it."""
    import shutil
    sub = st['sub']
    files = [_written_file(sub, kind) for kind in ('batch', 'review', 'items', 'solutions', 'decisions')]
    for prefix in (PFX, PFX + 'recheck.'):
        files.extend(BLIND / f'{sub}.{prefix}written.{kind}.json' for kind in ('questions', 'answers'))
    files = [path for path in files if path.is_file()]
    if not files:
        return None
    history = WORK / 'written-history' / sub / str(time.time_ns())
    history.mkdir(parents=True)
    manifest = []
    for path in files:
        shutil.copy2(path, history / path.name)
        manifest.append({'source': os.path.relpath(path, ROOT), 'file': path.name,
                         'sha256': _written_hash(history / path.name)})
    (history / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=1) + "\n")
    # Retarget only verified bindings after all immutable copies exist. Previously
    # archived proofs keep their existing references when another item is rechecked.
    records = _read(_written_file(sub, 'review'), {})
    changed = False
    if isinstance(records, dict):
        destinations = {os.path.relpath(path, ROOT): os.path.relpath(history / path.name, ROOT) for path in files}
        for ident, record in records.items():
            if not isinstance(record, dict):
                continue
            try:
                item = _written_proof_item(ident, record)
                if _written_record_problems([item], {ident: record}):
                    continue
            except (OSError, ValueError, TypeError, KeyError):
                continue
            for entry in record['evidence']['files'].values():
                if entry['path'] in destinations:
                    entry['path'] = destinations[entry['path']]
                    changed = True
        if changed:
            _written_file(sub, 'review').write_text(json.dumps(records, ensure_ascii=False, indent=1) + "\n")
    return history


def _start_written_batch(st: dict, pack: dict) -> None:
    """Snapshot what was stripped, before either independent worker sees it."""
    items = pending_written(st['sub'], pack)
    questions = [{"id": it["id"], "stem": it["stem"]} for it in items]
    if _read(_written_questions(st), None) != questions:
        raise ValueError("written questions do not match the current inventory")
    batch = {"id": str(time.time_ns()), "stage": _since(st), "pass": _since_pass(st),
             "prefix": _pfx(st), "items": items, "questions_hash": _written_hash(_written_questions(st))}
    WORK.mkdir(parents=True, exist_ok=True)
    _written_file(st['sub'], 'batch').write_text(json.dumps(batch, ensure_ascii=False, indent=1) + "\n")


def _written_batch(st: dict, pack: dict | None = None) -> dict:
    batch = _read(_written_file(st['sub'], 'batch'), None)
    if (not isinstance(batch, dict) or not isinstance(batch.get('id'), str)
            or batch.get('stage') != _since(st) or batch.get('pass') != _since_pass(st)
            or batch.get('prefix') != _pfx(st) or not isinstance(batch.get('items'), list)
            or not isinstance(batch.get('questions_hash'), str)
            or batch.get('questions_hash') != _written_hash(_written_questions(st))):
        raise ValueError('missing or stale written batch; strip this round again')
    items = batch['items']
    if (any(not isinstance(it, dict) or not isinstance(it.get('id'), str) or not it['id'].strip()
            or not isinstance(it.get('stem'), str) for it in items)
            or len({it['id'] for it in items}) != len(items)
            or _read(_written_questions(st), None) != [{'id': it['id'], 'stem': it['stem']} for it in items]):
        raise ValueError('invalid written batch inventory; strip this round again')
    if pack is not None:
        ids = {it['id'] for it in batch['items']}
        current = [it for it in written_items(pack) if it['id'] in ids]
        if (current != batch['items'] or any(it['id'] not in ids for it in pending_written(st['sub'], pack))):
            raise ValueError('written content changed after the blind batch; strip this round again')
    return batch


def _written_output_valid(st: dict, role: str, batch: dict) -> bool:
    ids = {it['id'] for it in batch['items']}
    path = _written_answers(st) if role == 'wsolver' else _written_file(st['sub'], 'decisions')
    data = _read(path, None)
    if not isinstance(data, dict) or set(data) != ids:
        return False
    if role == 'wsolver':
        return all(isinstance(v, str) and v.strip() for v in data.values())
    return all(isinstance(v, dict) and v.get('verdict') in ('accepted', 'rejected')
               and isinstance(v.get('rationale'), str) and v['rationale'].strip()
               and ('fix' not in v or isinstance(v['fix'], str)) for v in data.values())


def _written_input(st: dict, role: str) -> Path:
    return _written_questions(st) if role == 'wsolver' else _written_file(st['sub'], 'items')


def _written_launch(st: dict, role: str) -> dict:
    """Attach immutable batch/input evidence to a launch; old output cannot count."""
    if role not in ('wsolver', 'wreviewer'):
        return {}
    batch = _written_batch(st, json.loads(pack_path(st['sub']).read_text()))
    if role == 'wreviewer' and (not _written_done(st, 'wsolver') or not batch.get('review_items_hash')
            or batch['review_items_hash'] != _written_hash(_written_input(st, role))):
        raise ValueError('no current blind solution and reviewer inventory')
    output = _written_answers(st) if role == 'wsolver' else _written_file(st['sub'], 'decisions')
    if output.exists():
        output.unlink()
    return {'written_batch': batch['id'], 'written_input_hash': _written_hash(_written_input(st, role))}


def _finish_written_job(st: dict, role: str) -> None:
    if role not in ('wsolver', 'wreviewer'):
        return
    job = st['jobs'].get(role, {})
    try:
        batch = _written_batch(st)
        valid = (job.get('written_batch') == batch['id'] and job.get('written_input_hash')
                 == _written_hash(_written_input(st, role)) and _written_output_valid(st, role, batch))
    except (ValueError, TypeError, KeyError):
        valid = False
    if valid:
        path = _written_answers(st) if role == 'wsolver' else _written_file(st['sub'], 'decisions')
        job['written_output_hash'] = _written_hash(path)
    else:
        job['ok'] = False
        job['written_error'] = 'missing, malformed, or stale written evidence; rerun this worker'


def _written_done(st: dict, role: str) -> bool:
    job = st['jobs'].get(role, {})
    try:
        batch = _written_batch(st)
        output = _written_answers(st) if role == 'wsolver' else _written_file(st['sub'], 'decisions')
        if role == 'wreviewer' and (not _written_done(st, 'wsolver')
                or batch.get('solver_output_hash') != st['jobs']['wsolver'].get('written_output_hash')
                or batch.get('review_items_hash') != _written_hash(_written_input(st, role))):
            return False
        return bool(job.get('ok') is True and lifecycle.job_completed(st, role, ROOT)
                    and job.get('expects') == str(output.relative_to(ROOT))
                    and job.get('written_batch') == batch['id']
                    and job.get('written_input_hash') == _written_hash(_written_input(st, role))
                    and job.get('written_output_hash') and job['written_output_hash'] == _written_hash(output)
                    and _written_output_valid(st, role, batch))
    except (ValueError, TypeError, KeyError):
        return False


def _written_needs_strip(st: dict) -> bool:
    """Old in-flight jobs and content edits require a fresh blind inventory."""
    try:
        pack = json.loads(pack_path(st['sub']).read_text())
        if not pending_written(st['sub'], pack):
            return False
        _written_batch(st, pack)
        return False
    except (OSError, ValueError, TypeError, KeyError):
        return True


def _written_jobs(st: dict) -> list[str]:
    q = _written_questions(st)
    if not q.exists() or q.stat().st_mtime < _since(st) - 1 or not _read(q, []):
        return []
    return [] if _written_done(st, 'wreviewer') else ['wreviewer'] if _written_done(st, 'wsolver') else ['wsolver']


def _identity(st: dict, name: str) -> str:
    job = st["jobs"].get(name, {})
    return f"{job.get('provider', '?')}:{job.get('model', '?')}:{name}"


def write_written_items(sub: str) -> Path:
    """Freeze precisely the solved inventory and solutions supplied to the reviewer."""
    st, pack = load(sub), json.loads(pack_path(sub).read_text())
    batch = _written_batch(st, pack)
    if not _written_done(st, 'wsolver'):
        raise ValueError('no current complete blind written solution')
    solutions = _read(_written_answers(st), None)
    items = [{**it, 'solution': solutions[it['id']]} for it in batch['items']]
    out = _written_file(sub, 'items')
    out.write_text(json.dumps(items, ensure_ascii=False, indent=1))
    _written_file(sub, 'solutions').write_text(json.dumps(solutions, ensure_ascii=False, indent=1))
    batch.update(review_items_hash=_written_hash(out), solutions=solutions,
                 solver_output_hash=st['jobs']['wsolver']['written_output_hash'])
    _written_file(sub, 'batch').write_text(json.dumps(batch, ensure_ascii=False, indent=1) + "\n")
    return out


def bind_written(sub: str, pack: dict, ident: str, decision: dict, solver: str, reviewer: str) -> str | None:
    """Bind actual current independent outputs; a manager rationale is not a review."""
    import written_review
    st = load(sub)
    try:
        batch = _written_batch(st, pack)
        if not _written_done(st, 'wsolver') or not _written_done(st, 'wreviewer'):
            return 'no current independent written worker evidence'
        items = _read(_written_file(sub, 'items'), None)
        expected = [{**it, 'solution': batch.get('solutions', {}).get(it['id'])} for it in batch['items']]
        if (items != expected or batch.get('review_items_hash') != _written_hash(_written_file(sub, 'items'))
                or batch.get('solver_output_hash') != st['jobs']['wsolver'].get('written_output_hash')):
            return 'reviewed written inventory or solutions changed'
        decisions = _read(_written_file(sub, 'decisions'), {})
        if (decision != decisions.get(ident) or solver != _identity(st, 'wsolver')
                or reviewer != _identity(st, 'wreviewer')):
            return 'acceptance requires the independent reviewer decision and identities'
        item = next((it for it in batch['items'] if it['id'] == ident), None)
        if item is None:
            return 'not a reviewed written check'
        record = written_review.build_records([item], {ident: batch['solutions'][ident]}, {ident: decision},
                                             solver=solver, reviewer=reviewer)
        paths = {'batch': _written_file(sub, 'batch'), 'questions': _written_questions(st),
                 'answers': _written_answers(st), 'items': _written_file(sub, 'items'),
                 'decisions': _written_file(sub, 'decisions')}
        record[ident]['evidence'] = {'version': 1, 'batch_id': batch['id'], 'solver': solver, 'reviewer': reviewer,
                                    'files': {kind: {'path': os.path.relpath(path, ROOT), 'sha256': _written_hash(path)}
                                              for kind, path in paths.items()}}
    except (ValueError, TypeError, KeyError) as exc:
        return str(exc)
    records = _read(_written_file(sub, 'review'), {})
    records = records if isinstance(records, dict) else {}
    records.update(record)
    _written_file(sub, 'review').write_text(json.dumps(records, ensure_ascii=False, indent=1) + "\n")
    return None


def _ingest_written(st: dict, pack: dict) -> str:
    """Only exact current independent evidence can become accepted review records."""
    try:
        _written_batch(st, pack)
    except (ValueError, TypeError, KeyError) as exc:
        return '; written evidence stale: ' + str(exc)
    if not _written_done(st, 'wsolver') or not _written_done(st, 'wreviewer'):
        return ''
    decisions = _read(_written_file(st['sub'], 'decisions'), {})
    accepted = rejected = 0
    for item in pending_written(st['sub'], pack):
        d = decisions[item['id']]
        why = bind_written(st['sub'], pack, item['id'], d, _identity(st, 'wsolver'), _identity(st, 'wreviewer')) \
            if d['verdict'] == 'accepted' else d['rationale']
        if why is None:
            accepted += 1
            for finding in st['findings']:
                if finding.get('ref') == item['id'] and finding.get('rule') == 'written review rejected':
                    finding['status'] = 'closed'
                    finding['resolution'] = 'accepted by a fresh independent written review'
            continue
        rejected += 1
        st['findings'] = [f for f in st['findings'] if f['ref'] != item['id']] + [{
            'ref': item['id'], 'rule': 'written review rejected', 'evidence': str(why)[:600],
            'suggested': str(d.get('fix', ''))[:600], 'status': 'open'}]
    return f'; written checks {accepted} accepted, {rejected} rejected'


def corrections_file(sub: str) -> Path:
    return WORK / f"{sub}.corrections.json"


def correction_review_file(sub: str) -> Path:
    return WORK / f"{sub}.correction-review.json"


def archive_stale_corrections(sub: str) -> list[str]:
    """A correction proposal and its review belong to the pass that wrote them: one from an earlier pass is bound to
    that pass's baseline, can never match this one, and would fail every gate. Keep each under a dated name (it stays
    evidence for the learner and the foundry) and apply it to no later pass."""
    with chapter(sub) as st:
        since, moved = _since_pass(st), []
        for f in (corrections_file(sub), correction_review_file(sub)):
            if f.exists() and f.stat().st_mtime < since - 1:
                dest = f.with_name(f"{f.stem}.before-pass{st.get('pass', 1)}-"
                                   f"{datetime.fromtimestamp(f.stat().st_mtime):%Y%m%d-%H%M%S}-{time.time_ns()}.json")
                f.rename(dest)
                moved.append(dest.name)
        if moved:
            st["history"].append({"t": now(), "from": st["stage"], "to": st["stage"],
                                  "note": "earlier-pass correction proposals kept aside, not applied: " + ", ".join(moved)})
    return moved


def after_corrections(sub: str, before: dict, pack: dict, note_text: str, lost: list[str]) -> tuple[list[str], int]:
    """No-loss findings that remain once reviewed corrections are taken into account: (findings, how many were
    explained). The snapshot and `no_loss` are untouched. With a proposal on file (what changes, from what, to what,
    with the PDF pages that support it) and a review bound to this exact candidate and those PDF bytes, a finding is
    dropped only if it is one of the proposed changes; every other loss still fails. A proposal that is stale, was not
    reviewed, or whose replacement is not in the candidate adds a finding and explains nothing."""
    if not corrections_file(sub).exists():
        return lost, 0
    import correction_review as cr
    try:
        proposal = json.loads(corrections_file(sub).read_text(encoding="utf-8"))
        evidence = json.loads(correction_review_file(sub).read_text(encoding="utf-8"))
        audit = cr.assess_source_bound_candidate(before["pack"], before.get("note", ""), proposal, pack, note_text,
                                                  evidence, no_loss, REPO)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return lost + [f"proposed corrections not accepted: {exc}"], 0
    return audit["outside_proposal"], len(lost) - len(audit["outside_proposal"])


def bind_correction_review(sub: str, reviewer: str, finding: str) -> dict:
    """Write the review record for the chapter's proposal, bound to the candidate and the cited PDFs as they are now.
    Run it only after someone other than the author has checked each correction against its source; the record says who
    and what they found, and goes stale the moment the candidate or a PDF changes. It authenticates nobody."""
    import correction_review as cr
    before, pack = snapshot(sub), json.loads(pack_path(sub).read_text())
    note = note_path(pack).read_text(encoding="utf-8") if note_path(pack).is_file() else ""
    proposal = json.loads(corrections_file(sub).read_text(encoding="utf-8"))
    record = {"fingerprints": cr.review_fingerprints(before["pack"], before.get("note", ""), proposal, pack, note),
              "sources": cr.source_fingerprints(proposal, REPO), "reviewer": reviewer, "finding": finding,
              "verdict": "accepted"}
    correction_review_file(sub).write_text(json.dumps(record, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return record


def gates(sub: str, *, defer_written: bool = False) -> dict:
    """The foundry's gates (validator, note lint, syllabus, figures: links + diagrams), then no-loss and the plan.
    `defer_written`: after a refiner or fixer, written checks cannot have review records yet (the blind written solve
    and its review come next), so missing records are counted but do not fail the gates; signing never defers."""
    state = load(sub) if (STATE / f"{sub}.json").exists() else {}
    options = {"lesson_display": True} if state.get("scope") == "lessons" else {}
    if state.get("candidate_pack"):
        options.update(candidate_pack=pack_path(sub), candidate_note=note_path(json.loads(pack_path(sub).read_text())))
    if state.get("candidate_teach"):
        options.update(candidate_teach=teach_path(sub))
    if defer_written:
        options.update(defer_written=True)
    g = fd.gates(sub, **options)
    before = snapshot(sub)
    if not pack_path(sub).exists():
        return {**g, "no_loss": 0, "planned": 0}
    pack = json.loads(pack_path(sub).read_text())
    if pack.get("subtopic") != sub:  # a pack written over another subtopic's file (found in the Haiku batch)
        g["ok"] = False
        g["first"] = [f"identity: the pack for {sub} says subtopic {pack.get('subtopic')!r}"] + g.get("first", [])
    if before is not None:
        staged, repaired = reviewed_source_baseline(before['pack'], pack)
        before = {**before, 'pack': staged}
        if repaired:
            g['source_repairs'] = repaired
    written = written_review_problems(sub, pack)
    if before is None:
        if written:
            g['first'] = [f'written review {x}'[:200] for x in written[:6]] + g.get('first', [])
        return {**g, 'no_loss': 0, 'planned': 0, 'written_review': len(written),
                'ok': g['ok'] and (defer_written or not written)}
    note = note_path(pack)
    _inherited(g, sub, before, pack, note, lesson_display=state.get("scope") == "lessons")
    note_text = note.read_text(encoding="utf-8") if note.is_file() else ""
    lost, explained = after_corrections(sub, before, pack, note_text, no_loss(before, pack, note_text))
    lost += scope_problems(state.get("scope", "legacy"), before, pack, note_text)
    if state.get("scope") == "lessons" and before.get("note_bytes_sha256") and (
            hashlib.sha256(note.read_bytes() if note.is_file() else b"").hexdigest() != before["note_bytes_sha256"]):
        lost.append("lessons scope: subject note bytes changed")
    if explained:
        g["corrected"] = explained  # changes to what was there, each proposed with its source and reviewed
    try:
        plan = json.loads(plan_path(sub).read_text())
    except (OSError, ValueError):
        plan = None
    planned = plan_problems(sub, before, pack, plan, note.read_text(encoding="utf-8") if note.is_file() else "")
    g.update(no_loss=len(lost), planned=len(planned), written_review=len(written),
             ok=g["ok"] and not lost and not planned and (defer_written or not written))
    if lost or planned or (written and not defer_written):
        g["first"] = [f"no-loss {x}"[:200] for x in lost[:10]] + [f"plan {x}"[:200] for x in planned[:6]] + \
                     [f"written review {x}"[:200] for x in written[:6]] + \
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
    held = json.loads(HOLD.read_text()) if HOLD.exists() else {}
    out = []
    available = {p.stem for p in PACKS.glob("*/*.json")}
    for path in FOUNDRY_STATE.glob("*.json"):
        state = json.loads(path.read_text())
        if state.get("stage") == "ready" and state.get("candidate_pack"):
            available.add(path.stem)
    for sub in sorted(available):
        if sub in held or not sub[:1].isalnum():
            continue
        f = FOUNDRY_STATE / f"{sub}.json"
        if f.exists() and json.loads(f.read_text()).get("stage") != "ready":
            continue
        out.append(sub)
    return sorted(out, key=fd._natural)


def in_foundry(sub: str) -> str | None:
    """Why the foundry owns this chapter now, or None."""
    held = json.loads(HOLD.read_text()) if HOLD.exists() else {}
    f = FOUNDRY_STATE / f"{sub}.json"
    if f.exists() and (stage := json.loads(f.read_text()).get("stage")) != "ready":
        return f"in the foundry at {stage}"
    if sub in held:
        return f"held: {held[sub]}"
    return None


def _signed_foundry_source(sub: str) -> tuple[Path, Path, str] | None:
    """A signed candidate is a separate source; never fall back to older published bytes."""
    state_file = FOUNDRY_STATE / f"{sub}.json"
    if not state_file.is_file():
        return None
    try:
        state = json.loads(state_file.read_text())
        if state.get("stage") != "ready" or not state.get("candidate_pack"):
            return None
        pack, note = Path(state["candidate_pack"]), Path(state["candidate_note"])
        if not pack.is_file() or not note.is_file():
            raise ValueError("missing signed pack or note")
        signed = state.get("content_sha256")
        if not signed or lifecycle.content_fingerprint(pack, note) != signed:
            raise ValueError("missing or stale signing fingerprint")
        if json.loads(pack.read_text()).get("subtopic") != sub:
            raise ValueError("chapter identity mismatch")
        if any(row.get("status") == "open" for key in ("findings", "fixes", "disputes")
               for row in state.get(key, [])):
            raise ValueError("unresolved review findings")
        current = fd.gates(sub, candidate_pack=pack, candidate_note=note)
        if not current.get("ok"):
            raise ValueError(f"current gates fail: {current.get('first', [])}")
        if lifecycle.content_fingerprint(pack, note) != signed:
            raise ValueError("candidate changed during verification")
        return pack, note, signed
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise SystemExit(f"{sub}: cannot consume signed Foundry candidate: {exc}") from exc


def cmd_add(subs: list[str]) -> None:
    scope = "lessons"
    if "--scope" in subs:
        index = subs.index("--scope")
        scope = subs[index + 1] if len(subs) > index + 1 else ""
        subs = subs[:index] + subs[index + 2:]
    if scope not in ("lessons", "full"):
        raise SystemExit("scope must be lessons or full")
    if "--oldest" in subs:
        subs = [entry["sub"] for entry in preparation_queue()]
    if subs == ["--all"] or "--all" in subs:
        subs = signed_chapters()
    for sub in subs:
        path = STATE / f"{sub}.json"
        previous = load(sub) if path.exists() else None
        source = _signed_foundry_source(sub) if previous is None or previous.get("stage") == "ready" else None
        if source and previous:
            current_hash = lifecycle.content_fingerprint(pack_path(sub), note_path(json.loads(pack_path(sub).read_text())))
            if current_hash == source[2]:
                source = None
            else:
                try:
                    foundry = json.loads((FOUNDRY_STATE / f"{sub}.json").read_text())
                    source_time = datetime.fromisoformat(foundry["prepared_at"])
                    previous_time = datetime.fromisoformat(previous["prepared_at"])
                    if source_time == previous_time:
                        raise ValueError("different signed content at the same time")
                    newer = source_time > previous_time
                except (KeyError, ValueError, TypeError) as exc:
                    raise SystemExit(f"{sub}: ambiguous signed Foundry/Refine ancestry; preserve both candidates: {exc}") from exc
                if not newer:
                    source = None
                elif previous.get("content_sha256") != current_hash:
                    raise SystemExit(f"{sub}: independent or unverified Refine edits conflict with signed Foundry candidate")
        if not source and not pack_path(sub).exists():
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
            if source:
                source_pack, source_note, signed = source
                paths = candidates.prepare(ROOT, "refine", sub, source_pack, source_note, force=True)
                if lifecycle.content_fingerprint(Path(paths["candidate_pack"]), Path(paths["candidate_note"])) != signed:
                    raise SystemExit(f"{sub}: signed Foundry candidate changed while copying")
                with chapter(sub) as st:
                    st.update(paths, foundry_content_sha256=signed)
                    st.pop("candidate_teach", None)
                ensure_candidate(sub)
            else:
                ensure_candidate(sub, fresh=True)
            with chapter(sub) as st:  # a new pass on a chapter refined before
                st["scope"] = scope
                st["pass"] = st.get("pass", 1) + 1
                for k in ("disputes", "findings", "fixes"):
                    st[k] = []
                st.update(jobs={}, gates=None, checked=False, maker=None, plan=None, same_family=False)
                # the baseline is taken now, before anything in this pass is edited; the old one is kept in history
                baseline.begin_pass(sub, snap_path(sub), st["pass"], _rel(pack_path(sub)), pack_path(sub),
                                    note_path(json.loads(pack_path(sub).read_text())))
                move(st, "plan", f"pass {st['pass']}")
            print(f"{sub}: pass {load(sub)['pass']} added at plan")
        else:
            STATE.mkdir(parents=True, exist_ok=True)
            st = {"sub": sub, "scope": scope, "stage": "plan", "pass": 1, "refined": 0, "created": now(), "updated": now(),
                  "history": [], "gates": None, "disputes": [], "findings": [], "fixes": [], "jobs": {}}
            if source:
                source_pack, source_note, signed = source
                paths = candidates.prepare(ROOT, "refine", sub, source_pack, source_note, force=True)
                if lifecycle.content_fingerprint(Path(paths["candidate_pack"]), Path(paths["candidate_note"])) != signed:
                    raise SystemExit(f"{sub}: signed Foundry candidate changed while copying; state not created")
                st.update(paths, foundry_content_sha256=signed)
            path.write_text(json.dumps(st, indent=1))
            ensure_candidate(sub)
            baseline.begin_pass(sub, snap_path(sub), 1, _rel(pack_path(sub)), pack_path(sub),
                                note_path(json.loads(pack_path(sub).read_text())))
            print(f"{sub}: added at plan")
        if not (ROOT / "build/work/bundles" / f"{sub}.md").exists() and (REPO / "build/bundle.py").exists():
            subprocess.run([PY, str(REPO / "build/bundle.py"), sub], cwd=ROOT, capture_output=True)


def _rel(path: Path) -> str:
    return os.path.relpath(path, ROOT)


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
    t = next((h["t"] for h in reversed(st["history"]) if h["to"] == "plan" and h.get('from') != 'plan'), st["created"])
    return datetime.fromisoformat(t).timestamp()


def todo(st: dict) -> tuple[str, ...]:
    running = _running(st)
    if running:
        return ("wait", *running)
    stage = st["stage"]
    if stage == 'sign' and pending_written(st['sub'], json.loads(pack_path(st['sub']).read_text())):
        return ('dispatch',)
    if stage in ("solve", "recheck"):
        if _written_needs_strip(st):
            return ('dispatch',)
        names, qs = _solver_jobs(st), _questions(st)
        if qs is not None and _written_jobs(st):  # written checks: blind solve, then review
            return ("dispatch",)
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


def cmd_next(show_all: bool = False) -> None:
    for st in focused(chapters(), show_all):
        if st["stage"] != "ready":
            print(f"{st['sub']:<11} {st['stage']:<11} → {action(st)}")


MAX_UNCLEAN = 3  # fallback for historical gate notes; new launches use the shared two-failure guard


def unclean_streak(st: dict) -> int:
    """How many of the latest history entries, in a row, say a worker finished with the gates not clean."""
    n = 0
    for h in reversed(st["history"]):
        if "gates are not clean" not in h.get("note", ""):
            break
        n += 1
    return n


def give_up(sub: str, why: str) -> None:
    """Compatibility entry point: automated abandonment must never discard drafts."""
    raise SystemExit(f'{sub}: automatic abandonment disabled; candidate preserved: {why}')


def cmd_step(only: list[str] | None = None) -> None:
    import capabilities
    if (why := capabilities.preflight()):  # a tool the workers need is missing: say so, do not run on without it
        print(why)
        return
    for st in (chapters() if only else focused(chapters())):  # named chapters always run; a bare step stays on the focus list
        sub, (verb, *rest) = st["sub"], todo(st)
        if only and sub not in only:
            continue
        if st["stage"] in ("refine", "fix", "recheck") and not _running(st) and unclean_streak(st) >= MAX_UNCLEAN:
            last = st["history"][-1].get("note", "")
            print(f"{sub}: paused after repeated gate failures; candidate preserved. "
                  "Repair the reported blocker, then explicitly clear failures with unstick and a reason.")
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
        except (SystemExit, ValueError, OSError) as e:
            print(f"{sub}: {e}")


def cmd_unstick(sub: str, reason: str) -> None:
    with chapter(sub) as st:
        if _running(st):
            raise SystemExit('cannot clear failures while a worker is running')
        reliability.clear_failures(st, reason)
        st['history'].append({'t': now(), 'from': st['stage'], 'to': st['stage'],
                              'note': 'unstuck by manager: ' + reason})
    print(f'{sub}: failure allowance cleared; source and sign gates still apply')


def _short_date(ts: str | None) -> str:
    return ts[:10] if ts else "-"


def cmd_board(show_all: bool = False) -> None:
    rows = focused(chapters(), show_all)
    if not rows:
        print("no chapters on the refine board yet: refine.py add <subtopic…|--all>")
        return
    print(f"{'CHAPTER':<11} {'STAGE':<11} {'GATES':<6} {'OPEN':<5} {'PASS':<5} {'REFINED':<8} {'LAST':<11} WHO / RUNNING")
    for st in rows:
        g = st.get("gates") or {}
        failures = [f"{key}:{g[key]}" for key in ('validator', 'lint', 'syllabus', 'figures', 'glyphs', 'guided',
                                                   'no_loss', 'planned', 'written_review') if g.get(key)]
        gate = "ok" if g.get("ok") else ("-" if not g else ",".join(failures) or "failed")
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
    _archive_written_batch(st)
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
    # written checks are judged against a rubric, not the comparator: stems only for a blind solve, reviewed after
    written = [{"id": it["id"], "stem": it["stem"]} for it in pending_written(sub, pack)]
    for old in (BLIND / f"{sub}.{pfx}written.answers.json", _written_file(sub, "decisions"), _written_file(sub, "items")):
        if old.exists():
            old.unlink()
    (BLIND / f"{sub}.{pfx}written.questions.json").write_text(json.dumps(written, ensure_ascii=False, indent=1))
    _start_written_batch(st, pack)
    print(f"{out.relative_to(ROOT)}: {len(questions)} new questions" + (f" in {len(shards)} shards" if shards else "")
          + (f"; {len(written)} written checks to review" if written else ""))
    return list(range(1, len(shards) + 1))


def _ingest_check(st: dict) -> bool:
    f = WORK / f"{st['sub']}.check.json"
    if st.get("checked") or not f.exists() or f.stat().st_mtime < _since_pass(st) - 1:
        return False
    found = json.loads(f.read_text())
    written = [x for x in st["findings"] if x.get("rule") == "written review rejected"]  # recorded before the checker
    st["findings"] = written + [{"ref": x.get("where", "?"), "rule": x.get("rule", ""), "evidence": x.get("evidence", ""),
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
            fd._after_solving(st, f"{res['agreed']} of {len(asked)} new questions agreed, {n_open} disputed"
                              + _ingest_written(st, pack))
        elif st["stage"] == "tiebreak" and (BLIND / f"{sub}.{PFX}tiebreak.json").exists():
            if st['jobs'].get('tiebreak') and not _tiebroken(st):
                raise SystemExit(f'{sub}: tiebreak has not completed a validated review in this round')
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
    if _running(st):
        return  # never replace inputs underneath an active worker
    if st['stage'] == 'sign' and pending_written(sub, json.loads(pack_path(sub).read_text())):
        with chapter(sub) as state:
            move(state, 'recheck', 'written checks still need current independent review before signing')
        st = load(sub)
    wanted: list[tuple[str, int | None]] = []
    if st["stage"] in ("solve", "recheck"):
        if _questions(st) is None or _written_needs_strip(st):
            cmd_strip(sub, changed=st["stage"] == "recheck")
        wanted += [("solver", int(n.split("#")[1]) if "#" in n else None) for n in _solver_jobs(load(sub))]
        written = _written_jobs(load(sub))
        if written == ["wreviewer"] and "wreviewer" not in _running(load(sub)):
            write_written_items(sub)
        wanted += [(name, None) for name in written]
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
        if verdict == "keep" and any(x.get("rule") == "written review rejected" for x in hit):
            raise SystemExit(f"{sub}: cannot keep {ref} without a current independent written review; "
                             "resolve with fix, or rerun the written review instead of overriding its verdict")
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
    remaining(sub)
    ensure_candidate(sub)
    g, _ = fd.settle_glyphs(sub, gates, chapter, repair=repair_glyphs)
    with chapter(sub) as st:
        st["gates"] = g
        open_ = [d["id"] for d in st["disputes"] if d["status"] == "open"] + \
                [f["ref"] for f in st["findings"] if f["status"] == "open"] + \
                [f["ref"] for f in st["fixes"] if f["status"] == "open"]
        stage = st["stage"]
        ready = g["ok"] and not open_ and (stage == "sign" or (stage == "check" and bool(st.get("checked"))))
        if ready:
            published = publish_candidate(sub)
            st["publication"] = {"published": published, "at": now()}
            with fd.notes() as n:
                st["same_family"] = bool(n.get("only")) and n.get("only") == maker_of(st)
            st["last_additions"] = counts(additions(sub))
            st["refined"] = st.get("refined", 0) + 1
            st["last_refined"] = now()
            st["prepared_at"] = st["last_refined"]
            st["content_sha256"] = lifecycle.content_fingerprint(pack_path(sub), note_path(json.loads(pack_path(sub).read_text())))
            move(st, "ready", "refined: " + ", ".join(f"{v} {k}" for k, v in st["last_additions"].items() if v)
                 + (" (checked only by its own family)" if st["same_family"] else ""))
    if not ready:
        raise SystemExit(f"{sub}: not ready (stage {stage}, gates {g}, open {open_})")
    release(sub, published=published)
    fd.speech_after_sign(sub, state=chapter, logs=LOGS)  # new audio for the additions, in the background


def chapter_paths(sub: str) -> list[str]:
    pack = json.loads(pack_path(sub).read_text())
    found = [pack_path(sub), note_path(pack), STATE / f"{sub}.json", ROOT / "build/work/mcq/overrides.json",
             ROOT / "build/work/teach" / f"{sub}.json", plan_path(sub), WORK / f"{sub}.additions.md"]
    found += list((ROOT / "build/out/Assets").glob(f"*/{sub}-*"))
    return candidates.owned_paths(ROOT, found)


def publish_candidate(sub: str) -> bool:
    """Publish before marking the refine pass ready; report a failed publication."""
    cfg = config()
    if cfg.get("publish_on_sign", True) and os.environ.get("FOUNDRY_PUBLISH", "1") == "1":
        vault = os.environ.get("STEM_TUTOR_VAULT")
        r = subprocess.run([PY, str(REPO / "build/publish.py"), "--build-root", str(ROOT / "build/out"),
                            *(["--candidate", sub, str(pack_path(sub)), str(note_path(json.loads(pack_path(sub).read_text()))) ]
                              if candidates.state_paths(STATE, sub).get("candidate_pack") else []), *(["--vault", vault] if vault else [])], cwd=REPO,
                           capture_output=True, text=True)
        if r.returncode:
            raise RuntimeError(f"{sub}: PUBLISH FAILED: {r.stderr.strip()[-300:]}")
        print(f"{sub}: published into the vault {r.stdout.strip()[-120:]}")
        return True
    return False


def release(sub: str, *, published: bool = False) -> None:
    """Checkpoint the signed candidate and report actual publication outcome."""
    cfg = config()
    if cfg.get("commit_on_sign", True) and os.environ.get("FOUNDRY_COMMIT", "1") == "1":
        a = load(sub).get("last_additions", {})
        what = ", ".join(f"{v} {k.replace('_', ' ')}" for k, v in a.items() if v) or "additions"
        result = candidates.checkpoint(ROOT, chapter_paths(sub), f"refine({sub}): {what}", run=subprocess.run)
        print(f"{sub}: {result}")
    fd.notify(f"{sub} has been refined: the additions are in your vault" if published else
              f"{sub}: refined candidate ready; publication disabled")
    print(f"{sub}: ready" + (" in the vault" if published else " as an unpublished candidate"))


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
    elif role == "wsolver":  # blind too: the stems only
        lines.append(f"Questions: {_written_questions(st).relative_to(ROOT)}. Write your solutions to "
                     f"{_written_answers(st).relative_to(ROOT)}.")
    elif role == "wreviewer":
        lines.append(f"Checks with keys, rubrics and the blind solutions: {_written_file(sub, 'items').relative_to(ROOT)}. "
                     f"Write your decisions to {_written_file(sub, 'decisions').relative_to(ROOT)}. "
                     f"Chapter bundle for context: build/work/bundles/{sub}.md.")
    else:
        pack = json.loads(pack_path(sub).read_text()) if pack_path(sub).exists() else {}
        lines.append(f"Chapter files: editable pack {pack_path(sub)}, note {note_path(pack)}, "
                     f"bundle build/work/bundles/{sub}.md.")
    if role in ("refiner", "fixer"):
        lines.append(f"Teaching-card draft (editable copy for this pass): {teach_path(sub)}. Merge it with "
                     f"`.venv/bin/python build/teach_cards.py merge {sub} --draft {shlex.quote(str(teach_path(sub)))} "
                     f"--pack {shlex.quote(str(pack_path(sub)))}`.")
        if st.get('source_teach'):
            lines.append(f"Earlier teaching draft (read-only source): {st['source_teach']}. Reuse useful material "
                         "without replacing the current pack's existing teaching fields or treating drafts as approved.")
    if role not in ("solver", "tiebreak", "wsolver", "wreviewer"):
        lines.append(f"Persisted scope: {st.get('scope', 'legacy')}. Lessons scope preserves subject-note bytes and all assessment items; improve teaching cards, examples, independent checks, guided_forms and linked existing diagrams only.")
    if role == "scout":
        lines.append(f"Write the plan to {plan_path(sub).relative_to(ROOT)}.")
    if role in ("refiner", "fixer") and st.get('scope') != 'lessons':
        lines.append(f"Plan: {plan_path(sub).relative_to(ROOT)}. New question ids continue {sub}-r01, {sub}-r02, … "
                     f"after the highest -r id already in the pack.")
    elif role in ('refiner', 'fixer'):
        lines.append(f"Plan: {plan_path(sub).relative_to(ROOT)}. Do not add assessment-bank items, edit existing "
                     "stems/options/answers/rubrics, or write a corrections proposal in lessons scope. "
                     "Report suspected existing errors in not_done for separate source-bound review.")
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
    import evidence
    lines += evidence.prompt_lines(role, sub, config())
    return "\n".join(lines)


def _expects(st: dict, role: str, shard: int | None) -> str | None:
    sub = st["sub"]
    if role == "solver":
        return f"build/work/blind/{sub}.{_pfx(st)}answers{f'.part{shard}' if shard else ''}.json"
    if role == "wsolver":
        return str(_written_answers(st).relative_to(ROOT))
    if role == "wreviewer":
        return str(_written_file(sub, "decisions").relative_to(ROOT))
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


@lifecycle.serialized_launch(lambda *args, **kwargs: STATE)
def cmd_run(role: str, sub: str, on: str | None = None, shard: int | None = None) -> None:
    cfg = config()
    if role not in cfg["ladders"]:
        raise SystemExit(f"{role} is not a refine role (roles: {', '.join(cfg['ladders'])})")
    if on and on not in cfg["ladders"][role]:
        raise SystemExit(f"{on} is not an allowance (allowances: {', '.join(cfg['ladders'][role])})")
    remaining(sub)
    ensure_candidate(sub)
    name, st = role + (f"#{shard}" if shard else ""), load(sub)
    if name in _running(st):
        raise SystemExit(f"{sub}: a {name} is already working on this chapter")
    previous = st['jobs'].get(name, {})
    if previous.get('pid') and not previous.get('finished') and not lifecycle.process_alive(previous['pid']):
        with chapter(sub) as current:
            current['jobs'][name].update(finished=now(), exit=-1, ok=False, interrupted=True)
            reliability.record_result(current, name, ok=False, exit_code=-1, issues=['worker exited without collection'])
        st = load(sub)
    inputs = [pack_path(sub), SPECS / spec_of(sub) / 'graph.json', HERE / 'roles' / f'{role}.md']
    baseline = {'pack': json.loads(pack_path(sub).read_text())}
    original = snapshot(sub)
    if (not isinstance(original, dict) or original.get('pass') != st.get('pass', 1)
            or not isinstance(original.get('pack'), dict) or not isinstance(original['pack'].get('items'), list)):
        raise SystemExit(f'{sub}: missing, malformed or stale baseline; restore its verified checkpoint before paid work')
    if role == 'checker':
        # Recovery may advance a verified candidate without the normal collect
        # hook. Derive fresh checker input from that candidate and its immutable
        # baseline, including when a prior pass left an additions file behind.
        write_additions(sub)
    staged, _ = reviewed_source_baseline(original['pack'], baseline['pack'])
    baseline['pack']['items'] = staged['items'] + baseline['pack']['items']
    if why := reliability.launch_problem(st, role, inputs, baseline=baseline,
                                                diagram_catalog=fd._diagram_catalog(ROOT / "build/out/assets")):
        raise SystemExit(f'{sub}: {why}')
    import capabilities
    if why := capabilities.preflight():
        raise SystemExit(why)
    if role == "refiner":
        archive_stale_corrections(sub)
        ensure_snapshot(st)  # before the refiner touches anything
    last = st["jobs"].get(name, {})
    with fd.notes() as n:
        if on and n.get("only") and on != n["only"]:
            raise router.Wait(f"provider preference is only {n['only']}")
        provider = router.pick(role, maker_of(st), router.usage(n, fd.CODEX, fd.CLAUDE), cfg, _busy(),
                               only=on or n.get("only"))
        failed = last.get("provider") == provider and last.get("ok") is False and not last.get("limit")
        rung = router.rung(n, cfg, role, provider, retry=last.get("rung", 0) if failed else None)
    model, effort = cfg["ladders"][role][provider][rung]
    if role in ("scout", "refiner"):
        import evidence
        evidence.refresh_bundle(ROOT, PY, sub)
    LOGS.mkdir(parents=True, exist_ok=True)
    stem = f"{sub}.{name.replace('#', '-')}.{datetime.now():%m%d-%H%M%S}"
    log, out, expects = LOGS / f"{stem}.log", LOGS / f"{stem}.out.json", _expects(st, role, shard)
    worker = worker_command(role, provider, model, effort, role_prompt(role, sub, shard), out)
    authoring = [WORK, BLIND, STATE, LOGS, ROOT / "build/work/teach", ROOT / "build/work/gen",
                 ROOT / "build/work/mcq", ROOT / "build/out/assets", ROOT / "build/out/Assets"]
    for key in ("candidate_pack", "candidate_note", "candidate_teach"):
        if st.get(key):
            authoring.append(Path(st[key]).parent)
    worker += candidates.writable_flags(authoring)
    left = remaining(sub, start=True)
    if left is not None:
        worker = [PY, str(REPO / "src/tutor_workers/timeout.py"), str(left), *worker]
    written_launch = _written_launch(st, role)
    then = [PY, str(HERE / "refine.py"), "collect", name, sub, str(out)]
    shell = (f"{shlex.join(worker)} < /dev/null > {shlex.quote(str(log))} 2>&1; "
             f"{shlex.join(then)} $? >> {shlex.quote(str(log))} 2>&1")
    tier = f"{model}/{effort}" if effort else model
    with chapter(sub) as st:
        if role == "refiner":
            st["maker"] = provider  # the other family blind-solves what this one adds
        st["jobs"][name] = {"pid": None, "provider": provider, "model": tier, "rung": rung, "started": now(),
                            "failure_input": reliability.fingerprint(st, role, inputs),
                            "log": str(log.relative_to(ROOT)), "out": str(out.relative_to(ROOT)),
                            **written_launch,
                            **({"expects": expects} if expects else {})}
    # A fast child can collect before Popen returns. Its inputs and identity must
    # already be durable; afterward update only the PID, never overwrite results.
    try:
        proc = subprocess.Popen(["/bin/sh", "-c", shell], cwd=REPO, start_new_session=True, stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL,
                                env={**os.environ, "FOUNDRY_ROOT": str(ROOT),
                                     "FOUNDRY_EXPECTS": str(ROOT / expects) if expects else "",
                                     "FOUNDRY_NOTIFY": os.environ.get("FOUNDRY_NOTIFY", "1"),
                                     "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1"})
    except (OSError, ValueError) as exc:
        with chapter(sub) as st:
            st['jobs'][name].update(finished=now(), exit=-1, ok=False, launch_error=str(exc))
            reliability.record_result(st, name, ok=False, exit_code=-1, issues=[str(exc)])
        raise SystemExit(f'{sub}: {name} could not start: {exc}') from exc
    with chapter(sub) as st:
        st['jobs'][name]['pid'] = proc.pid
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


@reliability.collect_safely(lambda sub: chapter(sub))
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
    try:
        if role in ('refiner', 'fixer') and exit_code == 0:
            ensure_candidate(sub)  # recover a pre-upgrade worker that had no per-pass teaching draft
        g = fd.settle_glyphs(sub, lambda s: gates(s, defer_written=True), chapter, repair=repair_glyphs)[0] \
            if role in ("refiner", "fixer") and exit_code == 0 else None
    except Exception as exc:  # collection must persist a failure, never orphan a finished worker
        g = {'ok': False, 'collection': 1, 'first': [f'collection {type(exc).__name__}: {exc}']}
    wrote = True
    if job.get("expects"):
        f = ROOT / job["expects"]
        wrote = f.exists() and f.stat().st_mtime >= datetime.fromisoformat(job["started"]).timestamp() - 1
        if wrote and (problem := reliability.output_problem(f, role)):
            wrote = False
    if role == "scout" and wrote:  # the plan must be readable too
        try:
            wrote = isinstance(json.loads(plan_path(sub).read_text()), dict)
        except (OSError, ValueError):
            wrote = False
    import evidence
    evid = evidence.missing(role, sub, config(), ROOT / job["log"] if job.get("log") else None) \
        if exit_code == 0 and report and out != "-" else []
    if evid:
        g = {**(g or {"ok": True}), "ok": False, "sources": len(evid), "first": [f"sources {m}"[:200] for m in evid] + (g or {}).get("first", [])}
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
        _finish_written_job(st, name)
        reliability.record_result(st, name, ok=bool(ok and job.get('ok') is not False), exit_code=exit_code,
                                  issues=(g or {}).get('first', []) or ([] if ok else ['invalid worker output or failed exit']))
        if exit_code != 0 or not report or not wrote:
            why = (f"stopped by a usage limit on {NAMES[provider]}" if limit else
                   f"failed (exit {code})" if exit_code or not report else "finished without writing its file")
            st["history"].append({"t": now(), "from": st["stage"], "to": st["stage"],
                                  "note": f"{name} {why}; see {job.get('log')}"})
        elif role == "scout" and st["stage"] == "plan" and not evid:
            _accept_plan(st)
        elif role == "refiner" and g["ok"]:
            write_additions(sub)
            move(st, "solve", "refined: " + ", ".join(f"{v} {k}" for k, v in counts(additions(sub)).items() if v))
        elif role == "fixer" and g["ok"]:
            for f in st["fixes"]:
                f["status"] = "done"
            write_additions(sub)
            ids = {it["id"] for it in json.loads(pack_path(sub).read_text()).get("items", [])}
            changed = any(f["ref"] in ids or f["ref"].endswith((".faded", ".discover", ".check", ".retry"))
                          for f in st["fixes"])
            changed = changed or bool(g.get("written_review"))  # a written check without a current review is re-reviewed
            move(st, "recheck" if changed else "sign", f"fixed; {len(st['fixes'])} fixes applied")
        elif g is not None:
            st["history"].append({"t": now(), "from": st["stage"], "to": st["stage"],
                                  "note": f"{role} finished but gates are not clean: {g.get('first', [])[:2]}"})


# ---------------- views ----------------
def preparation_queue() -> list[dict]:
    """Missing guided preparation first, then unknown age, then oldest evidence.

    Audio cache times are intentionally irrelevant. A legacy pass timestamp is
    recorded evidence; file modification time is not preparation evidence.
    """
    states = {st["sub"]: st for st in chapters()}
    order, graphs = {}, {}
    for graph_file in sorted(SPECS.glob("*/graph.json")):
        graph = json.loads(graph_file.read_text())
        graphs[graph_file.parent.name] = graph
        for entry in graph.get("subtopics", []):
            order[entry["id"]] = len(order)
    queue = []
    for sub in signed_chapters():
        pack = json.loads(pack_path(sub).read_text())
        cards = pack.get("teach") or {}
        graph = graphs.get(spec_of(sub), {})
        expected = {kc["id"] for kc in graph.get("kcs", []) if kc.get("subtopic") == sub}
        missing = []
        if not expected:
            missing.append("expected syllabus KCs unavailable")
        missing.extend(f"{kc}: guided card missing" for kc in sorted(expected - cards.keys()))
        missing.extend(f"{kc}: unknown guided card KC" for kc in sorted(cards.keys() - expected))
        if not isinstance(pack.get("guided_forms"), dict):
            missing.append("reviewed guided form inventory is missing")
        # Opt into the same complete card/inventory/diagram validator used at
        # signing, including missing KCs, checks, rubrics and tracked mistakes.
        guided_pack = {**pack, "guided_forms": pack.get("guided_forms", {})}
        note = note_path(pack)
        if expected:
            missing += fd.guided_problems(guided_pack, graph,
                                          note.read_text() if note.is_file() else "", ROOT / "build/out/assets", lesson_display=True)
        ready = not missing
        state = states.get(sub, {})
        prepared = state.get("prepared_at") or state.get("last_refined")
        queue.append({"sub": sub, "guided_prepared": ready, "missing_reasons": list(dict.fromkeys(missing)), "prepared_at": prepared,
                      "age": "recorded" if prepared else "unknown",
                      "content_sha256": state.get("content_sha256"),
                      "stage": state.get("stage", "unstarted")})
    return sorted(queue, key=lambda row: (row["guided_prepared"], row["prepared_at"] or "",
                                         order.get(row["sub"], 10**9), fd._natural(row["sub"])))


def coverage() -> dict:
    """Which chapters were refined, when and how much; which built chapters still lack the diagrams the hints suggest."""
    import diagram_hints
    refined = {st["sub"]: {"passes": st.get("refined", 0), "last": st.get("last_refined"), "stage": st["stage"],
                           "added": st.get("last_additions", {})} for st in chapters()}
    bare = []
    for g in sorted(SPECS.glob("*/graph.json")):
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
    return {"preparation_queue": preparation_queue(), "speech_gaps": fd.pregen.gaps_report(), "refined": refined, "never": [s for s in signed if s not in refined], "no_diagram": sorted(set(bare), key=fd._natural),
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
    rows = focused(chapters())
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
            except (SystemExit, ValueError) as e:
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
    def doctor() -> None:
        import capabilities
        text, ok = capabilities.report()
        print(text)
        if not ok:
            raise SystemExit(1)
    simple = {"preparation-queue": lambda: print(json.dumps(preparation_queue(), indent=1)), "board": lambda: cmd_board("--all" in sys.argv), "next": lambda: cmd_next("--all" in sys.argv), "usage": fd.cmd_usage, "install-skill": cmd_install_skill, "doctor": doctor}
    one = {"compare": cmd_compare, "packet": cmd_packet, "gates": cmd_gates, "sign": cmd_sign, "status": cmd_status,
           "dispatch": cmd_dispatch, "escalate": lambda s: cmd_run("adjudicator", s)}
    if cmd == "new-run":
        print(json.dumps(lifecycle.new_course_run(STATE, rest[0], 3600, states=chapters), indent=1))
    elif cmd in simple:
        simple[cmd]()
    elif cmd in one:
        one[cmd](rest[0])
    elif cmd == "add":
        cmd_add(rest)
    elif cmd == "step":
        cmd_step(rest)
    elif cmd == "unstick":
        cmd_unstick(rest[0], ' '.join(rest[1:]))
    elif cmd == "only":
        fd.cmd_only(rest)
    elif cmd == "strip":
        cmd_strip(rest[0], "--changed" in rest)
    elif cmd == "resolve":
        cmd_resolve(rest[0], rest[1], rest[2], " ".join(rest[3:]))
    elif cmd == "review-corrections":  # bind the review of build/work/refine/<sub>.corrections.json to this candidate
        bind_correction_review(rest[0], rest[rest.index("--reviewer") + 1], rest[rest.index("--finding") + 1])
        print(f"review bound to {rest[0]}: now run gates")
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
