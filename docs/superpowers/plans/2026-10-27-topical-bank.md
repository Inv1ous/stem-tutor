# Topical Bank Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Publish a verified first topical batch with chapter-specific support and eligibility checks before 80% weekly usage is used.

**Architecture:** A versioned local bank overlays existing Packs. Source canonical IDs resolve against chapter item aliases. A pure prerequisite policy controls support and chapter exclusions, while the existing event store persists starts/exclusions and existing question controls expose eligibility checks.

**Tech Stack:** Python, pytest, PyMuPDF, Textual, existing tutorlib event store; no provider calls required for import.

**Spec:** `docs/superpowers/specs/2026-10-27-topical-bank-design.md`

## Global Constraints

- Read only the two requested source collections and official syllabuses; reuse existing bank metadata.
- Stop expansion near 80% weekly used; leave time for verification/publication.
- No Git operations that write; preserve all existing uncommitted work and learner progress.
- Store copied question content/images locally, excluded from Git. Publish only the topical bank and its assets.
- No-bank behaviour and all saved provider settings remain unchanged.
- Bank format: `bank.json` contains `format_version: 1`, `syllabus_versions`, `items`; items use existing pack item fields, plus `topical: {reviewed: true, requires: [subtopic IDs], support: {subtopic ID: supporting fact}, chapters: [serving subtopic IDs], revision: string}`. `source.qid` is the canonical paper ID. Images use `Assets/topicals/...`.

## Review Focus

- Duplicate source questions retain original IDs/freshness and do not inflate coverage.
- Missing prerequisites cannot leak support into unassisted checks or another chapter.
- Unknown source keys/mappings and incomplete multi-page content cannot become playable.
- Eligibility skips create no wrong answer, marks, mastery or hidden answer disclosure.
- Interrupted publishing never exposes a partial version; bank corruption degrades safely.

### Task 1: Bank runtime and eligibility

**Files:** new `tutorlib/topicals.py`; modify `packs.py`, `session.py`, `model.py`, `views.py`, `app/tutor_app/screens.py`; tests `tests/test_topicals.py`, `tests/app/test_topical_questions.py`.
**Interfaces:** Load `<vault>/.tutor/topicals/CURRENT` version's `bank.json`. Overlay canonical aliases onto existing items. Provide deterministic metadata-only eligibility and support functions; Tutor exposes `check_solvable(n)` and chapter exclusion listing/restoration. SessionScreen exposes a visible question action and shortcut.

- [x] Write failing behavioural tests for load/no-bank, aliases, requirements, support changes, no-hints, per-chapter exclusion/replay, multi-page rendering and corrupt-bank handling.
- [x] Observe RED, implement minimal runtime and existing-style UI, observe focused GREEN.
- [x] Preserve assessed KCs, count support as assistance, keep open instances unchanged on bank refresh.

### Task 2: Reproducible import and local publication

**Files:** new `build/topicals.py`; tests `tests/test_topical_import.py`; `.gitignore` local copied content path.
**Interfaces:** Produce bank format above; accept only source paths inside the two collections; canonical ref extraction and official-key matching; atomic `publish(bank_dir, vault)`.

- [x] Write failing tests for canonical references, exact keys/conflicts, valid AS mappings, deduplication, source crop boundaries and failed publication pointer preservation.
- [x] Observe RED, implement extraction/crops/validated manifest and atomic publication, observe GREEN.
- [x] Build first batch from high-confidence exact existing mappings; then expand reviewed new chapter mappings/keys and structured items within budget.
- [x] Keep provenance hashes/page/box, pending reasons and denominator records; never count raw inventory as ready.

### Task 3: Review, publish, and report

**Files:** `docs/TOPICAL_IMPORT_PROGRESS.md`; review reports; isolated UI captures.

- [x] Run focused tests, full suite, Standards and Spec review of only this task's diff; fix concrete defects.
- [x] Inspect actual terminal/Obsidian output in an isolated vault.
- [x] Publish only the verified topical bank locally, verify loaded counts/assets and preservation of learner state/provider settings.
- [x] Report unique ready/new/already available/pending by subject and honest coverage denominator, plus stop usage.

### Bounded integration addendum: independent topical practice

- [x] Add `topical` practice mode and Home entry using the existing picker and question controls. Include bank-only subtopics without fabricating lesson packs; keep the lesson picker unchanged.
- [x] Prove MCQ/structured source-only selection, no repetition, exclusions and unknown prerequisites in an isolated vault; review this isolated extension.

Reason: the live vault has fewer published lessons than the build tree. A separate bank should make reviewed questions available independently of lesson publication. Only locally reviewed bank entries are eligible.
