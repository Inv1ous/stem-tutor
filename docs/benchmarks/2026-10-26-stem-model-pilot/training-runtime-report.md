# Bounded STEM training runtime

26–27 October 2026. Status: the fresh checkpointed **512-token pilot completed all 100 optimizer updates**, passed its full development-selection and adapter-only reload checks, and released the GPU. Earlier 1024-token pilots stopped safely at the unchanged swap guard; all evidence and pending checkpoints are preserved. The selected adapter is SSD `stem-tutor-training/pilot-v2-512-001/adapters.safetensors`. Independent inference/evaluation, fusion and app registration are subsequent coordinator-owned gates.

## Environment receipt

The new environment is `/Volumes/External SSD TB4/LocalAI/tutor-runtime/stem-training/.venv`, Python 3.13.7. Exact critical versions: MLX 0.32.3, MLX-Metal 0.32.3, MLX-LM 0.32.2, Transformers 5.20.2, NumPy 2.5.4, Datasets 5.1.0, Tokenizers 0.23.3, Safetensors 0.8.0. `pip check` returned `No broken requirements found.` No project or inference environment was modified.

Full installed dependency versions and tokenizer evidence are in SSD `runtime_receipt.json`; the full pip lock is SSD `requirements.lock` (SHA256 `72d170d30f49cf81797685499d131159027c445ce6829f120e39c70235dd1d98`). Installation log and pip cache are in the same isolated runtime directory. Runtime plus caches measured 818 MiB immediately after installation; free SSD capacity measured 47 GiB. Caches, Python bytecode, data, temporary files, adapters and receipts are explicitly routed to SSD. The environment is offline during preparation/training; no training data is uploaded.

## CLI and controls

`app/tutor_app/stem_training.py` imports only the standard library in the normal application. `python -m tutor_app.stem_training --help` therefore needs no MLX/Transformers dependency in the app environment. The separate SSD Python must be used for the actual preparation/training command, with repository `app` in `PYTHONPATH`.

Required arguments are `--base-model`, `--data-dir`, and a **new** `--adapter-dir`. Default action (or `--prepare-only`) performs local-tokenizer preparation and writes a receipt without importing MLX or loading weights. `--execute` is explicit and additionally requires `--base-receipt`. The pinned identity, upstream identity, verified flag, required file inventory, every file size and SHA256 must match that receipt before training. Preparation without a verified base receipt records `base_revision: null` instead of claiming verification.

Smoke defaults are exactly five optimizer updates, 512-token complete sequences, batch 1, accumulation 1, learning rate 1e-5 and seed 42. Smoke selects a deterministic maximum 16 training and eight development examples after validating/tokenizing the full train/development splits. `--mode pilot --iterations 100 --max-seq-length 1024 --grad-accumulation 4` selects the full retained train/development sets and remains capped at 100 optimizer updates, batch 1, 1024 tokens, accumulation 4, a configured observed MLX active/peak budget no greater than 16 GiB and one hour wall time. Iterations count optimizer updates, not microbatches.

LoRA is fixed to rank 8, scale 2, dropout 0, the last eight decoder blocks, and only MLP gate/up/down projections. The base is frozen; all 48 trainable tensor names must match that adapter scope. The expected size from the pinned dimensions is 2,260,992 trainable parameters. The runtime checks finite loss/gradients before optimizer mutation, finite parameters before saving, initial/final tensor hashes, real weight changes and adapter-only save/reload values. It saves initial, every 25 updates, and final/interrupted checkpoints atomically. Interval/interrupted candidates remain pending; only development-accepted candidates publish to the canonical adapter. Final and periodic development deterioration stop training and retain explicitly rejected candidates; sealed test labels are never opened.

