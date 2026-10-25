# Local chat diagnosis: context, reply encoding and thinking

Investigated on 25 October 2026 with Ollama 0.40.11 on the installed Apple M4 Mac with 24 GiB unified memory.
The question was: “What are the formulaes we need to know for 9701 organic chemistry”.

## Confirmed client problems

The existing tutor brief told every model to ground everything in the supplied context. The active review session
contained recent atomic/ionic-radius questions and no OPEN questions. That background was still included when the
learner changed to organic chemistry. The persisted transcript and live replay both showed models treating the old
topic as a restriction. Resetting inference history did not remove the review session's context packet.

Local conversational calls now clarify that context is relevant background, not the only permitted subject or source
of knowledge. The student's current request sets the topic and requested answer type. OPEN-question protection and
uncertainty wording remain. Shared Claude/ChatGPT briefs, prompt packets and structured marking instructions are unchanged.

Previously, conversational calls had no response schema. A model-generated object such as `{"reply":"..."}` was
displayed as ordinary prose. Its JSON escapes could then reach the mathematical formatter as if they were commands.
There was no evidence that marking schemas leaked into chat: those requests are separate and memoryless.

Local chat now requests an explicit outer JSON transport with a `reply` string and, only when wanted, a `speech`
string. A strict incremental decoder emits the reply before completion, without displaying braces, escape syntax or
speech. Requested literal JSON/code belongs inside that string and remains literal; the program never guesses that
an arbitrary object is an unwanted wrapper. Duplicate/unknown fields, bad types, invalid escapes and incomplete
envelopes fail instead of becoming successful history. The required preload still precedes every attempt.

The decoder preserves literal characters. Separately, the visual formatter repairs known TeX commands accidentally
decoded as JSON backspace/formfeed/carriage-return/tab escapes only inside explicit maths. Code and ordinary
whitespace stay protected. Ambiguous newline escapes are not guessed. Markdown source ranges follow CR/LF rules,
so a formfeed before a code block cannot move the protection boundary.

## Why thinking still takes time

Thinking models generate hidden reasoning before their answer. The tutor does not display or save that reasoning.
It now reports the observed interval from a reasoning event to answer content separately in terminal performance
statistics. This is an observed phase duration, not an exact count of GPU compute seconds; first-event overhead is
excluded. The existing 300-second chat deadline remains. A reasoning timeout now explains the limit and suggests
turning Think first off for routine questions or selecting a faster model. It never silently changes the setting.

