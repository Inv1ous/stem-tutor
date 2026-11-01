# Course workflow refresh

The user selected extending the existing workflows on 2026-10-30 and then explicitly delegated remaining decisions and opted out of further questions. This design records the implementation choices rather than requesting another approval.

## Intent and requirements

Foundry creates new syllabus-aligned courses from the corresponding Library sources. Refine improves prepared teaching used by **Learn a topic**, with optional subject-note work. Bugwatch remains useful after the Library/Work/engine migration. A new PDF extraction workflow accepts Claude only, Codex only, or both, and questions only, notes diagrams only, or both. **TQ means topical questions.** Question media has one course shelf, without MCQ/topical subdivisions. Duplicate detection preserves identities, assessed parts, history, corrections, and legitimate cross-chapter use. Can I solve this works safely across all question kinds.

Prepared teaching covers foundations, terms/notation, evidence-backed question forms, staged examples, separate independent checks, misconceptions, useful visuals, practice and review. Existing guided-card schemas and lesson actions remain the foundation. Live AI adapts explanation and practice to the learner rather than replacing all prepared material. Source gaps remain explicit; schema passes and model confidence do not establish content approval.

## Approach

Extend the existing boards, source tools, pack format, router, Library resolver, and review gates. A shared-pipeline rewrite was considered and rejected by the user's selection: it would increase migration and worker-state risk. Keep the existing dirty checkout, because it contains the migrated implementation and resources absent from HEAD. A task-start snapshot under Work/Preparation/workflow-refresh-20261030/baseline provides the review fixed point. Do not commit unrelated work or publish a course release automatically.

## Foundry and Refine

Make the guided preparation contract explicit in roles, manager skills and gates. Fix chapter source discovery, filter the exact course plus relevant shared sources, verify catalog hashes before reading, and keep extraction caches in Work rather than the learner Library.

Refine gains a persisted `lessons` scope and explicit `full` scope. New lesson-only runs may improve teach cards, reviewed examples/checks, form inventory and linked visuals; they must preserve subject-note bytes and unrelated assessment items. Existing in-progress states keep legacy scope to avoid changing a running pass. New runs default to lessons; full scope remains available. Reuse no-loss and source-bound correction review, never replace baselines to make a gate pass. Library-backed inputs are immutable: copy them to a fresh preparation path before authoring; gate/publish the candidate explicitly. Do not write through a file adapter into Library.

Add an oldest-first queue and coverage output based on prepared teaching readiness and recorded preparation time. Missing guided preparation ranks first; use recorded last-refined/pass evidence where available, label unknown age honestly and break ties by syllabus order. Audio-cache age is not teaching preparation age. Record a content fingerprint and preparation timestamp for completed new passes.

Foundry has a **7,200-second per-course run limit**; Refine has a **3,600-second per-course run limit**. Courses 9701 Chemistry and 9702 Physics retain the user's large-course exception. Budgets survive restarts and apply to the whole course, not separately to each chapter. Clamp worker timeouts to remaining time and stop scheduling at the deadline; incomplete work remains pending, never signed because time ran out. Preserve existing provider preferences and `publish_on_sign`/`commit_on_sign` settings.

The current task must finish above 25% weekly remaining. Check actual Codex usage between work waves; reserve review/repair capacity and stop optional model work early. Workflow launches also need an explicit weekly reserve; do not guess unavailable usage or bypass an explicitly chosen provider through silent fallback.

## Extraction workflow

Add `bin/extract` and an installed Claude `/extract` manager skill using existing deterministic source/render/crop tools and shared worker lifecycle. Provider choice belongs to this job; it must not change Foundry/Refine's global `only` preference. Deterministic inventory, deduplication and validation cost no model calls. Workers receive course, source identities/hashes, selected scope and allowed output locations. Store state/logs in Work/Workers and editable candidates in Work/Preparation or Work/Candidates.

Question extraction retains complete ordered page regions, canonical paper/session/variant/question/part identities when known, source/mark-scheme pages, syllabus mapping, prerequisites and uncertainty. A figure extraction retains source hash/page/box, caption, teaching purpose and course/KC mapping. Images and SVGs are inspected before being described as reviewed. Unsupported question formats and incomplete/OCR-uncertain imports stay pending. Reuse `build/topicals.py` for its supported publication format; do not fabricate readiness for other courses. Registration is distinct from teaching approval. Both-provider mode uses an independent check from the other family; single-provider mode uses a separate blind task and records its family limitation.

## Visual teaching and solvability

Discover existing SVG, PNG, JPEG and supported course diagrams through AssetLibrary and explicit course/chapter/KC metadata. Reuse card-linked diagrams and source figures before generating replacements. Preserve IDs, captions, provenance and accessible terminal descriptions. Do not offer unrelated chapter images or protected assessment images as teaching illustrations. Recheck live session identity, open questions and skipped-answer guards after asynchronous generation, before applying or displaying output.

Can I solve this remains a metadata action, without answers, hints or scoring. Reviewed topical requirements retain current supported/solvable/unavailable policy. Ordinary questions receive a clearly identified course-graph prerequisite assessment from their validated assessed KCs; incomplete or conflicting graph/source data returns unverified. Do not invent reviewed topical metadata. Unknown questions remain open. Preserve no-hints behavior and saved written attempts when an unavailable reviewed question is skipped.

## Media consolidation and duplicates

Consolidate physical MCQ/topical image subdivisions into each course's `Questions/Media` shelf with collision-safe names. Preserve each existing asset ID, digest, provenance and old path as an exact declared alias. Use a locked, journalled, hash-verified migration, with originals retained under Archive and rollback evidence. Never merge distinct paper identities merely because image bytes match. Preserve immutable published JSON and learner events; runtime copies use aliases to reach the new paths. Do not rewrite review fingerprints.

Audit the actual CURRENT course/topical pointers, all active image fields after LibraryRefs adaptation, teaching diagrams/sidecars, historical lesson embeds and relevant preparation references. Distinguish archival/literal paths from live references. Verify callers before retiring a compatibility path. Duplicate selection uses canonical question plus independently assessed part and chapter/KC context; keep cross-chapter reuse. If same-context copies have conflicting answers or assessment fields, report a content conflict instead of deleting either. Filter confirmed equivalent copies at selection or in a new reviewed candidate, preserving historical aliases.

## Bugwatch and verification

Refresh canonical code paths and storage/answer-protection invariants. Scratch setup copies needed Library resources and must not mutate a catalogued published plan to disable Almanac syncing. Keep one writer per findings/fixes log.

Use regression-first tests for changed behavior: source discovery/course isolation/hash failure; persisted course deadlines and weekly reserve; lesson-only scope/no-loss/oldest order; provider/scope/restart extraction; SVG reuse and async guard lifecycle; all five question kinds and unknown metadata; consolidation collisions/aliases/restart/rollback and complete active image audit. Run relevant existing Foundry/Refine/library/guided/topical/UI suites, then independent Standards and Spec review of the task-start delta. A new course-wide content approval or native Terminal visual check is not implied by automated checks.

## Scope and reporting

Deliver executable workflows, installed manager skills, migration repairs, safe media consolidation, duplicate filtering and verification evidence. Exercise a representative lesson-only preparation candidate without launching an unbounded paid full-course regeneration. Report queued/pending/review-required content honestly. Do not change production scoring or claim the unresolved rubric/production-judge questions are settled. Remaining implementation choices are delegated to the builder within these constraints.
