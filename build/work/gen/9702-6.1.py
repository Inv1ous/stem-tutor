"""Generate the 9702-6.1 pack; numeric content is calculated and checked here."""
import itertools
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SUB = '9702-6.1'
K = {n: f'{SUB}.{n}' for n in range(1, 7)}
BANK = {q['id']: q for q in json.loads((ROOT/'build/work/mcq/9702.tagged.json').read_text())}
# corrections to bank questions (garbled fractions, figure-only options) live in overrides.json, as for the extras
FIX={q:{k:v for k,v in f.items() if k in ('stem','options')} for q,f in json.loads((ROOT/'build/work/mcq/overrides.json').read_text()).items()}
items = []

mis = [
    dict(id='m1',kc=K[1],statement='A tensile force shortens a wire.',refutation='Tension pulls outward along the wire and increases its length; compression pushes inward and shortens it.',contrast='Name the force by what it does to the specimen in the one-dimensional direction.',source='research'),
    dict(id='m2',kc=K[2],statement='The limit of proportionality is necessarily the elastic limit.',refutation='The limit of proportionality is the end of the straight-line part of the force–extension graph; elastic recovery can persist beyond it.',contrast='A curved unloading response can still return to the original length.',source='ER 9702 s22 P12 Q20'),
    dict(id='m3',kc=K[3],statement='Hooke’s law means extension is proportional to the original length of a spring.',refutation='For a given spring within its limit of proportionality, extension is proportional to applied force.',contrast='Plot force against extension: the Hooke’s-law region is a straight line through the origin.',source='research'),
    dict(id='m4',kc=K[4],statement='The gradient of an extension–force graph is the spring constant.',refutation='That gradient is extension divided by force, so it is $1/k$; a force–extension graph has gradient $k$.',contrast='Always read the axes before taking the gradient.',source='ER 9702 w23 P23 Q4'),
    dict(id='m5',kc=K[4],statement='Millimetres or centimetres can be inserted directly into $k=F/x$ to obtain N m$^{-1}$.',refutation='Extension must be in metres for $k$ in N m$^{-1}$.',contrast='Convert $15$ cm to $0.15$ m before dividing force by extension.',source='ER 9702 w19 P11 Q19'),
    dict(id='m6',kc=K[5],statement='Doubling wire diameter doubles its cross-sectional area.',refutation='Circular area is $A=\\pi d^2/4$, so doubling diameter quadruples area.',contrast='For equal material and load, $x=FL/(AE)$ falls by a factor of four.',source='ER 9702 s22 P11 Q19'),
    dict(id='m7',kc=K[5],statement='Strain is extension divided by final length, or stress is force divided by any surface area.',refutation='Strain uses original length; tensile stress uses cross-sectional area perpendicular to the force.',contrast='Use $\\varepsilon=x/L$ and $\\sigma=F/A$ before finding $E=\\sigma/\\varepsilon$.',source='ER 9702 w20 P21 Q4'),
    dict(id='m8',kc=K[6],statement='A single loaded length gives the wire extension without a reference reading.',refutation='Extension is the change from the original or reference length; a taut reference wire helps remove support movement.',contrast='Record the initial and loaded positions for each load and subtract them.',source='ER 9702 s23 P23 Q6'),
]

def hints(k):
    h={1:['Decide whether the forces pull outward or push inward.','Look at the change in length along the force.','Relate the force direction to extension or compression.'],
       2:['Separate applied force from change in length.','Use the axes of a force–extension graph.','Locate where the straight segment first ends.'],
       3:['Think about proportionality for one specimen.','Write the relationship between load and extension.','Check that the graph passes through the origin.'],
       4:['Start with force divided by extension.','Convert extension to metres.','Write $k=F/x$ before substituting.'],
       5:['Start from stress and strain.','Use the cross-sectional area and original length.','Write $E=FL/(Ax)$ and convert all lengths to metres.'],
       6:['List the measurements needed for $E=FL/(Ax)$.','Separate original length, diameter, applied force and extension.','Take an initial pointer reading before adding a load.']}
    return h[k]

def past(qid,k,explanation,wrong=None):
    assert BANK[qid]['answer'] in BANK[qid]['options']
    q={**BANK[qid],**FIX.get(qid,{})}
    n=1+sum(i['source']['type']=='past' for i in items)
    it=dict(id=f'{SUB}-p{n:02d}',kcs=[K[k]],kind='mcq',difficulty=3,command_word='Identify',source={'type':'past','ref':q['ref'],'qid':qid},stem=q['stem'],options=q['options'],answer=q['answer'],marks=1,explanation=explanation,distractors=wrong or {})
    if q.get('image'): it['image']=q['image']
    items.append(it)

