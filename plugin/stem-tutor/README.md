# STEM Tutor (Cowork plugin)

Version **2.6.1** — [release notes](../../docs/releases/v2.6.1.md).

Evidence-based tutor for CAIE 9701 Chemistry, CAIE 9702 Physics and Edexcel IAL Maths / Further Maths.
Haiku runs the conversation; a pure-Python engine does scheduling, grading, diagnosis and reports.

## Components
- `skills/tutor` — session protocol, mode references and distribution entry points (`scripts/tutor.py`, vendored wheels).
- `src/tutorlib/` in the repository — canonical engine source; the plugin's `scripts/tutorlib` is a distribution adapter.
- `skills/study-arsenal` — study-mode router used instead of full-arsenal on study requests.
- `commands/` — `/study`, `/learn`, `/after-video`, `/review`, `/mark`, `/paper`, `/profile`.
- `agents/marker` (handwriting audit), `agents/digest` (long-text mapping), both Haiku.
- `hooks/hooks.json` — SessionStart brief when the STEM Tutor folder is connected.

## Setup
1. Cowork → Customize → Plugins → Upload `stem-tutor.plugin`.
2. Create a Project "STEM Tutor"; connect only `iCloud Obsidian/Documents/Notes/01 Study/STEM Tutor`; pick Haiku 4.5; turn off unused connectors.
3. Finder: right-click the STEM Tutor folder → Keep Downloaded.
4. Run `/study`. The first session runs onboarding.

Reusable content packs, syllabus graphs, items and lesson notes live in the vault's catalogued `Library/`.
The `.tutor/packs/CURRENT` pointer selects the active release; prior resources and review bindings are preserved.
Unpublished preparation, candidates and worker records live in the sibling `Work/` tree. A source checkout does not
include those Library payloads or local worker data; see the repository's workspace-storage instructions.
