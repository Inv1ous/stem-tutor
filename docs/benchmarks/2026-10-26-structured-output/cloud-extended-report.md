# Extended live cloud verification

Runs began on 26 October 2026 UTC and completed on 27 October in Hong Kong. These are remote-model checks on the same Mac while the coordinator owned the local MLX workload. They do not isolate formatting transport cost, establish a general latency ranking or prove model accuracy.

## Method and evidence

Both routes use the actual `TutorAI` interface and current shared document decoder. Claude is **Sonnet only, Thinking Off**; ChatGPT is **GPT-6.1-Sol, Low**, through the saved Codex sign-in. Each provider uses a temporary cwd and temporary Claude usage file. Existing settings/authentication and the learner vault are untouched. No local client, local inference, model download or GPU job was created. All clients closed with zero remaining child processes.

Raw visible responses, prompts, schemas, actual usage where delivered, source hashes and all failures are retained in [the first extension](evidence/candidate-cloud-extended-1.json) and [large-context extension](evidence/candidate-cloud-large-context-1.json). Reproduction scripts and logs accompany them; [the separate manifest](evidence/cloud-extended-manifest.json) pins their hashes. No private reasoning is recorded. The first task startup failed before any model call because `tutorlib` was absent from the task-only `PYTHONPATH`; its log is retained and the corrected launch did not overwrite a model trial. No manual model retries were made.

`first_seconds` measures the first validated visible block, not necessarily a raw model token. Codex exec emits completed message items. A successful result establishes delivery through validation, not full scientific correctness. Failed requests have unavailable usage rather than demonstrated zero cost.

## First extension: separate denominators

| Route | Primary cases | Auxiliary real seed turns | All rows | Delivered marking vectors | Correct point flags among delivered vectors |
| --- | ---: | ---: | ---: | ---: | ---: |
| Sonnet Off | 9/9 | 3/3 | 12/12 | 4/4 | 7/7 |
| GPT-6.1-Sol Low | 8/9 | 2/3 | 10/12 | 3/4 | 5/5 |

Primary cases are physics, exact code, speech, OPEN hint, current evidence after real prior turns, and four marking cases. Auxiliary turns are not extra independent science questions. The three frozen marking cases preserve the initial local-matrix wording; the fourth tests an explicitly omitted kinetic-energy conclusion. Both code answers passed exact-line/same-block and Python AST parsing checks; generated code was never executed.

