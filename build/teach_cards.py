"""Teach cards: one per syllabus point (KC), used by lesson mode (motivate → discover → establish → connect → note).

  python build/teach_cards.py check <subtopic>...   validate build/work/teach/<subtopic>.json
  python build/teach_cards.py merge <subtopic>...   validate, then write the valid cards into the pack as pack["teach"]

Card: {"motivate", "establish", "connect", "note", "self_explain", "discover"?: {"stem", "options": {A..D}, "answer",
"explanation"}}. Markdown with $...$ maths; must pass the Obsidian lint.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "plugin/stem-tutor/skills/tutor/scripts"))
from tutorlib import lint  # noqa: E402

LIMITS = {"motivate": 60, "establish": 190, "connect": 60, "self_explain": 45}


def words(s: str) -> int:
    return len(str(s).split())


def check_card(kc: str, card: dict) -> list[str]:
    errs = []
    for f in ("motivate", "establish", "connect", "note", "self_explain"):
        if not str(card.get(f, "")).strip():
            errs.append(f"{kc}: missing {f}")
    for f, n in LIMITS.items():
        if words(card.get(f, "")) > n:
            errs.append(f"{kc}: {f} has {words(card.get(f, ''))} words (max {n})")
    bullets = [l for l in str(card.get("note", "")).splitlines() if l.strip()]
    if not 2 <= len(bullets) <= 7 or not all(l.lstrip().startswith("- ") for l in bullets):
        errs.append(f"{kc}: note must be 2-7 lines each starting '- '")
    d = card.get("discover")
    if d:
        opts = d.get("options") or {}
        if sorted(opts) != ["A", "B", "C", "D"] or d.get("answer") not in opts or not d.get("stem") or not d.get("explanation"):
            errs.append(f"{kc}: discover needs stem, options A-D, answer among them, explanation")
    for f in ("motivate", "establish", "connect", "note", "self_explain"):
        for x in lint.lint(str(card.get(f, ""))):
            errs.append(f"{kc}: {f} lint {x['rule']}: {x.get('message', '')}")
    if d:
        for part in [d.get("stem", ""), d.get("explanation", "")] + list((d.get("options") or {}).values()):
            for x in lint.lint(str(part)):
                errs.append(f"{kc}: discover lint {x['rule']}")
    return errs


def load(sub: str) -> tuple[dict, Path, dict]:
    cards = json.loads((ROOT / f"build/work/teach/{sub}.json").read_text())
    pack_path = next((ROOT / "build/out/packs").glob(f"*/{sub}.json"))
    return cards, pack_path, json.loads(pack_path.read_text())


def main(cmd: str, subs: list[str]) -> int:
    bad = 0
    for sub in subs:
        cards, pack_path, pack = load(sub)
        graph = json.loads((ROOT / f"build/out/specs/{pack['spec']}/graph.json").read_text())
        kcs = [k["id"] for k in graph["kcs"] if k["subtopic"] == sub]
        errs = [f"{k}: no card" for k in kcs if k not in cards] + [f"{k}: not a KC of {sub}" for k in cards if k not in kcs]
        good = {}
        for kc, card in cards.items():
            e = check_card(kc, card)
            errs += e
            if not e and kc in kcs:
                good[kc] = {**card, "source": "pack"}
        print(f"{sub}: {len(good)}/{len(kcs)} valid" + ("".join("\n  - " + e for e in errs) if errs else ""))
        bad += len(errs)
        if cmd == "merge" and good:
            pack["teach"] = good
            pack_path.write_text(json.dumps(pack, ensure_ascii=False, indent=1))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2:]))
