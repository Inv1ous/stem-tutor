# Topical bank review and verification

27 October 2026. Baseline: `aa558ff21ca1da5a46487a9ce6d0811c6f059d62`. Reviews were limited to this task's runtime/importer/UI paths and its new tests; prior unrelated uncommitted work was excluded.

## Standards

Independent review found incomplete numeric grading-field validation, invalid UTF-8 CURRENT handling, lost imported-ID exposure after later lesson publication, and publisher validation/asset-containment gaps. All were addressed with observed failing regressions and passing scoped checks. A second check caught optional numeric precision/tolerance shapes, including nested structured checks; these were corrected and independently verified with 18 passing regressions.

The source-only practice addendum had one invalid-explicit-focus fallback: an unmatched selection could expand to every chapter. It now preserves the distinction between `None` and explicit empty/unmatched selections. Independent scoped review confirms the finding closed.

## Spec

Independent review found a no-help selection path that could end assessment early despite safe alternatives. The first fix missed previously used alternatives and other allowed response kinds; both were reproduced and corrected. Scoped review confirms that independently solvable previously used questions remain available without assistance.

The source-only topical route exposes reviewed questions from graph-backed chapters without manufacturing teaching packs. Existing lesson availability stays unchanged. Invalid selections fail without creating a session. No outstanding scoped Spec findings remain.

## Content review

The first 1,199 MCQs reuse existing checked mappings and require a matching key independently parsed from the topical answer table. They are not claimed as 1,199 new questions.

Additional original source images were inspected: 34 chemistry MCQs and 276 physics MCQs were accepted. Three chemistry and 17 physics candidates remain pending. The physics holds include two apparent printed key/source conflicts and obsolete or uncertain scope. In particular, the graph in `9702_m17_12_q6` implies zero average velocity while its table gives another option; `9702_s17_13_q17` has a force/work scaling mismatch. The originals and parsed keys remain unchanged; neither was admitted.

Twenty-three structured parts from eleven whole parent questions retain every source page while marking only the named part. Independent scheme review corrected the gallium weighted-isotope calculation to AS objective `9701-22.2.2`, rather than definition objective `9701-2.1.2`, and corrected one A1 label. No further substantive scheme/part/image-completeness failures were identified in that review. Old chemistry Data Booklet references have the needed atomic masses supplied explicitly. New atomic-structure image questions include an upright official periodic-table reference.

## Visual and functional evidence

An isolated vault loaded the actual complete candidate bank and exercised an unbuilt alkenes chapter at 80×24 and an unbuilt mass-spectrometry chapter at 140×46. Both passed. Root inspected native Quick Look PNGs rendered from actual Textual SVG captures; the eligibility control, answer controls and footer fit. The generated Now note includes both complete source pages and clearly says “Answer (b) only”. No live learner notes were used for these tests.

This verifies terminal rendering, generated Obsidian Markdown and original source images. It is not a claim that a new live Obsidian screenshot was taken.

## Test evidence

Core/fix/addendum covering run: 239 passed. Importer final focused run: 9 passed, including fail-closed rotated-page cropping, key conflicts, source references and atomic pointer preservation. Actual candidate visual probe: 2 passed.

The first full run exposed the new footer's width/height regression, corrected with failing-to-passing viewport checks. An existing fake scout collection timed out once under concurrent work; it did not recur in subsequent complete runs. Bare pytest also encounters the repository's existing duplicate test-module names, so verification uses its documented canonical import mode.

Canonical run before the final rotation guard: 4,765 passed, one skipped, 28 existing warnings in 151.39 seconds. The final frozen-code run is recorded in the final progress report once complete. The skip is the existing optional MLX environment test.

## Final frozen-code verification and publication

Canonical command:

```sh
PYTHONPATH=tests/app .venv/bin/python -m pytest tests --import-mode=importlib -n 4 --dist=loadscope -q
```

Final frozen run: **4,766 passed, one skipped, 28 existing warnings in 157.24 seconds**, exit 0 (`/tmp/topical-full-suite-final-frozen.log`). This run includes the dedicated topical route, all review fixes and the rotated-page guard. Whitespace checks pass.

Publication loaded all 1,532 entries across 74 topical chapter selections with no bank errors. All 1,526 assets match their prepared bytes. Protected learner/settings/event hashes were unchanged. The previous engine remains in a recoverable backup; prior content packs were not republished. No model weights, saved provider selections or Git state were changed.
