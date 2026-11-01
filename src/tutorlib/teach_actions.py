"""The teaching actions the learning AI may ask for, and the program that checks and carries them out.

The AI never touches files and never draws SVG: it names an action from this list with small arguments. The one
thing it writes is the `write` action's explanation, which the screen requests in the program's standard document
format (learn_write) and labels as the tutor's own. `run` checks every request against the rules below and returns plain cards for the screen (and
Now / the lesson log) to draw in the usual way; anything that needs the learner (a hint, a check, a question) comes
back as a `ui` request for the existing handler. While a question is open or a skipped answer is protected, nothing
that could carry an answer is returned at all (`blocked`).

An action is only a request: whether the AI picks a sensible one is not guaranteed by this module.
"""
from __future__ import annotations

from .card_diagrams import diagram_descriptions

import hashlib
import io
import json
import re
import sys
from pathlib import Path

from . import views
from .asset_library import AssetLibrary, write_asset
from .library_refs import LibraryRefs
from .saved_figures import require_runtime_library

SECTIONS = ("plain_words", "establish", "connect", "self_explain")
SECTION_TITLE = {"plain_words": "In plain words", "establish": "The idea in more detail",
                 "connect": "How it connects", "self_explain": "In your own words"}
DIAGRAM_TYPES = {  # type: allowed `params` keys (build/PACK.md lists what each means)
    "graph_sketch": {"lines", "xlabel", "ylabel", "shade", "annotations", "ticks", "hide_axes", "equal_aspect"},
    "function_plot": {"functions", "asymptotes", "points", "xlim", "ylim", "xlabel", "ylabel"},
    "box_plot": {"min", "q1", "median", "q3", "max", "outliers", "labels", "xlabel", "ticks"},
    "density_panels": {"panels", "mark_centres", "xlabel"},
    "free_body": {"body", "incline_deg", "forces"},
    "energy_profile": {"reactants", "products", "ea", "catalysed_ea", "reactants_label", "products_label",
                       "ea_label", "dh_label"},
    "maxwell_boltzmann": {"temps", "labels", "ea", "shade_ea"},
    "wave": {"amplitude", "wavelength", "cycles", "show_amplitude", "show_wavelength", "xlabel", "ylabel"},
    "circuit": {"elements"},
    "case_split": {"start", "cases", "end"},
    "proof_flow": {"steps"},
}
ACTIONS = {
    "explain": "show one section of this idea's card: section = plain_words | establish | connect | self_explain",
    "term": "show a term with its meaning, notation and how to say it: term = a term from the list",
    "example": "show the worked example of a question form: form = its number in the list",
    "diagram": "show a figure: source = card (a diagram of this idea) | notes (a figure cropped from the learner's "
               "notes PDFs) | generated (a new one: type + params)",
    "check": "give the learner the short check for a question form: form = its number",
    "question": "give the learner one past-paper question on this idea (the program picks an eligible one)",
    "hint": "offer the next hint for the question on screen",
    "write": "when nothing on the card fits this learner's question, have a short new explanation or example written: "
             "just the topic (a few words): the program then asks you to write it in its standard format and checks any "
             "plain algebra or arithmetic in it",
    "note": "add a short note to the learner's lesson notes: text, at most 400 characters",
    "review": "put a term of this idea into the review queue: term = the term",
}
SHOWS_CONTENT = {"explain", "term", "example", "diagram", "write"}  # what could carry an answer: held back while one is open
MAX_ACTIONS = 4

SCHEMA = {"type": "object", "properties": {"actions": {"type": "array", "items": {
    "type": "object", "properties": {"action": {"type": "string", "enum": list(ACTIONS)}, "section": {"type": "string"},
                                     "term": {"type": "string"}, "form": {"type": "integer"},
                                     "source": {"type": "string"}, "figure": {"type": "string"},
                                     "type": {"type": "string"}, "params": {"type": "object"},
                                     "text": {"type": "string"}, "why": {"type": "string"}, "topic": {"type": "string"}},
    "required": ["action"]}}}, "required": ["actions"]}


