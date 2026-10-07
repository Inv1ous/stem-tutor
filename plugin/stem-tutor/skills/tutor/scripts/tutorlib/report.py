"""Human-facing outputs written by code (zero model tokens): brief, Today, Profile, session notes, Almanac sync."""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path

from . import almanac, experiments, model, policy
from .packs import _fill
from .store import read_json, write_json
from .store import write_text as _write_text

ERRFAM = {"RECALL": "Could not recall", "MISREAD": "Misread the question", "CONCEPT": "Wrong method",
          "PROCEDURE": "Wrong method", "STRATEGY": "Wrong method", "NOTATION": "Careless arithmetic",
          "TIME": "Ran out of time"}
CONF_WORD = {1: "guess", 2: "unsure", 3: "fairly sure", 4: "certain"}


_SUP = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ⁿ", "0123456789+-=()n")
_SUB = str.maketrans("₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎ₐₑₒₓₕₖₗₘₙₚₛₜ", "0123456789+-=()aeoxhklmnpst")


def to_note_math(text: str) -> str:
    """Unicode super/subscripts (from mined papers) -> inline LaTeX, since note fonts may lack the glyphs."""
    parts = re.split(r"(\$[^$]*\$)", text)
    for i, part in enumerate(parts):
        if part.startswith("$"):
            continue
        part = re.sub(r"[⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ⁿ]+", lambda m: "$^{" + m.group(0).translate(_SUP) + "}$", part)
        parts[i] = re.sub(r"[₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎ₐₑₒₓₕₖₗₘₙₚₛₜ]+", lambda m: "$_{" + m.group(0).translate(_SUB) + "}$", part)
    return "".join(parts)


def _n(n: int, word: str) -> str:
    """"1 mistake", "2 mistakes"."""
    return f"{n} {word}{'' if n == 1 else 's'}"


def note_answer(text: str) -> str:
    """A right answer as the notes show maths: 7.46e10 -> 7.46 × 10^10, m s^-2 and m s⁻¹ -> superscripts."""
    parts = re.split(r"(\$[^$]*\$)", str(text))
    for i, part in enumerate(parts):
        if not part.startswith("$"):
            part = re.sub(r"\b(\d+(?:\.\d+)?)[eE]([+-]?\d+)\b",
                          lambda m: f"{m.group(1)} × 10$^{{{int(m.group(2))}}}$", part)
            parts[i] = re.sub(r"\^\(?([+-]?\d+)\)?", r"$^{\1}$", part)
    return to_note_math("".join(parts))


def question_sheet(tutor) -> str:
    """Mirror the open questions into Question Sheets/Current.md (Obsidian live-reloads it)."""
    s = tutor.session or {}
    lines = [f"# Current questions", f"_Updated {tutor.now():%H:%M}. Answer in the Cowork chat._", ""]
    for n in sorted(s.get("presented", {}), key=int):
        p = s["presented"][n]
        inst = p["inst"]
        flag = " · no hints" if p.get("unassisted") else ""
        src = f" · {inst['source']['ref']}" if inst.get("source", {}).get("type") == "past" else ""
        lines += [f"## Q{n}{flag}{src}", "", to_note_math(inst.get("stem", "")), ""]
        if inst.get("image"):
            lines += [f"![[{inst['image']}]]", ""]
        for k, v in (inst.get("options") or {}).items():
            lines.append(f"- **{k}** {to_note_math(v)}")
        lines.append("")
    if not s.get("presented"):
        lines.append("No open questions.")
    return _write(tutor, "Question Sheets/Current.md", "\n".join(lines) + "\n")


def _errfam(code: str, subject: str) -> str:
    if code == "SLIP":
        return "Algebra slip" if subject == "math" else "Careless arithmetic"
    return ERRFAM.get(code, "Wrong method")


def _write(tutor, rel: str, text: str) -> str:
    from .store import write_text
    write_text(tutor.vault.root / rel, text)
    return rel


