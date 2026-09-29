"""Small, grounded prompts. Each carries a compact CONTEXT packet (~300 tokens) instead of whole notes."""
from __future__ import annotations

from tutorlib import lesson
from tutorlib.session import _display_answer


def _clip(text: str, n: int) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= n else text[: n - 1] + "…"


def context(tutor, kc: str | None = None) -> str:
    s = tutor.session or {}
    lines = ["CONTEXT"]
    if kc and kc in tutor.packs.kcs:
        k = tutor.packs.kc(kc)
        card = lesson.teach_card(tutor, kc)
        lines += [f"Syllabus point ({k['spec']} {kc}): {k['title']} — {k['statement']}",
                  f"What they were taught: {_clip(card.get('establish', ''), 700)}"]
    for n, p in sorted(s.get("presented", {}).items(), key=lambda x: int(x[0])):
        inst = p["inst"]
        opts = "; ".join(f"{k}) {v}" for k, v in (inst.get("options") or {}).items())
        lines.append(f"OPEN question {n} (do not reveal its answer): {_clip(inst.get('stem', ''), 400)} {opts}".rstrip())
    for fb in s.get("last_feedback", [])[-2:]:
        lines.append(f"Just marked: Q{fb['n']} {'correct' if fb.get('correct') else 'wrong'}; answer {fb.get('answer')}. "
                     f"{_clip(fb.get('explanation') or '', 300)}")
    return "\n".join(lines)


def ask(tutor, question: str, kc: str | None) -> str:
    return f"{context(tutor, kc)}\n\nSTUDENT ASKS: {question}"


def explain_again(tutor, kc: str) -> str:
    return (f"{context(tutor, kc)}\n\nThe student wants this idea explained a different way. Start from something "
            "they already know, give one concrete example or analogy, and end with one quick question to check it landed.")


def stuck(tutor, kc: str, mistakes: list[str]) -> str:
    return (f"{context(tutor, kc)}\nTheir mistakes so far: {'; '.join(mistakes) or 'none recorded'}\n\n"
            "They are stuck on this idea. Find the misunderstanding with ONE short guiding question. Do not lecture.")


def own_words(tutor, kc: str, text: str) -> str:
    return (f"{context(tutor, kc)}\n\nThe student explained the idea in their own words: \"{text}\"\n"
            "In at most two sentences: say what is right, and correct anything wrong or missing. No praise padding.")


JUDGE = {"type": "object", "properties": {
    "points": {"type": "array", "items": {"type": "object", "properties": {
        "point": {"type": "string"}, "met": {"type": "boolean"}, "why": {"type": "string"}},
        "required": ["point", "met"]}},
    "feedback": {"type": "string"}}, "required": ["points", "feedback"]}


def judge(stem: str, points: list[str], answer: str) -> str:
    listed = "\n".join(f"{i}. {p}" for i, p in enumerate(points, 1))
    return (f"Mark this A-Level answer strictly against the mark points, the way a Cambridge/Edexcel examiner would.\n"
            f"QUESTION: {stem}\nMARK POINTS:\n{listed}\nSTUDENT ANSWER: {answer}\n\n"
            "Return JSON: {\"points\": [{\"point\": <text>, \"met\": true|false, \"why\": <short>}], "
            "\"feedback\": <one or two sentences>}. A point is met only if its idea is clearly present.")


CARD = {"type": "object", "properties": {
    "motivate": {"type": "string"}, "establish": {"type": "string"}, "connect": {"type": "string"},
    "note": {"type": "string"}, "self_explain": {"type": "string"}},
    "required": ["motivate", "establish", "connect", "note", "self_explain"]}


def teach_card(tutor, kc: str) -> str:
    k = tutor.packs.kc(kc)
    pack = tutor.packs.pack_for_kc(kc) or {}
    facts = "\n".join(f"- {f['front']} → {f['back']}" for f in pack.get("flashcards", []) if f.get("kc") == kc)
    traps = "\n".join(f"- {m['statement']} (fix: {m['refutation']})" for m in pack.get("misconceptions", [])
                      if m["kc"] == kc)
    pres = ", ".join(tutor.packs.kcs[p]["title"] for p in k.get("prereqs", []) if p in tutor.packs.kcs)
    return (f"Write a teaching card for ONE syllabus point, grounded ONLY in the material below.\n"
            f"POINT ({kc}): {k['title']} — {k['statement']}\nBUILDS ON: {pres or 'nothing earlier'}\n"
            f"SUBTOPIC SUMMARY: {_clip(pack.get('outline', ''), 900)}\nFACTS:\n{facts or '-'}\nTRAPS:\n{traps or '-'}\n\n"
            "Return JSON with: motivate (1-2 sentences: why we need this idea now), establish (<=120 words: the idea "
            "itself, built up so it feels discoverable; LaTeX in $...$), connect (1 sentence: how it hangs off what they "
            "know), note (3-5 terse revision bullets, '- ' each, exam wording), self_explain (one question asking them "
            "to explain the idea in their own words).")


def key_of(tutor, n: int) -> tuple[str, str]:
    p = (tutor.session or {}).get("presented", {}).get(str(n))
    return (_display_answer(p["inst"]), p["inst"]["kind"]) if p else ("", "")
