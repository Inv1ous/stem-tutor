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
  foundry.py normalise [chapters]         repair blank options of figure questions (done at signing too)
  foundry.py only codex|claude|off        use one allowance only (its own family then checks its drafts: marked); off = both
  foundry.py reading claude five_hour <percent> [reset time]   pass on a figure Claude does not report to the foundry
  foundry.py run <role> <subtopic> [--on claude|codex]   launch one headless worker (drafter, fixer, tiebreak,
                                          solver, checker, adjudicator); `codex <role> <subtopic>` forces Codex
  foundry.py dispatch <subtopic>          launch the solvers (one per shard) and the checker the chapter needs now
  foundry.py queue <role> <subtopics…>    launch that role for each chapter as slots free up (run it detached)
  foundry.py wait [seconds]               return when no worker is running (default: up to 9 minutes)
  foundry.py coverage [--queue N|--json]  the whole syllabus against what is built; holes; what to build next
  foundry.py tts <subtopic…|--all> [--voice V] [--speed S]   make the read-aloud audio now (local CPU only, no allowance)
  foundry.py tts status                   per chapter: lines, with audio, missing, gaps; and whether Kokoro is set up
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
sys.path.insert(0, str(REPO / "src"))
from tutor_workers import lifecycle, candidates, reliability
from tutor_workers.locations import WorkerLocations, chapter_pack, spec_of

LOCATIONS = WorkerLocations.from_environment(REPO)
ROOT = LOCATIONS.data_root
HERE = REPO / "foundry"
STATE, LOGS = LOCATIONS.state("foundry"), LOCATIONS.logs("foundry")
PACKS, SPECS, NOTES = LOCATIONS.packs, LOCATIONS.specs, LOCATIONS.notes
BLIND, WORK = LOCATIONS.blind, LOCATIONS.work("foundry")
HOLD = PACKS / "HOLD.json"
PY = LOCATIONS.python
CODEX = os.environ.get("FOUNDRY_CODEX") or shutil.which("codex") or \
    "/Applications/ChatGPT.app/Contents/Resources/codex-cli/bin/codex"
CLAUDE = os.environ.get("FOUNDRY_CLAUDE") or shutil.which("claude") or "claude"
USAGE = LOCATIONS.usage  # the router's notes: readings of both allowances, tier floors (not in git)

sys.path.insert(0, str(REPO / "build"))
sys.path.insert(0, str(REPO / "plugin/stem-tutor/skills/tutor/scripts"))
sys.path.insert(0, str(HERE))
import router  # noqa: E402
import pregen  # noqa: E402  (read-aloud audio, shared with refine)
from router import NAMES  # noqa: E402

# every role is a headless worker; which allowance and which model does it is the router's choice (config.json)
STAGE_ROLE = {"draft": "drafter", "solve": "solver", "tiebreak": "tiebreak", "check": "checker",
              "adjudicate": "manager", "fix": "fixer", "recheck": "solver", "sign": "manager"}


def config() -> dict:
    return json.loads((HERE / "config.json").read_text())


def now() -> str:
    return lifecycle.timestamp()


def pack_path(sub: str) -> Path:
    return Path(candidates.state_paths(STATE, sub).get("candidate_pack", chapter_pack(PACKS, sub)))


def note_path(pack: dict, sub: str | None = None) -> Path:
    state = candidates.state_paths(STATE, sub or pack.get("subtopic", ""))
    return Path(state.get("candidate_note", NOTES / pack.get("note", "")))


def ensure_candidate(sub: str) -> None:
    st = load(sub)
    if st.get("candidate_pack"):
        return
    pack_file = pack_path(sub)
    pack = json.loads(pack_file.read_text()) if pack_file.is_file() else {}
    paths = candidates.prepare(ROOT, "foundry", sub, pack_file, note_path(pack, sub))
    if paths and not st.get("candidate_pack"):
        with chapter(sub) as current:
            current.update(paths)


def remaining(sub: str, *, start: bool = False) -> float | None:
    left = lifecycle.course_remaining(STATE, sub, 7200, start=start)
    if left is not None and left <= 0:
        raise lifecycle.DeadlineReached(f"{sub}: course deadline reached; incomplete work remains pending")
    return left


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
    lifecycle.transition(st, stage, note, at=now())


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


LINK = re.compile(r"(?<!!)\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]")
EMBEDDED = re.compile(r"!\[\[((?:Assets|Library)/[^\]|]+\.svg)")
ASSET_EMBEDS = re.compile(r'!\[\[((?:Assets|Library)/[^\]|]+\.(?:svg|png))(?:\|[^\]]*)?\]\]')


def _diagram_catalog(assets_root: Path):
    """Production and explicit Library roots use catalog integrity checks."""
    from tutorlib.asset_library import AssetLibrary
    if assets_root.name == 'Library':
        return AssetLibrary(assets_root.parent)
    if ROOT == REPO and assets_root in (ROOT / 'build/out/assets', ROOT / 'build/out/Assets'):
        # Worker-created nested catalogs must not shadow the authoritative Library.
        import library
        return AssetLibrary(Path(os.environ['STEM_TUTOR_VAULT'])
                            if os.environ.get('STEM_TUTOR_VAULT') else library.learner_vault())
    if (assets_root / 'Library/catalog.json').is_file():
        return AssetLibrary(assets_root)
    explicit = os.environ.get('STEM_TUTOR_VAULT')
    if explicit and (Path(explicit) / 'Library/catalog.json').is_file():
        return AssetLibrary(Path(explicit))
    return None  # isolated legacy worker fixtures retain their explicit asset root


def _catalog_diagram(catalog, reference: str) -> Path:
    if (not isinstance(reference, str) or not reference.startswith(('Assets/', 'Library/'))
            or '..' in Path(reference).parts or '\\' in reference):
        raise ValueError('invalid diagram reference')
    candidates = [reference]
    if reference.startswith('Assets/'):
        candidates += ['build/out/assets/' + reference.removeprefix('Assets/'),
                       'build/out/Assets/' + reference.removeprefix('Assets/')]
    for candidate in candidates:
        try:
            record = catalog.record(candidate)
        except ValueError:
            continue
        if record.get('teaching_status') == 'superseded':
            raise ValueError('diagram retired from teaching reuse; use ' + str(record.get('superseded_by', 'its reviewed replacement')))
        return catalog.resolve(candidate)  # a known corrupt asset must never fall back
    raise ValueError(f'unknown diagram reference: {reference}')


def _diagram_embedded(path: str, note_text: str, catalog=None) -> bool:
    if f'![[{path}]]' in note_text:
        return True
    if catalog is None:
        return False
    target = _catalog_diagram(catalog, path)
    for embedded in ASSET_EMBEDS.findall(note_text):
        if _catalog_diagram(catalog, embedded) == target:
            return True
    return False


