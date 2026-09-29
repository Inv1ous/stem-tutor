"""Generator for pack 9702-1.2 (SI units). Content as data; every unit expression is built from dimension
vectors and every numeric answer is asserted with sympy/arithmetic before writing."""
import json
from fractions import Fraction
from pathlib import Path

import sympy as sp

ROOT = Path(__file__).resolve().parents[3]
SUB = "9702-1.2"
K1, K2, K3, K4 = f"{SUB}.1", f"{SUB}.2", f"{SUB}.3", f"{SUB}.4"

# ---------- dimension algebra (kg, m, s, A, K) ----------
DIMS = ["kg", "m", "s", "A", "K"]


def V(**k):
    return tuple(Fraction(k.get(d, 0)) for d in DIMS)


def mul(*a):
    return tuple(sum(x) for x in zip(*a))


def inv(a):
    return tuple(-x for x in a)


def div(a, b):
    return mul(a, inv(b))


def pw(a, n):
    return tuple(x * Fraction(n) for x in a)


def fmt(v, order=None):
    parts = []
    for d in order or DIMS:
        e = v[DIMS.index(d)]
        if e == 0:
            continue
        parts.append(d if e == 1 else f"{d}^{{{e}}}")
    return "$\\mathrm{" + "\\,".join(parts) + "}$"


KG, M, S, A, KEL = V(kg=1), V(m=1), V(s=1), V(A=1), V(K=1)
N = div(mul(KG, M), pw(S, 2))
J = mul(N, M)
W = div(J, S)
PA = div(N, pw(M, 2))
C = mul(A, S)
VOLT = div(J, C)
OHM = div(VOLT, A)
assert N == V(kg=1, m=1, s=-2) and J == V(kg=1, m=2, s=-2) and W == V(kg=1, m=2, s=-3)
assert PA == V(kg=1, m=-1, s=-2) and VOLT == V(kg=1, m=2, s=-3, A=-1) and OHM == V(kg=1, m=2, s=-3, A=-2)


def opts(*vs, order=None):
    return {L: fmt(v, order) for L, v in zip("ABCD", vs)}


def key_of(vs, target):
    return "ABCD"[[v == target for v in vs].index(True)]


items = []
_gen = [0]
_past = [0]


def gen(kcs, kind, diff, cw, stem, marks, expl, hints, **kw):
    _gen[0] += 1
    it = {"id": f"{SUB}-i{_gen[0]:02d}", "kcs": kcs, "kind": kind, "difficulty": diff, "command_word": cw,
          "source": {"type": "generated"}, "stem": stem, "marks": marks, **kw, "explanation": expl, "hints": hints}
    if kind == "mcq":
        it["shuffle"] = True
    items.append(it)


def past(qid, kcs, diff, cw, stem, options, answer, expl, hints, distractors=None, image=None):
    _past[0] += 1
    it = {"id": f"{SUB}-p{_past[0]:02d}", "kcs": kcs, "kind": "mcq", "difficulty": diff, "command_word": cw,
          "source": {"type": "past", "ref": qid}, "stem": stem, "options": options, "answer": answer, "marks": 1,
          "distractors": distractors or {}, "explanation": expl, "hints": hints}
    if image:
        it["image"] = image
    items.append(it)


# ======================= PAST MCQs (12) =======================
past("9702_w23_12_q2", [K1], 1, "Identify", "Which quantity is an SI base quantity?",
     {"A": "force", "B": "newton", "C": "second", "D": "time"}, "D",
     "Time is one of the SI base quantities; the second is its unit. Force is a derived quantity and the newton is its unit. Option C is the popular wrong answer because it names a unit, but the question asks for a quantity (examiners: weaker candidates confused quantities with units).",
     ["Ask what is being measured, not what it is measured in.",
      "A base quantity is one of the few independent quantities from which all other quantities are built.",
      "Two options are units, so cross those out first; then decide which remaining quantity cannot be built from the base quantities."],
     {"B": "m2", "C": "m2"})
past("9702_s19_13_q1", [K1], 1, "Identify", "Which is an SI base unit?",
     {"A": "current", "B": "gram", "C": "kelvin", "D": "volt"}, "C",
     "The kelvin is the SI base unit of temperature. Current is a base quantity, not a unit; the volt is a derived unit ($\\mathrm{V}=\\mathrm{J\\,C^{-1}}$). The gram is the popular wrong answer (examiners): the SI base unit of mass is the kilogram, and the gram is only $10^{-3}$ of it.",
     ["A unit is a name like the metre; a quantity is what it measures.",
      "Remove any option that names a quantity, then any option built from other units.",
      "One remaining option is a thousandth of the SI base unit of mass, so it is not itself a base unit."],
     {"A": "m2", "B": "m1"})
past("9702_w24_12_q1", [K1], 2, "Identify",
     "A physical quantity consists of a magnitude and a unit. Which row does **not** show a correct combination of a quantity and its unit?",
     {"A": "mass, gram", "B": "length, metre", "C": "charge, ampere", "D": "temperature, kelvin"}, "C",
     "The ampere is the unit of current, not of charge; charge is measured in coulomb ($\\mathrm{C}=\\mathrm{A\\,s}$). Option A is a trap: the gram is a valid unit of mass even though the SI base unit is the kilogram.",
     ["Check each row separately: is the unit one that measures that quantity?",
      "Recall which base quantity goes with each of the five base units.",
      "Three rows pair a quantity with a unit that measures it; one pairs it with the unit of a different quantity."],
     {"A": "m1"}, image="Assets/mcq/9702_w24_12_q1.png")

