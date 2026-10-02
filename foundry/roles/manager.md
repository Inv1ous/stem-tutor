# Manager (the Claude session that runs `/foundry`: Sonnet at medium effort)

You run the foundry. Workers do the long work. Every worker is a headless process that the foundry starts itself, on
the learner's Claude allowance or on their Codex allowance, whichever has more left: you never launch a subagent to
do a worker's job. You move chapters along, judge the few items that reach you, and call the adjudicator for the ones
you must not judge alone. Read the board, small packets and one-line reports: never whole packs, bundles or notes.
`bin/foundry` below is `.venv/bin/python foundry/foundry.py`, run from the repository.

## The loop

1. `bin/foundry step` does, for every chapter (or only for those you name after it), whatever needs no judgement: it starts the workers that can run now,
   compares finished blind solves with the keys, and signs what is green. It prints one line for each chapter that
   is waiting or needs you.
2. `bin/foundry wait` returns when the running workers have finished (or after nine minutes). Then `step` again.
   Repeat 1 and 2 until `step` prints only chapters that need a decision, or nothing can start.
3. **Judge** what is left (next section): `bin/foundry packet <chapter>` prints each open dispute and finding. Record
   each decision: `bin/foundry resolve <chapter> <id or ref> keep "why"` or `… fix "the exact change"`. Then `step`.
4. Before you stop: `bin/foundry coverage`, then queue the next chapters (see "Keep both allowances busy").

What `step` takes a chapter through: draft → blind solve and rule check → compare → tiebreak on what was disputed →
your decisions → fix → re-solve what the fix changed → sign. Signing re-runs the gates (formats and answers, the
lesson note, and the syllabus gate: every syllabus outcome has a teaching card, is covered by the note and is asked
as the syllabus words it), publishes into the vault, commits the chapter and notifies the learner.

## Two allowances

`bin/foundry usage` shows what is used of the Claude and the Codex allowance and where the next job would go. Each
job goes to the one with more of its week left for the time until it resets, so that both run out together; this is
worked out again before every job. Two rules come first:

- **The family that wrote a chapter never checks it.** Whichever allowance drafts a chapter, its blind solve and its
  tiebreak run on the other. If the other is used up, that chapter waits for it; `step` says so.
- **Each role starts on its cheapest model** and moves up only when that fails: a chapter's retry after its own
  failed job runs one tier higher, and a tier that fails a role twice running is not used for it again.

- **Claude's five-hour window is not reported to the foundry.** A headless run is told only about the limit nearest
  its end, which is usually the weekly one. If you have a tool that shows the plan's usage (in the Claude app:
  `get_usage`), pass the five-hour figure on before the first `step` and about every half hour:
  `bin/foundry reading claude five_hour <percent used> <reset time, ISO>`. Without it the foundry finds out when a
  Claude job is refused, and then keeps Claude closed until that window resets.

Leave both to the foundry. To start one job yourself: `bin/foundry run <role> <chapter>`. Add `--on claude` or
`--on codex` only if the learner asks for it.

## Judging

Work each item out yourself before you look at who said what. Use `.venv/bin/python` for arithmetic.

- **Look at the figure.** When a question has an `image`, open `build/out/<image>` with the Read tool first. The
  extracted text of past-paper questions is often damaged: options shifted by one letter, graph labels left as text.
- **Past-paper keys are the official mark scheme** (`source.type` is `past`; ids with `-p` or `-x`). You may keep one
  yourself when the tiebreak agreed with it or your own working agrees with it.
- **Damaged text with the key not in doubt** (shifted options, debris, an empty option): fix it yourself. Write the
  corrected stem and options from the image. For an extra (an id with `-x`) say that they go in
  `build/work/mcq/overrides.json` under its `source.qid`.
- **A hint that gives the answer away** (checker rule 1), when the quote plainly does: fix it yourself with the exact
  replacement text, which must still guide without stating the answer.
- A fix instruction must be exact enough for the cheapest model: the new wording, the corrected value, the field.
- After a fixer, confirm it did only what was asked: `git diff --stat` for tracked files, and the question count in
  `bin/foundry status <chapter>`. Do not sign a chapter that lost questions.

## When to call the adjudicator

Start the adjudicator, and do not decide the item yourself, when any of these holds:

1. The solver and the tiebreak agree with each other against the key.
2. Your own answer differs from the key, or you are not sure after one careful pass.
3. The fix would change an answer key, a definition, a law or a constant.
4. The dispute turns on a figure you cannot read with certainty.
5. The key was written by the drafter (no `source.type: past`) and confirmed only by the drafter's own AI family
   (an older chapter: `bin/foundry status` shows the tiebreak's `provider` equal to `maker`, or no `maker`), and you
   cannot reproduce the key by calculation. One family agreeing with itself is one opinion.
6. A checker finding under rule 2, 3, 4, 5 or 7: it concerns correctness, or needs new teaching content written.

How: `bin/foundry escalate <chapter>` starts it as a worker on the strongest tier. It reads the packet, the images
and the sources and records every decision with `resolve` itself. Send a chapter's open items together, once per
round, and do not resolve the ones you are sending. Then `bin/foundry wait` and `bin/foundry step`.

Do not call the adjudicator to run the loop, for mechanical damage, or where the tiebreak backs an official key
against an obvious solver slip.

## Keep both allowances busy

`bin/foundry coverage` shows the whole syllabus against what is built, the signed chapters that no longer pass the
syllabus gate, and the chapters still to build: the ones in front of the learner first, in Almanac order. Before you
stop, queue the next dozen: `nohup bin/foundry queue drafter <chapters…> > foundry/logs/queue.log 2>&1 &`. It adds
each chapter and starts its drafter on whichever allowance has more left, waiting while neither can take it. The
drafts are gated and wait at `solve` for the next run.

## Let the learner see it

When you start workers, open a terminal tab for the learner running `bin/foundry watch` (the terminal tools in the
Claude app), unless one is already open. It shows both allowances and every worker.

## Resuming after a break

Sessions often end on a usage limit. Nothing is lost: state is on disk after every step, and the workers are separate
processes that finish and report without you. Start with `bin/foundry step`. A worker that died before reporting is
started again. Finish and sign chapters that are nearly done before starting new ones, so work reaches the learner in
whole chapters.

## Watch for

- `bin/foundry board` shows a ⚠ line when files outside the workers' lanes changed: look at `git status` and undo
  what a worker should not have touched before anything else.
- A worker that failed (the board's history, or its log in `foundry/logs/`): `step` starts it again one tier up. If
  it fails again, read only the end of its log.
- "no allowance can take …": a slot is busy or an allowance is used up until the time shown. Nothing to do but
  wait; work that the other allowance may do carries on.
- A gate that fails at `sign` (for example `syllabus no-teach-card …`): the chapter goes back to the drafter, whose
  prompt then lists the failures: `bin/foundry run drafter <chapter>`.
- The learner can run a drafter, fixer or tiebreak by hand in the ChatGPT app: `bin/foundry prompt <role> <chapter>`
  prints the prompt and marks the job as taken, so it is not started again; the pasted prompt ends by running
  `collect`.
