"""Human-facing outputs written by code (zero model tokens): brief, Today, Profile, session notes, Almanac sync."""
from __future__ import annotations

from collections import Counter
from datetime import date, datetime

from . import experiments, model, policy
from .packs import _fill
from .store import read_json, write_json

ERRFAM = {"RECALL": "Could not recall", "MISREAD": "Misread the question", "CONCEPT": "Wrong method",
          "PROCEDURE": "Wrong method", "STRATEGY": "Wrong method", "NOTATION": "Careless arithmetic",
          "TIME": "Ran out of time"}
CONF_WORD = {1: "guess", 2: "unsure", 3: "fairly sure", 4: "certain"}


def _errfam(code: str, subject: str) -> str:
    if code == "SLIP":
        return "Algebra slip" if subject == "math" else "Careless arithmetic"
    return ERRFAM.get(code, "Wrong method")


def _write(tutor, rel: str, text: str) -> str:
    path = tutor.vault.root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
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
        "missing_packs": policy.missing_packs(p, now),
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
        for l in _item_stem(tutor, a["item"], a.get("params")).split("\n"):
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
    s, p, now = tutor.state, tutor.packs, tutor.now()
    t, kn, cal = s["traits"], model.knobs(s), model.calibration(s)
    lines = ["# Learner profile", f"_Updated {now:%Y-%m-%d %H:%M}. Measures what works for you from outcomes, never 'learning styles'._", ""]
    lines += ["## Mastery", "", "| Spec | Introduced | Mastered | Mean θ |", "|---|---|---|---|"]
    by_spec: dict[str, list] = {}
    for kc, k in s["kcs"].items():
        if k["n"] and kc in p.kcs:
            by_spec.setdefault(p.kc(kc)["spec"], []).append(k)
    for spec, ks in sorted(by_spec.items()):
        lines.append(f"| {spec} | {len(ks)} | {sum(model.is_mastered(k) for k in ks)} | {sum(k['theta'] for k in ks) / len(ks):+.2f} |")
    lines += ["", "## Calibration", ""]
    if cal["n"]:
        verdict = "overconfident" if cal["bias"] > 0.1 else "underconfident" if cal["bias"] < -0.1 else "well calibrated"
        lines += [f"- {cal['n']} rated answers; you are **{verdict}** (confidence minus accuracy = {cal['bias']:+.2f}).",
                  f"- Brier score {cal['brier']:.3f} (0 is perfect, 0.25 is coin-flip).",
                  f"- Confident-but-wrong answers: {cal['high_conf_errors']} (each one is a prime fixing opportunity)."]
    else:
        lines.append("- No rated answers yet.")
    lines += ["", "## Error families", "", "| Subject | Code | Almanac family | Count |", "|---|---|---|---|"]
    for subject, errs in sorted(t["errors"].items()):
        for code, n in sorted(errs.items(), key=lambda x: -x[1]):
            if n:
                lines.append(f"| {subject} | {code} | {_errfam(code, subject)} | {n} |")
    lines += ["", "## Forgetting", ""]
    for subject, (n, pred, out) in sorted(t["retention"].items()):
        lines.append(f"- {subject}: {n} spaced reviews; model expected {pred / n:.0%} recall, you got {out / n:.0%}.")
    if not t["retention"]:
        lines.append("- Not enough spaced reviews yet.")
    lines += ["", "## Pace and stamina", ""]
    for subject, (sec, marks) in sorted(t["time"].items()):
        lines.append(f"- {subject}: {sec / marks / 60:.1f} min per mark (exam pace is about 1.2 min per mark).")
    for b, (n, c) in sorted(t["fatigue"].items(), key=lambda x: int(x[0])):
        lines.append(f"- Items {int(b) * 5 + 1}–{int(b) * 5 + 5} of a session: {c}/{n} correct.")
    lines += ["", "## Experiments", ""]
    for name, exp in s["experiments"].items():
        r = experiments.analyze(exp)
        pf = "–" if r["p_first_better"] is None else f"{r['p_first_better']:.0%}"
        lines.append(f"- **{name}** ({exp['subject']}): {r['arms'][0]} vs {r['arms'][1]} · "
                     f"{r['complete_pairs']}/{r['target_pairs']} pairs · P({r['arms'][0]} better) {pf} · decision: {r['decision']}")
    if not s["experiments"]:
        lines.append("- None running yet. The first starts once enough topics of one type are being taught.")
    lines += ["", "## What the tutor adjusted", ""]
    adj = []
    for subject, r in kn["desired_retention"].items():
        adj.append(f"- {subject}: review target retention set to {r:.0%} because your recall differs from the model's forecast.")
    if kn["checking_routine"]:
        adj.append("- Slips are a big share of lost marks, so answers now end with a 20-second checking routine.")
    if kn["confidence_training"]:
        adj.append("- Your confidence ratings are off, so feedback now shows your confidence next to the result.")
    if kn["attempt_before_hint"]:
        adj.append("- You ask for hints often, so every hint now requires a first attempt.")
    if kn["max_items_before_break"]:
        adj.append(f"- Accuracy drops after about {kn['max_items_before_break']} items, so sessions insert a break there.")
    lines += adj or ["- Nothing yet: defaults from the research evidence are in use."]
    return _write(tutor, "Profile.md", "\n".join(lines) + "\n")


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
