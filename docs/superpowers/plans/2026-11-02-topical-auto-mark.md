# Topical automatic marking implementation plan

> **For agentic workers:** Execute inline, then parallel Standards and Spec review.

**Goal:** Offer session-local automatic topical marking and prove reviewed-bank reuse across relevant modes.

**Architecture:** Existing setup passes a boolean to `Tutor.start`; session state owns it. Existing point judge gains an owned automatic structured path. Codex reuses its image transport; shared bank selection remains canonical.

**Tech stack:** Python, Textual, pytest, fake provider transports.

**Spec:** `docs/superpowers/specs/2026-11-02-topical-auto-mark-design.md`

## Global constraints

No production learner writes, active candidate admission, extraction launches, commits or app-wide setting changes. Default Self-mark; preserve deterministic grading and all protection gates. All source images must reach the selected automatic marker or fallback must be explicit.

## Review focus

Stale/cancelled verdicts, partial image inputs, invalid rubric points, bank-only kind mismatch and session defaults leaking across modes.

- [x] Write RED tests for mode-local setup/persistence, automatic full/partial/zero grades, invalid/failure/manual controls and owned cancellation/stale behaviour.
- [x] Write RED tests for ordered multi-image Codex structured requests and provider isolation.
- [x] Implement setup choice, validated session option, saved-work/ticket-bound automatic structured marking and short-mark routing.
- [x] Extend Codex one-shot image input through the existing transport, with complete-page validation and unsupported-provider fallback.
- [x] Prove shared-bank mode reachability; fix Test/Long bank-only picker visibility with supported-kind controls.
- [x] Write the extraction resume prompt with model roles, stage/coverage reuse and verified publication goals.
- [x] Run focused gates and native layouts; complete Standards/Spec review, fix demonstrated findings, update docs/bugwatch/evidence.
