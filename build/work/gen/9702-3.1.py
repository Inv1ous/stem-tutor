import json
from pathlib import Path
from decimal import Decimal
ROOT=Path(__file__).resolve().parents[3]
sub='9702-3.1'; K=lambda n:f'{sub}.{n}'
source={'type':'generated'}
mis=[
 dict(id='m1',kc=K(1),statement='Mass is the pull of Earth on an object.',refutation='That pull is weight; mass measures inertia.',contrast='Mass is measured in kg; weight is a force in N.',source='ER 9702 w21 P12 Q8'),
 dict(id='m2',kc=K(2),statement='Any one applied force equals mass times acceleration.',refutation='The vector resultant of all forces equals mass times acceleration.',contrast='Subtract opposing forces before using $F=ma$.',source='ER 9702 w22 P23 Q2'),
 dict(id='m3',kc=K(4),statement='A rebound changes momentum by the difference of the two speed magnitudes.',refutation='Opposite directions have opposite velocity signs.',contrast='Use $\Delta p=m(v-u)$ with signed velocities.',source='ER 9702 w23 P13 Q8'),
 dict(id='m4',kc=K(5),statement='Equal and opposite forces on one body form a third-law pair.',refutation='A third-law pair acts on two different interacting bodies.',contrast='The forces have the same type and equal magnitude.',source='ER 9702 s21 P12 Q8'),
 dict(id='m5',kc=K(5),statement='An instant of zero velocity means zero resultant force.',refutation='The object may still accelerate at that instant.',contrast='A bouncing ball momentarily stops while the upward contact force exceeds its weight.',source='ER 9702 s22 P13 Q9'),
 dict(id='m6',kc=K(6),statement='Weight is the same as mass.',refutation='Weight is the gravitational force on a mass.',contrast='Use $W=mg$; weight changes if $g$ changes.',source='research')]
items=[]
def add(k,kind,stem,answer=None,options=None,rubric=None,explanation='',difficulty=2,word='Calculate',mislinks=None):
 i=len([x for x in items if x['source']['type']=='generated'])+1
 d=dict(id=f'{sub}-i{i:02d}',kcs=[K(k)],kind=kind,difficulty=difficulty,command_word=word,source=source,stem=stem,marks=1,explanation=explanation,hints=['Identify the physical quantity involved.','Write the relevant law or definition.','Check directions and SI units before solving.'])
 if kind=='numeric':d['answer']=answer
 if kind=='mcq':d.update(options=options,answer=answer,distractors=mislinks or {},shuffle=True)
 if kind=='short':d['rubric']=rubric
 items.append(d);return d
def short(k,stem,point,groups,explanation,word='Explain',difficulty=2):
 return add(k,'short',stem,rubric=[{'point':point,'keywords':groups}],explanation=explanation,word=word,difficulty=difficulty)
def num(k,stem,value,unit,explanation,difficulty=3):
 return add(k,'numeric',stem,answer={'value':float(value),'unit':unit,'sf_ok':[2,3]},explanation=explanation,difficulty=difficulty)
def mcq(k,stem,opts,right,explanation,wrong=None,difficulty=2):
 return add(k,'mcq',stem,right,opts,explanation=explanation,word='Identify',mislinks=wrong,difficulty=difficulty)
