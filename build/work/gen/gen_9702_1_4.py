"""Generator for pack 9702-1.4 (Scalars and vectors). Content as data; every number computed here."""
import json, math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SUB = "9702-1.4"
K1, K2, K3 = f"{SUB}.1", f"{SUB}.2", f"{SUB}.3"
NOTE = "Subjects/9702 Physics/01 Physical quantities and units/1.4 Scalars and vectors.md"
G = 9.81
U = r"\mathrm{m\,s^{-1}}"
cos = lambda d: math.cos(math.radians(d))
sin = lambda d: math.sin(math.radians(d))

# ---------------- numbers for worked examples / fixed items ----------------
we1 = math.hypot(3.0, 1.2); we1_ang = math.degrees(math.atan2(3.0, 1.2)); we1f = math.hypot(4.0, 1.5)
we2 = math.hypot(4.0, 3.0); we2_ang = math.degrees(math.atan2(3.0, 4.0)); we2f = math.hypot(6.0, 8.0)
we3x, we3y = 25 * cos(35), 25 * sin(35); we3f = 40 * cos(20)
W = 4.0 * G; Wpar = W * sin(25); Wperp = W * cos(25)
boat_theta = math.degrees(math.asin(4 / 6)); boat_v = 6 * cos(boat_theta)
assert round(we1, 1) == 3.2 and round(we1_ang, 1) == 68.2 and round(we1f, 1) == 4.3
assert we2 == 5.0 and round(we2_ang, 1) == 36.9 and we2f == 10.0
assert round(we3x, 1) == 20.5 and round(we3y, 1) == 14.3 and round(we3f, 1) == 37.6
assert round(W, 1) == 39.2 and round(Wpar, 1) == 16.6 and round(Wperp, 1) == 35.6
assert round(boat_theta) == 42 and round(boat_v, 1) == 4.5
assert round(2 * 6 * cos(30), 0) == 10 and round(math.hypot(4, 3 + 0), 1) == 5.0
assert 12 + 9 == 21 and round(math.hypot(12, 9)) == 15

def num(v, unit, sf=(2, 3)): return {"value": v, "unit": unit, "sf_ok": list(sf)}

# ---------------- misconceptions ----------------
misconceptions = [
 {"id": "m1", "kc": K1, "statement": "A quantity is a vector if it can be positive or negative (temperature in °C, electric charge), or if it 'points' forwards in time.",
  "refutation": "A vector needs a direction in space. A plus or minus sign only tells you which of two opposite senses along a chosen axis, or which type of charge; it is not a direction in space, so temperature, charge and time are scalars.",
  "contrast": "Weight of $5\\ \\mathrm{N}$ downwards is a vector (magnitude and direction). A temperature of $-5\\,^\\circ\\mathrm{C}$ has only a size and a sign, so it is a scalar.", "source": "research"},
 {"id": "m2", "kc": K1, "statement": "Sorting quantities by how they 'feel': upthrust is called a scalar, or pressure, work and energy are called vectors because they involve forces.",
  "refutation": "Upthrust is a force, so it is a vector. Pressure ($F/A$), work and energy are scalars: they have no single direction. A scalar can be calculated from vectors (work is force times displacement in the direction of the force) without becoming a vector.",
  "contrast": "Upthrust acts upwards on a floating object (vector); the work it does is just a number of joules (scalar).", "source": "ER 9702 w23 P23 Q1"},
 {"id": "m3", "kc": K2, "statement": "Combining vectors by adding or subtracting their magnitudes and ignoring directions (or using Pythagoras whatever the angle is).",
  "refutation": "Magnitudes only add directly when the vectors are in the same direction. Opposite directions partly cancel, so a velocity of $8\\ \\mathrm{m\\,s^{-1}}$ right and one of $3\\ \\mathrm{m\\,s^{-1}}$ left differ by $11\\ \\mathrm{m\\,s^{-1}}$, not $5$. Pythagoras works only when the vectors are perpendicular.",
  "contrast": "Two forces of $6.0\\ \\mathrm{N}$ at $60^\\circ$ give a resultant of $10\\ \\mathrm{N}$, not $12\\ \\mathrm{N}$ (aligned) and not $8.5\\ \\mathrm{N}$ (perpendicular).", "source": "ER 9702 s21 P22 Q2"},
 {"id": "m4", "kc": K2, "statement": "Treating vector subtraction as addition: for a change in velocity, drawing $v_\\mathrm{f}+v_\\mathrm{i}$, or subtracting in the wrong order.",
  "refutation": "The change in a quantity is final minus initial: $\\Delta\\mathbf{v}=\\mathbf{v}_\\mathrm{f}-\\mathbf{v}_\\mathrm{i}$. Subtracting a vector means adding its reverse, so reverse the initial velocity first and only then add.",
  "contrast": "Initial $4.0\\ \\mathrm{m\\,s^{-1}}$ right, final $3.0\\ \\mathrm{m\\,s^{-1}}$ down: the sum points down-right, but the change points down-left with magnitude $5.0\\ \\mathrm{m\\,s^{-1}}$.", "source": "ER 9702 s22 P12 Q4"},
 {"id": "m5", "kc": K3, "statement": "Swapping sin and cos when resolving: using $F\\sin\\theta$ for the component next to the angle, or $F\\cos\\theta$ for the component opposite it.",
  "refutation": "The component adjacent to the angle $\\theta$ is $F\\cos\\theta$; the component opposite it is $F\\sin\\theta$. Always ask which side of the right-angled triangle touches the angle, and check limits: at $\\theta=0$ the whole force lies along the axis, so its component is $F$.",
  "contrast": "A force of $10\\ \\mathrm{N}$ at $30^\\circ$ above the horizontal has horizontal component $10\\cos30^\\circ=8.7\\ \\mathrm{N}$ (the larger one), not $10\\sin30^\\circ=5.0\\ \\mathrm{N}$.", "source": "ER 9702 w23 P12 Q4"},
]

