"""Generate and arithmetically check the 9701-14.1 teaching pack."""
import json
from pathlib import Path
from fractions import Fraction

ROOT = Path(__file__).resolve().parents[3]
SUB = '9701-14.1'
KC = lambda n: f'{SUB}.{n}'
H = ['Recall the relevant bond or reaction change.', 'Use the reagent and conditions to identify the process.', 'Start by stating the species or products involved.']
mis = [
 ('m1',1,'Hydrogenation of an alkene needs ultraviolet light.','Hydrogenation uses hydrogen with a Pt or Ni catalyst and heat; UV light initiates halogen substitution.','Distinguish addition of hydrogen from free-radical substitution.','research'),
 ('m2',2,'Incomplete combustion always produces carbon dioxide only.','Limited oxygen can form carbon monoxide or carbon as well as water.','Complete combustion produces carbon dioxide and water.','ER 9701 w19 P21 Q3'),
 ('m3',3,'A propagation step joins two radicals.','Radical–radical combination consumes radicals and is termination; propagation regenerates one.','Check the number of radicals before and after the step.','ER 9701 s23 P21 Q3'),
 ('m4',4,'Cracking only makes alkanes.','Cracking a long hydrocarbon commonly produces shorter alkanes and alkenes.','Balance both carbon and hydrogen atoms in candidate products.','ER 9701 s19 P22 Q4'),
 ('m5',5,'A polar reagent readily attacks a C–H bond in an alkane.','The C–H bond is strong and relatively non-polar, so polar reagents do not readily attack it.','Bond strength and bond polarity are separate parts of the explanation.','research'),
 ('m6',6,'A catalytic converter prevents all greenhouse-gas emissions.','It oxidises CO and unburnt hydrocarbons and reduces nitrogen oxides, but forms CO2.','Name the pollutant converted and its product.','research'),
 ('m7',3,'UV light breaks chlorine into ions.','UV light causes homolytic fission of Cl–Cl to give two chlorine radicals.','Each chlorine atom receives one electron from the bond.','research'),
 ('m8',4,'A cracking equation only needs its carbon atoms balanced.','Both carbon and hydrogen atoms must balance across the products.','Check each element separately.','ER 9701 s19 P22 Q4'),
]
misconceptions=[dict(id=i,kc=KC(k),statement=s,refutation=r,contrast=c,source=src) for i,k,s,r,c,src in mis]
items=[]
def short(k,stem,points,d=2,word='Describe'):
 n=len(items)+1
 items.append(dict(id=f'{SUB}-i{n:02}',kcs=[KC(k)],kind='short',difficulty=d,command_word=word,source={'type':'generated'},stem=stem,marks=len(points),rubric=[{'point':p,'keywords':[[q] for q in keys]} for p,keys in points],explanation=' '.join(p for p,_ in points),hints=H))
def mcq(k,stem,opts,key,explain,wrong=None,d=2,word='Identify'):
 n=len(items)+1
 items.append(dict(id=f'{SUB}-i{n:02}',kcs=[KC(k)],kind='mcq',difficulty=d,command_word=word,source={'type':'generated'},stem=stem,options=dict(zip('ABCD',opts)),answer=key,distractors=wrong or {},shuffle=True,marks=1,explanation=explain,hints=H))

