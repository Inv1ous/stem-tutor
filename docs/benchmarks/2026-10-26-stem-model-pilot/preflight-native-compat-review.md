# Native compatibility v2 preflight

27 October 2026. Scoped CPU-only review: **0 serious findings** in the frozen eight-request compatibility probe.

Verified the first six document IDs/user strings against original DEV18 in file order: three published cards and
three literal-JSON requests. These use real `TutorAI(document=True)` with full production system/instructions and
no speech. Marking uses supplied VALID `c58ad26c013848559f4ab9cf` criteria/response, real `prompts.judge`/one-shot
and native schema, with separate gold `[true,false]`. Genuine Deep retains full speech instructions and4096/180s.
Fast/Mark retain512/45s, context8192, seed42 and the existing1.5-presence samplers; aggregate bound is600s.

The pure transport transform only removes `format` for exact custom-alias document generation. Marking, other
aliases and controls remain unchanged. Runtime validates the untouched app payload before transformation and
the complete intended outgoing payload afterwards (`diagnostic.py:346–359`). System/user strings, options,
think controls and schema values remain frozen; this does not assert canonical HTTP object-key byte order.

The earlier marking serialization failure is reproduced on CPU. Runtime now rebuilds the production schema,
checks its ordered serialized string and value, and uses that factory object when composing the embedded
`json_instruction` prompt (`143–160`, `290–293`, `463–465`). The canonical round-trip test verifies the complete
captured request, addressing the actual string-order mismatch rather than weakening identity checks.

Strict recursive schema, mandatory DocumentDecoder completion, literal-source equality and scientific/manual
source-fidelity checks remain separate. Correct marking vectors require valid exact envelopes and criteria.
Deep success additionally requires genuine observed thinking and app delivery. Hidden text/token IDs are
discarded before public logging; no generated code is executed.

The runner retains failures/partials and exact available counters, runs serially, checks initially empty residency,
observed resource/deadline limits and owned-candidate unload/empty cleanup. Production, weights, datasets and
prior results remain unchanged; source/fixture/prior-result hashes are checked before execution.

Independently reran **nine CPU tests: passed**, plus frozen-manifest and exact-user/options checks. Reviewed:
manifest `83c09a83d1751af5b8888ed95b62e1ae4fc0cf256e79fb6a6c645dee966a6ab6`;
script `f6e2e47094baf7d2e79fdc74aa764e4e782e7b2ac0d0a7522e71bc842a93645a`.
No API/GPU/model calls or MLX imports occurred. Clears this bounded DEV probe only; promotion and a production
compatibility change require its actual outcomes.
