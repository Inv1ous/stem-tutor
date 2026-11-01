# Bug watch: Claude fixes, Codex spots

Two AI agents work on the same repository at the same time.

After the Library migration, start with `bugwatch/SCOPE.md` and the workspace
contract in `../AGENTS.md`. Canonical engine source is `src/tutorlib/`; the plugin
path is an adapter. `sandbox.sh` now copies the actual CURRENT release, topical
bank and verified Library dependency closure into a disposable vault. It does
not publish authoring drafts or modify registered plan bytes. Its temporary-vault
guard blocks writes beside the learner's real Almanac.

Claude entrypoint: `/bugwatch` runs the existing fixer loop; `/bugwatch status`
reads the board; `/bugwatch check` runs bounded migration/teaching regressions.
The installed skill points back to this repository. Spotters continue to use
the separate prompt below. Reading real source assets is allowed; testing must
never write to the real Library or learner records.

- **Codex (spotter)** reads the code, runs things in a scratch sandbox, and reports possible bugs as it finds them.
- **Claude (fixer)** reads those reports, confirms each one, fixes it with a test, and records what happened.

They talk through two append-only logs. **Each file has exactly one writer**, so neither agent can overwrite the other.

| File | Writer | Purpose |
|---|---|---|
| `codex/BUGS.md` | Codex only | Findings, sweep log, verification of fixes, replies to questions |
| `FIXES.md` | Claude only | Verdict and status for every finding |
| `SCOPE.md` | Claude (read-only for Codex) | Code map, how to run things, what to attack, what is by design |
| `CODEX_PROMPT.md` | human | The instruction to paste into Codex |
| `check.sh` | – | Runs the test suite without writing anything into the repo |
| `sandbox.sh` | – | Builds a scratch copy of the tutor vault in `/tmp` |
| `bugs.py` | – | Live table of every finding and its status (`--watch` keeps it on screen; also `--all`, `--unseen`, `--check`) |

## How to start (human)

1. **Claude session:** start it in the repo and say:
   `Read bugwatch/README.md and bugwatch/SCOPE.md, then run the bug-fix loop.`
2. **Codex session:** start Codex **inside `bugwatch/codex/`** with the workspace-write sandbox, so the only place it can
   write (besides `/tmp`) is `BUGS.md`'s folder:

   ```bash
   cd "/Users/sora/Miscellaneous/02 Education/~~ AI Workflow/stem-tutor/bugwatch/codex"
   codex --sandbox workspace-write --ask-for-approval never
   ```
   (flag names as in the Codex CLI docs; run `codex --help` if your version differs). Then paste `CODEX_PROMPT.md`.
3. **Watch progress** in a third terminal (works from any folder; it needs nothing but Python 3):
   ```bash
   python3 "/Users/sora/Miscellaneous/02 Education/~~ AI Workflow/stem-tutor/bugwatch/bugs.py" --watch
   ```

## Entry formats

### Codex → `codex/BUGS.md`

A finding is a level-3 heading plus fields. IDs run `B-001`, `B-002`, … (take the next free number).

```
### B-014 · P1 · session.py · answer() drops the confidence rating on comma answers
- **Found:** 14:07 · **Method:** ran | read | inferred · **Confidence:** high | medium | low
- **Where:** `plugin/stem-tutor/skills/tutor/scripts/tutorlib/session.py` · `Tutor.answer` · "results.append(self._record("
- **Repro:** exact commands or a snippet a stranger can paste (say which sandbox env it needs)
- **Expected:** what should happen
- **Actual:** what happens, with the real output
- **Impact:** who is hurt and how (wrong mark, lost notes, stuck screen…)
- **Suggested fix:** optional, at most two lines
```

Everything else is a one-line log entry that starts `- YYYY-MM-DD HH:MM VERB` in Hong Kong time:

```
- 2026-11-01 14:05 SWEEP · grade.py + units.py · ran check.sh, 40 property probes · findings: B-014 B-015   (or: clean)
- 2026-11-01 14:50 VERIFIED B-014 · tried 6 comma variants, all fine
- 2026-11-01 14:52 REOPEN B-014 · still splits on ';' — repro: <command>
- 2026-11-01 14:44 REPLY B-011 · answer to Claude's question
```

Codex may close its own checked findings in `codex/BUGS.md`: `VERIFIED B-nnn` closes a fixed finding after its regression and break-check pass, and `REJECTED B-nnn` closes a report disproved by reproduction. `REOPEN B-nnn` reopens either result. Claude's separate `FIXES.md` workflow remains unchanged.

Codex may also close its own quality-of-life ideas in `codex/BUGS.md` with `DONE Q-nnn · proof` or `DECLINED Q-nnn · reason`. Record `VERIFIED Q-nnn · proof` after fresh behavior checks, or `REJECTED Q-nnn · reason` after disproving the idea. The board uses the newest dated QOL verdict across `BUGS.md` and Claude-owned `FIXES.md`, and includes Codex's QOL terminal lines in latest activity.

**Priorities:** **P0** wrong grading, answer leak before an attempt, lost or corrupted progress or notes, crash on a
normal path, writing outside the vault. **P1** wrong behaviour on a normal path. **P2** edge-case crash, UX trap, an action
slower than about a second, guide text the code doesn't honour. **P3** minor.

