# MLX models and local reasoning strengths

Measured on 25 October 2026, with final regression verification on 26 October: M4 MacBook Air, 10 CPU/10 GPU cores, 24 GiB unified memory. Version remains 2.6.0. These small application-level tests do not establish universal speed or accuracy gains.

## Installed choices

| Model | Tutor choice | Execution |
|---|---|---|
| Gemma 4 26B | `ollama:gemma4:26b-tutor-mlx` | Ollama MLX; QAT affine 4-bit and the source's 120 eight-bit overrides |
| Gemma 4 E4B | `ollama:gemma4:e4b` | Existing MLX NVFP4 package and embedded draft |
| Qwen 3.8 27B | `ollama:qwen3.8:27b` | Existing MLX NVFP4 package |
| GPT-OSS 20B | `mlx:gpt-oss:20b` | Private MLX-LM worker; original MXFP4 experts and BF16 remaining tensors |

Live scheduler readings reported `runner: mlx` for all three Ollama choices. GPT-OSS loaded through MLX-LM on Metal and completed production chat and structured requests. E4B and Qwen already used MLX; their unchanged backends are controls, not migration gains.

All weights and the isolated environment are under `/Volumes/External SSD TB4/LocalAI`. Original GGUF Gemma/GPT choices remain available. LM Studio settings and model registration are unchanged. Only the active large runtime stays loaded.

## Response times

The baseline preceded installation and product changes. Tests used current tutor prompts, strict reply/speech envelopes, exact marking labels, native sampling, matching synthetic questions, and no added answer-token cap. GPU work ran sequentially with the test suite stopped. Each question had fresh conversation history and loaded weights. Response wall time includes per-request preload; initial preparation is separate in the evidence.

| Workload | Before | MLX | Interpretation |
|---|---:|---:|---|
| Gemma marking, 12 cases | Median **4.82 s**, range 4.12–5.65 | Median **4.09 s**, range 3.51–11.25 | About **15% lower median**; 12/12 expected decisions in each arm |
| Gemma first visible chat text, 9 replies | Median **1.90 s** | Median **0.30 s** | Earlier display; some replies remained incomplete |
| GPT High, acceleration | **249.88 s** | **64.52 s** | One matched trial per arm |
| GPT High, gradient | **109.25 s** | **90.49 s** | One matched trial per arm |
| GPT High, catalyst | **300 s timeout** | **199.87 s** | No measured baseline completion |

Gemma's first native mark took 11.25 s despite loaded weights. Preloading does not eliminate first-use kernels, prompt processing, or thinking. Initial native Gemma preparation took 16.10 s; a separate evaluated-weight GPT preparation smoke took 16.80 s. OS disk caching and thermal state were uncontrolled.

GPT Low did **not** become universally faster. Successful ordinary replies had a 9.38 s baseline median (only 4/9 valid envelopes) and 13.38 s native median (9/9 valid envelopes). Different survivors prevent a fair overall speed ratio. The matched catalyst question had an 8.18 s baseline median versus 9.85 s native across three trials. The private worker currently uses a fresh prompt cache per request, so prefill remains part of latency.

Native Medium's three ordinary replies took **14.15–21.53 s**; High took **64.52–199.87 s**. E4B's unchanged control took **5.01–9.48 s**. Qwen Low/Medium returned a one-sentence alkane formula in **38.93/37.37 s**; those narrow smokes are not comparable with the longer workloads.

Different quantization representations, stochastic output lengths, templates/caches, trial order and thermal conditions limit causal claims. Gemma compares a GGUF Q4_0 package with a mixed-precision MLX QAT package, not identical quantization in two engines.

## Quality audit

JSON validity is not answer quality. Native Gemma matched all twelve expected marking decisions, but ended two catalyst explanations mid-sentence. The baseline ended all three gradient explanations mid-sentence. Those short replies are failed completeness samples, not faster complete answers.

GPT Low's initial native run produced nine valid ordinary envelopes, but one contained NUL characters; a separate speech case contained ESC characters in visual units. These remain failed readability samples. Final guards reject unsafe decoded reply controls before display/history; residual terminal controls receive labelled, JSON-escaped exact-source fallback. Do not relabel old failures as quality passes after the guard change.

Factual errors persisted: a GPT Low reply reversed negative-gradient direction; some catalyst replies confused equilibrium composition with a ratio of reaction rates; one High reply misquoted the learner's units. E4B also made contextual physics/chemistry errors. Equilibrium depends on standard reaction Gibbs energy, not enthalpy alone. [IUPAC definition](https://goldbook.iupac.org/terms/view/S05915)

Some replies still require labelled fallback for malformed/unsupported notation. Preserving source precision and sampling does not prove unchanged teaching accuracy across quantizations or establish exam-authority accuracy.

An initial Medium speech trial failed on oversized Harmony metadata. Final header constraints prevent invalid protocol headers while leaving reasoning bodies and answer sampling intact. The post-hardening Medium speech check passed in 39.99 s. Final Low, High, E4B thinking and Qwen Maximum checks also passed; these compatibility checks are separate from the original speed comparison.

