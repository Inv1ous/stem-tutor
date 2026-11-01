# Paired evaluation harness

The evaluator is implemented in `app/tutor_app/stem_training_eval.py`. It does not alter tutor providers, settings,
installed models, the learner vault or the training dataset. No GPU generation was launched while building it.
The final project-wide test run remains owned by the root agent.

## Frozen selection and evidence

`freeze` verifies the immutable dataset manifest and sealed test-file SHA256. It selects at most 40 rows per subject,
balancing task metadata by round-robin and ordering rows by SHA256(seed:id). Selection never consults answers,
questions or evaluation results. The immutable receipt records ordered IDs, input hashes, task counts and both row
and group counts. Speech variants and other examples in one group remain correlated; 120 rows must not be described
as 120 independent scientific problems.

Root subsequently froze `stem-tutor-training/evaluation-selection-v1.json` on the SSD: 120 rows, 40 per subject,
31 groups. Its actual metadata shows no literal-code or speech cases and only one OPEN hint. Therefore this selection
does not establish coverage of those formats or protections. A separately frozen challenge suite must cover literal
code, speech, OPEN protection and mathematical formatting before promotion. Deep-mode generation also requires its
own completed measurements; selection alone establishes no reasoning-mode outcome.

`generate` loads one base, adapter or fused variant and one genuine Fast/Deep mode. Both modes use the pinned native
chat template. V1 prepended the compact system identity `STEM Tutor. Reply in document JSON.`; the later protocol
review established that this differs from training and can conflict with marking requests. V1 remains immutable.
V2 defaults to the `training` protocol, using only the unchanged dataset user message. Explicit `legacy_system` and
`neutral_system` conditions support the separately frozen development contrast; see
[the extension report](evaluator-protocol-extension-report.md). Gold answers, scoring checks, added format examples
and native output grammars are excluded from generation prompts.
The same resolved sampler, seed, total token budget and per-request deadline apply to both arms of a paired comparison.
The default budget is 4096 total generated tokens and 180 seconds; a frozen comparison may instead explicitly choose
up to 8192 tokens and 300 seconds. Deep tokens count towards that budget. Length stops remain failures.

Only final token IDs are decoded and stored. Thought token IDs are immediately discarded after incrementing a count;
the evaluator never reads streaming `text`, which can include hidden thoughts. Final answers, task IDs, groups, prompt
hashes, timing, token counts, memory observations and immutable hashes of every regular model/adapter root file are
retained. This includes generation configuration, vocabulary, tokenizer auxiliary files and weight indexes. Each
started request has a separate immutable marker with a stable attempt number; its terminal file uses the same number.
Unmatched starts are scored as interrupted attempts, distinct from rows never started. Every retry receives a new
number and preserves the interrupted/error history. Resume retries interrupted trials and skips terminal trials by
default. Explicit `--retry-failed` also retries the latest failed terminal outcome, including a length stop.
An advisory file lock prevents simultaneous invocations against the same output directory. Root still coordinates
GPU ownership across different jobs and directories.

`first_final_token_seconds` measures the first final token, including possible JSON syntax. It is deliberately not
labelled time to the first app-rendered human-readable block. Load time and native Ollama compatibility are also
separate measurements. MLX allocation limits are guidelines, accompanied by observed peak checks and the existing
pressure/swap/free-disk guards; no claim of interrupting an in-flight GPU kernel is made. Run peak is reset before
loading, observed active/peak allocation is checked immediately after evaluated loading, and load peaks/failures are
preserved in immutable `load.NNN.json` receipts. Tokenizer-boundary failures also pass through model cleanup. The
previous request's observed allocation is checked before clearing/resetting per-request peaks.

## Separate scoring

CPU-only `score` uses the actual app decoder. Fences, narration, duplicate keys and wrong envelopes fail raw-format
checks. A document accepted only after the app's narrow repair is reported as host-valid and repaired, but not raw
contract-valid. Length stops, errors and missing answers cannot earn delivered/valid status even when a partial string
looks like a complete object.

Marking requires exact criterion order/names and strict Boolean labels. Label agreement is scored independently of
the explanation's scientific quality. Literal code is compared exactly, including newlines and quotes, and is never
executed. Source-copy equality is labelled fidelity evidence rather than independent knowledge. Exact document match
is a conservative inspection aid, not a paraphrase-aware mathematical or scientific accuracy score. Scientific
correctness, requested coverage and OPEN-answer protection remain explicitly marked for manual review.

