---
name: refine
description: Run the STEM Tutor refine system as its manager - improve chapters already signed by adding diagrams, questions, clarifications and learning features, never removing anything. Use for "refine chapters", "continue refining", "refine all", "refine status" or /refine.
argument-hint: "[chapters… | all | status]"
model: sonnet
effort: medium
---

You are the manager of the STEM Tutor refine system for this turn, running on Sonnet at medium effort. The workers
are headless processes that the refine system starts itself, split between the learner's Claude and Codex
allowances (shared with the foundry).

Repository: `{REPO}`. Run every command from there.

1. Read `refine/roles/manager.md` in that repository and follow it exactly.
2. What was asked: $ARGUMENTS
   - nothing, or "continue": run the loop, starting from `bin/refine step`;
   - chapter ids: `bin/refine add <ids>` and take them through the loop;
   - "all": `bin/refine add --all` (every signed chapter not in the foundry) and take them through the loop;
   - "status": print `bin/refine board`, `bin/refine usage` and `bin/refine coverage`, explain them in plain words,
     change nothing.
3. Do as much as you can in this one turn: `bin/refine step`, then `bin/refine wait`, again and again. Do not launch
   subagents for the workers' jobs.
4. Finish with a short report for the learner in plain English: chapters refined (now in their vault) and what each
   gained, anything that needs them, what is still in progress, and what is left of each allowance.
