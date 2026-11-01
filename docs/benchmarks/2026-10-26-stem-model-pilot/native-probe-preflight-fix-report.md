# Native probe preflight fixes — revision 2

Both P2 findings in `preflight-native-probe-review.md` were reproduced before changing the probe. An injected
`TutorAI` constructor failure left all temporary catalogue mutations in the imported module. Numeric `met:1/0`
was incorrectly credited because Python equates these values with Boolean gold. The archived failing log is
`native-probe-preflight-red.txt`; its 16 test methods reported seven failures and ten errors (including paired
subtests and missing restoration/availability support).

`temporary_catalogue()` now snapshots each dictionary's alias presence/value and the text-only set membership.
Its `finally` covers the first mutation, body entry and setup failures. `execute()` places the whole setup/runtime
inside that context, with an outer file/lock finalizer. Existing values, including a pre-existing `None`, survive;
unrelated entries remain untouched.

Marking scores now require the existing strict marking envelope validator, exact Boolean `met` types, recursive
schema validity and exact criterion text/order before exposing `marking_decision_vector`. Invalid envelopes,
integer/string/missing flags and mismatched criteria leave availability false and both correctness metrics null.
Valid incorrect vectors remain available and explicitly incorrect. Raw schema, criterion, delivery and envelope
metrics stay separate.

CPU verification commands, run from the repository:

```sh
.venv/bin/python -m unittest discover -s docs/benchmarks/2026-10-26-stem-model-pilot -p test_native_probe_preflight.py -v
.venv/bin/python -m py_compile docs/benchmarks/2026-10-26-stem-model-pilot/native_probe_v1.py docs/benchmarks/2026-10-26-stem-model-pilot/test_native_probe_preflight.py
.venv/bin/python docs/benchmarks/2026-10-26-stem-model-pilot/native_probe_v1.py
.venv/bin/python '/Volumes/External SSD TB4/LocalAI/stem-tutor-training/native-probe-v1/native_probe_v1.py'
```

Result: **16 tests pass**, compilation passes, both identical probe copies report 27 jobs / 28 turns and matching
manifest checks. Tests cover normal and exceptional exits, pre-existing alias values/membership, failure during
the first mutation and an actual `execute()` constructor failure using a stub before any native socket. Scoring
covers numeric/string/missing flags, wrong/missing/extra envelope fields, absent requested reasons, wrong/order-
changed criteria, incorrect containers and valid correct/incorrect vectors. The green log is
`native-probe-preflight-green.txt`. No native API, import, GPU job or model-generated code execution occurred.

The exact reviewed eight-file preparation is preserved at
`/Volumes/External SSD TB4/LocalAI/stem-tutor-training/native-probe-v1-preflight`; the repository archive preserves
the old probe and manifest under `native-probe-v1-preflight/`. Every original18 row, prompt, source receipt, gold,
case ID and system file was byte/hash-compared against that archive and remains unchanged. Production source
hashes also pass.

Revision 2 is frozen in `manifest-v2-preflight-fixed.json` on SSD and the identical repository file
`native-probe-manifest-v2-preflight-fixed.json`; SSD `manifest.json` is the identical active receipt.

| Identity | SHA256 |
| --- | --- |
| Archived v1 manifest | `0ceb6614d7fc42bbe7bd0268fd18a96fa0ec24f25c1869dcf5cc1c3176aabf0c` |
| Revision 2 manifest | `f2a5e98a633a3f1b59dc90b00b5706b957d9594a17f298677375e0c397b82f24` |
| Revision 2 probe | `cb1c00d5293fc19e01ec945ab502d3847a2ab63298a360d6bb9ead6646522318` |
| CPU regression tests | `da13e85a97099e3836a5dc8582f6ddaf687740f0322bf8edc28473949d747a9d` |

`native-probe-preflight-fix.diff` exports the scoped archived-to-repaired probe diff without Git operations.
No runtime outputs exist. Native execution remains **HOLD ROOT_GO**, pending scoped rereview and root scheduling.

## Round 2 recorder fix — revision 3

The revision 2 preflight statements above preceded the subsequently preserved Fast v1 run. Its one attempted native
turn and recorder failure are documented in `native-runtime-report.md`; this repair did not repeat it. The full
existing `/Volumes/External SSD TB4/LocalAI/stem-tutor-training/native-probe-results-fast-v1` file/hash inventory was
recorded in `native-probe-round2-preserved-evidence.json` and verified unchanged afterwards.

The recorder passed `turn` twice to `dict()`: once from context and once from the completed observation. The new
pure `contextual_event()` constructs defaults and then merges explicit event fields, so event truth overrides
`case_id`, `turn` or `elapsed_seconds` defaults without duplicate keyword arguments. The recorder delegates to this
helper. No sampler, dataset, schema, scoring rule or product source changed in this round.

Failing-first CPU checks extended the suite with two pure merge cases and two **normal execute-path** regressions.
The latter use real `TutorAI`, `LocalAI`, production speech-document decoding, recording, scoring and final cleanup;
only the base HTTP transport and OS resource probes are stubbed. `asyncio.open_connection` raises if called, proving
the tests never contact the live server. Both successful and `done_reason=length` completions reproduced the actual
`TypeError` before repair. The successful Deep stub also supplies a hidden-thought sentinel and token IDs, and
verifies none survive in public evidence; the failed Fast stub retains its public partial answer, exact counters,
length reason, failure scores and cleanup acknowledgement. These temporary test outputs are not native evidence.

RED command before repair:

```sh
.venv/bin/python -m unittest discover -s docs/benchmarks/2026-10-26-stem-model-pilot -p test_native_probe_preflight.py -v > docs/benchmarks/2026-10-26-stem-model-pilot/native-probe-round2-red.txt 2>&1
```

Result: 20 methods, **four errors**: the two complete execute paths hit the exact runtime recorder collision, and
the two new pure merge tests reported the missing helper. Prior 16 regressions passed.

GREEN used the identical command with output `native-probe-round2-green.txt`: **20 tests pass**. Compilation and
default CPU manifest checks also pass for both identical repository/SSD probe copies, using the commands above.
No native API, model import or GPU job was run by this repair.

Before repair, the complete prepared revision 2 directory was copied to the immutable sibling
`/Volumes/External SSD TB4/LocalAI/stem-tutor-training/native-probe-v2-preflight`. The repository
`native-probe-v2-preflight/` preserves its probe, manifest and tests. Original 18 prompts, all case IDs, golds,
systems, original receipts and input-file hashes remain byte-identical to that archive. The active receipt and new
`manifest-v3-recorder-fixed.json` are identical; the repository copy is
`native-probe-manifest-v3-recorder-fixed.json`.

| Revision 3 identity | SHA256 |
| --- | --- |
| Manifest | `bf40714cc94a158c898453eeec2079c972cb2fb0bed7055b89341318f67092c2` |
| Probe | `7a3b1a10064a460abe007738df46b4f155d5926d5892be9ef2e85a55f9918d54` |
| CPU regressions | `b7bdaf8ed3463fdb9961db37465c359e823ba00a896abbd5291704ef5b3cc244` |

The minimal probe diff is `native-probe-round2-fix.diff`; separate test coverage is exported as
`native-probe-round2-tests.diff`. Both use archived files and `difflib`, with no Git operations. Revision 3 remains
**HOLD ROOT_GO** pending scoped review; no replacement native run or output directory was created.
