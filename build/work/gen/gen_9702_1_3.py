"""Generator for content pack 9702-1.3 (Errors and uncertainties). Content as data, every number computed here."""
import json, math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SUB = "9702-1.3"
K1, K2, K3 = f"{SUB}.1", f"{SUB}.2", f"{SUB}.3"
NOTE = "Subjects/9702 Physics/01 Physical quantities and units/1.3 Errors and uncertainties.md"
UNIT_G = r"$\mathrm{m\,s^{-2}}$"

def close(a, b, t=1e-9): assert abs(a - b) <= t * max(1, abs(b)), (a, b)

# ---------------------------------------------------------------- verified numbers
# past-paper answers
close(305 * 1.01, 308.05, 1e-4)                       # p01 true width 308
close(1.03 - (-0.05), 1.08)                           # p07 diameter
close(0.01 / 5.00 * 100 * 3, 0.6)                     # p08
mean_i = (3.04 + 3.08) / 2; close(mean_i, 3.06)
hi, lo = 1.01 * 3.08, 0.99 * 3.04
assert round(hi, 2) == 3.11 and round(lo, 2) == 3.01 and round((hi - lo) / 2, 2) == 0.05   # p09
pm = 0.005 / 0.506 * 100; pd = 0.02 / 2.20 * 100
close(round(pm + 3 * pd, 1), 3.7); close(round(pm + pd, 1), 1.9); close(round(pm + 2 * pd, 1), 2.8)   # p10
a = 2 * 16.5 / 15.0 ** 2; pa = 0.1 / 16.5 * 100 + 2 * 1.0 / 15.0 * 100
assert round(a, 2) == 0.15 and round(pa / 100 * a, 2) == 0.02
assert round((0.1 / 16.5 * 100 + 1.0 / 15.0 * 100) / 100 * a, 2) == 0.01     # p11 forgetting the square -> 0.01 (C)
assert (2 + 2) / (250 - 225) * 100 == 16 and round(4 / 250 * 100, 1) == 1.6 and 2 / 25 * 100 == 8   # p12

# worked example
def g_of(l, T): return 4 * math.pi ** 2 * l / T ** 2
W_l, W_dl, W_T, W_dT = 0.420, 0.002, 1.30, 0.02
W_g = g_of(W_l, W_T); W_pl = W_dl / W_l * 100; W_pT = W_dT / W_T * 100
W_pg = W_pl + 2 * W_pT; W_dg = W_pg / 100 * W_g
assert round(W_g, 2) == 9.81 and round(W_dg, 2) == 0.35, (W_g, W_dg)
F_l, F_dl, F_T, F_dT = 0.650, 0.002, 1.62, 0.02
F_g = g_of(F_l, F_T); F_pg = F_dl / F_l * 100 + 2 * F_dT / F_T * 100; F_dg = F_pg / 100 * F_g
F_dg2 = float(f"{F_dg:.2g}")

# structured numbers
z_read = [0.82, 0.84, 0.83, 0.83, 0.85]; mean_z = sum(z_read) / 5; corr = mean_z + 0.03
close(mean_z, 0.834); close(corr, 0.864)
X = [2.31, 2.30, 2.32, 2.31]; Y = [1.92, 2.09, 2.04, 1.95]
close(sum(Y) / 4, 2.00); close(max(X) - min(X), 0.02); close(max(Y) - min(Y), 0.17); close(sum(X) / 4, 2.31)
d, dd, R, dR, L, dL = 0.32e-3, 0.01e-3, 4.7, 0.1, 1.000, 0.002
rho = math.pi * d ** 2 * R / (4 * L); pd_, pR, pL = dd / d * 100, dR / R * 100, dL / L * 100
prho = 2 * pd_ + pR + pL; drho = prho / 100 * rho
assert round(rho * 1e7, 1) == 3.8 and round(prho, 1) == 8.6 and round(drho * 1e7, 1) == 0.3, (rho, prho, drho)
# mcq sets
close(sum([9.1, 10.5, 9.4, 10.2]) / 4, 9.8); close(sum([8.4, 10.9, 7.9, 9.2]) / 4, 9.1)
assert round(12.5 - 8.3, 1) == 4.2 and round(0.2 + 0.1, 1) == 0.3

# ---------------------------------------------------------------- misconceptions
M = [
 {"id": "m1", "kc": K1, "statement": "Repeating a measurement and averaging removes all errors, including systematic errors.",
  "refutation": "Averaging works because random errors fall above and below the true value in equal measure and partly cancel. A systematic error pushes every reading the same way by the same amount, so the mean carries exactly the same error.",
  "contrast": "Ten readings of a micrometer with a zero error of $+0.03\\ \\mathrm{mm}$ average to a value still $0.03\\ \\mathrm{mm}$ too large; only a correction or recalibration removes it.",
  "source": "research"},
 {"id": "m2", "kc": K1, "statement": "Getting the direction or sign of a systematic error wrong: adding a negative zero error instead of subtracting it, or thinking a ruler with graduations too far apart reads too high.",
  "refutation": "The corrected reading is reading minus zero error, with the sign kept. If graduations are too far apart, each one is longer than a true unit, so fewer are counted and the ruler reads too low.",
  "contrast": "Zero error $-0.05\\ \\mathrm{mm}$ and reading $1.03\\ \\mathrm{mm}$ give $1.03-(-0.05)=1.08\\ \\mathrm{mm}$, not $0.98\\ \\mathrm{mm}$.",
  "source": "ER 9702 s21 P11 Q5"},
 {"id": "m3", "kc": K2, "statement": "Precision and accuracy are the same thing, or precise means close to the true value.",
  "refutation": "Precise means repeated readings are close to each other (small scatter). Accurate means close to the true value. Readings can be tightly grouped yet all wrong because of a systematic error.",
  "contrast": "Readings $9.10,\\ 9.12,\\ 9.11$ for $g=9.81\\ \\mathrm{m\\,s^{-2}}$ are precise but not accurate.",
  "source": "ER 9702 w22 P21 Q1"},
 {"id": "m4", "kc": K3, "statement": "Ignoring the power when a quantity is squared or cubed: the percentage uncertainty is just added once instead of being multiplied by the power.",
  "refutation": "A power means the same quantity appears several times in the product, so its fractional uncertainty is counted that many times. For $x^n$ the percentage uncertainty is $n$ times that of $x$.",
  "contrast": "$V\\propto d^3$ with $0.2\\%$ uncertainty in $d$ gives $3\\times0.2=0.6\\%$ in $V$, not $0.2\\%$.",
  "source": "ER 9702 s22 P13 Q4"},
 {"id": "m5", "kc": K3, "statement": "Uncertainties can be subtracted: subtracting when values are subtracted or divided, or using one reading's uncertainty (or the wrong base) for a difference.",
  "refutation": "Uncertainties always add, whichever operation combines the values. For a difference add the absolute uncertainties of both readings, and take the percentage uncertainty relative to the difference itself, not to one of the readings.",
  "contrast": "Extension $=250-225=25\\ \\mathrm{mm}$ with $\\pm2\\ \\mathrm{mm}$ on each reading has uncertainty $\\pm4\\ \\mathrm{mm}$, so $\\frac{4}{25}\\times100=16\\%$, not $\\frac{4}{250}$ or $\\frac{2}{25}$.",
  "source": "ER 9702 w22 P12 Q3"},
]

