"""Generate the 9702-5.1 content pack; compute all numerical checks and variants."""
import json, math
from pathlib import Path
import sympy as sp
ROOT = Path(__file__).resolve().parents[3]
SUB = '9702-5.1'
K = {n:f'{SUB}.{n}' for n in range(1,8)}
NOTE = 'Subjects/9702 Physics/05 Work, energy and power/5.1 Energy conservation.md'
OUT = ROOT/'build/out/packs/9702/9702-5.1.json'
G = 9.81

def ans(v,u='',sf=(2,3)):
    return {'value':float(v),'unit':u,'sf_ok':list(sf)}

def check(v,u=''):
    return {'kind':'numeric','answer':ans(v,u)}

# The numerical examples and quoted past-paper answers are calculated, rather than typed as keys.
assert 0.5*.30*8.0**2-.30*G*1.9 > 3.9 and round(0.5*.30*8.0**2-.30*G*1.9,1)==4.0
assert (50+5-10)==45 and 120/.60==200 and 120/.60-120==80
assert round((2400+1800*math.sin(math.pi/6)) and 36000/(2400+1800*math.sin(math.pi/6)))==11
assert round(12000*24/1000,-1)==290 and round((80000+200*70)*G*math.sin(math.pi/6)*6/.40/1e6,1)==6.9
assert round(.5*1000*G*30/60/.70/1000,1)==3.5
assert round((60/70)**2,2)==.73 and round(600*G*12/60/1000,1)==1.2
assert round(1.8*8-4.8,1)==9.6 and 9.6/4==2.4
F,s,theta,t,v=sp.symbols('F s theta t v', positive=True)
assert sp.simplify((F*s)/t-F*(s/t))==0
assert sp.simplify(F*s*sp.cos(theta)/t-F*v*sp.cos(theta)).subs(v,s/t)==0

misconceptions=[
 {'id':'m1','kc':K[1],'statement':'Multiplying force by the full path length when displacement is not along the force.','refutation':'Work done by a force is its component along the displacement multiplied by the displacement: $W=Fs\\cos\\theta$. A perpendicular force does zero work.','contrast':'A $10\\ \\mathrm{N}$ force at $60^\\circ$ to a $4.0\\ \\mathrm{m}$ displacement does $20\\ \\mathrm{J}$, not $40\\ \\mathrm{J}$.','source':'ER 9702 w19 P23 Q2'},
 {'id':'m2','kc':K[2],'statement':'Assuming a fall at constant speed turns lost gravitational potential energy into kinetic energy.','refutation':'Constant speed means constant kinetic energy. Energy lost from the gravitational store is transferred to thermal energy of the object and surroundings by resistive forces.','contrast':'A stone at terminal speed loses gravitational potential energy while its kinetic energy stays unchanged.','source':'ER 9702 s22 P23 Q4'},
 {'id':'m3','kc':K[4],'statement':'Multiplying useful output by efficiency to find the input.','refutation':'Efficiency is useful output divided by total input. Therefore input equals useful output divided by efficiency; losses equal input minus useful output.','contrast':'For $120\\ \\mathrm{W}$ useful output at $60\\%$ efficiency, input is $200\\ \\mathrm{W}$ and waste is $80\\ \\mathrm{W}$.','source':'ER 9702 w19 P11 Q15'},
 {'id':'m4','kc':K[5],'statement':'Defining power as force times velocity or simply energy per unit time.','refutation':'The precise definition is work done per unit time, or energy transferred per unit time. $P=Fv$ follows only for a force component along the velocity.','contrast':'A $100\\ \\mathrm{J}$ energy transfer in $5.0\\ \\mathrm{s}$ gives $20\\ \\mathrm{W}$, regardless of how force and speed are described.','source':'ER 9702 s22 P21 Q3'},
 {'id':'m5','kc':K[7],'statement':'Using the resultant force for the power supplied by an engine when resistance is present.','refutation':'Power supplied by a particular force is that force times the velocity component along it. The resultant force times velocity is the rate of change of kinetic energy.','contrast':'With $12\\,000\\ \\mathrm{N}$ thrust, $3000\\ \\mathrm{N}$ drag and $24\\ \\mathrm{m\\,s^{-1}}$, engine power is $288\\ \\mathrm{kW}$, while net mechanical power is $216\\ \\mathrm{kW}$.','source':'ER 9702 s22 P13 Q18'},
 {'id':'m6','kc':K[7],'statement':'Ignoring the component of weight down a slope when calculating a vehicle’s driving force.','refutation':'At constant speed the driving force balances resistance plus the component of weight down the slope, $mg\\sin\\theta$ or $W\\sin\\theta$.','contrast':'A $1800\\ \\mathrm{N}$ weight on a $30^\\circ$ slope adds $900\\ \\mathrm{N}$ to the required driving force.','source':'ER 9702 w21 P12 Q20'},
]

