# Scoped protocol implementation review

27 October2026. **No serious finding within this extension.** This review covered the protocol correction and
its development diagnostic preparation, not model quality or later native deployment. No model/GPU call,
weight change, production-source edit or broad suite was performed by the reviewer.

- `generation_messages` preserves the exact original user content in a fresh dictionary, validates its role and
  shape, and adds no assistant gold, expected answer or scoring metadata. `training` supplies only that user;
  `legacy_system` retains the exact v1 sentence; `neutral_system` uses the exact reviewed ASCII sentence,
  `STEM Tutor. Follow the JSON contract requested by the current task.` Unknown protocols fail validation.
- Actual production function checks on all255 original development rows match the user-only inputs used in the
  prior tokenizer proof. That proof established byte-identical Fast training prefixes for255/255 rows. Native
  Deep still intentionally opens its own thinking region and remains a separate empirical gate.
- Config, CLI choices, version2 receipts, format-context metadata, per-request message hashes and rendered-prompt
  hashes identify the protocol. Pair validation rejects mixed protocol/config/code or role/content hashes.
  Existing v1 selections/receipts remain score-readable as `legacy_system`; their files are not rewritten.
- The actual frozen diagnostic contains18 rows in six correlated groups: chemistry2 documents, maths2 documents
  plus4 marking rows, physics2 documents plus8 marking rows. IDs match the metadata-only reviewed selection.
  It reads original VALID data, carries an explicit development-only role/source label, and its recorded source
  hash matches the unchanged original VALID file. It is not sealed-test promotion evidence.
- The scorer distinguishes a valid grading envelope, copied criterion identity/order, available decision vector
  and conditional correctness. Missing vectors or mismatched criterion identities have null conditional
  correctness. The legacy complete-contract `marking_labels_equal` remains separate from a semantic decision claim.

Independent focused verification:

```sh
PYTHONPATH=tests/app .venv/bin/python -m pytest \
  tests/app/test_stem_training_protocol.py tests/app/test_stem_training_eval.py \
  --import-mode=importlib -q
```

**44 passed.** Actual-data CPU checks also verified all255 message mappings, all18 selected IDs, subject/contract
counts and development role. ManifestSHA256:
`dfb6298fb33dc34f87de7c1383dd89e0433edd080e240db01d61eb12d4904f99`.
SelectionSHA256: `585081b48c45e53224f212a3e787cc2ec30767dbce7ca4e9697e04dc36dcf3a8`.

The extension is ready for the coordinator's bounded54-request development contrast. This review does not predict
which condition will perform better, convert v1 failures into passes, or authorise model promotion. Keep all240
v1 observations and their original source snapshot intact; do not make additional training changes before this
protocol diagnostic has been interpreted.