def link_problems(text: str) -> list[str]:
    """Links in a lesson note that name no chapter (`[[3.4 Chemical bonding]]` where the note is `3.4 Covalent
    bonding…`), each with the nearest real name. The vault's own pages and path links are fine."""
    import difflib

    import bundle
    names = set(bundle.note_names().values()) | set(bundle.VAULT_NOTES)
    plain = {n.replace("’", "'").lower(): n for n in names}
    out = []
    for m in LINK.finditer(text):
        t = m.group(1).strip()
        if t in names or "/" in t or t.startswith("Assets") or t.replace("’", "'").lower() in plain:
            continue
        import publish
        num = re.match(r"^(\d+(?:\.\d+)?)\s", t)
        same = [n for n in names if num and n.startswith(num.group(1) + " ") and publish._words(t) & publish._words(n)]
        near = same or [n for n in names if n.lower() in difflib.get_close_matches(t.lower(), [x.lower() for x in names], 1, 0.6)]
        out.append(f"[[{t}]] is not a chapter note" + (f"; did you mean [[{near[0]}]]?" if len(near) == 1 else ""))
    return list(dict.fromkeys(out))


def _card_display_paths(pack: dict) -> set[str]:
    paths = set()
    for card in (pack.get("teach") or {}).values():
        if not isinstance(card, dict):
            continue
        from tutorlib.card_diagrams import diagram_descriptions
        diagrams, descriptions = card.get("diagrams"), diagram_descriptions(card)
        if not isinstance(diagrams, list):
            continue
        for index, path in enumerate(diagrams):
            if (isinstance(path, str) and index < len(descriptions)
                    and isinstance(descriptions[index], str) and descriptions[index].strip()):
                paths.add(path)
    return paths


def _verified_display_diagram(catalog, reference: str) -> Path:
    """A card display is evidence of use only after hash/provenance validation."""
    if catalog is None:
        raise ValueError("lesson display requires a registered, hash-verified diagram")
    path = _catalog_diagram(catalog, reference)
    record = catalog.record(path.relative_to(catalog.root).as_posix())
    if 'question' in str(record.get('kind', '')).casefold():
        raise ValueError("assessment media cannot be used as a teaching diagram")
    if not (record.get("origins") or record.get("provenance")
            or (record.get("generated") and record.get("renderer"))):
        raise ValueError("diagram provenance is missing")
    provenance = record.get("provenance") or {}
    for sidecar in provenance.get("sidecars", []) if isinstance(provenance, dict) else []:
        data = json.loads(catalog.read(sidecar))
        if data.get("sha256") and data["sha256"] != record["sha256"]:
            raise ValueError("diagram provenance image hash does not match")
    if path.suffix.lower() == ".svg":
        from tutor_workers.media_checks import svg_problem
        problem = svg_problem(catalog.read(path.relative_to(catalog.root).as_posix()))
        if problem:
            raise ValueError(problem)
    return path


def diagram_problems(pack: dict, graph: dict, note_text: str, *, lesson_display: bool = False) -> list[str]:
    """A chapter with points a figure shows must request a diagram (or say why not), and every requested diagram must
    be embedded in the note."""
    import diagram_hints
    sub = pack.get("subtopic", "")
    kcs = [k for k in graph["kcs"] if k["subtopic"] == sub]
    out = []
    asked = [d.get("file", "") for d in pack.get("diagrams") or []]
    sug = diagram_hints.suggest(kcs)
    if sug and not asked and not pack.get("diagrams_skipped"):
        out.append("no diagram: points a figure shows (" + "; ".join(f"{k} for {', '.join(v[:3])}" for k, v in sug.items())
                   + "): request one in `diagrams` and embed it, or set `diagrams_skipped` with the reason")
    if lesson_display:
        card_paths = [path for card in (pack.get("teach") or {}).values() if isinstance(card, dict)
                      for path in (card.get("diagrams") if isinstance(card.get("diagrams"), list) else [])]
        asked = list(dict.fromkeys(asked + [path for path in card_paths if isinstance(path, str)]))
    try:
        catalog = _diagram_catalog(ROOT / 'build/out/assets')
    except (OSError, ValueError) as exc:
        return out + [f'diagram catalog unavailable: {exc}'] if asked else out
    described = _card_display_paths(pack)
    verified = {}
    def display_identity(reference):
        if reference not in verified:
            verified[reference] = _verified_display_diagram(catalog, reference)
        return verified[reference]
    described_identities = set()
    if lesson_display:
        for reference in sorted(described):
            try:
                described_identities.add(display_identity(reference))
            except (OSError, ValueError) as exc:
                out.append(f'diagram {reference} unavailable: {exc}')
    for path in asked:
        try:
            if lesson_display:
                # Alias equivalence is established only after both references
                # pass catalog hash/provenance checks, never by basename or bytes alone.
                if display_identity(path) not in described_identities:
                    out.append(f"diagram {path} is not bound to a teaching card with an accessible description")
                    continue
                continue
            if catalog is not None:
                _catalog_diagram(catalog, path)
            if not _diagram_embedded(path, note_text, catalog):
                out.append(f'diagram {path} is requested but not embedded in the note (![[{path}]])')
        except (OSError, ValueError) as exc:
            out.append(f'diagram {path} unavailable: {exc}')
    return out


def glyph_problems(pack: dict, note_text: str) -> list[str]:
    """Unsafe Unicode sub/superscript letters (Eₖ, vᵢₙᵢₜᵢₐₗ) in the pack's text or the note: the terminal draws them from
    several fonts and the line wobbles. They belong in LaTeX ($E_k$). build/glyphs.py repairs them."""
    import glyphs
    return glyphs.data_problems(pack) + glyphs.problems(note_text)


def repair_glyphs(sub: str) -> int:
    """Rewrite the chapter's pack and note with every unsafe sub/superscript as LaTeX (glyphs.fix_text), keeping each
    file's formatting. Returns how many strings changed."""
    import glyphs
    p = pack_path(sub)
    if not p.exists():
        return 0
    n = glyphs.repair_file(p)
    note = note_path(json.loads(p.read_text()), sub)
    return n + (glyphs.repair_file(note) if note.is_file() else 0)


def only_glyphs(g: dict) -> bool:
    """The gates fail for the glyphs alone: nothing else needs a worker, so the repair is mechanical."""
    return bool(g.get("glyphs")) and not g.get("ok") and not any(
        g.get(k) for k in ("validator", "lint", "syllabus", "figures", "guided", "no_loss", "planned")) and g.get("pack") != "missing"


