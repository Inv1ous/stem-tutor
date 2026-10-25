# Responsive tutoring: diagnosis and operating notes

## Empty Gemma answer

On 2026-10-25 the learner reported an empty Ask/chat response with Gemma 4 26B and Think first enabled.
A synthetic reproduction with the tutor's system prompt produced 3,082 prompt tokens and 1,014 generated tokens.
Their sum was exactly the active 4,096-token context. Ollama returned hidden reasoning, zero answer characters,
and `done_reason: length`. The tutor correctly rejected the missing answer, but did not distinguish context exhaustion.

Gemma now starts and preloads with an 8,192-token context. The same synthetic input returned a final answer with
Think first still enabled. If reasoning alone exhausts this window, one retry uses 16,384 tokens with the same
messages and thinking choice. That larger window is retained for the client to avoid repeated reloads. A second
exhaustion gives an actionable error; partial answers and hidden reasoning never become successful history.
Retry performance includes both attempts. No weights, precision, sampling settings or production output limits changed.

Ollama documents the separate answer and reasoning fields in its [thinking API](https://docs.ollama.com/capabilities/thinking).
The change increases available answer space. It does not impose a shorter reasoning budget or promise identical
outputs between stochastic generations.

## Waiting and speed

All three local models now show a spinner, actual backend stage and elapsed time before visible answer text arrives.
The text streams as available. Structured marking, teaching cards, profile summaries, challenge help and answer-only
view also show transient activity. Hidden reasoning is never displayed. Progress and performance do not enter Obsidian,
read aloud or answer text. Cancellation removes the transient status and preserves existing answer guards.

The existing next-task preloading, per-model residency and single inference queue remain. A small in-memory cache
adds exact reuse for successful structured replies, with a ten-minute lifetime and at most 32 entries. The key includes
the prompt, system instructions, schema, model, thinking and speech. Queued duplicates reuse completed work. Failures,
partial replies, streaming conversations and results crossing resets are excluded. No cache is written to disk.

One real Gemma arithmetic/schema request took 1.318405 seconds. Its identical repeated request returned the same
correct data in 0.000108 seconds from this cache. This demonstrates avoided generation, not increased model decode speed.

Sequential synthetic chat checks on the M4 MacBook Air, 24 GB RAM, returned answers with all three installed models:

| Model | Total | Load | Generation speed | Mode |
|---|---:|---:|---:|---|
| Qwen 3.8 27B | 5.70 s | 0.015 s | 4.87 tokens/s | Thinking off, warm |
| Qwen 3.5 9B | 12.27 s | 9.78 s | 19.79 tokens/s | Thinking off, cold |
| Gemma 4 26B | 52.53 s | 50.72 s | 20.81 tokens/s | Thinking off, cold |

These are single smoke checks, not a matched speed comparison. Model switching and cold loading can dominate wait time.
The Gemma reasoning regression passed with thinking on after the context fix. Qwen 9B also answered with thinking on,
but took 231.83 seconds, with 228.86 seconds before the first visible answer. A separate Qwen 27B thinking-on arithmetic
check returned the correct answer in 41.308 seconds, including 24.228 seconds loading and 12.648 seconds processing
the prompt. Its 44 generated tokens included reasoning; these different prompts do not establish a speed ranking.
Offline protocol tests exercise reasoning, progress and cancellation for every model. Keeping one model selected reduces reloads. Think first remains your choice;
turning it off can help routine questions but changes the reasoning budget.

## Ollama window and web sources

The Ollama window need not remain open. If no service answers on loopback, the tutor can start `ollama serve` with the
SSD model directory. It stops only its own child process. Existing Ollama services are not stopped or reconfigured.
The installed Ollama CLI and the SSD must remain available. Closing a window is different from quitting a shared
Ollama service while a request is active; an interrupted request reports an error and can be retried.

Optional local web lookup is selected by a fast deterministic check of the student's separate typed question.
Explicit phrases such as “search the web”, “look up” or “latest” trigger a lookup. Normal syllabus explanation and
marking do not. There is no extra model call to classify whether search is needed. Search uses the installed service's
`/api/experimental/web_search` route, which signs requests with that service's Ollama account. A real lookup through
the final client path returned three sources without an API key. This route is verified against the installed Ollama
0.40.11 and [Ollama's source](https://github.com/ollama/ollama/blob/main/server/routes.go).

Search sends only the explicit question, never the generated lesson packet, grades, answers or profile findings.
At most three results supply bounded excerpts. They are labelled untrusted and include real URLs. Results are cached
for five minutes, at most 32 queries; search has a six-second deadline. If internet access, sign-in or search is
unavailable, the model is instructed to say current facts could not be verified. An explicit `OLLAMA_NO_CLOUD=1` is
respected. The local model still performs inference locally; source retrieval contacts Ollama's hosted search service.
Disable Local AI web sources in Settings for offline work. Web retrieval improves access to current evidence; it
usually adds time and does not increase tokens per second. The [official search documentation](https://docs.ollama.com/capabilities/web-search)
describes the hosted service and source result format.

## ChatGPT subscription

The seven GPT IDs shown in Settings come from this account's installed Codex catalogue on 2026-10-25. Availability
still depends on the account and service. These are Codex-accessible subscription models, not a claim about the
ChatGPT website's picker. Requests require the installed CLI and saved ChatGPT sign-in (`codex login`). API-key
credentials and custom API endpoints are removed from the child environment, and ChatGPT authentication is forced.
No API-billing fallback or automatic switch to Claude occurs.

Each request runs in a private temporary folder, read-only and ephemeral, with project rules, user configuration,
commands, connectors, hooks, delegation and browsing disabled. The tutor supplies its own instructions, images and
private conversation history. It preserves structured schemas and optional fields, speech parsing and cancellation.
Thinking maps to low/high reasoning because this catalogue does not advertise an off setting. No cloud generation
runs ahead of a request. CLI JSON events deliver completed message blocks, rather than promising per-token output.
Usage stays separate from Claude's counters.

The implementation follows the official [non-interactive protocol](https://learn.chatgpt.com/docs/non-interactive-mode),
[authentication guidance](https://learn.chatgpt.com/docs/auth), and [CLI configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference).
Eighteen offline protocol tests exercise the documented events and failures. One bounded live check with GPT-6-Luna
returned the correct structured result for `3 + 4` through the saved ChatGPT sign-in in 4.955 seconds. The returned
usage was 9,615 input tokens and 15 output tokens. No API-key credentials were supplied. Other listed GPT models were
checked against the account's catalogue and offline protocol; a live request was not made to each one.