# ---------------------------------------------------------------- items
items = []
def opts(*v): return dict(zip("ABCD", v))
def past(n, ref, kcs, diff, cw, stem, options, ans, expl, hints, dis=None, image=None, qid=None, marks=1):
    it = {"id": f"{SUB}-p{n:02d}", "kcs": kcs, "kind": "mcq", "difficulty": diff, "command_word": cw,
          "source": {"type": "past", "ref": ref}, "stem": stem, "options": options, "answer": ans, "marks": marks,
          "explanation": expl, "hints": hints}
    if dis: it["distractors"] = dis
    if image: it["image"] = image
    items.append(it)
def gen(kind, diff, cw, kcs, stem, expl, hints, **kw):
    n = sum(1 for i in items if i["source"]["type"] == "generated") + 1
    it = {"id": f"{SUB}-i{n:02d}", "kcs": kcs, "kind": kind, "difficulty": diff, "command_word": cw,
          "source": {"type": "generated"}, "stem": stem, **kw, "explanation": expl, "hints": hints}
    if kind == "mcq": it["shuffle"] = True
    items.append(it)

# --- 12 past MCQs
past(1, "CAIE 9702 · Nov 2021 · P13 · Q5", [K1], 3, "Identify",
     "After measuring the width of a shelf to be 305 mm, it is found that the graduations on the ruler used are 1.0% further apart than they should be. Which type of measurement error is this and what is the true width of the shelf?",
     opts("random, 302 mm", "random, 308 mm", "systematic, 302 mm", "systematic, 308 mm"), "D",
     "Graduations that are too far apart make every reading wrong by the same factor, so this is a systematic error. Each graduation is longer than a true millimetre, so the ruler reads too low and the true width is $305\\times1.01=308\\ \\mathrm{mm}$; option C wrongly assumes the ruler reads too high.",
     ["Does the error act the same way on every reading, or does it vary unpredictably?", "If each division on the ruler is longer than it should be, decide whether you count more or fewer divisions along the shelf.", "The true width is the reading multiplied by a factor of 1.01, or divided by it: pick the direction that matches an under-reading ruler."],
     {"C": "m2"}, image="Assets/mcq/9702_w21_13_q5.png")
past(2, "CAIE 9702 · Nov 2023 · P13 · Q3", [K1], 2, "Identify",
     "A set of repeated measurements is made of a fixed quantity. An average of these measurements is calculated. What is the effect of averaging on the random error and the systematic error in the measurements?",
     opts("Random error and systematic error are both reduced.", "Random error and systematic error are both unaffected.", "Random error is reduced but systematic error is unaffected.", "Random error is unaffected but systematic error is reduced."), "C",
     "Random deviations are equally likely to be above or below the true value, so they partly cancel in a mean. A systematic error is the same on every reading, so it is still fully present in the average; option A is the common mistake of thinking repeats fix everything.",
     ["Which kind of error scatters readings on both sides of the true value?", "Averaging helps only when deviations can cancel each other.", "Ask whether an error that is identical on every reading can cancel when you average."],
     {"A": "m1"})
past(3, "CAIE 9702 · Nov 2021 · P11 · Q5", [K1], 3, "Identify",
     "Four possible sources of error in a series of measurements are listed. 1: an analogue meter whose scale is read from different angles. 2: a meter which always measures 5% too high. 3: a meter with a needle that is not frictionless, so the needle sometimes sticks slightly. 4: a meter with a zero error. Which errors are random and which are systematic?",
     opts("random: 1 and 2; systematic: 3 and 4", "random: 1 and 3; systematic: 2 and 4", "random: 2 and 4; systematic: 1 and 3", "random: 3 and 4; systematic: 1 and 2"), "B",
     "Reading a scale from different angles (parallax) and a needle that sticks sometimes vary unpredictably, so both are random. A meter that is always 5% too high and a zero error give the same kind of shift every time, so both are systematic.",
     ["Classify each source separately: does it change unpredictably from reading to reading?", "A fixed offset or a fixed scale factor is the signature of a systematic error.", "Put the varying sources together and the constant sources together, then match the pairs to an option."],
     image="Assets/mcq/9702_w21_11_q5.png")
past(4, "CAIE 9702 · Nov 2019 · P13 · Q4", [K1], 2, "Identify",
     "What could reduce systematic errors?",
     opts("averaging a large number of measurements", "careful calibration of measuring instruments", "reducing the sample size", "repeating measurements"), "B",
     "Calibrating an instrument against a known standard finds and removes a constant offset or scale error. Averaging or repeating readings (options A and D) only reduces random scatter and leaves a systematic error untouched.",
     ["A systematic error is the same every time, so more of the same measurement will not remove it.", "What could you check the instrument against to expose a constant offset?", "Compare the instrument with a known standard."],
     {"A": "m1", "D": "m1"})
