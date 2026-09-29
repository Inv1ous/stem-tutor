"""Generator for pack 9702-1.1 (Physical quantities). Content as data; every number computed here."""
import json, math
from pathlib import Path

ST = "9702-1.1"; K1 = "9702-1.1.1"; K2 = "9702-1.1.2"
U = lambda s: s  # unit text helper
MS = r"$\mathrm{m\,s^{-1}}$"; KMH = r"$\mathrm{km\,h^{-1}}$"

# ---------- verified numbers ----------
football_cm3 = 4/3*math.pi*11**3                      # r = 11 cm
assert 5000 < football_cm3 < 6500
assert all(math.isclose(a,b,rel_tol=1e-9) for a,b in [(50e-6/1e-30,5e25),(50e-2/1e-30,5e29),(50/1e-30,5e31)])
assert 0.1*1000 == 100 and abs(9000/100 - 90) < 1e-9
assert 0.5*80*10**2 == 4000
assert abs(80/1000 - 0.08) < 1e-12
ke_cyc = 0.5*90*(18/3.6)**2       # 1125 J
assert abs(ke_cyc - 1125) < 1e-6
ke_bike19 = 0.5*80*25; ke_car19 = 0.5*1000*12**2; p_cyc = 80*5; p_car = 1000*12
assert (ke_bike19, ke_car19, p_cyc, p_car) == (1000, 72000, 400, 12000)   # so 2e5 kg m/s is not reasonable
air = 8*6*3*1.2; assert abs(air - 172.8) < 1e-9
V3 = (0.030)**3; N3 = V3/1e-30; assert abs(V3 - 2.7e-5) < 1e-12 and math.isclose(N3,2.7e25,rel_tol=1e-9)
V5 = (0.050)**3; N5 = V5/1e-30; assert math.isclose(N5,1.25e26,rel_tol=1e-9)
assert abs(600/(400e-4) - 1.5e4) < 1e-6
walk = 1.5

mis = [
 {"id": "m1", "kc": K1, "statement": "A unit is treated as a physical quantity, so the kelvin, the metre, the minute, the ampere or the pascal is picked as a 'physical quantity'.",
  "refutation": "A physical quantity is what is measured (temperature, length, time, current, pressure) and it consists of a numerical magnitude and a unit. The kelvin, metre, minute, ampere and pascal are only the units in which those quantities are expressed.",
  "contrast": "Temperature is the physical quantity; kelvin is its unit. A record such as $T = 300\\ \\mathrm{K}$ contains both.", "source": "ER 9702 w22 P12 Q1"},
 {"id": "m2", "kc": K1, "statement": "A record of a physical quantity must include an SI unit, or a unit written in base units.",
  "refutation": "Every physical quantity needs a unit, but it need not be an SI unit or a base unit. A length recorded as 40 cm, 0.4 m or 400 mm is complete in each case; derived units such as the newton are equally acceptable.",
  "contrast": "$F = 12\\ \\mathrm{N}$ is a complete record even though the newton is not a base unit; $L = 0.75$ is incomplete whatever the number.", "source": "ER 9702 s23 P13 Q1"},
 {"id": "m3", "kc": K1, "statement": "All physical quantities must have a direction (as well as a magnitude and a unit).",
  "refutation": "Direction is needed only for vector quantities such as force and velocity. Scalar quantities such as mass, time, temperature and energy have a magnitude and a unit but no direction.",
  "contrast": "The mass $m = 2.0\\ \\mathrm{kg}$ has no direction; the force $F = 2.0\\ \\mathrm{N}$ upwards does. The two things every physical quantity has are magnitude and unit.", "source": "research"},
 {"id": "m4", "kc": K1, "statement": "Any number produced by measuring or calculating counts as a physical quantity, including ratios and counts such as efficiency, strain and atomic number.",
  "refutation": "The 9702 syllabus says a physical quantity consists of a numerical magnitude and a unit, and CAIE 9702 multiple-choice questions apply this strictly: quantities quoted with no unit (efficiency, strain, atomic number) are not accepted as physical quantities there. (In wider SI usage they are called dimensionless quantities.) Number density of charge carriers has the unit $\\mathrm{m^{-3}}$, so it passes the test.",
  "contrast": "Number density $n = 8.5\\times10^{28}\\ \\mathrm{m^{-3}}$ has a magnitude and a unit; strain $= 0.002$ has only a number.", "source": "research"},
 {"id": "m5", "kc": K2, "statement": "Power-of-ten slips when converting units before estimating: using $10^{-2}$ instead of $10^{-6}$ for cm$^3$ to m$^3$, forgetting to convert km per hour to m per second, or moving the decimal point the wrong way.",
  "refutation": "Convert each dimension separately and raise the factor to the power of the dimension: $1\\ \\mathrm{cm} = 10^{-2}\\ \\mathrm{m}$ so $1\\ \\mathrm{cm^3} = (10^{-2})^3 = 10^{-6}\\ \\mathrm{m^3}$. Divide km per hour by 3.6 to get m per second. Then check that the answer is sensible for the object.",
  "contrast": "$50\\ \\mathrm{cm^3} = 50\\times10^{-6}\\ \\mathrm{m^3}$, not $50\\times10^{-2}\\ \\mathrm{m^3}$; $72\\ \\mathrm{km\\,h^{-1}} = 20\\ \\mathrm{m\\,s^{-1}}$, not $72\\ \\mathrm{m\\,s^{-1}}$.", "source": "ER 9702 s23 P11 Q2"},
]

