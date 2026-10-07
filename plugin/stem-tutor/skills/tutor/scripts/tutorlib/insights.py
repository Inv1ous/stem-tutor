"""What the tutor has worked out about you, with the evidence, how sure it is, and what it changed (no AI).

Also exam readiness, weak spots and the week report. Everything is counted from the event log and the learner state.
Certainty labels follow the engine's own thresholds for acting, so a label never claims more than the tutor acts on.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta

from . import model, policy, profile

SUBJECTS = {"phys": "Physics", "chem": "Chemistry", "math": "Maths"}
MISTAKES = {"SLIP": "careless slips", "MISREAD": "misreading the question", "RECALL": "not remembering",
            "CONCEPT": "misunderstood ideas", "PROCEDURE": "method errors", "NOTATION": "units and significant figures"}
METHODS = {"worked_faded": "worked examples with the steps faded out",
           "problem_first": "a problem before the explanation",
           "pretest_explain": "a quick question before the explanation",
           "refutation": "tackling the misconception head-on"}
GAP = "a gap found by a blurt, test prep or a check"
NEVER = [
    "It doesn't sort you into a 'learning style': research finds no benefit from matching teaching to one.",
    "It doesn't ask an AI to guess things about you: every finding here is counted from your own answers.",
    "It doesn't act on one bad day: a finding needs enough answers before anything changes, and the labels say how "
    "sure it is.",
    "Nothing here leaves your Mac unless you ask the AI to explain your profile, which sends only these findings.",
]


def certainty(n: int, threshold: int) -> str:
    """Nothing yet, below the point where the tutor acts, at or above it, or at least three times it."""
    if n <= 0:
        return "not enough data"
    return "early sign" if n < threshold else "likely" if n < 3 * threshold else "clear"


def _subject(s: str) -> str:
    return SUBJECTS.get(s, s)


def _item(area: str, headline: str, detail: str, n: int, sure: str, action: str | None = None) -> dict:
    return {"area": area, "headline": headline, "detail": detail, "certainty": sure, "n": n, "action": action}


def _mis_text(packs, kc: str, mid: str) -> str:
    m = packs.misconception(packs.kc(kc)["subtopic"], mid) if kc in packs.kcs else None
    return m["statement"] if m else mid


def _method(m: str) -> str:
    return METHODS.get(m, m.replace("_", " "))


# ---------------- findings ----------------
def _memory(prof: dict, kn: dict) -> list[dict]:
    rows = []
    for s, v in sorted(prof["forgetting"].items()):
        n, exp, act = v["n"], v["expected"], v["actual"]
        how = "better than" if act > exp + 0.03 else "less well than" if act < exp - 0.03 else "about as well as"
        target = kn["desired_retention"].get(s)
        action = (f"{_subject(s)} reviews aim for {target:.0%} recall instead of 90%, so they come "
                  f"{'less' if target < 0.9 else 'more'} often." if target and target != 0.9 else None)
        rows.append(_item(f"Memory · {_subject(s)}", f"You remember {_subject(s)} {how} the memory model predicted",
                          f"On {n} spaced reviews it expected {exp:.0%} recall and you got {act:.0%}.", n,
                          certainty(n, 10), action))
    return rows or [_item("Memory", "How well you remember", "No spaced reviews yet. Until 10 are done in a subject, "
                          "reviews use the research default: due when recall is expected to fall to 90%.", 0,
                          "not enough data")]


def _confidence(prof: dict, kn: dict) -> dict:
    cal = prof["calibration"]
    if not cal["n"]:
        return _item("Confidence", "How sure vs how right", "No confidence ratings yet: after each answer, say how "
                     "sure you are (1–4) and this fills in.", 0, "not enough data")
    bias = cal["bias"] or 0.0
    head = ("You are often more sure than right" if bias > 0.1 else "You know more than you think" if bias < -0.1
            else "Your confidence matches how often you are right")
    levels = "; ".join(f"'{lv['level']}': right {lv['right']:.0%} of {lv['n']}" for lv in cal["levels"])
    detail = f"{levels}. Confidently wrong answers: {cal['high_conf_errors']} (the best moments to fix an idea)."
    action = ("After each answer, the feedback shows how often you are right at that confidence."
              if kn["confidence_training"] else None)
    return _item("Confidence", head, detail, cal["n"], certainty(cal["n"], 30), action)


def _mistakes(prof: dict, kn: dict) -> dict:
    errs = prof["errors"]
    total = sum(errs.values())
    if not total:
        return _item("Mistakes", "What costs you marks", "No mistakes classified yet.", 0, "not enough data")
    top = next(iter(errs))
    shares = ", ".join(f"{MISTAKES.get(c, c.lower())} {v / total:.0%}" for c, v in errs.items())
    return _item("Mistakes", f"Most marks are lost to {MISTAKES.get(top, top.lower())}",
                 f"Of {total} classified mistakes: {shares}.", total, certainty(total, 8),
                 "Answer boxes show a quick checking routine." if kn["checking_routine"] else None)


def _misconceptions(state: dict, packs) -> dict:
    active, fixed, seen = [], [], 0
    for kc, k in sorted(state["kcs"].items()):
        for mid, count in k.get("mis_counts", {}).items():
            seen += count
            text = f"“{_mis_text(packs, kc, mid)}” ({count}×)"
            (active if mid in k["active_misconceptions"] else fixed).append(text)
    if not seen:
        return _item("Misconceptions", "Wrong ideas the tutor has spotted", "None spotted yet: some wrong options in "
                     "questions are there to reveal a specific misconception.", 0, "not enough data")
    detail = " ".join(x for x in (f"Still active: {'; '.join(active)}." if active else "",
                                  f"Fixed: {'; '.join(fixed)}." if fixed else "") if x)
    action = ("When these ideas come up, the tutor tackles the misconception head-on (why it fails, then a contrasting "
              "case); two right answers in a row clear it." if active else None)
    head = (f"{len(active)} misconception{'s' if len(active) != 1 else ''} still active"
            + (f", {len(fixed)} fixed" if fixed else "") if active else
            f"{len(fixed)} misconception{'s' if len(fixed) != 1 else ''} fixed, none still active")
    return _item("Misconceptions", head, detail, seen, certainty(seen, 1),
                 action)


def _time_of_day(prof: dict) -> dict:
    used = [b for b in prof["time_of_day"]["blocks"] if b["n"]]
    if not used:
        return _item("Time of day", "When you learn best", "No answers yet.", 0, "not enough data")
    detail = "; ".join(f"{b['block']}: {b['n']} answers, {b['residual']:+.0%} vs expected" for b in used) + "."
    counts = sorted((b["n"] for b in used), reverse=True)
    best = prof["time_of_day"]["best"]
    return _item("Time of day", f"You do best in the {best}" if best else "No clear best time of day yet", detail,
                 counts[1] if len(counts) > 1 else 0,
                 certainty(counts[1], profile.MIN) if len(counts) > 1 else "early sign")


def _stamina(prof: dict) -> dict:
    buckets, k = prof["stamina"]["buckets"], prof["stamina"]["break_after"]
    if not buckets:
        return _item("Stamina", "Focus during a session", "No answers yet.", 0, "not enough data")
    detail = "; ".join(f"questions {b['items']}: {b['n']} answers, {b['residual']:+.0%} vs expected" for b in buckets)
    return _item("Stamina", f"Your accuracy dips after about {k} questions" if k else "No drop in accuracy during a "
                 "session so far", detail + ".", buckets[0]["n"], certainty(buckets[0]["n"], 10),
                 f"A short break is suggested after {k} questions." if k else None)


def _pace(prof: dict, state: dict) -> list[dict]:
    rows = []
    for s, m in sorted(prof["pace"].items()):
        marks = state["traits"]["time"][s][1]
        rows.append(_item(f"Pace · {_subject(s)}", f"{_subject(s)}: {m:.1f} minutes per mark",
                          f"Over {marks} marks of questions. Exam pace is about 1.2 minutes per mark; while you are "
                          "learning, slower is normal.", marks, certainty(marks, 20)))
    return rows or [_item("Pace", "How long you take", "No timed answers yet.", 0, "not enough data")]


def _hints(prof: dict, state: dict, kn: dict) -> dict:
    h = state["traits"]["hints"]
    if not h["n"]:
        return _item("Hints", "How often you use hints", "No answers yet.", 0, "not enough data")
    return _item("Hints", f"You used a hint on {prof['habits']['hints_rate']:.0%} of answers",
                 f"{h['hinted']} of {h['n']} answers.", h["n"], certainty(h["n"], 20),
                 "A hint now asks you to have a go first." if kn["attempt_before_hint"] else None)


def _methods(prof: dict) -> list[dict]:
    rows = []
    for e in prof["experiments"]:
        a, b = e["arms"]
        subj, done, target = _subject(e["subject"]), e["complete_pairs"], e["target_pairs"]
        detail = (f"Ideas are paired, one taught each way, then compared on later questions: {done} of {target} pairs "
                  "done" + (f"; so far the chance that {_method(a)} works better is {e['p_first_better']:.0%}"
                            if e["p_first_better"] is not None else "") + ".")
        if e["decision"] in (a, b):
            rows.append(_item(f"Teaching · {subj}", f"{subj}: {_method(e['decision'])} works better for you", detail,
                              done, "clear", f"{subj} lessons now use {_method(e['decision'])} for this kind of idea."))
        elif e["decision"] == "no_difference":
            rows.append(_item(f"Teaching · {subj}", f"{subj}: no real difference between the two ways", detail, done,
                              "clear"))
        else:
            rows.append(_item(f"Teaching · {subj}", f"{subj}: testing {_method(a)} against {_method(b)}", detail, done,
                              certainty(done, target)))
    return rows or [_item("Teaching", "Which way of teaching works for you", "No experiment yet: the first starts "
                          "once 5 ideas of one subject have been taught.", 0, "not enough data")]


def _topics(packs, answers: list[dict]) -> dict:
    per: dict[str, list[int]] = {}
    for e in answers:
        for kc in e["kcs"]:
            if kc in packs.kcs:
                v = per.setdefault(packs.kc(kc)["subtopic"], [0, 0])
                v[0] += 1
                v[1] += model.counts_as_right(e["grade"])
    if not per:
        return _item("Topics", "Strongest and weakest topics", "No answers yet.", 0, "not enough data")
    rated = sorted(((r / n, n, sub) for sub, (n, r) in per.items() if n >= 5), reverse=True)
    if len(rated) < 2:
        return _item("Topics", "Strongest and weakest topics", "Needs 5 answers in each of two subtopics to compare.",
                     sum(v[0] for v in per.values()), "early sign")
    name = lambda s: f"{s} {packs.subtopics[s]['title']}" if s in packs.subtopics else s  # noqa: E731
    (ra, na, sa), (rb, nb, sb) = rated[0], rated[-1]
    return _item("Topics", f"Strongest: {name(sa)}; weakest: {name(sb)}",
                 f"{name(sa)}: right {ra:.0%} of {na}. {name(sb)}: right {rb:.0%} of {nb}.", min(na, nb),
                 certainty(min(na, nb), 10))


def _habits(prof: dict, state: dict) -> dict:
    days = len(state.get("study_days", []))
    if not days:
        return _item("Habits", "How regularly you study", "No study days yet.", 0, "not enough data")
    h = prof["habits"]
    return _item("Habits", f"Studied on {h['last_28']} of the last 28 days", f"Current streak: {h['streak']} day{'s' if h['streak'] != 1 else ''}. "
                 "Short sessions on most days beat long ones now and then (spacing).", days, certainty(days, 7))


def _recorded(state: dict, evs: list[dict]) -> dict:
    answers = [e for e in evs if e["type"] == "answer"]
    days = sorted(e["ts"][:10] for e in answers)
    return {"answers": len(answers), "sessions": sum(e["type"] == "session_start" for e in evs),
            "study_days": len(state.get("study_days", [])),
            "confidence_ratings": sum(e.get("conf") is not None for e in answers),
            "hinted": sum(bool(e.get("hinted")) for e in answers),
            "mistakes_classified": sum(bool(e["grade"].get("error")) for e in answers),
            "misconceptions_spotted": sum(bool(e["grade"].get("misconception")) for e in answers),
            "blurts": sum(e["type"] == "blurt" for e in evs), "papers": sum(e["type"] == "paper_result" for e in evs),
            "first": days[0] if days else None, "latest": days[-1] if days else None}


def findings(tutor) -> dict:
    s, p = tutor.state, tutor.packs
    prof = profile.summary(s, p, tutor.now())
    kn = prof["knobs"]
    evs = list(tutor.vault.events())
    items = (_memory(prof, kn) + [_confidence(prof, kn), _mistakes(prof, kn), _misconceptions(s, p), _time_of_day(prof),
                                  _stamina(prof)] + _pace(prof, s) + [_hints(prof, s, kn)] + _methods(prof)
             + [_topics(p, [e for e in evs if e["type"] == "answer"]), _habits(prof, s)])
    return {"recorded": _recorded(s, evs), "items": items, "adjustments": [i["action"] for i in items if i["action"]],
            "never": NEVER}


# ---------------- exam readiness ----------------
def _exam_label(packs, spec: str, d: date) -> tuple[str, bool]:
    plan = packs.plan or {}
    for label, when in (plan.get("sittings") or {}).items():
        if label.split(" ")[0] == spec and when == d.isoformat():
            return label, False
    for paper in plan.get("papers") or []:
        if paper.get("short") == spec and paper.get("date") == d.isoformat():
            return f"{spec} ({paper['code'].split('/')[0]})", False
    if spec.isdigit():
        subject = next((k.get("subject", "") for k in packs.kcs.values() if k["spec"] == spec), "")
        return f"{spec} {_subject(subject)} {'AS' if d == policy.AS_2027 else 'A Level'}", True
    return spec, True


def readiness(tutor) -> list[dict]:
    """Per upcoming exam: how much of its syllabus is built, started and secure, and predicted recall on the day."""
    s, p, now = tutor.state, tutor.packs, tutor.now()
    groups: dict[tuple[str, date], list[str]] = {}
    for kc, meta in p.kcs.items():
        groups.setdefault((meta["spec"], policy.exam_date(p, kc)), []).append(kc)
    rows = []
    for (spec, d), kcs in groups.items():
        if d < now.date():
            continue
        label, estimated = _exam_label(p, spec, d)
        started = [k for k in kcs if s["kcs"].get(k, {}).get("n")]
        at = datetime.combine(d, time(9), tzinfo=now.tzinfo)
        stop = [r for r in (model.retrievability(s["kcs"][k], at) for k in started) if r is not None]
        keep = [policy.target_retention(s, p, k, at) for k in started]
        rows.append({"exam": label, "date": d.isoformat(), "estimated": estimated, "days": (d - now.date()).days,
                     "ideas": len(kcs), "built": sum(1 for k in kcs if p.items_for(k)), "started": len(started),
                     "secure": sum(model.is_mastered(s["kcs"][k]) for k in started),
                     "recall_if_stop": sum(stop) / len(stop) if stop else None,
                     "recall_if_keep": sum(keep) / len(keep) if keep else None})
    return sorted(rows, key=lambda r: (r["date"], r["exam"]))


# ---------------- weak spots ----------------
def _accuracy(tutor) -> dict[str, list[int]]:
    acc: dict[str, list[int]] = {}
    for e in tutor.vault.events():
        if e["type"] == "answer":
            for kc in e["kcs"]:
                v = acc.setdefault(kc, [0, 0])
                v[0] += 1
                v[1] += model.counts_as_right(e["grade"])
    return acc


def weak_spots(tutor) -> list[dict]:
    """Ideas with questions that are weak, with why: active misconception, then gap, then low accuracy."""
    s, p = tutor.state, tutor.packs
    acc = _accuracy(tutor)
    reasons: dict[str, tuple[int, list[str]]] = {}  # rank: 0 misconception, 1 gap, 2 low accuracy
    for kc in dict.fromkeys(list(s["kcs"]) + list(s["gaps"])):
        if kc not in p.kcs or not p.items_for(kc):
            continue
        k = s["kcs"].get(kc, {})
        why = [f"misconception: “{_mis_text(p, kc, m)}”" for m in k.get("active_misconceptions", [])]
        if kc in s["gaps"]:
            why.append(GAP)
        n, right = acc.get(kc, (0, 0))
        if n >= 3 and right / n < 0.5:
            why.append(f"right {right} of {n} times")
        if why:
            reasons[kc] = (0 if k.get("active_misconceptions") else 1 if kc in s["gaps"] else 2, why)
    order = sorted(reasons, key=lambda kc: (reasons[kc][0], policy.exam_date(p, kc), kc))
    return [{"kc": kc, "title": p.kc(kc)["title"], "subtopic": p.kc(kc)["subtopic"], "reasons": reasons[kc][1]}
            for kc in order]


# ---------------- week report ----------------
def state_at(tutor, when: datetime) -> dict:
    """The learner state as it was just before `when` (the event log replayed up to it)."""
    s = model.new_state()
    for e in tutor.vault.events():
        if datetime.fromisoformat(e["ts"]) < when:
            model.apply(s, e)
    return s


def _knob_changes(before: dict, after: dict) -> list[str]:
    out = []
    for subj in sorted(set(before["desired_retention"]) | set(after["desired_retention"])):
        a, b = before["desired_retention"].get(subj, 0.9), after["desired_retention"].get(subj, 0.9)
        if a != b:
            out.append(f"{_subject(subj)} reviews now aim for {b:.0%} recall (was {a:.0%}).")
    for key, what in (("checking_routine", "the checking routine"), ("confidence_training", "confidence feedback"),
                      ("attempt_before_hint", "have-a-go-before-a-hint")):
        if before[key] != after[key]:
            out.append(f"{what[0].upper()}{what[1:]} switched {'on' if after[key] else 'off'}.")
    if before["max_items_before_break"] != after["max_items_before_break"]:
        k = after["max_items_before_break"]
        out.append(f"A break is now suggested after {k} questions." if k else "No break point any more.")
    return out


def week_report(tutor, monday: date) -> dict:
    tz = tutor.now().tzinfo
    start = datetime.combine(monday, time(0), tzinfo=tz)
    end, before = start + timedelta(days=7), start - timedelta(days=7)
    evs = list(tutor.vault.events())
    within = lambda a, b: [e for e in evs if a <= datetime.fromisoformat(e["ts"]) < b]  # noqa: E731
    week, prev = within(start, end), within(before, start)
    answers, earlier = [e for e in week if e["type"] == "answer"], [e for e in prev if e["type"] == "answer"]
    rate = lambda es: sum(model.counts_as_right(e["grade"]) for e in es) / len(es) if es else None  # noqa: E731
    s0, s1 = state_at(tutor, start), state_at(tutor, end)
    secured = sorted(k for k, v in s1["kcs"].items()
                     if model.is_mastered(v) and not (k in s0["kcs"] and model.is_mastered(s0["kcs"][k])))
    raised = {(kc, e["grade"]["misconception"]) for e in answers if e["grade"].get("misconception") for kc in e["kcs"]}
    was = {(kc, m) for kc, v in s0["kcs"].items() for m in v["active_misconceptions"]} | raised
    still = {(kc, m) for kc, v in s1["kcs"].items() for m in v["active_misconceptions"]}
    changes = _knob_changes(model.knobs(s0), model.knobs(s1))
    for e in week:
        if e["type"] == "exp_start":
            changes.append(f"Started testing {_method(e['arms'][0])} against {_method(e['arms'][1])} in "
                           f"{_subject(e['subject'])}.")
        elif e["type"] == "exp_end":
            won = e.get("result", {}).get("decision")
            verdict = f"{_method(won)} works better" if won in METHODS else "no real difference"
            changes.append(f"An experiment finished: {verdict}.")
    r, r0 = rate(answers), rate(earlier)
    return {"week": f"{monday.isocalendar()[0]}-W{monday.isocalendar()[1]:02d}", "monday": monday.isoformat(),
            "days": len({e["ts"][:10] for e in answers}), "answers": len(answers),
            "minutes": round(sum(e.get("seconds") or 0 for e in answers) / 60, 1), "right": r,
            "right_change": round(r - r0, 3) if r is not None and r0 is not None else None, "secured": secured,
            "fixed": [f"“{_mis_text(tutor.packs, kc, m)}”" for kc, m in sorted(was - still)], "changes": changes}
