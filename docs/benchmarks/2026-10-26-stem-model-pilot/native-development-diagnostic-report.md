# Native DEV diagnostic — seven conditions attempted, delivery gate failed

27 October 2026 (Hong Kong). Root authorized the exact frozen DEV7 command. `/usr/bin/caffeinate -i` ran exec session **99490**, exit **0**, in **82.201 seconds**. Exit zero means the harness finished, not that model quality passed. One Python reference and five native generations ran; marking was blocked before generation. No retries, parameter changes or additional GPU conditions occurred.

The new SSD output is `/Volumes/External SSD TB4/LocalAI/stem-tutor-training/native-development-diagnostic-results-v1`. [Frozen scripts, inputs, manifest and CPU render proof](dev-diagnostic-v1/manifest.json), [observations](dev-diagnostic-v1/results/observations.json), [scores](dev-diagnostic-v1/results/scores.json) and [public events](dev-diagnostic-v1/results/public-events.jsonl) are copied into `dev-diagnostic-v1/`. Gold stayed separate from generation; no hidden reasoning text, token IDs, logits or generated-code execution were retained. The original first native challenge failure's three SHA256 identities remain unchanged.

Every calculation uses the fresh DEV user with 6.0 N and 0.50 m. Correct work is **3.0 J**. Fast limits were512 tokens/45 seconds; Deep1024/60, with the frozen samplers. Full app instructions and examples were retained for C/D/Deep.

| Condition | Seconds / end | Raw schema / DocumentDecoder | Public arithmetic and speech |
| --- | --- | --- | --- |
| Python user-only, unconstrained | 4.165 / stop | fail / fail | Formula and substitution only; no calculated result, unit or speech. |
| A native user-only, no format | 5.516 / stop | fail / fail | Correct3.0 J; speech missing and paragraph contains nested layout. |
| B native user-only, speech schema | 5.324 / stop | pass / pass | Visual substitution omits final result; separate speech correctly gives3.0 J. |
| C native full app, no format | 6.654 / stop | pass / pass | Correct formula, substitution,3.0 J and separate spoken answer. |
| D native full app, speech schema | 20.175 / length | fail / fail | Equation starts `W=Fd=6.0+6.0+0.50=3.00+3.00…`, repeats and truncates; application fails. |
| Marking | 0.026 / blocked | unassessed | No generation or decision vector. |
| Deep full app, speech schema | 40.182 / length | fail / fail | Thinking phase observed;1024 generated tokens and no public answer or speech; application fails. |

All five native generations expose all seven frozen API counters; marking has none. Fast thinking-Off and Deep thinking-On phase checks pass for their actual generations; marking control is **unassessed**, despite the generic scorer's absence-of-thinking Boolean. D first public/first rendered times were0.197/1.054 seconds. Deep has neither. C/A/B were raw transport contrasts, so rendered-block timing is unavailable. Python first public time1.181 seconds is separate from native API counters.

Actual outgoing D matched its frozen payload; C/D were asserted identical except `format`. C evaluated1298 prompt tokens with0 cached; D1298 with1294 cached. This single fixed-order result supports investigating a grammar/full-prompt interaction, but does not establish a sampler or kernel defect. B's syntactic success did not establish complete visual mathematics. Genuine Deep did not rescue delivery within its fixed total-token bound; no hidden content was inspected.

The marking failure is a harness serialization issue, not grading evidence. [Post-terminal CPU reconstruction](dev-diagnostic-v1/results/mark-payload-cpu-diff.json) finds only `messages[1].content` differs: both1655 characters, first difference1243. Canonical fixture serialization alphabetizes schema keys; runtime `json_instruction` embeds that loaded order, while the frozen captured prompt embeds production insertion order. The assertion rejected the request before recording/sending it. This reconstruction is explicitly not a retained actual wire request. No fix or rerun followed.

[Cleanup receipt](dev-diagnostic-v1/results/receipt.json) confirms the candidate unloaded and native residency empty; the root-owned server was left running. Pressure remained1, swap growth0; SSD free43.304 GB. Native reported size_vram checks are not a hard peak-allocation guarantee.

Do not promote or resume the challenge batch. A custom-model-only omission of native `format`, retaining full system/schema instructions and mandatory strict DocumentDecoder, is a **DEV confirmation hypothesis**. Freeze broader DEV confirmation before any product change; repair and review marking capture separately. This is not evidence for a compact brief, parameter tuning or new weights.

Frozen manifest SHA256: `427dd7ff3cd4b4937dbb5ec71c2203ef181ef5bda082d8ec35182f08f23f768a`. Executed source SHA256: `70d5b07e79417013b7558c91360e3180d413a99505d3002e4c9ea9bab3659ba5`.