def past(n, ref, qid, kcs, diff, cw, stem, opts, ans, expl, hints, dist=None, image=None):
    it = {"id": f"{ST}-p{n:02d}", "kcs": kcs, "kind": "mcq", "difficulty": diff, "command_word": cw,
          "source": {"type": "past", "ref": ref}, "stem": stem, "options": opts, "answer": ans,
          "marks": 1, "explanation": expl, "hints": hints}
    if dist: it["distractors"] = dist
    if image: it["image"] = image
    return it

items = [
 past(1, "CAIE 9702 · Nov 2022 · P12 · Q1", "w22_12_q1", [K1], 1, "Identify", "Which quantity is a physical quantity?",
  {"A": "flavour", "B": "kelvin", "C": "minute", "D": "potential difference"}, "D",
  "Potential difference has a numerical magnitude and a unit (the volt), so it is a physical quantity. The popular wrong choice B, kelvin, is a unit of the physical quantity temperature, and the minute is a unit of time; flavour has no unit.",
  ["Ask of each option: is this something I measure, or the unit I measure it in?", "A physical quantity is the thing measured and it comes with a unit; a unit is only the yardstick.", "For each option, try to write a sensible value with a unit, such as '3 of it'; which ones make sense?"], {"B": "m1", "C": "m1"}),
 past(2, "CAIE 9702 · Jun 2022 · P13 · Q1", "s22_13_q1", [K1], 2, "Identify", "Which pair of quantities are physical quantities?",
  {"A": "charge and ampere", "B": "efficiency and kilogram", "C": "pascal and strain", "D": "period and potential difference"}, "D",
  "Period and potential difference each have a numerical magnitude and a unit, so both are physical quantities. A, B and C each contain a unit (ampere, kilogram, pascal), and B and C also contain a ratio with no unit (efficiency, strain). The examiner report notes that A and C were the most popular wrong choices, showing confusion between units and quantities.",
  ["Both members of the correct pair must pass the test, not just one.", "Which members are units, or ratios with no unit, rather than measured quantities?", "Check which pair has two measurable things, each expressed with a unit."], {"A": "m1", "B": "m4", "C": "m1"}),
 past(3, "CAIE 9702 · Jun 2023 · P13 · Q1", "s23_13_q1", [K1], 2, "Identify", "What must be included in a record of a physical quantity?",
  {"A": "an integer value for the quantity", "B": "an SI unit", "C": "a numerical value for the quantity", "D": "a unit expressed in base units"}, "C",
  "A record needs a numerical value (with a unit, but that unit can be any correct unit, for example km or cm). The number need not be an integer, so A is wrong. The popular wrong choices B and D demand an SI unit or a base-unit form, which is not required.",
  ["Think of what a record such as $12\\ \\mathrm{cm}$ contains, and what is strictly necessary.", "Test each option against a valid record that breaks it, such as a length in centimetres.", "Only one option is needed by every possible record; the others add restrictions that are not required."], {"B": "m2", "D": "m2"}),
 past(4, "CAIE 9702 · Nov 2020 · P11 · Q1", "w20_11_q1", [K1], 2, "Identify", "Which quantity is a physical quantity?",
  {"A": "atomic number", "B": "efficiency", "C": "number density of charge carriers", "D": "strain"}, "C",
  "Number density of charge carriers has a magnitude and a unit ($\\mathrm{m^{-3}}$). Atomic number, efficiency and strain are pure numbers or ratios with no unit, so under the CAIE 9702 convention (magnitude and unit) they are not accepted as physical quantities.",
  ["A physical quantity needs both parts: numerical magnitude and unit.", "Ratios and counts cancel their units.", "For each option, ask what unit its value would be quoted in, if any."], {"A": "m4", "B": "m4", "D": "m4"}),
 past(5, "CAIE 9702 · Nov 2021 · P12 · Q1", "w21_12_q1", [K1], 2, "Identify", "Which row shows what all physical quantities must have? (Rows tick or cross magnitude, direction and unit; see the table.)",
  {"A": "A", "B": "B", "C": "C", "D": "D"}, "C",
  "Every physical quantity has a magnitude and a unit, but only vectors have a direction, so row C (magnitude and unit, no direction) is correct. Rows A and B tick direction for all quantities, which is wrong because scalars such as mass have none.",
  ["Test each column with a scalar such as mass or time.", "Does a mass of $5\\ \\mathrm{kg}$ point anywhere?", "Select the row that ticks exactly the two things every quantity has."], {"A": "m3", "B": "m3"}, image="Assets/mcq/9702_w21_12_q1.png"),
 past(6, "CAIE 9702 · Nov 2023 · P12 · Q1", "w23_12_q1", [K2], 3, "Identify", "A student estimates the maximum speed of some different moving objects.\nWhich maximum speed is not a reasonable estimate?",
  {"A": "container ship: 10 m s⁻¹", "B": "Olympic sprinter: 0.1 km s⁻¹", "C": "racing car: 9000 cm s⁻¹", "D": "snail: 0.01 km h⁻¹"}, "B",
  "Convert each to $\\mathrm{m\\,s^{-1}}$. B is $0.1\\ \\mathrm{km\\,s^{-1}} = 100\\ \\mathrm{m\\,s^{-1}}$, far above a sprinter's roughly $10\\ \\mathrm{m\\,s^{-1}}$. C, the popular wrong choice, is $9000\\ \\mathrm{cm\\,s^{-1}} = 90\\ \\mathrm{m\\,s^{-1}}$, about $320\\ \\mathrm{km\\,h^{-1}}$, which is reasonable for a racing car.",
  ["Put every speed into the same unit before comparing.", "You know typical speeds: a sprinter is about ten metres every second.", "Convert every option to $\\mathrm{m\\,s^{-1}}$ and compare each with the speed you expect for that object."], {"C": "m5"}),
 past(7, "CAIE 9702 · Nov 2020 · P13 · Q1", "w20_13_q1", [K2], 3, "Identify", "What is a reasonable estimate of the volume of a fully inflated standard football?",
  {"A": "600 cm³", "B": "6000 cm³", "C": "60 000 cm³", "D": "600 000 cm³"}, "B",
  "A football has a diameter of about 22 cm, so $V = \\tfrac{4}{3}\\pi r^3 \\approx \\tfrac{4}{3}\\pi(11)^3 \\approx 5.6\\times10^3\\ \\mathrm{cm^3}$, which is closest to 6000 $\\mathrm{cm^3}$. Option A would be an equivalent cube of side about 8 cm (too small) and C a cube of side about 39 cm (too large).",
  ["Estimate a length you know: how wide is a football?", "Model the football as a sphere with $V = \\tfrac{4}{3}\\pi r^3$.", "A diameter of about 22 cm gives a radius near 11 cm; cube it and multiply."]),
 past(8, "CAIE 9702 · Jun 2023 · P11 · Q2", "s23_11_q2", [K2], 4, "Identify", "What is the best estimate of the number of atoms in a piece of metal of volume 50 cm³?",
  {"A": "5 × 10¹⁵", "B": "5 × 10²⁵", "C": "5 × 10²⁹", "D": "5 × 10³¹"}, "B",
  "An atom has diameter about $10^{-10}\\ \\mathrm{m}$, so its volume is about $10^{-30}\\ \\mathrm{m^3}$. The metal has $V = 50\\times10^{-6}\\ \\mathrm{m^3}$, so $N \\approx 50\\times10^{-6}/10^{-30} = 5\\times10^{25}$. C comes from converting with $10^{-2}$ instead of $10^{-6}$, and D from not converting the volume at all.",
  ["Divide the volume of the piece by the volume of one atom.", "Convert the volume to $\\mathrm{m^3}$ first; remember $1\\ \\mathrm{cm} = 10^{-2}\\ \\mathrm{m}$ is cubed.", "The atomic diameter is about $10^{-10}\\ \\mathrm{m}$, so its volume is about $10^{-30}\\ \\mathrm{m^3}$."], {"C": "m5", "D": "m5"}),
 past(9, "CAIE 9702 · Jun 2021 · P12 · Q1", "s21_12_q1", [K2], 4, "Identify", "What is not a reasonable estimate of the physical property indicated?",
  {"A": "2 × 10³ W for the power dissipated by the heating element of an electric kettle", "B": "4 × 10² m³ for the volume of water in a swimming pool", "C": "5 × 10⁵ N s for the momentum of a lorry moving along a road", "D": "6 × 10² N for the weight of a fully grown racehorse"}, "D",
  "A racehorse has a mass of several hundred kilograms, so its weight is a few thousand newtons, not $6\\times10^{2}\\ \\mathrm{N}$ (that is the weight of a person). The popular wrong choice C is reasonable: $20\\,000\\ \\mathrm{kg}\\times25\\ \\mathrm{m\\,s^{-1}} = 5\\times10^{5}\\ \\mathrm{N\\,s}$.",
  ["Estimate each quantity from familiar masses, speeds and sizes.", "For each option, estimate the mass, speed or size involved and work out the quantity yourself.", "Weight is mass times $g$; is a horse only as heavy as a person?"]),
 past(10, "CAIE 9702 · Jun 2021 · P11 · Q1", "s21_11_q1", [K2], 3, "Identify", "What is a reasonable estimate of the volume of an adult person?",
  {"A": "0.10 m³", "B": "0.50 m³", "C": "1.0 m³", "D": "2.0 m³"}, "A",
  "An adult of mass about 80 kg has density close to that of water ($1000\\ \\mathrm{kg\\,m^{-3}}$), so $V = m/\\rho \\approx 80/1000 = 0.08\\ \\mathrm{m^3}$, close to 0.10 $\\mathrm{m^3}$. A cuboid of $1.6\\ \\mathrm{m}\\times0.4\\ \\mathrm{m}\\times0.2\\ \\mathrm{m}$ gives about $0.13\\ \\mathrm{m^3}$; $1\\ \\mathrm{m^3}$ would be a full cubic metre of water.",
  ["Estimate the person's mass, then use what you know about density.", "The human body is mostly water, density $1000\\ \\mathrm{kg\\,m^{-3}}$.", "Use $V = m/\\rho$ with a mass of about eighty kilograms."]),
 past(11, "CAIE 9702 · Jun 2021 · P13 · Q1", "s21_13_q1", [K2], 3, "Identify", "What is a reasonable estimate of the kinetic energy of an Olympic athlete sprinting in a 100 m race?",
  {"A": "40 J", "B": "400 J", "C": "4000 J", "D": "40 000 J"}, "C",
  "With $m \\approx 80\\ \\mathrm{kg}$ and $v \\approx 10\\ \\mathrm{m\\,s^{-1}}$, $E_k = \\tfrac{1}{2}mv^2 = \\tfrac{1}{2}\\times80\\times10^2 = 4000\\ \\mathrm{J}$. The popular wrong choice B, 400 J, comes from forgetting to square the speed.",
  ["You need a sensible mass and a sensible speed for the athlete.", "Kinetic energy depends on the square of the speed.", "Use $E_k = \\tfrac{1}{2}mv^2$ with about eighty kilograms and ten metres per second."]),
 past(12, "CAIE 9702 · Nov 2019 · P12 · Q1", "w19_12_q1", [K2], 5, "Identify", "A cyclist has a speed of 5 m s⁻¹ and a small car has a speed of 12 m s⁻¹.\nWhich statement does not give a reasonable estimate?",
  {"A": "The kinetic energy of the cyclist is 1 × 10³ J.", "B": "The kinetic energy of the car is 7 × 10⁴ J.", "C": "The momentum of the cyclist is 4 × 10² kg m s⁻¹.", "D": "The momentum of the car is 2 × 10⁵ kg m s⁻¹."}, "D",
  "Take a cyclist with bike of about 80 kg and a small car of about 1000 kg. The cyclist has $E_k = \\tfrac{1}{2}(80)(5)^2 = 1000\\ \\mathrm{J}$ and $p = 80\\times5 = 400\\ \\mathrm{kg\\,m\\,s^{-1}}$; the car has $E_k = \\tfrac{1}{2}(1000)(12)^2 = 7.2\\times10^{4}\\ \\mathrm{J}$ and $p = 1000\\times12 = 1.2\\times10^{4}\\ \\mathrm{kg\\,m\\,s^{-1}}$, so D (about 17 times too big) is the one that is not reasonable.",
  ["Estimate a mass for each vehicle, then test all four statements.", "Kinetic energy is $\\tfrac{1}{2}mv^2$ and momentum is $mv$.", "Pick a mass for the vehicle, multiply by its speed, and compare with the options."]),
]

