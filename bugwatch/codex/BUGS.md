# BUGS — written by Codex only, append-only

Claude reads this file continuously and answers in `../FIXES.md`. Never edit or delete existing lines; only append at
the very end, with a quoted heredoc (`cat >> BUGS.md <<'EOF' … EOF`). Full rules: `../README.md`.

## Finding format (one block per bug; take the next free `B-nnn`)

```
### B-014 · P1 · session.py · answer() drops the confidence rating on comma answers
- **Found:** 14:07 · **Method:** ran | read | inferred · **Confidence:** high | medium | low
- **Where:** `plugin/stem-tutor/skills/tutor/scripts/tutorlib/session.py` · `Tutor.answer` · "results.append(self._record("
- **Repro:** exact commands or a snippet a stranger can paste (say which sandbox env it needs)
- **Expected:** what should happen
- **Actual:** what happens, with the real output
- **Impact:** who is hurt and how (wrong mark, lost notes, stuck screen…)
- **Suggested fix:** optional, at most two lines
```

## Log lines (everything else; one line each, `- HH:MM VERB …`, Hong Kong time)

```
- 14:05 SWEEP · grade.py + units.py · ran check.sh and 40 probes · findings: B-014 B-015     (or: clean)
- 14:50 VERIFIED B-014 · tried 6 comma variants, all fine
- 14:52 REOPEN B-014 · still splits on ';' — repro: <command>
- 14:44 REPLY B-011 · answer to Claude's question
```

Priorities: **P0** wrong grading, answer leak, lost/corrupted progress or notes, crash on a normal path, writes outside
the vault · **P1** wrong behaviour on a normal path · **P2** edge-case crash, UX trap, action slower than ~1 s, guide
mismatch · **P3** minor.

<!-- ↓↓↓ append below this line — do not edit anything above ↓↓↓ -->

