"""Generator for pack 9702-2.1 (Equations of motion). Content as data; every number computed here."""
import json, math
from pathlib import Path
import sympy as sp

ROOT = Path(__file__).resolve().parents[3]
SUB = "9702-2.1"
K = {i: f"{SUB}.{i}" for i in range(1, 10)}
NOTE = "Subjects/9702 Physics/02 Kinematics/2.1 Equations of motion.md"
G = 9.81
U = r"\mathrm{m\,s^{-1}}"
U2 = r"\mathrm{m\,s^{-2}}"
def num(v, unit, sf=(2, 3)): return {"value": v, "unit": unit, "sf_ok": list(sf)}
cos = lambda d: math.cos(math.radians(d)); sin = lambda d: math.sin(math.radians(d))

# ---------------- verified numbers ----------------
# past-paper checks
assert round(2 * (20 / (2 * math.pi)) / 20, 2) == 0.32
assert 0.5 * 20 * 2 - 0.5 * 10 * 1 == 15
assert round(sum([100, 75, 50])) == 225                               # s21_11_q7 -> 230 s
assert round(math.sqrt(2 * 12.7 / G) * 2, 2) == 3.22 and round(math.sqrt(2 * 12.7 / G), 2) == 1.61
assert round(math.sqrt(G / 3.71), 2) == 1.63 and round(3.71 / G, 3) == 0.378 and round(G / 3.71, 2) == 2.64 and round(math.sqrt(3.71 / G), 3) == 0.615
assert round(math.hypot(4.0, 8.0 - 1.62 * 9.0), 2) == 7.70 and round(4 + 6.58, 2) == 10.58
vy_s22 = G * 3.0; assert round(math.hypot(10.0, vy_s22)) == 31 and round(10 + vy_s22) == 39
T_ex = sp.symbols("T", positive=True); assert sp.solve(sp.Eq(10 * T_ex, sp.Rational(1, 2) * sp.Rational(1, 2) * T_ex**2), T_ex) == [40]
# worked / fixed items
we1_dist = 300 + 400; we1_disp = math.hypot(300, 400); assert we1_dist / 100 == 7.0 and we1_disp / 100 == 5.0
we1_ang = math.degrees(math.atan2(400, 300)); assert round(we1_ang) == 53
we1f = math.hypot(240, 70) / 25; assert we1f == 10.0
we2_vmax = 1.5 * 4.0; we2_dec = we2_vmax / 3.0; assert we2_vmax == 6.0 and we2_dec == 2.0; we2f = 2.5 * 4.0
we3_t0 = 5.0 * 6.0 / (6.0 + 4.0); we3_up = 0.5 * we3_t0 * 6.0; we3_dn = 0.5 * (5.0 - we3_t0) * 4.0
assert (we3_t0, we3_up, we3_dn) == (3.0, 9.0, 4.0); we3_disp = we3_up - we3_dn; we3_dist = we3_up + we3_dn
we3f_t0 = 5.0 * 8.0 / 10.0; we3f = 0.5 * we3f_t0 * 8.0 - 0.5 * (5.0 - we3f_t0) * 2.0; assert (we3f_t0, we3f) == (4.0, 15.0)
we4 = (15.0 - 3.0) / (4.0 - 2.0); we4f = (8.0 - 0.0) / (3.0 - 1.0); assert we4 == 6.0 and we4f == 4.0
we5 = (6.0 - 24.0) / (9.0 - 3.0); we5f = (5.0 - 20.0) / (8.0 - 2.0); assert we5 == -3.0 and we5f == -2.5
uu, aa, tt = 2.0, 3.0, 4.0; vv = uu + aa * tt; assert uu * tt + 0.5 * aa * tt**2 == 0.5 * (uu + vv) * tt == 32.0
we6f = 3.0 * 5.0 + 0.5 * 2.0 * 5.0**2; assert we6f == 40.0
we7_h = 12.0**2 / (2 * G); we7_t = 2 * 12.0 / G; we7f = 15.0**2 / (2 * G)
# algebra checks with sympy
u_, v_, a_, t_, s_ = sp.symbols("u v a t s")
assert sp.simplify(sp.expand(a_ * s_ * 2) - sp.expand((u_ + v_) * (v_ - u_)) + 0) == sp.expand(2*a_*s_ - v_**2 + u_**2)  # (u+v)(v-u)=v^2-u^2 ; s=(v^2-u^2)/2a
assert sp.expand(sp.Rational(1, 2) * (u_ + u_ + a_ * t_) * t_ - (u_ * t_ + a_ * t_**2 / 2)) == 0
we8_grad = 0.98 / 0.200; we8_g = 2 * we8_grad; we8f_g = 2 * (1.20 / 0.250)
assert round(we8_grad, 2) == 4.90 and round(we8_g, 2) == 9.80 and round(we8f_g, 2) == 9.60
# structured: car
car_v = 2.0 * 5.0; car_dist = 0.5 * car_v * 5.0 + car_v * 10.0 + 0.5 * car_v * 4.0; car_brake = car_v / 4.0
assert (car_v, car_dist, car_brake) == (10.0, 145.0, 2.5)
# structured: tangent
tan_v = (20.0 - 2.0) / (7.0 - 1.0); assert tan_v == 3.0
# structured: cliff (up positive, s = -25, u = 14, a = -g)
t_c = sp.symbols("t_c")
roots = sp.solve(sp.Eq(-25, 14 * t_c - sp.Rational(981, 200) * t_c**2), t_c)
cliff_t = max(float(r) for r in roots); cliff_v = math.sqrt(14.0**2 + 2 * G * 25.0)
assert round(cliff_t, 2) == 4.10 and abs((14 - G * cliff_t) + cliff_v) < 1e-9 and round(cliff_v, 1) == 26.2
# structured: kick
kv, kth = 20.0, 40.0; kx, ky = kv * cos(kth), kv * sin(kth); kT = 2 * ky / G; kR = kx * kT
assert round(kx, 1) == 15.3 and round(ky, 1) == 12.9 and round(kT, 2) == 2.62 and round(kR, 1) == 40.2

