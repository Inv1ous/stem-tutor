# Examinent compiled MCQ source implementation plan

> For agentic workers: use subagent-driven development for one exact-source adapter with independent Spec and Standards gates.

**Goal:** Verify and publish previously unavailable ordinary MCQs from the registered non-PMT Chemistry topical compilation, using its literal answer appendix.

**Spec:** `workflows/source-verified-practice.md`; evidence `../Work/Workers/extraction/resume-source-practice-20261105-32pct/non-pmt-triage.md` and JSON.

## Global constraints

User already delegated format-adapter implementation and approved source-verified practice without mastery credit. Continue the existing checkout, preserve exact snapshots, no commits/push/cleanup. Stop at 32% weekly remaining; do not begin another format. No paid per-question extraction, solving or explanations.

Exact eligible source: `asset:legacy-94c51c9bcbba526ad8f64b38`, SHA256 `90d2c4a2c144714a1369d6775833e429457600f6b74a069c7daf00777159a70f`, registered Chemistry 9701 Examinent Paper 1 TA, 717 pages. Original question geometry remains the existing `topical_fastpath.analyse_source` responsibility. Only this authenticated source is added; unsupported source families stay unsupported.

The document contains 1,699 ordered question serial numbers and official QIDs with 1,699 matching native appendix rows on pp700–717. Independent PyMuPDF and pypdf extraction must agree on every SN, paper code, original question number and A–D answer. No paper or question identity is inferred from topical position alone. Preserve original question pixels and source-bound key-row geometry.

## Task 1: Exact compiled-key adapter and new-item admission

Files: create `extraction/caie_compiled_profile.py`; narrow dispatch/integration in `extraction/source_practice.py`; new `tests/test_source_practice_compiled.py`. PMT dispatch, existing exact D1, native original-paper profile, publisher, runtime, Bank and learner history remain unchanged.

- [ ] Snapshot exact entry bytes/pins in `.superpowers/sdd/2026-11-05-examinent-source-mcq/`.
- [ ] RED real shared-source fixtures in disposable vaults: independent key disagreement, SN/QID mismatch, missing key, resealed question/media tamper, private appendix never public, key-row crop cannot include the adjacent question's answer, shared response context absent, last-question appendix boundary, and existing verified canonical reuse without changing its original resource.
- [ ] Implement `compile_mcq(raw: bytes, fresh: dict) -> dict` in the new module. Authenticate exact source identity/hash/page count; independently parse full 1,699-row key and match every row against the source's question serial/QID sequence. Return source-bound marking regions, per-occurrence exclusions, and eligible ordinary MCQ items (marks=1, empty KCs, no mastery).
- [ ] Only original exam numbers 1..30 are eligible. The 425 discovered questions numbered31..40 lack authenticated common response context and remain excluded by source occurrence, with official QID and reason recorded. The last question that includes Appendix A p699 remains excluded. Do not synthesize context or silently modify frozen public geometry. Source-specific cover/front-matter pages1,2,4 are explicitly accounted; source question body cannot disappear into an unassigned review page.
- [ ] Full existing frozen source replay and pixel comparison remain active for all preparation media. Every admitted item must have nonempty original public images and its single original answer row, with no adjacent key leakage. Reuse original official canonical IDs, not a newly invented identity.
- [ ] At verification, check the actual immutable selected Collection. If an eligible compiled occurrence has an already source-verified canonical MCQ with the same official letter, retain that existing resource and report a provenance-reuse record instead of submitting different crop evidence for that ID to the publisher. This is not a new question. A conflicting key is a genuine canonical conflict and must stay quarantined. Source-occurrence exclusions (missing common context or appendix contamination) do not invalidate another independently verified native-paper representation; record these in the proof ledger rather than quarantining the unrelated source representation.
- [ ] Root serializes writers: stop/finish native publication before this compiled import, so the verification-time current-release snapshot cannot race a new native representation. No generic publisher semantics or `_canonical_evidence` relaxation is permitted.
- [ ] GREEN new focused source tests plus affected verifier tests. Use shared `tests/library_assets.py`, physical disposable vaults, no production test attempts. Freeze exact diff/pins and report RED/GREEN evidence. Independent Spec/Standards gates and one integrated final gate before publication.

## Review focus

1. Matching a serial number alone cannot authenticate the paper/QID or answer.
2. A two-column key table must not leak the neighboring row/column's answer.
3. Missing common response instructions must not be replaced by model-generated text.
4. Previously verified canonical items must retain their original source/media and counts.
5. Excluded source occurrences must remain visible in provenance without removing a valid independently verified native representation.

These cases belong in the focused RED/GREEN checks. Discovery counts are not upload counts. If the remaining allowance cannot cover the gates, checkpoint candidates without publishing them.