worked=[]
def work(n,k,problem,steps,faded_problem,faded_answer,blank=1):
    worked.append({'id':f'we{n}','kc':K[k],'problem':problem,'steps':[{'do':a,'why':b,'check':check(c,u) if c is not None else None} for a,b,c,u in steps], 'faded':{'id':f'we{n}f','problem':faded_problem,'answer':ans(*faded_answer),'blank_from':blank}})
work(1,1,'A $40\\ \\mathrm{N}$ force acts at $60^\\circ$ to a $3.0\\ \\mathrm{m}$ displacement. Find its work.',[
 ('State $W=Fs\\cos\\theta$.','Only the component along the displacement transfers energy.',None,''),('Substitute $W=40\\times3.0\\times\\cos60^\\circ$.','The angle is between force and displacement.',60,'J'),('Give $W=60\\ \\mathrm{J}$.','Work is measured in joules.',60,'J')], 'A $30\\ \\mathrm{N}$ force acts at $60^\\circ$ to a $4.0\\ \\mathrm{m}$ displacement. Find its work.',(30*4*math.cos(math.pi/3),'J'))
work(2,2,'A $0.30\\ \\mathrm{kg}$ object rises at $8.0\\ \\mathrm{m\\,s^{-1}}$ and stops $1.9\\ \\mathrm{m}$ above its launch point. Find work against air resistance.',[
 ('Write $E_{\\mathrm{k,initial}}=mgh+W_{\\mathrm{air}}$.','Energy is conserved when the energy transferred by drag is included.',None,''),('Find $E_{\\mathrm{k,initial}}=\\tfrac12(0.30)(8.0)^2=9.6\\ \\mathrm{J}$ and $mgh=(0.30)(9.81)(1.9)=5.59\\ \\mathrm{J}$.','At the top, kinetic energy is zero.',9.6,'J'),('Subtract: $W_{\\mathrm{air}}=9.6-5.59=4.0\\ \\mathrm{J}$ to two significant figures.','The missing mechanical energy was transferred by drag.',round(.5*.30*8**2-.30*G*1.9,1),'J')], 'A $0.20\\ \\mathrm{kg}$ ball launches upwards at $10\\ \\mathrm{m\\,s^{-1}}$ and stops $4.0\\ \\mathrm{m}$ higher. Find energy transferred by drag.',(.5*.20*10**2-.20*G*4,'J'))
work(3,4,'A motor has useful output power $120\\ \\mathrm{W}$ and efficiency $60\\%$. Find input and wasted power.',[
 ('Write $\\eta=P_{\\mathrm{useful}}/P_{\\mathrm{input}}$.','Energy and power ratios are equal when measured over the same time.',None,''),('Convert $60\\%=0.60$ and calculate $P_{\\mathrm{input}}=120/0.60=200\\ \\mathrm{W}$.','Divide by efficiency when solving for total input.',120/.6,'W'),('Find waste $=200-120=80\\ \\mathrm{W}$.','Input is partitioned into useful and wasted output.',120/.6-120,'W')], 'A device supplies $150\\ \\mathrm{W}$ useful power at $75\\%$ efficiency. Find its input power.',(150/.75,'W'))
