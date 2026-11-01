# Development protocol contrast: 54 preserved trials

27 October 2026. All three authorised runs are terminal, and the GPU is released. This is a **development-only
protocol diagnostic**, not sealed-test promotion evidence or a scientific model ranking. No further training,
full-v2 evaluation, Deep generation, fusion or native import was launched by this runner.

The same accepted update-100 adapter answered 18 unchanged original VALID rows under each fixed condition:
`legacy_system`, `training`, then `neutral_system`. The data has six correlated groups: six documents (two per
subject) and twelve marking rows (four mathematics, eight physics, no chemistry marking). All conditions used
Fast, seed42, 4096 total tokens, a 180-second request deadline, the same sampler and unchanged 14 GiB observed
allocation/pressure/swap/disk guards. No gold, schema, example or repair request was added.

## Results

| Measure | Legacy system | Training roles | Neutral system |
| --- | ---: | ---: | ---: |
| Delivered final response | 17/18 | 17/18 | 16/18 |
| Normal stop | 17 | 17 | 16 |
| Length stop | 1 | 1 | 1 |
| Request timeout | 0 | 0 | 1 |
| Document raw/host-valid | 5/6 | 5/6 | 3/6 |
| Literal code exact in an accepted document | 3/3 | 3/3 | 0/3 |
| Valid marking envelope | 0/12 | 0/12 | 0/12 |
| Matching criterion identity/order | 0/12 | 0/12 | 0/12 |
| Available marking vector | 0/12 | 0/12 | 0/12 |
| Conditional marking correctness | unavailable | unavailable | unavailable |
| Median request duration | 6.222 s | 4.649 s | 7.197 s |
| Maximum request duration | 134.674 s | 171.647 s | 180.038 s |

No decoded marking vectors met the envelope/criterion requirements. This does **not** mean 36 observed incorrect
scientific decision vectors. Explanation quality and scientific correctness remain manual-review work.
The neutral condition's zero exact-code score is a complete-contract metric: failure to return the expected document
can make this false even if some literal content survives. It is not a separately adjudicated raw-source corruption count.

Removing the additional v1 system instruction did not by itself recover marking envelopes in these development
rows. The fixed neutral directive also did not recover them. This is narrower than an explanation of the cause or
an assertion that the model lost subject knowledge. There is no evidence here for compact-format promotion.
The serial order, stochastic generation and uncontrolled thermal conditions also preclude a general speed ranking.

## Exact long/failure trials

All three length stops reached 4096 final tokens with zero counted reasoning tokens:

- Legacy system: mathematics marking `4ceb371324aa3642e14eae45`, **134.674 s**.
- Training roles: physics marking `ad5711eb8d4291384410f1c7`, **171.647 s**.
- Neutral system: mathematics marking `4ceb371324aa3642e14eae45`, **163.850 s**.
- Neutral timeout: mathematics marking `3cafb447352d84a93a69d7fc`, **180.038 s**, 3928 final tokens;
  `TimeoutError: Evaluation request deadline reached`.

The training condition's length-stop ID differs from the other two. Earlier progress messages misidentified the
length-stop task and then grouped the IDs together; both statements were corrected against exact trial metadata.
No underlying trial was edited or rerun.

## Reproduction and preservation

SSD root: `/Volumes/External SSD TB4/LocalAI/stem-tutor-training/evaluation-protocol-dev-v1`.
It contains all 54 immutable starts/results, load/run receipts, separate closed score/summary files,
`development-protocol-comparison.json`, result checksums, generation/scoring runtime fingerprints and all 44
Python source snapshots. The reviewed evaluator hash is
`d074ca483cd1f25bbe431d89fc8e2cd3b442b094100e5623b6c72c0929b6f9da`;
experiment fingerprint SHA256 is `059223fe62c6a5ae0dfc0e463432bc8083575a9161eda97bd48db622c9986cd8`.

The comparison verifies the same model/adapter file hashes, sampler, selected rows, harness, non-protocol config
and exact user content for corresponding IDs. Only the prescribed system-role/content changes differ.
The source dataset remains `evaluation-development-protocol-v1`; original `data-v2` and every v1 held-out artifact
remain untouched. Scoring used the preserved source snapshot and pinned project dependencies.

One runner-only CPU summary helper initially failed on a null `error` value; it was corrected without editing the
production evaluator or rerunning a model. The already authorised next job had been launched before that helper exit
was inspected. All relevant source hashes were reverified unchanged, with no GPU overlap or model/API error;
`orchestration-note-1.json` preserves the event. Subsequent stage transitions inspected the scoring exit before launch.

After the final job: no model/training/Ollama worker remained, memory pressure was normal (1), and swap was
3565.44 MiB versus 3573.44 MiB before the first condition. Owned caffeinate assertions ended with their jobs.
No hidden thought text, learner files, original weights, environments, app implementation or Git state was modified.