def _next_sitting(plan: dict, now: datetime) -> dict | None:
    upcoming = sorted((date.fromisoformat(d), label) for label, d in plan.get("sittings", {}).items()
                      if date.fromisoformat(d) >= now.date())
    if not upcoming:
        return None
    d, label = upcoming[0]
    return {"label": label, "date": d.isoformat(), "days": (d - now.date()).days}


def _plan_summary(blocks: list[dict]) -> str:
    parts = []
    for b in blocks:
        kcs = [b["kc"]] if "kc" in b else b.get("kcs", [])
        parts.append(f"{b['kind']} {', '.join(kcs[:3])}{'…' if len(kcs) > 3 else ''}")
    return " → ".join(parts) or "nothing scheduled"


def brief(tutor, minutes: int = 50) -> dict:
    now, s, p, ticked = tutor.now(), tutor.state, tutor.packs, tutor.ticks()
    week = policy.current_week(p.plan, now)
    focus = policy.focus_week(p.plan, s, ticked, now)  # past the calendar week once everything in it is done
    blocks = policy.plan_session(s, p, now, minutes, ticked=ticked)
    introduced = [k for k, v in s["kcs"].items() if v["n"] > 0]
    out = {
        "week": week,
        "due": len(model.due_kcs(s, now)),
        "retests": len(experiments.retests_due(s, now)),
        "gaps": len(s["gaps"]),
        "week_objectives": [f"{o['subject']}: {o['title']}" for o in p.plan.get("weeks", {}).get(str(focus), [])
                            if not policy.is_done(o, s, ticked)][:5],
        "next_sitting": _next_sitting(p.plan, now),
        "mastered": sum(model.is_mastered(s["kcs"][k]) for k in introduced),
        "introduced": len(introduced),
        "experiments": [n for n, e in s["experiments"].items() if e["status"] == "running"],
        "unbuilt_subtopics_all_subjects": (lambda m: {"count": len(m), "next": m[:5],
                                                      "say": "Build backlog; unrelated to the current request. Mention only if asked."}
                                           if m else [])(policy.missing_packs(p, now)),
        "suggest": f"{minutes} min: {_plan_summary(blocks)}",
        "open_session": bool(tutor.session),
    }
    return {k: v for k, v in out.items() if v not in (None, [], 0) or k in ("week", "due")}


# ---------------- notes ----------------
def _pack_item(tutor, item_id: str) -> dict | None:
    """A question as published: its id is its subtopic plus -i01 (written), -p01 (past paper) or -x001 (extra)."""
    subtopic = item_id.rsplit("-", 1)[0]
    if subtopic not in tutor.packs.subtopics:  # a check inside a lesson, or a chapter no longer published
        return None
    return next((i for i in (tutor.packs.pack(subtopic) or {}).get("items", []) if i["id"] == item_id), None)


def _item_stem(tutor, item_id: str, params: dict | None) -> str:
    it = _pack_item(tutor, item_id)
    if it:
        env = dict(params or {})
        for name, expr in (it.get("template") or {}).get("derived", {}).items():
            from .packs import _eval
            env[name] = _eval(expr, env)
        return _fill(it["stem"], env) if env else it["stem"]
    return f"(item {item_id})"


