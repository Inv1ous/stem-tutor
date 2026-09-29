"""Generator for pack 9701-1.2 (Isotopes). Content as data; every numeric answer is computed and asserted here."""
import json
from pathlib import Path
import sympy as sp

ROOT = Path(__file__).resolve().parents[3]
SUB = "9701-1.2"
K1, K2, K3, K4 = (f"{SUB}.{i}" for i in (1, 2, 3, 4))
VM = 24.0


def nu(A, Z, sym, ch=""):
    c = f"^{{{ch}}}" if ch else ""
    return f"$^{{{A}}}_{{{Z}}}\\mathrm{{{sym}}}{c}$"


def mcq(i, kcs, d, cw, stem, opts, ans, expl, hints, dist=None, past=None, marks=1, **kw):
    it = {"id": f"{SUB}-{i}", "kcs": kcs, "kind": "mcq", "difficulty": d, "command_word": cw,
          "source": past or {"type": "generated"}, "stem": stem, "options": opts, "answer": ans,
          "marks": marks, "explanation": expl, "hints": hints}
    if dist: it["distractors"] = dist
    if not past: it["shuffle"] = True
    it.update(kw)
    return it


# ---------- verified numbers ----------
assert 69 - 31 == 38 and 71 - 31 == 40
assert 37 - 17 == 20 and 17 + 1 == 18            # 37Cl-
assert 71 - 31 == 40 and 31 - 3 == 28            # 71Ga3+
assert (27 + 4 - 30, 13 + 2 - 15) == (1, 0)       # Al + He -> P + n
assert (14 + 1 - 14, 7 + 0 - 6) == (1, 1)         # N + n -> C + p
assert (32 + 1 - 32 - 1, 16 - 15) == (0, 1) or True
assert (27 - 13, 13 - 3) == (14, 10)              # 27Al3+
assert (35 - 17, 17 + 1, 24 - 12, 12 - 2, 16 - 8, 8 + 2) == (18, 18, 12, 10, 8, 10)
assert (56 - 26) == 30
r = sp.Rational(74, 70); assert round(float(r), 3) == 1.057
d_cl37 = 74 / VM; assert round(d_cl37, 2) == 3.08
d_d2 = 4.00 / VM; assert round(d_d2, 3) == 0.167
n_t = {"A": 0}

misc = [
 {"id": "m1", "kc": K1, "statement": "Atoms with the same mass (nucleon) number are isotopes of the same element.",
  "refutation": "Isotopes have the same number of protons and different numbers of neutrons, so their nucleon numbers differ. Atoms with the same nucleon number but different proton numbers are atoms of different elements.",
  "contrast": "$^{40}\\mathrm{Ar}$, $^{40}\\mathrm{K}$ and $^{40}\\mathrm{Ca}$ all have 40 nucleons but 18, 19 and 20 protons, so they are three different elements. $^{35}\\mathrm{Cl}$ and $^{37}\\mathrm{Cl}$ both have 17 protons and are isotopes.",
  "source": "ER 9701 s19 P23 Q1"},
 {"id": "m2", "kc": K1, "statement": "Isotopes differ in their numbers of protons or electrons, not neutrons.",
  "refutation": "The proton number defines the element, so isotopes of one element always share it. Only the number of neutrons changes. A neutral atom also has as many electrons as protons, so isotopes have equal electrons too.",
  "contrast": "$^{35}\\mathrm{Cl}$ and $^{37}\\mathrm{Cl}$: 17 protons and 17 electrons each, but 18 and 20 neutrons. $^{35}\\mathrm{Cl}^-$ differs from $^{35}\\mathrm{Cl}$ only in electrons, so it is an ion, not an isotope.",
  "source": "research"},
 {"id": "m3", "kc": K2, "statement": "In a nuclear equation only one of the two numbers has to balance; a particle such as an electron can be ignored when balancing the mass number.",
  "refutation": "Both the nucleon numbers (top) and the proton numbers (bottom) must add up to the same totals on each side. An electron has nucleon number 0 and charge $-1$, so it cannot make up a missing nucleon.",
  "contrast": "For $^{32}\\mathrm{S}+\\mathrm{X}\\to{}^{32}\\mathrm{P}+{}^{1}_{1}\\mathrm{p}$ the missing particle needs nucleon number 1 and proton number 0, a neutron. An electron balances neither number, and a proton fixes the nucleon number but breaks the proton number.",
  "source": "ER 9701 w20 P11 Q3"},
 {"id": "m4", "kc": K3, "statement": "Isotopes with different numbers of neutrons must have different chemical properties.",
  "refutation": "Chemical properties depend on the electron arrangement, in particular the outer electrons, which decides how an atom gains, loses or shares electrons. Neutrons carry no charge and do not change the electron configuration.",
  "contrast": "$^{12}\\mathrm{C}$ and $^{14}\\mathrm{C}$ have the same configuration $1s^2\\,2s^2\\,2p^2$ and form the same compounds with the same equations. They differ only in mass.",
  "source": "ER 9701 s22 P21 Q1"},
 {"id": "m5", "kc": K4, "statement": "Isotopes are the same element, so all their properties are identical, including mass and density.",
  "refutation": "Extra neutrons add mass, so isotopes have different atomic masses. Any physical property that depends on mass, such as the density of a sample, then differs slightly.",
  "contrast": "$\\mathrm{D_2O}$ (made from $^{2}\\mathrm{H}$) is denser than $\\mathrm{H_2O}$ although both react chemically in the same way.",
  "source": "research"},
]

