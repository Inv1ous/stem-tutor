import json
from pathlib import Path
from decimal import Decimal
root=Path(__file__).resolve().parents[3]
sub='9701-11.4'; a=sub+'.1'; b=sub+'.2'
out=root/'build/out/packs/9701/9701-11.4.json'
mis=[
 {'id':'m1','kc':a,'statement':'Cold alkali produces chlorate(V).','refutation':'Cold aqueous NaOH produces chlorate(I), with chlorine at +1; hot aqueous NaOH produces chlorate(V), with chlorine at +5.','contrast':'Match temperature to the oxidation number of the oxidised product.','source':'ER 9701 s23 P21 Q3'},
 {'id':'m2','kc':a,'statement':'Disproportionation only oxidises chlorine.','refutation':'In each reaction chlorine starts at 0 and ends at both -1 and a positive oxidation number.','contrast':'Name both oxidation and reduction of chlorine.','source':'ER 9701 w23 P21 Q3'},
 {'id':'m3','kc':b,'statement':'Chloride ions kill bacteria in chlorinated water.','refutation':'Chlorine reacts with water to form HOCl; HOCl and ClO- are active species that kill bacteria.','contrast':'Distinguish active HOCl and ClO- from Cl-.','source':'research'},
 {'id':'m4','kc':b,'statement':'Chlorine in HOCl or ClO- has oxidation number -1.','refutation':'Oxygen is -2 and hydrogen is +1, so chlorine is +1 in HOCl and ClO-.','contrast':'Calculate oxidation numbers from charge balance.','source':'research'}]
def short(i,k,stem,points,diff=2):
 return {'id':sub+f'-i{i:02d}','kcs':[k],'kind':'short','difficulty':diff,'command_word':stem.split()[0], 'source':{'type':'generated'},'stem':stem,'marks':len(points),'rubric':[{'point':p,'keywords':[[w] for w in ws]} for p,ws in points], 'explanation':'Credit the named species and oxidation-number changes shown in the mark scheme.','hints':['Recall the relevant chlorine species.','Write the equation or oxidation numbers before explaining.','Start with chlorine in the reactant.']}
items=[
 short(1,a,'Describe the reaction of chlorine with cold aqueous sodium hydroxide.', [('Produces sodium chloride and sodium chlorate(I).',['NaCl','NaClO']),('The reaction also produces water.',['water'])],3),
 short(2,a,'Describe the reaction of chlorine with hot aqueous sodium hydroxide.', [('Produces sodium chloride and sodium chlorate(V).',['NaCl','NaClO3']),('The reaction also produces water.',['water'])],3),
 short(3,a,'Explain why chlorine reacting with cold aqueous sodium hydroxide is a disproportionation reaction.', [('Chlorine is both oxidised and reduced.',['oxidised','reduced']),('Its oxidation number changes from zero to -1 and +1.',['0','-1','+1'])],4),
 short(4,a,'Explain why chlorine reacting with hot aqueous sodium hydroxide is a disproportionation reaction.', [('Chlorine is both oxidised and reduced.',['oxidised','reduced']),('Its oxidation number changes from zero to -1 and +5.',['0','-1','+5'])],4),
 short(5,a,'State the oxidation numbers of chlorine in the chlorine-containing products of its reaction with cold aqueous sodium hydroxide.', [('Chloride has chlorine at -1.',['-1']),('Chlorate(I) has chlorine at +1.',['+1'])]),
 short(6,a,'State the oxidation numbers of chlorine in the chlorine-containing products of its reaction with hot aqueous sodium hydroxide.', [('Chloride has chlorine at -1.',['-1']),('Chlorate(V) has chlorine at +5.',['+5'])]),
 short(7,b,'Explain how adding chlorine to water kills bacteria, including equations.', [('Chlorine reacts with water to form HOCl and HCl.',['Cl2','H2O','HOCl','HCl']),('HOCl dissociates to H+ and ClO-.',['HOCl','ClO-']),('HOCl and ClO- kill bacteria.',['HOCl','ClO-','bacteria'])],4),
 short(8,b,'State the two active chlorine species in water purification.', [('Hypochlorous acid, HOCl.',['HOCl']),('Hypochlorite ion, ClO-.',['ClO-'])]),
 short(9,b,'Explain the formation of chlorate(I) ions when chlorine is added to water.', [('Chlorine reacts with water to form HOCl and HCl.',['Cl2','H2O','HOCl','HCl']),('HOCl dissociates to H+ and ClO-.',['HOCl','ClO-'])],3),
 short(10,b,'Determine the oxidation number of chlorine in HOCl.', [('Oxygen is -2 and hydrogen is +1; chlorine is +1.',['+1'])]),
 short(11,b,'Determine the oxidation number of chlorine in ClO-.', [('Oxygen is -2 and the ion charge is -1; chlorine is +1.',['+1'])]),
 short(12,b,'Explain why chloride ions are not the disinfecting species formed when chlorine is added to water.', [('HOCl and ClO- are the active species that kill bacteria.',['HOCl','ClO-','bacteria']),('Chloride is a separate product, not the active species.',['chloride'])],4),
]
# Select distinct authentic questions directly from the tagged bank, retaining the bank's original text, options, key and image.
ids=['9701_s19_11_q17','9701_w25_12_q21','9701_w22_13_q22','9701_w22_12_q21','9701_w21_13_q17','9701_w19_12_q15','9701_s25_11_q19','9701_s24_12_q19','9701_s22_12_q23','9701_s22_11_q12','9701_s21_12_q17','9701_s19_12_q17']
bank={x['id']:x for x in json.loads((root/'build/work/mcq/9701.tagged.json').read_text())}
for n,qid in enumerate(ids,1):
 q=bank[qid]; stem=q['stem']; opts=q.get('options')
 kcs=[k for k in q['kcs'] if k in (a,b)]
 if qid=='9701_s19_11_q17':
  amount=Decimal('30.2')/Decimal('151'); mass=amount*6*40
  assert mass==Decimal('48.0')
  expl='NaBrO3 is 0.200 mol. The hot-alkali ratio NaOH : NaBrO3 is 6 : 1, so 1.20 mol NaOH has mass 48.0 g; option B misses that ratio.'
 elif qid=='9701_w25_12_q21':
  mass=Decimal('0.600')/3*Decimal('106.5'); assert mass==Decimal('21.3000')
  expl='Three moles of Cl2 give one mole of NaClO3, so 0.200 mol forms, with mass 21.3 g. The larger options use an incorrect mole ratio.'
 elif qid=='9701_s19_12_q17':
  amount=Decimal('0.100')*6*Decimal(5)/6; assert amount==Decimal('0.500')
  expl='The hot-alkali equation gives 6NaOH : 5NaCl. Hence 0.600 mol NaOH makes 0.500 mol NaCl; 0.600 mol ignores the 5:6 ratio.'
 elif qid=='9701_w22_12_q21': expl='HOCl and ClO- contain chlorine at +1, because oxygen is -2. -1 is the oxidation state of chloride, not the disinfecting species.'
 elif qid=='9701_s21_12_q17': expl='ClO- is an active chlorine species that kills bacteria. Cl- is a separate product and is not the active disinfectant.'
 elif qid=='9701_s22_11_q12': expl='In ClO-, chlorine is +1 because oxygen is -2 and the ion has charge -1; elemental chlorine starts at 0. A change of zero overlooks oxidation.'
 else: expl='Use the balanced cold or hot alkali equation and assign chlorine oxidation numbers: cold gives -1 and +1, while hot gives -1 and +5. The tempting alternative confuses the reaction conditions or oxidation numbers.'
 item={'id':sub+f'-p{n:02d}','kcs':kcs,'kind':'mcq','difficulty':3,'command_word':None,'source':{'type':'past','ref':q['ref'],'qid':qid},'stem':stem,'options':opts,'answer':q['answer'],'marks':1,'explanation':expl}
 if q.get('image'): item['image']=q['image']
 items.append(item)
