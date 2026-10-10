"""Generate the 9701-11.2 pack from checked conceptual rules and the official bank."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
SUB='9701-11.2'; K=[f'{SUB}.{i}' for i in (1,2,3)]
bank={x['id']:x for x in json.loads((ROOT/'build/work/mcq/9701.tagged.json').read_text())}
mis=[
 {'id':'m1','kc':K[0],'statement':'Iodine displaces bromide because it is a halogen.','refutation':'Oxidising power decreases down Group 17; iodine cannot oxidise bromide.','contrast':'Chlorine displaces bromide and iodide, but iodine displaces neither.','source':'ER 9701 w21 P13 Q16'},
 {'id':'m2','kc':K[0],'statement':'Only a displacement reaction can make the hexane layer purple.','refutation':'Iodine already present dissolves in hexane even when no displacement occurs.','contrast':'Count iodine added as well as iodine formed.','source':'ER 9701 w21 P13 Q16'},
 {'id':'m3','kc':K[1],'statement':'Hydrogen reacts equally vigorously with every halogen.','refutation':'Reactivity decreases down the group; fluorine combines explosively while iodine reacts slowly and reversibly on heating.','contrast':'Compare fluorine and iodine with hydrogen.','source':'research'},
 {'id':'m4','kc':K[2],'statement':'Hydrogen iodide is most thermally stable because iodine is largest.','refutation':'The H–I bond is weakest, so HI decomposes most readily on heating.','contrast':'HF has the strongest H–X bond and greatest thermal stability.','source':'ER 9701 w20 P21 Q4'},
]
pack={'subtopic':SUB,'spec':'9701','version':1,'note':'Subjects/9701 Chemistry/11 Group 17/11.2 The chemical properties of the halogen elements and the hydrogen halides.md','outline':'Halogens act as oxidising agents by gaining electrons; oxidising power falls from fluorine to iodine. A more reactive halogen displaces a less reactive halide from solution. Halogens combine with hydrogen to give hydrogen halides, $\\ce{H2 + X2 -> 2HX}$; reaction vigour generally falls down Group 17. The thermal stability of hydrogen halides decreases $\\ce{HF > HCl > HBr > HI}$ because H–X bonds become longer and weaker down the group.','misconceptions':mis,'worked':[],'items':[],'flashcards':[],'diagrams':[]}
ids=['9701_w21_13_q16','9701_s22_13_q22','9701_w25_13_q22','9701_w24_13_q22','9701_w21_12_q15','9701_w20_13_q14','9701_s25_13_q19','9701_s22_12_q22','9701_s20_12_q18','9701_s20_12_q36']
ex={
 '9701_w21_13_q16':'Iodine appears after chlorine or bromine oxidises iodide (experiments 3 and 6), and iodine added directly also colours hexane (7, 8 and 9): five tubes. C misses the pre-existing iodine in two tubes.',
 '9701_s22_13_q22':'Chlorine oxidises iodide to iodine: the colourless aqueous layer becomes brown, and iodine dissolves in the upper hexane layer to colour it. B overlooks iodine partitioning into hexane.',
 '9701_w25_13_q22':'Iodine is a weaker oxidising agent than bromine and cannot oxidise bromide, so no reaction occurs. B reverses the actual oxidising-power order.',
 '9701_w24_13_q22':'Down Group 17 hydrogen halides become easier to oxidise and less thermally stable as H–X bonds weaken. A wrongly claims thermal stability increases.',
 '9701_w21_12_q15':'Bromide reduces chlorine to chloride but cannot reduce iodine, a weaker oxidising agent. B is wrong because chlorine also oxidises iodide.',
 '9701_w21_11_q16':'Iodine is present in five hexane layers: produced in experiments 3 and 6 and initially added in 7, 8 and 9. C misses two iodine-containing mixtures.',
 '9701_w20_13_q14':'The 2p⁵ configuration identifies fluorine, the strongest halogen oxidising agent. C is chlorine, which is weaker than fluorine.',
 '9701_w20_11_q14':'Fluorine has the 2p⁵ configuration and is the strongest oxidising agent listed. C represents chlorine, less powerful than fluorine.',
 '9701_s25_13_q19':'HBr is more thermally stable than HI because H–Br is stronger than H–I. A reverses the reducing-power trend of halide ions.',
 '9701_s22_12_q22':'X is iodine, with weak I–I bonds and stronger London forces than bromine; Y is chlorine, a stronger oxidising agent than bromine Z. C makes bromine a stronger oxidant than chlorine.',
 '9701_s20_12_q18':'HI decomposes more readily because H–I is weaker; iodine gives a purple vapour while HBr may remain unchanged. C wrongly predicts brown bromine vapour from HBr first.',
 '9701_s20_12_q36':'H–X bonds weaken down the group, so thermal stability decreases and oxidation becomes easier. A incorrectly makes thermal stability increase.'}
for n,qid in enumerate(ids,1):
 x=bank[qid]; item={'id':f'{SUB}-p{n:02}','kcs':[k for k in x['kcs'] if k in K][:2],'kind':'mcq','difficulty':3,'command_word':None,'source':{'type':'past','ref':x['ref']},'stem':x['stem'],'options':x['options'],'answer':x['answer'],'marks':1,'explanation':ex[qid],'distractors':{},'hints':['Recall the Group 17 trend.','Compare the halogen and halide positions.','Check what species are present or formed before choosing.']}
 if x.get('image'): item['image']=x['image']
 pack['items'].append(item)
Q=[
 (0,'State the order of halogen oxidising power from strongest to weakest.','Fluorine, chlorine, bromine, iodine.',['fluorine','chlorine','bromine','iodine']),
 (0,'Explain why chlorine displaces bromide ions from solution.','Chlorine is the stronger oxidising agent and gains electrons from bromide ions, forming chloride ions and bromine.',['stronger','electrons','bromide','bromine']),
 (0,'Describe what happens when bromine is added to aqueous sodium chloride.','No displacement occurs: bromine cannot oxidise chloride ions.',['no','chloride']),
 (0,'Predict the products when chlorine is added to aqueous potassium iodide.','Potassium chloride and iodine form.',['chloride','iodine']),
 (0,'Explain why iodine does not displace bromide from solution.','Iodine is a weaker oxidising agent than bromine and cannot oxidise bromide ions.',['weaker','bromide']),
 (0,'Describe how a purple hexane layer can arise after shaking halogen and halide solutions.','Iodine dissolves in hexane; it may have been added initially or formed by displacement.',['iodine','hexane','displacement']),
 (1,'State the general equation for a halogen reacting with hydrogen.','$\\ce{H2 + X2 -> 2HX}$, where X is a halogen.',['H2','X2','HX']),
 (1,'Describe the reaction of fluorine with hydrogen.','Fluorine reacts explosively with hydrogen even in the dark to form hydrogen fluoride.',['explosively','hydrogen fluoride']),
 (1,'Describe the reaction of chlorine with hydrogen.','Hydrogen and chlorine react slowly in the dark but rapidly or explosively in light, forming hydrogen chloride.',['light','hydrogen chloride']),
 (1,'Describe the reaction of bromine with hydrogen.','Hydrogen reacts with bromine on heating to form hydrogen bromide; it is less vigorous than the chlorine reaction.',['heating','hydrogen bromide']),
 (1,'Describe the reaction of iodine with hydrogen.','Hydrogen and iodine react slowly and reversibly on heating to form hydrogen iodide.',['slowly','reversibly','hydrogen iodide']),
 (1,'Explain the relative reactivity of halogens with hydrogen down Group 17.','Reaction vigour generally decreases as the halogens become weaker oxidising agents and gain electrons less readily.',['decreases','oxidising agents','electrons']),
 (2,'State the order of thermal stability of hydrogen halides.','$\\ce{HF > HCl > HBr > HI}$.',['HF','HCl','HBr','HI']),
 (2,'Explain why HI is less thermally stable than HBr.','The H–I covalent bond is longer and weaker than H–Br, so less energy is needed to break it.',['longer','weaker','energy']),
 (2,'Describe what thermal stability means for a hydrogen halide.','Resistance to decomposition on heating; a more stable hydrogen halide is harder to decompose.',['decomposition','heating']),
 (2,'Explain why hydrogen fluoride is the most thermally stable hydrogen halide.','H–F is the strongest H–X covalent bond, so the most energy is needed to break it on heating.',['strongest','energy']),
 (2,'Predict which of HBr and HI decomposes more readily on heating and explain.','HI decomposes more readily because H–I is weaker than H–Br.',['HI','weaker']),
 (2,'Describe the bond strength trend from HF to HI and its effect.','H–X bond strength decreases down the group, so thermal stability decreases.',['decreases','thermal stability'])]
for n,(ki,stem,ans,words) in enumerate(Q,1):
 pack['items'].append({'id':f'{SUB}-i{n:02}','kcs':[K[ki]],'kind':'short','difficulty':4 if n%6==0 else 2,'command_word':stem.split()[0],'source':{'type':'generated'},'stem':stem,'marks':1,'rubric':[{'point':ans,'keywords':[[w] for w in words]}],'explanation':ans,'hints':['Recall the relevant Group 17 trend.','Identify which bond or electron transfer matters.','Link that feature to the observation.']})
pack['flashcards']=[{'id':f'fc{n}','kc':K[ki],'front':front,'back':back} for n,(ki,front,back) in enumerate([(0,'State the trend in halogen oxidising power.','Oxidising power decreases down Group 17: F₂ > Cl₂ > Br₂ > I₂.'),(1,'State the trend in reactions of halogens with hydrogen.','Reactions become less vigorous down Group 17; the product is a hydrogen halide, HX.'),(2,'State the order of hydrogen halide thermal stability.','HF > HCl > HBr > HI, following decreasing H–X bond strength.')],1)]
out=ROOT/'build/out/packs/9701/9701-11.2.json';out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(pack,ensure_ascii=False,indent=1));print(len(pack['items']))
