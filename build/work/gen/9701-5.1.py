"""Generate the 9701-5.1 teaching pack; numeric results are calculated here."""
import json
import sys
from pathlib import Path
from sympy import Rational

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "build"))
from validate_pack import validate  # noqa: E402

SUB = "9701-5.1"
K = {n: f"{SUB}.{n}" for n in range(1, 8)}
BANK = {q["id"]: q for q in json.loads((ROOT / "build/work/mcq/9701.tagged.json").read_text())}
items = []

# Check every fixed numerical result used below against the supplied data.
assert (50 - 20, 100 - 20, 100 - 50) == (30, 80, 50)
assert -114 / 2 == -57
assert (436 + 242) - 2 * 431 == -184
assert 1660 / 4 == 415
assert 200 * 4.18 * (66.0 - 18.0) == 40128
assert round(40128 / 0.45 / 1.60, -2) == 55700
assert 200 * 4.18 * (41.0 - 23.7) > 14400
assert 50 * 4.2 * 2.5 == 525
assert Rational(25, 1000) * Rational(350, 1000) == Rational(875, 100000)
assert -Rational(525, 1000) / Rational(875, 100000) == -60


def past(qid, kc, explanation, wrong=None):
    q = BANK[qid]
    n = 1 + sum(i["source"]["type"] == "past" for i in items)
    it = dict(id=f"{SUB}-p{n:02d}", kcs=[K[kc]], kind="mcq", difficulty=3,
              command_word="Identify", source={"type": "past", "ref": q["ref"], "qid": qid},
              stem=q["stem"], options=q["options"], answer=q["answer"],
              marks=1, explanation=explanation)
    if q.get("image"):
        it["image"] = q["image"]
    if wrong:
        it["distractors"] = wrong
    items.append(it)


def mcq(kcs, stem, options, answer, explanation, difficulty=2, wrong=None):
    n = 1 + sum(i["source"]["type"] == "generated" for i in items)
    items.append(dict(id=f"{SUB}-i{n:02d}", kcs=[K[k] for k in kcs], kind="mcq",
                      difficulty=difficulty, command_word="Identify", source={"type": "generated"},
                      stem=stem, options=dict(zip("ABCD", options)), answer=answer, marks=1,
                      explanation=explanation, hints=[
                          "Identify the physical meaning of each quantity before choosing.",
                          "Apply the definition to the species and energy levels in the question.",
                          "Check the direction of energy transfer, the amount, and the units."],
                      distractors=wrong or {}, shuffle=True))


def short(kcs, stem, points, explanation, difficulty=2):
    n = 1 + sum(i["source"]["type"] == "generated" for i in items)
    items.append(dict(id=f"{SUB}-i{n:02d}", kcs=[K[k] for k in kcs], kind="short",
                      difficulty=difficulty, command_word="Explain", source={"type": "generated"},
                      stem=stem, marks=len(points), rubric=[{"point": p, "keywords": kw} for p, kw in points],
                      explanation=explanation, hints=["Start from the definition relevant to the question.",
                      "Give the direction of energy transfer and identify what changes.",
                      "Use the reactants and products to state the relationship precisely."]))


def numeric(kcs, stem, params, answer_expr, distractors, unit, explanation, difficulty=3):
    n = 1 + sum(i["source"]["type"] == "generated" for i in items)
    items.append(dict(id=f"{SUB}-i{n:02d}", kcs=[K[k] for k in kcs], kind="numeric",
                      difficulty=difficulty, command_word="Calculate", source={"type": "generated"},
                      stem=stem, marks=3, template={"params": params, "answer": answer_expr,
                      "distractors": [{"expr": e, "misconception": m} for e, m in distractors],
                      "constraints": ["1 > 0"]}, answer={"unit": unit, "sf_ok": [2, 3, 4]},
                      explanation=explanation, hints=["Find the quantity per mole specified in the question.",
                      "Write the equation and keep track of the sign and units.",
                      "Substitute the given values before rounding."]))