# Preparation: conditions, bond change and balanced equations.
short(1,'Describe the reagents and conditions used to convert ethene into ethane.', [('Add hydrogen gas to ethene.', ['hydrogen']),('Use a platinum or nickel catalyst and heat.', ['catalyst','heat'])])
short(1,'Describe the reagents and conditions for cracking a long-chain alkane.', [('Heat the alkane with aluminium oxide catalyst.', ['heat','aluminium oxide'])])
mcq(1,'Identify the process in $\\ce{C2H4 + H2 -> C2H6}$.',['cracking','hydrogenation','substitution','combustion'],'B','Hydrogen adds across the alkene double bond to give an alkane.',{'C':'m1'})
mcq(1,'Identify the conditions that convert an alkene to an alkane.',['$\\ce{H2}$, Ni and heat','$\\ce{Cl2}$ and UV light','$\\ce{Al2O3}$ and heat','oxygen and a spark'],'A','Hydrogenation requires hydrogen, a Ni or Pt catalyst and heat.',{'B':'m1'})
short(1,'Give a balanced equation for hydrogenating propene.', [('$\\ce{C3H6 + H2 -> C3H8}$',['C3H6','H2','C3H8'])],word='Give')
short(1,'A heated long-chain alkane passes over $\\ce{Al2O3}$. Describe the reaction type and give one possible pair of product types.', [('Cracking breaks larger hydrocarbon molecules into smaller molecules.', ['cracking','smaller']),('Products can include a shorter alkane and an alkene.', ['alkane','alkene'])],d=4)

# Combustion and ethane halogenation.
short(2,'Describe complete combustion of ethane, including the products and a balanced equation.', [('$\\ce{2C2H6 + 7O2 -> 4CO2 + 6H2O}$.',['C2H6','O2','CO2','H2O'])])
short(2,'Describe two possible carbon-containing products of incomplete combustion of an alkane.', [('Carbon monoxide may form.', ['carbon monoxide']),('Solid carbon (soot) may form.', ['carbon'])])
mcq(2,'Identify the organic product of the first substitution of ethane by chlorine in ultraviolet light.',['ethene','chloroethane','ethanol','ethanal'],'B','One hydrogen atom in ethane is replaced by chlorine to form chloroethane and HCl.')
short(2,'Describe the reaction of ethane with bromine under ultraviolet light.', [('A hydrogen atom is substituted by bromine by a free-radical reaction.', ['substituted','free-radical']),('Bromoethane and hydrogen bromide form in the first substitution.', ['bromoethane','hydrogen bromide'])],d=4)

# Radical mechanism.
short(3,'Describe initiation in the chlorination of ethane.', [('$\\ce{Cl2 -> 2Cl^{\\bullet}}$ under ultraviolet light by homolytic fission.', ['Cl2','UV','homolytic'])])
short(3,'Describe both propagation steps for the first chlorination of ethane.', [('$\\ce{C2H6 + Cl^{\\bullet} -> C2H5^{\\bullet} + HCl}$.',['C2H6','HCl']),('$\\ce{C2H5^{\\bullet} + Cl2 -> C2H5Cl + Cl^{\\bullet}}$.',['C2H5Cl','Cl2'])],d=4)
short(3,'Give two valid termination equations in the chlorination of ethane.', [('$\\ce{C2H5^{\\bullet} + Cl^{\\bullet} -> C2H5Cl}$.',['C2H5','Cl']),('$\\ce{C2H5^{\\bullet} + C2H5^{\\bullet} -> C4H10}$.',['C4H10'])],word='Give')
mcq(3,'Identify the step type when $\\ce{C2H5^{\\bullet} + Cl2 -> C2H5Cl + Cl^{\\bullet}}$.',['initiation','propagation','termination','hydrogenation'],'B','A radical reacts, makes product and regenerates a radical, so the chain propagates.',{'C':'m3'})

