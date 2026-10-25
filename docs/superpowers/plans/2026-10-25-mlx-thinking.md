# MLX and Local Thinking Strengths Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Verify MLX execution for all four requested local models, add native local reasoning strengths, and publish measured response-time and quality comparisons.

**Architecture:** Keep E4B/Qwen native MLX and import Gemma QAT into Ollama under a distinct alias. Run original GPT-OSS in an isolated SSD MLX-LM worker with private pipes and Harmony-aware JSON constraints. Reuse the local client's request lock, required preload, reply decoder, histories, and downstream formatting.

**Tech Stack:** Python 3.13, Textual, Ollama 0.40.11; isolated MLX-LM 0.32.2, Outlines 1.3.3, llguidance 1.9.1, with verified compatible pins.

**Spec:** `docs/superpowers/specs/2026-10-25-mlx-thinking-design.md` (approved).

## Global Constraints

- All four: Gemma 26B, E4B, Qwen 3.8 27B, GPT-OSS run through verified MLX choices. Preserve originals as explicit rollback choices.
- All added weights, caches, runtime environments, and receipts stay below `/Volumes/External SSD TB4/LocalAI`.
- No LM Studio configuration/model registration changes; no shared Ollama replacement.
- Existing Claude/ChatGPT presets, boolean controls, routing, prompts, limits, and execution remain unchanged.
- Never retain or expose hidden reasoning; no silent cloud fallback or reduced answer/precision budget.
- One local inference/preload lock and one large loaded runtime; every generation requires successful exact preload acknowledgment.
- Preserve learner files, prior uncommitted work, version 2.6.0, and the published tag. No automatic commit/push/restart.
- User approved implementation; execute this plan with delegated independent work and focused reviews without another execution-method approval.

## Review Focus

- A reasoning header shares a separator with a final header: only a complete final-channel boundary activates JSON constraints.
- Low/Medium/High requests differ in histories, image omission, and answer cache identity; legacy aliases map canonically.
- A cancelled or replaced worker cannot acknowledge readiness or publish an old result into the next request.
- SSD removal or incomplete installation must hide the new option without erasing a saved selection.
- Switching cloud/local must preserve cloud switches and avoid loading local runtimes for cloud-only work.

## File ownership and interfaces

- Strength/settings worker: `local_models.py`, `config.py`, `presets.py`, `screens.py`, Settings CSS in `app.py`, and corresponding settings/catalogue tests.
- Native generation worker: new `mlx_harmony.py`, `mlx_worker.py`, and their focused tests. Heavy dependencies imported only inside the SSD worker.
- Root: new `mlx_local.py` parent IPC, `local_ai.py` and `tutor_ai.py` integration, SSD installation, live comparisons, documentation, and integration tests.
- Shared identifiers: `ollama:gemma4:26b-tutor-mlx` and `mlx:gpt-oss:20b`.
- SSD constants in `local_models.py`: `MLX_CHECKPOINT = ROOT / 'models/openai/gpt-oss-20b'`; `MLX_PYTHON = ROOT / 'tutor-runtime/mlx/.venv/bin/python'`; `MLX_RECEIPT = ROOT / 'tutor-runtime/mlx/gpt-oss-20b.json'`; pinned GPT revision from spec.
- Installation receipt: `revision` string plus `files` dictionary of checkpoint-relative basename to verified byte size, and runtime package version metadata. Availability checks runtime, expected revision, required config/tokenizer/index/shards, exact receipt sizes, and rejects unsafe filenames. Installation writes receipt atomically only after verification.
- `thinking_value(model, value: bool | str) -> bool | str | None` validates wire values. `thinking_key(model, value)` returns canonical history/cache identity (e.g. legacy GPT False equals `low`, Qwen True equals `xhigh`). Named levels: GPT `low/medium/high`; Qwen `off/low/medium/xhigh` with `off` mapped to False.
- Parent `MLXLocal.events(payload: dict, timeout: float)` yields the existing local event shape. Empty `messages` is preload, acknowledged with `done=True`, `done_reason='load'`, empty content, exact worker/model identity validated by parent. `close()` stops only owned worker.
- Worker reads JSON-line request `{id, payload}` and writes JSON-line `{id, event}`; all reply events carry the matching ID. `payload.model` is fixed `mlx:gpt-oss:20b`. A close/unload operation releases weights or terminates owned process. Protocol input/output bounded at 4 MiB per line.

