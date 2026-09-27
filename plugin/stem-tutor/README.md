# STEM Tutor (Cowork plugin)

Evidence-based tutor for CAIE 9701 Chemistry, CAIE 9702 Physics and Edexcel IAL Maths / Further Maths.
Haiku runs the conversation; a pure-Python engine does scheduling, grading, diagnosis and reports.

## Components
- `skills/tutor` — session protocol, mode references, and the engine (`scripts/tutor.py`, vendored wheels).
- `skills/study-arsenal` — study-mode router used instead of full-arsenal on study requests.
- `commands/` — `/study`, `/learn`, `/after-video`, `/review`, `/mark`, `/paper`, `/profile`.
- `agents/marker` (handwriting audit), `agents/digest` (long-text mapping), both Haiku.
- `hooks/hooks.json` — SessionStart brief when the STEM Tutor folder is connected.

## Setup
1. Cowork → Customize → Plugins → Upload `stem-tutor.plugin`.
2. Create a Project "STEM Tutor"; connect only `iCloud Obsidian/Documents/Notes/01 Study/STEM Tutor`; pick Haiku 4.5; turn off unused connectors.
3. Finder: right-click the STEM Tutor folder → Keep Downloaded.
4. Run `/study`. The first session runs onboarding.

Content packs (syllabus graphs, items, lesson notes) live in the folder's `.tutor/packs/` and are built in Claude Code.
