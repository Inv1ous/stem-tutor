# Local STEM models and presets

Measured on 25 October 2026 on this learner's M4 MacBook Air, 24 GiB unified RAM, with Ollama 0.40.11.
All downloaded weights and manifests are in `/Volumes/External SSD TB4/LocalAI`; the original three models remain installed.
Thirteen additional packages originally brought the total to sixteen models. Two explicit MLX Gemma/GPT choices now
coexist with their originals. See [MLX models and local strengths](LOCAL_MLX_COMPARISON.md) for current measurements.

## Choose a setup

Open Settings with F2, select an AI preset, inspect the three task rows, press **Apply**, then **Save**.
Apply changes only the open dialog. Esc cancels. Presets change exactly the marking, explaining and asking models
and their three thinking choices. They do not change web access, session length, resource display or other settings.
Manual task edits show Custom. Local presets require every model they select to be installed on the connected SSD.

| Preset | Marking | Explaining and asking | Thinking |
|---|---|---|---|
| Claude: fast | Haiku | Haiku | Off |
| Claude: balanced | Sonnet | Sonnet | Off |
| ChatGPT: fast | GPT-6-Luna | GPT-6-Luna | Low |
| ChatGPT: strong | GPT-6.1-Sol | GPT-6.1-Sol | Low |
| Local: careful marking | Gemma 4 26B MLX | Gemma 4 26B MLX | Off |
| Local: fast tutoring | Gemma 4 26B MLX | Gemma 4 E4B MLX | Off |
| Local: text reasoning | Gemma 4 26B MLX | GPT-OSS 20B MLX | Marking off; tutoring low |
| Local: medium reasoning | Gemma 4 26B MLX | GPT-OSS 20B MLX | Marking off; tutoring medium |
| Local: extended reasoning | Gemma 4 26B MLX | GPT-OSS 20B MLX | Marking off; tutoring high |

Start with **Local: careful marking** for a steady session without model switches. Choose **Local: fast tutoring**
for frequent explanations. GPT-OSS is a useful text reasoning alternative, with the image limitations below.
The original audit below did not time High GPT reasoning. The later [MLX comparison](LOCAL_MLX_COMPARISON.md)
includes Low/Medium/High and confirms substantially longer High responses.
Claude and ChatGPT keep their existing provider paths and limits; local preparation is not run for their requests.

## First candidate audit

Eight additional packages were installed: Qwen 3.5 2B/4B, Gemma 4 E2B/E4B, Ministral 3 3B, Phi-4-mini 3.8B,
GPT-OSS 20B and Granite 3.2 Vision 2B. Granite was evaluated as an image observer; the other seven were compared with
the existing Gemma 26B control on full synthetic mathematics, physics and chemistry requests.

Each general model completed one cold marking request, twelve warm marking cases and three tutoring questions:
128 complete baseline responses in total. Requests used the production tutor brief, context builder, rubric and
original JSON schema, 8,192-token context, native sampling and no output token cap. Thinking was off where supported,
omitted where unsupported, and low for GPT-OSS. These are complete response times, not first-token measurements.

| Model | Accepted exact cases | Cold marking | Warm marking median / maximum | Maximum tutoring |
|---|---:|---:|---:|---:|
| Gemma 4 E4B | 11/12 | 16.42 s | 4.24 / 5.12 s | 6.88 s |
| Gemma 4 26B, existing control | 8/12 | 24.89 s | 9.86 / 14.20 s | 9.93 s |
| GPT-OSS 20B, low | 10/12 | 29.93 s | 7.27 / 10.30 s | 10.88 s |
| Ministral 3 3B | 3/12 | 10.65 s | 5.33 / 6.94 s | 7.68 s |
| Phi-4-mini 3.8B | 8/12 | 13.25 s | 8.36 / 9.54 s | 14.54 s |
| Qwen 3.5 4B | 8/12 | 24.27 s | 11.08 / 15.38 s | 16.05 s |
| Qwen 3.5 2B | 4/12 | 17.43 s | 9.09 / 20.49 s | 25.46 s |
| Gemma 4 E2B | 5/12 | 13.69 s | 2.07 / 4.34 s | 0.94 s |

An accepted exact case requires correct marking decisions and the existing exact point text/order guard.
Gemma 26B made all twelve ordered decisions correctly on manual inspection. Four outputs were safely rejected
because copied mathematical labels were rewritten as equivalent LaTeX. The final local-only schema constrains labels
to the original allowed strings and fixes the row count; all four rejected cases then passed in 6.35–9.01 seconds.
The host still checks identity and order. Cloud requests retain their original schema.

