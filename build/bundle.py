"""Assemble everything a pack drafter needs for one subtopic into build/work/bundles/<subtopic>.md.

  python build/bundle.py <subtopic> [...]
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
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
