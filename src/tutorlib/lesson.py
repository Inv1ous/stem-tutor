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

from .card_diagrams import diagram_descriptions

from typing import TYPE_CHECKING, Any

from . import faded, policy, views
from .store import read_json

GOALS = {
    "scratch": "Learn it properly from scratch",
    "gaps": "I've had lessons: find and fill my gaps",
    "test": "Revise for a test soon",
    "quick": "Just the key ideas, quickly",
}


def term_id(kc: str, term: str) -> str:
    """Stable within a syllabus point; changing a definition does not reset its schedule."""
    import hashlib
    import unicodedata

    name = " ".join(unicodedata.normalize("NFKC", term).casefold().split())
    return "term:" + hashlib.sha256((kc + "\0" + name).encode()).hexdigest()[:24]


def misconception_text(m: dict) -> str:
    return (f"**The idea:** {m['idea']}\n\n**Why it is tempting:** {m['temptation']}\n\n"
            f"**The fix:** {m['fix']}")


def overview_figure(card: dict) -> dict:
    """Only an explicit concept figure can accompany an introduction, never a form's solution figure."""
    form_figures = {form.get('diagram') for form in card.get('forms') or [] if isinstance(form, dict)}
    descriptions = diagram_descriptions(card)
    for index, reference in enumerate(card.get('diagrams') or []):
        if isinstance(reference, str) and reference not in form_figures:
            return {'diagram': reference,
                    'diagram_description': descriptions[index] if index < len(descriptions) else 'Lesson diagram.'}
    return {}


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
    card = (pack.get("teach") or {}).get(kc) or _cached_card(tutor, kc)
    if card:
        return {**card, "source": card.get("source", "pack")}
    return offline_card(tutor.packs, kc)


def cached_card_data(vault_root, kc: str) -> dict | None:
    """Read a complete cached card for both lesson presentation and recall planning."""
    try:
        card = read_json(vault_root / ".tutor" / "cache" / "teach" / f"{kc}.json")
    except (ValueError, OSError):
        return None
    whole = isinstance(card, dict) and all(isinstance(card.get(f), str) for f in ("motivate", "establish", "note"))
    return card if whole else None


def _cached_card(tutor, kc: str) -> dict | None:
    """Use a cached AI card only when it is complete."""
    card = cached_card_data(tutor.vault.root, kc)
    return _visual_card(tutor, {**card, "source": "ai"}) if card else None


