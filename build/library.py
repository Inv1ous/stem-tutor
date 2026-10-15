"""The sources library: search and read the learner's own PDFs (textbooks, notes, mark schemes) at any folder depth.

  python build/library.py tree [folder]
  python build/library.py search "<terms>" [--folder NAME-FRAGMENT] [--root library|papers|specs|all] [--max N]
  python build/library.py text <pdf path or unique name fragment> [--pages 3-5] [--all]
  python build/library.py for <subtopic id, e.g. 9702-5.1> [--root ...] [--max N]
  python build/library.py figures <pdf> [--pages a-b] [--max N]       candidate figures, page by page
  python build/library.py page <pdf> <n> [--dpi 110] [--box x0,y0,x1,y1]   render a page (or part) to look at
  python build/library.py crop <pdf> --page N --box x0,y0,x1,y1 --to <spec>/<name> [--dpi 200] [--caption T]
                           [--for <subtopic>] [--kc <id>] [--why T]    save a figure for a chapter
  python build/library.py extract <pdf> --page N --index K --to <spec>/<name> [same options]   an embedded image

The library is sources/library/ (override with env STEM_LIBRARY_ROOT); `papers` and `specs` are its sibling folders.
Figures: a box is always x0,y0,x1,y1 as FRACTIONS (0-1) of the page as poppler renders it (after any rotation, cut to
the CropBox), so it does not depend on the dpi. Crops go to build/out/assets/<spec>/<name>.png (env STEM_LIBRARY_ASSETS)
with a <name>.png.json provenance sidecar; they are never committed. Needs poppler and Pillow.
Nothing is registered: any folder name, any depth. Page texts are cached per PDF in <library>/.cache/ and re-read when
a file changes. PDFs are never modified. Needs `pdftotext` (poppler) or the `pypdf` package.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import shutil
import subprocess
import sys
import unicodedata
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CAP = 12000
EMPTY = "library is empty: drop PDFs in sources/library/<any folder>"
CUES = (("worked example", "a worked example"), ("example", "has examples"), ("mark scheme", "mark scheme"),
        ("question", "has questions"), ("summary", "has a summary"), ("definition", "has a definition"))


class Fail(Exception):
    """A plain one-line reason for the user; never a traceback."""


def lib_root() -> Path:
    return Path(os.environ.get("STEM_LIBRARY_ROOT") or ROOT / "sources/library")


def roots(which: str) -> dict[str, Path]:
    lib = lib_root()
    every = {"library": lib, "papers": lib.parent / "papers", "specs": lib.parent / "specs"}
    if which == "all":
        return every
    if which not in every:
        raise Fail(f"unknown root '{which}': use library, papers, specs or all")
    return {which: every[which]}


def pdfs(folder: Path) -> list[Path]:
    """Every PDF under folder at any depth, skipping hidden files and folders (.cache, macOS ._ files)."""
    if not folder.is_dir():
        return []
    out = []
    for dirpath, dirs, files in os.walk(folder):
        dirs[:] = sorted(d for d in dirs if not d.startswith("."))
        out += [Path(dirpath, f) for f in sorted(files) if f.lower().endswith(".pdf") and not f.startswith(".")]
    return out


def show(p: Path) -> str:
    try:
        return str(p.relative_to(ROOT))
    except ValueError:
        return str(p)


def norm(s: str) -> str:
    """Lower-case, accent-free, same length as the input so snippet positions carry over."""
    out = []
    for c in s:
        d = unicodedata.normalize("NFKD", c)
        d = "".join(x for x in d if not unicodedata.combining(x)).casefold()
        out.append(d if len(d) == 1 else (d[:1] or c))
    return "".join(out)


# ---------- extraction and cache ----------

def _poppler(name: str) -> str | None:
    return shutil.which(name) or next((str(Path(d, name)) for d in ("/opt/homebrew/bin", "/usr/local/bin")
                                       if Path(d, name).exists()), None)


def extract(pdf: Path) -> list[str]:
    """Page texts of one PDF."""
    exe = _poppler("pdftotext")
    if exe:
        r = subprocess.run([exe, "-enc", "UTF-8", str(pdf), "-"], capture_output=True, timeout=300)
        if r.returncode:
            raise Fail(f"cannot read {pdf.name}: {r.stderr.decode('utf-8', 'replace').strip()[:100] or 'unreadable PDF'}")
        pages = r.stdout.decode("utf-8", "replace").split("\f")
        return pages[:-1] if len(pages) > 1 and not pages[-1].strip() else pages
    try:
        from pypdf import PdfReader
    except ImportError:
        raise Fail("no PDF reader: install poppler (brew install poppler) or pypdf") from None
    try:
        return [p.extract_text() or "" for p in PdfReader(str(pdf)).pages]
    except Exception as e:  # corrupt or encrypted
        raise Fail(f"cannot read {pdf.name}: {type(e).__name__}") from None


def load(pdf: Path, quiet: bool = False, tag: str = "") -> dict:
    """{"pages": [...], "scanned": bool, "error": str} for one PDF, from the cache when the file is unchanged."""
    st = pdf.stat()
    key = hashlib.sha1(f"{pdf}|{st.st_mtime_ns}|{st.st_size}".encode()).hexdigest()
    cache = lib_root() / ".cache" / f"{key}.json"
    try:
        return json.loads(cache.read_text())
    except (OSError, ValueError):
        pass
    if not quiet:
        print(f"reading {tag or pdf.name} ...", file=sys.stderr, flush=True)
    try:
        pages = extract(pdf)
        rec = {"pages": pages, "scanned": not any(p.strip() for p in pages), "error": ""}
    except Fail as e:
        if "no PDF reader" in str(e):
            raise
        rec = {"pages": [], "scanned": False, "error": str(e)}
    try:
        cache.parent.mkdir(parents=True, exist_ok=True)
        tmp = cache.with_suffix(".tmp")
        tmp.write_text(json.dumps(rec))
        tmp.replace(cache)
    except OSError:
        pass  # a read-only library still searches, just slower
    return rec


# ---------- ranking ----------

def _hits(text: str, terms: list[str]) -> dict[str, list[int]]:
    out = {}
    for t in terms:
        pos = [m.start() for m in re.finditer(re.escape(t), text)][:60]
        if pos:
            out[t] = pos
    return out


def _span(hits: dict[str, list[int]]) -> int:
    """Smallest stretch of text containing one hit of every matched term."""
    if len(hits) < 2:
        return 0
    anchor = min(hits.values(), key=len)
    best = 10 ** 9
    for a in anchor:
        near = [min(p, key=lambda x: abs(x - a)) for p in hits.values()]
        best = min(best, max(near) - min(near))
    return best


def rank_pages(items, terms: list[str], need: int) -> list[tuple[float, Path, int, str, list[str]]]:
    """items: (pdf, page no, original text). A page needs `need` distinct terms; score = terms hit, then closeness."""
    out = []
    for pdf, n, text in items:
        low = norm(text)
        hits = _hits(low, terms)
        if len(hits) < need:
            continue
        score = len(hits) * 10 + 5 / (1 + _span(hits) / 40)
        first = min(p[0] for p in hits.values())
        s = max(0, first - 70)
        snip = re.sub(r"\s+", " ", text[s:s + 200]).strip()
        out.append((score, pdf, n, ("..." if s else "") + snip, list(hits)))
    out.sort(key=lambda r: (-r[0], str(r[1]).casefold(), r[2]))
    return out


def corpus(which: str, folder: str = ""):
    """All PDFs to search -> (items of page texts, files without a text layer, unreadable files)."""
    files = [(r, p) for r, d in roots(which).items() for p in pdfs(d)]
    frag = norm(folder)
    if frag:
        files = [(r, p) for r, p in files if frag in norm(str(p.relative_to(roots(which)[r])))]
    items, scanned, bad = [], [], []
    for i, (r, p) in enumerate(files, 1):
        rec = load(p, tag=f"[{i}/{len(files)}] {p.name}")
        if rec["error"]:
            bad.append((p, rec["error"]))
        elif rec["scanned"]:
            scanned.append(p)
        items += [(p, n, t) for n, t in enumerate(rec["pages"], 1) if t.strip()]
    return files, items, scanned, bad


def notes(scanned, bad) -> None:
    for p in scanned:
        print(f"skipped {show(p)}: no text layer: needs OCR")
    for p, why in bad:
        print(f"skipped {show(p)}: {why}")


# ---------- commands ----------

def find_dir(folder: str) -> Path:
    base = lib_root()
    if not folder:
        return base
    for c in (Path(folder), base / folder, ROOT / folder):
        if c.is_dir():
            return c
    frag = norm(folder)
    hit = [Path(d) for d, _, _ in os.walk(base) if frag in norm(Path(d).name) and not Path(d).name.startswith(".")
           and ".cache" not in Path(d).parts]
    if len(hit) == 1:
        return hit[0]
    raise Fail(f"no folder matches '{folder}'" if not hit else
               f"'{folder}' matches {len(hit)} folders: " + "; ".join(show(h) for h in hit[:10]))


def cmd_tree(a) -> None:
    top = find_dir(a.folder or "")
    if not pdfs(lib_root()) and not a.folder:
        print(EMPTY)
        return

    def size(p: Path) -> str:
        n = p.stat().st_size
        return f"{n / 1e6:.1f} MB" if n >= 1e6 else f"{max(1, round(n / 1e3))} KB"

    def pages(p: Path) -> str:
        exe = _poppler("pdfinfo")
        if exe:
            m = re.search(r"^Pages:\s+(\d+)", subprocess.run([exe, str(p)], capture_output=True, text=True,
                                                             errors="replace").stdout, re.M)
            if m:
                return f"{m[1]} pages"
        rec = load(p, quiet=True)
        return f"{len(rec['pages'])} pages" if rec["pages"] else "? pages"

    def walk(d: Path, depth: int) -> None:
        pad = "  " * depth
        subs = sorted((x for x in d.iterdir() if x.is_dir() and not x.name.startswith(".")), key=lambda x: x.name.casefold())
        for f in pdfs_here(d):
            print(f"{pad}{f.name}  · {pages(f)} · {size(f)}")
        for s in subs:
            n = len(pdfs(s))
            print(f"{pad}{s.name}/  ({n} PDF{'s' * (n != 1)})" if n else f"{pad}{s.name}/  (empty)")
            walk(s, depth + 1)

    def pdfs_here(d: Path) -> list[Path]:
        return sorted((x for x in d.iterdir() if x.is_file() and x.suffix.lower() == ".pdf" and not x.name.startswith(".")),
                      key=lambda x: x.name.casefold())

    print(f"{show(top)}/  ({len(pdfs(top))} PDFs)")
    walk(top, 1)


def cmd_search(a) -> None:
    terms = list(dict.fromkeys(re.findall(r"\w+", norm(a.terms))))
    if not terms:
        raise Fail("give some words to search for")
    files, items, scanned, bad = corpus(a.root, a.folder or "")
    if not files:
        print(EMPTY if a.root == "library" and not a.folder else "no PDFs to search here")
        return
    res = rank_pages(items, terms, len(terms)) or (rank_pages(items, terms, 1) if len(terms) > 1 else [])
    for _, pdf, n, snip, hit in res[:a.max]:
        print(f"{show(pdf)} · page {n} · {snip}")
    if not res:
        print(f"no match for '{a.terms}' in {len(files)} PDF{'s' * (len(files) != 1)}")
    notes(scanned, bad)


def resolve(arg: str) -> Path:
    for c in (Path(arg), ROOT / arg):
        if c.is_file():
            return c
    frag = norm(arg)
    hit = [p for r, d in roots("all").items() for p in pdfs(d) if frag in norm(str(p.relative_to(d.parent)))]
    if len(hit) == 1:
        return hit[0]
    raise Fail(f"no PDF matches '{arg}'" if not hit else
               f"'{arg}' matches {len(hit)} PDFs, name one: " + "; ".join(show(h) for h in hit[:10]))


def page_range(spec: str | None, n: int, pdf: Path) -> tuple[int, int]:
    """'3' or '3-5' -> (lo, hi) within a PDF of n pages; no spec means every page."""
    if not spec:
        return 1, n
    m = re.fullmatch(r"(\d+)(?:-(\d+))?", spec.strip())
    if not m:
        raise Fail("--pages looks like 3 or 3-5")
    lo, hi = int(m[1]), int(m[2] or m[1])
    if lo > hi or lo < 1 or lo > n:
        raise Fail(f"{pdf.name} has {n} pages; asked for {spec}")
    return lo, min(hi, n)


def cmd_text(a) -> None:
    pdf = resolve(a.pdf)
    rec = load(pdf)
    if rec["error"]:
        raise Fail(rec["error"])
    if rec["scanned"]:
        raise Fail(f"{show(pdf)} has no text layer: needs OCR")
    n = len(rec["pages"])
    lo, hi = page_range(a.pages, n, pdf)
    out = "".join(f"--- page {i} ---\n{rec['pages'][i - 1].strip()}\n" for i in range(lo, hi + 1))
    if not a.all and len(out) > CAP:
        out = out[:CAP] + f"\n[cut at {CAP} characters of {len(out)}: use --pages a-b for the rest, or --all]\n"
    print(out, end="")


_MEMO: dict = {}


def hits_for(subtopic: str, per_kc: int = 3, root: str = "library") -> list[tuple[str, str, list[tuple[str, int, str]]]]:
    """[(kc id, kc title, [(pdf, page, why), ...])] for a chapter: what `for` prints, as data, for the bundle and the
    foundry's evidence check. Empty when the library has no PDFs or the chapter is unknown."""
    import hashlib
    listing = pdfs(roots(root)[root]) if root in roots(root) else []
    if not listing:
        return []
    fp = hashlib.sha1("\n".join(f"{f}|{f.stat().st_size}|{f.stat().st_mtime_ns}" for f in sorted(listing)).encode()).hexdigest()
    cache = lib_root() / ".cache" / "hits" / f"{subtopic}.{per_kc}.json"  # the same library gives the same hits: ask once
    try:
        saved = json.loads(cache.read_text())
        if saved.get("fp") == fp:
            return [(k, t, [tuple(r) for r in rows]) for k, t, rows in saved["rows"]]
    except (OSError, ValueError, KeyError):
        pass
    if _MEMO.get("fp") != fp:  # the library is read once per process, however many chapters are asked about
        _MEMO.clear()
        _MEMO.update(fp=fp, corpus=corpus(root))
    files, items, _, _ = _MEMO["corpus"]
    if not files:
        return []
    kcs = []
    for g in sorted((Path(os.environ.get("STEM_LIBRARY_SPECS") or ROOT / "build/out/specs")).glob("*/graph.json")):
        d = json.loads(g.read_text())
        if any(s["id"] == subtopic for s in d["subtopics"]):
            kcs = [k for k in d["kcs"] if k["subtopic"] == subtopic]
    out = []
    for k in kcs:
        terms = list(dict.fromkeys(norm(t).strip() for t in [k["title"], *k.get("glossary", [])] if t.strip()))
        if len(terms) == 1:
            terms += [w for w in re.findall(r"\w{5,}", norm(k["title"]))]
        res = rank_pages(items, list(dict.fromkeys(terms)), 2 if len(terms) > 1 else 1)
        rows = [(show(pdf), n, ", ".join(hit[:4])) for _, pdf, n, snip, hit in res[:per_kc]]
        out.append((k["id"], k["title"], rows))
    try:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps({"fp": fp, "rows": out}))
    except OSError:
        pass
    return out


