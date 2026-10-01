"""Build chapter 9702-5.2 from tagged questions and computed examples."""
import json
import math
import sys
from pathlib import Path
from sympy import Rational

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'build'))
from validate_pack import validate

SUB = '9702-5.2'
K = {i: f'{SUB}.{i}' for i in range(1, 5)}
BANK = {q['id']: q for q in json.loads((ROOT/'build/work/mcq/9702.tagged.json').read_text())}
items = []

def past(qid, k, explanation, wrong=None):
    q = BANK[qid]
    assert q['answer'] in q['options']
    n = 1 + sum(x['source']['type'] == 'past' for x in items)
    it = {'id': f'{SUB}-p{n:02d}', 'kcs': [K[k]], 'kind': 'mcq', 'difficulty': 3,
          'command_word': 'Identify', 'source': {'type': 'past', 'ref': q['ref'], 'qid': qid},
          'stem': q['stem'], 'options': q['options'], 'answer': q['answer'], 'marks': 1,
          'explanation': explanation, 'distractors': wrong or {}}
    if q.get('image'): it['image'] = q['image']
    items.append(it)

def short(k, command, stem, points, explanation, difficulty=2):
    n = 1 + sum(x['source']['type'] == 'generated' for x in items)
    items.append({'id': f'{SUB}-i{n:02d}', 'kcs': [K[k]], 'kind': 'short',
        'difficulty': difficulty, 'command_word': command, 'source': {'type': 'generated'},
        'stem': stem, 'marks': len(points),
        'rubric': [{'point': p, 'keywords': kw} for p,kw in points],
        'explanation': explanation,
        'hints': ['Identify the relevant force, displacement, or change in speed.',
                  'Start with the work done or equation of motion required by the question.',
                  'Write the first equation, then substitute the physical quantity it represents.']})

def numeric(k, stem, params, answer_expr, distractors, unit, explanation, difficulty=3):
    n = 1 + sum(x['source']['type'] == 'generated' for x in items)
    # Independently evaluate every Cartesian combination, checking numerical separation.
    import itertools
    keys = list(params)
    for values in itertools.product(*[params[key]['choices'] for key in keys]):
        env = dict(zip(keys, values))
        ans = eval(answer_expr, {'__builtins__': {}}, env)
        assert math.isfinite(ans)
        for expr,_ in distractors:
            d = eval(expr, {'__builtins__': {}}, env)
            assert math.isfinite(d) and abs(d-ans) > .02*max(abs(ans), 1e-12), (env, expr)
    items.append({'id': f'{SUB}-i{n:02d}', 'kcs': [K[k]], 'kind': 'numeric',
        'difficulty': difficulty, 'command_word': 'Calculate', 'source': {'type': 'generated'},
        'stem': stem, 'marks': 3, 'template': {'params': params, 'answer': answer_expr,
        'distractors': [{'expr': e, 'misconception': m} for e,m in distractors], 'constraints': ['1 > 0']},
        'answer': {'unit': unit, 'sf_ok': [2,3]}, 'explanation': explanation,
        'hints': ['Identify which given quantity is mass and which is a vertical height or speed.',
                  'Write the energy equation before substituting.',
                  'Convert to SI units and substitute, keeping the square on speed where needed.']})

mis = [
 {'id':'m1','kc':K[1],'statement':'The distance along a slope is the height in $\\Delta E_P=mg\\Delta h$.','refutation':'Gravity acts vertically, so the energy change depends on vertical height, not path length.','contrast':'A longer frictionless ramp to the same height requires the same gain in gravitational potential energy.','source':'ER 9702 s22 P23 Q4'},
 {'id':'m2','kc':K[2],'statement':'An object moving horizontally in a uniform vertical field gains gravitational potential energy.','refutation':'Its vertical displacement is zero, so $\\Delta E_P=mg(0)=0$.','contrast':'Only a change in height changes gravitational potential energy in this field.','source':'research'},
 {'id':'m3','kc':K[2],'statement':'A falling object at constant speed gains kinetic energy as it loses gravitational potential energy.','refutation':'Constant speed means constant $E_K$; energy lost from the gravitational store is transferred to the surroundings through resistive forces.','contrast':'At terminal speed, the rate of gravitational energy loss is $mgv$ while $E_K$ stays fixed.','source':'ER 9702 s22 P23 Q4'},
 {'id':'m4','kc':K[3],'statement':'The kinetic energy formula follows from $W=\\tfrac12 Fs$.','refutation':'Work by a constant force parallel to displacement is $W=Fs$; the half arises from $v^2-u^2=2as$.','contrast':'From rest, $s=v^2/(2a)$ and $Fs=ma\\,s=\\tfrac12 mv^2$.','source':'research'},
 {'id':'m5','kc':K[4],'statement':'Doubling speed doubles kinetic energy.','refutation':'At fixed mass, $E_K$ is proportional to $v^2$, so doubling speed multiplies it by four.','contrast':'Halving mass and doubling speed doubles kinetic energy overall.','source':'research'},
 {'id':'m6','kc':K[4],'statement':'At the highest point of projectile motion, kinetic energy is zero.','refutation':'Only vertical velocity is zero there; horizontal velocity remains when air resistance is negligible.','contrast':'At the top, use the horizontal speed in $E_K=\\tfrac12 mv^2$.','source':'ER 9702 s23 P13 Q17'},
]

