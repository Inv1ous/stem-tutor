"""Build the 9702-6.2 teaching pack. All computed values originate here."""
from __future__ import annotations
import json
from itertools import product
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'build/out/packs/9702/9702-6.2.json'
BANK = {q['id']: q for q in json.loads((ROOT / 'build/work/mcq/9702.tagged.json').read_text())}
K = lambda n: f'9702-6.2.{n}'

mis = [
 dict(id='m1',kc=K(1),statement='Elastic limit and limit of proportionality are the same boundary.',refutation='A sample may cease to obey Hooke’s law while still returning to its original dimensions after unloading.',contrast='The limit of proportionality ends the straight-line region; the elastic limit marks the onset of permanent deformation.',source='ER 9702 s22 P12 Q20'),
 dict(id='m2',kc=K(1),statement='A sample that partly recovers has undergone elastic deformation only.',refutation='A permanent change in length is evidence of plastic deformation, even if some of the change recovers.',contrast='The recovered part is elastic and the residual part is plastic.',source='ER 9702 w23 P23 Q4'),
 dict(id='m3',kc=K(2),statement='The entire area from zero gives the extra work for an already extended wire.',refutation='The extra work is the area only between the initial and final extensions.',contrast='For a linear segment, use the trapezium area $\\tfrac12(F_1+F_2)(x_2-x_1)$.',source='ER 9702 w20 P12 Q21'),
 dict(id='m4',kc=K(2),statement='The area between loading and unloading curves is stored elastic energy.',refutation='The loading area is work input and unloading area is recovered work; their difference is dissipated as thermal energy.',contrast='Only a reversible loading path returns all the work.',source='ER 9702 w20 P11 Q20'),
 dict(id='m5',kc=K(3),statement='Area under a length–force graph can be found as $\\tfrac12 FL$ using total length.',refutation='The deformation displacement is extension $x=L-L_0$, not the whole spring length.',contrast='Within the linear region, $E_P=\\tfrac12 F(L-L_0)$.',source='ER 9702 s23 P13 Q19'),
 dict(id='m6',kc=K(4),statement='Elastic energy is $Fx$ for a spring obeying Hooke’s law.',refutation='The force rises from zero to $F$, so the average force is $F/2$.',contrast='The triangle under the graph gives $E_P=\\tfrac12 Fx$.',source='ER 9702 w20 P13 Q21'),
 dict(id='m7',kc=K(4),statement='A compression in centimetres can be substituted directly into $\\tfrac12kx^2$ with $k$ in N m$^{-1}$.',refutation='The extension or compression must be in metres to obtain joules.',contrast='Convert centimetres to metres before squaring.',source='ER 9702 w23 P22 Q3'),
]

