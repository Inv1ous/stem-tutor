# Fast STEM models and presets

Install and evaluate small local models for this tutor on the learner's M4 MacBook Air with 24 GB unified RAM.
All model weights and Ollama manifests must live under `/Volumes/External SSD TB4/LocalAI`. Keep the original models.
The preferred goal is a complete tutoring answer within 40 seconds and complete marking JSON within 15 seconds; the learner explicitly says these are soft targets.
Report warm and cold performance separately, including image preparation and model switches. Never substitute
first-token latency for completed-response latency or truncate replies to pass the target.

Evaluate Qwen 3.5 2B/4B, Gemma 4 E2B/E4B, Ministral 3 3B, Phi-4-mini 3.8B and GPT-OSS 20B against synthetic A-Level mathematics,
physics and chemistry questions and mark schemes. Also evaluate Granite 3.2 Vision as an image observer.
The expanded family pass evaluates DeepSeek R1 8B/14B, Llama 3.1 8B, Liquid LFM2.5 8B and a community MiMo V2.6 9B
package where runtime compatibility is demonstrated. Research Kimi, but do not install a package whose claimed
vision support cannot be verified. Prefer smaller distills to a marginal 32B allocation on this 24 GiB Mac.
Choose recommendations using correctness and latency together.
Publisher benchmarks establish candidate suitability, not this Mac's speed or educational accuracy.

Prefer native image support. Text-only models use literal Apple Vision text OCR after every tested small generative
image helper failed the diagram-geometry audit. OCR is context-independent, discloses incomplete recognition and
does not interpret geometry or solve the question. An explicitly configured generative helper remains experimental.
The final tutor retains its original context and answer guard. Cache exact image bytes in
memory; do not silently discard images, fabricate missing values, or fall back to a cloud provider. Prefetch these
observations while the learner reads when safe and useful, without changing the question or stored progress.

Add two Claude-only, two ChatGPT-only and two to five local-only presets to existing Settings. Use a compact selector,
preview and explicit Apply button; Save remains the only persistence action. Manual edits show Custom. A local
preset is offered only while every required model is available on the SSD. Applying a preset changes exactly the
three task model selections and three thinking switches. Existing individual choices, cloud behavior and unrelated
settings remain available. Low-latency presets use direct answers/low reasoning, selected explicitly by the learner.

Latency is a measured goal for representative study workloads, not an unconditional guarantee for arbitrarily
long requests, cold loads, web delays or reasoning-heavy requests. Do not auto-apply a preset or overwrite the
learner's current preferences. Preserve earlier staged work and unrelated learner data; no commit or push requested.
