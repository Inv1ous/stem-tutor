"""After-video / baseline diagnosis.

1. `map_dump`: a closed-book brain dump -> candidate KCs (glossary hits) and echoed misconceptions.
2. Bracketing: per KC at most 3 unassisted items, start at difficulty 3, jump up after a success
   (ceiling) or down after a miss (floor). One more item separates a slip from a real gap.
3. `classify`: level (secure/partial/gap) and gap type, which decides the repair method.
"""
from __future__ import annotations

import re
from collections.abc import Sequence

STOP = {"that", "this", "with", "when", "from", "into", "they", "their", "there", "which", "about", "because",
        "thing", "things", "have", "been", "were", "does", "only", "more", "than", "also", "then"}


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z][a-z\-]{3,}", text.lower()) if w not in STOP}


def map_dump(text: str, packs, limit: int = 8) -> dict:
    low = " " + re.sub(r"\s+", " ", text.lower()) + " "
    ranked = []
    for order, (kc_id, kc) in enumerate(packs.kcs.items()):
        hits = [t for t in kc.get("glossary", []) if re.search(r"(?<![a-z])" + re.escape(t.lower()) + r"(?![a-z])", low)]
        if hits:
            ranked.append((-len(hits), order, {"kc": kc_id, "title": kc["title"], "hits": hits}))
    kcs = [r[2] for r in sorted(ranked, key=lambda r: r[:2])[:limit]]
    words = _words(text)
    echoes = []
    for st in sorted({packs.kc(k["kc"])["subtopic"] for k in kcs} or packs.subtopics):
        for m in (packs.pack(st) or {}).get("misconceptions", []):
            mw = _words(m["statement"])
            overlap = len(mw & words) / len(mw) if mw else 0
            if overlap >= 0.6 and len(mw & words) >= 2:
                echoes.append((-overlap, {"id": m["id"], "kc": m["kc"], "subtopic": st, "statement": m["statement"],
                                          "overlap": round(overlap, 2)}))
    return {"kcs": kcs, "misconceptions": [e[1] for e in sorted(echoes, key=lambda e: e[0])]}


def next_difficulty(asked: list[tuple[int, bool]]) -> int | None:
    if not asked:
        return 3
    if len(asked) >= 3:
        return None
    first = asked[0][1]
    if len(asked) == 1:
        return 5 if first else 1
    second = asked[1][1]
    if first and second:
        return None
    if not first and not second:
        return None
    return 4 if first else 3


def classify(asked: list[tuple[int, bool]], errors: Sequence[str] = (), misconceptions: Sequence[str] = ()) -> dict:
    correct = [d for d, ok in asked if ok]
    if correct and max(correct) >= 4:
        level = "secure"
    elif correct:
        level = "partial"
    else:
        level = "gap"
    if level == "secure" and not misconceptions:
        gap_type = None
    elif misconceptions:
        gap_type = "misconception"
    elif "SLIP" in errors and correct:
        gap_type = "slip"
    elif "RECALL" in errors or level == "gap":
        gap_type = "no_schema"
    else:
        gap_type = "procedure"
    return {"level": level, "gap_type": gap_type, "asked": asked, "errors": list(errors),
            "misconceptions": list(misconceptions)}


def needs_repair(result: dict) -> bool:
    return (result["level"] != "secure" and result["gap_type"] != "slip") or result["gap_type"] == "misconception"


def pick(packs, kc: str, want: int, exclude: set[str]):
    options = [i for i in packs.items_for(kc) if i["kind"] in ("mcq", "numeric", "expression") and i["id"] not in exclude]
    if not options:
        return None
    return min(options, key=lambda i: (abs(i.get("difficulty", 3) - want), i["id"]))