past_info = [
 ('9702_s22_12_q20',K(1),3,'A is the only statement that must hold: beyond the elastic limit deformation is plastic. D confuses this with the limit of proportionality, which may be reached earlier.',{'D':'m1'}),
 ('9702_w23_13_q19',K(1),4,'The length recovers from $0.6L$ to $0.8L$, an elastic recovery of $0.2L$, but remains $0.2L$ shorter than at first, so deformation is also plastic. Choosing elastic only ignores the permanent shortening.',{'B':'m2'}),
 ('9702_w25_13_q23',K(1),3,'The band returns to zero extension when unloaded, so it remains elastic even though the loading and unloading curves differ. A mistakes hysteresis for permanent deformation.',{'A':'m2','D':'m4'}),
 ('9702_w20_12_q21',K(2),4,'Use the area from 3.0 to 5.0 mm: $\\tfrac12(60+100)(2.0\times10^{-3})=0.16$ J. A instead calculates an area starting at zero extension.',{'A':'m3'}),
 ('9702_w20_11_q20',K(2),4,'The difference between work input along P and recovered work along Q is energy dissipated as heat. D describes the full area under P, not the shaded difference.',{'A':'m4','D':'m4'}),
 ('9702_w19_12_q19',K(2),3,'The area between the curves is the difference between work done in stretching and work returned on contraction; it becomes thermal energy. A confuses this loss with recoverable elastic energy.',{'A':'m4'}),
 ('9702_s23_12_q19',K(3),4,'The added energy is the trapezium from 0.30 to 0.45 mm: $\\tfrac12(100+150)(0.15\times10^{-3})=0.01875$ J, or 19 mJ. A uses too small an area rather than the full force range.',{'A':'m3'}),
 ('9702_w25_13_q20',K(3),4,'The unstretched length is 4 cm; at 6 N the length is 8 cm, so extension is 4 cm. The triangular area is $\\tfrac12(6)(0.04)=0.12$ J. B doubles this by treating final force as the average.',{'B':'m6','D':'m5'}),
 ('9702_s23_13_q19',K(3),3,'Extension is $L_1-L_0$. The triangular area gives $\\tfrac12F(L_1-L_0)$; D omits the half and A uses length in place of extension.',{'A':'m5','D':'m6'}),
 ('9702_w20_13_q21',K(4),4,'$E_P=\\tfrac12Fx=\\tfrac12(7.00\times10^6)(5.00\times10^{-3})=17.5$ kJ. D uses $Fx$ and is twice the correct work.',{'D':'m6'}),
 ('9702_s21_12_q20',K(4),3,'Each energy is $\\tfrac12Fx$; Y has twice both force and extension, so four times the energy. C accounts for doubling only one factor.',{'C':'m6'}),
 ('9702_w24_11_q22',K(4),3,'The extension is $0.50-0.30=0.20$ m, hence $E_P=\\tfrac12(400)(0.20)^2=8.0$ J. B omits the factor one half.',{'B':'m6','C':'m5'}),
]
items=[]
for qid,kc,diff,explanation,distractors in past_info:
 q=BANK[qid]
 items.append(dict(id='9702-6.2-p'+str(len(items)+1).zfill(2),kcs=[kc],kind='mcq',difficulty=diff,command_word='Calculate' if 'How much' in q['stem'] or 'What is the work' in q['stem'] or 'What is the elastic potential' in q['stem'] else 'Identify',source={'type':'past','ref':q['ref'],'qid':qid},stem=q['stem'],options=q['options'],answer=q['answer'],image=q.get('image'),marks=1,explanation=explanation,distractors=distractors))

def gen(kind,kcs,stem,difficulty,command_word,explanation,hints,**more):
 items.append(dict(id=f'9702-6.2-i{1+sum(i["source"]["type"]=="generated" for i in items):02}',kcs=kcs,kind=kind,difficulty=difficulty,command_word=command_word,source={'type':'generated'},stem=stem,marks=more.pop('marks',1),explanation=explanation,hints=hints,**more))

def num(value,unit='J'):
 return {'value':round(value,10),'unit':unit,'sf_ok':[2,3]}

gen('short',[K(1)],'Define elastic deformation and plastic deformation.',2,'Define','Elastic deformation is reversed on removal of the deforming force; plastic deformation leaves a permanent change.', ['Think about unloading.','Describe whether the original dimensions return.','State the outcome separately for each deformation.'],marks=2,rubric=[{'point':'Elastic deformation is reversed when the force is removed.','keywords':[['reversed','recover','returns'],['force','load']]},{'point':'Plastic deformation leaves a permanent change after force removal.','keywords':[['permanent','remains','does not return'],['force','load']]}])
gen('mcq',[K(1)],'A wire is no longer in the straight-line part of its force–extension graph but returns to its original length when unloaded. Which statement follows?',3,'Identify','The wire is still elastic, although force is no longer proportional to extension. The two limits need not coincide.', ['Compare the two limits.','Use what happens on unloading to decide whether deformation is elastic.','A curved graph can still describe recoverable deformation.'],options={'A':'It has exceeded its elastic limit.','B':'It is elastic but beyond its limit of proportionality.','C':'It has plastically deformed.','D':'Its extension must be proportional to force.'},answer='B',distractors={'A':'m1','C':'m2','D':'m1'},shuffle=True)
gen('structured',[K(1)],'A rod of original length 100.0 mm is stretched to 104.0 mm. After unloading it measures 101.5 mm. Determine the recovered and permanent changes, and identify the two types of deformation.',4,'Determine','It recovers 2.5 mm and retains a permanent extension of 1.5 mm, so both elastic and plastic deformation occurred.',[],marks=4,scheme=[{'mark':'A1','point':'Recovered change $104.0-101.5=2.5$ mm.','check':{'kind':'numeric','answer':num(2.5,'mm')}},{'mark':'A1','point':'Permanent extension $101.5-100.0=1.5$ mm.','check':{'kind':'numeric','answer':num(1.5,'mm')}},{'mark':'B1','point':'Recovered change shows elastic deformation.'},{'mark':'B1','point':'Permanent extension shows plastic deformation.'}])

