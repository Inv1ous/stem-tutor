# Responsive Tutoring Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development or superpowers:executing-plans. Follow each task's red/green verification before integration.

**Goal:** Fix reasoning-only local completions, show honest progress, add subscription-backed ChatGPT choices, and reduce avoidable waiting.

**Architecture:** Keep Claude as the original implementation. TutorAI routes lazily to independent local and Codex clients. Local runtime owns context/recovery/progress; small separate modules own exact structured-result reuse and targeted source retrieval. Existing cards render progress without changing answer guards or note writes.

**Tech Stack:** Python 3.13, asyncio, stdlib HTTP, installed Ollama/Codex CLIs, Textual/Rich, pytest.

**Spec:** docs/superpowers/specs/2026-10-25-responsive-tutoring.md

## Global constraints

- Preserve Claude inference, default model/thinking behavior, speech, conversations and usage accounting.
- No new dependencies, weight downloads, precision/sampling changes, production output caps, or API-billing fallback.
- Preserve unrelated learner content and working-tree changes. No commit or push requested.
- Test with synthetic content and fake cloud CLIs; use only a bounded synthetic live request when needed to verify the saved subscription integration.

## Review focus

- Reasoning exhausts context before answer; no private reasoning is shown or saved as an answer.
- Cancel/reset while requests are queued, preparing, reasoning, searching or shutting down.
- Exact cache isolation across schemas, models, thinking, speech and resets; failed/partial calls never reused.
- Mixed Claude/local/ChatGPT choices, missing tools, expired login and cloud limits remain distinct.
- No lesson context enters web queries; unavailable/stale sources never become fabricated fresh facts.

## Tasks

- [x] Runtime: reproduce Gemma failure with a synthetic long context; write failing context/recovery/progress tests; implement per-model answer headroom, bounded recovery and progress; run all local runtime tests and real synthetic smoke tests on all three models.
- [x] UI: capture existing slow-response state; write failing delayed-response tests; use one terminal-only progress helper for streams and structured calls; verify narrow windows and existing answer guards.
- [x] ChatGPT: verify installed CLI protocol and official documentation; write fake-process tests; implement isolated subscription-authenticated CodexAI and known model metadata; integrate lazy routing and existing settings.
- [x] Local reuse and web: write failing cache, reset, web-decision, source-isolation and timeout tests; implement bounded exact structured-result reuse and targeted Ollama search; connect only local request paths.
- [x] Integration: verify mixed providers, release ownership and settings persistence. Document Ollama background operation, reasoning controls and web behavior.
- [x] Review: run independent standards and specification reviews against baseline f18f781, resolve findings, then run the project test command and visual checks.

## Verification evidence

- Full project command: `PYTHONPATH=tests/app .venv/bin/python -m pytest tests --import-mode=importlib -q --tb=short`.
  Result: **3,254 passed**, 13 existing dependency/content warnings, 462.30 seconds.
- Focused new-provider/progress/runtime/settings/reuse/web integration passed 104 tests before the final narrow
  profile and queued-timeout corrections; affected gates and the final full suite cover those corrections.
- Eighteen offline Codex protocol tests pass. One bounded live GPT-6-Luna structured arithmetic request passed
  through the existing subscription sign-in in 4.955 seconds; no API-key credentials were supplied.
- Real local answers returned on all three installed models. The reproduced Gemma thinking case returned an
  answer after the context correction. Exact Gemma structured-result reuse measured 1.318405 seconds initially
  and 0.000108 seconds on repeat, with correct matching data.
- All three models also returned answers with thinking enabled. The final Qwen 27B arithmetic check returned
  the correct answer in 41.308 seconds, including 24.228 seconds loading and 12.648 seconds processing its prompt.
- Real signed-in Ollama search returned three sources through the final local client transport.
- Independent standards/security and specification reviews pass after fixes for provider routing, queue resets,
  web-query privacy, stale lookup completion and progress timestamps.
- Rendered visual checks covered three palettes, 80x24 and 120x40, including Settings, answer-only status and all
  local model progress phases. Existing answer guards and terminal-only status isolation remain covered.
- Source compilation and staged diff checks pass. The learner guide was synced only after an exact baseline match.
- Only task files are staged. No commit, tag or push was requested or performed for this follow-up.