`pair` refuses different modes, generation settings, samplers, selection hashes, evaluation code or base weights
(base-versus-adapter). Both adapter and fused comparisons require matching tokenizer/template/generation assets and
the same actually loaded thought-boundary and stop-token IDs. Successful load receipts are required, and inconsistent
resolved protocol IDs across resumes are rejected. It also compares actual prompt hashes for corresponding attempts.
The report preserves all attempts and displays the latest terminal or interrupted attempt per ID; it does not choose
the best retry. Null means no start or result was recorded. Fusion may have different weights/model configuration but
must retain this paired tokenizer/protocol contract.

## Commands after root grants exclusive GPU ownership

Run from the repository. The selection command is CPU-only and should be run exactly once into a fresh filename.
Keep generation output directories separate for every variant/mode/configuration.

```sh
STEM_RUN='/Volumes/External SSD TB4/LocalAI/stem-tutor-training'
STEM_PY='/Volumes/External SSD TB4/LocalAI/tutor-runtime/stem-training/.venv/bin/python'
STEM_BASE='/Volumes/External SSD TB4/LocalAI/models/mlx-community/Qwen3.5-4B-4bit'

PYTHONPATH=app .venv/bin/python -m tutor_app.stem_training_eval freeze \
  --data "$STEM_RUN/data-v2" --selection "$STEM_RUN/evaluation-selection-v1.json"

PYTHONPATH=app "$STEM_PY" -m tutor_app.stem_training_eval generate \
  --data "$STEM_RUN/data-v2" --selection "$STEM_RUN/evaluation-selection-v1.json" \
  --model "$STEM_BASE" --variant base --mode fast \
  --output "$STEM_RUN/eval-base-fast-v1" --execute

# Replace SELECTED_ADAPTER with the development-accepted adapter directory.
PYTHONPATH=app "$STEM_PY" -m tutor_app.stem_training_eval generate \
  --data "$STEM_RUN/data-v2" --selection "$STEM_RUN/evaluation-selection-v1.json" \
  --model "$STEM_BASE" --adapter SELECTED_ADAPTER --variant adapter --mode fast \
  --output "$STEM_RUN/eval-adapter-fast-v1" --execute

PYTHONPATH=app .venv/bin/python -m tutor_app.stem_training_eval pair \
  --data "$STEM_RUN/data-v2" --selection "$STEM_RUN/evaluation-selection-v1.json" \
  --baseline "$STEM_RUN/eval-base-fast-v1" --candidate "$STEM_RUN/eval-adapter-fast-v1" \
  > "$STEM_RUN/eval-fast-paired-v1.json"
```

The isolated MLX environment runs generation without importing Rich or MarkdownIt. CPU scoring runs in the project's
normal environment. No dependency installation or inference-stack mutation is needed for this separation.

## Verification

Test-first failures were observed for the missing evaluator, retry policy, paired-run validation and memory bounds.
The evaluator's 27 tests cover metadata-only deterministic selection, immutable hashes and IDs, duplicate keys/fences,
raw versus repaired format, scientific-quality separation, exact source/code fidelity, strict marking labels, length
stops, hidden-token disposal, resume/retry preservation and paired-setting validation. Independent preflight findings
were reproduced before fixes: generation-config hashing, fused tokenizer compatibility, interrupted-start reporting,
and observed load-memory/cleanup handling. The latter uses a stub only at the external GPU boundary: a simulated
17 GiB load peak must abort before generation, retain the peak/error receipt and execute cleanup; a malformed thought
boundary must also retain its failure and clean up. No real model was loaded by these tests.

Latest focused command:

```sh
.venv/bin/python -m pytest tests/app/test_stem_training_eval.py \
  tests/app/test_stem_training_data.py tests/app/test_stem_training.py -q
```

Result: **91 passed, 1 skipped** (the trainer's explicit optional GPU integration test). CLI help also ran successfully
without importing MLX. Real MLX generation, held-out science review, fusion and native Ollama compatibility remain
required evidence; these CPU tests do not establish those outcomes.
