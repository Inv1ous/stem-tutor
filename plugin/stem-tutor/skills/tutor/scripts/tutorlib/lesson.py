"""Lesson mode: probe → plan → teach, one idea (KC) at a time, like a good private tutor.

Flow (one subtopic):
  goal     what you want from this topic (learn from scratch / fill my gaps / test soon / key ideas fast)
  probe    one question per idea (plus key prerequisites) to find the edge of what you already know
  plan     the concept map; ideas you clearly know are ticked off; you approve or change it
  node     for each idea: motivate → (discover: try it before being told) → establish → (worked example)
           → connect → check without hints → on a miss: fix the trap, then one more check
           → optional "in your own words" → the idea is written into My Notes
  exit     a short no-hints check on what you learned today

Content comes from pre-built teach cards (pack["teach"][kc]); if a card is missing the app may write one with AI
into .tutor/cache/teach/<kc>.json, and otherwise a card is assembled offline from flashcards, traps and worked examples.
Everything here is deterministic: no AI tokens are spent by this module.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from . import policy, views
from .store import read_json

GOALS = {
    "scratch": "Learn it properly from scratch",
    "gaps": "I've had lessons: find and fill my gaps",
    "test": "Revise for a test soon",
    "quick": "Just the key ideas, quickly",
}


def subtopic_order(packs, kcs: list[str]) -> list[str]:
    """Prerequisites first (topological), otherwise syllabus order."""
    order, seen = [], set()

    def visit(k: str) -> None:
        if k in seen:
            return
        seen.add(k)
        for pre in packs.kcs[k].get("prereqs", []):
            if pre in kcs:
                visit(pre)
        order.append(k)

    for k in kcs:
        visit(k)
    return order


def teach_card(tutor, kc: str) -> dict:
    pack = tutor.packs.pack_for_kc(kc) or {}
    card = (pack.get("teach") or {}).get(kc) or read_json(tutor.vault.tutor / "cache" / "teach" / f"{kc}.json")
    if card:
        return {**card, "source": card.get("source", "pack")}
    return offline_card(tutor.packs, kc)


def offline_card(packs, kc: str) -> dict:
    k = packs.kc(kc)
    pack = packs.pack_for_kc(kc) or {}
    cards = [f for f in pack.get("flashcards", []) if f.get("kc") == kc]
    traps = [m for m in pack.get("misconceptions", []) if m["kc"] == kc]
    pres = [packs.kcs[p]["title"] for p in k.get("prereqs", []) if p in packs.kcs]
    facts = "\n".join(f"- **{c['front']}** {c['back']}" for c in cards) or f"- {k['statement'].capitalize()}."
    establish = facts + ("\n\n" + "\n".join(f"- Trap: {m['statement']}. {m['refutation']}" for m in traps) if traps else "")
    return {
        "source": "offline",
        "motivate": f"Next idea: **{k['title']}**. The syllabus asks you to {k['statement']}.",
        "establish": establish,
        "connect": (f"This builds on: {', '.join(pres)}." if pres else "This is a starting point: nothing earlier is needed."),
        "note": "\n".join(f"- {c['back']}" for c in cards) or f"- {k['statement'].capitalize()}.",
        "self_explain": f"In one or two sentences, explain: {k['title'].lower()}.",
    }


class LessonMixin:
    """Mixed into session.Tutor. Uses self.session / self.packs / self.state / self._questions / self.log."""

    if TYPE_CHECKING:
        session: Any
        packs: Any
        state: dict
        vault: Any
        rng: Any

        def _save(self) -> None: ...
        def _set_now(self, activity: dict | None = None) -> None: ...
        def _lesson_log(self) -> views.LessonLog | None: ...
        def _questions(self, block: dict, idx: int, items: list[dict], phase: str | None = None,
                       unassisted: bool = False, exp: str | None = None) -> dict | None: ...
        def _pick(self, kc: str, target: float, kinds: tuple = ...) -> dict | None: ...
        def log(self, event: dict) -> dict: ...

    # ---------------- waiting for the learner (not graded) ----------------
    def _await(self, activity: dict) -> dict:
        self.session["awaiting"] = activity
        self._set_now(activity)
        return activity

    def respond(self, data: dict) -> dict:
        """The learner's reply to a non-graded step: goal choice, plan choices, continue, own words, worked step."""
        s = self.session
        if not s or not s.get("awaiting"):
            return {"ok": False, "error": "nothing is waiting for a reply", "fix": "engine command: next"}
        act = s["awaiting"]
        kind = act["activity"]
        if kind == "worked" and data.get("step") is not None and not data.get("done"):
            i = int(data["step"])
            act["revealed"] = max(act.get("revealed", 0), i)
            if (log := self._lesson_log()) and 1 <= i <= len(act["steps"]):
                st = act["steps"][i - 1]
                log.tutor(f"{st['do']}\n\n_{st['why']}_", title=f"Step {i}")
            self._set_now(act)
            self._save()
            return {"ok": True, "revealed": act["revealed"]}
        s.pop("awaiting")
        blk = s["blocks"][act["block_idx"]] if act.get("block_idx") is not None else {}
        if kind == "choose" and act.get("purpose") == "goal":
            s["goal"] = data.get("choice") if data.get("choice") in GOALS else "gaps"
            self._log_you(GOALS[s["goal"]] + (f" — {data['text']}" if data.get("text") else ""))
            if s["goal"] in ("scratch", "quick"):
                s["blocks"] = [b for b in s["blocks"] if not b.get("lesson_probe")]
        elif kind == "plan":
            teach = [k for k in act["nodes_all"] if k in set(data.get("teach", act["default_teach"]))]
            self._log_you("Plan approved: " + (", ".join(self.packs.kcs[k]["title"] for k in teach) or "nothing to teach"))
            new = [{"kind": "node", "kc": k} for k in teach]
            if s.get("goal") == "test":
                new.append({"kind": "practice", "kcs": act["nodes_all"]})
            new.append({"kind": "exit", "kcs": (teach or act["nodes_all"])[:3]})
            s["blocks"][act["block_idx"] + 1:act["block_idx"] + 1] = new
        elif kind == "own_words":
            if data.get("text"):
                blk["own_words"] = data["text"].strip()
                self._log_you(data["text"])
        elif data.get("text"):  # a free comment on an explanation step
            self._log_you(data["text"])
        self._save()
        return {"ok": True}

    def _log_you(self, text: str) -> None:
        if (log := self._lesson_log()):
            log.you(text)

    # ---------------- blocks ----------------
    def _step_goal(self, b: dict, idx: int) -> dict | None:
        if b.get("done"):
            return None
        b["done"] = True
        sub = self.packs.subtopics.get(b.get("subtopic", ""), {})
        return self._await({"activity": "choose", "purpose": "goal", "block_idx": idx,
                            "question": f"What do you want from {sub.get('title', 'this topic')}?",
                            "options": GOALS, "allow_text": True})

    def _step_plan(self, b: dict, idx: int) -> dict | None:
        if b.get("done"):
            return None
        b["done"] = True
        kcs = subtopic_order(self.packs, [k for k in b["kcs"] if k in self.packs.kcs])
        probe = self.session.get("probe", {})
        known = [k for k in kcs if (probe.get(k, {}).get("ok") and (probe[k].get("conf") or 0) >= 3)
                 or views.kc_status(self.state, k) == "secure"]
        teach = [k for k in kcs if k not in known] if self.session.get("goal") not in ("scratch",) else kcs
        sub = b.get("subtopic")
        roots = [k for k in kcs if not [p for p in self.packs.kcs[k].get("prereqs", []) if p in kcs]]
        approach = (f"We'll build **{len(teach)} idea{'s' if len(teach) != 1 else ''}** in the order of the map: each "
                    "one is motivated, established, connected to what you already have, then checked without hints."
                    + (f" You showed you already know {len(known)} of them, so they are ticked off (you can still "
                       "choose to cover them)." if known else "")
                    + (f" We start from {', '.join(self.packs.kcs[k]['title'] for k in roots[:2])}." if roots else ""))
        act = {"activity": "plan", "block_idx": idx, "subtopic": sub,
               "title": self.packs.subtopics.get(sub, {}).get("title", ""), "approach": approach,
               "map": views.concept_map(self.packs, self.state, sub) if sub else "",
               "nodes": [{"kc": k, "title": self.packs.kcs[k]["title"], "known": k in known} for k in kcs],
               "nodes_all": kcs, "default_teach": teach}
        if (log := self._lesson_log()):
            log.tutor(approach + "\n\n" + act["map"], title="Plan")
        return self._await(act)

    def _step_node(self, b: dict, idx: int) -> dict | None:
        kc = b["kc"]
        s = self.session
        if "phases" not in b:
            card = teach_card(self, kc)
            method, assignment = policy.choose_method(self.state, self.packs, kc, self.rng,
                                                      self.state["kcs"].get(kc, {}).get("n", 0) == 0)
            self.log({"type": "method", "kc": kc, "method": method, "exp": assignment and assignment["exp"]})
            if assignment:
                self.log({"type": "exp_assign", **assignment})
            quick = s.get("goal") == "quick"
            socratic = bool(card.get("discover")) and not quick and method != "refutation"
            worked = bool(self.packs.worked_for(kc)) and method in ("worked_faded", "pretest_explain") and not quick
            b.update(card=card, method=method, i=0, misses=0, mistakes=[], phases=(
                ["motivate"] + (["discover"] if socratic else []) + ["establish"] + (["worked"] if worked else [])
                + (["faded"] if worked and method == "worked_faded" else []) + ["check"]
                + ([] if quick else ["own_words"]) + ["done"]))
            if (sub := self.packs.kcs[kc]["subtopic"]):
                views.notes_update(self.vault.root, self.packs, self.state, sub, current=kc)
        card, title = b["card"], self.packs.kcs[kc]["title"]
        while b["i"] < len(b["phases"]):
            phase = b["phases"][b["i"]]
            b["i"] += 1
            if phase == "motivate":
                return self._explain(idx, kc, "Why this matters", card["motivate"], part="motivate")
            if phase == "discover":
                d = card["discover"]
                item = {"id": f"{kc}-discover", "kcs": [kc], "kind": "mcq", "stem": d["stem"], "options": d["options"],
                        "answer": d["answer"], "explanation": d.get("explanation"), "difficulty": 3, "marks": 1}
                act = self._questions(b, idx, [item], phase="discover")
                if act:
                    act["say"] = "Have a go before being told: what would you expect?"
                    return act
            if phase == "establish":
                text = card["establish"] + ("\n\n**How it connects:** " + card["connect"] if card.get("connect") else "")
                return self._explain(idx, kc, title, text, part="establish")
            if phase == "worked":
                wk = self.packs.worked_for(kc)[0]
                act = {"activity": "worked", "block": "node", "kc": kc, "problem": wk["problem"], "steps": wk["steps"],
                       "block_idx": idx, "say": "Predict each step before you reveal it."}
                if (log := self._lesson_log()):
                    log.tutor(wk["problem"], title="Worked example")
                return self._await(act)
            if phase == "faded":
                wk = self.packs.worked_for(kc)[0]
                if wk.get("faded"):
                    f = wk["faded"]
                    item = {"id": f["id"], "kcs": [kc], "kind": "numeric" if "value" in f["answer"] else "expression",
                            "stem": f["problem"], "answer": f["answer"], "difficulty": 3, "marks": 2}
                    if (act := self._questions(b, idx, [item], phase="faded")):
                        return act
            if phase == "check":
                it = self._pick(kc, 0.7)
                if it and (act := self._questions(b, idx, [it], phase="check", unassisted=b["misses"] == 0)):
                    act["say"] = "Check: no hints on this one." if b["misses"] == 0 else "One more try at this idea."
                    return act
            if phase == "fix":
                mis = b.pop("fix_mis", None)
                if mis:
                    act = {"activity": "refute", "block_idx": idx, "kc": kc, "misconceptions": [mis],
                           "card": policy.METHOD_CARDS["refutation"]}
                    if (log := self._lesson_log()):
                        log.tutor(f"**Trap:** {mis['statement']}\n\n{mis.get('refutation', '')}\n\n"
                                  f"{mis.get('contrast', '')}", title="Fixing the trap")
                    return self._await(act)
                if self.packs.worked_for(kc) and "worked" not in b["phases"][:b["i"] - 1]:
                    b["phases"].insert(b["i"], "worked")
                    continue
                return self._explain(idx, kc, "Let's look at that again", card["establish"], part="fix")
            if phase == "stuck":
                return self._await({"activity": "stuck", "block_idx": idx, "kc": kc, "title": title,
                                    "say": "This idea hasn't clicked yet. It is saved as a gap and will come back. "
                                           "Talk it through with the tutor now, or move on."})
            if phase == "own_words":
                return self._await({"activity": "own_words", "block_idx": idx, "kc": kc, "title": title,
                                    "prompt": card.get("self_explain") or f"In your own words: {title.lower()}?"})
            if phase == "done":
                self._node_done(b)
        return None

    def _explain(self, idx: int, kc: str, title: str, text: str, part: str) -> dict:
        if (log := self._lesson_log()):
            log.tutor(text, title=title)
        return self._await({"activity": "explain", "block_idx": idx, "kc": kc, "part": part, "title": title,
                            "text": text})

    def _node_check_result(self, b: dict, g: dict, fb: dict, your: str) -> None:
        """Called from _record for a node's check: a miss adds a fix step and one more check; a second miss is a gap."""
        if g["correct"]:
            return
        b["misses"] += 1
        mis = fb.get("misconception")
        b["mistakes"].append(f"Trap: {mis['statement']}. {mis.get('refutation', '')}" if mis else
                             f"Didn't know yet: {fb.get('answer', '')}." if your == "?" else
                             f"You said {your}; correct: {fb.get('answer', '')}.")
        if b["misses"] == 1:
            b["fix_mis"] = mis
            b["phases"][b["i"]:b["i"]] = ["fix", "check"]
        else:
            self.log({"type": "gaps", "add": [b["kc"]]})
            b["stuck"] = True
            b["phases"][b["i"]:b["i"]] = ["stuck"]

    def _node_done(self, b: dict) -> None:
        kc = b["kc"]
        sub = self.packs.kcs[kc]["subtopic"]
        views.notes_update(self.vault.root, self.packs, self.state, sub,
                           node={"kc": kc, "note": b["card"].get("note", ""), "own_words": b.get("own_words"),
                                 "mistakes": b.get("mistakes")})
        self.log({"type": "node_done", "kc": kc, "method": b.get("method"), "misses": b.get("misses", 0),
                  "stuck": bool(b.get("stuck"))})
        if kc not in self.session["kcs_learned"]:
            self.session["kcs_learned"].append(kc)
