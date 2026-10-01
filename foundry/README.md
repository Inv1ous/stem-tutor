# The content foundry

A workshop for building syllabus chapters (content packs: questions, worked examples, flashcards and the lesson
note in `Subjects/`) with a team of AI workers, where the expensive model only manages.

| Who | Model | Does | Why this model |
|---|---|---|---|
| **Manager** | Claude Sonnet at medium effort (type `/foundry`) | Runs the loop: launches workers, judges the simple cases, signs chapters off | Cheap to run; reads only short summaries |
| **Adjudicator** | Claude Opus, called by the manager | Decides what the manager must not decide alone: a key both checkers dispute, a change to an answer or definition, missing teaching content | Judgement, used only where it matters |
| **Drafter** | Codex medium tier (`gpt-6-sol`) | Writes the chapter: pack + lesson note, computing every answer with Python | The long writing job, on your ChatGPT plan instead of Claude |
| **Solver** | Claude Haiku, several at once | Answers every question **without seeing the answer key**; a big chapter is split into shards of 20 questions, one solver each | A different AI family from the drafter, so a wrong key shows up as a disagreement |
| **Tiebreak** | Codex medium tier | Solves only the disputed questions, also blind | Settles most disputes without the manager |
| **Checker** | Claude Haiku, alongside the solvers | Checks six fixed rules (hints that give the answer away, wrong definitions, two right options, wrong constants, note vs pack, off-syllabus) and quotes evidence | Narrow, rule-based reading that small models do well |
| **Fixer** | Codex low tier (`gpt-6-luna`) | Makes exactly the changes the manager wrote down | Mechanical edits |

Between every step, **gates** run automatically at no token cost: the pack validator (formats, answers recomputed,
enough questions per outcome, duplicate questions), the note linter (Obsidian syntax and maths), the blind compare,
and the **syllabus gate** (below).

## Following the syllabus

- **Every outcome, every chapter.** A chapter cannot be signed unless each syllabus learning outcome in it has a
  teaching card, is covered by the lesson note, has enough questions, has a definition card if the syllabus says
  "define" and a worked derivation if it says "derive"; and, for CAIE, every question the drafter wrote uses a command
  word from the syllabus's own list, as real papers do. The checker also reads for outcomes that are mentioned but
  not really taught or tested (its rule 7).
- **The whole syllabus.** `foundry coverage` shows, per syllabus, how many outcomes are in signed chapters, in
  progress and not started; which signed chapters no longer pass the syllabus gate; and what to build next in Almanac
  order (`foundry coverage --queue 12` drafts the next twelve). It also checks the outcome list itself against the
  official syllabus documents: all 873 outcomes are present. The 2028–2030 CAIE syllabuses state that there are no
  significant changes which affect teaching, so the A Level outcomes hold for the 2028 exams.

## A chapter's path

```
add ─► draft (Codex) ─► gates ─► solve (Haiku, blind) ─► compare ──disagree──► tiebreak (Codex, blind)
                                                           │ agree                 │
                                                           ▼                       ▼
                                                  check (Haiku, 6 rules) ◄─────────┘
                                                           │ findings or open disputes
                                                           ▼
                                        adjudicate (Opus reads a small packet) ─► fix (Codex) ─► recheck (Haiku)
                                                           │ nothing open                          │
                                                           ▼                                       ▼
                                                        sign ─► ready ─► publish ◄─────────────────┘ (via sign)
```

New chapters stay on the hold list (`build/out/packs/HOLD.json`) until they are signed, so nothing half-checked
reaches your vault.

## Using it

Everything goes through one command, `bin/foundry` in the `stem-tutor` folder, which works from any folder:

```bash
"$HOME/Miscellaneous/02 Education/~~ AI Workflow/stem-tutor/bin/foundry" board   # where every chapter is
"$HOME/Miscellaneous/02 Education/~~ AI Workflow/stem-tutor/bin/foundry" next    # what each chapter needs now
"$HOME/Miscellaneous/02 Education/~~ AI Workflow/stem-tutor/bin/foundry" watch   # live screen (Ctrl+C to close)
```

To type just `foundry watch`, run this once and open a new Terminal window:

```bash
echo 'alias foundry="$HOME/Miscellaneous/02\ Education/~~\ AI\ Workflow/stem-tutor/bin/foundry"' >> ~/.zshrc
```

