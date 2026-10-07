"""Extract verbatim learning outcomes from official spec PDFs into raw JSON (build time, macOS).

CAIE 9701/9702: topic -> subtopic "2.1 Title" -> "Candidates should be able to:" -> numbered outcomes.
Pearson IAL Maths: per unit ("P1.3 Unit content" header) a two-column table: number | statement | guidance.
Output: build/raw/<spec>.json. Enrichment (types, prereqs, glossary, LaTeX) happens later on top of this.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "build" / "raw"
# The text layer carries soft hyphens and maths-font glyphs (private use area), and loses typeset fractions:
# map the glyphs and restore the few outcomes whose maths fell apart, so a re-extraction stays clean.
GLYPHS = str.maketrans({"­": None, "": "≤", "": "≥"})
REPAIRS = {
    "Cl O–": "ClO⁻",
    "d y 1 = The use of d x  d x    d y  ": "The use of dy/dx = 1/(dx/dy)",
    "the ‘middle’ item has position [ so that": "the ‘middle’ item has position [½(N + 1)] if N is odd, "
                                                "[½(N + 2)] if N is even, so that",
}


def tidy(v):
    if isinstance(v, str):
        v = v.translate(GLYPHS)
        for bad, good in REPAIRS.items():
            v = v.replace(bad, good)
        return v
    if isinstance(v, list):
        return [tidy(x) for x in v]
    if isinstance(v, dict):
        return {k: tidy(x) for k, x in v.items()}
    return v


NOISE = re.compile(r"^(Cambridge International AS & A Level|www\.cambridgeinternational|Back to contents page|\d+$)")


def caie(pdf: Path, code: str) -> dict:
    doc = pymupdf.open(pdf)
    lines: list[str] = []
    started = False
    for page in doc:
        text = page.get_text()
        if not started and not re.search(r"^\s*\d+\.\d+\s+\S", text, re.M) or not started and "Candidates should be able to:" not in text:
            continue
        if re.search(r"^\s*\d\s+Details of the assessment|^\s*Details of the assessment", text, re.M) and lines:
            break
        started = True
        raw = [x.replace("\x07", "").strip() for x in text.split("\n")]
        k = 0
        while k < len(raw):
            x = raw[k]
            if x.startswith("Cambridge International AS & A Level"):
                k += 2 if k + 1 < len(raw) and re.fullmatch(r"\d{1,3}", raw[k + 1]) else 1
                continue
            if x and not re.match(r"^(www\.cambridgeinternational|Back to contents page)", x):
                lines.append(x)
            k += 1
    topics, level = [], "AS"
    topic = sub = outcome = None
    skip = {"Learning outcomes", "Physical chemistry", "Inorganic chemistry", "Organic chemistry",
            "Analysis", "AS Level subject content"}
    i = 0
    while i < len(lines):
        l = re.sub(r"\s+", " ", lines[i]).strip()
        if re.match(r"^A Level subject content", l):
            level = "A2"
        want = topic["n"] + 1 if topic else 1
        ahead = [re.sub(r"\s+", " ", a).strip() for a in lines[i + 1:i + 300]]
        if l == str(want) and ahead and ahead[0][:1].isupper() \
                and any(re.match(rf"^{want}\.1( |$)", a) for a in ahead):
            topic = {"n": want, "title": ahead[0], "level": level, "subtopics": []}
            topics.append(topic)
            sub = outcome = None
            i += 2
            continue
        m_sub = re.match(r"^(\d{1,2})\.(\d{1,2})(?: (.+))?$", l)
        if m_sub and topic and int(m_sub[1]) == topic["n"] and \
                (not sub or int(m_sub[2]) == int(sub["id"].split(".")[1]) + 1 or not topic["subtopics"]):
            title = m_sub[3] or (ahead[0] if ahead else "")
            sub = {"id": f"{m_sub[1]}.{m_sub[2]}", "title": title.strip(), "outcomes": []}
            topic["subtopics"].append(sub)
            outcome = None
            i += 1 if m_sub[3] else 2
            continue
        m_out = re.match(r"^(\d{1,2})(?: (.+))?$", l)
        if l in skip or l.startswith("Candidates should be able to"):
            pass
        elif sub is not None and m_out and int(m_out[1]) == len(sub["outcomes"]) + 1:
            outcome = {"n": int(m_out[1]), "text": (m_out[2] or "").strip()}
            sub["outcomes"].append(outcome)
        elif outcome is not None:
            outcome["text"] = (outcome["text"] + " " + l).strip()
        i += 1
    return {"spec": code, "source": pdf.name, "topics": topics}


def ial(pdf: Path) -> dict:
    doc = pymupdf.open(pdf)
    units: dict[str, dict] = {}
    unit = section = item = None
    for page in doc:
        rows = []
        for b in page.get_text("dict")["blocks"]:
            for ln in b.get("lines", []):
                t = "".join(s["text"] for s in ln["spans"]).strip()
                if t:
                    rows.append((round(ln["bbox"][1]), round(ln["bbox"][0]), t))
        rows.sort()
        for y, x, t in rows:
            if y > 780 or y < 55:
                continue
            m_unit = re.match(r"^([A-Z]{1,2}\d)\.3(\s+Unit content)?$", t)
            if m_unit and x < 80:
                unit = units.setdefault(m_unit[1], {"unit": m_unit[1], "sections": []})
                section = item = None
                continue
            if unit is None:
                continue
            if re.match(r"^Assessment information|^[A-Z]{1,2}\d\.4|^Unit [A-Z]{1,2}\d:", t) and x < 80:
                unit = None
                continue
            m_sec = re.match(r"^(\d{1,2})\.\s+(.+?)(\s+continued)?$", t)
            if m_sec and x < 80:
                if not m_sec[3]:
                    section = {"n": int(m_sec[1]), "title": m_sec[2].strip(), "items": []}
                    unit["sections"].append(section)
                continue
            m_item = re.fullmatch(r"(\d{1,2})\.(\d{1,2})", t)
            if m_item and x < 80 and section:
                used = {i["id"] for sec in unit["sections"] for i in sec["items"]}
                iid = t if int(m_item[1]) == section["n"] and t not in used else f"{section['n']}.{len(section['items']) + 1}"
                item = {"id": iid, "text": "", "guidance": ""}  # official spec has numbering typos (S1 §6, FP2 §7)
                section["items"].append(item)
                continue
            if item is None or t in ("What students need to learn:", "Guidance"):
                continue
            key = "text" if x < 250 else "guidance"
            item[key] = (item[key] + " " + t).strip()
    return {"spec": "IAL-maths", "source": pdf.name, "units": list(units.values())}


if __name__ == "__main__":
    RAW.mkdir(parents=True, exist_ok=True)
    specs = ROOT / "sources" / "specs"
    jobs = {"9701": caie(specs / "9701-2025-2027.pdf", "9701"), "9702": caie(specs / "9702-2025-2027.pdf", "9702"),
            "9701-2028": caie(specs / "9701-2028-2030.pdf", "9701"), "9702-2028": caie(specs / "9702-2028-2030.pdf", "9702"),
            "ial-maths": ial(specs / "ial-maths-spec.pdf")}
    for name, data in jobs.items():
        data = tidy(data)
        (RAW / f"{name}.json").write_text(json.dumps(data, ensure_ascii=False, indent=1))
        if "topics" in data:
            n = sum(len(s["outcomes"]) for t in data["topics"] for s in t["subtopics"])
            print(name, len(data["topics"]), "topics", sum(len(t["subtopics"]) for t in data["topics"]), "subtopics", n, "outcomes")
        else:
            for u in data["units"]:
                print(name, u["unit"], len(u["sections"]), "sections", sum(len(s["items"]) for s in u["sections"]), "items")
    sys.exit(0)
