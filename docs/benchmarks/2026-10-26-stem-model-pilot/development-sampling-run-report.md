# Development sampling run report

27 October 2026. **36 fresh requests completed; development diagnostic only.** The accepted update-100 adapter was tested on the same frozen 18 rows per arm: six document rows and twelve marking rows, representing **six correlated groups**. Marking covers Mathematics and Physics; **no Chemistry marking examples** occur here. These are original development examples, not sealed-test promotion evidence.

## Controlled comparison

Fresh A (presence 1.5) ran before fresh B (presence 0.0), serially. Neither arm reuses the earlier protocol control. Both use training-matched user-only roles, Fast mode, seed42, temperature0.7, top-p0.8, top-k20, presence span1024, 4096 total tokens, 180-second deadline and 14 GiB observed allocation budget. The dedicated CPU validator confirms that **presence_penalty is the only changed configuration/sampler field**. All other run identity, base/adapter files, tokenizer/template assets, resolved thought/stop tokens, evaluator source and all18 prompt/message hashes match.

| Metric | A: presence1.5 | B: presence0.0 |
| --- | ---: | ---: |
| Delivered / attempted | 17/18 | 12/18 |
| Raw and host document contracts | 5/6 | 6/6 |
| Exact literal code | 3/3 | 3/3 |
| Marking envelopes / matching criteria / available vectors | 0/12 each | 0/12 each |
| Median response seconds | 4.566 | 6.298 |
| Maximum response seconds | 150.020 | 180.077 |
| Length failures / deadline timeouts | 1 / 0 | 1 / 5 |

Marking conditional correctness is **unavailable**, not an observed set of wrong decision vectors. Formatting/source-copy success does not establish scientific accuracy; manual science review remains pending. Timing includes failed attempts. The deadline is checked between generated tokens and can slightly exceed180seconds; it cannot interrupt an active kernel. This fixed-order, single-seed comparison does not isolate order, cache or thermal effects. It supplies no general latency guarantee.

## Preserved failures

All failures are marking requests. No retries or discarded attempts occurred.

| Arm | ID | Failure | Seconds |
| --- | --- | --- | ---: |
| A | `ad5711eb8d4291384410f1c7` | length,4096 tokens | 150.020 |
| B | `1647bbfdf666831dbaedd5ec` | length,4096 tokens | 162.963 |
| B | `30d3f0250c65cb529098d4be` | timeout | 180.038 |
| B | `9f1258a8c99a81a693f79db3` | timeout | 180.053 |
| B | `ad5711eb8d4291384410f1c7` | timeout | 180.077 |
| B | `c58ad26c013848559f4ab9cf` | timeout | 180.056 |
| B | `cfa3c77dd0ff5f41ca593d78` | timeout | 180.048 |

## Frozen evidence

SSD root: `/Volumes/External SSD TB4/LocalAI/stem-tutor-training/evaluation-sampling-dev-v1`. Both processes exited0; all36 trials and36 start markers remain. The final manifest verifies132 artifacts, including all44 source snapshots, runtime receipts and public outputs. No hidden reasoning text was retained.

SHA256 identities:

| Artifact | SHA256 |
| --- | --- |
| Evaluator | `ba1f4f755d18b93860b43730c2fda12f485e72cf1ee53e0d88173878afbad491` |
| Source/experiment fingerprint | `6ff7eab317dc252720fdca7ca78c806853fff599eb038abfb638564b2ce9e936` |
| Generation runtime receipt | `a19a20506f758824ad6d8b1bdc7351d3201b3c5c427903b22bcbae2e3af8daa5` |
| Scoring runtime receipt | `91d2ac39f752a8ac119966f61f231a4cc7c06527c6858d22e1497be1dccb2769` |
| Runtime dependency lock | `72d170d30f49cf81797685499d131159027c445ce6829f120e39c70235dd1d98` |
| Frozen selection | `585081b48c45e53224f212a3e787cc2ec30767dbce7ca4e9697e04dc36dcf3a8` |
| Update-100 adapter | `a547604e9f64c35ec999a4666d66b50efc7d462b1e35d4a18c8a055fc5a328ac` |
| Final comparison | `14a753c5f833ffc608683015077d80e42d1d38ab6cc3a3bbb38b5b60657339b5` |

## Decision

Retain published Fast presence1.5 and unchanged Deep1.5. Compact-prompt and marking gates **FAILED**. These data support neither a recommended preset nor a shorter production brief. Zero presence improves one document contract but worsens delivery. No further GPU work was authorized or launched by this evaluation runner after36; subsequent fusion work belongs to the separately authorized coordinator.
