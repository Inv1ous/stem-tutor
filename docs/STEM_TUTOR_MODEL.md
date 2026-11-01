# Experimental STEM Tutor 4B

Status, 27 October 2026: the bounded experiment is complete. The model was trained, exported and imported into
native MLX on this Mac, but failed the promotion gates. It remains an SSD research artifact, outside the tutor's
model menu and presets. Existing selections and presets stay unchanged.

## What was built

This is a LoRA adaptation of the pinned Apache-2.0 Qwen3.5-4B MLX conversion, merged with its own base.
It is not a new foundation model or a mixture of unrelated model architectures. Training changed 2,260,992
parameters in 24 MLP projections across the last eight decoder layers. The exported model keeps those learned
projections in BF16 and the remaining text weights in their original 4-bit representation. Its weights occupy
3,181,190,307 bytes. Original models, base weights and adapters remain on the external SSD.

The unused vision branch was omitted from this text model. The tutor's separate on-device OCR can supply literal
image text; this does not establish graph, diagram or handwriting understanding. Removing a vision branch is
different from deleting arbitrary non-STEM knowledge, which is distributed through the text model's weights.

Base and attribution: [pinned community conversion](https://huggingface.co/mlx-community/Qwen3.5-4B-4bit/tree/0e7ffd5c629ef7719d4cbc04069232580bfa9d9c),
[pinned upstream model](https://huggingface.co/Qwen/Qwen3.5-4B/tree/851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a),
and the preserved upstream licence inside the SSD artifact.

## Training and format

The public/synthetic corpus has 705 training, 255 development and 278 test rows, split by syllabus/question family.
The accepted 512-token run used 673 complete training rows and 246 complete development rows; overlength examples
were dropped whole. No learner logs, private screenshots or hidden model reasoning were used. Marking examples
are a small minority of this pilot, so the corpus is not a comprehensive examiner dataset.

The 100-update run took 51 minutes 15 seconds on the M4 MacBook Air with 24 GiB memory. Gradient checkpointing
reduced the smoke run's measured peak memory by 24.7% while preserving its losses and saved adapter bytes.
The accepted run's development loss fell from 0.98465 to 0.17597. Lower loss does not establish scientific accuracy.
See the [training evidence](benchmarks/2026-10-26-stem-model-pilot/training-evidence.png).

Training teaches the tutor's paragraph, heading, bullet, step, equation and code blocks, plus separate speech.
The app still owns layout and validates replies. Compact prompting has **not** passed its reliability gate;
the production formatting instructions and native schema constraints must remain. Current questions, syllabus
versions and actual mark schemes are still necessary context.

## Strengths

Two genuine native modes were tested: **Fast** uses thinking off; **Deep** uses thinking on. These are not
invented low/medium/high levels. Fast delivered all six development documents with the compatibility experiment,
but content-fidelity checks failed. Deep generated 4,096 tokens in 167.54 seconds without a public final answer.
Neither result justifies adding a new ready-to-use tutor strength or preset.

## Evidence and limitations

- [Preserved raw evaluation](benchmarks/2026-10-26-stem-model-pilot/evaluation-v1-fast-main-report.md): the adapter
  improved raw document adherence, but compact-format and marking-envelope requirements failed. The first protocol
  also added a system directive absent from training; its marking results are not a clean semantic comparison.
- [Development protocol test](benchmarks/2026-10-26-stem-model-pilot/development-protocol-run-report.md): changing
  roles alone did not recover marking envelopes.
- [Development sampling test](benchmarks/2026-10-26-stem-model-pilot/development-sampling-run-report.md): removing
  presence penalty raised document validity from 5/6 to 6/6 but reduced delivery from 17/18 to 12/18 and did not
  restore marking. The reference setting is retained. These six correlated groups are not a reliability estimate.
- [Independent quality audit](benchmarks/2026-10-26-stem-model-pilot/quality-v1-audit.md): copied reference defects,
  model-added errors, missing results and explicit false-credit judgements remain. Unavailable grading vectors are
  reported separately from observed wrong decisions. This pilot has not earned a scientific-superiority claim.
- [Fusion checks](benchmarks/2026-10-26-stem-model-pilot/fusion-execution-report.md): all saved tensors reload exactly;
  the original untrained text tensors remain unchanged. Live-adapter versus fused logits passed the predeclared
  screens, including 286/288 top predictions and all 18 first-answer predictions. This is not numerical identity
  or proof of equal generated answers.
- [Generated-answer fusion comparison](benchmarks/2026-10-26-stem-model-pilot/fusion-answer-parity-run-report.md):
  the fused model completed all 18 development requests, but only seven public texts were identical to the adapter.
  Marking envelopes still failed. Floating fusion can change sampled answers despite close logits.
- [First native trial](benchmarks/2026-10-26-stem-model-pilot/native-runtime-report.md): actual `runner: mlx`,
  successful empty preloads and genuine Fast Off were verified. An incorrect calculation repeated until the
  4096-token limit. A separate recorder exception was reproduced and fixed with CPU regressions; the original
  model failure remains preserved.
- [Controlled native diagnosis](benchmarks/2026-10-26-stem-model-pilot/native-development-diagnostic-report.md):
  a matched full-instruction request passed mathematics, speech and document validation in 6.65 seconds without
  native grammar, while adding native grammar produced a looping equation. This single development pair is not
  proof of a general runtime defect.
- [Broader development compatibility test](benchmarks/2026-10-26-stem-model-pilot/native-development-compat-report.md):
  omitting only native document constraints retained full instructions and strict host validation. All six
  documents delivered and all three literal code blocks matched. One marking check returned the correct
  `[true,false]` vector. However, a supplied mathematics formula was omitted, extra unsupported explanations
  were added, marking feedback was misleading, and Deep still failed delivery. Structural success did not pass
  the content/strength gates. This workaround was not added to production.

No further weights were tuned on the examined test failures. The remaining large native confirmation batch and
custom-model UI integration were not run after the failed gates. The original shared-format UI verification
remains separate and includes real terminal and Obsidian captures.

All model files, checkpoints, data and raw receipts live under `/Volumes/External SSD TB4/LocalAI`.
No cloud training or model upload occurred. Existing Claude/ChatGPT selections, credentials and reasoning settings
remain unchanged. The experimental model will not replace an existing preset automatically.
