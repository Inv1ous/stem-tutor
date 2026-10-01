"""Generate the S1-4 tutor pack; all numerical keys and distractors are calculated here."""
from __future__ import annotations

import json
import math
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "plugin/stem-tutor/skills/tutor/scripts"))
from tutorlib import packs  # noqa: E402

K1, K2, K3 = "S1-4.1", "S1-4.2", "S1-4.3"
items = []


def add(kcs, kind, difficulty, command_word, stem, explanation, hints, **more):
    item = dict(id=f"S1-4-i{len(items)+1:02d}", kcs=kcs, kind=kind,
                difficulty=difficulty, command_word=command_word,
                source={"type": "generated"}, stem=stem, marks=more.pop("marks", 1),
                explanation=explanation, hints=hints, **more)
    items.append(item)


def mcq(kc, difficulty, stem, options, answer, explanation, hints, distractors=None, command="State"):
    add([kc], "mcq", difficulty, command, stem, explanation, hints,
        options=dict(zip("ABCD", options)), answer="ABCD"[answer],
        distractors={"ABCD"[i]: m for i, m in (distractors or {}).items()}, shuffle=True)


def numeric(kc, difficulty, stem, value, unit, explanation, hints, distractors=(), command="Calculate", sf=(2, 3)):
    add([kc], "numeric", difficulty, command, stem, explanation, hints,
        answer={"value": value, "unit": unit, "sf_ok": list(sf)},
        distractors=[{"value": v, "misconception": m} for v, m in distractors])


misconceptions = [
    dict(id="m1", kc=K1, statement="The regression line passes through the origin.",
         refutation="The least-squares line passes through $(\\bar x,\\bar y)$; its intercept is $\\bar y-b\\bar x$, usually nonzero.",
         contrast="Find $b=S_{xy}/S_{xx}$, then $a=\\bar y-b\\bar x$.", source="research"),
    dict(id="m2", kc=K1, statement="Swapping explanatory and response variables gives the same regression line.",
         refutation="Regressing $y$ on $x$ minimises vertical squared residuals; regressing $x$ on $y$ minimises horizontal ones.",
         contrast="Choose the response variable first, then calculate its regression on the explanatory variable.", source="research"),
    dict(id="m3", kc=K2, statement="A regression equation is equally reliable outside the observed range.",
         refutation="The relationship beyond the observed explanatory values is unobserved and may change.",
         contrast="Interpolate within the observed range; label outside-range predictions as extrapolation.", source="research"),
    dict(id="m4", kc=K3, statement="A large correlation coefficient proves that one variable causes the other.",
         refutation="Association alone cannot establish causation; confounding variables or coincidence may explain it.",
         contrast="Describe the strength and direction of linear association only.", source="research"),
    dict(id="m5", kc=K3, statement="A PMCC near zero means the variables have no relationship.",
         refutation="PMCC measures linear association; a curved relationship can have PMCC near zero.",
         contrast="Inspect the scatter diagram for non-linear patterns and outliers.", source="research"),
]

# Least squares: each template is checked at multiple seeded instantiations below.
add([K1], "numeric", 3, "Calculate",
    "For regression of $y$ on $x$, $S_{xx}=[[sxx]]$ and $S_{xy}=[[sxy]]$. Calculate the gradient $b$.",
    "Use $b=S_{xy}/S_{xx}$. Dividing in the reverse order is not the regression gradient of $y$ on $x$.",
    ["Identify which variable is the response.", "Use the least-squares gradient formula.", "Put $S_{xy}$ in the numerator."],
    answer={"unit": "", "sf_ok": [2, 3]},
    template={"params": {"sxx": {"choices": [20, 25, 40, 50]}, "sxy": {"choices": [5, 10, 15]}},
              "answer": "sxy/sxx", "distractors": [{"expr": "sxx/sxy", "misconception": "m2"}],
              "constraints": ["sxx>sxy"]})

xbar, ybar, sxx, sxy = 4.0, 11.0, 20.0, 30.0
b = sxy / sxx
a = ybar - b*xbar
numeric(K1, 3, f"For $y$ on $x$, $\\bar x={xbar:g}$, $\\bar y={ybar:g}$, $S_{{xx}}={sxx:g}$ and $S_{{xy}}={sxy:g}$. Find the intercept $a$ of $y=a+bx$.",
        a, "", "First $b=30/20=1.5$, then $a=11-1.5(4)=5$; the line passes through the means.",
        ["The intercept is not generally zero.", "Find the gradient before the intercept.", "Substitute the means into $\\bar y=a+b\\bar x$."],
        [(0.0, "m1")], command="Find")

