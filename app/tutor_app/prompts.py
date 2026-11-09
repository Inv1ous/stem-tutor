"""Small, grounded prompts. Each carries a compact CONTEXT packet (~300 tokens) instead of whole notes."""
from __future__ import annotations

from pathlib import Path
import re

from tutorlib import lesson
from tutorlib import report as tutor_report
from tutorlib.session import _display_answer
from tutorlib.views import CONFIDENCE_LABELS

from .study_sources import references
from .marking_policy import instruction as marking_instruction


def _clip(text: str, n: int) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= n else text[: n - 1] + "…"


def _options(options: dict | None) -> str:
    return " " + "; ".join(f"{k}) {v}" for k, v in options.items()) if options else ""


MATH_RULE = ("Write mathematics as plain LaTeX ($...$ or $$...$$), never as HTML entities (&#x222B;, &int;), "
             "never spell digits as entities; keep fractions as \\frac{1}{2}.")


def _on_screen(act: dict) -> str | None:
    """The step in front of the learner, when it is not a question (only what has been shown: no steps ahead)."""
    kind = act.get("activity")
    if kind in ("explain", "teach"):
        return (f"On screen now, an explanation ({act.get('title') or act.get('kc_title', '')}): "
                f"{_clip(act.get('text') or act.get('outline', ''), 500)}")
    if kind in ("worked", "walkthrough"):
        shown = "; ".join(f"{i}. {st['do']}" for i, st in enumerate(act.get("steps", [])[:act.get("revealed", 0)], 1))
        return f"On screen now, a worked example: {_clip(act.get('problem', ''), 300)} Steps shown so far: {shown or 'none'}"
    if kind == "refute":
        m = (act.get("misconceptions") or [{}])[0]
        m = m if isinstance(m, dict) else {"statement": m}
        return f"On screen now, a common wrong idea being corrected: {_clip(m.get('statement', ''), 200)}"
    if kind == "own_words":
        return f"They are being asked to explain in their own words: {_clip(act.get('prompt', ''), 200)}"
    return None


def _source(item: dict) -> str:
    """"(past paper: CAIE 9702 · Jun 2024 · P11 · Q28; 1 mark; has a diagram)" — what kind of question it is."""
    bits = []
    src = item.get("source")
    ref = src.get("ref") if isinstance(src, dict) else src if isinstance(src, str) else None
    if ref:
        bits.append(f"past paper: {ref}")
    if item.get("marks"):
        bits.append(f"{item['marks']} mark{'s' if item['marks'] != 1 else ''}")
    if item.get("image"):
        bits.append("has a diagram (the image is attached)")
    return f" ({'; '.join(bits)})" if bits else ""


def _marked(q: dict, full: bool = False) -> str:
    if q.get("response") == "don't know" and not q.get("answer"):
        return (f"{_clip(q.get('stem', ''), 1500 if full else 300)}{_options(q.get('options'))}{_source(q)} "
                "Not attempted: the student skipped this question. Do not reveal its answer.").strip()
    verdict = ("correct" if q.get("correct") else
               f"right value but a mark lost ({q['detail']})" if q.get("partial") and q.get("detail") else "wrong")
    confidence = q.get("conf")
    calibration = (f"Self-rated confidence: {CONFIDENCE_LABELS[confidence]} ({confidence}/4). "
                   "This is calibration metadata, not part of the student's answer. "
                   if type(confidence) is int and confidence in CONFIDENCE_LABELS else "")
    return (f"{_clip(q.get('stem', ''), 1500 if full else 300)}{_options(q.get('options'))}{_source(q)} They answered: "
            f"{_clip(str(q.get('response')), 400 if full else 200)} ({verdict}); the answer is {q.get('answer')}. "
            f"{calibration}{_clip(q.get('explanation') or '', 800 if full else 300)}").strip()