# ---------------- misconceptions ----------------
misconceptions = [
 {"id": "m1", "kc": K[1], "statement": "Ignoring direction: using distance for displacement and average speed for average velocity, or subtracting speeds to find a change in velocity when the direction reverses.",
  "refutation": "Displacement and velocity are vectors. Average velocity is displacement divided by time, and displacement is the straight-line change in position from start to finish, so it can be much smaller than the distance travelled. A change in velocity is final minus initial, with signs for direction.",
  "contrast": "A toy car goes once round a circular track in $40\\ \\mathrm{s}$: its average speed is $0.50\\ \\mathrm{m\\,s^{-1}}$ but its average velocity over the whole lap is zero, because it returns to its starting point.", "source": "ER 9702 w22 P12 Q5"},
 {"id": "m2", "kc": K[1], "statement": "Tying acceleration to speed instead of change of velocity: 'constant speed means no acceleration' or 'at the top of its flight the velocity is zero, so the acceleration is zero'.",
  "refutation": "Acceleration is the rate of change of velocity, a vector. A body going round a bend at constant speed changes direction, so its velocity changes and it accelerates. A ball at the top of its flight has zero velocity for an instant, but its velocity is still changing at $9.81\\ \\mathrm{m\\,s^{-2}}$ downwards.",
  "contrast": "A ball thrown straight up has $v=0$ at the top but $a=9.81\\ \\mathrm{m\\,s^{-2}}$ downwards throughout; if $a$ were zero there it would stay there.", "source": "research"},
 {"id": "m3", "kc": K[3], "statement": "Adding the area below the time axis to the area above it when finding displacement from a velocity-time graph.",
  "refutation": "Area above the time axis is displacement in the positive direction; area below is displacement in the opposite direction, so it is subtracted. The sum of the two magnitudes is the total distance, not the displacement.",
  "contrast": "A stone thrown up at $20\\ \\mathrm{m\\,s^{-1}}$: the area above the axis is $20\\ \\mathrm{m}$ and the area below the axis, from $2.0\\ \\mathrm{s}$ to $3.0\\ \\mathrm{s}$, is $5\\ \\mathrm{m}$. Displacement $=15\\ \\mathrm{m}$ above the start (not $25\\ \\mathrm{m}$); distance travelled $=25\\ \\mathrm{m}$.", "source": "ER 9702 w20 P12 Q6"},
 {"id": "m4", "kc": K[5], "statement": "Reading gradients wrongly from a graph: counting grid squares instead of using the axis scale, or dividing a single value by a single time (like $v/t$) instead of using the change in each, or not comparing the graph with its equation, so that the gradient of $h$ against $t^2$ is taken as $g$ instead of $\\tfrac12g$.",
  "refutation": "A gradient is change in $y$ divided by change in $x$, read from the labelled axes with a large triangle. Grid squares are not equal to units unless the scale says so, and a single point gives $v/t$ only if the line passes through the origin. To see what a gradient means, compare the equation with $y=mx$: from $h=\\tfrac12gt^2$ the gradient of $h$ against $t^2$ is $\\tfrac12g$.",
  "contrast": "A line from $(2.0\\ \\mathrm{s},\\ 6.0\\ \\mathrm{m\\,s^{-1}})$ to $(6.0\\ \\mathrm{s},\\ 14\\ \\mathrm{m\\,s^{-1}})$ has gradient $8.0/4.0=2.0\\ \\mathrm{m\\,s^{-2}}$, not $14/6=2.3$.", "source": "ER 9702 w21 P12 Q6"},
 {"id": "m5", "kc": K[7], "statement": "Answering only half a trip: finding the time to reach the top of a vertical throw and forgetting to double it for the whole flight.",
  "refutation": "With no air resistance, the ascent and descent to the same level take equal times, so the time in the air is twice the time to the highest point. Check what the question asks for: 'time to the top' or 'total time in the air'.",
  "contrast": "A ball rising $12.7\\ \\mathrm{m}$ takes $1.61\\ \\mathrm{s}$ to reach the top, so its total time in the air is $3.22\\ \\mathrm{s}$.", "source": "ER 9702 w19 P12 Q6"},
 {"id": "m6", "kc": K[7], "statement": "Sign errors in suvat: using $+9.81$ for a body moving upwards when upwards is positive, or mixing the signs of $u$, $a$ and $s$.",
  "refutation": "Choose one direction as positive at the start and keep it. If upwards is positive then $a=-9.81\\ \\mathrm{m\\,s^{-2}}$, $u$ is positive for an upward throw and the displacement $s$ is negative when the object ends below its start.",
  "contrast": "Thrown upwards from a $25\\ \\mathrm{m}$ cliff, the ball lands at $s=-25\\ \\mathrm{m}$ with $a=-9.81\\ \\mathrm{m\\,s^{-2}}$; writing $s=+25$ gives a different, wrong equation.", "source": "ER 9702 w20 P23 Q3"},
 {"id": "m7", "kc": K[9], "statement": "Believing a force is needed in the direction of motion, so that a projectile in flight has a 'forward force' or an 'upward force' that runs out at the top.",
  "refutation": "A force is needed to change velocity, not to maintain it. Once a projectile has left the thrower its only forces are weight (down) and, in air, drag (opposite to the velocity). The forward motion is due to the initial horizontal velocity, which is unchanged when there is no drag.",
  "contrast": "At the top of its flight the velocity is horizontal, so drag acts backwards and weight acts downwards. No arrow points forwards.", "source": "ER 9702 s22 P11 Q9"},
 {"id": "m8", "kc": K[9], "statement": "Not treating horizontal and vertical motion separately: adding the components as magnitudes instead of using Pythagoras, using the launch speed as the vertical component, or thinking a larger horizontal speed changes the time of fall.",
  "refutation": "The two perpendicular motions are independent. Resolve the launch velocity, apply suvat to each direction separately, and join them only by time. Recombine perpendicular components with $v=\\sqrt{v_x^2+v_y^2}$.",
  "contrast": "A ball kicked horizontally and one dropped from the same height land together: the vertical motion is the same, whatever the horizontal speed.", "source": "ER 9702 w23 P12 Q6"},
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
 past(1, "9702_w22_12_q5", "CAIE 9702 · Nov 2022 · P12 · Q5", K[1], 4, "Determine",
  f"A toy car travels on a circular track at a constant speed of $0.50\\ {U}$. It passes a point on the track at time $t=0$ and takes $40\\ \\mathrm{{s}}$ to travel once around the track. The magnitude of the average velocity of the car between $t=0$ and $t=20\\ \\mathrm{{s}}$ is $v_{{20}}$. The magnitude of the average velocity between $t=0$ and $t=40\\ \\mathrm{{s}}$ is $v_{{40}}$. What are $v_{{20}}$ and $v_{{40}}$, in $\\mathrm{{m\\,s^{{-1}}}}$?", "A",
  "Average velocity is displacement divided by time. In $20\\ \\mathrm{s}$ the car travels $10\\ \\mathrm{m}$ (half the circumference) but its displacement is the diameter, $20/\\pi=6.4\\ \\mathrm{m}$, so $v_{20}=6.4/20=0.32\\ \\mathrm{m\\,s^{-1}}$. After a full lap the displacement is zero, so $v_{40}=0$. The popular wrong options C and D give the average speed, $0.50\\ \\mathrm{m\\,s^{-1}}$, which ignores direction.",
  {"A": "$v_{20}=0.32$, $v_{40}=0$", "B": "$v_{20}=0.32$, $v_{40}=0.32$", "C": "$v_{20}=0.50$, $v_{40}=0$", "D": "$v_{20}=0.50$, $v_{40}=0.50$"}, img("9702_w22_12_q5"), {"C": "m1", "D": "m1"}),
 past(2, "9702_w21_13_q6", "CAIE 9702 · Nov 2021 · P13 · Q6", K[2], 2, "Identify",
  "The graph shows the variation with time of the acceleration of a car. What must the shaded area under the graph represent?", "B",
  "Acceleration is change in velocity per unit time, so acceleration multiplied by time (the area under an acceleration-time graph) is change in velocity, $v-u=at$. Some candidates chose A, the average velocity, but the area is $at=v-u$, a change in velocity. It equals the final velocity only if the car starts from rest, and the average velocity only by coincidence, so it need not be either: the question asks what it must represent.",
  {"A": "the average velocity of the car", "B": "the change in velocity of the car", "C": "the final velocity of the car", "D": "the initial velocity of the car"}, img("9702_w21_13_q6"), None),
 past(3, "9702_w20_12_q6", "CAIE 9702 · Nov 2020 · P12 · Q6", K[3], 3, "Determine",
  "A stone is thrown vertically upwards from a point X at time $t=0$. The variation with time $t$ of the velocity $v$ of the stone is shown. What is the displacement of the stone from point X at time $t=3.0\\ \\mathrm{s}$?", "A",
  "The stone is thrown up at $20\\ \\mathrm{m\\,s^{-1}}$ and its velocity is zero at $2.0\\ \\mathrm{s}$, so the area above the axis is $\\tfrac12\\times2.0\\times20=20\\ \\mathrm{m}$ upwards. The area below the axis from $2.0\\ \\mathrm{s}$ to $3.0\\ \\mathrm{s}$ is $\\tfrac12\\times1.0\\times10=5\\ \\mathrm{m}$ downwards, so the displacement is $20-5=15\\ \\mathrm{m}$ above X. Many candidates chose B, giving the right size with the wrong direction: the positive area is the larger one, so the stone is above X. C (25 m) adds the areas.",
  {"A": "15 m above X", "B": "15 m below X", "C": "25 m above X", "D": "25 m below X"}, img("9702_w20_12_q6"), {"C": "m3"}),
 past(4, "9702_w21_12_q6", "CAIE 9702 · Nov 2021 · P12 · Q6", K[5], 4, "Determine",
  f"The graph shows the variation with time $t$ of the velocity of a vehicle moving in a straight line. The vehicle, moving at $4.0\\ {U}$, begins to accelerate at time $t=0$. What is the vehicle's acceleration at time $t=3.0\\ \\mathrm{{s}}$?", "C",
  "The velocity-time graph is a curve, so the acceleration at $3.0\\ \\mathrm{s}$ is the gradient of the tangent there: $\\Delta v/\\Delta t=8\\ \\mathrm{m\\,s^{-1}}/6.0\\ \\mathrm{s}=1.3\\ \\mathrm{m\\,s^{-2}}$. Many candidates chose A ($0.67$) because they counted grid squares ($4/6$) instead of reading the values on the labelled axes. D ($2.0$) divides the single reading $6.0\\ \\mathrm{m\\,s^{-1}}$ by $3.0\\ \\mathrm{s}$, which gives the gradient only for a straight line through the origin.",
  {"A": f"$0.67\\ {U2}$", "B": f"$1.0\\ {U2}$", "C": f"$1.3\\ {U2}$", "D": f"$2.0\\ {U2}$"}, img("9702_w21_12_q6"), {"A": "m4", "D": "m4"}),
 past(5, "9702_s21_11_q7", "CAIE 9702 · Jun 2021 · P11 · Q7", K[7], 4, "Calculate",
  f"A train, initially at rest at a station, has a uniform acceleration of $0.20\\ {U2}$ until it reaches a speed of $20\\ {U}$. It travels for a time at this constant speed and then has a uniform deceleration of $0.40\\ {U2}$ until it comes to rest at the next station. The distance between the two stations is $3000\\ \\mathrm{{m}}$. What is the time taken by the train to travel between the two stations?", "C",
  "Sketch the velocity-time graph: acceleration takes $20/0.20=100\\ \\mathrm{s}$ (distance $1000\\ \\mathrm{m}$) and deceleration takes $20/0.40=50\\ \\mathrm{s}$ (distance $500\\ \\mathrm{m}$). The remaining $1500\\ \\mathrm{m}$ at $20\\ \\mathrm{m\\,s^{-1}}$ takes $75\\ \\mathrm{s}$, so the total time is $100+75+50=225\\ \\mathrm{s}\\approx230\\ \\mathrm{s}$. Option A, $75\\ \\mathrm{s}$, is only the constant-speed part.",
  {"A": "75 s", "B": "150 s", "C": "230 s", "D": "300 s"}, None, None),
 past(6, "9702_w19_12_q6", "CAIE 9702 · Nov 2019 · P12 · Q6", K[7], 3, "Calculate",
  "A ball is thrown vertically upwards from ground level and reaches a maximum height of $12.7\\ \\mathrm{m}$ before falling back to ground level. Assume that air resistance is negligible. What is the total time for which the ball is in the air?", "B",
  "Time to fall $12.7\\ \\mathrm{m}$ from rest: $t=\\sqrt{2h/g}=\\sqrt{2\\times12.7/9.81}=1.61\\ \\mathrm{s}$. Rising and falling take equal times, so the total is $2\\times1.61=3.22\\ \\mathrm{s}$. Option A, the most popular wrong answer, is the time to the top only: the doubling was forgotten.",
  {"A": "1.61 s", "B": "3.22 s", "C": "3.88 s", "D": "5.18 s"}, None, {"A": "m5"}),
 past(7, "9702_w23_13_q6", "CAIE 9702 · Nov 2023 · P13 · Q6", K[7], 5, "Calculate",
  f"The time taken for an object to fall from rest through a certain distance on Mars is $T_\\mathrm{{M}}$. The time taken for the same object to fall from rest through the same distance on Earth is $T_\\mathrm{{E}}$. The acceleration of free fall on Mars is $3.71\\ {U2}$. Assume that air resistance is negligible on both Earth and Mars. What is the ratio $T_\\mathrm{{M}}/T_\\mathrm{{E}}$?", "C",
  "From $h=\\tfrac12gT^2$ the time is $T=\\sqrt{2h/g}$, so for the same $h$ the times are in the ratio $T_\\mathrm{M}/T_\\mathrm{E}=\\sqrt{g_\\mathrm{E}/g_\\mathrm{M}}=\\sqrt{9.81/3.71}=1.63$. Option A ($0.378$) is the most popular wrong answer, $g_\\mathrm{M}/g_\\mathrm{E}$: it is the wrong way up (Mars has the weaker gravity, so the fall takes longer, ratio above 1) and has no square root. Option D ($2.64$) forgets the square root.",
  {"A": "0.378", "B": "0.615", "C": "1.63", "D": "2.64"}, img("9702_w23_13_q6"), None),
 past(8, "9702_s21_13_q7", "CAIE 9702 · Jun 2021 · P13 · Q7", K[8], 4, "Determine",
  "A steel ball is dropped from rest from a height $h$ above the ground. The ball hits the ground after a time $t$. This is repeated for a number of different heights. The graph shows the variation of $h$ with $t^2$ for the ball, a straight line through the origin. The gradient of the graph is $G$. Which expression gives the acceleration of the ball?", "C",
  "For a ball released from rest $h=\\tfrac12at^2$, so a graph of $h$ against $t^2$ has gradient $\\tfrac12a$. If the gradient is $G$ then $a=2G$. Taking $G$ itself as the acceleration (B) forgets the factor $\\tfrac12$ in $s=ut+\\tfrac12at^2$.",
  {"A": "$G/2$", "B": "$G$", "C": "$2G$", "D": "$G^2$"}, img("9702_s21_13_q7"), {"B": "m4"}),
 past(9, "9702_w23_12_q6", "CAIE 9702 · Nov 2023 · P12 · Q6", K[9], 4, "Calculate",
  f"An astronaut on the Moon, where there is no air resistance, throws a ball. The ball's initial velocity has a vertical component of $8.00\\ {U}$ and a horizontal component of $4.00\\ {U}$. The acceleration of free fall on the Moon is $1.62\\ {U2}$. What is the speed of the ball $9.00\\ \\mathrm{{s}}$ after being thrown?", "B",
  "Horizontally there is no acceleration, so $v_x=4.00\\ \\mathrm{m\\,s^{-1}}$. Vertically $v_y=u+at=8.00-1.62\\times9.00=-6.58\\ \\mathrm{m\\,s^{-1}}$. The speed is $\\sqrt{4.00^2+6.58^2}=7.70\\ \\mathrm{m\\,s^{-1}}$. C ($10.6$) adds the magnitudes of the two components instead of using Pythagoras; A ($6.58$) is only the vertical component.",
  {"A": f"$6.58\\ {U}$", "B": f"$7.70\\ {U}$", "C": f"$10.6\\ {U}$", "D": f"$14.6\\ {U}$"}, img("9702_w23_12_q6"), {"C": "m8"}),
 past(10, "9702_s22_11_q6", "CAIE 9702 · Jun 2022 · P11 · Q6", K[9], 3, "Calculate",
  f"A ball is thrown horizontally with a speed of $10.0\\ {U}$ above horizontal ground. The ball hits the ground after a time of $3.0\\ \\mathrm{{s}}$. Air resistance is negligible. What is the speed of the ball just before it hits the ground?", "C",
  "The horizontal component stays $10.0\\ \\mathrm{m\\,s^{-1}}$. The vertical component is $v_y=0+9.81\\times3.0=29\\ \\mathrm{m\\,s^{-1}}$. The speed is the magnitude of the resultant, $\\sqrt{10.0^2+29.4^2}=31\\ \\mathrm{m\\,s^{-1}}$. Option D ($39$) adds the two components ($10+29$) instead of using Pythagoras.",
  {"A": f"$10\\ {U}$", "B": f"$29\\ {U}$", "C": f"$31\\ {U}$", "D": f"$39\\ {U}$"}, None, {"D": "m8"}),
 past(11, "9702_s22_11_q9", "CAIE 9702 · Jun 2022 · P11 · Q9", K[9], 3, "Identify",
  "A projectile is launched at an angle above horizontal ground and travels through the air. The projectile reaches its maximum height at position X. Assume that no upthrust acts on the projectile. Which diagram shows the directions of the force or forces acting on the projectile at position X?", "B",
  "At X the projectile is moving horizontally, and it is moving through air, so two forces act: its weight, vertically downwards, and air resistance, horizontally in the direction opposite to its motion. Almost half of candidates chose A, which has a forwards force along the direction of motion: nothing pushes the projectile forward once it has left the launcher, and a force is not needed to keep it moving. C shows only a forwards force and no weight.",
  None, img("9702_s22_11_q9"), {"A": "m7", "C": "m7"}),
 past(12, "9702_w22_12_q7", "CAIE 9702 · Nov 2022 · P12 · Q7", K[7], 4, "Determine",
  f"A goods train passes through a station at a steady speed of $10\\ {U}$ at time $t=0$. An express train is at rest at the station. The express train leaves the station with a uniform acceleration of $0.5\\ {U2}$ just as the goods train goes past. Both trains move in the same direction on straight, parallel tracks. At which time $t$ does the express train overtake the goods train?", "D",
  "They have travelled the same distance when they meet: $10T=\\tfrac12\\times0.5\\times T^2$, so $T=40\\ \\mathrm{s}$. Option C, $20\\ \\mathrm{s}$, is when the express train reaches the goods train's speed ($0.5\\times20=10\\ \\mathrm{m\\,s^{-1}}$), when the gap is largest; equal speeds do not mean equal positions.",
  {"A": "6 s", "B": "10 s", "C": "20 s", "D": "40 s"}, None, None),
]

