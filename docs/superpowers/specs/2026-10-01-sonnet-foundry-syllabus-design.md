# Foundry on Sonnet with Opus on call, and syllabus compliance (v1.2.2)

Approved by the learner on 2026-10-01 ("build it, but don't reopen chapters yet").

## A. The manager runs on Sonnet at medium effort

- `/foundry` (a user-level skill installed by `foundry install-skill` from `foundry/skill/SKILL.md`) sets
  `model: sonnet` and `effort: medium` for the turn that invokes it and tells the session to follow
  `foundry/roles/manager.md`.
- `manager.md` is written for that manager: the loop in one turn (Haiku batches in the foreground, `foundry wait` for
  Codex), what it may judge itself, and six triggers for calling Opus.
- `foundry escalate <chapter>` prints an Opus adjudicator prompt (`foundry/roles/adjudicator.md`). The adjudicator
  decides every open item of the chapter and records each with `resolve`.

## B. Syllabus compliance and coverage

- `build/syllabus.py check`: a gate before signing. Every outcome of the chapter has a teaching card, is mentioned by
  the lesson note, has a flashcard or Define question if it says "define" and a worked example or Show (that)
  question if it says "derive"; CAIE questions written by the drafter use the syllabus's command words (real papers
  from 2023 to 2025 keep to that list). Calibrated on the 21 existing chapters before it became a gate.
- Teaching cards join the pipeline: the drafter writes `build/work/teach/<chapter>.json`; `collect` merges the
  well-formed ones after any drafter or fixer; their check questions are blind-solved.
- Checker rule 7: an outcome that is mentioned but not really taught, or not tested as its wording asks.
- `foundry coverage`: per syllabus, outcomes in signed chapters, in progress and not started; signed chapters that do
  not pass the gate; chapters to build next in Almanac order (`--queue N`); and `build/syllabus.py audit`, which
  compares every graph with the outcomes extracted from the syllabus documents.

## Found while building

- 14 chapters (69 outcomes) have no teaching cards, including all Codex drafts: the drafter was never asked for them.
  Left as they are at the learner's request; `coverage` lists them.
- D1's graph listed three subtopics twice (glossary headings read as sections); fixed in the graph and in
  `graph.skeleton_unit`.
- 9701-2.4.1 had lost the syllabus's note on significant figures; restored, and the chapter re-bundled.
- The 2028 to 2030 CAIE syllabuses state "no significant changes which affect teaching"; their PDFs use a layout
  the extractor does not read, so the audit uses the 2025 to 2027 extraction.
- The queue stalled for hours on zombie workers; a finished job no longer counts as running.
