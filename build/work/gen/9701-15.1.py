"""Generate and check the halogenoalkanes pack."""
import json
import re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
SUB='9701-15.1'
K=lambda n:f'{SUB}.{n}'
H=['Identify the carbon bonded to the halogen and the reagent.','Decide whether a bond is substituted, added, or eliminated.','Track which atom leaves and which new bond forms.']
misdata=[
(1,'Alkene addition of a halogen needs ultraviolet light.','Alkenes add halogens electrophilically at room temperature; UV light initiates alkane radical substitution.','Compare the starting hydrocarbon and conditions.','ER 9701 s22 P23 Q4'),
(2,'Primary means the halogen is on carbon 1 of the longest chain.','Classification counts carbon atoms attached to the carbon bearing halogen, regardless of its locant.','Count carbon neighbours of C–X.','research'),
(3,'Ethanolic cyanide forms an amine.','Cyanide substitutes X through its carbon end to form a nitrile; ethanolic ammonia gives an amine.','Identify the attacking nucleophile.','ER 9701 s19 P23 Q5'),
(4,'Aqueous and ethanolic hydroxide give the same main product.','Aqueous hydroxide favours substitution to an alcohol; hot ethanolic hydroxide favours elimination to an alkene.','Use solvent and temperature to choose the pathway.','research'),
(5,'An SN2 reaction first forms a carbocation.','SN2 is one concerted step: nucleophile attack and C–X bond breaking occur together.','A free carbocation is the SN1 intermediate.','ER 9701 s21 P11 Q20'),
(6,'Tertiary halogenoalkanes favour SN2 because their carbocations are stable.','Their crowded reaction centre hinders backside attack; alkyl groups stabilise a tertiary carbocation, favouring SN1.','Separate steric access from carbocation stability.','research'),
(7,'A stronger C–X bond hydrolyses faster.','A weaker C–X bond breaks more readily: C–I faster than C–Br faster than C–Cl in comparable compounds.','Compare bond strength, not halogen electronegativity alone.','ER 9701 w19 P11 Q24'),
]
mis=[dict(id=f'm{k}',kc=K(k),statement=s,refutation=r,contrast=c,source=src) for k,s,r,c,src in misdata]
items=[]
def short(k,stem,answer,word='Describe',difficulty=2):
    points=answer if isinstance(answer,list) else [answer]
    items.append(dict(id=f'{SUB}-i{len(items)+1:02}',kcs=[K(k)],kind='short',difficulty=difficulty,command_word=word,source={'type':'generated'},stem=stem,marks=len(points),rubric=[{'point':p,'keywords':[[w] for w in [t for t in re.findall(r'[A-Za-z][A-Za-z0-9-]*',p.lower()) if t not in {'the','a','an','to','of','and','with','by','in','is','are','on','from','or','ce','s','n','x','sn','heat','gives'}][:3]]} for p in points],explanation=' '.join(points),hints=H))
def mcq(k,stem,opts,answer,explanation,wrong=None,difficulty=2):
    items.append(dict(id=f'{SUB}-i{len(items)+1:02}',kcs=[K(k)],kind='mcq',difficulty=difficulty,command_word='Identify',source={'type':'generated'},stem=stem,options=dict(zip('ABCD',opts)),answer=answer,distractors=wrong or {},shuffle=True,marks=1,explanation=explanation,hints=H))
