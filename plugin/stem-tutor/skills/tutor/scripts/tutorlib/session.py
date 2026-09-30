"""The Tutor: runs a study session as a sequence of blocks and keeps answer keys out of the model's view.

The model only ever sees what `next()` returns (stems/options, never keys) and what `answer()`
returns after an attempt. Every graded attempt becomes an event; state is a fold over events.
"""
from __future__ import annotations

import random
import re
import uuid
from datetime import datetime

from . import diagnose, grade, model, policy, views
from .lesson import LessonMixin
from .packs import Packs, instantiate
from .store import Vault, read_json, write_json

PUBLIC = ("kind", "stem", "options", "marks", "command_word", "image")
GENERIC_HINTS = [
    "Re-read the command word and underline what is given and what is asked.",
    "Which principle or equation links the given quantities to the unknown?",
    "Write the first line of working; check units before substituting.",
]


class Tutor(LessonMixin):
    def __init__(self, vault: Vault, rng: random.Random | None = None, now=None):
        self.vault = vault
        self.packs = Packs(vault)
        self.rng = rng or random.Random()
        self._now = now or vault.now
        self.state_path = vault.tutor / "state" / "learner.json"
        self.session_path = vault.tutor / "state" / "session.json"
        self.state = read_json(self.state_path)
        if not self.state or self.state.get("model_version") != model.MODEL_VERSION:
            self.state = self._fold()  # first run of a new model version: recompute everything from your history
            self._dirty = True
        self.session = read_json(self.session_path)

    def refresh_content(self) -> list[str]:
        """Between sessions, switch to newly published content: returns the titles of chapters that arrived."""
        if self.session or (self.packs.base / "CURRENT").read_text().strip() == self.packs.root.name:
            return []
        before = self.packs.published()
        self.packs = Packs(self.vault)
        return [self.packs.subtopics[s]["title"] for s in sorted(self.packs.published() - before)
                if s in self.packs.subtopics]

    # ---------- persistence ----------
    def now(self) -> datetime:
        return self._now()

    def _fold(self) -> dict:
        s = model.new_state()
        for e in self.vault.events():
            model.apply(s, e)
        return s

    def _save(self) -> None:
        if getattr(self, "_dirty", True):
            write_json(self.state_path, self.state, indent=None)  # compact; only after something was learned
            self._dirty = False
        if self.session is not None or (self.vault.root / "Now.md").exists():
            self._write_now()
        if self.session or self.session_path.exists():
            write_json(self.session_path, self.session)  # null when closed: deleting is not allowed in Cowork

    def log(self, event: dict) -> dict:
        e = self.vault.append_event(event, now=self.now())
        model.apply(self.state, e)
        self._dirty = True
        self._save()
        return e

    # ---------- Obsidian views ----------
    def _lesson_log(self) -> views.LessonLog | None:
        rel = (self.session or {}).get("log")
        return views.LessonLog(self.vault.root, rel) if rel else None

    def _set_now(self, activity: dict | None = None) -> None:
        if self.session is not None:
            self.session["now"] = activity
            self.session.pop("last_feedback", None) if activity and activity.get("activity") != "feedback" else None

    def _write_now(self) -> None:
        s = self.session
        if not s:
            views.write_now(self.vault.root, f"No session running · {self.now():%H:%M}",
                            ["Start the tutor to begin. Your last lessons are in the Lessons folder."])
            return
        blocks = []
        for fb in s.get("last_feedback", []):
            kind = "success" if fb.get("correct") else "failure"
            body = f"Answer: {fb.get('answer', '')}" + (f"\n\n{fb['explanation']}" if fb.get("explanation") else "")
            blocks.append(views.callout(kind, f"Q{fb['n']} — {'correct ✓' if fb.get('correct') else 'not quite ✗'}", body))
        act = s.get("now") or {}
        kind = act.get("activity")
        if kind == "explain":
            blocks.append(views.callout("abstract", act["title"], act["text"]))
        elif kind == "teach":
            blocks.append(views.callout("abstract", act["kc_title"], _teach_text(act)))
        elif kind == "plan":
            ticks = "\n".join(f"- [{' ' if n['kc'] in act['default_teach'] else 'x'}] {n['title']}" for n in act["nodes"])
            blocks.append(views.callout("abstract", f"Plan: {act['title']}", act["approach"]) + "\n\n" + act["map"]
                          + "\n\n" + ticks)
        elif kind == "choose":
            blocks.append(views.callout("question", act["question"],
                                        "\n".join(f"- {v}" for v in act["options"].values())))
        elif kind == "worked":
            shown = act.get("revealed", 0)
            steps = "\n".join(f"{i}. {st['do']}" for i, st in enumerate(act["steps"][:shown], 1))
            blocks.append(views.callout("example", "Worked example", act["problem"] + ("\n\n" + steps if steps else "")))
        elif kind == "refute":
            m = act["misconceptions"][0]
            blocks.append(views.callout("warning", "Trap: " + m["statement"],
                                        m.get("refutation", "") + ("\n\n" + m["contrast"] if m.get("contrast") else "")))
        elif kind in ("own_words", "stuck"):
            blocks.append(views.callout("tip", act.get("title", ""), act.get("prompt") or act.get("say", "")))
        for n in sorted(s.get("presented", {}), key=int):
            blocks.append(views.question_block(self._view(int(n))))
        sub = s.get("subtopic")
        notes = views.notes_rel(self.packs, sub) if sub and (self.vault.root / views.notes_rel(self.packs, sub)).exists() else None
        title = self.packs.subtopics.get(sub, {}).get("title", "") if sub else ""
        views.write_now(self.vault.root, " · ".join(x for x in (title, s.get("mode", ""), f"{self.now():%H:%M}") if x),
                        blocks or ["Working…"], notes)

    def rebuild(self) -> dict:
        self.state = self._fold()
        self._dirty = True
        self._save()
        return {"kcs": len(self.state["kcs"]), "events": sum(1 for _ in self.vault.events())}

    # ---------- session lifecycle ----------
    def start(self, mode: str = "autopilot", minutes: int = 50, focus: list[str] | None = None,
              replace: bool = False) -> dict:
        s = self.session
        if s and s.get("answered") and not replace:
            return {"ok": False, "error": f"A {s['mode']} session is in progress ({s['answered']} answered).",
                    "open_session": {"mode": s["mode"], "answered": s["answered"], "started": s["started"]},
                    "fix": "To continue it, run the engine command next. To start over, repeat session start with --replace."}
        blocks = policy.plan_session(self.state, self.packs, self.now(), minutes, mode, focus)
        if focus and mode in ("test", "learn", "diagnose", "long", "lesson") and not any(
                self.packs.items_for(k) for b in blocks for k in b.get("kcs", []) + [b.get("kc")] if k):
            return {"ok": False, "error": f"No questions are built yet for {', '.join(focus)}.",
                    "fix": "Use ids that find reports with has_pack true, or ask the learner to choose another topic."}
        if self.session:
            self.end(abandoned=True)
        self.session = {"id": uuid.uuid4().hex[:8], "mode": mode, "minutes": minutes, "started": self.now().isoformat(),
                        "blocks": blocks, "cursor": 0, "presented": {}, "count": 0, "answered": 0, "correct": 0,
                        "kcs_learned": [], "retest": {}}
        sub = next((b["subtopic"] for b in blocks if b.get("subtopic")), None)
        if not sub and focus:
            subs = {self.packs.kc(k)["subtopic"] for k in policy.expand_focus(self.packs, focus) or [] if k in self.packs.kcs}
            sub = subs.pop() if len(subs) == 1 else None
        if sub:
            self.session["subtopic"] = sub
        label = ({"autopilot": "Today's plan", "weak": "Weak spots"}.get(mode)
                 or (self.packs.subtopics.get(sub, {}).get("title") if sub else None) or ", ".join(focus or []) or mode)
        self.session["log"] = views.LessonLog.create(self.vault.root, f"{mode.title()} - {label}", self.now()).rel
        self.log({"type": "session_start", "session": self.session["id"], "mode": mode, "minutes": minutes,
                  "blocks": [b["kind"] for b in blocks]})
        return {"session": self.session["id"], "blocks": blocks}

    def end(self, abandoned: bool = False) -> dict:
        if self.session is None:
            return {"session": None, "answered": 0, "correct": 0, "accuracy": None, "kcs_learned": [],
                    "unanswered": 0, "abandoned": abandoned}
        s = self.session
        summary = {"session": s.get("id"), "answered": s.get("answered", 0), "correct": s.get("correct", 0),
                   "accuracy": round(s["correct"] / s["answered"], 2) if s.get("answered") else None,
                   "kcs_learned": s.get("kcs_learned", []), "unanswered": len(s.get("presented", {})),
                   "abandoned": abandoned}
        self.log({"type": "session_end", **summary})
        if (log := self._lesson_log()) and not abandoned:
            log.tutor(f"Answered {summary['answered']}, correct {summary['correct']}"
                      + (f"; learned: {', '.join(self.packs.kcs[k]['title'] for k in summary['kcs_learned'] if k in self.packs.kcs)}"
                         if summary["kcs_learned"] else "") + ".", title="Session summary")
        kcs = [k for p in s.get("presented", {}).values() for k in p.get("kcs", [])] + summary["kcs_learned"] \
            + s.get("kcs_answered", [])  # answered questions have left `presented`: a review changes mastery too
        touched = {self.packs.kcs[k]["subtopic"] for k in kcs if k in self.packs.kcs}
        if s.get("subtopic"):
            touched.add(s["subtopic"])
        self.session = None
        self._save()
        for sub in touched:
            views.refresh_status(self.vault.root, self.packs, self.state, sub)
        recent = sorted((str(f.relative_to(self.vault.root)) for f in (self.vault.root / "Lessons").glob("*.md")),
                        reverse=True) if (self.vault.root / "Lessons").exists() else []
        views.write_home(self.vault.root, self.packs, self.state, self.now(), recent)
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
        self._audit("present", n, inst)
        if (log := self._lesson_log()):
            log.question(self._view(n), label=phase or "")
        return self._view(n)

    def _audit(self, event: str, n: int, inst: dict) -> None:
        """Evaluation-only trail (STEM_TUTOR_AUDIT=1): when each question was shown and answered, with its key."""
        import json
        import os
        if not os.environ.get("STEM_TUTOR_AUDIT"):
            return
        row = {"event": event, "n": n, "turn": int(os.environ.get("STEM_TUTOR_TURN", "0")),
               "item": inst.get("id"), "key": _display_answer(inst), "kind": inst["kind"]}
        with open(self.vault.tutor / "audit.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

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
        shown = []
        for it in items:
            self.session.setdefault("used", []).append(it["id"])
            shown.append(self._present(it, block["kind"], phase, unassisted, idx, exp))
        if not shown:
            return None
        self._set_now({"activity": "questions"})
        self._save()
        return {"activity": "questions", "block": block["kind"], "phase": phase, "items": shown,
                "ask": "Stems may contain LaTeX: show them in chat. Collect answer + confidence (1 guess .. 4 certain)."}

    # ---------- next ----------
    def next(self) -> dict:
        s = self.session
        if not s:
            return {"activity": "no_session", "hint": "engine command: session start"}
        if s.get("awaiting"):
            return s["awaiting"]
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
        return {"activity": "end", "hint": "engine command: session end"}

    def _step_review(self, b: dict, idx: int) -> dict | None:
        while b.setdefault("i", 0) < len(b["kcs"]):  # keep going past ideas with no usable question
            batch = b["kcs"][b["i"]:b["i"] + 2]
            b["i"] += len(batch)
            items = [it for kc in batch if (it := self._pick(kc, b.get("target", 0.8)))]
            if items:
                return self._questions(b, idx, items)
        return None

    def _step_practice(self, b: dict, idx: int) -> dict | None:
        return self._step_review(b, idx)

    def _step_exit(self, b: dict, idx: int) -> dict | None:
        while b.setdefault("i", 0) < len(b["kcs"]):
            batch = b["kcs"][b["i"]:b["i"] + 2]
            b["i"] += len(batch)
            items = [it for kc in batch if (it := self._pick(kc, 0.75))]
            if items:
                return self._questions(b, idx, items, unassisted=True)
        return None

    def _step_bracket(self, b: dict, idx: int) -> dict | None:
        st = b.setdefault("st", {kc: {"asked": [], "errors": [], "mis": [], "items": []} for kc in b["kcs"]})
        items = []
        for kc, rec in st.items():
            want = diagnose.next_difficulty([tuple(a) for a in rec["asked"]])
            it = diagnose.pick(self.packs, kc, want, set(rec["items"])) if want else None
            if it:
                rec["items"].append(it["id"])
                b.setdefault("asked_for", {})[it["id"]] = kc
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

    def _step_sweep(self, b: dict, idx: int) -> dict | None:
        """Test prep: one exam-level question per KC, interleaved across subtopics; then repair only what was missed."""
        asked = b.setdefault("asked", {})
        while b.setdefault("i", 0) < len(b["kcs"]):
            batch = b["kcs"][b["i"]:b["i"] + 2]
            b["i"] += len(batch)
            items = []
            for kc in batch:
                it = self._pick(kc, 0.6)
                if it:
                    asked[it["id"]] = kc
                    items.append(it)
            act = self._questions(b, idx, items, phase="sweep", unassisted=True)
            if act:
                act["say"] = "Test check: one question per syllabus point, no hints until answered. 'Don't know' is a fine answer."
                return act
        res = b.get("res", {})
        if b.get("lesson_probe"):
            self.session["probe"] = res
            return None
        wrong = [kc for kc in b["kcs"] if kc in res and not res[kc]["ok"]]
        unsure = [kc for kc in b["kcs"] if kc in res and res[kc]["ok"] and (res[kc]["conf"] or 0) <= 2]
        if wrong:
            self.log({"type": "gaps", "add": wrong})
        n = max(1, int(max(0, self.session["minutes"] - 2 * len(b["kcs"]) - 10) / 12)) if wrong else 0
        extra: list[dict] = [{"kind": "learn", "kc": kc, "pretested": True} for kc in wrong[:n]]
        pool = wrong[n:] + unsure
        if pool:
            extra.append({"kind": "practice", "kcs": pool})
        if not wrong and not unsure:
            extra.append({"kind": "practice", "kcs": list(b["kcs"]), "target": 0.5})
        extra.append({"kind": "exit", "kcs": (wrong[:n] or unsure or list(b["kcs"]))[:3]})
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
                act["say"] = ("Long question: full working, units and a final answer; then mark it against the scheme "
                              f"(handwritten on the iPad? name the PDF '{act['items'][0]['n']}.pdf').")
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
                act = self._questions(b, idx, items, phase="retest", unassisted=True, exp=b["exp"][kc])
                for q in act["items"]:  # an item may cover several ideas: its score belongs to the one retested
                    self.session["presented"][str(q["n"])]["exp_kc"] = kc
                return act
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
            if wk:  # awaited, like the worked example below, so a restart resumes it at the same step
                return self._await({"activity": "walkthrough", "block": "learn", "kc": kc, "steps": wk["steps"],
                                    "problem": wk.get("faded", {}).get("problem"), "block_idx": idx,
                                    "say": "Walk from their first wrong step, one step per turn; they do each step."})
        pack = self.packs.pack_for_kc(kc) or {}
        meta = self.packs.kc(kc)
        while b["si"] < len(b["steps"]):
            phase = b["steps"][b["si"]]
            b["si"] += 1
            if phase == "lesson":  # awaited like the worked example: shown in Now, logged, resumed after a restart
                act = {"activity": "teach", "block": "learn", "kc": kc, "kc_title": meta["title"],
                       "statement": meta.get("statement"), "method": b["method"], "card": policy.METHOD_CARDS[b["method"]],
                       "note": pack.get("note", ""), "outline": pack.get("outline", ""), "block_idx": idx,
                       "misconceptions": [m["statement"] for m in pack.get("misconceptions", []) if m["kc"] == kc]}
                if (log := self._lesson_log()):
                    log.tutor(_teach_text(act), title=act["kc_title"])
                return self._await(act)
            if phase == "worked":
                wk = (self.packs.worked_for(kc) or [None])[0]
                if wk:  # awaited: a restart comes back to this example at the step reached, not past it
                    return self._await({"activity": "worked", "block": "learn", "kc": kc, "problem": wk["problem"],
                                        "steps": wk["steps"], "block_idx": idx,
                                        "say": "One step per turn; ask for the next step before revealing it."})
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
                    if (log := self._lesson_log()):
                        log.add(views.callout("warning", "Trap: " + mis[0]["statement"], mis[0].get("refutation", "")
                                              + ("\n\n" + mis[0]["contrast"] if mis[0].get("contrast") else "")))
                    return self._await({"activity": "refute", "block": "learn", "kc": kc, "block_idx": idx,
                                        "card": policy.METHOD_CARDS["refutation"], "misconceptions": mis})
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
            return {"ok": False, "error": "no active session", "fix": "engine command: session start"}
        judge = {int(k): v for k, v in (judge or {}).items()}
        results = []
        for r in grade.parse_responses(text):
            key = str(r["n"])
            if r["kind"] == "bad":
                results.append({"n": r["n"], "error": f"could not read {r['value']!r}; resend it as "
                                "'<n>B3' (option + confidence), '<n> = <value> <unit> ~3' or '<n>?'"})
                continue
            p = s["presented"].get(key)
            if not p:
                results.append({"n": r["n"], "error": f"question {r['n']} is not open: it was already marked "
                                "(the first answer stands) or was never asked"})
                continue
            inst = p["inst"]
            if inst["kind"] == "numeric" and r["kind"] == "value":
                problem = grade.value_problem(inst, str(r["value"]))
                if problem == "unreadable":
                    results.append({"n": r["n"], "error": f"could not read the value {r['value']!r}; resend it as "
                                    f"'{r['n']} = <number> <unit> ~<1-4>' (it stays open)"})
                    continue
                if problem == "unit":
                    results.append({"n": r["n"], "error": f"question {r['n']} wants a plain number, no unit; resend "
                                    f"it as '{r['n']} = <number> ~<1-4>' (it stays open)"})
                    continue
            if inst["kind"] == "expression" and r["kind"] == "value" and not grade.expression_readable(str(r["value"])):
                results.append({"n": r["n"], "error": f"could not read the expression {r['value']!r}; use letters, "
                                "numbers, + - * / ^ and brackets, then resend it (it stays open)"})
                continue
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
                                "say": "Judge every rubric point against their answer (keyword matches are only a hint: a "
                                       "swapped or negated statement contains them too), then resend with judge "
                                       "{n: score 0..1}."})
                continue
            results.append(self._record(key, p, r, g))
        done = [fb for fb in results if fb.get("event")]
        if done:
            s["last_feedback"] = [{k: fb.get(k) for k in ("n", "correct", "answer", "explanation")} for fb in done]
            s["now"] = {"activity": "feedback"}
        self._save()
        return {"results": results, "remaining": len(s["presented"])}

    def _typical_seconds(self, subject: str | None) -> float | None:
        sec, marks = self.state["traits"]["time"].get(subject or "", [0.0, 0])
        return sec / marks if marks >= 10 else None

    def blurt(self, subtopic: str, text: str) -> dict:
        """Score a free-recall attempt, pull forgotten ideas forward for review, and keep a record in Lessons."""
        from . import blurt as blurt_mod, lesson
        res = blurt_mod.score(self.packs, subtopic, text)
        self.log({"type": "blurt", "subtopic": subtopic, "recalled": res["recalled"], "missed": res["missed"],
                  "words": res["words"]})
        title = self.packs.subtopics.get(subtopic, {}).get("title", subtopic)
        log = views.LessonLog.create(self.vault.root, f"Blurt - {title}", self.now())
        log.you(text)
        body = [f"Recalled {len(res['recalled'])} of {len(res['ideas'])} ideas."]
        for kc, v in res["ideas"].items():
            body.append(f"- {'✅' if v['recalled'] else '❌'} **{v['title']}**"
                        + ("" if v["recalled"] else f": {' '.join(lesson.teach_card(self, kc).get('note', '').split())[:240]}"))
        log.tutor("\n".join(body), title="What you remembered")
        res["log"] = log.rel
        return res

    def tag(self, event_id: str, code: str) -> dict:
        """Your own verdict on why an answer went wrong (careless slip, misread, didn't know, wrong method…)."""
        return self.log({"type": "tag", "target": event_id, "error": code.upper()})

    def _record(self, key: str, p: dict, r: dict, g: dict) -> dict:
        s, inst = self.session, p["inst"]
        seconds = (self.now() - datetime.fromisoformat(p["shown_at"])).total_seconds()
        kc0 = p["kcs"][0]
        known = kc0 in self.packs.kcs
        p_exp = model.p_correct(self.state["kcs"].get(kc0, {}).get("theta", 0.0), p["difficulty"])
        typical = self._typical_seconds(p["subject"])
        slip = bool(not g["correct"] and r["kind"] != "idk" and not g.get("misconception") and p_exp >= 0.85
                    and typical and seconds <= 0.5 * typical * p["marks"])
        conf_stats = self.state["traits"]["calibration"].get("by_conf", {}).get(str(r.get("conf")))
        credit = sorted({pre for kc in p["kcs"] if kc in self.packs.kcs for pre in self.packs.kc(kc).get("prereqs", [])
                         if self.state["kcs"].get(pre, {}).get("fsrs")})
        ev = self.log({"type": "answer", "session": s["id"], "item": p["item"], "kcs": p["kcs"], "subject": p["subject"],
                       "difficulty": p["difficulty"], "conf": r.get("conf"), "hinted": p["hinted"], "seconds": round(seconds),
                       "marks": p["marks"], "grade": {k: g[k] for k in ("correct", "score", "error", "misconception")},
                       "credit": credit, "pos": s["answered"], "block": p["block"], "phase": p["phase"],
                       "params": inst.get("params"), "response": r["value"] if r["kind"] != "idk" else "don't know",
                       "key": _display_answer(inst),
                       **({"retention": policy.target_retention(self.state, self.packs, kc0, self.now())} if known else {}),
                       **({"slip_likely": True} if slip else {})})
        self._audit("answer", int(key), inst)
        del s["presented"][key]
        s.setdefault("kcs_answered", []).extend(k for k in p["kcs"] if k not in s["kcs_answered"])
        partial = g["correct"] and g["score"] < model.SUCCESS  # right value, mark lost (units, s.f.)
        if partial:
            g = {**g, "correct": False}
        s["answered"] += 1
        s["correct"] += 1 if g["correct"] else 0
        if p["block"] == "bracket":
            blk = s["blocks"][p["block_idx"]]
            rec = blk["st"][blk.get("asked_for", {}).get(p["item"], p["kcs"][0])]
            rec["asked"].append([p["difficulty"], g["correct"]])
            if g["error"]:
                rec["errors"].append(g["error"])
            if g.get("misconception"):
                rec["mis"].append(g["misconception"])
        if p["block"] == "sweep":
            blk = s["blocks"][p["block_idx"]]
            kc = blk.get("asked", {}).get(p["item"], p["kcs"][0])
            blk.setdefault("res", {})[kc] = {"ok": g["correct"], "conf": r.get("conf")}
        if p["unassisted"] and g["correct"] and not p["hinted"]:
            closed = [kc for kc in p["kcs"] if kc in self.state["gaps"]]
            if closed:
                self.log({"type": "gaps", "remove": closed})
        relearn = False
        if p["block"] in ("review", "practice") and not g["correct"] and p["block_idx"] is not None:
            blk = s["blocks"][p["block_idx"]]  # successive relearning: a missed idea comes back later this session
            done = blk.setdefault("relearn", {})
            if not done.get(kc0):
                done[kc0] = 1
                blk["kcs"].insert(min(blk.get("i", 0) + 2, len(blk["kcs"])), kc0)
                relearn = True
        s.setdefault("resid", []).append((1.0 if g["correct"] else 0.0) - p_exp)
        if p["phase"] == "faded" and not g["correct"] and p["block_idx"] is not None:
            s["blocks"][p["block_idx"]]["walkthrough"] = True
        if p["exp"]:
            kc = p.get("exp_kc") or p["kcs"][0]
            scores = s["retest"].setdefault(kc, [])
            scores.append(g["score"])
            if len(scores) >= self._retest_target(kc):
                self.log({"type": "exp_score", "exp": p["exp"], "kc": kc, "score": round(sum(scores) / len(scores), 3)})
        fb = {"n": int(key), "event": ev["id"], "correct": g["correct"], "partial": partial, "score": g["score"],
              "error_code": g["error"],
              "answer": _display_answer(inst), "explanation": inst.get("explanation"),
              "needs_judgement": g["needs_judgement"], "detail": g.get("detail")}
        if inst.get("tier") == "extra":
            fb["official_key_only"] = True
            if inst.get("examiner"):
                fb["examiner"] = inst["examiner"]
        if g.get("misconception") and p["kcs"][0] in self.packs.kcs:
            fb["misconception"] = self.packs.misconception(self.packs.kc(p["kcs"][0])["subtopic"], g["misconception"])
        your = ("?" if r["kind"] == "idk" else f"{r['value']}" if r["kind"] != "points" else
                "points " + ",".join(map(str, r["value"]))) + (f" (confidence {r['conf']})" if r.get("conf") else "")
        if (log := self._lesson_log()):
            log.answer(fb, your)
        if p["block"] == "node" and p["phase"] == "check" and p["block_idx"] is not None:
            self._node_check_result(s["blocks"][p["block_idx"]], g, fb, "?" if r["kind"] == "idk" else str(r["value"]))
        if r.get("conf") and r["conf"] >= 3 and not g["correct"]:
            fb["hypercorrect"] = "Confident but wrong: spend a turn on why; this is the best moment to fix it."
        if relearn:
            fb["relearn"] = True
        if (not g["correct"] and not g.get("misconception") and r["kind"] != "idk"
                and p["phase"] not in ("sweep", "pretest", "discover", "challenge") and s.get("reflections", 0) < 6):
            s["reflections"] = s.get("reflections", 0) + 1
            fb["reflect"] = True  # ask why it went wrong (feeds the mistake profile); capped so it never nags
            fb["slip_likely"] = slip
        knobs = model.knobs(self.state)
        if knobs["confidence_training"] and conf_stats and conf_stats[0] >= 10:
            fb["calibration_note"] = (f"When you say '{['', 'guess', 'unsure', 'fairly sure', 'certain'][r['conf']]}', "
                                      f"you're right {conf_stats[1] / conf_stats[0]:.0%} of the time.")
        recent = s["resid"][-8:]
        if not s.get("break_offered") and ((len(s["resid"]) >= 12 and sum(recent) / len(recent) <= -0.3)
                                           or (knobs["max_items_before_break"] and s["answered"] == knobs["max_items_before_break"])):
            s["break_offered"] = True
            fb["break_suggested"] = True
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
               re.finditer(r"(\w+)\s*=\s*(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)", text)}
        bad = [q for q, (sc, oo) in got.items() if oo <= 0 or sc > oo]
        if bad:
            return {"ok": False, "error": f"scores above the marks available: {', '.join(bad)}",
                    "fix": "Give each question as got/out-of, e.g. 1a=2/3."}
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

    def ai_help(self) -> dict:
        """The learner is asking the AI tutor. While a no-help check (exit ticket, retest, challenge) is open it is
        refused; otherwise every open question counts as hinted, as with hint(): help is help, whoever gives it."""
        open_ = (self.session or {}).get("presented", {})
        if any(p["unassisted"] for p in open_.values()):
            return {"refused": "This is a no-help check: answer it first, then ask me anything."}
        for p in open_.values():
            p["hinted"] = True
        if open_:
            self._save()
        return {"ok": True}


def _teach_text(act: dict) -> str:
    return act.get("outline", "") + "".join(f"\n- Trap: {m}" for m in act.get("misconceptions", []))


def _expected_kind(kind: str) -> tuple[str, ...]:
    return {"mcq": ("choice",), "structured": ("points",)}.get(kind, ("value",))


def _display_answer(inst: dict) -> str:
    kind = inst["kind"]
    if kind == "mcq":
        opts = inst.get("options") or {}  # image-only past-paper options have no text
        return f"{inst['answer']}: {opts[inst['answer']]}" if inst["answer"] in opts else inst["answer"]
    if kind == "numeric":
        a = inst["answer"]
        sf = (a.get("sf_ok") or [a.get("sf") or 3])[-1]
        return f"{a['value']:.{sf}g} {a.get('unit', '')}".strip()
    if kind == "expression":
        return inst["answer"]["expr"]
    if kind == "short":
        return "; ".join(pt["point"] for pt in inst["rubric"])
    return "; ".join(f"{pt.get('mark', '')} {pt.get('point', '')}".strip() for pt in inst.get("scheme", []))
