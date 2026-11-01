# STEM Tutor

Version **2.6.1** — see [release notes](docs/releases/v2.6.1.md) and `CHANGELOG.md`;
the evidence behind each feature is in `docs/RESEARCH.md`.

This release brings the Library/Work storage migration, shared validated AI replies, local-model improvements,
and the latest marking, recovery, screen and worker-cleanup fixes together. Extraction candidates remain unpublished;
inspection, independent review and teaching approval are separate. See the release notes for verification limits and
[the v2.6.1 push commands](docs/PUSH_V2_6_1.md) for the source-only staging list.

A-Level study system (CAIE 9701/9702, Edexcel IAL Maths/Further Maths): a terminal app for studying, an Obsidian
vault for reading, and a pure-Python engine that does the teaching logic without AI.

**Learner guide:** `STEM Tutor/How It Works.md` (in the vault; source in `build/out/notes/`).

## Layout
| Path | What |
|---|---|
| `app/tutor_app/` | Textual terminal app (screens, answer panels, cards), AI client (`ai.py`: persistent lean `claude -p` on the subscription), prompts, LaTeX→Unicode (`texmath.py`), the Night/Day/Classic looks (`look.py`), the Terminal window setup (`setup_look.py`, `termprofile.py`, JuliaMono from the shared Library) |
| `src/tutorlib/` | canonical engine: sessions, lesson mode (`lesson.py`), Obsidian views (`views.py`), grading, FSRS/Elo model, experiments, reports, weekly bookkeeping |
| `plugin/stem-tutor/` | the older Cowork plugin (still works; the terminal app is now primary) |
| `build/` | content pipeline: specs → graphs → packs (drafted, blind-solved, adjudicated), teach cards, publish to the vault |
| `foundry/` | content foundry: chapters built by headless Claude and Codex workers, split between the two allowances as they run down (`foundry/README.md`) |
| `refine/` | refine system: improves chapters already built, adding only (diagrams, questions, clarifications), on both allowances (`bin/refine`, the `/refine` skill) |
| `../STEM Tutor/Library/` | authoritative source PDFs/TQ files, questions, diagrams, notes, fonts and reusable test inputs; organized by course/type |
| `bugwatch/` | live two-agent bug hunt (Codex spots, Claude fixes; `bugwatch/README.md`) |
| `docs/` | `SHORTCUTS_COURSE.md` (the Shortcuts & Elegant Methods course: data, lessons, its own recall queue), `RESEARCH.md` |
| `bin/` | `tutor` (launcher: `tutor`, `tutor doctor`, `tutor look`, `tutor tts setup`), `foundry`, `refine`, `shortcuts` (parse, generate lessons, publish) |
| `bin/tutor` | launcher (`tutor`, `tutor doctor`, `tutor look`, `tutor --setup`) |
| `tests/` | pytest (engine) and `tests/app/` (AI client with a fake `claude`, Textual pilot tests) |

## Workspace storage

The authoritative learning library is now `../STEM Tutor/Library/`. Courses contain `Sources/`, `Questions/`, `Diagrams/`, and `Notes/`; shared resources and review media live under `Shared/`. The catalog preserves hashes, provenance, stable references, and legacy aliases. Availability in the library is not evidence of course-content acceptance.

`build/workspace_audit.py` inventories storage and references. `build/migrate_library.py` performs an expand-only, hash-verified copy. `build/migrate_library_links.py` repairs recognized Markdown links with exact-original journals. Reports are under `../Work/storage-migration/`; preserved originals are under `../Archive/`. The migration ledger is `docs/superpowers/plans/2026-10-30-workspace-storage-overhaul.md`. Legacy directories are compatibility adapters; originals and exact rollback records remain in Archive.

Generated work lives under `../Work/Preparation/`, candidate builds under `../Work/Candidates/`, and worker state/logs under `../Work/Workers/`. Historical `build/work`, `build/out`, and worker paths remain symlink adapters. Generated audio lives in the device cache selected by the vault storage metadata.

Tests share reusable learning inputs through `tests/library_assets.py`. Real-resource fixtures stage copies in a disposable Library; malformed-input scenarios and outputs stay disposable. Tests must not write learner state or production Library assets.

## Local AI

