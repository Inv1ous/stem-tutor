"""Generate the 9701-2.4 pack (reacting masses and volumes) with every number computed here.

Run:  .venv/bin/python build/work/gen/9701-2.4.py
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SUB = "9701-2.4"
KC = f"{SUB}.1"
OUT = ROOT / f"build/out/packs/9701/{SUB}.json"
BANK = {q["id"]: q for q in json.loads((ROOT / "build/work/mcq/9701.tagged.json").read_text())}

VM = 24.0          # dm3 mol-1 at r.t.p., from the bundle's constants
R = 8.31           # J K-1 mol-1
# A_r / M_r values as printed in the 9701 Periodic Table
AR = {"H": 1.0, "C": 12.0, "N": 14.0, "O": 16.0, "Na": 23.0, "Mg": 24.3, "S": 32.1,
      "Cl": 35.5, "K": 39.1, "Ca": 40.1, "Fe": 55.8, "Rb": 85.5, "Sr": 87.6, "Ba": 137.3}


def mr(*parts):
    """M_r from (element, count) pairs."""
    return sum(AR[e] * n for e, n in parts)


MR = {
    "CH4": mr(("C", 1), ("H", 4)),
    "H2O": mr(("H", 2), ("O", 1)),
    "CO": mr(("C", 1), ("O", 1)),
    "NO": mr(("N", 1), ("O", 1)),
    "CaCO3": mr(("Ca", 1), ("C", 1), ("O", 3)),
    "MgCO3": mr(("Mg", 1), ("C", 1), ("O", 3)),
    "Na2CO3": mr(("Na", 2), ("C", 1), ("O", 3)),
    "NaHCO3": mr(("Na", 1), ("H", 1), ("C", 1), ("O", 3)),
    "NaClO3": mr(("Na", 1), ("Cl", 1), ("O", 3)),
    "CH3COONa": mr(("C", 2), ("H", 3), ("O", 2), ("Na", 1)),
    "C2H5OH": mr(("C", 2), ("H", 6), ("O", 1)),
    "CH3COOH": mr(("C", 2), ("H", 4), ("O", 2)),
    "NH4NO3": mr(("N", 2), ("H", 4), ("O", 3)),
    "(NH4)2SO4": mr(("N", 2), ("H", 8), ("S", 1), ("O", 4)),
    "Fe2O3": mr(("Fe", 2), ("O", 3)),
    "Al4C3": mr(("C", 3)) + 4 * 27.0,
}

items = []


def _nid(kind):
    tag = "p" if kind == "past" else "i"
    n = 1 + sum(i["id"][len(SUB) + 1] == tag for i in items)
    return f"{SUB}-{tag}{n:02d}"


def past(qid, explanation, wrong=None, command="Calculate", difficulty=3, kcs=(KC,)):
    """A past MCQ, verbatim: original stem, options, letters and official key."""
    q = BANK[qid]
    opts = q["options"]
    assert sorted(opts) == ["A", "B", "C", "D"], (qid, opts)
    assert all(str(v).strip() for v in opts.values()), (qid, opts)
    assert q["answer"] in opts, qid
    it = {"id": _nid("past"), "kcs": list(kcs), "kind": "mcq", "difficulty": difficulty,
          "command_word": command, "source": {"type": "past", "ref": q["ref"], "qid": qid},
          "stem": q["stem"], "options": opts, "answer": q["answer"], "marks": 1,
          "explanation": explanation, "distractors": wrong or {}}
    if q.get("image"):
        it["image"] = q["image"]
    items.append(it)


HINTS = {
    "moles": ["Every stoichiometry question starts by turning the given data into moles.",
              "Convert each mass with $n=m/M_r$, each solution with $n=cV$ and each gas with $n=V/24.0$, then use the balanced equation.",
              "Write the balanced equation and find the amount, in mol, of each substance you are given."],
    "limit": ["Only one reactant can run out; the other is in excess.",
              "Divide each reactant's amount in mol by its coefficient in the balanced equation; the smallest value marks the limiting reagent, and all product amounts follow from it.",
              "Find the amount, in mol, of both reactants before comparing them."],
    "yield": ["A percentage yield compares what was actually made with the most that could have been made.",
              "Work out the theoretical amount of product from the limiting reagent, then divide the actual amount by it and multiply by 100.",
              "Convert the mass of the reactant into moles and use the equation ratio to get the theoretical amount of product."],
    "soln": ["Concentration links amount of substance to the volume of solution.",
             "Use $n=cV$ with $V$ in $\\mathrm{dm^3}$, carry the moles through the equation ratio, then convert back.",
             "Divide any volume given in $\\mathrm{cm^3}$ by 1000 before using it."],
    "gas": ["At r.t.p. one mole of any gas occupies the same volume.",
            "Find the amount, in mol, of the gas from the equation, then multiply by the molar gas volume.",
            "Decide first which substances are gases under the stated conditions."],
}


def gen_mcq(stem, options, key, explanation, hints, difficulty=3, wrong=None, command="Calculate"):
    assert len(options) == 4 and len(set(options)) == 4 and 0 <= key < 4
    items.append({"id": _nid("gen"), "kcs": [KC], "kind": "mcq", "difficulty": difficulty,
                  "command_word": command, "source": {"type": "generated"}, "stem": stem,
                  "options": dict(zip("ABCD", options)), "answer": "ABCD"[key], "marks": 1,
                  "explanation": explanation, "shuffle": True, "hints": HINTS[hints],
                  "distractors": wrong or {}})


def gen_num(stem, value, unit, sf_ok, explanation, hints, difficulty=3, marks=2,
            command="Calculate", distractors=None):
    items.append({"id": _nid("gen"), "kcs": [KC], "kind": "numeric", "difficulty": difficulty,
                  "command_word": command, "source": {"type": "generated"}, "stem": stem,
                  "marks": marks, "answer": {"value": round(value, 6), "unit": unit, "sf_ok": list(sf_ok)},
                  "distractors": distractors or [], "explanation": explanation, "hints": HINTS[hints]})


def gen_tmpl(stem, template, unit, sf_ok, explanation, hints, difficulty=3, marks=3,
             command="Calculate"):
    items.append({"id": _nid("gen"), "kcs": [KC], "kind": "numeric", "difficulty": difficulty,
                  "command_word": command, "source": {"type": "generated"}, "stem": stem,
                  "marks": marks, "template": template, "answer": {"unit": unit, "sf_ok": list(sf_ok)},
                  "explanation": explanation, "hints": HINTS[hints]})


def gen_short(stem, points, explanation, hints, difficulty=3, command="Explain"):
    items.append({"id": _nid("gen"), "kcs": [KC], "kind": "short", "difficulty": difficulty,
                  "command_word": command, "source": {"type": "generated"}, "stem": stem,
                  "marks": len(points), "rubric": [{"point": p, "keywords": k} for p, k in points],
                  "explanation": explanation, "hints": HINTS[hints]})


# ---------------------------------------------------------------- misconceptions
mis = [
    {"id": "m1", "kc": KC,
     "statement": "The limiting reagent is whichever reactant is present in the smaller amount in moles.",
     "refutation": "Divide each amount in mol by that reactant's coefficient in the balanced equation; the smallest quotient is the limiting reagent, so a reactant present in more moles can still run out first.",
     "contrast": "With $\\ce{Mg + 2HCl -> MgCl2 + H2}$, $0.070\\ \\mathrm{mol}$ of Mg needs $0.14\\ \\mathrm{mol}$ of HCl, so $0.11\\ \\mathrm{mol}$ of HCl is limiting even though it is the larger number.",
     "source": "ER 9701 s23 P11 Q13"},
    {"id": "m2", "kc": KC,
     "statement": "Equal masses of two substances contain equal amounts in moles, so they give equal volumes of gas.",
     "refutation": "Amount in moles is $m/M_r$, so the substance with the smaller $M_r$ gives more moles from the same mass and therefore more gas.",
     "contrast": "$5.0\\ \\mathrm{g}$ of calcium is $0.12\\ \\mathrm{mol}$ and releases $0.12\\ \\mathrm{mol}$ of $\\ce{H2}$, while $5.0\\ \\mathrm{g}$ of potassium is $0.13\\ \\mathrm{mol}$ but releases only $0.064\\ \\mathrm{mol}$.",
     "source": "ER 9701 s22 P11 Q3"},
    {"id": "m3", "kc": KC,
     "statement": "Percentage yield is the mass of product divided by the mass of reactant, multiplied by 100.",
     "refutation": "Percentage yield compares the actual amount of product with the theoretical amount calculated from the equation; masses of different substances may only be compared after converting to moles.",
     "contrast": "$74.00\\ \\mathrm{g}$ of butan-2-ol ($1.00\\ \\mathrm{mol}$) giving $44.64\\ \\mathrm{g}$ of butanone ($0.62\\ \\mathrm{mol}$) is a $62\\%$ yield, not $60\\%$.",
     "source": "ER 9701 s19 P12 Q39"},
    {"id": "m4", "kc": KC,
     "statement": "Moles of one substance can be carried straight across to another in a 1:1 ratio.",
     "refutation": "The coefficients of the balanced equation set the ratio; multiply or divide by them when moving from one substance to another.",
     "contrast": "In $\\ce{CaCO3 + 2HCl -> CaCl2 + H2O + CO2}$, $0.040\\ \\mathrm{mol}$ of HCl gives $0.020\\ \\mathrm{mol}$ of $\\ce{CO2}$, not $0.040\\ \\mathrm{mol}$.",
     "source": "research"},
    {"id": "m5", "kc": KC,
     "statement": "Water formed in a combustion is part of the final gas volume measured at room conditions.",
     "refutation": "At room conditions water is a liquid, so only gases left over and gaseous products such as $\\ce{CO2}$ are counted; water is only included when the stated temperature keeps it as steam.",
     "contrast": "Burning $0.0500\\ \\mathrm{mol}$ of propane gives $0.200\\ \\mathrm{mol}$ of water, which condenses at r.t.p. but would add $4.80\\ \\mathrm{dm^3}$ at $120\\ \\mathrm{^\\circ C}$.",
     "source": "research"},
]

# ---------------------------------------------------------------- past MCQs (12)
# 1. limiting reagent then gas volume
n_ch4, n_steam = 0.80 / MR["CH4"], 1.35 / MR["H2O"]
assert abs(n_ch4 - 0.05) < 1e-9 and abs(n_steam - 0.075) < 1e-9
v_h2 = n_steam / 2 * 4 * VM
assert abs(v_h2 - 3.60) < 1e-9
past("9701_w25_13_q4",
     "There is $0.050\\ \\mathrm{mol}$ of $\\ce{CH4}$ and $0.075\\ \\mathrm{mol}$ of steam, but $0.050\\ \\mathrm{mol}$ of $\\ce{CH4}$ would need $0.100\\ \\mathrm{mol}$ of steam, so steam is limiting and gives $0.075\\times 4/2 = 0.15\\ \\mathrm{mol}$ of $\\ce{H2}$, i.e. $0.15\\times 24.0 = 3.60\\ \\mathrm{dm^3}$. D ($7.20\\ \\mathrm{dm^3}$) comes from treating methane as limiting because it is the smaller number of moles.",
     {"D": "m1", "A": "m4"}, difficulty=4)

# 2. two reactants in exactly equal moles; total volume of products
n_no, n_co = 7.5 / MR["NO"], 7.0 / MR["CO"]
assert abs(n_no - 0.25) < 1e-9 and abs(n_co - 0.25) < 1e-9
v_prod = (n_no / 2 + n_co) * VM          # 2NO + 2CO -> N2 + 2CO2
assert abs(v_prod - 9.0) < 1e-9
past("9701_w24_13_q23",
     "Both reactants are $0.25\\ \\mathrm{mol}$ and $\\ce{2NO + 2CO -> N2 + 2CO2}$ consumes them together, giving $0.125\\ \\mathrm{mol}$ of $\\ce{N2}$ and $0.25\\ \\mathrm{mol}$ of $\\ce{CO2}$: $0.375\\times 24.0 = 9.0\\ \\mathrm{dm^3}$. B comes from counting only the $\\ce{CO2}$ and forgetting that nitrogen is also a gaseous product.",
     {"B": "m4"}, difficulty=4)

# 3. equal masses, different M_r
h2_per_5g = {"calcium": 5.0 / AR["Ca"] * 1, "potassium": 5.0 / AR["K"] * 0.5,
             "rubidium": 5.0 / AR["Rb"] * 0.5, "strontium": 5.0 / AR["Sr"] * 1}
assert max(h2_per_5g, key=h2_per_5g.get) == "calcium"
past("9701_s22_11_q3",
     f"Calcium gives $5.0/40.1 = 0.12\\ \\mathrm{{mol}}$ of $\\ce{{H2}}$ because each atom releases one $\\ce{{H2}}$, while potassium gives only $0.5\\times 5.0/39.1 = {h2_per_5g['potassium']:.3f}\\ \\mathrm{{mol}}$; rubidium and strontium have larger $A_r$ and give less still. Candidates who chose another option assumed equal masses mean equal amounts in moles.",
     {"B": "m2", "C": "m2", "D": "m2"}, command="Deduce", difficulty=4)

# 4. deduce a mixture ratio from product volumes
def combust(n_eth, n_meth):
    """CO2 and H2O from n_eth C2H5OH and n_meth CH3OH."""
    return 2 * n_eth + n_meth, 3 * n_eth + 2 * n_meth


assert combust(3, 1) == (7, 11) and (35, 55) == (5 * 7, 5 * 11)
assert combust(2, 3) == (7, 12) and combust(3, 2) == (8, 13) and combust(1, 3) == (5, 9)
past("9701_s21_13_q24",
     "The products are in the ratio $35:55 = 7:11$. Three $\\ce{C2H5OH}$ and one $\\ce{CH3OH}$ give $7\\ce{CO2}$ and $11\\ce{H2O}$, which matches. B gives $7:12$ and C gives $8:13$, so neither fits; both were popular because candidates matched only the $\\ce{CO2}$ count.",
     command="Deduce", difficulty=5)

# 5. limiting reagent, then pV = nRT
n_total = 1.5 + 3.0                      # X(g) + 2Y(g) -> 2Z(g), Y limiting
p_final = n_total * R * (120 + 273) / 1.0e-3
assert abs(p_final - 1.47e7) / 1.47e7 < 0.01
past("9701_s19_12_q6",
     f"Y is limiting: $3.0\\ \\mathrm{{mol}}$ of Y uses $1.5\\ \\mathrm{{mol}}$ of X and makes $3.0\\ \\mathrm{{mol}}$ of Z, leaving $4.5\\ \\mathrm{{mol}}$ of gas in total. Then $p = nRT/V = 4.5\\times 8.31\\times 393/(1.0\\times 10^{{-3}}) = {p_final:.2e}\\ \\mathrm{{Pa}}$. B and D were popular because they use the wrong total amount of gas, treating X as limiting or ignoring the unreacted X.",
     {"B": "m1", "D": "m1"}, difficulty=5)

# 6. chain of mole ratios
cr = 3 * 2                               # mol Cr(VI) in 3 mol K2Cr2O7
electrons = cr * 3                       # Cr(VI) -> Cr(3+)
i2 = electrons / 2
thio = 2 * i2
assert (cr, electrons, i2, thio) == (6, 18, 9, 18)
past("9701_s22_13_q12",
     "Three moles of $\\ce{K2Cr2O7}$ contain six moles of chromium(VI), which gain 18 moles of electrons; those 18 moles oxidise 18 moles of $\\ce{I-}$ to nine moles of $\\ce{I2}$, needing $2\\times 9 = 18$ moles of $\\ce{S2O3^{2-}}$. B follows the chain for one mole of dichromate instead of three.",
     {"B": "m4"}, command="Determine", difficulty=5, kcs=[KC, "9701-6.1.2"])

# 7. percentage yield of a named product
n_s = 0.200 * 0.800
m_s = n_s * MR["CH3COONa"]
assert abs(MR["CH3COONa"] - 82.0) < 1e-9 and abs(m_s - 13.12) < 1e-9
past("9701_s25_13_q26",
     f"$\\ce{{CH3CN}}$ is hydrolysed to sodium ethanoate, so a $100\\%$ yield would be $0.200\\ \\mathrm{{mol}}$; at $80.0\\%$ it is $0.160\\ \\mathrm{{mol}}$, and $0.160\\times 82.0 = {m_s:.2f}\\ \\mathrm{{g}}$. D is the mass of $0.200\\ \\mathrm{{mol}}$ of sodium ethanoate, i.e. the theoretical yield with the $80.0\\%$ ignored.",
     {"D": "m3"}, difficulty=4)

# 8. concentration from a gas volume
n_o2 = 0.600 / VM
c_h2o2 = (2 * n_o2) / (20.0 / 1000)      # 2H2O2 -> 2H2O + O2
assert abs(c_h2o2 - 2.50) < 1e-9
past("9701_s25_13_q13",
     "$600\\ \\mathrm{cm^3}$ of $\\ce{O2}$ is $0.600/24.0 = 0.0250\\ \\mathrm{mol}$, and $\\ce{2H2O2 -> 2H2O + O2}$ means $0.0500\\ \\mathrm{mol}$ of $\\ce{H2O2}$ decomposed. In $0.0200\\ \\mathrm{dm^3}$ that is $2.50\\ \\mathrm{mol\\,dm^{-3}}$. C comes from omitting the $2:1$ ratio between peroxide and oxygen.",
     {"C": "m4"}, command="Determine", difficulty=4)

# 9. titration to a percentage by mass
n_acid = 7.15 / 1000 * 0.100
pct_nahco3 = 2 * n_acid * MR["NaHCO3"] / 1.00 * 100
assert abs(MR["NaHCO3"] - 84.0) < 1e-9 and abs(pct_nahco3 - 12.0) < 0.05
past("9701_s25_13_q15",
     f"The acid is $7.15\\times 10^{{-4}}\\ \\mathrm{{mol}}$, and $\\ce{{2NaHCO3 + H2SO4 -> Na2SO4 + 2H2O + 2CO2}}$ needs twice as much $\\ce{{NaHCO3}}$: $1.43\\times 10^{{-3}}\\ \\mathrm{{mol}}$, or ${2 * n_acid * MR['NaHCO3']:.3f}\\ \\mathrm{{g}}$, which is ${pct_nahco3:.1f}\\%$ of $1.00\\ \\mathrm{{g}}$. B is what the $1:1$ ratio would give, and halves the correct answer.",
     {"B": "m4"}, command="Determine", difficulty=4)

# 10. basicity of an acid in a titration
v_naoh = 3 * 0.0050 / 0.40 * 1000
assert abs(v_naoh - 37.5) < 1e-9
past("9701_w21_11_q28",
     "Citric acid has three $\\ce{-CO2H}$ groups, so $0.0050\\ \\mathrm{mol}$ needs $0.015\\ \\mathrm{mol}$ of $\\ce{NaOH}$, i.e. $0.015/0.40 = 0.0375\\ \\mathrm{dm^3} = 37.5\\ \\mathrm{cm^3}$. B assumes a $1:1$ reaction and only counts one acidic hydrogen per molecule.",
     {"B": "m4"}, command="Determine", difficulty=4)

# 11. deduce a formula from reacting amounts
n_co2 = 0.108 / VM
n_al4c3 = 0.216 / MR["Al4C3"]
assert abs(MR["Al4C3"] - 144.0) < 1e-9 and abs(n_co2 - 3 * n_al4c3) < 1e-9
past("9701_w24_12_q3",
     f"$108\\ \\mathrm{{cm^3}}$ of $\\ce{{CO2}}$ is $0.0045\\ \\mathrm{{mol}}$, so the sample contains $0.0045\\ \\mathrm{{mol}}$ of carbon. Only $\\ce{{Al4C3}}$ fits: $M_r = 144.0$, so $0.216\\ \\mathrm{{g}}$ is $0.0015\\ \\mathrm{{mol}}$ and $3\\times 0.0015 = 0.0045\\ \\mathrm{{mol}}$ of carbon. A gives a carbon:formula ratio that needs $0.00144\\ \\mathrm{{mol}}$ of carbide and does not match the mass.",
     command="Deduce", difficulty=5, kcs=[KC, "9701-2.3.2"])

# 12. reacting masses from a disproportionation equation
n_naclo3 = 0.600 / 3                     # 3Cl2 + 6NaOH -> 5NaCl + NaClO3 + 3H2O
m_naclo3 = n_naclo3 * MR["NaClO3"]
assert abs(MR["NaClO3"] - 106.5) < 1e-9 and abs(m_naclo3 - 21.3) < 1e-9
past("9701_w25_12_q21",
     f"Hot alkali gives $\\ce{{3Cl2 + 6NaOH -> 5NaCl + NaClO3 + 3H2O}}$, so $0.600\\ \\mathrm{{mol}}$ of $\\ce{{Cl2}}$ makes $0.200\\ \\mathrm{{mol}}$ of $\\ce{{NaClO3}}$: $0.200\\times 106.5 = {m_naclo3:.1f}\\ \\mathrm{{g}}$. D assumes a $1:1$ ratio with chlorine and so is three times too large.",
     {"D": "m4"}, difficulty=4, kcs=[KC, "9701-11.4.1"])

# ---------------------------------------------------------------- generated items
# i01: limiting reagent -> volume of gas (template, counts as 3 variants)
gen_tmpl(
    "A [[m:.2f]] g sample of magnesium is added to [[v:.1f]] cm$^3$ of [[c:.2f]] mol dm$^{-3}$ "
    "hydrochloric acid. Calculate the volume of hydrogen produced, measured at r.t.p., in dm$^3$.",
    {"params": {"m": {"choices": [0.60, 0.72, 0.84, 0.96]},
                "v": {"choices": [40.0, 50.0]},
                "c": {"choices": [0.40, 0.50]}},
     "derived": {"n_mg": "m/24.3", "n_hcl": "c*v/1000"},
     "answer": "n_hcl/2*24.0",
     "distractors": [{"expr": "n_hcl*24.0", "misconception": "m4"},
                     {"expr": "n_mg*24.0", "misconception": "m1"}],
     "constraints": ["n_hcl/2 < n_mg"]},
    "dm^3", [2, 3],
    "$\\ce{Mg + 2HCl -> MgCl2 + H2}$. The acid supplies $cV$ mol of $\\ce{HCl}$, which is less than twice the amount of magnesium, so the acid is limiting; half as many moles of $\\ce{H2}$ form, and each occupies $24.0\\ \\mathrm{dm^3\\,mol^{-1}}$.",
    "limit", difficulty=4)

# i02: percentage yield (template)
gen_tmpl(
    "Ethanol is oxidised to ethanoic acid. When [[m:.2f]] g of ethanol is oxidised, [[y:.2f]] g of "
    "ethanoic acid is obtained. Calculate the percentage yield.",
    {"params": {"m": {"choices": [4.60, 9.20, 13.80, 23.00]},
                "y": {"choices": [4.50, 6.00, 9.00, 12.00, 18.00, 24.00]}},
     "derived": {"theory": "m/46.0*60.0"},
     "answer": "y/theory*100",
     "distractors": [{"expr": "y/m*100", "misconception": "m3"}],
     "constraints": ["y < 0.96*theory", "y > 0.5*theory"]},
    "%", [2, 3],
    "$\\ce{C2H5OH + 2[O] -> CH3COOH + H2O}$ is $1:1$, so the theoretical mass of ethanoic acid is $(m/46.0)\\times 60.0$. The percentage yield is the actual mass divided by that theoretical mass, times 100.",
    "yield")

# i03: concentration of a solution from a titration (template)
gen_tmpl(
    "In a titration, [[v:.1f]] cm$^3$ of [[c:.3f]] mol dm$^{-3}$ sodium hydroxide exactly "
    "neutralises 25.0 cm$^3$ of dilute sulfuric acid. Calculate the concentration of the sulfuric "
    "acid in mol dm$^{-3}$.",
    {"params": {"v": {"choices": [20.0, 24.0, 25.0, 30.0]},
                "c": {"choices": [0.100, 0.200, 0.500]}},
     "derived": {"n_naoh": "c*v/1000"},
     "answer": "(n_naoh/2)/0.0250",
     "distractors": [{"expr": "n_naoh/0.0250", "misconception": "m4"}],
     "constraints": ["1 > 0"]},
    "mol dm^-3", [2, 3],
    "$\\ce{2NaOH + H2SO4 -> Na2SO4 + 2H2O}$, so the amount of acid is half the amount of alkali. Divide that amount by $0.0250\\ \\mathrm{dm^3}$ to get the concentration.",
    "soln", command="Determine")

# i04: equal masses, different M_r
n_h2_mg, n_h2_ca = 1.0 / AR["Mg"], 1.0 / AR["Ca"]
assert n_h2_mg > n_h2_ca
gen_mcq("Equal masses of magnesium and of calcium are each added to an excess of dilute "
        "hydrochloric acid. Deduce which metal releases the larger volume of hydrogen, measured "
        "under the same conditions.",
        ["magnesium, because the same mass is a larger amount in moles",
         "calcium, because its relative atomic mass is larger",
         "neither, because the masses of metal are equal",
         "calcium, because each calcium atom transfers two electrons"],
        0,
        "Each metal gives one mole of $\\ce{H2}$ per mole of metal, so the comparison is between amounts: $1/24.3 > 1/40.1$, and magnesium wins. The masses being equal does not make the amounts equal.",
        "gas", difficulty=3, wrong={"B": "m2", "C": "m2", "D": "m2"}, command="Deduce")

# i05: water condenses at room conditions
n_prop, n_o2_start = 0.0500, 0.400
n_o2_used = 5 * n_prop
n_co2, n_h2o = 3 * n_prop, 4 * n_prop
v_final = (n_o2_start - n_o2_used + n_co2) * VM
v_with_water = (n_o2_start - n_o2_used + n_co2 + n_h2o) * VM
v_co2_only = n_co2 * VM
v_no_o2_used = (n_o2_start + n_co2) * VM
assert n_o2_used < n_o2_start
assert [round(x, 2) for x in (v_co2_only, v_final, v_with_water, v_no_o2_used)] == [3.60, 7.20, 12.00, 13.20]
gen_mcq("0.0500 mol of propane is burnt completely in 0.400 mol of oxygen. Calculate the final "
        "volume of gas, measured at room conditions.",
        [f"{v_co2_only:.2f} dm$^3$", f"{v_final:.2f} dm$^3$", f"{v_with_water:.2f} dm$^3$",
         f"{v_no_o2_used:.2f} dm$^3$"],
        1,
        "$\\ce{C3H8 + 5O2 -> 3CO2 + 4H2O}$ uses $0.250\\ \\mathrm{mol}$ of $\\ce{O2}$, leaving $0.150\\ \\mathrm{mol}$ unreacted, and makes $0.150\\ \\mathrm{mol}$ of $\\ce{CO2}$. The water condenses at room conditions, so $0.300\\times 24.0 = 7.20\\ \\mathrm{dm^3}$ of gas remains.",
        "gas", difficulty=4, wrong={"C": "m5", "A": "m4"})

# i06: identifying the limiting reagent
gen_short("Two reactants are mixed and the mass of each is given. Explain how to decide which one "
          "is the limiting reagent.",
          [("Convert each mass to an amount in moles using n = m/Mr.",
            [["mole", "mol", "amount"], ["divid", "m/m", "mr", "relative"]]),
           ("Divide each amount by its coefficient in the balanced equation.",
            [["coefficient", "ratio", "balanc", "equation"], ["divid", "compar"]]),
           ("The reactant with the smallest value is limiting; the other is in excess, and all product amounts are calculated from the limiting reagent.",
            [["smallest", "least", "lowest"], ["limiting"], ["excess"]])],
          "Masses cannot be compared directly; only the amounts in moles divided by the equation coefficients can be, and the smallest of those quotients runs out first.",
          "limit", difficulty=3)

# i07: percentage by mass of an element
pct_n_as = 2 * AR["N"] / MR["(NH4)2SO4"] * 100
pct_n_an = 2 * AR["N"] / MR["NH4NO3"] * 100
assert abs(MR["(NH4)2SO4"] - 132.1) < 1e-9 and abs(MR["NH4NO3"] - 80.0) < 1e-9
assert abs(pct_n_as - 21.2) < 0.05 and abs(pct_n_an - 35.0) < 0.05
gen_num("Ammonium sulfate, $\\ce{(NH4)2SO4}$, is used as a fertiliser. Calculate the percentage by "
        "mass of nitrogen in ammonium sulfate.",
        pct_n_as, "%", [3],
        f"$M_r[\\ce{{(NH4)2SO4}}] = 132.1$ and the two nitrogen atoms contribute $28.0$, so the percentage is $28.0/132.1\\times 100 = {pct_n_as:.1f}\\%$.",
        "moles", difficulty=3)

# i08: multi-step exam question
n_fe2o3, n_co_r = 8.00 / MR["Fe2O3"], 3.50 / MR["CO"]
assert abs(MR["Fe2O3"] - 159.6) < 1e-9
assert n_co_r / 3 < n_fe2o3 / 1          # CO is limiting
m_fe_max = n_co_r * 2 / 3 * AR["Fe"]
pct_yield_fe = 3.90 / m_fe_max * 100
assert abs(m_fe_max - 4.650) < 0.005 and abs(pct_yield_fe - 83.9) < 0.1
items.append({
    "id": _nid("gen"), "kcs": [KC], "kind": "structured", "difficulty": 5,
    "command_word": "Determine", "source": {"type": "generated"},
    "stem": "Iron(III) oxide is reduced by carbon monoxide in a blast furnace.\n\n"
            "$$\\ce{Fe2O3(s) + 3CO(g) -> 2Fe(s) + 3CO2(g)}$$\n\n"
            "8.00 g of $\\ce{Fe2O3}$ is heated with 3.50 g of $\\ce{CO}$. The reaction yields 3.90 g "
            "of iron.\n\n(a) Determine the limiting reagent.\n"
            "(b) Calculate the maximum mass of iron that could be obtained.\n"
            "(c) Calculate the percentage yield of iron.",
    "marks": 4,
    "scheme": [
        {"mark": "M1", "point": f"n(Fe2O3) = 8.00/159.6 = {n_fe2o3:.5f} mol and n(CO) = 3.50/28.0 = {n_co_r:.4f} mol."},
        {"mark": "A1", "point": f"CO is limiting: n(CO)/3 = {n_co_r / 3:.5f} is less than n(Fe2O3)/1 = {n_fe2o3:.5f}, so Fe2O3 is in excess."},
        {"mark": "M1", "point": f"n(Fe) = (2/3) x {n_co_r:.4f} = {n_co_r * 2 / 3:.5f} mol, so maximum mass = {n_co_r * 2 / 3:.5f} x 55.8 = {m_fe_max:.2f} g.",
         "check": {"kind": "numeric", "answer": {"value": round(m_fe_max, 3), "unit": "g", "sf_ok": [3]}}},
        {"mark": "A1", "point": f"Percentage yield = 3.90/{m_fe_max:.2f} x 100 = {pct_yield_fe:.1f}%.",
         "check": {"kind": "numeric", "answer": {"value": round(pct_yield_fe, 1), "unit": "%", "sf_ok": [3]}}},
    ],
    "explanation": f"Dividing each amount by its coefficient shows $\\ce{{CO}}$ runs out first, which fixes the theoretical yield at ${m_fe_max:.2f}\\ \\mathrm{{g}}$ of iron; the actual $3.90\\ \\mathrm{{g}}$ is ${pct_yield_fe:.1f}\\%$ of that.",
    "hints": HINTS["limit"]})

# i09: deduce a stoichiometric relationship from data
n_mg_d, n_hcl_d = 0.243 / AR["Mg"], 40.0 / 1000 * 0.500
ratio = n_hcl_d / n_mg_d
assert abs(n_mg_d - 0.0100) < 1e-9 and abs(ratio - 2.0) < 1e-9
gen_num("0.243 g of magnesium reacts completely with 40.0 cm$^3$ of 0.500 mol dm$^{-3}$ "
        "hydrochloric acid, and neither reactant is left over. Deduce the number of moles of "
        "hydrochloric acid that react with one mole of magnesium.",
        ratio, "", [1, 2],
        "The magnesium is $0.243/24.3 = 0.0100\\ \\mathrm{mol}$ and the acid is $0.0400\\times 0.500 = 0.0200\\ \\mathrm{mol}$, so the ratio is $0.0200:0.0100$, that is 2 mol of $\\ce{HCl}$ per mole of $\\ce{Mg}$.",
        "moles", difficulty=4, command="Deduce",
        distractors=[{"value": 1.0, "misconception": "m4"}])

# i10: when the molar gas volume may be used
gen_mcq("A student calculates the volume of a product gas by multiplying its amount in moles by "
        "24.0 dm$^3$ mol$^{-1}$. State the condition under which this is valid.",
        ["the substance is a gas at room temperature and pressure",
         "the gas has a relative molecular mass of 24.0",
         "the gas is the limiting reagent in the reaction",
         "one mole of the reactant was used"],
        0,
        "One mole of any gas occupies $24.0\\ \\mathrm{dm^3}$ at r.t.p., whatever its $M_r$; the molar gas volume may only be applied to substances that are gaseous under the stated conditions.",
        "gas", difficulty=2, wrong={"B": "m2"}, command="State")

# i11: why volumes of gases are in the same ratio as moles
gen_short("Explain why the volumes of two gases measured at the same temperature and pressure are "
          "in the same ratio as their amounts in moles.",
          [("Equal volumes of gases at the same temperature and pressure contain equal numbers of molecules.",
            [["equal volume", "same volume"], ["same number", "equal number", "equal amount"], ["molecul", "particle"]]),
           ("So volume is proportional to the amount in moles, and the ratio of volumes equals the ratio in the balanced equation.",
            [["proportional", "proportion"], ["mole", "amount"], ["ratio", "equation"]])],
          "Avogadro's result that equal volumes of gases contain equal numbers of molecules makes volume proportional to amount, so gas volumes may be used directly as mole ratios.",
          "gas", difficulty=3)

# ---------------------------------------------------------------- worked examples
n_caco3, n_hcl_w = 3.00 / MR["CaCO3"], 40.0 / 1000 * 1.00
assert abs(MR["CaCO3"] - 100.1) < 1e-9
assert n_hcl_w / 2 < n_caco3             # acid limiting
v_co2_w = n_hcl_w / 2 * VM
assert abs(v_co2_w - 0.480) < 1e-9
n_mgco3, n_hcl_f = 2.00 / MR["MgCO3"], 30.0 / 1000 * 1.00
assert abs(MR["MgCO3"] - 84.3) < 1e-9 and n_hcl_f / 2 < n_mgco3
v_co2_f = n_hcl_f / 2 * VM
assert abs(v_co2_f - 0.360) < 1e-9

n_hcl_t = 18.40 / 1000 * 0.0500
m_na2co3 = n_hcl_t / 2 * (250.0 / 25.0) * MR["Na2CO3"]
pct_na2co3 = m_na2co3 / 1.00 * 100
assert abs(MR["Na2CO3"] - 106.0) < 1e-9 and abs(pct_na2co3 - 48.76) < 0.01
n_hcl_t2 = 22.00 / 1000 * 0.100
pct_f2 = n_hcl_t2 / 2 * 10 * MR["Na2CO3"] / 2.00 * 100
assert abs(pct_f2 - 58.3) < 0.05

worked = [
    {"id": "we1", "kc": KC,
     "problem": "3.00 g of calcium carbonate is added to 40.0 cm$^3$ of 1.00 mol dm$^{-3}$ hydrochloric acid. Calculate the volume of carbon dioxide produced, measured at r.t.p.",
     "steps": [
         {"do": "Write the balanced equation: $\\ce{CaCO3(s) + 2HCl(aq) -> CaCl2(aq) + H2O(l) + CO2(g)}$.",
          "why": "Every mole ratio in the calculation comes from this equation, so it is written before any numbers."},
         {"do": f"Amounts: $n(\\ce{{CaCO3}}) = 3.00/100.1 = {n_caco3:.5f}\\ \\mathrm{{mol}}$ and $n(\\ce{{HCl}}) = 0.0400 \\times 1.00 = {n_hcl_w:.4f}\\ \\mathrm{{mol}}$.",
          "why": "Convert the volume to $\\mathrm{dm^3}$ before using $n=cV$; $40.0\\ \\mathrm{cm^3}$ is $0.0400\\ \\mathrm{dm^3}$."},
         {"do": f"Divide by the coefficients: ${n_caco3:.5f}/1 = {n_caco3:.5f}$ for the carbonate and ${n_hcl_w:.4f}/2 = {n_hcl_w / 2:.4f}$ for the acid, so the acid is the limiting reagent.",
          "why": "The acid is present in more moles than the carbonate, yet it still runs out first because two moles are needed per mole of carbonate."},
         {"do": f"$n(\\ce{{CO2}}) = {n_hcl_w:.4f}/2 = {n_hcl_w / 2:.4f}\\ \\mathrm{{mol}}$, so $V = {n_hcl_w / 2:.4f} \\times 24.0 = {v_co2_w:.3f}\\ \\mathrm{{dm^3}}$.",
          "why": "All product amounts follow from the limiting reagent, and the molar gas volume converts moles of gas to volume at r.t.p.",
          "check": {"kind": "numeric", "answer": {"value": round(v_co2_w, 4), "unit": "dm^3", "sf_ok": [2, 3]}}}],
     "faded": {"id": "we1f",
               "problem": "2.00 g of magnesium carbonate, $M_r = 84.3$, is added to 30.0 cm$^3$ of 1.00 mol dm$^{-3}$ hydrochloric acid. Calculate the volume of carbon dioxide produced, measured at r.t.p., in dm$^3$.",
               "answer": {"value": round(v_co2_f, 4), "unit": "dm^3", "sf_ok": [2, 3]},
               "blank_from": 1}},
    {"id": "we2", "kc": KC,
     "problem": "A 1.00 g sample of impure sodium carbonate is dissolved in water and made up to 250 cm$^3$. A 25.0 cm$^3$ portion of this solution requires 18.40 cm$^3$ of 0.0500 mol dm$^{-3}$ hydrochloric acid for complete reaction. Calculate the percentage by mass of sodium carbonate in the sample.",
     "steps": [
         {"do": f"$n(\\ce{{HCl}}) = 0.01840 \\times 0.0500 = {n_hcl_t:.3e}\\ \\mathrm{{mol}}$.",
          "why": "The titre is the only reliable measurement, so the calculation starts from it."},
         {"do": f"From $\\ce{{Na2CO3(aq) + 2HCl(aq) -> 2NaCl(aq) + H2O(l) + CO2(g)}}$, $n(\\ce{{Na2CO3}})$ in the portion is ${n_hcl_t:.3e}/2 = {n_hcl_t / 2:.3e}\\ \\mathrm{{mol}}$.",
          "why": "Carbonate is doubly basic; halving the acid amount is the step most often missed."},
         {"do": f"Scale to the flask: $\\times 250.0/25.0 = {n_hcl_t / 2 * 10:.3e}\\ \\mathrm{{mol}}$ in the whole 250 cm$^3$.",
          "why": "Only one tenth of the dissolved sample was titrated, so the amount found must be multiplied by ten."},
         {"do": f"Mass $= {n_hcl_t / 2 * 10:.3e} \\times 106.0 = {m_na2co3:.4f}\\ \\mathrm{{g}}$, so the purity is ${m_na2co3:.4f}/1.00 \\times 100 = {pct_na2co3:.1f}\\%$.",
          "why": "A percentage by mass compares the mass of the pure substance found with the mass of sample weighed out.",
          "check": {"kind": "numeric", "answer": {"value": round(pct_na2co3, 2), "unit": "%", "sf_ok": [3]}}}],
     "faded": {"id": "we2f",
               "problem": "A 2.00 g sample of impure sodium carbonate is dissolved and made up to 250 cm$^3$. A 25.0 cm$^3$ portion requires 22.00 cm$^3$ of 0.100 mol dm$^{-3}$ hydrochloric acid. Calculate the percentage by mass of sodium carbonate in the sample.",
               "answer": {"value": round(pct_f2, 2), "unit": "%", "sf_ok": [3]},
               "blank_from": 1}},
]

# ---------------------------------------------------------------- flashcards
flash = [
    ("fc1", "What is meant by a reacting mass?",
     "The mass of a substance that takes part in a reaction, found from the amount in moles given by the balanced equation and the relative formula mass: $m = n \\times M_r$."),
    ("fc2", "Define percentage yield.",
     "Percentage yield $=\\dfrac{\\text{actual amount (or mass) of product}}{\\text{theoretical amount (or mass) of product}} \\times 100$, where the theoretical value is calculated from the limiting reagent and the balanced equation."),
    ("fc3", "Define the limiting reagent.",
     "The reactant that is completely used up first, so it determines the maximum amount of product; it is the reactant with the smallest value of (amount in moles / coefficient in the balanced equation). Any other reactant is in excess."),
    ("fc4", "Define molar concentration and give its equation.",
     "The amount of solute, in mol, dissolved in $1\\ \\mathrm{dm^3}$ of solution: $c = n/V$ with $V$ in $\\mathrm{dm^3}$, so $n = cV$. Units $\\mathrm{mol\\,dm^{-3}}$."),
    ("fc5", "State the molar gas volume at r.t.p. and how it is used.",
     "One mole of any gas occupies $24.0\\ \\mathrm{dm^3}$ at r.t.p., so $V = n \\times 24.0\\ \\mathrm{dm^3}$ (or $n \\times 24\\,000\\ \\mathrm{cm^3}$) for any gas, independent of its $M_r$."),
]

# ---------------------------------------------------------------- assemble
pack = {
    "subtopic": SUB, "spec": "9701", "version": 1,
    "note": "Subjects/9701 Chemistry/02 Atoms, molecules and stoichiometry/2.4 Reacting masses and volumes (of solutions and gases).md",
    "outline": "Every stoichiometry calculation has the same shape: convert the data to amounts in moles, cross the balanced equation using its coefficients, then convert back to the quantity asked for. Masses give $n = m/M_r$; solutions give $n = cV$ with $V$ in $\\mathrm{dm^3}$; gases at r.t.p. give $n = V/24.0$. When two reactant amounts are given, divide each by its coefficient: the smallest quotient is the limiting reagent and fixes every product amount, while the other reactant is in excess. Percentage yield compares the actual product with the theoretical product from the limiting reagent. Gas volumes measured at the same temperature and pressure are in the same ratio as moles, so volumes may be used directly; water counts as a gas only when the conditions keep it as steam. Answers carry the significant figures the data justify.",
    "misconceptions": mis,
    "worked": worked,
    "items": items,
    "flashcards": [{"id": i, "kc": KC, "front": f, "back": b} for i, f, b in flash],
    "diagrams": [],
}

n_past = sum(i["source"]["type"] == "past" for i in items)
n_gen = len(items) - n_past
assert n_past == 12, n_past
assert len({i["id"] for i in items}) == len(items)
OUT.write_text(json.dumps(pack, indent=1, ensure_ascii=False) + "\n")
print(f"wrote {OUT.relative_to(ROOT)}: {n_past} past + {n_gen} generated items, "
      f"{len(worked)} worked, {len(flash)} flashcards, {len(mis)} misconceptions")
