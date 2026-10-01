# STEM Tutor

Version **1.2.3** — see `CHANGELOG.md`; the evidence behind each feature is in `docs/RESEARCH.md`.

A-Level study system (CAIE 9701/9702, Edexcel IAL Maths/Further Maths): a terminal app for studying, an Obsidian
vault for reading, and a pure-Python engine that does the teaching logic without AI.

**Learner guide:** `STEM Tutor/How It Works.md` (in the vault; source in `build/out/notes/`).

## Layout
| Path | What |
|---|---|
| `app/tutor_app/` | Textual terminal app (screens, answer panels, cards), AI client (`ai.py`: persistent lean `claude -p` on the subscription), prompts, LaTeX→Unicode |
| `plugin/stem-tutor/skills/tutor/scripts/tutorlib/` | engine: sessions, lesson mode (`lesson.py`), Obsidian views (`views.py`), grading, FSRS/Elo model, experiments, reports, weekly bookkeeping |
| `plugin/stem-tutor/` | the older Cowork plugin (still works; the terminal app is now primary) |
| `build/` | content pipeline: specs → graphs → packs (drafted, blind-solved, adjudicated), teach cards, publish to the vault |
| `foundry/` | content foundry: chapters built by Codex and Haiku workers with Opus managing (`foundry/README.md`) |
| `bugwatch/` | live two-agent bug hunt (Codex spots, Claude fixes; `bugwatch/README.md`) |
| `bin/tutor` | launcher (`tutor`, `tutor doctor`, `tutor --setup`) |
| `tests/` | pytest (engine) and `tests/app/` (AI client with a fake `claude`, Textual pilot tests) |

## Run
- `bin/tutor` — start (the vault also has a double-clickable `Start Tutor.command`)
- `bin/tutor doctor` — check vault, Obsidian registration, Claude sign-in, dependencies
- `.venv/bin/python -m pytest tests -q` — tests
- `.venv/bin/python build/publish.py` — publish packs, notes and the engine into the vault (`../STEM Tutor`)
- `.venv/bin/python build/plan.py && .venv/bin/python build/publish.py` — refresh the Almanac plan after
  `A-Levels.html` changes (the app says "Your Almanac has changed")

AI calls use `claude -p --safe-mode --disable-slash-commands --strict-mcp-config --setting-sources "" --tools ""
--system-prompt … --model haiku` so each request carries only the tutor brief and a small context packet.