Gemma E4B gave useful explanations in all three diagnostic tutoring cases, but awarded one unsupported Newton-law
point in the baseline. GPT-OSS omitted one mark row and under-awarded a correct Newton point; one chemistry
explanation blurred reaction rates and rate constants. Its final-schema replay fixed row shape but still under-awarded
a probability method point. Schema constraints cannot establish semantic correctness. Every curated local preset
therefore keeps marking on Gemma 26B.

Qwen 2B invented a different function in the calculus explanation. Gemma E2B invented extra marking rows and gave
an incorrect gradient explanation. Phi, Qwen 4B and Ministral also awarded unsupported points. These models remain
available for experimentation, but are not promoted as precision graders. No small sample establishes universal
exam accuracy, including for Gemma 26B.

## Image compatibility

Models with native image support receive the original image. Text-only models use on-device Apple Vision text OCR,
with literal text, confidence and text positions. It does not infer graph geometry, solve the question or fill missing
labels. OCR can omit arrows and isolated labels or misread units; confidence does not prove completeness.
Use a native vision model or clarify the diagram when geometry matters.

The tutor prepares text observations while the learner reads, caches successes for ten minutes in bounded session
memory, and reuses only exact matching image bytes and helper identity. Resets clear the observations. Images are not
saved by this bridge or sent to a cloud provider. Missing images or failed OCR stop the image-dependent request with
an actionable error. The terminal shows image preparation and its measured time; notes and speech exclude metrics.

The first native OCR audit took 30.57 seconds including compilation and Apple's initial Vision setup; a later fresh
OCR process took 0.131 seconds. Exact cached lookups took less than one millisecond. These two scans do not establish
a general OCR latency guarantee. Swift/Xcode command-line tools are required for the first compilation; the binary
is cached under the SSD's `tutor-runtime` folder.

Qwen 2B/4B, Gemma 26B/E4B, Ministral and Granite all failed the tested diagram-geometry gate, including when text
recognition looked correct. No generated image description is treated as verified geometry. An explicit alternative
vision helper in `local_vision_model` remains experimental; presets do not change that preference.

