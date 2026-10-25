# End-to-end local AI latency research

Researched 2026-10-25 for the M4 MacBook Air with 24 GiB unified memory, installed Ollama 0.40.11, and weights in `/Volumes/External SSD TB4/LocalAI`. The primary-source review is followed by a separate exploratory preload probe and implementation notes. No model downloads or service-wide runtime changes were needed.

The highest-confidence approach is to load the next selected model while the learner reads, retain it across related tasks, and reuse its unchanged prompt prefixes. Those mechanisms already exist in the tutor. This change improves preparation timing and overlaps independent work. Switching to another application or reducing reasoning is a separate experiment, not an established improvement with unchanged tutoring quality.

## Evidence and the existing baseline

Three kinds of evidence must remain separate:

| Evidence | What it establishes | Limit |
| --- | --- | --- |
| Existing [performance measurements](LOCAL_AI_PERFORMANCE.md) and [raw trials](local-ai-benchmark-2026-10-25.json) | Loading and prefix processing contributed materially to waits on this Mac | Exploratory trials; different workloads, power/thermal state and output lengths prevent a universal ranking |
| Installed-version upstream source linked below | What the public Ollama 0.40.11 implementation does | The locally installed binary can differ; logs and protocol behavior remain authoritative |
| Current LM Studio, MLX LM and llama.cpp documentation | Available mechanisms and candidate experiments | Not proof those controls exist in Ollama or are faster on this machine |

The existing measurements include Qwen 9B/Gemma 26B/Qwen 27B cold visible first-token waits of 13.53/68.84/103.31 seconds, one trial each. A later empty-preload phase took 8.94/23.45/23.28 seconds to preload, followed by uncached visible first-token waits of 6.86/3.64/40.17 seconds. Repeated nearly identical warm requests had much smaller waits. These were separate phases, not matched pairs from which to subtract a causal speedup. See the full limitations in [the measurement note](LOCAL_AI_PERFORMANCE.md).

Inspection found empty-message preloading and a common request queue in `app/tutor_app/local_ai.py`; load-context preparation is shared by preloads and real requests. `app/tutor_app/local_models.py` already specifies 30-minute Qwen 9B, 15-minute Gemma 26B, 10-minute Qwen 27B, and 45-minute small-model retention. Most GGUF models start at 8,192 tokens and can retain a 16,384-token recovery context. The Qwen MLX paths use their native context policy. These are current implementation observations, not newly applied recommendations. Claude and Codex routing must remain unchanged.

## Where the wait comes from

Useful wall-clock landmarks are submission, completion of local image preparation, queue acquisition, first backend token, first visible answer text, and successful completion. Loading, uncached prompt processing, hidden reasoning, visible decoding and final schema validation can all affect the experience. Backend durations do not necessarily partition all client work, so do not sum them and label the result end-to-end latency.

