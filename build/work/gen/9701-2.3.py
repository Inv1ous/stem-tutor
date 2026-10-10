"""Build formula chapter; arithmetic and ratios are computed here."""
import json, math
from pathlib import Path
from fractions import Fraction
ROOT=Path(__file__).resolve().parents[3]
SUB='9701-2.3'; K=lambda n:f'{SUB}.{n}'
OUT=ROOT/f'build/out/packs/9701/{SUB}.json'
BANK={q['id']:q for q in json.loads((ROOT/'build/work/mcq/9701.tagged.json').read_text())}
AR={'H':1,'C':12,'N':14,'O':16,'Na':23,'S':32.1,'Li':6.9}
MR=lambda **d:sum(AR[k]*v for k,v in d.items())
assert math.isclose(MR(Na=2,S=1,O=4),142.1)
mis=[
('m1',1,'Subscripts in an ionic formula may be chosen without balancing charge.','The sum of positive and negative charges must be zero.','Two $\\ce{Ag+}$ ions balance one $\\ce{CO3^2-}$ ion: $\\ce{Ag2CO3}$.','research'),
('m2',2,'Subscripts may be changed to balance an equation.','Only coefficients may be changed; changing subscripts changes substances.','Balance $\\ce{2Mg + O2 -> 2MgO}$, not $\\ce{MgO2}$.','research'),
('m3',2,'A complete ionic equation includes spectator ions.','Cancel ions present unchanged on both sides.','$\\ce{Ag+(aq) + Cl-(aq) -> AgCl(s)}$ omits nitrate and sodium ions.','research'),
('m4',3,'An empirical formula is always the molecular formula.','The empirical formula is the simplest whole-number ratio; molecular formula gives actual atoms in one molecule.','$\\ce{P2O5}$ is empirical, whereas $\\ce{P4O10}$ is molecular.','ER 9701 w20 P21 Q2'),
('m5',4,'The water in a hydrate is surface moisture.','Water of crystallisation is incorporated in fixed proportions in the crystal structure.','$\\ce{CuSO4.5H2O}$ contains five waters per formula unit.','research'),
('m6',5,'Mass percentages can be used directly as atom ratios.','Divide each mass or percentage by the corresponding $A_r$ before simplifying.','For 40.0% C, 6.7% H, 53.3% O, the mole ratio is approximately $1:2:1$.','research')]
mis=[dict(id=i,kc=K(k),statement=s,refutation=r,contrast=c,source=src) for i,k,s,r,c,src in mis]
items=[]
def hints(topic):
 return ['Identify the information that controls the formula or equation.',f'Use {topic} before selecting the final result.','Write the relevant charges, atom counts or mole amounts first.']
def add(k,stem,answer,options,why,command='Deduce',diff=2,wrong=None):
 n=sum(x['source']['type']=='generated' for x in items)+1
 items.append(dict(id=f'{SUB}-i{n:02d}',kcs=[K(k)],kind='mcq',difficulty=diff,command_word=command,source={'type':'generated'},stem=stem,options=dict(zip('ABCD',options)),answer='ABCD'[answer],marks=1,explanation=why,hints=hints('charge balance' if k==1 else 'the defining relationship'),shuffle=True,distractors=wrong or {}))
def short(k,stem,answer,keywords,command='State',diff=2):
 n=sum(x['source']['type']=='generated' for x in items)+1
 items.append(dict(id=f'{SUB}-i{n:02d}',kcs=[K(k)],kind='short',difficulty=diff,command_word=command,source={'type':'generated'},stem=stem,marks=1,rubric=[{'point':answer,'keywords':keywords}],explanation=answer,hints=hints('the precise definition or procedure')))
def numeric(k,stem,value,unit,why,wrong=None,diff=3):
 n=sum(x['source']['type']=='generated' for x in items)+1
 items.append(dict(id=f'{SUB}-i{n:02d}',kcs=[K(k)],kind='numeric',difficulty=diff,command_word='Calculate',source={'type':'generated'},stem=stem,marks=2,answer={'value':round(value,6),'unit':unit,'sf_ok':[2,3]},distractors=wrong or [],explanation=why,hints=hints('moles and whole-number ratios')))
