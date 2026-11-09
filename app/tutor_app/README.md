# Terminal app ownership

The terminal UI lives here; the canonical tutor engine lives in `src/tutorlib/`.

| Boundary | Owner | Responsibility |
| --- | --- | --- |
| App lifecycle | `app.py`, `__main__.py` | Start the app, own settings and AI clients, route global actions, manage local preparation, and apply shared CSS. |
| Main screens | `screens.py` | Home and topic selection, study sessions, chat, progress, saved attempts, help, and settings. `SessionScreen` coordinates the UI with the engine; engine rules stay in `tutorlib`. Shared reading/activity helpers remain here. |
| Modal dialogs | `dialogs.py` | Session summary, confirmation choices, and the Ask composer. `screens.py` re-exports `SummaryScreen`, `ConfirmScreen`, and `AskScreen` for existing callers and subclasses. Dialogs do not import the main screens. |
| Other study modes | `challenge_screen.py`, `shortcuts_screen.py` | Challenge and shortcut screen flows, using the shared panels and screen helpers. |
| Interaction and rendering | `panels.py`, `cards.py`, `look.py`, `texmath.py`, `output_format.py` | Input widgets and events, Rich cards, palette, terminal maths, and shared display normalization. `chat_output.py` owns structured AI documents; `learn_reply.py`, `learn_math.py`, and `learn_write.py` validate learning replies. |
| AI requests | `tutor_ai.py`, `ai.py`, `codex_ai.py`, `abacus_ai.py`, `local_ai.py` | Route requests through the existing AI interface, manage provider conversations and local inference. `abacus_ai.py` calls the Abacus.AI RouteLLM API with the learner's own key (`~/.config/routellm/key`); `abacus_models.py` lists the offered models. `prompts.py` prepares tutor context; local context, web, vision, OCR, and reuse modules support the local provider. |
| Voice | `tts.py`, `screens.py::ReadAloud` | Synthesis, cache lookup, playback, and screen reading controls. Screens supply readable text; voice code owns audio operations. |
| Settings and storage | `config.py`, `tutorlib.store`, `tutorlib.packs`, `tutorlib.asset_library` | App settings and explicit vault selection, engine state and event writes, course packs, and Library asset lookup. Screens call the engine rather than inventing storage layouts. |

Learner state belongs in the selected vault. Shared study assets use its canonical
`Library/`; generated authoring work belongs in the workspace `Work/` area. Tests
use temporary vaults through `tests/conftest.py` and reusable asset setup through
`tests/library_assets.py`.

Keep dialog dependencies directed toward widgets, rendering, and engine helpers.
Existing imports from `tutor_app.screens` remain supported; new dialog code can
import `tutor_app.dialogs` directly.

Settings includes **Confirm AI marks in lesson reviews**, enabled by default. Turning it off applies valid AI
mark-point results directly through the existing scoring path. Invalid or unavailable AI results still use manual
marking; protected attempt confirmation remains independent. The choice is saved with the other app settings.

**AI marking strictness** is separate from confirmation and model choice. `marking_policy.py` owns Auto, Lenient,
Balanced and Strict, their Settings help and shared examiner instructions. Auto (the default) selects Balanced
for learning/review and Strict for Practice, Test prep, Long questions, Topical past papers and Challenges. Explicit choices
override Auto. `prompts.py` applies the policy to short/long marking and session/Challenge re-marks for all providers.
Every level accepts equivalent correct wording and requires evidence from the complete answer; absent substantive
ideas and contradictions still lose credit. Deterministic numeric/MCQ rules and existing scores are unchanged.
Changing strictness changes the local reply-cache key through the prompt; no inference or re-mark starts on Save.

**Home menu and Practice.** `home_menu.py` lists the four home folders (Learn & revise, Questions, Profile & progress,
Tools) and the retired ids (`test`, `topical`, `source-practice`) that still start their old flows through
`HomeScreen.activate`. `HomeScreen` shows one level at a time (Enter opens, Esc/Backspace/left goes back, 1-9 jump,
0 back) and remembers the open folder on the app. Slow start-up work (Downloads scan, Today.md, week-in-review,
question-bank inventory, shortcut counts, Almanac push) runs in thread workers; the first paint uses the cached
inventory (`display_inventory.peek_inventory`). `practice_screens.py` is the merged Practice flow: `PickerScreen`
in mode `practice` (courses, "Entire course" rows, chapters), then `PracticeSetupScreen`, then
`SessionScreen({"mode": "practice", focus, course, scope, sources, count, difficulty, include_unstarted, types,
auto_mark})`. Options the engine's `start()` does not accept are dropped, not raised. Source-verified questions are
tagged "source-verified" (`cards.no_credit`) and count towards mastery like the past-paper bank. "Can I solve this?" (`solvable.py`) renders the
engine's dict (status, message, missing, given, adapted_prompt, topic, skipped) in `SessionScreen` and, from the
course graph, in `ChallengeScreen`.

Topical past papers (the older flow) reuses `PickerScreen` multi-select and then opens `TopicalSetupScreen` for a total question
count (1–200, default 10), type checklist and unique eligible availability. Change topics preserves count/type drafts;
Cancel leaves the current session untouched. Topic selection shortcuts operate on the topical list, while search
input keeps native editing. Availability and Start remain visible in small windows.

The same setup offers **Written-answer marking: Self-mark / Automatic AI**. Self-mark is the default; the choice
belongs to the topical session and survives resume without changing app Settings. Automatic marking uses the
existing examiner model and strictness, saves typed work before requesting a verdict, and applies exact valid
rubric results through owned marking tickets. Failed, stale or unsupported results cannot silently assign marks.
Paper-only work requires manual marking. Codex receives every declared source image in order; local models retain
single-image support, while unsupported image routes return to self-marking with a reason. MCQs and numeric or
expression questions keep deterministic grading.

Reviewed topical questions enter other suitable modes through the shared `Packs.items_for` overlay, preserving
source identity and eligibility rules. Test prep and Long question pickers include bank-only chapters when their
supported question kinds are available. Learn still requires published teaching content and applicable prerequisite
and no-help rules; unpublished extraction candidates never enter the learner bank through these selectors.

`tutorlib.topical_selection` owns kind/explicit-definition categories, eligible reviewed pools and random topic rounds.
The sampler assigns overlapping identities to topic contexts without starving a scarce topic when coverage is feasible.
`Tutor.start(..., topical_count=..., topical_types=...)` stores a bounded identity/chapter queue and revalidates each
question before serving it. `Tutor.topical_choices` supplies the same inventory to setup. Archived attempts are
reserved from custom counted/filtered sets and retain their ordinary recovery path; unconfigured legacy sessions
keep their existing time budget. Structured questions may mix writing and calculations; no image-based category
guesses, new questions or Library publication are performed by this flow.

Learn a topic displays processing status and elapsed time beside its controls, including answer-only view.
Startup and prepared actions paint an acknowledgement before synchronous work starts; pending tutor feedback and
marking keep their activity visible until completion. Controls wait during processing, while the inline composer
can retain a next-question draft. Activity is terminal-only and does not become lesson content or learner events.

The output backbone is documented in `docs/STEM_OUTPUT_FORMATTING.md`: `chat_output.py` owns semantic documents,
`output_format.py` owns display normalization, and the terminal/Obsidian adapters consume canonical Markdown.
Explicit prose line breaks and strongly evidenced worked-step boundaries remain visible across provider routes.
Protected literals, mathematical source, grading fields, speech and historical learner records retain their boundaries.