def cmd_for(a) -> None:
    files, items, scanned, bad = corpus(a.root)
    if not files:
        print(EMPTY if a.root == "library" else "no PDFs to search here")
        return
    sub, kcs = None, []
    for g in sorted((Path(os.environ.get("STEM_LIBRARY_SPECS") or ROOT / "build/out/specs")).glob("*/graph.json")):
        d = json.loads(g.read_text())
        if any(s["id"] == a.subtopic for s in d["subtopics"]):
            sub = next(s for s in d["subtopics"] if s["id"] == a.subtopic)
            kcs = [k for k in d["kcs"] if k["subtopic"] == a.subtopic]
    if not sub:
        raise Fail(f"unknown subtopic '{a.subtopic}' (like 9702-5.1)")
    print(f"{a.subtopic} {sub['title']}: {len(files)} PDFs searched")
    for k in kcs:
        terms = list(dict.fromkeys(norm(t).strip() for t in [k["title"], *k.get("glossary", [])] if t.strip()))
        if len(terms) == 1:
            terms += [w for w in re.findall(r"\w{5,}", norm(k["title"]))]
        res = rank_pages(items, list(dict.fromkeys(terms)), 2 if len(terms) > 1 else 1)
        seen, shown = set(), 0
        print(f"\n{k['id']} {k['title']}")
        for _, pdf, n, snip, hit in res:
            if shown >= a.max:
                break
            low = norm(snip)
            cue = next((c for w, c in CUES if w in low), "")
            print(f"  {show(pdf)} · page {n} · may add: {', '.join(hit[:4])}{' (' + cue + ')' if cue else ''}")
            shown += 1
        if not shown:
            print("  nothing in the library")
    notes(scanned, bad)