mis = [
    dict(id="m1", kc=K[1], statement="A reaction that makes its surroundings warm has positive $\\Delta H$.", refutation="Heat leaves an exothermic reacting system, so the products have lower enthalpy and $\\Delta H<0$.", contrast="A heat pad warms the surroundings: its reaction is exothermic and has negative $\\Delta H$.", source="ER 9701 w23 P22 Q2"),
    dict(id="m2", kc=K[2], statement="Activation energy and enthalpy change are the same vertical gap on a pathway diagram.", refutation="Activation energy goes from reactants to the peak; $\\Delta H$ goes from reactants to products.", contrast="For an exothermic reaction, $E_{a,\\mathrm{reverse}}=E_{a,\\mathrm{forward}}-\\Delta H$.", source="research"),
    dict(id="m3", kc=K[3], statement="Standard conditions alone define standard enthalpy of formation.", refutation="The elements must also be in their standard states, and exactly one mole of product must form.", contrast="Carbon in its standard state is graphite, not gaseous carbon atoms.", source="ER 9701 s22 P22 Q1"),
    dict(id="m4", kc=K[3], statement="Neutralisation enthalpy is quoted per mole of acid or per reaction as written.", refutation="It is the enthalpy change when an acid and an alkali react to form one mole of water.", contrast="If an equation forms two moles of water, divide its enthalpy change by two.", source="ER 9701 s22 P11 Q10"),
    dict(id="m5", kc=K[4], statement="Breaking bonds releases energy while making bonds takes in energy.", refutation="Bond breaking requires energy; bond making releases energy.", contrast="A reaction is exothermic when forming bonds releases more than breaking bonds absorbs.", source="ER 9701 w25 P13 Q7"),
    dict(id="m6", kc=K[5], statement="Bond energy calculations add the energies of bonds formed to those broken.", refutation="Use $\\Delta H=\\sum E(\\text{broken})-\\sum E(\\text{formed})$ and count bonds using the balanced equation.", contrast="For $\\ce{H2 + Cl2 -> 2HCl}$, break one H–H and one Cl–Cl, then form two H–Cl bonds.", source="research"),
    dict(id="m7", kc=K[6], statement="Every C–H bond in every molecule has the same exact bond energy.", refutation="Bond energy varies with molecular environment. A tabulated average bond energy averages values across compounds; a specified bond dissociation enthalpy is exact for that gaseous process.", contrast="The mean of the four successive C–H dissociations in methane is not the first dissociation alone.", source="ER 9701 s22 P13 Q9"),
    dict(id="m8", kc=K[7], statement="Use fuel mass in $q=mc\\Delta T$, or use Celsius temperature as an absolute temperature.", refutation="Use the mass of the heated water or solution and the temperature difference. For a heat-releasing reaction, divide negative heat absorbed by moles reacted.", contrast="A change of $10\\,^{\\circ}\\mathrm C$ is $10\\,\\mathrm K$, not $283\\,\\mathrm K$.", source="research"),
]

# Original wording, option letters, and official keys come directly from the tagged bank.
past("9701_w24_13_q10", 1, "Neutralisation, combustion and condensation all release heat, so each has negative enthalpy change. B incorrectly calls neutralisation endothermic.", {"B":"m1","C":"m1","D":"m1"})
past("9701_w25_12_q10", 1, "The pad gets hotter because the reaction releases heat; iron is oxidised and loses electrons. C has the heat direction right but incorrectly says iron gains electrons.", {"A":"m1","B":"m1"})
past("9701_s22_11_q10", 2, "The diagram's $x$ is the enthalpy change for the equation as written. It produces two moles of water, so neutralisation enthalpy is $x/2$; A misses this division.", {"A":"m4"})
past("9701_w22_12_q9", 2, "The reverse activation barrier is the forward barrier plus the vertical difference between reactants and products: $50+30=80$ kJ mol$^{-1}$. B mistakes the enthalpy gap for the forward reaction.", {"B":"m2","C":"m2","D":"m2"})
past("9701_w21_11_q8", 3, "Atomisation forms one mole of gaseous atoms from the element in its standard state, solid iodine. B starts with gaseous iodine and produces two moles of atoms.", {"B":"m3","D":"m3"})
past("9701_s22_13_q9", 3, "Breaking the four C–H bonds in methane and dividing the enthalpy by four gives their mean bond energy. C represents four times that mean, the common error.", {"C":"m7"})
past("9701_w24_12_q9", 3, "B forms one mole of NO from nitrogen and oxygen in their standard states. A starts from gaseous carbon instead of graphite.", {"A":"m3"})
past("9701_w25_13_q7", 4, "Making bonds releases energy and breaking them absorbs energy. The reaction is exothermic because bond formation releases more; C reverses these directions.", {"A":"m5","B":"m5","C":"m5"})
past("9701_w25_13_q8", 7, "Water absorbs $200\\times4.18\\times48=40128$ J. Divide by $0.450$ and then by $1.60$ g to obtain about $55700$ J g$^{-1}$; A fails to account for the fraction absorbed.", {"A":"m8"})
past("9701_w25_12_q9", 7, "For the water, $q=mc\\Delta T$ uses $m=200$ g and $\\Delta T=41.0-23.7=17.3$ K. A uses the fuel mass and D uses absolute temperature instead of a temperature change.", {"A":"m8","B":"m8","D":"m8"})
past("9701_w22_13_q10", 7, "The mixture absorbs $50.0\\times4.2\\times2.5=525$ J. $n=0.0250\\times0.350=0.00875$ mol, hence $\\Delta H=-0.525/0.00875=-60$ kJ mol$^{-1}$; C effectively uses the wrong mole count.", {"C":"m8"})
past("9701_w21_13_q7", 7, "Doubling both solution volumes doubles heat released and the mass warmed, so $\\Delta T$ remains $12\\,^{\\circ}\\mathrm C$. C doubles heat without doubling mass.", {"C":"m8"})