# Cracking fractions.
short(4,'Suggest why heavier crude-oil fractions are cracked.', [('They contain long hydrocarbon molecules with less demand.', ['long','demand']),('Cracking makes more useful lower-$M_r$ alkanes and alkenes.', ['lower','alkanes','alkenes'])],d=4,word='Suggest')
short(4,'Give a balanced equation for cracking decane into octane and ethene.', [('$\\ce{C10H22 -> C8H18 + C2H4}$.',['C10H22','C8H18','C2H4'])],word='Give')
mcq(4,'Identify a possible pair of products from cracking $\\ce{C6H14}$.',['$\\ce{C4H10}$ and $\\ce{C2H4}$','$\\ce{C4H10}$ and $\\ce{C2H6}$','$\\ce{C4H8}$ and $\\ce{C2H4}$','$\\ce{C5H12}$ and $\\ce{CH4}$'],'A','Carbon and hydrogen balance: $\\ce{C4H10 + C2H4}$ gives $\\ce{C6H14}$.',{'B':'m8','C':'m8','D':'m8'})
short(4,'A refinery has excess high-$M_r$ alkane fraction. Suggest two useful lower-$M_r$ products from cracking and explain their uses.', [('A shorter alkane is a useful fuel.', ['shorter alkane','fuel']),('An alkene is a feedstock for addition reactions such as polymerisation.', ['alkene','polymerisation'])],d=4,word='Suggest')
short(4,'Explain why cracking can increase the supply of useful low-$M_r$ hydrocarbons from crude oil.', [('Cracking breaks larger molecules in heavy fractions into smaller hydrocarbons.', ['larger','smaller']),('The lower-$M_r$ products include alkanes and alkenes.', ['lower','alkanes','alkenes'])],word='Explain')

# Unreactivity.
short(5,'Explain why alkanes generally do not react readily with polar reagents.', [('C–H bonds are strong and require substantial energy to break.', ['strong','energy']),('C–H bonds are relatively non-polar, giving no strongly charged site for polar reagents.', ['non-polar','polar'])],d=4,word='Explain')
mcq(5,'Identify the best bond-level explanation for alkane unreactivity towards polar reagents.',['Strong, nearly non-polar C–H bonds','Weak, highly polar C–H bonds','Weak C=C bonds','Ionic C–H bonds'],'A','Strong C–H bonds are hard to break and their relative lack of polarity gives polar reagents little site to attack.',{'B':'m5','D':'m5'})
short(5,'Describe the polarity of a C–H bond in an alkane.', [('It is relatively non-polar because the electronegativity difference is small.', ['non-polar','electronegativity'])])
short(5,'Explain why a strong C–H bond contributes to alkane unreactivity.', [('Breaking it requires substantial energy, so the activation barrier to reaction is high.', ['energy','activation'])],word='Explain')
mcq(5,'Identify why aqueous hydroxide usually does not substitute hydrogen in ethane.',['The C–H bond is ionic.','Ethane has no strongly polar reaction site.','Ethane has a C=C double bond.','Ethane is an oxidising agent.'],'B','The relatively non-polar C–H bonds do not present a suitable site for attack by polar hydroxide.',{'A':'m5'})
short(5,'Compare the response of ethane to aqueous polar reagents and to chlorine in ultraviolet light.', [('Ethane is generally unreactive to polar reagents due to strong, relatively non-polar C–H bonds.', ['polar','strong','non-polar']),('UV light can initiate free-radical substitution with chlorine.', ['UV','free-radical'])],d=4,word='Compare')

# Environmental consequences and converter.
short(6,'Describe two harmful consequences of carbon monoxide from an internal combustion engine.', [('Carbon monoxide is poisonous.', ['poisonous']),('It binds to haemoglobin, reducing oxygen transport in blood.', ['haemoglobin','oxygen'])])
short(6,'Describe an environmental consequence of nitrogen oxides from internal combustion engines.', [('Nitrogen oxides contribute to photochemical smog and/or acid rain.', ['smog'])])
short(6,'Describe an environmental consequence of unburnt hydrocarbons in engine exhaust.', [('Unburnt hydrocarbons contribute to photochemical smog.', ['smog'])])
short(6,'Describe how a catalytic converter removes carbon monoxide and nitrogen monoxide.', [('Carbon monoxide is oxidised to carbon dioxide.', ['carbon monoxide','carbon dioxide']),('Nitrogen monoxide is reduced to nitrogen.', ['nitrogen monoxide','nitrogen'])],d=4)
mcq(6,'Identify the balanced reaction in a catalytic converter that removes CO and NO.',['$\\ce{2CO + 2NO -> 2CO2 + N2}$','$\\ce{CO + NO -> CO2 + N2}$','$\\ce{2CO2 + N2 -> 2CO + 2NO}$','$\\ce{CO + NO -> C + NO2}$'],'A','The reaction balances C, O and N and converts CO to CO2 and NO to N2.',{'B':'m6'})
short(6,'Explain how a catalytic converter treats unburnt hydrocarbons.', [('They are oxidised to carbon dioxide and water.', ['oxidised','carbon dioxide','water'])],word='Explain')

