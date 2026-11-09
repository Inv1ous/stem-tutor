# Custom topical set implementation plan

> **For agentic workers:** Execute inline using superpowers:executing-plans, then parallel Standards/Spec review.

**Goal:** Select several topics, types and a question count for a random topical past-paper set.

**Architecture:** `tutorlib.topical_selection` owns categories, eligible pools and bounded sampling. `Tutor.start` stores count/types and an identity/chapter queue; a native setup modal uses the same inventory. Existing PickerScreen gains Topical multi-select.

**Tech stack:** Python, Textual, pytest, existing reviewed-bank and Library helpers.

**Spec:** `docs/superpowers/specs/2026-11-02-topical-set-design.md`

## Global constraints

Preserve reviewed eligibility, canonical identities, grading, historical bytes and existing unrelated changes. No Library writes, generation, commits or staging. Count whole bank items, not marks. Count range 1–200; default 10. Categories must not invent pure-calculation labels for mixed structured questions.

## Review focus

Duplicate paper identities across chapters; unavailable/excluded planned questions after resume; empty filters falling back to everything; editing shortcuts consumed by topic selection; nested modal cancellation losing draft choices.

## Task 1: Engine set selection

Files: new `src/tutorlib/topical_selection.py`, edit `src/tutorlib/session.py`, new `tests/test_topical_selection.py`.

- [x] Write failing tests for category mapping, eligible inventory, canonical deduplication and seeded balanced sampling.
- [x] Implement `category(item)`, `validate_types(types)`, `pools(packs, state, chapters, types, used=(), disclosed=())`, `sample(groups, count, rng)` and inventory counts without mutating resources.
- [x] Add read-only `Tutor.topical_choices(focus, question_types=None)` and keyword options `topical_count=None`, `topical_types=None` to `Tutor.start`.
- [x] Write failing integration tests for exact count independent of marks, types, resume, shortages, revalidation/exclusions and validation without writes.
- [x] Persist the bounded identity/chapter queue and serve through existing protected question paths. Keep unconfigured legacy topical sessions unchanged.
- [x] Run new engine tests and existing topical guards.

## Task 2: Native topic and set setup

Files: edit `app/tutor_app/screens.py`, `app/tutor_app/app.py`; new `tests/app/test_topical_setup.py`; update the existing topical home-route test for the intentional extra setup step.

- [x] Write failing tests for Topical multi-select, cross-folder/search persistence and native input editing.
- [x] Reuse Test prep multi-select, with context-sensitive shortcuts so topical count/search editing remains native.
- [x] Add `TopicalSetupScreen(focus)` returning `focus`, `topical_count`, `topical_types` on Start, with inventory, validation and Change topics. Reuse current modal styling and dock controls for small windows.
- [x] Pass new options only for topical SessionScreen startup; report planned counts clearly in the introduction.
- [x] Test keyboard Save/Cancel and topic changes, invalid inputs/empty types, actual resulting session, no provider requests, resize and three themes.
- [x] Inspect native captures, run focused regressions, complete parallel review, resolve demonstrated findings and update release logs/bugwatch/evidence. Leave changes uncommitted.