def focus(tutor) -> dict | None:
    """The question the learner is looking at: the open one on screen (the last, if several), or else the one just marked."""
    s = tutor.session or {}
    if s.get("presented"):
        n, p = max(s["presented"].items(), key=lambda x: int(x[0]))
        return {"n": int(n), "open": True, **p["inst"], "source": (p["inst"].get("source") or {}).get("ref")
                if isinstance(p["inst"].get("source"), dict) else p["inst"].get("source")}
    if s.get("recent"):
        recent = dict(s["recent"][-1])
        if not (recent.get('image') or recent.get('images')) and recent.get('event'):
            event = next((event for event in tutor.vault.events() if event.get('id') == recent['event']), None)
            question = (event or {}).get('question')
            if isinstance(question, dict):
                image, images = question.get('image'), question.get('images')
                if isinstance(image, str) and image:
                    recent['image'] = image
                if (isinstance(images, list) and images
                        and all(isinstance(path, str) and path for path in images)):
                    recent['images'] = list(images)
        return {**recent, "open": False}
    event = next((e for e in reversed(list(tutor.vault.events())) if e.get("type") == "answer"), None)
    if event:
        return {**_recent_answer(tutor, event), "open": False}
    return None


def _recent_answer(tutor, event: dict) -> dict:
    """Recover the exact instantiated question for menu chat when its session is over."""
    s = tutor.session or {}
    record = next((q for q in reversed(s.get("recent", []))
                   if q.get("event") == event.get("id")), None)
    if record:
        return record
    saved = event.get("question")
    if isinstance(saved, dict):
        return {**saved, "n": event.get("n"), "response": event.get("response"),
                "answer": event.get("key", ""), "correct": (event.get("grade") or {}).get("correct"),
                "conf": event.get("conf")}
    item_id = event.get("item")
    item = tutor_report._pack_item(tutor, item_id) if isinstance(item_id, str) else None
    return {"stem": event.get("stem") or tutor_report._item_stem(tutor, item_id, event.get("params")),
            "options": (item or {}).get("options"), "image": (item or {}).get("image"),
            "images": (item or {}).get("images"), "source": (item or {}).get("source"),
            "marks": (item or {}).get("marks"), "explanation": (item or {}).get("explanation"),
            "kind": (item or {}).get("kind"),
            "n": event.get("n"), "response": event.get("response"), "answer": event.get("key", ""),
            "correct": (event.get("grade") or {}).get("correct"), "conf": event.get("conf")}


def focus_image(tutor) -> "Path | None":
    """The diagram of the question in focus, as a file the AI can be shown (a past-paper diagram question is unanswerable
    from its text alone: the labels come out of the PDF as loose words)."""
    q = focus(tutor)
    rel = (q or {}).get("image") or next(iter((q or {}).get("images") or []), None)
    if not rel:
        return None
    try:
        from tutorlib.asset_library import AssetLibrary
        return AssetLibrary(tutor.vault.root).resolve(rel)
    except (ValueError, OSError):
        return None


def focus_page_count(tutor) -> int:
    """Declared source pages for the same focus as focus_image, without changing its context."""
    q = focus(tutor) or {}
    images = q.get('images')
    if not images and q.get('image') and not q.get('open') and q.get('event'):
        # Recent feedback retains only its primary image; the exact saved event retains all pages.
        event = next((event for event in tutor.vault.events() if event.get('id') == q['event']), None)
        question = (event or {}).get('question')
        images = question.get('images') if isinstance(question, dict) else None
    return len(images or ([q['image']] if q.get('image') else []))


def context(tutor, kc: str | None = None) -> str:
    """What the AI is told: the syllabus point, the step on screen, the question in front of the learner in full (open ones
    with their answers withheld; with its source, marks and diagram), and the last few questions marked, so "why was
    that wrong?", "what does the graph show?" or "what is the full answer here?" can be answered without the learner
    having to copy the question out. With no session running (the menu's chat), the last questions answered stand in."""
    s = tutor.session or {}
    lines = ["CONTEXT"]
    if kc and kc in tutor.packs.kcs:
        k = tutor.packs.kc(kc)
        card = lesson.teach_card(tutor, kc)
        lines += [f"Syllabus point ({k['spec']} {kc}): {k['title']} — {k['statement']}",
                  f"What they were taught: {_clip(card.get('establish', ''), 700)}"]
    if sub := s.get("subtopic"):
        lines.append(f"Session: {s.get('mode', '')} on {sub} {tutor.packs.subtopics.get(sub, {}).get('title', '')}".strip())
    if (step := _on_screen(s.get("now") or {})):
        lines.append(step)
    for n, p in sorted(s.get("presented", {}).items(), key=lambda x: int(x[0])):
        inst = p["inst"]
        lines.append(f"OPEN question {n}, on screen now (do not reveal its answer): {_clip(inst.get('stem', ''), 1500)}"
                     f"{_options(inst.get('options'))}{_source(inst)}")
    if tutor.session:
        recent = s.get("recent", [])[-3:]
        for i, q in enumerate(recent):
            last = i == len(recent) - 1 and not s.get("presented")
            lines.append(f"{'Just marked, on screen now' if last else 'Marked earlier in this session'}, Q{q['n']}: "
                         f"{_marked(q, full=last)}")
    else:
        from tutorlib import model
        for e in [e for e in tutor.vault.events() if e["type"] == "answer"][-3:]:
            q = _recent_answer(tutor, e)
            if not q:
                q = {"stem": e.get("stem", ""), "response": e.get("response"), "conf": e.get("conf"),
                     "correct": model.counts_as_right(e["grade"]), "answer": e.get("key")}
            else:
                q["correct"] = model.counts_as_right(e["grade"])
            lines.append("Answered in their last session: " + _marked(q, full=True))
    return "\n".join(lines) if len(lines) > 1 else "CONTEXT\n(none: a general question, nothing answered yet)"