work(4,6,'A machine transfers $900\\ \\mathrm{J}$ of work in $30\\ \\mathrm{s}$. Find its average power.',[
 ('State $P=W/t$.','Power is the rate of doing work.',None,''),('Substitute $P=900/30$.','Use consistent joule and second units.',900/30,'W'),('Give $P=30\\ \\mathrm{W}$.','One watt is one joule per second.',900/30,'W')], 'A motor does $1200\\ \\mathrm{J}$ of work in $40\\ \\mathrm{s}$. Find average power.',(1200/40,'W'))
work(5,7,'A car travels at $24\\ \\mathrm{m\\,s^{-1}}$ with engine thrust $12\\,000\\ \\mathrm{N}$. Find the engine’s instantaneous power.',[
 ('Derive $P=W/t=(Fs)/t=Fv$.','Speed $v=s/t$ for displacement along the force.',None,''),('Substitute $P=12\\,000\\times24$.','Use thrust for engine output, even if drag also acts.',12000*24,'W'),('Convert $P=288\\ \\mathrm{kW}$.','Divide watts by $1000$ to express kilowatts.',12000*24/1000,'kW')], 'A locomotive exerts $15\\,000\\ \\mathrm{N}$ along its motion at $20\\ \\mathrm{m\\,s^{-1}}$. Find its power in kilowatts.',(15000*20/1000,'kW'))

items=[]
def tpl(k,stem,params,expr,unit,wrong,explanation,hints,difficulty=3):
    n=len([x for x in items if x['source']['type']=='generated'])+1
    env={q:(p.get('choices') or [p['min']])[0] for q,p in params.items()}
    val=eval(expr,{'__builtins__':{},'sqrt':math.sqrt,'sin':math.sin,'cos':math.cos,'pi':math.pi},env)
    ds=[]
    for e,m in wrong:
        dv=eval(e,{'__builtins__':{},'sqrt':math.sqrt,'sin':math.sin,'cos':math.cos,'pi':math.pi},env)
        assert abs(dv-val)>.02*max(abs(val),1e-12)
        ds.append({'value':dv,'misconception':m})
    items.append({'id':f'{SUB}-i{n:02d}','kcs':[K[k]],'kind':'numeric','difficulty':difficulty,'command_word':'Calculate','source':{'type':'generated'},'stem':stem,'marks':2,'answer':ans(val,unit),'distractors':ds,'template':{'params':params,'answer':expr,'distractors':[{'expr':e,'misconception':m} for e,m in wrong]},'explanation':explanation,'hints':hints})

def choices(**kwargs): return {k:{'choices':v} for k,v in kwargs.items()}