# Templates use input numbers in simple, exact ranges. Nominal values and all distractors are calculated here.
def template(kc,stem,params,derived,answer_expr,wrong,explanation,hints,difficulty=3):
 env={name:(spec['choices'][0] if 'choices' in spec else spec['min']) for name,spec in params.items()}
 for name,expr in derived.items(): env[name]=eval(expr,{'__builtins__':{}},env)
 a=eval(answer_expr,{'__builtins__':{}},env)
 # Check every discrete parameter combination, including each computed wrong answer.
 ranges=[spec['choices'] if 'choices' in spec else [spec['min']+i*spec['step'] for i in range(round((spec['max']-spec['min'])/spec['step'])+1)] for spec in params.values()]
 for values in product(*ranges):
  trial=dict(zip(params,values))
  for name,expr in derived.items(): trial[name]=eval(expr,{'__builtins__':{}},trial)
  right=eval(answer_expr,{'__builtins__':{}},trial)
  assert right>0
  for expr,_ in wrong:
   bad=eval(expr,{'__builtins__':{}},trial)
   assert abs(bad-right)>0.02*right, (kc,trial,right,bad)
 ds=[{'value':eval(expr,{'__builtins__':{}},env),'misconception':mid} for expr,mid in wrong]
 assert all(abs(d['value']-a)>0.02*abs(a) for d in ds)
 gen('numeric',[kc],stem,difficulty,'Calculate',explanation,hints,answer=num(a),distractors=ds,template={'params':params,'derived':derived,'answer':answer_expr,'distractors':[{'expr':expr,'misconception':mid} for expr,mid in wrong],'constraints':[]})

template(K(2),'A wire already has extension [[x1]] mm at force [[f1]] N. Force rises linearly to [[f2]] N as extension reaches [[x2]] mm. Calculate the additional work done.',{'x1':{'choices':[2,3,4]},'dx':{'choices':[2,3]},'f1':{'choices':[40,60,80]},'df':{'choices':[20,40]}},{'x2':'x1+dx','f2':'f1+df'},'0.5*(f1+f2)*dx/1000',[('0.5*f2*dx/1000','m3'),('0.5*(f1+f2)*x2/1000','m3')],'The required area is the trapezium between the initial and final extensions, in metres.',['Identify the start and end extensions.','Use the mean of the two end forces.','Convert the change in extension from mm to m before finding area.'],4)
template(K(3),'A spring obeys Hooke’s law. Its unstretched length is [[L0]] cm; at force [[F]] N its length is [[L1]] cm. Use the force–extension graph area to find the elastic potential energy.',{'L0':{'choices':[10,12,15]},'dx':{'choices':[4,6,8]},'F':{'choices':[6,8,10]}},{'L1':'L0+dx'},'0.5*F*dx/100',[('F*dx/100','m6'),('0.5*F*L1/100','m5')],'The triangle has height $F$ and width equal to extension $L_1-L_0$, in metres.',['Find extension, not full length.','The area under a linear force–extension graph is triangular.','Convert the extension from cm to m.'],4)
template(K(4),'A spring of stiffness [[k]] N m$^{-1}$ is compressed by [[x]] cm within its limit of proportionality. Calculate its elastic potential energy.',{'k':{'choices':[200,300,400]},'x':{'choices':[4,6,8]}},{},'0.5*k*(x/100)**2',[('k*(x/100)**2','m6'),('0.5*k*x**2','m7')],'Use $E_P=\\tfrac12kx^2$ with compression converted to metres before squaring.',['Choose the stiffness form of the energy equation.','Square the compression after unit conversion.','Convert centimetres to metres first.'],4)

