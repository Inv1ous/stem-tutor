"""The "Shortcuts & Elegant Methods" course: its entries, parsed from the ranked notes in sources/shortcuts/.

Each source note (sources/shortcuts/base/<spec>.md, written by hand; sources/shortcuts/research/<name>.md, written by a
research worker) holds entries in one of two layouts:

    - **Title** `10/10`. body ...            (a bullet, body may continue on the lines below)
    **Title.** `9/10` body ...               (a paragraph)

under `## <section>` headings (and optional `### <topic>` headings). An entry is the unit the course teaches and the
recall queue schedules. Its id is stable (`SEM-<spec>-<slug>`), so recall history survives a re-parse.

  shortcuts.py parse            write build/out/shortcuts/<spec>.json for every spec and print the counts
  shortcuts.py list [--spec S] [--min N]   a one-line view of the entries that pass the filters
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "plugin/stem-tutor/skills/tutor/scripts"))
from tutorlib.shortcuts import level_of, select  # noqa: E402
SOURCES = REPO / "sources/shortcuts"
OUT = REPO / "build/out/shortcuts"

_SCORE = re.compile(r"`\s*(\d{1,2})\s*/\s*10\s*`")
_START = re.compile(r"^(?:[-*]\s+)?\*\*(?P<title>.+?)\*\*\s*(?P<rest>.*)$")
_SRC = re.compile(r"\s*\[src:\s*([^\]]+)\]\s*$")


def slug(text: str) -> str:
    text = re.sub(r"\$[^$]*\$", " ", text)  # maths in a title does not name it
    words = re.findall(r"[a-z0-9]+", text.lower())
    return "-".join(words)[:48].strip("-") or "entry"


def parse_note(text: str, spec: str, origin: str = "base") -> list[dict]:
    """The entries of one ranked note, in order. A line that is not an entry and not a heading continues the last one;
    the ranked-index table and the front matter are skipped."""
    out: list[dict] = []
    section, topic = "", ""
    cur: dict | None = None
    skip = False  # the front matter and the ranked index hold no entries
    text = re.sub(r"\A---\n.*?\n---\n", "", text, count=1, flags=re.S)  # front matter
    seen: dict[str, int] = {}

    def close() -> None:
        nonlocal cur
        if cur is not None:
            body = "\n".join(cur.pop("_lines")).strip()
            src = _SRC.search(body)
            if src:
                cur["source"], body = src.group(1).strip(), body[:src.start()].rstrip()
            cur["body"] = body
            out.append(cur)
        cur = None

    for line in text.splitlines():
        if m := re.match(r"\s*<!--\s*spec:\s*(\S+?)\s*-->\s*$", line):  # a research note covering several specs
            close()
            spec = m.group(1)
            continue
        if line.startswith("## "):
            close()
            section, topic = line[3:].strip(), ""
            skip = section.lower().startswith(("ranked index", "quick-check list", "how to use"))
            continue
        if line.startswith("### "):
            close()
            topic = line[4:].strip()
            continue
        if skip or line.startswith(("|", ">")):
            if cur is not None and line.startswith("|"):
                cur["_lines"].append(line)  # a table inside an entry (a lookup of the five suvat cases)
            continue
        m = _START.match(line)
        score = _SCORE.search(line) if m else None
        if m and score:
            close()
            title = re.sub(r"[.:]$", "", m.group("title").strip())
            base = f"SEM-{spec}-{slug(title)}"
            seen[base] = seen.get(base, 0) + 1
            rest = _SCORE.sub("", m.group("rest"), count=1).lstrip(" .:").strip()
            if not m.group("rest").strip():  # the score sits on the next line only in a broken entry: keep what is there
                rest = ""
            cur = {"id": base if seen[base] == 1 else f"{base}-{seen[base]}", "spec": spec, "section": section,
                   "topic": topic, "title": title, "score": int(score.group(1)), "origin": origin, "_lines": [rest]}
            continue
        if line.strip() == "---":
            close()
            continue
        if cur is not None:
            cur["_lines"].append(line)
    close()
    return out


def load(spec: str | None = None, sources: Path | None = None) -> list[dict]:
    """Every entry of every source note (base first, then research), de-duplicated by id."""
    root = sources or SOURCES
    entries: dict[str, dict] = {}
    for origin in ("base", "research"):
        for path in sorted((root / origin).glob("*.md")) if (root / origin).is_dir() else []:
            name = path.stem
            specs = [name] if origin == "base" else _research_specs(path)
            for e in parse_note(path.read_text(encoding="utf-8"), specs[0], origin):
                if spec and e["spec"] != spec:
                    continue
                entries.setdefault(e["id"], e)
    return list(entries.values())


def _research_specs(path: Path) -> list[str]:
    """A research note is named for the specs it covers, `9702.md` or `pure.md`; the first line of the file may say
    `spec: P1` per section (`<!-- spec: P2 -->`). Without that, the file stem is the spec."""
    return [path.stem]


def parse_all(out: Path | None = None, sources: Path | None = None) -> dict[str, int]:
    out = out or OUT
    out.mkdir(parents=True, exist_ok=True)
    by: dict[str, list[dict]] = {}
    for e in load(sources=sources):
        by.setdefault(e["spec"], []).append(e)
    for spec, rows in by.items():
        (out / f"{spec}.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return {s: len(r) for s, r in sorted(by.items())}


def main(argv: list[str]) -> int:
    cmd = argv[0] if argv else "parse"
    if cmd == "parse":
        counts = parse_all()
        for spec, n in counts.items():
            print(f"{spec}: {n} entries")
        print(f"total {sum(counts.values())}")
        return 0
    if cmd == "list":
        spec = argv[argv.index("--spec") + 1] if "--spec" in argv else None
        low = int(argv[argv.index("--min") + 1]) if "--min" in argv else 0
        for e in select(load(spec), {"min_score": low}):
            print(f"{e['score']:>2}/10  {e['id']}  [{e['section'][:34]}]  {e['title'][:70]}")
        return 0
    print(__doc__)
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
