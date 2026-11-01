---
name: extract
description: Manage resumable PDF question and notes-diagram extraction for STEM Tutor. Use for /extract, extract PDFs, TQ extraction, source diagrams, extraction board, or continue extraction.
argument-hint: "[course | job | status] [questions|diagrams|both] [claude|codex|both]"
model: sonnet
effort: medium
---

Manage extraction from `{REPO}` using `bin/extract`; read `extraction/README.md`.
TQ means topical questions. Jobs default to Claude and both scopes. Honor explicit
provider/scope requests; never change Foundry/Refine's global `only` preference.

For status use `bin/extract board`. Resume with `bin/extract resume JOB`, then
inspect persisted inventory, plan and pending findings. For a new course choose a
fresh descriptive job ID, run `new JOB --course COURSE --provider PROVIDER --scope
SCOPE`, then `inventory JOB` and `plan JOB`. Inventory and validation are free.
For a selected PDF add exact `--source asset:ID` (or canonical path); use `--pages
START-END` for slices. Each paid worker batch permits at most 100 selected pages.
Split larger course inventories into fresh source/page jobs without asking the
user to choose routine batch boundaries. After pending findings, preserve the
prior candidate and use `run --retry extract` to repair it, then rerun review.

Before each `run JOB`, obtain an actual current weekly remaining reading for its
selected provider and pass `--weekly-remaining PERCENT`; require above 25% reserve.
Never guess an unavailable reading or silently switch providers. `run` launches
one real worker and returns; resume/check its state until it finishes. Run again
to launch the separate reviewer, then `check JOB`. Do not launch subagents for
worker jobs. Keep provider and family limitation visible. In both mode the maker
is Claude and its separate reviewer is Codex. Single provider uses a separate
blind reviewer task and records same_family.

Report complete reviewed candidates, pending/OCR/unsupported cases and visual
inspection gaps plainly. `register JOB` is an explicit publication-boundary action
that stores reviewed media immutably in Library, preserving source provenance.
It does not imply teaching approval. `publish JOB --topical-batch PATH` separately
uses build/topicals.py's supported official-key/review gates. Never publish or
register just because a worker exited zero; require check results and the user's
requested publication scope. Registration/publishing is not part of extraction
unless the user requested it. A request to extract/import resources into the
Library already authorizes registration after checks and independent review;
do not ask for another confirmation. Inventory-only, preview-only and status
requests remain read-only. A course/topical release remains a separate scope.


## Stop repeated failures

Before launching paid work, run the repository's `bin/foundry doctor`. Honor the shared 70%-used launch cap and at least 25% Codex reserve; unknown readings stop launches. Treat a paused worker guard as a stop, not a request to change provider or retry through another command.

Classify the blocker first: protected PDF/source damage requires source-bound independent correction review; incomplete forms require every reviewed inventory entry; missing visuals require verified files bound to the relevant card; written checks require independent solving and review. Never fill content with placeholders or invent symbols.

After two failures for a role in the same pass/job, preserve candidate work and report the blocker. Never automatically call unstick, add a new pass to bypass the guard, renew a course budget, or overwrite a baseline/review record. Clear failures only after explicit operator direction, with a recorded reason. Verify the actual learner path before claiming the material is active or ready.