# 1.2.2 past: derived units
sig_opts = [V(kg=1, s=-2, K=-4), V(kg=1, s=-3, K=-4), V(kg=1, m=-1, s=-2, K=-4), V(kg=1, m=-1, s=-3, K=-4)]
sigma = div(div(W, pw(M, 2)), pw(KEL, 4))
o = opts(*sig_opts)
past("9702_w24_13_q3", [K2], 4, "Determine",
     "The power output $P$ of a star can be modelled with the equation $P=\\sigma A T^{4}$, where $\\sigma$ is a constant, $A$ is the surface area of the star and $T$ is the surface temperature of the star. What are the SI base units of $\\sigma$?",
     o, key_of(sig_opts, sigma),
     "$\\sigma=P/(AT^4)$, so its units are $\\mathrm{kg\\,m^2\\,s^{-3}}\\div(\\mathrm{m^2}\\,\\mathrm{K^4})=\\mathrm{kg\\,s^{-3}\\,K^{-4}}$. Option A comes from using energy ($\\mathrm{kg\\,m^2\\,s^{-2}}$) for $P$, forgetting that power is energy per unit time.",
     ["Rearrange the equation to make $\\sigma$ the subject.",
      "$\\sigma = P/(AT^4)$: write $P$, $A$ and $T$ in base units (power is energy per unit time).",
      "Power is $\\mathrm{kg\\,m^2\\,s^{-3}}$ and area is $\\mathrm{m^2}$; divide, and $\\mathrm{K^4}$ stays in the denominator."],
     {"A": "m3", "C": "m3", "D": "m3"})
emf_opts = [V(kg=1, m=2, s=-1, A=-1), V(kg=1, m=2, s=-3, A=-1), V(kg=1, m=2, s=-1, A=1), V(kg=1, m=1, s=-3, A=-1)]
o = opts(*emf_opts)
past("9702_w22_13_q2", [K2], 3, "Identify", "What are the SI base units of electromotive force (e.m.f.)?",
     o, key_of(emf_opts, VOLT),
     "E.m.f. is energy per unit charge, so $\\mathrm{V}=\\mathrm{J\\,C^{-1}}=\\mathrm{kg\\,m^2\\,s^{-2}}\\div(\\mathrm{A\\,s})=\\mathrm{kg\\,m^2\\,s^{-3}\\,A^{-1}}$. Option A comes from multiplying by the second in $\\mathrm{C}=\\mathrm{A\\,s}$ instead of dividing by it.",
     ["E.m.f. is a kind of potential difference: energy transferred per unit charge.",
      "$V=W/Q$: write the joule and the coulomb in base units.",
      "$\\mathrm{J}=\\mathrm{kg\\,m^2\\,s^{-2}}$ and $\\mathrm{C}=\\mathrm{A\\,s}$; now divide."],
     {"A": "m3", "C": "m3", "D": "m3"})
past("9702_w19_13_q2", [K2], 3, "Identify", "Which two units are **not** equivalent to each other?",
     {"A": "N m and kg m² s⁻²", "B": "N s and kg m s⁻¹", "C": "J s⁻¹ and kg m² s⁻³", "D": "Pa and kg m s⁻²"}, "D",
     "$\\mathrm{Pa}=\\mathrm{N\\,m^{-2}}=\\mathrm{kg\\,m^{-1}\\,s^{-2}}$, whereas $\\mathrm{kg\\,m\\,s^{-2}}$ is the newton, so D is not an equivalent pair. The other three pairs are equivalent: $\\mathrm{N\\,m}=\\mathrm{J}=\\mathrm{kg\\,m^2\\,s^{-2}}$, $\\mathrm{N\\,s}=\\mathrm{kg\\,m\\,s^{-1}}$ (impulse equals momentum) and $\\mathrm{J\\,s^{-1}}=\\mathrm{W}=\\mathrm{kg\\,m^2\\,s^{-3}}$. The pascal is a force per unit area, so its base units contain $\\mathrm{m^{-1}}$ not $\\mathrm{m}$.",
     ["Convert both units in each pair to base units, then compare them.",
      "Use $\\mathrm{N}=\\mathrm{kg\\,m\\,s^{-2}}$, $\\mathrm{J}=\\mathrm{N\\,m}$, $\\mathrm{W}=\\mathrm{J\\,s^{-1}}$ and $\\mathrm{Pa}=\\mathrm{N\\,m^{-2}}$.",
      "Three pairs match exactly; look for the pair where a division by area has been forgotten."],
     {})
mob_opts = [V(A=1, kg=-1), V(A=1, s=2, kg=-1), V(A=1, s=1, kg=-1), V(A=1, s=-2, kg=-1)]
mob = div(mul(mul(A, S), S), KG)
past("9702_w21_11_q2", [K2], 4, "Determine",
     "The mobility $\\mu$ of electrons in a metal conductor is $\\mu=\\dfrac{e\\tau}{m}$, where $e$ is the charge on an electron, $m$ is its mass and $\\tau$ is the average time between collisions of an electron with the atoms. What are the SI base units of $\\mu$?",
     opts(*mob_opts, order=["A", "s", "kg"]), key_of(mob_opts, mob),
     "Charge has units $\\mathrm{A\\,s}$, so $\\mu=(\\mathrm{A\\,s})(\\mathrm{s})/\\mathrm{kg}=\\mathrm{A\\,s^2\\,kg^{-1}}$. Option C is $e/m$: it leaves out the factor of $\\tau$ (a second).",
     ["Replace each symbol in $\\mu=e\\tau/m$ by its unit.",
      "The electron charge is measured in coulomb; write the coulomb in base units.",
      "Multiply the units in the numerator ($e$ and $\\tau$), then divide by the unit of mass."],
     {"C": "m3", "D": "m3"}, image="Assets/mcq/9702_w21_11_q2.png")