def _repo() -> Path:
    # Source imports and legacy symlink imports resolve to src/tutorlib. An
    # installed engine may instead bundle build/diagrams.py beside tutorlib.
    # Never infer a checkout from a fixed parent count: an exported engine is
    # deliberately self-contained and may have no diagram renderer installed.
    for parent in Path(__file__).resolve().parents:
        if (parent / "build/diagrams.py").is_file():
            return parent
    raise RuntimeError("diagram renderer is not included in this engine installation")


def figures_for(vault_root: Path, subtopic: str, *, kc: str | None = None, card: dict | None = None) -> list[dict]:
    """Verified teaching figures with explicit chapter, KC or current-card binding.

    File names and matching image bytes never establish teaching relevance.
    Catalog registration establishes availability, not content approval.
    """
    out = []
    root = Path(vault_root)
    card = card or {}
    course = subtopic.split('-', 1)[0]
    if (root / 'Library/catalog.json').exists() or (root / 'Library/catalog.json').is_symlink():
        library = AssetLibrary(root)
        card_paths = {}
        descriptions = diagram_descriptions(card)
        for position, reference in enumerate(card.get('diagrams') or []):
            try:
                path = library.resolve(reference).relative_to(root.resolve()).as_posix()
                card_paths[path] = descriptions[position] if position < len(descriptions) else ''
            except (OSError, ValueError, TypeError):
                continue

        def bound(meta):
            return (meta.get('subtopic') == subtopic or meta.get('chapter') == subtopic
                    or any(isinstance(meta.get(key), list) and subtopic in meta[key] for key in ('subtopics', 'chapters'))
                    or bool(kc and (meta.get('kc') == kc or isinstance(meta.get('kcs'), list) and kc in meta['kcs'])))

        for identifier, entry in library.records().items():
            path = entry['path']
            if (Path(path).suffix.lower() not in {'.svg', '.png', '.jpg', '.jpeg'}
                    or not path.startswith((f'Library/Courses/{course}/Diagrams/', 'Library/Shared/Diagrams/'))
                    or entry.get('course', course) != course):
                continue
            try:
                data = library.read(f'asset:{identifier}')
            except (OSError, ValueError):
                continue
            provenance = entry.get('provenance')
            provenance = provenance if isinstance(provenance, dict) else {}
            sidecars = provenance.get('sidecars', [])
            metadata = [entry] if bound(entry) or path in card_paths else []
            for reference in sidecars if isinstance(sidecars, list) else []:
                try:
                    meta = json.loads(library.read(reference))
                    if (meta.get('course', course) == course and bound(meta)
                            and hashlib.sha256(data).hexdigest() == meta.get('sha256')):
                        metadata.append(meta)
                except (OSError, ValueError, AttributeError, TypeError):
                    continue
            if not metadata:
                continue
            meta = metadata[-1]
            caption = str(meta.get('caption') or entry.get('caption') or '')
            description = str(card_paths.get(path) or meta.get('description') or entry.get('description')
                              or caption or meta.get('why') or 'Lesson diagram.')
            pdf = meta.get('pdf')
            source = (f"{Path(pdf).name}, p.{meta.get('page')}" if isinstance(pdf, str) and pdf else
                      str(provenance.get('source') or f'Library asset {identifier}'))
            out.append({'id': Path(path).stem, 'asset_id': identifier, 'file': path, 'caption': caption,
                        'description': description, 'source': source, 'provenance': provenance,
                        'why': str(meta.get('why') or ''), 'from_notes': bool(pdf)})
        # Preserve familiar names when unique; colliding names require stable catalog IDs.
        names = [figure['id'] for figure in out]
        for figure in out:
            if names.count(figure['id']) > 1:
                figure['id'] = figure['asset_id']
        return out
    # Compatibility for unmigrated vaults: explicit sidecar mapping and digest.
    for side in sorted((root / 'Assets').glob('*/*')):
        if side.parent.name != course:
            continue
        if not side.name.lower().endswith(tuple(ext + '.json' for ext in ('.svg', '.png', '.jpg', '.jpeg'))):
            continue
        try:
            meta = json.loads(side.read_text(encoding='utf-8'))
            picture = side.with_suffix('')
            if meta.get('subtopic') != subtopic or hashlib.sha256(picture.read_bytes()).hexdigest() != meta.get('sha256'):
                continue
        except (OSError, ValueError, AttributeError):
            continue
        out.append({'id': picture.stem, 'file': picture.relative_to(root).as_posix(), 'caption': meta.get('caption', ''),
                    'description': meta.get('description') or meta.get('caption') or 'Lesson diagram.',
                    'source': f"{Path(meta.get('pdf', '')).name}, p.{meta.get('page')}", 'why': meta.get('why', ''),
                    'from_notes': True})
    return out


