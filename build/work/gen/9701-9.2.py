import json
from pathlib import Path
from sympy import Eq, symbols, solve

ROOT=Path(__file__).resolve().parents[3]
sub='9701-9.2'; kc=lambda n:f'{sub}.{n}'
note='Subjects/9701 Chemistry/09 The Periodic Table: chemical periodicity/9.2 Periodicity of chemical properties of the elements in Period 3.md'
mis=[
('m1',1,'Every Period 3 element reacts with water.','Only Na and Mg are specified for elemental reactions with water.','Elemental reactions differ from oxide and chloride hydrolysis.','research'),
('m2',2,'Oxidation number is the number of oxygen atoms in a formula.','Assign O as −2 and Cl as −1, then balance the sum to zero.','In $\\ce{P4O10}$, P is +5 although there are ten O atoms.','ER 9701 s23 P22 Q2'),
('m3',3,'All Period 3 oxides dissolve in water.','Aluminium oxide and silicon dioxide do not react with water; MgO reacts only slightly.','An oxide may react with acid or base without dissolving in water.','research'),
('m4',4,'Amphoteric means neutral or unreactive.','Amphoteric $\\ce{Al2O3}$ and $\\ce{Al(OH)3}$ react with both acids and aqueous NaOH.','MgO is basic; phosphorus and sulfur oxides are acidic.','research'),
('m5',5,'Every chloride gives a neutral solution on addition to water.','NaCl is neutral; MgCl2 is slightly acidic and AlCl3, SiCl4 and PCl5 give acidic solutions.','Hydrolysis differs from simple dissolution.','ER 9701 w22 P21 Q3'),
('m6',6,'Silicon tetrachloride is a giant covalent solid.','SiCl4 is simple molecular and hydrolyses; SiO2 is giant covalent.','The same element can form compounds with different structures.','ER 9701 w22 P22 Q2'),
('m7',7,'A high melting point always means ionic bonding.','Giant covalent SiO2 also has a high melting point; combine melting and reaction evidence.','Simple molecular chlorides have low melting points.','research')]
mis=[dict(id=a,kc=kc(b),statement=c,refutation=d,contrast=e,source=f) for a,b,c,d,e,f in mis]
items=[]
def short(n,stem,points,d=2):
 i=len(items)+1
 items.append(dict(id=f'{sub}-i{i:02}',kcs=[kc(n)],kind='short',difficulty=d,command_word='Describe' if n in (1,3,5) else 'Explain' if n in (2,4,6) else 'Suggest',source={'type':'generated'},stem=stem,marks=len(points),rubric=[{'point':p,'keywords':[[q]]} for p,q in points],explanation='; '.join(p for p,q in points)+'.',hints=['Identify the relevant species or property.','Recall the Period 3 pattern.','Start with the bonding or balanced equation.']))
def mcq(n,stem,options,ans,ex,d=3,dm=None):
 i=len(items)+1
 items.append(dict(id=f'{sub}-i{i:02}',kcs=[kc(n)],kind='mcq',difficulty=d,command_word='Identify',source={'type':'generated'},stem=stem,marks=1,options=dict(zip('ABCD',options)),answer=ans,distractors=dm or {},shuffle=True,explanation=ex,hints=['Use the Period 3 trend.','Check which species actually reacts.','Eliminate choices with the wrong bonding or product.']))
def past(pid,n,stem,opts,ans,ex,image=None):
 x=dict(id=f'{sub}-p{len([i for i in items if i["source"]["type"]=="past"])+1:02}',kcs=[kc(n)],kind='mcq',difficulty=3,command_word='Identify',source={'type':'past','ref':pid},stem=stem,marks=1,options=dict(zip('ABCD',opts)),answer=ans,explanation=ex,hints=['Recall the relevant Period 3 trend.','Check each compound or reaction.','Apply the equation or bonding evidence.'])
 if image:x['image']='Assets/mcq/'+pid+'.png'
 items.append(x)
# Each reaction is balanced by solving atom counts where applicable.
reactions=[('Na','O2','Na2O',4,1,2),('Mg','O2','MgO',2,1,2),('Al','O2','Al2O3',4,3,2),('P4','O2','P4O10',1,5,1),('S','O2','SO2',1,1,1)]
for e,o,p,a,b,c in reactions:
 short(1,f'Describe the reaction of {e} with oxygen and give a balanced equation.',[(f'{a}{e} + {b}{o} → {c}{p}',p)],3)
