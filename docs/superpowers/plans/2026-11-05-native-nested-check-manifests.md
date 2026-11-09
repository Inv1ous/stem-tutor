# Nested check manifests Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Worker-only disjoint implementation.

**Goal:** Verify complete nested/flat question parts that currently stop before any model launch, retaining all previously completed receipts.

**Architecture:** Keep existing v1 part-manifest output exactly for every already-supported case. A source-only fallback derives hierarchical QP leaf parts and their printed allocations from complete validated whole questions, then checks against the independently proved whole maximum. The existing model checks actual MS part presence, values, units and allocations; proposals remain unreviewed.

**Tech Stack:** Existing AssetLibrary, native source words and lightweight verification client.

**Spec:** Parent overnight verification design and all-course user objective,10% reserve.

## Global Constraints

- Worker code/state only; no extraction core/client/UI/Library/history/guard edits or provider calls during implementation.
- Preserve v1 output bytes for supported cases and existing receipt digests. No repeated completed model checks.
- No model-generated required-part manifest. Every leaf/max has actual QP word/page/box/source evidence and sums to verified whole max.
- Every MS part match is still checked by the actual model against full official source; proposed chapters grant no mastery.
- Different packet bindings cannot silently reset the same canonical question's attempts or transport holds.

## Review Focus

- Parent labels with nested roman children, repeated parent headings and question-prefix labels.
- Equation labels/parenthetical values mistaken for marks; missing/duplicate/extra allocations or leaves.
- Old flat/unpartitioned manifests and completed receipts remain exact.
- Global per-question prior errors/cap across changed metadata; fresh quota must exist before paid launches.
- Chapter titles/IDs must come from registered frozen graphs, never fabricated IDs.

### Task1: Worker fallback and usable graph proposals

Files: new `Work/Workers/extraction/overnight-20261105-10pct/native_nested_parts.py`; narrow wrappers in `native_part_manifest.py`, `check_current.py`, `publish_native.py`; new tests under `stem-tutor/tests/test_native_nested_check_manifests.py`.

- [ ] Freeze worker entries. RED actual source nested examples and misleading marker/max cases using Library resources in disposable tests.
- [ ] Retain v1 derive as first choice. Only held cases enter hierarchical QP parsing. Preserve complete assessment context; reject ambiguity. Use source QP allocations and validated whole max; don't require the old incomplete MS word tokenizer to supply the new hierarchy.
- [ ] Add canonical-question history protection across packet changes: prior errors/exhaustion/changed attempted bindings require reconciliation, not a new Luna ladder. Retry only free quota observation when temporarily unknown; never call a model with unknown allowance.
- [ ] For genuinely new fallback packets, bind registered course/prerequisite chapter IDs, literal titles and graph digests; expose them to the existing proposal prompt. Old completed packets remain reused unchanged. Clarify semantic association and unresolved mapping are independent. Save actual prompt/schema/image-reference hashes.
- [ ] Publisher reconstructs exact same bound packet and trusted source manifests before accepting checked receipts. It still only filters source-verified rows, never clears holds or certifies mappings.
- [ ] Share a trusted replay-image resolver for package files and additional source-derived context images. Materialize missing extra pixels immutably in Work/Candidates, compare all bytes against fresh replay before model/provenance use, and never add files to an existing COMPLETE package. Tests use disposable cache paths.
- [ ] GREEN affected tests including v1 byte equality, real nested source maxima, forged/tampered part allocations, old failed-ledger resume, graph provenance and no provider/production writes. Freeze exact diff/pins/report; independent review before use.