# ---------------- generated items ----------------
def gen(n, kcs, diff, cw, stem, expl, hints, **kw):
    it = {"id": f"{SUB}-i{n:02d}", "kcs": kcs, "kind": kw.pop("kind"), "difficulty": diff, "command_word": cw,
          "source": {"type": "generated"}, "stem": stem}
    it.update(kw); it["explanation"] = expl; it["hints"] = hints
    return it

def tpl_num(params, answer, distractors=None, constraints=None, derived=None):
    t = {"params": params, "answer": answer}
    if derived: t["derived"] = derived
    if distractors: t["distractors"] = distractors
    t["constraints"] = constraints or ["1 > 0"]
    return t

ch = lambda *v: {"choices": list(v)}
generated = [
 # ---- KC 2.1.1
 gen(1, [K[1]], 1, "Define", "Define velocity and acceleration.",
  "Velocity is the rate of change of displacement; acceleration is the rate of change of velocity. Both are vectors.",
  ["Each quantity is defined as a rate of change of another quantity: which one?", "Velocity is linked to displacement, and acceleration is linked to velocity.", "Say 'rate of change of ...' for each, naming the correct quantity (displacement or distance, velocity or speed)."],
  kind="short", marks=2, rubric=[
   {"point": "velocity is the rate of change of displacement", "keywords": [["rate of change of displacement", "change in displacement per unit time", "displacement per unit time", "displacement divided by time", "displacement / time", "displacement/time", "change of displacement per"]]},
   {"point": "acceleration is the rate of change of velocity", "keywords": [["rate of change of velocity", "change in velocity per unit time", "velocity per unit time", "change of velocity per", "velocity divided by time", "change in velocity / time", "change in velocity divided by time"]]}]),
 gen(2, [K[1]], 4, "Calculate",
  "A car travels at a constant speed along a semicircular road of radius [[r]] m, from one end of a diameter to the other, in [[t]] s. Calculate the magnitude of the average velocity of the car.",
  "Average velocity is displacement divided by time. The displacement is the diameter, $2r$, so $v=2r/t$. Using the length of the road, $\\pi r$, gives the average speed, which is a different quantity.",
  ["Velocity uses displacement, not the distance along the road.", "Sketch the semicircle: what is the straight-line change in position between the two ends?", "Which straight-line distance links the two ends of the semicircle, in terms of $r$?"],
  kind="numeric", answer={"unit": "m s^-1", "sf_ok": [2, 3]}, marks=3,
  template=tpl_num({"r": ch(40, 50, 60, 75, 80), "t": ch(10, 12, 15, 20, 25)}, "2*r/t", [{"expr": "pi*r/t", "misconception": "m1"}])),
 gen(3, [K[1]], 2, "Identify", f"A car moves round a roundabout at a constant speed of $12\\ {U}$. Which statement is correct?",
  "Velocity is a vector, so a change in direction is a change in velocity even when the speed is constant. The car is therefore accelerating. The statements saying the acceleration is zero or the velocity is constant mistake constant speed for constant velocity.",
  ["Speed and velocity are not the same kind of quantity: which has a direction?", "Acceleration is the rate of change of velocity: does the roundabout change the car's velocity?", "Ask whether the car's direction of travel stays the same as it goes round."],
  kind="mcq", answer="C", shuffle=True, marks=1,
  options={"A": "Its acceleration is zero because its speed is constant.", "B": "Its velocity is constant because its speed is constant.",
           "C": "Its velocity is changing because its direction is changing, so it is accelerating.", "D": "Its displacement from its starting point increases at a constant rate."},
  distractors={"A": "m2", "B": "m2"}),
 gen(4, [K[1]], 3, "Calculate",
  "A ball travelling at [[u]] m s$^{-1}$ towards a wall rebounds along the same line at [[v]] m s$^{-1}$. It is in contact with the wall for [[t]] ms. Calculate the magnitude of the average acceleration of the ball during the contact.",
  "Take the initial direction as positive: $\\Delta v=(-v)-(+u)$, magnitude $u+v$. The acceleration is $\\Delta v/\\Delta t=(u+v)/\\Delta t$, with the time converted to seconds. Subtracting the speeds ignores the reversal of direction.",
  ["Velocity is a vector and the ball reverses direction.", "Choose one direction as positive and give the final velocity its sign.", "Change in velocity is final minus initial with signs; then divide by the time in seconds."],
  kind="numeric", answer={"unit": "m s^-2", "sf_ok": [2, 3]}, marks=3,
  template=tpl_num({"u": ch(8, 10, 12, 15, 20), "v": ch(4, 5, 6, 9), "t": ch(5, 8, 10, 12, 20)}, "(u + v)/T", [{"expr": "(u - v)/T", "misconception": "m1"}], derived={"T": "t/1000"})),
 # ---- KC 2.1.2
 gen(5, [K[2]], 2, "Identify", "For an object moving in a straight line, which row shows what the gradient and the area under a velocity-time graph represent?",
  "The gradient of a velocity-time graph is change in velocity divided by time, which is acceleration, and the area under it is velocity multiplied by time, which is displacement. Taking the area as velocity or acceleration is wrong because velocity multiplied by time is displacement, and taking the gradient as displacement is wrong because velocity divided by time is acceleration.",
  ["Work out the units: velocity divided by time, and velocity multiplied by time.", "The units of gradient ($\\mathrm{m\\,s^{-1}}\\ /\\ \\mathrm{s}$) and of area ($\\mathrm{m\\,s^{-1}}\\times\\mathrm{s}$) identify each quantity.", "Match the unit of the gradient to a quantity, then the unit of the area to another."],
  kind="mcq", answer="B", shuffle=True, marks=1,
  options={"A": "gradient: displacement; area: acceleration", "B": "gradient: acceleration; area: displacement", "C": "gradient: acceleration; area: velocity", "D": "gradient: displacement; area: velocity"}),
 gen(6, [K[2]], 2, "Describe", "Describe what a horizontal straight line represents on (i) a displacement-time graph and (ii) a velocity-time graph.",
  "A horizontal line on a displacement-time graph has zero gradient, so zero velocity: the object is at rest. A horizontal line on a velocity-time graph has zero gradient, so zero acceleration: constant velocity.",
  ["Each graph's gradient represents a different quantity.", "A horizontal line has zero gradient: zero what, for each graph?", "Name the quantity that the gradient represents on each graph, and then say what it being zero means."],
  kind="short", marks=2, rubric=[
   {"point": "displacement-time: stationary / at rest", "keywords": [["stationary", "at rest", "not moving", "zero velocity", "remains at the same", "no velocity"]]},
   {"point": "velocity-time: constant velocity / zero acceleration", "keywords": [["constant velocity", "constant speed", "uniform velocity", "zero acceleration", "not accelerating", "no acceleration", "steady"]]}]),
 gen(7, [K[2]], 3, "Identify", "A ball is thrown vertically upwards, rises, and falls back to the ground, air resistance being negligible. Taking upwards as positive, which describes the velocity-time graph from launch to the moment before landing?",
  "The acceleration is constant at $-9.81\\ \\mathrm{m\\,s^{-2}}$, so the velocity-time graph is a single straight line with a negative gradient. It is positive on the way up, passes through zero at the highest point and is negative on the way down. A curve is the displacement-time graph, and a V-shape is a speed-time graph.",
  ["The acceleration is constant: what shape is a velocity-time graph if the acceleration is constant?", "Decide the sign of the velocity on the way up and on the way down when upwards is positive.", "The velocity is zero at the highest point: where does the graph cross the time axis?"],
  kind="mcq", answer="A", shuffle=True, marks=1,
  options={"A": "one straight line with a negative gradient, crossing the time axis at the highest point", "B": "a curve with zero gradient at the highest point",
           "C": "one straight line with a positive gradient", "D": "a straight line falling to zero and then rising again to positive values"}),
 {"id": f"{SUB}-i08", "kcs": [K[2], K[3]], "kind": "structured", "difficulty": 4, "command_word": "Determine", "source": {"type": "generated"},
  "stem": f"A car starts from rest and accelerates uniformly at $2.0\\ {U2}$ for $5.0\\ \\mathrm{{s}}$. It then travels at constant velocity for $10\\ \\mathrm{{s}}$ before braking uniformly to rest in $4.0\\ \\mathrm{{s}}$. (a) Sketch the velocity-time graph for the whole journey. (b) Determine the total distance travelled.",
  "scheme": [{"mark": "B1", "point": "sketch: straight line from the origin up to $10\\ \\mathrm{m\\,s^{-1}}$ at $5.0\\ \\mathrm{s}$, horizontal to $15\\ \\mathrm{s}$, then a straight line down to zero at $19\\ \\mathrm{s}$", "check": {"kind": "numeric", "answer": num(car_v, "m s^-1")}},
             {"mark": "M1", "point": "distance is the area under the velocity-time graph (triangle + rectangle + triangle)"},
             {"mark": "A1", "point": f"total distance $=\\tfrac12\\times5.0\\times10+10\\times10+\\tfrac12\\times4.0\\times10=145\\ \\mathrm{{m}}$", "check": {"kind": "numeric", "answer": num(car_dist, "m")}}],
  "marks": 3, "explanation": "The maximum speed is $at=2.0\\times5.0=10\\ \\mathrm{m\\,s^{-1}}$. Uniform acceleration gives straight lines, constant velocity a horizontal line, and the distance is the total area beneath the graph.",
  "hints": ["Uniform acceleration means straight-line sections on a velocity-time graph.", "Find the speed at the end of the first section with $v=u+at$, then draw the three sections in order.", "The distance is the area under the graph: split it into two triangles and a rectangle."]},
 gen(9, [K[5], K[2]], 2, "Determine",
  "The velocity of a trolley changes uniformly from [[u]] m s$^{-1}$ to [[v]] m s$^{-1}$ in [[t]] s, so its velocity-time graph is a straight line. Determine the acceleration of the trolley.",
  "The acceleration is the gradient of the velocity-time graph: change in velocity divided by change in time, $(v-u)/t$. Dividing the final velocity by the time works only if the line starts at the origin.",
  ["Acceleration is what the gradient of a velocity-time graph represents.", "A gradient uses the change in each quantity, not a single value.", "Find the change in velocity first, then divide by the time taken."],
  kind="numeric", answer={"unit": "m s^-2", "sf_ok": [2, 3]}, marks=2,
  template=tpl_num({"u": ch(2, 3, 4, 5, 6), "v": ch(9, 12, 14, 18), "t": ch(2, 3, 4, 5)}, "(v - u)/t", [{"expr": "v/t", "misconception": "m4"}])),
 # ---- KC 2.1.3
 gen(10, [K[3]], 3, "Determine",
  "The velocity-time graph of a cyclist is a horizontal line at [[v]] m s$^{-1}$ for [[a]] s, followed by a straight line falling uniformly to zero over a further [[b]] s. Determine the total displacement of the cyclist.",
  "Displacement is the area under the velocity-time graph: a rectangle $vt_1$ plus a triangle $\\tfrac12vt_2$.",
  ["Displacement is found from the area under a velocity-time graph.", "Split the graph into two shapes: what are they?", "Find the area of the rectangle and the area of the triangle, then add them (both are above the axis)."],
  kind="numeric", answer={"unit": "m", "sf_ok": [2, 3]}, marks=3,
  template=tpl_num({"v": ch(6, 8, 10, 12), "a": ch(4, 5, 6, 8), "b": ch(3, 4, 5, 6)}, "v*a + 0.5*v*b", [{"expr": "v*(a + b)"}])),
 gen(11, [K[3]], 4, "Determine",
  "The velocity of an object moving along a straight line changes uniformly from [[a]] m s$^{-1}$ in one direction at $t=0$ to [[b]] m s$^{-1}$ in the opposite direction at $t=[[T]]$ s. Determine its displacement from its starting point at $t=[[T]]$ s, in the direction of the initial velocity.",
  "Taking the initial direction as positive, the graph goes from $+a$ to $-b$. The signed area is the displacement: $\\tfrac12(a-b)T$, the average velocity times the time. Adding the two areas' magnitudes gives the distance travelled, which is larger.",
  ["Give the velocity at the end a negative sign.", "The area below the time axis counts as displacement in the opposite direction.", "For a straight-line graph the displacement is the average velocity multiplied by time: find the average of the signed end values."],
  kind="numeric", answer={"unit": "m", "sf_ok": [2, 3]}, marks=3,
  template=tpl_num({"a": ch(8, 10, 12), "b": ch(2, 4, 6), "T": ch(4, 6, 8, 10)}, "T*(a - b)/2",
                   [{"expr": "T*(a**2 + b**2)/(2*(a + b))", "misconception": "m3"}], constraints=["a > b"])),
 gen(12, [K[3]], 2, "State", "State what is represented by the area under a velocity-time graph, and how an area below the time axis should be treated.",
  "The area under a velocity-time graph is the displacement. An area below the time axis is negative (displacement in the opposite direction) and is subtracted from the areas above it.",
  ["Consider the units: velocity multiplied by time.", "The graph can go below the time axis when the object turns round.", "Area = displacement; think about what a negative velocity does to that displacement."],
  kind="short", marks=2, rubric=[
   {"point": "area under v-t graph = displacement", "keywords": [["displacement", "change in position", "change in displacement"]]},
   {"point": "area below the axis is negative / subtracted (opposite direction)", "keywords": [["below"], ["negative", "subtract", "opposite direction", "opposite way", "minus", "backwards"]]}]),
 # ---- KC 2.1.4
 gen(13, [K[4]], 3, "Determine",
  "The displacement-time graph of a runner is a straight line passing through the points ([[t1]] s, [[s1]] m) and ([[t2]] s, [[s2]] m). Determine the velocity of the runner.",
  "Velocity is the gradient of a displacement-time graph: $(s_2-s_1)/(t_2-t_1)$. Dividing one displacement by one time gives the gradient only for a line through the origin.",
  ["Velocity is what the gradient of a displacement-time graph represents.", "A gradient needs a change in $s$ over a change in $t$: use both points.", "Subtract the two displacements and subtract the two times, then divide."],
  kind="numeric", answer={"unit": "m s^-1", "sf_ok": [2, 3]}, marks=2,
  template=tpl_num({"t1": ch(2, 3), "t2": ch(6, 8, 10), "s1": ch(2, 4), "s2": ch(30, 36, 40)}, "(s2 - s1)/(t2 - t1)", [{"expr": "s2/t2", "misconception": "m4"}],
                   constraints=["(s2*t1 - s1*t2)/(s2*(t2 - t1)) > 0.05"])),
 gen(14, [K[4]], 3, "Identify", "The displacement-time graph for an object is a curve whose gradient increases steadily with time. What does this show?",
  "The velocity is the gradient of the displacement-time graph. An increasing gradient means an increasing velocity, so the object is speeding up. A constant velocity would give a straight line.",
  ["Velocity is the gradient of a displacement-time graph.", "The gradient is getting steeper: what is happening to the velocity?", "Compare with a straight line, which has a constant gradient."],
  kind="mcq", answer="B", shuffle=True, marks=1,
  options={"A": "The object moves with constant velocity.", "B": "The velocity of the object is increasing.", "C": "The velocity of the object is decreasing.", "D": "The object is at rest."}),
 gen(15, [K[4]], 2, "Describe", "Describe how the instantaneous velocity at time $t$ is found from a displacement-time graph that is a curve.",
  "Draw a tangent to the curve at time $t$. The gradient of the tangent, change in displacement divided by change in time (using a large triangle), is the instantaneous velocity.",
  ["The gradient changes along a curve, so the gradient at one instant needs a special line.", "Draw a line that just touches the curve at the required time.", "Find the gradient of that line using a large triangle."],
  kind="short", marks=2, rubric=[
   {"point": "draw a tangent to the curve at that time", "keywords": [["tangent"]]},
   {"point": "gradient of the tangent = change in displacement / change in time", "keywords": [["gradient", "slope"], ["change in displacement", "displacement divided by", "displacement /", "displacement/", "rise over run", "vertical", "\u0394s", "\u2206s", "ds/dt"]]}]),
 gen(16, [K[4]], 2, "Identify", "The displacement-time graph for an object is a straight line sloping downwards from the top left to the bottom right. What does this show?",
  "A straight line has a constant gradient, so the velocity is constant; a downward slope means the gradient is negative, so the object moves in the negative direction at constant velocity.",
  ["A straight line has the same gradient everywhere.", "Constant gradient on a displacement-time graph means what for velocity?", "Now consider what a negative gradient means for the direction of motion."],
  kind="mcq", answer="C", shuffle=True, marks=1,
  options={"A": "The object is at rest.", "B": "The object is moving with constant velocity in the positive direction.", "C": "The object is moving with constant velocity in the negative direction.", "D": "The object is moving with constant acceleration in the negative direction."}),
 {"id": f"{SUB}-i17", "kcs": [K[4]], "kind": "structured", "difficulty": 4, "command_word": "Determine", "source": {"type": "generated"},
  "stem": "The displacement-time graph of a trolley is a curve. A tangent drawn to the curve at $t=4.0\\ \\mathrm{s}$ passes through the points $(1.0\\ \\mathrm{s},\\ 2.0\\ \\mathrm{m})$ and $(7.0\\ \\mathrm{s},\\ 20.0\\ \\mathrm{m})$. (a) Determine the velocity of the trolley at $t=4.0\\ \\mathrm{s}$. (b) State what the graph would look like if the velocity were constant.",
  "scheme": [{"mark": "M1", "point": "velocity = gradient of the tangent = change in displacement / change in time"},
             {"mark": "A1", "point": "$v=(20.0-2.0)/(7.0-1.0)=3.0\\ \\mathrm{m\\,s^{-1}}$", "check": {"kind": "numeric", "answer": num(tan_v, "m s^-1")}},
             {"mark": "B1", "point": "a straight line (constant gradient) on the displacement-time graph"}],
  "marks": 3, "explanation": "The velocity at an instant is the gradient of the tangent at that instant. Use the two points on the tangent, not a point on the curve. A constant velocity gives a constant gradient, a straight line.",
  "hints": ["Velocity is the gradient of a displacement-time graph.", "The gradient at an instant is the gradient of the tangent, and two points on the tangent are given.", "Use change in displacement divided by change in time between the two points."]},
 # ---- KC 2.1.5
 gen(18, [K[5]], 3, "Determine", f"A car moving in the positive direction slows uniformly from $12\\ {U}$ to $4.0\\ {U}$ in $2.0\\ \\mathrm{{s}}$. Determine its acceleration.",
  "Acceleration is $(v-u)/t=(4.0-12)/2.0=-4.0\\ \\mathrm{m\\,s^{-2}}$: negative because the velocity is decreasing in the positive direction. Using the initial velocity alone ($12/2.0$) or ignoring the sign gives wrong values.",
  ["Acceleration is change in velocity divided by time, with signs.", "Find the change in velocity: final minus initial.", "Then divide by the time taken and think about the sign of the result."],
  kind="mcq", answer="B", shuffle=True, marks=1,
  options={"A": f"$+4.0\\ {U2}$", "B": f"$-4.0\\ {U2}$", "C": f"$-8.0\\ {U2}$", "D": f"$-6.0\\ {U2}$"}, distractors={"A": "m6", "D": "m4"}),
 gen(19, [K[5]], 2, "State", "State how the acceleration is found from a velocity-time graph, and what a negative gradient shows for an object moving in the positive direction.",
  "Acceleration is the gradient of the velocity-time graph (of the tangent, if it is curved). A negative gradient means the velocity is decreasing, so the object is decelerating.",
  ["Think about the units of the gradient of a velocity-time graph.", "Gradient = change in velocity divided by change in time.", "Negative gradient: is the velocity getting larger or smaller for an object moving in the positive direction?"],
  kind="short", marks=2, rubric=[
   {"point": "acceleration = gradient of the velocity-time graph", "keywords": [["gradient", "slope"]]},
   {"point": "negative gradient: decreasing velocity / deceleration", "keywords": [["negative"], ["deceleration", "decelerating", "slowing", "decreasing", "slows", "opposite direction", "negative direction", "decelerat"]]}]),
 # ---- KC 2.1.6
 gen(20, [K[6]], 2, "Derive", "Use the definition of acceleration to derive $v=u+at$ for uniform acceleration from initial velocity $u$ to final velocity $v$ in time $t$.",
  "Acceleration is change in velocity divided by time, $a=(v-u)/t$. Multiplying by $t$ and adding $u$ gives $v=u+at$.",
  ["Start from the definition: acceleration is a rate of change of a particular quantity.", "Write the change in velocity in terms of $u$ and $v$, divided by the time taken.", "Rearrange $a=(v-u)/t$ to make $v$ the subject."],
  kind="short", marks=2, rubric=[
   {"point": "$a=(v-u)/t$: acceleration = change in velocity / time", "keywords": [["change in velocity", "(v-u)", "v-u", "v - u", "v \u2212 u", "(v \u2212 u)", "v\u2212u"], ["time", "/t", "\u00f7 t", "divided by t", "over t"]]},
   {"point": "rearranged to $v=u+at$", "keywords": [["v = u + at", "v=u+at", "v = u+at", "v = at + u", "v=at+u", "at + u", "u + at", "u+at"]]}]),
 {"id": f"{SUB}-i21", "kcs": [K[6]], "kind": "structured", "difficulty": 4, "command_word": "Show", "source": {"type": "generated"},
  "stem": "A body moves in a straight line with uniform acceleration $a$. Its velocity increases from $u$ to $v$ in time $t$ and its displacement is $s$. Show that $s=ut+\\tfrac12at^2$.",
  "scheme": [{"mark": "B1", "point": "for uniform acceleration the average velocity is $\\tfrac12(u+v)$, so $s=\\tfrac12(u+v)t$ (area of the trapezium under the velocity-time graph)"},
             {"mark": "M1", "point": "substitute $v=u+at$ into $s=\\tfrac12(u+v)t$"},
             {"mark": "A1", "point": "$s=\\tfrac12(2u+at)t=ut+\\tfrac12at^2$, with the algebra shown"}],
  "marks": 3, "explanation": "The average velocity is the mean of $u$ and $v$ only because the acceleration is uniform. Substituting $v=u+at$ and simplifying gives the result.",
  "hints": ["The displacement is the area under the velocity-time graph for uniform acceleration.", "The area is a trapezium: write $s$ in terms of $u$, $v$ and $t$.", "Eliminate $v$ using $v=u+at$, then simplify."]},
 gen(22, [K[6]], 3, "Explain", "The equation $s=\\tfrac12(u+v)t$ uses $\\tfrac12(u+v)$ as the average velocity. Why is this valid only for uniform acceleration?",
  "When the acceleration is uniform the velocity increases at a constant rate, so the mean of the initial and final velocities is the average velocity. If the acceleration changes, the average velocity is no longer halfway between them.",
  ["The mean of two values is the average only when the change between them is steady.", "Think about the shape of the velocity-time graph between $u$ and $v$ for uniform acceleration.", "Is the graph a straight line when the acceleration is uniform, and does the trapezium area then equal the mean height multiplied by the width?"],
  kind="mcq", answer="A", shuffle=True, marks=1,
  options={"A": "Uniform acceleration means the velocity changes at a constant rate, so the average velocity is halfway between $u$ and $v$.", "B": "Uniform acceleration means the acceleration equals $9.81\\ \\mathrm{m\\,s^{-2}}$.",
           "C": "Uniform acceleration means the velocity is constant, so $u=v$.", "D": "Uniform acceleration means the object is moving in a straight line, whatever the acceleration."}),
 gen(23, [K[6]], 2, "Identify", "A body has uniform acceleration. Its velocity-time graph is a straight line from $u$ at $t=0$ to $v$ at time $t$. Which expression gives the area under the graph, the displacement?",
  "The area is a trapezium with parallel sides $u$ and $v$ and width $t$: $\\tfrac12(u+v)t$. A triangle only ($\\tfrac12vt$) ignores the starting velocity, and $\\tfrac12(v-u)t$ is just the triangle above the rectangle.",
  ["The graph is a straight line that does not start at the origin.", "Sketch it: which shape lies under the line?", "Area of a trapezium = average of the two parallel sides multiplied by the width."],
  kind="mcq", answer="A", shuffle=True, marks=1,
  options={"A": "$\\tfrac12(u+v)t$", "B": "$\\tfrac12vt$", "C": "$(u+v)t$", "D": "$\\tfrac12(v-u)t$"}),
 gen(24, [K[6]], 5, "Derive", "For uniform acceleration $a$, use $v=u+at$ and $s=\\tfrac12(u+v)t$ to eliminate $t$ and write $v^2$ in terms of $u$, $a$ and $s$.",
  "From $v=u+at$, $t=(v-u)/a$. Then $s=\\tfrac12(u+v)(v-u)/a=(v^2-u^2)/(2a)$, so $v^2=u^2+2as$.",
  ["You need an equation with no $t$: make $t$ the subject of one equation.", "Substitute $t=(v-u)/a$ into $s=\\tfrac12(u+v)t$.", "Look for a difference of two squares in the product $(u+v)(v-u)$."],
  kind="expression", answer={"expr": "u**2 + 2*a*s"}, marks=3),
 gen(25, [K[6], K[7]], 2, "Identify", "A car accelerates uniformly. Its initial velocity, final velocity and displacement are known and its acceleration is required. Which equation should be used, because the time is neither given nor asked for?",
  "The equation with no $t$ is $v^2=u^2+2as$, which links exactly the four quantities in the question. The other equations all contain $t$.",
  ["List the quantities you know and the one you want.", "Only one of the four equations does not contain the time $t$.", "Which of $s$, $u$, $v$, $a$ and $t$ is missing from your list of knowns and unknowns? Rule out every option that contains it."],
  kind="mcq", answer="C", shuffle=True, marks=1,
  options={"A": "$v=u+at$", "B": "$s=ut+\\tfrac12at^2$", "C": "$v^2=u^2+2as$", "D": "$s=\\tfrac12(u+v)t$"}),
 gen(26, [K[6]], 1, "State", "State the conditions under which the equations of motion $v=u+at$ and $s=ut+\\tfrac12at^2$ can be used.",
  "The equations apply only when the acceleration is constant (uniform) and the motion is in a straight line.",
  ["The equations were derived using an average velocity.", "One condition concerns the acceleration; the other concerns the path of the motion.", "The acceleration must be what, and the motion must be along what kind of line?"],
  kind="short", marks=2, rubric=[
   {"point": "uniform / constant acceleration", "keywords": [["uniform", "constant acceleration", "constant", "same acceleration"]]},
   {"point": "motion in a straight line", "keywords": [["straight line", "one dimension", "in a line", "linear", "one direction", "straight path"]]}]),
 # ---- KC 2.1.7
 gen(27, [K[7]], 2, "Calculate", "A stone is dropped from rest from a bridge [[h]] m above a river. Air resistance is negligible. Calculate the time taken for the stone to reach the river.",
  "Take downwards as positive: $u=0$, $a=9.81\\ \\mathrm{m\\,s^{-2}}$, $s=h$, so $s=\\tfrac12at^2$ gives $t=\\sqrt{2h/g}$.",
  ["List $s$, $u$, $a$ and $t$: which are known?", "The stone starts from rest: which suvat equation contains $s$, $u$, $a$ and $t$?", "Use $s=ut+\\tfrac12at^2$ with $u=0$ and rearrange for $t$."],
  kind="numeric", answer={"unit": "s", "sf_ok": [2, 3]}, marks=2,
  template=tpl_num({"h": ch(5, 8, 12, 15, 20, 30, 45)}, "sqrt(2*h/9.81)", [{"expr": "sqrt(h/9.81)"}])),
 gen(28, [K[7]], 3, "Calculate", f"A ball is thrown vertically upwards at [[u]] m s$^{{-1}}$ from ground level. Air resistance is negligible. Calculate the maximum height reached by the ball.",
  "At the highest point $v=0$. Taking up as positive, $v^2=u^2+2as$ with $a=-9.81\\ \\mathrm{m\\,s^{-2}}$ gives $0=u^2-2gs$, so $s=u^2/(2g)$.",
  ["What is the velocity of the ball at its highest point?", "You know $u$, $v$ and $a$ but not the time: choose the equation with no $t$.", "Use $v^2=u^2+2as$ with $v=0$ and a negative $a$ (upwards positive)."],
  kind="numeric", answer={"unit": "m", "sf_ok": [2, 3]}, marks=3,
  template=tpl_num({"u": ch(6, 8, 10, 12, 15, 18, 20)}, "u**2/(2*9.81)", [{"expr": "u**2/9.81"}])),
 gen(29, [K[7]], 3, "Calculate", "A ball is thrown vertically upwards at [[u]] m s$^{-1}$ from ground level and returns to ground level. Air resistance is negligible. Calculate the total time for which the ball is in the air.",
  "Taking up as positive, the displacement is zero on return: $0=ut-\\tfrac12gt^2$, so $t=2u/g$. This is twice the time to the top, $u/g$.",
  ["The ball finishes at the same level from which it started.", "What is the displacement when it returns to its starting level?", "Use $s=ut+\\tfrac12at^2$ with $s=0$ and $a=-9.81$, or find the time to the top and double it."],
  kind="numeric", answer={"unit": "s", "sf_ok": [2, 3]}, marks=3,
  template=tpl_num({"u": ch(6, 8, 10, 12, 15, 18, 20)}, "2*u/9.81", [{"expr": "u/9.81", "misconception": "m5"}])),
 gen(30, [K[7]], 3, "Calculate", "A car travelling at [[u]] m s$^{-1}$ brakes with uniform deceleration and stops in a distance of [[s]] m. Calculate the magnitude of the deceleration.",
  "With $v=0$, $v^2=u^2+2as$ gives $a=-u^2/(2s)$, magnitude $u^2/(2s)$. The time is not needed.",
  ["You know $u$, $v$ (zero at rest) and $s$, and want $a$.", "Choose the equation that has no time in it.", "Use $v^2=u^2+2as$ with $v=0$ and make $a$ the subject."],
  kind="numeric", answer={"unit": "m s^-2", "sf_ok": [2, 3]}, marks=3,
  template=tpl_num({"u": ch(12, 15, 20, 25, 30), "s": ch(30, 40, 50, 60, 80)}, "u**2/(2*s)", [{"expr": "u**2/s"}])),
 {"id": f"{SUB}-i31", "kcs": [K[7]], "kind": "structured", "difficulty": 5, "command_word": "Calculate", "source": {"type": "generated"},
  "stem": f"A ball is thrown vertically upwards at $14\\ {U}$ from the top of a cliff. The ball lands at the foot of the cliff, $25\\ \\mathrm{{m}}$ below the point of projection. Air resistance is negligible and $g=9.81\\ {U2}$. (a) Calculate the time taken for the ball to reach the foot of the cliff. (b) Calculate the speed of the ball as it lands.",
  "scheme": [{"mark": "B1", "point": "upwards positive: $u=+14\\ \\mathrm{m\\,s^{-1}}$, $a=-9.81\\ \\mathrm{m\\,s^{-2}}$, $s=-25\\ \\mathrm{m}$"},
             {"mark": "M1", "point": "$s=ut+\\tfrac12at^2$: $-25=14t-4.905t^2$, solved as a quadratic (the positive root is chosen)"},
             {"mark": "A1", "point": "$t=4.1\\ \\mathrm{s}$ ($4.10\\ \\mathrm{s}$)", "check": {"kind": "numeric", "answer": num(cliff_t, "s")}},
             {"mark": "M1", "point": "$v^2=u^2+2as=14^2+2\\times9.81\\times25$ (or $v=u+at$)"},
             {"mark": "A1", "point": "speed $=26\\ \\mathrm{m\\,s^{-1}}$ ($26.2$)", "check": {"kind": "numeric", "answer": num(cliff_v, "m s^-1")}}],
  "marks": 5, "explanation": "With upwards positive, $s=-25\\ \\mathrm{m}$ because the ball ends below its start. The equation $4.905t^2-14t-25=0$ has one positive root, $4.10\\ \\mathrm{s}$; the negative root is unphysical. The landing speed follows from $v^2=u^2+2as$, taking the positive square root.",
  "hints": ["Choose upwards as positive and write down the sign of $u$, $a$ and $s$.", "The ball ends below where it started, so the displacement is negative and you must solve a quadratic in $t$.", "Use $s=ut+\\tfrac12at^2$ and reject the negative root, then find the speed with an equation that avoids $t$."]},
 gen(32, [K[7]], 2, "Identify", "A ball is thrown vertically upwards. Air resistance is negligible. Which row gives the velocity and acceleration of the ball at its highest point?",
  "At the highest point the velocity is momentarily zero, but the ball is still accelerating downwards at $g$ because gravity still acts, and the acceleration is constant for the whole flight.",
  ["The acceleration comes from the force of gravity: does this force stop acting at the top?", "Velocity is the rate of change of position; acceleration is the rate of change of velocity.", "The velocity changes from upwards to downwards, so what is the direction of the acceleration?"],
  kind="mcq", answer="B", shuffle=True, marks=1,
  options={"A": "velocity zero, acceleration zero", "B": f"velocity zero, acceleration $9.81\\ {U2}$ downwards", "C": f"velocity zero, acceleration $9.81\\ {U2}$ upwards", "D": f"velocity $9.81\\ {U}$ downwards, acceleration zero"},
  distractors={"A": "m2", "C": "m6"}),
 # ---- KC 2.1.8
 gen(33, [K[8]], 3, "Describe", "Describe an experiment to determine the acceleration of free fall using a falling object.",
  "Release a steel ball from rest with an electromagnet (switching it off starts the timer), stop the timer when the ball opens a trapdoor or passes a light gate, measure the height with a metre rule, repeat for several heights and plot $h$ against $t^2$. The gradient is $g/2$, so $g$ is twice the gradient.",
  ["Think about what you would measure and how: a distance and a time.", "Vary the height and repeat, so that you can plot a graph.", "Which two quantities are plotted so that the gradient is proportional to $g$, and how is $g$ found from it?"],
  kind="short", marks=5, rubric=[
   {"point": "release a small dense object (e.g. steel ball) from rest, e.g. with an electromagnet or a clamp", "keywords": [["electromagnet", "released", "release", "dropped", "drop", "from rest"]]},
   {"point": "measure the height fallen with a metre rule / tape / ruler", "keywords": [["metre rule", "meter rule", "ruler", "tape measure", "tape", "metre stick"], ["height", "distance", "fall"]]},
   {"point": "measure the time of fall with an electronic timer started when the electromagnet is switched off and stopped by a trapdoor or light gate", "keywords": [["timer", "stopwatch", "light gate", "light-gate", "data logger", "datalogger", "trapdoor", "stop clock"]]},
   {"point": "repeat for different heights (and repeat times to find an average)", "keywords": [["different heights", "range of heights", "vary the height", "varying height", "several heights", "change the height", "various heights", "different distances"]]},
   {"point": "plot $h$ against $t^2$; the gradient is $g/2$ so $g=2\\times$gradient", "keywords": [["t2", "t\u00b2", "t^2", "t squared", "time squared", "t*t"], ["gradient", "slope"]]}]),
 gen(34, [K[8]], 3, "Determine", "In a free-fall experiment a steel ball is released from rest at different heights $h$ and the time $t$ of fall is measured. The graph of $h$ against $t^2$ is a straight line through the origin with gradient [[G:.2f]] m s$^{-2}$. Determine the acceleration of free fall.",
  "From $h=\\tfrac12gt^2$ the graph of $h$ against $t^2$ has gradient $g/2$, so $g=2\\times$ gradient.",
  ["Compare $h=\\tfrac12gt^2$ with the straight line $y=mx$.", "Which quantity is on the $y$-axis, which on the $x$-axis, and what does the gradient then equal?", "The gradient equals $\\tfrac12 g$: rearrange for $g$."],
  kind="numeric", answer={"unit": "m s^-2", "sf_ok": [2, 3]}, marks=3,
  template=tpl_num({"G": ch(4.6, 4.7, 4.8, 4.9, 5.0, 5.1)}, "2*G", [{"expr": "G", "misconception": "m4"}])),
 gen(35, [K[8]], 2, "Identify", "A steel ball is released from rest and falls a height $h$ in time $t$. Which graph gives a straight line whose gradient can be used to find the acceleration of free fall?",
  "From $h=\\tfrac12gt^2$, $h$ is proportional to $t^2$, so a graph of $h$ against $t^2$ is straight with gradient $g/2$. The other graphs are curves, since $h$ is not proportional to $t$.",
  ["Start from $h=\\tfrac12gt^2$: what type of relationship links $h$ and $t$?", "For a straight line you need one plotted quantity proportional to the other.", "Look for the pair in which one quantity is directly proportional to the other."],
  kind="mcq", answer="B", shuffle=True, marks=1,
  options={"A": "$h$ against $t$", "B": "$h$ against $t^2$", "C": "$h^2$ against $t$", "D": "$t$ against $h$"}),
 gen(36, [K[8]], 3, "Suggest", "Suggest two ways to reduce the uncertainty in the value of the acceleration of free fall found in a free-fall experiment.",
  "Repeating the timing and averaging reduces random error; using electronic timing, or a larger fall height so that the time is longer, reduces the percentage uncertainty in the time.",
  ["Consider the main source of uncertainty: the measurement of a short time.", "One improvement concerns how many readings you take; another concerns how the time is measured or how long it is.", "Repeat and average, and use a method that removes human reaction time or makes the time larger."],
  kind="short", marks=2, rubric=[
   {"point": "repeat readings and average", "keywords": [["repeat", "average", "mean", "several readings", "many readings"]]},
   {"point": "electronic timing (light gates / data logger) or a larger fall height", "keywords": [["light gate", "light-gate", "electronic", "data logger", "datalogger", "electromagnet", "automatic", "greater height", "larger height", "increase the height", "greater distance", "longer time", "photogate"]]}]),
 gen(37, [K[8]], 3, "Calculate", "In a free-fall experiment a steel ball released from rest falls a distance of [[h]] m in a time of [[t:.2f]] s. Calculate the acceleration of free fall.",
  "For $u=0$, $s=\\tfrac12gt^2$, so $g=2s/t^2$.",
  ["The ball starts from rest.", "Choose the suvat equation with $s$, $u$, $a$ and $t$.", "Use $s=\\tfrac12at^2$ and make the acceleration the subject."],
  kind="numeric", answer={"unit": "m s^-2", "sf_ok": [2, 3]}, marks=3,
  template=tpl_num({"h": ch(1.0, 1.5, 2.0, 2.5), "gt": ch(9.6, 9.8, 10.0)}, "2*h/t**2", [{"expr": "h/t**2"}], derived={"t": "round(sqrt(2*h/gt), 2)"})),
 # ---- KC 2.1.9
 gen(38, [K[9]], 3, "Calculate", "A ball is kicked horizontally at [[u]] m s$^{-1}$ from the top of a cliff [[H]] m high. Air resistance is negligible. Calculate the horizontal distance from the foot of the cliff to where the ball lands.",
  "The vertical motion starts from rest: $H=\\tfrac12gt^2$, so $t=\\sqrt{2H/g}$. The horizontal velocity is constant, so the distance is $ut$.",
  ["Treat the horizontal and vertical motion separately.", "The time of fall depends only on the vertical motion: the ball has no initial vertical velocity.", "Find the time to fall $H$ from rest, then multiply by the constant horizontal velocity."],
  kind="numeric", answer={"unit": "m", "sf_ok": [2, 3]}, marks=3,
  template=tpl_num({"u": ch(6, 8, 10, 12), "H": ch(20, 30, 45, 80)}, "u*sqrt(2*H/9.81)", [{"expr": "u*sqrt(H/9.81)"}])),
 gen(39, [K[9]], 4, "Calculate", "A ball is kicked from level ground at [[v]] m s$^{-1}$ at [[t]]$^\\circ$ above the horizontal. Air resistance is negligible. Calculate the maximum height reached by the ball.",
  "Only the vertical component matters: $u_y=v\\sin\\theta$. At the top $v_y=0$, so $H=u_y^2/(2g)=(v\\sin\\theta)^2/(2g)$. Using $v$ instead of $v\\sin\\theta$ overestimates the height.",
  ["Resolve the launch velocity into horizontal and vertical components.", "The height depends only on the vertical component: what is the vertical velocity at the top?", "Use $v_y^2=u_y^2-2gs$ with $v_y=0$ and $u_y=v\\sin\\theta$."],
  kind="numeric", answer={"unit": "m", "sf_ok": [2, 3]}, marks=3,
  template=tpl_num({"v": ch(12, 15, 18, 20, 25), "t": ch(30, 35, 40, 45, 50, 55, 60)}, "(v*sin(radians(t)))**2/(2*9.81)", [{"expr": "v**2/(2*9.81)", "misconception": "m8"}])),
 gen(40, [K[9]], 3, "Identify", "Ball A is dropped from rest from the top of a tower. At the same instant ball B is fired horizontally from the same point with a large speed. Air resistance is negligible. Which statement is correct?",
  "The vertical motion of each ball is the same: zero initial vertical velocity and acceleration $g$. The horizontal velocity of B does not affect its vertical motion, so both balls land together.",
  ["Consider the vertical motion of each ball on its own.", "What is the initial vertical velocity of each ball and the acceleration in the vertical direction?", "Does the horizontal velocity of B change its vertical motion?"],
  kind="mcq", answer="C", shuffle=True, marks=1,
  options={"A": "A lands first because B has further to travel.", "B": "B lands first because it has a horizontal velocity as well.", "C": "They land at the same time because their vertical motions are identical.", "D": "Which lands first depends on the horizontal speed of B."},
  distractors={"A": "m8", "B": "m8", "D": "m8"}),
 gen(41, [K[9]], 4, "Explain", "Explain why the path of a projectile launched at an angle in a uniform gravitational field is a parabola. Air resistance is negligible.",
  "There is no horizontal force, so the horizontal velocity is constant and the horizontal distance is proportional to $t$. The vertical acceleration is constant ($g$), so the vertical displacement contains a $t^2$ term. Since the two motions are independent, eliminating $t$ gives a vertical displacement that is quadratic in horizontal distance: a parabola.",
  ["Split the motion into a horizontal and a vertical part and describe each.", "One part has constant velocity; the other has constant acceleration. How does each displacement depend on $t$?", "Combine: one displacement is proportional to $t$, the other has a term in $t^2$."],
  kind="short", marks=3, rubric=[
   {"point": "horizontal velocity is constant (no horizontal force or acceleration)", "keywords": [["horizontal"], ["constant velocity", "constant speed", "no acceleration", "no force", "uniform velocity", "does not change", "remains constant", "stays constant", "is constant", "unchanged"]]},
   {"point": "vertical acceleration is constant (downwards, $g$)", "keywords": [["vertical"], ["constant acceleration", "uniform acceleration", "acceleration of free fall", "accelerates downwards", "constant downward", "acceleration is constant", "constant downwards"]]},
   {"point": "the two motions are independent (perpendicular), so the vertical displacement is proportional to $t^2$ while horizontal is proportional to $t$", "keywords": [["independent", "separately", "perpendicular", "right angles", "at right angle"]]}]),
 {"id": f"{SUB}-i42", "kcs": [K[9], K[7]], "kind": "structured", "difficulty": 5, "command_word": "Calculate", "source": {"type": "generated"},
  "stem": f"A ball is kicked from level ground with speed $20\\ {U}$ at $40^\\circ$ above the horizontal. Air resistance is negligible and $g=9.81\\ {U2}$. (a) Calculate the horizontal and vertical components of the initial velocity. (b) Calculate the time for which the ball is in the air. (c) Calculate the horizontal distance travelled before it lands.",
  "scheme": [{"mark": "B1", "point": "$u_x=20\\cos40^\\circ=15.3\\ \\mathrm{m\\,s^{-1}}$ and $u_y=20\\sin40^\\circ=12.9\\ \\mathrm{m\\,s^{-1}}$", "check": {"kind": "numeric", "answer": num(ky, "m s^-1")}},
             {"mark": "M1", "point": "vertical: displacement zero on landing, so $0=u_yt-\\tfrac12gt^2$ (or $t=2u_y/g$)"},
             {"mark": "A1", "point": "$t=2.6\\ \\mathrm{s}$", "check": {"kind": "numeric", "answer": num(kT, "s")}},
             {"mark": "M1", "point": "horizontal: constant velocity, so distance $=u_xt$"},
             {"mark": "A1", "point": "distance $=15.3\\times2.62=40\\ \\mathrm{m}$", "check": {"kind": "numeric", "answer": num(kR, "m")}}],
  "marks": 5, "explanation": "Resolve the launch velocity, then treat the vertical motion (uniform acceleration, zero net displacement) and the horizontal motion (constant velocity) separately. They are joined only by the common time of flight.",
  "hints": ["Resolve the launch velocity into two perpendicular components first.", "The time of flight is decided by the vertical motion alone: what is the vertical displacement at landing?", "Once you have the time, the horizontal distance uses the constant horizontal velocity."]},
]