short(1,'Describe the reactions of sodium and magnesium with cold water.', [('Sodium reacts vigorously: 2Na + 2H2O → 2NaOH + H2','2Na'),('Magnesium reacts very slowly: Mg + 2H2O → Mg(OH)2 + H2','Mg +')],4)
# oxidation numbers computed from the neutral-compound sum
for formula,atoms,charge in [('Na2O',2,2),('MgO',1,2),('Al2O3',2,6),('P4O10',4,20),('SO2',1,4),('SO3',1,6),('SiCl4',1,4),('PCl5',1,5)]:
 x=symbols('x'); val=int(solve(Eq(atoms*x-charge,0),x)[0]); short(2,f'Determine the oxidation number of the Period 3 element in {formula}.',[(f'{val:+d}: the oxidation numbers sum to zero',str(val))],2)
for oxide,observation,eq in [('Na2O','strongly alkaline, pH about 13–14','Na2O + H2O → 2NaOH'),('MgO','weakly alkaline, pH about 9–10','MgO + H2O → Mg(OH)2'),('Al2O3','no reaction; no solution','No reaction'),('SiO2','no reaction; no solution','No reaction'),('P4O10','acidic, pH about 1–2','P4O10 + 6H2O → 4H3PO4'),('SO2','acidic, pH about 2–3','SO2 + H2O ⇌ H2SO3'),('SO3','strongly acidic, pH about 1','SO3 + H2O → H2SO4')]:
 short(3,f'Describe what happens when {oxide} is added to water, including the likely pH and equation if it reacts.',[(observation,observation.split(',')[0]),(eq,eq.split(' ')[0])],3)
for formula,why in [('Na2O','basic oxide; reacts with acids'),('MgO','basic oxide; reacts with acids'),('Al2O3','amphoteric; reacts with acids and NaOH'),('P4O10','acidic oxide; reacts with NaOH'),('SO2','acidic oxide; reacts with NaOH'),('SO3','acidic oxide; reacts with NaOH'),('NaOH','strong base; neutralises acids'),('Mg(OH)2','base; neutralises acids'),('Al(OH)3','amphoteric; reacts with acids and NaOH')]:
 short(4,f'Explain the acid–base behaviour of {formula}.',[(why,why.split(';')[0])],3)
# Manager-directed corrections to acid-base behaviour items.
acid_base = {
22: ("Explain the acid-base behaviour of Na2O and write a balanced equation for its reaction with aqueous HCl.", "Basic oxide; neutralises acids.", ["Na2O + 2HCl → 2NaCl + H2O"]),
23: ("Explain the acid-base behaviour of MgO and write a balanced equation for its reaction with aqueous HCl.", "Basic oxide; neutralises acids.", ["MgO + 2HCl → MgCl2 + H2O"]),
24: ("Explain the amphoteric behaviour of Al2O3. Write balanced equations for its reactions with aqueous HCl and excess aqueous NaOH.", "Amphoteric; reacts with both acids and bases.", ["Al2O3 + 6HCl → 2AlCl3 + 3H2O", "Al2O3 + 2NaOH + 3H2O → 2Na[Al(OH)4]"]),
25: ("Explain the acid-base behaviour of P4O10 and write a balanced equation for its complete neutralisation by excess aqueous NaOH.", "Acidic oxide; neutralises bases.", ["P4O10 + 12NaOH → 4Na3PO4 + 6H2O"]),
26: ("Explain the acid-base behaviour of SO2 and write a balanced equation for its complete neutralisation by excess aqueous NaOH.", "Acidic oxide; neutralises bases.", ["SO2 + 2NaOH → Na2SO3 + H2O"]),
27: ("Explain the acid-base behaviour of SO3 and write a balanced equation for its complete neutralisation by excess aqueous NaOH.", "Acidic oxide; neutralises bases.", ["SO3 + 2NaOH → Na2SO4 + H2O"]),
28: ("Explain the acid-base behaviour of NaOH and write a balanced equation for its reaction with aqueous HCl.", "Base; neutralises acids.", ["NaOH + HCl → NaCl + H2O"]),
29: ("Explain the acid-base behaviour of Mg(OH)2 and write a balanced equation for its reaction with aqueous HCl.", "Base; neutralises acids.", ["Mg(OH)2 + 2HCl → MgCl2 + 2H2O"]),
30: ("Explain the amphoteric behaviour of Al(OH)3. Write balanced equations for its reactions with aqueous HCl and excess aqueous NaOH.", "Amphoteric; reacts with both acids and bases.", ["Al(OH)3 + 3HCl → AlCl3 + 3H2O", "Al(OH)3 + NaOH → Na[Al(OH)4]"]),
}
for number, (stem, classification, equations) in acid_base.items():
    item = items[number - 1]
    item.update(stem=stem, command_word="Explain", marks=1 + len(equations),
                rubric=[{"point": classification, "keywords": [[classification.split(';')[0]]]}] +
                       [{"point": f"Balanced equation with correct products and stoichiometry: {eq}; accept equivalent balanced net ionic equations.", "keywords": [["correct products", "stoichiometry"]]} for eq in equations],
                explanation=classification + " " + " ".join(equations))

