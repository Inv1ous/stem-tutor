# The content foundry

A workshop for building syllabus chapters (content packs: questions, worked examples, flashcards and the lesson
note in `Subjects/`) with a team of AI workers, where the expensive model only manages.

| Who | Model | Does | Why this model |
|---|---|---|---|
| **Manager** | Claude Opus (the session you talk to) | Plans batches, launches workers, decides disputes, signs chapters off, publishes | Judgement; reads only short summaries |
| **Drafter** | Codex medium tier (`gpt-6-sol`) | Writes the chapter: pack + lesson note, computing every answer with Python | The long writing job, on your ChatGPT plan instead of Claude |
| **Solver** | Claude Haiku, several at once | Answers every question **without seeing the answer key**; a big chapter is split into shards of 20 questions, one solver each | A different AI family from the drafter, so a wrong key shows up as a disagreement |
| **Tiebreak** | Codex medium tier | Solves only the disputed questions, also blind | Settles most disputes without the manager |
| **Checker** | Claude Haiku, alongside the solvers | Checks six fixed rules (hints that give the answer away, wrong definitions, two right options, wrong constants, note vs pack, off-syllabus) and quotes evidence | Narrow, rule-based reading that small models do well |
| **Fixer** | Codex low tier (`gpt-6-luna`) | Makes exactly the changes the manager wrote down | Mechanical edits |

Between every step, **gates** run automatically at no token cost: the pack validator (formats, answers recomputed,
coverage, duplicate questions), the note linter (Obsidian syntax and maths), and the blind compare.

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

Everything goes through one script (run from the `stem-tutor` folder):

```bash
.venv/bin/python foundry/foundry.py add 9702-2.2 9702-2.3   # put chapters on the board
.venv/bin/python foundry/foundry.py board                    # where every chapter is
.venv/bin/python foundry/foundry.py next                     # what each chapter needs now
```

In practice you tell the Claude session: *"Run the foundry on 9702-2.2 to 9702-3.1"*, and it follows
`foundry/roles/manager.md`: it launches the Codex workers itself (headless, through the Codex CLI inside the ChatGPT
app) and the Haiku workers as subagents, and asks you only if something needs a person.

**You don't open any Codex sessions.** Each Codex job is its own separate headless session, started by the foundry
and closed when the job ends; up to `max_parallel` (3) run at once across chapters. **Haiku runs in parallel too**:
every solver shard and checker of every chapter that needs one can run at the same time.

If you would rather watch a Codex job in the ChatGPT app, run `.venv/bin/python foundry/foundry.py prompt <role>
<chapter>` (roles: drafter, tiebreak, fixer), paste the output into a new Codex task in the `stem-tutor` folder, and
the foundry won't start that job itself. The prompt ends with the command that reports the job back.

- 74 chapter bundles (weeks 1–10) are already prepared in `build/work/bundles/`.
- The six held chapters (9701-1.1 to 1.4, P1-2, S1-1) can go straight in: `add` puts an existing pack at `solve`.
- Codex jobs use your ChatGPT plan's Codex allowance. If it runs out, the log says so and the manager carries on
  with the Haiku work until it resets.

## Seeing what's running

- **Live screen:** `.venv/bin/python foundry/foundry.py watch` redraws every 5 seconds: each chapter's stage, every
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
