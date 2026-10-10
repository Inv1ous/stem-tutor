# Build status

## v2.1.5 (2026-10-10) — done
- The foundry hands each drafter the exact note names to link and the diagrams its chapter should have, and its gates fail a made-up link or a missing diagram.

## v2.1.4 (2026-10-10) — done
- Obsidian links find their chapter when the title was reworded (same number, a shared word); the drafter is told to draw diagrams again.

## v2.1.3 (2026-10-10) — done
- Obsidian: lesson tags `9701`/`9702` (digits only, invalid) are `cie-9701`/`cie-9702`; a link to a note that does not exist is plain text.

## v2.1.2 (2026-10-10) — done
- The foundry's Codex tiers were measured against Claude's on 60 blind questions; solving and checking now start on `gpt-6-sol` low (Haiku's match).

## v2.1.1 (2026-10-10) — done
- The foundry counts Codex's five-hour window (when its plan reports one) and pauses Codex until a limit it hits reopens.

## v2.1.0 (2026-10-09) — done
- Challenge mode: hard AI-written calculation questions (MCQ and typed) at ten difficulty levels, set up by words or
  menu, written by Sonnet or Opus, each checked for being solvable from the chosen chapters and the ones before.
  1927 tests.

## v2.0.0 (2026-10-08) — done
- A cleaner window and a hardening pass: the Night, Day and Classic looks with JuliaMono and `tutor look` (backup and
  undo), maths shown as printed, grading and recovery fixes, a safer publish, calmer screens, repaired published
  packs. 1,517 tests. Checked in the container only: how it draws in the learner's macOS Terminal (`tutor look`
  prints a test page to judge by eye).

## v1.6.1 (2026-10-07) — done
- Solo bug-and-comfort pass (four hunters, four fixers): grading reads more right answers, the maths shows properly,
  small windows fit, Almanac sync respects your edits, notes read better. 775 tests.

## v1.6.0 (2026-10-04) — done
- Every typed answer uses the box that wraps and grows; a quantity in another prefix, spelling or with words after
  the unit is the same answer; an answer marked wrong can be re-marked by the AI examiner and then counts as right
  everywhere; feedback buttons wrap in a narrow window. 682 tests.

## v1.5.1 (2026-10-04) — done
- The session bar wraps whole onto a second line in a narrow window; only the week's limit is shown beside the
  tokens. 676 tests.

## v1.5.0 (2026-10-04) — done
- A question folds the terminal's log (ctrl+l brings it back after the answer), a multi-line box for answers and
  questions, the AI tutor is told the step on screen and the last questions marked, and what is left of the Claude
  limits is shown beside the tokens. 675 tests.

## v1.4.0 (2026-10-03) — done
- The tutor fills in the Almanac (ticks earned, a colour for every topic, wall, error families, retrospective, mark
  bank, paper stage) through a file the planner page reads by itself; exam dates come back with the export; no cap on
  AI replies. Merge rules run in Node in the tests; not yet seen running in the learner's browser. 671 tests.

## v1.3.1 (2026-10-02) — done
- The foundry no longer mistakes "Claude's five-hour window is unknown" for "there is none": it says when it does not
  know, takes the figure passed on from the Claude app (`foundry reading`), and closes Claude until the reset when a
  job is refused; a job goes only where it fits. 662 tests.

## v1.3.0 (2026-10-02) — done
- The foundry runs on both allowances: every role is a headless Claude or Codex worker, each job goes to the allowance
  with more left (read before every job), the family that drafts never checks, and each role starts on its cheapest
  model. `foundry step`, `foundry usage`. First real run signed 9701-2.2 and 9701-2.4 (24 chapters, 111 of 873
  outcomes). 658 tests.