# ---------------- past MCQs ----------------
def past(n, qid, ref, kc, diff, cw, stem, ans, expl, options=None, image=None, dist=None):
    it = {"id": f"{SUB}-p{n:02d}", "kcs": [kc], "kind": "mcq", "difficulty": diff, "command_word": cw,
          "source": {"type": "past", "ref": ref, "qid": qid}, "stem": stem}
    if options: it["options"] = options
    it.update({"answer": ans, "marks": 1, "explanation": expl})
    if image: it["image"] = image
    if dist: it["distractors"] = dist
    return it

img = lambda q: f"Assets/mcq/{q}.png"
past_items = [
 past(1, "9702_w25_13_q1", "CAIE 9702 · Nov 2025 · P13 · Q1", K1, 1, "Identify",
      "The table lists four physical quantities: acceleration, charge, kinetic energy and wavelength. Which row correctly identifies them, in that order, as scalars or vectors?", "D",
      "Acceleration is the rate of change of velocity, so it has a direction: a vector. Charge, kinetic energy and wavelength have magnitude only: scalars. Option B is wrong because it calls charge a vector: charge has a sign (positive or negative), but a sign is not a direction in space.",
      {"A": "scalar, vector, vector, scalar", "B": "vector, vector, scalar, scalar", "C": "scalar, scalar, scalar, vector", "D": "vector, scalar, scalar, scalar"},
      img("9702_w25_13_q1"), {"B": "m1"}),
 past(2, "9702_w24_11_q2", "CAIE 9702 · Nov 2024 · P11 · Q2", K1, 2, "Identify",
      "Which statement about vector quantities is correct?", "D",
      "A vector quantity is defined by having a direction as well as a magnitude, and weight is a force acting towards the centre of the Earth. B is wrong: a quantity being positive or negative does not make it a vector (temperature is a scalar). C is wrong: time has no direction in space. A gives the wrong reason: g is a vector because it has a direction, not because its magnitude is constant.",
      {"A": "Acceleration of free fall is a vector quantity because it has a constant magnitude.", "B": "Temperature in °C is a vector quantity because it can be positive or negative.",
       "C": "Time is a vector quantity because it can only go in the forwards direction.", "D": "Weight is a vector quantity because it has a direction."}, None, {"B": "m1"}),
 past(3, "9702_w21_13_q3", "CAIE 9702 · Nov 2021 · P13 · Q3", K1, 2, "Identify",
      "Which list consists only of scalar quantities?", "C",
      "Distance, pressure, temperature and time all have magnitude only. Pressure acts equally in all directions on a surface, so although it is force divided by area it is a scalar. A contains displacement, force and weight; B contains velocity; D contains momentum: all vectors.",
      {"A": "acceleration, displacement, force, weight", "B": "density, energy, frequency, velocity", "C": "distance, pressure, temperature, time", "D": "momentum, power, volume, wavelength"}, None, {"D": "m2"}),
 past(4, "9702_s24_13_q4", "CAIE 9702 · Jun 2024 · P13 · Q4", K1, 3, "Identify",
      "Two physical quantities combined together as a product can produce a scalar quantity or a vector quantity. Which product of two quantities produces a scalar quantity?", "A",
      "Force multiplied by the displacement in the direction of the force is work done, which is a scalar (energy transferred). B is force (mass times acceleration), C is force (pressure times area) and D is displacement (velocity times time): all vectors. A scalar can be built from vectors without having a direction itself.",
      {"A": "(force) × (displacement of an object in the direction of the force)", "B": "(mass) × (acceleration of the mass)",
       "C": "(pressure) × (area on which the pressure acts)", "D": "(velocity) × (time for which an object has that velocity)"}, None, {"C": "m2"}),
 past(5, "9702_s22_12_q4", "CAIE 9702 · Jun 2022 · P12 · Q4", K2, 3, "Identify",
      "An object has an initial velocity of $4.0\\ \\mathrm{m\\,s^{-1}}$ to the right. Its velocity changes so that its final velocity is $3.0\\ \\mathrm{m\\,s^{-1}}$ downwards, as shown. Which arrow represents the change in velocity of the object?", "B",
      "The change in velocity is final minus initial, so reverse the initial velocity (left, $4.0\\ \\mathrm{m\\,s^{-1}}$) and add the final velocity (down, $3.0\\ \\mathrm{m\\,s^{-1}}$): an arrow pointing down and to the left, B. Over half of candidates chose A, which is the simple sum of the two velocities, the resultant, when the question asks for the change.",
      None, img("9702_s22_12_q4"), {"A": "m4"}),
 past(6, "9702_s23_13_q4", "CAIE 9702 · Jun 2023 · P13 · Q4", K2, 4, "Identify",
      "The diagram shows two vectors, X and Y, drawn to scale. If $X = Y - Z$, which diagram represents the vector Z?", "A",
      "Rearranging, $Z = Y - X$: reverse X and add it to Y, which gives an arrow pointing down and to the right, A. B shows $X - Y$ (the order is reversed), C shows $X + Y$ and D shows $-X - Y$.",
      None, img("9702_s23_13_q4"), {"B": "m4", "C": "m4"}),
 past(7, "9702_w25_13_q4", "CAIE 9702 · Nov 2025 · P13 · Q4", K2, 3, "Calculate",
      "The diagram shows two forces of $6.0\\ \\mathrm{N}$ acting on an object. The angle between the lines of action of the two forces is $60^\\circ$. What is the magnitude of the resultant force?", "C",
      "Components along the bisector add: $R = 2\\times6.0\\cos30^\\circ = 10.4\\ \\mathrm{N} \\approx 10\\ \\mathrm{N}$. D ($12\\ \\mathrm{N}$) simply adds the magnitudes, which is correct only when the forces act in the same direction. A ($6.0\\ \\mathrm{N}$) would be the resultant if the angle were $120^\\circ$.",
      {"A": "6.0 N", "B": "7.9 N", "C": "10 N", "D": "12 N"}, img("9702_w25_13_q4"), {"D": "m3"}),
 past(8, "9702_w23_13_q4", "CAIE 9702 · Nov 2023 · P13 · Q4", K2, 4, "Determine",
      "A boat crosses a river in which the water moves at $4.0\\ \\mathrm{m\\,s^{-1}}$ from left to right. In still water the boat's speed is $6.0\\ \\mathrm{m\\,s^{-1}}$. The boat is directed at angle $\\theta$ to the line perpendicular to the banks, and its resultant velocity $v$ is perpendicular to the banks. What are $\\theta$ and $v$?", "A",
      "For the resultant to be straight across, the boat's component along the bank must cancel the water: $6.0\\sin\\theta = 4.0$, so $\\theta = 42^\\circ$. The velocity across is then $v = 6.0\\cos\\theta = \\sqrt{6.0^2-4.0^2} = 4.5\\ \\mathrm{m\\,s^{-1}}$. C has the right speed but $\\theta = 48^\\circ$, from swapping sin and cos; B and D have $7.2$, which is $\\sqrt{6.0^2+4.0^2}$, wrongly treating the $6.0$ as a side rather than the hypotenuse.",
      {"A": f"$\\theta = 42^\\circ$, $v = 4.5\\ {U}$", "B": f"$\\theta = 42^\\circ$, $v = 7.2\\ {U}$", "C": f"$\\theta = 48^\\circ$, $v = 4.5\\ {U}$", "D": f"$\\theta = 48^\\circ$, $v = 7.2\\ {U}$"},
      img("9702_w23_13_q4"), {"C": "m5"}),
 past(9, "9702_w23_12_q4", "CAIE 9702 · Nov 2023 · P12 · Q4", K3, 4, "Identify",
      "An aeroplane moves at constant speed in a straight line at angle $\\theta$ to the horizontal. Four forces act: thrust $T$ along its path, weight $W$, lift $L$ perpendicular to its path and resistive force $R$ opposite to its motion. Which two equations must be correct?", "A",
      "Resolve along and perpendicular to the path (no acceleration, so forces balance). Perpendicular: $L = W\\cos\\theta$. Along the path, $T$ balances $R$ plus the component of weight down the path: $T = R + W\\sin\\theta$. Options B and D swap sin and cos, and C has the wrong sign for the weight component.",
      {"A": "$L = W\\cos\\theta$ and $T = R + W\\sin\\theta$", "B": "$L = W\\sin\\theta$ and $T = R + W\\cos\\theta$",
       "C": "$L = W\\cos\\theta$ and $T = R - W\\sin\\theta$", "D": "$L = W\\sin\\theta$ and $T = R - W\\cos\\theta$"}, img("9702_w23_12_q4"), {"B": "m5", "D": "m5"}),
 past(10, "9702_w21_12_q3", "CAIE 9702 · Nov 2021 · P12 · Q3", K3, 2, "Determine",
      "A tennis ball leaves a racket with velocity $v$ at an angle $\\theta$ to the horizontal. The vertical component of the velocity is $v_y$. What is the magnitude of the horizontal component of $v$?", "D",
      "The horizontal and vertical components are the perpendicular sides of a right-angled triangle whose hypotenuse is $v$, so $v_x=\\sqrt{v^2-v_y^2}$. Option B, $v_y\\cos\\theta$, was a common wrong answer: it confuses $v_y\\cos\\theta$ with $v\\cos\\theta$, since $\\cos\\theta$ multiplies the full velocity $v$, not one of its components.",
      {"A": "$v\\sin\\theta$", "B": "$v_y\\cos\\theta$", "C": "$v_y\\sin\\theta$", "D": "$\\sqrt{v^2-v_y^2}$"}, img("9702_w21_12_q3"), {"B": "m5"}),
 past(11, "9702_s21_11_q3", "CAIE 9702 · Jun 2021 · P11 · Q3", K3, 5, "Identify",
      "A force of $10\\ \\mathrm{N}$ and a force of $5\\ \\mathrm{N}$ act on an object. The angle between the forces is $150^\\circ$. The resultant force can be resolved into a pair of perpendicular components. Which row gives numerical expressions for a possible pair of perpendicular components, in newtons?", "C",
      "Take the $10\\ \\mathrm{N}$ force along $x$. The $5\\ \\mathrm{N}$ force is at $150^\\circ$ to it, so the components are $x$: $10 + 5\\cos150^\\circ = 10 - 5\\cos30^\\circ$ and $y$: $5\\sin150^\\circ = 5\\sin30^\\circ$, which is C. Option A has the correct $x$-component but $10\\cos30^\\circ$ for $y$, and B swaps sin and cos, the examiners' commonest errors.",
      {"A": "$10\\cos30^\\circ - 5$ and $10\\cos30^\\circ$", "B": "$10\\sin30^\\circ - 5$ and $10\\cos30^\\circ$", "C": "$10 - 5\\cos30^\\circ$ and $5\\sin30^\\circ$", "D": "$10 - 5\\sin30^\\circ$ and $5\\cos30^\\circ$"},
      img("9702_s21_11_q3"), {"A": "m5", "B": "m5"}),
 past(12, "9702_w19_13_q3", "CAIE 9702 · Nov 2019 · P13 · Q3", K3, 3, "Identify",
      "The arrow represents a vector R, pointing up and to the right at a shallow angle. Which diagram does not represent R as two perpendicular components?", "C",
      "Two perpendicular components must add (by the triangle or parallelogram rule) to give R. In C the two arrows are perpendicular, but the one perpendicular to R's direction points the wrong way (down instead of up), so their sum falls below R and cannot equal it. The other diagrams are all pairs of perpendicular components of R.",
      None, img("9702_w19_13_q3"), None),
]

