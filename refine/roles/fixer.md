# Fixer (refine)

Read `foundry/roles/fixer.md` and follow it, with these differences:

- The fixes concern what this refine pass added (`build/work/refine/<subtopic>.additions.md`): new items with
  `-r` ids, new note lines, new card lines, new diagrams. You may edit those freely.
- Everything that was there before the pass is protected by the **no-loss** gate (see `refine/roles/refiner.md`):
  never edit an existing item, line, card field or entry. If a fix would need that, do not make it; put it in
  `not_done` with why.
- Never re-run the chapter's generator script (`build/work/gen/…`): edit the pack JSON directly.
- After the three gates, also run `.venv/bin/python refine/refine.py gates <subtopic>` until it says `"ok": true`.