def catalogue(card: dict, figures: list[dict]) -> str:
    """What the AI is told it can do on this idea, visual tools first (it must keep them in mind every turn)."""
    lines = ["Prefer this to a list of section IDs. Actions you may request (reply with JSON {\"actions\": [...]}, at most 4, in the order to show them):"]
    lines += [f"- {name}: {text}" for name, text in ACTIONS.items()]
    lines.append("Prefer the card's own material when it fits. Use `write` when the learner asks for something the card "
                 "does not contain (another example, a different angle, a step they are stuck on); never give away the "
                 "answer to a question the learner has not attempted.")
    lines.append("Use a figure only when it helps the idea; a word picture is better than a decorative one. "
                 "Generated figure types and their only settings (params): "
                 + "; ".join(f"{t} ({', '.join(sorted(k))})" for t, k in DIAGRAM_TYPES.items())
                 + ". A case_split needs start, cases (2-3 short labels) and end; a proof_flow needs steps. "
                 "Never write SVG.")
    if card.get("diagrams"):
        lines.append("Card diagrams: " + "; ".join(f"{i}: {d}" for i, d in
                                                    enumerate(diagram_descriptions(card) or card["diagrams"])))
    if figures:
        lines.append("Teaching figures (source = notes, figure = id): " + "; ".join(
            f"{f['id']} ({f['why'] or f.get('description') or f['caption']}; source: {f['source']})" for f in figures))
    if card.get("terms"):
        lines.append("Terms: " + "; ".join(t["term"] for t in card["terms"] if isinstance(t, dict) and t.get("term")))
    if card.get("forms"):
        lines.append("Question forms: " + "; ".join(f"{i}: {f['name']}" for i, f in enumerate(card["forms"])
                                                    if isinstance(f, dict) and f.get("name")))
    return "\n".join(lines)


def _clean_params(params: object) -> dict | None:
    """Plain JSON of modest size, nothing else: a figure request is data, never code."""
    try:
        text = json.dumps(params, ensure_ascii=False)
    except (TypeError, ValueError):
        return None
    if not isinstance(params, dict) or len(text) > 4000:
        return None
    return json.loads(text)


