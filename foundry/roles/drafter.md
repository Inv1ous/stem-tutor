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
5. Run both gates and fix everything they report, until both are clean:
   - `.venv/bin/python build/validate_pack.py <pack path> build/out/specs/<spec>/graph.json`
   - `.venv/bin/python plugin/stem-tutor/skills/tutor/scripts/tutor.py lint "build/out/notes/<note path>"`

## Rules

- Write only these files: the pack JSON, the lesson note, `build/work/gen/<subtopic>*`, and figures under
  `build/out/Assets/`. Never edit code, other chapters, `foundry/` or anything else. Never run git commands.
- Verify arithmetic with `.venv/bin/python` (sympy is installed) as you go, not in your head.
- Past MCQs keep their original wording, options and letters; never present a past question as generated.
- Work economically: write each file once, then make small targeted edits. Aim for at most 40 tool calls.

## Finish

Reply with the JSON report the output schema asks for. List in `concerns` anything a checker should look at
(a figure you could not draw, a syllabus point with thin coverage, an answer you were unsure of).
