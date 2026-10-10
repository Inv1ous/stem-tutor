"""Generate 9701-4.2; all selected past questions come unchanged from the tagged bank."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
SUB='9701-4.2'; K=[f'{SUB}.{i}' for i in (1,2,3)]
bank={x['id']:x for x in json.loads((ROOT/'build/work/mcq/9701.tagged.json').read_text())}
selected=[
('9701_w25_13_q18','P₄O₁₀ consists of discrete molecules; MgO and Al₂O₃ are giant ionic, while SiO₂ is giant covalent. Option C wrongly treats network SiO₂ as molecular.'),
('9701_w24_13_q8','Sulfur forms discrete S₈ molecules in a molecular lattice. Calcium fluoride is ionic, nickel metallic and silicon(IV) oxide giant covalent.'),
('9701_s22_13_q7','Buckminsterfullerene and iodine are simple molecular; graphite and diamond are giant covalent. Option B misses one of the two molecular solids.'),
('9701_s20_12_q1','Diamond uses all four carbon valence electrons in localised covalent bonds. Graphite and graphene have delocalised electrons, as does buckminsterfullerene within each molecule.'),
('9701_s20_13_q3','Both solids have orderly lattices, but CO₂ is molecular and SiO₂ is giant covalent. Option B incorrectly assigns the same bonding structure to both.'),
('9701_s25_13_q9','Melting SiO₂ requires breaking covalent bonds throughout its network. Melting ice only overcomes attractions between intact water molecules, so B is wrong.'),
('9701_w22_13_q7','Strong network covalent bonds give a high melting point and the network is generally insoluble in polar solvents. Option B incorrectly assumes a polar solvent dissolves the covalent network.'),
('9701_s25_12_q1','SiO₂ has a giant covalent network, and ammonia forms hydrogen bonds unlike phosphine. Both statements are true; B overlooks the second.'),
('9701_s25_11_q7','Poor solid but good liquid conduction indicates mobile ions on melting; the high melting point and water insolubility fit aluminium oxide. Iron conducts as a solid, so B is wrong.'),
('9701_w24_13_q7','Grey tin is brittle and nonconducting, consistent with giant covalent bonding; white tin is malleable and conducts, consistent with metallic bonding. D incorrectly assigns ionic structure to elemental grey tin.'),
('9701_w22_13_q17','Molten NaCl conducts via mobile ions; SiCl₄ does not conduct as a liquid but reacts with water to give conducting products. B wrongly makes Al₂O₃ the nonconducting liquid.'),
('9701_s24_13_q8','W fits ionic NaF, X molecular C₂H₅Br, Y metallic Fe, and Z giant covalent SiO₂. B wrongly assigns MgO and HCl despite the listed properties.'),
]
mis=[
 {'id':'m1','kc':K[0],'statement':'Every covalently bonded solid is a giant covalent network.','refutation':'Discrete covalent molecules may form a simple molecular lattice held by intermolecular forces.','contrast':'C₆₀ and iodine are molecular; diamond and SiO₂ are networks.','source':'9701_s22_13_q7'},
 {'id':'m2','kc':K[1],'statement':'Melting a molecular solid breaks covalent bonds within molecules.','refutation':'Melting ordinarily overcomes intermolecular forces while molecules remain intact.','contrast':'Ice melts without breaking O–H bonds, whereas SiO₂ melting disrupts network bonds.','source':'9701_s25_13_q9'},
 {'id':'m3','kc':K[1],'statement':'A high melting point means a solid conducts electricity.','refutation':'Melting point measures energy needed to disrupt attractions; conduction requires mobile charged particles.','contrast':'Diamond has a high melting point but no mobile charge carriers.','source':'ER 9701 s22 P22 Q1'},
 {'id':'m4','kc':K[2],'statement':'An ionic solid conducts because it contains ions.','refutation':'Its ions are fixed in the solid lattice; mobile ions in a melt or solution conduct.','contrast':'Solid NaCl does not conduct but molten NaCl does.','source':'9701_w24_12_q8'},
]
pack={'subtopic':SUB,'spec':'9701','version':1,'note':'Subjects/9701 Chemistry/04 States of matter/4.2 Bonding and structure.md','outline':'Classify crystalline solids by their particles and the attractions connecting them: giant ionic, simple molecular, giant molecular (covalent), or giant metallic. Distinguish strong bonds within molecules from forces between molecules. Explain melting and boiling by what must be overcome, electrical conduction by mobile charged particles, and solubility by whether solvent–solute interactions can compensate for disrupting the lattice. Deduce an unknown structure by combining several properties rather than relying on one clue.','misconceptions':mis,'worked':[],'items':[],'flashcards':[],'diagrams':[]}
for n,(qid,explanation) in enumerate(selected,1):
 x=bank[qid]
 pack['items'].append({'id':f'{SUB}-p{n:02}','kcs':[k for k in x['kcs'] if k in K][:2],'kind':'mcq','difficulty':3,'command_word':None,'source':{'type':'past','ref':x['ref']},'stem':x['stem'],'options':x['options'],'answer':x['answer'],**({'image':x['image']} if x.get('image') else {}),'marks':1,'explanation':explanation,'distractors':{}})
questions=[
(0,'Describe the lattice structure of sodium chloride.','A giant three-dimensional lattice of alternating Na⁺ and Cl⁻ ions held by electrostatic attraction.'),
(0,'Describe the lattice structure of magnesium oxide.','A giant three-dimensional ionic lattice of Mg²⁺ and O²⁻ ions held by electrostatic attraction.'),
(0,'Describe the lattice structure of solid iodine.','Discrete I₂ molecules arranged regularly, held to neighbouring molecules by London dispersion forces.'),
(0,'Describe the structure of solid buckminsterfullerene.','Discrete C₆₀ molecules form a simple molecular lattice; covalent bonds hold carbon atoms within each cage and intermolecular forces hold cages together.'),
(0,'Describe the structure of ice.','Discrete H₂O molecules form an open molecular lattice held together by hydrogen bonds.'),
(0,'Describe the bonding in silicon(IV) oxide.','A giant covalent network in which each Si bonds to four O atoms and each O bridges two Si atoms.'),
(0,'Compare the structures of graphite and diamond.','Both are giant covalent structures. Each carbon bonds to three others in graphite layers with delocalised electrons, but to four others tetrahedrally in diamond.'),
(0,'Describe the structure and bonding of copper.','A giant metallic lattice of positive ions attracted to a sea of delocalised electrons.'),
(1,'Explain why sodium chloride conducts electricity when molten but not when solid.','Ions are fixed in the solid lattice; melting frees ions to move and carry charge.'),
(1,'Explain why copper conducts electricity as a solid.','Delocalised electrons are mobile through its giant metallic lattice and carry charge.'),
(1,'Explain why diamond does not conduct electricity.','Each carbon uses four outer electrons in covalent bonds, leaving no mobile charged particles.'),
(1,'Explain why graphite conducts along its layers.','Each carbon contributes one electron to a delocalised system; these electrons move along the layers.'),
(1,'Explain why iodine has a much lower melting point than diamond.','Melting iodine overcomes intermolecular dispersion forces; melting diamond requires breaking many strong network covalent bonds.'),
(1,'Explain why magnesium oxide has a high melting point.','Strong electrostatic attraction between oppositely charged Mg²⁺ and O²⁻ ions throughout the giant lattice requires much energy to overcome.'),
(1,'Explain why ice has a relatively high melting point among simple molecular substances.','Hydrogen bonds between H₂O molecules require more energy to overcome than weak dispersion forces in comparable non-hydrogen-bonding molecules.'),
(1,'Predict the electrical conductivity of molten silicon(IV) oxide.','It does not conduct appreciably: the giant covalent structure has no mobile ions or delocalised electrons.'),
(1,'Explain why sodium chloride can dissolve in water.','Hydration of separated ions by polar water can compensate for disrupting the ionic lattice.'),
(1,'Compare the solubility in water of iodine and sodium chloride.','NaCl can dissolve as hydrated ions; non-polar iodine is only sparingly soluble because water cannot stabilise it sufficiently.'),
(2,'Deduce the structure of a solid that is malleable and conducts electricity in both solid and liquid states.','A giant metallic lattice: mobile delocalised electrons conduct, and metallic bonding permits layers to slide.'),
(2,'Deduce the structure of a brittle high-melting solid that conducts only when molten.','A giant ionic lattice: fixed ions cannot conduct in the solid, but mobile ions carry charge in the melt.'),
(2,'Deduce the structure of a low-melting nonconducting solid made of discrete molecules.','A simple molecular lattice held by relatively weak intermolecular forces.'),
(2,'Deduce the structure of an insoluble, very high-melting solid that never conducts and contains only covalent bonds.','A giant covalent network without mobile charge carriers, as in diamond or SiO₂.'),
(2,'Deduce the structure of a high-melting solid that conducts electricity along layers but not perpendicular to them.','A layered giant covalent structure like graphite, with delocalised electrons mobile within layers.'),
(2,'Explain why conductivity measured in both solid and molten states is stronger evidence than melting point alone.','The change reveals whether charge carriers become mobile on melting; melting point alone does not identify the carrier or bonding type.'),
]
for n,(ki,stem,answer) in enumerate(questions,1):
 pack['items'].append({'id':f'{SUB}-i{n:02}','kcs':[K[ki]],'kind':'short','difficulty':4 if n in (7,13,18,23,24) else 2,'command_word':stem.split()[0],'source':{'type':'generated'},'stem':stem,'marks':1,'rubric':[{'point':answer,'keywords':[[answer.split()[0]]]}],'explanation':answer,'hints':['Identify the particles in the solid.','Ask which particles or electrons can move and which attractions must be overcome.','Link that structural feature to the stated property.']})
pack['worked']=[{'id':'we1','kc':K[2],'problem':'A substance has a high melting point, does not conduct as a solid, conducts when molten, and dissolves in water. Deduce its structure.','steps':[{'do':'The high melting point implies strong attractions across a giant lattice.','why':'A molecular lattice would usually melt much more readily.'},{'do':'The change from nonconductor to conductor on melting shows charged particles become mobile.','why':'This distinguishes ions from a solid metallic electron sea.'},{'do':'Deduce a giant ionic lattice; dissolving in water is supporting evidence.','why':'Mobile ions carry charge in the melt and hydrated ions can enter solution.'}],'faded':{'id':'we1f','problem':'A brittle, high-melting solid does not conduct when solid but conducts when molten. How many of these two states conduct electricity?','answer':{'value':1,'unit':'','exact':True},'blank_from':1}}]
flash=[('What is a giant ionic lattice?','A regular three-dimensional arrangement of oppositely charged ions held by strong electrostatic attractions.'),('What is a simple molecular lattice?','A regular arrangement of discrete molecules held together by intermolecular forces.'),('What is a giant molecular lattice?','A continuous network of atoms joined by covalent bonds throughout the structure.'),('What is a giant metallic lattice?','An arrangement of positive metal ions held by attraction to delocalised electrons.')]
pack['flashcards']=[{'id':f'fc{i}','kc':K[0],'front':f,'back':b} for i,(f,b) in enumerate(flash,1)]
out=ROOT/'build/out/packs/9701/9701-4.2.json';out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(pack,ensure_ascii=False,indent=1))
print(len(pack['items']))
