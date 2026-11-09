# Topical marking choice and shared bank reachability

The learner requests automatic AI marking as an option in Topical's own setup, and reassurance that reviewed source questions are reused in other relevant modes. Structured answers currently require self-marking and even an AI check returns a confirmation checklist.

## Approach

Add a mode-local Self-mark / Automatic AI selector to existing `TopicalSetupScreen`. Default Self-mark preserves current behaviour and old sessions. Store the choice with the active topical session, retain it across topic changes and resume, and leave app Settings unchanged. Reuse current AI marking model and strictness; MCQ/numeric/expression grading remains deterministic.

When Automatic AI is selected, grade typed structured work directly after exact rubric validation, without another tick confirmation. Save work before any asynchronous call, use the engine's owned marking tickets, and reject stale results or changed protection state. An invalid/unavailable result returns manual marking with saved work; paper-only placeholders require self-marking. Cancellation and leaving do not grade or lose work. Short written topical questions follow the same per-mode choice, while non-topical marking remains unchanged.

Automatic marking must supply the whole declared question input. Extend Codex structured one-shot requests to use its existing multi-image CLI transport, preserving image order and per-call isolation. Resolve question media through AssetLibrary and fail explicitly on missing pages. Local models keep single-image support; Claude's current structured route and multipage local inputs fall back to self-marking with a specific reason. Do not send an incomplete image subset or silently mark an image-only question from generic stem text. All existing models remain selectable.

## Reuse

The existing `Packs.items_for` overlay is the shared source of reviewed topical questions. Prove learning probes, test sweeps, review/practice and long-question selection can reach suitable reviewed bank items without changing identity, freshness, exclusions or no-help prerequisite policy. Fix Test/Long picker omission for bank-only chapters with supported kinds. Learn and Blurt continue to require their relevant published teaching content; structured questions remain in structured-capable modes. Pending extraction candidates are never admitted as a substitute for reviewed content.

## Scope and proof

Use source-bound disposable fixtures and fake providers. Cover per-session persistence/cancellation, manual/AI choices, full-image Codex payloads, exact/invalid points, unavailable provider, paper work, saved work, duplicate submissions, stale ownership, cancellation and small-window layouts. Run existing provider/marking/navigation/topical/picker gates. Review scoped changes on Standards and Spec separately. Update Unreleased docs and bugwatch; leave changes uncommitted. Deliver a separate copy-paste extraction handoff with current paths, stage/page reuse, model roles, publication acceptance and reserve controls; do not resume extraction in this session.
