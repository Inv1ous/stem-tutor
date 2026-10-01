# Content pack spec (one pack per subtopic)

A pack is everything a small model (Claude Haiku) needs to tutor one syllabus subtopic well: the ideas, the traps, step-by-step worked solutions, a bank of verified questions, flashcards and a lesson note. Haiku will not solve or invent anything at runtime; it selects from this pack and converses. So every fact, answer, distractor and hint here must be exactly right: this is what a real student sees, for two years, for exams that decide university entry.

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
tags: [stem-tutor/lesson, 9702]
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
```

Diagrams: request them in `diagrams` and embed with `![[Assets/…svg]]`. Use Mermaid only for concept or process maps (quote labels that contain brackets).

## Diagram types (`build/diagrams.py`)

Each request is `{"file": "Assets/<spec>/<subtopic>-<name>.svg", "type": …, "params": {…}}`. Look at the rendered SVG (convert with `qlmanage -t -s 600 -o /tmp <svg>` and view it) before finishing.

| type | params |
|---|---|
| `graph_sketch` | `lines` [{`points` [[x,y],…], `label`, `style`: "solid"/"dashed"}], `xlabel`, `ylabel`, `shade` {`line`: i} (area under a line) or {`polygon`: [[x,y],…]}, `annotations` [{`xy`, `text`, `xytext`}], `ticks` bool |
| `function_plot` | `functions` [{`expr` in x, `domain` [a,b], `label`}], `asymptotes` {`x`: […], `y`: […]}, `points` [{`xy`, `label`}], `xlim`, `ylim`, `xlabel`, `ylabel` |
| `box_plot` | `min`, `q1`, `median`, `q3`, `max`, `outliers` […], `labels`, `whisker_label`, `outlier_label`, `xlabel`, `ticks` |
| `density_panels` | `panels` [{`expr` in x, `domain` [a,b], `title`}], `mark_centres` bool (mode/median/mean), `xlabel` |
| `free_body` | `body` "box"/"dot", `incline_deg`, `forces` [{`label`, `angle` (degrees from +x), `length`}] |
| `energy_profile` | `reactants`, `products`, `ea`, `catalysed_ea`, `reactants_label`, `products_label`, `ea_label`, `dh_label` |
| `maxwell_boltzmann` | `temps` […], `labels` […], `ea`, `shade_ea` |
| `wave` | `amplitude`, `wavelength`, `cycles`, `show_amplitude`, `show_wavelength`, `xlabel`, `ylabel` |
| `circuit` | `elements` [{`type`: battery/cell/resistor/lamp/ammeter/voltmeter/switch/ldr/thermistor/diode/variable_resistor/potentiometer, `label`}] drawn as one series loop in CAIE (IEC) symbols |

A figure the table cannot draw (apparatus, molecular structures, mechanisms): describe it in words in the note and flag it in `concerns`; never hand-write SVG coordinates.
