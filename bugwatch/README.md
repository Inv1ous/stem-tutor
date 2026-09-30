# Bug watch: Claude fixes, Codex spots

Two AI agents work on the same repository at the same time.

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
| `bugs.py` | – | Live table of every finding and its status (`--watch` to keep it on screen) |

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
3. **Watch progress** in a third terminal:
   ```bash
   .venv/bin/python bugwatch/bugs.py --watch
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

Everything else is a one-line log entry that starts `- HH:MM VERB`:

```
- 14:05 SWEEP · grade.py + units.py · ran check.sh, 40 property probes · findings: B-014 B-015   (or: clean)
- 14:50 VERIFIED B-014 · tried 6 comma variants, all fine
- 14:52 REOPEN B-014 · still splits on ';' — repro: <command>
- 14:44 REPLY B-011 · answer to Claude's question
```

**Priorities:** **P0** wrong grading, answer leak before an attempt, lost or corrupted progress or notes, crash on a
normal path, writing outside the vault. **P1** wrong behaviour on a normal path. **P2** edge-case crash, UX trap, an action
slower than about a second, guide text the code doesn't honour. **P3** minor.

### Claude → `FIXES.md`

One line per event, `- HH:MM B-nnn STATUS · detail`:

| Status | Meaning |
|---|---|
| `CONFIRMED` | Reproduced; fix in progress |
| `FIXED` | Fixed and tested; detail gives the commit and the test id |
| `REJECTED` | Not a bug (reason given) |
| `DUPLICATE` | Same as an earlier finding (`DUPLICATE of B-003`) |
| `DEFERRED` | Real but not now (content work, feature, or needs the user) |
| `NEEDS-INFO` | Question for Codex; Codex answers with a `REPLY` |

Claude also appends `- HH:MM LAST-READ B-nnn` after each pass through `BUGS.md`, so `bugs.py --unseen` shows only new ones.

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
