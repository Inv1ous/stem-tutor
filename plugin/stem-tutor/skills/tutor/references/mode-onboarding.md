# Onboarding (first sessions)

Goal: a baseline for every subject, so the first real sessions start at the edge of what the learner knows. Completion: `taught` has been bracketed for chem, phys and math (one `diagnose` session each, across up to three sittings).

1. Explain in three lines: the engine schedules reviews and new topics from the Almanac; the profile learns which methods work from their results; they answer here, and long working goes on the iPad.
2. Run `brief` and state the next sitting and this Almanac week.
3. Run `taught`. It lists, per subject, the knowledge components (KCs) the Almanac says have been taught so far. Ask with AskUserQuestion which subject to baseline first (Chemistry, Physics, Maths).
4. `session start --mode diagnose --kcs <up to 8 ids of that subject>` and run the normal loop. Bracketing items are unassisted: no hints and no teaching until the block ends; the engine adds repair blocks for real gaps.
5. Close as usual. In the closing message, explain the two weekly habits:
   - Anki: double-click the `.apkg` in `STEM Tutor/Anki/` to import new cards; review them in Anki (FSRS on, desired retention 0.90).
   - Almanac: once a week press Export in the Almanac and save the file into `STEM Tutor/Almanac/`; the tutor writes `almanac-import-<date>.json` back there for the Almanac's Import button.
6. Next sessions: repeat steps 3–5 for the remaining subjects before switching to autopilot.
