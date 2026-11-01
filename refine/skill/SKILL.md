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
   - chapter ids: `bin/refine add <ids>` (default persisted `lessons` scope; use `--scope full` only for requested subject-note/assessment work) and take them through the loop;
   - "all": `bin/refine add --oldest` (every signed chapter not in the foundry) and take them through the loop;
   - "status": print `bin/refine board`, `bin/refine usage` and `bin/refine coverage`, explain them in plain words,
     change nothing.
3. Do as much as you can in this one turn: `bin/refine step`, then `bin/refine wait`, again and again. Do not launch
   subagents for the workers' jobs.
4. Finish with a short report for the learner in plain English: chapters refined and whether publication ran and what each
   gained, anything that needs them, what is still in progress, and what is left of each allowance.

Read the run-limit and report contract in the manager role before launching.

An explicitly requested `bin/refine new-run COURSE` starts a distinct course run and archives
the previous deadline/run ID. It refuses while a course worker/manual job is active, preserves
pending chapter history/candidates, and permits intentional renewal after an expired run.
Never invoke `new-run` automatically from continuation, add, retry, queue or restart.


## Stop repeated failures

Before launching paid work, run the repository's `bin/foundry doctor`. Honor the configured weekly launch cap and provider reserves in `refine/config.json`, plus any stricter current user limit; unknown readings stop launches. Treat a paused worker guard as a stop, not a request to change provider or retry through another command.

Classify the blocker first: protected PDF/source damage requires source-bound independent correction review; incomplete forms require every reviewed inventory entry; missing visuals require verified files bound to the relevant card; written checks require independent solving and review. Never fill content with placeholders or invent symbols.

After two failures for a role in the same pass/job, preserve candidate work and report the blocker. Never automatically call unstick, add a new pass to bypass the guard, renew a course budget, or overwrite a baseline/review record. Clear failures only after explicit operator direction, with a recorded reason. Verify the actual learner path before claiming the material is active or ready.
