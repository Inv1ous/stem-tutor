# Topical question bank: first bounded import

## Intent and scope

Import as many verified questions as the available usage budget permits from only `sources/library/Chemistry 9701 AS Topicals` and `sources/library/Physics 9702 AS Topicals`. Keep the original questions, diagrams, tables, official answers and source provenance. Do not invent missing text, keys or marking points. Stop expensive preparation before weekly usage reaches 80% used; publish the verified batch locally and report coverage and gaps. This request authorizes local question-database publication, not a GitHub push.

## Approaches

1. A separate, versioned, local topical bank overlays published chapter packs. This is the author's recommendation: original chapter packs and stable learner identifiers remain intact, while one source question can have chapter-specific support and exclusions.
2. Append everything to chapter packs. This reuses the existing generator but risks repeated questions, overwritten corrections and support leaking between chapters.
3. A source-browser-only catalogue. This imports quickly but is not a verified, markable question bank and does not fulfil the request.

The separate bank is the proposed default, pending the learner's design approval. Reuse the existing Textual cards, Obsidian question callouts, chapter selection, deterministic MCQ grading, official marking machinery and event store. No new provider, model setting or learning algorithm is required.

## Import and verification

- Inventory all PDFs in the two named collections, recording hashes, pages, readable question references, duplicate occurrences, scan-only material and extraction failures.
- Use canonical paper/series/variant/question identifiers; deduplicate across books and existing chapter items. Distinct parts retain distinct identifiers when they can be marked independently.
- Preserve a source crop for visual fidelity. Multi-page questions must include every necessary page or remain pending. Do not crop an answer into a question image.
- Match available official keys and previously checked bank mappings by exact paper reference. Conflicting keys or uncertain mappings remain pending. Existing matched questions count as already available, never as newly imported.
- Review new mappings against the published graph and the official Cambridge syllabus for the learner's examination window. AS eligibility is separate from whole A Level eligibility. Retain older questions when their actual requirements still fit; quarantine obsolete, moved-to-A-Level, ambiguous or unverified items.
- A ready item requires a complete question, verified key or usable official marking points, valid current syllabus mapping and reviewed prerequisite metadata. OCR supplies transcription only; uncertain diagrams and notation rely on the original crop.
- Prioritize reliable MCQ batches and a smaller set of verified structured questions before expanding scan-only material. Unverified inventory is not presented as ready coverage.

## Runtime prerequisites and support

Each imported item records the smallest reviewed required set of syllabus subtopics. Optional alternative prerequisite sets may express genuinely different solution methods. Required information supplied by the original stem does not count as knowledge the learner must already have.

The serving chapter is recorded separately from the question identity. Determine started subtopics from actual learning activity and existing progress, plus the current selected chapter; merely publishing or listing a chapter does not count as starting it. Recompute support on every presentation. Never mutate the shared source question.

For a required subtopic not yet started, show only reviewed supporting facts needed to attempt the target chapter's question. Do not reveal the answer or target chapter's tested skill. Once that subtopic is started, omit its support. If no safe support exists, leave the item unavailable for that chapter. A no-hints assessment never receives automatic teaching support; eligibility checking remains available.

## Solvability action

Add a discoverable `Can I solve this?` action beside the existing question controls, including no-hints questions. It returns only the minimal required topic numbers when the learner has started a sufficient prerequisite set. It does not reveal equations, definitions, answer keys or solution steps, and does not mark an answer or count as a hint.

If the learner lacks the necessary knowledge and the question cannot be safely supported for that chapter, skip without a failed answer, preserve the original question, and persist an exclusion scoped to `(question identity, serving chapter)`. The same question remains available in other chapters. Store an inspectable exclusion record with reason and missing topic numbers. Unknown or unreviewed requirements are reported as unverified rather than declared solvable. Never let an AI invent a permanent exclusion without an inspectable reason.

## Persistence and publication

Use a local bank directory with a manifest and immutable version, referenced through an atomic `CURRENT` pointer. Publish source assets before switching the manifest. Keep copyrighted question text and source images local and excluded from Git, consistent with the source library's existing conventions. The importer is repeatable and does not delete learner state, modify existing answers, overwrite chapter packs or republish unrelated in-progress foundry material. Loading no bank preserves existing behaviour.

## Evidence and completion

Tests cover deduplication, conflicting keys, invalid mappings, cropped/multi-page boundaries, no-bank compatibility, prerequisite state changes, chapter-scoped support/exclusions, no-hints checks, event replay, skip-without-marks and atomic publication. Exercise actual terminal and Obsidian output using an isolated vault. Review Standards and Spec independently before local publication.

Report ready unique questions, newly added questions, already available questions, structured versus MCQ counts, excluded/pending counts and per-subject coverage. State the denominator: identifiable unique source questions; separately disclose unenumerated image-only PDFs. Do not imply a percentage of all questions when the denominator remains unknown.

## Builder-check decisions

The independent builder check found implementation contracts, not a need for additional product questions. The following are author decisions for review:

- Use the currently published 2025–2027 Cambridge graphs and matching official PDFs. Store that syllabus revision per item; a future graph revision invalidates readiness until rechecked.
- Record chapter-start events when a lesson genuinely opens teaching or a question. For legacy history, infer started chapters from answered KCs and explicitly recorded completed chapters only. Starting a multi-chapter session does not mark every planned chapter started.
- Keep assessed KCs separate from prerequisite metadata. Providing missing prerequisite facts marks that attempt assisted; it cannot earn independent mastery credit for the supported content.
- Pass the serving chapter and no-help status through selection and recheck them at presentation, including queued/resumed questions. No-help questions with missing prerequisites are skipped, not supported.
- Preserve all existing learner item IDs and resolve canonical source identity through aliases for freshness/deduplication. A newly imported equivalent question does not erase prior exposure.
- A learner-requested exclusion persists for its specific chapter even after new learning; expose the recorded list and an explicit restore/recheck operation. Importing a new bank never silently clears it.
- Store ordered source images for multi-page questions. Until every necessary page and marking point is represented, such questions remain pending. Use the first image for existing single-image consumers and render all pages in Obsidian; AI marking must receive complete content or defer to self-marking.
- Reload the independent bank between questions or sessions using its own pointer; never change the instance of an already open question. Publish only the new topical bank, its images and required engine code, avoiding unrelated unfinished foundry changes.
