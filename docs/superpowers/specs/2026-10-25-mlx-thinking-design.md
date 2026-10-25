# Native MLX tutoring and local reasoning strengths

Status: approved and implemented. The learner selected full MLX migration, with compatibility checks and rollback, on 25 October 2026, then explicitly included Gemma 26B, Gemma E4B, Qwen 3.8 27B, and GPT-OSS. Final verification completed on 26 October.

## Intent

Improve local tutoring response time on this M4 MacBook Air (10 CPU cores, 10 GPU cores, 24 GiB unified memory). Provide verified MLX execution for Gemma 26B, Gemma E4B, Qwen 3.8 27B, and GPT-OSS, and update local presets to use compatible MLX selections. Add native reasoning strengths so a maximum-effort switch is no longer the only thinking option for eligible local models. Report comparative performance honestly even if an MLX candidate is slower for a workload; retain original choices for explicit rollback.

The comparison must measure complete, usable answers, not just token throughput. A fast but incomplete or incorrect explanation is a failed trial. Preserve the established terminal/Obsidian formatting contract, exact marking guards, speech, image preparation, web retrieval, and per-request preload requirement.

## Existing state and constraints

- Presets use Gemma 4 26B QAT, Gemma 4 E4B, and GPT-OSS 20B.
- E4B already uses Ollama's native MLX runner, NVFP4 weights, and an embedded assistant draft. Reinstalling it would not establish an MLX gain. Retain it as the unchanged control.
- Qwen 3.8 27B also already uses Ollama's native MLX runner and NVFP4 weights. Preserve that package and verify the live runner. It is included even though current presets do not select it.
- Gemma 26B currently uses GGUF Q4_0. A complete MLX QAT package already exists at `/Volumes/External SSD TB4/LocalAI/LMStudioModels/lmstudio-community/gemma-4-26B-A4B-it-QAT-MLX-4bit`, revision `aa5e2e50376f54254d503276ca2222ea8569b95e`. This source folder is an existing SSD asset; using it does not register it in LM Studio or change LM Studio settings.
- The Gemma MLX package uses affine 4-bit/group 64 with selected 8-bit tensors. Comparison with GGUF is a package-and-runtime comparison, not an isolated change of execution framework.
- Installed Ollama 0.40.11 supports importing this native Gemma architecture but has no native GPT-OSS MLX architecture.
- Original `openai/gpt-oss-20b`, pinned to revision `6cee5e81ee83917806bbde320786a8fb61efebee`, can load directly in MLX-LM. Preserve its MXFP4 experts and BF16 remaining tensors. Do not substitute an additionally quantized community package merely to improve a benchmark.
- All added weights, caches, runtime environments, and model receipts live under `/Volumes/External SSD TB4/LocalAI`. Do not register or repopulate LM Studio models.
- Existing Claude/ChatGPT presets, boolean controls, routing, prompts, limits, and execution remain unchanged by this local migration.
- Preserve all existing learner-content changes and current uncommitted tutor work. Do not publish or retarget the existing `v2.6.0` tag automatically.

## Approaches

The learner selected **full migration with compatibility checks and rollback**. Gemma uses the existing Ollama MLX importer; GPT-OSS gets an isolated tutor-owned worker. This is more work than leaving GPT-OSS on GGUF, but covers every distinct preset model without replacing the installed Ollama application or depending on LM Studio.

The smaller alternative migrated only Gemma and retained GPT-OSS GGUF. It avoids a second runtime but does not deliver MLX for every preset model. Replacing Ollama with a custom preview build would change a shared installed application and is not the selected approach. Stock MLX-LM server lacks schema handling; generic single-token thinking gates are insufficient for GPT Harmony. The worker therefore needs a small, explicit reasoning-aware integration.

## Model installation and adoption

