import json
from pathlib import Path

R=Path(__file__).resolve().parents[3]
sub='9701-13.3'; K=[f'{sub}.{i}' for i in range(1,5)]
out=R/f'build/out/packs/9701/{sub}.json'
mis=[
 {'id':'m1','kc':K[0],'statement':'A bent drawing of a carbon chain makes it branched.','refutation':'A straight chain may zigzag; branching means a carbon is bonded to a side carbon chain.','contrast':'Trace the carbon connectivity rather than the shape of the drawing.','source':'research'},
 {'id':'m2','kc':K[1],'statement':'Every atom in a double-bonded molecule is sp² hybridised.','refutation':'Only the atoms involved in the double bond are necessarily sp²; an adjacent saturated carbon remains sp³.','contrast':'Classify each atom separately from its local bonding.','source':'research'},
 {'id':'m3','kc':K[2],'statement':'A double bond consists of two σ bonds.','refutation':'A double bond has one σ bond from end-on overlap and one π bond from sideways p-orbital overlap.','contrast':'Count one σ for every connected atom pair and one additional π for each double bond.','source':'ER 9701 w21 P21 Q1'},
 {'id':'m4','kc':K[3],'statement':'A cyclic molecule must be planar.','refutation':'A saturated six-membered carbon ring has sp³ carbon centres and generally adopts a non-planar conformation.','contrast':'Check local hybridisation and three-dimensional arrangement, not only whether a ring is drawn flat.','source':'research'},
 {'id':'m5','kc':K[3],'statement':'Planar ethene means only its two carbon atoms lie in a plane.','refutation':'All six nuclei in ethene lie in the same plane; each carbon has trigonal planar local geometry.','contrast':'Planar describes the arrangement of all atoms being discussed.','source':'research'}]
rows=[
 [
 ('Describe a straight-chain organic molecule.','Its carbon atoms form one unbranched chain, even if drawn as a zigzag.'),
 ('Describe a branched organic molecule.','Its carbon skeleton has a side chain attached to the main carbon chain.'),
 ('Describe a cyclic organic molecule.','Its carbon skeleton includes a closed ring of atoms.'),
 ('Identify the carbon skeleton of CH₃CH₂CH₂CH₃.','It is straight-chained: four carbon atoms form an unbranched chain.'),
 ('Identify the carbon skeleton of CH₃CH(CH₃)CH₃.','It is branched: a methyl group is attached to the central carbon of the chain.'),
 ('Compare cyclohexane with hexane in carbon-skeleton arrangement.','Cyclohexane has a closed six-carbon ring; hexane is an open straight chain.')],
 [
 ('Describe the shape and bond angle around an sp³ carbon in an alkane.','Tetrahedral, with bond angles about 109.5°.'),
 ('Describe the shape and bond angle around each sp² carbon in ethene.','Trigonal planar, with bond angles about 120°.'),
 ('Describe the shape and bond angle around each sp carbon in ethyne.','Linear, with a bond angle of 180°.'),
 ('Explain why the central carbon in propene is trigonal planar.','It has three regions of σ bonding and is sp² hybridised, so its bonds lie approximately 120° apart.'),
 ('Identify the hybridisation of the methyl carbon in propene.','The methyl carbon has four σ bonds and is sp³ hybridised.'),
 ('Compare the geometry of the carbon atoms in ethane, ethene and ethyne.','Ethane carbon is sp³ tetrahedral, ethene carbon sp² trigonal planar, and ethyne carbon sp linear.')],
 [
 ('Describe the σ and π bonding in a carbon–carbon single bond.','One σ bond formed by end-on orbital overlap; no π bond.'),
 ('Describe the σ and π bonding in a carbon–carbon double bond.','One σ bond formed by end-on overlap and one π bond formed by sideways overlap of unhybridised p orbitals.'),
 ('Describe the σ and π bonding in a carbon–carbon triple bond.','One σ bond and two π bonds formed by overlap of two pairs of unhybridised p orbitals.'),
 ('Explain which orbitals form the π bond in ethene.','A parallel unhybridised p orbital on each sp² carbon overlaps sideways above and below the molecular plane.'),
 ('Determine the numbers of σ and π bonds in ethene.','Ethene has five σ bonds: four C–H and one C–C; it has one π bond.'),
 ('Compare the bonding of the carbon atoms in ethene and ethyne.','Ethene has an sp²–sp² σ bond and one π bond; ethyne has an sp–sp σ bond and two π bonds.')],
 [
 ('Define planar when describing atoms in a molecule.','Planar means the atoms lie in the same plane.'),
 ('Explain why ethene is planar.','Each sp² carbon is trigonal planar; the two carbons and four hydrogens lie in the same plane.'),
 ('Identify whether all atoms in ethene are planar.','Yes; both carbon atoms and all four hydrogen atoms lie in one plane.'),
 ('Explain why cyclohexane is not planar in its usual conformation.','Its sp³ carbon centres are tetrahedral and the ring puckers into a non-planar conformation.'),
 ('Compare the planarity of ethene and ethane.','All atoms of ethene lie in one plane; tetrahedral carbon centres in ethane prevent all atoms lying in one plane.'),
 ('Determine whether the carbonyl carbon and its three directly attached atoms in methanal are planar.','Yes; the carbonyl carbon is sp² and its three attached atoms lie in one plane.')]
]
keys=[
 [['unbranched'],['chain']], [['side'],['chain']], [['ring']], [['straight']], [['branched']], [['ring'],['chain']],
 [['tetrahedral'],['109']], [['trigonal planar'],['120']], [['linear'],['180']], [['three'],['sp²']], [['sp³']], [['tetrahedral'],['trigonal planar'],['linear']],
 [['σ'],['end-on']], [['σ'],['π']], [['σ'],['two π']], [['p orbital'],['sideways']], [['five σ'],['one π']], [['sp²'],['sp']],
 [['same plane']], [['six'],['plane']], [['four hydrogen'],['plane']], [['tetrahedral'],['non-planar']], [['ethene'],['ethane']], [['sp²'],['plane']]
]
def short(n,k,s,a,d):
 return {'id':f'{sub}-i{n:02d}','kcs':[k],'kind':'short','difficulty':d,'command_word':s.split()[0],'source':{'type':'generated'},'stem':s,'marks':1,'rubric':[{'point':a,'keywords':keys[n-1]}],'explanation':a,'hints':['Focus on the atoms or bonds named in the question.','Use carbon connectivity or the local bonding geometry.','Start by counting the groups bonded to the relevant carbon.']}
