# Marking strictness implementation plan

> **For agentic workers:** Execute inline using superpowers:executing-plans. Review the final scoped diff on Standards and Spec in parallel.

**Goal:** Offer saved Auto/Lenient/Balanced/Strict marking for every AI examiner path.

**Architecture:** A small `marking_policy.py` owns options, help and deterministic Auto resolution. Existing prompt builders consume the saved selection and study mode; the existing provider and scoring paths remain intact.

**Tech stack:** Python, Textual, pytest, existing provider fakes.

**Spec:** `docs/superpowers/specs/2026-11-02-marking-strictness-design.md`

## Global constraints

Preserve learner history, deterministic grading, rubric identities, manual fallback and confirmation. No Library writes, live inference, commits or staging. Reuse the current checkout and compare against the task's before snapshot.

## Review focus

Unknown settings, presets overwriting strictness, answer paragraph loss, Challenge re-mark omission, invalid rubric identity acceptance.

## Task 1: Shared policy and Settings

Files: create `app/tutor_app/marking_policy.py`; edit `config.py` and `screens.py`; test `tests/app/test_marking_strictness.py`.

- [x] Write failing tests for default/validation/roundtrip and Auto mode resolution.
- [x] Implement the four policy values and `resolve(level: str, mode: str = '') -> str`; default invalid values to Auto.
- [x] Add the saved `Settings.marking_strictness` string and validate it on load.
- [x] Write failing native Settings tests for selection, help, Save/Cancel and preset independence.
- [x] Add a compact selector and live help using existing Settings layout.
- [x] Verify the settings/policy tests.

## Task 2: Marking requests and regression proof

Files: edit `prompts.py`, `screens.py`, `challenge_screen.py`; extend the new tests.

- [x] Write failing tests for `judge(..., strictness='auto', mode='')` and `remark(..., strictness='auto', mode='')`; assert equivalent wording, full-answer evidence and unchanged rubric payloads.
- [x] Add shared policy instructions without duplicating scoring or rewriting student content.
- [x] Pass the saved selection and actual mode in short/long/session/Challenge requests.
- [x] Exercise all four request paths with fakes, including the pasted ice answer, missing-comparison negative control and invalid rubric fallback.
- [x] Check actual provider routing and local reply cache isolation after a policy change.
- [x] Run focused regression gates; inspect native Settings captures at small widths and all themes.
- [x] Complete parallel Standards/Spec review against the task snapshot; fix demonstrated issues and verify again if needed.
- [x] Update Unreleased logs, ownership documentation, bugwatch QoL entry/activity and evidence. Leave changes uncommitted.