In practice you type **`/foundry`** in any Claude session (or `/foundry 9702-7.1 9702-7.2` for particular chapters,
or `/foundry status`). That turn runs on **Sonnet at medium effort**, whatever model the session is set to, and
follows `foundry/roles/manager.md`: it launches the Codex workers (headless, through the Codex CLI inside the
ChatGPT app) and the Haiku workers as subagents, calls **Opus** itself for the decisions that need it, and asks you
only if something needs a person. `/foundry` is installed by `foundry install-skill` (run it again if the
`stem-tutor` folder moves).

**You don't open any Codex sessions.** Each Codex job is its own separate headless session, started by the foundry
and closed when the job ends; up to `max_parallel` (3) run at once across chapters. **Haiku runs in parallel too**:
every solver shard and checker of every chapter that needs one can run at the same time.

If you would rather watch a Codex job in the ChatGPT app, run `foundry prompt <role> <chapter>` (roles: drafter, tiebreak, fixer), paste the output into a new Codex task in the `stem-tutor` folder, and
the foundry won't start that job itself. The prompt ends with the command that reports the job back.

- 74 chapter bundles (weeks 1–10) are already prepared in `build/work/bundles/`.
- The six held chapters (9701-1.1 to 1.4, P1-2, S1-1) can go straight in: `add` puts an existing pack at `solve`.
- Codex jobs use your ChatGPT plan's Codex allowance. If it runs out, the log says so and the manager carries on
  with the Haiku work until it resets.

## When a chapter is done, and when tokens run out

- **Signed = in your vault.** The moment a chapter passes its last check, `sign` publishes it into the vault, commits
  that chapter's files to git (a checkpoint nothing can undo) and pops up "… is ready to study in your vault". If the
  tutor app is open, the next time you are back at its menu it loads the new chapter and says "New chapters ready: …".
  Nothing else in the app changes, and a session you are in the middle of is never disturbed.
- **Every step is saved as it happens.** The board (`foundry/state/`) is written to disk after every step, so a
  session that stops mid-way (usage limit, closed laptop) loses nothing already done.
- **Codex keeps going without Claude.** A Codex job that is running when the Claude session stops finishes on its own
  and records its result; the next session finds it done.
- **Haiku stops with Claude.** A Haiku worker cut off before it wrote its file shows as *stalled* after 40 minutes;
  the next session sends that shard again (only that shard: each is 20 questions at most).
- **Picking up again:** start a Claude session and say *"continue the foundry"*. It runs `foundry next`, which says
  exactly where every chapter is.
- **Drafting ahead with no Claude session:** `foundry queue drafter <chapters…>` (run detached) starts a Codex drafter
  for each chapter as slots free up. The drafts are checked by the gates and wait, unpublished, for the next session
  to blind-solve, check and sign them.

## Seeing what's running

- **Live screen:** `foundry watch` redraws every 5 seconds: each chapter's stage, every
  Haiku worker (… working / ✓ done, with minutes elapsed) and every Codex worker with its model, minutes running and
  the last thing it did (for example the validator command it is running). Ctrl+C to close. When the Claude session
  starts workers it opens this for you in a terminal tab beside the chat.
- **Notifications:** each Codex job that ends pops up a Mac notification ("9702-2.2: drafter finished · gates ok",
  or "failed").
- **Haiku agents** also appear in the Claude app's task list while they run, and the session is told the moment
  each one finishes.
- **Codex logs:** `foundry/logs/<chapter>.<role>.<time>.log` is the worker's full transcript. The session is also
  saved in Codex's history (`~/.codex/sessions`), so it can be reopened afterwards with `codex resume`.
- **One-off:** `foundry.py board` (one line per chapter) and `foundry.py next` (what each chapter is waiting for,
  e.g. "wait: Haiku solver#2, checker working (2/5 done)").

## Files

| Path | What |
|---|---|
| `foundry/foundry.py` | The board, the gates, and the worker launcher |
| `foundry/roles/*.md` | Each worker's instructions (workers read their own file, so the manager's prompts stay tiny) |
| `foundry/config.json` | Which Codex model and effort each role uses, and how many run at once |
| `foundry/schemas/*.json` | The report each Codex worker must return |
| `foundry/state/<chapter>.json` | Each chapter's stage, gate results, disputes, findings and fixes |
| `foundry/logs/` | Codex worker logs |
| `build/PACK.md` | The quality bar and format every chapter must meet |

## Safety

- Workers are told which files they may write (their chapter's pack, note, generator script and figures). The
  board flags any other changed file. Codex runs in its `workspace-write` sandbox, and never commits.
- Solvers never see answer keys: they read a stripped questions file.
- Nothing is published until the manager signs the chapter off and runs `build/publish.py`.
