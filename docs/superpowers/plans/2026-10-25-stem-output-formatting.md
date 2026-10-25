# Consistent STEM Output Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task by task.

**Goal:** Give all tutor providers consistent readable STEM prose and safe mathematics in terminal and Obsidian.

**Architecture:** Store canonical Markdown/LaTeX and adapt it for each display. Protect literal spans, buffer unfinished
maths in streaming cards, and format only whitelisted human-facing structured fields. Keep the existing provider
protocols and authored-content renderer.

**Tech Stack:** Python, existing MarkdownIt/Rich/Textual, pinned flatlatex, bundled JuliaMono; no new dependencies.

**Spec:** `docs/superpowers/specs/2026-10-25-stem-output-formatting-design.md` and `docs/STEM_OUTPUT_FORMATTING.md`.

## Global constraints

- Preserve provider transport, model selection, thinking, preload gates, timeouts, usage and conversation ownership.
- Preserve student text, code, URLs, speech, point identities, machine fields and mathematical meaning.
- Keep valid mathematical source for Obsidian even when terminal conversion needs a fallback.
- Inline pending maths ends at a paragraph break; all pending spans are capped at 2,048 characters.
- Reuse the active checkout because it contains required uncommitted preload work; preserve all unrelated changes.
- No downloads, production AI calls, dependency installations, commits or pushes are needed for this implementation.

## Review focus

- Currency, percentages, escaped delimiters and code remain literal.
- Split/incomplete delimiters cannot hide a response indefinitely or leak unlabelled raw syntax.
- Unsupported macro conversion cannot discard mathematical meaning or degrade valid Obsidian source.
- JSON machine fields and matching mark-point identities remain byte-for-byte unchanged.
- New italic glyphs and complete script groups fit bundled fonts and narrow transcript cards.

### Task 1: AI mathematical adapter

**Files:** create `app/tutor_app/stem_math.py`, `tests/app/test_stem_math.py`; targeted changes to `texmath.py` only if required.
**Interface:** `render_math(expr: str) -> str | None`; input is a delimiter-free expression; output is faithful terminal
Unicode with semantic variables/scripts, or `None` when unsupported. No Markdown escaping in this function.

- [x] Write and run failing corpus tests for italic variables/upright units/functions, powers/indices, derivatives,
  sums/integrals, matrices, chemistry, fractions/roots, bold vectors, `bot`, multiplication and unknown macros.
- [x] Implement the adapter with current converter reuse, complete-group scripts and meaning-preserving fallback.
- [x] Run new tests and existing `test_texmath.py`/`test_glyphs.py`; require successful common cases, separate fallback cases.
- [x] Independently review conversion and fix actionable findings.

### Task 2: Shared visual text and safe incremental cards

**Files:** create `app/tutor_app/output_format.py`, `tests/app/test_output_format.py`; modify `cards.py`, `screens.py`,
`challenge_screen.py` at AI rendering/final-text boundaries.
**Interfaces:** `normalise_visual(text: str, *, partial: bool = False) -> str` gives canonical Markdown/LaTeX;
`terminal_visual(text: str, *, partial: bool = False) -> str` gives Markdown-safe display text using Task 1.

- [x] Write failing tests for protected literals, canonical delimiters, spacing/list layout, all delimiter split
  positions, currency, missing delimiters, paragraph/size limits, math/Markdown collisions and final note parity.
- [x] Implement typed span handling using existing Markdown parsing plus bounded math scanning; never guess ambiguous algebra.
- [x] Render AI cards with the new adapter; keep standard lesson cards and student answers on existing paths.
- [x] Normalise final visual text before terminal/Now/log mirroring; preserve speech and answer-guard order.
- [x] Run focused renderer, streaming, Obsidian parity, speech and preload tests; inspect rendered samples at all planned sizes/themes.

### Task 3: Shared writing contract and structured prose

**Files:** create `app/tutor_app/output_fields.py`, `tests/app/test_output_contract.py`; modify `ai.py`, `prompts.py`,
`tutor_ai.py` only at common brief/structured visual-result boundaries.
**Interface:** `normalise_fields(data: dict | None, schema: dict | None) -> dict | None` copies only known visual prose
fields through Task 2; preserves every machine field and speech. Do not wrap or alter provider streaming protocols.

- [x] Write failing provider/field tests proving shared writing brief and explicit schema whitelists.
- [x] Add concise shared response-type rules: key idea, numbered calculations, independent bullets, blank logical gaps.
- [x] Normalise successful JSON prose across all providers including cached data without modifying caller inputs.
- [x] Cover marking `feedback`/`points[].why`, re-mark `why`, card prose, profile `summary` and separately audited
  challenge human prose; preserve all machine answers/values/working, IDs, units, expressions, options and speech.
- [x] Run contract/routing/default/speech/local-cache tests and independent review.

### Task 4: Integration, proof and handoff

- [x] Audit cached AI prose consumption and use the same visual standard without bulk rewriting history.
- [x] Review task changes independently against standards and approved specification; fix confirmed findings.
- [x] Run `PYTHONPATH=tests/app .venv/bin/python -m pytest tests --import-mode=importlib -n 4 --dist=loadscope -q`.
- [x] Run compile and whitespace checks, update README/CHANGELOG/design status and record evidence here.
- [x] Report capabilities, tested limits and restart instruction. Do not promise perfect model writing or arbitrary terminal typesetting.

## Ledger

- Inventory: 407 registered commands, 881 mapped non-ASCII glyphs. Counts and cmap claims independently verified.
- Baseline: 393 tests passed in 46.79 seconds for maths, glyphs, Obsidian parity and speech.
- Approval: user selected “Approve and implement (recommended)”.
- Ruling: use subagents for independent adapter/contract tasks and main agent for shared text/render integration;
  no further execution-method approval is needed after the user's explicit implementation instruction.
- Ruling: preserve the active checkout and its earlier uncommitted preload fixes; a clean HEAD worktree would omit
  required behaviour. No branch switch or bulk staging.

## Completion evidence

- Independent standards and specification reviews verified the inventory and found no unresolved P1/P2 issues after fixes.
- Regression work reproduced and fixed grouping loss in fractions, vectors, compound powers and root indices, as well as
  literal-boundary, incomplete-command and fallback adjacency defects. Every confirmed defect received a failing test first.
- Full integration suite: **3,652 passed**, 28 pre-existing warnings, in 137.99 seconds.
- Final focused formatter/contract/cache/display/math gate after the last edge fixes: **190 passed** in 4.47 seconds.
- Mathematical adapter: **79 named cases**; legacy maths/font protection also passed (416 cases together).
- Nine card exports cover 80, 100 and 140 columns in Night, Day and Classic. Browser inspection verified local JuliaMono
  regular/bold/italic glyphs, explicit source code, mathematical variables/scripts and reading gaps.
- No real AI requests, new dependencies, model downloads, commits, pushes or historical-file rewrites were performed.
- The user's queued Settings layout task follows this completed workflow; its final full run also covers these changes.

Final combined verification after the queued Settings task: **3,671 passed**, 28 pre-existing warnings,
in 138.98 seconds. This run includes the last differential, literal-fallback parity and Settings changes.
