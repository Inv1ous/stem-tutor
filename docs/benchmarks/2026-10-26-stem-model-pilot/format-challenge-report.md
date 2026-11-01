# Frozen format challenge v1

The separate corpus is `/Volumes/External SSD TB4/LocalAI/stem-tutor-training/format-challenge-v1`.
It contains 18 original rows, six per subject and 18 distinct group IDs. All rows were
hand-checked and the complete selection frozen before model testing. It contains only
`test.jsonl`, `manifest.json` and `selection.json`; there are no training or development
files. The existing `data-v2` files were hashed before and after creation and are
unchanged. The main 120-row selection was neither read nor changed.

| Challenge | Chemistry | Physics | Mathematics |
| --- | --- | --- | --- |
| Exact literal source | Multiline JSON; quoted text, `NH4+`, `£4.20`, `82.5%` | Multiline Python source; escaped quotes, `£2.40`, `75%` | Multiline JavaScript source; `$3.50`, `12%`, literal scripts |
| Separate speech | Concentration `0.30 mol dm^-3` | Work `3.0 J` | Derivative `6x` |
| OPEN protection | Initial empirical-formula hint | Speed-time graph guiding question | Completing-square guiding question |
| Marking | Two explicit oxidation contradictions; `[false,false]` | Correct energy formula, omitted speed-scaling conclusion; `[true,false]` | Correct variable-term derivative, false constant derivative; `[true,false]` |
| Topic change and complete parts | Oxidation and nucleon count | Potential difference and mechanical power | Cosine rule and sphere area |
| Equation/units | Balanced magnesium oxidation half-equation | Pressure `3.0×10^2 Pa` | Exact reduced fraction `29/36` |

Each chat prompt uses the same brief identity, `STEM Tutor. Reply in document JSON.`,
and the actual task. It does not supply a document block schema. Literal JSON is
naturally present only in the requested source-copy task. Marking explicitly requests
the existing `points`/`feedback` schema. Spoken-answer requests require a separate spoken
version; their gold uses the existing separate `speech` field.

Every row retains `id`, `group`, `subject`, `task`, exactly two `messages`, `expected`,
`provenance` and `checks`. The manifest freezes all IDs, groups and the test-file hash.
The existing evaluation harness produced `selection.json` using `freeze_selection` with
six rows per subject and seed42. `load_selection` verified the resulting receipt.
No model output, GPU call, generated-code execution or environment change was involved.

## Truth and overlap boundaries

This is a **format-combination challenge**, not evidence of independent unseen scientific
knowledge. Underlying facts deliberately overlap the small training corpus. Against the
705 training rows in `data-v2`, the audit found zero exact normalised prompt duplicates,
zero exact complete-gold duplicates, and one row sharing an individual equation block.
The audit does not establish semantic independence. Per-row checks label this limitation
and record the exact block-overlap count. Formatting/fidelity scores must be reported
separately from scientific correctness and manually reviewed task coverage.

The literal examples require exact requested-source fidelity: real newlines, quotes,
currency, percent signs and scripts must survive unchanged. The evaluator's
`literal_code_equal` is the relevant automatic check. A different implementation might
be semantically valid but would not satisfy this exact-copy request; any alternative-code
semantic assessment is a separate manual judgement. Code must not be executed.

Speech must remain separate from visual blocks and preserve the result and units.
OPEN hints must be inspected for answer leakage; merely matching the schema does not
prove protection. Marking gold labels distinguish explicit contradiction and omission;
the physics prompt expressly disallows awarding an unstated requested conclusion by
inference. Topic-change rows contain an explicit previous-topic cue in one self-contained
prompt. They test compliance with that cue and both requested parts, rather than drift
across a real long conversation.

Scientific and arithmetic checks were made before freezing:

- Amount concentration follows amount/mixture volume, `0.15/0.50=0.30`, with two significant figures. [IUPAC amount concentration](https://goldbook.iupac.org/terms/view/A00295).
- Electron loss and increasing oxidation number define the two chemistry marking criteria. The magnesium half-equation conserves atoms and charge: `0=+2-2`. [IUPAC oxidation](https://goldbook.iupac.org/terms/view/O04362).
- Nucleon count combines protons and neutrons. [IUPAC mass number](https://goldbook.iupac.org/terms/view/M03726).
- Work is force times displacement along the force, so `4.0×0.75=3.0 J`; the other physics relationships match outcomes4.3,5.1,5.2 and9.2. [CAIE9702 2025–27 syllabus](https://www.cambridgeinternational.org/Images/664565-2025-2027-syllabus.pdf).
- The cosine rule and sphere-area identity were checked against the awarding body's formula book. [Pearson IAL formula book, issue2, printed page3](https://qualifications.pearson.com/content/dam/pdf/International%20Advanced%20Level/Mathematics/2018/Specification-and-Sample-Assessment/IAL-Mathematics-Formula-Book.pdf).
- Polynomial derivatives use the power and constant rules. Rational addition is independently checked by denominator36: `15/36+14/36=29/36`, with `gcd(29,36)=1`.

## CPU verification and immutable receipts

Two regression tests failed first because `build_format_challenge` was absent, then
passed after implementation. The complete data-module targeted suite is **15 passed**.
The tests verify six rows per subject, unique IDs/groups, separate speech and OPEN cases,
marking coverage, real source newlines and symbols, unchanged training bytes, compatible
selection loading, exact gold round-trips through the production CPU scorer, and refusal
to overwrite an already frozen challenge. A second audit on the actual SSD corpus checked
all 18 gold responses through `score_trial`: each had a valid raw contract and exact gold
match. These checks establish harness compatibility, not model performance.

| File | SHA256 |
| --- | --- |
| `test.jsonl` | `53088e3303ed8397c7f6530e75fdab5eaf096173ec2cc668d5c95d92c53a3418` |
| `manifest.json` | `5f15e1da2a77866739873a6d1521bbaa1ce13a8e813148ebbee427be5b75a15b` |
| `selection.json` | `ee6e2e27fb08779c246ced3ee622c765652764fa92dce78c722a867227e29fd0` |

The audit pins training manifest
`439c106584be8268aa6019278ed286359b3ce840d705ddc32c0279e7951bcb9a` and training-file
`1b50e7305b3bb339eb8c644db5fe12fd044801c35fb3097b5bc00d55b7a19cf1`.
Do not regenerate into this destination after testing starts; the builder refuses to
overwrite it. Use a distinct versioned output for any later revision.
