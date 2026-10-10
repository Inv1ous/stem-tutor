import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SUB = '9702-10.3'
K = lambda n: f'{SUB}.{n}'
OUT = ROOT / 'build/out/packs/9702/9702-10.3.json'
NOTE = 'Subjects/9702 Physics/10 D.C. circuits/10.3 Potential dividers.md'

misdata = [
 (1,'The larger resistor always has the smaller p.d.','In series the same current passes through both; $V=IR$ makes p.d. proportional to resistance.','Find which resistor the output spans.','ER 9702 s23 P21 Q7'),
 (2,'The unknown cell must have zero internal resistance.','At balance no current flows through the unknown cell, so its internal p.d. is zero even if its resistance is non-zero.','A null measurement compares e.m.f. with wire p.d.','ER 9702 w23 P13 Q37'),
 (3,'A null galvanometer needs an amperes calibration.','Only zero deflection is required to find balance; its current scale is irrelevant.','Zero indicates equal opposing potential differences.','ER 9702 w23 P12 Q37'),
 (4,'Cooling an NTC thermistor reduces its resistance.','An NTC thermistor has higher resistance when cooler; an LDR has higher resistance in dimmer light.','Determine which divider component the voltmeter spans.','ER 9702 s23 P12 Q33'),
]
mis=[dict(id=f'm{i}',kc=K(i),statement=a,refutation=b,contrast=c,source=d) for i,a,b,c,d in misdata]
items=[]
def short(k,word,question,answer,keys,difficulty=2):
 n=len([i for i in items if i['source']['type']=='generated'])+1
 hints=['Identify the relevant component and output terminals.','Use the series or balance principle.','Think about what the galvanometer detects and how balance affects its deflection.' if n==13 else 'State how the potential difference follows from resistance or zero current.']
 items.append(dict(id=f'{SUB}-i{n:02d}',kcs=[K(k)],kind='short',difficulty=difficulty,command_word=word,source={'type':'generated'},stem=f'{word} {question}',marks=1,rubric=[{'point':answer,'keywords':keys}],explanation=answer,hints=hints))

for row in [
 (1,'Describe','the principle of a potential divider circuit.','Series components share the supply p.d. in proportion to their resistances.',[['series'],['proportion'],['resistance']]),
 (1,'State','the p.d. across $R_2$ in a two-resistor divider supplied by $V_{in}$.','$V_{out}=V_{in}R_2/(R_1+R_2)$.',[['R_2'],['R_1+R_2']]),
 (1,'Explain','why a larger series resistance has a larger p.d.','The same current flows through both resistors and $V=IR$.',[['same current'],['V=IR']]),
 (1,'Predict','the output across the lower resistor when its resistance increases at fixed supply p.d.','The output p.d. increases because its share of total resistance increases.',[['increases'],['share','fraction']]),
 (1,'Compare','the p.d.s across two equal series resistors.','Their potential differences are equal: each is half the supply p.d.',[['equal'],['half']]),
 (1,'Explain','why a loaded divider may have a different output from the unloaded prediction.','The load is parallel to an arm, changing its effective resistance and hence the voltage ratio.',[['parallel'],['effective resistance'],['ratio']]),
 (2,'Describe','how a uniform potentiometer wire compares two potential differences.','Find each zero-current balance length on the same wire; the p.d. ratio equals the balance-length ratio.',[['balance'],['length'],['ratio']]),
 (2,'State','the relation between p.d. and length along a uniform wire carrying steady current.','Potential difference is proportional to wire length.',[['proportional'],['length']]),
 (2,'Explain','why a potentiometer wire must have uniform resistance per unit length.','Then equal lengths have equal resistance and equal p.d. for steady current.',[['equal lengths'],['equal','same'],['p.d.']]),
 (2,'Describe','how to measure the e.m.f. of an unknown cell using a potentiometer.','Connect it against the wire p.d.; move the contact until the galvanometer reads zero, then use the balance length and potential gradient.',[['zero'],['length'],['gradient']]),
 (2,'Compare','two cell e.m.f.s with balance lengths $l_1$ and $l_2$ on the same wire.','$E_1/E_2=l_1/l_2$ when the wire potential gradient is unchanged.',[['E_1/E_2'],['l_1/l_2']]),
 (2,'Explain','why the driver supply must provide a wire p.d. at least as large as the unknown e.m.f.','A balance point exists only if the matching wire p.d. lies within its available range.',[['balance'],['range']]),
 (3,'State','the galvanometer reading at the balance point.','Zero deflection: no current flows through the galvanometer.',[['zero'],['current']]),
 (3,'Explain','what zero galvanometer deflection shows in a potentiometer.','The compared p.d.s are equal and opposed, so no current flows in the comparison branch.',[['equal'],['opposed'],['no current']]),
 (3,'Explain','why an unknown cell internal resistance does not alter its measured e.m.f. at balance.','No current passes through the cell, so there is no internal p.d. drop.',[['no current'],['internal'],['drop','p.d.']]),
 (3,'State','whether a null galvanometer requires an ampere-calibrated scale.','No; it need only identify zero deflection.',[['no'],['zero']]),
 (3,'Describe','the purpose of a sensitive galvanometer in a null method.','It detects small departures from zero current as the contact approaches balance.',[['zero'],['balance']]),
 (3,'Explain','why a non-zero galvanometer reading does not establish the unknown e.m.f.','A non-zero reading means the opposing p.d.s have not balanced.',[['not','unequal'],['balance']]),
 (4,'State','how an NTC thermistor resistance changes as temperature rises.','Its resistance decreases as temperature rises.',[['decreases'],['temperature']]),
 (4,'State','how LDR resistance changes as light intensity rises.','Its resistance decreases as light intensity rises.',[['decreases'],['light']]),
 (4,'Explain','how a thermistor divider can produce a temperature-dependent p.d.','Temperature changes thermistor resistance, changing its share of the supply p.d.',[['temperature'],['resistance'],['p.d.']]),
 (4,'Explain','how an LDR divider can produce a light-dependent p.d.','Light intensity changes LDR resistance, changing its share of the supply p.d.',[['light'],['resistance'],['p.d.']]),
 (4,'Predict','the p.d. across an NTC thermistor in series with a fixed resistor when temperature increases.','It decreases because thermistor resistance and its voltage fraction decrease.',[['decreases'],['resistance']]),
 (4,'Predict','the p.d. across a fixed resistor in series with an LDR when light intensity increases.','It increases because LDR resistance falls and the fixed resistor takes a larger voltage fraction.',[['increases'],['LDR'],['falls','decreases']]),
]: short(*row,difficulty=4 if row[1] in ('Explain','Compare') else 2)