def generate_diagram(vault_root: Path, dtype: str, params: object, *, course: str | None = None) -> tuple[str | None, str]:
    """Draw a figure from a structured request with the project's diagram module. (embed path or None, problem)"""
    if dtype not in DIAGRAM_TYPES:
        return None, f"'{dtype}' is not a figure type I can draw."
    clean = _clean_params(params)
    if clean is None:
        return None, "That figure request was not valid."
    extra = set(clean) - DIAGRAM_TYPES[dtype]
    if extra:
        return None, f"A {dtype} has no setting called {sorted(extra)[0]!r}."
    if dtype == "function_plot":  # a formula that does not evaluate would draw an empty graph that looks right
        from .packs import _eval
        try:
            for fn in clean.get("functions") or []:
                lo, hi = fn["domain"]
                for x in (lo, (lo + hi) / 2, hi):
                    _eval(str(fn["expr"]), {"x": x})
        except Exception:  # noqa: BLE001 - an unreadable formula, a missing domain, a pole at an end: not drawn
            return None, "I could not read that formula for the graph."
    name = hashlib.sha256(json.dumps([dtype, clean], sort_keys=True).encode()).hexdigest()[:12]
    folder = f'Library/Courses/{course}/Diagrams' if isinstance(course, str) and re.fullmatch(r'[A-Za-z0-9]+', course) else 'Library/Shared/Diagrams'
    rel = f"{folder}/{dtype}-{name}.svg"
    try:
        require_runtime_library(vault_root)
    except (OSError, ValueError) as exc:
        return None, str(exc)
    try:
        catalog = Path(vault_root) / 'Library/catalog.json'
        if catalog.exists() or catalog.is_symlink():
            library = AssetLibrary(vault_root)
            try:
                library.record(rel)
            except ValueError as exc:
                if not str(exc).startswith('unknown asset reference:'):
                    raise
            else:
                library.resolve(rel)
                return rel, ''
        sys.path.insert(0, str(_repo() / "build"))
        import diagrams  # noqa: PLC0415 - build-time module with matplotlib: only needed when a figure is asked for
        obj = diagrams.RENDER[dtype](clean)
        if dtype == "circuit":
            data = obj.get_imagedata('svg')
        else:
            try:
                obj.tight_layout()
                output = io.BytesIO()
                obj.savefig(output, format="svg", facecolor="white", metadata={'Date': None})
                data = output.getvalue()
            finally:
                diagrams.plt.close(obj)
        if isinstance(data, str):
            data = data.encode('utf-8')
        write_asset(vault_root, rel, data, metadata={'kind': 'Diagrams', 'generated': True})
    except Exception as e:  # noqa: BLE001 - any drawing failure is a fallback to words, never a crash
        return None, f"I could not draw that figure ({type(e).__name__})."
    return rel, ""


def describe_params(dtype: str, params: dict, why: str) -> str:
    """The text that stands in for a generated figure in the terminal (and as its alt text)."""
    bits = [why.strip()] if why and why.strip() else []
    for key in ("xlabel", "ylabel", "start", "end"):
        if isinstance(params.get(key), str):
            bits.append(f"{key}: {params[key]}")
    for key in ("cases", "steps"):
        if isinstance(params.get(key), list):
            bits.append(f"{key}: " + " / ".join(str(x) for x in params[key]))
    for f in params.get("functions") or []:
        if isinstance(f, dict) and f.get("expr"):
            bits.append(f"y = {f['expr']}")
    return (f"{dtype.replace('_', ' ').capitalize()}. " + "; ".join(bits)).strip()[:300]


def run(actions: object, *, card: dict, kc: str, subtopic: str, vault_root: Path, figures: list[dict],
        blocked: str | None = None) -> list[dict]:
    """Check each request and carry out the ones allowed. Returns results in order:
    {"kind": "card", "role", "title", "body", "image"?} to draw, {"kind": "ui", "do", ...} for the existing handlers,
    {"kind": "term", "term"} for the review queue, {"kind": "problem", "text"} for a request that was refused."""
    out: list[dict] = []
    if not isinstance(actions, list):
        return [{"kind": "problem", "text": "I could not read what to show."}]
    for req in actions[:MAX_ACTIONS]:
        name = req.get("action") if isinstance(req, dict) else None
        if name not in ACTIONS:
            out.append({"kind": "problem", "text": "I skipped something I do not know how to show."})
            continue
        if blocked and name in SHOWS_CONTENT:
            out.append({"kind": "problem", "text": blocked})
            continue
        res = _one(name, req, card, kc, subtopic, vault_root, figures)
        out.append(res)
    return out


