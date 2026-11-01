# Development-only sampling contrast for structured STEM replies

2026-10-27. Research status: CPU/source inspection and primary web sources only. No GPU/model calls, downloads, authentication, environment changes, weight updates or sampler changes. DEV54 retains exclusive GPU access. This note proposes a bounded follow-up after the role-protocol diagnosis; it does not report its outcome.

The coordinator reports development loss near 0.176 after the 100-update pilot, alongside 67/120 unassisted format successes in the earlier evaluation. That mismatch does not by itself establish undertraining: teacher-forced loss, generation protocol, decoding and exact-format scoring measure different things. Preserve the original counts and receipts while investigating role alignment first.

## Verified settings and implementation

The pinned [Qwen3.5-4B README](https://huggingface.co/Qwen/Qwen3.5-4B/blob/851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a/README.md), revision `851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a`, recommends these task-dependent settings:

| Publisher task | Thinking | Temperature | Top-p | Top-k | Presence penalty |
| --- | --- | ---: | ---: | ---: | ---: |
| General | On | 1.0 | 0.95 | 20 | 1.5 |
| Precise coding | On | 0.6 | 0.95 | 20 | 0.0 |
| General | Off | 0.7 | 0.8 | 20 | 1.5 |

These rows all use min-p 0 and repetition penalty 1. The card warns that higher presence penalties can reduce performance or cause language mixing. Its two non-thinking-reasoning recommendations conflict across sections: the API tip uses 1.0/0.95/20/presence 1.5, while Best Practices uses 1.0/1.0/40/presence 2.0. Neither changes the consistent general-Fast baseline above. Precise coding demonstrates task-specific zero penalty; it does **not** establish a publisher-recommended Fast STEM marking configuration. No model-specific greedy recommendation was found in this pinned card.

Installed MLX-LM 0.32.2 [`sample_utils.py`](https://github.com/ml-explore/mlx-lm/blob/v0.32.2/mlx_lm/sample_utils.py) confirms that presence subtracts its coefficient from logits for tokens found in the last configured history span, regardless of occurrence count. Zero omits that processor. Its API default span is 20; this evaluator explicitly uses 1024. With positive temperature, filtering runs top-p → min-p, if enabled → top-k → categorical sampling with temperature. Temperature zero selects argmax and bypasses these filters. [`generate.py`](https://github.com/ml-explore/mlx-lm/blob/v0.32.2/mlx_lm/generate.py) builds processor history from prompt/prefill and subsequent generated tokens, so this is not an output-only repetition penalty. These facts were checked against the installed SSD source, without importing MLX.

Local `app/tutor_app/stem_training_eval.py` currently supplies Fast 0.7/0.8/20, presence 1.5 and presence span 1024. Its generation call passes the penalty separately through `make_logits_processors`. Local `app/tutor_app/stem_training.py:loss_fn` applies cross-entropy directly to model logits, then masks to public answer tokens. There is no decoding penalty in that loss. The upstream [trainer loss](https://github.com/ml-explore/mlx-lm/blob/v0.32.2/mlx_lm/tuner/trainer.py) follows the same unpenalised-logit pattern.

## Mechanism: plausible, not established

A source criterion or required key already present in the prompt can receive the penalty even at its first generated appearance. Repeated keys across marking-point objects remain affected. This can favour a fresh synonym, altered criterion or different key over exact reuse. Common punctuation may also be affected, but tokens that are all penalised equally retain their relative preference. The mechanism is not a guarantee of malformed JSON.

For identical underlying model logits, if a penalised token and an unpenalised alternative both survive filtering in both arms, their final relative odds receive a factor of `exp(-penalty / temperature)`. At 1.5/0.7 this is about **0.117**, an approximately 8.5-fold reduction. Filtering can change which candidates survive, so this is not an absolute sampled probability or a full-distribution comparison. This mathematical consequence explains why a strong anti-repetition setting could conflict with narrow copying/format tasks despite low unpenalised training loss; the causal claim still needs data.

Other live explanations remain: role mismatch, wrong prompt prefix, insufficient output budget, incorrect raw schema, learned-content errors or evaluator strictness. Do not conclude that the penalty caused 67/120, or excuse malformed output with low loss.

## Minimal contrast after locking the role protocol

First select and freeze the best defensible role protocol from the existing **development** diagnostic. Then freeze its selected row IDs, exact rendered prompts, tokenizer/template, checkpoint, output cap, timeout, parser, scorer and grammar policy. Do not add role or prompt edits during the sampler contrast.

| Arm | Thinking | Temperature | Top-p / top-k | Presence | Span | Purpose |
| --- | --- | ---: | --- | ---: | ---: | --- |
| A: Fast reference | Off | 0.7 | 0.8 / 20 | 1.5 | 1024 | Reproduce the existing sampler under the locked protocol. |
| B: Fast no presence | Off | 0.7 | 0.8 / 20 | 0 | 1024, inactive | Change exactly one coefficient. |
| C: optional greedy diagnostic | Off | 0 | Inactive | 0 | Inactive | Test deterministic decoding separately; not part of the one-factor contrast. |

Keep repetition neutral, frequency zero, min-p zero and identical generation bounds. Start A/B on the same frozen development subset and seed 42; compare by item. If promising and budget permits, confirm both across predeclared seeds 43 and 44. Record every trial, including timeouts and budget exhaustion; do not rerun only failures or retain each arm's best sample. Randomise/interleave run order where practical and keep one GPU consumer. Arm C is optional, with a separate receipt; greedy results cannot isolate presence because temperature/filter behaviour also changes.

Primary endpoints: raw unassisted contract validity, exact copying where required, exact marking-criterion preservation, complete final delivery and marking decisions conditional on preserved criteria. Keep host-repaired validity separate. Report invalid-envelope, key/criterion substitution, duplicate-key, code/literal mismatch, looping and token-limit failures separately. Compare subject/task strata, token count, latency and paired successes/losses. Correlated variants do not become independent evidence merely by adding seeds. Do not promote B if improved formatting hides worse marking correctness or substantially more looping.

This experiment can establish which Fast sampler works better on these development inputs under the locked protocol. It cannot prove broader science accuracy, improved weights, absence of contamination, superiority on the already-evaluated 120 items, or reliable native Ollama parity. Keep all earlier results under their original sampler/protocol identities. Do not use sealed-test targets or failure-specific rewrites to choose these settings, and do not modify weights.

## Structured JSON is a separate axis

[Ollama's structured-output guidance](https://docs.ollama.com/capabilities/structured-outputs) recommends a JSON schema in `format`, grounding instructions in the prompt, response validation and lower temperature for deterministic completions. This is useful operational guidance, not proof that greedy Qwen marking is most accurate. [vLLM's primary documentation](https://docs.vllm.ai/en/latest/features/structured_outputs/) distinguishes JSON-schema constraints from prompt instructions and describes separate handling of reasoning boundaries. It also cautions that matching boundary text does not establish matching dedicated token IDs.

Keep grammar assistance fixed during A/B. For the claimed learned-format measurement, retain the same **unassisted** mode as the baseline. A later constrained-JSON production probe should have its own receipt and denominator. Grammar can restrict syntax/schema; it does not establish faithful criteria, correct units or correct grading. Enabling constraints only for B would test two interventions and hide whether the sampler helped learned format.

Deep remains a separate experiment: previous no-penalty thinking probes reportedly exhausted their budget without final answers. Fast no-presence results do not justify changing Deep. Preserve Deep's sampler and reasoning controls, all other local models, and all cloud settings. If a Fast change is eventually adopted, apply it only to the custom model's Fast requests and include the resolved sampler in result/cache identities. Actual native Ollama validation remains required because its sampling order differs from Python MLX-LM.