def short(k,command,stem,points,explanation,difficulty=2,h=None):
    n=1+sum(i['source']['type']=='generated' for i in items)
    items.append(dict(id=f'{SUB}-i{n:02d}',kcs=[K[k]],kind='short',difficulty=difficulty,command_word=command,source={'type':'generated'},stem=stem,marks=len(points),rubric=[{'point':p,'keywords':kw} for p,kw in points],explanation=explanation,hints=h or hints(k)))

def numeric(k,stem,params,answer_expr,wrong,unit,explanation,difficulty=3,h=None):
    n=1+sum(i['source']['type']=='generated' for i in items)
    names=list(params)
    for values in itertools.product(*(params[p]['choices'] for p in names)):
        env=dict(zip(names,values)); allowed={'pi':math.pi,'sqrt':math.sqrt}
        a=eval(answer_expr,{'__builtins__':{}},env|allowed)
        assert math.isfinite(a)
        for expr,_ in wrong:
            d=eval(expr,{'__builtins__':{}},env|allowed)
            assert math.isfinite(d) and abs(d-a)>.02*max(abs(a),1e-12),(stem,env,expr)
    items.append(dict(id=f'{SUB}-i{n:02d}',kcs=[K[k]],kind='numeric',difficulty=difficulty,command_word='Calculate',source={'type':'generated'},stem=stem,marks=3,answer={'unit':unit,'sf_ok':[2,3]},template={'params':params,'answer':answer_expr,'distractors':[{'expr':e,'misconception':m} for e,m in wrong],'constraints':['1 > 0']},explanation=explanation,hints=h or hints(k)))

# Original question text, option order and answer letters come directly from the tagged bank.
past('9702_w25_12_q21',2,'The marked change is the shortening of the spring: compression. B names the applied load, not a change in length.',{'B':'m1'})
past('9702_w24_13_q21',2,'Hooke’s law stops at the first departure from the straight-line force–extension region, labelled A. A later point may mark the elastic limit, which need not coincide with this limit.',{'B':'m2'})
past('9702_s23_11_q18',3,'The load per surviving wire changes from $W/3$ to $W/2$, so its extension becomes $0.40(3/2)=0.60$ cm. The lamp descends by $0.60-0.40=0.20$ cm; D confuses total extension with additional extension.',{'D':'m3'})
past('9702_w19_12_q18',3,'At 5.0 N, extension is $14-11=3.0$ cm; proportionality gives $3.0(7.0/5.0)=4.2$ cm. C treats the spring length as extension.',{'C':'m3'})
past('9702_w23_12_q18',4,'Parallel springs share extension and their constants add: B gives $3k$. D puts all three in series, giving $k/3$, the smallest combined constant.',{'D':'m4'})
past('9702_w19_11_q19',4,'The graph gives $F=6.0$ N at $x=0.15$ m, so $k=F/x=40$ N m$^{-1}$. C results from treating 15 cm as an unconverted length or reading the wrong slope.',{'C':'m5'})
past('9702_w20_12_q20',4,'The extra force is $(0.100-0.060)9.81$ N and extra extension is $(16.4-12.6)$ cm, giving $k=10.3$ N m$^{-1}$. D is ten times too large because of a length conversion error.',{'D':'m5'})
past('9702_s22_11_q19',5,'At equal force and Young modulus, $x\\propto L/A$. Q has half P’s length and four times its area, so $x_Q/x_P=1/8$. B fails to square the doubled diameter.',{'B':'m6'})
past('9702_w23_13_q18',5,'$A=\\pi(0.0016)^2/4$ and $\\varepsilon=F/(AE)=430/(A\\times130\\times10^9)=1.6\\times10^{-3}$. B follows an incorrect area or unit conversion.',{'B':'m6'})
past('9702_w22_12_q20',5,'Strain is extension divided by unstretched length, so both measurements in B are needed. Area in A is used for stress, not strain.',{'A':'m7'})
past('9702_w20_13_q20',5,'Each of four wires supports a quarter of the platform weight. Using $x=FL/(AE)$ with $F=200(9.81)/4$ and $A=\\pi(0.0030)^2/4$ gives $1.7\\times10^{-3}$ m. D uses the whole weight in one wire.',{'D':'m7'})
past('9702_s24_13_q3',6,'The diameter contributes twice its fractional uncertainty because $E\\propto d^{-2}$: $2(0.02/0.54)=7.4\\%$, exceeding the extension contribution $0.2/5.2=3.8\\%$. D ignores the squared diameter.',{'D':'m6'})