## Settings and presets

Restart the tutor, open **F2 Settings**, preview a preset, press **Apply**, then **Save**. Existing custom choices remain authoritative; reapply a preset to adopt its MLX selections. Local lists detect SSD insertion after launch and preserve saved disconnected choices.

| Local preset | Marking | Explaining and asking |
|---|---|---|
| Careful marking | Gemma 26B MLX, Off | Gemma 26B MLX, Off |
| Fast tutoring | Gemma 26B MLX, Off | E4B MLX, Off |
| Text reasoning | Gemma 26B MLX, Off | GPT-OSS MLX, Low |
| Medium reasoning | Gemma 26B MLX, Off | GPT-OSS MLX, Medium |
| Extended reasoning | Gemma 26B MLX, Off | GPT-OSS MLX, High |

All four Claude/ChatGPT presets and original boolean controls remain unchanged. Presets alter only task models/thinking, leaving web, speech, session length and resource display independent.

GPT offers **Low/Medium/High**, with no false Off choice. Qwen offers **Off/Low/Medium/Maximum**, with Maximum mapped to native `xhigh`. Gemma keeps Off/On. Old GPT switches map to Low/High; old Qwen On maps to Maximum. Strengths have separate histories/cache identities. Maximum effort can take minutes.

## Installation and isolation

- GPT: `models/openai/gpt-oss-20b`, revision `6cee5e81ee83917806bbde320786a8fb61efebee`. Ten required files passed Hugging Face checksum verification.
- Runtime: `tutor-runtime/mlx/.venv`; MLX 0.32.3, MLX-LM 0.32.2, Outlines 1.3.3, llguidance 1.9.1, Transformers 5.20.2. `pip check` passed.
- Receipt: `tutor-runtime/mlx/gpt-oss-20b.json`. Discovery checks revision, files/sizes and runtime. Hugging Face, Outlines, Python and temporary caches stay on the SSD; the owned worker uses Hugging Face offline mode.
- Gemma source: existing `LMStudioModels/lmstudio-community/gemma-4-26B-A4B-it-QAT-MLX-4bit`, revision `aa5e2e50376f54254d503276ca2222ea8569b95e`. Imported tensors are independent in the Ollama blob store.
- Ollama's importer accepted Gemma's architecture but missed its expert layout and eight-bit overrides. `PYTHONPATH=app .venv/bin/python -m tutor_app.mlx_gemma_import` is a zero-write dry run; `--apply` repairs the fixed alias. It verifies affected input hashes, rearranges expert bytes without numeric conversion, fixes precision metadata and atomically publishes a new immutable manifest. Source and other models remain intact; original manifest/link backups live under `tutor-runtime/mlx`.

GPT uses owned private pipes, with no exposed server or LM Studio dependency. Every question needs a fresh single-use preload acknowledgment bound to the exact child, epoch and checkpoint. A replacement child cannot receive the question without fresh readiness. Idle resets preserve weights while clearing conversation/answer caches; active resets cancel unfinished work. Runtime switching releases the tutor's prepared model while preserving unrelated models/externally owned servers.

The Ollama window can be closed; the tutor starts its service when needed. GPT uses its independent worker. Native images, text-only OCR and host web retrieval follow existing paths. Native Gemma correctly read the synthetic printed number 42 from an image. This establishes input compatibility, not graph-geometry accuracy.

## Verification

On 26 October, the complete suite passed **4,178 tests** with 28 existing warnings in 144.24 s:

```bash
PYTHONPATH=tests/app .venv/bin/python -m pytest tests --import-mode=importlib -n 4 --dist=loadscope -q
```

A subsequent label/description-only update passed 59 catalogue, preset and compact-layout tests. Settings screenshots were checked at 60/80/100 columns. Standards and Spec reviews have zero unresolved findings; the final control-preservation review was also resolved. The isolated runtime passes `pip check`. No actual Claude or ChatGPT requests were used for verification.

## Evidence and sources

[Combined measurements](benchmarks/2026-10-25-mlx-comparison.json) retain synthetic payloads, visible answers, counters, failed probes, final checks and installation metadata. Hidden reasoning is not recorded. Working artifacts also remain in `LocalAI/tutor-benchmarks/2026-10-25-mlx-migration`.

- [Native MLX loading of original GPT-OSS](https://huggingface.co/docs/transformers/en/community_integrations/mlx)
- [Native Gemma implementation](https://github.com/ollama/ollama/blob/v0.40.11/mlxrunner/model/gemma4/gemma4.go)
- [Ollama prequantized import](https://github.com/ollama/ollama/blob/v0.40.11/create/prequant.go)
- [Native thinking controls](https://docs.ollama.com/capabilities/thinking)
- [Installed MLX-LM generation API](https://github.com/ml-explore/mlx-lm/blob/v0.32.2/mlx_lm/generate.py)
- [Harmony framing](https://github.com/openai/harmony/blob/main/docs/format.md)
- [Outlines MLX integration](https://dottxt-ai.github.io/outlines/latest/features/models/mlxlm/)
