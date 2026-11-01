# Evaluation preflight re-review

26 October 2026. Scoped review of the four findings in `preflight-eval-review.md`
and their changes in `stem_training_eval.py` and focused tests. No real model load,
GPU execution, dependency changes, broad suite or product edits.

**Verdict: all four findings ADDRESSED. No new serious issue identified within
these fixes. The prior evaluator review objections are cleared.**

| Original finding | Verdict | Verified correction |
| --- | --- | --- |
| P1: load peak erased before observation | ADDRESSED | Peak resets before loading. Eager load/evaluation is followed by active/peak checks before generation. Load failures and invalid thought boundaries write immutable `load.NNN.json` evidence and execute cleanup. Successful load peak remains separately recorded before per-request resets. |
| P2: omitted generation configuration identity | ADDRESSED | `_model_hashes` records every top-level model/adapter file, including generation configuration, vocabulary, merges and auxiliary tokenizer files. Changing `generation_config.json` changes identity. Resolved thought/stop IDs are separately recorded after loading. |
| P2: fused pair allows tokenizer mismatch | ADDRESSED | Both adapter and fused comparisons require equal tokenizer/template/generation asset identities and stable successful resolved thought/stop identities. Different fused weights are permitted; changed protocol assets or stop IDs are rejected. |
| P2: interrupted starts treated as unattempted | ADDRESSED | Starts and terminals share stable attempt numbers. `read_attempts` reconciles them; orphan starts become explicit interrupted failures. Interrupted attempts remain scored while resume uses a later attempt number. Pair wording reserves null for no recorded start/result. |

Verification: **78 passed, 1 skipped** in 0.23 seconds for the evaluator and trainer
test modules, with Python bytecode and pytest cache writes disabled. The optional
native MLX parity test was skipped in the normal project runtime; no native GPU
or model invocation occurred.

The reproduced failure-path tests now verify that a simulated 17 GiB load peak
causes only reset → load → cleanup, with no generation, and preserves the error and
peak. Invalid thought-boundary setup also cleans up and preserves its failure.
Identity tests verify generation-config mutation changes hashes and fused
tokenizer/template/stop mismatches fail. Attempt tests verify interrupted attempt 1
remains present after successful attempt 2 and prevents neither safe resume nor
accurate failure accounting.

This is a scoped code-review clearance, not evidence of held-out model quality,
fusion equivalence or native serving compatibility. Those remain the coordinator's
post-pilot evaluation gates under exclusive GPU ownership.