def ask(tutor, question: str, kc: str | None) -> str:
    supplied = references(tutor, question, kc)
    packet = f"\n\n{supplied}" if supplied else ""
    return f"{context(tutor, kc)}{packet}\n\nSTUDENT ASKS: {question}"


def learn(tutor, kc: str, question: str) -> str:
    """Lesson context without future checks or their answers; open questions receive no example solutions."""
    import json

    session = tutor.session or {}
    active = bool(session.get("presented") or session.get("queue"))
    point = tutor.packs.kc(kc)
    card = lesson.teach_card(tutor, kc)
    progress = tutor.state.get("kcs", {}).get(kc, {})
    safe = {key: card[key] for key in ("plain_words", "terms", "misconceptions", "diagram_descriptions")
            if key in card} if not active else {}
    if not active:
        safe["forms"] = [{key: form[key] for key in ("name", "wordings", "example") if key in form}
                         for form in card.get("forms", []) if isinstance(form, dict)]
    history = {key: progress[key] for key in ("n", "reviews", "active_misconceptions", "last_rating") if key in progress}
    history["gap"] = kc in tutor.state.get("gaps", [])
    probe = (session.get("probe") or {}).get(kc)
    if not active and isinstance(probe, dict):
        history["probe"] = {key: probe[key] for key in ("ok", "conf") if key in probe}
    def misconception_labels(idea: str, record: dict) -> list[dict]:
        if active:
            return []  # even a tracker description may disclose an open question's answer
        lookup = getattr(tutor.packs, "misconception", None)
        subtopic = tutor.packs.kcs.get(idea, {}).get("subtopic")
        if not callable(lookup) or not subtopic:
            return []
        labels = []
        for ident in (record.get("active_misconceptions") or [])[:8]:
            entry = lookup(subtopic, ident)
            if entry and entry.get("kc") == idea and entry.get("statement"):
                labels.append({"id": ident, "statement": entry["statement"]})
        return labels

    history["misconception_details"] = misconception_labels(kc, progress)
    blocks = session.get("blocks") or []
    cursor = session.get("cursor")
    if not active and isinstance(cursor, int) and 0 <= cursor < len(blocks):
        current = blocks[cursor]
        if isinstance(current, dict) and current.get("kind") == "node" and current.get("kc") == kc:
            mistakes = current.get("mistakes") or []
            if isinstance(mistakes, list):
                history["lesson_mistakes"] = [_clip(m, 400) for m in mistakes[-4:] if isinstance(m, str)]
    related = []
    for prior in (point.get("prereqs") or [])[:8]:
        if prior not in tutor.packs.kcs:
            continue
        record = tutor.state.get("kcs", {}).get(prior, {})
        if not record and prior not in tutor.state.get("gaps", []):
            continue
        related.append({"kc": prior, "title": tutor.packs.kcs[prior].get("title", ""),
                        "gap": prior in tutor.state.get("gaps", []),
                        "misconception_details": misconception_labels(prior, record),
                        **{key: record[key] for key in ("n", "reviews", "active_misconceptions", "last_rating")
                           if key in record}})
    if active:
        lines = ["CONTEXT"]
        for n, presented in sorted(session.get("presented", {}).items(), key=lambda x: int(x[0])):
            inst = presented["inst"]
            lines.append(f"OPEN question {n}, on screen now (do not reveal its answer): {_clip(inst.get('stem', ''), 1500)}"
                         f"{_options(inst.get('options'))}{_source(inst)}")
        base = "\n".join(lines)
    else:
        base = context(tutor)
    return (f"{base}\n\nLESSON IDEA: {point.get('spec', '')} {kc}: {point.get('title', '')} — "
            f"{point.get('statement', '')}\nLearner history: {json.dumps(history, ensure_ascii=False)}\n"
            f"Lesson goal: {lesson.GOALS.get(session.get('goal'), 'Not chosen yet')}\n"
            f"Prerequisite history: {json.dumps(related, ensure_ascii=False)}\n"
            f"Available teaching material: {json.dumps(safe, ensure_ascii=False)}\n\n"
            "Address the learner directly. Use their earlier replies to tackle the specific obstacle, rather than "
            "repeating the whole card. When they are stuck, offer one manageable next step and one short guiding "
            "question. Explain what to notice in a useful diagram. For another example, choose a fresh situation "
            "instead of copying a future check. Conversation is assisted learning, never proof of mastery. "
            "Teach adaptively using the learner's history. If evidence conflicts, acknowledge uncertainty and ask a brief "
            "diagnostic question rather than assuming mastery. If the probe suggests understanding and no gap remains, "
            "invite an attempt first; if the idea is new or a gap remains, explain its foundations. "
            "Explain in short readable steps; offer more detail. "
            "Never disclose a solution to an open question. Ask the student to try before giving away an answer. "
            "Do not claim calculations or proof have been verified unless verification is supplied. "
            f"{MATH_RULE}\n"
            f"STUDENT ASKS: {question}")


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


