import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SUB = '9702-9.3'
ids = [f'{SUB}.{n}' for n in range(1, 9)]
note = 'Subjects/9702 Physics/09 Electricity/9.3 Resistance and resistivity.md'
mis = [
 ('m1', 1, 'Resistance is the same as potential difference.', 'Resistance is the ratio of potential difference to current, not the potential difference alone.', 'Use $R=V/I$.'),
 ('m2', 5, "$V=IR$ alone states Ohm’s law without a condition.", 'Ohm’s law requires constant temperature.', 'State proportionality and constant temperature.'),
 ('m3', 3, 'The gradient of an $I$–$V$ graph is resistance.', 'At a point resistance is $V/I$; the gradient of an $I$–$V$ graph is not generally resistance.', 'Use the ratio at the chosen point.'),
 ('m4', 4, 'A hotter filament has lower resistance.', 'Heating a metal filament increases its resistance.', 'As current and temperature rise, resistance rises.'),
 ('m5', 6, 'Doubling the diameter doubles the cross-sectional area.', 'Area depends on the square of diameter.', 'Use $A=\u03c0d^2/4$.'),
 ('m6', 7, 'An LDR has higher resistance in brighter light.', 'Its resistance decreases as light intensity increases.', 'More light means less resistance.'),
 ('m7', 8, 'A negative temperature coefficient thermistor has higher resistance when hot.', 'Its resistance decreases as temperature increases.', 'Hotter means less resistance.'),
]
pack = dict(subtopic=SUB, spec='9702', version=1, note=note,
 outline='Resistance is $R=V/I$ and $V=IR$. Ohm’s law applies when current is proportional to potential difference at constant temperature. A metallic conductor then has a straight-line $I$–$V$ graph through the origin. A filament lamp curves as it heats; a diode conducts mainly in one direction after a threshold. Resistivity connects material and dimensions through $R=\\rho L/A$. An LDR loses resistance in brighter light, and an assumed negative temperature coefficient thermistor loses resistance as temperature rises.',
 misconceptions=[dict(id=a,kc=ids[n-1],statement=b,refutation=c,contrast=d,source='ER 9702 w23 P23 Q7' if n==5 else 'research') for a,n,b,c,d in mis],
 worked=[],items=[],flashcards=[],diagrams=[])

def ans(v,u): return dict(value=round(v,10),unit=u,sf_ok=[2,3])
def item(k,stem,point,keywords,word='Explain',difficulty=2):
 n=len(pack['items'])+1
 pack['items'].append(dict(id=f'{SUB}-i{n:02d}',kcs=[ids[k-1]],kind='short',difficulty=difficulty,command_word=word,source={'type':'generated'},stem=stem,marks=1,rubric=[{'point':point,'keywords':keywords}],explanation=point,hints=['Recall the relevant physical quantity or behaviour.','Identify the variables that must be compared.','Start with the defining equation or trend.']))

def num(k,stem,params,expr,unit,explanation,ds=[]):
 n=len(pack['items'])+1
 vals={x:v['choices'][0] for x,v in params.items()}
 val=eval(expr,{'__builtins__':{}},vals)
 pack['items'].append(dict(id=f'{SUB}-i{n:02d}',kcs=[ids[k-1]],kind='numeric',difficulty=3,command_word='Calculate',source={'type':'generated'},stem=stem,marks=2,answer=ans(val,unit),template={'params':params,'derived':{},'answer':expr,'distractors':ds,'constraints':[]},explanation=explanation,hints=['Identify the quantities and units.','Rearrange the relevant equation.','Substitute the given values before rounding.']))

def worked(k,problem,steps,fade,unit):
 n=len(pack['worked'])+1
 pack['worked'].append(dict(id=f'we{n}',kc=ids[k-1],problem=problem,steps=[{'do':d,'why':w} for d,w in steps],faded={'id':f'we{n}f','problem':fade[0],'answer':ans(fade[1],unit),'blank_from':1}))

item(1,'Define resistance of a component.','Resistance is the ratio of potential difference across it to current through it.',[['ratio'],['potential difference'],['current']],'Define')
for q,p,kw in [
 ('State the equation defining resistance.','$R=V/I$.',[['R'],['V/I']]),
 ('Give the SI unit of resistance.','The ohm, $\Omega$.',[['ohm','Ω']]),
 ('Explain the meaning of a resistance of $1\,\Omega$.','A p.d. of $1\,\mathrm{V}$ causes a current of $1\,\mathrm{A}$.',[['1'],['V'],['A']]),
 ('Compare resistance and potential difference.','Resistance is p.d. divided by current; p.d. alone is not resistance.',[['divided','ratio'],['current']]),
 ('Determine whether two components at the same p.d. have the same resistance if their currents differ.','They have different resistances because $R=V/I$.',[['different'],['V/I']])]: item(1,q,p,kw)