# 1.2.3 past: homogeneity
p, q = sp.symbols("p q")
sol = sp.solve([p + q, -2 * p + 1], [p, q])  # kg: p+q=0 ; s: -2p = -1 (v = m s^-1)
assert sol == {p: sp.Rational(1, 2), q: -sp.Rational(1, 2)}
past("9702_w20_12_q2", [K3], 4, "Determine",
     "The speed $v$ of waves on a stretched wire is given by $v=T^{p}\\mu^{q}$, where $T$ is the tension in the wire and $\\mu$ is the mass per unit length of the wire. What are the values of $p$ and $q$?",
     {"A": "$p=-\\tfrac12,\\ q=-\\tfrac12$", "B": "$p=-\\tfrac12,\\ q=\\tfrac12$", "C": "$p=\\tfrac12,\\ q=-\\tfrac12$",
      "D": "$p=\\tfrac12,\\ q=\\tfrac12$"}, "C",
     "$T$ has base units $\\mathrm{kg\\,m\\,s^{-2}}$ and $\\mu$ has $\\mathrm{kg\\,m^{-1}}$; $v$ needs $\\mathrm{m\\,s^{-1}}$. No kg on the left means $p+q=0$, and the power of s gives $-2p=-1$, so $p=\\tfrac12$ and $q=-\\tfrac12$ ($v=\\sqrt{T/\\mu}$).",
     ["Write the base units of $v$, $T$ and $\\mu$.",
      "$T$ is a force and $\\mu$ is mass divided by length.",
      "Equate the power of kg on each side, then the power of s."],
     {}, image="Assets/mcq/9702_w20_12_q2.png")
past("9702_s25_12_q4", [K3], 3, "Determine",
     "The time period $T$ of a pendulum is given by $T=2\\pi\\left(\\dfrac{L}{g}\\right)^{n}$, where $L$ is the length of the pendulum and $g$ is the acceleration of free fall. The equation is homogeneous. What is the value of $n$?",
     {"A": "$-2$", "B": "$-\\tfrac12$", "C": "$\\tfrac12$", "D": "$2$"}, "C",
     "$L/g$ has base units $\\mathrm{m}/(\\mathrm{m\\,s^{-2}})=\\mathrm{s^2}$, so $(L/g)^n$ has units $\\mathrm{s^{2n}}$. $T$ is in seconds, so $2n=1$ and $n=\\tfrac12$; the $2\\pi$ has no units.",
     ["Work out the base units of $L/g$ first.",
      "$L$ is in m and $g$ is in $\\mathrm{m\\,s^{-2}}$; simplify the quotient.",
      "Once you have the base units of $L/g$, the power $n$ must turn them into the base unit of $T$."],
     {}, image="Assets/mcq/9702_s25_12_q4.png")
past("9702_w19_11_q2", [K3], 3, "Identify",
     "The speed of a wave in deep water depends on its wavelength $L$ and the acceleration of free fall $g$. What is a possible equation for the speed $v$ of the wave?",
     {"A": "$v=\\sqrt{\\dfrac{gL}{2\\pi}}$", "B": "$v=\\dfrac{gL}{4\\pi^2}$", "C": "$v=2\\pi\\sqrt{\\dfrac{g}{L}}$", "D": "$v=\\dfrac{2\\pi g}{L}$"}, "A",
     "$gL$ has base units $\\mathrm{m^2\\,s^{-2}}$, so $\\sqrt{gL}$ has $\\mathrm{m\\,s^{-1}}$, the units of speed; $2\\pi$ has no units. B has units $\\mathrm{m^2\\,s^{-2}}$ (no square root), while C and D both have units $\\mathrm{s^{-1}}$.",
     ["Speed has base units $\\mathrm{m\\,s^{-1}}$; test each option against this.",
      "A square root halves each power of a unit; numbers such as $2\\pi$ and $4\\pi^2$ carry no units.",
      "$gL$ has base units $\\mathrm{m^2\\,s^{-2}}$; look for the option that turns this into the units of speed."],
     {}, image="Assets/mcq/9702_w19_11_q2.png")

# 1.2.4 past: prefixes
t = {"A": 0.05e-3, "B": 50e-9, "C": 500000e-12, "D": 0.5e-6}
assert min(t, key=t.get) == "B"
past("9702_w20_11_q2", [K4], 3, "Identify", "Which time interval is the shortest?",
     {"A": "0.05 ms", "B": "50 ns", "C": "500 000 ps", "D": "0.5 μs"}, "B",
     "In seconds the options are $5\\times10^{-5}$ (A), $5\\times10^{-8}$ (B), $5\\times10^{-7}$ (C) and $5\\times10^{-7}$ (D), so B is shortest. C and D are equal to each other and ten times larger than B, which catches anyone who mixes up nano ($10^{-9}$), pico ($10^{-12}$) and micro ($10^{-6}$).",
     ["Convert every interval to seconds using the prefix values.",
      "milli is $10^{-3}$, micro is $10^{-6}$, nano is $10^{-9}$ and pico is $10^{-12}$.",
      "Write each as a number times a power of ten and compare the powers first."],
     {"C": "m5", "D": "m5"})
val = 0.25e3 / (1e-3) ** 2
assert abs(val - 2.5e8) < 1
past("9702_s25_12_q2", [K4], 4, "Calculate", "What is 0.25 kN mm⁻² expressed in N m⁻²?",
     {"A": "0.00025 N m⁻²", "B": "0.25 N m⁻²", "C": "250 000 N m⁻²", "D": "250 000 000 N m⁻²"}, "D",
     "$0.25\\ \\mathrm{kN\\,mm^{-2}}=0.25\\times10^{3}\\ \\mathrm{N}\\div(10^{-3}\\ \\mathrm{m})^2=0.25\\times10^{3}\\div10^{-6}=2.5\\times10^{8}\\ \\mathrm{N\\,m^{-2}}$. Option C applies only $10^{-3}$ to the area, forgetting that the prefix is squared along with the unit.",
     ["Convert kN to N and mm to m separately.",
      "$1\\ \\mathrm{kN}=10^{3}\\ \\mathrm{N}$, but $1\\ \\mathrm{mm^2}$ is $(10^{-3}\\ \\mathrm{m})^2$.",
      "Divide by the squared conversion factor for the area in the denominator."],
     {"C": "m5"})