mcq([1,2], "In an exothermic reaction, how do product enthalpy and $\\Delta H$ compare with those of reactants?", ["Products lower; $\\Delta H$ negative.","Products higher; $\\Delta H$ positive.","Products lower; $\\Delta H$ positive.","Products higher; $\\Delta H$ negative."], "A", "Exothermic means heat is released: products are lower in enthalpy, so products minus reactants is negative.", wrong={"B":"m1","C":"m1","D":"m1"})
mcq([1,4], "Which description fits an endothermic chemical reaction?", ["It absorbs energy overall and has positive $\\Delta H$.","It releases energy overall and has positive $\\Delta H$.","It absorbs energy overall and has negative $\\Delta H$.","No bonds are formed."], "A", "The products have higher enthalpy because net energy enters the system; bonds can both break and form.", wrong={"B":"m1","C":"m1","D":"m5"})
short([1,4], "Explain why a reaction can be exothermic even though bonds must be broken.", [("Breaking bonds absorbs energy.", [["break"],["absorb","require","take in"]]),("Making bonds releases more energy than breaking absorbs.", [["form","mak"],["releas","give out"],["more"]])], "Both processes occur; greater energy release from bond formation makes the net change negative.",4)
mcq([1,2], "On a pathway diagram, products lie above reactants. Which statement is correct?", ["The forward reaction is endothermic; $\\Delta H>0$.","The forward reaction is exothermic; $\\Delta H<0$.","The forward activation energy is negative.","The reverse reaction is endothermic."], "A", "Products above reactants have higher enthalpy; the forward enthalpy change is positive.", wrong={"B":"m1","C":"m2","D":"m1"})
numeric([2], "A pathway diagram has reactants at [[r]] kJ mol$^{-1}$, products at [[p]] kJ mol$^{-1}$ and a peak at [[peak]] kJ mol$^{-1}$. Calculate the forward activation energy in kJ mol$^{-1}$.", {"r":{"choices":[10,20,30]},"p":{"choices":[40,50]},"peak":{"choices":[100,120]}}, "peak-r", [("peak-p","m2"),("p-r","m2")], "kJ mol^-1", "The forward activation energy is the vertical gap from reactants to the peak: peak minus reactant enthalpy.")
numeric([2], "A pathway has reactants at [[r]] kJ mol$^{-1}$, products at [[p]] kJ mol$^{-1}$, and a peak at [[peak]] kJ mol$^{-1}$. Calculate the reverse activation energy.", {"r":{"choices":[10,20]},"p":{"choices":[40,50,60]},"peak":{"choices":[100,120]}}, "peak-p", [("peak-r","m2"),("p-r","m2")], "kJ mol^-1", "For the reverse direction, the barrier is measured from the products to the peak: peak minus product enthalpy.",4)
mcq([2,3], "A neutralisation equation makes two moles of water and has $\\Delta H=-114$ kJ. What is its enthalpy change of neutralisation?", ["$-57$ kJ mol$^{-1}$","$-114$ kJ mol$^{-1}$","$+57$ kJ mol$^{-1}$","$-228$ kJ mol$^{-1}$"], "A", "Neutralisation enthalpy is per mole of water: $-114/2=-57$ kJ mol$^{-1}$.",4,{"B":"m4","D":"m4"})
mcq([3], "What conditions does $\\ominus$ mean in this syllabus?", ["$298$ K and $101$ kPa.","$273$ K and $101$ kPa.","$298$ K and $1$ kPa.","Any temperature at $101$ kPa."], "A", "The syllabus uses 298 K and 101 kPa for standard conditions.")
mcq([3], "Which equation represents standard enthalpy of formation of carbon dioxide?", ["$\\ce{C(s, graphite) + O2(g) -> CO2(g)}$","$\\ce{C(g) + O2(g) -> CO2(g)}$","$\\ce{CO(g) + 1/2O2(g) -> CO2(g)}$","$\\ce{2C(s, graphite) + 2O2(g) -> 2CO2(g)}$"], "A", "Formation is of one mole of compound from elements in their standard states; graphite is standard carbon.", wrong={"B":"m3","C":"m3","D":"m3"})
short([3], "Define standard enthalpy change of combustion.", [("Enthalpy change when one mole of a substance burns completely in oxygen.", [["one mole","1 mole"],["complet"],["oxygen"]]),("All substances are in standard states under standard conditions.", [["standard state"],["standard condition","298","101"]])], "One mole of substance is completely burned in oxygen, with all reactants and products in their standard states under standard conditions.")
short([3], "Define standard enthalpy change of reaction and standard enthalpy change of formation.", [("Reaction: enthalpy change for the reaction as written under standard conditions, substances in standard states.", [["reaction"],["standard"]]),("Formation: one mole of compound formed from constituent elements in standard states.", [["one mole","1 mole"],["element"],["standard state"]])], "Reaction refers to stoichiometric amounts in the equation; formation requires one mole of product from elements in their standard states.",4)
short([3], "Define standard enthalpy change of neutralisation.", [("Enthalpy change when acid and alkali react in aqueous solution to produce one mole of water.", [["acid"],["alkali","base"],["one mole","1 mole"],["water"]]),("Under standard conditions.", [["standard condition","298","101"]])], "The enthalpy change is per mole of water formed by an aqueous acid and an aqueous alkali under standard conditions.")
mcq([4,5], "Which energy flow accompanies bond breaking and bond making?", ["Breaking absorbs; making releases.","Breaking releases; making absorbs.","Both release.","Both absorb."], "A", "Separating bonded atoms requires energy; formation of a bond releases energy.", wrong={"B":"m5","C":"m5","D":"m5"})
mcq([4,5], "Why is $\\ce{H2 + Cl2 -> 2HCl}$ exothermic if its $\\Delta H$ is negative?", ["Two H–Cl bonds release more energy on forming than one H–H and one Cl–Cl require to break.","Breaking H–H and Cl–Cl releases more energy than H–Cl formation absorbs.","No bonds are broken.","Only one H–Cl bond forms."], "A", "The balanced equation gives two product bonds. Net release requires bond formation energy to exceed bond breaking energy.",4,{"B":"m5","C":"m5","D":"m6"})
short([4,6], "Explain why bond energy data often give only an approximate reaction enthalpy.", [("Average bond energies are averaged over bonds in different gaseous molecules.", [["averag"],["different","various"],["molecule","compound"]]),("The energy of a particular bond depends on its molecular environment.", [["environment","surround","molecule"]])], "Average bond energies vary across molecular environments; a mean may differ from the exact bond dissociation enthalpies in this reaction.",4)
numeric([5], "For $\\ce{H2 + Cl2 -> 2HCl}$, use H–H = [[hh]], Cl–Cl = [[cc]] and H–Cl = [[hc]] kJ mol$^{-1}$. Calculate $\\Delta H$ in kJ mol$^{-1}$.", {"hh":{"choices":[430,436,440]},"cc":{"choices":[240,242,244]},"hc":{"choices":[425,430,435]}}, "hh+cc-2*hc", [("2*hc-hh-cc","m6"),("hh+cc-hc","m6")], "kJ mol^-1", "Break one H–H and one Cl–Cl bond; form two H–Cl bonds. Subtract the latter total from the former.")
numeric([5,6], "For $\\ce{CH4 + Cl2 -> CH3Cl + HCl}$, C–H = [[ch]], Cl–Cl = [[cc]], C–Cl = [[ccl]] and H–Cl = [[hcl]] kJ mol$^{-1}$. Calculate the bond-energy estimate of $\\Delta H$.", {"ch":{"choices":[410,415,420]},"cc":{"choices":[240,245]},"ccl":{"choices":[330,335,340]},"hcl":{"choices":[430,435]}}, "ch+cc-ccl-hcl", [("ccl+hcl-ch-cc","m6"),("ch+cc-ccl","m6")], "kJ mol^-1", "Only one C–H and one Cl–Cl bond break; one C–Cl and one H–Cl bond form. Average bond energies give an estimate.",4)
mcq([5,6], "If the four C–H bonds in gaseous methane require a total of $1660$ kJ mol$^{-1}$ to break, what is their mean bond energy?", ["$415$ kJ mol$^{-1}$","$1660$ kJ mol$^{-1}$","$-415$ kJ mol$^{-1}$","$6640$ kJ mol$^{-1}$"], "A", "Divide the total energy by four bonds: $1660/4=415$ kJ mol$^{-1}$. The total is four times the mean.", wrong={"B":"m7","C":"m5"})
short([5,6], "Contrast an exact bond dissociation enthalpy with an average bond energy.", [("Exact value belongs to breaking a specified bond in a specified gaseous molecule.", [["specif","particular"],["bond"],["gaseous","gas"]]),("Average value is the mean over the same bond type in different compounds or environments.", [["averag","mean"],["different","various"],["compound","environment","molecule"]])], "The first is process-specific; the second is a mean across molecular environments.")
mcq([6], "Which statement about a tabulated average O–H bond energy is valid?", ["It is a mean and need not equal the exact value in every gaseous compound.","It is identical for every O–H bond.","It is the energy released when an O–H bond is broken.","It applies directly to breaking an O–H bond in liquid water without other effects."], "A", "Tabulated average bond energies are means for gaseous bonds, whereas exact dissociation enthalpies depend on the molecule.", wrong={"B":"m7","C":"m5","D":"m7"})
short([6], "Why can successive C–H bond dissociations from methane have different enthalpy changes?", [("Each successive removal changes the molecule or radical environment.", [["chang","different"],["molecule","radical","environment"]]),("Therefore each particular C–H bond-breaking process can have a different exact energy.", [["different"],["energ","enthalp"]])], "Successive removal changes the species, so the exact bond dissociation enthalpies can differ.")
numeric([7], "[[m]] g of water warms by [[dt]] K. Calculate the heat absorbed in J using $c=4.18$ J g$^{-1}$ K$^{-1}$.", {"m":{"choices":[100,150,200]},"dt":{"choices":[8,12,16]}}, "m*4.18*dt", [("m*dt","m8"),("m*4.18*(273+dt)","m8")], "J", "Use the mass of water and the temperature change in $q=mc\\Delta T$.")
numeric([7], "[[n]] mol of a fuel burns and heats [[m]] g of water by [[dt]] K. Assuming all heat enters the water, calculate the fuel's molar enthalpy of combustion in kJ mol$^{-1}$; $c=4.18$ J g$^{-1}$ K$^{-1}$.", {"n":{"choices":[0.02,0.04,0.05]},"m":{"choices":[100,150,200]},"dt":{"choices":[5,8,10]}}, "-m*4.18*dt/(1000*n)", [("m*4.18*dt/(1000*n)","m1"),("-m*4.18*dt/1000","m8")], "kJ mol^-1", "Water absorbs $mc\\Delta T$ J. The fuel releases that energy, so $\\Delta H=-q/n$, converted from J to kJ.",4)

