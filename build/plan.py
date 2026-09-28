"""Almanac (A-Levels.html) -> build/out/plan.json: weekly objectives mapped to KC ids.

Mapping: CAIE refs "9701 §N" -> topic N, narrowed to the subtopics named after the em dash;
Edexcel refs "WMA11 §N[-M]" -> unit sections. When the same KC list recurs across NEW objectives
(e.g. two weeks of "P1 — Algebra and functions"), it is split into consecutive chunks, one per week.

P3 correction (the learner sits WMA13 in June 2027, not 2028): P3 paper practice moves into the
year-1 exam-preparation weeks, P3 leaves the F6 unit lists, and the stale "do not start P3" hold is dropped.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALMANAC = Path("/Users/sora/Miscellaneous/02 Education/00 Important/01 AS:A/A-Levels.html")
UNIT = {"WMA11": "P1", "WMA12": "P2", "WMA13": "P3", "WMA14": "P4", "WST01": "S1", "WST02": "S2", "WST03": "S3",
        "WME01": "M1", "WDM11": "D1", "WFM01": "FP1", "WFM02": "FP2", "WFM03": "FP3"}
P3_PAPER_WEEKS = {70: 27, 73: 29, 77: 31, 80: 33, 84: 35}  # untimed, untimed, timed, exam conditions, weakest first
SITTING_2027 = {"P1", "P2", "P3", "S1", "M1", "FP1"}


def _js_array(js: str, name: str):
    m = re.search(rf"\b{name}\s*=\s*\[", js)
    i = m.end() - 1
    j = js.index("];", i) + 1
    return json.loads(js[i:j])


def load_almanac() -> dict:
    js = re.findall(r"<script[^>]*>(.*?)</script>", ALMANAC.read_text(encoding="utf-8"), flags=re.S)[0]
    return {"OBJ": _js_array(js, "OBJ"), "PAPERS": _js_array(js, "PAPERS"), "PHASES": _js_array(js, "PHASES"),
            "STAGES": _js_array(js, "STAGES")}


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def kcs_for(ref: str, title: str, skel: dict) -> list[str]:
    m = re.match(r"^(9701|9702) §(\d+)", ref)
    if m:
        spec = skel[m[1]]
        topic = f"{m[1]}-{m[2]}"
        subs = [s for s in spec["subtopics"] if s["topic"] == topic]
        named = title.split(" — ", 1)[1].split(";") if " — " in title else []
        chosen = [s for s in subs if any(_norm(n)[:14] and _norm(s["title"]).startswith(_norm(n)[:14]) for n in named)]
        chosen = chosen or subs
        ids = {s["id"] for s in chosen}
        return [k["id"] for k in spec["kcs"] if k["subtopic"] in ids]
    m = re.match(r"^(W[A-Z]{2}\d\d)(?:/01)? §(\d+)(?:-(\d+))?", ref)
    if m and m[1] in UNIT:
        unit = UNIT[m[1]]
        lo, hi = int(m[2]), int(m[3] or m[2])
        return [k["id"] for k in skel[unit]["kcs"] if lo <= int(k["subtopic"].split("-")[1]) <= hi]
    return []


def _unit_of(ref: str) -> tuple[str, int] | None:
    m = re.match(r"^(9701|9702) §(\d+)", ref) or re.match(r"^(W[A-Z]{2}\d\d)(?:/01)? §(\d+)", ref)
    if not m:
        return None
    return (m[1] if m[1] in ("9701", "9702") else UNIT.get(m[1], m[1])), int(m[2])


def _fill_gaps(rows: list[dict], skel: dict) -> list[dict]:
    """Attach KCs no NEW objective covers to the closest NEW objective of the same spec.

    The Almanac names at most three subtopics per topic and omits some sections entirely
    (e.g. P2 §4, FP1 §5 only as an optional buffer); every examinable KC still has to be taught.
    """
    covered = {k for r in rows if r["type"] == "NEW" for k in r["kcs"]}
    new_rows = [(r, _unit_of(r["ref"])) for r in rows if r["type"] == "NEW"]
    added = []
    for spec, data in skel.items():
        by_part: dict[int, list[str]] = {}
        for k in data["kcs"]:
            if k["id"] not in covered:
                part = int(k["subtopic"].split("-")[1].split(".")[0])
                by_part.setdefault(part, []).append(k["id"])
        for part, ids in sorted(by_part.items()):
            same = [(r, u) for r, u in new_rows if u and u[0] == spec]
            if not same:
                continue
            exact = [r for r, u in same if u[1] == part]
            before = sorted((u[1], r["week"], id(r), r) for r, u in same if u[1] < part)
            target = max(exact, key=lambda r: r["week"]) if exact else (before[-1][3] if before else min(
                (r for r, _ in same), key=lambda r: r["week"]))
            target["kcs"] = target["kcs"] + ids
            target.setdefault("added_by_tutor", []).extend(ids)
            added.append({"spec": spec, "part": part, "kcs": ids, "week": target["week"], "objective": target["title"]})
    return added


def build() -> dict:
    alm = load_almanac()
    skel = json.loads((ROOT / "build/work/graph/skeletons.json").read_text())
    rows = []
    for w, subj, verb, title, ref, done, hours, kind, prio in alm["OBJ"]:
        if subj == "exam" and verb == "Hold" and "P3" in title:
            continue  # stale: P3 is taught in weeks 18-25 and sat in June 2027
        if "WMA13/01" in ref and w in P3_PAPER_WEEKS:
            w = P3_PAPER_WEEKS[w]
        if "WMA13" in ref and " · " in ref and w >= 42:
            ref = " · ".join(p for p in ref.split(" · ") if p != "WMA13")
            title = title.replace("P3 and P4", "P4").replace("seven F6 units", "six F6 units")
        rows.append({"week": w, "subject": subj, "verb": verb, "title": title, "ref": ref, "done": done,
                     "hours": hours, "type": kind, "priority": prio, "kcs": kcs_for(ref, title, skel)})
    groups: dict[tuple, list[dict]] = {}
    for r in rows:
        if r["type"] == "NEW" and r["kcs"]:
            groups.setdefault(tuple(r["kcs"]), []).append(r)
    for kcs, rs in groups.items():
        if len(rs) > 1:
            n = len(rs)
            for i, r in enumerate(sorted(rs, key=lambda x: x["week"])):
                r["kcs"] = list(kcs[i * len(kcs) // n:(i + 1) * len(kcs) // n])
    added = _fill_gaps(rows, skel)
    weeks: dict[str, list] = {}
    for r in sorted(rows, key=lambda x: x["week"]):
        weeks.setdefault(str(r.pop("week")), []).append(r)
    sittings, papers = {}, []
    for code, short, name, board, sitting, dur, marks, weight, date in alm["PAPERS"]:
        if short == "P3":
            sitting = "F5 · Jun 2027"
        papers.append({"code": code, "short": short, "name": name, "board": board, "sitting": sitting,
                       "marks": marks, "date": date or None})
        if date:
            sittings[f"{short} ({code.split('/')[0]})"] = date
    return {"source": ALMANAC.name, "start": "2026-09-01", "week2_monday": "2026-09-07", "weeks": weeks,
            "sittings": sittings, "papers": papers, "added_by_tutor": added, "sitting_2027_units": sorted(SITTING_2027),
            "phases": [{"n": p[0], "name": p[1], "from": p[2], "to": p[3], "job": p[5]} for p in alm["PHASES"]],
            "stages": [{"name": s[0], "note": s[1]} for s in alm["STAGES"]]}


if __name__ == "__main__":
    plan = build()
    out = ROOT / "build/out/plan.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(plan, ensure_ascii=False, indent=1))
    objs = [o for ws in plan["weeks"].values() for o in ws]
    new = [o for o in objs if o["type"] == "NEW"]
    unmapped = [o for o in new if not o["kcs"]]
    print(f"{len(objs)} objectives, {len(new)} NEW, {len(unmapped)} NEW without KCs")
    for o in unmapped[:15]:
        print("  unmapped:", o["subject"], o["title"][:60], "|", o["ref"])
    covered = {k for o in new for k in o["kcs"]}
    print("KCs covered by NEW objectives:", len(covered))