# Each generated set samples a distinct retrieval operation. Past questions below supply exam-style variants.
short(1,'Describe the preparation of chloroethane from ethane.','$\\ce{C2H6 + Cl2 -> C2H5Cl + HCl}$ by free-radical substitution in ultraviolet light.')
short(1,'Describe two room-temperature alkene reactions that produce halogenoalkanes.',['Electrophilic addition of $\\ce{X2}$ gives a dihalogenoalkane.','Electrophilic addition of $\\ce{HX(g)}$ gives a monohalogenoalkane.'])
short(1,'Give three distinct reagent sets for replacing the OH group of an alcohol by chlorine.',['React with $\\ce{HCl(g)}$ or $\\ce{KCl}$ and concentrated $\\ce{H2SO4}$ or $\\ce{H3PO4}$.','Use $\\ce{PCl3}$ with heat, $\\ce{PCl5}$, or $\\ce{SOCl2}$.'],word='Give',difficulty=4)
mcq(1,'Identify the conditions for the first chlorination of ethane.',['$\\ce{Cl2}$ with ultraviolet light','$\\ce{Cl2}$ at room temperature in the dark','$\\ce{NaOH(aq)}$ and heat','$\\ce{HCl(g)}$ at room temperature'],'A','UV light initiates free-radical substitution of ethane by chlorine.',{'B':'m1'})
short(1,'Describe how propene forms 1,2-dibromopropane.','Add $\\ce{Br2}$ across the C=C bond by electrophilic addition at room temperature.',difficulty=4)
short(2,'Define a primary halogenoalkane.','The carbon bonded to halogen is attached to one other carbon atom.',word='Define')
short(2,'Define a secondary halogenoalkane.','The carbon bonded to halogen is attached to two other carbon atoms.',word='Define')
short(2,'Define a tertiary halogenoalkane.','The carbon bonded to halogen is attached to three other carbon atoms.',word='Define')
mcq(2,'Identify the class of $\\ce{CH3CHBrCH3}$.',['primary','secondary','tertiary','not a halogenoalkane'],'B','The C–Br carbon has two carbon neighbours.',{'A':'m2'})
short(2,'Compare the classes of 1-bromopropane and 2-bromopropane.','1-Bromopropane is primary; 2-bromopropane is secondary because their C–Br carbons have one and two carbon neighbours respectively.',word='Compare',difficulty=4)
short(3,'Describe the reaction of bromoethane with aqueous sodium hydroxide.','$\\ce{CH3CH2Br + OH^- -> CH3CH2OH + Br^-}$; heat gives ethanol by nucleophilic substitution.')
short(3,'Describe the reaction of bromoethane with potassium cyanide.','Heat with $\\ce{KCN}$ in ethanol; carbon-end attack by $\\ce{CN^-}$ makes propanenitrile, adding one carbon.')
short(3,'Describe the reaction of bromoethane with ammonia.','Heat with $\\ce{NH3}$ in ethanol under pressure to form ethanamine by nucleophilic substitution.')
short(3,'Describe the aqueous silver nitrate test in ethanol for bromoethane.','Warm with aqueous $\\ce{AgNO3}$ in ethanol: hydrolysis releases $\\ce{Br^-}$, which gives cream $\\ce{AgBr}$ precipitate.')
mcq(3,'Identify the organic product when bromoethane is heated with $\\ce{KCN}$ in ethanol.',['ethanol','ethanamine','propanenitrile','ethene'],'C','The carbon end of cyanide bonds to the ethyl group, extending the carbon chain to propanenitrile.',{'B':'m3','D':'m4'})
short(4,'Describe the reaction of bromoethane with hot ethanolic sodium hydroxide.','$\\ce{CH3CH2Br + OH^- -> CH2=CH2 + H2O + Br^-}$; elimination forms ethene.')
short(4,'Explain why 1-bromo-2,2-dimethylpropane does not form an alkene with ethanolic hydroxide.','Its adjacent beta carbon has no hydrogen to remove; elimination cannot form a C=C bond.',word='Explain',difficulty=4)
mcq(4,'Identify the main organic product of hot ethanolic hydroxide with 2-bromopropane.',['propan-1-ol','propan-2-ol','propene','propane'],'C','Hot ethanolic hydroxide removes a beta hydrogen and bromide to form propene.',{'B':'m4'})
short(4,'Compare the main products when bromoethane is heated with aqueous and ethanolic sodium hydroxide.','Aqueous hydroxide gives ethanol by substitution; hot ethanolic hydroxide gives ethene by elimination.',word='Compare',difficulty=4)
short(5,'Describe the one-step $S_N2$ mechanism for bromoethane and cyanide.','The carbon lone pair of $\\ce{CN^-}$ attacks the C–Br carbon as the C–Br bond breaks heterolytically; no carbocation forms.')
short(5,'Describe the two steps of $S_N1$ hydrolysis of 2-bromo-2-methylpropane.',['C–Br breaks heterolytically to form a tertiary carbocation and bromide.','$\\ce{OH^-}$ attacks the carbocation to form 2-methylpropan-2-ol.'],difficulty=4)
short(5,'Explain how alkyl groups affect carbocation stability.','Their positive inductive effect donates electron density towards the positive carbon, stabilising tertiary more than secondary more than primary carbocations.',word='Explain')
mcq(5,'Identify the intermediate in the $S_N1$ hydrolysis of 2-bromo-2-methylpropane.',['a tertiary carbocation','a primary carbocation','a free radical','a cyclic transition state'],'A','Heterolytic C–Br cleavage first gives a tertiary carbocation.',{'D':'m5'})
short(5,'Compare the timing of bond making and bond breaking in $S_N1$ and $S_N2$.','In $S_N1$, C–X breaks before nucleophile attack; in $S_N2$, attack and C–X breaking are concerted.',word='Compare',difficulty=4)
short(6,'State the preferred substitution mechanism of primary, secondary and tertiary halogenoalkanes.','Primary tends to $S_N2$, tertiary to $S_N1$, and secondary to a mixture depending on structure.',word='State')
short(6,'Explain why primary halogenoalkanes tend to react by $S_N2$.','Their reaction carbon is less crowded, allowing backside attack; a primary carbocation is relatively unstable.',word='Explain')
short(6,'Explain why tertiary halogenoalkanes tend to react by $S_N1$.','Three alkyl groups hinder backside attack and stabilise the tertiary carbocation by positive inductive effects.',word='Explain')
mcq(6,'Identify the likely substitution mechanism for 1-bromobutane with aqueous hydroxide.',['$S_N1$','$S_N2$','free-radical substitution','electrophilic addition'],'B','The primary reaction centre favours concerted nucleophilic substitution.',{'A':'m6'})
short(6,'Predict the mechanism(s) possible for 2-bromobutane in nucleophilic substitution.','This secondary halogenoalkane may react by both $S_N1$ and $S_N2$; the mixture depends on its structure.',word='Predict',difficulty=4)
short(7,'Describe the reactivity order of comparable chloro-, bromo- and iodoalkanes in hydrolysis.','Iodoalkane reacts fastest, then bromoalkane, then chloroalkane; C–I is weakest and C–Cl strongest.')
short(7,'Explain why bromoethane hydrolyses faster than chloroethane.','The C–Br bond is longer and weaker than C–Cl, so it breaks more readily during nucleophilic substitution.',word='Explain')
short(7,'Describe the silver nitrate observations for chloro-, bromo- and iodoalkanes.','Warm with aqueous silver nitrate in ethanol: white AgCl, cream AgBr, yellow AgI; precipitate appears sooner for weaker C–X bonds.')
mcq(7,'Identify the fastest hydrolysing compound under identical conditions.',['chloroethane','bromoethane','iodoethane','fluoroethane'],'C','The weak C–I bond is cleaved most readily.',{'A':'m7'})
short(7,'Explain why precipitate timing in aqueous silver nitrate can compare C–X bond reactivity.','Hydrolysis releases halide ions, which react with silver ions; faster hydrolysis gives earlier silver halide precipitate.',word='Explain',difficulty=4)
# Formula mass uses paper A_r(C)=12.0, A_r(H)=1.0; enumerate and verify all template values.
tpl={'params':{'n':{'min':4,'max':7,'step':1}},'derived':{'h':'2*n-2'},'answer':'12*n+h','distractors':[{'expr':'12*n+2*n','misconception':'m4'},{'expr':'12*n+2*n+2','misconception':'m4'}],'constraints':['n>=4']}
for n in range(4,8):
 h=2*n-2; a=12*n+h; ds=[12*n+2*n,12*n+2*n+2]
 assert a>0 and all(d!=a for d in ds)
