"""Generator for pack S1-1 (Mathematical models in probability and statistics). Content as data; numbers asserted."""
import json
from pathlib import Path
from fractions import Fraction

ROOT = Path(__file__).resolve().parents[3]
SUB, K = "S1-1", "S1-1.1"
NOTE = "Subjects/Maths/S1 Statistics 1/1 Mathematical models in probability and statistics.md"

# ---------- verified numbers ----------
obs = {1: 22, 2: 17, 3: 19, 4: 20, 5: 24, 6: 18}
assert sum(obs.values()) == 120
exp = Fraction(120, 6); assert exp == 20
assert max(abs(v - 20) for v in obs.values()) == 4 and abs(obs[5] - 20) == 4
assert Fraction(60, 6) == 10
for n in (60, 90, 120, 150, 240, 300):           # template: all choices divisible by 6, distractors distinct
    a = n / 6
    for d in (n * 6, 5 * n / 6, n / 3):
        assert abs(d - a) > 0.02 * a
assert 60 * Fraction(1, 6) == 10 and (7, 13) == (10 - 3, 10 + 3)
assert Fraction(1, 6) * 6 == 1

# ---------- worked example (mirrors the note) ----------
fobs = [14, 17, 15, 13, 16, 15]
assert sum(fobs) == 90 and Fraction(90, 6) == 15 and max(abs(v - 15) for v in fobs) == 2
worked = [{"id": "we1", "kc": K,
 "problem": "A student throws a die 120 times: scores $1$ to $6$ occur $22,17,19,20,24,18$ times. The model says each score is equally likely. Comment on the model.",
 "steps": [
  {"do": "Find the predicted frequency for each score: $120\\times\\tfrac16=20$.",
   "why": "Each score has probability $\\tfrac16$ under the model, so multiply by the number of throws.",
   "check": {"kind": "numeric", "answer": {"value": 20.0, "unit": "", "exact": True}}},
  {"do": "Find the differences from 20: $2,3,1,0,4,2$. The largest is $4$, for the score 5.",
   "why": "Compare every observed value with the prediction, not just the highest one.",
   "check": {"kind": "numeric", "answer": {"value": 4.0, "unit": "", "exact": True}}},
  {"do": "Conclude in context: all the differences are small compared with 20, which is consistent with chance variation, so the fair-die model is suitable and there is no evidence to reject it.",
   "why": "A comment needs a reason from the numbers and a conclusion about the model, not just 'close'."}],
 "faded": {"id": "we1f",
  "problem": "A die is thrown 90 times: scores $1$ to $6$ occur $14,17,15,13,16,15$ times. The model says each score is equally likely. Find the largest difference between an observed frequency and the frequency the model predicts.",
  "answer": {"value": 2.0, "unit": "", "exact": True}, "blank_from": 1}}]

def hints(*h): return list(h)
def item(i, kind, d, cw, stem, expl, hs=None, **kw):
    it = {"id": f"{SUB}-i{i:02d}", "kcs": [K], "kind": kind, "difficulty": d, "command_word": cw,
          "source": {"type": "generated"}, "stem": stem}
    it.update(kw); it["explanation"] = expl
    if hs: it["hints"] = hs
    return it