def _written(req: dict) -> dict:
    """An explanation the AI wrote itself (laid out and its equations checked by the screen, see learn_write). It is
    shown, but never passed off as the learner's notes: it is labelled, and the label says exactly what was machine-
    checked (equations that are plain algebra or arithmetic) and what was not (the wording, the reasoning, any other
    maths)."""
    if req.get("problem"):
        return {"kind": "problem", "text": str(req["problem"])[:300]}
    topic = re.sub(r"\s+", " ", str(req.get("topic") or "")).strip()[:120]
    text = str(req.get("text") or "").strip()
    if not topic or not 40 <= len(text) <= 6000:
        return {"kind": "problem", "text": "I could not write a usable explanation just now."}
    checked = [c for c in req.get("checked") or [] if isinstance(c, str)][:12]
    unchecked = int(req.get("unchecked") or 0)
    foot = ("Written by the tutor for your question: it is not from your notes or a past paper. "
            + (f"Checked by computer algebra: {'; '.join(f'`{c}`' for c in checked)}. " if checked else "")
            + ("Other equations, the wording and the reasoning are not machine-checked." if checked else
               "The wording, the reasoning and any equations in it are not machine-checked."))
    return {"kind": "card", "role": "ai", "title": f"Tutor-written: {topic}", "body": f"{text}\n\n{foot}",
            "written": True}


def _one(name: str, req: dict, card: dict, kc: str, subtopic: str, vault_root: Path, figures: list[dict]) -> dict:
    def problem(text: str) -> dict:
        return {"kind": "problem", "text": text}

    def form_of(i: object) -> dict | None:
        forms = card.get("forms") or []
        return forms[i] if isinstance(i, int) and not isinstance(i, bool) and 0 <= i < len(forms) else None

    def term_of(wanted: object) -> dict | None:
        key = re.sub(r"\s+", " ", str(wanted or "")).strip().casefold()
        hits = [t for t in card.get("terms") or [] if isinstance(t, dict)
                and key in (str(t.get("term", "")).casefold(), str(t.get("notation", "")).casefold()) and key]
        return hits[0] if len(hits) == 1 else None

    if name == "write":
        return _written(req)
    if name == "explain":
        sec = req.get("section")
        if isinstance(sec, str) and "|" in sec:  # the older "<idea>|<section>" form: only this idea's own card
            owner, _, sec = sec.rpartition("|")
            sec = sec if owner == kc else None
        text = card.get(sec) if sec in SECTIONS else None
        if not (isinstance(text, str) and text.strip()):
            return problem("That part of the idea is not written yet.")
        return {"kind": "card", "role": "tutor", "title": SECTION_TITLE[sec], "body": text.strip()}
    if name == "term":
        t = term_of(req.get("term"))
        if not t:
            return problem("I could not find that term for this idea.")
        body = [f"**{t['term']}:** {t.get('meaning', '')}"]
        if t.get("notation"):
            body.append(f"Written: {t['notation']}")
        if t.get("spoken"):
            body.append(f"Said: {t['spoken']}")
        return {"kind": "card", "role": "tutor", "title": "Helpful term", "body": "\n\n".join(body),
                "term": t["term"]}
    if name == "example":
        f = form_of(req.get("form"))
        if not f or not f.get("example"):
            return problem("There is no worked example for that form.")
        ex = f["example"]
        body = ex if isinstance(ex, str) else "\n\n".join(str(v) for v in (ex.get("problem"), *(ex.get("steps") or []))
                                                          if v) if isinstance(ex, dict) else str(ex)
        return {"kind": "card", "role": "tutor", "title": f"Worked example: {f.get('name', '')}", "body": body}
    if name == "diagram":
        return _diagram(req, card, vault_root, figures, problem, subtopic=subtopic)
    if name == "check":
        f = form_of(req.get("form"))
        return ({"kind": "ui", "do": "check", "form": req["form"]} if f and f.get("check")
                else problem("There is no check for that form."))
    if name == "question":
        return {"kind": "ui", "do": "question", "kc": kc}
    if name == "hint":
        return {"kind": "ui", "do": "hint"}
    if name == "note":
        text = re.sub(r"\s+", " ", str(req.get("text") or "")).strip()
        if not text:
            return problem("There was no note to add.")
        return {"kind": "card", "role": "you", "title": "Note", "body": text[:400], "note": True}
    t = term_of(req.get("term"))  # review
    return {"kind": "term", "term": t["term"]} if t else problem("I could not find that term to review.")


