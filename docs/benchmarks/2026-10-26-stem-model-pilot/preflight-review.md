# STEM pilot preflight review

26 October 2026. Independent, read-only review of the new trainer/data builder,
their targeted tests, the pilot spec/plan/research, installed pinned library source,
and immutable dataset v2. No model loading, GPU work, training, dependency changes,
or broad test suite was performed. This report is the sole file written by the reviewer.

**Result: two actionable findings. Address the memory guard before GPU execution.**

## Findings

### P1 — The requested MLX memory budget is not enforced

Location: `app/tutor_app/stem_training.py:405–412`.

The only device-budget operation is `mx.set_memory_limit(...)`; the resource guard
checks system pressure, swap growth and free disk but never checks live/peak MLX
allocation against `config.memory_limit_gib`. The installed MLX 0.32.3 API explicitly
describes this setting as a *guideline*, and says allocation fails only after the
limit is exceeded **and** no RAM/swap remains. See the installed
`mlx/core/__init__.pyi:867–883` under the isolated training environment.
Consequently a 17 GiB MLX working set with normal pressure and unchanged swap passes
every current guard even though the configured maximum is 16 GiB. This also means
the runtime report's statement that allocation is capped at 16 GiB is too strong.

Add an explicit current/peak allocation budget check at safe evaluation boundaries,
including after loading, gradient evaluation, update and validation, with a CPU
regression using an injected memory probe. Keep the allocation guideline and the
system pressure/swap guards. Explain that an individual in-flight operation can
overshoot before a cooperative check; do not claim a hard OS/process cap.

### P2 — Final development deterioration is reported as success

Location: `app/tutor_app/stem_training.py:371–376`.

Intermediate evaluations compare against `best_validation`, but the final evaluation
only checks finiteness and unconditionally sets `state='completed'`. For the five-step
smoke, this is the only evaluation after any training. For a 100-update pilot, it
misses deterioration in the final 25 updates. The `finally` checkpoint also publishes
the final adapter as canonical even when it is worse than an earlier checkpoint.

CPU reproduction: call `run_updates(TrainingConfig(), backend, RunGuard(3600), {})`
with `backend.evaluate()` returning 1.0 then 2.0, `micro_step()` returning `(1.0, 3)`,
and inert `update()`. Actual result: `state='completed'`, validation losses
`[{update:0,loss:1.0},{update:5,loss:2.0}]`, checkpoints `[0,5]`.

Apply the same deterioration gate to final validation. Record/select the best
development checkpoint explicitly before later evaluation/fusion instead of treating
the canonical last checkpoint as the selected model. Add a regression for final
deterioration, including the smoke path.

## Verified evidence

- Targeted CPU tests: **57 passed** (`test_stem_training.py` and
  `test_stem_training_data.py`, bytecode and pytest cache writing disabled).
- Dataset manifest SHA256 is
  `439c106584be8268aa6019278ed286359b3ce840d705ddc32c0279e7951bcb9a`.
  Train/dev/test hashes and counts match the manifest: **705/255/278**.
- All pairwise group and ID intersections are empty. Cross-split normalized gold
  duplicates and public original-question signature duplicates are both zero.
  This is exact/normalized duplicate evidence, not proof of semantic independence.
- All document targets round-trip through `DocumentDecoder` without repair; no
  odd dollar-delimiter count in non-code blocks or hidden think markup was found.
  All assistant JSON equals `expected`. The builder reads the published pack glob
  only, rejects symlink escapes, and does not consume learner logs or model outputs.
- Reviewed curated formulas, domain conditions and marking truth tables against
  their explicit claims: no factual/label error identified. The source registry
  supplies primary-source URLs/locations and distinguishes claim hashes from source
  byte hashes. This review did not independently re-fetch the cited web sources or
  rederive the published source-transcription corpus.
- CPU-only pinned native-tokenizer audit covered **all 960 train/dev rows**.
  For every row the masked prefix ends with `</think>\n\n`; the supervised suffix
  equals the exact assistant JSON plus `<|im_end|>\n`. The native end-of-message
  token is 248046. No boundary mismatch occurred and **MLX was not imported**.
  The wrapper requests `return_dict=False` for Transformers 5 native template IDs.
  Its shifted-target mask includes the first public token and end-of-message token.
- Complete-sequence counts are **673/705 train, 246/255 dev at 512**, and
  **704/705 train, 255/255 dev at 1024**. Overlength rows are dropped whole;
  targets are never truncated. The historical v1 preparation counts must not be
  used as v2 evidence.
- Pinned model config and installed LoRA constructor imply
  `8 layers × 3 projections × rank 8 × (2560 + 9216) = 2,260,992` trainable
  parameters. Base freezing precedes replacement; the last-eight-layer projection
  keys, 48-tensor count and adapter-name allowlist match the requested scope.
  Actual loaded-model shapes and gradient behavior remain smoke-test evidence.
- CLI defaults to CPU tokenizer preparation. GPU execution requires explicit
  `--execute` plus the pinned base receipt. Receipt identity, required files, sizes
  and SHA256 are checked before tokenizer/model loading. Output must be a new SSD
  directory separate from base/data; no original-weight write path was found.
- Cooperative wall deadline and SIGINT/SIGTERM handling, initial normal-pressure
  requirement, sustained warning/critical pressure, swap growth, free disk checks,
  finite loss/gradient/parameter checks and adapter-only atomic checkpointing are
  present. Initial/every-25/final checkpoints provide recovery; process death or
  failure before a checkpoint can preserve only earlier saved state.

## Remaining execution gates

The root coordinator still owns the completed and verified base receipt, GPU
exclusivity, frozen native base Off/On development inference, fresh v2 preparation,
and the explicit decision to execute smoke. No success or quality claim follows
from this review. Backward-pass compatibility, real adapter change/reload, measured
peak memory, held-out improvement, fusion and native import remain untested here.