# ---------- generated items ----------
items += [
 {"id": f"{ST}-i01", "kcs": [K1], "kind": "numeric", "difficulty": 2, "command_word": "Calculate", "source": {"type": "generated"},
  "stem": "The length of a wire is recorded as $L = [[a]]\\ \\mathrm{m}$. Calculate the numerical magnitude of the same length when it is expressed in millimetres.",
  "template": {"params": {"a": {"choices": [0.25, 0.5, 0.75, 1.2, 2.4, 3.5]}}, "answer": "a * 1000",
               "distractors": [{"expr": "a / 1000", "misconception": "m5"}, {"expr": "a"}]},
  "answer": {"unit": "", "exact": True}, "marks": 1,
  "explanation": "The quantity is the number times the unit and stays the same: $1\\ \\mathrm{m} = 1000\\ \\mathrm{mm}$, so the smaller unit needs a larger number, $L = 1000a$ in mm.",
  "hints": ["The length itself does not change, only how it is written.", "A millimetre is a smaller unit than a metre, so more of them are needed.", "Multiply the number of metres by the number of millimetres in one metre."]},
 {"id": f"{ST}-i02", "kcs": [K1], "kind": "mcq", "difficulty": 3, "command_word": "Identify", "source": {"type": "generated"},
  "stem": "A student records the current in a lamp as 'the current was 0.35'. Which statement is correct?",
  "options": {"A": "The record is complete because the number gives the current.", "B": "The record is incomplete because it has no unit.",
              "C": "The record is incomplete because it has no direction.", "D": "The record is incomplete because it does not use an SI base unit."},
  "answer": "B", "distractors": {"C": "m3", "D": "m2"}, "marks": 1, "shuffle": True,
  "explanation": "A physical quantity consists of a numerical magnitude and a unit, and this record has only the number. Direction is not needed for a scalar, and the unit need not be an SI base unit: 0.35 A or 350 mA would both be complete.",
  "hints": ["Compare the record with the two parts every physical quantity has.", "Ask which of those two parts the student wrote down.", "The number alone is only half of a physical quantity; something must give it meaning."]},
 {"id": f"{ST}-i03", "kcs": [K1], "kind": "short", "difficulty": 3, "command_word": "Explain", "source": {"type": "generated"},
  "stem": "Explain why the kelvin is not a physical quantity.",
  "rubric": [{"point": "the kelvin is a unit", "keywords": [["is a unit", "is only a unit", "is just a unit", "is the unit", "a unit of", "a unit for", "unit of temperature", "unit for temperature", "unit used", "unit in which"]]},
             {"point": "the physical quantity is temperature (thermodynamic temperature)", "keywords": [["temperature"]]},
             {"point": "a physical quantity needs a numerical magnitude as well as a unit; the kelvin has no number", "keywords": [["magnitude", "number", "numerical", "value"], ["no ", "not have", "doesn't have", "without", "lacks", "missing", "on its own", "by itself", "alone"]]}],
  "marks": 3,
  "explanation": "The kelvin is a unit, in which the physical quantity temperature is measured. A physical quantity is a numerical magnitude with a unit, and a unit on its own has no magnitude.",
  "hints": ["Separate what is being measured from what it is measured in.", "The kelvin is used for one particular quantity; which one?", "Recall what two parts make up any physical quantity and which is missing here."]},
 {"id": f"{ST}-i04", "kcs": [K1], "kind": "structured", "difficulty": 4, "command_word": "Explain", "source": {"type": "generated"},
  "stem": "A student measures a wire and writes down 'length = 0.75'.\n\n(a) State what is missing from the record.\n(b) Explain why the record is not a physical quantity.\n(c) The student later writes the same length as 750 mm. Explain why the number has changed but the physical quantity has not.\n(d) The list is speed, newton, density, second, temperature. Identify the physical quantities.",
  "scheme": [{"mark": "B1", "point": "(a) a unit"},
             {"mark": "B1", "point": "(b) a physical quantity consists of a numerical magnitude and a unit (the record has only the magnitude)"},
             {"mark": "B1", "point": "(c) the unit is smaller (mm instead of m) so a larger number is needed; magnitude × unit is the same length"},
             {"mark": "B1", "point": "(d) speed, density and temperature (the newton and the second are units)"}],
  "marks": 4,
  "explanation": "A physical quantity is a numerical magnitude and a unit. Changing from metres to millimetres changes the number by a factor of 1000 because the unit is 1000 times smaller, so the length is unchanged. Of the list, only speed, density and temperature are quantities; the newton and second are units."},
 {"id": f"{ST}-i05", "kcs": [K2], "kind": "numeric", "difficulty": 4, "command_word": "Estimate", "source": {"type": "generated"},
  "stem": "A metal cube has sides of length [[s]] cm. Take the diameter of an atom to be $1.0\\times10^{-10}\\ \\mathrm{m}$ and assume each atom occupies a cube of that side. Estimate the number of atoms in the cube.",
  "template": {"params": {"s": {"choices": [1.0, 2.0, 3.0, 4.0, 6.0]}}, "answer": "(s * 1e-2) ** 3 / (1e-10) ** 3",
               "distractors": [{"expr": "s ** 3 * 1e-2 / (1e-10) ** 3", "misconception": "m5"}, {"expr": "s ** 3 * 1e-6 / 1e-10"}]},
  "answer": {"unit": "", "sf_ok": [1, 2, 3], "tol_rel": 0.15}, "marks": 3,
  "explanation": "Convert the side to metres, $s\\times10^{-2}\\ \\mathrm{m}$, and cube it to get the volume in $\\mathrm{m^3}$. Divide by the volume of one atom, $(10^{-10})^3 = 10^{-30}\\ \\mathrm{m^3}$, so $N = (s\\times10^{-2})^3/10^{-30}$.",
  "hints": ["Number of atoms is the volume of the cube divided by the volume of one atom.", "Convert centimetres to metres before cubing, and cube the atomic diameter as well.", "Find the cube volume in $\\mathrm{m^3}$ and divide by $(10^{-10}\\ \\mathrm{m})^3$."]},
 {"id": f"{ST}-i06", "kcs": [K2], "kind": "numeric", "difficulty": 3, "command_word": "Calculate", "source": {"type": "generated"},
  "stem": "A family car of mass [[m]] kg travels along a road at [[v]] " + KMH + ". Calculate its kinetic energy in J.",
  "template": {"params": {"m": {"choices": [800, 1000, 1200, 1500]}, "v": {"choices": [36, 54, 72, 90, 108]}}, "answer": "0.5 * m * (v / 3.6) ** 2",
               "distractors": [{"expr": "0.5 * m * v ** 2", "misconception": "m5"}, {"expr": "0.5 * m * (v * 3.6) ** 2", "misconception": "m5"}]},
  "answer": {"unit": "J", "sf_ok": [2, 3]}, "marks": 2,
  "explanation": "Convert the speed first: $v/3.6$ gives $\\mathrm{m\\,s^{-1}}$. Then $E_k = \\tfrac{1}{2}mv^2$ with $v$ in $\\mathrm{m\\,s^{-1}}$.",
  "hints": ["Kinetic energy formulas need speed in SI units.", "Divide a speed in $\\mathrm{km\\,h^{-1}}$ by 3.6 to get $\\mathrm{m\\,s^{-1}}$.", "After converting, use $E_k = \\tfrac{1}{2}mv^2$."]},
 {"id": f"{ST}-i07", "kcs": [K2], "kind": "mcq", "difficulty": 2, "command_word": "Identify", "source": {"type": "generated"},
  "stem": "Which is a reasonable estimate of the speed of a person walking normally?",
  "options": {"A": "0.15 m s⁻¹", "B": "1.5 m s⁻¹", "C": "15 m s⁻¹", "D": "150 m s⁻¹"}, "answer": "B", "marks": 1, "shuffle": True,
  "explanation": "A brisk walk covers about 5 km in an hour, which is $5000/3600 \\approx 1.4\\ \\mathrm{m\\,s^{-1}}$. $15\\ \\mathrm{m\\,s^{-1}}$ is a fast cyclist or a car in town.",
  "hints": ["Think of a journey you have walked and how long it took.", "Walking covers a few kilometres in an hour.", "Convert a few kilometres in an hour to metres per second."]},
 {"id": f"{ST}-i08", "kcs": [K2], "kind": "short", "difficulty": 3, "command_word": "Suggest", "source": {"type": "generated"},
  "stem": "Suggest how the thickness of a single sheet of paper can be estimated using a metre rule.",
  "rubric": [{"point": "measure the thickness of a stack or ream of many sheets", "keywords": [["stack", "pile", "ream", "many sheets", "several sheets", "lots of sheets", "sheets together", "100 sheets", "500 sheets", "book"]]},
             {"point": "divide by the number of sheets", "keywords": [["divide", "divided", "÷", "per sheet", "number of sheets"]]}],
  "marks": 2,
  "explanation": "One sheet is too thin for a rule, so measure many sheets together and divide their total thickness by the number of sheets.",
  "hints": ["A single sheet is far thinner than the smallest division on a rule.", "Use many sheets at once so the total is measurable.", "One sheet is too thin to measure directly; how could you make the thickness bigger, and then get back to one sheet?"]},
 {"id": f"{ST}-i09", "kcs": [K2], "kind": "structured", "difficulty": 5, "command_word": "Estimate", "source": {"type": "generated"},
  "stem": "Estimate the mass of air in a classroom. The density of air is $1.2\\ \\mathrm{kg\\,m^{-3}}$.",
  "scheme": [{"mark": "B1", "point": "sensible room dimensions, for example 8 m × 6 m × 3 m (accept volume 100 to 200 $\\mathrm{m^3}$)"},
             {"mark": "M1", "point": "mass = density × volume"},
             {"mark": "A1", "point": "mass of the order of $10^2$ kg, for example $8\\times6\\times3\\times1.2 \\approx 170$ kg", "check": {"kind": "numeric", "answer": {"value": 172.8, "unit": "kg", "sf_ok": [2, 3], "tol_rel": 0.6}}}],
  "marks": 3,
  "explanation": "A classroom is about $8\\ \\mathrm{m}\\times6\\ \\mathrm{m}\\times3\\ \\mathrm{m} = 144\\ \\mathrm{m^3}$, so $m = \\rho V = 1.2\\times144 \\approx 170\\ \\mathrm{kg}$, about the mass of two adults."},
]