def session_note(tutor, session_id: str) -> str:
    evs = [e for e in tutor.vault.events() if e.get("session") == session_id]
    start = next((e for e in evs if e["type"] == "session_start"), None)
    answers = [e for e in evs if e["type"] == "answer"]
    ts = datetime.fromisoformat(start["ts"] if start else tutor.now().isoformat())
    correct = sum(1 for a in answers if model.counts_as_right(a["grade"]))
    learned = sorted({k for a in answers if a.get("block") == "learn" for k in a["kcs"]})
    acc = f"{100 * correct / len(answers):.0f}%" if answers else "–"
    lines = ["---", "tags: [stem-tutor/session]", f"date: {ts.date()}", f"mode: {start['mode'] if start else '?'}",
             f"accuracy: {round(correct / len(answers), 2) if answers else 'null'}", "---",
             f"# Session {ts:%Y-%m-%d %H:%M} · {start['mode'] if start else ''}", "",
             "| Answered | Correct | Accuracy | KCs taught |", "|---|---|---|---|",
             f"| {len(answers)} | {correct} | {acc} | {', '.join(learned) or '–'} |", ""]
    for i, a in enumerate(answers, 1):
        g = a["grade"]
        kind = "success" if model.counts_as_right(g) else "failure"
        tag = f" · {g['error']}" if g.get("error") else ""
        lines.append(f"> [!{kind}]- Q{i} · {', '.join(a['kcs'])} · {a.get('phase') or a.get('block')}{tag}")
        for l in to_note_math(_item_stem(tutor, a["item"], a.get("params"))).split("\n"):
            lines.append(f"> {l}")
        conf = CONF_WORD.get(a.get("conf"), "–")
        lines.append(f"> **Your answer:** {a.get('response', '–')} ({conf}) · score {g['score']}")
        lines.append("")
    rel = f"Sessions/{ts:%Y-%m-%d %H%M} {start['mode'] if start else 'session'}.md"
    return _write(tutor, rel, "\n".join(lines))


TODAY_KCS = 4  # ideas named on one line of Today's plan; the rest are counted


def today_note(tutor, minutes: int = 50) -> str:
    now, s, p, ticked = tutor.now(), tutor.state, tutor.packs, tutor.ticks()
    week = policy.current_week(p.plan, now)
    focus = policy.focus_week(p.plan, s, ticked, now)
    blocks = policy.plan_session(s, p, now, minutes, ticked=ticked)
    lines = [f"# Today · {now:%a %d %b %Y} · Almanac week {week}", ""]
    ns = _next_sitting(p.plan, now)
    if ns:
        lines += [f"Next sitting: **{ns['label']}** in {ns['days']} days ({ns['date']}).", ""]
    lines += [f"## Suggested {minutes}-minute session", ""]
    for b in blocks:
        kcs = [b["kc"]] if "kc" in b else b.get("kcs", [])
        known = [k for k in kcs if k in p.kcs]
        names = ", ".join(f"{k} {p.kc(k)['title']}" for k in known[:TODAY_KCS])
        names += f" +{len(known) - TODAY_KCS} more" if len(known) > TODAY_KCS else ""
        lines.append(f"- **{'Check what you ticked' if b.get('claimed') else b['kind'].capitalize()}**: {names}")
    own = almanac.ticks(tutor.vault.root)  # the learner's own ticks; `ticked` also holds what they earned here
    lines += ["", "## This week's Almanac objectives" if focus == week else
              f"## Almanac week {focus}: you are ahead (the calendar is on week {week})", ""]
    for o in p.plan.get("weeks", {}).get(str(focus), []):
        kcs = o.get("kcs", [])
        mastered = sum(model.is_mastered(s["kcs"][k]) for k in kcs if k in s["kcs"])
        mark = (" ✅ ticked in your Almanac" if o.get("id") in own else
                " ✅ done: the tutor has ticked it in your Almanac" if policy.is_done(o, s, ticked) else "")
        lines.append(f"- {o['subject']} · {o['title']} ({mastered}/{len(kcs)} KCs mastered){mark}")
        if o.get("done"):
            lines.append(f"  - Done when: {o['done']}")
    missing = policy.missing_packs(p, now)
    if missing:
        lines += ["", f"Content not built yet for: {', '.join(missing)} (ask Claude Code to build the next batch)."]
    return _write(tutor, "Today.md", "\n".join(lines) + "\n")


SURE = {"not enough data": "⚪", "early sign": "🟡", "likely": "🟢", "clear": "✅"}


def load_ai_summary(tutor) -> dict | None:
    """The latest AI-written summary of the findings, if the learner asked for one: {"text", "at"}."""
    return read_json(tutor.vault.tutor / "profile_ai.json")


def _pct(x: float | None) -> str:
    return "–" if x is None else f"{x:.0%}"


