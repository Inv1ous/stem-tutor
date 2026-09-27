"""Syllabus graph build: raw spec JSON -> KC skeletons -> (agent enrichment) -> validated graph.json per spec.

  python build/graph.py skeletons     writes build/work/graph/<chunk>.input.json
  python build/graph.py merge         merges <chunk>.enriched.json into build/out/specs/<spec>/graph.json
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW, WORK, OUT = ROOT / "build/raw", ROOT / "build/work/graph", ROOT / "build/out"
UNITS = ["P1", "P2", "P3", "P4", "FP1", "FP2", "FP3", "M1", "S1", "S2", "S3", "D1"]
TYPES = {"factual", "conceptual", "procedural"}
CHUNKS = {"9701-AS": ("9701", range(1, 23)), "9701-A2": ("9701", range(23, 38)),
          "9702-AS": ("9702", range(1, 12)), "9702-A2": ("9702", range(12, 26)),
          "maths-pure": ("math", ["P1", "P2", "P3", "P4"]), "maths-fp": ("math", ["FP1", "FP2", "FP3"]),
          "maths-applied": ("math", ["M1", "S1", "S2", "S3", "D1"])}
SUBJECT = {"9701": "chem", "9702": "phys"}
TITLES = {"9701": "CAIE AS & A Level Chemistry 9701", "9702": "CAIE AS & A Level Physics 9702"}
UNIT_TITLES = {"P1": "Pure Mathematics 1", "P2": "Pure Mathematics 2", "P3": "Pure Mathematics 3",
               "P4": "Pure Mathematics 4", "FP1": "Further Pure Mathematics 1", "FP2": "Further Pure Mathematics 2",
               "FP3": "Further Pure Mathematics 3", "M1": "Mechanics 1", "S1": "Statistics 1", "S2": "Statistics 2",
               "S3": "Statistics 3", "D1": "Decision Mathematics 1"}


def skeleton_caie(code: str) -> dict:
    raw = json.loads((RAW / f"{code}.json").read_text())
    topics, subtopics, kcs = [], [], []
    for t in raw["topics"]:
        tid = f"{code}-{t['n']}"
        topics.append({"id": tid, "title": t["title"], "level": t["level"]})
        for s in t["subtopics"]:
            sid = f"{code}-{s['id']}"
            subtopics.append({"id": sid, "title": s["title"], "topic": tid})
            for o in s["outcomes"]:
                kcs.append({"id": f"{sid}.{o['n']}", "subtopic": sid, "level": t["level"], "raw": o["text"],
                            "context": f"{t['title']} > {s['title']}"})
    return {"spec": code, "subject": SUBJECT[code], "title": TITLES[code], "version": "2025-2027",
            "topics": topics, "subtopics": subtopics, "kcs": kcs}


def skeleton_unit(unit: str) -> dict:
    raw = json.loads((RAW / "ial-maths.json").read_text())
    u = next(x for x in raw["units"] if x["unit"] == unit)
    subtopics, kcs = [], []
    for sec in u["sections"]:
        sid = f"{unit}-{sec['n']}"
        subtopics.append({"id": sid, "title": sec["title"], "topic": unit})
        for it in sec["items"]:
            kcs.append({"id": f"{unit}-{it['id']}", "subtopic": sid, "level": unit, "raw": it["text"],
                        "guidance": it["guidance"], "context": f"{unit} > {sec['title']}"})
    return {"spec": unit, "subject": "math", "title": f"Edexcel IAL {UNIT_TITLES[unit]}", "version": "2018 Issue 3",
            "topics": [{"id": unit, "title": UNIT_TITLES[unit], "level": unit}], "subtopics": subtopics, "kcs": kcs}


def skeletons() -> None:
    WORK.mkdir(parents=True, exist_ok=True)
    specs = {c: skeleton_caie(c) for c in ("9701", "9702")} | {u: skeleton_unit(u) for u in UNITS}
    (WORK / "skeletons.json").write_text(json.dumps(specs, ensure_ascii=False, indent=1))
    for chunk, (spec, sel) in CHUNKS.items():
        if spec == "math":
            items = [k for u in sel for k in specs[u]["kcs"]]
        else:
            items = [k for k in specs[spec]["kcs"] if int(k["subtopic"].split("-")[1].split(".")[0]) in sel]
        (WORK / f"{chunk}.input.json").write_text(json.dumps(items, ensure_ascii=False, indent=1))
        print(chunk, len(items), "KCs")
    print("all KC ids:", sum(len(s["kcs"]) for s in specs.values()))
    (WORK / "all-ids.txt").write_text("\n".join(f"{k['id']}\t{k['context']}" for s in specs.values() for k in s["kcs"]))


def _cycle(graph: dict[str, list[str]]) -> list[str] | None:
    state: dict[str, int] = {}
    path: list[str] = []

    def visit(n: str) -> list[str] | None:
        state[n] = 1
        path.append(n)
        for m in graph.get(n, []):
            if state.get(m) == 1:
                return path[path.index(m):] + [m]
            if m not in state and (c := visit(m)):
                return c
        state[n] = 2
        path.pop()
        return None

    for n in graph:
        if n not in state and (c := visit(n)):
            return c
    return None


def merge() -> None:
    specs = json.loads((WORK / "skeletons.json").read_text())
    enriched: dict[str, dict] = {}
    for chunk in CHUNKS:
        f = WORK / f"{chunk}.enriched.json"
        if not f.exists():
            sys.exit(f"missing {f.name}")
        for e in json.loads(f.read_text()):
            enriched[e["id"]] = e
    ids = {k["id"] for s in specs.values() for k in s["kcs"]}
    errors = []
    for i in sorted(ids - set(enriched)):
        errors.append(f"not enriched: {i}")
    graph = {}
    for s in specs.values():
        for k in s["kcs"]:
            e = enriched.get(k["id"], {})
            if e.get("type") not in TYPES:
                errors.append(f"{k['id']}: bad type {e.get('type')}")
            bad = [p for p in e.get("prereqs", []) if p not in ids]
            if bad:
                errors.append(f"{k['id']}: unknown prereqs {bad}")
            if not e.get("title") or not e.get("statement") or len(e.get("glossary", [])) < 2:
                errors.append(f"{k['id']}: missing title/statement/glossary")
            graph[k["id"]] = [p for p in e.get("prereqs", []) if p in ids]
    cyc = _cycle(graph)
    if cyc:
        errors.append("prereq cycle: " + " -> ".join(cyc))
    if errors:
        print("\n".join(errors[:60]))
        sys.exit(f"{len(errors)} errors")
    cmd = json.loads((ROOT / "build/command_words.json").read_text())
    for name, s in specs.items():
        kcs = []
        for k in s["kcs"]:
            e = enriched[k["id"]]
            kcs.append({"id": k["id"], "subtopic": k["subtopic"], "level": k["level"], "title": e["title"],
                        "statement": e["statement"], "raw": k["raw"], "type": e["type"], "prereqs": e.get("prereqs", []),
                        "glossary": e["glossary"], **({"guidance": e["guidance"]} if e.get("guidance") else {})})
        out = {**{f: s[f] for f in ("spec", "subject", "title", "version", "topics", "subtopics")},
               "command_words": cmd.get(name, cmd.get("math", {})), "kcs": kcs}
        path = OUT / "specs" / name / "graph.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(out, ensure_ascii=False, indent=1))
        print(name, len(kcs), "KCs ->", path.relative_to(ROOT))


if __name__ == "__main__":
    {"skeletons": skeletons, "merge": merge}[sys.argv[1]]()
