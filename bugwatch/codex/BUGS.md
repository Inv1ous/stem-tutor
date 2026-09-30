# BUGS — written by Codex only, append-only

Claude reads this file continuously and answers in `../FIXES.md`. Never edit or delete existing lines; only append at
the very end, with a quoted heredoc (`cat >> BUGS.md <<'EOF' … EOF`). Full rules: `../README.md`.

## Finding format (one block per bug; take the next free `B-nnn`)

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

## Log lines (everything else; one line each, `- HH:MM VERB …`, Hong Kong time)

```
- 14:05 SWEEP · grade.py + units.py · ran check.sh and 40 probes · findings: B-014 B-015     (or: clean)
- 14:50 VERIFIED B-014 · tried 6 comma variants, all fine
- 14:52 REOPEN B-014 · still splits on ';' — repro: <command>
- 14:44 REPLY B-011 · answer to Claude's question
```

Priorities: **P0** wrong grading, answer leak, lost/corrupted progress or notes, crash on a normal path, writes outside
the vault · **P1** wrong behaviour on a normal path · **P2** edge-case crash, UX trap, action slower than ~1 s, guide
mismatch · **P3** minor.

<!-- ↓↓↓ append below this line — do not edit anything above ↓↓↓ -->