def insights_markdown(tutor, ai: dict | None = None) -> str:
    """What the tutor knows about you: shared by Profile.md and the app's insights screen."""
    from . import insights
    f = insights.findings(tutor)
    r = f["recorded"]
    L = ["# What the tutor knows about you",
         f"_Updated {tutor.now():%d %b %Y %H:%M}. Counted from your own answers: nothing here is guessed by AI._", "",
         "## What the tutor has recorded", ""]
    if r["answers"]:
        L += [f"- **{r['answers']}** answer{'' if r['answers'] == 1 else 's'} in {_n(r['sessions'], 'session')} over "
              f"{_n(r['study_days'], 'study day')} ({r['first']} to {r['latest']}).",
              f"- {_n(r['confidence_ratings'], 'confidence rating')} · {_n(r['hinted'], 'answer')} with a hint · "
              f"{_n(r['mistakes_classified'], 'mistake')} sorted by kind · "
              f"{_n(r['misconceptions_spotted'], 'misconception')} spotted.",
              f"- {_n(r['blurts'], 'blurt')} · {_n(r['papers'], 'past paper')} marked."]
    else:
        L.append("- Nothing yet: every answer you give adds to this.")
    L += ["", "> [!info] How sure the tutor is",
          "> ⚪ **not enough data** · 🟡 **early sign**: some answers, not enough to act on · 🟢 **likely**: enough "
          "for the tutor to act on · ✅ **clear**: three times that much", "", "## What it has worked out", ""]
    for i in f["items"]:
        L += [f"### {i['headline']}", f"{SURE[i['certainty']]} _{i['area']} · {i['certainty']}"
              + (f", from {i['n']}_" if i["n"] else "_"), "", i["detail"]]
        L += ["", f"**What the tutor does about it:** {i['action']}", ""] if i["action"] else [""]
    L += ["## What the tutor has adjusted for you", ""]
    L += [f"- {a}" for a in f["adjustments"]] or ["- Nothing yet: research-based defaults are in use."]
    L += ["", "## Exam readiness", ""]
    rows = insights.readiness(tutor)
    later = [x for x in rows if x["days"] > READY_DAYS and not x["started"]]  # far off and not begun: one line
    rows = [x for x in rows if x not in later]
    if rows:
        L += ["| Exam | Date | Ideas | Built | Started | Secure | If you stopped now | If you keep reviewing |",
              "|---|---|---|---|---|---|---|---|"]
        L += [f"| {x['exam']} | {x['date']}{' (estimated)' if x['estimated'] else ''}, in {x['days']} days | "
              f"{x['ideas']} | {x['built']} | {x['started']} | {x['secure']} | {_pct(x['recall_if_stop'])} | "
              f"{_pct(x['recall_if_keep'])} |" for x in rows]
        L += ["", "The last two columns are predicted recall on the day for the ideas you have started: with no more "
              "reviews, and with your review schedule kept up. Ideas not built yet can't be started."]
    elif not later:
        L.append("- No upcoming exams in the plan.")
    if later:
        L += ["", f"Later, not started yet: {', '.join(x['exam'] for x in later)} (from {later[0]['date']})."]
    weak = insights.weak_spots(tutor)
    L += ["", "## Weak spots", ""]
    L += [f"- **{w['kc']} {w['title']}**: {'; '.join(w['reasons'])}" for w in weak[:12]] or ["- None right now."]
    if len(weak) > 12:
        L.append(f"- …and {len(weak) - 12} more.")
    if weak:
        L += ["", "**Fix my weak spots** in the tutor works through these, weakest first."]
    if ai:
        L += ["", "## AI summary", "", f"> [!quote] Written by the AI tutor on {ai['at'][:10]} from the findings above"]
        L += [f"> {x}" if x.strip() else ">" for x in ai["text"].strip().splitlines()]
    L += ["", "## What it never does", ""] + [f"- {x}" for x in f["never"]]
    return "\n".join(L) + "\n"


READY_DAYS = 365  # exams further off than this are listed in one line until you start on them


def profile_note(tutor) -> str:
    return _write(tutor, "Profile.md", insights_markdown(tutor, load_ai_summary(tutor)))