# ======================= GENERATED =======================
# ---- 1.2.1
gen([K1], "mcq", 1, "Identify", "Which row correctly pairs an SI base quantity with its SI base unit?",
    1, "Time is measured in seconds. The base unit of mass is the kilogram (not the gram), the ampere is the unit of current (the coulomb is a derived unit, $\\mathrm{A\\,s}$), and the kelvin, not the degree Celsius, is the SI base unit of temperature.",
    ["Check each pairing against the five base quantities you have memorised.",
     "Two options use a unit that is derived or is not the SI base unit; a third uses a non-SI temperature scale.",
     "Which row is the only one where both the quantity and the unit are exactly as listed for the SI base set?"],
    options={"A": "mass, gram", "B": "time, second", "C": "current, coulomb", "D": "temperature, degree Celsius"},
    answer="B", distractors={"A": "m1", "C": "m2"})
gen([K1, K4], "mcq", 2, "Identify", "A student needs to use a mass of 350 g in an equation that requires SI base units. Which value should be substituted?",
    1, "The SI base unit of mass is the kilogram, so $350\\ \\mathrm{g}=350\\times10^{-3}\\ \\mathrm{kg}=0.350\\ \\mathrm{kg}$. Substituting 350 treats the gram as the base unit; 3.5 kg applies the wrong power of ten.",
    ["Which unit of mass do SI equations assume?",
     "The gram is not the SI base unit of mass; one gram is a fraction of it.",
     "Divide the number of grams by the number of grams in one kilogram."],
    options={"A": "350 (as the number)", "B": "0.350 kg", "C": "3.5 kg", "D": "35 kg"},
    answer="B", distractors={"A": "m1", "C": "m5", "D": "m5"})
gen([K1], "short", 1, "State", "State the five SI base quantities used in AS Physics, and give the SI base unit of each.",
    5, "Mass (kg), length (m), time (s), current (A) and temperature (K) are the base quantities; every other unit is derived from them.",
    ["Think of the quantities measured in a simple electrical and mechanical experiment, plus temperature.",
     "Pair each with a unit: two are named after people (one for electricity, one for temperature).",
     "Mass, length and time first; then the two remaining quantities, one of them electrical."],
    rubric=[{"point": "mass, kilogram (kg)", "keywords": [["mass"], ["kilogram", "kg"]]},
            {"point": "length, metre (m)", "keywords": [["length"], ["metre", "meter"]]},
            {"point": "time, second (s)", "keywords": [["time"], ["second"]]},
            {"point": "current, ampere (A)", "keywords": [["current"], ["ampere", "amp"]]},
            {"point": "temperature, kelvin (K)", "keywords": [["temperature"], ["kelvin"]]}])
gen([K1], "mcq", 3, "Identify", "Which statement is correct?", 1,
    "The kelvin is the SI base unit of temperature. The second is a unit (the base quantity is time), the gram is a thousandth of the base unit of mass, and the coulomb is a derived unit because $\\mathrm{C}=\\mathrm{A\\,s}$.",
    ["Sort each statement into: quantity or unit; base or derived.",
     "A base unit is one of the small set of SI units that everything else is built from.",
     "Look for the statement that names a unit and does not confuse it with a quantity or a derived unit."],
    options={"A": "The second is an SI base quantity.", "B": "The gram is the SI base unit of mass.",
             "C": "The coulomb is an SI base unit.", "D": "The kelvin is the SI base unit of temperature."},
    answer="D", distractors={"A": "m2", "B": "m1", "C": "m2"})
gen([K1], "structured", 4, "Explain",
     "A student writes: \"The SI base unit of mass is the gram and the SI base unit of charge is the coulomb.\" (a) Correct the statement about mass. [1] (b) Explain why the coulomb is not an SI base unit. [2]",
     3, "The base unit of mass is the kilogram. Charge is not a base quantity: the coulomb is derived from the base units ampere and second as $\\mathrm{C}=\\mathrm{A\\,s}$.",
     ["Which prefix does the SI base unit of mass carry?",
      "A base unit belongs to one of the base quantities; is charge among them?",
      "Charge $=$ current $\\times$ time; write the unit of that product."],
     scheme=[{"mark": "B1", "point": "(a) The SI base unit of mass is the kilogram (not the gram)"},
             {"mark": "B1", "point": "(b) Charge is not a base quantity / the coulomb is a derived unit"},
             {"mark": "B1", "point": "(b) The coulomb is defined in terms of base units: 1 C = 1 A s (current x time)"}])

# ---- 1.2.2
gen([K2], "numeric", 3, "Determine",
    "A quantity $Q$ is calculated using $Q=\\tfrac12\\rho v^{[[n]]}$, where $\\rho$ is density and $v$ is speed. Determine the power of $\\mathrm{m}$ in the SI base units of $Q$.",
    1, "$\\rho$ has base units $\\mathrm{kg\\,m^{-3}}$ and $v^n$ has $\\mathrm{m^{n}\\,s^{-n}}$, so the power of m in $Q$ is $-3+n$. The $\\tfrac12$ has no units.",
    ["Write the base units of density, then those of $v^n$; the number $\\tfrac12$ has none.",
     "Multiply the two sets of units, adding the powers of each base unit.",
     "Density contributes a negative power of m and each factor of speed contributes a positive one."],
    template={"params": {"n": {"choices": [2, 3, 4]}}, "answer": "n - 3",
              "distractors": [{"expr": "n + 3", "misconception": "m3"}, {"expr": "n", "misconception": "m3"}]},
    answer={"unit": "", "exact": True})
