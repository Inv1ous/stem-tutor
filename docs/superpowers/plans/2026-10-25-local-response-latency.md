# Local response latency implementation

Spec: `docs/superpowers/specs/2026-10-25-local-response-latency.md`.
Base: `475fd15d090a443c7d3c5339cc13893a0639bc54`.

Work in the current checkout and preserve unrelated learner content. The user's request authorizes the local-only
implementation; no commit, push, model installation, or service-wide tuning is needed.

## Task 1: Composer preparation

- [x] Add and run failing Pilot tests: local Ask starts loading during typing; submit retains preparation; Esc cancels;
  Claude/ChatGPT and AI-off never instantiate a local client.
- [x] Update `AskScreen` using existing preparation and cancellation ownership.
- [x] Run routing and image UI gates.

## Task 2: Independent preparation

- [x] Add and run failing event-controlled tests for native OCR/load and web/load overlap, generative-helper ordering,
  cancellation cleanup, reset rejection, deadline handling, and no extra warm for ordinary text requests.
- [x] Reuse local preparation with bounded task ownership. Preserve all cloud branches and request payload controls.
- [x] Run local vision, web, reuse, runtime, and provider gates.

## Task 3: Latency evidence and review

- [x] Add regression tests for queue-inclusive structured and cached reply timing; fix only local performance reporting.
- [x] Record primary-source findings and bounded preload measurements, including their limitations.
- [x] Review the scoped working diff independently for standards and spec. Fix material findings with regression tests.
- [x] Run the complete suite and inspect the final scoped diff. Document outcomes and remaining limits.

## Review focus

Cancellation must join speculative tasks; OCR failure must not leak warm work; a GPU image helper must not race
the tutor model; reset must prevent stale preparation from starting a fresh request; cloud paths must remain lazy;
timings must measure real wait without adding concurrent preparation twice.

## Review and validation evidence

- Baseline routing/vision/web/reuse: 41 passed.
- Composer TDD first exposed six missing-start cases, then four missing-cancellation/ownership cases. Final composer,
  routing and image UI gate: 37 passed. Six screenshots cover Night/Day/Classic at 80×24 and 120×40; typed input,
  focus and composer bounds were inspected.
- Latency TDD: five expected failures before implementation; later a search-duration regression failed separately
  and passed after excluding load wait. Runtime/image/progress/Codex regression gate: 113 passed.
- Standards review: no actionable findings. Spec review: two material findings, reproduced with new failing tests:
  cached image answers loaded an unnecessary runner; busy inference suppressed background model preparation.
  The fix starts overlap only on an OCR cache miss and retains a queued background fallback when overlap did not start.
- Final deadline audit reproduced a load budget that excluded an earlier image-observation queue wait. A failing
  regression now verifies the remaining budget reaches the preload transport. Final local lifecycle/runtime gate:
  132 passed.
- The first parallel full run found two outdated search-only transport doubles in `test_provider_extensions.py`:
  they required a third argument and did not represent the shared empty-preload route. The doubles now accept the
  production default path and assert empty messages for preload; search privacy and reset assertions are retained.
- The unconfigured bare pytest command cannot collect existing duplicate test basenames. Validation uses the README's
  importlib/PYTHONPATH configuration. A sequential full run was interrupted after 299 passing tests to apply review
  fixes; final validation runs the whole suite with the already installed pytest-xdist and four isolated workers.
- Final command: `PYTHONPATH=tests/app .venv/bin/python -m pytest tests --import-mode=importlib -n 4 --dist=loadscope -q`.
  Result: **3,394 passed, 28 warnings in 132.95 seconds**. Warnings are the existing SWIG deprecations (repeated per
  worker) and existing invalid escape sequences in the binomial generator test fixture. Provider/latency focused
  gate: 21 passed. Compilation and `git diff --check` pass. Claude/Codex client files, Settings, model metadata and
  presets have no diff from the task base. No unresolved review findings, model downloads, commits or pushes.
