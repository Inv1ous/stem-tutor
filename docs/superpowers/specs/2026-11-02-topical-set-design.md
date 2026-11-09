# Custom topical past-paper sets

## Intent

Allow the learner to choose multiple subtopics from the same or different chapters, choose question types and request a random number of reviewed past-paper questions. Reuse current course categories, reviewed content and grading; do not generate new questions or broaden a filter silently.

## Approaches

One overloaded picker would crowd small terminals. A separate topic selector would duplicate existing navigation. Reuse `PickerScreen` multi-select for Topical, followed by a compact native setup screen. A Change topics button reopens the picker with current ticks; cancellation preserves pending settings. This is the implementer's choice under the learner's standing request to proceed without questions.

## User flow

1. Home > Topical past papers opens the existing folder/search picker. Space toggles a subtopic or whole folder; Enter opens folders and toggles leaves; Ctrl+A selects shown topics, Ctrl+D clears. Ticks persist across folders/search. Continue or Ctrl+S proceeds only with a nonempty selection. Other picker modes retain their current behaviour.
2. Setup shows the selected topic summary, count (default 10, whole numbers 1–200), type checklist (all selected initially), unique matching availability and Start. Types are MCQs; Definitions; Written answers; Calculations / expressions; Long / structured questions. A short question is a Definition only with an explicit Define command or leading definition request. Other short questions are Written; numeric/expression are Calculations; structured remains Long/structured, which may mix writing and calculation. MCQs remain MCQs even when their stem contains calculation or definition words.
3. Counts are grounded in the eligible reviewed bank and scoped learner exclusions. Zero-count categories remain visible and selectable so the absence is understandable. Empty types, invalid counts and no eligible matches prevent Start with specific feedback. If requested count exceeds unique availability, explicitly show the smaller planned count and Start label; do not duplicate questions or borrow unselected topics/types.
4. Start submits selected topics, count and types through the engine. Change topics retains the count/types; cancelling setup does not start or replace a study session. Settings/presets/models are unaffected.

## Sampling and persistence

Build a set with a random question order within each topic and shuffled topic rounds. A scarce topic contributes when possible before a large topic consumes the set. A question mapped to several selected chapters still occupies one slot, identified by existing canonical paper/part identity. One bank item, including a long structured question, counts as one question irrespective of marks. Randomness uses the Tutor's existing seeded RNG; the planned identity/chapter queue persists for resume.

Revalidate the current reviewed bank, eligibility, chapter exclusions, disclosed aliases and used canonical identities before serving. Unavailable planned questions are skipped; never replace them with unrelated material or resurrect excluded questions. Preserve the chosen serving chapter for support and exclusion policy. Existing saved open attempts, correction/answer history and source bytes are preservation boundaries. Legacy topical sessions without new options keep their time-derived budget and behaviour.

Archived postponed attempts remain in their durable recovery records and are reserved from a new counted or filtered set. They must not be injected as additional questions outside the selected types/count; ordinary later sessions can recover them through the existing path. Active protected attempts still prevent session replacement under existing engine guards.

The current registered bank has only MCQ/structured labels and no command-word tags. This feature does not claim that Definitions or pure long calculations are separately available. Use honest category labels and counts rather than AI classification, OCR guesses or Library mutation. Only reviewed bank material is eligible; extraction candidates remain unpublished.

## Verification and delivery

Test exact count, type intersection, cross-chapter selection, canonical duplicates, balanced topic rounds, seeded randomness, exhaustion, persisted resume, exclusions/prerequisites, disclosed aliases, invalid options without session mutation and legacy behaviour. Native UI checks cover keyboard selection, editing/search shortcuts, topic changes, cancellation, count/type errors, zero availability and usable Start at 60x20, 80x24 and 100x30 across themes. Reuse Library readers for real assessments; synthetic variants stay in disposable vaults. Run focused existing topical/picker/session guards and independent Standards/Spec reviews against task snapshots. Update Unreleased docs and bugwatch; do not stage, commit, publish or run inference.
