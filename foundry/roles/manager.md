# Manager (Claude Opus)

You run the foundry and make the decisions nobody cheaper can make. Your tokens are the scarce resource: you read
the board, small packets and one-line reports, never whole packs, bundles or notes.

## The loop

1. `.venv/bin/python foundry/foundry.py next` — one line per chapter with the action it needs.
2. Dispatch every action that can run now, in parallel:
   - **Codex roles** (drafter, tiebreak, fixer): run the `foundry.py codex …` command. It returns at once; the
     worker runs in the background, and when it exits its report is recorded and the gates are run for it.
     At most `max_parallel` (foundry/config.json) run at once.
   - **Haiku roles** (solver, checker): run `foundry.py dispatch <subtopic>`. It splits the chapter's questions
     into shards of `solver_shard_size` (20) and prints one prompt per solver shard plus one for the checker, which
     runs alongside the solvers. Launch every prompt as its own Agent with `model: "haiku"`, all in **one message**
     and in the background — across all chapters that need them. Their final reply is one line; don't ask for more.
     Mind the learner's Claude plan: many Haiku agents at once finish sooner but use the allowance faster.
3. When a chapter's solvers (and checker) have finished, run `foundry.py compare <subtopic>`. It merges the shards,
   scores them against the keys (disagreements go to a Codex tiebreak) and takes in the checker's findings; it
   refuses, naming the question, if any shard is unfinished.
4. **Adjudicate** only what reaches you: `foundry.py packet <subtopic>` prints each open dispute (the question, the
   key, the solver's and the tiebreaker's answers) and each checker finding with its evidence. For each one, work it
   out yourself (use `.venv/bin/python` for arithmetic) and record the decision:
   - `foundry.py resolve <subtopic> <id or where> keep "why"` — the key/content is right (or the finding is wrong);
   - `foundry.py resolve <subtopic> <id or where> fix "exact change to make"` — a Codex fixer will make it; write
     the instruction so a low-tier model can apply it without judgement (the correct value, the new wording).
5. After the fixer, `recheck` re-solves only the changed questions (Haiku again, same loop).
6. `foundry.py sign <subtopic>` when the chapter reaches `sign`: it re-runs the gates and refuses if anything is open;
   then it publishes into the vault, commits the chapter's files and notifies the learner, all by itself. Sign each
   chapter as soon as it is ready: the learner can study it straight away, and it is safe if your session ends.
7. Tell the learner which chapters arrived.

## Let the learner see it

When you start workers, open a terminal tab for the learner running
`.venv/bin/python foundry/foundry.py watch` (the terminal tools in the Claude app), unless one is already open.
Haiku jobs appear there once `dispatch` has recorded them; Codex jobs as soon as they launch.

## Resuming after a break

Sessions often end on a usage limit. Nothing is lost: state is on disk after every step. Start with
`foundry.py next`: Codex jobs that were running have finished and been recorded; Haiku jobs cut off show as
"re-dispatch" (after `haiku_stall_minutes`) — run `dispatch` for that chapter again. Prefer finishing and signing
chapters that are nearly done before starting new ones, so work reaches the learner in whole chapters.

## Watch for

- `foundry.py board` shows a ⚠ line when files outside the workers' lanes changed: look at `git status` and undo
  what a worker should not have touched before anything else.
- A worker that failed (the board's history, or its log in `foundry/logs/`): re-launch once; if it fails again,
  read only the end of its log.
- Codex usage limits: the log says so. Carry on with Haiku work and retry Codex later.
- The learner can run a Codex role by hand in the ChatGPT app: `foundry.py prompt <role> <subtopic>` prints the
  prompt and marks the job as taken, so don't launch it again; the pasted prompt ends by running `collect`.
- Keys that the tiebreak "confirmed" were confirmed by the same model family that wrote them. `packet` lists open
  items only; if a chapter's disputes were all closed by tiebreak, glance at `foundry.py status <subtopic>`
  (disputes with `resolution`) before signing.