gen([K2], "mcq", 3, "Identify", "Which unit is **not** equivalent to the joule?", 1,
    "$\\mathrm{N\\,m}$, $\\mathrm{W\\,s}$ and $\\mathrm{kg\\,m^2\\,s^{-2}}$ are all equal to the joule ($\\mathrm{J}=\\mathrm{N\\,m}$, energy $=$ power $\\times$ time). $\\mathrm{N\\,s}=\\mathrm{kg\\,m\\,s^{-1}}$ is the unit of momentum and impulse, so it has one fewer power of m and one fewer power of s.",
    ["Convert every option to base units.",
     "Work $=$ force $\\times$ distance; energy $=$ power $\\times$ time.",
     "Three options end up as $\\mathrm{kg\\,m^2\\,s^{-2}}$; one does not."],
    options={"A": "N m", "B": "W s", "C": "kg m² s⁻²", "D": "N s"}, answer="D", distractors={})
gen([K2], "structured", 4, "Show that", "Show that the SI base units of the pascal are $\\mathrm{kg\\,m^{-1}\\,s^{-2}}$.", 3,
    "Pressure is force per unit area, so $\\mathrm{Pa}=\\mathrm{N\\,m^{-2}}$; with $\\mathrm{N}=\\mathrm{kg\\,m\\,s^{-2}}$ this gives $\\mathrm{kg\\,m\\,s^{-2}}\\div\\mathrm{m^2}=\\mathrm{kg\\,m^{-1}\\,s^{-2}}$.",
    ["Start from how pressure is defined.", "Use $F=ma$ to write the newton in base units.",
     "Divide the base units of force by $\\mathrm{m^2}$."],
    scheme=[{"mark": "M1", "point": "Pressure = force / area, so pascal = N m^-2"},
            {"mark": "A1", "point": "Newton in base units: N = kg m s^-2 (from F = ma)"},
            {"mark": "A1", "point": "Substitution: kg m s^-2 / m^2 = kg m^-1 s^-2"}])

# ---- 1.2.3
gen([K3, K2], "numeric", 3, "Determine",
    "Air resistance on a cyclist is modelled by $F=kv^{[[n]]}$, where $F$ is the resistive force and $v$ is the speed. Determine the power of $\\mathrm{m}$ in the SI base units of $k$.",
    1, "$k=F/v^n$. $F$ has base units $\\mathrm{kg\\,m\\,s^{-2}}$ and $v^n$ has $\\mathrm{m^{n}\\,s^{-n}}$, so the power of m in $k$ is $1-n$.",
    ["Make $k$ the subject of the equation.",
     "Write $F$ and $v^n$ in base units, then divide.",
     "Dividing subtracts powers: take the power of m in $F$ and subtract the power of m in $v^n$."],
    template={"params": {"n": {"choices": [2, 3, 4]}}, "answer": "1 - n",
              "distractors": [{"expr": "n - 1", "misconception": "m3"}, {"expr": "n", "misconception": "m3"}]},
    answer={"unit": "", "exact": True})
gen([K3], "mcq", 3, "Identify", "Which equation is homogeneous? ($s$ is distance, $u$ and $v$ are speeds, $a$ is acceleration, $t$ is time.)", 1,
    "$s=ut+\\tfrac12at^2$: each term has base unit $\\mathrm{m}$ (since $\\mathrm{m\\,s^{-2}}\\times\\mathrm{s^2}=\\mathrm{m}$). In A, $\\tfrac12at$ is in $\\mathrm{m\\,s^{-1}}$; in B, $at^2$ is in m rather than $\\mathrm{m\\,s^{-1}}$; in D, $2as^2$ is in $\\mathrm{m^3\\,s^{-2}}$ but $v^2$ is in $\\mathrm{m^2\\,s^{-2}}$.",
    ["Find the base units of every term, not just one side.",
     "Terms added or subtracted must all have the same base units as the other side.",
     "Multiplying acceleration by $t^2$ turns $\\mathrm{s^{-2}}$ into $\\mathrm{s^{0}}$."],
    options={"A": "$s=ut+\\tfrac12at$", "B": "$v=u+at^2$", "C": "$s=ut+\\tfrac12at^2$", "D": "$v^2=u^2+2as^2$"},
    answer="C", distractors={})
gen([K3], "mcq", 3, "Comment",
    "A student checks that an equation is homogeneous and concludes that it must be correct. Which comment is correct?", 1,
    "Homogeneity is necessary, not sufficient: it only compares base units, so a wrong numerical factor such as $\\tfrac12$ or $2\\pi$ (which has no units) is not detected. For example $E_k=mv^2$ and $E_k=\\tfrac12mv^2$ are both homogeneous, but only one is right.",
    ["Homogeneous means the base units match on both sides. Does that test every part of the equation?",
     "Think of factors such as $\\tfrac12$, $2\\pi$ or $4\\pi^2$: what base units do they have?",
     "A wrong coefficient leaves the base units unchanged."],
    options={"A": "Correct: an equation with the same units on both sides must be right.",
             "B": "Not necessarily: homogeneity does not test numerical factors such as $\\tfrac12$ or $2\\pi$.",
             "C": "Incorrect: homogeneity tests only the numbers, not the units.",
             "D": "Correct, provided both sides contain the same number of terms."},
    answer="B", distractors={"A": "m4", "D": "m4"})
gen([K3], "short", 3, "Explain",
    "Explain what is meant by an equation being homogeneous, and why showing that an equation is homogeneous does not prove that it is correct.", 2,
    "An equation is homogeneous when every term on both sides has the same base units. It can still be wrong because factors with no units (such as $\\tfrac12$ or $2\\pi$) are not tested by the check.",
    ["Compare what you check (units) with what you cannot check (numbers).",
     "Say what must be true of every term when an equation is homogeneous.",
     "Give an example of a factor that has no base units."],
    rubric=[{"point": "Homogeneous: all terms / both sides have the same base units",
             "keywords": [["both sides", "each term", "all terms", "every term"], ["same"], ["units", "dimensions"]]},
            {"point": "Numerical constants / factors with no units are not tested, so the equation could still be wrong",
             "keywords": [["numerical", "number", "constant", "factor", "coefficient", "dimensionless", "no units"],
                          ["not", "cannot", "does not", "unable", "no way"]]}])
