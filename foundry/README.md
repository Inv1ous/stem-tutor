# The content foundry

A workshop for building syllabus chapters (content packs: questions, worked examples, flashcards and the lesson
note in `Subjects/`) with a team of AI workers, paid for by **both** of your allowances: Claude and Codex.

## Who does what

Every role can run on either allowance. Each has a ladder of models per allowance, cheapest first, and starts on the
first rung.

| Who | On Claude, first rung → next | On Codex, first rung → next | Does |
|---|---|---|---|
| **Drafter** | Opus, low effort → medium | `gpt-6-sol` low → medium | Writes the chapter: pack + lesson note, computing every answer with Python |
| **Solver** | Haiku → Sonnet low | `gpt-6-sol` low → medium | Answers every question **without seeing the answer key**; a big chapter is split into shards of 20 questions, one solver each |
| **Tiebreak** | Sonnet low → medium | `gpt-6-sol` low → medium | Solves only the disputed questions, also blind, at a stronger tier than the solver |
| **Checker** | Haiku → Sonnet low | `gpt-6-sol` low → medium | Checks seven fixed rules (hints that give the answer away, wrong definitions, two right options, wrong constants, note vs pack, off-syllabus, outcomes not taught) and quotes evidence |
| **Fixer** | Haiku → Sonnet low | `gpt-6-luna` low → `gpt-6-sol` low | Makes exactly the changes that were decided |
| **Adjudicator** | Opus medium → high | `gpt-6-astra` medium → high | Decides what the manager must not decide alone: a key both checkers dispute, a change to an answer or definition, missing teaching content |
| **Manager** | Sonnet at medium effort (type `/foundry`) | | Runs the loop, judges the simple cases, calls the adjudicator |

Between every step, **gates** run automatically at no token cost: the pack validator (formats, answers recomputed,
enough questions per outcome, duplicate questions), the note linter (Obsidian syntax and maths), the blind compare,
and the **syllabus gate** (below).

## Two allowances, used up together

`foundry usage` shows what is used of each allowance and where the next job goes:

```
Codex   5 hours     29% used  resets Fri 23:01
Codex   week        84% used  resets Wed 17:00
Claude  5 hours     74% used  resets Sat 01:59
Claude  week        77% used  resets Wed 14:00 (5% kept back)
next job: Claude (more of its week left for the time until it resets); …
```

- **The split follows what is really left.** Before every job the foundry reads both allowances and sends the job to
  the one with more of its week left for the time until it resets. Whichever starts with more gets the work until
  the two are level, and then they are kept level, so they run out together. If one resets sooner, it is used first,
  because what is left of it at the reset would be lost. A full five-hour window closes an allowance until it
  reopens.
- **The family that wrote a chapter never checks it.** The allowance that drafts a chapter is its *maker*; the blind
  solver and the tiebreak always run on the other one, so a wrong key shows up as a disagreement between two
  different AI families. If the other allowance is used up, that chapter waits for it.
- **The least model that works.** A role starts on the first rung of its ladder. If a job fails (the worker stops,
  writes nothing, or leaves the gates red), that chapter's retry runs one rung up. A rung that fails a role twice
  running is not used for it again. A usage limit is not counted as a failure. A blind solver is judged by its
  answers, not by finishing: if the tiebreak sides with the key against it on more than 15% of a chapter's
  questions, that counts as a failure of its tier.
- **Some of Claude's week is kept back** (5%), because the tutor's own AI help uses the same allowance. Change
  `reserve` in `foundry/config.json` to keep more or none.
- **How the allowances are read.** Codex reports its own figures when asked, at no cost. Claude has no such command:
  the foundry uses what Claude Code last fetched (when a session started), what each Claude worker is told as it
  runs, and what its workers have cost since. The weekly figure for Claude can therefore lag a little; it is corrected by
  the next worker.
- **Claude's five-hour window is the blind spot.** A headless run is told about one limit only, the one nearest its
  end, which is usually the weekly one. So the foundry often does not know how full Claude's five-hour window is,
  and `foundry usage` says "not reported". The Claude app's usage card does show it: the manager passes it on
  (`foundry reading claude five_hour <percent> <reset time>`), and so can you. Without it the foundry finds out when
  a Claude job is refused; it then keeps Claude closed until that window resets and gives the work to Codex.

