# The refine system

A copy of the content foundry that, instead of building chapters, **refines chapters that already exist**. For the
chapters you name (or every signed chapter), it adds what is missing: diagrams, more questions, clarifications in the
lesson note and teaching cards, and learning features the pack format supports. It never removes or rewrites what
is there: a `no-loss` gate proves it before anything reaches your vault.

It runs exactly like the foundry (`foundry/README.md`): headless workers on your Claude and Codex allowances, chosen
by the same router (`foundry/router.py`, imported, not copied), the blind solve by the other AI family, tiebreak,
adjudicator, fixer, and signing that publishes into the vault and commits. Only the use differs.

## Stages

| Stage | Who | What happens | Moves on when |
|---|---|---|---|
| `plan` | **scout** | Reads the pack, note, cards, gates, bundle, your sources library and (if needed) official web sources; writes `build/work/refine/<chapter>.plan.json`: a short prioritised list `{kind: diagram/figure/questions/clarification/feature/source_gap, where, why, source?}`. Kept within the caps: ≤3 diagrams, ≤3 figures cropped from your PDFs, ≤8 new questions, ≤5 note/card additions | A readable plan. An empty plan ("nothing worth adding") goes straight to `ready` |
| `refine` | **refiner** | A snapshot of the chapter is taken first. Then exactly the plan, by appending only: new items `<chapter>-r01…`, new note lines and sections, new card lines, new diagrams (rendered with `build/diagrams.py`) | The gates are green |
| gates | (no tokens) | The foundry's gates (validator, note lint, syllabus, links + diagrams) **plus no-loss** (below) **plus the plan check** (new items are `-rNN`, what was planned exists, caps hold, diagrams rendered) | A failure sends the chapter back to the refiner, one tier up, with the list |
| `solve` | **solver** (the other family, blind) + **checker** | Only the **new** questions are stripped and solved; the checker reads only the additions (`build/work/refine/<chapter>.additions.md`) | Both reported |
| `tiebreak` | **tiebreak** (blind) | The disputed new questions only | Compared |
| `check` | | Waiting for the checker | Findings in |
| `adjudicate` | manager / **adjudicator** | Open disputes and findings, as in the foundry | Every item decided |
| `fix` → `recheck` | **fixer**, then the solver | Fixes to the additions only; the changed questions are solved again | Clean |
| `sign` | manager | Gates again, then publish into the vault and commit `refine(<chapter>): 2 questions, 1 diagrams, 6 note lines` | |
| `ready` | | `refined: N`, `last_refined` and what was added are kept, so `board` and `coverage` show when each chapter was last refined. `add` again starts a new pass | |

## Roles and their ladders (`refine/config.json`)

| Role | On Claude, first rung → next | On Codex, first rung → next | Web |
|---|---|---|---|
| **Scout** | Sonnet low → medium | `gpt-6-sol` low → medium | yes |
| **Refiner** (the maker) | Opus low → medium | `gpt-6-sol` medium → `gpt-6-astra` medium | yes |
| **Solver** | Haiku → Sonnet low | `gpt-6-sol` low → medium | |
| **Checker** | Haiku → Sonnet low | `gpt-6-sol` low → medium | |
| **Tiebreak** | Sonnet low → medium | `gpt-6-sol` low → medium | |
| **Fixer** | Haiku → Sonnet low | `gpt-6-luna` low → `gpt-6-sol` low | |
| **Adjudicator** | Opus medium → high | `gpt-6-astra` medium → high | |
| **Manager** | Sonnet medium (`/refine`) | | |

Each role starts on its first rung; a chapter's retry after its own failed job goes one rung up; a rung that fails a
role twice running is not used again (the router's notes are shared with the foundry, so `solver/codex` learned in
one system holds in the other). The allowance that the **refiner** ran on is the chapter's maker for this pass: its
new questions are solved and tiebroken by the other family. `only codex|claude|off` is the foundry's own switch (one
setting for both systems); a chapter signed with its own family checking it is marked `same_family`.

## The safety guarantee: no-loss

Before the refiner first runs in a pass, the chapter (pack and note) is saved to
`build/work/refine/<chapter>.snapshot.json` (not committed). A retry is compared with that same snapshot. The gate
fails, listing each violation, when:

- an existing item is gone, or its `id`, `kind`, `stem`, `options`, `answer`, `kcs`, `source`, `template`, `image`,
  `tier`, `marks`, `rubric`, `scheme` or `distractors` differ in any way (even an empty `options` must stay empty), or
  any other field that had a value (`explanation`, `hints`, …) changed. A field that was empty may be filled (an
  explanation an extra lacked);
- an existing misconception, worked example, flashcard or diagram is gone or changed;
- a top-level field of the pack (`subtopic`, `note`, `outline`, …) changed (`diagrams_skipped` may go once a diagram
  is drawn);
- a teaching card or one of its fields is gone, or a text field lost a line (lines may be added);
- a line of the lesson note is gone or edited (lines may be inserted anywhere; the originals stay in order).

