# Evaluation and training-memory preflight review

26 October 2026. Scope: `stem_training_eval.py`, its tests/report, and the native
gradient-checkpoint/materialized-accumulation changes in `stem_training.py`, against
the existing pilot design and plan. No GPU launch, real model load, dependencies,
product edits or broad suite. This report is the only retained review artifact.

**Four actionable evaluator findings; no new serious trainer-memory defect found.**
The evaluator findings should be fixed before using its output as paired promotion
evidence. They do not require changing the training objective.

## Findings

### P1 — Observe load memory before clearing its peak and starting generation

Location: `app/tutor_app/stem_training_eval.py:309–328`.

The model is eagerly loaded and evaluated without an observed allocation check.
The first trial then resets peak memory before the only allocation check, which is
inside the response-token loop at lines 353–354. A transient model/adapter-load
peak over the 14 GiB budget is erased; even a failed thought-boundary check occurs
before entering the model cleanup `try/finally`. The allocation guideline alone
cannot enforce this budget, as established in the trainer preflight.

CPU reproduction used stub MLX/load/stream objects: load peak 17 GiB, reset peak to
1 byte, then one token. `run_generation` returned a complete attempt under the
14 GiB configuration and the recorded sequence was reset followed by generation.
No real MLX or model was invoked.

Put loading and boundary setup inside cleanup/failure handling; reset the run peak
before loading, check observed active/peak immediately after evaluated loading and
before any generation, and preserve load-peak/failure evidence separately from
per-request peaks. Keep the documented cooperative/in-flight limitation.

### P2 — Hash generation configuration because it changes stopping behavior

Location: `app/tutor_app/stem_training_eval.py:261–268`.

`_model_hashes` excludes `generation_config.json`. The installed MLX-LM loader reads
this exact file and overrides `config['eos_token_id']` from it in `utils.py:367–377`,
then passes that value to the tokenizer at lines 699–700. Therefore changing this
file can change which tokens terminate output while resume and base/adapter pair
checks still claim identical model inputs.

CPU reproduction: create dummy weights/tokenizer plus `generation_config.json`
with `eos_token_id=1`, hash, change only the EOS value to 2, and hash again. Both
identity dictionaries are equal. Include this file and all tokenizer artifacts
actually consumed by the selected local loader in identity. Prefer an explicit
record of resolved stop IDs as well. Index/vocabulary auxiliary files should not
be silently ignored when they are part of the loader's effective inputs.

### P2 — Require compatible tokenizer identity in fused comparisons

Location: `app/tutor_app/stem_training_eval.py:249–257`.

For `variant='fused'`, `validate_pair` removes the whole `model_files` comparison,
including tokenizer/template configuration. Equal rendered prompt strings do not
establish equal token IDs or equal decoding/stop behavior: a different vocabulary
can encode the same prompt text differently. Such a pair can attribute a tokenizer
or protocol change to adapter fusion.

CPU reproduction: otherwise identical base/fused receipts with different
`model_files['tokenizer.json']['sha256']` values (`AAA` versus `BBB`) are accepted.
Separate compatible tokenizer/template/resolved stop identity from weight identity
and require it for both adapter and fused pairs. Permit expected weight/config
changes from fusion without permitting arbitrary tokenizer changes.

### P2 — Report started-but-interrupted attempts instead of “not attempted”

Location: `app/tutor_app/stem_training_eval.py:339–340`, `386–391`, `425–428`.

Started markers use a `.started` extension, but scoring reads only `*.json` and
ignores started states. A process kill after its marker and before `write_attempt`
therefore disappears from scored failure/attempt evidence. `compare_runs` reports
null with the explicit explanation “null means not attempted”, although generation
was started. This also prevents reported attempt counts from reflecting crash
retries. The immutable marker survives on disk, but the advertised paired report
does not account for it.

CPU reproduction: frozen one-row selection and base/candidate directories each
containing `run.json` plus an orphan started marker produce `scores=[]` and
`baseline:null,candidate:null`. Give starts a stable attempt identity, reconcile
them with terminal records, and report unmatched starts as interrupted attempts
distinct from genuinely unattempted rows. Resume may retry interrupted attempts
while preserving their failure history.

## Positive checks and limits

- Focused trainer/evaluator suite: **73 passed, 1 skipped**, 0.39 seconds. The
  optional native MLX parity case was not run in this review; no real model or GPU
  invocation occurred. Tests used the normal project environment.
- Selection is deterministic from subject/task/id metadata and verified sealed
  file hashes. Gold is not supplied as an assistant message or added by the
  evaluator to generation. Source-transcription user prompts intentionally contain
  their supplied source answers; those rows are explicitly source-fidelity evidence.
- Thought token IDs are discarded as they arrive, with only counts retained.
  The harness never reads streaming text for storage, and only final IDs are
  decoded. Unfinished native thought regions yield no visible answer.
- Scientific accuracy and OPEN protection remain manual-review fields. Raw format,
  repaired host validity, exact-source/code equality and marking label agreement
  are separate. Correct JSON is not assigned a scientific pass. Generated code is
  compared as text and never executed.
- Terminal retries are immutable and the latest terminal attempt is compared;
  no best-scoring retry selection was found. Same-output advisory locking and
  coordinator-owned GPU exclusivity are documented. The interrupted-start issue
  above is the remaining failure-accounting gap identified.
- The installed native `grad_checkpoint` helper wraps the decoder class's call,
  recomputes the original forward from trainable parameters, and is invoked once
  per distinct decoder class. No changed mask, target, rank, optimizer update count
  or loss objective was introduced. Configured dropout is zero. Actual native
  backward performance remains a GPU smoke/pilot question.
- Materialized accumulation adds the same gradient trees, evaluates the sum and
  clears cached memory after each microbatch. Division by accumulation count still
  occurs exactly once in the optimizer update. Static source and CPU tests show no
  change to averaging semantics; the additional observed-memory boundary remains.

Fix verification should remain focused: CPU stubs for load guard/cleanup,
generation-config identity, fused-tokenizer mismatch and interrupted-start scoring,
then the existing targeted suite. No full suite or GPU launch is needed to resolve
these review findings.