def local_judge_schema(points: list[str]) -> dict:
    """Constrain local copies of mark-point text; the host still checks every row and its order."""
    from copy import deepcopy

    schema = deepcopy(JUDGE)
    array = schema["properties"]["points"]
    array["minItems"] = array["maxItems"] = len(points)
    array["items"]["properties"]["point"]["enum"] = list(dict.fromkeys(points))
    return schema


def judge(stem: str, points: list[str], answer: str, *, strictness: str = 'auto', mode: str = '') -> str:
    listed = "\n".join(f"{i}. {p}" for i, p in enumerate(points, 1))
    return (f"Mark this A-Level answer against the supplied mark points.\n{marking_instruction(strictness, mode)}\n\n"
            f"QUESTION: {stem}\nMARK POINTS:\n{listed}\nSTUDENT ANSWER: {answer}\n\n"
            "Return JSON: {\"points\": [{\"point\": <text>, \"met\": true|false, \"why\": <short>}], "
            "\"feedback\": <one or two sentences>}. Return exactly one row per mark point, in the given order, "
            "copying its text exactly (without the list number). Judge each point independently using only the "
            "student's actual answer or explicit working, under the marking policy above.")


PROFILE = {"type": "object", "properties": {"summary": {"type": "string"}}, "required": ["summary"]}


def profile_summary(findings_md: str) -> str:
    return ("Below is the learner profile the tutor has worked out from a student's own answers. Each finding says how "
            "sure it is: not enough data, early sign, likely or clear.\n\n" + findings_md[:6000] + "\n\n"
            "Return JSON with summary: at most 150 words of Markdown bullets ('- ' each), in British English, speaking "
            "to the student: what is going well; the one change most likely to gain them marks; up to three specific "
            "things to do this week. Use only these findings. Where the evidence is an early sign or less, say it is "
            "too early to be sure. Never mention learning styles.")


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
            f"know), note (3-5 terse revision bullets, '- ' each, exam wording), self_explain (one question asking them "
            f"to explain the idea in their own words). {MATH_RULE}")


def key_of(tutor, n: int) -> tuple[str, str, dict | None]:
    """An open question's answer as shown, its kind, and for a numeric one its answer (true value, s.f. rules)."""
    p = (tutor.session or {}).get("presented", {}).get(str(n))
    if not p:
        return "", "", None
    inst = p["inst"]
    return _display_answer(inst), inst["kind"], inst["answer"] if inst["kind"] == "numeric" else None


