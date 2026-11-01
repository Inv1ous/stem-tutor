# Structured tutor output Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Consistent readable STEM answers across cloud and local tutor models, verified with real outputs and screenshots.

**Architecture:** A shared bounded document decoder renders semantic blocks to canonical Markdown. Provider adapters
retain their ownership and native schemas; existing terminal maths and Obsidian mirroring consume the rendered text.
Bounded local history and relevant existing study references reduce avoidable instruction and factual-context loss.

**Tech Stack:** Existing Python stdlib, Textual/Rich, MarkdownIt, Ollama and isolated MLX; Claude and Codex subscription CLIs.

**Spec:** `docs/superpowers/specs/2026-10-26-structured-tutor-output-design.md` (user approved).

## Global Constraints

- Preserve provider/model/thinking selections, subscription authentication, local readiness, deadlines and cancellation.
- Claude live tests use Sonnet only. No model training, weight changes, automatic provider fallback or default second-model formatting pass.
- Document bound 4 MiB; at most 256 blocks; per-block bound 256 KiB. Never emit protocol or speech as visual prose.
- Keep learner text, machine grading fields, copied mark points and literal code exact. Preserve mathematical meaning.
- New broad reference lookup skips OPEN questions. Never retrieve hidden answers/solutions or cached AI cards.
- Use existing checkout at `aa558ff21ca1da5a46487a9ce6d0811c6f059d62`; preserve unrelated learner-content changes. No Git writes requested.

## Review Focus

- A paragraph containing inline list syntax must not bypass block layout. Task 1/5 tests cover the supplied screenshot.
- A repeated native Claude candidate must not concatenate into a successful answer. Task 3 covers candidate identity and final agreement.
- Dropped history may remove an image the model previously saw. Task 2 covers reattachment and pair removal.
- A glossary excerpt may reveal an OPEN definition question. Task 4 proves retrieval is skipped without changing context.
- Canonical bytes can agree while Obsidian rendering differs. Task 6 requires actual reading-view screenshots.

## Shared interface

`app/tutor_app/chat_output.py` owns:

- `document_schema(speech: bool = False) -> dict`
- `document_instructions(speech: bool = False) -> str` (includes shallow schema and content rules)
- `DocumentError(ValueError)` with a human-readable failure message.
- `DocumentDecoder(speech: bool = False)`: `feed(chunk: str) -> str` emits only new canonical Markdown from complete
  validated blocks; `finish() -> tuple[str, str]` returns full canonical Markdown and separate speech.
- After successful finish, `.document: dict` is the validated object and `.wire: str` its deterministic JSON.
- Complete-block output and final rendering agree; clients can compare native final objects with `.document`.

Transport mode is additive: `document: bool = False` on `Claude`, `CodexAI` and `LocalAI` constructors. `TutorAI`
enables it for actual tutor conversations; legacy direct client behaviour remains testable. One-shot schemas keep
existing interfaces. Speech rules switch with document mode; no trailing speech marker in structured replies.

### Task 1: Shared semantic decoder and renderer

Files: create `app/tutor_app/chat_output.py`, `tests/app/test_chat_output.py`.

- [x] Write failing split-boundary tests: a paragraph, heading, two bullets, steps with associated equations, literal
  code and separate speech yield exactly one canonical document without keys or JSON punctuation leaking.
- [x] Run focused tests and record the missing-module failure.
- [x] Implement the shared interface, shallow flat schema, strict duplicate/unknown-field checks, bounded incremental
  scanning, arbitrary property order, controls guard and deterministic rendering through existing maths normalisation.
  Preserve code. Keep step numbering through equations and restart after other block kinds.
- [x] Add tests for empty/malformed/incomplete documents, invalid kinds, unknown fields, duplicate keys, Unicode,
  every escape boundary, bounds, nested Markdown/inlined bullets, equations, percentages and literal JSON/source.
- [x] Run focused tests; require all pass. No commit.

### Task 2: Local transport and context budget

Files: modify `local_ai.py`, `local_chat.py`; create `local_context.py`; test local document/context paths.
Consumes Task 1 interface. Produces successful local `Result.text` as canonical Markdown and validated protocol history.

- [x] Write failing native Ollama/MLX wire tests: semantic schema, complete-block emission, separate speech, no raw
  protocol, native effort unchanged, preload per attempt, bad/length-stopped replies do not enter history.
- [x] Run tests to prove failures before implementation.
- [x] Add document constructor mode and shared decoder without changing the event/Harmony/readiness layers. Keep
  legacy reply mode. Store validated document wire in document-mode history only.
- [x] Implement local-only oldest-complete-pair history selection with system/schema/latest request reserved. Preserve
  current question exactly; fail oversized current requests clearly. Reattach a current image after its historical
  turn drops. Bound retained history and reject explicit length stops, including visible-but-incomplete responses.
- [x] Test history bounds/current-request preservation, model/effort/speech isolation, reset, image removal/reattachment,
  oversized input, failed/cancelled history, MLX routing and actual readiness regressions. Record estimate limitations.
- [x] Run focused local and preload tests. No GPU tests while baseline process is live. No commit.