# Verify quantitative explanations against the original data.
assert math.isclose(.4*3/2-.4,.2)
assert math.isclose((14-11)*7/5,4.2)
assert math.isclose(6/.15,40)
assert math.isclose((.100-.060)*9.81/(.164-.126),10.326315789473684)
assert math.isclose(430/(math.pi*(.0016**2)/4*130e9),.001645,rel_tol=.001)
assert math.isclose((200*9.81/4)*5/(math.pi*.003**2/4*2.1e11),.001652,rel_tol=.001)
assert 2*.02/.54>.2/5.2

# Six independent retrieval prompts for each conceptual/factual KC.
short(1,'Define','Define tensile force acting on a straight specimen.', [('A tensile force pulls the specimen outward along its length.',[['pull','tension'],['outward','apart']])],'Tension is a pulling force along the specimen and tends to extend it.')
short(1,'Define','Define compressive force acting on a straight specimen.', [('A compressive force pushes inward along the specimen.',[['push','compression'],['inward','together']])],'Compression pushes the specimen inward and tends to shorten it.')
short(1,'Predict','A rod is pulled at opposite ends along its length. Predict the one-dimensional deformation.', [('Its length increases: it extends.',[['longer','length increases','extends','extension']])],'Opposed outward pulls create tensile deformation.')
short(1,'Predict','A straight column is squeezed along its axis. Predict its change in length.', [('Its length decreases: it compresses.',[['shorter','decreases','compression','contracts']])],'Opposed inward pushes create compressive deformation.')
short(1,'Explain','Explain why a hanging load causes tensile deformation in its supporting wire.', [('The load pulls the wire along its axis.',[['load','weight'],['pull','tension']]),('The wire extends along its length.',[['extend','longer','extension']])],'The load pulls the wire downward while the support pulls upward, stretching it along its axis.',4)
short(1,'Compare','Compare one-dimensional tensile and compressive deformation.', [('Tension increases length.',[['tension','tensile'],['increase','longer','extension']]),('Compression decreases length.',[['compression','compressive'],['decrease','shorter']])],'Both act along the specimen; tension lengthens it and compression shortens it.',4)

short(2,'Define','Define load in a force–extension experiment.', [('The load is the applied force on the specimen.',[['applied'],['force']])],'Load is the force applied to the spring or wire.', h=['Is a load a length or a force? Think about its unit.', 'In a force–extension experiment the load is what is hung on, or applied to, the spring or wire.', 'State it as a force and say what it acts on.'])
short(2,'Define','Define extension of a wire.', [('Extension is the increase in length from its original length.',[['increase','change'],['length'],['original','unstretched']])],'Extension is loaded length minus original length.', h=['Extension is a change in length, measured in metres.', 'Compare the stretched length with a reference length.', 'Say which length it is measured from: the original, unstretched length.'])
short(2,'Define','Define compression of a spring.', [('Compression is the decrease in length from the original length.',[['decrease','shortening'],['length']])],'Compression is the spring’s shortening due to a compressive load.', h=['Compression is a change in length, like extension but the other way.', 'Compare the squashed length with a reference length.', 'Say whether the length goes up or down, and from which length it is measured.'])
short(2,'Define','Define the limit of proportionality on a force–extension graph.', [('It is the point beyond which force and extension cease to be directly proportional.',[['force','load'],['extension'],['proportional','straight']])],'The limit of proportionality ends the straight-line region through the origin; it does not necessarily mark permanent deformation.', h=['Think about the shape of a force–extension graph for small loads.', 'Up to this point the graph is a straight line through the origin.', 'Say what stops being true about force and extension beyond this point.'])