misc = [
 {"id": "m1", "kc": K, "statement": "A model is either exactly right or useless: any gap between its prediction and the data means it is wrong, and close agreement proves it correct.",
  "refutation": "A model is a deliberate simplification, so its predictions are never exact. Real data vary by chance, so small differences are expected and do not reject the model. Only a large, systematic difference suggests refining it. Close agreement supports a model but never proves it.",
  "contrast": "A fair-die model predicts 10 sixes in 60 throws. Getting 7 is ordinary chance variation and gives no reason to reject the model. Getting 25 sixes would be a large gap and would suggest the die is not fair.",
  "source": "research"},
 {"id": "m2", "kc": K, "statement": "The sample is the population, or the results from a sample are exactly the values for the whole population.",
  "refutation": "The population is the whole set of items of interest. A sample is only a selection from it. A value found from a sample is an estimate of the population value and changes from sample to sample.",
  "contrast": "For the rents of all 4200 tenants in a town, the population is the 4200 tenants. The 150 surveyed are a sample, and their mean rent estimates, but is unlikely to equal, the mean rent of all 4200.",
  "source": "research"},
 {"id": "m3", "kc": K, "statement": "If the model says the probability of a six is 1/6, then 60 throws must give exactly 10 sixes, and after a run without a six a six is 'due'.",
  "refutation": "The model gives the long-run average, not a guarantee. Real counts vary about the predicted value. Throws are assumed independent, so earlier throws do not change the probability of the next.",
  "contrast": "After ten throws with no six the probability of a six on the next throw under the model is still 1/6. Over many throws the relative frequency settles near 1/6, but no single set of 60 throws is forced to match.",
  "source": "research"},
 {"id": "m4", "kc": K, "statement": "Assumptions are facts that have been proved, so once a model is built the assumptions no longer need checking.",
  "refutation": "An assumption is a simplifying statement taken to be true so the model can be built. It may be only approximately true, so it must be stated and later tested against data. The predictions are only as reliable as the assumptions.",
  "contrast": "'The coin is fair' is an assumption of a coin-tossing model. If 100 tosses give 80 heads, the data challenge the assumption and the model must be refined.",
  "source": "research"},
 {"id": "m5", "kc": K, "statement": "A random variable $X$ is an unknown number to be found by solving an equation.",
  "refutation": "A random variable is a variable whose numerical value depends on the outcome of a chance event. It can take several values, each with its own probability. The capital $X$ names the variable and a lower-case $x$ is one particular value.",
  "contrast": "$X$ = score on a fair die: $X$ can be $1,2,\\dots,6$, and $P(X=4)=\\tfrac16$ describes the chance that it takes the value $x=4$. Nothing is being solved for.",
  "source": "research"},
]