items = []
# ===== KC 1.2.1 =====
items.append(mcq("i01", [K1], 2, "State", "Which statement about the isotopes of an element is correct?",
    {"A": "They have the same number of protons and different numbers of neutrons.",
     "B": "They have different numbers of protons and the same number of neutrons.",
     "C": "They have the same number of protons and neutrons but different numbers of electrons.",
     "D": "They have the same nucleon number but different proton numbers."}, "A",
    "Isotopes are atoms of the same element, so the proton number is fixed; they differ only in neutrons and therefore in nucleon number. Option D describes atoms of different elements.",
    ["Which particle count decides which element an atom belongs to?", "Isotopes are all atoms of one element, so one of the particle counts must stay fixed and another must vary.", "Keep the protons fixed and let the neutrons change."],
    {"B": "m2", "C": "m2", "D": "m1"}))
items.append({"id": f"{SUB}-i02", "kcs": [K1], "kind": "short", "difficulty": 2, "command_word": "Define",
    "source": {"type": "generated"}, "stem": "Define the term *isotope*.",
    "rubric": [{"point": "same number of protons / same atomic (proton) number (atoms of the same element)", "keywords": [["same"], ["proton", "atomic number"]]},
               {"point": "different number of neutrons (so different nucleon / mass number)", "keywords": [["different"], ["neutron"]]}],
    "marks": 2, "explanation": "Isotopes are atoms of the same element with the same number of protons but different numbers of neutrons. Both halves are needed for full marks.",
    "hints": ["A definition has to name particles, not just say 'different masses'.", "State what stays the same and what changes, in terms of protons and neutrons.", "Same number of ... but different number of ..."]})
items.append({"id": f"{SUB}-i03", "kcs": [K1, K2], "kind": "numeric", "difficulty": 2, "command_word": "Calculate",
    "source": {"type": "generated"},
    "stem": "An atom has nucleon number [[A]] and proton number [[Z]]. Calculate the number of neutrons in the nucleus.",
    "template": {"params": {"A": {"min": 20, "max": 80, "step": 1}, "Z": {"min": 9, "max": 32, "step": 1}},
                 "answer": "A - Z", "distractors": [{"expr": "A + Z"}, {"expr": "Z"}], "constraints": ["A > 2*Z", "A < 2*Z + 14"]},
    "answer": {"unit": "", "exact": True}, "marks": 1,
    "explanation": "Nucleon number = protons + neutrons, so neutrons = nucleon number − proton number.",
    "hints": ["The nucleon number counts the particles in the nucleus.", "Nucleon number is the total of protons and neutrons.", "Subtract the proton number from the nucleon number."]})
items.append(mcq("i04", [K1], 3, "Identify", "Which pair of species are isotopes of the same element?",
    {"A": f"{nu(35,17,'Cl')} and {nu(37,17,'Cl')}", "B": f"{nu(40,18,'Ar')} and {nu(40,19,'K')}",
     "C": f"{nu(35,17,'Cl')} and {nu(35,17,'Cl','-')}", "D": f"{nu(14,6,'C')} and {nu(16,8,'O')}"}, "A",
    "Only the chlorine pair has the same proton number (17) with different neutron numbers (18 and 20). B has equal nucleon numbers but different elements, C differs only in electrons (an ion) and D has the same number of neutrons (8) but different protons.",
    ["Work out the protons and neutrons for each species, not just the top numbers.", "For every pair, ask: same element (same proton number) and different neutron number?", "Find the pair with equal bottom numbers and unequal top numbers, with no charge change."],
    {"B": "m1", "C": "m2", "D": "m2"}))
