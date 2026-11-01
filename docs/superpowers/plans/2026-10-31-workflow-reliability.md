# Workflow Reliability Implementation Plan

> **For agentic workers:** Use subagent-driven development for independent shared guards and card contracts; root integrates and verifies.

**Goal:** Stop repeated paid failures and make malformed course inputs actionable.

**Architecture:** Shared pure launch/collection guard in tutor_workers; retain existing workflow state machines and strict gates.

**Tech Stack:** Python, JSON, pytest, fake subprocess workers.

**Spec:** docs/superpowers/specs/2026-10-31-workflow-reliability-design.md

## Global Constraints

Library resources immutable; no learner state writes during tests. 70% launch cap, 25% Codex reserve. No course-budget reset or publication.

## Review Focus

- Failed/timed-out jobs through direct launches must stop after two failures.
- Changed model output must not erase failure counts.
- Missing/invalid JSON and collection exceptions must leave inspectable finished jobs.
- Malformed cards/inventories must report gate errors, not crash.
- Baseline preflight must not block pending written review or visual work that authors can still complete.

- [x] Reproduce failures with disposable regression tests and snapshot exact source state.
- [x] Implement shared launch counters and baseline preflight; integrate Foundry/Refine/extraction.
- [x] Harden shared card validation and worker instructions.
- [x] Make collection/launch errors durable, pause without discarding work, document reset and doctor commands.
- [x] Run focused then core checks, read-only course audit, independent standards/spec review.