# ---------- figures ----------
# A box is x0,y0,x1,y1 as fractions (0-1) of the page as poppler RENDERS it: after /Rotate, cut to the CropBox
# (pdftoppm -cropbox). pdftotext reports text positions in the uncropped, unrotated page, so caption boxes are
# converted for a cropped page and reported as unknown for a rotated one (look at it with `page` instead).
MIN_SIDE, TINY, MAX_BYTES, PAD = (150, 100), 120, 6_000_000, 6
CAPTION = re.compile(r"^(?:(?:figure|fig\.?|table|chart)\s*\d+|(?:diagram|graph)\s*\d*)(?:[.\-]\d+)*[a-z]?\b", re.I)
EMBED = re.compile(r"!\[\[(Assets/([^\]|/]+)/([^\]|/]+\.png))(?:\|[^\]]*)?\]\]")
SIDECAR_KEYS = ("pdf", "page", "sha256", "caption", "created")


def assets_dir() -> Path:
    return Path(os.environ.get("STEM_LIBRARY_ASSETS") or ROOT / "build/out/assets")


def _tool(name: str) -> str:
    exe = _poppler(name)
    if not exe:
        raise Fail(f"needs {name}: brew install poppler")
    return exe


def _run(cmd: list[str]) -> str:
    r = subprocess.run(cmd, capture_output=True, timeout=300)
    if r.returncode:
        raise Fail(f"{Path(cmd[0]).name} failed: {r.stderr.decode('utf-8', 'replace').strip()[:100] or 'unreadable PDF'}")
    return r.stdout.decode("utf-8", "replace")