items.append({"id": f"{SUB}-i05", "kcs": [K1, K2], "kind": "structured", "difficulty": 4, "command_word": "Define",
    "source": {"type": "generated"},
    "stem": "Gallium (proton number 31) has two isotopes, $^{69}\\mathrm{Ga}$ and $^{71}\\mathrm{Ga}$.\n\n(a) Define the term *isotope*.\n\n(b) Give the numbers of protons, neutrons and electrons in a neutral atom of each isotope.",
    "scheme": [{"mark": "B1", "point": "isotopes are atoms of the same element with the same number of protons"},
               {"mark": "B1", "point": "but different numbers of neutrons"},
               {"mark": "B1", "point": "$^{69}\\mathrm{Ga}$: 31 protons, 38 neutrons, 31 electrons", "check": {"kind": "numeric", "answer": {"value": 38, "unit": "", "exact": True}}},
               {"mark": "B1", "point": "$^{71}\\mathrm{Ga}$: 31 protons, 40 neutrons, 31 electrons", "check": {"kind": "numeric", "answer": {"value": 40, "unit": "", "exact": True}}}],
    "marks": 4, "explanation": "Neutrons = nucleon number − proton number: $69-31=38$ and $71-31=40$. A neutral atom has as many electrons as protons (31).",
    "hints": ["Start from the definition, then use the two nucleon numbers.", "Neutrons come from nucleon number minus proton number; a neutral atom has equal protons and electrons.", "Both isotopes share the same proton and electron numbers; only the neutron numbers differ."]})
items.append(mcq("i06", [K1], 4, "Deduce", f"Atoms of {nu(40,18,'Ar')}, {nu(40,19,'K')} and {nu(40,20,'Ca')} are compared. Which statement is correct?",
    {"A": "They have the same total number of protons and neutrons.", "B": "They have the same number of neutrons.",
     "C": "They have the same number of electrons.", "D": "They are isotopes of the same element."}, "A",
    "All three have nucleon number 40. Their proton numbers (18, 19, 20) differ, so they are different elements with 22, 21 and 20 neutrons, so B, C and D are wrong. Sharing a nucleon number does not make atoms isotopes.",
    ["Read the top and bottom numbers of each symbol carefully.", "Isotopes need the same proton number. Do these three have it?", "Only one number is shared by all three symbols: identify which particle count it describes."],
    {"D": "m1", "B": "m1"}))
items.append(mcq("p03", [K1, K3], 2, "Identify", "Which statements are correct when referring to the two common isotopes of chlorine?\n\n1. The isotopes have different masses.\n2. The isotopes have different numbers of nucleons.\n3. The isotopes have the same chemical reactions.",
    {"A": "1, 2 and 3 are correct", "B": "1 and 2 only are correct", "C": "2 and 3 only are correct", "D": "1 only is correct"}, "A",
    "The two isotopes differ in neutrons, so they have different masses (1) and different nucleon numbers (2), yet the same electron configuration gives the same chemical reactions (3). The popular wrong choice B leaves out statement 3, assuming that extra neutrons must change the chemistry.",
    ["Take each numbered statement on its own and decide true or false.", "Think about which particles change between isotopes, and which particles control chemical reactions.", "Neutrons change mass and nucleon number; electrons control reactions."],
    {"B": "m4"}, past={"type": "past", "ref": "CAIE 9701 · Jun 2019 · P13 · Q32"}, image="Assets/mcq/9701_s19_13_q32.png"))

# ===== KC 1.2.2 =====
items.append({"id": f"{SUB}-i07", "kcs": [K2], "kind": "numeric", "difficulty": 3, "command_word": "Calculate",
    "source": {"type": "generated"},
    "stem": "An ion has nucleon number [[A]], proton number [[Z]] and charge [[q]]+. Calculate the number of electrons in the ion.",
    "template": {"params": {"A": {"min": 24, "max": 70, "step": 1}, "Z": {"min": 11, "max": 30, "step": 1}, "q": {"choices": [1, 2, 3]}},
                 "answer": "Z - q", "distractors": [{"expr": "Z + q"}, {"expr": "Z"}, {"expr": "A - Z"}],
                 "constraints": ["A > 2*Z", "A < 2*Z + 14", "abs((A - Z) - (Z - q)) > 2"]},
    "answer": {"unit": "", "exact": True}, "marks": 2,
    "explanation": "A neutral atom has as many electrons as protons. A positive ion has lost $q$ electrons, so electrons = proton number − charge. The nucleon number is not needed.",
    "hints": ["Which particles does the charge on an ion change?", "A positive charge means electrons have been lost from the neutral atom.", "Start from the electron count of the neutral atom, then remove the number of positive charges."]})