worked = []
def work(n,k,problem,steps,answer,unit,faded_problem,faded_answer):
    worked.append({"id":f"we{n}","kc":K[k],"problem":problem,"steps":[{"do":d,"why":w,**({"check":{"kind":"numeric","answer":{"value":answer,"unit":unit,"sf_ok":[2,3,4]}}} if j==len(steps)-1 else {})} for j,(d,w) in enumerate(steps)],"faded":{"id":f"we{n}f","problem":faded_problem,"answer":{"value":faded_answer,"unit":unit,"sf_ok":[2,3,4]},"blank_from":1}})

work(1,2,"A pathway has reactants at 20, products at 50 and peak at 100 kJ mol$^{-1}$. Find forward activation energy.",[("Read the reactant and peak levels: 20 and 100 kJ mol$^{-1}$.","Activation energy is measured from the starting level to the peak."),("$E_a=100-20=80$ kJ mol$^{-1}$.","Subtract the reactant level; a barrier cannot be negative.")],100-20,"kJ mol^-1","Reactants are at 30 and peak at 120 kJ mol$^{-1}$. Find forward activation energy.",120-30)
work(2,5,"Estimate $\\Delta H$ for $\\ce{H2 + Cl2 -> 2HCl}$ using 436, 242 and 431 kJ mol$^{-1}$ for H–H, Cl–Cl and H–Cl.",[("Broken: one H–H and one Cl–Cl, so $436+242=678$ kJ mol$^{-1}$.","The balanced equation fixes the bond counts."),("Formed: two H–Cl, so $2(431)=862$ kJ mol$^{-1}$.","Each product molecule contains one H–Cl bond."),("$\\Delta H=678-862=-184$ kJ mol$^{-1}$.","Energy absorbed for breaking minus energy released in forming sets the sign.")],436+242-2*431,"kJ mol^-1","For the same reaction, use H–H = 440, Cl–Cl = 240 and H–Cl = 430 kJ mol$^{-1}$. Estimate $\\Delta H$.",440+240-2*430)
work(3,7,"A reaction warms 100 g of water by 5.0 K; 0.020 mol reacts. Calculate $\\Delta H$, with $c=4.18$ J g$^{-1}$ K$^{-1}$.",[("$q=mc\\Delta T=100(4.18)(5.0)=2090$ J.","Use the mass of water and the temperature difference."),("$\\Delta H=-2090/(0.020\\times1000)=-104.5$ kJ mol$^{-1}$.","The reaction releases the heat absorbed by water; divide by moles and convert to kJ.")],-100*4.18*5/(0.02*1000),"kJ mol^-1","A reaction warms 150 g of water by 4.0 K; 0.025 mol reacts. Calculate $\\Delta H$ using $c=4.18$ J g$^{-1}$ K$^{-1}$.",-150*4.18*4/(0.025*1000))