def _pil():
    try:
        from PIL import Image, ImageChops
    except ImportError:
        raise Fail("needs Pillow: use the project's .venv/bin/python") from None
    return Image, ImageChops


def pdf_info(pdf: Path, lo: int = 1, hi: int = 1) -> tuple[int, dict[int, dict]]:
    """(page count, {page: {w, h (points as displayed), rot, media, crop}}) for pages lo-hi."""
    out = _run([_tool("pdfinfo"), "-f", str(lo), "-l", str(hi), "-box", str(pdf)])
    n = int((re.search(r"^Pages:\s+(\d+)", out, re.M) or [0, 0])[1])
    info: dict[int, dict] = {}
    for m in re.finditer(r"^Page\s+(\d+) (size|rot|MediaBox|CropBox):\s*(.+)$", out, re.M):
        d = info.setdefault(int(m[1]), {})
        nums = [float(x) for x in re.findall(r"-?\d+(?:\.\d+)?", m[3])]
        d[{"size": "size", "rot": "rot", "MediaBox": "media", "CropBox": "crop"}[m[2]]] = nums
    return n, {p: {"w": d["size"][0], "h": d["size"][1], "rot": int(d["rot"][0]), "media": d["media"], "crop": d["crop"]}
               for p, d in info.items() if len(d) == 4}


