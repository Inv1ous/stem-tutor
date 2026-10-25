# Fast STEM Models and Presets Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development or superpowers:executing-plans. Prove regressions before implementation and keep file ownership separate.

**Goal:** Install and benchmark suitable small local STEM models, add safe image compatibility and task presets.

**Architecture:** Extend the existing manifest-backed model catalogue. Native vision uses the current path; text-only models use bounded cached literal Mac OCR without inferred geometry. Settings derives preset identity from model choices rather than maintaining a second source of truth. Claude and Codex keep their established routes.

**Tech Stack:** Python, asyncio, stdlib HTTP, installed Ollama, Textual/Rich and pytest.

**Spec:** docs/superpowers/specs/2026-10-25-fast-stem-presets.md

## Global constraints

- Store all downloads in `/Volumes/External SSD TB4/LocalAI`; keep existing models and learner data.
- No new dependency, cloud fallback, silent image loss, artificial response cap, or fabricated benchmark claim.
- Measure complete responses against 40-second tutoring and 15-second marking goals; include cold and warm costs.
- Preset Apply changes the open dialog only; Save applies settings. Default choices stay unchanged.

## Review focus

- Drive removal or partial model downloads must not make a preset appear runnable.
- Image extraction must preserve uncertainty, answer guards and reset/cancellation boundaries.
- Cache keys include exact image bytes and helper identity; failed and stale extractions are never reused.
- Model swaps, queue waits and optional web work count towards observed response latency.
- Manual/cloud settings retain their prior behavior when presets or image preparation are unused.

## Tasks

- [x] Research current primary model sources; confirm external model path and space; download eight initial candidates; record manifests, sizes and runners.
- [x] Write failing catalogue/capability tests; add new IDs, per-model residency/context and validated helper preference without changing existing defaults.
- [x] Write failing image observer and transport tests; implement exact-byte cached extraction, native bypass and visible failure; integrate safe prefetch and reset behavior.
- [x] Write failing preset selection/Apply/Save/hotplug tests; implement two Claude, two GPT and four benchmark-informed local presets in existing Settings.
- [x] Benchmark initial full synthetic tutoring, marking and image workloads sequentially; select recommendations and save raw evidence and limitations.
- [x] Expand the family pass to smaller DeepSeek distills, Llama, Liquid and compatible MiMo; verify reasoning semantics before exposing new choices. Document Kimi and 32B exclusions. Five further packages installed, 30 complete generation checks; experimental models stay outside presets.
- [x] Review standards and specification independently; run the full project suite and inspect narrow/large Settings and progress screens. Full gates: 3,348 then 3,360 passed; final model metadata also receives focused regressions.
- [x] Update README, changelog and learner guide; stage only task files and report installations, measured recommendations and limitations.
