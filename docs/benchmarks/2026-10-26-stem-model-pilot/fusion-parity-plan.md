# Fusion numerical parity plan

Prepared 27 October 2026; **CPU only. No fusion, MLX import, model loading or GPU capture executed.** The GPU remains owned by the development sampling run.

The standalone scratch utility is `/Volumes/External SSD TB4/LocalAI/tutor-runtime/stem-training/fusion-parity-v1/probe.py`. Its frozen resource and immutable-attempt helpers were copied from the sampling experiment's source snapshot. Product source, weights, data, dependencies and Git state were not changed.

## Frozen inputs and protocol

`inputs.json` contains the existing metadata-selected DEV18 questions in selection order: original user messages only, without assistant gold, expected answers or scoring checks. It uses the training-role protocol and native Fast template. CPU tokenisation froze identical token IDs for both variants, with 111 tokens maximum. Capture must reproduce every frozen ID before forwarding. Gold is neither copied into prepared inputs nor fed to either model.

Each input selects eight evenly spread earlier positions and its last eight positions: 16 per question, **288 total**, including every first-answer prediction position. Both variants receive the exact same complete prompt tokens. Full-vocabulary selected logits are stored as FP32 `.npy` files, approximately **572 MB across both variants**, plus hashes and receipts. No answer or reasoning tokens are generated. Sampling penalties are irrelevant to this raw-logit comparison and are not applied.

Final input SHA256: `22b31a6a86f10ca920d2e135f70ff7a3320cbe1b0294fcff562edf2547d03b1a`.
Script SHA256: `d94a4653fcf3a0405740a003d5f198396eca3cf8202676db64771e062a18ff77`.
Earlier CPU preflight files remain archived; they were never executed on GPU.

## Predeclared numerical screens

All logits must be finite, with matching input IDs, selected positions and vocabulary shapes. Report raw maximum/mean absolute errors, centred maximum/mean absolute errors, every top-1 agreement, live top-two margin and first-answer-position KL divergence in natural-log units.

Screens require:

- Overall top-1 agreement at least **95%**.
- **Zero** disagreements where the live-adapter margin is at least **0.5 logits**.
- Mean absolute centred error at most **0.05**, maximum at most **0.5 logits**.
- Mean first-answer KL at most **0.01 nats**, maximum at most **0.05 nats**.

These are engineering screening choices fixed before observing model differences, not theoretical BF16 error bounds. Centring removes probability-irrelevant common offsets; KL measures the distributional effect. The combined screens require close distributions and stable clear-margin predictions while exposing near ties. Passing establishes neither numerical identity nor answer/scientific parity. Full generated-answer comparison remains separate.

## Execution after root GO

Run `capture --variant adapter --output NEW_ADAPTER_DIRECTORY --execute`, then a separate `capture --variant fused --output NEW_FUSED_DIRECTORY --execute`. Each process loads exactly one variant and releases it before the next. The adapter is fixed to update100, canonical SHA `a547604e9f64c35ec999a4666d66b50efc7d462b1e35d4a18c8a055fc5a328ac`; the candidate is `models/stem-tutor-qwen35-hybrid-v1`, requiring its completed fusion receipt. `compare --adapter ADAPTER_DIRECTORY --fused FUSED_DIRECTORY --output NEW_REPORT.json` is CPU-only.

Capture retains the existing 14 GiB observed memory, 512 MiB additional-swap, 20 GiB free-disk, pressure and 600-second deadline guards. Load peaks are checked before cache clearing. Immutable attempts, orphan starts, raw checksums and final source identity survive failures; explicit resume skips only verified successes. Comparison requires completed captures and never selects an earlier success over a later failure.

Eight CPU checks pass, including offsets, finite rejection, confident rank flips, common-shift invariance, complete comparison and failed/interrupted-run handling. GPU operational proof remains pending.