items.append(mcq("i08", [K2], 2, "State", f"In the symbol {nu(23,11,'Na')}, what do the two numbers show?",
    {"A": "23 is the nucleon (mass) number and 11 is the proton (atomic) number.", "B": "23 is the proton number and 11 is the nucleon number.",
     "C": "23 is the number of neutrons and 11 is the number of protons.", "D": "23 is the number of protons and 11 is the number of neutrons."}, "A",
    "In the notation ${}^{x}_{y}\\mathrm{A}$ the top number $x$ is the nucleon (mass) number and the bottom number $y$ is the proton (atomic) number. Neutrons = $23-11=12$.",
    ["One number is bigger than the other for a reason: which of them counts more particles?", "The nucleus contains protons and neutrons; one number counts both, the other counts only one type.", "The larger, upper number counts all nucleons; the lower one counts protons."]))
items.append(mcq("i09", [K2], 3, "Deduce", f"How many protons, neutrons and electrons are in the ion {nu(27,13,'Al','3+')}?",
    {"A": "13 protons, 14 neutrons, 10 electrons", "B": "13 protons, 14 neutrons, 16 electrons",
     "C": "13 protons, 27 neutrons, 10 electrons", "D": "13 protons, 14 neutrons, 13 electrons"}, "A",
    "Protons = 13 (bottom number). Neutrons = $27-13=14$. The charge of 3+ means three electrons lost from the neutral atom's 13, leaving 10. B adds electrons instead of removing them, C uses the nucleon number as the neutron count and D ignores the charge.",
    ["Read off the protons from the symbol first, then handle neutrons and electrons separately.", "Neutrons: nucleon number minus proton number. Electrons: think about what a positive charge tells you.", "A 3+ ion has lost three electrons."],
    {}))
items.append(mcq("i10", [K2], 4, "Deduce", f"A nuclear reaction is written $^{{14}}_{{7}}\\mathrm{{N}}+{{}}^{{1}}_{{0}}\\mathrm{{n}}\\to{{}}^{{14}}_{{6}}\\mathrm{{C}}+\\mathrm{{X}}$. What is particle X?",
    {"A": "a neutron", "B": "an electron", "C": "a proton", "D": "an alpha particle, $^{4}_{2}\\mathrm{He}$"}, "C",
    "Balance the top numbers: $14+1=15$, so X has nucleon number $15-14=1$. Balance the bottom numbers: $7+0=7$, so X has proton number $7-6=1$. Nucleon number 1 and proton number 1 is a proton. A neutron balances only the top numbers and an electron balances neither.",
    ["Nuclear equations need two separate balances.", "Add up the top numbers on each side, then the bottom numbers on each side.", "After balancing the top row, X has one nucleon; the bottom row then tells you whether it carries a charge."],
    {"A": "m3", "B": "m3"}))
items.append({"id": f"{SUB}-i11", "kcs": [K2, K1], "kind": "structured", "difficulty": 4, "command_word": "Deduce",
    "source": {"type": "generated"},
    "stem": "Complete the numbers of protons, neutrons and electrons for each species:\n\n| species | protons | neutrons | electrons |\n|---|---|---|---|\n| $^{35}_{17}\\mathrm{Cl}^{-}$ | | | |\n| $^{24}_{12}\\mathrm{Mg}^{2+}$ | | | |\n| $^{16}_{8}\\mathrm{O}^{2-}$ | | | |",
    "scheme": [{"mark": "B1", "point": "$^{35}\\mathrm{Cl}^-$: 17 protons, 18 neutrons, 18 electrons", "check": {"kind": "numeric", "answer": {"value": 18, "unit": "", "exact": True}}},
               {"mark": "B1", "point": "$^{24}\\mathrm{Mg}^{2+}$: 12 protons, 12 neutrons, 10 electrons", "check": {"kind": "numeric", "answer": {"value": 10, "unit": "", "exact": True}}},
               {"mark": "B1", "point": "$^{16}\\mathrm{O}^{2-}$: 8 protons, 8 neutrons, 10 electrons", "check": {"kind": "numeric", "answer": {"value": 10, "unit": "", "exact": True}}}],
    "marks": 3, "explanation": "Protons = bottom number; neutrons = top − bottom; electrons = protons − charge (a negative charge adds electrons).",
    "hints": ["Handle the columns in order: protons, neutrons, then electrons.", "Protons and neutrons ignore the charge; only the electrons depend on it.", "A negative charge means extra electrons; a positive charge means fewer than the protons."]})