items.append(dict(id=f'{SUB}-i{len(items)+1:02}',kcs=[K(4)],kind='numeric',difficulty=4,command_word='Calculate',source={'type':'generated'},stem='A 1,[[n]]-dibromoalkane undergoes two eliminations with excess hot ethanolic $\\ce{NaOH}$ to form the open-chain diene $\\ce{C[[n]]H[[h]]}$. Calculate its relative formula mass. Use $A_r(\\ce{C})=12.0$ and $A_r(\\ce{H})=1.0$.',marks=2,answer={'value':54,'unit':'','sf_ok':[2,3]},template=tpl,explanation='Two eliminations give $\\ce{C_nH_{2n-2}}$; $M_r=12n+(2n-2)=14n-2$. For $n=4$, this is 54.',hints=['Find the molecular formula after both eliminations.','Count carbon and hydrogen atoms separately.','Multiply atom counts by their relative atomic masses.']))
# Original bank text, options, key, and images are copied unaltered.
bank={x['id']:x for x in json.loads((ROOT/'build/work/mcq/9701.tagged.json').read_text())}
chosen=[
('9701_w24_12_q31',1,'B','All three routes can form 2-chloro-2-methylpropane: HCl addition, alcohol substitution, and UV chlorination. B omits radical substitution of the alkane.'),
('9701_w23_12_q28',2,'A','The C–Br carbon has three carbon neighbours, so it is tertiary; numbering gives 3-bromo-4-methylhexane. A gives the methyl substituent the wrong locant.'),
('9701_w24_12_q29',3,'C','Aqueous NaOH substitutes bromine with OH to give the alcohol. Ethanolic NaOH in C favours elimination.'),
('9701_w22_13_q30',3,'B','Aqueous hydroxide first makes propan-1-ol; oxidation can make propanoic acid. B would require a secondary alcohol.'),
('9701_w22_13_q37',4,'B','Hot ethanolic hydroxide eliminates HBr to give propene. B is the substitution product favoured by aqueous hydroxide.'),
('9701_w21_12_q25',4,'B','The carbon adjacent to C–Br in 1-bromo-2,2-dimethylpropane has no hydrogen for elimination. B has beta hydrogens and can form an alkene.'),
('9701_s21_11_q20',5,'B','In SN2, the carbon end of CN⁻ attacks as C–Br breaks, giving a nitrile. B wrongly inserts a carbocation intermediate.'),
('9701_w22_12_q32',5,'B','2-Chloro-2-methylpropane gives a tertiary carbocation, stabilised by three alkyl groups. B gives only a secondary carbocation.'),
('9701_w25_12_q31',6,'D','Tertiary 2-chloro-2-methylpropane undergoing cyanide substitution favours SN1. D uses ethanolic hydroxide, favouring elimination instead.'),
('9701_w24_13_q33',6,'B','1-Iodobutane hydrolyses fastest because C–I is weaker than C–Cl, and its primary centre favours SN2. B chooses the slower chloroalkane.'),
('9701_w19_11_q24',7,'D','Bromoethane hydrolyses faster by nucleophilic substitution because C–Br is weaker than C–Cl. D identifies the mechanism but reverses the rate order.'),
('9701_w25_13_q30',7,'A','The C–I bond hydrolyses first and iodide gives yellow AgI; the chlorine substituents remain in the first product. A gives cream, the colour of AgBr.'),
]
for j,(qid,k,wrong,ex) in enumerate(chosen,1):
 x=bank[qid]
 assert x.get('options') and set(x['options'])==set('ABCD') and x['answer'] in x['options']
 it=dict(id=f'{SUB}-p{j:02}',kcs=[K(k)],kind='mcq',difficulty=3,command_word=None,source={'type':'past','ref':x['ref'],'qid':qid},stem=x['stem'],options=x['options'],answer=x['answer'],marks=1,explanation=ex,distractors={wrong:f'm{k}'})
 if x.get('image'): it['image']=x['image']
 items.append(it)