past(5, "CAIE 9702 · Nov 2025 · P12 · Q2", [K2], 2, "Identify",
     "What describes a set of data with a high precision?",
     opts("data measured using equipment with small scale divisions", "data that is close to the accepted value", "data with each value having a low uncertainty", "data with repeats that are close to each other"), "D",
     "High precision means repeated readings agree closely with each other (small scatter). Option B describes accuracy, which is how close a value is to the accepted value, and is the confusion examiners report most often.",
     ["Precision is judged from a set of repeats, not from a single value.", "It does not need the true value to be known.", "Look for the option about how the repeats compare with each other."],
     {"B": "m3"})
past(6, "CAIE 9702 · Nov 2020 · P12 · Q4", [K2], 2, "Identify",
     "A student wishes to measure a distance of about 10 cm to a precision of 0.01 cm. Which measuring instrument should be used?",
     opts("metre rule", "micrometer", "tape measure", "vernier calipers"), "D",
     "Vernier calipers read to 0.01 cm and open wide enough for 10 cm. A micrometer reads more finely but only spans about 2.5 cm, and a metre rule or tape measure reads only to about 0.1 cm.",
     ["What is the smallest reading each instrument can give?", "You also need the instrument to be able to open or reach 10 cm.", "Rule out instruments that are too coarse, then rule out the one with too small a range."])
past(7, "CAIE 9702 · Jun 2021 · P11 · Q5", [K1, K3], 4, "Determine",
     "A micrometer screw gauge is used to measure the diameter of a wire. The reading on the micrometer with the jaws closed is (−0.05 ± 0.02) mm. The reading with the wire in position between the two jaws is (+1.03 ± 0.02) mm. What is the diameter of the wire?",
     opts("(0.98 ± 0.02) mm", "(1.08 ± 0.02) mm", "(0.98 ± 0.04) mm", "(1.08 ± 0.04) mm"), "D",
     "The jaws move from the closed reading to the wire reading, so the diameter is $1.03-(-0.05)=1.08\\ \\mathrm{mm}$. Two readings are subtracted, so their absolute uncertainties add to $\\pm0.04\\ \\mathrm{mm}$; option C loses the sign of the zero error and gives $0.98\\ \\mathrm{mm}$.",
     ["Subtract the zero error from the reading and keep its sign.", "Both readings carry an uncertainty; think about what happens to the uncertainty when values are subtracted.", "A negative zero error means the true diameter is larger than the reading, and the absolute uncertainties are added."],
     {"C": "m2", "B": "m5"})
past(8, "CAIE 9702 · Jun 2022 · P13 · Q4", [K3], 3, "Calculate",
     "A micrometer screw gauge is used to measure the diameter of a small uniform steel sphere. The measurement of the diameter is 5.00 mm ± 0.01 mm. What is the percentage uncertainty in the calculated volume of the sphere, using these values?",
     opts("0.2%", "0.4%", "0.6%", "1.2%"), "C",
     "The percentage uncertainty in the diameter is $\\frac{0.01}{5.00}\\times100=0.2\\%$. Volume is proportional to the cube of the diameter, so it is $3\\times0.2=0.6\\%$; option A, the second most popular, forgets the cube.",
     ["Start with the percentage uncertainty in the diameter itself.", "Volume of a sphere depends on the diameter raised to what power?", "Multiply the percentage uncertainty in the diameter by that power."],
     {"A": "m4", "B": "m4"})
past(9, "CAIE 9702 · Nov 2022 · P13 · Q3", [K3], 4, "Determine",
     "A digital meter is used to measure the current in an electric circuit. The reading on the meter fluctuates (varies) between 3.04 A and 3.08 A. The readings on the meter have an accuracy of ±1%. What is the true value of the current, with its uncertainty?",
     opts("(3.06 ± 0.02) A", "(3.06 ± 0.04) A", "(3.06 ± 0.05) A", "(3.06 ± 0.07) A"), "C",
     "The largest true value is $1.01\\times3.08=3.11\\ \\mathrm{A}$ and the smallest is $0.99\\times3.04=3.01\\ \\mathrm{A}$. The mean of these is $3.06\\ \\mathrm{A}$ and half the range is $0.05\\ \\mathrm{A}$; option A allows only for the fluctuation and ignores the meter's stated accuracy.",
     ["There are two sources of uncertainty here: the fluctuation and the meter's accuracy.", "Find the largest and smallest values the true current could be, including the accuracy limits.", "The best value is the midpoint and the uncertainty is half the difference between the extremes."],
     )
past(10, "CAIE 9702 · Jun 2019 · P12 · Q5", [K3], 4, "Determine",
     "A student wishes to determine the density ρ of lead. She measures the mass and diameter of a small sphere of lead: mass = (0.506 ± 0.005) g, diameter = (2.20 ± 0.02) mm. What is the best estimate of the percentage uncertainty in her calculated value of ρ?",
     opts("1.7%", "1.9%", "2.8%", "3.7%"), "D",
     "Density is mass divided by volume and volume is proportional to $d^3$, so $\\rho\\propto m/d^3$. The percentage uncertainties are $1.0\\%$ for mass and $0.9\\%$ for diameter, giving $1.0+3\\times0.9=3.7\\%$; option B simply adds $1.0+0.9$ and option C uses $2\\times0.9$.",
     ["Write density in terms of mass and diameter.", "Percentage uncertainties add, but a power multiplies the percentage uncertainty of that quantity.", "Work out the percentage uncertainty in mass and in diameter separately, then combine with the correct power for diameter."],
     {"B": "m4", "C": "m4"})
past(11, "CAIE 9702 · Nov 2023 · P12 · Q3", [K3], 5, "Calculate",
     "A student takes measurements to determine the constant acceleration of a model car moving from rest in a straight line: displacement s = 16.5 m ± 0.1 m and time t = 15.0 s ± 1.0 s. The student uses the equation s = ½at² to calculate the acceleration of the car. What is the acceleration and its absolute uncertainty?",
     opts("(0.11 ± 0.01) m s⁻²", "(0.11 ± 0.02) m s⁻²", "(0.15 ± 0.01) m s⁻²", "(0.15 ± 0.02) m s⁻²"), "D",
     "Rearranging gives $a=2s/t^2=0.147\\ \\mathrm{m\\,s^{-2}}$, and the percentage uncertainty is $0.6\\%+2\\times6.7\\%=13.9\\%$, an absolute uncertainty of $0.02\\ \\mathrm{m\\,s^{-2}}$. If the square on $t$ is forgotten the result is about $0.01\\ \\mathrm{m\\,s^{-2}}$ (option C).",
     ["Rearrange the equation to make the acceleration the subject.", "Find the percentage uncertainty in s and in t, remembering how t appears in the equation.", "Convert the total percentage uncertainty back to an absolute uncertainty of the acceleration."],
     {"C": "m4"}, image="Assets/mcq/9702_w23_12_q3.png")
