# The foundry on two allowances

Asked by the learner on 2026-10-02: the foundry should use the Claude and the Codex usage limits together, split
between them so that both run out at the same time, adapting as it goes because either may start with less left.
Any model may do any job (Opus at its lowest effort can stand in for Codex); each job should get the least model that
gives consistent output; the Codex tiers in use were more than the jobs needed.

## What was measured first

- **Codex** (`codex app-server`, method `account/rateLimits/read`: no model call, exact): a five-hour window and a
  weekly one, each with a percentage used and a reset time. On 2026-10-02 21:22: 29% and 84%.
- **Claude**: no command reports the limits. Two sources exist. Claude Code keeps what it last fetched in
  `~/.claude.json` (`cachedUsageUtilization`, refreshed when a session starts): 72% of the week at 21:04, and no
  five-hour cap active. Every headless run prints a `rate_limit_event` with the fraction used, and a result with
  its cost in dollars: 77% at 21:45.
- **Past Codex jobs** (27 in `~/.codex/sessions`): a draft at `gpt-6-sol` medium took 3 to 8 minutes and about 4% of
  the five-hour window (about 0.5% of the week); a tiebreak about 1%; a fix under 1%.
- **A headless Claude worker** needs `claude -p` with `--safe-mode --disable-slash-commands --strict-mcp-config
  --setting-sources ""`: its fixed overhead is then about 3,000 tokens, where a subagent of a session with the
  learner's plugins carried far more. `--permission-mode acceptEdits` with `--allowedTools "Bash(.venv/bin/python *)"`
  lets it edit files and run the project's Python, which is what Codex's `workspace-write` sandbox allows.

## Design

**One launcher for every role.** `foundry run <role> <chapter>` starts a detached headless worker for any role
(drafter, fixer, tiebreak, solver, checker, adjudicator) on either allowance and collects it when it exits. The
manager no longer launches subagents: solvers and the checker are headless too (`foundry dispatch`), so they finish
even if the manager's session ends.

**Where a job goes** (`foundry/router.py`, asked again before every job):

1. An allowance is *open* when every one of its windows has room (after `reserve`, and after the nominal cost of the
   jobs already running on it) and it has a free slot (`max_parallel`).
2. Among open allowances the job goes to the one with the most of its longest window left **per hour until that
   window resets**. With equal reset times this is simply "the one with more left", which levels the two and then
   keeps them level, so they run out together. When one resets sooner, what would be lost at its reset is used
   first.
3. **A different AI family checks what the maker wrote.** The allowance that drafts a chapter is its *maker*. The
   blind solver and the tiebreak must run on the other one. If that one is closed, the chapter waits for it.
   Fixer, checker and adjudicator go wherever rule 2 says.

A tiebreak from the checking family, at a stronger tier than the solver, closes the common case (the solver slipped)
with two families in agreement; the old layout had Codex confirming Codex's own key.

**Which model** (`ladders` in `foundry/config.json`): each role has, per allowance, a ladder of `[model, effort]`
rungs, cheapest first. A job starts on the lowest rung that has not failed twice running. A chapter's retry after
its own failed job goes one rung up at once. A failure is a worker that exits badly, writes no output, or leaves the
gates red; a usage limit is not a failure of the tier and closes the allowance instead. So the least sufficient
model for each role is found from results, not guessed.

First rungs: drafter `opus low` / `gpt-6-sol low`; tiebreak `sonnet low` / `gpt-6-sol low`; solver, fixer `haiku` /
`gpt-6-luna low`; checker `haiku` / `gpt-6-luna medium`; adjudicator `opus medium` / `gpt-6-astra medium`.

**Reading the allowances** (`router.usage`): Codex is asked each time (kept for a minute). Claude is the newer of
Claude Code's cache and the last worker's event, plus what our own workers have cost since, at a rate (percent per
dollar) learned from successive readings. The notes are in `foundry/usage.json` (not in git).

**Fewer manager turns.** `foundry step` does everything that needs no judgement for every chapter: launches what
can run, compares finished solves, signs what is green, and says what needs a decision. `foundry usage` shows both
allowances and where the next job would go.

## Not done

- An unattended loop with no manager. The manager (Sonnet, medium effort) still judges the simple cases and calls
  the adjudicator for the rest.
- Reading the Claude limits from Anthropic's servers directly: there is no documented way.
- Changing which models the tutor app itself uses.
