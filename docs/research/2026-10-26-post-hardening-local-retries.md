# Post-hardening local model retries — 26 October 2026

Qwen27 Thinking Off completed the previously failing seeded-history case once cold and twice warm after optional-history pruning. All three preserved current evidence and avoided OOM. E4B and GPT-OSS still have retained accuracy, coverage, literal or transport failures; this evidence does not support a claim of consistently correct local teaching.

These are serial retained retries of frozen prompts from the original matrix, not a fresh benchmark with rewritten questions. GPU ownership was checked before starting; no trainer or other model inference was running. Empty native preloads remained mandatory, each owned Ollama model acknowledged unload, and owned services/private MLX workers were closed between groups. No learner vault, model weights, settings or production code were changed by this proof run.

## Timing, transport and content

| Model / effort | Frozen case | First block / total seconds | Transport | Separate content review |
| --- | --- | ---: | --- | --- |
| gemma4:e4b / True | bonding | 14.86 / 17.64 | PASS | FAIL coverage: omits ionic/covalent/metallic definitions and requested property detail. |
| gemma4:e4b / True | topic_change | 18.67 / 25.36 | PASS | FAIL coverage: only three hydrocarbon formulae; all four requested oxygenated formulae omitted. |
| gemma4:e4b / True | literal_code | 8.79 / 11.51 | PASS | FAIL literal/code: double quotes changed to single quotes; entire code flattened to one comment-bearing line; Python syntax invalid. |
| gemma4:e4b / True | sourced_definition | 16.81 / 24.86 | PASS | Required coverage PASS: electrostatic/opposite-ion definition and fixed-solid/mobile-molten charge carriers. |
| gemma4:e4b / True | speech | 12.67 / 18.53 | PASS | Visual sulfate composition/charge PASS; spoken-text FAIL: contains SO4^2- and -2 instead of plain spoken wording. |
| gpt-oss:20b / low | bonding | 25.07 / 51.94 | PASS | PARTIAL: broad requested categories covered; exam-definition precision weak and blanket covalent-solid nonconductivity omits graphite exception. |
| gpt-oss:20b / low | calculus | 11.50 / 29.41 | FAIL | FAIL transport: unsafe control/surrogate rejected; incomplete visible calculation and no finite-sum result. |
| gpt-oss:20b / low | literal_code | 19.11 / 25.25 | PASS | Literal/code PASS: exact requested line in square-function code block; Python syntax valid. Surrounding explanation contains malformed math/source notation. |
| gpt-oss:20b / low | sourced_definition | 16.51 / 23.02 | PASS | Required points covered, scientific qualification: molten ions described misleadingly as dissolving in a molten medium. |
| gpt-oss:20b / low | speech | none / 11.88 | FAIL | FAIL transport: unsafe control/surrogate rejected before any visual answer. |
| qwen3.8:27b / False | long_context (cold 1) | 92.42 / 123.04 | PASS | Required conductivity coverage PASS; two native generation messages; current evidence byte-identical; no OOM. |
| qwen3.8:27b / False | long_context (warm 2) | 14.81 / 30.59 | PASS | Required conductivity coverage PASS; two native generation messages; current evidence byte-identical; no OOM. |
| qwen3.8:27b / False | long_context (warm 3) | 11.24 / 23.15 | PASS | Required conductivity coverage PASS; two native generation messages; current evidence byte-identical; no OOM. |
| gemma4:e4b / False | bonding | 10.57 / 40.80 | PASS | FAIL scientific accuracy: fabricated IMF ordering dH < H2O < F < covalent; incorrectly asserts metallic conductivity in the gas state. |
| gemma4:e4b / False | topic_change | 7.19 / 28.17 | PASS | FAIL scientific accuracy/coverage: wrong carboxylic-acid formula C_nH_{2n-1}COOH; aldehyde/ketone C_nH_{2n}O overlap omitted; ring-strain explanation wrong. |
| gemma4:e4b / False | literal_code | 1.83 / 300.01 | FAIL | FAIL literal/code: see retained timeout/error and partial/native output. |

## Qwen memory evidence

The original retained failing request had eight messages and 17,221 content bytes. New requests had two messages and 5,870 content bytes, retaining the complete 345-byte current question. Each reported 1,280 native input tokens. Cold/warm cached input counts were 0, 1,275 and 1,279. Runtime context/output/sampling/effort options were not changed; no hard 4096 limit or 16K retry was added.

The warm trials immediately followed this same frozen request while keeping the model loaded; they did not replay the seven distinct predecessor cases. There is only one cold repetition. These successes do not prove safety for larger mandatory questions, images, different warm prefix state or concurrent memory pressure. Mandatory system/schema/current inputs may exceed the optional history target and can still exhaust memory.

## Integrity and retained failures

All 16 complete or partial streams equal their recorded final text. Schema validity is not treated as coverage or scientific correctness. Exact literal preservation was checked against the frozen requested line; code was parsed with Python ast without executing it. Content review is a narrow manual check of requested facts and demonstrated errors, not an exhaustive expert syllabus audit.

Both GPT-OSS failures are retained with their actionable document-validation error and visible partial response. Their earlier harness only wrapped rendering, so it did not recover the unsafe block rejected before rendering. They were not rerun solely to capture that block. The later E4B Off harness also captures native visible JSON fragments, validated assistant wire and decoded `_token` failures without hidden reasoning. Its literal-code timeout retained 52,827 visible JSON characters and the two complete introductory paragraphs emitted before the unfinished code block; no partial code was silently certified as complete.

Code hashes at start/end are retained. The first run changed only unrelated `stem_training.py`, and the E4B Off extension changed only unrelated `stem_training_eval.py`, during root-owned CPU work; tutor transport/renderer files were unchanged during both runs. Frozen original prompts and the original evidence JSON were not modified.

## Evidence

- [Initial serial retry data](evidence/2026-10-26-local-retries/candidate-local-retry-2.json)
- [E4B Thinking Off data](evidence/2026-10-26-local-retries/candidate-local-retry-e4b-off-1.json)
- [Separate content and Python syntax assessments](evidence/2026-10-26-local-retries/assessments.json)
- [Initial retry harness](evidence/2026-10-26-local-retries/stem_format_local_retry_2.py)
- [E4B Off harness with decoded-block capture](evidence/2026-10-26-local-retries/stem_format_local_retry_e4b_off_1.py)

Original transient evidence remains under `/tmp/stem-format-current/`; durable copies retain the JSON, logs and harnesses alongside this report.