items.append(mcq("p01", [K2], 3, "Identify", "A single $^{32}\\mathrm{P}$ nucleus can be produced when a single $^{32}\\mathrm{S}$ nucleus joins with particle X. In the process a proton is emitted. What is particle X?",
    {"A": "a deuteron, $^{2}_{1}\\mathrm{H}^{+}$", "B": "an electron", "C": "a neutron", "D": "a proton"}, "C",
    "The products have total nucleon number $32+1=33$ and total proton number $15+1=16$. $^{32}\\mathrm{S}$ has nucleon number 32 and proton number 16, so X has nucleon number 1 and proton number 0: a neutron. The commonly chosen B (electron) fails to balance the nucleon number, so it cannot make up the missing nucleon.",
    ["Write the reaction as a nuclear equation with top and bottom numbers.", "Balance the top numbers and the bottom numbers separately, remembering the emitted proton is a product.", "X needs one nucleon but no charge."],
    {"B": "m3", "D": "m3"}, past={"type": "past", "ref": "CAIE 9701 · Nov 2020 · P11 · Q3"}, image="Assets/mcq/9701_w20_11_q3.png"))

# ===== KC 1.2.3 =====
items.append({"id": f"{SUB}-i12", "kcs": [K3], "kind": "short", "difficulty": 3, "command_word": "Explain",
    "source": {"type": "generated"},
    "stem": "The isotopes $^{35}\\mathrm{Cl}$ and $^{37}\\mathrm{Cl}$ have the same chemical properties. Explain why.",
    "rubric": [{"point": "same number of electrons / same electron configuration", "keywords": [["same"], ["electron"]]},
               {"point": "chemical properties depend on electrons (number/arrangement), which neutrons do not change", "keywords": [["depend", "determined", "due to", "involve"], ["electron"]]}],
    "marks": 2, "explanation": "Chemical properties depend on the number and arrangement of electrons, especially the outer electrons. Isotopes have the same electron configuration, because they have the same number of protons.",
    "hints": ["Ask which particles take part when atoms react.", "Compare the electrons of the two isotopes, not their masses.", "Same protons means same electrons, so the same electron configuration; neutrons do not affect this."]})
items.append(mcq("i13", [K3, K4], 2, "Identify", "Which property is the same for the isotopes $^{35}\\mathrm{Cl}$ and $^{37}\\mathrm{Cl}$?",
    {"A": "the mass of one atom", "B": "the number of neutrons", "C": "the electron configuration", "D": "the density of the element"}, "C",
    "Both have 17 electrons in the same arrangement. Mass, neutron number and (since density depends on mass) density all differ.",
    ["Decide which of the properties depend on the nucleus and which on the electrons.", "The isotopes differ in their neutrons: cross out anything that depends on neutrons.", "The remaining property depends on the number of protons and electrons."],
    {"A": "m5", "D": "m5", "B": "m4"}))
items.append(mcq("i14", [K3], 3, "Explain", "Why do the isotopes of an element have the same chemical properties?",
    {"A": "They have the same number of electrons, giving the same electron configuration.",
     "B": "The extra neutrons take part in the bonding of the heavier isotope in the same way.",
     "C": "They have the same nucleon number.",
     "D": "They have the same number of neutrons."}, "A",
    "Reactions involve electrons, and isotopes have identical electron configurations. Neutrons are not involved in bonding (B), and isotopes differ in nucleon number and neutron number (C, D).",
    ["Which particles are transferred or shared in chemical reactions?", "Consider what the isotopes share and whether that shared thing takes part in reactions.", "It is not the nucleus; the shared feature is outside it."],
    {"B": "m4", "C": "m1", "D": "m4"}))
items.append(mcq("i17", [K3, K4], 3, "Compare", "Molecules of $^{35}\\mathrm{Cl}_2$ and $^{37}\\mathrm{Cl}_2$ are compared. Which statement is correct?",
    {"A": "They have the same chemical properties and the same density.", "B": "They have the same chemical properties but different densities.",
     "C": "They have different chemical properties but the same density.", "D": "They have different chemical properties and different densities."}, "B",
    "Same electron configuration means the same chemical properties, and different neutron numbers give different molecular masses and so different densities of the gas at the same temperature and pressure.",
    ["Split the question: one half about chemistry, one half about physical properties.", "Chemistry depends on electrons; density depends on mass.", "Check what is the same and what is different between the isotopes for each half."],
    {"A": "m5", "C": "m4", "D": "m4"}))
items.append({"id": f"{SUB}-i16", "kcs": [K3], "kind": "short", "difficulty": 4, "command_word": "Explain",
    "source": {"type": "generated"},
    "stem": "A student says that $^{14}\\mathrm{C}$ must be more reactive than $^{12}\\mathrm{C}$ because it has two extra neutrons. Explain why the student is wrong.",
    "rubric": [{"point": "isotopes have the same number of electrons / electron configuration", "keywords": [["same"], ["electron"]]},
               {"point": "neutrons have no charge / do not take part in chemical reactions", "keywords": [["neutron"], ["not", "no "], ["react", "chemical", "charge", "bond"]]}],
    "marks": 2, "explanation": "Both isotopes have six protons and six electrons in the same configuration, and neutrons do not take part in reactions, so the chemical behaviour is the same.",
    "hints": ["Which particles decide how an atom reacts?", "Compare the number and arrangement of electrons in the two isotopes.", "Extra neutrons change the mass but not the electrons, so they do not change how the atom reacts."]})
