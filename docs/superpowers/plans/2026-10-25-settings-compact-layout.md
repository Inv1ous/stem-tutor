# Compact Settings Layout Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development for the scoped implementation and review.

**Goal:** Widen Settings and reduce repeated grey preset/help text after completing the formatting workflow.

**Architecture:** Retain the existing modal, task selectors, preset preview/Apply/Save flow and design tokens.
Increase only Settings' preferred width, show a pending preset preview when needed, and collapse the long model
guide by default. This is the bounded visual adjustment requested by the user, not a settings redesign.

**Tech Stack:** Existing Textual CSS, Select, Static, Collapsible and Textual pilot tests. No new dependencies.

**Spec:** User request: make Settings wider and compact the grey text below presets, after current work.

## Global constraints

- Preferred Settings width 112 columns, max-width 95%; other modals retain width 90.
- Preserve palette, keyboard access, narrow layouts, docked Save, all task choices, preview semantics and SSD hotplug.
- Preserve all completed formatting and preload changes in the dirty checkout. Do not modify real learner settings.

## Review focus

- Save stays visible at 80×24 and narrower supported sizes.
- Previewing a preset cannot apply it or alter live/saved settings.
- Applying a preset hides redundant preview only after all task rows agree.
- SSD removal keeps reconnection information visible and never clears saved model selections.
- Expanding help cannot obscure Save or introduce unreadable text colours.

### Task 1: Scoped implementation

**Files:** `app/tutor_app/app.py` Settings CSS; `screens.py` SettingsScreen only;
`tests/app/test_settings_compact.py`.

- [x] Capture existing Settings at 80×24, 100×30 and 140×46 in Night, Day and Classic.
- [x] Add failing tests for increased width, collapsed guide, conditional preview and unchanged Apply/Save/Cancel.
- [x] Implement the width, guide disclosure and preview visibility with existing controls and tokens.
- [x] Run new tests and preset/local-settings/visual regressions; compare the captured layouts.
- [x] Independent review, fix confirmed issues, then run the full test suite and whitespace/compile checks.

## Ledger

- The user explicitly requested this small visual improvement after the active formatting workflow.
- Formatting completed first: full suite 3,652 passed; final additional formatter/math edge cases passed focused checks.
- Existing design and control behaviour are the visual target. Exact width and disclosure layout are routine builder choices.
- No downloads, real AI calls, commits or pushes are required.

## Completion evidence

- Before/after captures cover all nine combinations of Night/Day/Classic and 80×24, 100×30, 140×46.
- Modal widths are 76, 95 and 112 columns at those terminal widths; Save stays visible.
- TDD: 11 expected failures and 3 preservation passes before implementation; final Settings/preset/local-settings/visual gate
  passed **85 tests** in 44.45 seconds.
- Independent review found no P1/P2 issues. Additional checks passed at 60×24 in every theme, 80×20 and 100×24.
- Final complete suite including all formatting, cache, provider, preload and Settings changes: **3,671 passed**,
  28 pre-existing warnings, in 138.98 seconds.
- Compile and whitespace checks passed. No real learner settings, model files, dependencies, commits or pushes changed.