Ollama exposes load, prompt and generation timings, prompt/cache token counts and a completion reason. Its prompt duration covers uncached evaluation. Measure visible first-token time with a client clock: the first reasoning token is not the first answer shown to the learner. [Chat API metrics](https://docs.ollama.com/api/chat)

## Ollama: load ahead, preserve residency, reuse prefixes

An empty `/api/chat` or `/api/generate` request is the documented preload mechanism. `keep_alive` controls idle residency; a negative value requests indefinite retention and zero releases the model. A request value overrides `OLLAMA_KEEP_ALIVE`. Parallel contexts consume additional memory; retaining one selected model is a sensible policy for these weights and 24 GiB, rather than loading the full model catalogue. Flash Attention is automatic when supported. Quantizing the KV cache trades precision for memory, so retain the existing f16 cache for this quality-preserving task. [Ollama FAQ](https://docs.ollama.com/faq)

The 0.40.11 chat handler schedules the runner first, then returns a completed response with `done_reason: load` when messages are empty. It does not run a synthetic tutoring answer. Thus an empty preload avoids future model loading but does not evaluate the tutor system prompt, compile every request-specific schema, or remove hidden reasoning from the next real answer. Do not claim that an empty preload makes a new question equivalent to a repeated prompt. [Versioned chat handler](https://github.com/ollama/ollama/blob/v0.40.11/server/routes.go#L3008-L3025)

For GGUF runners, changing load options can cause a reload even when the model name is unchanged. The scheduler compares effective runner options, including context length, with allowances for automatically chosen settings. Use the same context and other load settings for preload and inference; after context recovery, retain the larger context for subsequent preload requests. MLX is an explicit exception to this runner-option comparison. [Versioned scheduler](https://github.com/ollama/ollama/blob/v0.40.11/server/sched.go#L1328-L1376)

The MLX runner initializes its context from the model's native maximum. Do not assume a generic Ollama `num_ctx` recommendation applies identically to MLX and GGUF. It also discovers embedded draft heads while loading. [Versioned MLX loading](https://github.com/ollama/ollama/blob/v0.40.11/mlxrunner/runner.go#L102-L138)

MLX maintains a token-prefix trie with reusable cache states across requests. It restores a matching prefix and evaluates at least a seed token before decoding. The 8 GiB paged-out-cache constant is an eviction threshold, not an upfront allocation or reserved memory. Preserve identical system text, chat formatting and conversation prefixes; changing early text can prevent later tokens from matching. Cache reuse avoids recomputation, not the model's examination of the retained context. [Versioned MLX prefix cache](https://github.com/ollama/ollama/blob/v0.40.11/mlxrunner/prefix_cache.go)

The inspected MLX pipeline serializes requests and uses a fixed 2,048-token prefill chunk. Its prompt preparation limits generation to remaining native context capacity. General `num_batch` or thread-tuning advice is not evidence that these controls adjust this pipeline. [Versioned MLX pipeline](https://github.com/ollama/ollama/blob/v0.40.11/mlxrunner/pipeline.go)

## Speculative decoding and engine alternatives

The Qwen MLX backend may already perform embedded speculation. Its target validates proposed tokens with rejection sampling and a residual distribution; its controller learns draft depth across requests. This is designed to retain the target sampling distribution, but does not promise identical seeded strings or identical floating-point execution. Longer drafts are not automatically faster: drafting, validation and rejected proposals all cost time. Keep the existing automatic path unless a controlled benchmark demonstrates a useful change. [Versioned speculation](https://github.com/ollama/ollama/blob/v0.40.11/mlxrunner/speculate.go), [adaptive depth controller](https://github.com/ollama/ollama/blob/v0.40.11/mlxrunner/speculate_depth.go)

The versioned Modelfile reference describes `draft_num_predict`, including manually enabling embedded MTP. The inspected MLX loader and controller use a different enablement path. A Modelfile parameter's presence or absence therefore does not prove whether a particular MLX run is using speculation. Confirm backend logs before proposing a switch. [Modelfile parameter reference](https://github.com/ollama/ollama/blob/v0.40.11/docs/modelfile.mdx#L141)

Standalone llama.cpp supports matching-prefix KV reuse through `cache_prompt`; its documentation warns that different batching can produce numerically different logits. Current `llama-server` also exposes cache-memory, chunk-reuse and speculative-draft controls. These are capabilities of that server, not established flags accepted by the tutor's Ollama endpoint. Do not pass them through blindly or start an extra server alongside active inference. [Current llama.cpp server reference](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md)

MLX LM supports reusable prompt caches and configurable prefill steps. Smaller steps reduce peak memory at a prompt-processing cost. Its rotating KV-cache option can worsen quality when made small. A file cache can preserve a known prefix between runs, but requires correct model/template identity and introduces stored learner-context handling. The tutor already benefits from Ollama's in-memory MLX cache, so an MLX LM migration is not justified merely to obtain prompt caching. [Official MLX LM README](https://github.com/ml-explore/mlx-lm#long-prompts-and-generations)

LM Studio explicitly loads models with `lms load`, supports idle TTL and context length, and can estimate memory without loading. Its REST load endpoint exposes context, Flash Attention and batch configuration, some specific to its llama.cpp engine. These provide comparable load-ahead controls; documentation alone does not establish faster inference for the installed weights on this M4. [LM Studio CLI load](https://lmstudio.ai/docs/cli/local-models/load), [REST load API](https://lmstudio.ai/docs/developer/rest/load)

LM Studio's JIT models have a documented default 60-minute idle TTL. Auto-Evict keeps at most one JIT-loaded model and leaves manually loaded models unaffected. Manual CLI loads have no TTL unless one is specified. An integration that manually preloads models therefore needs its own explicit unload policy rather than assuming JIT eviction applies. [LM Studio residency rules](https://lmstudio.ai/docs/developer/core/ttl-and-auto-evict)

LM Studio supports draft models through its Python prediction configuration. The vendor's 2025 launch article claims 1.5–3× generation gains in some cases and checks model compatibility; this is a vendor claim, not a benchmark of this tutor. A second model also requires memory and loading. No new draft package or runtime migration is recommended on that evidence. [Python speculative API](https://lmstudio.ai/docs/python/llm-prediction/speculative-decoding), [vendor launch claim](https://lmstudio.ai/blog/lmstudio-v0.3.10)

## Modest changes worth implementing or retaining

1. **Warm the next real local task early.** Start once its selected model is known, including Ask/chat and a restored session. Let reading and typing overlap the load. Skip Claude/Codex selections. A single empty-message request should carry the same load options and keep-alive policy as the real request.
2. **Avoid stale preload interference.** A submitted answer should supersede queued speculative loading for another model. Screen closure, task changes and Settings cancellation should invalidate stale work. Cancellation must not corrupt answer history or metrics. Preloading can still occupy the runner briefly; do not advertise instant cancellation without observing backend behavior.
3. **Keep residency bounded and model switches visible.** Retain the existing per-model durations initially. They are policies, not measured optima. An all-Gemma task setup avoids task-to-task reloads when suitable; automatically changing the learner's selected model to obtain that benefit would change task behavior.
4. **Preserve exact prompts.** Reuse existing prefix construction and successful structured-result caching. Do not remove history, rubric text, image evidence or reasoning budgets to manufacture lower latency. Do not run a synthetic answer solely to populate a cache without proving its benefit and bounded cost.
5. **Measure readiness and waits honestly.** Record preload start/end, model/context identity and whether a submitted task waited for it. `GET /api/ps` can report loaded model, expiry and context information; inspection is useful for diagnosis, but repeated polling does not itself keep a model warm. [Running-model API](https://docs.ollama.com/api/ps)
6. **Defer broad runtime tuning.** Preserve full GPU execution, existing Flash Attention, quantization, sampling, thinking choices and output budgets. Existing Gemma batch sweeps did not establish a better global setting. Benchmark an alternative engine separately only when the current path has a measured remaining bottleneck.

Do not extend residency by repeatedly sending work forever. Do not change system wired-memory limits as a routine application optimization. Do not preload several large models to avoid switching on a 24 GiB machine. These are engineering recommendations from the memory and lifecycle constraints, not measured claims about an optimal TTL or memory threshold.

## Acceptance and measurement protocol

Use complete real tutor payloads for explanation, schema marking and multi-turn chat. Hold model digest, prompt/history/images, schema, context, sampling, thinking and output budget fixed. Separate runner-cold, loaded with a new prefix, and loaded with a reused prefix. A runner unload is not a disk-cache flush. Compare five or more sequential observations per condition, alternate test order, and record power state, memory pressure/swap and thermal conditions. Avoid concurrent local inference.

Measure submission-to-visible-answer and submission-to-valid-completion, including OCR, queueing and retries. Record load/prompt/generation counters, cache hits, completion reason, output length and schema/answer correctness. Report individual trials plus median and spread. Empty, truncated, malformed or substantively incorrect answers do not count as successful fast results. Keep reasoning-on and reasoning-off results separate.

Compute decoding throughput as `eval_count / (eval_duration / 1e9)`. For this version, compute prefill throughput using uncached tokens, `(prompt_eval_count - prompt_eval_cached_count) / (prompt_eval_duration / 1e9)`, with missing/zero-value guards. Ollama's own CLI uses that subtraction. A total-token numerator on a cache hit exaggerates actual prefill work. [Versioned metric calculations](https://github.com/ollama/ollama/blob/v0.40.11/api/types.go#L995-L1025)

Adopt only changes that reduce the intended wall-clock wait without increasing failures, losing context or changing provider behavior. A faster first visible token and a faster completed answer are separate outcomes; report both.

## New exploratory preload probe

The [sanitized measurements](benchmarks/2026-10-25-local-latency.json) contain one runner-cold request, one empty
preload after unloading that runner, and the identical request after preloading for each original model. The production
system prompt asks for acceleration from a velocity change. Thinking is off in both phases, model sampling defaults
are unchanged, and no output cap or seed is imposed. The runner is absent before each cold request and preload.
Filesystem cache, thermal state, memory pressure and stochastic response length are not controlled.

| Model | Cold first visible answer | Preload itself | First visible answer after preload | Cold completion | Completion after preload |
| --- | ---: | ---: | ---: | ---: | ---: |
| Qwen 3.5 9B | 11.28 s | 4.72 s | 1.46 s | 12.58 s | 4.50 s |
| Gemma 4 26B | 24.73 s | 2.09 s | 0.78 s | 27.43 s | 4.37 s |
| Qwen 3.8 27B | 37.99 s | 23.52 s | 15.88 s | 41.74 s | 18.46 s |

Preload time is excluded from the post-preload request columns and still exists. For Qwen 27B, preload plus answer
takes about 41.98 s versus 41.74 s cold. This illustrates moving work into reading time, not making the full work
cheaper. Its prompt processing still takes about 15.44 s after preloading. The large Gemma load-time difference
between phases must not be attributed solely to preloading because filesystem cache was not flushed.

Both Qwen models return the correct acceleration, 2 m/s². Qwen 9B adds more prose in the preloaded phase. Gemma
gives the correct method but follows the tutor's guiding-question policy and withholds the requested numeric final
answer in both phases. These six responses are a latency smoke check, not evidence of general answer quality or a
controlled model ranking. They do not quantify the new OCR/web overlap or composer lifecycle changes.

## Applied local-only changes

- The session Ask composer starts the existing selected-model preload while the learner types. Send retains its
  ownership for the underlying study screen; Esc, empty input and screen closure cancel obsolete preparation.
- Native macOS text OCR and an empty model preload may run together. They use independent CPU and inference
  resources. A generative vision helper runs before the tutor model so two models do not compete for memory.
- Explicit web retrieval can run while its local model loads. It still sends only the typed query. Existing active
  inference/preloading takes precedence. The required-readiness update below adds a preflight for every generation.
- Speculative preparation tasks are joined on success, failure and cancellation. Existing reset epochs reject stale
  observations and search results. No speculative answer is generated and no cloud request is added.
- An exact image-observation cache hit does not start foreground loading. A matching cached structured answer
  therefore returns without loading an evicted runner. Background preparation still queues its selected model when
  active inference prevented overlap, and remains cancellable through the existing screen owner.
- Whole-call local timing includes image preparation, loading and reply-cache queue waits. Concurrent preparation
  is counted once. Search timing excludes time spent waiting for model loading. Reused structured answers retain
  their actual caller wait instead of reporting a zero-second response after waiting for another request.

No model selections, prompts, history, thinking flags, output budgets, weights, sampling, precision or cloud provider
branches change. No additional open-source server is installed: Ollama already supplies the relevant load, cache and
native speculation mechanisms. The remaining large delays are model/prompt processing and selected reasoning;
automatically reducing either would require a separate quality tradeoff.

## Required readiness before every local generation

The learner subsequently requested that no local generation begin without preloading. Every attempt now sends an
empty chat request and requires `done: true`, `done_reason: "load"`, with no reply or reasoning text. The preload
uses exactly the generation's selected model, load options and keep-alive. Generation follows immediately under
the same client inference lock and absolute deadline. Context recovery repeats this gate with its larger window.
Failed or incomplete acknowledgments stop the request; reset, close, cancellation and drive checks remain active.
Cached successful structured answers bypass this path because no new generation is required.

This costs one local HTTP request even when a runner is already warm. It is intentionally stricter than trusting
a timestamp or checking `/api/ps`: that endpoint is only a snapshot and may include runners that are still loading.
The empty-chat handler schedules the model and returns before building or evaluating a tutor prompt; runner reuse
checks compatibility and health. Thus this gate adds no synthetic answer or token budget change. [Versioned chat
handler](https://github.com/ollama/ollama/blob/v0.40.11/server/routes.go#L3210-L3232), [readiness acknowledgment](https://github.com/ollama/ollama/blob/v0.40.11/server/sched.go#L785-L805),
[runner reuse](https://github.com/ollama/ollama/blob/v0.40.11/server/sched.go#L1423-L1474),
[running-model snapshot](https://github.com/ollama/ollama/blob/v0.40.11/server/sched.go#L1805-L1848).

The enforceable guarantee is **no generating tutor request before a successful matching preload**. Ollama does not
pass an atomic residency lease between two HTTP calls. The client lock excludes this tutor's other inference tasks;
an external client, forced unload, service restart or scheduler pressure can still intervene. Keeping all three large
role models resident simultaneously on 24 GiB is not assumed. [Reference lifecycle](https://github.com/ollama/ollama/blob/v0.40.11/server/sched.go#L518-L534),
[scheduler eviction](https://github.com/ollama/ollama/blob/v0.40.11/server/sched.go#L379-L400).

Short and structured questions also prepare their Mark model while the learner reads. The initial session no longer
overwrites that choice with Explain. Actual request timing includes the preflight, and terminal statistics separate
its wall duration from the final generating request's engine load duration. A new live measurement was skipped
because GPT-OSS was already resident; [the skip record](benchmarks/2026-10-25-local-readiness.json) contains no new
inference timings. Offline wire tests exercise all sixteen model IDs and both text/JSON routes, plus failure, context
recovery, cancellation, queue ordering and cache behavior. The earlier timing tables remain exploratory observations
from before this strict gate; they do not measure its warm round-trip overhead.