def settle_glyphs(sub: str, gate, chapter_ctx, repair=None) -> tuple[dict, int]:
    """Run the gates; when the glyphs are the only thing failing, repair them (deterministic, no retry) and run the
    gates again, noting `glyphs auto-fixed: N strings` in the chapter's history. → (gates, strings repaired)."""
    g = gate(sub)
    if not only_glyphs(g):
        return g, 0
    n = (repair or repair_glyphs)(sub)
    if n:
        with chapter_ctx(sub) as st:
            st["history"].append({"t": now(), "from": st["stage"], "to": st["stage"], "note": f"glyphs auto-fixed: {n} strings"})
        g = gate(sub)
    return g, n


def speech_problems(sub: str) -> list[str]:
    """Maths in a chapter's read-aloud lines with no spoken form (the learner learns it as it is spoken, so it must read
    right with no `speech` override). Never raises: a speech fault must not stop the pipeline."""
    try:
        import pregen
        return [f"read aloud: {lid} has no spoken form for {' '.join(sy[:3])}: rewrite the maths in plain notation"
                for lid, sy in sorted(pregen.line_gaps(sub).items())][:6]
    except Exception:  # noqa: BLE001
        return []


def guided_draft_problems(path: Path, pack: dict, graph: dict) -> list[str]:
    """Do not sign the old pack while an attempted guided upgrade is incomplete or unmerged."""
    if not path.is_file():
        return []
    import teach_cards
    try:
        cards = json.loads(path.read_text())
    except (OSError, ValueError):
        return ["teaching-card draft cannot be read"]
    if not isinstance(cards, dict) or any(not isinstance(c, dict) for c in cards.values()):
        return ["teaching-card draft must map IDs to cards"]
    if not any(teach_cards.is_guided(card) for card in cards.values()):
        return []
    kcs = {k["id"] for k in graph["kcs"] if k["subtopic"] == pack.get("subtopic")}
    issues = [f"{kc}: guided draft card missing" for kc in sorted(kcs - cards.keys())]
    issues += [f"{kc}: guided draft has an unknown KC" for kc in sorted(cards.keys() - kcs)]
    for kc, card in cards.items():
        issues.extend(teach_cards.check_card(kc, card, guided=True))
        disclosed = card.get('disclosed_item_ids')
        if isinstance(disclosed, list):
            items = pack.get('items') if isinstance(pack.get('items'), list) else []
            for ident in disclosed:
                if isinstance(ident, str) and not any(isinstance(item, dict) and item.get('id') == ident
                                                       for item in items):
                    issues.append(f'{kc}: disclosed item {ident} is not in this pack')
        published = (pack.get("teach") or {}).get(kc, {})
        if not isinstance(published, dict) or any(published.get(key) != value for key, value in card.items()):
            issues.append(f"{kc}: guided draft is not merged into the pack")
    if not isinstance(pack.get("guided_forms"), dict):
        issues.append("guided form inventory is not merged into the pack")
    return issues


def guided_problems(pack: dict, graph: dict, note_text: str, assets_root: Path, *, lesson_display: bool = False) -> list[str]:
    """Validate opted-in guided chapters; the form inventory is an explicit, reviewable source audit."""
    if "guided_forms" not in pack:
        return []
    import teach_cards
    inventory = pack.get("guided_forms")
    if not isinstance(inventory, dict):
        return ["guided_forms must be an object mapping each KC to its reviewed forms"]
    kcs = [k["id"] for k in graph["kcs"] if k["subtopic"] == pack.get("subtopic")]
    cards = pack.get("teach")
    if not isinstance(cards, dict):
        return ["teach must be an object mapping each KC to its card"]
    issues = []
    try:
        catalog = _diagram_catalog(assets_root)
        catalog_error = None
    except (OSError, ValueError) as exc:
        catalog, catalog_error = None, str(exc)
    for kc in kcs:
        expected = inventory.get(kc)
        if (not isinstance(expected, list) or not expected
                or any(not isinstance(x, str) or not x.strip() for x in expected)
                or len({x.strip() for x in expected}) != len(expected)):
            issues.append(f"{kc}: reviewed form inventory is missing or invalid")
            expected = []
        card = cards.get(kc)
        if not isinstance(card, dict):
            issues.append(f"{kc}: guided card missing")
            continue
        issues.extend(teach_cards.check_card(kc, card, guided=True))
        disclosed = card.get('disclosed_item_ids')
        if isinstance(disclosed, list):
            items = pack.get('items') if isinstance(pack.get('items'), list) else []
            for ident in disclosed:
                if isinstance(ident, str) and not any(isinstance(item, dict) and item.get('id') == ident
                                                       for item in items):
                    issues.append(f'{kc}: disclosed item {ident} is not in this pack')
        tracked = pack.get("misconceptions")
        tracked = tracked if isinstance(tracked, list) else []
        misconceptions = card.get("misconceptions")
        for misconception in misconceptions if isinstance(misconceptions, list) else []:
            ident = misconception.get("id") if isinstance(misconception, dict) else None
            if not isinstance(ident, str) or not ident.strip() or not any(
                isinstance(item, dict) and item.get("id") == ident and item.get("kc") == kc for item in tracked
            ):
                issues.append(f"{kc}: guided misconception must match this idea in the tracker")
        forms = card.get("forms")
        names = {f["name"] for f in forms if isinstance(f, dict) and isinstance(f.get("name"), str)} if isinstance(forms, list) else set()
        issues.extend(f"{kc}: form {name} is not covered" for name in expected if name not in names)
        diagrams = card.get("diagrams")
        for path in diagrams if isinstance(diagrams, list) else []:
            if (not isinstance(path, str) or not path.startswith(("Assets/", "Library/"))
                    or ".." in Path(path).parts or '\\' in path):
                issues.append(f"{kc}: invalid diagram path")
                continue
            try:
                if catalog_error:
                    raise ValueError(catalog_error)
                if catalog is not None:
                    _catalog_diagram(catalog, path)
                else:
                    relative = path.removeprefix("Assets/")
                    if path.startswith('Library/') or not any((root / relative).is_file()
                            for root in (assets_root, assets_root.parent / "Assets")):
                        issues.append(f"{kc}: diagram {path} not rendered")
                if lesson_display:
                    _verified_display_diagram(catalog, path)
                    if path not in _card_display_paths({"teach": {kc: card}}):
                        issues.append(f"{kc}: diagram {path} lacks an accessible card description")
                elif not _diagram_embedded(path, note_text, catalog):
                    issues.append(f"{kc}: diagram {path} not embedded in note")
            except (OSError, ValueError) as exc:
                issues.append(f'{kc}: diagram {path} unavailable: {exc}')
    return issues