# Inertia
short(1,'Define mass in terms of motion.','Property resisting change in motion',[['resists','resistance'],['change in motion','change of motion']], 'Mass is the property of an object that resists change in motion.',word='Define')
mcq(1,'Which object has the greater resistance to a change in motion?',{'A':'A 1 kg trolley','B':'A 3 kg trolley','C':'Both equally','D':'Cannot be inferred from mass'},'B','Greater mass means greater inertia.',{'D':'m1'})
short(1,'Explain why an empty trolley accelerates more than a loaded trolley under the same resultant force.','Loaded trolley has greater mass, hence less acceleration',[['greater mass','larger mass'],['less acceleration','smaller acceleration']], 'For the same resultant force, $a=F/m$.',difficulty=4)
mcq(1,'A trolley moves at constant velocity. What does its mass measure?',{'A':'Its gravitational force','B':'Its acceleration','C':'Its resistance to changing this velocity','D':'Its resultant force'},'C','Mass measures inertia even while the trolley moves at constant velocity.',{'A':'m1'})
short(1,'Compare the mass of an object on Earth and the Moon.','Mass stays unchanged',[['same','unchanged','constant']], 'Mass is an intrinsic property and is unchanged by location.',word='Compare')
mcq(1,'Two carts experience the same non-zero resultant force. Cart X has twice the mass of Y. Compare their accelerations.',{'A':'X has half the acceleration of Y','B':'X has twice the acceleration of Y','C':'They accelerate equally','D':'X has zero acceleration'},'A','From $a=F/m$, doubling mass halves acceleration.',difficulty=4)
# F=ma
for m,a in [(2.4,3.0),(5.0,1.8)]:num(2,f'Calculate the resultant force on a {m} kg body accelerating at {a} m s⁻¹ in a straight line.',Decimal(str(m))*Decimal(str(a)),'N','Use $F=ma$ with the resultant force.')
num(2,'A 4.0 kg trolley is pulled right by 18 N and resisted left by 6.0 N. Calculate its acceleration.',(18-6)/4,'m s^-2','The resultant is $18-6=12$ N right, so $a=12/4$.',4)
short(2,'State the direction of the acceleration relative to the resultant force.','Same direction',[['same direction']], 'Acceleration and the resultant force always point in the same direction.',word='State')
mcq(2,'A 2 kg object has forces of 12 N east and 4 N west. What is its acceleration?',{'A':'4 m s⁻² east','B':'8 m s⁻² east','C':'6 m s⁻² east','D':'8 m s⁻² west'},'A','The resultant is 8 N east and $a=8/2=4$ m s⁻² east.',{'B':'m2'},4)
short(2,'Explain why a constant velocity implies zero resultant force for a body of constant mass.','Zero acceleration gives zero resultant force',[['zero acceleration','no acceleration'],['zero resultant force','no resultant force']], 'Constant velocity means $a=0$, hence $F=ma=0$.',difficulty=4)
# momentum
for m,v in [(0.6,5),(2.5,4)]:num(3,f'Calculate the momentum of a {m} kg object travelling at {v} m s⁻¹ east.',Decimal(str(m))*Decimal(str(v)),'kg m s^-1','Momentum is mass multiplied by velocity, in the velocity direction.')
short(3,'Define linear momentum.','Product of mass and velocity',[['mass'],['velocity']], 'Linear momentum is the product of mass and velocity; $p=mv$.',word='Define')
mcq(3,'A ball reverses its velocity from 3 m s⁻¹ east to 3 m s⁻¹ west. What happens to its momentum?',{'A':'It remains unchanged','B':'It reverses direction','C':'It becomes zero','D':'It doubles in the original direction'},'B','Momentum is a vector and follows the direction of velocity.',{'A':'m3'})
num(3,'A 0.20 kg ball changes velocity from 5.0 m s⁻¹ east to 3.0 m s⁻¹ west. Calculate the magnitude of its change in momentum.',Decimal('0.20')*(Decimal('5.0')+Decimal('3.0')),'kg m s^-1','Taking east as positive, $|\Delta p|=0.20|-3.0-5.0|$.',4)
short(3,'State the SI unit of linear momentum.','kg m s⁻¹',[['kg'],['m'],['s']], 'The unit follows from $p=mv$: kg m s⁻¹.',word='State')
# force as dp/dt
short(4,'Define force in terms of momentum.','Rate of change of momentum',[['rate of change'],['momentum']], 'Resultant force is the rate of change of momentum: $F=\Delta p/\Delta t$.',word='Define')
for mass,u,v,t in [('0.20','4','-2','0.10'),('0.50','6','-4','0.25')]:
 val=abs(Decimal(mass)*(Decimal(v)-Decimal(u))/Decimal(t))
 num(4,f'A {mass} kg ball changes velocity from {u} m s⁻¹ to {v} m s⁻¹ in {t} s. Calculate the magnitude of its average resultant force.',val,'N','Find the signed change in momentum, then divide its magnitude by contact time.',4)