Resource checks require normal macOS pressure before model loading and stop on critical pressure, a warning sustained for ten seconds, more than 512 MiB additional swap relative to the starting snapshot, or SSD capacity below 20 GiB. Existing swap alone is not a rejection condition. SIGINT/SIGTERM and the wall deadline are checked between safe GPU operations; the runtime preserves the last finite adapter checkpoint and an error/stop receipt. A single in-flight kernel cannot be interrupted by these Python checks. The receipt includes losses, elapsed time, peak MLX memory, resource snapshots, template hash, manifest/data hashes, dropped row IDs and selected row IDs. A full process crash or operating-system kill can only preserve the last checkpoint already written.

## Final-only masking evidence

The pinned local tokenizer was loaded with `trust_remote_code=False`, `local_files_only=True`, with no MLX import. A public semantic JSON example rendered to 45 tokens; token index 18 began the public JSON. The masked prefix ended with the native assistant `<think>\n\n</think>\n\n` region, and supervision covered the JSON plus native end-of-message tokens only. The template file SHA256 is `a4aee8afcf2e0711942cf848899be66016f8d14a889ff9ede07bca099c28f715`.

The wrapper checks rendered character offsets against the tokenizer's native template token IDs and rejects a token that crosses the final-answer seam. It does not use MLX-LM ChatDataset's prompt-only mask. A discovered Transformers 5 behavior (tokenized templates default to BatchEncoding) is handled by explicitly requesting `return_dict=False`, with a regression test. Gold containing hidden reasoning fields, think tags, malformed JSON or failed validation is rejected. Overlength complete examples are dropped and counted, never truncated.

Preparation on the earlier 1202-row corpus (manifest `a851cccb421d548b7d00ef89b645220ac31098ec178f39f0b61f45dd5c6b5b88`) retained 686/735 training and 222/232 development examples at 512 tokens. These counts are historical: the data builder is adding direct factual recall examples and shortening format instructions, so a fresh preparation is required before any training. No sealed test content was read by preparation.

## Verification and remaining gate

`python -m pytest tests/app/test_stem_training.py -q`: **48 passed** after preflight corrections. Tests cover prompt/reasoning masking, off-by-one target positions, token-boundary rejection, hidden-reasoning rejection, complete-sequence dropping, bounds, adapter-only tensor scope, SSD/path overwrite prevention, split leakage, manifest checksums, pinned model file integrity, signal/deadline behavior, optimizer-update counting, accumulation, checkpoint-on-error, resources and CLI execution gating. New behavior was exercised failing-first before implementation.

Bare project `pytest -q` is blocked by five existing duplicate module-name collection conflicts: `tests/test_bf_j02.py`, `tests/test_bf_j12.py`, `tests/test_p0_verify.py`, `tests/test_p1_fixes.py`, and `tests/test_qol_round2.py` collide with names under `tests/app`. Retrying with importlib collection produced 43 existing `ModuleNotFoundError` collection errors because app tests import sibling `test_tui`/`test_picker` modules directly. Logs are retained in SSD `project-test.log`. The separate `tests/app` run was cleanly interrupted with SIGINT at the coordinator's request to avoid CPU overlap with the benchmark: 1214 passed in 372.71 seconds before KeyboardInterrupt (exit 2, interruption rather than a test failure). No further broad suites will be run by this agent; the coordinator owns final canonical verification.

Before executing smoke: finish the benchmark, release all competing inference GPU users, verify normal pressure, complete and preserve native base development inference in Thinking Off/On, obtain the coordinating agent's explicit GO, verify the root-written base receipt, and freshly prepare the final immutable dataset. The command then adds `--base-receipt /Volumes/External SSD TB4/LocalAI/stem-tutor-training/base-receipt.json --execute` with a new SSD output directory. Independent base/adapter inference, sealed evaluation, fusion and import are subsequent gates; this code does not claim they pass. No model alias or default selection has changed.

## Preflight corrections (P1 / P2)