### Task 1: Local strengths, catalogue, and settings

- [x] Add failing tests for native values, old/new settings round trips, cloud isolation, effort-only manual edits, preset matching, missing/partial SSD receipt, and compact keyboard-accessible selectors.
- [x] Run the new focused tests and record the expected missing-feature failures.
- [x] Add additive `ai_mark_effort`, `ai_explain_effort`, `ai_ask_effort` strings; blank preserves legacy booleans. `Settings.ai_for()` returns named values only for eligible local models.
- [x] Add both distinct MLX model choices and complete-install availability checks; retain original IDs. Copy capability/context/keep-alive metadata appropriately.
- [x] Implement canonical reasoning mapping and existing-row strength selectors. Preserve unsupported/always-thinking switches, hotplug choices, Preview/Apply/Save/Cancel, cloud presets, and explicit local re-mark effort.
- [x] Update local presets to MLX IDs and explicit GPT Low/High. Root may retain an original preset if live compatibility fails; never falsely label fallback as MLX.
- [x] Run focused settings/catalogue/cloud-isolation tests after GPU benchmark finishes; capture representative terminal screenshots with fake providers.

### Task 2: GPT Harmony and native generation

- [x] Add failing pure tests for direct final, analysis then final, split/multiple headers, historical-prefix exclusion, unfinished final, EOS, schema-only final tokens, and no hidden reasoning retention. Use pinned special IDs from spec/tokenizer, derive and validate at runtime.
- [x] Observe expected failures before implementation.
- [x] Implement bounded token-state parsing shared in behavior but separate in instances for grammar lookahead and emitted-token filtering.
- [x] Implement SSD worker commands using `mlx_lm.load(..., lazy=False, trust_remote_code=False)` and native official template effort. Evaluate weights before preload acknowledgment.
- [x] Attach Outlines/llguidance JSON processor only after complete final header; feed it final tokens only. Decode final tokens separately into the existing strict chat/marking path. Preserve native sampling and complete-answer policy; enforce deadline/cancel through parent termination when needed.
- [x] Report real token/time/MLX memory counters with clear semantics, public phase only, and unknown counters left unknown. Bound idle residency to existing keep-alive policy.
- [x] Verify pure tests and live import/generation compatibility before adoption.

### Task 3: Parent lifecycle and existing client integration

- [x] Add failing IPC tests using an owned fake worker for identity, bounded lines, preloaded generation, cancellation, timeout, reset, crash, SSD removal, close, and cloud-only laziness.
- [x] Implement `MLXLocal` asynchronous private-pipe orchestration with original deadlines and bounded termination/kill cleanup.
- [x] Route only the registered MLX payload through the adapter from `LocalAI._events()`. Keep the same local lock/preload/retry/decoder path.
- [x] Release the tutor-prepared Ollama model before loading GPT; release GPT before Ollama. Do not stop an externally owned server or unload unrelated models. Detect unsafe remaining large residency and provide an actionable error.
- [x] Remove local bool casts and canonicalize effective strength in history/image keys and structured reply keys. Validate invalid strings before requests; preserve cloud branches.
- [x] Reset/close/release invalidate the worker and pending work. Retain hidden-reasoning privacy and exact schema/speech/vision/web flow.
- [x] Run focused integration/preload/cancellation/cache/cloud regression tests when GPU benchmarking is idle.

### Task 4: Install, compare, review, and handoff

