# Topical past papers

Restart the tutor after installing the code changes. Choose **Topical past papers** on the home menu, select a subject and chapter, and answer using the existing MCQ or written-answer controls. These questions are available independently of whether that chapter's lesson has been published.

Read original diagrams, formulae and complete question pages in Obsidian's **Now** note. When a question says **Answer (a) only**, only that part is assessed; the complete parent question remains visible for reuse. Multiple source pages are preserved in order. Until complete multi-page content can be provided to AI marking, written answers with multiple source images use the existing self-marking workflow.

**Can I solve this?** beside the answer controls, or **ctrl+y**, checks reviewed prerequisite metadata. It works during no-hints questions and reveals only required topic numbers. An unsuitable open question is skipped without a wrong answer and excluded only from that chapter. Unverified metadata is identified as unverified rather than guessed.

Supporting facts are recomputed for each presentation from chapters actually started. Facts are omitted once the corresponding chapter is started. Supported attempts count as assisted. No-hints checks receive no such support. Topic starts and exclusions are replayable learner events. The engine exposes `topical_exclusions(chapter=None)` and `restore_topical(identity, chapter)` for inspecting and restoring recorded exclusions; imported content never clears the list silently.

## Local storage and publication

The source PDFs remain in `sources/library/`. Original copyrighted questions and images stay local and are ignored by Git. The private prepared batch is `build/out/topicals/2026-10-27-v1/`.

The independent database is published to the vault's `.tutor/topicals/<version>/bank.json`, with an atomic `CURRENT` pointer. Source images are in `Assets/topicals/`. Publishing this bank does not run the content foundry or republish unfinished lessons, and does not change saved AI providers/settings.

To build a fresh conservative exact-match batch:

```sh
.venv/bin/python build/topicals.py build-matched --output build/out/topicals/fresh-batch
```

This automated pass requires exact existing AS mappings, complete source-image candidates and a matching separately parsed answer-table key. Additional manual review is needed for new mappings, part-specific marking and scans. A PDF's AS label alone does not establish current AS eligibility.

To publish a reviewed batch into an existing tutor vault:

```sh
.venv/bin/python build/topicals.py publish build/out/topicals/2026-10-27-v1 --vault '../STEM Tutor'
```

Publication validates the whole bank and all image paths before changing `CURRENT`. Previous versions remain available for rollback. The build command does not reproduce manually reviewed additions: their private review manifests and prepared bank are retained with the local evidence. Never commit copied question content or source images to the public repository.

## Scanned books

The two root physics books have varying 90°/270° PDF rotations and raster skew. PyMuPDF applies the PDF rotation during rendering; applying it a second time is unsafe. Pixel/OCR coordinates must be converted carefully before PDF cropping. Automatic text-header cropping refuses rotated pages and records them for review.

OCR inventory is not a ready question. Rotated/scanned pages require visual checks for upright text, every subpart, diagrams, symbols, complete options and answer separation. Unknown or conflicting items remain pending. The same applies to scanned chemistry collections. See the coverage report for what is actually available.
