# Required local readiness

The learner requests that every local generation is preloaded and that waits remain as small as practical. Add an
adapter-level readiness barrier before every local generation attempt, including helper vision and context recovery.
Use an empty Ollama chat request with exactly the generation's model/load options and require a successful load
acknowledgment. Share the existing inference lock and deadline; do not nest the public warm lock. Failure,
cancellation, reset, drive removal or budget exhaustion must prevent sending the prompt.

An unconditional empty preflight is selected over a running-model snapshot or timestamp cache: it asks the scheduler
to finish loading and health-check the runner. Reusing an already loaded runner costs a small local round trip.
Keep background preparation to hide real cold loads, and prepare Mark while the learner reads a written question.
Do not reload for a cached successful answer. Keep only the next selected model prepared, rather than trying to fit
three large models simultaneously. Do not change model selections, quality controls, cloud paths or shared services.

Report request-time preload duration separately from generation engine load metrics. Status remains terminal-only.
The enforceable guarantee is that the tutor sends no generating request before successful matching preload. Ollama
has no atomic residency lease between two requests; another client, daemon restart or explicit unload can interfere.
Do not claim zero startup time or that prompt processing and reasoning disappear.

This supersedes the earlier latency spec's exclusion of extra preflights for ordinary text requests. Validate all
installed model IDs, streaming, JSON, helpers, retries, failure/reset/deadline paths, caches, and unchanged cloud routing.
