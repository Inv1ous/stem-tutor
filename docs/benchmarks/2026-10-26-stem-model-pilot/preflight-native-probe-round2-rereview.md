# Native probe recorder rereview

27 October 2026. Scoped review of the revision2→revision3 recorder fix and added CPU regressions.
**Recorder collision addressed; no new serious findings in this fix.**

`contextual_event()` uses a dictionary-display merge, applying explicit event fields after context defaults
(`native_probe_v1.py:333–337`). This removes duplicate-keyword construction, preserves the measured event's
`case_id`, `turn` and `elapsed_seconds`, and mutates neither input. The actual recorder delegates directly to
that helper (`372–374`). The remaining probe changes only advance the frozen revision identity.

Independently reran **20 CPU tests: all passed**. The added complete execute-path tests retain real `TutorAI`,
`LocalAI`, document decoding, recording, scoring and cleanup while replacing HTTP transport/OS probes. They
forbid native sockets, cover both a successful Deep completion and a failed Fast length stop, and verify exact
counters, failed delivery/format metrics, owned unload, catalogue restoration and absence of hidden sentinel/token
IDs from public evidence. These synthetic completions establish harness behaviour, not model quality.

The CPU manifest command passes at27 jobs/28 turns. Current repo/SSD probe and manifest match the declared hashes:

- Probe: `7a3b1a10064a460abe007738df46b4f155d5926d5892be9ef2e85a55f9918d54`.
- Manifest: `bf40714cc94a158c898453eeec2079c972cb2fb0bed7055b89341318f67092c2`.

Inputs, gold, systems and original fixture/receipt copies remain byte-identical to the revision2 archive.
No sampler, schema, scoring rule, product source, learner/cloud setting or prior native result was changed by
this review. No API/GPU/model calls occurred.

This clears the recorder repair only. The preserved native model's4096-token looping failure remains a separate
unresolved result; proceed with root's bounded development diagnosis before any replacement large batch.
