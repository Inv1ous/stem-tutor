"""The Tutor: runs a study session as a sequence of blocks and keeps answer keys out of the model's view.

The model only ever sees what `next()` returns (stems/options, never keys) and what `answer()`
returns after an attempt. Every graded attempt becomes an event; state is a fold over events.
"""
from __future__ import annotations

import copy
import math
import random
import re
import time
import uuid
from collections.abc import Callable
from datetime import datetime

from . import almanac, diagnose, faded, grade, mermaid_refresh, model, policy, question_display, solvability, topicals, topical_selection, views
from . import prompts as engine_prompts
from .source_questions import SourceQuestions, drop_repeated, servable as source_servable, to_instance as source_instance
from .clock import StudyClock, fmt
from .lesson import LessonMixin
from .packs import DamagedContent, Packs, instantiate
from .store import Vault, read_json, write_json

PUBLIC = ("kind", "stem", "options", "marks", "command_word", "image", "images")
GENERIC_HINTS = [
    "Re-read the command word and underline what is given and what is asked.",
    "Which principle or equation links the given quantities to the unknown?",
    "Write the first line of working; check units before substituting.",
]


def _guard_identity(p: dict) -> str:
    import hashlib
    import json
    inst = p['inst']
    instance = json.dumps([p['item'], inst.get('stem'), inst.get('options'), inst.get('answer'),
                           inst.get('params')], sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(instance.encode()).hexdigest()


def _protected_guard(guard):
    if not isinstance(guard, dict) or not isinstance(guard.get('question'), dict):
        return None
    result = copy.deepcopy(guard)
    result['question'].pop('saved_work', None)
    return result


def _question_excerpt(value: object) -> str:
    text = ' '.join(str(value or '').split())
    return text if len(text) <= 90 else text[:89].rstrip() + '…'


def _has_deferred_judgment(s: dict) -> bool:
    return bool(s.get('deferred_judgments') or any(
        p.get('block') == 'deferred_judgment'
        for bucket in ('presented', 'queue') for p in (s.get(bucket) or {}).values()))


def whole_attempt_kind(working: str) -> str:
    """Classify attempt text without treating paper placeholders as confirmation."""
    if not isinstance(working, str):
        return 'none'
    text = working.strip().casefold().replace('’', "'").strip('?.! ')
    if text in ('', 'idk', 'dunno', "i don't know", 'i dont know', 'i do not know', 'skip',
                'no', 'not sure', 'i have no idea', 'i have no clue', 'i am unsure', "i'm unsure",
                'i cannot answer', "i can't answer", 'i cant answer'):
        return 'none'
    if text in ('done on paper', 'on paper', 'written on paper'):
        return 'paper'
    if re.fullmatch(r'(?:\d+\s*)?pts\s*=\s*[\d,\s]*', text):
        return 'none'
    return 'typed'


class Tutor(LessonMixin):
    def __init__(self, vault: Vault, rng: random.Random | None = None, now=None, one_at_a_time: bool = False,
                 ai_visual: Callable[[str], str] | None = None):
        self.vault = vault
        # Optional MermaidRefresher: the app and the command line attach one so that concept-map colours follow
        # mastery outside lessons too (see enable_map_refresh).
        self.mermaid: mermaid_refresh.MermaidRefresher | None = None
        self.view_warnings: dict[str, views.ReadOnlyViewDestination] = {}
        self.ai_visual = ai_visual or (lambda text: text)
        self.one_at_a_time = one_at_a_time  # the terminal app shows a batch one question at a time; the chat shows it whole
        self.packs = Packs(vault)
        self.rng = rng or random.Random()
        self._now = now or vault.now
        self.state_path = vault.tutor / "state" / "learner.json"
        self.session_path = vault.tutor / "state" / "session.json"
        self.state = self._read_state(self.state_path)
        upgraded_cache = bool(self.state and self.state.get("model_version") != model.MODEL_VERSION)
        if (not self.state or self.state.get("model_version") != model.MODEL_VERSION
                or self.state.get("last_event") != vault.last_event_id()
                or self.state.get("conflict_copies", {}) != vault.conflict_copies()):
            # a new model version, or the log moved on after this state was saved (the app stopped between the
            # two writes), or a sync copy brought older events: recompute everything from your history
            self.state = self._fold()
            self._dirty = True
        self.study_clock = StudyClock(vault)  # time spent studying: the app counts it, `end` reports it
        self._last_mark: dict | None = None  # the answer just marked and the session before it: see regrade
        self.session = self._read_state(self.session_path)
        # In-flight AI marking tickets are intentionally process-local: they
        # retain object identity for stale-response checks without changing the
        # persisted learner/session schema.
        self._marking_tickets: dict[str, dict] = {}
        # Injectable one-shot AI used only to name the topics of an untagged question (see check_solvable):
        # topic_ai(request: dict) -> str | dict | None; None/raise = AI unavailable.  Synchronous.
        self.topic_ai: Callable[[dict], object] | None = None
        self._source_questions: SourceQuestions | None = None
        self._recover()
        if upgraded_cache and self._dirty:
            self._save()  # persist this one-time version refold even if no learner action follows startup
        self._flush_deferred_notes()
        self.read_almanac()

    @staticmethod
    def _read_state(path):
        try:
            return read_json(path)
        except ValueError:  # a torn file: the state is rebuilt from the log, a torn session is dropped
            return None

    def _recover(self) -> None:
        """An answer is logged before the session is saved. If the app stopped in between, the question is still
        open here though the log holds its answer: close it, so it is not asked and recorded a second time, and do
        to the session what marking it did (a sweep's result, a relearn, a node's check), as a re-mark redoes it."""
        s = self.session
        if not s:
            return
        events = list(self.vault.events())
        # The end event can be saved before the active session is cleared.
        if self._recover_ended_session(events) is not None:
            return
        for e in events:
            if (e.get('type') == 'ungraded_retry' and e.get('session') == s['id']
                    and e.get('id') not in s.get('ungraded_retry_events', [])):
                p = s.get('presented', {}).get(str(e.get('n')))
                if p and p.get('item') == e.get('item') and _guard_identity(p) == e.get('guard'):
                    self._defer_retry_attempt(str(e['n']), p, e['response'], event=e)
            if e.get('type') == 'postponed_judgment' and e.get('session') == s['id']:
                archived = e.get('question') or {}
                pending = s.get('deferred_judgments') or []
                for i, candidate in enumerate(pending):
                    if (archived.get('judgment_id') and candidate.get('judgment_id') == archived['judgment_id']):
                        pending.pop(i)
                        self._save()
                        break
        # A logged answer takes precedence over a later exclusion: it must not
        # be requeued and graded twice after an interrupted session save.
        done = []
        for e in events:
            n = str(e.get("n"))
            if e["type"] in ("answer", "source_answer") and e.get("session") == s["id"] and s.get("presented", {}).get(n, {}).get("item") == e["item"]:
                p = s["presented"][n]
                kind = "idk" if e["response"] == "don't know" else _expected_kind(p["inst"]["kind"])[0]
                done.append(self._mark(n, p, {"kind": kind, "value": e["response"], "conf": e.get("conf")},
                                       {**e["grade"], "needs_judgement": False}, redo=e,
                                       reviewed_explanation=e.get('reviewed_explanation')))
        if done:
            s["thread"] = (s.get("thread") or []) + [self._feedback_item(fb, fb["your"]) for fb in done]
            s["now"] = {"activity": "feedback"}
            self._save()
            self._sync_almanac(force=True)
        # A draft cancellation saves the session before updating the durable guard store.
        # Reconcile that draft before an exclusion can remove the open retry.
        self._resume_faded_cancellation()
        self._sync_guard_drafts()
        # The exclusion event can outlive the session write, just as an answer can.
        excluded = {(e["identity"], e["chapter"]) for e in self.state.get("topical_exclusions", [])}
        removed = False
        for bucket in ("presented", "queue"):
            for n, p in list(s.get(bucket, {}).items()):
                if bucket == 'presented' and n == (s.get('faded_cancel_intent') or {}).get('n'):
                    continue  # recovery needs this exact open draft until its store commit succeeds
                chapter = p.get("serving_chapter") or self.packs.kcs.get(p["kcs"][0], {}).get("subtopic")
                if (topicals.identity(p["inst"]) or p["item"], chapter) in excluded:
                    if p.get('pending_saved_mark'):
                        self._remember_pending_node(p)
                        p.update(block='deferred_judgment', block_idx=None, exp=None)
                        s.setdefault('deferred_judgments', []).append(p)
                    elif p.get('block') == 'deferred_judgment':
                        s.setdefault('deferred_judgments', []).append(p)
                    del s[bucket][n]
                    removed = True
        if self._reconcile_correction_totals(events) or removed:
            self._save()

    def _reconcile_correction_totals(self, events) -> bool:
        """Bring only the current session's corrected summary in line with durable grades."""
        s = self.session
        if not s:
            return False
        answers = [e for e in events if e["type"] == "answer" and e.get("session") == s["id"]]
        if not any(e.get("regraded") for e in answers):
            return False
        earned = 0
        for answer in answers:
            earned = round(earned + answer["grade"]["score"] * answer.get("marks", 0), 2)
        totals = {"correct": sum(model.counts_as_right(e["grade"]) for e in answers), "marks_earned": earned}
        changed = any(s.get(key) != value for key, value in totals.items())
        s.update(totals)
        return changed

    def _recover_ended_session(self, events) -> dict | None:
        """Close a stale live session from its durable end, without appending another."""
        s = self.session
        if not s:
            return None
        ended = next((e for e in events if e.get("type") == "session_end" and e.get("session") == s["id"]), None)
        if ended is None:
            return None
        self.session = None
        self._save()
        return {key: value for key, value in ended.items() if key not in ("id", "ts", "type", "_answer_days")}

    def refresh_content(self) -> list[str]:
        """Between sessions, switch to newly published content: returns the titles of chapters that arrived."""
        if self.session:
            return []
        try:
            if (self.packs.pointer_base / "CURRENT").read_text().strip() == self.packs.root.name:
                return []
            before = self.packs.published()
            self.packs = Packs(self.vault)
        except (DamagedContent, OSError, UnicodeError):  # keep loaded content and retry a transient pointer failure
            return []
        self.read_almanac()
        return [self.packs.subtopics[s]["title"] for s in sorted(self.packs.published() - before)
                if s in self.packs.subtopics]

    def ticks(self) -> frozenset[str]:
        """Objectives that count as done: ticked by the learner in the Almanac (its newest progress file in the
        vault's Almanac folder), or earned here by what their answers show."""
        return almanac.ticks(self.vault.root) | policy.earned(self.packs.plan, self.state, self.packs)

    def read_almanac(self) -> None:
        """Take from the Almanac what only it knows: the exam dates entered in its statement of entry."""
        almanac.apply_dates(self.packs.plan, almanac.exam_dates(self.vault.root), self.packs.plan_dates)

    # ---------- persistence ----------
    def _sync_guard_drafts(self) -> None:
        from . import deferred_notes
        if (self.session or {}).get('faded_cancel_intent'):
            return  # never overwrite a conflicting durable guard during recovery
        for ident, guard in ((self.session or {}).get('skipped_answer_guards') or {}).items():
            question = guard.get('question') if isinstance(guard, dict) else None
            if isinstance(question, dict) and 'saved_work' in question:
                path = self.vault.tutor / 'state' / 'deferred-notes.json'
                if (question.get('inst') or {}).get('written_faded'):
                    deferred_notes.reconcile_written_draft(path, ident, guard)
                else:
                    deferred_notes.hold(path, ident, guard)

    def _written_guard_conflict(self) -> bool:
        from . import deferred_notes
        path = self.vault.tutor / 'state' / 'deferred-notes.json'
        try:
            for ident, guard in ((self.session or {}).get('skipped_answer_guards') or {}).items():
                question = guard.get('question') if isinstance(guard, dict) else None
                if isinstance(question, dict) and (question.get('inst') or {}).get('written_faded'):
                    snapshot = deferred_notes.guard_snapshot(path, ident)
                    if not snapshot or snapshot['guard'] != guard:
                        return True
            return False
        except (OSError, ValueError, TypeError):
            return True

    def _resume_faded_cancellation(self) -> bool:
        """Replay one persisted cancellation; conflicts retain the open draft."""
        from . import deferred_notes
        s = self.session or {}
        op = s.get('faded_cancel_intent')
        if not op:
            return True
        try:
            p = (s.get('presented') or {}).get(op['n'])
            guard = (s.get('skipped_answer_guards') or {}).get(op['ident'])
            if (not p or not guard or _guard_identity(p) != op['ident']
                    or _protected_guard(guard) is None
                    or _protected_guard(guard) != _protected_guard(op['expected'])
                    or _protected_guard(guard) != _protected_guard(op['proposed'])
                    or p.get('saved_work') != op['proposed']['question'].get('saved_work')
                    or (guard.get('question') or {}).get('inst') != p.get('inst')
                    or (guard.get('question') or {}).get('saved_work') not in
                       ((op['expected'].get('question') or {}).get('saved_work'),
                        (op['proposed'].get('question') or {}).get('saved_work'))):
                return False
            status = deferred_notes.cancel_draft(self.vault.tutor / 'state' / 'deferred-notes.json',
                                                 op['operation'], op['ident'], op['expected'],
                                                 op['proposed'], op['revision'])
            if status not in ('applied', 'already_applied'):
                if op.get('conflict_recorded'):
                    path = self.vault.tutor / 'state' / 'deferred-notes.json'
                    snapshot = deferred_notes.guard_snapshot(path, op['ident'])
                    previous = deferred_notes.read_draft_conflict(path, op['operation'])
                    if (snapshot and previous and snapshot['generation'] == op['generation']
                            and snapshot['revision'] != previous.get('revision')
                            and _protected_guard(snapshot['guard']) == _protected_guard(op['expected'])):
                        # Preserve the old archive and bind a new archive to the newer revision.
                        op['operation'] = uuid.uuid4().hex
                        op.pop('conflict_recorded', None)
                        self._save()
                archived = deferred_notes.record_draft_conflict(
                    self.vault.tutor / 'state' / 'deferred-notes.json', op['operation'], op['ident'],
                    op['expected'], op['proposed'], op['generation'])
                if archived in ('recorded', 'already_recorded'):
                    op['conflict_recorded'] = True
                    self._save()
                return False
            before = copy.deepcopy(s)
            s['skipped_answer_guards'][op['ident']] = copy.deepcopy(op['proposed'])
            s['presented'].pop(op['n'])
            s.pop('faded_cancel_intent')
            try:
                self._save()
            except (OSError, ValueError):
                s.clear()
                s.update(before)
                raise
            return True
        except (KeyError, TypeError, ValueError, OSError):
            return False

    def retry_faded_cancellation(self) -> dict:
        if not (self.session or {}).get('faded_cancel_intent'):
            return {'ok': False, 'error': 'No cancellation needs recovery.'}
        if self._resume_faded_cancellation():
            return {'ok': True}
        return {'ok': False, 'error': 'The saved draft is still open; the guard needs recovery.'}

    def faded_conflict_drafts(self) -> dict | None:
        """Offer private drafts only when no other question is protected or open."""
        from . import deferred_notes
        s = self.session or {}
        op = s.get('faded_cancel_intent') or {}
        ident = op.get('ident')
        p = (s.get('presented') or {}).get(op.get('n'))
        if (not op.get('conflict_recorded') or not p or s.get('queue') or s.get('suspended_for_retry')
                or len(s.get('presented') or {}) != 1 or set(s.get('skipped_answer_guards') or {}) != {ident}
                or _guard_identity(p) != ident):
            return None
        record = deferred_notes.current_draft_conflict(self.vault.tutor / 'state' / 'deferred-notes.json', op['operation'])
        if not record or record.get('guard') != ident or record.get('generation') != op.get('generation'):
            return None
        guards = [s['skipped_answer_guards'][ident], op.get('expected'), op.get('proposed'),
                  record.get('expected'), record.get('local'), record.get('stored')]
        reference = _protected_guard(guards[0])
        if (reference is None or any(_protected_guard(guard) != reference for guard in guards[1:])
                or reference['question'].get('inst') != p.get('inst')
                or record['expected'] != op.get('expected') or record['local'] != op.get('proposed')):
            return None
        return {'local': record['local']['question'].get('saved_work', ''),
                'stored': record['stored']['question'].get('saved_work', '')}

    def choose_faded_conflict_draft(self, choice: str, operation: str) -> dict:
        """Persist a choice as a new replayable operation; never discard the conflict archive."""
        from . import deferred_notes
        if (choice not in ('local', 'stored') or not isinstance(operation, str) or not operation
                or ((self.session or {}).get('faded_cancel_intent') or {}).get('operation') != operation
                or self.faded_conflict_drafts() is None):
            return {'ok': False, 'error': 'The conflict changed; no draft was selected.'}
        s = self.session
        op = s['faded_cancel_intent']
        session_work = s['skipped_answer_guards'][op['ident']]['question'].get('saved_work')
        if (session_work not in (op['expected']['question'].get('saved_work'),
                                 op['proposed']['question'].get('saved_work'))
                or s['presented'][op['n']].get('saved_work') != op['proposed']['question'].get('saved_work')):
            return {'ok': False, 'error': 'The open work changed; no draft was selected.'}
        path = self.vault.tutor / 'state' / 'deferred-notes.json'
        record = deferred_notes.current_draft_conflict(path, op['operation'])
        if (not record or record.get('guard') != op['ident'] or record.get('generation') != op['generation']
                or record.get('local') != op.get('proposed') or record.get('expected') != op.get('expected')):
            return {'ok': False, 'error': 'The conflict changed; no draft was selected.'}
        selected = copy.deepcopy(record[choice])
        before = copy.deepcopy(s)
        s['skipped_answer_guards'][op['ident']] = copy.deepcopy(record['stored'])
        s['presented'][op['n']]['saved_work'] = selected['question'].get('saved_work', '')
        s['faded_cancel_intent'] = {'n': op['n'], 'ident': op['ident'], 'operation': uuid.uuid4().hex,
                                     'expected': copy.deepcopy(record['stored']), 'proposed': selected,
                                     'revision': record['revision'], 'generation': record['generation']}
        try:
            self._save()
        except (OSError, ValueError):
            s.clear()
            s.update(before)
            return {'ok': False, 'error': 'The choice could not be saved; the drafts remain open.'}
        if self._resume_faded_cancellation():
            return {'ok': True}
        return {'ok': False, 'error': 'The choice was saved, but recovery still needs retrying.'}

    def _flush_deferred_notes(self) -> None:
        from . import deferred_notes
        path = self.vault.tutor / 'state' / 'deferred-notes.json'
        if not path.exists() or any((self.session or {}).get(key) for key in ('skipped_answer_guards', 'presented', 'queue', 'suspended_for_retry')):
            return
        if deferred_notes.outstanding(path):
            return
        for row in deferred_notes.ready(path):
            views.notes_update(self.vault.root, self.packs, self.state, row['subtopic'],
                               node=row['node'], deferred_id=row['id'])
            deferred_notes.acknowledge(path, row['id'])

    def now(self) -> datetime:
        return self._now()

    def _fold(self) -> dict:
        s = model.new_state()
        # Note copies before replay, so a sync arriving during replay is noticed again at the next start.
        if copies := self.vault.conflict_copies():
            s["conflict_copies"] = copies
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
        refresher = getattr(self, "mermaid", None)
        before = mermaid_refresh.snapshot(self.state) if refresher is not None else None
        e = self.vault.append_event(event, now=self.now())
        if e["type"] in ("regrade", "tag", "session_end"):
            # Corrections and ends can release after earlier raw records; save the exact derived fold.
            self.state = self._fold()
        else:
            model.apply(self.state, e)
        self._dirty = True
        self._save()
        if refresher is not None:
            try:  # any change of mastery recolours the maps of the changed subtopics (in the refresher's worker)
                refresher.changed(before, self.state)
            except Exception:  # noqa: BLE001 - a cosmetic redraw must never lose a recorded answer
                pass
        if event.get("type") in ("paper_result", "session_start"):
            self._sync_almanac(force=True)
        return e

    def _sync_almanac(self, force: bool = False) -> None:
        """Tell the Almanac what is happening as it happens (the page reads the file every half minute): the session
        under way, today's totals and each objective's progress. At most every ten seconds unless forced after a
        completed action; never raises, and writes nothing when the planner file is not on this machine."""
        try:
            now = time.monotonic()
            if not force and now - getattr(self, "_almanac_at", -99) < 10:
                return
            self._almanac_at = now
            from . import report
            report.almanac_push(self)
        except Exception:  # noqa: BLE001 - the Almanac is a courtesy; it never stops a lesson
            pass

    # ---------- Obsidian views ----------
    def enable_map_refresh(self, background: bool = True) -> mermaid_refresh.MermaidRefresher:
        """Recolour concept maps whenever mastery changes; `background` keeps the writes off the keypress path."""
        self.mermaid = mermaid_refresh.MermaidRefresher(
            self.vault.root, self.packs, background=background,
            active_log=lambda: (views.lesson_rel(self.vault.root, (self.session or {})["log"])
                                if (self.session or {}).get("log") else None))
        return self.mermaid

    def _lesson_log(self) -> views.LessonLog | None:
        rel = (self.session or {}).get("log")
        if not rel:
            return None
        log = views.LessonLog(self.vault.root, views.lesson_rel(self.vault.root, rel))
        try:
            log.admit()
        except views.ReadOnlyLessonDestination:
            self.session.setdefault("view_errors", {})["Lesson transcript"] = "Lesson transcript is read-only; progress saved."
            return None
        return log

    def _set_now(self, activity: dict | None = None) -> None:
        """A new question or step. Now shows what the terminal shows: everything since the terminal last cleared its
        log, which it does for a new question (answered from memory) and for "in your own words"."""
        s = self.session
        if s is None or not activity or activity.get("activity") == "feedback":
            return
        kind = activity["activity"]
        if kind in ("teach", "worked", "walkthrough", "refute", "own_words", "explain") and activity.get("kc"):
            self._start_chapter(self.packs.kcs.get(activity["kc"], {}).get("subtopic"))
        key = (f"{kind}:{activity.get('kc')}:{activity.get('part') or activity.get('title') or ''}:"
               f"{','.join(sorted(s.get('presented', {}), key=int))}")
        s["now"] = activity
        if key == s.get("thread_key"):  # the same step, moved on (a worked step revealed): its card grows
            for item in reversed(s.get("thread") or []):
                if item.get("kind") == "step":
                    item["act"] = activity
                    break
            return
        s["thread_key"] = key
        if kind in ("questions", "own_words"):
            s["thread"] = []
        if kind == "questions":  # the question was logged when it was opened
            s["thread"] += [{"kind": "question", "view": self._view(int(n))} for n in sorted(s["presented"], key=int)]
        elif views.activity_cards(activity):
            self._post({"kind": "step", "act": activity})

    CHAT_KEEP = 50

    def _post(self, item: dict) -> None:
        """A card for Now and the lesson log at once, so the two say what the terminal said."""
        s = self.session
        s["thread"] = (s.get("thread") or []) + [item]
        if (log := self._lesson_log()):
            log.add("\n\n".join(self._thread_blocks([item])))

    def show(self, kind: str, text: str, title: str = "", log: bool = True) -> None:
        """Put on Now, and in the lesson log, a card the terminal has just shown: an AI reply, what the learner typed, a
        hint, a notice. `kind` is the card's colour role (you, ai, hint, tutor, good, bad, note, notice). `log`: False
        when the log has it already. Outside a session (the free chat) they make up the page. Never raises."""
        try:
            if not (text or "").strip():
                return
            item = {"kind": kind, "title": title, "text": text.strip()}
            if self.session is None:
                self._chat = (getattr(self, "_chat", []) + [item])[-self.CHAT_KEEP:]
                self._write_now()
                return
            if log:
                self._post(item)
            else:
                self.session["thread"] = (self.session.get("thread") or []) + [item]
            self._save()
        except OSError:  # the Now page cannot be written: the terminal has it anyway
            pass

    def clear_chat(self) -> None:
        self._chat = []
        try:
            self._mirror_now(f"Chat · {self.now():%H:%M}", ["Type a question in the tutor to begin."])
        except OSError:  # as with chat replies, a failed mirror must not stop the terminal
            pass

    def _thread_blocks(self, items: list[dict]) -> list[str]:
        out = []
        tidy = self.ai_visual if (self.session or {}).get("mode") == "lesson" else (lambda text: text)  # as the terminal's
        for t in items:
            if t["kind"] == "question":
                out.append(views.question_block(t["view"]))
            elif t["kind"] == "step":
                out += [views.card_block(c[0], c[1], tidy(c[2])) for c in views.activity_cards(t["act"], obsidian=True)]
                if t["act"].get("activity") == "plan" and t["act"].get("map"):  # the map the terminal points to
                    out.append(t["act"]["map"])
            else:
                # Only an AI reply is AI visual text: engine cards (a marked answer, a hint, a notice) are logged
                # word for word, as the terminal drew them.
                out.append(views.card_block(t["kind"], t.get("title") or {"you": "You", "ai": "Tutor (AI)"}.get(t["kind"], ""),
                                            tidy(t["text"]) if t["kind"] == "ai" else t["text"]))
        return out

    def _mirror_now(self, header: str, blocks: list[str], notes: str | None = None) -> None:
        try:
            views.write_now(self.vault.root, header, blocks, notes)
        except views.ReadOnlyViewDestination as exc:
            self.view_warnings.setdefault("Now.md", exc)  # one warning until a successful mirror clears it
            if self.session is not None:
                self.session.setdefault("view_errors", {})["Now"] = str(exc)
        else:
            self.view_warnings.pop("Now.md", None)

    def _write_now(self) -> None:
        s = self.session
        if not s:
            chat = getattr(self, "_chat", [])
            if chat:
                self._mirror_now(f"Chat · {self.now():%H:%M}", self._thread_blocks(chat))
                return
            self._mirror_now(f"No session running · {self.now():%H:%M}",
                             ["Start the tutor to begin. Your last lessons are in the Lessons folder, a folder for each day."])
            return
        thread = s.get("thread") or []
        lead = []  # a page kept by an older version has no cards for the open question or the step: show them first
        if not any(t["kind"] == "step" for t in thread) and views.activity_cards(s.get("now") or {}):
            lead.append({"kind": "step", "act": s["now"]})
        shown = {t["view"]["n"] for t in thread if t["kind"] == "question"}
        lead += [{"kind": "question", "view": self._view(int(n))} for n in sorted(s.get("presented", {}), key=int)
                 if int(n) not in shown]
        blocks = self._thread_blocks(lead + thread)  # what the terminal shows, in its order
        sub = s.get("subtopic")
        where = views.note_location(self.vault.root, self.packs, sub) if sub else None
        notes = (where if where and not any(s.get(key) for key in ('skipped_answer_guards', 'presented', 'queue', 'suspended_for_retry'))
                 and (self.vault.root / where).exists() else None)
        title = self.packs.subtopics.get(sub, {}).get("title", "") if sub else ""
        self._mirror_now(" · ".join(x for x in (title, s.get("mode", ""), f"{self.now():%H:%M}") if x),
                         blocks or ["Working…"], notes)

    def rebuild(self) -> dict:
        self.state, n = model.new_state(), 0
        if copies := self.vault.conflict_copies():
            self.state["conflict_copies"] = copies
        for e in self.vault.events():  # one pass over the log: fold and count together
            model.apply(self.state, e)
            n += 1
        self._dirty = True
        self._save()
        return {"kcs": len(self.state["kcs"]), "events": n}

    # ---------- session lifecycle ----------
    def _remember_pending_node(self, p: dict) -> None:
        index = p.get('block_idx')
        blocks = self.session.get('blocks', [])
        if (p.get('block') == 'node' and type(index) is int and 0 <= index < len(blocks)
                and blocks[index].get('kind') == 'node'):
            p['deferred_node'] = {'session': self.session['id'], 'index': index,
                                  'kc': blocks[index].get('kc')}

    def topical_choices(self, focus: list[str], question_types: list[str] | None = None) -> dict:
        """Read-only availability for the same reviewed selection used by a topical set."""
        selected = topical_selection.validate_types(question_types)
        blocks = policy.plan_session(self.state, self.packs, self.now(), 1, 'topical', focus)
        chapters = blocks[0]['chapters'] if blocks else []
        groups = topical_selection.pools(self.packs, self.state, chapters, used=self._reserved_topical_ids())
        counts = topical_selection.counts(groups)
        return {'chapters': chapters, 'counts': counts, 'available': sum(counts[kind] for kind in selected)}

    def _reserved_topical_ids(self) -> set[str]:
        """Archived attempts retain their own recovery path and must not become new set questions."""
        return {key for saved in self.postponed_judgments() if (key := topicals.identity(saved.get('inst') or {}))}

    def start(self, mode: str = "autopilot", minutes: int = 50, focus: list[str] | None = None,
              replace: bool = False, *, topical_count: int | None = None,
              topical_types: list[str] | None = None, topical_auto_mark: bool = False,
              course: str | None = None, scope: str | None = None, sources: list[str] | None = None,
              count: int | None = None, started_only: bool = False) -> dict:
        """``mode="practice"`` (new): ``focus`` = subtopic/module ids (or empty with ``course``), ``scope`` =
        "course" | "module" | "chapters", ``sources`` ⊆ ["topical", "source_verified"], ``count`` = questions,
        ``started_only`` = only topics the learner has started.  The practice-only keywords are refused elsewhere."""
        configured = topical_count is not None or topical_types is not None
        practice = None
        try:
            if mode == 'practice':
                if scope not in (None, 'course', 'module', 'chapters'):
                    raise ValueError('Practice scope must be course, module or chapters.')
                if sources is not None and (not isinstance(sources, (list, tuple)) or not sources or any(
                        x not in ('topical', 'source_verified') for x in sources)):
                    raise ValueError('Practice sources must be topical and/or source_verified.')
                if count is not None and (type(count) is not int or not 1 <= count <= 200):
                    raise ValueError('Practice question count must be a whole number from 1 to 200.')
                if type(started_only) is not bool:
                    raise ValueError('started_only must be true or false.')
                if configured:
                    raise ValueError('Use count and sources for practice sessions.')
                practice = {'course': course, 'scope': scope, 'sources': list(sources) if sources else None,
                            'count': count, 'started_only': started_only}
            elif any(v not in (None, False) for v in (course, scope, sources, count, started_only)):
                raise ValueError('Course, scope, sources, count and started_only are for practice sessions only.')
        except ValueError as exc:
            return {'ok': False, 'error': str(exc)}
        try:
            topical_selection.validate_count(topical_count)
            selected_types = topical_selection.validate_types(topical_types)
            if type(topical_auto_mark) is not bool:
                raise ValueError('Automatic topical marking must be true or false.')
            if (configured or topical_auto_mark) and mode not in ('topical', 'practice'):
                raise ValueError('Question count and type filters are for topical sessions only.')
        except ValueError as exc:
            return {'ok': False, 'error': str(exc)}
        s = self.session
        if s and (s.get('suspended_for_retry') or s.get('deferred_feedback') or _has_deferred_judgment(s)):
            return {'ok': False, 'error': 'Resume saved questions and feedback before replacing this session.'}
        if s and s.get("answered") and not replace:
            return {"ok": False, "error": f"A {s['mode']} session is in progress ({s['answered']} answered).",
                    "open_session": {"mode": s["mode"], "answered": s["answered"], "started": s["started"]},
                    "fix": "To continue it, run the engine command next. To start over, repeat session start with --replace."}
        blocks = policy.plan_session(self.state, self.packs, self.now(), minutes, mode, focus, self.ticks(), practice)
        if mode == 'practice':
            if not blocks:
                return {'ok': False, 'error': 'No topics match this practice selection.'
                        + (' Start a topic first or turn off "started topics only".' if started_only else '')}
            self._plan_practice_queue(blocks[0], minutes)
            if not blocks[0]['question_queue']:
                return {'ok': False, 'error': 'No eligible questions match this practice selection.'}
        if mode == "topical" and not blocks:
            return {"ok": False, "error": "No reviewed topical questions are available for this selection."}
        if configured:
            block = blocks[0]
            groups = topical_selection.pools(self.packs, self.state, block['chapters'], selected_types,
                                             used=self._reserved_topical_ids())
            if not any(groups.values()):
                return {'ok': False, 'error': 'No eligible reviewed questions match the selected topics and types.'}
            block['question_types'] = selected_types
            if topical_count is not None:
                block['question_count'] = topical_count
                block['question_queue'] = topical_selection.sample(groups, topical_count, self.rng)
                block['question_index'] = 0
        if focus and mode in ("test", "learn", "diagnose", "long", "lesson") and not any(
                self.packs.items_for(k) for b in blocks for k in b.get("kcs", []) + [b.get("kc")] if k):
            return {"ok": False, "error": f"No questions are built yet for {', '.join(focus)}.",
                    "fix": "Use ids that find reports with has_pack true, or ask the learner to choose another topic."}
        sub = next((b["subtopic"] for b in blocks if b.get("subtopic")), None)
        if not sub and focus:
            subs = {self.packs.kc(k)["subtopic"] for k in policy.expand_focus(self.packs, focus) or [] if k in self.packs.kcs}
            sub = subs.pop() if len(subs) == 1 else None
        if mode == 'practice' and not focus and course:
            focus = [course]
        label = ({"autopilot": "Today's plan", "weak": "Weak spots"}.get(mode)
                 or (self.packs.subtopics.get(sub, {}).get("title") if sub else None) or ", ".join(focus or []) or mode)
        title = mode.title() if label == mode else f"{mode.title()} - {label}"
        name = title if len(title) <= 60 or not focus else f"{mode.title()} - {len(focus)} topics"
        try:
            views.LessonLog.destination(self.vault.root, title, self.now(), name=name)
        except views.ReadOnlyLessonDestination as exc:
            return {"ok": False, "error": str(exc)}
        if self.session:
            ended = self.end(abandoned=True)
            if ended.get('error'):
                return {'ok': False, 'error': ended['error']}
        try:
            transcript = views.LessonLog.create(self.vault.root, title, self.now(), name=name).rel
        except views.ReadOnlyLessonDestination as exc:
            return {"ok": False, "error": str(exc)}
        self.session = {"id": uuid.uuid4().hex[:8], "mode": mode, "minutes": minutes, "started": self.now().isoformat(),
                        "blocks": blocks, "cursor": 0, "presented": {}, "count": 0, "answered": 0, "correct": 0,
                        "kcs_learned": [], "retest": {}, "log": transcript}
        if mode in ('topical', 'practice'):
            self.session['topical_auto_mark'] = topical_auto_mark
        if mode == 'practice':
            self.session['practice'] = {k: blocks[0][k] for k in ('course', 'scope', 'sources', 'started_only', 'chapters')}
            self.session['course'] = course
        ready = []
        for saved in (self.postponed_judgments() if not configured else []):
            if saved['inst'].get('image') or saved['inst'].get('images'):
                continue  # old image bytes are not pinned
            candidate = self._revalidate_skipped(saved)
            chapter = candidate.get('serving_chapter') or self.packs.kcs.get(candidate['kcs'][0], {}).get('subtopic')
            ident = topicals.identity(candidate['inst']) or candidate['item']
            excluded = any(e['identity'] == ident and e['chapter'] == chapter for e in self.state.get('topical_exclusions', []))
            eligibility = topicals.eligibility(candidate['inst'], chapter, self.state, self.packs, candidate['unassisted'])
            if not excluded and (not candidate['inst'].get('topical') or eligibility['status'] in ('solvable', 'supported')):
                ready.append(candidate)
        if ready:
            self.session['deferred_judgments'] = ready
        from . import deferred_notes
        guards = deferred_notes.outstanding(self.vault.tutor / 'state' / 'deferred-notes.json')
        if guards:
            self.session['skipped_answer_guards'] = guards
        if sub:
            self.session["subtopic"] = sub
        self.log({"type": "session_start", "session": self.session["id"], "mode": mode, "minutes": minutes,
                  "blocks": [b["kind"] for b in blocks]})
        return {"session": self.session["id"], "blocks": blocks}

    def end(self, abandoned: bool = False) -> dict:
        if self.session is None:
            return {"session": None, "answered": 0, "correct": 0, "accuracy": None, "kcs_learned": [],
                    "unanswered": 0, "abandoned": abandoned}
        events = list(self.vault.events())
        if (recovered := self._recover_ended_session(events)) is not None:
            self._sync_almanac(force=True)
            return recovered
        if any(p.get('pending_saved_mark') for p in self.session.get('presented', {}).values()):
            return {'error': 'Finish or skip the saved answer before ending this session.'}
        try:
            if any(self._pending_ungraded_event(key, p) for key, p in self.session.get('presented', {}).items()):
                self._recover()
        except (OSError, ValueError):
            return {'error': 'Could not finish saving your earlier attempt. Retry before ending this session.'}
        if self.session.get('suspended_for_retry') or self.session.get('deferred_feedback') or _has_deferred_judgment(self.session):
            return {'error': 'Resume saved questions and feedback before ending this session.'}
        try:
            self._sync_guard_drafts()
        except (OSError, ValueError):
            return {'error': 'Could not save the skipped-question draft. Retry before ending this session.'}
        self._reconcile_correction_totals(events)
        s = self.session
        self.study_clock.flush()
        true_s = max(0, round((self.now() - datetime.fromisoformat(s["started"])).total_seconds())) if s.get("started") else 0
        try:
            log = self._lesson_log()
        except OSError as exc:
            log = None
            s.setdefault("view_errors", {})["Lesson transcript"] = str(exc)
        summary = {"session": s.get("id"), "answered": s.get("answered", 0), "correct": s.get("correct", 0),
                   "accuracy": round(s["correct"] / s["answered"], 2) if s.get("answered") else None,
                   "kcs_learned": s.get("kcs_learned", []), "unanswered": len(s.get("presented", {})),
                   "abandoned": abandoned, "active_seconds": round(self.study_clock.session(s.get("id"))), "true_seconds": true_s,
                   "marks": [s.get("marks_earned", 0), s.get("marks_total", 0)]}
        if s.get("view_errors"):
            summary["view_errors"] = dict(s["view_errors"])
        self.log({"type": "session_end", **summary})
        try:
            if log and not abandoned:
                log.tutor(f"Time: {fmt(summary['active_seconds'])} on the screen (session time), {fmt(summary['true_seconds'])} "
                          f"from start to finish (true time).\n\n"
                          f"Answered {summary['answered']}, correct {summary['correct']}"
                          + (f"; learned: {', '.join(self.packs.kcs[k]['title'] for k in summary['kcs_learned'] if k in self.packs.kcs)}"
                             if summary["kcs_learned"] else "") + ".", title="Session summary")
        except OSError as exc:
            summary.setdefault("view_errors", {})["Lesson transcript"] = str(exc)
        if s.get("view_errors"):
            summary.setdefault("view_errors", {}).update(s["view_errors"])
        kcs = [k for p in s.get("presented", {}).values() for k in p.get("kcs", [])] + summary["kcs_learned"] \
            + s.get("kcs_answered", [])  # answered questions have left `presented`: a review changes mastery too
        touched = {self.packs.kcs[k]["subtopic"] for k in kcs if k in self.packs.kcs}
        if s.get("subtopic"):
            touched.add(s["subtopic"])
        self.session = None
        self._save()
        for sub in touched:
            try:
                views.refresh_status(self.vault.root, self.packs, self.state, sub)
            except OSError as exc:
                summary.setdefault("view_errors", {})[f"My Notes {sub}"] = str(exc)
        try:
            views.write_home(self.vault.root, self.packs, self.state, self.now(), views.recent_lessons(self.vault.root))
        except Exception as exc:  # noqa: BLE001 - a dashboard failure must not hide a completed session
            summary["home_error"] = str(exc)
        self._sync_almanac(force=True)  # the session is over: the Almanac stops saying "live"
        return summary

    # ---------- presenting ----------
    def _present(self, item: dict, block: str, phase: str | None, unassisted: bool = False,
                 block_idx: int | None = None, exp: str | None = None, serving_chapter: str | None = None) -> dict | None:
        return self._open(*self._number(item, block, phase, unassisted, block_idx, exp, serving_chapter))

    def _number(self, item: dict, block: str, phase: str | None, unassisted: bool = False,
                block_idx: int | None = None, exp: str | None = None, serving_chapter: str | None = None) -> tuple[str, dict]:
        """A question made ready (its values drawn, its number taken) but not yet shown."""
        inst = instantiate(item, self.rng)
        self.session["count"] += 1
        meta = self.packs.kc(item["kcs"][0]) if item["kcs"][0] in self.packs.kcs else {}
        return str(self.session["count"]), {
            "item": item["id"], "inst": inst, "kcs": item["kcs"], "subject": meta.get("subject"),
            "serving_chapter": serving_chapter or item.get("_serving_chapter") or meta.get("subtopic"),
            "difficulty": item.get("difficulty", 3), "marks": item.get("marks", 1), "block": block,
            "block_idx": block_idx, "phase": phase, "hinted": False, "hint_level": 0, "unassisted": unassisted, "exp": exp}

    def _start_chapter(self, chapter: str | None) -> None:
        if chapter and chapter not in self.state.get("started_chapters", []):
            self.log({"type": "chapter_started", "chapter": chapter})

    def _open(self, n: str, p: dict) -> dict | None:
        """Show a question. From now it is open: its clock runs, the help rules apply, Now and the log have it."""
        chapter = p.get("serving_chapter") or self.packs.kcs.get(p["kcs"][0], {}).get("subtopic")
        p["serving_chapter"] = chapter
        ident = topicals.identity(p["inst"]) or p["item"]
        guard = (self.session.get('skipped_answer_guards') or {}).get(_guard_identity(p))
        ungraded = (p.get('ungraded_unavailable') is True and p.get('block') == 'skipped_retry'
                    and isinstance(guard, dict) and (guard.get('question') or {}).get('inst') == p['inst']
                    and not p['inst'].get('image') and not p['inst'].get('images'))
        if not ungraded and any(e["identity"] == ident and e["chapter"] == chapter for e in self.state.get("topical_exclusions", [])):
            return None
        check = topicals.eligibility(p["inst"], chapter, self.state, self.packs, p["unassisted"])
        if (not ungraded and p["inst"].get("topical") and check["status"] not in ("solvable", "supported")
                and not p.get("practice_any")):
            return None
        if not ungraded and check.get('support') and any(
                key != _guard_identity(p) for key in (self.session.get('skipped_answer_guards') or {})):
            return None  # support may disclose an answer protected by another guard
        p["support"] = {} if ungraded else check["support"]
        if p["support"]:
            p["hinted"] = True
        if not ungraded:
            self._start_chapter(chapter)
        p["shown_at"] = self.now().isoformat()
        self.session["presented"][n] = p
        self._audit("present", int(n), p["inst"])
        if (log := self._lesson_log()):
            log.question(self._view(int(n)))
        return self._view(int(n))

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
        if p.get('saved_work'):
            v['saved_work'] = p['saved_work']
        if p.get("support"):
            v["support"] = dict(p["support"])
        if v.get("images") and not v.get("image"):
            v["image"] = v["images"][0]
        # Speech dictionaries also hold explanations and hints, which stay private before an attempt.
        speech = inst.get("speech")
        if isinstance(speech, dict):
            speech = speech.get("stem")
        if isinstance(speech, str) and speech:
            v["speech"] = speech
        if inst.get("source", {}).get("type") == "past":
            v["source"] = inst["source"].get("ref")
        if inst["kind"] == "structured":
            if topicals.whole_rubric(inst) is not None:
                v['manual_marking'] = True
            else:
                v["scheme_points"] = len(inst.get("scheme", []))
        if question_display.shows_printed_question(inst):
            # The pictures are the question as printed. Shown alone, once each and in page order, with one line saying
            # which parts to do: the text the PDF copied out of them (stem, options, table cells) is never shown.
            v["images"] = question_display.page_order(drop_repeated(v.get("images") or [v["image"]], self.vault.root))
            v["image"] = v["images"][0]
            v["image_only"] = True
            parts = p.get("do_parts") or ([inst["source"]["part"]] if inst["source"].get("part") else [])
            v["stem"] = question_display.instruction(parts, whole=bool(p.get("do_whole"))) if inst["kind"] == "structured" else ""
        elif v.get("image"):  # a past-paper figure or table beside the question's own sentences
            if inst.get("source", {}).get("type") == "past":
                v["stem"] = question_display.strip_figure_labels(v.get("stem", ""))
                v["images"] = question_display.page_order(drop_repeated(v.get("images") or [v["image"]], self.vault.root))
                v["image"] = v["images"][0]
            # broken text read from the paper gives way to the picture (Q-009)
            bad = [k for k, o in (v.get("options") or {}).items() if views.garbled(o)]
            if bad or views.garbled(v.get("stem", "")):
                v["garbled"] = {"stem": views.garbled(v.get("stem", "")), "options": bad}
        return v

    def _disclosed_ids(self) -> set[str]:
        # Older saved lessons can already have initialized or completed nodes
        # without the session-level list introduced by newer teaching cards.
        from . import lesson
        disclosed = self.session.setdefault('disclosed_item_ids', [])
        for block in self.session.get('blocks', []):
            node_kc = block.get('kc') if block.get('kind') == 'node' and 'phases' in block else None
            if node_kc in self.packs.kcs:
                for card in (block.get('card'), lesson.teach_card(self, node_kc)):
                    ids = card.get('disclosed_item_ids') if isinstance(card, dict) else None
                    if isinstance(ids, list):
                        disclosed.extend(item for item in ids if isinstance(item, str) and item not in disclosed)
        return set(disclosed)

    def _pick(self, kc: str, target: float, kinds=("mcq", "numeric", "expression", "short"),
              staged: set[str] | None = None, unassisted: bool = False) -> dict | None:
        """Prefer items not yet used this session; fall back to reuse rather than skip the KC."""
        bank = self.packs.topicals
        with bank.request() as outer:
            result = self._pick_candidate(kc, target, kinds, staged, unassisted)
            return result if not outer or bank.request_current() else None

    def _pick_candidate(self, kc: str, target: float, kinds, staged, unassisted) -> dict | None:
        disclosed = self._disclosed_ids()
        open_ = {p["item"] for p in self.session["presented"].values()}
        open_.update(disclosed)
        open_.update(staged or ())  # fixed questions selected for this batch are not available to the reuse fallback
        used = open_ | set(self.session.get("used", []))
        return (self.packs.select_item(kc, self.state, target, self.rng, self.now(), kinds=kinds, exclude=used,
                                       unassisted=unassisted)
                or self.packs.select_item(kc, self.state, target, self.rng, self.now(), kinds=kinds, exclude=open_,
                                          unassisted=unassisted))

    def _pick_batch(self, kcs: list[str], target: float, unassisted: bool = False) -> list[tuple[str, dict]]:
        bank = self.packs.topicals
        with bank.request() as outer:
            selected = self._pick_candidates(kcs, target, unassisted)
            return selected if not outer or bank.request_current() else []

    def _pick_candidates(self, kcs, target, unassisted):
        selected, staged = [], set()
        for kc in kcs:
            if it := self._pick(kc, target, staged=staged, unassisted=unassisted):
                selected.append((kc, it))
                if not it.get("template"):
                    staged.add(it["id"])
        return selected

    def _questions(self, block: dict, idx: int, items: list[dict], phase: str | None = None,
                   unassisted: bool = False, exp: str | None = None) -> dict | None:
        ready = []
        disclosed = self._disclosed_ids()
        for it in items:
            if disclosed and self.packs.aliases_for(it) & disclosed:
                continue
            self.session.setdefault("used", []).append(it["id"])
            requested = block.get("asked_for", {}).get(it["id"]) or block.get("kc")
            chapter = it.get("_serving_chapter") or self.packs.kcs.get(requested, {}).get("subtopic")
            check = topicals.eligibility(it, chapter or self.packs.kcs.get(it["kcs"][0], {}).get("subtopic"),
                                         self.state, self.packs, unassisted)
            if it.get("topical") and check["status"] not in ("solvable", "supported"):
                if not unassisted:
                    continue
                requested = requested or it.get("_serving_kc") or next(
                    (k for k in it["kcs"] if self.packs.kcs.get(k, {}).get("subtopic") == chapter), it["kcs"][0])
                open_ = ({p["item"] for p in self.session["presented"].values()}
                         | {p["item"] for _, p in ready} | self._disclosed_ids())
                used = open_ | set(self.session.get("used", []))
                kinds = it.get("_selection_kinds") or (("structured",) if it["kind"] == "structured" else
                                                       ("mcq", "numeric", "expression", "short"))
                replacement = (self.packs.select_item(requested, self.state, .75, self.rng, self.now(),
                                                      kinds=kinds, exclude=used, unassisted=True)
                               or self.packs.select_item(requested, self.state, .75, self.rng, self.now(),
                                                         kinds=kinds, exclude=open_, unassisted=True))
                if not replacement:
                    continue
                if it["id"] in block.get("asked_for", {}):
                    block["asked_for"][replacement["id"]] = requested
                it = replacement
                chapter = it.get("_serving_chapter")
                self.session.setdefault("used", []).append(it["id"])
            ready.append(self._number(it, block["kind"], phase, unassisted, idx, exp, chapter))
        if not ready:
            return None
        if self.one_at_a_time:  # the rest of the batch waits unseen; next() shows each once the one before is marked
            self.session["queue"] = dict(ready[1:])
            ready = ready[:1]
        if block["kind"] == "learn" and phase == "practice":
            return self._ask(ready, practice_block=block)
        return self._ask(ready)

    def _ask(self, ready: list[tuple[str, dict]], practice_block: dict | None = None) -> dict | None:
        shown = [q for n, p in ready if (q := self._open(n, p))]
        if practice_block is not None:
            idx = ready[0][1]["block_idx"]
            staged = sum(p.get("block_idx") == idx and p.get("phase") == "practice"
                         for p in (*self.session["presented"].values(), *self.session.get("queue", {}).values()))
            practice_block["practiced"] = practice_block.get("practiced", 0) + staged
        if not shown:
            return None
        self._set_now({"activity": "questions"})
        self._save()
        return {"activity": "questions", "block": ready[0][1]["block"], "phase": ready[0][1]["phase"], "items": shown,
                "ask": "Stems may contain LaTeX: show them in chat. Collect answer + confidence (1 guess .. 4 certain)."}

    def _revalidate_skipped(self, question: dict) -> dict:
        """Return a copy, refreshing metadata only when the reviewed question still matches."""
        p = copy.deepcopy(question)
        inst = p['inst']
        chapter = p.get('serving_chapter') or self.packs.kcs.get(p['kcs'][0], {}).get('subtopic')
        if (inst.get('topical') and not inst.get('image') and not inst.get('images') and
                topicals.eligibility(inst, chapter, self.state, self.packs, p.get('unassisted', False))['status'] == 'unverified'):
            identity = topicals.identity(inst)
            fields = (*PUBLIC, 'kcs', 'answer', 'rubric', 'review_answer', 'explanation',
                      'hints', 'distractors', 'params')
            self.packs.topicals.refresh()
            matches = [candidate for candidate in self.packs.topicals.items
                       if identity and topicals.identity(candidate) == identity
                       and chapter in candidate['topical']['chapters']
                       and all(candidate.get(key) == inst.get(key) for key in fields)]
            if len(matches) == 1:
                inst['topical'] = copy.deepcopy(matches[0]['topical'])
        return p

    def skipped_retry_available(self) -> bool:
        """Whether at least one saved instance can be reopened without changing learner state."""
        s = self.session or {}
        for guard in s.get('skipped_answer_guards', {}).values():
            p = guard.get('question') if isinstance(guard, dict) else None
            if not isinstance(p, dict) or not isinstance(p.get('inst'), dict) or not p.get('kcs'):
                continue
            p = self._revalidate_skipped(p)
            inst = p['inst']
            chapter = p.get('serving_chapter') or self.packs.kcs.get(p['kcs'][0], {}).get('subtopic')
            ident = topicals.identity(inst) or p.get('item')
            if any(e['identity'] == ident and e['chapter'] == chapter for e in self.state.get('topical_exclusions', [])):
                continue
            eligibility = topicals.eligibility(inst, chapter, self.state, self.packs, p.get('unassisted', False))
            if eligibility.get('support') and any(key != _guard_identity(p)
                                                  for key in s.get('skipped_answer_guards', {})):
                continue
            if not inst.get('topical') or eligibility['status'] in ('solvable', 'supported'):
                return True
        return False

    def suspend_questions_for_retry(self) -> dict:
        """Preserve pending questions in the current session while retrying skipped work."""
        s = self.session
        if not s or not s.get('skipped_answer_guards') or s.get('suspended_for_retry'):
            return {'ok': False, 'error': 'Questions cannot be set aside now.'}
        if not s.get('presented') and not s.get('queue'):
            return {'ok': False, 'error': 'There are no pending questions to set aside.'}
        if any(self._pending_ungraded_event(key, p) for key, p in s.get('presented', {}).items()):
            return {'ok': False, 'error': 'Finish saving the earlier attempt before setting questions aside.'}
        awaiting = s.get('awaiting')
        s['suspended_for_retry'] = {'presented': s.get('presented', {}), 'queue': s.get('queue', {}),
                                    'awaiting': None if (awaiting or {}).get('part') == 'guard_pause' else awaiting}
        s['presented'], s['queue'], s['awaiting'] = {}, {}, None
        self._save()
        return {'ok': True}

    def resume_suspended_questions(self) -> dict:
        """Cancel a retry and return to the previously open questions without resolving guards."""
        s = self.session or {}
        if not s.get('suspended_for_retry') or s.get('presented') or s.get('queue'):
            return {'ok': False, 'error': 'Finish the active retry before returning to saved questions.'}
        suspended = s.pop('suspended_for_retry')
        s['presented'], s['queue'], s['awaiting'] = suspended['presented'], suspended['queue'], suspended['awaiting']
        self._save()
        return {'ok': True}

    def _pending_ungraded_event(self, key: str, p: dict) -> dict | None:
        s = self.session or {}
        matches = [e for e in self.vault.events() if e.get('type') == 'ungraded_retry'
                   and e.get('session') == s.get('id') and str(e.get('n')) == str(key)
                   and e.get('item') == p.get('item') and e.get('guard') == _guard_identity(p)
                   and e.get('id') not in s.get('ungraded_retry_events', [])]
        if len(matches) > 1:
            raise ValueError('Multiple saved attempts need review.')
        return matches[0] if matches else None

    def _defer_retry_attempt(self, key: str, p: dict, response: str, event: dict | None = None) -> dict:
        """Persist an attempt without a grade until protected rubrics can be shown."""
        from . import deferred_notes
        s = self.session
        ident = _guard_identity(p)
        event = event or self._pending_ungraded_event(key, p)
        if event and event.get('response') != response:
            raise ValueError('An earlier attempt is already saved; submit that same working to finish saving it.')
        event = event or self.log({'type': 'ungraded_retry', 'session': s['id'], 'n': int(key),
                                   'item': p['item'], 'guard': ident, 'response': response})
        before = copy.deepcopy(s)
        deferred_notes.resolve(self.vault.tutor / 'state' / 'deferred-notes.json', ident)
        s.get('skipped_answer_guards', {}).pop(ident, None)
        if event['id'] not in s.setdefault('ungraded_retry_events', []):
            pending = copy.deepcopy(p)
            pending.pop('ungraded_unavailable', None)
            pending.update(saved_work=response, block='deferred_judgment', block_idx=None, exp=None,
                           judgment_id=event['id'])
            s.setdefault('deferred_judgments', []).append(pending)
            s['ungraded_retry_events'].append(event['id'])
        s['presented'].pop(key, None)
        try:
            self._save()
        except (OSError, ValueError):
            s.clear()
            s.update(before)
            raise
        return {'n': int(key), 'event': event['id'], 'your': response, 'attempt_saved': True}

    def _give_up_ungraded_retry(self, key: str, p: dict) -> dict:
        """Close an unmarkable retry without marking it: the question stays on the review list."""
        from . import deferred_notes
        s = self.session
        ident = _guard_identity(p)
        deferred_notes.resolve(self.vault.tutor / 'state' / 'deferred-notes.json', ident)
        s.get('skipped_answer_guards', {}).pop(ident, None)
        s['presented'].pop(key, None)
        self._save()
        return {'n': int(key), 'gave_up': True, 'ungraded': True,
                'say': 'Not marked. The question stays on your review list.'}

    def postponed_judgments(self) -> list[dict]:
        events = list(self.vault.events())
        completed = {e.get('postponement_id') for e in events if e.get('type') == 'answer' and e.get('postponement_id')}
        return [copy.deepcopy(e['question']) for e in events if e.get('type') == 'postponed_judgment'
                and e.get('postponement_id') not in completed and isinstance(e.get('question'), dict)]

    def retained_drafts(self) -> dict:
        from . import deferred_notes
        return deferred_notes.all_draft_history(self.vault.tutor / 'state' / 'deferred-notes.json')

    def retry_draft_history(self, n: int) -> list[str]:
        """Only expose this question's drafts when no other answer is protected."""
        from . import deferred_notes
        s = self.session or {}
        presented = s.get('presented') or {}
        p = presented.get(str(n))
        if (not p or p.get('block') != 'skipped_retry' or len(presented) != 1
                or s.get('queue') or s.get('suspended_for_retry')):
            return []
        ident = _guard_identity(p)
        path = self.vault.tutor / 'state' / 'deferred-notes.json'
        guards = s.get('skipped_answer_guards') or {}
        stored, history = deferred_notes.guard_and_history(path, ident)
        if set(guards) != {ident} or set(stored) != {ident}:
            return []
        if (guards[ident].get('question') or {}).get('inst') != p.get('inst'):
            return []
        if (stored[ident].get('question') or {}).get('inst') != p.get('inst'):
            return []
        if any(guards[ident].get(key) != stored[ident].get(key)
               for key in ('key', 'kind', 'numeric', 'short_answers')):
            return []
        return history

    def postpone_saved_judgment(self) -> dict:
        s = self.session or {}
        pending = s.get('deferred_judgments') or []
        if not pending or s.get('presented') or s.get('queue'):
            return {'ok': False, 'error': 'No saved attempt is available to postpone.'}
        p = pending[0]
        if not p.get('postponement_id'):
            if not p.get('judgment_id'):
                p['judgment_id'] = uuid.uuid4().hex
                self._save()  # assign the unique identity before writing the archive event
            existing = [row for row in self.postponed_judgments() if row.get('judgment_id') == p['judgment_id']]
            if len(existing) > 1:
                raise ValueError('ambiguous postponed judgment')
            if not existing:
                postponement_id = uuid.uuid4().hex
                archived = {**copy.deepcopy(p), 'postponement_id': postponement_id}
                self.log({'type': 'postponed_judgment', 'session': s['id'], 'postponement_id': postponement_id,
                          'question': archived})
        pending.pop(0)
        self._save()
        return {'ok': True, 'image_review_required': bool(p['inst'].get('image') or p['inst'].get('images'))}

    def retry_skipped(self, identity: str | None = None, chapter: str | None = None,
                      guard_id: str | None = None) -> dict:
        """Reopen the exact saved instance without advancing the original lesson block."""
        s = self.session
        if not s or s.get("presented"):
            return {"activity": "error", "error": "Finish the current activity before retrying."}
        if self._written_guard_conflict():
            return {'activity': 'error', 'error': 'Saved drafts differ or are unavailable; recovery is required before retrying.'}
        if s.get('queue'):
            if not self.suspend_questions_for_retry().get('ok'):
                return {'activity': 'error', 'error': 'Could not set queued questions aside.'}
        saved = [g['question'] for g in s.get("skipped_answer_guards", {}).values()
                 if isinstance(g, dict) and isinstance(g.get("question"), dict)]
        if not saved:
            return {"activity": "error", "error": "No saved skipped question is available to retry."}
        restore_candidate = None
        restore_guard = None
        restore_stem = None
        missing_options = []
        unverified = False
        protected_support = False
        for question in saved:
            p = self._revalidate_skipped(question)
            if guard_id is not None and _guard_identity(question) != guard_id:
                continue
            saved_chapter = p.get('serving_chapter') or self.packs.kcs.get(p['kcs'][0], {}).get('subtopic')
            saved_identity = topicals.identity(p['inst']) or p['item']
            if identity is not None and (saved_identity != identity or saved_chapter != chapter):
                continue
            phase = p.get("phase") if p.get("phase") in ("form_check", "term_review") else "skipped_retry"
            p.update(block="skipped_retry", block_idx=None, phase=phase, exp=None)
            chapter = p.get('serving_chapter') or self.packs.kcs.get(p['kcs'][0], {}).get('subtopic')
            inst = p['inst']
            paused = s.get('awaiting') if (s.get('awaiting') or {}).get('part') == 'guard_pause' else None
            if paused:
                s['awaiting'] = None
            s["count"] += 1
            activity = self._ask([(str(s["count"]), p)])
            if activity is not None:
                return activity
            s["count"] -= 1
            if paused:
                s['awaiting'] = paused
            ident = topicals.identity(p['inst']) or p['item']
            excluded = any(e['identity'] == ident and e['chapter'] == chapter
                           for e in self.state.get('topical_exclusions', []))
            eligibility = topicals.eligibility(p['inst'], chapter, self.state, self.packs, p['unassisted'])
            if eligibility.get('support') and any(key != _guard_identity(p)
                                                  for key in s.get('skipped_answer_guards', {})):
                protected_support = True
            if p['inst'].get('topical'):
                if eligibility['status'] == 'unavailable':
                    missing_options.append(sorted(eligibility['missing']))
                elif eligibility['status'] == 'unverified':
                    unverified = True
            if (excluded and restore_candidate is None and
                    (not p['inst'].get('topical') or eligibility['status'] in ('solvable', 'supported'))):
                restore_candidate = {'identity': ident, 'chapter': chapter}
                restore_guard = _guard_identity(question)
                restore_stem = _question_excerpt(question['inst'].get('stem'))
        result = {"activity": "error", "error": "The saved skipped questions are no longer eligible."}
        if protected_support:
            result['error'] = 'Retry another skipped question first; its protected answer may overlap required support.'
        if restore_candidate:
            result['restore_candidate'] = restore_candidate
            result['restore_guard'] = restore_guard
            result['restore_stem'] = restore_stem
        elif missing_options:
            result['missing_chapters'] = min(missing_options, key=lambda chapters: (len(chapters), chapters))
            result['error'] = 'Start these chapters before retrying: ' + ', '.join(result['missing_chapters']) + '.'
        elif unverified:
            result['error'] = 'The saved question no longer matches the available syllabus or chapter data; it needs review.'
        return result

    def ungraded_retry_candidate(self) -> dict | None:
        s = self.session or {}
        if s.get('presented') or s.get('queue'):
            return None
        for ident, guard in (s.get('skipped_answer_guards') or {}).items():
            p = guard.get('question') if isinstance(guard, dict) else None
            inst = p.get('inst') if isinstance(p, dict) else None
            if (isinstance(inst, dict) and not inst.get('image') and not inst.get('images')
                    and inst.get('kind') in ('mcq', 'numeric', 'expression', 'short', 'structured')):
                return {'guard': ident, 'stem': _question_excerpt(inst.get('stem')), 'item': p.get('item', '')}
        return None

    def retry_skipped_ungraded(self, guard_id: str | None = None) -> dict:
        """Offer an exact text-only skipped instance without restoring or grading it."""
        s = self.session
        if not s or s.get('presented') or s.get('queue'):
            return {'activity': 'error', 'error': 'Finish the current activity first.'}
        if self._written_guard_conflict():
            return {'activity': 'error', 'error': 'Saved drafts differ or are unavailable; recovery is required before retrying.'}
        for ident, guard in (s.get('skipped_answer_guards') or {}).items():
            if guard_id is not None and ident != guard_id:
                continue
            p = copy.deepcopy(guard.get('question')) if isinstance(guard, dict) else None
            if not isinstance(p, dict) or not isinstance(p.get('inst'), dict):
                continue
            inst = p['inst']
            if inst.get('image') or inst.get('images') or inst.get('kind') not in ('mcq', 'numeric', 'expression', 'short', 'structured'):
                continue
            p.update(block='skipped_retry', block_idx=None, phase='skipped_retry', exp=None,
                     ungraded_unavailable=True)
            paused = s.get('awaiting') if (s.get('awaiting') or {}).get('part') == 'guard_pause' else None
            if paused:
                s['awaiting'] = None
            s['count'] += 1
            activity = self._ask([(str(s['count']), p)])
            if activity:
                return activity
            s['count'] -= 1
            if paused:
                s['awaiting'] = paused
        return {'activity': 'error', 'error': 'No recoverable text-only question is available.'}

    def save_ungraded_structured(self, n: int, work: str) -> dict:
        """Save typed work on an unavailable structured retry, without opening its scheme."""
        s = self.session or {}
        p = s.get('presented', {}).get(str(n))
        if (not isinstance(p, dict) or p.get('block') != 'skipped_retry'
                or p.get('ungraded_unavailable') is not True or p.get('inst', {}).get('kind') != 'structured'
                or p['inst'].get('image') or p['inst'].get('images')
                or (s.get('skipped_answer_guards', {}).get(_guard_identity(p), {}).get('question') or {}).get('inst') != p['inst']):
            return {'ok': False, 'error': 'This question is not an ungraded structured retry.'}
        text = work.strip() if isinstance(work, str) else ''
        normal = text.casefold().replace('’', "'").strip('?.! ')
        if normal in ('', 'idk', "i don't know", 'i dont know', 'i do not know', 'skip', 'no',
                      'i have no idea', "i can't answer", 'i cant answer', 'not sure', 'done on paper'):
            event = self._pending_ungraded_event(str(n), p)
            if event:
                return {'ok': True, **self._defer_retry_attempt(str(n), p, event['response'], event=event)}
            return {'ok': True, **self._give_up_ungraded_retry(str(n), p)}
        return {'ok': True, **self._defer_retry_attempt(str(n), p, text)}

    def cancel_ungraded_structured(self, n: int, work: str) -> dict:
        """Set aside typed draft while leaving the saved question guarded."""
        from . import deferred_notes
        s = self.session or {}
        p = s.get('presented', {}).get(str(n))
        if (not isinstance(p, dict) or p.get('block') != 'skipped_retry'
                or p.get('ungraded_unavailable') is not True or p.get('inst', {}).get('kind') != 'structured'
                or not isinstance(work, str)):
            return {'ok': False, 'error': 'This question is not an ungraded structured retry.'}
        ident = _guard_identity(p)
        guard = s.get('skipped_answer_guards', {}).get(ident)
        if not isinstance(guard, dict) or (guard.get('question') or {}).get('inst') != p['inst']:
            return {'ok': False, 'error': 'The saved question changed; retry is unavailable.'}
        if self._pending_ungraded_event(str(n), p):
            return {'ok': False, 'error': 'An earlier attempt is already saved; submit the same working to finish saving it.'}
        guard['question']['saved_work'] = work
        p['saved_work'] = work
        self._save()
        deferred_notes.hold(self.vault.tutor / 'state' / 'deferred-notes.json', ident, guard)
        s['presented'].pop(str(n))
        self._save()
        return {'ok': True}

    # ---------- next ----------
    def next(self) -> dict:
        self._last_mark = None  # a re-mark can redo only the answer still on screen
        s = self.session
        if not s:
            return {"activity": "no_session", "hint": "engine command: session start"}
        if s.get('skipped_answer_guards') and not s.get('presented'):
            awaiting = s.get('awaiting')
            if awaiting and awaiting.get('part') != 'guard_pause':
                s.setdefault('protected_awaiting', awaiting)
            activity = self._await({'activity': 'explain', 'block_idx': None, 'part': 'guard_pause',
                                    'title': 'Try the skipped question',
                                    'text': 'Pending work is saved. Press ctrl+u for retry options.'})
            self._save()
            return activity
        if s.get('suspended_for_retry') and not s.get('skipped_answer_guards') and not s.get('presented'):
            suspended = s.pop('suspended_for_retry')
            s['presented'], s['queue'], s['awaiting'] = suspended['presented'], suspended['queue'], suspended['awaiting']
            self._save()
        if not s.get('skipped_answer_guards') and s.get('protected_awaiting') and not s.get('awaiting'):
            s['awaiting'] = s.pop('protected_awaiting')
        if s.get("awaiting") and not any(p.get("block") in ("skipped_retry", "guided_request")
                                         for p in s.get("presented", {}).values()):
            if s.get("now") != s["awaiting"]:
                self._set_now(s["awaiting"])
                self._save()
            return s["awaiting"]
        if self.one_at_a_time and len(s["presented"]) > 1:  # a batch opened whole (the chat, or the app before 1.2.3)
            for n in sorted(s["presented"], key=int)[1:]:
                s.setdefault("queue", {})[n] = s["presented"].pop(n)
            self._save()
        if s["presented"]:
            return {"activity": "awaiting", "items": [self._view(int(n)) for n in s["presented"]]}
        while s.get("queue"):
            n = min(s["queue"], key=int)
            if (act := self._ask([(n, s["queue"].pop(n))])):
                return act
        if s.get('deferred_judgments') and not s.get('skipped_answer_guards') and not s.get('suspended_for_retry'):
            p = self._revalidate_skipped(s['deferred_judgments'][0])
            s['count'] += 1
            n = str(s['count'])
            view = self._open(n, p)
            if view is None:
                s['count'] -= 1
                chapter = p.get('serving_chapter') or self.packs.kcs.get(p['kcs'][0], {}).get('subtopic')
                ident = topicals.identity(p['inst']) or p['item']
                excluded = any(e['identity'] == ident and e['chapter'] == chapter
                               for e in self.state.get('topical_exclusions', []))
                eligibility = topicals.eligibility(p['inst'], chapter, self.state, self.packs, p['unassisted'])
                result = {'activity': 'saved_judgment_unavailable',
                          'error': 'The saved attempt cannot yet be marked; its working remains saved.'}
                if excluded and (not p['inst'].get('topical') or eligibility['status'] in ('solvable', 'supported')):
                    result['restore_candidate'] = {'identity': ident, 'chapter': chapter}
                return result
            s['deferred_judgments'].pop(0)
            self._set_now({'activity': 'questions'})
            self._save()
            return {'activity': 'questions', 'block': p['block'], 'phase': p['phase'], 'items': [view],
                    'ask': 'Your previous attempt is saved; submit it for marking.'}
        if s.get('deferred_feedback') and not s.get('skipped_answer_guards') and not s.get('suspended_for_retry'):
            fb = s['deferred_feedback'].pop(0)
            _, title, body = views.feedback_card(fb, fb.get('your', ''))
            activity = self._await({'activity': 'explain', 'block_idx': None, 'part': 'delayed_feedback',
                                    'title': title, 'text': body})
            self._save()
            return activity
        while s["cursor"] < len(s["blocks"]):
            idx = s["cursor"]
            act = getattr(self, "_step_" + s["blocks"][idx]["kind"])(s["blocks"][idx], idx)
            if act:
                self._save()
                return act
            s["cursor"] += 1
        self._save()
        return {"activity": "end", "hint": "engine command: session end"}

    def _step_topical(self, b: dict, idx: int) -> dict | None:
        """Source-only practice: no lesson packs, teaching steps, or repeats in this session."""
        if 'question_queue' in b:
            return self._step_topical_set(b, idx)
        remaining = b.setdefault("remaining", max(1, self.session["minutes"] // 3))
        used = set(self.session.setdefault("topical_used", []))
        if b.get('question_types'):
            used.update(self._reserved_topical_ids())
        disclosed = self._disclosed_ids()
        excluded = {(r["identity"], r["chapter"]) for r in self.topical_exclusions()}
        candidates = []
        for chapter in b["chapters"]:
            for item in self.packs.topical_items(chapter):
                key = topicals.identity(item)
                if b.get('question_types') and topical_selection.category(item) not in b['question_types']:
                    continue
                if disclosed and self.packs.aliases_for(item) & disclosed:
                    continue
                cost = max(1, math.ceil(item.get("marks", 1) / 2)) if item["kind"] == "structured" else 1
                if key in used or (key, chapter) in excluded or cost > remaining:
                    continue
                if topicals.eligibility(item, chapter, self.state, self.packs)["status"] not in ("solvable", "supported"):
                    continue
                aliases = self.packs._topical_aliases.get(key, {item["id"]})
                seen = any(alias in self.state["items_seen"] for alias in aliases)
                candidates.append((seen, self.rng.random(), key, cost, item))
        if not candidates:
            return None
        _, _, key, cost, item = min(candidates, key=lambda row: row[:2])
        self.session["topical_used"].append(key)
        b["remaining"] -= cost
        return self._questions(b, idx, [item], phase="topical")

    def _step_topical_set(self, b: dict, idx: int) -> dict | None:
        """Serve only planned identities, rechecking current eligibility and disclosure."""
        groups = topical_selection.pools(self.packs, self.state, b['chapters'], b['question_types'],
                                         used=self.session.get('topical_used', []), disclosed=self._disclosed_ids())
        current = {(topicals.identity(item), chapter): item for chapter, rows in groups.items() for item in rows}
        while b['question_index'] < len(b['question_queue']):
            chosen = b['question_queue'][b['question_index']]
            b['question_index'] += 1
            item = current.get((chosen['identity'], chosen['chapter']))
            if item is None:
                continue
            activity = self._questions(b, idx, [item], phase='topical')
            if activity:
                self.session.setdefault('topical_used', []).append(chosen['identity'])
                return activity
        return None

    # ---------- practice (topical past papers + source-verified banks) ----------
    def source_bank(self) -> SourceQuestions:
        """Registered source-verified banks of this vault (loaded once; empty when none are registered)."""
        if self._source_questions is None:
            try:
                self._source_questions = SourceQuestions.load(self.vault.root)
            except (OSError, ValueError, KeyError):
                self._source_questions = SourceQuestions({})
        return self._source_questions

    def _plan_practice_queue(self, b: dict, minutes: int) -> None:
        """Pick the questions of one practice set now: unseen first, sources interleaved, held items never."""
        chapters, started_only, sources = b['chapters'], b['started_only'], b['sources']
        scope_set = set(chapters)
        excluded = {(r['identity'], r['chapter']) for r in self.topical_exclusions()}
        pools: dict[str, list[tuple]] = {}
        if 'topical' in sources:
            reserved, rows, taken = self._reserved_topical_ids(), [], set()
            for chapter in chapters:
                for item in self.packs.topical_items(chapter):
                    key = topicals.identity(item)
                    if not key or key in taken or key in reserved or (key, chapter) in excluded:
                        continue
                    if started_only and topicals.eligibility(item, chapter, self.state, self.packs)['status'] not in (
                            'solvable', 'supported'):
                        continue
                    taken.add(key)
                    seen = any(a in self.state['items_seen'] for a in self.packs._topical_aliases.get(key, {item['id']}))
                    rows.append((seen, '', {'source': 'topical', 'identity': key, 'chapter': chapter}))
            pools['topical'] = rows
        if 'source_verified' in sources:
            bank, rows = self.source_bank(), []
            courses = [b['course']] if b.get('course') else sorted({self.packs.subtopics[c]['spec'] for c in chapters})
            for course in courses:
                for item in bank.raw_items(course):
                    if not source_servable(item):
                        continue
                    subs = [self.packs.kcs[k]['subtopic'] for k in item['kcs'] if k in self.packs.kcs]
                    hit = next((c for c in chapters if c in subs), None)
                    if hit is None or (item['id'], hit) in excluded:
                        continue
                    if started_only and solvability.assess(self.state, self.packs, item)['status'] != 'solvable':
                        continue
                    rows.append((item['id'] in self.state.get('source_seen', {}), self.state.get('source_seen', {}).get(item['id'], ''),
                                 {'source': 'source_verified', 'id': item['id'], 'chapter': hit}))
            pools['source_verified'] = rows
        ordered = []
        for rows in pools.values():
            self.rng.shuffle(rows)
            rows.sort(key=lambda r: (r[0], r[1]))  # unseen first; seen ones oldest first
            ordered.append([r[2] for r in rows])
        queue = []
        while any(ordered):
            for rows in ordered:
                if rows:
                    queue.append(rows.pop(0))
        count = b.get('count') or max(1, minutes // 3)
        b['question_count'] = count
        b['question_queue'] = queue[:count]
        b['question_index'] = 0
        b['available'] = len(queue)

    def _practice_item(self, b: dict, entry: dict) -> dict | None:
        """The question a queue entry names, rechecked against current exclusions and eligibility."""
        chapter = entry['chapter']
        excluded = {(r['identity'], r['chapter']) for r in self.topical_exclusions()}
        if entry['source'] == 'topical':
            if (entry['identity'], chapter) in excluded:
                return None
            item = next((i for i in self.packs.topical_items(chapter) if topicals.identity(i) == entry['identity']), None)
            if item and b.get('started_only') and topicals.eligibility(item, chapter, self.state, self.packs)['status'] not in (
                    'solvable', 'supported'):
                return None
            return item
        if (entry['id'], chapter) in excluded:
            return None
        try:
            raw = self.source_bank().item(entry['id'])
        except KeyError:
            return None
        if not source_servable(raw) or (b.get('started_only') and solvability.assess(self.state, self.packs, raw)['status'] != 'solvable'):
            return None
        inst = source_instance(raw, self.vault.root)
        inst['_serving_chapter'] = chapter
        return inst

    def _paper_parts(self) -> dict[str, set[str]]:
        """Every part the bank holds for each printed structured question: {qid: {"a(i)", "c", ...}} (built once)."""
        if getattr(self, '_parts_of_paper_question', None) is None:
            found: dict[str, set[str]] = {}
            for chapter in self.packs.subtopics:
                for item in self.packs.topical_items(chapter):
                    source = item.get('source') or {}
                    if item.get('kind') == 'structured' and source.get('qid') and source.get('part'):
                        found.setdefault(source['qid'], set()).add(source['part'])
            self._parts_of_paper_question = found
        return self._parts_of_paper_question

    def _sibling_parts(self, b: dict, item: dict) -> list[dict]:
        """Other parts of the same printed question that the chosen topics also cover and that can still be served
        (not excluded, not disclosed, not already served or merged), in paper order."""
        source = item.get('source') or {}
        qid = source.get('qid')
        if item.get('kind') != 'structured' or not qid or not source.get('part'):
            return []
        excluded = {(r['identity'], r['chapter']) for r in self.topical_exclusions()}
        disclosed, used = self._disclosed_ids(), set(self.session.get('used', [])) | set(b.get('merged', []))
        found: dict[str, dict] = {}
        for chapter in b['chapters']:
            for other in self.packs.topical_items(chapter):
                other_source = other.get('source') or {}
                if (other['id'] == item['id'] or other['id'] in used or other.get('kind') != 'structured'
                        or other_source.get('qid') != qid or not other_source.get('part')
                        or (topicals.identity(other), chapter) in excluded
                        or (disclosed and self.packs.aliases_for(other) & disclosed)):
                    continue
                if b.get('started_only') and topicals.eligibility(other, chapter, self.state, self.packs)['status'] not in (
                        'solvable', 'supported'):
                    continue
                found.setdefault(other['id'], other)
        return sorted(found.values(), key=lambda o: question_display.part_key(o['source']['part']))

    @staticmethod
    def _merged_question(item: dict, siblings: list[dict]) -> dict:
        """One question made of several parts of the same printed question: the marks, mark points, answers and
        assessed ideas of every part, each point labelled with its part."""
        rows = sorted([item, *siblings], key=lambda o: question_display.part_key(o['source']['part']))
        merged = copy.deepcopy(item)
        merged['marks'] = sum(o.get('marks', 1) for o in rows)
        merged['kcs'] = list(dict.fromkeys(k for o in [item, *rows] for k in o['kcs']))
        merged['scheme'] = [{**pt, 'label': f"{question_display.part_label(o['source']['part'])} {pt.get('label', '')}".strip()}
                            for o in rows for pt in o.get('scheme', []) if isinstance(pt, dict)]
        merged['answer'] = "\n".join(f"{question_display.part_label(o['source']['part'])} {o.get('answer', '')}".strip()
                                    for o in rows)
        topical = merged.setdefault('topical', {})
        topical['requires'] = list(dict.fromkeys(k for o in rows for k in (o.get('topical') or {}).get('requires', [])))
        topical['chapters'] = list(dict.fromkeys(k for o in rows for k in (o.get('topical') or {}).get('chapters', [])))
        merged['difficulty'] = max(o.get('difficulty', 3) for o in rows)
        return merged

    def _step_practice_set(self, b: dict, idx: int) -> dict | None:
        """Serve the planned practice questions one at a time. Parts of one printed question that the chosen topics all
        cover are served together as one question ("Do (a)(i) and (c)", or "Do the whole question")."""
        disclosed = self._disclosed_ids()
        while b['question_index'] < len(b['question_queue']):
            entry = b['question_queue'][b['question_index']]
            b['question_index'] += 1
            item = self._practice_item(b, entry)
            if item is None or (disclosed and self.packs.aliases_for(item) & disclosed) or item['id'] in b.get('merged', []):
                continue
            siblings = self._sibling_parts(b, item)
            parts = None
            if siblings:
                parts = [o['source']['part'] for o in sorted([item, *siblings], key=lambda o: question_display.part_key(o['source']['part']))]
                whole = set(parts) >= self._paper_parts().get(item['source']['qid'], set())
                merged_ids = [o['id'] for o in siblings]
                item = self._merged_question(item, siblings)
                b.setdefault('merged', []).extend(merged_ids)
                self.session.setdefault('used', []).extend(merged_ids)
            self.session.setdefault('used', []).append(item['id'])
            n, p = self._number(item, b['kind'], 'practice', False, idx, None, item.get('_serving_chapter'))
            if parts:
                p.update(do_parts=parts, do_whole=whole, merged_items=merged_ids)
            p['practice_any'] = not b.get('started_only')
            if act := self._ask([(n, p)]):
                return act
        return None


    def _step_term_review(self, b: dict, idx: int) -> dict | None:
        from . import lesson
        while b.setdefault("i", 0) < len(b["terms"]):
            tid = b["terms"][b["i"]]
            b["i"] += 1
            entry = self.state.get("terms", {}).get(tid)
            if not entry or entry["kc"] not in self.packs.kcs:
                continue
            kc = entry["kc"]
            card = lesson.teach_card(self, kc)
            term = next((t for t in card.get("terms", []) if lesson.term_id(kc, t.get("term", "")) == tid), None)
            if not term:
                continue
            words = [w.strip(".,;:()") for w in term["meaning"].split() if len(w.strip(".,;:()")) > 3]
            notation = term.get("notation", "")
            notation = f" ({notation})" if isinstance(notation, str) and notation.strip() and notation.strip().lower() != "none" else ""
            item = {"id": tid, "term_id": tid, "kcs": [kc], "kind": "short", "difficulty": 2, "marks": 1,
                    "stem": f"What does {term['term']}{notation} mean?", "review_answer": term["meaning"], "rubric": [{"point": term["meaning"],
                    "keywords": [words[:4] or [term["term"]]]}]}
            if act := self._questions(b, idx, [item], phase="term_review", unassisted=True):
                act["say"] = "Recall this term in your own words."
                return act
        return None

    def _step_review(self, b: dict, idx: int) -> dict | None:
        while b.setdefault("i", 0) < len(b["kcs"]):  # keep going past ideas with no usable question
            batch = b["kcs"][b["i"]:b["i"] + 2]
            b["i"] += len(batch)
            items = [it for _, it in self._pick_batch(batch, b.get("target", 0.8))]
            if items:
                return self._questions(b, idx, items)
        return None

    def _step_practice(self, b: dict, idx: int) -> dict | None:
        return self._step_review(b, idx)

    def _step_exit(self, b: dict, idx: int) -> dict | None:
        while b.setdefault("i", 0) < len(b["kcs"]):
            batch = b["kcs"][b["i"]:b["i"] + 2]
            b["i"] += len(batch)
            items = [it for _, it in self._pick_batch(batch, 0.75)]
            if items:
                return self._questions(b, idx, items, unassisted=True)
        return None

    def _step_bracket(self, b: dict, idx: int) -> dict | None:
        st = b.setdefault("st", {kc: {"asked": [], "errors": [], "mis": [], "items": []} for kc in b["kcs"]})
        items = []
        used = {item for rec in st.values() for item in rec["items"]}
        for kc, rec in st.items():
            want = diagnose.next_difficulty([tuple(a) for a in rec["asked"]])
            it = diagnose.pick(self.packs, kc, want, used) if want else None
            if it:
                rec["items"].append(it["id"])
                used.add(it["id"])
                b.setdefault("asked_for", {})[it["id"]] = kc
                items.append(it)
            if len(items) == 2:
                break
        if items:
            act = self._questions(b, idx, items, phase="diagnose", unassisted=True)
            if not act:
                return None
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
            for kc, it in self._pick_batch(batch, 0.6):
                asked[it["id"]] = kc
                items.append(it)
            act = self._questions(b, idx, items, phase="sweep", unassisted=True)
            if act:
                act["say"] = ("A quick check of what you ticked in your Almanac: one question per idea, no hints until "
                              "answered. 'Don't know' is a fine answer." if b.get("claimed") else
                              "Test check: one question per syllabus point, no hints until answered. 'Don't know' is a fine answer.")
                return act
        res = b.get("res", {})
        if b.get("lesson_probe"):
            self.session["probe"] = res
            return None
        wrong = [kc for kc in b["kcs"] if kc in res and not res[kc]["ok"]]
        unsure = [kc for kc in b["kcs"] if kc in res and res[kc]["ok"] and (res[kc]["conf"] or 0) <= 2]
        if wrong:
            self.log({"type": "gaps", "add": wrong})
        if b.get("claimed"):  # the day's plan carries on; what was missed is a gap, taught first next time
            return None
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
            if it and (act := self._questions(b, idx, [it], phase="long")):
                act["say"] = ("Long question: full working, units and a final answer; then mark it against the scheme "
                              f"(handwritten on the iPad? name the PDF '{act['items'][0]['n']}.pdf').")
                return act
        return None

    def _retest_target(self, kc: str) -> int:
        chapter = self.packs.kcs.get(kc, {}).get("subtopic")
        excluded = {entry["identity"] for entry in self.state.get("topical_exclusions", [])
                    if entry["chapter"] == chapter}
        disclosed = self._disclosed_ids()
        items = [item for item in self.packs.items_for(kc)
                 if item["kind"] in ("mcq", "numeric", "expression", "short")
                 and (topicals.identity(item) or item["id"]) not in excluded
                 and not (disclosed and self.packs.aliases_for(item) & disclosed)
                 and (not item.get("topical") or topicals.eligibility(
                     item, chapter, self.state, self.packs, unassisted=True)["status"] == "solvable")]
        return 3 if any(i.get("template") for i in items) else min(
            3, len({topicals.identity(item) or item["id"] for item in items}))

    def _step_retest(self, b: dict, idx: int) -> dict | None:
        for kc in b["kcs"]:
            given = b.setdefault("given", {}).get(kc, 0)
            need = self._retest_target(kc) - given
            if need > 0:
                items = [item for _, item in self._pick_batch([kc] * min(2, need), 0.8, unassisted=True)]
                b["given"][kc] = given + len(items)
                if not items:
                    b["given"][kc] = self._retest_target(kc)
                    continue
                act = self._questions(b, idx, items, phase="retest", unassisted=True, exp=b["exp"][kc])
                if not act:
                    continue
                # an item may cover several ideas: its score belongs to the one retested
                for p in (*self.session["presented"].values(), *self.session.get("queue", {}).values()):
                    p["exp_kc"] = kc
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
                                    "problem": wk.get("problem"), "block_idx": idx,
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
                    item = faded.question_item(f, kc)
                    return self._questions(b, idx, [item], phase="faded")
            if phase == "challenge":
                it = self._pick(kc, 0.3)
                if it and (act := self._questions(b, idx, [it], phase="challenge", unassisted=True)):
                    act["say"] = "Productive-failure challenge: attempt cold, no hints. Any approach counts."
                    return act
            if phase == "refute":
                mis = [m for m in pack.get("misconceptions", [])
                       if m["id"] in self.state["kcs"].get(kc, {}).get("active_misconceptions", [])]
                if mis:
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

    def _faded_guards_allow_review(self, p: dict, *, allow_deferred: bool = False) -> bool:
        from . import deferred_notes
        s = self.session or {}
        guards = s.get('skipped_answer_guards') or {}
        stored = deferred_notes.outstanding(self.vault.tutor / 'state' / 'deferred-notes.json')
        if not guards and not stored:
            return True
        ident = _guard_identity(p)
        if (p.get('block') != 'skipped_retry' or set(guards) != set(stored) or ident not in guards
                or (not allow_deferred and set(guards) != {ident})):
            return False
        return all((group[ident].get('question') or {}).get('inst') == p.get('inst')
                   for group in (guards, stored))

    def marking_guards(self) -> dict:
        """Return the same skipped-answer guards used by tutor prompts."""
        from . import deferred_notes
        guards = {}
        if self.vault is not None:
            guards.update(deferred_notes.outstanding(self.vault.tutor / 'state' / 'deferred-notes.json'))
        guards.update((self.session or {}).get('skipped_answer_guards') or {})
        if (self.session or {}).get('suspended_for_retry'):
            guards['suspended-for-retry'] = {}
        return guards

    def begin_marking(self, n: int, working: str) -> str:
        """Persist a written attempt and return an opaque in-flight mark ticket."""
        session = self.session
        question = (session or {}).get('presented', {}).get(str(n))
        from . import deferred_notes
        guard_path = self.vault.tutor / 'state' / 'deferred-notes.json'
        ticket = uuid.uuid4().hex
        self._marking_tickets[ticket] = {
            'session': session, 'question': question, 'n': str(n),
            'guards': copy.deepcopy(self.marking_guards()),
            'stored_guards': deferred_notes.outstanding(guard_path),
        }
        if question and isinstance(working, str):
            question['saved_work'] = working
            question['pending_saved_mark'] = True
            self._save()
        return ticket

    def marking_status(self, ticket: str) -> str:
        """Check a returned judge result before it can affect a question."""
        state = self._marking_tickets.pop(ticket, None)
        if state is None:
            return 'stale'
        session = state['session']
        if (self.session is not session or
                (session or {}).get('presented', {}).get(state['n']) is not state['question']):
            return 'stale'
        from . import deferred_notes
        stored_changed = deferred_notes.outstanding(self.vault.tutor / 'state' / 'deferred-notes.json') != state['stored_guards']
        if stored_changed:
            return 'stored_changed'
        if self.marking_guards() != state['guards']:
            current = session or {}
            if current.get('skipped_answer_guards') or current.get('suspended_for_retry'):
                return 'retry_protected'
            return 'guards_changed'
        if 'whole_snapshot' in state:
            try:
                if self._whole_snapshot(state['question']) != state['whole_snapshot']:
                    return 'stale'
            except (OSError, ValueError, KeyError, TypeError):
                return 'stale'
        return 'ok'

    def cancel_marking(self, ticket: str) -> None:
        """Release an in-flight ticket after cancellation or failed marking."""
        self._marking_tickets.pop(ticket, None)

    def _whole_snapshot(self, p: dict) -> dict:
        if type(p.get('marks')) is not int or p['marks'] != p['inst'].get('marks'):
            raise ValueError('The official maximum changed.')
        return {'question': copy.deepcopy(p), 'working': p.get('saved_work'),
                'paper_work': p.get('whole_paper_work'),
                'media': topicals.whole_rubric_media(p['inst'], self.vault.root)}

    def whole_rubric(self, n: int, working: str, *, paper_attempt: bool = False) -> dict:
        """Disclose only the reviewed part rubric for an attempted, unprotected question."""
        p = (self.session or {}).get('presented', {}).get(str(n))
        if not p:
            return {'error': 'No open whole-rubric question.'}
        try:
            entry = topicals.whole_rubric(p['inst'])
            if entry is None:
                raise ValueError('No open whole-rubric question.')
            if p.get('ungraded_unavailable'):
                raise ValueError('This retry is unavailable for marking. Use the ungraded save or cancel path.')
            if type(paper_attempt) is not bool or whole_attempt_kind(working) == 'none':
                raise ValueError('A real written or explicitly confirmed paper attempt is required.')
            # Save work even if a guard or missing raster prevents marking.
            p['saved_work'] = working
            p['pending_saved_mark'] = True
            p.pop('whole_paper_work', None)
            self._save()
            if whole_attempt_kind(working) == 'paper' and not paper_attempt:
                return {'error': 'Confirm that you attempted this question on paper.',
                        'paper_confirmation_required': True}
            if (self.session.get('suspended_for_retry') or self.session.get('faded_cancel_intent')
                    or not self._faded_guards_allow_review(p)):
                raise ValueError('Retry the protected question before opening this rubric. Your work is saved.')
            if paper_attempt:
                p['whole_paper_work'] = working
            snapshot = self._whole_snapshot(p)  # verify every raster before returning any text
            ticket = self.begin_marking(n, working)
            self._marking_tickets[ticket]['whole_snapshot'] = snapshot
            import hashlib
            import json
            fingerprint = hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()
            self._marking_tickets[ticket]['rubric_fingerprint'] = fingerprint
            return {'n': n, 'point': entry['point'], 'max_marks': entry['whole_rubric']['max_marks'],
                    'media': list(entry['whole_rubric']['media']), 'ticket': ticket,
                    'say': 'Manual marking required; your work is saved and ungraded.'}
        except (OSError, ValueError, KeyError, TypeError) as exc:
            return {'error': str(exc) or 'The official rubric is unavailable; your work remains ungraded.'}

    def confirm_faded_attempt(self, n: int, working: str) -> dict:
        """Record an explicit attempt for the exact currently saved written work."""
        s = self.session or {}
        p = (s.get('presented') or {}).get(str(n))
        retry = bool(p and p.get('block') == 'skipped_retry')
        if (not p or not (p.get('phase') == 'faded' or p.get('inst', {}).get('written_faded'))
                or p.get('inst', {}).get('kind') != 'short'
                or not isinstance(working, str) or not working.strip() or p.get('saved_work') != working
                or (not retry and (s.get('suspended_for_retry') or s.get('queue')))
                or len(s.get('presented') or {}) != 1
                or not self._faded_guards_allow_review(p, allow_deferred=retry)):
            return {'ok': False, 'error': 'The saved work or protected questions changed.'}
        p['confirmed_faded_work'] = working
        self._save()
        return {'ok': True}

    # ---------- answers ----------
    def answer(self, text: str, judge: dict | None = None, your: dict | None = None,
               explanation: dict | None = None, *, manual_awards: dict | None = None) -> dict:
        """Mark answers. `your`: {n: the answer as the screen showed it}, so Now and the log quote it the same way;
        `explanation`: {n: the AI examiner's verdict}, which then stands in for the item's own explanation."""
        s = self.session
        if not s:
            return {"ok": False, "error": "no active session", "fix": "engine command: session start"}
        if s.get('faded_cancel_intent'):
            return {'ok': False, 'error': 'A saved cancellation needs recovery before continuing.'}
        has_judge_payload = judge is not None
        judge = {int(k): v for k, v in (judge or {}).items()}
        responses = grade.parse_responses(text)
        try:
            if manual_awards is not None and not isinstance(manual_awards, dict):
                raise ValueError('Invalid manual award mapping.')
            awards = {int(k): v for k, v in (manual_awards or {}).items()}
            if len(awards) != len(manual_awards or {}):
                raise ValueError('Duplicate manual award question.')
            # The ordinary compact parser folds lines and commas. The single
            # whole attempt uses its exact saved bytes, including mathematical
            # lines that resemble another compact response.
            if len(awards) == 1:
                number = next(iter(awards))
                work = s['presented'].get(str(number), {}).get('saved_work')
                if isinstance(work, str) and text == f'{number} = {work}':
                    responses = [{'n': number, 'kind': 'value', 'value': work, 'conf': None}]
            for number, award in awards.items():
                matches = [r for r in responses if r['n'] == number]
                p = s['presented'].get(str(number))
                if (len(matches) != 1 or not p or topicals.whole_rubric(p['inst']) is None
                        or matches[0]['kind'] != 'value' or number in judge
                        or whole_attempt_kind(matches[0]['value']) == 'none'
                        or not isinstance(award, dict) or set(award) != {'earned_marks', 'ticket'}
                        or not isinstance(award['ticket'], str)):
                    raise ValueError('Manual awards require the exact whole-rubric attempt and ticket; no IDK, pts or judge.')
        except (ValueError, TypeError, KeyError) as exc:
            return {'results': [{'error': str(exc)}], 'remaining': len(s['presented'])}
        your, explanation = {int(k): v for k, v in (your or {}).items()}, {int(k): v for k, v in (explanation or {}).items()}
        results = []
        for r in responses:
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
            try:
                whole = topicals.whole_rubric(inst) is not None
            except ValueError as exc:
                results.append({'n': r['n'], 'error': str(exc)})
                continue
            if whole and (r['n'] in judge or r['kind'] == 'points'
                          or r['kind'] == 'idk' and (manual_awards is not None or has_judge_payload)):
                results.append({'n': r['n'], 'error': 'Whole rubrics require an explicit human integer award.'})
                continue
            if whole and r['n'] in awards and (p.get('ungraded_unavailable')
                    or s.get('suspended_for_retry') or not self._faded_guards_allow_review(p)):
                # A rejected award must never enter the ordinary ungraded-retry
                # deferral branches below, which write events and resolve guards.
                self.cancel_marking(awards[r['n']]['ticket'])
                results.append({'n': r['n'], 'error': 'The retry or protected questions changed; this award cannot be recorded.'})
                continue
            if (inst.get('kind') == 'short' and p.get('phase') == 'faded' and r['kind'] == 'value'
                    and str(r['value']).strip().casefold().replace('’', "'").strip('?.! ') in
                    ('idk', 'dunno', "i don't know", 'i dont know', 'i do not know', 'skip',
                     'i have no idea', 'i have no clue', 'i am unsure', "i'm unsure", 'i cannot answer',
                     "i can't answer", 'i cant answer', 'not sure')):
                r = {**r, 'kind': 'idk', 'value': None, 'conf': None}
            if p.get('block') == 'deferred_judgment' and r['kind'] == 'idk':
                s.setdefault('deferred_judgments', []).insert(0, p)
                del s['presented'][key]
                results.append({'n': r['n'], 'judgment_postponed': True})
                continue
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
            expected = ('value',) if whole else _expected_kind(inst["kind"])
            if r["kind"] != "idk" and r["kind"] not in expected:
                results.append({"n": r["n"], "error": f"question {r['n']} expects {' or '.join(expected)}; "
                                                     "resend in the right form (it stays open)"})
                continue
            if inst.get('kind') == 'short' and (p.get('phase') == 'faded' or inst.get('written_faded')) and r['kind'] != 'idk':
                retry = p.get('block') == 'skipped_retry'
                confirmed = (p.get('confirmed_faded_work') == str(r['value'])
                             and (retry or not (s.get('suspended_for_retry') or s.get('queue')))
                             and len(s.get('presented') or {}) == 1
                             and self._faded_guards_allow_review(p, allow_deferred=retry))
            else:
                confirmed = True
            if not confirmed:
                # Until explicit attempt confirmation is implemented, never expose
                # the rubric merely because some text was entered.
                p['saved_work'] = str(r['value'])
                p['pending_saved_mark'] = True
                p.pop('confirmed_faded_work', None)
                self._save()
                results.append({'n': r['n'], 'attempt_confirmation_required': True,
                                'error': 'Your work is saved. Written faded marking is not yet available.'})
                continue
            guards = list((s.get('skipped_answer_guards') or {}).values())
            if p.get('ungraded_unavailable') and p.get('block') == 'skipped_retry' and r['kind'] == 'idk':
                event = self._pending_ungraded_event(key, p)
                if event:
                    results.append(self._defer_retry_attempt(key, p, event['response'], event=event))
                    continue
                if p.get('inst', {}).get('written_faded') and p.get('saved_work'):
                    from . import deferred_notes
                    ident = _guard_identity(p)
                    try:
                        snapshot = deferred_notes.guard_snapshot(self.vault.tutor / 'state' / 'deferred-notes.json', ident)
                        guard = s.get('skipped_answer_guards', {}).get(ident)
                        if (not snapshot or not guard or (guard.get('question') or {}).get('inst') != p['inst']
                                or (snapshot['guard'].get('question') or {}).get('inst') != p['inst']
                                or _protected_guard(guard) is None
                                or _protected_guard(guard) != _protected_guard(snapshot['guard'])):
                            raise ValueError('The saved question changed.')
                        session_work = (guard.get('question') or {}).get('saved_work')
                        stored_work = (snapshot['guard'].get('question') or {}).get('saved_work')
                        if session_work not in (stored_work, p['saved_work']):
                            self._save()
                            raise ValueError('Different saved drafts need recovery; all remain open.')
                        proposed = copy.deepcopy(snapshot['guard'])
                        proposed['question']['saved_work'] = p['saved_work']
                        s['faded_cancel_intent'] = {'n': key, 'ident': ident, 'operation': uuid.uuid4().hex,
                                                    'expected': snapshot['guard'], 'proposed': proposed,
                                                    'revision': snapshot['revision'], 'generation': snapshot['generation']}
                        self._save()
                        if not self._resume_faded_cancellation():
                            raise ValueError('The saved guard changed; your draft remains open.')
                        results.append({'n': r['n'], 'retry_cancelled': True})
                    except (OSError, ValueError) as exc:
                        results.append({'n': r['n'], 'error': str(exc) or 'Could not save the draft.'})
                    continue
                s['presented'].pop(key, None)
                results.append({'n': r['n'], 'retry_cancelled': True})
                continue
            if p.get('ungraded_unavailable') and p.get('block') == 'skipped_retry':
                response = str(r['value']).strip().casefold().replace('’', "'").strip('?.! ')
                if _idk_like(r['value']) and not (inst.get('written_faded') and response == 'no'):
                    event = self._pending_ungraded_event(key, p)
                    results.append(self._defer_retry_attempt(key, p, event['response'], event=event) if event
                                   else self._give_up_ungraded_retry(key, p))
                    continue
                results.append(self._defer_retry_attempt(key, p, str(r['value'])))
                continue
            sole_retry = (p.get('block') == 'skipped_retry' and len(guards) == 1 and not s.get('suspended_for_retry')
                          and isinstance(guards[0], dict) and (guards[0].get('question') or {}).get('inst') == inst)
            if ((inst['kind'] == 'short' or whole) and r['kind'] != 'idk' and not sole_retry
                    and (guards or s.get('suspended_for_retry'))):
                if p.get('block') == 'skipped_retry' and _guard_identity(p) in s.get('skipped_answer_guards', {}):
                    response = str(r['value']).strip().casefold().replace('’', "'").strip('?.! ')
                    if _idk_like(r['value']) and not (inst.get('written_faded') and response == 'no'):
                        r = {**r, 'kind': 'idk', 'value': None, 'conf': None}  # a give-up: marked and revealed below
                    else:
                        results.append(self._defer_retry_attempt(key, p, str(r['value'])))
                        continue
                else:
                    p['saved_work'] = str(r['value'])
                    results.append({'n': r['n'], 'needs_retry': True,
                                    'error': 'Your answer is saved. Retry the protected question before marking.'})
                    continue
            if whole and r['kind'] != 'idk':
                award = awards.get(r['n'])
                if award is None:
                    p['saved_work'] = str(r['value'])
                    p['pending_saved_mark'] = True
                    p.pop('whole_paper_work', None)
                    results.append({'n': r['n'], 'pending_manual': True,
                                    'say': 'Manual marking required; your work is saved and ungraded.'})
                    continue
                state = self._marking_tickets.get(award['ticket'], {})
                try:
                    g = grade.grade_human_whole(inst, award['earned_marks'])
                    if (state.get('n') != key or 'whole_snapshot' not in state
                            or p.get('saved_work') != r['value'] or not self._faded_guards_allow_review(p)
                            or s.get('suspended_for_retry') or self.marking_status(award['ticket']) != 'ok'):
                        raise ValueError('The attempt, rubric or protected questions changed; reopen the manual rubric.')
                except (ValueError, TypeError, KeyError) as exc:
                    self.cancel_marking(award['ticket'])
                    results.append({'n': r['n'], 'error': str(exc)})
                    continue
                g['human_award'] = {'version': 1, 'earned_marks': award['earned_marks'],
                                    'max_marks': inst['marks'], 'marker': 'human',
                                    'rubric_fingerprint': state['rubric_fingerprint']}
            else:
                g = grade.grade_item(inst, r)
            if r["n"] in judge and r["kind"] != "idk":
                try:
                    sc = float(judge[r["n"]])
                except (TypeError, ValueError):
                    sc = math.nan
                if math.isnan(sc):
                    results.append({"n": r["n"], "error": f"judge score {judge[r['n']]!r} for question {r['n']} is not "
                                    "a number; resend with judge {n: score 0..1} (it stays open)"})
                    continue
                sc = min(1.0, max(0.0, sc))  # a 75 meant as 75% must not count as 75 right answers
                g.update(score=sc, correct=sc >= model.SUCCESS, needs_judgement=False)
            elif inst["kind"] == "short" and g["needs_judgement"]:
                results.append({"n": r["n"], "pending_judgement": True, "matched_score": g["score"],
                                "unmatched": g.get("unmatched"), "rubric": [pt["point"] for pt in inst["rubric"]],
                                "say": "Judge every rubric point against their answer (keyword matches are only a hint: a "
                                       "swapped or negated statement contains them too), then resend with judge "
                                       "{n: score 0..1}."})
                continue
            reviewed = explanation.get(r["n"]) if r["kind"] != "idk" else None
            results.append(self._record(key, p, r, g, reviewed_explanation=reviewed))
        done = [fb for fb in results if fb.get("event")]
        for fb in done:
            if (fb["n"] in explanation and not fb.get("answer_withheld")
                    and not fb.get('feedback_withheld') and not fb.get('attempt_saved')):
                fb["explanation"] = explanation[fb["n"]]
                if fb.get("phase") == "form_check":
                    for recent in s.get("recent", []):
                        if recent.get("event") == fb["event"]:
                            recent["explanation"] = fb["explanation"]
            fb["your"] = your.get(fb["n"]) or fb["your"]
            self._post(self._feedback_item(fb, fb["your"]))
        if done:
            s["now"] = {"activity": "feedback"}
        self._save()
        if done:  # the learner may pause here: send the finished session even inside the throttle window
            self._sync_almanac(force=True)
        return {"results": results, "remaining": len(s["presented"])}

    @staticmethod
    def _feedback_item(fb: dict, your: str) -> dict:
        role, title, body = views.feedback_card(fb, your)
        return {"kind": role, "title": title, "text": body}

    def _typical_seconds(self, subject: str | None) -> float | None:
        sec, marks = self.state["traits"]["time"].get(subject or "", [0.0, 0])
        return sec / marks if marks >= 10 else None

    def blurt(self, subtopic: str, text: str) -> dict:
        """Score a free-recall attempt, pull forgotten ideas forward for review, and keep a record in Lessons."""
        if self.marking_guards():
            return {"ok": False, "error": "A skipped answer is protected. Retry it before checking your blurt."}
        if (permission := self.ai_help(given=False)).get("refused"):
            return {"ok": False, "error": permission["refused"]}
        from . import blurt as blurt_mod, lesson
        res = blurt_mod.score(self.packs, subtopic, text)
        self.log({"type": "blurt", "subtopic": subtopic, "recalled": res["recalled"], "missed": res["missed"],
                  "words": res["words"]})
        title = self.packs.subtopics.get(subtopic, {}).get("title", subtopic)
        n, total = len(res["recalled"]), len(res["ideas"])
        missed = res["missed"]
        scheduled = [kc for kc in missed if self.state["kcs"].get(kc, {}).get("fsrs")]
        unscheduled = [kc for kc in missed if kc not in scheduled]
        if scheduled and unscheduled:
            review_note = ("Ideas already scheduled for Review that you left out are due next time. Ideas without a "
                           "review schedule aren't added to Review; work through them in a lesson.")
        elif scheduled:
            review_note = "Ideas already scheduled for Review that you left out are due next time."
        elif unscheduled:
            review_note = "Ideas without a review schedule aren't added to Review; work through them in a lesson."
        else:
            review_note = "You recalled every idea. Nothing was added to Review."
        res["cards"] = [("you", "You wrote", text),  # beside what it is checked against
                        ("good" if n == total else "hint", f"You recalled {n} of {total} ideas",
                         review_note)]
        res["cards"] += [("good" if v["recalled"] else "bad", f"{'✓' if v['recalled'] else '✗'} {v['title']}",
                          "You remembered this." if v["recalled"] else  # a line, not an empty box under the title
                          lesson.teach_card(self, kc).get("note", "") or "You left this out.")
                         for kc, v in res["ideas"].items()]
        log = views.LessonLog.create(self.vault.root, f"Blurt - {title}", self.now())
        for c in res["cards"]:  # the terminal draws these same cards
            log.card(*c)
        if self.session is None:  # Now shows them too, as it shows the screen
            views.write_now(self.vault.root, f"Blurt · {title} · {self.now():%H:%M}", [views.card_block(*c) for c in res["cards"]])
        res["log"] = log.rel
        return res

    def tag(self, event_id: str, code: str) -> dict:
        """Your own verdict on why an answer went wrong (careless slip, misread, didn't know, wrong method…)."""
        code = code.upper()
        if code not in grade.ERROR_CODES:
            return {"ok": False, "error": f"unknown error code {code}", "fix": f"Use one of {', '.join(grade.ERROR_CODES)}."}
        events = list(self.vault.events())
        answer = next((e for e in events if e.get("id") == event_id and e["type"] == "answer"), None)
        if not answer:
            return {"ok": False, "error": "no answer with that id"}
        if answer.get("regraded"):  # replay drops a reason given for a miss the re-mark found was no miss
            return {"ok": False, "error": "already re-marked"}
        context = {"subject": answer.get("subject", "misc"), "error": answer["grade"].get("error"),
                   "kcs": [] if answer.get("term_id") else list(answer.get("kcs", []))}
        previous = next((e for e in reversed(events) if e["type"] == "tag" and e.get("target") == event_id
                         and e.get("error") in grade.ERROR_CODES and isinstance(e.get("answer_context"), dict)), None)
        if previous:
            context["error"] = previous["error"]
        revision = 1 + max((e["revision"] for e in events if e["type"] == "tag" and e.get("target") == event_id
                            and isinstance(e.get("answer_context"), dict)
                            and type(e.get("revision")) is int and e["revision"] > 0), default=0)
        return {"ok": True, "event": self.log({"type": "tag", "target": event_id, "error": code, "revision": revision,
                                                "answer_context": context})["id"]}

    def regrade(self, event_id: str, why: str, by: str = "ai") -> dict:
        """Count an answer as right after all: a second marker found it correct though the program marked it wrong
        (the same quantity said another way, an equivalent form, a wrong answer key). The first mark stays in the
        log with the re-mark beside it; everything worked out from the log (your record, reviews, the mistake
        journal, the Almanac colours) follows the re-mark. For the answer just marked, the session is put back as it
        was before the wrong mark and the answer recorded as right: no repair step, relearning or gap comes of it."""
        events = list(self.vault.events())
        answer = next((e for e in events if e.get("id") == event_id and e["type"] == "answer"), None)
        if answer and (answer.get('human_award') or topicals.whole_rubric(answer.get('question', {})) is not None):
            return {'ok': False, 'error': 'Whole-rubric marks require a human; automated re-marking is unavailable.'}
        if not answer or model.counts_as_right(answer["grade"]):
            if answer and answer.get("regraded") and self._reconcile_correction_totals(events):
                self._save()
            return {"ok": False, "error": "no answer marked wrong with that id"}
        if answer.get("response") == "don't know" and answer.get("key") == "":
            return {"ok": False, "error": "a skipped question cannot be re-marked without an attempt"}
        last, self._last_mark = self._last_mark, None
        self.log({"type": "regrade", "target": event_id, "item": answer["item"], "by": by, "why": why,
                  "grade": dict(RIGHT)})
        s, fb = self.session, None
        if s and s.get("id") == answer.get("session"):
            if last and last["event"] == event_id:
                if (added := [kc for kc in self.state["gaps"] if kc not in last["gaps"]]):
                    self.log({"type": "gaps", "remove": added})
                for k, v in last["before"].items():
                    if v is _ABSENT:
                        s.pop(k, None)
                    else:
                        s[k] = v
                fb = self._mark(last["key"], s["presented"][last["key"]], last["r"],
                                {**RIGHT, "needs_judgement": False}, redo=answer)
            else:  # an earlier answer: the session keeps its course; its score and what the AI tutor is shown change
                self._reconcile_correction_totals(self.vault.events())
                for q in s.get("recent", []):
                    if q.get("n") == answer.get("n"):
                        q.update(correct=True, partial=False, detail=None)
            if (log := self._lesson_log()):  # as the terminal says it
                log.card("tutor", "Re-marked: correct ✓", f"{why}\n\nIt now counts as right in your record.")
            self._save()
        self._sync_almanac(force=True)
        return {"ok": True, **({"feedback": fb} if fb else {})}

    def _record(self, key: str, p: dict, r: dict, g: dict, reviewed_explanation: str | None = None) -> dict:
        """Record a marked answer, and remember what that changed in the session, so a re-mark can redo it."""
        before, gaps = copy.deepcopy(self.session), list(self.state["gaps"])
        fb = self._mark(key, p, r, g, reviewed_explanation=reviewed_explanation)
        now = self.session
        self._last_mark = {"event": fb["event"], "key": key, "r": r, "gaps": gaps,
                           "before": {k: before.get(k, _ABSENT) for k in before.keys() | now.keys()
                                      if before.get(k, _ABSENT) != now.get(k, _ABSENT)}}
        return fb

    def _mark(self, key: str, p: dict, r: dict, g: dict, redo: dict | None = None,
              reviewed_explanation: str | None = None) -> dict:
        """What a marked answer does to the session and the log. `redo` is the answer's event when it is recorded
        again after a re-mark: it is in the log and the lesson notes already."""
        s, inst = self.session, p["inst"]
        assessed = list(dict.fromkeys(p["kcs"]))  # old saved attempts can predate pack admission normalization
        seconds = (self.now() - datetime.fromisoformat(p["shown_at"])).total_seconds()
        kc0 = assessed[0]
        known = kc0 in self.packs.kcs
        p_exp = model.p_correct(self.state["kcs"].get(kc0, {}).get("theta", 0.0), p["difficulty"])
        typical = self._typical_seconds(p["subject"])
        slip = bool(not g["correct"] and r["kind"] != "idk" and not g.get("misconception") and p_exp >= 0.85
                    and typical and seconds <= 0.5 * typical * p["marks"])
        conf_stats = self.state["traits"]["calibration"].get("by_conf", {}).get(str(r.get("conf")))
        credit = sorted({pre for kc in assessed if kc in self.packs.kcs for pre in self.packs.kc(kc).get("prereqs", [])
                         if self.state["kcs"].get(pre, {}).get("fsrs")})
        give_up = (r["kind"] == "idk"
                   and (p.get("block") == "skipped_retry" or p.get("phase") == "skipped_retry"))
        answer_withheld = r["kind"] == "idk" and not give_up and (
            topicals.whole_rubric(inst) is not None or s.get("mode") == "lesson" or
            p.get("phase") in ("form_check", "term_review", "skipped_retry") or
            (p.get('phase') == 'faded' and inst['kind'] == 'short'))
        deferred_path = self.vault.tutor / 'state' / 'deferred-notes.json'
        if answer_withheld or s.get("skipped_answer_guards") or deferred_path.exists():
            # A generated item can reuse its ID with different values; protect each instance separately.
            guard_id = _guard_identity(p)
            guards = s.setdefault("skipped_answer_guards", {})
            if answer_withheld:
                guards[guard_id] = {"key": _display_answer(inst), "kind": inst["kind"],
                                     "question": copy.deepcopy(p),
                                     "numeric": inst.get("answer") if inst["kind"] == "numeric" else None,
                                     "short_answers": ([inst.get("review_answer", "")] +
                                                       [point.get("point", "") for point in inst.get("rubric", [])]
                                                       if inst["kind"] == "short" else [])}
            elif give_up or r["kind"] != "idk":
                guards.pop(guard_id, None)
        source_only = inst.get("source_verified") is True  # source-verified practice: tagged, counts towards mastery
        ev = redo or self.log({"type": "answer", "session": s["id"], "n": int(key), "item": p["item"], "kcs": assessed,
                       "subject": p["subject"],
                       "difficulty": p["difficulty"], "conf": r.get("conf"), "hinted": p["hinted"], "seconds": round(seconds),
                       "marks": p["marks"], "grade": {k: g[k] for k in ("correct", "score", "error", "misconception")},
                       "credit": credit, "pos": s["answered"],
                       **({"source_verified": True} if source_only else {}), "block": p["block"], "phase": p["phase"],
                       "params": inst.get("params"), "response": r["value"] if r["kind"] != "idk" else "don't know",
                       "question": {field: inst[field] for field in ("stem", "options", "image", "images", "source", "marks",
                                                                     "explanation", "kind",
                                                                     *(("scheme",) if topicals.whole_rubric(inst) is not None else ())) if field in inst},
                       **({"human_award": g["human_award"]} if g.get("human_award") else {}),
                       **({'postponement_id': p['postponement_id']} if p.get('postponement_id') else {}),
                       **({'merged_items': p['merged_items']} if p.get('merged_items') else {}),
                       **({'reviewed_explanation': reviewed_explanation} if reviewed_explanation and not answer_withheld else {}),
                       **({"term_id": inst["term_id"]} if inst.get("term_id") else {}),
                       "key": "" if answer_withheld else _display_answer(inst),
                       **({} if inst.get("source") else {"stem": inst.get("stem", "")}),
                       **({"retention": policy.target_retention(self.state, self.packs, kc0, self.now())} if known else {}),
                       **({"slip_likely": True} if slip else {})})
        if answer_withheld:
            from . import deferred_notes
            deferred_notes.hold(deferred_path, guard_id, guards[guard_id])
        elif (give_up or r['kind'] != 'idk') and deferred_path.exists():
            from . import deferred_notes
            deferred_notes.resolve(deferred_path, guard_id)
        if not redo:
            self._audit("answer", int(key), inst)
        del s["presented"][key]
        if deferred_path.exists():
            self._flush_deferred_notes()
        s.setdefault("kcs_answered", []).extend(k for k in assessed if k not in s["kcs_answered"])
        partial = g["correct"] and g["score"] < model.SUCCESS  # right value, mark lost (units, s.f.)
        if partial:
            g = {**g, "correct": False}
        s["answered"] += 1
        s["correct"] += 1 if g["correct"] else 0
        s["marks_total"] = s.get("marks_total", 0) + p["marks"]  # exam marks as well as whole questions (Q-017)
        s["marks_earned"] = round(s.get("marks_earned", 0) + g["score"] * p["marks"], 2)
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
            kc = inst.get("_serving_kc") or blk.get("asked", {}).get(p["item"], p["kcs"][0])
            blk.setdefault("res", {})[kc] = {"ok": g["correct"], "conf": r.get("conf")}
        if p["unassisted"] and g["correct"] and not p["hinted"] and not inst.get("term_id"):
            closed = [kc for kc in assessed if kc in self.state["gaps"]]
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
            score = {"type": "exp_score", "exp": p["exp"], "kc": kc, "score": round(sum(scores) / len(scores), 3)}
            # recovering an answer whose score reached the log before the app stopped: it is not logged twice
            if len(scores) >= self._retest_target(kc) and not (redo and any(
                    all(e.get(k) == v for k, v in score.items()) for e in self.vault.events())):
                self.log(score)
        fb = {"n": int(key), "event": ev["id"], "correct": g["correct"], "partial": partial, "score": g["score"],
              "marks": p["marks"],
              "error_code": g["error"], "response": ev["response"], "conf": r.get("conf"),
              "answer": _display_answer(inst), "explanation": inst.get("explanation"),
              "needs_judgement": g["needs_judgement"], "detail": None if r["kind"] == "idk" else g.get("detail")}
        if reviewed_explanation:
            fb['explanation'] = reviewed_explanation
        if p.get("phase") == "form_check":
            fb["phase"] = "form_check"
            if type(inst.get("form_index")) is int:
                fb["form_index"] = inst["form_index"]
            if reviewed_explanation:
                fb["explanation"] = reviewed_explanation
        if answer_withheld:
            fb.update(answer="", explanation=None, answer_withheld=True)
        s.setdefault("recent", []).append({**{k: fb[k] for k in ("n", "event", "correct", "partial", "detail", "response",
                                                                 "answer", "explanation", "conf")},
                                           "stem": inst.get("stem", ""), "options": inst.get("options"),
                                           "image": inst.get("image"), "kind": inst["kind"], "marks": inst.get("marks", 1),
                                           "unassisted": p.get("unassisted"),
                                           **({"source": inst["source"].get("ref")}
                                              if inst.get("source", {}).get("type") == "past" else {})})
        del s["recent"][:-4]  # the last few marked questions: what the AI tutor can be asked about
        if inst.get("tier") == "extra" and not answer_withheld:
            fb["official_key_only"] = True
            if inst.get("examiner"):
                fb["examiner"] = inst["examiner"]
        if g.get("misconception") and p["kcs"][0] in self.packs.kcs:
            fb["misconception"] = self.packs.misconception(self.packs.kc(p["kcs"][0])["subtopic"], g["misconception"])
        your = ("?" if r["kind"] == "idk" else f"{r['value']}" if r["kind"] != "points" else
                "points " + ",".join(map(str, r["value"])))
        fb["your"] = your  # Now and the log quote it when answer() posts the card, with everything below added
        if redo:
            # Recovery normally replays an event whose lesson callout was already appended. If the process stopped
            # between the event append and transcript append, restore that permanent callout exactly once.
            if log := self._lesson_log():
                log.recover_answer(fb, your)
        if p["block"] == "node" and p["phase"] in ("check", "form_check") and p["block_idx"] is not None:
            self._node_check_result(s["blocks"][p["block_idx"]], g, fb, "?" if r["kind"] == "idk" else str(r["value"]))
        elif p.get('block') == 'deferred_judgment' and p.get('phase') in ('check', 'form_check'):
            origin = p.get('deferred_node') or {}
            index = origin.get('index')
            if (origin.get('session') == s.get('id') and type(index) is int
                    and 0 <= index < len(s['blocks']) and s['blocks'][index].get('kind') == 'node'
                    and s['blocks'][index].get('kc') == origin.get('kc')):
                self._node_check_result(s['blocks'][index], g, fb,
                                        '?' if r['kind'] == 'idk' else str(r['value']))
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
        if (s.get('skipped_answer_guards') or s.get('suspended_for_retry')) and not answer_withheld and not give_up:
            pending = s.setdefault('deferred_feedback', [])
            if not any(row.get('event') == fb['event'] for row in pending):
                pending.append(copy.deepcopy(fb))
            s['recent'][-1].update(answer='', explanation=None, detail=None, correct=None, partial=None)
            fb = {'n': fb['n'], 'event': fb['event'], 'your': fb['your'], 'feedback_withheld': True}
        return fb

    def save_structured_draft(self, n: int, work: str) -> dict:
        p = (self.session or {}).get('presented', {}).get(str(n))
        if not p or p['inst'].get('kind') != 'structured' or not isinstance(work, str) or not work.strip():
            return {'ok': False, 'error': 'Cannot save this working.'}
        p['saved_work'] = work
        self._save()
        return {'ok': True}

    def scheme(self, n: int) -> dict:
        p = (self.session or {}).get("presented", {}).get(str(n))
        if not p or p["inst"]["kind"] != "structured":
            return {"error": "no open structured question with that number"}
        if topicals.whole_rubric(p["inst"]) is not None:
            return {"error": "Use guarded whole-rubric disclosure after a real attempt."}
        if self.session.get('skipped_answer_guards'):
            return {'error': 'A skipped answer is protected, so the marking scheme is withheld.'}
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
        rows = [(m[1].lower(), float(m[2]), float(m[3])) for m in
                re.finditer(r"(\w+)\s*=\s*(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)", text)]
        nonfinite = [q for q, sc, oo in rows if not math.isfinite(sc) or not math.isfinite(oo)]
        if nonfinite:
            return {"ok": False, "error": f"marks must be finite numbers: {', '.join(nonfinite)}",
                    "fix": "Give each question as got/out-of, e.g. 1a=2/3."}
        got = {q: (sc, oo) for q, sc, oo in rows}
        bad = [q for q, (sc, oo) in got.items() if oo <= 0 or sc > oo]
        if bad:
            return {"ok": False, "error": f"scores above the marks available: {', '.join(bad)}",
                    "fix": "Give each question as got/out-of, e.g. 1a=2/3."}
        unknown = sorted(set(got) - set(qmap))
        if not set(got) & set(qmap):  # nothing readable for this paper: no result, or it would count as sat
            return {"ok": False, "error": "no marks for a question of this paper could be read",
                    "unknown_questions": unknown, "questions": [q["q"] for q in paper["questions"]],
                    "fix": "Give each question as got/out-of, e.g. 1a=2/3, 1b=0/2."}
        total, maximum = sum(v[0] for q, v in got.items() if q in qmap), sum(v[1] for q, v in got.items() if q in qmap)
        whole = max(paper.get("marks") or 0, maximum)  # a paper marked in part is not full marks
        if not all(math.isfinite(value) for value in (total, maximum, whole)):
            return {"ok": False, "error": "total marks must be finite numbers",
                    "fix": "Give each question as got/out-of, e.g. 1a=2/3."}
        percent = round(100 * (total / whole), 1) if whole else None
        sid = "paper-" + uuid.uuid4().hex[:6]
        per_kc: dict[str, list[float]] = {}
        for q, (score, out_of) in got.items():
            if q not in qmap:
                continue
            meta = qmap[q]
            kcs = list(dict.fromkeys([k for k in meta["kcs"] if k in self.packs.kcs] or meta["kcs"]))
            frac = score / out_of if out_of else 0.0
            self.log({"type": "answer", "session": sid, "item": f"{paper_id}:{q}", "kcs": kcs,
                      "subject": self.packs.kc(kcs[0])["subject"] if kcs and kcs[0] in self.packs.kcs else None,
                      "difficulty": 4, "conf": None, "hinted": False, "marks": out_of, "block": "paper", "phase": None,
                      "grade": {"correct": frac >= 1.0, "score": round(frac, 3), "error": None, "misconception": None},
                      "credit": [], "pos": 0, "response": f"{score:g}/{out_of:g}"})
            for k in kcs:
                per_kc.setdefault(k, []).append(frac)
        self.log({"type": "paper_result", "paper": paper_id, "score": total, "max": maximum, "session": sid})
        weakest = sorted(({"kc": k, "score": round(sum(v) / len(v), 2)} for k, v in per_kc.items()), key=lambda x: x["score"])
        return {"paper": paper_id, "score": total, "max": maximum, "partial": maximum < whole,
                "percent": percent,
                "weakest": weakest[:5], "unknown_questions": unknown, "session": sid}

    def _topic_ai_cache(self) -> tuple:
        path = self.vault.tutor / 'state' / 'topic-ai.json'
        try:
            data = read_json(path, {})
        except ValueError:
            data = {}
        return path, data if isinstance(data, dict) else {}

    def _identify_topics(self, p: dict) -> dict:
        """Name the ideas of an untagged question: cached per (item, content), asked of the AI at most twice.
        {'status': 'ok', 'kcs', 'confidence', 'subtopics', 'reason'} | {'status': 'pending'|'unverified', 'message'}."""
        import hashlib
        inst = p['inst']
        source = inst.get('source') if isinstance(inst.get('source'), dict) else {}
        chapter = p.get('serving_chapter')
        known = next((k for k in p.get('kcs') or [] if k in self.packs.kcs), None)
        course = (inst.get('course') or source.get('course') or self.packs.subtopics.get(chapter, {}).get('spec')
                  or (self.session or {}).get('course') or (self.packs.kcs[known]['spec'] if known else None)
                  or topicals.official_course(source))
        rows = [(k, v['title']) for k, v in self.packs.kcs.items() if v.get('spec') == course]
        if not course or not rows:
            return {'status': 'unverified', 'message': 'The course of this question is unknown, so its topics cannot be named.'}
        options = inst.get('options') if isinstance(inst.get('options'), dict) else {}
        text = '\n'.join([str(inst.get('stem') or ''), *(f'{k}. {v}' for k, v in options.items())]).strip()
        refs = list(dict.fromkeys(([inst['image']] if inst.get('image') else []) + list(inst.get('images') or [])))
        paths, digests = [], []
        if refs:
            from .asset_library import AssetLibrary
            try:
                library = AssetLibrary(self.vault.root)
                for ref in refs:
                    path = library.resolve(ref)
                    paths.append(str(path))
                    digests.append(hashlib.sha256(path.read_bytes()).hexdigest())
            except (OSError, ValueError, KeyError):
                return {'status': 'pending', 'message': 'The question image could not be read, so its topics cannot be named yet.'}
        key = f"{p['item']}:{course}:{engine_prompts.content_hash(text, digests)}"
        path, cache = self._topic_ai_cache()
        record = cache.get(key)
        if record is None:
            if self.topic_ai is None:
                return {'status': 'pending', 'message': 'This question has no topic tags. Turn on AI help so its topics can be identified; it stays open.'}
            request = {'purpose': 'topic_identification', 'course': course, 'cheapest': True,
                       'system': engine_prompts.TOPIC_SYSTEM, 'schema': engine_prompts.TOPIC_SCHEMA, 'images': paths,
                       'prompt': engine_prompts.topic_prompt(course, rows, text, bool(paths))}
            parsed, unavailable = self._ask_topics(request, {k for k, _ in rows})
            if unavailable:
                return {'status': 'pending', 'message': 'AI help is unavailable, so this question\'s topics cannot be identified yet; it stays open.'}
            record = {**(parsed or {'kcs': [], 'confidence': 0.0, 'subtopics': [], 'reason': '', 'rejected': True}),
                      'course': course, 'at': self.now().isoformat()}
            cache[key] = record
            write_json(path, cache)
        if record.get('rejected') or not record.get('kcs') or record.get('confidence', 0) < engine_prompts.MIN_CONFIDENCE:
            return {'status': 'unverified', 'message': 'The topics of this question could not be identified reliably; it stays open.'}
        return {'status': 'ok', 'kcs': list(record['kcs']), 'confidence': record['confidence'],
                'subtopics': list(record.get('subtopics') or []), 'reason': record.get('reason') or ''}

    def _ask_topics(self, request: dict, valid_ids: set) -> tuple[dict | None, bool]:
        """One AI call; an invalid reply is asked once more with the problem appended.
        Returns (parsed reply or None, AI unavailable)."""
        try:
            reply = self.topic_ai(request)
        except Exception:
            return None, True
        if reply is None or reply == '':
            return None, True
        problem = engine_prompts.topic_reply_problem(reply, valid_ids)
        if problem is None:
            return engine_prompts.parse_topic_reply(reply, valid_ids), False
        retry = {**request, 'prompt': engine_prompts.topic_retry_prompt(request['prompt'], problem)}
        try:
            reply = self.topic_ai(retry)
        except Exception:
            return None, True
        if reply is None or reply == '':
            return None, True
        return engine_prompts.parse_topic_reply(reply, valid_ids), False

    def check_solvable(self, n: int) -> dict:
        """"Can I solve this?"  Deterministic against the learner's STARTED topics (see tutorlib.solvability).
        Returns {n, status: solvable|adapted|skipped|unverified|topic_pending, message, missing, given, adapted_prompt,
        topic, skipped, ...}; the old keys topics/basis remain.  Never reveals the key of an open question."""
        if (self.session or {}).get('faded_cancel_intent'):
            return {'n': n, 'status': 'unverified', 'topics': [], 'missing': [], 'given': [], 'adapted_prompt': None,
                    'topic': None, 'skipped': False,
                    'message': 'Finish recovering the saved draft before checking this question.'}
        p = (self.session or {}).get("presented", {}).get(str(n))
        blank = {'n': n, 'topics': [], 'missing': [], 'given': [], 'adapted_prompt': None, 'topic': None, 'skipped': False}
        if not p:
            return {**blank, "status": "unverified", "message": "This question is no longer open."}
        inst = p['inst']
        reviewed = 'topical' in inst
        chapter = p.get('serving_chapter') or self.packs.kcs.get((p.get('kcs') or [''])[0], {}).get('subtopic')
        if reviewed and topicals.eligibility(inst, p.get('serving_chapter'), self.state, self.packs, p['unassisted'])['status'] == 'unverified':
            message = 'Prerequisite metadata is unverified; this question remains open.'
            self.show("notice", message, "Can I solve this?")
            return {**blank, 'status': 'unverified', 'message': message, 'basis': 'reviewed_topical'}
        res = solvability.assess(self.state, self.packs, inst, serving_chapter=p.get('serving_chapter'), unassisted=p['unassisted'])
        basis = 'reviewed_topical' if reviewed else 'course_graph'
        if res['needs_topic']:
            found = self._identify_topics(p)
            if found['status'] == 'ok':
                res = solvability.assess(self.state, self.packs, inst, kcs=found['kcs'], serving_chapter=p.get('serving_chapter'),
                                         unassisted=p['unassisted'], topic_source='ai')
                basis = 'ai_topics'
            else:
                res = {**res, 'status': 'topic_pending' if found['status'] == 'pending' else 'unverified',
                       'message': found['message']}
        status = res['status']
        skippable = reviewed or inst.get('source_verified') is True or p.get('block') in ('topical', 'practice_set')
        message = res['message']
        if status == 'skipped' and not skippable:
            own = {self.packs.kcs[k]['subtopic'] for k in (inst.get('kcs') or []) if k in self.packs.kcs}
            if own and not own & set(res['missing_topics']):
                # The question's own topics are started; only its recorded prerequisites are missing.
                status = 'unavailable'
                message = 'Missing recorded topics: ' + ', '.join(k.split('-', 1)[-1] for k in res['missing_topics']) + \
                          '. This question remains open.'
            else:
                status, message = 'unverified', message.replace('Skipped for now: ', 'Not yet possible: ') + ' This question stays open.'
        elif status == 'skipped':
            ident = topicals.identity(inst) or p["item"]
            if chapter:
                self.log({"type": "topical_exclude", "identity": ident, "chapter": chapter,
                          "missing": res['missing_topics'],
                          "reason": "Missing started topics for every part of this question."})
            if p.get('pending_saved_mark'):
                self._remember_pending_node(p)
                p.update(block='deferred_judgment', block_idx=None, exp=None)
                self.session.setdefault('deferred_judgments', []).append(p)
            del self.session["presented"][str(n)]
            self._save()
            if p.get('pending_saved_mark'):
                message += " Your submitted working remains saved for later marking."
        elif status == 'adapted' and res['given']:
            p['hinted'] = True  # facts were given: assisted practice, never independent performance
            p['support_given'] = list(res['given'])
            self._save()
        if status == 'adapted':
            p['adapted_prompt'] = res['adapted_prompt']
        if not reviewed:
            message = 'Course graph prerequisite assessment (not reviewed question requirements). ' + message
        out = {**res, 'n': n, 'status': status, 'message': message, 'basis': basis, 'skipped': status == 'skipped',
               'topics': [k.split("-", 1)[-1] for k in (res['missing_topics'] or res.get('requires', []))]}
        self.show("notice", message + ('\n' + '\n'.join(res['given']) if status == 'adapted' and res['given'] else ''),
                  "Can I solve this?")
        return out

    def topical_exclusions(self, chapter: str | None = None) -> list[dict]:
        return copy.deepcopy([e for e in self.state.get("topical_exclusions", []) if chapter is None or e["chapter"] == chapter])

    def restore_topical(self, identity: str, chapter: str) -> dict:
        if not any(e["identity"] == identity and e["chapter"] == chapter for e in self.topical_exclusions()):
            return {"ok": False, "error": "No exclusion for that question and chapter."}
        self.log({"type": "topical_restore", "identity": identity, "chapter": chapter})
        return {"ok": True}

    def hint(self, n: int) -> dict:
        p = (self.session or {}).get("presented", {}).get(str(n))
        if not p:
            return {"error": "not an open question"}
        if self.session.get('skipped_answer_guards'):
            return {"n": n, "refused": "A skipped answer is protected. Finish or skip open questions, then retry it before asking for hints."}
        if p["unassisted"]:
            return {"n": n, "refused": "This question is unassisted (exit ticket, retest or challenge). Encourage an attempt."}
        hints = p["inst"].get("hints") or [st["do"] for kc in p["kcs"] for wk in self.packs.worked_for(kc)[:1]
                                           for st in wk["steps"]][:3] or GENERIC_HINTS
        p["hint_level"] = min(p["hint_level"] + 1, len(hints))
        p["hinted"] = True
        self.show("hint", hints[p["hint_level"] - 1], f"Hint {p['hint_level']} for Q{n}")
        return {"n": n, "level": p["hint_level"], "hint": hints[p["hint_level"] - 1],
                "say": "Give only this hint, in your words; do not add the next step."}

    def ai_help(self, given: bool = True) -> dict:
        """The learner is asking the AI tutor. While a no-help check (exit ticket, retest, challenge) is open it is
        refused; otherwise every open question counts as hinted, as with hint(): help is help, whoever gives it.
        `given=False` only asks whether help is allowed: a reply that never reaches the learner is no help."""
        open_ = (self.session or {}).get("presented", {})
        if any(p["unassisted"] for p in open_.values()):
            return {"refused": "This is a no-help check: answer it first, then ask me anything."}
        if given:
            for p in open_.values():
                p["hinted"] = True
            if open_:
                self._save()
        return {"ok": True}


RIGHT = {"correct": True, "score": 1.0, "error": None, "misconception": None}  # the grade a re-mark gives
_ABSENT = object()


def _idk_like(value) -> bool:
    """Text that gives up on a question instead of attempting it: the words the retry paths have always read."""
    return str(value).strip().casefold().replace('’', "'").strip('?.! ') in (
        '', 'idk', "i don't know", 'i dont know', 'i do not know', 'skip', 'no',
        'i have no idea', "i can't answer", 'i cant answer', 'not sure')


def _expected_kind(kind: str) -> tuple[str, ...]:
    return {"mcq": ("choice",), "structured": ("points",)}.get(kind, ("value",))


def _to_sig_figs(value: float, sf: int) -> str:
    """`value` with exactly `sf` significant figures, zeros kept: 11.0, 2.50, 0.0300, 120, 1.20e-3, 4.69e5."""
    if not value:
        return "0"
    mantissa, exp = f"{value:.{sf - 1}e}".split("e")
    if -3 < int(exp) < sf:  # plain digits from 0.01 up, while they show those figures and no others
        return f"{value:.{sf - 1 - int(exp)}f}"
    return f"{mantissa}e{int(exp)}"  # standard form, as the learner types it


def _in_full(value: float) -> str:
    """An exact answer written out: not rounded to 3 s.f., not padded, and free of float noise (0.1 + 0.2 is 0.3)."""
    if not value:
        return "0"
    text = f"{value:.12g}"  # 12 figures: well inside the 1e-9 an exact answer is marked to, and short of the noise
    if "e" not in text:
        return text
    mantissa, exp = text.split("e")
    return f"{mantissa}e{int(exp)}"  # standard form, as the learner types it


def _display_answer(inst: dict) -> str:
    kind = inst["kind"]
    if kind == "mcq":
        opts = inst.get("options") or {}  # image-only past-paper options have no text
        return f"{inst['answer']}: {opts[inst['answer']]}" if inst["answer"] in opts else inst["answer"]
    if kind == "numeric":
        a = inst["answer"]
        sf = (a.get("sf_ok") or [a.get("sf")])[-1]
        number = _to_sig_figs(a["value"], sf) if sf else _in_full(a["value"])  # an exact answer states no s.f.
        return f"{number} {a.get('unit', '')}".strip()
    if kind == "expression":
        return inst["answer"]["expr"]
    if kind == "short":
        return "; ".join(pt["point"] for pt in inst["rubric"])
    return "; ".join(f"{pt.get('mark', '')} {pt.get('point', '')}".strip() for pt in inst.get("scheme", []))
