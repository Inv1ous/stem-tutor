# Personal Learning Tutor Implementation Plan

> **For agentic workers:** Use the existing-flow implementation and independent review described below. Preserve the active Refine run.

**Goal:** Make Learn a topic visibly guide the learner through prepared explanations, useful diagrams and contextual tutor follow-ups.

**Architecture:** Extend current lesson activities and the existing Learning tutor. Keep asset rendering in a narrow app module; retain Library reads and answer guards. Prepare Chemistry 1.4 in an isolated authoring directory.

**Tech Stack:** Python, Textual, Rich, CairoSVG, Pillow, Library asset APIs.

**Spec:** `docs/superpowers/specs/2026-10-30-personal-learning-tutor-design.md`.

## Constraints and review focus

Do not mutate active workflow state/candidates, restart workers, change publication/provider settings, or rewrite historical learning data. Test in disposable vaults. Keep previews bounded and accessible. Test guarded images, unsupported images, resumed phases, small terminals and delayed AI replies. No automatic paid calls for routine lesson progression.

## Tasks

- [x] Capture the existing Chemistry lesson in a scratch vault and record visible gaps.
- [x] Add failing tests for visible Learning tutor controls, card-bound diagrams and protected answers.
- [x] Implement minimal contextual controls and verified visual presentation. Run focused regressions.
- [x] Stop the diagnostic Chemistry pilot after user clarification; leave it unpublished. No course content activation is wanted.
- [x] Capture and inspect the revised screens at small and regular terminal sizes.
- [x] Review task changes on standards and specification axes; repair findings.
- [x] Verify that all course publication pointers and diagnostic draft status remain unchanged; install no course release.
- [x] Report the learner-visible changes, verification and restart/new-lesson requirements honestly.