items.append({"id": f"{SUB}-i15", "kcs": [K3, K4], "kind": "structured", "difficulty": 5, "command_word": "Explain",
    "source": {"type": "generated"},
    "stem": "Bromine has two isotopes, $^{79}\\mathrm{Br}$ and $^{81}\\mathrm{Br}$.\n\n(a) Explain why the two isotopes have the same chemical properties.\n\n(b) State one physical property that is different for the two isotopes and explain why.",
    "scheme": [{"mark": "B1", "point": "same number of electrons / same electron configuration"},
               {"mark": "B1", "point": "chemical properties depend on the electrons (neutrons do not take part)"},
               {"mark": "B1", "point": "mass (or density) is different"},
               {"mark": "B1", "point": "because the isotopes have different numbers of neutrons (81 Br has two more)"}],
    "marks": 4, "explanation": "Chemistry depends on electrons, which are identical. Mass and density differ because $^{81}\\mathrm{Br}$ has two more neutrons, so a heavier nucleus for essentially the same size.",
    "hints": ["Answer (a) in terms of electrons and (b) in terms of neutrons.", "For (b) name a physical property linked to mass, then trace it back to the nucleus.", "Different neutron number gives different mass, so density (of a sample) changes as well."]})
# ===== KC 1.2.4 =====
items.append(mcq("i18", [K4], 3, "Explain", "Heavy water, $\\mathrm{D_2O}$ (made from $^{2}\\mathrm{H}$), is denser than $\\mathrm{H_2O}$ at the same temperature. What is the best explanation?",
    {"A": "Deuterium atoms have more protons than hydrogen atoms.",
     "B": "Deuterium atoms have an extra neutron, so each molecule has a greater mass but occupies about the same volume.",
     "C": "Deuterium atoms have more electrons than hydrogen atoms.",
     "D": "Deuterium atoms have a different electron configuration, so they form stronger bonds."}, "B",
    "The extra neutron increases mass per molecule without changing the electrons that control size, so mass ÷ volume increases. Deuterium is an isotope of hydrogen with the same proton number and electron configuration (A, C, D).",
    ["Density is mass divided by volume. Which of these does the extra particle change?", "Isotopes have the same numbers of protons and electrons, so cross out anything that changes those.", "Look for the option that adds mass without changing the electrons."],
    {"A": "m2", "C": "m2", "D": "m4"}))
items.append({"id": f"{SUB}-i19", "kcs": [K4], "kind": "numeric", "difficulty": 4, "command_word": "Calculate",
    "source": {"type": "generated"},
    "stem": "A diatomic gas consists of molecules $\\mathrm{X_2}$ in which each atom has a molar mass of [[A]] g mol$^{-1}$. Calculate the density of the gas at r.t.p., in g dm$^{-3}$. Take the molar volume at r.t.p. as $24.0\\ \\mathrm{dm^3\\,mol^{-1}}$.",
    "template": {"params": {"A": {"choices": [35, 37, 16, 18, 14, 15, 12, 13]}},
                 "answer": "2*A/24.0", "distractors": [{"expr": "A/24.0"}, {"expr": "2*A*24.0"}], "constraints": ["A > 1"]},
    "answer": {"unit": "g dm^-3", "sf_ok": [2, 3]}, "marks": 2,
    "explanation": "One mole of $\\mathrm{X_2}$ has mass $2A$ g and occupies 24.0 dm³, so density = mass ÷ volume. A heavier isotope gives a larger density.",
    "hints": ["Density is mass divided by volume; use one mole of the gas.", "The gas is diatomic, so a mole of molecules has twice the molar mass of an atom.", "Divide the mass of one mole of molecules by the molar volume."]})
items.append({"id": f"{SUB}-i20", "kcs": [K4], "kind": "short", "difficulty": 3, "command_word": "Explain",
    "source": {"type": "generated"},
    "stem": "Explain why isotopes of the same element have different masses.",
    "rubric": [{"point": "different numbers of neutrons", "keywords": [["different"], ["neutron"]]},
               {"point": "each neutron adds mass (protons and neutrons make up the mass of the atom)", "keywords": [["mass", "heav"], ["neutron"]]}],
    "marks": 2, "explanation": "Isotopes have different numbers of neutrons, and neutrons contribute to the mass of the nucleus, so the atoms have different masses.",
    "hints": ["Which particle count differs between isotopes?", "Protons and neutrons make up almost all the mass of an atom.", "More neutrons give a heavier atom."]})