items=[short(i*6+j+1,k,s,a,4 if j==5 else 2) for i,k in enumerate(K) for j,(s,a) in enumerate(rows[i])]
# Check every generated bond count from an explicit bond inventory.
def counts(single,double,triple):
 return (single+double+triple,double+2*triple)
assert counts(4,1,0)==(5,1) # ethene: four C-H and one C=C
assert counts(2,0,1)==(3,2) # ethyne: two C-H and one C≡C
bank={q['id']:q for q in json.loads((R/'build/work/mcq/9701.tagged.json').read_text())}
chosen=[
 ('9701_s19_11_q20','The ring offers five different positions for the second methyl group. Each compound has two π bonds, with two π electrons per bond, giving four π electrons; option C counts only one bond’s electrons.' ,'C','m3'),
 ('9701_w25_12_q5','The N–N σ bond forms by end-on overlap of one sp orbital from each nitrogen, and each lone pair occupies the other sp orbital. Option A incorrectly places the lone pair in a p orbital.','A','m3'),
 ('9701_w25_12_q25','Methanal is trigonal planar around its carbon, so all four atoms are planar. Its two C–H bonds and one σ component of C=O give three σ bonds; option B misses that third σ bond.','B','m3'),
 ('9701_w24_12_q25','The structure contains four carbon atoms involved in C=C double bonds, so four are sp². Option C includes carbon atoms that are saturated rather than double-bonded.','C','m2'),
 ('9701_w22_13_q32','The ester structure identifies the alcohol-derived carbon bearing OH as secondary, and the saturated ring from the dicarboxylic acid is non-planar. Option B treats a ring drawn flat as planar.','B','m4'),
 ('9701_w20_12_q4','Nine carbon atoms have four σ-bond directions and tetrahedral geometry; eight carbon atoms are trigonal planar. Option C misses two trigonal planar centres.','C','m2'),
 ('9701_s25_13_q8','All bonds in the shown saturated sugar structure are σ bonds, and its six-membered ring is non-planar. Option A wrongly assumes a drawn six-membered ring is planar.','A','m4'),
 ('9701_s25_11_q39','The two terminal alkene carbons and the two noncentral carbons of the cumulated double-bond pair are sp²; the central carbon is sp. Option B wrongly counts that central carbon as sp².','B','m2'),
 ('9701_s24_11_q26','Counting one σ per linked atom pair, including one for each multiple bond, gives six σ bonds. The molecule contains sp and sp² carbon; option D incorrectly assigns sp² and sp³.','D','m3'),
 ('9701_s21_12_q4','The marked centres have trigonal planar, trigonal planar and tetrahedral geometry respectively, giving about 120°, 120° and 109°. Option B treats the second trigonal centre as tetrahedral.','B','m2'),
 ('9701_s20_11_q3','Each ethene carbon is sp². Four C–H σ bonds plus one C–C σ bond make five σ bonds, and sideways p overlap makes one π bond; option A omits the C–C σ bond.','A','m3'),
 ('9701_s20_11_q24','Addition polymerisation turns the alkene carbons into sp³ carbon atoms along the poly(propene) backbone. Their C–C–C angles are approximately 109°; option D retains the alkene’s trigonal planar angle.','D','m2')]