def past(qid,k,why):
 q=BANK[qid]; assert q['answer'] in (q.get('options') or dict.fromkeys('ABCD'))
 n=sum(x['source']['type']=='past' for x in items)+1
 it=dict(id=f'{SUB}-p{n:02d}',kcs=[K(k)],kind='mcq',difficulty=3,command_word=None,source={'type':'past','ref':q['ref'],'qid':qid},stem=q['stem'],options=q.get('options'),answer=q['answer'],marks=1,explanation=why)
 if q.get('image'):it['image']=q['image']
 items.append(it)
# Genuine past questions are loaded verbatim from the tagged bank.
for q,k,why in [
('9701_s24_12_q1',1,'Balance each formula by charge. C alone has $\\ce{AgHCO3}$ and $\\ce{K3PO4}$; A uses three ammonium ions for a single nitrate.'),
('9701_w20_13_q12',1,'The acidic +4 oxide identifies sulfur, while the amphoteric oxide identifies aluminium. Their ions give $\\ce{Al2S3}$; A pairs the wrong elements.'),
('9701_w24_13_q17',1,'Sulfate identifies sulfur and one mole of chlorine molecules forming a chloride identifies magnesium. The sodium alternative needs only half a mole of chlorine.'),
('9701_w19_12_q9',2,'Oxygen atoms require three halves of $\\ce{O2}$ per $\\ce{PbS}$, giving $\\ce{PbO}$ and $\\ce{SO2}$. Other options change the specified products.'),
('9701_w25_13_q17',2,'With four metal atoms and two oxide formula units, equations 1 and 3 can be balanced. Equation 2 has four Mg atoms but only two in the products.'),
('9701_w24_12_q3',2,'The amount of carbon dioxide equals the amount of carbon in the carbide. The mole ratio of Al to C leads to $\\ce{Al4C3}$; the alternatives have different ratios.'),
('9701_w20_12_q36',3,'Silicon dioxide has empirical formula $\\ce{SiO2}$, but phosphorus(V) oxide has molecular formula $\\ce{P4O10}$. B wrongly treats $\\ce{P2O5}$ as molecular.'),
('9701_w19_12_q21',3,'Simplify the molecular atom ratio by two to obtain $\\ce{C6H4N}$. C is the unsimplified molecular formula.'),
('9701_w24_13_q3',4,'The mole ratio of water lost to anhydrous sulfate is ten to one, so $x=10$. B uses an uncorrected mass ratio instead of mole amounts.'),
('9701_s25_12_q11',4,'Water lost is $R-S$ and dry lithium hydroxide is $S-Q$; divide each by its molar mass. The reverse difference gives an impossible negative amount.'),
('9701_w21_12_q1',5,'Convert each percentage to moles using $A_r$: the ratio C:H:O is $1:2:1$, giving $\\ce{CH2O}$. D omits one hydrogen.'),
('9701_w19_13_q25',5,'The percentage composition gives the formula of Y; its relative molecular mass fixes the multiplier. The other alcohols yield a different carbon count or oxidation product.')]:past(q,k,why)
# Retrieval, concept and exam-style variants for each outcome.
add(1,'Deduce the formula of zinc phosphate.',1,['ZnPO₄','Zn₃(PO₄)₂','Zn₂(PO₄)₃','Zn₃PO₄'],'Three $\\ce{Zn^2+}$ ions balance two $\\ce{PO4^3-}$ ions.',wrong={'A':'m1','B':'m1','C':'m1'} if False else {'A':'m1','C':'m1','D':'m1'})
add(1,'Deduce the formula of iron(III) sulfate.',2,['FeSO₄','Fe₃SO₄','Fe₂(SO₄)₃','Fe₃(SO₄)₂'],'Two $\\ce{Fe^3+}$ ions balance three $\\ce{SO4^2-}$ ions.',wrong={'A':'m1','B':'m1','D':'m1'})
short(1,'State the formula and charge of nitrate.','$\\ce{NO3-}$, charge −1.',['nitrate','NO3'])
short(1,'State the formula and charge of hydrogencarbonate.','$\\ce{HCO3-}$, charge −1.',['hydrogencarbonate','HCO3'])
add(2,'Deduce the simplest whole-number coefficients for $\\ce{Al + O2 -> Al2O3}$, in order.',1,['2, 3, 2','4, 3, 2','4, 2, 3','2, 1, 1'],'Atom conservation gives $\\ce{4Al + 3O2 -> 2Al2O3}$.',diff=4,wrong={'A':'m2','C':'m2','D':'m2'})
short(2,'State the net ionic equation for mixing aqueous silver nitrate and sodium chloride.','$\\ce{Ag+(aq) + Cl-(aq) -> AgCl(s)}$.',['Ag','Cl','AgCl'])
short(2,'Explain why $\\ce{Na+(aq)}$ is absent from the net ionic equation for precipitation of $\\ce{AgCl}$.','It is a spectator ion present unchanged on both sides of the full ionic equation.',['spectator','unchanged'],command='Explain')
add(3,'Identify the empirical formula of a molecule with molecular formula $\\ce{C6H12O6}$.',0,['CH₂O','C₆H₁₂O₆','C₂H₄O₂','CHO'],'Divide all atom numbers by six to get $\\ce{CH2O}$.',wrong={'B':'m4','C':'m4','D':'m4'})
short(3,'Define empirical formula.','The simplest whole-number ratio of atoms of each element in a compound.',['simplest','whole','ratio'],command='Define')
short(3,'Define molecular formula.','The actual number of atoms of each element in one molecule.',['actual','number','atoms','molecule'],command='Define')
short(3,'Compare empirical and molecular formula for $\\ce{P4O10}$.','Its molecular formula is $\\ce{P4O10}$ and empirical formula is $\\ce{P2O5}$.',['P4O10','P2O5'],command='Compare')
add(3,'Identify a possible molecular formula for empirical formula $\\ce{CH2}$.',2,['CH₃','C₂H₂','C₃H₆','C₃H₈'],'A molecular formula must be an integer multiple of the empirical formula.',wrong={'A':'m4','B':'m4','D':'m4'})
short(4,'Define anhydrous.','Anhydrous means containing no water of crystallisation.',['no','water','crystallisation'],command='Define')
short(4,'Define water of crystallisation.','Water incorporated in fixed proportions in the crystal structure of a hydrated salt.',['water','fixed','crystal'],command='Define')
short(4,'Describe what hydrated means for a crystalline salt.','It contains water of crystallisation in its crystal structure.',['water','crystallisation','crystal'],command='Describe')
add(4,'Identify the anhydrous substance formed by heating $\\ce{CuSO4.5H2O}$ without decomposition.',0,['CuSO₄','CuSO₄·H₂O','CuO','Cu₂SO₄'],'Removing all water of crystallisation leaves $\\ce{CuSO4}$.',wrong={'B':'m5','C':'m5','D':'m5'})
short(4,'Explain why the dot in $\\ce{MgSO4.7H2O}$ does not represent a mixture with arbitrary water.','Seven water molecules occur per magnesium sulfate formula unit in the crystal.',['seven','water','crystal'],command='Explain')
ratio=[40.0/AR['C'],6.7/AR['H'],53.3/AR['O']]; scaled=[v/min(ratio) for v in ratio];assert all(abs(a-b)<0.02 for a,b in zip(scaled,[1,2,1]))
add(5,'Deduce the empirical formula from 40.0% C, 6.7% H and 53.3% O by mass.',0,['CH₂O','C₂H₄O','CHO','CH₄O'],'Divide each percentage by its $A_r$; the resulting mole ratio is approximately $1:2:1$.',diff=4,wrong={'B':'m6','C':'m6','D':'m6'})
numeric(5,'Calculate the multiplier from empirical formula $\\ce{CH2O}$ to molecular formula when $M_r=180$.',180/MR(C=1,H=2,O=1),'','The empirical formula mass is 30, so the multiplier is $180/30=6$.',diff=4)
numeric(5,'Calculate the number of water molecules per formula unit when $1.91\\,\\mathrm{g}$ of water is removed from $1.51\\,\\mathrm{g}$ of anhydrous $\\ce{Na2SO4}$.',round((1.91/MR(H=2,O=1))/(1.51/MR(Na=2,S=1,O=4))),'','Divide the moles of water by the moles of dry salt; the ratio rounds to ten.',diff=4)
short(5,'Describe the steps to find an empirical formula from elemental masses.','Divide each mass by its $A_r$, then divide all mole values by the smallest and convert to whole numbers.',['divide','mass','smallest','whole'],command='Describe')
add(5,'Deduce the molecular formula for empirical formula $\\ce{CH2}$ and $M_r=56$.',1,['C₂H₄','C₄H₈','C₃H₆','C₅H₁₀'],'The empirical formula mass is 14; $56/14=4$, so multiply each subscript by four.',diff=4,wrong={'A':'m6','C':'m6','D':'m6'})
worked=[]
def work(k,problem,steps,faded_problem,faded_answer):
 worked.append({'id':f'we{k}','kc':K(k),'problem':problem,'steps':steps,'faded':{'id':f'we{k}f','problem':faded_problem,'answer':{'value':faded_answer,'unit':'','exact':True},'blank_from':1}})