def _visual_card(tutor, card: dict) -> dict:
    """Copy only AI-written teaching prose at consumption; cached machine fields stay exact."""
    if card.get("source") != "ai":
        return card
    changed = {field: tutor.ai_visual(card[field])
               for field in ("motivate", "establish", "connect", "note", "self_explain")
               if isinstance(card.get(field), str)}
    return {**card, **changed} if any(card[field] != text for field, text in changed.items()) else card


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
        ai_visual: Any

        def _save(self) -> None: ...
        def _set_now(self, activity: dict | None = None) -> None: ...
        def _lesson_log(self) -> views.LessonLog | None: ...
        def _questions(self, block: dict, idx: int, items: list[dict], phase: str | None = None,
                       unassisted: bool = False, exp: str | None = None) -> dict | None: ...
        def _pick(self, kc: str, target: float, kinds: tuple = ...) -> dict | None: ...
        def log(self, event: dict) -> dict: ...
        def _fold(self) -> dict: ...

    # ---------------- waiting for the learner (not graded) ----------------
    def _await(self, activity: dict) -> dict:
        guards = getattr(self, 'marking_guards', None)
        guarded = (guards() if callable(guards) else self.session.get('skipped_answer_guards')) if activity.get('diagram') else None
        if activity.get("diagram") and guarded:
            # Images cannot be checked by the text answer guard. Do not retain the
            # image or its description in the saved activity or Obsidian thread.
            activity = {k: v for k, v in activity.items() if k not in ("diagram", "diagram_description")}
            if str(activity.get("part", "")).startswith("diagram:"):
                activity["text"] = "The diagram is withheld while a skipped answer is protected."
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
        if kind in ("worked", "walkthrough") and data.get("step") is not None and not data.get("done"):
            i = int(data["step"])
            act["revealed"] = max(act.get("revealed", 0), i)
            if (log := self._lesson_log()) and 1 <= i <= len(act["steps"]):  # Now redraws the example with it
                log.card(*views.activity_cards(act)[i])
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
            if s.get("goal") == "test" or not teach:  # nothing to teach: a harder mixed check instead
                new.append({"kind": "practice", "kcs": act["nodes_all"], "target": 0.8 if teach else 0.5})
            if teach:
                new.append({"kind": "exit", "kcs": teach[:3]})
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

    def _note_session(self) -> dict | None:
        """What a subtopic note records about this session: one dated section, updated in place on every write."""
        s = self.session or {}
        if not s.get("id"):
            return None
        return {"id": s["id"], "started": s.get("started"), "mode": s.get("mode"),
                "log": views.lesson_rel(self.vault.root, s["log"]) if s.get("log") else None}

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
        return self._await(act)

    def _step_node(self, b: dict, idx: int) -> dict | None:
        kc = b["kc"]
        s = self.session
        if "phases" not in b:
            card = teach_card(self, kc)
            # A teaching card may explicitly identify questions its material answers.
            # Keep them out of subsequent checks, even if no other item is available.
            disclosed = card.get('disclosed_item_ids') or []
            if isinstance(disclosed, list):
                used = s.setdefault('disclosed_item_ids', [])
                used.extend(item for item in disclosed if isinstance(item, str) and item not in used)
            quick = s.get("goal") == "quick"
            fresh = self.state["kcs"].get(kc, {}).get("n", 0) == 0
            if quick:  # the quick path can't deliver every method, so it never joins an experiment
                method, assignment = policy.default_method(self.packs.kc(kc), self.state["kcs"].get(kc, {}), fresh), None
            else:
                method, assignment = policy.choose_method(self.state, self.packs, kc, self.rng, fresh)
            self.log({"type": "method", "kc": kc, "method": method, "exp": assignment and assignment["exp"]})
            if assignment:
                self.log({"type": "exp_assign", **assignment})
            socratic = bool(card.get("guided_discover") or card.get("discover")) and not quick and method != "refutation"
            worked = bool(self.packs.worked_for(kc)) and method in ("worked_faded", "pretest_explain") and not quick
            form_steps = [step for i, form in enumerate(card.get("forms") or []) if form.get("rubric")
                          for step in (f"form_example:{i}", f"form_check:{i}")] if not quick else []
            form_diagrams = {f["diagram"] for f in card.get("forms") or []
                             if isinstance(f, dict) and isinstance(f.get("diagram"), str)} if not quick else set()
            intro_figure = overview_figure(card)
            diagram_steps = [f"diagram:{i}" for i, path in enumerate(card.get("diagrams") or [])
                             if path not in form_diagrams and path != intro_figure.get('diagram')]
            misconception_steps = [f"misconception:{i}" for i, _ in enumerate(card.get("misconceptions") or [])] if not quick else []
            b.update(card=card, intro_figure=intro_figure, method=method, i=0, misses=0, mistakes=[], phases=(
                ["motivate"] + (["challenge"] if method == "problem_first" and not quick else [])
                + (["discover"] if socratic else []) + (["terms"] if card.get("terms") else [])
                + (["plain_words"] if card.get("plain_words") else ["establish"])
                + (["exam_language"] if card.get("exam_language") else []) + diagram_steps + (["worked"] if worked else [])
                + (["faded"] if worked and method == "worked_faded" else []) + misconception_steps + form_steps + ["check"]
                + ([] if quick else ["own_words"]) + ["done"]))
            if (sub := self.packs.kcs[kc]["subtopic"]):
                views.notes_update(self.vault.root, self.packs, self.state, sub, current=kc,
                                   session=self._note_session())
        if s.get('skipped_answer_guards'):
            return self._await({'activity': 'explain', 'block_idx': idx, 'kc': kc, 'part': 'guard_pause',
                                'title': 'Try the skipped question',
                                'text': 'Press ctrl+u for retry options before continuing. If the question cannot be '
                                        'retried, its source or prerequisites need review.'})
        card = b["card"] = _visual_card(self, b["card"])
        title = self.packs.kcs[kc]["title"]
        ai_source = card.get("source") == "ai"
        while b["i"] < len(b["phases"]):
            phase = b["phases"][b["i"]]
            if phase == "done":
                self._node_done(b, idx)
                b["i"] += 1
                continue
            b["i"] += 1
            if phase == "motivate":
                return self._explain(idx, kc, "Why this matters", card["motivate"], part="motivate", ai_source=ai_source)
            if phase == "challenge":  # problem-first: attempt a harder question before being taught
                it = self._pick(kc, 0.3)
                if it and (act := self._questions(b, idx, [it], phase="challenge", unassisted=True)):
                    act["say"] = "Try this before being taught: any approach counts, and struggling here helps."
                    return act
            if phase == "discover":
                d = card.get("guided_discover") or card["discover"]
                suffix = "guided-discover" if card.get("guided_discover") else "discover"
                item = {"id": f"{kc}-{suffix}", "kcs": [kc], "kind": "mcq", "stem": d["stem"], "options": d["options"],
                        "answer": d["answer"], "explanation": d.get("explanation"), "difficulty": 3, "marks": 1}
                act = self._questions(b, idx, [item], phase="discover")
                if act:
                    act["say"] = "Have a go before being told: what would you expect?"
                    return act
            if phase == "terms":
                lines = []
                for term in card.get("terms", []):
                    self.log({"type": "term_introduced", "term_id": term_id(kc, term.get("term", "")), "kc": kc})
                    notation = term.get("notation", "")
                    spoken = term.get("spoken", "")
                    detail = f" — {term.get('meaning', '')}"
                    if notation and notation.lower() != "none":
                        detail += f" Notation: {notation}."
                    if spoken:
                        detail += f" Read: {spoken}."
                    lines.append(f"- **{term.get('term', '')}**{detail}")
                if lines:
                    return self._explain(idx, kc, "Helpful terms", "\n".join(lines), part="terms", ai_source=ai_source)
            if phase == "plain_words":
                detail = card.get("establish", "") + ("\n\n**How it connects:** " + card["connect"] if card.get("connect") else "")
                return self._await({"activity": "explain", "block_idx": idx, "kc": kc, "part": "plain_words",
                                    "title": "In plain words", "text": card["plain_words"], "detail": detail,
                                    **b.get('intro_figure', {}),
                                    **({"ai_source": True} if ai_source else {})})
            if phase == "exam_language":
                lines = [f"- **{entry['name']}:** {entry['meaning']}" for entry in card.get("exam_language", [])]
                if lines:
                    return self._explain(idx, kc, "Exam language", "\n".join(lines), part=phase, ai_source=ai_source)
            if phase.startswith("diagram:"):
                number = int(phase.split(":", 1)[1])
                descriptions = diagram_descriptions(card)
                description = descriptions[number] if number < len(descriptions) else "See the diagram in Obsidian."
                return self._await({"activity": "explain", "block_idx": idx, "kc": kc, "part": phase,
                                    "title": "Diagram", "text": description, "diagram": card["diagrams"][number]})
            if phase.startswith("misconception:"):
                number = int(phase.split(":", 1)[1])
                misconception = card["misconceptions"][number]
                return self._explain(idx, kc, "Common misconception", misconception_text(misconception),
                                     part=phase, ai_source=ai_source)
            if phase.startswith("form_example:"):
                form = card["forms"][int(phase.split(":", 1)[1])]
                wordings = "\n\n".join(f"- {wording}" for wording in form.get("wordings", []))
                text = ((f"**Question wordings:**\n\n{wordings}\n\n" if wordings else "")
                        + f"**Worked example:**\n\n{form['example']}")
                diagram = form.get("diagram")
                if diagram and diagram in (card.get("diagrams") or []):
                    index = card["diagrams"].index(diagram)
                    descriptions = diagram_descriptions(card)
                    description = descriptions[index] if index < len(descriptions) else ""
                    return self._await({"activity": "explain", "block_idx": idx, "kc": kc, "part": "form_example",
                                        "title": form["name"], "text": text, "diagram": diagram,
                                        "diagram_description": description,
                                        **({"ai_source": True} if ai_source else {})})
                return self._explain(idx, kc, form["name"], text, part="form_example", ai_source=ai_source)
            if phase.startswith(("form_check:", "form_retry:")):
                number = int(phase.split(":", 1)[1])
                form = card["forms"][number]
                retry = phase.startswith("form_retry:")
                check = form["retry"] if retry else form
                item = {"id": f"{kc}-form-{number + 1}" + ("-retry" if retry else ""),
                        "kcs": [kc], "kind": "short", "difficulty": 3,
                        "stem": check["check"], "rubric": check["rubric"], "marks": len(check["rubric"]),
                        "review_answer": check.get("answer", ""), "form_index": number}
                rule = check.get('review_rule', form.get('review_rule'))
                if rule:
                    item['review_rule'] = rule
                if act := self._questions(b, idx, [item], phase="form_check", unassisted=True):
                    act["say"] = "Try this form without hints."
                    return act
            if phase == "establish":
                text = card["establish"] + ("\n\n**How it connects:** " + card["connect"] if card.get("connect") else "")
                return self._explain(idx, kc, title, text, part="establish", ai_source=ai_source,
                                     figure=b.get('intro_figure'))
            if phase == "worked":
                wk = self.packs.worked_for(kc)[0]
                act = {"activity": "worked", "block": "node", "kc": kc, "problem": wk["problem"], "steps": wk["steps"],
                       "block_idx": idx, "say": "Predict each step before you reveal it."}
                return self._await(act)
            if phase == "faded":
                wk = self.packs.worked_for(kc)[0]
                if wk.get("faded"):
                    f = wk["faded"]
                    item = faded.question_item(f, kc)
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
                    matched = next((m for m in card.get("misconceptions", []) if m.get("id") == mis.get("id")
                                    and m.get("id")), None)
                    if matched:
                        return self._explain(idx, kc, "Let's look at that again", misconception_text(matched),
                                             part="fix", ai_source=ai_source)
                    act = {"activity": "refute", "block_idx": idx, "kc": kc, "misconceptions": [mis],
                           "card": policy.METHOD_CARDS["refutation"]}
                    return self._await(act)
                form_index = b.pop("fix_form", None)
                forms = card.get("forms") or []
                if type(form_index) is int and 0 <= form_index < len(forms):
                    form = forms[form_index]
                    if isinstance(form, dict) and isinstance(form.get("example"), str):
                        diagram = form.get("diagram")
                        if diagram and diagram in (card.get("diagrams") or []):
                            index = card["diagrams"].index(diagram)
                            descriptions = diagram_descriptions(card)
                            description = descriptions[index] if index < len(descriptions) else ""
                            return self._await({"activity": "explain", "block_idx": idx, "kc": kc, "part": "fix",
                                                "title": "Let's revisit this form", "text": form["example"],
                                                "diagram": diagram, "diagram_description": description,
                                                **({"ai_source": True} if ai_source else {})})
                        return self._explain(idx, kc, "Let's revisit this form", form["example"],
                                             part="fix", ai_source=ai_source)
                if self.packs.worked_for(kc) and "worked" not in b["phases"][:b["i"] - 1]:
                    b["phases"].insert(b["i"], "worked")
                    continue
                return self._explain(idx, kc, "Let's look at that again", card["establish"], part="fix", ai_source=ai_source)
            if phase == "stuck":
                return self._await({"activity": "stuck", "block_idx": idx, "kc": kc, "title": title,
                                    "say": "This idea hasn't clicked yet. It is saved as a gap and will come back. "
                                           "Talk it through with the tutor now, or move on."})
            if phase == "own_words":
                return self._await({"activity": "own_words", "block_idx": idx, "kc": kc, "title": title,
                                    "prompt": card.get("self_explain") or f"In your own words: {title.lower()}?",
                                    **({"ai_source": True} if ai_source and card.get("self_explain") else {})})
        return None

    def _explain(self, idx: int, kc: str, title: str, text: str, part: str, *, ai_source: bool = False,
                 figure: dict | None = None) -> dict:
        return self._await({"activity": "explain", "block_idx": idx, "kc": kc, "part": part, "title": title,
                            "text": text, **(figure or {}), **({"ai_source": True} if ai_source else {})})

    def _node_check_result(self, b: dict, g: dict, fb: dict, your: str) -> None:
        """Called from _record for a node's check: a miss adds a fix step and one more check; a second miss is a gap."""
        if g["correct"]:
            return
        b["misses"] += 1
        mis = fb.get("misconception")
        b["mistakes"].append(f"You said {your}. Reviewed mark points: {fb['explanation']}" if
                             fb.get("phase") == "form_check" and fb.get("explanation") else
                             f"Trap: {mis['statement']}. {mis.get('refutation', '')}" if mis else
                             f"Didn't know yet: {fb.get('answer', '')}." if your == "?" else
                             f"You said {your}; correct: {fb.get('answer', '')}.")
        form_index = fb.get("form_index")
        new_form = (fb.get("phase") == "form_check" and type(form_index) is int
                    and form_index not in b.get("form_repairs", []))
        if b["misses"] == 1 or new_form:
            if new_form:
                b.setdefault("form_repairs", []).append(form_index)
            b["fix_mis"] = mis
            if not mis and fb.get("phase") == "form_check" and your != "?" and type(fb.get("form_index")) is int:
                b["fix_form"] = fb["form_index"]
            forms = b.get("card", {}).get("forms") or []
            form = forms[form_index] if type(form_index) is int and 0 <= form_index < len(forms) else {}
            retry = form.get("retry") if isinstance(form, dict) else None
            if (new_form and isinstance(retry, dict) and isinstance(retry.get("check"), str)
                    and retry["check"].strip() and retry["check"] != form.get("check")
                    and isinstance(retry.get("answer"), str) and retry["answer"].strip()
                    and isinstance(retry.get("rubric"), list) and retry["rubric"]):
                followup = f"form_retry:{form_index}"
            else:
                followup = "check"
            b["phases"][b["i"]:b["i"]] = ["fix", followup]
        else:
            self.log({"type": "gaps", "add": [b["kc"]]})
            b["stuck"] = True
            b["phases"][b["i"]:b["i"]] = ["stuck"]

    def _node_done(self, b: dict, idx: int | None = None) -> None:
        kc = b["kc"]
        if idx is None:
            idx = next((i for i, block in enumerate(self.session.get("blocks", [])) if block is b), None)
        done = (next((event for event in self.vault.events() if event["type"] == "node_done"
                      and event.get("session") == self.session["id"] and event.get("node") == idx
                      and event.get("kc") == kc), None) if idx is not None else None)
        if done is not None:
            # A completion may have reached the log before its session save returned.
            # Its note binding is already durable; preserve it and finish only the cache transition.
            self.state = self._fold()
            self._dirty = True
            if not done.get("stuck") and kc not in self.session["kcs_learned"]:
                self.session["kcs_learned"].append(kc)
            return
        sub = self.packs.kcs[kc]["subtopic"]
        node = {"kc": kc, "note": b["card"].get("note", ""), "own_words": b.get("own_words"),
                "mistakes": b.get("mistakes")}
        guards = self.session.get("skipped_answer_guards") or {}
        if guards:
            import hashlib
            import json
            from . import deferred_notes
            content = json.dumps([self.session["id"], sub, node, guards], sort_keys=True, ensure_ascii=False)
            ident = hashlib.sha256(content.encode('utf-8')).hexdigest()
            deferred_notes.defer(self.vault.tutor / 'state' / 'deferred-notes.json', ident, sub, node, guards)
        else:
            views.notes_update(self.vault.root, self.packs, self.state, sub, node=node,
                               session=self._note_session())
        self.log({"type": "node_done", "session": self.session["id"], **({"node": idx} if idx is not None else {}),
                  "kc": kc, "method": b.get("method"), "misses": b.get("misses", 0),
                  "stuck": bool(b.get("stuck"))})
        if not b.get("stuck") and kc not in self.session["kcs_learned"]:
            self.session["kcs_learned"].append(kc)