- 12:07 SWEEP · baseline · ran bash bugwatch/check.sh: 250 passed in 32.65s · clean
### B-001 · P0 · grade.py · Unitless numeric answers accept arbitrary units and trailing expressions
- **Found:** 12:08 · **Method:** ran · **Confidence:** high
- **Where:** `plugin/stem-tutor/skills/tutor/scripts/tutorlib/grade.py` · `_grade_numeric` · "if want_unit:"
- **Repro:** With sandbox.sh exports, run Python: `from tutorlib import grade; i={'kind':'numeric','answer':{'value':500,'unit':'','exact':True}}; print(grade.grade_item(i,{'kind':'value','value':'500 kg'}))`. A real affected item is `9702-1.1-i01`: seed 4 instantiates a 0.5 m wire and asks for its numerical magnitude in millimetres (answer 500).
- **Expected:** An incompatible physical unit or unevaluated trailing expression must not earn full credit for a unitless numerical magnitude.
- **Actual:** `500 kg` earns `correct=True, score=1.0, error=None`; the parsed unit/tail is ignored entirely when the answer unit is empty.
- **Impact:** Students receive full credit for dimensionally wrong answers; the same branch also accepts a correct numeric prefix followed by arbitrary text.
### B-002 · P0 · grade.py · Exact numeric answers incorrectly allow one-percent error
- **Found:** 12:09 · **Method:** ran · **Confidence:** high
- **Where:** `plugin/stem-tutor/skills/tutor/scripts/tutorlib/grade.py` · `_grade_numeric` · "tol = ans.get(\"tol_rel\", 0.01)"
- **Repro:** With sandbox.sh exports, run Python: `from tutorlib import grade; print(grade.grade_item({'kind':'numeric','answer':{'value':117,'unit':'','exact':True}}, {'kind':'value','value':'118'}))`. Published `P1-1-i19`, instantiated with `random.Random(4)`, has exactly this answer object; `9702-1.1-i01` also marks 501 correct for an exact answer of 500.
- **Expected:** An answer marked `exact: true` must reject the wrong integer.
- **Actual:** 118 receives `correct=True, score=1.0` for the exact answer 117. The `exact` field is never consulted.
- **Impact:** Incorrect arithmetic and unit conversions receive full marks and successful learning credit.
### B-003 · P2 · units.py · Large unit exponent escapes grading as OverflowError
- **Found:** 12:09 · **Method:** ran · **Confidence:** high
- **Where:** `plugin/stem-tutor/skills/tutor/scripts/tutorlib/units.py` · `parse_unit` / `unit_factor` · "f *= uf**e" / "except ValueError:"
- **Repro:** With sandbox.sh exports, run Python: `from tutorlib import grade; print(grade.grade_item({'kind':'numeric','answer':{'value':9.81,'unit':'m'}}, {'kind':'value','value':'1 km9999'}))`.
- **Expected:** An invalid/out-of-range unit should return an unreadable or wrong-unit grade.
- **Actual:** Raises uncaught `OverflowError: (34, 'Result too large')`.
- **Impact:** A mistyped or pasted extreme unit exponent can interrupt the answer action instead of letting the student retry.
### B-004 · P0 · grade.py · Correct rounding to an explicitly allowed precision gets zero
- **Found:** 12:10 · **Method:** ran · **Confidence:** high
- **Where:** `plugin/stem-tutor/skills/tutor/scripts/tutorlib/grade.py` · `_grade_numeric` · "if _close(value, target, tol):"
- **Repro:** With sandbox.sh exports: `from tutorlib import grade; print(grade.grade_item({'kind':'numeric','answer':{'value':16.46207763315433,'unit':'N','sf_ok':[2,3]}}, {'kind':'value','value':'16 N'}))`. These are the answer and value from published `9702-1.4-i03` instantiated with seed 0. The same issue occurs for many other published numeric templates.
- **Expected:** 16 N is the correct two-significant-figure answer, and 2 is explicitly allowed by `sf_ok`.
- **Actual:** `correct=False, score=0, needs_judgement=True`: the fixed 1% tolerance rejects the correct rounded value before checking allowed significant figures.
- **Impact:** Correct student answers are rejected or sent to self-marking despite using a permitted precision.
### B-005 · P0 · grade.py · Expression answers execute Python and can write outside the vault
- **Found:** 12:10 · **Method:** ran · **Confidence:** high
- **Where:** `plugin/stem-tutor/skills/tutor/scripts/tutorlib/grade.py` · `_sympy` / `expressions_equal` · "return sympy, lambda s: parse_expr("
- **Repro:** With sandbox.sh exports and `/tmp/bugwatch-scratch/` present, run `from tutorlib import grade; grade.grade_item({'kind':'expression','answer':{'expr':'x'}},{'kind':'value','value':"open('/tmp/bugwatch-scratch/expression-proof.txt','w').write('BUGWATCH')"})`. Read that scratch file afterward. This proof only writes a harmless marker in /tmp, never the real vault.
- **Expected:** Student expression input is arithmetic data and cannot execute file operations.
- **Actual:** `/tmp/bugwatch-scratch/expression-proof.txt` is created containing `BUGWATCH`, outside the sandbox vault. Grading subsequently returns `needs_judgement=True`, after the side effect already happened.
- **Impact:** Pasted expression text can create or overwrite files anywhere the app can access, including learner notes and files outside the vault.
- **Suggested fix:** Validate a restricted arithmetic syntax before any eval-based SymPy parsing; exclude attributes, arbitrary names and calls.
- 12:10 SWEEP · (1) grade.py + units.py + packs.py · ran 2,791 published item instantiations, numeric precision probes, exact-answer probes, unit overflow and scratch-only expression side-effect repro · findings: B-001 B-002 B-003 B-004 B-005
### B-006 · P1 · model.py · Midnight to 04:59 is classified as afternoon
- **Found:** 12:11 · **Method:** ran · **Confidence:** high
- **Where:** `plugin/stem-tutor/skills/tutor/scripts/tutorlib/model.py` · `_time_block` · "else \"afternoon\" if h < 17"
- **Repro:** With sandbox.sh exports: `from datetime import datetime; from tutorlib import model; print(model._time_block(datetime.fromisoformat('2026-09-30T02:00:00+08:00')))`. Also tested hours 0 and 4.
- **Expected:** These study sessions belong to late night.
- **Actual:** All three return `afternoon`.
- **Impact:** The profile mixes overnight and afternoon performance, potentially recommending the wrong time to study.
### B-007 · P1 · model.py · Two hinted answers clear an active misconception
- **Found:** 12:11 · **Method:** ran · **Confidence:** high
- **Where:** `plugin/stem-tutor/skills/tutor/scripts/tutorlib/model.py` · `_apply_answer` · "elif g[\"score\"] >= SUCCESS:"
- **Repro:** With sandbox.sh exports: create `s=model.new_state()`; apply an answer event with ts `2026-09-30T12:00:00+08:00`, item `probe`, kcs `['k']`, subject `phys`, and grade `{correct:False,score:0,error:'CONCEPT',misconception:'m'}`. Apply that event twice more with `hinted=True` and grade `{correct:True,score:1,error:None,misconception:None}`.
- **Expected:** Hinted answers must not establish that a misconception is resolved; SCOPE invariant 6 says hints never count as success.
- **Actual:** `s['kcs']['k']['active_misconceptions']` becomes `[]`, although `succ_days` remains empty because both successful answers were assisted.
- **Impact:** The tutor stops targeting a student's misconception without any independent correct answer.
### B-008 · P1 · session.py · Lost-mark answers count as fully correct in the progress profile
- **Found:** 12:11 · **Method:** ran · **Confidence:** high
- **Where:** `plugin/stem-tutor/skills/tutor/scripts/tutorlib/session.py` · `Tutor._record` · "partial = g[\"correct\"] and g[\"score\"] < model.SUCCESS" (after `self.log`); `model.py` · `_apply_answer` · "c, acc = CONF_P[e[\"conf\"]], 1.0 if g[\"correct\"] else 0.0"
- **Repro:** With sandbox.sh exports, apply a model answer event with ts `2026-09-30T12:00:00+08:00`, item `probe`, kcs `['k']`, subject `phys`, conf `4`, and grade `{correct:True,score:0.5,error:'NOTATION',misconception:None}`. This is the exact grade `Tutor._record` logs for a right numeric value missing its unit, before changing correct to False for session feedback.
- **Expected:** The learner profile should agree with the lost-mark feedback and the session's incorrect-answer count.
- **Actual:** `by_conf` becomes `{'4':[1,1]}`, `high_conf_errors=0`, and bias is about `-0.05`; fatigue and time-of-day also count the answer as correct.
- **Impact:** Repeated missing-unit/s.f. errors make a student's confidence and performance look better than the marks actually earned.
### B-009 · P2 · policy.py · Completed teaching experiments never influence future method selection
- **Found:** 12:12 · **Method:** ran · **Confidence:** high
- **Where:** `plugin/stem-tutor/skills/tutor/scripts/tutorlib/policy.py` · `choose_method` · "return default_method(meta, ks, fresh), None"; `experiments.py` · `active` · "exp[\"status\"] == \"running\""
- **Repro:** With sandbox.sh exports, create Packs and a new model state. Set `s['experiments']['phys-1']={'status':'done','subject':'phys','arms':['worked_faded','problem_first'],'eligible':{'types':['procedural']},'result':{'decision':'problem_first'}}`. Pick any physics procedural KC with no existing learner state and call `policy.choose_method(s,p,k,random.Random(1))`.
- **Expected:** The guide's Teaching experiments promise says that when one method is confidently better, the tutor uses it.
- **Actual:** Returns `('worked_faded', None)`. Selection considers running experiments and defaults only; no code consumes a completed experiment's winning method.
- **Impact:** Weeks of personal experiment results are shown in the profile but never deliver the promised teaching adaptation.
- 12:12 SWEEP · (2) model.py + policy.py + profile.py + experiments.py + weekly.py · ran hour-boundary, hinted misconception, partial-grade calibration and completed-experiment selection probes; read planning and weekly flow · findings: B-006 B-007 B-008 B-009
### B-010 · P0 · views.py · Starting two same-title sessions within a minute overwrites the first lesson log
- **Found:** 12:12 · **Method:** ran · **Confidence:** high
- **Where:** `plugin/stem-tutor/skills/tutor/scripts/tutorlib/views.py` · `LessonLog.create` · "rel = f\"Lessons/{now:%Y-%m-%d %H%M} {_safe(title)}.md\""
- **Repro:** With sandbox.sh exports: `from tutorlib import store,views; from datetime import datetime; v=store.Vault(store.find_vault()); a=views.LessonLog.create(v.root,'Collision probe',datetime.fromisoformat('2026-09-30T12:12:01+08:00')); a.you('KEEP FIRST SESSION NOTES'); b=views.LessonLog.create(v.root,'Collision probe',datetime.fromisoformat('2026-09-30T12:12:59+08:00')); print(a.rel==b.rel, 'KEEP FIRST SESSION NOTES' in (v.root/b.rel).read_text())`.
- **Expected:** Both sessions and the first session's learner notes survive.
- **Actual:** Prints `True False`: both use the same path and creation replaces the first file.
- **Impact:** Returning to the menu and restarting the same lesson quickly can erase the earlier session transcript and notes.
### B-011 · P0 · views.py · Re-teaching truncates saved own-words notes at the first blank line
- **Found:** 12:12 · **Method:** ran · **Confidence:** high
- **Where:** `plugin/stem-tutor/skills/tutor/scripts/tutorlib/views.py` · `notes_update` · "re.search(r\"> \\[!quote\\] In your words\\n((?:> .*\\n?)+)\", prev)"
- **Repro:** With sandbox.sh exports, build `v=store.Vault(store.find_vault())`, `p=packs.Packs(v)`, `s=model.new_state()`; choose the first KC `k` in subtopic `9702-2.1`. Call `r=views.notes_update(v.root,p,s,'9702-2.1',node={'kc':k,'note':'sample','own_words':'FIRST PARAGRAPH\n\nSECOND PARAGRAPH'})`, then `views.notes_update(v.root,p,s,'9702-2.1',node={'kc':k,'note':'retaught'})`. Inspect `(v.root/r).read_text()`.
- **Expected:** The entire previous own-words note survives when no replacement is supplied.
- **Actual:** `SECOND PARAGRAPH` is present before re-teaching and absent afterward. `callout` renders a blank line as `>`, but the preservation regex only accepts `> ` lines and stops there.
- **Impact:** Ordinary multi-paragraph student notes are silently and permanently truncated during re-teaching.
- 12:13 SWEEP · (3) session.py + lesson.py + views.py + report.py · ran four lesson goals through 52 actions with restart and event-fold checks at each step; reproduced transcript collision and multi-paragraph note loss · findings: B-010 B-011
### B-012 · P0 · store.py · First successful event after a torn write is lost on replay
- **Found:** 12:14 · **Method:** ran · **Confidence:** high
- **Where:** `plugin/stem-tutor/skills/tutor/scripts/tutorlib/store.py` · `Vault.append_event` · "f.write(json.dumps(event, ensure_ascii=False) + \"\\n\")"
- **Repro:** Use `bash "$R/bugwatch/sandbox.sh" /tmp/bugwatch-store` and its exports. In Python, create `v=store.Vault(store.find_vault())`, mkdir `v.tutor/'events'`, and write `'{"type":"answer","item":'` to `v.tutor/'events/2026-08.jsonl'` to simulate a crash mid-append. Call `v.append_event({'type':'gaps','add':['9702-1.1.1']},now=datetime.fromisoformat('2026-08-30T12:00:00+08:00'))`, then `list(v.events())`.
- **Expected:** The new completed event survives replay even if the preceding event was torn.
- **Actual:** append_event returns a successful event, but replay returns `[]` with `bad_lines=['2026-08.jsonl:1']`: the new JSON is concatenated directly onto the incomplete line and skipped with it.
- **Impact:** The first valid progress update after a crash disappears on rebuild, violating the event-log source-of-truth invariant.
### B-013 · P0 · anki.py · A second incremental export in the same minute destroys the first batch
- **Found:** 12:14 · **Method:** ran · **Confidence:** high
- **Where:** `plugin/stem-tutor/skills/tutor/scripts/tutorlib/anki.py` · `export` · "rel = f\"Anki/STEM Tutor {now:%Y-%m-%d %H%M}.apkg\""
- **Repro:** In the `/tmp/bugwatch-store` sandbox, create Tutor with fixed now `2026-09-30T12:15:00+08:00`. Log one correct answer for `9702-1.1.1`, then call `anki.export(t)`. Log an answer for `9702-1.1.2` and export again without advancing the minute. Each answer event needs type `answer`, item equal to the KC, kcs `[kc]`, subject `phys`, and grade `{correct:True,score:1,error:None,misconception:None}`.
- **Expected:** Both exported batches remain available to import.
- **Actual:** First export reports 5 cards, second 6, both at `Anki/STEM Tutor 2026-09-30 1215.apkg`; the file contents change. State marks all 11 cards exported, and a third export returns `{'cards':0,'path':None}`.
- **Impact:** The first five cards disappear from the available package and cannot be recovered by retrying export. This is a separate writer from the lesson-log collision in B-010.
- 12:14 SWEEP · (4) store.py + deps.py + anki.py + JSON round trips · ran torn-event append/replay and two incremental Anki exports; prior sweep exercised learner/session JSON reload on each action · findings: B-012 B-013
### B-014 · P1 · screens.py · Failed AI long-answer marking leaves no way to submit marks
- **Found:** 12:16 · **Method:** ran · **Confidence:** high
- **Where:** `app/tutor_app/screens.py` · `SessionScreen.ai_check_long` · "self.say(cards.card(\"hint\", \"AI check unavailable\", r.message or \"Mark it yourself.\"))" followed by `return`
- **Repro:** Headless repro is `/tmp/bugwatch-scratch/test_app_probes.py`, test `test_long_ai_failure`; run via check.sh with R exported, sandbox vault `/tmp/bugwatch-store/mnt/STEM Tutor`, and app/engine PYTHONPATH. It opens a published long question, submits written work, clicks the AI examiner button, and substitutes a failed one_shot response (sign-in needed).
- **Expected:** Restore the self-marking TickPanel and the learner's selections after a failed AI call.
- **Actual:** After failure the panel is `ContinuePanel`, with zero buttons and one question still open. The message says to mark it yourself, but no marking controls remain.
- **Impact:** A normal authentication, limit or network failure traps the long-answer workflow; the student must leave and re-enter, losing the submitted text held only by the old screen.
### B-015 · P0 · screens.py · Submitted long-answer working is never saved
- **Found:** 12:16 · **Method:** ran · **Confidence:** high
- **Where:** `app/tutor_app/screens.py` · `SessionScreen.long_written` · "self.long_text = text" / "self.say(cards.you(text))"
- **Repro:** Run `/tmp/bugwatch-scratch/test_app_probes.py::test_long_work_missing_from_saved_notes` through check.sh with the sandbox exports and R exported. The pilot opens a published long question, types `MY SUBMITTED WORK: v = u + at = 19.6 m/s`, presses ctrl+s, and submits self-marks. Inspect the lesson log and event JSONL files.
- **Expected:** Submitted working survives in the promised full lesson transcript and can be recovered after leaving or restarting.
- **Actual:** The answer text is absent from both the lesson log and events. Only the self-marked point numbers are saved; the working lives in `self.long_text` and screen widgets.
- **Impact:** Completing or leaving a long-question session permanently loses the student's typed working, even when AI is disabled and everything succeeds normally.
### B-016 · P0 · mac.py · iPad import collision handling overwrites an existing student PDF
- **Found:** 12:17 · **Method:** ran · **Confidence:** high
- **Where:** `app/tutor_app/mac.py` · `import_ipad_inbox` · "target = dest / f\"{f.stem} {len(list(dest.glob(f.stem + '*')))}{f.suffix}\""
- **Repro:** In the scratch vault create `Inbox/collision.pdf` containing `FIRST` and `Inbox/collision 2.pdf` containing `KEEP SECOND`. In a scratch external inbox `/tmp/bugwatch-scratch/ipad-inbox`, create `collision.pdf` containing `NEW`. Call `mac.import_ipad_inbox(vault_root, Path('/tmp/bugwatch-scratch/ipad-inbox'))`.
- **Expected:** Import chooses an unused filename and preserves both existing PDFs.
- **Actual:** Returns `['collision 2.pdf']`; that existing file now contains `NEW`. Counting matching names does not guarantee the resulting suffix is unused.
- **Impact:** An ordinary repeated filename plus a gap in numbered copies silently overwrites handwritten student work during app startup.
### B-017 · P1 · ai.py · Concurrent AI requests bypass the daily reply cap
- **Found:** 12:17 · **Method:** ran · **Confidence:** high
- **Where:** `app/tutor_app/ai.py` · `Claude.stream` · "if self.today()[\"replies\"] >= self.daily_cap:" before "async with self._lock:"
- **Repro:** Run `/tmp/bugwatch-scratch/test_ai_cap.py` via check.sh with sandbox exports and R exported. It creates Claude with fake_claude.py, a fresh usage file and daily_cap=1, then awaits `asyncio.gather(c.reply('first'),c.reply('second'))`.
- **Expected:** At most one request is sent; the second returns cap reached.
- **Actual:** Both results are successful and daily usage is 2 despite a cap of 1. Both check the cap before either request is counted; the queued request never checks again after acquiring the lock.
- **Impact:** Overlapping help/card-generation/marking activity can exceed the advertised daily AI allowance. `one_shot` likewise has no reservation for concurrent calls.
### B-018 · P0 · ai.py · Open-answer leak guard misses plain option letters, algebra keys and positive exponents
- **Found:** 12:18 · **Method:** ran · **Confidence:** high
- **Where:** `app/tutor_app/ai.py` · `leaks` · "if not m: return False" and the MCQ phrase patterns; `screens.py` · `SessionScreen._stream` · "if open_n and ai_mod.leaks(buf, key, kind):"
- **Repro:** With sandbox exports: `from tutor_app.ai import leaks; print(leaks('B.','B: 0.35 kg','mcq')); print(leaks('The answer is x^2 + 2*x + 1','x**2+2*x+1','expression')); print(leaks('1000 m','1e+03 m','numeric'))`.
- **Expected:** Each is a direct disclosure of the protected answer and should be withheld while the question is open.
- **Actual:** All three return False. MCQ patterns need extra wording, nonnumeric expression keys return False immediately, and `1e+03` is read as 1 by the numeric regex. `_stream` consequently displays/logs these replies if the AI emits them.
- **Impact:** The advertised pre-attempt answer protection misses basic answer forms, including an entire class of algebra questions. These are deterministic guard probes; no signed-out live AI call was attempted.
- 12:18 SWEEP · (5) app/tutor_app · ran two Textual long-answer pilots, scratch iPad collision import, concurrent fake-AI cap probe and direct leak-guard cases; read installed claude --help and screen/panel flow · findings: B-014 B-015 B-016 B-017 B-018
### B-019 · P2 · publish.py · Version pruning deletes the newest rollback packs after v9
- **Found:** 12:19 · **Method:** ran · **Confidence:** high
- **Where:** `build/publish.py` · `publish` · "for old in sorted(p for p in packs.glob(\"v*\") if p.name != version)[:-2]:"
- **Repro:** Use a sandbox vault with its generated v1. Create empty scratch version directories v2 through v11 under that sandbox's `.tutor/packs`, then call `publish.publish(vault_root)` with build on PYTHONPATH. Inspect retained version directory names.
- **Expected:** After publishing v12, keep v10 and v11 as the documented two previous rollback versions.
- **Actual:** Retains `['v12','v8','v9']` and deletes v10/v11: pruning sorts Path names lexicographically instead of sorting their numeric versions.
- **Impact:** Once the version counter reaches two digits, rollback skips the latest published content and can only return to stale packs.
- 12:19 SWEEP · (6) build publish pipeline · read publish/finalize/validate/bundle; validated all seven non-held packs (zero validation errors); ran sandbox v12 rollback-retention probe · findings: B-019
### B-020 · P1 · session.py · Resuming a test-repair worked example skips its unseen steps
- **Found:** 12:20 · **Method:** ran · **Confidence:** high
- **Where:** `plugin/stem-tutor/skills/tutor/scripts/tutorlib/session.py` · `Tutor._step_learn` · "return {\"activity\": \"worked\", \"block\": \"learn\""; the step index is incremented before returning, without setting `awaiting`.
- **Repro:** With sandbox exports, create Tutor with seed 5 and `start('test',focus=['9702-1.1.2'],replace=True)`. Answer the initial sweep question with `n?`. Next returns `teach`; next returns `worked`. Construct a fresh Tutor on the same scratch vault and call next again.
- **Expected:** Resume the same worked example at the saved reveal count, as required by SCOPE invariant 5.
- **Actual:** Activity sequence is `questions/sweep → teach → worked → [restart] questions/faded`. The saved session has no awaiting worked activity. App Test mode uses this same repair path.
- **Impact:** Save-and-menu or restarting during repair teaching skips the worked example and sends the student straight to solving the faded problem, even if no step was viewed.
- 12:20 SWEEP · (7) SCOPE invariants · revisited session resume and event-fold guarantees, linted nine generated note files (zero issues), confirmed test-repair worked state is skipped after restart · findings: B-020
- 12:21 VERIFIED B-005 · at 0c64aee, 11 focused expression tests pass; original open/write payload plus import, print, attribute, indexing and power-tower probes are refused; fresh outside-vault proof file is not created. Separate mathematical equivalence defect logged as B-021.
### B-021 · P0 · grade.py · Positive-only sampling accepts false algebra identities
- **Found:** 12:21 · **Method:** ran · **Confidence:** high
- **Where:** `plugin/stem-tutor/skills/tutor/scripts/tutorlib/grade.py` · `expressions_equal` · "point = {s: Fraction(rng.randint(3, 17), rng.randint(2, 5)) for s in syms}"; `tests/test_grade.py` · `test_expression_equivalent_forms_still_match` · "(\"abs(-x) + 10^3\", \"x + 1000\")"
- **Repro:** With sandbox exports: `from tutorlib import grade; print(grade.grade_item({'kind':'expression','answer':{'expr':'x'}},{'kind':'value','value':'abs(x)'}))`. Repeat with `sqrt(x^2)`. Also `abs(-x)+1000` against `x+1000`.
- **Expected:** Reject these as general identities: at x=-1, abs(x)=1 while x=-1. No positive-domain restriction is supplied by the item.
- **Actual:** All receive `correct=True, score=1.0`. Symbolic simplification does not establish equality, but all six fallback samples use positive coordinates and hide the negative branch. The new B-005 compatibility test explicitly asserts one of these false identities.
- **Impact:** Students earn full marks for incorrect sign/absolute-value algebra; a passing regression test currently preserves the wrong marking.
- 12:22 SWEEP · (8) guide versus code · compared lesson, marking, review, profile and note promises with their call paths; outstanding mismatches already covered by B-009 B-015 B-018 B-020 · clean for new findings
### B-022 · P0 · units.py · Joined denominator units move all but the last factor into the numerator
- **Found:** 12:22 · **Method:** ran · **Confidence:** high
- **Where:** `plugin/stem-tutor/skills/tutor/scripts/tutorlib/units.py` · `parse_unit` · "readings.append([(u, 1) for u in split[:-1]] + [(split[-1], exp)])"
- **Repro:** With sandbox exports: `from tutorlib.units import unit_factor; print(unit_factor('kg/ms2','N'),unit_factor('kg/ms2','Pa')); print(unit_factor('J/molK','J mol^-1 K^-1'),unit_factor('J/molK','J mol K^-1'))`. Also grade `1 kg/ms2` against a numeric answer of `1 N`.
- **Expected:** The slash applies to the joined denominator factors: kg/(m s²) is Pa, and J/(mol K) is J mol⁻¹ K⁻¹. Neither is the corresponding expression with m or mol moved upstairs.
- **Actual:** Factors are `1.0 None` and `None 1.0`; `1 kg/ms2` gets full credit for `1 N`. Splitting a joined token gives preceding factors exponent +1 even when the token is after a slash.
- **Impact:** The unit checker accepts dimensionally wrong answers and rejects correct compact denominator notation.
### B-023 · P2 · grade.py · Bounded expression input still freezes grading on allowed powers
- **Found:** 12:23 · **Method:** ran · **Confidence:** high
- **Where:** `plugin/stem-tutor/skills/tutor/scripts/tutorlib/grade.py` · `_sympy` / `_check_size` / `expressions_equal` · "_MAX_POWER = 10_000" and "diff = sympy.simplify(ea - eb)"
- **Repro:** `/tmp/bugwatch-scratch/power_probe.py` runs grade_item in isolated subprocesses with a 2-second timeout and the sandbox exports. Inputs `Pow(2,1000000000)` and `(x+1)^10000`, each against expression key `x`, time out; controls `exp(1000000000)` and a large sine argument finish in about 0.2s. Repeated with the same result after checking git status/log.
- **Expected:** Refuse inputs exceeding a safe work budget promptly, including expensive symbolic simplification.
- **Actual:** Both cases exceed two seconds and must be killed by the scratch subprocess timeout. Explicit `Pow(...)` is a permitted constructor and can evaluate before the size guard; a symbolic degree of exactly 10,000 passes the bound but is expensive to simplify.
- **Impact:** A pasted or mistyped large power stalls the synchronous answer handler/UI. B-005's filesystem execution fix remains verified; this is a separate execution-time failure.
- 16:51 SWEEP · refreshed baseline after renewed spotter instruction · ran bash bugwatch/check.sh: 373 passed in 36.38s at HEAD 025f85a · clean
- 16:54 SWEEP · renewed baseline · ran bash bugwatch/check.sh: 373 passed, 1 failed in 35.98s; test_session.py::test_full_session_reaches_exit_and_end again fails (worked instead of end) after git status/log check at 025f85a; session.py, lesson.py and test_v110.py are currently modified by Claude, so treating this as a mid-edit observation pending B-020
- 16:55 REOPEN B-001 · Method: ran; Confidence: high. The new percent exception still accepts a wrong unit on published 9702-1.1-i01: with sandbox exports, instantiate that item with random.Random(4) (0.5 m → numerical magnitude 500 in mm), then grade_item(i, {'kind':'value','value':'500%'}); returns correct=True, score=1.0. Re-read grade.py::_grade_numeric and value_problem: both allow `unit not in ("", "%")`. The exception applies to every plain-number question, including exponents/counts; percentages should only be tolerated when the question asks for a percentage.
### B-024 · P0 · grade.py · Reversed physics definitions receive full marks without review
- **Found:** 16:55 · **Method:** ran · **Confidence:** high
- **Where:** `plugin/stem-tutor/skills/tutor/scripts/tutorlib/grade.py` · `_grade_rubric` · "if all(any(k.lower() in text for k in group) for group in point[\"keywords\"]):"; `session.py` · `Tutor.answer` · "elif inst[\"kind\"] == \"short\" and g[\"needs_judgement\"]:"
- **Repro:** With sandbox.sh exports, `from tutorlib import store,packs,grade; p=packs.Packs(store.Vault(store.find_vault())); i=next(i for i in p.pack('9702-2.1')['items'] if i['id']=='9702-2.1-i01'); print(grade.grade_item(i,{'kind':'value','value':'Velocity is the rate of change of velocity. Acceleration is the rate of change of displacement.'}))`.
- **Expected:** This answer swaps the definitions of velocity and acceleration and must not receive full marks automatically; require judgement if keyword presence cannot establish correctness.
- **Actual:** Returns correct=True, score=1.0, needs_judgement=False, unmatched=[]. The two phrases occur somewhere in the text, so both marks are awarded despite being assigned to the wrong quantities. Tutor.answer records this directly, bypassing the short-answer review UI.
- **Impact:** A normal conceptual error receives full marks and successful learning credit, reinforcing precisely the confusion the published question is meant to detect.
### B-025 · P2 · grade.py · Finite numeric input can overflow the error-classification ratio and crash grading
- **Found:** 17:00 · **Method:** ran · **Confidence:** high
- **Where:** `plugin/stem-tutor/skills/tutor/scripts/tutorlib/grade.py` · `_grade_numeric` · "k = math.log10(abs(value / target))" and "round(k)"
- **Repro:** With sandbox.sh exports, `from tutorlib import grade,store,packs; import random; p=packs.Packs(store.Vault(store.find_vault())); i=packs.instantiate(next(i for i in p.pack('9702-1.2')['items'] if i['id']=='9702-1.2-i14'),random.Random(4)); grade.grade_item(i,{'kind':'value','value':'1e308 m^2'})`. Repeated after git status/log check at 0d4fef7.
- **Expected:** A finite but wildly incorrect answer should return a wrong/unreadable grade without throwing.
- **Actual:** Raises `OverflowError: cannot convert float infinity to integer`. The unit conversion remains finite, but dividing 1e308 by the target 7.5e-7 overflows to infinity, then round(k) throws. B-003's unit conversion guard does not cover this later ratio.
- **Impact:** An extreme pasted exponent breaks the synchronous answer handler instead of letting the student correct the input.
- 17:00 VERIFIED B-001 · retested published 9702-1.1-i01 seed 4 at 0d4fef7: 500% now scores 0 and value_problem returns unit, so Tutor leaves the question open
- 17:00 SWEEP · (1) grade.py + units.py + packs.py · ran 129 grade tests (all passed before the latest percent patch), published percent/short-answer probes and finite overflow probes; read pack sampling and selection · findings: B-024 B-025; reopened then verified B-001
- 17:03 VERIFIED B-009 · completed procedural-physics winner selects problem_first; 64 model/experiment/v110 tests pass, including winner, no_difference, eligibility and misconception controls
- 17:03 VERIFIED B-006 · 64 focused model/experiment/v110 tests pass; independent late-night event sequence stays in late night
- 17:03 VERIFIED B-007 · independent five-day event sequence excludes the hinted day from successes; two-hinted-answer misconception regression also passes
- 17:03 VERIFIED B-008 · lost-mark calibration/profile regression passes in the 64-test focused run
- 17:03 SWEEP · (2) model.py + policy.py + profile.py + experiments.py + weekly.py · ran 64 focused tests plus completed-winner, five-day hinted/confidence, JSON round-trip and review-planning probes; read retention, weekly lifecycle and profile calculations · clean for new findings
### B-026 · P1 · session.py · Reviews leave My Notes progress stale after mastery changes
- **Found:** 17:03 · **Method:** ran · **Confidence:** high
- **Where:** `plugin/stem-tutor/skills/tutor/scripts/tutorlib/session.py` · `Tutor.end` · "for p in s.get(\"presented\", {}).values()" when building `touched`; `Tutor._record` · "del s[\"presented\"][key]"
- **Repro:** Run `bash "$R/bugwatch/sandbox.sh" /tmp/bugwatch-notes-refresh`, set its exports, then `"$R/.venv/bin/python" /tmp/bugwatch-scratch/review_notes_probe.py`. The script seeds five correct answers for 9702-2.1.1 on one day, creates its My Notes page, advances 40 days, starts Review, correctly answers published MCQ 9702-2.1-i03, and ends the session.
- **Expected:** My Notes' progress count, concept map and idea heading update from learning to secure, matching the learner state and Home dashboard.
- **Actual:** `model.is_mastered` becomes True and Home counts one secure idea, but My Notes still says `Progress: 0/9 ideas secure` and retains the yellow learning heading. Review has no single subtopic/kcs_learned, and answered questions have already been removed from presented, so touched is empty.
- **Impact:** Students reviewing normally see outdated mastery in their notes; subsequent misses can likewise leave an idea falsely green until another lesson explicitly refreshes that page.
### B-027 · P1 · session.py · Multi-idea questions prevent a completed experiment retest from being recorded
- **Found:** 17:05 · **Method:** ran · **Confidence:** high
- **Where:** `plugin/stem-tutor/skills/tutor/scripts/tutorlib/session.py` · `Tutor._step_retest` · "exp=b[\"exp\"][kc]"; `Tutor._record` · "kc = p[\"kcs\"][0]" before accumulating retest scores
- **Repro:** Run `bash "$R/bugwatch/sandbox.sh" /tmp/bugwatch-retest`, set its exports, then `"$R/.venv/bin/python" /tmp/bugwatch-scratch/retest_attribution_probe.py`. It assigns 9702-1.2.4 to an experiment, advances eight days, starts Review with seed 1, and answers all retest questions with don't-know.
- **Expected:** Finishing the three scheduled questions records that idea's retest score (0 here), and the completed retest stops appearing as due.
- **Actual:** Questions are i16, i02, p11. Published i02 lists kcs ['9702-1.2.1','9702-1.2.4'], so its score is credited to .1 instead of the target .4. The block has given={'.4':3}, but session retest scores split 2+1; experiment scores stays {}, and retests_due still returns .4.
- **Impact:** The student finishes the promised retest yet must repeat it in another session; affected experiments can stall or later record incomplete/misattributed evidence. The selected target KC is lost between presentation and recording.
- 17:05 VERIFIED B-020 · 104 session/report/v110/CLI tests pass, including restarting repair worked examples after one reveal and continuing the CLI; baseline's mid-edit worked/end failure is gone
- 17:05 VERIFIED B-010 · same-minute lesson collision regression passes in the 104-test run
- 17:05 VERIFIED B-011 · multi-paragraph own-words preservation regression passes in the 104-test run
- 17:05 SWEEP · (3) session.py + lesson.py + views.py + report.py · ran 104 focused tests and scratch review-mastery/note-refresh and experiment-retest attribution scripts; read state transitions and managed note writes · findings: B-026 B-027
- 17:06 REOPEN B-012 · Method: ran; Confidence: high. A torn multibyte UTF-8 character still makes all replay fail. In a sandbox, write one valid event plus `b'{"type":"answer","response":"' + 'μ'.encode('utf-8')[:1]` to the monthly event file, append a valid event with Vault.append_event, then list(v.events()). Reproduced twice after git status/log check: UnicodeDecodeError at the incomplete 0xce byte. Re-read store.py::Vault.events: `path.read_text(encoding="utf-8").splitlines()` decodes the whole file before its per-line ValueError handler. Normal physics Unicode input can therefore make a crash-torn line prevent both earlier and subsequent valid progress from replaying; scratch evidence is /tmp/bugwatch-torn-utf8/mnt/STEM Tutor/.tutor/events/2026-09.jsonl.
### B-028 · P1 · anki.py · Flashcard IDs collide across published packs and suppress whole later exports
- **Found:** 17:07 · **Method:** ran · **Confidence:** high
- **Where:** `plugin/stem-tutor/skills/tutor/scripts/tutorlib/anki.py` · `export` · "if card[\"id\"] in done" and "guid=guid(card[\"id\"])"
- **Repro:** Run `bash "$R/bugwatch/sandbox.sh" /tmp/bugwatch-anki-ids`, set its exports, then `"$R/.venv/bin/python" /tmp/bugwatch-scratch/anki_ids_probe.py`. It introduces 9702-1.1.1 and exports, then introduces 9702-2.1.1 and exports again.
- **Expected:** The second export contains the four newly introduced kinematics cards (distance, displacement, speed/velocity, acceleration).
- **Actual:** First export gives 5 cards; second gives `{'cards':0,'path':None}`. Every published pack reuses local IDs such as fc1–fc4; the first pack's exported IDs incorrectly suppress unrelated cards in later packs. The GUID generator also uses this unqualified ID.
- **Impact:** Studying another topic normally fails to deliver its promised Anki cards. This is independent of B-013's fixed filename collision; identifiers need a pack/KC namespace as well.
### B-029 · P1 · anki.py · Unescaped inequality symbols turn published Anki maths into HTML tags
- **Found:** 17:07 · **Method:** ran · **Confidence:** medium
- **Where:** `plugin/stem-tutor/skills/tutor/scripts/tutorlib/anki.py` · `to_anki` · "return s.replace(\"\n\", \"<br>\").replace(\"\x00\", \"$\")"
- **Repro:** With sandbox exports, get P1-1 flashcard fc8: its front is `How do you interpret $px^2+qx+r<ax+b$ graphically?`. Call `anki.to_anki(front)` and feed the result to a stdlib HTMLParser subclass printing handle_data; call close(). The HTML is `How do you interpret \(px^2+qx+r<ax+b\) graphically?`.
- **Expected:** Anki receives escaped HTML containing the entire inequality so MathJax can render it.
- **Actual:** HTMLParser emits only `How do you interpret \(px^2+qx+r`; `<ax+b...` starts an unfinished HTML tag. No HTML escaping occurs before Markdown/MathJax conversion. Native Anki rendering has not been exercised, so confidence is medium about the precise visual symptom.
- **Impact:** Published inequality flashcards can lose part of their question/formula when rendered as HTML in Anki.
### B-030 · P0 · store.py · Valid Unicode answer text silently drops its event during replay
- **Found:** 17:08 · **Method:** ran · **Confidence:** high
- **Where:** `plugin/stem-tutor/skills/tutor/scripts/tutorlib/store.py` · `Vault.events` · "path.read_text(encoding=\"utf-8\").splitlines()"; `Vault.append_event` · "json.dumps(event, ensure_ascii=False)"
- **Repro:** With a fresh sandbox and its exports, `from tutorlib import store; v=store.Vault(store.find_vault()); v.append_event({'type':'answer','response':'velocity\u2028displacement/time','item':'probe','kcs':['9702-2.1.1'],'subject':'phys','grade':{'correct':True,'score':1,'error':None,'misconception':None}}); print(list(v.events()),v.bad_lines)`.
- **Expected:** A successfully written valid JSONL event survives replay exactly, including Unicode separators inside a string.
- **Actual:** Returns `[]` and two bad-line entries. json.dumps leaves U+2028 literal (valid JSON), but splitlines treats it as a record separator and splits the event into invalid fragments. No torn write or invalid UTF-8 is involved.
- **Impact:** Pasted text containing a Unicode line separator silently loses its associated learning event on rebuild/model upgrade, violating the fold/round-trip invariant. Newline-delimited iteration also addresses this while fixing the separate B-012 torn-byte recovery case.
- 17:08 VERIFIED B-013 · same-minute incremental Anki collision regression passes; 15 store/Anki tests pass after removing the sandbox environment override from vault-discovery tests
- 17:08 SWEEP · (4) store.py + deps.py + anki.py + JSON round trips · ran 15 tests, torn-UTF-8 replay, valid Unicode separator replay, cross-topic incremental Anki export and inequality HTML parsing probes · findings: B-028 B-029 B-030; reopened B-012
### B-031 · P0 · screens.py · AI answer guard is disabled on feedback while another question remains open
- **Found:** 17:09 · **Method:** ran · **Confidence:** high
- **Where:** `app/tutor_app/screens.py` · `SessionScreen.action_ask` / `action_explain` · "open_n = self.view[\"n\"] if ... else None"; `_stream` · "if not open_n: w.update(cards.ai(buf))"
- **Repro:** Create `/tmp/bugwatch-app-secondary` with sandbox.sh. Export R and app/engine PYTHONPATH, then run `bash "$R/bugwatch/check.sh" /tmp/bugwatch-scratch/test_secondary_leak.py -q -s`. Headless pilot starts Test on 9702-1.1 (seed 1, two questions open), answers Q1 with don't-know, and asks about still-unanswered Q2 from the feedback screen. Fake AI returns `The answer is B: 1.5 m s⁻¹.`; no live AI is used, and iPad inbox is redirected to /tmp.
- **Expected:** Guard every still-open question, including Q2 while the screen is showing Q1 feedback.
- **Actual:** The detector correctly identifies the supplied reply as a leak when called directly, but action_ask passes open_n=None because self.view still refers to answered Q1. The reply is rendered and saved in Lessons; Q2 remains open. Pilot prints `guard detects True`, `LEAK_IN_LOG True`, `OPEN ['2']`.
- **Impact:** The pre-attempt answer protection is bypassed on a normal between-question screen. This is separate from B-018's detector-pattern fixes: the working detector is never invoked here.
- 17:11 VERIFIED B-014 · 54 app tests pass, including AI-marking failure restoring self-mark controls
- 17:11 VERIFIED B-015 · 54 app tests pass, including submitted long-answer working remaining in the lesson log
- 17:11 VERIFIED B-016 · 54 app tests pass, including preserving both imported PDFs and original inbox files across name collisions
- 17:11 VERIFIED B-017 · overlapping fake-AI requests remain capped in the 54-test app run (the already documented stream/one-shot reservation limit was not re-reported)
- 17:11 VERIFIED B-018 · direct disclosure and harmless-hint regression cases pass; separate missing guard invocation is B-031
- 17:11 SWEEP · (5) app/tutor_app · ran 54 existing app tests plus headless secondary-open-question disclosure pilot; read panels, screen transitions, streaming, prompts, settings and Mac helpers · findings: B-031
- 17:12 VERIFIED B-019 · numeric version-pruning regression passes in the 30-test publish/validate/packs run
- 17:12 SWEEP · (6) build publish pipeline · ran 30 tests, all seven published pack validators, 26,901 item instantiations, teach-card validation and figure existence checks; apparent duplicate MCQ options were case-sensitive SI units or image-backed diagrams, not findings · clean
### B-032 · P1 · session.py · Test-repair teaching is absent from Now and the lesson transcript and is skipped on resume
- **Found:** 17:13 · **Method:** ran · **Confidence:** high
- **Where:** `plugin/stem-tutor/skills/tutor/scripts/tutorlib/session.py` · `Tutor._step_learn` · "return {\"activity\": \"teach\", \"block\": \"learn\""; `Tutor._write_now` handles `explain` but not `teach`
- **Repro:** In a fresh sandbox, create Tutor with random.Random(5), start('test',focus=['9702-2.1.4']), answer initial questions with don't-know, then next(). It returns teach, titled 'Velocity from a displacement-time graph'. Inspect Now.md and the session's Lessons log, then instantiate a fresh Tutor on that vault and call next().
- **Expected:** The repair explanation shown in the app is mirrored in Now.md and the full lesson transcript; saving/restarting at that screen resumes the explanation until continued.
- **Actual:** session['now']['activity'] remains feedback; neither Now nor Lessons contains the outline or its teaching title. Restart returns worked, skipping the teaching screen. `_step_learn` increments its step before returning without awaiting, setting Now or logging the explanation.
- **Impact:** Normal Test prep repair teaching disappears from the promised live/full notes, and a student who saves mid-explanation cannot resume it. B-020's worked-example resume fix passes; this is the preceding teach branch.
- 17:14 VERIFIED B-012 · original torn-UTF-8 scratch evidence now replays the two valid surrounding events and reports only line 2 as bad at 1fb1360
- 17:14 VERIFIED B-030 · original U+2028 scratch event now replays intact with zero bad lines at 1fb1360
- 17:14 SWEEP · (7) SCOPE invariants · ran five complete lesson/test/long sessions over 76 actions with state-fold and JSON session-reload checks on every action, plus generated-note lint (zero issues); revisited interrupted replay proofs · findings: B-032
### B-033 · P1 · screens.py · AI hints bypass no-help checks and earn unassisted credit
- **Found:** 17:18 · **Method:** ran · **Confidence:** high
- **Where:** `app/tutor_app/screens.py` · `SessionScreen.action_ask` · "self.stream(prompts.ask(self.tutor, q, self.kc))"; `_stream` only checks direct disclosures; `tutorlib/session.py` · `Tutor._record` · "if p[\"unassisted\"] and g[\"correct\"] and not p[\"hinted\"]"
- **Repro:** Create `/tmp/bugwatch-ai-hint` with sandbox.sh; export R and app/engine PYTHONPATH; run `bash "$R/bugwatch/check.sh" /tmp/bugwatch-scratch/test_ai_hint_credit.py -q -s`. Pilot starts Test 9702-1.1 seed 1. For published p04, normal hint() refuses because unassisted=True. Ask the AI for a hint; fake AI gives a units-solving strategy (no answer), which is shown and logged. Answer C correctly. No real AI or iCloud inbox is used.
- **Expected:** No-hint checks cannot receive substantive AI help and then count as independent success; any permitted assistance is tracked as hinted.
- **Actual:** The AI hint appears, but p.hinted stays False. The answer event records hinted=False, score=1, and removes the seeded gap for this idea. The AI prompt does not even indicate that this is an unassisted check.
- **Impact:** Normal ctrl+t/ctrl+r help can clear gaps and contribute toward mastery/spacing as independent recall, contradicting the guide's no-hint checks and secure-without-help rule. This is distinct from B-031: the direct-answer guard works, but ordinary hints are untracked.
- 17:19 SWEEP · (8) guide versus code · read the guide against session, model, views and AI paths; ran headless no-help-check/AI-hint credit pilot with a fake response · findings: B-033
### B-034 · P0 · grade.py · Correct Unicode maths is recorded as wrong rather than accepted or left open
- **Found:** 17:20 · **Method:** ran · **Confidence:** high
- **Where:** `plugin/stem-tutor/skills/tutor/scripts/tutorlib/grade.py` · `_sympy.parse` · "if not _EXPR_TEXT.fullmatch(s)" (ASCII whitelist); `session.py` · `Tutor.answer` · "elif inst[\"kind\"] == \"short\" and g[\"needs_judgement\"]"
- **Repro:** In sandbox `/tmp/bugwatch-expression-unicode`, start a Tutor Test session; select published `9702-2.1-i24` from `t.packs.pack('9702-2.1')['items']`; present it with `t._present(item,'practice',None)` and answer with `t.answer(f'{n} = u² + 2as ~4')`. Repeat with `u^2 + 2×a×s` and ASCII `u^2 + 2as`.
- **Expected:** Equivalent standard mathematical notation is marked correctly, or unsupported notation is refused while keeping the question open for correction.
- **Actual:** Both Unicode answers earn 0 and close the question; ASCII earns 1. The parser raises on superscripts/multiplication symbols, `_grade_expression` asks for judgment, but Tutor.answer honors needs_judgement only for short answers and records an incorrect learning event. The app's expression input does no Unicode normalization, while its own maths renderer displays superscripts.
- **Impact:** A student typing/pasting the mathematically correct expression in the app's displayed notation loses all marks and changes their learning history. Numeric input already supports Unicode normalization; expressions do not.
- 17:20 VERIFIED B-024 · 242 focused engine/app tests pass, including swapped-keyword answers waiting for judgment at both grade and session layers
- 17:20 VERIFIED B-025 · the 242-test run includes finite extreme magnitudes without overflow, plus all existing numeric/unit/s.f. checks
- 17:20 VERIFIED B-026 · the 242-test run includes notes refreshing for every answered idea at session end
- 17:20 VERIFIED B-027 · the 242-test run includes multi-idea retest scores assigned to the selected experiment idea
- 17:20 VERIFIED B-031 · the 242-test run includes AI reply guarding while a secondary question remains open
- 20:57 SWEEP · 2026-10-01 refreshed baseline · ran bash bugwatch/check.sh: 528 passed in 42.30s at HEAD 5c7ea70 · clean
### B-035 · P2 · units.py · A short malformed unit stalls synchronous grading with exponential splitting
- **Found:** 20:58 · **Method:** ran · **Confidence:** high
- **Where:** `plugin/stem-tutor/skills/tutor/scripts/tutorlib/units.py` · `_splits` / `parse_unit` · "for rest in _splits(sym[i:])" and "for split in _splits(sym)"
- **Repro:** With sandbox.sh exports, run a subprocess calling `from tutorlib.units import unit_factor; unit_factor("m"*30, "m")`, with subprocess.run(..., timeout=2). A 16-character run returns in 0.029 s; 24 takes 0.661 s; 30 exceeds the two-second timeout and is killed. Equivalent student input is a numeric answer followed by thirty m characters.
- **Expected:** An invalid unit should be rejected promptly, without enumerating every possible grouping of its letters.
- **Actual:** Every m/mm decomposition is generated recursively and accumulated before dimension matching. Even this short malformed unit exceeds two seconds; longer input grows exponentially without a length/work bound.
- **Impact:** A pasted or repeated-key unit can freeze the app while its synchronous answer handler grades it. This is separate from the fixed exponent-overflow and expression-parser bounds.
### B-036 · P0 · grade.py · Bare superscript powers are silently read as decimal digits in numeric answers
- **Found:** 20:59 · **Method:** ran · **Confidence:** high
- **Where:** `plugin/stem-tutor/skills/tutor/scripts/tutorlib/grade.py` · `_parse` · "t = text.translate(SUPERSCRIPT)"; `session.py` · `Tutor.answer` · "problem = grade.value_problem(inst, str(r[\"value\"]))"
- **Repro:** With sandbox.sh exports, instantiate published 9702-5.1-i10 with random.Random(4): a 40 W motor runs for 25 s, answer 1000 J. `grade.parse_quantity("10³ J")` returns `(103.0, "J", 3)`. `grade.value_problem(item, "10³ J")` returns None; grade_item with kind=value and that text returns correct=False, score=0. The same parser reads 10² as 102 and 10⁴ as 104.
- **Expected:** Preserve the mathematical value of superscript notation, or refuse unsupported notation while keeping the question open. Any precision issue should not turn 1000 into 103.
- **Actual:** Global superscript-to-digit translation concatenates exponent digits onto the mantissa. The answer is considered readable and receives an incorrect-value mark; numeric answers do not route needs_judgement through the short-answer review.
- **Impact:** Normal pasted mathematical notation can record a false numerical error and alter the student's learning history. B-034 fixed expression normalization; numeric normalization still has this separate defect.
- 20:59 VERIFIED B-034 · fresh baseline covers Unicode expressions and unreadable-expression retry; published expression key also passes direct grading
- 20:59 SWEEP · (1) grade.py + units.py + packs.py · ran 2,130 allowed-precision answers across published packs, distractor probes, equivalent-unit checks, bounded malformed-unit subprocesses and Unicode-number probes · findings: B-035 B-036
- 21:01 SWEEP · (2) model.py + policy.py + profile.py + experiments.py + weekly.py · read all five modules; ran 200 mixed-score/hint/confidence events with a JSON round trip after every event, four mode planners and profile workload; baseline includes prior experiment/model regressions · clean
### B-037 · P1 · report.py · Past-paper mistakes lose their question text in the mistake journal
- **Found:** 21:01 · **Method:** ran · **Confidence:** high
- **Where:** `plugin/stem-tutor/skills/tutor/scripts/tutorlib/report.py` · `_item_stem` · "subtopic = item_id.rsplit(\"-i\", 1)[0]"; `session.py` · `Tutor._record` · "if inst.get(\"source\") else {\"stem\": inst.get(\"stem\", \"\")}"
- **Repro:** With sandbox.sh exports, create Tutor, start Test focused on 9702-1.1, take published item 9702-1.1-p01, present it with `t._present(item, 'practice', None)`, answer its number with '?', then call `report.mistakes_note(t)` and read Mistakes.md. Also reproduced naturally in the four-goal lesson walk.
- **Expected:** The journal includes the attempted question, 'Which quantity is a physical quantity?', alongside its right answer.
- **Actual:** It writes 'Question: not recorded' and 'Right answer: D: potential difference'. Events omit stems whenever an item has a source, then reconstruction only recognizes the -i ID separator; published past-paper questions use -p. The original question remains available in the pack but is never found.
- **Impact:** Normal mistakes on past-paper bank questions produce an incomplete revision journal with an answer detached from its question. The current lesson transcript still retains the question.
- 21:02 VERIFIED B-032 · baseline passes the repair-teaching mirror/resume regression; four-goal lesson walk resumes every saved activity without state drift
- 21:02 SWEEP · (3) session.py + lesson.py + views.py + report.py · read lifecycle, marking, lesson phases, notes and reports; ran four complete lesson goals with reload/fold checks after each activity and a published past-paper mistake-journal probe · findings: B-037
### B-038 · P0 · session.py · An interrupted answer save permanently separates cached progress from its event log
- **Found:** 21:02 · **Method:** ran · **Confidence:** high
- **Where:** `plugin/stem-tutor/skills/tutor/scripts/tutorlib/session.py` · `Tutor.log` · "e = self.vault.append_event(event, now=self.now())" before "self._save()"; `Tutor.__init__` · "if not self.state or self.state.get(\"model_version\") != model.MODEL_VERSION"
- **Repro:** Create a fresh vault with `bash "$R/bugwatch/sandbox.sh" /tmp/bugwatch-oct1-interrupt`, use its exports, and run `/tmp/bugwatch-scratch/interrupted_answer_probe.py`. It starts Test, submits the correct first MCQ, and injects an interruption at _save after the complete answer event was appended. It then constructs a new Tutor and answers the still-open question again.
- **Expected:** On restart, reconcile the saved learner/session state with durable answer events, preserving the answer once and keeping live state equal to replay.
- **Actual:** The event log contains one complete answer, but the restarted learner has n=0 while replay has n=1; the same question is still open. Answering again produces live n=1 and replay n=2, so ordinary subsequent saves preserve the divergence. The current model-version cache is trusted without checking whether events were appended since it was saved.
- **Impact:** A process interruption or save error between separate writes loses recorded progress from the live model and permits duplicate attempts; a later rebuild changes history again. Individual atomic JSON files do not make the event/state/session transaction recoverable.
- 21:03 VERIFIED B-028 · independent cross-pack export now emits 5 then 4 cards with nine distinct pack-qualified IDs
- 21:03 VERIFIED B-029 · independent HTML parser receives the complete inequality after Anki conversion, including <ax+b
- 21:03 SWEEP · (4) store.py + deps.py + anki.py + JSON round trips · read persistence/dependency/export code; ran interrupted-answer recovery, cross-pack export and inequality HTML probes; baseline covers torn bytes and Unicode event separators · findings: B-038
- 21:03 REPLY B-028 · Correction to my preceding VERIFIED line: this run emitted 5 then 1 cards, six distinct IDs. The current pack marks fc1, fc2 and fc4 in_anki, so only fc3 is eligible. The cross-pack collision is still verified fixed; the earlier count of four was stale and was written before inspecting the run output.
### B-039 · P1 · screens.py · Failed AI requests remove independent-answer credit despite delivering no help
- **Found:** 21:04 · **Method:** ran · **Confidence:** high
- **Where:** `app/tutor_app/screens.py` · `SessionScreen.stream` · "self.tutor.ai_help()" before "self._stream(prompt, then_continue)"; `_stream` · "if not a.last.ok" only displays the error
- **Repro:** Create `/tmp/bugwatch-oct1-ai-fail` with sandbox.sh. Export R and app/engine PYTHONPATH, then run `bash "$R/bugwatch/check.sh" /tmp/bugwatch-scratch/test_failed_hint_probe.py -q -s`. The pilot presents exactly one assisted-allowed MCQ, asks a fake Claude configured to return a login error, then answers correctly. Inbox import and Obsidian launch are disabled in the probe.
- **Expected:** If no AI help is delivered, the correct independent attempt retains its normal learning credit.
- **Actual:** The AI result is ok=False, status=login, text='', but the presented question has already been saved with hinted=True. Its correct score=1 event stays hinted=True and adds no success day. Output: `AI outcome False login text '' hinted True` and `answer hinted True score 1.0 success days []`.
- **Impact:** Authentication/network/usage failures can weaken ability updates and prevent mastery credit even though the student received no help. This uses only one open question and is separate from the already-in-progress unseen-second-question issue in FIXES.md.