mcq(K1, 2, "Which point must lie on the least-squares regression line of $y$ on $x$?",
    ["$(\\bar x,\\bar y)$", "$(0,0)$", "$(S_{xx},S_{xy})$", "$(\\bar y,\\bar x)$"], 0,
    "The line is $y-\\bar y=b(x-\\bar x)$, so it passes through $(\\bar x,\\bar y)$. It need not pass through the origin.",
    ["Think about the sample means.", "Use the intercept formula.", "Set $x$ equal to its sample mean."], {1: "m1", 3: "m2"})

mcq(K1, 2, "When fitting $y$ on $x$ by least squares, which distances are squared and summed?",
    ["Vertical distances from points to the line", "Horizontal distances from points to the line",
     "Distances from points to the origin", "Distances along the fitted line"], 0,
    "The residual is observed $y$ minus predicted $y$ at each $x$, a vertical distance. Horizontal distances belong to fitting $x$ on $y$.",
    ["Identify the response variable.", "Compare observed and fitted responses at each explanatory value.", "The $x$ coordinate stays fixed for each residual."], {1: "m2"})

add([K1], "structured", 4, "Find",
    "Six paired observations give $\\bar x=3$, $\\bar y=8$, $S_{xx}=12$, $S_{xy}=18$. Find the regression line of $y$ on $x$ and state a point to use when drawing it.",
    "The slope is $18/12=1.5$ and intercept is $8-1.5(3)=3.5$. Plot $(3,8)$, then use the slope to draw the line.",
    ["Find the slope from the centred sums.", "Use the fact that the line passes through the mean point.", "Write $y=a+bx$ and substitute both means."], marks=4,
    scheme=[{"mark": "M1", "point": "Use $b=S_{xy}/S_{xx}$."},
            {"mark": "A1", "point": "Obtain $b=1.5$.", "check": {"kind": "numeric", "answer": {"value": 18/12, "unit": "", "sf_ok": [2, 3]}}},
            {"mark": "A1", "point": "Obtain $y=3.5+1.5x$."},
            {"mark": "B1", "point": "Plot $(3,8)$ on the line."}])

mcq(K1, 3, "A scatter diagram trends downward from left to right. Which sign should the regression gradient of $y$ on $x$ have?",
    ["Negative", "Positive", "Zero", "Impossible to tell from the trend"], 0,
    "As $x$ rises, $y$ tends to fall, so the fitted gradient is negative.",
    ["Follow the general direction of the points.", "Ask whether the response rises as $x$ rises.", "Consider the sign of change in $y$ divided by change in $x$."], {})

# Explanatory and response variables, interpolation and changes of scale.
mcq(K2, 2, "A researcher uses weekly study hours to predict test score. Which variable belongs on the horizontal axis?",
    ["Weekly study hours", "Test score", "Both on the horizontal axis", "Neither variable"], 0,
    "Study hours are explanatory, so they go on the horizontal axis; score is the predicted response.",
    ["Identify what is being used to predict.", "The explanatory variable is the input.", "Put the input on the $x$ axis."], {1: "m2"})

mcq(K2, 3, "A line was fitted using temperatures from $12$ to $28\\,^{\\circ}\\mathrm{C}$. Which estimate is interpolation?",
    ["At $20\\,^{\\circ}\\mathrm{C}$", "At $35\\,^{\\circ}\\mathrm{C}$", "At $0\\,^{\\circ}\\mathrm{C}$", "At $40\\,^{\\circ}\\mathrm{C}$"], 0,
    "Only $20\\,^{\\circ}\\mathrm{C}$ lies in the observed range. The other estimates extrapolate beyond it.",
    ["Locate the observed range.", "Interpolation stays between observed extremes.", "Compare each temperature with 12 and 28."], {1: "m3", 2: "m3", 3: "m3"})

mcq(K2, 3, "A fitted line predicts crop yield from rainfall observed between $30$ and $80\\,\\mathrm{mm}$. Why is a prediction at $120\\,\\mathrm{mm}$ risky?",
    ["The trend may change beyond the observed rainfall", "The regression line must pass through the origin",
     "The PMCC must become zero outside the range", "Predictions are impossible within the observed range"], 0,
    "Rainfall of $120\\,\\mathrm{mm}$ is outside the data range; the linear pattern may not persist. A line need not pass through the origin.",
    ["Compare the new rainfall with the sample range.", "Consider the evidence for the trend outside the sample.", "Ask whether the relationship was observed above 80 mm."], {1: "m1"}, command="Explain")

