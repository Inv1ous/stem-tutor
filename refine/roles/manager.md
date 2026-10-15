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
4. Before you stop: `bin/refine coverage`.

What `step` takes a chapter through: plan (scout) → refine (refiner, additive only) → gates → blind solve of the
**new** questions by the other family, and the checker on the additions → compare → tiebreak → your decisions → fix
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