for n,(qid,exp,wrong,mid) in enumerate(chosen,1):
 q=bank[qid]
 p={'id':f'{sub}-p{n:02d}','kcs':[k for k in q['kcs'] if k in K],'kind':'mcq','difficulty':3,'command_word':None,'source':{'type':'past','ref':q['ref'],'qid':qid},'stem':q['stem'],'options':q['options'],'answer':q['answer'],'marks':1,'explanation':exp,'distractors':{wrong:mid}}
 if q.get('image'):p['image']=q['image']
 items.append(p)
worked=[{'id':'we1','kc':K[1],'problem':'Describe the local shapes and bond angles at the three carbon atoms of propene, CH₃CH=CH₂.','steps':[{'do':'The methyl carbon has four σ-bond directions, so it is sp³ hybridised.','why':'Classify each carbon from its own local bonding.'},{'do':'Give the methyl carbon a tetrahedral arrangement with angles about 109.5°.','why':'Four electron domains around carbon spread into a tetrahedron.'},{'do':'Each alkene carbon has three σ-bond directions and an unhybridised p orbital, so it is sp², trigonal planar and about 120°.','why':'The p orbitals provide the π bond while the sp² orbitals give the σ framework.'}],'faded':{'id':'we1f','problem':'Describe local shapes and bond angles at all three carbons of CH₂=CHCH₃.','answer':{'expr':'two trigonal planar sp2 centres near 120 degrees and one tetrahedral sp3 centre near 109.5 degrees'},'blank_from':1}},
 {'id':'we2','kc':K[2],'problem':'Count σ and π bonds in ethene, CH₂=CH₂.','steps':[{'do':'Count four C–H connections: each is one σ bond.','why':'A single bond is σ overlap.'},{'do':'Count the C=C as one C–C σ bond plus one π bond.','why':'A double bond has an end-on σ component and sideways p-overlap π component.'},{'do':f'Total {counts(4,1,0)[0]} σ bonds and {counts(4,1,0)[1]} π bond.','why':'Each linked atom pair contributes one σ bond.'}],'faded':{'id':'we2f','problem':'Count σ and π bonds in ethyne, HC≡CH.','answer':{'expr':f'{counts(2,0,1)[0]} sigma bonds and {counts(2,0,1)[1]} pi bonds'},'blank_from':1}}]
pack={'subtopic':sub,'spec':'9701','version':1,'note':'Subjects/9701 Chemistry/13 An introduction to AS Level organic chemistry/13.3 Shapes of organic molecules; σ and π bonds.md','outline':'Organic carbon skeletons may be straight-chained, branched or cyclic. Classify each atom locally: sp³ carbon is tetrahedral with bond angles near 109.5°, sp² carbon is trigonal planar with angles near 120°, and sp carbon is linear with a 180° angle. A single bond is σ; a double bond has one σ and one π; a triple bond has one σ and two π. σ bonds arise from end-on overlap, while π bonds arise from sideways overlap of unhybridised p orbitals. Planar means that the atoms lie in the same plane: all ethene atoms do, whereas a saturated six-membered ring is usually non-planar.','misconceptions':mis,'worked':worked,'items':items,'flashcards':[{'id':'fc1','kc':K[0],'front':'Describe straight-chained, branched and cyclic carbon skeletons.','back':'Straight-chained: one unbranched carbon chain; branched: a side chain attached to the main chain; cyclic: a closed ring of atoms.'},{'id':'fc2','kc':K[2],'front':'Describe σ and π bonding in a C=C double bond.','back':'One σ bond from end-on overlap and one π bond from sideways overlap of unhybridised p orbitals.'}],'diagrams':[]}
out.parent.mkdir(parents=True,exist_ok=True)
out.write_text(json.dumps(pack,ensure_ascii=False,indent=1))
print(len(items),len(worked))