worked = [
 {"id": "we1", "kc": K2, "problem": "Estimate the kinetic energy of an Olympic sprinter during a 100 m race.",
  "steps": [
   {"do": "Estimate the mass: an adult athlete is about $m = 80\\ \\mathrm{kg}$.", "why": "Estimates begin with familiar anchors; skipping this step and guessing the energy directly is what leads to power-of-ten errors."},
   {"do": "Estimate the speed: the race takes about 10 s, so $v = 100/10 = 10\\ " + "\\mathrm{m\\,s^{-1}}$.", "why": "Speed is in SI units before it enters an energy formula.", "check": {"kind": "numeric", "answer": {"value": 10.0, "unit": "m s^-1", "sf_ok": [1, 2]}}},
   {"do": "State $E_k = \\tfrac{1}{2}mv^2$, substitute and evaluate: $E_k = \\tfrac{1}{2}\\times80\\times10^2 = 4000\\ \\mathrm{J}$, about $4\\times10^3\\ \\mathrm{J}$.", "why": "The speed must be squared, and one significant figure is enough for an estimate.", "check": {"kind": "numeric", "answer": {"value": 4000.0, "unit": "J", "sf_ok": [1, 2]}}}],
  "faded": {"id": "we1f", "problem": "Estimate the kinetic energy of a cyclist and bicycle of total mass 90 kg travelling at $18\\ " + "\\mathrm{km\\,h^{-1}}$.",
            "answer": {"value": ke_cyc, "unit": "J", "sf_ok": [2, 3], "tol_rel": 0.05}, "blank_from": 1}},
 {"id": "we2", "kc": K2, "problem": "Estimate the number of atoms in a metal cube of side 3.0 cm. Take the diameter of an atom as $1.0\\times10^{-10}\\ \\mathrm{m}$.",
  "steps": [
   {"do": "Convert the side to metres, $0.030\\ \\mathrm{m}$, then find the volume: $V = (0.030)^3 = 2.7\\times10^{-5}\\ \\mathrm{m^3}$.", "why": "Converting cm$^3$ directly with $10^{-2}$ is the classic slip; cube the metre value instead.", "check": {"kind": "numeric", "answer": {"value": V3, "unit": "m^3", "sf_ok": [2]}}},
   {"do": "Model each atom as a cube of side $10^{-10}\\ \\mathrm{m}$: $V_{atom} = (10^{-10})^3 = 10^{-30}\\ \\mathrm{m^3}$.", "why": "The volume of an atom is the diameter cubed, not the diameter."},
   {"do": "Divide: $N = V/V_{atom} = 2.7\\times10^{-5}/10^{-30} = 2.7\\times10^{25}$, about $3\\times10^{25}$ atoms.", "why": "The number of atoms is the volume of the piece divided by the volume of one atom.", "check": {"kind": "numeric", "answer": {"value": N3, "unit": "", "sf_ok": [1, 2]}}}],
  "faded": {"id": "we2f", "problem": "Estimate the number of atoms in a metal cube of side 5.0 cm, using the same atomic diameter.",
            "answer": {"value": N5, "unit": "", "sf_ok": [2, 3], "tol_rel": 0.05}, "blank_from": 1}},
]

