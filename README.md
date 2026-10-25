# STEM Tutor

Version **2.6.0** — see `CHANGELOG.md`; the evidence behind each feature is in `docs/RESEARCH.md`.

A-Level study system (CAIE 9701/9702, Edexcel IAL Maths/Further Maths): a terminal app for studying, an Obsidian
vault for reading, and a pure-Python engine that does the teaching logic without AI.

**Learner guide:** `STEM Tutor/How It Works.md` (in the vault; source in `build/out/notes/`).

## Layout
| Path | What |
|---|---|
| `app/tutor_app/` | Textual terminal app (screens, answer panels, cards), AI client (`ai.py`: persistent lean `claude -p` on the subscription), prompts, LaTeX→Unicode (`texmath.py`), the Night/Day/Classic looks (`look.py`), the Terminal window setup (`setup_look.py`, `termprofile.py`, bundled JuliaMono in `fonts/`) |
| `plugin/stem-tutor/skills/tutor/scripts/tutorlib/` | engine: sessions, lesson mode (`lesson.py`), Obsidian views (`views.py`), grading, FSRS/Elo model, experiments, reports, weekly bookkeeping |
| `plugin/stem-tutor/` | the older Cowork plugin (still works; the terminal app is now primary) |
| `build/` | content pipeline: specs → graphs → packs (drafted, blind-solved, adjudicated), teach cards, publish to the vault |
| `foundry/` | content foundry: chapters built by headless Claude and Codex workers, split between the two allowances as they run down (`foundry/README.md`) |
| `refine/` | refine system: improves chapters already built, adding only (diagrams, questions, clarifications), on both allowances (`bin/refine`, the `/refine` skill) |
| `sources/` | your PDF library (`sources/library/`, searched by `build/library.py`) and the shortcut notes (`sources/shortcuts/`) the Shortcuts course is made from |
| `bugwatch/` | live two-agent bug hunt (Codex spots, Claude fixes; `bugwatch/README.md`) |
| `docs/` | `SHORTCUTS_COURSE.md` (the Shortcuts & Elegant Methods course: data, lessons, its own recall queue), `RESEARCH.md` |
| `bin/` | `tutor` (launcher: `tutor`, `tutor doctor`, `tutor look`, `tutor tts setup`), `foundry`, `refine`, `shortcuts` (parse, generate lessons, publish) |
| `bin/tutor` | launcher (`tutor`, `tutor doctor`, `tutor look`, `tutor --setup`) |
| `tests/` | pytest (engine) and `tests/app/` (AI client with a fake `claude`, Textual pilot tests) |

## Local AI

Settings (F2) offers the original **Qwen 3.5 9B**, **Gemma 4 26B**, and **Qwen 3.8 27B**, plus installed small candidates
including **Gemma E4B**, **GPT-OSS 20B**, smaller **DeepSeek R1** distills, **Llama 3.1 8B**, **Liquid LFM2.5 8B** and
a community **MiMo V2.6 9B**,
when their Ollama manifests are present in
`/Volumes/External SSD TB4/LocalAI`. The model lists refresh while Settings is open, including after plugging in the SSD.
Choose models separately for marking, explaining, and asking. Local inference runs on this Mac and does not use the
Claude allowance. A disconnected local selection stays saved until you explicitly choose another model.

Eight task presets offer two Claude, two ChatGPT and four local setups. Select a preset, inspect its preview, press
**Apply**, then **Save**. Presets change only the three task models and thinking switches. Start with **Local: careful
marking** to avoid model switches, or **Local: fast tutoring** for Gemma E4B explanations with Gemma 26B marking.
Measured comparisons and limitations are in [Local STEM models and presets](docs/LOCAL_STEM_MODELS.md).
Text-only models receive cached on-device image text OCR; this cannot interpret graph geometry. Native vision models
keep the original image. OCR preparation, queue waits and model loading count towards terminal performance timing.

The tutor uses the installed Ollama runtime. If no local service is running, it starts one on `127.0.0.1:11434` with
the SSD model directory and at most one model loaded. The Ollama app window does not need to remain open. The tutor
stops only a service it started; an existing service remains under your control.
Local replies show generation speed, first-token time, total time, model load time, and output tokens in the terminal;
these measurements are excluded from Obsidian and read aloud.

The next task's local model preloads while you read or type. Requests run one at a time to avoid competing for unified
memory. Qwen 9B stays warm for 30 minutes, Gemma 26B for 15, and Qwen 27B for 10; small candidates stay warm for 45.
Switching models still requires loading
the new model. Progress shows preparation, waiting, thinking, generation and elapsed time without displaying hidden
reasoning. Identical successful structured requests can reuse their result for ten minutes within the same session.
Gemma reserves an 8,192-token context, with one 16,384-token recovery attempt if reasoning exhausts the window before
any answer. Weights, precision, sampling and your thinking choice remain unchanged. Hardware measurements are in
[Local AI performance](docs/LOCAL_AI_PERFORMANCE.md); the empty-reply diagnosis and current checks are in
[Responsive tutoring](docs/RESPONSIVE_TUTORING.md).

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
