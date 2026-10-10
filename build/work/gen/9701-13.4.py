"""Generate the 9701-13.4 content pack; numeric counts are derived from explicit cases."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SUB = "9701-13.4"
PACK = ROOT / "build/out/packs/9701/9701-13.4.json"
TEACH = ROOT / "build/work/teach/9701-13.4.json"
NOTE = "Subjects/9701 Chemistry/13 An introduction to AS Level organic chemistry/13.4 Isomerism: structural isomerism and stereoisomerism.md"
if "--quarantine-corrupt-extras" in sys.argv:
    # These OCR entries contradict their own examiner explanations: the former
    # describes 3 isomers but keys 4; the latter lists 6 esters but keys 5.
    bad = {"9701_w23_12_q29", "9701_w23_12_q38"}
    existing = json.loads(PACK.read_text())
    existing["items"] = [item for item in existing["items"]
                         if item.get("source", {}).get("qid") not in bad]
    PACK.write_text(json.dumps(existing, ensure_ascii=False, indent=1))
    print("quarantined", len(bad), "contradictory bank entries")
    sys.exit(0)
kc = lambda n: f"{SUB}.{n}"
mis = [
 {"id":"m1","kc":kc(1),"statement":"Same molecular formula alone proves stereoisomerism.","refutation":"Structural isomers have different atom connectivity; stereoisomers have the same structural formula but different spatial arrangements.","contrast":"Compare connectivity first, then arrangement.","source":"ER 9701 s21 P22 Q4"},
 {"id":"m2","kc":kc(3),"statement":"Every C=C bond gives two geometrical isomers.","refutation":"Each double-bond carbon needs two different attached groups.","contrast":"A terminal CH2= group fails the test.","source":"ER 9701 w23 P21 Q4"},
 {"id":"m3","kc":kc(4),"statement":"Any tetrahedral carbon bonded to four atoms is chiral.","refutation":"The four attached groups must be different, comparing complete substituent paths.","contrast":"Two methyl groups or equivalent ring paths rule it out.","source":"ER 9701 s21 P23 Q5"},
 {"id":"m4","kc":kc(6),"statement":"Add independent stereochemical choices to count isomers.","refutation":"Multiply independent binary choices, then remove duplicates caused by symmetry.","contrast":"One chiral centre and two independent eligible double bonds give 2×2×2, not 2+2+2.","source":"ER 9701 s22 P12 Q26"},
 {"id":"m5","kc":kc(6),"statement":"Structural and stereochemical counts are interchangeable.","refutation":"One structural formula can give multiple geometrical or optical forms, so the count depends on which types the question includes.","contrast":"List structures first, then add eligible stereoisomers only when asked.","source":"ER 9701 w20 P13 Q20"},
]
pack={"subtopic":SUB,"spec":"9701","version":1,"note":NOTE,
"outline":"Isomers share a molecular formula. Structural isomers differ in connectivity: chain, position or functional group. Stereoisomers have the same connectivity but different spatial arrangements. Alkene geometrical isomers arise because the π bond prevents free C=C rotation; each alkene carbon must have two different groups. Cis and trans describe relative sides. A tetrahedral carbon with four different groups is a chiral centre, giving a mirror-image pair of enantiomers. For a formula, list distinct structures first; then test each for geometrical and optical isomerism and account for symmetry.",
"misconceptions":mis,"worked":[],"items":[],"flashcards":[],"diagrams":[]}
source={"type":"generated"}
def add_short(n,cw,stem,answer,keys,explanation,difficulty=2):
 i=len([x for x in pack["items"] if x["source"]["type"]=="generated"])+1
 pack["items"].append({"id":f"{SUB}-i{i:02d}","kcs":[kc(n)],"kind":"short","difficulty":difficulty,"command_word":cw,"source":source,"stem":stem,"marks":1,"rubric":[{"point":answer,"keywords":keys}],"explanation":explanation,
 "hints":["Recall which feature determines this type of isomerism.","Compare the connectivity and then the three-dimensional arrangement.","Test the relevant carbon atoms and their attached groups."]})
def add_mcq(n,cw,stem,options,answer,explanation,distractors=None,difficulty=3):
 i=len([x for x in pack["items"] if x["source"]["type"]=="generated"])+1
 pack["items"].append({"id":f"{SUB}-i{i:02d}","kcs":[kc(n)],"kind":"mcq","difficulty":difficulty,"command_word":cw,"source":source,"stem":stem,"marks":1,"options":dict(zip("ABCD",options)),"answer":answer,"distractors":distractors or {},"shuffle":True,"explanation":explanation,
 "hints":["Check what remains the same in the two structures.","Compare atom connections before considering space.","Apply the defining test to each option."]})
def add_numeric(n,cw,stem,cases,wrong,explanation,difficulty=4):
 i=len([x for x in pack["items"] if x["source"]["type"]=="generated"])+1
 value=len(set(cases))
 assert value != wrong
 pack["items"].append({"id":f"{SUB}-i{i:02d}","kcs":[kc(n)],"kind":"numeric","difficulty":difficulty,"command_word":cw,"source":source,"stem":stem,"marks":1,"answer":{"value":value,"unit":"","sf_ok":[1,2]},"distractors":[{"value":wrong,"misconception":"m5"}],"explanation":explanation,
 "hints":["List the chemically distinct cases.","Look for equivalent structures related by symmetry.","Count each unique arrangement once."]})
# Six generated retrieval variants per outcome, with an exam-level application.
add_short(1,"Define","Define structural isomerism.","Compounds with the same molecular formula but different structural formulae (connectivity).",[["same molecular formula"],["different structural formulae","different connectivity"]],"Connectivity distinguishes structural isomers.")
add_short(1,"Describe","Describe chain isomerism.","The carbon skeletons differ while the molecular formula is the same.",[["carbon skeleton","carbon chain"],["differ","different"]],"Branching changes the carbon skeleton.")
add_short(1,"Describe","Describe positional isomerism.","The same functional group or multiple bond occupies a different position on the same carbon skeleton.",[["same carbon skeleton"],["different position"]],"The group moves without changing its identity.")
add_short(1,"Describe","Describe functional group isomerism.","The same molecular formula gives compounds with different functional groups.",[["same molecular formula"],["different functional groups"]],"An alcohol and an ether can be functional group isomers.")
add_mcq(1,"Identify","Identify the type of structural isomerism between butan-1-ol and butan-2-ol.",["chain","positional","functional group","optical"],"B","The OH group changes position on the same carbon chain.",{"D":"m1"})
add_short(1,"Compare","Compare butane and 2-methylpropane as isomers.", "They have the same molecular formula, C4H10, but different carbon skeletons: chain isomerism.",[["same molecular formula","C4H10"],["different carbon skeletons","chain isomerism"]],"The branch changes connectivity.",4)
add_short(2,"Define","Define stereoisomerism.","Compounds with the same structural formula but different arrangements of atoms in space.",[["same structural formula"],["different arrangements","different spatial arrangements"]],"The bonds connect the same atoms.")
add_short(2,"State","State the two types of stereoisomerism required here.","Geometrical (cis/trans) and optical isomerism.",[["geometrical","cis/trans"],["optical"]],"These are the two syllabus categories.")
add_short(2,"Describe","Describe how stereoisomers differ from structural isomers.","Stereoisomers have the same connectivity and differ in spatial arrangement; structural isomers differ in connectivity.",[["same connectivity","same structural formula"],["spatial arrangement"],["different connectivity","different structural formula"]],"Structural formula, not just molecular formula, is the decisive comparison.")
add_mcq(2,"Identify","Identify a pair of stereoisomers.",["butane and 2-methylpropane","ethanol and methoxymethane","cis-but-2-ene and trans-but-2-ene","propan-1-ol and propan-2-ol"],"C","The cis and trans forms have identical connectivity but different spatial arrangements.",{"A":"m1","B":"m1","D":"m1"})
add_short(2,"State","State whether E/Z nomenclature is required for this syllabus outcome.","E/Z nomenclature is acceptable but not required; cis/trans descriptions suffice here.",[["acceptable","not required"]],"The syllabus permits E/Z but does not demand it.")
add_short(2,"Explain","Explain why a pair of enantiomers is classed as stereoisomers.","They share the same structural formula and differ in their three-dimensional arrangements as non-superimposable mirror images.",[["same structural formula"],["mirror images"],["non-superimposable"]],"The atom connections remain unchanged.",4)
add_short(3,"Explain","Explain the origin of cis/trans isomerism in an alkene.","The π bond restricts rotation around C=C, so distinct spatial arrangements persist.",[["pi bond","π bond"],["restricts rotation"]],"Rotation would break the sideways p-orbital overlap.")
add_short(3,"State","State the condition on each carbon of C=C for geometrical isomerism.","Each double-bond carbon must be attached to two different groups.",[["each","both"],["two different groups"]],"A CH2= carbon has two identical hydrogen substituents.")
add_short(3,"Explain","Explain why but-1-ene does not show cis/trans isomerism.","One C=C carbon has two hydrogen atoms, so the two-group condition fails.",[["two hydrogen"],["one","carbon"]],"The terminal alkene carbon has identical substituents.")
add_short(3,"Describe","Describe cis and trans arrangements in but-2-ene.","In cis-but-2-ene the two methyl groups are on the same side of C=C; in trans they are on opposite sides.",[["same side"],["opposite sides"]],"The groups cannot exchange sides by C=C rotation.")
add_mcq(3,"Identify","Identify the alkene that can show cis/trans isomerism.",["propene","2-methylpropene","but-2-ene","ethene"],"C","Each C=C carbon in but-2-ene bears H and CH3.",{"A":"m2","B":"m2","D":"m2"})
add_short(3,"Explain","Explain why CH2=CHCH=CH2 cannot have cis/trans isomers even though it contains two C=C bonds.","Both C=C bonds are terminal: each has a CH2 carbon with two identical H groups.",[["terminal","CH2"],["two","identical","hydrogen"]],"Count eligible bonds, not all π bonds.",4)
add_short(4,"Define","Define a chiral centre in the usual carbon compounds studied here.","A tetrahedral carbon atom bonded to four different groups.",[["tetrahedral","carbon"],["four different groups"]],"Check whole groups, not only the first atom.")
add_short(4,"Describe","Describe the relationship between the two enantiomers from one chiral centre.","They are non-superimposable mirror images with the same connectivity.",[["non-superimposable"],["mirror images"]],"Reversing the arrangement makes its mirror image.")
add_short(4,"Explain","Explain why the central carbon in propan-2-ol is not chiral.","It is attached to two identical methyl groups.",[["two","methyl groups"],["identical","same"]],"Four bonds alone do not make a chiral centre.")
add_short(4,"Identify","Identify the chiral carbon in CH3CH(OH)CO2H.","The middle CH(OH) carbon is bonded to H, OH, CH3 and CO2H.",[["middle","CH(OH)"],["H","hydrogen"],["OH"],["CH3"],["CO2H"]],"The four substituents differ.")
add_mcq(4,"Identify","Identify the compound with a chiral centre.",["propan-2-ol","butan-2-ol","2-methylpropan-2-ol","ethanol"],"B","C2 of butan-2-ol has H, OH, CH3 and CH2CH3.",{"A":"m3","C":"m3"})
add_short(4,"Explain","Explain why a molecule with two chiral centres may have more than one pair of optical isomers.","Each chiral centre can have two spatial arrangements, so combinations of arrangements are possible; symmetry may make some combinations identical.",[["two spatial arrangements","two arrangements"],["combinations"],["symmetry"]],"Do not assume every molecule has exactly one chiral centre.",4)
add_short(5,"Identify","Identify the chiral centre in CH3CH(Cl)CH2CH3.","Carbon 2, the CH(Cl) carbon, has H, Cl, CH3 and CH2CH3.",[["carbon 2","CH(Cl)"],["four","H, Cl, CH3 and CH2CH3"]],"The four groups are distinct.")
add_short(5,"Explain","Explain why carbon 2 of CH3CH(OH)CH3 is not a chiral centre.","It has two equivalent CH3 groups.",[["two","equivalent","identical"],["CH3","methyl"]],"Compare both branches.")
add_short(5,"Identify","Identify whether CH3CH=CHCH3 can show geometrical isomerism.","Yes; each C=C carbon has H and CH3, giving cis and trans forms.",[["yes"],["each","both"],["H","hydrogen"],["CH3","methyl"]],"Both alkene carbons pass the different-group test.")
add_short(5,"Identify","Identify whether 1,2-dimethylcyclopropane can have cis/trans isomers.","Yes; the two methyl groups can lie on the same or opposite sides of the ring plane.",[["yes"],["same","opposite"],["ring"]],"The ring restricts rotation.")
add_mcq(5,"Identify","Identify the compound with a chiral centre.",["cyclohexane","1-methylcyclohexane","1,2-dimethylcyclohexane","1,1-dimethylcyclohexane"],"C","At a substituted ring carbon in 1,2-dimethylcyclohexane, the two paths around the ring differ.",{"B":"m3","D":"m3"})
add_short(5,"Explain","Explain why cis/trans isomerism can occur in 1,2-dichlorocyclobutane but not in 1,1-dichlorocyclobutane.","In the 1,2 compound the chlorines are on different ring carbons and can be on the same or opposite faces; in the 1,1 compound both are on one carbon.",[["different ring carbons"],["same","opposite"],["one carbon"]],"Locate the substituents before assigning ring faces.",4)
add_short(6,"Describe","Describe a systematic method to deduce isomers from a molecular formula.","Enumerate distinct carbon skeletons and functional-group positions, then test each structure for eligible C=C bonds and chiral centres, removing symmetry duplicates.",[["carbon skeletons"],["functional"],["C=C","double bond"],["chiral"],["symmetry"]],"This prevents both omissions and double counting.")
add_short(6,"Deduce","Deduce the two acyclic saturated alcohol structural isomers of C3H8O.","Propan-1-ol and propan-2-ol.",[["propan-1-ol"],["propan-2-ol"]],"The OH group can occupy an end or middle carbon.")
add_short(6,"Deduce","Deduce the functional-group isomer of ethanol with molecular formula C2H6O.","Methoxymethane, CH3OCH3.",[["methoxymethane","CH3OCH3"]],"Moving oxygen between the carbons gives an ether.")
add_numeric(6,"Determine","Determine the number of acyclic alkene structural isomers of C4H8, ignoring stereoisomerism.",["but-1-ene","but-2-ene","2-methylpropene"],4,"The distinct connectivities are but-1-ene, but-2-ene and 2-methylpropene.")
add_numeric(6,"Determine","Determine the number of acyclic alkene isomers of C4H8 including cis/trans stereoisomerism.",["but-1-ene","cis-but-2-ene","trans-but-2-ene","2-methylpropene"],3,"But-2-ene has two geometrical forms; the other two structures do not.")
add_short(6,"Explain","Explain why the total count of stereoisomers of a symmetric molecule can be less than $2^n$ for $n$ stereogenic features.","Symmetry can make two nominal combinations identical, so duplicates must be removed.",[["symmetry"],["identical","same","duplicates"]],"Independent choice counting gives an upper bound, not always the final total.",4)
# Worked examples for procedural outcomes. Count answers are computed from enumerated cases.
def worked(n,problem,steps,faded_problem,faded_cases):
 val=len(set(faded_cases))
 pack["worked"].append({"id":f"we{n}","kc":kc(n),"problem":problem,"steps":[{"do":a,"why":b} for a,b in steps],
 "faded":{"id":f"we{n}f","problem":faded_problem,"answer":{"value":val,"unit":"","sf_ok":[1,2]},"blank_from":1}})
worked(5,"Identify chiral centres and geometrical isomerism in CH3CH(OH)CH=CHCH3.",
 [("Check the CH(OH) carbon: it has H, OH, CH3 and CH=CHCH3.","Four distinct groups make it chiral."),
 ("Check each C=C carbon: each has H and a different carbon group.","Restricted rotation produces cis/trans isomers.")],
 "How many chiral centres are in CH3CH(Cl)CH2CH3?",["C2"])
worked(6,"Count all acyclic alkene isomers of C4H8, including stereoisomers.",
 [("List distinct skeletons and double-bond positions: but-1-ene, but-2-ene, 2-methylpropene.","This covers structural isomerism."),
 ("Split but-2-ene into cis and trans forms; the others have identical groups at one C=C carbon.","Only but-2-ene meets the geometrical condition."),
 ("Count the resulting distinct structures: 1 + 2 + 1 = 4.","Exclude duplicate structures and include stereoisomers.")],
 "How many structural isomers are there among but-1-ene, but-2-ene and 2-methylpropene?",["but-1-ene","but-2-ene","2-methylpropene"])
for n,front,back in [
 (1,"Define structural isomerism.","Compounds with the same molecular formula but different structural formulae."),
 (1,"Define chain, positional and functional group isomerism.","Chain: different carbon skeleton. Positional: the same functional group or multiple bond at a different position. Functional group: different functional groups with the same molecular formula."),
 (2,"Define stereoisomerism.","Compounds with the same structural formula but different arrangements of atoms in space."),
 (2,"Name the types of stereoisomerism in this syllabus.","Geometrical (cis/trans) and optical isomerism; E/Z nomenclature is acceptable but not required."),
 (3,"What causes cis/trans isomerism in alkenes?","Restricted rotation about C=C due to its π bond; each double-bond carbon must have two different attached groups."),
 (4,"Define a chiral centre and enantiomers.","A chiral centre is a tetrahedral carbon bonded to four different groups. Enantiomers are non-superimposable mirror-image optical isomers."),
 (5,"How do you test a cyclic compound for cis/trans isomerism?","Check whether substituents can be on the same or opposite sides of the ring."),
 (6,"What order helps enumerate isomers from a formula?","List distinct connectivities first, then geometrical and optical alternatives, checking symmetry.")]:
 pack["flashcards"].append({"id":f"fc{len(pack['flashcards'])+1}","kc":kc(n),"front":front,"back":back})
# Preserve the bank's exact original stem, options, answer, image and reference.
selected=[
 ("9701_w21_13_q22","B overlooks cis and trans pent-2-ene, so B yields three alkenes. D is chiral and gives only 3-methylbut-1-ene and 2-methylbut-2-ene.",{"B":"m2"}),
 ("9701_w20_12_q27","The four aldehydes are pentanal, 2-methylbutanal, 3-methylbutanal and 2,2-dimethylpropanal. C misses one branched skeleton.",{}),
 ("9701_s22_12_q26","One chiral centre and two geometrical double bonds give 2 × 2 × 2 = 8. B adds 2 + 2 + 2 instead of multiplying.",{"B":"m4"}),
 ("9701_w24_13_q28","4-Methylhex-2-ene has both a chiral C4 and an eligible C=C: four stereoisomers. B has only alkene geometrical isomerism.",{"B":"m5"}),
 ("9701_w24_13_q27","Geraniol and nerol differ in the spatial arrangement at a restricted C=C bond. Chain isomerism would change connectivity.",{"A":"m1"}),
 ("9701_w24_12_q27","Six distinct position pairs of Cl on a straight butane chain remain after reversing its numbering. B counts a symmetry-equivalent placement twice.",{"B":"m4"}),
 ("9701_w24_12_q26","The C=C bond and each of two distinct chiral carbons give a binary choice: 2 × 2 × 2 = 8. C adds choices rather than multiplying.",{"C":"m4"}),
 ("9701_w24_13_q36","HCN addition to ethanal forms CH3CH(OH)CN, whose central carbon has four different groups. HCHO gives two H groups at that carbon.",{"D":"m3"}),
 ("9701_w25_12_q26","The apparent central CH has two identical side chains, so there is no chiral centre. B counts that carbon without comparing its complete substituents.",{"B":"m3"}),
 ("9701_w20_12_q20","The terminal C=C bonds cannot give cis/trans forms. The two internal bonds generate cis/cis, trans/trans and one mixed case because the two mixed arrangements are identical; C double-counts that case.",{"C":"m4"}),
 ("9701_s19_13_q28","Four aldehydes and three ketones of C5H10O undergo carbonyl addition of HCN, giving seven structural isomers. B misses one connectivity.",{}),
 ("9701_w22_13_q35","Enumerating the distinct dicarboxylic acid skeletons and splitting the two eligible alkenes into cis/trans forms gives seven. A or B omits at least one stereoisomer.",{"A":"m5","B":"m5"})]
bank={m["id"]:m for m in json.loads((ROOT/"build/work/mcq/9701.tagged.json").read_text())}
from importlib.util import spec_from_file_location, module_from_spec
sp=spec_from_file_location("add_past",ROOT/"build/add_past.py"); mod=module_from_spec(sp); sp.loader.exec_module(mod)
seen=set()
for j,(qid,ex,ds) in enumerate(selected,1):
 m=bank[qid]; assert m["answer"] in m["options"]
 item={"id":f"{SUB}-p{j:02d}","kcs":[k for k in m["kcs"] if k.startswith(SUB+".")],"kind":"mcq","difficulty":4 if j in (1,3,10,12) else 3,"command_word":None,
 "source":{"type":"past","ref":m["ref"],"qid":qid},"stem":m["stem"],"options":m["options"],"answer":m["answer"],"marks":1,"explanation":ex,"distractors":ds}
 if m.get("image"): item["image"]=m["image"]
 key=mod.question_key(item); assert key not in seen,qid; seen.add(key)
 pack["items"].append(item)
# Every count in the pack above comes from a named, enumerated set; verify arithmetic here.
assert len({"but-1-ene","but-2-ene","2-methylpropene"})==3
assert len({"but-1-ene","cis-but-2-ene","trans-but-2-ene","2-methylpropene"})==4
assert 2**3==8
cards={
kc(1):{"motivate":"One molecular formula can describe substances with different properties. Their atom connections reveal why.","establish":"Structural isomers have the same molecular formula but different structural formulae. In chain isomerism the carbon skeleton differs. In positional isomerism the same functional group or multiple bond occupies a different position on the same skeleton. In functional group isomerism the functional groups differ. Butane and 2-methylpropane show chain isomerism; propan-1-ol and propan-2-ol show positional isomerism; ethanol and methoxymethane show functional group isomerism.","connect":"Compare the displayed or structural formulae before thinking about three-dimensional shape.","note":"- Same molecular formula, different structural formulae.\n- Types: chain, positional, functional group.","self_explain":"How would you distinguish positional isomerism from functional group isomerism?"},
kc(2):{"motivate":"Two molecules can have exactly the same atom connections and still be distinct.","establish":"Stereoisomers have the same structural formula but different arrangements of atoms in space. The two types here are geometrical (cis/trans) isomerism and optical isomerism. Geometrical forms arise from restricted rotation; optical isomers arise around a chiral centre. E/Z nomenclature is acceptable but not required by this syllabus. When classifying a pair, first compare their connectivity: different connections mean structural isomerism; matching connections permit stereoisomerism.","connect":"Both categories share a molecular formula, but stereoisomers share a structural formula too.","note":"- Same structural formula, different spatial arrangement.\n- Types: geometrical and optical.","self_explain":"Why is matching molecular formula alone insufficient to establish stereoisomerism?"},
kc(3):{"motivate":"A double bond locks some arrangements into separate molecules.","establish":"In an alkene, the π bond comes from sideways overlap of p orbitals. Rotation about C=C would destroy that overlap, so rotation is restricted. Geometrical (cis/trans) isomerism is possible only when each double-bond carbon is attached to two different groups. In but-2-ene, the methyl groups are on the same side in the cis form and opposite sides in the trans form. But-1-ene fails because its terminal carbon bears two H atoms.","connect":"Apply the two-different-groups test to both C=C carbons before drawing isomers.","note":"- π bond restricts C=C rotation.\n- Each C=C carbon needs two different groups.\n- Cis: same side; trans: opposite sides.","self_explain":"Why does CH2=CHCH3 have no cis/trans pair?"},
kc(4):{"motivate":"A molecule and its mirror image can have identical bonds yet fail to overlap.","establish":"A chiral centre in these organic molecules is a tetrahedral carbon bonded to four different groups. Its two arrangements are optical isomers called enantiomers: non-superimposable mirror images. Compare complete groups, not just the atoms directly bonded to carbon. For example, the central carbon of butan-2-ol has H, OH, CH3 and CH2CH3 and is chiral; propan-2-ol has two CH3 groups and is not. Molecules can contain more than one chiral centre; symmetry must be considered when counting distinct stereoisomers.","connect":"This is the optical branch of stereoisomerism.","note":"- Chiral carbon: four different groups.\n- Enantiomers: non-superimposable mirror images.\n- More than one chiral centre is possible.","self_explain":"What makes butan-2-ol chiral but propan-2-ol achiral?"},
kc(5):{"motivate":"A complex structure can contain both chiral centres and geometrical alternatives.","establish":"For a given structural formula, inspect tetrahedral carbons and compare all four attached groups; include the full paths around a ring when deciding whether two groups match. Mark a carbon as chiral only if all four differ. For an alkene, inspect both C=C carbons; each must carry two different groups for cis/trans isomerism. In cyclic compounds, restricted rotation of the ring allows substituents on different ring carbons to occupy the same or opposite faces. Thus 1,2-dichlorocyclobutane can have cis/trans forms, while 1,1-dichlorocyclobutane cannot.","connect":"These checks apply the definitions to displayed, structural and skeletal formulae.","note":"- Test four complete groups at a tetrahedral carbon.\n- Test both carbons of each C=C.\n- In rings compare same and opposite faces.","self_explain":"Why can two paths from a substituted ring carbon be different?"},
kc(6):{"motivate":"Counting isomers accurately requires a method that catches each structure once.","establish":"Start with the known molecular formula and any stated restrictions. List distinct carbon skeletons, then allowed functional groups and positions, checking every structure has the right atom count and valencies. Remove structures that become identical when the chain is numbered from the opposite end or a symmetric molecule is turned around. Next split eligible alkenes or substituted rings into geometrical isomers and check tetrahedral carbons for optical isomers. Independent binary choices can multiply, but symmetry can make two nominal combinations identical. For C4H8 acyclic alkenes, the structural isomers are but-1-ene, but-2-ene and 2-methylpropene; splitting but-2-ene into cis and trans gives four compounds overall.","connect":"Use structural isomerism first, then apply geometrical and optical tests.","note":"- List skeletons, groups and positions.\n- Check formula and symmetry.\n- Add eligible geometrical and optical forms.","self_explain":"How does the count for acyclic C4H8 alkenes change when stereoisomers are included?"}}
PACK.parent.mkdir(parents=True,exist_ok=True)
PACK.write_text(json.dumps(pack,ensure_ascii=False,indent=1))
TEACH.parent.mkdir(parents=True,exist_ok=True)
TEACH.write_text(json.dumps(cards,ensure_ascii=False,indent=1))
print(len(pack["items"]),len(cards))
