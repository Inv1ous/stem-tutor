# STEM pilot corpus v2

Built 26 October 2026 with `app/tutor_app/stem_training_data.py`, seed `20261026`.
The explicit output is `/Volumes/External SSD TB4/LocalAI/stem-tutor-training/data-v2`.
Inputs were the 102 JSON packs selected by the public vault's `.tutor/packs/CURRENT`
(`v265`). The builder reads only `specs/*/packs/*.json`; it does not open learner logs,
private notes, screenshots, draft packs or model responses. It performs no network or model calls.
The published pack tree is read-only, including rejection of output destinations inside it.

| Split | Rows | Chemistry | Mathematics | Physics | Groups | Marking | Separate speech |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Train | 705 | 222 | 233 | 250 | 75 | 16 | 142 |
| Development (`valid`) | 255 | 124 | 59 | 72 | 23 | 12 | 35 |
| Sealed test | 278 | 115 | 56 | 107 | 32 | 8 | 56 |
| Total | 1238 | 461 | 348 | 429 | 130 | 36 | 233 |

The corpus contains 460 published flashcards, 242 accepted visible worked solutions,
233 plain-prose speech variants, 216 exact formula calculations across 18 algorithm
families, 36 curated marking examples across nine concepts, 12 literal source examples,
three OPEN-answer guiding questions, and 36 direct-recall rows from an 18-fact
primary-source registry (six facts per subject, two prompts per fact). CAIE 9701/9702 and the available Edexcel IAL
modules retain their source identifiers. All 102 input file hashes are in the manifest;
each public row records specification, KC, published version, content version, source
field, source item and file SHA256. Each synthetic row records its explicit formula or
curated truth table and a SHA256 of that reference. No unchecked teacher output is gold.

## What the labels establish

Published examples are explicitly **source-transformation tasks**: the prompt supplies
the published study-card answer or visible authored steps, and the assistant preserves
the facts while converting paragraph/equation boundaries to the current semantic document
format. Published scientific content was not independently rederived. Therefore these
rows establish source fidelity and formatting, not expert scientific knowledge or verified
official mark schemes. The separately labelled `direct_recall` rows have no supplied answer in their prompts;
their targets are hand-checked primary-source facts/formulae with exact source URLs,
source locations, our paraphrased claim and its SHA256 in provenance. Gold never invents a missing worked step, number, qualification,
mark label or answer. Public past-paper `items`, arbitrary negated public answers, faded
exercise answers and public notes were not used.

Synthetic calculations use integer or exact rational identities with explicit conditions
and units: constant-mass force, kinetic/potential energy, waves, charge, pressure, amount,
concentration, supplied molar gas volume, volume conversion, dilution, yield, derivatives,
integrals, arithmetic sequences, linear equations, expansions and rational addition.
Marking labels come from small written truth tables for catalysts, isotopes, dynamic
equilibrium, vectors, work, momentum, quadratic roots, real squares and triangle angles.
Their positive, missing and contradictory responses remain together by concept. Catalyst
omission/contradiction cases award neither criterion; no external evaluation question was
copied into training. OPEN hints ask a single conceptual question and omit the final
answer. Literal Python, JSON and CSV retain actual newlines and quotes; code is supplied
source copying, not an execution claim. Speech variants read only plain English source
verbatim in a separate `speech` field.

Every document gold is accepted without repair by the application's `DocumentDecoder`
(the current provider-independent shared document validator/renderer). Equation blocks
contain raw LaTeX without dollar wrappers. Inline mathematics retains its source. Code
remains literal. The one discarded source was `we1` in
`specs/9701/packs/9701-4.1.json`, which required a decoder repair. Its identifier/reason
is recorded in `quarantine.jsonl`; its answer was not silently repaired or included.
No gold includes private hidden reasoning or an assistant analysis channel. Authored
visible worked steps and brief mark-point reasons are explicit output, as in the app.

## Leakage controls and limits

Public groups encompass whole subtopics, which keeps their KCs and worked examples
together. Exact duplicated gold and case/whitespace-normalised original questions union
those groups before any speech augmentation. Known registry-related public subtopics
and synthetic formula/marking families are explicitly unioned with their corresponding
curated fact groups; for example a direct-recall force holdout also excludes the known
public dynamics and synthetic force examples from training. Synthetic numerical variants share an
indivisible algorithm family. Normal groups use `SHA256(seed:group) mod 100`, with
70/15/15 thresholds. Curated marking groups are ranked by the same seeded hash within
subject; at least one concept group is reserved for each holdout, with the remainder
training. This avoids a tiny marking stratum accidentally assigning every concept to
training. Direct-recall groups use the same per-subject hash ranking and holdout
reservation, with precedence over the marking allocation if a merged group overlaps.
This yields 20 train, eight development and eight sealed direct-recall rows, with every
subject represented in each split; these are distinct held-out fact families, not
paraphrases of a training registry fact. Merging also yields 16/12/8 marking rows rather
than equal counts. IDs and all group sets are pairwise disjoint across files.

