"""Build the 9701-3.6 chapter from reviewed bank entries and concept data."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SUB = '9701-3.6'
K = [f'{SUB}.{n}' for n in range(1, 5)]
bank = {x['id']: x for x in json.loads((ROOT/'build/work/mcq/9701.tagged.json').read_text())}

past = [
 ('9701_w19_11_q5', 'Ethanol has an O–H group and forms hydrogen bonds; ethanal and methoxymethane cannot donate such bonds. Option B wrongly assigns hydrogen bonding between ethanal molecules.'),
 ('9701_s20_12_q8', 'Oxygen molecules are non-polar, so melting oxygen overcomes only London dispersion forces. Option B involves hydrogen bonding in water.'),
 ('9701_w20_11_q4', 'Bromine molecules are non-polar and have only London dispersion forces between them. Ethanol and water hydrogen-bond; hydrogen chloride has permanent dipoles.'),
 ('9701_s21_13_q5', 'Dichloromethane is polar, methane has only London forces, and methanol hydrogen-bonds. Option A assigns the wrong force types to these substances.'),
 ('9701_w21_11_q5', 'A metal cation attracts the partially negative oxygen end of water: an ion–dipole interaction. Hydrogen bonding is not the attraction between the ion and water.'),
 ('9701_s22_11_q8', 'Ethanol forms hydrogen bonds, unlike ethanethiol, giving the first compound the higher boiling point. In B, the carboxylic acid hydrogen-bonds and boils higher than the ester.'),
 ('9701_s22_12_q6', 'The hydride of nitrogen, ammonia, forms significant hydrogen bonds; arsenic hydride does not. Group 15 atoms have outer configuration s²p³, so option A has the wrong configuration.'),
 ('9701_s24_11_q8', 'Water has strong intermolecular hydrogen bonds, unlike the other Group 16 hydrides. Option C refers to covalent bonds within molecules, which do not explain the boiling-point anomaly.'),
 ('9701_s24_12_q8', 'Branching lowers the boiling point of the alkane; the unbranched alkane follows, then the thiol, then the hydrogen-bonding alcohol. Option A reverses the thiol and alcohol.'),
 ('9701_w24_12_q6', 'ICl has a permanent dipole whereas Br₂ is non-polar, so ICl has additional intermolecular attraction. Option A compares intramolecular bond energies rather than forces overcome on boiling.'),
 ('9701_s25_12_q1', 'The giant covalent network in silicon dioxide has a high melting point, and ammonia hydrogen-bonds unlike phosphine. Option B misses the second true statement.'),
 ('9701_s25_13_q9', 'Melting giant covalent silicon(IV) oxide breaks covalent network bonds. Ice, iodine and ethanol melt by overcoming intermolecular attractions, so option B is wrong.'),
]

mis = [
 {'id':'m1','kc':K[0],'statement':'Boiling a molecular substance breaks its covalent bonds.','refutation':'Boiling separates molecules by overcoming intermolecular forces; the covalent bonds within each molecule remain.','contrast':'Compare melting ice with melting giant covalent silicon dioxide.','source':'ER 9701 w21 P12 Q7'},
 {'id':'m2','kc':K[1],'statement':'Any polar bond gives the entire molecule a permanent dipole.','refutation':'Bond dipoles are vectors and may cancel in a symmetrical molecule.','contrast':'Carbon dioxide has polar C–O bonds but no overall dipole.','source':'research'},
 {'id':'m3','kc':K[2],'statement':'A non-polar molecule has no intermolecular forces.','refutation':'Fluctuating electron clouds produce instantaneous dipoles, so all molecules exhibit London dispersion forces.','contrast':'Bromine is non-polar but liquid at room temperature.','source':'ER 9701 w20 P21 Q4'},
 {'id':'m4','kc':K[0],'statement':'Ice is denser than liquid water because it is more ordered.','refutation':'Hydrogen bonds hold ice in an open lattice with more empty space per molecule.','contrast':'Melting collapses some open structure, increasing density.','source':'research'},
]

pack = {'subtopic':SUB,'spec':'9701','version':1,
 'note':'Subjects/9701 Chemistry/03 Chemical bonding/3.6 Intermolecular forces, electronegativity and bond properties.md',
 'outline':'Electronegativity differences polarise bonds; molecular shape determines whether bond dipoles cancel. All molecules have London dispersion forces. Polar molecules also have permanent dipole–permanent dipole attraction; hydrogen bonding between molecules with N–H or O–H is a particularly strong case. Hydrogen bonds explain the high melting point, boiling point and surface tension of water, and the open, less dense structure of ice. Ionic, covalent and metallic bonds are generally stronger than intermolecular forces.',
 'misconceptions':mis,'worked':[],'items':[],'flashcards':[],'diagrams':[]}

for n,(qid,explanation) in enumerate(past,1):
 if qid=='9701_w21_11_q5':
  qid='9701_w19_12_q31'
  explanation='B: 1 and 2 only. Ammonia is trigonal pyramidal and hydrogen sulfide is bent; their bond dipoles do not cancel, so both molecules are polar. Boron trifluoride is trigonal planar with three identical B-F bonds whose dipoles cancel. A is incorrect because polar bonds do not necessarily make a molecule polar; D is incorrect because hydrogen sulfide is also polar.'
 x=bank[qid]
 item={'id':f'{SUB}-p{n:02}','kcs':['9701-3.6.2'] if n==5 else [k for k in x['kcs'] if k in K][:2],
 'kind':'mcq','difficulty':3,'command_word':None,'source':{'type':'past','ref':x['ref']},
 'stem':('Which gaseous molecules are polar?\n1 ammonia\n2 hydrogen sulfide\n3 boron trifluoride' if n==5 else x['stem']),'options':({'A':'1, 2 and 3 are correct','B':'1 and 2 only are correct','C':'2 and 3 only are correct','D':'1 only is correct'} if n==5 else x['options']),'answer':x['answer'],
 **({'image':x['image']} if x.get('image') else {}),'marks':1,'explanation':explanation,
 'distractors':({'A':'m1'} if qid=='9701_w24_12_q6' else {})}
 if n==5:
  item['source']['qid']=qid
 pack['items'].append(item)

questions = [
 (0,'Describe a hydrogen bond between water molecules.','Attraction between the $\\delta^+$ hydrogen bonded to oxygen in one molecule and a lone pair on oxygen in another.',['hydrogen','oxygen','lone pair']),
 (0,'Explain why water has a relatively high boiling point.','Many strong hydrogen bonds between water molecules require extra energy to overcome on boiling.',['hydrogen bonds','energy']),
 (0,'Explain the relatively high surface tension of water.','Hydrogen bonds create strong cohesion between surface water molecules; the surface resists being stretched.',['hydrogen bonds','surface']),
 (0,'Explain why ice is less dense than liquid water.','Hydrogen bonds hold molecules in an open lattice in ice. Some bonds break on melting, allowing molecules to pack closer together.',['open','closer']),
 (0,'Describe hydrogen bonding in ammonia.','A partially positive hydrogen in an N–H bond is attracted to a lone pair on nitrogen of another ammonia molecule.',['hydrogen','nitrogen','lone pair']),
 (0,'Explain why ammonia boils above phosphine.','Ammonia molecules form hydrogen bonds through N–H groups; phosphine does not form significant hydrogen bonds.',['ammonia','hydrogen bonds']),
 (1,'Explain how an electronegativity difference makes a bond polar.','The more electronegative atom attracts the shared electron pair more strongly and gains a partial negative charge; the other gains a partial positive charge.',['electronegative','partial']),
 (1,'Explain why carbon dioxide has no overall dipole moment.','Its two equal C–O bond dipoles point in opposite directions in a linear molecule and cancel.',['linear','cancel']),
 (1,'Explain why water has an overall dipole moment.','Its polar O–H bonds are arranged at an angle, so their bond dipoles do not cancel.',['polar','angle','cancel']),
 (1,'Describe the direction of the bond dipole in HCl.','It points towards chlorine, the more electronegative atom; chlorine is partially negative.',['chlorine','negative']),
 (1,'Compare the overall dipoles of BF₃ and NH₃.','The three B–F bond dipoles cancel in trigonal planar BF₃. The N–H dipoles do not cancel in pyramidal NH₃.',['cancel','pyramidal']),
 (1,'Explain why ICl has a permanent dipole whereas Br₂ does not.','I and Cl have different electronegativities, giving a polar bond; the identical Br atoms share electrons equally.',['electronegativities','identical']),
 (2,'Describe how instantaneous dipole-induced dipole forces arise.','A momentary uneven electron distribution creates an instantaneous dipole, which induces a dipole in a neighbouring molecule; opposite partial charges attract.',['electron','induces','attract']),
 (2,'State another name for instantaneous dipole-induced dipole forces.','London dispersion forces.',['London','dispersion']),
 (2,'Describe permanent dipole-permanent dipole forces.','The positive end of one polar molecule attracts the negative end of another polar molecule.',['positive','negative','polar']),
 (2,'Explain why bromine molecules attract one another despite being non-polar.','Their electron clouds fluctuate, producing temporary dipoles that induce dipoles in nearby molecules.',['temporary','induce']),
 (2,'Describe how hydrogen bonding fits within van der Waals forces.','It is a special, relatively strong permanent dipole–permanent dipole force; van der Waals forces is the generic term for intermolecular forces.',['permanent dipole','generic']),
 (2,'Explain why iodine is less volatile than chlorine.','Iodine molecules have more electrons and more polarisable electron clouds, making London dispersion forces between their molecules stronger.',['electrons','London','stronger']),
 (3,'State the general strength comparison between bonds and intermolecular forces.','Ionic, covalent and metallic bonding are generally stronger than intermolecular forces.',['ionic','covalent','metallic','stronger']),
 (3,'Explain why melting iodine does not break I–I covalent bonds.','Melting separates iodine molecules by overcoming intermolecular forces; I–I bonds remain within each molecule.',['intermolecular','remain']),
 (3,'Compare the bonds broken when silicon dioxide and ice melt.','Melting silicon dioxide breaks covalent network bonds; melting ice overcomes hydrogen bonds between intact water molecules.',['covalent','hydrogen']),
 (3,'Explain why ionic solids often melt at higher temperatures than molecular solids.','Strong electrostatic attractions between oppositely charged ions generally require more energy to overcome than intermolecular forces.',['ions','energy','intermolecular']),
 (3,'State which forces are overcome when ethanol boils.','Intermolecular forces, including hydrogen bonds, are overcome; covalent bonds within ethanol molecules are retained.',['intermolecular','hydrogen','retained']),
 (3,'Compare metallic bonding with London dispersion forces in general strength.','Metallic bonding is generally stronger than London dispersion forces between molecules.',['metallic','stronger','London']),
]
for n,(ki,stem,answer,keywords) in enumerate(questions,1):
 pack['items'].append({'id':f'{SUB}-i{n:02}','kcs':[K[ki]],'kind':'short','difficulty':4 if n%6==4 else 2,
 'command_word':stem.split()[0],'source':{'type':'generated'},'stem':stem,'marks':1,
 'rubric':[{'point':answer,'keywords':[[w] for w in keywords]}], 'explanation':answer,
 'hints':['Identify the particles involved.','Name the relevant attraction or geometry.','Link that feature directly to the observation.']})

flash = [
 (K[0],'Describe hydrogen bonding.','An intermolecular attraction between a hydrogen atom covalently bonded to N or O and a lone pair on N or O of another molecule.'),
 (K[1],'What is bond polarity?','An uneven distribution of bonding electrons caused by a difference in electronegativity, giving partial charges.'),
 (K[2],'What are van der Waals forces?','A generic term for intermolecular forces between molecular entities other than those due to bond formation.'),
 (K[2],'What are London dispersion forces?','Instantaneous dipole-induced dipole attractions between molecules.'),
 (K[3],'State the general relative strengths of bonding and intermolecular forces.','Ionic, covalent and metallic bonding are generally stronger than intermolecular forces.'),
]
pack['flashcards']=[{'id':f'fc{n}','kc':kc,'front':front,'back':back} for n,(kc,front,back) in enumerate(flash,1)]

out=ROOT/'build/out/packs/9701/9701-3.6.json'
out.parent.mkdir(parents=True,exist_ok=True)
out.write_text(json.dumps(pack,ensure_ascii=False,indent=1))
print(len(pack['items']))
