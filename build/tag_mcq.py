"""Tag mined MCQs with KC ids (agent step) and attach examiner-report comments.

  python build/tag_mcq.py prepare [n_chunks]   -> build/work/tag/<code>-<k>.input.txt + kcs-<code>.txt
  python build/tag_mcq.py merge                -> build/work/mcq/<code>.tagged.json (ER comment + KC tags merged)
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MCQ, TAG, ER = ROOT / "build/work/mcq", ROOT / "build/work/tag", ROOT / "build/work/er"
CODES = ("9701", "9702")


def _er_index(code: str) -> dict[str, str]:
    idx = {}
    for r in json.loads((ER / f"{code}.json").read_text()):
        if r["q"] and r["paper"][0] == "1":
            for q in re.findall(r"\d{1,2}", r["q"]):
                idx[f"{code}_{r['series']}_{r['paper']}_q{q}"] = r["text"]
    return idx


def prepare(n_chunks: int = 4) -> None:
    TAG.mkdir(parents=True, exist_ok=True)
    skel = json.loads((ROOT / "build/work/graph/skeletons.json").read_text())
    for code in CODES:
        kcs = [k for k in skel[code]["kcs"] if k["level"] == "AS"]
        (TAG / f"kcs-{code}.txt").write_text("\n".join(f"{k['id']} | {k['raw'][:110]}" for k in kcs))
        items = json.loads((MCQ / f"{code}.json").read_text())
        lines = []
        for it in items:
            opts = " ".join(f"{k}: {v[:60]}" for k, v in (it["options"] or {}).items())
            stem = re.sub(r"\s+", " ", it["stem"])[:260]
            lines.append(f"{it['id']} | {stem} | {opts or '(options in figure)'} | key {it['answer']}")
        size = -(-len(lines) // n_chunks)
        for k in range(n_chunks):
            (TAG / f"{code}-{k + 1}.input.txt").write_text("\n".join(lines[k * size:(k + 1) * size]))
        print(code, len(kcs), "AS KCs,", len(lines), "MCQs in", n_chunks, "chunks")


def merge() -> None:
    skel = json.loads((ROOT / "build/work/graph/skeletons.json").read_text())
    for code in CODES:
        ids = {k["id"] for k in skel[code]["kcs"]}
        tags = {}
        for f in sorted(TAG.glob(f"{code}-*.output.jsonl")):
            for line in f.read_text().splitlines():
                if line.strip():
                    t = json.loads(line)
                    tags[t["id"]] = t
        er = _er_index(code)
        items = json.loads((MCQ / f"{code}.json").read_text())
        missing = bad = 0
        for it in items:
            t = tags.get(it["id"])
            if not t:
                missing += 1
                continue
            it["kcs"] = [k for k in t.get("kcs", []) if k in ids]
            bad += len(t.get("kcs", [])) - len(it["kcs"])
            it["off_syllabus"] = bool(t.get("off_syllabus"))
            it["tag_conf"] = t.get("conf")
            if it["id"] in er:
                it["er"] = er[it["id"]]
        (MCQ / f"{code}.tagged.json").write_text(json.dumps(items, ensure_ascii=False, indent=1))
        tagged = [i for i in items if i.get("kcs")]
        print(code, f"{len(tagged)} tagged, {missing} untagged, {bad} invalid ids dropped, "
                    f"{sum(i.get('off_syllabus', False) for i in items)} off-syllabus, {sum('er' in i for i in items)} with ER")


if __name__ == "__main__":
    prepare(int(sys.argv[2]) if len(sys.argv) > 2 else 4) if sys.argv[1] == "prepare" else merge()
