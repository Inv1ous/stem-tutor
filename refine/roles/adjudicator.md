# Adjudicator (refine)

Read `foundry/roles/adjudicator.md` and follow it exactly, with these differences:

- Use `.venv/bin/python refine/refine.py packet <subtopic>` and `.venv/bin/python refine/refine.py resolve <subtopic>
  <id or ref> keep|fix "<text>"` (not `foundry/foundry.py`).
- Every open item concerns what this refine pass added (listed in `build/work/refine/<subtopic>.additions.md`).
  A key written by the refiner has no standing: compute it yourself.
- A fix may change only added content. If the right decision would change content that was there before the pass,
  record `fix` with the instruction "remove the addition <id or line>" instead, and say in one line what the original
  content gets wrong, for the learner to re-open that chapter in the foundry.