| ID | Route | Case | Delivered | Seconds | Content / coverage observation |
| --- | --- | --- | --- | ---: | --- |
| C1 | Sonnet | physics_calculation | yes | 4.87 | Correct 2.0 m s⁻², formula/substitution, two significant figures and velocity check. |
| C2 | Sonnet | literal_code | yes | 2.87 | Requested record line is exact in the same code block as a parseable square function; source not executed. |
| C3 | Sonnet | speech | yes | 5.35 | Correct sulfate atom counts and overall −2. Sonnet adds substantial extra detail and uses digit 4 / unspelled Na in speech; GPT is concise and spoken prose is clean. |
| C4 | Sonnet | open_hint | yes | 2.43 | Useful F=ma nudge; final 6 N withheld. |
| C5 | Sonnet | context_seed_alkanes | yes | 3.00 | Correct CnH2n+2 and total-carbon meaning/minimum. |
| C6 | Sonnet | context_seed_alcohols | yes | 2.94 | Sonnet: correct CnH2n+2O / CnH2n+1OH; no rings, only single C–C bonds, one OH. Other-functional-group exclusion not explicit. GPT: no answer before deadline. |
| C7 | Sonnet | context_seed_summary | yes | 2.11 | Sonnet summarises both formulae correctly. GPT summarises only the alkane actually retained after the alcohol timeout. |
| C8 | Sonnet | long_context | yes | 2.21 | Correct solid fixed-ion / molten mobile-ion explanation in exactly two bullets. Only short prior turns in this phase. |
| C9 | Sonnet | mark_ionic_definition | yes | 3.59 | [true], exact copied point and student quotation. |
| C10 | Sonnet | mark_physics_units | yes | 4.45 | [true,false]; correct method receives credit, wrong m/s acceleration unit does not. |
| C11 | Sonnet | mark_catalyst | yes | 3.88 | [false,false]; contradicted equilibrium claim and omitted rates claim receive no credit. |
| C12 | Sonnet | mark_physics_omission | yes | 3.76 | Sonnet [true,false], denies unstated speed-scaling conclusion. GPT times out; no decision vector to assess. |
| C13 | GPT-6.1-Sol | physics_calculation | yes | 9.00 | Correct 2.0 m s⁻², formula/substitution, two significant figures and velocity check. |
| C14 | GPT-6.1-Sol | literal_code | yes | 9.22 | Requested record line is exact in the same code block as a parseable square function; source not executed. |
| C15 | GPT-6.1-Sol | speech | yes | 6.76 | Correct sulfate atom counts and overall −2. Sonnet adds substantial extra detail and uses digit 4 / unspelled Na in speech; GPT is concise and spoken prose is clean. |
| C16 | GPT-6.1-Sol | open_hint | yes | 9.61 | Useful F=ma nudge; final 6 N withheld. |
| C17 | GPT-6.1-Sol | context_seed_alkanes | yes | 12.12 | Correct CnH2n+2 and total-carbon meaning/minimum. |
| C18 | GPT-6.1-Sol | context_seed_alcohols | **no** | 300.01 | Sonnet: correct CnH2n+2O / CnH2n+1OH; no rings, only single C–C bonds, one OH. Other-functional-group exclusion not explicit. GPT: no answer before deadline. |
| C19 | GPT-6.1-Sol | context_seed_summary | yes | 262.56 | Sonnet summarises both formulae correctly. GPT summarises only the alkane actually retained after the alcohol timeout. |
| C20 | GPT-6.1-Sol | long_context | yes | 7.59 | Correct solid fixed-ion / molten mobile-ion explanation in exactly two bullets. Only short prior turns in this phase. |
| C21 | GPT-6.1-Sol | mark_ionic_definition | yes | 8.12 | [true], exact copied point and student quotation. |
| C22 | GPT-6.1-Sol | mark_physics_units | yes | 8.52 | [true,false]; correct method receives credit, wrong m/s acceleration unit does not. |
| C23 | GPT-6.1-Sol | mark_catalyst | yes | 7.83 | [false,false]; contradicted equilibrium claim and omitted rates claim receive no credit. |
| C24 | GPT-6.1-Sol | mark_physics_omission | **no** | 150.01 | Sonnet [true,false], denies unstated speed-scaling conclusion. GPT times out; no decision vector to assess. |

The first phase’s case name `long_context` is retained for reproducibility, but it follows only three brief attempted organic turns. Sonnet retained all three. GPT’s alcohol turn timed out at **300.01 s** and was not committed; its later summary took **262.56 s**, contained 71 output tokens and reported zero reasoning-output tokens. The current NaCl reply then took **7.59 s** with two successful prior turns retained. These observations do not establish a history-format cause. The fresh memoryless GPT physics-omission marking call also timed out at **150.01 s**.

Sonnet’s speech case covers the requested core facts but is longer than requested, includes a digit `4` instead of spelling it out and uses `Na` rather than spelling its letters in the spoken version. Several optional visual facts are not repeated verbatim in speech. These are presentation limits despite valid required fields. No material error was identified in the core physics calculation, exact code, OPEN protection or delivered marking decisions. The seed alcohol answer gives the correct conventional formula but does not explicitly exclude other functional groups. None of these small checks establishes full syllabus or exam-marking reliability.

## Actual large prior context

The second phase supplies **15,843 UTF-8 bytes** of repetitive synthetic old-topic text, within a **16,086-byte user prompt**, asks for only a brief acknowledgement, then sends the identical **345-byte current NaCl question/evidence** from the frozen local matrix. Four full 120-repeat blocks were used; eight would exceed the requested 12–17 KB range. This is a distractor-retention check, not realistic comprehension or a context-window-capacity test.

| ID | Route | Case | Delivered | Seconds | Interpretation |
| --- | --- | --- | --- | ---: | --- |
| L1 | Sonnet | large_context_seed | yes | 2.03 | Acknowledgement delivered; persistent conversation retains the actual large user turn. |
| L2 | Sonnet | current_after_large_context | yes | 2.41 | Correct two bullets, no organic contamination; native usage reports 8,499 cached input tokens. |
| L3 | GPT-6.1-Sol | large_context_seed | **no** | 300.01 | Deadline failure; no seed is committed and no robustness pass is claimed. |
| L4 | GPT-6.1-Sol | current_after_large_context | yes | 56.26 | Correct two bullets, but actual native input contains one message and prior-seed success is false. This is a fresh reply, not a large-history pass. |

