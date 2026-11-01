# Local STEM model specialisation: research and bounded pilot

Date: 2026-10-26. Target: MacBook Air M4, 24 GiB unified memory, 10 CPU / 10 GPU cores. Status: this document records the research-stage recommendations. Subsequent execution is recorded in `docs/benchmarks/2026-10-26-stem-model-pilot/`; statements below about unperformed work refer to the research stage, not the current pilot status.

## Recommendation

Use **Qwen3.5-4B, text only, MLX affine 4-bit LoRA**, as the first candidate. Fine-tune answer organisation, mathematical notation and tutor behaviours in actual adapter weights; retain the app's deterministic renderer and source-backed syllabus context. Begin with native **Thinking Off / On**. Three named reasoning strengths require additional implementation and measurements before being advertised.

This is a feasible experiment, not evidence that the finished model will beat the existing models. Promotion depends on held-out STEM accuracy, marking fidelity, formatting and measured latency. The 2B variant is the memory/speed fallback; 9B is a later quality challenger. Do not begin with full fine-tuning, cross-family merging or pruning.

Exact candidate identity:

- Official upstream: [`Qwen/Qwen3.5-4B`](https://huggingface.co/Qwen/Qwen3.5-4B/tree/851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a), revision `851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a`.
- Proposed quantised training snapshot: [`mlx-community/Qwen3.5-4B-4bit`](https://huggingface.co/mlx-community/Qwen3.5-4B-4bit/tree/0e7ffd5c629ef7719d4cbc04069232580bfa9d9c), revision `0e7ffd5c629ef7719d4cbc04069232580bfa9d9c`.
- Runtime already on SSD: `/Volumes/External SSD TB4/LocalAI/tutor-runtime/mlx/.venv/bin/python`; MLX `0.32.3`, MLX-LM `0.32.2`, Transformers `5.20.2`.
- Quantisation config verified through HF metadata: affine, 4 bits, group size 64. It is **not** bitsandbytes NF4, NVFP4, MXFP4 or GGUF.

The community snapshot has no README/license metadata in this revision. Upstream identifies Apache 2.0; retain its LICENSE/attribution and record the source and conversion provenance. For the cleanest provenance, an alternative is converting the pinned official checkpoint locally into an independently recorded MLX snapshot; that needs a larger download and a separate conversion stage. Neither path has been executed. The [upstream license](https://huggingface.co/Qwen/Qwen3.5-4B/blob/851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a/LICENSE) is the authority, rather than assuming a missing metadata field grants rights.

## What the local source actually supports

LoRA freezes base weights and learns low-rank updates; this changes model behaviour through learned parameters. [LoRA](https://arxiv.org/abs/2106.09685) supports the mechanism, not a guarantee of STEM improvement. [QLoRA](https://arxiv.org/abs/2305.14314) backpropagates through a frozen quantised base into adapters. Its original NF4/double-quantisation/paged-optimizer implementation and CUDA results must not be treated as measured MLX/M4 performance.

Installed source inspection, without importing MLX or loading a model, found:

| File under SSD `site-packages/mlx_lm` | Evidence |
| --- | --- |
| `lora.py`, `tuner/utils.py` | Freezes base; wraps `nn.Linear` / `nn.QuantizedLinear`; accepts explicit layer keys, rank, dropout and **scale**. MLX scale is a direct multiplier; do not copy another framework's `lora_alpha` value blindly. |
| `models/qwen3_5.py` | Native dense Qwen3.5 architecture; exposes decoder layers; `GatedDeltaNet` calls `gated_delta_update(..., use_kernel=not self.training)`, providing a separate training path. |
| `tuner/trainer.py` | Gradient accumulation, checkpointing, validation and adapter saves. Training memory includes logits, activations, gradients and optimizer state, not just checkpoint bytes. |
| `tuner/datasets.py` | JSONL text, prompt/completion and messages; prompt masks for completion/chat. The stock chat path does not supply per-example `enable_thinking` template arguments. |
| `fuse.py`, `tuner/lora.py` | Loads exact base + adapters, adds low-rank update, and can requantise to the original affine type. Native save works; the built-in GGUF export allows only llama/mixtral/mistral, **not Qwen3.5**. |

Primary public counterparts: [Qwen3.5 source](https://github.com/ml-explore/mlx-lm/blob/v0.32.2/mlx_lm/models/qwen3_5.py), [tuner conversion](https://github.com/ml-explore/mlx-lm/blob/v0.32.2/mlx_lm/tuner/utils.py), [training](https://github.com/ml-explore/mlx-lm/blob/v0.32.2/mlx_lm/tuner/trainer.py), [dataset handling](https://github.com/ml-explore/mlx-lm/blob/v0.32.2/mlx_lm/tuner/datasets.py), [fusion](https://github.com/ml-explore/mlx-lm/blob/v0.32.2/mlx_lm/fuse.py). Installed files remain authoritative if locally modified.

Source compatibility is weaker evidence than a successful backward pass. Before committing to a training job, verify finite loss/gradients, nonzero adapter updates, saved-adapter reload and inference on this exact snapshot. Do not invent a need for architecture patches, or assume none can be required before this smoke test.

Package metadata has `tqdm 4.70.1`, but no `datasets` distribution was found. MLX-LM's train extra requires `datasets` and `tqdm`. Resolve that missing dependency in a pinned SSD training environment when the coordinating agent releases the machine for this bounded pilot; do not upgrade the working inference runtime indiscriminately. [MLX-LM LoRA documentation](https://github.com/ml-explore/mlx-lm/blob/main/mlx_lm/LORA.md) recommends quantisation, small batches, fewer trained layers, shorter sequences and checkpointing to control memory. Its M1 Max example is not a MacBook Air throughput forecast.

## Candidate comparison and pinned metadata

Read-only HF API metadata and `hf download --dry-run` were checked on the date above. Sizes below are safetensors bytes in decimal GB, excluding tokenizer/config and temporary copies; source VLM packages include more than just text weights.

| Candidate | Pinned revision | Weight GB | Decision |
| --- | --- | ---: | --- |
| Qwen3.5-4B official | `851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a` | 9.320 | Upstream reference, Apache 2.0. |
| Qwen3.5-4B MLX 4-bit | `0e7ffd5c629ef7719d4cbc04069232580bfa9d9c` | 3.034 | First pilot; native thinking switch, modest storage, native MLX training code. |
| [Qwen3.5-2B MLX 4-bit](https://huggingface.co/mlx-community/Qwen3.5-2B-4bit/tree/674aaa7240b91e8012fcad5d791b7dfe5ba90207) | `674aaa7240b91e8012fcad5d791b7dfe5ba90207` | 1.722 | Fallback when 4B training or latency fails the resource gate. |
| [Qwen3.5-9B MLX 4-bit](https://huggingface.co/mlx-community/Qwen3.5-9B-4bit/tree/8b2b98c00a6b4d291155e4890773ca8f769aee53) | `8b2b98c00a6b4d291155e4890773ca8f769aee53` | 5.950 | Later challenger; greater activation and sustained-compute cost. |
| [Qwen3-4B-Instruct-2507 MLX 4-bit](https://huggingface.co/mlx-community/Qwen3-4B-Instruct-2507-4bit/tree/50d427756c6b1b2fe0c0a10f67fbda1fc8e82c1b) | `50d427756c6b1b2fe0c0a10f67fbda1fc8e82c1b` | 2.263 | Simple conventional transformer and useful control; official card says **non-thinking only**, so unsuitable for a native reasoning-strength promise. |
| [Original Qwen3-4B MLX 4-bit](https://huggingface.co/mlx-community/Qwen3-4B-4bit/tree/4dcb3d101c2a062e5c1d4bb173588c54ea6c4d25) | `4dcb3d101c2a062e5c1d4bb173588c54ea6c4d25` | 2.263 | Conventional-architecture fallback with genuine Off/On; evaluate rather than assume it beats 3.5. |
| [Qwen2.5-Math-7B-Instruct](https://huggingface.co/Qwen/Qwen2.5-Math-7B-Instruct/tree/ef9926d75ab1d54532f6a30dd5e760355eb9aa4d) | `ef9926d75ab1d54532f6a30dd5e760355eb9aa4d` | 15.231 BF16 | Specialist reference/possible teacher; official card discourages other tasks. A maths specialist is not evidence of chemistry/physics/marking suitability. |
| [Gemma4-E4B-it official](https://huggingface.co/google/gemma-4-E4B-it/tree/ee0ef6023621cff504d758262d4e04895a5af4a2) | `ee0ef6023621cff504d758262d4e04895a5af4a2` | 15.993 BF16 | Retain existing native package as an inference baseline. E4B has about 8B total parameters including embeddings, so it is not a conventional 4B training footprint. Existing NVFP4/draft packaging needs separate training verification. |

Upstream Qwen3.5 is a vision-language model, but MLX-LM's text implementation drops vision tensors during sanitisation. The proposed pilot does not train vision or claim to interpret diagrams. The app's OCR/diagram limitations continue to apply. The [official card](https://huggingface.co/Qwen/Qwen3.5-4B/blob/851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a/README.md) describes its architecture and published benchmarks; those results are not local exam-tutor validation.

Memory inference: a 4-bit 4B base should leave substantially more headroom than a full BF16 9B base, but an 8–14 GiB training peak is only a planning envelope, **not a measured estimate**. At vocabulary 248,320, a single `[1,1024,V]` tensor alone occupies roughly 0.47 GiB in BF16 or 0.95 GiB in FP32; several temporaries can coexist. Profile 512 tokens first. Keep a practical 16 GiB process/device budget on the 24 GiB machine, watch system pressure and swap, and stop rather than relying on SSD swapping to make training fit.

## Genuine reasoning strengths

The pinned [Qwen3.5 tokenizer template](https://huggingface.co/Qwen/Qwen3.5-4B/blob/851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a/tokenizer_config.json) uses `enable_thinking=False` to place a closed empty thinking block before the answer; otherwise it opens `<think>`. The MLX snapshot stores its template separately as `chat_template.jinja`; include it when acquiring the snapshot. The [Qwen3 July Instruct card](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507) explicitly supports only non-thinking. These are different model capabilities despite similar names.

Native Qwen3.5 Off/On is source-verified, not yet inference-verified here. Neither its template nor inspected MLX-LM generation code provides a native low/medium/high reasoning-effort API or a separate hard thinking-token budget. A `max_tokens` setting limits total generation and may consume the answer allowance. The server's `TimeBudget` is scheduling machinery, not reasoning strength.

Proposed product progression:

1. Initially expose **Fast (Thinking Off)** and **Reasoning (Thinking On)**, with actual template and token-counter checks. Preserve model-specific sampling and record it in comparisons.
2. Only introduce **Standard / Deep** after implementing and measuring a real difference: for example, an explicit thinking-token budget that forces a valid transition to final output while reserving answer tokens, or a sequential independent verification pass. Label the latter a two-pass workflow, account for its latency, and avoid claiming native model effort levels.
3. Require the larger budget/pass to improve hard-item accuracy across repeated trials. If it only produces more tokens, keep two modes. Never label a setting “maximum intelligence”.

Training pitfall: the pinned template inserts a thinking block even for a plain final-answer assistant message. Stock ChatDataset prompt masking starts at the generated thinking prefix, so final-only chat examples teach immediate thinking termination. For a format-only pilot, a small standalone dataset wrapper should render the native template but set the loss offset **after the final thinking delimiter**, training only the final answer and EOS. This changes data/loss masking, not architecture or installed packages. Validate actual token boundaries and label counts with the pinned tokenizer. Alternatively, deliberately curate short high-level reasoning targets, record their provenance and evaluate their effect; do not accidentally train empty thoughts. Masking thought targets does not prove reasoning retention—test it.

## Merging, pruning and distillation

**Adapter fusion is the preferred merge.** Add the trained adapter to its exact recorded base. Keep the adapter separately. Requantisation can change answers, so evaluate base+adapter and fused checkpoint separately. Never apply the adapter to the existing Qwen GGUF or an unrelated “4B” checkpoint.

**Compatible task-vector merging is a later ablation.** [TIES](https://arxiv.org/abs/2306.01708) addresses interference between task updates; [DARE](https://arxiv.org/abs/2311.03099) sparsifies and rescales fine-tuning deltas of homologous models. Neither means mixing arbitrary Qwen, Gemma and GPT weights is valid. Require identical ancestor/revision, architecture, tensor semantics/shapes and tokenizer mapping, then compare each specialist and the merge on all subjects. A random delta being removable is not evidence that “irrelevant knowledge” has been deleted. [Mergekit](https://github.com/arcee-ai/mergekit) supplies methods, not universal compatibility or guaranteed gains. Do not install it for the first pilot.

**Pruning is not selective syllabus deletion.** Removing low-importance weights or dimensions does not identify a clean biology/history compartment while preserving chemistry reasoning. Distributed representations, shared linguistic skills and changed numerical conditioning make that assumption unsafe. [Wanda](https://arxiv.org/abs/2306.11695) reports activation/magnitude-based sparsification; ordinary dense kernels still process zero entries. [SliceGPT](https://arxiv.org/abs/2401.15024) physically reduces dimensions on evaluated architectures; it does not establish support for Qwen3.5 Gated DeltaNet or a measured M4 speed-up. Prefer an existing smaller dense checkpoint first. Removing an unused vision tower through the native text loader is separable from deleting selected factual knowledge.

**Distillation can transfer useful behaviours across architectures.** It trains a student from teacher targets rather than averaging incompatible parameters. [Hinton et al.](https://arxiv.org/abs/1503.02531) establish the mechanism; [DeepSeek-R1](https://arxiv.org/abs/2501.12948) demonstrates benefits of transferring reasoning to smaller models in its experiments. For this tutor, first use independently checked short worked answers, uncertainty statements and marking demonstrations. Generated answers need verification; a second model agreeing is insufficient. Do not promise that a small student retains every teacher capability, or spend cloud allowance/generate synthetic corpora without authorization.

## Dataset and evaluation design

The initial objective is reusable tutoring behaviour, not memorising an entire syllabus. Assemble approximately 256 carefully reviewed training examples, 64 development items and a sealed 120-item test: 40 mathematics/further mathematics, 40 physics and 40 chemistry, with marking and explanation tasks in each subject. These are proposed budgets, not existing validated datasets. Reserve additional format-only edge cases and broader non-STEM retention checks.

Training targets should contain: concise key idea, necessary numbered calculations, valid LaTeX with units/significant figures, restrained use of bullets, short paragraphs, correct explanation of the learner's error, and grounded marking criteria. Include ambiguity, insufficient information, incorrect premises, uncertain syllabus claims and deliberate wrong learner answers. Store source/version, board/year, topic, family ID, task, answer verification, license/permission and split in a manifest. Use approved local content and sources with suitable rights; owning an exam PDF is not automatic redistribution permission.

Use exact syllabus/mark-scheme excerpts at inference with identifiers and edition dates. Learn to use and cite provided context; do not substitute weight memorisation for the currently applicable authority. No evidence gathered here establishes that the repo's full content is accurate enough to be training gold without audit.

Split **before augmentation** by original question family, source paper and reasoning template; put numeric substitutions, paraphrases, sibling worked solutions and teacher rewrites in the same split. Keep selected topic families entirely held out to test transfer. Deduplicate normalized text plus symbolic/template similarity. Keep test labels out of generation prompts, training logs and teacher demonstrations. Audit current benchmark prompts against the training set; do not “fix” test failures by putting them in training. Public pretraining contamination cannot be ruled out from closed training inventories; newly authored questions and provenance reduce risk, not eliminate it. [GSM-Symbolic](https://arxiv.org/abs/2410.05229) motivates numerical/distractor robustness tests; [GSM1k](https://arxiv.org/abs/2405.00332) motivates fresh independently authored tests. Neither provides an A-Level gold set.

For each base/adapter/fused candidate test the same prompts, renderer, grounding packet, context and sampling. Measure raw valid format, rendered readability, exact/symbolic/numeric correctness, units, significant figures, marking-point agreement, unsupported claims, refusal/uncertainty and repeated-trial variation. Score final answers independently of formatting; reward no fabricated certainty. Review adjudicated errors against authoritative sources, with humans for ambiguous marking. A model judge alone is not the answer key.

Measure cold load, warm prompt evaluation, first visible answer token (excluding private reasoning), final duration, output/reasoning token counts, memory pressure and sustained multi-request performance. The Air's thermal behaviour makes another Mac's tokens/sec an unreliable forecast.

## Bounded local pilot and promotion

The user's request to try building a custom model authorises a reversible local experiment; this research agent has not started it. After the benchmark finishes and the coordinating agent releases the GPU:

1. Record package versions, snapshot hashes, template hash, data/split hashes, tokenizer and license. Acquire only the pinned model into a new SSD directory. Keep caches, temporary files and checkpoints on the SSD. Install missing train dependencies in a separate pinned SSD environment or carefully locked working environment; do not silently replace the functioning inference stack.
2. Establish native 4B base inference in Off/On on a small development set, including valid structured marking and mathematical notation. A failed base is not fixed by speculative training.
3. Smoke-test 8–16 examples for 5 optimizer updates at 512 tokens, batch 1, LoRA rank 8, scale 2.0, dropout 0, learning rate `1e-5`, last 8 decoder blocks, initially only `mlp.gate_proj`, `mlp.up_proj`, `mlp.down_proj`. This is about 2.26M trainable parameters from the pinned dimensions. Confirm gradients/weight changes, adapter-only save, reload and finite loss. Add checkpointing if required; no architecture patch or full fine-tuning.
4. If the resource gate passes, run at most 100 optimizer updates, maximum one hour wall time, sequence length at most 1024 and gradient accumulation 4. Save checkpoints every 25 updates, inspect development quality, stop on nonfinite values, deteriorating validation, sustained pressure/swap or resource limit. These caps are experiment controls, not convergence estimates. Enforce the wall-time cap with graceful checkpoint preservation. Use a small wrapper for final-only loss masking and to make update-count semantics explicit.
5. Evaluate base and selected adapter on sealed tests only after choosing on development data. Fuse into a **new native MLX directory**, then reload/evaluate it separately. Inspect text-only config/tensor naming before registering. Preserve base, adapter and provenance.
6. Promote an opt-in alias only if the following predeclared gates pass; otherwise retain all evidence and keep the existing model selection. Do not silently replace defaults.

Proposed gates (operating choices, not literature constants): at least 98% raw format validity and 100% schema-valid marking after constrained decoding; no critical new marking errors; total correctness no worse than the same base and at least a 5 percentage-point gain in the intended tutor-behaviour composite; no subject drops exceeding 2 items out of its 40-item test; warm first-answer/total latency no more than 15% worse than the corresponding base mode; resources within the agreed budget; Off/On produces the intended protocol and no internal-thinking leakage. Report paired uncertainty: a 120-item pilot is directional evidence and cannot establish a small reliable superiority margin. Repeated challenge seeds and a larger confirmation set are needed for a strong quality claim.

## App integration and rollback

Preferred deployment experiment: import the fused affine MLX checkpoint under a new Ollama alias, then verify `runner: mlx`, template, quantisation, stream parsing, structured marking, thinking and metrics. Ollama `v0.40.11` has a native [Qwen3.5 model implementation](https://github.com/ollama/ollama/blob/v0.40.11/mlxrunner/model/qwen3_5/qwen3_5.go) and [MLX prequantised import pattern](https://github.com/ollama/ollama/blob/v0.40.11/create/prequant.go), but these do not prove the fused checkpoint's exact tensor naming/config imports correctly. MLX-LM fusion may save text-only names; test registration without modifying existing aliases. Preserve templates and license/provenance; the model is text only despite upstream VLM metadata.

Installed `ollama create --help` confirms `ollama create MODEL -f FILE` and a `--force` flag described as bypassing MLX validation. **Do not use `--force`** for this pilot. The [matching import documentation](https://github.com/ollama/ollama/blob/v0.40.11/docs/import.mdx) supports a Modelfile containing `FROM .` beside the saved safetensors. From that new fused directory, the candidate command is `ollama create stem-tutor-qwen35:pilot -f Modelfile`, without another `--quantize` pass. This command has not been run. Treat successful validated import as a gate before any new-worker implementation. The text-only custom model can reuse the app's existing OCR helper; it does not gain native image reasoning.

If importer compatibility fails, use the SSD MLX-LM loader with a Qwen-capable private worker under the app's existing one-GPU queue. The current `mlx_worker.py` and `mlx_local.py` are fixed to GPT-OSS identity, Harmony and reasoning-effort controls; they cannot be reused unchanged. A Qwen implementation needs its own `<think>` state parser, final-only schema constraints, token limits, cancellation/deadlines and checkpoint identity. Register the custom model in the existing catalogue rather than creating a competing background GPU service. A matching empty preload acknowledgment must remain required before every generation, and switching/training must unload competing GPU users.

Do not use `mlx_lm.fuse --export-gguf` for this architecture. Do not claim a GGUF adapter can be attached to the existing package. Native adapter/fused validation comes first.

Rollback is selecting the previous model and disabling the new alias/receipt; retain immutable original snapshots and adapter. A candidate must never overwrite source models, existing selections or benchmark evidence. Training is an exclusive GPU job and never overlaps inference/benchmarks.

## Evidence boundaries and reproducibility

Facts verified here: named public revisions and file sizes, model-card capability claims, installed source APIs and package metadata, HF dry-run inventory, existing app's fixed GPT-OSS worker contract. Inferences/design choices: candidate ranking, memory envelope, data count, LoRA scope, experiment caps, deployment preference and promotion thresholds. Unverified until pilot: actual backward pass, peak RAM, speed, fusion/import parity, thinking retention and any accuracy improvement.

Installed-source SHA-256 receipts:

```text
models/qwen3_5.py 851449fd9989d6bf4b3c4fed92ddc3be5f1e781eb2246f89c54d7eff2518d9c6
tuner/utils.py f59f3c027176a3975fe60e7fbd9f3f38723c27c3f888cf9e591c103f93f68588
tuner/lora.py 4d3a8edab111d4ddba33398ba8700203db7b61621c39e9c348fdd50e57278b45
tuner/datasets.py dcd675376d68d1813261c8389236b586b16b9a58a5ea80be8eb535bb9d0e9689
fuse.py cf6bed1d41acc2442c4f50d04bc59a3ebc1890bfdbdf18914f480b246221f91c
```

No success claim about a custom model is justified by this research alone.

## Native Ollama sampling support: source check

Follow-up on 2026-10-26, source only. Ollama `v0.40.11` resolves to commit `675150d6ad2747df1e218ef59de9194bc4a7e538`. The coordinating agent is probing publisher-recommended Python MLX samplers; this section records compatibility, **not successful inference or quality results**.

[`mlxrunner/server.go:140–153`](https://github.com/ollama/ollama/blob/675150d6ad2747df1e218ef59de9194bc4a7e538/mlxrunner/server.go#L140) copies the actual request options into its native sampler: temperature, top-p, min-p, top-k, repeat-last-N, repetition/presence/frequency penalties and seed. Presence penalty and top-k are therefore implemented in the native MLX path, rather than merely accepted API fields.

The [native sampler](https://github.com/ollama/ollama/blob/675150d6ad2747df1e218ef59de9194bc4a7e538/mlxrunner/sample/sample.go#L226) uses `repeat_last_n` as the shared history span for all penalties. Zero disables **all** penalties, including presence; negative resolves to the native architectural context. Set an explicit positive span, e.g. **1024**, to correspond to the Python probe's `presence_context_size=1024`. Prompt tokens seed the ring and generated thinking/final tokens advance it. There is no final-only or thinking-only penalty scope. In `penalty` (line 897), presence subtracts its coefficient once from each present token's logit, independently of occurrence count; frequency penalty is separate. For positive temperature and valid top-k, the native sequence is penalties → top-k → temperature/softmax → top-p → min-p → renormalisation. At temperature zero it uses penalty-adjusted argmax. These are source facts, not evidence of better answers.

[API defaults](https://github.com/ollama/ollama/blob/675150d6ad2747df1e218ef59de9194bc4a7e538/api/types.go#L1224) are `repeat_last_n=64`, presence/frequency zero and repetition one. Sending only `presence_penalty=1.5` therefore does **not** reproduce a 1024-token Python presence window. The native [sampler tests](https://github.com/ollama/ollama/blob/675150d6ad2747df1e218ef59de9194bc4a7e538/mlxrunner/sample/sample_test.go#L62) cover presence, top-k, zero disabling penalties and negative-window resolution; they were inspected, not executed here.

The installed [MLX-LM sampling utility](https://github.com/ml-explore/mlx-lm/blob/v0.32.2/mlx_lm/sample_utils.py#L14) differs: its sampler filters top-p/min-p before top-k and applies temperature at categorical sampling; `make_logits_processors` separately constructs presence with its own span. Thus matching scalar settings and history span across the two engines does **not** establish identical sampling distributions or seeded output. A Python success must be followed by a native Ollama probe on the imported checkpoint.

Proposed native request options for the bounded comparison (the official recommendation is the baseline; the 1024-token penalty span is our explicit experimental choice):

| Mode | Native thinking | temperature | top_p | top_k | min_p | presence_penalty | repeat_penalty | repeat_last_n |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Fast | Off | 0.7 | 0.8 | 20 | 0 | 1.5 | 1 | 1024 |
| Deep | On | 1.0 | 0.95 | 20 | 0 | 1.5 | 1 | 1024 |

Use the same custom alias with mode-specific **request options**, rather than assuming the boolean thinking field changes sampling automatically. A Modelfile can supply one default set; it does not establish both mode presets. Include the entire resolved sampler in benchmark receipts and cache identities, enforce genuine thinking transitions and separate final-answer completion from budget exhaustion. Preserve original model samplers. Promote either setting only after actual native completion, STEM correctness, marking, latency and repetition measurements; a finite stream consisting entirely of thinking is a failed answer.
