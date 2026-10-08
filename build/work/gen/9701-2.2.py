import json
from pathlib import Path
from decimal import Decimal
ROOT=Path(__file__).resolve().parents[3]
sub='9701-2.2'; kc=sub+'.1'; NA=Decimal('6.02e23')
mis=[
 {'id':'m1','kc':kc,'statement':'A mole is a mass of substance.','refutation':'The mole counts specified entities; their mass depends on molar mass.','contrast':'One mole of any specified entities contains the same number of them.','source':'ER 9701 s21 P21 Q1'},
 {'id':'m2','kc':kc,'statement':'One mole of molecules contains one mole of atoms.','refutation':'Multiply by atoms per molecule: one mole of methane contains five moles of atoms.','contrast':'Count molecules first, then count the atoms in each molecule.','source':'ER 9701 w21 P12 Q2'},
 {'id':'m3','kc':kc,'statement':'A formula unit of an ionic compound is one ion.','refutation':'A formula unit of KCl contains two ions.','contrast':'The named entity determines the count.','source':'ER 9701 w22 P13 Q1'}]
items=[]
def add(kind,stem,answer,explanation, difficulty=2,**extra):
 i=len([x for x in items if x['source']['type']=='generated'])+1
 d={'id':f'{sub}-i{i:02}','kcs':[kc],'kind':kind,'difficulty':difficulty,'command_word': 'Calculate' if kind=='numeric' else 'Define' if kind=='short' else 'Identify','source':{'type':'generated'},'stem':stem,'marks':1,'answer':answer,'explanation':explanation,'hints':['Identify the specified entities.','Use the relationship between amount and particle number.','Write $N=nN_A$ or $n=N/N_A$ before substituting.']}
 d.update(extra);items.append(d)
add('numeric','Calculate the number of atoms in 0.250 mol of neon.',{'value':float(Decimal('0.250')*NA),'unit':'','sf_ok':[2,3]},'Each mole contains $6.02\\times10^{23}$ atoms, so multiply the amount by $N_A$.',distractors=[{'value':float(Decimal('0.250')*NA*2),'misconception':'m2'}])
add('numeric','Calculate the amount, in mol, of $1.204\\times10^{24}$ water molecules.',{'value':float(Decimal('1.204e24')/NA),'unit':'mol','sf_ok':[2,3]},'Divide the number of molecules by the Avogadro constant.')
add('numeric','Calculate the number of hydrogen atoms in 0.300 mol of water molecules.',{'value':float(Decimal('0.300')*2*NA),'unit':'','sf_ok':[2,3]},'Each water molecule has two hydrogen atoms, so multiply the number of molecules by two.',difficulty=4,distractors=[{'value':float(Decimal('0.300')*NA),'misconception':'m2'}])
add('numeric','Calculate the number of ions in 0.150 mol of sodium chloride formula units.',{'value':float(Decimal('0.150')*2*NA),'unit':'','sf_ok':[2,3]},'Each formula unit gives one sodium ion and one chloride ion.',difficulty=4,distractors=[{'value':float(Decimal('0.150')*NA),'misconception':'m3'}])
add('short','Define the mole in terms of the Avogadro constant.',None,'One mole contains $6.02\\times10^{23}$ specified elementary entities.',difficulty=1,rubric=[{'point':'One mole is the amount of substance containing $6.02\\times10^{23}$ specified entities.','keywords':[['6.02'],['10','23'],['entities','particles','atoms','molecules','ions']]}])
add('numeric','Calculate the number of oxygen atoms in 0.400 mol of $\\ce{CO2}$ molecules.',{'value':float(Decimal('0.400')*2*NA),'unit':'','sf_ok':[2,3]},'There are two oxygen atoms per carbon dioxide molecule.',difficulty=4,distractors=[{'value':float(Decimal('0.400')*NA),'misconception':'m2'}])
ids=['9701_w22_13_q1','9701_w21_12_q2','9701_w19_13_q2','9701_w25_13_q3','9701_w24_13_q4','9701_s24_13_q2','9701_s24_12_q2','9701_s21_12_q1','9701_s21_11_q1']
bank={m['id']:m for m in json.loads((ROOT/'build/work/mcq/9701.tagged.json').read_text())}
# corrections to bank questions (garbled fractions, figure-only options) live in overrides.json, as for the extras
FIX={q:{k:v for k,v in f.items() if k in ('stem','options')} for q,f in json.loads((ROOT/'build/work/mcq/overrides.json').read_text()).items()}
exps={ids[0]:'Chlorine molecules and sulfur atoms are each 0.50 mol. Option B is 1.0 mol of sodium atoms.',ids[1]:'One mole of methane contains five moles of atoms. Option D counts carbon dioxide molecules rather than its three atoms per molecule.',ids[2]:'One mole of carbon has mass 12.0 g, which is 60 carats. Option B reverses the mass-to-carat conversion.',ids[3]:'0.75 mol of sulfur dioxide has 1.50 mol of oxygen atoms. The other options give different oxygen-atom amounts.',ids[4]:'Compare moles of the named particles; 6.0 g of water gives one third of a mole, the greatest amount. The argon sample gives one quarter of a mole.',ids[5]:'One gram of hydrogen gas has one mole of atoms; 20 g of neon is one mole of atoms. Carbon dioxide has three atoms per molecule, so option A gives 1.5 mol of atoms.',ids[6]:'62 g of $\\ce{P4}$ is 0.5 mol of molecules, so it contains half the Avogadro number of molecules. Counting phosphorus atoms instead gives four times as many entities.',ids[7]:'The Avogadro constant counts specified entities in one mole; neon is monatomic. Option B describes a mass that varies with the element.',ids[8]:'One mole of hydrogen molecules contains two moles of hydrogen atoms. Pentane and but-2-ene supply fewer; option D supplies one mole of atoms.'}
for j,qid in enumerate(ids,1):
 m={**bank[qid],**FIX.get(qid,{})}; d={'id':f'{sub}-p{j:02}','kcs':[kc],'kind':'mcq','difficulty':3,'command_word':'Identify','source':{'type':'past','ref':m['ref'],'qid':qid},'stem':m['stem'],'options':m.get('options'),'answer':m['answer'],'marks':1,'explanation':exps[qid]}
 if m.get('image'):d['image']=m['image']
 if qid==ids[0]:d['distractors']={'B':'m1','C':'m3'}
 if qid==ids[1]:d['distractors']={'D':'m2'}
 items.append(d)
pack={'subtopic':sub,'spec':'9701','version':1,'note':'Subjects/9701 Chemistry/02 Atoms, molecules and stoichiometry/2.2 The mole and the Avogadro constant.md','outline':'The mole is an amount of substance containing $6.02\\times10^{23}$ specified entities. Use $N=nN_A$ and $n=N/N_A$. Always name the entity being counted. To count atoms within molecules or ions within formula units, multiply by the number of the named entities per formula.','misconceptions':mis,'worked':[],'items':items,'flashcards':[{'id':'fc1','kc':kc,'front':'Define one mole in terms of the Avogadro constant.','back':'One mole is the amount of substance containing $6.02\\times10^{23}$ specified elementary entities.'},{'id':'fc2','kc':kc,'front':'State the value and unit of the Avogadro constant.','back':'$N_A=6.02\\times10^{23}\\ \\mathrm{mol^{-1}}$.'}],'diagrams':[]}
path=ROOT/'build/out/packs/9701/9701-2.2.json';path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(pack,ensure_ascii=False,indent=1))
