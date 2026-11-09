# Overnight question verification and extraction

## Intent and authority

Implement the user's objective in `/Users/sora/.codex/attachments/ed9dc9c5-2688-40fd-b5d6-197d2c856eb9/goal-objective.md`, then resume all fourteen courses until 10% weekly allowance remains. Scope is all source questions, not merely the easiest MCQs. Completion requires reconciled source inventories, verified complete questions, deduplicated tutor availability and preservation evidence. A budget checkpoint is not goal completion.

The user has delegated implementation decisions and requested autonomous overnight execution. Existing authorization covers immutable Library publication after independent gates. Keep the current dirty checkout and leave changes uncommitted. No resets, purchases, global model changes, or historical data edits.

## Approaches and decision

1. Solve every item using a model: broad but repeats already-proved answers and can mistake answer-conditioned agreement for verification.
2. Only deterministic format adapters: highest throughput on supported formats, but leaves source/scheme ambiguities and novel formats unresolved.
3. Combine source replay with bounded model checks: selected by the coordinator to implement the user's vision. Reuse deterministic identity/pixel/key evidence; use cheap model checks for semantic associations/calculations, escalating ambiguous cases. Keep unknown cases held. Do not call a model answer an official scheme.

## Components

### Lightweight verification

A small extraction module prepares source-bound question packets and validates strict model receipts. Packets contain complete public question images/text and authenticated private official answer/scheme evidence. Bind receipts to a digest of the item/source evidence and record actual model, attempts, verdict and reasons. MCQ solving is blind to the answer on its first pass; compare to the authenticated answer afterward. At most three attempts, no retry-until-match approval. An explicit mismatch or insufficient diagram/context evidence requires official-source reconciliation or a stronger tier, not automatic acceptance. LQ checks establish matching question numbers, parts, values, units and mark maxima; uncertain/missing parts hold. Candidate subpart chapter/dependency annotations stay proposals, never certified KCs. Unknown receipt keys, wrong bindings and missing subparts fail closed.

Use Luna first; promote genuine ambiguity/failure to Sol/Terra as available. Keep model choice and reasoning explicit, use existing authenticated Codex infrastructure, and record actual failures. Web lookup is a separate explicit primary-source step if the provider disables browsing. No fake search or model receipt.

### On-demand feedback

Existing Explain/AI marking remains explicit and after submission. Generate concise confirmation for correct work; give focused correction for wrong work and full detail only when requested. Preserve original official answer/scheme and saved attempts if AI fails. No extraction-time explanations. No mastery or confirmed-award changes from an AI suggestion.

### Native written imports

Reuse the existing `prepared_scope` whole-question source proof rather than recreate its native identity and total validators. A source-practice adapter verifies a real prepared package against registered originals, maps complete public/private images with actual canonical IDs, and retains all source issues and guards. Only whole assessments with independently matched QP/MS maxima qualify. Entire question/scheme continuations and notes must be present. Scope remains source practice, not adaptive admission.

Generate fresh requests only for genuinely unprepared scopes. Discover original QP/MS pairs by catalog and printed identities, not filenames alone. Reuse valid packages. Shared-page schemes or unresolved totals remain held until a separately tested geometry profile exists. Later topical provenance joins must prove actual question identity; unknown occurrences are not falsely merged.

Read-only eligibility probing found three concrete native-proof limitations: normal May examination dates in the June series, marking-table question columns outside the hard-coded left margin, and explicit `Total N` maxima instead of `(N marks)`. Narrow fixes may accept these only with positive issuer/unit/component/year/series evidence, authenticated table headers/column alignment, and one located right-hand question total outside notes. May maps to the June series for QPs only; the MS must independently name June/Summer of that year. An October MS paired with a May QP remains a conflict. Preserve old accepted descriptors exactly when their proofs do not need a new variant. New source-based tests and independent reviews must cover the variant and misleading counterexamples.

## Safeguards and operation

Preserve all old Library records/payloads, aliases, review bindings, worker guards and learner history. Only one publisher writes CURRENT using the existing lock/CAS. Independent implementations may overlap only with disjoint explicit file ownership; shared product files have one writer. Test only disposable vaults with `tests/library_assets.py`. Keep the existing 147 crop quarantines; do not clear them by reimport. Retain the boundary audit for written crops and integrate any new derived geometry only with independent review.

At each bounded batch boundary read fresh weekly usage; stop paid launches with headroom near 10%, drain/checkpoint at the floor. Persist the already-consumed reset lock. No idle spend to reach a threshold. Keep queues keyed by source hashes, source scope and stage. Report supported-import pace separately from whole-corpus coverage. No completion percentage without a reconciled denominator.

## Evidence and deliverables

Tests cover source/receipt tampering, mismatches, retries, escalation, incomplete parts, answer privacy, full native blocks, deduplication and preserved mastery/history. Independent Spec and Standards reviews plus final risk review precede production imports. Save baseline pins, actual model receipts, per-course deltas, held reasons, useful improvement ideas and a rendered System Design report. Full-course completion remains unproven until every source and question has an explicit terminal disposition.
