"""The Tutor: runs a study session as a sequence of blocks and keeps answer keys out of the model's view.

The model only ever sees what `next()` returns (stems/options, never keys) and what `answer()`
returns after an attempt. Every graded attempt becomes an event; state is a fold over events.
"""
from __future__ import annotations

import random
import re
import uuid
from datetime import datetime

from . import diagnose, grade, model, policy
from .packs import Packs, instantiate
from .store import Vault, read_json, write_json

PUBLIC = ("kind", "stem", "options", "marks", "command_word", "image")
GENERIC_HINTS = [
    "Re-read the command word and underline what is given and what is asked.",
    "Which principle or equation links the given quantities to the unknown?",
    "Write the first line of working; check units before substituting.",
]


class Tutor:
    def __init__(self, vault: Vault, rng: random.Random | None = None, now=None):
        self.vault = vault
        self.packs = Packs(vault)
        self.rng = rng or random.Random()
        self._now = now or vault.now
        self.state_path = vault.tutor / "state" / "learner.json"
        self.session_path = vault.tutor / "state" / "session.json"
        self.state = read_json(self.state_path) or self._fold()
        self.session = read_json(self.session_path)

    # ---------- persistence ----------
    def now(self) -> datetime:
        return self._now()

    def _fold(self) -> dict:
        s = model.new_state()
        for e in self.vault.events():
            model.apply(s, e)
        return s

    def _save(self) -> None:
        write_json(self.state_path, self.state)
        if self.session:
            write_json(self.session_path, self.session)
        else:
            self.session_path.unlink(missing_ok=True)

    def log(self, event: dict) -> dict:
        e = self.vault.append_event(event, now=self.now())
        model.apply(self.state, e)
        self._save()
        return e

    def rebuild(self) -> dict:
        self.state = self._fold()
        self._save()
        return {"kcs": len(self.state["kcs"]), "events": sum(1 for _ in self.vault.events())}

    # ---------- session lifecycle ----------
    def start(self, mode: str = "autopilot", minutes: int = 50, focus: list[str] | None = None) -> dict:
        if self.session:
            self.end(abandoned=True)
        blocks = policy.plan_session(self.state, self.packs, self.now(), minutes, mode, focus)
        self.session = {"id": uuid.uuid4().hex[:8], "mode": mode, "minutes": minutes, "started": self.now().isoformat(),
                        "blocks": blocks, "cursor": 0, "presented": {}, "count": 0, "answered": 0, "correct": 0,
                        "kcs_learned": [], "retest": {}}
        self.log({"type": "session_start", "session": self.session["id"], "mode": mode, "minutes": minutes,
                  "blocks": [b["kind"] for b in blocks]})
        return {"session": self.session["id"], "blocks": blocks, "missing_packs": policy.missing_packs(self.packs, self.now())}

    def end(self, abandoned: bool = False) -> dict:
        s = self.session or {}
        summary = {"session": s.get("id"), "answered": s.get("answered", 0), "correct": s.get("correct", 0),
                   "accuracy": round(s["correct"] / s["answered"], 2) if s.get("answered") else None,
                   "kcs_learned": s.get("kcs_learned", []), "unanswered": len(s.get("presented", {})),
                   "abandoned": abandoned}
        self.log({"type": "session_end", **summary})
        self.session = None
        self._save()
        return summary

    # ---------- presenting ----------
    def _present(self, item: dict, block: str, phase: str | None, unassisted: bool = False,
                 block_idx: int | None = None, exp: str | None = None) -> dict:
        inst = instantiate(item, self.rng)
        s = self.session
        s["count"] += 1
        n = s["count"]
        meta = self.packs.kc(item["kcs"][0]) if item["kcs"][0] in self.packs.kcs else {}
        s["presented"][str(n)] = {"item": item["id"], "inst": inst, "kcs": item["kcs"], "subject": meta.get("subject"),
                                  "difficulty": item.get("difficulty", 3), "marks": item.get("marks", 1),
                                  "block": block, "block_idx": block_idx, "phase": phase, "shown_at": self.now().isoformat(),
                                  "hinted": False, "hint_level": 0, "unassisted": unassisted, "exp": exp}
        return self._view(n)

    def _view(self, n: int) -> dict:
        p = self.session["presented"][str(n)]
        inst = p["inst"]
        v = {"n": n, **{k: inst[k] for k in PUBLIC if inst.get(k) is not None}, "unassisted": p["unassisted"]}
        if inst.get("source", {}).get("type") == "past":
            v["source"] = inst["source"].get("ref")
        if inst["kind"] == "structured":
            v["scheme_points"] = len(inst.get("scheme", []))
        return v

    def _pick(self, kc: str, target: float, kinds=("mcq", "numeric", "expression", "short")) -> dict | None:
        """Prefer items not yet used this session; fall back to reuse rather than skip the KC."""
        open_ = {p["item"] for p in self.session["presented"].values()}
        used = open_ | set(self.session.get("used", []))
        return (self.packs.select_item(kc, self.state, target, self.rng, self.now(), kinds=kinds, exclude=used)
                or self.packs.select_item(kc, self.state, target, self.rng, self.now(), kinds=kinds, exclude=open_))

    def _questions(self, block: dict, idx: int, items: list[dict], phase: str | None = None,
                   unassisted: bool = False, exp: str | None = None) -> dict | None:
        views = []
        for it in items:
            self.session.setdefault("used", []).append(it["id"])
            views.append(self._present(it, block["kind"], phase, unassisted, idx, exp))
        if not views:
            return None
        self._save()
        return {"activity": "questions", "block": block["kind"], "phase": phase, "items": views,
                "ask": "Stems may contain LaTeX: show them in chat. Collect answer + confidence (1 guess .. 4 certain)."}

    # ---------- next ----------
    def next(self) -> dict:
        s = self.session
        if not s:
            return {"activity": "no_session", "hint": "run: session start"}
        if s["presented"]:
            return {"activity": "awaiting", "items": [self._view(int(n)) for n in s["presented"]]}
        while s["cursor"] < len(s["blocks"]):
            idx = s["cursor"]
            act = getattr(self, "_step_" + s["blocks"][idx]["kind"])(s["blocks"][idx], idx)
            if act:
                self._save()
                return act
            s["cursor"] += 1
        self._save()
        return {"activity": "end", "hint": "run: session end"}

    def _step_review(self, b: dict, idx: int) -> dict | None:
        i = b.setdefault("i", 0)
        batch = b["kcs"][i:i + 2]
        b["i"] = i + len(batch)
        items = [it for kc in batch if (it := self._pick(kc, 0.8))]
        return self._questions(b, idx, items) if batch else None

    def _step_practice(self, b: dict, idx: int) -> dict | None:
        return self._step_review(b, idx)

    def _step_exit(self, b: dict, idx: int) -> dict | None:
        i = b.setdefault("i", 0)
        batch = b["kcs"][i:i + 2]
        b["i"] = i + len(batch)
        items = [it for kc in batch if (it := self._pick(kc, 0.75))]
        return self._questions(b, idx, items, unassisted=True) if batch else None

    def _step_bracket(self, b: dict, idx: int) -> dict | None:
        st = b.setdefault("st", {kc: {"asked": [], "errors": [], "mis": [], "items": []} for kc in b["kcs"]})
        items = []
        for kc, rec in st.items():
            want = diagnose.next_difficulty([tuple(a) for a in rec["asked"]])
            it = diagnose.pick(self.packs, kc, want, set(rec["items"])) if want else None
            if it:
                rec["items"].append(it["id"])
                items.append(it)
            if len(items) == 2:
                break
        if items:
            act = self._questions(b, idx, items, phase="diagnose", unassisted=True)
            act["say"] = "Diagnostic: no hints, no teaching yet. 'Don't know' is a valid answer."
            return act
        results = {kc: diagnose.classify([tuple(a) for a in r["asked"]], r["errors"], r["mis"]) for kc, r in st.items()}
        gaps = [kc for kc, r in results.items() if diagnose.needs_repair(r)]
        self.log({"type": "diagnosis", "results": results})
        if gaps:
            self.log({"type": "gaps", "add": gaps})
        n = max(1, int(0.75 * max(0, self.session["minutes"] - 12) / 18))
        repair = [{"kind": "learn", "kc": kc, "gap_type": results[kc]["gap_type"]} for kc in gaps[:n]]
        old = [kc for kc, k in self.state["kcs"].items()
               if kc not in st and k["n"] > 0 and kc in self.packs.kcs and self.packs.items_for(kc)][:3]
        extra = repair + ([{"kind": "practice", "kcs": old}] if old else [])
        extra.append({"kind": "exit", "kcs": (gaps[:n] or list(st))[:3]})
        self.session["blocks"][idx + 1:idx + 1] = extra
        return None

    def _step_long(self, b: dict, idx: int) -> dict | None:
        i = b.setdefault("i", 0)
        while i < len(b["kcs"]):
            kc = b["kcs"][i]
            i += 1
            b["i"] = i
            it = self._pick(kc, 0.5, kinds=("structured",))
            if it:
                act = self._questions(b, idx, [it], phase="long")
                act["say"] = ("Long question: they write full working on the iPad and export it to Inbox as "
                              f"'{act['items'][0]['n']}.pdf'. Wait for the upload, then use the mark flow.")
                return act
        return None

    def _retest_target(self, kc: str) -> int:
        items = self.packs.items_for(kc)
        return 3 if any(i.get("template") for i in items) else min(3, len(items))

    def _step_retest(self, b: dict, idx: int) -> dict | None:
        for kc in b["kcs"]:
            given = b.setdefault("given", {}).get(kc, 0)
            need = self._retest_target(kc) - given
            if need > 0:
                items = []
                for _ in range(min(2, need)):
                    it = self._pick(kc, 0.8)
                    if it:
                        items.append(it)
                        self.session.setdefault("used", []).append(it["id"])
                b["given"][kc] = given + len(items)
                if not items:
                    b["given"][kc] = self._retest_target(kc)
                    continue
                return self._questions(b, idx, items, phase="retest", unassisted=True, exp=b["exp"][kc])
        return None

    def _step_learn(self, b: dict, idx: int) -> dict | None:
        kc = b["kc"]
        if not b.get("pretested"):
            b["pretested"] = True
            b["fresh"] = self.state["kcs"].get(kc, {}).get("n", 0) == 0
            items, used = [], set()
            for _ in range(2):
                it = self.packs.select_item(kc, self.state, 0.5, self.rng, self.now(), kinds=("mcq", "numeric", "expression"),
                                            exclude=used | {p["item"] for p in self.session["presented"].values()})
                if it:
                    items.append(it)
                    used.add(it["id"])
            act = self._questions(b, idx, items, phase="pretest")
            if act:
                act["say"] = "Pretest: have a go before any teaching. Wrong answers here are expected and useful."
                return act
        if not b.get("method"):
            method, assignment = policy.choose_method(self.state, self.packs, kc, self.rng, b.get("fresh", False))
            b["method"], b["steps"], b["si"] = method, policy.METHOD_PHASES[method], 0
            self.log({"type": "method", "kc": kc, "method": method, "exp": assignment and assignment["exp"]})
            if assignment:
                self.log({"type": "exp_assign", **assignment})
        if b.get("walkthrough"):
            b["walkthrough"] = False
            wk = (self.packs.worked_for(kc) or [None])[0]
            if wk:
                return {"activity": "walkthrough", "block": "learn", "kc": kc, "steps": wk["steps"],
                        "problem": wk.get("faded", {}).get("problem"),
                        "say": "Walk from their first wrong step, one step per turn; they do each step."}
        pack = self.packs.pack_for_kc(kc) or {}
        meta = self.packs.kc(kc)
        while b["si"] < len(b["steps"]):
            phase = b["steps"][b["si"]]
            b["si"] += 1
            if phase == "lesson":
                return {"activity": "teach", "block": "learn", "kc": kc, "kc_title": meta["title"],
                        "statement": meta.get("statement"), "method": b["method"], "card": policy.METHOD_CARDS[b["method"]],
                        "note": pack.get("note", ""), "outline": pack.get("outline", ""),
                        "misconceptions": [m["statement"] for m in pack.get("misconceptions", []) if m["kc"] == kc]}
            if phase == "worked":
                wk = (self.packs.worked_for(kc) or [None])[0]
                if wk:
                    return {"activity": "worked", "block": "learn", "kc": kc, "problem": wk["problem"], "steps": wk["steps"],
                            "say": "One step per turn; ask for the next step before revealing it."}
            if phase == "faded":
                wk = (self.packs.worked_for(kc) or [None])[0]
                if wk and wk.get("faded"):
                    f = wk["faded"]
                    item = {"id": f["id"], "kcs": [kc], "kind": "numeric" if "value" in f["answer"] else "expression",
                            "stem": f["problem"], "answer": f["answer"], "difficulty": 3, "marks": 2}
                    return self._questions(b, idx, [item], phase="faded")
            if phase == "challenge":
                it = self._pick(kc, 0.3)
                if it:
                    act = self._questions(b, idx, [it], phase="challenge", unassisted=True)
                    act["say"] = "Productive-failure challenge: attempt cold, no hints. Any approach counts."
                    return act
            if phase == "refute":
                mis = [m for m in pack.get("misconceptions", [])
                       if m["id"] in self.state["kcs"].get(kc, {}).get("active_misconceptions", [])]
                if mis:
                    return {"activity": "refute", "block": "learn", "kc": kc, "card": policy.METHOD_CARDS["refutation"],
                            "misconceptions": mis}
            if phase == "probe":
                active = set(self.state["kcs"].get(kc, {}).get("active_misconceptions", []))
                items = [i for i in self.packs.items_for(kc)
                         if active & set((i.get("distractors") or {}).values() if isinstance(i.get("distractors"), dict) else
                                         [d.get("misconception") for d in i.get("distractors") or []]
                                         + [d.get("misconception") for d in (i.get("template") or {}).get("distractors", [])])][:2]
                act = self._questions(b, idx, items, phase="probe")
                if act:
                    return act
            if phase == "practice":
                done = b.get("practiced", 0)
                if done < 3:
                    b["practiced"] = done + 2
                    b["si"] -= 1
                    items = [it for it in (self._pick(kc, 0.65), None) if it]
                    second = self._pick(kc, 0.65)
                    if second and second["id"] not in {i["id"] for i in items}:
                        items.append(second)
                    act = self._questions(b, idx, items[: 3 - done], phase="practice")
                    if act:
                        return act
                    b["si"] += 1
        if kc not in self.session["kcs_learned"]:
            self.session["kcs_learned"].append(kc)
        return None

    # ---------- answers ----------
    def answer(self, text: str, judge: dict | None = None) -> dict:
        s = self.session
        if not s:
            return {"error": "no active session"}
        judge = {int(k): v for k, v in (judge or {}).items()}
        results = []
        for r in grade.parse_responses(text):
            key = str(r["n"])
            p = s["presented"].get(key)
            if not p:
                results.append({"n": r["n"], "error": "not an open question"})
                continue
            inst = p["inst"]
            expected = _expected_kind(inst["kind"])
            if r["kind"] != "idk" and r["kind"] not in expected:
                results.append({"n": r["n"], "error": f"question {r['n']} expects {' or '.join(expected)}; "
                                                     "resend in the right form (it stays open)"})
                continue
            g = grade.grade_item(inst, r)
            if r["n"] in judge:
                sc = float(judge[r["n"]])
                g.update(score=sc, correct=sc >= model.SUCCESS, needs_judgement=False)
            elif inst["kind"] == "short" and g["needs_judgement"]:
                results.append({"n": r["n"], "pending_judgement": True, "matched_score": g["score"],
                                "unmatched": g.get("unmatched"), "rubric": [pt["point"] for pt in inst["rubric"]],
                                "say": "Judge the unmatched points, then resend with judge {n: score 0..1}."})
                continue
            results.append(self._record(key, p, r, g))
        self._save()
        return {"results": results, "remaining": len(s["presented"])}

    def _record(self, key: str, p: dict, r: dict, g: dict) -> dict:
        s, inst = self.session, p["inst"]
        seconds = (self.now() - datetime.fromisoformat(p["shown_at"])).total_seconds()
        credit = sorted({pre for kc in p["kcs"] if kc in self.packs.kcs for pre in self.packs.kc(kc).get("prereqs", [])
                         if self.state["kcs"].get(pre, {}).get("fsrs")})
        ev = self.log({"type": "answer", "session": s["id"], "item": p["item"], "kcs": p["kcs"], "subject": p["subject"],
                       "difficulty": p["difficulty"], "conf": r.get("conf"), "hinted": p["hinted"], "seconds": round(seconds),
                       "marks": p["marks"], "grade": {k: g[k] for k in ("correct", "score", "error", "misconception")},
                       "credit": credit, "pos": s["answered"], "block": p["block"], "phase": p["phase"],
                       "params": inst.get("params"), "response": r["value"] if r["kind"] != "idk" else "don't know"})
        del s["presented"][key]
        s["answered"] += 1
        s["correct"] += 1 if g["correct"] else 0
        if p["block"] == "bracket":
            rec = s["blocks"][p["block_idx"]]["st"][p["kcs"][0]]
            rec["asked"].append([p["difficulty"], g["correct"]])
            if g["error"]:
                rec["errors"].append(g["error"])
            if g.get("misconception"):
                rec["mis"].append(g["misconception"])
        if p["phase"] == "faded" and not g["correct"] and p["block_idx"] is not None:
            s["blocks"][p["block_idx"]]["walkthrough"] = True
        if p["exp"]:
            kc = p["kcs"][0]
            scores = s["retest"].setdefault(kc, [])
            scores.append(g["score"])
            if len(scores) >= self._retest_target(kc):
                self.log({"type": "exp_score", "exp": p["exp"], "kc": kc, "score": round(sum(scores) / len(scores), 3)})
        fb = {"n": int(key), "event": ev["id"], "correct": g["correct"], "score": g["score"], "error": g["error"],
              "answer": _display_answer(inst), "explanation": inst.get("explanation"),
              "needs_judgement": g["needs_judgement"], "detail": g.get("detail")}
        if g.get("misconception") and p["kcs"][0] in self.packs.kcs:
            fb["misconception"] = self.packs.misconception(self.packs.kc(p["kcs"][0])["subtopic"], g["misconception"])
        if r.get("conf") and r["conf"] >= 3 and not g["correct"]:
            fb["hypercorrect"] = "Confident but wrong: spend a turn on why; this is the best moment to fix it."
        return fb

    def scheme(self, n: int) -> dict:
        p = (self.session or {}).get("presented", {}).get(str(n))
        if not p or p["inst"]["kind"] != "structured":
            return {"error": "no open structured question with that number"}
        p["scheme_shown"] = True
        self._save()
        return {"n": n, "marks": p["marks"],
                "scheme": [{"i": i, "mark": pt.get("mark", ""), "point": pt.get("point", "")}
                           for i, pt in enumerate(p["inst"]["scheme"], 1)],
                "say": "Learner ticks the points they earned first (self-mark), then the marker audits."}

    # ---------- past papers ----------
    def paper_list(self, code: str | None = None) -> list[dict]:
        done = {e["paper"] for e in self.vault.events() if e["type"] == "paper_result"}
        return [{"id": p["id"], "qp": p["qp"], "ms": p["ms"], "marks": p["marks"], "done": p["id"] in done}
                for p in self.packs.papers if not code or p["code"] == code]

    def paper_score(self, paper_id: str, text: str) -> dict:
        paper = next((p for p in self.packs.papers if p["id"] == paper_id), None)
        if not paper:
            return {"error": f"unknown paper {paper_id}"}
        qmap = {q["q"].lower(): q for q in paper["questions"]}
        got = {m[1].lower(): (float(m[2]), float(m[3])) for m in
               re.finditer(r"(\w+)\s*=\s*([\d.]+)\s*/\s*([\d.]+)", text)}
        unknown = sorted(set(got) - set(qmap))
        sid = "paper-" + uuid.uuid4().hex[:6]
        per_kc: dict[str, list[float]] = {}
        for q, (score, out_of) in got.items():
            if q not in qmap:
                continue
            meta = qmap[q]
            kcs = [k for k in meta["kcs"] if k in self.packs.kcs] or meta["kcs"]
            frac = score / out_of if out_of else 0.0
            self.log({"type": "answer", "session": sid, "item": f"{paper_id}:{q}", "kcs": kcs,
                      "subject": self.packs.kc(kcs[0])["subject"] if kcs and kcs[0] in self.packs.kcs else None,
                      "difficulty": 4, "conf": None, "hinted": False, "marks": out_of, "block": "paper", "phase": None,
                      "grade": {"correct": frac >= 1.0, "score": round(frac, 3), "error": None, "misconception": None},
                      "credit": [], "pos": 0, "response": f"{score:g}/{out_of:g}"})
            for k in kcs:
                per_kc.setdefault(k, []).append(frac)
        total, maximum = sum(v[0] for q, v in got.items() if q in qmap), sum(v[1] for q, v in got.items() if q in qmap)
        self.log({"type": "paper_result", "paper": paper_id, "score": total, "max": maximum, "session": sid})
        weakest = sorted(({"kc": k, "score": round(sum(v) / len(v), 2)} for k, v in per_kc.items()), key=lambda x: x["score"])
        return {"paper": paper_id, "score": total, "max": maximum,
                "percent": round(100 * total / maximum, 1) if maximum else None,
                "weakest": weakest[:5], "unknown_questions": unknown, "session": sid}

    def hint(self, n: int) -> dict:
        p = (self.session or {}).get("presented", {}).get(str(n))
        if not p:
            return {"error": "not an open question"}
        if p["unassisted"]:
            return {"n": n, "refused": "This question is unassisted (exit ticket, retest or challenge). Encourage an attempt."}
        hints = p["inst"].get("hints") or [st["do"] for kc in p["kcs"] for wk in self.packs.worked_for(kc)[:1]
                                           for st in wk["steps"]][:3] or GENERIC_HINTS
        p["hint_level"] = min(p["hint_level"] + 1, len(hints))
        p["hinted"] = True
        self._save()
        return {"n": n, "level": p["hint_level"], "hint": hints[p["hint_level"] - 1],
                "say": "Give only this hint, in your words; do not add the next step."}


def _expected_kind(kind: str) -> tuple[str, ...]:
    return {"mcq": ("choice",), "structured": ("points",)}.get(kind, ("value", "points"))


def _display_answer(inst: dict) -> str:
    kind = inst["kind"]
    if kind == "mcq":
        return f"{inst['answer']}: {inst['options'][inst['answer']]}"
    if kind == "numeric":
        a = inst["answer"]
        sf = (a.get("sf_ok") or [a.get("sf") or 3])[-1]
        return f"{a['value']:.{sf}g} {a.get('unit', '')}".strip()
    if kind == "expression":
        return inst["answer"]["expr"]
    if kind == "short":
        return "; ".join(pt["point"] for pt in inst["rubric"])
    return "; ".join(f"{pt.get('mark', '')} {pt.get('point', '')}".strip() for pt in inst.get("scheme", []))