def _clip_math(text: str, n: int = 160) -> str:
    """First line, at most n characters, never cutting a $…$ formula in half."""
    lines = (text or "").strip().splitlines()
    line = lines[0] if lines else ""
    if len(line) <= n:
        return line + ("…" if len(lines) > 1 else "")
    cut = line[:n]
    if cut.count("$") % 2:
        cut = cut[:cut.rfind("$")]
    return cut.rstrip() + "…"


def _rebuilt_key(tutor, e: dict) -> str | None:
    """The right answer for an answer logged before keys were recorded, re-created from the pack."""
    from .packs import _eval
    from .session import _display_answer
    it = _pack_item(tutor, e["item"])
    if not it:
        return None
    inst, tpl = dict(it), it.get("template")
    if tpl and e.get("params"):
        env = dict(e["params"])
        for name, expr in tpl.get("derived", {}).items():
            env[name] = _eval(expr, env)
        if "answer" in tpl:
            inst["answer"] = {**it.get("answer", {}), "value": _eval(tpl["answer"], env)}
        if "options" in it:
            inst["options"] = {k: _fill(v, env) for k, v in it["options"].items()}
    if it["kind"] == "mcq" and it.get("shuffle") and it.get("source", {}).get("type") != "past":
        return (inst.get("options") or {}).get(inst["answer"], inst["answer"])  # letters were shuffled when shown
    try:
        return _display_answer(inst)
    except (KeyError, TypeError, ValueError):  # a template answer without its logged values
        return None


def mistakes_note(tutor) -> str:
    """Every question answered wrong or not known, by subtopic, newest first, with the right answer."""
    from . import insights
    answers = [e for e in tutor.vault.events() if e["type"] == "answer"]
    right_later: set[str] = set()
    groups: dict[str, list[list[str]]] = {}
    fixed = 0
    for e in reversed(answers):  # newest first, so "right since" means right after this mistake
        if model.counts_as_right(e["grade"]):
            right_later.add(e["item"])
            continue
        day, since = datetime.fromisoformat(e["ts"]).strftime("%d %b"), e["item"] in right_later
        fixed += since
        if ":" in e["item"]:
            paper, q = e["item"].split(":", 1)
            groups.setdefault("Past papers", []).append(
                [f"- **{day}** · {paper} Q{q}: {e['response']} marks" + (" · ✓ full marks since" if since else "")])
            continue
        g, kc = e["grade"], (e.get("kcs") or [""])[0]
        why = ("didn't know" if e.get("response") == "don't know"
               else f"misconception: “{insights._mis_text(tutor.packs, kc, g['misconception'])}”" if g.get("misconception")
               else insights.MISTAKES.get(g.get("error") or "", "wrong answer"))
        stem = e.get("stem") or _item_stem(tutor, e["item"], e.get("params"))
        key = e.get("key") or _rebuilt_key(tutor, e)
        you = str(e.get("response", "")).replace("`", "'")
        sub = tutor.packs.kc(kc)["subtopic"] if kc in tutor.packs.kcs else e["item"].rsplit("-", 1)[0]
        groups.setdefault(sub, []).append(
            [f"- **{day}** · {why}" + (" · ✓ right since" if since else ""),
             f"  - Question: {_clip_math(stem) if not stem.startswith('(item ') else 'not recorded'}",
             f"  - You: `{you}` · Right answer: {note_answer(key) if key else 'not recorded'}"])
    n = sum(len(v) for v in groups.values())
    L = ["# Mistake journal", "_Every question you got wrong or didn't know, newest first, with the right answer. "
         "Updated after each session._", "", f"{_n(n, 'mistake')} · {fixed} put right since." if n else "No mistakes yet."]
    for sub in sorted(groups, key=lambda x: (x == "Past papers", x)):
        title = tutor.packs.subtopics.get(sub, {}).get("title", "")
        L += ["", f"## {sub} {title}".rstrip(), ""] + [line for entry in groups[sub] for line in entry]
    return _write(tutor, "Mistakes.md", "\n".join(L) + "\n")


