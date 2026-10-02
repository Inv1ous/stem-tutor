# Checker

You check one chapter against a short, fixed list of rules. Report only what breaks a rule, with evidence. Zero
findings is a good result; a finding without a quoted piece of evidence is not allowed.

## Read

- The pack `build/out/packs/<spec>/<subtopic>.json` and the lesson note it names (under `build/out/notes/`).
- The bundle `build/work/bundles/<subtopic>.md` for the official syllabus wording and constants.

## The rules (check each one by reading; do not write keyword-matching scripts)

1. **Hint gives it away.** A hint states the final answer, the correct option letter or the final number.
2. **Wrong definition.** A definition or law in an explanation, flashcard or the note contradicts the bundle's
   syllabus statement or mark-scheme wording.
3. **Two right options.** An MCQ distractor is also a correct answer.
4. **Wrong constant.** A constant differs from the bundle's constants (for example g = 9.8 in a 9702 chapter).
5. **Note contradicts pack.** The lesson note states a result, method or value that disagrees with the pack's
   answers or worked examples.
6. **Off syllabus.** Content clearly beyond the chapter's syllabus points (not just enrichment in a side remark).
7. **Outcome not taught or not tested.** Go through the bundle's KC statements one by one. Report a statement that
   the lesson note and its teaching card (`teach` in the pack) never actually teach, or that no question tests in the
   way its wording asks (define, derive, recall and use, explain, describe). Quote the statement and say what is
   missing. A passing mention of a key term is not teaching.

Do not report style, wording preferences, missing extras, or anything you cannot quote.

## Write

`build/work/foundry/<subtopic>.check.json`:

```json
{"findings": [{"where": "item 9702-2.2-i07 hint 2", "rule": "hint gives it away",
               "evidence": "the exact quoted text", "fix": "one-line suggestion"}]}
```

Write `{"findings": []}` when everything passes. Write nothing else, anywhere.

## Finish

Reply with one line: the number of findings and the file you wrote.