The independent preflight review identified two valid issues before any GPU training. Four failing-first CPU cases reproduced both active/peak over-budget observations despite the allocator hint, prevented-next-step behavior, and initial development loss 1.0 followed by final loss 2.0 incorrectly completing. The targeted suite was red with four failures and 44 passes, then green with **48 passes** after the changes.

The installed MLX 0.32.3 `set_memory_limit` documentation says it is a graph-evaluation allocation **guideline**; it does not provide a hard allocation ceiling. The wrapper now defaults to a 14 GiB observed active/peak budget (16 GiB maximum) and sets the MLX allocation guideline to 87.5% of that budget (12.25 GiB by default). It calls `get_active_memory` and `get_peak_memory` after model loading, evaluated adapter initialisation, forward/backward, finite-check evaluation, optimizer evaluation, every development forward, and adapter reload; it checks before checkpoints/publication and before the next safe operation. Observations, phase, budget, guideline and any overrun are recorded in the receipt. An observed overrun stops further training and leaves the last saved finite checkpoint. These observations cannot interrupt or prevent the peak allocation of an in-flight kernel, and MLX active/peak figures do not cover every category of process/OS memory; the separate pressure/swap checks remain required. No RLIMIT_AS or hard-cap claim is used.

Final validation now applies the same best-development-loss policy as periodic validation. A deteriorating five-update candidate is stored as `000005_rejected_adapters.safetensors`, receipt state is stopped with rejected eligibility, and `adapters.safetensors` remains the prior development-accepted adapter. Periodic candidates are first saved pending and published only after the following development check accepts them. Sealed test labels do not participate.

## Final data-v2 preparation

Tokenizer-only preparation of final manifest `439c106584be8268aa6019278ed286359b3ce840d705ddc32c0279e7951bcb9a` passed without MLX/model loading. At 512 tokens, 673/705 training examples and 246/255 development examples remain; 32 and nine complete overlength examples were dropped respectively. Smoke selected deterministic 16/8 subsets. At 1024 tokens, 704/705 training and 255/255 development examples remain (dropped 1/0). Preparation receipts are in SSD `stem-tutor-training/prepared-smoke-v2` and `prepared-pilot-v2`. The sealed test file was not opened. The earlier v1 preparation remains preserved separately.

## Authorised five-update smoke result

The coordinator explicitly authorised only the five-update smoke after benchmark/base profiles ended and competing workers were unloaded. Immediately before launch: normal pressure level 1, swap 3517.50 MiB, and no matching inference/training/benchmark processes. Exactly one CLI job ran (exec session 92536), using the verified pinned base receipt, immutable data-v2, seed 42, 512-token complete sequences, batch/accumulation 1, fixed rank-8 LoRA scope and a new SSD `stem-tutor-training/smoke-v2-001` output. It exited 0. No pilot or other inference job was launched.

Observed results:

| Evidence | Result |
| --- | --- |
| Optimizer updates | 5 completed |
| Trainable parameters | 2,260,992, across 48 permitted adapter tensors |
| Training losses, updates 1–5 | 1.16525567, 2.25802588, 1.33578694, 0.37463081, 1.79920638 |
| Development loss (same eight selected items) | 1.0687229416 before → 1.0351127953 after |
| Finite checks | All loss, gradient, accumulated-gradient and adapter/checkpoint parameter checks passed |
| Real weight changes | All 48 trainable tensor hashes changed |
| GPU-entry elapsed time | 21.820806917 seconds, including load/development/training/checkpoint/reload |
| MLX peak allocation | 8,401,300,752 bytes (7.824 GiB) |
| Maximum sampled active allocation | 2,640,120,054 bytes (2.459 GiB); intermediate allocations are covered by the larger recorded peak |
| Observed memory samples | 86 |
| Pressure / swap | 1 → 1, 3517.50 → 3517.50 MiB (no growth) |
| Free SSD | 50,488,537,088 → 50,469,425,152 bytes |
| Saved adapter reload | Exact tensor-hash match into the same loaded base |
| Candidate status | Development accepted; canonical adapter is update 5 |