def parse_box(text: str) -> list[float]:
    try:
        b = [float(x) for x in text.split(",")]
    except ValueError:
        b = []
    if len(b) != 4 or not (0 <= b[0] < b[2] <= 1 and 0 <= b[1] < b[3] <= 1):
        raise Fail("--box looks like 0.1,0.2,0.9,0.6 (x0,y0,x1,y1 as fractions 0-1 of the page, left/top first)")
    return b


def fmt_box(b) -> str:
    return ",".join(f"{x:.2f}" for x in b)


def text_blocks(pdf: Path, lo: int, hi: int, info: dict) -> dict[int, list[dict] | None]:
    """{page: blocks} from pdftotext -bbox-layout; a block is {box (page fractions), words, lines [(text, box)]}.
    None for a rotated page, whose boxes cannot be mapped."""
    out = _run([_tool("pdftotext"), "-bbox-layout", "-f", str(lo), "-l", str(hi), str(pdf), "-"])
    pages: dict[int, list[dict] | None] = {}
    page, blk, line, mapper = lo - 1, None, None, None
    for m in re.finditer(r"<(page|block|line|word)\b([^>]*)>(?:([^<]*)</word>)?", out):
        kind, attrs = m[1], dict(re.findall(r'(\w+)="([^"]*)"', m[2]))
        if kind == "page":
            page += 1
            pg = info.get(page)
            mw, mh = float(attrs["width"]), float(attrs["height"])
            pages[page] = [] if pg and pg["rot"] == 0 else None
            if pg and pg["rot"] == 0:
                cx0, cy1 = pg["crop"][0] - pg["media"][0], pg["media"][3] - pg["crop"][3]
                mapper = lambda x0, y0, x1, y1, cx0=cx0, cy1=cy1, w=pg["w"], h=pg["h"]: tuple(
                    min(1, max(0, v)) for v in ((x0 - cx0) / w, (y0 - cy1) / h, (x1 - cx0) / w, (y1 - cy1) / h))
            continue
        if pages.get(page) is None:
            continue
        if kind == "word":
            line["words"].append(html.unescape(m[3]))
            continue
        box = mapper(*(float(attrs[k]) for k in ("xMin", "yMin", "xMax", "yMax")))
        if kind == "block":
            blk = {"box": box, "words": 0, "lines": []}
            pages[page].append(blk)
        else:
            line = {"box": box, "words": []}
            blk["lines"].append(line)
    for blocks in pages.values():
        for b in blocks or []:
            b["words"] = sum(len(ln["words"]) for ln in b["lines"])
            for ln in b["lines"]:
                ln["text"] = " ".join(ln["words"])
    return pages


def _columns(body: list[dict], cap: dict) -> tuple[float, float]:
    """The column a caption sits in on a two-column page, else the full width (trimming removes empty margins)."""
    left = [b for b in body if b["box"][2] <= 0.52]
    right = [b for b in body if b["box"][0] >= 0.48]
    if left and right and cap["box"][2] - cap["box"][0] < 0.55:
        return (0.0, 0.5) if (cap["box"][0] + cap["box"][2]) / 2 < 0.5 else (0.5, 1.0)
    return 0.0, 1.0


def propose_box(blocks: list[dict], cap: dict, table: bool) -> list[float] | None:
    """The region above the caption (below it for a table, or when nothing fits above) up to the neighbouring
    paragraph, a block of 8+ words or another caption, within the page's body (0.03-0.95 of its height)."""
    body = [b for b in blocks if b is not cap and (b["words"] >= 8 or b["caption"])]
    c0, c1 = _columns(body, cap)
    near = [b for b in body if b["box"][2] > c0 and b["box"][0] < c1]
    cy0, cy1 = cap["box"][1], cap["lines"][-1]["box"][3]
    above = [0.03, cy0 - 0.004]
    above[0] = max([above[0]] + [b["box"][3] + 0.004 for b in near if b["box"][3] <= cy0])
    below = [cy1 + 0.004, 0.95]
    below[1] = min([below[1]] + [b["box"][1] - 0.004 for b in near if b["box"][1] >= cy1])
    order = (below, above) if table else (above, below)
    for lo, hi in order:
        if hi - lo >= 0.05:
            return [c0, round(lo, 3), c1, round(hi, 3)]
    return None