- [x] Finish baseline; capture one raw answer-only GPT failure to distinguish malformed JSON from decoder disagreement. Do not infer a grammar cause from slow High alone.
- [x] Import Gemma under the new alias without requantization. Download pinned original GPT checkpoint with `hf download --local-dir` under SSD; install/verify isolated runtime pins and write completed receipt.
- [x] Verify all four actual live MLX runners/worker. Run candidate workloads serially with matching frozen baseline inputs. Report original/native package differences and unchanged E4B/Qwen controls.
- [x] Audit all completed explanation samples for correctness/completeness, and twelve marking flags. Record failures/timeouts and timing distributions with honest sample counts. Keep slow High optional; evaluate Medium on the same fixtures.
- [x] Review separate Standards and Spec axes against task diff/spec. Resolve material findings and recheck relevant tests.
- [x] Run `PYTHONPATH=tests/app .venv/bin/python -m pytest tests --import-mode=importlib -n 4 --dist=loadscope -q` after inference ends. Record actual pass/failure counts.
- [x] Update comparison/docs/README/CHANGELOG and provide scoped push commands for main at version 2.6.0, preserving the existing tag.

### Task 4a: Lossless Gemma import compatibility

**Files:** `app/tutor_app/mlx_gemma_import.py`, `tests/app/test_mlx_gemma_import.py`.

- [x] Prove expert-wise byte interleaving and mixed-precision header repair with small synthetic safetensors fixtures; observe RED before implementation.
- [x] Stream gate/up expert slabs into native fused banks and rename down-bank header keys, preserving numeric bytes and the original checkpoint.
- [x] Correct the 120 source-configured 8-bit tensor metadata entries; preserve group size and complete payload.
- [x] Write content-addressed new blobs and replace only the fixed tutor alias manifest atomically after validation; retain an original-manifest backup and make reruns idempotent.
- [x] Review the adapter and run it on the SSD only after tests pass; verify actual native load, memory, marking, image input, and tutoring before adoption.

## Execution ledger

- Design approved by learner; full migration selected. Builder check: nothing important left.
- Baseline started before any dependency/model/product change; exact payloads and source hashes saved on SSD. GPU inference stays serial and separate from tests.
- Ruling: reuse current checkout because required prior authorized changes are uncommitted here; a clean worktree would omit them. Preserve all unrelated content and leave staging/commits to learner's requested command handoff.
- Ruling: model and strength UI is additive to existing Settings rows and design tokens; no unrelated visual redesign.
- Ruling: idle conversation reset preserves evaluated MLX weights and clears history; an active reset still terminates pending native work. Every later response requires a fresh readiness acknowledgment. This preserves preload responsiveness without accepting stale results.
- Native Gemma import completed without requantization. Ollama writes it in `manifests-v2/ollama.com`, so discovery now checks both manifest versions.
- Original GPT checkpoint: ten required files passed Hugging Face checksum verification. Isolated runtime imports and `pip check` pass; first evaluated-weight readiness smoke passed (16.80 s, diagnostic rather than a comparison trial).
- First live candidate probe failed compatibility: native Gemma's runner cannot load the community package's expert keys, and its importer loses 120 per-layer int8 overrides. Preserve this failed probe as evidence; Task 4a repairs representation without requantization or source mutation.
- GPT live framing includes JSON content-type metadata. The parser now supports documented Harmony JSON metadata while requiring an explicit analysis/final channel and keeping reasoning private. Failed probes remain separate from successful comparisons.
- Ruling: confirmed-offline/empty Ollama means no weights remain to unload; clear stale ownership and permit MLX without starting Ollama. Unknown connection/residency states still block loading.

- Task 1: complete — native strengths, five local presets, cloud isolation and compact UI verified. Latest label-only gate: 59 passed.
- Task 2: complete — real Metal generation passed Low/Medium speech/High; finite headers and one-use child readiness verified.
- Task 3: complete — exact parent readiness, idle weight retention, active cancellation, offline switching and SSD-only cache environment verified. Spec fix round 1/5: one preload finding addressed, zero open (workspace changes at base 475fd15).
- Task 4a: complete — 30 adapter tests, source-hash verification, lossless native alias publication and real Gemma image input passed. Fix round 1/5: three findings addressed, zero open.
- Output controls: fix round 1/5 — canonical-before-terminal source loss addressed, zero open; 492 focused tests passed.
- Task 4: complete — 35 matched frozen payloads identical except model ID; timings and quality failures published locally. Full suite: 4,178 passed, 28 existing warnings, 144.24 s. Standards/Spec/late guard reviews clear. No commit, push or tag rewrite performed.