past(12, "CAIE 9702 · Nov 2022 · P12 · Q3", [K3], 3, "Calculate",
     "A spring is suspended from a fixed point and a force is applied. The position of a pointer attached to the bottom of the spring against a vertical ruler is recorded. Before the force is applied, the position of the pointer is (225 ± 2) mm. After the force is applied, the position of the pointer is (250 ± 2) mm. The extension of the spring is determined. What is the percentage uncertainty in the extension?",
     opts("1.6%", "1.8%", "8.0%", "16%"), "D",
     "The extension is $250-225=25\\ \\mathrm{mm}$ and the absolute uncertainties of the two readings add to $\\pm4\\ \\mathrm{mm}$, so the percentage uncertainty is $\\frac{4}{25}\\times100=16\\%$. Option A divides by $250$ instead of by the extension, and option C uses only one reading's $\\pm2\\ \\mathrm{mm}$.",
     ["What quantity is the extension made from, and how many readings does it need?", "When two readings are subtracted, what happens to their absolute uncertainties?", "Divide the total absolute uncertainty by the extension itself, not by either reading."],
     {"A": "m5", "C": "m5"})

# --- generated: KC 9702-1.3.1
gen("mcq", 2, "Identify", [K1],
    "A digital balance reads $0.04\\ \\mathrm{g}$ when nothing is on the pan. A student uses it for a whole experiment without adjusting for this. Which statement describes the effect on her mass measurements?",
    "The balance adds the same $0.04\\ \\mathrm{g}$ to every reading, which is a systematic error (a zero error). Taking a mean of many readings does not remove it; subtracting $0.04\\ \\mathrm{g}$ does.",
    ["Does the balance affect every reading in the same way or in a different way each time?", "A fixed offset on every reading is one of the two types of error; decide which.", "Ask whether averaging repeated readings could cancel a constant offset."],
    options=opts("A systematic error: every reading is $0.04\\ \\mathrm{g}$ too high.", "A random error: readings scatter about the true value.", "A systematic error that averaging many readings would remove.", "A random error that repeating the measurement would reduce."),
    answer="A", distractors={"C": "m1"}, marks=1)
gen("numeric", 2, "Calculate", [K1],
    "A micrometer screw gauge reads $[[z:.2f]]\\ \\mathrm{mm}$ when its jaws are closed. With a wire between the jaws it reads $[[r:.2f]]\\ \\mathrm{mm}$. Calculate the true diameter of the wire, in mm.",
    "The true diameter is the reading minus the zero error, keeping the sign of the zero error: $d=r-z$.",
    ["What does the gauge read when the true size is zero, and what does that mean for every reading?", "Correct the reading by removing the zero error from it.", "Subtract the zero error from the reading, keeping its sign."],
    template={"params": {"r": {"min": 1.05, "max": 1.95, "step": 0.01}, "z": {"choices": [-0.06, -0.04, -0.03, 0.02, 0.03, 0.05]}},
              "answer": "r - z", "distractors": [{"expr": "r + z", "misconception": "m2"}]},
    answer={"unit": "mm", "sf_ok": [3]}, marks=1)
gen("short", 3, "Explain", [K1],
    "Explain why taking the mean of many repeated readings reduces the effect of random errors but not of a systematic error.",
    "Random deviations are equally likely to be above and below the true value, so they partly cancel in a mean. A systematic error is the same size and direction in every reading, so the mean has the same error.",
    ["Think about which way each kind of error pushes the readings.", "Averaging works by cancelling; what must the errors do to cancel?", "Compare an error that is sometimes high and sometimes low with one that is always high."],
    rubric=[{"point": "random errors are above and below the true value / scatter, so they cancel (partly) in the mean", "keywords": [["random"], ["above", "below", "either", "both", "cancel", "scatter", "equally"]]},
            {"point": "a systematic error is the same every reading (same direction/size) so is not reduced by averaging", "keywords": [["systematic"], ["same direction", "same amount", "same size", "constant", "always", "every reading", "all readings", "not reduced", "unaffected", "still", "not removed", "remains", "not cancel"]]}],
    marks=2)
gen("structured", 4, "Explain", [K1],
    "A student measures the diameter of a wire with a micrometer screw gauge. With the jaws closed the gauge reads $-0.03\\ \\mathrm{mm}$. With the wire in place she takes five readings: $0.82,\\ 0.84,\\ 0.83,\\ 0.83,\\ 0.85\\ \\mathrm{mm}$.\n(a) State the type of error that the reading of $-0.03\\ \\mathrm{mm}$ represents.\n(b) Calculate the diameter of the wire, in mm.\n(c) Explain whether taking more readings would remove the effect of this error.",
    "A zero error is a systematic error, corrected by subtracting it from the mean reading: $0.834-(-0.03)=0.864\\ \\mathrm{mm}$. More readings only average out random scatter and leave the zero error unchanged.",
    ["Decide whether the zero error changes from reading to reading or is fixed.", "Use the mean of the five readings, then correct it for the zero error.", "Subtract the zero error from the mean, keeping its sign."],
    scheme=[{"mark": "B1", "point": "systematic error (zero error)"},
            {"mark": "M1", "point": "mean of readings = 0.834 mm, then corrected by subtracting the zero error (adding 0.03 mm)"},
            {"mark": "A1", "point": "diameter = 0.86 mm", "check": {"kind": "numeric", "answer": {"value": round(corr, 3), "unit": "mm", "sf_ok": [2, 3]}}},
            {"mark": "B1", "point": "no: a systematic error is the same in every reading, so averaging does not reduce it; it must be corrected"}],
    marks=4)

