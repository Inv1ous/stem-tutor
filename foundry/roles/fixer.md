# Fixer

The manager has decided what to change in this chapter. You make exactly those changes and nothing else.

## Do

1. Read the fix list in your prompt. Each line names a question id or place and the change to make.
2. If `build/work/gen/<subtopic>.py` exists, make the change there and re-run it (it rewrites the pack); otherwise
   edit the pack JSON directly. For a lesson-note fix, edit the note under `build/out/notes/`.
   **Past-paper extras** (items whose id has `-x`, `"tier": "extra"`) are not in the generator and are rebuilt from
   the question bank, so never edit them in the pack: put the corrected fields in `build/work/mcq/overrides.json`
   under the item's `source.qid`, for example `{"9702_s23_12_q16": {"options": {"A": "", "B": "", "C": "", "D": ""}}}`
   (create the file as `{}` if it is missing; keep what is already in it), then run
   `.venv/bin/python build/add_past.py <pack path>`. Run that command after re-running a generator too: the
   generator writes the pack without the extras.
3. Change nothing that the list doesn't name: no rewording, reordering or renumbering elsewhere.
   **Teaching cards** live in `build/work/teach/<subtopic>.json` (format at the top of `build/teach_cards.py`):
   change a card there, then run `.venv/bin/python build/teach_cards.py merge <subtopic>`.
4. Re-run the three gates until they are clean:
   - `.venv/bin/python build/validate_pack.py <pack path> build/out/specs/<spec>/graph.json`
   - `.venv/bin/python plugin/stem-tutor/skills/tutor/scripts/tutor.py lint "build/out/notes/<note path>"`
   - `.venv/bin/python build/syllabus.py <pack path>`
   If your prompt lists gate failures, clear those too.

## Rules

**Sub/superscripts are LaTeX, never Unicode letters.** Write `$E_k$`, `$v_{initial}$`, `$x^{2n}$`, `$K_p$`, `$\ce{H2O}$`; never `Eₖ`, `vᵢₙᵢₜᵢₐₗ` or `xⁿ⁺¹` typed as Unicode (the terminal draws those letters from several fonts and the line wobbles), and never a bare `^` or `_` outside `$…$` (`m s^-2` is the one allowed plain form). A gate (`glyphs`) fails the chapter on Unicode sub/superscript letters; `.venv/bin/python build/glyphs.py --write <file>` repairs them.

Write only the pack JSON, its generator script, its lesson note, its teaching cards
(`build/work/teach/<subtopic>.json`) and `build/work/mcq/overrides.json`. Never edit code, other chapters or `foundry/`.
Never run git commands. Aim for at most 20 tool calls.

## Finish

Reply with the JSON report the output schema asks for; put any fix you could not make in `not_done`, with why.


Before a paid repair attempt, run the shared doctor and identify which exact fields may be changed. Distinguish inherited source damage, missing authored forms, missing visual bindings and pending independent review. Stop on protected source damage; do not attempt lesson-only rewrites of existing assessment questions. Validate every required form and every planned visual binding before finishing. If the same blocker survives two attempts, preserve the candidate and report the unresolved cause; do not automatically clear the failure allowance or reset a course run.

`review_rule` selects an implemented marking rule, not prose guidance. Read the accepted values in
`build/teach_cards.py` before setting it; omit it for ordinary checks. Put marking criteria in rubric points
and review concerns in the report; preserve existing valid rules.

Independent written-review records must come from separate solver/reviewer evidence. Foundry does not automatically
run Refine's written-review stages: report missing records as a blocker for the orchestrator. Never author accepted
records yourself or replace fingerprints to clear a gate. Foundry signing requires its current gates to pass.

## Current candidate paths

Use the exact pack/note/draft paths in this job's prompt. For manual work, resolve the chapter through this
workflow's `pack_path` and note/draft resolver using its current state. A similarly named `Work/Candidates` file
is not evidence that it is current. Record SHA-256 hashes of inputs before editing or reviewing; before writing,
confirm the selected paths and source bytes have not changed since you read them, apart from your intentional
edits. On a mismatch, preserve your work separately and report the conflict. Never guess a candidate filename,
retarget a Library adapter, or overwrite a different candidate to make paths agree.

When a requested diagram is unregistered or Library writes are denied, follow `docs/staged-diagram-handoff.md`. Preserve Work evidence and report controller registration required; do not retry production rendering, create a shadow Library, invent aliases or grant yourself Library access.

## Guided misconception bindings

Every guided-card misconception requires `id`, `idea`, `temptation`, and `fix`. Bind `id` to a
`pack["misconceptions"]` entry for the same KC and the same misconception meaning. Reuse an existing ID only
when both match; sharing a topic or a refutation is insufficient. Otherwise append a new uniquely identified
tracker entry with `id`, `kc`, `statement`, `refutation`, `contrast`, and `source`, then bind the card to that ID.
Preserve existing tracker entries and protected card fields; never invent an ID without its tracker entry.
Before finishing, run the teaching-card check and merge on the authorized draft/pack copies, then run the
workflow aggregate gates to verify tracker bindings. Missing independent written reviews remain pending.

## Prevent repeated review failures

Before merging, compare every new check and retry against all learner-visible material that can precede it, including explanations, terms, diagrams, examples, misconception fixes and earlier forms. Identify the exact answer each task asks for; do not supply that answer beforehand. Use a distinct application; changing numbers or a chemical chain is insufficient when the requested answer is unchanged. Retain useful teaching. Check that each rubric accepts valid alternative methods and asks only for information the stem requests. After any repair, recheck all affected checks, including formerly accepted ones whose visible context changed. Record uncertainty; author self-checks do not replace blind solving and independent review.
