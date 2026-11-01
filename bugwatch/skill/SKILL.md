---
name: bugwatch
description: Run or inspect the STEM Tutor Bugwatch after the Library migration; fix confirmed findings with regression tests and preserve learner history.
argument-hint: "[continue | status | check]"
model: sonnet
effort: medium
---

Model tiers: use `gpt-6.1-sol` for the hardest coordination/review,
`gpt-6.1-terra` for medium work, and `gpt-6-luna` for simple inventory tasks.
Claude Haiku worker slots use `claude-haiku-5-5`. Preserve provider choices
and usage limits; escalate only when task difficulty warrants it.


Repository: `{REPO}`. Run commands from there. Read `../AGENTS.md`,
`bugwatch/README.md` and `bugwatch/SCOPE.md` before acting.

- `status`: run `.venv/bin/python bugwatch/bugs.py --unseen` and `--check`; summarize open findings. Do not change logs or content.
- `check`: run `bash bugwatch/check.sh tests/test_bugwatch_sandbox.py tests/test_consolidate_question_media.py tests/test_library_refs.py tests/test_topicals.py tests/test_extraction.py -q`. Report actual results, not content approval.
- Default or `continue`: follow the Claude fixer loop in the README. Read each finding, reproduce in a disposable sandbox, add a failing regression, fix the narrow cause and run affected checks. Work highest impact first. Preserve the separate writer ownership of BUGS.md and FIXES.md. Never alter learner events, review baselines or original Library resources to make a test pass.

Use `src/tutorlib/` for engine changes. The plugin path is a distribution adapter.
Use `tests/library_assets.py` for real learning inputs. `bugwatch/sandbox.sh`
copies current reviewed content and dependencies; it does not regenerate courses.
Do not start Foundry, Refine, extraction workers, real AI app calls or bulk
generation merely to investigate a bug. Use fake providers in tests. Inspect
the user's weekly usage before launching authorized model work; preserve at
least 25% remaining and leave review/repair headroom. When usage cannot be
verified, report that limitation and continue deterministic checks only.

For parallel spotting, assign independent bounded areas at the cheapest capable
model/effort and at most three hunters alongside the coordinator. Use a lower
model for deterministic duplicate inventories. Escalate reasoning only for
grading, answer protection, persistence or a proved difficult defect. Never
repeat the full suite per hunter. Keep findings concise and source-based.

Do not commit, publish or merge unless the current user request authorizes it.
Keep unresolved content and production-judge limitations visible.


## Stop repeated failures

Before launching paid work, run the repository's `bin/foundry doctor`. Honor the shared 70%-used launch cap and at least 25% Codex reserve; unknown readings stop launches. Treat a paused worker guard as a stop, not a request to change provider or retry through another command.

Classify the blocker first: protected PDF/source damage requires source-bound independent correction review; incomplete forms require every reviewed inventory entry; missing visuals require verified files bound to the relevant card; written checks require independent solving and review. Never fill content with placeholders or invent symbols.

After two failures for a role in the same pass/job, preserve candidate work and report the blocker. Never automatically call unstick, add a new pass to bypass the guard, renew a course budget, or overwrite a baseline/review record. Clear failures only after explicit operator direction, with a recorded reason. Verify the actual learner path before claiming the material is active or ready.