pack={'subtopic':sub,'spec':'9701','version':1,'note':'Subjects/9701 Chemistry/11 Group 17/11.4 The reactions of chlorine.md','outline':'Cold aqueous sodium hydroxide changes chlorine into chloride and chlorate(I); hot aqueous sodium hydroxide gives chloride and chlorate(V). Chlorine is both reduced (0 to -1) and oxidised (0 to +1 or +5), so both are disproportionation. In water, chlorine forms HOCl, which dissociates to ClO-. HOCl and ClO- kill bacteria.','misconceptions':mis,'worked':[{'id':'we1','kc':a,'problem':'Explain disproportionation of chlorine in hot aqueous sodium hydroxide.','steps':[{'do':'Write $3\\ce{Cl2} + 6\\ce{NaOH} \\rightarrow 5\\ce{NaCl} + \\ce{NaClO3} + 3\\ce{H2O}$.','why':'The balanced equation identifies both chlorine-containing products.'},{'do':'Assign chlorine oxidation numbers: 0 in $\\ce{Cl2}$, -1 in $\\ce{NaCl}$ and +5 in $\\ce{NaClO3}$.','why':'Oxidation numbers show both directions of electron transfer.'},{'do':'State that chlorine is reduced from 0 to -1 and oxidised from 0 to +5.','why':'Both changes in one element define disproportionation.'}],'faded':{'id':'we1f','problem':'Chlorine reacts with cold aqueous sodium hydroxide: Cl2 + 2NaOH -> NaCl + NaClO + H2O. Which explanation correctly shows why this is disproportionation? Enter 1, 2 or 3. (1) Chlorine is reduced from 0 in Cl2 to -1 in NaCl and oxidised from 0 in Cl2 to +1 in NaClO in the same reaction. (2) Chlorine is oxidised from 0 to +1 in both NaCl and NaClO. (3) Chlorine is reduced from 0 to -1 in both NaCl and NaClO.','answer':{'value':1,'unit':'','exact':True},'blank_from':1}}],'items':items,'flashcards':[{'id':'fc1','kc':a,'front':'What is disproportionation?','back':'Oxidation and reduction of the same element in the same reaction.'},{'id':'fc2','kc':b,'front':'Which species kill bacteria when chlorine is added to water?','back':'Hypochlorous acid, HOCl, and chlorate(I) ions, ClO-.'}],'diagrams':[]}
out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(pack,ensure_ascii=False,indent=1))
print(len(items))