short(3,'State','State Hooke’s law and its condition of validity.', [('Extension is directly proportional to applied force.',[['extension'],['directly proportional','proportional'],['force','load']]),('This applies up to the limit of proportionality.',[['limit of proportionality']])],'For one spring, $F\\propto x$ until its limit of proportionality.')
short(3,'Explain','A force–extension graph curves after an initial straight line. Explain whether Hooke’s law holds in the curved region.', [('Force and extension are no longer directly proportional.',[['force'],['extension'],['not proportional','no longer proportional','curved']]),('Hooke’s law therefore does not hold beyond the limit of proportionality.',[['Hooke'],['limit of proportionality','does not hold']])],'Curvature means the ratio $F/x$ is not constant, so the limit of proportionality has been passed.',4)
numeric(3,'A spring extends [[x]] cm under a load of [[F]] N while obeying Hooke’s law. Calculate its extension under a load of [[G]] N, in cm.',{'x':{'choices':[2,3,4]},'F':{'choices':[4,5]},'G':{'choices':[8,10]}},'x*G/F',[('x*F/G','m3'),('x*G/(100*F)','m5')],'cm','Since extension is proportional to force, $x_2=x_1F_2/F_1$.', h=['Think about proportionality for one specimen.', 'Write the relationship between load and extension.', 'Use $x_2 = x_1F_2/F_1$.'])

numeric(4,'A spring extends [[x]] cm when its load is [[F]] N. Calculate its spring constant in N m$^{-1}$.',{'x':{'choices':[4,5,8]},'F':{'choices':[2,3,6]}},'100*F/x',[('F/x','m5'),('x/(100*F)','m4')],'N m^-1','Convert centimetres to metres and use $k=F/x$.')

numeric(5,'A wire of length [[L]] m and diameter [[d]] mm extends [[x]] mm under a tensile force of [[F]] N. Calculate its Young modulus in Pa.',{'L':{'choices':[1.5,2.0]},'d':{'choices':[0.8,1.0]},'x':{'choices':[1.0,2.0]},'F':{'choices':[20,30]}},'F*L/(pi*(d*0.001)**2/4*(x*0.001))',[('F*L/(pi*(d*0.001)**2*(x*0.001))','m6'),('F*L/(pi*(d*0.001)**2/4*(x*0.001)*L)','m7')],'Pa','The circular area is $\\pi d^2/4$; use $E=FL/(Ax)$ with SI lengths.',4)

short(6,'Describe','Describe the measurements required to determine Young modulus for a metal wire.', [('Measure the original gauge length.',[['original','unstretched'],['length']]),('Measure the wire diameter at several places and calculate its cross-sectional area.',[['diameter'],['several','multiple','different'],['area']]),('Measure force and the corresponding extension.',[['force','load'],['extension']])],'Use $L$, mean $d$ and $A=\\pi d^2/4$, plus pairs of load and extension.',4)
short(6,'Explain','Why should the wire diameter be measured at several positions and orientations?', [('The diameter can vary and measurements contain random error.',[['diameter'],['vary','variation','random error']]),('A mean improves the area estimate.',[['mean','average'],['area','cross-sectional']])],'Several micrometer readings reduce random error and detect nonuniform diameter.')
short(6,'Describe','How can a reference wire help measure the extension of a loaded test wire?', [('Place an unloaded reference wire beside the test wire on the same support.',[['reference'],['same support','alongside']]),('Measure relative movement between markers to cancel support movement.',[['relative','difference'],['support','movement']])],'A reference wire tracks movement of the support, so relative pointer displacement better represents test-wire extension.',4)
short(6,'Explain','Why should the initial position be recorded before loading the wire?', [('Extension is the difference between loaded and initial positions.',[['difference','subtract','change'],['initial','original'],['loaded']])],'A loaded position alone is not an extension.')
short(6,'Describe','Describe how to obtain Young modulus from a force–extension graph for a wire of known original length and cross-sectional area.', [('Take the gradient $F/x$ of the straight-line region.',[['gradient','slope'],['force','F'],['extension','x']]),('Multiply by original length and divide by cross-sectional area.',[['original','initial'],['length'],['area']])],'For a force–extension graph, $E=(L/A)\\,(F/x)$ using the straight region.',4)

worked=[]
def work(k,problem,steps,value,unit,faded_problem,faded_value):
    assert math.isfinite(value) and math.isfinite(faded_value)
    w={'id':f'we{k}','kc':K[k],'problem':problem,'steps':[],'faded':{'id':f'we{k}f','problem':faded_problem,'answer':{'value':faded_value,'unit':unit,'sf_ok':[2,3]},'blank_from':1}}
    for j,(do,why) in enumerate(steps):
        st={'do':do,'why':why}
        if j==len(steps)-1: st['check']={'kind':'numeric','answer':{'value':value,'unit':unit,'sf_ok':[2,3]}}
        w['steps'].append(st)
    worked.append(w)