fc = [
 ("fc1", K1, "What two parts does every physical quantity consist of?", "A physical quantity consists of a numerical magnitude and a unit."),
 ("fc2", K1, "How is a physical quantity written symbolically? Give an example.", "physical quantity = numerical magnitude × unit, for example $v = 12\\ \\mathrm{m\\,s^{-1}}$."),
 ("fc3", K1, "Is the kelvin a physical quantity?", "No. The kelvin is a unit; the physical quantity is (thermodynamic) temperature."),
 ("fc4", K1, "What must be included in a record of a physical quantity?", "A numerical value (magnitude) and a unit. The unit need not be an SI or base unit, and direction is only needed for vector quantities."),
 ("fc5", K1, "Give two examples of things that are units, not physical quantities.", "Any two of: metre, kilogram, second, ampere, kelvin, newton, pascal, volt, minute."),
 ("fc6", K2, "Typical mass of an adult and of a small car.", "Adult about 70 to 80 kg; small car about 1000 kg."),
 ("fc7", K2, "Typical speeds: walking, sprinter, car on a road.", "Walking about $1.5\\ \\mathrm{m\\,s^{-1}}$; sprinter about $10\\ \\mathrm{m\\,s^{-1}}$; car about $25\\ \\mathrm{m\\,s^{-1}}$ ($90\\ \\mathrm{km\\,h^{-1}}$)."),
 ("fc8", K2, "Order of magnitude of the diameter of an atom and the volume of an atom.", "Diameter about $10^{-10}\\ \\mathrm{m}$; volume about $10^{-30}\\ \\mathrm{m^3}$."),
 ("fc9", K2, "Wavelength range of visible light; green light.", "About 400 nm to 700 nm; green about 500 to 550 nm."),
 ("fc10", K2, "Convert $\\mathrm{cm^3}$ to $\\mathrm{m^3}$ and $\\mathrm{km\\,h^{-1}}$ to $\\mathrm{m\\,s^{-1}}$.", "$1\\ \\mathrm{cm^3} = 10^{-6}\\ \\mathrm{m^3}$; divide $\\mathrm{km\\,h^{-1}}$ by 3.6 to get $\\mathrm{m\\,s^{-1}}$."),
 ("fc11", K2, "Density of water and of air, and typical weight of an adult.", "Water $1000\\ \\mathrm{kg\\,m^{-3}}$; air about $1.2\\ \\mathrm{kg\\,m^{-3}}$; adult weight about 700 N."),
]

