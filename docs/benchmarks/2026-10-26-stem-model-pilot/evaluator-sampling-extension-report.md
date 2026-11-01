# Fast development presence-penalty diagnostic

27 October 2026. CPU implementation only. No GPU requests, model loads, weight/data changes, old-result rewrites,
production provider changes or new training occurred. Independent review and root GPU authorisation remain required.
The mechanism and limitations are documented in [the primary-source research](../../research/2026-10-27-stem-structured-sampling.md).

The completed role diagnostic did not resolve the marking-envelope failures: the coordinator reports zero valid
marking envelopes in all three conditions. Training and legacy conditions each delivered five of six document
contracts, versus three of six for the neutral condition. The training protocol remains the reference because it
matches the training interface, not because it wins a metric. All 240 v1 trials and all 54 protocol diagnostic trials
retain their original settings and outcomes. No prior failure is relabelled as a pass.

## Minimal implementation

`EvaluationConfig.presence_penalty` defaults to 1.5. Validation and the `--presence-penalty` CLI accept only 0.0 or
1.5; NaN, infinities, Boolean values and other coefficients are rejected. Fast passes the resolved value directly
to `make_logits_processors`, retaining the 1024-token presence span. Configuration and resolved sampler receipts
record the actual coefficient, and the existing same-sampler paired comparison rejects different coefficients.

Deep retains its original 1.5 default. An alternate zero coefficient with Deep is rejected before model loading;
this extension is a Fast-only development contrast. Temperature, top-p, top-k, native thinking flags, protocol
messages, limits, seed, weights and scoring logic remain unchanged. No other local or cloud model is affected.

## Predeclared next contrast

Use the unchanged 18-row development corpus and selection at
`/Volumes/External SSD TB4/LocalAI/stem-tutor-training/evaluation-development-protocol-v1`, the same accepted
100-update adapter, `training` protocol, Fast mode, seed42, 4096 total tokens, 180 seconds and 14 GiB observed memory
budget. Root will run two fresh arms under the same final evaluator fingerprint in new directories under
`evaluation-sampling-dev-v1`; 18 requests per arm, 36 total:

| Arm | Temperature | Top-p | Top-k | Presence | Presence span |
| --- | ---: | ---: | ---: | ---: | ---: |
| Fresh reference | 0.7 | 0.8 | 20 | 1.5 | 1024 |
| No presence | 0.7 | 0.8 | 20 | 0.0 | 1024, inactive |

Do not reuse the old training condition as a supposedly identical control: the new run configuration and evaluator
fingerprint differ. The weight-comparison `pair` command intentionally continues to require the same sampler;
this separate one-factor diagnostic must explicitly retain and compare both sampler identities. Retain all trial
attempts and inspect document/envelope validity, exact criteria/source copying, available decision vectors,
conditional decision correctness, delivery/length failures and timing. A formatting gain does not establish better
scientific accuracy, and a development result is not sealed-test promotion evidence. Native full-schema production
compatibility is a later, separate gate.

Final evaluator SHA256 at this handoff:
`ba1f4f755d18b93860b43730c2fda12f485e72cf1ee53e0d88173878afbad491`.

## Verification

Test-first failures were observed for the new coefficient, invalid/nonfinite values, Deep isolation and comparison
identity. A CPU integration test stubs only the external MLX/model boundary and exercises real generation setup,
receipt writing and cleanup; it verifies zero reaches the logits-processor factory with span1024 and appears in
both configuration and resolved sampler receipts. No actual model or GPU is invoked by that test.

```sh
.venv/bin/python -m pytest tests/app/test_stem_training_protocol.py \
  tests/app/test_stem_training_eval.py tests/app/test_stem_training.py tests/app/test_stem_training_data.py -q
```

Result: **125 passed, 1 skipped** (explicit optional native GPU integration). CLI help exposes only the two allowed
coefficients. The root agent owns subsequent model runs, native production checks and the final broad test suite.