for formula,description,eq in [('NaCl','dissolves, approximately neutral pH 7','NaCl(s) → Na+(aq) + Cl−(aq)'),('MgCl2','dissolves, slightly acidic pH about 6','MgCl2(s) → Mg2+(aq) + 2Cl−(aq)'),('AlCl3','hydrolyses, acidic pH about 3','AlCl3 + 6H2O → [Al(H2O)6]3+ + 3Cl−'),('SiCl4','vigorous hydrolysis, white SiO2 and steamy HCl fumes, acidic pH about 1–2','SiCl4 + 2H2O → SiO2 + 4HCl'),('PCl5','vigorous hydrolysis, steamy HCl fumes, strongly acidic pH about 1','PCl5 + 4H2O → H3PO4 + 5HCl')]:
 short(5,f'Describe adding {formula} to excess water, including the likely pH.',[(description,description.split(',')[0]),(eq,eq.split(' ')[0])],3)
for stem,p in [('Explain why NaCl dissolves without hydrolysis but SiCl4 hydrolyses.','NaCl is ionic; SiCl4 is covalent and water attacks electron-deficient silicon.'),('Explain why acidity of Period 3 oxides increases across the period.','Electronegativity rises, bonding becomes more covalent and non-metal oxides form acids in water.'),('Explain why MgCl2 solution is slightly acidic.','Hydrated Mg2+ polarises coordinated water and releases H+.'),('Explain why Al2O3 is amphoteric.','Its intermediate bonding and aluminium ion charge density permit reaction with acids and bases.'),('Explain why SiO2 and SiCl4 differ in melting point.','SiO2 is giant covalent; SiCl4 consists of simple molecules with weak intermolecular forces.'),('Explain the trend in chloride bonding from sodium to phosphorus.','Ionic character falls and covalent character rises as electronegativity increases across Period 3.')]:short(6,stem,[(p,p.split(' ')[0])],4)
for obs,ans in [('A chloride has a high melting point and conducts when molten.','ionic'),('An oxide is insoluble in water and has a very high melting point.','giant covalent is plausible'),('A chloride is a volatile liquid that hydrolyses in water.','simple covalent molecules'),('An oxide conducts when molten and neutralises acid.','ionic basic oxide'),('A chloride has a low boiling point and does not conduct electricity.','simple molecular covalent'),('An oxide forms an acidic solution and has a low melting point.','simple molecular covalent')]:short(7,f'Suggest the bonding from this observation: {obs}',[(ans,ans.split(' ')[0])],4)
past('9701_w22_13_q25',3,'Separate 1.0 g samples of Na₂O, MgO, Al₂O₃, SiO₂, NaCl, MgCl₂, Al₂Cl₆ and SiCl₄ are added to separate beakers containing water and stirred. The number of beakers containing a white solid is Q. An excess of NaOH(aq) is then added to each beaker and stirred. The number of beakers now containing a white solid is R. Which row is correct? Q R',['3 2','3 3','4 3','4 4'],'D','Q is four: MgO, Al₂O₃, SiO₂ and SiCl₄ give white solids. R is four: MgO, SiO₂, MgCl₂ and SiCl₄. C misses one solid after NaOH.', '9701_w22_13_q25')
past('9701_s22_12_q17',5,'NH₃(aq) is added to separate samples of NaCl(aq), MgCl₂(aq), BaCl₂(aq) and SiCl₄(l). Under the conditions of this experiment, only two samples will produce a white precipitate when NH₃(aq) is added. What are these two samples?',['MgCl₂(aq) and BaCl₂(aq)','MgCl₂(aq) and SiCl₄(l)','NaCl(aq) and BaCl₂(aq)','NaCl(aq) and SiCl₄(l)'],'B','OH− from aqueous ammonia precipitates Mg(OH)₂; water hydrolyses SiCl₄ to white SiO₂. A overlooks water in aqueous ammonia.')
past('9701_w25_12_q23',4,'Element E is in Period 3. It forms a chloride which reacts with a small amount of water to produce a white precipitate and steamy fumes. This precipitate is soluble in NaOH(aq) and in HCl(aq). What is element E?',['magnesium','aluminium','silicon','phosphorus'],'B','Aluminium chloride gives amphoteric Al(OH)₃ with limited water; it dissolves in acid and base. Silicon dioxide does not dissolve in HCl.')
past('9701_w25_12_q18',3,'Compound X is an oxide of a Period 3 element. Compound X is a white solid at 25 °C. It reacts with water to form an acidic solution. What is compound X?',['aluminium oxide','silicon dioxide','sulfur dioxide','phosphorus(V) oxide'],'D','P₄O₁₀ is a white solid that produces phosphoric acid. Sulfur dioxide is acidic but is a gas at 25 °C.')
past('9701_w24_13_q18',5,'Q is a semi-conductor. The chloride of Q reacts with water to form white fumes and an acidic solution. Which Period 3 element is Q?',['magnesium','aluminium','silicon','phosphorus'],'C','Silicon is a semiconductor and SiCl₄ hydrolyses to HCl, giving acidic white fumes. Aluminium is a metal.')
past('9701_w24_13_q16',4,'What are the acid–base nature and structure of SO₂?',['acidic giant covalent lattice','acidic simple molecular','basic giant covalent lattice','basic simple molecular'],'B','SO₂ is an acidic simple molecular oxide. A assigns it the giant structure of SiO₂.','9701_w24_13_q16')
past('9701_w24_12_q18',1,'Sodium and sulfur are burned separately in oxygen. Each reaction has a distinctive coloured flame. Which row is correct? Na + O₂ / S + O₂',['white flame / blue flame','white flame / yellow flame','yellow flame / blue flame','yellow flame / yellow flame'],'C','Sodium burns with a yellow flame and sulfur with a blue flame. D gives sulfur the sodium flame colour.','9701_w24_12_q18')
past('9701_w24_12_q17',4,'Which oxide is insoluble in aqueous sodium hydroxide?',['MgO','Al₂O₃','P₄O₁₀','SO₂'],'A','Basic MgO does not dissolve in aqueous NaOH. Amphoteric Al₂O₃ and acidic P₄O₁₀ and SO₂ react with it.')
past('9701_w21_13_q12',1,'Which element requires the least number of moles of oxygen for the complete combustion of 1 mol of its atoms?',['aluminium','magnesium','phosphorus','sodium'],'D','Sodium uses 0.25 mol O₂ per mole of atoms to form Na₂O; magnesium uses 0.5 mol. A uses 0.75 mol.')
past('9701_w21_12_q12',4,'A mixture of two Period 3 oxides are added to water. A solution forms with a pH of just below 7. What could be the constituents of the mixture?',['Al₂O₃ and MgO','Na₂O and MgO','Na₂O and P₄O₁₀','SO₃ and P₄O₁₀'],'C','Na₂O produces alkali, which can partly neutralise acid from P₄O₁₀. D combines two acidic oxides.')
past('9701_w20_12_q19',4,'Compound X is the oxide of a Period 3 element. Compound X reacts with water to give an acidic solution. A solution is prepared by reacting 0.100 g of compound X with an excess of water. This solution is neutralised by exactly 25.0 cm³ of 0.100 mol dm⁻³ sodium hydroxide solution. What could be the identity of compound X?',['Al₂O₃','MgO','P₄O₁₀','SO₃'],'D','SO₃ has molar mass 80.0; 0.100 g makes 0.00125 mol H₂SO₄, requiring 0.00250 mol NaOH. P₄O₁₀ requires a different amount.')
past('9701_w20_12_q12',7,'Element X, in Period 3, has the following properties. Its oxide has a giant structure. It forms covalent bonds with chlorine. Its oxide will neutralise HCl(aq). What is element X?',['Mg','Al','Si','P'],'B','Al₂O₃ has a giant structure and neutralises acid, while AlCl₃ has covalent character. Silicon oxide does not neutralise HCl.')
# Manager-directed correction: aluminium chloride hydration and acid-producing hydrolysis.
i33 = items[32]
i33.update(
    stem="Describe what happens when AlCl3 is added to excess water and state the likely pH. Write an equation for formation of the hydrated aluminium ion. Explain why this ion makes the solution acidic and write its first hydrolysis equilibrium.",
    command_word="Explain", marks=5,
    rubric=[
        {"point":"Dissolves to give an acidic solution, typically pH about 3 (concentration dependent).", "keywords":[["acidic solution", "pH about 3"]]},
        {"point":"Balanced hydration equation with correct species and charges: AlCl3 + 6H2O → [Al(H2O)6]3+ + 3Cl−.", "keywords":[["AlCl3", "[Al(H2O)6]3+", "3Cl−"]]},
        {"point":"The small, highly charged Al3+ ion has high charge density and polarises the O-H bonds in coordinated water.", "keywords":[["high charge density", "polarises", "O-H"]]},
        {"point":"These weakened O-H bonds allow a proton to transfer to water, producing H3O+ and lowering pH.", "keywords":[["proton transfer", "H3O+", "lowering pH"]]},
        {"point":"Balanced first hydrolysis equilibrium with correct species and charges: [Al(H2O)6]3+ + H2O ⇌ [Al(H2O)5(OH)]2+ + H3O+; accept equivalent [Al(H2O)6]3+ ⇌ [Al(H2O)5(OH)]2+ + H+.", "keywords":[["[Al(H2O)6]3+", "[Al(H2O)5(OH)]2+", "H3O+", "H+"]]}
    ],
    explanation="AlCl3 dissolves to give an acidic solution, typically pH about 3 (concentration dependent). Hydration forms [Al(H2O)6]3+: AlCl3 + 6H2O → [Al(H2O)6]3+ + 3Cl−. The small, highly charged Al3+ ion has high charge density and polarises O-H bonds in coordinated water. These weakened bonds allow a proton to transfer to water, producing H3O+ and lowering pH. Acid-producing hydrolysis is distinct from hydration: [Al(H2O)6]3+ + H2O ⇌ [Al(H2O)5(OH)]2+ + H3O+ (or [Al(H2O)6]3+ ⇌ [Al(H2O)5(OH)]2+ + H+).",
    hints=["Identify the ion formed when aluminium chloride dissolves.", "Consider the charge density of Al3+ and its effect on coordinated water.", "Transfer one proton from a coordinated water molecule to another water molecule."]
)