work(3,'A spring extends 2.0 cm at 4.0 N. Find its extension at 6.0 N while it obeys Hooke’s law.', [('Write $x_2/x_1=F_2/F_1$.','Hooke’s law gives direct proportionality within the limit.'),('$x_2=2.0(6.0/4.0)=3.0$ cm.','Use the ratio of loads, not their difference.')],2*6/4,'cm','A spring extends 3.0 cm at 5.0 N. Find its extension at 10.0 N.',3*10/5)
work(4,'A spring extends 15 cm under 6.0 N. Find its spring constant.', [('Write $k=F/x$.','Spring constant is force per unit extension.'),('Convert $x=15$ cm to $0.15$ m.','The requested unit is N m$^{-1}$.'),('$k=6.0/0.15=40$ N m$^{-1}$.','Divide force by extension in metres.')],6/.15,'N m^-1','A spring extends 8.0 cm under 4.0 N. Find $k$ in N m$^{-1}$.',4/.08)
work(5,'A 2.0 m wire of diameter 1.0 mm extends 1.0 mm under 40 N. Find its Young modulus.', [('Write $E=\\sigma/\\varepsilon=FL/(Ax)$ and $A=\\pi d^2/4$.','Use cross-sectional area and original length.'),('Convert $d=0.0010$ m and $x=0.0010$ m; $A=\\pi(0.0010)^2/4$.','Square diameter after converting it to metres.'),('$E=40(2.0)/[\\pi(0.0010)^2(0.0010)/4]=1.02\\times10^{11}$ Pa.','Substitute SI values and round to sensible significant figures.')],40*2/(math.pi*.001**2/4*.001),'Pa','A 1.5 m wire of diameter 0.80 mm extends 1.2 mm under 30 N. Find $E$.',30*1.5/(math.pi*.0008**2/4*.0012))
work(6,'A wire has original gauge length 2.0 m and mean diameter 0.80 mm. Its straight-line force–extension graph shows 20 N at 1.0 mm extension. Determine $E$.',[('Measure $L$ and mean $d$; calculate $A=\\pi d^2/4$.','The area comes from several micrometer diameter measurements.'),('Record initial and loaded positions; from the straight-line graph, $F/x=20/0.0010$ N m$^{-1}$.','A reference reading removes support movement, and the straight region gives a constant gradient.'),('$E=(L/A)(F/x)=2.0[20/0.0010]/[\\pi(0.00080)^2/4]=7.96\\times10^{10}$ Pa.','Use the original gauge length and SI extension.')],2*20/(.001*math.pi*.0008**2/4),'Pa','A wire has $L=1.5$ m and mean $d=1.0$ mm. Its straight-line graph shows 30 N at 1.0 mm extension. Find $E$.',1.5*30/(.001*math.pi*.001**2/4))

pack={'subtopic':SUB,'spec':'9702','version':1,'note':'Subjects/9702 Physics/06 Deformation of solids/6.1 Stress and strain.md','outline':'Tensile forces pull and extend a specimen; compressive forces push and shorten it. Load is applied force, and extension or compression is the change from original length. Up to the limit of proportionality, Hooke’s law gives $F=kx$ for one spring. Spring constant $k=F/x$ has unit N m$^{-1}$. Tensile stress is $\\sigma=F/A$ in Pa, strain is $\\varepsilon=x/L$ with no unit, and Young modulus is $E=\\sigma/\\varepsilon=FL/(Ax)$ in Pa. For a wire, measure original gauge length, repeated diameter readings, and force–extension pairs in the straight-line region; $E=(L/A)$ times the force–extension gradient.','misconceptions':mis,'worked':worked,'items':items,'flashcards':[{'id':f'fc{n}','kc':K[k],'front':front,'back':back} for n,k,front,back in [(1,2,'What is load?','The force applied to a specimen.'),(2,2,'What is extension?','The increase in length from the original length.'),(3,2,'What is compression?','The decrease in length from the original length.'),(4,2,'What is the limit of proportionality?','The point beyond which force and extension are no longer directly proportional.'),(5,5,'Define Young modulus.','Young modulus is the ratio of tensile stress to tensile strain.')]],'diagrams':[]}
out=ROOT/'build/out/packs/9702/9702-6.1.json'
out.parent.mkdir(parents=True,exist_ok=True)
out.write_text(json.dumps(pack,ensure_ascii=False,indent=1))
print('items',len(items),'templates',sum('template' in i for i in items),'worked',len(worked))
