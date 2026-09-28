"""Mine CAIE Paper 1 multiple-choice questions (question text, options, official key, figure crops).

Text is rebuilt from PDF spans: superscripts/subscripts become Unicode (10², m⁻³, H₂O) and Symbol-font
private-use glyphs are mapped (×, μ, λ …). A question with drawings, images, tabular options or any
glyph that cannot be mapped keeps a PNG crop, and the tutor shows the crop instead of the text.

  python build/mine_mcq.py [code ...]      -> build/work/mcq/<code>.json + build/out/assets/mcq/*.png
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[1]
PAPERS, WORK, ASSETS = ROOT / "sources/papers", ROOT / "build/work/mcq", ROOT / "build/out/assets/mcq"
SYMBOL = {0xB4: "×", 0x6D: "μ", 0x6C: "λ", 0x71: "θ", 0x44: "Δ", 0x57: "Ω", 0x70: "π", 0xB0: "°", 0xB1: "±",
          0xA3: "≤", 0xB3: "≥", 0xAE: "→", 0xAC: "←", 0xDB: "⇌", 0xAB: "↔", 0xF2: "∫", 0x2D: "−", 0x61: "α",
          0x62: "β", 0x67: "γ", 0x72: "ρ", 0x73: "σ", 0x77: "ω", 0x66: "φ", 0x65: "ε", 0x64: "δ", 0x6E: "ν",
          0x74: "τ", 0xB9: "≠", 0xBB: "≈", 0xD6: "√", 0xB5: "∝", 0xA5: "∞", 0x2B: "+", 0x3D: "=", 0x3C: "<",
          0x3E: ">", 0xD7: "·", 0x44: "Δ", 0x53: "Σ", 0x46: "Φ", 0x6B: "κ", 0x68: "η", 0x6A: "φ", 0xA2: "′",
          0xB2: "″", 0x5B: "[", 0x5D: "]", 0x28: "(", 0x29: ")", 0x2F: "/", 0x2C: ",", 0x2E: ".", 0x20: " "}
BOILER = re.compile(r"Permission to reproduce|Copyright Acknowledgements|Cambridge Assessment International Education is part|"
                    r"Cambridge International Education is part|reasonable effort has been made|BLANK PAGE")
FOOTER = re.compile(r"^(© UCLES \d{4}|\d{4}/\d{2}/[A-Z]/[A-Z]/\d{2}|\[Turn over)")
SUP = str.maketrans("0123456789+-–−=()n", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁻⁻⁼⁽⁾ⁿ")
SUB = str.maketrans("0123456789+-–−=()aehklmnopstx", "₀₁₂₃₄₅₆₇₈₉₊₋₋₋₌₍₎ₐₑₕₖₗₘₙₒₚₛₜₓ")
SUPOK = set("0123456789+-–−=()n ")
SUBOK = set("0123456789+-–−=()aehklmnopstx ")


def _glyphs(span) -> tuple[str, bool]:
    ok, out = True, []
    for ch in span["text"]:
        cp = ord(ch)
        if 0xF000 <= cp <= 0xF0FF:
            mapped = SYMBOL.get(cp - 0xF000)
            ok &= mapped is not None
            out.append(mapped or "�")
        else:
            out.append(ch)
    return "".join(out), ok


def _line_text(line) -> tuple[str, bool]:
    spans = [s for s in line["spans"] if s["text"]]
    if not spans:
        return "", True
    base = max(s["size"] for s in spans)
    baseline = max(s["bbox"][3] for s in spans if s["size"] >= base - 0.5)
    parts, ok = [], True
    small_spans = [s for s in spans if s["size"] < base - 1.5 and s["text"].strip()]
    for a, b in zip(small_spans, small_spans[1:]):
        if a["bbox"][0] < b["bbox"][2] and b["bbox"][0] < a["bbox"][2]:
            ok = False  # stacked super/subscript (nuclide notation): only the image is faithful
    for s in spans:
        t, good = _glyphs(s)
        ok &= good
        small = s["size"] < base - 1.5
        if small and t.strip():
            core = t.strip()
            if s["flags"] & 1 or s["bbox"][3] < baseline - 1.5:
                ok &= set(core) <= SUPOK
                t = core.translate(SUP)
            else:
                ok &= set(core) <= SUBOK
                t = core.translate(SUB)
        parts.append(t)
    return re.sub(r"\s+", " ", "".join(parts)).strip(), ok


def _key(ms: Path) -> dict[int, str]:
    text = "\n".join(p.get_text() for p in pymupdf.open(ms))
    return {int(n): a for n, a in re.findall(r"(?m)^\s*(\d{1,2})\s*\n\s*([A-D])\s*\n\s*1\s*$", text)}


def mine_paper(qp: Path, ms: Path, code: str) -> list[dict]:
    key = _key(ms)
    doc = pymupdf.open(qp)
    anchors = []  # (page, y, n)
    want = 1
    for pno, page in enumerate(doc):
        for b in page.get_text("dict")["blocks"]:
            for ln in b.get("lines", []):
                for s in ln["spans"]:
                    if s["flags"] & 16 and s["bbox"][0] < 60 and s["text"].strip() == str(want):
                        anchors.append((pno, s["bbox"][1], want))
                        want += 1
    stem = qp.stem.replace("_qp", "")  # 9702_s23_12
    series, variant = stem.split("_")[1], stem.split("_")[2]
    out = []
    ASSETS.mkdir(parents=True, exist_ok=True)
    for i, (pno, y0, n) in enumerate(anchors):
        page = doc[pno]
        nxt = anchors[i + 1] if i + 1 < len(anchors) else None
        y1 = nxt[1] - 4 if nxt and nxt[0] == pno else 770
        rect = pymupdf.Rect(40, y0 - 4, page.rect.width - 40, y1)
        lines, ok, opts, cur = [], True, {}, None
        blocks = page.get_text("dict", clip=rect)["blocks"]
        for b in blocks:  # copyright notice below the last question: keep it out of the crop too
            if BOILER.search(" ".join(s["text"] for ln in b.get("lines", []) for s in ln["spans"])) and b["bbox"][1] > y0 + 20:
                rect.y1 = min(rect.y1, b["bbox"][1] - 2)
        for b in blocks:
            btext = " ".join(s["text"] for ln in b.get("lines", []) for s in ln["spans"])
            if BOILER.search(btext) or FOOTER.match(btext.strip()):
                continue
            for ln in b.get("lines", []):
                t, good = _line_text(ln)
                ok &= good
                if not t or t == str(n):
                    continue
                if re.fullmatch(r"[\d₀-₉⁰-⁹⁺⁻]{1,4}", t):
                    ok = False  # a stray line of bare digits is stacked notation or a diagram label
                if not lines and not opts and t.startswith(f"{n} "):
                    t = t[len(str(n)) + 1:]
                first = ln["spans"][0]
                if first["flags"] & 16 and first["text"].strip() in "ABCD" and len(first["text"].strip()) == 1:
                    cur = first["text"].strip()
                    rest = t[1:].strip()
                    opts[cur] = rest
                    continue
                if cur and ln["bbox"][0] > 80:
                    opts[cur] = (opts[cur] + " " + t).strip()
                else:
                    cur = None
                    lines.append(t)
        drawings = [d for d in page.get_drawings() if pymupdf.Rect(d["rect"]).intersects(rect)]
        images = [im for im in page.get_image_info() if pymupdf.Rect(im["bbox"]).intersects(rect)]
        tabular = len(opts) < 4 or any(not v for v in opts.values())
        figure = bool(drawings or images) or tabular or not ok
        qid = f"{stem}_q{n}"
        crop = None
        if figure:
            crop = f"Assets/mcq/{qid}.png"
            pix = page.get_pixmap(clip=rect, dpi=130, colorspace=pymupdf.csGRAY)
            pix.save(ROOT / "build/out" / crop)
        out.append({"id": qid, "code": code, "series": series, "variant": variant, "q": n,
                    "stem": "\n".join(lines).strip(), "options": opts if len(opts) == 4 else None,
                    "answer": key.get(n), "figure": figure, "image": crop,
                    "ref": f"CAIE {code} · {_series_name(series)} · P{variant} · Q{n}"})
    return out


def _series_name(s: str) -> str:
    return {"s": "Jun", "w": "Nov", "m": "Mar"}[s[0]] + " 20" + s[1:]


if __name__ == "__main__":
    WORK.mkdir(parents=True, exist_ok=True)
    for code in sys.argv[1:] or ["9701", "9702"]:
        items, problems = [], []
        for qp in sorted((PAPERS / code).rglob(f"{code}_*_qp_1[123].pdf")):
            ms = qp.with_name(qp.name.replace("_qp_", "_ms_"))
            if not ms.exists():
                problems.append(f"{qp.name}: no mark scheme")
                continue
            got = mine_paper(qp, ms, code)
            if len(got) != 40 or any(g["answer"] is None for g in got):
                problems.append(f"{qp.name}: {len(got)} questions, {sum(g['answer'] is None for g in got)} without key")
            items += got
        (WORK / f"{code}.json").write_text(json.dumps(items, ensure_ascii=False, indent=1))
        text_ok = sum(not i["figure"] for i in items)
        print(f"{code}: {len(items)} MCQs, {text_ok} text-renderable, {len(items) - text_ok} with crops")
        for p in problems:
            print("  ", p)
