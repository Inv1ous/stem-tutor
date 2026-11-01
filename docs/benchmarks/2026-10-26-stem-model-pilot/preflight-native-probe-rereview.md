# Native probe revision 2 rereview

27 October 2026. Scoped review of the two preflight repairs and their exact diff.
**Both findings addressed; no new serious findings in this fix round.**

1. **Catalogue restoration: addressed.** `temporary_catalogue()` snapshots all four alias mapping entries and
   text-only membership before mutation, then restores original presence/value, including pre-existing `None`,
   in its `finally` (`native_probe_v1.py:307–330`). `execute()` enters this context before tutor construction;
   the outer finalizer closes event/lock handles even when context entry or setup fails (`438–444`, `605–607`).
   Normal, exceptional and first-mutation failures are covered without replacing unrelated catalogue entries.

2. **Malformed marking credit: addressed.** Scoring now invokes the existing strict envelope validator and
   requires recursive schema validity plus exact criterion identity/order before exposing a vector
   (`273–291`). Integer/string/missing flags and malformed envelopes leave vector availability false and
   correctness null. Valid incorrect Boolean decisions remain available and false. Raw schema, envelope,
   criterion and delivery observations remain separate.

Independently reran the focused CPU regressions: **16 tests passed**. The CPU manifest command passes with
27 jobs/28 turns. Verified identical current repo/SSD probes and revision2 hashes:

- Probe: `cb1c00d5293fc19e01ec945ab502d3847a2ab63298a360d6bb9ead6646522318`.
- Manifest: `f2a5e98a633a3f1b59dc90b00b5706b957d9594a17f298677375e0c397b82f24`.

Inputs, gold, systems and all three original fixture/receipt copies hash-match the preserved preflight archive.
The reviewed diff retains requested native options, production routes, logging boundary and resource controls.
No native/API/GPU/model calls, original-input changes, learner/cloud changes or Git operations occurred.
The probe is ready for root's separately coordinated bounded execution; actual native results remain untested.
