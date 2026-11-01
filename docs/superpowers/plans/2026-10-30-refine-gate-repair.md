# Refine Gate Repair Implementation Plan

> **For agentic workers:** Use the existing Refine lifecycle and independent review; never weaken content gates.

**Goal:** Complete the handoff's review pipeline and prevent stale evidence, draft isolation and recurring gate failures.

**Architecture:** Keep the existing solve/recheck stages, add strict written-batch evidence, and create per-pass Work teaching drafts. Existing callbacks remain compatible; legacy proof must be regenerated.

**Tech Stack:** Python, JSON, existing worker lifecycle and Library APIs, pytest fake workers.

**Spec:** `docs/superpowers/specs/2026-10-30-refine-gate-repair-design.md`.

- [x] Read the handoff, save exact starting sources and hold launch shells while active workers finish.
- [x] Reproduce stale evidence and missing teaching drafts with failing isolated regressions.
- [x] Wire blind solve, independent review, evidence hashes, recovery and strict sign gates.
- [x] Isolate teaching drafts from current packs; preserve source copies and correction archives.
- [x] Update role instructions, report schemas, canonical media guidance and provider documentation.
- [x] Run focused and core tests, resolve failures, and independently review standards/spec.
- [x] Confirm worker/candidate preservation and resume the exact held coordinators under existing limits.
- [x] Update handoff and report actual outcomes, remaining content reviews and publication state.