# ---------------- worked examples ----------------
def wk(id_, kc, problem, steps, fid, fproblem, fanswer, blank_from=1):
    return {"id": id_, "kc": kc, "problem": problem, "steps": steps, "faded": {"id": fid, "problem": fproblem, "answer": fanswer, "blank_from": blank_from}}
st = lambda do, why, chk=None: ({"do": do, "why": why, "check": {"kind": "numeric", "answer": chk}} if chk else {"do": do, "why": why})
worked = [
 wk("we1", K[1], f"A cyclist rides $300\\ \\mathrm{{m}}$ due east then $400\\ \\mathrm{{m}}$ due north in $100\\ \\mathrm{{s}}$. Determine (a) the average speed and (b) the magnitude of the average velocity.",
  [st("Average speed uses the total distance: $\\dfrac{300+400}{100}=7.0\\ \\mathrm{m\\,s^{-1}}$.", "Speed is distance travelled divided by time and has no direction, so the route length is added.", num(we1_dist / 100, "m s^-1")),
   st("Displacement is the straight line from start to finish: $\\sqrt{300^2+400^2}=500\\ \\mathrm{m}$, at $53^\\circ$ north of east.", "The two legs are perpendicular, so Pythagoras applies; displacement is a vector and needs a direction.", num(we1_disp, "m")),
   st("Average velocity $=\\dfrac{500}{100}=5.0\\ \\mathrm{m\\,s^{-1}}$ at $53^\\circ$ north of east.", "Average velocity is displacement over time, so it is smaller than the average speed ($7.0$) unless the path is straight.", num(we1_disp / 100, "m s^-1"))],
  "we1f", f"A runner goes $240\\ \\mathrm{{m}}$ due east then $70\\ \\mathrm{{m}}$ due north in $25\\ \\mathrm{{s}}$. Determine the magnitude of the average velocity.", num(we1f, "m s^-1")),
 wk("we2", K[2], f"A lift starts from rest, accelerates uniformly at $1.5\\ {U2}$ for $4.0\\ \\mathrm{{s}}$, moves at constant velocity for $6.0\\ \\mathrm{{s}}$, then slows uniformly to rest in $3.0\\ \\mathrm{{s}}$. Sketch its velocity-time graph and find its greatest speed and the size of the final acceleration.",
  [st("First section: a straight line from the origin, gradient $1.5\\ \\mathrm{m\\,s^{-2}}$, ending at $v=at=1.5\\times4.0=6.0\\ \\mathrm{m\\,s^{-1}}$ at $t=4.0\\ \\mathrm{s}$.", "Uniform acceleration is a straight line whose gradient is the acceleration; the end value comes from $v=u+at$.", num(we2_vmax, "m s^-1")),
   st("Second section: a horizontal line at $6.0\\ \\mathrm{m\\,s^{-1}}$ from $t=4.0\\ \\mathrm{s}$ to $10\\ \\mathrm{s}$.", "Constant velocity means zero gradient, so no acceleration."),
   st("Third section: a straight line down to zero at $t=13\\ \\mathrm{s}$; gradient $=-6.0/3.0$, magnitude $2.0\\ \\mathrm{m\\,s^{-2}}$.", "Acceleration is the gradient, change in velocity divided by change in time; the negative sign shows deceleration.", num(we2_dec, "m s^-2"))],
  "we2f", f"A lift starts from rest, accelerates uniformly at $2.5\\ {U2}$ for $4.0\\ \\mathrm{{s}}$, then moves at constant velocity. Determine its constant speed.", num(we2f, "m s^-1")),
 wk("we3", K[3], f"The velocity of a trolley changes uniformly from $+6.0\\ {U}$ at $t=0$ to $-4.0\\ {U}$ at $t=5.0\\ \\mathrm{{s}}$. Determine its displacement at $t=5.0\\ \\mathrm{{s}}$ and the total distance travelled.",
  [st("Find where the graph crosses the axis: the velocity falls by $10\\ \\mathrm{m\\,s^{-1}}$ in $5.0\\ \\mathrm{s}$, so it reaches zero at $t=3.0\\ \\mathrm{s}$.", "The graph is a straight line from $+6.0$ to $-4.0$; the crossing point splits the area into a triangle above the axis and one below."),
   st("Area above: $\\tfrac12\\times3.0\\times6.0=9.0\\ \\mathrm{m}$. Area below: $\\tfrac12\\times2.0\\times4.0=4.0\\ \\mathrm{m}$ (opposite direction).", "Each triangle is $\\tfrac12\\times$ base $\\times$ height, with the base measured along the time axis."),
   st("Displacement $=9.0-4.0=+5.0\\ \\mathrm{m}$. Distance travelled $=9.0+4.0=13\\ \\mathrm{m}$.", "The area below the axis is displacement in the opposite direction, so it is subtracted for displacement but added for distance.", num(we3_disp, "m"))],
  "we3f", f"The velocity of a trolley changes uniformly from $+8.0\\ {U}$ at $t=0$ to $-2.0\\ {U}$ at $t=5.0\\ \\mathrm{{s}}$. Determine its displacement at $t=5.0\\ \\mathrm{{s}}$.", num(we3f, "m")),
 wk("we4", K[4], "The displacement-time graph of a trolley is a curve. A tangent drawn at $t=3.0\\ \\mathrm{s}$ passes through the points $(2.0\\ \\mathrm{s},\\ 3.0\\ \\mathrm{m})$ and $(4.0\\ \\mathrm{s},\\ 15.0\\ \\mathrm{m})$. Determine the velocity of the trolley at $t=3.0\\ \\mathrm{s}$.",
  [st("Velocity is the gradient of the displacement-time graph, so use the tangent at $t=3.0\\ \\mathrm{s}$, not the curve.", "On a curve the gradient changes; the tangent gives the gradient at that instant."),
   st("Take two points on the tangent, far apart: $\\Delta s=15.0-3.0=12.0\\ \\mathrm{m}$ and $\\Delta t=4.0-2.0=2.0\\ \\mathrm{s}$.", "A large triangle reduces reading errors; use the values on the axes.", num(12.0, "m")),
   st("$v=\\dfrac{\\Delta s}{\\Delta t}=\\dfrac{12.0}{2.0}=6.0\\ \\mathrm{m\\,s^{-1}}$.", "Gradient is change in $y$ over change in $x$, and the unit is $\\mathrm{m\\,s^{-1}}$.", num(we4, "m s^-1"))],
  "we4f", "A tangent to a displacement-time curve at $t=2.0\\ \\mathrm{s}$ passes through $(1.0\\ \\mathrm{s},\\ 0\\ \\mathrm{m})$ and $(3.0\\ \\mathrm{s},\\ 8.0\\ \\mathrm{m})$. Determine the velocity at $t=2.0\\ \\mathrm{s}$.", num(we4f, "m s^-1")),
 wk("we5", K[5], f"A car's velocity-time graph is a straight line from $24\\ {U}$ at $t=3.0\\ \\mathrm{{s}}$ to $6.0\\ {U}$ at $t=9.0\\ \\mathrm{{s}}$. Determine its acceleration.",
  [st("Acceleration is the gradient: $a=\\dfrac{\\Delta v}{\\Delta t}$.", "The quantity is defined as rate of change of velocity, which is the gradient of a velocity-time graph."),
   st("$\\Delta v=6.0-24=-18\\ \\mathrm{m\\,s^{-1}}$ and $\\Delta t=9.0-3.0=6.0\\ \\mathrm{s}$.", "Use final minus initial for each and keep the sign; do not use $24/3.0$, because the line does not start at the origin."),
   st("$a=\\dfrac{-18}{6.0}=-3.0\\ \\mathrm{m\\,s^{-2}}$: the car decelerates at $3.0\\ \\mathrm{m\\,s^{-2}}$.", "A negative gradient with positive velocity means the velocity is decreasing.", num(we5, "m s^-2"))],
  "we5f", f"A car's velocity-time graph is a straight line from $20\\ {U}$ at $t=2.0\\ \\mathrm{{s}}$ to $5.0\\ {U}$ at $t=8.0\\ \\mathrm{{s}}$. Determine its acceleration.", num(we5f, "m s^-2")),
 wk("we6", K[6], "Derive $s=ut+\\tfrac12at^2$ for uniform acceleration and check it with $u=2.0\\ \\mathrm{m\\,s^{-1}}$, $a=3.0\\ \\mathrm{m\\,s^{-2}}$, $t=4.0\\ \\mathrm{s}$.",
  [st("Definition of acceleration: $a=\\dfrac{v-u}{t}$, so $v=u+at$.", "This is the starting point; every suvat equation is built from definitions."),
   st("For uniform acceleration the average velocity is $\\tfrac12(u+v)$, so $s=\\tfrac12(u+v)t$ (the area of a trapezium).", "The mean of the two velocities is the average only when the velocity changes steadily."),
   st("Substitute $v=u+at$: $s=\\tfrac12(2u+at)t=ut+\\tfrac12at^2$.", "Eliminating $v$ leaves an equation in the given quantities $u$, $a$, $t$."),
   st("Check: $v=2.0+3.0\\times4.0=14\\ \\mathrm{m\\,s^{-1}}$; $s=2.0\\times4.0+\\tfrac12\\times3.0\\times4.0^2=32\\ \\mathrm{m}$, and $\\tfrac12(2.0+14)\\times4.0=32\\ \\mathrm{m}$ agrees.", "Two routes giving the same value confirm the algebra.", num(32.0, "m"))],
  "we6f", f"A body has $u=3.0\\ {U}$ and uniform acceleration $2.0\\ {U2}$ for $5.0\\ \\mathrm{{s}}$. Determine its displacement.", num(we6f, "m")),
 wk("we7", K[7], f"A stone is thrown vertically upwards at $12\\ {U}$ from ground level. Determine (a) the maximum height and (b) the time taken to return to the ground. Take $g=9.81\\ {U2}$.",
  [st("Upwards positive: $u=+12\\ \\mathrm{m\\,s^{-1}}$, $a=-9.81\\ \\mathrm{m\\,s^{-2}}$. At the top $v=0$.", "Fixing the direction and signs first avoids mixing $+g$ and $-g$ (the most frequent error).") ,
   st("No time is wanted, so use $v^2=u^2+2as$: $0=12^2-2\\times9.81\\,s$, so $s=\\dfrac{144}{19.62}=7.3\\ \\mathrm{m}$.", "Choose the equation that contains the three known quantities and the unknown, and no other unknown.", num(we7_h, "m")),
   st("Return to the ground means $v=-12\\ \\mathrm{m\\,s^{-1}}$: $t=\\dfrac{v-u}{a}=\\dfrac{-12-12}{-9.81}=2.4\\ \\mathrm{s}$.", "Rising and falling take equal times, so the total time is twice the time to the top ($1.22\\ \\mathrm{s}$).", num(we7_t, "s"))],
  "we7f", f"A stone is thrown vertically upwards at $15\\ {U}$ from ground level. Determine the maximum height. Take $g=9.81\\ {U2}$.", num(we7f, "m")),
 wk("we8", K[8], f"In a free-fall experiment a graph of height $h$ against $t^2$ is a straight line through the origin passing through the point $(0.200\\ \\mathrm{{s^2}},\\ 0.98\\ \\mathrm{{m}})$. Determine the acceleration of free fall.",
  [st("For a ball released from rest $h=\\tfrac12gt^2$, which has the form $y=mx$ with $y=h$, $x=t^2$ and gradient $m=\\tfrac12g$.", "Comparing with $y=mx$ shows what the gradient means, and why a graph of $h$ against $t^2$ is a straight line."),
   st("Gradient $=\\dfrac{0.98}{0.200}=4.90\\ \\mathrm{m\\,s^{-2}}$.", "The line goes through the origin, so one point is enough.", num(we8_grad, "m s^-2")),
   st("$g=2\\times$ gradient $=2\\times4.90=9.8\\ \\mathrm{m\\,s^{-2}}$.", "The gradient is $g/2$, not $g$: do not forget the factor of 2.", num(we8_g, "m s^-2"))],
  "we8f", "A graph of $h$ against $t^2$ is a straight line through the origin passing through $(0.250\\ \\mathrm{s^2},\\ 1.20\\ \\mathrm{m})$. Determine the acceleration of free fall.", num(we8f_g, "m s^-2")),
]

