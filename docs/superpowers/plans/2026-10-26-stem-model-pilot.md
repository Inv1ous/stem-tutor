# Experimental STEM Tutor model Implementation Plan

> **For agentic workers:** Use bounded parallel data/runtime work and independent review. No training overlaps the active inference benchmark.

**Goal:** Try a measured local STEM-specific LoRA model with learned output format and native Fast/Deep modes.
**Spec:** `docs/superpowers/specs/2026-10-26-stem-model-pilot-design.md`.
**Authorisation:** User explicitly requested the experiment, SSD downloads and routine optimisation choices; originals remain untouched.

- [x] Create isolated pinned SSD training runtime and verified pinned MLX base receipt; preserve upstream license.
- [x] Build reproducible public/synthetic dataset with provenance, validation and group-disjoint train/dev/test splits.
- [x] Write regression tests for data leakage, exact source preservation, deterministic math truth, and correct final-answer loss mask.
- [x] Run base inference/evaluation only after active benchmark93430 completes; no concurrent GPU job.
- [x] Run five-update smoke with explicit memory bound; prove adapter changes, finite loss and reload.
- [x] Run bounded pilot only if smoke passes; choose checkpoint on development data, preserve sealed evaluation.
- [x] Evaluate base/adapter, native Fast/Deep and fusion; report quality and timing separately.
- [x] Attempt a new native MLX Ollama alias; verify the actual runner and empty-preload readiness. Stop the deployment sequence when promotion gates fail.
- [x] Decide exposure and recommendation using the gates: retain the artifact but add no model choice or preset after content/Deep failures.
- [x] Verify original shared-output integration/screenshots and final software checks; review Standards/Spec. Custom-model UI integration is withheld by the failed pilot gates.

Ruling: all model/data/cache writes go to SSD; no original model mutation, cloud training, uploads or Git writes.
Ruling: native Off/On are two genuine strengths. No unsupported low/medium/high API is invented.
Ruling: current original-model full matrix remains authoritative process93430; do not restart it because a poll yields.

## Checkpoint: 27 October, 02:00 Hong Kong

The accepted pilot completed 100 updates at 512 tokens with native gradient checkpointing. Its complete
development loss fell from 0.98465 to 0.17597; this is training evidence, not an accuracy claim. All original,
failed and accepted checkpoints remain on the SSD. See the benchmark directory for receipts and plots.

The first 240 raw base/adapter responses and a 54-response development protocol contrast are preserved.
Compact-format and marking-envelope gates have not passed. A reviewed, fresh 36-response development test
now changes only Fast presence penalty (1.5 versus 0) under the exact training protocol. No extra training
is authorised by these scores alone. Production schema-constrained behaviour, Deep, fusion, native MLX
import, and final app integration remain separate gates. Existing model choices are unchanged.

## Final pilot outcome: not promoted

Training, fusion, native import and numerical screens completed. Original failures remain preserved. A controlled
native compatibility experiment delivered six strict documents and exact literal code, but lost a supplied maths
formula, added unsupported explanations and gave misleading grading feedback. Genuine Deep exhausted 4,096 tokens
without a public answer. The promotion gates therefore failed. No production compatibility bypass, catalogue entry,
custom preset or compact brief was added. No further training used the examined test answers.

The remaining large native challenge batch and custom-model image/UI checks are conditionally skipped after that
decision, rather than reported as passes. The existing model UI and original shared-output screenshots remain
verified independently. Final project verification and review complete the closeout below.

Final closeout: [4,690 passing software tests, one optional skip, independent review and preservation](../../benchmarks/2026-10-26-stem-model-pilot/final-verification.md).
