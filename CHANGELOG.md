# Changelog

## 1.2.0 — 2026-10-01

- **What the tutor knows about you** (menu, and Profile.md): every finding the tutor has worked out, with the
  evidence, how sure it is (not enough data / early sign / likely / clear, tied to the thresholds at which the tutor
  acts) and what it changed because of it; what was recorded; adjustments in force; what it never does. Press **a**
  for a short AI summary of the findings (one reply; only the findings are sent).
- **Fix my weak spots** (menu): a session on active misconceptions, gaps and ideas answered right under half the time.
- **Exam readiness** per exam: syllabus built, started and secure; predicted recall on the day if reviews stopped now
  vs kept up.
- **Mistake journal** (`Mistakes.md`): every wrong or unknown answer with the right answer, marked when put right.
  Answer events now log the key as shown.
- **Week in review** (`Weekly/<year>-W<nn>.md`), written once when the app opens in a new week.
- The guide starts with **Everything the tutor can do**, the full feature list.

## 1.1.5 — 2026-09-30

- **Your Almanac plans your day in the app.** The terminal app could not reach the engine's Almanac-driven plan:
  the menu now starts with **Today's plan** (due reviews, then the Almanac's topics in week order, practice, an exit
  check). The home screen shows this week's Almanac objectives and which have questions yet; `Today.md` is written
  when the app opens, not only after a session, and matches your session length; the home screen says when
  `A-Levels.html` has changed since the plan was built (the plan now records the file's path and fingerprint).

## 1.1.4 — 2026-09-30

- **The app always starts.** Opened from `Start Tutor.command`, it runs under Terminal, and macOS privacy settings
  can stop Terminal reading iCloud Drive; listing the iPad inbox then crashed the app at start-up. It now starts
  anyway and says how to allow access; a file still downloading from iCloud is left for next time instead of
  stopping the import; `tutor doctor` shows whether the inbox can be read.

## 1.1.3 — 2026-09-30

- **Chapters reach you as soon as they are done.** Signing a chapter in the foundry publishes it into the vault,
  commits it and notifies you; the app picks it up at the menu ("New chapters ready: …") without a restart, and a
  running session survives the old content version being pruned.
- Foundry: progress survives a session that stops (state on disk after every step; Codex jobs finish on their own;
  Haiku jobs that were cut off are flagged as stalled and re-sent); a live `foundry watch` screen, Mac notifications,
  parallel Haiku solvers per chapter with the checker alongside, and `bin/foundry` that works from any folder.

## 1.1.2 — 2026-09-30

### Content
- Past-paper questions that Cambridge printed in two papers (the P11/P13 timezone variants, sometimes a later year)
  were in the bank twice under different ids: 23 repeats removed, none lost. `add_past.py` now skips a question
  already in the pack, files a question on two subtopics under its first one, and keeps ids stable;
  `validate_pack.py` rejects a repeated question.
- The vault's `Assets/mcq` held 2,094 old copies named "… 2.png" (from a Finder "keep both" merge, not the app) and
  a stray copy of one Subjects note; moved to the Bin (49 MB).

### Tools
- **Content foundry** (`foundry/`): chapters built by Codex workers (draft, tiebreak, fix) and Claude Haiku workers
  (blind solve, rule check), with Opus managing from a board and small packets; deterministic gates between steps.
- The doctor accepts a vault opened from a parent folder in Obsidian.
- Guide and README updated to this version.

## 1.1.1 — 2026-09-30

Bug-hunt release: a second AI (Codex) searched for bugs live while Claude fixed them (`bugwatch/`), then a Haiku
review pass checked each area once more. 34 Codex findings fixed with tests, plus 3 found while fixing and 3 from the
Haiku pass; details in `bugwatch/FIXES.md`.

### Marking
- Numbers: `exact` answers allow no error (118 is not 117); a value correctly rounded to the learner's own s.f. is right
  (16 N for 16.46 N), with the s.f. rule deciding full or half marks; "20" is read strictly as 2 s.f.; a unit or sum
  after a plain-number answer ("500 kg", "500 + 1", "2^10") is refused and the question stays open ("%" only where the
  question asks for a percentage); compact units after a slash ("kg/ms2") put every factor below the line; "ms-1" as
  the expected unit also matches "m/s", and an identical unit (°C) always matches; extreme exponents and wildly wrong
  values no longer crash grading.
- Expressions: parsed as plain maths only (they could run Python before), can't freeze grading with huge powers, are
  checked at negative values too (abs(x) is not x), read "as" and subscripts (R1, m2) as variables, accept Unicode maths
  as the app displays it (u², 2×a×s, π, √), and an unreadable one stays open instead of being marked wrong.
- Written answers are never marked right on keywords alone: every short answer is judged (AI examiner or self-mark).

### Your work is kept
- Lesson logs and Anki exports made in the same minute no longer overwrite each other; iPad imports never overwrite a
  PDF; the event log survives a crash mid-save (even mid-character) and answers containing Unicode line separators;
  re-teaching keeps every paragraph of your own words; long-answer working is saved to the lesson log; a failed AI
  marking gives the tick list back. Tests can no longer touch the real iPad inbox.

### Learner model and teaching
- Study from midnight to 5 am counts as late night; hinted answers don't clear a misconception; lost-mark answers count
  as misses in the profile and session notes (saved progress is rebuilt from the event log once, model 1.1.1).
- Repair teaching, worked examples and trap cards in Test/repair sessions show in Now, are logged, and resume after a
  restart; finished teaching experiments now pick the method; retest scores go to the idea being retested; My Notes
  refreshes for every idea answered in a session.
- AI help: replies are checked for the answer of every open question; asking the AI during a question counts as a hint,
  and no-help checks refuse it; overlapping requests respect the daily cap.
- Anki: cards from different topics no longer block each other; inequalities and arrows survive as HTML.
- Terminal maths: no raw LaTeX left (≥, ≤, ≠, …, column vectors, words inside formulas).
- Publishing keeps the two newest rollback versions after v9.

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
