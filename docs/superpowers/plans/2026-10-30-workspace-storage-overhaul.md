# Workspace and storage overhaul implementation ledger

Approved design: `../specs/2026-10-30-workspace-storage-overhaul-design.md`.

- [x] Whole-workspace hash/reference inventory and architecture review; preserve dirty/untracked work.
- [x] Establish `STEM Tutor/Library` as the authoritative course/type resource tree and validated catalog.
- [x] Migrate 8,583 resource records; preserve hashes, IDs, source provenance and legacy aliases.
- [x] Route runtime assets, source readers, diagrams, publishing and reusable real test inputs through Library.
- [x] Archive retired source/media trees; retain exact compatibility adapters and rollback journals.
- [x] Repair 201 recognized references across 100 vault Markdown files, including 41 lesson notes.
- [x] Verify all 108 image embeds across 65 historical lesson notes; preserve checked learner events/state/backups.
- [x] Extract canonical engine to `src/tutorlib`; retain plugin distribution adapter and standalone-copy support.
- [x] Consolidate shared worker lifecycle and location rules in `src/tutor_workers`.
- [x] Move marking persistence behind session methods with cancellation cleanup and answer protection.
- [x] Extract summary/confirmation/Ask dialogs; preserve existing imports and class behavior; map app ownership.
- [x] Relocate preparation/candidates/worker records into Work: 6,852 regular files and 1,971 nested links verified.
- [x] Repair 101 standalone preparation-script repository anchors and one shell anchor; exact originals retained.
- [x] Relocate 15,195 existing speech-cache files without regenerating recordings.
- [x] Build 62 Library navigation pages and record the shared storage contract for future work.
- [x] Verify actual runtime: 102 published packs, 1,532 topical items, 869 shortcut entries; no topical errors.
- [x] Independent Standards/Spec review and fix loops, including active shortcut manifests and note-link cycles.
- [x] Complete broad core/UI runs and targeted repairs; no unresolved observed test failure. Refresh installed engine and write `Work/storage-migration/OVERHAUL-REPORT.md`.
- [x] Route the remaining 111 reusable draft/baseline inputs through Library; preserve their status and exact bytes.

Ruling: preserve the large pre-existing dirty checkout in place with a recovery archive; creating a clean worktree would omit current course work and break actual-vault integration. No Git commit, merge, tag, push or release is authorized by this overhaul.

Ruling: maintain historical repository paths as symlink adapters while physical working data lives in Work. Original evidence strings and hashes remain meaningful. Mutable preparation candidates are distinct from Library resources served to lessons/tests.

Limitations: native Terminal computer access was denied by the platform. Real Obsidian PNG/SVG checks passed; engine lesson smoke and Textual pilots are separate evidence. This ledger does not certify course content or resolve pre-existing content-review/restoration uncertainty. Several main screens remain in the documented `screens.py` module; this work extracts coherent ownership seams rather than rewriting every class.
