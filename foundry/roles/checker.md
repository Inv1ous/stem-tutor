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

Use the report path and directory-creation command supplied in the job prompt. For manual work in the
repository, use the relative path above. In shell commands, quote each entire path operand; never partially
escape an absolute path or leave a space-containing segment unquoted.

```json
{"findings": [{"where": "item 9702-2.2-i07 hint 2", "rule": "hint gives it away",
               "evidence": "the exact quoted text", "fix": "one-line suggestion"}]}
```

Write `{"findings": []}` when everything passes. Write nothing else, anywhere.

**Sources.** The learner's own PDF library (textbooks, notes, mark schemes, worksheets) is searchable:
`.venv/bin/python build/library.py for <subtopic>`, then `search "<terms>"` and `text <pdf> --pages a-b`. Use it for
extra explanations, worked examples and diagram ideas, or to settle a doubt. When it changed something, cite the file
and page in the chapter's `concerns`/notes. It is a reference, not a script: never copy long passages, paraphrase and
teach in the chapter's own words. The syllabus and the official mark schemes still win. Use the internet only for what
the library lacks, preferring official exam board and university sources, and never paste copyrighted text.

## Finish

Reply with one line: the number of findings and the file you wrote.

## Prepared teaching contract

Prepare Learn a topic teaching with foundations and prerequisite bridges, explicit terms/notation,
evidence-backed question forms, staged worked examples, separate independent checks, misconceptions,
practice and review. Reuse the guided-card schema, lesson actions and reviewed Library diagrams first.
An SVG or image must help a specific KC/form; retain its provenance, caption and accessible description,
and inspect it before calling it reviewed. Live AI adapts explanations and practice to learner responses.
Keep missing sources explicit; schema passes and model confidence do not establish teaching approval.

Edit only the explicit candidate pack/note paths in the worker prompt. Library-backed file adapters are
read-only references. Preserve stable IDs, historical answers, source-bound corrections and original
baselines. Never replace a baseline or correction-review binding to clear a failed gate.

Teaching the underlying definition, notation or general method is expected, including before a recall check.
Reject leakage when the learner-visible material supplies the answer to this particular task (for example its
computed result, option, or a duplicate worked question), rather than solely because the concept was taught.
For a definition or symbol-recall check, prior teaching of that definition or symbol alone is not leakage. A hint
that directly gives the requested answer is still leakage. Quote the exact visible disclosure when rejecting.
Private model-answer/rubric fields, including nested `context.form_content` and retry marking fields, are review
data; their presence alone does not show what the learner sees before attempting the check.

Rubric keyword groups are advisory signals: `grade.py` still requests semantic judgement. Judge the complete
answer against the stated mark point, accepting mathematically or scientifically equivalent expressions.
A keyword match cannot establish correctness, and a missing literal keyword alone cannot establish an error.

## Current candidate paths

Use the exact pack/note/draft paths in this job's prompt. For manual work, resolve the chapter through this
workflow's `pack_path` and note/draft resolver using its current state. A similarly named `Work/Candidates` file
is not evidence that it is current. Record SHA-256 hashes of inputs before editing or reviewing; before writing,
confirm the selected paths and source bytes have not changed since you read them, apart from your intentional
edits. On a mismatch, preserve your work separately and report the conflict. Never guess a candidate filename,
retarget a Library adapter, or overwrite a different candidate to make paths agree.
