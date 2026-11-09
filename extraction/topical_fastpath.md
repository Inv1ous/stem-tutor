# Topical compilation preparation

`bin/extract-topicals` preserves original question images and the existing topical organization. It prepares evidence without calling an AI, registering resources, updating manager jobs or publishing learner questions. It does not calculate missing answers or pretend a printed compilation number is an official exam identity.

```sh
bin/extract-topicals prepare \
  --vault '../STEM Tutor' \
  --source asset:legacy-5bc3d81eac5b76326e9a0048 \
  --course P1 \
  --output '../Work/Preparation/my-topicals/P1-c1.3'

bin/extract-topicals verify '../Work/Preparation/my-topicals/P1-c1.3'
```

Use a fresh output directory. Source bytes enter through AssetLibrary and are digest checked. The registered source course must agree with the requested course. Occurrence IDs bind source digest, section and position; they never overwrite canonical question IDs or approved resources. Files are written under a checked physical destination outside the learner vault. COMPLETE is written last. Verification checks image hashes and decoding, media/source/visibility bindings and preserved content for every substantive page, not merely a numbered page list.

SaveMyExams profiles validate each concatenated booklet cover and declared count, including question-number resets by difficulty. Original assessed parts remain together. CAIE compilation profiles recognize explicit exam-mate/PapaCambridge headers, classified labels and an older outer gutter; these remain provisional. Known answer paths are routed privately before layout detection, including opaque image-based mark schemes. Answer sections and booklet covers stop question continuations. Empty, unsupported and unanchored pages enter review.

For five existing frozen scan profiles, optionally reuse the source-bound OCR caches:

```sh
bin/extract-topicals prepare \
  --vault '../STEM Tutor' \
  --source asset:legacy-8f2f9994d0b9bb3f82615c58 \
  --course 9702 \
  --ocr-cache '../Work/Workers/extraction/ocr-cache' \
  --output '../Work/Preparation/my-topicals/physics-scan'
```

This command validates the complete existing cache before using it; it never generates OCR. Frozen source/manifest hashes, every page sidecar, render digest, cropbox, rotation and dimensions must match. OCR is provisional regardless of confidence. Crack-A-Level source-code headers are retained as page fragments and do not count as whole questions. The full scan profiles require the exact registered source revisions; changed caches need a separately tested profile revision.

Statuses have distinct meanings:

- `segmented_unreviewed`: the source profile's printed counts and numbering reconcile, with no unassigned pages. Source/visual, answer, mapping and publication gates remain.
- `needs_review`: proposed starts exist, but complete question boundaries remain unproven.
- `unsegmented`: preserve page fragments for review; no reliable whole-question extraction claim.
- `private_answers_only`: a registered answer companion; no public question media.
- `excluded`: an explicitly supplied, source-digest-bound exclusion rule. Exclusion does not delete Library bytes or invalidate prior published resources.

An exclusion file supplied through `--exclusions FILE.json` contains a list of `{ "source_id": "asset:…", "source_sha256": "…", "reason": "…" }` records. A changed digest rejects the rule rather than silently skipping a new revision. No exclusion was applied by the benchmark: sampled physics scans showed mild variable skew, and their cached OCR remained useful. Unresolved sources remain visible in the fixed denominator and queue.

The frozen topical test population covers 11 courses. FP2, FP3 and S3 have registered native papers but no topical PDFs in this cohort; they are not complete. Native-paper and notes/diagram workflows remain separate. Before paying for another maker pass, reconcile the existing successful stages and use their unchanged evidence. These preparation bundles are not a supported bulk tutor admission path and do not replace independent review or learner-route proof.

Exact source lists, full-population analysis, representative rendered bundles, review findings and the completion forecast are retained in `Work/Workers/extraction/topical-fastpath-20261104/`. The 89-test focused run does not represent the entire repository suite.

PMT preparation adds a separate provisional detector for canonical
`Library/Courses/<module>/Sources/Library/PMT/Edexcel/<module>/` sources. It
supports P1–P4, FP1–FP3, M1, D1 and S1–S3; this expands preparation support,
without changing identity/import admission support. A PMT shelf path and publisher
text are required for question detection. Registered Notes and MS companions are
routed before layout matching, including raster companions.

Set1 starts use the left number gutter. Mark codes, report prose, answer headings
or numbering resets stop public segmentation; the Internal Review footer alone
does not. A page containing question and answer evidence is wholly private, with
an ambiguity issue. Set2 keeps original printed numbers and explicit matching
`Question N continued` pages, stopping at formula lists. Unanchored and missing
text pages stop continuation. Plain S3 text starts remain question proposals;
raster stems with only a text number/session are preserved as review regions.
`mixed_review_regions` pages bind the question/context and review crops together
for full-page verification. These fragments do not count as whole questions.

PMT has no demonstrated complete printed count proof. All proposals therefore
remain `needs_review` or `unsegmented`, with null official identities and no
teaching approval. Whole-page private quarantine can intentionally withhold
question content; it must be resolved by independent source review before any
publication. Preparation and bundle verification establish accounting and media
integrity, not the completeness or correctness of individual question boundaries.