# The wording, option order, and keys are imported unchanged from the tagged bank.
past('9702_w23_12_q17',1,'Work done is force times displacement. Raising the object against its weight gives $W=mg\\Delta h$, stored as gravitational potential energy.')
past('9702_w20_12_q18',1,'Weight is $mg$. Combined with $W=Fs$ for vertical displacement, this gives $\\Delta E_P=mg\\Delta h$. The power equation in D is not the required step.')
past('9702_w24_13_q20',3,'Use $W=Fs$, $F=ma$ and $v^2=u^2+2as$ to obtain the kinetic energy gain. Power in equation 4 does not enter; B replaces the motion equation with power.')
past('9702_w25_12_q17',3,'The work equation is $W=Fs$, not $E=\\tfrac12 Fs$. The factor one half emerges after substituting $s=v^2/(2a)$, so C is the equation not needed.')
past('9702_w22_12_q19',2,'For X, $\\Delta E=3mg_X$; for Y, $4\\Delta E=4mg_Y$. Hence $g_Y=3g_X$, rather than D, which ignores the unequal heights.',{'D':'m1'})
past('9702_w23_13_q17',2,'In time $t$, the fall is $vt$, so $R=mgvt/t=mgv$ and $m=R/(gv)$. C treats the energy loss as a change in kinetic energy despite constant speed.',{'C':'m3'})
past('9702_w22_13_q18',2,'Horizontal displacement has $\\Delta h=0$, so gravitational potential energy is unchanged. C incorrectly treats horizontal distance as vertical height.',{'C':'m2'})
past('9702_w24_12_q18',2,'The minimum work is the gain in gravitational potential energy: $50(9.81)(1.6)=784.8$ J, or 780 J to two significant figures. D uses the 3.4 m plank length as the height.',{'D':'m1'})
past('9702_s23_13_q17',4,'Horizontal speed remains $18/1.5=12$ m s$^{-1}$ at maximum height, so $E_K=\\tfrac12(0.40)(12)^2=28.8$ J. A ignores this horizontal motion.',{'A':'m6'})
past('9702_w24_11_q7',4,'Speed is $p/m=18000/1200=15$ m s$^{-1}$, giving $E_K=\\tfrac12(1200)(15)^2=135000$ J. D omits the factor one half.',{'D':'m4'})
past('9702_w21_13_q18',4,'The energy ratio is $(1/2)(2)^2=2$, so car Q has 480 kJ. B counts only a single power of speed.',{'B':'m5'})
past('9702_w21_12_q19',4,'The energy ratio is $2(1/2)^2=1/2$, so X has half the kinetic energy of Y. B accounts for speed but omits the doubled mass.',{'B':'m5'})

# Recompute fixed past-paper quantities from their stated data.
assert 50*Rational(981,100)*Rational(16,10) == Rational(3924,5)
assert Rational(18,1)/Rational(3,2) == 12
assert Rational(1,2)*Rational(2,5)*12**2 == Rational(144,5)
assert Rational(1,2)*1200*Rational(18000,1200)**2 == 135000
assert Rational(1,2)*2**2 == 2
assert 2*Rational(1,2)**2 == Rational(1,2)
assert 4*(3/4) == 3

short(1,'Show (that)','Show that the gain in gravitational potential energy of mass $m$ raised by vertical height $\\Delta h$ in a uniform gravitational field is $mg\\Delta h$.',[
 ('State that the lifting force balances weight $mg$ at constant speed.',[['force','weight'],['mg']]),
 ('Use work done $W=Fs$ over vertical displacement $\\Delta h$.',[['work','W'],['F'],['height','displacement']]),
 ('Equate work against gravity to gained potential energy.',[['potential energy','E_P'],['work']])],
 'At constant speed, the upward force is $mg$ and its work over vertical displacement $\\Delta h$ is $mg\\Delta h$. This is the potential energy gained.',4)
