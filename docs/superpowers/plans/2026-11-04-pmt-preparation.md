# PMT preparation and extraction continuation implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Work task by task; keep changes uncommitted as the handoff requires.

**Goal:** Prepare the newly registered PMT topicals with preserved source images, explicit exceptions, and private schemes, while resuming supported existing question publication.
**Architecture:** Add a PMT adapter at the existing detector seam. Reuse analyse_source/prepare/verify_bundle rather than a separate rendering stack. Manager review and publication remain the approval path.
**Tech Stack:** Existing Python/PyMuPDF/Pillow/AssetLibrary; no new dependencies.
**Spec:** User request dated 2026-11-04 plus Work/Workers/extraction/handoffs/2026-11-02-resume-prompt.txt and resume-pmt-20261104/pmt-recon.json. This document records the scoped implementation design.

## Global Constraints

User delegated design decisions and authorized necessary extractor fixes; no approval pause. Use current dirty checkout and preserve unrelated work. No commits, pushes, destructive cleanup, guard resets, extra earned reset or purchases. Source bytes and prior IDs/reviews/history are preservation boundaries. All reusable test inputs resolve via tests/library_assets.py into disposable vaults. No tests write production learner state. New source preparation is not content approval or publication. Unknown official identities stay null. All PMT proposals remain unreviewed. Weekly floor20%; reduce launches around24%; fresh limits before paid dispatch. Coordinator alone changes dispatch state and publishes.

## Approaches and decision

Chosen: PMT detector adapter behind the existing preparation interface, because source roles and numbering differ but rendering/integrity requirements already exist. Rejected: repeat full AI transcription of all PDFs (cost and repeats); generic number matching (answer/report leaks); replacing all source material with native-paper downloads (discards topical organization). User explicitly delegated this choice.

## Review Focus

Notes/examples are not public questions. Repeated scheme/report numbers are not new questions. Formula pages and raster pages do not become guessed continuations. Unknown original-paper identity is never fabricated. Mixed question/scheme pages must be quarantined rather than exposing answers.

### Task 1: PMT detector and preparation integration

**Files:** Create extraction/topical_pmt.py and tests/test_topical_pmt.py. Modify extraction/topical_fastpath.py and extraction/topical_fastpath.md only as needed.
**Interface:** find_anchors(doc, course: str, source_path: str | None = None) -> dict matching the current detector schema (anchors, page_roles, issues, profile, segmentation_status). Existing analyse_source/prepare/verify_bundle interfaces stay compatible.

- [ ] Read current detectors, verifier and library test helper; inspect registered PMT originals from the recon file at the relevant layout pages.
- [ ] Add meaningful failing tests for PMT plain S3, Set1 and Set2 plus the five Review Focus cases. Include real registered inputs through the helper; synthetic malformed inputs remain disposable. Test requested-course rejection and source-role routing. Record RED command/output.
- [ ] Implement PMT source recognition using registered PMT path/provenance plus content evidence. Support all12math module IDs (P1-P4,FP1-FP3,M1,D1,S1-S3) in preparation; preserve SME/CAIE behavior. Route Notes before anchors and answer companions privately. Detect Set1 question-to-scheme-to-report transitions from actual rubric/reset evidence; Edexcel Internal Review footer alone is not a scheme marker. Set2 retains original question starts/continued context and stops at formula sheets. Plain S3 preserves question regions and explicit raster exceptions. Compilation numbers never become official identities. Provisional status only; no invented count proof.
- [ ] Where a page mixes questions and scheme/report evidence, quarantine the entire page as private/review and report the ambiguity. Do not guess a public cutoff that could leak answers. Missing-text and unanchored pages must stop continuations.
- [ ] Run focused PMT plus existing topical/native regression tests; record exact evidence. Run bounded all234source analysis and representative full preparation through the interface; all pages accounted, artifacts outside vault. Reuse existing recon and do not rerun model extraction.
- [ ] Document commands, limitations, exact counts and file hashes. Write implementer report; keep all changes uncommitted. Coordinator dispatches separate Spec and Standards reviews before batch preparation.

### Task 2: Source preparation and gated continuation

After Task1 gates pass, prepare supported PMT sources into fresh Work/Preparation output using immutable bundle hashes; reuse completed outputs. Preserve failures in a source-hash-keyed exception queue. Coordinator runs existing-manager jobs only on missing stages, then independent content review before registration/publication and learner-route proof. Do not force PMT sources into unsupported official-identity formats. Review the S3 pilot feasibility against existing identity/import support before extending admission.

### Task 3: Checkpoint and report

Persist per-course preparation/review/registration/publication counts with distinct denominators, exact hashes and exceptions. Reuse existing Markdown RESULTS evidence surface for this continuation; avoid report-runtime work displacing extraction. Verify preservation of prior catalog entries and historical learner bytes. Completion requires usable verified outputs and no required remaining work; budget stopping is a resumable checkpoint, not completion.
