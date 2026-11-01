# Terminal app ownership

The terminal UI lives here; the canonical tutor engine lives in `src/tutorlib/`.

| Boundary | Owner | Responsibility |
| --- | --- | --- |
| App lifecycle | `app.py`, `__main__.py` | Start the app, own settings and AI clients, route global actions, manage local preparation, and apply shared CSS. |
| Main screens | `screens.py` | Home and topic selection, study sessions, chat, progress, saved attempts, help, and settings. `SessionScreen` coordinates the UI with the engine; engine rules stay in `tutorlib`. Shared reading/activity helpers remain here. |
| Modal dialogs | `dialogs.py` | Session summary, confirmation choices, and the Ask composer. `screens.py` re-exports `SummaryScreen`, `ConfirmScreen`, and `AskScreen` for existing callers and subclasses. Dialogs do not import the main screens. |
| Other study modes | `challenge_screen.py`, `shortcuts_screen.py` | Challenge and shortcut screen flows, using the shared panels and screen helpers. |
| Interaction and rendering | `panels.py`, `cards.py`, `look.py`, `texmath.py`, `output_format.py` | Input widgets and events, Rich cards, palette, terminal maths, and shared display normalization. `chat_output.py` owns structured AI documents; `learn_reply.py`, `learn_math.py`, and `learn_write.py` validate learning replies. |
| AI requests | `tutor_ai.py`, `ai.py`, `codex_ai.py`, `local_ai.py` | Route requests through the existing AI interface, manage provider conversations and local inference. `prompts.py` prepares tutor context; local context, web, vision, OCR, and reuse modules support the local provider. |
| Voice | `tts.py`, `screens.py::ReadAloud` | Synthesis, cache lookup, playback, and screen reading controls. Screens supply readable text; voice code owns audio operations. |
| Settings and storage | `config.py`, `tutorlib.store`, `tutorlib.packs`, `tutorlib.asset_library` | App settings and explicit vault selection, engine state and event writes, course packs, and Library asset lookup. Screens call the engine rather than inventing storage layouts. |

Learner state belongs in the selected vault. Shared study assets use its canonical
`Library/`; generated authoring work belongs in the workspace `Work/` area. Tests
use temporary vaults through `tests/conftest.py` and reusable asset setup through
`tests/library_assets.py`.

Keep dialog dependencies directed toward widgets, rendering, and engine helpers.
Existing imports from `tutor_app.screens` remain supported; new dialog code can
import `tutor_app.dialogs` directly.