# ---------------- generated items ----------------
def gen(n, kc, diff, cw, stem, expl, hints, **kw):
    it = {"id": f"{SUB}-i{n:02d}", "kcs": [kc], "kind": kw.pop("kind"), "difficulty": diff, "command_word": cw,
          "source": {"type": "generated"}, "stem": stem}
    it.update(kw); it["explanation"] = expl; it["hints"] = hints
    return it

generated = [
 gen(1, K1, 2, "Calculate",
     "A cyclist rides [[a]] m due east along a straight road, then turns round and rides [[b]] m due west along the same road. Calculate the magnitude of the cyclist's displacement from the starting point.",
     "Displacement is a vector, so the westward leg reverses part of the eastward one: magnitude $a-b$. The total distance travelled, $a+b$, is a scalar and is not what was asked.",
     ["Distance and displacement are different quantities: which one has a direction?", "Displacement is the straight-line change in position, measured from the start to the finish.", "The two legs point in opposite directions, so treat them as opposing: subtract, do not add."],
     kind="numeric", template={"params": {"a": {"choices": [80, 100, 120, 150, 180, 200]}, "b": {"choices": [20, 30, 40, 50, 60]}},
                                "answer": "a - b", "distractors": [{"expr": "a + b", "misconception": "m3"}], "constraints": ["a > b + 20"]},
     answer={"unit": "m", "sf_ok": [2, 3]}, marks=2),
 gen(2, K1, 2, "Define",
     "Define a vector quantity and a scalar quantity, and give one example of each.",
     "A scalar quantity has magnitude only; a vector quantity has both magnitude and direction. For example, speed or mass is a scalar; velocity or force is a vector.",
     ["Think about what information you need to give to fully describe each type of quantity.", "One type needs only a size (with a unit); the other needs a size and something more.", "Name the extra property that a vector has, then choose examples from speed/velocity or distance/displacement pairs."],
     kind="short", rubric=[
         {"point": "scalar quantity has magnitude only", "keywords": [["scalar"], ["magnitude", "size"], ["only", "no direction", "without direction", "not direction"]]},
         {"point": "vector quantity has magnitude and direction", "keywords": [["vector"], ["magnitude", "size"], ["direction"]]},
         {"point": "one correct example of each", "keywords": [["mass", "speed", "distance", "energy", "time", "temperature", "density", "power", "work", "pressure", "volume"],
                                                                  ["force", "velocity", "displacement", "acceleration", "weight", "momentum", "field"]]}], marks=3),
 gen(3, K2, 3, "Determine",
     "Two forces of [[a]] N and [[b]] N act on an object. The angle between the forces is $[[t]]^\\circ$. Determine the magnitude of the resultant force.",
     "Resolve along the first force: $R_x=a+b\\cos t$ and $R_y=b\\sin t$, then $R=\\sqrt{R_x^2+R_y^2}=\\sqrt{a^2+b^2+2ab\\cos t}$. Adding the magnitudes ($a+b$) or using Pythagoras only works for $0^\\circ$ and $90^\\circ$ respectively.",
     ["The resultant is not just the sum of the magnitudes unless the forces point the same way.", "Put the first force along the $x$-axis and resolve the second force into $x$ and $y$ components.", "Add the components in each direction, then combine them with Pythagoras to get the magnitude."],
     kind="numeric", template={"params": {"a": {"choices": [5, 6, 8, 10, 12]}, "b": {"choices": [4, 5, 6, 9]}, "t": {"choices": [60, 120]}},
                                "answer": "sqrt(a**2 + b**2 + 2*a*b*cos(radians(t)))",
                                "distractors": [{"expr": "a + b", "misconception": "m3"}, {"expr": "sqrt(a**2 + b**2)", "misconception": "m3"}],
                                "constraints": ["a > b"]},
     answer={"unit": "N", "sf_ok": [2, 3]}, marks=3),
 gen(4, K2, 3, "Determine",
     "A ball moving at $12\\ \\mathrm{m\\,s^{-1}}$ to the right hits a wall and rebounds at $9.0\\ \\mathrm{m\\,s^{-1}}$ to the left. What is the magnitude of the change in velocity of the ball?",
     "Take right as positive: $\\Delta v = v_\\mathrm{f}-v_\\mathrm{i} = (-9.0)-(+12) = -21\\ \\mathrm{m\\,s^{-1}}$, a magnitude of $21\\ \\mathrm{m\\,s^{-1}}$ to the left. Subtracting the magnitudes ($3.0$) ignores that the velocity reversed direction.",
     ["Velocity is a vector: the ball changes direction as well as speed.", "Choose one direction as positive, then write the final and initial velocities with signs.", "Change $=$ final $-$ initial, and a negative velocity minus a positive one adds the magnitudes."],
     kind="mcq", answer="A", options={"A": f"$21\\ {U}$", "B": f"$3.0\\ {U}$", "C": f"$15\\ {U}$", "D": f"$9.0\\ {U}$"},
     distractors={"B": "m3"}, shuffle=True, marks=1),
 gen(5, K3, 2, "Calculate",
     "A force of [[F]] N acts on a box at an angle of $[[t]]^\\circ$ above the horizontal. Calculate the horizontal component of the force.",
     "The horizontal component is adjacent to the angle, so it is $F\\cos\\theta$. The vertical component (opposite the angle) is $F\\sin\\theta$.",
     ["Sketch the force as the hypotenuse of a right-angled triangle with a horizontal and a vertical side.", "Decide which side of the triangle is next to the given angle.", "The side adjacent to the angle is the hypotenuse multiplied by cosine of the angle."],
     kind="numeric", template={"params": {"F": {"choices": [12, 15, 20, 25, 30, 40, 50]}, "t": {"choices": [20, 25, 30, 35, 55, 60, 65, 70]}},
                                "answer": "F*cos(radians(t))", "distractors": [{"expr": "F*sin(radians(t))", "misconception": "m5"}], "constraints": ["F > 0"]},
     answer={"unit": "N", "sf_ok": [2, 3]}, marks=2),
 {"id": f"{SUB}-i06", "kcs": [K3, K2], "kind": "structured", "difficulty": 4, "command_word": "Calculate", "source": {"type": "generated"},
  "stem": "A box of mass $4.0\\ \\mathrm{kg}$ rests on a smooth slope inclined at $25^\\circ$ to the horizontal. (a) Calculate the weight of the box. (b) Calculate the component of the weight parallel to the slope. (c) Calculate the component of the weight perpendicular to the slope.",
  "scheme": [{"mark": "B1", "point": "weight $W=mg=4.0\\times9.81=39\\ \\mathrm{N}$", "check": {"kind": "numeric", "answer": num(W, "N")}},
             {"mark": "M1", "point": "component parallel to the slope is $W\\sin25^\\circ$ (angle between weight and the perpendicular to the slope is $25^\\circ$)"},
             {"mark": "A1", "point": "parallel component $=39.2\\sin25^\\circ=17\\ \\mathrm{N}$", "check": {"kind": "numeric", "answer": num(Wpar, "N")}},
             {"mark": "A1", "point": "perpendicular component $=W\\cos25^\\circ=36\\ \\mathrm{N}$", "check": {"kind": "numeric", "answer": num(Wperp, "N")}}],
  "marks": 4, "explanation": "The weight acts vertically downwards. Tilting the axes to lie along and perpendicular to the slope, the angle between the weight and the perpendicular to the slope equals the slope angle $25^\\circ$, so the parallel component is $W\\sin25^\\circ$ and the perpendicular component $W\\cos25^\\circ$."},
]

