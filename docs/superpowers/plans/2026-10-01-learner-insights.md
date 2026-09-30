# Learner insights and four study tools: implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax. Compact by design (the learner's token budget is tight): each task names its
> interfaces, tests and behaviour; the code is written once, test-first, in the files themselves.

**Goal:** Implement `docs/superpowers/specs/2026-09-30-learner-insights-design.md` and release it as 1.2.0.

**Architecture:** A new engine module `tutorlib/insights.py` computes everything as plain dicts from the tutor (state,
packs, event log). `report.py` renders them into vault notes, and the Textual app renders the same Markdown in a new
screen. One new session mode, `weak`, goes in `policy.plan_session`. The AI summary is a single `one_shot` call
through the existing client.

**Tech stack:** Python 3.13, Textual, pytest; engine at `plugin/stem-tutor/skills/tutor/scripts/tutorlib/` (below:
`tutorlib/`); app at `app/tutor_app/`. Tests run with `bash bugwatch/check.sh <paths> -q`.

## Global constraints

- No AI in anything computed. Certainty labels: `not enough data` (no data), `early sign` (below the engine's action
  threshold), `likely` (at or above it), `clear` (at least 3× it).
- Thresholds are the engine's own: retention knob n ≥ 10 reviews per subject; calibration advice n ≥ 30 rated answers;
  mistake pattern ≥ 8 classified mistakes; time of day and stamina `profile.MIN` = 12 answers per block; hints ≥ 20
  answers; low accuracy = at least 3 answers and under 50% right.
- Notes must pass `tutorlib.lint.lint` with no findings. Lines ≤ 120 characters; match the surrounding style.
- Never touch the real vault or the real iPad inbox in tests (fixtures: `make_vault`, `app_for`, `pin_clock`).
- Commit after each task, ending with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

---

### Task 1: findings (engine)

**Files:** create `tutorlib/insights.py`; test `tests/test_insights.py`.
**Interfaces:** produces `insights.findings(tutor) -> dict` with keys `recorded` (dict of counts), `items`
(list of `{"area", "headline", "detail", "certainty", "n", "action"}`), `adjustments` (list of str),
`never` (list of str); `insights.certainty(n, threshold) -> str`. Consumes `profile.summary`, `model.knobs`,
`experiments.analyze/preferred`, `tutor.vault.events()`.