def _rows(pdf: Path) -> list[dict]:
    """pdfimages -list rows of the whole PDF: page, index within the page (1-based), type, w, h, object, ppi."""
    rows, seen = [], {}
    for ln in _run([_tool("pdfimages"), "-list", str(pdf)]).splitlines()[2:]:
        t = ln.split()
        if len(t) < 14:
            continue
        seen[int(t[0])] = seen.get(int(t[0]), 0) + 1
        rows.append({"page": int(t[0]), "index": seen[int(t[0])], "type": t[2], "w": int(t[3]), "h": int(t[4]),
                     "obj": f"{t[10]} {t[11]}", "ppi": (float(t[12]) or 72, float(t[13]) or 72)})
    return rows


def cmd_figures(a) -> None:
    pdf = resolve(a.pdf)
    n, _ = pdf_info(pdf)
    lo, hi = page_range(a.pages, n, pdf)
    _, info = pdf_info(pdf, lo, hi)
    rows = _rows(pdf)
    pages_with = {}
    for r in rows:
        pages_with.setdefault((r["obj"], r["w"], r["h"]), set()).add(r["page"])
    blocks = text_blocks(pdf, lo, hi, info)
    lines, shown = [], 0
    for p in range(lo, hi + 1):
        pg, found = info.get(p), 0
        for r in (r for r in rows if r["page"] == p and r["type"] == "image"):
            frac = (r["w"] / r["ppi"][0] * 72 / pg["w"], r["h"] / r["ppi"][1] * 72 / pg["h"]) if pg else (0, 0)
            kind = f"raster {r['w']}x{r['h']}px" + (f" (shown ~{frac[0]:.0%}x{frac[1]:.0%} of the page)" if pg else "")
            same = len(pages_with[(r["obj"], r["w"], r["h"])])
            why = ("under 120 px a side" if min(r["w"], r["h"]) < TINY else
                   f"the same image on {same} pages (a logo or header)" if same >= 3 else
                   "a thin strip (a rule or banner)" if max(r["w"], r["h"]) > 8 * min(r["w"], r["h"]) else
                   "a full-page image (a scan): use `page` and `crop`" if min(frac) >= 0.9 else "")
            if why:
                lines.append(f"skip: decorative · page {p} · {kind} · {why}")
            else:
                found += 1
                lines.append(f"p{p}i{r['index']} · page {p} · {kind} · none · box unknown (extract it: "
                             f"extract --page {p} --index {r['index']})")
        bl = blocks.get(p)
        if bl is None:
            lines.append(f"page {p} is rotated: caption boxes unknown, look with `page {a.pdf} {p}`")
            continue
        for b in bl:
            b["caption"] = bool(CAPTION.match(b["lines"][0]["text"])) if b["lines"] else False
        for k, b in enumerate((b for b in bl if b["caption"]), 1):
            found += 1
            text = re.sub(r"\s+", " ", " ".join(ln["text"] for ln in b["lines"]))[:100]
            box = propose_box(bl, b, text.lower().startswith("table"))
            lines.append(f"p{p}c{k} · page {p} · caption · {text} · box {fmt_box(box) if box else 'none (no room)'}")
        words = sum(b["words"] for b in bl)
        cover = sum((ln["box"][2] - ln["box"][0]) * (ln["box"][3] - ln["box"][1]) for b in bl for ln in b["lines"])
        if not found and 3 <= words < 60 and cover < 0.12:
            lines.append(f"p{p}v · page {p} · vector? · none · box 0.00,0.00,1.00,1.00 (little text: maybe a drawing)")
    if not lines:
        lines = [f"no candidate figures on pages {lo}-{hi}"]
    print("\n".join(lines[:a.max]) + (f"\n[cut at {a.max} lines of {len(lines)}: use --pages a-b for the rest]"
                                      if len(lines) > a.max else ""))


def render(pdf: Path, p: int, dpi: int) -> Path:
    """The whole page as a PNG in the cache (as a reader shows it: rotated, cut to the CropBox)."""
    if not 20 <= dpi <= 400:
        raise Fail("--dpi is between 20 and 400")
    n, _ = pdf_info(pdf)
    if not 1 <= p <= n:
        raise Fail(f"{pdf.name} has {n} pages; asked for {p}")
    st = pdf.stat()
    key = hashlib.sha1(f"{pdf}|{st.st_mtime_ns}|{st.st_size}".encode()).hexdigest()[:12]
    out = lib_root() / ".cache/pages" / f"{key}-p{p}-{dpi}.png"
    if not out.is_file():
        out.parent.mkdir(parents=True, exist_ok=True)
        _run([_tool("pdftoppm"), "-f", str(p), "-l", str(p), "-r", str(dpi), "-cropbox", "-png", "-singlefile",
              str(pdf), str(out.with_suffix(""))])
    return out