For the large-context phase only, Codex native events were captured as **type, elapsed time, item type, phase and status**, with no item text or reasoning content. The failed seed emitted `thread.started` around 0.29 s, three completed `error` items around 0.86 s, and `turn.started`, then no final message before timeout. The subsequent successful fresh reply also emitted three initial `error` items around 0.73 s, then its final agent-message item around 55.17 s and completion around 55.19 s. Thus those startup items alone are not sufficient to explain the timeout. Their message text was deliberately not captured.

## Outcome and limits

Both cloud routes have live physics, exact-source code, spoken output, OPEN protection, short multi-turn context and delivered grading evidence. Sonnet also passes the actual large-prior-turn case. GPT’s large seed and one grading request fail their existing deadlines; those failures remain explicit. A separate controlled diagnosis is required before assigning a cause or changing history representation. No such A/B test or app fix was launched here.

The source dictionaries in both JSON files identify the exact code loaded at each start. Current model choices, thinking choices, cloud authentication and local runtime settings were not changed. These added checks close coverage gaps through honest attempted outcomes; they do not convert delivery failures into passes or claim identical wording across models.

## Separate public-startup diagnostic

One additional fresh acknowledgement request used the same actual GPT-6.1-Sol Low route, with an explicitly separate
60-second diagnostic deadline. It completed successfully in **6.48 seconds**. This is not a retry of a failed benchmark
question and not a history A/B test. The app's normal deadline was not changed.

[The diagnostic](evidence/codex-startup-diagnostic-1.json) records only public `item.type=error` message/text/error
fields, bounded to 600 characters per string and passed through credential redaction, plus event types/timestamps.
Reasoning-item text is excluded. The installed version is **codex-cli 0.164.0**, recorded separately.

The three startup items are configuration warnings: two say the unrecognised `tools.view_image` setting is ignored,
and one warns that `skip_host_skill_discovery` is under development. They are not authentication/network errors.
The same warning pattern accompanies a successful minimal request and a successful larger reply, so it does not
establish the cause of the latency failures. No warning suppression, user-config edit or production-code fix was made.
The unsupported image-setting flag warrants a separate capability-isolation review against this installed CLI; this
diagnostic does not establish which image tools remain available.

A fresh memoryless marking request and a fresh large-context seed both timed out, while another history-bearing
reply was fast. Therefore the observed failures cannot be assigned to wire-history representation alone. Any later
controlled fresh/wire-history/Markdown-history experiment must remain a separate diagnostic with identical model,
system, schema and thinking settings, not a selective replacement of these failed observations. All diagnostic
clients closed with zero remaining children and no local client.

## Installed-CLI compatibility confirmation

The coordinator replaced the ignored legacy `tools.view_image=false` setting with the installed CLI's supported
`features.view_image=false` flag. No user configuration was edited. The earlier benchmark and diagnostic evidence
above remains byte-for-byte unchanged and is not relabelled as running the new code.

One new [explicit-image confirmation](evidence/codex-image-capability-confirmation-1.json) used the actual `TutorAI`
GPT-6.1-Sol Low route with the same separate 60-second diagnostic cap. Its temporary, visually checked PNG showed
`2 + 3 = ?`; the text prompt asked only to read the attached image and return its equation/result, without revealing
the image contents. The [fixture](evidence/codex-image-capability-fixture-1.png), checksum and reproduction script
are retained. No learner image, local OCR, local model or local GPU operation was used.

The result was a validated equation **2 + 3 = 5**, completed in **6.48 seconds**. Captured native subprocess arguments
contain both `features.view_image=false` and the explicit `--image` attachment, and contain no legacy
`tools.view_image` key. The ignored-setting warnings are absent. Only the pre-existing warning about the
under-development `skip_host_skill_discovery` feature remains; it was not suppressed.

This confirms that the supported flag is sent without the legacy warning and explicit supplied images still work
in this small case. It does not prove general filesystem/tool isolation, broad image/diagram competence, or a latency
improvement. The successful six-second observation does not explain or erase earlier 150/300-second failures.
All children closed, the temporary input directory was removed, and no local client was created.
