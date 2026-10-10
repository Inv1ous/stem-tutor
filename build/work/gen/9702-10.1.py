import json, math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sub='9702-10.1'; kc=lambda n:f'{sub}.{n}'
P=ROOT/'build/out/packs/9702/9702-10.1.json'
note='Subjects/9702 Physics/10 D.C. circuits/10.1 Practical circuits.md'
mis=[
('m1',1,'A voltmeter belongs in series.','A voltmeter measures potential difference between two points, so connect it across the component.','An ammeter is connected in series.','research'),
('m2',2,'A wire crossing always makes a junction.','Only a marked junction joins branches; a crossing without a junction is not a connection.','Trace each continuous path between junctions.','research'),
('m3',3,'E.m.f. is the energy delivered only to the external resistor per charge.','E.m.f. is energy supplied per unit charge to the complete circuit, including internal resistance.','Terminal p.d. describes energy per charge available externally.','ER 9702 s21 P13 Q34'),
('m4',4,'E.m.f. and p.d. are both total energy.','Each is energy per unit charge: e.m.f. is energy supplied by the source; p.d. is energy transferred from electrical energy in a component.','Use J C^-1 for both.','ER 9702 w22 P22 Q6'),
('m5',5,'Terminal p.d. stays equal to e.m.f. as current rises.','The internal drop $Ir$ grows, so terminal p.d. $V=E-Ir$ falls.','At zero current the lost volts are zero.','ER 9702 w19 P12 Q35')]
mis=[dict(id=i,kc=kc(k),statement=s,refutation=r,contrast=c,source=src) for i,k,s,r,c,src in mis]
items=[]
def short(n,stem,point,keys,d=2):
 i=len([x for x in items if x['source']['type']=='generated'])+1
 items.append(dict(id=f'{sub}-i{i:02d}',kcs=[kc(n)],kind='short',difficulty=d,command_word=stem.split()[0],source={'type':'generated'},stem=stem,marks=1,rubric=[{'point':point,'keywords':keys}],explanation=point,hints=['Recall what the relevant symbol or quantity represents.','Apply the definition to this particular circuit.','Identify the component or energy transfer first.']))