short(1,'Explain','Why does a frictionless longer ramp not change the gravitational potential energy gained in lifting a crate to a fixed height?',[
 ('The change in gravitational potential energy depends on vertical height.',[['vertical','height']]),
 ('The vertical rise and weight are unchanged, so the work against gravity is unchanged.',[['work','energy'],['same','unchanged']])],
 'Work against gravity is weight times vertical height, irrespective of ramp length.')
short(1,'Show (that)','A mass is raised vertically at constant speed. Starting with $W=Fs$, show why the lifting force equals $mg$ and state the resulting energy change.',[
 ('Zero acceleration means balanced forces, so lifting force equals weight $mg$.',[['constant speed','zero acceleration'],['balance','equal'],['mg']]),
 ('Substitute $F=mg$ and $s=\\Delta h$ into $W=Fs$.',[['mg'],['height','\\Delta h'],['work','W']]),
 ('The work is the increase in gravitational potential energy.',[['potential energy'],['increase','gain']])],
 'Balanced forces give $F=mg$; $W=F\\Delta h=mg\\Delta h$, stored as gravitational potential energy.',4)
short(1,'Explain','For the same vertical rise, explain why the work against gravity is independent of the path taken.',[
 ('Weight acts vertically with magnitude $mg$.',[['weight','gravity'],['vertical']]),
 ('Only vertical displacement contributes to work against gravity.',[['vertical'],['displacement','height']])],
 'The gravitational potential energy change is $mg\\Delta h$ for either path.')
short(3,'Show (that)','Starting from $W=Fs$ and $v^2=u^2+2as$, derive the change in kinetic energy for a constant resultant force parallel to displacement.',[
 ('Use $F=ma$ and $s=(v^2-u^2)/(2a)$.',[['F=ma','force'],['v^2','speed'],['2a']]),
 ('Substitute in $W=Fs$ to get $W=\\tfrac12m(v^2-u^2)$.',[['work','W'],['half','1/2','\\tfrac12'],['v^2-u^2','v^2 - u^2']]),
 ('Identify $E_K=\\tfrac12mv^2$ from the change in energy.',[['kinetic energy','E_K'],['mv^2']])],
 'The work is $ma(v^2-u^2)/(2a)=\\tfrac12m(v^2-u^2)$; hence kinetic energy at speed $v$ is $\\tfrac12mv^2$.',4)
short(3,'Explain','Where does the factor $\\tfrac12$ arise in deriving $E_K$ from equations of motion?',[
 ('The motion equation has the term $2as$.',[['2as','two']]),
 ('Rearranging for displacement introduces division by two.',[['displacement','s'],['divide','half','two']])],
 'From rest, $v^2=2as$ gives $s=v^2/(2a)$; then $Fs=ma\\,s=\\tfrac12mv^2$.')
short(3,'Show (that)','An object accelerates from rest under constant resultant force. Show the work done in reaching speed $v$ in terms of mass $m$.',[
 ('Write $v^2=2as$ for $u=0$.',[['v^2'],['2as']]),
 ('Use $F=ma$ and $W=Fs$.',[['F=ma'],['W=Fs','work']]),
 ('Substitute $s=v^2/(2a)$ to obtain $W=\\tfrac12mv^2$.',[['v^2'],['half','1/2','\\tfrac12'],['mv^2']])],
 'The motion equation supplies $s=v^2/(2a)$, so $W=ma(v^2/(2a))=\\tfrac12mv^2$.',4)
short(3,'Explain','Why must the force used in a work–energy derivation be the resultant force rather than one of several applied forces?',[
 ('$F=ma$ applies to resultant force.',[['resultant'],['F=ma','acceleration']]),
 ('Net work changes kinetic energy.',[['net work','total work','resultant work'],['kinetic energy']])],
 'Only the resultant force produces the acceleration in the motion equation; its work equals the kinetic energy change.')

numeric(2,'A [[m]] kg load is raised vertically by [[h]] m in a uniform field. Calculate its gain in gravitational potential energy, using $g=9.81\\,\\mathrm{m\\,s^{-2}}$.',
 {'m':{'choices':[2,3,4]},'h':{'choices':[1.5,2.5,3.5]}},'m*9.81*h',
 [('m*9.81*(h+1)','m1'),('m*h','m1')],'J',
 'The gain is weight times vertical height: $\\Delta E_P=mg\\Delta h$.')
numeric(4,'A body of mass [[m]] kg moves at [[v]] $\\mathrm{m\\,s^{-1}}$. Calculate its kinetic energy.',
 {'m':{'choices':[2,3,5]},'v':{'choices':[4,6,8]}},'0.5*m*v**2',
 [('m*v**2','m4'),('0.5*m*v','m5')],'J',
 'Use $E_K=\\tfrac12mv^2$ with speed squared; the factor one half is essential.')