- [ ] Tests: `test_certainty_labels` (0, below, at, 3× threshold); `test_a_new_learner_gets_honest_empty_findings`
  (every item `not enough data`, no action, `recorded["answers"] == 0`); `test_misconception_finding_quotes_the_pack`
  (answers that trigger a misconception, then the finding quotes the pack's statement); `test_overconfidence_is_found_and_acted_on`
  (30+ confident wrong answers: calibration item `likely`, action mentions confidence feedback).
- [ ] Run: fail (module missing). Implement. Run: pass. Commit `feat(engine): insights findings with evidence and certainty`.

### Task 2: exam readiness

**Files:** `tutorlib/insights.py`; `tests/test_insights.py`.
**Interfaces:** `insights.readiness(tutor) -> list[{"exam", "date", "estimated", "days", "ideas", "built", "started",
"secure", "recall_if_stop", "recall_if_keep"}]`, upcoming only, soonest first. Groups KCs by `policy.exam_date`;
label from the plan's sittings when a sitting's spec matches, else `"<spec> (estimated)"`. Recall values are means over
started ideas (`model.retrievability` at the exam date; `policy.target_retention` at the exam date), `None` when none
are started.
- [ ] Test `test_readiness_counts_and_forecasts` (fixture spec 9702: ideas/built/started counts after one study session;
  `recall_if_stop < recall_if_keep`; past exams excluded). Fail, implement, pass, commit `feat(engine): exam readiness`.

### Task 3: weak spots and the `weak` session mode

**Files:** `tutorlib/insights.py`, `tutorlib/policy.py` (`plan_session`); `tests/test_insights.py`.
**Interfaces:** `insights.weak_spots(tutor) -> list[{"kc", "title", "subtopic", "reasons": [str]}]`, only KCs with
questions, ordered misconception > gap > low accuracy, then sooner exam. `plan_session(..., mode="weak", focus=kcs)`:
learn blocks for the first `n` of `focus` (n as for autopilot), a practice block on the rest, an exit block; the app
passes `focus=[w["kc"] for w in weak_spots(tutor)]`. `Tutor.start("weak", focus=...)` must not trip the
"no questions built" guard.
- [ ] Tests `test_weak_spots_order_and_reasons`, `test_weak_mode_plans_learn_then_practice`. Fail, implement, pass, commit
  `feat(engine): weak spots and a session mode for them`.

### Task 4: week report

**Files:** `tutorlib/insights.py`; `tests/test_insights.py`.
**Interfaces:** `insights.state_at(tutor, when) -> dict` (replay events with `ts < when`);
`insights.week_report(tutor, monday: date) -> dict` with `week` ("2026-W40"), `days`, `minutes`, `answers`,
`right` (fraction or None), `right_change` (vs the week before, or None), `secured` (list of KC ids), `fixed`
(misconceptions no longer active), `changes` (list of str: knob and experiment changes).
- [ ] Test `test_week_report_counts_a_scripted_week` (events stamped inside and outside the week; secured and changes
  detected). Fail, implement, pass, commit `feat(engine): week report`.

### Task 5: notes

**Files:** `tutorlib/report.py` (`profile_note` rewritten; new `mistakes_note`, `week_note`), `tutorlib/weekly.py`
(`run` also writes Mistakes.md); tests `tests/test_insights.py`, `tests/test_report.py`
(`test_profile_note_contains_traits_and_is_lint_clean` updated to the new headings).
**Interfaces:** `report.insights_markdown(tutor, ai: dict | None) -> str` (shared by Profile.md and the app);
`report.profile_note(tutor) -> str` (path); `report.mistakes_note(tutor) -> str`;
`report.week_note(tutor, monday) -> str` ("Weekly/2026-W40.md"); `report.load_ai_summary(tutor) -> dict | None`
reading `.tutor/profile_ai.json`.
- [ ] Tests: Profile headings (What the tutor has recorded, What it has worked out, What the tutor has adjusted for you,
  Exam readiness, Weak spots, What it never does) and lint-clean; `test_mistake_journal_has_the_right_answer_and_right_since`;
  `test_week_note_is_written`. Fail, implement, pass, commit `feat(notes): insights report, mistake journal, weekly page`.

### Task 6: app

**Files:** `app/tutor_app/screens.py` (menu entries `insights` and `weak`; `InsightsScreen`; weekly notice in
`HomeScreen.on_mount`), `app/tutor_app/prompts.py` (`PROFILE`, `profile_summary(findings_md) -> str`);
test `tests/app/test_tui.py`.
**Behaviour:** InsightsScreen renders `report.insights_markdown`; `a` runs `ai.one_shot(prompts.profile_summary(...),
schema=prompts.PROFILE)` when AI is on and available (else notify the reason), stores `{"text", "at"}` in
`.tutor/profile_ai.json` and re-renders; `o`/`m`/`w` write and open Profile/Mistakes/latest weekly in Obsidian.
Weak spots entry shows the count; with none it notifies instead of starting. On open in a new week with study last week
and no `Weekly/<last week>.md`, write it and notify "Your week in review is ready".
- [ ] Tests: `test_insights_screen_and_ai_summary` (fake Claude returns a summary; stored and shown);
  `test_fix_my_weak_spots_with_none_says_so`; `test_week_in_review_is_written_once`. Menu-position tests keep working.
  Fail, implement, pass; full suite; commit `feat(app): what the tutor knows about you, weak spots, week in review`.

### Task 7: docs and release

**Files:** guide `build/out/notes/How It Works.md` (new section "Everything the tutor can do" after section 1 with the
full feature list; section 3 menu rows; section 8 rewritten; section 9 pages; What's new 1.2.0; version line),
`CHANGELOG.md`, `README.md`, `STATUS.md`, `bugwatch/SCOPE.md`, `plugin.json`, `app/tutor_app/__init__.py` → 1.2.0.
- [ ] Guide lint clean; full suite green; end-to-end run on a scratch vault; commit `v1.2.0: …`; tag; publish; memory.