### Task 3: Cloud adapters and shared writing policy

Files: modify `ai.py`, `codex_ai.py`, `tutor_ai.py`; tests for structured Claude/Codex event streams and routing.
Consumes Task 1 interface and additive local constructor mode.

- [x] Write failing fake-CLI tests proving native schema flags, original model/thinking/auth options, structured event
  identity, complete-block output, final agreement, speech separation, usage accounting and cancellation cleanup.
- [x] Run focused tests to prove failures.
- [x] Implement additive Claude document mode with native schema, message/tool/index correlation, structured JSON deltas,
  suppressed narration, final object validation and process reset on invalid/divergent candidate. Preserve plain reader.
- [x] Implement additive Codex document mode using existing output-schema option and completed message granularity.
  Store validated wire in its host history. Preserve legacy mode and one-shot schemas.
- [x] Enable document mode in TutorAI actual conversations. Replace blanket 120-word/no-headings policy with task-scaled
  exam guidance; treat recent context as background for new-topic chat, while one-shot source-only tasks retain grounding.
- [x] Test all provider branches, custom systems, speech, bad finals, repeated candidates, native errors/limits and
  existing settings/routing compatibility. No commit.

### Task 4: Bounded existing study references

Files: modify `prompts.py`; create `study_sources.py`; add `test_study_sources.py` and prompt regressions.
Independent of transport. Produces source-labelled excerpts before the student's latest request.

- [x] Write failing tests with synthetic Packs: precise bonding match, explicit subject overrides stale session,
  ambiguous/weak query omits results, only allowed public facts, stable provenance and total bound.
- [x] Run tests to prove failures.
- [x] Reuse in-memory graph plus cached published packs. Rank exact glossary/title phrases and informative term overlap.
  At most six points and a fixed excerpt budget; label sources as study references, not official mark schemes.
- [x] Add retrieval to shared `prompts.ask` only. Skip whenever a practice question is OPEN. Preserve existing context
  and current user question exactly. Exclude hidden items/solutions and cached AI material.
- [x] Test OPEN answer protection, missing/damaged packs, partial publication, no match and topic switching. No commit.

### Task 5: Compatibility formatting regressions

Files: modify `output_format.py` narrowly; extend output/display/cached-content tests.

- [x] Freeze screenshot text and observed baseline layout defects; test blank-line/list recovery without changing math,
  dot products, hydration dots, code, literal escapes, quotes or URLs.
- [x] Run failing regression. Implement only unambiguous protected AI-prose recovery; new documents use Task 1 renderer.
- [x] Test character-split streaming plus canonical Now/log equality and all established maths corpus categories.
- [x] Run focused formatter and screen suites. No commit.

### Task 6: Live comparison and visual evidence

Files: durable comparison report and visible-output JSON under `docs/benchmarks`; isolated visual artifacts.

- [x] Preserve before-change baseline from `/tmp/stem-format-current/baseline-live.json` and native Sonnet probe.
- [x] Run frozen before/after prompts on six routes: Sonnet, GPT-6.1-Sol, native Gemma26B/E4B/Qwen27B/GPT-OSS20B.
  Include definitions, overviews, calculus/sums/limits, physics calculation, mark-point correction, OPEN hint, topic
  change, code/literal JSON, speech and long context. Repeat difficult cases; no simultaneous GPU jobs.
- [x] Inspect visible answers against fixed reference criteria. Report formatting, content/mark coverage and timing
  separately. Retain timeouts, invalid outputs and factual failures. Repair implementation defects then rerun affected
  cases; never relabel an earlier failure as a success.
- [x] Capture actual Textual at 80x24,100x30,140x46 across Night/Day/Classic. Inspect saved pixels for layout/glyphs.
- [x] Create isolated Obsidian vault; capture and inspect reading view including MathJax, lists and literal code.
  Restore original view without writing learner content. Compare semantic content and spacing, not identical glyph metrics.
- [x] Save concise research/comparison report, screenshot links, exact commands, model IDs, stop reasons and limitations.

### Task 7: Full verification and independent review

- [x] Run `PYTHONPATH=tests/app .venv/bin/python -m pytest tests --import-mode=importlib -n 4 --dist=loadscope -q`.
- [x] Run `git diff --check`. Confirm no altered provider settings, model weights or learner data from this task.
- [x] Dispatch independent Standards and Spec review of diff from `aa558ff21ca1da5a46487a9ce6d0811c6f059d62`, including
  untracked new files. Fix actionable findings and re-run relevant gates.
- [x] Audit every approved requirement against code, actual outputs, screenshots and test evidence. Mark goal complete
  only when implemented/verified; otherwise preserve full objective and record remaining work.

## Execution ledger

- Design approved by user on 26 October 2026. Implementation authorised; use parallel bounded tasks in this session.
- Initial read-only root-cause, primary-source and visual investigations complete. Baseline live process session26224
  remains authoritative; do not restart it merely because a poll times out. Native Sonnet probe session76225 completed.
- Existing dirty learner-content files are unrelated and preserved. No commits or release-tag changes planned.