num(2,'Calculate the resistance when the p.d. is [[V]] V and the current is [[I]] A.',{'V':{'choices':[6,9,12]},'I':{'choices':[0.2,0.3,0.4]}},'V/I','ohm','Divide p.d. by current: $R=V/I$.',[{'expr':'V*I','misconception':'m1'}])
for q,p,kw in [
 ('State the equation relating p.d., current and resistance.','$V=IR$.',[['V=IR']]),
 ('Explain how to find current from known p.d. and resistance.','Rearrange $V=IR$ to $I=V/R$.',[['V/R']]),
 ('Explain how to find p.d. from current and resistance.','Multiply current by resistance: $V=IR$.',[['IR']]),
 ('Predict the current when p.d. doubles across a fixed resistance.','Current doubles because $I=V/R$.',[['doubles'],['V/R']])]: item(2,q,p,kw)
worked(2,'A resistor has $V=12.0\,\mathrm{V}$ and $I=0.40\,\mathrm{A}$. Calculate $R$.',[('State $R=V/I$.','This rearranges $V=IR$.'),('Substitute: $R=12.0/0.40=30\,\Omega$.','Use the p.d. across and current through the same component.')],('A resistor has $V=15.0\,\mathrm{V}$ and $I=0.50\,\mathrm{A}$. Calculate $R$.',15/0.5),'ohm')

for q,p,kw in [
 ('Sketch the $I$–$V$ characteristic of a metallic conductor at constant temperature in words.','A straight line through the origin, with constant gradient.',[['straight'],['origin']]),
 ('Describe the $I$–$V$ characteristic of a filament lamp.','It passes through the origin and becomes less steep as $|V|$ rises.',[['origin'],['less steep','decreasing gradient']]),
 ('Describe the $I$–$V$ characteristic of a semiconductor diode.','Almost no reverse current; forward current rises sharply after a threshold p.d.',[['reverse'],['threshold']]),
 ('Compare the metallic conductor and filament lamp $I$–$V$ graphs.','Both pass through the origin; the conductor is straight, while the lamp curves.',[['origin'],['straight'],['curves']]),
 ('Explain why the gradient of a curved $I$–$V$ graph is not the resistance.','Resistance at a point is $V/I$, not $\Delta I/\Delta V$.',[['V/I'],['gradient','ΔI']]),
 ('Sketch in words the negative-p.d. region of a diode $I$–$V$ graph.','Current is approximately zero under reverse bias.',[['zero'],['reverse']])]: item(3,q,p,kw,'Sketch' if q.startswith('Sketch') else 'Describe',4 if q.startswith('Compare') else 2)
worked(3,'Sketch three $I$–$V$ curves with $V$ horizontal. Describe their shapes.', [('Metallic conductor: draw a straight line through the origin.','Constant temperature gives constant resistance.'),('Lamp: draw a symmetric curve that flattens as $|V|$ rises.','The filament heats as current rises.'),('Diode: show negligible reverse current and a sharp forward rise after a threshold.','A diode conducts mainly in one direction.')],('An $I$–$V$ graph has $V=2.0\\,\mathrm{V}$ at $I=0.40\\,\mathrm{A}$. Calculate the resistance at this point.',2/0.4),'ohm')

for q,p,kw in [
 ('Explain why filament lamp resistance increases when current increases.','Larger current heats the filament; higher temperature raises its resistance.',[['heats','temperature'],['resistance']]),
 ('Predict how $R=V/I$ changes as a lamp brightens.','Resistance increases as the filament heats.',[['increases'],['heats','temperature']]),
 ('Explain why the lamp $I$–$V$ graph becomes less steep at larger currents.','Its temperature and resistance rise, so each increase in p.d. produces a smaller current increase.',[['temperature'],['resistance'],['smaller']]),
 ('Compare a cold and hot filament at the same test current.','The hot filament has higher resistance.',[['hot'],['higher']]),
 ('Explain why a filament lamp does not obey Ohm’s law during heating.','Its temperature and resistance change, so current is not proportional to p.d.',[['temperature'],['not proportional']]),
 ('Predict the resistance when a switched-on filament warms.','It rises as its temperature rises.',[['rises','increases'],['temperature']])]: item(4,q,p,kw,difficulty=4 if 'law' in q else 2)