## v1.2.8 (2026-10-02) — done
- Almanac ticks count (read from the planner's export, found in Downloads): ticked objectives are checked instead of
  taught, the plan and the home screen follow the learner past the calendar week, and the foundry builds the chapters
  in front of them first. Checked on a scratch copy of the published content. 646 tests.

## v1.2.7 (2026-10-02) — done
- A resize clears the leftovers Terminal showed beside its scrollbar (the learner's original layout report); the
  launcher opens in the learner's "Study" Terminal profile. Both checked in Terminal itself. 631 tests.

## v1.2.6 (2026-10-02) — done
- The terminal window is named STEM Tutor while the app runs. 629 tests.

## v1.2.5 (2026-10-01) — done
- Layout at half-screen width (learner-reported): button ids no longer take layout styles, the log and the answer
  area share one grid with the scrollbar on the edge, the home side box scrolls. 628 tests.

## v1.2.4 (2026-10-01) — done
- Numeric marking: an exact answer typed with fewer figures keeps the mark (exceptions: the question fixes the
  figures; too many figures in the sciences); a rounded answer must be the rounding itself (no window just above a
  power of ten); a rounded whole number can be typed with zeros (2400 for 2375). 624 tests.

## v1.2.3 (2026-10-01) — done
- Bug hunt 2 with Codex (B-035 to B-039, all fixed) plus two bugs from the learner's lesson: the app now opens one
  question at a time (asking the AI about a marked answer was refused while the unseen next question was open), and a
  lost mark says why in Now, the lesson log and the AI's context. 572 tests.

## v1.2.2 (2026-10-01) — done
- v1.2.2: syllabus gate + `foundry coverage` + teaching cards in the foundry; `/foundry` runs the manager on Sonnet
  (medium) with an Opus adjudicator on call. 18 chapters signed; 14 lack teaching cards (left for the learner to
  decide); 217 chapters to build. Spec: `docs/superpowers/specs/2026-10-01-sonnet-foundry-syllabus-design.md`.
- v1.2.1: shown answers keep their s.f. and exact answers are in full; the AI leak guard works at any precision.
- Learner insights (`tutorlib/insights.py`, menu "What the tutor knows about you", Profile.md), AI summary on request,
  Fix my weak spots (session mode `weak`), exam readiness, mistake journal, week in review; full feature list in the
  guide. Design and plan: `docs/superpowers/specs/2026-09-30-learner-insights-design.md`,
  `docs/superpowers/plans/2026-10-01-learner-insights.md`.

## v1.1.5 (2026-09-30) — done
- v1.1.3: a chapter signed in the foundry is published to the vault, committed and announced at once; the app loads
  new chapters when you are back at its menu.
- v1.1.4: the app starts even when macOS stops Terminal reading iCloud Drive (iPad inbox); it says how to allow
  access, and `tutor doctor` reports it.
- v1.1.5: the app plans the day from the Almanac (Today's plan, this week's objectives on the home screen, `Today.md`
  at start, a notice when `A-Levels.html` changed). Content gap: 43 subtopics for weeks 1–7 are not built yet.

## v1.1.2 (2026-09-30) — done
- Bug hunt (`bugwatch/`): 34 Codex findings fixed with tests (v1.1.1), then a Haiku review pass; see `bugwatch/FIXES.md`.
- Content: 23 repeated past-paper questions removed; `validate_pack.py` rejects repeats. Vault `Assets/mcq` duplicates
  ("… 2.png", 2,094 files) moved to the Bin.
- **Content foundry** (`foundry/README.md`): Codex (draft/tiebreak/fix, headless via the ChatGPT app's Codex CLI) +
  Haiku (blind solve/check) + Opus (manager). The six held chapters are on the board; S1-1 is at `check`.
Next: run the foundry — finish the six held chapters, then batch 1 (74 bundles ready, weeks 1–10). Codex allowance
resets 22:00 on 2026-09-30 (first live Codex job still to run).

## Bug watch (run 2026-09-30: 34 findings, all fixed)
`bugwatch/` = live two-agent bug hunt: Codex (spotter, writes only `bugwatch/codex/BUGS.md`) and Claude (fixer, writes
`bugwatch/FIXES.md`). Start with `bugwatch/README.md`; board: `.venv/bin/python bugwatch/bugs.py --watch`;
tests without side effects: `bash bugwatch/check.sh`; scratch vault: `bash bugwatch/sandbox.sh`.
Claude session start line: "Read bugwatch/README.md and bugwatch/SCOPE.md, then run the bug-fix loop."

## v1.1.0 (2026-09-30) — done
Algorithms (4-grade FSRS, exam-aware retention, risk-ordered interleaved reviews, successive relearning, slip damping,
fatigue vs expectation, blurting), profile module + plain-English Profile.md, reflection prompt, keys that work while
typing, audit fixes (engine + app), performance (cached schedulers, no menu refold, compact state saves), guide rewritten
(How It Works 1.1.0), docs/RESEARCH.md, CHANGELOG.md. 250 tests. Tag v1.1.0.
Next: content only (adjudicate held packs 9701-1.x, P1-2, S1-1; build more packs + teach cards with a lower-tier agent).

## Overnight build (2026-09-29 → 30) — terminal app; plan: ~/.claude/plans/can-you-continue-what-polished-swing.md
- [x] 1 Vault moved to `~~ AI Workflow/STEM Tutor` (local vault, Obsidian config, publish default, iCloud inbox)
- [x] 2 Engine: texmath, views (Now/Lessons/My Notes/Home), lesson flow, teach-card fallback, inbox import (+tests)
- [x] 3 AI client (persistent headless Claude, lean flags) + prompts (+fake-claude tests)
- [x] 4 Textual app (+pilot tests, screenshots)
- [x] 5 Launcher (`bin/tutor`, `Start Tutor.command`) + `doctor`
- [x] 6 Teach cards for the 7 packs (Sonnet) + validate + publish
- [x] 7 How It Works.md, Home.md, README, memory
- [x] 8 Final offline E2E, commit, morning summary

Learner to do once: open `~~ AI Workflow/STEM Tutor` as an Obsidian vault; run `claude auth login` (AI stays off
until then); `bin/tutor doctor` should then be all ✅. Held packs (9701-1.x, P1-2, S1-1) still need adjudication.


## Done
- Engine `plugin/stem-tutor/skills/tutor/scripts/` — 161 pytest tests green; clean-Python run via vendored wheels.
  Live `Question Sheets/Current.md`; Unicode sub/superscripts converted to LaTeX in notes.
- Plugin: tutor + study-arsenal skills, mode references, 7 commands, marker/digest agents, SessionStart hook.
- Sources: 6 specs + 639 past papers/MS/ER (`sources/index.csv`).
- Syllabus graph: 873 KCs across 14 specs (`build/out/specs/*/graph.json`); Year-1 chunks enriched by agents,
  A2 chunks (9701 23–37, 9702 12–25) are heuristic placeholders (`enriched: false`) — enrich before Feb 2027.
- Almanac import `build/out/plan.json`: all 873 KCs scheduled; 22 gap-fills listed in `added_by_tutor`.
  Planner HTML fixed for P3 → June 2027 (backups in `00 Important/01 AS:A/.backup/`).
- MCQ bank: 3360 CAIE Paper 1 MCQs with official keys (`build/work/mcq/`), 2204 figure crops;
  examiner-report comments split per question (`build/work/er/`).
- Build tools: validate_pack.py, bundle.py, diagrams.py (IEC symbols), blind.py, publish.py, tag_mcq.py.
- Vault: `Notes/01 Study/STEM Tutor/` published as pack v1 (graphs + plan + figures, no packs yet).
- Obsidian check (app 1.13.7): inline/display/aligned maths, mhchem `\ce`, callout maths, table maths,
  Mermaid, SVG and PNG embeds all render. Editor font lacks some Unicode subscripts → notes use LaTeX.
- `dist/full-arsenal-cowork.zip`: Cowork full-arsenal that hands study requests to study-arsenal (upload it).

## In flight
- Workflow `tag-caie-mcqs`: tag → audit → fix for 12 chunks; then `python build/tag_mcq.py merge`.
- Workflow `build-content-packs` pilot on P1-1, S1-2 (draft → blind-solve → adjudicate).

## Remote Cowork (verified 2026-09-29)
Cowork sessions run in a cloud container; `device_bash` runs in the Mac's VM with connected folders at
`$HOME/mnt/<folder>/`, and rm/unlink there fail until the learner grants deletion. The engine therefore ships
inside the vault (`.tutor/engine/`, copied by publish.py) and runs as `python3 ~/mnt/*/.tutor/engine/tutor.py`.
It never deletes (flock lock in the temp dir, closed session written as null) and refuses to run on a copy.

## Deferred audit findings (remote Cowork)
- digest agent + after-video transcript fallback cannot see device files: add `diagnose map --file`, stage via device_stage_files.
- /profile reads Profile.md that the container cannot see: add a `profile` engine command.
- mark mode: `inbox` should return absolute device paths for device_stage_files; name uploads <session>-<n>.pdf.
- paper mode: papers.json empty; say so, and stage paper + mark scheme before marking.

## Next
1. Review pilot packs; tune PACK.md; run `build-content-packs` over batch 1 (74 subtopics, weeks 1–10).
2. Anki: mark pack flashcards already in the learner's existing decks (dedupe) before first export.
3. Publish v2 with packs; package `dist/stem-tutor.plugin`; user uploads + Cowork Project setup.
4. E2E in Cowork + Haiku-parity evals.
5. Papers for paper mode (P2 + IAL question→KC maps), A2 enrichment, batch 2+ packs just in time.