def _written_diagram_resolver():
    """Fresh, lazy catalog for one extraction; no catalog survives the call."""
    assets = ROOT / 'build/out/assets'
    loaded, catalog, failure = False, None, None
    def resolve(reference: str) -> Path:
        nonlocal loaded, catalog, failure
        if not loaded:
            loaded = True
            try:
                catalog = _diagram_catalog(assets)
            except (OSError, ValueError, KeyError) as exc:
                failure = exc
        if failure is not None:
            raise failure
        if catalog is not None:
            return _catalog_diagram(catalog, reference)
        # Disposable legacy fixtures have an explicit assets root, never a Library alias.
        if (not isinstance(reference, str) or not reference.startswith('Assets/')
                or '..' in Path(reference).parts or '\\' in reference):
            raise ValueError('invalid or unregistered review diagram')
        return assets / reference.removeprefix('Assets/')
    return resolve


def _written_diagram(reference: str) -> Path:
    """Compatibility single resolution; inventories use a fresh shared resolver."""
    return _written_diagram_resolver()(reference)


def written_review_problems(sub: str, pack: dict, *, defer_missing: bool = False) -> list[str]:
    """Signing requires the shared exact inventory and durable independent evidence."""
    import written_review
    try:
        items = written_review.pack_review_items(pack, diagram_resolver=_written_diagram_resolver())
    except (ValueError, TypeError) as exc:
        return [f'invalid written review inventory: {exc}']
    if not items:
        return []
    work = LOCATIONS.work('refine')
    try:
        records = json.loads((work / f'{sub}.written-review.json').read_text())
    except FileNotFoundError:
        return [] if defer_missing else [f'{len(items)} written checks need review records']
    except (OSError, ValueError):
        return ['written review records are unreadable or malformed']
    if defer_missing and isinstance(records, dict):
        items = [item for item in items if item['id'] in records]
        if not items:
            return []
    return written_review.independent_record_problems(items, records, root=ROOT, work=work, blind=BLIND)


def gates(sub: str, *, candidate_pack: Path | None = None, candidate_note: Path | None = None, lesson_display: bool = False,
          candidate_teach: Path | None = None, defer_written: bool = False, defer_missing_written: bool = False) -> dict:
    import validate_pack
    from tutorlib import lint

    p = candidate_pack or pack_path(sub)
    if not p.exists():
        return {"ok": False, "pack": "missing"}
    pack = json.loads(p.read_text())
    graph = json.loads((SPECS / spec_of(sub) / "graph.json").read_text())
    problems = validate_pack.validate(pack, graph)
    note = candidate_note or note_path(pack, sub)
    text = note.read_text(encoding="utf-8") if note.is_file() else ""
    findings = lint.lint(text) if note.is_file() else [{"rule": "note", "detail": "missing"}]
    gaps = syllabus_gaps(sub, pack, graph, text)
    import library
    import content_checks
    figures = (link_problems(text) + diagram_problems(pack, graph, text, lesson_display=lesson_display) + library.figure_problems(text, sub)) if note.is_file() else []
    figures += content_checks.letter_problems(pack) + content_checks.latex_problems(pack) + content_checks.debris_problems(pack) + content_checks.stacked_problems(pack) + content_checks.precision_problems(pack) + content_checks.id_problems(pack) + content_checks.chemical_spacing_problems(pack)
    figures += speech_problems(sub)
    glyph_list = glyph_problems(pack, text)
    contract = candidates.state_paths(STATE, sub).get("teaching_contract")
    guided_pack = pack
    required = contract == "guided-v1"
    if required and "guided_forms" not in pack:
        guided_pack = {**pack, "guided_forms": {}}
    guided = guided_problems(guided_pack, graph, text, ROOT / "build/out/assets", lesson_display=lesson_display)
    if required and "guided_forms" not in pack:
        guided.insert(0, "guided-v1 preparation requires a reviewed guided_forms inventory")
    guided += guided_draft_problems(candidate_teach or ROOT / "build/work/teach" / f"{sub}.json", pack, graph)
    if not defer_written:  # a refine pass reviews written checks after the refiner; signing never defers
        guided += (written_review_problems(sub, pack, defer_missing=True) if defer_missing_written
                   else written_review_problems(sub, pack))
    out = {"ok": not problems and not findings and not gaps and not figures and not glyph_list and not guided, "validator": len(problems),
           "lint": len(findings), "syllabus": len(gaps), "figures": len(figures), "glyphs": len(glyph_list),
           "guided": len(guided),
           "items": len(pack.get("items", [])), "extra": sum(it.get("tier") == "extra" for it in pack.get("items", []))}
    if problems or findings or gaps or figures or glyph_list or guided:  # enough for a worker to act on, capped so the board stays small
        out["first"] = [f"{e['rule']} {e['where']} {e.get('detail', '')}"[:160] for e in problems[:8]] + \
                       [f"lint {x.get('rule')} line {x.get('line')}: {x.get('message') or x.get('detail', '')}"[:160]
                        for x in findings[:4]] + \
                       [f"syllabus {e['rule']} {e['where']} {e['detail']}"[:160] for e in gaps[:8]] + \
                       [f"figures {e}"[:200] for e in figures[:6]] + [f"glyphs {e}"[:200] for e in glyph_list[:4]] + \
                       [f"guided {e}"[:200] for e in guided[:8]]
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


def _require_mutable_output(path: Path) -> None:
    """Collector repairs may write Work files, never immutable Library adapters."""
    if path.is_symlink() or candidates.library_backed(path):
        raise ValueError(f"immutable Library resource or file adapter: {path}; prepare an isolated candidate")