# Procedural worked examples and faded variants; every numerical check comes from arithmetic above.
def work(i,k,problem,steps,value,unit,faded_problem,faded_value):
    assert math.isfinite(value) and math.isfinite(faded_value)
    worked.append({'id':f'we{i}','kc':K[k],'problem':problem,
        'steps':[{'do':d,'why':w,**({'check':{'kind':'numeric','answer':{'value':value,'unit':unit,'sf_ok':[2,3]}}} if j==len(steps)-1 else {})} for j,(d,w) in enumerate(steps)],
        'faded':{'id':f'we{i}f','problem':faded_problem,'answer':{'value':faded_value,'unit':unit,'sf_ok':[2,3]},'blank_from':1}})
worked=[]
work(1,1,'Derive the gain in gravitational potential energy for a 2.0 kg load raised 3.0 m at constant speed.',[
 ('At constant speed, lifting force equals weight: $F=mg$.','Balanced forces mean no acceleration.'),
 ('Write $W=Fs=mg\\Delta h$.','The displacement against gravity is the vertical height.'),
 ('$\\Delta E_P=(2.0)(9.81)(3.0)=58.86$ J.','The work against gravity becomes gained gravitational potential energy.')],2*9.81*3,'J','Derive and calculate the gain for a 3.0 kg load raised 2.0 m at constant speed.',3*9.81*2)
work(2,2,'Calculate the gain in gravitational potential energy of a 50 kg barrel raised 1.6 m.',[
 ('Use $\\Delta E_P=mg\\Delta h$.','Only vertical height enters, even if a ramp is used.'),
 ('$\\Delta E_P=50(9.81)(1.6)=784.8$ J.','Substitute SI mass and height, then round appropriately.')],50*9.81*1.6,'J','Find the gain for a 40 kg barrel raised 2.0 m.',40*9.81*2)
work(3,3,'Derive the kinetic energy of a 3.0 kg body accelerated from rest to 4.0 m s$^{-1}$.',[
 ('Write $W=Fs$ and $F=ma$.','The net work gives the kinetic energy gained.'),
 ('From $v^2=u^2+2as$ with $u=0$, $s=v^2/(2a)$.','This is where the factor one half enters.'),
 ('$E_K=W=ma[v^2/(2a)]=\\tfrac12mv^2=24$ J.','Acceleration cancels, leaving mass and speed.')],.5*3*4**2,'J','Derive and calculate the kinetic energy of a 2.0 kg body accelerated from rest to 6.0 m s$^{-1}$.',.5*2*6**2)
work(4,4,'Find the kinetic energy of a 0.40 kg projectile at maximum height when its horizontal speed is 12 m s$^{-1}$.',[
 ('At maximum height, vertical speed is zero but horizontal speed is 12 m s$^{-1}$.','The projectile does not stop at its highest point.'),
 ('Use $E_K=\\tfrac12mv^2$.','Kinetic energy depends on the remaining speed.'),
 ('$E_K=\\tfrac12(0.40)(12)^2=28.8$ J.','Square speed before multiplying by half the mass.')],.5*.4*12**2,'J','Find the kinetic energy at the top for a 0.50 kg projectile with horizontal speed 8.0 m s$^{-1}$.',.5*.5*8**2)

pack={'subtopic':SUB,'spec':'9702','version':1,
'note':'Subjects/9702 Physics/05 Work, energy and power/5.2 Gravitational potential energy and kinetic energy.md',
'outline':'In a uniform gravitational field, work against weight changes gravitational potential energy: $W=Fs$ with $F=mg$ and vertical $s=\\Delta h$ gives $\\Delta E_P=mg\\Delta h$. Height, not path length, matters. For a constant resultant force, $W=Fs=mas$ and $v^2-u^2=2as$, so $W=\\tfrac12m(v^2-u^2)$ and $E_K=\\tfrac12mv^2$. Kinetic energy depends on speed squared. At constant falling speed it does not change, and a projectile at maximum height can still move horizontally.',
'misconceptions':mis,'worked':worked,'items':items,'flashcards':[], 'diagrams':[]}
out=ROOT/'build/out/packs/9702/9702-5.2.json'
out.parent.mkdir(parents=True,exist_ok=True)
out.write_text(json.dumps(pack,ensure_ascii=False,indent=1))
errors=validate(pack,json.loads((ROOT/'build/out/specs/9702/graph.json').read_text()))
print('draft items',len(items),'templates',sum('template' in x for x in items),'errors',len(errors))
for e in errors: print(e)
