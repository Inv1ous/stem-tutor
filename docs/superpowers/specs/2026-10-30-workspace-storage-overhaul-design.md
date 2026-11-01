# Workspace and storage overhaul

Approved in chat on 2026-10-30.

The authoritative learning library lives inside the STEM Tutor learner vault. Course resources are organized under Library/Courses/<course-id>/Sources, Questions, Diagrams and Notes. Shared resources live under Library/Shared. Immutable published content lives under Library/Releases. The stem-tutor repository remains code, tests, documentation and tooling. Workspace processing lives under Work; preserved originals live under Archive.

All reusable learning assets used by runtime, builders, documentation examples and tests must resolve through this library. Tests must never mutate the learner library or learner state. Destructive and malformed-input tests use isolated temporary STEM Tutor/Library copies; synthetic invalid bytes are test inputs, not lesson resources. No independent reusable test-asset library may develop.

A catalog records stable identifiers, hashes, provenance, canonical vault-relative paths and legacy aliases. Original source material, TQ files, question data, SVGs and other media remain traceable. Course eligibility and content review are separate from asset availability. Being used in a test does not confer teaching approval.

Migration expands storage before switching callers. It is journalled, restartable, hash-verified and reversible. Preserve original learner events, answers, grades, state meaning, immutable snapshots and correction bindings. Repair historical lesson links using explicit mappings. Do not delete originals or perform Git commit, merge, tag, push or release.

Generated speech uses a device-local cache with existing recordings reused. The staged code overhaul addresses asset/workspace location ownership, engine packaging, worker orchestration, session persistence and screen organization.
