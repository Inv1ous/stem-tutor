"""Deterministic grading of parity-eval sessions.

  python eval/grade.py <workflow-result.json>

Per session: answer leaks (a tutor message that states a question's key between showing it and its
answer event), engine use (answers logged, questions left open, session closed), misconception
detection for the persona's planted error. Prints a table and a Haiku-vs-Opus summary.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _leaks(transcript: list[dict], audit: list[dict]) -> list[dict]:
    tutor_turns = [m["text"] for m in transcript if m["role"] == "tutor"]
    out = []
    shown = {r["n"]: r for r in audit if r["event"] == "present"}
    answered = {r["n"]: r["turn"] for r in audit if r["event"] == "answer"}
    for n, r in shown.items():
        end = answered.get(n, len(tutor_turns) + 1)
        key = r["key"]
        if r["kind"] == "mcq":
            letter, _, text = key.partition(": ")
            pats = [re.escape(text.strip())] if len(text.strip()) > 3 else []
            pats += [rf"\b(answer|correct option) (is|was) \(?{letter}\b"]
        else:
            num = key.split()[0] if key else ""
            pats = [rf"(?<![\d.]){re.escape(num)}(?![\d])"] if num and re.match(r"-?\d", num) else []
        for t in range(r["turn"], end):
            if 1 <= t <= len(tutor_turns):
                msg = tutor_turns[t - 1]
                # the presenting message itself shows options; only flag stated answers there for numeric keys
                if any(re.search(p, msg, re.I) for p in pats) and not (t == r["turn"] and r["kind"] == "mcq"):
                    out.append({"n": n, "turn": t, "key": key})
                    break
    return out


def grade(run: dict, personas: dict) -> dict:
    vault = Path(run["vault"])
    audit_f = vault / ".tutor/audit.jsonl"
    audit = [json.loads(l) for l in audit_f.read_text().splitlines()] if audit_f.exists() else []
    events = [json.loads(l) for f in sorted((vault / ".tutor/events").glob("*.jsonl")) for l in f.read_text().splitlines()] \
        if (vault / ".tutor/events").exists() else []
    state = json.loads((vault / ".tutor/state/learner.json").read_text()) if (vault / ".tutor/state/learner.json").exists() else {}
    shown = {r["n"] for r in audit if r["event"] == "present"}
    answered = {r["n"] for r in audit if r["event"] == "answer"}
    p = personas[run["persona"]]
    target = p.get("misconception_kc")
    k = (state.get("kcs") or {}).get(target or "", {})
    detected = None
    if target:
        detected = bool(k.get("active_misconceptions") or k.get("mis_counts") or target in (state.get("gaps") or [])
                        or any(e["type"] == "tag" and e.get("error") == "CONCEPT" for e in events))
    return {"persona": run["persona"], "model": run["model"], "turns": run["turns"],
            "questions": len(shown), "answered": len(answered), "open_at_end": len(shown - answered),
            "session_started": any(e["type"] == "session_start" for e in events),
            "session_ended": any(e["type"] == "session_end" for e in events),
            "leaks": _leaks(run["transcript"], audit), "misconception_detected": detected}


if __name__ == "__main__":
    res = json.loads(Path(sys.argv[1]).read_text())
    personas = {p["id"]: p for p in json.loads((ROOT / "eval/personas.json").read_text())}
    rows = [grade(r, personas) for r in res["runs"]]
    for r in rows:
        print(f"{r['persona']:13} {r['model']:6} turns={r['turns']:2} q={r['questions']:2} ans={r['answered']:2} open={r['open_at_end']} "
              f"start={int(r['session_started'])} end={int(r['session_ended'])} leaks={len(r['leaks'])} misc={r['misconception_detected']}")
    for j in res.get("judgements", []):
        print(f"judge {j['persona']:13} A={j['A']} B={j['B']} winner={j['winner']} A={j['scores_A']} B={j['scores_B']}")
    json.dump({"rows": rows, "judgements": res.get("judgements", [])}, open(Path(sys.argv[1]).with_suffix(".graded.json"), "w"), indent=1)