# ---------------- worked examples ----------------
worked = [
 {"id": "we1", "kc": K2, "problem": "A boat is steered at $3.0\\ \\mathrm{m\\,s^{-1}}$ directly across a river. The river flows at $1.2\\ \\mathrm{m\\,s^{-1}}$ parallel to the banks. Determine the magnitude and direction of the boat's velocity relative to the bank.",
  "steps": [
   {"do": "Sketch the vector triangle: draw the river's velocity ($1.2\\ \\mathrm{m\\,s^{-1}}$ along the bank) and add the boat's velocity ($3.0\\ \\mathrm{m\\,s^{-1}}$ across) head to tail. The resultant runs from the start of the first arrow to the end of the second.",
    "why": "A sketch shows the two vectors are perpendicular, so the triangle is right-angled and Pythagoras applies; without it students add the magnitudes to get $4.2\\ \\mathrm{m\\,s^{-1}}$."},
   {"do": "Magnitude: $v=\\sqrt{3.0^2+1.2^2}=3.2\\ \\mathrm{m\\,s^{-1}}$.", "why": "Perpendicular vectors combine by Pythagoras, giving a speed larger than either but less than their sum.",
    "check": {"kind": "numeric", "answer": num(we1, "m s^-1")}},
   {"do": "Direction: $\\tan\\theta=\\dfrac{3.0}{1.2}$, so $\\theta=68^\\circ$ to the bank, pointing downstream and across.", "why": "State the angle from a named reference line (here the bank); a magnitude alone does not specify a vector."}],
  "faded": {"id": "we1f", "problem": "A boat is steered at $4.0\\ \\mathrm{m\\,s^{-1}}$ directly across a river flowing at $1.5\\ \\mathrm{m\\,s^{-1}}$. Determine the magnitude of its velocity relative to the bank.", "answer": num(we1f, "m s^-1"), "blank_from": 1}},
 {"id": "we2", "kc": K2, "problem": "An object moving at $4.0\\ \\mathrm{m\\,s^{-1}}$ to the right changes direction so that it moves at $3.0\\ \\mathrm{m\\,s^{-1}}$ downwards. Determine the magnitude and direction of the change in velocity.",
  "steps": [
   {"do": "Write the change as $\\Delta\\mathbf{v}=\\mathbf{v}_\\mathrm{f}-\\mathbf{v}_\\mathrm{i}$ and reverse the initial velocity: $-\\mathbf{v}_\\mathrm{i}$ is $4.0\\ \\mathrm{m\\,s^{-1}}$ to the left.",
    "why": "Subtracting a vector means adding its reverse. Adding $\\mathbf{v}_\\mathrm{i}$ instead gives the resultant of the two velocities, not the change."},
   {"do": "Add $-\\mathbf{v}_\\mathrm{i}$ (left, $4.0$) to $\\mathbf{v}_\\mathrm{f}$ (down, $3.0$) head to tail. These are perpendicular, so $|\\Delta\\mathbf{v}|=\\sqrt{4.0^2+3.0^2}=5.0\\ \\mathrm{m\\,s^{-1}}$.", "why": "The two vectors are at $90^\\circ$, so Pythagoras applies.",
    "check": {"kind": "numeric", "answer": num(we2, "m s^-1")}},
   {"do": "Direction: $\\tan\\alpha=\\dfrac{3.0}{4.0}$, so $\\alpha=37^\\circ$ below the leftward horizontal.", "why": "Give the direction relative to a stated axis; the change points down and to the left."}],
  "faded": {"id": "we2f", "problem": "An object moving at $6.0\\ \\mathrm{m\\,s^{-1}}$ to the right changes direction so that it moves at $8.0\\ \\mathrm{m\\,s^{-1}}$ upwards. Determine the magnitude of the change in velocity.", "answer": num(we2f, "m s^-1"), "blank_from": 1}},
 {"id": "we3", "kc": K3, "problem": "A force of $25\\ \\mathrm{N}$ acts at $35^\\circ$ above the horizontal. Determine its horizontal and vertical components.",
  "steps": [
   {"do": "Draw the force as the hypotenuse of a right-angled triangle, with the $35^\\circ$ angle between the force and the horizontal side.", "why": "The sketch shows which side is adjacent to the angle; sin and cos are then chosen by geometry, not by guesswork."},
   {"do": "Horizontal (adjacent to $\\theta$): $F_x=F\\cos\\theta=25\\cos35^\\circ=20\\ \\mathrm{N}$.", "why": "The adjacent side is hypotenuse $\\times\\cos\\theta$. Sense-check: at small angles most of the force is horizontal.",
    "check": {"kind": "numeric", "answer": num(we3x, "N")}},
   {"do": "Vertical (opposite $\\theta$): $F_y=F\\sin\\theta=25\\sin35^\\circ=14\\ \\mathrm{N}$.", "why": "Check by Pythagoras: $\\sqrt{20.5^2+14.3^2}=25\\ \\mathrm{N}$, the original magnitude.",
    "check": {"kind": "numeric", "answer": num(we3y, "N")}}],
  "faded": {"id": "we3f", "problem": "A force of $40\\ \\mathrm{N}$ acts at $20^\\circ$ above the horizontal. Determine its horizontal component.", "answer": num(we3f, "N"), "blank_from": 1}},
]