# ---------------- flashcards ----------------
fc = lambda n, kc, f, b: {"id": f"fc{n}", "kc": kc, "front": f, "back": b}
flashcards = [
 fc(1, K[1], "Define distance.", "Distance is the total length of the path travelled by an object; it is a scalar."),
 fc(2, K[1], "Define displacement.", "Displacement is the straight-line distance from the start point to the end point in a stated direction; it is a vector."),
 fc(3, K[1], "Define speed and velocity.", "Speed is the rate of change of distance. Velocity is the rate of change of displacement."),
 fc(4, K[1], "Define acceleration.", "Acceleration is the rate of change of velocity."),
 fc(5, K[2], "What do the gradient and area of a velocity-time graph represent?", "Gradient = acceleration; area under the graph = displacement (area below the axis is negative)."),
 fc(6, K[4], "What does the gradient of a displacement-time graph represent?", "The velocity (for a curve, the gradient of the tangent gives the instantaneous velocity)."),
 fc(7, K[5], "What does the gradient of a velocity-time graph represent?", "The acceleration (for a curve, the gradient of the tangent at the instant)."),
 fc(8, K[6], "List the four equations of motion for uniform acceleration.", "$v=u+at$, $s=ut+\\tfrac12at^2$, $v^2=u^2+2as$, $s=\\tfrac12(u+v)t$."),
 fc(9, K[6], "State the conditions for the equations of motion.", "The acceleration is uniform (constant) and the motion is in a straight line."),
 fc(10, K[7], "What is the acceleration of free fall, and when does it apply?", f"$g=9.81\\ {U2}$ downwards near the Earth's surface; every object falls with it when air resistance is negligible."),
 fc(11, K[8], "How is $g$ found from a graph in a free-fall experiment?", "Plot $h$ against $t^2$ for a ball released from rest; the gradient is $g/2$, so $g=2\\times$ gradient."),
 fc(12, K[9], "State the principle for projectile motion.", "Horizontal and vertical motions are independent: constant velocity horizontally, uniform acceleration $g$ vertically (no air resistance)."),
]

