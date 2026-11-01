# Structured tutor output: local verification

Updated: 27 October 2026. Machine: MacBook Air M4, 24 GiB unified memory.
The shared-output checks below are complete. The separate custom-model pilot concluded without promotion after
content-fidelity and Deep-delivery failures; see [its model card](STEM_TUTOR_MODEL.md).

## What changed

All chat providers generate the same semantic document. The app owns gaps, headings, bullets, step numbers,
equation wrappers and literal code fences. Native schema mechanisms constrain generation; the shared decoder
checks the actual document before recording success. Existing structured marking and card schemas remain separate.
The new shared instructions match detail to the task, require requested coverage and preserve OPEN-answer protection.
Published study references have bounded scope and provenance. Local history is bounded by complete turns.

This does not prove scientific accuracy. An answer can pass document validation and still omit requested facts,
misstate a formula or alter requested code. Failures remain recorded; no successful retry erases its predecessor.

## Retained evidence

Raw visible answers, request metadata and source hashes are in
[the evidence directory](benchmarks/2026-10-26-structured-output/evidence/). The manifest records exact SHA-256 values.
No private reasoning is retained. The independent
[quality audit](benchmarks/2026-10-26-structured-output/quality-audit.md) checks facts, coverage, notation,
code and marking separately from delivery.

| Run | Scope | Delivered |
| --- | --- | ---: |
| Original contract | Six models × three frozen questions | 14/18 |
| Cloud block retry | Sonnet and GPT-6.1-Sol × three questions | 6/6 |
| Initial local block matrix | Four models × eight chat and three marking cases | 37/44 |
| Final-hardening retry | E4B five, GPT-OSS five, Qwen long-history three | 11/13 |
| E4B preset-mode extension | Thinking Off, three frozen questions | 2/3 |
| Additional cloud coverage | Sonnet, nine primary cases and three real short history seeds | 12/12 |
| Additional cloud coverage | GPT-6.1-Sol, nine primary cases and three real short history seeds | 10/12 |

These are small, deliberately challenging samples with different denominators. Do not pool them into a reliability
estimate or a model ranking. The first cloud attempt's full answers were accidentally overwritten before archival;
only its logged metadata survives. It is explicitly excluded from answer-quality scoring.

The original Qwen baseline uses Low thinking, while the larger local matrix uses Off. That is not a matched speed
comparison. Cloud instructions and response lengths changed; measured elapsed differences do not isolate format
transport cost. Long broad questions require more output than short definitions.

The additional cloud cases cover definitions, multiple requested parts, equations, literal source, separate speech,
topic changes and marking. Sonnet returned all four expected marking vectors (seven flags); GPT returned all three
delivered marking vectors (five flags) correctly. GPT also had one chat-seed timeout and one fresh marking timeout.
A separate large-history probe retained Sonnet's actual 16 KB prior turn and passed both turns. GPT's prior-turn
request timed out; its later current-question answer therefore does not establish large-history success. These
failures and the independently adjudicated wording limitations remain in the evidence and quality audit.

The cloud reader also rejects explicit `max_tokens` or `model_context_window_exceeded` termination even if the
partial content happens to form valid JSON. Tests verify that actual reported usage is counted before rejection.
On installed Codex CLI 0.164.0, the ignored legacy image-tool configuration was replaced by the supported
`features.view_image=false` request setting. An actual explicitly attached synthetic image still returned 2+3=5
in 6.48 seconds. This confirms attachment compatibility, not a general latency improvement or tool-isolation claim.

## Reproduced Qwen memory case

The initial seeded-history request exhausted native Metal memory. The revised policy limits optional history only;
the full system, current question and assessment evidence remain. It changes no precision, sampling, native context,
thinking or output limit. This is a planning estimate, not a hard physical-memory bound.

The exact frozen case subsequently passed cold and twice warm: **123.04, 30.59 and 23.15 seconds**. Each real
request contained two messages and 5,870 content bytes, including the unchanged 345-byte current question/evidence.
Native input counts were 1,280 tokens; cached counts were 0, 1,275 and 1,279. Each answer covered fixed ions in the
solid and mobile ions in the melt. The original failure remains in the evidence. This verifies this case only.

## Visual checks

The [capture directory](benchmarks/2026-10-26-structured-output/screenshots/) contains actual Textual compositor
captures at 80×24, 100×30 and 140×46 in Night, Day and Classic, plus actual Obsidian reading views from a temporary
vault. Canonical Markdown, generated Now content and capture metadata accompany them. The synthetic fixture covers
scripts, charges, calculus, code, currency and paragraph/list gaps. Captures do not establish scientific truth.

Two saved GPT-OSS answers were also replayed through the actual chat screen at 80×24 and 140×46 and into a temporary
Obsidian vault. The code-copy answer preserved its requested literal source but contained malformed `\texttt` prose.
The initial real capture exposed a MathJax error. A failing-first regression now detects a known argument-taking
command with no argument at the end of its mathematical group. Both displays preserve that source in the labelled
literal fallback. New native captures verify the MathJax error is gone while valid mathematics and code remain.
The original model answer remains a formatting defect in the audit; the host does not rewrite its factual claims.

Native Quick Look rasterisation was used after a third-party SVG rasteriser incorrectly omitted spaces around bold
labels. The native view confirmed that was a capture artefact. No learner files were modified.

## Known limits

The current local models still make scientific and coverage errors, and some requests fail the document validator.
E4B can omit required clauses and corrupt literal Python. GPT-OSS can produce malformed mathematical escapes.
A successful format check never substitutes for a mark scheme or an independently verified answer.
Custom-model training and its paired held-out checks are recorded separately in
[the pilot report directory](benchmarks/2026-10-26-stem-model-pilot/).
