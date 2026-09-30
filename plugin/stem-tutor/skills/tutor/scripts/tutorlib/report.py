"""Human-facing outputs written by code (zero model tokens): brief, Today, Profile, session notes, Almanac sync."""
from __future__ import annotations

import re
from collections import Counter
from datetime import date, datetime

from . import experiments, model, policy
from .packs import _fill
from .store import read_json, write_json

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
    now, s, p = tutor.now(), tutor.state, tutor.packs
    week = policy.current_week(p.plan, now)
    blocks = policy.plan_session(s, p, now, minutes)
    introduced = [k for k, v in s["kcs"].items() if v["n"] > 0]
    out = {
        "week": week,
        "due": len(model.due_kcs(s, now)),
        "retests": len(experiments.retests_due(s, now)),
        "gaps": len(s["gaps"]),
        "week_objectives": [f"{o['subject']}: {o['title']}" for o in p.plan.get("weeks", {}).get(str(week), [])][:5],
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
def _item_stem(tutor, item_id: str, params: dict | None) -> str:
    subtopic = item_id.rsplit("-i", 1)[0]
    if subtopic in tutor.packs.subtopics:
        for it in (tutor.packs.pack(subtopic) or {}).get("items", []):
            if it["id"] == item_id:
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
    correct = sum(1 for a in answers if a["grade"]["correct"])
    learned = sorted({k for a in answers if a.get("block") == "learn" for k in a["kcs"]})
    acc = f"{100 * correct / len(answers):.0f}%" if answers else "–"
    lines = ["---", "tags: [stem-tutor/session]", f"date: {ts.date()}", f"mode: {start['mode'] if start else '?'}",
             f"accuracy: {round(correct / len(answers), 2) if answers else 'null'}", "---",
             f"# Session {ts:%Y-%m-%d %H:%M} · {start['mode'] if start else ''}", "",
             "| Answered | Correct | Accuracy | KCs taught |", "|---|---|---|---|",
             f"| {len(answers)} | {correct} | {acc} | {', '.join(learned) or '–'} |", ""]
    for i, a in enumerate(answers, 1):
        g = a["grade"]
        kind = "success" if g["correct"] else "failure"
        tag = f" · {g['error']}" if g.get("error") else ""
        lines.append(f"> [!{kind}]- Q{i} · {', '.join(a['kcs'])} · {a.get('phase') or a.get('block')}{tag}")
        for l in to_note_math(_item_stem(tutor, a["item"], a.get("params"))).split("\n"):
            lines.append(f"> {l}")
        conf = CONF_WORD.get(a.get("conf"), "–")
        lines.append(f"> **Your answer:** {a.get('response', '–')} ({conf}) · score {g['score']}")
        lines.append("")
    rel = f"Sessions/{ts:%Y-%m-%d %H%M} {start['mode'] if start else 'session'}.md"
    return _write(tutor, rel, "\n".join(lines))


def today_note(tutor, minutes: int = 50) -> str:
    now, s, p = tutor.now(), tutor.state, tutor.packs
    week = policy.current_week(p.plan, now)
    blocks = policy.plan_session(s, p, now, minutes)
    lines = [f"# Today · {now:%a %d %b %Y} · Almanac week {week}", ""]
    ns = _next_sitting(p.plan, now)
    if ns:
        lines += [f"Next sitting: **{ns['label']}** in {ns['days']} days ({ns['date']}).", ""]
    lines += [f"## Suggested {minutes}-minute session", ""]
    for b in blocks:
        kcs = [b["kc"]] if "kc" in b else b.get("kcs", [])
        names = ", ".join(f"{k} {p.kc(k)['title']}" for k in kcs if k in p.kcs)
        lines.append(f"- **{b['kind'].capitalize()}**: {names}")
    lines += ["", "## This week's Almanac objectives", ""]
    for o in p.plan.get("weeks", {}).get(str(week), []):
        kcs = o.get("kcs", [])
        mastered = sum(model.is_mastered(s["kcs"][k]) for k in kcs if k in s["kcs"])
        mark = " ✅ evidence says done — tick it in the Almanac" if kcs and mastered == len(kcs) else ""
        lines.append(f"- {o['subject']} · {o['title']} ({mastered}/{len(kcs)} KCs mastered){mark}")
        if o.get("done"):
            lines.append(f"  - Done when: {o['done']}")
    missing = policy.missing_packs(p, now)
    if missing:
        lines += ["", f"Content not built yet for: {', '.join(missing)} (ask Claude Code to build the next batch)."]
    return _write(tutor, "Today.md", "\n".join(lines) + "\n")


def profile_note(tutor) -> str:
    from . import profile
    s, now = tutor.state, tutor.now()
    p = profile.summary(s, tutor.packs, now)
    pct = lambda x: f"{x:.0%}"  # noqa: E731
    L = ["# Your learner profile",
         f"_Updated {now:%d %b %Y %H:%M}. Worked out from your answers, compared with what was expected for each "
         "question. No 'learning styles': only what measurably helps you._", ""]
    tips = profile.advice(p)
    L += ["## What this means for you", ""] + ([f"- {x}" for x in tips] or
                                              ["- Not enough answers yet: patterns appear after a few sessions."])
    L += ["", "## How sure vs how right", ""]
    cal = p["calibration"]
    if cal["n"]:
        verdict = ("overconfident" if cal["bias"] > 0.1 else "underconfident" if cal["bias"] < -0.1 else "well calibrated")
        L += [f"{cal['n']} rated answers: you are **{verdict}**. Confidently-wrong answers so far: {cal['high_conf_errors']} "
              "(the best moments to fix an idea).", "", "| You said | Answers | Actually right | A perfect judge |",
              "|---|---|---|---|"]
        L += [f"| {lv['level']} | {lv['n']} | {pct(lv['right'])} | {pct(lv['said'])} |" for lv in cal["levels"]]
    else:
        L.append("No rated answers yet.")
    L += ["", "## When you learn best", ""]
    tod = [b for b in p["time_of_day"]["blocks"] if b["n"]]
    L += [f"- {b['block'].title()}: {b['n']} answers, {b['residual']:+.0%} vs expected" for b in tod] or ["- No data yet."]
    L += ["", "## Stamina in a session", ""]
    L += [f"- Questions {b['items']}: {b['n']} answers, {b['residual']:+.0%} vs expected" for b in p["stamina"]["buckets"]] \
        or ["- No data yet."]
    L += ["", "## Mistakes by kind", ""]
    L += [f"- {code.title()}: {n}" for code, n in p["errors"].items()] or ["- None recorded yet."]
    L += ["", "## Remembering over time", ""]
    L += [f"- {s}: {v['n']} spaced reviews; the memory model expected {pct(v['expected'])} recall and you got "
          f"{pct(v['actual'])}" for s, v in p["forgetting"].items()] or ["- Not enough spaced reviews yet."]
    L += ["", "## Pace and habits", ""]
    L += [f"- {s}: {m:.1f} min per mark (exam pace is about 1.2)" for s, m in p["pace"].items()]
    h = p["habits"]
    L += [f"- Studied on {h['last_28']} of the last 28 days; current streak {h['streak']} day(s).",
          f"- Reviews due over the next 7 days: {' · '.join(str(x) for x in p['workload'])}."]
    L += ["", "## Teaching experiments on you", ""]
    for e in p["experiments"]:
        pf = "–" if e["p_first_better"] is None else pct(e["p_first_better"])
        L.append(f"- **{e['name']}** ({e['subject']}): {e['arms'][0]} vs {e['arms'][1]}, {e['complete_pairs']}/"
                 f"{e['target_pairs']} pairs, chance the first is better {pf}, decision: {e['decision']}")
    if not p["experiments"]:
        L.append("- None yet. The first starts once enough topics of one kind are being taught.")
    kn = p["knobs"]
    L += ["", "## What the tutor has adjusted for you", ""]
    adj = [f"- {s}: reviews now aim for {r:.0%} recall, because your memory differs from the model's forecast."
           for s, r in kn["desired_retention"].items()]
    if kn["checking_routine"]:
        adj.append("- Careless slips cost you many marks, so answer boxes now show a quick checking routine.")
    if kn["confidence_training"]:
        adj.append("- Your confidence is often off, so feedback now shows how often you're right at that confidence.")
    if kn["attempt_before_hint"]:
        adj.append("- You ask for hints often, so a hint now asks you to have a go first.")
    if kn["max_items_before_break"]:
        adj.append(f"- Your accuracy dips after about {kn['max_items_before_break']} questions, so a break is suggested there.")
    L += adj or ["- Nothing yet: research-based defaults are in use."]
    return _write(tutor, "Profile.md", "\n".join(L) + "\n")


# ---------------- Almanac two-way sync ----------------
MATH_UNITS = {"WMA11": "P1", "WMA12": "P2", "WMA13": "P3", "WMA14": "P4", "WST01": "S1", "WST02": "S2",
              "WST03": "S3", "WME01": "M1", "WDM11": "D1", "WFM01": "FP1", "WFM02": "FP2", "WFM03": "FP3"}


def _almanac_score_key(paper: dict) -> str | None:
    """Almanac mark-bank keys: chem-P2, phys-P4, math-S1 (best recent full-paper-equivalent score)."""
    if paper["code"] in ("9701", "9702"):
        return f"{'chem' if paper['code'] == '9701' else 'phys'}-P{str(paper['component'])[0]}"
    unit = MATH_UNITS.get(paper["code"])
    return f"math-{unit}" if unit else None

def almanac_sync(tutor) -> dict:
    folder = tutor.vault.root / "Almanac"
    exports = sorted(folder.glob("almanac-progress-*.json")) if folder.exists() else []
    base = read_json(exports[-1]) if exports else {}
    base = base or {}
    totals: Counter = Counter()
    for subject, errs in tutor.state["traits"]["errors"].items():
        for code, n in errs.items():
            totals[_errfam(code, subject)] += n
    added = Counter((base.get("tutor_sync") or {}).get("err_added", {}))
    err = Counter(base.get("err", {}))
    for fam, n in totals.items():
        err[fam] += n - added.get(fam, 0)
    wall = dict(base.get("wall", {}))
    for e in tutor.vault.events():
        if e["type"] == "session_start":
            wall[datetime.fromisoformat(e["ts"]).date().isoformat()] = 1
    rag = dict(base.get("rag", {}))
    p = tutor.packs
    for topic in {k["subtopic"].rsplit(".", 1)[0] for k in p.kcs.values()}:
        spec, num = topic.split("-", 1)
        key = {"9701": "chem", "9702": "phys"}.get(spec)
        kcs = [k for k, m in p.kcs.items() if m["subtopic"].startswith(topic + ".")]
        seen = [tutor.state["kcs"][k] for k in kcs if tutor.state["kcs"].get(k, {}).get("n")]
        if key and seen and not rag.get(f"{key}-{num}") and len(seen) * 2 >= len(kcs):
            ratio = sum(model.is_mastered(k) for k in seen) / len(kcs)
            rag[f"{key}-{num}"] = "g" if ratio >= 0.8 else "a" if ratio > 0 else "r"
    scores = dict(base.get("scores", {}))
    results: dict[str, list[float]] = {}
    for e in tutor.vault.events():
        if e["type"] == "paper_result" and e.get("max"):
            paper = next((x for x in p.papers if x["id"] == e["paper"]), None)
            key = _almanac_score_key(paper) if paper else None
            if key:
                results.setdefault(key, []).append(round(e["score"] / e["max"] * paper["marks"]))
    for key, vals in results.items():
        scores[key] = max(vals[-3:])
    out = {**base, "err": {k: v for k, v in err.items() if v}, "wall": wall, "rag": rag, "scores": scores,
           "tutor_sync": {"err_added": dict(totals), "at": tutor.now().isoformat()}}
    rel = f"Almanac/almanac-import-{tutor.now():%Y-%m-%d}.json"
    write_json(tutor.vault.root / rel, out)
    tutor.log({"type": "almanac_sync", "path": rel, "base": exports[-1].name if exports else None})
    return {"path": rel, "base": exports[-1].name if exports else None,
            "say": "In the Almanac: Import → choose this file. Export your progress into this folder before the next sync."}
