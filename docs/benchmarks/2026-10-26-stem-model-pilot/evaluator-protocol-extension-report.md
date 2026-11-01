# Evaluation protocol diagnostic extension

27 October 2026. CPU implementation and data preparation only; no model loading, GPU generation, weight changes,
new training, original-dataset edits or v1 artifact edits occurred. Independent review and root GPU authorisation
remain required before the 54 development requests.

## Fixed protocols

`generation_messages(row, protocol)` validates one original user message followed by one assistant gold record,
copies only that user message, and never reads the assistant content, expected answer or scoring metadata. The copy
preserves the user's content exactly and cannot mutate the source row. The three fixed choices are:

| Protocol | Messages passed to the native template |
| --- | --- |
| `training` | Original user only. This is the v2 default and matches the trainer's input roles. |
| `legacy_system` | System `STEM Tutor. Reply in document JSON.` followed by original user. This preserves the v1 condition. |
| `neutral_system` | System `STEM Tutor. Follow the JSON contract requested by the current task.` followed by original user. |

No schema, gold, repair prompt or format example is added by this function. Existing format instructions already
inside a dataset user message remain untouched. Native `enable_thinking` is still exactly `mode == 'deep'`; the
extension does not invent an intermediate strength or change native thinking termination.

`EvaluationConfig.protocol`, `--protocol`, the v2 run receipt and its format context all record the explicit choice.
Each request records both the structured role/content hash and rendered native prompt hash. Same-protocol paired
comparisons reject different protocol identities or message hashes. Existing v1 receipts/selections remain readable
and are classified as `legacy_system` when their older receipt has no protocol field. No old receipt is rewritten.
The retained `identity` configuration field is the original v1 compatibility stamp; only `legacy_system` applies it
as a system message. The v2 format context explicitly records `system: null` for training.

## Frozen development corpus

Prepared at `/Volumes/External SSD TB4/LocalAI/stem-tutor-training/evaluation-development-protocol-v1`.
This is **development protocol diagnostic data, not sealed-test promotion evidence**. The transport filename
`test.jsonl` is required by the existing evaluator reader; both manifest and selection explicitly label its
`evaluation_role` as `development_protocol_diagnostic` and its source split as `valid`.

The selection uses metadata only: keep all 12 original VALID marking rows, then select one `published_flashcard`
and one `literal_json` row per subject by the minimum `SHA256('protocol-dev-v1:' + id)` in each bucket. There are
18 rows in six groups, with correlated variants:

| Subject | Document rows | Marking rows |
| --- | ---: | ---: |
| Chemistry | 2 | 0 |
| Mathematics | 2 | 4 |
| Physics | 2 | 8 |

The marking families are `synthetic:square_domain_criteria`, `synthetic:vector_criteria` and
`curated:phys:dynamics`. The original VALID split has no chemistry marking examples. No balanced chemistry marking
coverage or independent-example count is claimed. All five original `data-v2` files have identical before/after
SHA256 values; the CPU build receipt records those hashes.

- Diagnostic manifest: `dfb6298fb33dc34f87de7c1383dd89e0433edd080e240db01d61eb12d4904f99`.
- Diagnostic transport file: `c2e3646a5cf58a4e537dedf00aabeb7588d43e3181c1a53101910c5e5094a090`.
- Frozen selection: `585081b48c45e53224f212a3e787cc2ec30767dbce7ca4e9697e04dc36dcf3a8`.
- Build-time evaluator source: `d074ca483cd1f25bbe431d89fc8e2cd3b442b094100e5623b6c72c0929b6f9da`.

Use the same development-accepted 100-update adapter for all three conditions, with Fast mode, seed42, the existing
Fast sampler, 4096 total generation tokens, 180-second request deadline, 14 GiB observed allocation budget and the
unchanged pressure/swap/disk guards. Each condition uses a separate fresh output directory. No automatic retry,
gradient update or test-specific target is added. Any future source change must be fingerprinted before generation.

## Marking evidence and interpretation

The scorer now separates `marking_envelope_valid`, exact criterion identity/order, `marking_vector_available`,
the decoded public `marking_decision_vector`, and conditional `marking_vector_correct`. An unavailable vector or
wrong criterion identity receives `null` conditional correctness, not an observed incorrect scientific decision.
A valid envelope with matching criterion identities can produce a true or false conditional decision comparison.

The existing `marking_labels_equal` field remains as a complete-contract metric for compatibility: false can mean
an unavailable envelope and must not be relabelled as a semantic error. Explanation quality remains manual review.
Literal-source fidelity, document validity, repaired host validity, science and OPEN protection remain separate.

All 240 v1 requests, their failures, source snapshot and scores remain intact. V1 chat-format failures remain genuine
robustness failures under its extra system directive. No failure is converted into a pass by this extension. V1
marking-envelope failures alone do not establish loss of marking knowledge. The forthcoming development contrast
may help identify a protocol effect; no outcome is presumed before generation.

## Verification

Test-first failures were observed for all three protocol roles, malformed inputs, default/unknown protocol handling,
explicit pair identity, development selection/data receipts, unavailable versus incorrect marking vectors, and v1
read compatibility. The neutral sentence and metadata selection were then revised to the exact independently
reviewed design before any diagnostic model call.

```sh
.venv/bin/python -m pytest tests/app/test_stem_training_protocol.py \
  tests/app/test_stem_training_eval.py tests/app/test_stem_training.py tests/app/test_stem_training_data.py -q
```

Result: **110 passed, 1 skipped** (the explicit optional GPU integration case). Protocol tests: 17. No broad suite
or native inference was run by this builder; root owns those checks. The CPU data preparation completed successfully
and verified all original dataset hashes unchanged.
