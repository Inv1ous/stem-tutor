# Learner insights, and four study tools (v1.2.0)

Chosen by the learner on 2026-09-30: computed insights plus an AI summary button; exam readiness; fix my weak spots;
weekly report; mistake journal. Also: a full feature list in the guide.

## Principles

- Everything is computed from the event log and the learner state, with no AI, except the optional AI summary.
- Every finding shows its evidence (counts and rates), how sure the tutor is, and what the tutor changed because of it.
- Certainty labels follow the engine's own action thresholds, so a label never claims more than the engine acts on:
  **not enough data** (nothing yet), **early sign** (some data, below the threshold at which the tutor acts),
  **likely** (at or above the threshold), **clear** (at least three times the threshold).
- Nothing new is stored except the AI summary (`.tutor/profile_ai.json`), the notes written into the vault, and
  (added while building) the answer key as shown in each answer event, plus the question text for checks that are
  not pack items, so the mistake journal is exact.

## Units

### 1. `tutorlib/insights.py` (new): findings, readiness, weak spots, week report

- `findings(tutor) -> dict`
  - `recorded`: what the tutor has recorded (answers, sessions, study days, confidence ratings, hinted answers,
    mistakes by type, misconceptions spotted, blurts, past-paper marks, first and latest activity).
  - `items`: one finding per area. Each has area, headline, detail with numbers, certainty, n, and action (or none).
    Areas: memory per subject (review recall vs the model's forecast; retention target); confidence vs accuracy
    (bias, costly confident errors; confidence feedback); mistake pattern (top type and share; checking routine);
    misconceptions (active and fixed, quoting the pack's statement); time of day; stamina (break point); pace per
    subject vs exam pace; hints (attempt-first rule); teaching-method experiments in plain words, with the method
    now preferred per subject; strongest and weakest subtopics; study habits.
  - `adjustments`: what the tutor currently does differently for this learner (from `model.knobs` and preferred
    methods), each with the reason.
  - `never`: what it deliberately does not do (learning styles; guessing about you with AI; judging from one day).
- `readiness(tutor) -> list[dict]`: one row per upcoming exam, grouping syllabus ideas by `policy.exam_date` (Almanac
  dates; estimates when the Almanac has none, labelled "estimated"). Row: ideas in the syllabus, built, started,
  secure, and predicted recall on exam day for started ideas if reviews stopped today (FSRS retrievability at the exam
  date) versus if reviews continue (the retention target).
- `weak_spots(tutor) -> list[dict]`: ideas with questions available that are weak, each with its reasons, in this
  order: active misconception; gap (from blurts, test prep or diagnosis); low accuracy (at least 3 answers, under 50%
  right). Ties go to the sooner exam.
- `week_report(tutor, monday) -> dict`: study days, minutes (answer time), answers, % right and change on the week
  before, ideas newly secured, misconceptions fixed, and profile changes (knobs, experiments started or decided). State
  at the start and end of the week comes from replaying the event log up to each boundary.

### 2. Notes (report.py)

- `Profile.md` becomes the insights report: recorded data, findings with certainty and action, adjustments, exam
  readiness, weak spots, the "never" list, and the latest AI summary (dated, marked as AI-written).
- `Mistakes.md` (new): every wrong or "don't know" answer by subtopic, newest first. Each entry has the date, the
  mistake type in words (or the misconception's statement), the question's start, your answer, the right answer
  (re-created from the pack and the logged template values), and "✓ right since" if you later answered the same
  question correctly. Past-paper questions show the paper, question and score.
- `Weekly/<year>-W<week>.md` (new): the week report.
- `weekly.run` (after each session) also writes `Mistakes.md`. The app writes last week's report when it opens in a
  new week that has no report yet and last week had study.

### 3. Engine session mode `weak`

`policy.plan_session(mode="weak")`: learn blocks for the top weak ideas (re-teaching uses the refutation method when a
misconception is active), practice on the rest of the weak list, then an exit check. Other modes are unchanged.

### 4. App

- Menu: **◉ What the tutor knows about you** (new InsightsScreen) and **✚ Fix my weak spots (N)** (session mode
  `weak`; with none it says so instead of starting).
- InsightsScreen: the Profile.md report rendered in the app. Keys: `a` AI summary, `o` Profile in Obsidian,
  `m` Mistakes in Obsidian, `w` the latest weekly report, Esc back.
- AI summary: `prompts.profile_summary(findings)` sends only the findings text (with certainty labels, never raw
  answers) to the existing AI client as one reply; the answer is stored with its date and shown in the screen and
  Profile.md. It is refused when AI is off, unavailable or today's allowance is used, with the reason.
- Home screen on open: writes last week's report if due and says "Your week in review is ready".

### 5. Docs

Guide: a new section **Everything the tutor can do** (the full feature list, pointing to sections); the menu table
(section 3), the profile section (8) rewritten around insights, Obsidian pages (9: Profile, Mistakes, Weekly); What's
new for 1.2.0. Version 1.2.0 in the guide, README, STATUS, CHANGELOG, SCOPE, plugin.json and the app.

## Error handling

- Missing or thin data gives "not enough data" findings, never an error or an empty screen.
- A question whose pack is no longer published keeps its journal entry, with "question no longer available".
- A failed AI call shows the client's reason; the computed report is unaffected.

## Testing

- `tests/test_insights.py`: synthetic learners through the real engine. Covers empty-state findings; an overconfident
  learner (label and action); a misconception finding quoting the pack; readiness recall with known FSRS states;
  weak-spot order and reasons; the week report for a scripted week (secured ideas, changes); the mistake journal's
  right answer and "right since".
- `tests/app/test_tui.py`: the menu entries; the insights screen renders; an AI summary via the fake Claude is stored
  and shown; Fix my weak spots with none says so; the weekly notice appears once in a new week.