Apple documents the [on-device text recognition API](https://developer.apple.com/documentation/vision/recognizing-text-in-images).
The OCR bridge disables [language correction](https://developer.apple.com/documentation/vision/vnrecognizetextrequest/useslanguagecorrection)
to avoid rewriting mathematical text as ordinary language.

## Speed without changing weights

Small candidates stay resident for 45 minutes; the original models retain their existing residency policies.
Only one requested local generation runs at a time. Background preparation yields to requested work, exact structured
replies can be reused, and image OCR does not load another generative model. Context recovery, queueing and image
preparation are included in observed timing. Model switching can still cause a cold load on this 24 GiB Mac.

No precision reduction, sampling retune, output truncation or silent thinking change was used to pass the preferred
40-second tutoring and 15-second marking targets. The targets are soft preferences. Long answers, reasoning,
web lookup, cold loads, other applications and thermal pressure can exceed them. Optional web lookup is shared by
local text and vision models and remains governed by the existing explicit setting.

## Additional model families

The second pass installed DeepSeek R1 0528 Qwen3 8B, DeepSeek R1 Qwen distill 14B, Llama 3.1 8B and Liquid
LFM2.5 8B. These are text-only choices and use the same local OCR bridge for images. Llama has no optional thinking
mode. DeepSeek R1 and Liquid always think; Settings shows their switches locked on.

DeepSeek 8B made three correct marking decisions in its partial gate, taking 103–114 seconds with thinking enabled;
its unit explanation took 41.69 seconds and was sound. The installed embedded GGUF templates have no working
thinking-off control. An explicit false control still produced hidden reasoning and took 43.48 seconds; this is a
different stochastic sample, not evidence of a faster off mode. The tutor requests true and represents that honestly
in Settings. Both distills are experimental slower reasoning choices rather than fast presets.
DeepSeek 14B completed two correct marking cases in 82.79 and 96.19 seconds; its correct unit explanation took
95.52 seconds. Both distills were fully offloaded to the GPU, with only the measured model resident for these runs.
The partial samples cannot establish general grading accuracy or prove that 14B is faster than 8B.

Llama completed its six-case marking gate with three accepted correct cases and two unsupported points. Its
calculus tutoring reply claimed that `y=x²` is always increasing, including the negative-x example. It is not a
recommended STEM grader or tutor in this audit. Warm marking took a median 16.01 seconds, maximum 18.35 seconds;
the two tutoring replies took at most 12.08 seconds. Initial Llama and Liquid measurements overlapped inactive
model residency and remaining SSD downloads, so they are not clean single-model speed comparisons.

Liquid's installed metadata incorrectly advertised only `think=false`. Real omitted-thinking requests exposed
literal reasoning tags in visible content. Explicit `think=true` correctly separated hidden reasoning in both a
full tutoring reply (24.08 seconds) and structured marking (26.28 seconds). The tutor therefore always sends true
for Liquid, including when an older preference contains false. The structured control still awarded an unsupported
probability point; this fixes parsing, not grading accuracy. Liquid is an experimental manual choice, not a preset.
The installed version's [renderer reports false](https://github.com/ollama/ollama/blob/v0.40.11/model/renderers/lfm2.go#L339),
while its [parser requires explicit true](https://github.com/ollama/ollama/blob/v0.40.11/model/parsers/lfm2.go#L73)
to separate reasoning, explaining the metadata discrepancy.

DeepSeek 32B was deferred: its roughly 19.85 GB quantised weights leave little headroom for macOS and context on
this 24 GiB machine. This is a memory-budget judgment, not a claim that loading is impossible. Start with the smaller
distills. Giant Llama 4 and Kimi K2/K3 packages are outside this practical local budget.
Quantised Kimi-VL might fit, but the inspected community package advertised text input and did not establish working
image routing in this runtime; no Kimi package was installed or presented as a vision-capable choice.

The [DeepSeek distill publisher](https://github.com/deepseek-ai/DeepSeek-R1),
[newer 8B card](https://huggingface.co/deepseek-ai/DeepSeek-R1-0528-Qwen3-8B),
[Meta's Llama 3.1 8B model card](https://huggingface.co/meta-llama/Llama-3.1-8B-Instruct),
[Liquid model card](https://huggingface.co/LiquidAI/LFM2.5-8B-A1B) and
[Kimi-VL publisher](https://github.com/MoonshotAI/Kimi-VL) informed these choices.
The four-family gate uses the final production enum/count schema and is reported separately from the first baseline.

The final community [MiMo V2.6 9B package](https://ollama.com/maternion/mimo-v2.6:9b-instruct)
uses Xiaomi's [distilled Qwen 9B architecture](https://huggingface.co/XiaomiMiMo/MiMo-V2.6-Distill-Qwen-9B).
Its selected embedded GGUF chat template has a real boolean thinking control. Compatibility checks passed for
tutoring with thinking on (48.96 seconds), structured marking (39.74 seconds, one correct two-point decision),
native PNG input (88.10 seconds), and default thinking off (7.90 seconds). Both modes kept hidden reasoning separate.
The image reply omitted requested table arrows, so routing success does not establish image completeness.
The faster off reply also called the acceleration calculation velocity and used confused unit wording, despite
ending with the correct unit. This speed comparison is not evidence of equal tutoring quality. MiMo remains an
experimental individual choice with an explicit community label; it is not included in curated presets.
The older MiMo 7B package was researched but not downloaded.

## Evidence

The repository's [benchmark summary](benchmarks/2026-10-25-local-stem.json) records package fingerprints, aggregate
timing and quality notes without learner data. Full synthetic requests, complete outputs, image audits and calibration
results remain on the SSD under `tutor-benchmarks/2026-10-25-fast-candidates/` and
`tutor-benchmarks/2026-10-25-family-expansion/`.

Candidate sources: [Qwen 3.5](https://ollama.com/library/qwen3.5), [Gemma 4](https://ollama.com/library/gemma4),
[Ministral 3](https://ollama.com/library/ministral-3), [Phi-4-mini](https://ollama.com/library/phi4-mini),
[GPT-OSS 20B](https://developers.openai.com/api/docs/models/gpt-oss-20b),
[Granite vision](https://ollama.com/library/granite3.2-vision).
Publisher benchmarks informed candidate selection; the measured results above are specific to this tutor and Mac.

Validation: the full project suite passed 3,360 tests with 13 existing warnings. After the final model metadata
changes, 184 focused catalogue, runtime, image, preset, settings and provider-compatibility checks passed. Settings
was inspected at 80×24 and 120×40 across Night, Day and Classic. Independent reviews found no remaining code issues.