The sealed test exceeds the requested approximate 40 examples per subject. Formatting/source examples are correlated within
published subtopics: row counts are not independent statistical sample counts. Grouping
catches exact duplicates and whole subtopics; it does not prove that semantic paraphrases,
related concepts or algorithm families appearing in different published subtopics are
independent. Explicit registry links cover known matching public/synthetic concepts, but do not
prove exhaustive semantic decontamination of the entire authored pack corpus. Other
synthetic algorithms can also be familiar from published source material.
Consequently unseen-group performance must not be described as proof of fully unseen
scientific concepts. Public source-copying scores and independently specified scientific
or marking evaluation scores must be reported separately. This bounded corpus does not
establish complete syllabus coverage, perfect marking, or broad model expertise.

The builder does not tokenize or truncate rows. The trainer must report which training
and development examples fit its 512/1024-token budgets and must not silently truncate
gold. The trainer should not read sealed test content during checkpoint selection.

## Reproduction and verification

```sh
PYTHONPATH=app .venv/bin/python -m tutor_app.stem_training_data \
  --vault '/Users/sora/Miscellaneous/02 Education/~~ AI Workflow/STEM Tutor/.tutor/packs/CURRENT' \
  --output '/Volumes/External SSD TB4/LocalAI/stem-tutor-training/data-v2'
.venv/bin/python -m pytest tests/app/test_stem_training_data.py -q
```

TDD began with six expected `NotImplementedError` failures after the initial absent-module
collection failure. Further new-behaviour tests failed first for separate speech,
held-out marking concepts, a real `Packs.root` facade and duplicated original questions
with differently worded source answers. The direct-recall requirement added a further expected failing regression before
implementation. The final targeted result is **13 passed**.
Tests also cover deterministic bytes/manifests, source-file hashes, exact equations and
literal code/newlines, private-log exclusion, OPEN protection, curated false labels,
all document decoder round-trips, group/ID disjointness and rejection of an output
inside the source tree. A separate built-corpus audit recomputed every split hash,
row count and pairwise group/ID disjointness, and checked assistant JSON equals expected.
The root agent owns the full repository test suite.

| File | SHA256 |
| --- | --- |
| `manifest.json` | `439c106584be8268aa6019278ed286359b3ce840d705ddc32c0279e7951bcb9a` |
| `train.jsonl` | `1b50e7305b3bb339eb8c644db5fe12fd044801c35fb3097b5bc00d55b7a19cf1` |
| `valid.jsonl` | `7d1f112e7ffe56566b1838b32bcdcb1fd158c160e99f1590c7efcd23661b44b2` |
| `test.jsonl` | `7d73eab08a0ed47716b0d5213955afb50be79c55bfa0d45def66ab8062148bb1` |
| `quarantine.jsonl` | `8719aeb8b22c54327bcf725cae862495a4076ec437be0a7a98941e85e665fbe1` |

The row contract is `id`, `group`, `subject` (`chem|phys|math`), `task`, exactly two
`messages` (user then final assistant JSON), `expected`, `provenance` and nonempty
`checks`. Document expected objects contain `blocks` and optionally `speech`; marking
expected objects retain the app's `points` (`point`, boolean `met`, short `why`) and
`feedback` schema. Prompts request that marking schema explicitly.

## Primary-source registry provenance

Authoring used read-only primary-source verification on 26 October 2026. The builder
itself remains offline and deterministic. Prompts now contain only the brief identity
`STEM Tutor. Reply in document JSON.` plus the actual task; marking alone specifies
its separate schema. The learned assistant targets, rather than a repeated long format
sheet, demonstrate semantic blocks, mathematical source and separate speech.

Chemistry checks cover atomic number ([US NRC glossary](https://www.nrc.gov/education-regulatory-research/glossary/atomic-number)),
nucleon count ([IUPAC mass number](https://goldbook.iupac.org/terms/view/M03726)),
isotope relationships ([IUPAC isotopes](https://goldbook.iupac.org/terms/view/I03331/pdf)),
electron-transfer oxidation ([IUPAC oxidation](https://goldbook.iupac.org/terms/view/O04362)),
amount per mixture volume ([IUPAC amount concentration](https://goldbook.iupac.org/terms/view/A00295))
and mass per amount ([IUPAC molar mass](https://goldbook.iupac.org/terms/view/12214/plain)).
Individual IUPAC Gold Book entries are attributed to IUPAC; its entry licensing is
[CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/). Registry targets are short
independently written factual paraphrases, not reproduced entry text.

Physics covers momentum, resultant force, power, potential difference, gravitational
field strength and electric field strength, checked against the exact numbered outcomes
3.1.3–4, 5.1.5, 9.2.1–2, 13.1.1 and 18.1.1–2 in the
[CAIE9702 2025–27 syllabus](https://www.cambridgeinternational.org/Images/664565-2025-2027-syllabus.pdf).
The six mathematics facts cover sphere and cone areas, the cosine rule, arithmetic nth
term, geometric sum to infinity with its convergence restriction, and change of logarithm
base with real-domain restrictions, checked against the mathematical identities in
[Pearson's IAL formula book, issue2 January2021, printed page3](https://qualifications.pearson.com/content/dam/pdf/International%20Advanced%20Level/Mathematics/2018/Specification-and-Sample-Assessment/IAL-Mathematics-Formula-Book.pdf).
This small registry supports a direct-recall comparison; it does not train or verify the
entire syllabus. Evaluate `direct_recall` separately from `published_flashcard` and
`published_worked` source tasks, and compare scientific content independently from
JSON/schema adherence.

The original `/Volumes/External SSD TB4/LocalAI/stem-tutor-training/data-v1` was retained
unchanged when direct-recall scope was added. All hashes and counts above identify v2.