items = [
 item(1, "numeric", 2, "Calculate",
  "A model for a die assumes that each of the six faces is equally likely. The die is thrown [[n]] times. Calculate the number of sixes the model predicts.",
  "The model gives $P(\\text{six})=\\tfrac16$ on each throw, so the predicted (expected) number of sixes is $n\\times\\tfrac16$. This is a long-run average, not a guaranteed count.",
  hints("The model says each of the six faces is equally likely, so first decide the probability of one particular face.",
        "The predicted count is the number of throws multiplied by the probability for a single throw.",
        "Divide the number of throws by the number of faces."),
  template={"params": {"n": {"choices": [60, 90, 120, 150, 240, 300]}}, "answer": "n/6",
            "distractors": [{"expr": "n*6"}, {"expr": "5*n/6"}, {"expr": "n/3"}]},
  answer={"unit": "", "exact": True}, marks=2),
 item(2, "mcq", 1, "State",
  "Which statement best describes a statistical model?",
  "A statistical model is a simplified mathematical description of a real-world situation, based on assumptions, that is used to describe and predict. It is not an exact copy and it does not guarantee outcomes.",
  hints("Think about why we use a model instead of studying the real situation in every detail.",
        "Decide which options claim the model is exact or certain, and whether a model can really be that.",
        "Recall the key features of a model: what it leaves out and what it must state."),
  options={"A": "A simplified mathematical description of a real situation, built on assumptions and used to make predictions",
           "B": "An exact copy of the real situation that includes every detail",
           "C": "A collection of data taken from a sample of the population",
           "D": "A rule that guarantees exactly what will happen"},
  answer="A", distractors={"B": "m1", "C": "m2", "D": "m3"}, marks=1, shuffle=True),
 item(3, "mcq", 2, "State",
  "A council wants to find the mean weekly rent paid by all 4200 tenants in a town. It surveys 150 of the tenants, chosen at random. What is the population?",
  "The population is the whole set of items of interest, here all 4200 tenants. The 150 surveyed tenants are the sample, which is used to estimate the population value.",
  hints("Ask who the council wants to know about, not who it actually asked.",
        "The population is the complete set of interest; the sample is a selection taken from it.",
        "Decide which group in the question is the complete set and which is the selection."),
  options={"A": "All 4200 tenants in the town",
           "B": "The 150 tenants who are surveyed",
           "C": "The mean weekly rent",
           "D": "The weekly rents paid by the 150 tenants surveyed"},
  answer="A", distractors={"B": "m2", "D": "m2"}, marks=1, shuffle=True),
 item(4, "mcq", 3, "Interpret",
  "A model of a fair die predicts 10 sixes in 60 throws. A student throws the die 60 times and gets 7 sixes. Which conclusion is most reasonable?",
  "The model predicts a long-run average, so the count varies by chance: a few sixes either side of 10 is ordinary in 60 throws, whereas 25 sixes would be a large gap. So 7 gives no strong reason to reject the model. Saying the model is wrong because the count is not exactly 10 treats any difference as failure, and saying the die will make up the shortfall ignores independence.",
  hints("Ask whether real results are expected to match a model's prediction exactly.",
        "Think about how far the count of sixes in 60 throws would normally stray from 10 just by chance.",
        "Remember that the throws are assumed independent, so earlier throws do not change later ones."),
  options={"A": "The model is wrong because the count is not exactly 10",
           "B": "A difference of this size is ordinary chance variation, so there is no strong reason to reject the model",
           "C": "The die is now more likely to give sixes, to make up the shortfall",
           "D": "The model is proved correct, so the assumptions need no further checking"},
  answer="B", distractors={"A": "m1", "C": "m3", "D": "m4"}, marks=1, shuffle=True),
 item(5, "mcq", 2, "State",
  "The random variable $X$ is the score when a fair die is thrown. Which statement about $X$ is correct?",
  "A random variable takes numerical values that depend on chance, so $X$ can be any of $1,\\dots,6$ and $x$ denotes one particular value. It is not something to solve for, and it has no single fixed value.",
  hints("Think about what happens to the value of $X$ each time the die is thrown.",
        "A capital letter and a lower-case letter are used for two different things.",
        "Check each option against what happens to $X$ on repeated throws."),
  options={"A": "$X$ can take the values $1,2,\\dots,6$ depending on the throw, and $x$ stands for one particular value",
           "B": "$X$ is an unknown number found by solving an equation",
           "C": "$X$ always equals the average score",
           "D": "$X$ is the whole set of throws made by one student"},
  answer="A", distractors={"B": "m5", "D": "m2"}, marks=1, shuffle=True),
 item(6, "short", 3, "State",
  "Sami models the number of heads when a coin is tossed 20 times. State two assumptions that Sami's model relies on.",
  "The usual modelling assumptions for coin tossing are that heads and tails are equally likely on each toss (the coin is fair) and that the tosses are independent, so one toss does not affect another.",
  hints("Think about what would have to be true of the coin itself.",
        "Think about how one toss relates to the next toss.",
        "One assumption concerns the coin, the other concerns how the tosses relate to each other."),
  rubric=[{"point": "the coin is fair / heads and tails are equally likely on each toss (the probability of a head is the same each time)",
           "keywords": [["fair", "equally likely", "unbiased", "equal probability", "equal chance", "same probability of", "probability of a head is the same", "probability of heads is the same", "probability of a head is constant", "constant probability"]]},
          {"point": "tosses are independent (one toss does not affect another)",
           "keywords": [["independent", "not affect", "no effect", "does not influence", "not influence", "unaffected"]]}],
  marks=2),
 item(7, "structured", 4, "Interpret",
  "A fair-die model says each score $1$ to $6$ is equally likely. A student throws a die 120 times.\n\n| Score | 1 | 2 | 3 | 4 | 5 | 6 |\n|---|---|---|---|---|---|---|\n| Frequency | 22 | 17 | 19 | 20 | 24 | 18 |\n\n(a) Calculate the frequency of each score that the model predicts.\n(b) Find the largest difference between an observed frequency and the predicted frequency.\n(c) Comment on whether the model is suitable for this die.\n(d) State one assumption of the model, in context.\n(e) Suggest how the model could be refined if the data had shown a much larger difference.",
  "The model predicts $120\\times\\tfrac16=20$ for each score. The largest difference is $|24-20|=4$ for the score 5, which is small for 120 throws, so the data are consistent with the model.",
  scheme=[
   {"mark": "B1", "point": "(a) predicted frequency $120\\times\\tfrac16=20$ for each score", "check": {"kind": "numeric", "answer": {"value": 20.0, "unit": "", "exact": True}}},
   {"mark": "B1", "point": "(b) largest difference is $|24-20|=4$ (the score 5)", "check": {"kind": "numeric", "answer": {"value": 4.0, "unit": "", "exact": True}}},
   {"mark": "B1", "point": "(c) all differences are small compared with 20, consistent with chance variation, so the model is suitable / there is no evidence to reject it"},
   {"mark": "B1", "point": "(d) any of: each score equally likely (the die is fair); throws are independent; the probability of each score is constant"},
   {"mark": "B1", "point": "(e) any of: use the observed relative frequencies as the probabilities; change the model to allow unequal probabilities for the scores"}],
  marks=5),
]
assert "$$" not in items[6]["stem"]

