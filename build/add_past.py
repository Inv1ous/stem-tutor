"""Append every remaining tagged past-paper MCQ to its subtopic pack as an "extra" tier item.

Drafted packs contain ~12 fully explained past MCQs; the rest of the bank still gives years of fresh
retrieval practice. Extra items carry the official key and any examiner comment; the engine serves
them only after the explained items.

  python build/add_past.py <pack.json> [...]
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMAGES = ROOT / "build/out/Assets/mcq"


def question_key(it: dict) -> str:
    """Same question, whatever paper it came from: the figure's bytes, else the stem and options as plain words.
    CAIE reuses questions across the timezone variants of a series (P11/P13) and sometimes across years."""
    img = IMAGES / Path(it["image"]).name if it.get("image") else None
    if img and img.exists():
        return "img:" + hashlib.md5(img.read_bytes()).hexdigest()
    words = lambda v: re.sub(r"\W+", " ", json.dumps(v, sort_keys=True, ensure_ascii=False)).strip().lower()
    return "txt:" + words(it.get("stem")) + "|" + words(it.get("options"))


def add(pack_path: Path) -> int:
    pack = json.loads(pack_path.read_text())
    spec, sub = pack["spec"], pack["subtopic"]
    bank = ROOT / f"build/work/mcq/{spec}.tagged.json"
    if not bank.exists():
        return 0
    old_ids = {(it.get("source") or {}).get("qid"): it["id"] for it in pack["items"] if it.get("tier") == "extra"}
    pack["items"] = [it for it in pack["items"] if it.get("tier") != "extra"]  # idempotent rebuild
    used = {(it.get("source") or {}).get("ref") for it in pack["items"]} | {it["id"] for it in pack["items"]}
    seen = {question_key(it) for it in pack["items"] if it["kind"] == "mcq"}
    last = max([int(i.rsplit("-x", 1)[1]) for i in old_ids.values()] or [0])
    n = 0
    for m in json.loads(bank.read_text()):
        kcs = [k for k in m.get("kcs") or [] if k.startswith(sub + ".")]
        if m.get("off_syllabus") or not kcs or m["id"] in used or m["ref"] in used or not m.get("answer"):
            continue
        if not m.get("options") and not m.get("image"):
            continue
        first = (m.get("kcs") or [""])[0].rsplit(".", 1)[0]
        if first != sub and (pack_path.parent / f"{first}.json").exists():  # on two subtopics: kept in its first one's
            continue                                                          # pack once that pack is built
        if (key := question_key(m)) in seen:  # the same question from another paper variant or year
            continue
        seen.add(key)
        n += 1
        if m["id"] not in old_ids:  # ids stay stable across rebuilds, so the learner's history keeps pointing at them
            last += 1
        pack["items"].append({
            "id": old_ids.get(m["id"]) or f"{sub}-x{last:03d}", "kcs": kcs[:2], "kind": "mcq", "difficulty": 3, "command_word": None,
            "source": {"type": "past", "ref": m["ref"], "qid": m["id"]}, "stem": m["stem"],
            "options": m.get("options"), "answer": m["answer"], "image": m.get("image"), "marks": 1,
            "tier": "extra", "explanation": None, **({"examiner": m["er"][:600]} if m.get("er") else {}),
        })
    pack_path.write_text(json.dumps(pack, ensure_ascii=False, indent=1))
    return n


if __name__ == "__main__":
    for p in sys.argv[1:]:
        print(p, add(Path(p)), "extra items")
