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
