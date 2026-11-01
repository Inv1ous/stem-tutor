# The refine system

A copy of the content foundry that, instead of building chapters, **refines chapters that already exist**. For the
chapters you name (or every signed chapter), it adds what is missing: diagrams, more questions, clarifications in the
lesson note and teaching cards, and learning features the pack format supports. It never removes or rewrites what
is there: a `no-loss` gate proves it before anything reaches your vault.

It runs exactly like the foundry (`foundry/README.md`): headless workers on your Claude and Codex allowances, chosen
by the same router (`foundry/router.py`, imported, not copied), the blind solve by the other AI family, tiebreak,
adjudicator, fixer, and signing that publishes into the vault and commits. Publication and commits occur only when enabled and successful. The persisted scope controls what may be added.

## Stages

| Stage | Who | What happens | Moves on when |
|---|---|---|---|
| `plan` | **scout** | Reads the pack, note, cards, gates, bundle, your sources library and (if needed) official web sources; writes `build/work/refine/<chapter>.plan.json`: a short prioritised list `{kind: diagram/figure/questions/clarification/feature/source_gap, where, why, source?}`. Kept within the caps: ≤3 diagrams, ≤3 figures cropped from your PDFs, ≤8 new questions, ≤5 note/card additions | A readable plan. An empty plan ("nothing worth adding") goes straight to `ready` |
| `refine` | **refiner** | A snapshot of the chapter is taken first. Then exactly the plan, by appending only: new items `<chapter>-r01…`, new note lines and sections, new card lines, new diagrams (rendered with `build/diagrams.py`) | The gates are green |
| gates | (no tokens) | The foundry's gates (validator, note lint, syllabus, links + diagrams) **plus no-loss** (below) **plus the plan check** (new items are `-rNN`, what was planned exists, caps hold, diagrams rendered) | A failure sends the chapter back to the refiner, one tier up, with the list |
| `solve` | **solver** (the other family, blind) + **checker** | Only the **new** questions are stripped and solved; the checker reads only the additions (`build/work/refine/<chapter>.additions.md`) | Both reported |
| written review | **wsolver**, then **wreviewer** | The solver sees written-check stems only and writes blind solutions; the reviewer compares them with the checks, answers and rubrics. Accepted decisions are bound to review records; rejected or missing decisions become findings. | Pending written checks have decisions and valid bindings |
| `tiebreak` | **tiebreak** (blind) | The disputed new questions only | Compared |
| `check` | | Waiting for the checker | Findings in |
| `adjudicate` | manager / **adjudicator** | Open disputes and findings, as in the foundry | Every item decided |
| `fix` → `recheck` | **fixer**, then the solver | Fixes to the additions only; the changed questions are solved again | Clean |
| `sign` | manager | Gates again, then publish into the vault and commit `refine(<chapter>): 2 questions, 1 diagrams, 6 note lines` | |
| `ready` | | `refined: N`, `last_refined` and what was added are kept, so `board` and `coverage` show when each chapter was last refined. `add` again starts a new pass | |

## Roles and their ladders (`refine/config.json`)

| Role | On Claude, first rung → next | On Codex, first rung → next | Web |
|---|---|---|---|
| **Scout** | Sonnet low → medium | `gpt-6.1-terra` low → medium | yes |
| **Refiner** (the maker) | Opus low → medium | `gpt-6.1-terra` medium → `gpt-6.1-sol` medium | yes |
| **Solver** | Haiku 5.5 → Sonnet low | `gpt-6.1-terra` low → medium | |
| **Checker** | Haiku 5.5 → Sonnet low | `gpt-6.1-terra` low → medium | |
| **Tiebreak** | Sonnet low → medium | `gpt-6.1-terra` low → medium | |
| **Written solver** | Sonnet low → medium | `gpt-6.1-terra` low → medium | |
| **Written reviewer** | Sonnet medium → Opus medium | `gpt-6.1-terra` medium → `gpt-6.1-sol` medium | |
| **Fixer** | Haiku 5.5 → Sonnet low | `gpt-6-luna` low → `gpt-6.1-terra` low | |
| **Adjudicator** | Opus medium → high | `gpt-6.1-sol` medium → high | |
| **Manager** | Sonnet medium (`/refine`) | | |

Each role starts on its first rung; a chapter's retry after its own failed job goes one rung up; a rung that fails a
role twice running is not used again (the router's notes are shared with the foundry, so `solver/codex` learned in
one system holds in the other). The allowance that the **refiner** ran on is the chapter's maker for this pass: its
new questions are solved and tiebroken by the other family. `only codex|claude|off` is the foundry's own switch (one
setting for both systems); a chapter signed with its own family checking it is marked `same_family`.