# --- generated: KC 9702-1.3.2
gen("mcq", 2, "Identify", [K2],
    "The accepted value of $g$ is $9.81\\ \\mathrm{m\\,s^{-2}}$. Four students each take four measurements of $g$. Which set of readings is precise but not accurate?",
    "Set B has readings within $0.02$ of each other (precise) but all about $0.7\\ \\mathrm{m\\,s^{-2}}$ below $9.81$ (not accurate). Set C has a mean near $9.81$ but its readings are widely scattered, so it is not precise.",
    ["Precise means the readings agree with each other; accurate means they agree with the accepted value.", "First find which sets have readings that are tightly grouped.", "Of the tightly grouped sets, keep the one that is far from $9.81$."],
    options=opts("$9.79,\\ 9.81,\\ 9.83,\\ 9.80$", "$9.10,\\ 9.12,\\ 9.11,\\ 9.10$", "$9.1,\\ 10.5,\\ 9.4,\\ 10.2$", "$8.4,\\ 10.9,\\ 7.9,\\ 9.2$"),
    answer="B", distractors={"C": "m3"}, marks=1)
gen("short", 2, "State", [K2],
    "State the difference between a precise set of measurements and an accurate measurement.",
    "Precision concerns how closely repeated readings agree with each other; accuracy concerns how close a reading is to the true (accepted) value.",
    ["One of the two words is about the readings compared with each other.", "The other word needs the true value to be known.", "Precise: agreement between repeats. Accurate: agreement with the true value."],
    rubric=[{"point": "precise: repeated readings are close together / small range or scatter", "keywords": [["precis"], ["close", "small range", "small spread", "scatter", "agree", "consistent", "similar"]]},
            {"point": "accurate: reading is close to the true / accepted value", "keywords": [["accura"], ["true", "accepted", "actual", "correct"]]}],
    marks=2)
gen("mcq", 3, "Predict", [K2],
    "A student times oscillations with a stopwatch that runs slow, so every time is $2\\%$ too small, while her reaction-time scatter is small. Which describes her set of repeated results?",
    "A constant $2\\%$ error is a systematic error, which shifts all results away from the true value (not accurate); small scatter means the results agree with each other (precise).",
    ["A stopwatch that is always slow by the same fraction is which type of error?", "Decide what that error does to the true value and what it does to the scatter.", "Small scatter with a constant shift is precise and inaccurate."],
    options=opts("Precise but not accurate", "Accurate but not precise", "Both precise and accurate", "Neither precise nor accurate"),
    answer="A", distractors={"B": "m3"}, marks=1)
gen("structured", 4, "Compare", [K2],
    "The accepted time for one oscillation of a pendulum is $2.00\\ \\mathrm{s}$. Student X measures $2.31,\\ 2.30,\\ 2.32,\\ 2.31\\ \\mathrm{s}$ and student Y measures $1.92,\\ 2.09,\\ 2.04,\\ 1.95\\ \\mathrm{s}$.\n(a) State, with a reason, which student's readings are more precise.\n(b) Calculate the mean of Y's readings.\n(c) State, with a reason, which student's results are more accurate.\n(d) Suggest a systematic error that could explain X's results.",
    "X's readings span only $0.02\\ \\mathrm{s}$ against $0.17\\ \\mathrm{s}$ for Y, so X is more precise. Y's mean is $8.00/4=2.00\\ \\mathrm{s}$, equal to the accepted value, while X's mean of $2.31\\ \\mathrm{s}$ is $0.31\\ \\mathrm{s}$ too large, so Y is more accurate.",
    ["Precision is about the spread of the readings within each set.", "The mean of Y is needed to compare with the accepted value.", "X's readings are tightly grouped but all above $2.00\\ \\mathrm{s}$; think of a fault that adds a similar amount to every time."],
    scheme=[{"mark": "B1", "point": "X more precise: range (0.02 s) smaller than Y's (0.17 s)"},
            {"mark": "B1", "point": "mean of Y = 2.00 s", "check": {"kind": "numeric", "answer": {"value": 2.0, "unit": "s", "sf_ok": [3]}}},
            {"mark": "B1", "point": "Y more accurate: mean equals the accepted value whereas X's mean (2.31 s) is 0.31 s too high"},
            {"mark": "B1", "point": "e.g. stopwatch runs fast / consistent delay stopping the watch / timing zero error"}],
    marks=4)
gen("short", 3, "Explain", [K2],
    "A student times a falling ball five times and gets $0.452,\\ 0.451,\\ 0.453,\\ 0.452,\\ 0.452\\ \\mathrm{s}$. She says the results are very accurate. Explain what these results actually show, and what more she would need to know to comment on accuracy.",
    "The readings agree closely, which shows high precision. Accuracy needs a comparison with the true (accepted) value, which she has not made.",
    ["Look at how the five readings compare with each other.", "Agreement between readings is one property; closeness to a correct value is another.", "What value would she have to compare her mean against?"],
    rubric=[{"point": "readings are close together / small spread, so they are precise", "keywords": [["close", "small range", "small spread", "agree", "similar", "consistent", "precis"]]},
            {"point": "accuracy needs comparison with the true / accepted value", "keywords": [["true", "accepted", "actual", "known", "expected"], ["compare", "comparison", "value", "need"]]}],
    marks=2)

# --- generated: KC 9702-1.3.3
gen("numeric", 3, "Calculate", [K3],
    "A student measures the length of a pendulum as $l=[[l:.3f]]\\ \\mathrm{m}\\pm[[dl:.3f]]\\ \\mathrm{m}$ and the period as $T=[[T:.2f]]\\ \\mathrm{s}\\pm[[dT:.2f]]\\ \\mathrm{s}$. She calculates $g=\\dfrac{4\\pi^2 l}{T^2}$. Calculate the percentage uncertainty in $g$, to 2 significant figures.",
    "The percentage uncertainty in $g$ is the percentage uncertainty in $l$ plus twice that in $T$, because $T$ is squared: $\\frac{\\Delta g}{g}=\\frac{\\Delta l}{l}+2\\frac{\\Delta T}{T}$.",
    ["Work out the percentage uncertainty in $l$ and in $T$ separately.", "Percentage uncertainties are added when quantities are multiplied or divided; check how $T$ appears in the formula.", "Add the percentage uncertainty in $l$ to the percentage uncertainty in $T$ multiplied by its power."],
    template={"params": {"l": {"choices": [0.400, 0.500, 0.600, 0.800]}, "dl": {"choices": [0.002, 0.005]},
                         "T": {"choices": [1.30, 1.40, 1.60, 1.80]}, "dT": {"choices": [0.02, 0.04]}},
              "answer": "dl/l*100 + 2*dT/T*100", "distractors": [{"expr": "dl/l*100 + dT/T*100", "misconception": "m4"}]},
    answer={"unit": "%", "sf_ok": [2], "tol_rel": 0.05}, marks=2)