def _diagram(req: dict, card: dict, vault_root: Path, figures: list[dict], problem, *, subtopic: str | None = None) -> dict:
    source = req.get("source")
    if source == "card":
        paths = card.get("diagrams") or []
        i = req.get("form")
        i = i if isinstance(i, int) and not isinstance(i, bool) else 0
        if not 0 <= i < len(paths):
            return problem("That card has no such diagram.")
        path = paths[i]
        if not isinstance(path, str):
            return problem('The lesson diagram has an invalid path. I will explain it in words instead.')
        root = Path(vault_root).resolve()
        try:
            refs = LibraryRefs(root)
            path = refs.reference(path)
            target = (root / path).resolve()
            if refs.library is None and not path.startswith('Assets/'):
                raise ValueError('invalid legacy figure path')
            if refs.library is not None and '/Diagrams/' not in path:
                raise ValueError('assessment media is not a teaching figure')
            allowed = root / ('Library' if refs.library is not None else 'Assets')
            if not target.is_relative_to(allowed) or not target.is_file():
                raise ValueError('unavailable figure')
        except (OSError, ValueError):
            return problem('The lesson diagram is unavailable. I will explain it in words instead.')
        descs = diagram_descriptions(card)
        return {"kind": "card", "role": "tutor", "title": "Diagram", "body": descs[i] if i < len(descs) else "Lesson diagram.",
                "image": path}
    if source == "notes":
        fig = next((f for f in figures if f["id"] == req.get("figure")), None)
        if not fig:
            return problem("I could not find that figure in your notes.")
        try:
            path = LibraryRefs(vault_root).reference(fig['file'])
        except (OSError, ValueError):
            return problem('That teaching figure is no longer available.')
        description = fig.get('description') or fig['caption'] or 'Lesson diagram.'
        if fig.get('caption') and fig['caption'] != description:
            description = fig['caption'] + '\n\n' + description
        return {"kind": "card", "role": "tutor", "title": "Figure from your notes" if fig.get('from_notes') else 'Teaching figure',
                "body": f"{description}\n\nSource: {fig['source']}.", "image": path}
    if source == "generated":
        course = subtopic.split('-', 1)[0] if isinstance(subtopic, str) and '-' in subtopic else None
        rel, why_not = generate_diagram(vault_root, str(req.get("type")), req.get("params"), course=course)
        if rel is None:
            return problem(why_not + " I will explain it in words instead.")
        params = _clean_params(req.get("params")) or {}
        return {"kind": "card", "role": "tutor", "title": "Diagram",
                "body": describe_params(str(req.get("type")), params, str(req.get("why") or "")), "image": rel,
                "generated": True}
    return problem("I did not know where to get that figure.")


def as_activity(card_result: dict) -> dict:
    """A card result as the lesson's own `explain` step, so Terminal and Obsidian draw it exactly as they draw one."""
    act = {"activity": "explain", "title": card_result["title"], "text": card_result["body"]}
    if card_result.get("image"):
        act["diagram"], act["diagram_description"] = card_result["image"], card_result["body"]
    return act


def blocks_for(results: list[dict]) -> list[str]:
    """Obsidian Markdown for the card results (for the lesson log), in the shared callout wording."""
    out = []
    for r in results:
        if r["kind"] == "card":
            out.append(views.card_block(r["role"], r["title"], r["body"]) +
                       (f"\n\n![[{r['image']}]]" if r.get("image") else ""))
    return out