def cut(im, box: list[float]):
    w, h = im.size
    return im.crop((round(box[0] * w), round(box[1] * h), round(box[2] * w), round(box[3] * h)))


def cmd_page(a) -> None:
    pdf = resolve(a.pdf)
    img = render(pdf, a.n, a.dpi)
    if a.box:
        box = parse_box(a.box)
        out = img.with_name(f"{img.stem}-{fmt_box(box).replace(',', '_')}.png")
        if not out.is_file():
            Image, _ = _pil()
            with Image.open(img) as im:
                cut(im, box).save(out)
        img = out
    print(img)


def trim(im):
    """Cut the uniform white margins, keep PAD px of them; None when nothing is drawn."""
    Image, ImageChops = _pil()
    rgb = im.convert("RGB")
    bb = ImageChops.difference(rgb, Image.new("RGB", rgb.size, (255, 255, 255))).convert("L").point(
        lambda v: 255 if v > 12 else 0).getbbox()
    if not bb:
        return None
    return rgb.crop((max(0, bb[0] - PAD), max(0, bb[1] - PAD), min(rgb.width, bb[2] + PAD), min(rgb.height, bb[3] + PAD)))


def _target(to: str) -> tuple[str, str, Path]:
    m = re.fullmatch(r"([A-Za-z0-9][A-Za-z0-9_-]*)/(.+)", to.strip())
    if not m:
        raise Fail("--to looks like 9702/5-1-fig-circuit (spec/name)")
    name = re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", m[2].lower().removesuffix(".png"))).strip("-")
    if not name:
        raise Fail("--to needs a name with letters or digits")
    dest = assets_dir() / m[1] / f"{name}.png"
    if dest.exists() or dest.with_name(dest.name + ".json").exists():
        raise Fail(f"{m[1]}/{name}.png already exists: choose another name (nothing is overwritten)")
    return m[1], name, dest


def _publish_figure(a, pdf: Path, spec: str, name: str, dest: Path, im, extra: dict) -> None:
    """Check the size, write the PNG and its sidecar, print the embed and caption lines."""
    if im.width < MIN_SIDE[0] or im.height < MIN_SIDE[1]:
        raise Fail(f"the figure is {im.width}x{im.height} px, under {MIN_SIDE[0]}x{MIN_SIDE[1]}: widen the box or raise --dpi")
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".tmp")
    im.save(tmp, format="PNG", optimize=True)
    size = tmp.stat().st_size
    if size > MAX_BYTES:
        tmp.unlink()
        raise Fail(f"the figure is {size / 1e6:.1f} MB, over 6 MB: lower --dpi (try {int(extra.get('dpi') or 150) * 0.7:.0f})")
    side = {"pdf": show(pdf), "page": a.page, **extra, "sha256": hashlib.sha256(tmp.read_bytes()).hexdigest(),
            "caption": a.caption or "", "subtopic": a.subtopic or "", "kc": a.kc or "", "why": a.why or "",
            "created": datetime.now().astimezone().isoformat(timespec="seconds")}
    tmp.replace(dest)
    dest.with_name(dest.name + ".json").write_text(json.dumps(side, ensure_ascii=False, indent=1), encoding="utf-8")
    cap = re.sub(r"\s+", " ", a.caption or "figure").strip()
    print(f"wrote {show(dest)} ({im.width}x{im.height} px, {size // 1000} KB)\n![[Assets/{spec}/{name}.png]]\n"
          f"*Figure: {cap} (source: {pdf.stem}, p.{a.page})*")


def cmd_crop(a) -> None:
    pdf = resolve(a.pdf)
    box = parse_box(a.box or "")
    spec, name, dest = _target(a.to)
    Image, _ = _pil()
    with Image.open(render(pdf, a.page, a.dpi)) as full:
        im = trim(cut(full, box))
    if im is None:
        raise Fail("the box is blank: look at the page again (`page`) and move the box")
    _publish_figure(a, pdf, spec, name, dest, im, {"box": box, "dpi": a.dpi})


def cmd_extract(a) -> None:
    pdf = resolve(a.pdf)
    n, _ = pdf_info(pdf)
    if not 1 <= a.page <= n:
        raise Fail(f"{pdf.name} has {n} pages; asked for {a.page}")
    spec, name, dest = _target(a.to)
    here = [r for r in _rows(pdf) if r["page"] == a.page]
    if not 1 <= a.index <= len(here) or here[a.index - 1]["type"] != "image":
        raise Fail(f"page {a.page} has no image {a.index}: see `figures {a.pdf} --pages {a.page}`")
    import tempfile
    Image, _ = _pil()
    with tempfile.TemporaryDirectory() as tmp:
        _run([_tool("pdfimages"), "-png", "-f", str(a.page), "-l", str(a.page), str(pdf), f"{tmp}/i"])
        files = sorted(Path(tmp).glob("i-*.png"))
        if len(files) != len(here):
            raise Fail(f"cannot match image {a.index} on page {a.page}")
        with Image.open(files[a.index - 1]) as im:
            im.load()
    _publish_figure(a, pdf, spec, name, dest, im, {"index": a.index})


