# Native full-schema probe v1 — HOLD ROOT_GO

Preparation and repairs use no native API/GPU, package, learner, weight or Git changes. Root’s preserved native attempt is documented separately. `native_probe_v1.py` exists here and identically at `/Volumes/External SSD TB4/LocalAI/stem-tutor-training/native-probe-v1/native_probe_v1.py`.

The SSD directory freezes 27 jobs / 28 turns **per mode**, separate `inputs.jsonl` and `gold.jsonl`, production systems, source hashes and unchanged copies of all three original format-challenge-v1 files. Its 18 original user prompts remain byte-for-byte unchanged, including the three marking prompts whose “Reply in document JSON” prefix conflicts with their requested marking envelope. Their conflict is explicitly labelled, never silently repaired. Six new hand-verified mark traps use real `prompts.judge`: oxidation omission, reduction negation, kinetic-energy scaling contradiction, erroneous work relationship plus unit omission, constant-derivative negation and incorrect antiderivative with independently correct arbitrary constant. The gold rationale is separate from prompts; supplied marking criteria remain legitimate assessment evidence.

The remaining jobs are the question “What are the formulaes we need to know for 9701 organic chemistry”, a real two-turn oxidation→potential-difference conversation retaining generated history, and an OPEN quadratic hint forbidding roots/factors/full solution. Organic formula coverage, science, speech meaning and OPEN protection require manual review; no narrow formula gold implies completeness. No image was supplied: `macos:vision` is configured through real TutorAI, while OCR remains untested.

Execution uses real `TutorAI(document=True)` stream and one-shot routes, production systems, `document_schema(False/True)` and `local_judge_schema(criteria)`. Temporary catalogue/text-only/keep-alive/context entries exist only within the harness process. It refuses source/fixture drift, missing/non-MLX native manifest, a server version other than 0.40.11, another loaded native model or reused output directory. It connects only to the existing loopback server and cannot import/register a model or start another server.

Fast requests native `think=false`, temperature 0.7/top-p0.8/top-k20; Deep requests `think=true`, 1.0/0.95/20. Both request presence 1.5, frequency 0, repetition 1, repeat-last-N 1024, min-p 0 and seed 42. These remain **requested options**; effective per-field values are not assumed from API acceptance. Recorded [native source inspection](../../research/2026-10-26-stem-model-specialisation.md#native-ollama-sampling-support-source-check) maps presence/frequency/repeat-last-N into Go MLX sampling; native ordering differs from Python. Neither Python quality results nor matching scalars establish native quality/timing parity.

At decode entry, `message.thinking` text is popped/deleted before recording or yielding. Production receives only a boolean phase marker for genuine Off/On and thinking timing. Unknown event fields and token IDs are discarded; explicit thought delimiters in final content fail closed. Saved evidence contains public final content, completion/error events, exact available API counters with missingness, requested payloads and timing. Raw wire NDJSON is never retained; the earlier integration plan now says this explicitly. Code is compared literally and never executed.

Each mode runs separately under root scheduling and one harness lock. Cold/warm preload results and all failures remain visible. Each turn is bounded to 4096 tokens/300 seconds; mode wall time is 7200 seconds. A watchdog checks normal initial pressure, sustained-warning/critical pressure, swap growth 512 MiB, SSD 20 GiB and OS 3 GiB headroom. Reported native `size_vram` is checked against 14 GiB; this is not a hard native allocation limit. Cleanup closes sockets and unloads only the run-owned candidate.

Scores separate raw recursive schema validity, mandatory `DocumentDecoder.finish`, exact criterion/order/labels, literal code, speech separation, native controls, delivery and manual science/OPEN review. First-rendered-block time is measured at actual stream yield; marking has no rendered-block time. Actual kernel counters remain distinct from wall time.

## Preflight fixes — revisions 2/3; HOLD ROOT_GO

Both P2s fixed: five catalogue entries restore through setup failures; malformed Boolean/envelope/criterion contracts expose no marking vector or correctness. V1/v2 archives preserve inputs/golds/IDs. Recorder event fields override context defaults.

CPU regression command (20 pass):

```sh
.venv/bin/python -m unittest discover -s docs/benchmarks/2026-10-26-stem-model-pilot -p test_native_probe_preflight.py -v
```

Compilation and manifest checks pass. [Appended repair report, hashes and scoped diffs](native-probe-preflight-fix-report.md#round-2-recorder-fix--revision-3). CPU repairs only.
