# Changelog

## 1.1.0 — 2026-09-30

### Learning algorithms
- FSRS now uses all four grades: wrong → Again; right only with a hint, or right but guessing/unsure → Hard; right →
  Good; certain on an idea already recalled on two earlier days → Easy.
- Exam-aware retention: each answer records a retention target that rises as the idea's exam approaches (planner dates;
  AS 2027 / A2 2028 estimates for CAIE), bounded 0.85–0.97, so rebuilds reproduce scheduling exactly.
- Reviews ordered by forgetting risk (1 − recall probability) weighted towards sooner exams, then interleaved across
  subtopics.
- Successive relearning: a missed review/practice idea is re-asked later in the same session with a different item.
- Likely slips (fast miss on an idea normally answered correctly, with no misconception) halve the ability update.
- Fatigue measured as accuracy against expectation; one break suggestion per session.
- Problem-first method now delivers a real challenge phase; the "quick" goal never joins method experiments.
- Blurting (free recall) scored offline from each idea's glossary and title terms; missed ideas already studied come due.

### Profiling
- New `tutorlib/profile.py`: confidence table per level, time-of-day and stamina residuals, mistakes by kind,
  forgetting vs forecast, pace, study habits, 7-day workload, experiments, plain-English advice.
- Profile.md rewritten in plain English; the app's My progress screen uses the same summary.
- Profile adjustments are now real in the app: checking routine, confidence notes, have-a-go-first hints, break point.
- One-key "why did I miss it?" reflection after unexplained wrong answers (capped at 6 per session, skippable).

### App
- Keys that work while typing: ctrl+t ask, ctrl+g hint, ctrl+r re-explain, ctrl+o Obsidian, ctrl+b / ctrl+q back to menu.
- Blurt screen; richer My progress; version shown on the menu.
- Guard before abandoning an unfinished session; resume restores elapsed time and revealed worked-example steps.
- Esc on the confidence step returns to the answer; review with nothing due no longer starts an empty session.

### Fixes
- Diagnose mode KeyError when an item's first idea wasn't the probed one.
- Review/exit blocks skipped remaining ideas after a batch without usable items.
- `pts=` on non-long questions, `5/0`, `1e999` and huge exponents no longer crash grading.
- Second Anki export in a run crashed on the yaml stub.
- A corrupt line in the event log no longer blocks the whole history.
- Stuck ideas were reported as learned; re-teaching an idea erased the learner's earlier own-words note and mistakes.
- Paper scores above the marks available are rejected; `end()` with no session logs nothing; plans with nothing to
  teach give a practice check instead of an exit ticket on untaught ideas.
- Right value but mark lost (units/s.f.) now counts as not yet correct everywhere (session score, gaps, lesson checks).
- AI: stopping a reply midway desynchronised later replies; login/limit states never recovered; answers could leak via
  re-explain; ctrl+q quit the app mid-session; option labels lost maths such as `v[y]`; commas split typed answers.
- Settings and usage files load safely and save atomically; settings inputs are clamped.

### Performance
- FSRS schedulers cached; the menu no longer refolds the whole history; streak and last Anki export kept in state.
- Learner state saved only after it changes, as compact JSON; answer map bounded; view files written atomically and
  skipped when unchanged; AI usage counter cached in memory; maths library warmed in the background.
- Saved states from 1.0 are rebuilt once from the event log (model version 1.1).

## 1.0.0 — 2026-09-30
- Terminal app (Textual) with lesson mode (goal → probe → plan → teach per idea), review, test prep, long questions and
  chat; Obsidian views (Now, Lessons, My Notes, Home); lean headless Claude on the subscription; local vault; teach cards
  for the 7 published packs; plain-English guide.
