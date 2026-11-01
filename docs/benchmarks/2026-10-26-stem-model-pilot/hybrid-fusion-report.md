# Hybrid fusion utility: CPU preflight

Status: implemented and CPU-tested; **no actual model loading, fusion, native import or inference has run** through
this utility. The coordinating agent owns the exclusive GPU queue and must release the completed training job first.

`app/tutor_app/stem_training_fuse.py` uses the installed MLX-LM public APIs to fuse only the 24 trained MLP linears:
`language_model.model.layers.{24..31}.mlp.{gate_proj,up_proj,down_proj}`. Each is replaced by
`LoRALinear.fuse(dequantize=True)`. All remaining modules retain their original packed representation. The global
affine 4-bit/group-64 configuration is retained with explicit `False` overrides for the 24 floating modules.
Native `utils.save` mirrors the quantisation configuration and removes unused vision metadata.

This avoids another 4-bit rounding step for the learned update. It is **not numerically identical to live LoRA**:
the native fusion implementation rounds the delta to the dequantised weight dtype before addition. Separate
logit/answer comparisons and held-out quality checks remain mandatory. The utility never invokes whole-model
dequantisation, requantisation, `ollama create`, `--force`, cloud services or Git commands.

## Preflight and preservation

Preparation is standard-library-only and writes no model output. It verifies the pinned upstream/base receipt,
the original source file hashes and upstream licence. It requires a real nonzero development-accepted **pilot**
checkpoint, finite development assessment at that update, completed updates at least that large, exact agreement
between the canonical adapter and selected checkpoint, and changed bytes versus the initial untrained adapter.
The adapter configuration and actual safetensor names must match the 48 permitted adapter tensors.

A stopped pilot can legitimately supply its prior accepted checkpoint. A later pending or rejected checkpoint is
not selected. Trainer `adapter_reload_verified` is not required for this case because the utility performs its own
saved-model reload check. A smoke-only run and a stopped pilot whose canonical adapter is still update zero are
ineligible.

All paths must remain on the external SSD. Output must be new and separate from both sources. Adapter files and
token assets cannot escape their own source directory through symlinks. Execution reconstructs and compares the
prepared plan before creating output, then rechecks source hashes before successful completion. Sources are never
overwritten.

Every tokenisation/template/generation asset is frozen, including vocabulary, added/special-token files and any
generation configuration. Native tokenizer saving can create additional files; the new output is restored to the
original generation-asset file set and exact bytes. Runtime vocabulary, chat-template, thought-boundary and stop IDs
are checked again after reload. Licence and provenance are copied into the new artifact.

## Runtime proof that execution must collect

The utility serialises the loaded adapter model temporarily and hashes each raw safetensor region with bounded
CPU reads. This handles BF16 bytes directly without NumPy dtype conversion. After saving, every tensor outside the
24 trained module prefixes must match byte-for-byte, including shape and dtype. Each trained module must contain
one floating weight of the shape implied by its packed 4-bit base. Native reload must preserve all saved tensor
bytes, dtypes and shapes and keep the 24 modules floating. Temporary snapshots are removed from the new output.

The same resource policy as training applies: normal memory pressure before importing MLX/loading the model;
14 GiB observed active/peak budget with a lower allocation guideline; at most 512 MiB additional swap; at least
20 GiB SSD headroom; sustained-warning/critical-pressure stops; and a 600-second operation deadline. Active and peak
memory are checked immediately after loading and after each safe operation. These checks cannot interrupt an
in-flight kernel. Partial outputs retain a failed/stopped receipt and are not ready for registration.

The default CLI prints a full reviewable JSON preparation receipt. `--execute` is the separate explicit GPU path:

```sh
PYTHONPATH=app '/Volumes/External SSD TB4/LocalAI/tutor-runtime/stem-training/.venv/bin/python' \
  -m tutor_app.stem_training_fuse \
  --base-model '/Volumes/External SSD TB4/LocalAI/models/mlx-community/Qwen3.5-4B-4bit' \
  --base-receipt '/Volumes/External SSD TB4/LocalAI/stem-tutor-training/base-receipt.json' \
  --adapter-dir '/Volumes/External SSD TB4/LocalAI/stem-tutor-training/PILOT_DIRECTORY' \
  --output '/Volumes/External SSD TB4/LocalAI/models/stem-tutor-qwen35-hybrid-v1'
```

Replace `PILOT_DIRECTORY` with the actual development-selected, terminal pilot directory. Add `--execute` only after
the coordinator grants this operation exclusive GPU ownership. The example command above has not been executed.

## Verification

TDD began with 20 failing missing-feature tests. Subsequent failing-first tests covered missing preservation,
resource-order, CLI receipt and source-path checks before correction. The final fusion suite contains **30 passing
CPU tests**. The combined fusion/trainer/data/evaluator gate is **123 passed, 1 skipped**; the skip is the trainer's
optional installed-MLX test in the main app environment. CLI help and scoped `git diff --check` pass.

CPU checks include raw BF16/packed hashes, unsafe offsets/shapes, exact module scope, original global quantisation,
unchanged non-target tensors, target shape/dtype rejection, source/asset/licence mutation, new SSD paths, symlink
escapes, canonical/accepted/initial separation, early-stop selection and no accidental MLX import during preparation.
A simulated 17 GiB load peak stops before any fusion, records the actual load phase and overrun, and cleans up.
A simulated system-pressure failure is recorded before any MLX import.

These are orchestration/preservation proofs, not GPU compatibility or model quality results. The coordinator owns
the final canonical full-project suite; no competing broad suite or GPU task was launched by this builder.

Primary implementation references: [MLX-LM v0.32.2 LoRA fusion](https://github.com/ml-explore/mlx-lm/blob/v0.32.2/mlx_lm/tuner/lora.py),
[MLX-LM save/load](https://github.com/ml-explore/mlx-lm/blob/v0.32.2/mlx_lm/utils.py),
[native Ollama prequantised import](https://github.com/ollama/ollama/blob/675150d6ad2747df1e218ef59de9194bc4a7e538/create/prequant.go#L170),
and [native floating/quantised linear loading](https://github.com/ollama/ollama/blob/675150d6ad2747df1e218ef59de9194bc4a7e538/mlxrunner/model/linear.go#L57).