1. Keep existing model identifiers and artifacts available for explicit rollback.
2. Import the existing Gemma MLX folder under a distinct tutor MLX alias, without requantizing. Confirm backend, multimodal capability, sampling, template, and actual successful inference after import.
3. Download the pinned original GPT-OSS checkpoint into a dedicated SSD folder. Validate the listed checkpoint/config/tokenizer files before writing an atomic installation receipt. No `trust_remote_code` or execution of model repository code.
4. Create an isolated SSD Python environment with compatible pinned MLX-LM, Outlines, and llguidance versions. Initial researched candidates are MLX-LM 0.32.2, Outlines 1.3.3, and llguidance 1.9.1; the builder must verify imports and adjust compatible pins only with recorded evidence.
5. Expose a distinct GPT-OSS MLX choice only when its completed receipt, checkpoint files, and runtime exist. Model discovery remains fresh so SSD insertion/removal works after launch.
6. Make all four verified MLX choices available. Update presets only after compatibility/quality checks pass, and use measurements to recommend the quickest suitable presets. If MLX is slower, report that limitation and preserve the original explicit rollback choice; do not claim improvement or silently downgrade precision/shorten answers. If a candidate fails functional compatibility, retain the usable original preset choice and report that migration as incomplete rather than silently presenting GGUF as MLX.
7. Existing saved custom selections remain authoritative. Updated presets take effect through the existing Preview, Apply, Save workflow; explain any required reapplication in the handoff.

## GPT-OSS worker boundary

Keep heavy MLX dependencies out of the normal tutor environment. A local-only adapter launches a private worker using the SSD Python environment. Use bounded JSON-lines over owned stdin/stdout pipes, not a public server. The adapter accepts only the registered checkpoint and fixed operation types: load, generate, unload/close.

The worker uses the official tokenizer chat template with native `reasoning_effort`. Load and evaluate weights before acknowledging readiness; loading must not generate an answer. Repeated load requests acknowledge the same live worker and exact checkpoint identity. Every generation still passes the tutor's mandatory preload gate under the same inference lock.

Use a token-sequence-aware Harmony parser for both grammar activation and visible-stream extraction, with separate parser instances because MLX-LM generates ahead of yielded tokens. Initialize at the unfinished current assistant prefix; never scan historical prompt headers as new output. Permit analysis unconstrained. Activate JSON constraints only after a complete final-channel header. Send only final-answer text into the existing strict reply decoder. Support direct-final replies, repeated analysis messages, split headers, Unicode, schema/speech output, and explicit errors for malformed or unfinished replies. Derive and validate control-token IDs against the pinned tokenizer.

Never store, log, display, or copy hidden reasoning into history. Public phases, times, and counts are sufficient. An error must not silently send a request to Claude or ChatGPT.

## Lifecycle, memory, and cancellation

Reuse the existing shared local request lock so preload and inference remain serialized across both runtimes. Before entering GPT-OSS MLX, unload only the last Ollama model successfully prepared for this tutor client. Leave unrelated models alone; if another loaded model prevents safe execution, provide an actionable error instead of loading both large runtimes into 24 GiB. Before returning to Ollama, release the owned GPT worker's weights or stop that worker.

Readiness includes live process, model identity, current generation, mounted SSD, and original request deadline. Check before load, before generation, and before accepting completion. Reset/cancel/close invalidate partial work and history. The parent owns worker termination and bounded kill fallback if a GPU operation does not stop promptly. No partial answer becomes a successful cached result.

Preserve existing per-request timeouts and complete-answer token policy. Do not impose a smaller hidden reasoning or answer cap to manufacture a speedup. Keep E4B's current native speculation. Prefix caching is optional builder work only if safe native cache copying/trimming is demonstrated, memory is bounded, and partial/cancelled work cannot pollute future answers; it is not required to ship this migration.

## Local reasoning controls

Add per-task local strength settings without replacing legacy boolean fields. Blank strength means the existing saved switch behavior. For eligible local models, show a compact strength selector in the existing task row; other models retain their current switches.

| Local model | Offered strengths | Legacy behavior |
|---|---|---|
| GPT-OSS GGUF and MLX | Low, Medium, High | Off switch maps to Low; On maps to High |
| Qwen 3.8 27B | Off, Low, Medium, Maximum | Off maps to false; On maps to native `xhigh` |
| Boolean-only thinking models, including Gemma | Existing Off/On | Unchanged |
| Always-thinking local models | Existing fixed On | Unchanged |
| Models without thinking | Existing unsupported state | Unchanged |