def numeric(k,stem,value,unit,explanation,difficulty=3):
 n=len([i for i in items if i['source']['type']=='generated'])+1
 items.append(dict(id=f'{SUB}-i{n:02d}',kcs=[K(k)],kind='numeric',difficulty=difficulty,command_word='Calculate',source={'type':'generated'},stem='Calculate '+stem,marks=2,answer={'value':round(value,8),'unit':unit,'sf_ok':[2,3]},explanation=explanation,hints=['Identify the output section and total section.','Write the potential-divider or balance-length ratio.','Substitute the resistance or length values before rounding.']))
numeric(1,'the p.d. across a $3.0\,\Omega$ resistor in series with a $6.0\,\Omega$ resistor across $12$ V.',12*3/(3+6),'V','$V=12(3.0)/(3.0+6.0)=4.0$ V.')
numeric(2,'the unknown e.m.f. if $1.50$ V balances at $60.0$ cm and the unknown balances at $40.0$ cm on the same wire.',1.5*40/60,'V','$E_x/E_0=l_x/l_0$, so $E_x=1.50(40.0/60.0)=1.00$ V.')
numeric(4,'the p.d. across a $10$ k$\Omega$ fixed resistor in series with a $15$ k$\Omega$ thermistor across $6.0$ V.',6*10/(10+15),'V','$V=6.0(10)/(10+15)=2.4$ V.')

bank={q['id']:q for q in json.loads((ROOT/'build/work/mcq/9702.tagged.json').read_text())}
past_ids=['9702_w23_13_q37','9702_w23_12_q37','9702_w22_13_q37','9702_w21_12_q38','9702_w20_13_q38','9702_w19_12_q37','9702_s23_13_q37','9702_s23_12_q37','9702_s21_13_q38','9702_s21_11_q38','9702_w25_12_q35','9702_w23_11_q37']
explanations=[
 'Uniform resistance per unit length makes p.d. proportional to balance length. C is wrong: the unknown cell carries no current at null, whatever its internal resistance.',
 'At the 1.5 V balance point only zero deflection matters, so no amperes calibration is needed. A is wrong: a non-zero reading means the p.d.s are unequal.',
 'A large series resistance lowers the wire potential gradient, spreading an 8 mV balance over a measurable length. Resistors in the unknown-cell branch do not change the gradient.',
 'The maximum wire p.d. is $9.0(3.0)/(1.0+5.0+3.0)=3.0$ V. The 3.4 V choice omits a series resistance.',
 'At null, 40.0 cm has 5.00 mV; the whole wire has 12.5 mV and current 2.50 mA. Thus $R=(2.000-0.0125)/0.00250=795$ $\\Omega$. The 805 $\\Omega$ choice fails to subtract the wire p.d.',
 'At null, the p.d. across $R+2.0$ $\\Omega$ is 2.0 V: $6.0(R+2.0)/(R+12)=2.0$, giving $R=3.0$ $\\Omega$. Using only the variable resistor as the output arm gives a wrong choice.',
 'At null, $0.50/2.0=QP/QR=1/4$. The longer fractions C and D reverse or misapply the wire ratio.',
 'Covering the LDR raises its resistance, so balance requires more wire to the right; move the contact left. D moves it in the opposite direction.',
 'The slider divides 120 $\\Omega$ into 30 $\\Omega$ below and 90 $\\Omega$ above. At null $R/150=30/90$, hence $R=50$ $\\Omega$; A uses the 30 $\\Omega$ wire section as the unknown.',
 'At null the unknown cell supplies no current, so its internal resistance need not be known. A remains necessary because the unknown e.m.f. must fit the wire p.d. range.',
 'Cooling increases thermistor resistance to 30 k$\\Omega$; the voltmeter spans the 20 k$\\Omega$ resistor, giving $60(20)/(20+30)=24$ V. C assigns the output to the thermistor.',
 'Across $R_1$, $V_{out}=V_{in}R_1/(R_1+R_2)$. Doubling $R_1$ and halving $R_2$ raises the fraction; doubling both leaves it unchanged.'
]
for j,(qid,ex) in enumerate(zip(past_ids,explanations),1):
 q=bank[qid]
 local=[k for k in q['kcs'] if k.startswith(SUB+'.')]
 items.append(dict(id=f'{SUB}-p{j:02d}',kcs=local,kind='mcq',difficulty=3,command_word='Identify',source={'type':'past','ref':q['ref'],'qid':qid},stem=q['stem'],options=q['options'],answer=q['answer'],image=q.get('image'),marks=1,explanation=ex,hints=[]))