gen([K3, K2], "structured", 5, "Show that",
    "The frequency $f$ of vibration of a stretched string of length $L$, tension $T$ and mass per unit length $\\mu$ is given by $f=\\dfrac{1}{2L}\\sqrt{\\dfrac{T}{\\mu}}$. Show that the equation is homogeneous.", 4,
    "$T/\\mu$ has base units $\\mathrm{kg\\,m\\,s^{-2}}\\div\\mathrm{kg\\,m^{-1}}=\\mathrm{m^2\\,s^{-2}}$, so $\\sqrt{T/\\mu}$ is in $\\mathrm{m\\,s^{-1}}$; dividing by $L$ gives $\\mathrm{s^{-1}}$, which is the unit of frequency, and the $2$ has no units.",
    ["List the base units of each quantity on the right-hand side.", "Tension is a force and $\\mu$ is mass divided by length.",
     "Combine $T$ and $\\mu$ inside the square root first, then take the root, then divide by $L$."],
    scheme=[{"mark": "B1", "point": "Tension is a force: T has base units kg m s^-2"},
            {"mark": "B1", "point": "mu has base units kg m^-1"},
            {"mark": "M1", "point": "T/mu has units m^2 s^-2, so sqrt(T/mu) has units m s^-1"},
            {"mark": "A1", "point": "(1/L) sqrt(T/mu) has units s^-1, the unit of frequency; factor 2 has no units, so homogeneous"}])

# ---- 1.2.4
gen([K4], "numeric", 3, "Calculate", "A wire has a cross-sectional area of [[a]] mm². Express this area in m².", 1,
    "$1\\ \\mathrm{mm}=10^{-3}\\ \\mathrm{m}$, so $1\\ \\mathrm{mm^2}=(10^{-3}\\ \\mathrm{m})^2=10^{-6}\\ \\mathrm{m^2}$. The prefix must be squared with the unit.",
    ["Start from the length conversion for one millimetre.",
     "The unit is squared, so the conversion factor must be squared as well.",
     "Multiply the number of square millimetres by the conversion factor for one square millimetre."],
    template={"params": {"a": {"choices": [0.5, 0.75, 1.2, 2.4, 3.6]}}, "answer": "a * 1e-6",
              "distractors": [{"expr": "a * 1e-3", "misconception": "m5"}, {"expr": "a * 1e6", "misconception": "m5"}]},
    answer={"unit": "m^2", "sf_ok": [1, 2, 3]})
gen([K4], "numeric", 4, "Calculate",
    "A potential difference of [[v]] V is applied across a resistor of resistance [[r]] GΩ. Calculate the current in the resistor in pA.", 2,
    "$I=V/R=V/(r\\times10^{9}\\ \\Omega)$, which is $(V/r)\\times10^{-9}\\ \\mathrm{A}$. Since $1\\ \\mathrm{pA}=10^{-12}\\ \\mathrm{A}$, the current is $(V/r)\\times10^{3}\\ \\mathrm{pA}$.",
    ["Write the resistance in ohms and use $I=V/R$.",
     "giga is $10^{9}$ and pico is $10^{-12}$; convert to amperes first, then to picoamperes.",
     "Each ampere is a very large number of picoamperes, so the answer in pA is a large number."],
    template={"params": {"v": {"choices": [10, 20, 40]}, "r": {"choices": [2, 4, 5, 8]}}, "answer": "v / r * 1e3",
              "distractors": [{"expr": "v / r * 1e6", "misconception": "m5"}, {"expr": "v / r * 1e-9", "misconception": "m5"}]},
    answer={"unit": "pA", "sf_ok": [2, 3, 4]})
gen([K4], "mcq", 2, "Identify", "Which list is in order of increasing length?", 1,
    "In metres: pm is $10^{-12}$, nm is $10^{-9}$, μm is $10^{-6}$ and mm is $10^{-3}$, so the order of increasing length is pm, nm, μm, mm. Swapping pico and nano, or putting μm before nm, confuses the powers of ten.",
    ["Convert each unit to metres using its prefix.",
     "The more negative the power of ten, the smaller the length.",
     "The smallest prefix here is pico; the largest is milli."],
    options={"A": "1 pm, 1 nm, 1 μm, 1 mm", "B": "1 nm, 1 pm, 1 mm, 1 μm", "C": "1 mm, 1 μm, 1 nm, 1 pm",
             "D": "1 pm, 1 μm, 1 nm, 1 mm"}, answer="A", distractors={"B": "m5", "D": "m5"})

# ---------- numeric verification of templates ----------
for n in (2, 3, 4):
    Q = mul(div(KG, pw(M, 3)), pw(div(M, S), n))
    assert Q[DIMS.index("m")] == n - 3
    k = div(N, pw(div(M, S), n))
    assert k[DIMS.index("m")] == 1 - n
    assert (n + 3, n) != (1 - n, 1 - n)
assert all(abs(v / r * 1e3 - v / (r * 1e9) / 1e-12) < 1e-6 for v in (10, 20, 40) for r in (2, 4, 5, 8))