Qwen's visible Maximum maps to exact native `xhigh`; do not invent a `high` wire value. Validate named values centrally. Never convert an arbitrary string to `True`. Resolve settings to canonical effective effort for histories, image reuse, and structured reply caching, so strengths cannot share answer state accidentally. Preload and image OCR do not generate reasoning or acquire an effort-specific history.

Keep all four cloud presets unchanged. Update local presets with adopted backend identities and explicit supported strengths. Keep low reasoning for everyday GPT tutoring and high for extended reasoning; a fifth local Medium preset may be added if the measurements establish a useful middle option. Presets still alter only three model choices and their thinking choices. Preview must spell out strengths; manual changes show Custom, Esc cancels, and Save preserves disconnected SSD selections. An explicit saved local marking strength also applies to re-marking; preserve existing cloud re-mark behavior.

## Comparison and acceptance

Use the current synthetic mathematics, physics, and chemistry fixtures with current production marking schema, chat envelope, system brief, and speech contract. Freeze exact messages/schema/options/effort and source hashes. Baseline collection started before model, dependency, or product changes.

- Gemma: twelve marking cases, plus three tutoring cases repeated three times.
- GPT-OSS Low and High: the same three tutoring cases repeated three times when viable. Stop an arm after a full-deadline timeout or repeated invalid output rather than spending many minutes repeating an established failure; report smaller sample counts and failures, not a misleading successful median.
- Medium: compare on the same fixtures after strength routing is implemented.
- E4B and Qwen 27B: unchanged MLX controls, live runner verification, and a final regression check. Do not describe their unchanged native execution as a migration speedup.
- At least one complete speech reply per viable arm; native Gemma image smoke; existing OCR path for text-only GPT.

Run one GPU workload at a time, with no simultaneous test suite. Record model preload separately, first backend activity, first decoded visible character, full valid completion, input/output counts, available backend counters, termination reason, retries, and mark correctness. Missing counters remain unknown rather than invented measurements. Preserve full final answers but no hidden reasoning. Separate runner-cold loading from warm responses and note uncontrolled OS disk caching, cache reuse, output length, temperature, and thermal/memory conditions.

Audit explanation correctness and completeness separately from schema validity. Existing baseline already exposes Gemma replies ending mid-sentence and GPT-OSS JSON failures; these are failed usability trials even if some timing counters exist. A small passing sample does not guarantee universal STEM accuracy or unchanged quality. Publish individual measurements, median/range where justified, failures, quantization differences, and practical recommendations.

Compatibility tests must cover native named-level mapping, settings migration, preset Preview/Apply/Save/Cancel, SSD hotplug, required preload for every attempt, Harmony boundaries and schema activation, speech, image handling, cancellation, stale worker identity, reset, history/cache separation, and regression tests for unchanged Claude/ChatGPT paths. Review both documented conventions and this spec, then run the appropriate complete suite.

## Completion and handoff

Deliver implemented controls and verified model integrations, a source-backed measured comparison with limitations, exact SSD installation details and rollback choices, restart/reapply instructions, and scoped Git commands. Keep version 2.6.0. Do not commit, push, force-update tags, remove original weights, change LM Studio settings, or restart a live study session automatically.

## Primary references

- [Ollama 0.40.11 native architecture registry](https://github.com/ollama/ollama/blob/v0.40.11/mlxrunner/model/architectures/architectures.go)
- [Ollama prequantized importer](https://github.com/ollama/ollama/blob/v0.40.11/create/prequant.go)
- [Gemma QAT MLX artifact](https://huggingface.co/lmstudio-community/gemma-4-26B-A4B-it-QAT-MLX-4bit)
- [Hugging Face native MLX integration](https://huggingface.co/docs/transformers/en/community_integrations/mlx)
- [Pinned original GPT-OSS model](https://huggingface.co/openai/gpt-oss-20b/tree/6cee5e81ee83917806bbde320786a8fb61efebee)
- [MLX-LM 0.32.2 generation](https://github.com/ml-explore/mlx-lm/blob/v0.32.2/mlx_lm/generate.py)
- [Outlines MLX integration](https://dottxt-ai.github.io/outlines/latest/features/models/mlxlm/)
- [Ollama native thinking values](https://docs.ollama.com/capabilities/thinking)
