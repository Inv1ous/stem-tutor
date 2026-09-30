"""Blurting (free recall): write everything you remember about a subtopic, then see what you left out.

Free recall is one of the strongest forms of retrieval practice. Scoring needs no AI: each idea (KC) has key terms
(its syllabus glossary and title words); an idea counts as recalled when enough of its terms appear in what you wrote.
Ideas you left out are pulled forward for review.
"""
from __future__ import annotations

import re

STOP = set("""a an and are as at be by can for from has have how in into is it its of on or that the their them then
there these this those to use used using what when where which with within without you your define state explain
describe determine calculate show understand recall represent quantities quantity simple including""".split())


def _stem(word: str) -> str:
    for suf in ("ings", "ing", "ies", "es", "ed", "s"):
        if len(word) > len(suf) + 3 and word.endswith(suf):
            return word[: -len(suf)] + ("y" if suf == "ies" else "")
    return word


def _tokens(text: str) -> set[str]:
    return {_stem(w) for w in re.findall(r"[a-z][a-z0-9]+", (text or "").lower())}


def terms(packs, kc: str) -> list[tuple[str, set[str]]]:
    """Key terms for an idea: glossary entries (whole phrases) plus distinctive title words."""
    k = packs.kc(kc)
    out: list[tuple[str, set[str]]] = []
    for g in k.get("glossary", []) or []:
        toks = {t for t in _tokens(g) if t not in STOP}
        if toks:
            out.append((g, toks))
    for w in _tokens(k.get("title", "")):
        if w not in STOP and len(w) >= 4 and not any(w in toks for _, toks in out):
            out.append((w, {w}))
    return out


def score(packs, subtopic: str, text: str) -> dict:
    said = _tokens(text)
    ideas = {}
    for kc in [k for k, v in packs.kcs.items() if v["subtopic"] == subtopic]:
        ts = terms(packs, kc)
        hits = [label for label, toks in ts if toks <= said]
        need = 1 if len(ts) <= 2 else 2
        ideas[kc] = {"title": packs.kc(kc)["title"], "hits": hits,
                     "missed_terms": [label for label, toks in ts if not toks <= said],
                     "recalled": len(hits) >= need if ts else False}
    recalled = [kc for kc, v in ideas.items() if v["recalled"]]
    return {"subtopic": subtopic, "ideas": ideas, "recalled": recalled,
            "missed": [kc for kc in ideas if kc not in recalled], "words": len(re.findall(r"\S+", text or ""))}