## Lessons scope

Lessons scope is strictly additive: preserve subject-note bytes and all existing assessment items, including stems,
options, answers and rubrics; do not add unrelated assessment-bank questions. Add teaching cards, worked examples,
checks, misconceptions and card-bound diagrams without changing existing entries. Record suspected source problems
in `not_done` for an independent correction workflow; do not generate corrections files in lessons scope. Edit the
exact `candidate_teach` path in the prompt and merge using its explicit `--draft` and `--pack` command. Use verified
canonical Library paths and accessible descriptions for source graphics; omit and report unverifiable graphics rather
than inventing embeds. These instructions apply to new prompts; active workers retain prompts already passed.

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

The scout and refiner read the learner's catalogued PDFs (textbooks, school notes, revision guides) under
`../STEM Tutor/Library/Courses/<course>/Sources/` through `build/library.py`:

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
poor one. The refiner crops each with `library.py crop` and inspects it. In lessons scope it binds a verified canonical Library
path to a card with provenance and an accessible description; full scope uses the source-captioned note embed. Gates: the foundry's `figures` check (file, sidecar, checksum, source caption within 2
lines for note embeds), at most 3 new figures, and scope-appropriate binding backed by a file and sidecar. A figure
is only ever added, never in place of a diagram (the no-loss rule). PNGs and provenance live in the shared Library;
use the canonical embed returned by the crop command. Historical paths remain catalog aliases.

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
| `refine/schemas/*.json` | Final worker reports, including written solver and reviewer reports; their answers and decisions are separate files |
| `refine/skill/SKILL.md` | `/refine` |
| `refine/state/<chapter>.json` | Each chapter's stage, pass, plan summary, maker, disputes, findings, refined count and date |
| `bin/refine` | Runs it from any folder |

## Run limits and report

The board enforces a persisted 3600-second wall-clock budget per course across chapters/restarts;
9701 and 9702 retain their large-course exception. At a deadline, leave incomplete work pending.
Honor `weekly_launch_cap` and provider reserves in `refine/config.json`, plus any stricter current user limit.
Do not launch when actual or projected use reaches a limit; unknown weekly usage means wait for a reading.
Change limits only at the user's direction. Preserve the shared `only` preference and configured
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

## Model policy (2026-10-30)

Codex tiers are `gpt-6.1-sol` (maximum), `gpt-6.1-terra` (medium), and
`gpt-6-luna` (lowest). The current configuration has ladders for both Claude and Codex; the shared `only` preference governs
which provider may actually run. The blind solver uses another family when available, subject to that preference. Haiku slots explicitly use
`claude-haiku-5-5`. Existing efforts, provider preferences and budgets remain in force.


## Reliability and spending safeguards

Run `bin/foundry doctor` before paid work; it exercises native SVG rendering and imports the PDF/image libraries, rather than only checking package names. Refine and Foundry direct launches also perform this check. Extraction verifies registered PDF hashes before each worker. Bugwatch must use its verified disposable vault and run the same doctor before an AI repair attempt.

The shared paid-worker guard stops a role after two failed results in one pass/job, including timeouts, malformed output and failed gates. Changing model output does not reset this allowance. Inspect saved evidence and fix the root cause before explicitly clearing the guard. `bin/refine unstick CHAPTER "reason"`, `bin/foundry unstick CHAPTER`, or `bin/extract unstick JOB "reason"` archives the decision; never run these automatically. Provider preferences, review gates and course deadlines still apply. Repeated Refine failures preserve candidate work and leave the chapter pending.

Existing question text containing PDF debris is a source-repair task, not a lesson-authoring task. Refine blocks lessons-scope workers before spending on such items. Never infer ×, −, Ω or another symbol solely from a control character: inspect the original PDF/image and bind independent source review to a new revision. Missing guided forms must be authored against the complete reviewed inventory, not filled with placeholders. Every planned lesson visual must be registered, inspected and bound to its teaching card with an accessible description. Written approval remains independent of authoring.

Use the configured weekly launch cap and provider reserves, plus any stricter user limit. Unknown allowance readings block launches. Change limits only at the user's direction; do not automatically restart an expired course run. For Bugwatch, compare the current failure with the previous attempt: if inputs and blocker are unchanged, stop instead of asking another model to repeat the same repair. Source gaps and disputed content remain visible; tests do not establish teaching approval.
