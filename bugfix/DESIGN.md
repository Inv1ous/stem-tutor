# How STEM Tutor is built: the rules a fix must follow

This is the house style of the code you are fixing, written by the engineer who designed it. A fix that works but
does not read like the code around it is sent back. When this file and the code disagree, the code around your change
wins; say so in your report.

## 1. Who it is for

One A-Level student (CAIE Physics 9702, Chemistry 9701; Edexcel IAL Maths P1–P4, FP1, M1, S1) studying alone, in a
macOS Terminal window beside Obsidian. Every decision follows from: **never cost the learner a mark, their work, or
their trust.** In order:

1. **Never reveal an answer before the learner has tried.** Not in the terminal, not in Obsidian (Now.md, Lessons),
   not through the AI tutor, not through read-aloud, not through a hint that gives the number.
2. **Mark exactly as the exam board would.** Never more lenient than the mark scheme (a wrong answer marked right
   teaches the wrong thing); never stricter than the scheme allows (an answer the examiner accepts must score).
   CAIE: answers to 2 or 3 significant figures unless the question asks otherwise; a final answer rounded from a
   correct unrounded value is right; units required where the scheme requires them. Edexcel IAL: exact forms (surds,
   fractions, π) where the question says "exact"; "a.w.r.t." accuracy where the scheme gives it.
3. **Never lose what the learner did.** Typed text, selected mark points, own-words notes, progress, ticks. Leaving a
   screen keeps the draft or asks first (`ConfirmScreen`). A write that can fail must not leave a half file.
4. **Plain words.** Everything the learner reads is short, plain English (British spelling: colour, organise,
   practise as a verb). Say what happened and what to do next. No jargon, no blame.

## 2. Where things live

- `plugin/stem-tutor/skills/tutor/scripts/tutorlib/` — the engine, pure Python, no UI. `session.Tutor` runs a session;
  `grade.py` marks; `units.py` reads quantities; `model.py` is the learning model (FSRS + ability θ); `policy.py` picks
  what comes next; `views.py` writes the Obsidian notes; `store.py` is all file access; `speech.py` turns text into
  what is said aloud; `almanac.py` talks to the learner's planner.
- `app/tutor_app/` — the Textual app: `app.py` (shell, keys), `screens.py` (screens), `panels.py` (answer panels),
  `cards.py` (cards in the session log), `look.py` (themes), `ai.py` + `prompts.py` (the AI tutor and its answer-leak
  guard), `tts.py` (playing speech), `texmath.py` (LaTeX to terminal text).
- `build/` — the content pipeline (mining past papers, checks in `content_checks.py`, `publish.py` into the vault).
- Content packs: `build/out/packs/<spec>/<subtopic>.json` (items, hints, explanations, worked examples).

## 3. Engine invariants (breaking one is a blocker)

- **The event log is the truth.** `events.jsonl` is append-only (`Vault.append_event`); state is a fold of the events
  (`model.apply`), cached and refolded when the log is ahead. Never "fix" the cache alone: fix the event or the fold.
- **Every write goes through `store.write_text` / `store.write_json`** (atomic: temp file, then rename). Never
  `open(..., "w")` on a vault file. Never write outside the vault, and never into the learner's real vault from tests.
- **Time comes from the tutor** (`tutor.now()`; tests set `STEM_TUTOR_NOW`). The learner is in Hong Kong (UTC+8):
  "today" is their local date. A session across midnight belongs to both days where that matters.
- **Mastery** = θ ≥ 0.8 and right on at least 2 different days. Partial or self-marked work counts only as the
  scheme would count it.
- **No network** in the engine and the app (the AI goes through the `claude` process only). New dependencies: none.

## 4. The app (Textual)