Settings (F2) offers the original **Qwen 3.5 9B**, **Gemma 4 26B**, and **Qwen 3.8 27B**, plus installed small candidates
including **Gemma E4B**, **GPT-OSS 20B**, smaller **DeepSeek R1** distills, **Llama 3.1 8B**, **Liquid LFM2.5 8B** and
a community **MiMo V2.6 9B**,
when their model packages are present in
`/Volumes/External SSD TB4/LocalAI`. The model lists refresh while Settings is open, including after plugging in the SSD.
Choose models separately for marking, explaining, and asking. Local inference runs on this Mac and does not use the
Claude allowance. A disconnected local selection stays saved until you explicitly choose another model.

Nine task presets offer two Claude, two ChatGPT and five local setups. Select a preset, inspect its preview, press
**Apply**, then **Save**. Presets change only the three task models and thinking choices. Start with **Local: careful
marking** to avoid model switches, or **Local: fast tutoring** for Gemma E4B explanations with Gemma 26B marking.
Measured comparisons and limitations are in [Local STEM models and presets](docs/LOCAL_STEM_MODELS.md).
Gemma 26B, E4B, Qwen 3.8 27B and GPT-OSS have verified MLX choices. Local presets use these native choices;
original GGUF Gemma/GPT choices remain available. GPT-OSS uses an isolated SSD worker, with no LM Studio dependency.
GPT-OSS offers Low/Medium/High, Qwen offers Off/Low/Medium/Maximum, and Gemma retains Off/On.
See [MLX comparisons](docs/LOCAL_MLX_COMPARISON.md) for response times and factual-accuracy limitations.
Existing saved choices stay authoritative: reapply a preset to adopt its MLX selections.
Settings uses a wider panel when space allows. Preset details appear while previewing; expand **Model guide** for
provider and thinking information. Applied model choices remain visible in their individual task rows.
Text-only models receive cached on-device image text OCR; this cannot interpret graph geometry. Native vision models
keep the original image. OCR preparation, queue waits and model loading count towards terminal performance timing.

Ollama-backed choices use the installed runtime. If no service is running, the tutor starts one on `127.0.0.1:11434` with
the SSD model directory and at most one model loaded. The Ollama app window does not need to remain open. The tutor
stops only a service it started; an existing service remains under your control.
GPT-OSS MLX uses its own private worker and can run while Ollama is closed.
Local replies show generation speed, first-token time, total time, model load time, and output tokens in the terminal;
these measurements are excluded from Obsidian and read aloud.

The next task's local model preloads while you read or type, including the session's Ask composer. Sending keeps that
preparation for the answer; cancelling stops it. Native text OCR and explicit web retrieval can overlap model loading.
Generative image helpers stay sequential. Requests run one at a time to avoid competing for unified
memory. Qwen 9B stays warm for 30 minutes, Gemma 26B for 15, and Qwen 27B for 10; small candidates stay warm for 45.
Every local generation attempt also requires a successful matching empty preload acknowledgment under that same
queue and deadline. This covers chat, marking, image helpers and larger-context retries. A failed preload stops the
request before its prompt is sent. Written questions prepare Mark while you read, and cached answers need no runner.
Switching models still requires loading
the new model. Progress shows preparation, waiting, thinking, generation and elapsed time without displaying hidden
reasoning. Identical successful structured requests can reuse their result for ten minutes within the same session.
The terminal reports request-time preload duration separately from generation engine load time. Preloading moves
loading earlier; it does not eliminate loading, prompt evaluation or thinking. Another client or a restarted Ollama
service can still interrupt residency between separate API calls.
Gemma reserves an 8,192-token context, with one 16,384-token recovery attempt if reasoning exhausts the window before
any answer. Weights, precision, sampling and your thinking choice remain unchanged. Hardware measurements are in
[Local AI performance](docs/LOCAL_AI_PERFORMANCE.md); the empty-reply diagnosis and current checks are in
[Responsive tutoring](docs/RESPONSIVE_TUTORING.md). See [response latency research](docs/LOCAL_AI_LATENCY_RESEARCH.md)
for preload measurements, existing prefix caches, engine alternatives, and their limitations.
Local Ask treats lesson context as background when you change topic and decodes its reply/speech transport before
display. Qwen 27B's Maximum and legacy Think first use `xhigh` effort and can take minutes. Preloading does not remove prompt
processing or hidden reasoning. Timings and the remaining factual-accuracy limitations are documented in
[Local chat reliability](docs/LOCAL_CHAT_RELIABILITY.md).