flash = [
 (1,"What does negative $\\Delta H$ mean?","An exothermic reaction transfers energy to the surroundings; products have lower enthalpy than reactants."),
 (1,"What does positive $\\Delta H$ mean?","An endothermic reaction absorbs energy from the surroundings; products have higher enthalpy than reactants."),
 (3,"What are standard conditions for this syllabus?","$298\\,\\mathrm K$ and $101\\,\\mathrm{kPa}$, indicated by $\\ominus$."),
 (3,"Define standard enthalpy change of formation.","Enthalpy change when one mole of a compound is formed from its constituent elements in their standard states under standard conditions."),
 (3,"Define standard enthalpy change of combustion.","Enthalpy change when one mole of a substance is completely burned in oxygen under standard conditions, with substances in their standard states."),
 (3,"Define standard enthalpy change of neutralisation.","Enthalpy change when an aqueous acid and aqueous alkali react to form one mole of water under standard conditions."),
 (3,"Define standard enthalpy change of reaction.","Enthalpy change for the reaction in the stoichiometric amounts shown by its equation under standard conditions, with substances in their standard states."),
]
flashcards=[{"id":f"fc{i}","kc":K[k],"front":front,"back":back} for i,(k,front,back) in enumerate(flash,1)]

pack={"subtopic":SUB,"spec":"9701","version":1,"note":"Subjects/9701 Chemistry/05 Chemical energetics/5.1 Enthalpy change, ΔH.md",
"outline":"Reactions transfer energy through bond breaking and making. Exothermic changes have $\\Delta H<0$; endothermic changes have $\\Delta H>0$. On a pathway diagram, activation energy reaches the peak from reactants, while $\\Delta H$ compares products with reactants. Standard conditions here are $298\\,\\mathrm K$ and $101\\,\\mathrm{kPa}$. Formation, combustion and neutralisation enthalpies refer to one mole of product, fuel and water respectively. Bond-energy estimates use energy of bonds broken minus energy of bonds formed; averages need not equal exact values. Calorimetry uses $q=mc\\Delta T$ for the solution, then $\\Delta H=-q/n$ for the reaction.",
"misconceptions":mis,"worked":worked,"items":items,"flashcards":flashcards,
"diagrams":[{"file":"Assets/9701/9701-5.1-exothermic.svg","type":"energy_profile","params":{"reactants":80,"products":30,"ea":55,"reactants_label":"reactants","products_label":"products","ea_label":"activation energy","dh_label":"enthalpy change"}}]}

out=ROOT/"build/out/packs/9701/9701-5.1.json"
out.parent.mkdir(parents=True,exist_ok=True)
out.write_text(json.dumps(pack,ensure_ascii=False,indent=1))
errors=validate(pack,json.loads((ROOT/"build/out/specs/9701/graph.json").read_text()))
print("draft items",len(items),"templates",sum("template" in x for x in items),"errors",len(errors))
for e in errors: print(e)