## How to run it

```bash
bin/refine add 9702-2.1 9702-2.2     # or: bin/refine add --all   (signed chapters not in the foundry)
bin/refine step                       # launch, compare, sign: whatever needs no judgement
bin/refine wait                       # until the workers finish; then step again
bin/refine board                      # stage, gates, passes, last refined
bin/refine coverage                   # what was refined when and how much; chapters still lacking diagrams
bin/refine watch                      # live screen
```

Other commands mirror the foundry's: `next`, `usage`, `only`, `run <role> <chapter> [--on claude|codex]`,
`dispatch`, `queue <role> <chapters…>`, `packet`, `resolve`, `escalate`, `gates`, `additions`, `sign`, `status`.

**Read aloud.** A refine pass that is signed starts the same background pre-generation as the foundry's sign-off
(`foundry/pregen.py`, log in `refine/logs/`), so the new questions, cards and note lines have audio ready; lines
already made are kept. `bin/refine tts <chapters…|--all> [--voice V] [--speed S]` makes audio by hand (a full run takes a
while and costs only local CPU, no allowance) and `bin/refine tts status` shows per chapter lines, audio, missing and
gaps. `refine coverage` lists chapters with read-aloud gaps (not a gate: add a `speech` field next to the line). See
the foundry README, "Read-aloud audio".

In practice, type **`/refine`** in a Claude session (`/refine 9702-2.1`, `/refine all`, `/refine status`). Install
the skill once (it writes `~/.claude/skills/refine/SKILL.md`, as `foundry install-skill` does for `/foundry`):

```bash
bin/refine install-skill
```

## Relation to the foundry

- **One pair of allowances.** Both systems read and write `foundry/usage.json` under the same lock, so the router
  balances one Claude and one Codex allowance across both. The refine system counts the foundry's running workers
  as well as its own against `max_parallel`.
- **Separate boards.** Refine state is in `refine/state/`, logs in `refine/logs/`, work files in
  `build/work/refine/`, blind files `build/work/blind/<chapter>.refine.*.json`. It never writes `foundry/state/` or the
  hold list.
- **Never both at once.** `add` skips a chapter the foundry holds or has on its board below `ready`. A refined
  chapter stays in the vault while it is refined (holding it back would take it out of the vault until signed).

## Sources library

The scout and the refiner read the learner's own PDFs (textbooks, school notes, revision guides) under
`sources/library/` through `build/library.py`:

```
.venv/bin/python build/library.py for <chapter>              passages matched to this chapter
.venv/bin/python build/library.py search "<terms>" [--folder X]
.venv/bin/python build/library.py text <path> --pages a-b
.venv/bin/python build/library.py tree
```

They use the learner's terms and methods where these agree with the syllabus, and paraphrase: nothing is copied.

## Figures from your PDFs

The scout may plan up to 3 `figure` entries (`{pdf, page, box, caption, kc, why}`, counted apart from diagrams) when a
page of your library has a clearly useful figure for the chapter: one that shows what a syllabus point is about, is
legible on its own and is something the diagram types cannot draw (apparatus, molecular models, mechanisms, real
graphs). It looks at the page first (`library.py figures`, `page`, then the Read tool on the PNG); no figure beats a
poor one. The refiner crops each with `library.py crop`, looks at the result, and embeds it with its source line and
one line on what to notice. Gates: the foundry's `figures` check (file, sidecar, checksum, source caption within 2
lines), at most 3 new figures, every planned figure embedded, each new embed backed by a file and a sidecar. A figure
is only ever added, never in place of a diagram (the no-loss rule). The PNGs live in `build/out/assets/`, which git
ignores: they are copied to your vault and never committed. See `sources/library/README.md`.

## Web

`"web": ["scout", "refiner"]` in `refine/config.json` lists the roles allowed to search the internet, for what the
library lacks and only from official sources (exam boards, examiner reports, IOP, RSC, universities). For those
roles a Claude worker gets `WebSearch,WebFetch` added to `--tools` and `--allowedTools`; a Codex worker gets the
top-level `--search` flag (`codex --search exec …`: live web search, checked against `codex --help`; `codex exec`
itself has no such flag). The foundry has no such setting yet.

## Files

| Path | What |
|---|---|
| `refine/refine.py` | Board, gates (no-loss, plan), launcher, CLI; imports the foundry's helpers and router |
| `refine/config.json` | Ladders, weights, caps (diagrams, figures, questions, additions), web roles, parallel slots, reserve |
| `refine/roles/*.md` | Scout and refiner in full; solver, checker, tiebreak, fixer, adjudicator as short adaptations of the foundry's |
| `refine/schemas/*.json` | Reports the scout, refiner, fixer and tiebreak return |
| `refine/skill/SKILL.md` | `/refine` |
| `refine/state/<chapter>.json` | Each chapter's stage, pass, plan summary, maker, disputes, findings, refined count and date |
| `bin/refine` | Runs it from any folder |
