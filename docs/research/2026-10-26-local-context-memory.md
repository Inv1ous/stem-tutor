# Qwen 27B native MLX long-context memory investigation

2026-10-26. Read-only source/metadata investigation; no model loads, inference, GPU work, runtime changes or original-model writes. The coordinating agent reports matrix 93430 succeeded on seven of eight Qwen3.8 27B Thinking Off chats; its long-history case panicked with `METAL InsufficientMemory`, while the other three models passed. This note did not rerun that failure.

## Source findings

All upstream links below are pinned to **Ollama v0.40.11**, resolved through the GitHub tree API to commit `675150d6ad2747df1e218ef59de9194bc4a7e538`.

- [`server/sched.go`, native branch](https://github.com/ollama/ollama/blob/675150d6ad2747df1e218ef59de9194bc4a7e538/server/sched.go#L632) passes `opts.NumCtx` to `mlxrunner.NewClient` as a **soft context length**. The llama-server automatic batch/memory prediction path is separate; do not apply its assumptions to native MLX.
- [`mlxrunner/client.go`, `reportedContextLength`](https://github.com/ollama/ollama/blob/675150d6ad2747df1e218ef59de9194bc4a7e538/mlxrunner/client.go#L285) reports the smaller positive soft/model context to the outer server. Its subprocess command passes only model and port. Therefore an explicit `num_ctx` can affect outer token-aware chat truncation/reporting without reconfiguring the model's internal context allocation.
- [`server/routes.go`, `truncateNativeChatMessages`](https://github.com/ollama/ollama/blob/675150d6ad2747df1e218ef59de9194bc4a7e538/server/routes.go#L3540) renders/tokenizes candidate suffixes and compares them to `opts.NumCtx`. This limit does not itself reserve answer tokens. Keep host pair-preserving selection: server truncation walks message suffixes rather than enforcing the tutor's complete-pair contract.
- [`mlxrunner/runner.go`](https://github.com/ollama/ollama/blob/675150d6ad2747df1e218ef59de9194bc4a7e538/mlxrunner/runner.go#L131) sets native `contextLength` from `m.MaxContextLength()`. Its wired-memory setup wires at most the model's active allocations or Metal's recommended working set; it is not a reservation for all future activations/KV, nor a context-based memory cap.
- [`mlxrunner/pipeline.go`](https://github.com/ollama/ollama/blob/675150d6ad2747df1e218ef59de9194bc4a7e538/mlxrunner/pipeline.go#L22) hardcodes prefill chunks to `2 << 10` = **2,048 tokens**. `num_batch` is not consulted by this prefill path. `Prepare` checks input and remaining generation against the architectural context; `NumPredict <= 0` becomes all remaining architectural tokens. Consequently explicit `num_predict` is the available bound on generated tokens. Smaller history reduces actual prefill length/KV but cannot configure that fixed chunk size.
- [`mlxrunner/prefix_cache.go`](https://github.com/ollama/ollama/blob/675150d6ad2747df1e218ef59de9194bc4a7e538/mlxrunner/prefix_cache.go#L43) retains prefix/snapshot state, with an 8 GiB paged-out eviction threshold. It is not a guarantee that every native allocation fits the remaining RAM. Warm multi-request pressure can differ from one cold request.

## Local metadata and likely mechanism

Read-only manifest inspection found native child manifest `47951e4a666180bc2aedfc93c169472f2de783696fe196efbf063f5730ecf163`. Its named `config.json` blob is `af908e4b42c018ef923ebc38c16083aa75051dc3778b92b1443adabd2cab2267`, with text `max_position_embeddings=262144`, 64 layers, hidden 5120, intermediate 17408, 4 KV heads, head dimension 256, and one MTP layer. Native tensor layers total **18,155,017,220 bytes**, about 16.91 GiB. Manifest bytes are not a measurement of device-active allocations.

Inference: loaded weights plus fixed-size prefill temporaries, growing attention caches, recurrent states, optional draft state and retained prefixes can exceed available unified memory even though an approximately 6K-token prompt fits the architecture. A 17,221-byte host payload is neither an exact token count nor proof of a particular peak allocation. No evidence here proves which tensor failed; retain the original native stack trace and phase timings.

## Narrow mitigation to test

Current host code excludes Qwen27 from `local_models.CONTEXT_LENGTH`, while document history independently falls back to 8192. `_with_context` consequently sends no `num_ctx` for that model. Give it one explicit per-model policy, consumed by both history planning and outgoing requests.

For **Thinking Off**, start by testing context **4096**, preserving the current **2048 response reserve**: system/schema/current material plus retained history must fit an estimated 2048 prompt tokens. Remove only oldest complete history pairs. If the complete current question, sources and schema exceed the budget, report the existing context error and offer another model; never cut that material. Send `num_ctx=4096` consistently for preload/generation, and consider `num_predict=2048` to bind output independently of the native 262144 maximum. These are candidate operating limits, not demonstrated safe values.

Do not let adding Qwen27 to `CONTEXT_LENGTH` implicitly add **16384** recovery through the existing generated `MAX_CONTEXT_LENGTH` mapping. Exclude this model from automatic context expansion or set an explicit tested maximum. Do not silently impose the Off output budget on thinking modes; they need a separately measured reasoning/output allowance.

If 4096 still fails, test a stricter prompt budget (for example 1024 estimated tokens while preserving the current request), then consider a small upstream native-runner change exposing prefill chunk size. An application `num_batch=256` setting alone cannot implement that change in this source version. Avoid global VRAM/wired-limit increases: they do not remove allocations and can increase system pressure.

## Proof required before claiming a fix

Unit checks should prove per-model policy agreement, matching empty preloads, no 16K escalation, whole-pair removal, and byte-identical preservation of current question/sources/schema. Confirm oversized immutable material fails before generation. Keep existing settings authoritative.

After exclusive GPU access is available, rerun the exact failing long-history item cold and after the prior seven chat cases, at least three repetitions; record actual prompt/eval counts, retained pairs, durations, runner identity, memory pressure and original failure phase. Include a short request, a large current mark scheme, native images/OCR routes, and cancellation/reload recovery. Compare output completeness/marking against the original budget. If failure persists, retain the limitation rather than declaring safety from a smaller request or a successful preload. No such runtime proof has been collected by this investigation.