def worked(n,k,problem,steps,faded,value,unit):
 return dict(id=f'we{n}',kc=K(k),problem=problem,steps=[dict(do=a,why=b,**({'check':{'kind':'numeric','answer':{'value':round(v,8),'unit':unit,'sf_ok':[2,3]}}} if v is not None else {})) for a,b,v in steps],faded=dict(id=f'we{n}f',problem=faded,answer={'value':round(value,8),'unit':unit,'sf_ok':[2,3]},blank_from=1))
worked_examples=[
 worked(1,1,'A 9.0 V supply feeds 2.0 k$\\Omega$ and 4.0 k$\\Omega$ in series. Find p.d. across 4.0 k$\\Omega$.',[('$V_{out}=V_{in}R_2/(R_1+R_2)$.','The same current passes through both series resistors.',None),('$V_{out}=9.0(4.0)/(2.0+4.0)=6.0$ V.','The output terminals span the 4.0 k$\\Omega$ arm.',9*4/(2+4))],'A 12 V supply feeds 3.0 k$\\Omega$ and 6.0 k$\\Omega$ in series. Find p.d. across 6.0 k$\\Omega$.',12*6/(3+6),'V'),
 worked(2,2,'On a uniform wire, a 1.50 V reference balances at 75.0 cm. An unknown cell balances at 45.0 cm. Find its e.m.f.',[('$E_x/E_0=l_x/l_0$.','On the same steady-current wire, p.d. is proportional to length.',None),('$E_x=1.50(45.0/75.0)=0.900$ V.','At null the unknown cell has no internal voltage drop.',1.5*45/75)],'A 1.20 V reference balances at 60.0 cm; an unknown balances at 35.0 cm. Find its e.m.f.',1.2*35/60,'V'),
 worked(3,4,'A 6.0 V divider has a 10 k$\\Omega$ fixed resistor and a 20 k$\\Omega$ thermistor. Find p.d. across the thermistor.',[('$V_T=V_{in}R_T/(R_F+R_T)$.','The thermistor is the output arm.',None),('$V_T=6.0(20)/(10+20)=4.0$ V.','Use the resistance ratio for the series circuit.',6*20/(10+20))],'A 9.0 V divider has 15 k$\\Omega$ fixed and 30 k$\\Omega$ thermistor resistances. Find p.d. across the thermistor.',9*30/(15+30),'V')]
pack=dict(subtopic=SUB,spec='9702',version=1,note=NOTE,outline='A potential divider shares a supply p.d. between series resistances: $V_{out}=V_{in}R_{out}/R_{total}$. A uniform potentiometer wire has a constant potential gradient. At a galvanometer null, the unknown p.d. equals the wire p.d. up to the contact; for the same gradient $V_1/V_2=l_1/l_2$. No current flows through the comparison cell. Thermistors and LDRs change divider output as temperature or illumination changes their resistance.',misconceptions=mis,worked=worked_examples,items=items,flashcards=[dict(id='fc1',kc=K(1),front='State the potential divider principle.',back='In a series circuit, the supply p.d. is shared in proportion to the component resistances.'),dict(id='fc2',kc=K(2),front='State the potentiometer comparison principle.',back='At null, each p.d. equals the p.d. across its balance length on the uniform wire; their ratio equals the length ratio.'),dict(id='fc3',kc=K(3),front='What does zero galvanometer deflection mean?',back='No current flows in the comparison branch because the opposed p.d.s are equal.'),dict(id='fc4',kc=K(4),front='How do NTC thermistor and LDR resistances respond?',back='NTC resistance decreases with increasing temperature; LDR resistance decreases with increasing light intensity.')],diagrams=[])
OUT.parent.mkdir(parents=True,exist_ok=True)
OUT.write_text(json.dumps(pack,ensure_ascii=False,indent=1))
print(OUT,len(items))
