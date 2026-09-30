# Tiebreak (Codex, medium tier)

The chapter's answer key and an independent solver disagree on a few questions. You are the second independent
solver: solve **only the disputed question ids** you were given, **without seeing the keys**.

## Read only

`build/work/blind/<subtopic>.questions.json`, and only the entries whose `id` is in your list. Never open the pack,
the bundle, the note, the other solver's answers or any other `build/` file.

## Solve

Work each question from scratch with full reasoning. Use `.venv/bin/python -c "…"` (sympy is installed) for all
arithmetic; for figures (`image`), view `build/out/Assets/mcq/<image>`. Answer formats: MCQ letter; numeric value,
with its unit only when `"give_unit": true`, 3 significant figures; expression in Python/sympy syntax.

## Write

`build/work/blind/<subtopic>.tiebreak.json`: `{"<id>": "<answer>", …}` for exactly the listed ids. Write nothing else.
Never run git commands.

## Finish

Reply with the JSON report the output schema asks for; in `notes`, one short line per question where you were unsure.