fcdata=[
(1,'State the conditions for radical substitution of ethane with chlorine or bromine.','$\\ce{Cl2}$ or $\\ce{Br2}$ and ultraviolet light.'),
(1,'State two room-temperature routes from an alkene to a halogenoalkane.','Electrophilic addition of $\\ce{X2}$ or $\\ce{HX(g)}$ at room temperature.'),
(1,'State five ways to substitute an alcohol OH group with chlorine.','$\\ce{HCl(g)}$; $\\ce{KCl}$ with concentrated $\\ce{H2SO4}$ or $\\ce{H3PO4}$; $\\ce{PCl3}$ and heat; $\\ce{PCl5}$; $\\ce{SOCl2}$.'),
(2,'Define primary, secondary and tertiary halogenoalkanes.','The C–X carbon is bonded to one, two or three other carbon atoms respectively.'),
(3,'State the reagent, solvent and condition to make an alcohol from a halogenoalkane.','$\\ce{NaOH(aq)}$ and heat; nucleophilic substitution.'),
(3,'State the reagent, solvent and condition to make a nitrile.','$\\ce{KCN}$ in ethanol and heat; nucleophilic substitution.'),
(3,'State the reagent, solvent and condition to make an amine.','$\\ce{NH3}$ in ethanol, heated under pressure.'),
(3,'State the silver nitrate test results for halogenoalkanes.','Aqueous $\\ce{AgNO3}$ in ethanol: $\\ce{AgCl}$ white, $\\ce{AgBr}$ cream, $\\ce{AgI}$ yellow precipitate.'),
(4,'State the conditions and product of elimination of bromoethane.','$\\ce{NaOH}$ in ethanol and heat gives ethene.'),
(6,'State the substitution mechanism preferences by class.','Primary tends to $S_N2$, tertiary to $S_N1$, secondary to a mixture depending on structure.'),
]
pack=dict(subtopic=SUB,spec='9701',version=1,note='Subjects/9701 Chemistry/15 Halogen compounds/15.1 Halogenoalkanes.md',outline='Halogenoalkanes arise from ultraviolet radical substitution of alkanes, room-temperature electrophilic addition to alkenes, or alcohol substitution. Classify them by the number of carbon neighbours of the C–X carbon. Aqueous hydroxide, ethanolic cyanide and ethanolic ammonia give alcohols, nitriles and amines by nucleophilic substitution. Hot ethanolic hydroxide gives alkenes by elimination. $S_N2$ is concerted; $S_N1$ first forms a carbocation, stabilised by alkyl groups. Primary centres favour $S_N2$, tertiary centres $S_N1$, and secondary centres may use both. Weaker C–X bonds hydrolyse faster; aqueous silver nitrate in ethanol gives characteristic silver halide precipitates.',misconceptions=mis,worked=[],items=items,flashcards=[dict(id=f'fc{j}',kc=K(k),front=f,back=b) for j,(k,f,b) in enumerate(fcdata,1)],diagrams=[])
out=ROOT/'build/out/packs/9701/9701-15.1.json'
out.parent.mkdir(parents=True,exist_ok=True)
out.write_text(json.dumps(pack,ensure_ascii=False,indent=1))
print(out,len(items),'items')
