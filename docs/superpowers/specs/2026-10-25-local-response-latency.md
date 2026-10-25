# Local response latency

## Intent

Reduce the wait after the learner submits a local AI request. Preserve the selected model, thinking choice,
weights, sampling, context policy, prompts, answer guards, and Claude/ChatGPT behavior. The user authorizes
research and implementation and wants to manage LM Studio models independently.

## Approaches

1. Improve the existing Ollama preparation lifecycle and overlap independent CPU/network preparation with
   loading. This is the selected implementation: it reuses the current runtime and preserves quality controls.
2. Replace the runtime with standalone MLX/llama.cpp or add a separate draft model. Defer: backend support and
   latency gains are model-specific, and extra weights compete for 24 GiB unified memory.
3. Shorten prompts, truncate history, reduce thinking, or quantize more aggressively. Excluded: those can change
   tutoring quality or the learner's selected settings.

## Behavior

- Opening the session Ask composer prepares only the selected local Ask model while the learner types. Sending
  keeps that work available to the ensuing request; cancelling the composer cancels its speculative preparation.
- Native macOS OCR and model loading may overlap. Generative vision helpers remain sequential because they
  compete for the same inference queue and memory.
- A local request needing explicit web retrieval may load its model while retrieval runs. Ordinary text requests
  do not gain an extra warm request. Preparation must not outlive cancellation, reset, or close.
- Preserve one inference at a time. Do not start additional cloud requests, change shared service configuration,
  download weights, replace LM Studio files, or persist private prompts.
- End-to-end structured response timing includes preparation and cache/inference queue waits. Reused results
  must not claim zero wait when another request was still running. Existing terminal-only status remains honest;
  hidden reasoning and performance do not enter Obsidian or speech.

## Validation

Use event-controlled offline tests for overlap, cancellation, provider isolation, composer ownership, queue timing,
and unchanged payloads. Run the complete project suite. Record a bounded synthetic original-three-model preload
probe separately from prior benchmarks, retaining preload time and runner-cold caveats. Research uses primary
sources and distinguishes existing optimizations from new changes and unverified alternatives.