The **Local AI: web sources when needed** setting allows targeted search for explicit web requests and questions
about fresh information. Only your typed question is sent to Ollama's search service; lesson context, grades and
profile evidence are excluded. Source excerpts are limited and cached for five minutes, and replies link to the
sources. Stable syllabus explanations and marking stay offline. Search needs internet access and a signed-in Ollama
service; if unavailable, the tutor asks the model to state that it could not verify current facts. An existing
`OLLAMA_NO_CLOUD=1` setting is respected. Disable the setting for fully offline tutoring.

## ChatGPT models

The per-task model selectors also offer the seven GPT models advertised by this account's installed Codex catalogue.
They use the existing **ChatGPT subscription sign-in**, with separate ChatGPT/Codex limits and no API-key fallback.
Install Codex and run `codex login` if needed. The tutor isolates each request from project files, tools and Codex
session history, and keeps its own conversation history. It does not send speculative cloud requests for preloading.
For these models, **Think first** selects high reasoning; switching it off selects low reasoning. Codex CLI returns
completed message blocks, so these replies do not promise token-by-token streaming. Claude retains its original
inference path, defaults, conversations, speech and usage tracking.

Settings also lets the resource indicator show weekly Claude usage, system RAM, or both. RAM includes memory held by
the separate local runtime; inactive and speculative macOS pages count as available. Challenge question creation
keeps its own explicit Sonnet/Opus selector; challenge explanations and re-marking use the per-task Settings choices.

## Reading AI replies

Local, Claude and ChatGPT chat replies use shared content blocks. The app supplies paragraph gaps, headings, bullets,
step numbers, equation wrappers and literal code fences. Only complete validated blocks enter the visible stream;
an invalid or incomplete document is reported as failed. The shared brief requires qualified definitions, causal
explanations, and justified calculation steps with units. Broad questions can receive enough detail
to cover their scope; hints stay short. The terminal renders mathematical variables in italic, keeps units
and function names upright, and uses complete Unicode subscript/superscript groups in the bundled JuliaMono font.
Obsidian retains LaTeX for its richer equations. Code, links, percentages, currency, learner answers, grading data
and separate speech remain protected.

Incomplete maths is held while a reply streams. Malformed or unsupported terminal expressions use a clearly labelled
source fallback instead of silently losing symbols or grouping. Formatting requires no extra AI request. Existing AI
teaching-card and profile caches are formatted when read, without rewriting their files. This standard improves
consistency; it does not promise identical model wording or arbitrary terminal typesetting. The complete renderer
inventory, examples and research sources are in [STEM output formatting](docs/STEM_OUTPUT_FORMATTING.md).

Ask can include a small set of relevant published study references with source identifiers. These are study material,
not an official mark scheme. References are omitted while a practice question is open to protect its answer.
Local chat history is bounded by complete conversation turns; the current question and assessment evidence take
priority. Format validation does not establish factual correctness or complete coverage of the syllabus.

An [experimental STEM fine-tuning pilot](docs/STEM_TUTOR_MODEL.md) produced and tested a separate 4B MLX model
on the SSD, including native Fast/Deep controls. Content-fidelity and Deep-delivery gates failed, so it remains
outside the tutor's model selectors and presets. The original models and saved provider choices are preserved.

## Run
- `bin/tutor` — start (the vault also has a double-clickable `Start Tutor.command`)
- `bin/tutor doctor` — check vault, Obsidian registration, Claude sign-in, dependencies, the look's font and Terminal profiles
- `bin/tutor look` — set up macOS Terminal for the Night and Day looks, once (backs up Terminal's settings first;
  `bin/tutor look --undo` goes back; the look is chosen in Settings, F2)
- `PYTHONPATH=tests/app .venv/bin/python -m pytest tests --import-mode=importlib -q` — tests (avoids duplicate test filenames)
- `.venv/bin/python build/publish.py` — publish packs, notes and the engine into the vault (`../STEM Tutor`)
- `.venv/bin/python build/plan.py && .venv/bin/python build/publish.py` — refresh the Almanac plan after
  `A-Levels.html` changes (the app says "Your Almanac has changed")

AI calls use `claude -p --safe-mode --disable-slash-commands --strict-mcp-config --setting-sources "" --tools ""
--system-prompt … --model haiku` so each request carries only the tutor brief and a small context packet.