def restore_extras(sub: str, known: dict) -> dict:
    """Re-append the past-paper extras with the ids they had: a worker that re-runs the generator rewrites the pack
    without them. Returns the ids to remember."""
    if not pack_path(sub).exists():
        return known
    _require_mutable_output(pack_path(sub))
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
    _require_mutable_output(p)
    import teach_cards
    pack = json.loads(p.read_text())
    graph = json.loads((SPECS / spec_of(sub) / "graph.json").read_text())
    kcs = {k["id"] for k in graph["kcs"] if k["subtopic"] == sub}
    staged = json.loads(cards.read_text())
    if any(teach_cards.is_guided(card) for card in staged.values()) and (
            set(staged) != kcs or any(teach_cards.check_card(kc, card, guided=True)
                                      for kc, card in staged.items())):
        return  # do not replace existing cards with a partial or malformed guided draft
    good = {kc: card for kc, card in staged.items()
            if kc in kcs and not teach_cards.check_card(kc, card, guided=teach_cards.is_guided(card))}
    pack["teach"] = teach_cards.merge_cards(pack.get("teach") or {}, good)
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
                note = note_path(pack, sub)
                rules = [e["rule"] for e in syllabus_gaps(sub, pack, g, note.read_text(encoding="utf-8")
                                                          if note.is_file() else "")]
                if rules:
                    out["holes"][sub] = {r: rules.count(r) for r in sorted(set(rules))}
        out["specs"][g["spec"]] = tally
        if (REPO / "build/raw").exists() and ROOT == REPO:  # the syllabus documents as extracted, outcome by outcome
            official = syllabus.official(g["spec"])
            problems = syllabus.audit(official, g) if official else [{"rule": "not-extracted", "where": g["spec"]}]
            out["audit"][g["spec"]] = [f"{e['rule']} {e['where']}" for e in problems]
    out["speech_gaps"] = pregen.gaps_report()  # read-aloud lines with no spoken form (shown, never a gate)
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
    own = sorted(f.stem for f in STATE.glob("*.json") if f.stem[:1].isalnum() and
                 load(f.stem).get("stage") == "ready" and load(f.stem).get("same_family"))
    if own:
        print(f"\nSigned with only its own family checking it (re-check with the other allowance when it is free): "
              f"{len(own)}: {' '.join(own)}")
    import diagram_hints
    bare = []
    for g in sorted((SPECS).glob("*/graph.json")):
        graph = json.loads(g.read_text())
        for s in graph["subtopics"]:
            pk = pack_path(s["id"])
            if pk.exists() and diagram_hints.suggest([k for k in graph["kcs"] if k["subtopic"] == s["id"]]):
                d = json.loads(pk.read_text())
                if not d.get("diagrams") and not d.get("diagrams_skipped"):
                    bare.append(s["id"])
    if bare:
        print(f"\nBuilt chapters with points a figure shows and no diagram ({len(bare)}; the next drafts get them, these "
              f"need a redraft to): {' '.join(bare)}")
    pregen.print_gaps()
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
        mid = next((r for r in _refine_chapters() if r.get("sub") == sub and r.get("stage") != "ready"), None)
        if mid:  # two systems must not rewrite one chapter at once
            print(f"{sub}: refine is working on it now ({mid['stage']}); add it here when that pass is done")
            continue
        STATE.mkdir(parents=True, exist_ok=True)
        start = "solve" if pack_path(sub).exists() and stage == "draft" else stage  # an existing pack is re-checked
        st = {"sub": sub, "teaching_contract": "guided-v1", "stage": start, "created": now(), "updated": now(), "history": [], "gates": None,
              "disputes": [], "findings": [], "fixes": [], "jobs": {}, "extra_ids": extra_ids(sub)}
        path.write_text(json.dumps(st, indent=1))
        if not (ROOT / "build/work/bundles" / f"{sub}.md").exists() and (REPO / "build/bundle.py").exists():
            subprocess.run([PY, str(REPO / "build/bundle.py"), sub], cwd=ROOT, capture_output=True)
        if sub not in (json.loads(HOLD.read_text()) if HOLD.exists() else {}):  # keep an existing reason
            hold(sub, "in the foundry: not signed off yet")
        print(f"{sub}: added at {start}")


def _running(st: dict) -> list[str]:
    return lifecycle.running_jobs(st, is_alive=_alive)


def _busy() -> dict[str, list[str]]:
    """The jobs running now on each allowance, across every chapter."""
    out: dict[str, list[str]] = {}
    for st in chapters() + _refine_chapters():  # the refine system shares the two allowances' slots
        for name in _running(st):
            out.setdefault(st["jobs"][name].get("provider", "codex"), []).append(name)
    return out


def _refine_chapters() -> list[dict]:
    """The refine system's chapters (refine/state), read-only: what it is running counts against the same slots."""
    out = []
    for f in sorted((ROOT / "refine/state").glob("*.json")) if (ROOT / "refine/state").is_dir() else []:
        try:
            out.append(json.loads(f.read_text()))
        except ValueError:
            pass
    return out


def maker_of(st: dict) -> str | None:
    """The allowance (so the AI family) that drafted this chapter, when that is known."""
    return st.get("maker") or ("codex" if st["jobs"].get("drafter", {}).get("model", "").startswith("gpt") else None)


def _since(st: dict) -> float:
    return lifecycle.stage_started(st)


def _done(st: dict, name: str) -> bool:
    return lifecycle.job_completed(st, name, ROOT)


def _solver_jobs(st: dict) -> list[str]:
    """The solver jobs this round needs, one per shard of the questions file; none before it has been written."""
    sub, pfx = st["sub"], _pfx(st)
    if not (BLIND / f"{sub}.{pfx}questions.json").exists():
        return []
    parts = sorted(int(p.stem.rsplit("part", 1)[1]) for p in BLIND.glob(f"{sub}.{pfx}questions.part*.json"))
    return [f"solver#{k}" for k in parts] or ["solver"]


def _alive(pid: int | None) -> bool:
    return lifecycle.process_alive(pid)


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
    pregen.print_gaps()


def _tiebroken(st: dict) -> bool:
    return lifecycle.tiebreak_completed(st)


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


MAX_UNCLEAN = 3  # consecutive attempts that end with the gates red before the foundry stops retrying a chapter


def unclean_streak(st: dict) -> int:
    """How many of the latest history entries, in a row, say a worker finished with the gates not clean."""
    n = 0
    for h in reversed(st["history"]):
        if "gates are not clean" not in h.get("note", ""):
            break
        n += 1
    return n


def cmd_unstick(sub: str) -> None:
    """Let a chapter that stopped retrying (its gates stayed red) explicitly clear its failure allowance."""
    with chapter(sub) as st:
        reliability.clear_failures(st, 'explicit manager unstick')
        st["history"].append({"t": now(), "from": st["stage"], "to": st["stage"], "note": "unstuck by the manager"})
    print(f"{sub}: failure allowance cleared; shared two-failure guard still applies")


def cmd_step(only: list[str] | None = None) -> None:
    """One pass over every chapter (or only those named) doing whatever needs no judgement: start the workers that can
    run now, compare finished solves, sign what is green. What it leaves is the manager's: decisions, and waiting."""
    import capabilities
    if (why := capabilities.preflight()):  # a tool the workers need is missing: say so, do not run on without it
        print(why)
        return
    for st in chapters():
        sub, (verb, *rest) = st["sub"], todo(st)
        if only and sub not in only:
            continue
        if st["stage"] in ("draft", "fix") and not _running(st) and unclean_streak(st) >= MAX_UNCLEAN:
            print(f"{sub}: stuck: its gates were red {unclean_streak(st)} times in a row ({st['history'][-1].get('note', '')[-150:]}); "
                  f"not retrying. Fix it by hand or `foundry.py unstick {sub}` after repairing the blocker.")
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
        except (SystemExit, ValueError, OSError) as e:
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


