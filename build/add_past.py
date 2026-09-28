"""Append every remaining tagged past-paper MCQ to its subtopic pack as an "extra" tier item.

Drafted packs contain ~12 fully explained past MCQs; the rest of the bank still gives years of fresh
retrieval practice. Extra items carry the official key and any examiner comment; the engine serves
them only after the explained items.

  python build/add_past.py <pack.json> [...]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def add(pack_path: Path) -> int:
    pack = json.loads(pack_path.read_text())
    spec, sub = pack["spec"], pack["subtopic"]
    bank = ROOT / f"build/work/mcq/{spec}.tagged.json"
    if not bank.exists():
        return 0
    used = {(it.get("source") or {}).get("ref") for it in pack["items"]} | {it["id"] for it in pack["items"]}
    pack["items"] = [it for it in pack["items"] if it.get("tier") != "extra"]  # idempotent rebuild
    n = 0
    for m in json.loads(bank.read_text()):
        kcs = [k for k in m.get("kcs") or [] if k.startswith(sub + ".")]
        if m.get("off_syllabus") or not kcs or m["id"] in used or m["ref"] in used or not m.get("answer"):
            continue
        if not m.get("options") and not m.get("image"):
            continue
        n += 1
        pack["items"].append({
            "id": f"{sub}-x{n:03d}", "kcs": kcs[:2], "kind": "mcq", "difficulty": 3, "command_word": None,
            "source": {"type": "past", "ref": m["ref"], "qid": m["id"]}, "stem": m["stem"],
            "options": m.get("options"), "answer": m["answer"], "image": m.get("image"), "marks": 1,
            "tier": "extra", "explanation": None, **({"examiner": m["er"][:600]} if m.get("er") else {}),
        })
    pack_path.write_text(json.dumps(pack, ensure_ascii=False, indent=1))
    return n


if __name__ == "__main__":
    for p in sys.argv[1:]:
        print(p, add(Path(p)), "extra items")