tpl(1,'A force of [[F]] N acts in the direction of a [[s]] m displacement. Calculate its work.',choices(F=[12,18,24],s=[3,5,7]),'F*s','J',[('F','m1')],'Work is the force component along displacement times displacement, $W=Fs$.',['What direction is the displacement relative to the force?','Use the force-displacement definition of work.','Multiply the stated force by the displacement.'],2)
tpl(1,'A [[F]] N force is [[a]]° to a [[s]] m displacement. Calculate the work done by the force.',choices(F=[20,30,40],a=[60],s=[4,6,8]),'F*s*cos(a*pi/180)','J',[('F*s','m1')],'Resolve the force along displacement: $W=Fs\\cos\\theta$.',['Only one component of force does work.','Resolve the force along the displacement.','Write $W=Fs\\cos\\theta$.'],4)
tpl(2,'A trolley has [[initial]] J of kinetic energy, loses [[gpe]] J of gravitational potential energy and transfers [[loss]] J to thermal energy. Calculate its final kinetic energy.',choices(initial=[20,30,40],gpe=[60,80],loss=[10,15]),'initial+gpe-loss','J',[('initial+gpe','m2')],'The lost gravitational potential energy increases kinetic energy except for the amount transferred thermally.',['List initial and final energy stores.','Include the thermal transfer in conservation of energy.','Use final kinetic energy = initial kinetic + lost GPE − thermal loss.'],4)
tpl(2,'A falling object loses [[gpe]] J of gravitational potential energy at constant speed. Calculate the energy transferred to thermal stores.',choices(gpe=[40,60,80]),'gpe','J',[('0','m2')],'Its kinetic energy stays constant, so all lost gravitational potential energy is transferred by resistance.',['What does constant speed tell you about kinetic energy?','Conserve total energy including the surroundings.','Set the thermal gain equal to the lost gravitational energy.'],3)
tpl(3,'A device receives [[input]] J and gives [[useful]] J of useful energy. Calculate its efficiency as a decimal.',choices(input=[200,300,400],useful=[60,80]),'useful/input','',[('input/useful','m3')],'Efficiency is useful output divided by total input.',['Identify which energy is useful.','Form a ratio of output to input.','Put useful output in the numerator.'],2)
tpl(3,'A system has [[input]] J input and [[waste]] J wasted energy. Calculate its efficiency as a percentage.',choices(input=[200,400,600],waste=[40,60]),'100*(input-waste)/input','%',[('100*waste/input','m3')],'Useful energy is input minus waste; divide it by input and multiply by 100%.',['First determine useful output.','Subtract waste from total input.','Divide useful output by total input, then multiply by 100.'],3)
tpl(4,'A motor provides [[useful]] W useful output at [[eta]]% efficiency. Calculate its input power.',choices(useful=[120,180,240],eta=[40,60,80]),'100*useful/eta','W',[('useful*eta/100','m3')],'Rearrange $\\eta=P_{\\mathrm{useful}}/P_{\\mathrm{input}}$ to find input.',['Convert the percent to a decimal.','Rearrange the efficiency ratio for input.','Divide useful output by the decimal efficiency.'],3)
tpl(4,'A machine receives [[input]] J and operates at [[eta]]% efficiency. Calculate its wasted energy.',choices(input=[300,500,700],eta=[40,60,80]),'input*(100-eta)/100','J',[('input*eta/100','m3')],'Waste is total input minus useful output.',['The useful and wasted parts add to input.','Find the fraction that is wasted.','Use $1-\\eta$ as the waste fraction.'],4)
tpl(6,'A motor does [[W]] J of work in [[t]] s. Calculate its average power.',choices(W=[600,900,1200],t=[20,30,40]),'W/t','W',[('W*t','m4')],'Average power is work done divided by time.',['Power measures a rate.','Use the definition of power.','Divide the work in joules by the time in seconds.'],2)
tpl(6,'A motor delivers [[P]] W for [[t]] s. Calculate the work done.',choices(P=[40,60,80],t=[15,25,35]),'P*t','J',[('P/t','m4')],'Rearranging $P=W/t$ gives $W=Pt$.',['Start from the definition of power.','Rearrange for work.','Multiply the power by elapsed time.'],3)
tpl(7,'An engine exerts [[F]] N thrust along motion at [[v]] m s⁻¹. Calculate the power supplied by the engine.',choices(F=[3000,5000,7000],v=[12,18,24]),'F*v','W',[('F/v','m5')],'The instantaneous rate of work by thrust is $P=Fv$.',['Which force supplies the requested power?','Use the force and speed relationship.','Multiply thrust by speed.'],3)
tpl(7,'A vehicle climbs a [[angle]]° slope at constant speed [[v]] m s⁻¹. Its weight is [[weight]] N and resistance along the slope is [[drag]] N. Calculate the driving power.',choices(angle=[30],v=[8,12,16],weight=[1000,1600,2000],drag=[300,500]),'(drag+weight*sin(angle*pi/180))*v','W',[('drag*v','m6'),('weight*sin(angle*pi/180)*v','m6')],'At constant speed, driving thrust balances resistance and the weight component down the slope; then $P=Fv$.',['Draw the forces along the slope.','Resolve the weight parallel to the slope and balance forces.','Add drag and $W\\sin\\theta$ before multiplying by speed.'],5)

