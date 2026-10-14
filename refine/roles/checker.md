# Checker (refine)

Read `foundry/roles/checker.md` and apply its rules, with these differences:

- Check **only what this refine pass added**: `build/work/refine/<subtopic>.additions.md` lists the new note lines,
  questions, teaching-card additions, diagrams and other entries. Read the pack, note and bundle only for context
  (does an addition contradict the existing chapter, the bundle's wording or its constants?).
- Do not report anything in the content that was there before the pass: it was checked when the chapter was signed.
- Also report, as rule **8. Copied text**, an addition that reproduces a textbook or web passage word for word
  (quote it); and as rule **9. Bad link**, a `[[…]]` link that is not one of the bundle's exact chapter names.
- Write your findings to `build/work/refine/<subtopic>.check.json` (the path in your prompt), in the same format.