# ---------- worked examples ----------
worked = [
    {"id": "we1", "kc": K2,
     "problem": "Determine the SI base units of the volt, given that the potential difference is the energy transferred per unit charge, $V=\\dfrac{W}{Q}$.",
     "steps": [
         {"do": "State the definition in units: $\\mathrm{V}=\\mathrm{J\\,C^{-1}}$.",
          "why": "Every derived unit starts from a defining equation; write it before substituting anything."},
         {"do": "Write the joule in base units: $\\mathrm{J}=\\mathrm{N\\,m}=\\mathrm{kg\\,m\\,s^{-2}}\\times\\mathrm{m}=\\mathrm{kg\\,m^{2}\\,s^{-2}}$, so the power of s in J is $-2$.",
          "why": "Energy is force times distance and the newton is $\\mathrm{kg\\,m\\,s^{-2}}$; forgetting the extra m from the distance is a common slip.",
          "check": {"kind": "numeric", "answer": {"value": -2, "unit": "", "exact": True}}},
         {"do": "Write the coulomb in base units: $\\mathrm{C}=\\mathrm{A\\,s}$ (charge is current times time).",
          "why": "The coulomb is not a base unit; it must be replaced by base units before dividing."},
         {"do": "Divide: $\\mathrm{V}=\\dfrac{\\mathrm{kg\\,m^{2}\\,s^{-2}}}{\\mathrm{A\\,s}}=\\mathrm{kg\\,m^{2}\\,s^{-3}\\,A^{-1}}$, so the power of s is $-3$.",
          "why": "Dividing by a unit subtracts its power; the second in the coulomb adds a further $-1$ to the $-2$.",
          "check": {"kind": "numeric", "answer": {"value": -3, "unit": "", "exact": True}}}],
     "faded": {"id": "we1f",
               "problem": "The ohm is defined by $R=V/I$. The SI base units of the ohm are $\\mathrm{kg\\,m^{2}\\,s^{-3}\\,A^{n}}$. Determine $n$.",
               "answer": {"value": -2, "unit": "", "exact": True}, "blank_from": 1}},
    {"id": "we2", "kc": K3,
     "problem": "The speed $v$ of a wave in shallow water of depth $h$ is $v=Cg^{a}h^{b}$, where $C$ is a number with no units and $g$ is the acceleration of free fall. Use base units to find $a$ and $b$.",
     "steps": [
         {"do": "Write the base units: $v$ is $\\mathrm{m\\,s^{-1}}$, $g$ is $\\mathrm{m\\,s^{-2}}$ and $h$ is $\\mathrm{m}$; $C$ has none.",
          "why": "Homogeneity compares base units, and a pure number has none, so it drops out of the check."},
         {"do": "Right-hand side: $g^{a}h^{b}$ has units $\\mathrm{m^{a+b}\\,s^{-2a}}$.",
          "why": "Powers of the same base unit add when quantities are multiplied."},
         {"do": "Equate the powers of s: $-2a=-1$, so $a=0.5$.",
          "why": "Each base unit must match separately; time appears only in $g$, so start with s.",
          "check": {"kind": "numeric", "answer": {"value": 0.5, "unit": "", "exact": True}}},
         {"do": "Equate the powers of m: $a+b=1$, so $b=0.5$.",
          "why": "Use the value of $a$ already found; then $v=C\\sqrt{gh}$.",
          "check": {"kind": "numeric", "answer": {"value": 0.5, "unit": "", "exact": True}}}],
     "faded": {"id": "we2f",
               "problem": "The frequency $f$ of a mass $m$ on a spring of spring constant $k$ (unit $\\mathrm{N\\,m^{-1}}$) is $f=Cm^{a}k^{b}$ with $C$ a pure number. Use base units to find $a$.",
               "answer": {"value": -0.5, "unit": "", "exact": True}, "blank_from": 1}},
]
# verify worked answers
assert J[DIMS.index("s")] == -2 and VOLT[DIMS.index("s")] == -3 and OHM[DIMS.index("A")] == -2
a_, b_ = sp.symbols("a b")
assert sp.solve([-2 * a_ + 1, a_ + b_ - 1], [a_, b_]) == {a_: sp.Rational(1, 2), b_: sp.Rational(1, 2)}
kspr = div(N, M)  # kg s^-2
sfa = sp.solve([sp.Symbol("x") + sp.Symbol("y"), -2 * sp.Symbol("y") + 1], [sp.Symbol("x"), sp.Symbol("y")])  # kg: a+b=0; s: -2b=-1
assert kspr == V(kg=1, s=-2) and sfa[sp.Symbol("x")] == -sp.Rational(1, 2)

