# Course Workflow Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Update existing course workflows and media handling for prepared, visual, adaptive lessons after the Library migration.

**Architecture:** Reuse existing workflow boards, guided cards, Library resolver and review gates. Independent domains have separate file owners and can run concurrently; integrate shared interfaces sequentially. Preserve the dirty checkout using the saved task-start file snapshot.

**Tech Stack:** Existing Python, pytest, Textual, shell entrypoints and Claude manager skills.

**Spec:** `../specs/2026-10-30-workflow-refresh-design.md`.

## Global Constraints

- Foundry: 7,200 seconds per course. Refine: 3,600 seconds per course. 9701/9702 are exempt.
- Preserve learner events, question IDs, aliases, answers, corrections, prior releases and no-loss baselines.
- Real test resources come through tests/library_assets.py into disposable vaults.
- Keep current provider settings and publication switches. Do not launch full-course paid regeneration.
- User opted out of further questions. Resolve routine choices and record them here.
- Finish current task above 25% weekly remaining; reserve repair/review capacity.

## Review Focus

- Library-backed file adapters cannot be edited by a content worker.
- Deadline accounting spans chapters and survives manager restart.
- Unknown or malformed prerequisites do not become a positive readiness claim.
- Image moves preserve all declared aliases and review hashes.
- Delayed AI output must not bypass a changed session or skipped-answer guard.

### Task 1: Foundry/Refine preparation and budgets

Files: `foundry/`, `refine/`, `src/tutor_workers/`, focused tests.

- [x] Add regression tests for course deadlines, reserve, lesson-only scope, age order and immutable authoring inputs; observe expected failures.
- [x] Implement persisted course budgets, clamped worker deadlines, guided contracts, scoped authoring candidates and oldest-first preparation.
- [x] Preserve old states and existing gates; update/reinstall Foundry and Refine manager skills.
- [x] Run affected workflow suites and record evidence.

### Task 2: Sources and extraction

Files: `build/library.py`, new extraction package/entrypoint/skill, source/extraction tests.

- [x] Reproduce canonical-shelf discovery failure and course/hash isolation failures.
- [x] Fix source inventory and Work cache; preserve isolated-fixture overrides.
- [x] Implement provider/scope-pinned resumable extraction with complete provenance, review state and existing source tools.
- [x] Test using disposable source fixtures and a real read-only inventory; install the manager skill.

### Task 3: Runtime learning and eligibility

Files: `src/tutorlib/teach_actions.py`, `topicals.py`, `packs.py`, `session.py`, `app/tutor_app/screens.py`, focused tests.

- [x] Test course/KC-bound SVG reuse, delayed-output guards, ordinary question prerequisites and duplicate candidate selection.
- [x] Implement conservative eligibility and all-kind UI behavior; preserve reviewed topical policy and saved attempts.
- [x] Filter same-context canonical duplicates while retaining all history aliases and cross-chapter use.
- [x] Run guided/topical/runtime and selected UI checks.

### Task 4: Media and Bugwatch

Files: new `build/consolidate_question_media.py`, media tests, `bugwatch/` documentation and sandbox tooling.

- [x] Test collision-safe consolidation, stable IDs, aliases, interrupted migration and rollback in disposable vaults.
- [x] Implement journalled consolidation and runtime-adapted reference audit; run dry plan before the authorized real move.
- [x] Apply and verify actual media consolidation with exact originals in Archive; preserve release and learner event hashes.
- [x] Repair scratch setup and document migrated ownership/invariants; verify scratch publication and doctor.

### Task 5: Integration and independent review

- [x] Compare changed paths against Work/Preparation/workflow-refresh-20261030/baseline; save task-only diff.
- [x] Run selected whole workflow/library/guided/topical suites and meaningful Textual pilots; repair observed failures.
- [x] Run separate Standards and Spec reviewers on the task delta; fix important findings and rerun affected checks.
- [x] Save counts, commands, usage readings and unresolved content limitations in Work/Preparation/workflow-refresh-20261030/REPORT.md.

Ruling: no worktree or commits — the existing checkout contains the migration and unpublished work; HEAD is not a valid implementation baseline. Task-start snapshot is the review fixed point.
Ruling: no approval pause — the user explicitly opted out of questions and delegated recommended choices.

Completion evidence: `../../../..` workspace `Work/Preparation/workflow-refresh-20261030/REPORT.md`. Final frozen core suite: 3,032 passed; focused UI/runtime checks: 192 passed; independent reviews closed.
Ruling: reviewed duplicate source evidence authorizes one exact OCR-equivalent pair through an immutable record/source-hash-bound resource; originals and history remain unchanged.
Ruling: standalone correction gates preserve legacy behavior without a board state; lesson-display context is passed explicitly rather than loaded again.
Ruling: new guided Foundry jobs are gated explicitly; pre-existing states remain compatible. Lesson-only card visuals satisfy display requirements without changing subject-note bytes.
