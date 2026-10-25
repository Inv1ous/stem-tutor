# Responsive tutoring and ChatGPT support

The learner reports an empty Gemma 4 response in Ask/chat with Think first enabled. A synthetic reproduction
exhausted a 4,096-token context: 3,082 prompt tokens and 1,014 generated tokens, with reasoning but no answer.
Preserve thinking and model quality; reserve answer headroom and recover boundedly from this specific failure.

Keep existing terminal card styles. Local requests immediately show an animated status and elapsed time, distinguish
waiting and thinking from visible generation, and never display hidden reasoning or mirror transient status into
Obsidian or speech. Cancellation must remove progress and preserve answer guards.

Add the account's Codex-accessible ChatGPT models to existing per-task selectors, using the learner's existing
ChatGPT sign-in. Isolate the subprocess from project files, agent rules, tools, credentials for API billing, and
Claude conversations and counters. Low/high reasoning maps to the current Think first switch and is explained in
Settings. Missing CLI, authentication and limit failures must be actionable without provider fallback.

Reduce unnecessary local work through bounded in-memory reuse of identical successful structured requests.
Preserve full cache keys, reset boundaries and cancellation. Do not cache streaming conversations, failures or
partial outputs. Preserve weights, precision, sampling, thinking choice and uncapped normal answers.

Allow optional, targeted local-model web lookup through the installed Ollama service's signed-in search endpoint.
Use only the student's explicit question as the search query; never send their lesson context, answers or profile.
Use short bounded source excerpts, citations and a short search cache. Stable syllabus questions remain offline.
If search is unavailable, say so and do not fabricate current facts. Web retrieval is a source feature, not a claim
of faster tokens per second. Claude requests do not use these local mechanisms.