- **Colours only from the theme**: `look.C["role"]` in Rich markup, theme variables in CSS. Roles: text, muted, dim,
  tutor, question, you, good (right), bad (wrong), hint, ai, plan, border, panel, surface, background. Green and red
  mean right and wrong, nothing else. A card drawn once must follow a theme change (redraw from roles, don't bake hex).
- **Fits at 80×24, 100×30 and 140×46.** Nothing cut off, no label wrapped mid-word, the focused control never hidden
  under a docked row, buttons reachable. Long text wraps by words; panels scroll. Check all three sizes.
- **Keys**: shown in a hint line (`Static(..., classes="hint")`) in the app's words ("Esc for the menu", "⏎ to
  check"). Esc goes back. `?` help, `ctrl+t` ask, `ctrl+k`/F3 answer-only, F2 settings work on every screen the guide
  says. An Enter that arrives with a new question (key repeat, double press) must never submit that question.
- **Leaving keeps the work** or asks with `ConfirmScreen`. A late AI reply belongs to the question it was asked
  about, never to the next one.
- **Notifications** are one short sentence (`notify(text, timeout=4–8)`; warnings with `severity="warning"`).
- Match the surrounding widget code: same compose structure, same CSS block in the same file, same naming.

## 5. Obsidian notes (`views.py`)

- `Now.md` mirrors what is on screen; `Lessons/<day>/<HHMM> <name>.md` is the full record. A question appears there
  before it is answered, **never with its key**; the answer appears only after marking.
- Callouts `> [!kind] Title`; wikilinks without `.md`; maths as `$…$` / `$$…$$`; figures `![[file]]`.
- `My Notes` holds the learner's own words: a refresh adds or updates the tutor's part, never deletes theirs, and never
  overwrites a newer save made in Obsidian.

## 6. Read-aloud (`speech.py`)

The learner learns how science is *said*. Use the standard spoken forms: "minus" for subtraction and negative signs,
"times" for numeric multiplication (never the letter x), "gives" for a reaction arrow, "squared", "cubed", "to the
power of", units spelled out ("metres per second squared", plurals right), charges as "two plus" / "minus", option
and point letters as letters ("option A", "point A" — not the article). Nothing a question needs (a table, the
choices) is dropped.

## 7. Content packs

Keep each file's JSON formatting (its indent, key order). Ids are stable: never renumber or delete an item the
learner may have answered; correct it in place. Text passes `build/content_checks.py` (no stacked-fraction debris, no
broken LaTeX, no unsafe Unicode sub/superscript letters). A flag that changes marking (`exact`, `sf`, mark points)
must match the past paper's mark scheme.

## 8. Code style

- Python 3.13, `from __future__ import annotations`, type hints on new functions.
- **Docstrings and comments say why, in plain sentences**, often from the learner's side, and name the cause of a
  past bug where it explains a line, e.g.
  `# a stacked fraction (½) is not left broken` or
  `"""Put the text size the learner chose back on the Terminal tab. A tab's profile brings its own size …"""`.
  Write as the code around you does: similar density, no banner comments, no commented-out code.
- Plain names (`remember_font_size`, `lesson_rel`), no clever one-liners, no new abstractions for one use.
- **Smallest change at the layer that owns the behaviour.** No drive-by refactors, renames or reformatting; no
  speculative options. If the right fix is bigger than the finding suggests, do it and explain why in your report.

## 9. Tests

- pytest. One test per fixed finding (more if it has several paths), in your job's file. The name is a sentence
  about what the learner sees: `test_a_late_ai_reply_never_marks_the_next_question_as_hinted`. The docstring cites
  the finding: `"""B-065 (bug watch): …"""`.
- The test fails on the code before your fix and passes after it (run it both ways). It asserts the behaviour, not
  the implementation.
- Engine tests use the fixtures in `tests/` (`make_vault`, the `tutor` fixture pattern in `tests/test_session.py`).
  App tests use a Textual pilot: `app_for()` from `tests/app/test_tui.py`, the fake Claude in
  `tests/app/fake_claude.py`, `await pilot.pause()` after each key. Never start the real `claude`, `codex` or speech
  engine; never touch the real vault (tests use `tmp_path`).
- Visual fixes: render the screen at 80×24, 100×30 and 140×46 (`app.run_test(size=(80, 24))`) and assert what must
  be visible (a widget's region inside the screen, a label on one line). Save the SVGs you looked at under
  `/tmp/bugfix-shots/` and name them in your report.

## 10. When the finding is wrong

A finding can be mistaken, by design (see `bugwatch/SCOPE.md`, "Known and by design"), or ask for behaviour that
would be wrong for a student. Then change nothing for it and say so (REJECTED, with the evidence), or DEFERRED with
what it would take. An honest REJECTED is worth more than a fix that makes the app worse.
