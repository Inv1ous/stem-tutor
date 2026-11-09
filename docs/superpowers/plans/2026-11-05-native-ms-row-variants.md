# Native marking row variants Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Independent gates precede production use.

**Goal:** Reuse complete native written proofs for repeated per-part question-number rows and positively located whole-question totals, preserving mechanics cover assumptions.

**Architecture:** Normalize only consecutive same-number native MS table rows into one complete whole-question start. Keep the original source words, parts, notes, alternatives and every distinct question boundary. Add one truthful total-label spelling under the existing authenticated right Marks-column restrictions. No source identity or grade-approval relaxation.

**Tech Stack:** Existing Python/PyMuPDF original-source proof and neutral total parser.

**Spec:** Parent overnight design; all fourteen-course extraction and10% reserve remain the actual goal.

## Global Constraints

- No commits/push, production/test-vault writes, old Library/guard/history changes, or invented source identity.
- MS-only row grouping. A repeated number after another distinct question remains ambiguous and held.
- Shared-page different questions remain held; do not admit neighbouring private answers.
- Bare total requires exact whole `N marks` right-column line, unique total, after authenticated Marks header and before Notes; independent QP total must agree.
- A unique final bare integer cell may qualify only with authenticated Marks-column/whole-row context and independently agreeing MS part-allocation or scoring-code arithmetic. An explicit unambiguous equal-mark OR suffix may be accounted once; all original alternatives remain visible. Bare digits alone or mere equality to QP are insufficient.
- Existing accepted descriptors byte-identical. Preserve source issues, cover/paper-log witness and whole scope proof.
- D1 QP has separate question/answer-booklet repeated numbers; that is a different unresolved format. Do not deduplicate its QP anchors.

## Review Focus

- A numerical result inside an answer/diagram is not a new whole-question boundary.
- Grouped rows must retain ALL same-question subparts and later notes; a reset after another Q cannot be merged.
- Part allocations, prose such as `award 10 marks`, Notes and competing maxima cannot become a whole total.
- Every accepted new row still has complete public/private original media and no mastery approval.
- Frozen old whole packages and all guards remain unchanged.

### Task1: One source-format extension

Files: `extraction/prepared_scope.py`, only `_whole_total` in `src/tutorlib/prepared_evidence.py`, new `tests/test_native_ms_row_variants.py`; M1-only context in `extraction/native_written_practice.py` and focused adapter tests.

- [ ] Freeze current approved4ebdcd80 source and neutral parser; test actual registered M1 originals through disposable Library fixtures. Read R/native-written-probe.json actual M1 starts/holds first.
- [ ] RED repeated `1(a)(i)` / `1(a)(ii)` rows currently count as duplicate starts; bare `N marks` maximum currently missing. Counterexamples cover nonconsecutive repeated whole numbers, shared pages, unlabelled formula digits and false totals in Notes/prose.
- [ ] Group consecutive same-number MS starts while retaining source word/part inventory. Require positive table-column evidence and do not globally deduplicate/reset question IDs. Derive the same complete private page scope through next distinct whole question.
- [ ] Accept a unique bare whole total only under positive column/row/Notes bounds. Keep literal label in witness. Extend source witness and neutral label parser coherently; don't synthesize parentheses.
- [ ] Keep authenticated bare integer labels truthful and require independent right-column scoring support; ambiguous alternatives stay held.
- [ ] Include the fresh original QP cover as public context for new M1 native questions, preserving actual g/precision instructions. Extra context pixels belong in the verifier result, not a mutation of a COMPLETE package. Other courses and prior rows stay unchanged. Worker resolver materializes only authenticated fresh pixels in disposable/unpublished output.
- [ ] GREEN source-level prepare/replay/private media and negative tests plus affected existing source/witness tests and three old byte fingerprints. No broad repeated suite.
- [ ] Freeze exact diff/pins/report. Independent Spec/Standards and bounded risk gate before root operations.

Task2 root resumes only newly qualified missing stages and existing exact packages; source issues, semantic receipts, dedupe and quota remain binding.