def read_answers(path: Path) -> dict:
    """A solver's answers file. One that ends with a literal backslash-n after the object (a worker wrote the two
    characters instead of a newline) is read all the same; anything else wrong is named, not a traceback."""
    text = path.read_text().strip()
    try:
        data, end = json.JSONDecoder().raw_decode(text)
    except ValueError as e:
        raise SystemExit(f"{path.name}: not readable ({e}); re-run the solver for this shard") from None
    if not isinstance(data, dict) or text[end:].replace("\\n", "").strip():
        raise SystemExit(f"{path.name}: not a single answers object; re-run the solver for this shard")
    return data


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
            answers = read_answers(BLIND / f"{sub}.answers.json") if pfx and \
                (BLIND / f"{sub}.answers.json").exists() else {}
            for f in files:  # every solver's shard
                answers.update(read_answers(f))
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
            if st['jobs'].get('tiebreak') and not _tiebroken(st):
                raise SystemExit(f'{sub}: tiebreak has not completed a validated review in this round')
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


def normalise_figures(sub: str) -> int:
    """A past-paper question whose options came out of the PDF empty keeps its figure and loses its options (the key
    letter stays, as in 2.0.0): the mechanical repair, made at signing so a chapter does not ship with blank options.
    The correction is also noted in build/work/mcq/overrides.json so a rebuild keeps it. Returns how many."""
    path = pack_path(sub)
    if not path.exists():
        return 0
    raw = path.read_text()
    pack, fixed = json.loads(raw), {}
    for it in pack.get("items", []):
        o = it.get("options")
        qid = (it.get("source") or {}).get("qid") or (it.get("source") or {}).get("ref")
        if it.get("kind") == "mcq" and isinstance(o, dict) and it.get("image") and qid \
                and any(not str(v).strip() for v in o.values()):
            it["options"] = None
            fixed[qid] = {"options": None}
    if fixed:
        path.write_text(json.dumps(pack, ensure_ascii=False, indent=1) + ("\n" if raw.endswith("\n") else ""))
        ov = ROOT / "build/work/mcq/overrides.json"
        ov.parent.mkdir(parents=True, exist_ok=True)
        data = json.loads(ov.read_text()) if ov.exists() else {}
        for qid, change in fixed.items():
            data.setdefault(qid, {}).update(change)
        ov.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n")
    return len(fixed)


def cmd_normalise(subs: list[str]) -> None:
    """foundry.py normalise [chapters…]: the signing repair for chapters already signed (all signed ones when none named)."""
    for s in subs or [f.stem for f in sorted(STATE.glob("*.json")) if f.stem[:1].isalnum() and load(f.stem)["stage"] == "ready"]:
        if n := normalise_figures(s):
            print(f"{s}: {n} figure questions now show the figure without blank options")


def cmd_sign(sub: str) -> None:
    remaining(sub)
    ensure_candidate(sub)
    normalise_figures(sub)
    g, _ = settle_glyphs(sub, gates, chapter)
    with chapter(sub) as st:
        st["gates"] = g
        open_ = [d["id"] for d in st["disputes"] if d["status"] == "open"] + \
                [f["ref"] for f in st["findings"] if f["status"] == "open"] + \
                [f["ref"] for f in st["fixes"] if f["status"] == "open"]
        stage = st["stage"]  # at "check" only once the checker has reported, with nothing open
        ready = g["ok"] and not open_ and (stage == "sign" or (stage == "check" and bool(st.get("checked"))))
        if ready:
            published = publish_candidate(sub)
            st["publication"] = {"published": published, "at": now()}
            with notes() as n:  # signed with only its own family to check it: said so, to be re-checked by the other
                st["same_family"] = bool(n.get("only")) and n.get("only") == maker_of(st)
            st["prepared_at"] = now()
            st["content_sha256"] = lifecycle.content_fingerprint(pack_path(sub), note_path(json.loads(pack_path(sub).read_text()), sub))
            move(st, "ready", "signed off" + (" (checked only by its own family)" if st["same_family"] else ""))
    if not ready:  # raised outside the block so the gate results are saved: the drafter's prompt lists the failures
        raise SystemExit(f"{sub}: not ready (stage {stage}, gates {g}, open {open_})")
    hold(sub, None)
    release(sub, published=published)
    speech_after_sign(sub)


def speech_after_sign(sub: str, state=None, logs: Path | None = None) -> None:
    """Read-aloud audio for the signed chapter, started in the background; never blocks or fails the sign-off."""
    state = state or chapter

    def note(text: str) -> None:
        with state(sub) as st:
            st["history"].append({"t": now(), "from": st["stage"], "to": st["stage"], "note": text})

    pregen.hook(sub, logs or LOGS, note=note)


def chapter_paths(sub: str) -> list[str]:
    """Everything that belongs to one chapter, relative to the repo: what a sign-off commits."""
    pack = json.loads(pack_path(sub).read_text())
    found = [pack_path(sub), note_path(pack, sub), STATE / f"{sub}.json", HOLD,
             ROOT / "build/work/mcq/overrides.json", ROOT / "build/work/teach" / f"{sub}.json"]
    found += list((ROOT / "build/work/gen").glob(f"{sub}*")) + list((ROOT / "build/out/Assets").glob(f"*/{sub}-*"))
    found += list(BLIND.glob(f"{sub}.*")) + list(WORK.glob(f"{sub}.*"))
    return candidates.owned_paths(ROOT, found)