def skipped_guards(tutor) -> dict:
    """Include persisted skipped questions even outside the lesson that created them."""
    engine_guards = getattr(tutor, 'marking_guards', None)
    if callable(engine_guards):
        return engine_guards()
    guards = {}
    vault = getattr(tutor, 'vault', None)
    if vault is not None:
        from tutorlib import deferred_notes
        guards.update(deferred_notes.outstanding(vault.tutor / 'state' / 'deferred-notes.json'))
    guards.update((tutor.session or {}).get('skipped_answer_guards') or {})
    if (tutor.session or {}).get('suspended_for_retry'):
        guards['suspended-for-retry'] = {}  # keep model replies paused until all open questions resume
    return guards


def guard_keys(tutor) -> list[tuple[str, str, dict | None]]:
    """Protect open questions and skipped lesson answers without putting their keys in the prompt."""
    session = tutor.session or {}
    skipped = skipped_guards(tutor)
    keys = [key_of(tutor, int(n)) for n in session.get("presented", {})]
    keys.extend((v.get("key", ""), v.get("kind", ""), v.get("numeric"))
                for v in skipped.values() if isinstance(v, dict))
    keys.extend((answer, "short", None)
                for v in skipped.values() if isinstance(v, dict)
                for answer in v.get("short_answers", []) if isinstance(answer, str) and answer)
    # A short written answer may itself be a number, which the prose matcher cannot protect.
    keys.extend((answer.strip().strip("$"), "numeric", None)
                for v in skipped.values() if isinstance(v, dict)
                for answer in v.get("short_answers", [])[:1] if isinstance(answer, str)
                and re.fullmatch(r"\s*\$?[+-]?\d+(?:\.\d+)?\$?\s*", answer))
    return keys


def challenge_explain(item: dict, solution: str, key: str, response: str) -> str:
    """Why the answer to a challenge question is what it is (the question is marked: nothing to withhold)."""
    return (f"A student just answered this challenge question.\nQUESTION: {item.get('stem', '')}"
            f"{_options(item.get('options'))}\nANSWER: {key}\nWORKED SOLUTION: {solution}\nSTUDENT ANSWER: {response}\n\n"
            "Explain clearly how to solve it: the key idea that unlocks it, then the steps in short. If the student was "
            "wrong, say where their answer most likely went wrong. At most 150 words; maths in $...$. " + MATH_RULE)


REMARK = {"type": "object", "properties": {"correct": {"type": "boolean"}, "why": {"type": "string"}},
          "required": ["correct", "why"]}
REMARK_MODEL = "sonnet"  # a re-mark is rare, asked for, and has to be right: the stronger model whatever the setting


def remark(view: dict, fb: dict, *, strictness: str = 'auto', mode: str = '') -> str:
    """A second marker for an answer the program marked wrong: it matches units, forms and wording narrowly, and an
    answer key can itself be wrong."""
    choice = view.get("kind") == "mcq"
    given = str(fb.get("response"))
    if choice and (text := (view.get("options") or {}).get(given)):
        given = f"{given}: {text}"
    rule = ("Work the question out yourself before you look at the answer key. The key has been checked and is nearly "
            "always right: the student is right only if their option is the best answer and you can show where the "
            "key goes wrong." if choice else
            "The student is right if their answer is the same quantity, expression or meaning as the mark scheme's: "
            "the same value in another correct unit (1.5 kW for 1500 W), an equivalent algebraic form, the same idea in "
            "other words, or a correct rounding to a sensible number of figures. They are wrong if the value or meaning "
            "differs, a required unit is missing or wrong, or the figures break what the question asked.")
    return ("A marking program marked this A-Level answer wrong. Check its decision against the question and "
            f"supplied assessment evidence.\n{marking_instruction(strictness, mode)}\n\n"
            f"QUESTION: {view.get('stem', '')}{_options(view.get('options'))}\nMARK SCHEME ANSWER: {fb.get('answer')}\n"
            f"STUDENT ANSWER: {given}\n" + (f"THE PROGRAM'S REASON: {fb['detail']}\n" if fb.get("detail") else "") +
            f"\n{rule}\n"
            'Return JSON: {"correct": true|false, "why": <one or two sentences, speaking to the student>}.')
