# Native compatibility DEV v2 — delivery improved; eight-gate acceptance failed

27 October 2026 (Hong Kong). Root authorized the exact reviewed eight-request command. Exec session **2038**, under `/usr/bin/caffeinate -i`, exited **0** after **201.727 seconds**. All eight native generation requests ran once. No retries, parameter changes, production changes or further GPU work followed. Exit zero means the harness completed, not that acceptance passed.

The SSD output is `/Volumes/External SSD TB4/LocalAI/stem-tutor-training/native-development-compat-results-v2`. [Frozen scripts/CPU tests/manifest](dev-compat-v2/manifest.json), [observations](dev-compat-v2/results/observations.json), [scores](dev-compat-v2/results/scores.json), [public events](dev-compat-v2/results/public-events.jsonl) and [manual public review](dev-compat-v2/results/manual-public-review.json) are preserved in `dev-compat-v2/`. V1 scripts/results and the original native challenge failure retain their frozen hashes. No hidden reasoning, token IDs or raw logits were saved; generated code was never executed.

The six Fast document users were byte-identical to frozen DEV18: three source-backed cards and three literal-JSON copies. All used real TutorAI, full SYSTEM/document instructions/examples and mandatory host DocumentDecoder. Only generating document-chat `format` was omitted for the exact custom alias. Marking retained native format. Every actual request matched its frozen full/outgoing identities; document payloads differed only by `format`.

| Request | Wall seconds | End / strict delivery | Content result |
| --- | ---: | --- | --- |
| Chemistry card | 8.573 | stop / pass | Adds explanations beyond supplied-only answer. |
| Chemistry literal JSON | 6.883 | stop / pass | Exact code; unsupported extra prose. |
| Maths card | 3.082 | stop / pass | Correct gradient-product condition; supplied negative-reciprocal formula omitted. |
| Maths literal JSON | 3.206 | stop / pass | Exact code; unsupported extra prose. |
| Physics card | 2.205 | stop / pass | Definition and W=mg preserved semantically. |
| Physics literal JSON | 3.157 | stop / pass | Exact code; unsupported extra prose. |
| Native-schema marking | 6.875 | stop / pass | Exact criteria/order; correct [true,false]. |
| Genuine Deep, speech document | 167.541 | length / fail | Thinking observed;4096 tokens; no public answer. |

Fast raw schema, mandatory decoder finish, application delivery and correct speech-field absence passed **6/6**. Literal code matched **3/3**, including quotes and line breaks. Fast median wall/first-rendered-block times were **3.181/1.609 seconds**. These structural results do not establish source fidelity: Chemistry adds steric/carbocation/solvent explanations beyond the supplied answer; Maths omits `m₂=-1/m₁`. Each literal row additionally claims charge is represented by x₁ squared, unsupported by the copied data. Physics leaves W=mg as plain text rather than canonical inline mathematics. Automatic exact-document equality was0/6; paraphrase alone is not a science failure.

The corrected marking factory survived canonical fixture serialization and actual runtime capture. The full native schema remained present, the envelope was valid, both criterion texts/order matched, and vector [true,false] was available and correct. Feedback nevertheless calls the relationship “scalar”, misleading wording for a vector quantity. Vector correctness and feedback quality are separate.

Deep retained full speech instructions, genuine Boolean thinking-On and existing Deep sampler, with4096 total tokens/180 seconds. Thinking phase occupied164.613 seconds; no public content or rendered block appeared. It ended at length, so raw schema/decoder/application delivery failed and arithmetic/spoken meaning are unavailable. This rules out delivery success for this bounded Deep case despite omitting document format; no hidden text was inspected.

All eight native responses expose all seven frozen counters with no missing fields. Prompt-cache reuse varied across fixed-order requests; these are diagnostic timings, not an engine speed comparison. Requested sampler fields remain distinct from independently observed effective settings.

[Cleanup receipt](dev-compat-v2/results/receipt.json) confirms owned-candidate unload and empty residency; the existing root server remains available for final cleanup. Pressure stayed1, swap growth0, final SSD free43.302 GB. Native reported size_vram checking is not a hard peak-allocation guarantee.

The eight gates did **not** pass: Deep delivery and content-fidelity findings remain. Do not promote, patch production, resume challenge confirmation or generate more without a subsequent root GO. This small DEV result supports retaining the exact-alias compatibility hypothesis for review, while preserving full instructions and strict host validation.

Manifest SHA256: `83c09a83d1751af5b8888ed95b62e1ae4fc0cf256e79fb6a6c645dee966a6ab6`. Executed source SHA256: `f6e2e47094baf7d2e79fdc74aa764e4e782e7b2ac0d0a7522e71bc842a93645a`.