### Claude → `FIXES.md`

One line per event, `- YYYY-MM-DD HH:MM B-nnn STATUS · detail` in Hong Kong time:

| Status | Meaning |
|---|---|
| `CONFIRMED` | Reproduced; fix in progress |
| `FIXED` | Fixed and tested; detail gives the commit and the test id |
| `REJECTED` | Not a bug (reason given) |
| `DUPLICATE` | Same as an earlier finding (`DUPLICATE of B-003`) |
| `DEFERRED` | Real but not now (content work, feature, or needs the user) |
| `NEEDS-INFO` | Question for Codex; Codex answers with a `REPLY` |

Claude also appends `- YYYY-MM-DD HH:MM LAST-READ B-nnn` after each pass through `BUGS.md`, so `bugs.py --unseen` shows only new ones. Existing `HH:MM` entries remain valid and are treated as older than dated entries; their calendar order cannot be reconstructed, so new entries must include the date.

## Claude's loop

1. Run `bugs.py --unseen`. Read each new entry in `codex/BUGS.md` in full.
2. Work **P0 first**. Reproduce using Codex's repro. Not reproducible → `NEEDS-INFO` or `REJECTED`.
3. Write a failing test, fix, run the full suite (`bash bugwatch/check.sh`), then commit
   (`fix(B-014): short description`, one bug per commit unless they share a cause).
4. Append the `FIXED` line with the commit hash and test id. Then `LAST-READ`.
5. Between fixes, check the log again. Codex may be several findings ahead.
6. Never edit `codex/BUGS.md`. Commit `bugwatch/` logs only at the end of the session.

## Rules for both

- Timestamps are Hong Kong time, from `date +%H:%M`.
- Claude edits files continuously, so **line numbers drift**. Cite file + function + a quoted line, and re-read just before reporting.
- Spotter runs the app or engine only through `sandbox.sh`, **never against the real vault** (`../STEM Tutor`).
- Tests may fail transiently while Claude is mid-edit: re-run once, and check `git status` before reporting.
- Reports are for behaviour that is wrong or could plausibly go wrong. No style, naming or refactor suggestions.

## Stopping

The human says stop, or Codex logs `SWEEP … clean` three times in a row across different areas. Claude then writes a
short summary at the bottom of `FIXES.md` (`- HH:MM SESSION-END · fixed N, rejected N, deferred N`), updates
`CHANGELOG.md`, and commits.

## Solo (overnight) watch: Codex spots now, Claude fixes later

When Claude's allowance is spent, Codex runs alone. Start a NEW Codex thread whose folder is the repo (`stem-tutor`, not `~~ AI Workflow`: only then does Codex load `.codex/agents/bug-hunter.toml`), then paste:
`Read bugwatch/CODEX_SOLO.md and follow it exactly.`
Hunters post each bug (visual ones too, with a screenshot in `codex/shots/`) and each quality-of-life idea the moment they prove it, through `post.py`; watch them arrive with `python3 bugwatch/bugs.py --watch`. After the reset, start Claude in the repo and say:
`Read bugwatch/README.md and bugwatch/SCOPE.md, then run the bug-fix loop on everything unseen in codex/BUGS.md; then triage codex/QOL.md.`

Model tiers: use `gpt-6.1-sol` for the hardest coordination/review,
`gpt-6.1-terra` for medium work, and `gpt-6-luna` for simple inventory tasks.
Claude Haiku worker slots use `claude-haiku-5-5`. Preserve provider choices
and usage limits; escalate only when task difficulty warrants it.


## Reliability and spending safeguards

Run `bin/foundry doctor` before paid work; it exercises native SVG rendering and imports the PDF/image libraries, rather than only checking package names. Refine and Foundry direct launches also perform this check. Extraction verifies registered PDF hashes before each worker. Bugwatch must use its verified disposable vault and run the same doctor before an AI repair attempt.

The shared paid-worker guard stops a role after two failed results in one pass/job, including timeouts, malformed output and failed gates. Changing model output does not reset this allowance. Inspect saved evidence and fix the root cause before explicitly clearing the guard. `bin/refine unstick CHAPTER "reason"`, `bin/foundry unstick CHAPTER`, or `bin/extract unstick JOB "reason"` archives the decision; never run these automatically. Provider preferences, review gates and course deadlines still apply. Repeated Refine failures preserve candidate work and leave the chapter pending.

Existing question text containing PDF debris is a source-repair task, not a lesson-authoring task. Refine blocks lessons-scope workers before spending on such items. Never infer ×, −, Ω or another symbol solely from a control character: inspect the original PDF/image and bind independent source review to a new revision. Missing guided forms must be authored against the complete reviewed inventory, not filled with placeholders. Every planned lesson visual must be registered, inspected and bound to its teaching card with an accessible description. Written approval remains independent of authoring.

The weekly launch cap is 70% used and Codex reserve is at least 25%. Unknown allowance readings block launches. Do not relax these limits or automatically restart an expired course run. For Bugwatch, compare the current failure with the previous attempt: if inputs and blocker are unchanged, stop instead of asking another model to repeat the same repair. Source gaps and disputed content remain visible; tests do not establish teaching approval.
