# Scope: what the code is and where bugs likely hide

STEM Tutor is a terminal study app for one A-Level learner (CAIE Physics/Chemistry and Edexcel IAL Maths), in `Asia/Hong_Kong`. The deterministic engine owns lessons, attempts, scoring, schedules and persistence. Prepared guided cards support Learn a topic; optional live AI can select reviewed material, explain, and request teaching actions. Those live actions do not replace grading or content review. Textual presents the app; Obsidian presents saved notes. Use the repository venv.

## Code map (paths from the repo root)

The workspace contract is `../AGENTS.md`. See `app/tutor_app/README.md` for UI ownership.
Use `src/tutorlib/` for engine investigation and `src/tutor_workers/` for shared workflow infrastructure.

## Migration and teaching invariants (check first)

- All reusable resources, including real test inputs, resolve through the learner Library catalog. Tests use `tests/library_assets.py` and disposable copies. A catalogued file adapter is read-only; edits start at a fresh Work preparation path.
- Library resource IDs, digests, provenance, question identities and reviewed correction bindings survive path changes. Directory adapters lead to Work; sources, published packs and learner history are not scratch output.
- Source queries must select the correct course and relevant shared documents, verify hashes, and keep caches outside the Library. A zero-hit search cannot silently prove source coverage.
- Prepared guided cards and live learning actions must protect unanswered checks, skipped answers and independent performance. Recheck session identity and guards after every asynchronous generation step.
- Use SVGs and source figures when they aid understanding. Verify file, provenance, chapter/KC binding and terminal description; never show a protected question's answer as a teaching figure.
- Can I solve this must remain answer-free and available for every question kind/media. Reviewed topical metadata and graph-derived prerequisites have distinct evidence. Unknown metadata remains unverified; checking does not grade or mark assistance.
- Canonical question/part identity shares exposure across chapter aliases. Same-context duplicates must not repeat; distinct parts, conflicting assessment records and deliberate cross-chapter KC assignments must not be discarded by image or stem similarity.
- Foundry has a two-hour course limit; Refine has a one-hour course limit. Physics (9702) and Chemistry (9701) are exempt. A timeout checkpoints pending work and never grants content approval. Existing publication switches remain authoritative.
- PDF extraction must respect its selected provider and question/notes-diagram scope. TQ means topical questions. Incomplete multi-page questions, missing official marking material and uncertain OCR stay pending.
- Scratch setup snapshots CURRENT content and its Library dependencies. Verify every pack/image; `doctor` alone does not prove image completeness. It never republishes unfinished authoring work or edits a registered plan.

High-value regression suites: `tests/test_library*.py`, `tests/test_worker*.py`,
`tests/test_refine*.py`, `tests/test_guided*.py`, `tests/test_topicals.py`,
`tests/test_consolidate_question_media.py`, `tests/test_bugwatch_sandbox.py`,
`tests/test_extraction.py`, and related `tests/app/test_learn*.py`/topical UI tests.

Course approval, structural gate passes, storage availability and code verification are separate claims.

| Path | What it does |
|---|---|
| `plugin/stem-tutor/skills/tutor/scripts/tutor.py` | Engine CLI (`doctor`, `session start/end`, `next`, `answer`, `find`, `week`, `lint`, …) |
| `src/tutorlib/grade.py` | Parses answers (`1B3`, `2 = 4.5 m s-1 ~3`, `3?`), number/unit/s.f. grading, sympy equivalence, rubric matching |
| `src/tutorlib/units.py` | SI unit algebra |
| `src/tutorlib/packs.py` | Loads content packs; safe template evaluator (`[[n]]` placeholders); item selection |
| `src/tutorlib/model.py` | Learner state as a fold over events: Elo θ, FSRS cards (py-fsrs), traits, `knobs()` |
| `src/tutorlib/policy.py` | Session planning per mode, teaching-method choice, exam dates, review priority |
| `src/tutorlib/session.py` | `Tutor`: start/next/answer/hint/end/blurt/paper; saves state and the live Obsidian view |
| `src/tutorlib/lesson.py` | Lesson mode state machine: goal → probe → plan → per-idea phases |
| `src/tutorlib/views.py` | Writes `Now.md`, `Lessons/`, `My Notes/` (managed marker blocks around the learner's own text), `Home.md` |
| `src/tutorlib/profile.py`, `insights.py`, `report.py`, `weekly.py`, `blurt.py`, `experiments.py`, `anki.py`, `lint.py` | Profile, insights (findings, readiness, weak spots, week report), notes, weekly tasks, free-recall scoring, n-of-1 experiments, Anki export, Obsidian lint |
| `src/tutorlib/store.py`, `deps.py` | Vault discovery, monthly JSONL event log, flock lock, atomic writes; vendored pure-Python wheels |
| `app/tutor_app/` | `app.py`, `screens.py`, `panels.py`, `cards.py`, `ai.py` (persistent `claude -p` stream), `prompts.py`, `texmath.py` (LaTeX → Unicode, textbook spacing), `look.py` (Night/Day/Classic palettes and themes), `termprofile.py` + `setup_look.py` (`tutor look`: Terminal profiles, font, backup, undo), `mac.py`, `config.py`; fonts resolve through `Library/Shared/Fonts` |
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
- Legacy chapters may use fallback teaching cards. Missing prepared coverage is a content gap, not proof that a ready card was lost. Check current coverage; do not rely on historical chapter counts.
- `src/tutorlib/` is canonical engine source. The plugin `tutorlib` path is a distribution adapter. Test standalone installed-engine compatibility as well as source imports.
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