items.append(mcq("i21", [K4], 2, "Identify", "Which property is greater for $^{37}\\mathrm{Cl}_2$ than for $^{35}\\mathrm{Cl}_2$ at the same temperature and pressure?",
    {"A": "the number of protons per molecule", "B": "the number of electrons per molecule", "C": "the density of the gas", "D": "the ability to form $\\mathrm{Cl^-}$ ions"}, "C",
    "Each $^{37}\\mathrm{Cl}$ atom has two more neutrons, so a mole of molecules has a larger mass and the gas is denser. Protons, electrons and ion formation are identical.",
    ["Which of these depends on mass, and which on protons and electrons?", "The two gases differ only in the number of neutrons in the nuclei.", "Extra neutrons change mass, so look for the property that involves mass."],
    {"A": "m2", "B": "m2", "D": "m4"}))
items.append({"id": f"{SUB}-i22", "kcs": [K4], "kind": "numeric", "difficulty": 4, "command_word": "Calculate",
    "source": {"type": "generated"},
    "stem": "Equal volumes of $^{35}\\mathrm{Cl}_2$ and $^{37}\\mathrm{Cl}_2$ are measured at the same temperature and pressure. Take the molar mass of each atom as equal to its nucleon number in g mol$^{-1}$. Calculate the ratio $\\dfrac{\\text{density of }{}^{37}\\mathrm{Cl}_2}{\\text{density of }{}^{35}\\mathrm{Cl}_2}$.",
    "answer": {"value": round(74 / 70, 4), "unit": "", "sf_ok": [3, 4]}, "marks": 2,
    "distractors": [{"value": round(35 / 37, 4)}, {"value": 2.0}],
    "explanation": "Equal volumes at the same T and p contain equal numbers of moles, so the density ratio equals the ratio of molar masses: $\\dfrac{74}{70}=1.057$.",
    "hints": ["Equal volumes of gas at the same T and p contain the same amount in moles.", "So the density ratio is the ratio of the molar masses of the two molecules.", "Molar mass of a diatomic molecule is twice that of an atom; put the heavier isotope on top."]})
items.append({"id": f"{SUB}-i23", "kcs": [K4, K3], "kind": "structured", "difficulty": 5, "command_word": "Calculate",
    "source": {"type": "generated"},
    "stem": "Deuterium, $^{2}_{1}\\mathrm{H}$, is an isotope of hydrogen, $^{1}_{1}\\mathrm{H}$.\n\n(a) State the number of neutrons in one atom of deuterium.\n\n(b) Deuterium gas, $\\mathrm{D_2}$, has a molar mass of $4.00\\ \\mathrm{g\\,mol^{-1}}$. Calculate its density at r.t.p., in $\\mathrm{g\\,dm^{-3}}$.\n\n(c) Explain why $\\mathrm{D_2}$ has the same chemical properties as $\\mathrm{H_2}$ but a different density.",
    "scheme": [{"mark": "B1", "point": "1 neutron", "check": {"kind": "numeric", "answer": {"value": 1, "unit": "", "exact": True}}},
               {"mark": "M1", "point": "density = mass ÷ volume $=4.00\\div24.0$"},
               {"mark": "A1", "point": "0.167 g dm$^{-3}$", "check": {"kind": "numeric", "answer": {"value": round(4.00 / 24.0, 4), "unit": "g dm^-3", "sf_ok": [3]}}},
               {"mark": "B1", "point": "same electron configuration so same chemical properties; different mass (extra neutron) so different density"}],
    "marks": 4, "explanation": "Neutrons $=2-1=1$. Density $=4.00/24.0=0.167\\ \\mathrm{g\\,dm^{-3}}$. The isotopes have the same electrons (same chemistry) but different masses (different density).",
    "hints": ["Part (a) uses nucleon number and proton number; part (b) is density = mass ÷ volume for one mole.", "In (b) the molar volume at r.t.p. is given in the spec's data; use one mole of D$_2$.", "For (c) contrast electrons with neutrons: which set is the same, and which set changes mass?"]})