pack = {"subtopic": ST, "spec": "9702", "version": 1,
 "note": "Subjects/9702 Physics/01 Physical quantities and units/1.1 Physical quantities.md",
 "outline": "A physical quantity is what is measured, and it always has a numerical magnitude and a unit: $Q = \\text{number} \\times \\text{unit}$. The unit alone (kelvin, metre, ampere) is not a physical quantity, the unit need not be SI, and only vectors have a direction. In CAIE 9702 MCQs, ratios quoted with no unit, such as strain or efficiency, are not accepted as physical quantities. Changing to a smaller unit makes the number larger, while the quantity is unchanged. To estimate: choose familiar anchor values (adult 80 kg, sprinter $10\\ \\mathrm{m\\,s^{-1}}$, atom $10^{-10}\\ \\mathrm{m}$), convert to SI units carefully, use the relevant equation, and give an answer to one or two significant figures. Check that the order of magnitude is sensible.",
 "misconceptions": mis,
 "worked": worked,
 "items": items,
 "flashcards": [{"id": i, "kc": k, "front": f, "back": b} for i, k, f, b in fc],
 "diagrams": []}

out = Path("build/out/packs/9702/9702-1.1.json"); out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(pack, ensure_ascii=False, indent=1))
print("wrote", out, len(items), "items")