def week_note(tutor, monday: date) -> str:
    from . import insights
    r = insights.week_report(tutor, monday)
    L = [f"# Week in review · {r['week']}", f"_{monday:%a %d %b} to {monday + timedelta(days=6):%a %d %b %Y}_", "",
         f"- Studied on **{r['days']}** day{'s' if r['days'] != 1 else ''} · {r['answers']} answers · "
         f"{r['minutes']:g} minutes answering questions"]
    if r["right"] is not None:
        change = f" ({r['right_change']:+.0%} on the week before)" if r["right_change"] is not None else ""
        L.append(f"- Answers right: **{r['right']:.0%}**{change}")
    secured = [f"{k} {tutor.packs.kc(k)['title']}" for k in r["secured"] if k in tutor.packs.kcs]
    L += [f"- Ideas newly secure: {', '.join(secured) or 'none this week'}",
          f"- Misconceptions fixed: {'; '.join(r['fixed']) or 'none this week'}", "", "## What changed in your profile",
          ""] + ([f"- {c}" for c in r["changes"]] or ["- Nothing changed this week."])
    L += ["", "See also [[Profile]] (what the tutor knows about you) and [[Mistakes]] (your mistake journal)."]
    return _write(tutor, f"Weekly/{r['week']}.md", "\n".join(L) + "\n")


# ---------------- what the tutor gives the Almanac ----------------
MATH_UNITS = {"WMA11": "P1", "WMA12": "P2", "WMA13": "P3", "WMA14": "P4", "WST01": "S1", "WST02": "S2",
              "WST03": "S3", "WME01": "M1", "WDM11": "D1", "WFM01": "FP1", "WFM02": "FP2", "WFM03": "FP3"}
BANK = {"P1": 40, "P2": 60, "P3": 40, "P4": 100, "P5": 30}  # what the Almanac's mark bank scores each CAIE paper out of
STAGES_FROM = ("2026-11-01", "2027-01-01", "2027-02-22", "2027-03-22")  # when the Almanac's later paper stages begin
ADVICE = {"Algebra slip": "Write every line of algebra and check the signs before moving on.",
          "Misread the question": "Underline the command word and what is given before you start.",
          "Wrong method": "Name the principle or equation out loud before you calculate.",
          "Ran out of time": "Time yourself: about a minute a mark.",
          "Could not recall": "These ideas come back sooner in your reviews: do the reviews first each day.",
          "Careless arithmetic": "Redo the arithmetic once, then check units and significant figures."}
_PAST_MCQ = re.compile(r"^(9701|9702)-[\d.]+-[px]\d+$")


def _almanac_score_key(paper: dict) -> str | None:
    """Almanac mark-bank keys: chem-P2, phys-P4, math-S1."""
    if paper["code"] in ("9701", "9702"):
        return f"{'chem' if paper['code'] == '9701' else 'phys'}-P{str(paper['component'])[0]}"
    unit = MATH_UNITS.get(paper["code"])
    return f"math-{unit}" if unit else None


def _scores(tutor, events: list[dict]) -> dict[str, int]:
    """The mark bank: the best of the last three marked papers of each kind, on the bank's own scale. With no marked
    Paper 1 yet, a Paper 1 equivalent: the last 40 past-paper multiple-choice questions answered without help."""
    results: dict[str, list[float]] = {}
    for e in events:
        if e["type"] == "paper_result" and e.get("max"):
            paper = next((x for x in tutor.packs.papers if x["id"] == e["paper"]), None)
            key = _almanac_score_key(paper) if paper else None
            if key:
                results.setdefault(key, []).append(round(e["score"] / e["max"] * BANK.get(key.split("-")[1], 75)))
    scores = {key: int(max(vals[-3:])) for key, vals in results.items()}
    for subject in ("chem", "phys"):
        past = [e for e in events if e["type"] == "answer" and e.get("subject") == subject and not e.get("hinted")
                and _PAST_MCQ.match(str(e.get("item")))][-40:]
        if len(past) == 40 and f"{subject}-P1" not in scores:
            scores[f"{subject}-P1"] = sum(model.counts_as_right(e["grade"]) for e in past)
    return scores