Adapter file SHA256:

- Initial `000000_adapters.safetensors`: `7efc031daa087ae3625700e5dd8bb4d6a85e3e0c0f75e640546087148eb2d3e6`
- Final `000005_adapters.safetensors`: `c28d0d215b8c4c2e077cff0ae34d8a1288a6233961d3eb5f596909cb44cb5367`
- Canonical `adapters.safetensors`: same final hash.

The full initial/final per-tensor hashes, all observations, data/template/base identities and loss records remain in SSD `smoke-v2-001/training_receipt.json`. Its compact summary is `smoke_summary.json`; complete stdout/stderr is SSD `tutor-runtime/stem-training/smoke-v2-001.log`. A fresh process inventory after exit found no matching model/training workers. This smoke proves the bounded backward pass, updates, resource envelope and adapter reload; the eight-item development loss change is not a scientific-quality or held-out promotion result. The sealed test file was not opened. A longer pilot, independent inference reload, final test evaluation, fusion and registration require subsequent coordinated work.

## Authorised pilot-v2-001: resource stop and diagnosis

Root explicitly authorised a fresh seed-42 adapter for up to 100 optimizer updates, complete sequences up to 1024 tokens, batch 1, accumulation 4, learning rate 1e-5, full retained training/development data, fixed LoRA scope and unchanged resource guards. Exactly one job ran, session **70376**. It exited **1 with TrainingStopped**, after **7 completed optimizer updates** and **292.976267292 seconds**, because sampled additional swap grew **653.31 MiB**, exceeding the 512 MiB threshold. Three microbatches of update 8 had completed backward/gradient checks, but update 8 was not applied. Pressure remained 1. The recorded peak was **14,767,872,038 bytes (13.754 GiB)**, below the 14 GiB observed threshold, while the maximum sampled active allocation was 2,816,126,389 bytes (2.623 GiB). No guard was weakened and no automatic restart occurred.

Full 255-item development loss before training was **0.8506162018**. Seven update losses were 1.08348657, 0.49503700, 1.24471619, 0.72699156, 1.49495289, 1.31263934 and 0.60124714. The pending update-7 adapter contains 48 finite tensors; a CPU Safetensors comparison confirms all 48 changed. It has not passed post-training development selection or an MLX reload, and is not the canonical accepted candidate. All logs, receipt observations and checkpoints remain under SSD `pilot-v2-001`; the compact result is `pilot_summary.json`.

- Initial/canonical `000000_adapters.safetensors` SHA256: `7efc031daa087ae3625700e5dd8bb4d6a85e3e0c0f75e640546087148eb2d3e6`. This matches the smoke's untrained checkpoint, proving the pilot did not continue smoke weights.
- Pending `000007_adapters.safetensors` SHA256: `8bbeb409a75dfb8fc327a6e35e84ca89062118e54541cfdddf45e37a91432668`.

The strongest measured explanation is backward activation/recurrence memory scaling with actual sequence length, rather than retained development or optimizer state. Replaying only tokenization and the NumPy seed/order on CPU mapped each backward observation to its row:

| Run / microbatch | Complete tokens | New cumulative MLX peak |
| --- | ---: | ---: |
| Smoke 1 | 118 | 5,749,005,118 bytes |
| Smoke 3 | 176 | 7,366,472,376 bytes |
| Smoke 4 | 214 | 8,401,300,752 bytes |
| Pilot 1 | 189 | 7,693,840,972 bytes |
| Pilot 2 | 336 | 11,713,171,928 bytes |
| Pilot 10 | 379 | 12,912,751,556 bytes |
| Pilot 31 (unapplied update 8) | 454 | 14,767,872,038 bytes |

