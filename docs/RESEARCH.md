# Research behind STEM Tutor

What each feature is based on, how strong the evidence is, and the limits. The learner-facing summary is section 14 of
`How It Works.md`. Items marked ✔ were checked against the source during the v1.1.0 evidence review (2026-09-30);
items marked ◌ are established findings carried over from the original design and not re-verified in that review.

## Strong evidence

**Retrieval practice (every question, probe, blurting).** Testing beats restudy, about g = 0.50, more with feedback and
short-answer formats (Rowland 2014, *Psychological Bulletin*) ◌.

**Successive relearning (review relearn step + FSRS spacing).** Practising to a correct-recall criterion across several
sessions beat single-session learning, d = 1.52–4.19; differences from the first session's spacing largely vanish after
relearning (Rawson, Vaughn, Walsh & Dunlosky 2018, *J Exp Psychol Applied*,
https://pubmed.ncbi.nlm.nih.gov/29431462/) ✔. Classroom evidence: Rawson, Dunlosky & Sciartelli 2013, *Educ Psychol Rev*
25:523 ✔. Review: Rawson & Dunlosky 2022, *Current Directions*. Limits: mostly lab/university and fact items; costs time.

**Free recall / blurting.** One week later, free-recall practice 0.67 vs elaborative concept mapping 0.45, d ≈ 1.5
(Karpicke & Blunt 2011, *Science*, https://www.science.org/doi/10.1126/science.1199327) ✔. Later work shrinks the gap
against concept mapping when study time is equalised (Mayrhofer et al. 2023, *Frontiers*) ✔ and finds concept mapping
helps inference questions (Lechuga et al. 2024) ✔. Design consequence: blurting is used against re-reading, always
followed by showing what was missed.

**Hypercorrection (confident-but-wrong flag, retest).** High-confidence errors are corrected more readily after feedback
(Butterfield & Metcalfe 2001), replicated in children (Metcalfe & Finn 2012) ✔; many return after a week unless retested
(Butterfield & Metcalfe 2011, *Psychon Bull Rev*) ✔. Review: Metcalfe 2017, *Annu Rev Psychol*.

**Self-explanation ("in your own words").** Self-explanation prompts g = 0.55 (Bisra et al. 2018, *Educ Psychol Rev*,
69 effect sizes) ✔; elaborative interrogation d = 0.56 and self-explanation d = 0.54, larger for surface than deep
outcomes (Donoghue & Hattie 2021, *Frontiers in Education*) ✔. Paired with feedback in the app.

**Worked examples → faded, and expertise reversal (method policy).** Worked examples help novices with procedures;
the benefit reverses as expertise grows (Sweller; Kalyuga 2007) ◌. The policy switches to problem-first at high ability.

## Moderate evidence

**Pretesting / trying first (probe, discover questions, problem-first challenge).** Prequestions improve learning of the
asked material; productive failure helps conceptual transfer for learners with some prior knowledge (Sinha & Kapur 2021
meta-analysis) ◌.

**Interleaving (mixed reviews, test prep).** Preregistered cluster RCT, 787 seventh-graders: interleaved 61% vs blocked
38% one month later, d = 0.83 (Rohrer, Dedrick, Hartwig & Cheung 2020, *J Educ Psychol*) ✔. Meta-analysis g = 0.42
overall, 0.34 in maths, highly variable (Brunmair & Richter 2019) ✔. Design consequence: interleave only after each type
has been learned (lessons are blocked by subtopic; reviews are mixed).

**Breaks and fatigue.** Micro-breaks improve vigour (d = 0.36) and reduce fatigue (d = 0.35) but show no significant
performance effect (d = 0.16) (Albulescu et al. 2022, *PLOS ONE*) ✔. Brief task switches can prevent vigilance
decrement (Ariga & Lleras 2011) ✔. Design consequence: breaks are suggested (once, when accuracy dips against
expectation), framed as comfort, never forced.

**Time of day.** Randomised school-timing study (753 students): morning classes favour early chronotypes, largest in maths
(Goldin et al. 2020, *Nature Human Behaviour*) ✔; small links between chronotype and achievement (Preckel et al. 2011) ✔.
Design consequence: reported as personal advice from the learner's own residuals, never a rule.

**FSRS scheduling.** On ~350M Anki reviews FSRS-6 predicts recall better than earlier versions and SM-2 (log loss 0.346,
AUC 0.703; open-spaced-repetition srs-benchmark) ✔. These are prediction-accuracy benchmarks, not learning trials.

## Weak evidence or design choices

**Grades from correctness + confidence + hints.** FSRS grades are normally self-reported; deriving them (wrong → Again,
hinted or unsure → Hard, correct → Good, certain on an established idea → Easy) is a design choice without direct trial
evidence ✔ (evidence review recommendation followed).

**Raising target retention near an exam.** Consistent with FSRS's retention/workload trade-off (90% → 95% roughly doubles
reviews) and the workload-optimal scheduling framework (Ye, Su & Cao 2022, KDD) ✔, but no trial has tested exam-deadline
retention. Bounded to 0.85–0.97.

**Elo with attempt-dependent K.** U(n) = a/(1 + b·n) (Pelánek 2016, *Computers & Education*; Pelánek et al. 2017, UMUAI) ✔;
the engine uses max(0.15, 0.6/(1 + 0.1n)). Evidence is prediction accuracy on fact practice.

**Slip detection.** Contextual slip estimates add predictive value beyond knowledge tracing (Baker et al. 2010, UMAP) ✔;
the fast-miss-on-a-known-idea rule is an inference from that work, used only to halve the ability update and to
suggest "slip" when asking why an answer was missed.

**Error self-tagging / exam wrappers.** Mixed: strategy changes reported informally (Lovett 2013); no exam-score gain from a
single-course wrapper (Soicher & Gurung 2017) ✔. Kept as a capped, skippable one-key habit.

**Not used: learning styles.** Matching teaching to a preferred "style" has no support (Pashler et al. 2008) ◌.

## Guided lesson redesign: source evidence and pilot (2026-10-28)

### Scope and source status

The local curriculum sources are `sources/specs/ial-maths-spec.pdf` (Pearson IAL, Issue 3),
`sources/specs/9701-2025-2027.pdf`, `sources/specs/9702-2025-2027.pdf`, and the corresponding
2028–2030 Cambridge syllabuses. The syllabus applies to the examination year. Cambridge states in
both 2028–2030 editions that there are no significant changes affecting teaching (Chemistry PDF
page 97; Physics PDF page 68). That statement is not a point-by-point comparison or proof that every
older question remains in scope. Compare each point against the relevant exam-year syllabus during
chapter refinement. Cambridge's
[Chemistry syllabus page](https://www.cambridgeinternational.org/programmes-and-qualifications/cambridge-international-as-and-a-level-chemistry-9701/)
and [Physics syllabus page](https://www.cambridgeinternational.org/programmes-and-qualifications/cambridge-international-as-and-a-level-physics-9702/)
publish both editions. These are authoritative for curriculum scope, not evidence that every
existing chapter already matches it. The student's exam year is not established here.

The [Pearson IAL mathematics specification](https://qualifications.pearson.com/content/dam/pdf/International%20Advanced%20Level/Mathematics/2018/Specification-and-Sample-Assessment/international-a-level-maths-spec.pdf)
P2 points 1.1–1.3 require proof structure from assumptions to conclusion, exhaustion, and
disproof by counterexample. Pearson's [P2 scheme of work](https://qualifications.pearson.com/content/dam/pdf/International%20Advanced%20Level/Mathematics/2018/Teaching-and-Learning-Materials/ial-sow-pure-2-final.pdf)
provides related vocabulary and teaching examples; it is guidance rather than an exhaustive list
of possible questions. Local `build/work/bundles/P2-1.md` supplies the mapped knowledge components
and glossary labels, but has no tagged past-paper MCQs and no examiner-report excerpts. Absence
from that bundle is not evidence that none exist. A complete point-by-point survey for the other
chapters remains to be done during their approved rollout.

### Program scope inventory

The current `build/out/specs/*/graph.json` files contain the following subtopic and knowledge-component counts. These are program inventory counts, not independently checked syllabus coverage or completed research. The pilot is P2 Proof only.

The local `sources/papers/ial` inventory contains question-paper/mark-scheme counts of 19/19 for WMA11, 18/18 for WMA12, 16/16 for WMA13, 17/18 for WME01, 17/17 for WST01 and 12/12 for WFM01. These counts are filename counts, not a check that each paper is correctly paired or relevant. No other IAL unit directories were present in that location at this check, so later units will need their sources located before their paper-based form surveys can be considered complete.

After that inventory, the missing June 2019 WME01 question paper was retrieved from [Pearson's official archive](https://qualifications.pearson.com/content/dam/pdf/International%20Advanced%20Level/Mathematics/2013/Exam%20materials/WME01_01_que_20190604.pdf) and saved as `sources/papers/ial/WME01/WME01_2019_Jun_qp.pdf` (SHA-256 `517c576af1718c23bc2be37dec5ad3b707bd1d3b379a7c56e9d563cd33e86258`). Its cover and first question match the existing June 2019 mark scheme. This is an initial identity check, not a complete content or current-syllabus review.

One June 2023 paper and scheme pair was also retrieved for each of Further Pure 2 ([paper](https://qualifications.pearson.com/content/dam/pdf/International-Advanced-Level/Mathematics/2018/Exam-materials/wfm02-01-que-20230609.pdf), [scheme](https://qualifications.pearson.com/content/dam/pdf/International-Advanced-Level/Mathematics/2018/Exam-materials/wfm02-01-rms-20230817.pdf)) and Further Pure 3 ([paper](https://qualifications.pearson.com/content/dam/pdf/International-Advanced-Level/Mathematics/2018/Exam-materials/wfm03-01-que-20230616.pdf), [scheme](https://qualifications.pearson.com/content/dam/pdf/International-Advanced-Level/Mathematics/2018/Exam-materials/wfm03-01-rms-20230817.pdf)). Their covers identify matching units and sessions. Each pair is a starting source, not a survey of those units or a substitute for checking each question against the current specification.

June 2023 starting pairs were also saved for P4 ([paper](https://qualifications.pearson.com/content/dam/pdf/International-Advanced-Level/Mathematics/2018/Exam-materials/wma14-01-que-20230610.pdf), [scheme](https://qualifications.pearson.com/content/dam/pdf/International-Advanced-Level/Mathematics/2018/Exam-materials/wma14-01-rms-20230817.pdf)), D1 ([paper](https://qualifications.pearson.com/content/dam/pdf/International-Advanced-Level/Mathematics/2018/Exam-materials/wdm11-01-que-20230603.pdf), [scheme](https://qualifications.pearson.com/content/dam/pdf/International-Advanced-Level/Mathematics/2018/Exam-materials/wdm11-01-rms-20230817.pdf)), S3 ([paper](https://qualifications.pearson.com/content/dam/pdf/International-Advanced-Level/Mathematics/2018/Exam-materials/wst03-01-que-20230614.pdf), [scheme](https://qualifications.pearson.com/content/dam/pdf/International-Advanced-Level/Mathematics/2018/Exam-materials/wst03-01-rms-20230817.pdf)) and S2 ([paper hosted by Physics & Maths Tutor](https://pmt.physicsandmathstutor.com/download/Maths/A-level/Papers/Edexcel-IAL/Statistics/S2/QP/June%202023%20QP.pdf), [Pearson scheme](https://qualifications.pearson.com/content/dam/pdf/International-Advanced-Level/Mathematics/2018/Exam-materials/wst02-01-rms-20230817.pdf)). The covers identify matching units and sessions. The D1 PDF includes its answer book beginning at PDF page 13, after the question paper; its diagrams and tables still need review. These pairs have not been fully reviewed.

The separate `sources/library/SaveMyExams/TQ YMA01 pure-3-questions-only` folder also contains Pure 3 topical question PDFs. Their scope, source attribution and corresponding mark schemes have not yet been verified, so they are leads rather than evidence of complete paper coverage. The library search included ignored files.

| Program specification | Subtopics | Knowledge components |
| --- | ---: | ---: |
| 9701 Chemistry | 90 | 354 |
| 9702 Physics | 76 | 300 |
| D1 | 5 | 15 |
| FP1 | 8 | 25 |
| FP2 | 7 | 17 |
| FP3 | 6 | 25 |
| M1 | 6 | 12 |
| P1 | 5 | 22 |
| P2 | 8 | 19 |
| P3 | 6 | 18 |
| P4 | 7 | 18 |
| S1 | 6 | 17 |
| S2 | 4 | 16 |
| S3 | 5 | 15 |

### P2 Proof: observations from local question papers

A text search of `sources/papers/ial/WMA12/*_qp.pdf` found examples of these forms; this is a
sample, not an exhaustive manual review. Refer to the matching question papers and mark schemes
for exact wording, allowable answers and mark allocation. Author new examples in our own words.

- **Counterexample under a stated domain:** January 2024 Q8(i), October 2024 Q11(i), and June
  2024 Q5(b) include claims about primes or real numbers. Require the proposed input to meet
  the assumptions and explicitly show the conclusion fails.
- **Exhaustion over finitely many eligible values or tuples:** October 2022 Q1 and October 2023
  Q1 constrain positive integer triples and request a product/divisibility proof. A complete,
  justified enumeration matters; account for symmetry only when the property is unchanged.
- **Exhaustion over finite *classes* of infinitely many integers:** January 2022 Q10(ii),
  January 2023 Q10, January 2024 Q8(ii), and October 2024 Q11(ii) use algebraic cases.
  Proof by exhaustion is not limited to a finite domain: finitely many exhaustive parity or
  residue classes can cover every integer, with a general argument for each class. The current
  P2-1.2 card's emphasis on finite lists alone should be expanded.
- **Algebraic proof and communicating an argument:** January 2021 Q5(i), June 2021 Q3(ii) and
  January 2025 Q8(ii) request algebraic justification; questions may state the result and require
  detailed reasoning. Keep a clear distinction between proving a general claim and testing examples.

The January 2024 P2 mark scheme in `sources/papers/ial/WMA12/WMA12_2024_Jan_ms.pdf` explains
that M marks reward an attempted method, A marks depend on relevant earned method marks, and B
marks are independent accuracy marks. Specific awarding, dependencies and follow-through depend
on the question's scheme; never imply that every correct-looking step automatically earns a mark.
The cited observations come from question-paper text searches and the mark scheme's general
instructions, not a complete question-by-question examiner-report analysis.

### Teaching approaches and strength of evidence

- **Retrieval for recall — strong, but task-specific.** In two experiments with prose passages,
  [Roediger and Karpicke (2006)](https://doi.org/10.1111/j.1467-9280.2006.01693.x) found that
  testing produced better delayed retention than restudy despite an immediate-test advantage
  for restudy. This supports scheduling term recall with feedback. It does not directly validate
  a particular FSRS schedule, nor establish problem-solving transfer.
- **Worked examples for novices — moderate direct evidence.** In secondary-school electrical
  troubleshooting, [van Gog et al. (2011)](https://doi.org/10.1016/j.cedpsych.2010.10.004)
  found example study and example–problem pairs lowered load and improved learning compared with
  problem-only study. Use worked examples before equivalent checks when the learner is new;
  circuits are not proof, and this study alone cannot guarantee an effect in every syllabus.
- **More independent practice with experience — moderate, conditional.**
  [Kalyuga et al. (2001)](https://eric.ed.gov/?id=EJ640537) found a change in the relative
  advantage of examples and problem solving as apprentices gained experience. Fade support in
  response to demonstrated performance, not merely a selected confidence score. Participants
  and tasks differ from A-level tutoring; adapt rather than assume an identical threshold.
- **Retrieval during procedures — mixed.** [Huang et al. (2023)](https://pmc.ncbi.nlm.nih.gov/articles/PMC9987560/)
  reported that retrieval did not necessarily improve mathematical word-problem solving over
  example study. In contrast, [van den Broek et al. (2025)](https://doi.org/10.1016/j.learninstruc.2025.102196)
  found better one-week recall and problem solving from stepwise retrieval prompts plus revealed
  feedback, but prompted participants studied roughly 31 minutes versus 13 minutes for controls.
  Participants were adults and tasks were limited. Retain examples and feedback; compare like
  outcomes and time costs rather than assuming retrieval alone teaches procedures better.
- **Granular presentation and adaptation — design decisions.** Short-first expandable prose,
  showing terms before use, and matching an observed mistake to a misconception are plausible
  accessibility and tutoring choices, not claims proven by the experiments above. Check their
  usability and correctness in the P2 pilot. Models can invent causes and solutions, and symbolic
  computation does not verify prose, assumptions or general proofs; only present checked maths
  when the verification actually covers the claim, otherwise say what remains unverified.

### Command words and pilot source pointers

Pearson P2 materials distinguish **prove** (complete logical reasoning covering the domain),
**show that** (establish the supplied result with sufficient working), and **hence** (use the
previous result where the question directs it). See `build/work/bundles/P2-1.md` for the
project's command-word list. Command-word interpretations must be checked against the exact
paper and mark scheme; wording and whether alternative methods receive credit can vary. A local
example is `sources/papers/ial/WMA12/WMA12_2021_Jun_qp.pdf`, Q3, which asks both for proof and
for algebra, together with `sources/papers/ial/WMA12/WMA12_2021_Jun_ms.pdf`.

Pilot source checks: `sources/papers/ial/WMA12/WMA12_2022_Oct_qp.pdf` Q1 (PDF page 2);
`.../WMA12_2023_Oct_qp.pdf` Q1 (page 2); `.../WMA12_2024_Jun_qp.pdf` Q5(b) (page 12);
`.../WMA12_2025_Jan_qp.pdf` Q8 (page 24); `.../WMA12_2022_Jan_qp.pdf` Q10 (page 34);
`.../WMA12_2024_Oct_qp.pdf` Q11 (page 30); and `.../WMA12_2024_Jan_qp.pdf` Q8 with
matching `.../WMA12_2024_Jan_ms.pdf`. Ellipses denote the same
`sources/papers/ial/WMA12/` directory. PDF page counts include cover pages and are not printed
paper page numbers. Mathematics notation extracted from PDFs can be damaged: review the page
image and scheme before reusing details. Examiner comments, all paper variants, diagrams, and
non-P2 syllabus points remain unreviewed here, so completeness is explicitly unproven.

### P2 proof-form follow-up, 28 October 2026

A literal text search for “prove”, “disprove”, “counter-example” and “exhaustion” was run over all 18 locally available WMA12 question papers from June 2019 through June 2025. This is a search inventory, not a complete manual assessment: mathematical symbols can be damaged during PDF text extraction, unlabelled proofs may not match these words, and other P2 topics also contain proofs. Examiner reports and all mark schemes still require further review.

The local June 2019 question paper is image-based: `pdftotext` extracts only the repeated `PMT` watermark from its 11 pages. Its cover identifies WMA12/01. The literal search therefore provides no evidence about that paper's question wording; it requires visual review or verified OCR.

Subsequent visual inspection of all 11 PDF pages found Q3 on PDF page 4: an algebraic inequality for all real numbers followed by disproof of a universal prime claim. The local matching June 2019 mark scheme, PDF pages 10–11, accepts a complete-square argument and awards credit for a valid counterexample. The pilot already has separately authored non-negative-square and counterexample forms. Q5(b) also asks for a calculus justification of a maximum; the pilot's stationary-point form is related. Other questions contain “show” and “hence” in topic-specific calculations. This visual pass establishes examples from this paper, not exhaustive classification of every proof form.

Pearson's [June 2019 examiner report, hosted by XtremePapers](https://papers.xtremepape.rs/Edexcel/Advanced%20Level/Mathematics/2019%20Jun/Examiner-report/Examinerreport-Unit2(WMA12)-June2019.pdf), PDF pages 3–4, identifies Q3 errors including treating several examples as a proof, failing to justify why a square is non-negative, and arithmetic or primality errors in counterexamples. It also notes missing sign explanations and conclusions in the maximum question, Q5(b). The draft explicitly teaches the limits of examples, the non-negative-square argument, a worked factorisation, and a negative second derivative followed by a conclusion. These are observations from one examination, not evidence of the prevalence of these errors in other cohorts. The report's title contains a unit-code inconsistency, so its Q3 and Q5 descriptions were cross-checked against the scanned WMA12 paper and mark scheme before use.

The local October 2019 WMA12 paper has a different text-extraction failure: much of the question text is encoded as unreadable characters, so the literal search can miss wording even when a text layer exists. Visual inspection of PDF page 8 finds Q4(b), which asks the learner to show a stated parameter value from a given factor. The matching mark scheme, PDF page 14, expects a factor-theorem substitution and intermediate working, or a valid check of the stated value. The unpublished pilot now has an independently authored example, check and retry for this cross-topic “show that” form; their parameter calculations were checked with SymPy. Only this question and scheme section were inspected, not the complete paper or its examiner report.

On reinspection, the scheme explicitly awards both marks to its alternative route that assumes the stated parameter and checks the factor with intermediate working. That is evidence of the examiner's credit policy for this particular question. Logically, checking a value demonstrates compatibility, whereas deriving it from the factor condition demonstrates that it is required. The pilot teaches this distinction and uses the stronger derivation in its own checks; its rubric is independently authored, not a reproduction of the historical scheme. The examiner's accepted route must not be described as an error in that historical marking scheme.

A subsequent visual pass examined all 32 pages of that question paper; its cover is dated 6 November 2019 despite the local filename's October label. Q9(ii)(a), PDF page 26, asks for a stated trigonometric relation to be derived from three terms of an arithmetic sequence. Q10(b), PDF page 30, asks for proof that a curve has no turning points after finding constants. The matching mark scheme, PDF page 26, accepts either showing the derivative has no real zeros using a negative discriminant, or completing the square and showing the derivative is positive everywhere. The draft now includes original worked examples, checks and retries for proving a derivative positive everywhere and deriving a relation from equal sequence differences. A separate original example, check and retry now apply equal differences to trigonometric terms. A further original example and checks include the reciprocal tangent manipulation and state the nonzero sine and cosine conditions. SymPy checked the derivatives and sequence solutions; it does not verify the explanatory arguments or local AI marking. This paper review alone does not establish coverage of other papers or their examiner reports.

A fresh extraction audit of all 18 local WMA12 question papers found that the June 2019 file yields only 55 characters, while the October 2019 extraction contains 754 non-whitespace control characters. All other papers contain at least one of the searched proof terms, but that does not demonstrate that their text extraction is complete or that every question was reviewed. The October 2019 paper is the clearest remaining priority for visual review; a successful keyword match elsewhere is not a completeness check.

Two additional proof forms matter for the pilot:

- **Complete a partially written exhaustion proof.** `sources/papers/ial/WMA12/WMA12_2023_Jan_qp.pdf`, Q10, PDF page 30, supplies one residue case and asks for the rest. Its matching `WMA12_2023_Jan_ms.pdf`, PDF page 27, awards method and accuracy marks for further cases, including a dependent method mark. An original example and check were added to the draft.
- **Cover only residue classes permitted by a restriction.** `sources/papers/ial/WMA12/WMA12_2025_Jun_qp.pdf`, Q10, PDF page 30, excludes multiples of three. The draft uses a different claim and explicitly identifies the two allowed classes. Four sample algebraic identities in the added examples were checked with SymPy; this does not independently verify the full prose, source coverage or all alternative solutions.

Other search matches, including 2023 June Q8 and 2024 June Q5, indicate multi-part proof contexts. They are not yet exhaustively classified or visually audited. No claim is made that the draft covers every possible wording.

A further review of WMA12 June 2023 Q8(ii) (question paper PDF page 20; mark scheme PDF page 19) found an ordered-pair exhaustion problem. The scheme distinguishes the swapped cases and asks for a conclusion. The P2 draft now includes an independently authored ordered-pair form with a non-symmetric expression. WMA12 June 2024 Q5(b) (question paper and mark scheme PDF page 12) tests a counterexample after widening a domain; the draft now has a separate original example and check for that form. The values in those examples and checks were independently evaluated. These observations do not establish completeness across all papers or examiner reports.

### P2 examiner-report review

Additional primary evidence: the [October 2022 WMA12 examiner report](https://qualifications.pearson.com/content/dam/pdf/International%20Advanced%20Level/Mathematics/2018/Exam-materials/wma12-01-pef-20230112.pdf), PDF page 3, describes candidates overlooking positive-integer conditions, confusing product with sum, omitting a conclusion and asserting an algebraic expression was even without justification. The pilot includes a product definition, domain checks, complete case lists and explicit conclusions. The same report distinguishes showing a given answer from merely verifying it; the pilot's show-that forms should be assessed against the particular question's marking scheme rather than treating verification as universally sufficient. The observations concern this one paper, not all examination cohorts.

The [June 2022 WMA12 examiner report](https://qualifications.pearson.com/content/dam/pdf/International%20Advanced%20Level/Mathematics/2018/Exam-materials/wma12-01-pef-20220818.pdf), PDF page 4, reports counterexamples outside the allowed natural-number domain and composite claims given without factors; it also describes geometry proofs that computed a right angle but omitted the circle-theorem conclusion. The draft explicitly checks domains and factor evidence, and its diameter example connects perpendicular lines to the stated circle fact. This is a targeted comparison, not an exhaustive survey of examiner comments or independent verification of every draft check.

Rechecking the local WMA12 June 2025 Q10 paper (PDF page 30) and mark scheme (PDF pages 22–23) confirms the existing restricted-residue form addresses the two eligible classes when multiples of three are excluded. The scheme explicitly awards no marks for testing numerical values instead of the requested algebra; it asks for reasoning in both classes and an overall conclusion. It directs alternative algebraic logic approaches for review rather than automatically treating them as equivalent to its primary method. The pilot's example expands both classes, while its independently authored check uses case-specific factors; its own rubric must be judged on its own wording and should not be represented as a reproduction of the paper's exact marking scheme.

The corresponding [June 2025 Pearson examiner report](https://qualifications.pearson.com/content/dam/pdf/International-Advanced-Level/Mathematics/2018/Exam-materials/wma12-01-pef-20250814.pdf), PDF page 12, reports continued use of numerical examples, duplicate or incomplete residue representations, and missing overall conclusions. It accepts equivalent complete class representations when they do not duplicate each other. The draft explicitly discusses an equivalent pair and a duplicated pair, and concludes after both cases. The report's warning about an expression that covers only part of a residue class is an additional point to evaluate in the pilot; the existing duplicate-class example alone does not demonstrate that distinction. This is feedback on one examination, not proof of broad prevalence.

Three Pearson reports were available online despite none being found in the local source library:

- [June 2023 WMA12 examiner report](https://qualifications.pearson.com/content/dam/pdf/International-Advanced-Level/Mathematics/2018/Exam-materials/wma12-01-pef-20230817.pdf), Q8, PDF pages 7–8: candidates sometimes used values outside the stated counterexample conditions, failed to state a conclusion, or missed combinations in the exhaustion part. This supports teaching domain checks, explicit conclusions and systematic ordered-pair lists; the report describes that paper's responses, not the prevalence of mistakes across all cohorts.
- [October 2023 WMA12 examiner report](https://qualifications.pearson.com/content/dam/pdf/International-Advanced-Level/Mathematics/2018/Exam-materials/wma12-01-pef-20240118.pdf), Q1, PDF page 3: reasons for lost marks included extra cases, missing a conclusion and confusing columns. Finite enumeration should check that each row satisfies the stated conditions as well as covering all allowed cases.
- [June 2024 WMA12 examiner report](https://qualifications.pearson.com/content/dam/pdf/International-Advanced-Level/Mathematics/2018/Exam-materials/wma12-01-pef-20240815.pdf), Q5, PDF page 7: candidates confused the positive domain in one part with the broader real domain in the next, and some failed to justify the sign when dividing an inequality. The draft's widened-domain counterexample addresses the former. A separate original example and check now teach sign-sensitive division.

These are primary examiner observations for specific questions, not exhaustive evidence of all P2 forms or marking conventions. The corresponding local papers and mark schemes remain the authority for each question's details. The sign-sensitive form and its marking rubric still need independent review before the pilot inventory can be treated as reviewed.

The local June 2024 question and mark scheme were subsequently checked against the new form: Q5(a) specifies positive variables, and the scheme requires that positivity be used to justify the inequality step. The independently authored check deliberately uses a negative divisor to test the reversal rule. Its rubric accepts division or multiplication by the reciprocal as methods; the existing short-answer grader treats keyword matches as hints and requires a separate judgement, since a negated incorrect answer can contain the same keywords. The full marking and independent content review remain outstanding.

The [January 2023 WMA12 examiner report](https://www.examsolutions.net/wp-content/uploads/2024/10/wma12-01-pef-20230302.pdf), Pearson's report hosted by ExamSolutions, describes Q10 on PDF page 10. It reports that candidates often repeated the provided case rather than completing the other residue cases, switched to an irrelevant case split, or omitted case-specific conclusions and the final conclusion. The pilot's partial-proof example now explicitly identifies the missing cases and states each case's result. This report concerns one paper; it does not establish that the draft covers every form.

### Cross-topic proof identified during pilot audit

WMA12 June 2024 Q7(b), question paper PDF page 18, asks for a proof that two circles do not touch or intersect, using results from part (a). The mark scheme, PDF page 15, credits either comparing the distance between centres with the sum of the radii, or solving the simultaneous circle equations and establishing that no real intersections exist. Both routes require a conclusion; the second uses a negative discriminant. SymPy confirms the first route's numerical comparison, √250 > √70 + √52. This comparison alone does not verify the derivation or the geometry argument.

The draft now includes a separate original example and check using given radii, centre distances and an explicitly supplied sufficient criterion, so it does not assume that the learner has studied circle equations. SymPy confirms the numerical comparisons in both examples. The draft rubric and live marking remain unverified, and this single example does not teach the alternative simultaneous-equations method. The audit remains incomplete.

### Further cross-topic proof search

A second literal search of the local WMA12 question papers located further proof contexts: an arithmetic-series sum derivation (January 2020, question paper PDF page 18), a geometric-series sum derivation (October 2020, page 26), a calculus maximum (June 2023, page 18), and a geometric diameter proof (June 2022, page 8). The June 2022 mark scheme, PDF page 12, gives distinct gradient and length-based approaches and requires a justified conclusion. These are leads for the pilot form audit, not an exhaustive review; the question numbers and other matching schemes still need checking. The draft inventory records them as unresolved cross-topic forms. A text search can miss proofs that do not use these words.

The October 2020 paper also has a **show-that trigonometric identity**, Q7(i), on PDF page 24, with restrictions on the angle. Visual inspection confirms the restriction excludes integer multiples of π/2, where a denominator or tangent is undefined. Its mark scheme credits rewriting tangent and its reciprocal, using a common denominator, and completing the identity without notation errors; it explicitly warns against spurious equations to zero. This is another proof form missed by searching only for “prove”. An original example and check now use the Pythagorean identity and state the nonzero denominator condition. SymPy simplifies both identities to zero; this checks the equalities, not the quality of AI marking or exhaustive coverage of trigonometric proofs.

The January 2020 arithmetic-series mark scheme describes reversing and adding corresponding terms, with enough written working to establish the pattern. The draft now teaches that reasoning using an independently authored sum of positive integers, followed by a check using the supplied result. SymPy confirms both sum identities; it does not validate every possible student proof or the local-model rubric. The June 2023 calculus maximum is Q7(c), and the June 2022 diameter proof is Q3(ii). The geometric-series derivation and calculus example remain to be assessed.

For the October 2020 geometric-series derivation, the mark scheme's principal route multiplies the sum by the common ratio, subtracts the two aligned sums, and then divides by one minus that ratio. That last step requires the denominator to be non-zero; the case where the ratio is one needs separate treatment. The draft currently teaches reversal and pairing in an arithmetic series, not this cancellation method, so the geometric-series form remains an open coverage item.

The draft now includes an original geometric-series cancellation example and a separate check. It states the non-zero denominator condition and treats ratio one separately. SymPy confirms the check's sum and the limiting value at ratio one; the direct repeated-term argument covers that case without division. The marking rubric and full live presentation have not yet been verified.

The draft now includes a self-contained stationary-point proof form based on the June 2023 Q7(c) method. It supplies both the second derivative and the criterion so a learner need not first derive them, and distinguishes a local maximum from a global one. SymPy verifies the check's substitution. This is a worked application of a supplied theorem, not a calculus lesson or a proof of the theorem; live model marking remains untested.

The June 2022 Q3(ii) mark scheme presents several valid chains, including gradients, squared lengths, and a midpoint argument. The draft now contrasts two independently authored routes, with the required circle fact supplied in the example and check. SymPy confirms the squared-length and gradient relationships for both. The other routes and the model's marking of alternate wording have not been tested; this is not a complete audit of all paper forms.

The proposed exhaustion corrections were checked against WMA12 January 2022 Q10(ii), question paper PDF page 34 and mark scheme PDF page 23. The question asks for exhaustion over all integers; the scheme treats odd and even cases algebraically and requires a conclusion for all integers. SymPy confirms its two expansions, 20k² + 2k + 12 and 20k² + 22k + 18, are even for integer k. The existing P2 worked example and hint each state finite domains, so the proposed local wording for those specific examples is appropriate. This source check supports the corrections but is not independent review or permission to bypass no-loss.

The [January 2022 WMA12 examiner report](https://qualifications.pearson.com/content/dam/pdf/International%20Advanced%20Level/Mathematics/2018/Exam-materials/WMA12_01_pef_20220303.pdf), Q10, PDF pages 10–11, reports that some candidates tested only a few integers instead of proving the parity cases, asserted evenness without justification, or omitted the conclusion. For the counterexample part, some chose values that did not satisfy the prime-number condition. The pilot explicitly uses a fresh integer parameter for each parity case, factors out 2 and concludes that both cases cover the integers; its counterexample guidance checks the stated domain. These observations concern one question and do not establish complete coverage or independently validate the pilot's marking.

The local WMA12 June 2025 Q10 asks for an algebraic exhaustion proof over positive integers not divisible by 3 (question paper PDF page 30). Its supplied mark scheme, PDF pages 22–23, accepts different pairs of residue representations but warns that $3k-1$ and $3k+2$ cover the same class. The draft restricted-residue example now explains this distinction and gives an alternative pair covering both nonzero classes. The scheme's displayed $p>0$ restriction alongside $3p+1$ and $3p+2$ would omit inputs 1 and 2 if read literally; the draft instead states $k$ is an integer and its claim covers all integers not divisible by 3. The mark scheme is a locally supplied PMT-labelled copy; this observation does not establish the provenance of that copy or full source coverage.

### October 2024 proof examiner feedback

Pearson's [October 2024 WMA12 examiner report](https://cdn.revivemygrades.com/past-papers/Edexcel/IAL/Pure%20Mathematics/P2/ON%202024%20ER.pdf), PDF page 11, identifies mistakes in Q11: using a non-prime input for a claim restricted to prime inputs, omitting a conclusion or justification of compositeness, substituting only sample values for a general exhaustion proof, using parity instead of the required residue classes, omitting a permitted class, and accidentally repeating the same residue class under different algebraic expressions. This is primary feedback for one paper, hosted by a third party. It supports the pilot's emphasis on the domain, explicit conclusions and distinct residue classes; it does not establish coverage of all question forms. The draft now includes an example explaining why 1 is not a valid input for a claim restricted to primes; a separate prime-domain form now includes an original check and retry.

Pearson's [October 2022 WMA12 examiner report](https://www.examsolutions.net/wp-content/uploads/2024/10/wma12-01-pef-20230112.pdf), Q1, PDF page 3, reports that some candidates confused a product with a sum, omitted the positivity restriction, or gave no final conclusion. The draft now defines product before the proof examples that use it, including when the exhaustion idea is studied independently. This single report does not quantify the prevalence of the misconception elsewhere.

The local October 2022 WMA12 Q1 (question paper PDF page 2) is more demanding than the draft's two-variable constrained-pair form: it combines three positive integers with both a sum and a relation between two variables. The current form teaches exhaustive listing under a sum constraint, but does not yet practise carrying two simultaneous constraints through a three-variable table. An independently authored three-variable form, check and retry now cover this structure; the wider source audit remains incomplete.

Pearson's [January 2021 WMA12 examiner report](https://qualifications.pearson.com/content/dam/pdf/International%20Advanced%20Level/Mathematics/2018/Exam-materials/WMA12_01_pef_20210304.pdf), Q5, PDF pages 9–10, describes two remaining pilot gaps. For an inequality proof, successful approaches could start with a non-negative square or work backwards and then justify the forward chain; omitting a conclusion or the required sign reasoning lost credit. For a counterexample involving consecutive primes, candidates sometimes confused prime with odd, included 1, used non-consecutive primes, or confused sum with product. Existing pilot material covers general proof chains and single-prime counterexamples, but now includes independently authored examples and checks for these two forms. The report concerns one paper; the cited percentages and observations should not be generalized to all learners.

### FP2 source lead: complex regions

Pearson IAL Mathematics Issue 3, `sources/specs/ial-maths-spec.pdf` PDF page 43, point FP2.3.3 includes loci and regions on an Argand diagram using modulus and argument; the preceding FP2 assessment description assumes P1–P4 and FP1 knowledge. The locally saved June 2023 WFM02 question paper, PDF page 6, Q2(b)–(c), combines a modulus boundary and an argument interval to shade a region, then asks for an extreme argument. The accompanying Pearson mark scheme, PDF pages 8–9, distinguishes drawing the circle and rays, shading the correct intersection, positioning it, and selecting a suitable point for the final angle. This is evidence for a future diagram-led, multi-stage question form and partial-credit explanation, not permission to roll out FP2 before the pilot review. Only one paper and this specification point were checked; other FP2 forms and examiner reports remain unreviewed.

### 9702 source lead: wave graphs

The Cambridge 9702 syllabus for 2025–2027, `sources/specs/9702-2025-2027.pdf`, printed page 20, points 7.1.1–7.1.7 and 7.2.1–7.2.2, requires wave vocabulary, wave speed, energy and intensity, plus interpretation of transverse and longitudinal graphs. In the locally available November 2023 9702/12 paper, PDF page 10, Q20 asks for phase difference from a wave diagram; Q21 asks for the time graph of a particular particle from a travelling displacement–distance profile. The corresponding principal examiner report, `sources/papers/9702/2023/w/9702_w23_er.pdf`, PDF page 8, describes the latter as challenging and explains determining the particle's initial direction by shifting the profile in the direction of travel. This supports teaching the distinction between a spatial snapshot and a single particle's time history, with a labelled sequence of diagrams and a separate check. It is one paper and one report, not a full survey or proof of future syllabus coverage. No science lesson has been modified before the pilot review.

### 9701 source lead: weak Brønsted–Lowry acids

The Cambridge 9701 syllabus for 2025–2027, `sources/specs/9701-2025-2027.pdf`, section 7.2 points 3–4, requires the Brønsted–Lowry theory and distinguishes full from partial dissociation in aqueous solution. November 2023 9701/22 Q3(a)(ii), question paper PDF page 8, asks for a definition combining both ideas. Its mark scheme, PDF page 7, awards separate marks for proton donation and partial dissociation. The corresponding principal examiner report, PDF page 13, identifies confusion between partial dissociation and incomplete dissolution. A later lesson should introduce both terms before the definition, teach the two distinct mark points, and contrast dissolving with ionisation using an appropriate example. This is one paper and one examiner observation, not a full syllabus or question-form survey. No Chemistry lesson has been changed before pilot review.

Pearson's [January 2020 WMA12 examiner report](https://qualifications.pearson.com/content/dam/pdf/International%20Advanced%20Level/Mathematics/2018/Exam-materials/WMA12_01_pef_20200305.pdf), PDF page 9, reports errors in Q8(i), including an incorrect last term, failure to reverse the sum, mishandling an odd number of terms when pairing within one row, and assuming the result to be proved. The draft now adds an original general arithmetic-series derivation using two aligned rows, shows the last term, and treats one- and two-term cases separately. SymPy checks the resulting sum formula; the report reflects one examination and does not establish error rates elsewhere.

Pearson's [October 2020 WMA12 examiner report, hosted by XtremePapers](https://papers.xtremepape.rs/Edexcel/Advanced%20Level/Mathematics/2020%20Oct/Examiner-report/Examinerreport-Unit2%28WMA12%29-October2020.pdf), PDF page 6, describes candidates confusing the arithmetic and geometric sum proofs, reversing subtraction signs, and skipping the unfactorised intermediate line in Q8(a). The pilot's geometric worked example now highlights subtraction order, that intermediate line, and the separate ratio-one case. The check now asks for the general formula with the nonzero-denominator restriction and the unfactorised subtraction line; the retry uses a particular ratio. These are observations from one examination.

### Further P2 proof source checks

Pearson’s [October 2023 WMA12 examiner report](https://qualifications.pearson.com/content/dam/pdf/International-Advanced-Level/Mathematics/2018/Exam-materials/wma12-01-pef-20240118.pdf), PDF page 3: Q1 proof by exhaustion lost marks for extra cases, omission of a conclusion, and confusion between case columns. The same page notes showing intermediate steps in show-that questions; PDF page 4 discusses this in factor theorem Q4(a). This supports explicit domain filtering, labelled case tables, and an answer that shows intermediate algebra. Single-exam evidence; inspect question and scheme before treating as full coverage.

Cross-check: local October 2023 question paper PDF page 2 Q1 sets c=3a+1 and a+b+c=15 for positive integer a,b,c. Matching mark scheme credits partial work even with extra/incorrect rows, but requires excluding those rows and a conclusion for full credit. It also accepts a complete deduction method; when representing two even quantities, it explicitly requires independent parameters (2m and 2n), not the same parameter by default. The draft now explains independent variables and filtering extra cases in its worked examples; the constrained-triples form lists labelled triples and checks their products. Do not generalize this particular mark scheme to every exhaustion question.

October 2023 Q8(b)–(c), question paper PDF page 20 and mark scheme PDF page 17, applies an arithmetic-series sum to seating rows, asks for a stated quadratic and then a valid row count. The scheme requires a correct sum setup and sufficient intermediate working for the supplied equation; the row count must be the positive solution. An independently authored version is now in the P2 draft, with a separate check and retry. SymPy confirmed its three equations and roots, a separate solver obtained both check solutions, and another reviewer checked the answers, rubrics and cited pages. The written-review records include both checks; this single example does not establish complete paper coverage.

October 2023 Q7(a), question paper PDF page 16 and mark scheme PDF page 15, asks for a stated radius-line equation using its perpendicular relationship with a tangent. The scheme credits the radius gradient, the equation through the centre and sufficient intermediate algebra. An original example, check and retry have been added to the draft; a separate solver worked both checks and another reviewer checked the mathematics, rubrics and source. The point of tangency is not needed to determine the radius line when the centre and tangent gradient are known. This is a single source example, not complete geometry-form coverage.

Pearson’s [June 2022 WMA12 examiner report](https://papers.xtremepape.rs/Edexcel/Advanced%20Level/Mathematics/2022%20Jun/Examiner-report/Examinerreport-Unit2%28WMA12%29-June2022.pdf), PDF page 4, is hosted by a third party. For Q3(i), candidates sometimes gave out-of-domain inputs or stated a result was composite without justifying it. In Q3(ii), the report accepts multiple routes for a circle-diameter proof but reports missing explicit right-angle and circle-theorem conclusions. The existing pilot's prime-domain and geometric alternative examples address these observations. Check the corresponding paper and scheme for exact credit and preserve source limitations; this report does not establish complete coverage.

### Visual survey of the scanned June 2019 P2 paper

The local `WMA12_2019_Jun_qp.pdf` has no usable question text layer. I rendered and visually inspected all ten question pages (PDF pages 2–11; the scan contains printed question pages but not every printed answer page). Besides Q3's inequality proof and counterexample, previously noted above, three cross-topic show-that forms need explicit consideration in the P2 Proof pilot:

- Q4(b), PDF page 5, asks for a binomial approximation after discarding fourth and higher powers. The scheme, PDF page 12, looks for addition of the two expansions with correct alternating signs and a fully justified result. This is a form combining a supplied truncation condition with cancellation, not an exact identity for arbitrary inputs.
- Q9(a), PDF page 10, asks for a trigonometric equation to be transformed into a stated quadratic in cosine. The scheme, PDF page 22, credits using the tangent and Pythagorean identities and showing intermediate equations. The domain where tangent exists matters when reasoning backwards.
- Q10(b), PDF page 11, asks for a definite integral to be shown equal to a stated value. The scheme, PDF page 24, expects an antiderivative, substitution of both limits and correct bracketing. A stated result needs visible working.

These are leads for original teaching examples and checks, not copied questions or evidence of complete coverage. The three scheme sections were checked through their text layers; the entire mark scheme and the source attribution of the local PMT-labelled files were not independently verified. The existing draft covers general show-that reasoning and trigonometric identities, but has not yet been checked against all three forms above.

The P2 draft now adds independently authored examples, checks and retries for each of these three forms. SymPy verifies the expansions, transformed polynomials and definite integrals; an independent reviewer checked the mathematical reasoning, domain restrictions, rubrics and direct answer overlap. These checks do not establish complete paper coverage or reliable AI marking.

The partial cross-topic P2 survey found two further show-that leads: WMA12 June 2025 Q9(a) (question paper PDF page 26, mark scheme PDF page 20) derives open-container surface area using a volume constraint; WMA12 January 2020 Q9(b) (question paper PDF page 22, mark scheme PDF page 18) derives an exponential-curve intersection using index and logarithm laws. Original candidate examples and checks are drafted in `build/work/guided/P2-1-cross-topic-leads.md`; they are not installed or fully reviewed. These questions belong to other P2 topics and do not by themselves prove a standalone proof-syllabus requirement. The survey remains incomplete.

### October 2019: quadratic gradients and sequence-to-trigonometry checks

A visual screen of the local October 2019 WMA12 question paper was followed by full-resolution review of Q9(ii), PDF page 26, and Q10, PDF page 30, and its mark scheme, PDF pages 24–26. The paper text layer is unreliable. Q9(ii)(a) derives a trigonometric relationship from an arithmetic sequence whose middle term is a reciprocal tangent; its mark scheme expects intermediate sequence and trigonometric working. The draft reciprocal-tangent form covers that type with independently authored coefficients, but does not cover the paper's later interval-constrained solution for the angle.

Q10 first derives parameters, then asks for a no-turning-points proof. The scheme accepts either a negative discriminant for the derivative quadratic or completing the square to show the derivative is positive. The draft's current no-turning-points checks use derivatives with immediate positivity and do not exercise a quadratic linear term or parameter derivation. A separate unpublished lead in `build/work/guided/P2-1-quadratic-gradient-lead.md` drafts an example and checks for that extra variation. SymPy verified the stated derivatives and discriminants; an independent blind solver verified the two completed-square proofs. The preceding parameter derivation, full cross-form disclosure review, marking review and interactive presentation are still outstanding. Screening thumbnails of the remaining pages are not a complete manual survey or full syllabus coverage.

The quadratic-gradient variation has since been incorporated into the unpublished P2 draft with prerequisite facts and an independently authored example, check and retry. A separate reviewer verified the derivative, discriminant and direct strict-monotonicity routes and the marking points; the rubric accepts all three. This does not add the paper's earlier parameter-derivation task, and it does not establish complete disclosure or source coverage.
