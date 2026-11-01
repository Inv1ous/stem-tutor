# Fusion and numerical parity execution

27 October 2026. **All requested gates passed; GPU released.** This verifies fusion, preservation, reload and the preregistered development-input numerical screen. It does not establish generated-answer quality, native Ollama compatibility or Fast/Deep latency.

Root granted exclusive GPU ownership after the sampling jobs ended. Fresh preflight found no model processes, normal pressure, 3,533.44 MiB swap and 47 GiB free SSD space. The new output directory was absent. Every stage ran once, sequentially, without retries or changed thresholds. GPU stages used `caffeinate -i`, the existing 14 GiB observed-memory, 512 MiB additional-swap, 20 GiB free-space, pressure and 600-second deadline guards.

## Commands and terminal evidence

The exact command strings, working directory, handles and exit codes are preserved in `/Volumes/External SSD TB4/LocalAI/tutor-runtime/stem-training/fusion-parity-v1/execution-commands-v1.json`. All commands used repository working directory `/Users/sora/Miscellaneous/02 Education/~~ AI Workflow/stem-tutor`.

| Stage | Exec handle | Terminal result | Evidence |
| --- | ---: | --- | --- |
| Reviewed fusion utility with `--execute` | 3982 | Exit 0 | `tutor-runtime/stem-training/fusion-hybrid-v1-001.log` |
| Adapter-only parity capture | 48612 | Exit 0, 18/18 finite | `fusion-parity-v1/adapter-capture-v1/` |
| Fused-only parity capture | 6692 | Exit 0, 18/18 finite | `fusion-parity-v1/fused-capture-v1/` |
| CPU comparison | Synchronous | Exit 0, numerical screen passed | `fusion-parity-v1/comparison-v1.json` |

The last three paths are below `/Volumes/External SSD TB4/LocalAI/tutor-runtime/stem-training/`. Capture logs sit beside their directories. Started/terminal attempts, load receipts, summaries and all 36 raw FP32 arrays remain intact. Each capture process ended before the next started. A final process inventory found no model, Ollama, MLX, parity or evaluation process.

## Fusion proof

Source: `stem-tutor-training/pilot-v2-512-001`, development-accepted update100, canonical adapter SHA256 `a547604e9f64c35ec999a4666d66b50efc7d462b1e35d4a18c8a055fc5a328ac`.

Output: `/Volumes/External SSD TB4/LocalAI/models/stem-tutor-qwen35-hybrid-v1`.

The completed receipt verifies all **24 target modules are BF16**, all 876 saved tensors reload exactly, and non-target runtime tensors remain byte-identical. Original source hashes, upstream licence, tokenizer, vocabulary and chat-template assets were independently rechecked after execution. There was no force import, requantisation, original-model mutation or generated answer.

Weights occupy **3,181,190,307 bytes**; the complete artifact, including its receipt, occupies **3,208,251,482 bytes**. Fusion peak allocation was **3,650,887,184 bytes (3.400 GiB)**. Receipt SHA256: `fe76202ddb456191d328cf3cb2a6b7b3e4ec5c7e2810ada4561104cc552f9df3`.

## Preregistered numerical screen

Both captures reproduced the same frozen DEV18 input IDs and all 288 selected positions. Every full-vocabulary vector was finite. Raw arrays total **572,133,888 bytes**, including headers. Adapter/fused peak allocations were **2,791,030,354 / 3,451,866,017 bytes**. Pressure stayed normal and swap remained 3,533.44 MiB throughout; final SSD headroom was 43 GiB.

| Metric | Observed |
| --- | ---: |
| Top-1 agreement | 286/288 (99.3056%) |
| Strong-margin disagreements | 0/259 |
| First-answer-position top-1 agreement | 18/18 |
| Raw mean / maximum absolute error | 0.0222914 / 0.3125 logits |
| Centred mean / maximum absolute error | 0.0204529 / 0.298764 logits |
| First-answer mean / maximum KL | 0.00000346603 / 0.0000110214 nats |

All frozen thresholds in [the plan](fusion-parity-plan.md) passed. The two top-1 differences occurred below the strong-margin threshold. No gate failed and no automatic retry occurred. Numerical differences remain measurable; this is not numerical identity or a response-speed result.

Comparison SHA256: `946ac5ae9da3b47509e1817364fc3fd93b2543e68291e8643b6e35fbead83b5c`.

Work stopped here. Native import/API calls, answer generation, catalogue/preset changes and further training were not performed.
