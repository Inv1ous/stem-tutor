# Sampling diagnostic preflight review

27 October 2026. Scoped CPU review: **0 serious findings**.

Compared the current evaluator with the preserved protocol-diagnostic source snapshot. The only implementation
changes are the configurable presence coefficient, validation, Fast-only restriction and CLI forwarding.
The final evaluator SHA256 is `ba1f4f755d18b93860b43730c2fda12f485e72cf1ee53e0d88173878afbad491`.

Only finite numeric 0.0 and 1.5 are accepted; Boolean values are rejected. The resolved coefficient reaches
`make_logits_processors` and both configuration/sampler receipts. Independent CPU comparison found exactly one
changed configuration field and one changed sampler field: `presence_penalty`. Temperature, filtering, seed,
presence span, token/time/memory limits and thinking controls remain fixed. Default Fast and Deep retain 1.5;
Deep with zero is rejected before model loading.

Protocol construction, gold exclusion, row selection, tokenizer handling, weights, scoring and immutable-run
checks are unchanged. The existing weight-comparison guard still rejects different sampler identities; it is
not a valid route for presenting this sampler contrast as an identical-sampling weight comparison. Both fresh
arms must retain their actual identities and be analysed as a development sampler intervention.

The [research note](../../research/2026-10-27-stem-structured-sampling.md) cites primary publisher/runtime sources
and clearly separates a plausible mechanism from demonstrated causation. It requires a controlled development
test, preserves unassisted formatting measurement and treats Deep/native compatibility as separate gates.
No outcome or promotion claim is justified yet.

Independent verification: **59 tests passed** across the protocol/evaluator suites, including the stubbed GPU
boundary, invalid coefficients, Deep isolation and sampler mismatch. No GPU/model calls, weight/data edits,
old-result rewrites or product changes occurred during this review. Ready for the proposed fresh 36-request,
training-protocol DEV18 comparison on the same accepted update-100 adapter.