f1,x1,f2,x2=20,0.001,50,0.004
w=0.5*(f1+f2)*(x2-x1)
k=320
x=0.15
energy=0.5*k*x*x
worked=[
 {'id':'we1','kc':K(3),'problem':'A linear force–extension graph passes through (1.0 mm, 20 N) and (4.0 mm, 50 N). Find the additional elastic energy stored between these states.','steps':[{'do':'Read $F_1=20$ N, $F_2=50$ N, and $\\Delta x=(4.0-1.0)$ mm $=0.003$ m.','why':'The required energy change begins at the initial extension, not at zero.'},{'do':'Use the trapezium area: $\\Delta E_P=\\tfrac12(F_1+F_2)\\Delta x$.','why':'The force changes linearly, so its mean over this interval is the average of its endpoints.'},{'do':f'$\\Delta E_P=\\tfrac12(20+50)(0.003)={w:.3f}$ J.','why':'Area under a force–extension graph is work; within elastic behaviour it increases the stored energy.','check':{'kind':'numeric','answer':num(w)}}],'faded':{'id':'we1f','problem':'The force rises linearly from 30 N at 2.0 mm to 70 N at 5.0 mm. Find the additional elastic energy stored.','answer':num(0.5*(30+70)*(0.005-0.002)),'blank_from':1}},
 {'id':'we2','kc':K(4),'problem':'A 320 N m$^{-1}$ spring is stretched 0.15 m within its limit of proportionality. Calculate its elastic potential energy.','steps':[{'do':'State $E_P=\\tfrac12kx^2$.','why':'Hooke’s law makes force proportional to extension, giving a triangular graph area.'},{'do':'Substitute $k=320$ N m$^{-1}$ and $x=0.15$ m.','why':'Metres with N m$^{-1}$ give energy in joules.'},{'do':f'$E_P=\\tfrac12(320)(0.15)^2={energy:.2f}$ J.','why':'The extension is squared, and the half accounts for rising force.','check':{'kind':'numeric','answer':num(energy)}}],'faded':{'id':'we2f','problem':'A 250 N m$^{-1}$ spring is compressed by 0.12 m within its limit of proportionality. Calculate its elastic potential energy.','answer':num(0.5*250*0.12**2),'blank_from':1}}
]
flashcards=[
 {'id':'fc1','kc':K(1),'front':'Define elastic deformation.','back':'Deformation that is reversed when the deforming force is removed; the object returns to its original dimensions.'},
 {'id':'fc2','kc':K(1),'front':'Define plastic deformation.','back':'Deformation that is not fully reversed when the deforming force is removed; a permanent change remains.'},
 {'id':'fc3','kc':K(1),'front':'What is the elastic limit?','back':'The maximum force or stress before plastic deformation begins; beyond it the material does not fully return to its original dimensions when unloaded.'},
]
pack={'subtopic':'9702-6.2','spec':'9702','version':1,'note':'Subjects/9702 Physics/06 Deformation of solids/6.2 Elastic and plastic behaviour.md','outline':'Elastic deformation is reversed when the force is removed; plastic deformation leaves a permanent change. The elastic limit is the boundary before plastic behaviour, distinct from the limit of proportionality. Work done in changing extension is the area under a force–extension graph over the relevant interval. For an elastic loading path, this work is stored elastic potential energy. Within the limit of proportionality, force rises linearly from zero, so $E_P=\\tfrac12Fx=\\tfrac12kx^2$. Extension must be measured from the natural length and converted to metres. A loading–unloading loop encloses energy dissipated as heat.','misconceptions':mis,'worked':worked,'items':items,'flashcards':flashcards,'diagrams':[{'file':'Assets/9702/9702-6.2-force-extension.svg','type':'graph_sketch','params':{'lines':[{'points':[[0,0],[4,4]],'label':'linear elastic','style':'solid'},{'points':[[4,4],[6,5.5],[8,5.7]],'label':'beyond proportional limit','style':'solid'}],'xlabel':'extension x','ylabel':'force F','shade':{'polygon':[[0,0],[4,0],[4,4]]},'annotations':[{'xy':[4,4],'text':'limit of proportionality','xytext':[5,2]}],'ticks':False}}]}
OUT.write_text(json.dumps(pack,ensure_ascii=False,indent=1)+'\n')
print(OUT, 'items',len(items),'worked',len(worked))