shorts=[
 ('Define power.','Power is work done per unit time.',['work done','work'],['per unit time','rate']),
 ('State the meaning of one watt.','One watt is one joule of work done per second.',['one joule','1 j'],['per second','each second']),
 ('Define power using energy transfer.','Power is energy transferred per unit time.',['energy transferred','transfer of energy'],['per unit time','rate']),
 ('Explain why $P=Fv$ does not by itself define power.','It is a relationship for force and speed in the direction of motion; the definition is work done per unit time.',['work done','energy transferred'],['per unit time','rate']),
 ('State the SI unit of power and express it in joules per second.','The unit is the watt, equal to one joule per second.',['watt','w'],['joule per second','j s']),
 ('State the quantity found by dividing work done by elapsed time.','The quotient is average power: work done per unit time.',['power'],['work done per unit time','rate of doing work'])]
for q,a,g1,g2 in shorts:
    n=len([x for x in items if x['source']['type']=='generated'])+1
    items.append({'id':f'{SUB}-i{n:02d}','kcs':[K[5]],'kind':'short','difficulty':2 if n<16 else 3,'command_word':'Define' if q.startswith('Define') else 'State' if q.startswith('State') else 'Explain','source':{'type':'generated'},'stem':q,'marks':1,'rubric':[{'point':a,'keywords':[g1,g2]}],'explanation':a,'hints':['Think of a rate rather than a total.','What happens to the amount of work as time changes?','Use work done divided by time in words.']})