## Following the syllabus

- **Every outcome, every chapter.** A chapter cannot be signed unless each syllabus learning outcome in it has a
  teaching card, is covered by the lesson note, has enough questions, has a definition card if the syllabus says
  "define" and a worked derivation if it says "derive"; and, for CAIE, every question the drafter wrote uses a command
  word from the syllabus's own list, as real papers do. The checker also reads for outcomes that are mentioned but
  not really taught or tested (its rule 7).
- **The whole syllabus.** `foundry coverage` shows, per syllabus, how many outcomes are in signed chapters, in
  progress and not started; which signed chapters no longer pass the syllabus gate; and what to build next: the
  chapters in front of you first, in Almanac order, with the ones you have ticked off in the Almanac last
  (`foundry coverage --queue 12` drafts the next twelve). It also checks the outcome list itself against the
  official syllabus documents: all 873 outcomes are present. The 2028–2030 CAIE syllabuses state that there are no
  significant changes which affect teaching, so the A Level outcomes hold for the 2028 exams.

## A chapter's path

```
add ─► draft (the maker) ─► gates ─► solve (the other family, blind) ─► compare ──disagree──► tiebreak (blind)
                                                           │ agree                              │
                                                           ▼                                    ▼
                                                  check (7 rules) ◄─────────────────────────────┘
                                                           │ findings or open disputes
                                                           ▼
                              adjudicate (manager, or the adjudicator on a small packet) ─► fix ─► recheck (blind)
                                                           │ nothing open                            │
                                                           ▼                                         ▼
                                                        sign ─► ready ─► publish ◄───────────────────┘ (via sign)
```

New chapters stay on the hold list (`build/out/packs/HOLD.json`) until they are signed, so nothing half-checked
reaches your vault.

## Using it

Everything goes through one command, `bin/foundry` in the `stem-tutor` folder, which works from any folder:

```bash
"$HOME/Miscellaneous/02 Education/~~ AI Workflow/stem-tutor/bin/foundry" board   # where every chapter is
"$HOME/Miscellaneous/02 Education/~~ AI Workflow/stem-tutor/bin/foundry" usage   # both allowances
"$HOME/Miscellaneous/02 Education/~~ AI Workflow/stem-tutor/bin/foundry" watch   # live screen (Ctrl+C to close)
```

To type just `foundry watch`, run this once and open a new Terminal window:

```bash
echo 'alias foundry="$HOME/Miscellaneous/02\ Education/~~\ AI\ Workflow/stem-tutor/bin/foundry"' >> ~/.zshrc
```

In practice you type **`/foundry`** in any Claude session (or `/foundry 9702-7.1 9702-7.2` for particular chapters,
or `/foundry status`). That turn runs on **Sonnet at medium effort**, whatever model the session is set to, and
follows `foundry/roles/manager.md`: it runs `foundry step` (start what can run, compare, sign) and `foundry wait` in
turn, judges the few items that need it, calls the adjudicator for the rest, and asks you only if something needs a
person. `/foundry` is installed by `foundry install-skill` (run it again if the `stem-tutor` folder moves).

**You don't open any sessions.** Each worker is its own separate headless process, started by the foundry and
closed when the job ends: a Codex one through the Codex CLI inside the ChatGPT app, a Claude one through `claude -p`
with your plugins, skills and hooks left out, so that it costs only what its job needs. Up to three run at once on
Codex and four on Claude.

If you would rather watch a Codex job in the ChatGPT app, run `foundry prompt <role> <chapter>` (roles: drafter,
tiebreak, fixer), paste the output into a new Codex task in the `stem-tutor` folder, and the foundry won't start that
job itself. The prompt ends with the command that reports the job back.

- 74 chapter bundles (weeks 1–10) are already prepared in `build/work/bundles/`.
- An existing pack can go straight in: `add` puts it at `solve`.

## When a chapter is done, and when an allowance runs out

- **Signed = in your vault.** The moment a chapter passes its last check, `sign` publishes it into the vault, commits
  that chapter's files to git (a checkpoint nothing can undo) and pops up "… is ready to study in your vault". If the
  tutor app is open, the next time you are back at its menu it loads the new chapter and says "New chapters ready: …".
  Nothing else in the app changes, and a session you are in the middle of is never disturbed.