# Computed numeric template: oxygen needed for complete combustion of an alkane.
n=4
oxygen=Fraction(3*n+1,2)
assert oxygen==Fraction(13,2)
template={'params':{'n':{'min':2,'max':8,'step':1}},'derived':{'h':'2*n+2'},'answer':'(3*n+1)/2','distractors':[{'expr':'n','misconception':'m2'},{'expr':'(n+1)/2','misconception':'m2'}],'constraints':['n>=2']}
for n in range(2,9):
 a=eval(template['answer'],{},dict(n=n)); ds=[eval(x['expr'],{},dict(n=n)) for x in template['distractors']]
 assert all(abs(d-a)>0.02*a for d in ds)
items.append(dict(id=f'{SUB}-i{len(items)+1:02}',kcs=[KC(2)],kind='numeric',difficulty=3,command_word='Calculate',source={'type':'generated'},stem='Calculate the moles of $\\ce{O2}$ needed for complete combustion of 1 mol of $\\ce{C[[n]]H[[h]]}$.',marks=2,answer={'value':float(oxygen),'unit':'mol','sf_ok':[2,3]},template=template,explanation='Complete combustion gives $\\ce{CO2}$ and $\\ce{H2O}$; balancing gives $(3n+1)/2$ mol of oxygen per mole of alkane.',hints=['Write the formula of the alkane from its carbon count.','Balance carbon and hydrogen before oxygen.','Count oxygen atoms on the product side.']))

# Twelve original past questions, including two whose scans repair extraction order.
bank=json.loads((ROOT/'build/work/mcq/9701.tagged.json').read_text())
byid={x['id']:x for x in bank}
chosen=[
 ('9701_s22_11_q30',4,'B','B omits buta-1,3-diene, but it can form when the oct-1-ene chain breaks between carbons 4 and 5.'),
 ('9701_w24_11_q31',3,'C','Light breaks $\\ce{Cl2}$ homolytically into radicals, not ions as C claims.'),
 ('9701_w21_12_q23',3,'D','A abstracts hydrogen from chloroethane and leaves another radical, so it is propagation. D combines radicals and terminates the chain.'),
 ('9701_w19_13_q21',2,'B','Alkanes undergo free-radical substitution with halogens in UV light. Electrophilic substitution is not their characteristic reaction.'),
 ('9701_s25_13_q36',3,'B','Both steps regenerate a radical and propagate the chain. B mislabels the second step termination even though a radical remains.'),
 ('9701_s25_12_q35',3,'A','Two $\\ce{CH2Cl^{\\bullet}}$ radicals combine to make $\\ce{CH2ClCH2Cl}$ in termination. HCl forms during propagation.'),
 ('9701_s25_11_q37',2,'A','Ethyl radicals can combine to make butane; abstraction makes HBr. Hydrogen is not a product, so A includes an incorrect statement.'),
 ('9701_s24_11_q28',2,'A','Ethane and chlorine undergo UV-initiated free-radical substitution, giving chloroethane and HCl. Hydrogen gas is not produced.'),
 ('9701_s24_11_q2',2,'B','Each methane volume gives one CO2 volume; each ethane volume gives two. Thus 10 + 20 = 30 cm³ is absorbed; B omits methane’s contribution.'),
 ('9701_s22_13_q4',2,'C','Water formation needs 3 oxygen atoms per ethane, so 1.5 mol O2. C is the complete-combustion requirement to CO2 and water.'),
 ('9701_s23_12_q24',6,'B','The converter removes NO, reducing photochemical-smog formation. B is false because oxidation of CO produces greenhouse gas CO2.'),
 ('9701_s23_12_q28',3,'A','Substitution can replace one through six hydrogens, with positional isomers: 1 + 2 + 2 + 2 + 1 + 1 = 9. A counts degrees of substitution but misses positional isomers.'),
]
for j,(qid,k,wrong,explanation) in enumerate(chosen,1):
 m=byid[qid]
 stem,opts=m['stem'],m.get('options')
 if qid=='9701_s23_12_q24':
  stem='The equation shows a reaction that occurs between carbon monoxide and nitrogen monoxide in a catalytic converter.\n2CO(g) + 2NO(g) → 2CO₂(g) + N₂(g)\nWhich statement is correct?'
  opts={'A':'The catalyst used is finely divided iron.','B':'The reaction prevents greenhouse gas emissions into the atmosphere.','C':'The reaction reduces the possibility of the formation of photochemical smog.','D':'The reaction results in increased ozone depletion.'}
 if qid=='9701_s23_12_q28':
  stem='Ethane reacts with an excess of chlorine in the presence of ultraviolet light to form a mixture of products.\nHow many of these products contain two carbon atoms and one or more chlorine atoms?'
  opts={'A':'6','B':'7','C':'8','D':'9'}
 assert opts and set(opts)==set('ABCD') and m['answer'] in opts
 it=dict(id=f'{SUB}-p{j:02}',kcs=[KC(k)],kind='mcq',difficulty=3,command_word=None,source={'type':'past','ref':m['ref'],'qid':qid},stem=stem,options=opts,answer=m['answer'],marks=1,explanation=explanation+' The correct option is '+m['answer']+'.',distractors={wrong:{2:'m2',3:'m3',4:'m4',6:'m6'}[k]})
 if m.get('image'): it['image']=m['image']
 items.append(it)

