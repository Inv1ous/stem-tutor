# Fixer (refine)

Read `foundry/roles/fixer.md` and follow it, with these differences:

- The fixes concern what this refine pass added (`build/work/refine/<subtopic>.additions.md`): new items with
  `-r` ids, new note lines, new card lines, new diagrams. You may edit those freely.
- Everything that was there before the pass is protected by the **no-loss** gate (see `refine/roles/refiner.md`):
  never edit an existing item, line, card field or entry. If a fix would need that, do not make it; put it in
  `not_done` with why.
- Never re-run the chapter's generator script (`build/work/gen/…`): edit the pack JSON directly.
- After the three gates, also run `.venv/bin/python refine/refine.py gates <subtopic>` and resolve authoring failures.
  Pending independent written reviews follow the lifecycle in `refine/roles/refiner.md`: collection defers them,
  while signing requires current accepted records. Report pending reviews in `not_done`.
- Use `review_rule` only for an implemented identifier accepted by `build/teach_cards.py`; express prose marking
  criteria in rubric points and review concerns in `not_done`. Preserve existing valid rules.

## Lessons scope

Preserve subject-note bytes and every existing assessment item, including stems, options, answers and rubrics.
Fix only additions to teaching cards, worked examples, checks, misconceptions and card-bound diagrams; do not add
unrelated assessment-bank questions. Report suspected source or pre-existing problems in `not_done` for an
independent correction workflow; never generate `<subtopic>.corrections.json` in lessons scope. Edit the exact
`candidate_teach` path in the prompt and merge with its explicit `--draft` and `--pack` command. Use only verified
canonical Library paths for source graphics, with provenance and accessible card descriptions; never invent embeds
or paths. If a graphic cannot be verified or bound, report it in `not_done`.


Before a paid repair attempt, run the shared doctor and identify which exact fields may be changed. Distinguish inherited source damage, missing authored forms, missing visual bindings and pending independent review. Stop on protected source damage; do not attempt lesson-only rewrites of existing assessment questions. Validate every required form and every planned visual binding before finishing. If the same blocker survives two attempts, preserve the candidate and report the unresolved cause; do not automatically clear the failure allowance or reset a course run.

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