worked=[]
for n,prob,eq,answer in [(1,'Balance the formation of magnesium oxide.','2Mg + O2 → 2MgO','2Mg + O2 → 2MgO'),(3,'State the reaction of phosphorus(V) oxide with water.','P4O10 + 6H2O → 4H3PO4','P4O10 + 6H2O → 4H3PO4'),(5,'State the complete hydrolysis of phosphorus(V) chloride.','PCl5 + 4H2O → H3PO4 + 5HCl','PCl5 + 4H2O → H3PO4 + 5HCl'),(7,'Use low boiling point and no electrical conductivity to suggest the bonding in SiCl4.','Weak forces between simple molecules; covalent bonds within each molecule.','simple molecular covalent')]:
 worked.append(dict(id=f'we{n}',kc=kc(n),problem=prob,steps=[{'do':eq,'why':'Use the observed product and conserve atoms, or match the physical evidence to bonding.'}],faded={'id':f'we{n}f','problem':{1:'For 4 mol Mg, calculate the moles of oxygen needed.',3:'For 1 mol P4O10, calculate the moles of water needed.',5:'For 1 mol PCl5, calculate the moles of water needed.',7:'How many covalent Si–Cl bonds are in one SiCl4 molecule?'}[n],'answer':{'value':{1:2,3:6,5:4,7:4}[n],'unit':'mol' if n != 7 else '', 'sf_ok':[1,2,3]},'blank_from':0}))
flash=[dict(id=f'fc{n}',kc=kc(n),front=q,back=a) for n,q,a in [(2,'What determines the highest oxidation number across Na to P?','The number of outer-shell electrons rises from one to five.'),(4,'What does amphoteric mean?','A substance that reacts with both acids and bases.'),(6,'Why do oxides become more acidic across Period 3?','Bonding becomes more covalent as electronegativity rises across the period.')]]
pack=dict(subtopic=sub,spec='9701',version=1,note=note,outline='Across Period 3, valence electrons and electronegativity increase. Oxides change from basic through amphoteric to acidic; chlorides change from mostly ionic to covalent. Use balanced equations, observed pH and physical properties to infer reactions and bonding.',misconceptions=mis,worked=worked,items=items,flashcards=flash,diagrams=[])
out=ROOT/'build/out/packs/9701'/f'{sub}.json';out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(pack,ensure_ascii=False,indent=1))
print(len(items),len(worked),out)