- **Every step is saved as it happens.** The board (`foundry/state/`) is written to disk after every step, so a
  session that stops mid-way (usage limit, closed laptop) loses nothing already done.
- **Workers keep going without the manager.** A worker that is running when the manager's session stops finishes on
  its own and records its result; the next session finds it done. A worker that was killed before it reported is
  started again by the next `foundry step`.
- **One allowance used up:** work that the other may do carries on. Chapters whose next job must run on the used-up
  one (the blind solve of a chapter the other family drafted) wait until it resets; `foundry step` says which.
- **Picking up again:** start a Claude session and say *"continue the foundry"*.
- **Drafting ahead with no Claude session:** `foundry queue drafter <chapters…>` (run detached) starts a drafter for
  each chapter as slots free up, on whichever allowance has more left. The drafts are checked by the gates and wait,
  unpublished, for their blind solve.

## Seeing what's running

- **Live screen:** `foundry watch` redraws every 5 seconds: both allowances, each chapter's stage, and every worker
  with its allowance, its model, minutes running and the last thing it did. Ctrl+C to close. When the manager starts
  workers it opens this for you in a terminal tab beside the chat.
- **Notifications:** each drafter, fixer, tiebreak or adjudicator that ends pops up a Mac notification
  ("9702-2.2: drafter finished · gates ok", or "failed").
- **Logs:** `foundry/logs/<chapter>.<job>.<time>.log` is the worker's full transcript (for a Claude worker, a list
  of events). A Codex session is also saved in Codex's history (`~/.codex/sessions`), so it can be reopened with
  `codex resume`.
- **One-off:** `foundry board` (one line per chapter) and `foundry next` (what each chapter is waiting for).

## Files

| Path | What |
|---|---|
| `foundry/foundry.py` | The board, the gates, and the worker launcher |
| `foundry/router.py` | Reads both allowances, chooses where each job goes and on which tier |
| `foundry/roles/*.md` | Each worker's instructions (workers read their own file, so prompts stay tiny) |
| `foundry/config.json` | Each role's ladder of models per allowance, how many run at once, how much to keep back |
| `foundry/schemas/*.json` | The report a drafter, fixer or tiebreak must return |
| `foundry/state/<chapter>.json` | Each chapter's stage, maker, gate results, disputes, findings and fixes |
| `foundry/usage.json` | The router's notes: the last readings, what has been learned about tiers (not in git) |
| `foundry/logs/` | Worker logs |
| `build/PACK.md` | The quality bar and format every chapter must meet |

## Safety

- Workers are told which files they may write (their chapter's pack, note, generator script and figures). The
  board flags any other changed file. A Codex worker runs in its `workspace-write` sandbox; a Claude worker may edit
  files in the repository and run the project's own Python, and nothing else. Neither commits.
- Solvers never see answer keys: they read a stripped questions file.
- Nothing is published until the chapter is signed.

## Why these Codex tiers (measured 2026-10-10)

The same 60 blind questions (30 official past-paper MCQs, 20 drafted numeric, 10 drafted MCQ), solved without keys and
marked by the real grader:

| Model | Right of 60 | Official MCQs | Time for 3 shards |
|---|---|---|---|
| Codex `gpt-6-luna` low | 47 | 22 / 30 | 45 s |
| Codex `gpt-6-luna` medium | 46 | 21 / 30 | 39 s |
| Codex `gpt-6-sol` low | 54 | 29 / 30 | 104 s |
| Codex `gpt-6-sol` medium | 55 | 30 / 30 | 114 s |
| Claude Haiku | 54 | 30 / 30 | 259 s |
| Claude Sonnet low | 55 | 30 / 30 | 124 s |

Two items nobody got right are worked-example ids, not model misses. So by accuracy `gpt-6-sol` low is Haiku's
equivalent, and `gpt-6-sol` medium is Sonnet's; `gpt-6-luna` (any effort) is below Haiku and its extra misses become
false disputes that cost tiebreaks. Blind solving and checking therefore start on `gpt-6-sol` low; `gpt-6-luna` stays
for the fixer, whose job is to make exactly the change it is told. Twelve Codex jobs moved the week by less than a
percent, so the larger model costs seconds, not allowance.
