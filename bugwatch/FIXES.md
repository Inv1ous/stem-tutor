# FIXES — written by Claude only, append-only

One line per event: `- HH:MM B-nnn STATUS · detail`. Statuses: `CONFIRMED`, `FIXED` (detail: commit · test id),
`REJECTED`, `DUPLICATE of B-nnn`, `DEFERRED`, `NEEDS-INFO` (a question for Codex). Also `- HH:MM LAST-READ B-nnn` after
each pass through `codex/BUGS.md`, and `- HH:MM SESSION-END · …` at the end. Full rules: `README.md`.

Codex: read this before every sweep. Don't re-report anything marked FIXED, REJECTED, DUPLICATE or DEFERRED. When a fix
lands, try to break it and log `VERIFIED` or `REOPEN`. Answer `NEEDS-INFO` questions with a `REPLY`.

<!-- ↓↓↓ append below this line ↓↓↓ -->

