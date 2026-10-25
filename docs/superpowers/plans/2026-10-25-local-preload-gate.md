# Local preload gate implementation

Spec: `docs/superpowers/specs/2026-10-25-local-preload-gate.md`.
Preserve the prior latency changes and unrelated learner work in this checkout. Do not commit or push.

- [x] Write and observe failing wire-level tests for preload-before-generation across all model IDs and routes.
- [x] Extract a raising, lock-free preload helper; call it under the inference lock before each generation attempt.
  Recheck reset/drive/deadline state after acknowledgment. Preserve request payload quality controls.
- [x] Adapt transport doubles to explicitly represent empty load acknowledgments while retaining generation checks.
- [x] Prepare marking for written questions early and show local loading status/request-time preload duration.
- [x] Test failure, cancellation, reset, recovery context, single-queue ordering and zero-runtime cached answers.
- [x] Review the scoped change, run the complete suite, and document precise limits and verification results.

## Evidence

- Initial readiness wire suite: 40 expected failures before the gate, then 40 passes. Extended cases include invalid
  acknowledgments, cancellation, SSD removal and exact preload/generation ordering for concurrent tasks.
- Runtime test migration retains generation assertions and explicitly models load acknowledgments; dedicated
  readiness tests use their own HTTP server so auto-acknowledgment cannot mask a missing gate.
- Proactive lifecycle TDD: six expected failures; later loading-state and preload-statistics failures; final focused
  lifecycle/image/composer/progress/routing gate: 57 passed.
- Standards review found no material issues. Runtime review reproduced a reset race while opening the generating
  connection after preload. New reset/SSD/deadline boundary tests all failed before the send guard. Transport now
  validates its captured epoch, model availability and remaining deadline after connection, immediately before write.
- The first full run passed 3,448 tests before adding the three boundary regressions. Final validation repeats the
  whole suite after that guard. Live probing was skipped because GPT-OSS was resident; no real inference or unload
  was performed, and no warm-round-trip speed claim is made.
- Final focused readiness/runtime/latency/lifecycle gate: **144 passed**. Final complete command:
  `PYTHONPATH=tests/app .venv/bin/python -m pytest tests --import-mode=importlib -n 4 --dist=loadscope -q`.
  Result: **3,451 passed, 28 existing warnings in 135.92 seconds**. Compilation and diff whitespace checks pass.
  Claude/Codex clients, Settings, model metadata and presets are unchanged. No unresolved material review findings,
  model downloads, shared-service changes, commits or pushes.
