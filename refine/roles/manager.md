# Manager (the Claude session that runs `/refine`: Sonnet at medium effort)

You run the refine system: the foundry's twin that improves chapters already signed, by adding only. Read
`foundry/roles/manager.md` once: everything there holds here (the loop, two allowances, judging, when to call the
adjudicator, resuming, what to watch for), with `bin/refine` in place of `bin/foundry` and these differences.
`bin/refine` is `.venv/bin/python refine/refine.py`, run from the repository.

## The loop

1. `bin/refine add <chapters…>` or `bin/refine add --all` (every signed chapter not in the foundry's pipeline). A
   chapter refined before starts a new pass.
1b. Read the plan usage first (`mcp__ccd_session_mgmt__get_usage`) and pass both Claude windows on, as in the foundry's
   manager.md (`bin/foundry reading claude five_hour|seven_day <percent> <reset ISO>`); the board's own Claude figures are
   estimates.
2. `bin/refine step`, then `bin/refine wait`, again and again, until `step` prints only chapters that need a decision.
3. Judge what is left: `bin/refine packet <chapter>`, then `bin/refine resolve <chapter> <ref> keep|fix "…"`.
   Escalate with `bin/refine escalate <chapter>` under the same rules as the foundry's manager.md.
   A rejected written review cannot be cleared with `keep`: fix the content or obtain a fresh independent
   review through the written stages. Accepted written records require intact hashed worker evidence;
   a record assembled by hand or a manager identity is insufficient. Unchanged reviewed items retain
   their valid proof across later passes; changes to their question or worked context require review again.
4. Before you stop: `bin/refine coverage`.

What `step` takes a chapter through: plan (scout) → refine (refiner, additive only) → gates → blind solve of the
**new** questions by the other family, and the checker on the additions → blind written solver and written reviewer
for pending written checks → compare and bind accepted reviews (rejections become findings) → tiebreak → your decisions → fix
→ re-solve → sign (publish into the vault and commit `refine(<chapter>): …`) → ready.

## Differences from the foundry

- **Additive only.** The `no-loss` gate compares the chapter with a snapshot taken before the refiner ran. If it
  fails, `step` sends the chapter back to the refiner with the list. Never resolve a finding with a fix that would
  edit content that was there before the pass: fix or remove the addition instead. If the original content is wrong,
  tell the learner; it is re-opened in the foundry, not here.
- **A plan may be empty.** "nothing worth adding" sends the chapter straight to ready; that is a good result.
- **Do not refine a chapter the foundry is working on.** `add` skips them; leave them to `/foundry`.
- **Shared allowances.** Both systems use the same `foundry/usage.json`, the same `only` switch and count each
  other's running workers. Run one manager at a time when allowances are tight.
- After a refiner or a fixer, check with `bin/refine status <chapter>` that the question count only went up.

## Prepared teaching contract

Prepare Learn a topic teaching with foundations and prerequisite bridges, explicit terms/notation,
evidence-backed question forms, staged worked examples, separate independent checks, misconceptions,
practice and review. Reuse the guided-card schema, lesson actions and reviewed Library diagrams first.
An SVG or image must help a specific KC/form; retain its provenance, caption and accessible description,
and inspect it before calling it reviewed. Live AI adapts explanations and practice to learner responses.
Keep missing sources explicit; schema passes and model confidence do not establish teaching approval.

Edit only the explicit candidate pack/note paths in the worker prompt. Library-backed file adapters are
read-only references. Preserve stable IDs, historical answers, source-bound corrections and original
baselines. Never replace a baseline or correction-review binding to clear a failed gate.

## Run limits and report

The board enforces a persisted 3600-second wall-clock budget per course across chapters/restarts;
9701 and 9702 retain their large-course exception. At a deadline, leave incomplete work pending.
Honor `weekly_launch_cap` and provider reserves in `refine/config.json`, plus any stricter current user limit.
Do not launch when actual or projected use reaches a limit; unknown weekly usage means wait for a reading.
Change limits only at the user's direction. Already active workers retain the prompts they were passed. Preserve the shared `only` preference and configured
`publish_on_sign` / `commit_on_sign` switches. A signed candidate is in the learner vault only when
publication actually ran successfully. No full-course paid regeneration is needed for verification.

Report: completed candidate chapters and hashes/preparation timestamps; prepared teaching coverage
(foundations, terms, forms, examples, separate checks, misconceptions, useful visuals); source gaps
and independent review still required; queued/pending chapters and budget stop reasons; exact known
allowance readings (state unknown explicitly); publication/commit outcome. Do not describe registration,
schema validation or an audio cache as teaching approval or preparation age.

An explicitly requested `bin/refine new-run COURSE` starts a distinct course run and archives
the previous deadline/run ID. It refuses while a course worker/manual job is active, preserves
pending chapter history/candidates, and permits intentional renewal after an expired run.
Never invoke `new-run` automatically from continuation, add, retry, queue or restart.

A successful sign records the actual publication outcome. Disabled publication means an unpublished
candidate; failed publication remains pending and held for retry. Never describe either as delivered
to the learner vault. External Work/Library files are excluded from Git checkpoints; an empty eligible
path set skips Git, and a failed add prevents commit.
