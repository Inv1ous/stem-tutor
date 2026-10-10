import json, math, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'build'))
from add_past import question_key
sub='9701-7.1'; kc=lambda n:f'{sub}.{n}'
note='Subjects/9701 Chemistry/07 Equilibria/7.1 Chemical equilibria: reversible reactions, dynamic equilibrium.md'
mis=[
('m1',1,'Equilibrium means reactions stop','Both reactions continue at equal rates in a closed system; concentrations stay constant.','ER 9701 s22 P22 Q3'),
('m2',3,'A catalyst moves the equilibrium position','A catalyst speeds both directions and does not change equilibrium composition.','research'),
('m3',4,'Include a pure solid in the Kc expression','Pure solids have constant activity and are omitted from the expression.','ER 9701 w20 P13 Q33'),
('m4',6,'Use moles in a Kp expression','Kp uses equilibrium partial pressures, found from mole fractions and total pressure.','ER 9701 w23 P22 Q2'),
('m5',9,'Pressure changes K at constant temperature','Only temperature changes the equilibrium constant; pressure can change composition.','research')]
mis=[dict(id=a,kc=kc(b),statement=c,refutation=d,contrast=d,source=e) for a,b,c,d,e in mis]
facts=[
('A reversible reaction proceeds in both forward and reverse directions; in a closed system dynamic equilibrium has equal forward and reverse rates and constant reactant and product concentrations.','equal forward and reverse rates','closed system'),
("Le Chatelier's principle: if a change is made to a system at dynamic equilibrium, the position of equilibrium moves to minimise this change.",'minimise the imposed change','position of equilibrium'),
('Higher temperature favours the endothermic direction; concentration changes favour consumption of the added species; higher pressure favours the side with fewer gas molecules; a catalyst changes rate but not position.','endothermic direction','fewer gas molecules'),
('For $aA+bB\\rightleftharpoons cC+dD$, $K_c=[C]^c[D]^d/([A]^a[B]^b)$ using equilibrium concentrations; omit pure solids and liquids.','equilibrium concentrations','stoichiometric powers'),
('Mole fraction is moles of a component divided by total moles; partial pressure is its mole fraction multiplied by total pressure.','moles divided by total moles','partial pressure'),
('For gaseous $aA+bB\\rightleftharpoons cC+dD$, $K_p=p_C^cp_D^d/(p_A^ap_B^b)$ using equilibrium partial pressures.','equilibrium partial pressures','stoichiometric powers'),
('Substitute equilibrium concentrations into $K_c$ or equilibrium partial pressures into $K_p$; simplify numerical value and units from the overall powers.','equilibrium values','units'),
('Use a change table: subtract reactant changes and add product changes in stoichiometric ratio, then use the given equilibrium datum or constant.','stoichiometric ratio','equilibrium amounts'),
('At fixed temperature, changing concentration or pressure or adding a catalyst does not change $K_c$ or $K_p$; changing temperature does.','temperature changes the constant','catalyst does not'),
('Haber: $N_2+3H_2\\rightleftharpoons2NH_3$ uses about 450 °C, 200 atm and iron. Contact: $2SO_2+O_2\\rightleftharpoons2SO_3$ uses about 450 °C, near atmospheric pressure and $V_2O_5$; conditions balance rate, yield and cost.','compromise temperature','catalyst')]
pack=dict(subtopic=sub,spec='9701',version=1,note=note,outline='Dynamic equilibrium in a closed system has continuing forward and reverse reactions at equal rates. Le Chatelier’s principle predicts how position responds to a disturbance. Equilibrium constants use concentrations or partial pressures at equilibrium; only temperature changes their values. Industrial conditions balance yield, rate and cost.',misconceptions=mis,worked=[],items=[],flashcards=[],diagrams=[])
for i,(full,key,other) in enumerate(facts,1):
    if i in (2,5):pack['flashcards'].append(dict(id=f'fc{i}',kc=kc(i),front=f'Define {"Le Chatelier’s principle" if i==2 else "mole fraction and partial pressure"}.',back=full))
    for j,(verb,prompt) in enumerate([('State',f'State the central rule for {key}.'),('Describe',f'Describe how {key} is used in chemical equilibrium.'),('Explain',f'Explain the role of {other}.'),('Give',f'Give the meaning of {key} in this topic.'),('Deduce',f'Deduce the relevant rule when considering {other}.'),('Explain',f'Explain {key} in an exam answer, including its relationship to {other}.')],1):
        pack['items'].append(dict(id=f'{sub}-i{i:02d}{j}',kcs=[kc(i)],kind='short',difficulty=4 if j==6 else (3 if j in (3,5) else 2),command_word=verb,source={'type':'generated'},stem=prompt,marks=1,rubric=[{'point':full,'keywords':[[key.split()[0].strip('$')]]}],explanation=full,hints=['Recall the relevant equilibrium definition.','Identify the species or condition being discussed.','Begin with the governing relationship.']))
