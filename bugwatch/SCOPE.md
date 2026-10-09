# Scope: what the code is and where bugs likely hide

STEM Tutor 2.1.0: a terminal study app for one A-Level student (CAIE Physics/Chemistry, Edexcel IAL Maths) in Hong Kong
(timezone `Asia/Hong_Kong`). A pure-Python learning engine does teaching, marking, scheduling and note-writing with no AI.
A Textual terminal app sits on top, and Obsidian shows the notes. Claude (headless `claude -p`) is used only for
optional chat/explanations. Python 3.13, repo venv `.venv/`.

## Code map (paths from the repo root)

| Path | What it does |
|---|---|
| `plugin/stem-tutor/skills/tutor/scripts/tutor.py` | Engine CLI (`doctor`, `session start/end`, `next`, `answer`, `find`, `week`, `lint`, …) |
| `…/tutorlib/grade.py` | Parses answers (`1B3`, `2 = 4.5 m s-1 ~3`, `3?`), number/unit/s.f. grading, sympy equivalence, rubric matching |
| `…/tutorlib/units.py` | SI unit algebra |
| `…/tutorlib/packs.py` | Loads content packs; safe template evaluator (`[[n]]` placeholders); item selection |
| `…/tutorlib/model.py` | Learner state as a fold over events: Elo θ, FSRS cards (py-fsrs), traits, `knobs()` |
| `…/tutorlib/policy.py` | Session planning per mode, teaching-method choice, exam dates, review priority |
| `…/tutorlib/session.py` | `Tutor`: start/next/answer/hint/end/blurt/paper; saves state and the live Obsidian view |
| `…/tutorlib/lesson.py` | Lesson mode state machine: goal → probe → plan → per-idea phases |
| `…/tutorlib/views.py` | Writes `Now.md`, `Lessons/`, `My Notes/` (managed marker blocks around the learner's own text), `Home.md` |
| `…/tutorlib/profile.py`, `insights.py`, `report.py`, `weekly.py`, `blurt.py`, `experiments.py`, `anki.py`, `lint.py` | Profile, insights (findings, readiness, weak spots, week report), notes, weekly tasks, free-recall scoring, n-of-1 experiments, Anki export, Obsidian lint |
| `…/tutorlib/store.py`, `deps.py` | Vault discovery, monthly JSONL event log, flock lock, atomic writes; vendored pure-Python wheels |
| `app/tutor_app/` | `app.py`, `screens.py`, `panels.py`, `cards.py`, `ai.py` (persistent `claude -p` stream), `prompts.py`, `texmath.py` (LaTeX → Unicode, textbook spacing), `look.py` (Night/Day/Classic palettes and themes), `termprofile.py` + `setup_look.py` (`tutor look`: Terminal profiles, font, backup, undo), `mac.py`, `config.py`; `fonts/` holds the bundled JuliaMono |
| `build/` | Content pipeline (`publish.py`, `finalize.py`, `validate_pack.py`, `teach_cards.py`, `syllabus.py`, `plan.py`, …) |
| `foundry/foundry.py` | Runs the content pipeline per chapter (stages, gates, state files, Codex queue). Report only what could let wrong content reach the learner or lose a chapter's work |
| `build/out/packs/<spec>/<subtopic>.json` | Content packs (24 published; `HOLD.json` lists the ones still being built) |
| `build/out/notes/How It Works.md` | The learner's guide. **Its claims are the spec** for behaviour |
| `tests/`, `tests/app/` | pytest for engine and app (`fake_claude.py` stands in for the Claude CLI; Textual pilot tests) |
| `docs/RESEARCH.md`, `CHANGELOG.md` | What each feature is based on; what 1.1.0 changed |

## Running things safely

```bash
R="/Users/sora/Miscellaneous/02 Education/~~ AI Workflow/stem-tutor"
bash "$R/bugwatch/check.sh"                        # whole suite, writes nothing in the repo
bash "$R/bugwatch/check.sh" tests/test_v110.py -q  # part of it
bash "$R/bugwatch/sandbox.sh"                      # scratch vault in /tmp/stem-tutor-bugwatch (prints env exports)
```

After `sandbox.sh`, set the exports it prints, then for example:

```bash
"$R/.venv/bin/python" "$R/plugin/stem-tutor/skills/tutor/scripts/tutor.py" session start --mode lesson --kcs 9702-2.1
"$R/.venv/bin/python" "$R/plugin/stem-tutor/skills/tutor/scripts/tutor.py" next
```

To drive the Textual app headlessly, copy the pilot pattern from `tests/app/test_tui.py` into a script under
`/tmp/bugwatch-scratch/` (`TutorApp(vault, claude_binary=".../tests/app/fake_claude.py", open_obsidian=False)`;
`async with app.run_test(size=(120, 40)) as pilot:`).

Learner data lives in `<vault>/.tutor/` (events, state, packs) and is a **fold over the event log**: `Tutor.rebuild()`
must reproduce the live state.

## Invariants worth attacking

1. Live state after any sequence of actions equals `rebuild()` from the events (and survives a JSON save/load round trip).
2. No answer key, option letter or explanation appears in `Now.md`, `Lessons/`, `My Notes/` or anything the app shows before the question is answered.
3. Every Obsidian file the engine writes passes `tutorlib.lint` and keeps the learner's own text (outside the `<!-- stem-tutor:… -->` markers, and inside "In your words").
4. Nothing is written outside the vault; nothing is deleted anywhere in it (the engine must work where deleting is forbidden).
5. A session saved mid-question resumes exactly (same open questions, same block cursor, same worked-example step).
6. Marking: a right value with a missing unit, or rounded to figures the question does not accept, loses the mark everywhere consistently (an exact value typed shorter than asked keeps it unless the question fixes the figures: `grade._figures_count`); hints and "don't know" never count as success.
7. The guide (`How It Works.md`) doesn't promise behaviour the code lacks.

## Where bugs are most likely

- State that goes through JSON: tuples become lists, integer dict keys become strings, missing keys in state saved by an older version (`model_version` refold).
- Time: `Asia/Hong_Kong` versus UTC date boundaries, `when.date()`, exam-date lookups, streaks across midnight.
- The lesson state machine: phases inserted at the cursor (`fix`, `stuck`, `check`), `awaiting`, blocks that produce no items, `exit`/`practice` after nothing was taught.
- Answer parsing: commas, minus signs, brackets, unicode, empty strings, huge/tiny numbers, percentages, units with prefixes.
- The Textual layer: focus (which widget owns a key), priority bindings versus `Input`, panels replaced while a worker is running, two workers at once, window resize.
- `views.py` marker regexes with odd characters in titles or the learner's text; concurrent writes from the app and Obsidian.
- The AI client against the **real** Claude CLI protocol (see below).
- New since the last hunt (1.1.3 to 1.2.2, `git log v1.1.2..HEAD -- app plugin`): Today's plan and the Almanac on the home screen (`mac.almanac_changed`, `report.today_note`), `tutorlib/insights.py` with the Profile, Mistakes and Weekly notes in `report.py`, session mode `weak`, shown answers (`session._display_answer`, `_in_full`), the AI leak guard (`ai.leaks`), `Tutor.refresh_content`, the iPad inbox when macOS blocks it.
- One question at a time (1.2.3): the app runs the engine with `one_at_a_time=True`, so the rest of a batch waits in `session["queue"]` and is not open (no clock, no help rules, not in Now, the lesson log or the AI context) until `next()` shows it. The chat interface still opens whole batches. Crash recovery (`Tutor._recover`, `state["last_event"]`) is new too.

## Known and by design (do not report)

- Chapters listed in `build/out/packs/HOLD.json` are still in the foundry and deliberately not published. "No questions built" for other subtopics is expected.
- Real AI calls cannot be exercised from the spotter's sandbox (no network). Review `ai.py` against the protocol by reading and mark such findings `Method: read`.
- 14 older chapters have no teaching cards (`pack["teach"]`), so their lessons use the generic fallback card; the learner knows.
- `plugin/stem-tutor/` skills, commands and agents are the old Cowork interface. Report only if they break the engine the app uses.
- Retention targets use estimated exam dates when the planner has none (AS 15 May 2027, A2 15 May 2028) on purpose.
- Only one app instance can run at once (flock); the iPad inbox is imported only at start-up; "extra" past-paper questions have no written explanation.
- Sessions with zero answers or `abandoned` don't count towards the streak; `Review` with nothing due refuses to start.
- Pyright "import could not be resolved" warnings are environment noise.
- Items already listed as deferred in `STATUS.md` (Cowork-only audit findings).

## Unverified assumptions (highest value to check by reading the docs or the CLI's `--help`)

1. The real `claude -p --input-format stream-json --output-format stream-json --include-partial-messages` event shapes: `stream_event` / `content_block_delta` / `text_delta`, the `result` event's `is_error`, `usage` keys, and `--json-schema` returning `structured_output`.
2. `obsidian://open?vault=<folder name>&file=<note>` opens the right note without stealing focus (`open -g`) on macOS.
3. py-fsrs usage across versions (`Scheduler`, `Card.from_dict`, `get_card_retrievability`, `Rating`); the retention argument name; the vendored wheel versions.
4. Textual 8.x behaviour on macOS Terminal.app (256 colours): priority bindings while an `Input` is focused, `OptionList` key handling, `TextArea` ctrl+s.
5. flock on the temp-dir lock file when two different vault paths hash to the same key, or the temp dir is cleaned mid-run.