numeric(K2, 3, "A regression line for response $y$ on explanatory $x$ is $y=4+2.5x$. Predict $y$ when $x=6$.",
        4+2.5*6, "", "Substitute $x=6$: $y=4+2.5(6)=19$.",
        ["The given value is for the explanatory variable.", "Substitute it into the fitted equation.", "Multiply before adding the intercept."],
        [(2.5*6, "m1")])

numeric(K2, 4, "The fitted line is $y=7+3x$. A new explanatory variable is $u=2x+1$. Find the coefficient of $u$ when the line is written as $y=A+Bu$.",
        3/2, "", "Since $x=(u-1)/2$, $y=7+3(u-1)/2=5.5+1.5u$.",
        ["Rewrite $x$ in terms of $u$.", "Substitute into the original line.", "Collect the term multiplying $u$."],
        [(3*2, "m2")], command="Find")

add([K2], "short", 4, "Interpret",
    "A model for distance travelled $d$ (km) from fuel used $f$ (litres) is $d=12+15f$. Interpret the gradient in context and say whether using $f=100$ is safe when the data used $f=2$ to $10$.",
    "Each extra litre of fuel is associated with a predicted 15 km increase in distance. A 100-litre input is extrapolation far outside the observed range.",
    ["Attach units to the gradient.", "Treat fuel as the explanatory variable.", "Compare 100 litres with the observed interval."], marks=2,
    rubric=[{"point": "For each additional litre of fuel, predicted distance rises by 15 km.",
             "keywords": [["litre", "liter"], ["15"], ["km", "kilometre", "kilometer"]]},
            {"point": "Prediction at 100 litres is unreliable extrapolation beyond the observed range.",
             "keywords": [["extrapolation", "outside", "beyond"], ["range", "data", "observed"]]}])

# Product moment correlation coefficient.
mcq(K3, 2, "A PMCC of $r=-0.92$ suggests what about the observed variables?",
    ["Strong negative linear association", "Strong positive linear association",
     "Weak negative linear association", "A causal effect"], 0,
    "The magnitude $0.92$ indicates a strong linear association and the minus sign gives its negative direction; it does not prove causation.",
    ["Separate magnitude from sign.", "Use magnitude for strength and sign for direction.", "Recall that correlation alone does not prove cause."], {3: "m4"}, command="Interpret")

numeric(K3, 3, "For paired data, $S_{xx}=25$, $S_{yy}=36$ and $S_{xy}=18$. Calculate the PMCC $r$.",
        18/math.sqrt(25*36), "", "Use $r=S_{xy}/\\sqrt{S_{xx}S_{yy}}=18/30=0.6$.",
        ["Use all three centred sums.", "The denominator is the square root of a product.", "Find $\\sqrt{25\\times36}$ first."])

mcq(K3, 2, "Which value cannot be a product moment correlation coefficient?",
    ["$1.2$", "$-0.8$", "$0$", "$1$"], 0,
    "PMCC is always between $-1$ and $1$ inclusive, so $1.2$ is impossible.",
    ["Recall the allowed interval.", "Compare each number with both endpoints.", "Check which magnitude exceeds one."], {})

mcq(K3, 3, "A scatter diagram follows a clear U-shaped curve and has $r$ close to zero. What is the sound conclusion?",
    ["There is a non-linear relationship that PMCC does not capture", "The variables are unrelated",
     "One variable causes the other", "The regression gradient must be positive"], 0,
    "A PMCC near zero rules out strong linear association, not a curved relationship. The graph supplies evidence of a U-shaped pattern.",
    ["Look at the shape, not just the coefficient.", "PMCC measures linear association.", "Decide whether a straight line describes the U shape."], {1: "m5", 2: "m4"}, command="Explain")

mcq(K3, 3, "Two variables have $r=0.85$. Which statement is justified?",
    ["They have strong positive linear association", "Increasing one causes the other to increase",
     "Exactly $85\\%$ of observations lie on a line", "Their regression line passes through the origin"], 0,
    "A positive PMCC near one means strong positive linear association. Correlation alone cannot establish cause.",
    ["Read the sign and magnitude.", "Avoid adding a causal claim.", "Describe association and its linear direction."], {1: "m4", 3: "m1"}, command="Interpret")

add([K3], "short", 4, "Explain",
    "A dataset has a PMCC of $0.94$, but one point lies far from the main cluster. Explain one limitation of reporting only $r$.",
    "An outlier can substantially change $r$, so the scatter diagram should be inspected before describing the linear association.",
    ["Consider the unusual point.", "Think about how sensitive a summary statistic can be.", "Mention the scatter diagram and possible influence of the outlier."], marks=1,
    rubric=[{"point": "An outlier may strongly influence $r$; inspect the scatter diagram.",
             "keywords": [["outlier", "unusual point"], ["affect", "influence", "change", "distort"]]}])