for q,p,kw in [
 ('State Ohm’s law.','Current through a conductor is directly proportional to potential difference across it, provided temperature remains constant.',[['current'],['directly proportional'],['potential difference'],['temperature'],['constant']]),
 ('Explain why $V=IR$ alone does not fully state Ohm’s law.','The law also requires current proportional to p.d. at constant temperature.',[['proportional'],['constant temperature']]),
 ('Describe the $I$–$V$ graph of an ohmic conductor at constant temperature.','It is a straight line through the origin.',[['straight'],['origin']]),
 ('Explain what stays constant for an ohmic conductor at constant temperature.','The ratio $V/I$, hence its resistance, stays constant.',[['V/I','ratio'],['constant']]),
 ('Determine whether a curved $I$–$V$ graph shows Ohm’s law.','No: current is not proportional to p.d.',[['not proportional']]),
 ('State the condition needed when testing Ohm’s law.','Keep the conductor at constant temperature.',[['constant'],['temperature']])]: item(5,q,p,kw,'State' if q.startswith('State') else 'Explain',4 if 'curved' in q else 2)

num(6,'A wire has $\\rho=[[rho]]\,\Omega\,\mathrm{m}$, length [[L]] m and area [[A]] $\mathrm{m^2}$. Calculate its resistance.',{'rho':{'choices':[0.002,0.003]},'L':{'choices':[2,3,4]},'A':{'choices':[0.0001,0.0002]}},'rho*L/A','ohm','Apply $R=\\rho L/A$ with SI dimensions.',[{'expr':'rho*A/L','misconception':'m5'}])
for q,p,kw in [
 ('State the resistivity equation for a uniform wire.','$R=\\rho L/A$.',[['R'],['rho','ρ'],['L'],['A']]),
 ('Give the SI unit of resistivity.','$\Omega\,\mathrm{m}$.',[['Ω'],['m']]),
 ('Predict the resistance if a wire of the same material and area doubles in length.','Resistance doubles because $R\propto L$.',[['doubles'],['length']]),
 ('Predict the resistance if cross-sectional area doubles with material and length fixed.','Resistance halves because $R\propto 1/A$.',[['halves'],['area']]),
 ('Explain why doubling a wire diameter quarters its resistance when length is fixed.','Area quadruples because $A\propto d^2$, so $R$ becomes a quarter.',[['area'],['quadruples'],['quarter']])]: item(6,q,p,kw,difficulty=4 if 'diameter' in q else 2)
worked(6,'A wire has $\\rho=2.0\\times10^{-8}\,\Omega\,\mathrm{m}$, $L=4.0\,\mathrm{m}$ and $A=2.0\\times10^{-6}\,\mathrm{m^2}$. Calculate $R$.',[('State $R=\\rho L/A$.','Resistance depends on material, length and area.'),('Substitute: $R=(2.0\\times10^{-8})(4.0)/(2.0\\times10^{-6})=0.040\,\Omega$.','Keep area in square metres.')],('Calculate $R$ for $\\rho=3.0\\times10^{-8}\,\Omega\,\mathrm{m}$, $L=2.0\,\mathrm{m}$ and $A=1.0\\times10^{-6}\,\mathrm{m^2}$.',3e-8*2/1e-6),'ohm')

for k,name,stim,change,other,misid in [(7,'LDR','light intensity','decreases','increases','m6'),(8,'negative temperature coefficient thermistor','temperature','decreases','increases','m7')]:
 for q,p,kw,word,diff in [
  (f'State how the resistance of an {name} changes as {stim} increases.',f'Resistance {change}.',[[change]],'State',1),
  (f'Predict the resistance of an {name} when {stim} rises.',f'It {change}.',[[change]],'Predict',2),
  (f'Compare the resistance of an {name} at higher and lower {stim}.',f'Resistance is lower at higher {stim}.',[['lower'],['higher']], 'Compare',2),
  (f'Explain why an answer saying resistance {other} with rising {stim} is wrong for this component.',f'The specified component has resistance that {change} as {stim} increases.',[[change],[stim.split()[0]]],'Explain',3),
  (f'Describe the trend on a resistance against {stim} graph for an {name}.',f'The graph slopes down as {stim} increases.',[['down'],['increases']],'Describe',3),
  (f'Predict the resistance change if {stim} falls for an {name}.',f'Resistance increases.',[['increases']],'Predict',4)]: item(k,q,p,kw,word,diff)