The full development forward pass peaked at only 3,547,253,598 bytes (3.304 GiB), before any training. Allocator cache observations never exceeded 439,537,112 bytes (419.18 MiB), and active allocation returned to approximately 2.24 GiB after optimizer updates. Adam's two float32 adapter moments account for approximately 18 MiB; accumulated adapter gradients are approximately 9 MiB per materialized tree. These are too small to explain the extra approximately 6 GiB transient peak. The unchanged class-level base and frozen parameters are not growing. Per-microbatch mappings are saved as SSD `microstep_memory_analysis.json` for both runs.

Installed Qwen3.5 source confirms that training selects `gated_delta_update(..., use_kernel=False)`, which runs the sequential reference recurrence and carries float32 `[batch, value_heads, value_dim, key_dim]` states through token positions. With these pinned dimensions, one such state is 2 MiB, before additional backward intermediates, and several linear-attention decoder layers require gradients through their inputs. This supports the sequence-length explanation; it is not a measured attribution of every allocated byte. The wrapper did not enable gradient checkpointing in either recorded run.

## CPU-prepared memory correction (GPU validation pending)

The smallest prepared change enables the supported native MLX-LM `grad_checkpoint` helper through explicit `--grad-checkpoint`. It invokes the helper once for every distinct decoder class because the helper wraps the class call; for pinned Qwen3.5 all 32 layers share DecoderLayer, which contains both linear-attention and full-attention branches. Thus all relevant layer calls are covered without editing installed packages. The trainable LoRA tensor scope remains last-eight MLP projections. The native helper trades retained activations for recomputation, as described by the [official MLX checkpoint API](https://ml-explore.github.io/mlx/build/html/python/_autosummary/mlx.core.checkpoint.html) and implemented in the [matching MLX-LM 0.32.2 trainer](https://github.com/ml-explore/mlx-lm/blob/v0.32.2/mlx_lm/tuner/trainer.py). The local installed 0.32.3 API documentation agrees with that contract.

The wrapper also now evaluates the accumulated gradient tree eagerly and clears allocator cache at every microbatch boundary, matching the native trainer's per-step materialization/cache policy instead of waiting until the fourth microbatch's optimizer update. The [official memory API](https://ml-explore.github.io/mlx/build/html/python/memory_management.html) distinguishes allocator cache clearing from active/peak observations. Cache clearing is supplementary here; the recorded cache size shows it cannot by itself explain or fix the large backward peak. Data rows, maximum sequence length 1024, no-truncation policy, seed/order, final-only loss mask, learning rate, effective accumulation, optimizer and all resource limits are unchanged.

Three new failing-first CPU tests covered decoder-class coverage, eager accumulation/cache ordering with a deferred computation graph and unchanged accumulation sum, and the explicit checkpoint CLI argument. RED: 3 failures / 48 passes; GREEN: 51 passes. The ordinary app environment reports 51 passed / one optional MLX test skipped. With only the isolated runtime packages on PYTHONPATH, **52 tests passed in 6.67 seconds**, including a real tiny MLX model explicitly fixed to the CPU device; native checkpointing preserved loss and every gradient within 1e-6. No Qwen weights or GPU model were loaded by those tests. Source code does not change the final-answer mask. Actual Qwen memory reduction and checkpointed backward behavior remain to be verified by a newly authorised smoke and fresh pilot after the coordinator releases the GPU. The pending update-7 weights will not be silently resumed.

## Checkpointed smoke-v2-checkpoint-001 result

After explicit coordinator GO and a fresh no-worker/normal-pressure preflight, exactly one fresh-adapter checkpointed smoke ran as session **76498** and exited **0**. It completed five updates in **24.846479500 seconds** with native gradient checkpointing enabled for all **32 DecoderLayer instances**, the same fixed 2,260,992 adapter parameters, same data/sampling, final-only mask and guards. It did not resume the pending seven-update adapter.

The measured MLX peak was **6,323,789,631 bytes (5.889 GiB)**, **24.73% lower** than the original smoke's 8,401,300,752 bytes (7.824 GiB). Maximum sampled active allocation was 2,640,121,474 bytes. Pressure stayed 1; recorded swap decreased from 3471.50 to 3447.50 MiB. No corresponding model/training worker remained after exit.

All five training losses and development losses were exactly identical to the original smoke: development **1.0687229415824668 → 1.0351127953064152**. All 48 adapter tensors changed, all finite checks passed, and native save/reload matched. The initial file hash remained `7efc031daa087ae3625700e5dd8bb4d6a85e3e0c0f75e640546087148eb2d3e6`; the final and canonical adapter hash was exactly the original smoke's `c28d0d215b8c4c2e077cff0ae34d8a1288a6233961d3eb5f596909cb44cb5367`. This supplies real Qwen GPU evidence that the prepared memory changes preserve the tested learning result while lowering its peak. It does not establish that all 1024-token pilot examples will fit.

The candidate was development accepted; all files are in SSD `stem-tutor-training/smoke-v2-checkpoint-001`, with summary `smoke_summary.json` and log in SSD `tutor-runtime/stem-training/smoke-v2-checkpoint-001.log`. A fresh full pilot awaits a separate coordinator GO; no automatic pilot, inference, fusion or publication ran.

## Checkpointed 1024-token pilot: second safe resource stop

The separately authorised fresh `pilot-v2-checkpoint-001` ran exactly once as session **56208** and stopped with **TrainingStopped / exit 1** after **10 completed optimizer updates**, in **491.240527333 seconds**. The recorded MLX peak was **14,848,926,580 bytes (13.829 GiB)**; maximum sampled active allocation was 2,816,126,389 bytes. The unchanged swap guard fired when its resource snapshot showed **1307.38 MiB additional swap**. Pressure remained 1. No memory, swap or wall-time bound was weakened.

CPU replay of the seed/order identifies the exact triggering work: microbatch **44**, the fourth microbatch of update 11, contained **710 complete tokens / 317 final tokens**. Its backward peak rose from 10,741,330,082 bytes at the earlier 454-token example to 14,848,926,580 bytes. The guard fired before optimizer update 11, so `updates_completed: 10` is accurate; incomplete accumulated gradients were not applied. Initial full-255 development loss remained exactly **0.8506162017844281**, and the first seven training losses were identical to the uncheckpointed pilot. Native checkpointing therefore preserved the learning result and lowered memory for equal-length examples, but the longer 710-token example still exceeded the available physical headroom under the strict swap guard.

Pending `000010_adapters.safetensors` SHA256 is `7703f51fe2802e5281375614fd9e1625efe7ce285c2b08954f53bf12c65f0f40`. CPU reading confirms 48 finite tensors, all 48 changed. It has not received post-training development selection or a native reload. Canonical remains initial `000000_adapters.safetensors` with SHA256 `7efc031daa087ae3625700e5dd8bb4d6a85e3e0c0f75e640546087148eb2d3e6`. All files, summary and microbatch mappings are retained separately from earlier runs. No automatic resume, fallback, fusion or inference followed.

Measured checkpointed peaks at 336, 379 and 454 tokens were approximately 7.96, 8.72 and 10.00 GiB. A local linear estimate from these observations puts 506–512 tokens around **10.9–11.1 GiB**, about 3 GiB below the observed budget; this is an estimate, not a swap-safety guarantee. The coordinator subsequently authorised a fresh bounded 512-token pilot with the same gradient checkpointing, accumulation 4, 100-update maximum, fixed adapters/LR/seed and all resource guards. Entire overlength rows are dropped: **673 training / 246 development** rows remain, versus 704/255 at 1024. No answered sequence is truncated, the original data/manifest stay immutable, and prior pending weights are not resumed. This new run is `pilot-v2-512-001`, session **72543**; its results will be added after a durable checkpoint or terminal state.

## Completed bounded pilot-v2-512-001

The coordinator explicitly authorised the minimal change to a 512-token cap while preserving native gradient checkpointing, batch 1, accumulation 4, seed 42, learning rate 1e-5, rank-8 last-eight MLP adapters and all resource limits. The run used a **fresh adapter from the verified base**, not any smoke or interrupted adapter. Complete overlength rows were dropped rather than truncated; **673 training / 246 development** rows remained from the same immutable data-v2 manifest `439c106584be8268aa6019278ed286359b3ce840d705ddc32c0279e7951bcb9a`. Longest retained train/development sequences were 506/488 tokens. The sealed test file was not opened.

Exactly one job, **session 72543**, completed **100 optimizer updates / 400 training microbatches** and exited **0**. Its GPU-entry elapsed time was **3075.456806375 seconds (51 minutes 15.46 seconds)**, below the one-hour cap. Every loss, gradient, accumulated-gradient and adapter/checkpoint finite check passed. All 48 permitted adapter tensors changed; save/reload into the same loaded base matched exactly. Fresh process inventory after terminal completion showed no model/training workers, and no automatic inference, fusion or follow-on GPU job was started by this agent.

Development selection used all 246 retained development rows, with the same token-weighted final-only loss each time:

| Optimizer update | Development loss | Selection |
| ---: | ---: | --- |
| 0 | 0.9846459448164081 | Initial base/adapter state |
| 25 | 0.4559189389466178 | Accepted |
| 50 | 0.3320067484751648 | Accepted |
| 75 | 0.24924816520344206 | Accepted |
| 100 | 0.17596980919190874 | Accepted and canonical |

The selected checkpoint is therefore **000100**, using development data only. This loss reduction is not a measured correctness/marking score; independent held-out inference and delivery checks remain required before any quality claim or promotion.

Resource evidence from 4,586 recorded observations:

- Peak MLX allocation: **11,697,389,652 bytes (10.894 GiB)**. Maximum sampled active allocation: **2,645,596,988 bytes (2.464 GiB)**. The larger recorded peak includes transients between samples.
- Observed budget remained 14 GiB; the separate MLX allocation guideline remained 12.25 GiB. No hard-cap claim is made.
- Pressure stayed **1 → 1**. Swap decreased **3989.44 → 3685.44 MiB**, a **304 MiB decrease**; the 512 MiB growth guard was never weakened.
- Free SSD capacity decreased **50,371,125,248 → 50,316,201,984 bytes**, remaining well above the 20 GiB guard.

Checkpoint file SHA256 values:

| File | SHA256 |
| --- | --- |
| `000000_adapters.safetensors` | `7efc031daa087ae3625700e5dd8bb4d6a85e3e0c0f75e640546087148eb2d3e6` |
| `000025_adapters.safetensors` | `4d6c8ac9c5586ffb8c91e063cccf708ddad04ef9bbc1862974dc25b7f1666f9d` |
| `000050_adapters.safetensors` | `654d6f2640446fbf68f7424e318ba1055957f38b98eb59b37fe17a78abcedf20` |
| `000075_adapters.safetensors` | `9e3492870154c044914b79e82bb66d7bb5f032157397e98eac1e1803d49e8468` |
| `000100_adapters.safetensors` | `a547604e9f64c35ec999a4666d66b50efc7d462b1e35d4a18c8a055fc5a328ac` |
| `adapters.safetensors` | `a547604e9f64c35ec999a4666d66b50efc7d462b1e35d4a18c8a055fc5a328ac` |

Full initial/final per-tensor hashes, all 100 update losses, development curve, resource observations, dropped/selected row IDs and immutable base/template/data hashes remain in `pilot-v2-512-001/training_receipt.json`; the compact result is `pilot_summary.json`. Complete stdout/stderr is SSD `tutor-runtime/stem-training/pilot-v2-512-001.log`. The original snapshots, previous adapters, checkpointed smoke and both interrupted 1024-token pilots remain intact.
