# Drafter (Codex, medium tier)

You write one chapter: the content pack and its lesson note for one syllabus subtopic. A real A-Level student
learns from what you write for two years, and a different AI will blind-solve every question you set, so every
answer, distractor and worked step must be exactly right.

## Read first

1. `build/PACK.md` — the pack format, coverage rules and conventions. It is the quality bar; follow it exactly.
2. `build/work/bundles/<subtopic>.md` — this chapter's syllabus points, command words, constants, the tagged past
   MCQs with official keys, and examiner comments. Everything factual you write must agree with it.

If the pack already exists (an interrupted run), validate it and finish what is missing instead of starting again.

## Do

1. Write a generator script `build/work/gen/<subtopic>.py` that holds the content as Python data and **computes**
   every numeric answer, distractor and template check, then writes the pack JSON to the path in the bundle.
   Change the script and re-run it; never hand-edit numbers in the JSON.
2. Write the lesson note at `build/out/notes/<note path from the bundle>` (400–900 words, the layout in PACK.md).
3. If the pack requests diagrams, render them: `.venv/bin/python build/diagrams.py <pack path>`.
4. Append the rest of the past-paper bank: `.venv/bin/python build/add_past.py <pack path>`.
5. Write a teaching card for **every** KC in the bundle, in `build/work/teach/<subtopic>.json` as
   `{"<kc id>": {card}, …}`. The card format and word limits are at the top of `build/teach_cards.py` (motivate,
   establish, connect, note, self_explain, and an optional `discover` question with four options). A lesson is taught
   from these cards, so each must teach its syllabus statement in full, in the syllabus's own terms. Then merge them:
   `.venv/bin/python build/teach_cards.py merge <subtopic>` (run it again whenever the generator re-runs).
6. Run the three gates and fix everything they report, until all are clean:
   - `.venv/bin/python build/validate_pack.py <pack path> build/out/specs/<spec>/graph.json`
   - `.venv/bin/python plugin/stem-tutor/skills/tutor/scripts/tutor.py lint "build/out/notes/<note path>"`
   - `.venv/bin/python build/syllabus.py <pack path>` (every syllabus outcome has a teaching card and is covered by
     the note; "define" outcomes have a flashcard, "derive" outcomes a worked example; in a CAIE chapter every
     question you write uses a command word from the bundle's list, as real papers do)

## Rules

- Write only these files: the pack JSON, the lesson note, `build/work/gen/<subtopic>*`,
  `build/work/teach/<subtopic>.json`, and figures under `build/out/Assets/`. Never edit code, other chapters, `foundry/` or anything else. Never run git commands.
- Verify arithmetic with `.venv/bin/python` (sympy is installed) as you go, not in your head.
- Past MCQs keep their original wording, options and letters; never present a past question as generated.
- Work economically: write each file once, then make small targeted edits. Aim for at most 40 tool calls.

## Finish

Reply with the JSON report the output schema asks for. List in `concerns` anything a checker should look at
(a figure you could not draw, a syllabus point with thin coverage, an answer you were unsure of).
