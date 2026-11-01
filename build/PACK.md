# Content pack spec (one pack per subtopic)

A pack supplies source-backed foundations for one syllabus subtopic: terms and notation, question forms, staged examples, separate independent checks, misconceptions, useful visuals, practice and review. The learning AI adapts explanation and practice to the learner using this prepared material and explicit source gaps. Every prepared fact, answer, distractor and hint must be independently checked: a real student relies on it for consequential exams.

## Inputs

`build/work/bundles/<subtopic>.md` (made by `build/bundle.py`): the subtopic's KCs (official statement, type, prerequisites, glossary), the spec's command words and constants, tagged past-paper MCQs with official keys and examiner comments, and examiner-report excerpts for this content.

## Outputs

1. `build/out/packs/<spec>/<subtopic>.json` — the pack (schema below).
2. `build/out/notes/<note path>` — the Obsidian lesson note named in the pack's `note` field.
3. Optional diagram requests in the pack's `diagrams` list (rendered by `build/diagrams.py`).

Then run, and fix everything reported until both are clean:

```bash
.venv/bin/python build/validate_pack.py build/out/packs/<spec>/<subtopic>.json build/out/specs/<spec>/graph.json
.venv/bin/python plugin/stem-tutor/skills/tutor/scripts/tutor.py lint "build/out/notes/<note path>"
```

## Pack schema

```json
{
 "subtopic": "9702-2.1", "spec": "9702", "version": 1,
 "note": "Subjects/9702 Physics/02 Kinematics/2.1 Equations of motion.md",
 "outline": "≤150 words: the core ideas in teaching order, with $…$ maths",
 "misconceptions": [{"id": "m1", "kc": "9702-2.1.1", "statement": "…", "refutation": "…", "contrast": "…", "source": "ER 9702 s23 P22 Q2"}],
 "worked": [{"id": "we1", "kc": "…", "problem": "…",
             "steps": [{"do": "…", "why": "…", "check": {"kind": "numeric", "answer": {"value": 69.0, "unit": "m", "sf_ok": [2, 3]}}}],
             "faded": {"id": "we1f", "problem": "…", "answer": {"value": 37.5, "unit": "m", "sf_ok": [2, 3]}, "blank_from": 1}}],
 "items": [ … ],
 "flashcards": [{"id": "fc1", "kc": "…", "front": "…", "back": "…"}],
 "diagrams": [{"file": "Assets/9702/2.1-vt-graph.svg", "type": "graph_sketch", "params": {…}}]
}
```

### Items