# ---------------- flashcards ----------------
fc = lambda n, kc, f, b: {"id": f"fc{n}", "kc": kc, "front": f, "back": b}
flashcards = [
 fc(1, K1, "Define a scalar quantity.", "A scalar quantity has magnitude only (no direction)."),
 fc(2, K1, "Define a vector quantity.", "A vector quantity has both magnitude and direction."),
 fc(3, K1, "Give four scalar quantities from the syllabus.", "Any four of: distance, speed, mass, time, energy, work, power, temperature, density, pressure, volume."),
 fc(4, K1, "Give five vector quantities from the syllabus.", "Any five of: displacement, velocity, acceleration, force, weight, momentum, field strength (gravitational or electric)."),
 fc(5, K1, "Why is temperature in °C a scalar although it can be negative?", "A negative sign is not a direction in space; temperature has magnitude only."),
 fc(6, K2, "What is the resultant of two vectors?", "The single vector that has the same effect as the two vectors together: their vector sum."),
 fc(7, K2, "How do you add two vectors using a vector triangle?", "Draw them to scale head to tail; the resultant joins the tail of the first to the head of the second."),
 fc(8, K2, "How do you subtract vector $\\mathbf{Y}$ from $\\mathbf{X}$?", "$\\mathbf{X}-\\mathbf{Y}=\\mathbf{X}+(-\\mathbf{Y})$: add the vector equal in magnitude but opposite in direction to $\\mathbf{Y}$."),
 fc(9, K2, "Write the change in velocity in terms of final and initial velocity.", "$\\Delta\\mathbf{v}=\\mathbf{v}_\\mathrm{f}-\\mathbf{v}_\\mathrm{i}$ (final minus initial, as vectors)."),
 fc(10, K3, "State the two perpendicular components of a vector $F$ at angle $\\theta$ to the $x$-axis.", "$F_x=F\\cos\\theta$ (adjacent to $\\theta$) and $F_y=F\\sin\\theta$ (opposite $\\theta$)."),
 fc(11, K3, "How do you find the magnitude of a vector from its perpendicular components?", "$F=\\sqrt{F_x^2+F_y^2}$, with $\\tan\\theta=F_y/F_x$ giving the angle to the $x$-axis."),
]