num(4,'A resultant force of 15 N acts for 0.40 s. Calculate the magnitude of the momentum change.',Decimal('15')*Decimal('0.40'),'kg m s^-1','From $F=\Delta p/\Delta t$, $\Delta p=F\Delta t$.')
mcq(4,'A ball rebounds from a wall at the same speed. Which quantity is zero?',{'A':'Its change in velocity','B':'Its change in momentum','C':'Its average force','D':'Its change in kinetic energy'},'D','Speed and kinetic energy are unchanged, but vector velocity and momentum reverse.',{'B':'m3'},4)
short(4,'Explain why the resultant force equals $ma$ for constant mass.','Differentiate momentum at fixed mass',[['momentum','mv'],['rate of change','change per time'],['acceleration']], 'For constant $m$, $F=\Delta(mv)/\Delta t=m\Delta v/\Delta t=ma$.',difficulty=4)
# laws
short(5,"State Newton's first law of motion.",'Zero resultant force means rest or constant velocity',[['zero resultant force','no resultant force'],['rest','stationary'],['constant velocity','uniform velocity']], 'With zero resultant force, a body remains at rest or moves at constant velocity.',word='State')
short(5,"State Newton's second law in terms of momentum.",'Resultant force equals rate of change of momentum',[['resultant force'],['rate of change'],['momentum']], 'The resultant force equals the rate of change of momentum and acts in that direction.',word='State')
short(5,"State Newton's third law of motion.",'Interacting bodies exert equal and opposite forces on each other',[['two bodies','different objects'],['equal'],['opposite']], 'The interacting bodies exert equal magnitude, opposite direction forces of the same type on each other.',word='State')
mcq(5,'A book rests on a table. Which is the third-law partner of the Earth’s gravitational force on the book?',{'A':'The table’s support force on the book','B':'The book’s gravitational force on Earth','C':'The book’s force on the table','D':'Earth’s force on the table'},'B','The partner is the same gravitational interaction on the other body.',{'A':'m4'},4)
short(5,'A ball is momentarily stationary while rebounding upward. Explain why the resultant force need not be zero.','Velocity can be zero while acceleration is non-zero',[['zero velocity','stationary'],['acceleration','changing velocity']], 'At the turnaround instant the ball has zero velocity but upward acceleration.',difficulty=4)
mcq(5,'An object moves at constant velocity in a straight line. Which law directly states the consequence for resultant force?',{'A':'Newton’s first law','B':'Newton’s second law only','C':'Newton’s third law','D':'Law of gravitation'},'A','Newton’s first law relates zero resultant force to constant velocity.')
# weight
short(6,'Define weight.','Force on mass due to gravitational field',[['force'],['gravitational field','gravity']], 'Weight is the force on an object due to a gravitational field.',word='Define')
for m in ['2.0','7.5']:
 num(6,f'Calculate the weight of a {m} kg object where $g=9.81$ m s⁻².',Decimal(m)*Decimal('9.81'),'N','Use $W=mg$ with $g=9.81$ m s⁻².')
num(6,'An object weighs 49.05 N where $g=9.81$ m s⁻². Calculate its mass.',Decimal('49.05')/Decimal('9.81'),'kg','Rearrange $W=mg$ to $m=W/g$.')
mcq(6,'An object falls at terminal velocity. Which statement about its weight is correct?',{'A':'Weight is zero','B':'Weight equals its mass','C':'Weight equals the upward drag in magnitude','D':'Weight equals mass times its zero acceleration'},'C','At terminal velocity the resultant force is zero, so drag balances the non-zero weight.',{'A':'m6'},4)
short(6,'Explain why the same object has less weight on the Moon than on Earth.','Gravitational field strength is less, mass unchanged',[['gravitational field','acceleration of free fall'],['less','smaller'],['mass']], 'Weight $W=mg$ falls when $g$ is smaller, while mass is unchanged.',difficulty=4)
# Parameterised retrieval: fixed worked instance plus independently checked generated variants.
for kc, ordinal, stem, params, expr, wrong_expr, mid in [
 (2,0,'Calculate the resultant force on a [[m]] kg body accelerating at [[a]] m s⁻¹.',{'m':{'choices':[2.4,3.6,4.8]},'a':{'choices':[3.0,4.0,5.0]}},'m*a','m+a','m2'),
 (3,0,'Calculate the momentum of a [[m]] kg body moving at [[v]] m s⁻¹ east.',{'m':{'choices':[0.6,0.8,1.2]},'v':{'choices':[5.0,7.0,9.0]}},'m*v','m+v','m3'),
 (4,0,'A [[m]] kg ball changes velocity from [[u]] m s⁻¹ to [[v]] m s⁻¹ in [[t]] s. Calculate average force magnitude.',{'m':{'choices':[0.2,0.4,0.6]},'u':{'choices':[4.0,6.0,8.0]},'v':{'choices':[-2.0,-4.0,-6.0]},'t':{'choices':[0.1,0.2,0.4]}},'abs(m*(v-u)/t)','abs(m*(u+v)/t)','m3'),
 (6,0,'Calculate the weight of a [[m]] kg object at $g=9.81$ m s⁻².',{'m':{'choices':[2.0,4.0,7.5]}},'m*9.81','m','m6')]:
 target=[x for x in items if x['kcs']==[K(kc)] and x['kind']=='numeric'][ordinal]
 target['stem']=stem
 target['template']={'params':params,'derived':{},'answer':expr,'distractors':[{'expr':wrong_expr,'misconception':mid}],'constraints':[]}
 # The base answer remains a checked sample; the runtime expression determines each variant.
 from itertools import product
 import math
 keys=list(params)
 for vals in product(*(params[k]['choices'] for k in keys)):
  env=dict(zip(keys,vals))
  good=eval(expr,{'abs':abs},env);bad=eval(wrong_expr,{'abs':abs},env)
  assert math.isfinite(good) and abs(good-bad)>0.02*max(abs(good),1e-12)