# ---------------- diagrams ----------------
tt = [i * 0.1 for i in range(0, 46)]
vx0 = 20 * cos(40); vy0 = 20 * sin(40)
traj = [[round(vx0 * t, 3), round(vy0 * t - 0.5 * G * t * t, 3)] for t in [i * kT / 199 for i in range(0, 200)]]
xt, yt = vx0 * vy0 / G, vy0**2 / (2 * G)
A = lambda xy, tail: {"text": "", "xy": xy, "xytext": tail}
T = lambda text, xy: {"text": text, "xy": xy}
diagrams = [
 {"file": "Assets/9702/9702-2.1-vt-graph.svg", "type": "graph_sketch", "params": {
   "lines": [{"points": [[0, 0], [5, 10], [15, 10], [19, 0]], "color": "#1f6feb"}], "shade": {"line": 0}, "ticks": True, "ylim": [0, 14], "xticklabels": [[0, "0"], [5, "5"], [10, "10"], [15, "15"], [20, "20"]],
   "xlabel": "$t$ / s", "ylabel": r"$v$ / $\mathrm{m\,s^{-1}}$",
   "annotations": [{"text": "gradient $= a$", "xy": [2.5, 5.0], "xytext": [0.2, 12.2]}, T("area $= s$", [8.0, 4.2]), T("$a=0$", [8.5, 10.5]), {"text": "gradient $<0$", "xy": [17.0, 5.0], "xytext": [14.4, 12.2]}]}},
 {"file": "Assets/9702/9702-2.1-st-graph.svg", "type": "graph_sketch", "params": {
   "lines": [{"points": [[round(t, 2), round(t * t, 3)] for t in tt], "color": "#1f2328"}, {"points": [[1.5, 0], [4.5, 18]], "color": "#d9480f", "style": "dashed"}, {"points": [[3, 9]], "color": "#1f6feb", "marker": "o"}],
   "ticks": True, "ylim": [0, 21], "xlabel": "$t$ / s", "ylabel": "$s$ / m",
   "annotations": [T("curve: gradient changes", [0.2, 15.5]), T("tangent at $t=3.0$ s: gradient $= v$", [0.2, 18.5])]}},
 {"file": "Assets/9702/9702-2.1-projectile.svg", "type": "graph_sketch", "params": {
   "lines": [{"points": traj, "color": "#1f6feb"}], "ticks": False, "ylim": [-1.5, 11], "xlim": [-8, 43], "xlabel": "horizontal distance", "ylabel": "height",
   "annotations": [A([xt + 6.0, yt + 0.9], [xt + 1.0, yt + 0.9]), T(r"$v_x$ constant", [xt + 1.0, yt + 1.3]),
                   A([xt, yt - 4.0], [xt, yt - 0.9]), T(r"$a=g$ downwards", [xt - 5.5, yt - 5.2]),
                   A([0.45 * vx0, 0.45 * vy0], [0, 0]), T(r"$v$", [0.45 * vx0 - 1.6, 0.45 * vy0 + 0.2]),
                   A([0.45 * vx0, 0], [0, 0]), T(r"$v\cos\theta$", [0.2, -1.2]),
                   A([0, 0.45 * vy0], [0, 0]), T(r"$v\sin\theta$", [-7.6, 0.45 * vy0 - 1.0]), T(r"$\theta$", [2.6, 0.35])]}},
]

