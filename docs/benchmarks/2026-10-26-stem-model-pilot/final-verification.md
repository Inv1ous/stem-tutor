# Final verification

27 October 2026. MacBook Air M4, 24 GiB unified memory. Shared-format production work is verified. The separate
fine-tuning experiment concluded without promotion; its failed source-fidelity and Deep-delivery gates are retained
in [the model card](../../STEM_TUTOR_MODEL.md). No custom model, preset or native-schema bypass was enabled.

## Software checks

Final canonical command:

```sh
PYTHONPATH=tests/app .venv/bin/python -m pytest tests --import-mode=importlib -n 4 --dist=loadscope -q
```

Exec session `89099`, exit 0: **4,690 passed, one skipped, 28 existing warnings in 148.49 seconds**.
The skip is the optional installed-MLX CPU proof in the main app environment. Actual MLX training, checkpointing,
fusion, reload, numerical comparison and native inference ran separately in their documented environments.

Additional benchmark-harness CPU groups passed **20 + 9 + 9** checks. The final import-safety repair's covering
training/data/evaluation/protocol/fusion suites passed **156, one optional skip**; progress/preload verification
passed **33** with four workers. These groups overlap production coverage and are not summed into the canonical
test count. `git diff --check` passes.

The earlier canonical run passed 4,689 tests. The import-safety review added one test case. Its subsequent full run
exposed a timer-dependent progress fixture, which was reproduced at the actual refresh boundary and corrected by
supplying explicit fake progress. Both original failure logs remain under `/tmp`; the reports preserve exact
commands/results. These repairs changed tests only, without changing production output or weakening assertions.

## Independent review

- [Standards review](closeout-standards-review.md): one P2 test-order issue, subsequently
  [addressed and rereviewed](closeout-fix-rereview.md); no production/tool regression found.
- [Spec review](closeout-spec-review.md): no actionable findings. It distinguishes completed shared formatting from
  the permitted negative pilot outcome.
- [Progress-fixture rereview](verification-progress-fix-rereview.md): addressed; no new serious findings.
- Earlier model/evaluator/fusion preflights and the real output quality/visual audits remain linked from their
  benchmark reports. Software tests and valid JSON do not certify model science accuracy.

## Preservation and handoff

The working branch is `main`; the staging area is unchanged. The application stays at `2.6.0`; the existing tag
was not moved. No commit or push was made. [Scoped push instructions](../../PUSH_V2_6_0.md) include the accepted
untracked files and exclude unrelated learner/generated data and SSD weights.

The owned native server and every owned model job were stopped. Original model weights, saved provider choices
and learner files were preserved. SSD `stem-tutor-training/EXPERIMENT_STATUS.md` records the negative outcome
separately from verified model files. [Decisions and costs](decisions.md) preserve the implementation rulings.

Final Codex weekly usage was **41% used / 59% remaining**, within the user's 50%-used ceiling.