gen("numeric", 4, "Calculate", [K3],
    "A solid cube has side $L=[[L:.2f]]\\ \\mathrm{cm}\\pm[[dL:.2f]]\\ \\mathrm{cm}$ and mass $M=[[M:.1f]]\\ \\mathrm{g}\\pm[[dM:.1f]]\\ \\mathrm{g}$. Calculate the absolute uncertainty in the density $\\rho=M/L^3$, in $\\mathrm{g\\,cm^{-3}}$, to 2 significant figures.",
    "The percentage uncertainty in $\\rho$ is $\\frac{\\Delta M}{M}+3\\frac{\\Delta L}{L}$, and the absolute uncertainty is this fraction multiplied by $\\rho$.",
    ["First calculate the density itself and the percentage uncertainty in $M$ and $L$.", "$L$ is cubed in the density formula, so it counts more than once.", "Find the total percentage uncertainty, then convert it back to an absolute uncertainty using the density."],
    template={"params": {"L": {"choices": [2.00, 2.50, 3.00, 4.00]}, "dL": {"choices": [0.02, 0.05]},
                         "M": {"choices": [30.0, 55.0, 80.0, 120.0]}, "dM": {"choices": [0.1, 0.5]}},
              "derived": {"rho": "M/L**3"},
              "answer": "rho*(dM/M + 3*dL/L)", "distractors": [{"expr": "rho*(dM/M + dL/L)", "misconception": "m4"}]},
    answer={"unit": "g cm^-3", "sf_ok": [2], "tol_rel": 0.05}, marks=2)
gen("mcq", 3, "Determine", [K3],
    "Two lengths are measured: $(12.5\\pm0.2)\\ \\mathrm{cm}$ and $(8.3\\pm0.1)\\ \\mathrm{cm}$. What is their difference, with its absolute uncertainty?",
    "The difference is $12.5-8.3=4.2\\ \\mathrm{cm}$. Absolute uncertainties add even when values are subtracted: $0.2+0.1=0.3\\ \\mathrm{cm}$.",
    ["Find the difference of the two lengths first.", "Decide what to do with the two uncertainties: does subtracting the values subtract the uncertainties?", "Uncertainties always add."],
    options=opts("$(4.2\\pm0.3)\\ \\mathrm{cm}$", "$(4.2\\pm0.1)\\ \\mathrm{cm}$", "$(4.2\\pm0.2)\\ \\mathrm{cm}$", "$(20.8\\pm0.3)\\ \\mathrm{cm}$"),
    answer="A", distractors={"B": "m5"}, marks=1)
gen("structured", 5, "Determine", [K3],
    "The resistivity of a wire is $\\rho=\\dfrac{\\pi d^2R}{4L}$. Measurements: diameter $d=(0.32\\pm0.01)\\ \\mathrm{mm}$, resistance $R=(4.7\\pm0.1)\\ \\Omega$, length $L=(1.000\\pm0.002)\\ \\mathrm{m}$.\n(a) Calculate the percentage uncertainty in $d$.\n(b) Show that the percentage uncertainty in $\\rho$ is about $8.6\\%$.\n(c) Calculate $\\rho$, in $\\Omega\\,\\mathrm{m}$.\n(d) Determine the absolute uncertainty in $\\rho$ and write $\\rho$ with its uncertainty.",
    "The percentage uncertainties are $3.1\\%$ for $d$, $2.1\\%$ for $R$ and $0.2\\%$ for $L$; $d$ is squared, so the total is $2\\times3.1+2.1+0.2=8.6\\%$. With $\\rho=3.78\\times10^{-7}\\ \\Omega\\,\\mathrm{m}$ the absolute uncertainty is $0.32\\times10^{-7}\\ \\Omega\\,\\mathrm{m}$, so $\\rho=(3.8\\pm0.3)\\times10^{-7}\\ \\Omega\\,\\mathrm{m}$.",
    ["Percentage uncertainty is absolute uncertainty divided by the value, times 100.", "Which quantity in the formula is squared, and what does that do to its contribution?", "Convert the total percentage uncertainty into an absolute one using the value of $\\rho$, and give the uncertainty to 1 significant figure."],
    scheme=[{"mark": "B1", "point": "percentage uncertainty in d = 3.1%", "check": {"kind": "numeric", "answer": {"value": round(pd_, 3), "unit": "%", "sf_ok": [2, 3]}}},
            {"mark": "M1", "point": "percentage uncertainty in rho = 2 x (% in d) + % in R + % in L (d is squared)"},
            {"mark": "A1", "point": "8.6% (about 8.6, shown from 6.25 + 2.1 + 0.2)", "check": {"kind": "numeric", "answer": {"value": round(prho, 2), "unit": "%", "sf_ok": [2, 3]}}},
            {"mark": "B1", "point": "rho = 3.8 x 10^-7 ohm m (d converted to metres)", "check": {"kind": "numeric", "answer": {"value": float(f"{rho:.3g}"), "unit": "ohm m", "sf_ok": [2, 3]}}},
            {"mark": "A1", "point": "absolute uncertainty about 0.3 x 10^-7 ohm m, so rho = (3.8 +/- 0.3) x 10^-7 ohm m"}],
    marks=5)

