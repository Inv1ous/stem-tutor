# Native MCQ preparation

`bin/extract-fastpath` prepares original question pixels and joins official answer-key rows without a model call. The first explicit profile supports registered native Cambridge 9701/9702 Paper 1 QP/MS pairs. It does not handle topical compilations, structured questions, IAL papers or universal OCR. Those remain on their existing paths until a separate adapter is demonstrated.

Run from `stem-tutor`:

```sh
bin/extract-fastpath prepare \
  --vault '../STEM Tutor' \
  --qp asset:legacy-33e899eb7277075af5175a4b \
  --ms asset:legacy-f34238051329383b94e62f54 \
  --output '../Work/Preparation/my-native-mcq-batch/9701_s20_12'

bin/extract-fastpath verify '../Work/Preparation/my-native-mcq-batch/9701_s20_12'
```

Choose a fresh output path. Existing paths are never overwritten. Both sources are read through AssetLibrary and checked against their registered digests. The profile checks printed paper identity on the cover and every MS page, and rejects conflicting QP footer identities. It requires ordered question numbers 1–40 and one unambiguous A/B/C/D official key for every question. A matching filename or cover alone is insufficient.

The bundle contains `bundle.json`, public question/context images under `qp/`, private key images under `ms/`, source hashes, page coordinates and an exception ledger. `COMPLETE` is written last and binds the manifest digest. Verification checks all referenced images, image decoding, media-map completeness and the public/private partition. It rejects symlinked media paths. This is integrity verification, not independent content approval or a signed attestation.

Every physical source page has a status. Missing native text, dominant page images, uncertain page content, numbering gaps and missing/conflicting keys remain explicit. A pair can produce `needs_review`; the program does not turn that into approval. Shared Section B instructions remain attached and flagged. All questions also retain an independent visual and mapping review requirement. The native text layer locates question boundaries and keys; the original rendered pixels are the question authority, preserving mathematical notation, diagrams and answer tables.

This program writes preparation only. It does not update manager jobs, clear guards, register resources, publish a bank or write learner state. Keep whole-question identities and source occurrences when comparing with existing candidates; these bundles can contain already published questions. Do not count prepared rows as new usable output. Do not rerun completed paid extraction to consume a bundle: use its source-bound evidence in the missing review/repair stage, through a supported manager adapter. Native full-paper bulk admission is not installed by this change.

The tutor already grades MCQs from the official letter without requiring a generated explanation. Its existing Explain this answer action generates teaching prose only on request. Do not bulk-generate explanations for these bundles. Long-question marking still requires independently verified official part/rubric evidence; MCQ letter parsing does not provide it.

Measured evaluation, exact fixtures and code-review findings live under `Work/Workers/extraction/fastpath-20261104/`. The paired benchmark compares repeated rendering with per-page reuse at identical DPI and verifies identical PNG digests. It does not measure AI time, complete publication throughput or a completion deadline.