Common fields: `id` (`<subtopic>-i01`, `-i02` … unique), `kcs` (1–2 KC ids), `kind`, `difficulty` 1–5 (1 recall, 2 single-step, 3 standard exam part, 4 multi-step, 5 hardest exam part), `command_word` (from the spec's list), `source` (`{"type": "generated"}` or `{"type": "past", "ref": "CAIE 9702 · Jun 2023 · P12 · Q7"}`), `stem`, `marks`, `explanation` (why the answer is right, in 1–3 sentences), `hints` (exactly 3: a nudge, then the strategy, then the key first step; none may contain the answer).

- **mcq**: `options` {A–D}, `answer` letter, `distractors` {letter: misconception id} for every distractor that encodes a known error, `shuffle: true` for generated questions. Past MCQs keep their original options and letters, add `image` when the bundle gives one, and need an `explanation` that also says why the most popular wrong option is wrong (use the examiner comment).
- **numeric**: `answer` {`value`, `unit`, `sf_ok` list of accepted significant figures, optional `tol_rel`}. Give a range by convention (`[2, 3]`): an exact value typed with fewer figures still earns the mark (9 for 9.0), as in the exam. Give ONE count (`[3]`) only when the figures are part of the answer, as for an instrument reading quoted to its precision (1.50 mm on a micrometer): then they are always marked. Figures the stem asks for ("to 3 s.f.") are always marked too; `distractors` [{`value`, `misconception`}] for values produced by known errors. Prefer a **template**: `template` {`params` {name: {min, max, step} | {choices}}, `derived` {name: expr}, `answer` expr, `distractors` [{expr, misconception}], `constraints` [expr]}, with `[[name]]` or `[[name:.2f]]` placeholders in the stem. Expressions are plain Python arithmetic (`sqrt`, `sin`, `log`, `pi` …). Constrain parameters so no distractor can equal the answer.
- **expression**: `answer` {`expr`} in Python/sympy syntax (`2*x*exp(x**2)`).
- **short**: `rubric` [{`point`, `keywords` [[synonyms…], …]}]: a point is met when every keyword group has one match. Use mark-scheme wording.
- **structured**: multi-part exam question; `scheme` [{`mark`: "M1"|"A1"|"B1", `point`, optional `check`}]; `marks` = number of scheme points.

### Coverage per KC (the validator enforces the number)

- At least 6 retrieval variants (a template counts 3): mix recall, procedure, concept-with-misconception-distractors and one exam-style item (difficulty 4–5).
- Use the 12 best genuine past MCQs from the bundle (they are the real standard), then generate to fill gaps; never copy a past question and present it as generated. The rest of the bank is appended automatically as unexplained "extra" items.
- Every `procedural` KC gets a worked example with a faded version.
- Every `factual` KC gets flashcards whose back uses mark-scheme wording (definitions exactly as Cambridge/Pearson credit them).
- Two to five misconceptions per subtopic (up to eight when it has more than six KCs), from examiner comments where possible (`source` = the ER ref), otherwise well-documented research (`source` = "research"). Map every distractor that encodes a known error to one.

## Conventions

- Maths: `$…$` inline, `$$…$$` on their own lines, never `\(`. Chemistry: `$\ce{H2SO4}$`, state symbols on equations.
- Units upright and SI, written as `m s^-1` in unit fields and `$\mathrm{m\,s^{-1}}$` in text.
- Constants exactly as the spec's data sheet: 9702 $g = 9.81\ \mathrm{m\,s^{-2}}$; Edexcel mechanics $g = 9.8$ (answers to 2 or 3 s.f.); 9701 $A_r$ values from the Periodic Table in the paper, $N_A = 6.02 \times 10^{23}$, $V_m = 24.0\ \mathrm{dm^3\,mol^{-1}}$ at r.t.p.
- Command words mean what the spec says (e.g. *Define* needs the formal definition; *Show that* needs every step).
- Worked steps follow the expert method a mark scheme rewards: equation stated, then substitution, then answer with unit and sensible s.f. Each `why` names the reason a student would otherwise miss.

## Lesson note

Obsidian markdown, about 400–900 words, readable in two minutes and printable:

```markdown
---
tags: [stem-tutor/lesson, cie-9702]
spec: "9702"
subtopic: "9702-2.1"
kcs: ["9702-2.1.1", "9702-2.1.2"]
---
# 2.1 Equations of motion
> [!abstract] In one breath
> …the big idea in two sentences…

## Key ideas
…definitions in markable wording, each with its $…$ form…

## Method
…numbered steps for the procedures…

> [!example]- Worked example
> …steps, `> ` on every line, `> $$` for display maths…

## Traps
- **Trap:** … **Why it's wrong:** … **Instead:** …

## Exam technique
…command words, mark-scheme habits for this subtopic…

## Links
Builds on [[1.3 Errors and uncertainties]] · Leads to [[3.1 Momentum and Newton's laws of motion]]
<!-- link only names from the bundle's "Chapters you may link" list, exactly as written; chapters not built yet may be linked -->
```

Diagrams: request them in `diagrams` and embed each with `![[Assets/…svg]]` (the gate fails a requested diagram that is not embedded, and a chapter with points a figure shows — the bundle lists them — and no diagram; a pack that truly has none sets `diagrams_skipped` to say why). Use Mermaid only for concept or process maps (quote labels that contain brackets).

## Diagram types (`build/diagrams.py`)

Each request is `{"file": "Assets/<spec>/<subtopic>-<name>.svg", "type": …, "params": {…}}`. Look at the rendered SVG (convert with `qlmanage -t -s 600 -o /tmp <svg>` and view it) before finishing.

| type | params |
|---|---|
| `graph_sketch` | `lines` [{`points` [[x,y],…], `label`, `style`: "solid"/"dashed"}], `xlabel`, `ylabel`, `shade` {`line`: i} (area under a line) or {`polygon`: [[x,y],…]}, `annotations` [{`xy`, `text`, `xytext`}], `ticks` bool, `hide_axes` bool for schematic figures, `equal_aspect` bool for equal axis scales |
| `function_plot` | `functions` [{`expr` in x, `domain` [a,b], `label`}], `asymptotes` {`x`: […], `y`: […]}, `points` [{`xy`, `label`}], `xlim`, `ylim`, `xlabel`, `ylabel` |
| `box_plot` | `min`, `q1`, `median`, `q3`, `max`, `outliers` […], `labels`, `whisker_label`, `outlier_label`, `xlabel`, `ticks` |
| `density_panels` | `panels` [{`expr` in x, `domain` [a,b], `title`}], `mark_centres` bool (mode/median/mean), `xlabel` |
| `free_body` | `body` "box"/"dot", `incline_deg`, `forces` [{`label`, `angle` (degrees from +x), `length`}] |
| `energy_profile` | `reactants`, `products`, `ea`, `catalysed_ea`, `reactants_label`, `products_label`, `ea_label`, `dh_label` |
| `maxwell_boltzmann` | `temps` […], `labels` […], `ea`, `shade_ea` |
| `wave` | `amplitude`, `wavelength`, `cycles`, `show_amplitude`, `show_wavelength`, `xlabel`, `ylabel` |
| `circuit` | `elements` [{`type`: battery/cell/resistor/lamp/ammeter/voltmeter/switch/ldr/thermistor/diode/variable_resistor/potentiometer, `label`}] drawn as one series loop in CAIE (IEC) symbols |
| `case_split` | `start`, `cases` (two or three short labels), `end`; for a complete set of proof cases |
| `proof_flow` | `steps` (two to four short labels); for a logical chain or counterexample process |

A figure the table cannot draw (apparatus, molecular structures, mechanisms): describe it in words in the note and flag it in `concerns`; never hand-write SVG coordinates.

Figures from the learner's own PDFs (not drawn, cropped): `library.py figures|page|crop` writes `build/out/assets/<spec>/<name>.png` + a `.png.json` sidecar; embed `![[Assets/<spec>/<name>.png]]` and, within 2 lines, `*Figure: … (source: <pdf>, p.N)*` (gated; local use only, never committed).

Sources: the learner's own PDF library is searchable with `.venv/bin/python build/library.py for <subtopic>` (see the "The sources library" section of `foundry/README.md`); a reference, never copied.

## Guided teaching cards

A guided chapter declares `guided_forms` in its pack: a mapping from every KC id to the names of its source-reviewed question forms. Keep the existing `teach` fields. Each guided card also needs:

- `plain_words`: a concise first explanation; `establish` remains the optional deeper explanation.
- `terms`: objects with `term`, `meaning`, `notation`, `spoken` and `source`.
- `forms`: objects with `name`, `wordings`, `example`, `check`, `answer`, `source` and `rubric`. Each rubric is a nonempty list of objects with `point` and nonempty keyword groups. Use criteria that allow alternative valid answers. Keyword matching is only a hint to the judge.
- A form may also include `retry` with a distinct `check`, its `answer`, and a complete `rubric`. This is a second question on the same form after its example is revisited; verify it independently and do not expose its answer before an attempt. Without a retry the existing general idea check remains the fallback.
- `misconceptions`: objects with `idea`, `temptation` and `fix`. An optional `id` connects the entry to an existing pack misconception.
- `source_gaps` (optional): what the specification, papers, mark schemes or notes PDFs did not cover or left unclear for this idea, one sentence each. Say so here instead of guessing; the learning AI is told these are not established.
- `diagrams`: asset paths, with matching `diagram_descriptions` for the terminal. If no appropriate figure can be drawn, give an honest `diagram_reason` and record the limitation in concerns.
- Optional `exam_language`: objects with `name` and `meaning`, grounded in the specification and mark schemes.

`build/teach_cards.py check <subtopic>` validates all cards as guided if any card includes guided fields. An incomplete guided draft does not replace existing cards during merge. Foundry and refine gates also check the declared form inventory, the draft-to-pack merge and diagram assets and note embeds. These checks do not prove that sources were exhaustively surveyed or that mathematics and prose are correct. Independently verify the content, inspect each rendered figure, and record source gaps. Use `bin/refine` for existing chapters and preserve the no-loss rule.

When an existing `discover` question overlaps a subsequent worked answer, preserve it and add an optional `guided_discover` MCQ with the same fields: `stem`, four `options` A–D, `answer`, and `explanation`. The lesson uses the new probe with a distinct item ID. Independently check its answer and review later lesson content for overlap; structural validation cannot establish that a skipped answer remains undisclosed.

A guided question form may declare `review_rule: "consecutive_primes"` when both its check and retry ask about consecutive prime triples. After a written attempt, the local or manual marking review can use SymPy to flag one explicitly stated invalid triple. Ambiguous, negated, oversized or unrecognised wording receives no automated warning; the learner still reviews the suggested marks. The rule does not prove a response correct and must not be used as a substitute for a complete mark scheme.

The P2 geometric-series form may declare `review_rule: "geometric_subtraction"` for its general sum proof. In local or manual review, it recognises a few explicit unfactorised subtraction lines and adds a note about their order. Other notation or longer expressions may not be recognised. This is not a general algebra verifier and never awards marks; the learner reviews the proposed marks.

## Foundation for AI-led teaching

A chapter does not need every explanation and question form written out. The learning AI (`tutorlib/teach_actions.py`) teaches from a modest foundation and asks the program for what it needs: per idea a short `plain_words`, the `terms`, a few source-checked `forms` (example, check, rubric), the misconceptions, `diagrams` or an honest `diagram_reason`, and `source_gaps`. Figures cropped from the notes PDFs (`library.py figures|crop|extract`, with their provenance sidecar) are offered to the AI automatically for the chapter named in `--for`; view each crop before relying on it. The AI may also ask for a new figure of a type in the table above; it supplies parameters, never SVG.

## SaveMyExams notes figures (any chapter, any course)

The notes PDFs sit in `sources/library/SaveMyExams/<course folder>/` (one PDF per chapter, e.g. `YMA01 pure-2/YMA01 c1.1.pdf` = P2 Proof). They are read-only: nothing here edits, moves or re-saves a PDF.

1. Find the pages: `library.py for <subtopic>` or `library.py search "<terms>" --folder <course>`; `library.py figures <pdf> --pages a-b` lists drawings and raster images page by page.
2. Look before you crop: `library.py page <pdf> <n> --dpi 70` renders a page to a PNG you open with the Read tool. A figure that is only a worked-example screenshot, or a decoration, is not worth showing.
3. Take it: `library.py crop <pdf> --page N --box x0,y0,x1,y1 --to <spec>/<subtopic>-<name> --for <subtopic> --caption "<what it shows, source>" --why "<what idea it helps with>"` (a box in 0-1 page fractions, or pixels; use it for a white background in both light and dark themes), or `extract --page N --index K` for an embedded raster (transparent backgrounds look black in a dark theme: prefer `crop`). Each crop is rendered upright, trimmed of blank margin, and written to `build/out/assets/<spec>/<name>.png` plus `<name>.png.json` recording the PDF, page, SHA-256, caption, why, chapter and time.
4. Check the crop: open the PNG. Labels complete and readable, nothing cut at an edge, no neighbouring text, and it shows what `--why` says. If not, delete both files and crop again with a better box; never publish an unchecked crop.
5. Use it: `figures_for(vault, subtopic)` (`tutorlib/teach_actions.py`) offers every figure of the chapter whose picture still has its recorded checksum to the learning AI, which names one by id; the program shows it with its caption, PDF and page in the Terminal log and as `![[Assets/<spec>/<name>.png]]` in Now and the lesson log. A note can embed it too, with `*Figure: … (source: <pdf>, p.N)*` after it (gated by `figure_problems`).
6. Where the files live: `build/out/assets/` is local-only (git-ignored: the PDFs are the learner's own and copyright is the publisher's). `build/publish.py` copies it, sidecars included, into the vault's `Assets/` folder, so a tutor run from the normal vault finds the figures there; on a machine without the library there are simply no notes figures to offer and the AI uses card or generated diagrams.


## Library / Work migration and workflow defaults

Reusable sources, question data, notes, figures, diagrams and fonts belong in `STEM Tutor/Library/`
and resolve through `tutorlib.asset_library.AssetLibrary`, retaining hashes, provenance, IDs and
aliases. Source discovery and verified PDF reads use `build/library.py`; source adapters are read-only.
The older `build/out`, `build/work`, `sources/library` and vault `Assets/` paths in this format guide
are compatibility paths: editable authoring lives in `Work/Preparation`, unpublished builds and diagram
outputs in `Work/Candidates`, and worker state/logs in `Work/Workers`. Follow explicit candidate paths
from the worker prompt. Never edit a Library-backed file adapter or delete a registered resource to
recrop it; create a fresh candidate and publish a new immutable resource. Publication registers assets
and releases in Library while preserving old identities and aliases; it does not establish teaching approval.

New Foundry board entries persist `teaching_contract: guided-v1`. Their signing gates require every
syllabus KC's complete guided card and reviewed form inventory using the validators above, including
separate checks/rubrics and linked visuals or honest visual exceptions. Pre-existing board entries
retain their legacy contract. Incremental Refine lesson passes remain governed by their persisted
scope/no-loss contract; the preparation queue reports incomplete guided coverage honestly.