for k,front,back in [(1,'Define resistance.','The ratio of the potential difference across a component to the current through it.'),(5,"State Ohm’s law.",'The current through a conductor is directly proportional to the potential difference across it, provided its temperature remains constant.')]:
 pack['flashcards'].append(dict(id=f'fc{k}',kc=ids[k-1],front=front,back=back))

bank={x['id']:x for x in json.loads((ROOT/'build/work/mcq/9702.tagged.json').read_text())}
past_ids=['9702_w23_13_q32','9702_w22_12_q33','9702_w23_12_q32','9702_w22_12_q34','9702_s22_11_q34','9702_w23_11_q33','9702_w23_13_q33','9702_w23_12_q33','9702_w20_12_q35','9702_s22_11_q33','9702_w23_11_q32','9702_w22_13_q32']
for n,qid in enumerate(past_ids,1):
 q=bank[qid]
 explanation={
 '9702_w23_13_q32':'A larger current heats the filament, increasing its temperature and resistance. A falling p.d. is not the cause.',
 '9702_w22_12_q33':'The filament heats as p.d. and current rise, so resistance increases. It does not decrease on heating.',
 '9702_w23_12_q32':'At fixed p.d., $I=VA/(\\rho L)$ and $A=\pi d^2/4$, so $I\propto d^2/L$. Diameter must be squared.',
 '9702_w22_12_q34':'At constant volume, $L\propto1/A$ and $R\propto1/A^2\propto1/d^4$. Hence $R_{new}/R=1/0.94^4=1.28$, not 1.13.',
 '9702_s22_11_q34':'Same mass and material imply equal volume. Tripling length reduces area to a third and makes resistance nine times larger, not three times.',
 '9702_w23_11_q33':'$\\rho=RA/L=20\pi(0.010)^2/0.060=0.10\,\Omega\,\mathrm{m}$. Use radius, not diameter, in area.',
 '9702_w23_13_q33':'Initially $R_T=12/0.10-40=80\,\Omega$; later $R_T=12/0.12-40=60\,\Omega$. Its temperature therefore increases, since this thermistor has a negative temperature coefficient.',
 '9702_w23_12_q33':'Increasing temperature lowers thermistor resistance; increasing light lowers LDR resistance. In the shown circuit both lower the measured p.d.; decreasing either input does not.',
 '9702_w20_12_q35':'Series current is $0.30\,\mathrm{A}$. The lamp graph gives $4.2\,\mathrm{V}$, so $R=4.2/0.30=14\,\Omega$. The resistor’s p.d. is not the lamp p.d.',
 '9702_s22_11_q33':'Use $R=V/I$ at each point of the diode graph. The steep forward section does not make current proportional to p.d. over the whole region.',
 '9702_w23_11_q32':'As p.d. rises, current heats the filament and its resistance increases from a nonzero cold value. A flat or falling resistance curve is wrong.',
 '9702_w22_13_q32':'The curve bends as a filament heats. A fixed metallic conductor would give a straight line; a diode would show strongly one-way conduction.'}
 for_p=[]
for n,qid in enumerate(past_ids,1):
 q=bank[qid]
 pack['items'].append(dict(id=f'{SUB}-p{n:02d}',kcs=[x for x in q['kcs'] if x in ids][:2],kind='mcq',difficulty=3,command_word=None,source={'type':'past','ref':q['ref'],'qid':qid},stem=q['stem'],options=q['options'],answer=q['answer'],image=q.get('image'),marks=1,explanation=explanation[qid],hints=['Identify the relevant property.','Use the graph or equation carefully.','Check the physical trend before choosing.']))

out=ROOT/'build/out/packs/9702/9702-9.3.json'
out.parent.mkdir(parents=True,exist_ok=True)
for it in pack['items']:
 if it.get('template'):
  tpl=it['template']
  for choice in (0,1):
   vals={name: spec['choices'][choice % len(spec['choices'])] for name,spec in tpl['params'].items()}
   value=eval(tpl['answer'],{'__builtins__':{}},vals)
   assert value > 0
   for d in tpl['distractors']:
    dv=eval(d['expr'],{'__builtins__':{}},vals)
    assert abs(dv-value)>0.02*abs(value)
out.write_text(json.dumps(pack,ensure_ascii=False,indent=1))