For the installed Qwen 3.8 renderer, boolean `true` means **xhigh**. `false`, `low`, `medium` and `xhigh` are distinct
native controls, but the existing tutor switch remains on/off. A tooltip now makes the maximum-effort meaning clear.
Lowering effort could improve latency, but would be a reasoning-behaviour choice rather than a free speed optimisation.
[Ollama's exact renderer](https://github.com/ollama/ollama/blob/v0.40.11/model/renderers/qwen35.go#L114),
[thinking API](https://docs.ollama.com/capabilities/thinking).

The installed packages also differ substantially:

| Selection | Installed package | Relevant consequence |
| --- | --- | --- |
| Gemma E4B | Native MLX, safetensors/NVFP4, embedded assistant draft | Smaller effective model; its total parameters include large embeddings |
| Gemma 26B A4B QAT | GGUF Q4_0, mixture of experts | Its label is total size, not the amount of active work per token |
| Qwen 3.8 27B | Native MLX, safetensors/NVFP4, dense model, embedded MTP | More active weight work and less memory headroom on this Mac |

Existing runtime logs showed successful E4B inference around 9.6 GiB MLX peak allocation and Qwen around 17.7 GiB.
Those numbers exclude other application and OS memory and are not a total-RAM measurement. These packages do run on
the Mac. Loading successfully does not establish short latency for long reasoning or large prompts.
[Google model card](https://huggingface.co/google/gemma-4-E4B-it),
[Qwen architecture card](https://huggingface.co/Qwen/Qwen3.8-27B).

Empty preloading moves weight loading earlier; prompt processing and reasoning still happen afterwards. Changing
Qwen thinking off/on also changes its leading system prefix, so the previous prompt cache may not match even when
weights remain resident. The inspected `LocalAI.reset()` does not unload models. Ollama's MLX reuse logic ignores
runner-option differences such as `num_ctx`; no deterministic reset/thinking/schema reload bug was found.
[Renderer prefix](https://github.com/ollama/ollama/blob/v0.40.11/model/renderers/qwen35.go#L230),
[scheduler reuse](https://github.com/ollama/ollama/blob/v0.40.11/server/sched.go#L1423).

The earlier 4,096-token exhaustion diagnosis was the GGUF Gemma run. It should not be applied automatically to E4B:
the installed MLX path uses native model limits, with `num_ctx` acting as a soft/reporting value. Increasing that
number is not a proven way to reserve a final answer or shorten thinking for MLX.
[MLX client](https://github.com/ollama/ollama/blob/v0.40.11/mlxrunner/client.go#L289),
[preparation](https://github.com/ollama/ollama/blob/v0.40.11/mlxrunner/pipeline.go#L73).

## What the live checks established

The complete visible responses, request scopes, timings, package fingerprints and source hashes are in
[the evidence file](benchmarks/2026-10-25-local-chat-reliability.json). Hidden reasoning text is absent.

- Six baseline requests replayed the same broad question with thinking off/on on the three packages. They reproduced
  the topic restriction. Gemma26 thinking completed in 58.7 seconds; Qwen's broad thinking request exceeded the
  diagnostic 150-second limit after beginning an answer.
- Six candidate requests checked the new context/transport path. Raw wrapper display stopped. Both larger-model
  broad thinking requests exceeded the diagnostic limit; one had begun an answer. This is not proof that the mode
  is unsupported, nor that the production 300-second deadline must also fail.
- Final verification used the broad question for all three non-thinking calls and E4B thinking. Gemma26/Qwen27
  thinking instead used the clearly labelled one-sentence acyclic-alkane question. All six completed. The focused
  thinking checks took about 45.5 and 97.6 seconds respectively, including preparation and prefill, not just reasoning.
- That final phase overlapped CPU test workers. It is not a quiet-machine speed estimate or a comparative ranking.
  Qwen's 97.6 seconds included 37.7 seconds awaiting preload, 26.3 seconds reported prompt processing and 27.4 seconds
  of observed reasoning. Preload wall time alone does not prove an actual reload.
- A separate quiet, single-model lifecycle check had no pytest workers. Initial Qwen preload took 24.56 seconds;
  another preload took 0.0013 seconds. A short non-thinking reply took 25.99 seconds with a 0.0008-second request
  preload. After reset, preloading took 0.0015 seconds. Residency snapshots were recorded. This demonstrates reuse
  and distinguishes warm loading from prompt evaluation; it does not promise those timings for other workloads.

No token cap, precision change, sampling retune or forced thinking-off was used. Each diagnostic had a bounded wall
deadline. Sequential runs did not control thermal state, file caches, prefix caches, memory pressure or stochastic
response length sufficiently to claim a causal speed improvement.

## Content accuracy remains a separate limitation

The generic chemistry question still produced incomplete revision lists in some final replies. One Gemma26
non-thinking reply incorrectly gave a one-oxygen molecular formula for carboxylic acids. For example, ethanoic acid
has two oxygen atoms. That response is not accepted as a verified revision list.
[NIST ethanoic/acetic acid data](https://webbook.nist.gov/cgi/cbook.cgi?ID=C64197).

The focused thinking replies correctly stated the acyclic-alkane formula. That single result is not a syllabus-wide
accuracy evaluation. Neither a valid transport envelope nor more thinking guarantees correct chemistry. Use the
published course notes and mark schemes to verify revision facts; the client repair does not replace model knowledge
with verified syllabus retrieval. No claim is made that every reported issue was a RAM fault or that larger labels
produce better teaching for every question.

## Publishing with the existing version

The application version remains 2.6.0. The existing annotated GitHub tag `v2.6.0` points to the original local-AI
release commit `f18f7811ba340ef71f644ff08376827e8d509f62`. Pushing new commits to `main` updates the repository without
moving that tag. Consequently, the old tag's source archive remains the old release. No force-push, retag or release
rewrite was performed. The learner's generated content/state changes are outside the suggested staging paths.

## Verification

Final complete suite: **3,778 passed**, 28 pre-existing warnings, in 139.89 seconds. The targeted formatter/math/chat
gate passed 231 cases; the existing local fixture/preload/UI gate passed 351. Independent protocol and specification
reviews found no unresolved P1/P2 issues. Compile and whitespace checks passed.