flash=[
 (1,'State the reagents and conditions for hydrogenation of an alkene.','$\\ce{H2(g)}$, Pt or Ni catalyst, and heat; alkane formed.'),
 (1,'State the conditions for cracking a long-chain alkane.','Heat with $\\ce{Al2O3}$; shorter alkanes and alkenes form.'),
 (2,'State the products of complete combustion of an alkane.','$\\ce{CO2}$ and $\\ce{H2O}$.'),
 (2,'State possible products of incomplete combustion of an alkane.','$\\ce{CO}$ and/or carbon, with $\\ce{H2O}$.'),
 (2,'State the conditions for halogen substitution of ethane.','$\\ce{Cl2}$ or $\\ce{Br2}$ in ultraviolet light; a hydrogen is replaced by halogen.'),
 (6,'State how a catalytic converter removes carbon monoxide and nitrogen oxides.','Oxidise $\\ce{CO}$ to $\\ce{CO2}$ and reduce nitrogen oxides to $\\ce{N2}$.')]
pack={'subtopic':SUB,'spec':'9701','version':1,'note':'Subjects/9701 Chemistry/14 Hydrocarbons/14.1 Alkanes.md','outline':'Alkanes are saturated hydrocarbons with strong, relatively non-polar C–H bonds. Prepare them by alkene hydrogenation or by cracking larger alkanes. They combust to give carbon dioxide and water in sufficient oxygen, but carbon monoxide or soot may form with limited oxygen. Ultraviolet light initiates free-radical substitution by halogens: initiation, propagation and termination. Cracking converts heavy fractions into useful lower-$M_r$ alkanes and alkenes. Engine exhaust contains carbon monoxide, nitrogen oxides and unburnt hydrocarbons; catalytic converters transform these pollutants.','misconceptions':misconceptions,'worked':[],'items':items,'flashcards':[dict(id=f'fc{i}',kc=KC(k),front=f,back=b) for i,(k,f,b) in enumerate(flash,1)],'diagrams':[]}
out=ROOT/'build/out/packs/9701/9701-14.1.json'
out.write_text(json.dumps(pack,ensure_ascii=False,indent=1))
print(out,len(items),'items')