# Computed numeric answers and all numeric distractors.
calc=[(5,'Calculate the partial pressure of a gas with mole amount 0.30 mol in a 1.20 mol mixture at 500 kPa.','kPa',lambda:0.30/1.20*500,lambda:0.30*500,'m4'),(7,'Calculate Kc for $A\\rightleftharpoons B$ when equilibrium concentrations are 0.20 and 0.80 mol dm^-3 respectively.','',lambda:0.80/0.20,lambda:0.20/0.80,'m3'),(8,'Calculate the moles of HI formed when 0.30 mol of H2 reacts with I2 according to $H_2+I_2\\rightleftharpoons2HI$.','mol',lambda:2*0.30,lambda:0.30,'m1')]
for n,stem,unit,fn,wrong,mid in calc:
    a=float(fn()); d=float(wrong()); assert not math.isclose(a,d)
    pack['items'].append(dict(id=f'{sub}-n{n}',kcs=[kc(n)],kind='numeric',difficulty=3,command_word='Calculate',source={'type':'generated'},stem=stem,marks=1,answer={'value':a,'unit':unit,'sf_ok':[2,3]},distractors=[{'value':d,'misconception':mid}],explanation=f'Apply the equilibrium relationship to obtain {a:g} {unit}.',hints=['Identify the relevant quantities.','Write the relationship before substituting.','Substitute the given equilibrium values.']))
for n,problem,steps,fade,ans,unit in [
(3,'For $N_2+3H_2\\rightleftharpoons2NH_3$, predict the effect of raising pressure.', [('Count four gaseous molecules on the left and two on the right.','Pressure favours fewer gas molecules.'),('The equilibrium shifts right.','This reduces the imposed pressure change.')],'Calculate the difference between the sums of gaseous coefficients on each side for $2SO_2+O_2\\rightleftharpoons2SO_3$.',1,''),
(4,'Deduce Kc for $N_2+3H_2\\rightleftharpoons2NH_3$.',[('Write product concentration over reactant concentrations.','Only equilibrium concentrations enter Kc.'),('$K_c=[NH_3]^2/([N_2][H_2]^3)$.','The coefficients become powers.')],'Calculate Kc for $H_2+I_2\\rightleftharpoons2HI$ when equilibrium concentrations of $H_2$, $I_2$ and $HI$ are 0.20, 0.20 and 0.40 mol dm^-3.',4,' '),
(6,'Deduce Kp for $N_2+3H_2\\rightleftharpoons2NH_3$.',[('Use equilibrium partial pressures.','Kp is pressure based.'),('$K_p=p_{NH_3}^2/(p_{N_2}p_{H_2}^3)$.','The coefficients become powers.')],'Calculate Kp for $H_2+I_2\\rightleftharpoons2HI$ when equilibrium partial pressures of $H_2$, $I_2$ and $HI$ are 20, 20 and 40 kPa.',4,' '),
(7,'For $A\\rightleftharpoons B$, calculate Kc if equilibrium concentrations are 0.20 and 0.80 mol dm^-3.',[('$K_c=[B]/[A]$.','Use equilibrium concentrations.'),('$K_c=0.80/0.20=4.0$.','Substitute in the correct order.')],'Calculate Kc if the equilibrium concentrations of A and B are 0.25 and 0.75 mol dm^-3.',3,''),
(8,'For $H_2+I_2\\rightleftharpoons2HI$, 0.30 mol of H2 reacts. Calculate HI formed.',[('Use the 1:2 mole ratio.','The coefficient of HI is two.'),('HI formed = 0.60 mol.','Multiply the extent by two.')],'Calculate HI formed if 0.20 mol of H2 reacts.',0.4,'mol')]:
    pack['worked'].append(dict(id=f'we{n}',kc=kc(n),problem=problem,steps=[{'do':a,'why':b} for a,b in steps],faded={'id':f'we{n}f','problem':fade,'answer':{'value':float(ans),'unit':unit,'sf_ok':[2,3]},'blank_from':1}))
# Prefer distinct paper questions with a complete text option set and spread across outcomes.
bank=json.loads((ROOT/'build/work/mcq/9701.tagged.json').read_text()); selected=[]; seen=set()
for target in [1,2,3,4,5,6,7,8,9,10,3,7]:
    choices=[m for m in bank if kc(target) in m.get('kcs',[]) and not m.get('off_syllabus') and m.get('answer') and m.get('options') and all(m['options'].values()) and m['id'] not in [x['id'] for x in selected] and question_key(m) not in seen]
    if not choices: continue
    choices.sort(key=lambda m:(not bool(m.get('er')),bool(m.get('image')),len(m['stem'])))
    m=choices[0]; selected.append(m);seen.add(question_key(m))
# Fill a missing past-paper slot with another distinct equilibrium question.
for m in bank:
    if len(selected)>=12: break
    if not any(x.startswith(sub+'.') for x in m.get('kcs',[])) or m.get('off_syllabus') or not m.get('answer') or not m.get('options') or not all(m['options'].values()) or question_key(m) in seen: continue
    selected.append(m); seen.add(question_key(m))
for j,m in enumerate(selected,1):
    pack['items'].append(dict(id=f'{sub}-p{j:02d}',kcs=[x for x in m['kcs'] if x.startswith(sub+'.')][:2],kind='mcq',difficulty=3,command_word=None,source={'type':'past','ref':m['ref'],'qid':m['id']},stem=m['stem'],options=m['options'],answer=m['answer'],image=m.get('image'),marks=1,explanation=(m.get('er') or 'The official key follows the equilibrium rule in the stem.')[:600]))
out=ROOT/'build/out/packs/9701/9701-7.1.json';out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(pack,ensure_ascii=False,indent=1))
print(len(pack['items']),len(selected))
