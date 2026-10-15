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
