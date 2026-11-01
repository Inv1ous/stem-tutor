# Fast main evaluation v1: preserved diagnostic run

Date: 27 October 2026. Both generation jobs completed and released the GPU. This is **protocol-v1 diagnostic
evidence, not a model-promotion comparison**. No further generation was launched after the adapter job.

The pinned base and development-selected update-100 adapter each answered the same frozen 120 rows: 40 per subject,
31 correlated groups. The selected adapter SHA256 is
`a547604e9f64c35ec999a4666d66b50efc7d462b1e35d4a18c8a055fc5a328ac`.
Both used Fast, seed42, 4096 total tokens, a 180-second request deadline, the same publisher-derived sampler and the
14 GiB observed allocation/resource guards. All 240 requests ended with normal stop and no request error.

| Observation | Base | Adapter |
| --- | ---: | ---: |
| Delivered final responses | 120/120 | 120/120 |
| Raw contract valid | 8/120 | 67/120 |
| Host contract valid | 8/120 | 68/120 |
| Narrow host repairs | 0 | 1 |
| Median final duration | 7.759 s | 4.042 s |
| Range of final duration | 1.962–37.247 s | 1.518–39.466 s |
| Median first final token | 0.951 s | 0.968 s |
| Marking vectors matching gold | 5/8 | 0/8 |
| Native model load | 0.813 s | 0.907 s |

First-final-token time includes possible JSON syntax and is not time to an app-rendered block. Model-file hashing
precedes loading and warms the file cache; load measurements are not uncached SSD cold starts. The serial order,
thermal conditions and different generated answers/lengths prevent attributing duration changes solely to training.
Scientific correctness and task coverage have not been independently adjudicated by this runner.

## Protocol limitation discovered during the run

The trainer renders only each row's user and assistant messages. The row user message already contains the short
STEM Tutor identity. Evaluator v1 additionally prepends a SYSTEM instruction to reply in document JSON. In marking
rows this higher-priority instruction competes with the user-level `points`/`feedback` envelope. The adapter's
marking-envelope failures therefore cannot establish a semantic marking regression. Several chat answers also fail
strict layout, escaping or single-object rules. No compact-format reliability or scientific-superiority claim is
justified by these results.

The coordinating agent requested a DEVELOPMENT-only protocol review before any corrected v2 evaluation or future
training decision. The v1 prompts, settings, weights, answers and failures were preserved unchanged. No test-guided
weights, sampler or prompt adjustment was made in these jobs. The separately frozen 18-row challenge, Deep mode,
fusion and native serving were not run by this sequence.

## Reproduction evidence

All evidence is on the SSD at `/Volumes/External SSD TB4/LocalAI/stem-tutor-training/evaluation-v1`:

- `codec-fingerprint.json` (SHA256 `ab1a6a056e98af972d54aa7175945efc338db998f79a3b4dfbf9be6b4a3aca01`),
  generation/scoring runtime fingerprints, and a checksum-manifested snapshot of all 44 tutor-app Python sources.
- Immutable `base-fast-main` and `adapter-fast-main` trials, load receipts, starts and run identities.
- Closed-run `base-fast-main-scores.json`, `adapter-fast-main-scores.json`, their summaries and `fast-main-paired.json`.
- `protocol-v1-applicability.json` records the interpretation limitation and GPU hold.

Generation ran in the isolated SSD MLX environment; scoring used the pinned project dependencies and the preserved
v1 source snapshot. Hidden thought tokens were never decoded or stored. Both variants produced zero counted reasoning
tokens here. No learner files, original weights, environments, Git state or app implementation were modified.

After both jobs: process inventory contained no model/training/Ollama workers, memory pressure was normal (1), and
swap was 3,629.44 MiB versus 3,645.44 MiB before the first job. Caffeinate assertions ended with their owned jobs.
