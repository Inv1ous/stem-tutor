# Native probe preflight review

27 October 2026. Scoped CPU-only review of the frozen native probe, manifest and inputs.
**Two P2 findings require repair before execution. No native/GPU request was made.**

1. **Restore every temporary catalogue entry, including setup failures.**
   `native_probe_v1.py:396–401` mutates `LOCAL_MODELS`, `TEXT_MODELS`, `KEEP_ALIVE`, `CONTEXT_LENGTH` and
   `MAX_CONTEXT_LENGTH` without preserving original membership/values. The finalizer at `537–565` closes runtime
   resources but never restores those imported production-module globals; initialization at `402–405` also precedes
   that finalizer. Standalone process exit limits persistence, but the explicit restoration contract is unmet and
   calling `execute()` in a surviving process leaves altered model availability/configuration. Snapshot existing
   values and set membership, then restore them in an outer `finally` covering the first mutation onward.

2. **Do not credit malformed marking labels as correct Boolean decisions.**
   `native_probe_v1.py:270–275` compares arbitrary parsed `met` values with Boolean gold using Python equality,
   independently of recursive schema validity. CPU reproduction using the real oxidation-omission case and
   `met:1`/`met:0` returns `raw_schema_valid=False` but `marking_labels_equal=True`, since `1 == True` and
   `0 == False`. The same metric can credit an invalid marking envelope. Require a valid marking envelope and
   exact Boolean labels before exposing a decision vector; report unavailable conditional correctness when the
   envelope/criterion contract fails. Preserve separate raw-schema, delivery and criterion metrics.

The CPU manifest command passes: 27 jobs/28 turns per mode, all original18 prompts unchanged, three original
marking-prefix conflicts explicitly labelled, six independent mark traps, organic question, real topic-change
conversation and OPEN hint. Inputs exclude gold except supplied assessment criteria; scoring loads separate gold
after requests. Production `TutorAI(document=True)` streaming/one-shot routes, schemas, system construction and
native Boolean think controls are used. Both requested samplers retain presence1.5 and effective values remain
explicitly unknown.

An isolated CPU extraction of `ProbeLocal` verified hidden thinking becomes only a Boolean phase marker, unknown
fields disappear and final-channel thought delimiters discard content. No generated code execution is present.
Available API counters are captured before production default-filling, with missing keys listed separately.
Science/OPEN remain manual review. Per-turn bounds, watchdog cancellation, residency checks and owned-candidate
cleanup are present; actual native allocation/GPU behaviour still requires operational proof.

Manifest SHA256 at this review: `0ceb6614d7fc42bbe7bd0268fd18a96fa0ec24f25c1869dcf5cc1c3176aabf0c`.
Probe SHA256: `304c8e0be305c144a29416a5aa80170779cf9f0d2db30ffeafab573a26f4e19d`.
Compilation/check/sanitizer/type-confusion probes were CPU-only. Product sources, frozen originals, learner files,
cloud settings and Git state were unchanged.