# ---------------------------------------------------------------- worked example
worked = [{"id": "we1", "kc": K3,
  "problem": f"A student finds $g$ from a pendulum using $g=\\dfrac{{4\\pi^2 l}}{{T^2}}$. She measures $l=({W_l:.3f}\\pm{W_dl:.3f})\\ \\mathrm{{m}}$ and $T=({W_T:.2f}\\pm{W_dT:.2f})\\ \\mathrm{{s}}$. Calculate $g$ and its absolute uncertainty.",
  "steps": [
   {"do": f"State the equation and substitute: $g=\\dfrac{{4\\pi^2\\times{W_l:.3f}}}{{{W_T:.2f}^2}}={W_g:.2f}\\ \\mathrm{{m\\,s^{{-2}}}}$.",
    "why": "Marks are given for the equation, the substitution and the value, so show all three before touching the uncertainties.",
    "check": {"kind": "numeric", "answer": {"value": round(W_g, 2), "unit": "m s^-2", "sf_ok": [3, 4]}}},
   {"do": f"Find each percentage uncertainty: $\\dfrac{{{W_dl:.3f}}}{{{W_l:.3f}}}\\times100={W_pl:.2f}\\%$ for $l$ and $\\dfrac{{{W_dT:.2f}}}{{{W_T:.2f}}}\\times100={W_pT:.2f}\\%$ for $T$.",
    "why": "Percentage uncertainties are the ones that can be added when quantities are multiplied or divided; absolute uncertainties cannot be mixed across different units."},
   {"do": f"Add them, doubling the one for $T$: $\\dfrac{{\\Delta g}}{{g}}={W_pl:.2f}\\%+2\\times{W_pT:.2f}\\%={W_pg:.1f}\\%$.",
    "why": "$T$ is squared, so it appears twice in the product and its percentage uncertainty is counted twice; this is the step most students skip.",
    "check": {"kind": "numeric", "answer": {"value": round(W_pg, 2), "unit": "%", "sf_ok": [2, 3]}}},
   {"do": f"Convert back to an absolute uncertainty: $\\Delta g={W_pg:.1f}\\%\\times{W_g:.2f}={W_dg:.2f}\\ \\mathrm{{m\\,s^{{-2}}}}$.",
    "why": "The question asks for an absolute uncertainty, so multiply the fractional uncertainty by the calculated value.",
    "check": {"kind": "numeric", "answer": {"value": round(W_dg, 2), "unit": "m s^-2", "sf_ok": [2]}}},
   {"do": f"Round the uncertainty to 1 s.f. and match the decimal places of $g$: $g=({W_g:.1f}\\pm{float(f'{W_dg:.1g}'):.1f})\\ \\mathrm{{m\\,s^{{-2}}}}$.",
    "why": "An uncertainty is only known to about one significant figure, and the value must not show more decimal places than its uncertainty."}],
  "faded": {"id": "we1f",
    "problem": f"A student measures a pendulum with $l=({F_l:.3f}\\pm{F_dl:.3f})\\ \\mathrm{{m}}$ and $T=({F_T:.2f}\\pm{F_dT:.2f})\\ \\mathrm{{s}}$ and uses $g=\\dfrac{{4\\pi^2 l}}{{T^2}}$. Determine the absolute uncertainty in $g$, to 2 significant figures.",
    "answer": {"value": F_dg2, "unit": "m s^-2", "sf_ok": [2]}, "blank_from": 1}}]

flashcards = [
 {"id": "fc1", "kc": K1, "front": "Define a systematic error.", "back": "An error that makes every reading differ from the true value by the same amount in the same direction (always too high or always too low). Repeating and averaging does not reduce it."},
 {"id": "fc2", "kc": K1, "front": "Define a random error.", "back": "An error that makes readings scatter unpredictably above and below the true value. It can be reduced by taking repeated readings and averaging."},
 {"id": "fc3", "kc": K1, "front": "What is a zero error, and how do you correct for it?", "back": "A zero error is a non-zero reading when the true value is zero. It is a systematic error; subtract it from every reading, keeping its sign: corrected reading = reading − zero error."},
 {"id": "fc4", "kc": K1, "front": "State one way to reduce (a) random errors and (b) systematic errors.", "back": "(a) Repeat the measurement and calculate a mean. (b) Calibrate the instrument or correct for the zero error."},
 {"id": "fc5", "kc": K2, "front": "What does it mean for measurements to be precise?", "back": "Repeated readings are close to each other (small range or scatter). Precision is related to random error."},
 {"id": "fc6", "kc": K2, "front": "What does it mean for a measurement to be accurate?", "back": "It is close to the true (accepted) value. A large systematic error makes measurements inaccurate even if they are precise."},
 {"id": "fc7", "kc": K3, "front": "Percentage uncertainty in a quantity $x$ with absolute uncertainty $\\Delta x$.", "back": "$\\dfrac{\\Delta x}{x}\\times100\\%$"},
 {"id": "fc8", "kc": K3, "front": "How are uncertainties combined when values are added or subtracted?", "back": "Add the absolute uncertainties (also for a subtraction)."},
 {"id": "fc9", "kc": K3, "front": "How are uncertainties combined when values are multiplied or divided?", "back": "Add the percentage (or fractional) uncertainties."},
 {"id": "fc10", "kc": K3, "front": "The percentage uncertainty in $x$ is $p\\%$. What is it in $x^n$?", "back": "$n\\times p\\%$ (the percentage uncertainty is multiplied by the power)."},
]

# ---------------------------------------------------------------- diagram
def gauss(mu, sd): return [[round(-4 + i * 0.1, 2), round(math.exp(-0.5 * ((-4 + i * 0.1 - mu) / sd) ** 2) / (sd * math.sqrt(2 * math.pi)), 4)] for i in range(81)]
DIAG = "Assets/9702/9702-1.3-precision-accuracy.svg"
diagrams = [{"file": DIAG, "type": "graph_sketch", "params": {
    "lines": [{"points": gauss(0, 1.2), "label": "accurate, not precise"},
              {"points": gauss(1.8, 0.35), "label": "precise, not accurate"},
              {"points": [[0, 0], [0, 1.2]], "style": "dashed", "label": "true value"}],
    "xlabel": "measured value", "ylabel": "number of readings"}}]

