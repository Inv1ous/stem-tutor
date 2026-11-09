# Programmatic Exam Extraction Implementation Plan

> **For agentic workers:** Use the native execution workflow for the adapter and independent assigned workers for the two disjoint release blockers. Keep all changes uncommitted as instructed.

**Goal:** Prepare complete source-bound native MCQ papers without AI transcription or prewritten explanations, while making omissions explicit.

**Architecture:** A read-only AssetLibrary adapter validates an exact native QP/MS pair, extracts numbered image regions and official key evidence, and writes a fresh unpublished preparation bundle. Existing review and publication gates remain authoritative. Small provenance and Q4 fixture corrections close previously reproduced blockers in separate files.

**Tech Stack:** Existing Python environment, PyMuPDF and Pillow; no new service or dependency.

**Spec:** `../../../../workflows/programmatic-exam-extraction.md` from this file's directory.

## Global Constraints

- Preserve source hashes, stable identities, reviewed resources and learner history.
- No credits, resets, global provider changes, production learner writes or bypassed failure guards.
- Outputs belong in Work/Preparation; logs and checkpoints belong in Work/Workers.
- Native 9701/9702 Paper 1 only in this batch; unsupported layouts fail closed.
- Independent Spec and Standards gates precede release claims.

## Review Focus

- Wrong sitting or variant must reject before producing a joined answer.
- Missing anchors, key conflicts and scanned pages must leave explicit exceptions.
- Shared Section B instructions must be preserved and flagged for review.
- Interrupted output and changed image bytes must never be reused as a completed bundle.
- Public review images and learner images must not expose private mark schemes.

### Task 1 Adapter and controlled evaluation

Files: create `extraction/fastpath.py`, `bin/extract-fastpath`, `tests/test_extraction_fastpath.py`.
Interfaces: `analyse_pair(qp: bytes, ms: bytes, paper: str, qp_ref: str, ms_ref: str) -> dict`; `prepare(vault: Path, qp_ref: str, ms_ref: str, output: Path, dpi: int = 144) -> dict`; `verify_bundle(output: Path) -> dict`.

- [ ] Write real Library-backed tests for 40 identities, official letters, complete physical-page accounting, private/public separation and wrong-pair rejection. Run RED.
- [ ] Implement native identity validation, conservative page geometry, official table parsing and exception reporting. Use pixels as the question authority; text is search/debug evidence only.
- [ ] Add fresh-only bundle writes and digest validation; test interruption and tampering.
- [ ] Compare per-region and per-page rendering with identical outputs; time complete preparation on at least two courses and multiple sittings. Keep exact source and environment evidence.

### Task 2 Reproduced release blockers

- [ ] Add direct registration provenance tests, observe the flat P1/P2 failure, apply the questions-only private-media region correction and verify diagrams retain accepted behavior.
- [ ] Reproduce the eight Q4 test failures, install the real seed graph in disposable fixtures and permit only the exact diagnostic history append. Run the full 80-case module.

### Task 3 Independent gates and checkpoint

- [ ] Run fresh separate Spec and Standards read-only reviews on the coherent changed paths. Resolve concrete blocking findings with regression proof.
- [ ] Run relevant extraction/runtime tests and preservation checks. Record scope limits and unresolved work honestly.
- [ ] Save measured results, resumable next actions, budget reading and an architecture document using the supplied System Design template. Stop further optimization search.
