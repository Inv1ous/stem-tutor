"""Does the content follow the syllabus? Checks with no AI.

`check` is a gate a chapter must pass before it is signed. For every learning outcome (KC) of the chapter:
- no-teach-card: it has a teaching card (pack["teach"]), so a lesson never falls back to a generic card;
- note-misses-outcome: the lesson note mentions it at all (one of its syllabus key terms, read as the blurt scorer
  reads them); whether the note really teaches it is the checker's rule 7, which reads the note;
- define-not-covered: an outcome that says "define" has a flashcard or a Define question;
- derive-not-covered: an outcome that says "derive" has a worked example or a Show (that) question.
And for every question a CAIE chapter wrote itself (past-paper wording is official, and Edexcel defines no list):
- command-word: its command word is one the syllabus lists (taken from the chapter's bundle); real papers keep to it.
Enough questions per outcome, constants and formats are validate_pack's job.

`audit` compares a graph with the outcomes extracted from the official syllabus document: every outcome must be
there (missing-outcome, not-in-syllabus), no subtopic may be listed twice (duplicate-subtopic), and wording-lost
flags an outcome that kept under 60% of the syllabus's words.

  python build/syllabus.py <pack.json>      check one chapter
  python build/syllabus.py audit            every graph against build/raw (the syllabus extraction)
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "plugin/stem-tutor/skills/tutor/scripts"))
from tutorlib import blurt  # noqa: E402


ALIASES = {"Show that": "Show (that)", "Show": "Show (that)"}


def _e(rule: str, where: str, detail: str = "") -> dict:
    return {"rule": rule, "where": where, "detail": detail}


class _Outcomes:
    """What the blurt scorer needs to know about a graph's outcomes."""

    def __init__(self, graph: dict):
        self.kcs = {k["id"]: k for k in graph["kcs"]}

    def kc(self, kc: str) -> dict:
        return self.kcs[kc]


def command_words(bundle: str) -> set[str] | None:
    """The syllabus's command words as the bundle lists them, or None when it has no such list."""
    section = re.search(r"^## Command words\n(.*?)(?=^## |\Z)", bundle, flags=re.S | re.M)
    words = set(re.findall(r"^- \*\*(.+?)\*\*", section[1], flags=re.M)) if section else set()
    return words or None


def check(pack: dict, graph: dict, note: str, words: set[str] | None = None) -> list[dict]:
    sub = pack.get("subtopic", "")
    kcs = [k for k in graph["kcs"] if k["subtopic"] == sub]
    out = []
    teach = pack.get("teach") or {}
    cards = {c.get("kc") for c in pack.get("flashcards", [])}
    worked = {w.get("kc") for w in pack.get("worked", [])}
    asked: dict[str, set] = {}
    for it in pack.get("items", []):
        for kc in it.get("kcs") or []:
            asked.setdefault(kc, set()).add(ALIASES.get(it.get("command_word"), it.get("command_word")))
    said, outcomes = blurt._tokens(note), _Outcomes(graph)
    for k in kcs:
        kc, wording = k["id"], k.get("statement", "").lower()
        if kc not in teach:
            out.append(_e("no-teach-card", kc, k.get("title", "")))
        if not any(tokens <= said for _, tokens in blurt.terms(outcomes, kc)):
            out.append(_e("note-misses-outcome", kc, f"none of its key terms: {', '.join(k.get('glossary') or [])}"))
        if re.search(r"\bdefine\b", wording) and kc not in cards and "Define" not in asked.get(kc, ()):
            out.append(_e("define-not-covered", kc, "needs a flashcard or a Define question"))
        if re.search(r"\bderive\b", wording) and kc not in worked and "Show (that)" not in asked.get(kc, ()):
            out.append(_e("derive-not-covered", kc, "needs a worked example or a Show (that) question"))
    if words and graph.get("spec", "").isdigit():
        for it in pack.get("items", []):
            word = ALIASES.get(it.get("command_word"), it.get("command_word"))
            if word and (it.get("source") or {}).get("type") != "past" and word not in words:
                out.append(_e("command-word", f"item {it.get('id')}", f"{word} is not a command word of this syllabus"))
    return out


def audit(official: dict[str, str], graph: dict) -> list[dict]:
    """`official`: outcome id → wording from the syllabus document. Every one must be in the graph; the graph tidies
    the wording (maths markup, extraction debris), so only a statement that lost many of its words is flagged."""
    have = {k["id"]: k.get("statement", "") for k in graph["kcs"]}
    words = lambda s: {w for w in re.findall(r"[a-z0-9]+", re.sub(r"\\[a-zA-Z]+|[$_^{}]", " ", s.lower()))  # noqa: E731
                       if len(w) > 1}
    out = [_e("missing-outcome", kc, text[:120]) for kc, text in official.items() if kc not in have]
    out += [_e("not-in-syllabus", kc, text[:120]) for kc, text in have.items() if kc not in official]
    ids = [s["id"] for s in graph.get("subtopics", [])]
    out += [_e("duplicate-subtopic", sub) for sub in dict.fromkeys(ids) if ids.count(sub) > 1]
    for kc in have:
        want = words(official.get(kc, ""))
        if want and len(want & words(have[kc])) / len(want) < 0.6:
            out.append(_e("wording-lost", kc, f"syllabus: {official[kc][:160]}"))
    return out


def official(spec: str) -> dict[str, str] | None:
    """Outcome id → wording as extracted from the syllabus document (build/raw), or None when it was not extracted."""
    import graph as build_graph
    try:
        skeleton = build_graph.skeleton_caie(spec) if spec.isdigit() else build_graph.skeleton_unit(spec)
    except (OSError, StopIteration, KeyError):
        return None
    return {k["id"]: k["raw"] for k in skeleton["kcs"]}


if __name__ == "__main__":
    problems = []
    if sys.argv[1] == "audit":
        for path in sorted((ROOT / "build/out/specs").glob("*/graph.json")):
            g = json.loads(path.read_text())
            expected = official(g["spec"])
            problems += audit(expected, g) if expected else [_e("not-extracted", g["spec"])]
    else:
        pack = json.loads(Path(sys.argv[1]).read_text())
        g = json.loads((ROOT / f"build/out/specs/{pack['spec']}/graph.json").read_text())
        note = ROOT / "build/out/notes" / pack.get("note", "")
        bundle = ROOT / "build/work/bundles" / f"{pack['subtopic']}.md"
        problems = check(pack, g, note.read_text(encoding="utf-8") if note.is_file() else "",
                         command_words(bundle.read_text(encoding="utf-8")) if bundle.is_file() else None)
    print(json.dumps({"ok": not problems, "errors": problems[:80], "count": len(problems)}, ensure_ascii=False, indent=1))
    sys.exit(1 if problems else 0)