work(1,'Deduce the number of sulfate ions in iron(III) sulfate.',[{'do':'Write $\\ce{Fe^3+}$ and $\\ce{SO4^2-}$.','why':'The Roman numeral gives the iron oxidation number.'},{'do':'Find the least common charge: $2(3)=3(2)=6$.','why':'The overall ionic compound is neutral.','check':{'kind':'numeric','answer':{'value':6,'unit':'','exact':True}}},{'do':'Write $\\ce{Fe2(SO4)3}$: three sulfate ions.','why':'Brackets preserve the polyatomic ion.'}],'Deduce the number of nitrate ions in aluminium nitrate.',3)
work(2,'Balance $\\ce{Al + O2 -> Al2O3}$ and give the oxygen coefficient.',[{'do':'Place 2 before $\\ce{Al2O3}$ to make six product oxygen atoms.','why':'Oxygen is supplied in pairs.'},{'do':'Place 3 before $\\ce{O2}$ and 4 before Al.','why':'Conserve oxygen and aluminium atoms.','check':{'kind':'numeric','answer':{'value':3,'unit':'','exact':True}}},{'do':'Check $\\ce{4Al + 3O2 -> 2Al2O3}$.','why':'Both sides have four Al and six O atoms.'}],'Balance $\\ce{Fe + O2 -> Fe2O3}$; give the oxygen coefficient.',3)
work(5,'Find the multiplier for empirical formula $\\ce{CH2O}$ with $M_r=180$.',[{'do':'Calculate empirical formula mass: $12+2(1)+16=30$.','why':'Use periodic-table $A_r$ values.'},{'do':'Divide $M_r$ by empirical mass: $180/30=6$.','why':'The molecular formula is an integer multiple.','check':{'kind':'numeric','answer':{'value':6,'unit':'','exact':True}}},{'do':'Multiply subscripts to obtain $\\ce{C6H12O6}$.','why':'Retain the same atom ratio.'}],'Find the multiplier for $\\ce{CH2}$ when $M_r=56$.',56/MR(C=1,H=2))
flash=[]
for k,front,back in [(1,'What is the formula of sulfate?','$\\ce{SO4^2-}$.'),(1,'What is the formula of ammonium?','$\\ce{NH4+}$.'),(3,'Define empirical formula.','The simplest whole-number ratio of atoms of each element in a compound.'),(3,'Define molecular formula.','The actual number of atoms of each element in one molecule.'),(4,'Define anhydrous.','Containing no water of crystallisation.'),(4,'Define water of crystallisation.','Water incorporated in fixed proportions in a crystal structure.')]:flash.append({'id':f'fc{len(flash)+1}','kc':K(k),'front':front,'back':back})
pack={'subtopic':SUB,'spec':'9701','version':1,'note':'Subjects/9701 Chemistry/02 Atoms, molecules and stoichiometry/2.3 Formulas.md','outline':'Predict ion charge from the periodic table and balance charges to write neutral ionic formulae. Conserve atoms and charge in full and net ionic equations, then include state symbols. Empirical formula gives the simplest whole-number atom ratio; molecular formula gives the actual atoms in one molecule. Hydrates contain a fixed amount of water of crystallisation. Convert elemental masses into moles, simplify their ratio, then use $M_r$ to obtain a molecular formula.','misconceptions':mis,'worked':worked,'items':items,'flashcards':flash,'diagrams':[]}
OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(pack,ensure_ascii=False,indent=1))
print(len(items),len(worked))
