"""Collect the learner's existing Anki cards so pack flashcards that duplicate them are not exported again.

  python build/anki_existing.py            -> build/work/anki_existing.json  (normalised fronts per deck)
  python build/anki_existing.py mark       -> sets "in_anki": true on duplicate flashcards in build/out/packs
"""
from __future__ import annotations

import html
import json
import re
import sqlite3
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EDU = Path("/Users/sora/Miscellaneous/02 Education")
OUT = ROOT / "build/work/anki_existing.json"


def _norm(text: str) -> set[str]:
    text = html.unescape(re.sub(r"<[^>]+>", " ", text)).lower()
    text = re.sub(r"\\[()\[\]]|\$", " ", text)
    return {w for w in re.findall(r"[a-z0-9]+", text) if len(w) > 2}


def collect() -> dict:
    decks = {}
    for apkg in sorted(EDU.rglob("*.apkg")):
        with tempfile.TemporaryDirectory() as tmp, zipfile.ZipFile(apkg) as z:
            name = next((n for n in z.namelist() if n.startswith("collection.anki2")), None)
            if not name:
                continue
            z.extract(name, tmp)
            con = sqlite3.connect(Path(tmp) / name)
            fronts = [r[0].split("\x1f")[0] for r in con.execute("select flds from notes")]
            con.close()
        decks[str(apkg.relative_to(EDU))] = [{"front": f, "words": sorted(_norm(f))} for f in fronts]
    OUT.write_text(json.dumps(decks, ensure_ascii=False, indent=1))
    return {k: len(v) for k, v in decks.items()}


def mark() -> int:
    existing = [set(c["words"]) for cards in json.loads(OUT.read_text()).values() for c in cards]
    marked = 0
    for pack_path in (ROOT / "build/out/packs").glob("*/*.json"):
        pack = json.loads(pack_path.read_text())
        changed = False
        for card in pack.get("flashcards", []):
            w = _norm(card["front"])
            if w and any(len(w & e) / len(w | e) >= 0.7 for e in existing if e):
                if not card.get("in_anki"):
                    card["in_anki"] = True
                    changed = True
                    marked += 1
        if changed:
            pack_path.write_text(json.dumps(pack, ensure_ascii=False, indent=1))
    return marked


if __name__ == "__main__":
    print(json.dumps(mark() if sys.argv[1:] == ["mark"] else collect()))
