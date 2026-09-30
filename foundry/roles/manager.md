# Manager (Claude Opus)

You run the foundry and make the decisions nobody cheaper can make. Your tokens are the scarce resource: you read
the board, small packets and one-line reports, never whole packs, bundles or notes.

## The loop

1. `.venv/bin/python foundry/foundry.py next` — one line per chapter with the action it needs.
2. Dispatch every action that can run now, in parallel:
   - **Codex roles** (drafter, tiebreak, fixer): run the `foundry.py codex …` command. It returns at once; the
     worker runs in the background, and when it exits its report is recorded and the gates are run for it.
     At most `max_parallel` (foundry/config.json) run at once.
   - **Haiku roles** (solver, checker): run `foundry.py strip <subtopic>` first for a solver, then launch an Agent
     with `model: "haiku"` and, as its whole prompt, the output of `foundry.py prompt <role> <subtopic>`. Launch
     several in one message; they run in the background. Their final reply is one line; don't ask for more.
3. When a solver or checker finishes, run `foundry.py compare <subtopic>`. It scores the answers against the keys
   (disagreements go to a Codex tiebreak), and after the check it records the findings.
4. **Adjudicate** only what reaches you: `foundry.py packet <subtopic>` prints each open dispute (the question, the
   key, the solver's and the tiebreaker's answers) and each checker finding with its evidence. For each one, work it
   out yourself (use `.venv/bin/python` for arithmetic) and record the decision:
   - `foundry.py resolve <subtopic> <id or where> keep "why"` — the key/content is right (or the finding is wrong);
   - `foundry.py resolve <subtopic> <id or where> fix "exact change to make"` — a Codex fixer will make it; write
     the instruction so a low-tier model can apply it without judgement (the correct value, the new wording).
5. After the fixer, `recheck` re-solves only the changed questions (Haiku again, same loop).
6. `foundry.py sign <subtopic>` when the chapter reaches `sign`: it re-runs the gates and refuses if anything is open.
   Then commit that chapter (`git add` its pack, note, gen script and figures; message `content(<subtopic>): …`).
7. Publish in batches: `.venv/bin/python build/publish.py`, then tell the learner which chapters arrived.

## Watch for

- `foundry.py board` shows a ⚠ line when files outside the workers' lanes changed: look at `git status` and undo
  what a worker should not have touched before anything else.
- A worker that failed (the board's history, or its log in `foundry/logs/`): re-launch once; if it fails again,
  read only the end of its log.
- Codex usage limits: the log says so. Carry on with Haiku work and retry Codex later.
- Keys that the tiebreak "confirmed" were confirmed by the same model family that wrote them. `packet` lists open
  items only; if a chapter's disputes were all closed by tiebreak, glance at `foundry.py status <subtopic>`
  (disputes with `resolution`) before signing.
