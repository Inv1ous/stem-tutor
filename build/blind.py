"""Blind-solve support: strip answer keys from a pack, then grade an independent solver's answers.

  python build/blind.py strip <pack.json> > questions.json     questions only (templates instantiated, seed 0)
  python build/blind.py compare <pack.json> <answers.json>      disagreements between key and solver

answers.json: {"<item id>": "<answer in tutor syntax: letter, value with unit, or expression>", ...}
plus "<worked id>.faded" for faded examples. A disagreement means the key or the question is suspect.
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "plugin/stem-tutor/skills/tutor/scripts"))
from tutorlib import grade, packs  # noqa: E402

SEED = 0


def _instances(pack: dict):
    for it in pack.get("items", []):
        if it["kind"] in ("mcq", "numeric", "expression"):
            yield it["id"], packs.instantiate(it, random.Random(SEED))
    for w in pack.get("worked", []):
        f = w.get("faded")
        if f:
            kind = "numeric" if "value" in f["answer"] else "expression"
            yield f"{w['id']}.faded", {"kind": kind, "stem": f["problem"], "answer": f["answer"], "marks": 2}


def strip(pack: dict) -> list[dict]:
    out = []
    for iid, inst in _instances(pack):
        q = {"id": iid, "kind": inst["kind"], "stem": inst["stem"]}
        if inst.get("options"):
            q["options"] = inst["options"]
        if inst.get("image"):
            q["image"] = inst["image"]
        if inst["kind"] == "numeric" and inst["answer"].get("unit"):
            q["give_unit"] = True
        out.append(q)
    return out


def compare(pack: dict, answers: dict) -> dict:
    disagreements, agreed, missing = [], 0, []
    for iid, inst in _instances(pack):
        if iid not in answers:
            missing.append(iid)
            continue
        text = str(answers[iid])
        resp = ({"kind": "choice", "value": text.strip()[:1].upper(), "conf": None} if inst["kind"] == "mcq"
                else {"kind": "value", "value": text, "conf": None})
        g = grade.grade_item(inst, resp)
        if g["correct"]:
            agreed += 1
        else:
            key = inst["answer"] if inst["kind"] != "mcq" else inst["answer"]
            disagreements.append({"id": iid, "key": key, "solver": text, "detail": g.get("detail") or g.get("error")})
    return {"agreed": agreed, "disagreements": disagreements, "missing": missing}


if __name__ == "__main__":
    pack = json.loads(Path(sys.argv[2]).read_text())
    if sys.argv[1] == "strip":
        print(json.dumps(strip(pack), ensure_ascii=False, indent=1))
    else:
        print(json.dumps(compare(pack, json.loads(Path(sys.argv[3]).read_text())), ensure_ascii=False, indent=1))
