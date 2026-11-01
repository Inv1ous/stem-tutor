# Evaluator protocol review

Date: 27 October 2026 (Hong Kong). Scope: CPU source/data/tokenizer inspection only. No model loading,
inference, GPU call, production-source change or learner-data access occurred. The pinned tokenizer was loaded
locally with Transformers; MLX was not imported. The accompanying
[evidence receipt](evaluator-protocol-cpu-proof.json) records source/data hashes and rendered-prefix proofs.

## Finding: evaluation introduces an untrained system-level format directive

This is a concrete evaluation-protocol mismatch, with a potentially conflicting marking instruction. It is not
proof that the new system message caused every failure or that the adapter has retained marking competence.

- `stem_training.py:86–94` permits exactly user/assistant messages. `encode_final_example` renders those exact
  messages at line111, with no added system message.
- `stem_training_data.py:276–282` constructs main-corpus marking prompts beginning **Return only JSON** with the
  explicit `points`/`feedback` envelope. These marking prompts do **not** contain the document-format prefix.
- `stem_training_eval.py:430–432` prepends a new system message, **STEM Tutor. Reply in document JSON.**, before
  every evaluation user turn, including marking tasks. `EvaluationConfig.validate` fixes that identity at lines220–224.
- The actual app distinguishes the contracts. `local_chat.py:18–22` adds document instructions for chat, whereas
  `local_ai.py:675–698` sends the generic tutor system and the task-specific schema for one-shot grading. The
  evaluator's blanket document directive does not reproduce the production marking path.

The dataset counts correct an earlier assumption that every training user turn carries the same prefix:

| Split | Document rows with document prefix | Marking rows without document prefix |
| --- | ---: | ---: |
| Training | 689 | 16 |
| Development | 243 | 12 |
| Test | 270 | 8 |

The separately frozen format challenge differs: all18 user prompts carry the prefix, including its three marking
rows, followed by an explicit marking request in the same user message. Preserve that corpus unchanged and disclose
this additional ambiguity when it is eventually assessed.

“Document JSON” is a learned project term; the system text does not itself enumerate the block schema. A model
might interpret it generically and follow the user marking request. Therefore this is not a formal impossibility
proof or an observed instruction-priority guarantee for Qwen. The definite defect is that the alleged training-style
unassisted benchmark adds a format directive and message role absent from training, including on the alternate
marking contract. The resulting marking score is confounded.

## Exact CPU reproduction

Using the pinned Qwen tokenizer and native Fast template, render each development row in two ways:

1. Render its complete training user/assistant pair; take the prefix immediately before the assistant gold.
2. Render only the original user message with `add_generation_prompt=True, enable_thinking=False`.

**All255/255 development prefixes match byte-for-byte.** Rendering the current evaluator's additional system message
instead introduces a65-character system block and changes the prompt hash. No gold answer is added to generation
inputs by condition2; gold is used only to locate the training boundary in this CPU comparison.

For marking row `1647bbfdf666831dbaedd5ec`:

- Training prefix and user-only generation: `e6733e7c2487b965f55e1fbda3e25e3f92b686452995a33e725cd4db422e1ca6`.
- Current system-plus-user generation: `861430fc90dff35d3be192537e8d8873ce65224b07ac6195454f0eeb47aac757`.
- Prefix sizes:485 versus550 characters. The roles change from the training prefix's user/assistant opening to
  system/user/assistant opening.

This equivalence is for Fast's closed empty thinking prefix. Deep intentionally opens native thinking and must be
verified separately; no Deep-generation result follows from this proof.

## What v1 does and does not establish

Keep both completed v1 runs and their source fingerprint immutable. They are valid observations under the extra
system-directive condition. Chat format failures under that condition are real robustness failures and must not be
relabelled as passes. The reported adapter raw67/120 and host68/120 do not meet the98% compact-format gate.

The reported main marking failures cannot yet establish a clean semantic regression: the task's requested envelope
competes with the added document directive. `score_trial` defaults `marking_labels_equal=False` when the envelope is
invalid, before a usable decision vector exists. Report **wrong/unavailable envelope** separately from **incorrect
criterion decisions in a valid envelope**. The latter requires actual decoded point identities and met flags.
Neither valid JSON nor an unavailable vector proves teaching truth or falsehood.

No further training is justified by these v1 counts alone. First correct the diagnostic method on development data.

## Minimal next experiment: frozen development protocol contrast

Use the accepted100-update adapter unchanged. Freeze18 existing development rows using metadata only:
all12 marking rows, plus one `published_flashcard` and one `literal_json` row per subject, ranked by
`SHA256("protocol-dev-v1:" + id)` within each bucket. This selection has three marking families: four maths
square-domain variants and eight physics vector/dynamics variants; **there are no chemistry marking rows in the
current development split**. Do not invent balanced chemistry coverage or independent sample counts.

Run each of the18 inputs once under each fixed condition, for54 total requests:

| Condition | Messages before native generation prefix | Purpose |
| --- | --- | --- |
| A — current v1 | System: `STEM Tutor. Reply in document JSON.`; original user | Retained conflicting/ambiguous robustness condition |
| B — training protocol | Original user only | Exact Fast training-prefix match established above |
| C — neutral system | System: `STEM Tutor. Follow the JSON contract requested by the current task.`; original user | Separate a task-neutral system role from the document-specific directive |

Keep seed42, Fast sampling,4096 total generated-token cap,180-second request deadline,14 GiB observed budget,
resource guards, thought-token discard, weights, tokenizer and task contents identical. Preserve every attempt,
message-role/content hash, finish reason, time, raw final answer and error. No grammar, example, repair prompt,
training update or automatic retry is added. Do not execute generated code.

Score each schema separately: strict document/envelope validity; exact copied criterion identities; decision-vector
availability; conditional vector correctness; and exact literal-source fidelity. Scientific explanation and OPEN
protection remain independent manual checks. A complete-contract success metric can count envelope failures, but
must not call them observed wrong scientific decisions.

If B improves on A, that supports a protocol effect on this development sample. If C behaves like B, the specific
system format directive is a plausible contributor; it does not isolate every role/content interaction. If B remains
poor, genuine learned-format or task-retention limitations remain. Do not presume any outcome in advance.

After choosing the intended interface from this development experiment, freeze a new versioned harness and pairing
policy before another full comparison. Keep v1 visible. Use the training-matched protocol as the unassisted reference;
measure the actual full-schema app path separately. Any later model or prompt tuning needs untouched confirmation
evidence, rather than turning the already examined v1 test results into a new claim of sealed performance.

## Required CPU guards before the next GPU run

Add a pure message-construction function and regressions for all three explicit protocol names. Assert that B adds
neither a system directive nor gold, A remains byte-identical to v1, C uses its exact frozen neutral sentence, and
run identity/pair validation includes protocol, role/content hashes and code fingerprints. Reject unknown protocols.
The parent owns implementation and GPU scheduling; this review changed only the report and CPU proof artifact.