# Preserve the tagged bank's original wording, options, letters, and image path.
bank={m['id']:m for m in json.loads((ROOT/'build/work/mcq/9702.tagged.json').read_text())}
past_specs=[
 ('9702_w24_13_q19',1,'Only the vertical displacement $q$ is in the direction opposite to weight, so the energy transferred to the weight is $Wq$. $Wp$ uses the horizontal displacement; $Wr$ uses the diagonal path.'),
 ('9702_w20_13_q18',2,'Initial kinetic energy is $\\tfrac12(0.30)(8.0)^2=9.6\\ \\mathrm{J}$. GPE gain is $(0.30)(9.81)(1.9)=5.6\\ \\mathrm{J}$, leaving $4.0\\ \\mathrm{J}$ against drag. Option B gives the GPE gain alone.'),
 ('9702_w20_13_q16',2,'During an elastic bounce the ball momentarily stops, so its kinetic energy falls to zero and returns to its original value. Option C confuses conservation over the whole collision with constant kinetic energy at every instant.'),
 ('9702_w20_11_q15',2,'The trolley loses $50\\ \\mathrm{kJ}$ of GPE, starts with $5\\ \\mathrm{kJ}$ KE and transfers $10\\ \\mathrm{kJ}$ to friction: final KE $=50+5-10=45\\ \\mathrm{kJ}$. Option C omits friction.'),
 ('9702_w19_11_q15',4,'Input power is $120/0.60=200\\ \\mathrm{W}$ and waste is $200-120=80\\ \\mathrm{W}$. Option A multiplies output by efficiency to find input, reversing the ratio.'),
 ('9702_w24_13_q18',5,'Both journeys gain the same GPE because the height is unchanged. Running takes less time, so power is greater. Option A incorrectly changes the energy gain as well.'),
 ('9702_w21_13_q19',6,'Lifting power is $(0.50)(1000)(9.81)(30)/60=2.45\\ \\mathrm{kW}$. Divide by $0.70$ to find the engine output, $3.5\\ \\mathrm{kW}$. Option A omits the pump efficiency.'),
 ('9702_w21_12_q20',7,'At steady speed the driving force is $2400+1800\\sin30^\\circ=3300\\ \\mathrm{N}$, so $v=36\\,000/3300=11\\ \\mathrm{m\\,s^{-1}}$. Option C ignores the weight component down the hill.'),
 ('9702_s22_13_q18',7,'Engine power uses thrust: $(12\\,000)(24)=288\\ \\mathrm{kW}\\approx290\\ \\mathrm{kW}$. Option B uses the resultant force after subtracting drag, which gives net power instead.'),
 ('9702_w23_12_q15',7,'For the same distance, battery energy is work $Fs$; with $F\\propto v^2$, $E_{60}/E_{70}=(60/70)^2=0.73$. Option B uses only one factor of the speed ratio.'),
 ('9702_s19_12_q19',7,'Total mass is $80\\,000+200(70)=94\\,000\\ \\mathrm{kg}$. Useful climbing power is $mgv\\sin30^\\circ$; dividing by $0.40$ gives $6.9\\ \\mathrm{MW}$. Option B omits efficiency.'),
 ('9702_w25_12_q20',7,'The rise speed is $12/60=0.20\\ \\mathrm{m\\,s^{-1}}$. At steady speed the lift force is $mg$, so useful power is $(600)(9.81)(0.20)=1.2\\ \\mathrm{kW}$. Option C fails to convert minutes to seconds.'),
 ('9702_s23_12_q16',7,'Constant power gives $P=Fv$, so $F$ is inversely proportional to $v$; graph A.'),
 ('9702_s23_13_q15',2,'Official answer C. Here CAIE means the work done on the suitcase by the system, which equals the gain in its total energy (kinetic plus gravitational potential). The lift raises it 10 m at constant speed, so it gains mg x 10 m of potential energy. On the frictionless slide no energy is supplied: potential energy just becomes kinetic energy, so the total is unchanged. The horizontal belt at constant speed supplies none, and the sloping belt raises it by less than 8 m. Using net work = change in kinetic energy here would wrongly give D.'),
]
for n,(qid,k,explanation) in enumerate(past_specs,1):
    m=bank[qid]
    assert m['answer'] in m['options'] and K[k] in m['kcs']
    if qid == '9702_s23_12_q16':
        m['stem'] = 'A variable force is applied to ensure that a constant power is supplied to a train.\nWhich graph best shows the variation of the force F applied with the velocity v of the train?'
        m['options'] = {letter: '' for letter in 'ABCD'}
        explanation = None
    items.append({'id':f'{SUB}-p{n:02d}','kcs':[K[k]],'kind':'mcq','difficulty':3 if k<7 else 4,'command_word':'Determine','source':{'type':'past','ref':m['ref'],'qid':qid},'stem':m['stem'],'options':m['options'],'answer':m['answer'],'marks':1,'explanation':explanation,**({'image':m['image']} if m.get('image') else {})})

pack={'subtopic':SUB,'spec':'9702','version':1,'note':NOTE,'outline':'Work done is force times displacement in the force direction: $W=Fs\\cos\\theta$. Total energy is conserved when all stores and transfers, including thermal losses, are counted. Efficiency is useful output divided by total input, using energies or powers over the same interval. Power is work done per unit time, $P=W/t$; when a force acts along motion, $W=Fs$ and $v=s/t$ give $P=Fv$. Resolve forces along a slope and distinguish engine thrust from resultant force.','misconceptions':misconceptions,'worked':worked,'items':items,'flashcards':[{'id':'fc1','kc':K[5],'front':'Define power.','back':'Power is work done per unit time.'},{'id':'fc2','kc':K[5],'front':'Give the energy-transfer definition of power.','back':'Power is energy transferred per unit time.'},{'id':'fc3','kc':K[5],'front':'What is one watt?','back':'One watt is one joule per second.'}],'diagrams':[]}
OUT.parent.mkdir(parents=True,exist_ok=True)
OUT.write_text(json.dumps(pack,ensure_ascii=False,indent=1))
print(OUT,len(items),len(worked))