def embeds(text: str) -> list[str]:
    """The `Assets/<spec>/<name>.png` embeds of a note, in order."""
    return [m[1] for m in EMBED.finditer(text)]


def sidecar_of(embed: str) -> Path:
    return assets_dir() / (embed.removeprefix("Assets/") + ".json")


def sidecars_for(subtopic: str) -> list[dict]:
    """The sidecars (plus their `file`) of every figure cropped for a chapter."""
    out = []
    for p in sorted(assets_dir().glob("*/*.png.json")):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(d, dict) and d.get("subtopic") == subtopic:
            out.append({**d, "file": str(p)[:-5]})
    return out


def figure_problems(note_text: str, subtopic: str = "") -> list[str]:
    """For each `![[Assets/<spec>/<name>.png]]` with a provenance sidecar: the file is there, the sidecar is whole,
    the sha matches, and a source caption (the PDF's name and the page) follows within 2 lines."""
    lines, out = note_text.splitlines(), []
    for i, line in enumerate(lines):
        for emb in embeds(line):
            side = sidecar_of(emb)
            if not side.is_file():
                continue  # not a cropped figure (no provenance to check)
            png = assets_dir() / emb.removeprefix("Assets/")
            try:
                d = json.loads(side.read_text(encoding="utf-8"))
                assert isinstance(d, dict) and all(d.get(k) not in (None, "") or k == "caption" for k in SIDECAR_KEYS)
                assert (isinstance(d.get("box"), list) and len(d["box"]) == 4) or isinstance(d.get("index"), int)
            except (OSError, ValueError, AssertionError):
                out.append(f"figure {emb}: its sidecar {side.name} is missing fields or unreadable")
                continue
            if not png.is_file():
                out.append(f"figure {emb}: the file does not exist (crop it again with build/library.py)")
            elif hashlib.sha256(png.read_bytes()).hexdigest() != d["sha256"]:
                out.append(f"figure {emb}: the file changed since it was cropped (sha does not match its sidecar)")
            near = " ".join(lines[i + 1:i + 3]).casefold()
            if Path(str(d["pdf"])).stem.casefold() not in near or not re.search(rf"\b(?:p|pp|page)\.?\s*{d['page']}\b", near):
                out.append(f"figure {emb}: needs a source caption within 2 lines: *Figure: … (source: "
                           f"{Path(str(d['pdf'])).stem}, p.{d['page']})*")
    return out


def cmd_warm(a) -> None:
    n = 0
    for g in sorted((Path(os.environ.get("STEM_LIBRARY_SPECS") or ROOT / "build/out/specs")).glob("*/graph.json")):
        for s in json.loads(g.read_text())["subtopics"]:
            hits_for(s["id"])
            n += 1
    print(f"library hits ready for {n} chapters")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="library.py", description=__doc__.split("\n")[0])
    sp = ap.add_subparsers(dest="cmd", required=True)
    t = sp.add_parser("tree"); t.add_argument("folder", nargs="?")
    s = sp.add_parser("search"); s.add_argument("terms"); s.add_argument("--folder")
    s.add_argument("--root", default="library"); s.add_argument("--max", type=int, default=10)
    x = sp.add_parser("text"); x.add_argument("pdf"); x.add_argument("--pages"); x.add_argument("--all", action="store_true")
    f = sp.add_parser("for"); f.add_argument("subtopic"); f.add_argument("--root", default="library")
    f.add_argument("--max", type=int, default=10)
    sp.add_parser("warm")
    g = sp.add_parser("figures"); g.add_argument("pdf"); g.add_argument("--pages"); g.add_argument("--max", type=int, default=60)
    pg = sp.add_parser("page"); pg.add_argument("pdf"); pg.add_argument("n", type=int)
    pg.add_argument("--dpi", type=int, default=110); pg.add_argument("--box")
    for name in ("crop", "extract"):
        c = sp.add_parser(name); c.add_argument("pdf"); c.add_argument("--page", type=int, required=True)
        c.add_argument("--to", required=True); c.add_argument("--caption"); c.add_argument("--for", dest="subtopic")
        c.add_argument("--kc"); c.add_argument("--why")
        if name == "crop":
            c.add_argument("--box"); c.add_argument("--dpi", type=int, default=200)
        else:
            c.add_argument("--index", type=int, required=True)
    a = ap.parse_args(argv)
    try:
        {"tree": cmd_tree, "search": cmd_search, "text": cmd_text, "for": cmd_for, "warm": cmd_warm, "figures": cmd_figures,
         "page": cmd_page, "crop": cmd_crop, "extract": cmd_extract}[a.cmd](a)
    except Fail as e:
        print(e)
        return 1
    except BrokenPipeError:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