def _retro(tutor, events: list[dict], week: int) -> dict | None:
    """The Almanac's weekly retrospective, from that week's answers: what broke, and the fix."""
    plan = tutor.packs.plan
    monday2 = date.fromisoformat(plan.get("week2_monday", "2026-09-07"))
    start = date.fromisoformat(plan.get("start", "2026-09-01")) if week <= 1 else monday2 + timedelta(days=7 * (week - 2))
    end = monday2 if week <= 1 else start + timedelta(days=7)
    answers = [e for e in events if e["type"] == "answer" and start.isoformat() <= e["ts"][:10] < end.isoformat()]
    if not answers:
        return None
    right = sum(model.counts_as_right(e["grade"]) for e in answers)
    kinds = Counter(_errfam(e["grade"]["error"], e.get("subject") or "") for e in answers if e["grade"].get("error"))
    missed = Counter(k for e in answers if not model.counts_as_right(e["grade"]) for k in e["kcs"])
    weakest = [f"{tutor.packs.kc(k)['title']} ({n})" for k, n in missed.most_common(3) if k in tutor.packs.kcs]
    gaps = [tutor.packs.kc(k)["title"] for k in tutor.state["gaps"] if k in tutor.packs.kcs][:3]
    broke = (f"{len(answers)} answers on {len({e['ts'][:10] for e in answers})} days, {right / len(answers):.0%} right."
             + (" Most misses: " + ", ".join(f"{k} ×{n}" for k, n in kinds.most_common(3)) + "." if kinds else "")
             + (" Weakest: " + "; ".join(weakest) + "." if weakest else ""))
    fix = " ".join(x for x in ("Re-teach first: " + "; ".join(gaps) + "." if gaps else "",
                               ADVICE.get(kinds.most_common(1)[0][0], "") if kinds else "") if x)
    return {"broke": broke, "fix": fix or "Nothing stood out: keep the reviews up."}


def almanac_payload(tutor) -> dict:
    """Everything the tutor can fill in for the Almanac: the objectives it has seen finished, a colour for every
    syllabus topic, mark-bank scores, the days studied, mistakes by family, the retrospective for this week and the
    last, and the paper stage the calendar has reached. The stamp changes only when one of them does."""
    s, p, now = tutor.state, tutor.packs, tutor.now()
    events = list(tutor.vault.events())
    err: Counter = Counter()
    for subject, errs in s["traits"]["errors"].items():
        for code, n in errs.items():
            err[_errfam(code, subject)] += n
    week = policy.current_week(p.plan, now)
    body = {"done": {i: 1 for i in sorted(policy.earned(p.plan, s, p))},
            "rag": policy.rag(s, p, policy.claimed(p.plan, almanac.ticks(tutor.vault.root))),
            "scores": _scores(tutor, events),
            "wall": {day: 1 for day in sorted({e["ts"][:10] for e in events if e["type"] == "answer"})},
            "err": {k: v for k, v in sorted(err.items()) if v > 0},
            "retro": {str(w): r for w in (week - 1, week) if w >= 1 and (r := _retro(tutor, events, w))},
            "stage": sum(now.date().isoformat() >= day for day in STAGES_FROM)}
    stamp = hashlib.sha1(json.dumps(body, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:12]
    return {"stamp": stamp, "at": now.isoformat(timespec="minutes"), **body}


def almanac_push(tutor) -> str | None:
    """Write what the tutor knows where the Almanac page picks it up: `<planner>.tutor.js` beside the planner file.
    The page merges it when it opens and every half minute after (build/almanac_link.py puts that into the page).
    Nothing is written when the planner is not on this machine."""
    src = tutor.packs.plan.get("source_path")
    if not src or not Path(src).is_file():
        return None
    target = Path(src).with_suffix(".tutor.js")
    _write_text(target, "window.TUTOR_SYNC = " + json.dumps(almanac_payload(tutor), ensure_ascii=False, indent=1) + ";\n")
    return str(target)