# ---------------- diagrams ----------------
A = lambda xy, tail: {"text": "", "xy": xy, "xytext": tail}
T = lambda text, xy: {"text": text, "xy": xy}
pad = {"points": [[-0.6, -1.0], [5.0, 3.8]], "color": "white"}
diagrams = [
 {"file": "Assets/9702/9702-1.4-components.svg", "type": "graph_sketch", "params": {
   "lines": [pad, {"points": [[0, 0], [4, 0]], "color": "#1f6feb"}, {"points": [[4, 0], [4, 3]], "color": "#d9480f"}, {"points": [[0, 0], [4, 3]], "color": "#1f2328"}],
   "annotations": [A([4, 3], [0, 0]), A([4, 0], [0, 0.0]), A([4, 3], [4, 0]), T("$F$", [1.7, 1.75]), T(r"$F_x = F\cos\theta$", [1.3, -0.45]), T(r"$F_y = F\sin\theta$", [4.15, 1.4]), T(r"$\theta$", [0.9, 0.2])]}},
 {"file": "Assets/9702/9702-1.4-velocity-change.svg", "type": "graph_sketch", "params": {
   "lines": [{"points": [[-0.5, -3.6], [5, 0.8]], "color": "white"}, {"points": [[0, 0], [0, -3]], "color": "#d9480f"}, {"points": [[0, 0], [4, 0]], "color": "#1f6feb"}, {"points": [[4, 0], [0, -3]], "color": "#1f2328", "style": "dashed"}],
   "annotations": [A([4, 0], [0, 0]), A([0, -3], [0, 0]), A([0, -3], [4, 0]), T(r"$\mathbf{v}_i$ (4.0 m/s)", [1.2, 0.3]), T(r"$\mathbf{v}_f$ (3.0 m/s)", [0.15, -1.6]), T(r"$\Delta\mathbf{v}=\mathbf{v}_f-\mathbf{v}_i$", [2.3, -1.9])]}},
 {"file": "Assets/9702/9702-1.4-vector-triangle.svg", "type": "graph_sketch", "params": {
   "lines": [{"points": [[-0.5, -1.0], [2.4, 4.6]], "color": "white"}, {"points": [[0, 0], [1.6, 0]], "color": "#1f6feb"}, {"points": [[1.6, 0], [1.6, 4.0]], "color": "#d9480f"}, {"points": [[0, 0], [1.6, 4.0]], "color": "#1f2328"}],
   "annotations": [A([1.6, 0], [0, 0]), A([1.6, 4.0], [1.6, 0]), A([1.6, 4.0], [0, 0]), T("river 1.2 m/s", [0.15, -0.65]), T("boat 3.0 m/s", [1.68, 1.9]), T("resultant 3.2 m/s", [-0.35, 2.7]), T(r"$\theta$", [0.42, 0.2])]}},
]

