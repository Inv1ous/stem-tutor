"""Assemble everything a pack drafter needs for one subtopic into build/work/bundles/<subtopic>.md.

  python build/bundle.py <subtopic> [...]
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import diagram_hints  # noqa: E402
import er_excerpts  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "build/work/bundles"
SPEC_NAMES = {"9701": "9701 Chemistry", "9702": "9702 Physics"}
CONSTANTS = {
    "9702": "g = 9.81 m s⁻², c = 3.00 × 10⁸ m s⁻¹, e = 1.60 × 10⁻¹⁹ C, h = 6.63 × 10⁻³⁴ J s, m_e = 9.11 × 10⁻³¹ kg, "
            "N_A = 6.02 × 10²³ mol⁻¹, R = 8.31 J K⁻¹ mol⁻¹, k = 1.38 × 10⁻²³ J K⁻¹, u = 1.66 × 10⁻²⁷ kg",
    "9701": "N_A = 6.02 × 10²³ mol⁻¹, F = 9.65 × 10⁴ C mol⁻¹, R = 8.31 J K⁻¹ mol⁻¹, e = 1.60 × 10⁻¹⁹ C, "
            "V_m = 24.0 dm³ mol⁻¹ at r.t.p., K_w = 1.00 × 10⁻¹⁴ mol² dm⁻⁶ at 298 K, c(water) = 4.18 J g⁻¹ K⁻¹; "
            "use A_r values from the Periodic Table printed in the paper",
    "M1": "g = 9.8 m s⁻²; give answers to 2 or 3 significant figures after using g = 9.8",
}


def note_path(graph: dict, sub: dict) -> str:
    spec = graph["spec"]
    topic = next(t for t in graph["topics"] if t["id"] == sub["topic"])
    if spec in SPEC_NAMES:
        tnum = int(topic["id"].split("-")[1])
        return f"Subjects/{SPEC_NAMES[spec]}/{tnum:02d} {topic['title']}/{sub['id'].split('-', 1)[1]} {sub['title']}.md"
    return f"Subjects/Maths/{spec} {topic['title']}/{sub['id'].split('-')[1]} {sub['title']}.md"


VAULT_NOTES = ("Home", "Today", "Now", "Profile", "Mistakes", "How It Works")  # the vault's own pages: always there


def graphs() -> dict[str, dict]:
    return {g.parent.name: json.loads(g.read_text()) for g in sorted((ROOT / "build/out/specs").glob("*/graph.json"))}


def note_names() -> dict[str, str]:
    """{subtopic id: the note's exact name} for every chapter of every syllabus, built or not: the file name each
    chapter's note will have, so a link written today to a chapter built next month is right."""
    out = {}
    for g in graphs().values():
        for s in g["subtopics"]:
            out[s["id"]] = Path(note_path(g, s)).stem
    return out


def related(subtopic: str) -> tuple[list[tuple[str, int]], list[tuple[str, int]]]:
    """(earlier, later): the chapters this one builds on (through its points' prerequisites) and those that build on
    it, each as (subtopic id, number of points that link them), the most connected first."""
    gs = graphs()
    owner = {k["id"]: k["subtopic"] for g in gs.values() for k in g["kcs"]}
    mine = {k["id"] for g in gs.values() for k in g["kcs"] if k["subtopic"] == subtopic}
    early: dict[str, int] = {}
    late: dict[str, int] = {}
    for g in gs.values():
        for k in g["kcs"]:
            if k["subtopic"] == subtopic:
                for p in k.get("prereqs", []):
                    if owner.get(p) and owner[p] != subtopic:
                        early[owner[p]] = early.get(owner[p], 0) + 1
            elif mine & set(k.get("prereqs", [])):
                late[k["subtopic"]] = late.get(k["subtopic"], 0) + 1
    rank = lambda d: sorted(d.items(), key=lambda x: (-x[1], x[0]))  # noqa: E731
    return rank(early), rank(late)


def _link_lines(subtopic: str) -> list[str]:
    names = note_names()
    early, late = related(subtopic)
    built = lambda s: (ROOT / f"build/out/packs/{s.split('-')[0]}/{s}.json").exists()  # noqa: E731
    L = ["## Chapters you may link (exact note names)", "",
         "Inside `[[ ]]` use these names exactly, nothing else: a title you made up or shortened opens nothing, and the "
         "lesson gate fails it. Put the earlier chapters on the `Builds on` line (up to 4, the most connected first) and the "
         "later ones on `Leads to` (up to 3). A chapter not built yet is fine to link: the link turns on when it is published.", ""]
    for head, rows in (("Builds on (earlier)", early[:6]), ("Leads to (later)", late[:6])):
        L.append(f"**{head}**")
        L += [f"- [[{names[s]}]] ({s}, {n} linked point{'s' if n > 1 else ''}, {'built' if built(s) else 'not built yet'})"
              for s, n in rows if s in names] or ["- none recorded"]
        L.append("")
    return L


def _diagram_lines(kcs: list[dict]) -> list[str]:
    sug = diagram_hints.suggest(kcs)
    if not sug:
        return []
    L = ["## Diagrams this chapter should have", "",
         "These points are things a figure shows. Request at least one of them in the pack's `diagrams` list (types in "
         "`build/PACK.md`) and embed each in the note with `![[Assets/...svg]]`; the chapter's gate fails without one "
         "(or, if none can honestly be drawn, a `diagrams_skipped` field in the pack that says why).", ""]
    L += [f"- `{kind}` for {', '.join(ids)}" for kind, ids in sug.items()]
    return L + [""]


def _mcqs(spec: str, kcs: set[str]) -> list[dict]:
    f = ROOT / f"build/work/mcq/{spec}.tagged.json"
    if not f.exists():
        return []
    return [m for m in json.loads(f.read_text()) if set(m.get("kcs") or []) & kcs and not m.get("off_syllabus")]


def bundle(subtopic: str) -> Path:
    spec = subtopic.split("-")[0]
    graph = json.loads((ROOT / f"build/out/specs/{spec}/graph.json").read_text())
    allk = {k["id"]: k for s in (ROOT / "build/out/specs").glob("*/graph.json") for k in json.loads(s.read_text())["kcs"]}
    sub = next(s for s in graph["subtopics"] if s["id"] == subtopic)
    kcs = [k for k in graph["kcs"] if k["subtopic"] == subtopic]
    ids = {k["id"] for k in kcs}
    L = [f"# Bundle {subtopic}: {sub['title']}", "",
         f"Spec: {graph['title']} ({graph['version']}). Pack file: `build/out/packs/{spec}/{subtopic}.json`. "
         f"Note path: `{note_path(graph, sub)}` (write it under `build/out/notes/`). "
         f"Diagram files: `Assets/{spec}/{subtopic}-<name>.svg`.", "", "## KCs", ""]
    for k in kcs:
        pre = "; ".join(f"{p} {allk[p]['title']}" for p in k["prereqs"] if p in allk) or "none"
        L += [f"### {k['id']} — {k['title']} ({k['type']})", f"Statement: {k['statement']}"]
        if k.get("guidance"):
            L.append(f"Guidance: {k['guidance']}")
        L += [f"Prerequisites: {pre}", f"Glossary: {', '.join(k['glossary'])}", ""]
    L += _link_lines(subtopic) + _diagram_lines(kcs)
    cw = graph.get("command_words") or {}
    L += ["## Command words", ""] + [f"- **{w}**: {m}" for w, m in cw.items()] + [""]
    const = CONSTANTS.get(spec) or (CONSTANTS["M1"] if spec.startswith("M") else "")
    if const:
        L += ["## Constants (use exactly these)", "", const, ""]
    mcqs = _mcqs(spec, ids)
    shown = sorted(mcqs, key=lambda m: ("er" in m, m["id"][5:8].replace("w", "z"), m["id"]), reverse=True)[:30]
    L += [f"## Past-paper MCQs tagged to these KCs ({len(mcqs)} in the bank, {len(shown)} most informative shown)", "",
          "Pick the 12 best of these (cover every KC, favour ones with examiner comments) as `source: past` items: "
          "item id `<subtopic>-p<NN>`, `ref` = the question id, original options and key, `image` when given. "
          "Each needs an `explanation` that also says why the popular wrong option is wrong, and `distractors` mapped to "
          "your misconceptions where the examiner comment shows one. The rest of the bank is added automatically as "
          "extra practice, so do not list them.", ""]
    for m in shown:
        opts = " / ".join(f"{k}: {v}" for k, v in (m.get("options") or {}).items()) or "(options in figure)"
        L.append(f"- `{m['id']}` {m['ref']} · KCs {', '.join(m['kcs'])} · key **{m['answer']}**"
                 + (f" · image `{m['image']}`" if m.get("image") else ""))
        L.append(f"  - {re.sub(chr(10), ' / ', m['stem'])[:400]}")
        L.append(f"  - {opts[:300]}")
        if m.get("er"):
            L.append(f"  - Examiner: {m['er'][:500]}")
    L += ["", "## Examiner-report excerpts (structured papers and general)", ""]
    if spec in ("9701", "9702"):
        for e in er_excerpts.excerpts(subtopic, 5000):
            L.append(f"- **{e['ref']}** (matched: {', '.join(e['matched'])}): {e['text']}")
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{subtopic}.md"
    path.write_text("\n".join(L) + "\n", encoding="utf-8")
    return path


if __name__ == "__main__":
    for s in sys.argv[1:]:
        p = bundle(s)
        print(p.relative_to(ROOT), f"{len(p.read_text()) // 4} tokens approx")