flash = [
 ("Define a statistical model.", "A simplified mathematical description of a real-world situation, using assumptions, that is used to describe it and to make predictions."),
 ("Define a population.", "The whole set of items or individuals of interest."),
 ("Define a sample.", "A selection of items taken from the population, used to find out about the population."),
 ("Define a random variable.", "A variable whose numerical value depends on the outcome of a chance event. A capital letter (such as $X$) names the variable and a lower-case letter (such as $x$) is a particular value."),
 ("What is an assumption in a model?", "A simplifying statement taken to be true so that the model can be built, for example that a die is fair or that throws are independent."),
 ("State the stages of the modelling process.", "Recognise the real-world situation, devise a model using assumptions, use the model to make predictions, compare the predictions with observed data, then refine the model if it is a poor fit."),
 ("Give advantages of using a model.", "It simplifies a complex situation, it is quicker and cheaper than experimenting, and it allows predictions to be made."),
 ("Give a limitation of a model.", "It is a simplification, so its predictions are only as reliable as its assumptions and may differ from what is observed."),
 ("State two assumptions when modelling the number of heads in repeated coin tosses.", "The probability of a head is the same on every toss (fair coin), and the tosses are independent."),
]
pack = {"subtopic": SUB, "spec": "S1", "version": 1, "note": NOTE,
 "outline": "A statistical model is a simplified mathematical description of a real situation, built on stated assumptions and used to describe it and to make predictions. The modelling process is: recognise the situation, devise a model with assumptions, use it to predict, compare the predictions with observed data, then refine. Key terms: the **population** is the whole set of interest and a **sample** is a selection from it. A **random variable** $X$ has numerical values that depend on chance, with $x$ a particular value. Data vary by chance about the model's prediction, so small gaps are expected and only large, systematic gaps suggest refining. Assumptions such as a fair die, $P(\\text{each face})=\\tfrac16$, and independent throws must be stated in context.",
 "misconceptions": misc, "worked": worked, "items": items,
 "flashcards": [{"id": f"fc{i+1}", "kc": K, "front": f, "back": b} for i, (f, b) in enumerate(flash)],
 "diagrams": []}
out = ROOT / "build/out/packs/S1/S1-1.json"
out.write_text(json.dumps(pack, ensure_ascii=False, indent=1))

