# Local AI performance investigation

2026-10-25. Goal: maximise each installed model's useful output speed on this Mac while preserving tutoring quality. This note records verified observations, candidate controls, and the measurement protocol. It does not establish a speedup from the initial smoke tests.

Production guard: preserve the installed weights and their quantisation, sampling settings, thinking choice, full conversation/context policy, and answer-token limits. Keep local requests local. Runtime changes can preserve the intended model distribution without guaranteeing identical stochastic answers or bit-for-bit floating-point results.

## Verified local observations

Hardware and runtime were inspected separately from performance tests:

| Item | Observation |
| --- | --- |
| Computer | Apple M4 MacBook Air; 10 CPU cores (4 performance, 6 efficiency), 10 GPU cores, 24 GB unified memory |
| Runtime | Installed Ollama reports 0.40.11; MLX reports `0.32.3-96-gbebd642`, GPU device |
| Qwen 3.5 9B | MLX safetensors, approximately 7.64 GB; mixed MXFP8/NVFP4 tensor formats; embedded MTP head; Modelfile contains `draft_num_predict 3` |
| Gemma 4 26B A4B | GGUF Q4_0, approximately 15.63 GB; llama.cpp backend |
| Qwen 3.8 27B | MLX NVFP4 safetensors, approximately 18.17 GB; embedded MTP head; no explicit draft parameter in the inspected Modelfile |

Existing Gemma logs show full GPU loading, Flash Attention enabled, one request slot, batch size 512, four CPU threads, and f16 KV cache. The existing MLX prefix-cache limit is an eviction threshold, not a reservation of that entire amount of RAM. The three initial cold schema smoke calls established that the models could answer through the app; they were not controlled benchmarks.

These are observations from this investigation's hardware, manifests, and installed-runtime logs, not specifications inferred from model names. The installed binary may contain custom changes; compare its behaviour and logs before treating an upstream option as effective.

## What the official sources support

