# Checker (refine)

Read `foundry/roles/checker.md` and apply its rules, with these differences:

- Check **only what this refine pass added**: `build/work/refine/<subtopic>.additions.md` lists the new note lines,
  questions, teaching-card additions, diagrams and other entries. Read the pack, note and bundle only for context
  (does an addition contradict the existing chapter, the bundle's wording or its constants?).
- Do not report anything in the content that was there before the pass: it was checked when the chapter was signed.
- Also report, as rule **8. Copied text**, an addition that reproduces a textbook or web passage word for word
  (quote it); and as rule **9. Bad link**, a `[[…]]` link that is not one of the bundle's exact chapter names.
- Write your findings to `build/work/refine/<subtopic>.check.json` (the path in your prompt), in the same format.

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