for st,pt,kw in [
('Identify the standard symbol for a cell in words.','One long and one short parallel line represent a cell.',[['long'],['short']]),
('Identify the standard symbol for a battery in words.','A battery is represented by two or more pairs of long and short parallel lines.',[['two','more'],['long'],['short']]),
('Identify the standard symbol for a resistor in words.','A fixed resistor is a rectangle in a wire.',[['rectangle']]),
('Identify the standard symbol for a variable resistor in words.','A variable resistor is a resistor rectangle with a diagonal arrow across it.',[['rectangle'],['arrow']]),
('Identify the standard symbol for an ammeter in words.','An ammeter is a circle containing A.',[['circle'],['A']]),
('Identify the standard symbol for a voltmeter in words.','A voltmeter is a circle containing V.',[['circle'],['V']])]:short(1,st,pt,kw)
items[-1].update(command_word='Identify',stem='Identify the standard symbol for a voltmeter in words.')
for st,pt,kw in [
('Describe how to connect an ammeter to measure current through a lamp.','Connect the ammeter in series with the lamp.',[['series']]),
('Describe how to connect a voltmeter to measure p.d. across a lamp.','Connect the voltmeter in parallel across the lamp.',[['parallel','across']]),
('Explain what an open switch does to a simple series circuit.','It breaks the conducting loop, so there is no current.',[['breaks','open','incomplete'],['no current','zero current']]),
('Describe how to recognise two resistors in parallel on a circuit diagram.','Both ends of each resistor connect to the same two junctions.',[['same'],['two'],['junctions','nodes']]),
('Describe how to trace a branch at a junction.','Follow the continuous wires from the junction along each distinct path.',[['continuous'],['path','branch']]),
('Explain why a voltmeter across a source reads its terminal p.d.','Its leads connect to the two terminals, measuring energy transferred per unit charge between them.',[['terminals'],['unit charge']])]:short(2,st,pt,kw,4 if st.startswith('Explain') else 2)
items[6].update(id='9702-10.1-i07',command_word='Sketch',stem='Using the standard circuit symbols in section 6 of the syllabus, draw a circuit containing one cell, a closed switch and a lamp in a complete series loop. Include an ammeter to measure the current through the lamp and a voltmeter to measure the potential difference across the lamp.',marks=3,rubric=[{'point':'Draw one cell, a closed switch and a lamp with correct standard symbols connected in a complete series loop.','keywords':[['cell'],['switch'],['lamp']]},{'point':'Draw an ammeter as a circle containing A, connected in series with the lamp.','keywords':[['ammeter'],['series']]},{'point':'Draw a voltmeter as a circle containing V, connected in parallel across the lamp.','keywords':[['voltmeter'],['parallel','across']]}],explanation='The diagram must show a complete cell-switch-lamp loop, with a circle containing A in series and a circle containing V across the lamp. Use one long and one short parallel line for the cell, a closed-switch symbol, and a circle containing a cross for the lamp. Assess the drawn symbols and connections against the rubric.',hints=['Start by drawing a complete loop containing the cell, closed switch and lamp.','Put the ammeter on the same current path as the lamp.','Connect the voltmeter to the two ends of the lamp.'])
for st,pt,kw in [
('Define the e.m.f. of a source.','Energy transferred per unit charge by the source in driving charge around a complete circuit.',[['energy'],['per unit charge'],['complete circuit']]),
('State the SI unit of e.m.f.','The unit is the volt, equal to one joule per coulomb.',[['volt','J C']]),
('Calculate the energy supplied by a source of e.m.f. $E$ to charge $Q$.','The supplied energy is $W=EQ$.',[['EQ','E Q']]),
('Explain what a 9.0 V label on a battery means.','The source supplies 9.0 J per coulomb to the complete circuit.',[['9.0 J'],['coulomb'],['complete circuit']]),
('State whether source e.m.f. includes energy dissipated internally.','Yes; it counts energy supplied per charge to the entire circuit, including internal resistance.',[['entire','complete'],['internal']]),
('Describe the energy transfer represented by e.m.f. in a chemical cell.','Chemical energy is transferred to electrical energy per unit charge.',[['chemical'],['electrical'],['per unit charge']])]:short(3,st,pt,kw,4 if st.startswith('Explain') else 2)
for st,pt,kw in [
('Compare the meanings of e.m.f. and p.d.','E.m.f. is energy supplied per unit charge by a source; p.d. is energy transferred per unit charge from electrical energy in a component.',[['supplied'],['transferred'],['unit charge']]),
('Explain why a resistor has a p.d. across it.','Electrical energy is transferred to thermal energy in the resistor per unit charge.',[['electrical'],['thermal'],['per unit charge']]),
('State when terminal p.d. equals source e.m.f.','They are equal when no current flows, so no energy per charge is dissipated internally.',[['no current','zero current'],['internal']]),
('Explain why e.m.f. can exceed terminal p.d.','Some energy per unit charge is dissipated in the source internal resistance.',[['energy'],['per unit charge'],['internal resistance']]),
('Compare the units of e.m.f. and p.d.','Both have units of volts or joules per coulomb.',[['volt','joules per coulomb']]),
('Describe the energy destination for charge passing through a lamp.','Electrical energy is transferred to light and thermal energy per unit charge across the lamp.',[['light'],['thermal'],['per unit charge']])]:short(4,st,pt,kw,4 if st.startswith(('Compare','Explain')) else 2)
for st,pt,kw in [
('State the relationship between e.m.f. $E$, terminal p.d. $V$, current $I$ and internal resistance $r$.','$V=E-Ir$.',[['E-Ir']]),
('Explain why terminal p.d. falls when current increases.','The internal p.d. $Ir$ increases, leaving less p.d. across the external circuit.',[['Ir'],['increases'],['external']]),
('Predict the terminal p.d. when a source supplies no current.','Terminal p.d. equals e.m.f. because $Ir=0$.',[['equals'],['e.m.f.','emf']]),
('Explain why increasing external resistance can raise terminal p.d.','Current falls, so the internal p.d. $Ir$ falls and $V=E-Ir$ rises.',[['current falls','current decreases'],['Ir'],['rises','increases']]),
('Describe what is meant by lost volts.','Lost volts is the p.d. $Ir$ across the source internal resistance.',[['Ir'],['internal resistance']]),
('Compare source e.m.f. and terminal p.d. when it supplies current.','Terminal p.d. is less than e.m.f. by $Ir$, the internal p.d.',[['less'],['Ir']])]:short(5,st,pt,kw,4 if st.startswith(('Compare','Explain')) else 2)
# Numerics are computed here; the JSON contains no hand-entered answer values.
def numeric(n,stem,value,unit,explanation):
 i=len([x for x in items if x['source']['type']=='generated'])+1
 items.append(dict(id=f'{sub}-i{i:02d}',kcs=[kc(n)],kind='numeric',difficulty=3,command_word='Calculate',source={'type':'generated'},stem=stem,marks=2,answer={'value':round(value,6),'unit':unit,'sf_ok':[2,3]},explanation=explanation,hints=['Write the energy or circuit equation.','Substitute the stated quantities with consistent units.','Rearrange before rounding the result.']))