# ---------------- outline ----------------
outline = ("A scalar has magnitude only; a vector has magnitude and direction. Adding vectors means joining them head to tail (a vector triangle) "
           "and reading off the resultant; subtracting $\\mathbf{Y}$ means adding $-\\mathbf{Y}$, so a change is always final minus initial, "
           "$\\Delta\\mathbf{v}=\\mathbf{v}_\\mathrm{f}-\\mathbf{v}_\\mathrm{i}$. Any coplanar vector can be resolved into two perpendicular components: "
           "$F_x=F\\cos\\theta$ next to the angle and $F_y=F\\sin\\theta$ opposite it. Perpendicular components act independently, "
           "so combine them separately then use $F=\\sqrt{F_x^2+F_y^2}$ and $\\tan\\theta=F_y/F_x$. Direction is part of the answer.")
assert len(outline.split()) <= 150

pack = {"subtopic": SUB, "spec": "9702", "version": 1, "note": NOTE, "outline": outline, "misconceptions": misconceptions,
        "worked": worked, "items": past_items + generated, "flashcards": flashcards, "diagrams": diagrams}
out = ROOT / "build/out/packs/9702" / f"{SUB}.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(pack, ensure_ascii=False, indent=1))
print("pack", out, len(pack["items"]), "items")

# brute-force template sanity (2000 seeds each)
import random, sys
sys.path.insert(0, str(ROOT / "plugin/stem-tutor/skills/tutor/scripts"))
from tutorlib import packs
for it in generated:
    if it.get("template"):
        for s in range(2000):
            inst = packs.instantiate(it, random.Random(s)); a = inst["answer"]["value"]
            for d in inst["distractors"]:
                assert abs(d["value"] - a) > 0.03 * a, (it["id"], s, a, d)
print("templates ok")