outline = ("Every measurement has error. A systematic error shifts all readings the same way (a zero error is one); repeating does not remove it, calibration or correction does. A random error scatters readings both sides of the true value; averaging reduces it. "
           "Precision means repeated readings are close to each other; accuracy means close to the true value. "
           "To find an uncertainty in a derived quantity, add absolute uncertainties for $a\\pm b$; add percentage uncertainties for products and quotients, multiplying by the power for $x^n$. "
           "Convert percentage back to absolute using the calculated value and quote the uncertainty to 1 s.f.")
assert len(outline.split()) <= 150

pack = {"subtopic": SUB, "spec": "9702", "version": 1, "note": NOTE, "outline": outline, "misconceptions": M,
        "worked": worked, "items": items, "flashcards": flashcards, "diagrams": diagrams}
out = ROOT / "build/out/packs/9702/9702-1.3.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(pack, ensure_ascii=False, indent=1) + "\n")

# ---------------------------------------------------------------- lesson note
note = f"""---
tags: [stem-tutor/lesson, 9702]
spec: "9702"
subtopic: "{SUB}"
kcs: ["{K1}", "{K2}", "{K3}"]
---
# 1.3 Errors and uncertainties
> [!abstract] In one breath
> Every measurement is off by some error: systematic errors shift every reading the same way, random errors scatter them. Precision is how closely repeats agree, accuracy is how close to the true value, and uncertainties in derived quantities are found by adding absolute or percentage uncertainties.

## Key ideas

**Systematic error**: every reading is too high or every reading is too low by the same amount or the same factor. A **zero error** is one example. Repeating and averaging does not reduce it; calibrating the instrument or correcting the zero error does.

**Random error**: readings scatter unpredictably above and below the true value. It is reduced by taking repeated readings and calculating a mean.

**Zero error correction**: corrected reading $=$ reading $-$ zero error, keeping the sign. A gauge with zero error $-0.05\\ \\mathrm{{mm}}$ reading $1.03\\ \\mathrm{{mm}}$ gives $1.03-(-0.05)=1.08\\ \\mathrm{{mm}}$.

**Precision**: repeated readings are close to each other (small range or scatter). **Accuracy**: a reading is close to the true (accepted) value.

![[{DIAG}]]

**Percentage uncertainty** $=\\dfrac{{\\Delta x}}{{x}}\\times100\\%$.

**Combining uncertainties**:
- $Q=a\\pm b$: $\\Delta Q=\\Delta a+\\Delta b$ (absolute uncertainties add, also for a difference).
- $Q=\\dfrac{{a\\,b}}{{c}}$: $\\dfrac{{\\Delta Q}}{{Q}}=\\dfrac{{\\Delta a}}{{a}}+\\dfrac{{\\Delta b}}{{b}}+\\dfrac{{\\Delta c}}{{c}}$ (percentage uncertainties add).
- $Q=x^n$: $\\dfrac{{\\Delta Q}}{{Q}}=n\\,\\dfrac{{\\Delta x}}{{x}}$.

## Method

1. Write the equation for the derived quantity and calculate its value.
2. Find the percentage uncertainty in each measured quantity ($\\Delta x/x\\times100$).
3. Add them, multiplying by the power for any squared, cubed or square-root quantity.
4. Convert back to an absolute uncertainty: $\\Delta Q=\\text{{percentage}}\\times Q$.
5. Give the uncertainty to 1 significant figure and the value to the same decimal place.

> [!example]- Worked example
> A pendulum gives $l=({W_l:.3f}\\pm{W_dl:.3f})\\ \\mathrm{{m}}$ and $T=({W_T:.2f}\\pm{W_dT:.2f})\\ \\mathrm{{s}}$. Find $g=\\dfrac{{4\\pi^2 l}}{{T^2}}$ with its uncertainty.
>
> $$g=\\dfrac{{4\\pi^2\\times{W_l:.3f}}}{{{W_T:.2f}^2}}={W_g:.2f}\\ \\mathrm{{m\\,s^{{-2}}}}$$
>
> $$\\dfrac{{\\Delta g}}{{g}}={W_pl:.2f}\\%+2\\times{W_pT:.2f}\\%={W_pg:.1f}\\%$$
>
> $$\\Delta g={W_pg:.1f}\\%\\times{W_g:.2f}={W_dg:.2f}\\ \\mathrm{{m\\,s^{{-2}}}}$$
>
> So $g=({W_g:.1f}\\pm{float(f'{W_dg:.1g}'):.1f})\\ \\mathrm{{m\\,s^{{-2}}}}$.

## Traps
- **Trap:** averaging repeats removes a zero error. **Why it's wrong:** a systematic error is identical in every reading, so the mean carries it too. **Instead:** correct or calibrate; use averaging only for random error.
- **Trap:** a negative zero error is added on. **Why it's wrong:** the correction is reading minus zero error, and subtracting a negative adds. **Instead:** $1.03-(-0.05)=1.08\\ \\mathrm{{mm}}$.
- **Trap:** precise means close to the true value. **Why it's wrong:** that is accuracy; precision is agreement between repeats. **Instead:** readings $9.10,\\ 9.12,\\ 9.11$ against $9.81$ are precise but not accurate.
- **Trap:** forgetting the power, so a cubed diameter with $0.2\\%$ gives $0.2\\%$. **Why it's wrong:** the quantity appears three times in the product. **Instead:** $3\\times0.2=0.6\\%$.
- **Trap:** subtracting uncertainties for a difference, or dividing by one original reading. **Why it's wrong:** uncertainties always add, and the percentage refers to the difference itself. **Instead:** $\\frac{{2+2}}{{250-225}}\\times100=16\\%$.

## Exam technique
- *Define* and *State* need the formal wording: precise means close to each other, accurate means close to the true value.
- *Explain* why averaging helps needs both halves: random errors cancel, a systematic error is the same in every reading.
- *Show that* needs each percentage uncertainty written out before the sum, including the doubled or tripled term.
- Check what the question asks for: percentage or absolute uncertainty, and the number of significant figures.
- Convert units (mm to m) before substituting, and quote the uncertainty to 1 s.f.

## Links
Builds on [[1.2 SI units]] · Leads to [[1.4 Scalars and vectors]]
"""
npath = ROOT / "build/out/notes" / NOTE
npath.parent.mkdir(parents=True, exist_ok=True)
npath.write_text(note)
print(len(items), "items;", len(note.split()), "note words")
