# Hybrid fusion preflight review

27 October 2026. Independent review of `stem_training_fuse.py`, its focused tests,
`hybrid-fusion-report.md`, and the installed MLX-LM 0.32.2 load/save/LoRA/Qwen3.5
implementation. No model loading, GPU work, product edits, dependency changes or
broad suite. The active training job retained exclusive GPU ownership.

**Findings: 0 concrete serious defects identified.** The implementation is ready
for the coordinator's bounded execution attempt after training becomes terminal.
This review does not establish successful fusion, numerical parity or native import.

## API and transformation checks

- Installed `mlx_lm.utils.load` accepts `return_config=True`, returns model,
  tokenizer and effective config, and supports the supplied adapter and trust/local
  tokenizer arguments. The reload correctly requests the normal two-value result.
- Installed `LoRALinear.fuse(dequantize=True)` dequantizes the base linear, forms
  the scaled low-rank delta, casts it to the base floating dtype and adds it. Its
  re-quantization branch is skipped when `dequantize=True`. The utility applies
  this only to the exact 24 permitted last-eight-layer MLP modules; it never calls
  whole-model dequantization or another quantization pass.
- Installed loader `class_predicate` returns explicit per-module quantization
  entries, including `False`. The utility retains affine 4-bit/group-64 globals
  and disables quantization only for the 24 fused module names. Installed native
  `save` accepts `donate_model=False`, serializes model parameters directly,
  mirrors the quantization metadata and removes unused vision configuration.
- The Qwen3.5 wrapper retains `language_model.model...` module names. Its sanitizer
  preserves these already normalized names, and its convolution/layout condition
  avoids repeating the original normalization adjustment on sanitized weights.
  The utility's full saved-versus-reloaded tensor inventory will detect a contrary
  actual result before marking fusion complete.

## Safety and evidence checks

- Preparation is standard-library-only and creates no model output. It requires
  pinned verified base identity/hashes, upstream license integrity, a nonzero
  accepted pilot checkpoint with finite development evidence, canonical/selected
  byte equality, changed bytes versus the initial adapter, and exact 48-tensor
  adapter scope/configuration. A stopped pilot can use its prior accepted canonical
  checkpoint; pending/rejected candidates are not substituted for it.
- Output is new, on the SSD and separate from both sources. Input file symlink
  escapes are rejected. Execution rebuilds and compares the preparation plan,
  then verifies source identity again before completion. No original-weight
  overwrite path was found.
- Normal pressure is checked before MLX import/load. The existing guards enforce
  observed 14 GiB active/peak budget, 512 MiB additional swap and 20 GiB free-space
  thresholds, with a 600-second cooperative deadline. Load observations occur
  before inspecting/fusing modules. Subsequent evaluation/save/reload boundaries
  are observed; historical peak is not cleared to hide a violation. Partial
  outputs receive stopped/failed receipts and temporary tensor snapshots are
  cleaned up.
- A serialized pre-fusion adapter-model snapshot supplies raw dtype/shape/byte
  hashes. Every tensor outside target module prefixes must remain identical.
  Each target must become one floating matrix of the shape implied by its packed
  4-bit base, without leftover quantization or LoRA tensors. A second serialized
  snapshot after independent reload must equal the saved inventory exactly.
- Generation assets are restored from the base's exact file set/bytes after
  tokenizer saving. Runtime vocabulary, chat template, thought boundaries and
  stop IDs must also match after reload. License and source provenance accompany
  the new artifact.

## Verification and remaining gates

`tests/app/test_stem_training_fuse.py`: **30 passed in 0.35 seconds**, with bytecode
and pytest cache writes disabled. Tests include changed source/token/license
identity, incorrect scope/layout, output and symlink safeguards, rejected/initial
checkpoint exclusion, prior-accepted early-stop selection, and CPU-stub failure
paths. A simulated 17 GiB load is stopped before fusion and recorded; abnormal
system pressure is recorded before MLX import.

The native-import source research supplied with the implementation supports a
mixed floating/packed candidate, but this review did not perform native registration
or prove runtime importer compatibility. Actual fusion/reload, adapter-versus-fused
logit and answer comparisons, Fast/Deep behavior, resource/latency measurements and
held-out scientific quality remain mandatory downstream evidence.

Floating fusion is explicitly **not lossless live-LoRA equivalence**: the native
delta cast/addition can round differently from applying the adapter during forward
execution. Preserved untrained bytes and successful reload do not replace those
numerical and behavioral comparisons.