# Official MCQs: exact bank fields and keys.
bank={m['id']:m for m in json.loads((ROOT/'build/work/mcq/9702.tagged.json').read_text())}
selected=['9702_w21_12_q8','9702_w23_12_q7','9702_w21_12_q9','9702_s19_12_q10','9702_s19_11_q11','9702_w23_13_q8','9702_w23_11_q8','9702_w21_13_q8','9702_s21_12_q8','9702_s21_11_q8','9702_w23_11_q7','9702_w25_12_q8']
for j,qid in enumerate(selected,1):
 m=bank[qid]
 explanation={
 '9702_w21_12_q8':'Mass is inertia: the property resisting change in motion. Counting atoms (C) does not account for their masses.',
 '9702_w23_12_q7':'Apply $F=ma$ to both connected blocks and eliminate tension; the friction is 3.5 N. Options B and C come from incomplete force balances.',
 '9702_w21_12_q9':'Both mass and air resistance double, so $(mg-R)/m$ is unchanged. Option A overlooks that weight also doubles.',
 '9702_s19_12_q10':'Use $F-R=ma$ and $2F-R=3ma$; solving gives $R=ma$. Option B omits the simultaneous balance.',
 '9702_s19_11_q11':'Momentum reverses from $mv$ to $-mv$, giving a change of magnitude $2mv$. Option A confuses conserved kinetic energy with unchanged momentum.',
 '9702_w23_13_q8':'The velocities have opposite signs, so $|\Delta p|=0.200(14.0+7.0)=4.2$ kg m s⁻¹ and $F=7.0$ N. Option B subtracts the speeds.',
 '9702_w23_11_q8':'The velocity change has magnitude 30 m s⁻¹; $F=0.200(30)/0.10=60$ N. Option A ignores the rebound direction.',
 '9702_w21_13_q8':'Convert 90 kg per minute to 1.5 kg s⁻¹, then $F=1.5(20)=30$ N. Option C uses minutes as seconds.',
 '9702_s21_12_q8':'The book pulls Earth gravitationally upward with force $W$. Option B is the support force on the same book, so it is not the third-law partner.',
 '9702_s21_11_q8':'The partner of Earth pulling the rocket is the rocket pulling Earth gravitationally. Exhaust forces are a different interaction.',
 '9702_w23_11_q7':'For downward acceleration $W-R=ma$, so $R<W$; the man pushes the floor with magnitude $R$. Option A wrongly assumes equilibrium.',
 '9702_w25_12_q8':'Weight is gravitational force on an object, equal to $mg$. Option A uses the object’s actual acceleration, which may differ from $g$.'}[qid]
 items.append(dict(id=f'{sub}-p{j:02d}',kcs=[k for k in m['kcs'] if k.startswith(sub)],kind='mcq',difficulty=3,command_word=None,source={'type':'past','ref':m['ref'],'qid':qid},stem=m['stem'],options=m['options'],answer=m['answer'],image=m.get('image'),marks=1,explanation=explanation,hints=['Identify the body and relevant law.','Use signed directions for vector quantities.','Check the force balance and units.']))
