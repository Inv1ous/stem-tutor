"""The sources library: search and read the learner's own PDFs (textbooks, notes, mark schemes) at any folder depth.

  python build/library.py tree [folder]
  python build/library.py search "<terms>" [--folder NAME-FRAGMENT] [--root library|papers|specs|all] [--max N]
  python build/library.py text <pdf path or unique name fragment> [--pages 3-5] [--all]
  python build/library.py for <subtopic id, e.g. 9702-5.1> [--root ...] [--max N]

The library is sources/library/ (override with env STEM_LIBRARY_ROOT); `papers` and `specs` are its sibling folders.
Nothing is registered: any folder name, any depth. Page texts are cached per PDF in <library>/.cache/ and re-read when
a file changes. PDFs are never modified. Needs `pdftotext` (poppler) or the `pypdf` package.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import unicodedata
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


def cmd_text(a) -> None:
    pdf = resolve(a.pdf)
    rec = load(pdf)
    if rec["error"]:
        raise Fail(rec["error"])
    if rec["scanned"]:
        raise Fail(f"{show(pdf)} has no text layer: needs OCR")
    n = len(rec["pages"])
    lo, hi = 1, n
    if a.pages:
        m = re.fullmatch(r"(\d+)(?:-(\d+))?", a.pages.strip())
        if not m:
            raise Fail("--pages looks like 3 or 3-5")
        lo, hi = int(m[1]), int(m[2] or m[1])
        if lo > hi or lo < 1 or lo > n:
            raise Fail(f"{pdf.name} has {n} pages; asked for {a.pages}")
    out = "".join(f"--- page {i} ---\n{rec['pages'][i - 1].strip()}\n" for i in range(lo, min(hi, n) + 1))
    if not a.all and len(out) > CAP:
        out = out[:CAP] + f"\n[cut at {CAP} characters of {len(out)}: use --pages a-b for the rest, or --all]\n"
    print(out, end="")


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


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="library.py", description=__doc__.split("\n")[0])
    sp = ap.add_subparsers(dest="cmd", required=True)
    t = sp.add_parser("tree"); t.add_argument("folder", nargs="?")
    s = sp.add_parser("search"); s.add_argument("terms"); s.add_argument("--folder")
    s.add_argument("--root", default="library"); s.add_argument("--max", type=int, default=10)
    x = sp.add_parser("text"); x.add_argument("pdf"); x.add_argument("--pages"); x.add_argument("--all", action="store_true")
    f = sp.add_parser("for"); f.add_argument("subtopic"); f.add_argument("--root", default="library")
    f.add_argument("--max", type=int, default=10)
    a = ap.parse_args(argv)
    try:
        {"tree": cmd_tree, "search": cmd_search, "text": cmd_text, "for": cmd_for}[a.cmd](a)
    except Fail as e:
        print(e)
        return 1
    except BrokenPipeError:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