# ---------- misconceptions ----------
mis = [
    {"id": "m1", "kc": K1, "statement": "The gram is the SI base unit of mass.",
     "refutation": "The SI base unit of mass is the kilogram. The gram is $10^{-3}$ of a kilogram, so a mass given in grams must be converted before it is used in an equation that needs SI base units.",
     "contrast": "For $350\\ \\mathrm{g}$ in $E_k=\\tfrac12mv^2$, use $m=0.350\\ \\mathrm{kg}$, not 350.",
     "source": "ER 9702 s19 P13 Q1"},
    {"id": "m2", "kc": K1, "statement": "Quantities and units are the same thing: 'second' is a base quantity, or 'coulomb' or 'ampere' are interchangeable with charge and current.",
     "refutation": "A quantity is what is measured (time, current); a unit is the agreed size used to measure it (second, ampere). Charge is not a base quantity; its unit the coulomb is derived as $\\mathrm{A\\,s}$.",
     "contrast": "Time is the base quantity and the second is its base unit; current is the base quantity and the ampere is its base unit; charge $=$ current $\\times$ time has the derived unit coulomb.",
     "source": "ER 9702 w23 P12 Q2"},
    {"id": "m3", "kc": K2, "statement": "Slips when building base units: dropping a factor or getting a sign wrong, e.g. giving the watt as $\\mathrm{kg\\,m^2\\,s^{-1}}$ or the pascal as $\\mathrm{kg\\,m\\,s^{-2}}$.",
     "refutation": "Substitute step by step and keep every power: $\\mathrm{W}=\\mathrm{J\\,s^{-1}}=\\mathrm{kg\\,m^2\\,s^{-2}}\\times\\mathrm{s^{-1}}=\\mathrm{kg\\,m^2\\,s^{-3}}$, and dividing by an area subtracts 2 from the power of m.",
     "contrast": "$\\mathrm{kg\\,m\\,s^{-2}}$ is the newton (force); the pascal is force per area, $\\mathrm{kg\\,m^{-1}\\,s^{-2}}$.",
     "source": "research"},
    {"id": "m4", "kc": K3, "statement": "If an equation is homogeneous it must be correct.",
     "refutation": "Homogeneity only checks that the base units on both sides match. It cannot detect a wrong numerical factor such as $\\tfrac12$ or $2\\pi$, which has no units. A non-homogeneous equation is certainly wrong; a homogeneous one may be.",
     "contrast": "$E_k=mv^2$ and $E_k=\\tfrac12mv^2$ are both homogeneous, but only the second is correct.",
     "source": "research"},
    {"id": "m5", "kc": K4, "statement": "Power-of-ten errors with prefixes: mixing up micro, nano and pico, taking a giga as $10^{6}$, or applying a prefix once to a squared unit ($1\\ \\mathrm{mm^2}=10^{-3}\\ \\mathrm{m^2}$).",
     "refutation": "Replace the prefix by its power of ten and apply the power of the unit to the whole thing: $1\\ \\mathrm{mm^2}=(10^{-3}\\ \\mathrm{m})^2=10^{-6}\\ \\mathrm{m^2}$.",
     "contrast": "$1\\ \\mathrm{G\\Omega}=10^{9}\\ \\Omega$ (not $10^{6}$) and $1\\ \\mathrm{pA}=10^{-12}\\ \\mathrm{A}$ (not $10^{-9}$).",
     "source": "ER 9702 s19 P23 Q1"},
]

# ---------- flashcards ----------
fcs = []


def fc(kc, front, back):
    fcs.append({"id": f"fc{len(fcs) + 1}", "kc": kc, "front": front, "back": back})


for qn, un in [("mass", "kilogram (kg)"), ("length", "metre (m)"), ("time", "second (s)"),
               ("current", "ampere (A)"), ("thermodynamic temperature", "kelvin (K)")]:
    fc(K1, f"What is the SI base unit of {qn}?", un)
fc(K1, "Is the gram the SI base unit of mass?", "No. The SI base unit of mass is the kilogram; the gram is $10^{-3}$ of it.")
fc(K1, "Is charge an SI base quantity? What is its unit in base units?", "No. Charge is a derived quantity. The coulomb is $\\mathrm{A\\,s}$ (current $\\times$ time).")
for name, v, txt in [("newton (N)", N, "$\\mathrm{N}=\\mathrm{kg\\,m\\,s^{-2}}$"), ("joule (J)", J, ""), ("watt (W)", W, ""),
                     ("pascal (Pa)", PA, ""), ("volt (V)", VOLT, ""), ("ohm (Ω)", OHM, "")]:
    fc(K2, f"Express the {name} in SI base units.", f"{fmt(v)}")
fc(K3, "What is meant by a homogeneous equation?", "An equation in which every term on both sides has the same SI base units.")
fc(K3, "Why does a homogeneous equation not have to be correct?", "The check only compares base units, so it cannot detect wrong numerical factors (such as $\\tfrac12$ or $2\\pi$), which have no units.")
for name, sym, power in [("pico", "p", -12), ("nano", "n", -9), ("micro", "μ", -6), ("milli", "m", -3), ("centi", "c", -2),
                         ("deci", "d", -1), ("kilo", "k", 3), ("mega", "M", 6), ("giga", "G", 9), ("tera", "T", 12)]:
    fc(K4, f"SI prefix {name}: symbol and power of ten?", f"{sym}, $10^{{{power}}}$")
fc(K4, "What is $1\\ \\mathrm{mm^2}$ in $\\mathrm{m^2}$?", "$10^{-6}\\ \\mathrm{m^2}$: the prefix is squared with the unit, $(10^{-3}\\ \\mathrm{m})^2$.")

outline = ("SI has five base quantities at AS: mass (kg), length (m), time (s), current (A) and temperature (K). Every other unit is derived by multiplying and dividing them. "
           "Write a derived unit in base units by substituting definitions: $\\mathrm{N}=\\mathrm{kg\\,m\\,s^{-2}}$, $\\mathrm{J}=\\mathrm{N\\,m}=\\mathrm{kg\\,m^2\\,s^{-2}}$, "
           "$\\mathrm{W}=\\mathrm{J\\,s^{-1}}=\\mathrm{kg\\,m^2\\,s^{-3}}$, $\\mathrm{Pa}=\\mathrm{N\\,m^{-2}}=\\mathrm{kg\\,m^{-1}\\,s^{-2}}$. "
           "An equation is homogeneous if every term has the same base units; factors such as $\\tfrac12$ and $2\\pi$ have none. Homogeneity can expose a wrong equation and find unknown powers, but cannot prove an equation right. "
           "Prefixes scale a unit: p $10^{-12}$, n $10^{-9}$, μ $10^{-6}$, m $10^{-3}$, c $10^{-2}$, d $10^{-1}$, k $10^{3}$, M $10^{6}$, G $10^{9}$, T $10^{12}$. "
           "A prefix on a squared unit is squared too, and masses go into kg.")

pack = {"subtopic": SUB, "spec": "9702", "version": 1,
        "note": "Subjects/9702 Physics/01 Physical quantities and units/1.2 SI units.md",
        "outline": outline, "misconceptions": mis, "worked": worked, "items": items, "flashcards": fcs, "diagrams": []}
out = ROOT / "build/out/packs/9702/9702-1.2.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(pack, ensure_ascii=False, indent=1))
print("wrote", out, len(items), "items", len(fcs), "cards", len(outline.split()), "outline words")