def publish_candidate(sub: str) -> bool:
    """Publish the explicitly checked candidate before changing board/hold state."""
    cfg = config()
    if not (cfg.get("publish_on_sign", True) and os.environ.get("FOUNDRY_PUBLISH", "1") == "1"):
        return False
    vault = os.environ.get("STEM_TUTOR_VAULT")
    r = subprocess.run([PY, str(REPO / "build/publish.py"), "--build-root", str(ROOT / "build/out"),
                        "--candidate", sub, str(pack_path(sub)),
                        str(note_path(json.loads(pack_path(sub).read_text()), sub)),
                        *(["--vault", vault] if vault else [])], cwd=REPO, capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(f"{sub}: PUBLISH FAILED: {r.stderr.strip()[-300:]}")
    print(f"{sub}: published into the vault {r.stdout.strip()[-120:]}")
    return True


def release(sub: str, *, published: bool | None = None) -> None:
    """Checkpoint and report actual delivery after successful publication."""
    if published is None:
        published = publish_candidate(sub)
    cfg = config()
    if cfg.get("commit_on_sign", True) and os.environ.get("FOUNDRY_COMMIT", "1") == "1":
        result = candidates.checkpoint(ROOT, chapter_paths(sub),
                                      f"content({sub}): signed off in the foundry", run=subprocess.run)
        print(f"{sub}: {result}")
    notify(f"{sub} is ready to study in your vault" if published else
           f"{sub}: signed candidate ready; publication disabled")
    print(f"{sub}: ready" + (" in the vault" if published else " as an unpublished candidate"))


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
        lines.append(f"Chapter files: editable pack {pack_path(sub)}, note {note_path(json.loads(pack_path(sub).read_text()), sub) if pack_path(sub).is_file() else 'pending'}, bundle build/work/bundles/{sub}.md.")
    if role == "checker":
        report = (ROOT / _expects(st, role, shard)).absolute()
        lines.append(f"Prepare report directory: `{shlex.join(['mkdir', '-p', '--', str(report.parent)])}`.")
        lines.append(f"Report file: {report}. In shell commands use this entire quoted operand: {shlex.quote(str(report))}.")
    if role == "tiebreak":
        lines.append("Disputed question ids: " + ", ".join(d["id"] for d in st["disputes"] if d["status"] == "open"))
    if role == "fixer":
        lines.append("Fixes to make (from the manager):\n" + "\n".join(
            f"- {f['ref']}: {f['instruction']}" for f in st["fixes"] if f["status"] == "open"))
    if role in ("fixer", "drafter") and st.get("gates") and not st["gates"].get("ok"):
        lines.append("Gate failures to clear: " + "; ".join(st["gates"].get("first", [])))
    if role == "adjudicator":
        lines.append(f"Open items: run `.venv/bin/python foundry/foundry.py packet {sub}`.")
    import evidence
    lines += evidence.prompt_lines(role, sub, config())
    return "\n".join(lines)


@lifecycle.serialized_launch(lambda *args, **kwargs: STATE)
def cmd_prompt(role: str, sub: str, shard: int | None = None) -> None:
    remaining(sub)
    ensure_candidate(sub)
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


@lifecycle.serialized_launch(lambda *args, **kwargs: STATE)
def cmd_run(role: str, sub: str, on: str | None = None, shard: int | None = None) -> None:
    """Start one headless worker on a chapter. The router picks the allowance (unless `on` names it) and the tier."""
    cfg = config()
    if role not in cfg["ladders"]:
        raise SystemExit(f"{role} is not a worker role (roles: {', '.join(cfg['ladders'])})")
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
    if role == 'drafter' and not pack_path(sub).exists():
        inputs.remove(pack_path(sub))  # a genuinely new chapter has no pack yet
    if why := reliability.launch_problem(st, role, inputs, diagram_catalog=_diagram_catalog(ROOT / "build/out/assets")):
        raise SystemExit(f'{sub}: {why}')
    import capabilities
    if why := capabilities.preflight():
        raise SystemExit(why)
    last = st["jobs"].get(name, {})
    with notes() as n:
        if on and n.get("only") and on != n["only"]:
            raise router.Wait(f"provider preference is only {n['only']}")
        provider = router.pick(role, maker_of(st), router.usage(n, CODEX, CLAUDE), cfg, _busy(), only=on or n.get("only"))
        failed = last.get("provider") == provider and last.get("ok") is False and not last.get("limit")
        rung = router.rung(n, cfg, role, provider, retry=last.get("rung", 0) if failed else None)
    model, effort = cfg["ladders"][role][provider][rung]
    if role == "drafter":  # a worker is about to start: give it the newest link names, diagram hints and library hits
        import evidence
        evidence.refresh_bundle(ROOT, PY, sub)
    with chapter(sub) as st:  # so collect can put the extras back with the same ids if the worker rewrites the pack
        st["extra_ids"] = {**st.get("extra_ids", {}), **extra_ids(sub)}
    LOGS.mkdir(parents=True, exist_ok=True)
    stem = f"{sub}.{name.replace('#', '-')}.{datetime.now():%m%d-%H%M%S}"
    log, out, expects = LOGS / f"{stem}.log", LOGS / f"{stem}.out.json", _expects(st, role, shard)
    prompt, schema = role_prompt(role, sub, shard), HERE / "schemas" / f"{role}.json"
    web = role in cfg.get("web", [])  # roles allowed to browse the internet (the learner's library comes first)
    if provider == "codex":
        worker = [CODEX, *(["--search"] if web else []), "exec", "-m", model, "-c", f'model_reasoning_effort="{effort}"',
                  "-c", 'approval_policy="never"',
                  "-s", "workspace-write", "-C", str(REPO), "--color", "never",
                  *(["--output-schema", str(schema)] if schema.exists() else []), "-o", str(out), prompt]
    else:  # lean: none of the learner's plugins, skills, hooks or MCP servers, so a job costs only what the job needs
        worker = [CLAUDE, "-p", prompt, "--model", model, *(["--effort", effort] if effort else []), *router.LEAN,
                  "--tools", "Read,Write,Edit,Bash,Glob,Grep" + (",WebSearch,WebFetch" if web else ""), "--permission-mode",
                  "acceptEdits", "--allowedTools", "Bash(.venv/bin/python *)", *(["WebSearch", "WebFetch"] if web else []),
                  *(["--json-schema", schema.read_text()] if schema.exists() else [])]
    authoring = [WORK, BLIND, STATE, LOGS, ROOT / "build/work/teach", ROOT / "build/work/gen",
                 ROOT / "build/work/mcq", ROOT / "build/out/assets", ROOT / "build/out/Assets"]
    for key in ("candidate_pack", "candidate_note"):
        if st.get(key):
            authoring.append(Path(st[key]).parent)
    worker += candidates.writable_flags(authoring)
    left = remaining(sub, start=True)
    if left is not None:
        worker = [PY, str(REPO / "src/tutor_workers/timeout.py"), str(left), *worker]
    then = [PY, str(HERE / "foundry.py"), "collect", name, sub, str(out)]
    shell = (f"{shlex.join(worker)} < /dev/null > {shlex.quote(str(log))} 2>&1; "
             f"{shlex.join(then)} $? >> {shlex.quote(str(log))} 2>&1")
    tier = f"{model}/{effort}" if effort else model
    with chapter(sub) as st:
        if role == "drafter":
            st["maker"] = provider  # the other family blind-solves what this one writes
        st["jobs"][name] = {"pid": None, "provider": provider, "model": tier, "rung": rung, "started": now(),
                            "failure_input": reliability.fingerprint(st, role, inputs),
                            "log": str(log.relative_to(ROOT)), "out": str(out.relative_to(ROOT)),
                            **({"expects": expects} if expects else {})}
    try:
        proc = subprocess.Popen(["/bin/sh", "-c", shell], cwd=REPO, start_new_session=True, stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL,
                                env={**os.environ, "FOUNDRY_ROOT": str(ROOT), "FOUNDRY_EXPECTS": str(ROOT / expects) if expects else "",
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
        for name, w in router.usage_windows(u.get(p)):
            reset = router.usage_reset(w.get('resets'))
            resets = f"resets {datetime.fromtimestamp(reset):%a %H:%M}" if reset else "no reset time"
            kept = f" ({cfg['reserve'][p]}% kept back)" if cfg["reserve"].get(p) and name == "seven_day" else ""
            used = router.usage_percent(w.get('used'))
            reading = f"{used:>3.0f}% used" if used is not None else "usage unknown"
            out.append(f"{NAMES[p]:<7} {words.get(name, name):<10} {reading}  {resets}{kept}")
        if not u.get(p):
            out.append(f"{NAMES[p]:<7} not known yet (it is read from the first worker that runs)")
        elif p == "claude" and "five_hour" not in u[p]:  # a headless run is told only of the limit nearest its end
            out.append(f"{NAMES[p]:<7} {'5 hours':<10} not reported by Claude (pass it on: foundry reading claude "
                       "five_hour <percent> <reset time>)")
        elif p == "codex" and "five_hour" not in u[p]:  # some plans report a week only
            out.append(f"{NAMES[p]:<7} {'5 hours':<10} not reported by Codex for this plan: used the moment Codex "
                       "reports one; a job that hits it pauses Codex until it reopens")
    with notes() as n:
        only = n.get("only")
    if only:
        out.append(f"mode: only {NAMES[only]} is used (`foundry only off` to use both)")
    try:
        out.append(f"next job: {NAMES[router.pick('drafter', None, u, cfg, _busy(), only=only)]} (more of its week left for the "
                   "time until it resets); a chapter's blind solve goes to the one that did not draft it")
    except router.Wait as e:
        out.append(f"next job: none can start ({e})")
    return out


def cmd_usage() -> None:
    print("\n".join(usage_lines()))


def cmd_only(rest: list[str]) -> None:
    """`only codex|claude` keeps every job on that allowance (the maker may then check its own work: such chapters
    are marked and listed by `coverage` for a re-check by the other family); `only off` goes back to using both."""
    want = rest[0] if rest else ""
    if want not in ("codex", "claude", "off"):
        raise SystemExit("usage: foundry.py only codex|claude|off")
    with notes() as n:
        if want == "off":
            n.pop("only", None)
        else:
            n["only"] = want
    print("both allowances are used again" if want == "off" else
          f"only {NAMES[want]} is used from now on; chapters it drafted are checked by it too, and are marked for a "
          "re-check by the other allowance")


def cmd_reading(provider: str, window: str, used: str, resets: str = "") -> None:
    """Tell the foundry a figure it cannot read itself. Claude tells a headless run about one limit only, the one
    nearest its end, so its five-hour window is usually unknown here; the Claude app's usage card shows it:
    `foundry.py reading claude five_hour 74 2026-10-02T17:59:59Z`."""
    if provider != "claude":
        raise SystemExit("only Claude's figures need passing on: Codex is asked directly")
    when = datetime.fromisoformat(resets.replace("Z", "+00:00")).timestamp() if resets else None
    with notes() as n:
        router._reading(n.setdefault("claude", {}), window, float(used), when, time.time(), exact=True)
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


@reliability.collect_safely(lambda sub: chapter(sub))
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
    try:
        if role in ("drafter", "fixer") and exit_code == 0:  # what a re-run generator leaves out of the pack
            _require_mutable_output(pack_path(sub))
            _require_mutable_output(note_path(json.loads(pack_path(sub).read_text()), sub))
            with chapter(sub) as st:
                st["extra_ids"] = restore_extras(sub, st.get("extra_ids", {}))
            merge_teach(sub)
        g = settle_glyphs(sub, lambda chapter: gates(chapter, defer_missing_written=True), chapter)[0] if role in ("drafter", "fixer") and exit_code == 0 else None  # only these two change the chapter
    except Exception as exc:  # collection must persist a failure, never orphan a finished worker
        g = {'ok': False, 'collection': 1, 'first': [f'collection {type(exc).__name__}: {exc}']}
    wrote = True
    if job.get("expects"):
        f = ROOT / job["expects"]
        wrote = f.exists() and f.stat().st_mtime >= datetime.fromisoformat(job["started"]).timestamp() - 1
        if wrote and (problem := reliability.output_problem(f, role)):
            wrote = False
    import evidence
    evid = evidence.missing(role, sub, config(), ROOT / job["log"] if job.get("log") else None) \
        if exit_code == 0 and report and out != "-" else []
    if evid:
        g = {**(g or {"ok": True}), "ok": False, "sources": len(evid), "first": [f"sources {m}"[:200] for m in evid] + (g or {}).get("first", [])}
    ok = exit_code == 0 and bool(report) and wrote and (g is None or g["ok"])
    if out != "-":
        with notes() as n:
            codex = provider == "codex" and limit  # Codex's own figures (free to ask) and its message say when it reopens
            router.record(n, config(), role, provider, job.get("rung", 0), ok=ok, limit=limit,
                          cost=facts.get("cost", 0.0), windows=router.codex_usage(CODEX) if codex else facts.get("windows"),
                          judge=not (role == "solver" and ok),  # a solver is judged by its answers, at compare
                          until=router.reset_from_message(said) if codex else None)
    if role not in ("solver", "checker"):
        notify(f"{sub}: {role} " + ("finished" if exit_code == 0 and report else "failed")
               + (" · gates ok" if g and g.get("ok") else ""))
    with chapter(sub) as st:
        if g is not None:
            st["gates"] = g
        job = st["jobs"].get(name, {})
        job.update(finished=now(), exit=exit_code, report=report, ok=ok, **({"limit": True} if limit else {}),
                   **({"cost_usd": round(facts["cost"], 3)} if facts.get("cost") else {}))
        reliability.record_result(st, name, ok=ok, exit_code=exit_code,
                                  issues=(g or {}).get('first', []) or ([] if ok else ['invalid worker output or failed exit']))
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
    if cmd == "new-run":
        print(json.dumps(lifecycle.new_course_run(STATE, rest[0], 7200, states=chapters), indent=1))
    elif cmd == "add":
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
    elif cmd == "doctor":
        import capabilities
        text, ok = capabilities.report()
        print(text)
        if not ok:
            raise SystemExit(1)
    elif cmd == "unstick":
        cmd_unstick(rest[0])
    elif cmd == "only":
        cmd_only(rest)
    elif cmd == "normalise":
        cmd_normalise(rest)
    elif cmd == "reading":
        cmd_reading(*rest)
    elif cmd == "queue":
        cmd_queue(rest[0], rest[1:])
    elif cmd == "wait":
        cmd_wait(*(float(x) for x in rest[:1]))
    elif cmd == "coverage":
        cmd_coverage(rest)
    elif cmd == "tts":
        if pregen.cli(rest):
            sys.exit(1)
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
