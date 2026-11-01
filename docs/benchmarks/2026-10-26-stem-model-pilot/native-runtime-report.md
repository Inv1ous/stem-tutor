# Native runtime probe — stopped after first Fast turn

27 October 2026 (Hong Kong). Root granted exclusive GPU ownership after prior jobs released it. The existing loopback Ollama 0.40.11 server (PID 7374, root session 45763) remained the sole server. Before execution, `/api/ps` was empty, CPU fixture/source checks passed, and pressure was normal. No import, package, learner, preset, configuration, weight or Git changes occurred.

The reviewed revision 2 probe ran once with `caffeinate -i`, main-repository `.venv/bin/python`, `--mode fast --execute --root-go ROOT_GO`. Exec session **90717** exited **1**. The harness forbids output within frozen inputs; root approved the new sibling `/Volumes/External SSD TB4/LocalAI/stem-tutor-training/native-probe-results-fast-v1`. Nothing was retried or overwritten. Deep was **not started** because the runtime problem required stopping. Its proposed sibling directory does not exist.

The planned experiment was 27 jobs/28 turns per mode, 56 turns total. Exactly **one generation request** ran: Fast case `005c35460c204a0c150cd248`, turn 1, a speech-document case. The receipt reports one completed observation and `scores.json` preserves that observation's scores. There are **zero persisted `turn_result` events**: recording the first observation raised `TypeError: dict() got multiple values for keyword argument 'turn'` at probe lines 367/562. `record()` supplies the contextual `turn` and the observation supplies it again. This prevented the other 27 Fast turns and all 28 Deep turns. The runner was not edited.

The generation itself reached `done_reason=length` at its 4096-token bound before that recording error. The 4,209-character public final is reconstructible from 4,096 public content events. Raw recursive schema validation failed with an unterminated JSON string; `DocumentDecoder.finish` failed, delivered=false and delivery gate=false. Speech separation is unavailable. Literal code, marking envelopes/vectors, criterion accuracy, science coverage, topic changes and OPEN protection were not assessed. Mark-vector availability is **0 assessed marking turns**, so conditional accuracy is undefined.

Fast requested genuine Boolean `think=false`; its score reports native-control valid with no observed thinking phase. This establishes only the single attempted Fast request; Deep On remains untested. Presence 1.5 and the other frozen Fast options were requested with the full native document schema. Effective per-field sampler values were not echoed and remain unknown.

| Observation | Actual value |
| --- | --- |
| Cold / warm preload wall time | 0.624773 / 0.013994 s, both successful |
| Entire failed run, including cleanup | 174.084013 s |
| API total / load duration | 173.401547 / 0.000340 s |
| API prompt evaluation / generation duration | 4.078528 / 169.280059 s |
| API prompt / cached prompt / generation counts | 1298 / 0 / 4096 |
| Missing API counters | None of the seven frozen counters |
| First public content after recorded request | 4.155405 s |
| First rendered-block time / application performance | Unavailable: observation recording failed |

Public-content latency is not first rendered-block latency or independently measured network TTFB. Native counters do not establish Python kernel or sampling parity. Public answer content and completion/control metadata were retained; hidden reasoning text and token IDs were discarded at the decode boundary. No generated code was executed.

Cleanup acknowledged `done_reason=unload`; a subsequent `/api/ps` was empty. The probe and caffeinate processes were absent; server PID 7374 remained alive and still reported 0.40.11. Receipt initial/final pressure was 1; swap stayed 3,679,914,557.44 bytes; final SSD free space was 43,312,058,368 bytes. The candidate GPU allocation is released.

SHA256 identities:

- Frozen input manifest: `f2a5e98a633a3f1b59dc90b00b5706b957d9594a17f298677375e0c397b82f24`.
- Repo/SSD probe: `cb1c00d5293fc19e01ec945ab502d3847a2ab63298a360d6bb9ead6646522318`.
- Native MLX alias manifest: `c354ed9ab0a95cb8395c5e9d727868f5927c7f0aa710d807c0d7b8c5f808c898`.
- Fast `receipt.json`: `80f5c232d229a3107af2343810ca99418bce3e134c475a420f439c29db867952`.
- Fast `public-events.jsonl`: `72a80657d50d3ac3244a3f989a7f1b3c52e0b42dbb075140156fbe4964c377cc`.
- Fast `scores.json`: `f824258963da01af31d530bb6b683f05887130e5ddac256672504d84f04b2f6f`.

Root review is needed for the recorder failure before any newly authorized run. Manual science, organic formula completeness, speech meaning, OPEN protection and comparison review remain outstanding; this partial failure supports no native-quality or winner claim.
