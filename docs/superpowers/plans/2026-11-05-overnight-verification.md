# Overnight verification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Tasks execute serially for shared product files, with independent reviews.

**Goal:** Implement the user's lightweight MCQ/LQ verification and resume all-course question imports to a 10% weekly reserve.

**Architecture:** Keep deterministic source replay and immutable source-practice publication. Add strict source-bound model check packets/receipts and native prepared whole-question dispatch. Existing AI clients provide on-demand feedback and bounded checks.

**Tech Stack:** Python, PyMuPDF, existing CodexAI client, AssetLibrary, Textual.

**Spec:** docs/superpowers/specs/2026-11-05-overnight-verification-design.md

## Global Constraints

- Current dirty checkout, no commits/push/cleanup; preserve exact entry versions.
- All reusable data through Library; tests disposable; production learner data read-only during tests.
- No new mastery certification or fabricated official answers; preserve all source guards/quarantines.
- Existing reset consumed; no reset/purchase; weekly stop floor 10%.
- One writer per shared product file and one serialized publisher; disjoint implementations may overlap with explicit ownership; independent content/review evidence.

## Review Focus

- A model guessing the supplied answer repeatedly must not approve a mismatch.
- Missing diagram context, missing parts, wrong receipt digest or hallucinated chapter IDs fail closed.
- Correct-answer feedback must remain concise, without silently changing marks or triggering a model automatically.
- Native packages must retain full question/scheme blocks and private guidance; source or raster tampering must fail.
- Same canonical question must be reused, not duplicated; existing guard holds remain binding.

### Task 1: Bounded checks and on-demand feedback

Files: new `extraction/lightweight_verification.py`; tests `tests/test_lightweight_verification.py`; narrow edits `app/tutor_app/source_practice_screen.py`, with `tests/test_source_practice_app.py` coverage. Existing client seams may be reused without global changes.

- [ ] Freeze entry files and write failing tests for bound packets, blind MCQ checks, maximum three attempts, mismatch/uncertain escalation, strict LQ part alignment and proposal-only mappings.
- [ ] Implement small pure packet/planning/receipt functions; store actual model evidence outside Library until admitted. No provider invocation on module import or ordinary question display.
- [ ] Improve existing explicit AI prompt to distinguish concise correct-answer explanation and incorrect-answer repair, preserving original images/private gating and saved work.
- [ ] Run focused tests, then independent Spec and Standards reviews. Fix scoped findings and pin final files.

### Task 2: Whole native written source-practice import

Files: new `extraction/native_written_practice.py`; narrow dispatch in `extraction/source_practice.py`; narrow proved native-proof fixes in `extraction/prepared_scope.py` and `src/tutorlib/prepared_evidence.py:_whole_total`; tests `tests/test_source_practice_native_written.py` using existing real whole-question fixtures from Library and focused native-proof regression tests.

- [ ] Write failing tests for replayed whole packages, real FP/math examples, altered answers/geometry/images, privacy, dedupe and original bank/history preservation.
- [ ] Implement verifier accepting `pearson_native_prepared_v1` COMPLETE packages via existing `prepared_scope.verify_native_package`; do not bypass its source/part/total/continuation validation. Use descriptor graph hash as binding only, never KC approval.
- [ ] Reproduce and narrowly fix real May/June QP series, shifted native MS header columns, and literal `Total N` question maxima. Positive cover/header/total evidence remains mandatory. Existing October2020/MS mismatch and shared-page boundaries remain held. Preserve unaffected existing package descriptors.
- [ ] Return the existing source-practice result contract, with `_pixels`, media proofs, sources, canonical IDs, held exceptions and no mastery. Retain complete private guidance and source text; require whole assessment mode.
- [ ] Run focused regressions and independent Spec/Standards plus integrated risk review. Pin source before production use.

### Task 3: Resume queues, actual checks and publication

Worker files live in `Work/Workers/extraction/overnight-20261105-10pct/`; fresh preparations/candidates in their authorized Work shelves.

- [ ] Capture exact baseline catalog, source-practice release, bank pointers, history and guard-state hashes; persist new floor and reset lock.
- [ ] Reconcile original pairs and existing packages. Generate whole-question requests from observed native page layouts and source maxima; reuse already completed scopes. Record every unsupported item/file, no filename-only pairing.
- [ ] Run actual Luna semantic checks in bounded source packets, escalate uncertain outcomes; verify actual receipts and retain source evidence. Do not pretend checked sources or model receipts exist.
- [ ] Publish independently cleared items serially, verify actual runtime discoverability and public/private media. Deduplicate canonical IDs; keep unknown source occurrences separate and flagged.
- [ ] Continue other source families with complete evidence; new adapter work requires the same tests/review gates. Read fresh allowance before dispatch and each batch.
- [ ] Audit preserved old resources/history and actual course deltas; save exact checkpoint at 10% or complete. Compile improvement ideas and render/verify the requested System Design report.

## Execution rulings

The objective provides implementation delegation and a detailed strategy, so proceed without an overnight design interview. Existing authorization covers the dirty checkout and immutable tutor publication after gates. Do not narrow the goal to the two adapters above: they open the next ready queues; source coverage and all remaining families stay in the durable ledger until genuinely complete.
