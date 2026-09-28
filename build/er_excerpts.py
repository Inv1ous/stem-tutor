"""Split CAIE examiner reports into per-question comments, then retrieve excerpts per subtopic.

  python build/er_excerpts.py split [code ...]           -> build/work/er/<code>.json
  python build/er_excerpts.py for <subtopic> [max_chars] -> prints the most relevant excerpts (by glossary)
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "build/work/er"
NOISE = re.compile(r"^(© \d{4}|Cambridge International|\d{4} [A-Z]|www\.|Page \d)", re.I)


def split(code: str) -> list[dict]:
    out = []
    for er in sorted((ROOT / "sources/papers" / code).rglob(f"{code}_*_er.pdf")):
        series = er.stem.split("_")[1]
        text = "\n".join(p.get_text() for p in pymupdf.open(er))
        lines = [l.strip() for l in text.split("\n") if l.strip() and not NOISE.match(l.strip())]
        body = "\n".join(lines)
        papers = re.split(rf"(?m)^Paper {code}/(\d\d)\s*$", body)
        for i in range(1, len(papers) - 1, 2):
            comp, chunk = papers[i], papers[i + 1]
            if comp[0] not in "12":  # AS theory papers only; practical reports handled later
                continue
            general = chunk.split("Comments on specific questions")[0]
            out.append({"ref": f"ER {code} {series} P{comp} general", "series": series, "paper": comp, "q": None,
                        "text": re.sub(r"\s+", " ", general)[:3000]})
            specific = chunk.split("Comments on specific questions", 1)[1] if "Comments on specific questions" in chunk else ""
            parts = re.split(r"(?m)^(?:Question|Questions)\s+(\d{1,2}(?:\s*(?:and|,|–|-)\s*\d{1,2})*)\s*$", specific)
            if len(parts) == 1:  # MCQ reports often write "Question 7" inline
                parts = re.split(r"(?:^|\n)(?:Question|Questions)\s+(\d{1,2}(?:\s*(?:and|,|–|-)\s*\d{1,2})*)\b", specific)
            for j in range(1, len(parts) - 1, 2):
                txt = re.sub(r"\s+", " ", parts[j + 1]).strip()
                if len(txt) > 40:
                    out.append({"ref": f"ER {code} {series} P{comp} Q{parts[j]}", "series": series, "paper": comp,
                                "q": parts[j], "text": txt[:2500]})
    return out


def excerpts(subtopic: str, max_chars: int = 6000) -> list[dict]:
    spec = subtopic.split("-")[0]
    graph = json.loads((ROOT / f"build/out/specs/{spec}/graph.json").read_text()) if \
        (ROOT / f"build/out/specs/{spec}/graph.json").exists() else None
    if graph:
        terms = {t.lower() for k in graph["kcs"] if k["subtopic"] == subtopic for t in k["glossary"] if len(t) > 3}
    else:
        enriched = [e for f in (ROOT / "build/work/graph").glob("*.enriched.json") for e in json.loads(f.read_text())]
        terms = {t.lower() for e in enriched if e["id"].startswith(subtopic + ".") for t in e["glossary"] if len(t) > 3}
    rows = json.loads((WORK / f"{spec}.json").read_text())
    scored = []
    for r in rows:
        if r["q"] is None:
            continue
        low = r["text"].lower()
        hits = sorted(t for t in terms if t in low)
        if hits:
            scored.append((-len(hits), -int(r["series"][1:]), r["ref"], hits, r["text"]))
    out, used = [], 0
    for _, _, ref, hits, text in sorted(scored):
        if used > max_chars:
            break
        out.append({"ref": ref, "matched": hits[:6], "text": text[:900]})
        used += min(len(text), 900)
    return out


if __name__ == "__main__":
    if sys.argv[1] == "split":
        WORK.mkdir(parents=True, exist_ok=True)
        for code in sys.argv[2:] or ["9701", "9702"]:
            rows = split(code)
            (WORK / f"{code}.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1))
            print(code, len(rows), "excerpts from", len({r["series"] for r in rows}), "series")
    else:
        print(json.dumps(excerpts(sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 6000), ensure_ascii=False, indent=1))