worked_slope = 24/16
worked_intercept = 9-worked_slope*4
faded_slope = 15/10
faded_intercept = 10-faded_slope*2
worked = [dict(id="we1", kc=K1,
    problem="For $y$ on $x$, $\\bar x=4$, $\\bar y=9$, $S_{xx}=16$, $S_{xy}=24$. Find the least-squares line.",
    steps=[{"do": "$b=S_{xy}/S_{xx}=24/16=1.5$.", "why": "The response is $y$, so divide the cross-deviation sum by $S_{xx}$.",
            "check": {"kind": "numeric", "answer": {"value": worked_slope, "unit": "", "sf_ok": [2, 3]}}},
           {"do": "$a=\\bar y-b\\bar x=9-1.5(4)=3$.", "why": "The fitted line passes through the mean point $(4,9)$.",
            "check": {"kind": "numeric", "answer": {"value": worked_intercept, "unit": "", "sf_ok": [2, 3]}}},
           {"do": "The line is $y=3+1.5x$; at $x=4$ it gives $y=9$.", "why": "Substitution checks the centroid condition."}],
    faded={"id": "we1f", "problem": "For $y$ on $x$, $\\bar x=2$, $\\bar y=10$, $S_{xx}=10$, $S_{xy}=15$. Find the intercept after calculating the slope.",
           "answer": {"value": faded_intercept, "unit": "", "sf_ok": [2, 3]}, "blank_from": 1})]

flashcards = [
    dict(id="fc1", kc=K1, front="What does the least-squares regression line of $y$ on $x$ minimise?", back="The sum of squared vertical residuals, $\\sum(y_i-\\hat y_i)^2$."),
    dict(id="fc2", kc=K1, front="Which point lies on the regression line of $y$ on $x$?", back="The mean point $(\\bar x,\\bar y)$."),
    dict(id="fc3", kc=K2, front="Define explanatory and response variables.", back="The explanatory variable is used to predict the response variable; the response is the variable predicted."),
    dict(id="fc4", kc=K2, front="What is extrapolation?", back="Using a fitted relationship to predict beyond the observed range of the explanatory variable."),
    dict(id="fc5", kc=K3, front="What does the product moment correlation coefficient measure?", back="The strength and direction of linear association between two variables; $-1\\le r\\le1$."),
    dict(id="fc6", kc=K3, front="Can a PMCC near zero rule out every relationship?", back="No. It indicates little linear association; a non-linear relationship may remain."),
]

pack = dict(subtopic="S1-4", spec="S1", version=1,
    note="Subjects/Maths/S1 Statistics 1/4 Correlation and regression.md",
    outline="Plot paired values on a scatter diagram, with explanatory variable on the horizontal axis. For least-squares regression of $y$ on $x$, calculate $b=S_{xy}/S_{xx}$ and $a=\\bar y-b\\bar x$; the line passes through $(\\bar x,\\bar y)$. Use it to predict the response within the observed explanatory range; outside that range is extrapolation. The product moment correlation coefficient $r=S_{xy}/\\sqrt{S_{xx}S_{yy}}$ describes the strength and direction of linear association, from $-1$ to $1$. Inspect the scatter diagram: outliers and curves limit the usefulness of a line and of $r$; correlation does not establish causation.",
    misconceptions=misconceptions, worked=worked, items=items, flashcards=flashcards, diagrams=[])

# Check every computed fixed answer, and exercise each template with the actual runtime evaluator.
assert (b, a, worked_slope, worked_intercept, faded_slope, faded_intercept) == (1.5, 5.0, 1.5, 3.0, 1.5, 7.0)
for item in items:
    if item.get("template"):
        for seed in range(100):
            concrete = packs.instantiate(item, random.Random(seed))
            value = concrete["answer"]["value"]
            assert math.isfinite(value)
            assert all(abs(d["value"]-value) > .02*max(abs(value), 1e-12) for d in concrete["distractors"])
    elif item["kind"] == "numeric":
        assert math.isfinite(item["answer"]["value"])
        assert all(d["value"] != item["answer"]["value"] for d in item["distractors"])

path = ROOT / "build/out/packs/S1/S1-4.json"
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(json.dumps(pack, ensure_ascii=False, indent=1) + "\n")
print(path, len(items), "items")