- **Keep the selected model resident.** Ollama supports an empty chat request to preload a model and a per-request `keep_alive` duration; the default residency is five minutes, and a negative value requests indefinite residency. This removes repeated loading from later requests, rather than increasing the decoder's intrinsic throughput. With 24 GB shared by the OS, application, weights, and caches, retain one selected model rather than preloading all three. The API setting overrides the server-wide setting. [Ollama FAQ](https://docs.ollama.com/faq#how-do-i-keep-a-model-loaded-in-memory-or-make-it-unload-immediately)
- **Reuse unchanged prefixes.** Upstream Ollama's MLX runner maintains a token-prefix trie across requests and restores matching cache state; generation still evaluates a seed token. Reusing the same system instructions and conversation prefix can reduce repeated prompt processing. Keep prompts semantically and textually unchanged for the comparison; do not remove context to create a faster result. [MLX prefix-cache implementation](https://github.com/ollama/ollama/blob/v0.40.11/mlxrunner/prefix_cache.go)
- **Treat MLX and llama.cpp separately.** Upstream MLX hardcodes a 2,048-token prefill chunk and serialises requests. Its pipeline does not use `num_batch` or `num_thread` to tune that chunk. Python `mlx-lm` exposes a different `--prefill-step-size` interface; that flag is not evidence of an Ollama API option. [Ollama MLX pipeline](https://github.com/ollama/ollama/blob/v0.40.11/mlxrunner/pipeline.go), [official MLX LM README](https://github.com/ml-explore/mlx-lm#long-prompts-and-generations)
- **Embedded MTP may already be automatic.** The upstream runner discovers a model's embedded draft head; its speculative session uses an adaptive depth controller across requests. The MLX enablement path does not read `draft_num_predict`. Therefore an absent Modelfile setting does not establish that Qwen 27B drafting is disabled. Check its actual speculative-generation logs before proposing a toggle. [Runner model loading](https://github.com/ollama/ollama/blob/v0.40.11/mlxrunner/runner.go), [speculative session](https://github.com/ollama/ollama/blob/v0.40.11/mlxrunner/speculate.go), [adaptive depth](https://github.com/ollama/ollama/blob/v0.40.11/mlxrunner/speculate_depth.go)
- **Speculation validates against the target.** The inspected MLX code uses target/draft acceptance probabilities and a residual rejection distribution. This supports preserving the intended target sampling distribution; it does not promise the same seeded token sequence because random draws and numerical execution differ. [Acceptance implementation](https://github.com/ollama/ollama/blob/v0.40.11/mlxrunner/speculate.go), [residual distribution](https://github.com/ollama/ollama/blob/v0.40.11/mlxrunner/sample/sample.go)

Source inspection uses the upstream `v0.40.11` tag, resolved during research to commit `675150d6ad2747df1e218ef59de9194bc4a7e538`. General documentation can lag implementation: the Modelfile reference describes manually enabling embedded MTP, whereas this MLX implementation discovers it automatically. Prefer the installed backend's observed behaviour for this Mac. [Modelfile reference](https://github.com/ollama/ollama/blob/v0.40.11/docs/modelfile.mdx)

## Candidates requiring measurement

| Candidate | Expected area of benefit | Acceptance condition |
| --- | --- | --- |
| Preload the selected model; extend residency through a study session | Cold response latency | Lower wall-clock first-token latency; bounded memory and clean model switching |
| Preserve and reuse stable prompt/history prefixes | Prompt processing and first-token latency | Reported cache hits and lower repeated-prefix latency, with the complete prompt retained |
| Keep one active model and one inference request at a time | Avoid contention and swapping | Stable per-request latency under the tutor's actual workload |
| Sweep Gemma `num_batch` around its current 512 and `num_thread` around its current 4 | Backend-specific prefill/CPU overhead | Repeatable end-to-end improvement; no truncation, failures, or unacceptable memory growth |

Ollama's API recognises `num_batch` and `num_thread` as runner options, but that alone does not prove a speed gain or support in every backend. Flash Attention is already active in the inspected Gemma run. Changing KV precision, model quantisation, thinking, context retention, or output limits is outside this quality-preserving investigation. [Ollama runner options](https://github.com/ollama/ollama/blob/v0.40.11/api/types.go), [Flash Attention and KV-cache documentation](https://docs.ollama.com/faq#how-can-i-enable-flash-attention)

## Controlled benchmark protocol

1. Benchmark models sequentially, with no other local inference. Record model digest, backend/library version, power state, thermal state, memory pressure, and swap. Keep the machine and SSD conditions comparable. Root owns inference during this investigation; research and inspection must not start competing generations.
2. Save one exact request per workload: a short tutor reply, a schema-based marking answer, and a longer conversation/prefix. Hold messages, history, images, schema, model, thinking, sampling, context, and output budget identical across each baseline/candidate pair. An optional fixed benchmark seed must be identical in both arms; it is not a production sampling change.
3. Separate **runner-cold** trials (explicitly unload and verify absence), **loaded but prefix-cold** trials, and **loaded prefix-warm** trials. Unloading is not an OS disk-cache flush; label it accurately. An empty preload tests load avoidance, while a real warm-up also exercises kernels and adaptive drafting.
4. Discard warm-up from steady-state summaries, then collect at least five sequential trials per condition. Alternate baseline/candidate order where possible. Show individual timings and medians/ranges; do not claim a universal optimum from one short request. Official MLX's benchmark similarly warms up before repeated timed trials, but its synthetic token workload is supplementary to real tutoring requests. [Official MLX benchmark](https://github.com/ml-explore/mlx-lm/blob/main/mlx_lm/benchmark.py)
5. Use a streaming monotonic clock. Record request start, first nonempty thinking token, first nonempty visible-content token, and final completion separately. Visible-content TTFT includes any preceding thinking; a fast first reasoning token does not establish a fast first displayed answer. Record terminal `load_duration`, `prompt_eval_count`, `prompt_eval_cached_count`, `prompt_eval_duration`, `eval_count`, `eval_duration`, and `done_reason` alongside wall-clock timings. [Ollama chat API](https://docs.ollama.com/api/chat)
6. Compute generation throughput as `eval_count / (eval_duration / 1e9)`. Compute uncached prefill throughput as `(prompt_eval_count - prompt_eval_cached_count) / (prompt_eval_duration / 1e9)`, guarding missing/zero durations. In this version, total prompt count includes cache hits, while prompt duration measures uncached work; dividing the total count by that duration exaggerates cache-hit prefill speed. Retain output token counts, complete answers, schema validity, and memory observations so faster early termination cannot masquerade as a runtime improvement. [Ollama metrics and CLI calculations](https://github.com/ollama/ollama/blob/v0.40.11/api/types.go)

Only adopt a candidate after a repeatable measured gain on its target model and successful tutoring/schema checks. Preserve raw measurements separately from application notes and Obsidian output.

## Measurements on this Mac

These are exploratory sequential tests on the M4 Air, not a causal before/after performance claim. The first phase contains one cold request and two repeated warm requests per model, plus Gemma batch sweeps. The later phase uses the production preload method, one uncached request, then five repeated requests. The benchmark alone uses seed 417, thinking off, and a 220-token cap; production sampling, thinking choices, context, and token limits were not changed. Full payloads and generated text are in [the benchmark evidence](local-ai-benchmark-2026-10-25.json).

| Model | Cold visible TTFT, one trial | Preload wall time | Preloaded first uncached TTFT | Warm repeated TTFT median | Warm output median (range), tokens/s | Valid warm trials |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Qwen 3.5 9B | 13.53s | 8.94s | 6.86s | 0.109s | 17.22 (16.64–20.99) | 5 |
| Gemma 4 26B | 68.84s | 23.45s | 3.64s | 0.199s | 25.64 (24.43–26.16) | 5 |
| Qwen 3.8 27B | 103.31s | 23.28s | 40.17s | 0.714s | 5.44 (4.76–6.03) | 4 |

The repeated requests reuse almost the whole prefix. These small TTFT figures are not predictions for a new question, a different model, a long context, or thinking enabled. Preloading moves model loading earlier; the preload wall time still exists. Warm decoding did not show a causal improvement: the later Qwen 9B and Gemma phase was slower than the earlier phase, and thermal state, memory pressure, output content, and adaptive speculation were not controlled well enough to attribute the difference.

One Qwen 27B request reached the benchmark-only 220-token cap and produced incomplete JSON; it is retained in the raw evidence and excluded from the warm summary. The other 32 requests passed the three numeric/schema checks. These checks do not validate prose: one baseline Qwen 27B explanation incorrectly described a velocity change of 4 m/s instead of 12 m/s while returning the correct numeric acceleration. No general accuracy or unchanged-quality guarantee follows from this probe. Quality preservation here means leaving the model weights and quality-related runtime controls unchanged.

### Applied policies

- Preload only the model for the next task: Mark for long-answer sessions, Explain for other sessions, Ask for chat. Cancel a stale preload when its screen closes or a requested answer needs another model.

- Keep Qwen 9B resident for 30 minutes, Gemma for 15, and Qwen 27B for 10. These are memory/responsiveness policies, not measured optimal durations.

- Use one loaded model and one parallel request in a tutor-owned server, and serialise this client's requests even when using an existing server. The queue-control benefit was not quantified under contention.

- Preserve the native MLX execution and embedded speculative decoding for the Qwens. Preserve Gemma's existing full GPU execution, Flash Attention, f16 KV cache, batch 512, and four CPU threads.

- Retain Gemma batch 512. Batch 128 showed only a small decode gain in one warm trial, with uncached prefill 4.07s versus the baseline 2.66s. Batch 256 and 1024 decoded more slowly. The sweep does not establish a global optimum.

- For this measured workload, Gemma had the fastest warm decoding. Qwen 9B has the smallest memory footprint and fastest repeated-prefix first output. Qwen 27B remains constrained by its large weights on 24 GB. A stronger answer on difficult tutoring questions would require a separate quality evaluation.