# Worked solutions: arithmetic computed from source quantities.
worked=[]
def work(n,problem,formula,substitution,value,unit,faded_problem,faded_value):
 ans=lambda v:{'value':float(v),'unit':unit,'sf_ok':[2,3]}
 worked.append({'id':f'we{n}','kc':K(n),'problem':problem,'steps':[{'do':formula,'why':'Start from the definition or law used for this quantity.'},{'do':substitution,'why':'Substitute SI values with a consistent positive direction.'},{'do':f'Answer: {value} {unit}.','why':'Give the magnitude and SI unit.','check':{'kind':'numeric','answer':ans(value)}}], 'faded':{'id':f'we{n}f','problem':faded_problem,'answer':ans(faded_value),'blank_from':1}})
work(2,'A 3.0 kg body has 14 N right and 5.0 N left. Find acceleration.','$F_{\\mathrm{net}}=ma$.','$a=(14-5.0)/3.0$.',Decimal('9')/Decimal('3'),'m s^-2','A 2.0 kg body has 11 N right and 3.0 N left. Find acceleration.',Decimal('8')/Decimal('2'))
work(3,'Find momentum of a 0.40 kg object moving at 6.0 m s⁻¹.','$p=mv$.','$p=0.40(6.0)$.',Decimal('.40')*Decimal('6'),'kg m s^-1','Find momentum of a 0.50 kg object moving at 8.0 m s⁻¹.',Decimal('.50')*Decimal('8'))
work(4,'A 0.20 kg ball rebounds from +5.0 to −3.0 m s⁻¹ in 0.10 s. Find average force magnitude.','$F=\\Delta p/\\Delta t$.','$|F|=0.20|-3.0-5.0|/0.10$.',Decimal('.2')*Decimal('8')/Decimal('.1'),'N','A 0.30 kg ball changes velocity from +4.0 to −2.0 m s⁻¹ in 0.20 s. Find average force magnitude.',Decimal('.3')*Decimal('6')/Decimal('.2'))
work(5,'A 60 kg lift passenger accelerates downward at 2.0 m s⁻². Find floor force on passenger.','$W-R=ma$, so $R=m(g-a)$.','$R=60(9.81-2.0)$.',Decimal('60')*(Decimal('9.81')-Decimal('2')),'N','A 50 kg lift passenger accelerates downward at 1.0 m s⁻². Find floor force.',Decimal('50')*(Decimal('9.81')-Decimal('1')))
work(6,'Find the weight of a 4.0 kg mass at $g=9.81$ m s⁻².','$W=mg$.','$W=4.0(9.81)$.',Decimal('4')*Decimal('9.81'),'N','Find the weight of a 3.0 kg mass at $g=9.81$ m s⁻².',Decimal('3')*Decimal('9.81'))
flash=[('What is mass?','The property of an object that resists change in motion.'),('Define linear momentum.','The product of mass and velocity: $p=mv$.'),('Define resultant force in momentum terms.','The rate of change of momentum: $F=\\Delta p/\\Delta t$.'),('State Newton’s first law.','An object remains at rest or at constant velocity unless acted on by a resultant force.'),('State Newton’s second law.','Resultant force is the rate of change of momentum, in the direction of the force.'),('State Newton’s third law.','Interacting bodies exert equal and opposite forces of the same type on each other.'),('Define weight.','The force on an object due to a gravitational field; $W=mg$.')]
fcs=[{'id':f'fc{j}','kc':K([1,3,4,5,5,5,6][j-1]),'front':q,'back':a} for j,(q,a) in enumerate(flash,1)]
pack={'subtopic':sub,'spec':'9702','version':1,'note':'Subjects/9702 Physics/03 Dynamics/3.1 Momentum and Newton’s laws of motion.md','outline':'Mass resists changes in motion. Resultant force produces acceleration in its direction: $F=ma$. Linear momentum is the vector $p=mv$; resultant force is its rate of change, $F=\\Delta p/\\Delta t$. Newton’s first law describes zero resultant force, the second connects force and changing momentum, and the third identifies equal and opposite forces on different interacting bodies. Weight is the force of a gravitational field on mass, $W=mg$.','misconceptions':mis,'worked':worked,'items':items,'flashcards':fcs,'diagrams':[]}
out=ROOT/'build/out/packs/9702/9702-3.1.json';out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(pack,ensure_ascii=False,indent=1))
print(out,len(items),len(worked))