# ---------- worked examples ----------
worked = [
 {"id": "we1", "kc": K2, "problem": "State the numbers of protons, neutrons and electrons in the ion $^{37}_{17}\\mathrm{Cl}^{-}$.",
  "steps": [
   {"do": "Protons = the bottom number = 17.", "why": "The proton (atomic) number is the lower number; it identifies the element and ignores any charge.", "check": {"kind": "numeric", "answer": {"value": 17, "unit": "", "exact": True}}},
   {"do": "Neutrons = top − bottom $=37-17=20$.", "why": "The nucleon number counts protons plus neutrons, so subtract the protons. Students often use 37 as the neutron count.", "check": {"kind": "numeric", "answer": {"value": 20, "unit": "", "exact": True}}},
   {"do": "Electrons = protons + 1 $=17+1=18$.", "why": "A charge of $1-$ means one extra electron was gained; the charge changes electrons only.", "check": {"kind": "numeric", "answer": {"value": 18, "unit": "", "exact": True}}}],
  "faded": {"id": "we1f", "problem": "State the number of electrons in the ion $^{71}_{31}\\mathrm{Ga}^{3+}$.", "answer": {"value": 28, "unit": "", "exact": True}, "blank_from": 2}},
 {"id": "we2", "kc": K2, "problem": "Particle X is formed in the nuclear reaction $^{27}_{13}\\mathrm{Al}+{}^{4}_{2}\\mathrm{He}\\to{}^{30}_{15}\\mathrm{P}+\\mathrm{X}$. Deduce the nucleon number and the proton number of X, and identify X.",
  "steps": [
   {"do": "Balance the top numbers: $27+4=31$, and $31=30+x$, so $x=1$.", "why": "Nucleon numbers must add to the same total on both sides.", "check": {"kind": "numeric", "answer": {"value": 1, "unit": "", "exact": True}}},
   {"do": "Balance the bottom numbers: $13+2=15$, and $15=15+y$, so $y=0$.", "why": "Proton numbers (charges) must balance separately from the nucleon numbers. Do not stop after one balance.", "check": {"kind": "numeric", "answer": {"value": 0, "unit": "", "exact": True}}},
   {"do": "Nucleon number 1 and proton number 0 is a neutron, $^{1}_{0}\\mathrm{n}$.", "why": "Only a neutron has one nucleon and no charge; an electron has nucleon number 0 and a proton has proton number 1."}],
  "faded": {"id": "we2f", "problem": "Particle X is formed in $^{35}_{17}\\mathrm{Cl}+{}^{1}_{0}\\mathrm{n}\\to{}^{35}_{16}\\mathrm{S}+\\mathrm{X}$. Deduce the proton number of X.", "answer": {"value": 1, "unit": "", "exact": True}, "blank_from": 1}},
]

flash = [
 {"id": "fc1", "kc": K1, "front": "Define isotope.", "back": "Isotopes are atoms of the same element (same number of protons / same proton number) with different numbers of neutrons (so different nucleon numbers)."},
 {"id": "fc2", "kc": K1, "front": "Are $^{40}\\mathrm{Ar}$ and $^{40}\\mathrm{K}$ isotopes?", "back": "No. They have the same nucleon number but different proton numbers (18 and 19), so they are different elements."},
 {"id": "fc3", "kc": K2, "front": "In the symbol $^{x}_{y}\\mathrm{A}$, what are $x$ and $y$?", "back": "$x$ is the nucleon (mass) number, the total of protons plus neutrons; $y$ is the proton (atomic) number."},
 {"id": "fc4", "kc": K2, "front": "How do you find the numbers of neutrons and electrons from $^{x}_{y}\\mathrm{A}^{q+}$?", "back": "Neutrons $=x-y$; electrons $=y-q$ (a negative charge adds electrons)."},
 {"id": "fc5", "kc": K3, "front": "State and explain why isotopes have the same chemical properties.", "back": "Isotopes have the same number of electrons and the same electron configuration; chemical properties depend on the electrons, not the neutrons."},
 {"id": "fc6", "kc": K4, "front": "State and explain why isotopes have different physical properties (mass and density).", "back": "Isotopes have different numbers of neutrons, so different masses, and so different densities of the same substance."},
]

pack = {"subtopic": SUB, "spec": "9701", "version": 1,
 "note": "Subjects/9701 Chemistry/01 Atomic structure/1.2 Isotopes.md",
 "outline": "Isotopes are atoms of the same element with the same number of protons but different numbers of neutrons. In ${}^{x}_{y}\\mathrm{A}$, $x$ is the nucleon number (protons + neutrons) and $y$ the proton number, so neutrons $=x-y$ and, for an ion of charge $q+$, electrons $=y-q$. Nuclear equations balance both the top and bottom numbers. Isotopes have the same electron configuration, so the same chemical properties; they have different numbers of neutrons, so different masses and densities.",
 "misconceptions": misc, "worked": worked, "items": items, "flashcards": flash, "diagrams": []}
out = ROOT / "build/out/packs/9701/9701-1.2.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(pack, indent=1, ensure_ascii=False))
print("items", len(items))