note = r'''---
tags: [stem-tutor/lesson, S1]
spec: "S1"
subtopic: "S1-1"
kcs: ["S1-1.1"]
---
# 1 Mathematical models in probability and statistics

> [!abstract] In one breath
> A statistical model is a simplified, assumption-based mathematical description of a real situation, used to describe it and predict what will happen. You build it, use it, compare its predictions with real data, and refine it if the fit is poor.

## Key ideas

**Statistical model**: a simplified mathematical description of a real-world situation, using assumptions, used to describe it and to make predictions. Simplifying is the point: a model that included every detail would be no easier to use than reality.

**Population**: the whole set of items or individuals of interest. **Sample**: a selection of items taken from the population, used to find out about it. A value found from a sample only estimates the population value, and it changes from sample to sample.

**Random variable**: a variable whose numerical value depends on the outcome of a chance event. A capital letter names it and a lower-case letter is one particular value: $X$ is the score on a fair die, and $x=4$ is one value it can take. For a fair die

$$P(X=x)=\frac16,\qquad x=1,2,\dots,6.$$

**Assumptions**: simplifying statements taken to be true so the model can be built, such as "the die is fair (each score is equally likely)" and "the throws are independent (one throw does not affect the next)". Predictions are only as reliable as the assumptions.

```mermaid
graph LR
  A["Real-world situation"] --> B["Devise a model (state assumptions)"]
  B --> C["Use the model to make predictions"]
  C --> D["Compare with observed data"]
  D -->|"poor fit"| E["Refine the model"]
  E --> B
  D -->|"good fit"| F["Model accepted for this purpose"]
```

**Prediction versus observation**: a model gives a predicted value, but real data vary by chance around it. For 60 throws of a fair die the model predicts $60\times\tfrac16=10$ sixes. Getting 7 or 13 is ordinary variation, whereas 25 sixes is a large gap that suggests the die is not fair. Over very many trials the relative frequency settles near the model probability.

**Advantages**: a model simplifies a complex situation, is quicker and cheaper than experimenting, and allows predictions. **Limitations**: it is a simplification, so its results are only as good as its assumptions.

## Method

1. Identify the real situation and the quantity of interest, and name the random variable.
2. State the assumptions in context.
3. Use the model to calculate a prediction, such as a probability or an expected count.
4. Compare the prediction with observed data: small differences are chance, large systematic ones suggest the model is unsuitable.
5. Refine: change an assumption or the probabilities, then test again.

> [!example]- Worked example
> A student throws a die 120 times: scores $1$ to $6$ occur $22,17,19,20,24,18$ times. The model says each score is equally likely. Comment on the model.
>
> 1. Find the predicted frequency for each score:
> $$120\times\tfrac16=20$$
>    *(Each score has probability $\tfrac16$ under the model, so multiply by the number of throws.)*
> 2. Find the differences from 20: $2,3,1,0,4,2$. The largest is $4$, for the score 5.
>    *(Compare every observed value with the prediction, not just the highest one.)*
> 3. Conclude in context: all the differences are small compared with 20, which is consistent with chance variation, so the fair-die model is suitable and there is no evidence to reject it.
>    *(A comment needs a reason from the numbers and a conclusion about the model, not just "close".)*

## Traps

- **Trap:** Saying the model is wrong because the observed count is not exactly the predicted count. **Why it's wrong:** real data vary by chance about the prediction. **Instead:** judge whether the difference is small or large compared with the prediction.
- **Trap:** Thinking a six is "due" after a run without one. **Why it's wrong:** throws are assumed independent, so the probability stays $\tfrac16$. **Instead:** treat every throw as a fresh trial.
- **Trap:** Calling the sample the population. **Why it's wrong:** the population is the whole set of interest and the sample is only a selection from it. **Instead:** ask who the question is about, then who was actually measured.
- **Trap:** Treating $X$ as an unknown to solve for. **Why it's wrong:** $X$ is a variable that takes different values by chance. **Instead:** write $X$ for the variable and $x$ for a particular value.
- **Trap:** Treating assumptions as proven facts. **Why it's wrong:** they are simplifications that may be only approximately true. **Instead:** state them and test them against data.

## Exam technique

- *State* an assumption in context ("the die is fair", "the tosses are independent") rather than saying "the model is random".
- *Comment* or *Explain* on suitability needs a reason using the numbers, then a conclusion about the model.
- A refinement must say what to change in the model, such as using observed relative frequencies as the probabilities. Collecting more data only re-tests the model.
- Avoid "the model is perfect" or "the model is useless": a model is judged by how well it fits, not by being exact.
- Use the wording of the question (die, coin, tenants) in every answer, not a general phrase.

## Links
Leads to [[2 Representation and summary of data]]
'''
np = ROOT / "build/out/notes" / NOTE
np.parent.mkdir(parents=True, exist_ok=True)
np.write_text(note)
print("ok", len(note.split()), "words")