numeric(3,'Calculate energy supplied when a 6.0 V source drives 4.0 C around a complete circuit.',6.0*4.0,'J','$W=EQ=6.0\times4.0=24$ J.')
numeric(5,'Calculate terminal p.d. for $E=12.0$ V, $I=2.0$ A and $r=0.50$ $\\Omega$.',12.0-2.0*0.50,'V','$V=E-Ir=12.0-(2.0)(0.50)=11.0$ V.')
# Original bank records retain their wording, options and official letter.
bank={x['id']:x for x in json.loads((ROOT/'build/work/mcq/9702.tagged.json').read_text())}
past_ids=['9702_w21_11_q36','9702_s19_13_q34','9702_s21_13_q34','9702_w22_11_q35','9702_w25_12_q34','9702_w21_12_q36','9702_w19_12_q35','9702_w21_12_q34','9702_s23_13_q34','9702_s23_11_q35','9702_w23_11_q36','9702_w24_11_q35']
expl={
'9702_w21_11_q36':'The image option C is the standard oscilloscope symbol. The other image symbols show different instruments or components.',
'9702_s19_13_q34':'Both supply points must connect to Z to complete each circuit. Option B leaves Z in one circuit unconnected.',
'9702_s21_13_q34':'E.m.f. gives energy per coulomb supplied to the whole circuit. Option B ignores energy dissipated inside the battery.',
'9702_w22_11_q35':'E.m.f. has units J C^-1, energy per charge. Option D is power in watts.',
'9702_w25_12_q34':'The source supplies $EQ$ to the cell and external circuit together. Option A omits energy dissipated within the cell.',
'9702_w21_12_q36':'Both quantities must be energy per unit charge: supply in the cell and transfer in the resistor. Option A omits per unit charge.',
'9702_w19_12_q35':'As current grows, lost volts $Ir$ grow, so terminal p.d. falls. Option D would reduce rather than increase current.',
'9702_w21_12_q34':'Higher load resistance lowers current and lost volts, so load p.d. rises. Option C is wrong because internal power $I^2r$ falls.',
'9702_s23_13_q34':'Closing the switch adds a parallel path, raising total current and lost volts, so terminal p.d. falls. Option C overlooks internal resistance.',
'9702_s23_11_q35':'Increasing $r$ lowers $I=E/(R+r)$ and therefore load p.d. $IR$. Option B overlooks the falling load p.d.',
'9702_w23_11_q36':'Energy per charge is split between $Ir$ inside and $IR$ outside: $E-Ir=IR$. Option D omits internal loss.',
'9702_w24_11_q35':'E.m.f. remains the same, but internal resistance reduces current and p.d. across X. Option D reverses the p.d. change.'}
for j,q in enumerate(past_ids,1):
 m=bank[q]; local=[k for k in m['kcs'] if k.startswith(sub+'.')]
 items.append(dict(id=f'{sub}-p{j:02d}',kcs=local[:2],kind='mcq',difficulty=3,command_word='Identify',source={'type':'past','ref':m['ref'],'qid':q},stem=m['stem'],options=m['options'],answer=m['answer'],image=m.get('image'),marks=1,explanation=expl[q],hints=[]))
def worked(n,problem,steps,fproblem,fvalue,unit):
 return dict(id=f'we{n}',kc=kc(n),problem=problem,steps=[{'do':a,'why':b,**({'check':{'kind':'numeric','answer':{'value':round(v,6),'unit':unit,'sf_ok':[2,3]}}} if v is not None else {})} for a,b,v in steps],faded={'id':f'we{n}f','problem':fproblem,'answer':{'value':round(fvalue,6),'unit':unit,'sf_ok':[2,3]},'blank_from':1})
worked_examples=[
worked(2,'A lamp circuit needs current through the lamp measured. Where should the ammeter go?',[('Place the ammeter in series with the lamp.','The same charge per second must pass through both.',None)],'A resistor circuit needs its current measured. Place the ammeter in series and state the reading if 2.0 C crosses it in 4.0 s.',2.0/4.0,'A'),
worked(3,'A 9.0 V source drives 3.0 C around a complete circuit. Calculate energy supplied.',[('$E=W/Q$, so $W=EQ$.','E.m.f. is energy supplied per unit charge.',None),('$W=(9.0)(3.0)=27$ J.','Charge is in coulombs and e.m.f. in joules per coulomb.',9.0*3.0)],'A 6.0 V source drives 5.0 C around a complete circuit. Calculate energy supplied.',6.0*5.0,'J')]
pack=dict(subtopic=sub,spec='9702',version=1,note=note,outline='Use standard symbols to draw complete conducting loops. Put an ammeter in series and a voltmeter across a component. Source e.m.f. $E=W/Q$ is energy supplied per unit charge around the complete circuit. P.d. is energy transferred from electrical energy per unit charge across a component. With internal resistance $r$, terminal p.d. is $V=E-Ir$; increasing current increases lost volts.',misconceptions=mis,worked=worked_examples,items=items,flashcards=[dict(id=f'fc{n}',kc=kc(n),front=q,back=a) for n,q,a in [(1,'What represents a cell?','One long and one short parallel line.'),(1,'What represents a resistor?','A rectangle in the conducting path.'),(3,'Define e.m.f.','Energy transferred per unit charge by a source in driving charge around a complete circuit.')]],diagrams=[])
P.parent.mkdir(parents=True,exist_ok=True);P.write_text(json.dumps(pack,ensure_ascii=False,indent=1))
print(P,len(items))
