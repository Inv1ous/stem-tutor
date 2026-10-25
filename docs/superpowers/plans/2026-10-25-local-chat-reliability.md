# Local Chat Reliability Repair

**Goal:** Answer an explicit change of A-Level topic, prevent chat transport syntax reaching the display, and distinguish
reasoning latency from missing model support. Preserve cloud routes, thinking choices, sampling, weights and preload gates.

## Diagnosis

- Persisted review context contained recent ionic-radius questions, no OPEN questions, and actual context-mismatch refusals.
  The local model obeyed the shared exclusive-grounding instruction even after the student explicitly changed subject.
- Local chat had no response schema. A generated `reply` object was sent directly through speech/maths formatting and stored
  in history. JSON escapes could then be interpreted as bare maths commands. Structured marking requests did not leak schemas.
- Ollama 0.40.11 maps Qwen 3.8 `think:true` to `xhigh`. Gemma 26B has fewer active parameters than dense Qwen 27B.
  Preloading cannot remove reasoning computation. Native MLX context handling differs from the GGUF Gemma window.

## Bounded repair

- [x] Reproduce prompt/context and wrapper mechanisms before editing; capture six baseline local requests with the user's question.
- [x] Add `local_chat.chat_system`: modify only local conversational grounding and output instructions; preserve shared/cloud briefs.
- [x] Add an explicit local chat `reply`/optional `speech` transport schema and an incremental strict decoder. Literal requested
  JSON/code stays inside `reply`; do not guess whether arbitrary JSON is an accidental wrapper.
- [x] Integrate decoded text before display, speech and history, preserving request cancellation and required preload acknowledgments.
- [x] Measure the observed reasoning phase separately and give an actionable thinking-timeout message. Keep the existing 300-second
  chat deadline and never silently switch off or lower thinking.
- [x] Migrate legacy fake chat events to the explicit wire envelope; retain an unadapted strict-wire server mode.
- [x] Verify the same organic-chemistry question on E4B, Gemma26B and Qwen27B, thinking on/off, with a bounded diagnostic deadline.
- [x] Independent reviews, targeted/cloud/preload tests and full suite; document limitations and safe v2.6.0 push commands.

## Constraints and ownership

The existing dirty checkout contains earlier authorised formatting, Settings and preload work. Preserve all learner data and unrelated
changes. No downloads, model re-quantisation, sampling changes, reasoning caps, cloud model requests, commits or pushes are planned.
Diagnostics store timing/counters and visible answers only, never hidden reasoning text. Test one local inference at a time; stop only
the service this diagnostic owns.

## Evidence

- Root strict-wire gate: ten expected failures before integration; ten pass after the transport/prompt fix.
- Decoder: 68 split/escape/Unicode/malformed-envelope cases; 400 deterministic chunk/escape probes passed.
- Prompt and cloud argument gate: 36 passed. No changes to shared SYSTEM, prompts.context or structured marking instructions.
- Baseline live captures: `/tmp/stem-local-chat-baseline.json`; final evidence is copied into the benchmark directory after validation.
- Existing `v2.6.0` is an annotated tag: object `178983c49916d75c22b282444795d4b2a5a0a47f`,
  commit `f18f7811ba340ef71f644ff08376827e8d509f62`, verified against GitHub. Preserve it unless explicitly asked to retarget it.

## Completion evidence

- Final complete suite: **3,778 passed**, 28 pre-existing warnings, in 139.89 seconds.
- Final targeted formatter/math/chat transport gate: **231 passed**. Legacy local runtime/preload/UI fixture gate: **351 passed**.
- Independent protocol and specification reviews found no unresolved P1/P2 issues. Review-driven math escape fixes
  include Markdown CR/LF source mapping, formfeed preceding literal code and shared known-command classification.
- Live evidence contains 18 sequential case replays plus one short quiet Qwen inference and its preload lifecycle.
  No hidden reasoning text was saved. Six final requests completed, with the focused thinking-question distinction
  documented explicitly; broad chemistry accuracy is not represented as passing.
- Quiet Qwen lifecycle: first preload 24.56s; second preload 0.0013s; short reply 25.99s; preload after reset 0.0015s.
- The final live Gemma26 non-thinking reply contained a chemical error, recorded as a failed content-quality observation.
  This repair fixes context and response handling, not underlying model factual knowledge.
- Shared/cloud briefs, cloud request paths, thinking/sampling/precision choices, local structured marking instructions
  and preload gates remain protected by regression tests.
- Compile and whitespace checks passed. Diagnostic-owned services were stopped; no model files, real learner state,
  Git tags, commits or remote branches were changed by the repair. Push commands are supplied for the user to run.