outline = ("Distance and speed are scalars; displacement, velocity and acceleration are vectors, with velocity the rate of change of displacement and acceleration the rate of change of velocity. "
           "On a displacement-time graph the gradient is velocity; on a velocity-time graph the gradient is acceleration and the area is displacement (below the axis is negative). "
           "For uniform acceleration in a straight line, $v=u+at$, $s=\\tfrac12(u+v)t$, $s=ut+\\tfrac12at^2$ and $v^2=u^2+2as$ follow from the definitions. "
           "Choose a positive direction, list $s,u,v,a,t$, and pick the equation missing the unwanted variable. For free fall $a=9.81\\ \\mathrm{m\\,s^{-2}}$ downwards; $g$ can be found from the gradient of $h$ against $t^2$. "
           "A projectile's horizontal and vertical motions are independent: constant horizontal velocity, uniform vertical acceleration.")
assert len(outline.split()) <= 150, len(outline.split())

pack = {"subtopic": SUB, "spec": "9702", "version": 1, "note": NOTE, "outline": outline, "misconceptions": misconceptions,
        "worked": worked, "items": past_items + generated, "flashcards": flashcards, "diagrams": diagrams}
out = ROOT / "build/out/packs/9702" / f"{SUB}.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(pack, ensure_ascii=False, indent=1))
print("pack", out, len(pack["items"]), "items")

import random, sys
sys.path.insert(0, str(ROOT / "plugin/stem-tutor/skills/tutor/scripts"))
from tutorlib import packs
for it in generated:
    if it.get("template"):
        for s in range(2000):
            inst = packs.instantiate(it, random.Random(s)); a = inst["answer"]["value"]
            assert a > 0, (it["id"], s)
            for d in inst["distractors"]:
                assert abs(d["value"] - a) > 0.03 * a, (it["id"], s, a, d)
print("templates ok")
